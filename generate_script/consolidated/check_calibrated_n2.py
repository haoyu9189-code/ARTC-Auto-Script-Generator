#!/usr/bin/env python3
"""N=2 calibrated sim vs OLD NS3 baseline / NS4 / experiment.

Local re-run files (E=1240 + sphere=1.0 calibration):
  generate_script/{topo}/5/0p5/8/StaCompre/feature_data.txt   (2x2x2)
"""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
GENROOT = os.path.dirname(CONS)
N = 2
CELL = 5.0
TOPOS_TO_PLOT = ['Iso_truss', 'Kelvin', 'Octet_truss']


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


def trim_exp(eps, sig, threshold=0.02):
    keep = np.where(sig > threshold)[0]
    if keep.size == 0:
        return eps, sig
    i0 = keep[0]
    return eps[i0:] - eps[i0], sig[i0:]


fig, axes = plt.subplots(1, 3, figsize=(20, 6))
summary = []

for ax, topo in zip(axes, TOPOS_TO_PLOT):
    new_path = os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt')
    ns3_path = os.path.join(CONS,'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt')
    ns4_path = os.path.join(CONS,'simulation','NewSession4',topo,f'N{N}','feature_data.txt')

    new_  = parse_sim(new_path)
    ns3   = parse_sim(ns3_path)
    ns4   = parse_sim(ns4_path)

    if ns4 is not None:
        ax.plot(ns4[1], ns4[2], color='#bbbbbb', lw=1.0, ls=':',
                label=f'OLD NS4 sphere x1.2  (rho={ns4[0]:.3f})')
    if ns3 is not None:
        ax.plot(ns3[1], ns3[2], color='#1f4e79', lw=1.6, ls='--',
                label=f'OLD NS3 baseline   (rho={ns3[0]:.3f})')
    if new_ is not None:
        ax.plot(new_[1], new_[2], color='#d62728', lw=2.4, ls='-',
                label=f'NEW E=1240 sphere=1.0  (rho={new_[0]:.3f})')

    n_exp = 0
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            ax.plot(eps, sig, color='#2ca02c', lw=1.0, alpha=0.6,
                    label='experiment (3 spec)' if n_exp == 0 else None)
            n_exp += 1

    ax.set_title(f'{topo}  N=2  slider=8', fontsize=12, fontweight='bold')
    ax.set_xlabel('strain', fontsize=10)
    ax.set_ylabel('stress [MPa]', fontsize=10)
    ax.set_xlim(0, 0.55)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc='upper left')

    # extract metrics for summary
    def pk_metric(eps, sig, win=0.20):
        if eps is None or len(eps) < 5: return float('nan'), float('nan')
        mask = eps <= win
        if mask.sum() < 5: return float('nan'), float('nan')
        e = eps[mask]; s = sig[mask]
        # smoothed first significant local max
        sm = np.convolve(s, np.ones(11)/11, mode='same')
        d1 = np.diff(sm)
        cand = np.where((d1[:-1] > 0) & (d1[1:] <= 0))[0] + 1
        for i in cand:
            if (sm[i] - sm[i:].min()) / max(sm[i],1e-9) >= 0.05:
                return float(e[i]), float(s[i])
        # else knee = max curvature drop
        if len(sm) > 13:
            d2 = np.diff(sm, 2)
            knee = int(np.argmin(d2)) + 1
            return float(e[knee]), float(s[knee])
        i = int(np.argmax(s))
        return float(e[i]), float(s[i])

    new_pk = pk_metric(new_[1], new_[2]) if new_ is not None else (float('nan'),)*2
    ns3_pk = pk_metric(ns3[1], ns3[2]) if ns3 is not None else (float('nan'),)*2
    ns4_pk = pk_metric(ns4[1], ns4[2]) if ns4 is not None else (float('nan'),)*2

    exp_pks = []
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            ek, sk = pk_metric(eps, sig)
            if not np.isnan(ek): exp_pks.append((ek, sk))
    exp_e = np.mean([p[0] for p in exp_pks]) if exp_pks else float('nan')
    exp_s = np.mean([p[1] for p in exp_pks]) if exp_pks else float('nan')

    summary.append((topo, ns3_pk, ns4_pk, new_pk, (exp_e, exp_s)))

fig.suptitle(
    'N=2 (2x2x2) calibrated sim vs OLD NS3/NS4 vs experiment   (slider=8)\n'
    'NEW = E reduced 1554.5 -> 1240 (x 0.80), sphere=1.0',
    fontsize=13, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.93])
out = os.path.join(CONS, 'check_calibrated_n2.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)
print()
print(f'{"topology":<12}  {"NS3 (eps_pk, sig_pk)":>22}  {"NS4":>20}  {"NEW":>22}  {"EXP":>20}')
for t, (e3,s3), (e4,s4), (en,sn), (ee,se) in summary:
    print(f'{t:<12}  ({e3:6.3f}, {s3:6.2f})       ({e4:6.3f}, {s4:6.2f})   ({en:6.3f}, {sn:6.2f})       ({ee:6.3f}, {se:6.2f})')
