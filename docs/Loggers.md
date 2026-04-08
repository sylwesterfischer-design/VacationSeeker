# Logowanie — VacationSeeker (Python / BAT)

Źródło prawdy dla tego repozytorium: ten plik + kod w `src/vacation_seeker/run_audit.py`, `main.py`, `pipeline.py`.

## Pliki logów

| Plik | Zawartość |
|------|-----------|
| `logs/run_report_YYYYMMDD_HHMMSS.log` | Jeden przebieg `run_report.bat`: linie BAT (prefiks czasu z PowerShell), stdout/stderr z Pythona, oraz wpisy z `logging` (START/END, traceback). |
| `logs/run_report_last.log` | Kopia ostatniego przebiegu (`copy /y` z BAT). |

Kodowanie: **UTF-8** (`chcp 65001` w BAT, `FileHandler` z `encoding=utf-8` w Pythonie).

## Linie audytu (obowiązkowe dla `run-once`)

W pliku przekazanym przez `--log-file` (oraz na stderr, gdy brak pliku):

- `START run_id=<uuid> argv=<...>`
- `END run_id=<uuid> status=ok code=0` — sukces
- `END run_id=<uuid> status=exception code=1` — wyjątek; w pliku dodatkowo pełny traceback

Stdout z `print()` w pipeline nadal trafia do konsoli; przy `run_report.bat` jest też **dopisywany** do tego samego pliku przez `>>` (łączone wyjście procesu).

## Flagi CLI (`python -m src.vacation_seeker.main run-once`)

| Flaga | Opis |
|-------|------|
| `--log-file PATH` | Append UTF-8: START/END + traceback; timestamp w formatterze `logging`. |
| `--dry-run` | Brak zapisu DB, HTML, webhook, maili TOP/watch; na stderr podsumowanie `[dry-run] scanned_raw=…`. |
| `--verbose-items` | Każdy kolektor: `[item] source_name -> N raw` (stderr + logger). |
| `--no-progress` | Wyłącza `tqdm` / ręczne `%` postępu kolektorów. |

## Postęp (collectors)

- Preferencja: **`tqdm`** na **stderr** (pakiet w `requirements.txt`).
- Gdy `tqdm` nie jest zainstalowane: tekstowy `\rCollectors i/n (pct%)` na stderr.
- Wyłączenie: `--no-progress`.

## BAT → log

- Linie dodawane przez BAT używają **PowerShell** `Get-Date -Format 'yyyy-MM-dd HH:mm:ss'` przed i po wywołaniu `py`.
- Stdout/stderr Pythona: `>> "%LOG_FILE%" 2>&1`.

## Excel / lock / kolejka JSONL

**Nie dotyczy** VacationSeeker (brak zapisu Excel). Gdy w przyszłości pojawi się zapis do plików z lockiem, należy dodać tu wzorzec pending JSONL i metrykę `pending_flushed`.

## Scheduler / GUI

- `schedule` i `add-watch` **nie** dodają automatycznie `RunContext` z pełnym audytem pliku — tylko `run-once` z `main.py`.
- GUI (`gui_location`) wywołuje `run_once(settings)` bez `ctx` (zachowanie jak wcześniej, bez paska tqdm z CLI).

## Odwołanie stylu

Zachowanie ma być spójne z ideą: osobny plik `.log` procesu, START/END, traceback, opcjonalny dry-run i verbose — jak w opisie „observability pack” dla długich skryptów CLI.
