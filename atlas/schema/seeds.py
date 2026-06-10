"""A4:24 种子拓扑 → atlas-cell-graph/1.0 商图规范化转换。

structure_set 的"装饰单胞"(节点 mm 坐标 ±2.5,边界节点在相邻面重复出现,
个别节点越出胞界如 Cuboctahedron_Z 的 F1=[0,3,0],FBCCXYZ 含重复杆)
规范化为 labeled quotient graph:
- 节点:分数坐标 wrap 到 [0,1)^3,位置重合(1e-6)的节点归并(aliases 留痕)
- 边:整数 shift 向量 = o(n2) − o(n1),o(p) = p_frac − wrap(p_frac) ∈ Z³
- 定向规范化(n1≤n2,自环 shift 取字典序正),(n1,n2,shift) 去重
- 零长自环(shift=0 且同节点)剔除并留痕

正确性内检:每条商图边长 ||pos(n2)+shift−pos(n1)||·size 必须等于
原始杆 mm 长度(1e-6),wrap/shift 算错立刻暴露。
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SEEDS_DIR = os.path.join(_HERE, 'seeds')

_MERGE_DECIMALS = 6   # 节点归并容差(分数坐标)
_SNAP = 1e-9          # wrap 前的数值噪声吸收


def _wrap_frac(f):
    """wrap 到 [0,1):先吸收数值噪声再取小数部分。"""
    f = np.round(np.asarray(f, dtype=float), 9)
    w = f - np.floor(f)
    w[np.abs(w - 1.0) < _SNAP] = 0.0
    w[np.abs(w) < _SNAP] = 0.0
    return w


def seed_graph(topology, slider=4, cell_size_mm=5.0, default_radius_mm=0.5):
    """把 structure_set 拓扑转换为 atlas-cell-graph/1.0 文档。"""
    from atlas.geometry import parse_structure
    coords, cyls = parse_structure(topology, slider)

    # 原始 mm → 分数坐标(structure_set 原生胞 ±2.5 → /5 + 0.5)
    frac_raw = {n: np.asarray(c, dtype=float) / 5.0 + 0.5
                for n, c in coords.items()}

    # 节点归并:wrap 后按 round(6) 位置聚类
    pos_to_id = {}
    node_alias = {}
    node_pos = {}
    for name in sorted(frac_raw):
        w = _wrap_frac(frac_raw[name])
        key = tuple(np.round(w, _MERGE_DECIMALS))
        if key not in pos_to_id:
            pos_to_id[key] = None  # 占位,稍后按确定性顺序编号
        node_alias.setdefault(key, []).append(name)
    for i, key in enumerate(sorted(pos_to_id)):
        nid = f'N{i}'
        pos_to_id[key] = nid
        node_pos[nid] = np.asarray(key, dtype=float)

    def node_of(name):
        w = _wrap_frac(frac_raw[name])
        return pos_to_id[tuple(np.round(w, _MERGE_DECIMALS))]

    def offset_of(name):
        f = np.round(frac_raw[name], 9)
        return np.round(f - _wrap_frac(f)).astype(int)

    edges = {}
    notes = []
    n_dropped_zero = 0
    n_dup = 0
    for a, b in cyls:
        if a not in frac_raw or b not in frac_raw:
            notes.append(f'edge ({a},{b}) 引用未知节点,跳过')
            continue
        n1, n2 = node_of(a), node_of(b)
        shift = (offset_of(b) - offset_of(a)).astype(int)
        # 定向规范化
        if (n1 > n2) or (n1 == n2 and tuple(shift) < tuple(-shift)):
            n1, n2 = n2, n1
            shift = -shift
        if n1 == n2 and not shift.any():
            n_dropped_zero += 1
            continue
        key = (n1, n2, tuple(int(s) for s in shift))
        if key in edges:
            n_dup += 1
            continue
        # 内检:商图边长必须复现原始杆长
        raw_len = float(np.linalg.norm(
            (frac_raw[b] - frac_raw[a]) * cell_size_mm))
        q_len = float(np.linalg.norm(
            (node_pos[n2] + shift - node_pos[n1]) * cell_size_mm))
        if abs(raw_len - q_len) > 1e-6:
            raise AssertionError(
                f'{topology} edge ({a},{b}): raw {raw_len} != quotient '
                f'{q_len} — wrap/shift 计算错误')
        edges[key] = {'n1': n1, 'n2': n2,
                      'shift': [int(s) for s in shift]}
    if n_dup:
        notes.append(f'原始杆去重 {n_dup} 条(同 (n1,n2,shift))')
    if n_dropped_zero:
        notes.append(f'剔除零长自环 {n_dropped_zero} 条')

    doc = {
        'schema': 'atlas-cell-graph/1.0',
        'name': topology,
        'cell': {'size_mm': cell_size_mm},
        'nodes': [
            {'id': pos_to_id[key],
             'frac': [float(x) for x in key],
             'aliases': node_alias[key]}
            for key in sorted(pos_to_id)
        ],
        'edges': [edges[k] for k in sorted(edges)],
        'default_radius_mm': default_radius_mm,
        'free_params': {
            'slider': {'value': float(slider), 'min': 0.0, 'max': 8.0,
                       'description': 'structure_set 拓扑变形参数'
                                      '(部分拓扑在 slider=8 改变连通性)'},
            'radius_mm': {'value': default_radius_mm, 'min': 0.25,
                          'max': 0.55,
                          'description': '全局杆半径(DB 覆盖区间)'},
        },
        'lineage': {
            'tier': 'seed',
            'generator': 'atlas.schema.seeds.seed_graph',
            'source': 'ARTC-Auto-Script structure_set.get_crystal_structure'
                      f'(topology={topology}, slider={slider})',
            'parents': [],
            'notes': notes,
        },
    }
    return doc


def export_all(out_dir=SEEDS_DIR, slider=4):
    """生成全部 24 个种子实例文件;返回 {topology: path}。"""
    from atlas.geometry import list_topologies
    from atlas.schema import validate_graph
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for ct in list_topologies():
        doc = seed_graph(ct, slider=slider)
        validate_graph(doc)
        p = os.path.join(out_dir, f'{ct}.json')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        paths[ct] = p
    return paths


if __name__ == '__main__':
    paths = export_all()
    for ct, p in paths.items():
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        print(f'{ct:<25} nodes={len(d["nodes"]):>3} '
              f'edges={len(d["edges"]):>3} notes={d["lineage"]["notes"]}')
