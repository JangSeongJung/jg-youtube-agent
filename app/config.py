"""config.yaml + .env 로딩. 다른 모듈은 여기서 settings 를 가져다 쓴다."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
DB_PATH = DATA_DIR / "agent.db"

load_dotenv(ROOT / ".env", encoding="utf-8")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_chrome(configured: str | None) -> str:
    """config 의 chrome_path 가 비었거나 없는 경로면 기본 설치 위치에서 찾는다."""
    candidates = [configured] if configured else []
    for base in (os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("LOCALAPPDATA")):
        if base:
            candidates.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    for c in candidates:
        if Path(c).exists():
            return c
    raise RuntimeError("크롬(chrome.exe)을 찾지 못했습니다. config.yaml 의 chrome_path 에 경로를 넣어주세요.")


settings = load_config()
# 프로필 폴더는 프로젝트 폴더 기준 상대경로로 적을 수 있다 (다른 PC에 받아도 그대로 동작)
for _p in settings["profiles"]:
    _p["dir"] = str((ROOT / _p["dir"]).resolve())
settings["chrome_path"] = find_chrome(settings.get("chrome_path"))


def get_profile(name: str) -> dict:
    for p in settings["profiles"]:
        if p["name"] == name:
            return p
    raise KeyError(f"config.yaml 에 없는 프로필: {name}")


def profile_in_use(profile_dir: str) -> bool:
    """크롬이 프로필을 쓰는 중이면 user-data-dir/lockfile 을 잠그고 있다 (Windows)."""
    lock = Path(profile_dir) / "lockfile"
    if not lock.exists():
        return False
    try:
        with open(lock, "rb"):
            return False
    except PermissionError:
        return True


def env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(f".env 에 {key} 값이 없습니다. .env.example 을 참고하세요.")
    return val
