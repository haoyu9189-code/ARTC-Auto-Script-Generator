"""C4 单测:四并行验证扇出 ~30s、证据进 Evaluator、OOD 不发最近邻。"""
import time

import pytest

from atlas.data import ingest_cell_db as ing
from atlas.evaluator import judge
from atlas.orchestration.verify import verify_batch, verify_candidate


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    p = tmp_path_factory.mktemp('verifydb') / 'cell_db.sqlite'
    ing.build(db_path=str(p))
    return str(p)


SPEC = {'process': 'MJF', 'material': 'PA12', 'n_cells': 1,
        'fos_already_applied': True, 'confidence_level': 'screening',
        'margin_metric': 'EA_proxy', 'design_value_with_fos': 50.0}


def cands():
    out = []
    for i, (topo, r) in enumerate([('BCC', 0.5), ('FCC', 0.45),
                                   ('Octet_truss', 0.4), ('Kelvin', 0.5),
                                   ('Diamond', 0.45), ('AFCC', 0.4)]):
        out.append({'id': f'c{i}', 'tier': '1', 'rho_rel': None,
                    'geometry': {'topology': topo, 'slider': 4,
                                 'radius_mm': r}})
    return out


def test_batch_fanout_six_candidates_under_30s(db):
    t0 = time.perf_counter()
    results = verify_batch(cands(), SPEC, db_path=db)
    dt = time.perf_counter() - t0
    assert dt < 30.0, f'6 候选四维扇出 {dt:.1f}s 超预算'
    assert len(results) == 6
    for r in results:
        dims = {c['dimension'] for c in r['checks']}
        assert {'printability', 'mechanics', 'density', 'material',
                'size_effect'} <= dims
        for c in r['checks']:
            assert c['source'], f"缺 source: {c['tool']}"


def test_checks_feed_evaluator_and_db_margin_passes(db):
    r = verify_batch(cands()[:1], SPEC, db_path=db)[0]
    trace = judge(r['candidate']['id'], '1', r['checks'], SPEC)
    assert trace['verdict'] in ('PASS', 'SCREENING_PASS', 'FAIL')
    # BCC r=0.5 在库内,最近邻 comp_EA 是 internal_fea 白名单证据
    nn = [c for c in r['checks']
          if c['tool'].startswith('retriever.nearest')]
    assert nn and nn[0]['applicability_distance'] is not None
    assert trace['margin']['ratio'] > 0
    if trace['verdict'] == 'PASS':
        assert 'internal_fea' == nn[0]['source_type']


def test_dynamic_availability_is_informational(db):
    checks = verify_candidate(cands()[0], SPEC, db_path=db)
    dyn = next(c for c in checks
               if c['tool'] == 'dynamic_data_availability')
    assert dyn['pass'] is None  # informational,不构成验证
    assert any('成熟度' in c for c in dyn['caveats'])
    assert isinstance(dyn['value'], int)


def test_ood_candidate_gets_no_nearest_neighbor_call(db):
    novel = {'id': 'x1', 'tier': '2',
             'geometry': {'graph_doc': {
                 'schema': 'atlas-cell-graph/1.0', 'name': 'novel_x',
                 'cell': {'size_mm': 5.0},
                 'nodes': [{'id': 'A', 'frac': [0.0, 0.0, 0.0]},
                           {'id': 'B', 'frac': [0.5, 0.5, 0.5]}],
                 'edges': [
                     {'n1': 'A', 'n2': 'A', 'shift': [1, 0, 0]},
                     {'n1': 'A', 'n2': 'A', 'shift': [0, 1, 0]},
                     {'n1': 'A', 'n2': 'A', 'shift': [0, 0, 1]},
                     {'n1': 'A', 'n2': 'B', 'shift': [0, 0, 0]},
                     {'n1': 'B', 'n2': 'A', 'shift': [1, 1, 1]}],
                 'default_radius_mm': 0.5, 'free_params': {},
                 'lineage': {'tier': 'tier2', 'generator': 't',
                             'source': 't'}}}}
    checks = verify_candidate(novel, SPEC, db_path=db)
    assert not any('nearest' in c['tool'] for c in checks)  # 连请求都不发
    dims = {c['dimension'] for c in checks}
    assert 'printability' in dims and 'density' in dims


def test_n_cells_warning(db):
    spec2 = dict(SPEC, n_cells=2)
    checks = verify_candidate(cands()[0], spec2, db_path=db)
    se = next(c for c in checks if c['dimension'] == 'size_effect')
    assert any('n<3' in c for c in se['caveats'])
