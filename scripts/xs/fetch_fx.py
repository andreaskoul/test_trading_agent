"""Fetch FX spot (Fed H.10 via FRED; Yahoo for PLN HUF CZK ILS CLP) and OECD 3-month rates (FRED) for PROTOCOL_fx.md.

    python scripts/xs/fetch_fx.py   # -> data/raw/fx/{spot_usd_per_ccy,rates_monthly,spike_log}.parquet/csv

Spot is stored as USD per unit of currency. Yahoo series pass the
Amendment 1 filter; removed prints are logged.
"""

import io
import os
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw", "fx")
os.makedirs(OUT, exist_ok=True)

CCY = {  # ccy: (yahoo ticker, quoted as USD per ccy?, OECD country code)
    "EUR": ("EURUSD=X", True, "EZ"), "JPY": ("JPY=X", False, "JP"), "GBP": ("GBPUSD=X", True, "GB"),
    "CHF": ("CHF=X", False, "CH"), "AUD": ("AUDUSD=X", True, "AU"), "NZD": ("NZDUSD=X", True, "NZ"),
    "CAD": ("CAD=X", False, "CA"), "SEK": ("SEK=X", False, "SE"), "NOK": ("NOK=X", False, "NO"),
    "MXN": ("MXN=X", False, "MX"), "ZAR": ("ZAR=X", False, "ZA"), "PLN": ("PLN=X", False, "PL"),
    "HUF": ("HUF=X", False, "HU"), "CZK": ("CZK=X", False, "CZ"), "KRW": ("KRW=X", False, "KR"),
    "ILS": ("ILS=X", False, "IL"), "CLP": ("CLP=X", False, "CL"), "IDR": ("IDR=X", False, "ID"),
}

# Amendment 1: Fed H.10 (FRED) where available, Yahoo only for the rest.
H10 = {"EUR": ("DEXUSEU", True), "JPY": ("DEXJPUS", False), "GBP": ("DEXUSUK", True),
       "CHF": ("DEXSZUS", False), "AUD": ("DEXUSAL", True), "NZD": ("DEXUSNZ", True),
       "CAD": ("DEXCAUS", False), "SEK": ("DEXSDUS", False), "NOK": ("DEXNOUS", False),
       "MXN": ("DEXMXUS", False), "ZAR": ("DEXSFUS", False), "KRW": ("DEXKOUS", False)}
YAHOO = [c for c in CCY if c not in H10 and c != "IDR"]


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna()


spot = {}
for c, (fid, usd_per) in H10.items():
    s = fred(fid)
    s = s[(s.index >= "2003-06-01") & (s.index < "2026-09-26")]
    spot[c] = s if usd_per else 1.0 / s
raw = yf.download([CCY[c][0] for c in YAHOO], start="2003-06-01", end="2026-09-26", interval="1d",
                  progress=False, auto_adjust=False, threads=False)["Close"]
raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
log_rows = []
for c in YAHOO:
    s = (1.0 / raw[CCY[c][0]]).where(raw[CCY[c][0]] > 0).dropna()
    # remove prints that jump > 5% and are at least half reversed within 3 prints
    while True:
        lr = np.log(s).diff().to_numpy()
        bad = []
        for i in np.where(np.abs(lr) > np.log(1.05))[0]:
            back = np.log(s.iloc[i + 1:i + 4] / s.iloc[i]).to_numpy()
            if len(back) and np.any(-np.sign(lr[i]) * back >= 0.5 * abs(lr[i])):
                bad.append(s.index[i])
        if not bad:
            break
        for d in bad:
            log_rows.append(dict(ccy=c, date=d, value=s[d]))
        s = s.drop(bad)
    spot[c] = s
spot = pd.DataFrame(spot)
pd.DataFrame(log_rows).to_csv(os.path.join(OUT, "spike_log.csv"), index=False)
spot.to_parquet(os.path.join(OUT, "spot_usd_per_ccy.parquet"))

rates = {}
for c, (_, _, cc) in [(k, v) for k, v in CCY.items() if k != "IDR"] + [("USD", (None, None, "US"))]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=IR3TIB01{cc}M156N"
    with urllib.request.urlopen(url, timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    rates[c] = s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100.0
rates = pd.DataFrame(rates)
rates.to_parquet(os.path.join(OUT, "rates_monthly.parquet"))

print("spot", spot.shape, spot.index.min().date(), spot.index.max().date())
print("spikes removed:", len(log_rows), pd.DataFrame(log_rows).groupby("ccy").size().to_dict() if log_rows else {})
print("rates last obs:", rates.apply(lambda s: str(s.last_valid_index().date())).to_dict())
