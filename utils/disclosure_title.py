import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from constants.disclosure_keywords import (
    IMPORTANT_TYPES,
    EXCLUDE_KEYWORDS,
    IMPORTANT_KEYWORDS,
)
LIST_URL = "https://opendart.fss.or.kr/api/list.json"

def is_valid_rm(rm: str) -> bool:
    """
    rm은 '비고' 플래그 문자열(예: 유/코/정/철 등)
    여기선 정정(정), 철회(철) 포함이면 제외
    """
    if not rm:
        return True
    return not any(x in rm for x in ["정", "철"])

def is_major_disclosure(item: dict) -> bool:
    report_nm = item.get("report_nm", "") or ""
    pblntf_ty = item.get("pblntf_ty")  
    rm = item.get("rm", "") or ""

    if not is_valid_rm(rm):
        return False

    if any(k in report_nm for k in EXCLUDE_KEYWORDS):
        return False

    if any(k in report_nm for k in IMPORTANT_KEYWORDS):
        return True

    if pblntf_ty and pblntf_ty not in IMPORTANT_TYPES:
        return False

    return False

def classify_category(report_nm: str) -> str:
    r = report_nm or ""
    if any(k in r for k in ["횡령", "배임", "소송", "영업정지", "회생", "파산"]):
        return "리스크"
    if any(k in r for k in ["유상증자", "무상증자", "전환사채", "신주인수권부사채", "CB", "BW", "자사주취득", "자사주처분"]):
        return "투자"
    if any(k in r for k in ["대량보유", "최대주주", "주식취득", "주식처분", "경영권", "합병", "분할"]):
        return "지분"
    if any(k in r for k in ["배당", "실적", "잠정", "전망"]):
        return "실적"
    return "기타"

def dart_viewer_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def fetch_disclosures_page(dart_key: str, corp_code: str, bgn_de: str, end_de: str, page_no: int, page_count: int = 100) -> dict:
    params = {
        "crtfc_key": dart_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "sort": "date",
        "sort_mth": "desc",
        "page_no": page_no,
        "page_count": page_count,
    }
    r = requests.get(LIST_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "000":
        raise RuntimeError(f"DART list API error {data.get('status')}: {data.get('message')}")
    return data

def fetch_major_disclosures_until(
    dart_key: str,
    corp_code: str,
    target_major: int = 10,
    days: int = 365,
    page_count: int = 100,
    max_pages: int = 50,
    sleep_sec: float = 0.2,
) -> List[dict]:
    end_de = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    majors: List[dict] = []
    seen_rcept: set[str] = set()

    page_no = 1
    while len(majors) < target_major and page_no <= max_pages:
        data = fetch_disclosures_page(corp_code, bgn_de, end_de, page_no, page_count=page_count)
        rows = data.get("list", []) or []
        if not rows:
            break

        for item in rows:
            rcept_no = item.get("rcept_no")
            if not rcept_no or rcept_no in seen_rcept:
                continue
            seen_rcept.add(rcept_no)

            if is_major_disclosure(item):
                majors.append(item)
                if len(majors) >= target_major:
                    break

        page_no += 1
        time.sleep(sleep_sec)

    return majors