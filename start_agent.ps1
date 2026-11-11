# Запуск агента «Варвары» в фоне с автоперезапуском.
# Использование: powershell -ExecutionPolicy Bypass -File .\start_agent.ps1
# Остановить: закрой окно или Ctrl+C.

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { $python = $venv }
}

Write-Host "Запуск агента. Логи: $root\logs" -ForegroundColor Cyan

while ($true) {
    & $python -u run.py play
    Write-Host "Агент завершился, перезапуск через 10 c..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
