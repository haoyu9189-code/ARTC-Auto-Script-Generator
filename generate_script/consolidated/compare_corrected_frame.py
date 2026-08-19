#!/usr/bin/env python3
"""Auxetic + BCC N=2: experiment converted to LATTICE FRAME (using H_lattice = N*cell,
not H_specimen) and A_lattice = (N*cell)^2 (not T*W).
Sim already uses lattice frame, so we just rescale exp."""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT, CELL

TOPOS = ['Auxetic', 'BCC']
H_LAT = N * CELL          # 10
A_LAT = (N * CELL) ** 2   # 100

fig, axes = plt.subplots(2, 2, figsize=(20, 13))

for row, topo in enumerate(TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))

    # collect raw + lattice-frame experiment
    exp_data = []  # list of (eps_raw, sig_raw, eps_lat, sig_lat, dims_label)
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            # original (specimen frame)
            eps_raw = disp / H
            sig_raw = force / (T * W)
            eps_raw, sig_raw = trim_exp(eps_raw, sig_raw)
            # lattice frame (use H_LAT, A_LAT)
            eps_lat = disp / H_LAT
            sig_lat = force / A_LAT
            eps_lat, sig_lat = trim_exp(eps_lat, sig_lat)
            exp_data.append((eps_raw, sig_raw, eps_lat, sig_lat, f'T={T:.1f}xW={W:.1f}xH={H:.1f}'))

    # === LEFT: original specimen frame (current) ===
    ax = axes[row, 0]
    n_exp = 0; m_exp = 0.0
    for er, sr, _, _, _ in exp_data:
        ax.plot(er, sr, color='#1a9e1a', lw=2.0, alpha=0.95,
                label='EXPERIMENT (specimen frame)' if n_exp == 0 else None, zorder=10)
        n_exp += 1
        m = (er >= 0) & (er <= 0.55)
        if m.any(): m_exp = max(m_exp, float(sr[m].max()))
    if ns3 is not None:
        ax.plot(ns3[1], ns3[2] * 0.5, color='#5599cc', lw=2.0, ls='-', alpha=0.95,
                label=f'NS3 x0.5 (rho={ns3[0]:.3f})', zorder=4)
    if new_ is not None:
        ax.plot(new_[1], new_[2], color='#d62728', lw=1.8, ls='--', alpha=0.85,
                label=f'NEW current (rho={new_[0]:.3f})', zorder=3)
    ax.set_title(f'{topo}  N=2  —  EXP in specimen frame (ε=Δ/H_spec, σ=F/A_spec)',
                 fontsize=12, fontweight='bold')
    ax.set_xlabel('strain'); ax.set_ylabel('stress [MPa]')
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, max(m_exp, 3) * 1.4)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=9, loc='upper left')

    # === RIGHT: lattice frame (corrected) ===
    ax = axes[row, 1]
    n_exp = 0; m_lat = 0.0
    for _, _, el, sl, _ in exp_data:
        ax.plot(el, sl, color='#1a9e1a', lw=2.0, alpha=0.95,
                label='EXPERIMENT (lattice frame)' if n_exp == 0 else None, zorder=10)
        n_exp += 1
        m = (el >= 0) & (el <= 0.55)
        if m.any(): m_lat = max(m_lat, float(sl[m].max()))
    if ns3 is not None:
        ax.plot(ns3[1], ns3[2] * 0.5, color='#5599cc', lw=2.0, ls='-', alpha=0.95,
                label=f'NS3 x0.5 (rho={ns3[0]:.3f})', zorder=4)
    if new_ is not None:
        ax.plot(new_[1], new_[2], color='#d62728', lw=1.8, ls='--', alpha=0.85,
                label=f'NEW current (rho={new_[0]:.3f})', zorder=3)
    ax.set_title(f'{topo}  N=2  —  EXP CORRECTED to lattice frame (ε=Δ/{H_LAT}, σ=F/{A_LAT})',
                 fontsize=12, fontweight='bold')
    ax.set_xlabel('strain'); ax.set_ylabel('stress [MPa]')
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, max(m_lat, 3) * 1.4)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=9, loc='upper left')

fig.suptitle('Specimen frame vs Lattice frame — experiment correction for sim comparability',
             fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.97])
out = os.path.join(CONS, 'compare_corrected_frame.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
