"""单页报表生成器:每个设计案例 → 一张 16:9 英文 HTML(打印/转 PDF 即成品)。

数据 = D1 验收管线真实判决(候选→四维验证→确定性引擎);
线框 = parse_structure 真实几何的服务端 SVG(打印不糊);
红线文案固化在模板页脚。用法:
    python atlas/reports/report_page.py            # 三案例全出
"""
import json
import os
import sys
from datetime import date

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     '..', '..'))
sys.path.insert(0, _ROOT)

from atlas.geometry import parse_structure
from atlas.orchestration.acceptance import CASES, run_case

OUT_DIR = os.path.join(_ROOT, 'atlas', 'reports', 'D1')
TMPL = os.path.join(os.path.dirname(__file__),
                    'atlas_report_template.html')

SRC_BUCKET = {'academic_doi': 'doi', 'vendor': 'vendor',
              'internal_fea': 'vendor', 'internal_computed': 'vendor',
              'beam_fem_calibrated': 'vendor', 'inference': 'inf'}

import re as _re

DOI_RE = _re.compile(r'10\.\d{4,9}/[A-Za-z0-9()./:_-]+')
DOI_CITE = {
    '10.1016/S0022-5096(01)00010-2':
        'Deshpande, Fleck & Ashby 2001, JMPS — octet stretch scaling',
    '10.1016/S1359-6454(00)00379-7':
        'Deshpande, Ashby & Fleck 2001, Acta Mater — Maxwell criterion',
    '10.1016/j.cossms.2023.101081':
        'Zhong et al. 2023, COSSMS — AM as-built deviation (metal l/d<5)',
    '10.3390/polym17202804':
        'Raz et al. 2025, Polymers — MJF powder-removal vs density',
    '10.1039/D2MA00972B':
        'Chen et al. 2023, Mater. Adv. — PA12 TPMS scaling anchor',
    '10.1073/pnas.2003504118':
        'Lumpe & Stankovic 2021, PNAS — crystal-net catalog',
}
INF_HINTS = ('inference', '内部工程', '越域', '代理', '降级', '无文献')

# 报表为英文版面:管线证据串(中文原文)仅在显示层翻译,trace 本体不动。
# 顺序敏感:长串在前,避免短前缀截胡。
EN_MAP = (
    ('LPBF AlSi10Mg 航空支架点阵填充',
     'LPBF AlSi10Mg aerospace bracket lattice infill'),
    ('SLS PA12 吸能缓冲块', 'SLS PA12 energy-absorber block'),
    ('MJF PA12 auxetic 缓冲垫', 'MJF PA12 auxetic cushioning pad'),
    ('comp_EA(库内同单位代理)', 'comp_EA, in-DB same-unit proxy'),
    ('Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2',
     'Onck/Andrews 2001 boundary-layer mechanism (atlas/references); '
     'correction-engine wiring under P2'),
    ('manifold3d watertight 体积 / 胞体积',
     'manifold3d watertight volume / cell volume'),
    ('trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,',
     'trimesh edge-face count + manifold3d Mesh.merge round-trip '
     'status (dual-engine, '),
    ('本机验证)', 'verified locally)'),
    ('困粉: embree 列射线奇偶填充 + scipy flood-fill(',
     'Trapped powder: embree column-ray parity fill + scipy '
     'flood-fill ('),
    ('正负对照验证)', 'pos/neg control verified)'),
    ('自支撑角: LPBF 自支撑角行业共识区间(EOS/SLM Solutions 设计指南);'
     '容限: 内部工程容限:临界角以下面积占比 ≤5% 视为可接受'
     '(节点附近局部小面不可避免);无文献支撑;方法: 面法向分类'
     '(毫秒级,bench 验证)',
     'Self-support angle: LPBF industry-consensus range (EOS/SLM '
     'Solutions design guides); tolerance: internal engineering limit '
     '— sub-critical-angle area fraction ≤5% acceptable (small local '
     'faces near nodes unavoidable); no literature support; method: '
     'face-normal classification (ms-scale, bench-verified)'),
    ('阈值: 内部保守取值;文献设计指南给 0.4-0.6 mm(约保守 2 倍),'
     '记录在案后续可论证放宽;方法: embree 射线测厚'
     '(bench 验证 BCC d=1.0 误差 0.1-0.5%)',
     'Threshold: internal conservative value; published design guides '
     'give 0.4-0.6 mm (~2x conservative), on record for argued '
     'relaxation; method: embree ray thickness probe (bench: BCC '
     'd=1.0 error 0.1-0.5%)'),
    ('内部工程假设,查无文献出处(2026-06-10 调研);中期应以 Zhong 2023 '
     'effective-strut-diameter 框架替代,',
     'Internal engineering assumption, no literature source found '
     '(surveyed 2026-06-10); mid-term: replace with Zhong 2023 '
     'effective-strut-diameter framework,'),
    ('粉末床聚合物无需支撑,悬垂检查不适用(skip)',
     'Powder-bed polymer needs no supports; overhang check not '
     'applicable (skip)'),
    ('聚合物 AM as-built 偏差幅度无文献来源,内部工程估计 ±10-30%'
     '(source_type=inference)',
     'Polymer AM as-built deviation magnitude lacks a literature '
     'source; internal engineering estimate ±10-30% '
     '(source_type=inference)'),
    ("输出时必须标'内部工程假设(无文献支撑)'并降级",
     "Output must carry 'internal engineering assumption (no "
     "literature support)' tag and be downgraded"),
    ('阈值为内部工程取值(inference),输出须降级标注',
     'Threshold is an internal engineering value (inference); output '
     'must be downgraded'),
    ('面积分数容限为内部工程取值(inference),输出须降级标注',
     'Area-fraction tolerance is an internal engineering value '
     '(inference); output must be downgraded'),
    ('P2-5 原始曲线自提', 'P2-5 raw-curve self-extraction'),
    ('应变割线(含惯性瞬态,非弹性模量,Phase 3 滤波后重提)',
     'strain secant (incl. inertial transient, not elastic modulus; '
     're-extract after Phase 3 filtering)'),
    ('dyna_yield=首个局部峰应力(落锤动态屈服代理)',
     'dyna_yield=first local peak stress (drop-weight dynamic yield '
     'proxy)'),
    ('peak 取前 30% 应变窗;剪切面积=名义 25mm²(约定);'
     '曲线源=内部 Abaqus 显式管线(步长 ~0.1mm)',
     'peak from first 30% strain window; shear area = nominal 25 mm² '
     '(convention); curve source = internal Abaqus explicit pipeline '
     '(~0.1 mm step)'),
    ('阈值: ', 'Threshold: '),
    ('容限: ', 'Tolerance: '),
)


def _en(s):
    """显示层中→英翻译(只影响报表文本,不改 trace 数据)。"""
    for zh, en in EN_MAP:
        s = s.replace(zh, en)
    return s


def wire_svg(topology, slider=4, w=560, h=380):
    """真实几何 → 深度排序线框 SVG(等轴侧投影)。"""
    coords, cyls = parse_structure(topology, slider)
    segs = [(coords[a], coords[b]) for a, b in cyls
            if a in coords and b in coords]
    ay, ax = 0.62, 0.42
    cy, sy = np.cos(ay), np.sin(ay)
    cx, sx = np.cos(ax), np.sin(ax)

    def proj(p):
        X = p[0] * cy + p[1] * sy
        Yd = -p[0] * sy + p[1] * cy
        Ys = p[2] * cx - Yd * sx
        D = p[2] * sx + Yd * cx
        return X, Ys, D

    P = [(proj(p1), proj(p2)) for p1, p2 in segs]
    xs = [v for a, b in P for v in (a[0], b[0])]
    ys = [v for a, b in P for v in (a[1], b[1])]
    sc = min((w - 60) / (max(xs) - min(xs) + 1e-9),
             (h - 60) / (max(ys) - min(ys) + 1e-9))
    cxm = (max(xs) + min(xs)) / 2
    cym = (max(ys) + min(ys)) / 2
    items = sorted(P, key=lambda ab: (ab[0][2] + ab[1][2]) / 2)
    zs = [(a[2] + b[2]) / 2 for a, b in items]
    zmin, zmax = min(zs), max(zs) + 1e-9
    lines = []
    for (a, b), z in zip(items, zs):
        d = (z - zmin) / (zmax - zmin)
        x1 = w / 2 + (a[0] - cxm) * sc
        y1 = h / 2 - (a[1] - cym) * sc
        x2 = w / 2 + (b[0] - cxm) * sc
        y2 = h / 2 - (b[1] - cym) * sc
        col = f'rgb({150 + int(80 * d)},{100 + int(50 * d)},0)'
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" stroke="{col}" '
            f'stroke-width="{1.1 + 2.4 * d:.2f}" '
            f'stroke-linecap="round" opacity="{0.45 + 0.55 * d:.2f}"/>')
    return (f'<svg viewBox="0 0 {w} {h}" '
            f'xmlns="http://www.w3.org/2000/svg">'
            + ''.join(lines) + '</svg>'), len(segs)


def fmt_val(v):
    if isinstance(v, dict):
        return '; '.join(f'{k}={vv}' for k, vv in list(v.items())[:2])
    if isinstance(v, float):
        return f'{v:.4g}'
    return str(v)


def build_case(case, judged):
    spec = case['spec']
    # 冠选:margin 最高的 PASS,否则首个候选(零通过页也要出报表)
    passing = [j for j in judged if j['trace']['verdict'] == 'PASS'
               and j['trace'].get('margin')]
    winner = (max(passing, key=lambda j: j['trace']['margin']['ratio'])
              if passing else judged[0])
    w_geo = winner['candidate'].get('geometry', {})
    w_topo = w_geo.get('topology') or w_geo.get('graph_doc', {}).get(
        'name', '?')

    rows = []
    for j in judged:
        t = j['trace']
        geo = j['candidate'].get('geometry', {})
        topo = geo.get('topology') or geo.get('graph_doc', {}).get(
            'name', '?')
        rho = next((c['value'] for c in t['checks']
                    if c['dimension'] == 'density'), None)
        m = t.get('margin')
        ratio = m['ratio'] if m else None
        pct = 0 if ratio is None else min(ratio / 2 * 100, 100)
        col = ('var(--green)' if t['verdict'] == 'PASS'
               else 'var(--amber)' if (ratio or 0) >= 1
               else 'var(--red)')
        cls = ' class="winner"' if j is winner else ''
        vlabel = t['verdict'].replace('SCREENING_PASS', 'SCREEN')
        rows.append(
            f'<tr{cls}><td>{t["candidate_id"]}</td>'
            f'<td>T{t["tier"]}</td><td>{topo}</td>'
            f'<td>{rho if rho is not None else "—"}</td>'
            f'<td>{f"{ratio:.2f}" if ratio else "no evid."}</td>'
            f'<td><span class="mbar"><i style="width:{pct:.0f}%;'
            f'background:{col}"></i><b></b></span></td>'
            f'<td><span class="vd {vlabel}">{vlabel}</span></td></tr>')

    tr_rows = []
    for c in winner['trace']['checks']:
        mark = {True: '<span class="ok">✓</span>',
                False: '<span class="no">✗</span>',
                None: '<span class="info">ℹ</span>'}[c['pass']]
        tr_rows.append(
            f'<tr><td>{c["dimension"]}</td>'
            f'<td>{c["tool"].split(".")[-1][:26]}</td>'
            f'<td>{_en(fmt_val(c["value"]))[:42]}</td><td>{mark}</td>'
            f'<td class="src">{_en(c["source"])[:46]}</td></tr>')

    svg, nseg = wire_svg(w_topo) if w_geo.get('topology') else ('', 0)
    if not svg and 'graph_doc' in w_geo:
        from atlas.abaqus_adapter import graph_to_structure_text
        text, _ = graph_to_structure_text(w_geo['graph_doc'])
        # 简易解析复用
        import re as _re
        coords, segs = {}, []
        in_c = False
        for ln in text.split('\n'):
            ln = ln.strip()
            if 'cylinders = [' in ln:
                in_c = True
                continue
            if in_c and ln == ']':
                in_c = False
                continue
            if '=' in ln and not in_c:
                k, v = ln.split('=', 1)
                coords[k.strip()] = eval(v.strip())
        svg, nseg = '', 0  # graph 案例线框略(D1 三案例冠选均为目录拓扑)

    kv = []
    for c in winner['trace']['checks']:
        if c['dimension'] == 'topology_tendency' and isinstance(
                c['value'], dict):
            kv.append(('Maxwell M (tendency only)',
                       f"{c['value'].get('maxwell_M')} · "
                       f"{c['value'].get('tendency')}"))
        if c['dimension'] == 'density':
            kv.append(('Rel. density ρ̄ (mesh-true)',
                       f"<b>{c['value']}</b>"))
        if c['tool'].endswith('nearest_by_density+comp_EA'):
            kv.append(('In-DB nearest comp_EA',
                       f"<b>{fmt_val(c['value'])}</b> mJ"))
            if c.get('applicability_distance') is not None:
                kv.append(('Applicability distance',
                           f"{c['applicability_distance']:.4f}"))
        if c['tool'] == 'gibson_ashby.estimate' and isinstance(
                c['value'], dict):
            kv.append(('G–A analytic E* (screening)',
                       f"{c['value'].get('E_MPa', 0):.1f} MPa"))
    m = winner['trace'].get('margin')
    if m:
        kv.append(('Margin (pred/design, FoS incl.)',
                   f"<b>{m['ratio']:.2f}</b>"))
    kv_rows = ''.join(f'<div class="kv"><span class="k">{k}</span>'
                      f'<span class="v">{v}</span></div>'
                      for k, v in kv[:8])

    buckets = {'doi': set(), 'vendor': set(), 'inf': set()}
    for j in judged:
        for c in j['trace']['checks']:
            blob = c['source'] + ' ' + ' '.join(c.get('caveats', []))
            # 学术 DOI:从证据串正则抽取并映射为规范引用
            for doi in DOI_RE.findall(blob):
                doi = doi.rstrip('.,;)')
                buckets['doi'].add(
                    f"{DOI_CITE.get(doi, 'Literature')} · DOI {doi}")
            if 'Gibson' in blob or 'G-A' in blob:
                buckets['doi'].add('Gibson & Ashby 1997, Cellular '
                                   'Solids 2nd ed. — bending scaling')
            if 'Maxwell' in blob:
                buckets['doi'].add(DOI_CITE[
                    '10.1016/S1359-6454(00)00379-7'] +
                    ' · DOI 10.1016/S1359-6454(00)00379-7')
            # 标记推测:source_type=inference 或 caveat 含降级线索
            if c.get('source_type') == 'inference':
                buckets['inf'].add(_en(c['source'])[:70])
            for cv in c.get('caveats', []):
                if any(h in cv for h in INF_HINTS):
                    buckets['inf'].add(_en(cv)[:70])
            b = SRC_BUCKET.get(c.get('source_type', 'internal_computed'),
                               'vendor')
            buckets[b].add(_en(c['source'])[:64])
    # 常驻推测项:margin 单位代理(本报表度量定义自带)
    buckets['inf'].add('Margin unit proxy: comp_EA absolute-unit mapping '
                       'pending calibration (inference, downgraded)')
    src_html = {k: ''.join(f'<li>{s}</li>' for s in sorted(v)[:6])
                or '<li>—</li>' for k, v in buckets.items()}
    vendor_inline = ' · '.join(sorted(buckets['vendor'])[:5]) or '—'

    zero_pass = not passing
    extra_foot = ('No candidate passed every hard check in this case; '
                  'the table reports this honestly — see the verdict '
                  'basis for the way forward.' if zero_pass else '')
    spec_line = (f"{spec['process']} / {spec['material']} · array n="
                 f"{spec['n_cells']} · FoS {spec['fos']} (included) · "
                 f"design {spec['design_value_with_fos']} "
                 f"({_en(spec['margin_metric'])}) · confidence: "
                 f"{spec['confidence_level']}")
    return {
        '__CASE_TITLE__': _en(case['title']),
        '__CASE_KEY__': case['key'].upper(),
        '__SPEC_LINE__': spec_line,
        '__RISK_BADGE__': ('<span class="badge-risk">⚠ HIGH-RISK '
                           'APPLICATION · SCREENING ONLY</span>'
                           if case['high_risk'] else ''),
        '__DATE__': date.today().isoformat(),
        '__CAND_ROWS__': ''.join(rows),
        '__MARGIN_NOTE__': ('Margin metric is an in-DB comp_EA same-unit '
                            'proxy (absolute unit mapping pending '
                            'calibration — flagged inference, '
                            'downgraded); centre line = 1.0 pass gate.'),
        '__TRACE_WHO__': f"CANDIDATE {winner['trace']['candidate_id']}"
                         f" (TIER-{winner['trace']['tier']})",
        '__TRACE_ROWS__': ''.join(tr_rows),
        '__WIRE_NAME__': w_topo,
        '__WIRE_SVG__': svg,
        '__WIRE_CAP__': f'{w_topo} · {nseg} struts · 5.0 mm cell · '
                        'real pipeline geometry (atlas.geometry)',
        '__KV_ROWS__': kv_rows,
        '__SRC_DOI__': src_html['doi'],
        '__SRC_VENDOR_INLINE__': vendor_inline,
        '__SRC_INF__': src_html['inf'],
        '__EXTRA_FOOT__': extra_foot,
    }


def render_all(out_dir=OUT_DIR):
    tmpl = open(TMPL, encoding='utf-8').read()
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for case in CASES:
        judged = run_case(case)
        ctx = build_case(case, judged)
        html = tmpl
        for k, v in ctx.items():
            html = html.replace(k, v)
        p = os.path.join(out_dir, f"report_{case['key']}.html")
        open(p, 'w', encoding='utf-8', newline='\n').write(html)
        paths.append(p)
        print('written', p)
    return paths


if __name__ == '__main__':
    render_all()
