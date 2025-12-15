import re
from typing import List, Optional, Tuple

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


class KoNewsKeywordExtractor:
    """
    Ko-SRoBERTa 임베딩 + KeyBERT 기반 뉴스 키워드 추출기

    개선 사항:
    - HTML/JS/URL/숫자/날짜 등 노이즈 제거(_clean_content)
    - 영문 토큰 기본 제외(필요하면 allow_english=True)
    - 날짜/단위/숫자 포함 토큰 강력 필터링
    - 기사당 top_n을 크게 뽑아도 워드클라우드에 쓸만한 키워드만 남도록 필터 강화
    """

    def __init__(
        self,
        model_name: str = "jhgan/ko-sroberta-multitask",
        top_n: int = 20,
        allow_english: bool = False,
    ):
        self.top_n = top_n
        self.allow_english = allow_english

        st_model = SentenceTransformer(model_name)
        self.keybert = KeyBERT(model=st_model)

        # 기본 불용어 
        self.stopwords = {
            "기자", "이번", "다음", "지난", "당시", "현재", "오늘", "내일", "어제",
            "그러나", "하지만", "또한", "그리고", "때문", "통해", "위해", "따라",
            "이미지", "사진", "제공", "뉴스", "기사", "연합뉴스", "속보",
            "있는", "없는", "되는", "하는", "같은", "많은", "모든",
            "이상", "이하", "관련", "대한", "통한", "의한",
            "기준", "분야", "부문", "수준", "전망", "전망치", "영향", "변화",

            # 너무 흔한 금융/시장 단어 (워드클라우드에서 의미가 옅어지는 애들)
            "주가", "주식", "투자", "투자자", "투자자들", "종목", "기업",
            "증시", "코스피", "코스닥", "지수", "주요지수", "주가지수",
            "상승", "상승세", "하락", "대비", "마감", "마감했다",
            "매수", "순매수", "순매도", "순매도했다",
            "목표주가", "목표주",
        }

        # JS/HTML에서 많이 튀어나오는 노이즈 토큰
        self.js_noise = {
            "addclass", "removeclass", "hasclass", "click", "scroll",
            "videoheight", "var", "function", "document", "window",
        }

    # ----------------------- 전처리 ----------------------- #

    def _remove_josa_tail(self, word: str) -> str:
        if len(word) <= 2:
            return word

        josa_patterns = [
            r"(에서|에게|한테서|으로부터|로부터)$",
            r"(으로|로|와|과|랑|이랑)$",
            r"(을|를|이|가|은|는|에|에서|에게|한테|께)$",
            r"(의|도|만|까지|부터|마저|조차|밖에|뿐|라도|라서)$",
        ]

        cleaned = word
        for pattern in josa_patterns:
            cleaned = re.sub(pattern, "", cleaned)
        return cleaned

    def _clean_content(self, text: str) -> str:
        """
        워드클라우드 품질을 위해 본문에서 잡음 제거:
        - [IMG] 제거
        - HTML 태그 제거
        - URL 제거
        - JS/CSS 흔한 단어 제거
        - 숫자/날짜/단위 패턴 제거
        """
        if not text:
            return ""

        t = text

        # 이미지 마커/특수문자
        t = t.replace("[IMG]", " ")
        t = t.replace("\u200b", " ")  # zero-width space 같은 것

        # HTML 태그 제거
        t = re.sub(r"<[^>]+>", " ", t)

        # URL 제거
        t = re.sub(r"https?://\S+", " ", t)

        # JS/CSS 노이즈 제거 (단어 단위)
        t = re.sub(
            r"\b(addclass|removeclass|hasclass|videoheight|click|scroll|var|function|document|window)\b",
            " ",
            t,
            flags=re.I,
        )

        # 날짜/단위/숫자 토큰 제거
        # 예: 12일, 2025년, 3분기, 6조원, 0.25%p, 31억8400만, 02gwh 등
        t = re.sub(r"\b\d{1,4}(년|월|일|분기|주|개월)\b", " ", t)
        t = re.sub(r"\b\d+(조|억|만)?(원|달러|명|건|회)\b", " ", t)
        t = re.sub(r"\b\d+(\.\d+)?%p?\b", " ", t)
        t = re.sub(r"\b\d+[a-zA-Z]+\b", " ", t)   # 02gwh 같은 토큰
        t = re.sub(r"\b\d+\b", " ", t)

        # 공백 정리
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _build_input_text(self, title: str, content: Optional[str]) -> str:
        """
        제목 가중치 3배 + 본문 일부
        """
        title = (title or "").strip()
        pieces = [title, title, title]

        if content:
            content = self._clean_content(content.strip())
            if len(content) > 20:
                pieces.append(content[:1200])

        return " ".join([p for p in pieces if p])

    def _extract_simple_nouns(self, text: str) -> List[str]:
        korean_words = re.findall(r"[가-힣]{2,10}", text)
        candidates = []
        for w in korean_words:
            w_clean = self._remove_josa_tail(w)
            if 2 <= len(w_clean) <= 10:
                candidates.append(w_clean)

        seen = set()
        result = []
        for w in candidates:
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result

    # ----------------------- 필터링 ----------------------- #

    def _is_valid_keyword(self, keyword: str, seen: set) -> bool:
        if not keyword:
            return False

        kw = keyword.strip()

        # 길이 제한
        if len(kw) < 2 or len(kw) > 15:
            return False

        # 숫자 포함/혼합 제거 (예: 31억8400, 02gwh 등)
        if re.search(r"\d", kw):
            return False

        # 영문 기본 제거 (tsmc, var 등)
        if not self.allow_english and re.search(r"[A-Za-z]", kw):
            return False

        # JS 노이즈 제거
        if kw.lower() in self.js_noise:
            return False

        # stopword 제거
        if kw in self.stopwords:
            return False

        # 너무 흔한 접미 형태(…했다/…한다 같은 동사형) 대충 컷
        if kw.endswith("했다") or kw.endswith("한다") or kw.endswith("됐다") or kw.endswith("된다"):
            return False

        # 중복 제거
        if kw.lower() in seen:
            return False

        return True

    # ----------------------- 메인 ----------------------- #

    def extract_from_article(
        self,
        title: str,
        content: Optional[str] = None,
        top_n: Optional[int] = None,
        with_scores: bool = False,
        candidate_multiplier: int = 6,
    ):
        """
        단일 기사에서 키워드 추출
        - candidate_multiplier: top_n * multiplier 만큼 후보를 먼저 뽑아 필터링 후 top_n으로 자름
        """
        if top_n is None:
            top_n = self.top_n

        text = self._build_input_text(title, content)

        try:
            raw_keywords = self.keybert.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 1),
                stop_words=list(self.stopwords),
                use_mmr=True,
                diversity=0.35,
                top_n=max(top_n * candidate_multiplier, 50),
            )

            cleaned: List[Tuple[str, float]] = []
            seen = set()

            for kw, score in raw_keywords:
                kw = (kw or "").strip()
                kw_clean = self._remove_josa_tail(kw)

                if self._is_valid_keyword(kw_clean, seen):
                    cleaned.append((kw_clean, float(score)))
                    seen.add(kw_clean.lower())

                if len(cleaned) >= top_n:
                    break

            # fallback
            if len(cleaned) < top_n:
                simple_nouns = self._extract_simple_nouns(text)
                for noun in simple_nouns:
                    if noun.lower() in seen:
                        continue
                    if noun in self.stopwords:
                        continue
                    if not self.allow_english and re.search(r"[A-Za-z]", noun):
                        continue
                    if re.search(r"\d", noun):
                        continue

                    cleaned.append((noun, 0.0))
                    seen.add(noun.lower())
                    if len(cleaned) >= top_n:
                        break

            cleaned = cleaned[:top_n]
            return cleaned if with_scores else [k for k, _ in cleaned]

        except Exception as e:
            print(f"키워드 추출 오류: {e}")
            fallback = self._extract_simple_nouns(text)[:top_n]
            return [(k, 0.0) for k in fallback] if with_scores else fallback


if __name__ == "__main__":
    extractor = KoNewsKeywordExtractor(top_n=20, allow_english=False)

    title = "TSMC 점유율 71% 독주...삼성전자와 격차 벌려"
    content = "본문 예시..."
    kws = extractor.extract_from_article(title, content, top_n=20, with_scores=True)
    for kw, score in kws:
        print(f"{kw}\t{score:.4f}")
