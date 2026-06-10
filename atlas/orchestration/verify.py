"""C4:四并行验证接线(静态先行)。

verify_batch:候选批量 → 四维度检查(printability / mechanics /
material / size_effect)+ 动态/剪切数据可用性(informational,不吹
验证成熟度)→ 检查数组直接喂 C2 judge。生产中四维度由 background
subagents 承载;本模块是其确定性核心(同一套仓内工具),也是 D1
端到端验收的执行层。

并行:ThreadPoolExecutor 按候选扇出(B1 单候选 <5s,8 候选 4 线程
预算 ~30s 内)。OOD 纪律:tier 2/1.75 不调用最近邻(连请求都不发,
Evaluator R6 是兜底)。
"""
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SKILL_SCRIPTS = os.path.join(_ROOT, '.claude', 'skills', 'atlas',
                              'scripts')
if _SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, _SKILL_SCRIPTS)


def _chk(dimension, tool, value, passed, source, status='computed',
         **kw):
    c = {'dimension': dimension, 'tool': tool, 'value': value,
         'pass': passed, 'status': status, 'source': source}
    c.update(kw)
    return c


def _envelope_to_check(dimension, tool, env):
    """physics_common / printability 信封 → trace check。"""
    return _chk(dimension, tool, env.get('value'),
                env.get('pass', None) if 'pass' in env
                else (env.get('status') == 'computed' or None),
                env['source'], status=env.get('status', 'computed'),
                caveats=env.get('caveats', []),
                threshold=env.get('threshold'))


def _geometry_mesh(candidate):
    from atlas.geometry import generate_cell
    from atlas.geometry.realize_graph import realize_graph
    geo = candidate.get('geometry', {})
    if 'graph_doc' in geo:
        r = realize_graph(geo['graph_doc'])
        if not r.ok:
            return None, r.to_trace()
        return r.mesh, None
    cm = generate_cell(geo['topology'], slider=int(geo.get('slider', 4)),
                       radius=geo['radius_mm'])
    return cm, None


def verify_candidate(candidate, spec, db_path=None):
    """单候选四维度 + 可用性检查。返回 checks 列表(喂 judge)。"""
    from atlas.printability import (validate_mesh, measure_min_feature,
                                    check_overhangs, check_powder_escape)
    import gibson_ashby
    import maxwell_check
    process = spec.get('process', 'MJF')
    tier = str(candidate.get('tier', '1'))
    checks = []

    mesh_obj, fail_trace = _geometry_mesh(candidate)
    if fail_trace is not None:
        return [_chk('gates', 'realize_graph', fail_trace['reason'],
                     False, fail_trace['source'])]
    mesh = mesh_obj.trimesh
    rho = mesh_obj.volume / (mesh_obj.cell_size * mesh_obj.n) ** 3

    # ---- printability(四项,B1 工具) ----
    checks.append(_envelope_to_check('printability',
                                     'printability.validate_mesh',
                                     validate_mesh(mesh, process)))
    checks.append(_envelope_to_check('printability',
                                     'printability.measure_min_feature',
                                     measure_min_feature(mesh, process)))
    checks.append(_envelope_to_check('printability',
                                     'printability.check_overhangs',
                                     check_overhangs(mesh, process)))
    checks.append(_envelope_to_check('printability',
                                     'printability.check_powder_escape',
                                     check_powder_escape(mesh, process)))

    # ---- mechanics(解析筛 + 库内最近邻,OOD 不发请求) ----
    checks.append(_chk('density', 'rel_density.mesh(manifold3d)',
                       round(rho, 5), 0 < rho < 0.95,
                       'manifold3d watertight 体积 / 胞体积'))
    geo = candidate.get('geometry', {})
    topology = geo.get('topology')
    if topology:
        from atlas.data.ingest_cell_db import classify
        from atlas.geometry import parse_structure
        cls = classify(topology)
        mat = ('metal' if spec.get('material', 'PA12') != 'PA12'
               else 'polymer')
        ga = gibson_ashby.estimate(cls, rho, 1700.0, 45.0,
                                   material_family=mat)
        c = _envelope_to_check('mechanics',
                               'gibson_ashby.estimate', ga)
        c['source_type'] = 'internal_computed'  # 解析筛,R7 非白名单
        checks.append(c)
        coords, cyls = parse_structure(topology, int(geo.get('slider', 4)))
        mx = maxwell_check.check(len(cyls), len(coords))
        checks.append(_envelope_to_check('topology_tendency',
                                         'maxwell_check', mx))
    if tier in ('1', '1.5') and topology:
        from atlas.retriever.core import nearest_by_density, get_structure
        nn = nearest_by_density(topology, rho, k=1, db_path=db_path)
        if not nn.get('rejected') and nn['rows']:
            row = nn['rows'][0]
            full = get_structure(row['sample_name'], db_path=db_path)
            ea = next((f for f in full.get('features', [])
                       if f['feature'] == 'comp_EA'
                       and f['value'] is not None), None)
            if ea:
                checks.append(_chk(
                    'mechanics', 'retriever.nearest_by_density+comp_EA',
                    ea['value'], True, ea['source'],
                    source_type='internal_fea', margin_eligible=True,
                    applicability_distance=row['density_distance'],
                    caveats=['库内最近邻实测值;'
                             f"密度距离 {row['density_distance']:.4f}"]))

    # ---- material(阈值表,inference 自动降级演示) ----
    import json as _json
    props_path = os.path.join(_ROOT, '.claude', 'skills', 'atlas',
                              'references', 'thresholds',
                              'material_props.json')
    props = _json.load(open(props_path, encoding='utf-8'))
    key = ('PA12_MJF' if spec.get('material', 'PA12') == 'PA12'
           else 'AlSi10Mg_LPBF')
    es = props[key]['Es_MPa'] if 'Es_MPa' in props[key] \
        else props[key]['Es_GPa']
    checks.append(_chk('material', f'material_props[{key}]',
                       es['value'], True, es['source'],
                       source_type=es['source_type']))
    if key == 'AlSi10Mg_LPBF':
        kd = props[key]['surface_defect_knockdown']
        checks.append(_chk('material', 'surface_defect_knockdown',
                           kd['value'], True, kd['source'],
                           source_type='inference',
                           caveats=[kd['caveat']]))

    # ---- size effect(静态先行:n 警示位;修正引擎 P2 接 corrector) ----
    n_cells = int(spec.get('n_cells', 1))
    checks.append(_chk(
        'size_effect', 'scaling.n_cells_advisory', n_cells, None,
        'Onck/Andrews 2001 边界层机制(atlas/references);'
        '修正引擎接线归 P2', status='computed',
        caveats=(['n<3 强警示:1→3 胞跳变最剧烈,建议 n>=3 或实测']
                 if n_cells < 3 else [])))

    # ---- 动态/剪切(P2-5 升级:近邻真特征值,带源;成熟度仍如实标注) ----
    if topology:
        con = sqlite3.connect(db_path or os.path.join(
            _ROOT, 'atlas', 'data', 'cell_db.sqlite'))
        try:
            n_dyn = con.execute(
                "SELECT COUNT(*) FROM curves c JOIN structures s ON "
                "s.sample_name=c.sample_name WHERE s.topology=? AND "
                "c.load_case IN ('DynaCompre','DynaShear')",
                (topology,)).fetchone()[0]
            dyn_feats = {}
            dyn_src = None
            if tier in ('1', '1.5'):
                row = con.execute(
                    "SELECT f.feature, f.value, f.source FROM features f "
                    "JOIN structures s ON s.sample_name=f.sample_name "
                    "WHERE s.topology=? AND f.feature IN "
                    "('dyna_stiffness','dyna_yield','dyna_peak',"
                    "'shear_peak') AND f.value IS NOT NULL AND "
                    "s.density IS NOT NULL "
                    "ORDER BY ABS(s.density - ?) LIMIT 8",
                    (topology, rho)).fetchall()
                for feat, val, src in row:
                    dyn_feats.setdefault(feat, round(val, 4))
                    dyn_src = src
        finally:
            con.close()
        value = {'n_dynamic_curves': n_dyn}
        value.update(dyn_feats)
        checks.append(_chk(
            'mechanics', 'dynamic_shear_features', value, None,
            dyn_src or 'cell_db.sqlite curves 表',
            caveats=['P2-5 自提特征(近邻库内值,OOD 不提供);'
                     '动态/剪切验证成熟度属 Phase 3,数值供参考'
                     '不入 margin']))
    return checks


def verify_batch(candidates, spec, db_path=None, max_workers=4):
    """并行扇出验证 → [{'candidate','checks'}];与 judge 直接衔接。"""
    def one(c):
        return {'candidate': c,
                'checks': verify_candidate(c, spec, db_path=db_path)}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(one, candidates))
