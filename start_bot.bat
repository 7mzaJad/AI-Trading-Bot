@echo off
setlocal
echo ========================================================
echo             AI TRADING BOT - START SERVICE
echo ========================================================
echo.

:: Remove stop flag if present
if exist "G:\My Drive\My Projects\Trading Bot\.stop_bot" del /f /q "G:\My Drive\My Projects\Trading Bot\.stop_bot" 2>nul

:: Check if already running
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*run_alpaca.py*' }; if ($p) { Write-Host ('[INFO] Trading Bot is ALREADY RUNNING (PID: ' + $p.ProcessId + ')') -ForegroundColor Yellow; exit 1 } else { exit 0 }"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Nothing to do.
    pause
    exit /b 0
)

echo Starting Trading Bot in the background...
wscript.exe "C:\Users\Artelco\AppData\Roaming\TradingBot\start_trading_bot.vbs"

ping 127.0.0.1 -n 3 >nul
echo.
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*run_alpaca.py*' }; if ($p) { Write-Host ('[SUCCESS] Trading Bot is now running in the background (PID: ' + $p.ProcessId + ')') -ForegroundColor Green } else { Write-Host '[INFO] Service runner launched in background and initializing.' -ForegroundColor Cyan }"
echo.
pause
