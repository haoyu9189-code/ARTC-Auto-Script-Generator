#!/usr/bin/env python3
"""Auxetic-only N=2 shape comparison: NEW x0.5 vs NS3 x0.5 vs NS4 x0.5 vs experiment."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT

SCALE = 0.5
TOPO = 'Auxetic'

new_  = parse_sim(os.path.join(GENROOT, TOPO, '5','0p5','8','StaCompre','feature_data.txt'))
ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{TOPO}__baseline',f'N{N}','feature_data.txt'))
ns4   = parse_sim(os.path.join(CONS, 'simulation','NewSession4',TOPO,f'N{N}','feature_data.txt'))

fig, ax = plt.subplots(figsize=(11, 7.5))

if ns4 is not None:
    ax.plot(ns4[1], ns4[2] * SCALE, color='#bbbbbb', lw=1.2, ls=':', alpha=0.8,
            label=f'OLD NS4 x{SCALE}  (rho={ns4[0]:.3f})', zorder=1)
if ns3 is not None:
    ax.plot(ns3[1], ns3[2] * SCALE, color='#5599cc', lw=1.8, ls='--', alpha=0.85,
            label=f'OLD NS3 baseline x{SCALE}  (rho={ns3[0]:.3f})', zorder=2)
if new_ is not None:
    ax.plot(new_[1], new_[2] * SCALE, color='#d62728', lw=2.4, ls='-', alpha=0.95,
            label=f'NEW calibrated x{SCALE}  (rho={new_[0]:.3f})', zorder=3)

n_exp = 0; exp_max = 0.0
for sub, csvp in find_exp(TOPO):
    names, dims, specs = parse_exp(csvp)
    for k, (force, disp) in enumerate(specs):
        if force.size == 0 or k >= len(dims): continue
        T, W, H = dims[k]
        if T <= 0 or W <= 0 or H <= 0: continue
        eps, sig = trim_exp(disp / H, force / (T * W))
        ax.plot(eps, sig, color='#1a9e1a', lw=2.2, alpha=0.95,
                label=f'EXPERIMENT  ({sub})' if n_exp == 0 else None, zorder=10)
        exp_max = max(exp_max, float(sig.max()) if sig.size else 0.0)
        n_exp += 1

ax.set_title(f'{TOPO}  N=2  slider=8 :  SIMULATION x{SCALE} vs EXPERIMENT',
             fontsize=14, fontweight='bold')
ax.set_xlabel('strain', fontsize=12)
ax.set_ylabel('stress [MPa]', fontsize=12)
ax.set_xlim(0, 0.55)
ax.set_ylim(0, exp_max * 1.4 if exp_max > 0 else None)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=11, loc='upper left')

plt.tight_layout()
out = os.path.join(CONS, 'compare_auxetic.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
