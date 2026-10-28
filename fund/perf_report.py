"""Performance report (QuantStats) for the Alpaca paper account, published on the dashboard.

    python fund/perf_report.py NAV_CSV OUT_HTML

Daily returns come from the broker's equity curve (execution/nav.csv), from the close of the
first trade on, so they include everything the account earned or paid: trading P&L, dividends,
fees, borrow and interest. Benchmark: SPY total return. Risk-free: the 3-month T-bill (FRED
DTB3) averaged over the period. Alpaca labels each daily equity point with the next calendar
day (the 2026-10-23 close is stamped 2026-10-24), so each label is moved back to the previous
business day before aligning with SPY.

With fewer than MIN_RETURNS daily returns the page says so instead of showing statistics.
"""

import io
import re
import sys
import urllib.request

import pandas as pd

nav_p, out_p = sys.argv[1], sys.argv[2]
MIN_RETURNS = 5          # below this nothing meaningful can be shown; under 20 the page is flagged as early
FIRST_TRADE = "2026-10-01"

N = pd.read_csv(nav_p, parse_dates=["date"])
N["session"] = N["date"] - pd.offsets.BDay(1)                # label is the next calendar day
eq = N.set_index("session")["equity"].sort_index()
eq = eq[eq.index >= FIRST_TRADE]                             # value at the first trade's close onward
ret = eq.pct_change().dropna()
ret.index = pd.DatetimeIndex(ret.index).tz_localize(None)


def page(body):
    open(out_p, "w").write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Performance Report</title>
<style>body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1d1d1f}}a{{color:#2c5aa0}}</style>
</head><body><p><a href="./">&larr; Trade monitor</a></p><h1>Performance report</h1>{body}</body></html>""")


if len(ret) < MIN_RETURNS:
    page(f"<p>The report starts once the account has {MIN_RETURNS} daily returns; it has {len(ret)}.</p>")
    print(f"perf report: {len(ret)} returns, placeholder written")
    sys.exit(0)

import quantstats as qs
import yfinance as yf

spy = yf.download("SPY", start=ret.index[0] - pd.Timedelta(days=10), end=ret.index[-1] + pd.Timedelta(days=3),
                  progress=False, auto_adjust=True)["Close"].squeeze()
spy.index = pd.DatetimeIndex(spy.index).tz_localize(None)
bench = spy.pct_change().reindex(ret.index).fillna(0.0).rename("SPY")
with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3", timeout=60) as r:
    tb = pd.read_csv(io.BytesIO(r.read()), na_values=".")
tb.columns = ["date", "v"]
tb["date"] = pd.to_datetime(tb["date"])
rf = float(tb[(tb.date >= ret.index[0]) & (tb.date <= ret.index[-1])]["v"].mean() / 100)

title = (f"Alpaca paper account, {ret.index[0]:%d %b %Y} to {ret.index[-1]:%d %b %Y} "
         f"({len(ret)} daily returns{', early: statistics are not yet meaningful' if len(ret) < 20 else ''})")
try:
    qs.reports.html(ret.rename("Fund"), benchmark=bench, rf=rf, output=out_p, title=title,
                    download_filename="fund_performance.html")
except Exception as exc:                                     # too few points for some panels
    qs.reports.html(ret.rename("Fund"), benchmark=bench, rf=rf, output=out_p, title=title,
                    download_filename="fund_performance.html", periods_per_year=252, match_dates=True)
    print(f"perf report: retried after {exc!r}")
html = re.sub(r"(<body[^>]*>)", r'\1<p style="margin:12px 16px;font-family:Arial,sans-serif"><a href="./">&larr; Trade monitor</a></p>', open(out_p).read(), count=1)
open(out_p, "w").write(html)
print(f"perf report: {len(ret)} returns, {ret.index[0].date()} to {ret.index[-1].date()}, rf {rf:.2%} -> {out_p}")
