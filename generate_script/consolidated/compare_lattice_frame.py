#!/usr/bin/env python3
"""Auxetic + BCC N=2 in correct (lattice) frame.
Experiment converted: eps = disp/H_lat, sig = F/A_lat (was disp/H_spec, F/A_spec).
Sim already in lattice frame, plotted as-is."""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT, CELL

TOPOS = ['Auxetic', 'BCC']
H_LAT = N * CELL          # 10
A_LAT = (N * CELL) ** 2   # 100

fig, axes = plt.subplots(1, 2, figsize=(20, 8))

for ax, topo in zip(axes, TOPOS):
    ns3 = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))

    n_exp = 0; m_exp = 0.0
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H_LAT, force / A_LAT)
            ax.plot(eps, sig, color='#1a7e1a', lw=2.2, alpha=0.95,
                    label=f'EXPERIMENT (3 spec, lattice frame)' if n_exp == 0 else None, zorder=10)
            m = (eps >= 0) & (eps <= 0.55)
            if m.any(): m_exp = max(m_exp, float(sig[m].max()))
            n_exp += 1

    if ns3 is not None:
        e, s = ns3[1], ns3[2]
        ax.plot(e, s * 0.6, color='#5599cc', lw=2.4, ls='-', alpha=0.95,
                label=f'NS3 x0.6  (rho={ns3[0]:.3f})', zorder=5)
        ax.plot(e, s * 0.5, color='#aaaaff', lw=1.8, ls='--', alpha=0.85,
                label=f'NS3 x0.5  (rho={ns3[0]:.3f})', zorder=4)
        ax.plot(e, s, color='#cccccc', lw=1.0, ls=':', alpha=0.6,
                label=f'NS3 raw  (rho={ns3[0]:.3f})', zorder=3)

    ax.set_title(f'{topo}  N=2  slider=8 - LATTICE FRAME (corrected)',
                 fontsize=14, fontweight='bold')
    ax.set_xlabel('strain  (eps = disp / 10)', fontsize=12)
    ax.set_ylabel('stress [MPa]  (sig = F / 100)', fontsize=12)
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, m_exp * 1.5)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11, loc='upper left')

fig.suptitle('Lattice-frame comparison: experiment converted to sim coordinate system',
             fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_lattice_frame.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
