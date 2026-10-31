"""YouTube Data API v3: 영상 검색, 상세 정보, 인기 댓글, 링크 파싱."""
import re
from datetime import datetime, timedelta, timezone

import httpx

from .config import env, settings

API = "https://www.googleapis.com/youtube/v3"


class YouTubeError(RuntimeError):
    pass


def _get(path: str, **params) -> dict:
    params["key"] = env("YOUTUBE_API_KEY")
    r = httpx.get(f"{API}/{path}", params=params, timeout=20)
    if r.status_code != 200:
        try:
            err = r.json()["error"]
            reason = (err.get("errors") or [{}])[0].get("reason", "")
            msg = f"{err.get('message', '')} ({reason})"
        except Exception:
            msg = r.text[:200]
        raise YouTubeError(f"YouTube API 오류 {r.status_code}: {msg}")
    return r.json()


def parse_video_id(text: str) -> str:
    """watch?v=, youtu.be/, shorts/, live/, embed/ 링크 또는 11자리 ID."""
    text = (text or "").strip()
    if re.fullmatch(r"[\w-]{11}", text):
        return text
    for pat in (r"[?&]v=([\w-]{11})", r"youtu\.be/([\w-]{11})", r"/shorts/([\w-]{11})",
                r"/live/([\w-]{11})", r"/embed/([\w-]{11})"):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    raise ValueError("유튜브 링크에서 영상 ID를 찾지 못했습니다.")


def _to_item(v: dict) -> dict:
    sn, st = v["snippet"], v.get("statistics", {})
    thumbs = sn.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url", "")
    views = int(st.get("viewCount", 0) or 0)
    age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))).total_seconds() / 3600
    return {
        "id": v["id"],
        "title": sn["title"],
        "channel": sn["channelTitle"],
        "channel_id": sn["channelId"],
        "published_at": sn["publishedAt"],
        "description": sn.get("description", ""),
        "thumbnail": thumb,
        "views": views,
        "views_per_hour": round(views / max(age_h, 0.1), 1),
        "comments_disabled": "commentCount" not in st,
    }


def get_videos(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    data = _get("videos", part="snippet,statistics", id=",".join(ids[:50]))
    by_id = {v["id"]: _to_item(v) for v in data.get("items", [])}
    return [by_id[i] for i in ids if i in by_id]


def get_video(video_id: str) -> dict:
    items = get_videos([video_id])
    if not items:
        raise ValueError(f"영상을 찾을 수 없습니다 (비공개/삭제/잘못된 ID): {video_id}")
    return items[0]


def search_rising() -> list[dict]:
    """뜨기 직전 영상: 최근 N시간 업로드 중 조회수 범위 + 시간당 조회수 기준 통과, 시간당 조회수 높은 순."""
    r = settings["rising"]
    # 조회수순은 이미 뜬 영상만 잡히므로, 최신순으로 여러 페이지(페이지당 할당량 100)를 훑어 거른다
    videos = search_videos(hours=r["hours"], max_results=50, pages=r.get("pages", 3))
    hits = [v for v in videos
            if r["min_views"] <= v["views"] <= r["max_views"] and v["views_per_hour"] >= r["min_views_per_hour"]]
    return sorted(hits, key=lambda v: v["views_per_hour"], reverse=True)


def search_videos(hours: int | None = None, max_results: int | None = None, order: str = "date",
                  pages: int = 1) -> list[dict]:
    """설정의 검색어로 검색 (기본 최신순). hours 를 주면 최근 N시간 업로드만. pages 만큼 다음 페이지를 이어 받는다."""
    s = settings["search"]
    params = dict(part="snippet", type="video", q=s["query"], order=order,
                  regionCode=s["region"], relevanceLanguage=s["language"],
                  maxResults=min(max_results or s["max_results"], 50))
    if hours:
        after = datetime.now(timezone.utc) - timedelta(hours=hours)
        params["publishedAfter"] = after.strftime("%Y-%m-%dT%H:%M:%SZ")
    videos = []
    for _ in range(pages):
        data = _get("search", **params)
        ids = [it["id"]["videoId"] for it in data.get("items", []) if it["id"].get("videoId")]
        videos += get_videos(ids)
        if not data.get("nextPageToken"):
            break
        params["pageToken"] = data["nextPageToken"]
    return videos


def top_comments(video_id: str, n: int = 20) -> list[str]:
    """인기순 상위 댓글 본문. 댓글이 막힌 영상이면 빈 목록."""
    try:
        data = _get("commentThreads", part="snippet", videoId=video_id, order="relevance",
                    maxResults=n, textFormat="plainText")
    except YouTubeError as e:
        if "commentsDisabled" in str(e):
            return []
        raise
    return [it["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for it in data.get("items", [])]
