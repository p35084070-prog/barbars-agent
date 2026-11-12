"""Разведка окна входа ОК: какие поля, есть ли капча/подтверждение по SMS.

Ничего не вводим и не логинимся — только смотрим форму.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "ok-login-check"
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)
HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "profile-ok-check"),
            headless=True,
            viewport={"width": 390, "height": 844},
            user_agent=IPHONE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            extra_http_headers=HEADERS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for url in ("https://m.ok.ru/", "https://ok.ru/dsh"):
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(4)
            print("=" * 60)
            print("URL:", page.url)
            try:
                body = " ".join(page.inner_text("body").split())
            except Exception as exc:  # noqa: BLE001
                body = f"<ошибка: {exc}>"
            print("текст:", body[:700])
            fields = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('input, button, a').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) return;
                    out.push({
                        tag: el.tagName,
                        type: el.getAttribute('type') || '',
                        name: el.getAttribute('name') || '',
                        id: el.id || '',
                        text: (el.innerText || el.value || '').trim().slice(0, 50),
                        href: (el.getAttribute('href') || '').slice(0, 80),
                    });
                });
                return out;
            }""")
            for f in fields:
                print("  ", f)
            html = page.content()
            (OUT / (re.sub(r"[^a-z0-9]+", "_", page.url)[:60] + ".html")).write_text(
                html, encoding="utf-8"
            )
            for key in ("captcha", "капч", "g-recaptcha", "smartcaptcha", "st.lgi",
                        "sms", "tel", "one-time", "code"):
                n = len(re.findall(key, html, re.IGNORECASE))
                if n:
                    print(f"   маркер «{key}»: {n}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
