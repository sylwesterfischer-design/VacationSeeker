@echo off
setlocal
cd /d "%~dp0"

set "DEST=%~1"
if "%DEST%"=="" set "DEST=Irlandia"
set "EMAIL=%~2"
if "%EMAIL%"=="" set "EMAIL=sylwester.fischer@gmail.com"
set "DROP=%~3"
if "%DROP%"=="" set "DROP=0.5"
set "ADULTS=2"
set "CHILDREN=12,14"

echo [VacationSeeker] Dodaje watch: %DEST% ^| dorosli=%ADULTS% ^| dzieci=%CHILDREN% ^| prog=%DROP% ^| email=%EMAIL%
py -3 -m src.vacation_seeker.main add-watch --destination "%DEST%" --adults %ADULTS% --children-ages "%CHILDREN%" --drop-ratio %DROP% --email "%EMAIL%"
if errorlevel 1 (
  echo [VacationSeeker] Blad dodawania watcha.
  exit /b 1
)
echo [VacationSeeker] OK.
endlocal
