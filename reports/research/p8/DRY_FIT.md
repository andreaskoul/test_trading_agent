# P8 family H: dry run on the FIT sample (code check, B = 199)

Lock: 2026-10-27T08:02:07.801809+00:00 commit e4446804e7a52a2c02fe3c97d6aba890ca58dbf9 DRY-FIT

## sp500

| test | statistic | t | p | Holm p | halves | net spread | pass |
|---|---|---|---|---|---|---|---|
| H1 | beta -0.0010 | -0.03 | 0.5050 | 1.000 | no | -38.3 bp | no |
| H2 | not run: rows not built (gates or data) | | 1 | 1.000 | | | no |
| H2b | not run: TNIC not joinable (Amendment 5 A1) | | 1 | 1.000 | | | no |
| H3a | slope -5.7 bp/sd | -1.04 | 0.8427 | 1.000 | no | -19.2 bp | no |
| H3b | beta -0.7831 | -2.47 | 0.9900 | 1.000 | no | -6.1 bp | no |
| H4 | beta +0.1421 | +0.91 | 0.4350 | 1.000 | no | -14.8 bp | no |
| H5 | slope +1.0 bp/sd | +0.15 | 0.4420 | 1.000 | no | +13.8 bp | no |

## sp400

| test | statistic | t | p | Holm p | halves | net spread | pass |
|---|---|---|---|---|---|---|---|
| H1 | beta -0.0490 | -0.57 | 0.3200 | 1.000 | no | -16.5 bp | no |
| H2 | not run: rows not built (gates or data) | | 1 | 1.000 | | | no |
| H2b | not run: TNIC not joinable (Amendment 5 A1) | | 1 | 1.000 | | | no |
| H3a | slope +6.7 bp/sd | +0.58 | 0.2885 | 1.000 | ok | -10.0 bp | no |
| H3b | beta -0.0181 | -0.25 | 0.6500 | 1.000 | no | -8.9 bp | no |
| H4 | beta +0.1421 | +0.91 | 0.4350 | 1.000 | no | -14.8 bp | no |
| H5 | slope -48.4 bp/sd | -1.84 | 0.9555 | 1.000 | no | -111.5 bp | no |
