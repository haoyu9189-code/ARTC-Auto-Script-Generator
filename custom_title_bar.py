#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义标题栏模块
实现无边框窗口的自定义标题栏，包含标题、窗口控制按钮和拖动功能

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon
import os
import sys


class CustomTitleBar(QWidget):
    """自定义标题栏组件"""

    def __init__(self, parent=None, title="Smart AM"):
        super().__init__(parent)
        self.parent = parent
        self.title_text = title
        self.is_maximized = False

        # 用于拖动窗口
        self.drag_position = QPoint()
        self.is_dragging = False

        # 页面切换相关
        self.current_page = 0  # 0: Smart Generator, 1: Result Preview

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 标题栏高度: 60 * 1.3 = 78
        self.setFixedHeight(78)

        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 0, 0)  # 15 * 1.3 ≈ 20
        layout.setSpacing(0)

        # Logo图标: 36 * 1.3 ≈ 47
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(47, 47)
        self.icon_label.setScaledContents(True)

        # 尝试加载图标
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                # 优先使用 assets/icons 目录
                base_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons')
                if not os.path.exists(os.path.join(base_path, 'logo.svg')):
                    base_path = os.path.join(os.path.dirname(__file__), 'work')

            # Prioritize SVG for better quality
            icon_path = os.path.join(base_path, 'logo.svg')
            if not os.path.exists(icon_path):
                icon_path = os.path.join(base_path, 'logo.ico')

            if os.path.exists(icon_path):
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap(icon_path)
                self.icon_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Failed to load title bar icon: {e}")

        layout.addWidget(self.icon_label)
        layout.addSpacing(20)  # 15 * 1.3 ≈ 20

        # 应用标题文本 - 使用富文本让 AM 显示为亮紫色
        self.title_label = QLabel()
        self.title_label.setObjectName("title_bar_label")
        # 解析标题，将 "AM" 部分变成亮紫色
        if "AM" in self.title_text:
            rich_text = self.title_text.replace("AM", '<span style="color: #a29bfe;">AM</span>')
            self.title_label.setText(rich_text)
        else:
            self.title_label.setText(self.title_text)
        layout.addWidget(self.title_label)

        layout.addSpacing(39)  # 30 * 1.3 = 39

        # 页面切换按钮
        self.page_smart_gen = QPushButton("Smart Generator")
        self.page_smart_gen.setObjectName("page_tab_button")
        self.page_smart_gen.setCheckable(True)
        self.page_smart_gen.setChecked(True)  # 默认选中
        self.page_smart_gen.clicked.connect(lambda: self.switch_page(0))
        layout.addWidget(self.page_smart_gen)

        self.page_result_preview = QPushButton("Result Preview")
        self.page_result_preview.setObjectName("page_tab_button")
        self.page_result_preview.setCheckable(True)
        self.page_result_preview.clicked.connect(lambda: self.switch_page(1))
        layout.addWidget(self.page_result_preview)

        # 弹簧，将按钮推到右侧
        layout.addStretch()

        # 最小化按钮: 69 * 1.3 ≈ 90, 48 * 1.3 ≈ 62
        self.min_button = QPushButton("−")
        self.min_button.setObjectName("title_bar_button")
        self.min_button.setFixedSize(90, 62)
        self.min_button.clicked.connect(self.minimize_window)
        self.min_button.setToolTip("最小化")
        layout.addWidget(self.min_button)

        # 最大化/还原按钮
        self.max_button = QPushButton("□")
        self.max_button.setObjectName("title_bar_button")
        self.max_button.setFixedSize(90, 62)
        self.max_button.clicked.connect(self.maximize_restore_window)
        self.max_button.setToolTip("最大化")
        layout.addWidget(self.max_button)

        # 关闭按钮
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("title_bar_close_button")
        self.close_button.setFixedSize(90, 62)
        self.close_button.clicked.connect(self.close_window)
        self.close_button.setToolTip("关闭")
        layout.addWidget(self.close_button)

    def minimize_window(self):
        """最小化窗口"""
        if self.parent:
            self.parent.showMinimized()

    def maximize_restore_window(self):
        """最大化/还原窗口"""
        if self.parent:
            if self.is_maximized:
                self.parent.showNormal()
                self.max_button.setText("□")
                self.max_button.setToolTip("最大化")
                self.is_maximized = False
            else:
                self.parent.showMaximized()
                self.max_button.setText("❐")
                self.max_button.setToolTip("向下还原")
                self.is_maximized = True

    def close_window(self):
        """关闭窗口"""
        if self.parent:
            self.parent.close()

    def mousePressEvent(self, event):
        """鼠标按下事件 - 开始拖动"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPos() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖动窗口"""
        if self.is_dragging and event.buttons() == Qt.LeftButton:
            # 如果窗口是最大化状态，先还原到正常状态
            if self.is_maximized:
                self.maximize_restore_window()
                # 调整拖动位置，使鼠标保持在标题栏的相对位置
                self.drag_position = QPoint(int(self.parent.width() / 2), int(self.height() / 2))

            self.parent.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 结束拖动"""
        self.is_dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 最大化/还原"""
        if event.button() == Qt.LeftButton:
            self.maximize_restore_window()
            event.accept()

    def update_title(self, title):
        """更新标题文本"""
        self.title_text = title
        self.title_label.setText(title)

    def switch_page(self, page_index):
        """切换页面"""
        if self.current_page == page_index:
            return  # 已经在当前页面，无需切换

        self.current_page = page_index

        # 更新按钮状态
        self.page_smart_gen.setChecked(page_index == 0)
        self.page_result_preview.setChecked(page_index == 1)

        # 通知父窗口切换页面
        if self.parent and hasattr(self.parent, 'switch_to_page'):
            self.parent.switch_to_page(page_index)


def get_title_bar_stylesheet():
    """返回与应用主题匹配的标题栏样式表 - 放大30%"""
    return """
        /* 自定义标题栏样式 - 深色主题（放大30%） */
        CustomTitleBar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #262b3d, stop:1 #1e2330);
            border-bottom: 1px solid #3d5a80;
        }

        #title_bar_label {
            color: #e1e8f0;
            font-size: 29px;  /* 22 * 1.3 ≈ 29 */
            font-weight: 600;
            padding-left: 10px;
        }

        #title_bar_button {
            background: transparent;
            color: #c5d1de;
            border: none;
            font-size: 36px;  /* 28 * 1.3 ≈ 36 */
            font-weight: 400;
        }

        #title_bar_button:hover {
            background: #3d5a80;
            color: #ffffff;
        }

        #title_bar_button:pressed {
            background: #2d4660;
        }

        #title_bar_close_button {
            background: transparent;
            color: #c5d1de;
            border: none;
            font-size: 31px;  /* 24 * 1.3 ≈ 31 */
            font-weight: 400;
        }

        #title_bar_close_button:hover {
            background: #e74c3c;
            color: #ffffff;
        }

        #title_bar_close_button:pressed {
            background: #c0392b;
        }

        /* 页面切换按钮样式 */
        #page_tab_button {
            background: transparent;
            color: #8a95a5;
            border: none;
            padding: 10px 26px;  /* 8*1.3≈10, 20*1.3=26 */
            font-size: 26px;  /* 20 * 1.3 = 26 */
            font-weight: 500;
        }

        #page_tab_button:hover {
            background: rgba(61, 90, 128, 0.3);
            color: #c5d1de;
        }

        #page_tab_button:checked {
            background: #3d5a80;
            color: #ffffff;
            border-bottom: 3px solid #5a8bc0;  /* 2 * 1.3 ≈ 3 */
        }

        #page_tab_button:pressed {
            background: #2d4660;
        }
    """
