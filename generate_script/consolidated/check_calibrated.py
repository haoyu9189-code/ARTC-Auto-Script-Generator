#!/usr/bin/env python3
"""Overlay new calibrated sim vs old NS4/NS3 sim vs experiment for the
two topologies the user re-ran (Kelvin N=3, Auxetic N=3)."""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
GENROOT = os.path.dirname(CONS)


def parse_sim(path, n=3, cell=5.0):
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
    if sl is None: sl = n * cell
    if sa is None: sa = (n * cell) ** 2
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


def find_exp_dir(topo, n, slider=8):
    base = os.path.join(CONS, 'experiment', '20260422', topo)
    out = []
    if not os.path.isdir(base): return out
    for sub in sorted(os.listdir(base)):
        if not sub.startswith(f'N{n}_slider{slider}'): continue
        if any(x in sub for x in ('wrong_dir','fault','one_sample','remove')): continue
        p = os.path.join(base, sub, 'data.csv')
        if os.path.exists(p): out.append((sub, p))
    return out


CASES = [
    ('Kelvin',  3, os.path.join(GENROOT, 'Kelvin',  '5','0p5','8','StaCompre','feature_data.txt')),
    ('Auxetic', 3, os.path.join(GENROOT, 'Auxetic', '5','0p5','8','StaCompre','feature_data.txt')),
]

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for ax, (topo, n, new_path) in zip(axes, CASES):
    new_ = parse_sim(new_path, n)
    ns4  = parse_sim(os.path.join(CONS,'simulation','NewSession4',topo,f'N{n}','feature_data.txt'), n)
    ns3  = parse_sim(os.path.join(CONS,'simulation','NewSession3',f'{topo}__baseline',f'N{n}','feature_data.txt'), n)

    if ns3 is not None:
        ax.plot(ns3[1], ns3[2], color='#999999', lw=1.4, ls=':',  label='OLD NS3 baseline (sphere=1.0, μ=0.15)')
    if ns4 is not None:
        ax.plot(ns4[1], ns4[2], color='#1f4e79', lw=1.6, ls='--', label='OLD NS4 (sphere×1.2, μ=0.15)')
    if new_ is not None:
        ax.plot(new_[1], new_[2], color='#d62728', lw=2.4, ls='-',
                label=f'NEW calibrated (sphere=1.0, μ=0.05, soft hardening, low damage)')

    for sub, csvp in find_exp_dir(topo, n):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            ax.plot(disp/H, force/(T*W), color='#2ca02c', lw=1.0, alpha=0.7,
                    label='experiment' if (sub == find_exp_dir(topo,n)[0][0] and k==0) else None)

    ax.set_title(f'{topo}  N={n}', fontsize=13, fontweight='bold')
    ax.set_xlabel('strain ε', fontsize=11)
    ax.set_ylabel('stress σ [MPa]', fontsize=11)
    ax.set_xlim(0, 0.55)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc='upper left')

fig.suptitle('Calibrated sim vs OLD sim vs experiment   (slider=8)', fontsize=13)
plt.tight_layout(rect=[0,0,1,0.95])
out = os.path.join(CONS, 'check_calibrated.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)

# Print key features
print()
print(f'{"case":<22}{"rho":>7}  {"slope_init":>12}  {"σ_pk":>8}  {"ε_pk":>8}  {"σ@0.25":>8}')
for topo, n, new_path in CASES:
    for label, p in [('NEW', new_path),
                     ('OLD NS4', os.path.join(CONS,'simulation','NewSession4',topo,f'N{n}','feature_data.txt')),
                     ('OLD NS3', os.path.join(CONS,'simulation','NewSession3',f'{topo}__baseline',f'N{n}','feature_data.txt'))]:
        r = parse_sim(p, n)
        if r is None: print(f'{topo+" N3 "+label:<22}  (missing)'); continue
        rho, eps, sig = r
        ie = np.searchsorted(eps, 0.005); slope = sig[ie]/eps[ie] if ie>0 else float('nan')
        ipk = int(np.argmax(sig)); s_pk, e_pk = sig[ipk], eps[ipk]
        s25 = float(np.interp(0.25, eps, sig)) if eps[-1]>=0.25 else float('nan')
        print(f'{topo+" N3 "+label:<22}{rho:7.4f}  {slope:12.1f}  {s_pk:8.3f}  {e_pk:8.4f}  {s25:8.3f}')
