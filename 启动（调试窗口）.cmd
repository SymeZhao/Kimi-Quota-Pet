@echo off
rem Debug launcher: keeps a console window open so errors are visible.
cd /d "%~dp0"
echo Starting Kimi quota pet (debug window)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0kimi_pet.ps1"
echo.
echo Exited with code %ERRORLEVEL%.
pause
