"""Phase 0 Q2a 反推:能量 + 最大力 → SEA_required 与平台应力上限。

公式(HANDOFF §6):
    SEA_required [J/kg] = E / (ρ̄ · V · ρs)
    σ_plateau_max [Pa]  = F_max / A
注意:返回的是 SEA_required(不含 FoS);SEA_design = SEA_required × FoS
由 Phase 0 确认块计算,**后续 margin = pred/design,不得二次乘 FoS**。
缺体积/包络必须追问,不得默认。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physics_common import make_result

SRC = ('能量守恒定义式 SEA=E/m, m=rho_rel*V*rho_s;sigma_plateau<=F_max/A '
       '(HANDOFF §6 Q2a,定义式无需文献)')


def from_energy(energy_J, f_max_N=None, area_m2=None,
                rho_rel=None, volume_m3=None, rho_s_kg_m3=1010.0):
    """反推 SEA_required;缺关键输入返回 needs_input(绝不默认补值)。"""
    echo = dict(energy_J=energy_J, f_max_N=f_max_N, area_m2=area_m2,
                rho_rel=rho_rel, volume_m3=volume_m3,
                rho_s_kg_m3=rho_s_kg_m3)
    missing = [k for k, v in (('energy_J', energy_J), ('rho_rel', rho_rel),
                              ('volume_m3', volume_m3)) if not v]
    if missing:
        return make_result(None, 'needs_input', echo, SRC,
                           [f'缺关键输入 {missing},必须向用户追问'
                            '(落高/速度/对象质量/几何包络),不得默认'])
    if energy_J <= 0 or rho_rel <= 0 or volume_m3 <= 0 or rho_s_kg_m3 <= 0:
        return make_result(None, 'needs_input', echo, SRC, ['输入必须为正'])

    mass_kg = rho_rel * volume_m3 * rho_s_kg_m3
    sea_required = energy_J / mass_kg  # J/kg
    out = {'SEA_required_J_per_kg': sea_required,
           'SEA_required_kJ_per_kg': sea_required / 1000.0,
           'mass_kg': mass_kg}
    caveats = ['SEA_required 不含 FoS;SEA_design = SEA_required x FoS,'
               '此后 margin = pred/design,不得二次乘 FoS']
    if f_max_N and area_m2 and f_max_N > 0 and area_m2 > 0:
        out['sigma_plateau_max_Pa'] = f_max_N / area_m2
    else:
        caveats.append('未给 F_max/A,平台应力上限未约束,'
                       '若有受保护对象的最大减速度要求必须追问')
    return make_result(out, 'computed', echo, SRC, caveats)


if __name__ == '__main__':
    import json
    print(json.dumps(from_energy(50.0, f_max_N=2000.0, area_m2=0.01,
                                 rho_rel=0.2, volume_m3=0.001),
                     indent=2, ensure_ascii=False))
