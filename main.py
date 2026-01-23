import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import os

# ---------------------------
# 0. 페이지 설정(선택)
# ---------------------------
st.set_page_config(page_title="전국 대학 평균 등록금 대시보드", layout="wide")

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
st.sidebar.header("필터")

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

# ---------------------------
# 3. KPI 영역
# ---------------------------
st.subheader("📌 요약 지표")

col1, col2, col3, col4 = st.columns(4)

univ_count = int(filtered["대학교명"].nunique()) if "대학교명" in filtered.columns else len(filtered)

avg_tuition = filtered["평균등록금액"].mean() if "평균등록금액" in filtered.columns else float("nan")
max_tuition = filtered["평균등록금액"].max() if "평균등록금액" in filtered.columns else float("nan")
min_tuition = filtered["평균등록금액"].min() if "평균등록금액" in filtered.columns else float("nan")

col1.metric("대학 수", univ_count)
col2.metric("평균 등록금", "-" if pd.isna(avg_tuition) else f"{avg_tuition:,.0f} 원")
col3.metric("최고 등록금", "-" if pd.isna(max_tuition) else f"{max_tuition:,.0f} 원")
col4.metric("최저 등록금", "-" if pd.isna(min_tuition) else f"{min_tuition:,.0f} 원")

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
st.plotly_chart(fig, use_container_width=True)

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

show_cols = ["대학교명", "시도명", "설립형태구분명", "평균입학금액", "평균등록금액"]
exist_cols = [c for c in show_cols if c in filtered.columns]
st.dataframe(filtered[exist_cols], use_container_width=True)

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
# 7. (추가) 사이드바 하단: 고등학생 상담 챗봇(OpenAI) - 완전 안정 버전
# =========================================================
st.sidebar.divider()
st.sidebar.subheader("💬 등록금 상담 챗봇 (고등학생용)")

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

# 대화 기록
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "안녕하세요! 원하는 지역/설립형태/대학구분을 말해주면 등록금 데이터를 바탕으로 비교를 도와줄게요 😊"}
    ]

# 위젯 입력값(절대 코드에서 직접 수정하지 않음)
if "chat_input_box" not in st.session_state:
    st.session_state.chat_input_box = ""

# 전송 대기 메시지(이 값만 코드에서 컨트롤)
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

# 현재 화면 필터/통계(챗봇 컨텍스트)
filter_summary = {
    "기준연도": year,
    "시도명": region if region else "전체",
    "설립형태": found_type if found_type else "전체",
}
filtered_stats = {
    "대학수": univ_count,
    "평균등록금": None if pd.isna(avg_tuition) else float(avg_tuition),
    "최고등록금": None if pd.isna(max_tuition) else float(max_tuition),
    "최저등록금": None if pd.isna(min_tuition) else float(min_tuition),
}

# 최근 대화 표시
for msg in st.session_state.chat_history[-8:]:
    if msg["role"] == "user":
        st.sidebar.markdown(f"**🙋‍학생:** {msg['content']}")
    else:
        st.sidebar.markdown(f"**🤖상담:** {msg['content']}")

def queue_message():
    """입력창 내용을 pending_message로 '복사'만 한다. (위젯 key는 수정 금지)"""
    text = st.session_state.chat_input_box.strip()
    if text:
        st.session_state.pending_message = text

# Enter로 전송: on_change에서 queue만 수행
st.sidebar.text_input(
    "질문을 입력하세요 (Enter로 전송)",
    key="chat_input_box",
    on_change=queue_message
)

# 버튼 전송도 제공(클릭 시에도 queue)
if st.sidebar.button("전송", use_container_width=True):
    queue_message()

# 실제 전송 처리(위젯 이후 실행)
if st.session_state.pending_message:
    user_text = st.session_state.pending_message
    st.session_state.pending_message = None  # 먼저 비워서 중복 전송 방지

    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if client is None:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "API 키가 설정되지 않았어요. Streamlit Secrets(OPENAI_API_KEY) 또는 환경변수를 설정해 주세요."
        })
    else:
        system_prompt = f"""
너는 고등학생을 위한 대학 등록금 상담 챗봇이야.
- 친절하고 쉬운 한국어로 답해.
- 이 앱은 '전국 대학 평균 등록금 공공데이터'를 기반으로 한다.
- 현재 화면의 필터/통계를 참고해서 설명해.
- 특정 대학 합격을 보장하거나 과도한 단정/비방을 하지 마.
- 개인정보(전화번호, 주민번호 등)를 요구하지 마.
- 가능한 경우 선택지를 2~3개로 정리해주고, 다음 질문을 제안해.

[현재 필터]
{filter_summary}

[현재 필터 결과 요약 통계]
{filtered_stats}
"""
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *st.session_state.chat_history[-10:],
                ],
                temperature=0.5,
            )
            answer = resp.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"오류가 발생했어요: {e}"})

    # ✅ 입력창을 비우고 싶다면? -> 위젯 key를 건드리면 안 됨.
    # 대신 rerun으로 새 run에서 초기화되도록, '입력창 key'에 default를 주는 구조로 바꿔야 함.
    # 여기서는 안전하게 rerun만 수행.
    st.rerun()

