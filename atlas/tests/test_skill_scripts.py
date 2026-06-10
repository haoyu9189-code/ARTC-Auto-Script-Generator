"""A3 单测:skill 脚本信封合同 + 已知解析值回归 + 勘误数值核验。"""
import importlib.util
import json
import pathlib
import sys

import pytest

SKILL = pathlib.Path(__file__).resolve().parents[2] / '.claude' / 'skills' / 'atlas'
SCRIPTS = SKILL / 'scripts'
THRESHOLDS = SKILL / 'references' / 'thresholds'


def load(name):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENVELOPE_KEYS = {'value', 'status', 'inputs_echo', 'source', 'caveats'}


def assert_envelope(r):
    assert ENVELOPE_KEYS <= set(r), f'信封缺字段: {ENVELOPE_KEYS - set(r)}'
    assert r['source'] and isinstance(r['source'], str)
    assert isinstance(r['inputs_echo'], dict)
    assert r['status'] in ('computed', 'estimate', 'default',
                           'out_of_domain', 'needs_input')


# ---- gibson_ashby:已知解析值 ----

def test_gibson_ashby_octet_stretch():
    ga = load('gibson_ashby')
    r = ga.estimate('stretch', 0.1, 1700.0, 45.0)
    assert_envelope(r)
    assert r['status'] == 'estimate'
    assert abs(r['value']['E_MPa'] - (1 / 9) * 0.1 * 1700) < 1e-9
    assert abs(r['value']['sigma_y_MPa'] - (1 / 3) * 0.1 * 45) < 1e-9
    assert 'S0022-5096(01)00010-2' in r['source']  # DFA 2001 DOI


def test_gibson_ashby_bending():
    ga = load('gibson_ashby')
    r = ga.estimate('bending', 0.1, 1700.0, 45.0)
    assert abs(r['value']['E_MPa'] - 0.01 * 1700) < 1e-9
    assert abs(r['value']['sigma_y_MPa'] - 0.3 * 0.1 ** 1.5 * 45) < 1e-9
    # screening-only 红线必须出现在 caveats
    assert any('screening' in c for c in r['caveats'])


def test_gibson_ashby_domain_and_inputs():
    ga = load('gibson_ashby')
    assert ga.estimate('bending', 0.8, 1700, 45)['status'] == 'out_of_domain'
    assert ga.estimate('bending', -1, 1700, 45)['status'] == 'needs_input'
    r = ga.estimate('hybrid', 0.2, 1700, 45)
    assert r['value']['E_MPa'] <= (1 / 9) * 0.2 * 1700 + 1e-9  # 保守下包络


# ---- maxwell:只说倾向 ----

def test_maxwell_known_values():
    mx = load('maxwell_check')
    r = mx.check(36, 14)  # octet
    assert_envelope(r)
    assert r['value']['maxwell_M'] == 0
    assert r['value']['tendency'] == 'stretch-leaning'
    r2 = mx.check(8, 9)  # BCC
    assert r2['value']['maxwell_M'] == -13
    assert r2['value']['tendency'] == 'bending-leaning'
    # 红线:必要非充分 caveat 必须在
    assert any('必要非充分' in c for c in r['caveats'])


# ---- rel_density:estimate 与 mesh 双档 ----

def test_rel_density_two_modes():
    rd = load('rel_density')
    a = rd.analytic('BCC', 4, 0.5)
    m = rd.mesh('BCC', 4, 0.5)
    assert_envelope(a)
    assert_envelope(m)
    assert a['status'] == 'estimate' and m['status'] == 'computed'
    assert 0.15 < m['value'] < 0.30  # BCC r=0.5 实测体积 27.16/125≈0.217
    assert abs(m['value'] - 27.16 / 125) < 0.01
    assert a['value'] > m['value'] * 0.8  # 一阶高估或接近


# ---- sea_sanity:勘误后带 0.3–8 ----

def test_sea_sanity_band():
    ss = load('sea_sanity')
    ok = ss.check(2.5)
    assert_envelope(ok)
    assert ok['value']['verdict'] == 'ok_typical'
    assert ok['value']['band_kj_per_kg'] == [0.3, 8.0]  # 勘误后,非 2–15
    bad = ss.check(12.0)
    assert bad['value']['verdict'] == 'implausible'
    assert any('金属' in c for c in bad['caveats'])
    other = ss.check(5.0, material='AlSi10Mg')
    assert other['status'] == 'out_of_domain'


# ---- sea_backcalc:Q2a 反推 ----

def test_sea_backcalc():
    sb = load('sea_backcalc')
    r = sb.from_energy(50.0, f_max_N=2000.0, area_m2=0.01,
                       rho_rel=0.2, volume_m3=0.001, rho_s_kg_m3=1010)
    assert_envelope(r)
    assert r['status'] == 'computed'
    assert abs(r['value']['SEA_required_J_per_kg']
               - 50.0 / (0.2 * 0.001 * 1010)) < 1e-9
    assert abs(r['value']['sigma_plateau_max_Pa'] - 200000.0) < 1e-9
    # 红线:不二次乘 FoS 的提示必须在
    assert any('不得二次乘' in c for c in r['caveats'])
    # 缺体积必须 needs_input 且要求追问
    r2 = sb.from_energy(50.0, rho_rel=0.2)
    assert r2['status'] == 'needs_input'
    assert any('追问' in c for c in r2['caveats'])


# ---- 阈值 JSON:每条带 source;勘误值核验 ----

def _walk_leaves(node, path=''):
    if isinstance(node, dict):
        if 'value' in node or 'points_rho_rel_to_cleanable_cell_layers' in node:
            yield path, node
        else:
            for k, v in node.items():
                yield from _walk_leaves(v, f'{path}/{k}')


@pytest.mark.parametrize('fname', ['dfam_rules.json', 'material_props.json'])
def test_thresholds_all_have_sources(fname):
    data = json.loads((THRESHOLDS / fname).read_text(encoding='utf-8'))
    leaves = [(p, n) for k, v in data.items() if k != '_meta'
              for p, n in _walk_leaves(v, k)]
    assert leaves, '阈值文件为空?'
    for path, node in leaves:
        assert node.get('source'), f'{fname}:{path} 缺 source'
        assert node.get('source_type') in (
            'academic_doi', 'vendor', 'inference'), \
            f'{fname}:{path} source_type 非法'


def test_corrected_values_present():
    sl = json.loads((THRESHOLDS / 'scaling_laws.json').read_text(encoding='utf-8'))
    # Zhong 2023 勘误出处 + 仅限金属
    assert 'cossms' in sl['am_asbuilt_deviation']['metal_lattices']['source']
    assert sl['am_asbuilt_deviation']['polymer_lattices']['source_type'] == 'inference'
    # TPMS 指数限定 Ti-6Al-4V,不适用 PA12
    assert 'PA12' in sl['tpms_stiffness_exponents']['validity_domain']
    # SEA 带勘误为 0.3–8
    assert sl['pa12_sea_band']['value_kj_per_kg'] == [0.3, 8.0]
    mp = json.loads((THRESHOLDS / 'material_props.json').read_text(encoding='utf-8'))
    # ×0.92 必须 inference
    kd = mp['AlSi10Mg_LPBF']['surface_defect_knockdown']
    assert kd['source_type'] == 'inference'


def test_no_stale_numbers_in_skill():
    """勘误前数值(SEA 2–15 带)不得在 skill 文案中出现。"""
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    assert '2–15' not in text and '2-15 kJ' not in text
    for f in THRESHOLDS.glob('*.json'):
        t = f.read_text(encoding='utf-8')
        assert '[2, 15]' not in t and '2-15 kJ' not in t
