# 无人机集群管理平台 - 部署指南

本文档说明如何将本平台部署到其他电脑上运行。

---

## 方式一：直接复制项目（推荐，最简单）

### 适用场景
目标电脑已安装 Python 3.9+，希望快速部署。

### 步骤

1. **复制项目文件夹**
   将整个 `drone-swarm-platform` 文件夹复制到目标电脑的任意位置（如 `D:\drone-swarm-platform`）。

   > 注意：可以删除 `backend\venv` 文件夹（虚拟环境），因为它是针对当前电脑的，复制到其他电脑可能不兼容。删除后启动脚本会自动重建。

2. **确保目标电脑已安装 Python**
   - 下载地址：https://www.python.org/downloads/
   - 版本要求：Python 3.9 或更高（推荐 3.11/3.12/3.13）
   - 安装时**务必勾选 "Add Python to PATH"**

   验证安装：打开命令行输入 `python --version`，显示版本号即成功。

3. **双击启动**
   进入项目文件夹，双击 `start.bat`。
   - 脚本会自动创建虚拟环境
   - 自动安装所有依赖（fastapi、uvicorn、sqlalchemy、pymavlink 等）
   - 启动服务并自动打开浏览器

4. **访问平台**
   - 前端界面：http://localhost:8000
   - API 文档：http://localhost:8000/docs

---

## 方式二：打包成 EXE（目标电脑无需 Python）

### 适用场景
目标电脑没有安装 Python，或希望分发为独立可执行文件。

### 步骤

1. **在开发电脑上安装 PyInstaller**
   ```bash
   cd drone-swarm-platform\backend
   venv\Scripts\pip.exe install pyinstaller
   ```

2. **创建打包配置**
   在 `backend` 目录下创建 `build.spec`：
   ```python
   # -*- mode: python ; coding: utf-8 -*-
   import os

   block_cipher = None
   backend_dir = os.path.abspath('.')
   frontend_dir = os.path.abspath('../frontend')

   a = Analysis(
       ['main.py'],
       pathex=[backend_dir],
       binaries=[],
       datas=[
           (frontend_dir, 'frontend'),  # 打包前端静态文件
       ],
       hiddenimports=[
           'uvicorn.logging',
           'uvicorn.loops',
           'uvicorn.loops.auto',
           'uvicorn.protocols',
           'uvicorn.protocols.http.auto',
           'uvicorn.protocols.websockets.auto',
           'aiosqlite',
           'pymavlink',
       ],
       hookspath=[],
       runtime_hooks=[],
       excludes=[],
       win_no_prefer_redirects=False,
       win_private_assemblies=False,
       cipher=block_cipher,
       noarchive=False,
   )

   pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

   exe = EXE(
       pyz,
       a.scripts,
       a.binaries,
       a.zipfiles,
       a.datas,
       [],
       name='DroneSwarmPlatform',
       debug=False,
       bootloader_ignore_signals=False,
       strip=False,
       upx=True,
       upx_exclude=[],
       runtime_tmpdir=None,
       console=True,
       disable_windowed_traceback=False,
       argv_emulation=False,
       target_arch=None,
       codesign_identity=None,
       entitlements_file=None,
   )
   ```

3. **执行打包**
   ```bash
   venv\Scripts\pyinstaller.exe build.spec --clean
   ```

4. **分发**
   打包完成后，在 `dist` 目录下生成 `DroneSwarmPlatform.exe`。
   将该 exe 文件复制到目标电脑，双击即可运行（无需安装 Python）。

   > 注意：打包后的 exe 体积较大（约 50-100MB），因为包含了 Python 运行时和所有依赖。

---

## 方式三：Docker 部署（适合服务器/多机统一管理）

### 适用场景
部署到 Linux 服务器，或需要容器化管理。

### 步骤

1. **在项目根目录创建 `Dockerfile`**
   ```dockerfile
   FROM python:3.12-slim

   WORKDIR /app

   # 安装系统依赖
   RUN apt-get update && apt-get install -y --no-install-recommends \
       gcc \
       && rm -rf /var/lib/apt/lists/*

   # 复制后端代码
   COPY backend/ /app/backend/
   COPY frontend/ /app/frontend/

   WORKDIR /app/backend

   # 安装 Python 依赖
   RUN pip install --no-cache-dir -r requirements.txt

   # 暴露端口
   EXPOSE 8000

   # 启动
   CMD ["python", "main.py"]
   ```

2. **构建镜像**
   ```bash
   docker build -t drone-swarm-platform .
   ```

3. **运行容器**
   ```bash
   docker run -d \
     --name drone-swarm \
     -p 8000:8000 \
     -v $(pwd)/data:/app/backend/data \
     drone-swarm-platform
   ```

4. **访问**
   http://服务器IP:8000

---

## 真实无人机连接配置

部署到其他电脑后，连接真实无人机需要配置正确的连接地址：

### UDP 连接（数传电台/WiFi）
- 连接类型选择 `udp`
- 连接地址格式：`飞控IP:端口`，如 `192.168.1.10:14550`
- 地面端数传插入电脑后，通常会虚拟为串口，需要用数传配置工具设置为 UDP 模式

### 串口连接（USB 直连）
- **Windows**：连接类型 `serial`，地址如 `COM3`、`COM5`
  - 查看端口号：设备管理器 → 端口(COM和LPT)
- **Linux**：地址如 `/dev/ttyUSB0`、`/dev/ttyACM0`
  - 查看端口：`ls /dev/ttyUSB* /dev/ttyACM*`
- 波特率默认 57600，可在 `config.py` 中修改 `MAVLINK_BAUDRATE`

### 多架无人机
每架无人机需要独立的连接地址：
- **串口方式**：每架无人机需要一个独立的 USB 串口（如 COM3、COM4、COM5）
- **UDP方式**：每架无人机使用不同的端口（如 14550、14551、14552）
- 在平台中分别注册，填写各自的连接地址即可

### 连接模式说明
- 注册无人机时，如果连接类型是 `udp`/`tcp`/`serial`，平台会**优先尝试真实连接**
- 真实连接失败（如飞控未连接、地址错误、超时）时，会**自动 fallback 到模拟模式**
- 在无人机详情面板可以看到当前连接模式（绿色"真实连接" / 橙色"模拟模式"）
- 强制使用模拟模式：注册时连接类型填写 `simulation`

---

## 常见问题

### Q: 双击 start.bat 后窗口一闪而过
A: 右键 start.bat → 编辑，在最后一行 `pause` 前加一行 `echo 错误代码: %errorlevel%`，保存后重新运行，查看错误信息。常见原因：
- Python 未安装或未加入 PATH
- 依赖安装失败（网络问题）

### Q: 提示 "Address already in use" 或端口被占用
A: 8000 端口被其他程序占用。解决方法：
- 关闭占用 8000 端口的程序
- 或修改 `backend\config.py` 中的 `PORT` 为其他端口（如 8080）

### Q: 真实无人机连接不上，一直显示模拟模式
A: 排查步骤：
1. 确认飞控已通电、数传已连接
2. 确认串口号/IP地址和端口正确
3. 确认波特率匹配（PX4 默认 57600）
4. 在 QGroundControl 中测试能否连接飞控
5. 查看平台控制台输出的连接错误信息

### Q: 如何修改默认地图中心
A: 编辑 `frontend\js\map.js`，修改 `DEFAULT_CENTER` 的经纬度坐标。

### Q: 数据存在哪里
A: 所有数据存在 `backend\data\` 目录：
- `drone_swarm.db`：SQLite 数据库（无人机、任务、日志等）
- `arp_table.json`：ARP 地址解析表缓存
- 迁移到其他电脑时，复制此文件夹可保留历史数据

---

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| Python | 3.9+ | 3.11+ |
| 内存 | 2GB | 4GB+ |
| 磁盘 | 500MB | 2GB+ |
| 网络 | 局域网（连接无人机） | 千兆网卡 |
| 浏览器 | Chrome 90+ / Edge 90+ | Chrome 最新版 |
