"""
无人机集群管理平台 - 主入口
Drone Swarm Management Platform

技术栈:
- FastAPI (后端框架)
- SQLAlchemy + aiosqlite (异步数据库)
- WebSocket (实时遥测推送)
- MAVLink (无人机通信协议)
- AOP (面向切面编程: 日志/鉴权/监控/异常)
- ARP (无人机地址解析注册协议)
"""
import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 确保backend目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from database import init_db
from aop.exception_handler import ExceptionAspect, register_exception_handlers
from aop.logging import logger
from api.drones import router as drones_router
from api.missions import router as missions_router
from api.swarm import router as swarm_router
from api.arp import router as arp_router
from api.system import router as system_router
from api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时清理资源"""
    logger.info("=" * 60)
    logger.info("  Drone Swarm Management Platform starting...")
    logger.info("  Version: %s", settings.APP_VERSION)
    logger.info("  Max drones: %d", settings.MAX_DRONES)
    logger.info("  AOP: Logging / Auth / Metrics / Exception aspects loaded")
    logger.info("  ARP: Drone Address Resolution Protocol loaded")
    logger.info("=" * 60)

    # 初始化数据库
    await init_db()
    logger.info("Database initialized")

    # 启动后台任务：ARP表定期清理
    arp_cleanup_task = asyncio.create_task(_arp_cleanup_loop())

    yield

    # 关闭清理
    arp_cleanup_task.cancel()
    from services.mavlink_service import mavlink_service
    for drone_id in list(mavlink_service.get_all_connections().keys()):
        await mavlink_service.disconnect_drone(drone_id)
    logger.info("Platform shutdown complete")


async def _arp_cleanup_loop():
    """ARP表定期老化清理"""
    from arp.resolver import arp_resolver
    while True:
        await asyncio.sleep(60)  # 每分钟清理一次
        try:
            arp_resolver.cleanup_expired()
        except Exception as e:
            logger.error("ARP cleanup error: %s", str(e))


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
        无人机集群管理平台 API

        ## 核心特性
        - **多无人机管理**: 支持同时接入和管理多架无人机
        - **AOP面向切面编程**: 统一日志、鉴权、性能监控、异常处理
        - **ARP地址解析协议**: 无人机ID到通信地址的动态解析与注册
        - **实时遥测**: WebSocket推送无人机位置、姿态、电池等数据
        - **飞行任务**: 航点任务创建、下发、执行监控
        - **编队控制**: 编队组管理、长机设置、批量指令

        ## 快速开始
        1. 注册无人机: POST /api/v1/drones
        2. 发送指令: POST /api/v1/drones/{drone_id}/command
        3. 查看实时数据: 连接 ws://host:8000/ws/telemetry
        """,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # AOP 全局异常处理中间件
    app.add_middleware(ExceptionAspect)

    # 注册自定义异常处理器
    register_exception_handlers(app)

    # 注册API路由
    api_prefix = "/api/v1"
    app.include_router(drones_router, prefix=api_prefix)
    app.include_router(missions_router, prefix=api_prefix)
    app.include_router(swarm_router, prefix=api_prefix)
    app.include_router(arp_router, prefix=api_prefix)
    app.include_router(system_router, prefix=api_prefix)
    app.include_router(ws_router)

    # 静态文件 - 前端界面
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    if os.path.exists(frontend_dir):
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

        @app.get("/", summary="前端界面")
        async def serve_frontend():
            """返回无人机集群管理平台前端界面"""
            return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/api/v1/health", tags=["system"], summary="健康检查")
    async def root_health():
        return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
