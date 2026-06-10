"""相对密度计算:analytic 一阶估算 + mesh 精确计算(manifold3d 地面真值)。

- analytic:Σ(π r² L)/V_cell,忽略节点重叠(高估)与球节点贡献,
  status='estimate';适合生成期快速预筛。
- mesh:atlas.geometry.generate_cell 实现 watertight 网格后取
  体积/胞体积,status='computed';这是几何地面真值(同一网格栈
  供 Printability Checker 消费)。
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from physics_common import make_result

SRC_ANALYTIC = ('一阶解析 sum(pi r^2 L)/a^3(忽略节点重叠与球节点,'
                '系统性高估)— 内部推导(source_type=inference)')
SRC_MESH = ('manifold3d watertight 布尔体积 / 胞体积,'
            'atlas/geometry/cells.py generate_cell(双轨水密判据)')


def analytic(topology, slider, radius, cell_size=5.0):
    """一阶解析估算(快,毫秒级)。"""
    echo = dict(topology=topology, slider=slider, radius=radius,
                cell_size=cell_size)
    try:
        from atlas.geometry import parse_structure
        coords, cyls = parse_structure(topology, slider)
    except Exception as e:
        return make_result(None, 'needs_input', echo, SRC_ANALYTIC,
                           [f'解析失败: {e}'])
    scale = cell_size / 5.0
    total = 0.0
    for a, b in cyls:
        if a not in coords or b not in coords:
            continue
        d = coords[b] - coords[a]
        L = float((d @ d) ** 0.5) * scale
        total += math.pi * radius ** 2 * L
    rho = total / cell_size ** 3
    return make_result(rho, 'estimate', echo, SRC_ANALYTIC,
                       ['忽略节点重叠,高估;定稿值用 mode=mesh'])


def mesh(topology, slider, radius, cell_size=5.0, segments=24):
    """manifold3d 网格精确值(秒级,几何地面真值)。"""
    echo = dict(topology=topology, slider=slider, radius=radius,
                cell_size=cell_size, segments=segments)
    try:
        from atlas.geometry import generate_cell
        cm = generate_cell(topology, slider=slider, radius=radius,
                           cell_size=cell_size, segments=segments)
    except Exception as e:
        return make_result(None, 'needs_input', echo, SRC_MESH,
                           [f'网格生成失败: {e}'])
    if not cm.is_watertight:
        return make_result(None, 'out_of_domain', echo, SRC_MESH,
                           ['网格非水密,体积不可信'])
    rho = cm.volume / cell_size ** 3
    return make_result(rho, 'computed', echo, SRC_MESH, [])


if __name__ == '__main__':
    import json
    print(json.dumps(analytic('BCC', 4, 0.5), indent=2, ensure_ascii=False))
    print(json.dumps(mesh('BCC', 4, 0.5), indent=2, ensure_ascii=False))
