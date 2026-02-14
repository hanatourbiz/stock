import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="김팀장님의 주식관리 V3", layout="wide")

# 커스텀 CSS (UI 정돈)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    [data-testid="stMetric"] { 
        background-color: #f0f2f6; padding: 15px; border-radius: 10px; 
        border-left: 5px solid #007BFF; height: 110px !important;
    }
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 5px 0; padding-bottom: 5px; }
    .stButton>button[kind="primary"] { width: 100%; border-radius: 5px; background-color: #007BFF; color: white; }
    .section-title { background-color: #e1e4e8; padding: 10px; border-radius: 5px; font-weight: bold; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 관리 함수
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준", "그룹"])

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
        stocks = {row['Name']: f"{row['Code']}{'.KS' if row['Market']=='KOSPI' else '.KQ'}" for _, row in df_krx.iterrows()}
    except: stocks = {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS"}
    return stocks

stock_dict = get_stock_list()
stock_names = sorted(list(stock_dict.keys()))

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 공통 데이터 계산 함수 ---
def get_portfolio_details(df):
    details = []
    t_buy = t_val = 0.0
    for idx, row in df.iterrows():
        try:
            tk = yf.Ticker(row['종목코드'])
            df_h = tk.history(period="1mo")
            if not df_h.empty:
                curr = df_h['Close'].iloc[-1]
                mx = df_h['High'].max()
                buy_amt = row['평균매수가'] * row['주식수']
                val_amt = curr * row['주식수']
                p_rate = ((curr - row['평균매수가']) / row['평균매수가'] * 100) if row['평균매수가'] > 0 else 0
                details.append({'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': p_rate})
                t_buy += buy_amt; t_val += val_amt
        except: continue
    return sorted(details, key=lambda x: x['val_amt'], reverse=True), t_buy, t_val

# --- 상단 자산 요약 ---
st.title("📈 주식 관리 시스템 V3")
curr_cash = load_cash()
full_details, total_buy_amt, total_val_amt = get_portfolio_details(st.session_state.portfolio)

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy_amt:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val_amt:,.0f}원")
m3.metric("📈 총 수익률", f"{(total_val_amt - total_buy_amt):,.0f}원", delta=f"{(total_val_amt-total_buy_amt)/total_buy_amt*100 if total_buy_amt>0 else 0:.2f}%")
m4.metric("🏦 합계 자산", f"{total_val_amt + curr_cash:,.0f}원")

# --- 종목 입력/수정 섹션 (최상단 배치) ---
with st.container():
    is_edit = st.session_state.edit_index is not None
    st.markdown(f"<div class='section-title'>{'🔍 종목 정보 수정' if is_edit else '➕ 종목 추가'}</div>", unsafe_allow_html=True)
    
    # 수정 모드 시 기본값 로드
    d_name, d_date, d_price, d_qty, d_target, d_group = "", date.today(), 0, 0, 15, "그룹1"
    if is_edit:
        er = st.session_state.portfolio.loc[st.session_state.edit_index]
        d_name, d_date, d_price, d_qty, d_target = er['종목명'], pd.to_datetime(er['기준일']).date(), int(er['평균매수가']), int(er['주식수']), int(er['익절기준'])
        d_group = er.get('그룹', '그룹1')

    with st.form("input_form"):
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1, 0.8, 0.8, 1])
        with c1: in_name = st.selectbox("종목명", options=[""] + stock_names, index=(stock_names.index(d_name)+1 if d_name in stock_names else 0))
        with c2: in_date = st.date_input("기준일", value=d_date)
        with c3: in_price = st.number_input("평단가(원)", min_value=0, value=d_price)
        with c4: in_qty = st.number_input("수량", min_value=0, value=d_qty)
        with c5: in_target = st.number_input("익절(%)", value=d_target)
        with c6: in_group = st.radio("분류", options=["그룹1", "그룹2"], index=0 if d_group=="그룹1" else 1, horizontal=True)
        
        if st.form_submit_button("데이터 저장"):
            if in_name:
                new_row = {"종목명": in_name, "종목코드": stock_dict[in_name], "기준일": in_date.strftime('%Y-%m-%d'), 
                           "평균매수가": in_price, "주식수": in_qty, "익절기준": in_target, "그룹": in_group}
                if is_edit:
                    st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.portfolio); st.rerun()

st.divider()

# --- 리스트 출력 함수 ---
def display_stock_list(title, group_name):
    st.subheader(f"📍 {title}")
    group_items = [i for i in full_details if i['row'].get('그룹', '그룹1') == group_name]
    
    if not group_items:
        st.info("등록된 종목이 없습니다.")
        return

    h = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
    titles = ["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]
    for i, t in enumerate(titles): h[i].caption(f"**{t}**")
    
    for item in group_items:
        st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True)
        r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
        
        # 신호 로직
        sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
        if p_rate <= -10: sig, clr, bg = "💥 손절", "white", "#dc3545"
        elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절", "white", "#28a745"
        elif p_rate >= 50: sig, clr, bg = "🔥 추매", "white", "#007bff"

        d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
        d[0].markdown(f"**{r['종목명']}**")
        d[1].markdown(f"<span style='font-size:0.85em;'>{r['기준일']}<br>(高:{mx:,.0f})</span>", unsafe_allow_html=True)
        d[2].markdown(f"{r['평균매수가']:,.0f}원")
        d[3].markdown(f"{r['주식수']}")
        d[4].markdown(f"{item['val_amt']:,.0f}원")
        
        drop_val = ((curr - mx) / mx * 100) if mx > 0 else 0
        d[5].markdown(f"{curr:,.0f}원<br><span style='font-size:0.8em; color:{'#dc3545' if drop_val < 0 else '#28a745'};'>{drop_val:+.1f}%</span>", unsafe_allow_html=True)
        d[6].markdown(f"<span style='color:{'#dc3545' if p_rate < 0 else '#28a745'}; font-weight:bold;'>{(item['val_amt'] - item['buy_amt']):,.0f}원<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
        d[7].markdown(f"<div style='background-color:{bg}; color:{clr}; padding:4px 8px; border-radius:15px; text-align:center; font-weight:bold; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
        
        if d[8].button("수정", key=f"e_{item['idx']}"):
            st.session_state.edit_index = item['idx']; st.rerun()
        if d[9].button("삭제", key=f"d_{item['idx']}"):
            st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
            save_data(st.session_state.portfolio); st.rerun()

# --- 섹션 1 & 2 출력 ---
display_stock_list("주식 리스트 - 섹션 1 (그룹1)", "그룹1")
st.markdown("<br><br>", unsafe_allow_html=True)
display_stock_list("주식 리스트 - 섹션 2 (그룹2)", "그룹2")

# --- 하단 현금 관리 ---
st.divider()
st.subheader("💵 현금 관리")
c_c1, c_c2 = st.columns([1, 3])
with c_c1:
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0)
    if st.button("현금 잔액 업데이트"):
        save_cash(nc); st.rerun()
