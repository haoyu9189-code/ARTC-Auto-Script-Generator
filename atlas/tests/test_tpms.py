"""B2 单测:TPMS 5 族 × 2 变体水密、定标精度、解析锚点、3×3×3 计时。"""
import json
import os
import time

import pytest

from atlas.geometry.tpms import (generate_tpms, generate_tpms_at_density,
                                 calibrate_density, from_implicit,
                                 TPMS_TYPES, VARIANTS)

TABLE_PATH = os.path.join(os.path.dirname(__file__), '..', 'references',
                          'tpms_density_calibration.json')


@pytest.fixture(scope='module')
def table():
    with open(TABLE_PATH, encoding='utf-8') as f:
        return json.load(f)


def test_calibration_table_archived_and_within_tolerance(table):
    """存档标定表:全部条目 |rel_err| < 2%(DoD),且声明适用域。"""
    assert 'validity_domain' in table['_meta']
    assert len(table['table']) == len(TPMS_TYPES) * len(VARIANTS) == 10
    for key, rows in table['table'].items():
        assert rows, f'{key} 空表'
        for r in rows:
            assert 'error' not in r, f'{key}@{r["rho_target"]}: {r}'
            assert abs(r['rel_err']) < 0.02, \
                f'{key}@{r["rho_target"]} 定标误差 {r["rel_err"]:.2%}'


@pytest.mark.parametrize('tpms_type', TPMS_TYPES)
@pytest.mark.parametrize('variant', VARIANTS)
def test_all_families_watertight_at_archived_t(table, tpms_type, variant):
    """用存档 t 重建 @ρ̄=0.3:水密 + 密度复现(对照存档=转换回归)。"""
    rows = table['table'][f'{tpms_type}_{variant}']
    row = next(r for r in rows if r['rho_target'] == 0.3)
    cm = generate_tpms(tpms_type, variant, row['t'])
    assert cm.is_watertight, f'{tpms_type}_{variant} 非水密'
    rho = cm.volume / 125.0
    assert abs(rho - row['rho_achieved']) < 0.005, '与存档标定值漂移'
    assert abs(rho - 0.3) / 0.3 < 0.02


def test_analytic_anchor_balanced_tpms_bisect_space():
    """解析锚:gyroid/P/D skeletal t=0 精确二分空间 → ρ̄=0.5。"""
    for tt in ('gyroid', 'schwarz_p', 'diamond'):
        cm = generate_tpms(tt, 'skeletal', 0.0)
        assert abs(cm.volume / 125.0 - 0.5) < 0.01, f'{tt} 锚点偏离'


def test_density_pipeline_end_to_end():
    cm = generate_tpms_at_density('gyroid', 'sheet', 0.30)
    assert cm.is_watertight
    assert abs(cm.rho_achieved - 0.30) / 0.30 < 0.02
    assert cm.topology == 'gyroid_sheet'


def test_block_3x3x3_under_5s(table):
    row = next(r for r in table['table']['gyroid_sheet']
               if r['rho_target'] == 0.3)
    t0 = time.perf_counter()
    cm = generate_tpms('gyroid', 'sheet', row['t'], n=3, edge_length=5 / 24)
    dt = time.perf_counter() - t0
    assert dt < 5.0, f'3x3x3 用时 {dt:.2f}s 超预算'
    assert cm.is_watertight


def test_sheet_low_density_rejected():
    with pytest.raises(ValueError, match='rho>=0.15'):
        calibrate_density('gyroid', 'sheet', 0.10)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        generate_tpms('not_a_tpms', 'sheet', 0.3)
    with pytest.raises(ValueError):
        generate_tpms('gyroid', 'not_a_variant', 0.3)


def test_from_implicit_schema_doc():
    doc = {
        'schema': 'atlas-implicit/1.0', 'name': 'g_sheet',
        'family': 'tpms_combo', 'cell': {'size_mm': 5.0},
        'params': {'basis': [{'type': 'gyroid', 'weight': 1.0}],
                   'variant': 'sheet', 'thickness_t': 0.9382},
        'lineage': {'tier': 'tier2', 'generator': 'test', 'source': 'test'},
    }
    cm = from_implicit(doc)
    assert cm.is_watertight
    spino = {
        'schema': 'atlas-implicit/1.0', 'name': 's', 'family': 'spinodoid',
        'cell': {'size_mm': 5.0},
        'params': {'theta1_deg': 30, 'theta2_deg': 30, 'theta3_deg': 15,
                   'rho_rel': 0.35},
        'lineage': {'tier': 'tier2', 'generator': 't', 'source': 't'},
    }
    with pytest.raises(NotImplementedError):
        from_implicit(spino)  # spinodoid 实现器在 Phase 3,不得静默假装
