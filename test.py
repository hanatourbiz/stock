import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인 주입
st.set_page_config(page_title="김팀장님의 주식관리 V2", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    
    /* 자산 요약 블록 크기 및 모바일 대응 */
    [data-testid="stMetric"] { 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        border-left: 5px solid #007BFF;
        min-height: 90px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-bottom: 10px;
    }
    
    /* 종목 구분선 */
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 8px 0; }
    
    /* 버튼 스타일 (텍스트 링크형 및 세로 정렬) */
    .stButton>button {
        background-color: transparent !important;
        border: none !important;
        color: #007BFF !important;
        text-decoration: underline !important;
        padding: 0 !important;
        font-size: 0.9em !important;
        height: auto !important;
        line-height: 1.5 !important;
    }
    /* 삭제 버튼 빨간색 */
    div.stButton > button[key^="d_"] { color: #dc3545 !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리 및 시세 로직 (기존 로직 100% 유지)
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

# --- 데이터 계산 (기존 로직 유지) ---
portfolio_details = []
total_buy_amt = total_val_amt = 0.0

if not st.session_state.portfolio.empty:
    with st.spinner('동기화 중...'):
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

# --- 화면 출력 (반응형 레이아웃 보정) ---
st.title("📈 주식 관리 V2")

if portfolio_details:
    st.subheader("🚨 실시간 리스트")
    
    for item in portfolio_details:
        r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
        profit_val = item['val_amt'] - item['buy_amt']
        drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
        
        # 신호 로직 유지
        sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
        if p_rate <= -10: sig, clr, bg = "💥 손절", "white", "#dc3545"
        elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절", "white", "#28a745"
        elif p_rate >= 50: sig, clr, bg = "🔥 추매", "white", "#007bff"

        # 10개 열을 5개 그룹으로 통합하여 모바일 대응
        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 1.2, 0.8])
        
        with c1: # 종목명 및 기준일
            st.markdown(f"**{r['종목명']}**\n<br><span style='font-size:0.8em; color:gray;'>{r['기준일']}</span>", unsafe_allow_html=True)
        with c2: # 평가금액 및 수익률
            st.markdown(f"**{item['val_amt']:,.0f}원**\n<br><span style='color:{'red' if p_rate < 0 else 'blue'}; font-size:0.9em;'>{p_rate:+.1f}%</span>", unsafe_allow_html=True)
        with c3: # 시세 정보
            st.markdown(f"{curr:,.0f}원\n<br><span style='color:gray; font-size:0.8em;'>고점대비 {drop_val:+.1f}%</span>", unsafe_allow_html=True)
        with c4: # 신호 뱃지
            st.markdown(f"<div style='margin-top:5px; background-color:{bg}; color:{clr}; padding:2px 5px; border-radius:10px; text-align:center; font-weight:bold; font-size:0.75em;'>{sig}</div>", unsafe_allow_html=True)
        with c5: # 관리 버튼
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("수정", key=f"e_{item['idx']}"):
                    st.session_state.edit_index = item['idx']; st.rerun()
            with bc2:
                if st.button("삭제", key=f"d_{item['idx']}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                    save_data(st.session_state.portfolio); st.rerun()
        st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True)

# 자산 요약 (하단 고정)
st.divider()
st.subheader("📊 요약")
curr_cash = load_cash()
t_profit = total_val_amt - total_buy_amt
t_rate = (t_profit / total_buy_amt * 100) if total_buy_amt > 0 else 0.0

m1, m2 = st.columns(2)
m1.metric("매수원금", f"{total_buy_amt:,.0f}")
m2.metric("현재가치", f"{total_val_amt:,.0f}")
m3, m4 = st.columns(2)
m3.metric("수익금", f"{t_profit:,.0f}", delta=f"{t_rate:.1f}%")
m4.metric("합계자산", f"{total_val_amt + curr_cash:,.0f}")

# 종목 추가/수정 섹션 생략 (기존 코드 유지)
