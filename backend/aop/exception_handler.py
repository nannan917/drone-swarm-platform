"""
AOP - 全局异常处理切面
统一异常捕获、错误码映射、友好响应
"""
import logging
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("drone-swarm")


class ExceptionAspect(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # FastAPI自带异常，直接透传
            raise e
        except Exception as e:
            logger.error("[UNHANDLED] path=%s method=%s error=%s",
                         request.url.path, request.method, str(e), exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": str(e),
                    "path": request.url.path,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )


class DronePlatformError(Exception):
    """平台自定义异常基类"""
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class DroneNotFoundError(DronePlatformError):
    def __init__(self, drone_id: str):
        super().__init__("drone_not_found", f"Drone {drone_id} not found", 404)


class DroneOfflineError(DronePlatformError):
    def __init__(self, drone_id: str):
        super().__init__("drone_offline", f"Drone {drone_id} is offline", 409)


class DroneBusyError(DronePlatformError):
    def __init__(self, drone_id: str):
        super().__init__("drone_busy", f"Drone {drone_id} is busy", 409)


class MissionNotFoundError(DronePlatformError):
    def __init__(self, mission_id: str):
        super().__init__("mission_not_found", f"Mission {mission_id} not found", 404)


class ARPResolutionError(DronePlatformError):
    def __init__(self, drone_id: str):
        super().__init__("arp_resolution_failed", f"Failed to resolve address for drone {drone_id}", 502)


def register_exception_handlers(app):
    """注册自定义异常处理器"""
    @app.exception_handler(DronePlatformError)
    async def drone_platform_error_handler(request: Request, exc: DronePlatformError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
