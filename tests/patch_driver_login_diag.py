"""Патч: диагностика неудачного автовхода + ожидание перезагрузки страницы."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")

old = '''            self.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
            self._settle()
            self.human.pause("page")
        except Exception as exc:
            print(f"[вход] автовход не удался: {exc}")
            return False
        ok = self.is_authenticated()
        print("[вход] автовход выполнен" if ok else "[вход] автовход не прошёл")
        return ok
'''

new = '''            self.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
            try:
                self.p.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            self._settle()
            self.human.pause("page")
        except Exception as exc:
            print(f"[вход] автовход не удался: {exc}")
            return False
        ok = self.is_authenticated()
        if ok:
            print("[вход] автовход выполнен")
            return True
        # диагностика: показываем, что игра ответила вместо входа
        try:
            body = " ".join(self.body_text().split())
        except Exception:
            body = ""
        print(f"[вход] автовход не прошёл, страница: {body[:400]}")
        try:
            self.dump_page("login-failed", self.config.get("_root", "."))
        except Exception:
            pass
        return False
'''

assert old in text, "не найден блок auto_login"
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("патч применён")
