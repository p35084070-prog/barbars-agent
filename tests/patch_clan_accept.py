"""Патч: принять приглашение в клан (текст «keis приглашает тебя в клан ... принять»)."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tests" / "clan_join_auto.py"
text = path.read_text(encoding="utf-8")

old = '''            if re.search(r"Вступить|Принять приглашение|Приглашение в клан", body, re.I):
                log(f"герой видит приглашение: {body[:200]}")
                for word in ("Вступить", "Принять", "Приглашение"):
                    btn = page_b.query_selector(f"a:has-text('{word}')")
                    if btn:
                        btn.click()
                        page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                        log(f"нажато «{word}»")
                        break
                break'''

new = '''            if re.search(r"приглашает тебя в клан|вступить|принять|приглашени", body, re.I):
                log(f"герой видит приглашение: {body[:200]}")
                accepted = False
                # сперва пробуем штатную ссылку «принять» (acceptLink)
                accept = page_b.query_selector("a[href*='acceptLink']")
                if accept:
                    accept.click()
                    page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                    log("нажато «принять» (acceptLink)")
                    accepted = True
                if not accepted:
                    for word in ("принять", "Вступить", "Принять", "Приглашение"):
                        btn = page_b.query_selector(f"a:has-text('{word}')")
                        if btn:
                            btn.click()
                            page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                            log(f"нажато «{word}»")
                            break
                break'''

assert old in text, "не найден блок принятия приглашения"
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("патч применён")
