"""C3:K=3 重生回路(Evaluator-Optimizer,CAX 恢复阶梯)。

阶梯(RESEARCH 决策,CAX-Agent 实证 69%→93% 完成率):
  round 1 确定性参数修补(便宜,不动拓扑)
  round 2 LLM 重生成(Generator 重新发散,带失败原因)
  round 3 上下文增强重生成(带全部历史 + 文献检索提示)
K 耗尽 → 不硬憋结果,输出全部候选 trace 的 Pareto 前沿 + 未满足项
(HANDOFF §4:重生预算 K=3,超出报 Pareto 前沿)。

文件计数器:回路状态落盘 JSON(防跨会话重复烧预算)。
回调注入式设计:judge_fn 默认 = C2 确定性引擎;regenerate_fn 在生产中
由 Orchestrator 调 atlas-generator subagent,测试中注入桩。
"""
import json
import os

LADDER = ('param_repair', 'regenerate', 'context_enrich')


def default_param_repair(candidate, trace, spec):
    """确定性参数修补:只动连续参数,不动拓扑。修不了返回 None。"""
    reasons = ' '.join(trace.get('verdict_reasons', []))
    geo = dict(candidate.get('geometry', {}))
    repaired = False
    # margin 不足 → 加密度/半径(一阶 ρ∝r²:margin 缺口按比例放大 r)
    if 'margin' in reasons and trace.get('margin'):
        ratio = trace['margin']['ratio']
        if ratio > 0:
            scale = min(1.5, (1.05 / ratio) ** 0.5)
            geo['radius_mm'] = round(geo.get('radius_mm', 0.5) * scale, 4)
            repaired = True
    # DfAM 杆径不足 → 抬到工艺下限(含实测节点削薄补偿)
    # 注意:C2 引擎对该失败的 reason 实文是「硬性检查未过: printability/
    # printability.measure_min_feature」——D2 真跑发现原匹配词
    # ('杆径'/'min_strut')对不上引擎口径,修补从未触发(P3-B 修复)。
    if ('杆径' in reasons or 'min_strut' in reasons
            or 'measure_min_feature' in reasons):
        from atlas.printability import load_dfam_rules
        process = spec.get('process', 'MJF')
        min_d = load_dfam_rules()[process]['min_strut_diameter_mm']['value']
        base = geo.get('radius_mm', 0.5)
        measured = None
        for ch in trace.get('checks', []):
            if (ch.get('tool', '').endswith('measure_min_feature')
                    and isinstance(ch.get('value'), dict)):
                measured = ch['value'].get('min_mm')
        # 名义直径 2r 与射线实测 min 的差 = 节点削薄,修补时一并补偿
        thinning = max(0.0, 2 * base - measured) if measured else 0.0
        geo['radius_mm'] = round(
            max(base, (min_d + thinning) / 2 + 0.01), 4)
        repaired = True
    if not repaired:
        return None
    new = dict(candidate)
    new['geometry'] = geo
    new['lineage'] = dict(candidate.get('lineage', {}),
                          parents=[candidate.get('id', '?')],
                          notes=['round-1 确定性参数修补'])
    return new


def pareto_front(entries, maximize=('margin_ratio',),
                 minimize=('rho_rel',)):
    """非支配集。entries: [{'margin_ratio':…, 'rho_rel':…, …}]"""
    def dominates(a, b):
        ge = all(a.get(k, -1e18) >= b.get(k, -1e18) for k in maximize) \
            and all(a.get(k, 1e18) <= b.get(k, 1e18) for k in minimize)
        gt = any(a.get(k, -1e18) > b.get(k, -1e18) for k in maximize) \
            or any(a.get(k, 1e18) < b.get(k, 1e18) for k in minimize)
        return ge and gt
    return [e for e in entries
            if not any(dominates(o, e) for o in entries if o is not e)]


class RegenerationLoop:
    """K=3 重生回路驱动器。"""

    def __init__(self, evaluate_fn, regenerate_fn=None,
                 param_repair_fn=default_param_repair, k_max=3,
                 state_path=None):
        """evaluate_fn(candidate, spec, round_idx) -> trace(合 schema);
        regenerate_fn(failed, spec, history, enriched) -> [candidate]。"""
        self.evaluate_fn = evaluate_fn
        self.regenerate_fn = regenerate_fn
        self.param_repair_fn = param_repair_fn
        self.k_max = int(k_max)
        self.state_path = state_path

    def _save_state(self, state):
        if self.state_path:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=1)

    def run(self, candidates, spec):
        all_traces = []
        rounds_log = []
        state = {'round': 0, 'ladder': [], 'k_max': self.k_max}

        def evaluate_all(cands, round_idx):
            out = []
            for c in cands:
                t = self.evaluate_fn(c, spec, round_idx)
                t['regeneration_round'] = round_idx
                all_traces.append({'candidate': c, 'trace': t})
                out.append((c, t))
            return out

        current = evaluate_all(candidates, 0)
        passed = [(c, t) for c, t in current
                  if t['verdict'] in ('PASS', 'SCREENING_PASS')]
        failed = [(c, t) for c, t in current if t['verdict'] == 'FAIL']

        for round_idx in range(1, self.k_max + 1):
            if not failed:
                break
            stage = LADDER[min(round_idx - 1, len(LADDER) - 1)]
            state['round'] = round_idx
            state['ladder'].append(stage)
            rounds_log.append({'round': round_idx, 'stage': stage,
                               'n_failed_in': len(failed)})
            if stage == 'param_repair':
                new = [r for c, t in failed
                       if (r := self.param_repair_fn(c, t, spec))]
            else:
                if self.regenerate_fn is None:
                    new = []
                else:
                    history = [{'id': c.get('id'),
                                'reasons': t['verdict_reasons']}
                               for c, t in failed]
                    new = self.regenerate_fn(
                        [c for c, _ in failed], spec, history,
                        enriched=(stage == 'context_enrich'))
            if not new:
                continue
            current = evaluate_all(new, round_idx)
            passed += [(c, t) for c, t in current
                       if t['verdict'] in ('PASS', 'SCREENING_PASS')]
            failed = [(c, t) for c, t in current if t['verdict'] == 'FAIL']
        self._save_state(state)

        result = {'rounds': rounds_log,
                  'ladder_executed': state['ladder'],
                  'n_traces': len(all_traces),
                  'all_traces': all_traces,
                  'passed': [{'candidate': c, 'trace': t}
                             for c, t in passed]}
        if passed:
            result['outcome'] = 'PASS'
        else:
            # K 耗尽:Pareto 前沿(margin 最大化 × 密度最小化)+ 全 trace
            entries = []
            for item in all_traces:
                t = item['trace']
                entries.append({
                    'candidate_id': t['candidate_id'],
                    'margin_ratio': (t.get('margin') or {}).get('ratio',
                                                                float('-inf')),
                    'rho_rel': item['candidate'].get('rho_rel',
                                                     float('inf')),
                    'trace': t})
            result['outcome'] = 'PARETO'
            result['pareto_front'] = pareto_front(entries)
            result['unmet'] = sorted({r for item in all_traces
                                      for r in item['trace']
                                      ['verdict_reasons']})
        return result
