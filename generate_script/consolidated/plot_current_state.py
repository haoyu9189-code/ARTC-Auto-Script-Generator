#!/usr/bin/env python3
"""
N=3 current-state plot:
  - experiment slider=8 (3 specimens per topology)
  - NS3 baseline (consolidated/)
  - NS4         (consolidated/)
  - local re-run (generate_script/{topo}/5/0p5/8/StaCompre/) if any
"""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS    = os.path.dirname(os.path.abspath(__file__))
GENROOT = os.path.dirname(CONS)
TOPOS   = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']
N       = 3
CELL    = 5.0


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
                if k + 1 < len(rows) and rows[k+1][:4] == ['Time','Force','Disp.','Stroke']:
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


def trim_exp(eps, sig, sig_threshold=0.02):
    keep = np.where(sig > sig_threshold)[0]
    if keep.size == 0:
        return eps, sig
    i0 = keep[0]
    return eps[i0:] - eps[i0], sig[i0:]


fig, axes = plt.subplots(2, 3, figsize=(20, 11))
axes = axes.flatten()

availability = []
for ax, topo in zip(axes, TOPOS):
    ns3_path   = os.path.join(CONS,'simulation','NewSession3',f'{topo}__baseline',f'N{N}','feature_data.txt')
    ns4_path   = os.path.join(CONS,'simulation','NewSession4',topo,f'N{N}','feature_data.txt')
    local_path = os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt')

    ns3   = parse_sim(ns3_path)
    ns4   = parse_sim(ns4_path)
    local = parse_sim(local_path)

    have = {
        'NS3': ns3 is not None,
        'NS4': ns4 is not None,
        'local': local is not None,
        'exp':  bool(find_exp(topo)),
    }
    availability.append((topo, have))

    if ns3 is not None:
        ax.plot(ns3[1], ns3[2], color='#1f4e79', lw=1.6, ls='--',
                label=f'NS3 baseline  (ρ={ns3[0]:.3f})')
    if ns4 is not None:
        ax.plot(ns4[1], ns4[2], color='#bbbbbb', lw=1.0, ls=':',
                label=f'NS4 sphere×1.2  (ρ={ns4[0]:.3f})')
    if local is not None:
        ax.plot(local[1], local[2], color='#d62728', lw=2.4, ls='-',
                label=f'local re-run  (ρ={local[0]:.3f})')

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

    ax.set_title(f'{topo}  N=3', fontsize=12, fontweight='bold')
    ax.set_xlabel('strain ε', fontsize=10)
    ax.set_ylabel('stress σ [MPa]', fontsize=10)
    ax.set_xlim(0, 0.55)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc='upper left')

# 第 6 个面板放数据可用性表
axes[5].axis('off')
hdr = f'{"topology":<14}{"NS3":>6}{"NS4":>6}{"local":>8}{"exp":>6}'
body = []
for topo, have in availability:
    body.append(
        f'{topo:<14}'
        f'{"yes" if have["NS3"] else "no ":>6}'
        f'{"yes" if have["NS4"] else "no ":>6}'
        f'{"yes" if have["local"] else "no ":>8}'
        f'{"yes" if have["exp"] else "no ":>6}'
    )
axes[5].text(0.0, 0.95,
    'N=3  slider=8  data availability\n\n' +
    hdr + '\n' + '-'*40 + '\n' + '\n'.join(body) +
    '\n\nLegend:\n'
    '  NS3 baseline : sphere=1.0\n'
    '  NS4          : sphere x 1.2 (NS3 -> NS4 = sphere change only)\n'
    '  local        : generate_script/{topo}/5/0p5/8/StaCompre/\n'
    '  exp          : experiment/20260422/{topo}/N3_slider8/',
    family='monospace', fontsize=11, verticalalignment='top')

fig.suptitle(
    'Current state - N=3 slider=8: experiment + simulation',
    fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.95])
out = os.path.join(CONS, 'current_state_n3.png')
plt.savefig(out, dpi=140); plt.close(fig)
print('Saved:', out)

print()
print(hdr)
print('-' * 40)
for line in body: print(line)
