"""
AOP - 鉴权切面
统一API访问控制、Token校验、权限检查
"""
from functools import wraps
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from config import settings


class AuthAspect:
    """鉴权切面：Token校验、角色权限、操作权限"""

    # 白名单路径（无需鉴权）
    WHITELIST_PATHS = {
        "/", "/docs", "/redoc", "/openapi.json",
        "/api/v1/health", "/ws/telemetry",
    }

    @staticmethod
    def require_token(func: Callable):
        """要求有效API Token的装饰器"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                # 从args中找Request
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request and request.url.path not in AuthAspect.WHITELIST_PATHS:
                token = request.headers.get("X-API-Token", "")
                if not token:
                    # 也支持query参数
                    token = request.query_params.get("token", "")

                if token != settings.API_TOKEN:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or missing API token",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            return await func(*args, **kwargs)
        return wrapper

    @staticmethod
    def require_role(roles: list):
        """要求特定角色的装饰器（预留扩展）"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 预留：从Token或Session中解析角色
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    async def verify_websocket_token(websocket) -> bool:
        """WebSocket连接Token校验"""
        token = websocket.query_params.get("token", "")
        return token == settings.API_TOKEN or token == ""  # 开发模式允许空token
