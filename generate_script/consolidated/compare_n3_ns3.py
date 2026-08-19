#!/usr/bin/env python3
"""5 topologies × N=3 (slider=8): NS3 baseline vs experiment.

NS3 baseline = sphere=1.0, no calibration — closest in shape to experiment.
Diagnostic: where does the elastic peak (first yield-like maximum) occur?
"""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
TOPOS = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']
N = 3
CELL = 5.0


def parse_sim(path, n=N):
    if not os.path.exists(path):
        return None
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


def trim_exp(eps, sig, force_threshold=2.0):
    """Trim leading loose-contact region (force < threshold N).  Re-zero strain."""
    # estimate force from sig*A — but we don't have A here. Use sig threshold instead
    # Use a sigma threshold: ~0.02 MPa is well above noise
    sig_threshold_mpa = 0.02
    keep_idx = np.where(sig > sig_threshold_mpa)[0]
    if keep_idx.size == 0:
        return eps, sig
    i0 = keep_idx[0]
    eps_re = eps[i0:] - eps[i0]
    sig_re = sig[i0:]
    return eps_re, sig_re


def find_first_local_max_or_knee(eps, sig, eps_window=0.20, min_drop=0.05,
                                  smooth_win=21):
    """Find first SIGNIFICANT local maximum within ε ∈ [0, eps_window].

    "Significant" = followed by a relative drop of at least min_drop (5%).
    If no such peak found, fall back to the knee defined by max curvature
    (point where σ stops being concave-up).
    """
    if len(eps) < 5: return None, None
    mask = eps <= eps_window
    e_w = eps[mask]; s_w = sig[mask]
    if len(s_w) < smooth_win: return None, None
    s_smooth = np.convolve(s_w, np.ones(smooth_win)/smooth_win, mode='same')
    d1 = np.diff(s_smooth)
    # candidate local maxima
    cand = np.where((d1[:-1] > 0) & (d1[1:] <= 0))[0] + 1
    for i in cand:
        peak_v = s_smooth[i]
        post = s_smooth[i:]
        if (peak_v - post.min()) / max(peak_v, 1e-9) >= min_drop:
            return float(e_w[i]), float(s_w[i])
    # No real peak: find knee — max of d²σ/dε² (most concave-down point)
    if len(s_smooth) > smooth_win + 2:
        d2 = np.diff(s_smooth, 2)
        # negative d² ⇒ concave down ⇒ knee.  Take min (most negative).
        knee = int(np.argmin(d2)) + 1
        return float(e_w[knee]), float(s_w[knee])
    i = int(np.argmax(s_w))
    return float(e_w[i]), float(s_w[i])


fig, axes = plt.subplots(2, 3, figsize=(20, 11))
axes = axes.flatten()

summary_rows = []
for ax, topo in zip(axes, TOPOS):
    ns3_path = os.path.join(CONS,'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt')
    ns4_path = os.path.join(CONS,'simulation','NewSession4',topo,f'N{N}','feature_data.txt')
    ns3 = parse_sim(ns3_path)
    ns4 = parse_sim(ns4_path)
    sim_label = 'NS3 baseline (sphere=1.0)'
    sim_data = ns3
    if sim_data is None:
        sim_data = ns4
        sim_label = 'NS4  (NS3 missing — using NS4 sphere×1.2)'

    # NS4 dotted for context (only if NS3 is the primary)
    if ns4 is not None and ns3 is not None:
        ax.plot(ns4[1], ns4[2], color='#bbbbbb', lw=1.0, ls=':', alpha=0.7,
                label='NS4 (sphere×1.2) ctx')

    # primary sim
    sim_e_pk = sim_s_pk = None
    if sim_data is not None:
        ax.plot(sim_data[1], sim_data[2], color='#1f4e79', lw=2.4, ls='-',
                label=sim_label)
        sim_e_pk, sim_s_pk = find_first_local_max_or_knee(sim_data[1], sim_data[2])

    # experiment specimens (trimmed)
    exp_pks = []
    exp_paths = find_exp(topo)
    first_label_done = False
    for sub, csvp in exp_paths:
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps_raw = disp / H; sig_raw = force / (T * W)
            eps, sig = trim_exp(eps_raw, sig_raw)
            ax.plot(eps, sig, color='#2ca02c', lw=1.2, alpha=0.7,
                    label='experiment' if not first_label_done else None)
            first_label_done = True
            ek, sk = find_first_local_max_or_knee(eps, sig, eps_window=0.20)
            if ek is not None:
                exp_pks.append((ek, sk))

    # mark elastic peak
    if sim_e_pk is not None:
        ax.scatter([sim_e_pk], [sim_s_pk], s=180, marker='*', color='#1f4e79',
                   edgecolor='white', linewidth=1.5, zorder=10,
                   label=f'sim peak  ε={sim_e_pk:.3f}, σ={sim_s_pk:.2f}')
    if exp_pks:
        ee = np.mean([p[0] for p in exp_pks]); ss = np.mean([p[1] for p in exp_pks])
        ax.scatter([ee], [ss], s=180, marker='X', color='#2ca02c',
                   edgecolor='white', linewidth=1.5, zorder=10,
                   label=f'exp peak    ε={ee:.3f}, σ={ss:.2f}')
    else:
        ee = ss = float('nan')

    summary_rows.append((topo, sim_e_pk if sim_e_pk else float('nan'),
                         sim_s_pk if sim_s_pk else float('nan'),
                         ee, ss))

    ax.set_title(f'{topo}  N=3   slider=8', fontsize=12, fontweight='bold')
    ax.set_xlabel('strain ε', fontsize=10)
    ax.set_ylabel('stress σ [MPa]', fontsize=10)
    ax.set_xlim(0, 0.55)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc='upper left')

# summary panel
axes[5].axis('off')
hdr = f'{"topology":<14}{"ε_pk_sim":>11}{"σ_pk_sim":>11}{"ε_pk_exp":>11}{"σ_pk_exp":>11}{"εsim/εexp":>12}\n' + '-'*70
body = []
for t, es, ss_, ee, sse in summary_rows:
    r = es / ee if (ee and not np.isnan(ee) and ee > 0 and not np.isnan(es)) else float('nan')
    body.append(f'{t:<14}{es:>11.4f}{ss_:>11.2f}{ee:>11.4f}{sse:>11.2f}{r:>12.2f}')
axes[5].text(0.0, 0.95,
    'Elastic-peak diagnostic   (first local max within ε<0.15)\n'
    'sim = NS3 baseline (sphere=1.0)\n'
    'exp = trimmed to skip loose-contact region (σ>0.02 MPa)\n\n' +
    hdr + '\n' + '\n'.join(body) +
    '\n\nReading the εsim/εexp ratio:\n'
    '  <0.5  → sim yields way too early (too stiff initial response)\n'
    '  ~1.0  → elastic peak position matches\n'
    '  >2.0  → sim yields too late\n',
    family='monospace', fontsize=10, verticalalignment='top')

fig.suptitle(
    'N=3   slider=8   experiment vs NS3 baseline\n'
    'NS3 = sphere=1.0, no calibration → most "raw" sim shape.   ★/X mark first elastic peak.',
    fontsize=13, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.93])
out = os.path.join(CONS, 'compare_n3_ns3.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)

print()
print(hdr)
for line in body: print(line)
