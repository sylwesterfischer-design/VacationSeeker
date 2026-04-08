# VacationSeeker Starter

Starter agenta do zbierania okazji last minute z wielu zrodel, normalizacji, scoringu i prezentacji w HTML.
Slownik skrotow znajdziesz w `DICTIONARY.md` oraz na koncu raportu HTML.
Baza dla znajomego / prompt (Tequila API, SMTP, RSS, Cursor): `PROMPT_BAZA_KUMPLA.md`.

## Co jest gotowe
- SQLite schema pod oferty i snapshoty cen.
- Pipeline: collector -> normalizer -> scorer -> aggregator.
- Ranking osobno dla 1 i 2 osob.
- Dwa rankingi cen: nominalny oraz realny koszt calkowity/os.
- Okna terminow: 0-3, 4-7, 8-14, 15-30, 31-56 dni.
- Alerty webhook (Discord/Slack/Teams przez incoming webhook).
- Raport HTML: `output/report.html`.
- Scheduler odswiezania co N minut.
- Family Watch: profil celu (np. Irlandia 2+2) i alert email gdy pojawi sie najlepsza oferta.
- Alert **TOP OF THE TOP** (e-mail): po kazdym `run-once` / `run_report.bat` — zestawienie trzech „liderow” (najtanszy koszt realny/os, najnizsza cena nominalna/os, najwyzszy score) w horyzoncie raportu; **bez duplikatow** dopoki te same trzy oferty sa na czole (hash w `meta_kv`).

## Szybki start
1. Python 3.11+
2. Instalacja:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
   - `pip install -r requirements.txt`
3. Uruchom raz:
   - `python -m src.vacation_seeker.main run-once`
4. Uruchom scheduler:
   - `python -m src.vacation_seeker.main schedule`

## Watcher (destynacja + rodzina + email)
Dodaj profil monitorowania:
- `py -3 -m src.vacation_seeker.main add-watch --destination Irlandia --adults 2 --children-ages 12,14 --drop-ratio 0.5 --email sylwester.fischer@gmail.com --departure-from 2026-06-01 --departure-to 2026-08-31`

Podglad aktywnych watchy:
- `py -3 -m src.vacation_seeker.main list-watches`

Co oznacza "najlepsza oferta" w watcherze:
- dla pasujacych ofert liczony jest koszt rodziny = `total_trip_cost_pln * liczba_podroznych`
- system bierze mediane kosztu dla destynacji
- alert idzie, gdy najlepsza oferta spada co najmniej o `drop_ratio` (np. 0.5 = 50%) vs mediana
- opcjonalnie mozna ustawic sufit: `--max-total-pln`
- w mailu dostajesz ostrzezenie o ryzyku ukrytych kosztow (bagaz/transfer)
- opcjonalnie mozna ograniczyc zakres dat wylotu: `--departure-from` i `--departure-to`

## Windows / PowerShell (najprosciej)
Jesli uruchamiasz z innego katalogu i dostajesz `No module named 'src'`, odpal gotowe pliki:
- `run_report.bat` - jednorazowe generowanie raportu
- `schedule_report.bat` - scheduler

Przyklady:
- `run_report.bat`
- `run_report.bat D:\Raporty\Vacation`
- `run_report.bat output 2026-04-01 2026-04-07`
- `run_report.bat output 2026-04-01 2026-04-07 Majorka`
- `run_report.bat output "" "" "" hold` (zatrzymuje okno po sukcesie)
- `schedule_report.bat D:\Raporty\Vacation 30`
- `add_watch_family.bat Irlandia sylwester.fischer@gmail.com 0.5`
- `run_family_watch.bat` (interaktywnie pyta o kierunek)
- `run_family_watch.bat Majorka sylwester.fischer@gmail.com 2 2026-06-15 2026-08-31 0.5 30 output`
- `run_raport_location.bat Zakynthos 2026-06-27 2026-07-05 2 12 14 target`
- `run_raport_location_gui.bat` — okno GUI (pole **lokalizacji**, **zakres dat wylotu** od–do, **zakres powrotu** od–do, dorośli + dzieci); zapis do `report_<Kierunek>.html` (nie nadpisuje `report.html` z `run_report.bat`)

**Raport lokalizacyjny** zapisuje sie jako osobny plik, np. `target/report_Zakynthos.html`, zeby nie nadpisywac ogolnego `report.html`. Z linii komend: `py -3 -m src.vacation_seeker.main run-once --target-folder target --location-report --destination Zakynthos ...`

Gdy **brak ofert** w feedach po filtrze (kierunek + daty), na dole raportu pojawia sie tabela z linkami do **Kayak** (najtaniej / najszybciej), **Skyscanner** i **Google Flights** (elastycznie, z przesiadkami). Linki uwzgledniaja **liczbe doroslych i wieki dzieci** z parametrow raportu (`--adults`, `--children-ages`), a nie „jedna osoba” / „wszyscy jako dorośli”. Lotnisko startowe: `VACATION_ORIGIN_AIRPORT` (domyslnie `WAW`).

Parametry `run_family_watch.bat`:
- `kierunek email dorosli data_od data_do prog interval_min target_folder`
- dzieci sa domyslnie `12,14` (dla innych wiekow uzyj `add-watch`)

Parametry `run_report.bat`:
- `target_folder [data_od data_do kierunek]`
- opcjonalny 5. parametr `hold` zostawia okno otwarte
- logi: **audyt** `logs\run_report_*.log` (`--log-file`: START/END, traceback) + kopia `run_report_last.log`; **stdout** Pythona w `logs\run_report_console_*.log`; **pasek postepu (tqdm)** i stderr na **oknie konsoli** (bez `2>&1` do pliku — patrz `docs/Loggers.md` i `.cursorrules_CodingImprovment` § postep BEZWZGLĘDNIE)

**Observability (run-once z CLI):** `--log-file PATH` (audyt START/END, traceback), `--dry-run` (bez DB/HTML/maili), `--verbose-items` (kazdy kolektor), `--no-progress` (wylacza tqdm: kolektory + walidacja linkow). Pelny opis: `docs/Loggers.md` (zgodnosc z `.cursorrules_CodingImprovment`).

Parametry `run_raport_location.bat`:
- `lokalizacja data_wylotu_od data_wylotu_do data_powrotu_od data_powrotu_do dorosli dziecko1_wiek dziecko2_wiek target_folder`
- raport dodatkowo pokazuje sugestie ceny dla wariantu +/- 1 dzien
- wyjscie: `target_folder/report_<lokalizacja>.html` (flaga `--location-report` w wywolaniu Pythona)

## Konfiguracja (zmienne srodowiskowe)
- `VACATION_DB_PATH` (domyslnie: `vacation_seeker.db`)
- `VACATION_REPORT_PATH` (domyslnie: `output/report.html`)
- `VACATION_REFRESH_MINUTES` (domyslnie: `60`)
- `VACATION_WEBHOOK_URL` (opcjonalnie)
- `VACATION_ALERT_EMAIL` (domyslny email alertow, fallback)
- `VACATION_TOP_EMAIL` (opcjonalnie — adres na alert **TOP OF THE TOP**; jesli pusty, uzywany jest `VACATION_ALERT_EMAIL`)
- `VACATION_TOP_EMAIL_ENABLED` (domyslnie `true` — wysylka tylko gdy skonfigurowany SMTP; mail idzie gdy zmieni sie zestaw 3 liderow: najtanszy real / najtanszy nominal / najwyzszy score)
- `VACATION_SMTP_HOST`
- `VACATION_SMTP_PORT` (domyslnie 587)
- `VACATION_SMTP_USER`
- `VACATION_SMTP_PASSWORD`
- `VACATION_SMTP_FROM`
- `VACATION_VALIDATE_OFFER_LINKS` (domyslnie `true`, odrzuca linki z trescia "oferta niedostepna")
- `VACATION_VALIDATION_TIMEOUT_SECONDS` (domyslnie `12`)
- `VACATION_ORIGIN_AIRPORT` (domyslnie `WAW` — lotnisko wylotu w linkach Kayak/Google gdy brak ofert w feedach)
- `VACATION_PIRACI_FETCH_ARTICLE` (domyslnie `true` — pobieranie HTML artykułu WP, gdy RSS nie ma pelnego terminu, np. „14 - 21 maja”)
- `VACATION_PIRACI_FETCH_MAX` (domyslnie `28` — max liczba stron do pobrania na jeden run)
- `VACATION_PIRACI_FETCH_TIMEOUT` (sekundy na jeden request)
- `VACATION_RAINBOW_MAX_PAGES` (domyslnie `4` — ile stron `r.pl/last-minute` skanowac per run)
- `VACATION_RAINBOW_MAX_OFFERS` (domyslnie `260` — limit ofert z Rainbow)
- `VACATION_RAINBOW_TIMEOUT` (domyslnie `20` sekund na request Rainbow)
- `VACATION_REPORT_HORIZON_MONTHS` (domyslnie `6` — glowne tabele raportu tylko z wylotem w tym horyzoncie; pozniejsze — osobna sekcja „dalszy termin”)

Uwaga: bez SMTP alert mailowy nie wyjdzie (watch nadal dziala, ale bez wysylki).

## Co oznacza "realny koszt"
`total_trip_cost_pln` jest liczony jako:
- `price_per_person_pln`
- `+ baggage_cost_pln` (gdy brak bagazu)
- `+ airport_transfer_cost_pln` (gdy brak transferu)
- `+ local_daily_cost_pln * trip_nights`

To przyblizenie, ktore pomaga wybierac faktycznie tansze oferty, a nie tylko najnizsza cene bazowa.

## Integracje zrodel
Aktualnie podlaczone (6 warstw LIVE w `pipeline.py`; szczegoly w `collectors/live_sources.py` i `collectors/extra_feeds.py`):

**Biura / listingi:**
- `wakacyjni_piraci_rss` (publiczny feed RSS; gdy brak konkretnych dat w RSS, z pobranego HTML probuje wyciagnac m.in. „Wolne terminy znajdziecie do {miesiac genetyw} {rok}” i wtedy zamiast „[brak terminu w RSS…]” wstawia ten fragment jako podpowiedz + szacowany zakres dat)
- `tui_live` (publiczny listing page z osadzonym JSON)
- `rainbow_live` (publiczny listing `r.pl/last-minute`, parsowanie kart ofert SSR)
- `itaka_lastminute_live` (strona `itaka.pl/last-minute`, JSON `__NEXT_DATA__` → lista `rates`)

**RSS okazji (loty/pakiety; bez portali informacyjnych i redakcji podrozniczej bez ofert):**
- `fly4free_rss`
- `holidaypirates_rss` (moze zwrocic 0 przy timeout sieci)

Fallback:
- jesli live zrodla nie zwroca ofert, wlacza sie `mock_feed` (kontroluje to `VACATION_USE_MOCK_FALLBACK`, domyslnie `true`)

Tryb danych widzisz na gorze raportu HTML.
