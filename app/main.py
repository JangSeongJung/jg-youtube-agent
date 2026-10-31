"""FastAPI 진입점. 실행: run.bat (uvicorn app.main:app --host 127.0.0.1 --port 8000)"""
import csv
import io
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import comment_rules, db, llm, mock_youtube, poster, youtube_api
from .config import ROOT, SCREENSHOT_DIR, settings
from .transcript import get_transcript

app = FastAPI(title="유튜브 댓글 에이전트")
app.include_router(mock_youtube.router)
db.init()

MAX_TRIES = 3


def _wrap(fn, *a, **kw):
    """외부 API 오류를 화면에 보여줄 메시지로 바꾼다."""
    try:
        return fn(*a, **kw)
    except (youtube_api.YouTubeError, llm.LLMError) as e:
        raise HTTPException(502, str(e))
    except (RuntimeError, ValueError) as e:  # .env 키 없음, 잘못된 링크 등
        raise HTTPException(400, str(e))


def _mark(videos: list[dict]) -> list[dict]:
    done = db.commented_video_ids()
    for v in videos:
        v["already_commented"] = v["id"] in done
    return videos


@app.get("/")
def index():
    # 화면을 고친 뒤 브라우저가 옛 화면을 보여주지 않도록 캐시하지 않음
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/info")
def info():
    return {"keys": {k: bool(os.getenv(k, "").strip()) for k in ("YOUTUBE_API_KEY", "ANTHROPIC_API_KEY")},
            "profiles": [p["name"] for p in settings["profiles"]],
            "assignment": settings["profile_assignment"],
            "next_profile": poster.assign_profile(),
            "comment": settings["comment"], "search": settings["search"], "rising": settings["rising"],
            "model": settings["llm"]["model"],
            "today_count": db.today_success_count(), "daily_max": settings["limits"]["daily_max_comments"],
            "allowed_channels": len(settings.get("allowed_channel_ids") or [])}


@app.get("/api/videos")
def videos():
    return _mark(_wrap(youtube_api.search_videos))


@app.get("/api/rising")
def rising():
    """뜨기 직전 영상: 목록 + (선택 시) 초안까지만. 자동 게시하지 않는다."""
    return _mark(_wrap(youtube_api.search_rising))


class DraftReq(BaseModel):
    video: str                     # 영상 ID 또는 링크
    analysis: dict | None = None   # 재생성 시 기존 분석 재사용


@app.post("/api/draft")
def draft(req: DraftReq):
    vid = _wrap(youtube_api.parse_video_id, req.video)
    video = _mark([_wrap(youtube_api.get_video, vid)])[0]

    analysis, tr = req.analysis, None
    if not analysis:
        tr = get_transcript(vid)
        comments = _wrap(youtube_api.top_comments, vid)
        analysis = _wrap(llm.analyze, video, tr["text"], comments)

    previous = db.previous_comments()
    attempts, feedback = [], None
    for _ in range(MAX_TRIES):
        text = _wrap(llm.write_comment, video, analysis, feedback)
        fails = comment_rules.validate(text, previous)
        attempts.append({"text": text, "fails": fails})
        if not fails:
            break
        feedback = fails

    source = None
    if tr:
        source = tr["source"] + (" (앞부분)" if tr["truncated"] else "")
    return {"video": video, "analysis": analysis, "transcript_source": source,
            "comment": attempts[-1]["text"], "passed": not attempts[-1]["fails"], "attempts": attempts}


class CheckReq(BaseModel):
    text: str


@app.post("/api/check")
def check(req: CheckReq):
    """사용자가 직접 고친 초안을 같은 규칙으로 검사."""
    return {"fails": comment_rules.validate(req.text, db.previous_comments())}


@app.get("/api/can_post")
def can_post(video_id: str, profile: str | None = None):
    """[댓글 달기] 버튼 활성화용. 실제 강제는 /api/post 에서 다시 한다."""
    video = _wrap(youtube_api.get_video, video_id)
    assigned = profile or poster.assign_profile(video_id)
    return {"reason": poster.blocked_reason(video, assigned), "profile": assigned,
            "today_count": db.today_success_count(), "daily_max": settings["limits"]["daily_max_comments"]}


class PostReq(BaseModel):
    video_id: str
    text: str
    profile: str | None = None     # None = 자동 순환 배정


@app.post("/api/post")
def post(req: PostReq):
    video = _wrap(youtube_api.get_video, req.video_id)
    fails = comment_rules.validate(req.text, db.previous_comments())
    if fails:
        raise HTTPException(400, "규칙 위반으로 게시할 수 없습니다: " + " · ".join(fails))
    if req.profile and req.profile not in [p["name"] for p in settings["profiles"]]:
        raise HTTPException(400, f"없는 프로필: {req.profile}")
    try:
        job_id, profile = poster.start(video, req.text.strip(), req.profile)
    except poster.PostError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job_id, "profile": profile}


@app.get("/api/post/{job_id}")
def post_status(job_id: str):
    job = poster.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return {**job, "steps": poster.STEPS}


@app.get("/api/log")
def log():
    return db.recent_posts(200)


@app.get("/api/log.csv")
def log_csv():
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=db.LOG_COLUMNS)
    w.writerow({"created_at": "시각", "video_id": "영상ID", "title": "영상 제목", "profile": "프로필",
                "comment": "댓글 본문", "status": "상태", "reason": "실패 사유",
                "screenshot": "스크린샷", "comment_url": "댓글 링크"})
    w.writerows(db.recent_posts(None))
    name = f"comment_log_{db.now_kst():%Y%m%d_%H%M}.csv"
    # utf-8-sig: 엑셀에서 한글이 깨지지 않도록 BOM 포함
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/shots", StaticFiles(directory=SCREENSHOT_DIR), name="shots")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
