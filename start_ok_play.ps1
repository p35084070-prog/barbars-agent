# Запуск игры «Варвары» через Одноклассники с компьютера.
# Использование: powershell -ExecutionPolicy Bypass -File .\start_ok_play.ps1
#
# Первый раз: войдите в ОК в открывшемся окне (tools\ok_phone.py),
# дальше сессия сохранится в профиле profile-ok-phone.

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { $python = $venv }
}

$args = @('tools\ok_play.py')
if ($env:OK_HOLD) { $args += '--hold'; $args += $env:OK_HOLD }
if ($env:OK_HEADLESS -eq '1') { $args += '--headless' }

Write-Host "Запускаю «Варвары» через мобильную версию ОК..." -ForegroundColor Cyan
& $python -u @args
