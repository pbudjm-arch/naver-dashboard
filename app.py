from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
BRANDS = ["유니클로", "스파오", "탑텐"]
TOPICS = ["제품 출시", "협업", "할인 혹은 행사", "실적 또는 사업", "기타"]
COLORS = {"유니클로": "#d62828", "스파오": "#277da1", "탑텐": "#43aa8b"}

st.set_page_config(page_title="패션 SPA 브랜드 경쟁 분석", page_icon="📊", layout="wide")


@st.cache_data
def load_data():
    news = pd.read_csv(DATA / "news_competitors_categorized_20261102.csv", encoding="utf-8-sig")
    keywords = pd.read_csv(DATA / "news_keyword_comparison_20261102.csv", encoding="utf-8-sig")
    monthly_path = max(DATA.glob("brand_search_trend_monthly_*.csv"), key=lambda p: p.name)
    age_path = max(DATA.glob("brand_search_trend_age_monthly_*.csv"), key=lambda p: p.name)
    monthly = pd.read_csv(monthly_path, encoding="utf-8-sig")
    ages = pd.read_csv(age_path, encoding="utf-8-sig")
    monthly["period"] = pd.to_datetime(monthly["period"])
    ages["period"] = pd.to_datetime(ages["period"])
    news["날짜 정렬"] = pd.to_datetime(news["날짜"], errors="coerce", utc=True).dt.tz_localize(None)
    return news, keywords, monthly, ages


def brand_articles(news: pd.DataFrame, brand: str) -> pd.DataFrame:
    return news[news["브랜드"].fillna("").map(lambda value: brand in str(value).split("·"))].copy()


def format_index(value) -> str:
    return "—" if pd.isna(value) else f"{float(value):.1f}"


news, keywords, monthly, ages = load_data()
period_start = monthly["period"].min().strftime("%Y.%m")
period_end = monthly["period"].max().strftime("%Y.%m")
latest_period = monthly["period"].max()

st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}
  [data-testid="stMetric"] {background: #f5f7fa; padding: 14px 18px; border-radius: 12px; border: 1px solid #e8edf2;}
  h1, h2, h3 {letter-spacing: -0.025em;}
</style>
""", unsafe_allow_html=True)

st.title("SPA 브랜드 경쟁 분석 대시보드")
st.caption(f"유니클로 · 스파오 · 탑텐 | 뉴스·주제·키워드·네이버 검색 관심도 | 검색 추이 {period_start}–{period_end}")

with st.sidebar:
    st.header("보기 설정")
    selected_brands = st.multiselect("브랜드", BRANDS, default=BRANDS)
    selected_topic = st.selectbox("뉴스 주제", ["전체 주제", *TOPICS])
    st.divider()
    st.caption("검색 지수는 네이버 통합검색의 상대 관심도입니다. 실제 검색 횟수나 시장 점유율은 아닙니다.")

if not selected_brands:
    st.info("왼쪽에서 비교할 브랜드를 하나 이상 선택하세요.")
    st.stop()

tabs = st.tabs(["한눈에 보기", "뉴스와 주제", "키워드", "검색 추이", "기사 목록"])

with tabs[0]:
    scoped_news = news[news["브랜드"].fillna("").map(lambda value: any(b in str(value).split("·") for b in selected_brands))]
    if selected_topic != "전체 주제":
        scoped_news = scoped_news[scoped_news["주제"] == selected_topic]
    current = monthly[(monthly["period"] == latest_period) & monthly["brand"].isin(selected_brands)]
    current_sorted = current.sort_values("ratio", ascending=False)
    leader = current_sorted.iloc[0] if not current_sorted.empty else None
    topic_counts = scoped_news["주제"].value_counts()
    top_topic = topic_counts.index[0] if not topic_counts.empty else "—"
    metric_cols = st.columns(4)
    metric_cols[0].metric("분석 뉴스", f"{len(scoped_news):,}건")
    metric_cols[1].metric("분석 브랜드", f"{len(selected_brands)}개")
    metric_cols[2].metric(f"{latest_period:%Y년 %m월} 검색 관심도 선두", leader["brand"] if leader is not None else "—")
    metric_cols[3].metric("뉴스 최다 주제", top_topic)

    left, right = st.columns([1.5, 1])
    with left:
        st.subheader("월별 검색 관심도")
        trend = monthly[monthly["brand"].isin(selected_brands)].pivot(index="period", columns="brand", values="ratio")
        st.line_chart(trend, color=[COLORS[b] for b in trend.columns], height=320)
        st.caption("세 브랜드를 한 요청에서 비교한 상대 지수입니다. 비교 범위 내 최고값을 100으로 환산했습니다.")
    with right:
        st.subheader("뉴스 주제 분포")
        counts = scoped_news.groupby(["주제", "브랜드"]).size().unstack(fill_value=0)
        counts = counts.reindex(index=TOPICS, columns=selected_brands, fill_value=0)
        st.bar_chart(counts, color=[COLORS[b] for b in counts.columns], height=320)
        st.caption("브랜드가 함께 언급된 기사는 해당 브랜드 각각에 포함됩니다.")

    st.subheader("최근 완료 월 비교")
    st.dataframe(current.sort_values("ratio", ascending=False)[["brand", "period", "ratio"]].rename(
        columns={"brand": "브랜드", "period": "월", "ratio": "상대 검색 지수"}),
        hide_index=True, use_container_width=True,
        column_config={"상대 검색 지수": st.column_config.NumberColumn(format="%.1f")})

with tabs[1]:
    st.subheader("브랜드별 뉴스 주제")
    rows = []
    for brand in selected_brands:
        subset = brand_articles(news, brand)
        for topic in TOPICS:
            rows.append({"브랜드": brand, "주제": topic, "기사 수": int((subset["주제"] == topic).sum())})
    topic_frame = pd.DataFrame(rows)
    topic_wide = topic_frame.pivot(index="주제", columns="브랜드", values="기사 수").reindex(TOPICS)
    st.bar_chart(topic_wide, color=[COLORS[b] for b in topic_wide.columns], height=360)
    st.dataframe(topic_wide.rename_axis("주제").reset_index(), hide_index=True, use_container_width=True)

    st.subheader("선택 주제의 기사")
    topic_news = news[news["브랜드"].fillna("").map(lambda value: any(b in str(value).split("·") for b in selected_brands))]
    if selected_topic != "전체 주제":
        topic_news = topic_news[topic_news["주제"] == selected_topic]
    topic_news = topic_news.sort_values("날짜 정렬", ascending=False)
    st.caption(f"현재 조건: {selected_topic} · {len(topic_news)}건")
    if not topic_news.empty:
        article_view = topic_news[["브랜드", "주제", "날짜", "제목", "요약", "원문 링크"]].copy()
        st.dataframe(article_view, hide_index=True, use_container_width=True, height=520,
                     column_config={"원문 링크": st.column_config.LinkColumn("원문", display_text="기사 열기")})
    else:
        st.info("현재 조건에 해당하는 기사가 없습니다.")

with tabs[2]:
    st.subheader("BoW와 TF-IDF 키워드 비교")
    key_brand = st.selectbox("키워드 브랜드", selected_brands, key="keyword_brand")
    key_topic = st.selectbox("키워드 주제", TOPICS, key="keyword_topic")
    keyword_group = keywords[(keywords["브랜드"] == key_brand) & (keywords["주제"] == key_topic)].copy()
    article_count = int(keyword_group["기사 수"].iloc[0]) if not keyword_group.empty else 0
    st.caption(f"{key_brand} · {key_topic} · 분석 기사 {article_count}건")
    if article_count == 0:
        st.info("이 브랜드와 주제 조합에는 분류된 기사가 없습니다.")
    else:
        bow_col, tfidf_col = st.columns(2)
        with bow_col:
            st.markdown("#### BoW · 자주 나온 단어")
            bow = keyword_group[["순위", "BoW 키워드", "BoW 빈도"]].dropna(subset=["BoW 키워드"])
            st.bar_chart(bow.set_index("BoW 키워드")["BoW 빈도"].astype(float).head(12), height=340, color="#277da1")
        with tfidf_col:
            st.markdown("#### TF-IDF · 상대적으로 특징적인 단어")
            tfidf = keyword_group[["순위", "TF-IDF 키워드", "TF-IDF 점수"]].dropna(subset=["TF-IDF 키워드"])
            st.bar_chart(tfidf.set_index("TF-IDF 키워드")["TF-IDF 점수"].astype(float).head(12), height=340, color="#43aa8b")
        detail_left, detail_right = st.columns(2)
        with detail_left:
            st.dataframe(bow, hide_index=True, use_container_width=True, height=330)
        with detail_right:
            st.dataframe(tfidf, hide_index=True, use_container_width=True, height=330)

    st.subheader("브랜드별 키워드 워드 클라우드")
    cloud_cols = st.columns(len(selected_brands))
    for col, brand in zip(cloud_cols, selected_brands):
        image_path = FIGURES / f"news_keyword_wordcloud_{brand}_20261102.png"
        with col:
            st.markdown(f"**{brand}**")
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)
            else:
                st.info("워드 클라우드 파일을 찾을 수 없습니다.")

with tabs[3]:
    st.subheader("월별 검색 관심도")
    trend = monthly[monthly["brand"].isin(selected_brands)].pivot(index="period", columns="brand", values="ratio")
    st.line_chart(trend, color=[COLORS[b] for b in trend.columns], height=400)
    st.caption("검색어 트렌드 API 지수입니다. 같은 요청 안의 브랜드 비교에 사용할 수 있으며, 실제 검색량·시장점유율을 뜻하지 않습니다.")

    age_labels = list(ages["segment"].drop_duplicates())
    age = st.selectbox("연령대", age_labels, index=3, key="age_segment")
    age_trend = ages[(ages["segment"] == age) & ages["brand"].isin(selected_brands)]
    age_wide = age_trend.pivot(index="period", columns="brand", values="ratio")
    st.subheader(f"{age} 검색 관심도 추이")
    st.line_chart(age_wide, color=[COLORS[b] for b in age_wide.columns], height=340)
    latest_age = age_trend[age_trend["period"] == latest_period].sort_values("ratio", ascending=False)
    st.markdown(f"**{latest_period:%Y년 %m월} {age} 브랜드 비교**")
    st.dataframe(latest_age[["brand", "ratio"]].rename(columns={"brand": "브랜드", "ratio": "상대 검색 지수"}),
                 hide_index=True, use_container_width=True,
                 column_config={"상대 검색 지수": st.column_config.NumberColumn(format="%.1f")})
    st.caption("각 연령대는 별도 요청으로 지수를 계산했습니다. 같은 연령대 안에서 브랜드를 비교할 수 있지만, 연령대 간 지수 크기를 검색자 비중으로 해석하면 안 됩니다.")

with tabs[4]:
    st.subheader("수집·분류된 뉴스")
    article_data = news[news["브랜드"].fillna("").map(lambda value: any(b in str(value).split("·") for b in selected_brands))]
    if selected_topic != "전체 주제":
        article_data = article_data[article_data["주제"] == selected_topic]
    article_data = article_data.sort_values("날짜 정렬", ascending=False)
    st.caption(f"{len(article_data)}건 · 주제와 브랜드는 왼쪽 보기 설정을 따릅니다.")
    view = article_data[["브랜드", "주제", "날짜", "제목", "요약", "원문 링크"]]
    st.dataframe(view, hide_index=True, use_container_width=True, height=680,
                 column_config={"원문 링크": st.column_config.LinkColumn("원문", display_text="기사 열기")})

st.divider()
st.caption("자료: NAVER API HUB 뉴스 검색·검색어 트렌드, 프로젝트의 뉴스 분류 및 BoW/TF-IDF 분석 자료")
