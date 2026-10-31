"""3단계 검증(코드): 글자수 / 브랜드 포함 / URL·# 없음 / 이용후기 패턴 없음 / 이전 댓글과 유사도."""
import re
from difflib import SequenceMatcher

from .config import settings

URL_RE = re.compile(r"https?://|www\.|\.com\b|\.kr\b|\.net\b|bit\.ly", re.I)
REVIEW_RE = re.compile(r"(봤는데|봤더니|봤어요|받았는데|받아봤|받아보니|상담\s*받|해봤는데|해보니|다녀왔|후기|소름|찐이|맞더라|맞췄)")
SIMILARITY_MAX = 0.6


def validate(text: str, previous: list[str]) -> list[str]:
    """탈락 사유 목록. 빈 목록이면 통과."""
    c = settings["comment"]
    text = (text or "").strip()
    fails = []
    n = len(text)
    if not c["min_chars"] <= n <= c["max_chars"]:
        fails.append(f"글자수 {n}자 (허용 {c['min_chars']}~{c['max_chars']}자)")
    if c["brand"] not in text:
        fails.append(f"'{c['brand']}' 미포함")
    if URL_RE.search(text):
        fails.append("링크 포함")
    if "#" in text:
        fails.append("해시태그 포함")
    m = REVIEW_RE.search(text)
    if m:
        fails.append(f"이용후기처럼 보이는 표현: '{m.group(0)}'")
    for p in previous:
        r = SequenceMatcher(None, text, p).ratio()
        if r >= SIMILARITY_MAX:
            fails.append(f"이전 댓글과 너무 비슷함 (유사도 {r:.0%})")
            break
    return fails
