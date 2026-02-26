#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abaqus Script Generator
根据UI参数生成定制化的Abaqus脚本

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import os
import sys
import re
import platform
import json
import numpy as np
from structure_set import get_crystal_structure


# from macro_integration import MacroIntegrator



class AbaqusScriptGenerator:
    def __init__(self):
        self.base_template_file_static = 'model/Static_model.py'
        self.base_template_file_dynamic = 'model/Dynamic_model.py'
        self.base_cell_size = 5.0  # 原始模板的单元尺寸
        # self.macro_integrator = MacroIntegrator()  # 宏集成器
        self._file_tracker_callback = None  # 文件追踪回调函数


    def set_file_tracker_callback(self, callback):
        """设置文件追踪回调函数"""
        self._file_tracker_callback = callback

    def _extract_velocity_from_analysis_type(self, analysis_type):
        """从 analysis_type 中提取速度值

        例如:
        - 'DynaCompre_500' -> '500'
        - 'DynaShear_500' -> '500'
        - 'StaCompre' -> None
        - 'StaShear' -> None
        """
        if analysis_type and '_' in analysis_type:
            return analysis_type.split('_')[1]
        return None

    # 特殊样本直接指定densified strain位置 (来自 qt_interface.py)
    SPECIAL_OVERRIDES = {
        'WeairePhelan_5_0p45_0': 0.4,
        'WeairePhelan_5_0p45_1': 0.35,
        'WeairePhelan_5_0p5_3': 0.48,
        'WeairePhelan_5_0p5_4': 0.44,
        'Octet_truss_5_0p5_6': 0.58,
        'FBCCXYZ_5_0p45_1': 0.58,
        'FBCCXYZ_5_0p45_2': 0.52,
        'FBCCXYZ_5_0p45_4': 0.45,
        'BCC_5_0p45_3': 0.61,
        'BCC_5_0p35_6': 0.66,
        'BCCZ_5_0p45_2': 0.62,
        'Octet_truss_5_0p5_3': 0.6,
        'Octet_truss_5_0p5_4': 0.58,
        'Octet_truss_5_0p5_5': 0.58,
        'Auxetic_5_0p5_2': 0.55,
        'Auxetic_5_0p5_3': 0.55,
    }

    def _get_static_energy_absorb(self, cell_type, cell_size, cell_radius, slider, mode_type):
        """从 feature_data.json 读取对应静态仿真的 Energy Absorb (EA) 值

        参数:
            cell_type: 结构类型 (如 'Cubic', 'BCC')
            cell_size: 单元尺寸 (如 5)
            cell_radius: 杆件半径 (如 0.5)
            slider: 滑块值 (0-8)
            mode_type: 模式类型 ('Compression' 或 'Shear')

        返回:
            EA 值 (mJ) 或 None (如果找不到数据)
        """
        try:
            # 构建 feature_data.json 路径
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))

            feature_data_path = os.path.join(base_dir, "work", "feature_data.json")

            if not os.path.exists(feature_data_path):
                print(f"Error: feature_data.json not found at {feature_data_path}")
                return None

            # 读取 JSON 数据
            with open(feature_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 构建结构键名: 如 "Cubic_5_0p5_4"
            # 处理 cell_size: 整数去掉小数点
            if float(cell_size).is_integer():
                size_str = str(int(float(cell_size)))
            else:
                size_str = str(cell_size).replace('.', 'p')

            # 处理 cell_radius: 小数点替换为 p
            radius_str = str(cell_radius).replace('.', 'p')

            # 处理 slider: 整数去掉小数点
            if float(slider) == int(float(slider)):
                slider_str = str(int(float(slider)))
            else:
                slider_str = str(slider).replace('.', 'p')

            structure_key = f"{cell_type}_{size_str}_{radius_str}_{slider_str}"

            print(f"Looking for structure key: {structure_key}")

            if structure_key not in data:
                print(f"Error: Structure '{structure_key}' not found in feature_data.json")
                return None

            # 确定曲线类型
            is_compression = (mode_type == "Compression")
            curve_key = "StaCompre_curve" if is_compression else "StaShare_curve"

            if curve_key not in data[structure_key]:
                print(f"Error: '{curve_key}' not found for structure '{structure_key}'")
                return None

            curve_data = data[structure_key][curve_key]
            displacement = np.array(curve_data['displacement'])
            force = np.array(curve_data['force'])

            # 计算应变和应力
            cell_size_float = float(cell_size)
            strain = displacement / cell_size_float
            stress = force / (cell_size_float ** 2)
            V0 = cell_size_float ** 3  # 体积

            # 检查是否为特殊样本，直接使用 override 位置
            if is_compression and structure_key in self.SPECIAL_OVERRIDES:
                target_strain = self.SPECIAL_OVERRIDES[structure_key]
                key_idx = int(np.argmin(np.abs(strain - target_strain)))
                E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
                EA = E_total * V0
                print(f"[SPECIAL_OVERRIDE] {structure_key}: target_strain={target_strain}, key_idx={key_idx}, EA={EA:.4f} mJ")
                return EA

            # 非特殊样本，使用 v10 算法计算密实化点
            key_idx = self._find_densification_point_v10(strain, stress, is_compression)

            # 计算能量吸收
            E_total = np.trapz(stress[:key_idx+1], strain[:key_idx+1])
            EA = E_total * V0  # mJ

            print(f"Calculated EA for {structure_key}: {EA:.4f} mJ (key_idx={key_idx}, key_strain={strain[key_idx]:.4f})")
            return EA

        except Exception as e:
            import traceback
            print(f"Error getting static energy absorb: {e}")
            traceback.print_exc()
            return None

    def _find_densification_point_v10(self, strain, stress, is_compression=True):
        """v10算法 - 找到密实化点（斜率开始急剧增加的位置）

        与 qt_interface.py 中的算法保持一致
        """
        from scipy.ndimage import uniform_filter1d

        if not is_compression:
            # 剪切曲线：直接取最后一个点
            return len(strain) - 1

        if len(strain) < 20:
            return len(strain) - 1

        n = len(strain)

        # 平滑应力
        smooth_window = 7
        stress_smooth = uniform_filter1d(stress, size=smooth_window)

        # 计算局部斜率
        window = 3
        slopes = np.zeros(n)
        for i in range(window, n - window):
            d_stress = stress_smooth[i + window] - stress_smooth[i - window]
            d_strain = strain[i + window] - strain[i - window]
            slopes[i] = d_stress / max(d_strain, 1e-6)

        # 平滑斜率
        slopes_smooth = uniform_filter1d(slopes, size=5)

        # 找峰值（用于确定搜索起点）
        stiffness_end = max(int(n * 0.1), 10)
        prominence_window = 50
        all_peaks = []

        for i in range(stiffness_end, n - window - 1):
            if slopes[i] > 0 and slopes[i + 1] <= 0:
                peak_h = stress_smooth[i]
                left_min = np.min(stress_smooth[max(0, i-prominence_window):i]) if i > 0 else peak_h
                if i >= n * 0.8:
                    prominence = peak_h - left_min
                else:
                    right_min = np.min(stress_smooth[i:min(len(stress_smooth), i+prominence_window)])
                    prominence = peak_h - max(left_min, right_min)
                min_prominence = max(peak_h * 0.05, 0.1)
                if prominence >= min_prominence:
                    all_peaks.append(i)

        # 末端斜率（80%-95%区域）
        end_start = int(n * 0.80)
        end_end = int(n * 0.95)
        end_slope_avg = np.mean(slopes_smooth[end_start:end_end]) if end_start < end_end else 0

        # 搜索起点：第一个峰值后或40%位置
        if all_peaks:
            search_start = max(all_peaks[0] + 5, int(n * 0.4))
        else:
            search_start = int(n * 0.4)

        search_end = int(n * 0.95)

        # 使用末端斜率的15%作为阈值
        threshold = end_slope_avg * 0.15

        # 从后向前搜索，找第一个斜率低于阈值的点
        key_idx = search_start
        for i in range(search_end, search_start, -1):
            if slopes_smooth[i] < threshold:
                key_idx = i + 1
                break
        else:
            # 备选：使用更低的阈值（10%）
            threshold = end_slope_avg * 0.10
            for i in range(search_end, search_start, -1):
                if slopes_smooth[i] < threshold:
                    key_idx = i + 1
                    break

        return key_idx

    def _calculate_velocity_for_auto_mode(self, ea_value, mass_gram=1.0, multiplier=0.8):
        """根据静态吸能计算冲击速度（固定质量模式）

        参数:
            ea_value: 静态吸能极限 (mJ)
            mass_gram: 刚板质量 (g), 默认 1.0 g
            multiplier: 动能倍数, 默认 2.0 (动能 = 2 × EA)

        返回:
            速度 (mm/s)

        ABAQUS 单位制 (mm, tonne, s):
            1 tonne = 1000 kg, 1 mm = 0.001 m

            KE = ½mv²
            单位换算: tonne × (mm/s)² = 1000 kg × (0.001 m/s)² = 1e-3 kg·m²/s² = 1e-3 J = 1 mJ

            所以: 1 tonne·mm²/s² = 1 mJ
            KE (mJ) = ½ × m (tonne) × v² (mm/s)²
            反推: v = sqrt(2 × KE / m)  mm/s
        """
        target_ke = multiplier * ea_value  # mJ
        mass_tonne = mass_gram / 1e6  # g -> tonne

        # v = sqrt(2 * KE(mJ) / m(tonne))  -- 不需要除以1000！
        velocity = np.sqrt(2.0 * target_ke / mass_tonne)  # mm/s

        # 验证: KE_check = 0.5 * m * v^2
        ke_check = 0.5 * mass_tonne * (velocity ** 2)

        print(f"Auto mode velocity calculation:")
        print(f"  EA = {ea_value:.4f} mJ")
        print(f"  Target KE = {target_ke:.4f} mJ ({multiplier}× EA)")
        print(f"  Fixed mass = {mass_gram} g = {mass_tonne:.6e} tonne")
        print(f"  Calculated velocity = {velocity:.2f} mm/s ({velocity/1000:.4f} m/s)")
        print(f"  Verification: KE = {ke_check:.4f} mJ (should equal Target KE)")

        return velocity

    def _replace_plate_mass(self, content, mass_value):
        """替换刚板质量参数"""
        # 替换 mass=xxx 为计算出的值
        pattern = r'mass=[\d.e+-]+(?=,\s*alpha)'
        replacement = f'mass={mass_value:.6e}'
        content = re.sub(pattern, replacement, content)
        print(f"Replaced plate mass to: {mass_value:.6e}")
        return content

    def _replace_time_period(self, content, time_period):
        """替换 timePeriod 参数"""
        # 替换 timePeriod=xxx 为计算出的值
        pattern = r'timePeriod=[\d.e+-]+'
        replacement = f'timePeriod={time_period:.6f}'
        content = re.sub(pattern, replacement, content)
        print(f"Replaced timePeriod to: {time_period:.6f} s")
        return content

    def _get_auto_multipliers(self, cell_radius):
        """根据 radius 返回两个 multiplier 值

        Radius  Multiplier1  Multiplier2
        0.3     0.4          0.7
        0.35    0.5          0.8
        0.4     0.6          0.9
        0.45    0.7          1.0
        0.5     0.8          1.1
        """
        radius_float = float(cell_radius)
        # 线性插值: multiplier1 = 0.4 + (radius - 0.3) * 2
        #          multiplier2 = multiplier1 + 0.3
        multiplier1 = 0.4 + (radius_float - 0.3) * 2.0
        multiplier2 = multiplier1 + 0.3
        return [round(multiplier1, 1), round(multiplier2, 1)]

    def generate_script(self, cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None):
        """
        生成定制化的Abaqus脚本

        参数:
        - cell_type: 晶体结构类型 (如 'BCC', 'FCC', 'FCCZ' 等)
        - cell_size: 单元尺寸 (如 3, 4, 5)
        - cell_radius: 杆件半径 (如 0.3, 0.4, 0.5)
        - slider: 滑块值 (0-8)，用于控制BCC/BCCZ结构中O原子的位置
        - output_dir: 输出目录
        - mode_type: 模式类型 ("Compression" 或 "Shear")
        - analysis_type: 分析类型 ("StaCompre", "DynaCompre_500", "StaShear", "DynaShear_500" 等)
        - batch_mode: 是否为批量模式
        - batch_parent_dir: 批量模式的父文件夹路径

        返回:
        - (success: bool, message: str, filename: str)
        """

        # 对于 Auto 模式，生成两个脚本（不同 multiplier）
        if analysis_type.endswith("_Auto"):
            multipliers = self._get_auto_multipliers(cell_radius)
            print(f"\n=== Auto Mode: Generating scripts with a/b naming (multipliers: {multipliers}) ===")

            all_success = True
            all_filenames = []

            # 使用 a/b 命名代替 multiplier 数值
            suffix_names = ['a', 'b']
            for idx, multiplier in enumerate(multipliers):
                # 设置当前 multiplier 供 _generate_script_content 使用
                self._auto_multiplier = multiplier

                # 修改 analysis_type 为带 a/b 后缀的版本，用于目录命名
                # 如 DynaCompre_Auto -> DynaCompre_Auto_a 或 DynaCompre_Auto_b
                suffix = suffix_names[idx] if idx < len(suffix_names) else f"x{idx}"
                modified_analysis_type = f"{analysis_type}_{suffix}"

                success, message, filename = self._generate_single_script(
                    cell_type, cell_size, cell_radius, slider, output_dir,
                    mode_type, modified_analysis_type, batch_mode, batch_parent_dir
                )

                if not success:
                    all_success = False
                    print(f"  Failed for {suffix} (multiplier={multiplier}): {message}")
                else:
                    all_filenames.append(filename)
                    print(f"  Success for {suffix} (multiplier={multiplier}): {filename}")

            # 清理临时变量
            if hasattr(self, '_auto_multiplier'):
                del self._auto_multiplier

            if all_success:
                return True, f"Auto模式脚本生成成功: {', '.join(all_filenames)}", all_filenames[0]
            else:
                return False, "部分脚本生成失败", ""

        # 非 Auto 模式，正常生成单个脚本
        return self._generate_single_script(
            cell_type, cell_size, cell_radius, slider, output_dir,
            mode_type, analysis_type, batch_mode, batch_parent_dir
        )

    def _generate_single_script(self, cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None):
        """生成单个脚本的内部实现"""
        try:
            # 统一的文件夹创建逻辑
            output_dir = self._create_output_directory(cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, batch_mode, batch_parent_dir, output_dir)

            # 设置当前结构名称，用于结构感知检测
            self._current_structure_name = cell_type

            # 1. 验证参数
            if not self._validate_parameters(cell_type, cell_size, cell_radius):
                return False, "参数验证失败", ""

            # 2. 读取基础模板
            template_content = self._read_template(mode_type, analysis_type)
            if not template_content:
                return False, "无法读取模板文件", ""

            # 3. 获取结构几何定义
            structure_data = self._get_structure_data(cell_type, slider, analysis_type)
            if not structure_data:
                return False, f"不支持的结构类型: {cell_type}", ""

            # 4. 生成文件名
            filename = self._generate_filename(cell_type, cell_size, cell_radius, slider, mode_type, analysis_type)

            # 5. 生成脚本内容
            script_content = self._generate_script_content(
                template_content, structure_data, cell_size, cell_radius, slider, mode_type, analysis_type, output_dir, filename
            )



            # 6. 保存前处理脚本
            preprocess_filename = filename.replace('.py', '_preprocess.py')
            preprocess_filepath = os.path.join(output_dir, preprocess_filename)

            # 使用UTF-8编码并添加BOM以确保兼容性
            with open(preprocess_filepath, 'w', encoding='utf-8-sig') as f:
                f.write(script_content)

            # 将生成的文件添加到追踪列表
            if hasattr(self, '_file_tracker_callback') and self._file_tracker_callback:
                try:
                    self._file_tracker_callback(preprocess_filepath)
                except Exception as e:
                    print(f"Warning: 无法添加文件到追踪列表: {e}")

            # 7. 生成并保存后处理脚本
            postprocess_content = self._generate_postprocess_script(
                output_dir, cell_size, mode_type, analysis_type, filename
            )
            postprocess_filename = filename.replace('.py', '_postprocess.py')
            postprocess_filepath = os.path.join(output_dir, postprocess_filename)

            with open(postprocess_filepath, 'w', encoding='utf-8-sig') as f:
                f.write(postprocess_content)

            # 将后处理文件也添加到追踪列表
            if hasattr(self, '_file_tracker_callback') and self._file_tracker_callback:
                try:
                    self._file_tracker_callback(postprocess_filepath)
                except Exception as e:
                    print(f"Warning: 无法添加文件到追踪列表: {e}")

            return True, f"脚本生成成功: {preprocess_filename} 和 {postprocess_filename}", filename

        except Exception as e:
            return False, f"生成脚本时出错: {str(e)}", ""

    def _create_output_directory(self, cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, batch_mode, batch_parent_dir, output_dir):
        """
        统一的文件夹创建逻辑 - 层级结构
        创建层级结构: clean_cell_type -> cell_size -> radius -> slider -> analysis_suffix
        """
        # 获取基础目录
        if batch_mode and batch_parent_dir:
            base_output_dir = batch_parent_dir
        else:
            if output_dir is None:
                if getattr(sys, 'frozen', False):
                    # 打包环境：获取可执行文件所在目录
                    current_dir = os.path.dirname(sys.executable)
                else:
                    # 开发环境：获取脚本文件所在目录
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = os.path.join(current_dir, "generate_script")
            else:
                base_output_dir = output_dir

        # 构建层级路径
        target_output_dir = self._build_hierarchical_path(base_output_dir, cell_type, cell_size, cell_radius, slider, mode_type, analysis_type)

        # 确保目录存在
        if not os.path.exists(target_output_dir):
            os.makedirs(target_output_dir)

        return target_output_dir

    def _build_hierarchical_path(self, base_dir, cell_type, cell_size, cell_radius, slider, mode_type, analysis_type):
        """
        构建层级路径结构
        基础目录/
        ├─ BCC/                          # level1: cell_type
        │  ├─ 4/                         # level2: size
        │  │  ├─ 0p3/                    # level3: radius (小数点替换为p)
        │  │  │  ├─ 0/                   # level4: slider
        │  │  │  │  ├─ static/           # level5: suffix (根据 analysis_type)
        │  │  │  │  │  └─ BCC_4_0.3_0_static.py
        │  │  │  │  ├─ 500/              # DynaCompre_500
        │  │  │  │  ├─ X/                # StaShear
        │  │  │  │  └─ X_500/            # DynaShear_500
        """
        # 清理cell_type，移除特殊字符
        clean_cell_type = re.sub(r'[^\w-]', '', cell_type)

        # 处理cell_size: 如果是整数(如5.0)去掉小数点变成5,如果是小数(如5.1)替换为5p1
        if float(cell_size).is_integer():
            size_str = str(int(float(cell_size)))
        else:
            size_str = str(cell_size).replace('.', 'p')

        # 处理radius: 将小数点替换为p (如0.5变成0p5)
        radius_dir_str = str(cell_radius).replace('.', 'p')

        # 处理slider: 如果是整数(如8.0)去掉小数点变成8,如果是小数(如8.2)替换为8p2
        if float(slider) == int(float(slider)):
            slider_str = str(int(float(slider)))
        else:
            slider_str = str(slider).replace('.', 'p')

        # 确定后缀 (Level 5) - 直接使用 analysis_type
        suffix = analysis_type

        # 构建层级路径
        # 第1层: cell_type
        level1 = clean_cell_type

        # 第2层: size
        level2 = size_str

        # 第3层: radius (小数点替换为p)
        level3 = radius_dir_str

        # 第4层: slider
        level4 = slider_str

        # 第5层: suffix
        level5 = suffix

        # 组装完整路径
        full_path = os.path.join(base_dir, level1, level2, level3, level4, level5)

        return full_path

    def _validate_parameters(self, cell_type, cell_size, cell_radius):
        """验证输入参数"""
        try:
            # 验证cell_size和cell_radius是数值
            float(cell_size)
            float(cell_radius)

            # 验证cell_type是字符串且不为空
            if not isinstance(cell_type, str) or not cell_type.strip():
                return False

            return True
        except (ValueError, TypeError):
            return False

    def _read_template(self, mode_type, analysis_type):
        """读取基础模板文件，根据分析类型选择静态或动态模板"""
        try:
            print(f"=== 模板选择调试信息 ===")
            print(f"mode_type: {mode_type}")
            print(f"analysis_type: {analysis_type}")

            # 根据 analysis_type 选择模板文件
            # 静态分析 (StaCompre, StaShear) 使用静态模板
            # 动态分析 (DynaCompre_*, DynaShear_*) 使用动态模板
            if analysis_type in ["StaCompre", "StaShear"]:
                template_file = self.base_template_file_static
                print(f"静态分析，使用静态模板: {template_file}")
            elif analysis_type.startswith("DynaCompre") or analysis_type.startswith("DynaShear"):
                template_file = self.base_template_file_dynamic
                print(f"动态分析，使用动态模板: {template_file}")
            else:
                # 默认使用静态模板
                template_file = self.base_template_file_static
                print(f"未知分析类型，使用默认静态模板: {template_file}")

            # 处理 PyInstaller 打包后的资源文件路径
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                bundle_dir = sys._MEIPASS
                template_path = os.path.join(bundle_dir, template_file)
            else:
                # 开发环境
                template_path = os.path.join(os.path.dirname(__file__), template_file)

            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            print(f"模板文件未找到: {template_path}")
            print(f"错误详情: {e}")
            return None
        except Exception as e:
            print(f"读取模板文件出错: {e}")
            print(f"模板路径: {template_path}")
            return None

    def _get_structure_data(self, cell_type, slider=4, analysis_type="StaCompre"):
        """获取结构几何数据"""
        try:
            # 判断是否需要应用X方向旋转
            # 所有剪切模式 (StaShear 和 DynaShear) 都需要旋转结构
            # 因为剪切是在X方向加载，而默认结构是为Y方向压缩设计的
            apply_x_rotation = (analysis_type == "StaShear" or analysis_type.startswith("DynaShear"))

            # 使用structure_set.py中的函数获取结构定义，传递slider参数和旋转标志
            structure_output = get_crystal_structure(cell_type, slider, apply_x_rotation=apply_x_rotation)

            # 检查是否是错误消息
            if isinstance(structure_output, str) and "不存在" in structure_output:
                return None

            # 解析字符串格式的输出
            return self._parse_structure_output(structure_output)
        except Exception as e:
            print(f"Error in _get_structure_data: {e}")
            return None

    def _parse_structure_output(self, structure_output):
        """解析结构输出，提取坐标和连接定义"""
        lines = structure_output.split('\n')
        coords = []
        cylinders = []

        in_cylinders_section = False

        for line in lines:
            line = line.strip()

            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue

            # 检测cylinders部分开始
            if 'cylinders = [' in line:
                in_cylinders_section = True
                continue

            # cylinders部分结束
            if in_cylinders_section and line == ']':
                in_cylinders_section = False
                continue

            # 处理坐标定义
            if '=' in line and not in_cylinders_section and 'cylinders' not in line:
                coords.append(line)

            # 处理cylinders连接
            elif in_cylinders_section:
                # 移除末尾的逗号并添加到列表
                cylinder_line = line.rstrip(',').strip()
                if cylinder_line:
                    cylinders.append(cylinder_line)

        return {'coords': coords, 'cylinders': cylinders}

    def _generate_script_content(self, template_content, structure_data, cell_size, cell_radius, slider=4, mode_type="Compression", analysis_type="StaCompre", output_dir=None, script_filename=None):
        """生成最终的脚本内容"""
        content = template_content

        # 1. 替换半径参数（同时根据cell_size和radius调整网格密度）
        content = self._replace_radius(content, cell_radius, cell_size)

        # 1.5. 替换模板开头的cell_size值
        content = self._replace_template_cell_size(content, cell_size)

        # 2. 替换坐标定义
        content = self._replace_coordinates(content, structure_data['coords'], cell_size)

        # 3. 替换cylinders连接
        content = self._replace_cylinders(content, structure_data['cylinders'])

        # 4. 替换切割参数（新增）
        content = self._replace_cutting_parameters(content, cell_size, cell_radius)

        # 5. 替换钢板尺寸和位置（新增）
        content = self._replace_steel_plate_dimensions(content, cell_size)

        # # 6. 生成上下刚体识别代码
        # rigid_body_code = self._generate_rigid_body_detection(structure_data, cell_size)
        # content = self._insert_rigid_body_detection(content, rigid_body_code)


        # 8. 替换velocity参数（当使用动态模板时，但不处理 Auto 模式）
        # 压缩模式(DynaCompre): velocity2 (Y方向)
        # 剪切模式(DynaShear): velocity1 (X方向)
        if analysis_type.startswith("DynaCompre") and "_Auto" not in analysis_type:
            velocity_value = self._extract_velocity_from_analysis_type(analysis_type)
            if velocity_value:
                content = self._replace_velocity_parameters(content, velocity_value, is_shear=False)

        if analysis_type.startswith("DynaShear") and "_Auto" not in analysis_type:
            velocity_value = self._extract_velocity_from_analysis_type(analysis_type)
            if velocity_value:
                content = self._replace_velocity_parameters(content, velocity_value, is_shear=True)

        # 9. 处理 Auto 模式 (DynaCompre_Auto_a/b 或 DynaShear_Auto_a/b)
        if "_Auto" in analysis_type:
            print(f"\n=== Auto Mode Detected: {analysis_type} ===")
            # 获取静态吸能极限
            ea_value = self._get_static_energy_absorb(
                self._current_structure_name, cell_size, cell_radius, slider, mode_type
            )
            if ea_value is None:
                raise ValueError(f"无法获取静态吸能数据，请先运行静态仿真 (StaCompre/StaShear)")

            # 使用 generate_script 设置的 multiplier
            multiplier = getattr(self, '_auto_multiplier', 0.8)
            print(f"  Using multiplier = {multiplier}")

            # 固定质量模式：质量固定为 1g，通过速度控制动能
            fixed_mass_gram = 1.0  # 固定质量 1g
            auto_velocity = self._calculate_velocity_for_auto_mode(ea_value, mass_gram=fixed_mass_gram, multiplier=multiplier)

            # 质量保持模板默认值 (1.0e-06 tonne = 1g)，无需替换
            # 替换速度值 - 根据 mode_type 选择方向
            is_shear = (mode_type == "Shear")
            content = self._replace_velocity_parameters(content, str(int(auto_velocity)), is_shear=is_shear)

            # 根据速度计算 timePeriod = 20 / velocity (确保足够压缩行程)
            time_period = 20.0 / auto_velocity
            content = self._replace_time_period(content, time_period)

            print(f"=== Auto Mode Setup Complete ===\n")

        # 10. 设置作业文件保存路径到脚本文件同级目录
        # content = self._set_job_directory(content, output_dir)

        # 11. 追加作业设置、提交和等待语句
        content = self._append_job_settings(content, output_dir, cell_size, mode_type, analysis_type, script_filename)

        return content

    # def _determine_script_type(self, speed_value, direction_value):
    #     """确定脚本类型"""
    #     if direction_value is not None:
    #         return "direction"
    #     elif speed_value is not None:
    #         return "speed"
    #     else:
    #         return "static"


    def _append_job_settings(self, content, output_dir, cell_size, mode_type="Compression", analysis_type="StaCompre", script_filename=None):
        """在 content 末尾追加 Job 设置和提交语句（前处理脚本）"""
        import os
        # 使用脚本文件名（去掉.py扩展名）作为job_name
        if script_filename:
            job_name = os.path.splitext(script_filename)[0]
        else:
            job_name = os.path.basename(output_dir).replace('.', 'p')

        # 生成odb文件路径：与脚本文件路径一致，只是后缀改为.odb
        odb_path = os.path.join(output_dir, f"{job_name}.odb")

        # 速度场和边界条件代码
        # 注意：顶部Tie约束现在已在模板中硬编码（Constraint-4），无需动态添加
        # 压缩模式：使用 u2 (Y方向)
        # 剪切模式：使用 u1 (X方向)
        velocity_bc_code = ""

        # 如果是动态剪切模式（非Auto），添加速度场和边界条件
        # Auto模式的速度会在后面的Auto mode处理部分通过 _replace_velocity_parameters 设置
        if analysis_type.startswith("DynaShear") and "_Auto" not in analysis_type:
            velocity_value = self._extract_velocity_from_analysis_type(analysis_type)
            if velocity_value and velocity_value.isdigit():
                velocity_bc_code = f"""
# 设置初始速度场和边界条件（动态剪切）
mdb.models['Model-1'].predefinedFields['Predefined Field-1'].setValues(
    velocity1=-{velocity_value}.0, velocity2=0.0, omega=0.0)

mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
    stepName='Step-1', u1=FREED, u2=0.0)
"""
        # 动态剪切Auto模式：只设置边界条件，速度由Auto mode处理
        elif analysis_type.startswith("DynaShear") and "_Auto" in analysis_type:
            velocity_bc_code = """
# 设置边界条件（动态剪切Auto模式，速度由Auto mode设置）
mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
    stepName='Step-1', u1=FREED, u2=0.0)
"""

        # 根据 mode_type 决定使用U1还是U2
        if mode_type == "Shear":
            disp_var_name = "U1"
        else:
            disp_var_name = "U2"  # 压缩模式使用U2

        # 如果是剪切模式（StaShear 或 DynaShear），需要替换模板中的u2为u1
        if mode_type == "Shear":
            # 1. 替换 u2=-任意数字*cell_size 为 u1=-相同数字*cell_size (Static模板)
            content = re.sub(r'u2=(-[\d.]+\*cell_size)', r'u1=\1', content)

            # 2. 替换边界条件中的 u2=u2 为 u1=u1 (在DisplacementBC中)
            content = re.sub(r'u1=0\.0, u2=u2,', 'u1=u1, u2=0.0,', content)

            # 3. 替换Initial步骤中的边界条件 (剪切模式: 释放X方向u1,固定Y方向u2)
            content = content.replace(
                'region=region, u1=SET, u2=UNSET, u3=SET,',
                'region=region, u1=UNSET, u2=SET, u3=SET,'
            )

            # 4. 替换setValuesInStep - Static模板 (变量u2)
            content = content.replace(
                '# COMPRESSION_MODE_PLACEHOLDER: u2=u2\n    mdb.models[\'Model-1\'].boundaryConditions[\'BC-2\'].setValuesInStep(\n        stepName=\'Step-1\', u2=u2, amplitude=\'Amp-1\')',
                '# SHEAR_MODE: u1=u1\n    mdb.models[\'Model-1\'].boundaryConditions[\'BC-2\'].setValuesInStep(\n        stepName=\'Step-1\', u1=u1, amplitude=\'Amp-1\')'
            )

            # 5. 替换setValuesInStep - Dynamic模板 (固定值u2=-0.5)
            content = content.replace(
                '# COMPRESSION_MODE_PLACEHOLDER: u2=-0.5\n    mdb.models[\'Model-1\'].boundaryConditions[\'BC-2\'].setValuesInStep(\n        stepName=\'Step-1\', u2=-0.5, amplitude=\'Amp-1\')',
                '# SHEAR_MODE: u1=-0.5\n    mdb.models[\'Model-1\'].boundaryConditions[\'BC-2\'].setValuesInStep(\n        stepName=\'Step-1\', u1=-0.5, amplitude=\'Amp-1\')'
            )

        addition = f"""
{velocity_bc_code}
# a = mdb.models['Model-1'].rootAssembly
# a.regenerate()

os.chdir(r"{output_dir}")

# mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(numIntervals=60)

mdb.Job(name='{job_name}', model='Model-1', description='', type=ANALYSIS,
    atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90,
    memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
    explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=ON,
    modelPrint=ON, contactPrint=ON, historyPrint=ON, userSubroutine='',
    scratch='', resultsFormat=ODB, numThreadsPerMpiProcess=0, numCpus=8,
    numDomains=8, numGPUs=0)

# 计算体积和密度，保存到文件供后处理使用
try:
    part = mdb.models['Model-1'].parts['MergedStructure']
    volume = part.getVolume()
    density = volume / ({cell_size} ** 3)
    print("MergedStructure volume = ", volume)
    print("Density = ", density)

    # 保存到临时文件
    with open('density_temp.txt', 'w') as f:
        f.write(str(density))
    print("Density saved to density_temp.txt")
except Exception as e:
    print("Warning: Cannot calculate density: " + str(e))
    with open('density_temp.txt', 'w') as f:
        f.write('0.0')

# 生成 .inp 文件而不是直接提交
print("Generating input file...")
mdb.jobs['{job_name}'].writeInput(consistencyChecking=OFF)
print("Input file '{job_name}.inp' generated successfully.")
print("CAE will exit after script completion to release license.")

# 脚本自然结束，Abaqus CAE 会自动退出并释放 license
# 注意：不要使用 sys.exit()，它会导致批处理脚本也退出

"""
        return content.rstrip() + addition

    def _generate_postprocess_script(self, output_dir, cell_size, mode_type="Compression", analysis_type="StaCompre", script_filename=None):
        """生成后处理脚本内容"""
        import os
        # 使用脚本文件名（去掉.py扩展名）作为job_name
        if script_filename:
            job_name = os.path.splitext(script_filename)[0]
        else:
            job_name = os.path.basename(output_dir).replace('.', 'p')

        # 根据 mode_type 决定使用U1还是U2
        if mode_type == "Shear":
            disp_var_name = "U1"  # 剪切模式
        else:
            disp_var_name = "U2"  # 压缩模式

        postprocess_content = f"""# -*- coding: utf-8 -*-
# Abaqus后处理脚本 - 自动等待计算完成并提取结果
from abaqus import *
from abaqusConstants import *
import os
import time
import sys

print("="*80)
print("POST-PROCESSING SCRIPT STARTED")
print("Python version:", sys.version)
print("="*80)

# 使用当前工作目录
script_dir = os.getcwd()
print("Working directory:", script_dir)

# 等待计算完成
odb_filename = '{job_name}.odb'
lck_filename = '{job_name}.lck'

print("ODB file to process:", odb_filename)
print("Checking file existence...")
print("  ODB exists:", os.path.exists(odb_filename))
print("  LCK exists:", os.path.exists(lck_filename))
print("Waiting for job completion...")

# 第1步：等待ODB文件生成（作业开始）
timeout = 3600  # 1小时超时
start_time = time.time()
job_status = "unknown"  # 记录作业状态: completed, timeout, no_odb

try:
    while not os.path.exists(odb_filename):
        if time.time() - start_time > timeout:
            print("WARNING: Timeout - ODB file not created after 1 hour")
            job_status = "no_odb"
            break
        time.sleep(10)
        print("Waiting for ODB to be created...")

    if job_status == "unknown":
        print("ODB file detected, waiting for analysis to complete...")

        # 第2步：等待.lck文件消失（作业完成）
        while os.path.exists(lck_filename):
            if time.time() - start_time > timeout:
                print("WARNING: Timeout - Job still running after 1 hour, will attempt data extraction anyway")
                job_status = "timeout"
                break
            time.sleep(10)
            print("Analysis running (lck file exists)...")

        if job_status == "unknown":
            print("Analysis completed (lck file removed). Starting post-processing...")
            job_status = "successful"

        time.sleep(2)  # 短暂等待确保文件写入完成

except Exception as e:
    print("ERROR during job monitoring: " + str(e))
    job_status = "error"

print("Job status: " + job_status)
print("Attempting data extraction...")

# ===== 开始后处理 =====
# 使用odbAccess直接读取ODB，避免启动可视化组件
from odbAccess import openOdb
import xyPlot

# 检查ODB文件是否存在
if not os.path.exists(odb_filename):
    print("=" * 80)
    print("ERROR: ODB file does not exist!")
    print("Job failed to create output database.")
    print("=" * 80)
    raise RuntimeError("ODB file not created - job failed")

# 如果超时但作业仍在运行，等待.lck文件消失
if job_status == "timeout":
    print("=" * 80)
    print("Job timed out - waiting for lock file to be released...")
    print("=" * 80)
    # 额外等待一段时间，看作业是否会自然结束
    extra_wait = 300  # 额外等待5分钟
    extra_start = time.time()
    while os.path.exists(lck_filename) and (time.time() - extra_start < extra_wait):
        time.sleep(10)
        print("  Still waiting for lock file (timeout + extra wait)...")

    # 如果还有锁文件，说明作业卡住了
    if os.path.exists(lck_filename):
        print("Lock file still exists after extra wait - job may be stuck")
        print("Attempting to proceed anyway...")

# 打开odb文件进行后处理 (使用odbAccess避免GUI)
try:
    odb = openOdb(path=odb_filename, readOnly=True)
except Exception as e:
    print("=" * 80)
    print("ERROR: Cannot open ODB file!")
    print("Error details: " + str(e))
    print("=" * 80)
    raise RuntimeError("Cannot open ODB file: " + str(e))

try:
    # ===== 自动查找输出变量名 =====
    step = odb.steps['Step-1']
    force_var = None
    disp_var = None
    force_key = None
    disp_key = None

    # 确定要查找的反力和位移变量名
    disp_key = '{disp_var_name}'
    mode_type = '{mode_type}'
    analysis_type = '{analysis_type}'

    # 确定 force_key: 根据位移变量名直接对应
    if disp_key == 'U1':
        force_key = 'RF1'  # 剪切模式
    else:
        force_key = 'RF2'  # 压缩模式

    # 判断是否为 Dynamic 模式
    is_dynamic = analysis_type.startswith('Dyna')
    print("Mode: " + ("Dynamic" if is_dynamic else "Static"))

    # 调试：打印所有可用的region及其输出变量
    print("=" * 80)
    print("Available history regions:")
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        outputs = region.historyOutputs.keys()
        print("  - " + region_name + " -> " + str(outputs))

    print("")
    print("=" * 80)
    print("Searching for: Displacement=%s, Force=%s" % (disp_key, force_key))
    print("=" * 80)

    # 辅助函数：从候选列表中选择绝对值均值最大的
    def select_by_max_mean(candidates, output_key, label):
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            selected = candidates[0][0]
            print("  Selected %s: %s" % (label, selected))
            return selected
        else:
            max_mean = -1
            selected = None
            for name, reg in candidates:
                data = reg.historyOutputs[output_key].data
                mean_val = sum([abs(d[1]) for d in data]) / len(data) if data else 0
                print("  %s candidate %s mean: %f" % (label, name, mean_val))
                if mean_val > max_mean:
                    max_mean = mean_val
                    selected = name
            print("  Selected %s (max mean): %s (mean=%f)" % (label, selected, max_mean))
            return selected

    # 查找位移：根据模式决定在哪里查找
    disp_candidates = []
    if is_dynamic:
        # Dynamic模式：
        # - 压缩(Compression): 位移在 MERGEDSTRUCTURE (Reflection节点集)
        # - 剪切(Shear): 位移在 RIGIDPLATE-2 (TopReflection节点集)
        # 同时搜索两者，通过 select_by_max_mean 选择正确的
        print("[Dynamic Mode] Searching displacement in MERGEDSTRUCTURE and RIGIDPLATE...")
        for region_name in step.historyRegions.keys():
            region = step.historyRegions[region_name]
            region_upper = region_name.upper()
            if 'MERGEDSTRUCTURE' in region_upper or 'RIGIDPLATE' in region_upper:
                if disp_key in region.historyOutputs.keys():
                    disp_candidates.append((region_name, region))
                    print("  Found displacement candidate: %s" % region_name)
    else:
        # Static/其他: 位移在 RIGIDPLATE-2
        print("[Static Mode] Searching displacement in RIGIDPLATE-2...")
        for region_name in step.historyRegions.keys():
            region = step.historyRegions[region_name]
            region_upper = region_name.upper()
            if 'RIGIDPLATE-2' in region_upper:
                if disp_key in region.historyOutputs.keys():
                    disp_candidates.append((region_name, region))
                    print("  Found displacement candidate: %s" % region_name)

    disp_var = select_by_max_mean(disp_candidates, disp_key, "displacement")

    # 查找反力：在所有 RIGIDPLATE 中查找，选择均值最大的
    print("Searching force in all RIGIDPLATE...")
    force_candidates = []
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        if 'RIGIDPLATE' in region_name.upper():
            if force_key in region.historyOutputs.keys():
                force_candidates.append((region_name, region))
                print("  Found force candidate: %s" % region_name)

    force_var = select_by_max_mean(force_candidates, force_key, "force")

    # ===== 最终结果 =====
    print("")
    print("=" * 80)
    print("FINAL RESULT:")
    print("  Force variable (%s): %s" % (force_key, str(force_var)))
    print("  Displacement variable (%s): %s" % (disp_key, str(disp_var)))
    print("=" * 80)

    if force_var is None or disp_var is None:
        error_msg = "Cannot find required output variables. Force: " + str(force_var) + ", Disp: " + str(disp_var)
        odb.close()
        raise ValueError(error_msg)

    # 提取数据
    force_region = step.historyRegions[force_var]
    force_data = force_region.historyOutputs[force_key]
    xy_force = session.XYData('Force', force_data.data)

    disp_region = step.historyRegions[disp_var]
    disp_data = disp_region.historyOutputs['{disp_var_name}']
    xy_disp = session.XYData('Displacement', disp_data.data)

    # 合并数据
    xy_combined = combine(abs(xy_disp), abs(xy_force))

    # 切换到输出目录
    os.chdir(r"{output_dir}")

    # 读取前处理阶段计算的密度
    density = 0.0
    try:
        with open('density_temp.txt', 'r') as f:
            density = float(f.read().strip())
        print("Density loaded from file: ", density)
    except Exception as e:
        print("Warning: Cannot load density from file: " + str(e))
        density = 0.0

    # 保存为txt文件
    with open('feature_data.txt', 'w') as f:
        f.write('{job_name}' + "\\n")
        f.write("status: " + job_status + "\\n")
        f.write("density: " + str(density) + "\\n")
        f.write(str(disp_var) + " " + str(force_var))

    # 追加xy_combined数据
    session.writeXYReport(fileName='feature_data.txt', xyData=(xy_combined, ), appendMode=ON)

    # 关闭ODB
    odb.close()


    print("=" * 80)
    print("Post-processing completed successfully!")
    print("Status: " + job_status)
    print("=" * 80)

except Exception as e:
    print("=" * 80)
    print("FATAL ERROR during post-processing")
    print("Error: " + str(e))
    print("=" * 80)
    import traceback
    traceback.print_exc()
    raise  # 重新抛出异常，让脚本以错误状态退出

print("CAE will exit after script completion to release license.")

# 脚本自然结束，Abaqus CAE 会自动退出并释放 license
# 注意：不要使用 sys.exit()，它会导致批处理脚本也退出
"""
        return postprocess_content

    def _replace_amp_parameters(self, content, cell_size):
        """根据size值替换amp-1范围参数，目前0.6对应size=5"""
        try:
            # 计算amp值：基于size=5对应0.6的比例关系
            # amp_value = 0.6 * (cell_size / 5.0)
            base_size = 5.0  # 基础size值
            base_amp = 0.6   # 基础amp值

            cell_size_float = float(cell_size)
            amp_value = base_amp * (cell_size_float / base_size)

            print(f"\n=== Amp-1参数替换调试信息 ===")
            print(f"单元尺寸: {cell_size_float}")
            print(f"基础尺寸: {base_size}")
            print(f"基础Amp值: {base_amp}")
            print(f"计算的Amp值: {amp_value}")

            # 格式化数值，保持4位小数精度，然后移除尾随零
            formatted_amp = f"{amp_value:.4f}".rstrip('0').rstrip('.')
            if not formatted_amp:
                formatted_amp = '0'

            # 替换TabularAmplitude中的data参数
            # 匹配模式：data=((0.0, 0.0), (0.6, 1.0))
            pattern = r'data=\(\(0\.0, 0\.0\), \(0\.6, 1\.0\)\)'
            replacement = f'data=((0.0, 0.0), ({formatted_amp}, 1.0))'
            content = re.sub(pattern, replacement, content)

            # 同时替换seedPart中的size参数
            # 匹配模式：size=0.6
            size_pattern = r'size=0\.6(?=,|\)|$)'
            size_replacement = f'size={formatted_amp}'
            content = re.sub(size_pattern, size_replacement, content)

            print(f"已将Amp-1参数替换为: {formatted_amp}")
            print(f"已将seedPart size参数替换为: {formatted_amp}")

            return content

        except (ValueError, TypeError) as e:
            print(f"Warning: 无法转换cell_size到数值: {cell_size}, 错误: {e}")
            return content

    def _replace_velocity_parameters(self, content, speed_value, is_shear=False):
        """替换速度参数，根据speed_value调整速度值

        Args:
            content: 模板内容
            speed_value: 速度值
            is_shear: 是否为剪切模式。True则替换velocity1(X方向)，False则替换velocity2(Y方向)
        """
        try:
            # 将speed_value转换为数值，然后取负值作为速度
            speed_num = float(speed_value)
            velocity_value = -speed_num

            print(f"\n=== 速度参数替换调试信息 ===")
            print(f"Speed值: {speed_value}")
            print(f"模式: {'剪切(X方向)' if is_shear else '压缩(Y方向)'}")

            if is_shear:
                # 剪切模式：替换velocity1 (X方向)
                print(f"Velocity1值: {velocity_value}")
                # 先将velocity2设为0
                content = re.sub(r'velocity2=-?\d+\.?\d*', 'velocity2=0.0', content)
                # 设置velocity1
                content = re.sub(r'velocity1=-?\d+\.?\d*', f'velocity1={velocity_value}', content)
                print(f"已将velocity1替换为: {velocity_value}, velocity2设为0")
            else:
                # 压缩模式：替换velocity2 (Y方向)
                print(f"Velocity2值: {velocity_value}")
                pattern = r'velocity2=-?\d+\.?\d*'
                replacement = f'velocity2={velocity_value}'
                content = re.sub(pattern, replacement, content)
                print(f"已将velocity2替换为: {velocity_value}")

            return content

        except (ValueError, TypeError) as e:
            print(f"Warning: 无法转换speed_value到数值: {speed_value}, 错误: {e}")
            return content


    def _replace_radius(self, content, cell_radius, cell_size=5.0):
        """替换半径参数并动态调整网格密度（基于cell_size和radius）"""
        # 1. 查找并替换radius = xxx这一行
        pattern = r'radius = [\d.]+\s*$'
        replacement = f'radius = {cell_radius}'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        # 2. 根据cell_size和radius动态调整网格密度
        # 基准: cell_size=5, radius=0.5 对应 mesh_size=0.1
        base_cell_size = 5.0
        base_radius = 0.5
        base_mesh_size = 0.1

        # 计算新的网格密度: mesh_size = base_mesh_size * (radius / base_radius) * (cell_size / base_cell_size)
        cell_size_float = float(cell_size)
        radius_float = float(cell_radius)
        new_mesh_size = base_mesh_size * (radius_float / base_radius) * (cell_size_float / base_cell_size)

        # 格式化为两位小数
        new_mesh_size = round(new_mesh_size, 2)

        # 3. 替换MergedStructure的seedPart size参数（通常是第一个）
        # 匹配模式: p.seedPart(size=0.2, ...
        mesh_pattern = r'(p\.seedPart\(size=)[\d.]+(\s*,)'
        mesh_replacement = rf'\g<1>{new_mesh_size}\g<2>'
        content = re.sub(mesh_pattern, mesh_replacement, content, count=1)

        print(f"\n=== 网格密度动态调整 ===")
        print(f"Cell Size: {cell_size_float}, Radius: {radius_float}")
        print(f"基准: cell_size=5, radius=0.5, mesh_size=0.1")
        print(f"调整后网格密度: {new_mesh_size}")

        return content

    def _replace_template_cell_size(self, content, cell_size):
        """替换模板开头的cell_size值"""
        # 查找并替换cell_size = xxx这一行
        pattern = r'cell_size = [\d.]+\s*$'

        # 处理数值，移除不必要的小数点
        size_str = str(int(float(cell_size))) if float(cell_size).is_integer() else str(cell_size)
        replacement = f'cell_size = {size_str}'

        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        print(f"\n=== Cell Size模板替换调试信息 ===")
        print(f"原始cell_size: 5")
        print(f"新cell_size: {size_str}")
        print(f"替换模式: {pattern}")
        print(f"替换内容: {replacement}")

        return content

    def _replace_coordinates(self, content, coords, cell_size):
        """替换坐标定义并进行缩放"""
        # 计算缩放因子
        scale_factor = float(cell_size) / self.base_cell_size

        print(f"\n=== 坐标缩放调试信息 ===")
        print(f"目标单元尺寸: {cell_size}")
        print(f"基础单元尺寸: {self.base_cell_size}")
        print(f"缩放因子: {scale_factor}")
        print(f"原始坐标数量: {len(coords)}")

        # 找到坐标定义的开始和结束位置
        start_pattern = r'# 定义关键点坐标\s*\n'
        end_pattern = r'\n\s*# 定义圆柱体连接'

        # 生成缩放后的坐标
        scaled_coords = []
        for i, coord in enumerate(coords):
            scaled_coord = self._scale_coordinate_line(coord, scale_factor)
            scaled_coords.append(scaled_coord)
            # 只打印前几个坐标以避免过多输出
            if i < 5:
                print(f"坐标{i+1}: {coord.strip()} -> {scaled_coord.strip()}")

        # 构建新的坐标部分
        new_coords_section = "# 定义关键点坐标\n" + '\n'.join(scaled_coords) + '\n'

        # 替换内容
        match = re.search(start_pattern + r'(.*?)' + end_pattern, content, re.DOTALL)
        if match:
            content = content[:match.start()] + new_coords_section + '\n# 定义圆柱体连接' + content[match.end():]

        return content

    def _scale_coordinate_line(self, coord_line, scale_factor):
        """缩放单个坐标行"""
        # 使用正则表达式找到坐标数组中的数字并缩放
        def scale_number(match):
            number = float(match.group())
            scaled = number * scale_factor
            # 改进的数值格式化，保持精度
            # 使用4位小数精度，然后移除尾随零
            formatted = f"{scaled:.4f}".rstrip('0').rstrip('.')
            # 如果结果为空（如0.0000），返回'0'
            return formatted if formatted else '0'

        # 匹配方括号内的数字（包括负数），但不匹配变量名中的数字
        # 使用更精确的正则表达式，只匹配 = [ 和 ] 之间的数字
        pattern = r'(=\s*\[)([^\]]+)(\])'

        def replace_coordinates(match):
            prefix = match.group(1)  # '= ['
            coords_str = match.group(2)  # 坐标字符串
            suffix = match.group(3)  # ']'

            # 在坐标字符串中替换数字
            number_pattern = r'-?\d+\.?\d*'
            scaled_coords = re.sub(number_pattern, scale_number, coords_str)

            return prefix + scaled_coords + suffix

        scaled_line = re.sub(pattern, replace_coordinates, coord_line)
        return scaled_line

    def _replace_cylinders(self, content, cylinders):
        """替换cylinders连接定义"""
        # 找到cylinders定义的开始和结束位置
        start_pattern = r'cylinders = \['
        end_pattern = r'\]'

        # 构建新的cylinders部分
        cylinders_lines = []
        for i, cylinder in enumerate(cylinders):
            if i == len(cylinders) - 1:
                cylinders_lines.append(f'    {cylinder}')
            else:
                cylinders_lines.append(f'    {cylinder},')

        new_cylinders_section = 'cylinders = [\n' + '\n'.join(cylinders_lines) + '\n]'

        # 查找并替换cylinders部分
        # 使用更精确的正则表达式匹配整个cylinders数组
        pattern = r'cylinders = \[([^\]]*(?:\[[^\]]*\][^\]]*)*)?\]'
        content = re.sub(pattern, new_cylinders_section, content, flags=re.DOTALL)

        return content

    def _replace_cutting_parameters(self, content, cell_size, cell_radius):
        """替换切割相关的参数，使用新的位置计算方式"""
        cell_size_float = float(cell_size)
        cell_radius_float = float(cell_radius)

        # 新的切割位置计算方式
        # 切割开始位置：size/2 + 2*max(radius_value)
        cutting_start_position = cell_size_float / 2 + 2 * cell_radius_float

        # 切割结束位置：-size
        cutting_end_position = -cell_size_float

        # 计算切割深度（从开始位置到结束位置的距离）
        cutting_depth = cutting_start_position - cutting_end_position

        # 半尺寸用于设置矩形和变换原点
        half_size = cell_size_float / 2

        print(f"\n=== 切割参数新计算方式调试信息 ===")
        print(f"单元尺寸: {cell_size_float}")
        print(f"圆柱半径: {cell_radius_float}")
        print(f"切割开始位置: {cutting_start_position} (size/2 + 2*radius)")
        print(f"切割结束位置: {cutting_end_position} (-size)")
        print(f"切割深度: {cutting_depth}")
        print(f"半尺寸: {half_size}")

        # 替换切割平面offset值（使用新的切割开始位置）
        content = re.sub(r'offset=3(?=\))', f'offset={cutting_start_position}', content)

        # 替换切割深度值（使用新计算的深度）
        content = re.sub(r'depth=6(?=,)', f'depth={cutting_depth}', content)

        # 替换变换原点中的坐标值
        # 顶部切割的origin坐标（使用半尺寸）
        content = re.sub(r'origin=\(0\.0, 0\.0, 2\.5\)',
                        f'origin=(0.0, 0.0, {half_size})', content)

        # 侧面切割的origin坐标（使用半尺寸）
        content = re.sub(r'origin=\(0\.0, 2\.5, 0\.0\)',
                        f'origin=(0.0, {half_size}, 0.0)', content)

        # 替换切割矩形的尺寸
        # 内部矩形 (-2.5, -2.5) to (2.5, 2.5) 使用半尺寸
        content = re.sub(r'point1=\(-2\.5, -2\.5\)',
                        f'point1=(-{half_size}, -{half_size})', content)
        content = re.sub(r'point2=\(2\.5, 2\.5\)',
                        f'point2=({half_size}, {half_size})', content)

        # 外部矩形 (-5.0, -5.0) to (5.0, 5.0) - 使用双倍尺寸
        outer_size = cell_size_float
        content = re.sub(r'point1=\(-5\.0, -5\.0\)',
                        f'point1=(-{outer_size}, -{outer_size})', content)
        content = re.sub(r'point2=\(5\.0, 5\.0\)',
                        f'point2=({outer_size}, {outer_size})', content)

        return content

    def _replace_steel_plate_dimensions(self, content, cell_size):
        """替换钢板尺寸和位置，使其与cell_size成比例缩放"""
        # 计算钢板尺寸 = 1.5 × cell_size
        cell_size_float = float(cell_size)
        plate_size = 1.5 * cell_size_float  # 钢板总尺寸（例如 cell_size=5 时，钢板=7.5）

        # 基础模板的钢板参数（8.0 x 8.0）
        base_plate_length = 8.0    # 原刚性板长度
        base_plate_width = 8.0     # 原刚性板宽度（extrude depth）
        base_half_size = 2.5        # 原始模板的半尺寸
        base_offset = 4.0           # 原刚性板半长度（8.0 / 2 = 4.0）

        # 计算新的钢板参数
        scaled_plate_length = plate_size    # 新钢板长度
        scaled_plate_width = plate_size     # 新钢板宽度
        scaled_half_size = cell_size_float / 2.0    # cell的半尺寸
        scaled_offset = plate_size / 2.0    # 钢板半长度

        print(f"\n=== 钢板参数缩放调试信息 ===")
        print(f"刚性板长度: {base_plate_length} -> {scaled_plate_length}")
        print(f"刚性板宽度: {base_plate_width} -> {scaled_plate_width}")
        print(f"板位置偏移: {base_offset} -> {scaled_offset}")

        # 替换刚性板的线段长度 (-4.0, 0.0) to (4.0, 0.0)
        content = re.sub(r'point1=\(-4\.0, 0\.0\)',
                        f'point1=(-{scaled_offset}, 0.0)', content)
        content = re.sub(r'point2=\(4\.0, 0\.0\)',
                        f'point2=({scaled_offset}, 0.0)', content)

        # 替换刚性板的挤出深度
        content = re.sub(r'depth=8\.0(?=\))', f'depth={scaled_plate_width}', content)

        # 替换刚性板的位置 vector
        # RigidPlate-1: (0.0, -2.5, -4.0)
        content = re.sub(r'vector=\(0\.0, -2\.5, -4\.0\)',
                        f'vector=(0.0, -{scaled_half_size}, -{scaled_offset})', content)

        # RigidPlate-2: (0.0, 2.5, -4.0)
        content = re.sub(r'vector=\(0\.0, 2\.5, -4\.0\)',
                        f'vector=(0.0, {scaled_half_size}, -{scaled_offset})', content)

        return content

    # def _generate_rigid_body_detection(self, structure_data, cell_size):
    #     """生成上下刚体识别代码（已禁用）"""
    #     # 刚体识别功能已禁用，因为：
    #     # 1. 当前代码只输出调试信息，无实际功能
    #     # 2. 插入位置复杂，容易导致缩进错误
    #     # 如需启用，需要修复插入逻辑以确保代码插入到Macro1函数内部
    #     return ""



    # def _insert_rigid_body_detection(self, content, rigid_body_code):
    #     """将上下刚体识别代码插入到适当位置"""
    #     # 在Macro1()函数内，接触定义之前插入
    #     # 使用灵活的正则表达式，支持多种注释格式

    #     # 第一层：尝试匹配包含"接触"的注释（如"接触属性"、"接触定义"等）
    #     contact_pattern = r'(\s*#.*?接触.*?\n)'

    #     # 如果找到接触相关标记，在其前面插入
    #     if re.search(contact_pattern, content):
    #         replacement = rigid_body_code + r'\1'
    #         content = re.sub(contact_pattern, replacement, content, count=1)
    #         print("刚体识别代码已插入（在接触注释前）")
    #     else:
    #         # 如果没找到，在第一个ContactProperty定义前插入
    #         contact_property_pattern = r'(\s*mdb\.models\[\'Model-1\'\]\.ContactProperty\(\'IntProp-1\'\))'
    #         if re.search(contact_property_pattern, content):
    #             replacement = rigid_body_code + r'\1'
    #             content = re.sub(contact_property_pattern, replacement, content, count=1)
    #             print("刚体识别代码已插入（在ContactProperty前）")
    #         else:
    #             print("警告：未找到合适的位置插入刚体识别代码")

    #     return content


    def _generate_filename(self, cell_type, cell_size, cell_radius, slider, mode_type="Compression", analysis_type="StaCompre"):
        """生成文件名 (小数点替换为p)"""
        # 清理cell_type，移除特殊字符
        clean_cell_type = re.sub(r'[^\w-]', '', cell_type)

        # 处理cell_size: 如果是整数(如5.0)去掉小数点变成5,如果是小数(如5.1)替换为5p1
        if float(cell_size).is_integer():
            size_str = str(int(float(cell_size)))
        else:
            size_str = str(cell_size).replace('.', 'p')

        # 处理radius: 将小数点替换为p (如0.5变成0p5)
        radius_str = str(cell_radius).replace('.', 'p')

        # 处理slider: 如果是整数(如8.0)去掉小数点变成8,如果是小数(如8.2)替换为8p2
        if float(slider) == int(float(slider)):
            slider_str = str(int(float(slider)))
        else:
            slider_str = str(slider).replace('.', 'p')

        # 使用 analysis_type 作为后缀
        suffix = f"_{analysis_type}"

        return f"{clean_cell_type}_{size_str}_{radius_str}_{slider_str}{suffix}.py"



def generate_abaqus_script(cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None):
    """
    便捷函数：生成Abaqus脚本

    参数:
    - cell_type: 晶体结构类型
    - cell_size: 单元尺寸
    - cell_radius: 杆件半径
    - slider: 滑块值 (0-8)，用于控制BCC/BCCZ结构中O原子的位置
    - output_dir: 输出目录
    - mode_type: 模式类型 ("Compression" 或 "Shear")
    - analysis_type: 分析类型 ("StaCompre", "DynaCompre_500", "StaShear", "DynaShear_500" 等)
    - batch_mode: 是否为批量模式
    - batch_parent_dir: 批量模式的父文件夹路径

    返回:
    - (success: bool, message: str, filename: str)
    """
    generator = AbaqusScriptGenerator()

    # 尝试设置文件追踪回调
    try:
        import sys
        # 尝试多种可能的模块名称
        main_module = None
        for module_name in ['main', '__main__']:
            if module_name in sys.modules:
                main_module = sys.modules[module_name]
                if hasattr(main_module, 'add_generated_file'):
                    generator.set_file_tracker_callback(main_module.add_generated_file)
                    break
    except Exception:
        pass  # 静默失败，不影响脚本生成

    return generator.generate_script(cell_type, cell_size, cell_radius, slider, output_dir, mode_type, analysis_type, batch_mode, batch_parent_dir)


if __name__ == "__main__":
    pass