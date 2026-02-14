import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인 주입
st.set_page_config(page_title="김팀장님의 통합 주식관리 시스템 V2", layout="wide")

# 커스텀 CSS (기존 디자인 유지 및 보완)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    
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
    
    .stock-divider {
        border-bottom: 1px solid #e0e0e0;
        margin: 5px 0;
        padding-bottom: 5px;
    }
    
    .v-center {
        line-height: 2.5;
        font-weight: bold;
    }

    .stButton>button[kind="secondary"] {
        background-color: transparent;
        border: none;
        color: #007BFF; 
        text-decoration: underline;
        padding: 0;
        height: auto;
        font-size: 0.85em;
    }
    div[data-testid="column"]:nth-child(10) .stButton>button {
        color: #dc3545 !important;
    }

    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리 함수 및 환율 함수
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준", "시장"])

def save_data(df): df.to_csv(DB_FILE, index=False)

def load_cash():
    if os.path.exists(CASH_FILE):
        with open(CASH_FILE, "r") as f:
            try: return float(f.read())
            except: return 0.0
    return 0.0

def save_cash(cash):
    with open(CASH_FILE, "w") as f: f.write(str(cash))

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        ex_data = yf.Ticker("USDKRW=X").history(period="1d")
        return ex_data['Close'].iloc[-1]
    except:
        return 1450.0 # API 실패 시 대비

@st.cache_data
def get_stock_list():
    try:
        df_krx = fdr.StockListing('KRX')
        stocks = {}
        for _, row in df_krx.iterrows():
            code = row['Code']
            suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ" if row['Market'] == 'KOSDAQ' else ""
            stocks[row['Name']] = f"{code}{suffix}"
        return stocks
    except:
        return {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS"}

# 3. 데이터 로드 및 초기화
stock_dict = get_stock_list()
stock_names = sorted(list(stock_dict.keys()))
exchange_rate = get_exchange_rate()

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 데이터 계산 로직 ---
portfolio_details = []
total_buy_krw = total_val_krw = 0.0

if not st.session_state.portfolio.empty:
    with st.spinner('실시간 시세 및 환율 동기화 중...'):
        for idx, row in st.session_state.portfolio.iterrows():
            ticker = str(row['종목코드'])
            market = row.get('시장', '국내') # 시장 구분 정보 (없으면 국내)
            
            try:
                stock_obj = yf.Ticker(ticker)
                df_h = stock_obj.history(period="1mo")
                if not df_h.empty:
                    ref_dt = pd.to_datetime(row['기준일']).tz_localize('Asia/Seoul') if market == '국내' else pd.to_datetime(row['기준일']).tz_localize('UTC')
                    df_since = df_h[df_h.index >= ref_dt]
                    if df_since.empty: df_since = df_h
                    
                    curr, mx = df_h['Close'].iloc[-1], df_since['Close'].max()
                    buy_amt = row['평균매수가'] * row['주식수']
                    val_amt = curr * row['주식수']
                    
                    # 환율 변환 (미국 주식인 경우)
                    if market == '해외':
                        buy_krw = buy_amt * exchange_rate # 간이 계산 (매수 시점 환율은 별도 관리 필요 시 확장 가능)
                        val_krw = val_amt * exchange_rate
                    else:
                        buy_krw, val_krw = buy_amt, val_amt
                        
                    p_rate = ((curr - row['평균매수가']) / row['평균매수가'] * 100) if row['평균매수가'] > 0 else 0
                    
                    portfolio_details.append({
                        'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 
                        'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': p_rate,
                        'market': market, 'val_krw': val_krw, 'buy_krw': buy_krw
                    })
                    total_buy_krw += buy_krw
                    total_val_krw += val_krw
            except: continue

# --- 화면 구성 ---
st.title("📈 주식 관리 시스템 V2 (Global)")
st.sidebar.markdown(f"### 💱 실시간 환율\n**1 USD = {exchange_rate:,.2f} KRW**")

# --- A. 실시간 리스트 (국내/해외 분리) ---
for m_label, m_key in [("🇰🇷 국내 주식", "국내"), ("🇺🇸 미국 주식", "해외")]:
    m_list = [i for i in portfolio_details if i['market'] == m_key]
    if m_list:
        st.subheader(f"■ {m_label} 모니터링")
        h = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
        titles = ["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]
        for i, t in enumerate(titles): h[i].markdown(f"<p style='color:gray; font-size:0.8em; margin-bottom:0;'><b>{t}</b></p>", unsafe_allow_html=True)
        
        for item in m_list:
            st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True)
            r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
            unit = "원" if m_key == "국내" else "$"
            
            # 신호 로직
            sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
            if p_rate <= -10: sig, clr, bg = "💥 SELL", "white", "#dc3545"
            elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 TAKE", "white", "#28a745"
            elif p_rate >= 50: sig, clr, bg = "🔥 ADD", "white", "#007bff"

            d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
            d[0].markdown(f"**{r['종목명']}**")
            d[1].markdown(f"<span style='font-size:0.85em;'>{r['기준일']}<br>(高:{mx:,.1f})</span>", unsafe_allow_html=True)
            d[2].write(f"{r['평균매수가']:,.1f}{unit}" if m_key == "국내" else f"{unit}{r['평균매수가']:,.2f}")
            d[3].write(f"{r['주식수']}")
            d[4].write(f"{item['val_amt']:,.0f}{unit}" if m_key == "국내" else f"{unit}{item['val_amt']:,.2f}")
            
            drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
            d[5].markdown(f"{curr:,.0f}{unit}<br><span style='font-size:0.8em; color:{'#dc3545' if drop_val < 0 else '#28a745'};'>{drop_val:+.1f}%</span>", unsafe_allow_html=True)
            
            profit_val = item['val_amt'] - item['buy_amt']
            d[6].markdown(f"<span style='color:{'#dc3545' if p_rate < 0 else '#28a745'}; font-weight:bold;'>{profit_val:,.1f}{unit}<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
            d[7].markdown(f"<div style='background-color:{bg}; color:{clr}; padding:4px 8px; border-radius:15px; text-align:center; font-weight:bold; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
            
            with d[8]:
                if st.button("수정", key=f"e_{item['idx']}"):
                    st.session_state.edit_index = item['idx']; st.rerun()
            with d[9]:
                if st.button("삭제", key=f"d_{item['idx']}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                    save_data(st.session_state.portfolio); st.rerun()

st.divider()

# --- B. 종목 추가/수정 (티커 검색 보완) ---
with st.container():
    title_text = "🔍 종목 정보 수정" if st.session_state.edit_index is not None else "➕ 신규 종목 추가"
    with st.expander(title_text, expanded=(st.session_state.edit_index is not None)):
        # 기본값 설정
        def_market, def_name, def_date, def_price, def_qty, def_target = "국내", "", date.today(), 0, 0, 15
        if st.session_state.edit_index is not None:
            edit_row = st.session_state.portfolio.loc[st.session_state.edit_index]
            def_market = edit_row.get('시장', '국내')
            def_name, def_date = edit_row['종목명'], pd.to_datetime(edit_row['기준일']).date()
            def_price, def_qty, def_target = edit_row['평균매수가'], edit_row['주식수'], edit_row['익절기준']

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            add_market = st.radio("시장", ["국내", "해외"], index=0 if def_market == "국내" else 1, horizontal=True)
            if add_market == "국내":
                add_name = st.selectbox("종목명", options=[""] + stock_names, index=(stock_names.index(def_name)+1 if def_name in stock_names else 0))
                ticker_res = stock_dict.get(add_name, "")
            else:
                search_input = st.text_input("티커 또는 회사명(영문)", value=def_name if def_market == "해외" else "")
                if search_input:
                    try:
                        s_obj = yf.Ticker(search_input)
                        ticker_res = s_obj.ticker.upper()
                        add_name = search_input.upper()
                        st.caption(f"✅ 인식된 티커: **{ticker_res}**")
                    except: ticker_res = search_input.upper(); add_name = search_input
                else: ticker_res = ""; add_name = ""

        with c2: add_date = st.date_input("기준일", value=def_date)
        with c3: add_price = st.number_input(f"평균매수가({'원' if add_market=='국내' else '$'})", min_value=0.0, value=float(def_price), step=0.1)
        with c4: add_qty = st.number_input("수량", min_value=0, value=int(def_qty))
        with c5: add_target = st.number_input("익절기준(%)", value=int(def_target))

        if st.button("저장하기", type="primary"):
            if add_name and ticker_res:
                new_row = {"종목명": add_name, "종목코드": ticker_res, "기준일": add_date.strftime('%Y-%m-%d'), 
                           "평균매수가": add_price, "주식수": add_qty, "익절기준": add_target, "시장": add_market}
                if st.session_state.edit_index is not None:
                    st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.portfolio); st.rerun()

# --- C. 자산 요약 (환율 반영 합산) ---
st.subheader("📊 통합 자산 요약 (원화 환산)")
curr_cash = load_cash()
t_profit_krw = total_val_krw - total_buy_krw
t_rate = (t_profit_krw / total_buy_krw * 100) if total_buy_krw > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy_krw:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val_krw:,.0f}원")
m3.metric("📈 총 수익 (수익률)", f"{t_profit_krw:,.0f}원", delta=f"{t_rate:.2f}%")
m4.metric("🏦 합계 자산(현금포함)", f"{total_val_krw + curr_cash:,.0f}원")

# --- D. 비중 분석 및 현금 관리 ---
c_btm1, c_btm2 = st.columns([1.5, 1])
with c_btm1:
    if total_val_krw > 0:
        st.subheader("🥧 자산 구성 비중")
        p_data = pd.DataFrame([{'종목': i['row']['종목명'], '금액': i['val_krw']} for i in portfolio_details])
        p_data = pd.concat([p_data, pd.DataFrame([{'종목': '예수금', '금액': curr_cash}])])
        fig = px.pie(p_data, values='금액', names='종목', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig, use_container_width=True)

with c_btm2:
    st.subheader("💵 현금 관리")
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0)
    if st.button("현금 잔액 업데이트"):
        save_cash(nc); st.rerun()
