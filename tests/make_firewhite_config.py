"""Создаёт конфиг второго аккаунта «Fire White» на основе config.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

config["account"] = "firewhite"
config["profile_dir"] = "profile-firewhite"
config["state_dir"] = "logs/firewhite"
# второй аккаунт работает без окна, чтобы не мешать первому
config["headless"] = True
config["auth"]["credentials_file"] = r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt"

# свежий герой: осторожнее с тратами, пока нет ресурсов
config["altar"]["keep_iron"] = 50000
config["spend"]["clan_donate"]["keep_iron"] = 500000

out = ROOT / "config-firewhite.json"
out.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
print("записан:", out)
