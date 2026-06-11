"""C2:Evaluator 判决引擎(确定性代码,非 LLM 自觉)。

设计依据(RESEARCH.md):提示词不可靠(ChemCrow EvaluatorGPT 偏好流利
幻觉)、单一自动裁判过信(A-Lab 被 Nature 更正)、默认值静默泄出
(FEABench)。判决规则表全部落在代码,LLM Evaluator agent 只是调用方,
数字抄录不转述。

规则表(每条有正反测试):
R1 多模态一致:任何单项检查不得授予 PASS;≥2 个维度有 computed 证据
   且全部硬性检查通过才可 PASS。
R2 margin = pred/design ≥ 1.0,design 已含 FoS;spec 未确认
   fos_already_applied 时拒绝判决(防二次乘)。
R3 n<3 强警示;confidence=near_final 且 n<3 → FAIL。
R4 source_type=inference 的证据 → 结论自动降级一档并留痕。
R5 库内最近邻证据必须带 applicability_distance,缺失则该证据不可用。
R6 OOD(Tier-2/1.75 库外)候选使用最近邻证据 = 红线违例,证据作废。
R7 margin 证据来源白名单:库内实测(internal_fea)或 Tier-D FEA;
   解析筛(screening only)支撑的最高判 SCREENING_PASS。
"""
import json
import os

import jsonschema

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_HERE, '..', 'schema',
                            'verification-trace-1.0.json')

RULES = ('R1 多模态一致', 'R2 margin 含 FoS 不二次乘', 'R3 n<3 强警示',
         'R4 inference 自动降级', 'R5 最近邻必带 applicability',
         'R6 OOD 禁最近邻', 'R7 margin 证据来源白名单')

_CONF_ORDER = ['screening', 'design_reference', 'near_final']
# beam_fem_calibrated:P2-1c 标定的 frame_fem,margin 值须为
# E_y_margin_safe(已按 p90 残差折减,弯曲类 OOD 折减后≈0 → 实质
# 强制 Tier-D)。abaqus_fea:P3-A Tier-D 终审(tier_d.py 桥,能量门
# 未过时 margin_eligible 由桥端取消,白名单成员资格不变)。
MARGIN_EVIDENCE_WHITELIST = ('internal_fea', 'beam_fem_calibrated',
                             'abaqus_fea')


def validate_trace(trace):
    """trace 不合 schema 即拒(PostToolUse 校验角色)。"""
    with open(_SCHEMA_PATH, encoding='utf-8') as f:
        schema = json.load(f)
    jsonschema.validate(trace, schema)


def judge(candidate_id, tier, checks, spec, n_cells=None,
          regeneration_round=0):
    """判决一个候选。输入:checks(各验证维度信封)+ spec。
    返回合 schema 的 verification trace。"""
    reasons, downgrades = [], []
    verdict = None

    # R2 前置:FoS 已含确认
    if not spec.get('fos_already_applied'):
        return _trace(candidate_id, tier, checks, 'FAIL',
                      ['R2: spec 未确认 fos_already_applied,拒绝判决'
                       '(防二次乘 FoS)'], downgrades, spec, n_cells,
                      regeneration_round)

    usable = []
    for c in checks:
        # R5/R6:最近邻证据纪律
        is_nn = 'nearest' in c.get('tool', '')
        if is_nn:
            if tier in ('2', '1.75'):
                reasons.append(f"R6: OOD(Tier-{tier}) 候选的最近邻证据"
                               f"作废({c['tool']})")
                continue
            if c.get('applicability_distance') is None:
                reasons.append(f"R5: 最近邻证据缺 applicability_distance,"
                               f"不可用({c['tool']})")
                continue
        # R4:inference 降级留痕
        if c.get('source_type') == 'inference':
            downgrades.append(f"R4: {c['dimension']}/{c['tool']} 证据为 "
                              f"inference,结论降级一档")
        usable.append(c)

    hard_fails = [c for c in usable if c.get('pass') is False]
    computed_dims = {c['dimension'] for c in usable
                     if c.get('status') == 'computed'
                     and c.get('pass') is True}

    # R3:尺寸效应警示
    conf = spec.get('confidence_level')
    if n_cells is not None and n_cells < 3:
        downgrades.append('R3: n<3,尺寸效应区强警示(1→3 胞跳变最剧烈),'
                          '强烈建议 n>=3 或实测')
        if conf == 'near_final':
            reasons.append('R3: 接近定稿级 + n<3 → FAIL(必须实测/加大阵列)')
            verdict = 'FAIL'

    if hard_fails and verdict is None:
        verdict = 'FAIL'
        reasons += [f"硬性检查未过: {c['dimension']}/{c['tool']}"
                    for c in hard_fails]

    # R1:多模态一致
    if verdict is None and len(computed_dims) < 2:
        verdict = 'FAIL'
        reasons.append(f'R1: 仅 {len(computed_dims)} 个维度有 computed '
                       f'通过证据,单项检查不得授予 PASS')

    # R2/R7:margin 判定
    margin = None
    if verdict is None:
        margin = _compute_margin(usable, spec)
        if margin is None:
            verdict = 'FAIL'
            reasons.append('R2: 无可用 margin 证据(pred/design 缺失)')
        elif margin['ratio'] < 1.0:
            verdict = 'FAIL'
            reasons.append(f"R2: margin {margin['ratio']:.3f} < 1.0"
                           f"(design 已含 FoS,不再二次乘)")
        elif not margin['whitelisted']:
            verdict = 'SCREENING_PASS'
            reasons.append('R7: margin 证据来自解析筛(screening only),'
                           '最高判 SCREENING_PASS;设计参考级需库内实测'
                           '或 Tier-D FEA')
        else:
            verdict = 'PASS'
            reasons.append(f"全维度通过,margin {margin['ratio']:.3f} >= 1.0")

    # R4 落地:降级影响最终可用置信度
    if downgrades and verdict == 'PASS' and conf in _CONF_ORDER[1:]:
        idx = _CONF_ORDER.index(conf)
        reasons.append(f'R4: 存在 inference 证据,结论置信度降为 '
                       f'{_CONF_ORDER[idx - 1]}')

    return _trace(candidate_id, tier, checks, verdict, reasons,
                  downgrades, spec, n_cells, regeneration_round,
                  margin=margin)


def _compute_margin(checks, spec):
    metric = spec.get('margin_metric', 'SEA')
    design = spec.get('design_value_with_fos')
    if not design:
        return None
    cands = [c for c in checks
             if c.get('margin_eligible') and isinstance(c.get('value'),
                                                        (int, float))]
    if not cands:
        return None
    # 取白名单来源优先,其次解析筛
    cands.sort(key=lambda c: c.get('source_type')
               not in MARGIN_EVIDENCE_WHITELIST)
    best = cands[0]
    return {'metric': metric, 'predicted': float(best['value']),
            'design_value_with_fos': float(design),
            'ratio': float(best['value']) / float(design),
            'evidence_source': best['source'],
            'whitelisted': best.get('source_type')
            in MARGIN_EVIDENCE_WHITELIST}


def _trace(candidate_id, tier, checks, verdict, reasons, downgrades,
           spec, n_cells, regeneration_round, margin=None):
    trace = {'candidate_id': candidate_id, 'tier': tier,
             'checks': checks, 'verdict': verdict,
             'verdict_reasons': reasons, 'downgrades': downgrades,
             'confidence_level': spec.get('confidence_level'),
             'n_cells': n_cells,
             'regeneration_round': regeneration_round}
    if margin:
        trace['margin'] = {k: v for k, v in margin.items()
                           if k != 'whitelisted'}
    validate_trace(trace)
    return trace
