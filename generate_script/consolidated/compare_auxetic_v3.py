#!/usr/bin/env python3
"""Auxetic N=2 latest run vs experiment + NS3 baseline.
Y-axis adaptive to NEW + experiment range (NOT to NS3/NS4 max)."""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT

TOPO = 'Auxetic'

new_  = parse_sim(os.path.join(GENROOT, TOPO, '5','0p5','8','StaCompre','feature_data.txt'))
ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{TOPO}__baseline',f'N{N}','feature_data.txt'))

fig, ax = plt.subplots(figsize=(11, 7.5))

# experiment
exp_max_in_xlim = 0.0
n_exp = 0
for sub, csvp in find_exp(TOPO):
    names, dims, specs = parse_exp(csvp)
    for k, (force, disp) in enumerate(specs):
        if force.size == 0 or k >= len(dims): continue
        T, W, H = dims[k]
        if T <= 0 or W <= 0 or H <= 0: continue
        eps, sig = trim_exp(disp / H, force / (T * W))
        ax.plot(eps, sig, color='#1a9e1a', lw=2.0, alpha=0.95,
                label=f'EXPERIMENT (3 specimens)' if n_exp == 0 else None, zorder=10)
        m = (eps >= 0) & (eps <= 0.55)
        if m.any(): exp_max_in_xlim = max(exp_max_in_xlim, float(sig[m].max()))
        n_exp += 1

new_max = 0.0
if new_ is not None:
    e, s = new_[1], new_[2]
    ax.plot(e, s, color='#d62728', lw=2.4, ls='-', alpha=0.95,
            label=f'NEW (E=777, σ_y=17, contact=1.0; rho={new_[0]:.3f})', zorder=3)
    m = (e >= 0) & (e <= 0.55)
    if m.any(): new_max = float(s[m].max())

ns3_max = 0.0
if ns3 is not None:
    e, s = ns3[1], ns3[2]
    ax.plot(e, s, color='#5599cc', lw=1.4, ls='--', alpha=0.7,
            label=f'NS3 baseline (rho={ns3[0]:.3f})', zorder=2)
    m = (e >= 0) & (e <= 0.55)
    if m.any(): ns3_max = float(s[m].max())

# Y-axis: adapt to NEW + experiment, ignore NS3/NS4 (which dominate top)
y_top = max(new_max, exp_max_in_xlim) * 1.15

ax.set_title(f'{TOPO}  N=2  slider=8 :  NEW (NS3 x0.50 material) vs EXPERIMENT',
             fontsize=14, fontweight='bold')
ax.set_xlabel('strain', fontsize=12)
ax.set_ylabel('stress [MPa]', fontsize=12)
ax.set_xlim(0, 0.55)
ax.set_ylim(0, y_top)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=10, loc='upper left')

# annotate peak values
if new_ is not None:
    e, s = new_[1], new_[2]
    cutoff = np.searchsorted(e, 0.15)
    if cutoff > 5:
        i = int(np.argmax(s[:cutoff]))
        ax.annotate(f'NEW peak\nσ={s[i]:.2f}\nε={e[i]:.3f}',
                    xy=(e[i], s[i]), xytext=(e[i]+0.04, s[i]),
                    fontsize=9, color='#d62728',
                    arrowprops=dict(arrowstyle='->', color='#d62728', lw=1))

plt.tight_layout()
out = os.path.join(CONS, 'compare_auxetic_v3.png')
plt.savefig(out, dpi=140); plt.close(fig)
print(f'NEW peak in xlim: {new_max:.3f}, NS3 peak: {ns3_max:.3f}, exp peak: {exp_max_in_xlim:.3f}')
print(f'Y-axis top: {y_top:.3f}')
print('Saved:', out)
