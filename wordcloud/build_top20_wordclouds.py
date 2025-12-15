import os
import re
import json
from collections import Counter, defaultdict
from typing import Dict, Any, List, Tuple
from keyword_kobert import KoNewsKeywordExtractor
from constants.top20List import TOP20
from utils.wordcloudutils import safe_filename, iter_news_files, get_companies_in_news

INPUT_DIR = "./뉴스_크롤링"          # 뉴스 json 폴더
OUTPUT_DIR = "./wordcloud_out"     
PER_ARTICLE_TOPN = 30              # 기사당 키워드 개수
GLOBAL_TOPN = 150                  # 기업별 최종 워드클라우드 단어 수
EXCLUDE_SELF_NAME = True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name_to_ticker = {c["name"]: c["stock_code"] for c in TOP20}
    target_names = set(name_to_ticker.keys())
    bucket: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    total_files = 0
    used_files = 0

    for path in iter_news_files(INPUT_DIR):
        total_files += 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        if not title and not content:
            continue

        mentioned = set(get_companies_in_news(data))
        hit = mentioned & target_names
        if not hit:
            continue

        used_files += 1
        for name in hit:
            bucket[name].append((title, content))

    print(f"전체 뉴스 파일: {total_files}")
    print(f"상위20개 기업 중 하나라도 포함된 뉴스: {used_files}\n")

    # 키워드 추출
    extractor = KoNewsKeywordExtractor(top_n=PER_ARTICLE_TOPN, allow_english=False)

    # 기업별 워드클라우드 생성
    for company_name in TOP20:
        name = company_name["name"]
        ticker = company_name["stock_code"]

        articles = bucket.get(name, [])
        if not articles:
            print(f"[SKIP] {name}({ticker}) - 기사 0건")
            continue

        if EXCLUDE_SELF_NAME:
            extractor.stopwords.update({name})
        freq = Counter()

        for title, content in articles:
            kws = extractor.extract_from_article(
                title=title,
                content=content,
                top_n=PER_ARTICLE_TOPN,
                with_scores=False,
                candidate_multiplier=6,
            )
            freq.update(kws)

        out = [{"text": k, "weight": int(v)} for k, v in freq.most_common(GLOBAL_TOPN)]

        # 파일명: {ticker}_{company}_wordcloud.json
        out_name = f"{ticker}_{safe_filename(name)}_wordcloud.json"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"{name}({ticker})")
        print(f"기사 수: {len(articles)} | 유니크 키워드: {len(freq)}")
        print("TOP10:", ", ".join([k for k, _ in freq.most_common(10)]))
        print(f"{out_path}")


if __name__ == "__main__":
    main()
