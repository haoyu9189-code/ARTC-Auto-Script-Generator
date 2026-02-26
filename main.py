#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口文件
运行此文件启动Qt界面应用程序

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import sys
import os

# 获取当前目录路径，兼容打包环境
def get_current_dir():
    """获取当前目录，兼容打包和开发环境"""
    if getattr(sys, 'frozen', False):
        # 打包环境：获取可执行文件所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：获取脚本文件所在目录
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_dir():
    """获取资源目录，兼容打包和开发环境"""
    if getattr(sys, 'frozen', False):
        # 打包环境：PyInstaller 解压资源到 _MEIPASS 临时目录
        return sys._MEIPASS
    else:
        # 开发环境：使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

current_dir = get_current_dir()
sys.path.insert(0, current_dir)

# 使用新的FileTracker类替代全局变量
from file_tracker import file_tracker

# 向后兼容的包装函数
def add_generated_file(file_path):
    """添加生成的文件到追踪列表（向后兼容）"""
    return file_tracker.add(file_path)

def get_generated_files():
    """获取本次运行生成的文件列表（向后兼容）"""
    return file_tracker.get_all()

def clear_generated_files():
    """清空生成文件追踪列表（向后兼容）"""
    file_tracker.clear()

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtGui import QIcon
    from qt_interface import ModernInterface
    from structure_set import get_crystal_structure
    import ctypes
    import platform
    from datetime import datetime
except ImportError as e:
    print("错误: 无法导入必要的模块")
    print(f"详细错误: {e}")
    print("请确保已安装PyQt5: pip install PyQt5")
    sys.exit(1)


# 导入新的脚本生成器模块
from shell_script_generator import generate_shell_script

# 原来的321行函数已被重构到 shell_script_generator.py
# 现在直接使用新模块的实现，消除了70%的代码重复


def generate_batch_on_exit():
    """程序退出时生成批处理文件"""
    try:
        print("\n程序退出，正在生成批处理文件...")

        # 获取generate_script目录
        from config import Config
        generate_script_dir = os.path.join(current_dir, Config.GENERATE_SCRIPT_DIR)
        if not os.path.exists(generate_script_dir):
            print("未找到generate_script目录，跳过批处理文件生成")
            return

        # 使用本次运行生成的文件列表，而不是遍历所有文件
        python_files = get_generated_files()

        if not python_files:
            print("本次运行未生成任何Python脚本文件，跳过批处理文件生成")
            return

        # 过滤确保文件仍然存在，并且分离前处理和后处理脚本
        preprocess_files = [
            f for f in python_files
            if os.path.exists(f) and f.endswith('_preprocess.py')
        ]
        postprocess_files = [
            f for f in python_files
            if os.path.exists(f) and f.endswith('_postprocess.py')
        ]

        # 如果有拆分的前处理/后处理脚本，使用优化的批处理生成器
        if preprocess_files and postprocess_files:
            print(f"本次运行生成了 {len(preprocess_files)} 个前处理脚本和 {len(postprocess_files)} 个后处理脚本")
            print("生成优化的批处理脚本（最小化CAE license占用）...")

            import platform
            if platform.system() == "Windows":
                from batch_script_generator import generate_split_batch_script
                generate_split_batch_script(
                    sorted(preprocess_files),
                    sorted(postprocess_files),
                    generate_script_dir
                )
            else:
                # Linux/Unix系统生成.sh文件
                from batch_script_generator import generate_split_shell_script
                generate_split_shell_script(
                    sorted(preprocess_files),
                    sorted(postprocess_files),
                    generate_script_dir
                )
        else:
            # 向后兼容：处理旧的单体脚本
            existing_files = [f for f in python_files if os.path.exists(f)]
            if not existing_files:
                print("本次生成的文件已不存在，跳过批处理文件生成")
                return

            python_files = sorted(existing_files)
            print(f"本次运行生成了 {len(python_files)} 个Python脚本文件")

            # 检测操作系统并生成相应的脚本
            import platform
            if platform.system() == "Windows":
                generate_shell_script(python_files, generate_script_dir, "bat")
            else:
                # Linux/Unix系统只生成.sh文件
                generate_shell_script(python_files, generate_script_dir, "sh")

    except Exception as e:
        print(f"生成批处理文件时出错: {e}")


def main():
    """主函数 - 启动Qt应用程序"""
    try:
        # 清空上次运行的文件追踪列表
        clear_generated_files()
        print("已清空文件追踪列表，开始新会话")

        # 创建generate_script文件夹用于存放生成的文件
        from config import Config
        generate_script_dir = os.path.join(current_dir, Config.GENERATE_SCRIPT_DIR)
        if not os.path.exists(generate_script_dir):
            os.makedirs(generate_script_dir)
            print(f"已创建文件夹: {generate_script_dir}")

        # 创建Qt应用程序实例
        # Linux 环境下检查 DISPLAY 环境变量
        if platform.system() == "Linux":
            display = os.environ.get('DISPLAY', '')
            print(f"DISPLAY 环境变量: {display}")
            if not display:
                print("警告: DISPLAY 环境变量未设置，窗口可能无法显示")
                print("请确保使用 ssh -X 或 ssh -Y 连接，或者设置 DISPLAY 环境变量")

        app = QApplication(sys.argv)

        # 打印 Qt 平台信息
        print(f"Qt Platform: {app.platformName()}")

        # 设置应用程序属性
        app.setApplicationName("智能生成器")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("ARTC")

        # 设置应用程序图标（Windows任务栏需要ICO或PNG格式）
        icon_path = None
        resource_dir = get_resource_dir()

        # 按优先级查找图标路径（使用资源目录，兼容打包环境）
        icon_search_paths = [
            os.path.join(resource_dir, "assets", "logo"),   # 优先使用 assets/logo
            os.path.join(resource_dir, "assets", "icons"),  # 备选 assets/icons
        ]

        for icon_base in icon_search_paths:
            for ext in ["ico", "png", "svg"]:
                candidate = os.path.join(icon_base, f"logo.{ext}")
                if os.path.exists(candidate):
                    icon_path = candidate
                    break
            if icon_path:
                break

        if icon_path:
            print(f"使用图标: {icon_path}")
            app.setWindowIcon(QIcon(icon_path))
        else:
            # 备用路径
            icon_path_alt = os.path.join(resource_dir, "work", "logo.svg")
            if os.path.exists(icon_path_alt):
                app.setWindowIcon(QIcon(icon_path_alt))
            else:
                print("警告: 未找到应用图标文件")

        # Windows特定: 设置任务栏图标
        if platform.system() == "Windows":
            try:
                # 设置应用程序ID，确保在任务栏显示正确的图标
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ARTC.ScriptGenerator.1.0")
            except:
                pass  # 如果设置失败，继续运行
        
        # 创建主窗口
        window = ModernInterface()

        # 显示窗口
        print("正在显示主窗口...")
        window.show()

        # Linux 下强制窗口激活
        if platform.system() == "Linux":
            from PyQt5.QtWidgets import QDesktopWidget

            # 获取屏幕尺寸
            screen = QDesktopWidget().screenGeometry()

            # 设置合理的窗口尺寸（留足边距给标题栏、任务栏等）
            # 使用屏幕尺寸的85%，最大不超过1400x900
            window_width = min(1400, int(screen.width() * 0.85))
            window_height = min(900, int(screen.height() * 0.85))
            window.resize(window_width, window_height)

            # 不设置窗口位置，让窗口管理器自己决定
            # 只确保窗口可见和激活
            window.raise_()
            window.activateWindow()

            # 强制刷新
            app.processEvents()

            print(f"窗口已创建 - 尺寸: {window.width()}x{window.height()}, 位置: ({window.x()}, {window.y()})")
            print(f"屏幕尺寸: {screen.width()}x{screen.height()}")
            print(f"窗口可见性: {window.isVisible()}")
            print("=" * 60)
            print("窗口已显示，位置由窗口管理器决定")
            print("=" * 60)

        # 可视化初始化已在 ModernInterface.__init__ 中通过 init_default_visualization 完成
        # 不再需要额外的 force_refresh，避免重复更新

        # 运行应用程序事件循环
        exit_code = app.exec_()

        # 程序退出时生成批处理文件
        generate_batch_on_exit()

        sys.exit(exit_code)
        
    except Exception as e:
        # 错误处理
        print(f"程序运行出错: {e}")
        if 'app' in locals():
            QMessageBox.critical(None, "错误", f"程序运行出错:\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()