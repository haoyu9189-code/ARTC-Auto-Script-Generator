#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 集中管理所有硬编码的配置参数

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""
import os


class Config:
    """应用配置类"""

    # ========== 文件和路径配置 ==========
    FEATURE_FILE_MIN_SIZE = int(os.getenv('MIN_FILE_SIZE', 2000))  # 特征文件最小大小(字节)
    GENERATE_SCRIPT_DIR = "generate_script"  # 生成脚本的目录名
    LOG_DIR = os.getenv('LOG_DIR', "logs")  # PBS/SLURM 日志文件目录

    BASE_SCRIPT_PATH = os.getenv('BASE_SCRIPT_PATH', "/home/haoyu.wang/ARTC_Database_final/generate_script")  # 集群上脚本基础路径

    # ========== 集群调度系统类型 ==========
    SCHEDULER_TYPE = os.getenv('SCHEDULER_TYPE', "PBS")  # 调度系统类型: PBS 或 SLURM

    # ========== PBS 集群配置 ==========
    PBS_QUEUE = os.getenv('PBS_QUEUE', "qintel_wfly")  # PBS队列名
    PBS_PROJECT = os.getenv('PBS_PROJECT', "as_mae_kzhou")  # PBS项目名称
    PBS_NODES = int(os.getenv('PBS_NODES', 1))  # 节点数
    PBS_NCPUS = int(os.getenv('PBS_NCPUS', 8))  # CPU核心数
    PBS_MEMORY = os.getenv('PBS_MEM', "16gb")  # 内存大小 (优化: 从64gb降至16gb，基于实际使用2-2.5GB)
    PBS_WALLTIME = os.getenv('PBS_WALLTIME', "168:00:00")  # 作业时间限制（批量）
    PBS_PER_JOB_WALLTIME = os.getenv('PBS_PER_JOB_WALLTIME', "24:00:00")  # 单任务时间限制
    PBS_PER_JOB_MEMORY = os.getenv('PBS_PER_JOB_MEM', "8gb")  # 单任务内存
    PBS_JOIN_OE = os.getenv('PBS_JOIN_OE', "oe")  # 合并输出和错误日志 (oe=合并, n=分离)

    # ========== SLURM 集群配置 ==========
    SLURM_TIME_LIMIT = os.getenv('SLURM_TIME', "72:00:00")  # 作业时间限制
    SLURM_PARTITION = os.getenv('SLURM_PARTITION', "default")  # 分区名
    SLURM_NODES = int(os.getenv('SLURM_NODES', 1))  # 节点数
    SLURM_NTASKS = int(os.getenv('SLURM_NTASKS', 1))  # 任务数
    SLURM_CPUS_PER_TASK = int(os.getenv('SLURM_CPUS', 8))  # 每个任务的CPU数
    SLURM_MEMORY = os.getenv('SLURM_MEM', "64G")  # 内存大小

    # ========== Abaqus 配置 ==========
    ABAQUS_MODULE = os.getenv('ABAQUS_MODULE', "abaqus/2023u4")  # Abaqus模块名（含版本号）
    ABAQUS_COMMAND = os.getenv('ABAQUS_CMD', "abaqus cae noGUI")  # Abaqus执行命令

    # ========== 脚本生成配置 ==========
    BASE_CELL_SIZE = float(os.getenv('BASE_CELL_SIZE', 5.0))  # 基础晶胞尺寸
    DEFAULT_SLIDER_VALUE = int(os.getenv('DEFAULT_SLIDER', 4))  # 默认滑块值
    SLIDER_RANGE = (0, 9)  # 滑块范围

    # ========== 球径比配置（节点球半径 = 杆半径 × ratio） ==========
    # 预览和 STL 导出: 1.0 → 球与杆等径，外观干净
    # Abaqus 脚本生成: 1.0 → 节点不再过厚，保留塑性铰/旋转机制
    #   注：1.2 会过度刚化节点，废掉 Auxetic / Re-entrant 等铰链主导拓扑
    #   的负泊松机制，使仿真曲线变成"持续硬化"而非"yield-plateau"。
    SPHERE_RADIUS_RATIO_PREVIEW = float(os.getenv('SPHERE_RATIO_PREVIEW', 1.0))
    SPHERE_RADIUS_RATIO_SCRIPT = float(os.getenv('SPHERE_RATIO_SCRIPT', 1.0))

    # ========== 数据处理配置 ==========
    INTERPOLATION_POINTS = int(os.getenv('INTERP_POINTS', 100))  # 插值点数
    MIN_DATA_FILE_SIZE = int(os.getenv('MIN_DATA_SIZE', 1000))  # 最小数据文件大小

    # ========== UI 配置 ==========
    VISUALIZATION_UPDATE_INTERVAL = int(os.getenv('VIS_UPDATE_MS', 1000))  # 可视化更新间隔(毫秒)
    FORCE_REFRESH_DELAY = int(os.getenv('REFRESH_DELAY_MS', 1000))  # 强制刷新延迟(毫秒)

    # ========== 日志配置 ==========
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')  # 日志级别
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')  # 日志文件

    # ========== 无slider功能的cell types ==========
    NO_SLIDER_CELL_TYPES = ["Cubic", "Octahedron"]

    # ========== Cell Type 分组 ==========
    CELL_TYPE_GROUPS = [
        ("Group 1", ["Cubic", "BCC", "BCCZ", "Octet_truss", "AFCC", "Truncated_cube", "FCC",
                     "FCCZ", "Tetrahedron_base", "Iso_truss", "G7", "FBCCZ", "FBCCXYZ",
                     "Cuboctahedron_Z", "Diamond", "Rhombic", "Kelvin", "Auxetic",
                     "Octahedron", "Truncated_Octoctahedron", "CubicRosette", "CBCC",
                     "WeairePhelan", "DiamondPlus"])
    ]

    @classmethod
    def get_pbs_header(cls):
        """获取PBS作业头部配置"""
        return {
            'queue': cls.PBS_QUEUE,
            'project': cls.PBS_PROJECT,
            'nodes': cls.PBS_NODES,
            'ncpus': cls.PBS_NCPUS,
            'memory': cls.PBS_MEMORY,
            'walltime': cls.PBS_WALLTIME,
            'join_oe': cls.PBS_JOIN_OE
        }

    @classmethod
    def get_slurm_header(cls):
        """获取SLURM作业头部配置"""
        return {
            'time': cls.SLURM_TIME_LIMIT,
            'partition': cls.SLURM_PARTITION,
            'nodes': cls.SLURM_NODES,
            'ntasks': cls.SLURM_NTASKS,
            'cpus_per_task': cls.SLURM_CPUS_PER_TASK,
            'memory': cls.SLURM_MEMORY
        }

    @classmethod
    def validate(cls):
        """验证配置参数"""
        assert cls.FEATURE_FILE_MIN_SIZE > 0, "FEATURE_FILE_MIN_SIZE must be positive"
        assert cls.BASE_CELL_SIZE > 0, "BASE_CELL_SIZE must be positive"

        if cls.SCHEDULER_TYPE == "PBS":
            assert cls.PBS_NODES > 0, "PBS_NODES must be positive"
            assert cls.PBS_NCPUS > 0, "PBS_NCPUS must be positive"
        elif cls.SCHEDULER_TYPE == "SLURM":
            assert cls.SLURM_NODES > 0, "SLURM_NODES must be positive"
            assert cls.SLURM_CPUS_PER_TASK > 0, "SLURM_CPUS_PER_TASK must be positive"

        return True


# 在导入时验证配置
Config.validate()
