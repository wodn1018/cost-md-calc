import streamlit as st
import pandas as pd
import altair as alt

# -----------------------------------------------------------
# [1] 기본 설정 및 세션 초기화
# -----------------------------------------------------------
st.set_page_config(page_title="인건비 견적/수당 계산기", layout="wide")

if 'staff_list' not in st.session_state:
    st.session_state['staff_list'] = []

# -----------------------------------------------------------
# [2] 사이드바: 입력 패널
# -----------------------------------------------------------
with st.sidebar:
    st.header("🎛️ 견적 및 근무 설정")
    
    # 1. 비율 설정
    st.subheader("1. 공통 비율 설정")
    c1, c2 = st.columns(2)
    with c1:
        overhead_rate = st.number_input(
            "간접비율 (%)", 
            min_value=0.0, max_value=500.0, 
            value=50.0, step=0.5, format="%.1f",
            help="4대보험, 퇴직금, 운영비 등"
        )
    with c2:
        margin_rate = st.number_input(
            "목표 마진율 (%)", 
            min_value=0.0, max_value=500.0, 
            value=10.0, step=0.5, format="%.1f",
            help="회사가 가져갈 순이익"
        )
    
    st.markdown("---")
    
    # 2. 인력 및 근무 조건 추가
    st.subheader("2. 인력 및 근무시간 추가")
    
    with st.form("staff_form", clear_on_submit=True):
        st.caption("💰 연봉 및 인원")
        col1, col2 = st.columns(2)
        input_salary_str = col1.text_input("연봉 (원)", value="00,000,000")
        input_count = col2.number_input("인원 (명)", min_value=0, value=0)
        
        st.markdown("---")
        st.caption("📅 근무 일수 및 초과 시간 (월 기준)")
        
        # 평일/휴일 일수
        c3, c4 = st.columns(2)
        weekday_days = c3.number_input("평일 근무 (일)", 0, 31, 0)
        holiday_days = c4.number_input("휴일/주말 (일)", 0, 31, 0)
        
        # [추가됨] 초과근무 시간
        st.markdown("")
        overtime_hours = st.number_input(
            "⏰ 월 초과근무 시간 (Hour)", 
            min_value=0.0, max_value=100.0, value=0.0, step=1.0,
            help="평일 야근 등 연장근로 시간 합계 (1.5배 적용)"
        )

        submitted = st.form_submit_button("➕ 리스트에 추가", use_container_width=True)
        
        if submitted:
            try:
                clean_salary = input_salary_str.replace(",", "").strip()
                salary_int = int(clean_salary)
                
                if salary_int > 0:
                    group_id = len(st.session_state['staff_list']) + 1
                    st.session_state['staff_list'].append({
                        "id": f"Group {group_id}",
                        "연봉": salary_int,
                        "인원": input_count,
                        "평일일수": weekday_days,
                        "휴일일수": holiday_days,
                        "초과시간": overtime_hours
                    })
                    
                    msg = f"연봉 {salary_int:,}원 ({input_count}명) 추가됨"
                    st.success(msg)
                else:
                    st.error("연봉은 0보다 커야 합니다.")
            except ValueError:
                st.error("연봉에는 숫자와 콤마만 입력해주세요.")

    # 3. 입력 리스트 확인 및 초기화
    st.markdown("---")
    if len(st.session_state['staff_list']) > 0:
        st.subheader("📋 입력 내역 확인")
        temp_df = pd.DataFrame(st.session_state['staff_list'])
        
        st.dataframe(
            temp_df[["연봉", "인원", "평일일수", "휴일일수", "초과시간"]], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "연봉": st.column_config.NumberColumn(format="%d 원"),
                "인원": st.column_config.NumberColumn(format="%d 명"),
                "평일일수": st.column_config.NumberColumn(format="%d 일"),
                "휴일일수": st.column_config.NumberColumn(format="%d 일"),
                "초과시간": st.column_config.NumberColumn(format="%.1f 시간")
            }
        )
        
        if st.button("🗑️ 전체 초기화"):
            st.session_state['staff_list'] = []
            st.rerun()

# -----------------------------------------------------------
# [3] 계산 로직
# -----------------------------------------------------------

STANDARD_HOURS = 209
results = []

def get_billing_price(base_cost, overhead_pct, margin_pct):
    overhead_amt = base_cost * (overhead_pct / 100)
    cost_price = base_cost + overhead_amt
    margin_amt = cost_price * (margin_pct / 100)
    billing_price = cost_price + margin_amt
    return billing_price

for row in st.session_state['staff_list']:
    salary = row["연봉"]
    count = row["인원"]
    w_days = row["평일일수"]
    h_days = row["휴일일수"]
    ov_hours = row["초과시간"]
    
    # 1. 시급 계산
    monthly_salary = salary / 12
    hourly_wage = monthly_salary / STANDARD_HOURS 
    
    # 2. [평일 1일 비용] (8시간)
    daily_wage_normal = hourly_wage * 8
    daily_bill_normal = get_billing_price(daily_wage_normal, overhead_rate, margin_rate)
    
    # 3. [휴일 1일 비용] (8시간 * 1.5배)
    daily_wage_holiday = hourly_wage * 8 * 1.5
    daily_bill_holiday = get_billing_price(daily_wage_holiday, overhead_rate, margin_rate)
    
    # 4. [초과근무 시간당 비용] (1시간 * 1.5배)
    # 근로기준법상 연장근로는 통상임금의 50% 가산
    hourly_wage_overtime = hourly_wage * 1.5
    hourly_bill_overtime = get_billing_price(hourly_wage_overtime, overhead_rate, margin_rate)

    # --- 총액 계산 (인원수 반영) ---
    
    # A. 평일 총액
    total_weekday_amt = daily_bill_normal * w_days * count
    
    # B. 휴일 총액
    total_holiday_amt = daily_bill_holiday * h_days * count
    
    # C. 초과근무 총액 (시간 * 단가 * 인원)
    total_overtime_amt = hourly_bill_overtime * ov_hours * count
    
    # D. 월 합계
    total_monthly_sum = total_weekday_amt + total_holiday_amt + total_overtime_amt

    results.append({
        "연봉": salary,
        "인원": count,
        "평일근무": f"{w_days}일",
        "휴일근무": f"{h_days}일",
        "초과근무": f"{ov_hours}시간",
        "평일 총액": total_weekday_amt,
        "휴일 총액": total_holiday_amt,
        "초과 총액": total_overtime_amt, # [NEW]
        "월 합계": total_monthly_sum
    })

# -----------------------------------------------------------
# [4] 데이터프레임 처리
# -----------------------------------------------------------
df_result = pd.DataFrame(results)

if not df_result.empty:
    # 합계 행
    total_row = {
        "연봉": 0,
        "인원": df_result["인원"].sum(),
        "평일근무": "-",
        "휴일근무": "-",
        "초과근무": "-",
        "평일 총액": df_result["평일 총액"].sum(),
        "휴일 총액": df_result["휴일 총액"].sum(),
        "초과 총액": df_result["초과 총액"].sum(),
        "월 합계": df_result["월 합계"].sum()
    }
    
    df_display = pd.concat([df_result, pd.DataFrame([total_row])], ignore_index=True)
    
    last_idx = df_display.index[-1]
    df_display.at[last_idx, "연봉"] = 0 
    df_display.at[last_idx, "평일근무"] = "Total"

# -----------------------------------------------------------
# [5] 대시보드
# -----------------------------------------------------------
st.title("📊 인건비 산출 내역서 (초과근무 포함)")
st.markdown(f"""
**기준:** 월 209시간 | 간접비 {overhead_rate}% | 마진 {margin_rate}%  
**근로기준법:** 휴일 및 연장근로(초과) 시 **통상임금의 1.5배** 적용
""")

if not df_result.empty:
    
    sum_weekday = df_result["평일 총액"].sum()
    sum_holiday = df_result["휴일 총액"].sum()
    sum_overtime = df_result["초과 총액"].sum()
    sum_total = df_result["월 합계"].sum()

    # KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 평일 총액", f"{int(sum_weekday):,} 원")
    c2.metric("🚨 휴일 총액", f"+ {int(sum_holiday):,} 원", delta="특근")
    c3.metric("⏰ 초과 총액", f"+ {int(sum_overtime):,} 원", delta="연장", delta_color="inverse")
    c4.metric("💰 월 합계 (최종)", f"{int(sum_total):,} 원", delta="Total")

    st.divider()

    st.subheader("📋 상세 견적 테이블")
    
    # 포맷팅
    show_df = df_display.copy()
    cols_money = ["연봉", "평일 총액", "휴일 총액", "초과 총액", "월 합계"]
    
    for col in cols_money:
        show_df[col] = show_df[col].apply(lambda x: f"{int(x):,}")
    
    show_df.at[last_idx, "연봉"] = ""
    show_df["인원"] = show_df["인원"].apply(lambda x: f"{x}명")

    # 테이블 출력
    st.dataframe(
        show_df[["연봉", "인원", "평일근무", "휴일근무", "초과근무", "평일 총액", "휴일 총액", "초과 총액", "월 합계"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "평일근무": st.column_config.TextColumn("평일(일수)"),
            "휴일근무": st.column_config.TextColumn("휴일(일수)"),
            "초과근무": st.column_config.TextColumn("초과(시간)", help="입력한 월 연장근로 시간"),
            "평일 총액": st.column_config.TextColumn("평일 총액", help="평일근무 × 단가"),
            "휴일 총액": st.column_config.TextColumn("휴일 총액", help="휴일근무 × 1.5배 단가"),
            "초과 총액": st.column_config.TextColumn("초과 총액", help="초과시간 × 1.5배 시급"),
            "월 합계": st.column_config.TextColumn("월 합계", help="평일 + 휴일 + 초과 총합")
        }
    )
    
    # 차트
    st.divider()
    st.subheader("비용 구성 차트")
    chart_data = pd.DataFrame({
        '구분': ['평일 총액', '휴일 총액', '초과 총액'],
        '금액': [sum_weekday, sum_holiday, sum_overtime]
    })
    
    base = alt.Chart(chart_data).encode(theta=alt.Theta("금액", stack=True))
    pie = base.mark_arc(outerRadius=100, innerRadius=50).encode(
        color=alt.Color("구분", scale=alt.Scale(domain=['평일 총액', '휴일 총액', '초과 총액'], range=['#3776ab', '#d62728', '#ff7f0e'])), 
        order=alt.Order("금액", sort="descending"),
        tooltip=[alt.Tooltip("구분"), alt.Tooltip("금액", format=",")]
    )
    st.altair_chart(pie, use_container_width=True)

    # 엑셀 다운로드
    csv = df_display.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 엑셀 다운로드", csv, "견적서_최종_초과포함.csv", "text/csv")

else:
    st.info("👈 왼쪽 사이드바에서 데이터를 입력해주세요.")