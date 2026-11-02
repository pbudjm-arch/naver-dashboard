"""Extract BoW and TF-IDF keywords and draw Korean word clouds."""

from collections import Counter, defaultdict
from pathlib import Path
import csv
import html
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "news_competitors_categorized_20261102.csv"
OUTPUT = ROOT / "data" / "processed" / "news_keyword_comparison_20261102.csv"
FIGURES = ROOT / "outputs" / "figures"
BRANDS = ["유니클로", "스파오", "탑텐"]
TOPICS = ["제품 출시", "협업", "할인 혹은 행사", "실적 또는 사업", "기타"]
FONT_PATH = Path(r"C:\Windows\Fonts\malgunbd.ttf")
PALETTE = ["#17324D", "#177E89", "#315C9B", "#8C4A69", "#A66B24", "#39735B", "#5D4B8A"]
STOPWORDS = {
    "유니클로", "스파오", "탑텐", "탑텐키즈", "브랜드", "패션", "업계", "업체", "기업", "국내", "해외",
    "사진", "자료", "뉴스", "기자", "출처", "기사", "보도", "이날", "현재", "최근", "지난", "올해", "내년",
    "지난해", "이번", "다음", "이후", "당시", "특히", "관련", "위해", "통해", "대한", "대해", "따르면", "가운데",
    "밝혔다", "전했다", "설명했다", "말했다", "있다", "없다", "됐다", "된다", "했다", "하는", "하며", "위한", "위해",
    "등", "수", "것", "곳", "점", "개", "명", "측", "중", "후", "전", "안", "밖", "말", "간", "조", "억",
    "경우", "부문", "분야", "부분", "기준", "정도", "수준", "모두", "각각", "먼저", "함께", "또한", "다만", "오히려",
    "이처럼", "이같은", "그러나", "때문", "무엇", "모습", "방식", "가장", "더욱", "그동안", "것으로", "등으로",
    "사회", "관계자", "관계자들", "시장", "소비자", "고객", "상품", "제품", "매장", "의류", "의상",
}
PARTICLES = [
    "으로부터", "에게서는", "으로서는", "에서부터", "으로부터", "에게까지", "들에서는", "들에게는", "으로서는",
    "으로부터", "에서는", "으로는", "에게는", "에서", "에게", "으로", "부터", "까지", "처럼", "보다", "에도",
    "만큼", "으로서", "이라며", "이라고", "이라서", "이며", "이고", "이자", "하는", "해서", "하여", "하며",
    "에서의", "으로의", "들의", "에는", "으로", "라며", "라고", "라는", "이라", "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "만", "로", "며", "고",
]


def tokenize(text: str) -> list[str]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    raw = re.findall(r"[가-힣]+|[A-Za-z]{2,}", text)
    tokens = []
    for word in raw:
        word = word.lower()
        if word in STOPWORDS or word.startswith("유니클"):
            continue
        changed = True
        while changed:
            changed = False
            for suffix in PARTICLES:
                if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                    word = word[:-len(suffix)]
                    changed = True
                    break
        if len(word) >= 2 and word not in STOPWORDS:
            tokens.append(word)
    return tokens


def best_positions(counter: Counter, idf: dict[str, float], docs: list[list[str]]) -> dict[str, list[tuple[str, float]]]:
    bow = Counter()
    tfidf = Counter()
    for doc in docs:
        counts = Counter(doc)
        bow.update(counts)
        denom = max(1, sum(counts.values()))
        for word, count in counts.items():
            tfidf[word] += (count / denom) * idf.get(word, 1.0)
    if docs:
        for word in list(tfidf):
            tfidf[word] /= len(docs)
    return {
        "BoW": bow.most_common(20),
        "TF-IDF": sorted(tfidf.items(), key=lambda pair: (-pair[1], pair[0]))[:20],
    }


def draw_cloud(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], pairs: list[tuple[str, float]], seed: int) -> None:
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    if not pairs:
        font = ImageFont.truetype(str(FONT_PATH), 22)
        draw.text((x0 + 20, y0 + 28), "분류된 기사 없음", font=font, fill="#52616F")
        return

    weights = np.array([max(float(value), 1e-12) for _, value in pairs], dtype=float)
    max_weight = float(weights.max())
    min_weight = float(weights.min())
    occupied = np.zeros((height, width), dtype=bool)
    golden = 2.399963229728653
    for index, (word, value) in enumerate(pairs):
        ratio = math.sqrt(max(float(value), 1e-12) / max_weight)
        if max_weight == min_weight:
            ratio = 0.8
        size = int(18 + 40 * ratio)
        font = ImageFont.truetype(str(FONT_PATH), size)
        bounds = draw.textbbox((0, 0), word, font=font)
        tw, th = max(1, bounds[2] - bounds[0]), max(1, bounds[3] - bounds[1])
        if tw > width - 8:
            size = max(14, int(size * (width - 8) / tw))
            font = ImageFont.truetype(str(FONT_PATH), size)
            bounds = draw.textbbox((0, 0), word, font=font)
            tw, th = max(1, bounds[2] - bounds[0]), max(1, bounds[3] - bounds[1])

        placed = False
        max_radius = int(math.hypot(width, height))
        for step in range(1600):
            radius = 2.8 * math.sqrt(step)
            angle = step * golden + seed * 0.31
            cx = width / 2 + radius * math.cos(angle)
            cy = height / 2 + radius * math.sin(angle)
            left, top = int(cx - tw / 2), int(cy - th / 2)
            right, bottom = left + tw, top + th
            if left < 2 or top < 2 or right >= width - 2 or bottom >= height - 2:
                if radius > max_radius:
                    break
                continue
            if occupied[top:bottom, left:right].any():
                continue
            occupied[top:bottom, left:right] = True
            color = PALETTE[(index + seed) % len(PALETTE)]
            draw.text((x0 + left - bounds[0], y0 + top - bounds[1]), word, font=font, fill=color)
            placed = True
            break
        if not placed and size > 14:
            # Keep the most prominent words visible without overlapping.
            continue


def main() -> None:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Korean font not found: {FONT_PATH}")
    source_rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig")))
    article_tokens = [tokenize(f"{row['제목']} {row['요약']}") for row in source_rows]
    document_frequency = Counter(word for doc in article_tokens for word in set(doc))
    total_docs = max(1, len(article_tokens))
    idf = {word: math.log((total_docs + 1) / (freq + 1)) + 1 for word, freq in document_frequency.items()}

    groups: dict[tuple[str, str], list[list[str]]] = defaultdict(list)
    for row, tokens in zip(source_rows, article_tokens):
        for brand in row["브랜드"].split("·"):
            groups[(brand, row["주제"])].append(tokens)

    comparison_rows = []
    for brand in BRANDS:
        for topic in TOPICS:
            docs = groups.get((brand, topic), [])
            values = best_positions(Counter(), idf, docs)
            bow, tfidf = values["BoW"], values["TF-IDF"]
            for rank in range(20):
                comparison_rows.append({
                    "브랜드": brand,
                    "주제": topic,
                    "기사 수": len(docs),
                    "순위": rank + 1,
                    "BoW 키워드": bow[rank][0] if rank < len(bow) else "",
                    "BoW 빈도": bow[rank][1] if rank < len(bow) else "",
                    "TF-IDF 키워드": tfidf[rank][0] if rank < len(tfidf) else "",
                    "TF-IDF 점수": f"{tfidf[rank][1]:.6f}" if rank < len(tfidf) else "",
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    FIGURES.mkdir(parents=True, exist_ok=True)
    for brand_index, brand in enumerate(BRANDS):
        cell_w, cell_h = 700, 310
        margin, header_h = 28, 90
        image = Image.new("RGB", (margin * 2 + 2 * cell_w, header_h + 5 * cell_h + margin), "#FFFFFF")
        draw = ImageDraw.Draw(image)
        title_font = ImageFont.truetype(str(FONT_PATH), 34)
        label_font = ImageFont.truetype(str(FONT_PATH), 20)
        method_font = ImageFont.truetype(str(FONT_PATH), 17)
        draw.text((margin, 18), f"{brand} 뉴스 키워드 워드 클라우드", font=title_font, fill="#17324D")
        draw.text((margin, 62), "BoW: 단어 빈도  |  TF-IDF: 전체 기사 대비 특징도", font=method_font, fill="#52616F")

        for topic_index, topic in enumerate(TOPICS):
            y0 = header_h + topic_index * cell_h
            draw.text((margin, y0 + 5), topic, font=label_font, fill="#17324D")
            for method_index, method in enumerate(("BoW", "TF-IDF")):
                x0 = margin + method_index * cell_w
                method_label = "BoW · 단어 빈도" if method == "BoW" else "TF-IDF · 상대적 특징도"
                draw.text((x0 + 6, y0 + 38), method_label, font=method_font, fill="#52616F")
                docs = groups.get((brand, topic), [])
                pairs = best_positions(Counter(), idf, docs)[method]
                draw_cloud(draw, (x0 + 6, y0 + 66, x0 + cell_w - 16, y0 + cell_h - 8), pairs, brand_index * 11 + topic_index * 3 + method_index)

        image.save(FIGURES / f"news_keyword_wordcloud_{brand}_{20261102}.png", optimize=True)

    print(f"articles={len(source_rows)}; brands={len(BRANDS)}; topics={len(TOPICS)}")
    print(f"comparison={OUTPUT.relative_to(ROOT)}")
    for brand in BRANDS:
        print(f"wordcloud={Path('outputs/figures') / f'news_keyword_wordcloud_{brand}_{20261102}.png'}")


if __name__ == "__main__":
    main()
