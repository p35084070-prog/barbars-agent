#!/usr/bin/env bash
# Установка агентов «Варвары» на Ubuntu/Debian VPS (Timeweb, reg.ru, Selectel, Oracle Cloud).
# Запуск:  sudo bash deploy/install.sh
#
# Что делает:
#   1. ставит Python-зависимости и Chromium для Playwright;
#   2. раскладывает облачные конфиги и systemd-юниты;
#   3. создаёт каталог с файлами учётных данных (права 600);
#   4. запускает три сервиса: keis, firewhite и watcher клана.

set -euo pipefail

APP_DIR=${APP_DIR:-/opt/barbars-agent}
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRED_DIR="$APP_DIR/credentials"

echo "== 1. Системные пакеты =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates >/dev/null
# зависимости Chromium/Playwright
apt-get install -y -qq \
  libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
  libcairo2 libatspi2.0-0 >/dev/null

echo "== 2. Копируем приложение в $APP_DIR =="
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude 'profile*' --exclude 'logs' --exclude '__pycache__' --exclude '.git' \
  "$SRC_DIR"/ "$APP_DIR"/

echo "== 3. Python-зависимости и Chromium =="
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install chromium

echo "== 4. Конфиги и учётные данные =="
cp -f deploy/config-cloud-keis.json "$APP_DIR/config-keis.json"
cp -f deploy/config-cloud-firewhite.json "$APP_DIR/config-firewhite.json"
mkdir -p "$CRED_DIR"
chmod 700 "$CRED_DIR"

for f in keis firewhite; do
  if [ ! -f "$CRED_DIR/$f.txt" ]; then
    echo "ВНИМАНИЕ: не создан $CRED_DIR/$f.txt — впишите туда ник и пароль (2 строки)."
  fi
done
chmod 600 "$CRED_DIR"/*.txt 2>/dev/null || true

echo "== 5. systemd-юниты =="
for u in barbars-keis barbars-firewhite barbars-clan-watch; do
  sed "s#/opt/barbars-agent#$APP_DIR#g" "deploy/systemd/$u.service" > "/etc/systemd/system/$u.service"
done
systemctl daemon-reload
systemctl enable barbars-keis barbars-firewhite barbars-clan-watch >/dev/null

echo "== 6. Запуск =="
systemctl restart barbars-keis barbars-firewhite barbars-clan-watch
sleep 5
systemctl --no-pager --lines=5 status barbars-keis barbars-firewhite barbars-clan-watch || true

cat <<'EOF'

Готово. Полезные команды:
  journalctl -u barbars-keis -f          # логи keis
  journalctl -u barbars-firewhite -f     # логи fire white ii
  journalctl -u barbars-clan-watch -f    # вступление в клан
  ls -l /opt/barbars-agent/logs/keis /opt/barbars-agent/logs/firewhite
EOF
