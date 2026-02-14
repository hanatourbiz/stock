import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date
import plotly.express as px

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="김팀장님의 주식관리 시스템 V2", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    [data-testid="stMetric"] { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #007BFF; height: 120px !important; display: flex; flex-direction: column; justify-content: center; }
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 5px 0; padding-bottom: 5px; }
    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준"])

def save_data(df): df.to_csv(DB_FILE, index=False)

@st.cache_data
def get_stock_list():
    try:
        df_krx = fdr.StockListing('KRX')
        stocks = {}
        for _, row in df_krx.iterrows():
            suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ" if row['Market'] == 'KOSDAQ' else ""
            stocks[row['Name']] = f"{row['Code']}{suffix}"
        try:
            df_etf = fdr.StockListing('ETF/KR')
            for _, row in df_etf.iterrows(): stocks[row['Name']] = f"{row['Symbol']}.KS"
        except: pass
        return stocks
    except: return {"삼성전자": "005930.KS"}

stock_dict = get_stock_list()

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 데이터 계산 로직 (기존과 동일) ---
portfolio_details = []
total_buy_amt = total_val_amt = 0.0
if not st.session_state.portfolio.empty:
    for idx, row in st.session_state.portfolio.iterrows():
        try:
            df_h = yf.Ticker(str(row['종목코드'])).history(period="1mo")
            if not df_h.empty:
                curr = df_h['Close'].iloc[-1]
                mx = df_h[df_h.index >= pd.to_datetime(row['기준일']).tz_localize('Asia/Seoul')]['Close'].max() if not df_h.empty else curr
                buy_amt, val_amt = row['평균매수가'] * row['주식수'], curr * row['주식수']
                portfolio_details.append({'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': (curr-row['평균매수가'])/row['평균매수가']*100})
                total_buy_amt += buy_amt; total_val_amt += val_amt
        except: continue

# --- 화면 표시 ---
st.title("📈 주식 관리 대시보드")

# [A. 리스트] 수정 버튼 클릭 시 st.rerun()으로 상태 반영됨
if portfolio_details:
    for item in portfolio_details:
        r = item['row']
        d = st.columns([2, 1, 1, 1, 1, 1, 1])
        d[0].write(f"**{r['종목명']}**")
        if d[5].button("수정", key=f"btn_e_{item['idx']}"):
            st.session_state.edit_index = item['idx']
            st.rerun()
        if d[6].button("삭제", key=f"btn_d_{item['idx']}"):
            st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
            save_data(st.session_state.portfolio); st.rerun()

st.divider()

# --- [B. 종목 추가/수정] 문제 해결 핵심 섹션 ---
with st.expander("🔍 종목 정보 입력/수정", expanded=(st.session_state.edit_index is not None)):
    # 초기값 설정
    def_name, def_date, def_price, def_qty, def_target = "", date.today(), 0, 0, 15
    def_mkt_idx = 0
    etf_list = ["KODEX", "TIGER", "RISE", "ACE", "SOL", "ARIRANG", "HANARO", "KOSEF", "KBSTAR"]

    if st.session_state.edit_index is not None:
        edit_row = st.session_state.portfolio.loc[st.session_state.edit_index]
        def_name = edit_row['종목명']
        def_date = pd.to_datetime(edit_row['기준일']).date()
        def_price, def_qty, def_target = int(edit_row['평균매수가']), int(edit_row['주식수']), int(edit_row['익절기준'])
        
        # 수정 모드일 때 시장 자동 판별
        if any(etf in def_name.upper() for etf in etf_list): def_mkt_idx = 2 # ETF
        elif ".KQ" in edit_row['종목코드']: def_mkt_idx = 1 # KOSDAQ
        else: def_mkt_idx = 0 # KOSPI

    c0, c1, c2, c3, c4, c5 = st.columns([1, 2, 1.5, 1, 1, 1])
    
    with c0:
        m_choice = st.selectbox("시장", ["KOSPI", "KOSDAQ", "ETF"], index=def_mkt_idx)
    
    with c1:
        # 시장 선택에 따른 리스트 생성
        if m_choice == "KOSPI":
            items = [n for n, c in stock_dict.items() if ".KS" in c and not any(etf in n.upper() for etf in etf_list)]
        elif m_choice == "KOSDAQ":
            items = [n for n, c in stock_dict.items() if ".KQ" in c]
        else:
            items = [n for n, c in stock_dict.items() if any(etf in n.upper() for etf in etf_list)]
        
        items = sorted(items)
        # 종목명 매칭 (수정 모드 대응)
        try:
            name_idx = items.index(def_name) + 1 if def_name in items else 0
        except: name_idx = 0
        
        add_name = st.selectbox("종목명", options=["선택하세요"] + items, index=name_idx)

    # ... 나머지 입력 필드 및 저장 로직 ...
    add_date = c2.date_input("기준일", value=def_date)
    add_price = c3.number_input("평단가", value=def_price)
    add_qty = c4.number_input("수량", value=def_qty)
    add_target = c5.number_input("익절%", value=def_target)

    if st.button("데이터 저장하기", type="primary"):
        if add_name != "선택하세요":
            new_data = {"종목명": add_name, "종목코드": stock_dict[add_name], "기준일": add_date.strftime('%Y-%m-%d'), "평균매수가": add_price, "주식수": add_qty, "익절기준": add_target}
            if st.session_state.edit_index is not None:
                st.session_state.portfolio.loc[st.session_state.edit_index] = new_data
                st.session_state.edit_index = None
            else:
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.portfolio); st.rerun()
