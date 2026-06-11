# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
from atlas.printability.checks import check_overhangs
from atlas.geometry.tpms import generate_tpms_at_density, TPMS_TYPES
out = {}
for tt in TPMS_TYPES:
    for var in ('sheet', 'skeletal'):
        try:
            cm = generate_tpms_at_density(tt, var, 0.30, cell_size=5.0, n=1)
            f = check_overhangs(cm.trimesh, process='LPBF')['value']['overhang_area_fraction']
            out[f'{tt}_{var}'] = {'overhang': round(f,4), 'rho': round(cm.rho_achieved,4)}
        except Exception as e:
            out[f'{tt}_{var}'] = {'error': str(e)[:120]}
        print(f'{tt}_{var}', out[f'{tt}_{var}'])
json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\survey2.json','w'), indent=1)
