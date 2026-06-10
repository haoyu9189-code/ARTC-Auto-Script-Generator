# atlas_demo.html 构建器:导出真实几何与 D1 判决数据,注入模板
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _ROOT)

from atlas.geometry import parse_structure
from atlas.abaqus_adapter import graph_to_structure_text
from atlas.orchestration.acceptance import CASES, NOVEL_GRAPH, run_case


def segments_from(coords, cyls):
    segs = []
    for a, b in cyls:
        if a in coords and b in coords:
            p, q = coords[a], coords[b]
            segs.append([round(float(x), 3) for x in (*p, *q)])
    return segs


def parse_text(text):
    import numpy as np
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


lattices = {}
for topo, tier in (('Octet_truss', 'TIER-1'), ('Auxetic', 'TIER-1'),
                   ('Kelvin', 'TIER-1')):
    c, y = parse_structure(topo, 4)
    lattices[topo] = {'tier': tier, 'segments': segments_from(c, y)}
text, _ = graph_to_structure_text(NOVEL_GRAPH)
c, y = parse_text(text)
lattices['cubic_plus_diagonal'] = {'tier': 'TIER-2 · 库外生成',
                                   'segments': segments_from(c, y)}

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

tmpl_path = os.path.join(os.path.dirname(__file__),
                         'atlas_demo_template.html')
out_path = os.path.join(_ROOT, 'atlas_demo.html')
html = open(tmpl_path, encoding='utf-8').read()
html = html.replace('__ATLAS_DATA__', json.dumps(data, ensure_ascii=False))
open(out_path, 'w', encoding='utf-8', newline='\n').write(html)
print(f'written {out_path} ({len(html)//1024} KB, '
      f'{sum(len(v["segments"]) for v in lattices.values())} segments, '
      f'{len(cases)} cases)')
