import os
import json
from collections import Counter
from typing import Dict, Any, Iterator, Tuple

from keyword_kobert import KoNewsKeywordExtractor

INPUT_DIR = "./뉴스_크롤링"
PER_ARTICLE_TOPN = 30     # 기사당 뽑을 키워드 수
GLOBAL_TOPN = 150         # 최종 워드클라우드에 쓸 상위 단어 수


def has_samsung_in_analysis(data: Dict[str, Any]) -> bool:
    analysis = data.get("analysis", {}) or {}
    companies = analysis.get("companies", {}) or {}
    return "삼성전자" in companies


def iter_samsung_articles(folder: str) -> Iterator[Tuple[str, str, str]]:
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue

        path = os.path.join(folder, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not has_samsung_in_analysis(data):
            continue

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()

        if not title and not content:
            continue

        yield fn, title, content


def main():
    extractor = KoNewsKeywordExtractor(top_n=PER_ARTICLE_TOPN, allow_english=False)
    extractor.stopwords.update({"삼성전자", "삼성"})

    freq = Counter()
    doc_count = 0

    for fn, title, content in iter_samsung_articles(INPUT_DIR):
        doc_count += 1
        kws = extractor.extract_from_article(
            title=title,
            content=content,
            top_n=PER_ARTICLE_TOPN,
            with_scores=False,
            candidate_multiplier=6,
        )
        freq.update(kws)

    print(f"삼성전자 포함 기사 수: {doc_count}")
    print(f"유니크 키워드 수: {len(freq)}")
    for k, v in freq.most_common(30):
        print(f"{k}\t{v}")
    out = [{"text": k, "weight": int(v)} for k, v in freq.most_common(GLOBAL_TOPN)]

    with open("samsung_wordcloud_freq.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n저장 완료: samsung_wordcloud_freq.json")


if __name__ == "__main__":
    main()
