#!/usr/bin/env python3
"""Compare NS3 x0.5 (post-processing scale) vs NEW (current material tune) vs experiment.
Auxetic + BCC, N=2."""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT

TOPOS = ['Auxetic', 'BCC']
SCALE = 0.5

fig, axes = plt.subplots(1, 2, figsize=(20, 7.5))

for ax, topo in zip(axes, TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))

    exp_max = 0.0; n_exp = 0
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            ax.plot(eps, sig, color='#1a9e1a', lw=2.0, alpha=0.95,
                    label=f'EXPERIMENT (3 spec)' if n_exp == 0 else None, zorder=10)
            m = (eps >= 0) & (eps <= 0.55)
            if m.any(): exp_max = max(exp_max, float(sig[m].max()))
            n_exp += 1

    ns3_max_scaled = 0.0
    if ns3 is not None:
        e, s = ns3[1], ns3[2] * SCALE
        ax.plot(e, s, color='#5599cc', lw=2.4, ls='-', alpha=0.95,
                label=f'NS3 x{SCALE} (E=1554.5, σ_y=33.97; rho={ns3[0]:.3f})', zorder=4)
        m = (e >= 0) & (e <= 0.55)
        if m.any(): ns3_max_scaled = float(s[m].max())

    new_max = 0.0
    if new_ is not None:
        e, s = new_[1], new_[2]
        ax.plot(e, s, color='#d62728', lw=2.0, ls='--', alpha=0.85,
                label=f'NEW current (E=1240, σ_y=17; rho={new_[0]:.3f})', zorder=3)
        m = (e >= 0) & (e <= 0.55)
        if m.any(): new_max = float(s[m].max())

    y_top = max(new_max, ns3_max_scaled, exp_max) * 1.18

    ax.set_title(f'{topo}  N=2  slider=8',
                 fontsize=14, fontweight='bold')
    ax.set_xlabel('strain', fontsize=12)
    ax.set_ylabel('stress [MPa]', fontsize=12)
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, y_top)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10, loc='upper left')

fig.suptitle('NS3 x0.5 (post-scale) vs NEW (material tune) vs EXPERIMENT',
             fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_ns3_scaled_vs_new.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
