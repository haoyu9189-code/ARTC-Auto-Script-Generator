#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D可视化控件模块
基于PyVista实现晶格结构的三维可视化显示

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import numpy as np
import platform
import os
import shutil
import subprocess
import tempfile
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from structure_set import get_crystal_structure

# 根据操作系统选择性导入可视化库
# 默认不显示可视化，只有系统为 "Windows" 时才显示
ENABLE_VISUALIZATION_SYSTEM = "Windows"
CURRENT_SYSTEM = platform.system()

if CURRENT_SYSTEM == ENABLE_VISUALIZATION_SYSTEM:
    try:
        import pyvista as pv
        from pyvistaqt import QtInteractor
        VISUALIZATION_AVAILABLE = True
        print(f"系统 {CURRENT_SYSTEM} 检测到，可视化功能已启用")
    except ImportError:
        print("警告: 无法导入 PyVista，可视化功能将被禁用")
        VISUALIZATION_AVAILABLE = False
else:
    VISUALIZATION_AVAILABLE = False
    print(f"系统 {CURRENT_SYSTEM} 检测到，可视化功能已禁用（需要 {ENABLE_VISUALIZATION_SYSTEM} 系统）")

# Global VTK warning suppression
if VISUALIZATION_AVAILABLE:
    try:
        import pyvista as pv
        # Suppress all VTK messages (warnings, errors, etc.) to console
        pv.vtk.vtkObject.GlobalWarningDisplayOff()
    except Exception:
        pass


class CellVisualizationWidget(QWidget):
    """3D visualization widget for displaying cell structure sketches using PyVista"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置对象名称，用于样式表排除圆角
        self.setObjectName("vtk_3d_widget")

        # Set widget background to match theme
        self.setStyleSheet("background-color: #1a1d29; border-radius: 0px;")

        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # 初始化mesh缓存加载器
        self.mesh_loader = None
        if VISUALIZATION_AVAILABLE:
            try:
                from mesh_cache import MeshCacheLoader
                self.mesh_loader = MeshCacheLoader()
                print("[OK] Mesh缓存系统已初始化")
            except ImportError:
                print("⚠️ 无法导入mesh_cache模块，将使用实时生成")

        if VISUALIZATION_AVAILABLE:
            # 完全禁用VTK警告输出（在创建plotter之前）
            try:
                import vtk
                vtk_output = vtk.vtkOutputWindow()
                vtk_output.SetGlobalWarningDisplay(0)
                # 创建一个静默的输出窗口
                vtk.vtkObject.GlobalWarningDisplayOff()
            except Exception:
                pass

            # Windows: Create PyVista Qt interactor
            self.plotter = QtInteractor(self)
            layout.addWidget(self.plotter.interactor)

            # Configure plotter appearance
            self.plotter.set_background('#1a1d29')  # Dark theme background
            self.plotter.enable_anti_aliasing()

            # 显式启用光照
            self.plotter.enable_lightkit()


            # 获取渲染器并确保光照已启用
            if hasattr(self.plotter, 'renderer'):
                self.plotter.renderer.SetUseShadows(False)  # 先不用阴影，简化问题
                self.plotter.renderer.SetTwoSidedLighting(True)  # 双面光照
            
            # Enable SSAO for better depth perception
            try:
                self.plotter.enable_ssao(radius=2.0, bias=0.01)
            except Exception:
                pass # SSAO might not be supported on all hardware

        else:
            # Linux: 显示提示信息
            from PyQt5.QtCore import Qt
            label = QLabel("3D 可视化在 Linux 环境下不可用\n请在 Windows 环境下查看 3D 模型")
            label.setStyleSheet("color: #888888; font-size: 14px;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            self.plotter = None

        # Store current cell type to detect changes
        self.current_cell_type = None

        # Store camera zoom state
        self.camera_zoom = 1.0  # 默认缩放倍数

        # Store base cell size for camera distance calculation
        self.base_cell_size = 5.0  # 基准cell size
        self.current_cell_size = 5.0  # 当前cell size

        # Lattice and Grid display states
        self.show_lattice = False  # 默认不显示晶格阵列
        self.show_grid = True  # 默认显示网格
        self.grid_actor = None  # 存储网格actor引用

        # Lattice dimensions (a×b×c)
        self.lattice_a = 3  # X方向晶胞数量
        self.lattice_b = 3  # Y方向晶胞数量
        self.lattice_c = 2  # Z方向晶胞数量

        # Stats text actor
        self.stats_text_actor = None  # 存储统计信息文字actor
        self.current_nodes_count = 0  # 当前节点数
        self.current_struts_count = 0  # 当前杆件数

        # 加载缓存文件（如果可用）
        if self.mesh_loader and VISUALIZATION_AVAILABLE:
            self._load_mesh_cache_async()

    def toggle_lattice(self, show, lattice_a=None, lattice_b=None, lattice_c=None):
        """切换晶格阵列显示 (a×b×c cells)

        Args:
            show: 是否显示晶格阵列
            lattice_a: X方向晶胞数量 (默认保持当前值)
            lattice_b: Y方向晶胞数量 (默认保持当前值)
            lattice_c: Z方向晶胞数量 (默认保持当前值)
        """
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return
        self.show_lattice = show

        # 更新 lattice 尺寸（如果提供了新值）
        if lattice_a is not None:
            self.lattice_a = lattice_a
        if lattice_b is not None:
            self.lattice_b = lattice_b
        if lattice_c is not None:
            self.lattice_c = lattice_c

        print(f"[Lattice] Toggled to: {show}, Size: {self.lattice_a}×{self.lattice_b}×{self.lattice_c}")

    def toggle_grid(self, show):
        """切换网格坐标显示"""
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return
        self.show_grid = show
        print(f"[Grid] Toggled to: {show}")

        # 如果grid_actor存在,立即更新其可见性
        if self.grid_actor is not None:
            try:
                if show:
                    self.plotter.add_actor(self.grid_actor)
                else:
                    self.plotter.remove_actor(self.grid_actor)
                self.plotter.render()
            except Exception as e:
                print(f"[Grid] Failed to toggle visibility: {e}")

    def get_camera_state(self):
        """获取当前相机状态（用于保存）"""
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return None
        try:
            if hasattr(self.plotter, 'camera') and self.plotter.camera is not None:
                camera = self.plotter.camera
                state = {
                    'position': [float(x) for x in camera.GetPosition()],
                    'focal_point': [float(x) for x in camera.GetFocalPoint()],
                    'view_up': [float(x) for x in camera.GetViewUp()],
                    'distance': float(camera.GetDistance())
                }
                print(f"相机状态已获取: {state}")
                return state
            else:
                print("相机对象不存在")
        except Exception as e:
            print(f"获取相机状态失败: {e}")
            import traceback
            traceback.print_exc()
        return None

    def set_camera_state(self, state):
        """恢复相机状态"""
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return
        if state and hasattr(self.plotter, 'camera'):
            camera = self.plotter.camera
            if 'position' in state:
                camera.SetPosition(state['position'])
            if 'focal_point' in state:
                camera.SetFocalPoint(state['focal_point'])
            if 'view_up' in state:
                camera.SetViewUp(state['view_up'])
            self.plotter.render()
            print(f"相机状态已恢复: {state}")

    def parse_structure_from_set(self, cell_type, slider_value=4):
        """Parse structure data from structure_set.py"""
        try:
            # 获取结构数据字符串，传入slider值
            structure_data = get_crystal_structure(cell_type, slider_value)

            if "结构" in structure_data and "不存在" in structure_data:
                return None, None

            # 解析坐标
            points = []
            point_names = {}
            lines = structure_data.split('\n')

            # 提取坐标定义
            for line in lines:
                if '=' in line and '[' in line and ']' in line:
                    parts = line.strip().split('=')
                    if len(parts) == 2:
                        name = parts[0].strip()
                        coord_str = parts[1].strip().strip('[]')
                        try:
                            coords = [float(x.strip()) for x in coord_str.split(',')]
                            if len(coords) == 3:
                                points.append(coords)
                                point_names[name] = len(points) - 1
                        except:
                            continue

            # 提取连接关系
            connections = []
            in_cylinders = False
            for line in lines:
                line = line.strip()
                if 'cylinders = [' in line:
                    in_cylinders = True
                    continue
                elif in_cylinders and ']' in line and '(' not in line:
                    break
                elif in_cylinders and '(' in line and ')' in line:
                    # 提取连接对
                    start = line.find('(')
                    end = line.find(')')
                    if start != -1 and end != -1:
                        pair_str = line[start+1:end]
                        parts = [p.strip() for p in pair_str.split(',')]
                        if len(parts) == 2:
                            point1, point2 = parts
                            if point1 in point_names and point2 in point_names:
                                connections.append([point_names[point1], point_names[point2]])

            if points and connections:
                return np.array(points), connections
            else:
                return None, None

        except Exception as e:
            print(f"Error parsing structure {cell_type}: {e}")
            return None, None

    def get_cell_structure(self, cell_type, slider_value=4):
        """Generate points and connections for different cell types"""

        # 首先尝试从structure_set动态获取
        points, connections = self.parse_structure_from_set(cell_type, slider_value)
        if points is not None and connections is not None:
            return points, connections

        # 如果structure_set中没有找到，使用默认的立方体结构
        if cell_type == "Cubic" or points is None:
            # 立方体结构 - 8个顶点
            points = np.array([
                [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],  # 底面
                [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]   # 顶面
            ])
            # 立方体的12条边
            connections = [
                [0, 1], [1, 2], [2, 3], [3, 0],  # 底面
                [4, 5], [5, 6], [6, 7], [7, 4],  # 顶面
                [0, 4], [1, 5], [2, 6], [3, 7]   # 垂直边
            ]

        return points, connections

    def update_visualization(self, cell_type, slider_value=4, radius=0.3, cell_size=5.0, reset_view_angle=True, resolution=12, enable_clipping=True):
        """Update the 3D visualization based on cell type, slider value and strut radius

        Args:
            cell_type: 晶胞类型
            slider_value: slider值
            radius: 圆柱半径
            cell_size: 晶胞尺寸
            reset_view_angle: 是否重置视角
            resolution: 圆柱网格分辨率（网格线密度），值越大网格越密，推荐范围: 8-24
            enable_clipping: 是否启用切割，将超出范围的部分切除
        """

        # Linux 下不执行可视化
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return

        # Lattice模式下降低精度以提升性能
        if self.show_lattice:
            resolution = 8  # 降低精度: 12 -> 8

        # 禁用自动渲染，避免中间状态闪烁
        render_window = self.plotter.render_window
        if render_window:
            render_window.SetSwapBuffers(0)  # 禁用交换缓冲区

        # 只在cell type改变时才清空，但不强制重置视角（尊重外部参数）
        # 这样可以避免闪烁，同时保持用户保存的相机视角
        if cell_type != self.current_cell_type:
            self.plotter.clear()
            # 只在外部明确要求重置时才重置（不覆盖 reset_view_angle 参数）
            # reset_view_angle = True  # 移除强制重置
        else:
            # 只清空actor，不重置整个plotter
            self.plotter.clear_actors()

        # 🚀 优先尝试从缓存加载mesh
        combined_mesh = None
        default_cell_size = 5.0  # 缓存mesh默认的cell size

        # 只在cell_size等于默认值时使用缓存，否则实时生成以确保切割和封盖正确
        use_cache = abs(cell_size - default_cell_size) < 0.001

        if use_cache and self.mesh_loader and self.mesh_loader.is_full_loaded:
            combined_mesh = self.mesh_loader.get_mesh(cell_type, slider_value, radius)
            if combined_mesh:
                # print(f"[OK] 使用缓存mesh: {cell_type}_{slider_value}_{radius}")
                # 使用缓存时，需要获取节点数和杆件数用于统计显示
                points, connections = self.get_cell_structure(cell_type, slider_value)
                self.current_nodes_count = len(points)
                self.current_struts_count = len(connections)

        # 如果缓存中没有，则实时生成
        if combined_mesh is None:
            # Get structure data
            points, connections = self.get_cell_structure(cell_type, slider_value)

            # 保存节点数和杆件数用于统计显示
            self.current_nodes_count = len(points)
            self.current_struts_count = len(connections)

            # 根据cell_size缩放坐标点
            # get_cell_structure返回的坐标基于默认cell_size=5.0
            default_cell_size = 5.0
            scale_factor = cell_size / default_cell_size
            points = points * scale_factor

            # Swap Y and Z coordinates for display (to match previous behavior)
            display_points = points.copy()
            display_points[:, [1, 2]] = display_points[:, [2, 1]]  # Swap Y and Z columns

            # 性能优化：合并所有圆柱为一个mesh
            all_cylinders = []

            # Calculate clipping limits
            limit = cell_size / 2.0

            # 准备裁剪平面 (如果启用)
            planes = None
            if enable_clipping:
                try:
                    import vtk
                    planes = vtk.vtkPlaneCollection()

                    # Define 6 planes with outward normals (pointing away from the box center)
                    # This tells vtkClipClosedSurface to remove everything on the "positive" side of the plane

                    # x = limit, n = (1,0,0) -> removes x > limit
                    p = vtk.vtkPlane(); p.SetOrigin(limit, 0, 0); p.SetNormal(1, 0, 0); planes.AddItem(p)
                    # x = -limit, n = (-1,0,0) -> removes x < -limit
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

            # Create cylinders for each connection
            for connection in connections:
                start_point = display_points[connection[0]]
                end_point = display_points[connection[1]]

                # Create PyVista cylinder
                direction = end_point - start_point
                length = np.linalg.norm(direction)

                if length > 1e-6:
                    center = (start_point + end_point) / 2
                    direction_normalized = direction / length

                    # Create cylinder mesh
                    cylinder = pv.Cylinder(
                        center=center,
                        direction=direction_normalized,
                        radius=radius,
                        height=length,
                        resolution=resolution
                    )

                    # 如果启用切割且不是lattice模式，对圆柱体进行切割和封盖
                    # Lattice模式下，先不切割单个cell，而是复制后对整体切割
                    if enable_clipping and planes and not self.show_lattice:
                        cylinder = self._clip_and_cap_mesh(cylinder, limit)
                        if cylinder is None:
                            continue

                    if cylinder.n_cells > 0 and cylinder.n_points > 0:
                        all_cylinders.append(cylinder)

            # 创建球体（在每个关键点处）
            all_spheres = []
            for point in display_points:
                # 创建球体
                sphere = pv.Sphere(
                    radius=radius,
                    center=point,
                    theta_resolution=resolution,
                    phi_resolution=resolution
                )

                # 如果启用切割且不是lattice模式，对球体进行切割和封盖
                # Lattice模式下，先不切割单个cell，而是复制后对整体切割
                if enable_clipping and planes and not self.show_lattice:
                    sphere = self._clip_and_cap_mesh(sphere, limit)
                    if sphere is None:
                        continue

                if sphere.n_cells > 0 and sphere.n_points > 0:
                    all_spheres.append(sphere)

            # 合并所有圆柱和球体为一个大的mesh
            all_meshes = all_cylinders + all_spheres
            if all_meshes:
                # 使用 merge 合并所有 mesh
                combined_mesh = all_meshes[0].merge(all_meshes[1:])

                # 一次性计算所有法线
                combined_mesh = combined_mesh.compute_normals(cell_normals=False, point_normals=True)

        # 创建晶格阵列: a×b×c (可配置的晶胞数量)
        # Lattice模式：对每个圆柱/球体单独进行切割和封盖（与单个cell逻辑一致）
        if self.show_lattice and combined_mesh and combined_mesh.n_points > 0:
            # 获取 lattice 尺寸
            lattice_a = self.lattice_a  # X方向晶胞数量
            lattice_b = self.lattice_b  # Y方向晶胞数量
            lattice_c = self.lattice_c  # Z方向晶胞数量

            # 计算Lattice的切割边界
            lattice_limit_x = cell_size * lattice_a / 2.0  # X方向半宽 (a个cell / 2)
            lattice_limit_y = cell_size * lattice_b / 2.0  # Y方向半宽 (b个cell / 2)
            lattice_limit_z = cell_size * lattice_c / 2.0  # Z方向半宽 (c个cell / 2)

            # 计算中心点
            center_x = cell_size * (lattice_a - 1) / 2.0
            center_y = cell_size * (lattice_b - 1) / 2.0
            center_z = cell_size * (lattice_c - 1) / 2.0

            # 定义切割边界 (相对于原点)
            x_min = center_x - lattice_limit_x  # = -cell_size/2
            x_max = center_x + lattice_limit_x  # = cell_size * 2.5
            y_min = center_y - lattice_limit_y  # = -cell_size/2
            y_max = center_y + lattice_limit_y  # = cell_size * 2.5
            z_min = center_z - lattice_limit_z  # = -cell_size/2
            z_max = center_z + lattice_limit_z  # = cell_size * 1.5

            # 定义晶胞位置 (i, j, k): i=X方向, j=Y方向, k=Z方向
            positions = []

            # 生成 a×b×c 的晶胞阵列
            for k in range(lattice_c):  # Z: 0 to c-1
                for i in range(lattice_a):  # X: 0 to a-1
                    for j in range(lattice_b):  # Y: 0 to b-1
                        positions.append((i, j, k))

            # 收集所有圆柱和球体（每个单独处理）
            all_lattice_meshes = []

            print(f"[Lattice] Clipping bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}], Z=[{z_min:.2f}, {z_max:.2f}]")

            # 对每个晶胞位置，复制圆柱和球体并单独切割封盖
            for i, j, k in positions:
                offset = np.array([i * cell_size, j * cell_size, k * cell_size])

                # 处理圆柱
                for cyl in all_cylinders:
                    cyl_copy = cyl.copy()
                    cyl_copy.translate(offset, inplace=True)

                    if enable_clipping:
                        cyl_copy = self._clip_and_cap_mesh_lattice(cyl_copy, x_min, x_max, y_min, y_max, z_min, z_max)
                        if cyl_copy is None:
                            continue

                    if cyl_copy.n_cells > 0 and cyl_copy.n_points > 0:
                        all_lattice_meshes.append(cyl_copy)

                # 处理球体
                for sph in all_spheres:
                    sph_copy = sph.copy()
                    sph_copy.translate(offset, inplace=True)

                    if enable_clipping:
                        sph_copy = self._clip_and_cap_mesh_lattice(sph_copy, x_min, x_max, y_min, y_max, z_min, z_max)
                        if sph_copy is None:
                            continue

                    if sph_copy.n_cells > 0 and sph_copy.n_points > 0:
                        all_lattice_meshes.append(sph_copy)

            # 合并所有mesh
            if all_lattice_meshes:
                combined_mesh = all_lattice_meshes[0].merge(all_lattice_meshes[1:])
                combined_mesh = combined_mesh.compute_normals(cell_normals=False, point_normals=True)
                print(f"[Lattice] Generated {len(positions)} cells ({lattice_a}×{lattice_b}×{lattice_c} array) with {len(all_lattice_meshes)} meshes")

        # 渲染mesh（无论是从缓存加载还是实时生成）
        if combined_mesh and combined_mesh.n_points > 0:
            # 一次性添加整个mesh（而不是逐个添加）
            # Enable Eye Dome Lighting (EDL) for enhanced depth and shadow definition
            # This gives a very strong "3D" look without needing complex PBR setups
            self.plotter.enable_eye_dome_lighting()

            actor = self.plotter.add_mesh(
                combined_mesh,
                color='#d0d0e0',   # Slight blue-grey tint to show highlights better
                smooth_shading=True,
                show_edges=False,
                pbr=False,
                specular=0.6,      # Stronger highlights
                specular_power=30, # Sharper highlights
                diffuse=0.9,
                ambient=0.2
            )

        # 添加网格坐标 (Grid)
        if self.show_grid:
            # 移除旧的网格actor
            if self.grid_actor is not None:
                try:
                    self.plotter.remove_actor(self.grid_actor)
                except Exception:
                    pass
                self.grid_actor = None

            # 计算网格位置和大小
            if self.show_lattice:
                # Lattice模式: Grid居中于a×b阵列
                grid_center_x = cell_size * (self.lattice_a - 1) / 2.0  # a×b阵列X方向中心
                grid_center_y = cell_size * (self.lattice_b - 1) / 2.0  # a×b阵列Y方向中心
                grid_size = cell_size * max(self.lattice_a, self.lattice_b)  # 网格覆盖整个阵列
            else:
                # 单晶胞模式: Grid居中于原点
                grid_center_x = 0
                grid_center_y = 0
                grid_size = cell_size

            # 创建Grid平面 (XY平面,Z=底部)
            limit = cell_size / 2.0
            grid_z_position = -limit  # Grid贴在晶胞底部

            # 使用PyVista创建网格
            try:
                # 计算网格分辨率，使网格密度固定为边长为1
                # resolution = grid_size 意味着每个单位长度有1条网格线
                grid_resolution = int(grid_size)

                # 创建网格平面
                grid = pv.Plane(
                    center=(grid_center_x, grid_center_y, grid_z_position),
                    direction=(0, 0, 1),  # Z方向法线
                    i_size=grid_size,
                    j_size=grid_size,
                    i_resolution=grid_resolution,
                    j_resolution=grid_resolution
                )

                # 添加网格到场景（增加可见度：更粗的线条和更高的不透明度）
                self.grid_actor = self.plotter.add_mesh(
                    grid,
                    color='#5a8bc0',  # 更亮的蓝色
                    style='wireframe',
                    line_width=3,  # 增加线宽从1到3
                    opacity=0.7  # 增加不透明度从0.3到0.7
                )
                print(f"[Grid] Added at center=({grid_center_x}, {grid_center_y}, {grid_z_position}), size={grid_size}")
            except Exception as e:
                print(f"[Grid] Failed to create grid: {e}")
        else:
            # 如果不显示Grid,移除旧的grid_actor
            if self.grid_actor is not None:
                try:
                    self.plotter.remove_actor(self.grid_actor)
                except Exception:
                    pass
                self.grid_actor = None

        # Update camera if needed
        if reset_view_angle:
            self.plotter.reset_camera()
            # Set default view angle (matching matplotlib's elev=20, azim=135)
            self.plotter.camera.elevation = 20
            self.plotter.camera.azimuth = 135

        # Adjust camera distance based on cell_size change
        # 当cell_size改变时，调整相机距离、焦点和裁剪范围以保持视野中的相对大小
        if hasattr(self, 'current_cell_size') and self.current_cell_size != cell_size:
            if hasattr(self.plotter, 'camera') and self.plotter.camera is not None:
                # 计算缩放比例
                scale_ratio = cell_size / self.current_cell_size

                # 获取当前相机参数
                camera = self.plotter.camera
                current_position = camera.GetPosition()
                current_focal_point = camera.GetFocalPoint()

                # 计算晶胞中心位置（根据是否显示lattice）
                if self.show_lattice:
                    # Lattice模式: 中心在 (a-1)/2, (b-1)/2, (c-1)/2
                    new_focal_point = [
                        cell_size * (self.lattice_a - 1) / 2.0,
                        cell_size * (self.lattice_b - 1) / 2.0,
                        cell_size * (self.lattice_c - 1) / 2.0
                    ]
                else:
                    # 单晶胞模式: 中心在原点
                    new_focal_point = [0, 0, 0]

                # 计算相机位置相对于当前焦点的向量
                camera_vector = [
                    current_position[0] - current_focal_point[0],
                    current_position[1] - current_focal_point[1],
                    current_position[2] - current_focal_point[2]
                ]

                # 按比例缩放相机向量
                scaled_camera_vector = [v * scale_ratio for v in camera_vector]

                # 计算新的相机位置（基于新焦点）
                new_position = [
                    new_focal_point[0] + scaled_camera_vector[0],
                    new_focal_point[1] + scaled_camera_vector[1],
                    new_focal_point[2] + scaled_camera_vector[2]
                ]

                # 更新相机位置和焦点
                camera.SetPosition(new_position)
                camera.SetFocalPoint(new_focal_point)

                # 调整裁剪范围（clipping range）以适应新的场景大小
                # 裁剪范围也需要按比例缩放
                current_clipping = camera.GetClippingRange()
                new_clipping = (
                    current_clipping[0] * scale_ratio,
                    current_clipping[1] * scale_ratio
                )
                camera.SetClippingRange(new_clipping)

                print(f"[Camera] Cell size changed from {self.current_cell_size} to {cell_size}, scale ratio: {scale_ratio:.2f}")
                print(f"[Camera] Position: {current_position} -> {new_position}")
                print(f"[Camera] Focal point: {current_focal_point} -> {new_focal_point}")
                print(f"[Camera] Clipping range: {current_clipping} -> {new_clipping}")

        # 更新当前cell_size记录
        self.current_cell_size = cell_size

        # Update current cell type and parameters (for STL export)
        self.current_cell_type = cell_type
        self.current_radius = radius
        self.current_slider_value = slider_value

        # 添加统计信息文字（左下角，灰色）
        try:
            # 移除旧的文字actor
            if self.stats_text_actor is not None:
                try:
                    self.plotter.remove_actor(self.stats_text_actor)
                except Exception:
                    pass
                self.stats_text_actor = None

            # 创建统计信息文字
            stats_text = f"Nodes: {self.current_nodes_count}\nStruts: {self.current_struts_count}"

            # 添加2D文字到左下角
            self.stats_text_actor = self.plotter.add_text(
                stats_text,
                position='lower_left',
                font_size=10,
                color='#a3a3a3',  # 灰色 (亮20%)
                font='arial'
            )
        except Exception as e:
            print(f"[Stats] Failed to add stats text: {e}")

        # 重新启用缓冲区交换并一次性渲染
        if render_window:
            render_window.SetSwapBuffers(1)  # 重新启用交换缓冲区

        # 只渲染一次，所有更新完成后
        self.plotter.render()

    def _load_mesh_cache_async(self):
        """异步加载mesh缓存（启动时在后台执行，不阻塞UI）"""
        from PyQt5.QtCore import QThread, QTimer
        import threading

        def load_cache_thread():
            """在后台线程中加载缓存"""
            if not self.mesh_loader:
                return

            # 检查缓存文件是否存在
            if not self.mesh_loader.cache_exists():
                print("\n" + "=" * 80)
                print("⚠️ 首次运行：需要生成mesh缓存文件")
                print("=" * 80)
                print("这是一次性操作，大约需要10-15秒...")
                print("生成后，下次启动只需2秒加载\n")

                # 生成缓存文件
                from mesh_cache import MeshCacheBuilder
                builder = MeshCacheBuilder()

                def progress_callback(current, total, message):
                    """进度回调"""
                    percent = (current / total * 100) if total > 0 else 0
                    print(f"  进度: {current}/{total} ({percent:.1f}%) - {message}")

                # 生成完整缓存
                builder.generate_full_cache(progress_callback)
                print("\n[OK] 缓存文件生成完成!\n")

            # 加载完整缓存
            print("正在后台加载mesh缓存...")
            if self.mesh_loader.load_full_cache():
                print("[OK] Mesh缓存加载完成，所有操作现在零延迟!\n")
            else:
                print("⚠️ 缓存加载失败，将使用实时生成模式\n")

        # 使用线程在后台加载，不阻塞UI
        thread = threading.Thread(target=load_cache_thread, daemon=True)

        # 延迟100ms后启动后台线程
        QTimer.singleShot(100, thread.start)

    def save_screenshot(self, filepath, transparent_background=False):
        """保存当前可视化的截图（原原本本保存当前显示的内容）

        Args:
            filepath: 保存路径（支持 .png, .jpg, .bmp 等格式）
            transparent_background: 是否使用透明背景（仅PNG支持）

        Returns:
            bool: 是否保存成功
        """
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            print("可视化不可用，无法保存截图")
            return False

        try:
            # 直接使用plotter的screenshot方法，保存当前渲染的内容
            self.plotter.screenshot(filepath, transparent_background=transparent_background)
            print(f"截图已保存: {filepath}")
            return True
        except Exception as e:
            print(f"保存截图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_screenshot_high_res(self, filepath, scale=2, transparent_background=False):
        """保存高分辨率截图（放大渲染后保存）

        Args:
            filepath: 保存路径
            scale: 放大倍数（默认2倍，即分辨率翻倍）
            transparent_background: 是否使用透明背景

        Returns:
            bool: 是否保存成功
        """
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            print("可视化不可用，无法保存截图")
            return False

        try:
            # 获取当前窗口大小
            current_size = self.plotter.window_size

            # 临时调整窗口大小以获取高分辨率图像
            high_res_size = (current_size[0] * scale, current_size[1] * scale)

            # 使用image_scale参数获取高分辨率截图
            # PyVista的screenshot支持image_scale参数
            self.plotter.screenshot(
                filepath,
                transparent_background=transparent_background,
                window_size=high_res_size
            )
            print(f"高分辨率截图已保存: {filepath} ({high_res_size[0]}x{high_res_size[1]})")
            return True
        except Exception as e:
            print(f"保存高分辨率截图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_screenshot_svg(self, filepath):
        """保存当前可视化为SVG格式（白色背景，不包含统计文字）

        Args:
            filepath: 保存路径（.svg文件）

        Returns:
            bool: 是否保存成功
        """
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            print("可视化不可用，无法保存SVG")
            return False

        try:
            # 保存当前背景色
            original_background = self.plotter.background_color

            # 临时隐藏统计文字
            stats_was_visible = False
            if self.stats_text_actor is not None:
                try:
                    stats_was_visible = self.stats_text_actor.GetVisibility()
                    self.stats_text_actor.SetVisibility(False)
                except:
                    pass

            # 设置白色背景
            self.plotter.set_background('white')
            self.plotter.render()

            # 使用PyVista的export_graphics导出SVG
            # PyVista支持导出为多种矢量格式
            if filepath.lower().endswith('.svg'):
                self.plotter.save_graphic(filepath)
                print(f"SVG已保存: {filepath}")
            else:
                # 如果不是SVG，保存为PNG（白色背景）
                self.plotter.screenshot(filepath, transparent_background=False)
                print(f"截图已保存: {filepath}")

            # 恢复统计文字显示
            if self.stats_text_actor is not None and stats_was_visible:
                try:
                    self.stats_text_actor.SetVisibility(True)
                except:
                    pass

            # 恢复原来的背景色
            self.plotter.set_background(original_background)
            self.plotter.render()

            return True
        except Exception as e:
            print(f"保存SVG失败: {e}")
            import traceback
            traceback.print_exc()
            # 尝试恢复背景色和统计文字
            try:
                self.plotter.set_background('#1a1d29')
                if self.stats_text_actor is not None:
                    self.stats_text_actor.SetVisibility(True)
                self.plotter.render()
            except:
                pass
            return False

    def _clip_and_cap_mesh(self, mesh, limit):
        """对单个mesh进行切割和封盖（单Cell模式）

        Args:
            mesh: 待切割的PyVista mesh
            limit: 切割边界（以原点为中心，-limit到+limit）

        Returns:
            切割并封盖后的mesh，如果完全在边界外则返回None
        """
        bounds = mesh.bounds
        (xmin, xmax, ymin, ymax, zmin, zmax) = bounds

        # 检查是否完全在外部
        if (xmax < -limit or xmin > limit or
            ymax < -limit or ymin > limit or
            zmax < -limit or zmin > limit):
            return None  # 完全在外部，跳过

        # 检查是否完全在内部
        if (xmin > -limit and xmax < limit and
            ymin > -limit and ymax < limit and
            zmin > -limit and zmax < limit):
            return mesh  # 完全在内部，保留原样

        # 需要切割和封盖
        try:
            # 1. Clip the body (uncapped)
            body = mesh.clip_box(bounds=(-limit, limit, -limit, limit, -limit, limit), invert=False)
            body = body.extract_surface()

            # 2. Generate Caps
            caps = []

            # 定义切割平面信息
            planes_info = [
                ((1, 0, 0), (limit, 0, 0), lambda b: b[1] > limit),   # X+
                ((-1, 0, 0), (-limit, 0, 0), lambda b: b[0] < -limit), # X-
                ((0, 1, 0), (0, limit, 0), lambda b: b[3] > limit),   # Y+
                ((0, -1, 0), (0, -limit, 0), lambda b: b[2] < -limit), # Y-
                ((0, 0, 1), (0, 0, limit), lambda b: b[5] > limit),   # Z+
                ((0, 0, -1), (0, 0, -limit), lambda b: b[4] < -limit)  # Z-
            ]

            for normal, origin, check_func in planes_info:
                # Only slice if the mesh actually crosses this plane
                if not check_func(bounds):
                    continue

                # Slice the ORIGINAL mesh to get the full cross-section contour
                cut = mesh.slice(normal=normal, origin=origin, generate_triangles=True)

                if cut.n_points > 0:
                    try:
                        # Fill the contour to get a solid disk
                        disk = cut.delaunay_2d()

                        # Clip the disk to the box
                        tolerance = 0.01
                        expanded_limit = limit + tolerance
                        cap = disk.clip_box(bounds=(-expanded_limit, expanded_limit,
                                                   -expanded_limit, expanded_limit,
                                                   -expanded_limit, expanded_limit), invert=False)
                        cap = cap.extract_surface()

                        if cap.n_points > 0:
                            caps.append(cap)
                    except Exception:
                        pass

            # 3. Combine body and caps
            if caps:
                for cap in caps:
                    body = body.merge(cap)

            return body

        except Exception:
            # Fallback to simple clip (uncapped)
            clipped = mesh.clip_box(bounds=(-limit, limit, -limit, limit, -limit, limit), invert=False)
            return clipped.extract_surface()

    def _clip_and_cap_mesh_lattice(self, mesh, x_min, x_max, y_min, y_max, z_min, z_max):
        """对单个mesh进行切割和封盖（Lattice模式）

        Args:
            mesh: 待切割的PyVista mesh
            x_min, x_max: X方向切割边界
            y_min, y_max: Y方向切割边界
            z_min, z_max: Z方向切割边界

        Returns:
            切割并封盖后的mesh，如果完全在边界外则返回None
        """
        bounds = mesh.bounds
        (mxmin, mxmax, mymin, mymax, mzmin, mzmax) = bounds

        # 检查是否完全在外部
        if (mxmax < x_min or mxmin > x_max or
            mymax < y_min or mymin > y_max or
            mzmax < z_min or mzmin > z_max):
            return None  # 完全在外部，跳过

        # 检查是否完全在内部
        if (mxmin > x_min and mxmax < x_max and
            mymin > y_min and mymax < y_max and
            mzmin > z_min and mzmax < z_max):
            return mesh  # 完全在内部，保留原样

        # 需要切割和封盖
        try:
            # 1. Clip the body (uncapped)
            body = mesh.clip_box(bounds=(x_min, x_max, y_min, y_max, z_min, z_max), invert=False)
            body = body.extract_surface()

            # 2. Generate Caps
            caps = []
            lattice_planes_info = [
                ((1, 0, 0), (x_max, 0, 0), lambda b: b[1] > x_max),   # X+
                ((-1, 0, 0), (x_min, 0, 0), lambda b: b[0] < x_min),  # X-
                ((0, 1, 0), (0, y_max, 0), lambda b: b[3] > y_max),   # Y+
                ((0, -1, 0), (0, y_min, 0), lambda b: b[2] < y_min),  # Y-
                ((0, 0, 1), (0, 0, z_max), lambda b: b[5] > z_max),   # Z+
                ((0, 0, -1), (0, 0, z_min), lambda b: b[4] < z_min)   # Z-
            ]

            for normal, origin, check_func in lattice_planes_info:
                # Only slice if the mesh actually crosses this plane
                if not check_func(bounds):
                    continue

                # Slice the ORIGINAL mesh to get the full cross-section contour
                cut = mesh.slice(normal=normal, origin=origin, generate_triangles=True)

                if cut.n_points > 0:
                    try:
                        # Fill the contour to get a solid disk
                        disk = cut.delaunay_2d()

                        # Clip the disk to the box
                        tolerance = 0.01
                        cap = disk.clip_box(bounds=(x_min - tolerance, x_max + tolerance,
                                                   y_min - tolerance, y_max + tolerance,
                                                   z_min - tolerance, z_max + tolerance), invert=False)
                        cap = cap.extract_surface()

                        if cap.n_points > 0:
                            caps.append(cap)
                    except Exception:
                        pass

            # 3. Combine body and caps
            if caps:
                for cap in caps:
                    body = body.merge(cap)

            return body

        except Exception:
            # Fallback to simple clip (uncapped)
            clipped = mesh.clip_box(bounds=(x_min, x_max, y_min, y_max, z_min, z_max), invert=False)
            return clipped.extract_surface()

    def save_blend(self, filepath, export_resolution=32):
        """保存当前晶格结构为Blender .blend格式（通过OBJ中间格式转换）

        Args:
            filepath: 保存路径（.blend文件）
            export_resolution: 导出时的圆柱/球体分辨率（默认32，比显示时更精细）

        Returns:
            bool: 是否保存成功
        """
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            print("可视化不可用，无法保存blend")
            return False

        # 检查是否有当前显示的结构
        if self.current_cell_type is None:
            print("没有当前结构可导出")
            return False

        try:
            print(f"[Blend Export] 正在以高分辨率 (resolution={export_resolution}) 生成mesh...")

            # 获取当前结构的参数
            cell_type = self.current_cell_type
            cell_size = self.current_cell_size
            radius = getattr(self, 'current_radius', 0.3)
            slider_value = getattr(self, 'current_slider_value', 0)

            # 获取结构数据（使用与可视化相同的方法）
            points, connections = self.get_cell_structure(cell_type, slider_value)

            # 根据cell_size缩放坐标点
            # get_cell_structure返回的坐标基于默认cell_size=5.0
            default_cell_size = 5.0
            scale_factor = cell_size / default_cell_size
            points = points * scale_factor

            # Swap Y and Z coordinates for display (to match visualization)
            display_points = points.copy()
            display_points[:, [1, 2]] = display_points[:, [2, 1]]  # Swap Y and Z columns

            # 生成高分辨率的圆柱体和球体
            all_cylinders = []
            all_spheres = []

            # 创建圆柱
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
                        resolution=export_resolution,
                        capping=False  # 不需要端盖，球体会覆盖端点
                    )
                    all_cylinders.append(cylinder)

            # 创建球体
            for point in display_points:
                sphere = pv.Sphere(
                    radius=radius,
                    center=point,
                    theta_resolution=export_resolution,
                    phi_resolution=export_resolution
                )
                all_spheres.append(sphere)

            # 如果是Lattice模式
            if self.show_lattice:
                lattice_a = self.lattice_a
                lattice_b = self.lattice_b
                lattice_c = self.lattice_c

                # 计算切割边界（与可视化渲染使用相同的逻辑）
                lattice_limit_x = cell_size * lattice_a / 2.0
                lattice_limit_y = cell_size * lattice_b / 2.0
                lattice_limit_z = cell_size * lattice_c / 2.0
                center_x = cell_size * (lattice_a - 1) / 2.0
                center_y = cell_size * (lattice_b - 1) / 2.0
                center_z = cell_size * (lattice_c - 1) / 2.0

                x_min = center_x - lattice_limit_x
                x_max = center_x + lattice_limit_x
                y_min = center_y - lattice_limit_y
                y_max = center_y + lattice_limit_y
                z_min = center_z - lattice_limit_z
                z_max = center_z + lattice_limit_z

                # 生成所有位置
                positions = []
                for k in range(lattice_c):
                    for i in range(lattice_a):
                        for j in range(lattice_b):
                            positions.append((i, j, k))

                print(f"[Blend Export] 生成 {lattice_a}×{lattice_b}×{lattice_c} = {len(positions)} 个晶胞...")
                print(f"[Blend Export] 切割边界: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}], Z=[{z_min:.2f}, {z_max:.2f}]")

                # 复制mesh到每个位置（不切割，在Blender中切割）
                all_lattice_meshes = []
                for i, j, k in positions:
                    offset = np.array([i * cell_size, j * cell_size, k * cell_size])

                    # 复制并移动每个圆柱
                    for cyl in all_cylinders:
                        cyl_copy = cyl.copy()
                        cyl_copy.translate(offset, inplace=True)
                        all_lattice_meshes.append(cyl_copy)

                    # 复制并移动每个球体
                    for sph in all_spheres:
                        sph_copy = sph.copy()
                        sph_copy.translate(offset, inplace=True)
                        all_lattice_meshes.append(sph_copy)

                if not all_lattice_meshes:
                    print("没有生成任何mesh")
                    return False

                combined_mesh = all_lattice_meshes[0].merge(all_lattice_meshes[1:])
                print(f"[Blend Export] Lattice模式: 生成了 {len(all_lattice_meshes)} 个mesh")

            else:
                # 单Cell模式
                all_meshes = []

                # 添加圆柱
                for cyl in all_cylinders:
                    all_meshes.append(cyl)

                # 添加球体
                for sph in all_spheres:
                    all_meshes.append(sph)

                if not all_meshes:
                    print("没有生成任何mesh")
                    return False

                combined_mesh = all_meshes[0].merge(all_meshes[1:])
                print(f"[Blend Export] 单Cell模式: 生成了 {len(all_meshes)} 个mesh")

            # 计算法线并保存为OBJ中间格式
            combined_mesh = combined_mesh.compute_normals(cell_normals=False, point_normals=True)

            # 创建临时OBJ文件路径
            import tempfile
            import subprocess
            import shutil

            # 确保filepath以.blend结尾
            if not filepath.lower().endswith('.blend'):
                filepath = filepath + '.blend'

            # 创建临时OBJ文件
            temp_obj = tempfile.NamedTemporaryFile(suffix='.obj', delete=False)
            temp_obj_path = temp_obj.name
            temp_obj.close()

            try:
                # 保存为OBJ格式
                combined_mesh.save(temp_obj_path)
                print(f"[Blend Export] OBJ临时文件已保存: {temp_obj_path}")

                # 查找Blender可执行文件
                blender_paths = [
                    r"D:\blender\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
                    "blender",  # 尝试从PATH查找
                ]

                blender_exe = None
                for path in blender_paths:
                    if os.path.exists(path) or shutil.which(path):
                        blender_exe = path
                        break

                if blender_exe is None:
                    print("错误: 未找到Blender。请安装Blender或将其添加到PATH环境变量。")
                    # 退回到保存OBJ
                    obj_fallback = filepath.replace('.blend', '.obj')
                    shutil.copy(temp_obj_path, obj_fallback)
                    print(f"已保存OBJ替代文件: {obj_fallback}")
                    return False

                # 创建简化的Blender Python脚本（直接导入，不切割）
                blender_script = f'''
import bpy

# 清除默认场景中的所有对象
bpy.ops.wm.read_factory_settings(use_empty=True)

# 导入OBJ文件
bpy.ops.wm.obj_import(filepath=r"{temp_obj_path}")

# 获取导入的对象并重命名
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        obj.name = "Lattice_Structure"
        print(f"导入完成: 顶点数={{len(obj.data.vertices)}}, 面数={{len(obj.data.polygons)}}")
        break

# 保存为.blend文件
bpy.ops.wm.save_as_mainfile(filepath=r"{filepath}")

print("Blend文件已保存: {filepath}")
'''

                # 创建临时脚本文件
                temp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
                temp_script_path = temp_script.name
                temp_script.write(blender_script)
                temp_script.close()

                # 调用Blender执行脚本
                print(f"[Blend Export] 调用Blender转换...")
                result = subprocess.run(
                    [blender_exe, '--background', '--python', temp_script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=120
                )

                # 清理临时脚本
                os.unlink(temp_script_path)

                if result.returncode == 0 and os.path.exists(filepath):
                    print(f"Blend已保存: {filepath} (顶点数: {combined_mesh.n_points}, 面数: {combined_mesh.n_cells})")
                    return True
                else:
                    print(f"Blender转换失败: {result.stderr}")
                    # 退回到保存OBJ
                    obj_fallback = filepath.replace('.blend', '.obj')
                    shutil.copy(temp_obj_path, obj_fallback)
                    print(f"已保存OBJ替代文件: {obj_fallback}")
                    return False

            finally:
                # 清理临时OBJ文件
                if os.path.exists(temp_obj_path):
                    os.unlink(temp_obj_path)

        except Exception as e:
            print(f"保存Blend失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_stl(self, filepath, export_resolution=32):
        """保存当前晶格结构为STL格式（无需外部依赖）"""
        if not VISUALIZATION_AVAILABLE or self.plotter is None:
            return False
        if self.current_cell_type is None:
            return False

        try:
            cell_size = self.current_cell_size
            radius = getattr(self, 'current_radius', 0.3)
            slider_value = getattr(self, 'current_slider_value', 0)
            points, connections = self.get_cell_structure(self.current_cell_type, slider_value)
            points = points * (cell_size / 5.0)
            points[:, [1, 2]] = points[:, [2, 1]]

            meshes = []
            for c in connections:
                d = points[c[1]] - points[c[0]]
                L = np.linalg.norm(d)
                if L > 1e-6:
                    meshes.append(pv.Cylinder(center=(points[c[0]]+points[c[1]])/2, direction=d/L,
                        radius=radius, height=L, resolution=export_resolution, capping=False))
            for p in points:
                meshes.append(pv.Sphere(radius=radius, center=p,
                    theta_resolution=export_resolution, phi_resolution=export_resolution))

            if self.show_lattice:
                base = meshes
                meshes = []
                for k in range(self.lattice_c):
                    for i in range(self.lattice_a):
                        for j in range(self.lattice_b):
                            off = np.array([i*cell_size, j*cell_size, k*cell_size])
                            for m in base:
                                mc = m.copy()
                                mc.translate(off, inplace=True)
                                meshes.append(mc)

            if not meshes:
                return False
            combined = meshes[0].merge(meshes[1:]) if len(meshes) > 1 else meshes[0]
            if not filepath.lower().endswith('.stl'):
                filepath += '.stl'
            combined.save(filepath)
            print(f"STL已保存: {filepath}")
            return True
        except Exception as e:
            print(f"保存STL失败: {e}")
            return False
