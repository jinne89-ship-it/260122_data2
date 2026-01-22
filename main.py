import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ---------------------------
# 1. 데이터 로드
# ---------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("tuitionfee.csv")
    return df

df = load_data()

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

filtered = df[df["기준연도"] == year]

if region:
    filtered = filtered[filtered["시도명"].isin(region)]

if found_type:
    filtered = filtered[filtered["설립형태구분명"].isin(found_type)]

# ---------------------------
# 3. KPI 영역
# ---------------------------
st.subheader("📌 요약 지표")

col1, col2, col3, col4 = st.columns(4)

col1.metric("대학 수", len(filtered))
col2.metric("평균 등록금", f"{filtered['평균등록금액'].mean():,.0f} 원")
col3.metric("최고 등록금", f"{filtered['평균등록금액'].max():,.0f} 원")
col4.metric("최저 등록금", f"{filtered['평균등록금액'].min():,.0f} 원")

# ---------------------------
# 4. 시각화
# ---------------------------
st.subheader("📊 시도별 평균 등록금")

fig, ax = plt.subplots()
sns.barplot(
    data=filtered,
    x="시도명",
    y="평균등록금액",
    ax=ax
)
plt.xticks(rotation=45)
st.pyplot(fig)

# ---------------------------
# 5. 데이터 테이블
# ---------------------------
st.subheader("📋 대학별 상세 데이터")
st.dataframe(
    filtered[[
        "대학교명",
        "시도명",
        "설립형태구분명",
        "평균입학금액",
        "평균등록금액"
    ]]
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
