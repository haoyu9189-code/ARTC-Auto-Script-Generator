#!/usr/bin/env python3
"""
Experiment vs simulation SEA comparison.

For each (topology, N, slider=8) successful experiment:
  - read 3-specimen Shimadzu data.csv
  - compute strain = disp / Height, stress = Force / (Thickness*Width) per specimen
  - W_exp(eps_cut) = trapz(stress, strain) up to eps_cut
  - SEA_exp = W / rho_rel_sim     (use NS4 density at same N as proxy; geometry matches)

Compare to NS4 and NS3 baseline simulation SEA at same (topology, N).

Outputs:
  exp_vs_sim_sea.csv          — one row per (topology, N) with exp mean+/-std and sim values
  exp_vs_sim_curves.png       — overlay σ-ε curves (exp 3-specimen + sim) per topology
  exp_vs_sim_sea_bar.png      — bar plot of SEA exp vs NS4 vs NS3 baseline
"""

import os, csv, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
EPS_CUT = 0.25
EXP_TOPOS = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']

DENSITY_RE = re.compile(r'^density:\s*([0-9.eE+-]+)')
SLEN_RE    = re.compile(r'^strain_length:\s*([0-9.eE+-]+)')
SAREA_RE   = re.compile(r'^stress_area:\s*([0-9.eE+-]+)')


# ---------- simulation ----------
CELL_SIZE = 5.0


def parse_sim(path, n=None):
    """Return (rho, strain[], stress[]).  Falls back to L=n*5, A=(n*5)^2
    when header omits strain_length / stress_area (NS3 baseline does)."""
    if not os.path.exists(path):
        return None
    rho = sl = sa = None
    d, f = [], []
    started = False
    with open(path, errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not started:
                m = DENSITY_RE.match(s)
                if m: rho = float(m.group(1)); continue
                m = SLEN_RE.match(s)
                if m: sl = float(m.group(1)); continue
                m = SAREA_RE.match(s)
                if m: sa = float(m.group(1)); continue
                if 'X' in s and '_temp_3' in s:
                    started = True
                continue
            parts = s.split()
            if len(parts) == 2:
                try: d.append(float(parts[0])); f.append(float(parts[1]))
                except ValueError: pass
    if not started or len(d) < 5 or rho is None: return None
    if sl is None and n is not None: sl = n * CELL_SIZE
    if sa is None and n is not None: sa = (n * CELL_SIZE) ** 2
    if sl is None or sa is None: return None
    d, f = np.asarray(d), np.asarray(f)
    return rho, d / sl, f / sa


# ---------- experiment ----------
def parse_exp(csv_path):
    """Return dict: dims = list of 3 (T,W,H), specs = list of 3 (force[], disp[]).

    Shimadzu Trapezium layout:
      ... "Name","Thickness","Width","Height" ...
      "Size Unit:","mm","mm","mm"
      "<spec1>", T, W, H
      "<spec2>", T, W, H
      "<spec3>", T, W, H
      ...
      "<spec1>",
      "Time","Force","Disp.","Stroke"
      "sec","N","mm","mm"
      <data...>
      <blank>
      "<spec2>",
      ...
    """
    rows = []
    with open(csv_path, encoding='utf-8', errors='replace') as fh:
        reader = csv.reader(fh)
        for r in reader:
            rows.append(r)

    # 1) find dimension table
    dims = []
    spec_names = []
    for i, r in enumerate(rows):
        if len(r) >= 4 and r[0].strip() == 'Name' and \
           r[1].strip() == 'Thickness' and r[2].strip() == 'Width' and r[3].strip() == 'Height':
            # next non-empty rows after "Size Unit:" line
            j = i + 1
            while j < len(rows):
                rr = rows[j]
                if len(rr) >= 4 and rr[0].strip() and rr[0].strip() != 'Size Unit:':
                    try:
                        T = float(rr[1]); W = float(rr[2]); H = float(rr[3])
                        dims.append((T, W, H)); spec_names.append(rr[0].strip())
                    except ValueError:
                        pass
                if len(rr) == 1 or (len(rr) >= 1 and rr[0].strip() == ''):
                    if dims: break
                j += 1
            break

    # 2) find each specimen's data block by specimen name
    specs = []
    for sn in spec_names:
        block = None
        for k, r in enumerate(rows):
            if len(r) >= 1 and r[0].strip() == sn and (len(r) == 1 or r[1:] == [''] * (len(r) - 1) or r[1].strip() == ''):
                # next row should be the column header
                if k + 1 < len(rows) and rows[k + 1][:4] == ['Time', 'Force', 'Disp.', 'Stroke']:
                    block = k + 3   # skip header + units
                    break
        if block is None:
            specs.append((np.array([]), np.array([])))
            continue
        force, disp = [], []
        m = block
        while m < len(rows):
            r = rows[m]
            if len(r) < 4 or r[0].strip() == '':
                break
            try:
                force.append(float(r[1])); disp.append(float(r[2]))
            except ValueError:
                break
            m += 1
        specs.append((np.asarray(force), np.asarray(disp)))
    return spec_names, dims, specs


def energy_density(strain, stress, eps_cut):
    if strain.size == 0 or strain[-1] < eps_cut:
        return np.nan
    idx = np.searchsorted(strain, eps_cut)
    if idx < 2:
        return np.nan
    eps = np.r_[strain[:idx], eps_cut]
    sig = np.r_[stress[:idx], np.interp(eps_cut, strain, stress)]
    return float(np.trapz(sig, eps))


# ---------- compare per (topology, N) ----------
def find_exp_path(topo, n, slider=8):
    base = os.path.join(CONS, 'experiment', '20260422', topo)
    if not os.path.isdir(base):
        return []
    paths = []
    for sub in sorted(os.listdir(base)):
        full = os.path.join(base, sub)
        if not os.path.isdir(full): continue
        if not (f'N{n}_slider{slider}' in sub): continue
        if 'wrong_dir' in sub or 'fault' in sub or 'one_sample' in sub or 'remove' in sub:
            continue
        csvp = os.path.join(full, 'data.csv')
        if os.path.exists(csvp):
            paths.append((sub, csvp))
    return paths


def sim_paths_for(topo, n):
    return {
        'NS4':         os.path.join(CONS, 'simulation', 'NewSession4', topo, f'N{n}', 'feature_data.txt'),
        'NS3_baseline':os.path.join(CONS, 'simulation', 'NewSession3', f'{topo}__baseline', f'N{n}', 'feature_data.txt'),
    }


def main():
    rows_out = []
    fig, axes = plt.subplots(len(EXP_TOPOS), 5, figsize=(22, 4.0 * len(EXP_TOPOS)),
                              sharex=True)
    if len(EXP_TOPOS) == 1: axes = np.array([axes])

    for i_t, topo in enumerate(EXP_TOPOS):
        for i_n, n in enumerate([1, 2, 3, 4, 5]):
            ax = axes[i_t, i_n]
            ax.set_title(f'{topo}  N={n}', fontsize=10, fontweight='bold')
            ax.set_xlim(0, 0.55)
            ax.grid(True, alpha=0.25)
            if i_t == len(EXP_TOPOS) - 1:
                ax.set_xlabel('strain ε', fontsize=9)
            if i_n == 0:
                ax.set_ylabel('stress σ [MPa]', fontsize=9)

            sims = sim_paths_for(topo, n)
            ns4 = parse_sim(sims['NS4'], n)
            ns3 = parse_sim(sims['NS3_baseline'], n)
            rho_for_sea = ns4[0] if ns4 is not None else (ns3[0] if ns3 is not None else None)
            sea_sim_ns4 = energy_density(ns4[1], ns4[2], EPS_CUT) / ns4[0] if ns4 is not None else np.nan
            sea_sim_ns3 = energy_density(ns3[1], ns3[2], EPS_CUT) / ns3[0] if ns3 is not None else np.nan

            if ns4 is not None:
                ax.plot(ns4[1], ns4[2], color='#1f4e79', lw=2.0, label='NS4')
            if ns3 is not None:
                ax.plot(ns3[1], ns3[2], color='#c0504d', lw=1.4, ls='--', label='NS3 baseline')

            exp_paths = find_exp_path(topo, n, slider=8)
            sea_exp_vals, w_exp_vals, dim_log = [], [], []
            for sub, csvp in exp_paths:
                try:
                    names, dims, specs = parse_exp(csvp)
                except Exception as e:
                    print(f'[ERR] {csvp}: {e}'); continue
                for k, (force, disp) in enumerate(specs):
                    if force.size == 0 or k >= len(dims):
                        continue
                    T, W, H = dims[k]
                    if T <= 0 or W <= 0 or H <= 0: continue
                    strain = disp / H
                    stress = force / (T * W)
                    W_exp = energy_density(strain, stress, EPS_CUT)
                    if not np.isnan(W_exp):
                        w_exp_vals.append(W_exp)
                        if rho_for_sea:
                            sea_exp_vals.append(W_exp / rho_for_sea)
                    ax.plot(strain, stress, color='#2ca02c', lw=0.9, alpha=0.55,
                            label=f'exp ({sub})' if k == 0 else None)
                    dim_log.append((sub, names[k] if k < len(names) else '?', T, W, H))

            ax.axvline(EPS_CUT, color='k', ls=':', lw=0.7, alpha=0.4)
            if i_t == 0 and i_n == 0:
                ax.legend(fontsize=7, loc='upper left')

            rows_out.append(dict(
                topology=topo, N=n,
                rho_rel_sim=rho_for_sea,
                sea_ns4=sea_sim_ns4, sea_ns3=sea_sim_ns3,
                n_exp_specimens=len(sea_exp_vals),
                sea_exp_mean=float(np.mean(sea_exp_vals)) if sea_exp_vals else np.nan,
                sea_exp_std =float(np.std(sea_exp_vals))  if sea_exp_vals else np.nan,
                w_exp_mean  =float(np.mean(w_exp_vals))   if w_exp_vals   else np.nan,
            ))

    fig.suptitle(
        f'Experiment vs simulation σ-ε curves (slider=8)   [ε_cut={EPS_CUT} for SEA]',
        fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out_curves = os.path.join(CONS, 'exp_vs_sim_curves.png')
    plt.savefig(out_curves, dpi=130)
    plt.close(fig)
    print(f'Saved: {out_curves}')

    # CSV
    out_csv = os.path.join(CONS, 'exp_vs_sim_sea.csv')
    keys = ['topology', 'N', 'rho_rel_sim', 'sea_exp_mean', 'sea_exp_std',
            'n_exp_specimens', 'sea_ns4', 'sea_ns3', 'w_exp_mean']
    with open(out_csv, 'w', encoding='utf-8') as fh:
        fh.write(','.join(keys) + '\n')
        for r in rows_out:
            vals = ['' if (isinstance(r[k], float) and np.isnan(r[k])) else
                    (f'{r[k]:.6g}' if isinstance(r[k], float) else str(r[k]))
                    for k in keys]
            fh.write(','.join(vals) + '\n')
    print(f'Saved: {out_csv}')

    # Bar plot
    fig2, axes2 = plt.subplots(1, len(EXP_TOPOS), figsize=(4.4 * len(EXP_TOPOS), 4.5),
                                sharey=False)
    for ax, topo in zip(axes2, EXP_TOPOS):
        ns = [1, 2, 3, 4, 5]
        x = np.arange(5); w = 0.27
        e_m  = [next((r['sea_exp_mean'] for r in rows_out if r['topology']==topo and r['N']==n), np.nan) for n in ns]
        e_s  = [next((r['sea_exp_std']  for r in rows_out if r['topology']==topo and r['N']==n), np.nan) for n in ns]
        s4   = [next((r['sea_ns4']      for r in rows_out if r['topology']==topo and r['N']==n), np.nan) for n in ns]
        s3   = [next((r['sea_ns3']      for r in rows_out if r['topology']==topo and r['N']==n), np.nan) for n in ns]
        ax.bar(x - w, e_m, w, yerr=e_s, color='#2ca02c', label='exp', capsize=3)
        ax.bar(x,      s4, w, color='#1f4e79', label='NS4')
        ax.bar(x + w,  s3, w, color='#c0504d', label='NS3 baseline')
        ax.set_xticks(x); ax.set_xticklabels([f'N={n}' for n in ns], fontsize=9)
        ax.set_title(topo, fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.25, axis='y')
        if ax is axes2[0]:
            ax.set_ylabel(f'SEA = W/ρ_rel @ ε={EPS_CUT}  [MPa]', fontsize=10)
            ax.legend(fontsize=9)
    fig2.suptitle('SEA experiment vs NS4 vs NS3 baseline (slider=8)',
                  fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_bar = os.path.join(CONS, 'exp_vs_sim_sea_bar.png')
    plt.savefig(out_bar, dpi=140)
    plt.close(fig2)
    print(f'Saved: {out_bar}')

    # report
    print()
    print(f'{"topology":<14}{"N":>3}  {"rho":>7}  {"SEA_exp":>16}  {"SEA_NS4":>9}  {"SEA_NS3":>9}  {"exp/NS4":>8}')
    for r in rows_out:
        em = r['sea_exp_mean']; es = r['sea_exp_std']
        ratio = em / r['sea_ns4'] if (not np.isnan(em) and not np.isnan(r['sea_ns4'])) else float('nan')
        em_s = f'{em:6.3f}±{es:5.3f}' if not np.isnan(em) else '       n/a      '
        n4_s = f'{r["sea_ns4"]:7.3f}' if not np.isnan(r['sea_ns4']) else '   n/a '
        n3_s = f'{r["sea_ns3"]:7.3f}' if not np.isnan(r['sea_ns3']) else '   n/a '
        rho_s = f'{r["rho_rel_sim"]:.4f}' if r['rho_rel_sim'] else ' n/a   '
        rt_s = f'{ratio:6.2f}' if not np.isnan(ratio) else '   n/a'
        print(f'{r["topology"]:<14}{r["N"]:>3}  {rho_s:>7}  {em_s:>16}  {n4_s:>9}  {n3_s:>9}  {rt_s:>8}')


if __name__ == '__main__':
    main()
