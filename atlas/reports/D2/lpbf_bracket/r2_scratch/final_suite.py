# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch')
from t2_slab import hslab_pillar
from atlas.gates.gates import run_gates
from atlas.geometry.realize_graph import realize_graph
from atlas.geometry.cells import generate_cell
from atlas.geometry.tpms import generate_tpms_at_density
from atlas.printability.checks import (check_overhangs, validate_mesh,
                                       measure_min_feature, check_powder_escape)

def b1(m, n, full=True):
    row = {}
    oh = check_overhangs(m, 'LPBF')
    row['overhang_area_fraction'] = round(oh['value']['overhang_area_fraction'], 5)
    row['overhang_pass_vs_0.05'] = oh['pass']
    vm = validate_mesh(m, 'LPBF')
    row['watertight_b1'] = vm['pass']
    if full:
        mf = measure_min_feature(m, 'LPBF')
        row['min_feature_p5_mm'] = round(mf['value']['p5_mm'], 4)
        row['min_feature_min_mm'] = round(mf['value']['min_mm'], 4)
        row['min_feature_pass'] = mf['pass']
        pe = check_powder_escape(m, 'LPBF')
        row['trapped_void_mm3'] = pe['value']['trapped_void_mm3']
        row['powder_pass'] = pe['pass']
    return row

out = {}

# ---- candidate 1: Tier-2 HSlabPillar (A: k5 rs0.75 r0.52) ----
doc = hslab_pillar(0.75, 0.52, 0.52, 5)
g = run_gates(doc, process='LPBF')
c1 = {'doc': doc, 'gates': g}
for n in (1, 3):
    rr = realize_graph(doc, n=n)
    c1[f'n{n}'] = {'realize_ok': rr.ok, 'stats': rr.stats}
    if rr.ok:
        c1[f'n{n}'].update(b1(rr.mesh.trimesh, n, full=True))
out['c1_slab'] = c1
print('c1 done', c1['n1']['overhang_area_fraction'], c1['n3']['overhang_area_fraction'])

# ---- candidate 2: Tier-1.75 schwarz_p skeletal rho 0.5 ----
c2 = {}
for n in (1, 3):
    cm = generate_tpms_at_density('schwarz_p', 'skeletal', 0.50, cell_size=5.0, n=n)
    c2[f'n{n}'] = {'rho_achieved': round(cm.rho_achieved, 5), 'threshold_t': round(cm.threshold_t, 6),
                   'watertight_dualtrack': bool(cm.is_watertight)}
    c2[f'n{n}'].update(b1(cm.trimesh, n, full=(n == 1)))
out['c2_schwarzP_skel'] = c2
print('c2 done', c2['n1']['overhang_area_fraction'], c2['n3']['overhang_area_fraction'])

# ---- candidate 3: Tier-1.5 Cubic r=0.55 (default sphere_ratio) ----
c3 = {}
for n in (1, 3):
    cm = generate_cell('Cubic', slider=0, radius=0.55, n=n)
    c3[f'n{n}'] = {'rho_mesh': round(cm.volume / (125.0 * n**3), 5),
                   'watertight_dualtrack': bool(cm.is_watertight)}
    c3[f'n{n}'].update(b1(cm.trimesh, n, full=(n == 1)))
out['c3_cubic'] = c3
print('c3 done', c3['n1']['overhang_area_fraction'], c3['n3']['overhang_area_fraction'])

json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\final_suite.json', 'w'),
          indent=1, ensure_ascii=False, default=str)
print('SAVED')
