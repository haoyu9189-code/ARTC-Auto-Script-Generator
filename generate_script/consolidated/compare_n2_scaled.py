#!/usr/bin/env python3
"""Same as compare_n2_full but NEW sim stress is scaled x0.5 to match experiment magnitude."""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, TOPOS, N, CONS, GENROOT

SCALE = 0.5

fig, axes = plt.subplots(2, 3, figsize=(22, 12))
axes = axes.flatten()

for ax, topo in zip(axes, TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))
    ns4   = parse_sim(os.path.join(CONS, 'simulation','NewSession4',topo,f'N{N}','feature_data.txt'))

    if ns4 is not None:
        ax.plot(ns4[1], ns4[2] * SCALE, color='#bbbbbb', lw=1.0, ls=':', alpha=0.7,
                label=f'OLD NS4 x{SCALE} (rho={ns4[0]:.3f})', zorder=1)
    if ns3 is not None:
        ax.plot(ns3[1], ns3[2] * SCALE, color='#5599cc', lw=1.4, ls='--', alpha=0.8,
                label=f'OLD NS3 x{SCALE} (rho={ns3[0]:.3f})', zorder=2)
    if new_ is not None:
        ax.plot(new_[1], new_[2] * SCALE, color='#d62728', lw=2.0, ls='-', alpha=0.9,
                label=f'NEW x{SCALE} (rho={new_[0]:.3f})', zorder=3)

    n_exp = 0; exp_max = 0.0
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            ax.plot(eps, sig, color='#1a9e1a', lw=2.0, alpha=1.0,
                    label='EXPERIMENT (3 spec)' if n_exp == 0 else None, zorder=10)
            exp_max = max(exp_max, float(sig.max()) if sig.size else 0.0)
            n_exp += 1

    ax.set_title(f'{topo}  N=2  slider=8', fontsize=13, fontweight='bold')
    ax.set_xlabel('strain', fontsize=11)
    ax.set_ylabel('stress [MPa]', fontsize=11)
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, exp_max * 1.5 if exp_max > 0 else None)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc='upper left')

axes[5].axis('off')
axes[5].text(0.0, 0.95,
    f'All simulation curves scaled x{SCALE}\n'
    'to match experiment peak magnitude.\n\n'
    'NEW = E=1240 + NS3-original everything else\n'
    'NS3 = original NewSession3 baseline\n'
    'NS4 = old NewSession4 (sphere=1.2 etc)\n\n'
    'Focus: shape comparison only.',
    family='monospace', fontsize=11, verticalalignment='top')

fig.suptitle(
    f'N=2 (slider=8): SIMULATION x{SCALE} vs experiment - SHAPE comparison',
    fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_n2_scaled.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
