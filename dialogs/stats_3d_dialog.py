#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D 统计曲面可视化对话框
从 qt_interface.py 拆出，保持行为不变。
"""

import os
import json
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QDesktopWidget,
)
from PyQt5.QtCore import Qt, QTimer

try:
    import sys
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    _parent_dir = os.path.dirname(_base_dir)
    _model_path = os.path.join(_parent_dir, '.claude', 'skills', 'material-assistant', 'model')
    if _model_path not in sys.path:
        sys.path.insert(0, _model_path)
    from feature_extract import detect_densification_point
except ImportError:
    detect_densification_point = None


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
