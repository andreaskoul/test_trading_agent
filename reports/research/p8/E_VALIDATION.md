# Family E validation read (2022-2025, once)

Lock: 2026-10-31T15:02:47.108005+00:00 commit 8409c3bc4430dc94654743547ed4f08f91826191

Rule B (PREREG_family_E.md §5): Holm p <= 0.05 over E1 and E2; the registered sign in 2022-23 and in 2024-25; net per event at the live cost above the 4 bp margin and >= 0 at the 20 bp stress. A passing module then goes to the sealed 2026 check.

| module | n | effect | p (max of tests) | Holm p | halves | net live bp | net stress bp | passes |
|---|---:|---|---:|---:|---|---:|---:|---|
| E1 earnings_post (t0+1, h 10) | 7164 | slope +4.9 bp/sd, IC +0.0254 | 0.2373 | 0.3556 | ok [8.8, 1.1] | +13.0 | -19.0 | **no** |
| E2 news_8k (h 10) | 221 | mean +54.8 bp | 0.1778 | 0.3556 | ok [65.5, 44.8] | +50.8 | +34.8 | **no** |

Diagnostic: Bonferroni over every hypothesis read on 2022-2025 (34 before + 2): E1 1.0000, E2 1.0000.
E1 tests: wild (industry) 0.2373, randomisation 0.2370, CR1 (month) 0.2351. E2 tests: cr1_week 0.1074, wild_week 0.1075, cr1_ind 0.1504, wild_ind 0.1778, cr1_two_way 0.1540.
