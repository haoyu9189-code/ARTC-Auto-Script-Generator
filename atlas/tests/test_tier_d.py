"""P3-A 单测:能量注入幂等/作业生成/结果桥/能量门语义/R7 白名单。"""
import json
import os

import numpy as np
import pytest

from atlas.evaluator.core import MARGIN_EVIDENCE_WHITELIST, validate_trace
from atlas.mechanics.tier_d import (CHAMPIONS, ENERGY_GATE_THRESHOLD,
                                    generate_tier_d_jobs,
                                    inject_energy_extraction,
                                    load_champion_docs,
                                    parse_energy_data,
                                    parse_feature_data,
                                    results_to_checks)

ANCHOR = ("    session.writeXYReport(fileName='feature_data.txt', "
          "xyData=(xy_combined, ), appendMode=ON)")


# ---- 注入器 ----

def test_inject_idempotent_and_fail_loudly():
    fake = "try:\n    foo()\n" + ANCHOR + "\n    odb.close()\n"
    once = inject_energy_extraction(fake)
    assert 'ATLAS-P3A-ENERGY-GATE' in once
    assert once.index('ATLAS-P3A-ENERGY-GATE') > once.index('writeXYReport')
    assert once.index('ATLAS-P3A-ENERGY-GATE') < once.index('odb.close')
    assert inject_energy_extraction(once) == once          # 幂等
    with pytest.raises(ValueError):                        # 锚点缺失必炸
        inject_energy_extraction('print(1)\n')


# ---- 作业生成(真管线,单冠军冒烟) ----

def test_generate_champion_job(tmp_path):
    jobs = generate_tier_d_jobs(str(tmp_path), names=('dual_column_web',))
    assert len(jobs) == 1
    d = tmp_path / 'dual_column_web'
    files = os.listdir(d)
    assert any(f.endswith('_preprocess.py') for f in files)
    assert any(f.endswith('.pbs') for f in files)
    post = [f for f in files if f.endswith('_postprocess.py')]
    assert len(post) == 1
    txt = (d / post[0]).read_text(encoding='utf-8')
    assert 'ATLAS-P3A-ENERGY-GATE' in txt
    meta = json.loads((d / 'job_meta.json').read_text(encoding='utf-8'))
    assert meta['energy_gate']['threshold'] == ENERGY_GATE_THRESHOLD
    assert any('radii_groups' in c for c in meta['caveats'])  # 单半径限定
    assert (tmp_path / 'README.md').exists()


def test_champions_all_loadable():
    docs = load_champion_docs(CHAMPIONS)
    assert [n for n, _, _ in docs] == list(CHAMPIONS)
    for _, doc, _ in docs:
        assert doc['default_radius_mm'] > 0
        assert doc['cell']['size_mm'] > 0


# ---- 结果桥 ----

def _write_job(tmp_path, slope=100.0, ratio=0.01, energy_status='ok',
               n_pts=30):
    meta = {'name': 'champ', 'analysis_type': 'StaCompre',
            'lattice_array': [1, 1, 1], 'radius_mm': 0.4,
            'cell_size_mm': 5.0, 'caveats': ['单半径限定'],
            'energy_gate': {'threshold': 0.05}}
    (tmp_path / 'job_meta.json').write_text(
        json.dumps(meta), encoding='utf-8')
    d = np.linspace(0, 0.2, n_pts)
    f = slope * d
    lines = ['champ_job', 'status: COMPLETED', 'density: 0.3',
             'strain_length: 5.0', 'stress_area: 25.0',
             'RIGIDPLATE-2 RIGIDPLATE-1']
    lines += [f'  {di:.6f}  {fi:.6f}' for di, fi in zip(d, f)]
    (tmp_path / 'feature_data.txt').write_text(
        '\n'.join(lines), encoding='utf-8')
    if energy_status == 'ok':
        e = ['status: ok', 'time allke allie']
        ie = np.linspace(0, 10, n_pts)
        ke = ratio * ie
        e += [f'{t:.4f} {k:.6f} {i:.6f}'
              for t, k, i in zip(d, ke, ie)]
        (tmp_path / 'energy_data.txt').write_text(
            '\n'.join(e), encoding='utf-8')
    elif energy_status == 'no_history':
        (tmp_path / 'energy_data.txt').write_text(
            'status: no_energy_history', encoding='utf-8')
    # energy_status == 'missing':不写文件


def test_parse_and_stiffness_convention(tmp_path):
    _write_job(tmp_path, slope=100.0)
    feat = parse_feature_data(str(tmp_path / 'feature_data.txt'))
    assert feat['header']['status'] == 'COMPLETED'
    assert len(feat['disp']) == 30
    checks = results_to_checks(str(tmp_path),
                               {'margin_metric': 'comp_stiffness'})
    stiff = next(c for c in checks
                 if c['tool'] == 'abaqus.sta_compre.stiffness')
    # E* = k·H/A = 100·5/25 = 20 MPa(与 calibrate.curve_slope 同口径)
    assert stiff['value'] == pytest.approx(20.0, rel=1e-6)
    assert stiff['source_type'] == 'abaqus_fea'
    assert stiff['margin_eligible'] is True


def test_comp_ea_trapz_and_metric_gating(tmp_path):
    _write_job(tmp_path, slope=100.0)
    checks = results_to_checks(str(tmp_path), {'margin_metric': 'comp_EA'})
    ea = next(c for c in checks if c['tool'].endswith('comp_EA'))
    # ∫kδ·dδ = 100·0.2²/2 = 2.0 mJ
    assert ea['value'] == pytest.approx(2.0, rel=1e-3)
    assert ea['margin_eligible'] is True
    stiff = next(c for c in checks if c['tool'].endswith('stiffness'))
    assert stiff['margin_eligible'] is False   # metric 不匹配不抢 margin


def test_energy_gate_fail_cancels_margin(tmp_path):
    _write_job(tmp_path, ratio=0.20)           # 20% ≫ 5%
    checks = results_to_checks(str(tmp_path), {'margin_metric': 'comp_EA'})
    gate = next(c for c in checks if c['tool'] == 'abaqus.energy_gate')
    assert gate['pass'] is False
    assert gate['value'] == pytest.approx(0.20, rel=1e-3)
    for c in checks:
        if c['tool'] != 'abaqus.energy_gate':
            assert c['margin_eligible'] is False
            assert any('能量门' in cv for cv in c['caveats'])


def test_no_energy_history_is_informational(tmp_path):
    _write_job(tmp_path, energy_status='no_history')
    checks = results_to_checks(str(tmp_path), {'margin_metric': 'comp_EA'})
    gate = next(c for c in checks if c['tool'] == 'abaqus.energy_gate')
    assert gate['pass'] is None                # Standard 静力:门不适用
    ea = next(c for c in checks if c['tool'].endswith('comp_EA'))
    assert ea['margin_eligible'] is True       # margin 资格保留


def test_energy_missing_downgrades(tmp_path):
    _write_job(tmp_path, energy_status='missing')
    assert parse_energy_data(str(tmp_path / 'energy_data.txt'))[
        'status'] == 'missing'
    checks = results_to_checks(str(tmp_path), {'margin_metric': 'comp_EA'})
    ea = next(c for c in checks if c['tool'].endswith('comp_EA'))
    assert ea['margin_eligible'] is False      # 缺数据 ≠ 不适用


# ---- R7 白名单 + schema ----

def test_abaqus_fea_whitelisted_and_schema_valid(tmp_path):
    assert 'abaqus_fea' in MARGIN_EVIDENCE_WHITELIST
    _write_job(tmp_path)
    checks = results_to_checks(str(tmp_path), {'margin_metric': 'comp_EA'})
    trace = {'candidate_id': 'champ', 'tier': '2', 'checks': checks,
             'verdict': 'PASS'}
    validate_trace(trace)                      # enum 含 abaqus_fea,不抛
