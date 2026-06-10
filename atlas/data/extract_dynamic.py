"""P2-5:动态/剪切特征自提(解除动态验证维度断粮)。

动态曲线实况(实测 BCC_5_0p3_0):输出步长 ~0.1mm 且首点含惯性瞬态
(f 跳 12.6 → 振铃),"初段弹性斜率"在该数据上**不可提取**——
诚实重定义(全部带 source 与方法/局限说明):
- dyna_stiffness:**5% 应变割线模量**(d≈0.25mm 最近点 secant),
  caveat=含惯性瞬态,非弹性模量,Phase 3 滤波后重提
- dyna_yield:**首个局部峰应力**(落锤试验动态屈服标准代理)
- dyna_peak:前 30% 应变窗峰值应力(避开致密化尖峰)
- shear_peak:StaShear 同窗峰值(剪切面积约定 = 名义 25mm²,caveat)

可复跑:先删后插(幂等);缺动态曲线的结构如实跳过(不补值)。
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

DB = os.path.join(_ROOT, 'atlas', 'data', 'cell_db.sqlite')
H, A = 5.0, 25.0
FEATURES = ('dyna_stiffness', 'dyna_yield', 'dyna_peak', 'shear_peak')
SRC = ('P2-5 原始曲线自提(atlas/data/extract_dynamic.py):'
       'dyna_stiffness=5% 应变割线(含惯性瞬态,非弹性模量,'
       'Phase 3 滤波后重提);dyna_yield=首个局部峰应力(落锤动态屈服'
       '代理);peak 取前 30% 应变窗;剪切面积=名义 25mm²(约定);'
       '曲线源=内部 Abaqus 显式管线(步长 ~0.1mm)')


def _curve(con, name, case):
    row = con.execute(
        'SELECT displacement_json, force_json FROM curves WHERE '
        'sample_name=? AND load_case=?', (name, case)).fetchone()
    if not row:
        return None, None
    return (np.array(json.loads(row[0]), float),
            np.array(json.loads(row[1]), float))


def _secant_5pct(d, f, d_target=0.25):
    """5% 应变割线模量(动态曲线步长粗+惯性瞬态,斜率不可提取)。"""
    m = d > 1e-6
    if m.sum() < 2:
        return None
    i = int(np.argmin(np.abs(d - d_target)))
    if d[i] < 1e-6 or f[i] <= 0:
        return None
    return float((f[i] / A) / (d[i] / H))


def _first_peak(d, f, strain_cap=0.30):
    """首个局部峰应力(动态屈服标准代理)。"""
    m = d <= strain_cap * H
    ff = f[m]
    if len(ff) < 3:
        return None
    for i in range(1, len(ff) - 1):
        if ff[i] >= ff[i - 1] and ff[i] > ff[i + 1] and ff[i] > 0:
            return float(ff[i] / A)
    return None


def _peak(d, f, strain_cap=0.30):
    m = d <= strain_cap * H
    if m.sum() < 3:
        return None
    return float(f[m].max() / A)


def extract(db_path=DB):
    con = sqlite3.connect(db_path)
    con.execute('DELETE FROM features WHERE feature IN (?,?,?,?)',
                FEATURES)
    names = [r[0] for r in con.execute(
        'SELECT sample_name FROM structures WHERE in_json=1')]
    stats = {k: 0 for k in FEATURES}
    skipped = 0
    for name in names:
        rows = []
        d, f = _curve(con, name, 'DynaCompre')
        if d is not None:
            E = _secant_5pct(d, f)
            if E:
                rows.append((name, 'dyna_stiffness', E,
                             'dynamic_compression', SRC))
            y = _first_peak(d, f)
            if y:
                rows.append((name, 'dyna_yield', y,
                             'dynamic_compression', SRC))
            p = _peak(d, f)
            if p:
                rows.append((name, 'dyna_peak', p,
                             'dynamic_compression', SRC))
        else:
            skipped += 1
        d2, f2 = _curve(con, name, 'StaShear')
        if d2 is not None:
            sp = _peak(d2, f2)
            if sp:
                rows.append((name, 'shear_peak', sp,
                             'static_shear', SRC))
        for r in rows:
            con.execute('INSERT OR REPLACE INTO features VALUES '
                        '(?,?,?,?,?)', r)
            stats[r[1]] += 1
    con.commit()
    con.close()
    stats['structures'] = len(names)
    stats['skipped_no_dyna_curve'] = skipped
    return stats


if __name__ == '__main__':
    s = extract()
    print(s)
