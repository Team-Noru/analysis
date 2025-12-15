import os
import json
from collections import Counter
from typing import Dict, Any, List, Tuple

from keyword_kobert import KoNewsKeywordExtractor


def has_samsung_in_companies(data: Dict[str, Any]) -> bool:
    """
    analysis.companies 안에 '삼성전자' 키가 존재하는지 확인
    """
    analysis = data.get("analysis", {}) or {}
    companies = analysis.get("companies", {}) or {}
    return "삼성전자" in companies


def load_articles_with_samsung(folder: str) -> List[Tuple[str, str, str]]:
    """
    (file_name, title, content) 리스트 반환
    """
    results = []
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(folder, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[SKIP] {fn}: json load error -> {e}")
            continue

        if not has_samsung_in_companies(data):
            continue

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()

        if not title and not content:
            continue

        results.append((fn, title, content))

    return results


def main():
    INPUT_DIR = "./뉴스_크롤링"

    extractor = KoNewsKeywordExtractor(top_n=5)

    total_freq = Counter()  
    doc_freq = Counter()     

    articles = load_articles_with_samsung(INPUT_DIR)
    print(f"삼성전자 포함 기사 수: {len(articles)}")

    for fn, title, content in articles:
        kws = extractor.extract_from_article(title, content, top_n=5, with_scores=False)
        total_freq.update(kws)
        doc_freq.update(set(kws))

    # '삼성전자' 키워드가 실제로 추출되는 빈도 확인
    print("\n[CHECK] 키워드로 뽑힌 '삼성전자' 빈도")
    print(f"  total_freq['삼성전자'] = {total_freq.get('삼성전자', 0)}")
    print(f"  doc_freq['삼성전자']   = {doc_freq.get('삼성전자', 0)}")

    # 상위 키워드 출력
    print("\n[TOP 30] total_freq 기준")
    for kw, cnt in total_freq.most_common(30):
        print(f"{kw}\t{cnt}")

    print("\n[TOP 30] doc_freq(기사 수) 기준")
    for kw, cnt in doc_freq.most_common(30):
        print(f"{kw}\t{cnt}")

    out_total = [{"keyword": k, "count": c} for k, c in total_freq.most_common()]
    out_doc = [{"keyword": k, "count": c} for k, c in doc_freq.most_common()]

    with open("samsung_keywords_total_freq.json", "w", encoding="utf-8") as f:
        json.dump(out_total, f, ensure_ascii=False, indent=2)

    with open("samsung_keywords_doc_freq.json", "w", encoding="utf-8") as f:
        json.dump(out_doc, f, ensure_ascii=False, indent=2)

    print("저장 완료:")
    print(" - samsung_keywords_total_freq.json")
    print(" - samsung_keywords_doc_freq.json")


if __name__ == "__main__":
    main()
