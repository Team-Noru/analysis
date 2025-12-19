import os
import json
import time
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from constants.top20List import TOP20_TICKERS
from utils.disclosure_title import is_major_disclosure, classify_category, dart_viewer_url, fetch_major_disclosures_until
from utils.data import load_ticker_to_corp_code
load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")
CORP_MERGED_PATH = "./corp_merged.json"  
OUTPUT_JSON_PATH = "./output/announcements_top20_major.json"

def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY가 .env 없음")

    os.makedirs("./output", exist_ok=True)

    ticker_map = load_ticker_to_corp_code(CORP_MERGED_PATH)

    results: List[Dict[str, Any]] = []
    missing: List[str] = []

    for i, ticker in enumerate(TOP20_TICKERS, start=1):
        info = ticker_map.get(ticker)
        if not info:
            missing.append(ticker)
            continue

        corp_code = info.get("corp_code")
        corp_name = info.get("name")

        print(f"\n[{i}/{len(TOP20_TICKERS)}] {corp_name} ({ticker}) corp_code={corp_code}")

        majors = fetch_major_disclosures_until(
            dart_key=DART_KEY,
            corp_code=corp_code,
            target_major=5,   # 회사당 몇건씩 크롤링할지
            days=365 * 3,      # 3년치까지 넓혀서 몇건 채우기 쉬움
            max_pages=100,     # 부족하면 더 늘려도 됨 (100페이지=1만건 스캔 상한)
            page_count=100,
            sleep_sec=0.2,
        )

        # DB 저장용 레코드 형태로 변환
        for item in majors:
            rcept_no = item.get("rcept_no")
            report_nm = item.get("report_nm")

            results.append({
                "company_id": ticker,  
                "category": classify_category(report_nm or ""),
                "title": report_nm,
                "announcement_url": dart_viewer_url(rcept_no) if rcept_no else None,
                "published_at": item.get("rcept_dt"), 
                "meta": {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "rcept_no": rcept_no,
                    "flr_nm": item.get("flr_nm"),
                    "rm": item.get("rm"),
                }
            })

        print(f"  -> collected major: {len(majors)}")

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"saved {len(results)} rows -> {OUTPUT_JSON_PATH}")



if __name__ == "__main__":
    main()


