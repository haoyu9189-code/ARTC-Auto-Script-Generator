# -*- coding: utf-8 -*-
"""round-2 overhang survey: probes + 24 DB topologies + TPMS, B1 check_overhangs (LPBF, build z)."""
import json, sys, numpy as np
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
from atlas.printability.checks import check_overhangs
from atlas.geometry.cells import generate_cell, list_topologies, _strut_manifold, _union, CellMesh
from manifold3d import Manifold

def frac(mesh):
    r = check_overhangs(mesh, process='LPBF')
    return r['value']['overhang_area_fraction']

out = {}

# --- probes: single primitives (not candidates, mechanism probes) ---
p0 = np.array([0.,0.,0.])
probes = {
 'vertical_cyl':  _strut_manifold(p0, np.array([0.,0.,5.]), 0.6, 24),
 'horizontal_cyl':_strut_manifold(p0, np.array([5.,0.,0.]), 0.6, 24),
 'diag45_cyl':    _strut_manifold(p0, np.array([5.,0.,5.]), 0.6, 24),
 'sphere':        Manifold.sphere(0.6, 24),
}
pr = {}
for k, m in probes.items():
    cm = CellMesh(m, k, 0, 0.6, 1, 5.0)
    pr[k] = round(frac(cm.trimesh), 4)
# union of two overlapping vertical cylinders (wall element probe)
wall = _union([_strut_manifold(np.array([0.,0.,0.]), np.array([0.,0.,5.]), 0.7, 24),
               _strut_manifold(np.array([1.0,0.,0.]), np.array([1.0,0.,5.]), 0.7, 24)])
pr['two_overlap_vert_cyls'] = round(frac(CellMesh(wall,'w',0,0.7,1,5.0).trimesh), 4)
out['probes'] = pr
print('PROBES', json.dumps(pr))

# --- 24 DB topologies, r=0.55, n=1, slider 0 and 4 ---
topo = {}
for t in list_topologies():
    row = {}
    for sl in (0, 4):
        try:
            cm = generate_cell(t, slider=sl, radius=0.55, n=1)
            row[f's{sl}'] = {'overhang': round(frac(cm.trimesh), 4),
                             'watertight': bool(cm.is_watertight),
                             'rho': round(cm.volume/125.0, 4)}
        except Exception as e:
            row[f's{sl}'] = {'error': str(e)[:100]}
    topo[t] = row
    print(t, json.dumps(row))
out['db_topologies'] = topo

json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\survey1.json','w'), indent=1)
print('DONE')
