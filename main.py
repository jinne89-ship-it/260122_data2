import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import os

st.markdown(
    """
    <style>
    .card {
        padding: 1.2rem;
        border-radius: 10px;
        background-color: #ffffff;
        border: 1px solid #e6e6e6;
        margin-bottom: 1.2rem;
    }
    .card-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# 0. 페이지 설정(선택)
# ---------------------------
st.set_page_config(page_title="전국 대학 등록금 현황 분석 대시보드", layout="wide")

st.sidebar.markdown(
    """
    <style>
    .stSidebar p, .stSidebar div {
        font-size: 0.95rem;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# 1. 데이터 로드
# ---------------------------
@st.cache_data
def load_data(path: str):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
    raise last_err

df = load_data("tuitionfee.csv")

st.title("🎓 전국 대학 평균 등록금 대시보드")

# ---------------------------
# 2. 사이드바 필터
# ---------------------------
st.sidebar.header("조회조건")

year = st.sidebar.selectbox(
    "기준연도", sorted(df["기준연도"].dropna().unique())
)

region = st.sidebar.multiselect(
    "시도명", sorted(df["시도명"].dropna().unique())
)

found_type = st.sidebar.multiselect(
    "설립형태", sorted(df["설립형태구분명"].dropna().unique())
)

filtered = df[df["기준연도"] == year].copy()

if region:
    filtered = filtered[filtered["시도명"].isin(region)]

if found_type:
    filtered = filtered[filtered["설립형태구분명"].isin(found_type)]

# 숫자형 안전 변환
for col in ["평균입학금액", "평균등록금액"]:
    if col in filtered.columns:
        filtered[col] = pd.to_numeric(filtered[col], errors="coerce")

# 등록금액 = 0 인 경우 제외
before_n = len(filtered)
filtered = filtered.dropna(subset=["평균등록금액"])
filtered = filtered[filtered["평균등록금액"] > 0]
after_n = len(filtered)

st.sidebar.caption(f"※ 등록금 0원/결측 데이터 {before_n - after_n}건 제외됨")

# ---------------------------
# 2-1. 우리대학 선택 (비교 기준)
# ---------------------------
st.sidebar.subheader("🏫 우리대학 선택 (비교 기준)")

univ_options = (
    sorted(filtered["대학교명"].dropna().unique())
    if "대학교명" in filtered.columns
    else []
)

my_univ = st.sidebar.selectbox(
    "우리대학을 선택하세요",
    options=["(선택 안 함)"] + univ_options,
    index=0,
    help="선택한 대학을 기준으로 전국/지역/설립형태 내 등록금 위치를 분석합니다."
)

# ---------------------------
# 3. KPI 영역
# ---------------------------
st.subheader("📌 요약 지표")


col1, col2, col3, col4 = st.columns(4)

#univ_count = int(filtered["대학교명"].nunique()) if "대학교명" in filtered.columns else len(filtered)

#avg_tuition = filtered["평균등록금액"].mean() if "평균등록금액" in filtered.columns else float("nan")
#max_tuition = filtered["평균등록금액"].max() if "평균등록금액" in filtered.columns else float("nan")
#min_tuition = filtered["평균등록금액"].min() if "평균등록금액" in filtered.columns else float("nan")

#col1.metric("대학 수", univ_count)
#col2.metric("평균 등록금", "-" if pd.isna(avg_tuition) else f"{avg_tuition:,.0f} 원")
#col3.metric("최고 등록금", "-" if pd.isna(max_tuition) else f"{max_tuition:,.0f} 원")
#col4.metric("최저 등록금", "-" if pd.isna(min_tuition) else f"{min_tuition:,.0f} 원")


rank_base = (
    filtered.dropna(subset=["대학교명", "평균등록금액"])
    .groupby(["대학교명", "시도명", "설립형태구분명"], as_index=False)["평균등록금액"]
    .mean()
)
univ_count = int(rank_base["대학교명"].nunique()) if "대학교명" in rank_base.columns else len(rank_base)

avg_tuition = rank_base["평균등록금액"].mean() if "평균등록금액" in rank_base.columns else float("nan")
max_tuition = rank_base["평균등록금액"].max() if "평균등록금액" in rank_base.columns else float("nan")
min_tuition = rank_base["평균등록금액"].min() if "평균등록금액" in rank_base.columns else float("nan")

st.markdown('<div class="card">', unsafe_allow_html=True)

col1.metric("대학 수", univ_count)
col2.metric("평균 등록금(대학별 평균값 적용)", "-" if pd.isna(avg_tuition) else f"{avg_tuition:,.0f} 원")
col3.metric("최고 등록금(대학별 평균값 적용)", "-" if pd.isna(max_tuition) else f"{max_tuition:,.0f} 원")
col4.metric("최저 등록금(대학별 평균값 적용)", "-" if pd.isna(min_tuition) else f"{min_tuition:,.0f} 원")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# 3.5 우리대학 벤치마킹 패널
# ---------------------------
st.subheader("🏫 우리대학 벤치마킹")

if "my_univ" not in globals():
    st.info("왼쪽 사이드바에서 '우리대학(비교 기준)'을 먼저 선택해 주세요.")
elif my_univ == "(선택 안 함)":
    st.info("왼쪽 사이드바에서 '우리대학(비교 기준)'을 선택하면 전국/시도/설립형태 기준 순위와 격차를 보여드립니다.")
else:
    base = rank_base.dropna(subset=["대학교명", "평균등록금액"]).copy()
    base = base.sort_values("평균등록금액", ascending=False).reset_index(drop=True)
    n = len(base)

    if n < 2:
        st.warning("현재 조회조건에서 대학 수가 너무 적어 벤치마킹이 어렵습니다. 조회조건을 완화해 보세요.")
    elif my_univ not in set(base["대학교명"]):
        st.warning("현재 조회조건(연도/시도/설립형태)에서 선택한 대학이 조회되지 않습니다. 조회조건을 조정해 보세요.")
    else:
        base["전국순위"] = base["평균등록금액"].rank(ascending=False, method="min").astype(int)
        base["전국백분위(낮을수록 상위)"] = ((base["전국순위"] - 1) / (n - 1) * 100).round(1)

        row = base.loc[base["대학교명"] == my_univ].iloc[0]
        my_fee = float(row["평균등록금액"])
        my_region = row["시도명"]
        my_type = row["설립형태구분명"]

        # 전국 평균/중앙값
        nat_avg = float(base["평균등록금액"].mean())
        nat_med = float(base["평균등록금액"].median())

        # 시도 내 순위
        reg_base = base[base["시도명"] == my_region].copy()
        reg_n = len(reg_base)
        reg_base["시도순위"] = reg_base["평균등록금액"].rank(ascending=False, method="min").astype(int)
        reg_base["시도백분위(낮을수록 상위)"] = ((reg_base["시도순위"] - 1) / (reg_n - 1) * 100).round(1) if reg_n > 1 else 0.0
        reg_row = reg_base.loc[reg_base["대학교명"] == my_univ].iloc[0]
        reg_avg = float(reg_base["평균등록금액"].mean())

        # 설립형태 내 순위
        type_base = base[base["설립형태구분명"] == my_type].copy()
        type_n = len(type_base)
        type_base["유형순위"] = type_base["평균등록금액"].rank(ascending=False, method="min").astype(int)
        type_base["유형백분위(낮을수록 상위)"] = ((type_base["유형순위"] - 1) / (type_n - 1) * 100).round(1) if type_n > 1 else 0.0
        type_row = type_base.loc[type_base["대학교명"] == my_univ].iloc[0]
        type_avg = float(type_base["평균등록금액"].mean())

        # 격차(원/%) 계산
        def gap_str(x, ref):
            gap = x - ref
            pct = (gap / ref * 100) if ref != 0 else 0.0
            sign = "+" if gap >= 0 else ""
            return f"{sign}{gap:,.0f}원 ({sign}{pct:.1f}%)"

        # KPI 카드(8개 권장: 2줄)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("우리대학", my_univ)
        c2.metric("평균등록금(우리대학)", f"{my_fee:,.0f} 원")
        c3.metric("전국 순위/백분위", f"{int(row['전국순위'])} / {n}  ·  {float(row['전국백분위(낮을수록 상위)']):.1f}%")
        c4.metric("전국 평균 대비", gap_str(my_fee, nat_avg))

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("시도(지역)", f"{my_region} (n={reg_n})")
        d2.metric("시도 내 순위/백분위", f"{int(reg_row['시도순위'])} / {reg_n}  ·  {float(reg_row['시도백분위(낮을수록 상위)']):.1f}%")
        d3.metric("시도 평균 대비", gap_str(my_fee, reg_avg))
        d4.metric("설립형태 평균 대비", gap_str(my_fee, type_avg))

        # (선택) 핵심 비교 요약 한 줄
        st.caption(
            f"※ 전국 중앙값 {nat_med:,.0f}원 / {my_region} 평균 {reg_avg:,.0f}원 / {my_type} 평균 {type_avg:,.0f}원 (현재 조회조건 기준)"
        )
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# 4. 시각화 (Plotly)
# ---------------------------
st.subheader("📊 시도별 평균 등록금")

by_region = (
    filtered.groupby("시도명", dropna=False)["평균등록금액"]
    .mean()
    .reset_index()
    .dropna(subset=["시도명"])
    .sort_values("평균등록금액", ascending=False)
)

fig = px.bar(
    by_region,
    x="시도명",
    y="평균등록금액",
    labels={"시도명": "시도", "평균등록금액": "평균 등록금(원)"},
    title=f"{year}년 시도별 평균 등록금"
)
fig.update_layout(
    xaxis_tickangle=-45,
    yaxis_tickformat=",",
    height=520,
    margin=dict(l=20, r=20, t=60, b=40)
)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.subheader("📦 설립형태별 등록금 분포")

box_df = filtered.dropna(subset=["설립형태구분명", "평균등록금액"]).copy()

fig2 = px.box(
    box_df,
    x="설립형태구분명",
    y="평균등록금액",
    points="outliers",
    labels={"설립형태구분명": "설립형태", "평균등록금액": "평균 등록금(원)"},
    title=f"{year}년 설립형태별 등록금 분포"
)
fig2.update_layout(
    xaxis_tickangle=-20,
    yaxis_tickformat=",",
    height=520,
    margin=dict(l=20, r=20, t=60, b=40)
)
st.plotly_chart(fig2, use_container_width=True)

# ===========================
# 4.5 상·하위 10% 대학 탐색 + 선택 대학 순위/위치
# ===========================
st.subheader("🏁 상·하위 10% 대학 탐색 (평균등록금액 기준)")

rank_base = (
    filtered.dropna(subset=["대학교명", "평균등록금액"])
    .groupby(["대학교명", "시도명", "설립형태구분명"], as_index=False)["평균등록금액"]
    .mean()
)

n_univ = len(rank_base)

if n_univ < 5:
    st.info("현재 필터 결과의 대학 수가 너무 적어(5개 미만) 상·하위 10% 산출이 불안정합니다. 필터를 조금 완화해 보세요.")
else:
    rank_base = rank_base.sort_values("평균등록금액", ascending=False).reset_index(drop=True)
    rank_base["순위"] = rank_base["평균등록금액"].rank(ascending=False, method="min").astype(int)
    rank_base["백분위(낮을수록 상위)"] = ((rank_base["순위"] - 1) / (n_univ - 1) * 100).round(1)

    top_n = max(1, int(round(n_univ * 0.10)))
    bot_n = max(1, int(round(n_univ * 0.10)))

    top10 = rank_base.head(top_n).copy()
    bottom10 = rank_base.tail(bot_n).copy()

    def highlight_top_bottom(df_):
        styles = pd.DataFrame("", index=df_.index, columns=df_.columns)
        if "구분" in df_.columns:
            styles.loc[df_["구분"] == "상위10%", :] = "background-color: rgba(46, 204, 113, 0.18);"
            styles.loc[df_["구분"] == "하위10%", :] = "background-color: rgba(231, 76, 60, 0.18);"
        if "평균등록금액" in df_.columns:
            styles["평균등록금액"] += "font-weight: 700;"
        if "순위" in df_.columns:
            styles["순위"] += "font-weight: 700;"
        return styles

    top10_disp = top10[["순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].copy()
    top10_disp["구분"] = "상위10%"

    bottom10_disp = bottom10[["순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].copy()
    bottom10_disp["구분"] = "하위10%"

    cols_order = ["구분", "순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]
    top10_disp = top10_disp[cols_order].sort_values("순위", ascending=True)
    bottom10_disp = bottom10_disp[cols_order].sort_values("순위", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**상위 10% (총 {top_n}개 / 전체 {n_univ}개)**")
        st.dataframe(
            top10_disp.style.apply(highlight_top_bottom, axis=None).format(
                {"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}
            ),
            use_container_width=True
        )
    with c2:
        st.markdown(f"**하위 10% (총 {bot_n}개 / 전체 {n_univ}개)**")
        st.dataframe(
            bottom10_disp.style.apply(highlight_top_bottom, axis=None).format(
                {"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}
            ),
            use_container_width=True
        )

    st.divider()

    st.subheader("🎯 선택 대학의 순위·위치 확인")

    selected_univ = st.selectbox(
        "대학교 선택 (현재 필터 결과 기준)",
        options=sorted(rank_base["대학교명"].unique())
    )

    row = rank_base[rank_base["대학교명"] == selected_univ].iloc[0]
    sel_rank = int(row["순위"])
    sel_fee = float(row["평균등록금액"])
    sel_pct = float(row["백분위(낮을수록 상위)"])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("선택 대학", selected_univ)
    k2.metric("평균등록금액", f"{sel_fee:,.0f} 원")
    k3.metric("순위(높을수록 상위)", f"{sel_rank} / {n_univ}")
    k4.metric("백분위(낮을수록 상위)", f"{sel_pct:.1f}%")

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sel_pct,
        number={"suffix": "%"},
        title={"text": "선택 대학 위치 (백분위: 낮을수록 상위)"},
        gauge={"axis": {"range": [0, 100]}}
    ))
    gauge.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(gauge, use_container_width=True)

    st.markdown("**선택 대학 주변 순위(±5) 스냅샷**")
    window = 5
    start_rank = max(1, sel_rank - window)
    end_rank = min(n_univ, sel_rank + window)

    around = rank_base[(rank_base["순위"] >= start_rank) & (rank_base["순위"] <= end_rank)].copy()
    around["선택"] = around["대학교명"].apply(lambda x: "◀" if x == selected_univ else "")
    around_disp = around[["선택", "순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].sort_values("순위")

    def highlight_selected(df_):
        styles = pd.DataFrame("", index=df_.index, columns=df_.columns)
        if "선택" in df_.columns:
            styles.loc[df_["선택"] == "◀", :] = "background-color: rgba(52, 152, 219, 0.15); font-weight: 700;"
        return styles

    st.dataframe(
        around_disp.style.apply(highlight_selected, axis=None).format(
            {"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}
        ),
        use_container_width=True
    )

# ---------------------------
# 5. 데이터 테이블
# ---------------------------
st.subheader("📋 대학별 상세 데이터")
st.caption("※ 컬럼명 클릭 시 정렬 기준을 변경할 수 있습니다.")
sort_col = st.selectbox(
    "정렬 기준",
    ["시도명", "대학교명", "평균등록금액"]
)

show_cols = ["대학교명", "시도명", "설립형태구분명", "평균입학금액", "평균등록금액"]
exist_cols = [c for c in show_cols if c in filtered.columns]
st.dataframe(
    filtered[exist_cols]
        .sort_values(by=[sort_col, "대학교명"])
        .reset_index(drop=True)
        .assign(No=lambda x: x.index + 1)
        .loc[:, ["No"] + exist_cols]
        .style.format({
            "평균입학금액": "{:,.0f}",
            "평균등록금액": "{:,.0f}",
        }),
    use_container_width=True
)

# ---------------------------
# 6. 다운로드
# ---------------------------
st.download_button(
    "📥 CSV 다운로드",
    data=filtered.to_csv(index=False, encoding="utf-8-sig"),
    file_name="filtered_tuition_data.csv",
    mime="text/csv"
)

# =========================================================
# 7. (추가) 사이드바 하단: 등록금 분석 챗봇(OpenAI)
#    - 대학(행정부서) 분석용 / 버튼 1회 클릭 즉시 응답
# =========================================================
st.sidebar.divider()
st.sidebar.subheader("💬 등록금 분석 챗봇")

# ---------- OpenAI client ----------
def get_openai_client():
    api_key = None
    if hasattr(st, "secrets"):
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

client = get_openai_client()


# ---------- session state init ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "안녕하세요. 현재 조회조건 기준으로 등록금 데이터를 요약·비교·해석해 드립니다. (예: 우리대학 위치, 지역 내 비교, 국공립/사립 격차)"}
    ]

if "chat_input_box" not in st.session_state:
    st.session_state.chat_input_box = ""

if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

# ---------- context for the bot ----------
filter_summary = {
    "기준연도": year,
    "시도명": region if region else "전체",
    "설립형태": found_type if found_type else "전체",
}

filtered_stats = {
    "대학수(대학단위)": int(univ_count) if "univ_count" in globals() else None,
    "평균등록금(대학단위)": None if pd.isna(avg_tuition) else float(avg_tuition),
    "최고등록금(대학단위)": None if pd.isna(max_tuition) else float(max_tuition),
    "최저등록금(대학단위)": None if pd.isna(min_tuition) else float(min_tuition),
}

# ---------- recent chat render ----------
st.sidebar.caption("최근 대화")
for msg in st.session_state.chat_history[-8:]:
    if msg["role"] == "user":
        st.sidebar.markdown(f"**🙋‍사용자:** {msg['content']}")
    else:
        st.sidebar.markdown(f"**🤖분석챗봇:** {msg['content']}")

# ---------- input + send ----------
def queue_message_from_textbox():
    text = st.session_state.chat_input_box.strip()
    if text:
        st.session_state.pending_message = text

st.sidebar.text_input(
    "질문 입력 (Enter로 전송)",
    key="chat_input_box",
    on_change=queue_message_from_textbox
)

if st.sidebar.button("전송", use_container_width=True):
    queue_message_from_textbox()

# ---------- controls: 기준 대학 선택 + 추천 질문 ----------
st.sidebar.divider()
st.sidebar.subheader("🏫 기준 대학 선택")

univ_options = sorted(filtered["대학교명"].dropna().unique()) if "대학교명" in filtered.columns else []
my_univ = st.sidebar.selectbox("우리대학(비교 기준)", options=["(선택 안 함)"] + univ_options)

# 컨텍스트에 포함(답변 품질 개선)
filter_summary["우리대학"] = my_univ

st.sidebar.caption("👇 자주 쓰는 분석 질문")
if my_univ == "(선택 안 함)":
    suggested_questions = [
        "현재 조회조건에서 등록금이 높은 대학/낮은 대학(Top/Bottom)을 요약해줘.",
        "현재 조회조건에서 시도별 평균 등록금 차이를 표/핵심 포인트로 정리해줘.",
        "현재 조회조건에서 국공립과 사립의 평균 등록금 격차(원/%)를 계산해줘.",
        "상·하위 10% 대학 분포를 근거로 해석 포인트(시사점) 3가지를 제시해줘.",
    ]
else:
    suggested_questions = [
        f"'{my_univ}'의 평균 등록금은 (현재 조회조건)에서 전체 대학 대비 순위/백분위를 알려줘.",
        f"'{my_univ}'이(가) 속한 시도 내에서 등록금 수준이 높은 편인지 낮은 편인지 비교해줘.",
        "현재 조회조건에서 국공립과 사립의 평균 등록금 격차(원/%)를 계산해줘.",
        "상·하위 10% 대학 분포를 근거로 해석 포인트(시사점) 3가지를 제시해줘.",
    ]

b1, b2 = st.sidebar.columns(2)
with b1:
    if st.button("① 기준대학 위치", key="q1", use_container_width=True):
        st.session_state.pending_message = suggested_questions[0]
        st.rerun()
with b2:
    if st.button("② 지역 내 비교", key="q2", use_container_width=True):
        st.session_state.pending_message = suggested_questions[1]
        st.rerun()

b3, b4 = st.sidebar.columns(2)
with b3:
    if st.button("③ 국공립 vs 사립", key="q3", use_container_width=True):
        st.session_state.pending_message = suggested_questions[2]
        st.rerun()
with b4:
    if st.button("④ 시사점", key="q4", use_container_width=True):
        st.session_state.pending_message = suggested_questions[3]
        st.rerun()

if st.sidebar.button("대화 초기화", use_container_width=True):
    st.session_state.chat_history = [
        {"role": "assistant", "content": "대화가 초기화되었습니다. 현재 조회조건 기준으로 등록금 분석 질문을 입력해 주세요."}
    ]
    st.session_state.pending_message = None
    st.rerun()

# ---------- send pending message ----------
if st.session_state.pending_message:
    user_text = st.session_state.pending_message
    st.session_state.pending_message = None  # 중복 전송 방지

    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if client is None:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Secrets(OPENAI_API_KEY) 또는 환경변수를 확인해 주세요."
        })
        st.rerun()
    else:
        system_prompt = f"""
너는 '대학 등록금 데이터' 분석을 지원하는 분석 어시스턴트다.
- 사용자의 조회조건(연도/시도/설립형태/우리대학)을 우선 반영해 설명한다.
- 가능한 경우 수치를 포함(평균/최고/최저/격차/백분위 등)하여 근거 중심으로 답한다.
- 데이터로 확정할 수 없는 내용은 추정하지 말고, 필요한 추가 데이터가 무엇인지 제안한다.
- 답변은 (1)결론 (2)근거 수치 (3)해석/시사점 (4)다음 분석 제안 순서로 간결하게 작성한다.

[현재 조회조건]
{filter_summary}

[현재 화면 요약 통계(대학단위)]
{filtered_stats}
"""

        with st.sidebar.spinner("분석 중입니다... 잠시만 기다려 주세요 🙂"):
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *st.session_state.chat_history[-10:],
                    ],
                    temperature=0.3,
                )
                answer = resp.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.session_state.chat_history.append({"role": "assistant", "content": f"오류가 발생했어요: {e}"})

        st.rerun()
