"""Read the real mail resource choices. Never select or send a resource."""
import json
import tempfile

from barbars.driver import Game


def main():
    cfg = {"headless": True, "auth": {"username_env": "KEIS_LOGIN", "password_env": "KEIS_PASS"},
           "humanize": {"enabled": False}}
    with tempfile.TemporaryDirectory(prefix="mail-options-") as profile:
        with Game(cfg, profile) as game:
            if not game.ensure_login(timeout_sec=30):
                raise RuntimeError("Не удалось войти сохранённым доступом Кейса")
            game.goto("https://barbars.ru/user/mail/send/id/31389504")
            opened = game.click_href("sendMessageForm:mailGoodsLink")
            fields = []
            for select in game.p.locator("select").all():
                fields.append({"name": select.get_attribute("name"), "options": [
                    {"value": option.get_attribute("value"), "label": option.inner_text().strip(),
                     "disabled": option.get_attribute("disabled") is not None}
                    for option in select.locator("option").all()]})
            print("MAIL_RESOURCE_OPTIONS " + json.dumps({"account": "keis", "recipient_id": "31389504",
                  "resource_tab_opened": opened, "fields": fields, "submitted": False}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
