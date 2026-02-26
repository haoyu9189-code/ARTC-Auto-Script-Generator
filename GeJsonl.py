#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据收集与清理模块
收集feature_data.txt数据，处理插值并输出JSON格式

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import os
import json
import glob
import re
from pathlib import Path
try:
    import numpy as np
    from scipy.interpolate import interp1d, CubicSpline, UnivariateSpline
    SCIPY_AVAILABLE = True
except ImportError:
    try:
        import numpy as np
        SCIPY_AVAILABLE = False
        print("警告: scipy未安装，将使用线性插值替代样条插值")
    except ImportError:
        print("警告: numpy未安装，插值功能将不可用")
        SCIPY_AVAILABLE = False

# 参数设置
A = 50
B = 10 * A  # B = 50

def advanced_interpolation(displacement, force, target_points=B, method='cubic_spline',
                          noise_threshold=0.15):
    """
    高级插值函数，支持多种插值方法，并可以过滤噪声点

    Args:
        displacement: 原始位移数据
        force: 原始力数据
        target_points: 目标插值点数，默认100
        method: 插值方法 ('linear', 'cubic', 'cubic_spline', 'smooth_spline')
        noise_threshold: 噪声阈值，默认0.15（相对变化率大于15%视为噪声）

    Returns:
        tuple: (插值后的位移, 插值后的力, 插值信息)
    """

    if len(displacement) < 2 or len(force) < 2:
        return displacement, force, "数据点不足，无法插值"

    # 转换为numpy数组
    x_original = np.array(displacement)
    y_original = np.array(force)

    # 处理X值连续相同的情况：保留Y变化最小的点
    x_clean = []
    y_clean = []
    i = 0
    removed_duplicate_x = 0

    while i < len(displacement):
        current_x = displacement[i]
        current_y = force[i]

        # 查找所有X值相同的点
        j = i + 1
        same_x_indices = [i]
        while j < len(displacement) and abs(displacement[j] - current_x) < 1e-10:
            same_x_indices.append(j)
            j += 1

        # 如果有多个X值相同的点
        if len(same_x_indices) > 1:
            # 计算所有Y值的均值
            y_values = [force[idx] for idx in same_x_indices]
            y_mean = sum(y_values) / len(y_values)

            # 找到距离均值最近的点（Y变化最小）
            min_diff = float('inf')
            best_idx = same_x_indices[0]
            for idx in same_x_indices:
                diff = abs(force[idx] - y_mean)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = idx

            # 只保留最稳定的点
            x_clean.append(displacement[best_idx])
            y_clean.append(force[best_idx])
            removed_duplicate_x += len(same_x_indices) - 1
        else:
            # 只有一个点，直接保留
            x_clean.append(current_x)
            y_clean.append(current_y)

        i = j

    if removed_duplicate_x > 0:
        print(f"  已移除 {removed_duplicate_x} 个X值重复的不稳定点")

    # 不进行收敛检测，保留所有清洗后的数据
    x_final = x_clean
    y_final = y_clean

    info = f"处理后数据: {len(displacement)} -> {len(x_final)} 点"
    return x_final, y_final, info

def smart_target_points(original_length, target=B):
    """
    智能确定目标插值点数 - 统一到100个点

    Args:
        original_length: 原始数据点数
        target: 目标点数 (默认100)

    Returns:
        int: 实际使用的插值点数
    """

    # 统一处理：无论原始点数多少，都处理到100个点
    if original_length < 2:
        return original_length  # 数据点太少，无法处理
    else:
        return target  # 统一到100个点

def parse_sample_name_for_sorting(sample_name):
    """
    解析样本名称以提取排序关键字

    样本名称格式: {结构名}_{size}_{ratio}_{slider}
    例如: BCC_5_0.5_5, Auxetic_5_0.3_8, FCCZ_4_0p5_4 (0p5表示0.5)

    Args:
        sample_name: 样本名称字符串

    Returns:
        tuple: (structure, size, ratio, slider) 用于排序
               如果解析失败，返回 (sample_name, float('inf'), float('inf'), float('inf'))
    """

    try:
        # 使用正则表达式解析样本名称
        # 匹配格式: 结构名_数字_小数_数字
        # 支持 0.5 和 0p5 两种格式
        pattern = r'^([A-Za-z_]+)_(\d+)_(\d*[p\.]?\d+)_(\d+)$'
        match = re.match(pattern, sample_name.strip())

        if match:
            structure = match.group(1)  # 结构名 (如 BCC, FCC, Auxetic)
            size = int(match.group(2))  # 尺寸 (如 5)
            ratio_str = match.group(3).replace('p', '.')  # 比例 (如 0.5, 0.3)，将 p 替换为 .
            ratio = float(ratio_str)
            slider = int(match.group(4))  # 滑块值 (如 0-8)

            return (structure, size, ratio, slider)
        else:
            # 如果格式不匹配，尝试更宽松的模式
            parts = sample_name.split('_')
            if len(parts) >= 4:
                try:
                    structure = parts[0]
                    size = int(parts[1])
                    ratio_str = parts[2].replace('p', '.')  # 将 p 替换为 .
                    ratio = float(ratio_str)
                    slider = int(parts[3])
                    return (structure, size, ratio, slider)
                except (ValueError, IndexError):
                    pass

            # 解析失败，返回默认值使其排在最后
            print(f"警告: 无法解析样本名称格式 '{sample_name}'，将排在最后")
            return (sample_name, float('inf'), float('inf'), float('inf'))

    except Exception as e:
        print(f"解析样本名称 '{sample_name}' 时出错: {str(e)}")
        return (sample_name, float('inf'), float('inf'), float('inf'))

def calculate_sea(displacement, force, volume):
    """
    计算SEA (Specific Energy Absorption)

    Args:
        displacement: 位移数据列表
        force: 力数据列表
        volume: 结构体积

    Returns:
        float: SEA值
    """
    if len(displacement) < 2 or len(force) < 2:
        return None

    try:
        # 找到峰值点
        peak_force = max(force)
        peak_index = force.index(peak_force)

        # 从峰值后找到谷值点（局部最小值）
        valley_index = peak_index
        if peak_index < len(force) - 1:
            # 在峰值后寻找谷值
            for i in range(peak_index + 1, len(force) - 1):
                # 找到一个局部最小值点（前后都比它大）
                if (force[i] <= force[i-1] and force[i] <= force[i+1]):
                    valley_index = i
                    break
            # 如果没找到局部最小值，使用峰值后的最小值点
            if valley_index == peak_index:
                min_force_after_peak = min(force[peak_index+1:])
                valley_index = force.index(min_force_after_peak, peak_index+1)

        # 截取从零到谷值的数据
        disp_to_valley = displacement[:valley_index+1]
        force_to_valley = force[:valley_index+1]

        # 使用梯形法则计算积分 (Total_Energy_Absorbed)
        total_energy_absorbed = 0.0
        for i in range(len(disp_to_valley)-1):
            # 梯形面积 = (f1 + f2) * (x2 - x1) / 2
            area = (force_to_valley[i] + force_to_valley[i+1]) * (disp_to_valley[i+1] - disp_to_valley[i]) / 2.0
            total_energy_absorbed += area

        # Structure_Mass = volume
        structure_mass = volume

        # SEA = Total_Energy_Absorbed / Structure_Mass
        sea_value = total_energy_absorbed / structure_mass
        return sea_value
    except Exception as e:
        print(f"计算SEA时出错: {str(e)}")
        return None

def sort_samples_by_hierarchy(sample_file_map):
    """
    根据层级规则对样本进行排序

    排序优先级:
    1. 结构名 (字母顺序)
    2. Size (数值大小)
    3. Ratio (数值大小)
    4. Slider (数值大小)

    Args:
        sample_file_map: 字典 {sample_name: (file_path, file_size)}

    Returns:
        list: 排序后的 [(sample_name, file_path, file_size), ...] 列表
    """

    # 创建包含排序关键字的列表
    items_with_keys = []
    for sample_name, (file_path, file_size) in sample_file_map.items():
        sort_key = parse_sample_name_for_sorting(sample_name)
        items_with_keys.append((sort_key, sample_name, file_path, file_size))

    # 按排序关键字排序
    # sort_key = (structure, size, ratio, slider)
    items_with_keys.sort(key=lambda x: x[0])

    # 返回排序后的样本列表，格式: [(sample_name, file_path, file_size), ...]
    sorted_samples = [(item[1], item[2], item[3]) for item in items_with_keys]

    return sorted_samples

# SEA计算函数已移除，在其他模块中实现

def parse_feature_data_advanced(content):
    """
    改进的feature_data解析函数
    """
    lines = content.strip().split('\n')

    # 提取样本名称（第一行）
    sample_name = lines[0].strip() if lines else ""

    # 提取强度、密度、SEA和体积（支持更多格式）
    strength = None
    density = None
    sea = None
    volume = None

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # 匹配强度（支持多种格式）
        strength_patterns = [
            r'strength[:\s]*([\d.e+-]+)',
            r'强度[:\s]*([\d.e+-]+)',
            r'stress[:\s]*([\d.e+-]+)'
        ]

        for pattern in strength_patterns:
            match = re.search(pattern, line_lower, re.IGNORECASE)
            if match and strength is None:
                try:
                    strength = float(match.group(1))
                    break
                except ValueError:
                    continue

        # 匹配SEA（支持多种格式）
        sea_patterns = [
            r'sea[:\s]*([\d.e+-]+)',
            r'specific energy absorption[:\s]*([\d.e+-]+)'
        ]

        for pattern in sea_patterns:
            match = re.search(pattern, line_lower, re.IGNORECASE)
            if match and sea is None:
                try:
                    sea = float(match.group(1))
                    break
                except ValueError:
                    continue

        # 匹配密度（支持多种格式）
        density_patterns = [
            r'density[:\s]*([\d.e+-]+)',
            r'密度[:\s]*([\d.e+-]+)',
            r'ρ[:\s]*([\d.e+-]+)'
        ]

        for pattern in density_patterns:
            match = re.search(pattern, line_lower, re.IGNORECASE)
            if match and density is None:
                try:
                    density = float(match.group(1))
                    break
                except ValueError:
                    continue

        # 匹配体积（支持多种格式）
        volume_patterns = [
            r'volume[:\s]*([\d.e+-]+)',
            r'体积[:\s]*([\d.e+-]+)'
        ]

        for pattern in volume_patterns:
            match = re.search(pattern, line_lower, re.IGNORECASE)
            if match and volume is None:
                try:
                    volume = float(match.group(1))
                    break
                except ValueError:
                    continue

    # 查找F_D curve数据（支持更多格式）
    fd_start_idx = None
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ["f_d curve", "force-displacement", "力-位移"]):
            fd_start_idx = i
            break

    displacement = []
    force = []

    # 如果找到了 "F_D curve" 标记
    if fd_start_idx is not None:
        data_started = False
        for line in lines[fd_start_idx + 1:]:
            line = line.strip()
            if not line:
                continue

            # 跳过表头行
            if any(keyword in line.lower() for keyword in ["x", "displacement", "force", "位移", "力"]):
                data_started = True
                continue

            if data_started and line:
                # 更robust的数据行匹配
                # 支持多种分隔符：空格、制表符、逗号
                parts = re.split(r'[,\s\t]+', line)
                if len(parts) >= 2:
                    try:
                        disp_val = float(parts[0])
                        force_val = float(parts[1])
                        displacement.append(disp_val)
                        force.append(force_val)
                    except ValueError:
                        continue
    else:
        # 如果没有找到 "F_D curve" 标记，直接查找数据表头
        # 查找包含 "X" 或 "_temp" 的表头行
        data_started = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 检测表头行：包含 "X" 和其他列名（如 _temp_3）
            if not data_started:
                if "X" in line and ("temp" in line.lower() or "force" in line.lower()):
                    data_started = True
                    continue

            # 开始解析数据行
            if data_started:
                parts = re.split(r'[,\s\t]+', line_stripped)
                if len(parts) >= 2:
                    try:
                        disp_val = float(parts[0])
                        force_val = float(parts[1])
                        displacement.append(disp_val)
                        force.append(force_val)
                    except ValueError:
                        continue

    return {
        "sample_name": sample_name,
        "strength": strength,
        "sea": sea,
        "density": density,
        "volume": volume,
        "displacement": displacement,
        "force": force
    }

def extract_sample_name_from_path(file_path, root_path):
    """
    从文件路径中提取样本名称

    路径格式: root/BCC/4/0p4/0/static/feature_data.txt
    提取为: BCC_4_0p4_0

    Args:
        file_path: feature_data.txt的路径
        root_path: 根目录路径

    Returns:
        str: 样本名称
    """
    try:
        # 获取相对路径
        rel_path = file_path.relative_to(root_path)
        # 获取路径部分 (去掉最后的文件名和curve类型目录)
        # 例如: BCC/4/0p4/0/static/feature_data.txt -> BCC/4/0p4/0
        parts = rel_path.parts[:-2]  # 去掉 'static' 和 'feature_data.txt'
        # 组合为样本名称: BCC_4_0p4_0
        sample_name = '_'.join(parts)
        return sample_name
    except Exception as e:
        print(f"提取样本名称失败: {file_path}, 错误: {str(e)}")
        return None

def _get_expected_multipliers(radius):
    """根据 radius 计算期望的两个 multiplier 值"""
    try:
        radius_float = float(str(radius).replace('p', '.'))
    except (ValueError, TypeError):
        return None, None
    multiplier1 = round(0.4 + (radius_float - 0.3) * 2.0, 1)
    multiplier2 = round(multiplier1 + 0.3, 1)
    return multiplier1, multiplier2

def _extract_radius_from_path(file_path):
    """从文件路径中提取 radius 值
    路径格式: root/CellType/Size/Radius/Slider/CurveType/feature_data.txt
    """
    try:
        parts = file_path.parts
        # 从后往前找: feature_data.txt(-1), CurveType(-2), Slider(-3), Radius(-4)
        if len(parts) >= 4:
            radius_str = parts[-4]
            return radius_str
    except Exception:
        pass
    return None

def identify_curve_type(file_path):
    """
    识别曲线类型 - 支持所有静态和动态模式（包括Auto模式的不同变体）
    将旧的multiplier命名(0p4, 0p7等)统一转换为a/b命名

    Args:
        file_path: feature_data.txt的路径

    Returns:
        str: 曲线类型，格式为 '{分析类型}_curve'
             静态: 'StaCompre_curve', 'StaShear_curve'
             动态Auto模式: 'DynaCompre_Auto_a_curve', 'DynaCompre_Auto_b_curve', 等
             如果无法识别返回 None
    """
    # 获取包含feature_data.txt的目录名
    parent_dir = file_path.parent.name

    # 静态模式 - 固定映射
    static_map = {
        'StaCompre': 'StaCompre_curve',
        'StaShear': 'StaShear_curve',
        'StaShare': 'StaShear_curve',  # 旧命名兼容
    }

    # 检查静态模式（精确匹配，不带后缀）
    if parent_dir in static_map:
        return static_map[parent_dir]

    # 动态模式处理
    # 标准化命名：Share -> Shear
    normalized = parent_dir.replace('DynaShare', 'DynaShear')

    # 检查是否为 Auto 模式
    if '_Auto_' in normalized:
        # 提取基础类型和后缀 (如 DynaCompre_Auto_0p4 -> DynaCompre_Auto, 0p4)
        parts = normalized.rsplit('_', 1)
        if len(parts) == 2:
            base_type = parts[0]  # DynaCompre_Auto 或 DynaShear_Auto
            suffix = parts[1]     # 0p4, 0p7, a, b 等

            # 如果已经是 a/b 命名，直接返回
            if suffix in ['a', 'b']:
                return f"{normalized}_curve"

            # 否则需要转换 multiplier 到 a/b
            # 从路径中提取 radius
            radius_str = _extract_radius_from_path(file_path)
            if radius_str:
                mult1, mult2 = _get_expected_multipliers(radius_str)
                if mult1 is not None and mult2 is not None:
                    # 将后缀转换为数值进行比较
                    try:
                        suffix_value = float(suffix.replace('p', '.'))
                        # 比较并映射到 a/b
                        if abs(suffix_value - mult1) < 0.05:
                            return f"{base_type}_a_curve"
                        elif abs(suffix_value - mult2) < 0.05:
                            return f"{base_type}_b_curve"
                    except ValueError:
                        pass

            # 如果无法转换，返回原始命名
            return f"{normalized}_curve"

    # 非 Auto 动态模式 (如 DynaCompre_500)
    dynamic_prefixes = ['DynaCompre', 'DynaShear']
    for prefix in dynamic_prefixes:
        if normalized.startswith(prefix):
            return f"{normalized}_curve"

    return None

def collect_feature_data_to_json_advanced(root_folder, output_file="feature_data.json",
                                        encoding='utf-8', target_points=B,
                                        interpolation_method='cubic_spline',
                                        collection_mode=1,
                                        update_mode='full'):
    """
    新版本的feature_data收集函数
    将同一样本的所有曲线类型整合到一起（支持静态、动态固定速度、动态Auto模式）

    Args:
        root_folder: 根文件夹路径
        output_file: 输出JSON文件名
        encoding: 文件编码
        target_points: 目标插值点数
        interpolation_method: 插值方法
        collection_mode: 采集模式
            - 1: 仅静态 (StaCompre, StaShear)
            - 2: 全部（静态 + 动态Auto所有变体）
        update_mode: 更新模式
            - 'full': 全量更新，重新处理所有样本
            - 'incremental': 增量更新，只处理新样本
            - 'overwrite': 覆盖更新，自动扫描源文件夹并覆盖更新已存在的样本
    """

    result = {}
    root_path = Path(root_folder)

    # 非全量模式：加载现有数据
    existing_samples = set()
    if update_mode in ['incremental', 'overwrite'] and os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                existing_samples = set(result.keys())
                print(f"{update_mode}模式: 已加载现有数据，包含 {len(existing_samples)} 个样本")
        except Exception as e:
            print(f"警告: 无法加载现有JSON文件: {e}，将创建新文件")
            result = {}

    # 查找所有feature_data.txt文件
    all_feature_files = list(root_path.rglob("feature_data.txt"))
    print(f"找到 {len(all_feature_files)} 个feature_data.txt文件")

    # 按样本分组，同时收集所有发现的曲线类型
    sample_curve_map = {}  # {sample_name: {curve_type: file_path}}
    all_discovered_curve_types = set()  # 收集所有发现的曲线类型

    print("正在扫描文件并按样本分组...")
    for feature_file in all_feature_files:
        try:
            # 提取样本名称
            sample_name = extract_sample_name_from_path(feature_file, root_path)
            if not sample_name:
                continue

            # 识别曲线类型
            curve_type = identify_curve_type(feature_file)
            if not curve_type:
                print(f"无法识别曲线类型: {feature_file.relative_to(root_path)}")
                continue

            # 记录发现的曲线类型
            all_discovered_curve_types.add(curve_type)

            # 添加到分组
            if sample_name not in sample_curve_map:
                sample_curve_map[sample_name] = {}

            sample_curve_map[sample_name][curve_type] = feature_file

        except Exception as e:
            print(f"扫描文件 {feature_file} 时出错: {str(e)}")

    print(f"扫描完成，发现 {len(sample_curve_map)} 个唯一样本")
    print(f"发现的曲线类型: {sorted(all_discovered_curve_types)}")

    # 根据更新模式过滤样本
    if update_mode == 'incremental' and existing_samples:
        # 增量模式：只处理新样本
        new_samples = set(sample_curve_map.keys()) - existing_samples
        skipped_count = len(sample_curve_map) - len(new_samples)
        sample_curve_map = {k: v for k, v in sample_curve_map.items() if k in new_samples}
        print(f"增量模式: 跳过 {skipped_count} 个已存在样本，待处理 {len(sample_curve_map)} 个新样本")
    elif update_mode == 'overwrite':
        # 覆盖模式：自动扫描源文件夹中存在的样本并覆盖更新
        # 不需要过滤，直接处理所有扫描到的样本
        print(f"覆盖模式: 将覆盖更新 {len(sample_curve_map)} 个扫描到的样本")

    print("-" * 50)

    # 对样本进行排序
    print("正在对样本进行排序...")
    sorted_sample_names = sorted(sample_curve_map.keys(),
                                 key=lambda x: parse_sample_name_for_sorting(x))
    print(f"排序完成，共 {len(sorted_sample_names)} 个样本")

    # 显示排序后的前几个样本
    if sorted_sample_names:
        print("排序后的前几个样本:")
        for i, sample_name in enumerate(sorted_sample_names[:5]):
            curves = list(sample_curve_map[sample_name].keys())
            print(f"  {i+1}. {sample_name} (包含 {len(curves)} 种曲线: {', '.join(curves)})")
        if len(sorted_sample_names) > 5:
            print(f"  ... 还有 {len(sorted_sample_names) - 5} 个样本")
    print("-" * 50)

    # 根据采集模式确定要处理的曲线类型
    static_curves = ['StaCompre_curve', 'StaShear_curve']
    # Auto曲线从发现的类型中筛选
    dynamic_auto_curves = sorted([ct for ct in all_discovered_curve_types
                                   if 'Auto' in ct and ct not in static_curves])

    if collection_mode == 1:
        # 模式1: 仅静态
        target_curve_types = static_curves
        print(f"\n采集模式1: 仅静态曲线 ({len(target_curve_types)} 种)")
    else:
        # 模式2: 全部（静态 + 动态Auto所有变体）
        target_curve_types = static_curves + dynamic_auto_curves
        print(f"\n采集模式2: 全部曲线类型 ({len(target_curve_types)} 种)")
        if dynamic_auto_curves:
            print(f"  发现的Auto变体: {dynamic_auto_curves}")

    # 处理每个样本
    print("\n开始处理样本数据...")
    for sample_name in sorted_sample_names:
        try:
            curve_files = sample_curve_map[sample_name]
            # 覆盖模式：从现有数据开始，只更新有新数据的曲线
            if update_mode == 'overwrite' and sample_name in result:
                sample_data = result[sample_name].copy()
                density_value = sample_data.get("density")
            else:
                sample_data = {}
                density_value = None

            # 使用根据采集模式确定的曲线类型
            curve_types = target_curve_types

            # 旧key名到新key名的映射（用于向后兼容）
            old_to_new_key_map = {
                'StaShare_curve': 'StaShear_curve',
                'DynaShare_Auto_curve': 'DynaShear_Auto_curve',
                'DynaShare_500_curve': 'DynaShear_500_curve'
            }
            # 迁移现有数据中的旧key到新key
            for old_key, new_key in old_to_new_key_map.items():
                if old_key in sample_data and new_key not in sample_data:
                    sample_data[new_key] = sample_data.pop(old_key)

            # 处理每种曲线类型
            # 对于该样本，处理目标曲线类型中存在的，以及样本自身拥有的曲线
            sample_curve_types_to_process = set(curve_types) | set(curve_files.keys())

            for curve_type in sorted(sample_curve_types_to_process):
                if curve_type in curve_files:
                    feature_file = curve_files[curve_type]

                    # 读取并解析文件
                    content = feature_file.read_text(encoding=encoding, errors='ignore')
                    parsed_data = parse_feature_data_advanced(content)

                    displacement = parsed_data["displacement"]
                    force = parsed_data["force"]

                    # 保存第一个文件的density
                    if density_value is None:
                        # 先检查同路径下是否有 density_temp.txt
                        density_temp_file = feature_file.parent / "density_temp.txt"
                        if density_temp_file.exists():
                            try:
                                density_content = density_temp_file.read_text(encoding='utf-8', errors='ignore').strip()
                                density_value = float(density_content)
                            except (ValueError, Exception) as e:
                                print(f"读取 {density_temp_file} 失败: {e}，使用原始逻辑")
                                if parsed_data["density"] is not None:
                                    density_value = parsed_data["density"]
                        elif parsed_data["density"] is not None:
                            density_value = parsed_data["density"]

                    # 处理X值重复的情况
                    if len(displacement) > 1:
                        disp_interp, force_interp, process_info = advanced_interpolation(
                            displacement, force, target_points, interpolation_method
                        )
                        print(f"{sample_name} - {curve_type}: {process_info}")
                    else:
                        disp_interp, force_interp = displacement, force
                        print(f"{sample_name} - {curve_type}: {len(displacement)} 点（数据不足）")

                    # 添加曲线数据
                    sample_data[curve_type] = {
                        "displacement": disp_interp,
                        "force": force_interp
                    }
                elif curve_type in curve_types:
                    # 仅对目标曲线类型报告缺失（Auto变体不强制要求）
                    # 覆盖模式：保留现有数据；其他模式：设为null
                    if update_mode == 'overwrite' and curve_type in sample_data:
                        print(f"{sample_name} - {curve_type}: 源文件缺失，保留现有数据")
                    elif curve_type in static_curves:
                        # 只对静态曲线类型设置null
                        sample_data[curve_type] = None
                        print(f"{sample_name} - {curve_type}: 缺失")

            # 添加density到样本数据
            sample_data["density"] = density_value

            # 保存到结果
            result[sample_name] = sample_data
            print(f"已完成: {sample_name}")
            print("-" * 30)

        except Exception as e:
            print(f"处理样本 {sample_name} 时出错: {str(e)}")

    # 保存为JSON文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # 自定义格式化以确保数组在同一行
            json_str = json.dumps(result, indent=2, ensure_ascii=False)
            # 将数组格式化为单行
            import re
            # 匹配displacement和force数组，使其在一行显示
            for field in ["displacement", "force"]:
                pattern = rf'("{field}":\s*\[)\s*\n\s*(.*?)\s*\n\s*(\])'
                json_str = re.sub(pattern,
                                lambda m: m.group(1) + ' ' + re.sub(r'\s*\n\s*', ', ', m.group(2).strip()) + ' ' + m.group(3),
                                json_str, flags=re.DOTALL)
            # 清理可能产生的双逗号
            json_str = re.sub(r',\s*,', ',', json_str)
            f.write(json_str)
        print(f"\n成功保存到: {output_file}")
        print(f"总共处理了 {len(result)} 个样本")

        # 输出统计信息
        if result:
            print(f"\n=== 处理统计 ===")
            print(f"总样本数: {len(result)}")

            # 动态收集所有曲线类型进行统计
            all_curve_types_in_result = set()
            for sample_data in result.values():
                for key in sample_data.keys():
                    if key.endswith('_curve'):
                        all_curve_types_in_result.add(key)

            # 统计每种曲线类型的数量
            curve_stats = {ct: 0 for ct in sorted(all_curve_types_in_result)}
            for sample_data in result.values():
                for curve_type in curve_stats.keys():
                    if sample_data.get(curve_type) is not None:
                        curve_stats[curve_type] += 1

            # 分类显示统计
            print("\n各曲线类型数量:")
            print("  [静态曲线]")
            for curve_type in ['StaCompre_curve', 'StaShear_curve']:
                if curve_type in curve_stats:
                    print(f"    {curve_type}: {curve_stats[curve_type]}")

            # Auto曲线
            auto_curves = sorted([ct for ct in curve_stats.keys() if 'Auto' in ct])
            if auto_curves:
                print("  [动态Auto曲线]")
                # 按类型分组显示
                compre_auto = [ct for ct in auto_curves if 'Compre' in ct]
                shear_auto = [ct for ct in auto_curves if 'Shear' in ct]

                if compre_auto:
                    print("    压缩(Compre):")
                    for curve_type in compre_auto:
                        print(f"      {curve_type}: {curve_stats[curve_type]}")
                if shear_auto:
                    print("    剪切(Shear):")
                    for curve_type in shear_auto:
                        print(f"      {curve_type}: {curve_stats[curve_type]}")

    except Exception as e:
        print(f"保存JSON文件时出错: {str(e)}")

# 简化调用函数
def optimize_interpolation(folder_path=".", output_file="feature_data.json",
                          target_points=B, method='cubic_spline', collection_mode=1,
                          update_mode='full'):
    """
    优化插值的简化调用函数

    Args:
        folder_path: 文件夹路径
        output_file: 输出文件名
        target_points: 目标点数
        method: 插值方法 ('linear', 'cubic', 'cubic_spline', 'smooth_spline')
        collection_mode: 采集模式
            - 1: 仅静态 (StaCompre, StaShear)
            - 2: 全部 (静态 + Auto所有变体)
        update_mode: 更新模式 ('full'=全量, 'incremental'=增量, 'overwrite'=覆盖更新)
    """
    collect_feature_data_to_json_advanced(
        folder_path,
        output_file,
        target_points=target_points,
        interpolation_method=method,
        collection_mode=collection_mode,
        update_mode=update_mode
    )

# 使用示例
if __name__ == "__main__":
    print("=== 数据收集与清理器 ===")
    print("功能: 收集所有feature_data.txt中的数据")
    print("处理: 当X值连续相同时，保留Y值最接近均值的点")
    print("=" * 50)

    # 用户选择采集模式
    print("\n请选择数据采集模式:")
    print("1. 仅采集静态数据 (StaCompre, StaShear)")
    print("2. 采集全部数据 (静态 + 动态Auto所有变体)")

    while True:
        try:
            choice = input("\n请输入选择 (1 或 2): ").strip()
            if choice in ['1', '2']:
                collection_mode = int(choice)
                break
            else:
                print("无效输入，请输入 1 或 2")
        except Exception as e:
            print(f"输入错误: {e}，请重新输入")

    if collection_mode == 1:
        print("\n已选择: 仅采集静态数据 (StaCompre, StaShear)")
    else:
        print("\n已选择: 采集全部数据 (静态 + 动态Auto所有变体)")

    # 用户选择更新模式
    print("\n请选择更新模式:")
    print("1. 全量更新 (重新处理所有样本)")
    print("2. 增量更新 (只处理新样本，合并到现有数据)")
    print("3. 覆盖更新 (自动扫描源文件夹，覆盖更新已存在的样本)")

    while True:
        try:
            update_choice = input("\n请输入选择 (1, 2 或 3): ").strip()
            if update_choice in ['1', '2', '3']:
                break
            else:
                print("无效输入，请输入 1, 2 或 3")
        except Exception as e:
            print(f"输入错误: {e}，请重新输入")

    update_mode = 'full'

    if update_choice == '1':
        update_mode = 'full'
        print("\n已选择: 全量更新模式")
    elif update_choice == '2':
        update_mode = 'incremental'
        print("\n已选择: 增量更新模式")
    else:
        update_mode = 'overwrite'
        print("\n已选择: 覆盖更新模式 (自动扫描源文件夹中的样本)")

    folder_path = "generate_script"

    print(f"\n开始处理...")
    print(f"输入路径: {os.path.abspath(folder_path)}")
    print(f"处理方式: X值重复去重（保留Y值最稳定的点）")
    print("=" * 50)

    # 处理所有数据（新格式：6种曲线整合到一起）
    print("\n收集所有样本数据...")
    print("-" * 50)
    optimize_interpolation(folder_path, "work/feature_data.json", B, 'cubic_spline', collection_mode, update_mode)

    print("\n" + "=" * 50)
    print("\n✓ 全部完成！")
    print(f"  - 数据已保存到: work/feature_data.json")
    print(f"  - 已处理X值重复的数据点")
    mode_names = {'full': '全量更新', 'incremental': '增量更新', 'overwrite': '覆盖更新'}
    print(f"  - 更新模式: {mode_names.get(update_mode, update_mode)}")
    if collection_mode == 1:
        print(f"  - 采集范围: 仅静态 (StaCompre, StaShear)")
    else:
        print(f"  - 采集范围: 全部 (静态 + 动态Auto所有变体)")