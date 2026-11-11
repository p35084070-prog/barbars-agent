# Постоянный watcher: каждые 15 минут проверяет уровень нового героя и,
# если он 11+, приглашает его в клан «Слепые ТИТАНЫ» и повышает до генерала.
# Запуск: powershell -ExecutionPolicy Bypass -File .\start_clan_watch.ps1

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { $python = $venv }
}

Write-Host "Watcher клана запущен. Лог: $root\logs\clan-auto.log" -ForegroundColor Cyan

while ($true) {
    & $python -u tests\clan_join_auto.py
    Write-Host "Проверка клана завершена, следующая через 15 мин..." -ForegroundColor Yellow
    Start-Sleep -Seconds 900
}
