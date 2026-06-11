# -*- coding: utf-8 -*-
"""Tier-2 vertical-wall graphs: gates -> realize -> B1 checks (n=1 and n=3)."""
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
from atlas.gates.gates import run_gates
from atlas.geometry.realize_graph import realize_graph
from atlas.printability.checks import (check_overhangs, validate_mesh,
                                       measure_min_feature, check_powder_escape)

def vwall_grid(rp=0.75, rt=0.5, k=5):
    """crossed vertical walls: pillars at pitch 1/k along x-wall(y=0) and y-wall(x=0)."""
    nodes = [{'id': f'A{i}', 'frac': [i/k, 0.0, 0.0]} for i in range(k)]
    nodes += [{'id': f'B{j}', 'frac': [0.0, j/k, 0.0]} for j in range(1, k)]
    edges = [{'n1': n['id'], 'n2': n['id'], 'shift': [0,0,1], 'radius_mm': rp} for n in nodes]
    for i in range(k-1):
        edges.append({'n1': f'A{i}', 'n2': f'A{i+1}', 'shift': [0,0,0], 'radius_mm': rt})
    edges.append({'n1': f'A{k-1}', 'n2': 'A0', 'shift': [1,0,0], 'radius_mm': rt})
    edges.append({'n1': 'A0', 'n2': 'B1', 'shift': [0,0,0], 'radius_mm': rt})
    for j in range(1, k-1):
        edges.append({'n1': f'B{j}', 'n2': f'B{j+1}', 'shift': [0,0,0], 'radius_mm': rt})
    edges.append({'n1': f'B{k-1}', 'n2': 'A0', 'shift': [0,1,0], 'radius_mm': rt})
    return {'schema': 'atlas-cell-graph/1.0', 'name': 'VWallGrid_XY',
            'cell': {'size_mm': 5.0}, 'nodes': nodes, 'edges': edges,
            'default_radius_mm': rp,
            'lineage': {'tier': 'tier2', 'generator': 'atlas-candidate-generator/D2-r2',
                        'source': 'round-2 anti-overhang design: crossed vertical walls realized as fused vertical pillar rows; horizontal tie edges fully buried inside pillar union (graph-level 3D connectivity, zero exposed downward-normal area)'},
            'free_params': {'radius_mm': {'value': rp, 'min': 0.5, 'max': 0.9,
                'description': 'pillar radius (wall thickness driver); ties fixed via per-edge radius'}}}

def vwall_comb(rp=0.75, rt=0.5, k=5):
    """single x-wall + y-web through mid pillar W."""
    nodes = [{'id': f'A{i}', 'frac': [i/k, 0.0, 0.0]} for i in range(k)]
    nodes.append({'id': 'W', 'frac': [2/k, 0.5, 0.0]})
    edges = [{'n1': n['id'], 'n2': n['id'], 'shift': [0,0,1], 'radius_mm': rp} for n in nodes]
    for i in range(k-1):
        edges.append({'n1': f'A{i}', 'n2': f'A{i+1}', 'shift': [0,0,0], 'radius_mm': rt})
    edges.append({'n1': f'A{k-1}', 'n2': 'A0', 'shift': [1,0,0], 'radius_mm': rt})
    edges.append({'n1': 'A2', 'n2': 'W', 'shift': [0,0,0], 'radius_mm': rt})
    edges.append({'n1': 'W', 'n2': 'A2', 'shift': [0,1,0], 'radius_mm': rt})
    return {'schema': 'atlas-cell-graph/1.0', 'name': 'VWallComb_P',
            'cell': {'size_mm': 5.0}, 'nodes': nodes, 'edges': edges,
            'default_radius_mm': rp,
            'lineage': {'tier': 'tier2', 'generator': 'atlas-candidate-generator/D2-r2',
                        'source': 'round-2 anti-overhang design: single-direction vertical wall + minimal exposed horizontal web through intermediate pillar W (lower rho variant; web is the only exposed non-vertical surface)'},
            'free_params': {'radius_mm': {'value': rp, 'min': 0.5, 'max': 0.9,
                'description': 'pillar radius; web/tie radius per-edge'}}}

def evaluate(name, doc):
    res = {'name': name}
    g = run_gates(doc, process='LPBF')
    res['gates_passed'] = g['passed']; res['hard_failures'] = g.get('hard_failures', ['C1'])
    res['flags'] = g['flags']
    res['C5'] = g['gates']['C5']['value']; res['C7'] = g['gates']['C7']['value']
    res['C4'] = {k: g['gates']['C4']['value'][k] for k in ('maxwell_M','tendency')}
    res['C3'] = g['gates']['C3']['value']
    if not g['passed']:
        print(json.dumps(res, ensure_ascii=False)); return res, g
    for n in (1, 3):
        rr = realize_graph(doc, n=n)
        key = f'n{n}'
        if not rr.ok:
            res[key] = {'realize_ok': False, 'reason': rr.reason}; continue
        m = rr.mesh.trimesh
        oh = check_overhangs(m, process='LPBF')
        vm = validate_mesh(m, process='LPBF')
        row = {'realize_ok': True, 'stats': rr.stats,
               'overhang': round(oh['value']['overhang_area_fraction'], 5),
               'overhang_pass': oh['pass'],
               'watertight_b1': vm['pass']}
        if n == 1:
            mf = measure_min_feature(m, process='LPBF')
            pe = check_powder_escape(m, process='LPBF')
            row['min_feature_p5'] = round(mf['value']['p5_mm'], 3)
            row['min_feature_pass'] = mf['pass']
            row['trapped_void_mm3'] = pe['value']['trapped_void_mm3']
            row['powder_pass'] = pe['pass']
        res[key] = row
    print(json.dumps(res, ensure_ascii=False))
    return res, g

if __name__ == '__main__':
    out = {}
    for name, doc in [('grid_rp075', vwall_grid(0.75, 0.5, 5)),
                      ('grid_rp065_k6', vwall_grid(0.65, 0.5, 6)),
                      ('comb_rp075', vwall_comb(0.75, 0.5, 5))]:
        out[name] = evaluate(name, doc)[0]
    json.dump(out, open(r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch\t2_results.json','w'), indent=1)
