#!/usr/bin/env python3
"""
为 4 个非 Auxetic 拓扑生成 N=3 校准对照脚本
  - BCC, Iso_truss, Kelvin, Octet_truss
  - cell_size = 5, radius = 0.5, slider = 8, analysis = StaCompre
  - lattice_array = (3, 3, 3)

输出到 generate_script/{Topology}/5/0p5/8/StaCompre/，与之前 Auxetic / Kelvin
试跑的目录结构一致。
"""

import os
import sys

# 让 import 找到顶层包
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from script_generator import AbaqusScriptGenerator


TOPOS = ['BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']
CELL_SIZE = 5
RADIUS    = 0.5
SLIDER    = 8
ANALYSIS  = 'StaCompre'
LATTICE   = (3, 3, 3)


def main():
    gen = AbaqusScriptGenerator()
    output_root = os.path.join(HERE, 'generate_script')
    os.makedirs(output_root, exist_ok=True)

    print(f'Output root: {output_root}')
    print(f'Topologies : {TOPOS}')
    print(f'Geometry   : cell={CELL_SIZE}, r={RADIUS}, slider={SLIDER}, '
          f'array={LATTICE}, analysis={ANALYSIS}')
    print()

    successes, failures = [], []
    for topo in TOPOS:
        print(f'>>> Generating {topo} ...')
        try:
            ok, msg, fn = gen.generate_script(
                cell_type     = topo,
                cell_size     = CELL_SIZE,
                cell_radius   = RADIUS,
                slider        = SLIDER,
                output_dir    = output_root,
                mode_type     = 'Compression',
                analysis_type = ANALYSIS,
                batch_mode    = False,
                lattice_array = LATTICE,
                flat_output   = False,
            )
        except Exception as e:
            ok, msg, fn = False, f'EXCEPTION: {e}', ''

        if ok:
            print(f'    OK   {fn}')
            successes.append((topo, fn))
        else:
            print(f'    FAIL {msg}')
            failures.append((topo, msg))

    print()
    print('=' * 60)
    print(f'Done.  success: {len(successes)}/{len(TOPOS)}   '
          f'fail: {len(failures)}/{len(TOPOS)}')
    if failures:
        for t, m in failures:
            print(f'  FAILED  {t}  -- {m}')


if __name__ == '__main__':
    main()
