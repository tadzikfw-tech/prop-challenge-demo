#!/usr/bin/env python3
"""Demo: nasza (jedyna sprawdzona) strategia trendowa BTC pod typowymi zasadami
"challenge'u" prop firmy. Raz dziennie, tylko biblioteka standardowa.

WAŻNE: to symulacja na WIRTUALNYCH pieniądzach, bez żadnej prawdziwej firmy,
prawdziwego konta ani prawdziwych zleceń. Zasady (cel zysku, limity strat) są
reprezentatywne dla typowych firm (np. FTMO-style), nie kopią żadnej konkretnej.

STRATEGIA ZABLOKOWANA (nie zmieniamy jej w trakcie testu) - te same 9 reguł
trendu co w bocie "btc-trend-demo": każda głosuje "trend rośnie" (1) / "nie" (0),
udział BTC w koncie = (głosy/9) x 50%. Bez dźwigni, bez shortów.

Dlaczego 50%, nie 100%: backtest 2020-2026 pod tymi samymi zasadami pokazał, że
100% ekspozycji i 50% dają podobny wynik finansowy netto, ale przy 50% mniejszy
odsetek dni łamie limit dzienny (sam BTC potrafi spaść >=5% w jeden dzień średnio
raz na ok. 24 dni - przy pełnej ekspozycji to od razu koniec próby). Niższe
poziomy (20-35%) wypadały w backteście "lepiej" tylko dlatego, że próbka prób
była zbyt mała, by cokolwiek z niej wnioskować. 50% to ostatnia decyzja przed
zablokowaniem - dalej reguł (w tym tego mnożnika) już nie zmieniamy.

ZASADY "CHALLENGE'U" (typowe, nie żadnej konkretnej firmy):
  - wirtualny kapitał konta: 10 000 USD
  - cel zysku (faza ewaluacji): +8%
  - limit straty dziennej: 5% (liczony od salda na koniec poprzedniego dnia)
  - limit straty całkowitej: 10% od startu próby (faza ewaluacji),
    10% od SZCZYTU konta (faza "sfinansowana" - trailing, jak u wielu firm)
  - podział zysku na koncie "sfinansowanym": 80% dla tradera / 20% dla firmy
  - złamanie limitu = koniec próby/konta, start od nowa następnego dnia
"""
import os, json, csv, time, datetime, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
STATE = os.path.join(DATA, "state.json")
ATTEMPTS = os.path.join(DATA, "attempts.csv")
HIST = os.path.join(DATA, "history.csv")

CAPITAL = 10_000.0
TARGET_PROFIT = 0.08
DAILY_LOSS_LIMIT = 0.05
EVAL_MAX_LOSS = 0.10
FUNDED_MAX_LOSS = 0.10           # trailing od szczytu
PROFIT_SPLIT = 0.80
FEE_PLN = 500.0                  # szacunkowa, poglądowa opłata za jedną próbę
USD_PLN = 4.0
FEE_USD = FEE_PLN / USD_PLN
DAY = 86_400_000


# ------------------------------------------------------------------ strategia (zablokowana)
def ema(v, span):
    k, out = 2.0 / (span + 1), [v[0]]
    for x in v[1:]:
        out.append(k * x + (1 - k) * out[-1])
    return out


def r_sma(c, n):
    out, s = [], 0.0
    for i, x in enumerate(c):
        s += x
        if i >= n:
            s -= c[i - n]
        out.append(1.0 if i >= n - 1 and x > s / n else 0.0)
    return out


def r_cross(c, f, s):
    a, b = ema(c, f), ema(c, s)
    return [1.0 if x > y else 0.0 for x, y in zip(a, b)]


def r_donchian(c, n_in, n_out):
    out, cur = [], 0.0
    for i, x in enumerate(c):
        if cur == 0.0 and i >= n_in and x > max(c[i - n_in:i]):
            cur = 1.0
        elif cur == 1.0 and i >= n_out and x < min(c[i - n_out:i]):
            cur = 0.0
        out.append(cur)
    return out


def r_mom(c, n):
    return [1.0 if i >= n and x > c[i - n] else 0.0 for i, x in enumerate(c)]


RULES = [
    ("Cena powyżej średniej z 50 dni", lambda c: r_sma(c, 50)),
    ("Cena powyżej średniej z 100 dni", lambda c: r_sma(c, 100)),
    ("Cena powyżej średniej z 150 dni", lambda c: r_sma(c, 150)),
    ("Średnia 10 dni powyżej średniej 30 dni", lambda c: r_cross(c, 10, 30)),
    ("Średnia 20 dni powyżej średniej 50 dni", lambda c: r_cross(c, 20, 50)),
    ("Wybicie z 20-dniowego maksimum (wyjście: 10-dniowe minimum)", lambda c: r_donchian(c, 20, 10)),
    ("Wybicie z 55-dniowego maksimum (wyjście: 20-dniowe minimum)", lambda c: r_donchian(c, 55, 20)),
    ("Cena wyższa niż 30 dni temu", lambda c: r_mom(c, 30)),
    ("Cena wyższa niż 90 dni temu", lambda c: r_mom(c, 90)),
]
FEE, SLIP = 0.001, 0.0003


def compute_series(closes):
    return [f(closes) for _, f in RULES]


EXPOSURE_CAP = 0.50   # maks. udział BTC w koncie (patrz uzasadnienie w docstringu pliku)
WEEKEND_FLAT_FUNDED = True   # konto "sfinansowane": zamykaj pozycje na weekend (reguła realnych firm)


def target_at(series, i):
    return (sum(s[i] for s in series) / len(series)) * EXPOSURE_CAP


def eff_target(phase, ts, series, i):
    """Docelowa ekspozycja z uwzględnieniem reguły weekendowej.
    W realnych firmach (np. FTMO) konto W FAZIE EWALUACJI może trzymać pozycje bez
    ograniczeń, nawet przez weekend. Dopiero na koncie SFINANSOWANYM trzeba je
    zamknąć przed weekendem (piątek) i można otworzyć znów w poniedziałek. Sobota
    i niedziela = płasko (0% BTC), niezależnie od sygnału."""
    if WEEKEND_FLAT_FUNDED and phase == "SFINANSOWANE":
        weekday = datetime.datetime.utcfromtimestamp(ts / 1000).weekday()  # pon=0 ... nie=6
        if weekday >= 4:   # piątek, sobota, niedziela
            return 0.0
    return target_at(series, i)


# ------------------------------------------------------------------ dane
def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "prop-challenge-demo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def src_binance_vision():
    return [(int(r[0]), float(r[4])) for r in _get("https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000")]


def src_binance():
    return [(int(r[0]), float(r[4])) for r in _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000")]


def src_kraken():
    res = _get("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440")["result"]
    rows = [v for k, v in res.items() if k != "last"][0]
    return [(int(r[0]) * 1000, float(r[4])) for r in rows]


def src_bitstamp():
    rows = _get("https://www.bitstamp.net/api/v2/ohlc/btcusd/?step=86400&limit=1000")["data"]["ohlc"]
    return [(int(r["timestamp"]) * 1000, float(r["close"])) for r in rows]


SOURCES = [("Binance", src_binance_vision), ("Binance", src_binance), ("Kraken", src_kraken), ("Bitstamp", src_bitstamp)]


def fetch_daily():
    errs = []
    for name, fn in SOURCES:
        try:
            c = sorted(fn())
            if len(c) >= 300:
                return name, c
            errs.append("%s: za mało świec" % name)
        except Exception as e:
            errs.append("%s: %r" % (name, e))
    raise RuntimeError("Żadne źródło danych nie odpowiada: " + " | ".join(errs))


# ------------------------------------------------------------------ konto (rebalans jak w btc-trend-demo)
def equity(acc, price):
    return acc["cash"] + acc["qty"] * price


def rebalance(acc, price, target, ts, log):
    eq = equity(acc, price)
    delta = target * eq - acc["qty"] * price
    acc["target"] = target
    if abs(delta) < 1.0:
        return
    if delta > 0:
        n = min(delta, acc["cash"] / (1 + FEE))
        px = price * (1 + SLIP)
        q, fee = n / px, n * FEE
        acc["cash"] -= n + fee
        acc["qty"] += q
        side = "KUPNO"
    else:
        px = price * (1 - SLIP)
        q = min(-delta / px, acc["qty"])
        n = q * px
        fee = n * FEE
        acc["cash"] += n - fee
        acc["qty"] -= q
        side = "SPRZEDAŻ"
    log.append((ts, side, px, q, n))


def new_account(capital, price, target, ts):
    acc = dict(cash=capital, qty=0.0, target=0.0)
    rebalance(acc, price, target, ts, [])
    return acc


# ------------------------------------------------------------------ maszyna stanu challenge'u
def new_attempt(no, phase, start_equity, ts, price, series, i):
    acc = new_account(start_equity, price, eff_target(phase, ts, series, i), ts)
    return dict(no=no, phase=phase, start_ts=ts, start_equity=start_equity, peak_equity=start_equity,
                prev_close_equity=start_equity, acc=acc)


def close_attempt(att, ts, price, result, attempts_log, funded_stats):
    eq = equity(att["acc"], price)
    pnl = eq / att["start_equity"] - 1
    days = (ts - att["start_ts"]) / DAY
    attempts_log.append(dict(no=att["no"], phase=att["phase"], start=att["start_ts"], end=ts, days=days,
                              result=result, start_eq=att["start_equity"], end_eq=eq, pnl=pnl))
    if att["phase"] == "SFINANSOWANE":
        profit_usd = max(eq - att["start_equity"], 0.0)
        funded_stats["payout_usd"] += profit_usd * PROFIT_SPLIT
        funded_stats["funded_days"] += days
    return eq


def process_day(state, ts, price, series, i, trades_log, hist, attempts_log, funded_stats):
    att = state["att"]
    acc = att["acc"]
    tgt = eff_target(att["phase"], ts, series, i)
    trades_before = len(trades_log)
    if abs(tgt - acc["target"]) > 1e-9:
        rebalance(acc, price, tgt, ts, trades_log)
    eq = equity(acc, price)
    att["peak_equity"] = max(att["peak_equity"], eq)

    daily_dd = eq / att["prev_close_equity"] - 1
    if att["phase"] == "EWALUACJA":
        total_dd = eq / att["start_equity"] - 1
        loss_ref, loss_limit = att["start_equity"], EVAL_MAX_LOSS
    else:
        total_dd = eq / att["peak_equity"] - 1
        loss_ref, loss_limit = att["peak_equity"], FUNDED_MAX_LOSS

    result = None
    if daily_dd <= -DAILY_LOSS_LIMIT:
        result = "PRZEKROCZONY LIMIT DZIENNY"
    elif total_dd <= -loss_limit:
        result = "PRZEKROCZONY LIMIT CAŁKOWITY"
    elif att["phase"] == "EWALUACJA" and eq / att["start_equity"] - 1 >= TARGET_PROFIT:
        result = "ZDANE"

    hist.append(dict(ts=ts, equity=eq, phase=att["phase"], attempt=att["no"],
                     daily_dd=daily_dd, total_dd=total_dd))

    if result in ("PRZEKROCZONY LIMIT DZIENNY", "PRZEKROCZONY LIMIT CAŁKOWITY"):
        close_attempt(att, ts, price, result, attempts_log, funded_stats)
        state["attempts_failed"] += 1
        if att["phase"] == "SFINANSOWANE":
            state["funded_losses"] += 1
        state["n"] += 1
        state["att"] = new_attempt(state["n"], "EWALUACJA", CAPITAL, ts, price, series, i)
    elif result == "ZDANE":
        close_attempt(att, ts, price, result, attempts_log, funded_stats)
        state["attempts_passed"] += 1
        state["att"] = new_attempt(state["n"], "SFINANSOWANE", eq, ts, price, series, i)
    else:
        att["prev_close_equity"] = eq


# ------------------------------------------------------------------ pliki
def d(ts):
    return datetime.datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")


def load_state():
    return json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else None


def save_state(state):
    tmp = STATE + ".tmp"
    json.dump(state, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, STATE)


def append_csv(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def read_csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []


# ------------------------------------------------------------------ raport
def svg_chart(hist):
    if len(hist) < 2:
        return "<p class='muted'>Wykres pojawi się po kilku dniach działania.</p>"
    hist = sorted({int(h["ts"]): h for h in hist}.values(), key=lambda h: int(h["ts"]))
    W, H = 900, 280
    ts = [int(h["ts"]) for h in hist]
    eq = [float(h["equity"]) for h in hist]
    ph = [h["phase"] for h in hist]
    lo, hi = min(eq) * 0.97, max(eq) * 1.03
    X = lambda t: 12 + (W - 24) * (t - ts[0]) / max(ts[-1] - ts[0], 1)
    Y = lambda v: H - 18 - (H - 40) * (v - lo) / max(hi - lo, 1e-9)
    segs, cur_col, buf = [], None, []

    def col_for(p):
        return "#4cc38a" if p == "SFINANSOWANE" else "#6ea8ff"

    for t, v, p in zip(ts, eq, ph):
        c = col_for(p)
        if cur_col is not None and c != cur_col:
            buf.append((t, v))
            segs.append((cur_col, buf))
            buf = [(t, v)]
        else:
            buf.append((t, v))
        cur_col = c
    if buf:
        segs.append((cur_col, buf))
    poly = "".join("<polyline fill='none' stroke='%s' stroke-width='2.5' points='%s'/>" %
                   (c, " ".join("%.1f,%.1f" % (X(t), Y(v)) for t, v in pts)) for c, pts in segs)
    marks = "".join("<line x1='%.1f' x2='%.1f' y1='14' y2='%d' stroke='#e5534b' stroke-width='1' stroke-dasharray='3'/>" % (X(t), X(t), H - 18)
                    for i, (t, v, p) in enumerate(zip(ts, eq, ph)) if i > 0 and ph[i - 1] != p and col_for(ph[i - 1]) == "#6ea8ff" and p == "EWALUACJA")
    return ("<svg viewBox='0 0 %d %d' width='100%%'>%s%s</svg>"
            "<div class='muted'><span style='color:#6ea8ff'>━</span> faza ewaluacji &nbsp; "
            "<span style='color:#4cc38a'>━</span> konto sfinansowane &nbsp; "
            "<span style='color:#e5534b'>┊</span> nieudana próba / reset</div>" % (W, H, poly, marks))


def write_report(state, price, series, i_last, src, funded_stats):
    hist, attempts = read_csv(HIST), read_csv(ATTEMPTS)
    for h in hist:
        h["ts"] = int(h["ts"])
    att = state["att"]
    eq = equity(att["acc"], price)
    n_total = state["n"] - 1 + (1 if att else 0)
    passed, failed = state["attempts_passed"], state["attempts_failed"]
    finished = passed + failed
    rate = (passed / finished * 100) if finished else 0.0
    if att["phase"] == "EWALUACJA":
        prog_target = (eq / att["start_equity"] - 1) / TARGET_PROFIT * 100
        dist_total = (eq / att["start_equity"] - 1 + EVAL_MAX_LOSS) / EVAL_MAX_LOSS * 100
        phase_lbl = "FAZA EWALUACJI — próba #%d" % att["no"]
        phase_col = "#6ea8ff"
    else:
        prog_target = None
        dist_total = (eq / att["peak_equity"] - 1 + FUNDED_MAX_LOSS) / FUNDED_MAX_LOSS * 100
        phase_lbl = "KONTO SFINANSOWANE — od próby #%d" % att["no"]
        phase_col = "#4cc38a"
    dist_daily = (eq / att["prev_close_equity"] - 1 + DAILY_LOSS_LIMIT) / DAILY_LOSS_LIMIT * 100
    days_in_attempt = (att["acc"].get("_ts", 0))
    est_fees = FEE_USD * n_total
    payout = funded_stats["payout_usd"]
    net = payout - est_fees

    rows_att = "".join(
        "<tr><td>#%s</td><td>%s</td><td>%s</td><td>%s</td><td>%.0f</td><td style='color:%s'>%s</td><td style='color:%s'>%+.1f%%</td></tr>" % (
            a["no"], a["phase"], d(int(a["start"])), d(int(a["end"])), float(a["days"]),
            "#4cc38a" if a["result"] == "ZDANE" else "#e5534b", a["result"],
            "#4cc38a" if float(a["pnl"]) >= 0 else "#e5534b", float(a["pnl"]) * 100)
        for a in reversed(attempts[-30:])) or "<tr><td colspan='7' class='muted'>Jeszcze żadna próba się nie zakończyła.</td></tr>"

    rules_now = "".join("<tr><td>%s</td><td style='color:%s'>%s</td></tr>" % (
        n, "#4cc38a" if v else "#e5534b", "▲ trend rośnie" if v else "▼ nie")
        for (n, _), v in zip(RULES, [s[i_last] for s in series]))

    bar = lambda pct, col: "<div style='background:#222a35;border-radius:6px;height:10px;overflow:hidden'><div style='width:%.0f%%;background:%s;height:100%%'></div></div>" % (max(0, min(100, pct)), col)

    target_block = ""
    if prog_target is not None:
        target_block = """<div class="card"><div class="k">Postęp do celu zysku (+%.0f%%)</div><div class="v">%.0f%%</div>%s</div>""" % (TARGET_PROFIT*100, max(0,prog_target), bar(prog_target, "#4cc38a"))

    html = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo: bot vs zasady prop firmy</title>
<style>body{background:#0e1116;color:#e6e9ef;font:15px/1.5 Segoe UI,Arial,sans-serif;margin:0;padding:16px;max-width:980px;margin:auto}h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:26px 0 8px;color:#9fb0c8}
.big{font-size:40px;font-weight:700;margin:4px 0}.card{background:#161b22;border:1px solid #262d38;border-radius:10px;padding:14px 16px;margin:10px 0}
table{width:100%%;border-collapse:collapse;font-size:13px}th,td{padding:6px 8px;border-bottom:1px solid #232a34;text-align:left}th{color:#8b98ab}.muted{color:#7d8899}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.k{color:#8b98ab;font-size:12px}.v{font-size:20px;font-weight:600}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:13px;font-weight:600}
.warn{background:#3a2a10;border:1px solid #7a5a1a;padding:10px 14px;border-radius:8px;color:#f0c674;margin:10px 0}</style></head><body>
<h1>Demo: strategia trendowa BTC pod zasadami "challenge'u" prop firmy</h1>
<div class="warn">To symulacja na WIRTUALNYCH pieniądzach. Nie ma tu prawdziwej firmy, prawdziwego konta ani prawdziwych zleceń.
Zasady (cel +8%%, limit dzienny 5%%, limit całkowity 10%%, konto 10 000 USD) są reprezentatywne dla typowych firm, nie kopią żadnej konkretnej.</div>
<div class="muted">Stan na koniec dnia %(day)s (UTC). Aktualizacja raz dziennie. Źródło cen: %(src)s.</div>
<div class="card"><span class="badge" style="background:%(pcol)s22;color:%(pcol)s">%(plbl)s</span>
<div class="big">%(eq).2f USD</div>
<div class="muted">start tej próby: %(start).0f USD · dzień %(days).0f próby</div></div>
<div class="grid">%(target)s
<div class="card"><div class="k">Zapas do limitu dziennego (dziś)</div><div class="v">%(dd).0f%%</div>%(bard)s</div>
<div class="card"><div class="k">Zapas do limitu całkowitego</div><div class="v">%(dt).0f%%</div>%(bart)s</div></div>
<h2>Wynik od początku testu</h2>
<div class="grid"><div class="card"><div class="k">Prób ewaluacji (ukończonych)</div><div class="v">%(fin)d</div></div>
<div class="card"><div class="k">Zdanych</div><div class="v">%(passed)d (%(rate).0f%%)</div></div>
<div class="card"><div class="k">Niezdanych</div><div class="v">%(failed)d</div></div>
<div class="card"><div class="k">Dni w fazie "sfinansowane" łącznie</div><div class="v">%(fdays).0f</div></div></div>
<div class="grid"><div class="card"><div class="k">Szacowany koszt prób (%(feeone).0f zł/próba, poglądowo)</div><div class="v">%(fees).0f USD (≈%(feespln).0f zł)</div></div>
<div class="card"><div class="k">Symulowana wypłata z konta "sfinansowanego" (80%% zysku)</div><div class="v">%(payout).2f USD</div></div>
<div class="card"><div class="k">Bilans: wypłata − koszt prób</div><div class="v" style="color:%(ncol)s">%(net)+.2f USD</div></div></div>
<h2>Kapitał w czasie</h2><div class="card">%(svg)s</div>
<h2>Co strategia "myśli" dziś (9 reguł głosuje)</h2><div class="card"><table>%(rules)s</table></div>
<h2>Historia prób</h2><div class="card"><table><tr><th>Nr</th><th>Faza</th><th>Start</th><th>Koniec</th><th>Dni</th><th>Wynik</th><th>Zmiana kapitału</th></tr>%(rows)s</table></div>
<div class="muted" style="margin-top:20px">Symulacja na prawdziwych cenach BTC, koszty (prowizja 0,1%% + poślizg 0,03%%) uwzględnione. Nie jest poradą inwestycyjną i nie promuje konkretnej firmy typu prop trading.</div>
</body></html>""" % dict(day=d(hist[-1]["ts"]) if hist else "-", src=src, pcol=phase_col, plbl=phase_lbl, eq=eq, start=att["start_equity"],
                          days=(hist[-1]["ts"] - att["start_ts"]) / DAY if hist else 0, target=target_block,
                          dd=max(0, dist_daily), bard=bar(dist_daily, "#f0c674" if dist_daily < 40 else "#6ea8ff"),
                          dt=max(0, dist_total), bart=bar(dist_total, "#f0c674" if dist_total < 40 else "#6ea8ff"),
                          fin=finished, passed=passed, rate=rate, failed=failed, fdays=funded_stats["funded_days"],
                          fees=est_fees, feespln=est_fees * USD_PLN, feeone=FEE_PLN, payout=payout, ncol=("#4cc38a" if net >= 0 else "#e5534b"), net=net,
                          svg=svg_chart(hist), rules=rules_now, rows=rows_att)
    os.makedirs(DOCS, exist_ok=True)
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(DOCS, ".nojekyll"), "w").write("")


# ------------------------------------------------------------------ główny przebieg
def run():
    os.makedirs(DATA, exist_ok=True)
    src, candles = fetch_daily()
    now = int(time.time() * 1000)
    closed = [c for c in candles if c[0] + DAY <= now]
    forming = [c for c in candles if c[0] + DAY > now]
    ts_l = [c[0] for c in closed]
    closes = [c[1] for c in closed]
    series = compute_series(closes)

    raw = load_state()
    trades_log, hist, attempts_log = [], [], []
    funded_stats = {"payout_usd": 0.0, "funded_days": 0.0}
    if raw is None:
        i0 = len(closes) - 1
        state = dict(n=1, attempts_passed=0, attempts_failed=0, funded_losses=0,
                     att=new_attempt(1, "EWALUACJA", CAPITAL, ts_l[i0], closes[i0], series, i0))
        state["att"]["_last_ts"] = ts_l[i0]
        eq0 = equity(state["att"]["acc"], closes[i0])
        hist.append(dict(ts=ts_l[i0], equity=eq0, phase="EWALUACJA", attempt=1, daily_dd=0.0, total_dd=0.0))
        print("START demo: próba #1, kapitał %.0f USD, cel +%.0f%%" % (CAPITAL, TARGET_PROFIT * 100))
    else:
        state = raw
        state["funded_losses"] = state.get("funded_losses", 0)
        att = state["att"]
        acc = att["acc"]
        last_processed = att.get("_last_ts", att["start_ts"])
        for i, (ts, c) in enumerate(zip(ts_l, closes)):
            if ts > last_processed:
                process_day(state, ts, c, series, i, trades_log, hist, attempts_log, funded_stats)
                state["att"]["_last_ts"] = ts
                last_processed = ts
        if hist:
            print("Przetworzono %d dni. Faza: %s (próba #%d), kapitał %.2f USD" %
                  (len(hist), state["att"]["phase"], state["att"]["no"], equity(state["att"]["acc"], closes[-1])))
        else:
            print("Brak nowych zamkniętych dni.")

    append_csv(HIST, ["ts", "equity", "phase", "attempt", "daily_dd", "total_dd"],
               [[h["ts"], "%.4f" % h["equity"], h["phase"], h["attempt"], "%.4f" % h["daily_dd"], "%.4f" % h["total_dd"]] for h in hist])
    append_csv(ATTEMPTS, ["no", "phase", "start", "end", "days", "result", "start_eq", "end_eq", "pnl"],
               [[a["no"], a["phase"], a["start"], a["end"], "%.1f" % a["days"], a["result"],
                 "%.2f" % a["start_eq"], "%.2f" % a["end_eq"], "%.4f" % a["pnl"]] for a in attempts_log])
    save_state(state)

    # dopisz zysk z zakończonych faz sfinansowanych z tej sesji do skumulowanej wypłaty w state (persystencja)
    fund_key = "cum_payout_usd"
    state[fund_key] = state.get(fund_key, 0.0) + funded_stats["payout_usd"]
    fund_days_key = "cum_funded_days"
    state[fund_days_key] = state.get(fund_days_key, 0.0) + funded_stats["funded_days"]
    save_state(state)
    funded_stats["payout_usd"] = state[fund_key]
    funded_stats["funded_days"] = state[fund_days_key]

    price_now = forming[-1][1] if forming else closes[-1]
    write_report(state, price_now, series, len(closes) - 1, src, funded_stats)


if __name__ == "__main__":
    run()
