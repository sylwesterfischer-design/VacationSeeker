@echo off
setlocal
cd /d "%~dp0"

set "DEST=%~1"
if "%DEST%"=="" set /p DEST=Podaj kierunek (np. Majorka): 
if "%DEST%"=="" set "DEST=Majorka"

set "EMAIL=%~2"
if "%EMAIL%"=="" set "EMAIL=sylwester.fischer@gmail.com"

set "ADULTS=%~3"
if "%ADULTS%"=="" set "ADULTS=2"

set "CHILDREN=12,14"

set "DATE_FROM=%~4"
if "%DATE_FROM%"=="" set "DATE_FROM="

set "DATE_TO=%~5"
if "%DATE_TO%"=="" set "DATE_TO="

set "DROP=%~6"
if "%DROP%"=="" set "DROP=0.5"

set "INTERVAL=%~7"
if "%INTERVAL%"=="" set "INTERVAL=30"

set "TARGET=%~8"
if "%TARGET%"=="" set "TARGET=output"

echo [VacationSeeker] Tworze/aktualizuje watch: %DEST% ^| dorosli=%ADULTS% ^| dzieci=%CHILDREN% ^| od=%DATE_FROM% ^| do=%DATE_TO% ^| prog=%DROP% ^| email=%EMAIL%
if "%DATE_FROM%"=="" (
  py -3 -m src.vacation_seeker.main add-watch --destination "%DEST%" --adults %ADULTS% --children-ages "%CHILDREN%" --drop-ratio %DROP% --email "%EMAIL%"
) else (
  py -3 -m src.vacation_seeker.main add-watch --destination "%DEST%" --adults %ADULTS% --children-ages "%CHILDREN%" --drop-ratio %DROP% --email "%EMAIL%" --departure-from "%DATE_FROM%" --departure-to "%DATE_TO%"
)
if errorlevel 1 (
  echo [VacationSeeker] Blad tworzenia watcha.
  exit /b 1
)

echo [VacationSeeker] Start monitoringu rodzinnego. Raport: "%TARGET%\report.html", co %INTERVAL% min.
py -3 -m src.vacation_seeker.main schedule --target-folder "%TARGET%" --refresh-minutes %INTERVAL%
endlocal
