# Demo: bot vs zasady "challenge'u" prop firmy

Nasza jedyna sprawdzona strategia (9 reguł trendu BTC, ta sama co w `btc-trend-demo`) puszczona
codziennie w chmurze pod TYPOWYMI zasadami tzw. prop firmy: konto 10 000 USD (wirtualne), cel
zysku +8%, limit straty dziennej 5%, limit straty całkowitej 10%. Przy złamaniu limitu próba się
kończy i następnego dnia startuje nowa, od zera. Po zdaniu: konto "sfinansowane" (80% zysku dla
"tradera", limit całkowity liczony od szczytu), aż do kolejnego złamania limitu.

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

Backtest naszej (jedynej sprawdzonej w 7-letnim teście) strategii pod tymi regułami, 2020–2026:

| | Wynik |
|---|---|
| Ukończonych prób ewaluacji | 66 |
| Zdanych | 23 (35%) |
| Kont "sfinansowanych" utraconych po zdaniu | 22 z 23 |
| Symulowana wypłata (80% zysku) | +26 470 USD |
| Szacowany koszt prób (500 zł/próba) | ~33 000 zł (~8 250 USD) |

Zdawalność 35% jest WYŻSZA niż realne 5–14% — bo to był mocny, wielomiesięczny rynek byka na BTC
(2020–2021, 2023–2024). W realnym, mieszanym rynku i u realnej firmy wynik będzie gorszy.
Prawie każde zdane konto ostatecznie traciło status "sfinansowane" (22 z 23) — co pasuje do
statystyki "tylko 1–3% zostaje stałymi płatnymi traderami".

## Pliki

- `bot.py` — cała logika (biblioteka standardowa Pythona)
- `.github/workflows/daily.yml` — harmonogram (GitHub Actions)
- `data/` — stan próby, historia salda, lista prób (zapisywane automatycznie)
- `docs/index.html` — raport (generowany automatycznie)

## Wyłączenie

GitHub → zakładka **Actions** → workflow „dzienny-bot" → menu „…" → **Disable workflow**.
