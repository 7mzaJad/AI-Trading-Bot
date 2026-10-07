@echo off
setlocal
echo ========================================================
echo             MT5 XAUUSD BOT - SYSTEM STATUS
echo ========================================================
echo.

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*run_mt5.py*' }; if ($p) { Write-Host ('[STATUS] RUNNING in background (PID: ' + $p.ProcessId + ')') -ForegroundColor Green } else { Write-Host '[STATUS] NOT RUNNING' -ForegroundColor Red }"

echo.
echo ------------------- Last 15 Log Entries -------------------
powershell -NoProfile -Command "if (Test-Path 'G:\My Drive\My Projects\Trading Bot\trading_bot.log') { Get-Content 'G:\My Drive\My Projects\Trading Bot\trading_bot.log' -Tail 15 } else { Write-Host 'No log file found yet.' }"
echo -----------------------------------------------------------
echo.
pause
