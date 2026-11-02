"""Collect and visualize NAVER DataLab brand search trends."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "processed" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
ENDPOINT = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
BRANDS = {
    "유니클로": ["유니클로", "UNIQLO"],
    "스파오": ["스파오", "SPAO"],
    "탑텐": ["탑텐", "TOPTEN"],
}
AGES = {
    "0~12세": "1", "13~18세": "2", "19~24세": "3", "25~29세": "4",
    "30~34세": "5", "35~39세": "6", "40~44세": "7", "45~49세": "8",
    "50~54세": "9", "55~59세": "10", "60세 이상": "11",
}
COLORS = {"유니클로": "#d62828", "스파오": "#277da1", "탑텐": "#43aa8b"}
FONT_PATH = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def post(headers: dict[str, str], body: dict) -> dict:
    request = Request(ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Keep credentials and request headers out of error text/logs.
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"NAVER API returned HTTP {exc.code}: {detail}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"NAVER API network request failed: {type(exc).__name__}") from None


def flatten(payload: dict, segment: str) -> list[dict]:
    rows = []
    for result in payload.get("results", []):
        for item in result.get("data", []):
            rows.append({
                "brand": result.get("title", ""),
                "segment": segment,
                "period": item.get("period", ""),
                "ratio": item.get("ratio"),
            })
    return rows


def draw_line_chart(image: Image.Image, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                    datasets: dict[str, list[tuple[datetime, float]]], title: str,
                    y_label: str, x_ticks: list[tuple[float, str]], legend: bool = True,
                    small: bool = False) -> None:
    x0, y0, x1, y1 = box
    title_font = ImageFont.truetype(str(FONT_PATH), 24 if not small else 18)
    label_font = ImageFont.truetype(str(FONT_PATH), 15 if not small else 11)
    draw.text((x0, y0), title, font=title_font, fill="#17324D")
    left, right = x0 + (74 if not small else 45), x1 - 12
    top, bottom = y0 + (40 if not small else 28), y1 - (40 if not small else 28)
    for val in (0, 25, 50, 75, 100):
        y = bottom - (bottom - top) * val / 100
        draw.line((left, y, right, y), fill="#E2E7EB", width=1)
        draw.text((x0 + 2, y - 8), str(val), font=label_font, fill="#52616F")
    draw.line((left, top, left, bottom), fill="#687784", width=1)
    draw.line((left, bottom, right, bottom), fill="#687784", width=1)
    for pos, label in x_ticks:
        x = left + (right - left) * pos
        draw.line((x, bottom, x, bottom + 4), fill="#687784", width=1)
        draw.text((x - 21, bottom + 7), label, font=label_font, fill="#52616F")
    all_dates = [d for points in datasets.values() for d, _ in points]
    if not all_dates:
        return
    min_date, max_date = min(all_dates), max(all_dates)
    span = max(1, (max_date - min_date).days)
    for brand, points in datasets.items():
        coords = []
        for date, ratio in points:
            x = left + (right - left) * (date - min_date).days / span
            y = bottom - (bottom - top) * min(100, max(0, float(ratio))) / 100
            coords.append((x, y))
        if len(coords) > 1:
            draw.line(coords, fill=COLORS[brand], width=3 if not small else 2)
        for x, y in coords:
            r = 2 if small else 3
            draw.ellipse((x-r, y-r, x+r, y+r), fill=COLORS[brand])
    if legend:
        lx, ly = x1 - 300, y0 + 2
        for brand in BRANDS:
            draw.line((lx, ly + 10, lx + 22, ly + 10), fill=COLORS[brand], width=3)
            draw.text((lx + 28, ly), brand, font=label_font, fill="#17324D")
            lx += 90


def year_ticks(points: list[tuple[datetime, float]]) -> list[tuple[float, str]]:
    if not points:
        return []
    first, last = points[0][0], points[-1][0]
    span = max(1, (last - first).days)
    return [((datetime(y, 1, 1) - first).days / span, str(y))
            for y in range(first.year, last.year + 1) if first <= datetime(y, 1, 1) <= last]


def main() -> None:
    for line in (ROOT / "api_keys.env").read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret or client_id.startswith("여기에") or client_secret.startswith("여기에"):
        raise SystemExit("NAVER API HUB credentials are empty or placeholders; no request was sent.")

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
        "Content-Type": "application/json",
    }

    # Five complete years give enough context for seasonality and recent changes.
    last_month = datetime.now().replace(day=1)
    end_date = (last_month - timedelta(days=1)).date().isoformat()
    monthly_body = {
        "startDate": "2021-11-01", "endDate": end_date, "timeUnit": "month",
        "keywordGroups": [
            {"groupName": brand, "keywords": terms} for brand, terms in BRANDS.items()
        ],
    }
    raw_payloads = {}
    cache_path = None
    try:
        monthly = post(headers, monthly_body)
        raw_payloads["monthly"] = monthly
        for age_label, age_code in AGES.items():
            body = {**monthly_body, "ages": [age_code]}
            raw_payloads[f"age_{age_code}"] = post(headers, body)
    except RuntimeError:
        caches = sorted(RAW.glob("naver_brand_search_trend_raw_*.json"))
        if not caches:
            raise
        # Some API deployments reject a request ending on the last completed
        # calendar day. Reuse the latest successful response and omit its
        # partial current-month observations below.
        cache_path = caches[-1]
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        raw_payloads = cached["responses"]
        print(f"API request unavailable; using prior successful response: {cache_path.name}")
    monthly = raw_payloads["monthly"]
    records = flatten(monthly, "전체 연령")
    age_rows = []
    for age_label, age_code in AGES.items():
        age_rows.extend(flatten(raw_payloads[f"age_{age_code}"], age_label))

    raw_path = cache_path or (RAW / f"naver_brand_search_trend_raw_{stamp}.json")
    if cache_path is None:
        raw_path.write_text(json.dumps({"collected_at": datetime.now().isoformat(timespec="seconds"),
                                        "endpoint": ENDPOINT, "monthly_request": monthly_body,
                                        "age_codes": AGES, "responses": raw_payloads},
                                       ensure_ascii=False, indent=2), encoding="utf-8")

    monthly_df = pd.DataFrame(records)
    age_df = pd.DataFrame(age_rows)
    monthly_df["period"] = pd.to_datetime(monthly_df["period"])
    age_df["period"] = pd.to_datetime(age_df["period"])
    # Keep only complete months, even if the endpoint returned the current
    # partial month in a cached response.
    cutoff = pd.Timestamp(end_date)
    monthly_df = monthly_df[monthly_df.period <= cutoff].copy()
    age_df = age_df[age_df.period <= cutoff].copy()
    monthly_csv = PROCESSED / f"brand_search_trend_monthly_{stamp}.csv"
    age_csv = PROCESSED / f"brand_search_trend_age_monthly_{stamp}.csv"
    monthly_df.to_csv(monthly_csv, index=False, encoding="utf-8-sig")
    age_df.to_csv(age_csv, index=False, encoding="utf-8-sig")

    font = ImageFont.truetype(str(FONT_PATH), 16)
    image = Image.new("RGB", (1600, 760), "white")
    draw = ImageDraw.Draw(image)
    datasets = {}
    for brand in BRANDS:
        subset = monthly_df[monthly_df.brand == brand].sort_values("period")
        datasets[brand] = [(d.to_pydatetime(), float(v)) for d, v in zip(subset.period, subset.ratio)]
    period_label = f"2021.11~{end_date[:7].replace('-', '.')}"
    draw_line_chart(image, draw, (75, 35, 1530, 680), datasets,
                    f"브랜드별 네이버 검색 관심도 월간 추이 ({period_label})",
                    "상대 검색 지수", year_ticks(datasets[list(BRANDS)[0]]))
    draw.text((75, 725), "출처: NAVER DataLab 검색어 트렌드 API | 동일 요청 브랜드를 함께 비교 (전체 최고=100)", font=font, fill="#555555")
    monthly_png = FIGURES / f"brand_search_trend_monthly_{stamp}.png"
    image.save(monthly_png, optimize=True)

    image = Image.new("RGB", (1800, 1500), "white")
    draw = ImageDraw.Draw(image)
    draw.text((55, 18), "연령대별 브랜드 검색 관심도 추이", font=ImageFont.truetype(str(FONT_PATH), 32), fill="#17324D")
    for index, (age_label, _) in enumerate(AGES.items()):
        col, row = index % 3, index // 3
        x, y = 45 + col * 580, 75 + row * 335
        part = age_df[age_df.segment == age_label]
        datasets = {}
        for brand in BRANDS:
            subset = part[part.brand == brand].sort_values("period")
            datasets[brand] = [(d.to_pydatetime(), float(v)) for d, v in zip(subset.period, subset.ratio)]
        ticks = year_ticks(datasets[list(BRANDS)[0]])
        draw_line_chart(image, draw, (x, y, x + 555, y + 300), datasets, age_label,
                        "상대 검색 지수", ticks, legend=(index == 0), small=True)
    draw.text((45, 1425), "각 연령 패널 안에서 브랜드를 비교할 수 있습니다. 연령 패널끼리는 검색자 비중 비교용이 아닙니다.", font=font, fill="#555555")
    age_png = FIGURES / f"brand_search_trend_by_age_{stamp}.png"
    image.save(age_png, optimize=True)

    summary = []
    for brand in BRANDS:
        subset = monthly_df[monthly_df.brand == brand].sort_values("ratio", ascending=False)
        top = subset.head(3)
        summary.append({
            "brand": brand,
            "peak_month": str(top.iloc[0].period.date()),
            "peak_index": round(float(top.iloc[0].ratio), 2),
            "top_months": "; ".join(f"{r.period:%Y-%m} ({r.ratio:.1f})" for r in top.itertuples()),
            "latest_month": str(monthly_df[monthly_df.brand == brand].sort_values("period").iloc[-1].period.date()),
            "latest_index": round(float(monthly_df[monthly_df.brand == brand].sort_values("period").iloc[-1].ratio), 2),
        })
    summary_df = pd.DataFrame(summary)
    summary_csv = PROCESSED / f"brand_search_trend_summary_{stamp}.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print(f"RAW={raw_path}")
    print(f"MONTHLY={monthly_csv}")
    print(f"AGE={age_csv}")
    print(f"SUMMARY={summary_csv}")
    print(f"MONTHLY_PLOT={monthly_png}")
    print(f"AGE_PLOT={age_png}")
    print("SUMMARY_ROWS")
    print(summary_df.to_string(index=False))
    print("AGE_PEAKS")
    for (age, brand), group in age_df.groupby(["segment", "brand"]):
        top = group.loc[group.ratio.idxmax()]
        print(f"{age}\t{brand}\t{top.period:%Y-%m}\t{top.ratio:.2f}")


if __name__ == "__main__":
    main()
