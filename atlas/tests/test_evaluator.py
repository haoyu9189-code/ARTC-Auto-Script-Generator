"""C2 单测:判决规则 R1–R7 逐条正反用例 + trace schema + hook 脚本。"""
import json
import subprocess
import sys

import jsonschema
import pytest

from atlas.evaluator import judge, validate_trace


def check(dimension='printability', tool='atlas.printability.checks',
          value=1.0, passed=True, status='computed',
          source='test source', **kw):
    c = {'dimension': dimension, 'tool': tool, 'value': value,
         'pass': passed, 'status': status, 'source': source}
    c.update(kw)
    return c


def spec(**over):
    s = {'fos_already_applied': True, 'confidence_level': 'screening',
         'margin_metric': 'SEA', 'design_value_with_fos': 2.0}
    s.update(over)
    return s


def good_checks():
    return [
        check('printability'),
        check('mechanics', tool='gibson_ashby', value=2.6,
              margin_eligible=True, source_type='internal_fea'),
        check('density', tool='rel_density.mesh', value=0.3),
    ]


# ---- R1 多模态一致 ----

def test_r1_single_check_cannot_pass():
    t = judge('c1', '1', [check('printability')], spec())
    assert t['verdict'] == 'FAIL'
    assert any('R1' in r for r in t['verdict_reasons'])


def test_r1_multi_dimension_passes():
    t = judge('c1', '1', good_checks(), spec())
    assert t['verdict'] == 'PASS'


# ---- R2 margin 含 FoS 不二次乘 ----

def test_r2_fos_not_confirmed_refuses():
    t = judge('c1', '1', good_checks(), spec(fos_already_applied=False))
    assert t['verdict'] == 'FAIL'
    assert any('二次乘' in r for r in t['verdict_reasons'])


def test_r2_margin_below_one_fails():
    cs = good_checks()
    cs[1]['value'] = 1.5  # 1.5/2.0 = 0.75 < 1
    t = judge('c1', '1', cs, spec())
    assert t['verdict'] == 'FAIL'
    assert any('margin' in r for r in t['verdict_reasons'])
    assert t['margin']['ratio'] == pytest.approx(0.75)


# ---- R3 n<3 ----

def test_r3_warning_and_near_final_fail():
    t = judge('c1', '1', good_checks(), spec(), n_cells=2)
    assert any('R3' in d for d in t['downgrades'])
    assert t['verdict'] == 'PASS'  # screening 级只警示
    t2 = judge('c1', '1', good_checks(),
               spec(confidence_level='near_final'), n_cells=2)
    assert t2['verdict'] == 'FAIL'
    assert any('实测' in r for r in t2['verdict_reasons'])


# ---- R4 inference 降级 ----

def test_r4_inference_downgrade():
    cs = good_checks() + [check('material', tool='material_props',
                                value=0.92, source_type='inference')]
    t = judge('c1', '1', cs, spec(confidence_level='design_reference'))
    assert any('R4' in d for d in t['downgrades'])
    assert any('降为 screening' in r for r in t['verdict_reasons'])


# ---- R5 最近邻必带 applicability ----

def test_r5_nn_without_applicability_unusable():
    cs = [check('printability'),
          check('mechanics', tool='retriever.nearest_by_density',
                value=2.6, margin_eligible=True,
                source_type='internal_fea')]  # 缺 applicability_distance
    t = judge('c1', '1', cs, spec())
    assert t['verdict'] == 'FAIL'  # NN 证据作废后只剩 1 维 → R1
    assert any('R5' in r for r in t['verdict_reasons'])
    cs[1]['applicability_distance'] = 0.02  # 带距离则可用
    t2 = judge('c1', '1', cs + [check('density')], spec())
    assert t2['verdict'] == 'PASS'


# ---- R6 OOD 禁最近邻 ----

def test_r6_ood_nearest_neighbor_voided():
    cs = [check('printability'), check('density'),
          check('mechanics', tool='retriever.nearest_by_density',
                value=2.6, margin_eligible=True,
                source_type='internal_fea', applicability_distance=0.01)]
    t = judge('c2', '2', cs, spec())  # Tier-2 OOD
    assert any('R6' in r for r in t['verdict_reasons'])
    assert t['verdict'] == 'FAIL'  # NN 作废 → 无 margin 证据


# ---- R7 margin 证据来源白名单 ----

def test_r7_screening_evidence_caps_verdict():
    cs = [check('printability'), check('density'),
          check('mechanics', tool='gibson_ashby', value=2.6,
                margin_eligible=True, status='estimate',
                source_type='internal_computed')]  # 解析筛,非白名单
    t = judge('c1', '1', cs, spec())
    assert t['verdict'] == 'SCREENING_PASS'
    assert any('R7' in r for r in t['verdict_reasons'])


# ---- trace schema ----

def test_trace_schema_accept_and_reject():
    t = judge('c1', '1', good_checks(), spec())
    validate_trace(t)  # 引擎产物必合 schema
    bad = dict(t)
    bad['verdict'] = 'MAYBE'  # 非法判决值
    with pytest.raises(jsonschema.ValidationError):
        validate_trace(bad)
    bad2 = {k: v for k, v in t.items() if k != 'checks'}  # 缺证据
    with pytest.raises(jsonschema.ValidationError):
        validate_trace(bad2)


# ---- PreToolUse hook 脚本 ----

def _run_hook(payload, enabled=True):
    import os
    env = dict(os.environ)
    env['ATLAS_EVALUATOR_HOOK'] = '1' if enabled else '0'
    p = subprocess.run(
        [sys.executable, 'atlas/evaluator/hooks/block_non_evidence.py'],
        input=json.dumps(payload), capture_output=True, text=True,
        env=env)
    return p.returncode, p.stderr


def test_hook_blocks_non_whitelist_and_allows_evidence_tools():
    rc, err = _run_hook({'tool_name': 'WebFetch'})
    assert rc == 2 and '证据白名单' in err
    rc, _ = _run_hook({'tool_name': 'Write'})
    assert rc == 2
    rc, _ = _run_hook({'tool_name': 'Bash'})
    assert rc == 0
    rc, _ = _run_hook({'tool_name': 'mcp__atlas-retriever__query_cell_db'})
    assert rc == 0
    rc, _ = _run_hook({'tool_name': 'WebFetch'}, enabled=False)
    assert rc == 0  # 未启用时放行(不影响其它会话)
