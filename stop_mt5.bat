@echo off
setlocal
echo ========================================================
echo             MT5 XAUUSD BOT - STOP SERVICE
echo ========================================================
echo.

:: Create stop flag so supervisor will not restart the process
echo Stopped by user on %DATE% %TIME% > "G:\My Drive\My Projects\Trading Bot\.stop_bot"

echo Stopping background Trading Bot processes...
powershell -NoProfile -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*' -and $_.CommandLine -like '*run_mt5.py*') -or ($_.Name -like 'cmd*' -and $_.CommandLine -like '*service_runner.bat*') }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('  - Terminated PID ' + $p.ProcessId + ' (' + $p.Name + ')') -ForegroundColor Yellow } } else { Write-Host '  - No active bot processes found.' -ForegroundColor Gray }"

echo.
echo [SUCCESS] MT5 XAUUSD BOT has been completely stopped.
echo.
pause
