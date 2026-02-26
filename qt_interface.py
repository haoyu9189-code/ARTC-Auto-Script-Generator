#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qt图形界面模块
实现应用程序的主界面和用户交互功能

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import sys
import os
import json
import platform
import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial.distance import cdist

# 获取脚本所在目录（支持PyInstaller打包环境）
if getattr(sys, 'frozen', False):
    # PyInstaller 打包环境
    BASE_DIR = sys._MEIPASS
else:
    # 开发环境
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                           QWidget, QComboBox, QLabel, QPushButton, QFrame, QGridLayout, QSplitter, QCheckBox, QSlider, QMenuBar, QAction, QLineEdit, QSpinBox, QDoubleSpinBox, QGroupBox, QTextEdit, QDialog, QMessageBox, QTabWidget, QScrollArea)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QIcon, QPixmap
from PyQt5.QtCore import QSize
from visualization_widget import CellVisualizationWidget


def get_icon_path(icon_name):
    """获取图标路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "assets", "icons", icon_name)
    if os.path.exists(icon_path):
        return icon_path
    return None
from script_generator import generate_abaqus_script
from config import Config
from custom_title_bar import CustomTitleBar, get_title_bar_stylesheet
# 导入批量管理器
try:
    from batch_manager import BatchJobManager
except ImportError:
    BatchJobManager = None

# 导入统一的特征提取模块（可选，Linux服务器可能没有）
_model_path = os.path.join(BASE_DIR, '.claude', 'skills', 'material-assistant', 'model')
if _model_path not in sys.path:
    sys.path.insert(0, _model_path)
try:
    from feature_extract import detect_densification_point, find_peak_point, linear_region_fit
    FEATURE_EXTRACT_AVAILABLE = True
except ImportError:
    FEATURE_EXTRACT_AVAILABLE = False
    detect_densification_point = None
    find_peak_point = None
    linear_region_fit = None
    print("警告: feature_extract模块未找到，曲线特征分析功能将被禁用")

# 避免循环导入，在需要时动态导入


class Statistics3DDialog(QWidget):
    """3D 统计曲面可视化对话框"""

    # 压缩曲线特征
    FEATURES_COMPRESSION = ["Young's Modulus", 'Densified Stress', 'Densified Strain',
                            'Yield Stress', 'Yield Strain', 'Energy Absorb']
    # 剪切曲线特征
    FEATURES_SHEAR = ['Shear Modulus', 'Last Stress', 'Last Strain',
                      'Yield Stress', 'Yield Strain', 'Energy Absorb']

    # 设置文件路径
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'work', 'ui_settings.json')

    def __init__(self, data, cell_type, cell_size, curve_type, parent=None):
        super().__init__(parent, Qt.Window)
        # 使用无边框窗口 + 自定义标题栏（与主窗口一致）
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1300, 950)  # 增大窗口尺寸
        # 非模态窗口，允许与主界面并行操作
        self.setWindowModality(Qt.NonModal)

        # 保存标题信息
        self._window_title = f"Statistics - {cell_type} (Cell Size: {cell_size}mm)"

        # 从设置文件加载窗口位置，如果没有则使用默认位置
        self._load_window_position(parent)

        self.data = data
        self.curve_type = curve_type
        self.cell_size = cell_size
        self.parent_window = parent  # 保存父窗口引用以获取实时 UI 值

        # 根据曲线类型选择特征列表 (支持动态曲线)
        self.is_compression = ('Compre' in curve_type)
        self.FEATURES = self.FEATURES_COMPRESSION if self.is_compression else self.FEATURES_SHEAR

        # 异常值过滤属性
        self.filter_outliers = True  # 默认开启过滤
        self.outlier_samples = set()  # 存储异常样本名
        self.all_points = []  # 存储所有点（包括异常）

        # 平滑处理属性
        self.use_smooth = True  # 默认开启平滑

        # 解析数据点
        self._parse_data()

        # 创建 UI
        self._setup_ui()

        # 初始显示
        self.update_surface(self.FEATURES[0])

        # 设置定时器监听父窗口 slider 变化
        if parent:
            self._setup_realtime_update()

    def _load_window_position(self, parent):
        """从设置文件加载窗口位置"""
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    stats_pos = settings.get('statistics_dialog_position', None)
                    if stats_pos:
                        # 验证位置是否在屏幕范围内
                        from PyQt5.QtWidgets import QDesktopWidget
                        screen = QDesktopWidget().screenGeometry()
                        x = stats_pos.get('x', 0)
                        y = stats_pos.get('y', 0)
                        w = stats_pos.get('width', self.width())
                        h = stats_pos.get('height', self.height())
                        # 确保窗口在屏幕范围内
                        if 0 <= x <= screen.width() - 100 and 0 <= y <= screen.height() - 100:
                            self.resize(w, h)
                            self.move(x, y)
                            return
        except Exception as e:
            print(f"加载Statistics窗口位置失败: {e}")

        # 如果没有保存的位置，使用默认位置（父窗口右下角）
        if parent:
            parent_geo = parent.geometry()
            new_x = parent_geo.x() + parent_geo.width() - self.width() - 50
            new_y = parent_geo.y() + parent_geo.height() - self.height() - 50
            from PyQt5.QtWidgets import QDesktopWidget
            screen = QDesktopWidget().screenGeometry()
            new_x = max(0, min(new_x, screen.width() - self.width()))
            new_y = max(0, min(new_y, screen.height() - self.height()))
            self.move(new_x, new_y)

    def _save_window_position(self):
        """保存窗口位置到设置文件"""
        try:
            settings = {}
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

            # 保存窗口位置和大小
            settings['statistics_dialog_position'] = {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height()
            }

            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存Statistics窗口位置失败: {e}")

    def closeEvent(self, event):
        """窗口关闭时保存位置"""
        self._save_window_position()
        # 停止定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        super().closeEvent(event)

    def _setup_realtime_update(self):
        """设置实时更新监听"""
        from PyQt5.QtCore import QTimer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._check_ui_change)
        self.update_timer.start(200)  # 每200ms检查一次
        self._last_radius = None
        self._last_slider = None
        self._last_cell_type = None
        self._last_curve_type = self.curve_type  # 监听曲线类型变化

    def _get_current_cell_type(self):
        """获取当前选中的 Cell type"""
        if self.parent_window:
            # 优先从 Page 2 获取 (dropdowns_page2["Cell type:"])
            dropdowns_page2 = getattr(self.parent_window, 'dropdowns_page2', {})
            cell_type_dropdown_p2 = dropdowns_page2.get("Cell type:", None)
            if cell_type_dropdown_p2:
                return cell_type_dropdown_p2.currentText()
            # 否则从 Page 1 获取
            dropdowns = getattr(self.parent_window, 'dropdowns', {})
            cell_type_dropdown = dropdowns.get("Cell type :", None)
            if cell_type_dropdown:
                return cell_type_dropdown.currentText()
        return None

    def _get_current_curve_type(self):
        """获取当前选中的 Curve type"""
        if self.parent_window:
            # 优先从 Page 2 获取
            dropdowns_page2 = getattr(self.parent_window, 'dropdowns_page2', {})
            curve_type_dropdown = dropdowns_page2.get("Curve type:", None)
            if curve_type_dropdown:
                return curve_type_dropdown.currentText()
        return None

    def _check_ui_change(self):
        """检查 UI 值是否变化，触发更新"""
        if not self.parent_window:
            return
        try:
            current_radius, current_slider = self._get_current_ui_values()
            current_cell_type = self._get_current_cell_type()
            current_curve_type = self._get_current_curve_type()

            # 检查 Cell type 是否变化 - 需要重新加载数据
            if current_cell_type != self._last_cell_type:
                self._last_cell_type = current_cell_type
                self._reload_data_for_cell_type(current_cell_type)
                return

            # 检查 Curve type 是否变化 - 需要更新特征列表和图表
            if current_curve_type and current_curve_type != self._last_curve_type:
                self._last_curve_type = current_curve_type
                self._reload_for_curve_type(current_curve_type)
                return

            # 检查 radius 或 slider 是否变化 - 只需更新红点位置
            if current_radius != self._last_radius or current_slider != self._last_slider:
                self._last_radius = current_radius
                self._last_slider = current_slider
                # 重新绘制以更新红色点
                self.update_surface(self.feature_combo.currentText())
        except Exception as e:
            print(f"[3D Plot] UI change check error: {e}")

    def _reload_data_for_cell_type(self, cell_type):
        """重新加载指定 Cell type 的数据"""
        import os
        import json

        if not cell_type:
            return

        try:
            # 加载 feature_data.json
            feature_data_path = os.path.join(BASE_DIR, "work", "feature_data.json")
            if not os.path.exists(feature_data_path):
                return

            with open(feature_data_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)

            # 过滤出当前 Cell type 的数据
            filtered_data = {k: v for k, v in all_data.items() if k.startswith(cell_type + "_")}

            if filtered_data:
                self.data = filtered_data
                self._parse_data()
                self.update_surface(self.feature_combo.currentText())
                # 更新窗口标题
                self.setWindowTitle(f"Statistics - {cell_type} (Cell Size: {self.cell_size}mm)")
                print(f"[3D Plot] Reloaded data for {cell_type}: {len(self.points)} points")
        except Exception as e:
            print(f"[3D Plot] Failed to reload data: {e}")

    def _reload_for_curve_type(self, curve_type):
        """切换曲线类型时更新特征列表和图表"""
        if not curve_type:
            return

        try:
            # 更新曲线类型
            self.curve_type = curve_type
            self.is_compression = ('Compre' in curve_type)

            # 更新特征列表
            self.FEATURES = self.FEATURES_COMPRESSION if self.is_compression else self.FEATURES_SHEAR

            # 更新下拉框选项
            if hasattr(self, 'feature_combo'):
                current_idx = self.feature_combo.currentIndex()
                self.feature_combo.blockSignals(True)
                self.feature_combo.clear()
                self.feature_combo.addItems(self.FEATURES)
                # 尽量保持相同索引，否则回到第一个
                new_idx = min(current_idx, len(self.FEATURES) - 1)
                self.feature_combo.setCurrentIndex(max(0, new_idx))
                self.feature_combo.blockSignals(False)

            # 重新解析数据并更新图表
            self._parse_data()
            self.update_surface(self.feature_combo.currentText())

            print(f"[3D Plot] Switched to curve type: {curve_type} (is_compression={self.is_compression})")
        except Exception as e:
            print(f"[3D Plot] Failed to switch curve type: {e}")

    def _get_current_ui_values(self):
        """从父窗口获取当前 radius 和 slider 值

        注意: slider_val 需要根据 Limit Range 模式转换
        - Limit Range ON: slider 内部值 0-8，直接使用
        - Limit Range OFF: slider 内部值 0-80，需要除以10
        """
        radius = 0.3
        slider_val = 0
        if self.parent_window:
            # 获取 radius (Page 2 优先)
            if hasattr(self.parent_window, 'strut_radius_slider_page2'):
                radius = self.parent_window.strut_radius_slider_page2.value() / 100.0
            elif hasattr(self.parent_window, 'strut_radius_slider'):
                radius = self.parent_window.strut_radius_slider.value() / 100.0

            # 获取 transform slider 值 (Page 2 优先)
            # 需要根据 Limit Range 模式转换
            is_limited = (hasattr(self.parent_window, 'is_limit_range_mode') and
                         self.parent_window.is_limit_range_mode())

            if hasattr(self.parent_window, 'transform_slider_page2'):
                raw_val = self.parent_window.transform_slider_page2.value()
            elif hasattr(self.parent_window, 'slider'):
                raw_val = self.parent_window.slider.value()
            else:
                raw_val = 0

            # 转换为实际显示值
            if is_limited:
                slider_val = raw_val  # 0-8 整数
            else:
                slider_val = raw_val / 10.0  # 0-80 -> 0-8.0

        return radius, slider_val

    def _setup_ui(self):
        """设置 UI"""
        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QComboBox
        from PyQt5.QtCore import QPoint

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 无边距让标题栏贴边
        layout.setSpacing(0)

        # 深色主题样式 - 最小字体20px
        self.setStyleSheet("""
            QWidget {
                background-color: #1e2330;
                color: #c5d1de;
                font-size: 20px;
            }
            QLabel {
                color: #c5d1de;
                font-size: 20px;
            }
            QComboBox {
                background-color: #262b3d;
                color: #c5d1de;
                border: 1px solid #3d5a80;
                border-radius: 5px;
                padding: 8px 15px;
                min-width: 200px;
                font-size: 20px;
            }
            QComboBox:hover {
                border-color: #4a6fa5;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #262b3d;
                color: #c5d1de;
                selection-background-color: #3d5a80;
                font-size: 20px;
            }
            /* 自定义标题栏样式 - 无分割线无色差 */
            #dialog_title_bar {
                background-color: #1e2330;
                border: none;
            }
            #dialog_title_label {
                color: #e1e8f0;
                font-size: 22px;
                font-weight: 600;
                padding-left: 10px;
                background: transparent;
            }
            #dialog_title_button {
                background: transparent;
                color: #c5d1de;
                border: none;
                font-size: 26px;
                font-weight: 400;
            }
            #dialog_title_button:hover {
                background: #3d5a80;
                color: #ffffff;
            }
            #dialog_close_button {
                background: transparent;
                color: #c5d1de;
                border: none;
                font-size: 22px;
                font-weight: 400;
            }
            #dialog_close_button:hover {
                background: #e74c3c;
                color: #ffffff;
            }
        """)

        # ===== 自定义标题栏 =====
        title_bar = QWidget()
        title_bar.setObjectName("dialog_title_bar")
        title_bar.setFixedHeight(45)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(15, 0, 0, 0)
        title_bar_layout.setSpacing(0)

        # 标题文本
        title_label = QLabel(self._window_title)
        title_label.setObjectName("dialog_title_label")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        # 最小化按钮
        min_btn = QPushButton("−")
        min_btn.setObjectName("dialog_title_button")
        min_btn.setFixedSize(55, 40)
        min_btn.clicked.connect(self.showMinimized)
        min_btn.setToolTip("最小化")
        title_bar_layout.addWidget(min_btn)

        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setObjectName("dialog_close_button")
        close_btn.setFixedSize(55, 40)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("关闭")
        title_bar_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # 为标题栏添加拖动功能
        self._title_bar = title_bar
        self._drag_position = QPoint()
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        # ===== 内容区域 =====
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(5)

        # 顶部控制栏 - 紧凑布局
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(10, 5, 10, 0)
        feature_label = QLabel("Feature:")
        feature_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        top_layout.addWidget(feature_label)
        self.feature_combo = QComboBox()
        self.feature_combo.addItems(self.FEATURES)
        self.feature_combo.currentTextChanged.connect(self.update_surface)
        top_layout.addWidget(self.feature_combo)

        # 显示数据点数量
        self.info_label = QLabel(f"Data points: {len(self.points)}")
        self.info_label.setStyleSheet("font-size: 16px; margin-left: 20px;")
        top_layout.addWidget(self.info_label)

        # 异常值过滤复选框
        from PyQt5.QtWidgets import QCheckBox
        self.cb_filter_outliers = QCheckBox("过滤异常值")
        self.cb_filter_outliers.setChecked(self.filter_outliers)
        self.cb_filter_outliers.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                margin-left: 20px;
                color: #c5d1de;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #3d5a80;
                background: #262b3d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4a6fa5;
                background: #3d5a80;
                border-radius: 3px;
            }
        """)
        self.cb_filter_outliers.stateChanged.connect(self._on_filter_changed)
        top_layout.addWidget(self.cb_filter_outliers)

        # 平滑曲面复选框
        self.cb_smooth = QCheckBox("平滑曲面")
        self.cb_smooth.setChecked(self.use_smooth)
        self.cb_smooth.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                margin-left: 15px;
                color: #c5d1de;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #3d5a80;
                background: #262b3d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4a6fa5;
                background: #3d5a80;
                border-radius: 3px;
            }
        """)
        self.cb_smooth.stateChanged.connect(self._on_smooth_changed)
        top_layout.addWidget(self.cb_smooth)

        top_layout.addStretch()
        content_layout.addLayout(top_layout)

        # Matplotlib 3D 视图 - 填满窗口
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        from PyQt5.QtWidgets import QSizePolicy

        self.figure = Figure(facecolor='#1e2330')
        self.figure.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)  # 图表占满
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor('#1e2330')
        content_layout.addWidget(self.canvas, 1)  # stretch=1 让 canvas 占用所有剩余空间

        layout.addWidget(content_widget, 1)

    def _title_bar_mouse_press(self, event):
        """标题栏鼠标按下事件 - 开始拖动"""
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event):
        """标题栏鼠标移动事件 - 拖动窗口"""
        if event.buttons() == Qt.LeftButton and self._drag_position:
            self.move(event.globalPos() - self._drag_position)
            event.accept()

    def _parse_data(self):
        """解析数据，提取 radius, slider, features, sample_name"""
        import numpy as np
        from scipy.signal import find_peaks

        self.all_points = []  # [(radius, slider, features_dict, sample_name), ...]

        for key, value in self.data.items():
            parts = key.split('_')
            if len(parts) < 4:
                continue

            # 从后往前解析：最后是slider，倒数第二是ratio，倒数第三是size
            # 格式: {结构名}_{size}_{ratio}_{slider}
            # 例如: Octet_truss_5_0p35_0 -> slider=0, ratio=0.35, size=5
            try:
                slider = int(parts[-1])
                radius = float(parts[-2].replace('p', '.'))
            except (ValueError, IndexError):
                continue

            # 获取曲线数据
            curve_key = None
            if self.curve_type in value:
                curve_key = self.curve_type
            elif 'StaCompre_curve' in value:
                curve_key = 'StaCompre_curve'
            elif 'StaShare_curve' in value:
                curve_key = 'StaShare_curve'

            if curve_key and curve_key in value:
                curve = value[curve_key]
                if curve is not None and 'displacement' in curve and 'force' in curve:
                    features = self._extract_features(
                        curve['displacement'],
                        curve['force'],
                        value.get('density', 1.0),
                        curve_key,
                        sample_name=key  # 传递样本名称用于特殊处理
                    )
                    self.all_points.append((radius, slider, features, key))

        # 检测EA异常值
        self.outlier_samples = self._detect_ea_outliers()

        # 应用过滤
        self._apply_outlier_filter()

    def _detect_ea_outliers(self):
        """检测 EA 异常值 - 基于局部变化剧烈程度（曲面尖刺检测）"""
        import numpy as np

        if len(self.all_points) < 4:
            return set()

        # 提取所有点的信息: (radius, slider, EA, sample_name)
        points_data = []
        for p in self.all_points:
            ea = p[2].get('EA', None)
            if ea is not None and not np.isnan(ea):
                points_data.append((p[0], p[1], ea, p[3]))  # radius, slider, EA, sample_name

        if len(points_data) < 4:
            return set()

        outliers = set()

        # 对每个点，检查与邻近点的变化是否过于剧烈
        for i, (r1, s1, ea1, name1) in enumerate(points_data):
            # 找到邻近点（radius 差 < 0.1, slider 差 < 3）
            neighbors_ea = []
            for j, (r2, s2, ea2, name2) in enumerate(points_data):
                if i != j:
                    r_diff = abs(r1 - r2)
                    s_diff = abs(s1 - s2)
                    # 邻近点条件
                    if r_diff < 0.1 and s_diff < 3:
                        neighbors_ea.append(ea2)

            # 如果有邻近点，检查变化是否剧烈
            if len(neighbors_ea) >= 2:
                neighbor_mean = np.mean(neighbors_ea)
                neighbor_std = np.std(neighbors_ea)

                # 异常条件：使用比率检测（可检测高于或低于邻居的异常）
                if neighbor_mean > 0 and ea1 > 0:
                    # 计算比率（始终 >= 1）
                    ratio = max(ea1, neighbor_mean) / min(ea1, neighbor_mean)
                    abs_diff = abs(ea1 - neighbor_mean)
                    # 异常条件：
                    # 1. 比率超过 10 倍 - 极端异常，直接标记
                    # 2. 比率超过 2 倍，且绝对差异超过 1.5 倍标准差
                    threshold = max(1.5 * neighbor_std, 20)
                    is_extreme = ratio > 10
                    is_significant = ratio > 2.0 and abs_diff > threshold
                    if is_extreme or is_significant:
                        outliers.add(name1)

        return outliers

    def _apply_outlier_filter(self):
        """根据过滤开关应用异常值过滤"""
        if self.filter_outliers and self.outlier_samples:
            self.points = [p for p in self.all_points if p[3] not in self.outlier_samples]
        else:
            self.points = self.all_points.copy()

    def _on_filter_changed(self, state):
        """过滤复选框状态变化回调"""
        from PyQt5.QtCore import Qt
        self.filter_outliers = (state == Qt.Checked)
        self._apply_outlier_filter()
        # 刷新曲面显示
        if hasattr(self, 'feature_combo'):
            self.update_surface(self.feature_combo.currentText())

    def _on_smooth_changed(self, state):
        """平滑复选框状态变化回调"""
        from PyQt5.QtCore import Qt
        self.use_smooth = (state == Qt.Checked)
        # 刷新曲面显示
        if hasattr(self, 'feature_combo'):
            self.update_surface(self.feature_combo.currentText())

    def _extract_features(self, displacement, force, density, curve_type='StaCompre_curve', sample_name=None):
        """从曲线提取特征

        Args:
            sample_name: 样本名称，用于特殊样本的位置override
        """
        import numpy as np
        from scipy.signal import find_peaks

        # 特殊样本直接指定densified strain位置
        SPECIAL_OVERRIDES = {
            'Octet_truss_5_0p5_2': 0.37,  # 特殊设置：算法检测为0.55，实际应为0.37
            # 'WeairePhelan_5_0p45_0': 0.4,
            # 'WeairePhelan_5_0p45_1': 0.35,
            # 'WeairePhelan_5_0p5_3': 0.48,
            # 'WeairePhelan_5_0p5_4': 0.44,
            # 'Octet_truss_5_0p5_6': 0.58,
            # 'FBCCXYZ_5_0p45_1': 0.58,
            # 'FBCCXYZ_5_0p45_2': 0.52,
            # 'FBCCXYZ_5_0p45_4': 0.45,
            # 'BCC_5_0p45_3': 0.61,
            # 'BCC_5_0p35_6': 0.66,
            # 'BCCZ_5_0p45_2': 0.62,
            # 'Octet_truss_5_0p5_3': 0.6,
            # 'Octet_truss_5_0p5_4': 0.58,
            # 'Octet_truss_5_0p5_5': 0.58,
            # 'Auxetic_5_0p5_2': 0.55,
            # 'Auxetic_5_0p5_3': 0.55,
        }

        displacement = np.array(displacement)
        force = np.array(force)

        # 转换为应变和应力
        strain = displacement / self.cell_size
        stress = force / (self.cell_size ** 2)

        is_compression = ('Compre' in curve_type)
        is_dynamic = ('Dyna' in curve_type)

        if len(strain) < 5:
            return {
                'stiffness': 0.0,
                'yield_strain': 0.0,
                'yield_stress': 0.0,
                'densified_strain': 0.0,
                'densified_stress': 0.0,
                'peak_strain': 0.0,
                'peak_stress': 0.0,
                'EA': 0.0
            }

        # 线性区拟合
        lin_idx = min(10, len(strain) // 4)
        lin_idx = max(lin_idx, 2)
        x = strain[:lin_idx+1]
        y = stress[:lin_idx+1]
        K = (x @ y) / max(x @ x, 1e-12)  # 刚度/剪切模量

        # 屈服点 (0.5% 偏移法)
        offset_strain = 0.005
        stress_off = K * (strain - offset_strain)
        diff = stress - stress_off
        start = np.searchsorted(strain, max(offset_strain, 0.005))
        cross = np.where((diff[1:] <= 0) & (diff[:-1] > 0))[0]
        cross = cross[cross >= start-1] if cross.size else cross
        yield_idx = (cross[0] + 1) if cross.size else len(strain) - 1
        yield_stress = float(stress[yield_idx])
        yield_strain = float(strain[yield_idx])

        if is_compression:
            # 压缩曲线：找 Densified 点（密实化起点）
            n = len(strain)

            # 检查是否为特殊样本，直接使用override位置并提前返回
            if sample_name and sample_name in SPECIAL_OVERRIDES:
                target_strain = SPECIAL_OVERRIDES[sample_name]
                key_idx = int(np.argmin(np.abs(strain - target_strain)))
                # 直接计算EA并返回
                V0 = self.cell_size ** 3
                E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
                EA = E_total * V0
                return {
                    'stiffness': K,
                    'yield_strain': yield_strain,
                    'yield_stress': yield_stress,
                    'densified_strain': float(strain[key_idx]),
                    'densified_stress': float(stress[key_idx]),
                    'peak_strain': 0.0,
                    'peak_stress': 0.0,
                    'EA': EA
                }

            # 非特殊样本
            if is_dynamic:
                # 动态压缩：首先检查是否有回弹
                max_strain_idx = int(np.argmax(strain))
                max_strain_val = float(strain[max_strain_idx])

                # 检查是否有回弹：max_strain在前90%的数据中
                has_rebound = max_strain_idx < n * 0.9

                if has_rebound:
                    # 有回弹：积分到max_strain
                    key_idx = max_strain_idx
                    densified_strain = max_strain_val
                else:
                    # 无回弹（可能有尾部spike）：检测尖峰并找到切断点
                    # 计算前80%数据的中位应力作为平台应力
                    cut_80 = int(n * 0.8)
                    plateau_stress = float(np.median(stress[:cut_80])) if cut_80 > 0 else float(stress[0])
                    max_stress = float(np.max(stress))

                    # 判断是否有尖峰：最大应力超过平台应力3倍
                    has_spike = max_stress > 3 * plateau_stress and plateau_stress > 0

                    if has_spike:
                        # 有尖峰：找应力首次超过2倍平台应力的位置作为切断点
                        spike_threshold = 2 * plateau_stress
                        spike_onset_indices = np.where(stress > spike_threshold)[0]
                        if len(spike_onset_indices) > 0:
                            key_idx = spike_onset_indices[0]
                            densified_strain = float(strain[key_idx])
                        else:
                            densified_strain = 0.8 * max_strain_val
                            key_idx = int(np.argmin(np.abs(strain - densified_strain)))
                    else:
                        # 无明显尖峰：使用密实化点检测
                        try:
                            detected_strain = detect_densification_point(strain, stress)
                            if 0.2 * max_strain_val <= detected_strain <= 0.95 * max_strain_val:
                                densified_strain = detected_strain
                                key_idx = int(np.argmin(np.abs(strain - densified_strain)))
                            else:
                                densified_strain = 0.8 * max_strain_val
                                key_idx = int(np.argmin(np.abs(strain - densified_strain)))
                        except:
                            densified_strain = 0.8 * max_strain_val
                            key_idx = int(np.argmin(np.abs(strain - densified_strain)))
            else:
                # 静态压缩：使用新算法检测
                # 在 strain 0.5 到 0.7 范围内，找二阶导数的最后一个峰值作为压实点
                densified_strain = detect_densification_point(strain, stress)
                key_idx = int(np.argmin(np.abs(strain - densified_strain)))
            densified_stress = float(stress[key_idx])
            peak_stress = 0.0
            peak_strain = 0.0
        else:
            # 剪切曲线：积分到最后一点（与 extract_curve_features_inline 保持一致）
            key_idx = len(strain) - 1
            # Peak 点信息仍然保留用于显示
            peak_idx = int(np.argmax(stress))
            peak_stress = float(stress[peak_idx])
            peak_strain = float(strain[peak_idx])
            densified_stress = 0.0
            densified_strain = 0.0

        # EA (从起点到关键点的积分面积)
        V0 = self.cell_size ** 3
        E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
        EA = E_total * V0

        return {
            'stiffness': K,
            'yield_strain': yield_strain,
            'yield_stress': yield_stress,
            'densified_strain': densified_strain,
            'densified_stress': densified_stress,
            'peak_strain': peak_strain,
            'peak_stress': peak_stress,
            'EA': EA
        }

    def update_surface(self, feature_name):
        """更新 3D 散点图和拟合曲面"""
        import numpy as np
        from scipy.interpolate import griddata

        if len(self.points) < 1:
            return

        # 提取数据点
        radius = np.array([p[0] for p in self.points])
        slider = np.array([p[1] for p in self.points])

        feature_map = {
            # 压缩曲线特征
            "Young's Modulus": 'stiffness',
            'Densified Stress': 'densified_stress',
            'Densified Strain': 'densified_strain',
            # 剪切曲线特征
            'Shear Modulus': 'stiffness',  # 剪切模量使用同一个 stiffness 字段
            'Last Stress': 'peak_stress',   # Last 使用同一个 peak_stress 字段
            'Last Strain': 'peak_strain',   # Last 使用同一个 peak_strain 字段
            # 通用特征
            'Yield Stress': 'yield_stress',
            'Yield Strain': 'yield_strain',
            'Energy Absorb': 'EA'
        }
        feature_key = feature_map.get(feature_name, 'stiffness')
        values = np.array([p[2][feature_key] for p in self.points])

        # 获取当前 UI 值
        current_radius, current_slider = self._get_current_ui_values()

        # 保存用于后续更新信息标签
        self._current_feature_name = feature_name
        self._current_values = values
        self._current_slider = current_slider
        self._current_radius = current_radius

        # 清空图形
        self.ax.clear()

        # X=slider, Y=radius, Z=feature
        # 绘制所有已有结果的数据点 - 浅灰色小点（比红点小一半以便区分）
        self.ax.scatter(slider, radius, values, c='#aaaaaa', s=40, zorder=10,
                       label='Data Points', alpha=0.5, edgecolors='#888888', linewidths=0.5)

        # 拟合曲面
        zi_interp = None
        try:
            # 检查数据维度
            slider_unique = np.unique(slider)
            radius_unique = np.unique(radius)

            if len(slider_unique) > 1 and len(radius_unique) > 1:
                # 两个维度都有变化，进行2D插值
                grid_size = 50 if self.use_smooth else 30
                xi = np.linspace(slider.min(), slider.max(), grid_size)
                yi = np.linspace(radius.min(), radius.max(), grid_size)
                xi_grid, yi_grid = np.meshgrid(xi, yi)

                if self.use_smooth:
                    # 平滑模式：RBF + 高斯平滑
                    try:
                        from scipy.interpolate import RBFInterpolator
                        from scipy.ndimage import gaussian_filter
                        points = np.column_stack([slider, radius])
                        rbf = RBFInterpolator(points, values, kernel='thin_plate_spline', smoothing=1.0)
                        grid_points = np.column_stack([xi_grid.ravel(), yi_grid.ravel()])
                        zi = rbf(grid_points).reshape(xi_grid.shape)
                        # 高斯平滑
                        nan_mask = np.isnan(zi)
                        if not np.all(nan_mask):
                            zi_filled = np.where(nan_mask, np.nanmean(zi), zi)
                            zi_smooth = gaussian_filter(zi_filled, sigma=1.5)
                            zi = np.where(nan_mask, np.nan, zi_smooth)
                    except Exception:
                        zi = griddata((slider, radius), values, (xi_grid, yi_grid), method='cubic')
                else:
                    # 原始模式：cubic griddata（不平滑）
                    try:
                        zi = griddata((slider, radius), values, (xi_grid, yi_grid), method='cubic')
                    except:
                        zi = griddata((slider, radius), values, (xi_grid, yi_grid), method='linear')

                # 绘制曲面
                if zi is not None and not np.all(np.isnan(zi)):
                    surf = self.ax.plot_surface(xi_grid, yi_grid, zi,
                                               alpha=0.6, cmap='viridis',
                                               edgecolor='none', antialiased=True)
                    # 保存曲面网格数据，用于直接从曲面取点
                    self._surface_grid = (xi_grid, yi_grid, zi, xi, yi)

            elif len(slider_unique) > 1:
                # 只有 slider 变化，绘制2D线在3D空间
                sort_idx = np.argsort(slider)
                self.ax.plot(slider[sort_idx], radius[sort_idx], values[sort_idx],
                           'b-', linewidth=3, alpha=0.7, label='Fitted Line')

            elif len(radius_unique) > 1:
                # 只有 radius 变化，绘制2D线在3D空间
                sort_idx = np.argsort(radius)
                self.ax.plot(slider[sort_idx], radius[sort_idx], values[sort_idx],
                           'b-', linewidth=3, alpha=0.7, label='Fitted Line')

        except Exception as e:
            print(f"Surface fitting error: {e}")

        # 绘制红色目标点 - 显示当前 UI 选择的位置
        target_z = None
        is_interpolated = False
        # 用于绘制的实际坐标（可能被调整到曲面网格上）
        plot_slider = current_slider
        plot_radius = current_radius
        try:
            # 优先查找精确匹配的数据点（比插值更准确）
            for p in self.points:
                if abs(p[0] - current_radius) < 0.01 and abs(p[1] - current_slider) < 0.5:
                    target_z = p[2][feature_key]
                    plot_slider = p[1]
                    plot_radius = p[0]
                    is_interpolated = False
                    break

            # 如果没有精确匹配，从曲面网格取插值
            if target_z is None:
                if hasattr(self, '_surface_grid') and self._surface_grid is not None:
                    xi_grid, yi_grid, zi, xi, yi = self._surface_grid
                    # 找到最近的网格点索引
                    i_slider = np.argmin(np.abs(xi - current_slider))
                    i_radius = np.argmin(np.abs(yi - current_radius))
                    # 使用网格上的精确坐标和Z值
                    plot_slider = xi[i_slider]
                    plot_radius = yi[i_radius]
                    target_z = zi[i_radius, i_slider]
                    is_interpolated = True

            # 如果还是没有，用平均值
            if target_z is None or np.isnan(target_z):
                target_z = values.mean()
                is_interpolated = True

            # 获取 Z 轴底部位置 (XY 平面)
            z_min = values.min() if len(values) > 0 else 0

            # 绘制红色虚线 - 从目标点垂直投影到 XY 平面
            self.ax.plot([plot_slider, plot_slider],
                        [plot_radius, plot_radius],
                        [target_z, z_min],
                        'r--', linewidth=2, alpha=0.8, zorder=15)

            # 在 XY 平面上绘制投影点
            self.ax.scatter([plot_slider], [plot_radius], [z_min],
                          c='red', s=80, zorder=15, marker='o', alpha=0.5)

            # 绘制红色目标点 - 大尺寸、高亮显示
            self.ax.scatter([plot_slider], [plot_radius], [target_z],
                          c='red', s=150, zorder=20, marker='o',
                          edgecolors='darkred', linewidths=2,
                          label=f'Current (R={current_radius:.2f}, S={current_slider})')

        except Exception as e:
            print(f"Target point error: {e}")

        # 更新信息标签 - 显示当前位置的插值特征值
        interp_mark = "~" if is_interpolated else ""
        # 过滤信息
        outlier_info = f" | 已过滤: {len(self.outlier_samples)}" if self.filter_outliers and self.outlier_samples else ""
        if target_z is not None and not np.isnan(target_z):
            self.info_label.setText(
                f"Data points: {len(self.points)} | "
                f"Range: [{values.min():.4f}, {values.max():.4f}] | "
                f"Current: R={current_radius:.2f}, S={current_slider} | "
                f"{feature_name}: {interp_mark}{target_z:.4f}{outlier_info}"
            )
        else:
            self.info_label.setText(
                f"Data points: {len(self.points)} | "
                f"Range: [{values.min():.4f}, {values.max():.4f}] | "
                f"Current: R={current_radius:.2f}, S={current_slider}{outlier_info}"
            )

        # 设置坐标轴标签 - 增大字体
        self.ax.set_xlabel('Slider', color='#c5d1de', fontsize=14, fontweight='bold')
        self.ax.set_ylabel('Radius (mm)', color='#c5d1de', fontsize=14, fontweight='bold')
        self.ax.set_zlabel(feature_name, color='#c5d1de', fontsize=14, fontweight='bold')

        # 设置刻度颜色和大小
        self.ax.tick_params(colors='#c5d1de', labelsize=12)

        # 添加图例
        self.ax.legend(loc='upper left', fontsize=11, facecolor='#262b3d',
                      edgecolor='#3d5a80', labelcolor='#c5d1de')

        self.canvas.draw()

    def exec_(self):
        """显示对话框"""
        self.show()

    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        event.accept()


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


class ModernInterface(QMainWindow):
    def __init__(self):
        super().__init__()

        # 移除默认标题栏和边框
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        # 不使用透明背景（会影响3D渲染）
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # self.setWindowTitle("Smart Generator")

        # 用于窗口调整大小
        self.resize_margin = 5  # 边缘检测区域宽度
        self.is_resizing = False
        self.resize_direction = None

        # 启用鼠标追踪以便更新光标
        self.setMouseTracking(True)

        # 检测操作系统并设置适当的窗口大小
        import platform
        if platform.system() != "Linux":
            # Windows和其他系统设置初始尺寸和位置
            self.setGeometry(100, 100, 1950, 1040)  # 1500*1.3=1950, 800*1.3=1040
        # Linux: 不设置窗口几何，让窗口管理器决定位置和尺寸
        # 设置窗口图标
        self.set_window_icon()


        # 设置文件路径
        self.settings_file = os.path.join(os.path.dirname(__file__), "work", "ui_settings.json")

        # 初始化批量管理器
        self.batch_manager = BatchJobManager() if BatchJobManager else None

        self.setStyleSheet(self.get_stylesheet())
        self.init_ui()

        # 加载上次保存的设置
        # 只在启用可视化的系统上加载设置（避免窗口位置异常）
        from visualization_widget import VISUALIZATION_AVAILABLE
        if VISUALIZATION_AVAILABLE:
            self.load_settings()
        else:
            # 即使可视化不可用，也尝试加载 Page 2 曲线
            QTimer.singleShot(300, self._init_page2_curve)

    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 处理 PyInstaller 打包后的资源文件路径
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                icon_path = os.path.join(sys._MEIPASS, 'logo.ico')
            else:
                # 开发环境 - 优先使用 assets/icons/logo.svg
                icon_path = get_icon_path("logo.svg")
                if not icon_path:
                    icon_path = os.path.join(os.path.dirname(__file__), 'work', 'logo.svg')

            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Failed to set window icon: {e}")
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 添加自定义标题栏
        self.title_bar = CustomTitleBar(self, "Smart AM")
        main_layout.addWidget(self.title_bar)

        # 创建页面切换容器（使用 QStackedWidget）
        from PyQt5.QtWidgets import QStackedWidget
        self.page_stack = QStackedWidget()

        # 检测当前操作系统
        import platform
        self.is_linux = platform.system() == "Linux"

        # === 页面 0: Smart Generator ===
        page_smart_gen = QWidget()
        page_smart_gen_layout = QVBoxLayout(page_smart_gen)
        page_smart_gen_layout.setSpacing(0)  # 最小化标题与功能区的间隔
        page_smart_gen_layout.setContentsMargins(30, 10, 30, 30)

        # 创建标题区域（标题和说明在同一行）
        title_container = QWidget()
        title_container_layout = QHBoxLayout(title_container)
        title_container_layout.setSpacing(15)
        title_container_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Smart Generator")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignLeft)
        title_label.setStyleSheet("font-size: 32px; font-weight: 600; color: #e1e8f0;")
        title_container_layout.addWidget(title_label)

        # 添加说明文字（在同一行）
        description_label = QLabel("Quickly generate ABAQUS lattice structure scripts.")
        description_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        description_label.setStyleSheet("font-size: 26px; color: #8a95a5;")
        title_container_layout.addWidget(description_label)
        title_container_layout.addStretch()

        page_smart_gen_layout.addWidget(title_container)

        # Create horizontal splitter for controls and visualization
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #2d3548; }")

        # Left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        form_frame = QFrame()
        form_frame.setObjectName("form_frame")
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(20)
        form_layout.setVerticalSpacing(25)
        form_layout.setContentsMargins(20, 20, 20, 40)  # 增加底部内边距
        
        dropdown_configs = [
            ("Cell type :", [
            "Cubic",
            "BCC",
            "BCCZ",
            "Octet_truss",
            "AFCC",
            "Truncated_cube",
            "FCC",
            "FCCZ",
            "Tetrahedron_base",
            "Iso_truss",
            "G7",
            "FBCCZ",
            "FBCCXYZ",
            "Cuboctahedron_Z",
            "Diamond",
            "Rhombic",
            "Kelvin",
            "Auxetic",
            "Octahedron",
            "Truncated_Octoctahedron",
            "CubicRosette",
            "CBCC",
            "WeairePhelan",
            "DiamondPlus",
            ]),
            ("Compression:", ["StaCompre", "DynaCompre_500","DynaCompre_Auto"]),
            ("Shear:", ["StaShear","DynaShear_500","DynaShear_Auto"])
        ]
        
        self.dropdowns = {}
        self.checkboxes = {}
        self.checkbox_labels = {}  # Store label references for Compression and Shear
        self.slider = None

        # 连续运行相关变量
        self.is_batch_running = False
        self.current_batch_index = 0
        self.batch_timer = None
        self.batch_parent_dir = None

        for i, (label_text, options) in enumerate(dropdown_configs):
            label = QLabel(label_text)
            label.setObjectName("field_label")

            # Store references to Compression and Shear labels and set initial colors
            if label_text in ["Compression:", "Shear:"]:
                self.checkbox_labels[label_text] = label
                # Default color for checked is blue, unchecked is gray (dark theme)
                color = "#5a8bc0" if label_text == "Compression:" else "#6b7785"
                label.setStyleSheet(f"color: {color}; font-size: 29px; font-weight: 600; padding: 10px 0;")

            dropdown = QComboBox()
            dropdown.setObjectName("dropdown")
            dropdown.addItems(options)
            dropdown.setCurrentIndex(0)

            # Connect cell type dropdown to visualization update
            if label_text == "Cell type :":
                dropdown.currentTextChanged.connect(self.on_cell_type_changed)

            form_layout.addWidget(label, i, 0)
            form_layout.addWidget(dropdown, i, 1)

            # Add checkbox for Compression and Shear
            if label_text in ["Compression:", "Shear:"]:
                checkbox = QCheckBox()
                checkbox.setObjectName("checkbox")
                # Default: Compression is checked, Shear is unchecked
                checkbox.setChecked(label_text == "Compression:")
                # Connect checkbox signal for mutual exclusion and label color update
                checkbox.toggled.connect(lambda checked, label=label_text: self.on_speed_direction_checkbox_changed(checked, label))
                form_layout.addWidget(checkbox, i, 2)
                self.checkboxes[label_text] = checkbox

            self.dropdowns[label_text] = dropdown

        # Add slider controls at the bottom
        slider_row = len(dropdown_configs)

        # Cell size slider (3.0 - 10.0, step 0.5, default 5.0)
        self.cell_size_label = QLabel("Cell size:")
        self.cell_size_label.setObjectName("field_label")

        # Container for slider and value label (保存为实例变量，可在页面间移动)
        self.cell_size_container = QWidget()
        cell_size_layout = QHBoxLayout(self.cell_size_container)
        cell_size_layout.setContentsMargins(0, 0, 0, 0)

        self.cell_size_slider = QSlider(Qt.Horizontal)
        self.cell_size_slider.setObjectName("slider")
        self.cell_size_slider.setMinimum(30)  # 3.0 * 10
        self.cell_size_slider.setMaximum(100)  # 10.0 * 10
        self.cell_size_slider.setValue(50)  # 5.0 * 10 (default)
        self.cell_size_slider.setTickPosition(QSlider.TicksBelow)
        self.cell_size_slider.setTickInterval(5)  # 0.5 * 10

        self.cell_size_value_label = QLabel("5.0")
        self.cell_size_value_label.setObjectName("slider_value_label")
        self.cell_size_value_label.setFixedWidth(52)  # 40*1.3=52

        cell_size_layout.addWidget(self.cell_size_slider)
        cell_size_layout.addWidget(self.cell_size_value_label)

        form_layout.addWidget(self.cell_size_label, slider_row, 0)
        form_layout.addWidget(self.cell_size_container, slider_row, 1)

        # Strut radius slider (0.3 - 0.5, step 0.05, default 0.35)
        self.strut_radius_label = QLabel("Strut radius:")
        self.strut_radius_label.setObjectName("field_label")

        self.strut_radius_container = QWidget()
        strut_radius_layout = QHBoxLayout(self.strut_radius_container)
        strut_radius_layout.setContentsMargins(0, 0, 0, 0)

        # Strut radius slider: 使用直接值方式（与Transform一致）
        # Limit Range ON: 30-50 (0.30-0.50, step 5 -> 实际0.05)
        # Limit Range OFF: 20-100 (0.20-1.00, step 1 -> 实际0.01)
        self.strut_radius_slider = QSlider(Qt.Horizontal)
        self.strut_radius_slider.setObjectName("slider")

        # 初始状态：Limit Range ON (默认选中)，范围30-50，步长5
        self.strut_radius_slider.setMinimum(30)  # 0.3 * 100
        self.strut_radius_slider.setMaximum(50)  # 0.5 * 100
        self.strut_radius_slider.setValue(30)    # 0.3 * 100 (默认匹配feature_data.json)
        self.strut_radius_slider.setSingleStep(5)  # 0.05 * 100
        self.strut_radius_slider.setTickPosition(QSlider.TicksBelow)
        self.strut_radius_slider.setTickInterval(5)  # 0.05 * 100

        self.strut_radius_value_label = QLabel("0.3")
        self.strut_radius_value_label.setObjectName("slider_value_label")
        self.strut_radius_value_label.setFixedWidth(52)  # 40*1.3=52

        strut_radius_layout.addWidget(self.strut_radius_slider)
        strut_radius_layout.addWidget(self.strut_radius_value_label)

        form_layout.addWidget(self.strut_radius_label, slider_row + 1, 0)
        form_layout.addWidget(self.strut_radius_container, slider_row + 1, 1)

        # Transform slider (0-8, step 1, default 8)
        self.slider_label = QLabel("Transform:")
        self.slider_label.setObjectName("field_label")

        self.transform_container = QWidget()
        transform_layout = QHBoxLayout(self.transform_container)
        transform_layout.setContentsMargins(0, 0, 0, 0)

        # Create slider with 0.1 resolution (0-8), default value at maximum (8)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("slider")
        self.slider.setMinimum(0)  # 0 * 10
        self.slider.setMaximum(80)  # 8 * 10
        self.slider.setValue(80)  # 8 * 10 (Maximum value)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(10)  # 1.0 * 10

        self.transform_value_label = QLabel("8.0")
        self.transform_value_label.setObjectName("slider_value_label")
        self.transform_value_label.setFixedWidth(52)  # 40*1.3=52

        transform_layout.addWidget(self.slider)
        transform_layout.addWidget(self.transform_value_label)

        # Add slider components to form layout
        form_layout.addWidget(self.slider_label, slider_row + 2, 0)
        form_layout.addWidget(self.transform_container, slider_row + 2, 1)

        # Connect cell type change to slider state update
        if "Cell type :" in self.dropdowns:
            self.dropdowns["Cell type :"].currentTextChanged.connect(self.update_slider_state)

        # Connect slider value changes to update methods
        self.cell_size_slider.valueChanged.connect(self.on_cell_size_slider_changed)
        self.strut_radius_slider.valueChanged.connect(self.on_strut_radius_slider_changed)
        self.slider.valueChanged.connect(self.on_slider_changed)

        # Store slider values for each cell type to maintain state
        self.slider_values = {}

        # Initialize slider state based on current cell type
        self.update_slider_state()

        # Apply initial range limitation (默认选中，限制参数范围)
        # 注意：这需要在复选框创建之后调用，所以会在后面的代码中调用


        # 添加上方弹性空间，使内容垂直居中
        left_layout.addStretch(1)

        left_layout.addWidget(form_frame)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.generate_button = QPushButton("Generate Script")
        self.generate_button.setObjectName("generate_button")
        self.generate_button.clicked.connect(self.generate_config)
        # 添加图标
        icon_path = get_icon_path("icon_generate.svg")
        if icon_path:
            self.generate_button.setIcon(QIcon(icon_path))
            self.generate_button.setIconSize(QSize(26, 26))  # 20*1.3=26

        button_layout.addWidget(self.generate_button)

        # 添加间距
        button_layout.addSpacing(26)  # 20*1.3=26

        # 添加PBS script按钮（与Generate Script相同大小）
        self.triangle_button = QPushButton("PBS Script")
        self.triangle_button.setObjectName("generate_button")  # 使用与Generate Script相同的样式
        self.triangle_button.setToolTip("批量生成脚本")  # 添加工具提示
        self.triangle_button.clicked.connect(self.on_triangle_button_clicked)
        # 添加图标
        icon_path = get_icon_path("icon_export.svg")
        if icon_path:
            self.triangle_button.setIcon(QIcon(icon_path))
            self.triangle_button.setIconSize(QSize(26, 26))  # 20*1.3=26

        button_layout.addWidget(self.triangle_button)
        button_layout.addStretch()

        left_layout.addLayout(button_layout)

        # 在PBS按钮后添加间距
        left_layout.addSpacing(39)  # 30*1.3=39

        # 添加下方弹性空间，使内容垂直居中
        left_layout.addStretch(1)

        # Right panel for visualization
        # 根据 visualization_widget 模块的设置决定是否添加可视化面板
        from visualization_widget import VISUALIZATION_AVAILABLE

        if VISUALIZATION_AVAILABLE:
            # 创建右侧容器,包含复选框和可视化widget
            right_panel = QWidget()
            right_panel_layout = QVBoxLayout(right_panel)
            right_panel_layout.setContentsMargins(10, 10, 10, 10)
            right_panel_layout.setSpacing(5)

            # 创建复选框容器(水平布局,放在右上角)
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setSpacing(20)

            # Lattice复选框和尺寸控件容器
            lattice_container = QWidget()
            lattice_layout = QHBoxLayout(lattice_container)
            lattice_layout.setContentsMargins(0, 0, 0, 0)
            lattice_layout.setSpacing(5)

            # Lattice复选框
            self.lattice_checkbox = QCheckBox("Lattice:")
            self.lattice_checkbox.setObjectName("viz_checkbox")
            self.lattice_checkbox.setChecked(False)
            self.lattice_checkbox.toggled.connect(self.on_lattice_toggle)
            icon_path = get_icon_path("icon_lattice.svg")
            if icon_path:
                self.lattice_checkbox.setIcon(QIcon(icon_path))
            lattice_layout.addWidget(self.lattice_checkbox)

            # Lattice尺寸输入框样式
            lattice_input_style = """
                QLineEdit {
                    background-color: #1e2330;
                    color: #c5d1de;
                    border: 2px solid #3d5a80;
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QLineEdit:hover {
                    border-color: #5a8bc0;
                }
                QLineEdit:focus {
                    border-color: #6c5ce7;
                }
            """
            lattice_label_style = "color: #6b7280; font-size: 14px;"

            # 创建整数验证器 (>=1)
            from PyQt5.QtGui import QIntValidator
            int_validator = QIntValidator(1, 99)

            # Lattice尺寸输入框: a×b×c
            self.lattice_a_input = QLineEdit("3")
            self.lattice_a_input.setFixedWidth(32)
            self.lattice_a_input.setAlignment(Qt.AlignCenter)
            self.lattice_a_input.setValidator(int_validator)
            self.lattice_a_input.setToolTip("X方向晶胞数量 (a)")
            self.lattice_a_input.setStyleSheet(lattice_input_style)
            self.lattice_a_input.editingFinished.connect(self.on_lattice_size_changed)
            lattice_layout.addWidget(self.lattice_a_input)

            label_x1 = QLabel("×")
            label_x1.setStyleSheet(lattice_label_style)
            lattice_layout.addWidget(label_x1)

            self.lattice_b_input = QLineEdit("3")
            self.lattice_b_input.setFixedWidth(32)
            self.lattice_b_input.setAlignment(Qt.AlignCenter)
            self.lattice_b_input.setValidator(int_validator)
            self.lattice_b_input.setToolTip("Y方向晶胞数量 (b)")
            self.lattice_b_input.setStyleSheet(lattice_input_style)
            self.lattice_b_input.editingFinished.connect(self.on_lattice_size_changed)
            lattice_layout.addWidget(self.lattice_b_input)

            label_x2 = QLabel("×")
            label_x2.setStyleSheet(lattice_label_style)
            lattice_layout.addWidget(label_x2)

            self.lattice_c_input = QLineEdit("2")
            self.lattice_c_input.setFixedWidth(32)
            self.lattice_c_input.setAlignment(Qt.AlignCenter)
            self.lattice_c_input.setValidator(int_validator)
            self.lattice_c_input.setToolTip("Z方向晶胞数量 (c)")
            self.lattice_c_input.setStyleSheet(lattice_input_style)
            self.lattice_c_input.editingFinished.connect(self.on_lattice_size_changed)
            lattice_layout.addWidget(self.lattice_c_input)

            checkbox_layout.addWidget(lattice_container)

            # Grid复选框
            self.grid_checkbox = QCheckBox("Grid Coordinate:")
            self.grid_checkbox.setObjectName("viz_checkbox")
            self.grid_checkbox.setChecked(True)  # 默认显示网格
            self.grid_checkbox.toggled.connect(self.on_grid_toggle)
            icon_path = get_icon_path("icon_grid.svg")
            if icon_path:
                self.grid_checkbox.setIcon(QIcon(icon_path))
            checkbox_layout.addWidget(self.grid_checkbox)

            # 参数范围限制复选框
            self.limit_range_checkbox = QCheckBox("Limit Range:")
            self.limit_range_checkbox.setObjectName("viz_checkbox")
            self.limit_range_checkbox.setChecked(True)  # 默认限制参数范围
            self.limit_range_checkbox.toggled.connect(self.on_limit_range_toggle)
            icon_path = get_icon_path("icon_parameters.svg")
            if icon_path:
                self.limit_range_checkbox.setIcon(QIcon(icon_path))
            checkbox_layout.addWidget(self.limit_range_checkbox)

            checkbox_layout.addStretch()

            # 添加到右侧面板
            right_panel_layout.addWidget(checkbox_container)

            # 创建可视化widget
            self.visualization_widget = CellVisualizationWidget()
            right_panel_layout.addWidget(self.visualization_widget)

            # 保存视图按钮 - 放在3D视图右下角
            self.save_view_btn = QPushButton()
            self.save_view_btn.setObjectName("save_view_btn")
            self.save_view_btn.setFixedSize(44, 44)
            self.save_view_btn.clicked.connect(self.on_save_view_clicked)
            self.save_view_btn.setToolTip("Save View as SVG")
            self.save_view_btn.setAttribute(Qt.WA_TranslucentBackground)
            icon_path = get_icon_path("icon_dataset.svg")
            if icon_path:
                self.save_view_btn.setIcon(QIcon(icon_path))
                self.save_view_btn.setIconSize(QSize(40, 40))
            self.save_view_btn.setStyleSheet("""
                QPushButton#save_view_btn {
                    background-color: #1a1d29;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton#save_view_btn:hover {
                    background-color: rgba(90, 139, 192, 0.3);
                }
                QPushButton#save_view_btn:pressed {
                    background-color: rgba(90, 139, 192, 0.5);
                }
            """)
            # 使用绝对定位将按钮放在右下角
            self.save_view_btn.setParent(self.visualization_widget)
            self.save_view_btn.raise_()

            # 连接resize事件以更新按钮位置
            def update_save_btn_position():
                if hasattr(self, 'save_view_btn') and hasattr(self, 'visualization_widget'):
                    btn = self.save_view_btn
                    parent = self.visualization_widget
                    # 右下角，留10px边距
                    x = parent.width() - btn.width() - 10
                    y = parent.height() - btn.height() - 10
                    btn.move(x, y)

            # 保存函数引用以便后续调用
            self.visualization_widget._update_save_btn_position = update_save_btn_position

            # 重写resizeEvent
            original_resize = self.visualization_widget.resizeEvent
            def new_resize_event(event):
                if original_resize:
                    original_resize(event)
                update_save_btn_position()
            self.visualization_widget.resizeEvent = new_resize_event

            # 初始位置更新（延迟执行以确保widget已布局）
            QTimer.singleShot(100, update_save_btn_position)

            # Add panels to splitter
            splitter.addWidget(left_panel)
            splitter.addWidget(right_panel)
            splitter.setSizes([650, 1040])  # 500*1.3=650, 800*1.3=1040
        else:
            # 不显示可视化，只添加左侧控制面板
            self.visualization_widget = None
            splitter.addWidget(left_panel)

        # 保存splitter引用以便后续保存设置
        self.splitter = splitter

        page_smart_gen_layout.addWidget(splitter)

        # Apply initial range limitation (复选框默认选中，应用参数范围限制)
        # update_visualization=False 避免使用默认值渲染，等 load_settings 加载用户设置后再渲染
        # Linux 环境下强制应用 Limit Range 模式
        if self.is_linux:
            self.on_limit_range_toggle(True, update_visualization=False)
        elif VISUALIZATION_AVAILABLE and hasattr(self, 'limit_range_checkbox'):
            self.on_limit_range_toggle(True, update_visualization=False)

        # 将第一个页面添加到页面栈
        self.page_stack.addWidget(page_smart_gen)

        # === 页面 1: Result Preview (仅 Windows 系统) ===
        # Linux 系统跳过 Page1 的创建
        if not self.is_linux:
            page_result_preview = QWidget()
            page_result_preview_layout = QVBoxLayout(page_result_preview)
            page_result_preview_layout.setSpacing(0)  # 最小化标题与功能区的间隔
            page_result_preview_layout.setContentsMargins(30, 10, 30, 30)

            # 创建标题区域（标题和说明在同一行）
            title_container2 = QWidget()
            title_container2_layout = QHBoxLayout(title_container2)
            title_container2_layout.setSpacing(15)
            title_container2_layout.setContentsMargins(0, 0, 0, 0)

            title_label2 = QLabel("Result Preview")
            title_label2.setObjectName("title")
            title_label2.setAlignment(Qt.AlignLeft)
            title_label2.setStyleSheet("font-size: 32px; font-weight: 600; color: #e1e8f0;")
            title_container2_layout.addWidget(title_label2)

            desc_label2 = QLabel("Quickly Preview the calculation results and conduct feature analysis.")
            desc_label2.setObjectName("description")
            desc_label2.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            desc_label2.setStyleSheet("font-size: 26px; color: #8a95a5;")
            title_container2_layout.addWidget(desc_label2)
            title_container2_layout.addStretch()

            page_result_preview_layout.addWidget(title_container2)

            # Create horizontal splitter for left panel and right panel
            splitter2 = QSplitter(Qt.Horizontal)
            splitter2.setStyleSheet("QSplitter::handle { background-color: #2d3548; }")

            # === Left Panel (Control + 3D Visualization) ===
            left_panel2 = QWidget()
            left_layout2 = QVBoxLayout(left_panel2)
            left_layout2.setSpacing(0)  # 移除间距，让框填满
            left_layout2.setContentsMargins(0, 0, 0, 0)  # 移除边距

            # Control panel
            form_frame2 = QFrame()
            form_frame2.setObjectName("form_frame")
            form_layout2 = QGridLayout(form_frame2)
            form_layout2.setSpacing(20)  # 统一间距
            form_layout2.setVerticalSpacing(20)  # 统一垂直间距
            form_layout2.setContentsMargins(26, 26, 26, 26)  # 统一内边距

            # Page 2 configurations: dropdown for Cell type and Curve type, sliders for others
            self.dropdowns_page2 = {}
            row = 0

            # Cell type dropdown
            cell_type_label = QLabel("Cell type:")
            cell_type_label.setObjectName("field_label")
            form_layout2.addWidget(cell_type_label, row, 0)

            cell_type_dropdown = QComboBox()
            cell_type_dropdown.setObjectName("dropdown")
            cell_type_dropdown.addItems([
                "Cubic", "BCC", "BCCZ", "Octet_truss", "AFCC", "Truncated_cube",
                "FCC", "FCCZ", "Tetrahedron_base", "Iso_truss", "G7", "FBCCZ",
                "FBCCXYZ", "Cuboctahedron_Z", "Diamond", "Rhombic", "Kelvin",
                "Auxetic", "Octahedron", "Truncated_Octoctahedron", "CubicRosette",
                "CBCC", "WeairePhelan", "DiamondPlus"
            ])
            # 初始化时从第一页获取 Cell type 的值（不再实时同步，只在切换页面时同步）
            # 先阻止信号，避免初始化时触发 plot_stress_strain_curve
            cell_type_dropdown.blockSignals(True)
            if "Cell type :" in self.dropdowns:
                page1_cell_type = self.dropdowns["Cell type :"]
                cell_type_dropdown.setCurrentIndex(page1_cell_type.currentIndex())
            cell_type_dropdown.blockSignals(False)
            form_layout2.addWidget(cell_type_dropdown, row, 1)
            self.dropdowns_page2["Cell type:"] = cell_type_dropdown
            cell_type_dropdown.currentIndexChanged.connect(self.plot_stress_strain_curve)
            row += 1

            # Curve type dropdown
            curve_type_label = QLabel("Curve type:")
            curve_type_label.setObjectName("field_label")
            form_layout2.addWidget(curve_type_label, row, 0)

            curve_type_dropdown = QComboBox()
            curve_type_dropdown.setObjectName("dropdown")
            # 先阻止信号，避免初始化时触发 plot_stress_strain_curve
            curve_type_dropdown.blockSignals(True)
            # 默认包含所有可能的曲线类型
            curve_type_dropdown.addItems(["StaCompre_curve", "StaShear_curve", "DynaCompre_curve", "DynaShear_curve"])
            curve_type_dropdown.blockSignals(False)
            form_layout2.addWidget(curve_type_dropdown, row, 1)
            self.dropdowns_page2["Curve type:"] = curve_type_dropdown
            curve_type_dropdown.currentIndexChanged.connect(self.plot_stress_strain_curve)
            row += 1

            # Cell size slider - 创建独立的Page 2 slider
            cell_size_label2 = QLabel("Cell size:")
            cell_size_label2.setObjectName("field_label")
            form_layout2.addWidget(cell_size_label2, row, 0)

            cell_size_container2 = QWidget()
            cell_size_layout2 = QHBoxLayout(cell_size_container2)
            cell_size_layout2.setContentsMargins(0, 0, 0, 0)

            self.cell_size_slider_page2 = QSlider(Qt.Horizontal)
            self.cell_size_slider_page2.setObjectName("slider")
            self.cell_size_slider_page2.setMinimum(30)  # 3.0 * 10
            self.cell_size_slider_page2.setMaximum(100)  # 10.0 * 10
            self.cell_size_slider_page2.setValue(50)  # 5.0 * 10
            self.cell_size_slider_page2.setTickPosition(QSlider.TicksBelow)
            self.cell_size_slider_page2.setTickInterval(5)  # 0.5 * 10

            self.cell_size_value_label_page2 = QLabel("5.0")
            self.cell_size_value_label_page2.setObjectName("slider_value_label")
            self.cell_size_value_label_page2.setFixedWidth(52)  # 40*1.3=52

            cell_size_layout2.addWidget(self.cell_size_slider_page2)
            cell_size_layout2.addWidget(self.cell_size_value_label_page2)

            form_layout2.addWidget(cell_size_container2, row, 1)
            row += 1

            # Strut radius slider - Page 2也使用值列表方式（与Page 1完全一致）
            strut_radius_label2 = QLabel("Strut radius:")
            strut_radius_label2.setObjectName("field_label")
            form_layout2.addWidget(strut_radius_label2, row, 0)

            strut_radius_container2 = QWidget()
            strut_radius_layout2 = QHBoxLayout(strut_radius_container2)
            strut_radius_layout2.setContentsMargins(0, 0, 0, 0)

            self.strut_radius_slider_page2 = QSlider(Qt.Horizontal)
            self.strut_radius_slider_page2.setObjectName("slider")
            # 初始状态：Limit Range ON (默认选中)，使用与Page 1相同的设置（直接值方式）
            self.strut_radius_slider_page2.setMinimum(30)  # 0.3 * 100
            self.strut_radius_slider_page2.setMaximum(50)  # 0.5 * 100
            self.strut_radius_slider_page2.setValue(30)    # 0.3 * 100 (默认匹配feature_data.json)
            self.strut_radius_slider_page2.setSingleStep(5)  # 0.05 * 100
            self.strut_radius_slider_page2.setTickPosition(QSlider.TicksBelow)
            self.strut_radius_slider_page2.setTickInterval(5)  # 0.05 * 100

            self.strut_radius_value_label_page2 = QLabel("0.3")
            self.strut_radius_value_label_page2.setObjectName("slider_value_label")
            self.strut_radius_value_label_page2.setFixedWidth(52)  # 40*1.3=52

            strut_radius_layout2.addWidget(self.strut_radius_slider_page2)
            strut_radius_layout2.addWidget(self.strut_radius_value_label_page2)

            form_layout2.addWidget(strut_radius_container2, row, 1)
            row += 1

            # Transform slider - Page 2与Page 1完全一致
            transform_label2 = QLabel("Transform:")
            transform_label2.setObjectName("field_label")
            form_layout2.addWidget(transform_label2, row, 0)

            transform_container2 = QWidget()
            transform_layout2 = QHBoxLayout(transform_container2)
            transform_layout2.setContentsMargins(0, 0, 0, 0)

            self.transform_slider_page2 = QSlider(Qt.Horizontal)
            self.transform_slider_page2.setObjectName("slider")
            # 初始状态：Limit Range ON (默认选中)，范围0-8，步长1
            self.transform_slider_page2.setMinimum(0)
            self.transform_slider_page2.setMaximum(8)
            self.transform_slider_page2.setValue(8)  # 默认值8
            self.transform_slider_page2.setTickPosition(QSlider.TicksBelow)
            self.transform_slider_page2.setTickInterval(1)

            self.transform_value_label_page2 = QLabel("8")
            self.transform_value_label_page2.setObjectName("slider_value_label")
            self.transform_value_label_page2.setFixedWidth(52)  # 40*1.3=52

            transform_layout2.addWidget(self.transform_slider_page2)
            transform_layout2.addWidget(self.transform_value_label_page2)

            form_layout2.addWidget(transform_container2, row, 1)

            # Page 2 滑块值变化时只更新自己的标签和曲线图（不再实时同步到 Page 1）
            def update_cell_size_page2_label(v):
                """Page 2 Cell size 滑块值变化时更新标签"""
                self.cell_size_value_label_page2.setText(f"{v/10.0:.1f}")
                if hasattr(self, 'ax') and hasattr(self, 'canvas'):
                    self.plot_stress_strain_curve()

            def update_radius_page2_label(v):
                """Page 2 Strut radius 滑块值变化时更新标签"""
                is_limited = self.is_limit_range_mode()
                if is_limited:
                    # Limit Range ON: 强制对齐到步长5 (0.05)
                    aligned_v = round(v / 5) * 5
                    if aligned_v != v:
                        self.strut_radius_slider_page2.blockSignals(True)
                        self.strut_radius_slider_page2.setValue(aligned_v)
                        self.strut_radius_slider_page2.blockSignals(False)
                        v = aligned_v
                radius = v / 100.0
                self.strut_radius_value_label_page2.setText(f"{radius:.2f}")
                if hasattr(self, 'ax') and hasattr(self, 'canvas'):
                    self.plot_stress_strain_curve()

            def update_transform_page2_label(v):
                """Page 2 Transform 滑块值变化时更新标签"""
                is_limited = self.is_limit_range_mode()
                if is_limited:
                    self.transform_value_label_page2.setText(str(int(v)))
                else:
                    self.transform_value_label_page2.setText(f"{v/10.0:.1f}")
                if hasattr(self, 'ax') and hasattr(self, 'canvas'):
                    self.plot_stress_strain_curve()

            self.cell_size_slider_page2.valueChanged.connect(update_cell_size_page2_label)
            self.strut_radius_slider_page2.valueChanged.connect(update_radius_page2_label)
            self.transform_slider_page2.valueChanged.connect(update_transform_page2_label)

            # === Load Result and Statistics Buttons (在Feature Summary上方) ===
            row += 1
            button_container_left = QWidget()
            button_layout_left = QHBoxLayout(button_container_left)
            button_layout_left.setContentsMargins(0, 8, 0, 8)
            button_layout_left.setSpacing(15)

            small_btn_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a7ba7, stop:1 #3d5a80);
                    color: #ffffff;
                    border: none;
                    padding: 8px 20px;
                    font-size: 18px;
                    font-weight: 600;
                    border-radius: 6px;
                    min-height: 33px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5a8bc0, stop:1 #4a7ba7);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3d5a80, stop:1 #2d4660);
                }
            """

            generate_button2 = QPushButton("Load Result")
            generate_button2.setStyleSheet(small_btn_style)
            generate_button2.clicked.connect(self.load_result)
            icon_path = get_icon_path("icon_reload.svg")
            if icon_path:
                generate_button2.setIcon(QIcon(icon_path))
                generate_button2.setIconSize(QSize(20, 20))
            button_layout_left.addWidget(generate_button2, 1)  # stretch factor 1

            statistics_button = QPushButton("Statistics")
            statistics_button.setStyleSheet(small_btn_style)
            icon_path = get_icon_path("icon_csv.svg")
            if icon_path:
                statistics_button.setIcon(QIcon(icon_path))
                statistics_button.setIconSize(QSize(20, 20))
            statistics_button.clicked.connect(self.show_statistics_3d)
            button_layout_left.addWidget(statistics_button, 1)  # stretch factor 1

            form_layout2.addWidget(button_container_left, row, 0, 1, 2)

            # 在form_frame2中添加Feature Summary文本框 (放在按钮下方)
            row += 1
            self.summary_text = QTextEdit()
            self.summary_text.setReadOnly(True)
            self.summary_text.setStyleSheet("""
                QTextEdit {
                    background-color: #262b3d;
                    color: #c5d1de;
                    border: none;
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 16px;
                    font-family: 'Consolas', 'Courier New', monospace;
                }
                QScrollBar:vertical {
                    background-color: #1e2330;
                    width: 12px;
                    border-radius: 6px;
                    margin: 2px;
                }
                QScrollBar::handle:vertical {
                    background-color: #3d5a80;
                    border-radius: 5px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #4a6fa5;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)
            self.summary_text.setPlaceholderText("Feature data will be displayed here...")
            form_layout2.setRowStretch(row, 1)
            form_layout2.addWidget(self.summary_text, row, 0, 1, 2)

            left_layout2.addWidget(form_frame2)

            # 第二个页面不需要3D可视化 - 移除stretch，让form_frame2填充整个左侧面板
            splitter2.addWidget(left_panel2)

            # === Right Panel (Plot + Buttons) ===
            right_panel2 = QWidget()
            right_layout2 = QVBoxLayout(right_panel2)
            right_layout2.setSpacing(15)
            right_layout2.setContentsMargins(0, 0, 0, 0)

            # Feature visibility checkboxes
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setContentsMargins(10, 5, 10, 5)
            checkbox_layout.setSpacing(15)

            checkbox_style = """
                QCheckBox {
                    color: #c5d1de;
                    font-size: 18px;
                    font-weight: 500;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 20px;
                    height: 20px;
                    border-radius: 4px;
                    border: 2px solid #5a8bc0;
                    background-color: #1e2330;
                }
                QCheckBox::indicator:checked {
                    background-color: #6c5ce7;
                    border: 2px solid #6c5ce7;
                }
                QCheckBox::indicator:hover {
                    border: 2px solid #6c5ce7;
                }
            """

            self.cb_ea = QCheckBox("EA")
            self.cb_ea.setChecked(True)
            self.cb_ea.setStyleSheet(checkbox_style)
            self.cb_ea.stateChanged.connect(self._refresh_plot)

            self.cb_stiffness = QCheckBox("Stiffness")
            self.cb_stiffness.setChecked(True)
            self.cb_stiffness.setStyleSheet(checkbox_style)
            self.cb_stiffness.stateChanged.connect(self._refresh_plot)

            self.cb_peak = QCheckBox("Densified")
            self.cb_peak.setChecked(True)
            self.cb_peak.setStyleSheet(checkbox_style)
            self.cb_peak.stateChanged.connect(self._refresh_plot)

            self.cb_yield = QCheckBox("Yield")
            self.cb_yield.setChecked(True)
            self.cb_yield.setStyleSheet(checkbox_style)
            self.cb_yield.stateChanged.connect(self._refresh_plot)

            self.cb_density = QCheckBox("Density")
            self.cb_density.setChecked(True)
            self.cb_density.setStyleSheet(checkbox_style)
            self.cb_density.stateChanged.connect(self._refresh_plot)

            show_label = QLabel("Show:")
            show_label.setStyleSheet("color: #8a95a5; font-size: 18px; font-weight: 500;")
            checkbox_layout.addWidget(show_label)
            checkbox_layout.addWidget(self.cb_ea)
            checkbox_layout.addWidget(self.cb_stiffness)
            checkbox_layout.addWidget(self.cb_peak)
            checkbox_layout.addWidget(self.cb_yield)
            checkbox_layout.addWidget(self.cb_density)
            checkbox_layout.addStretch()

            right_layout2.addWidget(checkbox_container)

            # Top: Matplotlib plot area (放大尺寸)
            try:
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
                from matplotlib.figure import Figure

                self.figure = Figure(figsize=(13, 9), facecolor='#1e2330')  # 10*1.3=13, 7*1.3≈9
                self.canvas = FigureCanvas(self.figure)
                self.canvas.setMinimumHeight(650)  # 500*1.3=650
                self.canvas.setStyleSheet("background-color: #1e2330; border: 1px solid #3d5a80; border-radius: 10px;")

                # Create initial empty plot
                self.ax = self.figure.add_subplot(111)
                self.ax.set_facecolor('#1e2330')
                self.ax.tick_params(colors='#c5d1de', labelsize=14)
                self.ax.spines['bottom'].set_color('#3d5a80')
                self.ax.spines['top'].set_color('#3d5a80')
                self.ax.spines['left'].set_color('#3d5a80')
                self.ax.spines['right'].set_color('#3d5a80')
                self.ax.set_title('Stress-Strain Curve', color='#e1e8f0', fontsize=21)  # 16*1.3≈21
                self.ax.set_xlabel('Strain', color='#c5d1de', fontsize=16)  # 12*1.3≈16
                self.ax.set_ylabel('Stress (MPa)', color='#c5d1de', fontsize=16)
                self.ax.grid(True, alpha=0.2, color='#3d5a80')

                right_layout2.addWidget(self.canvas)

            except ImportError:
                plot_placeholder = QFrame()
                plot_placeholder.setObjectName("form_frame")
                plot_placeholder.setMinimumHeight(650)  # 500*1.3=650
                plot_layout = QVBoxLayout(plot_placeholder)
                plot_label = QLabel("Interactive Plot Area\n\n(Matplotlib not available)")
                plot_label.setAlignment(Qt.AlignCenter)
                plot_label.setStyleSheet("color: #8a95a5; font-size: 21px;")  # 16*1.3≈21
                plot_layout.addWidget(plot_label)
                right_layout2.addWidget(plot_placeholder)

            # === Feature Search Section (compact single row, no frame) ===
            search_container = QWidget()
            search_layout = QHBoxLayout(search_container)
            search_layout.setContentsMargins(5, 4, 5, 4)
            search_layout.setSpacing(10)

            # 统一样式 - 高度一致，字体更大
            combo_style = """
                QComboBox {
                    background-color: #1e2330;
                    color: #c5d1de;
                    border: 1px solid #3d5a80;
                    border-radius: 6px;
                    padding: 10px 14px;
                    font-size: 20px;
                    min-height: 24px;
                }
                QComboBox::drop-down { border: none; }
                QComboBox QAbstractItemView {
                    background-color: #1e2330;
                    color: #c5d1de;
                    selection-background-color: #3d5a80;
                    font-size: 20px;
                }
            """

            input_style = """
                QLineEdit {
                    background-color: #1e2330;
                    color: #c5d1de;
                    border: 1px solid #3d5a80;
                    border-radius: 6px;
                    padding: 10px 12px;
                    font-size: 20px;
                    min-height: 24px;
                }
                QLineEdit:focus { border: 1px solid #4a6fa5; }
            """

            btn_style = """
                QPushButton {
                    background-color: #3d5a80;
                    color: #e1e8f0;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 24px;
                    font-size: 20px;
                    font-weight: bold;
                    min-height: 24px;
                }
                QPushButton:hover { background-color: #4a6fa5; }
                QPushButton:pressed { background-color: #2d4a70; }
            """

            # Feature 1 dropdown (auto-sizing)
            self.feature1_combo = QComboBox()
            self.feature1_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            self.feature1_combo.setStyleSheet(combo_style)
            self.feature1_combo.addItems([
                "None", "density",
                "comp_EA", "comp_stiffness", "comp_densified", "comp_yield",
                "shear_EA", "shear_stiffness", "shear_yield",
                "dyna_comp_EA", "dyna_shear_EA"
            ])
            self.feature1_combo.currentIndexChanged.connect(self._on_feature1_changed)
            search_layout.addWidget(self.feature1_combo)

            # Range label 1
            self.range_label1 = QLabel("")
            self.range_label1.setStyleSheet("color: #8a95a5; font-size: 18px;")
            search_layout.addWidget(self.range_label1)

            # Value input 1
            self.value1_input = QLineEdit()
            self.value1_input.setPlaceholderText("Value")
            self.value1_input.setFixedWidth(110)
            self.value1_input.setStyleSheet(input_style)
            search_layout.addWidget(self.value1_input)

            # Separator
            sep_label = QLabel("|")
            sep_label.setStyleSheet("color: #5a6a7a; font-size: 24px;")
            search_layout.addWidget(sep_label)

            # Feature 2 dropdown (auto-sizing)
            self.feature2_combo = QComboBox()
            self.feature2_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            self.feature2_combo.setStyleSheet(combo_style)
            self.feature2_combo.addItems([
                "None", "density",
                "comp_EA", "comp_stiffness", "comp_densified", "comp_yield",
                "shear_EA", "shear_stiffness", "shear_yield",
                "dyna_comp_EA", "dyna_shear_EA"
            ])
            self.feature2_combo.currentIndexChanged.connect(self._on_feature2_changed)
            search_layout.addWidget(self.feature2_combo)

            # Range label 2
            self.range_label2 = QLabel("")
            self.range_label2.setStyleSheet("color: #8a95a5; font-size: 18px;")
            search_layout.addWidget(self.range_label2)

            # Value input 2
            self.value2_input = QLineEdit()
            self.value2_input.setPlaceholderText("Value")
            self.value2_input.setFixedWidth(110)
            self.value2_input.setStyleSheet(input_style)
            search_layout.addWidget(self.value2_input)

            # Search button
            self.search_btn = QPushButton("Search")
            self.search_btn.setStyleSheet(btn_style)
            self.search_btn.clicked.connect(self._on_search_clicked)
            search_layout.addWidget(self.search_btn)

            search_layout.addStretch()

            right_layout2.addWidget(search_container)

            # 初始化特征数据库
            self.feature_df = None
            self.feature_ranges = {}
            self._load_feature_database()

            splitter2.addWidget(right_panel2)

            # Set splitter sizes: left slightly larger, right slightly smaller
            splitter2.setSizes([1050, 998])

            page_result_preview_layout.addWidget(splitter2)

            # 将第二个页面添加到页面栈（仅 Windows）
            self.page_stack.addWidget(page_result_preview)
            print("Windows 系统检测到，Page1（结果预览页面）已启用")

            # Page 2 创建完成后，重新应用 Limit Range 设置到 Page 2 的 sliders
            is_limited = self.is_limit_range_mode()
            self.on_limit_range_toggle(is_limited, update_visualization=False)
        else:
            print("Linux 系统检测到，已禁用 Page1（结果预览页面）")
            # Linux 环境下也需要应用 Limit Range 设置
            self.on_limit_range_toggle(True, update_visualization=False)

        # 将页面栈添加到主布局
        main_layout.addWidget(self.page_stack)

        # Initialize visualization with default cubic display
        # 只在启用可视化时初始化
        # 延迟到400ms以确保在load_settings和update_ui_after_load之后执行
        if VISUALIZATION_AVAILABLE:
            QTimer.singleShot(400, self.init_default_visualization)

    def save_settings(self):
        """保存当前UI设置到JSON文件"""
        try:
            # 不再保存相机状态，每次启动使用默认视角
            settings = {
                "dropdowns": {},
                "checkboxes": {},
                "slider_value": self.slider.value() if self.slider else 8,
                "cell_size_slider_value": self.cell_size_slider.value() if hasattr(self, 'cell_size_slider') else 50,
                "strut_radius_slider_value": self.strut_radius_slider.value() if hasattr(self, 'strut_radius_slider') else 35,
                "slider_values": getattr(self, 'slider_values', {}),
                "batch_enabled": getattr(self, 'batch_checkbox', None) and self.batch_checkbox.isChecked() if hasattr(self, 'batch_checkbox') else False,
                "batch_config": getattr(self, 'batch_config', {}),
                "splitter_sizes": self.splitter.sizes() if hasattr(self, 'splitter') else [600, 810],
                # "lattice_checked": self.lattice_checkbox.isChecked() if hasattr(self, 'lattice_checkbox') else False,  # 不再保存lattice状态
                "grid_checked": self.grid_checkbox.isChecked() if hasattr(self, 'grid_checkbox') else True,
                "limit_range_checked": self.limit_range_checkbox.isChecked() if hasattr(self, 'limit_range_checkbox') else True
            }

            # 保存下拉框的当前选择
            for label_text, dropdown in self.dropdowns.items():
                settings["dropdowns"][label_text] = dropdown.currentText()

            # 保存复选框状态
            for label_text, checkbox in self.checkboxes.items():
                settings["checkboxes"][label_text] = checkbox.isChecked()

            # 写入JSON文件
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            print(f"设置已保存到: {self.settings_file}")

        except Exception as e:
            print(f"保存设置失败: {str(e)}")

    def load_settings(self):
        """从JSON文件加载UI设置"""
        try:
            if not os.path.exists(self.settings_file):
                print("设置文件不存在，使用默认设置")
                # 即使无设置文件，也需要初始化 Page 2 曲线
                QTimer.singleShot(300, self.update_ui_after_load)
                return

            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # Block signals to avoid triggering multiple updates during load
            # Block Page1 dropdown signals (especially Cell type dropdown)
            if hasattr(self, "dropdowns"):
                for dropdown in self.dropdowns.values():
                    dropdown.blockSignals(True)

            # Block Page2 dropdown signals
            if hasattr(self, "dropdowns_page2"):
                for dropdown in self.dropdowns_page2.values():
                    dropdown.blockSignals(True)

            # Block all sliders signals
            if hasattr(self, 'cell_size_slider'):
                self.cell_size_slider.blockSignals(True)
            if hasattr(self, 'cell_size_slider_page2'):
                self.cell_size_slider_page2.blockSignals(True)
            if hasattr(self, 'strut_radius_slider'):
                self.strut_radius_slider.blockSignals(True)
            if hasattr(self, 'strut_radius_slider_page2'):
                self.strut_radius_slider_page2.blockSignals(True)
            if hasattr(self, 'slider'):
                self.slider.blockSignals(True)
            if hasattr(self, 'transform_slider_page2'):
                self.transform_slider_page2.blockSignals(True)

            # Block visualization checkboxes to avoid premature updates
            if hasattr(self, 'lattice_checkbox'):
                self.lattice_checkbox.blockSignals(True)
            if hasattr(self, 'grid_checkbox'):
                self.grid_checkbox.blockSignals(True)
            if hasattr(self, 'limit_range_checkbox'):
                self.limit_range_checkbox.blockSignals(True)

            # 恢复下拉框选择
            if "dropdowns" in settings:
                for label_text, value in settings["dropdowns"].items():
                    if label_text in self.dropdowns:
                        dropdown = self.dropdowns[label_text]
                        index = dropdown.findText(value)
                        if index >= 0:
                            dropdown.setCurrentIndex(index)

            # 恢复复选框状态
            if "checkboxes" in settings:
                for label_text, checked in settings["checkboxes"].items():
                    if label_text in self.checkboxes:
                        self.checkboxes[label_text].setChecked(checked)

            # 不再恢复lattice checkbox状态 - 始终保持默认OFF
            # if "lattice_checked" in settings and hasattr(self, 'lattice_checkbox'):
            #     self.lattice_checkbox.blockSignals(True)
            #     self.lattice_checkbox.setChecked(settings["lattice_checked"])
            #     self.lattice_checkbox.blockSignals(False)
            #     if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            #         self.visualization_widget.toggle_lattice(settings["lattice_checked"])

            # 恢复grid checkbox状态
            if "grid_checked" in settings and hasattr(self, 'grid_checkbox'):
                self.grid_checkbox.blockSignals(True)
                self.grid_checkbox.setChecked(settings["grid_checked"])
                self.grid_checkbox.blockSignals(False)
                # 只设置标志，不触发update_visualization
                if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
                    self.visualization_widget.toggle_grid(settings["grid_checked"])

            # 恢复limit range checkbox状态
            # Linux 环境下强制使用 Limit Range 模式参数
            if platform.system() == "Linux":
                limit_range_checked = True  # Linux 强制限制参数范围
            elif "limit_range_checked" in settings:
                limit_range_checked = settings["limit_range_checked"]
            else:
                limit_range_checked = True  # 默认值

            if hasattr(self, 'limit_range_checkbox'):
                self.limit_range_checkbox.setChecked(limit_range_checked)

            # 手动调用on_limit_range_toggle来更新slider范围(信号被block,不会自动触发)
            # 这样可以确保slider范围和label在恢复slider值之前就是正确的
            # update_visualization=False 避免在加载设置时重复更新可视化
            if hasattr(self, 'on_limit_range_toggle'):
                self.on_limit_range_toggle(limit_range_checked, update_visualization=False)

            # 恢复滑块值（如果没有保存的值，使用默认值8）
            # 注意: 此时slider范围已经根据limit_range_checked正确设置了
            if "slider_value" in settings and self.slider:
                self.slider.setValue(settings["slider_value"])
            elif self.slider:
                self.slider.setValue(8)

            # 恢复 cell_size slider 值
            if "cell_size_slider_value" in settings and hasattr(self, 'cell_size_slider'):
                self.cell_size_slider.setValue(settings["cell_size_slider_value"])

            # 恢复 strut_radius slider 值
            if "strut_radius_slider_value" in settings and hasattr(self, 'strut_radius_slider'):
                self.strut_radius_slider.setValue(settings["strut_radius_slider_value"])

            # 恢复滑块值字典
            if "slider_values" in settings:
                self.slider_values = settings["slider_values"]


            # 恢复批量设置
            if "batch_enabled" in settings and hasattr(self, 'batch_checkbox') and self.batch_checkbox:
                self.batch_checkbox.setChecked(settings["batch_enabled"])
                if hasattr(self, 'batch_config_button') and self.batch_config_button:
                    self.batch_config_button.setEnabled(settings["batch_enabled"])

            if "batch_config" in settings:
                self.batch_config = settings["batch_config"]

            # 恢复splitter尺寸
            if "splitter_sizes" in settings and hasattr(self, 'splitter'):
                QTimer.singleShot(100, lambda: self.splitter.setSizes(settings["splitter_sizes"]))

            # 不再恢复相机状态，每次启动使用默认视角

            # Unblock all signals
            # Unblock Page1 dropdown signals
            if hasattr(self, "dropdowns"):
                for dropdown in self.dropdowns.values():
                    dropdown.blockSignals(False)

            # Unblock Page2 dropdown signals
            if hasattr(self, "dropdowns_page2"):
                for dropdown in self.dropdowns_page2.values():
                    dropdown.blockSignals(False)

            # Unblock all sliders signals
            if hasattr(self, 'cell_size_slider'):
                self.cell_size_slider.blockSignals(False)
            if hasattr(self, 'cell_size_slider_page2'):
                self.cell_size_slider_page2.blockSignals(False)
            if hasattr(self, 'strut_radius_slider'):
                self.strut_radius_slider.blockSignals(False)
            if hasattr(self, 'strut_radius_slider_page2'):
                self.strut_radius_slider_page2.blockSignals(False)
            if hasattr(self, 'slider'):
                self.slider.blockSignals(False)
            if hasattr(self, 'transform_slider_page2'):
                self.transform_slider_page2.blockSignals(False)

            # Unblock visualization checkboxes
            if hasattr(self, 'lattice_checkbox'):
                self.lattice_checkbox.blockSignals(False)
            if hasattr(self, 'grid_checkbox'):
                self.grid_checkbox.blockSignals(False)
            if hasattr(self, 'limit_range_checkbox'):
                self.limit_range_checkbox.blockSignals(False)

            print(f"设置已从 {self.settings_file} 加载")

            # 更新相关UI状态
            QTimer.singleShot(300, self.update_ui_after_load)

        except Exception as e:
            print(f"加载设置失败: {str(e)}")

    def update_ui_after_load(self):
        """加载设置后更新UI状态"""
        try:
            # 更新Compression和Shear标签颜色
            self.update_checkbox_labels()

            # 更新滑块状态
            self.update_slider_state()

            # 不在这里更新可视化，因为 init_default_visualization() 已经处理了
            # 避免重复调用导致多次渲染

            # 刷新 Curve type 下拉列表（从当前 feature_data.json 读取可用曲线类型）
            self._refresh_curve_type_dropdown()

            # 自动刷新曲线（使用当前 UI 选择，而不是重置到 feature_data.json 的第一个结构）
            # 这样可以保持用户上次的设置
            if hasattr(self, "dropdowns_page2") and "Cell type:" in self.dropdowns_page2:
                self.plot_stress_strain_curve()

        except Exception as e:
            print(f"更新UI状态失败: {str(e)}")

    def _refresh_curve_type_dropdown(self):
        """从 feature_data.json 读取可用曲线类型并更新下拉列表"""
        import json
        try:
            feature_data_path = os.path.join(BASE_DIR, "work", "feature_data.json")
            if not os.path.exists(feature_data_path):
                return

            with open(feature_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                return

            # 收集所有结构中出现的曲线类型
            all_curve_types = set()
            for structure_key, structure_data in data.items():
                for key in structure_data.keys():
                    if key.endswith('_curve'):
                        all_curve_types.add(key)

            if not all_curve_types:
                return

            # 按固定顺序排列（优先静态，其次动态）
            ordered_types = []
            for ct in ['StaCompre_curve', 'StaShear_curve', 'DynaCompre_curve', 'DynaShear_curve']:
                if ct in all_curve_types:
                    ordered_types.append(ct)
            # 添加其他未知曲线类型
            for ct in sorted(all_curve_types):
                if ct not in ordered_types:
                    ordered_types.append(ct)

            # 更新下拉列表
            if "Curve type:" in self.dropdowns_page2:
                combo = self.dropdowns_page2["Curve type:"]
                current_text = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(ordered_types)
                # 恢复之前选择的曲线类型（如果仍然存在）
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                combo.blockSignals(False)
                print(f"Curve type 下拉列表已更新: {ordered_types}")

        except Exception as e:
            print(f"刷新 Curve type 下拉列表失败: {str(e)}")

    def _init_page2_curve(self):
        """初始化 Page 2 曲线图（使用当前 UI 设置绘制曲线）"""
        try:
            # 直接绘制曲线，使用当前 UI 选择的参数
            # 不再重置到 feature_data.json 的第一个结构
            if hasattr(self, "dropdowns_page2") and "Cell type:" in self.dropdowns_page2:
                self.plot_stress_strain_curve()
        except Exception as e:
            print(f"初始化 Page 2 曲线失败: {str(e)}")

    def _auto_load_feature_data(self, file_path):
        """自动加载 feature_data.json 并更新 UI"""
        import json
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                return

            # 获取第一个结构名称作为默认值
            structure_names = list(data.keys())
            first_structure = structure_names[0]

            # 解析结构名称: Cell_Size_Radius_Slider
            parts = first_structure.split('_')
            if len(parts) >= 4:
                cell_type = parts[0]
                cell_size_str = parts[1]
                radius_str = parts[2].replace('p', '.')
                transform_str = parts[3]

                # 阻止所有信号，避免设置值时触发多次绘图
                if "Cell type:" in self.dropdowns_page2:
                    self.dropdowns_page2["Cell type:"].blockSignals(True)
                if hasattr(self, 'cell_size_slider_page2'):
                    self.cell_size_slider_page2.blockSignals(True)
                if hasattr(self, 'strut_radius_slider_page2'):
                    self.strut_radius_slider_page2.blockSignals(True)
                if hasattr(self, 'transform_slider_page2'):
                    self.transform_slider_page2.blockSignals(True)

                # 更新 Cell type dropdown
                if "Cell type:" in self.dropdowns_page2:
                    combo = self.dropdowns_page2["Cell type:"]
                    index = combo.findText(cell_type)
                    if index >= 0:
                        combo.setCurrentIndex(index)

                # 更新 Cell size slider
                try:
                    cell_size_value = float(cell_size_str)
                    slider_value = int(cell_size_value * 10)
                    if hasattr(self, 'cell_size_slider_page2'):
                        self.cell_size_slider_page2.setValue(slider_value)
                        self.cell_size_value_label_page2.setText(f"{cell_size_value:.1f}")
                except ValueError:
                    pass

                # 更新 Strut radius slider
                try:
                    radius_value = float(radius_str)
                    slider_value = int(radius_value * 100)
                    if hasattr(self, 'strut_radius_slider_page2'):
                        self.strut_radius_slider_page2.setValue(slider_value)
                        self.strut_radius_value_label_page2.setText(f"{radius_value:.2f}")
                except ValueError:
                    pass

                # 更新 Transform slider
                try:
                    transform_value = float(transform_str)
                    is_limited = self.is_limit_range_mode()
                    if is_limited:
                        slider_val = int(transform_value)
                        label_text = str(slider_val)
                    else:
                        slider_val = int(transform_value * 10)
                        label_text = f"{transform_value:.1f}"
                    if hasattr(self, 'transform_slider_page2'):
                        self.transform_slider_page2.setValue(slider_val)
                        self.transform_value_label_page2.setText(label_text)
                except ValueError:
                    pass

                # 恢复所有信号
                if "Cell type:" in self.dropdowns_page2:
                    self.dropdowns_page2["Cell type:"].blockSignals(False)
                if hasattr(self, 'cell_size_slider_page2'):
                    self.cell_size_slider_page2.blockSignals(False)
                if hasattr(self, 'strut_radius_slider_page2'):
                    self.strut_radius_slider_page2.blockSignals(False)
                if hasattr(self, 'transform_slider_page2'):
                    self.transform_slider_page2.blockSignals(False)

            # 绘制曲线（只调用一次）
            if hasattr(self, "dropdowns_page2") and "Cell type:" in self.dropdowns_page2:
                self.plot_stress_strain_curve()

            print(f"自动加载 feature_data.json 完成: {first_structure}")

        except Exception as e:
            print(f"自动加载 feature_data.json 失败: {str(e)}")

    def update_checkbox_labels(self):
        """更新复选框标签颜色"""
        for label_text in ["Compression:", "Shear:"]:
            if label_text in self.checkbox_labels:
                checkbox = self.checkboxes.get(label_text)
                if checkbox and checkbox.isChecked():
                    # Checkbox is checked - set label color to blue (dark theme)
                    color = "#5a8bc0"
                    self.checkbox_labels[label_text].setStyleSheet(f"color: {color}; font-size: 29px; font-weight: 600; padding: 10px 0;")
                else:
                    # Checkbox is unchecked - set label color to gray (dark theme)
                    self.checkbox_labels[label_text].setStyleSheet("color: #6b7785; font-size: 29px; font-weight: 600; padding: 10px 0;")

    def closeEvent(self, event):
        """窗口关闭时保存设置"""
        self.save_settings()
        event.accept()

    def switch_to_page(self, page_index):
        """切换到指定页面，并同步参数"""
        if hasattr(self, 'page_stack'):
            # Linux 系统只允许停留在 Page 0
            if self.is_linux and page_index != 0:
                print(f"Linux 系统禁止切换到页面 {page_index}，保持在 Page 0")
                return

            current_page = self.page_stack.currentIndex()

            # 切换页面前，根据来源页面同步参数到目标页面
            if current_page != page_index:
                self._sync_params_on_page_switch(current_page, page_index)

            self.page_stack.setCurrentIndex(page_index)
            print(f"切换到页面 {page_index}: {'Smart Generator' if page_index == 0 else 'Result Preview'}")

    def _sync_params_on_page_switch(self, from_page, to_page):
        """页面切换时同步参数

        Args:
            from_page: 来源页面索引 (0=Smart Generator, 1=Result Preview)
            to_page: 目标页面索引
        """
        is_limited = self.is_limit_range_mode()

        if from_page == 0 and to_page == 1:
            # Page 0 -> Page 1: 将 Page 0 的参数同步到 Page 1
            print("[Sync] Page 0 -> Page 1: 同步参数")

            # 同步 Cell type
            if "Cell type :" in self.dropdowns and hasattr(self, 'dropdowns_page2') and "Cell type:" in self.dropdowns_page2:
                idx = self.dropdowns["Cell type :"].currentIndex()
                self.dropdowns_page2["Cell type:"].blockSignals(True)
                self.dropdowns_page2["Cell type:"].setCurrentIndex(idx)
                self.dropdowns_page2["Cell type:"].blockSignals(False)
                print(f"  Cell type: {self.dropdowns['Cell type :'].currentText()}")

            # 同步 Cell size
            if hasattr(self, 'cell_size_slider') and hasattr(self, 'cell_size_slider_page2'):
                v = self.cell_size_slider.value()
                self.cell_size_slider_page2.blockSignals(True)
                self.cell_size_slider_page2.setValue(v)
                self.cell_size_value_label_page2.setText(f"{v/10.0:.1f}")
                self.cell_size_slider_page2.blockSignals(False)
                print(f"  Cell size: {v/10.0:.1f}")

            # 同步 Strut radius
            if hasattr(self, 'strut_radius_slider') and hasattr(self, 'strut_radius_slider_page2'):
                v = self.strut_radius_slider.value()
                self.strut_radius_slider_page2.blockSignals(True)
                self.strut_radius_slider_page2.setValue(v)
                self.strut_radius_value_label_page2.setText(f"{v/100.0:.2f}")
                self.strut_radius_slider_page2.blockSignals(False)
                print(f"  Strut radius: {v/100.0:.2f}")

            # 同步 Transform
            if hasattr(self, 'slider') and hasattr(self, 'transform_slider_page2'):
                v = self.slider.value()
                self.transform_slider_page2.blockSignals(True)
                self.transform_slider_page2.setValue(v)
                if is_limited:
                    self.transform_value_label_page2.setText(str(int(v)))
                else:
                    self.transform_value_label_page2.setText(f"{v/10.0:.1f}")
                self.transform_slider_page2.blockSignals(False)
                print(f"  Transform: {v}")

            # 刷新 Page 1 的曲线图
            if hasattr(self, 'ax') and hasattr(self, 'canvas'):
                self.plot_stress_strain_curve()

        elif from_page == 1 and to_page == 0:
            # Page 1 -> Page 0: 将 Page 1 的参数同步到 Page 0
            print("[Sync] Page 1 -> Page 0: 同步参数")

            # 同步 Cell type
            if hasattr(self, 'dropdowns_page2') and "Cell type:" in self.dropdowns_page2 and "Cell type :" in self.dropdowns:
                idx = self.dropdowns_page2["Cell type:"].currentIndex()
                self.dropdowns["Cell type :"].blockSignals(True)
                self.dropdowns["Cell type :"].setCurrentIndex(idx)
                self.dropdowns["Cell type :"].blockSignals(False)
                print(f"  Cell type: {self.dropdowns_page2['Cell type:'].currentText()}")

            # 同步 Cell size
            if hasattr(self, 'cell_size_slider_page2') and hasattr(self, 'cell_size_slider'):
                v = self.cell_size_slider_page2.value()
                self.cell_size_slider.blockSignals(True)
                self.cell_size_slider.setValue(v)
                self.cell_size_value_label.setText(f"{v/10.0:.1f}")
                self.cell_size_slider.blockSignals(False)
                print(f"  Cell size: {v/10.0:.1f}")

            # 同步 Strut radius
            if hasattr(self, 'strut_radius_slider_page2') and hasattr(self, 'strut_radius_slider'):
                v = self.strut_radius_slider_page2.value()
                self.strut_radius_slider.blockSignals(True)
                self.strut_radius_slider.setValue(v)
                self.strut_radius_value_label.setText(f"{v/100.0:.2f}")
                self.strut_radius_slider.blockSignals(False)
                print(f"  Strut radius: {v/100.0:.2f}")

            # 同步 Transform
            if hasattr(self, 'transform_slider_page2') and hasattr(self, 'slider'):
                v = self.transform_slider_page2.value()
                self.slider.blockSignals(True)
                self.slider.setValue(v)
                if is_limited:
                    self.transform_value_label.setText(str(int(v)))
                else:
                    self.transform_value_label.setText(f"{v/10.0:.1f}")
                self.slider.blockSignals(False)
                print(f"  Transform: {v}")

            # 刷新 Page 0 的可视化
            if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
                cell_type = self.dropdowns["Cell type :"].currentText() if "Cell type :" in self.dropdowns else "Cubic"
                slider_value = self.get_transform_value()
                radius = self.get_strut_radius_value()
                cell_size = self.cell_size_slider.value() / 10.0 if hasattr(self, 'cell_size_slider') else 5.0
                self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size)


    def init_default_visualization(self):
        """Initialize the visualization with current UI parameters"""
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            # 从界面读取当前参数，而不是使用硬编码的默认值
            current_cell_type = self.dropdowns.get("Cell type :", None)
            cell_type = current_cell_type.currentText() if current_cell_type else "Cubic"

            slider_value = self.get_transform_value()

            # 从滑动条获取radius和cell_size
            radius = self.get_strut_radius_value()
            cell_size = self.cell_size_slider.value() / 10.0 if hasattr(self, 'cell_size_slider') else 5.0

            print(f"[Init Visualization] Cell type: {cell_type}, Slider: {slider_value}, Radius: {radius}, Cell Size: {cell_size}")

            # 每次启动都使用默认视角
            self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size, reset_view_angle=True)

            # 如果是Lattice模式，调整相机视角
            if hasattr(self, 'lattice_checkbox') and self.lattice_checkbox.isChecked():
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()

                from visualization_widget import VISUALIZATION_AVAILABLE
                if VISUALIZATION_AVAILABLE and self.visualization_widget.plotter is not None:
                    camera = self.visualization_widget.plotter.camera
                    # Lattice选中: 调整焦点到3×3×2阵列中心
                    lattice_center = (cell_size * 1.0, cell_size * 1.0, cell_size * 0.5)
                    camera.SetFocalPoint(lattice_center)

                    # 调整相机位置
                    current_pos = camera.GetPosition()
                    current_focal = camera.GetFocalPoint()
                    direction = [current_pos[i] - current_focal[i] for i in range(3)]
                    new_position = [lattice_center[i] + direction[i] * 3.0 for i in range(3)]
                    camera.SetPosition(new_position)
                    print(f"[Camera] Lattice view - Center: {lattice_center}, New position: {new_position}")

    def generate_config(self):
        # 直接生成单个配置
        self.generate_single_config()

    def start_batch_generation(self):
        """开始连续运行模式，slider值从0到8依次变化"""
        if self.is_batch_running:
            return  # 如果已经在运行，则忽略

        self.is_batch_running = True
        self.current_batch_index = 0

        # 禁用按钮防止重复点击
        self.generate_button.setEnabled(False)

        # 开始第一次生成
        self.generate_batch_step()


    def generate_batch_step(self):
        """执行连续运行的单步操作"""
        if not self.is_batch_running or self.current_batch_index > 8:
            self.finish_batch_generation()
            return

        # 设置当前slider值
        self.slider.setValue(self.current_batch_index)

        # 更新按钮文本显示当前进度
        self.generate_button.setText(f"running... {self.current_batch_index + 1}/9")

        # 生成当前配置的脚本
        self.generate_single_config_for_batch()

        # 准备下一步
        self.current_batch_index += 1

        # 使用定时器延迟执行下一步，给用户看到进度
        if not self.batch_timer:
            self.batch_timer = QTimer()
            self.batch_timer.setSingleShot(True)
            self.batch_timer.timeout.connect(self.generate_batch_step)

        self.batch_timer.start(500)  # 500ms延迟

    def generate_single_config_for_batch(self):
        """为连续运行模式生成单个配置的脚本"""
        try:
            # 收集UI配置
            config = {}
            for label_text, dropdown in self.dropdowns.items():
                config[label_text.replace(":", "").strip()] = dropdown.currentText()

            # 收集复选框状态
            checkbox_config = {}
            for label_text, checkbox in self.checkboxes.items():
                checkbox_config[label_text.replace(":", "").strip()] = checkbox.isChecked()

            # 提取关键参数
            cell_type = config.get('Cell type', 'Cubic')

            # 从滑动条获取值
            cell_size = str(self.cell_size_slider.value() / 10.0)
            cell_radius = str(self.get_strut_radius_value())

            # 使用当前slider值
            slider_value = self.current_batch_index

            print(f"连续运行第 {self.current_batch_index + 1}/9 步:")
            print(f"Cell type: {cell_type}, Slider value: {slider_value}")

            # 确定模式类型和分析类型
            mode_type = "Compression"  # 默认压缩模式
            analysis_type = "StaCompre"  # 默认静态压缩

            if checkbox_config.get('Compression', False):
                mode_type = "Compression"
                compression_setting = config.get('Compression', 'StaCompre')
                analysis_type = compression_setting
            elif checkbox_config.get('Shear', False):
                mode_type = "Shear"
                shear_setting = config.get('Shear', 'StaShear')
                analysis_type = shear_setting

            # 生成脚本（批量模式）
            success, message, filename = generate_abaqus_script(
                cell_type=cell_type,
                cell_size=float(cell_size),
                cell_radius=float(cell_radius),
                slider=slider_value,
                mode_type=mode_type,
                analysis_type=analysis_type,
                batch_mode=True,
                batch_parent_dir=self.batch_parent_dir
            )

            if success:
                print(f"第 {self.current_batch_index + 1} 步生成成功: {filename}")
            else:
                print(f"第 {self.current_batch_index + 1} 步生成失败: {message}")

        except Exception as e:
            print(f"连续运行第 {self.current_batch_index + 1} 步出错: {str(e)}")

    def finish_batch_generation(self):
        """完成连续运行"""
        self.is_batch_running = False
        self.current_batch_index = 0
        self.batch_parent_dir = None

        # 显示完成状态
        self.generate_button.setText("Down!")

        # 1秒后重置按钮
        QTimer.singleShot(1000, self.reset_button)

    def generate_single_config(self):
        """单次生成配置"""
        try:
            # 收集UI配置
            config = {}
            for label_text, dropdown in self.dropdowns.items():
                config[label_text.replace(":", "").strip()] = dropdown.currentText()

            # 收集复选框状态
            checkbox_config = {}
            for label_text, checkbox in self.checkboxes.items():
                checkbox_config[label_text.replace(":", "").strip()] = checkbox.isChecked()

            # 提取关键参数
            cell_type = config.get('Cell type', 'Cubic')

            # 从滑动条获取值
            cell_size = str(self.cell_size_slider.value() / 10.0)
            cell_radius = str(self.get_strut_radius_value())

            # 获取slider值 (使用get_transform_value方法,自动根据Limit Range状态处理)
            slider_value = self.get_transform_value()

            print("生成的配置:")
            for key, value in config.items():
                print(f"{key}: {value}")
            for key, value in checkbox_config.items():
                print(f"{key} (选中): {value}")
            print(f"Slider value: {slider_value}")

            # 更新按钮状态
            self.generate_button.setText("waiting...")
            self.generate_button.setEnabled(False)

            # 确定模式类型和分析类型
            mode_type = "Compression"  # 默认压缩模式
            analysis_type = "StaCompre"  # 默认静态压缩

            if checkbox_config.get('Compression', False):
                mode_type = "Compression"
                compression_setting = config.get('Compression', 'StaCompre')
                # compression_setting可能是 "StaCompre" 或 "DynaCompre_500" 等
                analysis_type = compression_setting
            elif checkbox_config.get('Shear', False):
                mode_type = "Shear"
                shear_setting = config.get('Shear', 'StaShear')
                # shear_setting可能是 "StaShear" 或 "DynaShear_500" 等
                analysis_type = shear_setting

            # 生成脚本
            success, message, filename = generate_abaqus_script(
                cell_type=cell_type,
                cell_size=float(cell_size),
                cell_radius=float(cell_radius),
                slider=slider_value,
                mode_type=mode_type,
                analysis_type=analysis_type
            )

            if success:
                self.generate_button.setText(f"Down! {filename}")
                print(f"脚本生成成功: {filename}")
            else:
                self.generate_button.setText("生成失败!")
                print(f"脚本生成失败: {message}")

        except Exception as e:
            self.generate_button.setText("生成出错!")
            print(f"生成脚本时出错: {str(e)}")

        # 0.3秒后重置按钮
        QTimer.singleShot(300, self.reset_button)
    
    def reset_button(self):
        # 重置按钮状态，但不干扰正在进行的连续运行
        if not self.is_batch_running:
            self.generate_button.setText("Generate Script")
            self.generate_button.setEnabled(True)

    def on_triangle_button_clicked(self):
        """红色三角按钮点击事件处理 - 批量生成脚本"""
        print("开始批量生成脚本...")

        # 动态导入避免循环依赖
        try:
            import main
            clear_generated_files = main.clear_generated_files
            get_generated_files = main.get_generated_files
            from shell_script_generator import generate_shell_script
            from config import Config
            from datetime import datetime
        except ImportError as e:
            print(f"无法导入必要模块: {e}")
            return

        # 使用配置文件中的分组和设置
        cell_type_groups = Config.CELL_TYPE_GROUPS
        no_slider_types = Config.NO_SLIDER_CELL_TYPES

        try:
            # 禁用按钮防止重复点击
            self.triangle_button.setEnabled(False)
            self.triangle_button.setText("Running...")

            # 创建基于配置参数的任务文件夹
            # 获取配置参数用于文件夹命名
            # cell_size和strut_radius是slider，不是dropdown
            speed_checkbox = self.checkboxes.get("Compression:", None)
            direction_checkbox = self.checkboxes.get("Shear:", None)
            direction_dropdown = self.dropdowns.get("Shear:", None)

            # 构建文件夹名称
            folder_parts = []
            # 从slider获取cell_size值
            if hasattr(self, 'cell_size_slider'):
                cell_size_val = self.cell_size_slider.value() / 10.0
                # 整数去掉小数点(5.0->5)，小数替换点为p(5.1->5p1)
                if float(cell_size_val).is_integer():
                    folder_parts.append(str(int(cell_size_val)))
                else:
                    folder_parts.append(str(cell_size_val).replace('.', 'p'))
            # 从slider获取strut_radius值
            if hasattr(self, 'strut_radius_slider'):
                strut_radius_val = self.strut_radius_slider.value() / 100.0
                folder_parts.append(f"0p{int(strut_radius_val * 100)}")

            # 添加类型标识 (使用实际的 speed_value 或 direction_value)
            # 注意：Compression 和 Shear 是互斥的
            if direction_checkbox and direction_checkbox.isChecked():
                # direction模式：使用direction的实际值（如 X, X_50, X_500等）
                if direction_dropdown:
                    direction = direction_dropdown.currentText()
                    folder_parts.append(direction)
                else:
                    folder_parts.append("dir")
            elif speed_checkbox and speed_checkbox.isChecked():
                # speed模式：使用speed的实际值（如 50, 500等）
                speed_dropdown = self.dropdowns.get("Compression:", None)
                if speed_dropdown:
                    speed = speed_dropdown.currentText()
                    folder_parts.append(speed)
                else:
                    folder_parts.append("speed")
            else:
                folder_parts.append("static")

            folder_name = "_".join(folder_parts) if folder_parts else f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            generate_script_root = os.path.join(os.path.dirname(__file__), "generate_script")
            task_dir = os.path.join(generate_script_root, folder_name)
            os.makedirs(task_dir, exist_ok=True)
            print(f"创建任务文件夹: {task_dir}")

            # 保存任务目录供后续使用
            self.current_task_dir = task_dir

            total_groups = len(cell_type_groups)
            current_group = 0

            # 保存批量生成开始时的slider值，防止on_cell_type_changed修改
            batch_cell_size = self.cell_size_slider.value() if hasattr(self, 'cell_size_slider') else 50
            batch_strut_radius = self.strut_radius_slider.value() if hasattr(self, 'strut_radius_slider') else 35
            print(f"[BATCH] 批量生成参数: cell_size={batch_cell_size/10.0}, strut_radius={batch_strut_radius/100.0}")

            for group_name, cell_types in cell_type_groups:
                current_group += 1
                print(f"\n=== 处理 {group_name} ({current_group}/{total_groups}) ===")

                # 清空文件追踪列表
                clear_generated_files()

                for cell_type in cell_types:
                    print(f"正在处理 Cell Type: {cell_type}")

                    # 设置当前cell type（会触发on_cell_type_changed，可能改变slider值）
                    if "Cell type :" in self.dropdowns:
                        dropdown = self.dropdowns["Cell type :"]
                        index = dropdown.findText(cell_type)
                        if index >= 0:
                            dropdown.setCurrentIndex(index)

                    # 强制恢复批量生成时的slider值，覆盖on_cell_type_changed的影响
                    if hasattr(self, 'cell_size_slider'):
                        self.cell_size_slider.blockSignals(True)
                        self.cell_size_slider.setValue(batch_cell_size)
                        self.cell_size_slider.blockSignals(False)
                    if hasattr(self, 'strut_radius_slider'):
                        self.strut_radius_slider.blockSignals(True)
                        self.strut_radius_slider.setValue(batch_strut_radius)
                        self.strut_radius_slider.blockSignals(False)

                    if cell_type in no_slider_types:
                        # 只生成1个脚本
                        self._generate_single_script(cell_type, 8)  # 使用默认slider值8
                    else:
                        # 生成9个脚本 (slider值 0-8)
                        for slider_value in range(9):
                            self._generate_single_script(cell_type, slider_value)

                # 生成当前组的批处理脚本到task文件夹
                python_files = get_generated_files()
                if python_files:
                    print(f"{group_name} 共生成 {len(python_files)} 个脚本文件")

                    # 获取配置参数用于命名
                    # cell_size和strut_radius是slider，不是dropdown
                    speed_checkbox = self.checkboxes.get("Compression:", None)
                    direction_checkbox = self.checkboxes.get("Shear:", None)
                    speed_dropdown = self.dropdowns.get("Compression:", None)
                    direction_dropdown = self.dropdowns.get("Shear:", None)

                    config_parts = []
                    # 从slider获取cell_size值
                    if hasattr(self, 'cell_size_slider'):
                        cell_size_val = self.cell_size_slider.value() / 10.0
                        # 整数去掉小数点(5.0->5)，小数替换点为p(5.1->5p1)
                        if float(cell_size_val).is_integer():
                            config_parts.append(str(int(cell_size_val)))
                        else:
                            config_parts.append(str(cell_size_val).replace('.', 'p'))
                    # 从slider获取strut_radius值
                    if hasattr(self, 'strut_radius_slider'):
                        strut_radius_val = self.strut_radius_slider.value() / 100.0
                        config_parts.append(f"0p{int(strut_radius_val * 100)}")

                    # 使用实际的 speed_value 或 direction_value
                    # 注意：Compression 和 Shear 是互斥的
                    if direction_checkbox and direction_checkbox.isChecked():
                        # direction模式：使用direction的实际值（如 X, X_50, X_500等）
                        if direction_dropdown:
                            direction_val = direction_dropdown.currentText()
                            config_parts.append(direction_val)
                        else:
                            config_parts.append("dir")
                    elif speed_checkbox and speed_checkbox.isChecked():
                        # speed模式：使用speed的实际值（如 50, 500等）
                        if speed_dropdown:
                            speed_val = speed_dropdown.currentText()
                            config_parts.append(speed_val)
                        else:
                            config_parts.append("speed")
                    else:
                        config_parts.append("static")

                    config_name = "_".join(config_parts)

                    # 使用task文件夹作为输出目录
                    import platform
                    if platform.system() == "Windows":
                        generate_shell_script(python_files, task_dir, "bat", config_name=config_name)
                    else:
                        # Linux系统只生成.sh文件，不生成.bat文件
                        generate_shell_script(python_files, task_dir, "sh", config_name=config_name)

                    print(f"{group_name} 批处理脚本生成完成")
                else:
                    print(f"警告: {group_name} 未生成任何脚本文件")

            print("\n=== 所有批处理脚本生成完成! ===")

            # 生成主控制脚本到task文件夹
            self.generate_master_control_script()

            # 生成PBS脚本到task文件夹
            self.generate_pbs_script()

            # 清理历史文件追踪
            clear_generated_files()
            print("已清理文件追踪历史")

        except Exception as e:
            print(f"批量生成脚本时出错: {str(e)}")
        finally:
            # 显示完成状态
            self.show_completion_star()
            # 重新启用按钮
            self.triangle_button.setEnabled(True)

    def _generate_single_script(self, cell_type, slider_value):
        """生成单个脚本的辅助函数"""
        try:
            # 收集当前配置
            config = {}
            for label_text, dropdown in self.dropdowns.items():
                config[label_text.replace(":", "").strip()] = dropdown.currentText()

            # 收集复选框状态
            checkbox_config = {}
            for label_text, checkbox in self.checkboxes.items():
                checkbox_config[label_text.replace(":", "").strip()] = checkbox.isChecked()

            # 使用传入的参数覆盖cell_type
            config['Cell type'] = cell_type

            # 从slider获取实际的cell_size和strut_radius值
            if hasattr(self, 'cell_size_slider'):
                cell_size = self.cell_size_slider.value() / 10.0
            else:
                cell_size = 5.0

            if hasattr(self, 'strut_radius_slider'):
                cell_radius = self.strut_radius_slider.value() / 100.0
            else:
                cell_radius = 0.5

            # 调试输出：显示实际使用的参数
            print(f"  [DEBUG] cell_type={cell_type}, slider={slider_value}, cell_size={cell_size}, radius={cell_radius}")

            # 确定模式类型和分析类型
            mode_type = "Compression"  # 默认压缩模式
            analysis_type = "StaCompre"  # 默认静态压缩

            if checkbox_config.get('Compression', False):
                mode_type = "Compression"
                compression_setting = config.get('Compression', 'StaCompre')
                analysis_type = compression_setting
            elif checkbox_config.get('Shear', False):
                mode_type = "Shear"
                shear_setting = config.get('Shear', 'StaShear')
                analysis_type = shear_setting

            # 生成脚本
            success, message, filename = generate_abaqus_script(
                cell_type=cell_type,
                cell_size=float(cell_size),
                cell_radius=float(cell_radius),
                slider=slider_value,
                mode_type=mode_type,
                analysis_type=analysis_type
            )

            if success:
                print(f"  [OK] 生成成功: {filename}")
            else:
                print(f"  [ERROR] 生成失败: {message}")

            return success

        except Exception as e:
            print(f"  [ERROR] 生成脚本时出错: {str(e)}")
            return False

    def on_speed_direction_checkbox_changed(self, checked, label):
        """Handle mutual exclusion between Compression and Shear checkboxes and update label colors"""
        if checked:
            # If this checkbox is being checked, uncheck the other one
            for other_label, other_checkbox in self.checkboxes.items():
                if other_label != label and other_label in ["Compression:", "Shear:"]:
                    other_checkbox.setChecked(False)
        else:
            # If trying to uncheck, ensure at least one is checked
            # Check if any other checkbox in the group is checked
            any_checked = False
            for other_label, other_checkbox in self.checkboxes.items():
                if other_label != label and other_label in ["Compression:", "Shear:"]:
                    if other_checkbox.isChecked():
                        any_checked = True
                        break

            # If no other checkbox is checked, prevent unchecking this one
            if not any_checked:
                current_checkbox = self.checkboxes.get(label)
                if current_checkbox:
                    current_checkbox.blockSignals(True)  # Prevent signal loop
                    current_checkbox.setChecked(True)
                    current_checkbox.blockSignals(False)
                return

        # Update label colors based on checkbox states
        for label_text in ["Compression:", "Shear:"]:
            if label_text in self.checkbox_labels:
                checkbox = self.checkboxes.get(label_text)
                if checkbox and checkbox.isChecked():
                    # Checkbox is checked - set label color to blue (dark theme)
                    color = "#5a8bc0"
                    self.checkbox_labels[label_text].setStyleSheet(f"color: {color}; font-size: 29px; font-weight: 600; padding: 10px 0;")
                else:
                    # Checkbox is unchecked - set label color to gray (dark theme)
                    self.checkbox_labels[label_text].setStyleSheet("color: #6b7785; font-size: 29px; font-weight: 600; padding: 10px 0;")

    def is_limit_range_mode(self):
        """
        检查是否处于 Limit Range 模式
        Linux 环境下强制返回 True
        """
        if platform.system() == "Linux":
            return True
        return hasattr(self, 'limit_range_checkbox') and self.limit_range_checkbox.isChecked()

    def get_transform_value(self):
        """
        获取 Transform slider 的实际值
        根据 Limit Range 模式自动判断如何转换slider值
        注意: 对于某些结构类型，slider 被禁用，返回固定值
        """
        if not hasattr(self, 'slider') or not self.slider.isEnabled():
            # 根据当前结构类型返回对应的固定 slider 值
            current_cell_type = None
            if hasattr(self, 'dropdowns') and "Cell type :" in self.dropdowns:
                current_cell_type = self.dropdowns["Cell type :"].currentText()
            # Cubic, Octahedron, FCC 固定 slider=8，其他禁用 slider 的结构返回 0
            if current_cell_type in ['Cubic', 'Octahedron', 'FCC']:
                return 8.0
            else:
                return 0.0

        is_limited = self.is_limit_range_mode()
        slider_value = self.slider.value()

        if is_limited:
            # Limit Range 模式: slider 值范围 0-8（整数），直接返回
            return float(slider_value)
        else:
            # 完整范围模式: slider 值范围 0-80，需要除以10
            return slider_value / 10.0

    def get_strut_radius_value(self):
        """
        获取 Strut radius slider 的实际值
        使用直接值方式（与get_transform_value一致）
        """
        if not hasattr(self, 'strut_radius_slider'):
            return 0.35  # 默认值

        slider_value = self.strut_radius_slider.value()
        return slider_value / 100.0  # 转换为实际值 (30->0.3, 35->0.35, etc.)

    def on_cell_type_changed(self, cell_type):
        """Update visualization when cell type changes"""
        # 保存旧cell type的slider值（如果有旧值）
        if hasattr(self, '_previous_cell_type') and self._previous_cell_type:
            old_cell_type = self._previous_cell_type
            if not hasattr(self, 'slider_values'):
                self.slider_values = {}
            # 保存transform, radius, cell_size
            self.slider_values[old_cell_type] = {
                'transform': self.slider.value() if hasattr(self, 'slider') else 0,
                'radius': self.strut_radius_slider.value() if hasattr(self, 'strut_radius_slider') else 30,
                'cell_size': self.cell_size_slider.value() if hasattr(self, 'cell_size_slider') else 50
            }

        # 记录当前cell type作为下次切换的"旧值"
        self._previous_cell_type = cell_type

        # 检查是否有保存的slider值
        if hasattr(self, 'slider_values') and cell_type in self.slider_values:
            saved = self.slider_values[cell_type]
            # 阻止信号避免重复触发
            if hasattr(self, 'slider'):
                self.slider.blockSignals(True)
                self.slider.setValue(saved.get('transform', self.slider.value()))
                self.slider.blockSignals(False)
                # 更新显示标签
                self.on_slider_changed(self.slider.value())

            if hasattr(self, 'strut_radius_slider'):
                self.strut_radius_slider.blockSignals(True)
                self.strut_radius_slider.setValue(saved.get('radius', self.strut_radius_slider.value()))
                self.strut_radius_slider.blockSignals(False)
                # 更新显示标签
                radius_val = self.strut_radius_slider.value() / 100.0
                self.strut_radius_value_label.setText(f"{radius_val:.2f}")

            if hasattr(self, 'cell_size_slider'):
                self.cell_size_slider.blockSignals(True)
                self.cell_size_slider.setValue(saved.get('cell_size', self.cell_size_slider.value()))
                self.cell_size_slider.blockSignals(False)
                # 更新显示标签
                cell_size_val = self.cell_size_slider.value() / 10.0
                self.cell_size_value_label.setText(f"{cell_size_val:.1f}")

        # 更新可视化
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            slider_value = self.get_transform_value()
            radius = self.get_strut_radius_value()
            cell_size = self.cell_size_slider.value() / 10.0  # Convert back to 3.0-10.0

            # 更新页面1的可视化
            self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size)

    def on_cell_size_slider_changed(self, value):
        """Update when cell size slider changes"""
        cell_size = value / 10.0  # Convert to actual value (3.0-10.0)
        self.cell_size_value_label.setText(f"{cell_size:.1f}")

        # Update visualization
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type:
                cell_type = current_cell_type.currentText()
                slider_value = self.get_transform_value()
                radius = self.get_strut_radius_value()
                self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size, reset_view_angle=False)

    def on_strut_radius_slider_changed(self, value):
        """Update when strut radius slider changes - using direct value approach"""
        # 检查是否在 Limit Range 模式
        is_limited = self.is_limit_range_mode()

        # Limit Range ON: 步长5 (0.05), 需要强制对齐
        if is_limited:
            step = 5
            aligned_value = round(value / step) * step
            # 如果值不对齐，强制对齐（防止鼠标拖动产生非步长值）
            if aligned_value != value:
                self.strut_radius_slider.blockSignals(True)
                self.strut_radius_slider.setValue(aligned_value)
                self.strut_radius_slider.blockSignals(False)
                value = aligned_value

        # 直接使用value，与Transform slider一致
        radius = value / 100.0  # Convert to actual value (30->0.3, 35->0.35, etc.)
        self.strut_radius_value_label.setText(f"{radius:.2f}")

        # Update visualization
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type:
                cell_type = current_cell_type.currentText()
                slider_value = self.get_transform_value()
                cell_size = self.cell_size_slider.value() / 10.0
                self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size, reset_view_angle=False)

    def on_slider_changed(self, value):
        """Update visualization when transform slider value changes"""
        # 判断当前是否在 Limit Range 模式
        is_limited = self.is_limit_range_mode()

        if is_limited:
            # Limit Range 模式: slider 值范围 0-8（整数）
            actual_value = float(value)
            self.transform_value_label.setText(str(int(value)))
        else:
            # 完整范围模式: slider 值范围 0-80，需要除以10得到 0.0-8.0
            actual_value = value / 10.0
            self.transform_value_label.setText(f"{actual_value:.1f}")

        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type and self.slider.isEnabled():
                cell_type = current_cell_type.currentText()
                # 从滑动条获取当前值
                radius = self.get_strut_radius_value()
                cell_size = self.cell_size_slider.value() / 10.0

                # 更新页面1的可视化 (使用实际值)
                self.visualization_widget.update_visualization(cell_type, actual_value, radius, cell_size, reset_view_angle=False)

    def get_lattice_value(self, input_widget, default=1):
        """从输入框获取lattice尺寸值，确保>=1的整数"""
        try:
            value = int(input_widget.text())
            return max(1, value)
        except (ValueError, AttributeError):
            return default

    def on_lattice_toggle(self, checked):
        """Toggle lattice array display (a×b×c cells)"""
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            # 获取当前lattice尺寸
            lattice_a = self.get_lattice_value(self.lattice_a_input, 3)
            lattice_b = self.get_lattice_value(self.lattice_b_input, 3)
            lattice_c = self.get_lattice_value(self.lattice_c_input, 2)

            self.visualization_widget.toggle_lattice(checked, lattice_a, lattice_b, lattice_c)

            # Update visualization
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type:
                cell_type = current_cell_type.currentText()
                slider_value = self.get_transform_value()

                # 从滑动条获取当前值（使用值列表方式）
                radius = self.get_strut_radius_value()
                cell_size = self.cell_size_slider.value() / 10.0

                self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size, reset_view_angle=False)

                # 强制处理事件，确保可视化已经渲染
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()

                # 调整相机视角距离和焦点
                from visualization_widget import VISUALIZATION_AVAILABLE
                if VISUALIZATION_AVAILABLE and self.visualization_widget.plotter is not None:
                    camera = self.visualization_widget.plotter.camera
                    if checked:
                        # Lattice选中: 调整焦点到a×b×c阵列中心,并扩大视角
                        lattice_center = (
                            cell_size * (lattice_a - 1) / 2.0,
                            cell_size * (lattice_b - 1) / 2.0,
                            cell_size * (lattice_c - 1) / 2.0
                        )
                        camera.SetFocalPoint(lattice_center)

                        # 调整相机位置以保持视角方向,但距离更远
                        # 获取当前的视角方向
                        current_pos = camera.GetPosition()
                        current_focal = camera.GetFocalPoint()

                        # 计算从焦点到相机的方向向量
                        direction = [current_pos[i] - current_focal[i] for i in range(3)]

                        # 根据lattice大小调整相机距离
                        max_dim = max(lattice_a, lattice_b, lattice_c)
                        distance_factor = max(1.5, max_dim / 2.0)
                        new_position = [lattice_center[i] + direction[i] * distance_factor for i in range(3)]
                        camera.SetPosition(new_position)

                        print(f"[Camera] Lattice view ({lattice_a}×{lattice_b}×{lattice_c}) - Center: {lattice_center}, New position: {new_position}")
                    else:
                        # Lattice取消: 恢复默认焦点(原点)和视角
                        camera.SetFocalPoint(0, 0, 0)

                        # 重置相机到默认视角
                        self.visualization_widget.plotter.reset_camera()
                        camera.elevation = 20
                        camera.azimuth = 135

                        print("[Camera] Restored to default view (origin)")

                    # 重置相机裁剪范围以适应新的场景大小
                    camera.Modified()
                    self.visualization_widget.plotter.reset_camera_clipping_range()

                    # 强制重新渲染以立即显示新视角
                    self.visualization_widget.plotter.render()

                    # 强制刷新渲染窗口
                    render_window = self.visualization_widget.plotter.render_window
                    if render_window:
                        render_window.Modified()
                        render_window.Render()

                    # 强制更新Qt interactor
                    if hasattr(self.visualization_widget, 'interactor'):
                        self.visualization_widget.interactor.update()
                        self.visualization_widget.interactor.repaint()

                    QApplication.processEvents()

    def on_lattice_size_changed(self):
        """Handle lattice size input changes"""
        # 只在Lattice模式启用时更新可视化
        if hasattr(self, 'lattice_checkbox') and self.lattice_checkbox.isChecked():
            self.on_lattice_toggle(True)

    def on_grid_toggle(self, checked):
        """Toggle grid coordinate display"""
        if hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            self.visualization_widget.toggle_grid(checked)

    def on_save_view_clicked(self):
        """Save current 3D view as SVG and Blend files"""
        if not hasattr(self, 'visualization_widget') or self.visualization_widget is None:
            return

        from PyQt5.QtWidgets import QFileDialog
        import os

        # 获取当前cell type作为默认文件名
        cell_type = "structure"
        if hasattr(self, 'cell_type_combo'):
            cell_type = self.cell_type_combo.currentText()

        # 获取lattice尺寸信息
        lattice_suffix = ""
        if hasattr(self, 'lattice_checkbox') and self.lattice_checkbox.isChecked():
            a = self.get_lattice_value(self.lattice_a_input, 3)
            b = self.get_lattice_value(self.lattice_b_input, 3)
            c = self.get_lattice_value(self.lattice_c_input, 2)
            lattice_suffix = f"_{a}x{b}x{c}"

        # 默认保存路径
        default_dir = os.path.join(os.path.dirname(__file__), "work")
        if not os.path.exists(default_dir):
            default_dir = os.path.dirname(__file__)

        default_filename = f"{cell_type}{lattice_suffix}"
        default_path = os.path.join(default_dir, default_filename)

        # 打开文件保存对话框
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save 3D View (SVG + Blend)",
            default_path,
            "All Files (*)"
        )

        if filepath:
            # 移除扩展名（如果用户输入了的话）
            base_path = os.path.splitext(filepath)[0]

            svg_path = base_path + ".svg"
            blend_path = base_path + ".blend"
            stl_path = base_path + ".stl"

            # 保存SVG
            svg_success = self.visualization_widget.save_screenshot_svg(svg_path)

            # 保存Blend
            blend_success = self.visualization_widget.save_blend(blend_path)

            # 保存STL
            stl_success = self.visualization_widget.save_stl(stl_path)

            # 显示结果
            results = []
            if svg_success:
                results.append(f"SVG: {svg_path}")
            if blend_success:
                results.append(f"Blend: {blend_path}")
            if stl_success:
                results.append(f"STL: {stl_path}")

            if results:
                print(f"已保存: {', '.join(results)}")
                try:
                    os.startfile(svg_path)
                except Exception:
                    pass
            else:
                print("保存失败")

    def on_limit_range_toggle(self, checked, update_visualization=True):
        """
        Toggle parameter range limitation

        Args:
            checked: 是否启用限制范围
            update_visualization: 是否更新可视化（load_settings时设为False避免重复更新）

        When checked (限制范围):
          - Transform: 0-8, step 1.0
          - Strut radius: 0.3-0.5, step 0.05
          - Cell size: 固定为5.0 (禁用slider)
        When unchecked (完整范围):
          - Transform: 0-8.0, step 0.1
          - Strut radius: 0.2-1.0, step 0.01
          - Cell size: 3.0-10.0, step 0.5
        """
        if checked:
            # 限制范围模式
            # Cell size: 固定为5.0，禁用slider (Page 1)
            self.cell_size_slider.blockSignals(True)
            self.cell_size_slider.setValue(50)  # 5.0 * 10
            self.cell_size_slider.setEnabled(False)
            self.cell_size_value_label.setText("5.0")
            self.cell_size_slider.blockSignals(False)

            # Cell size: Page 2同步
            if hasattr(self, 'cell_size_slider_page2'):
                self.cell_size_slider_page2.blockSignals(True)
                self.cell_size_slider_page2.setValue(50)
                self.cell_size_slider_page2.setEnabled(False)
                self.cell_size_value_label_page2.setText("5.0")
                self.cell_size_slider_page2.blockSignals(False)

            # Strut radius: 切换到限制范围 30-50 (0.30-0.50), 步长5 (0.05)
            # 获取当前实际值
            current_radius = self.strut_radius_slider.value()  # 直接值 (20-100 或 30-50)

            # 约束到新范围并对齐到步长5
            if current_radius < 30:
                new_radius = 30
            elif current_radius > 50:
                new_radius = 50
            else:
                # 四舍五入到最近的5的倍数
                new_radius = round(current_radius / 5) * 5

            self.strut_radius_slider.blockSignals(True)
            self.strut_radius_slider.setMinimum(30)  # 0.30 * 100
            self.strut_radius_slider.setMaximum(50)  # 0.50 * 100
            self.strut_radius_slider.setValue(new_radius)
            self.strut_radius_slider.setSingleStep(5)  # 0.05 * 100
            self.strut_radius_value_label.setText(f"{new_radius / 100.0:.2f}")
            self.strut_radius_slider.blockSignals(False)

            # Page 2 strut radius同步
            if hasattr(self, 'strut_radius_slider_page2'):
                self.strut_radius_slider_page2.blockSignals(True)
                self.strut_radius_slider_page2.setMinimum(30)
                self.strut_radius_slider_page2.setMaximum(50)
                self.strut_radius_slider_page2.setValue(new_radius)
                self.strut_radius_slider_page2.setSingleStep(5)
                self.strut_radius_value_label_page2.setText(f"{new_radius / 100.0:.2f}")
                self.strut_radius_slider_page2.blockSignals(False)

            # Transform: 改为步长1.0（范围0-8）
            current_transform_value = self.slider.value()
            self.slider.blockSignals(True)
            # 将当前值（0-80，步长1）转换为整数值（0-8）
            current_int_value = round(current_transform_value / 10.0)
            self.slider.setMinimum(0)
            self.slider.setMaximum(8)  # 直接使用整数值
            self.slider.setValue(current_int_value)
            self.slider.setTickInterval(1)  # 步长为1
            self.transform_value_label.setText(str(current_int_value))
            self.slider.blockSignals(False)

            # Page 2 transform同步
            if hasattr(self, 'transform_slider_page2'):
                self.transform_slider_page2.blockSignals(True)
                self.transform_slider_page2.setMinimum(0)
                self.transform_slider_page2.setMaximum(8)
                self.transform_slider_page2.setValue(current_int_value)
                self.transform_slider_page2.setTickInterval(1)
                self.transform_value_label_page2.setText(str(current_int_value))
                self.transform_slider_page2.blockSignals(False)

        else:
            # 完整范围模式
            # Cell size: 启用slider，范围3.0-10.0 (Page 1)
            self.cell_size_slider.setEnabled(True)

            # Cell size: Page 2同步
            if hasattr(self, 'cell_size_slider_page2'):
                self.cell_size_slider_page2.setEnabled(True)

            # Strut radius: 切换到完整范围 20-100 (0.20-1.00), 步长1 (0.01)
            # 获取当前实际值
            current_radius = self.strut_radius_slider.value()  # 直接值 (30-50 或 20-100)

            # 保持当前值（如果在范围内）
            if current_radius < 20:
                new_radius = 20
            elif current_radius > 100:
                new_radius = 100
            else:
                new_radius = current_radius

            self.strut_radius_slider.blockSignals(True)
            self.strut_radius_slider.setMinimum(20)  # 0.20 * 100
            self.strut_radius_slider.setMaximum(100)  # 1.00 * 100
            self.strut_radius_slider.setValue(new_radius)
            self.strut_radius_slider.setSingleStep(1)  # 0.01 * 100
            self.strut_radius_value_label.setText(f"{new_radius / 100.0:.2f}")
            self.strut_radius_slider.blockSignals(False)

            # Page 2 strut radius同步
            if hasattr(self, 'strut_radius_slider_page2'):
                self.strut_radius_slider_page2.blockSignals(True)
                self.strut_radius_slider_page2.setMinimum(20)
                self.strut_radius_slider_page2.setMaximum(100)
                self.strut_radius_slider_page2.setValue(new_radius)
                self.strut_radius_slider_page2.setSingleStep(1)
                self.strut_radius_value_label_page2.setText(f"{new_radius / 100.0:.2f}")
                self.strut_radius_slider_page2.blockSignals(False)

            # Transform: 恢复步长0.1（范围0-8.0）
            current_transform_value = self.slider.value()  # 当前是整数值0-8
            self.slider.blockSignals(True)
            # 将整数值转换回0-80范围
            self.slider.setMinimum(0)
            self.slider.setMaximum(80)  # 8.0 * 10
            self.slider.setValue(current_transform_value * 10)  # 转换为0-80范围
            self.slider.setTickInterval(10)  # 1.0 * 10
            self.transform_value_label.setText(f"{current_transform_value}.0")
            self.slider.blockSignals(False)

            # Page 2 transform同步
            if hasattr(self, 'transform_slider_page2'):
                self.transform_slider_page2.blockSignals(True)
                self.transform_slider_page2.setMinimum(0)
                self.transform_slider_page2.setMaximum(80)
                self.transform_slider_page2.setValue(current_transform_value * 10)
                self.transform_slider_page2.setTickInterval(10)
                self.transform_value_label_page2.setText(f"{current_transform_value}.0")
                self.transform_slider_page2.blockSignals(False)

        # 更新可视化（如果需要）
        if update_visualization and hasattr(self, 'visualization_widget') and self.visualization_widget is not None:
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type:
                cell_type = current_cell_type.currentText()
                slider_value = self.get_transform_value()
                # 直接从slider获取实际radius值
                radius = self.get_strut_radius_value()
                cell_size = self.cell_size_slider.value() / 10.0
                self.visualization_widget.update_visualization(cell_type, slider_value, radius, cell_size, reset_view_angle=False)

    def update_slider_state(self):
        """Update slider enabled state based on cell type"""
        if hasattr(self, 'slider') and self.slider is not None:
            current_cell_type = self.dropdowns.get("Cell type :", None)
            if current_cell_type:
                previous_cell_type = getattr(self, 'previous_cell_type', None)
                cell_type = current_cell_type.currentText()

                # Disable slider for specific cell types
                disabled_types = ["Cubic", "Octahedron"]
                should_disable = cell_type in disabled_types

                # Temporarily block signals to avoid triggering updates
                self.slider.blockSignals(True)

                if should_disable:
                    # For Cubic and Octahedron: set to 8 and disable
                    self.slider.setValue(8 if self.is_limit_range_mode() else 80)
                    self.slider.setEnabled(False)
                else:
                    # For other cell types: keep current slider value unchanged
                    # Only enable the slider, don't change its value
                    self.slider.setEnabled(True)

                # Unblock signals
                self.slider.blockSignals(False)

                # Store current cell type for next time
                self.previous_cell_type = cell_type

    def create_batch_controls(self, form_layout, start_row):

        # 批量生成选项
        batch_label = QLabel("Batch Mode:")
        batch_label.setObjectName("input_label")

        self.batch_checkbox = QCheckBox()
        self.batch_checkbox.setObjectName("batch_checkbox")
        self.batch_checkbox.toggled.connect(self.on_batch_toggle)

        # 批量配置按钮
        self.batch_config_button = QPushButton("Batch Config")
        self.batch_config_button.setObjectName("batch_config_button")
        self.batch_config_button.clicked.connect(self.show_batch_config)
        self.batch_config_button.setEnabled(False)

        form_layout.addWidget(batch_label, start_row + 1, 0)
        form_layout.addWidget(self.batch_config_button, start_row + 1, 1)
        form_layout.addWidget(self.batch_checkbox, start_row + 1, 2)

        return start_row + 2


    def on_batch_toggle(self, checked):
        """批量模式切换处理"""
        self.batch_config_button.setEnabled(checked)

        if checked:
            print("批量模式已启用")
        else:
            print("批量模式已禁用")

    def load_result(self):
        """Load feature_data.json or feature_data.txt and update UI based on selected structure"""
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        # Open file dialog with default path to work/feature_data.json
        default_path = os.path.join(BASE_DIR, "work", "feature_data.json")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Feature Data",
            default_path,
            "JSON Files (*.json);;Text Files (*.txt);;All Files (*.*)"
        )

        if not file_path:
            return

        # Check file extension and handle accordingly
        if file_path.lower().endswith('.txt'):
            self._load_result_from_txt(file_path)
        else:
            self._load_result_from_json(file_path)

    def _load_result_from_txt(self, file_path):
        """Load feature_data.txt and add data to the database"""
        from PyQt5.QtWidgets import QMessageBox
        import numpy as np

        try:
            # Parse the txt file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if len(lines) < 7:
                QMessageBox.warning(self, "Warning", "Invalid feature_data.txt format: file too short.")
                return

            # Parse first line: structure name (e.g., "FCCZ_5_0p48_6p8_StaCompre")
            structure_name = lines[0].strip()

            # Parse second line: status
            status_line = lines[1].strip()
            status = status_line.split(': ')[1] if ': ' in status_line else status_line

            # Parse third line: density
            density_line = lines[2].strip()
            density_str = density_line.split(': ')[1] if ': ' in density_line else density_line
            density = float(density_str)

            # Parse data starting from line 7 (index 6)
            data_lines = []
            for line in lines[6:]:
                line = line.strip()
                if not line:
                    break
                parts = line.split()
                if len(parts) == 2:
                    try:
                        # Handle scientific notation like "4.96586E-06"
                        x = float(parts[0])
                        y = float(parts[1])
                        data_lines.append((x, y))
                    except ValueError:
                        pass

            if not data_lines:
                QMessageBox.warning(self, "Warning", "No valid data found in the file.")
                return

            displacement = np.array([d[0] for d in data_lines])
            force = np.array([d[1] for d in data_lines])

            # Parse structure name to get parameters
            # Example: FCCZ_5_0p48_6p8_StaCompre -> FCCZ, 5, 0.48, 6.8, StaCompre
            parts = structure_name.split('_')
            if len(parts) >= 5:
                cell_type = parts[0]
                cell_size_str = parts[1]
                radius_str = parts[2].replace('p', '.')
                transform_str = parts[3].replace('p', '.')
                curve_type = parts[4]  # StaCompre, StaShear, etc.

                # Build structure key for display
                structure_key = '_'.join(parts[:4])  # e.g., FCCZ_5_0p48_6p8

                # Parse values
                radius_value = float(radius_str)
                transform_value = float(transform_str)
                cell_size_value = float(cell_size_str)

                # Add data to feature_data.json FIRST
                self._add_txt_data_to_json(structure_name, curve_type, density, displacement, force)

                # Switch Limit Range to OFF for precise values
                if hasattr(self, 'limit_range_checkbox_page2'):
                    if self.limit_range_checkbox_page2.isChecked():
                        print(f"Switching Limit Range OFF for imported data")
                        self.limit_range_checkbox_page2.setChecked(False)
                        # This triggers _on_limit_range_changed which updates slider ranges

                # Clear any previous precise value flags
                self._skip_radius_alignment = False
                self._precise_transform_value = None

                # Block signals to prevent auto-plotting during slider updates
                if hasattr(self, 'cell_size_slider_page2'):
                    self.cell_size_slider_page2.blockSignals(True)
                if hasattr(self, 'strut_radius_slider_page2'):
                    self.strut_radius_slider_page2.blockSignals(True)
                if hasattr(self, 'transform_slider_page2'):
                    self.transform_slider_page2.blockSignals(True)

                try:
                    # Update Cell type dropdown
                    if "Cell type:" in self.dropdowns_page2:
                        combo = self.dropdowns_page2["Cell type:"]
                        index = combo.findText(cell_type)
                        if index >= 0:
                            combo.setCurrentIndex(index)

                    # Update Cell size slider
                    if hasattr(self, 'cell_size_slider_page2'):
                        self.cell_size_slider_page2.setValue(int(cell_size_value * 10))

                    # Update Strut radius slider (Limit Range OFF: range 20-100, step 1)
                    if hasattr(self, 'strut_radius_slider_page2'):
                        self.strut_radius_slider_page2.setValue(int(round(radius_value * 100)))
                        if hasattr(self, 'strut_radius_value_label_page2'):
                            self.strut_radius_value_label_page2.setText(f"{radius_value:.2f}")

                    # Update Transform slider (Limit Range OFF: range 0-80, value = transform * 10)
                    if hasattr(self, 'transform_slider_page2'):
                        slider_val = int(round(transform_value * 10))
                        self.transform_slider_page2.setValue(slider_val)
                        if hasattr(self, 'transform_value_label_page2'):
                            self.transform_value_label_page2.setText(f"{transform_value:.1f}")
                        print(f"  Transform: slider_val={slider_val}, label={transform_value:.1f}")

                    print(f"Sliders set to: cell_size={cell_size_value}, radius={radius_value}, transform={transform_value}")

                finally:
                    # Unblock signals
                    if hasattr(self, 'cell_size_slider_page2'):
                        self.cell_size_slider_page2.blockSignals(False)
                    if hasattr(self, 'strut_radius_slider_page2'):
                        self.strut_radius_slider_page2.blockSignals(False)
                    if hasattr(self, 'transform_slider_page2'):
                        self.transform_slider_page2.blockSignals(False)

                QMessageBox.information(
                    self,
                    "Success",
                    f"Data added to feature_data.json\n\n"
                    f"Structure key: {structure_key}\n"
                    f"Curve type: {curve_type}_curve\n"
                    f"Density: {density:.6f}\n"
                    f"Data points: {len(data_lines)}\n\n"
                    f"Adjust sliders to view the curve."
                )

                # Don't auto-plot, let user adjust sliders manually
            else:
                QMessageBox.warning(self, "Warning", f"Cannot parse structure name: {structure_name}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load txt file:\n{str(e)}")

    def _add_limit_range_exception(self, cell_size, radius, transform):
        """Legacy function - no longer needed since we switch to Limit Range OFF when importing.
        Kept for compatibility.
        """
        pass

    def _add_txt_data_to_json(self, structure_name, curve_type, density, displacement, force):
        """Add data from txt file to feature_data.json

        Uses the same format as GeJsonl.py:
        - curve_type should be like 'StaCompre_curve', 'StaShare_curve', etc.
        - displacement and force are stored as lists
        """
        import json

        # Build structure key: Cell_Size_Radius_Transform (without curve type)
        parts = structure_name.split('_')
        if len(parts) >= 4:
            # e.g., FCCZ_5_0p48_6p8_StaCompre -> FCCZ_5_0p48_6p8
            structure_key = '_'.join(parts[:4])
        else:
            structure_key = structure_name

        # Convert curve_type to match GeJsonl.py format (add '_curve' suffix if not present)
        # e.g., 'StaCompre' -> 'StaCompre_curve'
        if not curve_type.endswith('_curve'):
            curve_type_key = f"{curve_type}_curve"
        else:
            curve_type_key = curve_type

        # Load existing feature_data.json or create new
        json_path = os.path.join(BASE_DIR, "work", "feature_data.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        # Create structure entry if not exists
        if structure_key not in data:
            data[structure_key] = {'density': density}

        # Add curve data
        # Convert numpy arrays to lists for JSON serialization
        data[structure_key][curve_type_key] = {
            'displacement': displacement.tolist(),
            'force': force.tolist()
        }

        # Update density if different
        data[structure_key]['density'] = density

        # Save back to JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"Added {curve_type_key} data for {structure_key} to feature_data.json")

    def _load_result_from_json(self, file_path):
        """Load feature_data.json and update UI based on selected structure"""
        import json
        from PyQt5.QtWidgets import QMessageBox

        try:
            # Load JSON data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                QMessageBox.warning(self, "Warning", "The JSON file is empty.")
                return

            # Get first structure name as example: "AFCC_5_0p3_0"
            structure_names = list(data.keys())
            first_structure = structure_names[0]

            # Parse structure name: Cell_Size_Radius_Slider
            # Example: AFCC_5_0p3_0 -> AFCC, 5, 0.3, 0
            parts = first_structure.split('_')
            if len(parts) >= 4:
                cell_type = parts[0]
                cell_size_str = parts[1]
                radius_str = parts[2].replace('p', '.')
                transform_str = parts[3]

                # Update Cell type dropdown (仍然是dropdown)
                if "Cell type:" in self.dropdowns_page2:
                    combo = self.dropdowns_page2["Cell type:"]
                    index = combo.findText(cell_type)
                    if index >= 0:
                        combo.setCurrentIndex(index)

                # Update Cell size slider (现在是slider，会同步到Page 1)
                try:
                    cell_size_value = float(cell_size_str)
                    slider_value = int(cell_size_value * 10)  # 转换为slider值
                    if hasattr(self, 'cell_size_slider_page2'):
                        self.cell_size_slider_page2.setValue(slider_value)
                except ValueError:
                    pass

                # Update Strut radius slider (使用直接值方式，会同步到Page 1)
                try:
                    radius_value = float(radius_str)
                    # 直接将实际值转换为slider值 (乘以100)
                    slider_value = int(radius_value * 100)
                    if hasattr(self, 'strut_radius_slider_page2'):
                        self.strut_radius_slider_page2.setValue(slider_value)
                except ValueError:
                    pass

                # Update Transform slider (现在是slider，会同步到Page 1)
                try:
                    transform_value = float(transform_str)
                    # 根据Limit Range模式设置值
                    is_limited = self.is_limit_range_mode()
                    if is_limited:
                        # Limit Range ON: 直接使用整数值0-8
                        slider_val = int(transform_value)
                    else:
                        # Limit Range OFF: 乘以10转换为0-80
                        slider_val = int(transform_value * 10)

                    if hasattr(self, 'transform_slider_page2'):
                        self.transform_slider_page2.setValue(slider_val)
                except ValueError:
                    pass

            # Extract curve types from the first structure's data
            structure_data = data[first_structure]
            curve_types = [key for key in structure_data.keys() if key not in ['density']]

            # Update Curve type dropdown with available curves
            if "Curve type:" in self.dropdowns_page2:
                curve_combo = self.dropdowns_page2["Curve type:"]
                curve_combo.clear()
                curve_combo.addItems(curve_types)

            QMessageBox.information(
                self,
                "Success",
                f"Loaded {len(structure_names)} structures from {os.path.basename(file_path)}\n\n"
                f"Detected structure: {cell_type}\n"
                f"Available curves: {', '.join(curve_types)}"
            )

            # Auto-plot the first available curve
            self.plot_stress_strain_curve()

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error", f"Failed to parse JSON file:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")

    def get_structure_key_from_page2_selections(self):
        """Construct structure key from Page 2 selections (dropdown + sliders)
        Returns: string like "AFCC_5_0p3_0"
        """
        try:
            # Get Cell type from dropdown (e.g., "AFCC")
            cell_type = ""
            if "Cell type:" in self.dropdowns_page2:
                cell_type = self.dropdowns_page2["Cell type:"].currentText()

            # Get Cell size from slider (Page 2) - 与Page 1同步
            cell_size = ""
            if hasattr(self, 'cell_size_slider_page2'):
                cell_size_value = self.cell_size_slider_page2.value() / 10.0
                # 格式化为整数或小数
                if cell_size_value == int(cell_size_value):
                    cell_size = str(int(cell_size_value))
                else:
                    cell_size = str(cell_size_value)

            # Get Strut radius from slider (直接从 Page 2 slider 获取)
            # Check for precise imported value first
            radius = ""
            if hasattr(self, 'strut_radius_slider_page2'):
                radius_value = self.strut_radius_slider_page2.value() / 100.0
                # 格式化并去除尾随零（0.30 -> 0.3, 0.35 -> 0.35）
                radius_str = f"{radius_value:.2f}".rstrip('0').rstrip('.')
                radius = radius_str.replace('.', 'p')

            # Get Transform value from slider (直接从 Page 2 slider 获取)
            slider_value = "0"
            if hasattr(self, 'transform_slider_page2'):
                is_limited = self.is_limit_range_mode()
                raw_value = self.transform_slider_page2.value()
                if is_limited:
                    transform_value = float(raw_value)
                else:
                    transform_value = raw_value / 10.0
                # 使用 round 避免浮点误差，然后格式化
                transform_value = round(transform_value, 1)
                # 格式化为整数或小数，使用 'p' 代替 '.'
                if transform_value == int(transform_value):
                    slider_value = str(int(transform_value))
                else:
                    # 格式化为一位小数，使用 'p' 代替 '.' 以匹配文件命名格式
                    slider_value = f"{transform_value:.1f}".replace('.', 'p')

            # Debug print
            print(f"Building structure key: {cell_type}_{cell_size}_{radius}_{slider_value}")

            # Construct key: Cell_Size_Radius_Slider
            structure_key = f"{cell_type}_{cell_size}_{radius}_{slider_value}"
            return structure_key

        except Exception as e:
            print(f"Error constructing structure key: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ==================== Feature Search Methods ====================

    def _load_feature_database(self):
        """Load extracted_features.csv and calculate global ranges"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), "work", "extracted_features.csv")
            if os.path.exists(csv_path):
                self.feature_df = pd.read_csv(csv_path)
                print(f"Loaded feature database: {len(self.feature_df)} samples")

                # Calculate global ranges for each feature
                numeric_cols = ['density',
                               'comp_EA', 'comp_stiffness', 'comp_densified', 'comp_yield',
                               'shear_EA', 'shear_stiffness', 'shear_yield',
                               'dyna_comp_EA', 'dyna_shear_EA']
                self.feature_ranges = {}
                for col in numeric_cols:
                    if col in self.feature_df.columns:
                        self.feature_ranges[col] = {
                            'min': self.feature_df[col].min(),
                            'max': self.feature_df[col].max()
                        }
            else:
                print(f"Feature database not found: {csv_path}")
                self.feature_df = None
                self.feature_ranges = {}
        except Exception as e:
            print(f"Error loading feature database: {e}")
            self.feature_df = None
            self.feature_ranges = {}

    def _on_feature1_changed(self, index):
        """Handle Feature 1 dropdown change - show range"""
        feature = self.feature1_combo.currentText()
        if feature != "None" and feature in self.feature_ranges:
            r = self.feature_ranges[feature]
            self.range_label1.setText(f"Range: {r['min']:.4g} ~ {r['max']:.4g}")
        else:
            self.range_label1.setText("")

    def _on_feature2_changed(self, index):
        """Handle Feature 2 dropdown change - show range"""
        feature = self.feature2_combo.currentText()
        if feature != "None" and feature in self.feature_ranges:
            r = self.feature_ranges[feature]
            self.range_label2.setText(f"Range: {r['min']:.4g} ~ {r['max']:.4g}")
        else:
            self.range_label2.setText("")

    def _search_single_feature(self, feature, target_value):
        """Search for materials closest to target value for a single feature"""
        if self.feature_df is None:
            return []

        df = self.feature_df.copy()
        df['distance'] = abs(df[feature] - target_value)
        df_sorted = df.nsmallest(3, 'distance')

        results = []
        for _, row in df_sorted.iterrows():
            results.append({
                'sample_name': row['sample_name'],
                'value': row[feature],
                'distance': row['distance'],
                'cell_type': row['cell_type']
            })
        return results

    def _find_nearest_families(self, f1, v1, f2, v2, k=1):
        """Find k nearest cell_type families in normalized dual-feature space"""
        if self.feature_df is None:
            return {}

        df = self.feature_df.copy()

        # Normalize features
        f1_min, f1_max = df[f1].min(), df[f1].max()
        f2_min, f2_max = df[f2].min(), df[f2].max()

        if f1_max - f1_min > 0:
            df['norm_f1'] = (df[f1] - f1_min) / (f1_max - f1_min)
            target_norm1 = (v1 - f1_min) / (f1_max - f1_min)
        else:
            df['norm_f1'] = 0
            target_norm1 = 0

        if f2_max - f2_min > 0:
            df['norm_f2'] = (df[f2] - f2_min) / (f2_max - f2_min)
            target_norm2 = (v2 - f2_min) / (f2_max - f2_min)
        else:
            df['norm_f2'] = 0
            target_norm2 = 0

        # Calculate Euclidean distance
        df['distance'] = np.sqrt(
            (df['norm_f1'] - target_norm1)**2 +
            (df['norm_f2'] - target_norm2)**2
        )

        # Iteratively select k different families
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

    def _display_single_results(self, feature, target_value, results):
        """Display single feature search results in Feature Summary"""
        if not results:
            self.summary_text.setText("No results found.")
            return

        # Format feature name for display
        feat_display = feature.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()

        text = f"Feature Search Results:\n"
        text += f"Target: {feat_display} = {target_value:.4g}\n"
        text += "-" * 40 + "\n\n"

        for i, r in enumerate(results):
            rank = ["1st", "2nd", "3rd"][i]
            text += f"{rank}: {r['sample_name']}\n"
            text += f"     Value: {r['value']:.4g}, Diff: {r['distance']:.4g}\n\n"

        self.summary_text.setText(text)

    def _display_dual_results(self, f1, v1, f2, v2, best_samples):
        """Display dual feature search results in Feature Summary"""
        f1_display = f1.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()
        f2_display = f2.replace('static_comp_', '').replace('static_shear_', '').replace('_', ' ').title()

        text = f"Dual Feature Search Results:\n"
        text += f"Target: {f1_display} = {v1:.4g}\n"
        text += f"        {f2_display} = {v2:.4g}\n"
        text += "-" * 40 + "\n\n"

        if best_samples:
            for i, sample in enumerate(best_samples[:3]):
                rank = ["1st", "2nd", "3rd"][i]
                # 检查是否为近似值
                is_approx = sample.get('is_approximation', False)
                approx_note = " (Closest)" if is_approx else ""
                text += f"{rank}: {sample.get('sample_name', 'N/A')}{approx_note}\n"
                if 'predicted_f1' in sample:
                    text += f"     {f1_display}: {sample['predicted_f1']:.4g}\n"
                if 'predicted_f2' in sample:
                    text += f"     {f2_display}: {sample['predicted_f2']:.4g}\n"
                text += "\n"
            # 如果是近似值，添加说明
            if any(s.get('is_approximation', False) for s in best_samples):
                text += "(Closest) = No exact intersection found,\n"
                text += "showing closest approximation.\n"
        else:
            text += "No suitable materials found.\n"

        self.summary_text.setText(text)

    def _on_search_clicked(self):
        """Handle Search button click"""
        if self.feature_df is None:
            QMessageBox.warning(self, "Warning", "Feature database not loaded.\nPlease ensure extracted_features.csv exists.")
            return

        f1 = self.feature1_combo.currentText()
        f2 = self.feature2_combo.currentText()

        # Validate selection
        if f1 == "None" and f2 == "None":
            QMessageBox.warning(self, "Warning", "Please select at least one feature.")
            return

        # Parse input values
        try:
            v1 = float(self.value1_input.text()) if f1 != "None" and self.value1_input.text().strip() else None
            v2 = float(self.value2_input.text()) if f2 != "None" and self.value2_input.text().strip() else None
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter valid numeric values.")
            return

        # Check if values are provided
        if f1 != "None" and v1 is None:
            QMessageBox.warning(self, "Warning", "Please enter a value for Feature 1.")
            return
        if f2 != "None" and v2 is None:
            QMessageBox.warning(self, "Warning", "Please enter a value for Feature 2.")
            return

        # Single feature search
        if (f1 != "None") != (f2 != "None"):
            feature = f1 if f1 != "None" else f2
            value = v1 if v1 is not None else v2
            results = self._search_single_feature(feature, value)
            self._display_single_results(feature, value, results)

        # Dual feature search
        else:
            dialog = FeatureSearchDialog(self, self.feature_df, f1, v1, f2, v2)
            dialog.exec_()
            # Update Feature Summary with results
            if hasattr(dialog, 'best_samples') and dialog.best_samples:
                self._display_dual_results(f1, v1, f2, v2, dialog.best_samples)

    # ==================== End Feature Search Methods ====================

    def plot_stress_strain_curve(self):
        """Load curve data from feature_data.json and plot stress-strain curve"""
        import json
        from PyQt5.QtWidgets import QMessageBox

        try:
            # Check if matplotlib components are available
            if not hasattr(self, 'ax') or not hasattr(self, 'canvas'):
                print("Matplotlib components not available")
                return

            # Get structure key from current selections
            structure_key = self.get_structure_key_from_page2_selections()
            if not structure_key:
                return

            # Get curve type selection
            curve_type = "static_curve"  # default
            if "Curve type:" in self.dropdowns_page2:
                curve_type = self.dropdowns_page2["Curve type:"].currentText()

            # Load feature_data.json
            feature_data_path = os.path.join(BASE_DIR, "work", "feature_data.json")
            if not os.path.exists(feature_data_path):
                self.summary_text.setPlainText(f"Feature data file not found:\n{feature_data_path}")
                return

            with open(feature_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if structure exists in data
            if structure_key not in data:
                self.summary_text.setPlainText(
                    f"Structure '{structure_key}' not found in feature_data.json\n\n"
                    f"Available structures:\n" + "\n".join(list(data.keys())[:10])
                )
                # 清空曲线图
                self.ax.clear()
                self.ax.set_facecolor('#1e2330')
                self.ax.set_title('Stress-Strain Curve', color='#e1e8f0', fontsize=14)
                self.ax.set_xlabel('Strain (ε)', color='#c5d1de')
                self.ax.set_ylabel('Stress (σ) [MPa]', color='#c5d1de')
                self.ax.text(0.5, 0.5, f'No data for:\n{structure_key}',
                           transform=self.ax.transAxes, ha='center', va='center',
                           fontsize=12, color='#ff6b6b')
                self.canvas.draw()
                return

            structure_data = data[structure_key]

            # Check if curve type exists
            if curve_type not in structure_data:
                available_curves = [k for k in structure_data.keys() if k != 'density']
                self.summary_text.setPlainText(
                    f"Curve type '{curve_type}' not found for structure '{structure_key}'\n\n"
                    f"Available curves: {', '.join(available_curves)}"
                )
                return

            curve_data = structure_data[curve_type]

            # Extract displacement and force data
            if 'displacement' not in curve_data or 'force' not in curve_data:
                self.summary_text.setPlainText(
                    f"Missing displacement or force data in '{curve_type}' for structure '{structure_key}'"
                )
                return

            displacement = curve_data['displacement']
            force = curve_data['force']

            # Get cell size for calculations (从slider获取)
            cell_size = 5.0  # default
            if hasattr(self, 'cell_size_slider_page2'):
                try:
                    cell_size = self.cell_size_slider_page2.value() / 10.0
                except:
                    pass

            # Calculate strain and stress
            # Strain = displacement / cell_size
            # Stress = force / (cell_size)^2
            cell_size_squared = cell_size * cell_size
            strain = [d / cell_size for d in displacement]
            stress = [f / cell_size_squared for f in force]

            # Clear previous plot
            self.ax.clear()

            # Get density for calculations
            density = structure_data.get('density', 'N/A')
            try:
                rho_r = float(density) if density != 'N/A' else 1.0
            except (ValueError, TypeError):
                rho_r = 1.0

            # 计算体积 V0 = cell_size^3 (mm³)
            V0 = cell_size ** 3

            # Extract curve features first (need for plotting points)
            features = self._extract_curve_features(strain, stress, rho_r=rho_r, V0=V0, curve_type=curve_type, sample_name=structure_key)

            # Plot stress-strain curve
            self.ax.plot(strain, stress, color='#7fa0c9', linewidth=2, label=curve_type)

            # Get checkbox states (default True if not exists)
            show_ea = getattr(self, 'cb_ea', None) and self.cb_ea.isChecked()
            show_stiffness = getattr(self, 'cb_stiffness', None) and self.cb_stiffness.isChecked()
            show_peak = getattr(self, 'cb_peak', None) and self.cb_peak.isChecked()
            show_yield = getattr(self, 'cb_yield', None) and self.cb_yield.isChecked()
            show_density = getattr(self, 'cb_density', None) and self.cb_density.isChecked()

            # Add EA area fill (从起点到关键点的面积用浅色填充)
            key_idx = features.get('key_idx', len(strain) - 1)
            if show_ea and len(strain) > 0 and key_idx > 0:
                self.ax.fill_between(strain[:key_idx+1], stress[:key_idx+1],
                                    alpha=0.3, color='#7fa0c9', label=f'EA: {features["EA"]:.4f} mJ')

            # Add Modulus linear fit line (虚线) - 压缩=Young's Modulus, 剪切=Shear Modulus
            lin_idx = features.get('lin_idx', 10)
            modulus = features.get('modulus', 0)
            modulus_type = features.get('modulus_type', "Young's Modulus")
            if show_stiffness and modulus > 0 and lin_idx > 0:
                # 画从原点到屈服点附近的模量线
                import numpy as np
                max_strain_for_line = min(features.get('yield_strain', 0.1) * 1.5, max(strain) * 0.3)
                line_x = np.linspace(0, max_strain_for_line, 50)
                line_y = modulus * line_x
                self.ax.plot(line_x, line_y, '--', color='#e74c3c', linewidth=1.5,
                            label=f'{modulus_type}: {modulus:.2f} MPa')

            # Add Yield point marker
            yield_idx = features.get('yield_idx', 0)
            if show_yield and yield_idx < len(strain):
                self.ax.plot(strain[yield_idx], stress[yield_idx], 's', color='#26de81',
                            markersize=8, label=f'Yield (ε={features["yield_strain"]:.4f}, σ={features["yield_stress"]:.2f})')

            # Add Density as text label in legend
            if show_density:
                self.ax.plot([], [], ' ', label=f'Density: {density}')

            # ========== 添加Densified点的标注（仅压缩曲线） ==========
            # 在strain>0.35范围内，在2倍yield force限制下，找d2第一次超过阈值的点
            # 如果数据均匀递增无明显d2_max，则用1.5倍yield作为densified点
            if curve_type == 'StaCompre_curve' and len(strain) > 10 and show_peak:
                try:
                    from scipy.ndimage import uniform_filter1d
                    from scipy.interpolate import interp1d

                    strain_arr = np.array(strain)
                    stress_arr = np.array(stress)

                    # 去重
                    _, unique_indices = np.unique(strain_arr, return_index=True)
                    unique_indices = np.sort(unique_indices)
                    strain_clean = strain_arr[unique_indices]
                    stress_clean = stress_arr[unique_indices]

                    # 先插值到均匀X轴（100点），再平滑
                    n_resample = 100
                    strain_uniform = np.linspace(strain_clean.min(), strain_clean.max(), n_resample)
                    interp_func = interp1d(strain_clean, stress_clean, kind='cubic', fill_value='extrapolate')
                    stress_uniform = interp_func(strain_uniform)

                    # 在均匀采样后平滑
                    smooth_size = 5
                    stress_smooth = uniform_filter1d(stress_uniform, size=smooth_size)
                    d_strain = strain_uniform[1] - strain_uniform[0]
                    d1 = np.gradient(stress_smooth, d_strain)
                    d2 = np.gradient(d1, d_strain)

                    # 确定yield force（0.35之前的最大应力）
                    idx_035 = np.searchsorted(strain_uniform, 0.35)
                    yield_force = np.max(stress_smooth[:idx_035]) if idx_035 > 0 else stress_smooth[0]
                    stress_limit = 2 * yield_force

                    # 在 strain > 0.35 范围内，且 stress < 2*yield_force
                    mask = (strain_uniform > 0.35) & (stress_smooth < stress_limit)
                    indices_in_range = np.where(mask)[0]

                    densified_strain = None
                    densified_stress = None

                    if len(indices_in_range) > 0:
                        d2_in_range = d2[indices_in_range]

                        # 找d2最大值，设定阈值为最大值的30%
                        d2_max = np.max(d2_in_range)
                        threshold = d2_max * 0.3

                        # 找d2第一次超过阈值的点（曲线开始明显上升的拐点）
                        above_threshold = np.where(d2_in_range >= threshold)[0]

                        if len(above_threshold) > 0:
                            first_above = above_threshold[0]
                            idx = indices_in_range[first_above]
                            densified_strain = strain_uniform[idx]
                            orig_idx = np.argmin(np.abs(strain_arr - densified_strain))
                            densified_stress = stress_arr[orig_idx]

                    # 如果没找到d2拐点（数据均匀递增），用1.5倍yield作为densified点
                    if densified_strain is None:
                        stress_limit_15 = 1.5 * yield_force
                        exceed_indices = np.where(stress_smooth > stress_limit_15)[0]
                        if len(exceed_indices) > 0:
                            idx = exceed_indices[0]
                            densified_strain = strain_uniform[idx]
                            orig_idx = np.argmin(np.abs(strain_arr - densified_strain))
                            densified_stress = stress_arr[orig_idx]

                    # 标注Densified点（橙色圆点）
                    if densified_strain is not None and densified_stress is not None:
                        self.ax.plot(densified_strain, densified_stress, 'o', color='#ff9f43', markersize=8,
                                    label=f'Densified (ε={densified_strain:.4f}, σ={densified_stress:.2f})')

                except Exception as e:
                    print(f"[Plot] Failed to add Densified markers: {e}")

            # Set X-axis range: 显示完整曲线
            x_max = max(strain) if strain else 1.0
            self.ax.set_xlim(0, x_max * 1.05)  # 留 5% 余量

            # Set Y-axis range based on full data
            stress_arr = np.array(stress)
            y_max = np.max(stress_arr) * 1.1  # 留 10% 余量
            self.ax.set_ylim(0, y_max)

            # Set plot style
            self.ax.set_facecolor('#1e2330')
            self.ax.tick_params(colors='#c5d1de')
            self.ax.spines['bottom'].set_color('#3d5a80')
            self.ax.spines['top'].set_color('#3d5a80')
            self.ax.spines['left'].set_color('#3d5a80')
            self.ax.spines['right'].set_color('#3d5a80')
            self.ax.set_title('Stress-Strain Curve', color='#e1e8f0', fontsize=14)
            self.ax.set_xlabel('Strain (ε)', color='#c5d1de')
            self.ax.set_ylabel('Stress (σ) [MPa]', color='#c5d1de')
            self.ax.grid(True, alpha=0.2, color='#3d5a80')
            self.ax.legend(loc='upper left', facecolor='#262b3d', edgecolor='#3d5a80',
                          labelcolor='#c5d1de', fontsize=9)

            # Refresh canvas
            self.canvas.draw()

            # Update summary text
            max_stress = max(stress) if stress else 0
            max_strain = max(strain) if strain else 0

            summary_text = f"""Structure: {structure_key}
Curve Type: {curve_type}
Cell Size: {cell_size} mm
Density: {density}

Curve Statistics:
- Data Points: {len(displacement)}
- Max Stress: {max_stress:.4f}
- Max Strain: {max_strain:.6f}
- Displacement Range: [{min(displacement):.4f}, {max(displacement):.4f}]
- Force Range: [{min(force):.4f}, {max(force):.4f}]

Feature Summary:
- {features['modulus_type']}: {features['modulus']:.4f} MPa
- {features['key_point_type']} Stress: {features['key_stress']:.4f} MPa
- {features['key_point_type']} Strain: {features['key_strain']:.6f}
- Yield Stress: {features['yield_stress']:.4f} MPa
- Yield Strain: {features['yield_strain']:.6f}
- Energy Absorb: {features['EA']:.4f} mJ
"""
            self.summary_text.setPlainText(summary_text)

            # Save current plot data for refresh
            self._current_plot_data = True

            print(f"Successfully plotted {curve_type} for {structure_key}")

        except json.JSONDecodeError as e:
            self.summary_text.setPlainText(f"Error parsing JSON:\n{str(e)}")
        except Exception as e:
            self.summary_text.setPlainText(f"Error plotting curve:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _refresh_plot(self):
        """Refresh the plot when checkbox state changes"""
        # Re-plot with current selections
        try:
            self.plot_stress_strain_curve()
        except Exception as e:
            print(f"Refresh plot error: {e}")

    def _extract_curve_features(self, strain, stress, rho_r=1.0, V0=1.0, curve_type='StaCompre_curve', sample_name=None):
        """
        提取应变-应力曲线特征：刚度/剪切模量、屈服、压实点/峰值点、SEA

        参数:
            strain: 应变数组
            stress: 应力数组
            rho_r: 相对密度
            V0: 体积 (mm³)
            curve_type: 曲线类型 ('StaCompre_curve' 或 'StaShare_curve')
            sample_name: 样本名称，用于特殊样本的位置override

        返回:
            dict: 包含各特征的字典
        """
        import numpy as np

        # 特殊样本直接指定densified strain位置
        SPECIAL_OVERRIDES = {
            'Octet_truss_5_0p5_2': 0.37,  # 特殊设置：算法检测为0.55，实际应为0.37
            # 'WeairePhelan_5_0p45_0': 0.4,
            # 'WeairePhelan_5_0p45_1': 0.35,
            # 'WeairePhelan_5_0p5_3': 0.48,
            # 'WeairePhelan_5_0p5_4': 0.44,
            # 'Octet_truss_5_0p5_6': 0.58,
            # 'FBCCXYZ_5_0p45_1': 0.58,
            # 'FBCCXYZ_5_0p45_2': 0.52,
            # 'FBCCXYZ_5_0p45_4': 0.45,
            # 'BCC_5_0p45_3': 0.61,
            # 'BCC_5_0p35_6': 0.66,
            # 'BCCZ_5_0p45_2': 0.62,
            # 'Octet_truss_5_0p5_3': 0.6,
            # 'Octet_truss_5_0p5_4': 0.58,
            # 'Octet_truss_5_0p5_5': 0.58,
            # 'Auxetic_5_0p5_2': 0.55,
            # 'Auxetic_5_0p5_3': 0.55,
        }

        strain = np.array(strain)
        stress = np.array(stress)

        # 判断是否为压缩曲线（包括静态和动态）
        is_compression = ('Compre' in curve_type)
        is_dynamic = ('Dyna' in curve_type)

        if len(strain) < 5:
            return {
                'modulus': 0.0,
                'modulus_type': "Young's Modulus" if is_compression else 'Shear Modulus',
                'lin_idx': 0,
                'yield_strain': 0.0,
                'yield_stress': 0.0,
                'yield_idx': 0,
                'key_strain': 0.0,
                'key_stress': 0.0,
                'key_idx': 0,
                'key_point_type': 'Densified' if is_compression else 'Last',
                'EA': 0.0,
                'SEA': 0.0
            }

        # 自动识别线性区末端
        _, _, lin_idx = linear_region_fit(strain, stress)
        lin_idx = max(lin_idx, 2)

        # 1) 初始刚度（应变-应力曲线的斜率，强制过原点）
        x = strain[:lin_idx+1]
        y = stress[:lin_idx+1]
        K = (x @ y) / max(x @ x, 1e-12)  # 刚度 (应力/应变)

        # 2) 0.5% 偏移屈服判定
        offset_strain = 0.005
        stress_off = K * (strain - offset_strain)
        diff = stress - stress_off
        start = np.searchsorted(strain, max(offset_strain, 0.005))
        cross = np.where((diff[1:] <= 0) & (diff[:-1] > 0))[0]
        cross = cross[cross >= start-1] if cross.size else cross

        # 屈服点
        yield_idx = (cross[0] + 1) if cross.size else len(strain) - 1
        yield_stress = float(stress[yield_idx])
        yield_strain = float(strain[yield_idx])

        # 根据曲线类型确定关键点
        if is_compression:
            # 检查是否为特殊样本，直接使用override位置
            if sample_name and sample_name in SPECIAL_OVERRIDES:
                target_strain = SPECIAL_OVERRIDES[sample_name]
                key_idx = int(np.argmin(np.abs(strain - target_strain)))
                key_stress = float(stress[key_idx])
                key_strain = float(strain[key_idx])

                # 能量吸收 EA
                E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
                EA = E_total * V0
                mass = rho_r * V0 * 1.01e-09
                SEA = EA / mass if mass > 0 else 0.0

                return {
                    'modulus': K,
                    'modulus_type': "Young's Modulus",
                    'lin_idx': lin_idx,
                    'yield_strain': yield_strain,
                    'yield_stress': yield_stress,
                    'yield_idx': yield_idx,
                    'key_strain': key_strain,
                    'key_stress': key_stress,
                    'key_idx': key_idx,
                    'key_point_type': 'Densified',
                    'EA': EA,
                    'SEA': SEA
                }

            # 压缩曲线：找 Densified 点（密实化起点/应力急升拐点）
            if is_dynamic:
                # 动态压缩曲线：首先检查是否有回弹
                max_strain_idx = int(np.argmax(strain))
                max_strain_val = float(strain[max_strain_idx])
                n = len(strain)

                # 检查是否有回弹：max_strain在前90%的数据中
                has_rebound = max_strain_idx < n * 0.9

                if has_rebound:
                    # 有回弹：积分到max_strain
                    key_idx = max_strain_idx
                    key_strain = max_strain_val
                else:
                    # 无回弹（可能有尾部spike）：检测尖峰并找到切断点
                    # 计算前80%数据的中位应力作为平台应力
                    cut_80 = int(n * 0.8)
                    plateau_stress = float(np.median(stress[:cut_80])) if cut_80 > 0 else float(stress[0])
                    max_stress = float(np.max(stress))

                    # 判断是否有尖峰：最大应力超过平台应力3倍
                    has_spike = max_stress > 3 * plateau_stress and plateau_stress > 0

                    if has_spike:
                        # 有尖峰：找应力首次超过2倍平台应力的位置作为切断点
                        spike_threshold = 2 * plateau_stress
                        spike_onset_indices = np.where(stress > spike_threshold)[0]
                        if len(spike_onset_indices) > 0:
                            key_idx = spike_onset_indices[0]
                            key_strain = float(strain[key_idx])
                        else:
                            key_strain = 0.8 * max_strain_val
                            key_idx = int(np.argmin(np.abs(strain - key_strain)))
                    else:
                        # 无明显尖峰：使用密实化点检测
                        try:
                            detected_strain = detect_densification_point(strain, stress)
                            if 0.2 * max_strain_val <= detected_strain <= 0.95 * max_strain_val:
                                key_strain = detected_strain
                                key_idx = int(np.argmin(np.abs(strain - key_strain)))
                            else:
                                key_strain = 0.8 * max_strain_val
                                key_idx = int(np.argmin(np.abs(strain - key_strain)))
                        except Exception:
                            key_strain = 0.8 * max_strain_val
                            key_idx = int(np.argmin(np.abs(strain - key_strain)))
            else:
                # 静态压缩曲线：使用标准密实化点检测
                key_strain = detect_densification_point(strain, stress)
                key_idx = int(np.argmin(np.abs(strain - key_strain)))
        else:
            # 剪切曲线：直接取最后一个点（包括动态剪切）
            key_idx = len(strain) - 1

        key_stress = float(stress[key_idx])
        key_strain = float(strain[key_idx])

        # 能量吸收 EA (从起点到关键点的积分面积)
        # E_total = ∫σdε, 单位: MPa = N/mm² = 1 mJ/mm³
        E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
        # EA = E_total × 体积, 单位: mJ
        EA = E_total * V0

        # 比吸能 SEA = EA / 质量
        # 质量 = 相对密度 × 体积 × 绝对密度(1.01e-09 tonne/mm³)
        mass = rho_r * V0 * 1.01e-09  # 单位: tonne
        SEA = EA / mass if mass > 0 else 0.0  # 单位: mJ/tonne

        return {
            'modulus': K,
            'modulus_type': "Young's Modulus" if is_compression else 'Shear Modulus',
            'lin_idx': lin_idx,
            'yield_strain': yield_strain,
            'yield_stress': yield_stress,
            'yield_idx': yield_idx,
            'key_strain': key_strain,
            'key_stress': key_stress,
            'key_idx': key_idx,
            'key_point_type': 'Densified' if is_compression else 'Last',
            'EA': EA,
            'SEA': SEA
        }

    def show_statistics_3d(self):
        """显示3D统计曲面图"""
        import os
        import json

        try:
            # 1. 获取当前选择
            cell_type = self.dropdowns_page2["Cell type:"].currentText()
            curve_type = self.dropdowns_page2["Curve type:"].currentText()
            cell_size = self.cell_size_slider_page2.value() / 10.0

            # 2. 加载 feature_data.json
            feature_data_path = os.path.join(BASE_DIR, "work", "feature_data.json")
            if not os.path.exists(feature_data_path):
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Feature data file not found:\n{feature_data_path}")
                return

            with open(feature_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 3. 筛选匹配的 keys (cell_type + cell_size)
            pattern = f"{cell_type}_{int(cell_size)}_"
            matching_data = {k: v for k, v in data.items() if k.startswith(pattern)}

            if not matching_data:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "No Data",
                    f"No data found for {cell_type} with cell size {cell_size}mm")
                return

            # 4. 打开 3D 统计对话框 (非阻塞，与主界面并行)
            # 保存引用防止被垃圾回收
            if not hasattr(self, '_statistics_dialogs'):
                self._statistics_dialogs = []
            dialog = Statistics3DDialog(matching_data, cell_type, cell_size, curve_type, self)
            self._statistics_dialogs.append(dialog)
            dialog.show()

        except Exception as e:
            import traceback
            traceback.print_exc()
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to show statistics:\n{str(e)}")

    def show_batch_config(self):
        """显示批量配置对话框"""
        try:
            from batch_config_dialog import BatchConfigDialog

            if not hasattr(self, 'batch_config'):
                self.batch_config = {}

            dialog = BatchConfigDialog(self.batch_config, self)
            if dialog.exec_() == dialog.Accepted:
                self.batch_config = dialog.get_config()
                print("批量配置已更新:", self.batch_config)
        except ImportError:
            # 如果没有配置对话框，显示简单的消息
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "批量配置",
                                  "批量配置功能需要额外的配置对话框模块。\n请手动设置参数组合。")

    def show_completion_star(self):
        """显示完成状态"""
        # 显示勾选符号表示完成
        self.triangle_button.setText("Done!")

        # 3秒后恢复原始文本 "PBS Script"
        QTimer.singleShot(3000, lambda: self.triangle_button.setText("PBS Script"))

    def generate_master_control_script(self):
        """生成主控制脚本用于并行计算"""
        try:
            from datetime import datetime
            import glob

            # 使用task文件夹作为输出目录
            if not hasattr(self, 'current_task_dir'):
                print("错误: 未找到任务文件夹")
                return

            output_dir = self.current_task_dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 查找所有生成的批处理脚本
            script_pattern = os.path.join(output_dir, "run_all_scripts_*_*.sh")
            batch_scripts = glob.glob(script_pattern)
            batch_scripts.sort()  # 按文件名排序

            if not batch_scripts:
                print("未找到批处理脚本文件，请先运行triangle_button生成脚本")
                return

            # 生成主控制脚本
            master_script_name = f"master_control_{timestamp}.sh"
            master_script_path = os.path.join(output_dir, master_script_name)

            # 创建主控制脚本内容
            script_content = [
                "#!/bin/bash",
                "# 主控制脚本 - 并行执行批处理脚本（许可证优化版本）",
                f"# 自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "# 显示Logo",
                "clear",
                'echo "================================================================="',
                'echo "     _____ _____ ____  _____ ____  _______   ____ _____  _   _ "',
                'echo "    |  ___| ____/ ___||_   _|  _ \\|  ___\\ \\ / /  ___|| \\ | |"',
                'echo "    | |_  | |__ \\___ \\  | | | |_) | |_   \\ V /| |__  |  \\| |"',
                'echo "    |  _| |  __| ___) | | | |  _ <|  _|   | | |  __| | . \\` |"',
                'echo "    |_|   |____||____/  |_| |_| \\_\\_|     |_| |____||_|\\  |_|"',
                'echo "                                                              "',
                'echo "            Smart Generator - License Optimized Parallel     "',
                'echo "================================================================="',
                'echo "启动并行计算 - 许可证优化版本"',
                "",
                "# 确保在正确的目录中执行",
                'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
                'cd "$script_dir"',
                'echo "执行目录: $script_dir"',
                "",
                "# Abaqus环境设置 - 根据需要取消注释",
                "# module load abaqus",
                "",
                "# 创建错误日志目录",
                'log_dir="./logs"',
                'mkdir -p "$log_dir"',
                'echo "错误日志将保存到: $log_dir"',
                "",
                "# 批处理脚本列表"
            ]

            # 添加脚本文件列表
            script_content.append("batch_files=(")
            for script in batch_scripts:
                script_name = os.path.basename(script)
                script_content.append(f'    "{script_name}"')
            script_content.append(")")

            script_content.extend([
                "",
                'if [ ${#batch_files[@]} -eq 0 ]; then',
                '    echo "未找到批处理脚本文件"',
                '    exit 1',
                'fi',
                "",
                'echo "找到 ${#batch_files[@]} 个批处理脚本，开始并行执行（许可证优化）..."',
                "",
                "# 启动所有批处理脚本（添加延迟和进程隔离）",
                "pids=()",
                'for i in "${!batch_files[@]}"; do',
                '    script="${batch_files[$i]}"',
                '    log_file="$log_dir/group$(($i + 1))_errors.log"',
                '    echo "启动 $script -> $log_file (延迟 $((i * 10)) 秒)"',
                "",
                '    chmod +x "$script"',
                '    # 错峰启动避免许可证冲突',
                '    sleep $((i * 10))',
                '    # 使用setsid创建独立进程组，模拟独立终端',
                '    setsid ./"$script" > "$log_file" 2>&1 &',
                '    pids+=($!)',
                'done',
                "",
                "# 监控进度",
                'echo ""',
                'echo "监控任务进度 (Ctrl+C 停止监控，不会停止后台任务)..."',
                'echo "按 \'l\' 查看实时日志，按 \'q\' 退出日志查看"',
                'echo ""'
            ])

            # 添加与原脚本相同的监控函数
            script_content.extend([
                "",
                "# 事件驱动监控函数",
                "monitor_progress() {",
                "    local last_check_time=$(date +%s)",
                "    declare -A last_log_sizes",
                "",
                "    # 初始化日志文件大小记录",
                '    for i in "${!batch_files[@]}"; do',
                '        log_file="$log_dir/group$(($i + 1))_errors.log"',
                '        if [ -f "$log_file" ]; then',
                '            last_log_sizes[$i]=$(wc -c < "$log_file" 2>/dev/null || echo 0)',
                "        else",
                "            last_log_sizes[$i]=0",
                "        fi",
                "    done",
                "",
                "    while true; do",
                "        running=0",
                "        has_changes=false",
                "        current_time=$(date +%s)",
                "",
                "        # 检查是否有日志文件变化或足够时间过去（最少3秒强制刷新一次）",
                '        for i in "${!batch_files[@]}"; do',
                '            log_file="$log_dir/group$(($i + 1))_errors.log"',
                '            if [ -f "$log_file" ]; then',
                '                current_size=$(wc -c < "$log_file" 2>/dev/null || echo 0)',
                '                if [ "$current_size" != "${last_log_sizes[$i]}" ]; then',
                "                    has_changes=true",
                "                    last_log_sizes[$i]=$current_size",
                "                fi",
                "            fi",
                "        done",
                "",
                "        # 检查进程状态",
                '        for pid in "${pids[@]}"; do',
                '            if kill -0 "$pid" 2>/dev/null; then',
                "                running=$((running + 1))",
                "            fi",
                "        done",
                "",
                "        if [ $running -eq 0 ]; then",
                '            echo "$(date \'+%H:%M:%S\') - 所有任务已完成！"',
                "            break",
                "        fi",
                "",
                "        # 只有当有变化或超过强制刷新间隔时才显示状态",
                '        if [ "$has_changes" = true ] || [ $((current_time - last_check_time)) -ge 30 ]; then',
                "            last_check_time=$current_time",
                "",
                "            # 显示各任务详细状态",
                '            echo "$(date \'+%H:%M:%S\') - 任务状态更新:"',
                '            for i in "${!batch_files[@]}"; do',
                '                script="${batch_files[$i]}"',
                '                log_file="$log_dir/group$(($i + 1))_errors.log"',
                '                pid="${pids[$i]}"',
                "",
                '                if kill -0 "$pid" 2>/dev/null; then',
                '                    status="运行中"',
                '                    if command -v ps >/dev/null 2>&1; then',
                '                        runtime=$(ps -p $pid -o etime= 2>/dev/null | tr -d \' \' || echo "未知")',
                '                        resource_info="(运行时间:${runtime})"',
                "                    else",
                '                        resource_info=""',
                "                    fi",
                '                    if [ -f "$log_file" ]; then',
                '                        latest_logs=$(tail -n 3 "$log_file" 2>/dev/null | tr \'\\n\' \' | \' | sed \'s/ | $//\')',
                '                        if [ -n "$latest_logs" ]; then',
                '                            log_info="$latest_logs"',
                "                        else",
                '                            log_info="日志: 生成中..."',
                "                        fi",
                "                    else",
                '                        log_info="日志: 等待中..."',
                "                    fi",
                "                else",
                '                    status="已完成"',
                '                    resource_info=""',
                '                    if [ -f "$log_file" ]; then',
                '                        if grep -q "SUCCESS:" "$log_file" 2>/dev/null; then',
                '                            success_count=$(grep -c "SUCCESS:" "$log_file" 2>/dev/null)',
                '                            log_info="| 状态: 成功完成 (${success_count}个脚本)"',
                '                        elif grep -q "FAILED:" "$log_file" 2>/dev/null; then',
                '                            failed_count=$(grep -c "FAILED:" "$log_file" 2>/dev/null)',
                '                            log_info="| 状态: 发现失败 (${failed_count}个脚本)"',
                '                        elif grep -q "PARTIAL:" "$log_file" 2>/dev/null; then',
                '                            partial_count=$(grep -c "PARTIAL:" "$log_file" 2>/dev/null)',
                '                            log_info="| 状态: 部分完成 (${partial_count}个脚本数据不足)"',
                "                        else",
                '                            log_info="| 状态: 运行中或已结束"',
                "                        fi",
                "                    else",
                '                        log_info="| 状态: 无日志"',
                "                    fi",
                "                fi",
                "",
                '                echo "  Group $(($i + 1)): $status $resource_info"',
                '                if [ -n "$log_info" ]; then',
                '                    echo "       $log_info"',
                "                fi",
                '                echo ""',
                "            done",
                "",
                '            completion_percent=$(( (${#batch_files[@]} - running) * 100 / ${#batch_files[@]} ))',
                '            echo "进度: ${completion_percent}% (运行中: $running/${#batch_files[@]})"',
                '            echo "----------------------------------------"',
                "        fi",
                "",
                "        # 短暂等待以降低CPU使用率",
                "        sleep 1",
                "    done",
                "}",
                "",
                "# 启动监控",
                "monitor_progress",
                "",
                'echo ""',
                'echo "所有批处理任务已完成"',
                'echo "日志文件位置: $log_dir"',
                "",
                "# 生成并行执行总结报告",
                'summary_file="$log_dir/parallel_summary.log"',
                'echo "Parallel Execution Summary Report (License Optimized)" > "$summary_file"',
                'echo "=====================================================" >> "$summary_file"',
                'echo "Execution completed at: $(date)" >> "$summary_file"',
                'echo "Total parallel batches: ${#batch_files[@]}" >> "$summary_file"',
                'echo "License optimization: Staggered start + Process isolation" >> "$summary_file"',
                'echo "Log directory: $log_dir" >> "$summary_file"',
                'echo "" >> "$summary_file"',
                "",
                'echo "检查各任务完成情况:"',
                "completed_count=0",
                "error_count=0",
                'for i in "${!batch_files[@]}"; do',
                '    log_file="$log_dir/group$(($i + 1))_errors.log"',
                "    batch_num=$(($i + 1))",
                "",
                '    if [ -f "$log_file" ]; then',
                '        if grep -q "SUCCESS:" "$log_file" 2>/dev/null; then',
                "            completed_count=$((completed_count + 1))",
                '            success_count=$(grep -c "SUCCESS:" "$log_file" 2>/dev/null)',
                '            echo "  Group $batch_num: 成功完成 (${success_count}个脚本) - 日志: $log_file"',
                '            echo "Group $batch_num: SUCCESS" >> "$summary_file"',
                '        elif grep -q "FAILED:" "$log_file" 2>/dev/null; then',
                "            error_count=$((error_count + 1))",
                '            failed_count=$(grep -c "FAILED:" "$log_file" 2>/dev/null)',
                '            echo "  Group $batch_num: 发现失败 (${failed_count}个脚本) - 日志: $log_file"',
                '            echo "Group $batch_num: ERROR" >> "$summary_file"',
                "        else",
                '            echo "  Group $batch_num: 状态未知 - 日志: $log_file"',
                '            echo "Group $batch_num: UNKNOWN" >> "$summary_file"',
                "        fi",
                "    else",
                '        echo "  Group $batch_num: 无日志文件"',
                '        echo "Group $batch_num: NO_LOG" >> "$summary_file"',
                "    fi",
                "done",
                "",
                'echo "" >> "$summary_file"',
                'echo "Summary:" >> "$summary_file"',
                'echo "  Completed: $completed_count" >> "$summary_file"',
                'echo "  Errors: $error_count" >> "$summary_file"',
                'echo "  Total: ${#batch_files[@]}" >> "$summary_file"',
                "",
                'echo ""',
                'echo "总结: 成功=$completed_count, 错误=$error_count, 总计=${#batch_files[@]}"',
                'echo "详细报告已保存到: $summary_file"'
            ])

            # 写入主控制脚本文件
            with open(master_script_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(script_content))

            # 设置执行权限
            import stat
            os.chmod(master_script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

            print(f"主控制脚本已生成: {master_script_path}")
            print(f"找到 {len(batch_scripts)} 个批处理脚本:")
            for i, script in enumerate(batch_scripts):
                print(f"  Group {i+1}: {os.path.basename(script)}")
            print(f"\n执行命令: ./{master_script_name}")
            print("特性: 错峰启动(10秒间隔) + 进程隔离，确保许可证使用受控")

        except Exception as e:
            print(f"生成主控制脚本时出错: {str(e)}")

    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于窗口边缘调整大小"""
        if event.button() == Qt.LeftButton:
            self.resize_direction = self.get_resize_direction(event.pos())
            if self.resize_direction:
                self.is_resizing = True
                self.resize_start_pos = event.globalPos()
                self.resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 调整窗口大小或更新鼠标光标"""
        if self.is_resizing:
            self.resize_window(event.globalPos())
            event.accept()
        else:
            # 更新鼠标光标
            direction = self.get_resize_direction(event.pos())
            self.update_cursor(direction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 结束调整大小"""
        if event.button() == Qt.LeftButton and self.is_resizing:
            self.is_resizing = False
            self.resize_direction = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        super().mouseReleaseEvent(event)

    def get_resize_direction(self, pos):
        """获取鼠标位置对应的调整方向"""
        rect = self.rect()
        x, y = pos.x(), pos.y()
        margin = self.resize_margin

        # 检查八个方向
        on_left = x <= margin
        on_right = x >= rect.width() - margin
        on_top = y <= margin
        on_bottom = y >= rect.height() - margin

        if on_top and on_left:
            return "top_left"
        elif on_top and on_right:
            return "top_right"
        elif on_bottom and on_left:
            return "bottom_left"
        elif on_bottom and on_right:
            return "bottom_right"
        elif on_top:
            return "top"
        elif on_bottom:
            return "bottom"
        elif on_left:
            return "left"
        elif on_right:
            return "right"
        return None

    def update_cursor(self, direction):
        """根据调整方向更新鼠标光标"""
        if direction in ["top", "bottom"]:
            self.setCursor(Qt.SizeVerCursor)
        elif direction in ["left", "right"]:
            self.setCursor(Qt.SizeHorCursor)
        elif direction in ["top_left", "bottom_right"]:
            self.setCursor(Qt.SizeFDiagCursor)
        elif direction in ["top_right", "bottom_left"]:
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def resize_window(self, global_pos):
        """根据鼠标位置调整窗口大小"""
        if not self.resize_direction:
            return

        delta = global_pos - self.resize_start_pos
        geo = self.resize_start_geometry
        new_geo = geo

        # 最小窗口尺寸
        min_width = 800
        min_height = 600

        if "left" in self.resize_direction:
            new_x = geo.x() + delta.x()
            new_width = max(geo.width() - delta.x(), min_width)
            if new_width > min_width:
                new_geo.setX(new_x)
            new_geo.setWidth(new_width)

        if "right" in self.resize_direction:
            new_width = max(geo.width() + delta.x(), min_width)
            new_geo.setWidth(new_width)

        if "top" in self.resize_direction:
            new_y = geo.y() + delta.y()
            new_height = max(geo.height() - delta.y(), min_height)
            if new_height > min_height:
                new_geo.setY(new_y)
            new_geo.setHeight(new_height)

        if "bottom" in self.resize_direction:
            new_height = max(geo.height() + delta.y(), min_height)
            new_geo.setHeight(new_height)

        self.setGeometry(new_geo)

    def generate_pbs_script(self):
        """生成PBS脚本文件"""
        try:
            from datetime import datetime
            import glob

            # 使用task文件夹作为输出目录
            if not hasattr(self, 'current_task_dir'):
                print("错误: 未找到任务文件夹")
                return

            output_dir = self.current_task_dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 查找最新生成的run_all脚本
            run_all_pattern = os.path.join(output_dir, "run_all_*.sh")
            run_all_scripts = glob.glob(run_all_pattern)

            if not run_all_scripts:
                print("未找到run_all脚本文件，无法生成PBS脚本")
                return

            # 选择最新的run_all脚本
            run_all_scripts.sort()
            latest_run_all_script = run_all_scripts[-1]
            run_all_script_name = os.path.basename(latest_run_all_script)

            # 生成PBS脚本名称 (使用run_all脚本的配置名称)
            config_name = run_all_script_name.replace("run_all_", "").replace(".sh", "")
            pbs_script_name = f"pbs_submit_{config_name}.pbs"
            pbs_script_path = os.path.join(output_dir, pbs_script_name)

            # 获取task文件夹的名称(例如: task_20250930_123456)
            task_folder_name = os.path.basename(output_dir)

            # 获取generate_script的绝对路径
            generate_script_dir = os.path.dirname(output_dir)

            # 创建logs目录
            logs_dir = os.path.join(output_dir, "logs")
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
                print(f"已创建日志目录: {logs_dir}")

            # 获取PBS配置
            pbs_config = Config.get_pbs_header()

            # 创建PBS脚本内容
            pbs_content = [
                "#!/bin/bash",
                f"#PBS -N abaqus_{config_name}",
                f"#PBS -P {pbs_config['project']}",
                f"#PBS -q {pbs_config['queue']}",
                f"#PBS -l walltime={pbs_config['walltime']}",
                f"#PBS -l select=1:ncpus={pbs_config['ncpus']}:mem={pbs_config['memory']}",
                f"#PBS -j {pbs_config['join_oe']}",
                f"#PBS -o {Config.BASE_SCRIPT_PATH}/{task_folder_name}/logs/run_all_{config_name}.log",
                "",
                "cd $PBS_O_WORKDIR",
                "",
                "# Setup real-time logging",
                f"LOGDIR=\"{Config.BASE_SCRIPT_PATH}/{task_folder_name}/logs\"",
                "mkdir -p $LOGDIR",
                f"REALTIME_LOG=\"$LOGDIR/realtime_{config_name}_$PBS_JOBID.log\"",
                "",
                "# Execute with real-time output",
                f'bash "{Config.BASE_SCRIPT_PATH}/{task_folder_name}/{run_all_script_name}" 2>&1 | tee "$REALTIME_LOG" &',
                "wait",
                'echo "Abaqus tasks finished."'
            ]

            # 写入PBS脚本文件
            with open(pbs_script_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(pbs_content))

            # 设置执行权限
            import stat
            os.chmod(pbs_script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

            print(f"PBS脚本已生成: {pbs_script_path}")
            print(f"关联的run_all脚本: {run_all_script_name}")
            print(f"提交命令: qsub {pbs_script_name}")

        except Exception as e:
            print(f"生成PBS脚本时出错: {str(e)}")




    def _old_unused_stylesheet(self):
        return """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:0.5 #34495e, stop:1 #2c3e50);
            }

            #cyberpunk_theme_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4caf50, stop:1 #2e7d32);
                border: 2px solid #1b5e20;
                border-radius: 20px;
            }

            #forest_theme_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #66bb6a, stop:1 #43a047);
            }

            #forest_theme_btn[active="true"] {
                border: 3px solid #81c784;
            }

            #sunset_theme_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ff7043, stop:1 #8e24aa);
                border: 2px solid #6a1b9a;
                border-radius: 20px;
            }

            #sunset_theme_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ff8a65, stop:1 #ab47bc);
            }

            #sunset_theme_btn[active="true"] {
                border: 3px solid #81c784;
            }

            #space_theme_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3498db, stop:1 #2c3e50);
                border: 2px solid #6a1b9a;
                border-radius: 20px;
            }

            #space_theme_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5dade2, stop:1 #34495e);
            }

            #space_theme_btn[active="true"] {
                border: 3px solid #81c784;
            }

            #title {
                font-size: 48px;
                font-weight: bold;
                color: #e8f5e8;
                padding: 30px;
                margin-bottom: 15px;
            }

            #form_frame {
                background: rgba(46, 125, 50, 0.15);
                border: 2px solid #4caf50;
                border-radius: 20px;
                padding: 40px;
                margin: 15px;
            }

            #field_label {
                font-size: 27px;
                font-weight: 600;
                color: #e8f5e8;
                padding: 8px 0;
            }

            #dropdown {
                padding: 16px 20px;
                border: 2px solid #66bb6a;
                border-radius: 10px;
                background: rgba(27, 94, 32, 0.8);
                font-size: 27px;
                color: #e8f5e8;
                min-width: 280px;
                min-height: 20px;
            }

            #dropdown:hover {
                border-color: #4caf50;
                background: rgba(27, 94, 32, 0.9);
            }

            #dropdown QAbstractItemView {
                border: 1px solid #4caf50;
                background: #1b5e20;
                selection-background-color: #4caf50;
                selection-color: #e8f5e8;
                border-radius: 5px;
                padding: 5px;
            }

            #generate_button {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4caf50, stop:1 #2e7d32);
                color: #e8f5e8;
                border: 2px solid #1b5e20;
                padding: 20px 60px;
                font-size: 27px;
                font-weight: bold;
                border-radius: 25px;
                min-width: 220px;
                min-height: 25px;
            }

            #generate_button:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #66bb6a, stop:1 #43a047);
            }

            #checkbox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #66bb6a;
                border-radius: 4px;
                background: rgba(27, 94, 32, 0.8);
            }

            #checkbox::indicator:checked {
                background: #4caf50;
                border-color: #2e7d32;
            }

            #slider::groove:horizontal {
                border: none;
                height: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1b5e20, stop:1 #2e7d32);
                border-radius: 5px;
            }

            #slider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #2e7d32);
                border: 2px solid #e8f5e8;
                width: 22px;
                height: 22px;
                margin: -8px 0;
                border-radius: 13px;
            }

            #slider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4caf50, stop:1 #2e7d32);
                border-radius: 5px;
            }

            #batch_config_button {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #2e7d32);
                color: #e8f5e8;
                border: 2px solid #1b5e20;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: normal;
                font-size: 11px;
                min-width: 80px;
                max-height: 24px;
            }

            #batch_config_button:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #43a047);
                border-color: #2e7d32;
            }

            #batch_config_button:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #388e3c, stop:1 #1b5e20);
            }

            #batch_config_button:disabled {
                background: #757575;
                color: #bdbdbd;
                border-color: #424242;
            }
        """

    def get_space_stylesheet(self):
        # 合并标题栏样式和主题样式 - 放大30%
        title_bar_style = get_title_bar_stylesheet()

        main_style = """
            /* 深色主题 - 统一蓝色系 - 放大30% */
            * {
                font-family: Arial, sans-serif;
            }

            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1d29, stop:1 #0f1419);
            }

            /* 排除3D可视化窗口的圆角 - VTK/PyVista不支持圆角 */
            #vtk_3d_widget, #vtk_3d_widget * {
                border-radius: 0px !important;
            }

            QVTKRenderWindowInteractor {
                border-radius: 0px;
            }"""

        return title_bar_style + main_style + """

            QMenuBar {
                background-color: #1e2330;
                color: #c5d1de;
                border-bottom: 3px solid #2d3548;
                font-size: 18px;
            }

            QMenuBar::item {
                background: transparent;
                padding: 10px 21px;
            }

            QMenuBar::item:selected {
                background: #2d3548;
            }

            QMenu {
                background-color: #1e2330;
                color: #c5d1de;
                border: 1px solid #2d3548;
                border-radius: 5px;
                font-size: 16px;
            }

            QMenu::item:selected {
                background-color: #3d5a80;
                color: #ffffff;
            }

            #title {
                font-size: 52px;
                font-weight: 600;
                color: #e1e8f0;
                padding: 39px;
                margin-bottom: 20px;
                letter-spacing: 1px;
            }

            #form_frame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #262b3d, stop:1 #1e2330);
                border: 3px solid #3d5a80;
                border-radius: 10px;
                padding: 52px;
                margin: 20px;
            }

            #field_label {
                font-size: 29px;
                font-weight: 600;
                color: #5a8bc0;
                padding: 10px 0;
            }

            #dropdown {
                padding: 12px 16px;
                border: 2px solid #3d5a80;
                border-radius: 4px;
                background: #1e2330;
                font-size: 26px;
                color: #5a8bc0;
                min-width: 300px;
                min-height: 20px;
            }

            #dropdown:hover {
                border-color: #5a7fa8;
                background: #262b3d;
            }

            #dropdown:focus {
                border-color: #6b93c0;
                outline: none;
                background: #262b3d;
            }

            #dropdown QAbstractItemView {
                border: 1px solid #3d5a80;
                background: #1e2330;
                color: #c5d1de;
                selection-background-color: #3d5a80;
                selection-color: #ffffff;
                border-radius: 5px;
                padding: 7px;
                font-size: 24px;
            }

            #dropdown QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 30px;
            }

            #dropdown QAbstractItemView::item:hover {
                background-color: #2d3548;
                color: #e1e8f0;
            }

            #generate_button {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a7ba7, stop:1 #3d5a80);
                color: #ffffff;
                border: none;
                padding: 26px 78px;
                font-size: 29px;
                font-weight: 600;
                border-radius: 5px;
                min-width: 286px;
                min-height: 33px;
            }

            #generate_button:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5a8bc0, stop:1 #4a7ba7);
            }

            #generate_button:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3d5a80, stop:1 #2d4660);
            }

            #checkbox::indicator {
                width: 26px;
                height: 26px;
                border: 3px solid #5a8bc0;
                border-radius: 4px;
                background: #1e2330;
            }

            #checkbox::indicator:hover {
                border-color: #5a7fa8;
            }

            #checkbox::indicator:checked {
                background: #3d5a80;
                border-color: #3d5a80;
            }

            /* 可视化区域复选框样式 */
            #viz_checkbox {
                color: #c5d1de;
                font-size: 23px;
                font-weight: 500;
                spacing: 10px;
            }

            #viz_checkbox::indicator {
                width: 26px;
                height: 26px;
                border: 3px solid #5a8bc0;
                border-radius: 5px;
                background: #1e2330;
            }

            #viz_checkbox::indicator:hover {
                border-color: #6c5ce7;
            }

            #viz_checkbox::indicator:checked {
                background: #6c5ce7;
                border-color: #6c5ce7;
            }

            #slider {
                min-height: 35px;
                padding: 0 15px;
            }

            #slider::groove:horizontal {
                border: none;
                height: 10px;
                background: #1e2330;
                border-radius: 5px;
                margin: 0 5px;
            }

            #slider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a7fa8, stop:1 #3d5a80);
                border: 2px solid #6b93c0;
                width: 24px;
                height: 24px;
                margin: -8px -5px;
                border-radius: 12px;
            }

            #slider::handle:horizontal:hover {
                background: #5a8bc0;
                border-color: #7dadd6;
            }

            #slider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3d5a80, stop:1 #4a7ba7);
                border-radius: 5px;
                margin: 0 5px;
            }

            #slider::add-page:horizontal {
                background: #1e2330;
                border-radius: 5px;
                margin: 0 5px;
            }

            #slider_value_label {
                color: #5a8bc0;
                font-size: 23px;
                font-weight: 600;
                padding-left: 13px;
                min-width: 52px;
            }

            #batch_config_button {
                background: #262b3d;
                color: #c5d1de;
                border: 3px solid #3d5a80;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: 600;
                font-size: 14px;
                min-width: 104px;
                max-height: 31px;
            }

            #batch_config_button:hover {
                background: #3d5a80;
                border-color: #5a7fa8;
                color: #ffffff;
            }

            #batch_config_button:pressed {
                background: #2d4660;
            }

            #batch_config_button:disabled {
                background: #1e2330;
                color: #4d5563;
                border-color: #2d3548;
            }
        """

    def get_stylesheet(self):
        return self.get_space_stylesheet()

    def get_original_stylesheet(self):
        return """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
            }
            
            #title {
                font-size: 48px;
                font-weight: bold;
                color: white;
                padding: 30px;
                margin-bottom: 15px;
            }
            
            #form_frame {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 40px;
                margin: 15px;
            }
            
            #field_label {
                font-size: 27px;
                font-weight: 600;
                color: #2c3e50;
                padding: 8px 0;
            }
            
            #dropdown {
                padding: 16px 20px;
                border: 2px solid #bdc3c7;
                border-radius: 10px;
                background: white;
                font-size: 27px;
                color: #2c3e50;
                min-width: 280px;
                min-height: 20px;
            }
            
            #dropdown:hover {
                border-color: #3498db;
                background: #f8f9fa;
            }
            
            #dropdown:focus {
                border-color: #2980b9;
                outline: none;
            }
            
            #dropdown::drop-down {
                border: none;
                width: 30px;
            }
            
            #dropdown::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #7f8c8d;
                margin-right: 5px;
            }
            
            #dropdown QAbstractItemView {
                border: 1px solid #bdc3c7;
                background: white;
                selection-background-color: #3498db;
                selection-color: white;
                border-radius: 5px;
                padding: 5px;
            }
            
            #generate_button {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                padding: 20px 60px;
                font-size: 27px;
                font-weight: bold;
                border-radius: 30px;
                min-width: 220px;
                min-height: 25px;
            }
            
            #generate_button:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #45a049, stop:1 #3d8b40);
            }
            
            #generate_button:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3d8b40, stop:1 #2e7031);
            }
            
            #generate_button:disabled {
                background: #95a5a6;
                color: #ecf0f1;
            }

            #checkbox {
                spacing: 8px;
                min-width: 20px;
                min-height: 20px;
            }

            #checkbox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }

            #checkbox::indicator:hover {
                border-color: #3498db;
            }

            #checkbox::indicator:checked {
                background: #3498db;
                border-color: #2980b9;
                image: none;
            }

            #checkbox::indicator:checked:hover {
                background: #2980b9;
            }

        #slider {
            height: 25px;
            background: transparent;
        }

        #slider::groove:horizontal {
            border: none;
            height: 8px;
            background: rgba(255, 255, 255, 100);
            border-radius: 4px;
        }

        #slider::handle:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #ffffff, stop:1 #e0e0e0);
            border: 2px solid #cccccc;
            width: 20px;
            height: 20px;
            margin: -8px 0;
            border-radius: 12px;
        }

        #slider::handle:horizontal:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #f0f0f0, stop:1 #d0d0d0);
            border: 2px solid #aaaaaa;
        }

        #slider::handle:horizontal:pressed {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e0e0e0, stop:1 #c0c0c0);
            border: 2px solid #888888;
        }

        #slider::sub-page:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #9c27b0, stop:1 #7b1fa2);
            border-radius: 4px;
        }

        #slider::add-page:horizontal {
            background: rgba(255, 255, 255, 100);
            border-radius: 4px;
        }

        #slider:focus::sub-page:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #8e24aa, stop:1 #6a1b9a);
            border-radius: 5px;
        }

        /* Disabled state - 完全灰色主题 */
        #slider:disabled {
            opacity: 0.7;
        }

        #slider:disabled::groove:horizontal {
            background: rgba(189, 195, 199, 100);
            border-radius: 4px;
        }

        #slider:disabled::handle:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #bdc3c7, stop:1 #95a5a6);
            border: none;
        }

        #slider:disabled::sub-page:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #95a5a6, stop:1 #7f8c8d);
        }

        #slider:disabled::add-page:horizontal {
            background: #ecf0f1;
        }
        """


if __name__ == "__main__":
    pass