@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Pełne ścieżki: u niektórych profili PATH nie zawiera System32 — wtedy „powershell/chcp nie znaleziono”.
if not defined SystemRoot set "SystemRoot=C:\Windows"
set "SYS32=%SystemRoot%\System32"
set "CHCP_EXE=%SYS32%\chcp.com"
set "PS_EXE=%SYS32%\WindowsPowerShell\v1.0\powershell.exe"
if exist "%CHCP_EXE%" (
  "%CHCP_EXE%" 65001 > nul 2>&1
) else (
  echo [VacationSeeker] Ostrzezenie: brak "%CHCP_EXE%" — kodowanie konsoli bez zmian.
)

set "TARGET=%~1"
if "%TARGET%"=="" (
  if exist "target" (
    set "TARGET=target"
  ) else (
    set "TARGET=output"
  )
)
set "DATE_FROM=%~2"
set "DATE_TO=%~3"
set "DEST=%~4"
set "HOLD=%~5"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "TS="
if exist "%PS_EXE%" (
  for /f "usebackq delims=" %%i in (`"%PS_EXE%" -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul`) do set "TS=%%i"
)
if not defined TS (
  for /f "tokens=2 delims==" %%v in ('"%SYS32%\wbem\WMIC.exe" os get localdatetime /value 2^>nul') do set "LDT=%%v"
  if defined LDT set "TS=%LDT:~0,8%_%LDT:~8,6%"
)
if not defined TS set "TS=fallback_%RANDOM%"

set "LOG_FILE=%LOG_DIR%\run_report_%TS%.log"
set "LAST_LOG=%LOG_DIR%\run_report_last.log"
set "STDOUT_LOG=%LOG_DIR%\run_report_console_%TS%.log"

echo [VacationSeeker] Generowanie raportu do "%TARGET%\report.html"
echo [VacationSeeker] Log audytu UTF-8: "%LOG_FILE%"
echo [VacationSeeker] Stdout/stderr Pythona: "%STDOUT_LOG%"

if exist "%PS_EXE%" (
  "%PS_EXE%" -NoProfile -Command "$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'; Add-Content -LiteralPath '%CD%\%LOG_FILE%' -Encoding utf8 -Value ($ts + ' BAT run_report.bat — przed Python')"
) else (
  echo %date% %time% BAT run_report.bat — przed Python (powershell niedostepny, brak wpisu PS do logu) >> "%LOG_FILE%"
)

rem NIE przekierowuj do tego samego pliku co --log-file: cmd trzyma uchwyt pliku i Python dostaje PermissionError przy FileHandler.
if "%DATE_FROM%"=="" (
  py -3 -m src.vacation_seeker.main run-once --target-folder "%TARGET%" --log-file "%LOG_FILE%" >> "%STDOUT_LOG%" 2>&1
) else (
  py -3 -m src.vacation_seeker.main run-once --target-folder "%TARGET%" --departure-from "%DATE_FROM%" --departure-to "%DATE_TO%" --destination "%DEST%" --log-file "%LOG_FILE%" >> "%STDOUT_LOG%" 2>&1
)

if errorlevel 1 (
  if exist "%PS_EXE%" (
    "%PS_EXE%" -NoProfile -Command "$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'; Add-Content -LiteralPath '%CD%\%LOG_FILE%' -Encoding utf8 -Value ($ts + ' BAT run_report.bat — py zakonczyl code=ERROR; zobacz tez console log')"
  ) else (
    echo %date% %time% BAT run_report.bat — py ERROR >> "%LOG_FILE%"
  )
  copy /y "%LOG_FILE%" "%LAST_LOG%" > nul
  echo [VacationSeeker] Blad uruchomienia.
  echo [VacationSeeker] Audyt: "%LOG_FILE%"
  echo [VacationSeeker] Konsola Pythona zapisana: "%STDOUT_LOG%"
  type "%STDOUT_LOG%" 2>nul
  pause
  exit /b 1
)

if exist "%PS_EXE%" (
  "%PS_EXE%" -NoProfile -Command "$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'; Add-Content -LiteralPath '%CD%\%LOG_FILE%' -Encoding utf8 -Value ($ts + ' BAT run_report.bat — py zakonczyl code=0')"
) else (
  echo %date% %time% BAT run_report.bat — py OK >> "%LOG_FILE%"
)

copy /y "%LOG_FILE%" "%LAST_LOG%" > nul
echo [VacationSeeker] OK.
echo [VacationSeeker] Ostatni log audytu: "%LAST_LOG%"
echo [VacationSeeker] Pelny zrzut konsoli: "%STDOUT_LOG%"
if "%HOLD%"=="hold" pause
endlocal
