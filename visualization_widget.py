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
from config import Config

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

# Manifold3D for watertight boolean union
try:
    import manifold3d
    MANIFOLD3D_AVAILABLE = True
except ImportError:
    MANIFOLD3D_AVAILABLE = False


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
        self.lattice_a = 1  # X方向晶胞数量
        self.lattice_b = 1  # Y方向晶胞数量
        self.lattice_c = 1  # Z方向晶胞数量

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

    def _build_manifold_mesh(self, display_points, connections, radius, cell_size, segments=12):
        """用 manifold3d 原语构建水密 mesh (单 cell 或 lattice)，返回 PyVista PolyData。"""
        print(f"[Solid.build] ENTER: la={self.lattice_a} lb={self.lattice_b} lc={self.lattice_c}, cs={cell_size}")
        sphere_r = radius * Config.SPHERE_RADIUS_RATIO_PREVIEW

        # 构建单个 unit cell 的 manifold3d parts
        base_parts = []
        for conn in connections:
            strut = self._build_manifold_strut(
                display_points[conn[0]], display_points[conn[1]], radius, segments)
            if strut is not None:
                base_parts.append(strut)
        # 坐标去重：Auxetic 等存在同位置异名点，避免重合球产生 union 伪影
        unique_pts = np.unique(np.round(np.asarray(display_points), 6), axis=0)
        for pt in unique_pts:
            sph = manifold3d.Manifold.sphere(float(sphere_r), segments)
            sph = sph.translate([float(pt[0]), float(pt[1]), float(pt[2])])
            base_parts.append(sph)

        if not base_parts:
            return None

        # Lattice 阵列: 复制 + 平移 (display 坐标系 Y/Z 已交换)
        la, lb, lc = self.lattice_a, self.lattice_b, self.lattice_c
        if la > 1 or lb > 1 or lc > 1:
            parts = []
            for k in range(lc):
                for i in range(la):
                    for j in range(lb):
                        off = [float(i * cell_size), float(k * cell_size), float(j * cell_size)]
                        for bp in base_parts:
                            parts.append(bp.translate(off))
        else:
            parts = base_parts

        result = self._batch_union(parts)
        if result is None or result.num_tri() == 0:
            return None

        return self._manifold_to_pv(result)

    @staticmethod
    def _build_manifold_strut(p0, p1, radius, segments=12):
        """用 manifold3d 原语创建一根从 p0 到 p1 的圆柱 (水密)。"""
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            return None
        d_unit = d / L

        cyl = manifold3d.Manifold.cylinder(L, float(radius), float(radius), segments)

        # 旋转: Z轴 -> d_unit
        z = np.array([0.0, 0.0, 1.0])
        cross_v = np.cross(z, d_unit)
        dot_v = float(np.dot(z, d_unit))

        if np.linalg.norm(cross_v) < 1e-8:
            rot = np.eye(3) if dot_v > 0 else np.diag([1.0, -1.0, -1.0])
        else:
            cross_n = cross_v / np.linalg.norm(cross_v)
            angle = np.arccos(np.clip(dot_v, -1, 1))
            K = np.array([
                [0, -cross_n[2], cross_n[1]],
                [cross_n[2], 0, -cross_n[0]],
                [-cross_n[1], cross_n[0], 0]
            ])
            rot = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K

        # manifold3d transform: 3x4 矩阵 [R | t]
        mat = [[rot[0][0], rot[0][1], rot[0][2], float(p0[0])],
               [rot[1][0], rot[1][1], rot[1][2], float(p0[1])],
               [rot[2][0], rot[2][1], rot[2][2], float(p0[2])]]
        return cyl.transform(mat)

    @staticmethod
    def _manifold_to_pv(manifold_obj):
        """manifold3d Manifold -> PyVista PolyData"""
        out = manifold_obj.to_mesh()
        verts = np.array(out.vert_properties[:, :3])
        faces = np.array(out.tri_verts, dtype=np.int32)
        n = len(faces)
        pv_faces = np.column_stack([np.full(n, 3, dtype=np.int32), faces]).ravel()
        return pv.PolyData(verts, pv_faces)


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

        # Lattice模式(solid)下降低精度以提升性能
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

        # Always get structure data (needed for both wireframe and solid modes)
        points, connections = self.get_cell_structure(cell_type, slider_value)

        # 保存节点数和杆件数用于统计显示
        self.current_nodes_count = len(points)
        self.current_struts_count = len(connections)

        # 根据cell_size缩放坐标点
        default_cell_size = 5.0
        scale_factor = cell_size / default_cell_size
        scaled_points = points * scale_factor

        # Swap Y and Z coordinates for display (to match previous behavior)
        display_points = scaled_points.copy()
        display_points[:, [1, 2]] = display_points[:, [2, 1]]  # Swap Y and Z columns

        combined_mesh = None  # Solid mode sets this; wireframe adds directly to plotter

        # ========== Wireframe mode (show_lattice = False): 点+线段，极快 ==========
        if not self.show_lattice:
            all_pts = []   # flat list of [x,y,z]
            all_lines = [] # VTK line connectivity: [2, i0, i1, 2, i2, i3, ...]
            pt_idx = 0

            for ix in range(self.lattice_a):
                for iy in range(self.lattice_b):
                    for iz in range(self.lattice_c):
                        offset = np.array([ix * cell_size, iz * cell_size, iy * cell_size])

                        for conn in connections:
                            start = display_points[conn[0]] + offset
                            end = display_points[conn[1]] + offset
                            all_pts.append(start)
                            all_pts.append(end)
                            all_lines.extend([2, pt_idx, pt_idx + 1])
                            pt_idx += 2

            if all_pts:
                pts_array = np.array(all_pts)
                lines_array = np.array(all_lines)
                wire_mesh = pv.PolyData(pts_array, lines=lines_array)

                self.plotter.add_mesh(
                    wire_mesh,
                    color='#d0d0e0',
                    line_width=4,
                    opacity=0.9,
                    render_lines_as_tubes=True,
                )
                # 节点球
                # 去重节点坐标后画点
                unique_pts = np.unique(pts_array, axis=0)
                node_cloud = pv.PolyData(unique_pts)
                self.plotter.add_mesh(
                    node_cloud,
                    color='#8ecae6',
                    point_size=10,
                    render_points_as_spheres=True,
                )
                print(f"[Wire] {self.lattice_a}x{self.lattice_b}x{self.lattice_c}: {pt_idx // 2} lines, {len(unique_pts)} nodes")

        # ========== Solid mode: manifold3d primitives → union → render ==========
        else:
            combined_mesh = None

            if MANIFOLD3D_AVAILABLE:
                try:
                    combined_mesh = self._build_manifold_mesh(
                        display_points, connections, radius, cell_size, resolution)
                except Exception as e:
                    import traceback
                    print(f"[Solid] manifold3d failed: {e}")
                    traceback.print_exc()
                    combined_mesh = None

            # fallback: PyVista merge (非水密，仅预览) —— 必须遵守 lattice
            if combined_mesh is None:
                sphere_radius = radius * Config.SPHERE_RADIUS_RATIO_PREVIEW
                all_meshes = []
                for ix in range(self.lattice_a):
                    for iy in range(self.lattice_b):
                        for iz in range(self.lattice_c):
                            # 与 wireframe/manifold3d 一致: display-X=a(ix), display-Y=c(iz), display-Z=b(iy)
                            offset = np.array([ix * cell_size, iz * cell_size, iy * cell_size])
                            for connection in connections:
                                start = display_points[connection[0]] + offset
                                end = display_points[connection[1]] + offset
                                d = end - start
                                L = np.linalg.norm(d)
                                if L > 1e-6:
                                    all_meshes.append(pv.Cylinder(
                                        center=(start + end) / 2,
                                        direction=d / L, radius=radius, height=L, resolution=resolution))
                            for pt in display_points:
                                all_meshes.append(pv.Sphere(
                                    radius=sphere_radius, center=pt + offset,
                                    theta_resolution=resolution, phi_resolution=resolution))
                if all_meshes:
                    combined_mesh = all_meshes[0].merge(all_meshes[1:])

            if combined_mesh is not None and combined_mesh.n_points > 0:
                combined_mesh = combined_mesh.compute_normals(cell_normals=False, point_normals=True)

        # 渲染solid mesh（仅在solid模式下）
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

            # 计算网格位置和大小 - display坐标Y/Z已交换
            # display-X = a, display-Y = c, display-Z = b
            grid_center_x = cell_size * (self.lattice_a - 1) / 2.0
            grid_center_y = cell_size * (self.lattice_c - 1) / 2.0  # display-Y = c方向
            grid_size = cell_size * max(self.lattice_a, self.lattice_c)  # XY平面覆盖

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

                # 计算晶胞中心位置 - display坐标Y/Z已交换
                # display-X = a, display-Y = c, display-Z = b
                new_focal_point = [
                    cell_size * (self.lattice_a - 1) / 2.0,
                    cell_size * (self.lattice_c - 1) / 2.0,  # display-Y = c
                    cell_size * (self.lattice_b - 1) / 2.0   # display-Z = b
                ]

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
            cell_size = self.current_cell_size
            radius = getattr(self, 'current_radius', 0.3)
            slider_value = getattr(self, 'current_slider_value', 0)

            points, connections = self.get_cell_structure(self.current_cell_type, slider_value)
            points = points * (cell_size / 5.0)
            display_points = points.copy()
            display_points[:, [1, 2]] = display_points[:, [2, 1]]

            combined_mesh = self._build_manifold_mesh(
                display_points, connections, radius, cell_size, export_resolution)
            if combined_mesh is None:
                print("Blend export: mesh generation failed")
                return False
            combined_mesh = combined_mesh.compute_normals(cell_normals=False, point_normals=True)
            print(f"[Blend Export] watertight mesh: {combined_mesh.n_points} verts, {combined_mesh.n_cells} faces")

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

    @staticmethod
    def _batch_union(parts):
        """二叉树分治 union — O(n log n)，比顺序 union O(n^2) 快得多。"""
        if not parts:
            return None
        while len(parts) > 1:
            merged = []
            for i in range(0, len(parts), 2):
                if i + 1 < len(parts):
                    merged.append(parts[i] + parts[i + 1])
                else:
                    merged.append(parts[i])
            parts = merged
        return parts[0]

    def save_stl(self, filepath, export_resolution=48):
        """保存当前晶格结构为水密 STL (manifold3d 原语直接构建，不经过 PyVista)"""
        if self.current_cell_type is None:
            return False

        try:
            if not MANIFOLD3D_AVAILABLE:
                raise RuntimeError("manifold3d 未安装，无法生成水密 STL")

            import time
            t0 = time.time()

            cell_size = self.current_cell_size
            radius = getattr(self, 'current_radius', 0.3)
            slider_value = getattr(self, 'current_slider_value', 0)
            sphere_r = radius * Config.SPHERE_RADIUS_RATIO_PREVIEW
            seg = export_resolution

            points, connections = self.get_cell_structure(self.current_cell_type, slider_value)
            points = points * (cell_size / 5.0)
            points[:, [1, 2]] = points[:, [2, 1]]  # Y/Z swap

            # 用 manifold3d 原语构建
            parts = []
            for conn in connections:
                strut = self._build_manifold_strut(points[conn[0]], points[conn[1]], radius, seg)
                if strut is not None:
                    parts.append(strut)
            # 坐标去重：Auxetic 等结构存在命名不同但坐标相同的点
            # (T_TL/F_TL 等 8 对)，若不去重会产生重合球导致 union 退化伪影
            unique_pts = np.unique(np.round(points, 6), axis=0)
            for pt in unique_pts:
                sph = manifold3d.Manifold.sphere(float(sphere_r), seg)
                sph = sph.translate([float(pt[0]), float(pt[1]), float(pt[2])])
                parts.append(sph)

            # Lattice 阵列：spinners (a/b/c) 决定是否展开，与 Render（show_lattice）无关
            if self.lattice_a > 1 or self.lattice_b > 1 or self.lattice_c > 1:
                base = parts
                parts = []
                for k in range(self.lattice_c):
                    for i in range(self.lattice_a):
                        for j in range(self.lattice_b):
                            off = [float(i * cell_size), float(k * cell_size), float(j * cell_size)]
                            for bp in base:
                                parts.append(bp.translate(off))

            if not parts:
                return False

            # 二叉树 union（比顺序快）
            result = self._batch_union(parts)

            if result is None or result.num_tri() == 0:
                raise RuntimeError("manifold3d union 结果为空")

            # 保存
            if not filepath.lower().endswith('.stl'):
                filepath += '.stl'

            pv_mesh = self._manifold_to_pv(result)
            pv_mesh.save(filepath)

            dt = time.time() - t0
            print(f"STL saved (watertight): {filepath} | {result.num_vert()} verts, {result.num_tri()} faces, {dt:.2f}s")
            return True

        except Exception as e:
            print(f"STL export failed: {e}")
            import traceback; traceback.print_exc()
            return False
