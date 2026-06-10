# atlas_demo.html 构建器 v2:真实几何 + D1 判决 + 压缩工况变形场(frame FEM)
# + 生成式搜索发现的新拓扑 + 公式/角度辅助数据
import json
import math
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, '.claude', 'skills', 'atlas',
                                'scripts'))

import numpy as np

from atlas.geometry import parse_structure
from atlas.abaqus_adapter import graph_to_structure_text
from atlas.orchestration.acceptance import CASES, run_case
from atlas.mechanics import solve_compression
from atlas.mechanics.gen_search import search, _load_seed
from atlas.data.ingest_cell_db import classify
import gibson_ashby


def segments_from(coords, cyls):
    return [[round(float(x), 3) for x in (*coords[a], *coords[b])]
            for a, b in cyls if a in coords and b in coords]


def parse_text(text):
    coords, cyls, in_c = {}, [], False
    for line in text.split('\n'):
        line = line.strip()
        if 'cylinders = [' in line:
            in_c = True
            continue
        if in_c and line == ']':
            in_c = False
            continue
        if '=' in line and not in_c:
            k, v = line.split('=', 1)
            coords[k.strip()] = np.array(eval(v.strip()), float)
        elif in_c and line:
            a, b = [x.strip() for x in line.rstrip(',').strip('()').split(',')]
            cyls.append((a, b))
    return coords, cyls


def fem_pack(doc, label_class):
    """压缩工况求解 → demo 数据包(变形场/公式实算值/角度直方)。"""
    fem = solve_compression(doc, n=2, strain=0.05)
    coords = fem['coords']
    u = fem['u'].reshape(-1, 6)[:, :3]
    elems, angles = [], []
    for pe in fem['per_elem']:
        i, j = pe['i'], pe['j']
        d = coords[j] - coords[i]
        ang = math.degrees(math.acos(min(1, abs(d[2]) / pe['L'])))
        angles.append(ang)
        elems.append([i, j, round(pe['axial_stress'], 3),
                      round(pe['bend_frac'], 3), round(ang, 1)])
    hist = [0] * 6
    for a in angles:
        hist[min(5, int(a // 15))] += 1
    b, jn = len(doc['edges']), len(doc['nodes'])
    M = b - 3 * jn + 6
    from atlas.gates import run_gates
    rho = run_gates(doc)['gates']['C5']['value'][
        'rho_estimate_at_default_r']
    ga = gibson_ashby.estimate(label_class, rho, 1700.0, 45.0)
    lengths = [pe['L'] for pe in fem['per_elem']]
    r0 = doc['default_radius_mm']
    return {
        'nodes': [[round(float(x), 3) for x in p] for p in coords],
        'u': [[round(float(x), 5) for x in v] for v in u],
        'elems': elems,
        'E_star': round(fem['E_star'], 2),
        'sigma': round(fem['sigma'], 4), 'strain': fem['strain'],
        'H': round(fem['H'], 2), 'rho': round(rho, 4),
        'maxwell_M': M,
        'tendency': 'stretch-leaning' if M >= 0 else 'bending-leaning',
        'bend_mean': round(float(np.mean([e[3] for e in elems])), 3),
        'E_GA': round(ga['value']['E_MPa'], 2),
        'ga_model': ga['value']['model'],
        'klass': label_class,
        'angle_hist': hist,
        'ld': round(float(np.median(lengths)) / (2 * r0), 2),
        'caveat': fem['caveat'],
    }


# ---- 展示点阵:3 个种子 + 生成式搜索冠军 ----
lattices = {}
for topo in ('Octet_truss', 'Kelvin', 'Auxetic'):
    c, y = parse_structure(topo, 4)
    doc = _load_seed(topo)
    lattices[topo] = {'tier': 'TIER-1 · 库内',
                      'segments': segments_from(c, y),
                      'fem': fem_pack(doc, classify(topo))}

print('运行生成式搜索(变异→硬门→WL 查重→FEM 裁判)…')
gs = search()
champ = gs['top'][0]
gdoc = champ['doc']
text, _ = graph_to_structure_text(gdoc)
c, y = parse_text(text)
best_seed_score = max(v['score'] for v in gs['seed_refs'].values())
lattices['GEN-01'] = {
    'tier': 'TIER-2 · 库外生成(screening)',
    'segments': segments_from(c, y),
    'fem': fem_pack(gdoc, classify(champ['parent'])),
    'gen': {'parent': champ['parent'],
            'score': round(champ['score'], 1),
            'best_seed_score': round(best_seed_score, 1),
            'vs_parent': round(champ['score'] /
                               gs['seed_refs'][champ['parent']]['score'], 2),
            'proposed': gs['stats']['proposed'],
            'survivors': gs['n_survivors'],
            'dup_killed': gs['stats']['dup'],
            'wl_hash': champ['wl_hash'][:16]}}
print(f"GEN-01 = {gdoc['name']} score={champ['score']:.1f} "
      f"(种子最优 {best_seed_score:.1f})")

# ---- D1 案例(同 v1) ----
cases = []
n_checks_total = 0
src_counts = {}
for case in CASES:
    judged = run_case(case)
    rows = []
    for item in judged:
        t = item['trace']
        geo = item['candidate'].get('geometry', {})
        topo = geo.get('topology') or geo.get('graph_doc', {}).get('name')
        rho = next((ch['value'] for ch in t['checks']
                    if ch['dimension'] == 'density'), None)
        m = t.get('margin')
        n_checks_total += len(t['checks'])
        for ch in t['checks']:
            st = ch.get('source_type', 'internal_computed')
            src_counts[st] = src_counts.get(st, 0) + 1
        rows.append({'id': t['candidate_id'], 'tier': t['tier'],
                     'topo': topo, 'rho': rho,
                     'margin': (round(m['ratio'], 3) if m else None),
                     'verdict': t['verdict'],
                     'reasons': t['verdict_reasons'][:2]})
    cases.append({'key': case['key'], 'title': case['title'],
                  'process': case['spec']['process'],
                  'material': case['spec']['material'],
                  'design': case['spec']['design_value_with_fos'],
                  'fos': case['spec']['fos'],
                  'high_risk': case['high_risk'], 'rows': rows})

data = {'lattices': lattices, 'cases': cases,
        'stats': {'tasks': '18/18', 'tests': 257, 'structures': 5304,
                  'catalog': 17262, 'checks': n_checks_total,
                  'errata': 19},
        'sources': src_counts}

tmpl = open(os.path.join(os.path.dirname(__file__),
                         'atlas_demo_template.html'),
            encoding='utf-8').read()
out_path = os.path.join(_ROOT, 'atlas_demo.html')
open(out_path, 'w', encoding='utf-8', newline='\n').write(
    tmpl.replace('__ATLAS_DATA__', json.dumps(data, ensure_ascii=False)))
print(f'written {out_path}')
