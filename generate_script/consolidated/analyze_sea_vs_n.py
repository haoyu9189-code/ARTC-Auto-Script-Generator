#!/usr/bin/env python3
"""
SEA vs N analysis across consolidated dataset.

For each (session, topology, variant, N):
  strain  = X / strain_length
  stress  = F / stress_area  (MPa)
  W(eps)  = trapz(stress, strain) up to a cutoff eps
  SEA     = W / rho_rel        (specific energy absorption per unit relative density,
                                proportional to true mass-SEA up to a constant rho_solid)

Outputs:
  sea_vs_n.csv               — per-curve table
  sea_vs_n_per_topology.png  — 6x4 grid, one panel per topology, NS4 vs NS3 vs NS2
  sea_vs_n_summary.png       — mean+/-std SEA(N) aggregated over topologies, per session
"""

import os
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CONS = os.path.dirname(os.path.abspath(__file__))
EPS_CUTS = (0.10, 0.25, 0.50)
PRIMARY_EPS = 0.25
CELL_SIZE = 5.0

CELL_TYPES = [
    'AFCC', 'Auxetic', 'BCC', 'BCCZ',
    'CBCC', 'Cubic', 'CubicRosette', 'Cuboctahedron_Z',
    'Diamond', 'DiamondPlus', 'FBCCXYZ', 'FBCCZ',
    'FCC', 'FCCZ', 'G7', 'Iso_truss',
    'Kelvin', 'Octahedron', 'Octet_truss', 'Rhombic',
    'Tetrahedron_base', 'Truncated_cube', 'Truncated_Octoctahedron', 'WeairePhelan',
]
EXCLUDED = {'CBCC', 'Cubic', 'FCCZ', 'Truncated_cube', 'G7'}
N_COLORS = {1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c', 4: '#d62728', 5: '#9467bd'}
SESSION_STYLE = {
    'NS4':         dict(color='#1f4e79', marker='o', ls='-',  label='NS4 (sphere×1.2)'),
    'NS3_baseline':dict(color='#c0504d', marker='s', ls='--', label='NS3 baseline'),
    'NS2_orig6':   dict(color='#7f7f7f', marker='^', ls=':',  label='NS2 original_6'),
}

DENSITY_RE = re.compile(r'^density:\s*([0-9.eE+-]+)')
SLEN_RE    = re.compile(r'^strain_length:\s*([0-9.eE+-]+)')
SAREA_RE   = re.compile(r'^stress_area:\s*([0-9.eE+-]+)')


def parse_feature(path):
    """Return (rho_rel, strain_length, stress_area, disp_arr, force_arr) or None."""
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
                if m:
                    rho = float(m.group(1)); continue
                m = SLEN_RE.match(s)
                if m:
                    sl = float(m.group(1)); continue
                m = SAREA_RE.match(s)
                if m:
                    sa = float(m.group(1)); continue
                if 'X' in s and '_temp_3' in s:
                    started = True
                continue
            parts = s.split()
            if len(parts) == 2:
                try:
                    d.append(float(parts[0])); f.append(float(parts[1]))
                except ValueError:
                    pass
    if not started or len(d) < 5 or rho is None or sl is None or sa is None:
        return None
    return rho, sl, sa, np.asarray(d), np.asarray(f)


def energy_density(strain, stress, eps_cut):
    """Trapz integral of stress over strain in [0, eps_cut].  Units: MPa."""
    if strain[-1] < eps_cut:
        return np.nan
    idx = np.searchsorted(strain, eps_cut)
    if idx < 2:
        return np.nan
    eps = np.r_[strain[:idx], eps_cut]
    sig = np.r_[stress[:idx], np.interp(eps_cut, strain, stress)]
    return float(np.trapz(sig, eps))


def session_paths(ct, n):
    """Yield (session_label, path) tuples for the three primary sources."""
    yield ('NS4',
           os.path.join(CONS, 'simulation', 'NewSession4', ct, f'N{n}', 'feature_data.txt'))
    yield ('NS3_baseline',
           os.path.join(CONS, 'simulation', 'NewSession3', f'{ct}__baseline', f'N{n}', 'feature_data.txt'))
    yield ('NS2_orig6',
           os.path.join(CONS, 'simulation', 'NewSession2', 'original_6', ct, f'N{n}', 'feature_data.txt'))


def collect():
    rows = []
    for ct in CELL_TYPES:
        for n in (1, 2, 3, 4, 5):
            for sess, path in session_paths(ct, n):
                parsed = parse_feature(path)
                if parsed is None:
                    continue
                rho, sl, sa, disp, force = parsed
                strain = disp / sl
                stress = force / sa
                row = dict(session=sess, topology=ct, N=n, density=rho,
                           strain_length=sl, stress_area=sa,
                           eps_max=float(strain.max()),
                           excluded=ct in EXCLUDED)
                for ec in EPS_CUTS:
                    W = energy_density(strain, stress, ec)
                    row[f'W_eps{ec:g}'] = W
                    row[f'SEA_eps{ec:g}'] = (W / rho) if (W is not None and not np.isnan(W) and rho > 0) else np.nan
                rows.append(row)
    return rows


def write_csv(rows, path):
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(','.join(keys) + '\n')
        for r in rows:
            vals = []
            for k in keys:
                v = r[k]
                if isinstance(v, float):
                    vals.append('' if np.isnan(v) else f'{v:.6g}')
                else:
                    vals.append(str(v))
            fh.write(','.join(vals) + '\n')


def plot_per_topology(rows, eps_cut, out_path):
    fig, axes = plt.subplots(6, 4, figsize=(22, 28))
    axes = axes.flatten()
    sea_key = f'SEA_eps{eps_cut:g}'
    for idx, ct in enumerate(CELL_TYPES):
        ax = axes[idx]
        for sess, style in SESSION_STYLE.items():
            xs, ys = [], []
            for n in (1, 2, 3, 4, 5):
                hits = [r for r in rows
                        if r['topology'] == ct and r['session'] == sess
                        and r['N'] == n and not np.isnan(r[sea_key])]
                if hits:
                    xs.append(n); ys.append(hits[0][sea_key])
            if xs:
                ax.plot(xs, ys, marker=style['marker'], linestyle=style['ls'],
                        color=style['color'], label=style['label'],
                        linewidth=1.6, markersize=6, alpha=0.9)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.set_xlabel('N', fontsize=8)
        ax.set_ylabel(f'SEA  (W/ρ_rel @ ε={eps_cut})  [MPa]', fontsize=7)
        ax.grid(True, alpha=0.25)
        title_color = 'red' if ct in EXCLUDED else 'black'
        ax.set_title(ct, fontsize=10, fontweight='bold', color=title_color)
        if ct in EXCLUDED:
            for sp in ax.spines.values():
                sp.set_edgecolor('red'); sp.set_linewidth(2.0)
    handles, labels = [], []
    seen = set()
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in seen:
                handles.append(h); labels.append(l); seen.add(l)
    fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=10, frameon=True)
    fig.suptitle(
        f'Specific Energy Absorption vs N  (ε_cut = {eps_cut})\n'
        f'SEA = ∫₀^ε σ dε / ρ_rel   |   24 topologies  |  red frame = excluded set',
        fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0.035, 1, 0.965])
    plt.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f'Saved: {out_path}')


def plot_summary(rows, out_path):
    fig, axes = plt.subplots(1, len(EPS_CUTS), figsize=(6.2 * len(EPS_CUTS), 5.2),
                             sharex=True)
    for ax, ec in zip(axes, EPS_CUTS):
        sea_key = f'SEA_eps{ec:g}'
        for sess, style in SESSION_STYLE.items():
            ns = [1, 2, 3, 4, 5]
            mean_all, std_all = [], []
            mean_inc, std_inc = [], []
            for n in ns:
                vals_all = [r[sea_key] for r in rows
                            if r['session'] == sess and r['N'] == n
                            and not np.isnan(r[sea_key])]
                vals_inc = [r[sea_key] for r in rows
                            if r['session'] == sess and r['N'] == n
                            and not r['excluded'] and not np.isnan(r[sea_key])]
                mean_all.append(np.mean(vals_all) if vals_all else np.nan)
                std_all.append(np.std(vals_all) if vals_all else np.nan)
                mean_inc.append(np.mean(vals_inc) if vals_inc else np.nan)
                std_inc.append(np.std(vals_inc) if vals_inc else np.nan)
            mean_inc = np.array(mean_inc); std_inc = np.array(std_inc)
            ok = ~np.isnan(mean_inc)
            if ok.any():
                xs = np.array(ns)[ok]
                m  = mean_inc[ok]; s = std_inc[ok]
                ax.errorbar(xs, m, yerr=s, color=style['color'],
                            marker=style['marker'], linestyle=style['ls'],
                            label=style['label'], linewidth=1.8, capsize=3,
                            markersize=7)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.set_xlabel('N (cells per side)', fontsize=11)
        ax.set_ylabel(f'mean SEA over topologies (excluded set removed)  [MPa]',
                      fontsize=10)
        ax.set_title(f'ε_cut = {ec}', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
    fig.suptitle(
        'SEA(N) summary — mean ± std across 19 non-excluded topologies\n'
        'higher N → larger array → tests for size effect',
        fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f'Saved: {out_path}')


def report_text(rows):
    """Console-style summary: per-session SEA(N) means and N1→N5 ratios."""
    lines = []
    sea_key = f'SEA_eps{PRIMARY_EPS:g}'
    lines.append(f'Primary epsilon cutoff: {PRIMARY_EPS}')
    lines.append('Aggregating over topologies NOT in EXCLUDED set:')
    for sess in SESSION_STYLE:
        means = []
        counts = []
        for n in (1, 2, 3, 4, 5):
            vals = [r[sea_key] for r in rows
                    if r['session'] == sess and r['N'] == n
                    and not r['excluded'] and not np.isnan(r[sea_key])]
            means.append(np.mean(vals) if vals else float('nan'))
            counts.append(len(vals))
        lines.append(f'  {sess:14s}  '
                     f'N=1:{means[0]:7.3f} (n={counts[0]:2d})  '
                     f'N=2:{means[1]:7.3f} (n={counts[1]:2d})  '
                     f'N=3:{means[2]:7.3f} (n={counts[2]:2d})  '
                     f'N=4:{means[3]:7.3f} (n={counts[3]:2d})  '
                     f'N=5:{means[4]:7.3f} (n={counts[4]:2d})')
        if means[0] and not np.isnan(means[0]) and not np.isnan(means[4]):
            lines.append(f'                  N5/N1 = {means[4]/means[0]:.3f}   '
                         f'N5/N2 = {means[4]/means[1]:.3f}')
    lines.append('')
    lines.append('Per-topology N5/N1 ratio (NS4):')
    for ct in CELL_TYPES:
        if ct in EXCLUDED:
            continue
        v1 = next((r[sea_key] for r in rows
                   if r['topology'] == ct and r['session'] == 'NS4' and r['N'] == 1
                   and not np.isnan(r[sea_key])), None)
        v5 = next((r[sea_key] for r in rows
                   if r['topology'] == ct and r['session'] == 'NS4' and r['N'] == 5
                   and not np.isnan(r[sea_key])), None)
        if v1 and v5:
            lines.append(f'  {ct:24s}  N1={v1:7.3f}  N5={v5:7.3f}  ratio={v5/v1:6.3f}')
    return '\n'.join(lines)


def main():
    rows = collect()
    write_csv(rows, os.path.join(CONS, 'sea_vs_n.csv'))
    print(f'Parsed {len(rows)} curves')
    plot_per_topology(rows, PRIMARY_EPS,
                      os.path.join(CONS, 'sea_vs_n_per_topology.png'))
    plot_summary(rows, os.path.join(CONS, 'sea_vs_n_summary.png'))
    txt = report_text(rows)
    with open(os.path.join(CONS, 'sea_vs_n_report.txt'), 'w', encoding='utf-8') as fh:
        fh.write(txt + '\n')
    print()
    print(txt)


if __name__ == '__main__':
    main()
