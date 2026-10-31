"""
오프라인 시연용 모의 시청 페이지 (/mock/watch?v=ID).
- 댓글 영역의 DOM 구조/ID 는 실제 유튜브와 같게 만들어 poster.py 가 같은 셀렉터로 동작하게 한다.
- '로그인 상태'는 크롬 프로필에 저장되는 쿠키(mock_account)로 흉내 낸다.
- 댓글은 data/agent.db 의 mock_comments 에 저장된다. 실제 유튜브에는 아무것도 보내지 않는다.
"""
import html
import re
import secrets
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import db, youtube_api

router = APIRouter(prefix="/mock")
_video_cache: dict[str, dict] = {}


def _video(vid: str) -> dict:
    if vid not in _video_cache:
        try:
            _video_cache[vid] = youtube_api.get_video(vid)
        except Exception:  # 키 없음/오프라인이어도 페이지는 뜨게 (임시값은 캐시하지 않아 다음에 다시 시도)
            return {"id": vid, "title": f"영상 {vid}", "channel": "", "thumbnail": "", "description": ""}
    return _video_cache[vid]


def _thread(c: dict, highlight: str | None) -> str:
    e = html.escape
    cls = ' class="highlighted"' if c["id"] == highlight else ""
    return f"""
<ytd-comment-thread-renderer data-comment-id="{e(c['id'])}"{cls}>
  <div class="avatar">{e(c['author'][1:2])}</div>
  <div class="body">
    <div class="header"><a id="author-text" href="#">{e(c['author'])}</a>
      <span id="published-time-text"><a href="/mock/watch?v={e(c['video_id'])}&lc={e(c['id'])}">{e(c['created_at'][5:16].replace('T', ' '))}</a></span>
      {'<span class="pin">고정된 댓글로 연결됨</span>' if cls else ''}</div>
    <div id="content-text">{e(c['text'])}</div>
  </div>
</ytd-comment-thread-renderer>"""


@router.get("/watch", response_class=HTMLResponse)
def watch(request: Request, v: str, lc: str | None = None):
    e = html.escape
    if not re.fullmatch(r"[\w-]{11}", v):
        raise HTTPException(400, "잘못된 영상 ID")
    video = _video(v)
    account = unquote(request.cookies.get("mock_account", ""))
    comments = db.mock_comments(v)
    if lc:  # &lc= 로 열면 해당 댓글을 맨 위에 강조 (유튜브 동작과 같게)
        comments.sort(key=lambda c: c["id"] != lc)
    threads = "".join(_thread(c, lc) for c in comments)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>{e(video['title'])} - 모의 시청 페이지</title>
<style>
 body{{margin:0;font-family:"Malgun Gothic",sans-serif;background:#fff;color:#0f0f0f}}
 #masthead{{position:sticky;top:0;display:flex;align-items:center;gap:12px;padding:10px 24px;background:#fff;border-bottom:1px solid #eee;z-index:5}}
 .logo{{font-weight:800}} .notice{{background:#fde68a;font-size:12px;padding:2px 8px;border-radius:10px}}
 #account-name{{margin-left:auto;font-size:13px;color:#555}}
 main{{max-width:860px;margin:0 auto;padding:16px 24px 200px}}
 #player{{background:#000;border-radius:12px;aspect-ratio:16/9;display:grid;place-items:center;overflow:hidden}}
 #player img{{width:100%;height:100%;object-fit:cover;opacity:.85}}
 h1{{font-size:20px;margin:12px 0 4px}} #owner{{color:#606060;font-size:14px}}
 #description{{background:#f2f2f2;border-radius:12px;padding:12px;margin:12px 0;white-space:pre-wrap;font-size:13px;min-height:420px}}
 ytd-comments,ytd-comment-simplebox-renderer,ytd-comment-thread-renderer{{display:block}}
 #count{{font-size:18px;margin:24px 0 16px}}
 ytd-comment-simplebox-renderer{{display:flex;gap:12px;margin-bottom:24px}}
 #simplebox-placeholder{{flex:1;border-bottom:1px solid #ccc;padding:6px 0;color:#606060;cursor:text}}
 #editor{{flex:1}} #contenteditable-root{{border-bottom:2px solid #0f0f0f;padding:6px 0;min-height:22px;outline:none}}
 #buttons{{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}}
 #buttons button{{border:0;border-radius:18px;padding:8px 16px;font:inherit;cursor:pointer;background:#f2f2f2}}
 #submit-button:not([disabled]){{background:#065fd4;color:#fff}}
 ytd-comment-thread-renderer{{display:flex;gap:12px;margin-bottom:20px;padding:6px;border-radius:8px}}
 ytd-comment-thread-renderer.highlighted{{background:#eef4ff}}
 .avatar{{width:40px;height:40px;border-radius:50%;background:#c4b5fd;display:grid;place-items:center;color:#fff;font-weight:700;flex:none}}
 #author-text{{font-weight:600;font-size:13px;color:#0f0f0f;text-decoration:none}}
 #published-time-text a{{color:#606060;font-size:12px;margin-left:6px;text-decoration:none}}
 .pin{{font-size:11px;color:#065fd4;margin-left:6px}} #content-text{{margin-top:4px;line-height:1.5;white-space:pre-wrap}}
</style></head><body>
<div id="masthead"><span class="logo">▶ 모의 시청 페이지</span><span class="notice">오프라인 시연용 · 실제 유튜브가 아닙니다</span>
  <div id="account-name" data-current-account="{e(account)}">{e(account) if account else '로그인 안 됨'}</div></div>
<main>
  <div id="player">{f'<img src="{e(video["thumbnail"])}" alt="">' if video['thumbnail'] else ''}</div>
  <h1 id="title">{e(video['title'])}</h1><div id="owner">{e(video['channel'])}</div>
  <div id="description">{e(video['description'][:1500])}</div>
  <ytd-comments id="comments">
    <h2 id="count">댓글 {len(comments)}개</h2>
    <ytd-comment-simplebox-renderer>
      <div class="avatar">{e(account[1:2]) if account else '?'}</div>
      <div id="simplebox-placeholder" tabindex="0">댓글 추가...</div>
      <div id="editor" hidden>
        <div id="contenteditable-root" contenteditable="true" aria-label="댓글 추가..."></div>
        <div id="buttons"><button id="cancel-button">취소</button><button id="submit-button" aria-label="댓글" disabled>댓글</button></div>
      </div>
    </ytd-comment-simplebox-renderer>
    <div id="contents">{threads}</div>
  </ytd-comments>
</main>
<script>
const ph = document.getElementById('simplebox-placeholder'), ed = document.getElementById('editor'),
      root = document.getElementById('contenteditable-root'), sub = document.getElementById('submit-button');
ph.onclick = () => {{ ph.hidden = true; ed.hidden = false; root.focus(); }};
root.addEventListener('input', () => sub.disabled = !root.innerText.trim());
document.getElementById('cancel-button').onclick = () => {{ root.innerText = ''; ed.hidden = true; ph.hidden = false; sub.disabled = true; }};
sub.onclick = async () => {{
  sub.disabled = true;
  await new Promise(r => setTimeout(r, 800));   // 서버 처리 지연 흉내
  const r = await fetch('/mock/api/comments', {{method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{video_id: {v!r}, text: root.innerText.trim()}})}});
  if (!r.ok) {{ alert((await r.json()).detail); sub.disabled = false; return; }}
  const d = await r.json();
  document.getElementById('contents').insertAdjacentHTML('afterbegin', d.html);
  root.innerText = ''; ed.hidden = true; ph.hidden = false;
}};
</script></body></html>"""


class MockCommentIn(BaseModel):
    video_id: str
    text: str


@router.post("/api/comments")
def add_comment(req: Request, body: MockCommentIn):
    account = unquote(req.cookies.get("mock_account", ""))
    if not account:
        raise HTTPException(401, "로그인이 필요합니다.")
    if not body.text.strip():
        raise HTTPException(400, "빈 댓글")
    cid = "Ugx" + secrets.token_urlsafe(12)
    db.mock_add_comment(cid, body.video_id, account, body.text.strip())
    c = {"id": cid, "video_id": body.video_id, "author": account, "text": body.text.strip(),
         "created_at": db.now_kst().isoformat(timespec="seconds")}
    return {"id": cid, "html": _thread(c, None)}
