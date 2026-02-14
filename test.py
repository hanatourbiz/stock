import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="김팀장님의 주식관리 시스템 V2.9", layout="wide")

# 커스텀 CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    [data-testid="stMetric"] { 
        background-color: #f0f2f6; padding: 15px; border-radius: 10px; 
        border-left: 5px solid #007BFF; height: 120px !important; 
        display: flex; flex-direction: column; justify-content: center;
    }
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
        if '통화' not in df.columns: df['통화'] = 'KRW'
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준", "통화"])

def save_data(df): df.to_csv(DB_FILE, index=False)
def load_cash():
    if os.path.exists(CASH_FILE):
        with open(CASH_FILE, "r") as f:
            try: return float(f.read())
            except: return 0.0
    return 0.0
def save_cash(cash):
    with open(CASH_FILE, "w") as f: f.write(str(cash))

# 실시간 환율 정보
@st.cache_data(ttl=3600)
def get_exchange_rates():
    rates = {'KRW': 1.0}
    symbols = {'USD': 'USDKRW=X', 'JPY': 'JPYKRW=X', 'GBP': 'GBPKRW=X', 'CHF': 'CHFKRW=X'}
    for curr, sym in symbols.items():
        try:
            data = yf.Ticker(sym).history(period="1d")
            rates[curr] = data['Close'].iloc[-1]
        except: rates[curr] = 1.0 if curr != 'JPY' else 9.0
    return rates

# [핵심 수정] 종목 리스트 로딩 및 비상용 샘플링
@st.cache_data
def get_combined_stock_list():
    stocks = {}
    # 기본 해외 종목 (서버 에러 시에도 항상 노출)
    overseas = {
        "[USA] Apple": ("AAPL", "USD"), "[USA] Tesla": ("TSLA", "USD"), 
        "[USA] NVIDIA": ("NVDA", "USD"), "[UK] AstraZeneca": ("AZN.L", "GBP"),
        "[JPN] Toyota": ("7203.T", "JPY"), "[SUI] Nestle": ("NESN.SW", "CHF")
    }
    stocks.update(overseas)
    
    try:
        # 한국 시장 종목 불러오기
        df_krx = fdr.StockListing('KRX')
        if not df_krx.empty:
            for _, row in df_krx.iterrows():
                code = row['Code']
                market = row['Market']
                suffix = ".KS" if market == 'KOSPI' else ".KQ" if market == 'KOSDAQ' else ""
                display_name = f"[{market}] {row['Name']}"
                stocks[display_name] = (f"{code}{suffix}", "KRW")
    except Exception as e:
        # 오류 발생 시 최소한의 대형주라도 수동 추가
        stocks["[KOSPI] 삼성전자"] = ("005930.KS", "KRW")
        stocks["[KOSPI] SK하이닉스"] = ("000660.KS", "KRW")
    
    return stocks

# 초기 데이터 로드
stock_info_dict = get_combined_stock_list()
stock_names = sorted(list(stock_info_dict.keys()))
exchange_rates = get_exchange_rates()

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 데이터 계산 및 평가금액 순 정렬 ---
portfolio_details = []
total_buy_amt_krw = total_val_amt_krw = 0.0

if not st.session_state.portfolio.empty:
    with st.spinner('시세 동기화 중...'):
        for idx, row in st.session_state.portfolio.iterrows():
            ticker = str(row['종목코드'])
            currency = row.get('통화', 'KRW')
            rate = exchange_rates.get(currency, 1.0)
            try:
                # 데이터 수집 (안전성을 위해 5일치만)
                tk = yf.Ticker(ticker)
                df_h = tk.history(period="5d") 
                if not df_h.empty:
                    curr_price = df_h['Close'].iloc[-1]
                    max_price = df_h['High'].max()
                    buy_amt_krw = (row['평균매수가'] * row['주식수']) * rate
                    val_amt_krw = (curr_price * row['주식수']) * rate
                    p_rate = ((curr_price - row['평균매수가']) / row['평균매수가'] * 100) if row['평균매수가'] > 0 else 0
                    
                    portfolio_details.append({
                        'idx': idx, 'row': row, 'curr': curr_price, 'mx': max_price, 
                        'val_amt': val_amt_krw, 'buy_amt': buy_amt_krw, 'p_rate': p_rate, 'currency': currency
                    })
                    total_buy_amt_krw += buy_amt_krw
                    total_val_amt_krw += val_amt_krw
            except: continue
    # 1. 평가금액순 정렬
    portfolio_details = sorted(portfolio_details, key=lambda x: x['val_amt'], reverse=True)

# --- 타이틀 ---
st.title("📈 주식 관리 대시보드")
cols_rate = st.columns(4)
cols_rate[0].caption(f"🇺🇸 USD: {exchange_rates['USD']:,.0f}원")
cols_rate[1].caption(f"🇯🇵 JPY(100): {exchange_rates['JPY']*100:,.0f}원")
cols_rate[2].caption(f"🇬🇧 GBP: {exchange_rates['GBP']:,.0f}원")
cols_rate[3].caption(f"🇨🇭 CHF: {exchange_rates['CHF']:,.0f}원")

# --- A. 실시간 리스트 ---
if portfolio_details:
    st.subheader("■ 실시간 모니터링")
    h = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
    titles = ["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]
    for i, t in enumerate(titles): h[i].markdown(f"<p style='color:gray; font-size:0.9em; margin-bottom:0;'><b>{t}</b></p>", unsafe_allow_html=True)
    
    for item in portfolio_details:
        st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True) 
        r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
        
        sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
        if p_rate <= -10: sig, clr, bg = "💥 손절(SELL)", "white", "#dc3545"
        elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절(TAKE)", "white", "#28a745"
        elif p_rate >= 50: sig, clr, bg = "🔥 ADD(추매)", "white", "#007bff"

        d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
        d[0].markdown(f"**{r['종목명']}**")
        d[1].markdown(f"<span style='font-size:0.85em;'>{r['기준일']}<br>(高:{mx:,.0f})</span>", unsafe_allow_html=True)
        d[2].markdown(f"{r['평균매수가']:,.0f}원")
        d[3].markdown(f"{r['주식수']}")
        d[4].markdown(f"{item['val_amt']:,.0f}원")
        
        drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
        d[5].markdown(f"{curr:,.0f}원<br><span style='font-size:0.8em; color:{'#dc3545' if drop_val < 0 else '#28a745'};'>{drop_val:+.1f}%</span>", unsafe_allow_html=True)
        profit_val_krw = item['val_amt'] - item['buy_amt']
        d[6].markdown(f"<span style='color:{'#dc3545' if p_rate < 0 else '#28a745'}; font-weight:bold;'>{profit_val_krw:,.0f}원<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
        d[7].markdown(f"<div style='background-color:{bg}; color:{clr}; padding:4px 8px; border-radius:15px; text-align:center; font-weight:bold; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
        
        with d[8]:
            if st.button("수정", key=f"edit_{item['idx']}"):
                st.session_state.edit_index = item['idx']
                st.rerun()
        with d[9]:
            if st.button("삭제", key=f"del_{item['idx']}"):
                st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                save_data(st.session_state.portfolio)
                st.rerun()

st.divider()

# --- B. 종목 추가 및 수정 (입력 문제 해결) ---
with st.container():
    edit_idx = st.session_state.edit_index
    is_editing = edit_idx is not None
    
    st.subheader("➕ 종목 추가 및 수정" if not is_editing else "🔍 종목 정보 수정")
    
    # 폼 기본값 설정
    f_name = ""
    f_date = date.today()
    f_price = 0.0
    f_qty = 0
    f_target = 15
    
    if is_editing and edit_idx in st.session_state.portfolio.index:
        row = st.session_state.portfolio.loc[edit_idx]
        f_name = row['종목명']
        f_date = pd.to_datetime(row['기준일']).date()
        f_price = float(row['평균매수가'])
        f_qty = int(row['주식수'])
        f_target = int(row['익절기준'])

    # 입력 UI
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        # 검색 가능한 selectbox
        sel_name = st.selectbox("종목 검색", options=[""] + stock_names, 
                                index=(stock_names.index(f_name) + 1 if f_name in stock_names else 0),
                                key="stock_selector")
    with c2:
        sel_date = st.date_input("기준일", value=f_date, key="stock_date")
    with c3:
        sel_price = st.number_input("평단가", min_value=0.0, value=f_price, key="stock_price")
    with c4:
        sel_qty = st.number_input("수량", min_value=0, value=f_qty, key="stock_qty")
    with c5:
        sel_target = st.number_input("익절기준(%)", value=f_target, key="stock_target")

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("저장하기", type="primary", key="save_btn"):
            if sel_name:
                code_val, curr_val = stock_info_dict[sel_name]
                new_data = {
                    "종목명": sel_name, "종목코드": code_val, "기준일": sel_date.strftime('%Y-%m-%d'),
                    "평균매수가": sel_price, "주식수": sel_qty, "익절기준": sel_target, "통화": curr_val
                }
                if is_editing:
                    st.session_state.portfolio.loc[edit_idx] = new_data
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_data])], ignore_index=True)
                
                save_data(st.session_state.portfolio)
                st.rerun()
    
    with col_btn2:
        if is_editing:
            if st.button("수정 취소", key="cancel_btn"):
                st.session_state.edit_index = None
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# --- C. 자산 요약 ---
st.subheader("📊 자산 요약 현황")
curr_cash = load_cash()
t_profit_krw = total_val_amt_krw - total_buy_amt_krw
t_rate = (t_profit_krw / total_buy_amt_krw * 100) if total_buy_amt_krw > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy_amt_krw:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val_amt_krw:,.0f}원")
m3.metric("📈 총 수익 (수익률)", f"{t_profit_krw:,.0f}원", delta=f"{t_rate:.2f}%")
m4.metric("🏦 합계 자산(현금포함)", f"{total_val_amt_krw + curr_cash:,.0f}원")

st.markdown("<br>", unsafe_allow_html=True)

# --- D. 현금 관리 ---
st.subheader("💵 현금 관리")
c_cash1, _ = st.columns([1, 2])
with c_cash1:
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0, key="cash_input")
    if st.button("현금 잔액 업데이트", key="update_cash_btn"):
        save_cash(nc); st.rerun()
