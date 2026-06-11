"""C3 单测:K=3 阶梯顺序、必败候选耗尽出 Pareto、修补即停、状态落盘。

evaluate 直接用 C2 确定性引擎(集成而非桩),regenerate 注入桩。
"""
import json

from atlas.evaluator import judge
from atlas.orchestration import RegenerationLoop, pareto_front


def make_eval(margin_value_fn):
    """构造 evaluate_fn:margin 证据值由 margin_value_fn(candidate) 给。"""
    def evaluate(candidate, spec, round_idx):
        v = margin_value_fn(candidate)
        checks = [
            {'dimension': 'printability', 'tool': 'checks', 'value': 1.0,
             'pass': True, 'status': 'computed', 'source': 's'},
            {'dimension': 'density', 'tool': 'rel_density.mesh',
             'value': candidate.get('rho_rel', 0.3), 'pass': True,
             'status': 'computed', 'source': 's'},
            {'dimension': 'mechanics', 'tool': 'db', 'value': v,
             'pass': True, 'status': 'computed', 'source': 's',
             'source_type': 'internal_fea', 'margin_eligible': True},
        ]
        return judge(candidate['id'], candidate.get('tier', '1'), checks,
                     spec, regeneration_round=round_idx)
    return evaluate


SPEC = {'fos_already_applied': True, 'confidence_level': 'screening',
        'margin_metric': 'SEA', 'design_value_with_fos': 2.0}


def test_param_repair_fixes_margin_and_stops():
    """margin 不足 → round1 确定性修补(加半径)即过,不再走 LLM 重生。"""
    # margin 值 ∝ r²(模拟密度增益)
    ev = make_eval(lambda c: 8.0 * c['geometry']['radius_mm'] ** 2)
    loop = RegenerationLoop(ev, regenerate_fn=lambda *a, **k: [])
    r = loop.run([{'id': 'c1', 'tier': '1', 'rho_rel': 0.3,
                   'geometry': {'topology': 'BCC', 'radius_mm': 0.45}}],
                 SPEC)  # 8*0.2025=1.62 < 2.0 → 修补放大 r
    assert r['outcome'] == 'PASS'
    assert r['ladder_executed'] == ['param_repair']
    assert len(r['passed']) == 1
    assert r['passed'][0]['trace']['regeneration_round'] == 1


def test_doomed_candidate_exhausts_ladder_in_order_then_pareto():
    """必败候选:≤3 轮、阶梯顺序正确、K 耗尽出含全 trace 的 Pareto。"""
    calls = []

    def regen(failed, spec, history, enriched):
        calls.append(enriched)
        assert history and history[0]['reasons']  # 失败原因传给重生器
        return [{'id': f'r{len(calls)}', 'tier': '1', 'rho_rel': 0.35,
                 'geometry': {'topology': 'FCC', 'radius_mm': 0.4}}]

    ev = make_eval(lambda c: 0.5)  # 永远 margin 0.25 < 1 → 必败
    loop = RegenerationLoop(ev, regenerate_fn=regen)
    r = loop.run([{'id': 'c1', 'tier': '1', 'rho_rel': 0.30,
                   'geometry': {'topology': 'BCC', 'radius_mm': 0.5}}],
                 SPEC)
    assert r['outcome'] == 'PARETO'
    # 阶梯顺序:修补 → 重生 → 增强重生;LLM 桩第二次调用带 enriched
    assert r['ladder_executed'] == ['param_repair', 'regenerate',
                                    'context_enrich']
    assert calls == [False, True]
    assert len(r['rounds']) == 3  # ≤ K=3
    # Pareto 前沿存在且全部 trace 在册
    assert r['pareto_front'] and r['n_traces'] == len(r['all_traces'])
    assert all('trace' in e for e in r['pareto_front'])
    assert r['unmet']  # 未满足项明示


def test_pareto_front_nondominated():
    es = [{'margin_ratio': 0.9, 'rho_rel': 0.30},
          {'margin_ratio': 0.8, 'rho_rel': 0.20},
          {'margin_ratio': 0.7, 'rho_rel': 0.25}]  # 被前两者支配
    front = pareto_front(es)
    assert es[0] in front and es[1] in front and es[2] not in front


def test_state_file_counter(tmp_path):
    state = str(tmp_path / 'loop_state.json')
    ev = make_eval(lambda c: 0.5)
    loop = RegenerationLoop(ev, regenerate_fn=lambda *a, **k: [],
                            state_path=state)
    loop.run([{'id': 'c1', 'tier': '1', 'rho_rel': 0.3,
               'geometry': {'topology': 'BCC', 'radius_mm': 0.5}}], SPEC)
    s = json.loads(open(state, encoding='utf-8').read())
    assert s['k_max'] == 3 and s['round'] >= 1
    assert s['ladder'][0] == 'param_repair'


def test_dfam_repair_bumps_radius_to_process_floor():
    from atlas.orchestration.regenerate import default_param_repair
    trace = {'verdict_reasons': ['硬性检查未过: 杆径 0.70 < MJF 最小 0.8'],
             'margin': None}
    fixed = default_param_repair(
        {'id': 'c9', 'geometry': {'topology': 'BCC', 'radius_mm': 0.35}},
        trace, {'process': 'MJF'})
    assert fixed['geometry']['radius_mm'] >= 0.41
    assert fixed['lineage']['parents'] == ['c9']


def test_dfam_repair_matches_engine_reason_wording_with_thinning():
    """P3-B 回归:C2 引擎实文 reason + 实测节点削薄补偿。

    D2 真跑发现:引擎对 min-feature 失败的 reason 实文是
    「硬性检查未过: printability/printability.measure_min_feature」,
    原匹配词('杆径'/'min_strut')对不上 → 修补从未触发。
    """
    from atlas.orchestration.regenerate import default_param_repair
    trace = {'verdict_reasons': [
        '硬性检查未过: printability/printability.measure_min_feature'],
        'margin': None,
        'checks': [{'tool': 'printability.measure_min_feature',
                    'value': {'min_mm': 0.7759}, 'pass': False}]}
    fixed = default_param_repair(
        {'id': 'c1', 'geometry': {'topology': 'BCC', 'radius_mm': 0.4}},
        trace, {'process': 'SLS'})
    assert fixed is not None, '引擎实文 reason 必须触发修补'
    # 削薄 = 0.8-0.7759 = 0.0241 → r ≥ (0.8+0.0241)/2+0.01 ≈ 0.4221
    assert fixed['geometry']['radius_mm'] >= 0.422
    assert any('round-1' in n for n in fixed['lineage']['notes'])
