"""B1 单测:五工具 BCC 正负对照、信封契约、<5s 预算、fail-loudly。"""
import time

import numpy as np
import manifold3d
import pytest
import trimesh

from atlas.geometry import generate_cell
from atlas.printability import (validate_mesh, measure_min_feature,
                                check_overhangs, check_powder_escape,
                                measure_clearance, require_ray_engine,
                                load_dfam_rules)

ENVELOPE = {'value', 'threshold', 'pass', 'source', 'status', 'caveats',
            'applicable', 'elapsed_s'}


@pytest.fixture(scope='module')
def bcc():
    return generate_cell('BCC', slider=4, radius=0.5).trimesh


@pytest.fixture(scope='module')
def bcc_thin():
    return generate_cell('BCC', slider=4, radius=0.35).trimesh  # d=0.7<0.8


def assert_envelope(r):
    assert ENVELOPE <= set(r), f'缺信封字段: {ENVELOPE - set(r)}'
    assert r['source'] and isinstance(r['source'], str)


# ---- validate_mesh 正负对照 ----

def test_validate_positive(bcc):
    r = validate_mesh(bcc)
    assert_envelope(r)
    assert r['pass'] is True
    assert r['value']['watertight'] and r['value']['is_volume']


def test_validate_negative(bcc):
    broken = trimesh.Trimesh(vertices=bcc.vertices,
                             faces=bcc.faces[:-1], process=False)
    r = validate_mesh(broken)
    assert r['pass'] is False


# ---- min_feature 正负对照 ----

def test_min_feature_positive(bcc):
    r = measure_min_feature(bcc, process='MJF')
    assert_envelope(r)
    assert r['pass'] is True
    # BCC r=0.5 真值杆径 1.0,射线测厚应复现到 ~1%
    assert abs(r['value']['median_mm'] - 1.0) < 0.05
    assert r['threshold'] == 0.8


def test_min_feature_negative(bcc_thin):
    r = measure_min_feature(bcc_thin, process='MJF')
    assert r['pass'] is False  # d=0.7 < 0.8


# ---- overhang:LPBF 检出 35.26° 杆;SLS/MJF 跳过 ----

def test_overhang_lpbf_flags_bcc(bcc):
    r = check_overhangs(bcc, process='LPBF')
    assert_envelope(r)
    assert r['applicable'] is True
    assert r['value']['overhang_area_fraction'] > 0.05
    assert r['pass'] is False  # BCC 35.26° < 45° 自支撑阈值


def test_overhang_skipped_for_powder_bed(bcc):
    r = check_overhangs(bcc, process='MJF')
    assert r['applicable'] is False and r['pass'] is True


def test_overhang_known_cylinders_regression():
    """E12 回归:三圆柱已知几何正交验证(D2 round-2 真 agent 发现带反)。

    正确语义(朝下面倾角 = 法向与正下方夹角,<45° 需支撑):
    - 竖直圆柱:仅底盖朝下(theta=0)→ frac ≈ cap/total ≈ 0.045
    - 水平圆柱:下四分之一壳带 → frac ≈ 0.23
    - 45° 斜柱:侧面 theta∈[45°,90°) 全自支撑,端盖恰在 45° 边界 → ≈ 0
    反向实现的输出是 0.0 / 0.227 / 0.477(45° 比水平还差,物理不可能)。
    """
    import numpy as np
    cyl = trimesh.creation.cylinder(radius=1.0, height=10.0, sections=64)
    v = check_overhangs(cyl, process='LPBF')['value'][
        'overhang_area_fraction']
    assert 0.03 < v < 0.06, f'竖直柱应只数底盖 ~0.045,得 {v}'

    h = cyl.copy()
    h.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi / 2, [0, 1, 0]))
    vh = check_overhangs(h, process='LPBF')['value'][
        'overhang_area_fraction']
    assert 0.18 < vh < 0.28, f'水平柱应 ~0.23(下四分壳),得 {vh}'

    d = cyl.copy()
    d.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi / 4, [0, 1, 0]))
    vd = check_overhangs(d, process='LPBF')['value'][
        'overhang_area_fraction']
    assert vd < 0.05, f'45° 斜柱应 ~0(自支撑边界),得 {vd}'
    assert vd < vh, '斜柱悬垂必须小于水平柱(反向实现在此必挂)'


# ---- powder escape:开放点阵过;封皮腔体困粉;开排粉孔后过 ----

def _skinned(with_vent):
    cell = generate_cell('BCC', slider=4, radius=0.5,
                         return_type='manifold')
    L = 5.0
    t = 1.0
    outer = manifold3d.Manifold.cube([L + 2 * t] * 3).translate([-t - L / 2] * 3)
    inner = manifold3d.Manifold.cube([L] * 3).translate([-L / 2] * 3)
    solid = manifold3d.Manifold.batch_boolean(
        [outer - inner, cell], manifold3d.OpType.Add)
    if with_vent:
        hole = manifold3d.Manifold.cylinder(4 * t, 1.0, 1.0, 24) \
            .translate([0, 0, L / 2 - t])
        solid = solid - hole
    out = solid.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties)[:, :3],
        faces=np.asarray(out.tri_verts))


def test_powder_open_lattice_passes(bcc):
    r = check_powder_escape(bcc, process='MJF', pitch=0.25)
    assert_envelope(r)
    assert r['pass'] is True
    assert r['value']['trapped_void_mm3'] <= r['value']['tolerance_mm3']


def test_powder_sealed_cavity_fails_and_vent_fixes():
    sealed = check_powder_escape(_skinned(False), pitch=0.25)
    assert sealed['pass'] is False
    assert sealed['value']['trapped_void_mm3'] > 50  # 封死腔体,显著困粉
    vented = check_powder_escape(_skinned(True), pitch=0.25)
    assert vented['pass'] is True


def test_powder_raz_interpolation(bcc):
    r = check_powder_escape(bcc, process='MJF', pitch=0.25, rho_rel=0.43,
                            topology='BCC')
    # 0.39->1.7, 0.47->1.5 中点内插 1.6
    assert abs(r['value']['cleanable_cell_layers'] - 1.6) < 1e-9
    r2 = check_powder_escape(bcc, process='MJF', pitch=0.25, rho_rel=0.43,
                             topology='Octet_truss', n_cell_layers=3)
    assert any('越域' in c for c in r2['caveats'])  # 跨拓扑标 inference
    assert r2['pass'] is False  # 3 层 > 可清 1.6 层


# ---- clearance 正负对照 ----

def test_clearance_controls(bcc):
    b_far = bcc.copy()
    b_far.apply_translation([5.0 + 1.2 + 1.0, 0, 0])  # 净距 1.2
    r = measure_clearance(bcc, b_far, process='MJF')
    assert_envelope(r)
    assert abs(r['value']['min_gap_mm'] - 1.2) < 0.02
    assert r['pass'] is True
    b_near = bcc.copy()
    b_near.apply_translation([5.0 + 0.8 + 1.0, 0, 0])  # 净距 0.8 < 1.0
    r2 = measure_clearance(bcc, b_near, process='MJF')
    assert r2['pass'] is False


# ---- 性能预算:单候选全套 <5 s ----

def test_single_candidate_under_5s():
    mesh = generate_cell('BCC', slider=4, radius=0.5, n=2).trimesh
    t0 = time.perf_counter()
    validate_mesh(mesh)
    measure_min_feature(mesh)
    check_overhangs(mesh, process='LPBF')
    check_powder_escape(mesh, pitch=0.25)
    dt = time.perf_counter() - t0
    assert dt < 5.0, f'单候选四检查 {dt:.2f}s 超预算'


# ---- embreex fail loudly ----

def test_ray_engine_fail_loudly():
    require_ray_engine()  # 当前环境必须可用
    with pytest.raises(RuntimeError, match='embree'):
        require_ray_engine(module='trimesh.ray.no_such_engine')


# ---- 阈值版本化 + MCP server 注册 ----

def test_rules_versioned():
    rules = load_dfam_rules()
    assert rules['_meta']['version'] >= '1.1'
    assert rules['LPBF']['max_overhang_area_fraction']['source_type'] \
        == 'inference'


def test_server_registers_five_tools():
    import asyncio
    from atlas.printability.server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names >= {'validate_mesh', 'measure_min_feature',
                     'check_overhangs', 'check_powder_escape',
                     'measure_clearance'}
