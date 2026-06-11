# -*- coding: utf-8 -*-
import json, io
SC = r'D:\ARTC\ARTC-Auto-Script\atlas\reports\D2\lpbf_bracket\r2_scratch'
P1 = json.load(io.open(SC + r'\part1.json', encoding='utf-8'))
CU = json.load(io.open(SC + r'\final_cubic.json', encoding='utf-8'))
B1_NOTE = P1['r2c1']['printability_measured_B1']['note']

r2c3 = {
 'id': 'r2c3', 'tier': '1.5',
 'geometry': {'topology': 'Cubic', 'slider': 0.0, 'radius_mm': 0.55, 'cell_size_mm': 5.0},
 'rho_rel': CU['n1']['rho_mesh'],
 'rho_notes': {'mesh_n1_decorated': CU['n1']['rho_mesh'], 'mesh_n3': CU['n3']['rho_mesh'],
               'note': ('装饰胞边界杆被邻胞共享, n1 体积偏大;n3 0.17885 更接近周期真值;'
                        'DB structures 行存在但 density_smoothed=NULL, 无库内值可引')},
 'features': {'note': ('DB 221 行 Cubic 样本存在, 但 comp_stiffness/comp_EA 静压特征全 NULL'
                       '(round-1 检索杀的原因), 无库内特征可引;力学估算归 Surrogate(物理或跨族迁移路径), '
                       'margin 判定归 Evaluator')},
 'gates': {'applicable': False,
           'note': ('库内拓扑家族 A1 引擎实现(generate_cell, 默认 sphere_ratio), 生成期图门 C1-C8 不适用;'
                    '实现自检: n1 双轨水密 True;n3 双轨水密 False(A1 引擎装饰胞平铺切相退化, '
                    '工程缺口留痕, 非本候选可调参数)')},
 'novelty': {'applicable': False, 'note': 'Tier-1.5 库内家族几何, 非新拓扑'},
 'printability_measured_B1': {'note': B1_NOTE, 'n1': CU['n1'], 'n3': CU['n3'],
   'caveat': 'n3 overhang 0.20648 在非水密网格上测得, 仅供参考'},
 'lineage': {
   'tier': 'tier1.5', 'generator': 'atlas-candidate-generator/D2-round2',
   'source': ('24 拓扑全家族 overhang 普查(slider 0/4, r=0.55, n=1, r2_scratch/survey1.py)最优者: '
              'Cubic 0.1707(次优 G7 0.2476, CBCC 0.2478;round-1 候选 Iso_truss 0.2658 复现)。'
              '竖杆面精确竖直不计 downward, 危险面 = 水平杆 45-90 度侧带(2/3 杆长水平所致), '
              'sphere_ratio 0.9-1.0 仅差 0.002;round-1 曾以 Tier-1 检索身份被杀(comp_stiffness 行数 0), '
              '本轮按 round-2 目标以几何身份复活留痕'),
   'measured_overhang_area_fraction': {'n1': 0.17073, 'n3': 0.20648,
       'vs_threshold_0.05': 'n1 FAIL(3.4x); n3 FAIL(4.1x, 非水密网格参考值)'},
   'role': '对照锚: 词汇表内可检索家族的悬垂下限, 供 Evaluator 量化新图收益(0.171 -> 0.050)'}
}
with io.open(SC + r'\part2.json', 'w', encoding='utf-8') as f:
    json.dump({'r2c3': r2c3}, f, ensure_ascii=False, indent=1)
print('part2 ok')
