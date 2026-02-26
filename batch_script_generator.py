#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门用于生成前处理+后处理批处理脚本的模块
两阶段执行策略：最小化CAE license占用并避免ODB堆积
Phase 1: 批量前处理
Phase 2: 逐个求解并后处理

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

import os
from typing import List
from datetime import datetime


def generate_split_batch_script(preprocess_files: List[str], postprocess_files: List[str], output_dir: str):
    """
    生成Windows批处理脚本，分两个阶段执行：
    Phase 1: 批量运行所有前处理（连续执行，快速释放CAE）
    Phase 2: 逐个提交求解器并后处理（求解完立即处理ODB，避免堆积）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(output_dir, f"run_all_optimized_{timestamp}.bat")

    content = [
        "@echo off",
        "setlocal enabledelayedexpansion",
        "echo ========================================",
        "echo Abaqus Optimized Batch Executor",
        "echo Minimizing CAE License Usage",
        "echo ========================================",
        "echo.",
        "",
        "rem ========================================",
        "rem Phase 1: Submit All Preprocessing Scripts",
        "rem ========================================",
        f"echo Phase 1: Submitting {len(preprocess_files)} preprocessing scripts...",
        "echo.",
        ""
    ]

    # 第1阶段：提交所有前处理脚本
    for i, pf in enumerate(preprocess_files, 1):
        script_name = os.path.basename(pf)
        content.extend([
            f"echo [{i}/{len(preprocess_files)}] Submitting: {script_name}",
            f"call abaqus cae noGUI=\"{pf}\"",
            "if errorlevel 1 (",
            f"    echo ERROR: Failed to submit {script_name}",
            f"    echo {script_name} >> failed_submissions.log",
            ")",
            "echo.",
            ""
        ])

    # 第2阶段：逐个提交求解器并后处理（避免ODB堆积）
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
        lck_file = os.path.join(script_dir, f"{job_name}.lck")
        odb_file = os.path.join(script_dir, f"{job_name}.odb")
        abq_folder = os.path.join(script_dir, f"{job_name}.abq")
        feature_file = os.path.join(script_dir, "feature_data.txt")
        postprocess_script = postprocess_files[i-1] if i <= len(postprocess_files) else None

        content.extend([
            f"echo ========================================",
            f"echo [{i}/{len(preprocess_files)}] Processing: {job_name}",
            f"echo ========================================",
            f"cd /d \"{script_dir}\"",
            "",
            "rem Clean up lock files first",
            f"del /Q \"{script_dir}\\*.lck\" 2>nul",
            "",
            "rem Check if feature_data.txt exists",
            f"if exist \"{feature_file}\" (",
            f"    echo feature_data.txt exists, skipping solver and postprocess",
            "",
            "    rem Cleanup ODB and ABQ files if they exist",
            f"    if exist \"{odb_file}\" (",
            f"        echo Deleting ODB file: {job_name}.odb",
            f"        del /Q \"{odb_file}\"",
            "    )",
            f"    if exist \"{abq_folder}\\\" (",
            f"        echo Deleting ABQ folder: {job_name}.abq",
            f"        rd /S /Q \"{abq_folder}\" >nul 2>&1",
            "    )",
            "",
            f"    goto skip_postprocess_{i}",
            ") else (",
            "    echo feature_data.txt does not exist, running solver",
            ")",
            "",
            "rem Submit solver job and wait for completion",
            f"if exist \"{inp_file}\" (",
            f"    echo Submitting solver job: {job_name}",
            "    rem Redirect verbose output to log file, only show summary",
            f"    echo y | abaqus job={job_name} input={job_name}.inp cpus=8 interactive > \"{job_name}_solver.log\" 2>&1",
            f"    echo Solver completed for {job_name}",
            f"    echo Full solver log: {job_name}_solver.log",
            f") else (",
            f"    echo ERROR: Input file not found: {inp_file}",
            f"    echo {job_name} >> failed_submissions.log",
            f"    goto skip_postprocess_{i}",
            ")",
            "",
        ])

        if postprocess_script:
            postprocess_name = os.path.basename(postprocess_script)
            content.extend([
                "rem Run postprocessing immediately",
                f"echo Running postprocessing: {postprocess_name}",
                f"call abaqus cae noGUI=\"{postprocess_script}\"",
                "if errorlevel 1 (",
                f"    echo ERROR: Postprocessing failed for {postprocess_name}",
                f"    echo {postprocess_name} >> failed_postprocess.log",
                ") else (",
                f"    echo Postprocessing completed for {job_name}",
                ")",
                "",
                "rem Cleanup files after postprocessing (ODB deletion disabled)",
                f"rem if exist \"{odb_file}\" (",
                f"rem     echo Deleting ODB file: {job_name}.odb",
                f"rem     del /f /q \"{odb_file}\" >nul 2>&1",
                "rem )",
                f"if exist \"{abq_folder}\\\" (",
                f"    echo Deleting ABQ folder: {job_name}.abq",
                f"    rmdir /s /q \"{abq_folder}\" >nul 2>&1",
                ")",
                f"echo Cleanup completed for {job_name}",
            ])

        content.extend([
            f":skip_postprocess_{i}",
            "echo.",
            ""
        ])

    content.extend([
        "echo All jobs completed!",
        "echo.",
        ""
    ])

    # 结束
    content.extend([
        "echo ========================================",
        "echo All tasks completed!",
        "echo ========================================",
        "echo.",
        "pause"
    ])

    # 写入文件
    with open(script_path, 'w', encoding='ascii', errors='ignore') as f:
        f.write('\n'.join(content))

    print(f"Optimized batch script generated: {script_path}")
    return script_path


def generate_simple_batch_script(python_files: List[str], output_dir: str):
    """
    生成简单的批处理脚本（用于单体脚本）
    保持向后兼容
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(output_dir, f"run_all_{timestamp}.bat")

    content = [
        "@echo off",
        "setlocal enabledelayedexpansion",
        "echo Abaqus Batch Script Executor",
        "echo ========================================",
        "echo.",
        ""
    ]

    for i, pf in enumerate(python_files, 1):
        script_name = os.path.basename(pf)
        content.extend([
            f"echo [{i}/{len(python_files)}] Executing: {script_name}",
            f"abaqus cae noGUI=\"{pf}\"",
            "echo.",
            ""
        ])

    content.extend([
        "echo All scripts completed!",
        "pause"
    ])

    with open(script_path, 'w', encoding='ascii', errors='ignore') as f:
        f.write('\n'.join(content))

    print(f"Batch script generated: {script_path}")
    return script_path


def generate_split_shell_script(preprocess_files: List[str], postprocess_files: List[str], output_dir: str):
    """
    生成Linux Shell脚本，分两个阶段执行：
    Phase 1: 批量运行所有前处理（连续执行，快速释放CAE）
    Phase 2: 逐个提交求解器并后处理（求解完立即处理ODB，避免堆积）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(output_dir, f"run_all_optimized_{timestamp}.sh")

    # 将Windows路径转换为Unix路径
    from config import Config

    def convert_to_unix_path(win_path):
        """将Windows路径转换为Linux路径"""
        # 将反斜杠替换为正斜杠
        unix_path = win_path.replace('\\', '/')
        # 提取 generate_script 之后的相对路径
        if 'generate_script' in unix_path:
            rel_path = unix_path.split('generate_script', 1)[1].lstrip('/')
            # 使用配置中的Linux基础路径
            return f"{Config.BASE_SCRIPT_PATH}/{rel_path}"
        return unix_path

    preprocess_files_unix = [convert_to_unix_path(f) for f in preprocess_files]
    postprocess_files_unix = [convert_to_unix_path(f) for f in postprocess_files]

    content = [
        "#!/bin/bash",
        "",
        "echo '========================================'",
        "echo 'Abaqus Optimized Batch Executor'",
        "echo 'Minimizing CAE License Usage'",
        "echo '========================================'",
        "echo",
        "",
        "# ========================================",
        "# Phase 1: Submit All Preprocessing Scripts",
        "# ========================================",
        f"echo 'Phase 1: Submitting {len(preprocess_files)} preprocessing scripts...'",
        "echo",
        ""
    ]

    # 第1阶段：提交所有前处理脚本
    for i, pf in enumerate(preprocess_files_unix, 1):
        script_name = os.path.basename(pf)
        content.extend([
            f"echo '[{i}/{len(preprocess_files)}] Submitting: {script_name}'",
            f"abaqus cae noGUI=\"{pf}\"",
            "if [ $? -ne 0 ]; then",
            f"    echo 'ERROR: Failed to submit {script_name}'",
            f"    echo '{script_name}' >> failed_submissions.log",
            "fi",
            "echo",
            ""
        ])

    # 第2阶段：逐个提交求解器并后处理（避免ODB堆积）
    content.extend([
        "# ========================================",
        "# Phase 2: Submit Solver and Postprocess (Sequential)",
        "# ========================================",
        "echo 'Phase 2: Processing jobs sequentially to avoid ODB accumulation...'",
        "echo",
        ""
    ])

    # 逐个处理每个任务
    for i, pf in enumerate(preprocess_files_unix, 1):
        script_dir = os.path.dirname(pf)
        job_name = os.path.basename(pf).replace('_preprocess.py', '')
        inp_file = os.path.join(script_dir, f"{job_name}.inp").replace('\\', '/')
        lck_file = os.path.join(script_dir, f"{job_name}.lck").replace('\\', '/')
        odb_file = os.path.join(script_dir, f"{job_name}.odb").replace('\\', '/')
        abq_folder = os.path.join(script_dir, f"{job_name}.abq").replace('\\', '/')
        feature_file = os.path.join(script_dir, "feature_data.txt").replace('\\', '/')
        postprocess_script = postprocess_files_unix[i-1] if i <= len(postprocess_files_unix) else None

        content.extend([
            f"echo '========================================'",
            f"echo '[{i}/{len(preprocess_files)}] Processing: {job_name}'",
            f"echo '========================================'",
            f"cd \"{script_dir}\"",
            "",
            "# Clean up lock files first",
            f"rm -f \"{script_dir}\"/*.lck 2>/dev/null",
            "",
            "# Check if feature_data.txt exists",
            f"if [ -f \"{feature_file}\" ]; then",
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
            "",
            "    continue",
            "else",
            f"    echo 'feature_data.txt does not exist, running solver'",
            "fi",
            "",
            "# Submit solver job and wait for completion",
            f"if [ -f \"{inp_file}\" ]; then",
            f"    echo 'Submitting solver job: {job_name}'",
            "    # Redirect verbose output to log file, only show summary",
            f"    yes | abaqus job={job_name} input={job_name}.inp cpus=8 interactive > \"{job_name}_solver.log\" 2>&1",
            f"    echo 'Solver completed for {job_name}'",
            f"    echo 'Full solver log: {job_name}_solver.log'",
            "else",
            f"    echo 'ERROR: Input file not found: {inp_file}'",
            f"    echo '{job_name}' >> failed_submissions.log",
            f"    continue",
            "fi",
            "",
        ])

        if postprocess_script:
            postprocess_name = os.path.basename(postprocess_script)
            content.extend([
                "# Run postprocessing immediately",
                f"echo 'Running postprocessing: {postprocess_name}'",
                f"abaqus cae noGUI=\"{postprocess_script}\"",
                "if [ $? -ne 0 ]; then",
                f"    echo 'ERROR: Postprocessing failed for {postprocess_name}'",
                f"    echo '{postprocess_name}' >> failed_postprocess.log",
                "else",
                f"    echo 'Postprocessing completed for {job_name}'",
                "fi",
                "",
                "# Cleanup files after postprocessing",
                f"if [ -f \"{odb_file}\" ]; then",
                f"    echo 'Deleting ODB file: {job_name}.odb'",
                f"    rm -f \"{odb_file}\"",
                "fi",
                f"if [ -d \"{abq_folder}\" ]; then",
                f"    echo 'Deleting ABQ folder: {job_name}.abq'",
                f"    rm -rf \"{abq_folder}\"",
                "fi",
                f"echo 'Cleanup completed for {job_name}'",
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

    # 结束
    content.extend([
        "echo '========================================'",
        "echo 'All tasks completed!'",
        "echo '========================================'",
        "echo",
        "read -p 'Press Enter to exit...'"
    ])

    # 写入文件（使用Unix换行符）
    with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(content))

    # 设置执行权限
    try:
        import stat
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    except Exception as e:
        print(f"Warning: Could not set execute permission: {e}")

    print(f"Optimized shell script generated: {script_path}")
    return script_path
