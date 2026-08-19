# Data Analysis Report: NS4

SEA = specific energy absorption, ∫σ dε up to ε ≤ 0.25 (units: MPa = mJ/mm³).
ΔSEA = (SEA[N_max] / SEA[N=1] − 1) × 100 %.

## Summary

| Item | Count |
|------|-------|
| Topologies in group | 24 |
| With valid SEA data  | 24 |
| Positive ΔSEA (SEA ↑ with N) | 10 |
| Negative ΔSEA (SEA ↓ with N) | 13 |
| Excluded from ΔSEA analysis  | 5 (CBCC, Cubic, FCCZ, G7, Truncated_cube) |

## SEA Values (MPa)

| Topology | N=1 | N=2 | N=3 | N=4 | N=5 | ΔSEA (%) | Trend |
|---|---|---|---|---|---|---|---|
| AFCC | 0.6717 | 0.7856 | 0.8139 | 0.8159 | 0.8251 | +22.8 | ↑ |
| Auxetic | 1.3067 | 1.3666 | 1.2694 | 1.1471 | 1.1137 | -14.8 | ↓ |
| BCC | 0.6282 | 0.3463 | 0.3229 | 0.3013 | 0.3024 | -51.9 | ↓ |
| BCCZ | 0.9365 | 0.7617 | 0.7561 | 0.7631 | 0.7600 | -18.9 | ↓ |
| CBCC\* | 0.9939 | 0.9067 | 0.9168 | 0.9245 | 0.9278 | -6.7 | ↓ |
| Cubic\* | 0.2560 | 0.1285 | 0.1239 | 0.1196 | 0.1255 | -51.0 | ↓ |
| CubicRosette | 0.3311 | 0.6517 | 0.7450 | 0.7919 | 0.8054 | +143.3 | ↑ |
| Cuboctahedron_Z | 2.4609 | 2.4004 | 2.3805 | 2.3173 | 2.3697 | -3.7 | ↓ |
| Diamond | 0.2892 | 0.5375 | 0.6441 | 0.6983 | 0.7268 | +151.4 | ↑ |
| DiamondPlus | 1.2450 | 1.4407 | 1.5350 | 1.5815 | — | +27.0 | ↑ |
| FBCCXYZ | 1.9758 | 2.0657 | 2.0933 | 2.0971 | 2.1001 | +6.3 | ↑ |
| FBCCZ | 1.1374 | 0.7668 | — | — | — | -32.6 | ↓ |
| FCC | 0.6679 | 0.5257 | 0.4911 | 0.4729 | 0.4737 | -29.1 | ↓ |
| FCCZ\* | 0.9896 | 0.9182 | 0.8607 | 0.8521 | 0.8514 | -14.0 | ↓ |
| G7\* | 0.6975 | 0.5159 | 0.4942 | 0.4834 | 0.4783 | -31.4 | ↓ |
| Iso_truss | 1.5636 | 1.5128 | 1.5380 | 1.5450 | 1.5549 | -0.6 | ↓ |
| Kelvin | 0.5526 | 0.6724 | 0.7135 | 0.7314 | 0.7449 | +34.8 | ↑ |
| Octahedron | 0.8838 | 0.8810 | 0.8732 | 0.8759 | 0.8720 | -1.3 | ↓ |
| Octet_truss | 1.9518 | 1.9128 | 1.8842 | 1.8764 | 1.8723 | -4.1 | ↓ |
| Rhombic | — | 1.4926 | 1.4601 | 1.4342 | 1.3934 | — | ? |
| Tetrahedron_base | 1.1866 | 1.4201 | 1.4879 | 1.5185 | 1.5330 | +29.2 | ↑ |
| Truncated_cube\* | 0.3753 | 0.4171 | 0.4333 | 0.4127 | 0.4566 | +21.7 | ↑ |
| Truncated_Octoctahedron | 1.0436 | 1.2229 | 1.2873 | 1.3166 | 1.3326 | +27.7 | ↑ |
| WeairePhelan | 3.3317 | 3.4206 | 3.4527 | 3.4578 | 3.3770 | +1.4 | ↑ |

`\*` Excluded (data quality): CBCC, Cubic, FCCZ, G7, Truncated_cube

## Ranking by ΔSEA (active topologies only)

- **Diamond**: +151.4% ↑  (N=1 → N=5)
- **CubicRosette**: +143.3% ↑  (N=1 → N=5)
- **Kelvin**: +34.8% ↑  (N=1 → N=5)
- **Tetrahedron_base**: +29.2% ↑  (N=1 → N=5)
- **Truncated_Octoctahedron**: +27.7% ↑  (N=1 → N=5)
- **DiamondPlus**: +27.0% ↑  (N=1 → N=4)
- **AFCC**: +22.8% ↑  (N=1 → N=5)
- **FBCCXYZ**: +6.3% ↑  (N=1 → N=5)
- **WeairePhelan**: +1.4% ↑  (N=1 → N=5)
- **Iso_truss**: -0.6% ↓  (N=1 → N=5)
- **Octahedron**: -1.3% ↓  (N=1 → N=5)
- **Cuboctahedron_Z**: -3.7% ↓  (N=1 → N=5)
- **Octet_truss**: -4.1% ↓  (N=1 → N=5)
- **Auxetic**: -14.8% ↓  (N=1 → N=5)
- **BCCZ**: -18.9% ↓  (N=1 → N=5)
- **FCC**: -29.1% ↓  (N=1 → N=5)
- **FBCCZ**: -32.6% ↓  (N=1 → N=2)
- **BCC**: -51.9% ↓  (N=1 → N=5)

## Notable Findings

- **Largest positive**: Diamond (+151.4%)
- **Largest negative**: BCC (-51.9%)
- 10/23 active topologies show positive size effect.

