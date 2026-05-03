@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Pełne ścieżki (jak run_report.bat) — PATH bywa obcięty przy podwójnym kliknięciu z Eksploratora.
if not defined SystemRoot set "SystemRoot=C:\Windows"
set "SYS32=%SystemRoot%\System32"
set "CHCP_EXE=%SYS32%\chcp.com"
set "PS_EXE=%SYS32%\WindowsPowerShell\v1.0\powershell.exe"
if exist "%CHCP_EXE%" (
  "%CHCP_EXE%" 65001 > nul 2>&1
) else (
  echo [VacationSeeker] Ostrzezenie: brak "%CHCP_EXE%" — kodowanie konsoli bez zmian.
)

rem Raport HTML: feedy + macierz lotów + Booking hotele. Czas: zwykle 1–3 min (sieć + walidacja linków).
rem NIE przekierujemy stdout do pliku — wtedy widać postęp (tqdm na stderr + komunikaty). Audyt: --log-file.

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=output"
set "REPORT=%~dp0%TARGET%\report_Zakynthos.html"

set "VACATION_APPEND_METASEARCH=true"
set "VACATION_FLIGHT_MATRIX_DEPARTURES=2026-06-27,2026-06-28,2026-06-29"
set "VACATION_FLIGHT_MATRIX_RETURNS=2026-07-03,2026-07-04,2026-07-05"
set "VACATION_HOTEL_STAY_CHECKIN=2026-06-27"
set "VACATION_HOTEL_STAY_CHECKOUT=2026-07-05"
set "VACATION_HOTEL_TOWNS=Argassi,Alikanas,Alykes"
set "VACATION_REPORT_HOTEL_AREAS=Argassi,Alikanas,Alykes"

set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "TS="
if exist "%PS_EXE%" (
  for /f "usebackq delims=" %%i in (`"%PS_EXE%" -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul`) do set "TS=%%i"
)
if not defined TS set "TS=fallback_%RANDOM%"
set "LOG_FILE=%LOG_DIR%\run_zakynthos_%TS%.log"

echo.
echo ============================================================
echo VacationSeeker — Zakynthos 2026
echo ============================================================
echo Katalog roboczy: "%CD%"
echo Plik raportu (powstanie na koniec, nie wczesniej^): 
echo   %REPORT%
echo Audyt (START/END, traceback): "%CD%\%LOG_FILE%"
echo.
echo Zajmuje to zwykle ok. 1 do 3 minut — najpierw kolektory (RSS/TUI/itd.^), potem zapis HTML.
echo Postep: pasek "Collectors" / walidacja (tqdm na stderr^) oraz linie [item] (--verbose-items^).
echo Okno ZAMYKA sie dopiero po komunikacie ponizej i nacisnieciu klawisza (pause^).
echo ============================================================
echo.

echo [VacationSeeker] Sprawdzanie: py -3 --version
py -3 --version
if errorlevel 1 (
  echo [VacationSeeker] BLAD: nie uruchomiono "py -3". Zainstaluj Python Launcher lub dodaj Python do PATH.
  echo.
  pause
  exit /b 1
)

echo.
echo [VacationSeeker] --- START generowania (Python -u = bez buforowania stdout^) ---
echo.

rem Bez przekierowania stdout — widzisz przebieg; stderr zostaje na konsoli (tqdm). Zgodnie z docs/Loggers.md.
py -3 -u -m src.vacation_seeker.main run-once ^
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
  --verbose-items ^
  --log-file "%LOG_FILE%"
if errorlevel 1 (
  echo.
  echo [VacationSeeker] BLAD generowania Pythona. Zobacz komunikaty powyzej oraz log: "%CD%\%LOG_FILE%"
  echo.
  pause
  exit /b 1
)
echo.
echo [VacationSeeker] --- Python zakonczyl sie pomyslnie (exit code 0^) ---

if not exist "%REPORT%" (
  echo [VacationSeeker] BLAD: Python zakonczyl sie code=0, ale brak pliku:
  echo   %REPORT%
  echo Sprawdz --target-folder i uprawnienia zapisu do folderu "%TARGET%".
  echo.
  pause
  exit /b 1
)

echo.
echo [VacationSeeker] OK — raport zapisany:
echo   %REPORT%
for %%A in ("%REPORT%") do echo   Rozmiar: %%~zA bajtow, data: %%~tA
echo.
echo [VacationSeeker] Pelny audyt w: "%CD%\%LOG_FILE%"
echo.
pause
endlocal
