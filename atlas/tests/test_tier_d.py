"""P3-A 单测:能量注入幂等/作业生成/结果桥/能量门语义/R7 白名单。"""
import json
import os

import numpy as np
import pytest

from atlas.evaluator.core import MARGIN_EVIDENCE_WHITELIST, validate_trace
from atlas.mechanics.tier_d import (CHAMPIONS, ENERGY_GATE_THRESHOLD,
                                    crush_metrics,
                                    generate_tier_d_jobs,
                                    inject_energy_extraction,
                                    inject_energy_history_request,
                                    load_champion_docs,
                                    parse_energy_data,
                                    parse_feature_data,
                                    results_to_checks,
                                    results_to_checks_crush)

ANCHOR = ("    session.writeXYReport(fileName='feature_data.txt', "
          "xyData=(xy_combined, ), appendMode=ON)")
HIST_ANCHOR = ("    region=a.sets['TopReflection'], sectionPoints=DEFAULT, "
               "rebar=EXCLUDE)")


# ---- NT-1:能量历史注入器 ----

def test_inject_energy_history_idempotent_and_fail_loud():
    fake = "    foo()\n" + HIST_ANCHOR + "\n    bar()\n"
    once = inject_energy_history_request(fake)
    assert 'ATLAS-P3X-ENERGY-HIST' in once
    assert 'H-Energy' in once and 'ALLAE' in once
    assert inject_energy_history_request(once) == once       # 幂等
    with pytest.raises(ValueError):                          # 锚点缺失必炸
        inject_energy_history_request('print(1)\n')


def test_patch_displacement_control():
    from atlas.mechanics.tier_d import patch_displacement_control
    fake = (
        "    mdb.models['Model-1'].DisplacementBC(name='BC-2', "
        "createStepName='Step-1',\n"
        "        region=a.sets['TopReflection'],\n"
        "        u1=0.0, u2=UNSET, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,\n"
        "        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM,\n"
        "        localCsys=None)\n"
        "    mdb.models['Model-1'].Velocity(name='Predefined Field-1',\n"
        "        region=a.sets['TopReflection'],\n"
        "        velocity1=0.0, velocity2=-50.0, velocity3=0.0,\n"
        "        omega=0.0)\n")
    out = patch_displacement_control(fake, target_disp=4.0, time_period=0.08)
    assert 'ATLAS-P3X-DISPCTRL' in out
    assert 'SmoothStepAmplitude' in out and "(0.08, 1.0)" in out
    assert 'u2=-4' in out and 'u2=UNSET' not in out     # 位移驱动
    assert "amplitude='Amp-Crush'" in out
    assert 'velocity2=-50.0' not in out          # 初速度场已删除
    assert "Velocity(name='Predefined Field-1'" not in out
    assert patch_displacement_control(out, 4.0, 0.08) == out         # 幂等
    with pytest.raises(ValueError):
        patch_displacement_control('print(1)\n', 4.0, 0.08)


def test_parse_feature_data_abaqus_format(tmp_path):
    """Abaqus XY 报表 '0.' / '859.525E-06' 格式必须解析(原 regex 漏 '0.')。"""
    p = tmp_path / 'feat.txt'
    p.write_text('\n'.join([
        'job', 'status: successful', 'density: 0.12',
        'Node X Y',
        '                0.                 1.5',
        '              859.525E-06          12.3',
        '                1.10403E-03        0.']), encoding='utf-8')
    f = parse_feature_data(str(p))
    assert len(f['disp']) == 3
    assert f['disp'][0] == 0.0 and abs(f['force'][1] - 12.3) < 1e-9


def test_parse_energy_data_header_aware(tmp_path):
    # 新多列格式(列序任意)
    p = tmp_path / 'e_new.txt'
    rows = ['status: ok', 'time allie allke allae allvd allfd']
    for i in range(20):
        ie = (i + 1) * 5.0
        rows.append(f'{i*0.01:.4f} {ie} {0.02*ie} {0.01*ie} '
                    f'{0.03*ie} {0.02*ie}')
    p.write_text('\n'.join(rows), encoding='utf-8')
    r = parse_energy_data(str(p))
    assert r['status'] == 'ok'
    assert abs(r['ratio_max'] - 0.02) < 1e-6        # ALLKE/ALLIE
    assert abs(r['ratio_allae'] - 0.01) < 1e-6
    assert abs(r['contact_frac'] - 0.05) < 1e-6     # (vd+fd)/ie=0.03+0.02
    # 旧 3 列格式 'time allke allie' 仍解析(向后兼容)
    p2 = tmp_path / 'e_old.txt'
    old = ['status: ok', 'time allke allie']
    for i in range(20):
        ie = (i + 1) * 5.0
        old.append(f'{i*0.01:.4f} {0.01*ie} {ie}')
    p2.write_text('\n'.join(old), encoding='utf-8')
    r2 = parse_energy_data(str(p2))
    assert abs(r2['ratio_max'] - 0.01) < 1e-6


# ---- NT-2/3/4:压溃指标 + 硬门 + margin(合成已知曲线)----

def _synthetic_crush(sigma_pl=1.0, eps_y=0.03, eps_d=0.6, eps_end=0.8,
                     sig_dens=6.0, n=300):
    """理想化 σ(ε):弹性斜坡→平台→致密化陡升。返回 (eps, sig)。"""
    eps = np.linspace(0, eps_end, n)
    sig = np.where(
        eps <= eps_y, sigma_pl * eps / eps_y,
        np.where(eps <= eps_d, sigma_pl,
                 sigma_pl + (sig_dens - sigma_pl)
                 * (eps - eps_d) / (eps_end - eps_d)))
    return eps, sig


def _write_crush_job(tmp_path, eps, sig, rel_density=0.2,
                     ke=0.01, ae=0.01, vd=0.005, fd=0.005,
                     H0=5.0, A0=25.0, lattice=(1, 1, 1)):
    meta = {'name': 'champ_crush', 'analysis_type': 'DynaCompre_50',
            'lattice_array': list(lattice), 'caveats': ['单半径限定'],
            'energy_gate': {'threshold': 0.05}}
    (tmp_path / 'job_meta.json').write_text(json.dumps(meta),
                                            encoding='utf-8')
    disp, force = eps * H0, sig * A0
    fl = ['champ_crush', 'status: COMPLETED', f'density: {rel_density}',
          f'strain_length: {H0}', f'stress_area: {A0}',
          'RIGIDPLATE-2 RIGIDPLATE-1']
    fl += [f'  {d:.6f}  {f:.6f}' for d, f in zip(disp, force)]
    (tmp_path / 'feature_data.txt').write_text('\n'.join(fl),
                                               encoding='utf-8')
    el = ['status: ok', 'time allie allke allae allvd allfd']
    for i in range(40):
        ie = (i + 1) * 10.0
        el.append(f'{i*0.002:.4f} {ie} {ke*ie} {ae*ie} {vd*ie} {fd*ie}')
    (tmp_path / 'energy_data.txt').write_text('\n'.join(el),
                                              encoding='utf-8')


def test_crush_metrics_densification_and_truncation():
    eps, sig = _synthetic_crush(sigma_pl=10.0, sig_dens=60.0, eps_d=0.6)
    cm = crush_metrics(eps * 5.0, sig * 25.0, H0=5.0, A0=25.0)
    assert cm['densified'] is True
    assert 0.54 < cm['eps_d'] < 0.66           # 效率峰 ≈ 致密化起点 0.6
    assert 9.0 < cm['sigma_pl'] < 11.0          # 平台 ≈ 10 MPa
    # 截到 ε_d 的吸能 ≈ 弹性+平台 = (0.15+5.7)*125 ≈ 731 mJ
    assert 680 < cm['comp_EA_to_d'] < 780
    # 关键修正:截断值 << 全曲线(含致密化尾)
    assert cm['comp_EA_to_d'] < 0.75 * cm['comp_EA_full']


def test_crush_SEA_out_of_band_blocks_margin(tmp_path):
    """SEA 超出 PA12 合理带(0.3-8 kJ/kg)→ 即使硬门全过也不进 margin。"""
    eps, sig = _synthetic_crush(sigma_pl=10.0, sig_dens=60.0)  # SEA≈29kJ/kg
    _write_crush_job(tmp_path, eps, sig, ke=0.01, rel_density=0.2)
    checks, summ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12', 'margin_metric': 'SEA'})
    assert summ['gates']['all_pass'] is True     # 物理门过
    assert summ['SEA_in_band'] is False          # 但超合理带
    sea = next(c for c in checks if c['tool'] == 'abaqus.crush.SEA')
    assert sea['pass'] is False
    assert sea['margin_eligible'] is False       # 超带不进 margin
    assert any('合理带' in c for c in sea['caveats'])


def test_crush_SEA_solid_mass_not_envelope(tmp_path):
    eps, sig = _synthetic_crush()
    _write_crush_job(tmp_path, eps, sig, rel_density=0.2)
    checks, summ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12', 'margin_metric': 'SEA'})
    sea = next(c for c in checks if c['tool'] == 'abaqus.crush.SEA')
    # 实心质量 = 1.01e-3·125·0.2 = 0.02525 g;SEA = comp_EA/质量
    assert summ['m_solid_g'] == pytest.approx(0.02525, rel=1e-3)
    assert sea['value'] == pytest.approx(
        summ['comp_EA_to_d'] / 0.02525, rel=1e-3)
    # 实心质量归一 = 包络质量归一 × (1/ρ̄) = 5×(ρ̄=0.2)
    envelope = summ['comp_EA_to_d'] / (1.01e-3 * 125)
    assert sea['value'] == pytest.approx(envelope * 5.0, rel=1e-3)


def test_crush_energy_gate_hard_and_margin(tmp_path):
    eps, sig = _synthetic_crush()
    _write_crush_job(tmp_path, eps, sig, ke=0.01)        # 门过
    checks, summ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12', 'margin_metric': 'comp_EA'})
    gate = next(c for c in checks
                if c['tool'] == 'abaqus.crush.energy_gate')
    assert gate['pass'] is True
    assert summ['gates']['all_pass'] is True
    sea = next(c for c in checks if c['tool'] == 'abaqus.crush.SEA')
    assert sea['margin_eligible'] is True               # 吸能 spec + 门全过


def test_crush_energy_gate_fail_cancels_margin(tmp_path):
    eps, sig = _synthetic_crush()
    _write_crush_job(tmp_path, eps, sig, ke=0.20)        # 动能门超
    checks, summ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12', 'margin_metric': 'SEA'})
    gate = next(c for c in checks
                if c['tool'] == 'abaqus.crush.energy_gate')
    assert gate['pass'] is False
    assert summ['gates']['all_pass'] is False
    for c in checks:
        if c['tool'] in ('abaqus.crush.SEA', 'abaqus.crush.comp_EA'):
            assert c.get('margin_eligible') is False


def test_crush_non_energy_metric_not_margin(tmp_path):
    eps, sig = _synthetic_crush()
    _write_crush_job(tmp_path, eps, sig, ke=0.01)
    checks, _ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12',
                        'margin_metric': 'comp_stiffness'})
    for c in checks:
        if c['tool'] in ('abaqus.crush.SEA', 'abaqus.crush.comp_EA'):
            assert c.get('margin_eligible') is False     # 刚度 spec≠吸能


def test_crush_judge_gives_margin_pass(tmp_path):
    """NT-4 全链:门全过的压溃 SEA(abaqus_fea 白名单)→ judge 给 PASS。"""
    from atlas.evaluator.core import judge
    eps, sig = _synthetic_crush()
    _write_crush_job(tmp_path, eps, sig, ke=0.01, rel_density=0.2)
    spec = {'material': 'PA12', 'margin_metric': 'SEA',
            'design_value_with_fos': 1000.0, 'n_cells': 3,
            'fos_already_applied': True, 'confidence_level': 'screening'}
    checks, summ = results_to_checks_crush(str(tmp_path), spec)
    sea = next(c for c in checks if c['tool'] == 'abaqus.crush.SEA')
    assert summ['SEA_in_band'] is True
    assert sea['value'] > 1000.0 and sea['margin_eligible'] is True
    extra = [{'dimension': 'density', 'tool': 'rel_density.mesh',
              'value': 0.2, 'pass': True, 'status': 'computed',
              'source': 'mesh'},
             {'dimension': 'printability',
              'tool': 'printability.validate_mesh',
              'value': {'watertight': True}, 'pass': True,
              'status': 'computed', 'source': 'trimesh'}]
    t = judge('crush1', '2', checks + extra, spec, n_cells=3)
    assert t['verdict'] == 'PASS'
    assert t['margin']['ratio'] > 1.0


def test_crush_not_densified_no_margin(tmp_path):
    # 只压到 50%,平台未结束,无内部效率峰 → 未致密化
    eps = np.linspace(0, 0.5, 200)
    sig = np.where(eps <= 0.03, 10.0 * eps / 0.03, 10.0)
    _write_crush_job(tmp_path, eps, sig, ke=0.01)
    checks, summ = results_to_checks_crush(
        str(tmp_path), {'material': 'PA12', 'margin_metric': 'SEA'})
    assert summ['gates']['densified'] is False
    assert summ['gates']['all_pass'] is False
    sea = next(c for c in checks if c['tool'] == 'abaqus.crush.SEA')
    assert sea['margin_eligible'] is False


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
