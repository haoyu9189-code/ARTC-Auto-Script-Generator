"""ATLAS 几何核心:24 拓扑单胞的程序化 watertight 网格生成(A1)。

根因记录(2026-06-10,Cuboctahedron_Z watertight 失败,两个叠加退化):
1. 球-柱等半径整圆相切:SPHERE_RADIUS_RATIO_SCRIPT=1.0 时节点球与杆柱
   半径严格相等,球面与柱面沿整条圆周退化相切(x²+y²=r² ∩ x²+y²+z²=R²,
   R=r ⟹ z=0 整圆)。离散采样在该圆上产生"位置重合、拓扑不同"的顶点,
   顶点焊接后成非流形边。修复:网格实现层对节点球施加 +0.1% 半径扰动
   (TANGENCY_EPS,r=0.5mm 时 0.5µm,远低于打印公差),整圆相切变两条
   横截交线;仅影响预览/打印/检查网格,不触碰仿真模板与 config 锁定值。
2. 布尔三角化退化 sliver:对称几何(45° 杆系)中两根斜杆的交线精确穿过
   相邻杆的离散母线时,manifold3d 输出含顶点全同的零面积三角形对
   (法向 [0,0,0]),按索引流形合法,焊接后该母线边被 4 面共享。
   修复:welded 形态统一做去零面积面 + 去重复面清理(不改变几何)。
两个退化都是采样相位敏感(segments=23 侥幸通过,24/32 失败);
Cuboctahedron_Z 因 F1/F2 悬挑节点暴露相切圆 + 面菱形 45° 杆系而必然触发。

水密判据从此双轨,二者必须同时成立:
1. raw   — manifold3d 索引网格边-面计数水密(流形性)
2. welded — trimesh 默认顶点焊接后仍水密(STL/打印现实判据)
"""
import numpy as np
import manifold3d
from manifold3d import Manifold, OpType
import trimesh

from structure_set import get_crystal_structure
from config import Config

# 球-柱整圆相切退化的对称破缺扰动(相对半径)
TANGENCY_EPS = 1e-3
# structure_set 内坐标硬编码的单胞边长(±2.5)
_NATIVE_CELL_SIZE = 5.0


def list_topologies():
    """全部 24 个拓扑名,顺序与 Config.CELL_TYPE_GROUPS 一致。"""
    out = []
    for _group, types in Config.CELL_TYPE_GROUPS:
        out.extend(types)
    return out


def parse_structure(topology, slider=4):
    """把 get_crystal_structure 的文本输出解析为 (coords, cylinders)。

    coords: {节点名: np.ndarray(3)};cylinders: [(节点名a, 节点名b), ...]
    """
    output = get_crystal_structure(topology, slider)
    coords, cylinders = {}, []
    in_cyl = False
    for line in output.split('\n'):
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
            name, expr = line.split('=', 1)
            vec = eval(expr.strip(), {"__builtins__": {}}, {})
            coords[name.strip()] = np.array(vec, dtype=float)
        elif in_cyl:
            cyl_line = line.rstrip(',').strip()
            if cyl_line:
                a, b = [s.strip() for s in cyl_line.strip('()').split(',')]
                cylinders.append((a, b))
    return coords, cylinders


def _strut_manifold(p0, p1, r, segments):
    """两点之间的圆柱 Manifold;退化(零长)返回 None。"""
    d = p1 - p0
    length = float(np.linalg.norm(d))
    if length < 1e-6:
        return None
    d_unit = d / length
    cyl = Manifold.cylinder(length, float(r), float(r), segments)
    z = np.array([0.0, 0.0, 1.0])
    cross_v = np.cross(z, d_unit)
    dot_v = float(np.dot(z, d_unit))
    if np.linalg.norm(cross_v) < 1e-8:
        rot = np.eye(3) if dot_v > 0 else np.diag([1.0, -1.0, -1.0])
    else:
        cn = cross_v / np.linalg.norm(cross_v)
        angle = np.arccos(np.clip(dot_v, -1, 1))
        K = np.array([[0, -cn[2], cn[1]],
                      [cn[2], 0, -cn[0]],
                      [-cn[1], cn[0], 0]])
        rot = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K
    mat = [[rot[0][0], rot[0][1], rot[0][2], float(p0[0])],
           [rot[1][0], rot[1][1], rot[1][2], float(p0[1])],
           [rot[2][0], rot[2][1], rot[2][2], float(p0[2])]]
    return cyl.transform(mat)


def _union(parts):
    try:
        return Manifold.batch_boolean(parts, OpType.Add)
    except (AttributeError, TypeError):
        result = parts[0]
        for p in parts[1:]:
            result = result + p
        return result


class CellMesh:
    """generate_cell 的返回值:同时暴露 Manifold 与 Trimesh 两种形态。"""

    def __init__(self, manifold, topology, slider, radius, n, cell_size):
        self.manifold = manifold
        self.topology = topology
        self.slider = slider
        self.radius = radius
        self.n = n
        self.cell_size = cell_size
        self._tri = None
        self._tri_raw = None

    def _verts_faces(self):
        out = self.manifold.to_mesh()
        verts = np.asarray(out.vert_properties)[:, :3]
        faces = np.asarray(out.tri_verts)
        return verts, faces

    @property
    def trimesh(self):
        """焊接后的 Trimesh(process=True,STL/打印现实形态)。

        焊接后只做一种清理:删除"成对的重复面"(顶点集合相同的面对,
        即零厚度翻盖)。manifold3d 布尔三角化在对称几何的精确重合切线上
        会产生顶点全同的零面积 sliver 对(实测 Cuboctahedron_Z:斜杆交线
        精确穿过相邻杆离散母线),按索引流形合法,焊接后表现为 4 面共享边;
        成对删除恢复边奇偶性。注意不能删除全部零面积面——非重复的退化
        sliver 可能承担连通性(实测 Auxetic),删之开洞。清理不改变几何。"""
        if self._tri is None:
            verts, faces = self._verts_faces()
            m = trimesh.Trimesh(vertices=verts, faces=faces)
            sorted_f = np.sort(m.faces, axis=1)
            _, inv, cnt = np.unique(sorted_f, axis=0,
                                    return_inverse=True, return_counts=True)
            if (cnt > 1).any():
                keep = np.ones(len(m.faces), dtype=bool)
                groups = {}
                for i, g in enumerate(inv):
                    groups.setdefault(int(g), []).append(i)
                for idxs in groups.values():
                    if len(idxs) > 1:
                        # 偶数组全删(互相抵消的翻盖);奇数组留一份
                        drop = idxs if len(idxs) % 2 == 0 else idxs[1:]
                        keep[drop] = False
                m.update_faces(keep)
                m.remove_unreferenced_vertices()
            self._tri = m
        return self._tri

    @property
    def trimesh_raw(self):
        """按 manifold3d 原始索引的 Trimesh(process=False)。"""
        if self._tri_raw is None:
            verts, faces = self._verts_faces()
            self._tri_raw = trimesh.Trimesh(vertices=verts, faces=faces,
                                            process=False)
        return self._tri_raw

    @property
    def is_watertight(self):
        """双轨判据:流形性(raw)与焊接后(welded)同时水密。"""
        return (self.manifold.status() == manifold3d.Error.NoError
                and self.trimesh_raw.is_watertight
                and self.trimesh.is_watertight)

    @property
    def volume(self):
        return float(self.trimesh.volume)


def generate_cell(topology, slider=4, radius=0.5, n=1, cell_size=5.0,
                  segments=24, sphere_ratio=None, return_type='cellmesh'):
    """生成 n×n×n 拓扑阵列的 watertight 网格。

    参数:
        topology:     24 拓扑名之一(见 list_topologies())
        slider:       拓扑变形参数 0–8
        radius:       杆半径 (mm)
        n:            阵列尺寸(1 = 单胞)
        cell_size:    单胞边长 (mm),structure_set 原生 5.0
        segments:     圆柱/球离散段数
        sphere_ratio: 节点球半径/杆半径;None 取 Config.SPHERE_RADIUS_RATIO_SCRIPT。
                      与 1.0 过近时自动施加 +TANGENCY_EPS 破缺整圆相切退化。
        return_type:  'cellmesh' | 'manifold' | 'trimesh'
    """
    if topology not in list_topologies():
        raise ValueError(f"unknown topology: {topology!r}; "
                         f"valid: {list_topologies()}")
    if n < 1 or int(n) != n:
        raise ValueError(f"n must be a positive integer, got {n!r}")

    ratio = (Config.SPHERE_RADIUS_RATIO_SCRIPT if sphere_ratio is None
             else float(sphere_ratio))
    sphere_r = radius * ratio
    if abs(sphere_r - radius) < radius * 10 * np.finfo(float).eps + 1e-12 \
            or abs(ratio - 1.0) < TANGENCY_EPS:
        sphere_r = radius * (1.0 + TANGENCY_EPS)

    coords, cylinders = parse_structure(topology, slider)
    scale = cell_size / _NATIVE_CELL_SIZE
    coords = {k: v * scale for k, v in coords.items()}

    parts = []
    for a, b in cylinders:
        if a not in coords or b not in coords:
            continue
        s = _strut_manifold(coords[a], coords[b], radius, segments)
        if s is not None:
            parts.append(s)
    for pt in coords.values():
        sph = Manifold.sphere(float(sphere_r), segments)
        parts.append(sph.translate([float(pt[0]), float(pt[1]), float(pt[2])]))
    if not parts:
        raise ValueError(f"topology {topology!r} (slider={slider}) "
                         f"produced no geometry")
    unit = _union(parts)

    if n > 1:
        tiles = []
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    tiles.append(unit.translate([i * cell_size,
                                                 j * cell_size,
                                                 k * cell_size]))
        result = _union(tiles)
        # 居中回原点
        shift = -cell_size * (n - 1) / 2.0
        result = result.translate([shift, shift, shift])
    else:
        result = unit

    cm = CellMesh(result, topology, slider, radius, n, cell_size)
    if return_type == 'cellmesh':
        return cm
    if return_type == 'manifold':
        return cm.manifold
    if return_type == 'trimesh':
        return cm.trimesh
    raise ValueError(f"return_type must be 'cellmesh' | 'manifold' | "
                     f"'trimesh', got {return_type!r}")
