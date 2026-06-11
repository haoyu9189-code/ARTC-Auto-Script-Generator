"""P3-B D2:真子代理派发的文件协议层(Orchestrator = 主会话)。

协议(与 .claude/agents/*.md 合同对应):
1. atlas-generator 子代理 → `<case>/candidates.json`(本模块不生成候选)
2. verify_case():candidates + spec → verify_batch →
   `<case>/checks/<cid>.json` + `<case>/timings.json`
   (stage 级 perf_counter 计时 —— P3-C 基准仪表的前身)
3. atlas-evaluator 子代理读 checks 文件、Bash 调确定性引擎 →
   `<case>/traces_agent/<cid>.json`
4. judge_direct() + compare_traces():主会话直跑引擎 ↔ 子代理产物
   对照 —— 引擎确定性 ⇒ verdict/margin/downgrades 应全等;不等即
   说明 agent 在搬运证据时改写了数字(R 系列要防的事)。

诚实记录:verify_batch 目前无 TPMS 网格路径(D2 实跑发现的缺口),
tpms 候选落 out_of_domain 检查项而非假装验证。
"""
import json
import os
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas.evaluator.core import judge
from atlas.orchestration.verify import verify_batch

D2_ROOT = os.path.join(_ROOT, 'atlas', 'reports', 'D2')


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _tpms_gap_checks(candidate):
    """TPMS 候选的诚实占位:验证管线缺口,不假装验证过。"""
    return [{
        'dimension': 'gates', 'tool': 'verify.geometry_support',
        'value': 'tpms', 'threshold': None, 'pass': False,
        'source': 'atlas.orchestration.verify._geometry_mesh 无 TPMS '
                  '网格路径(D2 实跑发现,归 Phase 3 backlog)',
        'source_type': 'internal_computed', 'status': 'out_of_domain',
        'caveats': ['候选几何本身合法(B2 定标管线水密),仅验证扇出不支持'],
    }]


def verify_case(case_dir, db_path=None):
    """candidates.json + spec.json → checks/<cid>.json + timings.json。"""
    spec = _load(os.path.join(case_dir, 'spec.json'))['spec']
    cands = _load(os.path.join(case_dir, 'candidates.json'))['candidates']
    supported = [c for c in cands if 'tpms' not in c.get('geometry', {})]
    tpms = [c for c in cands if 'tpms' in c.get('geometry', {})]

    t0 = time.perf_counter()
    results = verify_batch(supported, spec, db_path=db_path)
    t_verify = time.perf_counter() - t0
    for c in tpms:
        results.append({'candidate': c, 'checks': _tpms_gap_checks(c)})

    for r in results:
        _dump({'candidate_id': r['candidate']['id'],
               'tier': str(r['candidate'].get('tier', '1')),
               'checks': r['checks']},
              os.path.join(case_dir, 'checks',
                           f"{r['candidate']['id']}.json"))
    timings = {'n_candidates': len(cands),
               'n_tpms_gap': len(tpms),
               'verify_batch_s': round(t_verify, 3),
               'source': 'time.perf_counter(P3-C 仪表前身)'}
    _dump(timings, os.path.join(case_dir, 'timings.json'))
    return timings


def judge_direct(case_dir):
    """主会话直跑引擎 → traces_direct/<cid>.json(对照组)。"""
    spec = _load(os.path.join(case_dir, 'spec.json'))['spec']
    cdir = os.path.join(case_dir, 'checks')
    out = []
    t0 = time.perf_counter()
    for fn in sorted(os.listdir(cdir)):
        c = _load(os.path.join(cdir, fn))
        t = judge(c['candidate_id'], c['tier'], c['checks'], spec,
                  n_cells=spec.get('n_cells'))
        _dump(t, os.path.join(case_dir, 'traces_direct', fn))
        out.append(t)
    elapsed = time.perf_counter() - t0
    return {'n': len(out), 'judge_direct_s': round(elapsed, 3),
            'verdicts': {t['candidate_id']: t['verdict'] for t in out}}


_KEYS = ('verdict', 'verdict_reasons', 'downgrades', 'margin',
         'confidence_level')


def compare_traces(case_dir):
    """traces_agent/ ↔ traces_direct/ 逐字段对照(确定性 ⇒ 应全等)。"""
    a_dir = os.path.join(case_dir, 'traces_agent')
    d_dir = os.path.join(case_dir, 'traces_direct')
    report = {'identical': [], 'mismatched': [], 'missing_agent': []}
    for fn in sorted(os.listdir(d_dir)):
        ap = os.path.join(a_dir, fn)
        if not os.path.exists(ap):
            report['missing_agent'].append(fn)
            continue
        a, d = _load(ap), _load(os.path.join(d_dir, fn))
        diff = {k: {'agent': a.get(k), 'direct': d.get(k)}
                for k in _KEYS if a.get(k) != d.get(k)}
        if diff:
            report['mismatched'].append({'file': fn, 'diff': diff})
        else:
            report['identical'].append(fn)
    report['consistent'] = (not report['mismatched']
                            and not report['missing_agent'])
    _dump(report, os.path.join(case_dir, 'consistency.json'))
    return report
