# Baza pod klon / rozszerzenie VacationSeeker (dla znajomego + prompt do Cursora)

Ten plik zbiera to, co i tak jest w repo (`SOURCES_MANIFEST.json`, `README`), plus **Tequila API (Kiwi)** i **mail**, żeby można było od razu planować integrację bez zgadywania.

---

## 1. Co to jest w skrócie

- **VacationSeeker** zbiera oferty z kilku źródeł (kolektory → normalizacja → scoring → HTML + SQLite).
- Lista źródeł i plików: **`SOURCES_MANIFEST.json`** (JSON nie steruje aplikacją — to dokumentacja; prawdziwa logika to **Python**).
- Reguły dla agenta w Cursorze: **`.cursorrulesVacationGeneral`**, **`.cursorrulesVacationDataFeeding.mdc`** (skopiuj do `.cursor/rules/` albo trzymaj w root projektu).
- Logowanie CLI / `run_report.bat`: **`docs/Loggers.md`** (`--log-file`, `--dry-run`, START/END, tqdm).

---

## 2. RSS — nadal ma sens

- W kodzie jest wzorzec **`GenericRssDealCollector`** w `src/vacation_seeker/collectors/extra_feeds.py`.
- Nowy feed RSS = zwykle nowa klasa dziedzicząca po `GenericRssDealCollector` + wpis w `default_extra_collectors()` + aktualizacja `SOURCES_MANIFEST.json`.
- RSS redakcyjny ≠ katalog biura: w modelu to często `package_type=deal_post` — użytkownik weryfikuje link.

---

## 3. Kiwi **Tequila API** (loty) — baza pod rozszerzenie

**Tequila** to API Kiwi.com do wyszukiwania lotów (B2B / partnerzy). Nie zastępuje samo w sobie pakietów biura (TUI/Rainbow), ale daje **twarde ceny lotów** i można je scalać z resztą pipeline’u albo wysyłać w mailu jako „benchmark lotu”.

### Wejście

- Rejestracja / klucz: dokumentacja portalu Kiwi (Tequila) — szukaj **„Tequila API”** / **„Kiwi.com Tequila”** (portal partnerski).
- Typowe elementy integracji:
  - **Location API** — lotniska, miasta, IATA.
  - **Search** — wyszukiwanie lotów (w jedną stronę / powrót / multidestynacja w zależności od produktu).
- **Uwaga:** dostęp bywa ograniczony programem partnerskim; trzeba przeczytać aktualny regulamin i limity (RPM).

### Sugestia zmiennych środowiskowych (własny kolektor)

```text
VACATION_KIWI_TEQUILA_API_KEY=twoj_kluc_z_portalu
VACATION_KIWI_TEQUILA_BASE_URL=https://api.tequila.kiwi.com
```

(Dokładny host i ścieżki endpointów **muszą** pochodzić z aktualnej dokumentacji API — nie kopiuj na ślepo starych tutoriali.)

### Kierunek pracy w kodzie

1. Nowy plik np. `collectors/tequila_flights.py` z klasą `TequilaFlightCollector(BaseCollector)`.
2. Mapowanie odpowiedzi JSON → `RawOffer` (lub osobny typ przed normalizacją, jeśli loty nie pasują 1:1 do hotel+flight).
3. `source_name` np. `kiwi_tequila_live`.
4. Dopisanie kolektora w **`pipeline.py`** obok pozostałych.

---

## 4. Wysyłka maila (SMTP) — już jest w projekcie

Żeby **działały** alerty (watch, TOP OF THE TOP), trzeba ustawić:

```text
VACATION_SMTP_HOST=smtp.gmail.com
VACATION_SMTP_PORT=587
VACATION_SMTP_USER=twoj_mail@gmail.com
VACATION_SMTP_PASSWORD=haslo_aplikacji
VACATION_SMTP_FROM=twoj_mail@gmail.com
VACATION_ALERT_EMAIL=odbiorca@gmail.com
VACATION_TOP_EMAIL=opcjonalnie_inny@domena.pl
```

- Implementacja: `src/vacation_seeker/emailer.py`, wywołania w `pipeline.py` / `top_tier_email.py` / watch.
- Bez SMTP log pokaże, że mail nie wyleci — raport HTML i tak się zbuduje.

**Idea dla znajomego:** po integracji Tequila można w jednym mailu wysłać np. „najtańszy lot z API” + link do najlepszej oferty z biura z raportu (wymaga dopisania małego szablonu w Pythonie).

---

## 5. Gotowy prompt do wklejenia w Cursor (Custom Instructions / chat)

Poniżej blok po polsku — możesz go wkleić jako **regułę projektu** albo pierwszą wiadomość w czacie przy pracy nad tym repo.

```text
Pracujesz nad repozytorium VacationSeeker (Python): agregacja ofert last minute.

Źródła danych (Data Feeding Layers):
- Plik SOURCES_MANIFEST.json opisuje source_name i pliki kolektorów — nie edytuj go jako jedynej „prawdy”, jeśli zmieniasz kod: aktualizuj collectors i manifest razem.
- Kolektory „live”: src/vacation_seeker/collectors/live_sources.py (Wakacyjni Piraci, TUI, Rainbow).
- Kolektory „extra”: src/vacation_seeker/collectors/extra_feeds.py (Fly4free, Holiday Pirates RSS, Itaka last minute).
- Pipeline: src/vacation_seeker/pipeline.py — tu dokładasz nowe kolektory.

RSS: nowe źródło RSS = klasa dziedzicząca po GenericRssDealCollector w extra_feeds.py (lub osobny moduł + import w pipeline).

Kiwi Tequila API: planując integrację lotów, trzymaj klucz w zmiennych środowiskowych (np. VACATION_KIWI_TEQUILA_API_KEY), nie w kodzie. Endpointy i limity bierz z aktualnej dokumentacji Tequila/Kiwi. Wynik mapuj do RawOffer albo osobnej ścieżki normalizacji.

E-mail: SMTP przez zmienne VACATION_SMTP_*; alerty TOP i watch są w pipeline — nie wymyślaj drugiego mailera, rozszerz emailer.py / treści jeśli trzeba.

Zachowaj zgodność z ToS i limitami zapytań; nie commituj sekretów.
```

---

## 6. Checklist dla znajomego

| Krok | Akcja |
|------|--------|
| 1 | `git clone` + `venv` + `pip install -r requirements.txt` |
| 2 | Skopiować reguły `.cursorrules*` do swojego workspace |
| 3 | Uruchomić `python -m src.vacation_seeker.main run-once` |
| 4 | (Opcja) Ustawić SMTP i sprawdzić log `[top]` / watch |
| 5 | (Opcja) Kiwi Tequila: klucz z portalu → nowy kolektor → test na jednym wyszukiwaniu |

---

*Plik pomocniczy; nie zastępuje README ani oficjalnej dokumentacji Kiwi/Tequila.*
