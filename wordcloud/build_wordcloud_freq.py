import os, json
from collections import Counter
from typing import Dict, Any, List, Tuple

from keyword_kobert import KoNewsKeywordExtractor


INPUT_DIR = "./뉴스_크롤링"   # 너 폴더로 수정
PER_ARTICLE_TOPN = 30                  # 워드클라우드는 20~50 추천
GLOBAL_TOPN = 200                      # 최종 상위 몇 개 저장할지


def has_samsung(data: Dict[str, Any]) -> bool:
    analysis = data.get("analysis", {}) or {}
    companies = analysis.get("companies", {}) or {}
    return "삼성전자" in companies


def iter_articles(folder: str):
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(folder, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            continue

        if not has_samsung(data):
            continue

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        if not title and not content:
            continue

        yield fn, title, content


def main():
    extractor = KoNewsKeywordExtractor(top_n=PER_ARTICLE_TOPN)
    extractor.stopwords.update({"삼성", "삼성전자"})

    total_freq = Counter()

    article_count = 0
    for fn, title, content in iter_articles(INPUT_DIR):
        article_count += 1
        
        kws = extractor.extract_from_article(
            title, content,
            top_n=PER_ARTICLE_TOPN,
            with_scores=False
        )
        total_freq.update(kws)

    print(f"삼성전자 포함 기사 수: {article_count}")
    print(f"키워드 종류 수: {len(total_freq)}")

    top_items = total_freq.most_common(GLOBAL_TOPN)
    out = [{"text": k, "weight": int(v)} for k, v in top_items]

    with open("samsung_wordcloud_freq.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("저장 완료: samsung_wordcloud_freq.json")


if __name__ == "__main__":
    main()
