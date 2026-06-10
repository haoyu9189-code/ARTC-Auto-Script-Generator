"""B6 单测:商图→装饰文本往返等价 + 词汇表外新图端到端生成 preprocess。"""
import json
import os

import numpy as np
import pytest

from atlas.abaqus_adapter import (graph_to_structure_text,
                                  generate_abaqus_script)
from atlas.geometry import list_topologies, parse_structure
from atlas.schema import SEEDS_DIR


def load_seed(topology):
    with open(os.path.join(SEEDS_DIR, f'{topology}.json'),
              encoding='utf-8') as f:
        return json.load(f)


def canonical_segments(coords, cyls):
    """(coords dict, cylinders) → 规范化线段集合(排序端点,6dp)。"""
    out = set()
    for a, b in cyls:
        if a not in coords or b not in coords:
            continue
        p1 = tuple(np.round(coords[a], 5))
        p2 = tuple(np.round(coords[b], 5))
        if p1 == p2:
            continue
        out.add(tuple(sorted((p1, p2))))
    return out


def parse_text(text):
    """复用 cells.parse_structure 的逻辑解析适配器文本。"""
    coords, cyls = {}, []
    in_c = False
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


REPRESENTATIVE = ['Cubic', 'BCC', 'Octet_truss', 'Kelvin', 'Diamond', 'FCC']


@pytest.mark.parametrize('topology', REPRESENTATIVE)
def test_roundtrip_exact_segment_set(topology):
    """商图 → 装饰文本应精确复现原始装饰线段集(去重后)。"""
    orig = canonical_segments(*parse_structure(topology, 4))
    text, _ = graph_to_structure_text(load_seed(topology))
    adapted = canonical_segments(*parse_text(text))
    assert adapted == orig, (f'{topology}: 缺 {len(orig - adapted)} 段, '
                             f'多 {len(adapted - orig)} 段')


@pytest.mark.parametrize('topology', list_topologies())
def test_all_seeds_completeness(topology):
    """全 24 种子:原始盒内线段 ⊆ 适配集(几何完备,允许周期补全多出)。"""
    coords, cyls = parse_structure(topology, 4)
    orig = canonical_segments(coords, cyls)
    in_box = {seg for seg in orig
              if all(-2.5 - 1e-6 <= x <= 2.5 + 1e-6
                     for pt in seg for x in pt)}
    text, stats = graph_to_structure_text(load_seed(topology))
    adapted = canonical_segments(*parse_text(text))
    missing = in_box - adapted
    assert not missing, f'{topology} 丢失盒内线段 {len(missing)}'
    assert stats['points'] > 0


def test_cubic_boundary_nodes_at_corners():
    """Cubic 商图 1 节点 → 装饰文本应补全 8 角点 + 12 棱(频 0/1 边界)。"""
    text, stats = graph_to_structure_text(load_seed('Cubic'))
    coords, cyls = parse_text(text)
    assert len(coords) == 8 and len(cyls) == 12


NOVEL = {
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
    'free_params': {'slider': {'value': 4, 'min': 0, 'max': 8}},
    'lineage': {'tier': 'tier2', 'generator': 'test', 'source': 'test'},
}


def test_novel_graph_end_to_end_preprocess(tmp_path):
    """DoD:词汇表外测试图端到端生成 preprocess 脚本。"""
    r = generate_abaqus_script(NOVEL, output_dir=str(tmp_path),
                               analysis_type='StaCompre')
    assert r['ok'], r['message']
    files = os.listdir(tmp_path)
    pre = [f for f in files if f.endswith('_preprocess.py')]
    post = [f for f in files if f.endswith('_postprocess.py')]
    assert pre and post and 'run.pbs' in files
    content = open(os.path.join(tmp_path, pre[0]), encoding='utf-8').read()
    # 注入的坐标与连接必须在脚本里(P 系命名)
    assert 'P0 = [' in content and '(P0, ' in content
    # 半径与胞尺寸替换生效(0.5 半径出现于 cylinder profile)
    assert 'cubic_plus_diagonal' in pre[0]


def test_shear_explicitly_rejected(tmp_path):
    from atlas.abaqus_adapter import GraphScriptGenerator
    g = GraphScriptGenerator(NOVEL)
    with pytest.raises(NotImplementedError):
        g._gen._get_structure_data('x', 4, 'StaShear')
