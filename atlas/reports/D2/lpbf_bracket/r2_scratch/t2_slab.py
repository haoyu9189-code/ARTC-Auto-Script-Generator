# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
from atlas.gates.gates import run_gates
from atlas.geometry.realize_graph import realize_graph
from atlas.printability.checks import (check_overhangs, validate_mesh,
                                       measure_min_feature, check_powder_escape)

def hslab_pillar(rs=0.75, rt=0.5, rp=0.5, k=5, pillar_nodes=1):
    """horizontal slab (k fused x-cylinders at y-pitch 1/k) + vertical pillar on S0."""
    nodes = [{'id': f'S{j}', 'frac': [0.0, j/k, 0.0]} for j in range(k)]
    edges = [{'n1': f'S{j}', 'n2': f'S{j}', 'shift': [1,0,0], 'radius_mm': rs} for j in range(k)]
    for j in range(k-1):
        edges.append({'n1': f'S{j}', 'n2': f'S{j+1}', 'shift': [0,0,0], 'radius_mm': rt})
    edges.append({'n1': f'S{k-1}', 'n2': 'S0', 'shift': [0,1,0], 'radius_mm': rt})
    edges.append({'n1': 'S0', 'n2': 'S0', 'shift': [0,0,1], 'radius_mm': rp})
    return {'schema': 'atlas-cell-graph/1.0', 'name': 'HSlabPillar',
            'cell': {'size_mm': 5.0}, 'nodes': nodes, 'edges': edges,
            'default_radius_mm': rs,
            'lineage': {'tier': 'tier2', 'generator': 'atlas-candidate-generator/D2-r2',
                        'source': 'round-2 anti-overhang: horizontal slab of fused x-cylinders (pitch<r*sqrt2 so exposed bottom scallop normals stay within 45deg of straight-down = self-classified OK) + single vertical pillar for z-connectivity'},
            'free_params': {'radius_mm': {'value': rs, 'min': 0.5, 'max': 0.9,
                'description': 'slab cylinder radius; ties/pillar per-edge'}}}

def evaluate(name, doc, ns=(1,3)):
    res = {'name': name}
    g = run_gates(doc, process='LPBF')
    res['gates_passed'] = g['passed']; res['hard_failures'] = g.get('hard_failures', ['C1'])
    if not g['passed']:
        print(name, 'GATES FAIL', res['hard_failures']); return res
    res['C5'] = g['gates']['C5']['value']; res['C4'] = {k: g['gates']['C4']['value'][k] for k in ('maxwell_M','tendency')}
    for n in ns:
        rr = realize_graph(doc, n=n)
        if not rr.ok:
            res[f'n{n}'] = {'realize_ok': False, 'reason': rr.reason}
            print(name, f'n{n} realize FAIL', rr.reason); continue
        m = rr.mesh.trimesh
        oh = check_overhangs(m, 'LPBF')
        row = {'realize_ok': True, 'rho': rr.stats['rho_rel'],
               'overhang': round(oh['value']['overhang_area_fraction'],5)}
        if n == 1:
            row['min_feature_p5'] = round(measure_min_feature(m,'LPBF')['value']['p5_mm'],3)
            row['trapped_void_mm3'] = check_powder_escape(m,'LPBF')['value']['trapped_void_mm3']
            row['watertight_b1'] = validate_mesh(m,'LPBF')['pass']
        res[f'n{n}'] = row
        print(name, f'n{n}', json.dumps(row))
    return res

if __name__ == '__main__':
    out = {}
    for nm, doc in [('slab_rs075_rp05', hslab_pillar(0.75, 0.5, 0.5, 5)),
                    ('slab_rs065_k6', hslab_pillar(0.65, 0.5, 0.5, 6)),
                    ('slab_rs075_rp075', hslab_pillar(0.75, 0.5, 0.75, 5))]:
        out[nm] = evaluate(nm, doc)
    json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\slab_results.json','w'), indent=1)
