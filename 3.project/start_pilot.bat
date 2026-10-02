@echo off
chcp 65001 > nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_launcher.ps1" -OnlyIfMissing
if errorlevel 1 (
    pause
    exit /b 1
)
"%~dp0C-Pilot.exe" %*
if errorlevel 1 pause
