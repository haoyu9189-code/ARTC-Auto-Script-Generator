# Bulk viscosity sensitivity test — 2026-05-02

Tested whether dropping `linearBulkViscosity / quadBulkViscosity` from NS3 (0.25, 2.0) to Abaqus defaults (0.06, 1.2) improves σ-ε fidelity for PA12 lattice quasi-static compression.

## Setup
- N=2 (2x2x2), cell=5mm, radius=0.5, slider=8
- Aux + BCC topologies
- Other params: E=1010 MPa, contactStiffnessScaleFactor=5.0, friction=0.15, contact damping=0.1, NS3 plastic + DuctileDamage
- Mass scaling dt=5e-6, ExplicitDynamics quasi-static

## Result

|              | BCC OLD | BCC NEW | Δ      | Aux OLD | Aux NEW | Δ      |
|--------------|---------|---------|--------|---------|---------|--------|
| σ_pk (MPa)   | 1.488   | 1.488   |  0.0%  | 4.43    | 4.35    | -1.6%  |
| ε_pk         | 0.190   | 0.185   | small  | 0.047   | 0.047   |  0.0%  |
| E_lat (MPa)  | 17.50   | 17.50   |  0.0%  | 113.85  | 113.84  |  0.0%  |
| σ@ε=0.05     | 0.821   | 0.821   |  0.0%  | 4.34    | 4.10    | **-5.6%** |
| σ@ε=0.10     | 1.296   | 1.296   |  0.0%  | 3.27    | 3.34    | +2.2%  |
| σ@ε=0.15     | 1.457   | 1.457   |  0.0%  | 2.90    | 2.86    | -1.3%  |
| σ@ε=0.30     | 1.617   | 1.610   | -0.4%  | 2.43    | 2.42    | -0.4%  |
| σ@ε=0.45     | 2.602   | 2.600   |  0.0%  | 3.10    | 3.13    | +0.8%  |
| **wall time**| 10 min  | 48 min  | **5×** | 31 min  | ~50 min | **~2×** |

## Conclusion
**Rolled back to NS3 (0.25, 2.0).** Defaults are literature-standard (Lee&Kajtaz 2022, etc.) but the impact on σ-ε for this quasi-static + mass-scaled setup is negligible (<2% on all summary metrics; the only meaningful change is Aux post-peak at ε=0.05, -5.6%). Cost is 2-5× wall time per analysis. Not worth it.

## Files
- `<topo>_OLD_bv0p25.txt` — feature_data with bv=0.25/2.0 (NS3, current)
- `<topo>_NEW_bv0p06.txt` — feature_data with bv=0.06/1.2 (Abaqus default)
- Format: Abaqus xy report (col1=disp, col2=force). Strain = disp/10, stress = force/100.
