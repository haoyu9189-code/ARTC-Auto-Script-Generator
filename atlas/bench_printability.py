"""ATLAS Printability Checker - local feasibility/performance benchmark.

Builds an N x N x N BCC lattice with manifold3d (same pipeline as
test_manifold_all_cells.py), then times every candidate printability check
using ONLY the packages already installed in this env:
  trimesh 4.11.5, manifold3d 3.4.1, pyvista 0.46.4 (VTK 9.5.2), scipy 1.16.1
(no embreex, no rtree, no open3d -> exercises the fallback paths)
"""
import sys, os, time
import numpy as np

sys.path.insert(0, r"D:\ARTC\ARTC-Auto-Script")
import manifold3d
import trimesh
import pyvista as pv
from scipy import ndimage
from structure_set import get_crystal_structure
from config import Config

T = {}
def tic(): return time.perf_counter()
def toc(t0, key): T[key] = time.perf_counter() - t0; print(f"  [{key}] {T[key]*1000:.1f} ms")

# ---------------- build lattice ----------------
cell_type, slider, radius, cell_size, seg, N = "BCC", 4, 0.5, 5.0, 24, 3
sphere_radius = radius * Config.SPHERE_RADIUS_RATIO_SCRIPT

def parse(cell_type, slider):
    out = get_crystal_structure(cell_type, slider)
    coords, cyls, in_c = {}, [], False
    for line in out.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "cylinders = [" in line: in_c = True; continue
        if in_c and line == "]": in_c = False; continue
        if "=" in line and not in_c and "cylinders" not in line:
            k, v = line.split("=", 1); coords[k.strip()] = np.array(eval(v.strip()), float)
        elif in_c:
            s = line.rstrip(",").strip()
            if s:
                a, b = [x.strip() for x in s.strip("()").split(",")]
                cyls.append((a, b))
    return coords, cyls

def strut(p0, p1, r, seg):
    d = p1 - p0; L = float(np.linalg.norm(d))
    if L < 1e-6: return None
    du = d / L
    cyl = manifold3d.Manifold.cylinder(L, r, r, seg)
    z = np.array([0.0, 0.0, 1.0]); cv = np.cross(z, du); dv = float(np.dot(z, du))
    if np.linalg.norm(cv) < 1e-8:
        rot = np.eye(3) if dv > 0 else np.diag([1.0, -1.0, -1.0])
    else:
        cn = cv / np.linalg.norm(cv); ang = np.arccos(np.clip(dv, -1, 1))
        K = np.array([[0,-cn[2],cn[1]],[cn[2],0,-cn[0]],[-cn[1],cn[0],0]])
        rot = np.eye(3) + np.sin(ang)*K + (1-np.cos(ang))*K@K
    mat = np.zeros((3,4)); mat[:,:3] = rot; mat[:,3] = p0
    return cyl.transform(mat.tolist())

coords, cyls = parse(cell_type, slider)
t0 = tic()
parts = []
for a, b in cyls:
    s = strut(coords[a], coords[b], radius, seg)
    if s is not None: parts.append(s)
for _, pt in coords.items():
    parts.append(manifold3d.Manifold.sphere(sphere_radius, seg).translate(pt.tolist()))
cell = manifold3d.Manifold.batch_boolean(parts, manifold3d.OpType.Add)
toc(t0, "cell_union_batch_boolean")

t0 = tic()
span = float(np.ptp([p for p in coords.values()], axis=0).max())  # cell extent
tiles = [cell.translate([i*span, j*span, k*span])
         for i in range(N) for j in range(N) for k in range(N)]
lat = manifold3d.Manifold.batch_boolean(tiles, manifold3d.OpType.Add)
toc(t0, f"lattice_{N}x{N}x{N}_union")
print(f"  lattice tris={lat.num_tri()}, verts={lat.num_vert()}, genus={lat.genus()}, "
      f"vol={lat.volume():.2f}, area={lat.surface_area():.2f}, status={lat.status()}")
bbox_vol = (span*N)**3 if span > 0 else 1.0
print(f"  relative density (vol/cell_bbox) = {lat.volume()/((span*N)**3):.4f}")

mgl = lat.to_mesh()
V = np.asarray(mgl.vert_properties[:, :3], dtype=np.float64)
F = np.asarray(mgl.tri_verts, dtype=np.int64)

# ---------------- (a) watertight / manifold validation ----------------
print("\n(a) validation")
t0 = tic(); mesh = trimesh.Trimesh(vertices=V, faces=F, process=False); toc(t0, "trimesh_construct_noprocess")
t0 = tic(); wt = mesh.is_watertight; toc(t0, "trimesh_is_watertight")
t0 = tic(); wc = mesh.is_winding_consistent; toc(t0, "trimesh_is_winding_consistent")
t0 = tic(); iv = mesh.is_volume; toc(t0, "trimesh_is_volume")
t0 = tic(); eu = mesh.euler_number; toc(t0, "trimesh_euler_number")
t0 = tic(); nb = mesh.body_count; toc(t0, "trimesh_body_count")
print(f"  watertight={wt} winding={wc} volume_ok={iv} euler={eu} bodies={nb}")

# manifold3d as validator: round-trip a raw mesh (merge vectors lost, like STL)
t0 = tic()
raw = manifold3d.Mesh(np.ascontiguousarray(V, dtype=np.float32), np.ascontiguousarray(F, dtype=np.uint32))
changed = raw.merge()
m2 = manifold3d.Manifold(raw)
toc(t0, "manifold3d_merge_plus_construct")
print(f"  Mesh.merge() changed={changed}, Manifold.status={m2.status()}")

# broken mesh: drop one face -> expect NotManifold
broken = manifold3d.Mesh(np.ascontiguousarray(V, dtype=np.float32),
                         np.ascontiguousarray(F[:-1], dtype=np.uint32))
broken.merge()
mb = manifold3d.Manifold(broken)
mt = trimesh.Trimesh(vertices=V, faces=F[:-1], process=False)
print(f"  broken: manifold3d.status={mb.status()}, trimesh.is_watertight={mt.is_watertight}")

# ---------------- (c) overhang from face normals ----------------
print("\n(c) overhang")
t0 = tic()
fn = mesh.face_normals                       # (m,3), build dir +Z
down = fn[:, 2] < 0                          # downward-facing only
theta = np.degrees(np.arccos(np.clip(-fn[down, 2], -1, 1)))  # angle from -Z
# convention: angle from horizontal plate = 90 - theta_from_down... report vs threshold
# overhang angle alpha measured from horizontal: alpha = 90 - angle(normal, -Z)
alpha = 90.0 - theta
area = mesh.area_faces[down]
crit = alpha < 45.0                          # self-support threshold (LPBF)
frac = float(area[crit].sum() / mesh.area)
toc(t0, "overhang_face_normal_classify")
print(f"  downward faces={down.sum()}/{len(fn)}, overhang(<45deg from plate) area frac={frac:.3f}")

# ---------------- (b) thickness ----------------
print("\n(b) thickness")
pts, fidx = trimesh.sample.sample_surface(mesh, 200)
nrm = mesh.face_normals[fidx]
try:
    t0 = tic()
    th = trimesh.proximity.thickness(mesh, pts, normals=nrm, method="ray")
    toc(t0, "trimesh_thickness_ray_200pts")
    print(f"  ray thickness min/med={np.min(th):.3f}/{np.median(th):.3f} (true strut d=1.0)")
except BaseException as e:
    print(f"  trimesh ray thickness FAILED: {type(e).__name__}: {e}")
try:
    t0 = tic()
    th2 = trimesh.proximity.thickness(mesh, pts[:50], normals=nrm[:50], method="max_sphere")
    toc(t0, "trimesh_thickness_maxsphere_50pts")
    print(f"  max_sphere thickness min/med={np.min(th2):.3f}/{np.median(th2):.3f}")
except BaseException as e:
    print(f"  trimesh max_sphere FAILED: {type(e).__name__}: {e}")

# VTK OBBTree single-ray fallback (no rtree/embree needed)
try:
    pvm = pv.PolyData(V, np.column_stack([np.full(len(F), 3), F]).ravel())
    t0 = tic()
    hits = []
    for p, n in zip(pts[:200], nrm[:200]):
        o = p - n * 1e-4
        end = p - n * (2 * span)
        xs, _ = pvm.ray_trace(o, end, first_point=True)
        if len(xs): hits.append(np.linalg.norm(xs - o))
    toc(t0, "vtk_obbtree_ray_thickness_200pts")
    hits = np.array(hits)
    print(f"  vtk ray thickness n={len(hits)} min/med={hits.min():.3f}/{np.median(hits):.3f}")
except BaseException as e:
    print(f"  vtk ray FAILED: {type(e).__name__}: {e}")

# ---------------- voxel SDF / EDT route: (b) strut d, (d) trapped powder, (e) gap ----
print("\n(b/d/e) voxel EDT route")
pitch = 0.125
t0 = tic()
xs = np.arange(mesh.bounds[0][0]-2*pitch, mesh.bounds[1][0]+2*pitch, pitch)
ys = np.arange(mesh.bounds[0][1]-2*pitch, mesh.bounds[1][1]+2*pitch, pitch)
zs = np.arange(mesh.bounds[0][2]-2*pitch, mesh.bounds[1][2]+2*pitch, pitch)
gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
grid = pv.StructuredGrid(gx, gy, gz)
sel = grid.select_enclosed_points(pvm.extract_surface(), tolerance=0.0, check_surface=False)
occ = sel["SelectedPoints"].reshape(gx.shape).astype(bool)
toc(t0, f"vtk_select_enclosed_{occ.shape}={occ.size}pts")
print(f"  grid={occ.shape}, solid voxels={occ.sum()} ({occ.mean()*100:.1f}%)")

t0 = tic()
edt_solid = ndimage.distance_transform_edt(occ, sampling=pitch)
toc(t0, "edt_solid")
print(f"  max inscribed radius in solid={edt_solid.max():.3f} -> approx max strut d={2*edt_solid.max():.3f}")

t0 = tic()
void = ~occ
lab, nlab = ndimage.label(void)
edge_labels = np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(),
    lab[:,0].ravel(), lab[:,-1].ravel(), lab[:,:,0].ravel(), lab[:,:,-1].ravel()]))
trapped_mask = void & ~np.isin(lab, edge_labels)
toc(t0, "void_label_floodfill")
print(f"  void components={nlab}, trapped voxels={trapped_mask.sum()} "
      f"({trapped_mask.sum()*pitch**3:.2f} mm3 trapped)")

t0 = tic()
edt_void = ndimage.distance_transform_edt(void, sampling=pitch)
toc(t0, "edt_void")
# largest sphere that passes anywhere in the open void = powder escape proxy
print(f"  max void inscribed radius={edt_void.max():.3f} (gap proxy: min channel half-width)")

# ---------------- (e) min_gap between separate bodies ----------------
print("\n(e) manifold3d.min_gap")
m_a = cell
m_b = cell.translate([span + 0.8, 0, 0])   # 0.8 mm clearance
t0 = tic(); g = m_a.min_gap(m_b, 5.0); toc(t0, "manifold3d_min_gap")
print(f"  min_gap = {g:.4f} (expected ~0.8)")

# ---------------- proximity (rtree-dependent) ----------------
print("\nProximityQuery (expect rtree dependency on this env)")
try:
    q = trimesh.proximity.ProximityQuery(mesh)
    rnd = np.random.default_rng(0).uniform(mesh.bounds[0], mesh.bounds[1], (2000, 3))
    t0 = tic(); sd = q.signed_distance(rnd); toc(t0, "signed_distance_2000pts")
    print(f"  signed distance ok, inside frac={np.mean(sd>0):.3f}")
except BaseException as e:
    print(f"  ProximityQuery FAILED: {type(e).__name__}: {e}")

print("\nTIMINGS_SUMMARY")
for k, v in T.items(): print(f"  {k}: {v*1000:.1f} ms")
