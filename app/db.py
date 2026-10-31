"""SQLite 기록 (data/agent.db): 게시 기록(posts) + 모의 시청 페이지의 댓글(mock_comments)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import DATA_DIR, DB_PATH

KST = timezone(timedelta(hours=9))

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,           -- KST ISO 시각 (앞 10자리 = KST 날짜)
    video_id    TEXT NOT NULL,
    title       TEXT,
    profile     TEXT,
    comment     TEXT,
    status      TEXT NOT NULL,           -- 성공 | 실패
    reason      TEXT,
    screenshot  TEXT,
    comment_url TEXT
);
-- 영상당 성공 댓글 1개
CREATE UNIQUE INDEX IF NOT EXISTS one_success_per_video ON posts(video_id) WHERE status = '성공';

CREATE TABLE IF NOT EXISTS mock_comments (
    id          TEXT PRIMARY KEY,
    video_id    TEXT NOT NULL,
    author      TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""

LOG_COLUMNS = ["created_at", "video_id", "title", "profile", "comment", "status", "reason", "screenshot", "comment_url"]


def now_kst() -> datetime:
    return datetime.now(KST)


@contextmanager
def connect():
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with connect() as con:
        con.executescript(SCHEMA)


def previous_comments(limit: int = 200) -> list[str]:
    with connect() as con:
        rows = con.execute("SELECT comment FROM posts WHERE status='성공' ORDER BY id DESC LIMIT ?", (limit,))
        return [r["comment"] for r in rows if r["comment"]]


def add_post(video_id: str, title: str, profile: str, comment: str, status: str,
             reason: str | None = None, screenshot: str | None = None, comment_url: str | None = None) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO posts(created_at, video_id, title, profile, comment, status, reason, screenshot, comment_url)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (now_kst().isoformat(timespec="seconds"), video_id, title, profile, comment, status,
             reason, screenshot, comment_url))


# ── 운영 규칙용 조회 ──
def today_success_count() -> int:
    with connect() as con:
        (n,) = con.execute("SELECT COUNT(*) FROM posts WHERE status='성공' AND substr(created_at,1,10)=?",
                           (now_kst().date().isoformat(),)).fetchone()
    return n


def commented_video_ids() -> set[str]:
    with connect() as con:
        return {r[0] for r in con.execute("SELECT video_id FROM posts WHERE status='성공'")}


def video_profiles(video_id: str) -> list[str]:
    """이 영상에 시도했던 프로필 (한 영상에는 계정 하나만)."""
    with connect() as con:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT profile FROM posts WHERE video_id=? AND profile IS NOT NULL", (video_id,))]


def last_profile() -> str | None:
    with connect() as con:
        row = con.execute("SELECT profile FROM posts ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def recent_posts(limit: int | None = 200) -> list[dict]:
    sql = f"SELECT {', '.join(LOG_COLUMNS)} FROM posts ORDER BY id DESC"
    with connect() as con:
        rows = con.execute(sql + " LIMIT ?", (limit,)) if limit else con.execute(sql)
        return [dict(r) for r in rows]


# ── 모의 시청 페이지용 ──
def mock_add_comment(cid: str, video_id: str, author: str, text: str) -> None:
    with connect() as con:
        con.execute("INSERT INTO mock_comments VALUES (?,?,?,?,?)",
                    (cid, video_id, author, text, now_kst().isoformat(timespec="seconds")))


def mock_comments(video_id: str) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT * FROM mock_comments WHERE video_id=? ORDER BY created_at DESC", (video_id,))
        return [dict(r) for r in rows]
