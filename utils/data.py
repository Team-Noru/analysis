import json
from typing import Any, Dict, Iterator, List, Optional, TypeVar
T = TypeVar("T")
def yyyymmdd_to_yyyy_mm_dd(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s  


def chunked(lst, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]
        

# corp_merged.json에서 ticker -> corp_code 매핑
def load_ticker_to_corp_code(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    out: Dict[str, Dict[str, Any]] = {}
    for row in data:
        t = (row.get("ticker") or row.get("dart_stock_code") or "").strip()
        if t:
            out[t] = row
    return out