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
from config import Config


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

    def _write_and_track(self, filepath, content):
        """Write *content* to *filepath* and notify the file tracker.

        Shell/batch 脚本必须是纯 UTF-8（BOM 会破坏 shebang 与 #PBS 指令）；
        .py 输出保留 BOM 以兼容老版本 Windows Abaqus Python。
        """
        ext = os.path.splitext(filepath)[1].lower()
        encoding = 'utf-8' if ext in ('.pbs', '.sh', '.bat', '.slurm') else 'utf-8-sig'
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
        if hasattr(self, '_file_tracker_callback') and self._file_tracker_callback:
            try:
                self._file_tracker_callback(filepath)
            except Exception as e:
                print(f"Warning: 无法添加文件到追踪列表: {e}")

    @staticmethod
    def _format_param(value, try_int=True):
        """Convert a number to a path-safe string (e.g. 0.5 -> '0p5', 8.0 -> '8').

        Args:
            value: numeric value (int, float, or string representation)
            try_int: if True, convert whole-number floats to int strings (5.0 -> '5')
        Returns:
            path-safe string with dots replaced by 'p'
        """
        v = float(value)
        if try_int and v == int(v):
            return str(int(v))
        return str(value).replace('.', 'p')

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
            size_str = self._format_param(cell_size)
            radius_str = self._format_param(cell_radius, try_int=False)
            slider_str = self._format_param(slider)

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

    def generate_script(self, cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None, lattice_array=(1,1,1), flat_output=False):
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
                    mode_type, modified_analysis_type, batch_mode, batch_parent_dir, lattice_array=lattice_array, flat_output=flat_output
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
            mode_type, analysis_type, batch_mode, batch_parent_dir, lattice_array=lattice_array, flat_output=flat_output
        )

    def _generate_single_script(self, cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None, lattice_array=(1,1,1), flat_output=False):
        """生成单个脚本的内部实现"""
        try:
            # 统一的文件夹创建逻辑
            output_dir = self._create_output_directory(cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, batch_mode, batch_parent_dir, output_dir, flat_output=flat_output)

            # 设置当前结构名称，用于结构感知检测
            self._current_structure_name = cell_type

            # 1. 验证参数
            if not self._validate_parameters(cell_type, cell_size, cell_radius):
                return False, "参数验证失败", ""

            # 统一走阵列路径（包括1x1x1），确保输出格式一致
            is_array = True

            if is_array:
                # ========== 阵列模式：生成完整的独立脚本 ==========
                # 获取结构几何定义
                structure_data = self._get_structure_data(cell_type, slider, analysis_type)
                if not structure_data:
                    return False, f"不支持的结构类型: {cell_type}", ""

                # 生成文件名（含阵列后缀）
                filename = self._generate_filename(cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, lattice_array=lattice_array)

                # 生成阵列脚本内容
                script_content = self._generate_array_script(
                    structure_data, cell_type, cell_size, cell_radius, slider,
                    mode_type, analysis_type, output_dir, filename, lattice_array
                )

                # 保存前处理脚本
                preprocess_filename = filename.replace('.py', '_preprocess.py')
                preprocess_filepath = os.path.join(output_dir, preprocess_filename)
                self._write_and_track(preprocess_filepath, script_content)

                # 生成阵列后处理脚本
                postprocess_content = self._generate_array_postprocess_script(
                    output_dir, cell_size, mode_type, analysis_type, filename, lattice_array
                )
                postprocess_filename = filename.replace('.py', '_postprocess.py')
                postprocess_filepath = os.path.join(output_dir, postprocess_filename)
                self._write_and_track(postprocess_filepath, postprocess_content)

                # 生成 per-job PBS 提交脚本
                pbs_content = self._generate_pbs_script(
                    output_dir, os.path.splitext(filename)[0],
                    preprocess_filename, postprocess_filename
                )
                pbs_filepath = os.path.join(output_dir, 'run.pbs')
                self._write_and_track(pbs_filepath, pbs_content)

                return True, f"阵列脚本生成成功: {preprocess_filename}, {postprocess_filename} 和 run.pbs", filename

            # ========== 原有1x1x1模式 ==========
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
            self._write_and_track(preprocess_filepath, script_content)

            # 7. 生成并保存后处理脚本
            postprocess_content = self._generate_postprocess_script(
                output_dir, cell_size, mode_type, analysis_type, filename
            )
            postprocess_filename = filename.replace('.py', '_postprocess.py')
            postprocess_filepath = os.path.join(output_dir, postprocess_filename)
            self._write_and_track(postprocess_filepath, postprocess_content)

            return True, f"脚本生成成功: {preprocess_filename} 和 {postprocess_filename}", filename

        except Exception as e:
            return False, f"生成脚本时出错: {str(e)}", ""

    def _create_output_directory(self, cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, batch_mode, batch_parent_dir, output_dir, flat_output=False):
        """
        统一的文件夹创建逻辑

        当 flat_output=True 时，直接使用 output_dir 作为目标目录（不添加层级路径）。
        否则按层级结构创建: clean_cell_type -> cell_size -> radius -> slider -> analysis_suffix
        """
        if flat_output and output_dir is not None:
            # 平铺模式：直接使用调用方指定的目录
            target_output_dir = output_dir
        else:
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

        size_str = self._format_param(cell_size)
        radius_dir_str = self._format_param(cell_radius, try_int=False)
        slider_str = self._format_param(slider)

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

        # 1.6. 替换球径比（模板中的 1.2 → Config.SPHERE_RADIUS_RATIO_SCRIPT）
        content = re.sub(
            r'sphere_radius\s*=\s*radius\s*\*\s*[\d.]+',
            f'sphere_radius = radius * {Config.SPHERE_RADIUS_RATIO_SCRIPT}',
            content
        )

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
        # 公式与模板和阵列脚本一致: 0.3 * sqrt(radius / 0.5) * (cell_size / 5.0)
        import math
        cell_size_float = float(cell_size)
        radius_float = float(cell_radius)
        new_mesh_size = 0.3 * math.sqrt(radius_float / 0.5) * (cell_size_float / 5.0)

        # 格式化为两位小数
        new_mesh_size = round(new_mesh_size, 2)

        # 3. 替换MergedStructure的seedPart size参数（通常是第一个）
        # 匹配模式: p.seedPart(size=0.2, ...
        mesh_pattern = r'(p\.seedPart\(size=)[\d.]+(\s*,)'
        mesh_replacement = rf'\g<1>{new_mesh_size}\g<2>'
        content = re.sub(mesh_pattern, mesh_replacement, content, count=1)

        print(f"\n=== 网格密度动态调整 ===")
        print(f"Cell Size: {cell_size_float}, Radius: {radius_float}")
        print(f"公式: 0.2 * sqrt(radius / 0.5) * (cell_size / 5.0)")
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


    # ------------------------------------------------------------------
    # Array script sub-methods  (each returns list[str])
    # ------------------------------------------------------------------

    def _array_script_header(self, cell_type, cell_size, cell_radius, a, b, c, analysis_type, time_period=0.3):
        """Config + imports section for the array ABAQUS script."""
        cell_size_float = float(cell_size)
        lines = []
        lines.append("# -*- coding: utf-8 -*-")
        lines.append(f'"""')
        lines.append(f'{cell_type} {a}x{b}x{c} Array - {analysis_type}')
        lines.append(f'Generated by size_effect_batch/generate_batch.py')
        lines.append(f'timePeriod = {time_period} ({0.3} * {b}, constant strain rate)')
        lines.append(f'"""')
        lines.append("")
        lines.append("from abaqus import *")
        lines.append("from abaqusConstants import *")
        lines.append("import numpy as np")
        lines.append("from math import acos, degrees")
        lines.append("from numpy.linalg import norm")
        lines.append("from numpy import cross, dot")
        lines.append("import regionToolset")
        lines.append("import os")
        lines.append("import math")
        lines.append("")
        lines.append("# ==========================================================")
        lines.append("# CONFIG")
        lines.append("# ==========================================================")
        lines.append(f"radius = {cell_radius}")
        lines.append(f"cell_size = {int(cell_size_float) if cell_size_float == int(cell_size_float) else cell_size_float}")
        lines.append(f"ARRAY_A = {a}  # X direction")
        lines.append(f"ARRAY_B = {b}  # Y direction (compression)")
        lines.append(f"ARRAY_C = {c}  # Z direction")
        lines.append("PLATE_GAP = 0.02")
        lines.append("")
        return lines

    def _array_script_unit_cell(self, scaled_coords, cylinders):
        """Unit cell geometry: coordinates, struts, cylinder+sphere build, merge."""
        lines = []
        # Coordinates
        lines.append("# Unit cell coordinates")
        for coord in scaled_coords:
            lines.append(coord)
        lines.append("")

        # Cylinders
        lines.append("# Unit cell struts")
        lines.append("cylinders = [")
        for i, cyl in enumerate(cylinders):
            if i == len(cylinders) - 1:
                lines.append(f"    {cyl}")
            else:
                lines.append(f"    {cyl},")
        lines.append("]")
        lines.append("")

        # Build cylinders + node spheres
        lines.append("model = mdb.models['Model-1']")
        lines.append("assembly = model.rootAssembly")
        lines.append("inst_list = []")
        lines.append("node_points = []")
        lines.append("")
        lines.append("# ==========================================================")
        lines.append("# BUILD UNIT CELL: CYLINDERS + NODE SPHERES")
        lines.append("# ==========================================================")
        lines.append("for i, (start, end) in enumerate(cylinders):")
        lines.append("    start = np.array(start, dtype=float)")
        lines.append("    end   = np.array(end, dtype=float)")
        lines.append("    vec = end - start")
        lines.append("    length = norm(vec)")
        lines.append("    if length < 1e-6:")
        lines.append("        continue")
        lines.append("    direction = vec / length")
        lines.append("")
        lines.append("    node_points.append(tuple(start.tolist()))")
        lines.append("    node_points.append(tuple(end.tolist()))")
        lines.append("")
        lines.append("    sketch = model.ConstrainedSketch(name='circleSketch-%02d' % (i+1), sheetSize=20.0)")
        lines.append("    sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(radius, 0.0))")
        lines.append("")
        lines.append("    part_name = 'Cyl-%02d' % (i+1)")
        lines.append("    if part_name in model.parts.keys():")
        lines.append("        del model.parts[part_name]")
        lines.append("    part = model.Part(name=part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)")
        lines.append("    part.BaseSolidExtrude(sketch=sketch, depth=length)")
        lines.append("")
        lines.append("    inst_name = 'Inst-%02d' % (i+1)")
        lines.append("    assembly.Instance(name=inst_name, part=part, dependent=ON)")
        lines.append("    assembly.translate(instanceList=(inst_name,), vector=tuple(start))")
        lines.append("")
        lines.append("    z_axis = np.array([0.0, 0.0, 1.0])")
        lines.append("    rot_axis = cross(z_axis, direction)")
        lines.append("    dot_product = dot(z_axis, direction)")
        lines.append("")
        lines.append("    if norm(rot_axis) < 1e-6:")
        lines.append("        if dot_product < 0:")
        lines.append("            assembly.rotate(instanceList=(inst_name,),")
        lines.append("                            axisPoint=tuple(start),")
        lines.append("                            axisDirection=(1, 0, 0), angle=180.0)")
        lines.append("    else:")
        lines.append("        if dot_product > 1.0: dot_product = 1.0")
        lines.append("        if dot_product < -1.0: dot_product = -1.0")
        lines.append("        angle = degrees(acos(dot_product))")
        lines.append("        assembly.rotate(instanceList=(inst_name,),")
        lines.append("                        axisPoint=tuple(start),")
        lines.append("                        axisDirection=tuple(rot_axis), angle=angle)")
        lines.append("")
        lines.append("    inst_list.append(assembly.instances[inst_name])")
        lines.append("")
        lines.append("assembly.regenerate()")
        lines.append("")

        # Node spheres
        lines.append("# Node spheres")
        lines.append("uniq_nodes = []")
        lines.append("seen = set()")
        lines.append("for pnt in node_points:")
        lines.append("    key = (round(pnt[0], 6), round(pnt[1], 6), round(pnt[2], 6))")
        lines.append("    if key not in seen:")
        lines.append("        seen.add(key)")
        lines.append("        uniq_nodes.append((float(pnt[0]), float(pnt[1]), float(pnt[2])))")
        lines.append("")
        lines.append("if 'NodeSphere' in model.parts.keys():")
        lines.append("    del model.parts['NodeSphere']")
        lines.append("s_sph = model.ConstrainedSketch(name='sphereSketch', sheetSize=50.0)")
        lines.append("s_sph.setPrimaryObject(option=STANDALONE)")
        lines.append(f"sphere_radius = radius * {Config.SPHERE_RADIUS_RATIO_SCRIPT}")
        lines.append("s_sph.ConstructionLine(point1=(0.0, -sphere_radius*2), point2=(0.0, sphere_radius*2))")
        lines.append("s_sph.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, sphere_radius),")
        lines.append("                       point2=(0.0, -sphere_radius), direction=CLOCKWISE)")
        lines.append("s_sph.Line(point1=(0.0, sphere_radius), point2=(0.0, -sphere_radius))")
        lines.append("sphere_part = model.Part(name='NodeSphere', dimensionality=THREE_D, type=DEFORMABLE_BODY)")
        lines.append("sphere_part.BaseSolidRevolve(sketch=s_sph, angle=360.0, flipRevolveDirection=OFF)")
        lines.append("s_sph.unsetPrimaryObject()")
        lines.append("del model.sketches['sphereSketch']")
        lines.append("")
        lines.append("for k, pnt in enumerate(uniq_nodes):")
        lines.append("    nm = 'NodeSphere-%03d' % (k+1)")
        lines.append("    assembly.Instance(name=nm, part=sphere_part, dependent=ON)")
        lines.append("    assembly.translate(instanceList=(nm,), vector=pnt)")
        lines.append("    inst_list.append(assembly.instances[nm])")
        lines.append("")
        lines.append("assembly.regenerate()")
        lines.append("")

        # Merge unit cell
        lines.append("# Merge unit cell")
        lines.append("if 'MergedStructure' in model.parts.keys():")
        lines.append("    del model.parts['MergedStructure']")
        lines.append("assembly.InstanceFromBooleanMerge(")
        lines.append("    name='MergedStructure',")
        lines.append("    instances=tuple(inst_list),")
        lines.append("    keepIntersections=OFF,")
        lines.append("    originalInstances=DELETE,")
        lines.append("    domain=GEOMETRY")
        lines.append(")")
        lines.append("assembly.regenerate()")
        lines.append("")
        return lines

    def _array_script_array_build(self, a, b, c, merged_name):
        """Build the a*b*c array from unit cells and handle instance naming."""
        lines = []
        lines.append("# ==========================================================")
        lines.append(f"# BUILD {a}x{b}x{c} ARRAY")
        lines.append("# ==========================================================")

        if a == 1 and b == 1 and c == 1:
            # N=1: no array merge needed, use the merged unit cell directly
            lines.append("if ARRAY_A == 1 and ARRAY_B == 1 and ARRAY_C == 1:")
            lines.append("    # N=1: no array merge needed, use the merged unit cell directly")
            lines.append("    ARR_PART_NAME = 'MergedStructure'")
            lines.append("    ARR_INST_NAME = 'MergedStructure-1'")
            lines.append("else:")
            lines.append("    uc_part = model.parts['MergedStructure']")
            lines.append("    array_instances = []")
            lines.append("")
            lines.append("    for ix in range(ARRAY_A):")
            lines.append("        for iy in range(ARRAY_B):")
            lines.append("            for iz in range(ARRAY_C):")
            lines.append("                dx = (ix - (ARRAY_A - 1) / 2.0) * cell_size")
            lines.append("                dy = (iy - (ARRAY_B - 1) / 2.0) * cell_size")
            lines.append("                dz = (iz - (ARRAY_C - 1) / 2.0) * cell_size")
            lines.append("                nm = 'UC-%d-%d-%d' % (ix, iy, iz)")
            lines.append("                assembly.Instance(name=nm, part=uc_part, dependent=ON)")
            lines.append("                assembly.translate(instanceList=(nm,), vector=(dx, dy, dz))")
            lines.append("                array_instances.append(assembly.instances[nm])")
            lines.append("")
            lines.append(f"    merged3 = assembly.InstanceFromBooleanMerge(")
            lines.append(f"        name='{merged_name}',")
            lines.append("        instances=tuple(array_instances),")
            lines.append("        keepIntersections=OFF,")
            lines.append("        originalInstances=DELETE,")
            lines.append("        domain=GEOMETRY")
            lines.append("    )")
            lines.append("    assembly.regenerate()")
            lines.append("")
            lines.append("    try:")
            lines.append("        ARR_INST_NAME = merged3.name")
            lines.append("    except:")
            lines.append(f"        ARR_INST_NAME = '{merged_name}-1'")
            lines.append("    try:")
            lines.append("        ARR_PART_NAME = merged3.partName")
            lines.append("    except:")
            lines.append("        try:")
            lines.append("            ARR_PART_NAME = merged3.part.name")
            lines.append("        except:")
            lines.append(f"            ARR_PART_NAME = '{merged_name}'")
            lines.append("")
            lines.append(f"    if ARR_INST_NAME != '{merged_name}-1':")
            lines.append(f"        if '{merged_name}-1' not in assembly.instances.keys():")
            lines.append(f"            assembly.instances.changeKey(fromName=ARR_INST_NAME, toName='{merged_name}-1')")
            lines.append(f"        ARR_INST_NAME = '{merged_name}-1'")
            lines.append("")
            lines.append("    assembly.regenerate()")
        else:
            lines.append("uc_part = model.parts['MergedStructure']")
            lines.append("array_instances = []")
            lines.append("")
            lines.append("for ix in range(ARRAY_A):")
            lines.append("    for iy in range(ARRAY_B):")
            lines.append("        for iz in range(ARRAY_C):")
            lines.append("            dx = (ix - (ARRAY_A - 1) / 2.0) * cell_size")
            lines.append("            dy = (iy - (ARRAY_B - 1) / 2.0) * cell_size")
            lines.append("            dz = (iz - (ARRAY_C - 1) / 2.0) * cell_size")
            lines.append("            nm = 'UC-%d-%d-%d' % (ix, iy, iz)")
            lines.append("            assembly.Instance(name=nm, part=uc_part, dependent=ON)")
            lines.append("            assembly.translate(instanceList=(nm,), vector=(dx, dy, dz))")
            lines.append("            array_instances.append(assembly.instances[nm])")
            lines.append("")
            lines.append(f"merged3 = assembly.InstanceFromBooleanMerge(")
            lines.append(f"    name='{merged_name}',")
            lines.append("    instances=tuple(array_instances),")
            lines.append("    keepIntersections=OFF,")
            lines.append("    originalInstances=DELETE,")
            lines.append("    domain=GEOMETRY")
            lines.append(")")
            lines.append("assembly.regenerate()")
            lines.append("")

            # Instance name handling (robust try/except pattern from BCC.py)
            lines.append("try:")
            lines.append("    ARR_INST_NAME = merged3.name")
            lines.append("except:")
            lines.append(f"    ARR_INST_NAME = '{merged_name}-1'")
            lines.append("try:")
            lines.append("    ARR_PART_NAME = merged3.partName")
            lines.append("except:")
            lines.append("    try:")
            lines.append("        ARR_PART_NAME = merged3.part.name")
            lines.append("    except:")
            lines.append(f"        ARR_PART_NAME = '{merged_name}'")
            lines.append("")
            lines.append(f"if ARR_INST_NAME != '{merged_name}-1':")
            lines.append(f"    if '{merged_name}-1' not in assembly.instances.keys():")
            lines.append(f"        assembly.instances.changeKey(fromName=ARR_INST_NAME, toName='{merged_name}-1')")
            lines.append(f"    ARR_INST_NAME = '{merged_name}-1'")
            lines.append("")
            lines.append("assembly.regenerate()")

        lines.append("")

        # Y extents detection (always runs)
        lines.append("inst3 = assembly.instances[ARR_INST_NAME]")
        lines.append("y_vals = [v.pointOn[0][1] for v in inst3.vertices]")
        lines.append("Y_MIN = min(y_vals)")
        lines.append("Y_MAX = max(y_vals)")
        lines.append('print("TRUE LATTICE Y EXTENTS: Y_MIN=%.6f Y_MAX=%.6f" % (Y_MIN, Y_MAX))')
        lines.append("")
        return lines

    @staticmethod
    def _array_script_cutting():
        """Cut the merged array structure to create flat top/bottom/side surfaces.

        Mirrors the cutting logic from the N=1 Static_model.py template.
        After cutting, the structure has flat faces at the bounding box boundaries
        (±half_x, ±half_y, ±half_z), enabling reliable Tie constraint creation
        via face normal detection.
        """
        lines = []
        lines.append("# ==========================================================")
        lines.append("# CUTTING: trim protrusions to create flat surfaces")
        lines.append("# ==========================================================")
        lines.append("p_cut = model.parts[ARR_PART_NAME]")
        lines.append("")
        lines.append("half_x = ARRAY_A * cell_size / 2.0")
        lines.append("half_y = ARRAY_B * cell_size / 2.0")
        lines.append("half_z = ARRAY_C * cell_size / 2.0")
        lines.append("cut_margin = 2.0 * radius")
        lines.append("")

        # Datum axes (reusable for both cuts)
        lines.append("da_y = p_cut.DatumAxisByPrincipalAxis(principalAxis=YAXIS)")
        lines.append("da_x = p_cut.DatumAxisByPrincipalAxis(principalAxis=XAXIS)")
        lines.append("")

        # --- Cut 1: XYPLANE (Z direction) ---
        # Sketch lives in XY plane; ring removes material outside [-half_x, half_x] x [-half_y, half_y]
        lines.append("# Cut 1: Z direction (XYPLANE) — trims X & Y protrusions")
        lines.append("cut_z_offset = half_z + cut_margin")
        lines.append("cut_z_depth  = 2.0 * cut_z_offset")
        lines.append("dp_z = p_cut.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE, offset=cut_z_offset)")
        lines.append("")
        lines.append("t1 = p_cut.MakeSketchTransform(sketchPlane=p_cut.datums[dp_z.id],")
        lines.append("    sketchUpEdge=p_cut.datums[da_y.id],")
        lines.append("    sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,")
        lines.append("    origin=(0.0, 0.0, half_z))")
        lines.append("s1 = model.ConstrainedSketch(name='cutZSketch', sheetSize=200.0, transform=t1)")
        lines.append("s1.setPrimaryObject(option=SUPERIMPOSE)")
        lines.append("p_cut.projectReferencesOntoSketch(sketch=s1, filter=COPLANAR_EDGES)")
        lines.append("s1.rectangle(point1=(-half_x, -half_y), point2=(half_x, half_y))")
        lines.append("outer = max(half_x, half_y) + 10.0")
        lines.append("s1.rectangle(point1=(-outer, -outer), point2=(outer, outer))")
        lines.append("p_cut.CutExtrude(sketchPlane=p_cut.datums[dp_z.id],")
        lines.append("    sketchUpEdge=p_cut.datums[da_y.id],")
        lines.append("    sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,")
        lines.append("    sketch=s1, depth=cut_z_depth, flipExtrudeDirection=OFF)")
        lines.append("s1.unsetPrimaryObject()")
        lines.append("del model.sketches['cutZSketch']")
        lines.append("")

        # --- Cut 2: XZPLANE (Y direction) ---
        # Sketch lives in XZ plane; ring removes material outside [-half_x, half_x] x [-half_z, half_z]
        # This is the critical cut for creating flat top/bottom faces for Tie constraints
        lines.append("# Cut 2: Y direction (XZPLANE) — creates flat top/bottom for Tie")
        lines.append("cut_y_offset = half_y + cut_margin")
        lines.append("cut_y_depth  = 2.0 * cut_y_offset")
        lines.append("dp_y = p_cut.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=cut_y_offset)")
        lines.append("")
        lines.append("t2 = p_cut.MakeSketchTransform(sketchPlane=p_cut.datums[dp_y.id],")
        lines.append("    sketchUpEdge=p_cut.datums[da_x.id],")
        lines.append("    sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,")
        lines.append("    origin=(0.0, half_y, 0.0))")
        lines.append("s2 = model.ConstrainedSketch(name='cutYSketch', sheetSize=200.0, transform=t2)")
        lines.append("s2.setPrimaryObject(option=SUPERIMPOSE)")
        lines.append("p_cut.projectReferencesOntoSketch(sketch=s2, filter=COPLANAR_EDGES)")
        lines.append("s2.rectangle(point1=(-half_x, -half_z), point2=(half_x, half_z))")
        lines.append("outer2 = max(half_x, half_z) + 10.0")
        lines.append("s2.rectangle(point1=(-outer2, -outer2), point2=(outer2, outer2))")
        lines.append("p_cut.CutExtrude(sketchPlane=p_cut.datums[dp_y.id],")
        lines.append("    sketchUpEdge=p_cut.datums[da_x.id],")
        lines.append("    sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,")
        lines.append("    sketch=s2, depth=cut_y_depth, flipExtrudeDirection=OFF)")
        lines.append("s2.unsetPrimaryObject()")
        lines.append("del model.sketches['cutYSketch']")
        lines.append("")

        # After cutting, update Y extents to the exact cut boundaries
        lines.append("# Update Y extents after cutting (now exact, no protrusions)")
        lines.append("Y_MIN = -half_y")
        lines.append("Y_MAX =  half_y")
        lines.append('print("After cutting: Y_MIN=%.4f  Y_MAX=%.4f" % (Y_MIN, Y_MAX))')
        lines.append("")
        lines.append("assembly.regenerate()")
        lines.append('print("Cutting completed: flat top/bottom surfaces created for Tie constraints")')
        lines.append("")
        return lines

    @staticmethod
    def _array_script_plates():
        """Rigid plates section."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# RIGID PLATES")
        lines.append("# ==========================================================")
        lines.append("plate_half = max(ARRAY_A, ARRAY_C) * cell_size / 2.0 + 1.0")
        lines.append("")
        lines.append("s3 = model.ConstrainedSketch(name='rigidPlateSketch', sheetSize=50.0)")
        lines.append("s3.setPrimaryObject(option=STANDALONE)")
        lines.append("s3.Line(point1=(-plate_half, 0.0), point2=(plate_half, 0.0))")
        lines.append("s3.HorizontalConstraint(entity=s3.geometry[2], addUndoState=False)")
        lines.append("")
        lines.append("if 'RigidPlate' in model.parts.keys():")
        lines.append("    del model.parts['RigidPlate']")
        lines.append("rigid_part = model.Part(name='RigidPlate', dimensionality=THREE_D, type=DISCRETE_RIGID_SURFACE)")
        lines.append("rigid_part.BaseShellExtrude(sketch=s3, depth=2.0 * plate_half)")
        lines.append("s3.unsetPrimaryObject()")
        lines.append("del model.sketches['rigidPlateSketch']")
        lines.append("")
        lines.append("assembly.DatumCsysByDefault(CARTESIAN)")
        lines.append("assembly.Instance(name='RigidPlate-1', part=rigid_part, dependent=ON)")
        lines.append("assembly.translate(instanceList=('RigidPlate-1',), vector=(0.0, Y_MIN - PLATE_GAP, -plate_half))")
        lines.append("assembly.Instance(name='RigidPlate-2', part=rigid_part, dependent=ON)")
        lines.append("assembly.translate(instanceList=('RigidPlate-2',), vector=(0.0, Y_MAX + PLATE_GAP, -plate_half))")
        lines.append("assembly.regenerate()")
        lines.append("")
        return lines

    @staticmethod
    def _array_script_material():
        """Material definition section."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# MATERIAL")
        lines.append("# ==========================================================")
        # ----------------------------------------------------------------
        # MATERIAL CARD — NS3 plastic + 校准 E
        #   E = 1010 (NS3 ×0.65 — 校准实验 compliance / 延长弹性段)
        #   σ_y0=33.97, σ_ult=56.80 (NS3 unchanged)
        # 同步位置: model/Static_model.py, model/Dynamic_model.py
        # ----------------------------------------------------------------
        lines.append("material_obj = model.Material(name='Material-1')")
        lines.append("material_obj.Density(table=((1.01e-09,),))")
        lines.append("material_obj.Elastic(table=((1010, 0.3),))")
        lines.append("material_obj.Plastic(table=(")
        lines.append("    (33.97, 0.0),(36.71, 0.0014),(39.03, 0.0040),(41.13, 0.0071),")
        lines.append("    (43.36, 0.0115),(45.09, 0.0162),(46.48, 0.0218),(47.74, 0.0279),")
        lines.append("    (49.00, 0.0357),(50.21, 0.0456),(51.47, 0.0569),(52.48, 0.0718),")
        lines.append("    (53.86, 0.0830),(55.07, 0.1041),(55.98, 0.1227),(56.31, 0.1376),")
        lines.append("    (56.64, 0.1534),(56.80, 0.1633),")
        lines.append("))")
        lines.append("material_obj.DuctileDamageInitiation(table=(")
        lines.append("    (0.60, -0.333, 0.033),(0.40, 0.0, 0.033),(0.25, 0.333, 0.033),")
        lines.append("))")
        lines.append("material_obj.ductileDamageInitiation.DamageEvolution(type=DISPLACEMENT, table=((0.5,),))")
        lines.append("")
        return lines

    @staticmethod
    def _array_script_sections(merged_name):
        """Section assignments for the merged structure and rigid plate."""
        lines = []
        lines.append("model.HomogeneousSolidSection(name='Section-1', material='Material-1', thickness=None)")
        lines.append("model.HomogeneousShellSection(name='Section-2',")
        lines.append("    preIntegrate=OFF, material='Material-1',")
        lines.append("    thicknessType=UNIFORM, thickness=0.05,")
        lines.append("    thicknessField='', nodalThicknessField='',")
        lines.append("    idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,")
        lines.append("    thicknessModulus=None, temperature=GRADIENT,")
        lines.append("    useDensity=OFF, integrationRule=SIMPSON, numIntPts=5)")
        lines.append("")
        lines.append("rigid_part = model.parts['RigidPlate']")
        lines.append("region = regionToolset.Region(faces=rigid_part.faces[:])")
        lines.append("rigid_part.SectionAssignment(region=region, sectionName='Section-2',")
        lines.append("    offset=0.0, offsetType=MIDDLE_SURFACE,")
        lines.append("    offsetField='', thicknessAssignment=FROM_SECTION)")
        lines.append("")
        lines.append("main_part = model.parts[ARR_PART_NAME]")
        lines.append("c = main_part.cells")
        lines.append("if len(c) == 0:")
        lines.append('    raise RuntimeError("ERROR: %s has 0 solid cells." % ARR_PART_NAME)')
        lines.append("region = regionToolset.Region(cells=c[:])")
        lines.append("main_part.SectionAssignment(region=region, sectionName='Section-1',")
        lines.append("    offset=0.0, offsetType=MIDDLE_SURFACE,")
        lines.append("    offsetField='', thicknessAssignment=FROM_SECTION)")
        lines.append("")
        lines.append("assembly.regenerate()")
        lines.append('print("Model creation completed successfully!")')
        lines.append("")
        return lines

    def _array_script_macro(self, is_shear, is_dynamic, compress_disp, time_period, velocity_num, plate_half=8.5):
        """Macro1 containing step, BC, contact, rigid body constraints, and mesh."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# MACRO1")
        lines.append("# ==========================================================")
        lines.append("import section")
        lines.append("import displayGroupMdbToolset as dgm")
        lines.append("import part")
        lines.append("import material as material_module")
        lines.append("import assembly as assembly_module")
        lines.append("import step")
        lines.append("import interaction")
        lines.append("import load")
        lines.append("import mesh")
        lines.append("import optimization")
        lines.append("import job")
        lines.append("import sketch")
        lines.append("import visualization")
        lines.append("import xyPlot")
        lines.append("import displayGroupOdbToolset as dgo")
        lines.append("import connectorBehavior")
        lines.append("")
        lines.append("")
        lines.append("def Macro1():")
        lines.append("    p = mdb.models['Model-1'].parts['RigidPlate']")
        lines.append("    v = p.vertices")
        lines.append("    p.ReferencePoint(point=v[0])")
        lines.append("    r = p.referencePoints")
        lines.append("    rp_key = list(r.keys())[-1]")
        lines.append("    refPoints = (r[rp_key], )")
        lines.append("    region = p.Set(referencePoints=refPoints, name='RefPlateSet')")
        # 刚性板质量按面积缩放: 基准 4.375mm 板 = 8.45e-07 tonne
        base_plate_size = 4.375
        base_mass = 8.45e-07
        plate_size = 2.0 * plate_half
        scaled_mass = base_mass * (plate_size / base_plate_size) ** 2
        lines.append("    p.engineeringFeatures.PointMassInertia(")
        lines.append(f"        name='Inertia-1', region=region, mass={scaled_mass:.6e}, alpha=0.0, composite=0.0)")
        lines.append("")
        lines.append("    a = mdb.models['Model-1'].rootAssembly")
        lines.append("    a.regenerate()")
        lines.append("")

        # Step definition
        lines.append("    mdb.models['Model-1'].ExplicitDynamicsStep(")
        lines.append(f"        name='Step-1', previous='Initial', timePeriod={time_period},")
        lines.append("        massScaling=((SEMI_AUTOMATIC, MODEL, THROUGHOUT_STEP, 0.0, 5e-06, BELOW_MIN, 1, 0, 0.0, 0.0, 0, None), ),")
        lines.append("        improvedDtMethod=ON, nlgeom=ON,")
        # Bulk viscosity = NS3 (0.25, 2.0). Tried Abaqus default (0.06, 1.2) on 2026-05-02:
        # impact on σ-ε <2% (BCC<0.5%, Aux ε=0.05 -5.6% only), but wall time 2-5×.
        # Lit recommends defaults but real impact is negligible for quasi-static + mass scaling.
        lines.append("        linearBulkViscosity=0.25, quadBulkViscosity=2.0)")
        lines.append("")
        lines.append("    mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(")
        lines.append("        variables=('S', 'E', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF', 'CSTRESS', 'CDISP', 'STATUS'),")
        lines.append("        numIntervals=100)")
        lines.append("")

        # Reference points and history output
        lines.append("    def _get_first_rp(instName):")
        lines.append("        rpDict = a.instances[instName].referencePoints")
        lines.append("        return list(rpDict.values())[0]")
        lines.append("")
        lines.append("    rp_bot = _get_first_rp('RigidPlate-1')")
        lines.append("    rp_top = _get_first_rp('RigidPlate-2')")
        lines.append("    a.Set(referencePoints=(rp_bot,), name='BotReflection')")
        lines.append("    a.Set(referencePoints=(rp_top,), name='TopReflection')")
        lines.append("")
        lines.append("    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-2',")
        lines.append("        createStepName='Step-1', variables=('U1', 'U2', 'RF1', 'RF2'),")
        lines.append("        region=a.sets['TopReflection'], sectionPoints=DEFAULT, rebar=EXCLUDE)")
        lines.append("")

        # Rigid body constraints
        lines.append("    mdb.models['Model-1'].RigidBody(name='Constraint-1',")
        lines.append("        refPointRegion=regionToolset.Region(referencePoints=(rp_top,)),")
        lines.append("        bodyRegion=a.sets['TopReflection'])")
        lines.append("    mdb.models['Model-1'].RigidBody(name='Constraint-2',")
        lines.append("        refPointRegion=regionToolset.Region(referencePoints=(rp_bot,)),")
        lines.append("        bodyRegion=a.sets['BotReflection'])")
        lines.append("")

        # Contact property
        lines.append("    mdb.models['Model-1'].ContactProperty('IntProp-1')")
        lines.append("    mdb.models['Model-1'].interactionProperties['IntProp-1'].TangentialBehavior(")
        lines.append("        formulation=PENALTY, directionality=ISOTROPIC, slipRateDependency=OFF,")
        lines.append("        pressureDependency=OFF, temperatureDependency=OFF, dependencies=0,")
        # 摩擦系数恢复 NS3 原值 0.15
        lines.append("        table=((0.15, ), ), shearStressLimit=None, maximumElasticSlip=FRACTION,")
        lines.append("        fraction=0.005, elasticSlipStiffness=None)")
        # NormalBehavior: HARD contact + scale=5.0
        # 锁定 5.0 跨所有 N — 文献依据: Lee&Kajtaz 2022, Park 2022, Khan 2022 (PA12 lattice
        # Abaqus/Explicit 默认 HARD + penalty)。N=2/3 用 1.0 虽更软, 但跨 N 趋势分析必须参数统一。
        lines.append("    mdb.models['Model-1'].interactionProperties['IntProp-1'].NormalBehavior(")
        lines.append("        pressureOverclosure=HARD, allowSeparation=ON,")
        lines.append("        contactStiffnessScaleFactor=5.0)")
        # ContactDamping (NS3 设置): 耗散 buckling 事件触发的高频振荡，
        # 防止 BCCZ 类拓扑在屈曲时出现穿透。
        lines.append("    mdb.models['Model-1'].interactionProperties['IntProp-1'].Damping(")
        lines.append("        definition=DAMPING_COEFFICIENT, tangentFraction=DEFAULT,")
        lines.append("        clearanceDependence=STEP, table=((0.1, ),))")
        lines.append("")

        # Surface-to-surface contacts
        lines.append("    region1 = a.Surface(side1Faces=a.instances['RigidPlate-2'].faces[:], name='m_Surf-1')")
        lines.append("    f_lat = a.instances[ARR_INST_NAME].faces")
        lines.append("    top_faces = f_lat.getByBoundingBox(xMin=-1e9, xMax=1e9,")
        lines.append("        yMin=Y_MAX - 0.30, yMax=Y_MAX + 0.30, zMin=-1e9, zMax=1e9)")
        lines.append("    region2 = a.Surface(side1Faces=top_faces, name='s_Surf-1')")
        lines.append("    mdb.models['Model-1'].SurfaceToSurfaceContactExp(name='Int-1',")
        lines.append("        createStepName='Step-1', main=region1, secondary=region2,")
        lines.append("        sliding=FINITE, interactionProperty='IntProp-1')")
        lines.append("")
        lines.append("    region1 = a.Surface(side1Faces=a.instances['RigidPlate-1'].faces[:], name='m_Surf-3')")
        lines.append("    bot_faces = f_lat.getByBoundingBox(xMin=-1e9, xMax=1e9,")
        lines.append("        yMin=Y_MIN - 0.30, yMax=Y_MIN + 0.30, zMin=-1e9, zMax=1e9)")
        lines.append("    region2 = a.Surface(side1Faces=bot_faces, name='s_Surf-3')")
        lines.append("    mdb.models['Model-1'].SurfaceToSurfaceContactExp(name='Int-2',")
        lines.append("        createStepName='Step-1', main=region1, secondary=region2,")
        lines.append("        sliding=FINITE, interactionProperty='IntProp-1')")
        lines.append("")
        lines.append("    mdb.models['Model-1'].interactions['Int-1'].move('Step-1', 'Initial')")
        lines.append("    mdb.models['Model-1'].interactions['Int-2'].move('Step-1', 'Initial')")
        lines.append("")

        # Boundary conditions
        lines.append("    mdb.models['Model-1'].EncastreBC(name='BC-1', createStepName='Initial',")
        lines.append("        region=a.sets['BotReflection'], localCsys=None)")
        lines.append("")

        if is_dynamic:
            vel_num = float(velocity_num) if velocity_num is not None else 500.0

            if is_shear:
                lines.append(f"    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',")
                lines.append("        region=a.sets['TopReflection'],")
                lines.append("        u1=UNSET, u2=0.0, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,")
                lines.append("        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',")
                lines.append("        localCsys=None)")
                lines.append(f"    mdb.models['Model-1'].Velocity(name='Predefined Field-1',")
                lines.append(f"        region=a.sets['TopReflection'],")
                lines.append(f"        velocity1=-{vel_num}, velocity2=0.0, velocity3=0.0,")
                lines.append(f"        omega=0.0)")
            else:
                lines.append(f"    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',")
                lines.append("        region=a.sets['TopReflection'],")
                lines.append("        u1=0.0, u2=UNSET, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,")
                lines.append("        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',")
                lines.append("        localCsys=None)")
                lines.append(f"    mdb.models['Model-1'].Velocity(name='Predefined Field-1',")
                lines.append(f"        region=a.sets['TopReflection'],")
                lines.append(f"        velocity1=0.0, velocity2=-{vel_num}, velocity3=0.0,")
                lines.append(f"        omega=0.0)")
        else:
            if is_shear:
                lines.append(f"    u1 = {compress_disp}")
                lines.append("    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',")
                lines.append("        region=a.sets['TopReflection'],")
                lines.append("        u1=u1, u2=0.0, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,")
                lines.append("        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',")
                lines.append("        localCsys=None)")
            else:
                lines.append(f"    u2 = {compress_disp}")
                lines.append("    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',")
                lines.append("        region=a.sets['TopReflection'],")
                lines.append("        u1=0.0, u2=u2, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,")
                lines.append("        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',")
                lines.append("        localCsys=None)")

            lines.append(f"    mdb.models['Model-1'].SmoothStepAmplitude(name='Amp-1', timeSpan=STEP,")
            lines.append(f"        data=((0.0, 0.0), ({time_period}, 1.0)))")
            lines.append("    mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(")
            lines.append("        stepName='Step-1', amplitude='Amp-1')")

        lines.append("")

        # Update rigid body constraints with face sets
        lines.append("    a_rb = mdb.models['Model-1'].rootAssembly")
        lines.append("    f1 = a_rb.instances['RigidPlate-2'].faces")
        lines.append("    region2 = a_rb.Set(faces=f1[:], name='b_Set-8')")
        lines.append("    rp_top2 = _get_first_rp('RigidPlate-2')")
        lines.append("    region1 = regionToolset.Region(referencePoints=(rp_top2,))")
        lines.append("    mdb.models['Model-1'].constraints['Constraint-1'].setValues(")
        lines.append("        refPointRegion=region1, bodyRegion=region2)")
        lines.append("")
        lines.append("    f1 = a_rb.instances['RigidPlate-1'].faces")
        lines.append("    region2 = a_rb.Set(faces=f1[:], name='b_Set-9')")
        lines.append("    rp_bot2 = _get_first_rp('RigidPlate-1')")
        lines.append("    region1 = regionToolset.Region(referencePoints=(rp_bot2,))")
        lines.append("    mdb.models['Model-1'].constraints['Constraint-2'].setValues(")
        lines.append("        refPointRegion=region1, bodyRegion=region2)")
        lines.append("")
        lines.append("    a.regenerate()")

        # Mesh
        lines.append("    p = mdb.models['Model-1'].parts[ARR_PART_NAME]")
        lines.append("    c = p.cells")
        lines.append("    p.setMeshControls(regions=c[:], elemShape=TET, technique=FREE)")
        lines.append("    # distortionControl=ON with lengthRatio=0.1: prevent element inversion")
        lines.append("    # when elements compress below 10% of original size (densification regime).")
        lines.append("    # Avoids CFL violation crash without affecting elastic/plateau response.")
        lines.append("    # element deletion: enabled by default when damage model is defined.")
        lines.append("    elemType1 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,")
        lines.append("        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)")
        lines.append("    elemType2 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,")
        lines.append("        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)")
        lines.append("    elemType3 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,")
        lines.append("        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)")
        lines.append("    p.setElementType(regions=(c[:],), elemTypes=(elemType1, elemType2, elemType3))")
        lines.append("")
        lines.append("    mesh_size_structure = 0.3 * math.sqrt(radius / 0.5) * (cell_size / 5.0)")
        lines.append("    mesh_size_plate = 0.5 * (radius / 0.5) * (cell_size / 5.0)")
        lines.append("    p.seedPart(size=mesh_size_structure, deviationFactor=0.1, minSizeFactor=0.1)")
        lines.append("    p.generateMesh()")
        lines.append("")
        lines.append("    p2 = mdb.models['Model-1'].parts['RigidPlate']")
        lines.append("    p2.seedPart(size=mesh_size_plate, deviationFactor=0.1, minSizeFactor=0.1)")
        lines.append("    p2.generateMesh()")
        lines.append("")
        lines.append("")
        lines.append("Macro1()")
        lines.append("")
        return lines

    @staticmethod
    def _array_script_tie(merged_name):
        """Tie constraints section."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# TIE CONSTRAINTS")
        lines.append("# ==========================================================")
        lines.append('print("\\n========== Creating Tie Constraints ==========")')
        lines.append("a = mdb.models['Model-1'].rootAssembly")
        lines.append("instance = a.instances[ARR_INST_NAME]")
        lines.append("faces = instance.faces")
        lines.append("")
        lines.append("bottom_face_objects = []")
        lines.append("for face in faces:")
        lines.append("    try:")
        lines.append("        normal = face.getNormal()")
        lines.append("        if abs(normal[0]) < 0.01 and abs(normal[1] + 1.0) < 0.01 and abs(normal[2]) < 0.01:")
        lines.append("            bottom_face_objects.append(face)")
        lines.append("    except:")
        lines.append("        pass")
        lines.append("")
        lines.append('print("Found %d bottom faces" % len(bottom_face_objects))')
        lines.append("if bottom_face_objects:")
        lines.append("    s1 = a.instances['RigidPlate-1'].faces")
        lines.append("    region1 = regionToolset.Region(side2Faces=s1[:])")
        lines.append("    s1_struct = a.instances[ARR_INST_NAME].faces")
        lines.append("    found_faces = []")
        lines.append("    for face in bottom_face_objects:")
        lines.append("        found_faces.append(s1_struct.findAt((face.pointOn[0],)))")
        lines.append("    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-BottomTie')")
        lines.append("    mdb.models['Model-1'].Tie(name='Constraint-3', main=region1, secondary=region2,")
        lines.append("        positionToleranceMethod=COMPUTED, adjust=ON, tieRotations=ON, thickness=ON)")
        lines.append('    print("SUCCESS: Bottom Tie created")')
        lines.append("")
        lines.append("top_face_objects = []")
        lines.append("for face in faces:")
        lines.append("    try:")
        lines.append("        normal = face.getNormal()")
        lines.append("        if abs(normal[0]) < 0.01 and abs(normal[1] - 1.0) < 0.01 and abs(normal[2]) < 0.01:")
        lines.append("            top_face_objects.append(face)")
        lines.append("    except:")
        lines.append("        pass")
        lines.append("")
        lines.append('print("Found %d top faces" % len(top_face_objects))')
        lines.append("if top_face_objects:")
        lines.append("    s1 = a.instances['RigidPlate-2'].faces")
        lines.append("    region1 = regionToolset.Region(side2Faces=s1[:])")
        lines.append("    s1_struct = a.instances[ARR_INST_NAME].faces")
        lines.append("    found_faces = []")
        lines.append("    for face in top_face_objects:")
        lines.append("        found_faces.append(s1_struct.findAt((face.pointOn[0],)))")
        lines.append("    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-TopTie')")
        lines.append("    mdb.models['Model-1'].Tie(name='Constraint-4', main=region1, secondary=region2,")
        lines.append("        positionToleranceMethod=COMPUTED, adjust=ON, tieRotations=ON, thickness=ON)")
        lines.append('    print("SUCCESS: Top Tie created")')
        lines.append("")
        lines.append('print("=" * 50)')
        lines.append("")
        return lines

    @staticmethod
    def _array_script_contact():
        """General contact section (replaces surface-to-surface contacts)."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# GENERAL CONTACT")
        lines.append("# ==========================================================")
        lines.append('print("\\n========== Creating General Contact ==========")')
        lines.append("try:")
        lines.append("    if 'Int-1' in mdb.models['Model-1'].interactions.keys():")
        lines.append("        del mdb.models['Model-1'].interactions['Int-1']")
        lines.append("except:")
        lines.append("    pass")
        lines.append("try:")
        lines.append("    if 'Int-2' in mdb.models['Model-1'].interactions.keys():")
        lines.append("        del mdb.models['Model-1'].interactions['Int-2']")
        lines.append("except:")
        lines.append("    pass")
        lines.append("")
        lines.append("mdb.models['Model-1'].ContactExp(name='GeneralContact', createStepName='Initial')")
        lines.append("mdb.models['Model-1'].interactions['GeneralContact'].includedPairs.setValuesInStep(")
        lines.append("    stepName='Initial', useAllstar=ON)")
        lines.append("mdb.models['Model-1'].interactions['GeneralContact'].contactPropertyAssignments.appendInStep(")
        lines.append("    stepName='Initial', assignments=((GLOBAL, SELF, 'IntProp-1'), ))")
        lines.append('print("SUCCESS: General Contact created")')
        lines.append('print("=" * 50)')
        lines.append("")
        return lines

    @staticmethod
    def _array_script_job(job_name, merged_name, array_volume, output_dir):
        """Job definition, density calculation, and input file generation."""
        lines = []
        lines.append("# ==========================================================")
        lines.append("# JOB")
        lines.append("# ==========================================================")
        lines.append("mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(frequency=3)")
        lines.append("")
        lines.append(f"JOB_NAME = '{job_name}'")
        lines.append("")
        lines.append(f"os.chdir(r\"{output_dir}\")")
        lines.append("")
        lines.append("mdb.Job(name=JOB_NAME, model='Model-1', description='', type=ANALYSIS,")
        lines.append("    atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90,")
        lines.append("    memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,")
        lines.append("    explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=ON,")
        lines.append("    modelPrint=ON, contactPrint=ON, historyPrint=ON, userSubroutine='',")
        lines.append("    scratch='', resultsFormat=ODB, numThreadsPerMpiProcess=0, numCpus=8,")
        lines.append("    numDomains=8, numGPUs=0)")
        lines.append("")
        lines.append("try:")
        lines.append("    part = mdb.models['Model-1'].parts[ARR_PART_NAME]")
        lines.append("    volume = part.getVolume()")
        lines.append(f"    density = volume / ({array_volume})")
        lines.append('    print("Volume = ", volume)')
        lines.append('    print("Relative density = ", density)')
        lines.append("    with open('density_temp.txt', 'w') as f:")
        lines.append("        f.write(str(density))")
        lines.append("except Exception as e:")
        lines.append('    print("Warning: Cannot calculate density: " + str(e))')
        lines.append("    with open('density_temp.txt', 'w') as f:")
        lines.append("        f.write('0.0')")
        lines.append("")
        lines.append('print("Generating input file...")')
        lines.append("mdb.jobs[JOB_NAME].writeInput(consistencyChecking=OFF)")
        lines.append("print(\"Input file '%s.inp' generated successfully.\" % JOB_NAME)")
        lines.append("")

        # INP patch: inject SC-Solid section controls with element deletion
        lines.append("# ==========================================================")
        lines.append("# PATCH: inject SC-Solid section controls with element deletion")
        lines.append("# (ductile damage >=95% -> remove element) to prevent Explicit")
        lines.append("# from collapsing dt to 1e-14 in densification regime. The CAE")
        lines.append("# Python API does not expose a controls kwarg on")
        lines.append("# SectionAssignment, so we post-edit the .inp directly.")
        lines.append("# ==========================================================")
        lines.append("import re as _re_patch")
        lines.append('_inp_patch = JOB_NAME + ".inp"')
        lines.append('with open(_inp_patch, "r") as _fp:')
        lines.append("    _c_patch = _fp.read()")
        lines.append('_sc_def = ("*Section Controls, name=SC-Solid, element deletion=YES, "')
        lines.append('           "max degradation=0.95\\n1., 1., 1.\\n")')
        lines.append('if "*Section Controls, name=SC-Solid" not in _c_patch:')
        lines.append('    _c_patch = _c_patch.replace("*Step", _sc_def + "*Step", 1)')
        lines.append("_c_patch = _re_patch.sub(")
        lines.append('    r"\\*Solid Section, (elset=[^,]+), material=Material-1",')
        lines.append('    r"*Solid Section, \\1, controls=SC-Solid, material=Material-1",')
        lines.append("    _c_patch)")
        lines.append('with open(_inp_patch, "w") as _fp:')
        lines.append("    _fp.write(_c_patch)")
        lines.append('print("PATCH: injected SC-Solid section controls into %s" % _inp_patch)')
        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def _generate_array_script(self, structure_data, cell_type, cell_size, cell_radius, slider, mode_type, analysis_type, output_dir, script_filename, lattice_array):
        """生成a*b*c阵列的完整ABAQUS Python脚本 (orchestrator)."""
        a, b, c = lattice_array
        cell_size_float = float(cell_size)
        cell_radius_float = float(cell_radius)

        # Derived parameters
        scale_factor = cell_size_float / self.base_cell_size
        scaled_coords = [self._scale_coordinate_line(coord, scale_factor) for coord in structure_data['coords']]
        job_name = os.path.splitext(script_filename)[0]
        merged_name = f'MergedStructure_{a}x{b}x{c}'
        is_shear = (mode_type == "Shear")
        is_dynamic = analysis_type.startswith("Dyna")
        compress_disp = -0.6 * b * cell_size_float

        velocity_num = None
        if is_dynamic:
            if "_Auto" in analysis_type:
                # Auto 模式：从静态 EA 反推速度 (固定 1g 板质量、multiplier 由 generate_script 设置)
                ea_value = self._get_static_energy_absorb(
                    cell_type, cell_size, cell_radius, slider, mode_type
                )
                if ea_value is None:
                    raise ValueError("无法获取静态吸能数据，请先运行对应的静态仿真 (StaCompre/StaShear)")
                multiplier = getattr(self, '_auto_multiplier', 0.8)
                velocity_num = float(self._calculate_velocity_for_auto_mode(
                    ea_value, mass_gram=1.0, multiplier=multiplier
                ))
            else:
                velocity_str = self._extract_velocity_from_analysis_type(analysis_type)
                velocity_num = float(velocity_str) if velocity_str else 500.0
            time_period = 20.0 / velocity_num if velocity_num else 0.01
        else:
            # 恒定应变率: timePeriod = 0.3 * ARRAY_B
            time_period = round(0.3 * b, 10)

        array_volume_total = (a * cell_size_float) * (b * cell_size_float) * (c * cell_size_float)
        plate_half = max(a, c) * cell_size_float / 2.0 + 1.0

        # Assemble script from sub-methods
        lines = []
        lines.extend(self._array_script_header(cell_type, cell_size, cell_radius, a, b, c, analysis_type, time_period=time_period))
        lines.extend(self._array_script_unit_cell(scaled_coords, structure_data['cylinders']))
        lines.extend(self._array_script_array_build(a, b, c, merged_name))
        lines.extend(self._array_script_cutting())
        lines.extend(self._array_script_plates())
        lines.extend(self._array_script_material())
        lines.extend(self._array_script_sections(merged_name))
        lines.extend(self._array_script_macro(is_shear, is_dynamic, compress_disp, time_period, velocity_num, plate_half))
        lines.extend(self._array_script_tie(merged_name))
        lines.extend(self._array_script_contact())
        lines.extend(self._array_script_job(job_name, merged_name, array_volume_total, output_dir))

        return '\n'.join(lines)

    def _generate_pbs_script(self, output_dir, job_name, preprocess_filename, postprocess_filename):
        """生成 per-job PBS 提交脚本 (run.pbs)"""
        from config import Config
        pbs = Config.get_pbs_header()
        ncpus = pbs['ncpus']
        pbs_content = f"""#!/bin/bash
#PBS -N {job_name}
#PBS -P {pbs['project']}
#PBS -q {pbs['queue']}
#PBS -l walltime={Config.PBS_PER_JOB_WALLTIME}
#PBS -l select=1:ncpus={ncpus}:mem={Config.PBS_PER_JOB_MEMORY}
#PBS -j oe
#PBS -o {job_name}.log

module load {Config.ABAQUS_MODULE}
export PYTHONDONTWRITEBYTECODE=1

# ============================================================
# USAGE: Modify JOB_NAME, WORK_DIR below before submitting.
#   qsub run.pbs
# ============================================================
JOB_NAME="{job_name}"
WORK_DIR="{output_dir}"

cd "$WORK_DIR"

echo "=== $JOB_NAME ==="
echo "Start: $(date)"

echo "[1/3] Preprocess — generate .inp"
abaqus cae noGUI="{preprocess_filename}"
if [ $? -ne 0 ]; then
    echo "ERROR: preprocess failed"
    exit 1
fi

echo "[2/3] Solver — run Abaqus Explicit"
abaqus job=$JOB_NAME cpus={ncpus} interactive
if [ $? -ne 0 ]; then
    echo "WARNING: solver exited with error (partial results may exist)"
fi

echo "[3/3] Postprocess — extract force-displacement"
abaqus cae noGUI="{postprocess_filename}"

echo "=== Done: $(date) ==="
"""
        return pbs_content

    def _generate_array_postprocess_script(self, output_dir, cell_size, mode_type, analysis_type, script_filename, lattice_array):
        """生成阵列模式的后处理脚本 (使用阵列感知的归一化参数)

        Args:
            output_dir: 输出目录
            cell_size: 单元尺寸
            mode_type: "Compression" 或 "Shear"
            analysis_type: 分析类型
            script_filename: 脚本文件名
            lattice_array: (a, b, c) 阵列尺寸

        Returns:
            后处理脚本内容字符串
        """
        a, b, c_dim = lattice_array
        cell_size_float = float(cell_size)

        job_name = os.path.splitext(script_filename)[0]

        # 根据 mode_type 决定使用U1还是U2
        if mode_type == "Shear":
            disp_var_name = "U1"
        else:
            disp_var_name = "U2"

        # 应力应变归一化参数 (array-aware)
        # 两种模式共享相同的板几何：Y 方向为板间距、XZ 为板接触面。
        # Shear 沿 X 施加 u1，Compression 沿 Y 施加 u2，但归一化几何相同。
        strain_length = b * cell_size_float                # 板间距 (Y)
        stress_area = a * c_dim * cell_size_float ** 2     # 板接触面积 (X*Z)

        postprocess_content = f"""# -*- coding: utf-8 -*-
# Abaqus post-processing script - Array mode ({a}x{b}x{c_dim})
from abaqus import *
from abaqusConstants import *
import os
import time
import sys

print("="*80)
print("POST-PROCESSING SCRIPT STARTED (ARRAY MODE {a}x{b}x{c_dim})")
print("Strain length (normalization): {strain_length}")
print("Stress area   (normalization): {stress_area}")
print("="*80)

script_dir = os.getcwd()
print("Working directory:", script_dir)

odb_filename = '{job_name}.odb'
lck_filename = '{job_name}.lck'

print("ODB file to process:", odb_filename)
print("Waiting for job completion...")

timeout = 3600
start_time = time.time()
job_status = "unknown"

try:
    while not os.path.exists(odb_filename):
        if time.time() - start_time > timeout:
            print("WARNING: Timeout - ODB file not created after 1 hour")
            job_status = "no_odb"
            break
        time.sleep(10)

    if job_status == "unknown":
        print("ODB file detected, waiting for analysis to complete...")
        while os.path.exists(lck_filename):
            if time.time() - start_time > timeout:
                print("WARNING: Timeout - Job still running after 1 hour")
                job_status = "timeout"
                break
            time.sleep(10)

        if job_status == "unknown":
            print("Analysis completed. Starting post-processing...")
            job_status = "successful"
        time.sleep(2)

except Exception as e:
    print("ERROR during job monitoring: " + str(e))
    job_status = "error"

print("Job status: " + job_status)

from odbAccess import openOdb
import xyPlot

if not os.path.exists(odb_filename):
    raise RuntimeError("ODB file not created - job failed")

if job_status == "timeout":
    extra_wait = 300
    extra_start = time.time()
    while os.path.exists(lck_filename) and (time.time() - extra_start < extra_wait):
        time.sleep(10)

try:
    odb = openOdb(path=odb_filename, readOnly=True)
except Exception as e:
    raise RuntimeError("Cannot open ODB file: " + str(e))

try:
    step = odb.steps['Step-1']
    disp_key = '{disp_var_name}'
    force_key = 'RF2'
    if disp_key == 'U1':
        force_key = 'RF1'

    print("Available history regions:")
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        outputs = region.historyOutputs.keys()
        print("  - " + region_name + " -> " + str(outputs))

    def select_by_max_mean(candidates, output_key, label):
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0][0]
        else:
            max_mean = -1
            selected = None
            for name, reg in candidates:
                data = reg.historyOutputs[output_key].data
                mean_val = sum([abs(d[1]) for d in data]) / len(data) if data else 0
                if mean_val > max_mean:
                    max_mean = mean_val
                    selected = name
            return selected

    disp_candidates = []
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        if 'RIGIDPLATE-2' in region_name.upper():
            if disp_key in region.historyOutputs.keys():
                disp_candidates.append((region_name, region))

    disp_var = select_by_max_mean(disp_candidates, disp_key, "displacement")

    force_candidates = []
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        if 'RIGIDPLATE' in region_name.upper():
            if force_key in region.historyOutputs.keys():
                force_candidates.append((region_name, region))

    force_var = select_by_max_mean(force_candidates, force_key, "force")

    if force_var is None or disp_var is None:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('{job_name}' + "\\n")
            f.write("status: no_outputs\\n")
            f.write("strain_length: {strain_length}\\n")
            f.write("stress_area: {stress_area}\\n")
        raise ValueError("Cannot find required output variables (ODB may be empty from crashed solver)")

    force_region = step.historyRegions[force_var]
    force_data = force_region.historyOutputs[force_key]

    disp_region = step.historyRegions[disp_var]
    disp_data = disp_region.historyOutputs['{disp_var_name}']

    # Validate data arrays are non-empty (solver may have crashed at startup, ODB exists but empty)
    if not force_data.data or len(force_data.data) < 2 or not disp_data.data or len(disp_data.data) < 2:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('{job_name}' + "\\n")
            f.write("status: empty_odb\\n")
            f.write("strain_length: {strain_length}\\n")
            f.write("stress_area: {stress_area}\\n")
            f.write("force_points: " + str(len(force_data.data) if force_data.data else 0) + "\\n")
            f.write("disp_points: " + str(len(disp_data.data) if disp_data.data else 0) + "\\n")
        raise ValueError("ODB contains no time history data (likely solver crash at startup)")

    xy_force = session.XYData('Force', force_data.data)
    xy_disp = session.XYData('Displacement', disp_data.data)

    if xy_force is None or xy_disp is None:
        odb.close()
        with open('feature_data.txt', 'w') as f:
            f.write('{job_name}' + "\\n")
            f.write("status: xydata_failed\\n")
            f.write("strain_length: {strain_length}\\n")
            f.write("stress_area: {stress_area}\\n")
        raise ValueError("session.XYData returned None")

    xy_combined = combine(abs(xy_disp), abs(xy_force))

    os.chdir(r"{output_dir}")

    density = 0.0
    try:
        with open('density_temp.txt', 'r') as f:
            density = float(f.read().strip())
    except:
        density = 0.0

    with open('feature_data.txt', 'w') as f:
        f.write('{job_name}' + "\\n")
        f.write("status: " + job_status + "\\n")
        f.write("density: " + str(density) + "\\n")
        f.write("strain_length: {strain_length}\\n")
        f.write("stress_area: {stress_area}\\n")
        f.write(str(disp_var) + " " + str(force_var))

    session.writeXYReport(fileName='feature_data.txt', xyData=(xy_combined, ), appendMode=ON)
    odb.close()

    print("Post-processing completed successfully!")

except Exception as e:
    print("FATAL ERROR: " + str(e))
    import traceback
    traceback.print_exc()
    raise
"""
        return postprocess_content

    def _generate_filename(self, cell_type, cell_size, cell_radius, slider, mode_type="Compression", analysis_type="StaCompre", lattice_array=(1,1,1)):
        """生成文件名 (小数点替换为p)"""
        # 清理cell_type，移除特殊字符
        clean_cell_type = re.sub(r'[^\w-]', '', cell_type)

        size_str = self._format_param(cell_size)
        radius_str = self._format_param(cell_radius, try_int=False)
        slider_str = self._format_param(slider)

        # 使用 analysis_type 作为后缀
        suffix = f"_{analysis_type}"

        # 添加阵列后缀 (如 _3x3x3)
        array_suffix = ""
        if lattice_array != (1,1,1):
            a, b, c = lattice_array
            array_suffix = f"_{a}x{b}x{c}"

        return f"{clean_cell_type}_{size_str}_{radius_str}_{slider_str}{suffix}{array_suffix}.py"



def generate_abaqus_script(cell_type, cell_size, cell_radius, slider=4, output_dir=None, mode_type="Compression", analysis_type="StaCompre", batch_mode=False, batch_parent_dir=None, lattice_array=(1,1,1), flat_output=False):
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
    - lattice_array: 阵列尺寸元组 (a, b, c)，默认 (1,1,1) 即单个晶胞
    - flat_output: 为True时直接使用output_dir，不添加层级子目录

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

    return generator.generate_script(cell_type, cell_size, cell_radius, slider, output_dir, mode_type, analysis_type, batch_mode, batch_parent_dir, lattice_array=lattice_array, flat_output=flat_output)


if __name__ == "__main__":
    pass