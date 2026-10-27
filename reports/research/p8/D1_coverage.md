# P8 data foundation D1: S&P 500 price coverage (member-days with a close)

Alpaca SIP bars (adjusted for splits and dividends) 2016-01-04 .. 2025-12-31; yfinance cache for 2012-2015.
Expected = every (session, member) pair: `data/raw/stocks/sp500_membership.csv` (one row per change date) carried forward to each session.

| year | member-days | Alpaca | yfinance cache | either |
|---|---|---|---|---|
| 2012 | 124,242 | 0.0% | 68.6% | 68.6% |
| 2013 | 125,241 | 0.0% | 70.7% | 70.7% |
| 2014 | 125,534 | 0.0% | 71.7% | 71.7% |
| 2015 | 126,147 | 0.0% | 73.5% | 73.5% |
| 2016 | 127,356 | 98.0% | 76.6% | 98.4% |
| 2017 | 126,995 | 98.9% | 79.5% | 99.1% |
| 2018 | 126,917 | 99.4% | 81.3% | 99.4% |
| 2019 | 127,260 | 99.4% | 84.1% | 99.6% |
| 2020 | 127,767 | 99.8% | 87.2% | 100.0% |
| 2021 | 127,260 | 99.8% | 89.1% | 100.0% |
| 2022 | 126,437 | 99.8% | 91.7% | 100.0% |
| 2023 | 125,750 | 99.7% | 94.2% | 99.9% |
| 2024 | 126,757 | 99.6% | 95.7% | 99.8% |
| 2025 | 125,752 | 99.6% | 97.1% | 99.8% |

Symbols with the most missing member-days (either source):

STI (1996), BHGE (1961), DOW (1426), ANDV (1403), AABA (1373), ARNC (1216), TE (1131), CCE (1108), SNDK (1096), NBL (1011), JNPR (1010), RHT (1010), ETFC (1009), HES (1009), PXD (1009), TSS (1009), VAR (1009), MRO (1008), AGN (1007), CTXS (1007), NFX (1007), RTN (1007), XLNX (1007), ABC (1006), AET (1006), ANTM (1006), APC (1006), ARG (1006), AVB (1006), BBBY (1006), BCR (1006), BK (1006), BLL (1006), BRCM (1006), CA (1006), CAM (1006), CBS (1006), CELG (1006), CERN (1006), CHK (1006)
