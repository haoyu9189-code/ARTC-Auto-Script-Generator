"""单页报表生成器:每个设计案例 → 一张 A4 HTML(打印/转 PDF 即成品)。

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
        rows.append(
            f'<tr{cls}><td>{t["candidate_id"]}</td>'
            f'<td>T{t["tier"]}</td><td>{topo}</td>'
            f'<td>{rho if rho is not None else "—"}</td>'
            f'<td>{f"{ratio:.2f}" if ratio else "无证据"}</td>'
            f'<td><span class="mbar"><i style="width:{pct:.0f}%;'
            f'background:{col}"></i><b></b></span></td>'
            f'<td><span class="vd {t["verdict"]}">'
            f'{t["verdict"].replace("SCREENING_PASS", "SCREEN")}'
            f'</span></td></tr>')

    tr_rows = []
    for c in winner['trace']['checks']:
        mark = {True: '<span class="ok">✓</span>',
                False: '<span class="no">✗</span>',
                None: '<span class="info">ℹ</span>'}[c['pass']]
        tr_rows.append(
            f'<tr><td>{c["dimension"]}</td>'
            f'<td>{c["tool"].split(".")[-1][:26]}</td>'
            f'<td>{fmt_val(c["value"])[:42]}</td><td>{mark}</td>'
            f'<td class="src">{c["source"][:46]}</td></tr>')

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
            kv.append(('Maxwell M(倾向,非判定)',
                       f"{c['value'].get('maxwell_M')} · "
                       f"{c['value'].get('tendency')}"))
        if c['dimension'] == 'density':
            kv.append(('相对密度 ρ̄(网格实算)', f"<b>{c['value']}</b>"))
        if c['tool'].endswith('nearest_by_density+comp_EA'):
            kv.append(('库内最近邻 comp_EA',
                       f"<b>{fmt_val(c['value'])}</b> mJ"))
            if c.get('applicability_distance') is not None:
                kv.append(('applicability 距离',
                           f"{c['applicability_distance']:.4f}"))
        if c['tool'] == 'gibson_ashby.estimate' and isinstance(
                c['value'], dict):
            kv.append(('G–A 解析 E*(screening)',
                       f"{c['value'].get('E_MPa', 0):.1f} MPa"))
    m = winner['trace'].get('margin')
    if m:
        kv.append(('margin(pred/design,已含 FoS)',
                   f"<b>{m['ratio']:.2f}</b>"))
    kv_rows = ''.join(f'<div class="kv"><span class="k">{k}</span>'
                      f'<span class="v">{v}</span></div>'
                      for k, v in kv[:8])

    buckets = {'doi': set(), 'vendor': set(), 'inf': set()}
    for j in judged:
        for c in j['trace']['checks']:
            b = SRC_BUCKET.get(c.get('source_type', 'internal_computed'),
                               'vendor')
            buckets[b].add(c['source'][:64])
    src_html = {k: ''.join(f'<li>{s}</li>' for s in sorted(v)[:6])
                or '<li>—</li>' for k, v in buckets.items()}

    zero_pass = not passing
    extra_foot = ('本案例无候选通过全部硬性检查,推荐表如实呈现;'
                  '出路见判决依据。' if zero_pass else '')
    spec_line = (f"{spec['process']} / {spec['material']} · 阵列 n="
                 f"{spec['n_cells']} · FoS {spec['fos']}(已含) · "
                 f"design {spec['design_value_with_fos']}"
                 f"({spec['margin_metric']}) · 置信度 "
                 f"{spec['confidence_level']}")
    return {
        '__CASE_TITLE__': case['title'],
        '__CASE_KEY__': case['key'].upper(),
        '__SPEC_LINE__': spec_line,
        '__RISK_BADGE__': ('<span class="badge-risk">⚠ 高风险场景 · '
                           '仅作筛选</span>' if case['high_risk'] else ''),
        '__DATE__': date.today().isoformat(),
        '__CAND_ROWS__': ''.join(rows),
        '__MARGIN_NOTE__': ('margin 度量为库内 comp_EA 同单位代理'
                            '(绝对单位映射待标定,inference 级,已降级);'
                            '中线 = 1.0 及格门。'),
        '__TRACE_WHO__': f"候选 {winner['trace']['candidate_id']}"
                         f"(Tier-{winner['trace']['tier']})",
        '__TRACE_ROWS__': ''.join(tr_rows),
        '__WIRE_NAME__': w_topo,
        '__WIRE_SVG__': svg,
        '__WIRE_CAP__': f'{w_topo} · {nseg} struts · 5.0 mm cell · '
                        'atlas.geometry 管线真实几何',
        '__KV_ROWS__': kv_rows,
        '__SRC_DOI__': src_html['doi'],
        '__SRC_VENDOR__': src_html['vendor'],
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
