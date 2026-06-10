"""P2-1c 单测:分层标定工件、认证接口、OOD 兜底与强制 Tier-D。"""
import copy
import json
import os

import pytest

from atlas.mechanics.calibrate import certify, OUT
from atlas.schema import SEEDS_DIR

pytestmark = pytest.mark.skipif(
    not os.path.exists(OUT),
    reason='beam_error_bars.json 未生成(python -m atlas.mechanics.calibrate)')


def seed(t):
    with open(os.path.join(SEEDS_DIR, f'{t}.json'), encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def bars():
    with open(OUT, encoding='utf-8') as f:
        return json.load(f)


def test_artifact_structure(bars):
    assert len(bars['per_topology']) == 24
    assert set(bars['per_class']) == {'stretch', 'bending', 'hybrid'}
    assert 'volatile_topologies' in bars['_meta']
    for t, b in bars['per_topology'].items():
        assert b['n_samples'] >= 3 and b['correction'] > 0
    # 弯曲类 p90 > 95% ⟹ OOD 折减≈0(强制 Tier-D 的数学来源)
    assert bars['per_class']['bending']['p90_resid'] > 0.95


def test_certify_in_db_topology_uses_per_topology(bars):
    r = certify(seed('Octet_truss'), error_bars=bars)
    assert r['certified']
    assert r['calibration_level'] == 'per_topology[Octet_truss]'
    assert r['source_type'] == 'beam_fem_calibrated'
    assert 0 < r['E_y_margin_safe'] < r['E_y_calibrated']


def test_certify_volatile_topology_flagged(bars):
    r = certify(seed('BCC'), error_bars=bars)
    assert r['certified']
    assert any('形变敏感' in c for c in r['caveats'])


def test_certify_ood_stretch_uses_class_fallback(bars):
    doc = {
        'schema': 'atlas-cell-graph/1.0', 'name': 'alien_strut_x',
        'cell': {'size_mm': 5.0},
        'nodes': [{'id': 'A', 'frac': [0.0, 0.0, 0.0]},
                  {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
        'edges': [{'n1': 'A', 'n2': 'A', 'shift': [1, 0, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 1, 0]},
                  {'n1': 'A', 'n2': 'A', 'shift': [0, 0, 1]},
                  {'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
                  {'n1': 'B', 'n2': 'A', 'shift': [1, 1, 1]}],
        'default_radius_mm': 0.4, 'free_params': {},
        'lineage': {'tier': 'tier2', 'generator': 't', 'source': 't'},
    }
    r = certify(doc, error_bars=bars)
    assert r['certified']
    assert 'per_class' in r['calibration_level']
    assert any('Maxwell 倾向推断' in c for c in r['caveats'])
    assert r['deflation'] > 0.2  # stretch 类 OOD 仍可给折减后 margin


def test_certify_ood_bending_forces_tier_d(bars):
    """弯曲类 OOD:折减后 margin-safe≈0 → 实质强制 Tier-D。"""
    doc = copy.deepcopy(seed('Kelvin'))      # M=-6 → bending 推断
    doc['name'] = 'unknown_bending_net'
    r = certify(doc, error_bars=bars)
    assert r['certified']
    assert r['calibration_level'] == 'per_class[bending](OOD 兜底)'
    assert r['E_y_margin_safe'] < 1e-9
    assert any('Tier-D' in c for c in r['caveats'])


def test_ld_below_2_rejected(bars):
    doc = copy.deepcopy(seed('Octet_truss'))
    doc['default_radius_mm'] = 0.95          # l/d ≈ 1.9 < 2
    r = certify(doc, error_bars=bars)
    assert not r['certified'] and 'l/d' in r['reason']


def test_evaluator_accepts_calibrated_and_blocks_zero_margin(bars):
    """R7:beam_fem_calibrated 进白名单;弯曲 OOD 零 margin → FAIL。"""
    from atlas.evaluator import judge
    spec = {'fos_already_applied': True, 'confidence_level': 'screening',
            'margin_metric': 'E_y', 'design_value_with_fos': 30.0}
    base = [
        {'dimension': 'printability', 'tool': 'checks', 'value': 1,
         'pass': True, 'status': 'computed', 'source': 's'},
        {'dimension': 'density', 'tool': 'mesh', 'value': 0.3,
         'pass': True, 'status': 'computed', 'source': 's'},
    ]
    ok = certify(seed('Octet_truss'), error_bars=bars)
    t = judge('c1', '1', base + [
        {'dimension': 'mechanics', 'tool': 'calibrate.certify',
         'value': ok['E_y_margin_safe'], 'pass': True,
         'status': 'computed', 'source': ok['source'],
         'source_type': 'beam_fem_calibrated', 'margin_eligible': True}],
        spec)
    assert t['verdict'] == 'PASS' and t['margin']['ratio'] >= 1.0
    bad = certify({**copy.deepcopy(seed('Kelvin')),
                   'name': 'unknown_bending_net'}, error_bars=bars)
    t2 = judge('c2', '2', base + [
        {'dimension': 'mechanics', 'tool': 'calibrate.certify',
         'value': bad['E_y_margin_safe'], 'pass': True,
         'status': 'computed', 'source': bad['source'],
         'source_type': 'beam_fem_calibrated', 'margin_eligible': True}],
        spec)
    assert t2['verdict'] == 'FAIL'  # margin 0 → 必须升级 Tier-D
