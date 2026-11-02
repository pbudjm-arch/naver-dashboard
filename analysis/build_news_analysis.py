"""Top up brand news counts and build a deduplicated analysis CSV."""

from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
import csv
import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
BRANDS = ["유니클로", "스파오", "탑텐"]
SOURCE = ROOT / "data" / "processed" / "news_competitors_cleaned_20261101_192237.csv"
EXCLUDE_URLS = {
    "https://www.topstarnews.net/news/articleView.html?idxno=16260917",
    "https://www.sisaweek.com/news/articleView.html?idxno=238648",
    "https://wemakenews.co.kr/news/view.php?no=26696",
    "https://biz.sbs.co.kr/article_hub/20000342640?division=NAVER",
}
SPAO_PARENT_ARTICLE_PREFIXES = (
    "기네스 세계기록 2개 부문 인증...이랜드, 30년 모은",
    "[Who Is ?] 최종양 이랜드그룹",
    "[재계 인사이드] 이랜드 박성수 회장",
    "[리포트] 이랜드, '30년 모은 소장품",
    "[WIKI 현장] 30년간 모은 소장품",
    "이랜드, 여행 가방 7816점",
    "[현장] 이랜드 30년 아카이브 최초",
    '[현장] 이랜드 "소장품 100만 점',
    "'기네스 2관왕' 이랜드, 30년 수집품",
    "[C스토리] 마이클 잭슨 재킷까지",
    "기네스도 반한 이랜드뮤지엄",
    "[르포] 박성수의 30년 수집史",
    "마릴린 먼로 드레스부터 여행가방",
    "이랜드, 30년 수집한 소장품 100만점",
    "[현장] 기네스 오른 이랜드의 30년 수집",
    "[현장] 세계기록 세운 '수집광' 이랜드",
)


def load_env_file() -> None:
    for line in (ROOT / "api_keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def clean_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or ""))


def excluded(brand: str, title: str, url: str) -> bool:
    if brand == "탑텐" and (
        "tenasia.co.kr" in url
        or any(term in title for term in ("탑텐가요쇼", "뉴스탑텐", "MAMA"))
    ):
        return True
    if brand == "유니클로" and url in EXCLUDE_URLS:
        return True
    if brand == "스파오" and title.startswith(SPAO_PARENT_ARTICLE_PREFIXES):
        return True
    return False


def labels(row: dict) -> set[str]:
    return set(row["브랜드"].split("·"))


def main() -> int:
    load_env_file()
    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("STOP: API key values are missing; no requests were sent.")
        return 2

    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig")))
    by_url = {row["원문 링크"]: row for row in rows}
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }
    raw_dir = ROOT / "data" / "processed" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for brand in BRANDS:
        start = 51
        while sum(brand in labels(row) for row in rows) < 50 and start <= 1000:
            query = urlencode({
                "query": brand,
                "display": 50,
                "start": start,
                "sort": "date",
                "format": "json",
            })
            cached = sorted(raw_dir.glob(f"news_{brand}_*_start{start}.json"), key=lambda p: p.stat().st_mtime)
            if cached:
                raw_path = cached[-1]
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                status = 200
            else:
                request = Request(f"{BASE_URL}?{query}", headers=headers, method="GET")
                try:
                    with urlopen(request, timeout=30) as response:
                        status = response.status
                        payload = json.loads(response.read().decode("utf-8"))
                except HTTPError as exc:
                    print(f"FAIL {brand} start={start}: HTTP {exc.code}; body omitted")
                    return 1
                except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                    print(f"FAIL {brand} start={start}: request error ({type(exc).__name__})")
                    return 1

            if status != 200 or not isinstance(payload, dict):
                print(f"FAIL {brand} start={start}: unexpected response")
                return 1

            if not cached:
                raw_path = raw_dir / f"news_{brand}_{stamp}_start{start}.json"
                raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            added = 0
            for item in payload.get("items", []):
                title = clean_text(item.get("title", ""))
                original_link = item.get("originallink", "")
                if not original_link or excluded(brand, title, original_link):
                    continue
                if original_link in by_url:
                    row = by_url[original_link]
                    current = labels(row)
                    if brand in current:
                        continue
                    current.add(brand)
                    row["브랜드"] = "·".join(b for b in BRANDS if b in current)
                else:
                    row = {
                        "브랜드": brand,
                        "제목": title,
                        "요약": clean_text(item.get("description", "")),
                        "날짜": item.get("pubDate", ""),
                        "원문 링크": original_link,
                    }
                    rows.append(row)
                    by_url[original_link] = row
                added += 1
                if sum(brand in labels(existing) for existing in rows) >= 50:
                    break

            print(
                f"{brand}: start={start}, returned={len(payload.get('items', []))}, "
                f"new_brand_rows={added}, total_brand_rows={sum(brand in labels(row) for row in rows)}"
            )
            start += 50

        total = sum(brand in labels(row) for row in rows)
        if total < 50:
            print(f"STOP: only {total} usable rows found for {brand} through start=1000.")
            return 1

    def sort_key(row: dict):
        first_brand = min(BRANDS.index(brand) for brand in labels(row))
        try:
            date_value = parsedate_to_datetime(row["날짜"]).timestamp()
        except (TypeError, ValueError, OverflowError):
            date_value = 0
        return first_brand, -date_value, row["제목"]

    rows.sort(key=sort_key)
    output = ROOT / "data" / "processed" / f"news_competitors_analysis_{stamp}.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["브랜드", "제목", "요약", "날짜", "원문 링크"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"OUTPUT {output.relative_to(ROOT)}; unique_articles={len(rows)}")
    for brand in BRANDS:
        print(f"COUNT {brand}={sum(brand in labels(row) for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
