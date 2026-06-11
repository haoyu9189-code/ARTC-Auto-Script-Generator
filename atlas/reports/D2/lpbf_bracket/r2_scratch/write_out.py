# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r'D:\ARTC\ARTC-Auto-Script')
SC = r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch'
AE = json.load(open(SC + r'\gates_novelty_AE.json', encoding='gbk'))
FS = json.load(open(SC + r'\final_suite.json', encoding='utf-8'))
CU = json.load(open(SC + r'\final_cubic.json', encoding='utf-8'))

B1_NOTE = ('B1 实测口径: printability.check_overhangs(process=LPBF, build_dir=(0,0,1)), '
           '焊接 trimesh;n=1 = round-1 B1 检查口径(c1 0.2658 完全复现), n=3 = spec n_cells 口径;'
           '容限 0.05 为内部工程取值(inference, 输出须降级标注)')

def gates_block(g, c9_n1, c9_n3):
    det = {}
    for k in ('C1','C2','C3','C4','C5','C6','C7','C8'):
        gg = g['gates'][k]
        det[k] = {'pass': gg['pass'], 'hard': gg['hard'], 'value': gg['value'], 'flags': gg['flags']}
    return {'passed': g['passed'], 'hard_failures': g['hard_failures'],
            'detail': det,
            'C9_realization': {'engine': 'atlas.geometry.realize_graph',
                               'n1': c9_n1, 'n3': c9_n3},
            'flags_carryover': g['flags']}

mk_b1 = lambda d: {k: d[k] for k in d if k != 'stats'}

A = AE['A']
c1n1 = FS['c1_slab']['n1']; c1n3 = FS['c1_slab']['n3']
r2c1 = {
 'id': 'r2c1', 'tier': '2',
 'geometry': {'graph_doc': A['doc']},
 'rho_rel': c1n1['stats']['rho_rel'],
 'rho_notes': {'mesh_n1': c1n1['stats']['rho_rel'], 'mesh_n3': c1n3['stats']['rho_rel'],
               'first_order_C5_at_default_r': A['gates']['gates']['C5']['value']['rho_estimate_at_default_r'],
               'note': '一阶估算忽略节点/融合重叠(高估);定稿密度以 mesh 为准, n3 值含边界效应'},
 'features': {'note': 'OOD 新图: 禁用 cell-DB 最近邻 surrogate, 力学裁判须物理计算(beam/shell-FEM 或均质化, HANDOFF s11);本层不做力学判断。spec margin_metric=comp_EA(design_value_with_fos=60.0)的判定归 Evaluator'},
 'gates': gates_block(A['gates'],
     {'ok': True, 'watertight': True, 'faces': c1n1['stats']['faces'], 'volume_mm3': c1n1['stats']['volume_mm3']},
     {'ok': True, 'watertight': True, 'faces': c1n3['stats']['faces'], 'volume_mm3': c1n3['stats']['volume_mm3']}),
 'novelty': {'wl_hash': A['novelty']['wl_hash'], 'duplicate_of': None,
             'statement': 'ATLAS 索引范围内未发现重复(WL 同构查重 vs seed 拓扑索引)',
             'note': 'r2c1 与 r2c2 同一商图拓扑(WL hash 相同), 仅 free_params 半径不同 - 参数兄弟, 非独立新拓扑'},
 'printability_measured_B1': {'note': B1_NOTE, 'n1': mk_b1(c1n1), 'n3': mk_b1(c1n3)},
 'lineage': {
   'tier': 'tier2', 'generator': 'atlas-candidate-generator/D2-round2',
   'source': ('round-2 反悬垂设计 HSlabPillar: 水平板条(5 根沿 x 的融合水平圆柱 rs=0.75, y-pitch 1.0 < rs*sqrt2)'
              '+链向 y-tie(r=0.52, 全埋入板条)+单根竖柱(r=0.52, S0 自环)承担 z 连通。'
              '机理: 板条底面扇贝法向全部落在正下方 45 度锥内(check_overhangs 分类为安全), 对布尔重三角化的'
              '近竖直面法向抖动翻转免疫;竖柱是唯一受翻转影响的暴露面, 已压到 C3 允许的最小量(1 根/胞)'),
   'design_probes': {'vertical_cyl': 0.0, 'horizontal_cyl': 0.2766, 'diag45_cyl': 0.4765, 'sphere': 0.3655,
                     'fused_vertical_wall': 0.0,
                     'note': '单基元 check_overhangs 实测(r2_scratch/survey1.py);竖直面法向 z 分量精确为 0 时不计 downward'},
   'measured_overhang_area_fraction': {'n1': 0.10911, 'n3': 0.05028,
       'vs_threshold_0.05': 'n1 FAIL(2.2x); n3 FAIL(超 0.00028, 即 0.56%)',
       'noise_caveat': '同家族近邻参数 n3 实测散布 0.0503-0.0728(布尔重三角化对近竖直面的 1e-4 级法向抖动, 半随机翻转), 该 0.050 是家族地板而非可调参数'},
   'scripts': 'atlas/reports/D2/lpbf_bracket/r2_scratch/ 下 survey1.py t2_walls.py t2_slab.py final_suite.py',
   'maxwell_from_C4': {'M': 2, 'tendency': 'stretch-leaning',
                       'caveat': '必要非充分, 只说倾向;82 对杆熔合(C6), 按熔合后板-柱结构解读'},
   'd1_d2_lessons': 'round-1 六杀消化: 杆系斜杆/节点球内禀 0.25-0.47;竖壁策略被 realize_graph 强制节点球的面污染否决(实测 0.26-0.34, 见 killed);水平板条是该词汇表内唯一逼近 0.05 的家族'}
}

E = AE['E']
r2c2 = {
 'id': 'r2c2', 'tier': '2',
 'geometry': {'graph_doc': E['doc']},
 'rho_rel': 0.38102,
 'rho_notes': {'mesh_n1': 0.38102, 'mesh_n3': 0.33893,
               'first_order_C5_at_default_r': E['gates']['gates']['C5']['value']['rho_estimate_at_default_r'],
               'note': '同 r2c1;rs=0.80 加厚板条多埋竖柱根部, 换 rho +0.03'},
 'features': {'note': '同 r2c1: OOD 新图, 力学归物理裁判'},
 'gates': gates_block(E['gates'],
     {'ok': True, 'watertight': True, 'note': 'B1 validate_mesh pass; min_feature p5=1.012 pass; powder trapped=0'},
     {'ok': True, 'watertight': True}),
 'novelty': {'wl_hash': E['novelty']['wl_hash'], 'duplicate_of': None,
             'statement': 'ATLAS 索引范围内未发现重复(WL 同构查重 vs seed 拓扑索引)',
             'note': '与 r2c1 同一商图拓扑的参数兄弟(rs=0.80, r_tie/pillar=0.51), 作为对布尔噪声的鲁棒性备份'},
 'printability_measured_B1': {'note': B1_NOTE,
   'n1': {'overhang_area_fraction': 0.10896, 'overhang_pass_vs_0.05': False,
          'min_feature_p5_mm': 1.012, 'min_feature_pass': True,
          'trapped_void_mm3': 0.0, 'powder_pass': True, 'watertight_b1': True},
   'n3': {'overhang_area_fraction': 0.05567, 'overhang_pass_vs_0.05': False, 'realize_watertight': True}},
 'lineage': {
   'tier': 'tier2', 'generator': 'atlas-candidate-generator/D2-round2',
   'source': 'r2c1 的参数变体(板条加厚 rs=0.80, 柱/tie 0.51): 牺牲 rho 换竖柱暴露高度下降;同机理同脚本',
   'measured_overhang_area_fraction': {'n1': 0.10896, 'n3': 0.05567,
       'vs_threshold_0.05': 'n1 FAIL; n3 FAIL(超 11%)'},
   'scripts': 'atlas/reports/D2/lpbf_bracket/r2_scratch/t2_slab.py(变体 E_k5_rs080_r051)'}
}

json.dump({'r2c1': r2c1, 'r2c2': r2c2}, open(SC + r'\part1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('part1 ok')
