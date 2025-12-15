import os
import re
from typing import Dict, Any, List


#파일명 안전하게(공백/특수문자 제거)
def safe_filename(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^\w가-힣\-]+", "_", s)   
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def iter_news_files(folder: str):
    for fn in os.listdir(folder):
        if fn.endswith(".json"):
            yield os.path.join(folder, fn)


#뉴스 하나에서 analysis.companies의 '키(회사명)' 리스트 반환  
def get_companies_in_news(data: Dict[str, Any]) -> List[str]:
    analysis = data.get("analysis", {}) or {}
    companies = analysis.get("companies", {}) or {}
    return list(companies.keys())
