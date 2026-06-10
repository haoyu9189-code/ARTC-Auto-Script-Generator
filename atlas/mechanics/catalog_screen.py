"""P2-3:Lumpe-Stanković 目录摄入 + Tier-1.75 三级筛。

红线:目录扩容是**枚举**(enumeration)不是生成——17,262 条已编目
晶体网,新颖性主张到此为止;与种子/FunSearch 同台比较时如实标层。

摄入:全目录 → catalog.sqlite(几何 JSON + 性能 + C,n + WL 哈希),
provenance = DOI 10.3929/ethz-b-000457598, CC BY-NC 4.0(非商用,
errata 许可表)。quality_flag:duplicate(WL 结构查重,实测 103 条;
头部按名对声明 135)/ ok。**数据质量发现(errata E11)**:头部声明的
星号标记(40 条数值问题结构)在存档文件中实际缺失(全文无 '*'),
无法按文件识别——缓解:自家硬门(C1–C8)+ 绝对门(SPD/Voigt/跨档)
在筛选时兜底捕获数值退化网。

三级筛(对给定 spec):
  S1(SQL,毫秒):立方·非星·非重复,按目录自带 C,n 标度在目标密度
     处的 E_y/ρ̄ 排序 → top-K
  S2(硬门,~100ms/条):转商图(半径=DfAM 下限 0.4)→ C1–C8
  S3(裁判,~10ms/条):beam_homog E_y/ρ̄_mesh(与 P2-2 同口径)→ top-10
"""
import json
import os
import sqlite3
import sys

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas.mechanics.lumpe_catalog import iter_entries, to_quotient_doc

DB = os.path.join(_ROOT, 'atlas', 'data', 'catalog.sqlite')
SCREEN_OUT = os.path.join(_ROOT, 'atlas', 'reports',
                          'catalog_screen_run.json')
SOURCE = ('Lumpe & Stankovic 2021, PNAS 10.1073/pnas.2003504118; '
          'catalog DOI 10.3929/ethz-b-000457598; license CC BY-NC 4.0'
          '(非商用,见 errata 许可表)')
R_FLOOR = 0.4   # MJF DfAM d>=0.8

SCHEMA = """
DROP TABLE IF EXISTS catalog;
CREATE TABLE catalog (
    name TEXT PRIMARY KEY,
    cubic INTEGER NOT NULL,
    star INTEGER NOT NULL,
    duplicate_of TEXT,
    n_nodes INTEGER, n_bars INTEGER,
    Ex REAL, Ey REAL, Ez REAL,
    Cx REAL, Cy REAL, Cz REAL,
    nx REAL, ny REAL, nz REAL,
    nodes_json TEXT NOT NULL,
    bars_json TEXT NOT NULL,
    wl_hash TEXT,
    quality_flag TEXT NOT NULL CHECK (length(quality_flag) > 0),
    source TEXT NOT NULL CHECK (length(source) > 0)
);
CREATE INDEX idx_cat_cubic ON catalog(cubic, star);
"""


def ingest(db_path=DB, limit=None):
    """全目录摄入(一次性,~2-3 分钟);WL 哈希顺带查重。"""
    from atlas.schema.novelty import wl_hash
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    seen_hash = {}
    n = n_star = n_dup = n_badparse = 0
    for e in iter_entries():
        if limit and n >= limit:
            break
        n += 1
        h = None
        dup = None
        if e['star']:
            n_star += 1
            flag = 'star'
        else:
            try:
                doc = to_quotient_doc(e, rho=0.01)
                h = wl_hash(doc)
                if h in seen_hash:
                    dup = seen_hash[h]
                    n_dup += 1
                    flag = 'duplicate'
                else:
                    seen_hash[h] = e['name']
                    flag = 'ok'
            except Exception:
                n_badparse += 1
                flag = 'convert_failed'
        C = e['C'] or (None, None, None)
        N = e['n'] or (None, None, None)
        p = e['props']
        con.execute(
            'INSERT OR REPLACE INTO catalog VALUES '
            '(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (e['name'], int(e['cubic']), int(e['star']), dup,
             len(e['nodes']), len(e['bars']),
             p.get('Ex'), p.get('Ey'), p.get('Ez'),
             C[0], C[1], C[2], N[0], N[1], N[2],
             json.dumps(e['nodes']), json.dumps(e['bars']),
             h, flag, SOURCE))
        if n % 2000 == 0:
            con.commit()
    con.commit()
    stats = {'total': n, 'star': n_star, 'duplicate': n_dup,
             'convert_failed': n_badparse}
    con.close()
    return stats


def _entry_doc(row, radius):
    entry = {'name': row['name'], 'nodes': json.loads(row['nodes_json']),
             'bars': [tuple(b) for b in json.loads(row['bars_json'])]}
    doc = to_quotient_doc(entry, rho=0.01)
    doc['default_radius_mm'] = radius
    doc['cell']['size_mm'] = 5.0
    # 还原 mm:to_quotient_doc 按归一胞 1.0 给 frac,本来就是分数坐标 ✓
    doc['lineage'] = {'tier': 'tier1.75',
                      'generator': 'catalog enumeration(枚举,非生成)',
                      'source': SOURCE, 'parents': [row['name']],
                      'notes': []}
    return doc


def screen(top_k1=150, top_out=10, db_path=DB, out_path=SCREEN_OUT):
    """三级筛(spec:MJF PA12,r=DfAM 下限,最大化 E_y/ρ̄)。"""
    from atlas.gates import run_gates
    from atlas.mechanics.funsearch import score_doc, seed_baseline
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # S1:目录自带标度排序(在参考密度 0.1 处的 E_y/ρ̄ ∝ Cy·0.1^(ny−1));
    # sqlite 无 POWER,取回后 Python 排序(仍毫秒级)
    rows = con.execute(
        "SELECT * FROM catalog WHERE cubic=1 AND quality_flag='ok' AND "
        "Cy IS NOT NULL AND ny IS NOT NULL AND Cy > 0").fetchall()
    rows = sorted(rows, key=lambda r: -(r['Cy'] * 0.1 ** (r['ny'] - 1)))
    rows = rows[:top_k1]
    s1 = len(rows)

    survivors, killed = [], 0
    for row in rows:
        try:
            doc = _entry_doc(row, R_FLOOR)
        except Exception:
            killed += 1
            continue
        g = run_gates(doc)
        if not g['passed']:
            killed += 1
            continue
        s, rho, h = score_doc(doc)
        if s is None:
            killed += 1
            continue
        survivors.append({'name': row['name'], 'score': round(s, 1),
                          'rho_mesh': round(rho, 4),
                          'E_y_bulk': round(h['constants']['E_y'], 2),
                          'catalog_Cy': row['Cy'], 'catalog_ny': row['ny'],
                          'tier': '1.75(枚举)', 'source': SOURCE})
    survivors.sort(key=lambda x: -x['score'])
    con.close()

    baseline = seed_baseline()
    fs_path = os.path.join(_ROOT, 'atlas', 'reports',
                           'funsearch_run.json')
    fs_top = []
    if os.path.exists(fs_path):
        fs = json.load(open(fs_path, encoding='utf-8'))
        fs_top = [{'name': a['name'], 'score': a['score'],
                   'tier': '2(生成)'} for a in fs['accepted'][:3]]

    result = {'spec': 'MJF PA12 · r=0.4(DfAM 下限) · 最大化 E_y/ρ̄ · '
                      '与 P2-2 同口径',
              's1_pool': s1, 's2s3_killed': killed,
              'survivors': len(survivors),
              'top10_catalog': survivors[:top_out],
              'seed_top3': dict(sorted(baseline.items(),
                                       key=lambda kv: -kv[1])[:3]),
              'funsearch_top3': fs_top,
              'wording': 'Tier-1.75 为**枚举**(已编目晶体网)非生成;'
                         '同台分数均为 screening 级(线弹性 bulk)'}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result


if __name__ == '__main__':
    if not os.path.exists(DB):
        print('摄入目录(一次性)…')
        st = ingest()
        print(f'  {st}')
    r = screen()
    print(f"S1 池 {r['s1_pool']} → 杀 {r['s2s3_killed']} → "
          f"幸存 {r['survivors']}")
    print(f"种子 top3: {r['seed_top3']}")
    print(f"FunSearch top3: {[(x['name'], x['score']) for x in r['funsearch_top3']]}")
    for s in r['top10_catalog']:
        print(f"  {s['name']:<24} score={s['score']:>7} "
              f"ρ̄={s['rho_mesh']:.3f}")
