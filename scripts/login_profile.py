"""
크롬 프로필 준비용: 지정 프로필 폴더로 '일반' chrome.exe 를 실행만 한다. (Playwright 아님)
- 사용자가 직접 로그인/확인 후 창을 닫으면 끝.
- 평소 쓰는 기본 크롬 프로필은 건드리지 않는다 (--user-data-dir 로 분리).

사용법:  .venv\\Scripts\\python scripts\\login_profile.py 유튜브1
         (인자 없이 실행하면 목록에서 고름)
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_profile, profile_in_use, settings  # noqa: E402


def main():
    names = [p["name"] for p in settings["profiles"]]
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        for i, n in enumerate(names, 1):
            print(f"  {i}) {n}")
        name = names[int(input("프로필 번호: ")) - 1]

    prof = get_profile(name)
    pdir = Path(prof["dir"])
    pdir.mkdir(parents=True, exist_ok=True)

    if profile_in_use(str(pdir)):
        sys.exit(f"[중단] '{name}' 프로필 창이 이미 열려 있습니다. 해당 크롬 창을 닫고 다시 실행하세요.")

    chrome = settings["chrome_path"]
    if not Path(chrome).exists():
        sys.exit(f"[중단] 크롬을 찾을 수 없습니다: {chrome} (config.yaml 의 chrome_path 확인)")

    print(f"'{name}' 프로필로 크롬을 엽니다 → {pdir}")
    print("로그인/확인을 마치면 크롬 창을 닫아주세요.")
    proc = subprocess.Popen([chrome, f"--user-data-dir={pdir}", "--no-first-run",
                             "https://www.youtube.com/?hl=ko"])
    proc.wait()
    print("완료. 이 프로필은 이제 대시보드에서 사용할 수 있습니다.")


if __name__ == "__main__":
    main()
