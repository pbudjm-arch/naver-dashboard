"""Small, credential-safe smoke test for the NAVER API HUB endpoints."""

from pathlib import Path
import argparse
import os
import json
import html
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://naverapihub.apigw.ntruss.com"


def load_env_file() -> None:
    for line in (ROOT / "api_keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Test NAVER API HUB with a keyword.")
    parser.add_argument("--query", default="네이버", help="keyword to search")
    query = parser.parse_args().query.strip()
    if not query:
        print("STOP: query must not be empty.")
        return 2

    load_env_file()
    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("STOP: NAVER_API_HUB_CLIENT_ID and/or NAVER_API_HUB_CLIENT_SECRET is empty.")
        return 2
    if client_id.lower().startswith(("your_", "여기에", "<")) or client_secret.lower().startswith(("your_", "여기에", "<")):
        print("STOP: API key values look like placeholders; no request was sent.")
        return 2

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }
    checks = [
        (
            "news_search",
            "GET",
            f"{BASE_URL}/search/v1/news",
            {"query": query, "display": 5, "sort": "date", "format": "json"},
            None,
        ),
        (
            "search_trend",
            "POST",
            f"{BASE_URL}/search-trend/v1/search",
            None,
            {
                "startDate": "2026-10-01",
                "endDate": "2026-10-31",
                "timeUnit": "week",
                "keywordGroups": [{"groupName": query, "keywords": [query]}],
            },
        ),
        (
            "shopping_category_trend",
            "POST",
            f"{BASE_URL}/shopping/v1/categories",
            None,
            {
                "startDate": "2026-10-01",
                "endDate": "2026-10-31",
                "timeUnit": "month",
                "category": [{"name": "패션의류", "param": ["50000000"]}],
            },
        ),
    ]

    failures = 0
    for name, method, url, params, body in checks:
        try:
            if params:
                url = f"{url}?{urlencode(params)}"
            request_headers = {**headers, **({"Content-Type": "application/json"} if body else {})}
            data = json.dumps(body).encode("utf-8") if body else None
            request = Request(url, data=data, headers=request_headers, method=method)
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as response:
                status = response.code
                payload = None

            if 200 <= status < 300 and isinstance(payload, dict):
                if name == "news_search":
                    detail = f"items={len(payload.get('items', []))}, total={payload.get('total', 'n/a')}"
                    print(f"PASS {name} ({query}): HTTP {status}; {detail}")
                    for item in payload.get("items", []):
                        title = html.unescape(re.sub(r"<[^>]+>", "", item.get("title", "")))
                        print(f"  - {title} ({item.get('pubDate', '날짜 없음')})")
                    continue
                else:
                    detail = f"results={len(payload.get('results', []))}"
                print(f"PASS {name}: HTTP {status}; {detail}")
                if name == "search_trend":
                    for result in payload.get("results", []):
                        print(f"  {result.get('title', query)}: {result.get('data', [])}")
            else:
                failures += 1
                if status in (401, 403):
                    category = "authentication/permission or application API entitlement"
                elif status == 429:
                    category = "daily quota exceeded"
                else:
                    category = "request/endpoint/server error"
                print(f"FAIL {name}: HTTP {status}; {category}")
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            failures += 1
            print(f"FAIL {name}: network/request error ({type(exc).__name__})")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
