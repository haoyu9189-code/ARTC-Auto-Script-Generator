"""P2-3 单测:目录摄入完整性、三级筛工件、枚举措辞红线。"""
import json
import os
import sqlite3

import pytest

from atlas.mechanics.catalog_screen import DB, SCREEN_OUT

pytestmark = pytest.mark.skipif(
    not (os.path.exists(DB) and os.path.exists(SCREEN_OUT)),
    reason='catalog.sqlite / screen 工件未生成'
           '(python -m atlas.mechanics.catalog_screen)')


@pytest.fixture(scope='module')
def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture(scope='module')
def run():
    with open(SCREEN_OUT, encoding='utf-8') as f:
        return json.load(f)


def test_ingest_counts(con):
    n = con.execute('SELECT COUNT(*) FROM catalog').fetchone()[0]
    assert n == 17262  # 目录总数(errata E9:论文口径 17,087)
    dup = con.execute("SELECT COUNT(*) FROM catalog WHERE "
                      "quality_flag='duplicate'").fetchone()[0]
    assert 90 <= dup <= 140  # WL 结构查重 103;头部按名对声明 135
    # E11:存档无星号标记,star 全 0(数据质量发现已记 errata)
    assert con.execute('SELECT SUM(star) FROM catalog').fetchone()[0] == 0


def test_provenance_on_every_row(con):
    n = con.execute("SELECT COUNT(*) FROM catalog WHERE source NOT LIKE "
                    "'%CC BY-NC%' OR source NOT LIKE '%10.3929%'"
                    ).fetchone()[0]
    assert n == 0


def test_pcu_anchor_row(con):
    r = con.execute("SELECT * FROM catalog WHERE name='cub_Z06.0_E1'"
                    ).fetchone()
    assert r['cubic'] == 1 and r['quality_flag'] == 'ok'
    assert abs(r['Cy'] - 0.33) < 1e-9 and abs(r['ny'] - 1.0) < 1e-9
    assert r['wl_hash'] and len(r['wl_hash']) == 64


def test_screen_artifact_and_wording(run):
    assert run['survivors'] > 0
    assert len(run['top10_catalog']) == 10
    for s in run['top10_catalog']:
        assert s['tier'] == '1.75(枚举)'
        assert 'CC BY-NC' in s['source']
        assert s['score'] > 0 and s['rho_mesh'] > 0
    # 红线:称枚举不称生成;screening 级标注
    assert '枚举' in run['wording'] and '非生成' in run['wording']
    assert 'screening' in run['wording']
    # 三层同台:种子 / 枚举 / 生成
    assert run['seed_top3'] and run['funsearch_top3']


def test_three_tier_narrative_ordering(run):
    """实测叙事弧:目录枚举冠军应超种子最优(搜索空间扩容的直接证据)。"""
    best_seed = max(run['seed_top3'].values())
    best_catalog = run['top10_catalog'][0]['score']
    assert best_catalog > best_seed
