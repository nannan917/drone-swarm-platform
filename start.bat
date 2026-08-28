@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   无人机集群管理平台 - Windows 启动脚本
echo   Drone Swarm Management Platform
echo ============================================
echo.

REM 切换到 backend 目录
cd /d "%~dp0backend"
if errorlevel 1 (
    echo [错误] 无法进入 backend 目录: %~dp0backend
    pause
    exit /b 1
)

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查8000端口是否被占用
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [警告] 端口 8000 已被占用，正在尝试释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

REM 检查虚拟环境，不存在则创建
if not exist "venv\Scripts\python.exe" (
    echo [信息] 创建 Python 虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [信息] 虚拟环境创建完成
)

REM 使用 venv 中的 pip 安装依赖
echo [信息] 检查并安装依赖...
"venv\Scripts\pip.exe" install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

echo.
echo ============================================
echo   平台启动成功！
echo.
echo   前端界面:  http://localhost:8000
echo   API 文档:  http://localhost:8000/docs
echo   健康检查:  http://localhost:8000/api/v1/health
echo.
echo   浏览器将在 3 秒后自动打开...
echo   按 Ctrl+C 停止服务
echo ============================================
echo.

REM 延迟 3 秒后自动打开浏览器（等待服务启动完成）
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

REM 使用 venv 中的 python 启动
"venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败，错误代码: %errorlevel%
    echo 请检查上方错误信息
)

echo.
pause
