"""A2:cell DB 摄入 SQLite + provenance 列。

数据源(盘面实况,2026-06-10 核实):
- data_package/feature_data.json          999 结构,四工况 displacement/force
  原始曲线 + 相对密度;43 条缺至少一条动态工况曲线(18 缺 DynaShear,
  18 缺 DynaCompre,7 双缺)——调研报告原记"93 条"为误,以本脚本统计为准。
- data_package/extracted_features_smoothed.csv  5,304 行 × 9 个标量力学特征
  = 24 拓扑 × 13 半径 × 17 滑块(0.5 步进)整格覆盖。

身份关键事实:CSV 样本名含浮点累积伪影(如 0p30000000000000004 vs JSON
的 0p3),按名字合并会把同一物理结构裂成两条记录;999 个 JSON 结构在
CSV 中全部物理存在(JSON ⊂ CSV)。因此结构身份 = 物理键
(topology, cell_size, round(radius,6), slider),canonical sample_name
优先用 JSON 名(无伪影),json_name/csv_name 双列保留原始名。

设计:
- structures   每个唯一物理结构一行(=CSV 全集 5304),身份 + 密度 + 质量旗标
- curves       JSON 曲线按 (sample_name, load_case) 长表,原始数组存 JSON 文本
- features     CSV 标量特征长表(逐特征 provenance,便于 MCP query_cell_db)
- 全表 source 非空 CHECK;source_type/topology_class/load_case 枚举 CHECK
- 可复跑:DROP + 重建,两次运行结果一致(日期取数据源文件 mtime,确定性)
"""
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scaling.selection import (STRETCH_DOMINATED, BENDING_DOMINATED,
                               HYBRID_SPECIAL, _parse_structure_key)

JSON_PATH = os.path.join(_ROOT, 'data_package', 'feature_data.json')
CSV_PATH = os.path.join(_ROOT, 'data_package', 'extracted_features_smoothed.csv')
DB_PATH = os.path.join(_HERE, 'cell_db.sqlite')

LOAD_CASES = ('StaCompre', 'StaShear', 'DynaCompre', 'DynaShear')

# CSV 特征列 → (feature 名, load_mode)
FEATURE_COLS = {
    'comp_EA': 'static_compression',
    'comp_stiffness': 'static_compression',
    'comp_densified': 'static_compression',
    'comp_yield': 'static_compression',
    'shear_EA': 'static_shear',
    'shear_stiffness': 'static_shear',
    'shear_yield': 'static_shear',
    'dyna_comp_EA': 'dynamic_compression',
    'dyna_shear_EA': 'dynamic_shear',
}

SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS features;
DROP TABLE IF EXISTS curves;
DROP TABLE IF EXISTS structures;

CREATE TABLE structures (
    sample_name    TEXT PRIMARY KEY,
    json_name      TEXT,
    csv_name       TEXT,
    topology       TEXT NOT NULL CHECK (length(topology) > 0),
    cell_size      REAL NOT NULL CHECK (cell_size > 0),
    strut_radius   REAL NOT NULL CHECK (strut_radius > 0),
    slider         REAL NOT NULL CHECK (slider >= 0),
    topology_class TEXT NOT NULL CHECK (topology_class IN
                                        ('stretch','bending','hybrid')),
    -- density_fea = feature_data.json 原始 FEA 值;density_smoothed =
    -- extracted_features_smoothed.csv 平滑拟合值(两种方法,中位差 1.5%,
    -- 最大 22%,442 行 CSV 无值);canonical density 取 FEA 优先
    density          REAL CHECK (density IS NULL OR density > 0),
    density_fea      REAL CHECK (density_fea IS NULL OR density_fea > 0),
    density_smoothed REAL CHECK (density_smoothed IS NULL
                                 OR density_smoothed > 0),
    density_source   TEXT CHECK (
        (density_source IN ('fea','smoothed') AND density IS NOT NULL)
        OR (density_source IS NULL AND density IS NULL)),
    in_json        INTEGER NOT NULL CHECK (in_json IN (0,1)),
    in_csv         INTEGER NOT NULL CHECK (in_csv IN (0,1)),
    quality_flag   TEXT NOT NULL CHECK (length(quality_flag) > 0),
    source         TEXT NOT NULL CHECK (length(source) > 0),
    source_type    TEXT NOT NULL CHECK (source_type IN
                       ('internal_fea','academic_doi','vendor','inference')),
    method         TEXT NOT NULL CHECK (length(method) > 0),
    date           TEXT NOT NULL CHECK (length(date) > 0)
);

CREATE TABLE curves (
    sample_name       TEXT NOT NULL REFERENCES structures(sample_name),
    load_case         TEXT NOT NULL CHECK (load_case IN
                          ('StaCompre','StaShear','DynaCompre','DynaShear')),
    displacement_json TEXT NOT NULL CHECK (length(displacement_json) > 2),
    force_json        TEXT NOT NULL CHECK (length(force_json) > 2),
    n_points          INTEGER NOT NULL CHECK (n_points > 0),
    source            TEXT NOT NULL CHECK (length(source) > 0),
    PRIMARY KEY (sample_name, load_case)
);

CREATE TABLE features (
    sample_name TEXT NOT NULL REFERENCES structures(sample_name),
    feature     TEXT NOT NULL CHECK (length(feature) > 0),
    value       REAL,
    load_mode   TEXT NOT NULL CHECK (load_mode IN
                    ('static_compression','static_shear',
                     'dynamic_compression','dynamic_shear','general')),
    source      TEXT NOT NULL CHECK (length(source) > 0),
    PRIMARY KEY (sample_name, feature)
);

CREATE INDEX idx_structures_topology ON structures(topology);
CREATE INDEX idx_features_feature ON features(feature);
"""


def classify(topology):
    """带前缀适配的拓扑分类(selection.py 的集合是基名,DB 用全名)。"""
    for names, cls in ((STRETCH_DOMINATED, 'stretch'),
                       (BENDING_DOMINATED, 'bending'),
                       (HYBRID_SPECIAL, 'hybrid')):
        if topology in names:
            return cls
    head = topology.split('_')[0]
    for names, cls in ((STRETCH_DOMINATED, 'stretch'),
                       (BENDING_DOMINATED, 'bending'),
                       (HYBRID_SPECIAL, 'hybrid')):
        if head in names:
            return cls
    return 'hybrid'


def _mtime_date(path):
    return datetime.fromtimestamp(os.path.getmtime(path),
                                  tz=timezone.utc).strftime('%Y-%m-%d')


def _parse_csv_name_fallback(name):
    """CSV slider 可为 0.5 步进,selection 的 int 解析会失败,从右手解。"""
    parts = name.split('_')
    slider = float(parts[-1])
    radius = float(parts[-2].replace('p', '.'))
    size = float(parts[-3])
    topo = '_'.join(parts[:-3])
    return topo, size, radius, slider


def build(db_path=DB_PATH, json_path=JSON_PATH, csv_path=CSV_PATH):
    json_date = _mtime_date(json_path)
    csv_date = _mtime_date(csv_path)
    src_json = (f'internal FEA: ARTC-Auto-Script pipeline '
                f'(model templates -> Abaqus -> GeJsonl.py), PA12/MJF, '
                f'material props = config.py; '
                f'file = data_package/feature_data.json (mtime {json_date})')
    src_csv = (f'internal FEA feature extraction: '
               f'data_package/extracted_features_smoothed.csv '
               f'(mtime {csv_date}), derived from the same Abaqus pipeline')

    with open(json_path, encoding='utf-8') as f:
        jdata = json.load(f)
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    # ---- 收集结构身份(物理键归并:topology, size, round(radius,6), slider) ----
    info = {}  # phys_key -> dict
    for r in rows:
        name = r['sample_name']
        topo = r['cell_type']
        size = float(r['cell_size'])
        radius = round(float(r['strut_radius']), 6)
        slider = float(r['transform'])
        key = (topo, size, radius, slider)
        if key in info:
            raise ValueError(f'duplicate CSV physical key: {key}')
        dens = float(r['density']) if r['density'] else None
        info[key] = dict(csv_name=name, json_name=None, topology=topo,
                         cell_size=size, strut_radius=radius, slider=slider,
                         in_json=0, in_csv=1, density_json=None,
                         density_csv=dens, missing_curves=None)
    for name, entry in jdata.items():
        topo, size, radius, slider = _parse_structure_key(name)
        if topo is None:
            raise ValueError(f'unparseable JSON key: {name}')
        key = (topo, float(size), round(float(radius), 6), float(slider))
        missing = [lc for lc in LOAD_CASES
                   if not entry.get(f'{lc}_curve')
                   or not all(len(arr) > 0
                              for arr in entry[f'{lc}_curve'].values())]
        d = info.get(key)
        if d is None:
            info[key] = dict(csv_name=None, json_name=name, topology=topo,
                             cell_size=float(size),
                             strut_radius=round(float(radius), 6),
                             slider=float(slider), in_json=1, in_csv=0,
                             density_json=float(entry['density']),
                             density_csv=None, missing_curves=missing)
        else:
            d['json_name'] = name
            d['in_json'] = 1
            d['density_json'] = float(entry['density'])
            d['missing_curves'] = missing

    # canonical 名:JSON 名优先(无浮点伪影),否则 CSV 名
    canon_of_json = {}
    canon_of_csv = {}
    for d in info.values():
        canon = d['json_name'] or d['csv_name']
        d['canon'] = canon
        if d['json_name']:
            canon_of_json[d['json_name']] = canon
        if d['csv_name']:
            canon_of_csv[d['csv_name']] = canon

    # ---- structures ----
    n_flagged = 0
    n_density_none = 0
    for key in sorted(info, key=lambda k: (k[0], k[1], k[2], k[3])):
        d = info[key]
        dj, dc = d['density_json'], d['density_csv']
        if dj is not None:
            density, density_source = dj, 'fea'
        elif dc is not None:
            density, density_source = dc, 'smoothed'
        else:
            density, density_source = None, None
            n_density_none += 1

        if d['in_json'] and d['missing_curves']:
            flag = 'missing_curves:' + ','.join(d['missing_curves'])
            n_flagged += 1
        elif not d['in_json']:
            flag = 'csv_only_no_curves'
        else:
            flag = 'ok'

        con.execute(
            'INSERT INTO structures VALUES '
            '(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (d['canon'], d['json_name'], d['csv_name'], d['topology'],
             d['cell_size'], d['strut_radius'], d['slider'],
             classify(d['topology']), density, dj, dc, density_source,
             d['in_json'], d['in_csv'], flag,
             src_json if d['in_json'] else src_csv,
             'internal_fea', 'Abaqus FEA (quasi-static/dynamic explicit)',
             json_date if d['in_json'] else csv_date))

    # ---- curves(canonical 名引用) ----
    n_curves = 0
    for name, entry in sorted(jdata.items()):
        canon = canon_of_json[name]
        for lc in LOAD_CASES:
            c = entry.get(f'{lc}_curve')
            if not c or not all(len(arr) > 0 for arr in c.values()):
                continue
            disp, force = c['displacement'], c['force']
            if len(disp) != len(force):
                raise ValueError(f'{name}/{lc}: len mismatch')
            con.execute('INSERT INTO curves VALUES (?,?,?,?,?,?)',
                        (canon, lc, json.dumps(disp), json.dumps(force),
                         len(disp), src_json))
            n_curves += 1

    # ---- features(canonical 名引用) ----
    n_feat = 0
    for r in sorted(rows, key=lambda x: x['sample_name']):
        canon = canon_of_csv[r['sample_name']]
        for col, mode in FEATURE_COLS.items():
            raw = r.get(col, '')
            value = float(raw) if raw not in ('', None) else None
            con.execute('INSERT INTO features VALUES (?,?,?,?,?)',
                        (canon, col, value, mode, src_csv))
            n_feat += 1

    con.commit()
    stats = dict(structures=len(info),
                 json_entries=sum(1 for d in info.values() if d['in_json']),
                 csv_entries=sum(1 for d in info.values() if d['in_csv']),
                 overlap=sum(1 for d in info.values()
                             if d['in_json'] and d['in_csv']),
                 curves=n_curves, features=n_feat,
                 flagged_missing_curves=n_flagged,
                 density_none=n_density_none)
    con.close()
    return stats


if __name__ == '__main__':
    stats = build()
    print(f'cell_db.sqlite built at {DB_PATH}')
    for k, v in stats.items():
        print(f'  {k}: {v}')
