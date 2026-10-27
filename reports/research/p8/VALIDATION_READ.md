# P8 family H: the validation read (2022-2025), made once

Lock: 2026-10-27T08:03:49.512140+00:00 commit b2e2cfd7a91259b84b4edfc136e8a6e69708d587

## sp500

| test | statistic | t | p | Holm p | halves | net spread | pass |
|---|---|---|---|---|---|---|---|
| H1 | beta -0.0390 | -0.85 | 0.2096 | 1.000 | no | -48.1 bp | no |
| H2 | not run: rows not built (gates or data) | | 1 | 1.000 | | | no |
| H2b | not run: TNIC not joinable (Amendment 5 A1) | | 1 | 1.000 | | | no |
| H3a | slope +7.9 bp/sd | +0.69 | 0.2582 | 1.000 | no | +15.2 bp | no |
| H3b | beta -0.4213 | -2.04 | 0.9474 | 1.000 | no | -68.1 bp | no |
| H4 | beta -0.2529 | -2.76 | 0.9954 | 1.000 | no | -43.0 bp | no |
| H5 | slope +34.0 bp/sd | +2.83 | 0.0075 | 0.053 | ok | +118.1 bp | no |

## sp400

| test | statistic | t | p | Holm p | halves | net spread | pass |
|---|---|---|---|---|---|---|---|
| H1 | beta -0.1696 | -2.70 | 0.0045 | 0.032 | ok | +79.2 bp | PASS |
| H2 | not run: rows not built (gates or data) | | 1 | 1.000 | | | no |
| H2b | not run: TNIC not joinable (Amendment 5 A1) | | 1 | 1.000 | | | no |
| H3a | slope +8.9 bp/sd | +0.79 | 0.2295 | 1.000 | no | +5.5 bp | no |
| H3b | beta +1.1697 | +0.95 | 0.1840 | 1.000 | no | -55.0 bp | no |
| H4 | beta -0.2529 | -2.76 | 0.9954 | 1.000 | no | -43.0 bp | no |
| H5 | slope -1.7 bp/sd | -0.11 | 0.5410 | 1.000 | no | -22.8 bp | no |
