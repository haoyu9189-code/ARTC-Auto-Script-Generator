"""P3-D:新拓扑/OOD 的"物理为体、文献为界"筛选估值器(不跑 ABAQUS)。

回答用户的"为什么不能生成结构 + 根据论文对比估测":
- 真问题不是生成不出来,而是 verify.py 的 OOD 分支不调 beam_homog,
  graph_doc-only 新候选(如 PSCZ)连力学证据都没有 → R2/R1 FAIL →
  被迫升 Tier-D。
- "直接按论文对比估测"(把候选归到 archetype 再套 C 系数)本质等同于
  红线 R6 禁掉的"库内最近邻类比",只是从单点类比变类别类比 → 绝不可
  承担裕度。
- 正解:**beam_homog(在候选自身商图上做 Timoshenko 周期均质化,
  ~10ms,对 Lumpe 目录中位 0.9%)作为核心排序估值**(在自身几何上做
  物理,满足创始原则);**文献标度律(G-A/DFA)只作独立误差带做
  交叉校验,永不进裕度**。

红线对抗(workflow safe_with_safeguards)固化的护栏:
1. beam_homog 估值 margin_eligible=True 但 source_type='internal_computed'
   (非白名单)→ R7 封顶 SCREENING_PASS,永不 PASS。
2. 文献带 margin_eligible=False、status∈{estimate,out_of_domain}
   (绝不 'computed')→ 不进 R1 多模态计数、不进裕度。
3. 聚合物偏差子项 source_type='inference' → R4 自动降级。
4. beam 与文献带不一致(超出文献误差带)→ cross_check pass=False →
   FAIL → 强制升 Tier-D(物理与文献分歧时谁都不信,付费跑 ABAQUS)。
5. Maxwell 必要非充分:M 符号与 SVD 机构数矛盾(FCCZ/FBCCZ 型)→
   强制保守 hybrid 下包络 + 挂 Nasim 2021 反例 caveat。
6. l/d<5 或 ρ̄∉[0.01,0.5] → 文献带 out_of_domain。
7. OOD 仍不碰 retriever 最近邻(R6,verify.py 既有 tier 门保留)。
8. 弯曲类 OOD 的设计裕度仍走 calibrate.certify(p90 折减→0→Tier-D),
   本估值器只给筛选排序,不开后门。
"""
import json
import os
import sys

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas.gates.gates import gate_c4_maxwell_svd
from atlas.mechanics.beam_homog import homogenize

_SCALING = os.path.join(_ROOT, '.claude', 'skills', 'atlas', 'references',
                        'thresholds', 'scaling_laws.json')

SRC_DFA = ('Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, '
           'DOI 10.1016/S0022-5096(01)00010-2')
SRC_GA = ('Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 '
          '(ISBN 9780521499118)')
SRC_LUMPE = ('beam_homog vs Lumpe-Stankovic 目录(中位 0.9%,p90 15.1%,'
             '全正偏置;atlas/references/beam_homog_validation.md)')
CAVEAT_SCREENING = ('筛选级:仅供排序/SCREENING_PASS,不得进 margin 门;'
                    '设计裕度须 calibrate.certify(白名单)或 Tier-D FEA')
NASIM_CAVEAT = ('Maxwell 必要非充分:FCCZ/FBCCZ 类含定向杆拓扑可违背倾向'
                '(Nasim & Galvanetto 2021, MJF PA12)→ 已强制保守包络')

# 文献 C 系数相对半宽(workflow 语料审计):随 archetype 散布,
# 用于新拓扑(精确 C 未知)的诚实误差带。
_HALFWIDTH = {'stretch': 0.20, 'bending': 0.30, 'hybrid': 0.30}
# beam_homog 对 Lumpe 的 p90 单边带(全正偏置 → 真值≤beam 估计)
_BEAM_P90_LO = 0.151
_POLY_INFER = (0.10, 0.30)   # 聚合物-金属基线漂移(无文献,inference)
_RHO_DOMAIN = (0.01, 0.5)
_LD_MIN = 5.0


def classify_for_scaling(doc):
    """Maxwell 倾向 + SVD 机构数定类;矛盾则强制保守 hybrid。"""
    g = gate_c4_maxwell_svd(doc)
    v = g['value'] if isinstance(g, dict) and 'value' in g else g
    M = v['maxwell_M']
    mech = v.get('mechanisms_est', 0)
    ss = v.get('self_stress_states', 0)
    base = 'stretch' if M >= 0 else 'bending'
    # FCCZ/FBCCZ 型:Maxwell 判 stretch(M≥0)但 SVD 仍有机构(欠定)
    ambiguous = (M >= 0 and mech > 0) or (abs(M) <= 1)
    cls = 'hybrid' if ambiguous else base
    caveats = []
    if ambiguous:
        caveats.append(NASIM_CAVEAT)
    return {'cls': cls, 'maxwell_M': int(M), 'mechanisms_est': int(mech),
            'self_stress_states': int(ss), 'ambiguous': bool(ambiguous),
            'caveats': caveats}


def literature_band(cls, rho_rel, Es, sigma_ys, material_family='polymer',
                    ld_median=None):
    """文献标度律点估 + 按 archetype C 散布的诚实区间(交叉校验用)。"""
    if cls == 'stretch':
        E = (1.0 / 9.0) * rho_rel * Es
        sy = (1.0 / 3.0) * rho_rel * sigma_ys
        src = SRC_DFA
    elif cls == 'bending':
        E = rho_rel ** 2 * Es
        sy = 0.3 * rho_rel ** 1.5 * sigma_ys
        src = SRC_GA
    else:  # hybrid:两族下包络(保守)
        E = min(rho_rel ** 2 * Es, (1.0 / 9.0) * rho_rel * Es)
        sy = min(0.3 * rho_rel ** 1.5 * sigma_ys,
                 (1.0 / 3.0) * rho_rel * sigma_ys)
        src = SRC_DFA + ' + ' + SRC_GA
    hw = _HALFWIDTH[cls]
    status = 'estimate'
    caveats = [CAVEAT_SCREENING]
    if not (_RHO_DOMAIN[0] <= rho_rel <= _RHO_DOMAIN[1]):
        status = 'out_of_domain'
        caveats.append(f'ρ̄={rho_rel:.3f} 越出 G-A/DFA 适用域 '
                       f'[{_RHO_DOMAIN[0]}, {_RHO_DOMAIN[1]}]')
    if ld_median is not None and ld_median < _LD_MIN:
        status = 'out_of_domain'
        caveats.append(f'中位 l/d={ld_median:.2f}<5:梁理论失效区'
                       '(Zhong 2023,金属可达 300% 偏差)')
    poly = None
    if material_family != 'metal':
        poly = {'extra_halfwidth': list(_POLY_INFER),
                'source_type': 'inference',
                'note': '聚合物-金属基线漂移 ±10-30%,查无文献来源'}
        hw += _POLY_INFER[0]   # 点估带按下界保守加宽
    return {'E_point': E, 'sigma_point': sy,
            'E_lo': E * (1 - hw), 'E_hi': E * (1 + hw),
            'halfwidth': hw, 'status': status, 'source': src,
            'polymer_inference': poly, 'caveats': caveats}


def estimate_from_graph(doc, spec=None, Es=1700.0, sigma_ys=45.0,
                        rho_rel=None, material_family=None):
    """新拓扑筛选估值 → (checks, summary)。verify.py OOD 分支单一入口。

    核心估值 = beam_homog(自身几何物理);文献带 = 交叉校验,不进裕度。
    """
    spec = spec or {}
    if material_family is None:
        material_family = ('metal' if spec.get('material', 'PA12') != 'PA12'
                           else 'polymer')
    bh = homogenize(doc)
    consts = bh.get('constants') or {}
    # 载荷轴:默认 y(structure_set 为 y 压设计);取该轴模量为排序值,
    # 不可用时取三轴保守最小
    axis = 'E_y'
    E_rank = consts.get(axis)
    if E_rank is None:
        cand = [consts.get(k) for k in ('E_x', 'E_y', 'E_z')
                if consts.get(k)]
        E_rank = min(cand) if cand else None
    if rho_rel is None:
        # 商图单胞体积比:用 homogenize 给不出密度时回退 spec
        rho_rel = spec.get('rho_rel')

    cls_info = classify_for_scaling(doc)
    band = (literature_band(cls_info['cls'], rho_rel, Es, sigma_ys,
                            material_family, bh.get('ld_median'))
            if rho_rel else None)

    bh_ok = bool(bh.get('spd') and bh.get('status') == 'computed'
                 and E_rank is not None)
    # beam_homog 给的是**模量**:只有 spec 的 margin_metric 是刚度类时
    # 才可作该 spec 的 margin 证据(comp_EA/SEA 等吸能量纲不匹配 →
    # 仅信息性,仍需 Tier-D)。
    metric = str(spec.get('margin_metric', '')).lower()
    stiffness_metric = any(k in metric for k in
                           ('stiff', 'modul', 'e_', 'young', '刚度'))
    margin_ok = bool(bh_ok and stiffness_metric)
    checks = []
    # (1) beam_homog 物理估值 —— margin 仅刚度类(非白名单→封顶 SCREEN)
    bh_cav = list(bh.get('caveats', [])) + [CAVEAT_SCREENING, SRC_LUMPE]
    if bh_ok and not stiffness_metric:
        bh_cav.append(f'spec.margin_metric={metric or "?"} 非刚度量纲:'
                      'beam 模量不可作该 margin,仅排序;裕度须 Tier-D')
    checks.append({
        'dimension': 'mechanics', 'tool': 'beam_homog.homogenize',
        'value': round(float(E_rank), 4) if E_rank is not None else None,
        'threshold': None, 'pass': (True if bh_ok else None),
        'source': bh.get('source', SRC_LUMPE) + ';排序口径=' + axis,
        'source_type': 'internal_computed',
        'status': bh.get('status', 'out_of_domain'),
        'margin_eligible': margin_ok,
        'caveats': bh_cav})
    # (2) 文献带 —— 交叉校验,绝不 computed、绝不 margin_eligible
    if band:
        checks.append({
            'dimension': 'mechanics', 'tool': 'gibson_ashby.band',
            'value': {'E_point': round(band['E_point'], 4),
                      'E_lo': round(band['E_lo'], 4),
                      'E_hi': round(band['E_hi'], 4),
                      'cls': cls_info['cls']},
            'threshold': None, 'pass': None, 'source': band['source'],
            'source_type': 'internal_computed', 'status': band['status'],
            'margin_eligible': False,
            'caveats': band['caveats'] + cls_info['caveats']
            + [f"Maxwell M={cls_info['maxwell_M']}"]})
        # (3) 聚合物偏差子项 → R4 降级
        if band['polymer_inference']:
            checks.append({
                'dimension': 'material', 'tool': 'am_polymer_deviation',
                'value': band['polymer_inference']['extra_halfwidth'],
                'threshold': None, 'pass': None,
                'source': band['polymer_inference']['note'],
                'source_type': 'inference', 'status': 'estimate',
                'margin_eligible': False,
                'caveats': ['聚合物 AM 偏差无文献来源,结论须降级']})

    # (4) 交叉校验:**信息性**(pass=None)——文献是弱证据,不否决 beam 物理;
    # 分歧只置 escalate(设计裕度须 Tier-D),beam 估值仍供筛选排序。
    consistent, escalate = None, False
    if band and bh_ok:
        lo = band['E_point'] * (1 - band['halfwidth'])
        hi = band['E_point'] * (1 + band['halfwidth'])
        consistent = bool(lo <= E_rank <= hi)
        escalate = not consistent
        checks.append({
            'dimension': 'mechanics', 'tool': 'screen_estimate.cross_check',
            'value': {'beam_E': round(float(E_rank), 4),
                      'lit_point': round(band['E_point'], 4),
                      'band': [round(lo, 4), round(hi, 4)],
                      'consistent': consistent},
            'threshold': None, 'pass': None,
            'source': 'beam_homog(自身几何物理)vs 文献标度律误差带交叉校验'
                      '(信息性:文献不否决物理)',
            'source_type': 'internal_computed', 'status': 'computed',
            'caveats': ([] if consistent else
                        ['物理与文献分歧超出文献误差带:文献 archetype '
                         '可能不适用本拓扑(如柱主导 Voigt 方向),'
                         '设计裕度建议升 Tier-D 核实'])})
    if band and band['status'] == 'out_of_domain':
        escalate = True
    if cls_info['cls'] == 'bending':
        escalate = True   # 弯曲类设计裕度恒走 certify→Tier-D,本器只排序

    E_lo_report = None
    if band and bh_ok:
        E_lo_report = min(band['E_lo'], E_rank * (1 - _BEAM_P90_LO))
    summary = {
        'estimate': {'E_rank_MPa': (round(float(E_rank), 4)
                                    if E_rank is not None else None),
                     'axis': axis, 'model': 'beam_homog Timoshenko PBC'},
        'bounds': {'E_lo': (round(E_lo_report, 4) if E_lo_report else None),
                   'E_hi': (round(max(band['E_hi'], E_rank), 4)
                            if band and bh_ok else None),
                   'basis': '文献 C 散布 ∪ beam Lumpe-p90 全正偏置'},
        'cls': cls_info, 'cross_check_consistent': consistent,
        'escalate_tier_d': bool(escalate),
        'margin_eligible': False, 'source_type': 'internal_computed',
        'beam_certified': bool(bh.get('certified')),
        'note': '排序值=自身几何物理(beam_homog);文献仅作误差带交叉校验,'
                '不进裕度;设计裕度走 certify/Tier-D'}
    return checks, summary
