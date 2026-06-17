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
            _keys = [_k for _k in ('ALLIE','ALLKE','ALLAE','ALLVD',
                                   'ALLFD','ALLWK')
                     if _k in _e_reg.historyOutputs.keys()]
            _ef.write('status: ok\\n')
            _ef.write('time ' + ' '.join([_k.lower() for _k in _keys])
                      + '\\n')
            _maps = {}
            for _k in _keys:
                _maps[_k] = {}
                for _p in _e_reg.historyOutputs[_k].data:
                    _maps[_k][_p[0]] = _p[1]
            for _p in _e_reg.historyOutputs['ALLIE'].data:
                _t = _p[0]
                _row = [str(_t)] + [str(_maps[_k].get(_t, 0.0))
                                    for _k in _keys]
                _ef.write(' '.join(_row) + '\\n')
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


# NT-1:whole-model 能量历史(显式动态压溃用)——填补 script_generator
# H-Output-2 只取板 U/RF 的缺口,使 ALLKE/ALLIE/ALLAE/ALLVD/ALLFD 入 ODB
_HIST_MARKER = '# ATLAS-P3X-ENERGY-HIST'
_HIST_ANCHOR = ("region=a.sets['TopReflection'], sectionPoints=DEFAULT, "
                "rebar=EXCLUDE)")
_HIST_SNIPPET = (
    "\n    " + _HIST_MARKER + ": whole-model 能量历史(准静态/沙漏/接触门)\n"
    "    mdb.models['Model-1'].HistoryOutputRequest(name='H-Energy',\n"
    "        createStepName='Step-1',\n"
    "        variables=('ALLKE', 'ALLIE', 'ALLAE', 'ALLVD', 'ALLFD',"
    " 'ALLWK', 'ETOTAL'), numIntervals=200)")


def inject_energy_history_request(preprocess_text):
    """向生成的 preprocess 注入 whole-model 能量历史请求(幂等,锚点缺失 fail loud)。"""
    if _HIST_MARKER in preprocess_text:
        return preprocess_text
    if _HIST_ANCHOR not in preprocess_text:
        raise ValueError('preprocess 锚点缺失(H-Output-2 行)——'
                         'script_generator 模板已变,能量历史注入器需更新')
    return preprocess_text.replace(_HIST_ANCHOR,
                                   _HIST_ANCHOR + _HIST_SNIPPET, 1)


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

    # NT-1:显式动态压溃需注入 whole-model 能量历史(静态 Standard 不需要)
    if analysis_type.startswith('DynaCompre'):
        pre = [f for f in os.listdir(out_dir)
               if f.endswith('_preprocess.py')]
        if len(pre) != 1:
            raise RuntimeError(f'{name} preprocess 文件异常: {pre}')
        prepath = os.path.join(out_dir, pre[0])
        with open(prepath, encoding='utf-8') as f:
            ptxt = f.read()
        with open(prepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(inject_energy_history_request(ptxt))

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


import re as _re

_DISPCTRL_MARKER = '# ATLAS-P3X-DISPCTRL'


def patch_displacement_control(text, target_disp, time_period):
    """显式 step 的「自由板+初速度冲击」→「位移控制斜坡」(准静态压溃正确设置)。

    原 DynaCompre 给顶板一个初速度预定义场(自由板):准静态低速下初动能太小
    → 板几乎不压入、顶板 RF2≈0(自由板反力本为零)。改为 SmoothStep 位移 BC
    驱动顶板下行 target_disp → RF2=真实阻力,曲线干净。幂等;锚点缺失 fail loud。
    """
    if _DISPCTRL_MARKER in text:
        return text
    bc_anchor = "mdb.models['Model-1'].DisplacementBC(name='BC-2',"
    if bc_anchor not in text or 'u2=UNSET' not in text \
            or "Velocity(name='Predefined Field-1'" not in text:
        raise ValueError('位移控制 patch 锚点缺失(BC-2/u2=UNSET/Velocity)——'
                         'generator 动态模板已变')
    amp = (_DISPCTRL_MARKER + " 位移控制斜坡(准静态压溃)\n"
           "    mdb.models['Model-1'].SmoothStepAmplitude(name='Amp-Crush',"
           " timeSpan=STEP, data=((0.0, 0.0), (%g, 1.0)))\n    " % time_period)
    text = text.replace(bc_anchor, amp + bc_anchor, 1)
    text = text.replace('u1=0.0, u2=UNSET, u3=0.0,',
                        'u1=0.0, u2=-%g, u3=0.0,' % target_disp, 1)
    text = text.replace('amplitude=UNSET, fixed=OFF,',
                        "amplitude='Amp-Crush', fixed=OFF,", 1)
    # 删除初速度预定义场(改为位移驱动;全零 Velocity 会被 Abaqus 拒绝)
    text, nv = _re.subn(
        r"mdb\.models\['Model-1'\]\.Velocity\(name='Predefined Field-1',"
        r".*?omega=0\.0\)",
        "pass  " + _DISPCTRL_MARKER + " 初速度预定义场已移除(位移控制)",
        text, count=1, flags=_re.S)
    if nv != 1:
        raise ValueError('Velocity 预定义场移除失败:锚点未命中')
    return text


def generate_crush_job(doc, out_dir, lattice_array=(1, 1, 1),
                       crush_strain=0.8, strain_rate=10.0,
                       extra_caveats=()):
    """非线性吸能 Tier-D 压溃作业(NT-1):显式 + 自接触 + 能量历史 + 位移控制。

    显式动力学步(大变形/自接触/单元删除)+ **位移控制斜坡**(SmoothStep,
    避免自由板冲击在准静态低速下不压入);速率 strain_rate(准静态),压溃量
    crush_strain·H0。均经文本 patch,不改 generator 源。准静态有效性由
    ALLKE/ALLIE≤5% 能量门 + 半速不变性(NT-5)实证,非断言。
    """
    nz = lattice_array[2]
    H0 = CELL_H * nz
    velocity = strain_rate * H0                       # mm/s(名义,位移控制后仅记录)
    time_period = crush_strain / strain_rate          # s
    target_disp = crush_strain * H0                   # mm
    cav = list(extra_caveats) + [
        f'位移控制准静态压溃:目标应变 {crush_strain}、应变率 {strain_rate}/s '
        f'→ 压溃 {target_disp:g}mm、timePeriod {time_period:g}s;'
        '准静态由能量门+半速不变性实证']
    meta = generate_job_for_doc(
        doc, out_dir, analysis_type=f'DynaCompre_{velocity:g}',
        lattice_array=lattice_array, extra_caveats=cav)
    pre = [f for f in os.listdir(out_dir)
           if f.endswith('_preprocess.py')][0]
    prepath = os.path.join(out_dir, pre)
    with open(prepath, encoding='utf-8') as f:
        txt = f.read()
    txt, n = _re.subn(r'timePeriod=[\d.eE+-]+',
                      f'timePeriod={time_period:g}', txt, count=1)
    if n != 1:
        raise RuntimeError('timePeriod patch 失败:锚点未命中')
    txt = patch_displacement_control(txt, target_disp, time_period)
    with open(prepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)
    meta['crush'] = {'crush_strain': crush_strain,
                     'strain_rate': strain_rate, 'velocity_mm_s': velocity,
                     'time_period_s': time_period, 'H0_mm': H0,
                     'target_disp_mm': target_disp, 'control': 'displacement'}
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


# Abaqus XY report 格式:含 "0."(尾点无小数)、"859.525E-06" 等 → 允许
# 小数点后可空、可科学计数(原 \.\d+ 漏掉 "0." 导致 0 数据点)
_NUM = r'-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?'
_FLOAT_PAIR = re.compile(r'^\s*(' + _NUM + r')\s+(' + _NUM + r')\s*$')


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
    """energy_data.txt → {'status','ratio_max','ratio_allae','contact_frac',
    'n_points'}(header 驱动,兼容旧 3 列 'time allke allie';新格式列序任意)。

    比值只在 ALLIE ≥ 1% 终值处取(初期 ALLIE≈0 的比值噪声不计,准静态惯例)。
    ratio_max=ALLKE/ALLIE(动能门);ratio_allae=ALLAE/ALLIE(沙漏/人工能门);
    contact_frac=(ALLVD+ALLFD)/ALLIE(接触/黏性耗散占比,稳定性代理)。
    """
    if not os.path.exists(path):
        return {'status': 'missing', 'ratio_max': None,
                'ratio_allae': None, 'contact_frac': None, 'n_points': 0}
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    status = (lines[0].split(':', 1)[1].strip()
              if lines and ':' in lines[0] else 'empty')
    none3 = {'ratio_max': None, 'ratio_allae': None, 'contact_frac': None}
    if status != 'ok' or len(lines) < 2:
        return dict(status=status, n_points=0, **none3)
    cols = lines[1].split()                      # e.g. time allie allke allae
    data = {c: [] for c in cols}
    for ln in lines[2:]:
        parts = ln.split()
        if len(parts) != len(cols):
            continue
        for c, p in zip(cols, parts):
            try:
                data[c].append(float(p))
            except ValueError:
                data[c].append(0.0)

    def arr(name):
        return np.asarray(data.get(name, []), float)

    ie = arr('allie')
    if not len(ie) or ie.max() <= 0:
        return dict(status='no_internal_energy', n_points=int(len(ie)),
                    **none3)
    m = ie >= 0.01 * ie.max()

    def ratio(name):
        n = arr(name)
        if len(n) != len(ie) or not m.any():
            return None
        return float((n[m] / ie[m]).max())

    vd, fd = arr('allvd'), arr('allfd')
    cd = np.zeros_like(ie)
    has_cd = False
    if len(vd) == len(ie):
        cd = cd + vd
        has_cd = True
    if len(fd) == len(ie):
        cd = cd + fd
        has_cd = True
    contact = (float((cd[m] / ie[m]).max()) if (has_cd and m.any())
               else None)
    return {'status': 'ok', 'ratio_max': ratio('allke'),
            'ratio_allae': ratio('allae'), 'contact_frac': contact,
            'n_points': int(len(ie))}


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


# ============================================================
# NT-2/3/4:非线性压溃指标(SEA/平台/致密化)+ 硬有效性门 + margin 接线
# ============================================================

# 实心材料密度 g/mm³(SEA 用实心杆质量 m=ρ·V0·ρ̄,非包络质量)
_RHO_SOLID_G_MM3 = {'PA12': 1.01e-3, 'AlSi10Mg': 2.67e-3, 'Ti64': 4.43e-3}
CRUSH_KE_GATE = 0.05        # ALLKE/ALLIE 准静态
CRUSH_AE_GATE = 0.05        # ALLAE/ALLIE 沙漏/人工能
CRUSH_CONTACT_GATE = 0.10   # (ALLVD+ALLFD)/ALLIE 接触/黏性耗散
# SEA 合理带 kJ/kg(errata E4:PA12 lattice 0.3–8,>10 属金属);超带→
# 不静默进 margin(实心杆质量归一下,超带多因 n=1 边界高估或模型偏硬)
_SEA_BAND_KJ = {'PA12': (0.3, 8.0), 'AlSi10Mg': (1.0, 40.0),
                'Ti64': (1.0, 50.0)}
ISO13314 = ('ISO 13314:2011(平台应力 20-40% 均值)+ Li 2006 '
            '能量吸收效率法(致密化起点)')


def _smooth(y, w=7):
    if len(y) < w or w < 2:
        return np.asarray(y, float)
    return np.convolve(np.asarray(y, float), np.ones(w) / w, mode='same')


def crush_metrics(disp, force, H0, A0, n_grid=400):
    """力-位移压溃曲线 → SEA 输入(ISO 13314 + 效率法致密化)。None 表数据不足。

    eps_d=致密化应变(效率 η=W/σ 全局峰,限 ε>0.1);comp_EA_to_d=∫F·dδ
    截到 δ_d=ε_d·H0(关键:不积满全曲线,否则 SEA 虚高);sigma_pl=平台应力。
    """
    disp = np.asarray(disp, float)
    force = np.asarray(force, float)
    ok = np.isfinite(disp) & np.isfinite(force) & (disp >= 0)
    disp, force = disp[ok], force[ok]
    if len(disp) < 8:                       # 数据不足(空/极少)直接判不可用
        return None
    order = np.argsort(disp)
    disp, force = disp[order], force[order]
    uniq = np.concatenate([[True], np.diff(disp) > 1e-9])
    disp, force = disp[uniq], force[uniq]
    if len(disp) < 8:
        return None
    eps, sig = disp / H0, force / A0
    eps_max = float(eps.max())
    g = np.linspace(0.0, eps_max, n_grid)
    sg = _smooth(np.interp(g, eps, sig))
    W = np.concatenate([[0.0], np.cumsum(0.5 * (sg[1:] + sg[:-1])
                                         * np.diff(g))])
    with np.errstate(divide='ignore', invalid='ignore'):
        eta = np.where(sg > 1e-9, W / sg, 0.0)
    mask = g > 0.1
    densified, eps_d = False, eps_max
    if mask.any():
        idx = np.flatnonzero(mask)[int(np.argmax(eta[mask]))]
        eps_d = float(g[idx])
        densified = bool(idx < len(g) - 3 and eps_d < 0.98 * eps_max)
    d_d = eps_d * H0
    wd = disp <= d_d
    comp_EA_to_d = (float(np.trapezoid(force[wd], disp[wd]))
                    if wd.sum() >= 2 else 0.0)
    comp_EA_full = float(np.trapezoid(force, disp))
    lo, hi = 0.20, min(0.40, eps_d)
    pm = (g >= lo) & (g <= hi)
    sigma_pl = (float(np.trapezoid(sg[pm], g[pm]) / (hi - lo))
                if pm.sum() >= 2 and hi > lo else None)
    return {'eps_d': eps_d, 'eps_max': eps_max, 'sigma_pl': sigma_pl,
            'comp_EA_to_d': comp_EA_to_d, 'comp_EA_full': comp_EA_full,
            'densified': densified, 'plateau_window': [lo, round(hi, 4)]}


def results_to_checks_crush(job_dir, spec):
    """显式压溃产物 → (checks, summary)。SEA/comp_EA 仅在五硬门全过时进 margin。"""
    with open(os.path.join(job_dir, 'job_meta.json'),
              encoding='utf-8') as f:
        meta = json.load(f)
    nx, ny, nz = meta.get('lattice_array', [1, 1, 1])
    H0, A0 = CELL_H * nz, CELL_A * nx * ny
    V0 = A0 * H0
    feat = parse_feature_data(os.path.join(job_dir, 'feature_data.txt'))
    energy = parse_energy_data(os.path.join(job_dir, 'energy_data.txt'))
    spec = spec or {}
    metric = str(spec.get('margin_metric', '')).lower()
    is_ea = ('ea' in metric) or ('sea' in metric) or ('吸能' in metric)
    try:
        rho_rel = float(feat['header'].get('density'))
    except (TypeError, ValueError):
        rho_rel = spec.get('rho_rel')
    material = spec.get('material', 'PA12')
    rho_solid = _RHO_SOLID_G_MM3.get(material, _RHO_SOLID_G_MM3['PA12'])

    cm = crush_metrics(feat['disp'], feat['force'], H0, A0)
    ke, ae, cf = (energy.get('ratio_max'), energy.get('ratio_allae'),
                  energy.get('contact_frac'))
    ke_ok = (ke is not None and ke <= CRUSH_KE_GATE)
    ae_ok = (ae is None) or (ae <= CRUSH_AE_GATE)
    cf_ok = (cf is None) or (cf <= CRUSH_CONTACT_GATE)
    dens_ok = bool(cm and cm['densified'])
    gates_pass = bool(cm and ke_ok and ae_ok and cf_ok and dens_ok)

    checks = [
        {'dimension': 'mechanics', 'tool': 'abaqus.crush.energy_gate',
         'value': (round(ke, 6) if ke is not None else None),
         'threshold': CRUSH_KE_GATE, 'pass': bool(ke_ok),
         'source': ENERGY_GATE_SOURCE + ';DynaCompre 显式→HARD 门',
         'source_type': 'vendor', 'status': 'computed',
         'caveats': ['ALLKE/ALLIE≤5% 准静态有效性(显式动态为硬门)']},
        {'dimension': 'mechanics', 'tool': 'abaqus.crush.hourglass_gate',
         'value': (round(ae, 6) if ae is not None else None),
         'threshold': CRUSH_AE_GATE, 'pass': bool(ae_ok),
         'source': 'ALLAE/ALLIE 沙漏/人工能(C3D10M 弯曲屈曲下 EA 失真判据)',
         'source_type': 'vendor',
         'status': ('computed' if ae is not None else 'needs_input'),
         'caveats': ([] if ae is not None
                     else ['无 ALLAE 历史,沙漏门未验证(留痕)'])},
        {'dimension': 'mechanics', 'tool': 'abaqus.crush.contact_stability',
         'value': (round(cf, 6) if cf is not None else None),
         'threshold': CRUSH_CONTACT_GATE, 'pass': bool(cf_ok),
         'source': '(ALLVD+ALLFD)/ALLIE 接触/黏性耗散占比(稳定性代理)',
         'source_type': 'vendor',
         'status': ('computed' if cf is not None else 'needs_input'),
         'caveats': ['穿透<单元尺寸不可从能量历史判定,代理量留 caveat']},
        {'dimension': 'mechanics', 'tool': 'abaqus.crush.densification',
         'value': (round(cm['eps_d'], 4) if cm else None),
         'threshold': None, 'pass': dens_ok, 'source': ISO13314,
         'source_type': 'abaqus_fea',
         'status': ('computed' if cm else 'out_of_domain'),
         'caveats': ([] if dens_ok
                     else ['未检出内部效率峰:未压到致密化,SEA 不可认证'])},
    ]
    base_cav = list(meta.get('caveats', []))
    if not gates_pass:
        base_cav.append('硬有效性门未全过 → SEA/comp_EA 仅 screening,不进 margin')

    sea, m_solid = None, 0.0
    if cm:
        if cm['sigma_pl'] is not None:
            checks.append({
                'dimension': 'mechanics',
                'tool': 'abaqus.crush.plateau_stress',
                'value': round(cm['sigma_pl'], 4), 'threshold': None,
                'pass': None, 'source': ISO13314 + f";窗 {cm['plateau_window']}",
                'source_type': 'abaqus_fea', 'status': 'computed',
                'caveats': [], 'margin_eligible': False})
        m_solid = rho_solid * V0 * (rho_rel or 0.0)
        sea = (cm['comp_EA_to_d'] / m_solid) if m_solid > 0 else None
        band = _SEA_BAND_KJ.get(material, _SEA_BAND_KJ['PA12'])
        in_band = (sea is not None
                   and band[0] <= sea / 1000.0 <= band[1])
        n1 = (nx == 1 and ny == 1 and nz == 1)
        sea_cav = base_cav + ['SEA=实心杆质量归一(非包络);积分截到致密化']
        if sea is not None and not in_band:
            sea_cav.append(f'SEA {sea/1000:.1f} kJ/kg 超出 {material} '
                           f'合理带 {band} kJ/kg(errata E4)→ 不进 margin,'
                           '复核(多因 n=1 边界高估/模型偏硬/速率)')
        if n1:
            sea_cav.append('n=1 单胞:平台直载边界效应高估 SEA,'
                           '代表性值须 n≥3 阵列')
        checks.append({
            'dimension': 'mechanics', 'tool': 'abaqus.crush.SEA',
            'value': (round(sea, 2) if sea is not None else None),
            'threshold': None, 'pass': (in_band if sea is not None else None),
            'source': f'∫F·dδ 截到 ε_d={cm["eps_d"]:.3f} ÷ 实心质量'
                      f'(ρ_{material}·V0·ρ̄={m_solid:.5g} g),单位 J/kg',
            'source_type': 'abaqus_fea', 'status': 'computed',
            'caveats': sea_cav,
            'margin_eligible': bool(gates_pass and is_ea
                                    and sea is not None and in_band)})
        checks.append({
            'dimension': 'mechanics', 'tool': 'abaqus.crush.comp_EA',
            'value': round(cm['comp_EA_to_d'], 4), 'threshold': None,
            'pass': None,
            'source': f'∫F·dδ 截到 ε_d(全曲线={cm["comp_EA_full"]:.1f} 仅对照)',
            'source_type': 'abaqus_fea', 'status': 'computed',
            'caveats': base_cav,
            'margin_eligible': bool(gates_pass and is_ea)})

    summary = {'eps_d': (cm['eps_d'] if cm else None),
               'sigma_pl': (cm['sigma_pl'] if cm else None),
               'comp_EA_to_d': (cm['comp_EA_to_d'] if cm else None),
               'comp_EA_full': (cm['comp_EA_full'] if cm else None),
               'SEA_J_per_kg': (round(sea, 2) if sea is not None else None),
               'SEA_in_band': (None if not cm or sea is None
                               else bool(_SEA_BAND_KJ.get(
                                   material, _SEA_BAND_KJ['PA12'])[0]
                                   <= sea / 1000.0 <=
                                   _SEA_BAND_KJ.get(
                                       material, _SEA_BAND_KJ['PA12'])[1])),
               'm_solid_g': round(m_solid, 6), 'rho_rel': rho_rel,
               'n1_cell': bool(nx == 1 and ny == 1 and nz == 1),
               'gates': {'ke': ke_ok, 'hourglass': ae_ok, 'contact': cf_ok,
                         'densified': dens_ok, 'all_pass': gates_pass},
               'is_energy_metric': is_ea, 'source_type': 'abaqus_fea'}
    return checks, summary
