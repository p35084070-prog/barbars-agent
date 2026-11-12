# Обновить секрет GitHub OK_SESSION_B64 свежей сессией ОК.
#
# Что делает:
#   1) берёт cookie из живого профиля profile-ok-phone (вход в ОК уже есть);
#   2) пишет state\ok-session.b64;
#   3) кладёт содержимое в секрет OK_SESSION_B64 репозитория.
#
# Запуск (из корня проекта):
#   powershell -ExecutionPolicy Bypass -File tools\ok_refresh_secret.ps1
#
# Если профиль ОК тоже разлогинился (в tools\ok_phone.py скажет
# «вход не требуется» не сработает), сначала войдите руками:
#   python tools\ok_phone.py
param(
    [string]$Repo = 'p35084070-prog/barbars-agent'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

Write-Host '1/3 выгружаем cookie из профиля ОК...' -ForegroundColor Cyan
python -u tools\ok_export_cookies.py
if ($LASTEXITCODE -ne 0) { throw 'не удалось выгрузить сессию' }

$b64 = (Get-Content -LiteralPath 'state\ok-session.b64' -Raw).Trim()
if (-not $b64) { throw 'пустой файл сессии' }

Write-Host "2/3 обновляем секрет OK_SESSION_B64 в $Repo..." -ForegroundColor Cyan
gh secret set OK_SESSION_B64 --repo $Repo --body $b64
if ($LASTEXITCODE -ne 0) { throw 'не удалось обновить секрет' }

Write-Host '3/3 запускаем тестовую сессию в облаке (10 минут)...' -ForegroundColor Cyan
gh workflow run agent-ok.yml -f duration=10 --repo $Repo
Write-Host ''
Write-Host 'Готово. Смотрим результат: gh run list --repo ' $Repo -ForegroundColor Green
