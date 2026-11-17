@echo off
setlocal EnableExtensions
rem Mecha Lab - GoZ set-up in one go: makes ZBrush list Blender as a GoZ program.
rem It writes two small text files into ZBrush's shared GoZ folder (GoZApps\Blender) and nothing else.
rem You can drag blender.exe onto this file to choose which Blender is used.
title Mecha Lab - GoZ set-up

rem ---- 1. ZBrush's shared GoZ folder ------------------------------------------------------------
set "ROOT="
if exist "%PUBLIC%\Pixologic\GoZBrush" set "ROOT=%PUBLIC%\Pixologic"
if not defined ROOT if exist "%PUBLIC%\Maxon\GoZBrush" set "ROOT=%PUBLIC%\Maxon"
if defined ROOT goto have_root

echo ZBrush's GoZ folder was not found:
echo   %PUBLIC%\Pixologic\GoZBrush
echo.
set "ZB="
for /d %%D in ("%ProgramFiles%\Maxon ZBrush*") do if exist "%%D\Troubleshoot Help\GoZ_for_ZBrush_Installer_WIN.exe" set "ZB=%%D"
for /d %%D in ("%ProgramFiles%\Pixologic\ZBrush*") do if exist "%%D\Troubleshoot Help\GoZ_for_ZBrush_Installer_WIN.exe" set "ZB=%%D"
if not defined ZB goto no_root
echo Starting ZBrush's own GoZ installer:
echo   %ZB%\Troubleshoot Help\GoZ_for_ZBrush_Installer_WIN.exe
start "" "%ZB%\Troubleshoot Help\GoZ_for_ZBrush_Installer_WIN.exe"
echo.
echo When it has finished, run this file again.
pause
exit /b 1

:no_root
echo Start ZBrush once (it makes that folder), then run this file again.
pause
exit /b 1

:have_root
echo GoZ folder : %ROOT%

rem ---- 2. Blender ---------------------------------------------------------------------------------
set "BL="
if not "%~1"=="" if exist "%~1" set "BL=%~1"
if defined BL goto have_blender
for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BL=%%D\blender.exe"
if defined BL goto have_blender
for /f "delims=" %%P in ('where blender.exe 2^>nul') do if not defined BL set "BL=%%P"
if defined BL goto have_blender
echo.
echo Blender was not found in Program Files\Blender Foundation.
echo Drag blender.exe into this window and press Enter (or just press Enter to stop):
set /p "BL="
if not defined BL exit /b 1
set "BL=%BL:"=%"
if not exist "%BL%" (echo That file does not exist. & pause & exit /b 1)

:have_blender
echo Blender    : %BL%

rem ---- 3. the two files -----------------------------------------------------------------------------
set "APP=%ROOT%\GoZApps\Blender"
if not exist "%APP%" mkdir "%APP%"
if not exist "%APP%" (echo Could not make %APP% & pause & exit /b 1)
set "BLF=%BL:\=/%"
> "%APP%\GoZ_Config.txt" echo PATH = "%BLF%"
(
echo NAME			=	"Blender"
echo GOZ_VERSION		=	1
echo EXTENSION		=	".GoZ"
echo TAMPLATE		=	"GoZ Complete Binary.GoZ"
echo.
echo EXPORT_FLIP_Y			=	FALSE
echo EXPORT_FLIP_Z			=	FALSE
echo IMPORT_FLIP_Y			=	FALSE
echo IMPORT_FLIP_Z			=	FALSE
echo.
echo NORMAL_MAP_FLIP_VERT		=	FALSE
echo TEXTURE_MAP_FLIP_VERT		=	FALSE
echo DISPLACEMENT_MAP_FLIP_VERT	=	FALSE
) > "%APP%\GoZ_Info.txt"
if not exist "%APP%\GoZ_Info.txt" (echo Could not write into %APP% & pause & exit /b 1)

echo.
echo Done. Written:
echo   %APP%\GoZ_Info.txt
echo   %APP%\GoZ_Config.txt
echo.
echo Next: restart ZBrush, then Preferences ^> GoZ and choose Blender.
echo In Blender (Mecha Lab ^> ZBrush bridge ^> GoZ): Send (GoZ) / Import (GoZ) / Auto.
echo To undo: delete the folder %APP%
pause
