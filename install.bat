@echo off
title Worksoft Support Agent - Installer
color 0B
echo.
echo  =====================================================
echo    Worksoft Support Agent - Dependency Installer
echo  =====================================================
echo.

echo  Installing required packages...
echo.
pip install -r "%~dp0requirements.txt"

if %ERRORLEVEL% neq 0 (
    echo.
    echo  Install failed. Make sure Python and pip are installed and in PATH.
    echo.
    pause
    exit /b 1
)

echo.
echo  =====================================================
echo    All requirements installed successfully.
echo    You can now run: Launch Worksoft Agent.bat
echo  =====================================================
echo.
pause
exit /b 0
