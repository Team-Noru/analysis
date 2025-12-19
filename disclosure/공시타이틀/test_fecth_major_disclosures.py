import os
import time
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")
LIST_URL = "https://opendart.fss.or.kr/api/list.json"
from utils.disclosure_title import is_major_disclosure, classify_tag, dart_viewer_url, fetch_major_disclosures_until

if __name__ == "__main__":
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 없음")

    SAMSUNG_CORP_CODE = "00126380"  
    major5 = fetch_major_disclosures_until(
        dart_key=DART_KEY,
        SAMSUNG_CORP_CODE,
        target_major=5,
        days=365,       # 최대 1년치까지
        max_pages=50,   # 최대 50페이지(=최대 5000건)까지 추출 후보
        page_count=100,
        sleep_sec=0.2,
    )

    for m in major5:
        print(f"[{m['date']}] ({m['tag']}) {m['title']}")
        print(f"  - 제출인: {m['flr_nm']} | rm={m['rm']}")
        print(f"  - viewer: {m['viewer']}\n")
