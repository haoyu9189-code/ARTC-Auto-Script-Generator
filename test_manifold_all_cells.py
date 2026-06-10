"""验证所有 24 种 cell type 的 manifold3d 水密 union(A1 起经 atlas.geometry.generate_cell)

水密双轨判据(均须通过):
1. raw    — manifold3d 索引网格按边-面计数水密(流形性)
2. welded — trimesh 顶点焊接 + 成对重复面清理后仍水密(STL/打印现实判据)

按 ATLAS A1 DoD 连续运行两遍,要求结果完全一致(确定性)。
根因与修复记录见 atlas/geometry/cells.py 模块注释。
"""
import time
from atlas.geometry import generate_cell, list_topologies


def run_once():
    rows = []
    all_ok = True
    for ct in list_topologies():
        try:
            t0 = time.time()
            cm = generate_cell(ct, slider=4, radius=0.5, segments=24)
            raw_wt = cm.trimesh_raw.is_watertight
            welded_wt = cm.trimesh.is_watertight
            dt = time.time() - t0
            vol = cm.volume
            ok = raw_wt and welded_wt and vol > 0
            all_ok &= ok
            rows.append((ct, len(cm.trimesh.vertices), len(cm.trimesh.faces),
                         raw_wt, welded_wt, vol, dt, 'OK' if ok else 'FAIL'))
        except Exception as e:
            all_ok = False
            rows.append((ct, 0, 0, False, False, 0.0, 0.0, f'FAIL: {e}'))
    return all_ok, rows


def main():
    print(f"{'Cell Type':<25} {'Verts':>7} {'Faces':>7} {'Raw':>5} "
          f"{'Weld':>5} {'Vol':>8} {'Time':>6} {'Status'}")
    print("-" * 80)
    ok1, rows1 = run_once()
    for r in rows1:
        print(f"{r[0]:<25} {r[1]:>7} {r[2]:>7} {str(r[3]):>5} "
              f"{str(r[4]):>5} {r[5]:>8.2f} {r[6]:>5.2f}s {r[7]}")
    print("-" * 80)

    ok2, rows2 = run_once()
    deterministic = all(
        a[0] == b[0] and a[1] == b[1] and a[2] == b[2]
        and abs(a[5] - b[5]) < 1e-9 and a[7] == b[7]
        for a, b in zip(rows1, rows2))

    n = len(list_topologies())
    print(f"\nRun 1: {'ALL PASS' if ok1 else 'SOME FAILED'} ({n} cell types)")
    print(f"Run 2: {'ALL PASS' if ok2 else 'SOME FAILED'} "
          f"(deterministic: {deterministic})")
    if ok1 and ok2 and deterministic:
        print("RESULT: 24/24 watertight x2 runs, deterministic — A1 DoD met")
        return 0
    print("RESULT: FAILED")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
