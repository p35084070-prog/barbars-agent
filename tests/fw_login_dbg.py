import json
import re
import requests
from pathlib import Path

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")
c = json.loads(Path("credentials-firewhite.json").read_text(encoding="utf-8"))
s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
p = s.get("https://barbars.ru/login", timeout=30)
action = re.search(r'<form action="([^"]+)"[^>]*method="post"', p.text).group(1)
data = {}
for tag in re.findall(r"<input[^>]*>", p.text):
    name = re.search(r'name="([^"]+)"', tag)
    val = re.search(r'value="([^"]*)"', tag)
    if name:
        data[name.group(1)] = val.group(1) if val else ""
data["login"] = c["nick"]
data["password"] = c["password"]
url = "https://barbars.ru/login".rsplit("/", 1)[0] + "/" + action.lstrip("/")
res = s.post(url, data=data, timeout=30, headers={"Referer": p.url})
text = re.sub(r"<script.*?</script>", " ", res.text, flags=re.S)
text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
text = re.sub(r"<[^>]+>", "\n", text)
lines = [l.strip() for l in text.splitlines() if l.strip()]
print("post", res.status_code, res.url, "lines", len(lines))
print("\n".join(lines[:60]))
