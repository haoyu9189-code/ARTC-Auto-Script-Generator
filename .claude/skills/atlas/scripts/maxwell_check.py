"""Maxwell 数判据(只说倾向,不说判定 — HANDOFF 红线)。

M = b − 3j + 6(3D 铰接桁架):M≥0 倾向 stretch-dominated,
M<0 倾向 bending-dominated。**必要非充分**:FCCZ/FBCCZ 含竖直 strut
是反例(Nasim & Galvanetto 2021, MJF PA12 实验)。
来源:J.C. Maxwell 1864;现代形式 Deshpande, Ashby & Fleck,
Acta Mater. 49(6):1035-1040, 2001, DOI 10.1016/S1359-6454(00)00379-7。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physics_common import make_result

SRC = ('Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):'
       '1035-1040, 2001, DOI 10.1016/S1359-6454(00)00379-7')
CAVEAT = ('Maxwell 数是必要非充分判据,只输出倾向;FCCZ/FBCCZ 类含定向'
          'strut 的拓扑是已知反例(Nasim & Galvanetto 2021, MJF PA12)。'
          '最终力学行为以工具证据(beam-FEM/FEA/实验)为准')


def check(n_struts, n_joints):
    """b=杆数, j=节点数 → Maxwell 数与倾向(tendency,非判定)。"""
    echo = dict(n_struts=n_struts, n_joints=n_joints)
    if n_struts <= 0 or n_joints <= 0:
        return make_result(None, 'needs_input', echo, SRC, ['输入必须为正'])
    M = n_struts - 3 * n_joints + 6
    tendency = 'stretch-leaning' if M >= 0 else 'bending-leaning'
    return make_result({'maxwell_M': M, 'tendency': tendency},
                       'computed', echo, SRC, [CAVEAT])


if __name__ == '__main__':
    import json
    # Octet: b=36, j=14 -> M=0;BCC 单胞: b=8, j=9 -> M=-13
    print(json.dumps(check(36, 14), indent=2, ensure_ascii=False))
    print(json.dumps(check(8, 9), indent=2, ensure_ascii=False))
