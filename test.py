import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인 주입
st.set_page_config(page_title="김팀장님의 주식관리 시스템 V2", layout="wide")

# [수정] 다른 건 안 건드리고, 모바일에서 겹치지 않게 '가로 스크롤'만 강제 적용했습니다.
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    
    /* 모바일에서 10칸이 겹치지 않도록 가로 스크롤 활성화 */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        display: flex !important;
        flex-wrap: nowrap !important;
    }
    [data-testid="column"] {
        min-width: 100px !important; /* 각 칸의 최소 너비 보장 */
        flex-shrink: 0 !important;
    }

    [data-testid="stMetric"] { 
        background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #007BFF;
        height: 120px !important; display: flex; flex-direction: column; justify-content: center;
    }
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 5px 0; padding-bottom: 5px; }
    .v-center { line-height: 2.5; font-weight: bold; }

    /* 버튼 스타일 */
    .stButton>button {
        background-color: transparent !important; border: none !important; color: #007BFF !important;
        text-decoration: underline !important; padding: 0 !important; height: auto !important; font-size: 0.85em !important;
    }
    div[data-testid="column"]:nth-child(10) .stButton>button { color: #dc3545 !important; }
    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF !important; color: white !important; border: none !important; text-decoration: none !important;}
    </style>
    """, unsafe_allow_html=True)

# --- 이후 모든 코드는 팀장님이 주신 것과 100% 동일합니다 ---

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

st.title("📈 주식 관리 대시보드")
st.write(f"**{date.today()}** 기준 | 타이밍 관리기")

if portfolio_details:
    st.subheader("🚨 실시간 모니터링 및 투자 신호")
    d_cols = [1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5]
    h = st.columns(d_cols)
    titles = ["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]
    for i, t in enumerate(titles): h[i].markdown(f"<p style='color:gray; font-size:0.9em;'><b>{t}</b></p>", unsafe_allow_html=True)
    
    for item in portfolio_details:
        st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True) 
        r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
        sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
        if p_rate <= -10: sig, clr, bg = "💥 손절(SELL)", "white", "#dc3545"
        elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절(TAKE)", "white", "#28a745"
        elif p_rate >= 50: sig, clr, bg = "🔥 ADD(추매)", "white", "#007bff"

        d = st.columns(d_cols)
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
        
        with d[8]:
            st.markdown("<div style='padding-top:12px;'></div>", unsafe_allow_html=True)
            if st.button("수정", key=f"e_{item['idx']}"): st.session_state.edit_index = item['idx']; st.rerun()
        with d[9]:
            st.markdown("<div style='padding-top:12px;'></div>", unsafe_allow_html=True)
            if st.button("삭제", key=f"d_{item['idx']}"):
                st.session_state.portfolio = st.session_state.portfolio.drop(item['idx']); save_data(st.session_state.portfolio); st.rerun()

st.divider()
# (이하 생략 - 팀장님 원본 데이터 유지)
