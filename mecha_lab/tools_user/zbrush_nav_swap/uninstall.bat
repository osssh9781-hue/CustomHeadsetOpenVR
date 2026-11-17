@echo off
rem Mecha Lab - ZBrush viewport Shift / Alt swap: stop it and take it out of the Startup folder.
taskkill /F /FI "WINDOWTITLE eq zbrush_nav_swap.ahk*" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\zbrush_nav_swap.ahk" >nul 2>&1
echo Removed from the Startup folder. If the swap is still on, right-click the green H icon near the clock and choose Exit.
pause
