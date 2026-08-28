# 无人机集群管理平台

Drone Swarm Management Platform — 支持多无人机接入、实时遥测、飞行任务与编队控制的全栈管理平台。

## 功能特性

### 核心能力
- **多无人机管理** — 同时接入和管理多达 50 架无人机，统一注册、状态监控
- **实时遥测** — WebSocket 推送位置、姿态、电池、GPS 等数据，延迟 < 500ms
- **地图可视化** — 基于 Leaflet 的暗色地图，无人机标记、飞行轨迹、弹窗详情
- **飞行任务** — 航点任务创建、下发、执行监控、暂停/取消
- **编队控制** — 编队组管理、长机设置、批量起飞/降落/返航
- **事件日志** — 完整的操作审计与系统事件记录

### AOP — 面向切面编程
平台实现了完整的 AOP 横切关注点分离：

| 切面 | 功能 |
|------|------|
| `LoggingAspect` | 方法调用日志、耗时统计、参数/返回值记录、审计日志 |
| `AuthAspect` | API Token 校验、白名单路径、WebSocket 鉴权 |
| `MetricsAspect` | 接口 QPS、耗时、错误率统计，可通过 `/api/v1/system/metrics` 查看 |
| `ExceptionAspect` | 全局异常捕获、自定义异常体系、统一错误响应格式 |

### ARP — 无人机地址解析注册协议
类比网络 ARP 协议，实现无人机逻辑 ID 到通信地址的动态解析：

- **ARP Request** — `drone_id` → `(sys_id, connection_type, connection_address)`
- **ARP Reply** — 返回解析结果并缓存
- **Gratuitous ARP** — 无人机注册/心跳时主动宣告地址
- **ARP Table** — 带 TTL 老化的映射表，持久化到 JSON 文件
- **地址自动分配** — 自动分配 MAVLink System ID（10-250）

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLAlchemy 2.0 + aiosqlite（异步） |
| 实时通信 | WebSocket |
| 无人机协议 | MAVLink（pymavlink） |
| 前端 | 原生 HTML/CSS/JS + Leaflet 地图 |
| 设计模式 | AOP 面向切面、单例、依赖注入 |

## 项目结构

```
drone-swarm-platform/
├── backend/
│   ├── main.py                 # 应用入口
│   ├── config.py               # 全局配置
│   ├── database.py             # 数据库连接
│   ├── models.py               # SQLAlchemy 数据模型
│   ├── schemas.py              # Pydantic 请求/响应 Schema
│   ├── requirements.txt        # Python 依赖
│   ├── aop/                    # AOP 面向切面编程模块
│   │   ├── __init__.py
│   │   ├── logging.py          # 日志切面
│   │   ├── auth.py             # 鉴权切面
│   │   ├── metrics.py          # 性能监控切面
│   │   └── exception_handler.py # 异常处理切面
│   ├── arp/                    # ARP 地址解析协议模块
│   │   ├── __init__.py
│   │   └── resolver.py         # ARP 解析器核心
│   ├── services/               # 业务服务层
│   │   ├── __init__.py
│   │   ├── drone_service.py    # 无人机服务
│   │   ├── mission_service.py  # 任务服务
│   │   ├── swarm_service.py    # 编队服务
│   │   ├── mavlink_service.py  # MAVLink 通信服务
│   │   └── ws_manager.py       # WebSocket 连接管理
│   └── api/                    # API 路由层
│       ├── __init__.py
│       ├── drones.py           # 无人机 API
│       ├── missions.py         # 任务 API
│       ├── swarm.py            # 编队 API
│       ├── arp.py              # ARP API
│       ├── system.py           # 系统 API
│       └── ws.py               # WebSocket 端点
├── frontend/
│   ├── index.html              # 主页面
│   ├── css/style.css           # 样式（深色科技风）
│   └── js/
│       ├── app.js              # 主应用逻辑
│       ├── map.js              # 地图模块
│       ├── drone-panel.js      # 无人机面板
│       └── mission-panel.js    # 任务/编队面板
├── data/                       # 数据目录（数据库、ARP表）
├── start.bat                   # Windows 启动脚本
├── start.sh                    # Linux/Mac 启动脚本
└── README.md
```

## 快速开始

### 环境要求
- Python 3.9+
- 现代浏览器（Chrome / Edge / Firefox）

### 方式一：使用启动脚本（推荐）

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 方式二：手动启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

### 访问平台

启动后打开浏览器访问：

- **前端界面**: http://localhost:8000
- **API 文档 (Swagger)**: http://localhost:8000/docs
- **ReDoc 文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/api/v1/health

## API 概览

### 无人机管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/drones` | 注册无人机 |
| GET | `/api/v1/drones` | 获取无人机列表 |
| GET | `/api/v1/drones/{id}` | 获取无人机详情 |
| PUT | `/api/v1/drones/{id}` | 更新无人机信息 |
| DELETE | `/api/v1/drones/{id}` | 删除无人机 |
| POST | `/api/v1/drones/{id}/command` | 发送控制指令 |

**控制指令类型:** `arm` / `disarm` / `takeoff` / `land` / `rtl` / `go_to` / `set_mode`

### 飞行任务
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/missions` | 创建任务 |
| GET | `/api/v1/missions` | 任务列表 |
| POST | `/api/v1/missions/{id}/start` | 开始任务 |
| POST | `/api/v1/missions/{id}/pause` | 暂停任务 |
| POST | `/api/v1/missions/{id}/cancel` | 取消任务 |

### 编队控制
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/swarm/groups` | 创建编队组 |
| GET | `/api/v1/swarm/groups` | 编队组列表 |
| POST | `/api/v1/swarm/groups/{id}/command` | 批量指令 |

### ARP 协议
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/arp/table` | 查看 ARP 表 |
| POST | `/api/v1/arp/resolve` | 地址解析 |
| POST | `/api/v1/arp/cleanup` | 清理过期条目 |

### 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/system/stats` | 平台统计 |
| GET | `/api/v1/system/events` | 事件日志 |
| GET | `/api/v1/system/metrics` | AOP 性能指标 |

### WebSocket
- `ws://localhost:8000/ws/telemetry` — 实时遥测数据流

## 使用示例

### 1. 注册无人机
```bash
curl -X POST http://localhost:8000/api/v1/drones \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "DRONE-001",
    "name": "侦察一号",
    "model": "Generic Quadcopter",
    "connection_type": "udp",
    "connection_address": "127.0.0.1:14550"
  }'
```

### 2. 发送起飞指令
```bash
curl -X POST http://localhost:8000/api/v1/drones/DRONE-001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "takeoff", "params": {"altitude": 30}}'
```

### 3. 创建飞行任务
```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "区域巡逻",
    "drone_id": "DRONE-001",
    "waypoints": [
      {"lat": 22.5431, "lon": 113.9440, "alt": 50, "speed": 10},
      {"lat": 22.5450, "lon": 113.9460, "alt": 80, "speed": 12}
    ]
  }'
```

## 连接真实无人机

当前 MAVLink 服务内置模拟模式，可直接用于演示和开发。连接真实飞控（PX4/ArduPilot）时：

1. 确保飞控通过 USB/数传连接到电脑
2. 在注册无人机时填写正确的连接地址：
   - **串口**: `connection_type: "serial"`, `connection_address: "COM3"` (Windows) 或 `/dev/ttyUSB0` (Linux)
   - **UDP**: `connection_type: "udp"`, `connection_address: "192.168.1.10:14550"`
3. 修改 `mavlink_service.py` 中的 `MAVLinkConnection` 类，启用真实的 pymavlink 连接

## 配置说明

复制 `.env.example` 为 `.env` 并修改：

```bash
cp backend/.env.example backend/.env
```

主要配置项：
- `MAX_DRONES` — 最大接入无人机数
- `HEARTBEAT_TIMEOUT` — 心跳超时时间（秒）
- `TELEMETRY_INTERVAL` — 遥测推送间隔（秒）
- `ARP_CACHE_TTL` — ARP 缓存过期时间（秒）
- `API_TOKEN` — API 访问令牌

## 许可证

MIT License
