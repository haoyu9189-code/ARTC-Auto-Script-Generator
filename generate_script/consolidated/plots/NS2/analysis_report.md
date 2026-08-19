# Data Analysis Report: NS2 original_6

SEA = specific energy absorption, ∫σ dε up to ε ≤ 0.25 (units: MPa = mJ/mm³).
ΔSEA = (SEA[N_max] / SEA[N=1] − 1) × 100 %.

## Summary

| Item | Count |
|------|-------|
| Topologies in group | 6 |
| With valid SEA data  | 6 |
| Positive ΔSEA (SEA ↑ with N) | 1 |
| Negative ΔSEA (SEA ↓ with N) | 5 |
| Excluded from ΔSEA analysis  | 1 (FCCZ) |

## SEA Values (MPa)

| Topology | N=1 | N=2 | N=3 | N=4 | N=5 | ΔSEA (%) | Trend |
|---|---|---|---|---|---|---|---|
| Auxetic | 1.1910 | 0.8114 | 0.6405 | 0.4685 | 0.4205 | -64.7 | ↓ |
| BCC | 0.6061 | 0.3265 | 0.2960 | 0.2854 | 0.2835 | -53.2 | ↓ |
| FCC | 0.5586 | 0.4965 | 0.4616 | 0.4474 | 0.4545 | -18.6 | ↓ |
| FCCZ\* | 0.8346 | 0.8808 | 0.8074 | 0.8122 | 0.8166 | -2.1 | ↓ |
| Kelvin | 0.4910 | 0.6249 | 0.6731 | 0.6805 | 0.6945 | +41.4 | ↑ |
| Octet_truss | 1.9101 | 1.8751 | 1.8552 | 1.8433 | 1.8428 | -3.5 | ↓ |

`\*` Excluded (data quality): FCCZ

## Ranking by ΔSEA (active topologies only)

- **Kelvin**: +41.4% ↑  (N=1 → N=5)
- **Octet_truss**: -3.5% ↓  (N=1 → N=5)
- **FCC**: -18.6% ↓  (N=1 → N=5)
- **BCC**: -53.2% ↓  (N=1 → N=5)
- **Auxetic**: -64.7% ↓  (N=1 → N=5)

## Notable Findings

- **Largest positive**: Kelvin (+41.4%)
- **Largest negative**: Auxetic (-64.7%)
- 1/6 active topologies show positive size effect.

