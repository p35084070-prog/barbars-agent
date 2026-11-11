# Запуск мобильного окна ОК для игры «Варвары» (нужен вход в аккаунт ОК).
# Использование: powershell -ExecutionPolicy Bypass -File .\start_ok_mobile.ps1

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { $python = $venv }
}

Write-Host "Мобильное окно ОК: войдите в аккаунт в открывшемся Chromium." -ForegroundColor Cyan
& $python -u tests\ok_mobile_login.py
