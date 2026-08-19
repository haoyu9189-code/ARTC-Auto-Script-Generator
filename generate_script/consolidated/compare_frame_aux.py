#!/usr/bin/env python3
"""Auxetic N=2 single-panel: specimen-frame vs lattice-frame experiment overlay."""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT, CELL

TOPO = 'Auxetic'
H_LAT = N * CELL          # 10
A_LAT = (N * CELL) ** 2   # 100

new_  = parse_sim(os.path.join(GENROOT, TOPO, '5','0p5','8','StaCompre','feature_data.txt'))
ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{TOPO}__baseline',f'N{N}','feature_data.txt'))

fig, ax = plt.subplots(figsize=(13, 8))

# experiment in BOTH frames
n0 = n1 = 0; max_lat = 0
for sub, csvp in find_exp(TOPO):
    names, dims, specs = parse_exp(csvp)
    for k, (force, disp) in enumerate(specs):
        if force.size == 0 or k >= len(dims): continue
        T, W, H = dims[k]
        if T <= 0 or W <= 0 or H <= 0: continue
        # specimen frame (current/old)
        e1, s1 = trim_exp(disp / H, force / (T * W))
        ax.plot(e1, s1, color='#a8d8a8', lw=1.6, alpha=0.7,
                label=f'EXP specimen frame (H={H:.1f}, A={T*W:.1f})' if n0 == 0 else None, zorder=8)
        # lattice frame (corrected)
        e2, s2 = trim_exp(disp / H_LAT, force / A_LAT)
        ax.plot(e2, s2, color='#1a7e1a', lw=2.4, alpha=0.95,
                label=f'EXP lattice frame (H={H_LAT}, A={A_LAT}) <- corrected' if n1 == 0 else None, zorder=10)
        m = (e2 >= 0) & (e2 <= 0.55)
        if m.any(): max_lat = max(max_lat, float(s2[m].max()))
        n0 += 1; n1 += 1

if ns3 is not None:
    ax.plot(ns3[1], ns3[2] * 0.5, color='#5599cc', lw=2.2, ls='-', alpha=0.95,
            label=f'NS3 x0.5  (rho={ns3[0]:.3f})', zorder=5)
    ax.plot(ns3[1], ns3[2] * 0.6, color='#aaaaff', lw=1.6, ls=':', alpha=0.85,
            label=f'NS3 x0.6  (rho={ns3[0]:.3f})', zorder=4)
if new_ is not None:
    ax.plot(new_[1], new_[2], color='#d62728', lw=1.8, ls='--', alpha=0.85,
            label=f'NEW current  (E=1240, σ_y=17; rho={new_[0]:.3f})', zorder=3)

ax.set_title(f'{TOPO}  N=2  —  EXP in two frames + sim candidates',
             fontsize=14, fontweight='bold')
ax.set_xlabel('strain', fontsize=12)
ax.set_ylabel('stress [MPa]', fontsize=12)
ax.set_xlim(0, 0.55)
ax.set_ylim(0, max_lat * 1.4)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=10, loc='upper left')

plt.tight_layout()
out = os.path.join(CONS, 'compare_frame_aux.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
