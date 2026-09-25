# Demo: bot vs zasady "challenge'u" prop firmy

Nasza jedyna sprawdzona strategia (9 reguł trendu, ta sama logika co w pierwszej wersji na BTC)
puszczona codziennie w chmurze na **S&P 500** (indeks ^GSPC, u brokerów CFD "US500.cash") pod
TYPOWYMI zasadami tzw. prop firmy: konto 10 000 USD (wirtualne), cel zysku +8%, limit straty
dziennej 5%, limit straty całkowitej 10%. Przy złamaniu limitu próba się kończy i następnego dnia
startuje nowa, od zera. Po zdaniu: konto "sfinansowane" (80% zysku dla "tradera", limit całkowity
liczony od szczytu), aż do kolejnego złamania limitu. Modelowany typ konta: "Swing" (u FTMO
dostępny w 2-Step) — zwolniony z obowiązkowego zamykania pozycji na weekend.

Zmiana z BTC na S&P 500 (2026-09-25): większość realnych traderów zarabia na indeksach, nie na
krypto; koszty na S&P 500 są rząd wielkości niższe (FTMO: zero prowizji, spread ~0,01%
vs ~0,13% modelowane wcześniej dla BTC); S&P 500 prawie nigdy nie rusza się >=5% w jeden dzień
(BTC robił to średnio co ~24 dni), więc limit dzienny straty jest rzadziej łamany przypadkiem.

**To symulacja na wirtualnych pieniądzach. Nie ma tu żadnej prawdziwej firmy, konta ani zleceń.**
Zasady są reprezentatywne dla branży (na podstawie publicznych statystyk, patrz niżej), nie kopią
żadnej konkretnej firmy.

**Wyniki:** GitHub Pages → link w ustawieniach repozytorium (Settings → Pages), aktualizacja raz
dziennie ok. 00:10 UTC.

## Dlaczego to demo powstało

Sprawdziliśmy, czy "zdanie egzaminu i handel cudzym kapitałem" to sposób na ominięcie problemu
kosztów transakcyjnych w day tradingu. Realne statystyki branżowe: zdawalność 5–14%, a spośród
zdających tylko ~45% dostaje choć jedną wypłatę (łącznie ~7% "od zakupu do wypłaty"), stałych,
długoterminowo płatnych traderów jest 1–3%. 60–70% niezdanych prób kończy się na złamaniu limitu
straty, nie na niedobiciu do celu.

Backtest naszej strategii pod tymi regułami na S&P 500, 2001–2026 (24 lata, dane dzienne ^GSPC):

| | Wynik |
|---|---|
| Ukończonych prób ewaluacji | 3 |
| Zdanych | 2 (67%) |
| Kont "sfinansowanych" utraconych po zdaniu | 1 z 2 |
| Konto obecnie aktywne, saldo (niezrealizowane) | +5 531 USD (od próby #2, wciąż trwa) |
| Szacowany koszt prób (165 USD/próba) | 330 USD |

**Uwaga na próbkę: 3 ukończone próby w 24 lata to za mało, by cokolwiek statystycznie wnioskować**
o zdawalności — to jakościowa obserwacja, nie twardy wynik. Liczy się mechanizm: S&P 500 prawie
nigdy nie rusza się >=5% w jeden dzień, więc limit dzienny straty rzadko bywa złamany przypadkiem
(inaczej niż na BTC, gdzie to normalne raz na ~24 dni) — stąd dłuższe, spokojniejsze przebiegi.
Poprzedni backtest na BTC (2020–2026, 66 ukończonych prób, zdawalność 35%, +26 470 USD symulowanej
wypłaty przy ~8 250 USD kosztu prób) pozostaje w historii repo jako punkt odniesienia, ale bot już
na nim nie działa.

## Pliki

- `bot.py` — cała logika (biblioteka standardowa Pythona)
- `.github/workflows/daily.yml` — harmonogram (GitHub Actions)
- `data/` — stan próby, historia salda, lista prób (zapisywane automatycznie)
- `docs/index.html` — raport (generowany automatycznie)

## Wyłączenie

GitHub → zakładka **Actions** → workflow „dzienny-bot" → menu „…" → **Disable workflow**.
