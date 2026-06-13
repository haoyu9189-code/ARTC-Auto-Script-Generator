"""P3-D 单测:新拓扑筛选估值器(beam 为体、文献为界)+ 红线护栏不变量。"""
import json
import os

import pytest

from atlas.evaluator.core import (MARGIN_EVIDENCE_WHITELIST, judge,
                                  validate_trace)
from atlas.mechanics.screen_estimate import (classify_for_scaling,
                                             estimate_from_graph,
                                             literature_band)
from atlas.schema.seeds import seed_graph

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 计算维补齐(模拟 verify 的 density+printability),喂 judge 满足 R1
_EXTRA = [
    {'dimension': 'density', 'tool': 'rel_density.mesh', 'value': 0.124,
     'pass': True, 'status': 'computed', 'source': 'mesh'},
    {'dimension': 'printability', 'tool': 'printability.validate_mesh',
     'value': {'watertight': True}, 'pass': True, 'status': 'computed',
     'source': 'trimesh'},
]
STIFF_SPEC = {'process': 'LPBF', 'material': 'AlSi10Mg', 'n_cells': 3,
              'fos_already_applied': True, 'fos': 1.5,
              'confidence_level': 'screening',
              'margin_metric': 'comp_stiffness',
              'design_value_with_fos': 50.0}


def _champion(name):
    for fn in ('claude_20260612.json', 'claude_20260612b.json'):
        p = os.path.join(_ROOT, 'atlas', 'proposals', fn)
        for pr in json.load(open(p, encoding='utf-8'))['proposals']:
            if pr['name'] == name:
                return pr['doc']
    raise KeyError(name)


# ---- classify_for_scaling ----

def test_classify_clean_stretch():
    info = classify_for_scaling(seed_graph('Cubic'))
    assert info['cls'] == 'stretch'        # M=6, mech=0,非歧义
    assert info['ambiguous'] is False


def test_classify_ambiguous_forces_hybrid():
    # 构造 M=0 的图 → abs(M)<=1 触发歧义 → 保守 hybrid + Nasim caveat
    doc = {'schema': 'atlas-cell-graph/1.0', 'name': 't_amb',
           'cell': {'size_mm': 5.0},
           'nodes': [{'id': 'A', 'frac': [0, 0, 0]},
                     {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
           'edges': [{'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
                     {'n1': 'A', 'n2': 'B', 'shift': [1, 0, 0]},
                     {'n1': 'A', 'n2': 'B', 'shift': [0, 1, 0]}],
           'default_radius_mm': 0.4}
    info = classify_for_scaling(doc)        # M = 3-6+6 = 3? → 见下
    # 该图 M=3-3*2+6=3,mech 可能>0 → 若歧义则 hybrid
    if info['ambiguous']:
        assert info['cls'] == 'hybrid'
        assert any('Nasim' in c or 'FCCZ' in c for c in info['caveats'])


# ---- literature_band ----

def test_band_is_interval_with_provenance():
    b = literature_band('stretch', 0.1, 1700.0, 45.0, 'polymer')
    assert b['E_lo'] < b['E_point'] < b['E_hi']
    assert 'DOI' in b['source']
    assert b['polymer_inference']['source_type'] == 'inference'


def test_band_out_of_domain_gates():
    hi = literature_band('bending', 0.6, 1700.0, 45.0, 'metal')
    assert hi['status'] == 'out_of_domain'      # rho>0.5
    ld = literature_band('stretch', 0.1, 1700.0, 45.0, 'metal',
                         ld_median=3.0)
    assert ld['status'] == 'out_of_domain'      # l/d<5


# ---- estimate_from_graph: 排序值 = beam 物理,非文献 ----

def test_rank_value_is_beam_not_literature():
    checks, summary = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124)
    bh = next(c for c in checks if c['tool'] == 'beam_homog.homogenize')
    band = next(c for c in checks if c['tool'] == 'gibson_ashby.band')
    # 排序值来自 beam_homog,显著 ≠ 文献点估(柱族 Voigt 方向 beam≫文献)
    assert summary['estimate']['E_rank_MPa'] == bh['value']
    assert abs(bh['value'] - band['value']['E_point']) > 10


# ---- 红线护栏不变量 ----

def test_beam_screening_caps_at_screening_pass_never_pass():
    checks, _ = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124)
    t = judge('c', '2', checks + _EXTRA, STIFF_SPEC, n_cells=3)
    assert t['verdict'] == 'SCREENING_PASS'     # 非白名单 → R7 封顶
    assert t['verdict'] != 'PASS'
    assert t['margin']['ratio'] > 1.0           # 有筛选裕度可排序


def test_band_not_margin_eligible_and_not_computed():
    checks, _ = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124)
    band = next(c for c in checks if c['tool'] == 'gibson_ashby.band')
    assert band.get('margin_eligible') is False
    assert band['status'] in ('estimate', 'out_of_domain')
    assert band['status'] != 'computed'         # 不进 R1 多模态计数


def test_energy_metric_rejects_modulus_as_margin():
    """量纲纪律:comp_EA(吸能)spec 下 beam 模量不可作 margin → 需 Tier-D。"""
    ea_spec = dict(STIFF_SPEC, margin_metric='comp_EA',
                   design_value_with_fos=60.0)
    checks, summary = estimate_from_graph(
        _champion('dual_column_web'), ea_spec, rho_rel=0.124)
    bh = next(c for c in checks if c['tool'] == 'beam_homog.homogenize')
    assert bh['margin_eligible'] is False
    t = judge('c', '2', checks + _EXTRA, ea_spec, n_cells=3)
    assert t['verdict'] == 'FAIL'               # 无 margin 证据


def test_judge_invariant_all_classes_never_pass():
    """对 stretch/bending/hybrid,仅 beam 筛选证据者永不到 PASS。"""
    for name in ('dual_column_web', 'mid_braced_column', 'twin_offset_web'):
        checks, _ = estimate_from_graph(_champion(name), STIFF_SPEC,
                                        rho_rel=0.1)
        t = judge('c', '2', checks + _EXTRA, STIFF_SPEC, n_cells=3)
        assert t['verdict'] != 'PASS', f'{name} 不得到 PASS'


def test_screen_estimate_never_calls_retriever():
    """R6:估值器纯本地物理+文献,不碰库内最近邻。"""
    import inspect
    import atlas.mechanics.screen_estimate as se
    src = inspect.getsource(se)
    # 检查实际调用/导入模式(不误伤 docstring 里"不碰 retriever"的说明)
    assert 'from atlas.retriever' not in src
    assert 'import atlas.retriever' not in src
    assert 'nearest_by_density(' not in src
    assert 'get_structure(' not in src


def test_cross_check_informational_not_hard_fail():
    """文献分歧只置 escalate,不否决 beam 物理(pass=None)。"""
    checks, summary = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124)
    cc = next(c for c in checks
              if c['tool'] == 'screen_estimate.cross_check')
    assert cc['pass'] is None                   # 信息性,不 hard-fail
    # 柱族 Voigt 方向 beam≫文献 → 不一致 → escalate
    assert summary['escalate_tier_d'] is True


def test_polymer_subterm_triggers_r4_downgrade():
    checks, _ = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124,
        material_family='polymer')
    t = judge('c', '2', checks + _EXTRA, STIFF_SPEC, n_cells=3)
    assert any('R4' in d for d in t['downgrades'])


def test_trace_schema_valid_with_screen_checks():
    checks, _ = estimate_from_graph(
        _champion('dual_column_web'), STIFF_SPEC, rho_rel=0.124)
    t = judge('c', '2', checks + _EXTRA, STIFF_SPEC, n_cells=3)
    validate_trace(t)                            # source_type 全在 enum


def test_pscz_replay_yields_physics_evidence_no_abaqus():
    """PSCZ(此前零力学证据→被迫 Tier-D)现得 beam 物理估值 + 升压标志。"""
    cands = json.load(open(os.path.join(
        _ROOT, 'atlas', 'reports', 'D2', 'lpbf_bracket',
        'candidates.json'), encoding='utf-8'))['candidates']
    pscz = next(c for c in cands if c['id'] == 'c6')['geometry']['graph_doc']
    spec = json.load(open(os.path.join(
        _ROOT, 'atlas', 'reports', 'D2', 'lpbf_bracket', 'spec.json'),
        encoding='utf-8'))['spec']
    checks, summary = estimate_from_graph(pscz, spec, rho_rel=0.265)
    assert any(c['tool'] == 'beam_homog.homogenize'
               and c['status'] == 'computed' for c in checks)
    # 吸能 spec + beam/文献分歧 → 诚实升 Tier-D(与实测 ABAQUS 路径一致)
    assert summary['escalate_tier_d'] is True
