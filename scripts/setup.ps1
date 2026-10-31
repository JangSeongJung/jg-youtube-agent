# 환경 세팅: venv 생성 + 패키지 설치. 설치물/캐시는 프로젝트 폴더 안에 둔다 (C 드라이브 용량 절약).
# 실행: 프로젝트 폴더에서  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PIP_CACHE_DIR = "$root\.pip-cache"
$env:PLAYWRIGHT_BROWSERS_PATH = "$root\.pw-browsers"

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .venv\Scripts\python -m pip install --upgrade pip
& .venv\Scripts\python -m pip install -r requirements.txt
# 설치된 크롬(channel="chrome")을 쓰므로 Playwright 브라우저 다운로드는 생략한다.

if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host ".env 를 만들었습니다. API 키를 채워주세요." }
Write-Host "세팅 완료."
