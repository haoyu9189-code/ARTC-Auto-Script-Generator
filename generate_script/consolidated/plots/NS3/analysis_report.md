# Data Analysis Report: NS3 baseline

SEA = specific energy absorption, ∫σ dε up to ε ≤ 0.25 (units: MPa = mJ/mm³).
ΔSEA = (SEA[N_max] / SEA[N=1] − 1) × 100 %.

## Summary

| Item | Count |
|------|-------|
| Topologies in group | 24 |
| With valid SEA data  | 24 |
| Positive ΔSEA (SEA ↑ with N) | 10 |
| Negative ΔSEA (SEA ↓ with N) | 14 |
| Excluded from ΔSEA analysis  | 5 (CBCC, Cubic, FCCZ, G7, Truncated_cube) |

## SEA Values (MPa)

| Topology | N=1 | N=2 | N=3 | N=4 | N=5 | ΔSEA (%) | Trend |
|---|---|---|---|---|---|---|---|
| AFCC | 0.5630 | 0.7194 | 0.7542 | 0.8135 | 0.8014 | +42.4 | ↑ |
| Auxetic | 1.1910 | 0.8114 | 0.6405 | 0.4685 | 0.4205 | -64.7 | ↓ |
| BCC | 0.6061 | 0.3472 | — | 0.3104 | — | -48.8 | ↓ |
| BCCZ | 0.8454 | 0.7622 | 0.7558 | 0.7634 | 0.7687 | -9.1 | ↓ |
| CBCC\* | 0.9071 | 0.8324 | 0.8180 | 0.8307 | — | -8.4 | ↓ |
| Cubic\* | 0.1979 | 0.1171 | 0.1161 | 0.1127 | 0.1182 | -40.3 | ↓ |
| CubicRosette | 0.2935 | 0.5515 | 0.6491 | 0.6903 | 0.7363 | +150.9 | ↑ |
| Cuboctahedron_Z | 2.4192 | 2.3707 | 2.3564 | 2.3500 | — | -2.9 | ↓ |
| Diamond | 0.2277 | 0.5061 | 0.6292 | 0.6982 | 0.7101 | +211.8 | ↑ |
| DiamondPlus | 0.5469 | 0.8662 | 0.9845 | 1.0619 | 1.1010 | +101.3 | ↑ |
| FBCCXYZ | 1.8131 | 1.9506 | 1.9980 | 2.0951 | — | +15.6 | ↑ |
| FBCCZ | 1.0410 | 0.7176 | 0.7306 | 0.7137 | 0.7112 | -31.7 | ↓ |
| FCC | 0.5586 | 0.4965 | 0.4616 | 0.4474 | 0.4545 | -18.6 | ↓ |
| FCCZ\* | 0.8346 | 0.8808 | 0.7879 | 0.7926 | — | -5.0 | ↓ |
| G7\* | 0.6751 | 0.4927 | 0.4706 | 0.4832 | 0.4785 | -29.1 | ↓ |
| Iso_truss | 1.5632 | 1.4780 | 1.5398 | 1.5141 | 1.5240 | -2.5 | ↓ |
| Kelvin | 0.4910 | 0.6249 | 0.6731 | 0.6805 | 0.6945 | +41.4 | ↑ |
| Octahedron | 0.8743 | 0.8486 | 0.8590 | 0.8629 | — | -1.3 | ↓ |
| Octet_truss | 1.9101 | 1.8751 | 1.8552 | 1.8433 | 1.8428 | -3.5 | ↓ |
| Rhombic | 1.4565 | 1.3886 | 1.4506 | 1.4287 | — | -1.9 | ↓ |
| Tetrahedron_base | 1.0915 | 1.3489 | 1.4862 | 1.5181 | — | +39.1 | ↑ |
| Truncated_cube\* | 0.3542 | 0.3135 | 0.3931 | — | — | +11.0 | ↑ |
| Truncated_Octoctahedron | 0.9471 | 1.0945 | 1.2289 | 1.2541 | — | +32.4 | ↑ |
| WeairePhelan | 2.9573 | 3.1861 | 3.2167 | 3.2246 | — | +9.0 | ↑ |

`\*` Excluded (data quality): CBCC, Cubic, FCCZ, G7, Truncated_cube

## Ranking by ΔSEA (active topologies only)

- **Diamond**: +211.8% ↑  (N=1 → N=5)
- **CubicRosette**: +150.9% ↑  (N=1 → N=5)
- **DiamondPlus**: +101.3% ↑  (N=1 → N=5)
- **AFCC**: +42.4% ↑  (N=1 → N=5)
- **Kelvin**: +41.4% ↑  (N=1 → N=5)
- **Tetrahedron_base**: +39.1% ↑  (N=1 → N=4)
- **Truncated_Octoctahedron**: +32.4% ↑  (N=1 → N=4)
- **FBCCXYZ**: +15.6% ↑  (N=1 → N=4)
- **WeairePhelan**: +9.0% ↑  (N=1 → N=4)
- **Octahedron**: -1.3% ↓  (N=1 → N=4)
- **Rhombic**: -1.9% ↓  (N=1 → N=4)
- **Iso_truss**: -2.5% ↓  (N=1 → N=5)
- **Cuboctahedron_Z**: -2.9% ↓  (N=1 → N=4)
- **Octet_truss**: -3.5% ↓  (N=1 → N=5)
- **BCCZ**: -9.1% ↓  (N=1 → N=5)
- **FCC**: -18.6% ↓  (N=1 → N=5)
- **FBCCZ**: -31.7% ↓  (N=1 → N=5)
- **BCC**: -48.8% ↓  (N=1 → N=4)
- **Auxetic**: -64.7% ↓  (N=1 → N=5)

## Notable Findings

- **Largest positive**: Diamond (+211.8%)
- **Largest negative**: Auxetic (-64.7%)
- 10/24 active topologies show positive size effect.

