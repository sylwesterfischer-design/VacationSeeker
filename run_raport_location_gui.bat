@echo off
setlocal
cd /d "%~dp0"
echo [VacationSeeker] Uruchamiam okno GUI raportu lokalizacyjnego...
start "VacationSeeker GUI" /D "%~dp0" py -3 -m src.vacation_seeker.gui_location
if errorlevel 1 pause
endlocal
