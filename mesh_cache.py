#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesh缓存系统 - 将所有mesh预计算并保存到磁盘文件

功能:
1. 生成所有1,080个mesh组合并保存到压缩文件
2. 快速加载缓存，避免重复计算
3. 支持分层加载（快速缓存 + 完整缓存）

文件结构:
- mesh_cache_quick.pkl.gz: 24个结构的默认配置 (~1MB)
- mesh_cache_full.pkl.gz: 所有1,080个组合 (~12MB)

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import pickle
import gzip
import numpy as np
from pathlib import Path
import time


class MeshCacheBuilder:
    """Mesh缓存生成器"""

    def __init__(self, cache_dir="work"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.quick_cache_file = self.cache_dir / "mesh_cache_quick.pkl.gz"
        self.full_cache_file = self.cache_dir / "mesh_cache_full.pkl.gz"

        # 所有结构类型
        self.cell_types = [
            "Cubic", "BCC", "BCCZ", "Octet_truss", "AFCC",
            "Truncated_cube", "FCC", "FCCZ", "Tetrahedron_base",
            "Iso_truss", "G7", "FBCCZ", "FBCCXYZ", "Cuboctahedron_Z",
            "Diamond", "Rhombic", "Kelvin", "Auxetic",
            "Octahedron", "Truncated_Octoctahedron", "CubicRosette", "CBCC",
            "WeairePhelan", "DiamondPlus"
        ]

        # Slider和radius值
        self.slider_values = list(range(9))  # 0-8
        self.radius_values = [0.5, 0.45, 0.4, 0.35, 0.3]

    def serialize_mesh(self, mesh):
        """将PyVista mesh序列化为字典（用于pickle存储）"""
        if mesh is None or mesh.n_points == 0:
            return None

        # 兼容新旧版本PyVista
        try:
            n_faces = mesh.n_cells  # 新版本使用 n_cells
        except AttributeError:
            n_faces = mesh.n_faces  # 旧版本使用 n_faces

        return {
            'points': mesh.points.copy(),  # 顶点坐标 (N×3)
            'faces': mesh.faces.copy(),    # 面片索引
            'n_points': mesh.n_points,
            'n_faces': n_faces
        }

    def generate_quick_cache(self, progress_callback=None):
        """
        生成快速缓存: 24个结构 × 固定slider=4 × 固定radius=0.3

        Args:
            progress_callback: 进度回调函数 callback(current, total, message)

        Returns:
            成功生成的mesh数量
        """
        print("=" * 80)
        print("生成快速缓存 (Quick Cache)")
        print("=" * 80)

        cache = {}
        total = len(self.cell_types)
        start_time = time.time()

        for i, cell_type in enumerate(self.cell_types):
            key = f"{cell_type}_4_0.3"

            if progress_callback:
                progress_callback(i, total, f"生成 {cell_type}...")

            try:
                mesh = self._generate_single_mesh(cell_type, slider=4, radius=0.3)
                serialized = self.serialize_mesh(mesh)

                if serialized:
                    cache[key] = serialized
                    print(f"  [{i+1}/{total}] OK {cell_type}")
                else:
                    print(f"  [{i+1}/{total}] SKIP {cell_type} (empty mesh)")

            except Exception as e:
                print(f"  [{i+1}/{total}] ERROR {cell_type} - Error: {e}")

        # 保存到文件
        with gzip.open(self.quick_cache_file, 'wb') as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)

        elapsed = time.time() - start_time
        file_size = self.quick_cache_file.stat().st_size / 1024 / 1024

        print("-" * 80)
        print(f"[OK] 快速缓存已保存: {self.quick_cache_file}")
        print(f"  - 文件大小: {file_size:.2f} MB")
        print(f"  - Mesh数量: {len(cache)}")
        print(f"  - 生成时间: {elapsed:.1f}秒")
        print("=" * 80)

        if progress_callback:
            progress_callback(total, total, "快速缓存生成完成!")

        return len(cache)

    def generate_full_cache(self, progress_callback=None):
        """
        生成完整缓存: 24结构 × 9 sliders × 5 radius = 1,080个组合

        Args:
            progress_callback: 进度回调函数 callback(current, total, message)

        Returns:
            成功生成的mesh数量
        """
        print("\n" + "=" * 80)
        print("生成完整缓存 (Full Cache)")
        print("=" * 80)

        cache = {}
        total = len(self.cell_types) * len(self.slider_values) * len(self.radius_values)
        count = 0
        start_time = time.time()

        for cell_type in self.cell_types:
            print(f"\n正在处理: {cell_type}")

            for slider in self.slider_values:
                for radius in self.radius_values:
                    key = f"{cell_type}_{slider}_{radius}"

                    if progress_callback:
                        progress_callback(count, total,
                                         f"{cell_type} (slider={slider}, r={radius})")

                    try:
                        mesh = self._generate_single_mesh(cell_type, slider, radius)
                        serialized = self.serialize_mesh(mesh)

                        if serialized:
                            cache[key] = serialized
                        else:
                            print(f"  SKIP {key} (empty mesh)")

                    except Exception as e:
                        print(f"  ERROR {key} - Error: {e}")

                    count += 1

                    # 每完成一个结构的所有组合，显示进度
                    if count % 45 == 0:  # 9 sliders × 5 radius = 45
                        print(f"  进度: {count}/{total} ({count*100/total:.1f}%)")

        # 保存到文件
        print("\n正在保存缓存文件...")
        with gzip.open(self.full_cache_file, 'wb') as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)

        elapsed = time.time() - start_time
        file_size = self.full_cache_file.stat().st_size / 1024 / 1024

        print("-" * 80)
        print(f"[OK] 完整缓存已保存: {self.full_cache_file}")
        print(f"  - 文件大小: {file_size:.2f} MB")
        print(f"  - Mesh数量: {len(cache)}/{total}")
        print(f"  - 生成时间: {elapsed:.1f}秒")
        print("=" * 80)

        if progress_callback:
            progress_callback(total, total, "完整缓存生成完成!")

        return len(cache)

    def _generate_single_mesh(self, cell_type, slider, radius, resolution=12, cell_size=5.0, enable_clipping=True):
        """
        生成单个mesh（使用与visualization_widget相同的逻辑，包括切割）

        Args:
            cell_type: 结构类型
            slider: slider值 (0-8)
            radius: 圆柱半径
            resolution: 圆柱分辨率
            cell_size: 晶胞尺寸（用于切割边界）
            enable_clipping: 是否启用切割

        Returns:
            PyVista PolyData mesh
        """
        try:
            import pyvista as pv
        except ImportError:
            print("错误: 需要安装pyvista")
            return None

        # 导入结构生成函数
        from structure_set import get_crystal_structure
        import re

        # 获取结构数据
        structure_text = get_crystal_structure(cell_type, slider=slider)

        # 解析顶点和连接
        points, connections = self._parse_structure(structure_text)

        if points is None or connections is None:
            return pv.PolyData()  # 返回空mesh

        # 交换Y和Z坐标（与visualization_widget保持一致）
        display_points = points.copy()
        display_points[:, [1, 2]] = display_points[:, [2, 1]]

        # 计算切割边界
        limit = cell_size / 2.0

        # 准备裁剪平面（如果启用）
        planes = None
        if enable_clipping:
            try:
                import vtk
                planes = vtk.vtkPlaneCollection()

                # 定义6个平面，法向量指向外部
                # x = limit, n = (1,0,0)
                p = vtk.vtkPlane(); p.SetOrigin(limit, 0, 0); p.SetNormal(1, 0, 0); planes.AddItem(p)
                # x = -limit, n = (-1,0,0)
                p = vtk.vtkPlane(); p.SetOrigin(-limit, 0, 0); p.SetNormal(-1, 0, 0); planes.AddItem(p)
                # y = limit, n = (0,1,0)
                p = vtk.vtkPlane(); p.SetOrigin(0, limit, 0); p.SetNormal(0, 1, 0); planes.AddItem(p)
                # y = -limit, n = (0,-1,0)
                p = vtk.vtkPlane(); p.SetOrigin(0, -limit, 0); p.SetNormal(0, -1, 0); planes.AddItem(p)
                # z = limit, n = (0,0,1)
                p = vtk.vtkPlane(); p.SetOrigin(0, 0, limit); p.SetNormal(0, 0, 1); planes.AddItem(p)
                # z = -limit, n = (0,0,-1)
                p = vtk.vtkPlane(); p.SetOrigin(0, 0, -limit); p.SetNormal(0, 0, -1); planes.AddItem(p)
            except ImportError:
                print("Warning: VTK not available, falling back to simple clipping")
                planes = None

        # 生成圆柱体（带切割）
        all_cylinders = []

        for connection in connections:
            start_point = display_points[connection[0]]
            end_point = display_points[connection[1]]

            direction = end_point - start_point
            length = np.linalg.norm(direction)

            if length > 1e-6:
                center = (start_point + end_point) / 2
                direction_normalized = direction / length

                cylinder = pv.Cylinder(
                    center=center,
                    direction=direction_normalized,
                    radius=radius,
                    height=length,
                    resolution=resolution
                )

                # 如果启用切割，使用clip_box进行切割
                if enable_clipping and planes:
                    # 快速边界检查
                    bounds = cylinder.bounds
                    (xmin, xmax, ymin, ymax, zmin, zmax) = bounds

                    # 检查是否完全在外部
                    if (xmin > limit or xmax < -limit or
                        ymin > limit or ymax < -limit or
                        zmin > limit or zmax < -limit):
                        continue  # 跳过完全在外部的圆柱

                    # 检查是否完全在内部
                    if (xmin >= -limit and xmax <= limit and
                        ymin >= -limit and ymax <= limit and
                        zmin >= -limit and zmax <= limit):
                        all_cylinders.append(cylinder)  # 不需要切割
                    else:
                        # 需要切割：使用与visualization_widget相同的策略
                        try:
                            # 1. 切割主体（不封口）
                            body = cylinder.clip_box(bounds=(-limit, limit, -limit, limit, -limit, limit), invert=False)
                            body = body.extract_surface()

                            # 2. 生成封口
                            caps = []

                            # 定义6个平面的参数
                            plane_configs = [
                                ((1, 0, 0), (limit, 0, 0), lambda b: b[1] > limit),   # x = limit
                                ((-1, 0, 0), (-limit, 0, 0), lambda b: b[0] < -limit),  # x = -limit
                                ((0, 1, 0), (0, limit, 0), lambda b: b[3] > limit),   # y = limit
                                ((0, -1, 0), (0, -limit, 0), lambda b: b[2] < -limit),  # y = -limit
                                ((0, 0, 1), (0, 0, limit), lambda b: b[5] > limit),   # z = limit
                                ((0, 0, -1), (0, 0, -limit), lambda b: b[4] < -limit),  # z = -limit
                            ]

                            current_bounds = body.bounds

                            for normal, origin, check_func in plane_configs:
                                # 只在圆柱确实穿过平面时才切片
                                if not check_func(current_bounds):
                                    continue

                                # A. 切片原始圆柱获取完整的横截面轮廓
                                cut = cylinder.slice(normal=normal, origin=origin, generate_triangles=True)

                                if cut.n_points > 0:
                                    try:
                                        # B. 填充轮廓形成实心圆盘
                                        disk = cut.delaunay_2d()

                                        # C. 将圆盘裁剪到盒子内
                                        cap = disk.clip_box(bounds=(-limit, limit, -limit, limit, -limit, limit), invert=False)
                                        cap = cap.extract_surface()

                                        if cap.n_points > 0:
                                            caps.append(cap)
                                    except Exception:
                                        pass  # 忽略失败的封口

                            # 3. 合并主体和封口
                            if caps:
                                cylinder = body.merge(caps)
                            else:
                                cylinder = body

                        except Exception as e:
                            # 回退到标准clip（不封口）
                            cylinder = cylinder.clip_box(bounds=(-limit, limit, -limit, limit, -limit, limit), invert=False)
                            cylinder = cylinder.extract_surface()

                # 检查裁剪后是否还有有效的多边形网格
                if cylinder.n_cells > 0 and cylinder.n_points > 0:
                    all_cylinders.append(cylinder)

        # 合并所有圆柱
        if all_cylinders:
            combined_mesh = all_cylinders[0].merge(all_cylinders[1:])
            combined_mesh = combined_mesh.compute_normals(
                cell_normals=False,
                point_normals=True
            )
            return combined_mesh

        return pv.PolyData()  # 空mesh

    def _parse_structure(self, structure_text):
        """解析结构文本，提取顶点和连接"""
        import re

        lines = structure_text.split('\n')
        vertices = {}
        edges = []

        # 解析坐标
        coord_pattern = re.compile(r'(\w+)\s*=\s*\[(.*?)\]')
        for line in lines:
            match = coord_pattern.match(line.strip())
            if match:
                var_name = match.group(1)
                coords_str = match.group(2)
                try:
                    coords = [float(x.strip()) for x in coords_str.split(',')]
                    if len(coords) == 3:
                        vertices[var_name] = np.array(coords)
                except:
                    pass

        # 解析连接
        cylinder_pattern = re.compile(r'\((\w+),\s*(\w+)\)')
        for line in lines:
            match = cylinder_pattern.search(line)
            if match:
                v1 = match.group(1)
                v2 = match.group(2)
                if v1 in vertices and v2 in vertices:
                    edges.append((v1, v2))

        if not vertices or not edges:
            return None, None

        # 转换为numpy数组和索引
        vertex_names = list(vertices.keys())
        points = np.array([vertices[name] for name in vertex_names])

        name_to_idx = {name: idx for idx, name in enumerate(vertex_names)}
        connections = [[name_to_idx[v1], name_to_idx[v2]] for v1, v2 in edges]

        return points, connections


class MeshCacheLoader:
    """Mesh缓存加载器"""

    def __init__(self, cache_dir="work"):
        self.cache_dir = Path(cache_dir)
        self.quick_cache_file = self.cache_dir / "mesh_cache_quick.pkl.gz"
        self.full_cache_file = self.cache_dir / "mesh_cache_full.pkl.gz"

        self.quick_cache = {}
        self.full_cache = {}
        self.is_quick_loaded = False
        self.is_full_loaded = False

    def cache_exists(self):
        """检查缓存文件是否存在"""
        return self.full_cache_file.exists()

    def load_quick_cache(self):
        """加载快速缓存 (24个mesh, ~1MB, 0.2秒)"""
        if not self.quick_cache_file.exists():
            print("[WARNING] 快速缓存文件不存在")
            return False

        try:
            start_time = time.time()
            with gzip.open(self.quick_cache_file, 'rb') as f:
                self.quick_cache = pickle.load(f)

            self.is_quick_loaded = True
            elapsed = time.time() - start_time

            print(f"[OK] 快速缓存已加载: {len(self.quick_cache)} meshes ({elapsed:.2f}秒)")
            return True

        except Exception as e:
            print(f"[ERROR] 加载快速缓存失败: {e}")
            return False

    def load_full_cache(self):
        """加载完整缓存 (1,080个mesh, ~12MB, 2秒)"""
        if not self.full_cache_file.exists():
            print("[WARNING] 完整缓存文件不存在")
            return False

        try:
            start_time = time.time()
            with gzip.open(self.full_cache_file, 'rb') as f:
                self.full_cache = pickle.load(f)

            self.is_full_loaded = True
            elapsed = time.time() - start_time

            print(f"[OK] 完整缓存已加载: {len(self.full_cache)} meshes ({elapsed:.2f}秒)")
            return True

        except Exception as e:
            print(f"[ERROR] 加载完整缓存失败: {e}")
            return False

    def get_mesh(self, cell_type, slider, radius):
        """
        获取缓存的mesh

        Args:
            cell_type: 结构类型
            slider: slider值
            radius: 半径值

        Returns:
            PyVista mesh 或 None
        """
        key = f"{cell_type}_{slider}_{radius}"

        # 优先查完整缓存
        if self.is_full_loaded and key in self.full_cache:
            return self._deserialize_mesh(self.full_cache[key])

        # 回退到快速缓存
        if self.is_quick_loaded and key in self.quick_cache:
            return self._deserialize_mesh(self.quick_cache[key])

        return None

    def _deserialize_mesh(self, data):
        """从字典反序列化为PyVista mesh"""
        if data is None:
            return None

        try:
            import pyvista as pv

            mesh = pv.PolyData()
            mesh.points = data['points']
            mesh.faces = data['faces']

            return mesh

        except Exception as e:
            print(f"反序列化mesh失败: {e}")
            return None


# ============================================================================
# 独立测试和工具函数
# ============================================================================

def generate_cache_files(progress_callback=None):
    """
    生成所有缓存文件（快速+完整）

    Args:
        progress_callback: 进度回调函数
    """
    builder = MeshCacheBuilder()

    print("开始生成缓存文件...\n")

    # 生成快速缓存
    builder.generate_quick_cache(progress_callback)

    # 生成完整缓存
    builder.generate_full_cache(progress_callback)

    print("\n[OK] 所有缓存文件生成完成!")


def test_cache_loading():
    """测试缓存加载功能"""
    print("=" * 80)
    print("测试缓存加载")
    print("=" * 80)

    loader = MeshCacheLoader()

    # 测试快速缓存
    print("\n测试快速缓存...")
    if loader.load_quick_cache():
        mesh = loader.get_mesh("Cubic", 4, 0.3)
        if mesh:
            # 兼容新旧版本PyVista
            try:
                n_faces = mesh.n_cells
            except AttributeError:
                n_faces = mesh.n_faces
            print(f"  [OK] 成功加载 Cubic mesh: {mesh.n_points} 顶点, {n_faces} 面")
        else:
            print("  [ERROR] 加载mesh失败")

    # 测试完整缓存
    print("\n测试完整缓存...")
    if loader.load_full_cache():
        mesh = loader.get_mesh("BCC", 0, 0.5)
        if mesh:
            # 兼容新旧版本PyVista
            try:
                n_faces = mesh.n_cells
            except AttributeError:
                n_faces = mesh.n_faces
            print(f"  [OK] 成功加载 BCC mesh: {mesh.n_points} 顶点, {n_faces} 面")
        else:
            print("  [ERROR] 加载mesh失败")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        # 生成缓存
        generate_cache_files()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # 测试加载
        test_cache_loading()
    else:
        print("用法:")
        print("  python mesh_cache.py generate  # 生成缓存文件")
        print("  python mesh_cache.py test      # 测试缓存加载")
