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
echo Phase 1: Submitting 2 preprocessing scripts...
echo.

echo [1/2] Submitting: Auxetic_5_0p5_8_StaCompre_2x2x2_preprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2_preprocess.py"
if errorlevel 1 (
    echo ERROR: Failed to submit Auxetic_5_0p5_8_StaCompre_2x2x2_preprocess.py
    echo Auxetic_5_0p5_8_StaCompre_2x2x2_preprocess.py >> failed_submissions.log
)
echo.

echo [2/2] Submitting: BCC_5_0p5_8_StaCompre_2x2x2_preprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2_preprocess.py"
if errorlevel 1 (
    echo ERROR: Failed to submit BCC_5_0p5_8_StaCompre_2x2x2_preprocess.py
    echo BCC_5_0p5_8_StaCompre_2x2x2_preprocess.py >> failed_submissions.log
)
echo.

rem ========================================
rem Phase 2: Submit Solver and Postprocess (Sequential)
rem ========================================
echo Phase 2: Processing jobs sequentially to avoid ODB accumulation...
echo.

echo ========================================
echo [1/2] Processing: Auxetic_5_0p5_8_StaCompre_2x2x2
echo ========================================
cd /d "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre"

rem Clean up lock files first
del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\*.lck" 2>nul

rem Check if feature_data.txt exists
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\feature_data.txt" (
    echo feature_data.txt exists, skipping solver and postprocess

    rem Cleanup ODB and ABQ files if they exist
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.odb" (
        echo Deleting ODB file: Auxetic_5_0p5_8_StaCompre_2x2x2.odb
        del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.odb"
    )
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.abq" (
        echo Deleting ABQ folder: Auxetic_5_0p5_8_StaCompre_2x2x2.abq
        rd /S /Q "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.abq"
    )

    goto skip_postprocess_1
) else (
    echo feature_data.txt does not exist, running solver
)

rem Submit solver job and wait for completion
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.inp" (
    echo Submitting solver job: Auxetic_5_0p5_8_StaCompre_2x2x2
    rem Redirect verbose output to log file, only show summary
    echo y | abaqus job=Auxetic_5_0p5_8_StaCompre_2x2x2 input=Auxetic_5_0p5_8_StaCompre_2x2x2.inp cpus=8 interactive > "Auxetic_5_0p5_8_StaCompre_2x2x2_solver.log" 2>&1
    echo Solver completed for Auxetic_5_0p5_8_StaCompre_2x2x2
    echo Full solver log: Auxetic_5_0p5_8_StaCompre_2x2x2_solver.log
) else (
    echo ERROR: Input file not found: d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.inp
    echo Auxetic_5_0p5_8_StaCompre_2x2x2 >> failed_submissions.log
    goto skip_postprocess_1
)

rem Run postprocessing immediately
echo Running postprocessing: Auxetic_5_0p5_8_StaCompre_2x2x2_postprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2_postprocess.py"
if errorlevel 1 (
    echo ERROR: Postprocessing failed for Auxetic_5_0p5_8_StaCompre_2x2x2_postprocess.py
    echo Auxetic_5_0p5_8_StaCompre_2x2x2_postprocess.py >> failed_postprocess.log
) else (
    echo Postprocessing completed for Auxetic_5_0p5_8_StaCompre_2x2x2
)

rem Cleanup files after postprocessing (ODB deletion disabled)
rem if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.odb" (
rem     echo Deleting ODB file: Auxetic_5_0p5_8_StaCompre_2x2x2.odb
rem     del /f /q "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.odb" >nul 2>&1
rem )
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.abq" (
    echo Deleting ABQ folder: Auxetic_5_0p5_8_StaCompre_2x2x2.abq
    rmdir /s /q "d:\ARTC\ARTC-Auto-Script\generate_script\Auxetic\5\0p5\8\StaCompre\Auxetic_5_0p5_8_StaCompre_2x2x2.abq" >nul 2>&1
)
echo Cleanup completed for Auxetic_5_0p5_8_StaCompre_2x2x2
:skip_postprocess_1
echo.

echo ========================================
echo [2/2] Processing: BCC_5_0p5_8_StaCompre_2x2x2
echo ========================================
cd /d "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre"

rem Clean up lock files first
del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\*.lck" 2>nul

rem Check if feature_data.txt exists
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\feature_data.txt" (
    echo feature_data.txt exists, skipping solver and postprocess

    rem Cleanup ODB and ABQ files if they exist
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.odb" (
        echo Deleting ODB file: BCC_5_0p5_8_StaCompre_2x2x2.odb
        del /Q "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.odb"
    )
    if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.abq" (
        echo Deleting ABQ folder: BCC_5_0p5_8_StaCompre_2x2x2.abq
        rd /S /Q "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.abq"
    )

    goto skip_postprocess_2
) else (
    echo feature_data.txt does not exist, running solver
)

rem Submit solver job and wait for completion
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.inp" (
    echo Submitting solver job: BCC_5_0p5_8_StaCompre_2x2x2
    rem Redirect verbose output to log file, only show summary
    echo y | abaqus job=BCC_5_0p5_8_StaCompre_2x2x2 input=BCC_5_0p5_8_StaCompre_2x2x2.inp cpus=8 interactive > "BCC_5_0p5_8_StaCompre_2x2x2_solver.log" 2>&1
    echo Solver completed for BCC_5_0p5_8_StaCompre_2x2x2
    echo Full solver log: BCC_5_0p5_8_StaCompre_2x2x2_solver.log
) else (
    echo ERROR: Input file not found: d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.inp
    echo BCC_5_0p5_8_StaCompre_2x2x2 >> failed_submissions.log
    goto skip_postprocess_2
)

rem Run postprocessing immediately
echo Running postprocessing: BCC_5_0p5_8_StaCompre_2x2x2_postprocess.py
call abaqus cae noGUI="d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2_postprocess.py"
if errorlevel 1 (
    echo ERROR: Postprocessing failed for BCC_5_0p5_8_StaCompre_2x2x2_postprocess.py
    echo BCC_5_0p5_8_StaCompre_2x2x2_postprocess.py >> failed_postprocess.log
) else (
    echo Postprocessing completed for BCC_5_0p5_8_StaCompre_2x2x2
)

rem Cleanup files after postprocessing (ODB deletion disabled)
rem if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.odb" (
rem     echo Deleting ODB file: BCC_5_0p5_8_StaCompre_2x2x2.odb
rem     del /f /q "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.odb" >nul 2>&1
rem )
if exist "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.abq" (
    echo Deleting ABQ folder: BCC_5_0p5_8_StaCompre_2x2x2.abq
    rmdir /s /q "d:\ARTC\ARTC-Auto-Script\generate_script\BCC\5\0p5\8\StaCompre\BCC_5_0p5_8_StaCompre_2x2x2.abq" >nul 2>&1
)
echo Cleanup completed for BCC_5_0p5_8_StaCompre_2x2x2
:skip_postprocess_2
echo.

echo All jobs completed!
echo.

echo ========================================
echo All tasks completed!
echo ========================================
echo.
pause