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


settings = load_config()


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
