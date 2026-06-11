# -*- coding: utf-8 -*-
import json, io
SC = r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch'
P1 = json.load(io.open(SC + r'\part1.json', encoding='utf-8'))
P2 = json.load(io.open(SC + r'\part2.json', encoding='utf-8'))
P3 = json.load(io.open(SC + r'\part3.json', encoding='utf-8'))

notes = (
 '诚实条款结论: 本词汇表(Tier-1 检索 24 族 / Tier-1.5 插值 / TPMS 5 族x2 / Tier-2 realize_graph 商图)内, '
 '没有任何候选能在两种测量口径下稳健达到 overhang_area_fraction <= 0.05。全词汇表实测最好值: '
 'n=1 口径(round-1 B1 协议)0.09802(HSlabPillar k=6, 但其 n=3 非水密被杀), 有效候选最好 0.10896-0.10911;'
 'n=3 口径(spec n_cells=3)有效最好 0.05028(r2c1), 距容限差 0.00028(0.56%), 但同家族近邻参数散布 '
 '0.0503-0.0728 表明该值含 0.005 量级布尔重三角化噪声, 不能声称稳健达标。'
 '机理(实测确证, 脚本与中间数据在 r2_scratch/ 留痕): '
 '(1) check_overhangs 危险类 = 朝下且法向偏离正下方 >45 度的面: 圆柱侧面带按倾角贡献 25%(水平)-50%(>=45 度), '
 '节点球带约 37%, 这是杆系族 0.17-0.47 的内禀来源, 与 round-1 六杀和 PSCZ(>=50 度自支撑设计反而 0.47)完全一致;'
 '(2) 法向 z 精确为 0 的竖直面不计 downward(竖柱单体实测 0.0), 但 realize_graph 强制节点球切割使近竖直面'
 '重三角化后产生 1e-4 级法向抖动, 约半数翻为危险, 竖壁策略因此失效;'
 '(3) 水平板条(融合水平圆柱, pitch < r*sqrt2)底面扇贝法向全落在正下 45 度锥内, 被分类为安全且对 (2) 免疫, '
 'HSlabPillar 家族因此成为词汇表内唯一逼近 0.05 的构型。'
 '语义备注(留给阈值层 B7, 本层不改判): 该分类把陡峭/竖直朝下面记危险、水平底面记安全, 方向与 LPBF '
 '自支撑角 >=45 度的工程惯例相反;round-1/D1 全灭与本轮结果都是该 oracle 语义下的数学现实。'
 '给 Evaluator 的边界提示(非力学判断): 若以 n=3 口径并允许 >=0.6% 容差或鲁棒统计, r2c1 为边界可过候选;'
 '若严格 n=1 口径, 本案例在现词汇表内不可行, 需要板/壳基元词汇表扩展或构建方向/规则修订(均超出本层权限)。'
 '其余 B1 维度全部实测通过(r2c1/r2c2: 双轨水密 + B1 validate、min_feature p5 1.031/1.012 >= 1.0、困粉 0.0;'
 'r2c3: n=1 全过, n=3 非水密为 A1 引擎平铺缺口)。')

out = {
 'spec_ref': {'key': 'lpbf_bracket', 'process': 'LPBF', 'material': 'AlSi10Mg', 'n_cells': 3, 'high_risk': True,
              'round': 2,
              'objective_override': 'orchestrator round-2 指令: 最小化 overhang_area_fraction(B1 实测), 2-3 候选',
              'margin_metric_spec': 'comp_EA(库内同单位代理), design_value_with_fos=60.0; margin 判定归 Evaluator'},
 'diversity': {'tiers': ['2', '1.5'],
               'topology_families': ['HSlabPillar(novel graph, 水平板条+竖柱)', 'Cubic(DB 家族)'],
               'tendency_mix_note': ('r2c1/r2c2 C4 M=2 stretch-leaning(必要非充分, 熔合后按板-柱解读);'
                                     'Cubic 力学倾向判定归 Surrogate;round-2 目标覆写常规 3 族发散要求, '
                                     '收敛为悬垂最优家族 + 对照锚, 理由见 notes')},
 'generator_notes': [
   '本层只保证几何合法 + 可实现 + 查重留痕 + B1 实测数字;力学归 Surrogate/Evaluator, 阈值规则归 B7',
   ('所有 overhang 数字 = printability.check_overhangs(LPBF, build_dir z)对焊接 trimesh 实测, '
    'n=1 与 n=3 双口径并报;round-1 c1 0.2658 在本管线精确复现, 口径可比')],
 'candidates': [P1['r2c1'], P1['r2c2'], P2['r2c3']],
 'killed': P3['killed'],
 'notes': notes}

path = r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\candidates_round2.json'
with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
    f.write('\n')
d = json.load(io.open(path, encoding='utf-8'))
print('written', path)
print('candidates:', [(c['id'], c['tier']) for c in d['candidates']], '| killed:', len(d['killed']))
for c in d['candidates']:
    print(c['id'], c['lineage']['measured_overhang_area_fraction'])
