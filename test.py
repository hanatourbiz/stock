import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="김팀장님의 통합 주식관리 시스템 V3.2", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    [data-testid="stMetric"] { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #007BFF; height: 120px !important; display: flex; flex-direction: column; justify-content: center; }
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 5px 0; padding-bottom: 5px; }
    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리 함수
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        if '시장' not in df.columns:
            df['시장'] = '국내'
            df.to_csv(DB_FILE, index=False)
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
    except: return 1450.0

# 종목 리스트 로딩 (캐시 문제 방지를 위해 로직 단순화)
@st.cache_data
def get_stock_dict():
    try:
        df_krx = fdr.StockListing('KRX')
        return {row['Name']: f"{row['Code']}{'.KS' if row['Market'] == 'KOSPI' else '.KQ'}" for _, row in df_krx.iterrows()}
    except: return {"삼성전자": "005930.KS"}

# 3. 데이터 및 세션 초기화
stock_dict = get_stock_dict()
stock_names = sorted(list(stock_dict.keys()))
exchange_rate = get_exchange_rate()

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 실시간 데이터 계산 및 정렬 ---
portfolio_details = []
total_buy_krw = total_val_krw = 0.0

if not st.session_state.portfolio.empty:
    with st.spinner('시세 동기화 중...'):
        for idx, row in st.session_state.portfolio.iterrows():
            ticker = str(row['종목코드'])
            market = row.get('시장', '국내')
            try:
                stock_obj = yf.Ticker(ticker)
                df_h = stock_obj.history(period="1mo")
                if not df_h.empty:
                    curr, mx = df_h['Close'].iloc[-1], df_h['Close'].max()
                    buy_amt, val_amt = row['평균매수가'] * row['주식수'], curr * row['주식수']
                    ex_val = exchange_rate if market == '해외' else 1
                    buy_krw, val_krw = buy_amt * ex_val, val_amt * ex_val
                    profit_krw = val_krw - buy_krw
                    p_rate = (profit_krw / buy_krw * 100) if buy_krw > 0 else 0
                    
                    portfolio_details.append({
                        'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 
                        'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': p_rate,
                        'market': market, 'val_krw': val_krw, 'profit_krw': profit_krw
                    })
                    total_buy_krw += buy_krw
                    total_val_krw += val_krw
            except: continue

# 수익금액 기준 정렬
portfolio_details = sorted(portfolio_details, key=lambda x: x['profit_krw'], reverse=True)

# --- 화면 출력 ---
st.title("📊 통합 주식관리 시스템 V3.2")

# A. 리스트 출력
for m_label, m_key in [("🇰🇷 국내 주식", "국내"), ("🇺🇸 미국 주식", "해외")]:
    m_list = [i for i in portfolio_details if i['market'] == m_key]
    if m_list:
        st.subheader(m_label)
        cols = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
        titles = ["종목명", "고점대비", "평단가", "수량", "평가금액", "현재가", "수익(원화)", "신호", "", ""]
        for i, t in enumerate(titles): cols[i].markdown(f"**{t}**")
        
        for item in m_list:
            st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True)
            r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
            unit = "원" if m_key == "국내" else "$"
            
            d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
            d[0].write(f"**{r['종목명']}**")
            drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
            d[1].write(f"{mx:,.0f}{unit}\n({drop_val:+.1f}%)")
            d[2].write(f"{r['평균매수가']:,.0f}{unit}" if m_key == "국내" else f"{unit}{r['평균매수가']:,.2f}")
            d[3].write(f"{r['주식수']}")
            d[4].write(f"{item['val_amt']:,.0f}{unit}" if m_key == "국내" else f"{unit}{item['val_amt']:,.2f}")
            d[5].write(f"{curr:,.0f}{unit}" if m_key == "국내" else f"{unit}{curr:,.2f}")
            
            color = "#dc3545" if item['profit_krw'] < 0 else "#28a745"
            d[6].markdown(f"<span style='color:{color}; font-weight:bold;'>{item['profit_krw']:,.0f}원<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
            
            sig, sig_bg = ("HOLD", "#e9ecef")
            if p_rate <= -10: sig, sig_bg = ("💥 SELL", "#dc3545")
            elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, sig_bg = ("💰 TAKE", "#28a745")
            d[7].markdown(f"<div style='background-color:{sig_bg}; color:white; padding:4px; border-radius:15px; text-align:center; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
            
            if d[8].button("📝", key=f"edit_{item['idx']}"):
                st.session_state.edit_index = item['idx']
                st.rerun()
            if d[9].button("🗑️", key=f"del_{item['idx']}"): 
                st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                save_data(st.session_state.portfolio); st.rerun()

st.divider()

# B. 종목 추가/수정 (작동 오류 해결 핵심 섹션)
is_editing = st.session_state.edit_index is not None
with st.expander("➕ 종목 추가 및 정보 수정", expanded=is_editing):
    # 폼(Form)을 사용하여 입력값 전송 시점을 제어
    with st.form("stock_form", clear_on_submit=False):
        if is_editing:
            edit_row = st.session_state.portfolio.loc[st.session_state.edit_index]
            def_market = edit_row.get('시장', '국내')
            def_name = edit_row['종목명']
            def_price = float(edit_row['평균매수가'])
            def_qty = int(edit_row['주식수'])
            def_target = int(edit_row['익절기준'])
            st.info(f"수정 모드: {def_name}")
        else:
            def_market, def_name, def_price, def_qty, def_target = "국내", "", 0.0, 0, 15

        c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
        with c1:
            m_choice = st.radio("시장", ["국내", "해외"], index=0 if def_market == "국내" else 1, horizontal=True)
        with c2:
            if m_choice == "국내":
                # 인덱스 계산 시 안전장치 추가
                try: sel_idx = stock_names.index(def_name) + 1 if def_name in stock_names else 0
                except: sel_idx = 0
                res_name = st.selectbox("종목 선택", options=["선택하세요"] + stock_names, index=sel_idx)
                res_ticker = stock_dict.get(res_name, "")
            else:
                res_name = st.text_input("해외 티커 (예: TSLA)", value=def_name if def_market == "해외" else "")
                res_ticker = res_name.upper()

        with c3: res_price = st.number_input("평단가", min_value=0.0, value=def_price)
        with c4: res_qty = st.number_input("수량", min_value=0, value=def_qty)
        
        sub_btn = st.form_submit_button("저장하기")
        
        if sub_btn:
            if res_name and res_ticker and res_name != "선택하세요":
                new_row = {"종목명": res_name, "종목코드": res_ticker, "기준일": date.today().strftime('%Y-%m-%d'), 
                           "평균매수가": res_price, "주식수": res_qty, "익절기준": def_target, "시장": m_choice}
                
                if is_editing:
                    st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                
                save_data(st.session_state.portfolio)
                st.rerun()
            else:
                st.error("종목을 정확히 선택하거나 입력해주세요.")

    if is_editing:
        if st.button("수정 취소"):
            st.session_state.edit_index = None
            st.rerun()

# C. 자산 요약
st.subheader("📊 통합 자산 요약")
curr_cash = load_cash()
t_profit_krw = total_val_krw - total_buy_krw
t_rate = (t_profit_krw / total_buy_krw * 100) if total_buy_krw > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy_krw:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val_krw:,.0f}원")
m3.metric("📈 총 수익", f"{t_profit_krw:,.0f}원", delta=f"{t_rate:.2f}%")
m4.metric("🏦 합계 자산", f"{total_val_krw + curr_cash:,.0f}원")

# D. 현금 관리
with st.container():
    st.subheader("💵 현금 관리")
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0)
    if st.button("현금 업데이트"):
        save_cash(nc); st.rerun()
