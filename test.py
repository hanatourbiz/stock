import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="김팀장님의 주식관리 시스템 V3.1", layout="wide")

# 커스텀 CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto+Sans+KR', sans-serif; }
    [data-testid="stMetric"] { 
        background-color: #f0f2f6; padding: 15px; border-radius: 10px; 
        border-left: 5px solid #007BFF; height: 110px !important;
    }
    .stock-divider { border-bottom: 1px solid #e0e0e0; margin: 8px 0; padding-bottom: 8px; }
    .section-header { 
        background: linear-gradient(90deg, #007BFF 0%, #00d4ff 100%);
        color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold; margin: 20px 0;
    }
    .stButton>button[kind="primary"] { width: 100%; height: 3em; background-color: #007BFF; color: white; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 및 종목 리스트 로드 (에러 방지 강화)
DB_FILE = "portfolio.csv"
CASH_FILE = "cash.txt"

def load_data():
    if os.path.exists(DB_FILE): 
        df = pd.read_csv(DB_FILE)
        df['기준일'] = pd.to_datetime(df['기준일']).dt.strftime('%Y-%m-%d')
        if '그룹' not in df.columns: df['그룹'] = '섹션1'
        return df
    return pd.DataFrame(columns=["종목명", "종목코드", "기준일", "평균매수가", "주식수", "익절기준", "그룹"])

def save_data(df): df.to_csv(DB_FILE, index=False)
def load_cash():
    if os.path.exists(CASH_FILE):
        with open(CASH_FILE, "r") as f:
            try: return float(f.read())
            except: return 0.0
    return 0.0

@st.cache_data(ttl=86400) # 하루 단위 캐시
def get_full_stock_list():
    try:
        # 코스피, 코스닥 종목 리스트 결합
        df_krx = fdr.StockListing('KRX')
        stocks = {row['Name']: f"{row['Code']}{'.KS' if row['Market']=='KOSPI' else '.KQ'}" for _, row in df_krx.iterrows()}
        if not stocks: raise Exception("Empty List")
        return stocks
    except:
        # 서버 연결 실패 시 비상용 기본 리스트
        return {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "NAVER": "035420.KS"}

stock_dict = get_full_stock_list()
stock_names = sorted(list(stock_dict.keys()))

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data()
if 'edit_index' not in st.session_state: st.session_state.edit_index = None

# --- 실시간 데이터 계산 ---
def calculate_portfolio(df):
    details = []
    t_buy = t_val = 0.0
    if df.empty: return [], 0, 0
    
    with st.spinner('실시간 시세 업데이트 중...'):
        for idx, row in df.iterrows():
            try:
                tk = yf.Ticker(row['종목코드'])
                df_h = tk.history(period="5d") # 속도를 위해 5일치만
                if not df_h.empty:
                    curr = df_h['Close'].iloc[-1]
                    mx = df_h['High'].max()
                    buy_amt = row['평균매수가'] * row['주식수']
                    val_amt = curr * row['주식수']
                    p_rate = ((curr - row['평균매수가']) / row['평균매수가'] * 100) if row['평균매수가'] > 0 else 0
                    details.append({'idx': idx, 'row': row, 'curr': curr, 'mx': mx, 'val_amt': val_amt, 'buy_amt': buy_amt, 'p_rate': p_rate, 'group': row.get('그룹', '섹션1')})
                    t_buy += buy_amt; t_val += val_amt
            except: continue
    return sorted(details, key=lambda x: x['val_amt'], reverse=True), t_buy, t_val

# 상단 요약 정보
full_details, total_buy, total_val = calculate_portfolio(st.session_state.portfolio)
curr_cash = load_cash()

st.title("📈 김팀장님의 통합 주식관리 시스템")
m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 총 매수원금", f"{total_buy:,.0f}원")
m2.metric("📊 현재 평가액", f"{total_val:,.0f}원")
m3.metric("📈 평가손익", f"{(total_val - total_buy):,.0f}원", delta=f"{(total_val-total_buy)/total_buy*100 if total_buy>0 else 0:.2f}%")
m4.metric("🏦 총 합계자산", f"{total_val + curr_cash:,.0f}원")

# --- 입력 및 리스트 출력 함수 ---
def render_section(section_id, display_title):
    st.markdown(f"<div class='section-header'>{display_title}</div>", unsafe_allow_html=True)
    
    # 1. 해당 섹션용 입력창 (검색 기능 포함)
    with st.expander(f"➕ {display_title} 종목 추가/수정", expanded=(st.session_state.edit_index is not None)):
        # 수정 모드 확인
        def_name, def_date, def_price, def_qty, def_target = "", date.today(), 0, 0, 15
        if st.session_state.edit_index is not None:
            er = st.session_state.portfolio.loc[st.session_state.edit_index]
            if er.get('그룹', '섹션1') == section_id:
                def_name, def_date, def_price, def_qty, def_target = er['종목명'], pd.to_datetime(er['기준일']).date(), int(er['평균매수가']), int(er['주식수']), int(er['익절기준'])

        with st.form(key=f"form_{section_id}"):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            with c1: in_name = st.selectbox("종목 검색 및 선택", options=[""] + stock_names, index=(stock_names.index(def_name)+1 if def_name in stock_names else 0))
            with c2: in_date = st.date_input("기준일", value=def_date)
            with c3: in_price = st.number_input("평단가(원)", min_value=0, value=def_price)
            with c4: in_qty = st.number_input("수량", min_value=0, value=def_qty)
            with c5: in_target = st.number_input("익절(%)", value=def_target)
            
            if st.form_submit_button("이 섹션에 저장"):
                if in_name:
                    new_row = {"종목명": in_name, "종목코드": stock_dict[in_name], "기준일": in_date.strftime('%Y-%m-%d'), 
                               "평균매수가": in_price, "주식수": in_qty, "익절기준": in_target, "그룹": section_id}
                    if st.session_state.edit_index is not None:
                        st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                        st.session_state.edit_index = None
                    else:
                        st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(st.session_state.portfolio); st.rerun()

    # 2. 해당 섹션 리스트 출력
    items = [i for i in full_details if i.get('group') == section_id]
    if items:
        h = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
        for i, t in enumerate(["종목명", "기준일(고점)", "평단가", "수량", "평가금액", "현재가(대비)", "수익(률)", "신호", "", ""]):
            h[i].caption(f"**{t}**")
        
        for item in items:
            st.markdown("<div class='stock-divider'></div>", unsafe_allow_html=True)
            r, curr, mx, p_rate = item['row'], item['curr'], item['mx'], item['p_rate']
            sig, clr, bg = "HOLD", "#6c757d", "#e9ecef"
            if p_rate <= -10: sig, clr, bg = "💥 손절", "white", "#dc3545"
            elif curr <= (mx * (1 - r['익절기준']/100)) and p_rate > 0: sig, clr, bg = "💰 익절", "white", "#28a745"
            elif p_rate >= 50: sig, clr, bg = "🔥 추매", "white", "#007bff"

            d = st.columns([1.5, 1.2, 0.8, 0.5, 1.2, 1.2, 1.2, 1.0, 0.5, 0.5], vertical_alignment="center")
            d[0].markdown(f"**{r['종목명']}**")
            d[1].markdown(f"<span style='font-size:0.85em;'>{r['기준일']}<br>(高:{mx:,.0f}원)</span>", unsafe_allow_html=True)
            d[2].markdown(f"{r['평균매수가']:,.0f}원")
            d[3].markdown(f"{r['주식수']}")
            d[4].markdown(f"{item['val_amt']:,.0f}원")
            d[5].markdown(f"{curr:,.0f}원<br><small>{((curr-mx)/mx*100):+.1f}%</small>", unsafe_allow_html=True)
            d[6].markdown(f"<span style='color:{'#dc3545' if p_rate < 0 else '#28a745'}; font-weight:bold;'>{(item['val_amt']-item['buy_amt']):,.0f}원<br>({p_rate:.1f}%)</span>", unsafe_allow_html=True)
            d[7].markdown(f"<div style='background-color:{bg}; color:{clr}; padding:4px 8px; border-radius:15px; text-align:center; font-weight:bold; font-size:0.7em;'>{sig}</div>", unsafe_allow_html=True)
            if d[8].button("수정", key=f"e_{item['idx']}"):
                st.session_state.edit_index = item['idx']; st.rerun()
            if d[9].button("삭제", key=f"d_{item['idx']}"):
                st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                save_data(st.session_state.portfolio); st.rerun()
    else:
        st.info("이 섹션에 등록된 종목이 없습니다.")

# 섹션 1과 2 실행
render_section("섹션1", "📊 주식 포트폴리오 1세트")
render_section("섹션2", "📊 주식 포트폴리오 2세트")

# --- C. 자산 내역 요약 (원그래프 제외, 상세 내역 복구) ---
st.markdown("<div class='section-header'>📋 전체 자산 구성 내역 상세</div>", unsafe_allow_html=True)
if full_details:
    summary_df = pd.DataFrame([{
        "종목명": i['row']['종목명'],
        "보유수량": f"{i['row']['주식수']}",
        "평단가": f"{i['row']['평균매수가']:,.0f}원",
        "현재가": f"{i['curr']:,.0f}원",
        "평가금액": f"{i['val_amt']:,.0f}원",
        "수익률": f"{i['p_rate']:.2f}%",
        "섹션": i['group']
    } for i in full_details])
    
    # 예수금 행 추가
    cash_row = pd.DataFrame([{"종목명": "현금(예수금)", "보유수량": "-", "평단가": "-", "현재가": "-", "평가금액": f"{curr_cash:,.0f}원", "수익률": "-", "섹션": "공통"}])
    summary_df = pd.concat([summary_df, cash_row], ignore_index=True)
    
    st.table(summary_df)

# --- D. 현금 관리 ---
st.divider()
st.subheader("💵 예수금 관리")
c_c1, _ = st.columns([1, 3])
with c_c1:
    nc = st.number_input("현재 보유 예수금(원)", value=curr_cash, step=10000.0)
    if st.button("현금 잔액 업데이트"):
        with open(CASH_FILE, "w") as f: f.write(str(nc))
        st.rerun()
