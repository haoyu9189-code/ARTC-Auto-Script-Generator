"""B3 单测:C1–C8 硬门 —— 24 种子全过,劣化反例全被杀,毫秒级。"""
import copy
import json
import os
import time

import pytest

from atlas.geometry import list_topologies
from atlas.gates import run_gates
from atlas.gates.gates import _hnf_det3
from atlas.schema import SEEDS_DIR


def load_seed(topology):
    with open(os.path.join(SEEDS_DIR, f'{topology}.json'),
              encoding='utf-8') as f:
        return json.load(f)


def minimal_graph(**over):
    doc = {
        'schema': 'atlas-cell-graph/1.0', 'name': 'T',
        'cell': {'size_mm': 5.0},
        'nodes': [{'id': 'N0', 'frac': [0.25, 0.25, 0.25]}],
        'edges': [{'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
                  {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]},
                  {'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]}],
        'default_radius_mm': 0.5,
        'free_params': {'radius_mm': {'value': 0.5, 'min': 0.25,
                                      'max': 0.55}},
        'lineage': {'tier': 'tier2', 'generator': 'test', 'source': 'test'},
    }
    doc.update(over)
    return doc


# ---- 24 种子全过 ----

@pytest.mark.parametrize('topology', list_topologies())
def test_all_seeds_pass_gates(topology):
    r = run_gates(load_seed(topology), process='MJF')
    assert r['passed'], (f'{topology} 硬门失败: {r["hard_failures"]}; '
                         f'{ {k: g["reason"] for k, g in r["gates"].items() if not g["pass"]} }')
    # C3 双轨一致必须成立
    assert r['gates']['C3']['value']['dual_track_consistent']


def test_all_seeds_gate_speed():
    """毫秒级:24 种子全套门总耗时 < 3 s(平均 <125 ms/胞)。"""
    docs = [load_seed(ct) for ct in list_topologies()]
    t0 = time.perf_counter()
    for d in docs:
        run_gates(d)
    dt = time.perf_counter() - t0
    assert dt < 3.0, f'24 种子全门 {dt:.2f}s 超预算'


# ---- C3:互穿网反例(勘误后的正确条件) ----

def test_c3_kills_interpenetrating_double_net():
    """单节点三自环 shift=(2,0,0),(0,1,0),(0,0,1):rank=3 但格指数 2
    → 两套互穿网。rank-3 旧条件会放行,Smith/HNF 条件必须杀。"""
    doc = minimal_graph(edges=[
        {'n1': 'N0', 'n2': 'N0', 'shift': [2, 0, 0]},
        {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]},
        {'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]}])
    r = run_gates(doc)
    assert not r['passed'] and 'C3' in r['hard_failures']
    assert r['gates']['C3']['value']['cycle_lattice_index'] == 2
    # 双轨:3³ 超胞也应检出多分量,且与 SNF 一致
    assert r['gates']['C3']['value']['dual_track_consistent']


def test_c3_kills_disconnected_quotient():
    doc = minimal_graph(
        nodes=[{'id': 'N0', 'frac': [0.2, 0.2, 0.2]},
               {'id': 'N1', 'frac': [0.7, 0.7, 0.7]}],
        edges=[{'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]},
               {'n1': 'N1', 'n2': 'N1', 'shift': [1, 0, 0]}])
    r = run_gates(doc)
    assert not r['passed'] and 'C3' in r['hard_failures']
    assert not r['gates']['C3']['value']['quotient_connected']


def test_c3_kills_planar_net():
    """只有 xy 向圈 → 格 rank 2(层状不连通 z)。"""
    doc = minimal_graph(edges=[
        {'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
        {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]}])
    r = run_gates(doc)
    assert not r['passed'] and 'C3' in r['hard_failures']
    assert r['gates']['C3']['value']['cycle_lattice_index'] == 0


def test_hnf_det3_known_values():
    assert _hnf_det3([(1, 0, 0), (0, 1, 0), (0, 0, 1)]) == 1
    assert _hnf_det3([(2, 0, 0), (0, 1, 0), (0, 0, 1)]) == 2
    assert _hnf_det3([(1, 1, 0), (0, 1, 1), (1, 0, 1)]) == 2  # fcc 类指数 2
    assert _hnf_det3([(1, 0, 0), (0, 1, 0)]) == 0
    assert _hnf_det3([(1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 0, 0)]) == 1


# ---- C2:节点碰撞 ----

def test_c2_kills_duplicate_node_and_flags_overlap():
    # 0.1mm < 0.5r=0.25mm:疑似未归并重复节点 → 硬判死
    doc = minimal_graph(
        nodes=[{'id': 'N0', 'frac': [0.25, 0.25, 0.25]},
               {'id': 'N1', 'frac': [0.27, 0.25, 0.25]}],
        edges=[{'n1': 'N0', 'n2': 'N1', 'shift': [0, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]}])
    r = run_gates(doc)
    assert 'C2' in r['hard_failures']
    # 0.6mm ∈ (0.5r, 2r):球互吞,合法但打 flag(实测种子有此形态)
    doc2 = minimal_graph(
        nodes=[{'id': 'N0', 'frac': [0.25, 0.25, 0.25]},
               {'id': 'N1', 'frac': [0.37, 0.25, 0.25]}],
        edges=[{'n1': 'N0', 'n2': 'N1', 'shift': [0, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]}])
    r2 = run_gates(doc2)
    assert r2['gates']['C2']['pass']
    assert any('互吞' in f for f in r2['gates']['C2']['flags'])


# ---- C5:密度可解性 ----

def test_c5_kills_unsolvable_density():
    # 三自环立方,目标密度 0.9 需 r≈3.0mm,越出 free_params 上限
    r = run_gates(minimal_graph(), rho_target=0.9)
    assert 'C5' in r['hard_failures']
    r2 = run_gates(minimal_graph(), rho_target=0.05)
    assert r2['gates']['C5']['pass']


# ---- C7:图级 DfAM ----

def test_c7_kills_thin_strut():
    doc = minimal_graph(default_radius_mm=0.3)  # d=0.6 < MJF 0.8
    r = run_gates(doc, process='MJF')
    assert 'C7' in r['hard_failures']


def test_c7_narrow_gap_flagged_not_killed():
    """净距危险带只打 flag(实测校正:真实种子内部杆距天然 <1mm,
    排粉权威裁决在 B1 网格级);杆径不足才硬判。"""
    doc = minimal_graph(
        nodes=[{'id': 'N0', 'frac': [0.25, 0.25, 0.25]},
               {'id': 'N1', 'frac': [0.55, 0.25, 0.25]}],  # 中心距1.5,净距0.5
        edges=[{'n1': 'N0', 'n2': 'N0', 'shift': [0, 0, 1]},
               {'n1': 'N1', 'n2': 'N1', 'shift': [0, 0, 1]},
               {'n1': 'N0', 'n2': 'N1', 'shift': [0, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]},
               {'n1': 'N0', 'n2': 'N0', 'shift': [0, 1, 0]}])
    r = run_gates(doc, process='MJF')
    assert r['gates']['C7']['pass']
    assert r['gates']['C7']['value']['n_narrow_gaps'] >= 1
    assert any('B1' in f for f in r['gates']['C7']['flags'])


def test_c7_contact_is_not_a_gap_violation():
    """贴合/交叉(gap≤0)= 熔合,不进危险带(物理正确性)。"""
    doc = load_seed('FBCCXYZ')  # 面对角线交叉的种子
    r = run_gates(doc)
    assert r['gates']['C7']['pass']
    # C6 信息门应报告贴合对
    assert r['gates']['C6']['value']['contact_pairs'] > 0


# ---- C4:信息门红线 ----

def test_c4_tendency_only_and_isolated_node_kill():
    r = run_gates(load_seed('BCC'))
    c4 = r['gates']['C4']
    assert not c4['hard']  # 信息门
    assert c4['value']['tendency'] in ('stretch-leaning', 'bending-leaning')
    assert '倾向' in c4['value']['caveat']
    doc = minimal_graph(
        nodes=[{'id': 'N0', 'frac': [0.25, 0.25, 0.25]},
               {'id': 'N9', 'frac': [0.75, 0.75, 0.75]}])  # N9 孤立
    r2 = run_gates(doc)
    assert 'C4' in r2['hard_failures']


# ---- C1 / C8 ----

def test_c1_kills_bad_reference_and_duplicate():
    doc = minimal_graph()
    doc['edges'][0]['n2'] = 'GHOST'
    assert not run_gates(doc)['passed']
    doc2 = minimal_graph()
    doc2['edges'].append(copy.deepcopy(doc2['edges'][0]))
    assert not run_gates(doc2)['passed']


def test_c8_kills_oversized():
    doc = minimal_graph()
    doc['nodes'] = [{'id': f'N{i}', 'frac': [(i % 97) / 97.0,
                                             (i % 89) / 89.0,
                                             (i % 83) / 83.0]}
                    for i in range(501)]
    doc['edges'] = [{'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]}]
    r = run_gates(doc)
    assert 'C8' in r.get('hard_failures', []) or not r['passed']
