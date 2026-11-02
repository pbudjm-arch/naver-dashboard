"""Add a single primary topic and a brand/topic count table to news data."""

from collections import Counter
from pathlib import Path
import csv
import html
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "news_competitors_analysis_20261101_193938.csv"
OUTPUT = ROOT / "data" / "processed" / "news_competitors_categorized_20261102.csv"
SUMMARY = ROOT / "data" / "processed" / "news_competitors_category_summary_20261102.csv"
BRANDS = ["유니클로", "스파오", "탑텐"]
CATEGORIES = ["제품 출시", "협업", "할인 혹은 행사", "실적 또는 사업", "기타"]


def matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def classify(row: dict) -> tuple[str, str]:
    title = html.unescape(row["제목"] or "")
    summary = html.unescape(row["요약"] or "")
    text = f"{title} {summary}"

    # Choose the article's central subject, not every secondary mention.
    if matches(r"협업|콜라보|컬래버|제휴|파트너십|공동기획|공동개발|팬心전심", title):
        return "협업", "제목에서 브랜드 제휴·공동 기획을 중심 주제로 다룸"
    if "스파오" in row["브랜드"] and "먼작귀" in title and "굿즈 품절" in title:
        return "협업", "요약에서 스파오와 캐릭터 상품 협업을 확인"
    if matches(r"할인|세일|텐텐데이|쇼핑축제|팝업|행사|오픈런|기획전|프로모션|이벤트", title):
        return "할인 혹은 행사", "제목에서 할인·행사·팝업을 중심 주제로 다룸"
    if matches(r"출시|선보|내놓|발매|신제품|신상품|신제품군|4종 확대|신규 라인", title):
        return "제품 출시", "제목에서 신제품·상품 공개 또는 출시를 다룸"
    if matches(r"에어테크 파카|에어테크.*화보|누구템", title):
        return "제품 출시", "제목에서 특정 제품·상품을 소개"
    if "유니클로" in row["브랜드"] and "엄마 패션" in title and "출시" in summary:
        return "제품 출시", "요약에서 유니클로 신상품 출시를 확인"

    if matches(r"느린학습자|재해보험|수해 시름|희망브리지|사회공헌|교육지원", text):
        return "기타", "사회공헌·지원 활동을 다룸"
    if matches(r"오타니 영입 효과|슈퍼리치들의 아우터|런드리고.*세탁|세탁.*트렌드|야장|직관|뮤지엄|아카이브", title):
        return "기타", "라이프스타일·문화·세탁 이용 동향 등 다른 주제를 다룸"
    if matches(r"캐릭터 IP.*신성장동력", title) and matches(r"UTme|유니클로", summary):
        return "협업", "요약에서 유니클로의 캐릭터 공동 상품 활동을 확인"

    business_pattern = (
        r"매출|실적|성장|증가|사업|시장|경쟁|인수|확장|진출|매장|점포|상권|유통|플랫폼|"
        r"연봉|월급|대표|회장|기업|전략|수요|판매|가격|양말값|백기|공략|리뉴얼|"
        r"쇼핑|브랜드|고객|투자|신용등급|본격화|전환|산업|업계|대전|흥행|인기|트렌드|"
        r"패션|패딩|아우터|경량|의류|패밀리룩|키즈|외투|소비|쇼핑몰|스토어|직영점|할인|매장|AI|서비스 도입|솔루션"
    )
    if matches(business_pattern, title):
        return "실적 또는 사업", "시장·매출·운영·소비 동향 또는 기업 활동을 다룸"

    # Corporate/community programs and unrelated lifestyle coverage are retained as Other.
    if matches(r"사회공헌|교육지원|재해보험|느린학습자|수해|야장|직관|뮤지엄|아카이브", text):
        return "기타", "사회공헌·문화·라이프스타일 등 다른 주제를 다룸"
    return "기타", "지정된 네 가지 핵심 주제 외의 내용"


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig")))
    brand_counts = {brand: Counter() for brand in BRANDS}
    fields = ["브랜드", "주제", "제목", "요약", "날짜", "원문 링크", "분류 근거"]
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            category, reason = classify(row)
            for brand in row["브랜드"].split("·"):
                if brand in brand_counts:
                    brand_counts[brand][category] += 1
            writer.writerow({
                "브랜드": row["브랜드"],
                "주제": category,
                "제목": row["제목"],
                "요약": row["요약"],
                "날짜": row["날짜"],
                "원문 링크": row["원문 링크"],
                "분류 근거": reason,
            })

    with SUMMARY.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["브랜드", *CATEGORIES, "합계"])
        writer.writeheader()
        for brand in BRANDS:
            counts = brand_counts[brand]
            writer.writerow({"브랜드": brand, **{c: counts[c] for c in CATEGORIES}, "합계": sum(counts.values())})

    print(f"classified_articles={len(rows)}")
    print(f"detail={OUTPUT.relative_to(ROOT)}")
    print(f"summary={SUMMARY.relative_to(ROOT)}")
    for brand in BRANDS:
        print(brand, dict(brand_counts[brand]), "total", sum(brand_counts[brand].values()))


if __name__ == "__main__":
    main()
