@echo off
setlocal
cd /d "%~dp0"

set "LOCATION=%~1"
if "%LOCATION%"=="" set /p LOCATION=Podaj kierunek (np. Zakynthos): 
if "%LOCATION%"=="" set "LOCATION=Zakynthos"

set "DEP=%~2"
if "%DEP%"=="" set /p DEP=Data wylotu (YYYY-MM-DD): 
set "RET=%~3"
if "%RET%"=="" set /p RET=Data powrotu (YYYY-MM-DD): 

set "ADULTS=%~4"
if "%ADULTS%"=="" set "ADULTS=2"
set "CHILD1=%~5"
if "%CHILD1%"=="" set "CHILD1=12"
set "CHILD2=%~6"
if "%CHILD2%"=="" set "CHILD2=14"
set "CHILDREN=%CHILD1%,%CHILD2%"
set "TARGET=%~7"
if "%TARGET%"=="" set "TARGET=target"

echo [VacationSeeker] Raport lokalizacyjny: %LOCATION% ^| wylot %DEP% powrot %RET% ^| dorosli=%ADULTS% dzieci=%CHILD1%+%CHILD2%
echo [VacationSeeker] Plik: report_%LOCATION%.html (osobny od report.html)
py -3 -m src.vacation_seeker.main run-once --target-folder "%TARGET%" --location-report --destination "%LOCATION%" --departure-from "%DEP%" --departure-to "%DEP%" --return-from "%RET%" --return-to "%RET%" --adults %ADULTS% --children-ages "%CHILDREN%"
if errorlevel 1 (
  echo [VacationSeeker] Blad generowania raportu lokalizacyjnego.
  pause
  exit /b 1
)
echo [VacationSeeker] OK. Raport: "%TARGET%\report_%LOCATION%.html"
pause
endlocal
