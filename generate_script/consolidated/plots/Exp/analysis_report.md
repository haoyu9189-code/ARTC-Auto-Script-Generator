# Data Analysis Report: Experiment 20260422

SEA = specific energy absorption, ∫σ dε up to ε ≤ 0.25 (units: MPa = mJ/mm³).
ΔSEA = (SEA[N_max] / SEA[N=1] − 1) × 100 %.

## Summary

| Item | Count |
|------|-------|
| Topologies in group | 5 |
| With valid SEA data  | 5 |
| Positive ΔSEA (SEA ↑ with N) | 3 |
| Negative ΔSEA (SEA ↓ with N) | 2 |
| Excluded from ΔSEA analysis  | 0 (none) |

## SEA Values (MPa)

| Topology | N=1 | N=2 | N=3 | N=4 | N=5 | ΔSEA (%) | Trend |
|---|---|---|---|---|---|---|---|
| Auxetic | 0.9427 | 0.3587 | 0.2440 | 0.1785 | 0.2021 | -78.6 | ↓ |
| BCC | 0.0463 | 0.0914 | 0.1249 | — | 0.1325 | +186.2 | ↑ |
| Iso_truss | 0.8784 | 0.8767 | 0.8209 | 0.8961 | 0.7308 | -16.8 | ↓ |
| Kelvin | 0.3000 | 0.4124 | 0.3777 | 0.4451 | 0.4190 | +39.7 | ↑ |
| Octet_truss | 0.9335 | 0.7748 | 0.9765 | 1.0130 | 1.0105 | +8.3 | ↑ |

`\*` Excluded (data quality): none

## Ranking by ΔSEA (active topologies only)

- **BCC**: +186.2% ↑  (N=1 → N=5)
- **Kelvin**: +39.7% ↑  (N=1 → N=5)
- **Octet_truss**: +8.3% ↑  (N=1 → N=5)
- **Iso_truss**: -16.8% ↓  (N=1 → N=5)
- **Auxetic**: -78.6% ↓  (N=1 → N=5)

## Notable Findings

- **Largest positive**: BCC (+186.2%)
- **Largest negative**: Auxetic (-78.6%)
- 3/5 active topologies show positive size effect.

