"""P2-1c:节点刚化修正标定 —— frame 块求解 vs 自家 FEA 原始曲线。

标定设计(v2,诊断后修正):
- 参照 = **原始 StaCompre 力-位移曲线自提初始斜率**(curves 表,
  0–2% 应变窗线性拟合;CSV 平滑特征与原始曲线同量级已核实,但用
  原始曲线 provenance 更干净)
- 模型 = **frame_fem.solve_compression(n=1)**:底面固支/顶面位移/
  横向锁定 —— 与 FEA 单胞平台压缩同边界条件。
  ⚠ 周期均质化(beam_homog)对照 n=1 平台数据会把「尺寸效应/边界层」
  混进修正(实测弯曲类差 20–30×,BCC 细长杆也如此,与 l/d 无关)——
  那是 BC 差异不是梁理论失效;尺寸效应归 Size-Effect Corrector,
  本标定只吸收节点刚化 + 单元理想化。
- 口径:E_s=1010 MPa(model/Static_model.py 实值),载荷轴 y
  (structure_set 为 y 压设计)→ 商图 y↔z 轴置换后用 frame z 向压缩。

产出:atlas/references/beam_error_bars.json(每类 correction +
p50/p90 残差 + l/d 域);certify() 给 margin 级证据
(source_type='beam_fem_calibrated',按 p90 折减)。
"""
import json
import os
import sqlite3
import sys

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas.data.ingest_cell_db import classify
from atlas.geometry import list_topologies
from atlas.mechanics.frame_fem import solve_compression
from atlas.schema.seeds import seed_graph

E_FEA = 1010.0   # model/Static_model.py material.Elastic 实值
NU_FEA = 0.3
G_FEA = E_FEA / (2 * (1 + NU_FEA))
DB = os.path.join(_ROOT, 'atlas', 'data', 'cell_db.sqlite')
OUT = os.path.join(_ROOT, 'atlas', 'references', 'beam_error_bars.json')

SLIDERS = (0, 2, 4, 6, 8)
RADII = (0.3, 0.4, 0.5)
CELL_H = 5.0
CELL_A = 25.0


def swap_yz(doc):
    """商图 y↔z 轴置换(DB 沿 y 压,frame_fem 沿 z 压)。"""
    import copy
    d = copy.deepcopy(doc)
    for nd in d['nodes']:
        f = nd['frac']
        nd['frac'] = [f[0], f[2], f[1]]
    for e in d['edges']:
        s = e['shift']
        e['shift'] = [s[0], s[2], s[1]]
    return d


def curve_slope(con, sample_name, window_mm=0.10):
    """原始 StaCompre 曲线初始斜率 → E*(MPa)。"""
    row = con.execute(
        "SELECT displacement_json, force_json FROM curves WHERE "
        "sample_name=? AND load_case='StaCompre'",
        (sample_name,)).fetchone()
    if not row:
        return None
    d = np.array(json.loads(row[0]), float)
    f = np.array(json.loads(row[1]), float)
    m = (d > 1e-6) & (d <= window_mm)
    if m.sum() < 5:
        return None
    k = np.polyfit(d[m], f[m], 1)[0]
    if k <= 0:
        return None
    return float(k * CELL_H / CELL_A)


def frame_modulus(topology, slider, radius):
    doc = swap_yz(seed_graph(topology, slider=slider,
                             default_radius_mm=radius))
    r = solve_compression(doc, n=1, strain=0.01, E=E_FEA, G=G_FEA)
    lds = [pe['L'] / (2 * pe['r']) for pe in r['per_elem']]
    return r['E_star'], float(np.median(lds))


def collect_pairs(db_path=DB):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    pairs = []
    for topo in list_topologies():
        for sl in SLIDERS:
            for rr in RADII:
                row = con.execute(
                    "SELECT sample_name FROM structures WHERE topology=? "
                    "AND ABS(slider-?)<1e-6 AND ABS(strut_radius-?)<1e-6 "
                    "AND in_json=1", (topo, float(sl), float(rr))
                ).fetchone()
                if not row:
                    continue
                e_db = curve_slope(con, row['sample_name'])
                if e_db is None or e_db <= 0:
                    continue
                try:
                    e_fr, ld = frame_modulus(topo, sl, rr)
                except Exception:
                    continue
                if e_fr <= 0:
                    continue
                pairs.append({'topology': topo, 'class': classify(topo),
                              'slider': sl, 'radius': rr,
                              'sample': row['sample_name'],
                              'db': e_db, 'frame': e_fr, 'ld': ld})
    con.close()
    return pairs


def _stats(ratios):
    ratios = np.asarray(ratios, float)
    corr = float(np.median(ratios))
    resid = np.abs(ratios / corr - 1)
    return {'n_samples': int(len(ratios)),
            'correction': round(corr, 4),
            'p50_resid': round(float(np.median(resid)), 4),
            'p90_resid': round(float(np.percentile(resid, 90)), 4),
            'raw_ratio_range': [round(float(ratios.min()), 3),
                                round(float(ratios.max()), 3)]}


def fit_error_bars(pairs):
    """分层修正:逐拓扑(库内/近库内插值用)+ 类级兜底(OOD 用)。

    类级 p90 折减后弯曲类 margin-safe ≈ 0 —— 把「弯曲主导 OOD 必须
    Tier-D FEA」从红线措辞变成数学事实,这是特性不是缺陷。"""
    out = {'_meta': {
        'date': '2026-06-12',
        'basis': 'E_s=1010 MPa, nu=0.3(FEA 模板实值);载荷轴 y(轴置换);'
                 '参照=原始 StaCompre 曲线 0-2% 应变窗斜率;'
                 '模型=frame_fem n=1 块(底固/顶压/横向锁,与 FEA 同 BC)',
        'scope': '修正吸收节点刚化+单元理想化;尺寸效应(n=1→bulk)归 '
                 'Size-Effect Corrector;周期 bulk 值另见 beam_homog'
                 '(Lumpe 细长区中位 0.9%)',
        'hierarchy': 'per_topology(p50≈14%)优先;OOD 落 per_class 兜底'
                     '(p90 折减,弯曲类≈0 → 强制 Tier-D)',
        'source_type': 'internal_computed',
    }, 'per_topology': {}, 'per_class': {}}
    bytopo = {}
    for p in pairs:
        bytopo.setdefault(p['topology'], []).append(p)
    volatile = []
    for topo, sub in sorted(bytopo.items()):
        s = _stats([p['db'] / p['frame'] for p in sub])
        s['class'] = sub[0]['class']
        s['ld_range'] = [round(float(min(p['ld'] for p in sub)), 2),
                         round(float(max(p['ld'] for p in sub)), 2)]
        out['per_topology'][topo] = s
        if s['p90_resid'] > 1.0:
            volatile.append(topo)
    for cls in ('stretch', 'bending', 'hybrid'):
        sub = [p for p in pairs if p['class'] == cls]
        if sub:
            s = _stats([p['db'] / p['frame'] for p in sub])
            s['ld_range'] = [round(float(min(p['ld'] for p in sub)), 2),
                             round(float(max(p['ld'] for p in sub)), 2)]
            out['per_class'][cls] = s
    out['_meta']['volatile_topologies'] = volatile
    return out


def certify(doc, error_bars=None, n=1, class_hint=None):
    """Tier-B 认证(n=1 平台压缩口径,可与 DB/试件直接对比)。

    分层:库内拓扑名 → 逐拓扑修正;OOD → 类级兜底(class_hint 或
    Maxwell 倾向推断,p90 折减;弯曲类 margin-safe≈0 → 实质强制
    Tier-D)。l/d<2 标定域外拒绝。"""
    if error_bars is None:
        with open(OUT, encoding='utf-8') as f:
            error_bars = json.load(f)
    r = solve_compression(swap_yz(doc), n=n, strain=0.01,
                          E=E_FEA, G=G_FEA)
    lds = [pe['L'] / (2 * pe['r']) for pe in r['per_elem']]
    ld = float(np.median(lds))

    name = doc.get('name', '')
    caveats = []
    per_topo = error_bars.get('per_topology', {})
    if name in per_topo:
        bars = per_topo[name]
        level = f'per_topology[{name}]'
        if name in error_bars['_meta'].get('volatile_topologies', []):
            caveats.append(f'{name} 为形变敏感族(类内 p90>100%),'
                           '修正可信度降级')
    else:
        from atlas.geometry import list_topologies
        if class_hint:
            cls = class_hint
        elif name in list_topologies():
            cls = classify(name)
        else:
            M = len(doc['edges']) - 3 * len(doc['nodes']) + 6
            cls = 'stretch' if M >= 0 else 'bending'
            caveats.append(f'OOD 拓扑,类别由 Maxwell 倾向推断(M={M},'
                           '必要非充分)')
        bars = error_bars.get('per_class', {}).get(cls)
        level = f'per_class[{cls}](OOD 兜底)'
        if bars is None:
            return {'certified': False,
                    'reason': f'类 {cls} 无标定', 'E_frame': r['E_star']}

    # 标定域检查:l/d 须落在所用层级的标定覆盖域内(±10% 容差)
    lo, hi = bars.get('ld_range', [2.0, 12.0])
    if not (0.9 * lo <= ld <= 1.1 * hi):
        return {'certified': False,
                'reason': f'中位 l/d={ld:.2f} 越出 {level} 标定域 '
                          f'[{lo},{hi}](拒绝认证)',
                'E_frame': r['E_star']}

    e_corr = r['E_star'] * bars['correction']
    deflation = max(0.0, 1 - bars['p90_resid'])
    if deflation <= 0.05:
        caveats.append('p90 残差折减后 margin-safe≈0:'
                       '本证据不足以支撑 margin,须 Tier-D FEA')
    return {'certified': True,
            'E_y_calibrated': round(e_corr, 4),
            'E_y_margin_safe': round(e_corr * deflation, 4),
            'deflation': round(deflation, 4),
            'calibration_level': level,
            'ld_median': round(ld, 2),
            'caveats': caveats,
            'bc': 'n=1 平台压缩(与 DB 同口径);bulk 周期值另用 beam_homog',
            'source_type': 'beam_fem_calibrated',
            'source': 'frame_fem(n=1) × DB 原始曲线标定'
                      '(atlas/references/beam_error_bars.json)'}


if __name__ == '__main__':
    pairs = collect_pairs()
    bars = fit_error_bars(pairs)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(bars, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'对照样本 {len(pairs)} 组 → {OUT}')
    all_resid = []
    for t, b in bars['per_topology'].items():
        all_resid.append(b['p50_resid'])
    print(f"逐拓扑修正:{len(bars['per_topology'])} 拓扑,"
          f"类内 p50 残差中位 {np.median(all_resid):.1%};"
          f"形变敏感族 {bars['_meta']['volatile_topologies']}")
    for cls, b in bars['per_class'].items():
        defl = max(0.0, 1 - b['p90_resid'])
        print(f"  类级兜底 {cls:<8} n={b['n_samples']:>3} "
              f"corr={b['correction']:.2f} p90={b['p90_resid']:.1%} "
              f"→ OOD 折减系数 {defl:.2f}"
              + ('(margin 不可用,强制 Tier-D)' if defl <= 0.05 else ''))
