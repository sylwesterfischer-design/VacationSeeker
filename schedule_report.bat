@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=output"

set "INTERVAL=%~2"
if "%INTERVAL%"=="" set "INTERVAL=60"

echo [VacationSeeker] Scheduler start, co %INTERVAL% min, raport: "%TARGET%\report.html"
py -3 -m src.vacation_seeker.main schedule --target-folder "%TARGET%" --refresh-minutes %INTERVAL%
endlocal
