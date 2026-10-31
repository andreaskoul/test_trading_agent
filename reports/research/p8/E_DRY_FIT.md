# Family E dry fit (2016-2021; selection only, no lock)

Rule (PREREG_family_E.md §4): E1 picks the cell with the highest season-level IC t; E2 the h with the highest t of mean y; ties to the shorter h. Validation and sealed data are not loaded.

## E1 earnings_post (SUE)

| entry | h | n | seasons | IC | IC t | tercile spread bp | net live | net stress |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t0 | 5 | 7957 | 20 | +0.0480 | +2.34 | +40.5 | +32.5 | +0.5 |
| t0 | 10 | 7947 | 20 | +0.0617 | +2.68 | +51.9 | +43.9 | +11.9 |
| t0 | 20 | 7935 | 20 | +0.0563 | +2.28 | +58.2 | +50.2 | +18.2 |
| t0 | 40 | 7803 | 20 | +0.0319 | +1.33 | +30.7 | +22.7 | -9.3 |
| t0+1 | 5 | 7957 | 20 | +0.0301 | +1.89 | +22.1 | +14.1 | -17.9 |
| t0+1 | 10 | 7944 | 20 | +0.0505 | +2.78 | +43.4 | +35.4 | +3.4 |
| t0+1 | 20 | 7931 | 20 | +0.0463 | +2.24 | +47.1 | +39.1 | +7.1 |
| t0+1 | 40 | 7768 | 20 | +0.0192 | +0.89 | +10.9 | +2.9 | -29.1 |

**Chosen: entry t0+1, h 10.**

## E2 news_8k (hard items, direction of day 0)

| h | n | weeks | mean bp | t | net live | net stress |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 426 | 206 | +15.1 | +0.87 | +11.1 | -4.9 |
| 10 | 424 | 205 | +32.4 | +1.23 | +28.4 | +12.4 |
| 20 | 414 | 201 | +56.4 | +1.20 | +52.4 | +36.4 |

**Chosen: h 10.**

## E3 soft 8-K (items 5.02, 1.01), the fund's entry, 5 sessions (descriptive)

n 7076, weeks 255, mean -1.2 bp, t -0.19; item 5.02: n 4626, mean -2.7 bp, t -0.35; item 1.01: n 2509, mean +2.3 bp, t +0.23

The E3 decision is the locked holdout read (rule A); this fit line only checks the pipeline.
