"""
Demo: 3 种 Watertight Remeshing 方案对比
输入: Truncated_cube (slider=8, radius=0.5, cell_size=5)
输出: demo_stl/ 下 4 个 STL 文件
"""

import os
import time
import numpy as np
import pyvista as pv
from structure_set import get_crystal_structure
from config import Config

OUT_DIR = os.path.join(os.path.dirname(__file__), 'demo_stl')
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 解析晶格结构
# ============================================================
cell_type = 'Truncated_cube'
slider = 8
radius = 0.5
cell_size = 5.0
sphere_radius = radius * Config.SPHERE_RADIUS_RATIO_SCRIPT
resolution = 24

structure_output = get_crystal_structure(cell_type, slider)
lines = structure_output.split('\n')

coords = {}
cylinders = []
in_cyl = False

for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if 'cylinders = [' in line:
        in_cyl = True
        continue
    if in_cyl and line == ']':
        in_cyl = False
        continue
    if '=' in line and not in_cyl and 'cylinders' not in line:
        parts = line.split('=', 1)
        name = parts[0].strip()
        val = eval(parts[1].strip())
        coords[name] = np.array(val, dtype=float)
    elif in_cyl:
        cyl_line = line.rstrip(',').strip()
        if cyl_line:
            inner = cyl_line.strip('()')
            a_name, b_name = [s.strip() for s in inner.split(',')]
            cylinders.append((a_name, b_name))

print(f"Structure: {cell_type}, slider={slider}")
print(f"  Nodes: {len(coords)}, Struts: {len(cylinders)}")
print(f"  radius={radius}, sphere_radius={sphere_radius}")

# 构建 PyVista mesh 列表
pv_meshes = []
for a_name, b_name in cylinders:
    if a_name not in coords or b_name not in coords:
        continue
    p0, p1 = coords[a_name], coords[b_name]
    d = p1 - p0
    L = np.linalg.norm(d)
    if L < 1e-6:
        continue
    cyl = pv.Cylinder(center=(p0+p1)/2, direction=d/L,
                       radius=radius, height=L,
                       resolution=resolution, capping=True)
    pv_meshes.append(cyl)

for name, point in coords.items():
    sph = pv.Sphere(radius=sphere_radius, center=point,
                     theta_resolution=resolution, phi_resolution=resolution)
    pv_meshes.append(sph)

# 原始拼接
raw = pv_meshes[0]
for m in pv_meshes[1:]:
    raw = raw.merge(m)
raw.save(os.path.join(OUT_DIR, '0_raw_combined.stl'))
print(f"\n[0] Raw combined: {raw.n_points} pts, {raw.n_cells} cells")
print(f"    Saved: 0_raw_combined.stl (有内部面)")


# ============================================================
# 方案 1: PyVista boolean_union (逐个合并)
# ============================================================
print("\n=== 方案 1: PyVista boolean_union ===")
t0 = time.time()
try:
    # PyVista boolean 对复杂形状容易失败，尝试分步
    result = pv_meshes[0].copy()
    ok, fail = 0, 0
    for m in pv_meshes[1:]:
        try:
            result = result.boolean_union(m)
            ok += 1
        except Exception:
            fail += 1
            result = result.merge(m)
    dt = time.time() - t0
    result.save(os.path.join(OUT_DIR, '1_pyvista_boolean.stl'))
    print(f"  Time: {dt:.2f}s | Union OK: {ok}, Failed: {fail}")
    print(f"  Points: {result.n_points}, Cells: {result.n_cells}")
    print(f"  Manifold: {result.is_manifold}")
except Exception as e:
    print(f"  FAILED: {e}")


# ============================================================
# 方案 2: PyMeshFix (对原始拼接做 repair)
# ============================================================
print("\n=== 方案 2: PyMeshFix ===")
t0 = time.time()
try:
    import pymeshfix

    surf = raw.extract_surface()
    if not surf.is_all_triangles:
        surf = surf.triangulate()

    meshfix = pymeshfix.MeshFix(surf)
    meshfix.repair(joincomp=True)
    repaired = meshfix.mesh

    dt = time.time() - t0
    repaired.save(os.path.join(OUT_DIR, '2_pymeshfix.stl'))
    print(f"  Time: {dt:.2f}s")
    print(f"  Points: {repaired.n_points}, Cells: {repaired.n_cells}")
    print(f"  Manifold: {repaired.is_manifold}")
except Exception as e:
    print(f"  FAILED: {e}")
    import traceback; traceback.print_exc()


# ============================================================
# 方案 3: Manifold3D (用原语构建 + 精确布尔并集)
# ============================================================
print("\n=== 方案 3: Manifold3D ===")
t0 = time.time()
try:
    import manifold3d
    import trimesh

    seg = 32  # manifold3d 分辨率

    def make_strut(p0, p1, r):
        """创建从 p0 到 p1 的圆柱 (manifold3d)"""
        d = p1 - p0
        L = np.linalg.norm(d)
        if L < 1e-6:
            return None
        d_unit = d / L

        # manifold3d cylinder 沿 Z 轴, 高度 L
        cyl = manifold3d.Manifold.cylinder(L, r, r, seg)

        # 旋转: Z轴 -> d_unit
        z = np.array([0, 0, 1.0])
        cross_v = np.cross(z, d_unit)
        dot_v = np.dot(z, d_unit)

        if np.linalg.norm(cross_v) < 1e-8:
            if dot_v > 0:
                rot = np.eye(3)
            else:
                rot = np.diag([1.0, -1.0, -1.0])
        else:
            cross_n = cross_v / np.linalg.norm(cross_v)
            angle = np.arccos(np.clip(dot_v, -1, 1))
            K = np.array([
                [0, -cross_n[2], cross_n[1]],
                [cross_n[2], 0, -cross_n[0]],
                [-cross_n[1], cross_n[0], 0]
            ])
            rot = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K

        # manifold3d transform: 3x4 矩阵 [[R | t]] (3行4列)
        mat = np.zeros((3, 4))
        mat[:3, :3] = rot
        mat[:3, 3] = p0
        cyl = cyl.transform(mat.tolist())
        return cyl

    # 构建所有组件
    manifolds = []

    for a_name, b_name in cylinders:
        if a_name not in coords or b_name not in coords:
            continue
        strut = make_strut(coords[a_name], coords[b_name], radius)
        if strut is not None:
            manifolds.append(strut)

    for name, point in coords.items():
        sph = manifold3d.Manifold.sphere(sphere_radius, seg)
        sph = sph.translate(point.tolist())
        manifolds.append(sph)

    print(f"  Components: {len(manifolds)}")

    # 用 batch_boolean 做批量并集 (比逐个 + 快得多)
    result_m = manifold3d.Manifold.compose(manifolds)
    # compose 只是放在一起，需要 batch_boolean 或逐步 union
    # 实际上 compose 后 + 空 Manifold 可以触发 union
    # 更好的方式: 逐步合并
    result_m = manifolds[0]
    for m in manifolds[1:]:
        result_m = result_m + m  # boolean union

    out_mesh = result_m.to_mesh()
    verts = np.array(out_mesh.vert_properties[:, :3])
    faces = np.array(out_mesh.tri_verts)

    tri_mesh = trimesh.Trimesh(vertices=verts, faces=faces)
    dt = time.time() - t0
    tri_mesh.export(os.path.join(OUT_DIR, '3_manifold3d.stl'))

    print(f"  Time: {dt:.2f}s")
    print(f"  Vertices: {len(verts)}, Faces: {len(faces)}")
    print(f"  Watertight: {tri_mesh.is_watertight}")
    print(f"  Volume: {tri_mesh.volume:.2f} mm3")
except Exception as e:
    print(f"  FAILED: {e}")
    import traceback; traceback.print_exc()


# ============================================================
# 汇总
# ============================================================
print("\n" + "="*60)
print("STL 文件已保存到:", OUT_DIR)
for f in sorted(os.listdir(OUT_DIR)):
    if f.endswith('.stl'):
        size = os.path.getsize(os.path.join(OUT_DIR, f))
        print(f"  {f:35s} {size/1024:.0f} KB")
print("="*60)
print("请用 MeshLab / Windows 3D Viewer 打开对比")
