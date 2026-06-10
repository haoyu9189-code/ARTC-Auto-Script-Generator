"""A2 单测:cell_db.sqlite schema 约束、计数一致性、可复跑性。"""
import json
import sqlite3

import pytest

from atlas.data import ingest_cell_db as ing


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp('celldb') / 'cell_db.sqlite'
    stats = ing.build(db_path=str(path))
    con = sqlite3.connect(str(path))
    con.execute('PRAGMA foreign_keys = ON')
    yield con, stats, str(path)
    con.close()


def test_counts_match_sources(db):
    con, stats, _ = db
    with open(ing.JSON_PATH, encoding='utf-8') as f:
        jdata = json.load(f)
    assert stats['json_entries'] == len(jdata) == 999
    assert stats['csv_entries'] == 5304
    # JSON ⊂ CSV(物理键归并):结构总数 = CSV 全集,交集 = 999
    assert stats['structures'] == 5304
    assert stats['overlap'] == 999
    n = con.execute('SELECT COUNT(*) FROM structures').fetchone()[0]
    assert n == stats['structures']
    n = con.execute('SELECT COUNT(*) FROM structures '
                    'WHERE in_json=1 AND in_csv=1').fetchone()[0]
    assert n == 999
    # canonical density:JSON 在场必为 fea
    n = con.execute("SELECT COUNT(*) FROM structures "
                    "WHERE in_json=1 AND density_source!='fea'").fetchone()[0]
    assert n == 0
    # 双密度列:989 个结构两值齐备(999 重叠 - 10 个 CSV density 空)
    n = con.execute('SELECT COUNT(*) FROM structures WHERE density_fea IS '
                    'NOT NULL AND density_smoothed IS NOT NULL').fetchone()[0]
    assert n == 989
    # 曲线行数 = JSON 内非空曲线总数(独立重算)
    expected = sum(
        1 for e in jdata.values() for lc in ing.LOAD_CASES
        if e.get(f'{lc}_curve')
        and all(len(a) > 0 for a in e[f'{lc}_curve'].values()))
    assert con.execute('SELECT COUNT(*) FROM curves').fetchone()[0] \
        == expected == stats['curves']
    assert con.execute('SELECT COUNT(*) FROM features').fetchone()[0] \
        == 5304 * len(ing.FEATURE_COLS)


def test_missing_curve_flags(db):
    con, stats, _ = db
    # 盘面实况:43 条缺至少一条动态工况曲线(调研报告"93"为误)
    n = con.execute("SELECT COUNT(*) FROM structures "
                    "WHERE quality_flag LIKE 'missing_curves:%'").fetchone()[0]
    assert n == stats['flagged_missing_curves'] == 43
    # 缺的全部是动态工况
    bad = con.execute(
        "SELECT quality_flag FROM structures "
        "WHERE quality_flag LIKE 'missing_curves:%'").fetchall()
    for (flag,) in bad:
        cases = flag.split(':', 1)[1].split(',')
        assert all(c in ('DynaCompre', 'DynaShear') for c in cases)


def test_source_nonempty_everywhere(db):
    con, _, _ = db
    for table in ('structures', 'curves', 'features'):
        n = con.execute(f"SELECT COUNT(*) FROM {table} "
                        f"WHERE source IS NULL OR length(source)=0"
                        ).fetchone()[0]
        assert n == 0, f'{table} 存在空 source'


def test_check_constraints_enforced(db):
    con, _, _ = db
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO structures VALUES "
                    "('X_5_0p5_0',NULL,'X_5_0p5_0','X',5,0.5,0,'stretch',"
                    "0.1,NULL,0.1,'smoothed',0,1,"
                    "'ok','', 'internal_fea','m','2026-01-01')")  # 空 source
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO structures VALUES "
                    "('X_5_0p5_0',NULL,'X_5_0p5_0','X',5,0.5,0,'WRONG',"
                    "0.1,NULL,0.1,'smoothed',0,1,"
                    "'ok','s','internal_fea','m','2026-01-01')")  # 非法 class
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO structures VALUES "
                    "('X_5_0p5_0',NULL,'X_5_0p5_0','X',5,0.5,0,'stretch',"
                    "0.1,NULL,0.1,'INVALID',0,1,"
                    "'ok','s','internal_fea','m','2026-01-01')")  # 非法 density_source
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO structures VALUES "
                    "('X_5_0p5_0',NULL,'X_5_0p5_0','X',5,0.5,0,'stretch',"
                    "NULL,NULL,NULL,'fea',0,1,"
                    "'ok','s','internal_fea','m','2026-01-01')")  # density NULL 但 source 非 NULL
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO curves VALUES "
                    "('AFCC_5_0p3_0','BadCase','[1]','[1]',1,'s')")  # 非法工况
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO features VALUES "
                    "('AFCC_5_0p3_0','f',1.0,'bad_mode','s')")  # 非法 load_mode


def test_known_value_spot_check(db):
    con, _, _ = db
    v = con.execute("SELECT value FROM features WHERE "
                    "sample_name='AFCC_5_0p25_0' AND feature='comp_EA'"
                    ).fetchone()[0]
    assert abs(v - 77.468740) < 1e-6
    # 物理键归并:JSON 名 canonical,挂着 CSV 伪影名,特征经 canonical 名可查
    row = con.execute(
        "SELECT json_name, csv_name, in_json, in_csv FROM structures "
        "WHERE sample_name='AFCC_5_0p3_0'").fetchone()
    assert row[0] == 'AFCC_5_0p3_0' and row[2] == 1 and row[3] == 1
    assert '0p30000000000000004' in row[1]
    n = con.execute("SELECT COUNT(*) FROM features "
                    "WHERE sample_name='AFCC_5_0p3_0'").fetchone()[0]
    assert n == len(ing.FEATURE_COLS)
    cls = con.execute("SELECT DISTINCT topology_class FROM structures "
                      "WHERE topology='Octet_truss'").fetchall()
    assert cls == [('stretch',)]
    cls = con.execute("SELECT DISTINCT topology_class FROM structures "
                      "WHERE topology='BCC'").fetchall()
    assert cls == [('bending',)]
    cls = con.execute("SELECT DISTINCT topology_class FROM structures "
                      "WHERE topology='Auxetic'").fetchall()
    assert cls == [('hybrid',)]


def test_curve_roundtrip(db):
    con, _, _ = db
    d, f, n = con.execute(
        "SELECT displacement_json, force_json, n_points FROM curves "
        "WHERE sample_name='AFCC_5_0p3_0' AND load_case='StaCompre'"
    ).fetchone()
    disp, force = json.loads(d), json.loads(f)
    assert len(disp) == len(force) == n == 198


def test_rerunnable(tmp_path):
    p = str(tmp_path / 'db.sqlite')
    s1 = ing.build(db_path=p)
    s2 = ing.build(db_path=p)
    assert s1 == s2
