import os
import json
import time
import hashlib
import requests
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")
IRDS_URL = "https://opendart.fss.or.kr/api/irdsSttus.json"
COMPANY_LIST_PATH = "./company_list_market.json"
OUT_PATH = "./output/irds_risk_events.json"

# 조회할 보고서 목록
REPRT_CODES = {
    "11011": "사업보고서",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서",
}


def save_json_atomic(obj: Any, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def make_event_id(corp_code: str, rcept_no: str, payload: Dict[str, Any]) -> str:
    raw = f"{corp_code}|{rcept_no}|{payload.get('isu_dcrs_de','')}|{payload.get('isu_dcrs_stle','')}|{payload.get('isu_dcrs_stock_knd','')}|{payload.get('isu_dcrs_qy','')}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"risk:{corp_code}:{rcept_no}:{h[:10]}"


def fetch_irds(corp_code: str, bsns_year: int, reprt_code: str) -> List[Dict[str, Any]]:
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bsns_year": str(bsns_year),
        "reprt_code": reprt_code,
    }
    try:
        r = requests.get(IRDS_URL, params=params, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"IRDS 호출/파싱 실패 corp={corp_code} year={bsns_year} reprt={reprt_code} : {e}")
        return []

    status = data.get("status")
    if status == "000":
        return data.get("list", []) or []
    if status == "013":
        return []  # 조회 0건
    print(f"[ERROR] IRDS error corp={corp_code} year={bsns_year} reprt={reprt_code} status={status} msg={data.get('message')}")
    return []


def normalize_to_risk_events(corp: Dict[str, Any], bsns_year: int, reprt_code: str, rows: List[Dict[str, Any]]):
    """
    IRDS row(증자/감자 현황) → Risk Event Node + Edge 로 변환
    """
    corp_code = safe_str(corp.get("corp_code"))
    corp_name = safe_str(corp.get("name") or corp.get("corp_name"))

    events = []
    edges = []

    for row in rows:
        isu_dcrs_qy = to_int(row.get("isu_dcrs_qy"))
        isu_dcrs_de = safe_str(row.get("isu_dcrs_de"))
        isu_dcrs_stle = safe_str(row.get("isu_dcrs_stle"))
        stock_knd = safe_str(row.get("isu_dcrs_stock_knd"))
        fval = to_float(row.get("isu_dcrs_mstvdv_fval_amount"))
        price = to_float(row.get("isu_dcrs_mstvdv_amount"))
        stlm_dt = safe_str(row.get("stlm_dt"))
        rcept_no = safe_str(row.get("rcept_no"))

        # 이벤트 타입(리스크 관점) — 기본은 감자(감소)
        event_type = "CAPITAL_REDUCTION"
        stle_text = f"{isu_dcrs_stle} {stock_knd}"
        if ("증자" in stle_text) or ("발행" in stle_text and "감소" not in stle_text):
            event_type = "CAPITAL_INCREASE"
        if not rcept_no:
            continue

        payload = {
            "rcept_no": rcept_no,
            "isu_dcrs_de": isu_dcrs_de,
            "isu_dcrs_stle": isu_dcrs_stle,
            "isu_dcrs_stock_knd": stock_knd,
            "isu_dcrs_qy": isu_dcrs_qy,
            "isu_dcrs_mstvdv_fval_amount": fval,
            "isu_dcrs_mstvdv_amount": price,
            "stlm_dt": stlm_dt,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "reprt_name": REPRT_CODES.get(reprt_code, reprt_code),
        }

        event_id = make_event_id(corp_code, rcept_no, payload)

        event_node = {
            "node_id": event_id,
            "label": "RiskEvent",
            "event_type": event_type,          
            "risk_tag": "RISK",               
            "corp_code": corp_code,
            "corp_name": corp_name,
            "event_date": isu_dcrs_de or stlm_dt,
            "rcept_no": rcept_no,
            "payload": payload,
        }
        events.append(event_node)


        edge = {
            "from_id": f"corp:{corp_code}",
            "to_id": event_id,
            "rel_type": "RISK_EVENT",
            "event_type": event_type,
            "event_tag": "CAPITAL_STRUCTURE",
            "event_date": isu_dcrs_de or stlm_dt,
            "rcept_no": rcept_no,
            "weight": isu_dcrs_qy,   
            "source_json": "irdsSttus",
            "extra": payload,
        }
        edges.append(edge)

    return events, edges


def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY가 .env에 없습니다.")

    with open(COMPANY_LIST_PATH, "r", encoding="utf-8") as f:
        companies = json.load(f)

    out = {"events": [], "edges": []}
    done_keys = set()  

    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                out = json.load(f)
            for e in out.get("events", []):
                p = e.get("payload", {})
                done_keys.add((e.get("corp_code"), p.get("bsns_year"), p.get("reprt_code")))
            
        except Exception:
            out = {"events": [], "edges": []}
            done_keys = set()

    # 연도 설정
    YEARS = list(range(2019, 2025 + 1))

    total = len(companies)
    for i, corp in enumerate(companies, start=1):
        corp_code = safe_str(corp.get("corp_code"))
        if not corp_code:
            continue

        if i % 50 == 0:
            print(f"[PROGRESS] {i}/{total}")

        for year in YEARS:
            for reprt_code in REPRT_CODES.keys():
                if (corp_code, year, reprt_code) in done_keys:
                    continue

                rows = fetch_irds(corp_code, year, reprt_code)
                if rows:
                    events, edges = normalize_to_risk_events(corp, year, reprt_code, rows)
                    if events:
                        out["events"].extend(events)
                        out["edges"].extend(edges)
                        save_json_atomic(out, OUT_PATH)
                        print(f" {corp.get('name') or corp.get('corp_name')}({corp_code}) {year}-{reprt_code}: events={len(events)}")

                done_keys.add((corp_code, year, reprt_code))
                time.sleep(0.25)  

    print(f"완료: events={len(out['events'])}, edges={len(out['edges'])}")
    print(f"저장 경로: {OUT_PATH}")


if __name__ == "__main__":
    main()
