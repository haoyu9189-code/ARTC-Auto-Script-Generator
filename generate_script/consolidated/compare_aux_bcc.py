#!/usr/bin/env python3
"""Auxetic + BCC N=2: NEW vs NS3 baseline vs experiment (raw + x0.5 scaled)."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT

TOPOS = ['Auxetic', 'BCC']

fig, axes = plt.subplots(2, 2, figsize=(18, 11))

for row, topo in enumerate(TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))

    # collect experiment
    exp_curves = []
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            exp_curves.append((eps, sig, sub))

    for col, scale in enumerate([1.0, 0.5]):
        ax = axes[row, col]
        if ns3 is not None:
            ax.plot(ns3[1], ns3[2] * scale, color='#5599cc', lw=1.8, ls='--', alpha=0.85,
                    label=f'NS3 baseline x{scale}  (rho={ns3[0]:.3f})', zorder=2)
        if new_ is not None:
            ax.plot(new_[1], new_[2] * scale, color='#d62728', lw=2.4, ls='-', alpha=0.95,
                    label=f'NEW x{scale}  (rho={new_[0]:.3f})', zorder=3)

        exp_max = 0.0
        for i, (eps, sig, sub) in enumerate(exp_curves):
            ax.plot(eps, sig, color='#1a9e1a', lw=2.0, alpha=0.95,
                    label=f'EXPERIMENT' if i == 0 else None, zorder=10)
            exp_max = max(exp_max, float(sig.max()) if sig.size else 0.0)

        title_suffix = ' (raw)' if scale == 1.0 else f' (sim x{scale})'
        ax.set_title(f'{topo}  N=2{title_suffix}', fontsize=13, fontweight='bold')
        ax.set_xlabel('strain', fontsize=11)
        ax.set_ylabel('stress [MPa]', fontsize=11)
        ax.set_xlim(0, 0.55)
        if scale == 1.0:
            ax.set_ylim(0, exp_max * 3.0 if exp_max > 0 else None)
        else:
            ax.set_ylim(0, exp_max * 1.5 if exp_max > 0 else None)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10, loc='upper left')

fig.suptitle('Auxetic & BCC  N=2 (slider=8): NEW vs NS3 baseline vs EXPERIMENT',
             fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_aux_bcc.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
