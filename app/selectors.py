"""
게시 자동화에 쓰는 셀렉터 모음. 화면 구조가 바뀌면 이 파일만 고친다.
각 항목은 우선순위 순서의 후보 목록: ID 기반 → 한국어 UI 텍스트 기반 대체.
"""

COMMENTS_SECTION = ["ytd-comments#comments", "#comments"]
PLACEHOLDER = ["#simplebox-placeholder", "text=댓글 추가..."]
EDITOR = ["#contenteditable-root[contenteditable='true']", "[contenteditable='true'][aria-label*='댓글 추가']"]
SUBMIT = ["#submit-button", "button[aria-label='댓글']", "ytd-comment-simplebox-renderer button:text-is('댓글')"]
CURRENT_ACCOUNT = ["#account-name[data-current-account]"]

THREAD = "ytd-comment-thread-renderer"
THREAD_TEXT = "#content-text"
THREAD_AUTHOR = "#author-text"
THREAD_LINK = "#published-time-text a"
