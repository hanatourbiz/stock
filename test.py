import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인 주입
st.set_page_config(page_title="김팀장님의 주식관리 시스템 V2", layout="wide")

# 커스텀 CSS: 자산 요약 및 버튼 스타일 수정
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    
    /* 자산 요약 블록 크기 고정 */
    [data-testid="stMetric"] { 
        background-color: #f0f2f6; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #007BFF;
        height: 120px !important; 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* 종목 간 구분선 */
    .stock-divider {
        border-bottom: 1px solid #e0e0e0;
        margin: 5px 0;
        padding-bottom: 5px;
    }
    
    /* 세로 중앙 정렬용 스타일 */
    .v-center {
        line-height: 2.5;
        font-weight: bold;
    }

    /* [수정] 리스트 내 버튼 스타일링: 배경 제거 및 텍스트 강조 */
    .stButton>button[kind="secondary"] {
        background-color: transparent;
        border: none;
        color: #007BFF; /* 수정 버튼 파란색 */
        text-decoration: underline;
        padding: 0;
        height: auto;
        font-size: 0.85em;
    }
    /* 삭제 버튼 전용 스타일 (빨간색) */
    div[data-testid="column"]:nth-child(10) .stButton>button {
        color: #dc3545 !important;
    }

    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; border: none; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리 함수 (유지)
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준"])

def save_data(df): df.to_csv(DB_FILE, index=False)

def load_cash():
    if os.path.exists(CASH_FILE):
        with open(CASH_FILE, "r") as f:
            try: return float(f.read())
            except: return 0.0
    return 0.0

def save_cash(cash):
    with open(CASH_FILE, "w") as f: f.write(str(cash))

# [수정] KRX 접속 에러 방지용 함수
@st.cache_data
def get_stock_list():
    try:
        df_krx = fdr.StockListing('KRX')
        stocks = df_krx[['Name', 'Code']].set_index('Name').to_dict()['Code']
    except:
        try:
            df_krx = fdr.StockListing('KOSPI')
            df_kosdaq = fdr.StockListing('KOSDAQ')
            df_combined = pd.concat([df_krx, df_kosdaq])
            stocks = df_combined[['Name', 'Code']].set_index('Name').to_dict()['Code']
        except:
            stocks = {"삼성전자": "005930", "SK하이닉스": "000660"} 
    try:
        df_etf = fdr.StockListing('ETF/KR')
        etfs = df_etf[['Name', 'Symbol']].set_index('Name').to_dict()['Symbol']
        stocks.update(etfs)
    except: pass
    return stocks

stock_dict = get_stock_list()
stock_names = sorted(list(stock_dict.keys()))

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 데이터 계산 (상단 처리) ---
portfolio_details = []
total_buy_amt = total_val_amt = 0.0

if not st.session_state.portfolio.empty:
    with st.spinner('실시간 시세 동기화 중...'):
        for idx, row in st.session_state.portfolio.iterrows():
            ticker = str(row['종목코드'])
            yf_ticker = f"{ticker}.KS" if ticker.isdigit() and len(ticker)==6 else ticker
            try:
                df_h = yf.Ticker(yf_ticker).history(period="1y")
                if not df_h.empty:
                    ref_dt = pd.to_datetime(row['기준일']).tz_localize('Asia/Seoul')
                    df_since = df_h[df_h.index >= ref_dt]
                    if df_since.empty: df_since = df_h
                    curr, mx = df_h['Close'].iloc[-1], df_since['Close'].max()
                    buy_amt, val_amt = row['평균매수가'] * row['주식수'], curr * row['주식수']
                    p_rate = ((curr - row['평균매수가']) / row['평균매수가'] * 100) if row['평균매수가'] > 0 else 0
                    
                    portfolio_details.append({'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': p_rate})
                    total_buy_amt += buy_amt; total_val_amt += val_amt
            except: continue
    portfolio_details = sorted(portfolio_details, key=lambda x: x['val_amt'], reverse=True)

# --- 타이틀 ---
st.title("📈 주식 관리 대시보드")
st.write(f"**{date.today()}** 기준 | 타이밍 관리기")

# --- A. 실시간 리스트 (버튼 텍스트 및 스타일 수정) ---
if portfolio_details:
    st.subheader("🚨 실시간 모니터링 및 투자 신호")
    h = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5]) # 너비 소폭 조정
    titles = ["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]
    for i, t in enumerate(titles): h[i].markdown(f"<p style='color:gray; font-size:0.9em;'><b>{t}</b></p>", unsafe_allow_html=True)
    
    for item in portfolio_details:
        st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True) 
        r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
        sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
        if p_rate <= -10: sig, clr, bg = "💥 손절(SELL)", "white", "#dc3545"
        elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절(TAKE)", "white", "#28a745"
        elif p_rate >= 50: sig, clr, bg = "🔥 ADD(추매)", "white", "#007bff"

        d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5])
        
        d[0].markdown(f"<div class='v-center'>{r['종목명']}</div>", unsafe_allow_html=True)
        d[1].markdown(f"<span style='font-size:0.85em;'>{r['기준일']}<br>(高:{mx:,.0f})</span>", unsafe_allow_html=True)
        d[2].markdown(f"<div class='v-center'>{r['평균매수가']:,.0f}</div>", unsafe_allow_html=True)
        d[3].markdown(f"<div class='v-center'>{r['주식수']}</div>", unsafe_allow_html=True)
        d[4].markdown(f"<div class='v-center'>{item['val_amt']:,.0f}원</div>", unsafe_allow_html=True)
        
        drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
        d[5].markdown(f"{curr:,.0f}원<br><span style='font-size:0.8em; color:{'#dc3545' if drop_val < 0 else '#28a745'};'>{drop_val:+.1f}%</span>", unsafe_allow_html=True)
        
        profit_val = item['val_amt'] - item['buy_amt']
        d[6].markdown(f"<span style='color:{'#dc3545' if p_rate < 0 else '#28a745'}; font-weight:bold;'>{profit_val:,.0f}원<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
        
        d[7].markdown(f"<div style='margin-top:12px; background-color:{bg}; color:{clr}; padding:4px 8px; border-radius:15px; text-align:center; font-weight:bold; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
        
        # [수정] 아이콘 대신 텍스트로 변경 및 세로 중앙 정렬
        with d[8]:
            st.markdown("<div style='padding-top:12px;'></div>", unsafe_allow_html=True)
            if st.button("수정", key=f"e_{item['idx']}"):
                st.session_state.edit_index = item['idx']; st.rerun()
        with d[9]:
            st.markdown("<div style='padding-top:12px;'></div>", unsafe_allow_html=True)
            if st.button("삭제", key=f"d_{item['idx']}"):
                st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                save_data(st.session_state.portfolio); st.rerun()

st.divider()

# --- B. 종목 추가/수정 (유지) ---
with st.container():
    title_text = "🔍 종목 정보 수정" if st.session_state.edit_index is not None else "➕ 신규 종목 추가"
    with st.expander(title_text, expanded=(st.session_state.edit_index is not None)):
        def_name, def_date, def_price, def_qty, def_target = "", date.today(), 0, 0, 15
        if st.session_state.edit_index is not None:
            edit_row = st.session_state.portfolio.loc[st.session_state.edit_index]
            def_name, def_date = edit_row['종목명'], pd.to_datetime(edit_row['기준일']).date()
            def_price, def_qty, def_target = int(edit_row['평균매수가']), int(edit_row['주식수']), int(edit_row['익절기준'])

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: add_name = st.selectbox("종목명", options=[""] + stock_names, index=(stock_names.index(def_name)+1 if def_name in stock_names else 0))
        with c2: add_date = st.date_input("기준일", value=def_date)
        with c3: add_price = st.number_input("평균매수가", min_value=0, value=def_price)
        with c4: add_qty = st.number_input("수량", min_value=0, value=def_qty)
        with c5: add_target = st.number_input("익절기준(%)", value=def_target)

        if st.button("저장", type="primary"):
            if add_name:
                code = stock_dict[add_name]
                new_row = {"종목명": add_name, "종목코드": f"{code}.KS" if str(code).isdigit() and len(str(code))==6 else code, "기준일": add_date.strftime('%Y-%m-%d'), "평균매수가": add_price, "주식수": add_qty, "익절기준": add_target}
                if st.session_state.edit_index is not None:
                    st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.portfolio); st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# --- C. 자산 요약 (하단 배치 및 크기 통일) ---
st.subheader("📊 자산 요약 현황")
curr_cash = load_cash()
t_profit = total_val_amt - total_buy_amt
t_rate = (t_profit / total_buy_amt * 100) if total_buy_amt > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy_amt:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val_amt:,.0f}원")
m3.metric("📈 총 수익 (수익률)", f"{t_profit:,.0f}원", delta=f"{t_rate:.2f}%")
m4.metric("🏦 합계 자산(현금포함)", f"{total_val_amt + curr_cash:,.0f}원")

st.markdown("<br>", unsafe_allow_html=True)

# --- D. 비중 분석 및 현금 관리 ---
c_btm1, c_btm2 = st.columns([1.5, 1])
with c_btm1:
    if total_val_amt > 0:
        st.subheader("🥧 자산 구성 비중")
        p_data = pd.DataFrame([{'종목': i['row']['종목명'], '금액': i['val_amt']} for i in portfolio_details])
        p_data = pd.concat([p_data, pd.DataFrame([{'종목': '예수금', '금액': curr_cash}])])
        fig = px.pie(p_data, values='금액', names='종목', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

with c_btm2:
    st.subheader("💵 현금 관리")
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0)
    if st.button("현금 잔액 업데이트"):
        save_cash(nc); st.rerun()
