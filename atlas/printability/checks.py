"""B1:Printability Checker 核心检查(纯函数层,MCP server 是薄壳)。

五工具契约,每响应必含 {value, threshold, pass, source}(另带
status/caveats/applicable/elapsed_s)。阈值唯一来源 =
.claude/skills/atlas/references/thresholds/dfam_rules.json(版本化)。

方法均经本机基准验证(atlas/bench_printability{,2,3}.py,2026-06 调研):
- 双引擎验证:trimesh 边-面计数 + manifold3d merge 往返 status
- 测厚:embree 射线法(BCC 真值 d=1.0 复现 0.1–0.5%)
- 悬垂:面法向分类(毫秒级);粉末床聚合物跳过
- 困粉:embree 列射线奇偶填充体素 + scipy flood-fill(禁 VTK
  select_enclosed_points 回退,实测 14–350 s 不可用)
- 间隙:manifold3d.min_gap(双体精确,190 ms)

红线:embreex 缺失必须 fail loudly,禁止静默回退慢引擎。
"""
import hashlib
import importlib
import json
import os
import time

import numpy as np
import trimesh
import manifold3d
from scipy import ndimage

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DFAM_RULES_PATH = os.path.join(
    _ROOT, '.claude', 'skills', 'atlas', 'references', 'thresholds',
    'dfam_rules.json')

_cache = {}


def require_ray_engine(module='trimesh.ray.ray_pyembree'):
    """embreex 缺失 fail loudly(红线:禁静默回退 VTK/纯 python 慢引擎)。"""
    try:
        importlib.import_module(module)
    except BaseException as e:
        raise RuntimeError(
            'embree 射线引擎不可用(pip install embreex);'
            '按红线禁止静默回退到慢速引擎') from e


def load_dfam_rules():
    with open(DFAM_RULES_PATH, encoding='utf-8') as f:
        return json.load(f)


def _envelope(value, threshold, passed, source, status='computed',
              caveats=None, applicable=True, elapsed_s=None):
    return {'value': value, 'threshold': threshold,
            'pass': (None if passed is None else bool(passed)),
            'source': source, 'status': status,
            'caveats': list(caveats or []), 'applicable': applicable,
            'elapsed_s': elapsed_s}


def _mesh_key(mesh, name, params):
    h = hashlib.sha256()
    h.update(np.asarray(mesh.vertices, np.float64).tobytes())
    h.update(np.asarray(mesh.faces, np.int64).tobytes())
    h.update(json.dumps(params, sort_keys=True).encode())
    return (name, h.hexdigest())


def _cached(mesh, name, params, fn):
    key = _mesh_key(mesh, name, params)
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


# ---------------------------------------------------------------- validate

def validate_mesh(mesh, process='MJF'):
    """双引擎水密/流形验证。"""
    def run():
        t0 = time.perf_counter()
        wt = bool(mesh.is_watertight)
        wc = bool(mesh.is_winding_consistent)
        iv = bool(mesh.is_volume)
        raw = manifold3d.Mesh(
            np.ascontiguousarray(mesh.vertices, np.float32),
            np.ascontiguousarray(mesh.faces, np.uint32))
        raw.merge()
        status3d = str(manifold3d.Manifold(raw).status())
        ok3d = status3d.endswith('NoError')
        value = {'watertight': wt, 'winding_consistent': wc,
                 'is_volume': iv, 'manifold3d_status': status3d,
                 'body_count': int(mesh.body_count)}
        return _envelope(
            value, {'watertight': True, 'manifold3d_status': 'NoError'},
            wt and wc and iv and ok3d,
            'trimesh 边-面计数 + manifold3d Mesh.merge 往返 status'
            '(双引擎,bench_printability.py 本机验证)',
            elapsed_s=round(time.perf_counter() - t0, 4))
    return _cached(mesh, 'validate_mesh', {'process': process}, run)


# ------------------------------------------------------------ min feature

def measure_min_feature(mesh, process='MJF', n_samples=400, seed=0):
    """embree 射线测厚:最小特征(杆径)vs 工艺最小可打印特征。"""
    require_ray_engine()
    rules = load_dfam_rules()
    rule = rules[process]['min_strut_diameter_mm']

    def run():
        t0 = time.perf_counter()
        pts, fidx = trimesh.sample.sample_surface(mesh, n_samples, seed=seed)
        nrm = mesh.face_normals[fidx]
        th = trimesh.proximity.thickness(mesh, pts, normals=nrm,
                                         method='ray')
        th = th[np.isfinite(th) & (th > 0)]
        value = {'min_mm': float(np.min(th)),
                 'p5_mm': float(np.percentile(th, 5)),
                 'median_mm': float(np.median(th)),
                 'n_valid_samples': int(len(th))}
        passed = value['p5_mm'] >= rule['value']
        caveats = ['判据用 p5(射线采样对尖角/相贯线的极小值噪声鲁棒);'
                   'min_mm 一并报告']
        if rule.get('source_type') == 'inference':
            caveats.append('阈值为内部工程取值(inference),输出须降级标注')
        return _envelope(value, rule['value'], passed,
                         f"阈值: {rule['source']};方法: embree 射线测厚"
                         f"(bench 验证 BCC d=1.0 误差 0.1-0.5%)",
                         caveats=caveats,
                         elapsed_s=round(time.perf_counter() - t0, 4))
    return _cached(mesh, 'min_feature',
                   {'process': process, 'n': n_samples, 'seed': seed}, run)


# ---------------------------------------------------------------- overhang

def check_overhangs(mesh, process='LPBF', build_dir=(0, 0, 1)):
    """面法向悬垂分类;粉末床聚合物(SLS/MJF)不适用,跳过。"""
    rules = load_dfam_rules()
    if process in ('SLS', 'MJF'):
        return _envelope(
            {'overhang_area_fraction': 0.0}, None, True,
            rules[process]['overhang_check']['source'],
            caveats=['粉末床聚合物自支撑,悬垂检查跳过'], applicable=False)

    ang_rule = rules[process]['self_supporting_overhang_deg']
    frac_rule = rules[process]['max_overhang_area_fraction']
    thr_deg = max(ang_rule['value'])  # 保守取 45

    def run():
        t0 = time.perf_counter()
        b = np.asarray(build_dir, float)
        b = b / np.linalg.norm(b)
        fn = mesh.face_normals
        downward = fn @ b < 0
        # 几何事实:朝下面的「法向与正下方向的夹角 theta」**就是**该面
        # 与水平板的夹角(平面倾角)。自支撑惯例:倾角 ≥ thr(45°) 自支撑;
        # theta < thr 需支撑。
        # 勘误 E12(D2 round-2 真 agent 实跑发现):原实现误取余角
        # alpha=90-theta 再判 alpha<thr,把判据带反——数了 [45°,90°) 的
        # 陡峭自支撑面、漏了 [0°,45°) 的真朝下面(竖直柱测 0、45° 斜柱
        # 反而 0.48)。正交验证=三圆柱已知几何回归测试。
        theta = np.degrees(np.arccos(np.clip(-(fn[downward] @ b), -1, 1)))
        areas = mesh.area_faces[downward]
        crit = theta < thr_deg
        frac = float(areas[crit].sum() / mesh.area) if mesh.area > 0 else 0.0
        value = {'overhang_area_fraction': frac,
                 'threshold_angle_deg': thr_deg,
                 'downward_face_count': int(downward.sum())}
        caveats = []
        if frac_rule.get('source_type') == 'inference':
            caveats.append('面积分数容限为内部工程取值(inference),'
                           '输出须降级标注')
        return _envelope(
            value, frac_rule['value'], frac <= frac_rule['value'],
            f"自支撑角: {ang_rule['source']};容限: {frac_rule['source']};"
            f"方法: 面法向分类(毫秒级,bench 验证)",
            caveats=caveats, elapsed_s=round(time.perf_counter() - t0, 4))
    return _cached(mesh, 'overhangs',
                   {'process': process, 'build_dir': list(build_dir)}, run)


# ------------------------------------------------------------- powder

def _voxel_occupancy(mesh, pitch):
    """embree 列射线奇偶填充(禁 VTK 回退)。"""
    require_ray_engine()
    lo = mesh.bounds[0] - 2 * pitch
    hi = mesh.bounds[1] + 2 * pitch
    xs = np.arange(lo[0], hi[0], pitch)
    ys = np.arange(lo[1], hi[1], pitch)
    zs = np.arange(lo[2], hi[2], pitch)
    gx, gy = np.meshgrid(xs, ys, indexing='ij')
    origins = np.column_stack([gx.ravel(), gy.ravel(),
                               np.full(gx.size, lo[2] - 1.0)])
    dirs = np.tile([0.0, 0.0, 1.0], (len(origins), 1))
    locs, ray_idx, _ = mesh.ray.intersects_location(
        origins, dirs, multiple_hits=True)
    occ = np.zeros((len(xs), len(ys), len(zs)), bool)
    n_odd = 0
    if len(locs):
        order = np.argsort(ray_idx, kind='stable')
        locs, ray_idx = locs[order], ray_idx[order]
        for r in np.unique(ray_idx):
            zh = np.sort(locs[ray_idx == r][:, 2])
            zh = zh[np.concatenate([[True], np.diff(zh) > 1e-9])]
            if len(zh) % 2:
                n_odd += 1
                zh = zh[:-1]
            i, j = divmod(int(r), len(ys))
            for k in range(0, len(zh) - 1, 2):
                occ[i, j, (zs >= zh[k]) & (zs <= zh[k + 1])] = True
    return occ, (xs, ys, zs), n_odd


def check_powder_escape(mesh, process='MJF', pitch=0.25, rho_rel=None,
                        topology=None, n_cell_layers=None):
    """体素 flood-fill 困粉检测 + Raz 排粉深度内插(MJF)。"""
    rules = load_dfam_rules()

    def run():
        t0 = time.perf_counter()
        occ, _, n_odd = _voxel_occupancy(mesh, pitch)
        void = ~occ
        lab, _ = ndimage.label(void)
        edge = np.unique(np.concatenate([
            lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(),
            lab[:, -1].ravel(), lab[:, :, 0].ravel(),
            lab[:, :, -1].ravel()]))
        trapped = void & ~np.isin(lab, edge)
        trapped_mm3 = float(trapped.sum() * pitch ** 3)
        tol_mm3 = 8 * pitch ** 3  # 体素量化容差
        value = {'trapped_void_mm3': trapped_mm3,
                 'voxel_pitch_mm': pitch,
                 'tolerance_mm3': tol_mm3,
                 'odd_parity_rays': n_odd}
        caveats = [f'体素量化容差 ±{tol_mm3:.3f} mm³(pitch={pitch});'
                   'Evaluator 不得据此误杀边界候选']
        passed = trapped_mm3 <= tol_mm3
        src = ('困粉: embree 列射线奇偶填充 + scipy flood-fill'
               '(bench_printability3.py 正负对照验证)')

        if process == 'MJF' and rho_rel is not None:
            pr = rules['MJF']['powder_removal_depth_vs_density']
            pts = np.array(pr['points_rho_rel_to_cleanable_cell_layers'])
            layers = float(np.interp(rho_rel, pts[:, 0], pts[:, 1]))
            value['cleanable_cell_layers'] = layers
            src += f"; 排粉深度: {pr['source']}"
            cv = [f"锚点内插({pr['note']})"]
            if topology != 'BCC':
                cv.append(f"适用域 {pr['validity_domain']} — 当前拓扑 "
                          f"{topology or '未知'} 越域,标 inference 降级")
            caveats.extend(cv)
            if n_cell_layers is not None and n_cell_layers > layers:
                passed = False
                caveats.append(f'深度 {n_cell_layers} 层 > 可清 '
                               f'{layers:.1f} 层,排粉不可行')
        return _envelope(value, tol_mm3, passed, src, caveats=caveats,
                         elapsed_s=round(time.perf_counter() - t0, 4))
    return _cached(mesh, 'powder',
                   {'process': process, 'pitch': pitch, 'rho': rho_rel,
                    'topo': topology, 'layers': n_cell_layers}, run)


# ---------------------------------------------------------------- clearance

def measure_clearance(mesh_a, mesh_b, process='MJF'):
    """双体最小间隙(manifold3d.min_gap 精确)vs 工艺最小间隙。"""
    rules = load_dfam_rules()
    rule = rules[process]['min_gap_mm']
    t0 = time.perf_counter()

    def to_manifold(m):
        raw = manifold3d.Mesh(
            np.ascontiguousarray(m.vertices, np.float32),
            np.ascontiguousarray(m.faces, np.uint32))
        raw.merge()
        return manifold3d.Manifold(raw)

    ma, mb = to_manifold(mesh_a), to_manifold(mesh_b)
    search = max(10.0, 4 * rule['value'])
    gap = float(ma.min_gap(mb, search))
    value = {'min_gap_mm': gap}
    caveats = ['双体间隙;单体内部杆间净距由生成期图级 DfAM 预检(B3)负责']
    if rule.get('source_type') == 'inference':
        caveats.append('阈值为内部工程取值(inference),输出须降级标注')
    return _envelope(value, rule['value'], gap >= rule['value'],
                     f"阈值: {rule['source']};方法: manifold3d.min_gap"
                     f"(bench 验证 0.8mm 精确复现)",
                     caveats=caveats,
                     elapsed_s=round(time.perf_counter() - t0, 4))
