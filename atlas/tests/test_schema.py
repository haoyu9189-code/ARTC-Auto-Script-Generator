"""A4 单测:双轨 schema 校验 + 24 种子商图永久回归。"""
import json
import os

import jsonschema
import pytest

from atlas.geometry import list_topologies
from atlas.schema import (load_schema, validate_graph, validate_implicit,
                          seed_graph, SEEDS_DIR)


def test_schemas_are_valid_jsonschema():
    for which in ('cell-graph', 'implicit'):
        schema = load_schema(which)
        jsonschema.Draft202012Validator.check_schema(schema)


# ---- 24 种子永久回归 ----

@pytest.mark.parametrize('topology', list_topologies())
def test_seed_matches_committed_instance(topology):
    """重生成 == 已提交实例(转换确定性 + 防漂移)。"""
    regenerated = seed_graph(topology, slider=4)
    validate_graph(regenerated)
    path = os.path.join(SEEDS_DIR, f'{topology}.json')
    assert os.path.exists(path), f'缺已提交种子 {path},运行 seeds.py 生成'
    with open(path, encoding='utf-8') as f:
        committed = json.load(f)
    assert regenerated == committed, f'{topology} 转换结果漂移'


def test_known_canonical_anchors():
    """教科书锚点:简单立方商图 1 节点 3 边;BCC 2 节点 8 边。"""
    cubic = seed_graph('Cubic')
    assert len(cubic['nodes']) == 1 and len(cubic['edges']) == 3
    shifts = sorted(tuple(e['shift']) for e in cubic['edges'])
    assert shifts == [(0, 0, 1), (0, 1, 0), (1, 0, 0)]
    bcc = seed_graph('BCC')
    assert len(bcc['nodes']) == 2 and len(bcc['edges']) == 8


def test_seed_invariants():
    """全种子:frac ∈ [0,1)、shift 整数、无重复边、边长>0。"""
    import numpy as np
    for ct in list_topologies():
        doc = seed_graph(ct)
        pos = {n['id']: np.array(n['frac']) for n in doc['nodes']}
        seen = set()
        for n in doc['nodes']:
            assert all(0 <= x < 1 for x in n['frac']), f'{ct} frac 越界'
        for e in doc['edges']:
            key = (e['n1'], e['n2'], tuple(e['shift']))
            assert key not in seen, f'{ct} 重复边 {key}'
            seen.add(key)
            L = np.linalg.norm(pos[e['n2']] + np.array(e['shift'])
                               - pos[e['n1']]) * doc['cell']['size_mm']
            assert L > 1e-6, f'{ct} 零长边 {key}'


def test_dedup_recorded_in_lineage():
    """FBCCXYZ 原始定义含 (O,A)+(A,O) 类重复,去重必须留痕。"""
    doc = seed_graph('FBCCXYZ')
    assert any('去重' in n for n in doc['lineage']['notes'])


# ---- graph schema 拒收非法文档 ----

def _minimal_graph():
    return {
        'schema': 'atlas-cell-graph/1.0', 'name': 'T',
        'cell': {'size_mm': 5.0},
        'nodes': [{'id': 'N0', 'frac': [0.0, 0.0, 0.0]}],
        'edges': [{'n1': 'N0', 'n2': 'N0', 'shift': [1, 0, 0]}],
        'default_radius_mm': 0.5,
        'free_params': {},
        'lineage': {'tier': 'tier2', 'generator': 'g', 'source': 's'},
    }


def test_graph_schema_rejections():
    validate_graph(_minimal_graph())  # 合法基线
    bad = _minimal_graph()
    bad['nodes'][0]['frac'] = [0.0, 0.0, 1.0]  # frac 必须 <1
    with pytest.raises(jsonschema.ValidationError):
        validate_graph(bad)
    bad = _minimal_graph()
    bad['edges'][0]['shift'] = [0.5, 0, 0]  # shift 必须整数
    with pytest.raises(jsonschema.ValidationError):
        validate_graph(bad)
    bad = _minimal_graph()
    del bad['lineage']  # lineage 必填(可审计性)
    with pytest.raises(jsonschema.ValidationError):
        validate_graph(bad)


# ---- implicit schema ----

def test_implicit_examples():
    gyroid = {
        'schema': 'atlas-implicit/1.0', 'name': 'gyroid_sheet',
        'family': 'tpms_combo', 'cell': {'size_mm': 5.0},
        'params': {'basis': [{'type': 'gyroid', 'weight': 1.0}],
                   'variant': 'sheet', 'thickness_t': 0.3},
        'lineage': {'tier': 'tier2', 'generator': 'g', 'source': 's'},
    }
    validate_implicit(gyroid)
    spinodoid = {
        'schema': 'atlas-implicit/1.0', 'name': 'spino_demo',
        'family': 'spinodoid', 'cell': {'size_mm': 5.0},
        'params': {'theta1_deg': 30, 'theta2_deg': 30, 'theta3_deg': 15,
                   'rho_rel': 0.35},
        'lineage': {'tier': 'tier2', 'generator': 'g', 'source': 's'},
    }
    validate_implicit(spinodoid)
    bad = dict(spinodoid, family='magic')  # 未知族
    with pytest.raises(jsonschema.ValidationError):
        validate_implicit(bad)
    bad = json.loads(json.dumps(spinodoid))
    bad['params']['theta1_deg'] = 120  # 锥角越界
    with pytest.raises(jsonschema.ValidationError):
        validate_implicit(bad)
    bad = json.loads(json.dumps(spinodoid))
    del bad['params']['rho_rel']  # 缺关键参数
    with pytest.raises(jsonschema.ValidationError):
        validate_implicit(bad)
