import streamlit as st
import pandas as pd
import plotly.express as px

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

# 숫자형 안전 변환 (가끔 문자열로 들어올 수 있어서 방어)
for col in ["평균입학금액", "평균등록금액"]:
    filtered[col] = pd.to_numeric(filtered[col], errors="coerce")

# ---------------------------
# 3. KPI 영역
# ---------------------------
st.subheader("📌 요약 지표")

col1, col2, col3, col4 = st.columns(4)

col1.metric("대학 수", int(filtered["대학교명"].nunique()) if "대학교명" in filtered.columns else len(filtered))

avg_tuition = filtered["평균등록금액"].mean()
max_tuition = filtered["평균등록금액"].max()
min_tuition = filtered["평균등록금액"].min()

col2.metric("평균 등록금", "-" if pd.isna(avg_tuition) else f"{avg_tuition:,.0f} 원")
col3.metric("최고 등록금", "-" if pd.isna(max_tuition) else f"{max_tuition:,.0f} 원")
col4.metric("최저 등록금", "-" if pd.isna(min_tuition) else f"{min_tuition:,.0f} 원")

# ---------------------------
# 4. 시각화 (Plotly)
# ---------------------------
st.subheader("📊 시도별 평균 등록금")

# 시도별 평균 집계
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

# (선택) 설립형태별 분포 박스플롯
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

# ---------------------------
# 5. 데이터 테이블
# ---------------------------
st.subheader("📋 대학별 상세 데이터")

show_cols = ["대학교명", "시도명", "설립형태구분명", "평균입학금액", "평균등록금액"]
exist_cols = [c for c in show_cols if c in filtered.columns]

st.dataframe(filtered[exist_cols])

# ---------------------------
# 6. 다운로드
# ---------------------------
st.download_button(
    "📥 CSV 다운로드",
    data=filtered.to_csv(index=False, encoding="utf-8-sig"),
    file_name="filtered_tuition_data.csv",
    mime="text/csv"
)
