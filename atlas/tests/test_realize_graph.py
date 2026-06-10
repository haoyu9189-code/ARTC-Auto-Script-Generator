"""B4 单测:C9 实现器 —— 24 种子全水密、新图实现、失败显式入 trace。"""
import json
import os

import pytest

from atlas.geometry import list_topologies
from atlas.geometry.cells import CellMesh
from atlas.geometry.realize_graph import realize_graph, RealizeResult
from atlas.schema import SEEDS_DIR


def load_seed(topology):
    with open(os.path.join(SEEDS_DIR, f'{topology}.json'),
              encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.parametrize('topology', list_topologies())
def test_all_seeds_realize_watertight(topology):
    r = realize_graph(load_seed(topology))
    assert r.ok, f'{topology}: {r.reason}'
    assert isinstance(r.mesh, CellMesh)  # 与 A1 同栈
    assert r.mesh.is_watertight
    assert r.stats['volume_mm3'] > 0


def test_quotient_per_cell_volume_is_true_density():
    """商图单胞体积 = 真实每胞材料量(装饰胞边界杆共享导致偏大)。

    Cubic 商图 = 1 节点 + 3 杆(轴向):体积 ≈ 3·πr²·a + 球贡献
    ≈ 11.8 + 0.5,显著小于装饰胞的 43.7(12 杆全计)。
    """
    r = realize_graph(load_seed('Cubic'))
    assert 10.5 < r.stats['volume_mm3'] < 12.8
    # 平铺一致性:n=2 体积 ≈ 8×单胞(允许节点接触熔合的小亏)
    r2 = realize_graph(load_seed('Cubic'), n=2)
    assert r2.ok
    ratio = r2.stats['volume_mm3'] / (8 * r.stats['volume_mm3'])
    assert 0.90 < ratio <= 1.001


def test_novel_graph_realizes():
    """词汇表外新图(立方 + 体对角杆)——Tier-2 能力的直接验证。"""
    doc = {
        'schema': 'atlas-cell-graph/1.0', 'name': 'cubic_plus_diagonal',
        'cell': {'size_mm': 5.0},
        'nodes': [{'id': 'A', 'frac': [0.0, 0.0, 0.0]},
                  {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
        'edges': [{'n1': 'A', 'n2': 'A', 'shift': [1, 0, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 1, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 0, 1]},
                  {'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
                  {'n1': 'B', 'n2': 'A', 'shift': [1, 1, 1]}],
        'default_radius_mm': 0.5,
        'free_params': {},
        'lineage': {'tier': 'tier2', 'generator': 'test', 'source': 'test'},
    }
    # 先过硬门,再实现(标准 Tier-2 流程)
    from atlas.gates import run_gates
    g = run_gates(doc)
    assert g['passed'], g['hard_failures']
    r = realize_graph(doc)
    assert r.ok and r.mesh.is_watertight
    r3 = realize_graph(doc, n=3)
    assert r3.ok


def test_failure_is_trace_not_exception():
    """失败显式入 trace(防搜索偏置),不抛异常。"""
    bad = {'schema': 'atlas-cell-graph/1.0'}  # 缺字段
    r = realize_graph(bad)
    assert isinstance(r, RealizeResult)
    assert not r.ok and 'schema' in r.reason
    tr = r.to_trace()
    assert tr['gate'] == 'C9_realize' and tr['pass'] is False
    assert tr['source']


def test_per_edge_radius_and_override():
    doc = load_seed('BCC')
    r_thick = realize_graph(doc, radius_override=0.55)
    r_thin = realize_graph(doc, radius_override=0.30)
    assert r_thick.ok and r_thin.ok
    assert r_thick.stats['volume_mm3'] > r_thin.stats['volume_mm3'] * 2
