"""P2-1b 单测:目录解析 + pcu 解析锚(协议内建金标准)。"""
import os

import pytest

from atlas.mechanics.lumpe_catalog import (iter_entries, to_quotient_doc,
                                           CATALOG, RHO_REF)
from atlas.mechanics.beam_homog import homogenize

pytestmark = pytest.mark.skipif(
    not os.path.exists(CATALOG),
    reason='Unit_Cell_Catalog.txt 未下载(atlas/data/external/)')


@pytest.fixture(scope='module')
def pcu():
    return next(iter_entries())


def test_parse_first_entry_is_pcu(pcu):
    assert pcu['name'] == 'cub_Z06.0_E1'
    assert pcu['cubic'] and not pcu['star']
    assert len(pcu['nodes']) == 8 and len(pcu['bars']) == 12
    assert abs(pcu['props']['Ex'] - 3.34e-3) < 1e-6
    assert pcu['C'] == (0.33, 0.33, 0.33)


def test_pcu_quotient_and_reference_density(pcu):
    """装饰 8 节点 12 杆 → 商图 1 节点 3 边;目录 ρ̄=1% 约定自洽。"""
    doc = to_quotient_doc(pcu)
    assert len(doc['nodes']) == 1 and len(doc['edges']) == 3
    # Ex = C·ρ̄ ⟹ ρ̄_ref = 3.34e-3/0.33 ≈ 1%
    assert abs(pcu['props']['Ex'] / pcu['C'][0] - RHO_REF) < 2e-4
    from atlas.schema import validate_graph
    validate_graph(doc)


def test_pcu_beam_matches_catalog_within_1pct(pcu):
    doc = to_quotient_doc(pcu)
    r = homogenize(doc, E=1.0, G=1.0 / 2.6, nu=0.3)
    assert r['certified']  # ρ̄=1% 细长区,l/d≥5
    for axis in ('E_x', 'E_y', 'E_z'):
        dev = r['constants'][axis] / pcu['props']['Ex'] - 1
        assert abs(dev) < 0.01, f'{axis} 偏差 {dev:.2%}'


def test_validation_report_archived():
    p = os.path.join(os.path.dirname(CATALOG), '..', '..',
                     'references', 'beam_homog_validation.md')
    text = open(p, encoding='utf-8').read()
    assert '中位' in text and '0.9%' in text and 'ρ̄=1%' in text
