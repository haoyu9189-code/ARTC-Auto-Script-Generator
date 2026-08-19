"""Wait for Aux+BCC Abaqus jobs, run postprocess, compare bv=0.25/2.0 (OLD) vs bv=0.06/1.2 (NEW).
Run as: python bv_sensitivity_run.py  (waits up to 60 min)."""
import os, time, subprocess, sys

ABQ = r'D:\ABAQUS\2023\Commands\abaqus.bat'
ROOT = r'D:\ARTC\ARTC-Auto-Script\generate_script'

JOBS = [
    ('Auxetic', os.path.join(ROOT, 'Auxetic', '5', '0p5', '8', 'StaCompre'),
                'Auxetic_5_0p5_8_StaCompre_2x2x2'),
    ('BCC',     os.path.join(ROOT, 'BCC',     '5', '0p5', '8', 'StaCompre'),
                'BCC_5_0p5_8_StaCompre_2x2x2'),
]

def wait_job(jobname, workdir, timeout=3600):
    lck = os.path.join(workdir, jobname + '.lck')
    odb = os.path.join(workdir, jobname + '.odb')
    sta = os.path.join(workdir, jobname + '.sta')
    t0 = time.time()
    print('[wait] %s' % jobname)
    while time.time() - t0 < timeout:
        if os.path.exists(odb) and not os.path.exists(lck):
            # confirm completion via .sta
            try:
                with open(sta, 'r') as f: s = f.read()
                if 'COMPLETED SUCCESSFULLY' in s:
                    print('  -> done (%.0f s)' % (time.time() - t0))
                    return 'success'
                if 'NOT BEEN COMPLETED' in s or 'ERROR' in s:
                    print('  -> failed (sta says NOT COMPLETED)')
                    return 'failed'
            except IOError:
                pass
            # odb exists, no lck, but sta unclear — give it 5s then assume done
            time.sleep(5)
            return 'success'
        time.sleep(15)
    print('  -> TIMEOUT after %d s' % timeout)
    return 'timeout'

def run_postprocess(jobname, workdir):
    pp = os.path.join(workdir, jobname + '_postprocess.py')
    print('[postprocess] %s' % jobname)
    p = subprocess.Popen([ABQ, 'cae', 'noGUI=' + pp],
                         cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate(timeout=600)
    out = out.decode('utf-8', errors='replace')
    if 'Post-processing completed successfully' in out:
        print('  -> postprocess OK')
        return True
    print('  -> postprocess output tail:')
    print('\n'.join(out.splitlines()[-30:]))
    return False

def parse_feature(path):
    """Return list of (disp, force) pairs from feature_data.txt."""
    if not os.path.exists(path): return []
    with open(path) as f: lines = f.readlines()
    pairs = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith(('Auxetic','BCC','status','density','strain_length','stress_area','Node','X','_temp')):
            continue
        parts = ln.split()
        if len(parts) >= 2:
            try:
                d = float(parts[0].replace('E','e'))
                # Abaqus rpt format is `1.234E-03` already, just convert
                f_ = float(parts[1].replace('E','e'))
                pairs.append((d, f_))
            except ValueError:
                pass
    return pairs

def write_compare_csv(label, workdir, out_csv):
    new = parse_feature(os.path.join(workdir, 'feature_data.txt'))
    old = parse_feature(os.path.join(workdir, 'feature_data_OLD_bv0p25.txt'))
    rows = ['# strain = disp/10, stress = force/100', '# label,bv,strain,stress']
    for d, f in old: rows.append('%s,OLD_0.25/2.0,%.6e,%.6e' % (label, d/10.0, f/100.0))
    for d, f in new: rows.append('%s,NEW_0.06/1.2,%.6e,%.6e' % (label, d/10.0, f/100.0))
    with open(out_csv, 'w') as fp: fp.write('\n'.join(rows) + '\n')
    print('  CSV: %s  (old=%d new=%d pts)' % (out_csv, len(old), len(new)))
    return new, old

# === main ===
results = {}
for label, workdir, jobname in JOBS:
    status = wait_job(jobname, workdir)
    results[label] = {'status': status, 'workdir': workdir, 'jobname': jobname}

# postprocess + parse only for successful ones
out_dir = r'D:\ARTC\ARTC-Auto-Script\bv_sensitivity'
if not os.path.exists(out_dir): os.makedirs(out_dir)

for label, info in results.items():
    if info['status'] != 'success':
        print('[skip postprocess] %s: status=%s' % (label, info['status']))
        continue
    ok = run_postprocess(info['jobname'], info['workdir'])
    if not ok:
        print('[warn] postprocess returned non-success for %s' % label)
    csv = os.path.join(out_dir, label + '_bv_compare.csv')
    new, old = write_compare_csv(label, info['workdir'], csv)

    # peak summary
    if old:
        d_old = [x[0]/10.0 for x in old]; s_old = [x[1]/100.0 for x in old]
        m = [(s, d) for s, d in zip(s_old, d_old) if d <= 0.20]
        peak_old = max(m) if m else (None, None)
    else: peak_old = (None, None)
    if new:
        d_new = [x[0]/10.0 for x in new]; s_new = [x[1]/100.0 for x in new]
        m = [(s, d) for s, d in zip(s_new, d_new) if d <= 0.20]
        peak_new = max(m) if m else (None, None)
    else: peak_new = (None, None)

    print('[%s] OLD peak σ=%s @ ε=%s' % (label, peak_old[0], peak_old[1]))
    print('[%s] NEW peak σ=%s @ ε=%s' % (label, peak_new[0], peak_new[1]))

print('=== ALL DONE ===')
