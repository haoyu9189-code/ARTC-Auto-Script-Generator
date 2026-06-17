# -*- coding: utf-8 -*-
# Abaqus post-processing script - Array mode (3x3x3)
from abaqus import *
from abaqusConstants import *
import os
import time
import sys

print("="*80)
print("POST-PROCESSING SCRIPT STARTED (ARRAY MODE 3x3x3)")
print("Strain length (normalization): 15.0")
print("Stress area   (normalization): 225.0")
print("="*80)

script_dir = os.getcwd()
print("Working directory:", script_dir)

odb_filename = 'dual_column_web_5_0p5_4_DynaCompre_60_3x3x3.odb'
lck_filename = 'dual_column_web_5_0p5_4_DynaCompre_60_3x3x3.lck'

print("ODB file to process:", odb_filename)
print("Waiting for job completion...")

timeout = 3600
start_time = time.time()
job_status = "unknown"

try:
    while not os.path.exists(odb_filename):
        if time.time() - start_time > timeout:
            print("WARNING: Timeout - ODB file not created after 1 hour")
            job_status = "no_odb"
            break
        time.sleep(10)

    if job_status == "unknown":
        print("ODB file detected, waiting for analysis to complete...")
        while os.path.exists(lck_filename):
            if time.time() - start_time > timeout:
                print("WARNING: Timeout - Job still running after 1 hour")
                job_status = "timeout"
                break
            time.sleep(10)

        if job_status == "unknown":
            print("Analysis completed. Starting post-processing...")
            job_status = "successful"
        time.sleep(2)

except Exception as e:
    print("ERROR during job monitoring: " + str(e))
    job_status = "error"

print("Job status: " + job_status)

from odbAccess import openOdb
import xyPlot

if not os.path.exists(odb_filename):
    raise RuntimeError("ODB file not created - job failed")

if job_status == "timeout":
    extra_wait = 300
    extra_start = time.time()
    while os.path.exists(lck_filename) and (time.time() - extra_start < extra_wait):
        time.sleep(10)

try:
    odb = openOdb(path=odb_filename, readOnly=True)
except Exception as e:
    raise RuntimeError("Cannot open ODB file: " + str(e))

try:
    step = odb.steps['Step-1']
    disp_key = 'U2'
    force_key = 'RF2'
    if disp_key == 'U1':
        force_key = 'RF1'

    print("Available history regions:")
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        outputs = region.historyOutputs.keys()
        print("  - " + region_name + " -> " + str(outputs))

    def select_by_max_mean(candidates, output_key, label):
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0][0]
        else:
            max_mean = -1
            selected = None
            for name, reg in candidates:
                data = reg.historyOutputs[output_key].data
                mean_val = sum([abs(d[1]) for d in data]) / len(data) if data else 0
                if mean_val > max_mean:
                    max_mean = mean_val
                    selected = name
            return selected

    disp_candidates = []
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        if 'RIGIDPLATE-2' in region_name.upper():
            if disp_key in region.historyOutputs.keys():
                disp_candidates.append((region_name, region))

    disp_var = select_by_max_mean(disp_candidates, disp_key, "displacement")

    force_candidates = []
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        if 'RIGIDPLATE' in region_name.upper():
            if force_key in region.historyOutputs.keys():
                force_candidates.append((region_name, region))

    force_var = select_by_max_mean(force_candidates, force_key, "force")

    if force_var is None or disp_var is None:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('dual_column_web_5_0p5_4_DynaCompre_60_3x3x3' + "\n")
            f.write("status: no_outputs\n")
            f.write("strain_length: 15.0\n")
            f.write("stress_area: 225.0\n")
        raise ValueError("Cannot find required output variables (ODB may be empty from crashed solver)")

    force_region = step.historyRegions[force_var]
    force_data = force_region.historyOutputs[force_key]

    disp_region = step.historyRegions[disp_var]
    disp_data = disp_region.historyOutputs['U2']

    # Validate data arrays are non-empty (solver may have crashed at startup, ODB exists but empty)
    if not force_data.data or len(force_data.data) < 2 or not disp_data.data or len(disp_data.data) < 2:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('dual_column_web_5_0p5_4_DynaCompre_60_3x3x3' + "\n")
            f.write("status: empty_odb\n")
            f.write("strain_length: 15.0\n")
            f.write("stress_area: 225.0\n")
            f.write("force_points: " + str(len(force_data.data) if force_data.data else 0) + "\n")
            f.write("disp_points: " + str(len(disp_data.data) if disp_data.data else 0) + "\n")
        raise ValueError("ODB contains no time history data (likely solver crash at startup)")

    xy_force = session.XYData('Force', force_data.data)
    xy_disp = session.XYData('Displacement', disp_data.data)

    if xy_force is None or xy_disp is None:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('dual_column_web_5_0p5_4_DynaCompre_60_3x3x3' + "\n")
            f.write("status: xydata_failed\n")
            f.write("strain_length: 15.0\n")
            f.write("stress_area: 225.0\n")
        raise ValueError("session.XYData returned None")

    xy_combined = combine(abs(xy_disp), abs(xy_force))

    os.chdir(r"D:\ARTC\ARTC-Auto-Script\atlas\reports\tierd_crush\dual_column_web_n333")

    density = 0.0
    try:
        with open('density_temp.txt', 'r') as f:
            density = float(f.read().strip())
    except:
        density = 0.0

    with open('feature_data.txt', 'w') as f:
        f.write('dual_column_web_5_0p5_4_DynaCompre_60_3x3x3' + "\n")
        f.write("status: " + job_status + "\n")
        f.write("density: " + str(density) + "\n")
        f.write("strain_length: 15.0\n")
        f.write("stress_area: 225.0\n")
        f.write(str(disp_var) + " " + str(force_var))

    session.writeXYReport(fileName='feature_data.txt', xyData=(xy_combined, ), appendMode=ON)
    # ATLAS-P3A-ENERGY-GATE: ALLKE/ALLIE 准静态能量门数据(P3-A 注入)
    try:
        _e_reg = None
        for _rn in step.historyRegions.keys():
            _ho = step.historyRegions[_rn].historyOutputs
            if 'ALLKE' in _ho.keys() and 'ALLIE' in _ho.keys():
                _e_reg = step.historyRegions[_rn]
                break
        _ef = open('energy_data.txt', 'w')
        if _e_reg is None:
            _ef.write('status: no_energy_history\n')
        else:
            _keys = [_k for _k in ('ALLIE','ALLKE','ALLAE','ALLVD',
                                   'ALLFD','ALLWK')
                     if _k in _e_reg.historyOutputs.keys()]
            _ef.write('status: ok\n')
            _ef.write('time ' + ' '.join([_k.lower() for _k in _keys])
                      + '\n')
            _maps = {}
            for _k in _keys:
                _maps[_k] = {}
                for _p in _e_reg.historyOutputs[_k].data:
                    _maps[_k][_p[0]] = _p[1]
            for _p in _e_reg.historyOutputs['ALLIE'].data:
                _t = _p[0]
                _row = [str(_t)] + [str(_maps[_k].get(_t, 0.0))
                                    for _k in _keys]
                _ef.write(' '.join(_row) + '\n')
        _ef.close()
    except Exception as _e_err:
        try:
            _ef = open('energy_data.txt', 'w')
            _ef.write('status: error ' +
                      str(_e_err).replace('\n', ' ') + '\n')
            _ef.close()
        except:
            pass

    odb.close()

    print("Post-processing completed successfully!")

except Exception as e:
    print("FATAL ERROR: " + str(e))
    import traceback
    traceback.print_exc()
    raise
