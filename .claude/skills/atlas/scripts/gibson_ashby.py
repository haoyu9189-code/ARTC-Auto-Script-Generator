"""Gibson-Ashby / Deshpande-Fleck-Ashby 解析标度律(Tier-A 解析筛)。

勘误后数值(2026-06-10 调研核实,详见 atlas/research/RESEARCH.md §4):
- bending:  E*/Es ≈ ρ̄²(C1≈1);σy*/σys ≈ 0.3·ρ̄^1.5
  来源:Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997.
- stretch(octet,pin-jointed,立方轴向): E*/Es = (1/9)·ρ̄;σy*/σys = (1/3)·ρ̄
  来源:Deshpande, Fleck, Ashby, J. Mech. Phys. Solids 49(8):1747-1769,
  2001, DOI 10.1016/S0022-5096(01)00010-2.
- AM as-built 偏差:金属 l/d<5 时偏差可达 300%(Zhong et al., Curr. Opin.
  Solid State Mater. Sci. 27:101081, 2023, DOI 10.1016/j.cossms.2023.101081);
  聚合物偏差幅度查无文献来源,按内部工程估计 ±10–30% 标 inference。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physics_common import make_result

SRC_GA = ('Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 '
          '(bending: E*~rho^2, sigma_y*~0.3 rho^1.5)')
SRC_DFA = ('Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, '
           'DOI 10.1016/S0022-5096(01)00010-2 '
           '(octet pin-jointed: E*=(1/9) rho Es, sigma_y*=(1/3) rho sigma_ys)')
CAVEAT_AM_METAL = ('AM as-built 金属点阵 l/d<5 时解析律偏差可达 300% — '
                   'Zhong 2023, DOI 10.1016/j.cossms.2023.101081')
CAVEAT_AM_POLYMER = ('聚合物 AM as-built 偏差幅度无文献来源,'
                     '内部工程估计 ±10-30%(source_type=inference)')
CAVEAT_SCREENING = ('解析筛数值仅 screening only,不得通过 margin 门;'
                    'OOD 拓扑只有全 FEA(Tier-D)可授予设计参考级')


def estimate(topology_class, rho_rel, Es_MPa, sigma_ys_MPa,
             material_family='polymer'):
    """解析估算相对模量与相对强度。

    topology_class: 'stretch' | 'bending' | 'hybrid'
    返回 value = {'E_MPa':…, 'sigma_y_MPa':…, 'model':…}
    """
    echo = dict(topology_class=topology_class, rho_rel=rho_rel,
                Es_MPa=Es_MPa, sigma_ys_MPa=sigma_ys_MPa,
                material_family=material_family)
    if topology_class not in ('stretch', 'bending', 'hybrid'):
        return make_result(None, 'needs_input', echo,
                           SRC_GA, ['未知 topology_class'])
    if not (rho_rel > 0 and Es_MPa > 0 and sigma_ys_MPa > 0):
        return make_result(None, 'needs_input', echo, SRC_GA,
                           ['输入必须为正'])

    caveats = [CAVEAT_SCREENING,
               CAVEAT_AM_METAL if material_family == 'metal'
               else CAVEAT_AM_POLYMER]
    status = 'estimate'
    if not (0.01 <= rho_rel <= 0.5):
        status = 'out_of_domain'
        caveats.append('rho_rel 越出 G-A/DFA 标度律常用适用域 [0.01, 0.5]')

    if topology_class == 'stretch':
        E = (1.0 / 9.0) * rho_rel * Es_MPa
        sy = (1.0 / 3.0) * rho_rel * sigma_ys_MPa
        src, model = SRC_DFA, 'DFA octet (stretch)'
    elif topology_class == 'bending':
        E = rho_rel ** 2 * Es_MPa
        sy = 0.3 * rho_rel ** 1.5 * sigma_ys_MPa
        src, model = SRC_GA, 'Gibson-Ashby (bending)'
    else:  # hybrid:两族包络,取保守(低)值并报告区间
        E_b = rho_rel ** 2 * Es_MPa
        E_s = (1.0 / 9.0) * rho_rel * Es_MPa
        sy_b = 0.3 * rho_rel ** 1.5 * sigma_ys_MPa
        sy_s = (1.0 / 3.0) * rho_rel * sigma_ys_MPa
        E, sy = min(E_b, E_s), min(sy_b, sy_s)
        src = SRC_GA + ' + ' + SRC_DFA
        model = 'hybrid envelope (conservative min of bending/stretch)'
        caveats.append('hybrid 拓扑取两族下包络,区间上限 = '
                       f'E {max(E_b, E_s):.4g} MPa / '
                       f'sigma_y {max(sy_b, sy_s):.4g} MPa')

    return make_result({'E_MPa': E, 'sigma_y_MPa': sy, 'model': model},
                       status, echo, src, caveats)


if __name__ == '__main__':
    import json
    print(json.dumps(estimate('stretch', 0.1, 1700, 45), indent=2,
                     ensure_ascii=False))
