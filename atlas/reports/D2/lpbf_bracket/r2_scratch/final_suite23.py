# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
from atlas.geometry.cells import generate_cell
from atlas.geometry.tpms import generate_tpms_at_density
from atlas.printability.checks import (check_overhangs, validate_mesh,
                                       measure_min_feature, check_powder_escape)

def b1(m, full=True):
    row = {}
    oh = check_overhangs(m, 'LPBF')
    row['overhang_area_fraction'] = round(oh['value']['overhang_area_fraction'], 5)
    row['overhang_pass_vs_0.05'] = oh['pass']
    row['watertight_b1'] = validate_mesh(m, 'LPBF')['pass']
    if full:
        mf = measure_min_feature(m, 'LPBF')
        row['min_feature_p5_mm'] = round(mf['value']['p5_mm'], 4)
        row['min_feature_pass'] = mf['pass']
        pe = check_powder_escape(m, 'LPBF')
        row['trapped_void_mm3'] = pe['value']['trapped_void_mm3']
        row['powder_pass'] = pe['pass']
    return row

out = {}
c2 = {}
for n in (1, 3):
    cm = generate_tpms_at_density('schwarz_p', 'skeletal', 0.50, cell_size=5.0, n=n)
    c2[f'n{n}'] = {'rho_achieved': round(cm.rho_achieved, 5), 'threshold_t': round(cm.threshold_t, 6),
                   'watertight_dualtrack': bool(cm.is_watertight)}
    c2[f'n{n}'].update(b1(cm.trimesh, full=(n == 1)))
    print('c2', f'n{n}', json.dumps(c2[f'n{n}']))
out['c2_schwarzP_skel'] = c2

c3 = {}
for n in (1, 3):
    cm = generate_cell('Cubic', slider=0, radius=0.55, n=n)
    c3[f'n{n}'] = {'rho_mesh': round(cm.volume / (125.0 * n**3), 5),
                   'watertight_dualtrack': bool(cm.is_watertight)}
    c3[f'n{n}'].update(b1(cm.trimesh, full=(n == 1)))
    print('c3', f'n{n}', json.dumps(c3[f'n{n}']))
out['c3_cubic'] = c3
json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\final_suite23.json', 'w'), indent=1)
print('SAVED')
