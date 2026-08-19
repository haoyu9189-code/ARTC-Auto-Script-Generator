#!/usr/bin/env python3
"""Final comparison: NS3-baseline NEW sim (just re-run, contact=1.0) vs experiment in LATTICE FRAME."""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT, CELL

H_LAT = N * CELL
A_LAT = (N * CELL) ** 2

TOPOS = ['Auxetic', 'BCC']

fig, axes = plt.subplots(1, 2, figsize=(20, 8))

for ax, topo in zip(axes, TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))

    n_exp = 0; m_exp = 0.0
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H_LAT, force / A_LAT)
            ax.plot(eps, sig, color='#1a7e1a', lw=2.2, alpha=0.95,
                    label='EXPERIMENT (3 spec, lattice frame)' if n_exp == 0 else None, zorder=10)
            m = (eps >= 0) & (eps <= 0.55)
            if m.any(): m_exp = max(m_exp, float(sig[m].max()))
            n_exp += 1

    new_max = 0.0
    if new_ is not None:
        e, s = new_[1], new_[2]
        ax.plot(e, s, color='#d62728', lw=2.4, ls='-', alpha=0.95,
                label=f'NEW (NS3 mat, contact=1.0)  (rho={new_[0]:.3f})', zorder=5)
        m = (e >= 0) & (e <= 0.55)
        if m.any(): new_max = float(s[m].max())

    if ns3 is not None:
        e, s = ns3[1], ns3[2]
        ax.plot(e, s, color='#5599cc', lw=1.6, ls='--', alpha=0.7,
                label=f'OLD NS3 (contact=5.0)  (rho={ns3[0]:.3f})', zorder=3)

    y_top = max(new_max, m_exp) * 1.4

    # peak annotation
    if new_ is not None:
        e, s = new_[1], new_[2]
        cutoff = np.searchsorted(e, 0.20)
        if cutoff > 5:
            i = int(np.argmax(s[:cutoff]))
            ax.annotate(f'NEW peak\nsig={s[i]:.2f}\neps={e[i]:.3f}',
                        xy=(e[i], s[i]), xytext=(e[i]+0.05, s[i]+y_top*0.08),
                        fontsize=9, color='#d62728',
                        arrowprops=dict(arrowstyle='->', color='#d62728', lw=1))

    ax.set_title(f'{topo}  N=2  (lattice frame)',
                 fontsize=14, fontweight='bold')
    ax.set_xlabel('strain  (eps = disp / 10)', fontsize=12)
    ax.set_ylabel('stress [MPa]  (sig = F / 100)', fontsize=12)
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, y_top)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10, loc='upper left')

fig.suptitle('Final: NS3 material + contact=1.0 sim vs lattice-frame experiment',
             fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_final.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
