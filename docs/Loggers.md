# Logowanie — VacationSeeker (Python / BAT)

Źródło prawdy dla tego repozytorium: ten plik + kod w `src/vacation_seeker/run_audit.py`, `main.py`, `pipeline.py`, `availability_validator.py`.

**Zgodność z regułami projektu:** sekcja **„Logowanie i wizualizacja wykonania postępu skryptu (BEZWZGLĘDNIE)”** w `.cursorrules_CodingImprovment` — audyt START/END, osobny plik logu, `tqdm` / `%` na stderr, `--verbose-items`, `--dry-run`, `--no-progress`, dokumentacja tutaj i w README.

## Pliki logów

| Plik | Zawartość |
|------|-----------|
| `logs/run_report_YYYYMMDD_HHMMSS.log` | **Audyt** z `--log-file`: wpisy `logging` (START/END, traceback, opcj. `[item]` przy `--verbose-items`). **Bez** pełnego duplikatu stderr (żeby uniknąć kolizji uchwytu z przekierowaniem cmd). |
| `logs/run_report_console_YYYYMMDD_HHMMSS.log` | **Stdout** Pythona z `run_report.bat` (`print` telemetry, `OK. Report` itd.). |
| `logs/run_report_last.log` | Kopia ostatniego pliku **audytu** (`copy /y` z BAT). |

Kodowanie: **UTF-8** (`chcp 65001` w BAT, `FileHandler` z `encoding=utf-8` w Pythonie).

## Linie audytu (obowiązkowe dla `run-once`)

W pliku przekazanym przez `--log-file` (oraz na stderr, gdy brak pliku):

- `START run_id=<uuid> argv=<...>`
- `END run_id=<uuid> status=ok code=0` — sukces
- `END run_id=<uuid> status=exception code=1` — wyjątek; w pliku dodatkowo pełny traceback

**Konsola (stderr)** przy `run_report.bat`: **nie** jest przekierowywana do pliku (`2>&1` byłoby błędem) — tam widać **`tqdm`** (kolektory + walidacja linków) oraz tracebacki. Stdout idzie do `run_report_console_*.log` przez `>>`.

## Flagi CLI (`python -m src.vacation_seeker.main run-once`)

| Flaga | Opis |
|-------|------|
| `--log-file PATH` | Append UTF-8: START/END + traceback; timestamp w formatterze `logging`. |
| `--dry-run` | Brak zapisu DB, HTML, webhook, maili TOP/watch; na stderr podsumowanie `[dry-run] scanned_raw=…`. |
| `--verbose-items` | Każdy kolektor: `[item] source_name -> N raw` (stderr + logger). |
| `--no-progress` | Wyłącza `tqdm` / ręczne `%` postępu kolektorów. |

## Postęp (collectors + walidacja linków)

- **Kolektory źródeł:** `tqdm` na **stderr** (`desc="Collectors"`), fallback `\rCollectors i/n (pct%)` gdy brak `tqdm`.
- **Walidacja dostępności linków** (`validate_offer_links`): drugi pasek `tqdm` na stderr (`desc="Link validation"`, `unit="url"`), ten sam fallback procentowy bez `tqdm`.
- Wyłączenie obu: **`--no-progress`**.

## BAT → log

- Linie dodawane przez BAT używają **PowerShell** `Get-Date -Format 'yyyy-MM-dd HH:mm:ss'` przed i po wywołaniu `py`.
- **Nie** używaj `>> "%LOG_FILE_AUDYT%" 2>&1` — ten sam plik co `--log-file` powoduje **PermissionError** w Pythonie; **nie** przekierowuj stderr do pliku, jeśli ma być widoczny **pasek tqdm** (wymaga prawdziwej konsoli).
- Wzorzec `run_report.bat`: `py ... --log-file "%LOG_FILE%" >> "%STDOUT_LOG%"` (tylko stdout do pliku konsoli; stderr = okno cmd).

## Excel / lock / kolejka JSONL

**Nie dotyczy** VacationSeeker (brak zapisu Excel). Gdy w przyszłości pojawi się zapis do plików z lockiem, należy dodać tu wzorzec pending JSONL i metrykę `pending_flushed`.

## Scheduler / GUI

- `schedule` i `add-watch` **nie** dodają automatycznego `RunContext` z pełnym audytem pliku — tylko `run-once` z `main.py`.
- GUI (`gui_location`) wywołuje `run_once(settings, ctx)` z `RunContext(progress_callback=…)`, `no_progress=True` (bez tqdm na stderr) oraz **pasek `ttk.Progressbar`** w oknie — fazy: kolektory, walidacja linków, przygotowanie, przetwarzanie raportu (1–4).

## Odwołanie stylu

Zachowanie ma być spójne z ideą: osobny plik `.log` audytu, START/END, traceback, opcjonalny dry-run i verbose, **postęp current/total na stderr** — jak w opisie „observability pack” w `.cursorrules_CodingImprovment` oraz jak w `insert_from_mt5_html.py` / skryptach backfill (wzorcowo).
