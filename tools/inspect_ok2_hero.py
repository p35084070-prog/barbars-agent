"""Read OK2 hero identity and class without entering any activity."""
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from barbars.ok_channel import OkGame


def main():
    cfg = json.loads(Path('config-ok.json').read_text(encoding='utf8'))
    cfg['account'] = 'ok2'
    cfg['ok_channel']['session_file'] = str(Path('state/ok2/ok-session.b64').resolve())
    cfg['ok_channel']['session_env'] = 'OK2_SESSION_B64'
    with tempfile.TemporaryDirectory(prefix='ok2-identity-') as profile:
        with OkGame(cfg, profile) as game:
            if not game.ensure_login(timeout_sec=90):
                raise RuntimeError('ОК2: вход в игру не подтверждён')
            game.goto('https://od.barbars.ru/user')
            hero = game.hero()
            evidence = [line.strip() for line in game.body_text().splitlines()
                        if 'qdl' in line.lower() or 'суммар' in line.lower()]
            print('OK2_HERO_IDENTITY ' + json.dumps({'hero_id': game.hero_id, 'hero': asdict(hero),
                  'name_evidence': evidence, 'activities_started': False}, ensure_ascii=False), flush=True)
            if not game.hero_id or hero.guild_id != 16675 or hero.klass not in ('воин', 'медик'):
                raise RuntimeError('ОК2: требуется проверка ID, класса или клана')


if __name__ == '__main__':
    main()
