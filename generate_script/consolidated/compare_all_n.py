#!/usr/bin/env python3
"""
全部 (topology, N) 仿真与实验对比：
  - 5 topologies × 5 N values = 25 panels
  - 每格 overlay: NS3 baseline / NS4 / 本地新跑 / 实验
"""
import os, csv, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
GENROOT = os.path.dirname(CONS)
TOPOS = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']
NS    = [1, 2, 3, 4, 5]
CELL  = 5.0


def parse_sim(path, n=2):
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


def find_exp(topo, n, slider=8):
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


fig, axes = plt.subplots(len(TOPOS), len(NS), figsize=(24, 20), sharex=True)

availability = {}
for i_t, topo in enumerate(TOPOS):
    for i_n, n in enumerate(NS):
        ax = axes[i_t, i_n]

        ns3_path = os.path.join(CONS, 'simulation', 'NewSession3', f'{topo}__baseline', f'N{n}', 'feature_data.txt')
        ns4_path = os.path.join(CONS, 'simulation', 'NewSession4', topo, f'N{n}', 'feature_data.txt')

        # Local re-run is at fixed dir (all N folded into single feature_data.txt by user's
        # pipeline at 5/0p5/8/StaCompre/) — only valid if file's array matches this N.
        local_path = os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt')

        ns3 = parse_sim(ns3_path, n)
        ns4 = parse_sim(ns4_path, n)
        local = None
        if os.path.exists(local_path):
            with open(local_path, errors='replace') as fh:
                first = fh.readline().strip()
            # name like "Iso_truss_5_0p5_8_StaCompre_2x2x2"
            tag = f'_{n}x{n}x{n}'
            if tag in first:
                local = parse_sim(local_path, n)

        # ----- 先画仿真（薄、半透明，作背景） -----
        if ns4 is not None:
            ax.plot(ns4[1], ns4[2], color='#bbbbbb', lw=0.8, ls=':',  alpha=0.6, label='NS4 sphere x1.2', zorder=1)
        if ns3 is not None:
            ax.plot(ns3[1], ns3[2], color='#5599cc', lw=1.0, ls='--', alpha=0.7, label='NS3 baseline', zorder=2)
        if local is not None:
            ax.plot(local[1], local[2], color='#d62728', lw=1.6, ls='-', alpha=0.8, label='NEW E=1240, sphere=1', zorder=3)

        # ----- 再画实验（粗、不透明、最前层） -----
        n_exp = 0
        exp_max = 0.0
        for sub, csvp in find_exp(topo, n):
            try:
                names, dims, specs = parse_exp(csvp)
            except Exception:
                continue
            for k, (force, disp) in enumerate(specs):
                if force.size == 0 or k >= len(dims): continue
                T, W, H = dims[k]
                if T <= 0 or W <= 0 or H <= 0: continue
                eps, sig = trim_exp(disp / H, force / (T * W))
                ax.plot(eps, sig, color='#1a9e1a', lw=2.0, alpha=1.0,
                        label='EXPERIMENT' if n_exp == 0 else None, zorder=10)
                exp_max = max(exp_max, float(sig.max()) if sig.size else 0.0)
                n_exp += 1

        availability[(topo, n)] = dict(NS3=ns3 is not None, NS4=ns4 is not None,
                                       NEW=local is not None, EXP=n_exp > 0,
                                       exp_max=exp_max)

        ax.set_xlim(0, 0.55)
        ax.grid(True, alpha=0.25)
        if i_t == 0:
            ax.set_title(f'N = {n}', fontsize=12, fontweight='bold')
        if i_n == 0:
            ax.set_ylabel(f'{topo}\nstress [MPa]', fontsize=10)
        if i_t == len(TOPOS) - 1:
            ax.set_xlabel('strain', fontsize=10)
        if i_t == 0 and i_n == 0:
            ax.legend(fontsize=8, loc='upper left')

# ----- 按行做 y 轴限制，避免 sim 把实验压到底 -----
for i_t, topo in enumerate(TOPOS):
    row_exp_max = max(availability[(topo, n)]['exp_max'] for n in NS) or 1.0
    # y 上限 = 实验最大 × 1.8（既看得见实验，也保留 sim 上半截）
    ylim_top = row_exp_max * 1.8
    for i_n in range(len(NS)):
        axes[i_t, i_n].set_ylim(0, ylim_top)

fig.suptitle(
    'All N x topology comparison  (slider=8)\n'
    'GREEN = experiment (highlighted) | blue dash = NS3 | grey dot = NS4 | red = NEW E=1240\n'
    'y axis clipped to 1.8x experiment max per row — sim curves may extend above',
    fontsize=13, fontweight='bold')
plt.tight_layout(rect=[0,0,1,0.94])
out = os.path.join(CONS, 'compare_all_n.png')
plt.savefig(out, dpi=120); plt.close(fig)
print('Saved:', out)

# availability table
print()
print(f'{"topology":<12}', '  '.join([f'N={n}' for n in NS]))
for topo in TOPOS:
    row = [topo.ljust(12)]
    for n in NS:
        a = availability[(topo, n)]
        flags = ''
        flags += '3' if a['NS3'] else '-'
        flags += '4' if a['NS4'] else '-'
        flags += 'N' if a['NEW'] else '-'
        flags += 'E' if a['EXP'] else '-'
        row.append(flags.ljust(4))
    print('  '.join(row))
print('\nflags: 3=NS3 baseline, 4=NS4, N=NEW local re-run, E=experiment')
