"""Bench 3: (1) trapped-powder positive control (skinned lattice), (2) STL round-trip validation."""
import sys, time, os
import numpy as np
sys.path.insert(0, r"D:\ARTC\ARTC-Auto-Script")
import manifold3d, trimesh, pyvista as pv
from scipy import ndimage
from bench_printability2 import parse, strut, build

# ---- 1. skinned lattice: shell box + lattice inside -> trapped internal void ----
lat, span, cell = build("BCC", 4, 0.5, 24, 2)   # 2x2x2 BCC, spans [0,10]
L = span * 2
shell_t = 1.0
outer = manifold3d.Manifold.cube([L + 2*shell_t]*3).translate([-shell_t]*3)
inner = manifold3d.Manifold.cube([L]*3)
shell = outer - inner
solid = manifold3d.Manifold.batch_boolean([shell, lat], manifold3d.OpType.Add)
print(f"skinned: tris={solid.num_tri()} status={solid.status()} vol={solid.volume():.1f}")

mgl = solid.to_mesh()
V = np.asarray(mgl.vert_properties[:, :3], np.float64)
F = np.asarray(mgl.tri_verts, np.int64)
pvm = pv.PolyData(V, np.column_stack([np.full(len(F), 3), F]).ravel())

pitch = 0.25
lo = V.min(0) - 2*pitch; hi = V.max(0) + 2*pitch
xs_ = np.arange(lo[0], hi[0], pitch); ys_ = np.arange(lo[1], hi[1], pitch); zs_ = np.arange(lo[2], hi[2], pitch)
t0 = time.perf_counter()
occ = np.zeros((len(xs_), len(ys_), len(zs_)), bool)
for i, x in enumerate(xs_):
    for j, y in enumerate(ys_):
        xp, _ = pvm.ray_trace([x, y, lo[2]-1], [x, y, hi[2]+1])
        if len(xp) < 2: continue
        zh = np.sort(xp[:, 2]); zh = zh[np.concatenate([[True], np.diff(zh) > 1e-9])]
        for k in range(0, len(zh)-1, 2):
            occ[i, j, (zs_ >= zh[k]) & (zs_ <= zh[k+1])] = True
print(f"voxelize {occ.shape} {time.perf_counter()-t0:.1f}s solid={occ.mean()*100:.1f}%")

void = ~occ
lab, nl = ndimage.label(void)
edge = np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:,0].ravel(),
                                 lab[:,-1].ravel(), lab[:,:,0].ravel(), lab[:,:,-1].ravel()]))
trapped = void & ~np.isin(lab, edge)
cavity_void_expected = L**3 - lat.volume()
print(f"trapped voxels={trapped.sum()} -> {trapped.sum()*pitch**3:.0f} mm3 "
      f"(expected enclosed void ~{cavity_void_expected:.0f} mm3)")

# escape-channel variant: drill a 2 mm hole through the shell
hole = manifold3d.Manifold.cylinder(shell_t*4, 1.0, 1.0, 24).translate([L/2, L/2, L - shell_t])
solid2 = solid - hole
mgl2 = solid2.to_mesh()
V2 = np.asarray(mgl2.vert_properties[:, :3], np.float64)
F2 = np.asarray(mgl2.tri_verts, np.int64)
pvm2 = pv.PolyData(V2, np.column_stack([np.full(len(F2), 3), F2]).ravel())
occ2 = np.zeros_like(occ)
for i, x in enumerate(xs_):
    for j, y in enumerate(ys_):
        xp, _ = pvm2.ray_trace([x, y, lo[2]-1], [x, y, hi[2]+1])
        if len(xp) < 2: continue
        zh = np.sort(xp[:, 2]); zh = zh[np.concatenate([[True], np.diff(zh) > 1e-9])]
        for k in range(0, len(zh)-1, 2):
            occ2[i, j, (zs_ >= zh[k]) & (zs_ <= zh[k+1])] = True
void2 = ~occ2
lab2, _ = ndimage.label(void2)
edge2 = np.unique(np.concatenate([lab2[0].ravel(), lab2[-1].ravel(), lab2[:,0].ravel(),
                                  lab2[:,-1].ravel(), lab2[:,:,0].ravel(), lab2[:,:,-1].ravel()]))
trapped2 = void2 & ~np.isin(lab2, edge2)
print(f"with 2mm vent hole: trapped={trapped2.sum()*pitch**3:.0f} mm3 (expect ~0, void now connected)")

# ---- 2. STL round-trip ----
lat3, _, _ = build("BCC", 4, 0.5, 32, 3)
mgl3 = lat3.to_mesh()
V3 = np.asarray(mgl3.vert_properties[:, :3], np.float64)
F3 = np.asarray(mgl3.tri_verts, np.int64)
m3 = trimesh.Trimesh(vertices=V3, faces=F3, process=False)
p = os.path.join(os.path.dirname(__file__), "_rt.stl")
m3.export(p)
t0 = time.perf_counter()
rt = trimesh.load(p)          # default process=True merges duplicate vertices
t_load = time.perf_counter()-t0
print(f"\nSTL round-trip: load+process {t_load*1000:.0f}ms, tris={len(rt.faces)}, "
      f"is_watertight={rt.is_watertight}")
raw = manifold3d.Mesh(np.ascontiguousarray(rt.vertices, np.float32),
                      np.ascontiguousarray(rt.faces, np.uint32))
changed = raw.merge()
print(f"manifold3d after STL: merge_changed={changed}, status={manifold3d.Manifold(raw).status()}")
# also raw STL soup direct (no trimesh processing)
soup = trimesh.load(p, process=False)
raw2 = manifold3d.Mesh(np.ascontiguousarray(soup.vertices, np.float32),
                       np.ascontiguousarray(soup.faces, np.uint32))
ch2 = raw2.merge()
print(f"unprocessed soup: verts={len(soup.vertices)}, merge_changed={ch2}, "
      f"status={manifold3d.Manifold(raw2).status()}, trimesh_watertight={soup.is_watertight}")
os.remove(p)
