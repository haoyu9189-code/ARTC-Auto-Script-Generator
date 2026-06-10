"""D1:三案例端到端验收(LPBF 支架 / SLS 吸能块 / MJF auxetic 垫)。

全链:候选(Tier-1 库内 + MJF 案例带一个 Tier-2 新图)→ verify_batch
四维扇出 → C2 judge → 中文报告(裕度列/trace/三类来源/免责页脚)。
audit_report 做红线自动审计(违例即测试失败)。

诚实声明:margin 用库内 comp_EA 同单位代理(CSV 特征,绝对单位映射
待 P2-5 标定),报告内显式标注;LPBF 航空支架属高风险场景,全文标
「仅作筛选」。
"""
import os

from atlas.evaluator import judge
from atlas.orchestration.verify import verify_batch

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
REPORTS_DIR = os.path.join(_ROOT, 'atlas', 'reports', 'D1')

DISCLAIMER = ('本报告为计算与数据库辅助选型,最终设计须经实物压缩测试'
              '验证。')
HIGH_RISK_TAG = ('⚠️ 高风险场景(航空结构件):本报告输出仅作筛选,'
                 '不得直接用于定型设计。')

NOVEL_GRAPH = {
    'schema': 'atlas-cell-graph/1.0', 'name': 'cubic_plus_diagonal',
    'cell': {'size_mm': 5.0},
    'nodes': [{'id': 'A', 'frac': [0.0, 0.0, 0.0]},
              {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
    'edges': [{'n1': 'A', 'n2': 'A', 'shift': [1, 0, 0]},
              {'n1': 'A', 'n2': 'A', 'shift': [0, 1, 0]},
              {'n1': 'A', 'n2': 'A', 'shift': [0, 0, 1]},
              {'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
              {'n1': 'B', 'n2': 'A', 'shift': [1, 1, 1]}],
    'default_radius_mm': 0.5, 'free_params': {},
    'lineage': {'tier': 'tier2',
                'generator': 'atlas-generator(演示)',
                'source': 'D1 验收案例'},
}

CASES = [
    {
        'key': 'lpbf_bracket',
        'title': 'LPBF AlSi10Mg 航空支架点阵填充',
        'high_risk': True,
        'spec': {'process': 'LPBF', 'material': 'AlSi10Mg', 'n_cells': 3,
                 'fos_already_applied': True, 'fos': 1.5,
                 'confidence_level': 'screening',
                 'margin_metric': 'comp_EA(库内同单位代理)',
                 'design_value_with_fos': 60.0},
        'candidates': [
            {'id': 'lp1', 'tier': '1',
             'geometry': {'topology': 'Octet_truss', 'slider': 4,
                          'radius_mm': 0.55}},
            {'id': 'lp2', 'tier': '1',
             'geometry': {'topology': 'FCCZ', 'slider': 4,
                          'radius_mm': 0.55}},
            {'id': 'lp3', 'tier': '1',
             'geometry': {'topology': 'Kelvin', 'slider': 4,
                          'radius_mm': 0.55}},
        ],
    },
    {
        'key': 'sls_absorber',
        'title': 'SLS PA12 吸能缓冲块',
        'high_risk': False,
        'spec': {'process': 'SLS', 'material': 'PA12', 'n_cells': 4,
                 'fos_already_applied': True, 'fos': 1.3,
                 'confidence_level': 'screening',
                 'margin_metric': 'comp_EA(库内同单位代理)',
                 'design_value_with_fos': 55.0},
        'candidates': [
            {'id': 'sa1', 'tier': '1',
             'geometry': {'topology': 'BCC', 'slider': 4,
                          'radius_mm': 0.5}},
            {'id': 'sa2', 'tier': '1',
             'geometry': {'topology': 'Diamond', 'slider': 4,
                          'radius_mm': 0.5}},
            {'id': 'sa3', 'tier': '1',
             'geometry': {'topology': 'G7', 'slider': 4,
                          'radius_mm': 0.5}},
        ],
    },
    {
        'key': 'mjf_auxetic_pad',
        'title': 'MJF PA12 auxetic 缓冲垫',
        'high_risk': False,
        'spec': {'process': 'MJF', 'material': 'PA12', 'n_cells': 2,
                 'fos_already_applied': True, 'fos': 1.3,
                 'confidence_level': 'screening',
                 'margin_metric': 'comp_EA(库内同单位代理)',
                 'design_value_with_fos': 40.0},
        'candidates': [
            {'id': 'ax1', 'tier': '1',
             'geometry': {'topology': 'Auxetic', 'slider': 4,
                          'radius_mm': 0.5}},
            {'id': 'ax2', 'tier': '1',
             'geometry': {'topology': 'CBCC', 'slider': 4,
                          'radius_mm': 0.5}},
            {'id': 'ax3', 'tier': '2',
             'geometry': {'graph_doc': NOVEL_GRAPH}},
        ],
    },
]

_SOURCE_BUCKETS = (('academic_doi', '学术文献(DOI)'),
                   ('vendor', '厂商标准/数据表'),
                   ('internal_fea', '内部 FEA 数据库'),
                   ('internal_computed', '内部确定性计算'),
                   ('inference', '标记推测(inference,已降级)'))


def run_case(case, db_path=None):
    spec = case['spec']
    results = verify_batch(case['candidates'], spec, db_path=db_path)
    judged = []
    for r in results:
        t = judge(r['candidate']['id'],
                  str(r['candidate'].get('tier', '1')),
                  r['checks'], spec, n_cells=spec.get('n_cells'))
        judged.append({'candidate': r['candidate'], 'trace': t})
    return judged


def render_report(case, judged):
    spec = case['spec']
    L = []
    L.append(f"# ATLAS 选型报告:{case['title']}")
    L.append('')
    if case['high_risk']:
        L.append(HIGH_RISK_TAG)
        L.append('')
    L.append(f"工艺/材料:{spec['process']} / {spec['material']};"
             f"阵列 n={spec['n_cells']};FoS={spec['fos']}"
             f"(**设计值已含 FoS,margin = pred/design,"
             f"任何环节不再二次乘**);置信度等级:"
             f"{spec['confidence_level']}(筛选级)。")
    L.append('')
    L.append('搜索范围:候选在 cell DB(5,304 结构)+ 生成层内比较,'
             '推荐为 **database-wide(数据库范围内)最优**,'
             '不主张绝对全局最优。')
    L.append('')
    # ---- 推荐表(裕度列) ----
    L.append('## 推荐表')
    L.append('')
    L.append('| 候选 | Tier | 拓扑 | ρ̄(实算) | margin(pred/design) '
             '| 判决 |')
    L.append('|------|------|------|----------|---------------------|------|')
    for item in judged:
        c, t = item['candidate'], item['trace']
        geo = c.get('geometry', {})
        topo = geo.get('topology') or geo.get('graph_doc', {}).get(
            'name', '?')
        rho = next((ch['value'] for ch in t['checks']
                    if ch['dimension'] == 'density'), None)
        m = t.get('margin')
        m_str = (f"{m['ratio']:.2f}" if m else '无可用证据')
        L.append(f"| {t['candidate_id']} | Tier-{t['tier']} | {topo} | "
                 f"{rho if rho is not None else '—'} | {m_str} | "
                 f"{t['verdict']} |")
    L.append('')
    L.append(f"margin 度量:{spec['margin_metric']},设计值(含 FoS)= "
             f"{spec['design_value_with_fos']}。"
             '注:库内 comp_EA 的绝对单位映射待 P2-5 标定,'
             '本列为同单位代理比较(source_type=inference 级别的'
             '单位假设,已降级)。')
    L.append('')
    if not any(item['trace']['verdict'] in ('PASS', 'SCREENING_PASS')
               for item in judged):
        L.append('**结论:本轮无候选通过全部硬性检查**(详见各候选判决'
                 '依据)。系统如实报告而非硬选:典型出路 = ① 接受支撑'
                 '结构并复核排粉;② 换粉末床聚合物工艺(SLS/MJF 无悬垂'
                 '约束);③ Phase 2 自支撑拓扑定向生成(45° 准则前置'
                 '喂给 Generator)。')
        L.append('')
    # ---- 验证 trace ----
    L.append('## 验证 trace(每个数字可溯源)')
    for item in judged:
        t = item['trace']
        L.append('')
        L.append(f"### 候选 {t['candidate_id']}(Tier-{t['tier']})")
        L.append('')
        L.append('| 维度 | 工具 | 值 | 通过 | 来源 |')
        L.append('|------|------|----|------|------|')
        for ch in t['checks']:
            val = ch['value']
            if isinstance(val, dict):
                val = '; '.join(f'{k}={v}' for k, v in list(val.items())[:3])
            p = {True: '✓', False: '✗', None: 'ℹ️'}[ch['pass']]
            src = ch['source'][:60]
            L.append(f"| {ch['dimension']} | {ch['tool']} | {val} | {p} "
                     f"| {src} |")
        if t['verdict_reasons']:
            L.append('')
            L.append('判决依据:' + ';'.join(t['verdict_reasons']))
        if t['downgrades']:
            L.append('')
            L.append('降级记录:' + ';'.join(t['downgrades']))
        # 倾向性表述纪律
        mx = next((ch for ch in t['checks']
                   if ch['dimension'] == 'topology_tendency'), None)
        if mx and isinstance(mx['value'], dict):
            L.append('')
            L.append(f"拓扑倾向(Maxwell,必要非充分,只说倾向):"
                     f"M={mx['value'].get('maxwell_M')},"
                     f"{mx['value'].get('tendency')}")
    # ---- 三类来源 ----
    L.append('')
    L.append('## 来源清单(三类分列)')
    buckets = {k: set() for k, _ in _SOURCE_BUCKETS}
    for item in judged:
        for ch in item['trace']['checks']:
            st = ch.get('source_type', 'internal_computed')
            buckets.setdefault(st, set()).add(ch['source'])
    for key, label in _SOURCE_BUCKETS:
        if buckets.get(key):
            L.append('')
            L.append(f'### {label}')
            for s in sorted(buckets[key]):
                L.append(f'- {s}')
    # ---- caveats + 页脚 ----
    L.append('')
    L.append('## 适用域与警示')
    n = spec.get('n_cells', 1)
    if n < 3:
        L.append(f'- n={n} < 3:尺寸效应强警示(1→3 胞跳变最剧烈),'
                 '建议 n≥3 或实测。')
    L.append('- Tier-2 候选(如有)为库外生成,其力学结论为 screening '
             'only,待物理计算裁判(Phase 2 beam-FEM / Tier-D FEA);'
             '与 Tier-1 检索结论分层呈现,不混叙。')
    L.append('- 动态/剪切维度仅报数据可用性,验证成熟度属 Phase 2/3。')
    L.append('')
    L.append('---')
    L.append(DISCLAIMER)
    if case['high_risk']:
        L.append('')
        L.append(HIGH_RISK_TAG)
    return '\n'.join(L) + '\n'


def audit_report(text, high_risk):
    """红线自动审计:返回违例列表(空 = 过)。"""
    violations = []
    if DISCLAIMER not in text:
        violations.append('缺实测免责页脚')
    if '全局最优' in text and 'database-wide' not in text \
            and '数据库范围内' not in text:
        violations.append('全局最优缺 database-wide 限定')
    if '二次乘' not in text:
        violations.append('缺 margin 已含 FoS 不二次乘声明')
    if high_risk and '仅作筛选' not in text:
        violations.append('高风险场景缺「仅作筛选」标注')
    # Maxwell 只说倾向:出现判定式措辞即违例
    for banned in ('判定为 stretch', '判定为 bending', 'Maxwell 判定'):
        if banned in text:
            violations.append(f'Maxwell 判定式措辞: {banned}')
    if 'Tier-2' in text and '分层' not in text and 'screening' not in text:
        violations.append('Tier-2 内容缺分层/screening 标注')
    return violations


def run_all(db_path=None, out_dir=REPORTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    outputs = {}
    for case in CASES:
        judged = run_case(case, db_path=db_path)
        report = render_report(case, judged)
        path = os.path.join(out_dir, f"{case['key']}.md")
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(report)
        outputs[case['key']] = {'judged': judged, 'report_path': path,
                                'violations': audit_report(
                                    report, case['high_risk'])}
    return outputs


if __name__ == '__main__':
    for key, out in run_all().items():
        verdicts = [j['trace']['verdict'] for j in out['judged']]
        print(f"{key}: verdicts={verdicts} violations="
              f"{out['violations']} -> {out['report_path']}")
