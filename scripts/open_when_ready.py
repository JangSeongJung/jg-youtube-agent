"""서버(127.0.0.1:8000)가 응답할 때까지 기다렸다가 기본 브라우저로 대시보드를 연다. run.bat 이 호출."""
import time
import urllib.request
import webbrowser

URL = "http://127.0.0.1:8000"

for _ in range(60):  # 최대 30초
    try:
        urllib.request.urlopen(URL + "/api/info", timeout=1)
        webbrowser.open(URL)
        break
    except OSError:
        time.sleep(0.5)
