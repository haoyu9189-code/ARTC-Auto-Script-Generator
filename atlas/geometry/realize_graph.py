"""B4:C9 实现器 —— atlas-cell-graph/1.0 商图 → watertight 网格。

与 A1 同栈(cells._strut_manifold / _union / CellMesh,含 TANGENCY_EPS
球扰动与焊接清理)。任何 LLM 提案的合法商图经此实现,之后才进入
B1 可打印性检查与力学裁判。

失败纪律(防搜索偏置):几何失败不抛异常,返回 RealizeResult(ok=False,
reason=...) 显式入 verification trace —— 静默丢弃失败候选会让上游
搜索误以为该区域为空。

商图实现语义:每胞内容 = 节点球(home 位置)+ 每条边一根杆
(pos(n1) → pos(n2)+shift)。跨界杆伸入邻胞是正确行为 —— 商图按构造
每胞每边恰好一次,n³ 平铺无重复;单胞体积即真实每胞材料量
(与装饰表示不同:装饰胞的边界杆被 2/4 胞共享,体积偏大)。

对称破缺(与 cells.py TANGENCY_EPS 同族):对称杆系的精确重合切线会
产生顶点不全同的零厚度翻盖(成对清理抓不到;实测 CubicRosette 商图,
count=4 奇异边 0.05mm)。每杆施加确定性半径微抖动 RADIUS_JITTER
(≤0.05%,r=0.5 时 ≤0.25µm,远低于打印公差与 FEA 相关性),
通用消除精确对称重合而非逐拓扑打地鼠。
"""
import time

import numpy as np
from manifold3d import Manifold

from atlas.geometry.cells import (CellMesh, TANGENCY_EPS, _strut_manifold,
                                  _union)

# 确定性每杆半径微抖动(对称破缺,见模块注释)
RADIUS_JITTER = 5e-4


class RealizeResult:
    """C9 输出:ok / mesh / reason / stats,直接可入 trace。"""

    def __init__(self, ok, mesh=None, reason=None, stats=None,
                 elapsed_s=None):
        self.ok = bool(ok)
        self.mesh = mesh
        self.reason = reason
        self.stats = dict(stats or {})
        self.elapsed_s = elapsed_s

    def to_trace(self):
        return {'gate': 'C9_realize', 'pass': self.ok,
                'reason': self.reason, 'stats': self.stats,
                'elapsed_s': self.elapsed_s,
                'source': 'atlas.geometry.realize_graph'
                          '(manifold3d,双轨水密判据)'}


def realize_graph(doc, n=1, segments=24, radius_override=None):
    """商图 → CellMesh。几何失败返回 RealizeResult(ok=False)。"""
    t0 = time.perf_counter()

    # 轻量结构检查(C1 的兜底;C9 必须可独立健壮运行)
    try:
        from atlas.schema import validate_graph
        validate_graph(doc)
    except Exception as e:
        return RealizeResult(False, reason=f'schema 不合法: {str(e)[:200]}',
                             elapsed_s=time.perf_counter() - t0)

    a = float(doc['cell']['size_mm'])
    default_r = (float(radius_override) if radius_override
                 else float(doc['default_radius_mm']))
    pos = {nd['id']: np.asarray(nd['frac'], float) * a
           for nd in doc['nodes']}

    parts = []
    n_degenerate = 0
    node_max_r = {nid: default_r for nid in pos}
    for k, e in enumerate(doc['edges']):
        if e['n1'] not in pos or e['n2'] not in pos:
            return RealizeResult(
                False, reason=f"边引用未知节点 ({e['n1']},{e['n2']})",
                elapsed_s=time.perf_counter() - t0)
        r = float(e.get('radius_mm', default_r))
        if radius_override:
            r = float(radius_override)
        r *= 1.0 + RADIUS_JITTER * ((k * 7919) % 13) / 13.0
        p1 = pos[e['n1']]
        p2 = pos[e['n2']] + np.asarray(e['shift'], float) * a
        s = _strut_manifold(p1, p2, r, segments)
        if s is None:
            n_degenerate += 1
            continue
        parts.append(s)
        node_max_r[e['n1']] = max(node_max_r[e['n1']], r)
        node_max_r[e['n2']] = max(node_max_r[e['n2']], r)
    if not parts:
        return RealizeResult(False, reason='无有效杆(全部退化)',
                             stats={'degenerate_edges': n_degenerate},
                             elapsed_s=time.perf_counter() - t0)

    for nid, p in pos.items():
        sph_r = node_max_r[nid] * (1.0 + TANGENCY_EPS)
        parts.append(Manifold.sphere(sph_r, segments)
                     .translate([float(p[0]), float(p[1]), float(p[2])]))

    unit = _union(parts)

    if n > 1:
        tiles = []
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    tiles.append(unit.translate([i * a, j * a, k * a]))
        solid = _union(tiles)
        shift = -a * (n - 1) / 2.0
        solid = solid.translate([shift, shift, shift])
    else:
        solid = unit

    cm = CellMesh(solid, doc.get('name', 'graph'), 0, default_r, n, a)
    stats = {'nodes': len(pos), 'edges': len(doc['edges']),
             'degenerate_edges': n_degenerate,
             'faces': len(cm.trimesh.faces),
             'volume_mm3': round(cm.volume, 4),
             'rho_rel': round(cm.volume / (a * n) ** 3, 5)}
    if not cm.is_watertight:
        return RealizeResult(False, mesh=cm,
                             reason='布尔结果非水密(双轨判据)',
                             stats=stats,
                             elapsed_s=time.perf_counter() - t0)
    return RealizeResult(True, mesh=cm, stats=stats,
                         elapsed_s=round(time.perf_counter() - t0, 4))
