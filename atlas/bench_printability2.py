"""ATLAS Printability bench 2: scale to 100k-1M tris; fix min_gap; column-parity voxelization."""
import sys, time
import numpy as np
sys.path.insert(0, r"D:\ARTC\ARTC-Auto-Script")
import manifold3d, trimesh, pyvista as pv
from scipy import ndimage
from structure_set import get_crystal_structure

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

def build(cell_type, slider, radius, seg, N, sphere_ratio=1.0):
    coords, cyls = parse(cell_type, slider)
    parts = []
    for a, b in cyls:
        s = strut(coords[a], coords[b], radius, seg)
        if s is not None: parts.append(s)
    for _, pt in coords.items():
        parts.append(manifold3d.Manifold.sphere(radius*sphere_ratio, seg).translate(pt.tolist()))
    cell = manifold3d.Manifold.batch_boolean(parts, manifold3d.OpType.Add)
    span = float(np.ptp([p for p in coords.values()], axis=0).max())
    tiles = [cell.translate([i*span, j*span, k*span]) for i in range(N) for j in range(N) for k in range(N)]
    return manifold3d.Manifold.batch_boolean(tiles, manifold3d.OpType.Add), span, cell

if __name__ == "__main__":
    print("=== min_gap fix (single cells, true 0.8 mm clearance) ===")
    _, span1, cell1 = build("BCC", 4, 0.5, 24, 1)
    other = cell1.translate([span1 + 2*0.5 + 0.8, 0, 0])
    t0 = time.perf_counter(); g = cell1.min_gap(other, 5.0)
    print(f"min_gap={g:.4f} (expect 0.8), {1000*(time.perf_counter()-t0):.1f} ms")

    for (N, seg, label) in [(4, 32, "~100k"), (5, 64, "~400k"), (6, 96, "~1M")]:
        print(f"\n=== scale {label}: N={N}, seg={seg} ===")
        t0 = time.perf_counter(); lat, span, cell = build("BCC", 4, 0.5, seg, N)
        t_build = time.perf_counter()-t0
        print(f"build+union {t_build:.2f}s tris={lat.num_tri()} status={lat.status()} genus={lat.genus()}")

        mgl = lat.to_mesh()
        V = np.asarray(mgl.vert_properties[:, :3], np.float64)
        F = np.asarray(mgl.tri_verts, np.int64)
        mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)

        t0 = time.perf_counter(); wt = mesh.is_watertight; t_wt = time.perf_counter()-t0
        t0 = time.perf_counter()
        raw = manifold3d.Mesh(np.ascontiguousarray(V, np.float32), np.ascontiguousarray(F, np.uint32))
        raw.merge(); st = manifold3d.Manifold(raw).status()
        t_m3 = time.perf_counter()-t0
        print(f"is_watertight={wt} {t_wt*1000:.0f}ms | manifold3d status={st} {t_m3*1000:.0f}ms")

        t0 = time.perf_counter()
        fn = mesh.face_normals; down = fn[:, 2] < 0
        alpha = 90.0 - np.degrees(np.arccos(np.clip(-fn[down, 2], -1, 1)))
        frac = float(mesh.area_faces[down][alpha < 45.0].sum()/mesh.area)
        print(f"overhang frac={frac:.3f} {1000*(time.perf_counter()-t0):.0f}ms")

        pvm = pv.PolyData(V, np.column_stack([np.full(len(F), 3), F]).ravel())
        pts, fidx = trimesh.sample.sample_surface(mesh, 1000)
        nrm = mesh.face_normals[fidx]
        t0 = time.perf_counter(); hits = []
        for p, n in zip(pts, nrm):
            o = p - n*1e-4
            xs, _ = pvm.ray_trace(o, p - n*(2*span), first_point=True)
            if len(xs): hits.append(np.linalg.norm(xs - o))
        t_ray = time.perf_counter()-t0
        hits = np.array(hits)
        print(f"vtk ray thickness 1000pts {t_ray:.2f}s min={hits.min():.3f} p05={np.percentile(hits,5):.3f} med={np.median(hits):.3f}")

        if N <= 5:
            pitch = 0.2
            t0 = time.perf_counter()
            lo = mesh.bounds[0]-2*pitch; hi = mesh.bounds[1]+2*pitch
            xs_ = np.arange(lo[0], hi[0], pitch); ys_ = np.arange(lo[1], hi[1], pitch); zs_ = np.arange(lo[2], hi[2], pitch)
            occ = np.zeros((len(xs_), len(ys_), len(zs_)), bool)
            z0, z1 = lo[2]-1.0, hi[2]+1.0
            for i, x in enumerate(xs_):
                for j, y in enumerate(ys_):
                    xpts, _ = pvm.ray_trace([x, y, z0], [x, y, z1])
                    if len(xpts) < 2: continue
                    zh = np.sort(xpts[:, 2])
                    zh = zh[np.concatenate([[True], np.diff(zh) > 1e-9])]
                    for k in range(0, len(zh)-1, 2):
                        occ[i, j, (zs_ >= zh[k]) & (zs_ <= zh[k+1])] = True
            t_vox = time.perf_counter()-t0
            print(f"column-parity voxelize {occ.shape} {t_vox:.2f}s solid={occ.mean()*100:.1f}%")
            t0 = time.perf_counter()
            edt_s = ndimage.distance_transform_edt(occ, sampling=pitch)
            void = ~occ; labv, nl = ndimage.label(void)
            edge = np.unique(np.concatenate([labv[0].ravel(), labv[-1].ravel(), labv[:,0].ravel(),
                                             labv[:,-1].ravel(), labv[:,:,0].ravel(), labv[:,:,-1].ravel()]))
            trapped = void & ~np.isin(labv, edge)
            edt_v = ndimage.distance_transform_edt(void, sampling=pitch)
            t_edt = time.perf_counter()-t0
            print(f"EDT+floodfill {t_edt:.2f}s maxR_solid={edt_s.max():.3f} trapped_mm3={trapped.sum()*pitch**3:.2f} maxR_void={edt_v.max():.3f}")
