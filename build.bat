@echo off
chcp 65001 >nul
title 打包 AI学英语 App 为 exe

echo ============================================
echo   打包 AI 学英语 App (Windows)
echo ============================================
echo.

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [x] 未检测到 Python, 请先安装 https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ==^> 安装/更新依赖 ...
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m pip install -r requirements.txt

echo.
echo ==^> 开始打包 ...
python build_exe.py

echo.
if exist "dist\AI学英语.exe" (
    echo [√] 打包成功! 产物位于 dist\AI学英语.exe
    echo     可将整个 dist 目录分发给他人, 双击即可运行。
) else (
    echo [x] 打包似乎未成功, 请检查上方日志。
)
echo.
pause
