"""frame FEM 锚点回归 + 生成式搜索冒烟(P2-1/P2-2 预演)。"""
import json
import os

import numpy as np
import pytest

from atlas.mechanics import solve_compression
from atlas.schema import SEEDS_DIR


def seed(t):
    with open(os.path.join(SEEDS_DIR, f'{t}.json'), encoding='utf-8') as f:
        return json.load(f)


def test_column_array_matches_analytic():
    """解析锚点:纯竖柱阵 E* = E·A/a²(轴压精确解);边界共享权校验。"""
    cubic = seed('Cubic')
    doc = dict(cubic)
    doc['edges'] = [e for e in cubic['edges'] if e['shift'] == [0, 0, 1]]
    r = solve_compression(doc, n=2, strain=0.05)
    exact = 1700.0 * np.pi * 0.5 ** 2 / 25.0
    assert abs(r['E_star'] / exact - 1) < 1e-6


def test_horizontal_beams_carry_nothing_axially():
    """Cubic 全图 E* == 竖柱阵(横梁不承轴压)。"""
    full = solve_compression(seed('Cubic'), n=2)
    exact = 1700.0 * np.pi * 0.5 ** 2 / 25.0
    assert abs(full['E_star'] / exact - 1) < 1e-3


def test_bend_fraction_separates_classes():
    """拉压主导(Octet)弯曲能量占比应显著低于弯曲主导(Kelvin)。"""
    oc = solve_compression(seed('Octet_truss'), n=2)
    ke = solve_compression(seed('Kelvin'), n=2)
    bf = lambda r: float(np.mean([e['bend_frac'] for e in r['per_elem']]))
    assert bf(oc) < bf(ke) - 0.15
    assert 'screening' in oc['caveat']


def test_gen_search_smoke():
    from atlas.mechanics.gen_search import search
    r = search(bases=('BCC',), per_base=4, keep=1, seed=7)
    assert r['stats']['proposed'] == 4
    if r['top']:
        t = r['top'][0]
        assert t['doc']['lineage']['tier'] == 'tier2'
        assert t['score'] > 0 and len(t['wl_hash']) == 64
