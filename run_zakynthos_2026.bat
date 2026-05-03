@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Raport jeden HTML: oferty z feedów (Zakynthos + okno dat + miejscowości) + na końcu macierz lotów
rem (Kayak / Skyscanner / Google Flights) dla kombinacji wylotów i powrotów + linki hoteli (Booking / Google / Kayak).
rem Brak API cenowych tych serwisów — tylko gotowe wyszukiwania w przeglądarce.

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=output"

set "VACATION_APPEND_METASEARCH=true"
set "VACATION_FLIGHT_MATRIX_DEPARTURES=2026-06-27,2026-06-28,2026-06-29"
set "VACATION_FLIGHT_MATRIX_RETURNS=2026-07-03,2026-07-04,2026-07-05"
set "VACATION_HOTEL_STAY_CHECKIN=2026-06-27"
set "VACATION_HOTEL_STAY_CHECKOUT=2026-07-05"
set "VACATION_HOTEL_TOWNS=Argassi,Alikanas,Alykes"
set "VACATION_REPORT_HOTEL_AREAS=Argassi,Alikanas,Alykes"

set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "SystemRoot=C:\Windows"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "TS="
if exist "%PS_EXE%" (
  for /f "usebackq delims=" %%i in (`"%PS_EXE%" -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul`) do set "TS=%%i"
)
if not defined TS set "TS=fallback_%RANDOM%"
set "LOG_FILE=%LOG_DIR%\run_zakynthos_%TS%.log"
set "STDOUT_LOG=%LOG_DIR%\run_zakynthos_console_%TS%.log"

echo [VacationSeeker] Zakynthos 2026: raport + metasearch do "%TARGET%\report_Zakynthos.html"
echo [VacationSeeker] Log: "%LOG_FILE%" | stdout: "%STDOUT_LOG%"

py -3 -m src.vacation_seeker.main run-once ^
  --target-folder "%TARGET%" ^
  --location-report ^
  --destination Zakynthos ^
  --departure-from 2026-06-27 ^
  --departure-to 2026-06-29 ^
  --return-from 2026-07-03 ^
  --return-to 2026-07-05 ^
  --adults 2 ^
  --children-ages 11,13 ^
  --hotel-areas Argassi,Alikanas,Alykes ^
  --log-file "%LOG_FILE%" >> "%STDOUT_LOG%"

if errorlevel 1 (
  echo [VacationSeeker] Blad — zobacz konsola / "%STDOUT_LOG%"
  pause
  exit /b 1
)
echo [VacationSeeker] OK: "%TARGET%\report_Zakynthos.html"
pause
endlocal
