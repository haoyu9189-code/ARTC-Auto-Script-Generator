#!/usr/bin/env python3
"""
Consolidated 24-topology stress-strain overview.
Same 6×4 grid structure and N-color scheme as NewSession3/all_24_combined.png.

Data sources (read from consolidated/):
  NS4 (primary)  — solid line, lw=2.2  — sphere×1.2, cleanest (97% complete)
  NS3 baseline   — dashed line, lw=1.3 — baseline (no sphere variant)
  NS2 original_6 — dotted line, lw=1.0 — legacy 6 topologies only

Background: green = NS4 has all N=1..5 | yellow = 3–4 | red = <3
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

CONS = os.path.dirname(os.path.abspath(__file__))
CELL_SIZE = 5.0
STRAIN_CUT = 0.25

CELL_TYPES = [
    'AFCC',        'Auxetic',   'BCC',              'BCCZ',
    'CBCC',        'Cubic',     'CubicRosette',     'Cuboctahedron_Z',
    'Diamond',     'DiamondPlus','FBCCXYZ',          'FBCCZ',
    'FCC',         'FCCZ',      'G7',               'Iso_truss',
    'Kelvin',      'Octahedron','Octet_truss',       'Rhombic',
    'Tetrahedron_base','Truncated_cube','Truncated_Octoctahedron','WeairePhelan',
]
EXCLUDED = {'CBCC', 'Cubic', 'FCCZ', 'Truncated_cube', 'G7'}
N_COLORS = {1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c', 4: '#d62728', 5: '#9467bd'}


def path_ns4(ct, n):
    return os.path.join(CONS, 'simulation', 'NewSession4', ct, f'N{n}', 'feature_data.txt')


def path_ns3_baseline(ct, n):
    return os.path.join(CONS, 'simulation', 'NewSession3', f'{ct}__baseline', f'N{n}', 'feature_data.txt')


def path_ns2_orig(ct, n):
    return os.path.join(CONS, 'simulation', 'NewSession2', 'original_6', ct, f'N{n}', 'feature_data.txt')


def parse(path):
    if not os.path.exists(path):
        return None, None
    d, f = [], []
    started = False
    with open(path, errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if 'X' in line and '_temp_3' in line:
                started = True
                continue
            if not started:
                continue
            parts = line.split()
            if len(parts) == 2:
                try:
                    d.append(float(parts[0]))
                    f.append(float(parts[1]))
                except ValueError:
                    pass
    return (np.array(d), np.array(f)) if len(d) > 5 else (None, None)


fig, axes = plt.subplots(6, 4, figsize=(24, 30))
axes = axes.flatten()

ns4_total = ns3_total = ns2_total = 0

for idx, ct in enumerate(CELL_TYPES):
    ax = axes[idx]
    ns4_n_ok = 0

    for n in [1, 2, 3, 4, 5]:
        L = n * CELL_SIZE
        A = (n * CELL_SIZE) ** 2
        col = N_COLORS[n]

        # NS4 — solid primary
        d4, f4 = parse(path_ns4(ct, n))
        if d4 is not None:
            strain4, stress4 = d4 / L, f4 / A
            complete4 = len(d4) >= 190
            lw4 = 2.2 if complete4 else 1.4
            ls4 = '-' if complete4 else '--'
            alpha4 = 0.95 if complete4 else 0.65
            ax.plot(strain4, stress4, linestyle=ls4, color=col,
                    linewidth=lw4, alpha=alpha4, zorder=3)
            if complete4:
                ns4_n_ok += 1
                ns4_total += 1

        # NS3 baseline — dashed secondary
        d3, f3 = parse(path_ns3_baseline(ct, n))
        if d3 is not None:
            ax.plot(d3 / L, f3 / A, linestyle=(0, (4, 3)), color=col,
                    linewidth=1.3, alpha=0.55, zorder=2)
            ns3_total += 1

        # NS2 original_6 — dotted (only 6 topologies)
        d2, f2 = parse(path_ns2_orig(ct, n))
        if d2 is not None:
            ax.plot(d2 / L, f2 / A, linestyle=':', color=col,
                    linewidth=1.0, alpha=0.45, zorder=1)
            ns2_total += 1

    ax.axvline(x=STRAIN_CUT, color='k', linestyle=':', linewidth=0.8, alpha=0.25)
    ax.set_xlim(0, 0.65)
    ax.tick_params(labelsize=7)
    ax.set_xlabel('ε (strain)', fontsize=7)
    ax.set_ylabel('σ (MPa)', fontsize=7)
    ax.grid(True, alpha=0.2)

    # Background: based on NS4 N=1..5 availability
    n_any_ns4 = sum(1 for n in [1,2,3,4,5] if parse(path_ns4(ct, n))[0] is not None)
    if n_any_ns4 == 5:
        bg = '#c8e6c9'
    elif n_any_ns4 >= 3:
        bg = '#fff9c4'
    else:
        bg = '#ffcdd2'
    ax.set_facecolor(bg)

    # Red spine for excluded topologies (same as NS3 convention)
    title_color = 'red' if ct in EXCLUDED else 'black'
    status_str = f'NS4:{ns4_n_ok}/5'
    ax.set_title(f'{ct}\n[{status_str}]', fontsize=9, fontweight='bold',
                 color=title_color)
    if ct in EXCLUDED:
        for spine in ax.spines.values():
            spine.set_edgecolor('red')
            spine.set_linewidth(2.5)

# Shared legend: N colors + line-style session key
legend_handles = []
for n in [1, 2, 3, 4, 5]:
    legend_handles.append(
        mlines.Line2D([], [], color=N_COLORS[n], linewidth=2.0,
                      label=f'N = {n}'))
legend_handles.append(mlines.Line2D([], [], color='gray', linewidth=2.2,
                                     linestyle='-', label='NS4  (solid, primary)'))
legend_handles.append(mlines.Line2D([], [], color='gray', linewidth=1.3,
                                     linestyle=(0, (4, 3)), label='NS3 baseline (dash)'))
legend_handles.append(mlines.Line2D([], [], color='gray', linewidth=1.0,
                                     linestyle=':', label='NS2 orig-6  (dot)'))
fig.legend(handles=legend_handles, loc='lower center', ncol=8,
           fontsize=9, frameon=True, bbox_to_anchor=(0.5, 0.0))

fig.suptitle(
    'Consolidated — 24 Topologies  (NewSession2 / NS3 / NS4)\n'
    f'NS4 curves: {ns4_total} | NS3 baseline: {ns3_total} | NS2 orig-6: {ns2_total}\n'
    'bg Green = NS4 all N=1..5 | Yellow = 3–4 | Red = <3 | RED FRAME = excluded from ΔSEA (CBCC/Cubic/FCCZ/Trunc_cube/G7)',
    fontsize=12, fontweight='bold')
plt.tight_layout(rect=[0, 0.045, 1, 0.965])
out = os.path.join(CONS, 'all_sessions_combined.png')
plt.savefig(out, dpi=140)
print(f'Saved: {out}')
print(f'NS4: {ns4_total} curves | NS3 baseline: {ns3_total} | NS2 orig-6: {ns2_total}')
