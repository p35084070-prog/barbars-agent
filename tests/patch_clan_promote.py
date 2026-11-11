"""Патч: повышать до генерала нужно именно участника fire white ii.

На странице управления кланом у каждого участника свой блок со ссылками
demote/promote/kick; раньше скрипт кликал первую «повысить» на странице —
это был другой игрок.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tests" / "clan_join_auto.py"
text = path.read_text(encoding="utf-8")

old = '''        # лидер повышает до генерала
        if joined:
            for step in range(4):
                page_a.goto(f"https://barbars.ru/guild/{GUILD}", wait_until="domcontentloaded", timeout=60_000)
                page_a.click("a:has-text('Управление кланом')")
                page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                html = page_a.content()
                idx = html.find(NEW_NICK)
                if idx < 0:
                    log("героя нет в списке участников")
                    break
                block = html[max(0, idx - 1500) : idx + 1500]
                rank = next((r for r in RANKS if f">{r}" in block or f">{r} " in block), None)
                log(f"текущий ранг: {rank}")
                if rank == "генерал":
                    log("ранг генерал получен")
                    break
                promote = None
                for candidate in page_a.query_selector_all("a:has-text('повысить')"):
                    if candidate.get_attribute("href"):
                        promote = candidate
                        break
                if not promote:
                    log("кнопки повышения нет")
                    break
                promote.click()
                page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                time.sleep(1)
'''

new = '''        # лидер повышает до генерала
        if joined:
            for step in range(4):
                page_a.goto(f"https://barbars.ru/guild/{GUILD}", wait_until="domcontentloaded", timeout=60_000)
                page_a.click("a:has-text('Управление кланом')")
                page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                html = page_a.content()
                idx = html.find(NEW_NICK)
                if idx < 0:
                    log("героя нет в списке участников")
                    break
                # блок участника: от ближайшего <div> до следующего </div><div>
                start = html.rfind("<div>", 0, idx)
                end = html.find("<div>", idx)
                block = html[start:end if end > 0 else idx + 2000]
                m = re.search(r"<span>\\s*(рядовой|офицер|генерал|маршал|лидер)\\s*</span>", block)
                rank = m.group(1) if m else None
                log(f"текущий ранг: {rank}")
                if rank == "генерал":
                    log("ранг генерал получен")
                    break
                m = re.search(r'href="([^"]*promoteLink[^"]*)"', block)
                if not m:
                    log("кнопки повышения нет")
                    break
                page_a.goto(urljoin(page_a.url, m.group(1).replace("&amp;", "&")),
                            wait_until="domcontentloaded", timeout=60_000)
                time.sleep(1)
'''

assert old in text, "не найден блок повышения"
text = text.replace(old, new, 1)

if "from urllib.parse import urljoin" not in text:
    text = text.replace(
        "from pathlib import Path",
        "from pathlib import Path\nfrom urllib.parse import urljoin",
        1,
    )

path.write_text(text, encoding="utf-8")
print("патч применён")
