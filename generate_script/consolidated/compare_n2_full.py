#!/usr/bin/env python3
"""All 5 topologies × N=2: NEW calibrated sim vs OLD NS3/NS4 vs experiment.

NEW = generate_script/{topo}/5/0p5/8/StaCompre/feature_data.txt
  - Auxetic / BCC: latest E=1240 + bulk 0.06/1.2 + scale=1.0 (with old Auxetic geometry)
  - Iso_truss / Kelvin / Octet_truss: E=1240 + scale=1.0 but OLD bulk 0.25/2.0
"""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
GENROOT = os.path.dirname(CONS)
TOPOS = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']
N = 2
CELL = 5.0


def parse_sim(path, n=N):
    if not os.path.exists(path): return None
    rho = sl = sa = None
    d, f = [], []; started = False
    with open(path, errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not started:
                if s.startswith('density:'):       rho = float(s.split(':')[1]); continue
                if s.startswith('strain_length:'): sl  = float(s.split(':')[1]); continue
                if s.startswith('stress_area:'):   sa  = float(s.split(':')[1]); continue
                if 'X' in s and '_temp_3' in s: started = True
                continue
            parts = s.split()
            if len(parts) == 2:
                try: d.append(float(parts[0])); f.append(float(parts[1]))
                except ValueError: pass
    if not started or len(d) < 5 or rho is None: return None
    if sl is None: sl = n * CELL
    if sa is None: sa = (n * CELL) ** 2
    return rho, np.asarray(d) / sl, np.asarray(f) / sa


def parse_exp(csv_path):
    rows = []
    with open(csv_path, encoding='utf-8', errors='replace') as fh:
        for r in csv.reader(fh): rows.append(r)
    dims, names = [], []
    for i, r in enumerate(rows):
        if len(r) >= 4 and r[0].strip() == 'Name' and r[1].strip() == 'Thickness':
            j = i + 1
            while j < len(rows):
                rr = rows[j]
                if len(rr) >= 4 and rr[0].strip() and rr[0].strip() != 'Size Unit:':
                    try:
                        dims.append((float(rr[1]), float(rr[2]), float(rr[3])))
                        names.append(rr[0].strip())
                    except ValueError: pass
                if not rr or not rr[0].strip():
                    if dims: break
                j += 1
            break
    specs = []
    for sn in names:
        block = None
        for k, r in enumerate(rows):
            if len(r) >= 1 and r[0].strip() == sn and (len(r) == 1 or not r[1].strip()):
                if k+1 < len(rows) and rows[k+1][:4] == ['Time','Force','Disp.','Stroke']:
                    block = k + 3; break
        if block is None: specs.append((np.array([]), np.array([]))); continue
        force, disp = [], []
        m = block
        while m < len(rows):
            r = rows[m]
            if len(r) < 4 or not r[0].strip(): break
            try: force.append(float(r[1])); disp.append(float(r[2]))
            except ValueError: break
            m += 1
        specs.append((np.asarray(force), np.asarray(disp)))
    return names, dims, specs


def find_exp(topo, n=N, slider=8):
    base = os.path.join(CONS, 'experiment', '20260422', topo)
    out = []
    if not os.path.isdir(base): return out
    for sub in sorted(os.listdir(base)):
        if not sub.startswith(f'N{n}_slider{slider}'): continue
        if any(x in sub for x in ('wrong_dir','fault','one_sample','remove')): continue
        p = os.path.join(base, sub, 'data.csv')
        if os.path.exists(p): out.append((sub, p))
    return out


def trim_exp(eps, sig, sig_min=0.05, window=20):
    """Compliance correction: find true ε=0 by linear extrapolation.

    Real compression starts where load-displacement is linear elastic.
    Before that, there is a 'loose-contact / glue' region that should be
    discarded.  Find the max-slope window, fit a line, extrapolate back
    to σ = 0, and use that intersection as the new origin.
    """
    if len(eps) < window * 2:
        return eps, sig
    # Step 1: compute local slope using a sliding window
    slopes = np.full(len(eps), np.nan)
    for i in range(window // 2, len(eps) - window // 2):
        e_w = eps[i - window // 2 : i + window // 2]
        s_w = sig[i - window // 2 : i + window // 2]
        if e_w[-1] - e_w[0] < 1e-6: continue
        slopes[i] = (s_w[-1] - s_w[0]) / (e_w[-1] - e_w[0])
    # Step 2: find the index of max slope (within first 30% strain to avoid plateau)
    cutoff = int(len(eps) * 0.3)
    valid = ~np.isnan(slopes[:cutoff])
    if valid.sum() < 5:
        # fallback to simple threshold
        keep = np.where(sig > sig_min)[0]
        if keep.size == 0: return eps, sig
        i0 = keep[0]
        return eps[i0:] - eps[i0], sig[i0:]
    i_max_slope = int(np.nanargmax(slopes[:cutoff]))
    # Step 3: fit linear in a window around i_max_slope
    fit_lo = max(window // 2, i_max_slope - window)
    fit_hi = min(len(eps), i_max_slope + window)
    e_fit = eps[fit_lo:fit_hi]
    s_fit = sig[fit_lo:fit_hi]
    # Use only the rising portion (sig > sig_min)
    mask = s_fit > sig_min
    if mask.sum() < 3:
        keep = np.where(sig > sig_min)[0]
        if keep.size == 0: return eps, sig
        i0 = keep[0]
        return eps[i0:] - eps[i0], sig[i0:]
    slope, intercept = np.polyfit(e_fit[mask], s_fit[mask], 1)
    # Step 4: ε at σ = 0 from the linear fit
    eps_zero = -intercept / slope if slope > 0 else 0.0
    # Step 5: shift and trim
    new_eps = eps - eps_zero
    keep = new_eps >= 0
    return new_eps[keep], sig[keep]


fig, axes = plt.subplots(2, 3, figsize=(22, 12))
axes = axes.flatten()

for ax, topo in zip(axes, TOPOS):
    new_  = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    ns3   = parse_sim(os.path.join(CONS, 'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt'))
    ns4   = parse_sim(os.path.join(CONS, 'simulation','NewSession4',topo,f'N{N}','feature_data.txt'))

    if ns4 is not None:
        ax.plot(ns4[1], ns4[2], color='#bbbbbb', lw=1.0, ls=':', alpha=0.7,
                label=f'OLD NS4 (rho={ns4[0]:.3f})', zorder=1)
    if ns3 is not None:
        ax.plot(ns3[1], ns3[2], color='#5599cc', lw=1.4, ls='--', alpha=0.8,
                label=f'OLD NS3 baseline (rho={ns3[0]:.3f})', zorder=2)
    if new_ is not None:
        ax.plot(new_[1], new_[2], color='#d62728', lw=2.0, ls='-', alpha=0.9,
                label=f'NEW calibrated (rho={new_[0]:.3f})', zorder=3)

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
    ax.set_ylim(0, exp_max * 1.8 if exp_max > 0 else None)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc='upper left')

axes[5].axis('off')
axes[5].text(0.0, 0.95,
    'NEW calibration legend:\n'
    '  Auxetic / BCC : E=1240, bulk 0.06/1.2, scale 1.0  (full calib)\n'
    '  Iso_truss / Kelvin / Octet_truss : E=1240, scale 1.0\n'
    '                                     BUT old bulk 0.25/2.0\n\n'
    'Y-axis clipped to 1.8 x experiment max per panel\n'
    '(sim curves may extend above clip)',
    family='monospace', fontsize=11, verticalalignment='top')

fig.suptitle(
    'N=2 (slider=8): NEW calibration vs OLD NS3 / NS4 vs experiment',
    fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(CONS, 'compare_n2_full.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
