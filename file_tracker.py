#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件追踪器 - 管理本次运行生成的文件列表
替代原来的全局变量设计

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""
import os
from typing import List


class FileTracker:
    """文件追踪器类 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._files: List[str] = []
        self._initialized = True

    def add(self, file_path: str) -> bool:
        """
        添加生成的文件到追踪列表

        Args:
            file_path: 文件绝对路径

        Returns:
            bool: 是否成功添加
        """
        if not file_path:
            return False

        if not os.path.exists(file_path):
            print(f"警告: 文件不存在，无法添加到追踪列表: {file_path}")
            return False

        if not file_path.endswith('.py'):
            print(f"警告: 仅支持追踪.py文件: {file_path}")
            return False

        if file_path not in self._files:
            self._files.append(file_path)
            print(f"已添加到追踪列表: {os.path.basename(file_path)}")
            return True

        return False

    def get_all(self) -> List[str]:
        """
        获取所有追踪的文件

        Returns:
            List[str]: 文件路径列表的副本
        """
        return self._files.copy()

    def get_existing(self) -> List[str]:
        """
        获取所有仍然存在的文件

        Returns:
            List[str]: 存在的文件路径列表
        """
        return [f for f in self._files if os.path.exists(f)]

    def clear(self):
        """清空追踪列表"""
        self._files.clear()

    def count(self) -> int:
        """获取追踪文件数量"""
        return len(self._files)

    def remove(self, file_path: str) -> bool:
        """
        从追踪列表中移除文件

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否成功移除
        """
        if file_path in self._files:
            self._files.remove(file_path)
            print(f"已从追踪列表移除: {os.path.basename(file_path)}")
            return True
        return False

    def __len__(self) -> int:
        """支持 len() 函数"""
        return len(self._files)

    def __repr__(self) -> str:
        return f"FileTracker(files={len(self._files)})"


# 创建全局单例实例
file_tracker = FileTracker()
