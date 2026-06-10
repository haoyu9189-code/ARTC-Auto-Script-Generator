"""B8 单测:数值带源/OOD 拒绝/留痕/文本检索/rank-fusion 规则。"""
import json
import sqlite3

import pytest

from atlas.data import ingest_cell_db as ing
from atlas.retriever import core


@pytest.fixture(scope='module')
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp('retr')
    db = str(d / 'cell_db.sqlite')
    log = str(d / 'log.jsonl')
    ing.build(db_path=db)
    return db, log


def test_query_values_match_db_and_carry_source(env):
    db, log = env
    r = core.query_cell_db(topology='AFCC', feature='comp_EA',
                           load_mode='static_compression', limit=5,
                           db_path=db, log_path=log)
    assert r['n_hits'] == 5
    for row in r['rows']:
        assert row['structure_source'] and row['feature_source']
    # 与直查 SQL 数值一致(原样返回)
    con = sqlite3.connect(db)
    v = con.execute("SELECT value FROM features WHERE sample_name=? "
                    "AND feature='comp_EA'",
                    (r['rows'][0]['sample_name'],)).fetchone()[0]
    con.close()
    assert r['rows'][0]['feature_value'] == v
    assert 'rank fusion' in r['policy']


def test_get_structure_full_provenance(env):
    db, log = env
    r = core.get_structure('AFCC_5_0p3_0', db_path=db, log_path=log)
    assert r['found']
    assert r['structure']['source']
    assert len(r['curves']) == 4 and all(c['source'] for c in r['curves'])
    assert len(r['features']) == 9
    miss = core.get_structure('NoSuch_5_0p5_0', db_path=db, log_path=log)
    assert not miss['found']


def test_nearest_rejects_ood_topology(env):
    """红线:OOD 拓扑禁最近邻,显式拒绝并指引物理裁判。"""
    db, log = env
    r = core.nearest_by_density('alien_xyz', 0.3, db_path=db, log_path=log)
    assert r['rejected']
    assert '物理计算' in r['reason']
    ok = core.nearest_by_density('BCC', 0.25, k=3, db_path=db,
                                 log_path=log)
    assert not ok['rejected'] and ok['n_hits'] == 3
    assert ok['rows'][0]['density_distance'] <= \
        ok['rows'][-1]['density_distance']
    assert any('applicability' in c for c in ok['caveats'])


def test_reference_retrieval_hits_and_miss_flag(env):
    db, log = env
    r = core.retrieve_reference('Maxwell 倾向', log_path=log)
    files = [h['file'] for h in r['hits']]
    assert 'daf_maxwell_2001.md' in files
    top = next(h for h in r['hits'] if h['file'] == 'daf_maxwell_2001.md')
    assert '10.1016/S1359-6454(00)00379-7' in top['doi']
    r2 = core.retrieve_reference('排粉', log_path=log)
    assert any(h['file'] == 'raz_2025.md' for h in r2['hits'])
    r3 = core.retrieve_reference('zzzz不存在的词qqqq', log_path=log)
    assert r3['miss'] is True  # miss 标志 = LanceDB 升级触发条件 ② 的统计源


def test_call_logging(env):
    db, log = env
    before = sum(1 for _ in open(log, encoding='utf-8'))
    core.query_cell_db(topology='BCC', limit=2, db_path=db, log_path=log)
    core.retrieve_reference('TPMS', log_path=log)
    lines = open(log, encoding='utf-8').read().strip().split('\n')
    assert len(lines) == before + 2
    last = json.loads(lines[-1])
    assert last['tool'] == 'retrieve_reference' and 'n_hits' in last


def test_server_instructions_contain_rules():
    import asyncio
    from atlas.retriever.server import mcp
    instr = mcp.instructions
    assert 'rank fusion' in instr and 'OOD' in instr
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} >= {'query_cell_db', 'get_structure',
                                       'nearest_by_density',
                                       'retrieve_reference'}
