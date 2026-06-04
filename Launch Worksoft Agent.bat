@echo off
title Worksoft Support Agent
color 0B
echo.
echo  =====================================================
echo    Worksoft Support Agent
echo  =====================================================
echo.

echo  Stopping any previous instance on port 8504...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8504 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo  Starting Worksoft Support Agent on http://localhost:8504
echo.

cd /d "%~dp0"
python -m streamlit run worksoft_support.py --server.port=8504 --browser.gatherUsageStats=false

echo.
echo  Agent stopped. Press any key to close.
pause > nul
