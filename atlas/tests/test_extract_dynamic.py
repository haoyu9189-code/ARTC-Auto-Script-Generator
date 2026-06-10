"""P2-5 单测:动态/剪切特征自提(幂等/缺曲线跳过/verify 升级)。"""
import sqlite3

import pytest

from atlas.data import ingest_cell_db as ing
from atlas.data.extract_dynamic import extract, FEATURES


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    p = str(tmp_path_factory.mktemp('dyn') / 'cell_db.sqlite')
    ing.build(db_path=p)
    stats = extract(db_path=p)
    return p, stats


def test_extraction_counts_and_honest_skips(db):
    p, stats = db
    assert stats['structures'] == 999
    # 43 条缺动态曲线如实跳过(25 缺 DynaCompre:18 单缺+7 双缺)
    assert stats['skipped_no_dyna_curve'] == 25
    assert stats['dyna_stiffness'] > 900
    assert stats['shear_peak'] > 900
    con = sqlite3.connect(p)
    for feat in FEATURES:
        n_null_src = con.execute(
            "SELECT COUNT(*) FROM features WHERE feature=? AND "
            "(source IS NULL OR length(source)=0)", (feat,)).fetchone()[0]
        assert n_null_src == 0
    con.close()


def test_values_physically_sane(db):
    p, _ = db
    con = sqlite3.connect(p)
    rows = con.execute(
        "SELECT feature, value FROM features WHERE sample_name="
        "'BCC_5_0p3_0' AND feature IN ('dyna_stiffness','dyna_peak')"
    ).fetchall()
    con.close()
    vals = dict(rows)
    assert vals['dyna_stiffness'] > 0
    assert 0 < vals['dyna_peak'] < 1010  # 应力不可能超基材模量量级
    # 动态初段斜率与静态同量级(同结构 StaCompre 自提 ≈ 32.8)
    assert 5 < vals['dyna_stiffness'] < 200


def test_rerun_idempotent(db):
    p, s1 = db
    s2 = extract(db_path=p)
    assert s1 == s2
    con = sqlite3.connect(p)
    n = con.execute("SELECT COUNT(*) FROM features WHERE feature IN "
                    "(?,?,?,?)", FEATURES).fetchone()[0]
    con.close()
    assert n == sum(s2[f] for f in FEATURES)


def test_verify_dynamic_check_upgraded(db):
    p, _ = db
    from atlas.orchestration.verify import verify_candidate
    spec = {'process': 'MJF', 'material': 'PA12', 'n_cells': 1,
            'fos_already_applied': True}
    checks = verify_candidate(
        {'id': 'c', 'tier': '1',
         'geometry': {'topology': 'BCC', 'slider': 4, 'radius_mm': 0.5}},
        spec, db_path=p)
    dyn = next(c for c in checks if c['tool'] == 'dynamic_shear_features')
    assert 'dyna_stiffness' in dyn['value']  # 真特征值
    assert dyn['source'].startswith('P2-5')  # 带源
    assert dyn['pass'] is None               # 仍不入 margin
    assert any('不入 margin' in c for c in dyn['caveats'])
