"""B6:strut 商图 → 现有 ABAQUS 管线适配器(Tier-D 终审入口)。

管线原生输入 = structure_set 文本格式(±2.5 原生坐标 + cylinders 列表),
ScriptGenerator._get_structure_data 是唯一注入点(参数校验不设拓扑白名单)。

商图 → 装饰文本的关键:枚举每条商图边与单胞盒相交的全部周期像
(平移 c ∈ Z³),端点自动落在 frac 0/1 边界(PLAN B6 "跨界边经边界节点")。
装饰惯例与 999 个 DB 结构的生成方式一致:边界杆由相邻胞重复绘制,
Abaqus 模板合并实例时熔合 —— 单胞 FEA 模型因此几何完备
(只发射商图原始边会丢失边界上属于邻胞像的杆,如 Cubic 12 缺 9)。

范围:StaCompre / DynaCompre(剪切需 X 旋转,归 Phase 2,显式拒绝)。
"""
import os
import sys

import numpy as np

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_NATIVE_HALF = 2.5   # structure_set 原生 ±2.5 坐标系
_TOL = 1e-9


def _segment_intersects_unit_box(p1, p2, tol=_TOL, min_overlap=1e-6):
    """线段(分数坐标)与 [0,1]³ 盒相交且盒内长度为正(slab 裁剪)。

    正长度要求排除"点接触"的邻胞像(只碰角点/端点贴面的外来杆),
    保留贴面而有正长度的杆(Cubic 棱在面上,装饰惯例包含)。
    """
    d = p2 - p1
    t0, t1 = 0.0, 1.0
    for k in range(3):
        if abs(d[k]) < 1e-15:
            if p1[k] < -tol or p1[k] > 1 + tol:
                return False
        else:
            ta = (-tol - p1[k]) / d[k]
            tb = (1 + tol - p1[k]) / d[k]
            lo, hi = min(ta, tb), max(ta, tb)
            t0, t1 = max(t0, lo), min(t1, hi)
            if t0 > t1:
                return False
    return (t1 - t0) > min_overlap


def graph_to_structure_text(doc):
    """atlas-cell-graph/1.0 → 管线消费的装饰结构文本。

    返回 (text, stats)。节点名 P0..Pk 按位置排序(确定性)。
    """
    from atlas.schema import validate_graph
    validate_graph(doc)
    pos = {n['id']: np.asarray(n['frac'], float) for n in doc['nodes']}

    segments = set()
    max_shift = max((max(abs(s) for s in e['shift'])
                     for e in doc['edges']), default=0)
    rng = range(-max_shift - 1, max_shift + 2)
    for e in doc['edges']:
        a = pos[e['n1']]
        b = pos[e['n2']] + np.asarray(e['shift'], float)
        for cx in rng:
            for cy in rng:
                for cz in rng:
                    c = np.array([cx, cy, cz], float)
                    p1, p2 = a + c, b + c
                    if not _segment_intersects_unit_box(p1, p2):
                        continue
                    key = tuple(sorted((tuple(np.round(p1, 6)),
                                        tuple(np.round(p2, 6)))))
                    segments.add(key)

    points = sorted({pt for seg in segments for pt in seg})
    name_of = {pt: f'P{i}' for i, pt in enumerate(points)}

    lines = []
    for pt in points:
        mm = [round(x * 2 * _NATIVE_HALF - _NATIVE_HALF, 6) for x in pt]
        lines.append(f'{name_of[pt]} = [{mm[0]}, {mm[1]}, {mm[2]}]')
    lines.append('cylinders = [')
    for seg in sorted(segments):
        lines.append(f'({name_of[seg[0]]}, {name_of[seg[1]]}),')
    lines.append(']')
    text = '\n'.join(lines)
    stats = {'points': len(points), 'segments': len(segments),
             'quotient_edges': len(doc['edges'])}
    return text, stats


class GraphScriptGenerator:
    """注入自定义结构文本的 ScriptGenerator 包装。"""

    def __init__(self, doc):
        from script_generator import AbaqusScriptGenerator
        self._doc = doc
        text, self.stats = graph_to_structure_text(doc)
        self._text = text
        gen = AbaqusScriptGenerator()
        outer = self

        def _get_structure_data(cell_type, slider=4,
                                analysis_type='StaCompre'):
            if analysis_type in ('StaShear',) or \
                    analysis_type.startswith('DynaShear'):
                raise NotImplementedError(
                    '剪切需 X 旋转适配,归 Phase 2 — 不静默假装支持')
            return gen._parse_structure_output(outer._text)

        gen._get_structure_data = _get_structure_data
        self._gen = gen

    def generate(self, cell_radius=None, cell_size=None,
                 analysis_type='StaCompre', output_dir=None,
                 lattice_array=(1, 1, 1)):
        doc = self._doc
        radius = (cell_radius if cell_radius is not None
                  else doc['default_radius_mm'])
        size = (cell_size if cell_size is not None
                else doc['cell']['size_mm'])
        ok, msg, filename = self._gen.generate_script(
            cell_type=doc.get('name', 'atlas_graph'),
            cell_size=size, cell_radius=radius,
            slider=int(doc.get('free_params', {})
                       .get('slider', {}).get('value', 4)),
            output_dir=output_dir, mode_type='Compression',
            analysis_type=analysis_type, flat_output=True,
            lattice_array=lattice_array)
        return {'ok': bool(ok), 'message': msg, 'filename': filename,
                'output_dir': output_dir, 'adapter_stats': self.stats,
                'source': 'atlas.abaqus_adapter(复用 script_generator 管线)'}


def generate_abaqus_script(doc, output_dir, **kw):
    """便捷入口:商图 → preprocess/postprocess/run.pbs 三件套。"""
    return GraphScriptGenerator(doc).generate(output_dir=output_dir, **kw)
