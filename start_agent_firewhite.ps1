# Запуск второго агента «Варвары» — аккаунт «Fire White».
# Использование: powershell -ExecutionPolicy Bypass -File .\start_agent_firewhite.ps1

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { $python = $venv }
}

Write-Host "Запуск агента Fire White. Логи: $root\logs\firewhite" -ForegroundColor Cyan

while ($true) {
    & $python -u run.py --config config-firewhite.json play
    Write-Host "Агент Fire White завершился, перезапуск через 15 c..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
}
