"""Патч: если приглашение уже отправлено — не прерываться, а принять его."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tests" / "clan_join_auto.py"
text = path.read_text(encoding="utf-8")

old = '''        invite = page_a.query_selector("a:has-text('Пригласить в клан')")
        if not invite:
            log("кнопки приглашения нет")
            ctx_a.close()
            ctx_b.close()
            return 2
        invite.click()
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        log(f"приглашение отправлено: {' '.join(page_a.inner_text('body').split())[:150]}")
'''

new = '''        invite = page_a.query_selector("a:has-text('Пригласить в клан')")
        if invite:
            invite.click()
            page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
            log(f"приглашение отправлено: {' '.join(page_a.inner_text('body').split())[:150]}")
        else:
            # приглашение, скорее всего, уже висит — идём принимать
            log("кнопки приглашения нет (приглашение, вероятно, уже отправлено)")
'''

assert old in text, "не найден блок приглашения"
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("патч применён")
