#!/bin/bash
# 无人机集群管理平台 - Linux/Mac 启动脚本

echo "============================================"
echo "  无人机集群管理平台 - 启动脚本"
echo "  Drone Swarm Management Platform"
echo "============================================"
echo ""

cd "$(dirname "$0")/backend"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到python3，请先安装Python 3.9+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 创建Python虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "[信息] 检查并安装依赖..."
pip install -r requirements.txt -q

echo ""
echo "============================================"
echo "  平台启动中..."
echo "  前端界面: http://localhost:8000"
echo "  API文档:  http://localhost:8000/docs"
echo "  按 Ctrl+C 停止服务"
echo "============================================"
echo ""

python3 main.py
