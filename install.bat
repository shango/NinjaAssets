@echo off
REM ============================================================
REM   NinjaAssets Installer for Windows
REM   Double-click this file to install NinjaAssets into Maya.
REM ============================================================

echo.
echo  ==============================
echo   NinjaAssets Installer
echo  ==============================
echo.

REM Try mayapy first (ships with Maya, always available)
set "MAYAPY="

REM Check common Maya install locations for mayapy
for %%Y in (2026 2025 2024 2023 2022) do (
    if exist "C:\Program Files\Autodesk\Maya%%Y\bin\mayapy.exe" (
        if not defined MAYAPY (
            set "MAYAPY=C:\Program Files\Autodesk\Maya%%Y\bin\mayapy.exe"
            echo  Found Maya %%Y
        )
    )
)

REM Fall back to system Python
if not defined MAYAPY (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "MAYAPY=python"
        echo  Using system Python
    ) else (
        where python3 >nul 2>&1
        if %errorlevel%==0 (
            set "MAYAPY=python3"
            echo  Using system Python3
        ) else (
            echo  ERROR: Could not find Maya or Python on this computer.
            echo  Please install Maya first, then try again.
            echo.
            pause
            exit /b 1
        )
    )
)

echo.
echo  Installing NinjaAssets...
echo.

"%MAYAPY%" -m ninja_assets.cli.install --copy

echo.
if %errorlevel%==0 (
    echo  ----------------------------------------
    echo   Done! Restart Maya to start using
    echo   NinjaAssets.
    echo  ----------------------------------------
) else (
    echo  Something went wrong. See the error above.
    echo  If you need help, ask your pipeline TD.
)
echo.
pause
