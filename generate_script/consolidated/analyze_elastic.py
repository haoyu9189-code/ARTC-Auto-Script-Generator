#!/usr/bin/env python3
"""For each topology N=2: extract elastic slope, yield peak (σ_pk, ε_pk) for both
experiment and current NS3-baseline simulation.  Compare to identify
physical mismatch (E_lattice, σ_y) instead of blunt scaling."""
import os, numpy as np
from compare_n2_full import parse_sim, parse_exp, find_exp, trim_exp, N, CONS, GENROOT

TOPOS = ['Auxetic', 'BCC', 'Iso_truss', 'Kelvin', 'Octet_truss']

def elastic_slope(eps, sig, sig_lo=0.05, sig_hi=0.5):
    """Linear fit of (eps,sig) over the rising portion sig in [sig_lo, sig_hi*peak]."""
    if len(eps) < 5: return None
    pk = sig.max()
    hi = max(sig_hi * pk, sig_lo + 0.01)
    mask = (sig >= sig_lo) & (sig <= hi)
    if mask.sum() < 5: return None
    slope, intercept = np.polyfit(eps[mask], sig[mask], 1)
    return slope, intercept

def find_first_peak(eps, sig, eps_max=0.15):
    """First local σ peak within ε < eps_max (so we get the elastic peak,
    not the densification peak at ε≈0.5)."""
    n = len(sig)
    if n < 5: return None
    # mask for early region
    cutoff = np.searchsorted(eps, eps_max)
    if cutoff < 5: return None
    seg_e = eps[:cutoff]; seg_s = sig[:cutoff]
    # find global max in this region
    i = int(np.argmax(seg_s))
    return seg_e[i], seg_s[i]

print(f'{"topo":<12} {"src":<8} {"E_latt":>9} {"sig_pk":>8} {"eps_pk":>8}')
print('-' * 52)

for topo in TOPOS:
    # experiment: collect all specimens
    exp_E, exp_pk_sig, exp_pk_eps = [], [], []
    for sub, csvp in find_exp(topo):
        names, dims, specs = parse_exp(csvp)
        for k, (force, disp) in enumerate(specs):
            if force.size == 0 or k >= len(dims): continue
            T, W, H = dims[k]
            if T <= 0 or W <= 0 or H <= 0: continue
            eps, sig = trim_exp(disp / H, force / (T * W))
            r = elastic_slope(eps, sig)
            E_i = r[0] if r else float('nan')
            pk = find_first_peak(eps, sig)
            if pk:
                exp_E.append(E_i); exp_pk_eps.append(pk[0]); exp_pk_sig.append(pk[1])
                print(f'{topo:<12} {"EXP#"+str(len(exp_E)):<8} {E_i:>9.1f} {pk[1]:>8.3f} {pk[0]:>8.4f}')

    if exp_pk_sig:
        med = np.median(exp_pk_sig); lo = min(exp_pk_sig); hi = max(exp_pk_sig)
        print(f'{topo:<12} {"EXP_med":<8} {np.median(exp_E):>9.1f} {med:>8.3f} {np.median(exp_pk_eps):>8.4f}'
              f'  range[{lo:.2f}-{hi:.2f}]')

    exp_E_mean   = np.median(exp_E)       if exp_E       else float('nan')
    exp_sig_mean = np.median(exp_pk_sig)  if exp_pk_sig  else float('nan')
    exp_eps_mean = np.median(exp_pk_eps)  if exp_pk_eps  else float('nan')

    # simulation NEW (current)
    new_ = parse_sim(os.path.join(GENROOT, topo, '5','0p5','8','StaCompre','feature_data.txt'))
    if new_ is not None:
        e, s = new_[1], new_[2]
        r = elastic_slope(e, s)
        E_sim = r[0] if r else float('nan')
        pk = find_first_peak(e, s)
        if pk:
            print(f'{topo:<12} {"SIM":<8} {E_sim:>9.1f} {pk[1]:>8.3f} {pk[0]:>8.4f}')
            if not np.isnan(exp_E_mean):
                print(f'{"":12} {"vs_med":<8} {E_sim/exp_E_mean:>9.2f}x {pk[1]/exp_sig_mean:>7.2f}x {pk[0]/exp_eps_mean:>7.2f}x')
        else:
            print(f'{topo:<12} {"SIM":<8} {E_sim:>9.1f} {"---":>8} {"---":>8}')
    print()
