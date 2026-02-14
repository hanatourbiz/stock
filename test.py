# --- B. 종목 추가/수정 ---
with st.container():
    title_text = "🔍 종목 정보 수정" if st.session_state.edit_index is not None else "➕ 신규 종목 추가"
    with st.expander(title_text, expanded=(st.session_state.edit_index is not None)):
        def_name, def_date, def_price, def_qty, def_target = "", date.today(), 0, 0, 15
        
        # 수정 모드일 때 기존 데이터 불러오기
        if st.session_state.edit_index is not None:
            edit_row = st.session_state.portfolio.loc[st.session_state.edit_index]
            def_name, def_date = edit_row['종목명'], pd.to_datetime(edit_row['기준일']).date()
            def_price, def_qty, def_target = int(edit_row['평균매수가']), int(edit_row['주식수']), int(edit_row['익절기준'])

        # 시장 구분을 위한 로직 (종목코드 접미사 기준)
        def get_market_type(name):
            if not name: return "KOSPI"
            code = stock_dict.get(name, "")
            if ".KQ" in code: return "KOSDAQ"
            if "KODEX" in name or "TIGER" in name or "RISE" in name: return "ETF" # 단순 예시
            return "KOSPI"

        # 레이아웃 구성 (기존 5열에서 시장구분 포함 6열로 변경하거나, 1열에 시장구분 배치)
        c0, c1, c2, c3, c4, c5 = st.columns([0.8, 1.5, 1.2, 1, 0.8, 0.8])
        
        with c0:
            market_choice = st.selectbox("시장", ["KOSPI", "KOSDAQ", "ETF"])
        
        with c1:
            # 선택한 시장에 해당하는 종목만 필터링
            if market_choice == "KOSPI":
                display_list = [n for n, c in stock_dict.items() if ".KS" in c and "KODEX" not in n and "TIGER" not in n]
            elif market_choice == "KOSDAQ":
                display_list = [n for n, c in stock_dict.items() if ".KQ" in c]
            else: # ETF
                display_list = [n for n, c in stock_dict.items() if "KODEX" in n or "TIGER" in n or "RISE" in n or "ACE" in n]
            
            display_list = sorted(display_list)
            add_name = st.selectbox("종목명", options=[""] + display_list, 
                                    index=(display_list.index(def_name)+1 if def_name in display_list else 0))
        
        with c2: add_date = st.date_input("기준일", value=def_date)
        with c3: add_price = st.number_input("평균매수가", min_value=0, value=def_price)
        with c4: add_qty = st.number_input("수량", min_value=0, value=def_qty)
        with c5: add_target = st.number_input("익절(%)", value=def_target)

        if st.button("저장", type="primary"):
            if add_name:
                code_val = stock_dict[add_name]
                new_row = {"종목명": add_name, "종목코드": code_val, "기준일": add_date.strftime('%Y-%m-%d'), "평균매수가": add_price, "주식수": add_qty, "익절기준": add_target}
                if st.session_state.edit_index is not None:
                    st.session_state.portfolio.loc[st.session_state.edit_index] = new_row
                    st.session_state.edit_index = None
                else:
                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.portfolio); st.rerun()
