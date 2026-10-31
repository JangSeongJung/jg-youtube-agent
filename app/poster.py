"""
③ 게시 자동화 (Playwright, 화면에 보이는 크롬).
흐름: 프로필 열기 → 영상 열기 → 댓글창으로 스크롤 → 입력창 클릭 → 한 글자씩 입력 → 게시 → 내 댓글 확인
진행 상태는 jobs[job_id] 에 기록하고, 대시보드가 1초마다 /api/post/{job_id} 로 읽어간다.
오프라인 시연판: 대상 URL 은 로컬 모의 시청 페이지(/mock/watch)로 고정.
"""
import random
import re
import threading
import time
import uuid
from urllib.parse import quote

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from . import db
from . import selectors as S
from .config import SCREENSHOT_DIR, get_profile, profile_in_use, settings

BASE = "http://127.0.0.1:8000"
STEPS = ["프로필 여는 중", "영상 여는 중", "댓글창 찾는 중", "입력 중", "게시 중", "내 댓글 확인 중", "게시 완료"]

jobs: dict[str, dict] = {}
_busy = threading.Lock()   # 동시에 한 건만 (같은 PC에서 크롬 창 여러 개가 엉키지 않게)


class PostError(Exception):
    pass


class _Fail(Exception):
    """브라우저 단계 실패: 사유 + 스크린샷 파일명."""
    def __init__(self, reason: str, shot: str | None):
        self.reason, self.shot = reason, shot


def account_of(profile_name: str) -> str:
    """모의 페이지에서 이 프로필이 로그인된 계정 이름."""
    return "@" + profile_name


def assign_profile(video_id: str | None = None) -> str:
    """자동 배정: 이 영상에 쓴 계정이 있으면 그 계정, 없으면 마지막 사용 계정의 다음 차례(창이 열린 프로필은 건너뜀)."""
    if video_id:
        used = db.video_profiles(video_id)
        if used:
            return used[0]
    names = [p["name"] for p in settings["profiles"]]
    last = db.last_profile()
    start_i = (names.index(last) + 1) % len(names) if last in names else 0
    order = names[start_i:] + names[:start_i]
    for n in order:
        if not profile_in_use(get_profile(n)["dir"]):
            return n
    return order[0]


def blocked_reason(video: dict, profile_name: str | None) -> str | None:
    """운영 규칙 검사. 게시할 수 없으면 사유, 가능하면 None. (UI 가 아니라 여기서 강제)"""
    vid = video["id"]
    if any(j["video_id"] == vid and j["status"] == "running" for j in jobs.values()):
        return "이 영상에 댓글을 게시하는 중입니다."
    if vid in db.commented_video_ids():
        return "이미 댓글을 단 영상입니다. (영상당 1개)"
    used = db.video_profiles(vid)
    if profile_name and used and profile_name not in used:
        return f"이 영상은 '{used[0]}' 계정으로 시도한 적이 있습니다. (한 영상에는 계정 하나만)"
    limit = settings["limits"]["daily_max_comments"]
    if db.today_success_count() >= limit:
        return f"오늘 게시 상한 {limit}건에 도달했습니다. (KST 자정에 초기화)"
    allowed = settings.get("allowed_channel_ids") or []
    if allowed and video["channel_id"] not in allowed:
        return f"허용 채널 목록에 없는 채널입니다: {video['channel']}"
    return None


def start(video: dict, text: str, profile_name: str | None) -> tuple[str, str]:
    """게시 작업 시작. (job_id, 배정된 프로필) 반환. 규칙 위반이면 PostError."""
    if not _busy.acquire(blocking=False):
        raise PostError("다른 댓글을 게시하는 중입니다. 끝난 뒤 다시 시도하세요.")
    try:
        profile_name = profile_name or assign_profile(video["id"])
        reason = blocked_reason(video, profile_name)
        if reason:
            raise PostError(reason)
    except Exception:
        _busy.release()
        raise
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"id": job_id, "video_id": video["id"], "profile": profile_name, "step": STEPS[0],
                    "step_index": 0, "typed": 0, "total": len(text), "status": "running",
                    "reason": None, "screenshot": None, "comment_url": None}
    threading.Thread(target=_run, args=(job_id, video, text, profile_name), daemon=True).start()
    return job_id, profile_name


def _set(job: dict, step: str, **kw):
    job.update(step=step, step_index=STEPS.index(step), **kw)


def _find(page, candidates: list[str], timeout_ms: int = 8000):
    """후보 셀렉터를 순서대로 시도해 처음 보이는 요소를 반환."""
    per = max(timeout_ms // len(candidates), 1000)
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=per)
            return loc
        except PWTimeout:
            continue
    raise PostError(f"화면 요소를 찾지 못했습니다: {candidates[0]}")


def _screenshot(page, video_id: str) -> str | None:
    if page is None:
        return None
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{db.now_kst():%Y%m%d_%H%M%S}_{video_id}.png"
    try:
        page.screenshot(path=str(SCREENSHOT_DIR / name))
        return name
    except PWError:
        return None


def _run(job_id: str, video: dict, text: str, profile_name: str):
    job = jobs[job_id]
    cfg = settings["posting"]
    lo, hi = cfg["typing_delay_ms"]
    page = None
    try:
        prof = get_profile(profile_name)
        if profile_in_use(prof["dir"]):
            raise PostError(f"'{profile_name}' 프로필 크롬 창이 이미 열려 있습니다. 해당 창을 닫아주세요.")

        with sync_playwright() as p:
            try:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=prof["dir"], executable_path=settings["chrome_path"], headless=False,
                    locale="ko-KR", viewport={"width": 1280, "height": 860},
                    args=["--no-first-run", "--no-default-browser-check"])
            except PWError as e:
                raise PostError(f"크롬을 열지 못했습니다. '{profile_name}' 프로필 창이 열려 있으면 닫아주세요. ({str(e).splitlines()[0]})")
            try:
                # 모의 페이지의 '로그인 상태' (프로필 폴더에 쿠키로 저장됨)
                me = account_of(profile_name)
                ctx.add_cookies([{"name": "mock_account", "value": quote(me), "url": BASE}])
                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                _set(job, "영상 여는 중")
                page.goto(f"{BASE}/mock/watch?v={video['id']}&hl=ko", wait_until="domcontentloaded", timeout=20000)

                _set(job, "댓글창 찾는 중")
                section = page.locator(S.COMMENTS_SECTION[0])
                section.scroll_into_view_if_needed(timeout=10000)
                page.mouse.wheel(0, 300)
                _find(page, S.PLACEHOLDER).click()
                editor = _find(page, S.EDITOR)
                editor.click()
                before = page.locator(S.THREAD).count()

                _set(job, "입력 중")
                for i, ch in enumerate(text, 1):
                    page.keyboard.type(ch)
                    job["typed"] = i
                    time.sleep(random.uniform(lo, hi) / 1000)

                _set(job, "게시 중")
                _find(page, S.SUBMIT).click()

                _set(job, "내 댓글 확인 중")
                current = page.locator(S.CURRENT_ACCOUNT[0]).get_attribute("data-current-account")
                page.wait_for_function(f"document.querySelectorAll('{S.THREAD}').length > {before}", timeout=15000)
                thread = page.locator(S.THREAD).first
                got_text = thread.locator(S.THREAD_TEXT).inner_text().strip()
                got_author = thread.locator(S.THREAD_AUTHOR).inner_text().strip()
                # 입력창이 공백 일부를 nbsp 로 바꾸고 줄 끝 공백을 다르게 남기므로, 공백 차이는 무시하고 비교
                if " ".join(got_text.split()) != " ".join(text.split()):
                    raise PostError("새 댓글 본문이 입력한 내용과 다릅니다.")
                if got_author != current:
                    raise PostError(f"새 댓글 작성자({got_author})가 현재 계정({current})이 아닙니다.")
                href = thread.locator(S.THREAD_LINK).get_attribute("href") or ""
                m = re.search(r"lc=([\w-]+)", href)
                url = f"{BASE}/mock/watch?v={video['id']}&lc={m.group(1)}" if m else None
                thread.scroll_into_view_if_needed()

                _set(job, "게시 완료", status="success", comment_url=url)
                db.add_post(video["id"], video["title"], profile_name, text, "성공", comment_url=url)
                time.sleep(cfg["close_after_sec"])   # 시연 영상에서 확인 화면이 보이도록
            except (PostError, PWError) as e:
                shot = _screenshot(page, video["id"])
                reason = str(e).splitlines()[0] if isinstance(e, PWError) else str(e)
                if isinstance(e, PWTimeout):
                    reason = f"시간 초과: {reason}"
                raise _Fail(reason, shot) from e
            finally:
                ctx.close()
    except _Fail as f:
        _fail(job, video, text, profile_name, f.reason, f.shot)
    except PostError as e:
        _fail(job, video, text, profile_name, str(e), None)
    except Exception as e:  # 예상 못한 오류도 화면에 남긴다
        _fail(job, video, text, profile_name, f"예상 못한 오류: {type(e).__name__}: {e}", None)
        raise
    finally:
        _busy.release()


def _fail(job, video, text, profile_name, reason, shot):
    job.update(status="failed", reason=f"[{job['step']}] {reason}", screenshot=shot)
    db.add_post(video["id"], video["title"], profile_name, text, "실패", reason=job["reason"], screenshot=shot)
