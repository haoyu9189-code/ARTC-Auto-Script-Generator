"""B5 单测:WL 哈希不变性、24 种子零碰撞、查重接口。"""
import copy
import json
import os

from atlas.geometry import list_topologies
from atlas.schema import SEEDS_DIR
from atlas.schema.novelty import wl_hash, NoveltyIndex


def load_seed(topology):
    with open(os.path.join(SEEDS_DIR, f'{topology}.json'),
              encoding='utf-8') as f:
        return json.load(f)


def test_24_seeds_no_collision():
    hashes = {ct: wl_hash(load_seed(ct)) for ct in list_topologies()}
    assert len(set(hashes.values())) == 24, '种子哈希碰撞'


def test_relabel_and_reorder_invariance():
    """改节点名、乱列表顺序、翻转边定向(shift 取负)→ 哈希不变。"""
    doc = load_seed('Octet_truss')
    h0 = wl_hash(doc)
    mod = copy.deepcopy(doc)
    rename = {n['id']: f'X{i}' for i, n in enumerate(reversed(mod['nodes']))}
    for n in mod['nodes']:
        n['id'] = rename[n['id']]
    for i, e in enumerate(mod['edges']):
        e['n1'], e['n2'] = rename[e['n1']], rename[e['n2']]
        if i % 2:  # 翻转一半边的定向
            e['n1'], e['n2'] = e['n2'], e['n1']
            e['shift'] = [-s for s in e['shift']]
    mod['nodes'].sort(key=lambda n: n['id'])
    mod['edges'].reverse()
    assert wl_hash(mod) == h0


def test_radius_not_in_hash_but_geometry_is():
    doc = load_seed('BCC')
    h0 = wl_hash(doc)
    thick = copy.deepcopy(doc)
    thick['default_radius_mm'] = 0.55  # Tier-1.5 自由度,非新拓扑
    assert wl_hash(thick) == h0
    moved = copy.deepcopy(doc)
    moved['nodes'][1]['frac'] = [0.4, 0.5, 0.5]  # 几何变了 = 新结构
    assert wl_hash(moved) != h0


def test_duplicate_detection_interface():
    idx = NoveltyIndex.from_seeds()
    assert len(idx) == 24
    renamed_bcc = copy.deepcopy(load_seed('BCC'))
    for i, n in enumerate(renamed_bcc['nodes']):
        old = n['id']
        n['id'] = f'Q{i}'
        for e in renamed_bcc['edges']:
            if e['n1'] == old:
                e['n1'] = f'Q{i}'
            if e['n2'] == old:
                e['n2'] = f'Q{i}'
    r = idx.check(renamed_bcc)
    assert r['duplicate_of'] == 'BCC'
    novel = {
        'schema': 'atlas-cell-graph/1.0', 'name': 'novel',
        'cell': {'size_mm': 5.0},
        'nodes': [{'id': 'A', 'frac': [0.0, 0.0, 0.0]},
                  {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
        'edges': [{'n1': 'A', 'n2': 'A', 'shift': [1, 0, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 1, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 0, 1]},
                  {'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
                  {'n1': 'B', 'n2': 'A', 'shift': [1, 1, 1]}],
        'default_radius_mm': 0.5, 'free_params': {},
        'lineage': {'tier': 'tier2', 'generator': 't', 'source': 't'},
    }
    r2 = idx.check(novel)
    assert r2['duplicate_of'] is None
    assert len(r2['wl_hash']) == 64
    # novelty 块可直接写回 doc 并过 schema 校验
    from atlas.schema import validate_graph
    novel['novelty'] = r2
    validate_graph(novel)
