@echo off
rem Mecha Lab - ZBrush viewport Shift / Alt swap: start it now and at every Windows start.
set "SRC=%~dp0zbrush_nav_swap.ahk"
set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\zbrush_nav_swap.ahk"
if not exist "%SRC%" (echo zbrush_nav_swap.ahk is not next to this file. & pause & exit /b 1)
copy /Y "%SRC%" "%DST%" >nul
if errorlevel 1 (echo Could not copy to the Startup folder. & pause & exit /b 1)
start "" "%DST%"
if errorlevel 1 (echo Copied, but it did not start: install AutoHotkey v2 from https://www.autohotkey.com and run this again. & pause & exit /b 1)
echo Done. The swap is on now and will start with Windows.
echo To remove it, run uninstall.bat.
pause
