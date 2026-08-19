@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Abaqus Optimized Batch Executor
echo Minimizing CAE License Usage
echo ========================================
echo.

rem ========================================
rem Phase 1: Submit All Preprocessing Scripts
rem ========================================
echo Phase 1: Submitting 3 preprocessing scripts...
echo.

echo [1/3] Submitting: Iso_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py"
if errorlevel 1 (
    echo ERROR: Failed to submit Iso_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py
    echo Iso_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py >> failed_submissions.log
)
echo.

echo [2/3] Submitting: Kelvin_5_0p5_8_StaCompre_2x2x2_preprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2_preprocess.py"
if errorlevel 1 (
    echo ERROR: Failed to submit Kelvin_5_0p5_8_StaCompre_2x2x2_preprocess.py
    echo Kelvin_5_0p5_8_StaCompre_2x2x2_preprocess.py >> failed_submissions.log
)
echo.

echo [3/3] Submitting: Octet_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py"
if errorlevel 1 (
    echo ERROR: Failed to submit Octet_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py
    echo Octet_truss_5_0p5_8_StaCompre_2x2x2_preprocess.py >> failed_submissions.log
)
echo.

rem ========================================
rem Phase 2: Submit Solver and Postprocess (Sequential)
rem ========================================
echo Phase 2: Processing jobs sequentially to avoid ODB accumulation...
echo.

echo ========================================
echo [1/3] Processing: Iso_truss_5_0p5_8_StaCompre_2x2x2
echo ========================================
cd /d "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre"

rem Clean up lock files first
del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\*.lck" 2>nul

rem Check if feature_data.txt exists
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\feature_data.txt" (
    echo feature_data.txt exists, skipping solver and postprocess

    rem Cleanup ODB and ABQ files if they exist
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.odb" (
        echo Deleting ODB file: Iso_truss_5_0p5_8_StaCompre_2x2x2.odb
        del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.odb"
    )
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.abq" (
        echo Deleting ABQ folder: Iso_truss_5_0p5_8_StaCompre_2x2x2.abq
        rd /S /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.abq"
    )

    goto skip_postprocess_1
) else (
    echo feature_data.txt does not exist, running solver
)

rem Submit solver job and wait for completion
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.inp" (
    echo Submitting solver job: Iso_truss_5_0p5_8_StaCompre_2x2x2
    rem Redirect verbose output to log file, only show summary
    echo y | abaqus job=Iso_truss_5_0p5_8_StaCompre_2x2x2 input=Iso_truss_5_0p5_8_StaCompre_2x2x2.inp cpus=8 interactive > "Iso_truss_5_0p5_8_StaCompre_2x2x2_solver.log" 2>&1
    echo Solver completed for Iso_truss_5_0p5_8_StaCompre_2x2x2
    echo Full solver log: Iso_truss_5_0p5_8_StaCompre_2x2x2_solver.log
) else (
    echo ERROR: Input file not found: d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.inp
    echo Iso_truss_5_0p5_8_StaCompre_2x2x2 >> failed_submissions.log
    goto skip_postprocess_1
)

rem Run postprocessing immediately
echo Running postprocessing: Iso_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py"
if errorlevel 1 (
    echo ERROR: Postprocessing failed for Iso_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py
    echo Iso_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py >> failed_postprocess.log
) else (
    echo Postprocessing completed for Iso_truss_5_0p5_8_StaCompre_2x2x2
)

rem Cleanup files after postprocessing (ODB deletion disabled)
rem if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.odb" (
rem     echo Deleting ODB file: Iso_truss_5_0p5_8_StaCompre_2x2x2.odb
rem     del /f /q "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.odb" >nul 2>&1
rem )
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.abq" (
    echo Deleting ABQ folder: Iso_truss_5_0p5_8_StaCompre_2x2x2.abq
    rmdir /s /q "d:\ARTC\ARTC-Auto-Script\generate_script\Iso_truss\5\0p5\8\StaCompre\Iso_truss_5_0p5_8_StaCompre_2x2x2.abq" >nul 2>&1
)
echo Cleanup completed for Iso_truss_5_0p5_8_StaCompre_2x2x2
:skip_postprocess_1
echo.

echo ========================================
echo [2/3] Processing: Kelvin_5_0p5_8_StaCompre_2x2x2
echo ========================================
cd /d "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre"

rem Clean up lock files first
del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\*.lck" 2>nul

rem Check if feature_data.txt exists
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\feature_data.txt" (
    echo feature_data.txt exists, skipping solver and postprocess

    rem Cleanup ODB and ABQ files if they exist
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.odb" (
        echo Deleting ODB file: Kelvin_5_0p5_8_StaCompre_2x2x2.odb
        del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.odb"
    )
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.abq" (
        echo Deleting ABQ folder: Kelvin_5_0p5_8_StaCompre_2x2x2.abq
        rd /S /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.abq"
    )

    goto skip_postprocess_2
) else (
    echo feature_data.txt does not exist, running solver
)

rem Submit solver job and wait for completion
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.inp" (
    echo Submitting solver job: Kelvin_5_0p5_8_StaCompre_2x2x2
    rem Redirect verbose output to log file, only show summary
    echo y | abaqus job=Kelvin_5_0p5_8_StaCompre_2x2x2 input=Kelvin_5_0p5_8_StaCompre_2x2x2.inp cpus=8 interactive > "Kelvin_5_0p5_8_StaCompre_2x2x2_solver.log" 2>&1
    echo Solver completed for Kelvin_5_0p5_8_StaCompre_2x2x2
    echo Full solver log: Kelvin_5_0p5_8_StaCompre_2x2x2_solver.log
) else (
    echo ERROR: Input file not found: d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.inp
    echo Kelvin_5_0p5_8_StaCompre_2x2x2 >> failed_submissions.log
    goto skip_postprocess_2
)

rem Run postprocessing immediately
echo Running postprocessing: Kelvin_5_0p5_8_StaCompre_2x2x2_postprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2_postprocess.py"
if errorlevel 1 (
    echo ERROR: Postprocessing failed for Kelvin_5_0p5_8_StaCompre_2x2x2_postprocess.py
    echo Kelvin_5_0p5_8_StaCompre_2x2x2_postprocess.py >> failed_postprocess.log
) else (
    echo Postprocessing completed for Kelvin_5_0p5_8_StaCompre_2x2x2
)

rem Cleanup files after postprocessing (ODB deletion disabled)
rem if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.odb" (
rem     echo Deleting ODB file: Kelvin_5_0p5_8_StaCompre_2x2x2.odb
rem     del /f /q "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.odb" >nul 2>&1
rem )
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.abq" (
    echo Deleting ABQ folder: Kelvin_5_0p5_8_StaCompre_2x2x2.abq
    rmdir /s /q "d:\ARTC\ARTC-Auto-Script\generate_script\Kelvin\5\0p5\8\StaCompre\Kelvin_5_0p5_8_StaCompre_2x2x2.abq" >nul 2>&1
)
echo Cleanup completed for Kelvin_5_0p5_8_StaCompre_2x2x2
:skip_postprocess_2
echo.

echo ========================================
echo [3/3] Processing: Octet_truss_5_0p5_8_StaCompre_2x2x2
echo ========================================
cd /d "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre"

rem Clean up lock files first
del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\*.lck" 2>nul

rem Check if feature_data.txt exists
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\feature_data.txt" (
    echo feature_data.txt exists, skipping solver and postprocess

    rem Cleanup ODB and ABQ files if they exist
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.odb" (
        echo Deleting ODB file: Octet_truss_5_0p5_8_StaCompre_2x2x2.odb
        del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.odb"
    )
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.abq" (
        echo Deleting ABQ folder: Octet_truss_5_0p5_8_StaCompre_2x2x2.abq
        rd /S /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.abq"
    )

    goto skip_postprocess_3
) else (
    echo feature_data.txt does not exist, running solver
)

rem Submit solver job and wait for completion
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.inp" (
    echo Submitting solver job: Octet_truss_5_0p5_8_StaCompre_2x2x2
    rem Redirect verbose output to log file, only show summary
    echo y | abaqus job=Octet_truss_5_0p5_8_StaCompre_2x2x2 input=Octet_truss_5_0p5_8_StaCompre_2x2x2.inp cpus=8 interactive > "Octet_truss_5_0p5_8_StaCompre_2x2x2_solver.log" 2>&1
    echo Solver completed for Octet_truss_5_0p5_8_StaCompre_2x2x2
    echo Full solver log: Octet_truss_5_0p5_8_StaCompre_2x2x2_solver.log
) else (
    echo ERROR: Input file not found: d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.inp
    echo Octet_truss_5_0p5_8_StaCompre_2x2x2 >> failed_submissions.log
    goto skip_postprocess_3
)

rem Run postprocessing immediately
echo Running postprocessing: Octet_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py"
if errorlevel 1 (
    echo ERROR: Postprocessing failed for Octet_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py
    echo Octet_truss_5_0p5_8_StaCompre_2x2x2_postprocess.py >> failed_postprocess.log
) else (
    echo Postprocessing completed for Octet_truss_5_0p5_8_StaCompre_2x2x2
)

rem Cleanup files after postprocessing (ODB deletion disabled)
rem if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.odb" (
rem     echo Deleting ODB file: Octet_truss_5_0p5_8_StaCompre_2x2x2.odb
rem     del /f /q "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.odb" >nul 2>&1
rem )
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.abq" (
    echo Deleting ABQ folder: Octet_truss_5_0p5_8_StaCompre_2x2x2.abq
    rmdir /s /q "d:\ARTC\ARTC-Auto-Script\generate_script\Octet_truss\5\0p5\8\StaCompre\Octet_truss_5_0p5_8_StaCompre_2x2x2.abq" >nul 2>&1
)
echo Cleanup completed for Octet_truss_5_0p5_8_StaCompre_2x2x2
:skip_postprocess_3
echo.

echo All jobs completed!
echo.

echo ========================================
echo All tasks completed!
echo ========================================
echo.
pause