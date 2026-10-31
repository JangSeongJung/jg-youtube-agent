"""자막 가져오기: 한국어 수동 자막 → 한국어 자동생성 → 없으면 None (호출측에서 제목·설명으로 대체)."""
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

# 아주 긴 영상의 비용을 막기 위한 상한 (약 30분 분량). 잘린 경우 truncated 로 표시한다.
MAX_CHARS = 15000


def get_transcript(video_id: str) -> dict:
    """{"text": str|None, "source": "ko 자막"|"ko 자동생성"|"없음", "truncated": bool}"""
    try:
        tlist = YouTubeTranscriptApi().list(video_id)
    except CouldNotRetrieveTranscript:
        return {"text": None, "source": "없음", "truncated": False}

    for finder, label in ((tlist.find_manually_created_transcript, "ko 자막"),
                          (tlist.find_generated_transcript, "ko 자동생성")):
        try:
            fetched = finder(["ko"]).fetch()
        except CouldNotRetrieveTranscript:
            continue
        text = " ".join(s.text.replace("\n", " ") for s in fetched).strip()
        if text:
            return {"text": text[:MAX_CHARS], "source": label, "truncated": len(text) > MAX_CHARS}
    return {"text": None, "source": "없음", "truncated": False}
