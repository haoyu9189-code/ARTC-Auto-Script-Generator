"""PA12 lattice SEA 合理性带核验(勘误后:0.3–8 kJ/kg,原 2–15 过乐观)。

依据(2026-06-10 调研核实):实测 MJF PA12 octet @ρ̄=0.30 SEA 仅
0.63–0.92 kJ/kg;G-A 能量估算给 PA12 准静态上限 ~6–8 kJ/kg;
文献中 >10 kJ/kg 的值属金属点阵。带本身为内部工程界
(source_type=inference),组成依据带源列出。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physics_common import make_result

BAND_LO, BAND_HI = 0.3, 8.0
TYPICAL_LO, TYPICAL_HI = 0.5, 4.0
SRC = ('内部工程界 0.3-8 kJ/kg(source_type=inference),组成依据:'
       '实测 MJF PA12 octet @rho=0.30 SEA 0.63-0.92 kJ/kg;'
       'G-A 能量估算 PA12 准静态上限 ~6-8 kJ/kg;'
       '>10 kJ/kg 文献值属金属点阵(见 atlas/research/RESEARCH.md §4);'
       'PA12 TPMS 标度锚 Chen 2023, DOI 10.1039/D2MA00972B')


def check(sea_kj_per_kg, material='PA12', loading='quasi-static'):
    """SEA 设计值/预测值合理性分级:ok / atypical / implausible。"""
    echo = dict(sea_kj_per_kg=sea_kj_per_kg, material=material,
                loading=loading)
    caveats = []
    if material.upper() != 'PA12' or loading != 'quasi-static':
        caveats.append('合理性带仅针对 PA12 准静态压缩标定,'
                       '其它材料/工况此带不适用')
        return make_result({'verdict': 'unknown_domain',
                            'band_kj_per_kg': None},
                           'out_of_domain', echo, SRC, caveats)
    if sea_kj_per_kg is None or sea_kj_per_kg <= 0:
        return make_result(None, 'needs_input', echo, SRC, ['SEA 必须为正'])

    if sea_kj_per_kg > BAND_HI:
        verdict = 'implausible'
        caveats.append(f'>{BAND_HI} kJ/kg 对 PA12 准静态不合理;'
                       '>10 kJ/kg 的文献值属金属点阵')
    elif sea_kj_per_kg < BAND_LO:
        verdict = 'below_band'
        caveats.append(f'<{BAND_LO} kJ/kg 低于实测下界,'
                       '可能密度过低或未充分压实')
    elif TYPICAL_LO <= sea_kj_per_kg <= TYPICAL_HI:
        verdict = 'ok_typical'
    else:
        verdict = 'ok_atypical'
        caveats.append(f'在带内但偏离典型区 {TYPICAL_LO}-{TYPICAL_HI} kJ/kg')

    return make_result({'verdict': verdict,
                        'band_kj_per_kg': [BAND_LO, BAND_HI],
                        'typical_kj_per_kg': [TYPICAL_LO, TYPICAL_HI]},
                       'computed', echo, SRC, caveats)


if __name__ == '__main__':
    import json
    for v in (2.5, 12.0, 0.1):
        print(json.dumps(check(v), indent=2, ensure_ascii=False))
