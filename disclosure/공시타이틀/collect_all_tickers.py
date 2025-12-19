import os
import json
import time
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any, List
from tqdm import tqdm
from utils.disclosure_title import is_major_disclosure, classify_category, dart_viewer_url, fetch_major_disclosures_until
from utils.data import load_ticker_to_corp_code

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")
CORP_MERGED_PATH = "./corp_merged.json"
OUTPUT_JSON_PATH = "./output/announcements_all_tickers_major5.json"


def load_companies_with_ticker(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    companies = []
    for row in data:
        ticker = (row.get("ticker") or row.get("dart_stock_code") or "").strip()
        corp_code = (row.get("corp_code") or "").strip()
        name = row.get("name")

        if ticker and corp_code and name:
            row["_ticker"] = ticker
            companies.append(row)

    return companies


def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 없음")

    os.makedirs("./output", exist_ok=True)

    companies = load_companies_with_ticker(CORP_MERGED_PATH)

    results: List[Dict[str, Any]] = []

    for i, info in enumerate(tqdm(companies, desc="Collecting major disclosures"), start=1):
        ticker = info["_ticker"]
        corp_code = info.get("corp_code")
        corp_name = info.get("name")

        try:
            majors = fetch_major_disclosures_until(
                dart_key=DART_KEY,
                corp_code=corp_code,
                target_major=5,      
                days=365 ,
                max_pages=100,
                page_count=100,
                sleep_sec=0.2,
            )
        except Exception as e:
            print(f"\n[WARN] {corp_name}({ticker}) corp_code={corp_code} fetch failed: {e}")
            continue

        for item in majors:
            rcept_no = item.get("rcept_no")
            report_nm = item.get("report_nm") or ""

            results.append({
                "company_id": ticker,  
                "category": classify_category(report_nm),
                "title": report_nm,
                "announcement_url": dart_viewer_url(rcept_no) if rcept_no else None,
                "published_at": item.get("rcept_dt"),  
                "meta": {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "ticker": ticker,
                    "rcept_no": rcept_no,
                    "flr_nm": item.get("flr_nm"),
                    "rm": item.get("rm"),
                }
            })

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\ndone: saved {len(results)} rows -> {OUTPUT_JSON_PATH}")

if __name__ == "__main__":
    main()
