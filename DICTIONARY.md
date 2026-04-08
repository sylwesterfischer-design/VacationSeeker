# Slownik skrotow (VacationSeeker)

- `AI` - All Inclusive (pelne wyzywienie + napoje)
- `HB` - Half Board (sniadanie + obiadokolacja)
- `BB` - Bed & Breakfast (nocleg + sniadanie)
- `RO` - Room Only (sam nocleg)

- `Cena/os nominalna` - cena na osobe bez doszacowanych kosztow dodatkowych
- `Koszt realny/os` - cena na osobe z doliczeniem kosztow (np. bagaz, transfer, wydatki lokalne)
- `Total` - cena calej oferty, jak podana przez zrodlo

- `Score nominalny` - ranking oparty glownie o cene bazowa
- `Score realny` - ranking oparty glownie o koszt realny

## Uwaga o `IRD`
`IRD` nie jest obecnie standardowym polem w modelu aplikacji.
Jesli pojawia sie w danych z konkretnego zrodla, trzeba dopisac mapowanie na etapie normalizacji.
