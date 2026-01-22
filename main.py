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

# ===========================
# 4.5 상·하위 10% 대학 탐색 + 선택 대학 순위/위치
# ===========================
st.subheader("🏁 상·하위 10% 대학 탐색 (평균등록금액 기준)")

# 분석용 데이터 준비: 대학별 1행으로 정리(중복 대비)
rank_base = (
    filtered.dropna(subset=["대학교명", "평균등록금액"])
    .groupby(["대학교명", "시도명", "설립형태구분명"], as_index=False)["평균등록금액"]
    .mean()
)

# 대학 수가 너무 적으면(예: 필터가 과도) 순위 계산이 의미 없을 수 있음
n_univ = len(rank_base)

if n_univ < 5:
    st.info("현재 필터 결과의 대학 수가 너무 적어(5개 미만) 상·하위 10% 산출이 불안정합니다. 필터를 조금 완화해 보세요.")
else:
    # 순위(높을수록 1위) 및 백분위(0~100) 계산
    rank_base = rank_base.sort_values("평균등록금액", ascending=False).reset_index(drop=True)
    rank_base["순위"] = rank_base["평균등록금액"].rank(ascending=False, method="min").astype(int)

    # 백분위: 상위일수록 0%에 가깝게(= 상위권), 하위일수록 100%에 가깝게
    # 예: 1위 -> 0% / 꼴찌 -> 100%에 가깝게
    rank_base["백분위(낮을수록 상위)"] = ((rank_base["순위"] - 1) / (n_univ - 1) * 100).round(1)

    # 상·하위 10% 커트
    top_n = max(1, int(round(n_univ * 0.10)))
    bot_n = max(1, int(round(n_univ * 0.10)))

    top10 = rank_base.head(top_n).copy()
    bottom10 = rank_base.tail(bot_n).copy()

    # ----- 강조 스타일(표) -----
    def highlight_top_bottom(df):
        # top 테이블은 녹색, bottom 테이블은 빨강 계열
        # (Streamlit 테마에 따라 약간 다르게 보일 수 있음)
        styles = pd.DataFrame("", index=df.index, columns=df.columns)

        if "구분" in df.columns:
            styles.loc[df["구분"] == "상위10%", :] = "background-color: rgba(46, 204, 113, 0.18);"
            styles.loc[df["구분"] == "하위10%", :] = "background-color: rgba(231, 76, 60, 0.18);"

        # 등록금 컬럼만 조금 더 강조
        if "평균등록금액" in df.columns:
            styles["평균등록금액"] += "font-weight: 700;"
        if "순위" in df.columns:
            styles["순위"] += "font-weight: 700;"
        return styles

    # 보기 좋은 컬럼 구성
    top10_disp = top10[["순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].copy()
    top10_disp["구분"] = "상위10%"

    bottom10_disp = bottom10[["순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].copy()
    bottom10_disp["구분"] = "하위10%"

    # 표시 순서 정리
    cols_order = ["구분", "순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]
    top10_disp = top10_disp[cols_order].sort_values("순위", ascending=True)
    bottom10_disp = bottom10_disp[cols_order].sort_values("순위", ascending=False)

    # ----- UI: 상/하위 테이블 -----
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"**상위 10% (총 {top_n}개 / 전체 {n_univ}개)**")
        st.dataframe(
            top10_disp.style.apply(highlight_top_bottom, axis=None).format({"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}),
            use_container_width=True
        )

    with c2:
        st.markdown(f"**하위 10% (총 {bot_n}개 / 전체 {n_univ}개)**")
        st.dataframe(
            bottom10_disp.style.apply(highlight_top_bottom, axis=None).format({"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}),
            use_container_width=True
        )

    st.divider()

    # ===========================
    # 선택 대학의 순위/위치 표시
    # ===========================
    st.subheader("🎯 선택 대학의 순위·위치 확인")

    selected_univ = st.selectbox(
        "대학교 선택 (현재 필터 결과 기준)",
        options=sorted(rank_base["대학교명"].unique())
    )

    row = rank_base[rank_base["대학교명"] == selected_univ].iloc[0]
    sel_rank = int(row["순위"])
    sel_fee = float(row["평균등록금액"])
    sel_pct = float(row["백분위(낮을수록 상위)"])

    # KPI로 요약
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("선택 대학", selected_univ)
    k2.metric("평균등록금액", f"{sel_fee:,.0f} 원")
    k3.metric("순위(높을수록 상위)", f"{sel_rank} / {n_univ}")
    k4.metric("백분위(낮을수록 상위)", f"{sel_pct:.1f}%")

    # 간단한 위치 게이지(Plotly)
    # 상위일수록 왼쪽(0)에 가깝게 보여주고 싶으면 값 자체는 sel_pct (0~100)
    import plotly.graph_objects as go

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sel_pct,
        number={"suffix": "%"},
        title={"text": "선택 대학 위치 (백분위: 낮을수록 상위)"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "rgba(52, 152, 219, 0.9)"},
            "steps": [
                {"range": [0, 10], "color": "rgba(46, 204, 113, 0.18)"},
                {"range": [10, 50], "color": "rgba(241, 196, 15, 0.12)"},
                {"range": [50, 100], "color": "rgba(231, 76, 60, 0.10)"},
            ],
            "threshold": {
                "line": {"color": "rgba(44, 62, 80, 0.9)", "width": 3},
                "thickness": 0.75,
                "value": sel_pct
            }
        }
    ))
    gauge.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(gauge, use_container_width=True)

    # 선택 대학 주변(±5) 순위 스냅샷
    st.markdown("**선택 대학 주변 순위(±5) 스냅샷**")
    window = 5
    start_rank = max(1, sel_rank - window)
    end_rank = min(n_univ, sel_rank + window)

    around = rank_base[(rank_base["순위"] >= start_rank) & (rank_base["순위"] <= end_rank)].copy()
    around["선택"] = around["대학교명"].apply(lambda x: "◀" if x == selected_univ else "")
    around_disp = around[["선택", "순위", "대학교명", "시도명", "설립형태구분명", "평균등록금액", "백분위(낮을수록 상위)"]].sort_values("순위")

    def highlight_selected(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        if "선택" in df.columns:
            styles.loc[df["선택"] == "◀", :] = "background-color: rgba(52, 152, 219, 0.15); font-weight: 700;"
        return styles

    st.dataframe(
        around_disp.style.apply(highlight_selected, axis=None).format({"평균등록금액": "{:,.0f}", "백분위(낮을수록 상위)": "{:.1f}"}),
        use_container_width=True
    )


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
