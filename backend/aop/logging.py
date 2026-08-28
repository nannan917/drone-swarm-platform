"""
AOP - 日志切面
统一记录请求/响应日志、无人机操作审计日志
"""
import time
import json
import logging
from datetime import datetime
from functools import wraps
from typing import Callable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("drone-swarm")


class LoggingAspect:
    """日志切面：记录方法调用、耗时、参数、返回值"""

    @staticmethod
    def log_method(level: int = logging.INFO, log_args: bool = True, log_result: bool = False):
        """
        方法级日志装饰器
        :param level: 日志级别
        :param log_args: 是否记录参数
        :param log_result: 是否记录返回值
        """
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                method_name = f"{func.__module__}.{func.__qualname__}"
                if log_args:
                    logger.log(level, "[ENTER] %s args=%s kwargs=%s",
                               method_name, _safe_str(args), _safe_str(kwargs))
                try:
                    result = await func(*args, **kwargs)
                    elapsed = (time.time() - start) * 1000
                    logger.log(level, "[EXIT]  %s elapsed=%.2fms", method_name, elapsed)
                    if log_result:
                        logger.log(level, "[RESULT] %s -> %s", method_name, _safe_str(result))
                    return result
                except Exception as e:
                    elapsed = (time.time() - start) * 1000
                    logger.error("[ERROR] %s elapsed=%.2fms error=%s", method_name, elapsed, str(e))
                    raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                method_name = f"{func.__module__}.{func.__qualname__}"
                if log_args:
                    logger.log(level, "[ENTER] %s args=%s kwargs=%s",
                               method_name, _safe_str(args), _safe_str(kwargs))
                try:
                    result = func(*args, **kwargs)
                    elapsed = (time.time() - start) * 1000
                    logger.log(level, "[EXIT]  %s elapsed=%.2fms", method_name, elapsed)
                    return result
                except Exception as e:
                    elapsed = (time.time() - start) * 1000
                    logger.error("[ERROR] %s elapsed=%.2fms error=%s", method_name, elapsed, str(e))
                    raise

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator

    @staticmethod
    def audit(action: str, resource: str = "drone"):
        """
        审计日志装饰器：记录关键操作（如无人机解锁、起飞、任务下发）
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                logger.info(
                    "[AUDIT] action=%s resource=%s args=%s at=%s",
                    action, resource, _safe_str(kwargs), datetime.utcnow().isoformat()
                )
                return result
            return wrapper
        return decorator


def _safe_str(obj, max_len: int = 500) -> str:
    """安全转字符串，避免敏感信息和超长输出"""
    try:
        s = json.dumps(obj, default=str, ensure_ascii=False) if not isinstance(obj, str) else obj
        return s[:max_len] + "..." if len(s) > max_len else s
    except Exception:
        return str(obj)[:max_len]
