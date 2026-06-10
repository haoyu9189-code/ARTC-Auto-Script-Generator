"""P2-1b:Lumpe-Stanković Unit Cell Catalog 解析 + beam_homog 金标准对照。

目录约定(头部 + pcu 条目反推):
- 归一胞,基材 E_s=1 MPa,ν=0.3;模量单位 MPa
- 列出的 Ex/Ey/Ez 在 **ρ̄ = 1%** 处取值(pcu:Ex=3.34e-3=0.33·0.01,
  与解析解 E_z=ρ̄/3 精确一致 —— 协议的内建锚点)
- 节点 1-based 索引;装饰表示(角点重复)→ 走与 seeds.py 同款商图
  规范化;* 标记 = 数值问题条目,排除
许可:CC BY-NC 4.0(非商用,errata 许可表已登记)。
"""
import os
import re

import numpy as np

CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'data', 'external', 'Unit_Cell_Catalog.txt')
RHO_REF = 0.01  # 目录性能取值密度

_num = r'[-+0-9.Ee]+'


def iter_entries(path=CATALOG):
    """流式解析目录条目。yield dict(name, star, cubic, props, C, n,
    nodes[频率坐标], bars[(i,j) 0-based])。"""
    block = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('-----') and block:
                e = _parse_block(block)
                if e:
                    yield e
                block = []
            else:
                block.append(line.rstrip('\n'))
    if block:
        e = _parse_block(block)
        if e:
            yield e


def _parse_block(lines):
    text = '\n'.join(lines)
    m = re.search(r'^Name:\s*(.+)$', text, re.M)
    if not m:
        return None
    raw_name = m.group(1).strip()
    star = '*' in raw_name
    name = raw_name.replace('*', '').strip()

    pm = re.search(r'unit cell parameters.*?\n\s*(' + _num + r'),\s*('
                   + _num + r'),\s*(' + _num + r'),\s*(' + _num
                   + r'),\s*(' + _num + r'),\s*(' + _num + r')', text)
    if not pm:
        return None
    a, b, c, al, be, ga = (float(pm.group(i)) for i in range(1, 7))
    cubic = (abs(a - 1) < 1e-4 and abs(b - 1) < 1e-4 and abs(c - 1) < 1e-4
             and all(abs(x - 90) < 1e-3 for x in (al, be, ga)))

    props = {}
    for key in ('Ex', 'Ey', 'Ez', 'Gyz', 'Gxz', 'Gxy'):
        km = re.search(key + r'\s*=\s*(' + _num + r')', text)
        if km:
            props[key] = float(km.group(1))
    Cm = re.search(r'Scaling constants Cx = (' + _num + r'), Cy = ('
                   + _num + r'), Cz = (' + _num + r')', text)
    nm = re.search(r'Scaling exponents nx = (' + _num + r'), ny = ('
                   + _num + r'), nz = (' + _num + r')', text)

    nodes, bars = [], []
    sec = None
    for ln in lines:
        s = ln.strip()
        if s.startswith('Nodal positions'):
            sec = 'n'
            continue
        if s.startswith('Bar connectivities'):
            sec = 'b'
            continue
        if not s:
            continue
        if sec == 'n':
            parts = s.split()
            if len(parts) == 3:
                try:
                    nodes.append(tuple(float(x) for x in parts))
                except ValueError:
                    sec = None
        elif sec == 'b':
            parts = s.split()
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                bars.append((int(parts[0]) - 1, int(parts[1]) - 1))

    if not nodes or not bars:
        return None
    return {'name': name, 'star': star, 'cubic': cubic,
            'abc': (a, b, c), 'props': props,
            'C': (tuple(float(Cm.group(i)) for i in range(1, 4))
                  if Cm else None),
            'n': (tuple(float(nm.group(i)) for i in range(1, 4))
                  if nm else None),
            'nodes': nodes, 'bars': bars}


def to_quotient_doc(entry, rho=RHO_REF):
    """装饰条目 → atlas-cell-graph/1.0(商图规范化,seeds.py 同款数学)。

    radius 由一阶密度反解:ρ = π r² ΣL / V(ρ̄=1% 处一阶式精确)。"""
    raw = [np.asarray(p, float) for p in entry['nodes']]

    def wrap(f):
        f = np.round(f, 9)
        w = f - np.floor(f)
        w[np.abs(w - 1) < 1e-9] = 0.0
        w[np.abs(w) < 1e-9] = 0.0
        return w

    pos_to_id, node_pos = {}, {}
    for p in raw:
        key = tuple(np.round(wrap(p), 6))
        if key not in pos_to_id:
            pos_to_id[key] = f'N{len(pos_to_id)}'
            node_pos[pos_to_id[key]] = np.asarray(key, float)

    edges = {}
    total_L = 0.0
    for i, j in entry['bars']:
        pi, pj = raw[i], raw[j]
        wi, wj = wrap(pi), wrap(pj)
        n1 = pos_to_id[tuple(np.round(wi, 6))]
        n2 = pos_to_id[tuple(np.round(wj, 6))]
        shift = np.round((np.round(pj, 9) - wj) - (np.round(pi, 9) - wi)
                         ).astype(int)
        if n1 > n2 or (n1 == n2 and tuple(shift) < tuple(-shift)):
            n1, n2 = n2, n1
            shift = -shift
        if n1 == n2 and not shift.any():
            continue
        key = (n1, n2, tuple(int(s) for s in shift))
        if key in edges:
            continue
        L = float(np.linalg.norm(node_pos[n2] + shift - node_pos[n1]))
        total_L += L
        edges[key] = {'n1': n1, 'n2': n2,
                      'shift': [int(s) for s in shift]}
    if total_L <= 0:
        raise ValueError(f"{entry['name']}: 零总杆长")
    r = float(np.sqrt(rho * 1.0 / (np.pi * total_L)))
    return {
        'schema': 'atlas-cell-graph/1.0', 'name': entry['name'],
        'cell': {'size_mm': 1.0},
        'nodes': [{'id': nid, 'frac': [float(x) for x in node_pos[nid]]}
                  for nid in sorted(node_pos)],
        'edges': [edges[k] for k in sorted(edges)],
        'default_radius_mm': r,
        'free_params': {},
        'lineage': {'tier': 'tier1.75',
                    'generator': 'atlas.mechanics.lumpe_catalog',
                    'source': 'Lumpe & Stankovic 2021, '
                              'DOI 10.3929/ethz-b-000457598 (CC BY-NC)'},
    }


def validate_sample(n_target=24, stride=40, rho=RHO_REF):
    """抽样对照:目录立方条目(非 *)每 stride 取一,beam_homog vs
    目录 Ex/Ey/Ez。返回逐条记录 + 汇总统计。"""
    from atlas.mechanics.beam_homog import homogenize
    rows = []
    seen_cubic = 0
    for entry in iter_entries():
        if not entry['cubic'] or entry['star'] or len(entry['props']) < 3:
            continue
        seen_cubic += 1
        if (seen_cubic - 1) % stride:
            continue
        try:
            doc = to_quotient_doc(entry, rho=rho)
            r = homogenize(doc, E=1.0, G=1.0 / 2.6, nu=0.3)
        except Exception as ex:
            rows.append({'name': entry['name'], 'error': str(ex)[:80]})
            continue
        if not r['constants']:
            rows.append({'name': entry['name'], 'error': 'C* 奇异'})
            continue
        rec = {'name': entry['name'], 'ld': r['ld_median'],
               'n_nodes': r['n_nodes'], 'n_edges': r['n_edges']}
        devs = []
        for ours, theirs in (('E_x', 'Ex'), ('E_y', 'Ey'), ('E_z', 'Ez')):
            ref = entry['props'][theirs]
            val = r['constants'][ours]
            if ref > 0:
                d = val / ref - 1
                rec[theirs] = {'ref': ref, 'beam': round(val, 8),
                               'dev': round(d, 4)}
                devs.append(abs(d))
        rec['max_abs_dev'] = round(max(devs), 4) if devs else None
        rows.append(rec)
        if sum(1 for x in rows if 'max_abs_dev' in x) >= n_target:
            break
    devs = [x['max_abs_dev'] for x in rows if x.get('max_abs_dev')
            is not None]
    summary = {'n_compared': len(devs),
               'median_dev': round(float(np.median(devs)), 4),
               'p90_dev': round(float(np.percentile(devs, 90)), 4),
               'max_dev': round(float(np.max(devs)), 4),
               'n_errors': sum(1 for x in rows if 'error' in x),
               'rho_ref': rho}
    return rows, summary


if __name__ == '__main__':
    rows, s = validate_sample()
    print(f"对照 {s['n_compared']} 条 | 中位偏差 {s['median_dev']:.1%} | "
          f"p90 {s['p90_dev']:.1%} | 最大 {s['max_dev']:.1%} | "
          f"解析失败 {s['n_errors']}")
    for r in rows:
        if 'error' in r:
            print(f"  {r['name']:<22} ERROR {r['error']}")
        elif r['max_abs_dev'] > 0.30:
            print(f"  {r['name']:<22} max_dev={r['max_abs_dev']:+.1%} "
                  f"l/d={r['ld']:.0f} (>30%,待归因)")
        else:
            print(f"  {r['name']:<22} max_dev={r['max_abs_dev']:+.1%} "
                  f"l/d={r['ld']:.0f}")
