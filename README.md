# 유튜브 댓글 에이전트 (오프라인 시연판)

제이지그룹 AI PM 과제 TRACK 2 제출물입니다.
'연애' 관련 유튜브 영상을 찾고, AI가 영상 속 연애 고민을 정리해 댓글 초안을 쓰고, 지정한 크롬 프로필이 화면에 보이게 열려 한 글자씩 입력·게시·확인까지 하는 로컬 대시보드입니다.

> **오프라인 시연판 안내**
> 영상 검색·자막·인기 댓글·AI 초안은 실제 YouTube Data API와 LLM으로 동작합니다.
> **게시는 실제 youtube.com이 아니라 이 프로그램이 띄우는 로컬 모의 시청 페이지(`/mock/watch`)에만** 합니다.
> 모의 페이지는 유튜브 댓글창과 같은 구조(입력창·게시 버튼·댓글 스레드·`&lc=` 링크)를 흉내 내어, 브라우저 자동화 흐름 전체를 실제와 같은 방식으로 보여줍니다.

---

## 화면 구성

| 칸 | 하는 일 |
|---|---|
| **STEP 1 영상 고르기** | [영상 불러오기]로 최신 '연애' 영상 목록(썸네일·제목·채널·올린 날짜·조회수). 링크 직접 입력(`watch?v=`, `youtu.be/`, `shorts/`). [뜨기 직전 영상 찾기]로 막 뜨기 시작한 영상만 추리기 |
| **STEP 2 댓글 초안 확인** | 영상을 고르면 바로 분석 → "영상 속 연애 고민 한 줄", AI가 짚은 장면, 댓글 초안. 초안은 직접 고칠 수 있고 [다시 쓰기]·[영상 다시 분석] 가능. 고칠 때마다 규칙 검사 결과 표시 |
| **STEP 3 댓글 달기** | 계정(크롬 프로필) 선택 또는 자동 순환 배정 → 크롬 창이 열리고 한 글자씩 입력 → 게시 → 내 댓글 확인. 진행 단계와 입력 글자 수를 실시간 표시, 실패하면 단계·이유·스크린샷 표시 |
| **게시 기록** | 시각·영상·계정·댓글·상태·사유·댓글 링크·실패 스크린샷. CSV 내보내기(엑셀에서 한글 깨지지 않음) |

---

## 설치

Windows 10/11, Python 3.11 이상, 크롬이 설치돼 있어야 합니다.

```powershell
cd D:\Cowork\jg-youtube-agent
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

`setup.ps1`이 하는 일:
- 프로젝트 안에 `.venv` 가상환경을 만들고 `requirements.txt` 패키지 설치
- pip 캐시와 Playwright 경로를 프로젝트 폴더 안으로 지정 (C 드라이브 용량 절약)
- `.env.example`을 복사해 `.env` 생성

Playwright는 PC에 설치된 크롬을 그대로 쓰므로 별도 브라우저 다운로드가 없습니다. 크롬은 기본 설치 위치에서 자동으로 찾고, 다른 곳에 설치했다면 `config.yaml`의 `chrome_path`에 경로를 넣으세요.

### API 키 넣기 (`.env`)

```
YOUTUBE_API_KEY=...      # Google Cloud 콘솔 → YouTube Data API v3 사용 설정 → 사용자 인증 정보 → API 키
ANTHROPIC_API_KEY=...    # console.anthropic.com → API Keys
```

`.env`는 git에 올라가지 않습니다. 키가 비어 있으면 대시보드 상단에 경고가 뜹니다.

### 크롬 프로필 준비 (선택)

```
scripts\login_profile.bat 유튜브1
```

지정한 프로필 폴더(`profiles\youtube1` 등)로 **일반 크롬**을 열기만 합니다(자동화 아님). 평소 쓰는 기본 크롬 프로필과는 완전히 분리됩니다.
오프라인 시연판에서는 로그인 없이도 게시 시연이 됩니다(모의 페이지가 프로필 이름을 계정으로 씁니다).

---

## 실행

```
run.bat
```

서버(`http://127.0.0.1:8000`)가 뜨고, 준비되면 브라우저가 자동으로 열립니다. 끄려면 검은 창을 닫으세요.

---

## 설정 (`config.yaml`)

| 항목 | 설명 |
|---|---|
| `profiles` | 계정 이름과 크롬 프로필 폴더 (프로젝트 폴더 기준 상대경로) |
| `profile_assignment` | `round_robin`이면 자동 순환 배정 토글이 켜진 채로 시작 |
| `comment` | 글자 수 범위(40~120자), 꼭 들어갈 브랜드명(운명원) |
| `limits.daily_max_comments` | 하루 게시 상한 (KST 날짜 기준 성공 건수) |
| `search` | 검색어·지역·언어·목록 개수 |
| `allowed_channel_ids` | 비어 있으면 제한 없음. 채널 ID를 넣으면 그 채널 영상에만 게시 |
| `rising` | 뜨기 직전 조건: 최근 48시간, 조회 1,000~5,000, 시간당 150회 이상, 검색 페이지 수 |
| `llm` | `provider`(anthropic / openai)와 `model` |
| `posting` | 글자당 입력 지연(60~180ms), 완료 후 창 닫기까지 대기(3초) |

---

## 동작 방식

### 댓글 초안 3단계
1. **분석** — 자막(한국어 → 자동생성 한국어 → 없으면 제목·설명)과 인기 댓글 상위 20개를 LLM에 넣어 "연애 고민 한 줄", 구체적 장면(key moments), 이 영상을 볼 법한 시청자상을 JSON으로 받습니다.
2. **작성** — 그 시청자의 말투로, 장면 하나를 언급하며 운명원에 대해 "궁금하다·보고 싶다" 정도로 끝나는 댓글을 씁니다. 링크·해시태그·이용 후기처럼 꾸민 문장은 금지합니다.
3. **검증(코드)** — 글자 수, 브랜드 포함, URL·`#` 없음, 이용 후기 패턴 없음, 이전 게시 댓글과의 유사도(0.6 이상 탈락). 탈락하면 이유를 붙여 최대 3회 다시 쓰고, 그래도 안 되면 위반 사유를 화면에 보여줍니다.

### 게시 자동화 (Playwright)
`프로필 여는 중 → 영상 여는 중 → 댓글창 찾는 중 → 입력 중(n/N자) → 게시 중 → 내 댓글 확인 중 → 게시 완료`
- 화면에 보이는 크롬(`headless=False`)으로 지정 프로필을 열고, 글자당 60~180ms 랜덤 지연으로 입력합니다.
- 확인 단계: 새로 생긴 댓글 스레드의 본문이 입력한 내용과 같은지(공백 차이 무시), 작성자가 현재 계정인지 검사하고 `&lc=댓글ID` 링크를 만듭니다.
- 셀렉터는 `app/selectors.py`에 모았고, 한국어 UI 문구("댓글 추가...", "댓글") 기반의 대체 셀렉터도 함께 둡니다.
- 실패하면 `data/screenshots/{시각}_{영상ID}.png`를 남기고 실패 단계와 이유를 기록합니다.
- 프로필 크롬 창이 이미 열려 있으면 열기 전에 알려줍니다.

### 운영 규칙 (화면이 아니라 서버에서 강제)
- **영상당 댓글 1개** — 성공 기록이 있거나 게시 중인 영상은 거부 (DB 고유 제약 + 진행 중 잠금)
- **한 영상에는 계정 하나** — 그 영상에 쓴 적 있는 계정만 다시 시도 가능
- **하루 상한** — KST 날짜 기준 성공 건수, 도달하면 버튼 비활성화 + 사유 표시
- **허용 채널** — 목록이 있으면 그 밖의 채널은 거부
- **동시 게시 1건**

---

## 폴더 구조

```
jg-youtube-agent/
  app/
    main.py            API 엔드포인트
    youtube_api.py     검색·영상 정보·인기 댓글·링크 파싱·뜨기 직전 영상
    transcript.py      자막 가져오기
    llm.py             분석·댓글 작성 (Anthropic / OpenAI 선택)
    comment_rules.py   댓글 검증 규칙
    poster.py          Playwright 게시 자동화 + 운영 규칙 + 계정 배정
    selectors.py       댓글창 셀렉터 모음
    mock_youtube.py    오프라인 시연용 모의 시청 페이지
    db.py              SQLite 기록
    config.py          설정·.env 읽기
  static/              index.html, app.js, style.css
  scripts/             setup.ps1, login_profile.py/.bat, open_when_ready.py
  data/                agent.db, screenshots/   (git 제외)
  profiles/            크롬 프로필             (git 제외)
  config.yaml, .env.example, requirements.txt, run.bat
```

---

## 제작 의도

처음부터 정해둔 원칙은 하나였습니다. 게시 버튼은 사람이 누른다는 것. AI는 영상을 보고 댓글 초안을 쓰는 데까지만 하고, 올릴지 말지는 사람이 보고 정합니다. 뜨기 직전 영상을 찾는 기능도 후보 목록과 초안만 만들어 두고, 자동으로 올리지는 않습니다.

규칙은 프롬프트가 아니라 코드에 넣었습니다. 같은 지시를 줘도 AI는 매번 조금씩 다르게 답하니, 프롬프트에만 적어두면 언젠가는 어긋날 거라고 봤기 때문입니다. 글자 수, 금지 표현, 이전 댓글과의 유사도 같은 품질 기준과 영상당 1개, 계정 하나, 하루 상한 같은 운영 기준을 모두 서버에서 검사합니다. 화면을 거치지 않고 요청을 보내도 결과는 같습니다.

만들면서 가장 신경 쓴 건 댓글이 다 비슷해지는 문제였습니다. 그래서 자막과 인기 댓글에서 실제 장면을 뽑아 그 장면을 짚도록 했고, 앞서 쓴 댓글과 너무 닮았으면 다시 쓰게 했습니다.

화면은 처음 보는 사람도 따로 설명 없이 쓸 수 있는 걸 목표로 했습니다. 왼쪽에서 오른쪽으로 STEP 1, 2, 3을 따라가면 되고, 칸마다 뭘 넣으면 되는지 적혀 있습니다. 버튼이 안 눌릴 땐 그 이유가 바로 아래에 뜹니다.

자동화가 소리 없이 멈추는 것도 싫었습니다. 지금 몇 번째 단계인지 화면에 보이고, 실패하면 어디서 왜 멈췄는지 스크린샷과 함께 기록에 남습니다.

참고로 평가용 버전은 실제 유튜브에 아무것도 올리지 않습니다. 같은 구조로 만든 모의 페이지에서 자동화 전 과정을 돌려볼 수 있습니다.

---

## 사용한 오픈소스·외부 서비스

| 이름 | 용도 | 라이선스 |
|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | 웹 서버·API | MIT |
| [Uvicorn](https://github.com/encode/uvicorn) | ASGI 서버 | BSD-3-Clause |
| [HTTPX](https://github.com/encode/httpx) | YouTube·LLM API 호출 | BSD-3-Clause |
| [PyYAML](https://github.com/yaml/pyyaml) | `config.yaml` 읽기 | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | `.env` 읽기 | BSD-3-Clause |
| [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | 자막 가져오기 | MIT |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | Claude 호출 | MIT |
| [Playwright for Python](https://github.com/microsoft/playwright-python) | 크롬 자동화 | Apache-2.0 |
| [Pretendard](https://github.com/orioncactus/pretendard) | 화면 글꼴 (CDN) | SIL OFL 1.1 |
| [Lucide](https://github.com/lucide-icons/lucide) | 아이콘 모양 참고 (SVG 직접 작성) | ISC |
| YouTube Data API v3 | 영상 검색·정보·댓글 | Google API 서비스 약관 |
| Anthropic Claude API | 영상 분석·댓글 초안 (`claude-opus-5-5`) | Anthropic 이용 약관 |
