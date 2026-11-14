"""Read the real mail resource choices. Never select or send a resource."""
import json
import tempfile
import re

from barbars.driver import Game, normalize_ru


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
            game.goto('https://barbars.ru/guild/16675')
            members = []
            target = None
            for link in game.p.locator('a').all():
                href = link.get_attribute('href') or ''
                match = re.search(r'user/(?:body/)?id/(\d+)', href)
                if not match:
                    continue
                name = ' '.join(link.inner_text().split())
                members.append({'id': match[1], 'name': name})
                if normalize_ru(name) == normalize_ru('Qdle'):
                    target = match[1]
            print('CLAN_MEMBERS ' + json.dumps(members, ensure_ascii=False), flush=True)
            if target:
                game.goto(f'https://barbars.ru/user/body/id/{target}')
                hero = game.hero()
                print('QDLE_IDENTITY ' + json.dumps({'hero_id': target, 'class': hero.klass,
                      'level': hero.level, 'guild_id': hero.guild_id, 'max_hp': hero.max_hp,
                      'max_energy': hero.max_energy}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
