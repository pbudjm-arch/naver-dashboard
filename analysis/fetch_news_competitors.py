"""Fetch the latest 50 NAVER API HUB news results for three brands."""

from datetime import datetime
from pathlib import Path
import csv
import json
import os
import re
import html
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
QUERIES = ["유니클로", "스파오", "탑텐"]


def load_env_file() -> None:
    for line in (ROOT / "api_keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def clean_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or ""))


def main() -> int:
    load_env_file()
    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("STOP: API key values are missing; no requests were sent.")
        return 2

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = ROOT / "data" / "processed" / "raw"
    processed_dir = ROOT / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for query in QUERIES:
        url = f"{BASE_URL}?{urlencode({'query': query, 'display': 50, 'start': 1, 'sort': 'date', 'format': 'json'})}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            print(f"FAIL {query}: HTTP {exc.code}; response body omitted")
            return 1
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            print(f"FAIL {query}: request error ({type(exc).__name__})")
            return 1

        items = payload.get("items", []) if isinstance(payload, dict) else []
        if status != 200 or not items:
            print(f"FAIL {query}: HTTP {status}; no result items returned")
            return 1

        raw_path = raw_dir / f"news_{query}_{stamp}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for rank, item in enumerate(items, start=1):
            rows.append({
                "query": query,
                "rank": rank,
                "title": clean_text(item.get("title", "")),
                "description": clean_text(item.get("description", "")),
                "pubDate": item.get("pubDate", ""),
                "originallink": item.get("originallink", ""),
                "link": item.get("link", ""),
            })
        print(f"PASS {query}: HTTP {status}; returned={len(items)}; total={payload.get('total', 'n/a')}; raw={raw_path.relative_to(ROOT)}")

    csv_path = processed_dir / f"news_competitors_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "rank", "title", "description", "pubDate", "originallink", "link"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV: {csv_path.relative_to(ROOT)}")
    print("RESULTS")
    for row in rows:
        print(f"{row['query']}\t{row['rank']}\t{row['pubDate']}\t{row['title']}\t{row['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
