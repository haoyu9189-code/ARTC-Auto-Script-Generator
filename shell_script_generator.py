#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shell脚本生成器 - 重构后的模块化设计
消除sh和bat脚本生成的重复代码

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from config import Config


class BaseScriptGenerator(ABC):
    """脚本生成器基类"""

    def __init__(self, python_files: List[str], output_dir: str,
                 group_number: Optional[int] = None, config_name: Optional[str] = None):
        """
        初始化脚本生成器

        Args:
            python_files: Python脚本文件列表
            output_dir: 输出目录
            group_number: 组号(可选)
            config_name: 配置名称(可选)
        """
        self.python_files = python_files
        self.output_dir = output_dir
        self.group_number = group_number
        self.config_name = config_name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    @abstractmethod
    def get_file_extension(self) -> str:
        """获取脚本文件扩展名"""
        pass

    @abstractmethod
    def generate_header(self) -> List[str]:
        """生成脚本头部"""
        pass

    @abstractmethod
    def generate_script_loop(self) -> List[str]:
        """生成脚本循环体"""
        pass

    @abstractmethod
    def generate_footer(self) -> List[str]:
        """生成脚本尾部"""
        pass

    @abstractmethod
    def write_file(self, content: str, file_path: str):
        """写入文件并设置权限"""
        pass

    def get_script_filename(self) -> str:
        """生成脚本文件名"""
        ext = self.get_file_extension()
        if self.config_name:
            return f"run_all_{self.config_name}.{ext}"
        elif self.group_number:
            return f"run_all_scripts_{self.group_number}_{self.timestamp}.{ext}"
        else:
            return f"run_all_scripts_{self.timestamp}.{ext}"

    def generate(self) -> Optional[str]:
        """
        生成脚本文件

        Returns:
            str: 生成的脚本文件路径，失败返回None
        """
        try:
            script_filename = self.get_script_filename()
            script_path = os.path.join(self.output_dir, script_filename)

            # 生成脚本内容
            content_lines = []
            content_lines.extend(self.generate_header())
            content_lines.extend(self.generate_script_loop())
            content_lines.extend(self.generate_footer())

            content = '\n'.join(content_lines)

            # 写入文件
            self.write_file(content, script_path)

            print(f"脚本已生成: {script_filename}")
            print(f"文件路径: {script_path}")

            return script_path

        except Exception as e:
            print(f"生成脚本文件时出错: {e}")
            return None


class LinuxShellGenerator(BaseScriptGenerator):
    """Linux Shell脚本生成器"""

    def get_file_extension(self) -> str:
        return "sh"

    def _normalize_paths(self) -> List[str]:
        """将Windows路径转换为Unix路径"""
        return [pf.replace('\\', '/') for pf in self.python_files]

    def generate_header(self) -> List[str]:
        """生成Shell脚本头部"""
        script_name = self.get_script_filename()[:-3]  # 去掉.sh后缀

        if Config.SCHEDULER_TYPE == "PBS":
            pbs_config = Config.get_pbs_header()
            return [
                "#!/bin/bash",
                f"#PBS -N {script_name}",
                "#PBS -o abaqus_execution.log",
                "#PBS -e abaqus_execution.err",
                f"#PBS -l walltime={pbs_config['walltime']}",
                f"#PBS -q {pbs_config['queue']}",
                f"#PBS -l nodes={pbs_config['nodes']}:ppn={pbs_config['ncpus']}",
                f"#PBS -l mem={pbs_config['memory']}",
                "",
                "# Change to working directory",
                "cd $PBS_O_WORKDIR",
                "",
                "# Setup real-time logging",
                "LOGDIR=logs",
                "mkdir -p $LOGDIR",
                "REALTIME_LOG=\"$LOGDIR/realtime_${PBS_JOBID}.log\"",
                "REALTIME_ERR=\"$LOGDIR/realtime_${PBS_JOBID}.err\"",
                "",
                "# Redirect all output to real-time log files with unbuffered output",
                "exec > >(tee -a \"$REALTIME_LOG\")",
                "exec 2> >(tee -a \"$REALTIME_ERR\" >&2)",
                "",
                "# Disable output buffering",
                "stdbuf -oL -eL echo 'Abaqus Batch Script Executor - Auto Generated'",
                "echo 'Job ID: '$PBS_JOBID",
                "echo 'Real-time log: '$REALTIME_LOG",
                "echo '" + "="*60 + "'",
                "",
                "# Set up Abaqus environment",
                f"module load {Config.ABAQUS_MODULE}",
                "",
                "# Fix ABAQUS environment file permission issue (IR-637600 workaround)",
                "echo 'Applying ABAQUS Python bytecode workaround...'",
                "export PYTHONDONTWRITEBYTECODE=1",
                "mkdir -p ~/.abaqus 2>/dev/null || true",
                "echo 'Workaround applied'",
                "",
                "# Start script execution",
                "echo \"Starting script execution...\"",
                ""
            ]
        else:  # SLURM
            slurm_config = Config.get_slurm_header()
            return [
                "#!/bin/bash",
                f"#SBATCH --job-name={script_name}",
                "#SBATCH --output=abaqus_execution_%j.log",
                "#SBATCH --error=abaqus_execution_%j.err",
                f"#SBATCH --time={slurm_config['time']}",
                f"#SBATCH --partition={slurm_config['partition']}",
                f"#SBATCH --nodes={slurm_config['nodes']}",
                f"#SBATCH --ntasks={slurm_config['ntasks']}",
                f"#SBATCH --cpus-per-task={slurm_config['cpus_per_task']}",
                f"#SBATCH --mem={slurm_config['memory']}",
                "",
                "echo 'Abaqus Batch Script Executor - Auto Generated'",
                "echo 'Job ID: $SLURM_JOB_ID'",
                "echo '" + "="*60 + "'",
                "",
                "# Set up Abaqus environment",
                f"module load {Config.ABAQUS_MODULE}",
                "",
                "# Fix ABAQUS environment file permission issue (IR-637600 workaround)",
                "echo 'Applying ABAQUS Python bytecode workaround...'",
                "export PYTHONDONTWRITEBYTECODE=1",
                "mkdir -p ~/.abaqus 2>/dev/null || true",
                "echo 'Workaround applied'",
                "",
                "# Start script execution",
                "echo \"Starting script execution...\"",
                ""
            ]

    def generate_script_loop(self) -> List[str]:
        """生成Shell脚本循环体 - 两阶段执行（与.bat完全一致）"""
        unix_files = self._normalize_paths()

        # 分离前处理和后处理脚本
        preprocess_files = [f for f in unix_files if '_preprocess.py' in f]
        postprocess_files = [f for f in unix_files if '_postprocess.py' in f]

        content = []

        # ========================================
        # Phase 1: 执行所有前处理脚本
        # ========================================
        if preprocess_files:
            content.extend([
                "# ========================================",
                "# Phase 1: Submit All Preprocessing Scripts",
                "# ========================================",
                f"echo 'Phase 1: Submitting {len(preprocess_files)} preprocessing scripts...'",
                "echo",
                ""
            ])

            for i, pf in enumerate(preprocess_files, 1):
                script_name = os.path.basename(pf)
                content.extend([
                    f"echo '[{i}/{len(preprocess_files)}] Submitting: {script_name}'",
                    f"{Config.ABAQUS_COMMAND}=\"{pf}\"",
                    "if [ $? -ne 0 ]; then",
                    f"    echo 'ERROR: Failed to submit {script_name}'",
                    f"    echo '{script_name}' >> failed_submissions.log",
                    "fi",
                    "echo",
                    ""
                ])

        # ========================================
        # Phase 2: 逐个提交求解器并后处理（避免ODB堆积）
        # ========================================
        if preprocess_files:
            content.extend([
                "# ========================================",
                "# Phase 2: Submit Solver and Postprocess (Sequential)",
                "# ========================================",
                "echo 'Phase 2: Processing jobs sequentially to avoid ODB accumulation...'",
                "echo",
                ""
            ])

            # 逐个处理每个任务
            for i, pf in enumerate(preprocess_files, 1):
                script_dir = os.path.dirname(pf)
                job_name = os.path.basename(pf).replace('_preprocess.py', '')
                inp_file = f"{script_dir}/{job_name}.inp"
                odb_file = f"{script_dir}/{job_name}.odb"
                abq_folder = f"{script_dir}/{job_name}.abq"
                feature_data_file = f"{script_dir}/feature_data.txt"
                postprocess_script = postprocess_files[i-1] if i <= len(postprocess_files) else None
                postprocess_name = os.path.basename(postprocess_script) if postprocess_script else None

                content.extend([
                    f"echo '========================================'",
                    f"echo '[{i}/{len(preprocess_files)}] Processing: {job_name}'",
                    f"echo '========================================'",
                    "",
                    "# Clean up lock files first",
                    f"rm -f \"{script_dir}\"/*.lck 2>/dev/null",
                    "",
                    f"cd \"{script_dir}\"",
                    "",
                    "# Check if feature_data.txt exists (skip if already processed)",
                    f"if [ -f \"{feature_data_file}\" ]; then",
                    f"    echo 'feature_data.txt exists, skipping solver and postprocess'",
                    "",
                    "    # Cleanup ODB and ABQ files if they exist",
                    f"    if [ -f \"{odb_file}\" ]; then",
                    f"        echo 'Deleting ODB file: {job_name}.odb'",
                    f"        rm -f \"{odb_file}\"",
                    "    fi",
                    f"    if [ -d \"{abq_folder}\" ]; then",
                    f"        echo 'Deleting ABQ folder: {job_name}.abq'",
                    f"        rm -rf \"{abq_folder}\"",
                    "    fi",
                    f"    if [ -f \"{script_dir}/{job_name}.dat\" ]; then",
                    f"        echo 'Deleting DAT file: {job_name}.dat'",
                    f"        rm -f \"{script_dir}/{job_name}.dat\"",
                    "    fi",
                    f"    if [ -f \"{inp_file}\" ]; then",
                    f"        echo 'Deleting INP file: {job_name}.inp'",
                    f"        rm -f \"{inp_file}\"",
                    "    fi",
                    "",
                    f"    echo 'Cleanup completed for {job_name}'",
                    "else",
                    "    echo 'feature_data.txt does not exist, running solver'",
                    "",
                    "    # Submit solver job and wait for completion",
                    f"    if [ -f \"{inp_file}\" ]; then",
                    f"        echo 'Submitting solver job: {job_name}'",
                    f"        abaqus job={job_name} input={job_name}.inp cpus=8",
                    f"        echo 'Solver completed for {job_name}'",
                    "    else",
                    f"        echo 'ERROR: Input file not found: {inp_file}'",
                    f"        echo '{job_name}' >> failed_submissions.log",
                    "    fi",
                    "fi",
                    "",
                ])

                if postprocess_script:
                    content.extend([
                        f"# Run postprocessing only if feature_data.txt doesn't exist",
                        f"if [ ! -f \"{feature_data_file}\" ]; then",
                        f"    if [ -f \"{inp_file}\" ]; then",
                        "        # Run postprocessing immediately",
                        f"        echo 'Running postprocessing: {postprocess_name}'",
                        f"        {Config.ABAQUS_COMMAND}=\"{postprocess_script}\" > \"{job_name}_postprocess.log\" 2>&1",
                        "        if [ $? -ne 0 ]; then",
                        f"            echo 'ERROR: Postprocessing failed for {postprocess_name}'",
                        f"            echo '{postprocess_name}' >> failed_postprocess.log",
                        "        else",
                        f"            echo 'Postprocessing completed for {job_name}'",
                        "        fi",
                        "",
                        "        # Cleanup files after postprocessing",
                        f"        if [ -f \"{odb_file}\" ]; then",
                        f"            echo 'Deleting ODB file: {job_name}.odb'",
                        f"            rm -f \"{odb_file}\"",
                        "        fi",
                        f"        if [ -d \"{abq_folder}\" ]; then",
                        f"            echo 'Deleting ABQ folder: {job_name}.abq'",
                        f"            rm -rf \"{abq_folder}\"",
                        "        fi",
                        f"        if [ -f \"{script_dir}/{job_name}.dat\" ]; then",
                        f"            echo 'Deleting DAT file: {job_name}.dat'",
                        f"            rm -f \"{script_dir}/{job_name}.dat\"",
                        "        fi",
                        f"        if [ -f \"{inp_file}\" ]; then",
                        f"            echo 'Deleting INP file: {job_name}.inp'",
                        f"            rm -f \"{inp_file}\"",
                        "        fi",
                        f"        echo 'Cleanup completed for {job_name}'",
                        "    fi",
                        "fi",
                    ])

                content.extend([
                    "echo",
                    ""
                ])

            content.extend([
                "echo 'All jobs completed!'",
                "echo",
                ""
            ])

        return content

    def generate_footer(self) -> List[str]:
        """生成Shell脚本尾部"""
        return [
            "echo '========================================'",
            "echo 'All tasks completed!'",
            "echo '========================================'",
            "echo",
            "read -p 'Press Enter to exit...'"
        ]

    def write_file(self, content: str, file_path: str):
        """写入Shell脚本文件并设置执行权限"""
        # 使用Unix换行符
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

        # 设置执行权限
        try:
            import stat
            os.chmod(file_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        except Exception as e:
            print(f"警告: 无法设置执行权限: {e}")

        print("在Linux中可执行: chmod +x script.sh && ./script.sh")


class WindowsBatchGenerator(BaseScriptGenerator):
    """Windows批处理脚本生成器"""

    def get_file_extension(self) -> str:
        return "bat"

    def generate_header(self) -> List[str]:
        """生成批处理脚本头部"""
        return [
            "@echo off",
            "setlocal enabledelayedexpansion",
            "echo Abaqus Batch Script Executor - Auto Generated",
            "echo " + "="*60,
            ""
        ]

    def generate_script_loop(self) -> List[str]:
        """生成批处理脚本循环体 - 两阶段执行（与.sh一致）"""
        content = []
        min_size = Config.FEATURE_FILE_MIN_SIZE

        # 分离前处理和后处理脚本
        preprocess_files = [f for f in self.python_files if '_preprocess.py' in os.path.basename(f)]
        postprocess_files = [f for f in self.python_files if '_postprocess.py' in os.path.basename(f)]

        # ========================================
        # Phase 1: 执行所有前处理脚本
        # ========================================
        if preprocess_files:
            content.extend([
                "rem ========================================",
                "rem Phase 1: Execute All Preprocessing Scripts",
                "rem ========================================",
                f"echo Phase 1: Executing {len(preprocess_files)} preprocessing scripts...",
                "echo.",
                ""
            ])

            for i, pf in enumerate(preprocess_files, 1):
                script_name = os.path.basename(pf)
                content.extend([
                    f"echo [{i}/{len(preprocess_files)}] Preprocessing: {script_name}",
                    f"call abaqus cae noGUI=\"{pf}\"",
                    "if errorlevel 1 (",
                    f"    echo ERROR: Failed to execute {script_name}",
                    f"    echo {script_name} >> failed_preprocessing.log",
                    ")",
                    "echo.",
                    ""
                ])

        # ========================================
        # Phase 2: 逐个提交求解器并后处理（避免ODB堆积）
        # ========================================
        if preprocess_files:
            content.extend([
                "rem ========================================",
                "rem Phase 2: Submit Solver and Postprocess (Sequential)",
                "rem ========================================",
                "echo Phase 2: Processing jobs sequentially to avoid ODB accumulation...",
                "echo.",
                ""
            ])

            # 逐个处理每个任务
            for i, pf in enumerate(preprocess_files, 1):
                script_dir = os.path.dirname(pf)
                job_name = os.path.basename(pf).replace('_preprocess.py', '')
                inp_file = os.path.join(script_dir, f"{job_name}.inp")
                postprocess_script = postprocess_files[i-1] if i <= len(postprocess_files) else None
                postprocess_name = os.path.basename(postprocess_script) if postprocess_script else None

                content.extend([
                    f"echo ========================================",
                    f"echo [{i}/{len(preprocess_files)}] Processing: {job_name}",
                    f"echo ========================================",
                    "",
                    "rem Clean up lock files first",
                    f"del /Q \"{script_dir}\\*.lck\" 2>nul",
                    "",
                    f"cd /d \"{script_dir}\"",
                    "",
                    "rem Submit solver job and wait for completion",
                    f"if exist \"{job_name}.inp\" (",
                    f"    echo Submitting solver job: {job_name}",
                    f"    abaqus job={job_name} input={job_name}.inp cpus=8 interactive > \"{job_name}_solver.log\" 2>&1",
                    f"    echo Solver completed for {job_name}",
                    ") else (",
                    f"    echo ERROR: Input file not found: {job_name}.inp",
                    f"    echo {job_name} >> failed_solver.log",
                    ")",
                    "",
                ])

                if postprocess_script:
                    content.extend([
                        "rem Check if solver succeeded before postprocessing",
                        f"if exist \"{inp_file}\" (",
                        "    rem Run postprocessing immediately",
                        f"    echo Running postprocessing: {postprocess_name}",
                        f"    call abaqus cae noGUI={postprocess_name} > \"{job_name}_postprocess.log\" 2>&1",
                        "    if errorlevel 1 (",
                        f"        echo ERROR: Postprocessing failed for {postprocess_name}",
                        f"        echo {postprocess_name} >> failed_postprocess.log",
                        "    ) else (",
                        f"        echo Postprocessing completed for {job_name}",
                        "    )",
                        ")",
                    ])

                content.extend([
                    "echo.",
                    ""
                ])

            content.extend([
                "echo All jobs completed!",
                "echo.",
                ""
            ])

        return content

    def generate_footer(self) -> List[str]:
        """生成批处理脚本尾部"""
        # Count only postprocess scripts for success rate calculation
        postprocess_count = sum(1 for pf in self.python_files if '_postprocess.py' in os.path.basename(pf))

        content = [
            "echo " + "="*60,
            "echo All scripts execution completed!",
            "",
            "rem Generate execution summary report",
            "echo Execution Summary Report > final_report.log",
            "echo ====================== >> final_report.log",
            "echo Execution completed at: %date% %time% >> final_report.log",
            f"echo Total scripts processed: {len(self.python_files)} >> final_report.log",
            f"echo Postprocess tasks ^(counted^): {postprocess_count} >> final_report.log",
            "echo. >> final_report.log",
            "",
            "if exist execution_summary.log (",
            "    echo Individual Script Results: >> final_report.log",
            "    type execution_summary.log >> final_report.log",
            "    echo. >> final_report.log",
            ")",
            "",
            "if exist error.log (",
            "    echo Error Summary: >> final_report.log",
            "    type error.log >> final_report.log",
            "    echo. >> final_report.log",
            ")",
            "",
            "rem Calculate success rate based on feature_data.txt quality (postprocess scripts only)",
            "set success_count=0",
            ""
        ]

        # 为每个后处理脚本添加检查代码
        min_size = Config.FEATURE_FILE_MIN_SIZE
        for script_file in self.python_files:
            script_name = os.path.basename(script_file)
            # Only count postprocess scripts
            if '_postprocess.py' in script_name:
                script_dir = os.path.dirname(script_file)
                feature_data_path = os.path.join(script_dir, "feature_data.txt")
                content.append(f"if exist \"{feature_data_path}\" (")
                content.append(f"    for %%i in (\"{feature_data_path}\") do (")
                content.append(f"        if %%~zi geq {min_size} set /a success_count+=1")
                content.append(f"    )")
                content.append(f")")

        content.extend([
            f"set /a failure_count={postprocess_count}-!success_count!",
            "echo Success: !success_count!, Failed: !failure_count! >> final_report.log",
        ])

        if postprocess_count > 0:
            content.extend([
                f"set /a success_rate=!success_count! * 100 / {postprocess_count}",
                "echo Success rate: !success_rate!%% >> final_report.log",
            ])
        else:
            content.append("echo Success rate: N/A ^(no postprocess tasks^) >> final_report.log")

        content.extend([
            "",
            "echo Final execution report saved to: final_report.log",
            "echo Summary: Success=!success_count!, Failed=!failure_count!",
            "echo.",
            "pause"
        ])

        return content

    def write_file(self, content: str, file_path: str):
        """写入批处理文件"""
        with open(file_path, 'w', encoding='ascii', errors='ignore') as f:
            f.write(content)

        print("可在Abaqus Command中执行此批处理文件")


def generate_shell_script(python_files: List[str], output_dir: str, script_type: str = "sh",
                          group_number: Optional[int] = None, config_name: Optional[str] = None) -> Optional[str]:
    """
    生成shell脚本文件的工厂函数 (保持向后兼容)

    Args:
        python_files: Python脚本文件列表
        output_dir: 输出目录
        script_type: 脚本类型 ("sh" 或 "bat")
        group_number: 组号(可选)
        config_name: 配置名称(可选)

    Returns:
        str: 生成的脚本文件路径，失败返回None
    """
    generator_class = LinuxShellGenerator if script_type == "sh" else WindowsBatchGenerator
    generator = generator_class(python_files, output_dir, group_number, config_name)
    return generator.generate()
