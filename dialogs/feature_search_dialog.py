#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual-feature 搜索可视化对话框（4 个子图）
从 qt_interface.py 拆出，保持行为不变。
"""

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial.distance import cdist

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget,
)
from PyQt5.QtCore import Qt


class FeatureSearchDialog(QDialog):
    """Dialog for dual-feature search visualization with 4 plots"""

    def __init__(self, parent, df, feature1, value1, feature2, value2):
        super().__init__(parent)
        # 无边框窗口（去掉标题栏的 - □ × 按钮，因为已有 Close 按钮）
        from PyQt5.QtCore import Qt
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(1400, 900)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1d29, stop:1 #0f1419);
                border: 2px solid #3d5a80;
                border-radius: 12px;
            }
            QTabWidget::pane {
                border: 2px solid #3d5a80;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #262b3d, stop:1 #1e2330);
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #262b3d;
                color: #c5d1de;
                padding: 12px 24px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a7ba7, stop:1 #3d5a80);
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2d3548;
            }
            QLabel {
                color: #c5d1de;
                font-size: 13px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a7ba7, stop:1 #3d5a80);
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5a8bc0, stop:1 #4a7ba7);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3d5a80, stop:1 #2d4660);
            }
        """)

        self.df = df
        self.f1 = feature1
        self.v1 = value1
        self.f2 = feature2
        self.v2 = value2
        self.best_samples = []

        # Find nearest family
        self.nearest_family = self._find_nearest_family()
        self.nearest_families_3 = self._find_nearest_families_k(3)

        self._setup_ui()
        self._generate_plots()

    def _find_nearest_family(self):
        """Find the single nearest cell_type family"""
        df = self.df.copy()

        # Normalize features
        f1_min, f1_max = df[self.f1].min(), df[self.f1].max()
        f2_min, f2_max = df[self.f2].min(), df[self.f2].max()

        if f1_max - f1_min > 0:
            df['norm_f1'] = (df[self.f1] - f1_min) / (f1_max - f1_min)
            target_norm1 = (self.v1 - f1_min) / (f1_max - f1_min)
        else:
            df['norm_f1'] = 0
            target_norm1 = 0

        if f2_max - f2_min > 0:
            df['norm_f2'] = (df[self.f2] - f2_min) / (f2_max - f2_min)
            target_norm2 = (self.v2 - f2_min) / (f2_max - f2_min)
        else:
            df['norm_f2'] = 0
            target_norm2 = 0

        df['distance'] = np.sqrt(
            (df['norm_f1'] - target_norm1)**2 +
            (df['norm_f2'] - target_norm2)**2
        )

        closest = df.nsmallest(1, 'distance').iloc[0]
        return closest['cell_type']

    def _find_nearest_families_k(self, k=3):
        """Find k nearest cell_type families"""
        df = self.df.copy()

        f1_min, f1_max = df[self.f1].min(), df[self.f1].max()
        f2_min, f2_max = df[self.f2].min(), df[self.f2].max()

        if f1_max - f1_min > 0:
            df['norm_f1'] = (df[self.f1] - f1_min) / (f1_max - f1_min)
            target_norm1 = (self.v1 - f1_min) / (f1_max - f1_min)
        else:
            df['norm_f1'] = 0
            target_norm1 = 0

        if f2_max - f2_min > 0:
            df['norm_f2'] = (df[self.f2] - f2_min) / (f2_max - f2_min)
            target_norm2 = (self.v2 - f2_min) / (f2_max - f2_min)
        else:
            df['norm_f2'] = 0
            target_norm2 = 0

        df['distance'] = np.sqrt(
            (df['norm_f1'] - target_norm1)**2 +
            (df['norm_f2'] - target_norm2)**2
        )

        selected = {}
        excluded = set()
        for _ in range(k):
            remaining = df[~df['cell_type'].isin(excluded)]
            if len(remaining) == 0:
                break
            closest = remaining.nsmallest(1, 'distance').iloc[0]
            cell_type = closest['cell_type']
            selected[cell_type] = df[df['cell_type'] == cell_type].copy()
            excluded.add(cell_type)

        return selected

    def _setup_ui(self):
        """Setup the dialog UI with tabs for each plot"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Info label
        f1_display = self.f1.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()
        f2_display = self.f2.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()
        info_label = QLabel(f"Searching: {f1_display} = {self.v1:.4g}, {f2_display} = {self.v2:.4g}  |  Nearest Family: {self.nearest_family}")
        info_label.setStyleSheet("font-size: 14px; color: #e1e8f0; padding: 10px;")
        layout.addWidget(info_label)

        # Tab widget for plots
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs for each plot
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()

        self.tab_widget.addTab(self.tab1, "2D Feature Space")
        self.tab_widget.addTab(self.tab2, f"{f1_display} 3D Surface")
        self.tab_widget.addTab(self.tab3, f"{f2_display} 3D Surface")
        self.tab_widget.addTab(self.tab4, "2D Intersection")

        # Setup matplotlib canvas for each tab
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        # Tab 1: 2D Feature Space
        layout1 = QVBoxLayout(self.tab1)
        self.fig1 = Figure(figsize=(12, 8), facecolor='#1e2330')
        self.canvas1 = FigureCanvas(self.fig1)
        layout1.addWidget(self.canvas1)

        # Tab 2: 3D Surface for Feature 1
        layout2 = QVBoxLayout(self.tab2)
        self.fig2 = Figure(figsize=(10, 8), facecolor='#1e2330')
        self.canvas2 = FigureCanvas(self.fig2)
        layout2.addWidget(self.canvas2)

        # Tab 3: 3D Surface for Feature 2
        layout3 = QVBoxLayout(self.tab3)
        self.fig3 = Figure(figsize=(10, 8), facecolor='#1e2330')
        self.canvas3 = FigureCanvas(self.fig3)
        layout3.addWidget(self.canvas3)

        # Tab 4: 2D Intersection
        layout4 = QVBoxLayout(self.tab4)
        self.fig4 = Figure(figsize=(10, 8), facecolor='#1e2330')
        self.canvas4 = FigureCanvas(self.fig4)
        layout4.addWidget(self.canvas4)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d5a80;
                color: #e1e8f0;
                border: none;
                border-radius: 6px;
                padding: 10px 30px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a6fa5;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _generate_plots(self):
        """Generate all 4 plots"""
        self._plot_2d_feature_space()
        self._plot_3d_surface(self.fig2, self.f1, self.v1)
        self._plot_3d_surface(self.fig3, self.f2, self.v2)
        self._plot_2d_intersection()

        # Refresh all canvases
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()
        self.canvas4.draw()

    def _plot_2d_feature_space(self):
        """Plot 1: 2D Feature Space with all samples and nearest families"""
        ax = self.fig1.add_subplot(111)
        ax.set_facecolor('#1e2330')

        # Plot all samples (gray)
        ax.scatter(self.df[self.f1], self.df[self.f2], c='gray', alpha=0.3, s=30, label='Other materials')

        # Plot nearest 3 families (colored)
        colors = ['#4a90d9', '#50c878', '#9370db']  # Blue, Green, Purple
        for i, (cell_type, df_family) in enumerate(self.nearest_families_3.items()):
            ax.scatter(df_family[self.f1], df_family[self.f2], c=colors[i % len(colors)],
                      s=60, alpha=0.8, label=f'{cell_type} ({len(df_family)} samples)')

        # Plot target point (red X)
        ax.scatter([self.v1], [self.v2], marker='X', c='red', s=300, linewidths=3,
                  edgecolors='white', label='Target', zorder=10)

        # Style
        f1_display = self.f1.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()
        f2_display = self.f2.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()

        ax.set_xlabel(f1_display, color='#c5d1de', fontsize=12)
        ax.set_ylabel(f2_display, color='#c5d1de', fontsize=12)
        ax.set_title(f'2D Feature Space: {f1_display} vs {f2_display}', color='#e1e8f0', fontsize=14, fontweight='bold')
        ax.tick_params(colors='#c5d1de')
        ax.spines['bottom'].set_color('#3d5a80')
        ax.spines['top'].set_color('#3d5a80')
        ax.spines['left'].set_color('#3d5a80')
        ax.spines['right'].set_color('#3d5a80')
        ax.legend(facecolor='#262b3d', edgecolor='#3d5a80', labelcolor='#c5d1de', fontsize=10)
        ax.grid(True, alpha=0.2, color='#3d5a80')

        self.fig1.tight_layout()

    def _is_1d_structure(self, cell_type):
        """Check if cell type only has radius dimension (no transform)"""
        return cell_type in ['Cubic', 'Octahedron']

    def _plot_3d_surface(self, fig, feature, target_value):
        """Plot 3D surface for a single feature with target plane intersection"""
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D

        # Check if this is a 1D structure (only radius dimension)
        if self._is_1d_structure(self.nearest_family):
            self._plot_2d_curve(fig, feature, target_value)
            return

        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor('#1e2330')

        # Get family data
        df_family = self.df[self.df['cell_type'] == self.nearest_family].copy()

        if len(df_family) < 3:
            ax.text(0.5, 0.5, 0.5, 'Insufficient data', ha='center', va='center',
                   transform=ax.transAxes, color='#c5d1de', fontsize=14)
            return

        # Create grid
        radius_min, radius_max = df_family['strut_radius'].min(), df_family['strut_radius'].max()
        slider_min, slider_max = df_family['transform'].min(), df_family['transform'].max()

        radius_range = np.linspace(radius_min, radius_max, 50)
        slider_range = np.linspace(slider_min, slider_max, 50)
        R, S = np.meshgrid(radius_range, slider_range)

        # Interpolate - 使用 RBF + 高斯平滑获得更平滑的曲面
        points = df_family[['transform', 'strut_radius']].values
        values = df_family[feature].values

        try:
            from scipy.interpolate import RBFInterpolator
            from scipy.ndimage import gaussian_filter

            # 使用 RBF 插值 - thin_plate_spline 产生平滑曲面
            rbf = RBFInterpolator(points, values, kernel='thin_plate_spline', smoothing=1.0)
            grid_points = np.column_stack([S.ravel(), R.ravel()])
            Z = rbf(grid_points).reshape(R.shape)

            # 高斯平滑
            nan_mask = np.isnan(Z)
            if not np.all(nan_mask):
                Z_filled = np.where(nan_mask, np.nanmean(Z), Z)
                Z_smooth = gaussian_filter(Z_filled, sigma=1.5)
                Z = np.where(nan_mask, np.nan, Z_smooth)
        except Exception:
            # 回退到 LinearNDInterpolator
            try:
                interpolator = LinearNDInterpolator(points, values, rescale=True)
                Z = np.zeros_like(R)
                for i in range(R.shape[0]):
                    for j in range(R.shape[1]):
                        Z[i, j] = interpolator(S[i, j], R[i, j])
            except Exception as e:
                ax.text(0.5, 0.5, 0.5, f'Interpolation error: {e}', ha='center', va='center',
                       transform=ax.transAxes, color='#c5d1de', fontsize=10)
                return

        # Plot surface
        ax.plot_surface(R, S, Z, cmap='viridis', alpha=0.6, linewidth=0, antialiased=True)

        # Plot data points
        ax.scatter(df_family['strut_radius'], df_family['transform'], df_family[feature],
                  c='black', s=15, alpha=0.5)

        # Plot target plane
        R_plane, S_plane = np.meshgrid([radius_min, radius_max], [slider_min, slider_max])
        Z_target = np.full_like(R_plane, target_value)
        ax.plot_surface(R_plane, S_plane, Z_target, color='darkred', alpha=0.2)

        # Extract and plot intersection contour
        try:
            import matplotlib.pyplot as plt
            temp_fig, temp_ax = plt.subplots()
            contour_set = temp_ax.contour(R, S, Z, levels=[target_value])

            z_min = np.nanmin(Z[~np.isnan(Z)]) if np.any(~np.isnan(Z)) else 0

            for seg in contour_set.allsegs[0]:
                if len(seg) > 0:
                    # Draw contour on surface
                    z_contour = np.full(len(seg), target_value)
                    ax.plot(seg[:, 0], seg[:, 1], z_contour, 'r-', linewidth=3, alpha=0.8)
                    # Project to XY plane
                    z_bottom = np.full(len(seg), z_min)
                    ax.plot(seg[:, 0], seg[:, 1], z_bottom, 'r--', linewidth=2, alpha=0.6)

            plt.close(temp_fig)
        except Exception as e:
            print(f"Contour extraction error: {e}")

        # Labels
        feat_display = feature.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()
        ax.set_xlabel('Strut Radius (mm)', color='#c5d1de', fontsize=10, labelpad=10)
        ax.set_ylabel('Transform', color='#c5d1de', fontsize=10, labelpad=10)
        ax.set_zlabel(feat_display, color='#c5d1de', fontsize=10, labelpad=10)
        ax.set_title(f'{self.nearest_family} - {feat_display} Surface', color='#e1e8f0', fontsize=12)

        # Legend
        legend_elements = [
            Patch(facecolor='purple', alpha=0.6, label='Complete surface'),
            Patch(facecolor='darkred', alpha=0.2, label=f'Target: {target_value:.4g}'),
            Line2D([0], [0], color='red', linewidth=3, label='Surface-Target intersection'),
            Line2D([0], [0], color='red', linewidth=2, linestyle='--', label='Intersection projection'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='black', markersize=5, alpha=0.5, label='Data points')
        ]
        ax.legend(handles=legend_elements, fontsize=8, loc='upper left',
                 facecolor='#262b3d', edgecolor='#3d5a80', labelcolor='#c5d1de')

        ax.view_init(elev=25, azim=45)
        ax.tick_params(colors='#c5d1de')

        fig.tight_layout()

    def _plot_2d_curve(self, fig, feature, target_value):
        """Plot 2D curve for 1D structures (Cubic, Octahedron) - only radius dimension"""
        from scipy.interpolate import interp1d
        from matplotlib.lines import Line2D

        ax = fig.add_subplot(111)
        ax.set_facecolor('#1e2330')

        # Get family data
        df_family = self.df[self.df['cell_type'] == self.nearest_family].copy()

        if len(df_family) < 2:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center',
                   transform=ax.transAxes, color='#c5d1de', fontsize=14)
            return

        # Sort by radius
        df_family = df_family.sort_values('strut_radius')
        radius = df_family['strut_radius'].values
        values = df_family[feature].values

        # Interpolate 1D curve - 使用更多点和平滑处理
        from scipy.ndimage import gaussian_filter1d
        radius_fine = np.linspace(radius.min(), radius.max(), 200)
        try:
            interp_func = interp1d(radius, values, kind='cubic', fill_value='extrapolate')
            values_fine = interp_func(radius_fine)
            # 高斯平滑
            values_fine = gaussian_filter1d(values_fine, sigma=2)
        except:
            interp_func = interp1d(radius, values, kind='linear', fill_value='extrapolate')
            values_fine = interp_func(radius_fine)

        # Plot curve
        ax.plot(radius_fine, values_fine, 'b-', linewidth=2, label=f'{feature} curve')
        ax.scatter(radius, values, c='black', s=50, zorder=5, label='Data points')

        # Plot target line and find intersection
        ax.axhline(y=target_value, color='red', linestyle='--', linewidth=2, label=f'Target: {target_value:.4g}')

        # Find intersection point
        intersections = []
        for i in range(len(values_fine) - 1):
            if (values_fine[i] - target_value) * (values_fine[i+1] - target_value) <= 0:
                # Linear interpolation to find exact crossing
                t = (target_value - values_fine[i]) / (values_fine[i+1] - values_fine[i])
                r_intersect = radius_fine[i] + t * (radius_fine[i+1] - radius_fine[i])
                intersections.append(r_intersect)

        for r_int in intersections:
            ax.scatter([r_int], [target_value], marker='o', s=200, c='red',
                      edgecolors='white', linewidths=2, zorder=10)
            ax.annotate(f'R={r_int:.3f}', (r_int, target_value),
                       textcoords='offset points', xytext=(10, 10),
                       color='#e1e8f0', fontsize=10,
                       arrowprops=dict(arrowstyle='->', color='#c5d1de'))

        # Store intersection for later use
        if intersections:
            self._1d_intersections = {feature: intersections}

        # Labels
        feat_display = feature.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()
        ax.set_xlabel('Strut Radius (mm)', color='#c5d1de', fontsize=12)
        ax.set_ylabel(feat_display, color='#c5d1de', fontsize=12)
        ax.set_title(f'{self.nearest_family} - {feat_display} vs Radius (1D Structure)', color='#e1e8f0', fontsize=12)
        ax.tick_params(colors='#c5d1de')
        ax.legend(facecolor='#262b3d', edgecolor='#3d5a80', labelcolor='#c5d1de', fontsize=10)
        ax.grid(True, alpha=0.2, color='#3d5a80')
        ax.spines['bottom'].set_color('#3d5a80')
        ax.spines['top'].set_color('#3d5a80')
        ax.spines['left'].set_color('#3d5a80')
        ax.spines['right'].set_color('#3d5a80')

        fig.tight_layout()

    def _plot_2d_intersection(self):
        """Plot 4: 2D Feature Intersection Analysis"""
        # Check if this is a 1D structure
        if self._is_1d_structure(self.nearest_family):
            self._plot_1d_intersection()
            return

        ax = self.fig4.add_subplot(111)
        ax.set_facecolor('#1e2330')

        # Get family data
        df_family = self.df[self.df['cell_type'] == self.nearest_family].copy()

        if len(df_family) < 3:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center',
                   transform=ax.transAxes, color='#c5d1de', fontsize=14)
            return

        # Create grid
        radius_min, radius_max = df_family['strut_radius'].min(), df_family['strut_radius'].max()
        slider_min, slider_max = df_family['transform'].min(), df_family['transform'].max()

        # Expand by 10%
        r_range = radius_max - radius_min
        s_range = slider_max - slider_min
        radius_min -= r_range * 0.1
        radius_max += r_range * 0.1
        slider_min -= s_range * 0.1
        slider_max += s_range * 0.1

        radius_grid = np.linspace(radius_min, radius_max, 50)
        slider_grid = np.linspace(slider_min, slider_max, 50)
        R, S = np.meshgrid(radius_grid, slider_grid)

        points = df_family[['transform', 'strut_radius']].values

        # Interpolate both features - 使用 RBF + 高斯平滑
        try:
            from scipy.interpolate import RBFInterpolator
            from scipy.ndimage import gaussian_filter

            # RBF 插值
            rbf1 = RBFInterpolator(points, df_family[self.f1].values, kernel='thin_plate_spline', smoothing=1.0)
            rbf2 = RBFInterpolator(points, df_family[self.f2].values, kernel='thin_plate_spline', smoothing=1.0)

            grid_points = np.column_stack([S.ravel(), R.ravel()])
            Z1 = rbf1(grid_points).reshape(R.shape)
            Z2 = rbf2(grid_points).reshape(R.shape)

            # 高斯平滑
            for Z in [Z1, Z2]:
                nan_mask = np.isnan(Z)
                if not np.all(nan_mask):
                    Z_filled = np.where(nan_mask, np.nanmean(Z), Z)
                    Z_smooth = gaussian_filter(Z_filled, sigma=1.5)
                    Z[:] = np.where(nan_mask, np.nan, Z_smooth)

            # 保存插值器供后续使用（标记为RBF类型）
            interp1 = rbf1
            interp2 = rbf2
            use_rbf = True
        except Exception:
            use_rbf = False
            # 回退到 LinearNDInterpolator
            try:
                interp1 = LinearNDInterpolator(points, df_family[self.f1].values, rescale=True)
                interp2 = LinearNDInterpolator(points, df_family[self.f2].values, rescale=True)
                Z1 = np.zeros_like(R)
                Z2 = np.zeros_like(R)
                for i in range(R.shape[0]):
                    for j in range(R.shape[1]):
                        Z1[i, j] = interp1(S[i, j], R[i, j])
                        Z2[i, j] = interp2(S[i, j], R[i, j])
            except Exception as e:
                ax.text(0.5, 0.5, f'Interpolation error: {e}', ha='center', va='center',
                       transform=ax.transAxes, color='#c5d1de', fontsize=10)
                return

        # Plot contours
        f1_display = self.f1.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()
        f2_display = self.f2.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()

        contour1 = ax.contour(R, S, Z1, levels=[self.v1], colors=['blue'], linewidths=2.5)
        contour2 = ax.contour(R, S, Z2, levels=[self.v2], colors=['red'], linewidths=2.5)

        # Add labels for legend
        ax.plot([], [], color='blue', linewidth=2.5, label=f1_display)
        ax.plot([], [], color='red', linewidth=2.5, label=f2_display)

        # Find intersection point
        optimal_radius, optimal_slider = self._find_contour_intersection(contour1, contour2)
        is_approximation = False

        if optimal_radius is not None:
            ax.scatter([optimal_radius], [optimal_slider], marker='o', s=200, c='black',
                      edgecolors='white', linewidths=2, zorder=10,
                      label=f'Intersection: R={optimal_radius:.3f}, S={optimal_slider:.1f}')
        else:
            # 没有找到交点，寻找最接近目标值的点
            is_approximation = True
            # 计算每个网格点到两个目标值的归一化距离
            f1_range = np.nanmax(Z1) - np.nanmin(Z1)
            f2_range = np.nanmax(Z2) - np.nanmin(Z2)
            if f1_range > 0 and f2_range > 0:
                norm_dist1 = (Z1 - self.v1) / f1_range
                norm_dist2 = (Z2 - self.v2) / f2_range
                combined_dist = np.sqrt(norm_dist1**2 + norm_dist2**2)
                # 找最小距离点
                valid_mask = ~np.isnan(combined_dist)
                if np.any(valid_mask):
                    min_idx = np.unravel_index(np.nanargmin(combined_dist), combined_dist.shape)
                    optimal_slider = S[min_idx]
                    optimal_radius = R[min_idx]
                    ax.scatter([optimal_radius], [optimal_slider], marker='s', s=200, c='orange',
                              edgecolors='white', linewidths=2, zorder=10,
                              label=f'Closest: R={optimal_radius:.3f}, S={optimal_slider:.1f}')

        if optimal_radius is not None:
            # Store best sample info - 根据插值器类型调用
            if use_rbf:
                pred_f1 = interp1([[optimal_slider, optimal_radius]])[0]
                pred_f2 = interp2([[optimal_slider, optimal_radius]])[0]
            else:
                pred_f1 = interp1(optimal_slider, optimal_radius)
                pred_f2 = interp2(optimal_slider, optimal_radius)

            self.best_samples = [{
                'sample_name': f'{self.nearest_family}_5_{optimal_radius:.3f}_{optimal_slider:.1f}'.replace('.', 'p'),
                'cell_type': self.nearest_family,
                'radius': optimal_radius,
                'slider': optimal_slider,
                'predicted_f1': pred_f1,
                'predicted_f2': pred_f2,
                'is_approximation': is_approximation
            }]

        # Plot data points
        ax.scatter(df_family['strut_radius'], df_family['transform'], c='gray', s=30, alpha=0.3, zorder=1)

        # Style
        ax.set_xlabel('Strut Radius (mm)', color='#c5d1de', fontsize=12, fontweight='bold')
        ax.set_ylabel('Transform', color='#c5d1de', fontsize=12, fontweight='bold')
        ax.set_title(f'{self.nearest_family} - 2D Feature Intersection Analysis', color='#e1e8f0', fontsize=14, fontweight='bold')
        ax.tick_params(colors='#c5d1de')
        ax.spines['bottom'].set_color('#3d5a80')
        ax.spines['top'].set_color('#3d5a80')
        ax.spines['left'].set_color('#3d5a80')
        ax.spines['right'].set_color('#3d5a80')
        ax.legend(facecolor='#262b3d', edgecolor='#3d5a80', labelcolor='#c5d1de', fontsize=10)
        ax.grid(True, alpha=0.3, color='#3d5a80')

        self.fig4.tight_layout()

    def _plot_1d_intersection(self):
        """Plot intersection for 1D structures (Cubic, Octahedron) - find closest radius from two feature curves"""
        from scipy.interpolate import interp1d

        ax = self.fig4.add_subplot(111)
        ax.set_facecolor('#1e2330')

        # Get family data
        df_family = self.df[self.df['cell_type'] == self.nearest_family].copy()

        if len(df_family) < 2:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center',
                   transform=ax.transAxes, color='#c5d1de', fontsize=14)
            return

        # Sort by radius
        df_family = df_family.sort_values('strut_radius')
        radius = df_family['strut_radius'].values
        values1 = df_family[self.f1].values
        values2 = df_family[self.f2].values

        # Create fine radius grid
        radius_fine = np.linspace(radius.min(), radius.max(), 200)

        # Interpolate both features - 使用高斯平滑
        from scipy.ndimage import gaussian_filter1d
        try:
            interp_f1 = interp1d(radius, values1, kind='cubic', fill_value='extrapolate')
            interp_f2 = interp1d(radius, values2, kind='cubic', fill_value='extrapolate')
            values1_fine = gaussian_filter1d(interp_f1(radius_fine), sigma=2)
            values2_fine = gaussian_filter1d(interp_f2(radius_fine), sigma=2)
        except:
            interp_f1 = interp1d(radius, values1, kind='linear', fill_value='extrapolate')
            interp_f2 = interp1d(radius, values2, kind='linear', fill_value='extrapolate')
            values1_fine = interp_f1(radius_fine)
            values2_fine = interp_f2(radius_fine)

        # Find intersections with target values
        intersections_f1 = []
        intersections_f2 = []

        for i in range(len(values1_fine) - 1):
            if (values1_fine[i] - self.v1) * (values1_fine[i+1] - self.v1) <= 0:
                t = (self.v1 - values1_fine[i]) / (values1_fine[i+1] - values1_fine[i] + 1e-10)
                r_intersect = radius_fine[i] + t * (radius_fine[i+1] - radius_fine[i])
                intersections_f1.append(r_intersect)

        for i in range(len(values2_fine) - 1):
            if (values2_fine[i] - self.v2) * (values2_fine[i+1] - self.v2) <= 0:
                t = (self.v2 - values2_fine[i]) / (values2_fine[i+1] - values2_fine[i] + 1e-10)
                r_intersect = radius_fine[i] + t * (radius_fine[i+1] - radius_fine[i])
                intersections_f2.append(r_intersect)

        # Plot curves (normalized for comparison)
        # Normalize to 0-1 range for visualization
        v1_min, v1_max = values1_fine.min(), values1_fine.max()
        v2_min, v2_max = values2_fine.min(), values2_fine.max()

        norm1 = (values1_fine - v1_min) / (v1_max - v1_min + 1e-10)
        norm2 = (values2_fine - v2_min) / (v2_max - v2_min + 1e-10)
        target1_norm = (self.v1 - v1_min) / (v1_max - v1_min + 1e-10)
        target2_norm = (self.v2 - v2_min) / (v2_max - v2_min + 1e-10)

        f1_display = self.f1.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()
        f2_display = self.f2.replace('comp_', 'Comp ').replace('shear_', 'Shear ').replace('_', ' ').title()

        ax.plot(radius_fine, norm1, 'b-', linewidth=2, label=f'{f1_display} (normalized)')
        ax.plot(radius_fine, norm2, 'r-', linewidth=2, label=f'{f2_display} (normalized)')

        # Plot target lines
        ax.axhline(y=target1_norm, color='blue', linestyle='--', linewidth=1.5, alpha=0.7)
        ax.axhline(y=target2_norm, color='red', linestyle='--', linewidth=1.5, alpha=0.7)

        # Plot intersection points
        for r in intersections_f1:
            ax.axvline(x=r, color='blue', linestyle=':', linewidth=1.5, alpha=0.5)
            ax.scatter([r], [target1_norm], marker='s', s=100, c='blue', edgecolors='white', linewidths=1.5, zorder=5)

        for r in intersections_f2:
            ax.axvline(x=r, color='red', linestyle=':', linewidth=1.5, alpha=0.5)
            ax.scatter([r], [target2_norm], marker='s', s=100, c='red', edgecolors='white', linewidths=1.5, zorder=5)

        # Find optimal radius (closest intersection from both curves)
        optimal_radius = None
        is_approximation = False

        if intersections_f1 and intersections_f2:
            # Find the closest pair of intersections
            min_dist = float('inf')
            for r1 in intersections_f1:
                for r2 in intersections_f2:
                    dist = abs(r1 - r2)
                    if dist < min_dist:
                        min_dist = dist
                        optimal_radius = (r1 + r2) / 2
        else:
            # 没有找到交点，寻找最接近目标值的点
            is_approximation = True
            # 计算每个点到两个目标值的归一化距离
            combined_dist = np.sqrt((norm1 - target1_norm)**2 + (norm2 - target2_norm)**2)
            min_idx = np.argmin(combined_dist)
            optimal_radius = radius_fine[min_idx]

        if optimal_radius is not None:
            if is_approximation:
                ax.axvline(x=optimal_radius, color='orange', linestyle='-', linewidth=3, alpha=0.8)
                ax.scatter([optimal_radius], [0.5], marker='s', s=300, c='orange',
                          edgecolors='white', linewidths=2, zorder=10,
                          label=f'Closest R={optimal_radius:.3f}')
            else:
                ax.axvline(x=optimal_radius, color='green', linestyle='-', linewidth=3, alpha=0.8)
                ax.scatter([optimal_radius], [0.5], marker='*', s=400, c='green',
                          edgecolors='white', linewidths=2, zorder=10,
                          label=f'Optimal R={optimal_radius:.3f}')

            # Store best sample info (transform=8 for these structures)
            self.best_samples = [{
                'sample_name': f'{self.nearest_family}_5_{optimal_radius:.3f}_8'.replace('.', 'p'),
                'cell_type': self.nearest_family,
                'radius': optimal_radius,
                'slider': 8,  # Fixed transform for 1D structures
                'predicted_f1': float(interp_f1(optimal_radius)),
                'predicted_f2': float(interp_f2(optimal_radius)),
                'is_approximation': is_approximation
            }]

        # Style
        ax.set_xlabel('Strut Radius (mm)', color='#c5d1de', fontsize=12, fontweight='bold')
        ax.set_ylabel('Normalized Feature Value', color='#c5d1de', fontsize=12, fontweight='bold')
        ax.set_title(f'{self.nearest_family} - 1D Feature Intersection (Radius Only)', color='#e1e8f0', fontsize=14, fontweight='bold')
        ax.tick_params(colors='#c5d1de')
        ax.spines['bottom'].set_color('#3d5a80')
        ax.spines['top'].set_color('#3d5a80')
        ax.spines['left'].set_color('#3d5a80')
        ax.spines['right'].set_color('#3d5a80')
        ax.legend(facecolor='#262b3d', edgecolor='#3d5a80', labelcolor='#c5d1de', fontsize=9, loc='best')
        ax.grid(True, alpha=0.3, color='#3d5a80')

        self.fig4.tight_layout()

    def _find_contour_intersection(self, contour1, contour2):
        """Find the intersection point of two contour sets"""
        try:
            if not hasattr(contour1, 'allsegs') or not hasattr(contour2, 'allsegs'):
                return None, None

            if len(contour1.allsegs) == 0 or len(contour2.allsegs) == 0:
                return None, None

            if len(contour1.allsegs[0]) == 0 or len(contour2.allsegs[0]) == 0:
                return None, None

            # Merge all segments
            points1 = np.vstack(contour1.allsegs[0]) if contour1.allsegs[0] else np.array([])
            points2 = np.vstack(contour2.allsegs[0]) if contour2.allsegs[0] else np.array([])

            if len(points1) == 0 or len(points2) == 0:
                return None, None

            # Find closest pair
            distances = cdist(points1, points2)
            min_idx = np.unravel_index(distances.argmin(), distances.shape)

            closest1 = points1[min_idx[0]]
            closest2 = points2[min_idx[1]]
            best_point = (closest1 + closest2) / 2

            return best_point[0], best_point[1]

        except Exception as e:
            print(f"Error finding intersection: {e}")
            return None, None
