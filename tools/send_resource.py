"""Передача ресурса (железо/мифрил/бутылочки) другому герою почтой.

Форма игры: /user/mail/send/id/<id> -> вкладка «Ресурсы» -> тип -> количество
-> «отправить». Комиссия игры: 5 серебра за каждые 10 000 железа.

Инструмент печатает одну строку JSON в stdout:
    SEND_RESOURCE {"ok": bool, "message": str, ...}
и складывает страницы в logs/<label>-send-resource/ для разбора.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402


def build_game(config: dict, profile: Path):
    if config.get("ok_channel"):
        from barbars.ok_channel import OkGame

        return OkGame(config, profile)
    return Game(config, profile)


def snapshot(game: Game) -> dict[str, object]:
    """Текущий баланс отправителя (железо/мифрил/бутылки/монеты)."""
    out: dict[str, object] = {}
    try:
        status = game.status()
    except Exception as exc:  # noqa: BLE001
        return {"status_error": str(exc).splitlines()[0][:200]}
    if isinstance(status, dict):
        for key in ("iron", "mifril", "bottles", "gold", "silver"):
            if key in status:
                out[key] = status[key]
    elif hasattr(status, "as_dict"):
        out.update({k: v for k, v in status.as_dict().items() if v is not None})
    else:
        out["raw"] = str(status)[:300]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Отправить ресурс герою почтой")
    parser.add_argument("--config", required=True)
    parser.add_argument("--label", default="send")
    parser.add_argument("--recipient-id", default="")
    parser.add_argument("--resource", default="iron", choices=["iron", "mifril", "bottles"])
    parser.add_argument("--amount", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", help="только показать форму, не отправлять")
    parser.add_argument("--status-only", action="store_true", help="только показать баланс, ничего не отправлять")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    label = args.label or str(config.get("account") or args.config)
    log_dir = ROOT / "logs" / f"{label}-send-resource"
    log_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, object] = {"label": label, "recipient_id": args.recipient_id,
                                  "resource": args.resource, "amount": args.amount}

    with tempfile.TemporaryDirectory(prefix=f"send-{label}-") as tmp:
        game = build_game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=args.timeout):
                result["ok"] = False
                result["message"] = "вход не подтверждён"
                print("SEND_RESOURCE " + json.dumps(result, ensure_ascii=False), flush=True)
                return 1

            result["before"] = snapshot(game)

            if args.status_only:
                result["ok"] = True
                result["message"] = "status-only: баланс показан, отправка не выполнялась"
                print("SEND_RESOURCE " + json.dumps(result, ensure_ascii=False), flush=True)
                return 0

            if not args.recipient_id or args.amount <= 0:
                result["ok"] = False
                result["message"] = "нужен --recipient-id и --amount > 0"
                print("SEND_RESOURCE " + json.dumps(result, ensure_ascii=False), flush=True)
                return 1

            # Смотрим форму: сколько серебра просит игра и есть ли вкладка «Ресурсы».
            try:
                game.goto(f"https://barbars.ru/user/mail/send/id/{args.recipient_id}")
                form_text = " ".join(game.body_text().split())
                result["form_head"] = form_text[:500]
                opened = game.click_href("sendMessageForm:mailGoodsLink")
                result["resources_tab_opened"] = bool(opened)
                if opened:
                    game._settle()
                    options = []
                    for option in game.p.locator("select[name='type'] option").all():
                        try:
                            options.append({"text": (option.inner_text() or "").strip()[:40],
                                            "value": option.get_attribute("value"),
                                            "disabled": option.get_attribute("disabled") is not None})
                        except Exception:  # noqa: BLE001
                            continue
                    result["resource_options"] = options
                    body = " ".join(game.body_text().split())
                    result["form_body"] = body[:800]
            except Exception as exc:  # noqa: BLE001
                result["form_error"] = str(exc).splitlines()[0][:200]

            if args.dry_run:
                result["ok"] = True
                result["message"] = "dry-run: форма показана, отправка не выполнялась"
                print("SEND_RESOURCE " + json.dumps(result, ensure_ascii=False), flush=True)
                return 0

            sent = game.send_resources_to(args.recipient_id, args.resource, args.amount)
            result["send"] = sent
            result["ok"] = bool(sent.get("ok"))
            result["message"] = str(sent.get("message", ""))
            try:
                game.dump_page(f"after-send-{args.resource}", log_dir)
            except Exception:  # noqa: BLE001
                pass
            result["after"] = snapshot(game)
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["message"] = str(exc).splitlines()[0][:300]
            try:
                game.dump_page("send-resource-error", log_dir)
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("SEND_RESOURCE " + json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
