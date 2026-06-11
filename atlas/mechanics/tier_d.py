"""P3-A:Tier-D ABAQUS 升压收口 —— 作业生成 + 能量门 + 结果→trace 桥。

三件事(见 PLAN P3-A):
1. generate_tier_d_jobs:FunSearch 冠军商图 → preprocess/postprocess/
   run.pbs 作业目录;postprocess **文本注入** ALLKE/ALLIE 能量历史提取
   (不改 script_generator 源——用户工作区有未提交修改)。
2. 能量门:显式准静态有效性判据 ALLKE/ALLIE ≤ 5%(Abaqus 文档准静态
   能量平衡准则,vendor);Standard 静力分析无 ALLKE 历史时门不适用,
   informational 留痕。
3. results_to_checks:feature_data.txt + energy_data.txt → checks
   (source_type='abaqus_fea',R7 白名单成员)。刚度提取与 P2-1c 标定
   同口径(0–0.10mm 位移窗线性拟合,E*=k·H/A)。

诚实限定:
- 管线为单半径(structure text 无逐杆半径)——CMA-ES polish 的
  radii_groups 不可表示,作业按 default_radius_mm 均匀半径生成并
  在 job_meta/caveat 声明(冠军分数的逐组半径增益不在本测试内)。
- 剪切需 X 旋转适配(B6 显式拒绝),本模块仅 StaCompre/DynaCompre。
- 提交求解由用户决定(loop 协议);本模块只生成与回收。
"""
import json
import os
import re
import sys

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas.mechanics.calibrate import CELL_A, CELL_H

PROPOSAL_FILES = (
    os.path.join(_ROOT, 'atlas', 'proposals', 'claude_20260612.json'),
    os.path.join(_ROOT, 'atlas', 'proposals', 'claude_20260612b.json'),
)
CHAMPIONS = ('dual_column_web', 'mid_braced_column', 'twin_offset_web')

ENERGY_GATE_THRESHOLD = 0.05
ENERGY_GATE_SOURCE = ('Abaqus Analysis User\'s Guide — quasi-static '
                      'energy balance criterion(ALLKE ≤ ~5% ALLIE)')
SLOPE_WINDOW_MM = 0.10   # 与 calibrate.curve_slope 同口径

_MARKER = '# ATLAS-P3A-ENERGY-GATE'
_ANCHOR = ("    session.writeXYReport(fileName='feature_data.txt', "
           "xyData=(xy_combined, ), appendMode=ON)")

# Abaqus Python 2.7(jython 风格)片段;复用 postprocess 作用域内的
# step 变量;失败写 status 不抛——能量缺失由 ingest 端定性,不毁主产物。
_ENERGY_SNIPPET = '''
    ''' + _MARKER + ''': ALLKE/ALLIE 准静态能量门数据(P3-A 注入)
    try:
        _e_reg = None
        for _rn in step.historyRegions.keys():
            _ho = step.historyRegions[_rn].historyOutputs
            if 'ALLKE' in _ho.keys() and 'ALLIE' in _ho.keys():
                _e_reg = step.historyRegions[_rn]
                break
        _ef = open('energy_data.txt', 'w')
        if _e_reg is None:
            _ef.write('status: no_energy_history\\n')
        else:
            _ef.write('status: ok\\n')
            _ef.write('time allke allie\\n')
            _ie_map = {}
            for _p in _e_reg.historyOutputs['ALLIE'].data:
                _ie_map[_p[0]] = _p[1]
            for _p in _e_reg.historyOutputs['ALLKE'].data:
                _ef.write(str(_p[0]) + ' ' + str(_p[1]) + ' ' +
                          str(_ie_map.get(_p[0], 0.0)) + '\\n')
        _ef.close()
    except Exception as _e_err:
        try:
            _ef = open('energy_data.txt', 'w')
            _ef.write('status: error ' +
                      str(_e_err).replace('\\n', ' ') + '\\n')
            _ef.close()
        except:
            pass
'''


def inject_energy_extraction(postprocess_text):
    """向生成的 postprocess 脚本注入能量提取段(幂等,锚点缺失则 fail loudly)。"""
    if _MARKER in postprocess_text:
        return postprocess_text
    if _ANCHOR not in postprocess_text:
        raise ValueError('postprocess 锚点缺失(writeXYReport 行)——'
                         'script_generator 模板已变,注入器需要更新')
    return postprocess_text.replace(_ANCHOR, _ANCHOR + _ENERGY_SNIPPET, 1)


def load_champion_docs(names=CHAMPIONS):
    """从提案文件载入冠军 (name, doc, polish);找不到则 KeyError。"""
    pool = {}
    for path in PROPOSAL_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            for p in json.load(f)['proposals']:
                pool[p['name']] = p
    out = []
    for n in names:
        if n not in pool:
            raise KeyError(f'冠军 {n} 不在提案文件中')
        out.append((n, pool[n]['doc'], pool[n].get('polish') or {}))
    return out


def generate_job_for_doc(doc, out_dir, analysis_type='StaCompre',
                         lattice_array=(1, 1, 1), extra_caveats=()):
    """任意 atlas-cell-graph 文档 → Tier-D 作业目录(三件套+能量注入+meta)。

    P3-B 用例:D2 真 agent 生成的 OOD 新图(如 PSCZ)被 R2/R7 卡在
    margin 证据 → 本函数即其合法升压出口。
    """
    from atlas.abaqus_adapter import generate_abaqus_script
    name = doc.get('name', 'atlas_graph')
    os.makedirs(out_dir, exist_ok=True)
    r = generate_abaqus_script(doc, out_dir,
                               analysis_type=analysis_type,
                               lattice_array=lattice_array)
    if not r['ok']:
        raise RuntimeError(f'{name} 脚本生成失败: {r["message"]}')
    post = [f for f in os.listdir(out_dir)
            if f.endswith('_postprocess.py')]
    if len(post) != 1:
        raise RuntimeError(f'{name} postprocess 文件异常: {post}')
    ppath = os.path.join(out_dir, post[0])
    with open(ppath, encoding='utf-8') as f:
        txt = f.read()
    with open(ppath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(inject_energy_extraction(txt))

    caveats = [
        '管线为单半径:逐杆/逐组半径不可表示,'
        f'按均匀 default_radius_mm={doc["default_radius_mm"]} 生成',
        f'analysis_type={analysis_type};剪切需 X 旋转适配,不支持',
    ] + list(extra_caveats)
    meta = {'name': name, 'analysis_type': analysis_type,
            'lattice_array': list(lattice_array),
            'radius_mm': doc['default_radius_mm'],
            'cell_size_mm': doc['cell']['size_mm'],
            'adapter_stats': r['adapter_stats'],
            'energy_gate': {'threshold': ENERGY_GATE_THRESHOLD,
                            'source': ENERGY_GATE_SOURCE,
                            'source_type': 'vendor'},
            'caveats': caveats,
            'source': 'atlas.mechanics.tier_d.generate_job_for_doc'}
    with open(os.path.join(out_dir, 'job_meta.json'), 'w',
              encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def generate_tier_d_jobs(out_root, names=CHAMPIONS,
                         analysis_type='StaCompre',
                         lattice_array=(1, 1, 1)):
    """冠军 → 作业目录(三件套 + 能量注入 + job_meta.json + README)。"""
    os.makedirs(out_root, exist_ok=True)
    jobs = []
    for name, doc, polish in load_champion_docs(names):
        extra = []
        if polish.get('radii_groups'):
            extra.append(f'polish.radii_groups 共 '
                         f'{len(polish["radii_groups"])} 组,已忽略'
                         '——冠军分数中的逐组半径增益不在本次测试内')
        meta = generate_job_for_doc(
            doc, os.path.join(out_root, name),
            analysis_type=analysis_type, lattice_array=lattice_array,
            extra_caveats=extra)
        jobs.append(meta)

    readme = [
        '# Tier-D ABAQUS 终审作业(P3-A 生成)\n',
        f'冠军:{", ".join(j["name"] for j in jobs)}(FunSearch P2-2)\n',
        '## 提交(由用户决定,loop 协议)\n',
        '- 集群:`qsub run.pbs`(config.py 当前为 PBS 口径)',
        '- 本地:`abaqus cae noGUI=preprocess_*.py` → 求解 → '
        '`abaqus cae noGUI=postprocess_*.py`\n',
        '## 产物回收\n',
        '求解后目录内出现 `feature_data.txt` + `energy_data.txt`,运行:\n',
        '```python',
        'from atlas.mechanics.tier_d import results_to_checks',
        "checks = results_to_checks(job_dir, spec)  # → judge() 可消费",
        '```\n',
        f'能量门:ALLKE/ALLIE ≤ {ENERGY_GATE_THRESHOLD}'
        f'({ENERGY_GATE_SOURCE});Standard 静力分析无 ALLKE 历史时'
        '门不适用(informational)。\n',
        '## 已知限定\n',
    ] + [f'- {c}' for j in jobs for c in j['caveats'][:1]]
    with open(os.path.join(out_root, 'README.md'), 'w',
              encoding='utf-8') as f:
        f.write('\n'.join(readme))
    return jobs


_FLOAT_PAIR = re.compile(
    r'^\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+'
    r'(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$')


def parse_feature_data(path):
    """feature_data.txt → {'header': dict, 'disp': arr, 'force': arr}。

    格式 = 生成的 postprocess 产物:首行 job 名,继之 key: value 头,
    末尾 writeXYReport 追加的两列表(|位移| |力|)。
    """
    header, disp, force = {}, [], []
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    if lines:
        header['job_name'] = lines[0].strip()
    for ln in lines[1:]:
        m = _FLOAT_PAIR.match(ln)
        if m:
            disp.append(float(m.group(1)))
            force.append(float(m.group(2)))
        elif ':' in ln:
            k, v = ln.split(':', 1)
            header[k.strip()] = v.strip()
    return {'header': header,
            'disp': np.asarray(disp, float),
            'force': np.asarray(force, float)}


def parse_energy_data(path):
    """energy_data.txt → {'status', 'ratio_max', 'n_points'}。

    ratio_max 只在 ALLIE ≥ 1% 终值处取(初期 ALLIE≈0 的比值噪声不计,
    属准静态评估惯例,留 caveat)。
    """
    if not os.path.exists(path):
        return {'status': 'missing', 'ratio_max': None, 'n_points': 0}
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    status = lines[0].split(':', 1)[1].strip() if lines else 'empty'
    if status != 'ok':
        return {'status': status, 'ratio_max': None, 'n_points': 0}
    ke, ie = [], []
    for ln in lines[2:]:
        parts = ln.split()
        if len(parts) == 3:
            ke.append(float(parts[1]))
            ie.append(float(parts[2]))
    ke, ie = np.asarray(ke), np.asarray(ie)
    if not len(ie) or ie.max() <= 0:
        return {'status': 'no_internal_energy', 'ratio_max': None,
                'n_points': int(len(ke))}
    m = ie >= 0.01 * ie.max()
    ratio = float((ke[m] / ie[m]).max()) if m.any() else None
    return {'status': 'ok', 'ratio_max': ratio, 'n_points': int(len(ke))}


def results_to_checks(job_dir, spec):
    """求解产物 → judge() 可消费的 checks(source_type='abaqus_fea')。"""
    with open(os.path.join(job_dir, 'job_meta.json'),
              encoding='utf-8') as f:
        meta = json.load(f)
    nx, ny, nz = meta.get('lattice_array', [1, 1, 1])
    h = CELL_H * nz
    a = CELL_A * nx * ny
    feat = parse_feature_data(os.path.join(job_dir, 'feature_data.txt'))
    energy = parse_energy_data(os.path.join(job_dir, 'energy_data.txt'))
    job = feat['header'].get('job_name', meta['name'])
    metric = (spec or {}).get('margin_metric', '')
    checks = []

    # 能量门(先判,决定力学证据是否 margin 级)
    gate_applicable = energy['ratio_max'] is not None
    if gate_applicable:
        gate_ok = energy['ratio_max'] <= ENERGY_GATE_THRESHOLD
        checks.append({
            'dimension': 'mechanics', 'tool': 'abaqus.energy_gate',
            'value': round(energy['ratio_max'], 6),
            'threshold': ENERGY_GATE_THRESHOLD, 'pass': bool(gate_ok),
            'source': ENERGY_GATE_SOURCE, 'source_type': 'vendor',
            'status': 'computed',
            'caveats': ['ratio 仅在 ALLIE≥1% 终值区间取最大(初期噪声不计)']})
    else:
        gate_ok = energy['status'] == 'no_energy_history'
        checks.append({
            'dimension': 'mechanics', 'tool': 'abaqus.energy_gate',
            'value': None, 'threshold': ENERGY_GATE_THRESHOLD,
            'pass': None, 'source': ENERGY_GATE_SOURCE,
            'source_type': 'vendor',
            'status': ('computed' if gate_ok else 'needs_input'),
            'caveats': [('无 ALLKE 历史:Standard 静力分析能量门不适用;'
                         '如为显式求解则属异常')
                        if gate_ok else
                        f"能量数据不可用(status={energy['status']}),"
                        'Tier-D 证据降为 screening']})

    margin_allowed = gate_ok
    base_caveats = list(meta.get('caveats', []))
    if not margin_allowed:
        base_caveats.append('能量门未过/不可用,margin_eligible 取消')

    d, fo = feat['disp'], feat['force']
    m = (d > 1e-6) & (d <= SLOPE_WINDOW_MM)
    if m.sum() >= 5:
        k = float(np.polyfit(d[m], fo[m], 1)[0])
        if k > 0:
            checks.append({
                'dimension': 'mechanics',
                'tool': 'abaqus.sta_compre.stiffness',
                'value': round(k * h / a, 6), 'threshold': None,
                'pass': None,
                'source': f'ABAQUS Tier-D StaCompre ODB({job}),'
                          f'0–{SLOPE_WINDOW_MM}mm 窗与 P2-1c 标定同口径',
                'source_type': 'abaqus_fea', 'status': 'computed',
                'caveats': base_caveats,
                'margin_eligible': bool(margin_allowed
                                        and 'stiffness' in metric)})
    if len(d) >= 2:
        ea = float(np.trapezoid(fo, d))  # N·mm = mJ
        checks.append({
            'dimension': 'mechanics', 'tool': 'abaqus.sta_compre.comp_EA',
            'value': round(ea, 6), 'threshold': None, 'pass': None,
            'source': f'ABAQUS Tier-D StaCompre ODB({job}),'
                      f'∫F·dδ 全可用曲线(末位移 {d.max():.3f}mm)',
            'source_type': 'abaqus_fea', 'status': 'computed',
            'caveats': base_caveats + ['积分窗=可用曲线全程,与 DB '
                                       'comp_EA 窗口径需对照后比较'],
            'margin_eligible': bool(margin_allowed
                                    and metric.startswith('comp_EA'))})
    return checks
