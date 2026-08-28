"""
AOP - 性能监控切面
统计接口耗时、QPS、错误率，输出到日志和内存指标
"""
import time
import threading
from collections import defaultdict
from functools import wraps
from typing import Callable, Dict


class MetricsAspect:
    """性能监控切面：记录方法调用指标"""

    _metrics: Dict[str, dict] = defaultdict(lambda: {
        "count": 0, "errors": 0, "total_time": 0.0, "min_time": float("inf"), "max_time": 0.0
    })
    _lock = threading.Lock()

    @staticmethod
    def monitor(func: Callable):
        """方法性能监控装饰器"""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            key = f"{func.__module__}.{func.__qualname__}"
            try:
                result = await func(*args, **kwargs)
                MetricsAspect._record(key, time.time() - start, error=False)
                return result
            except Exception:
                MetricsAspect._record(key, time.time() - start, error=True)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            key = f"{func.__module__}.{func.__qualname__}"
            try:
                result = func(*args, **kwargs)
                MetricsAspect._record(key, time.time() - start, error=False)
                return result
            except Exception:
                MetricsAspect._record(key, time.time() - start, error=True)
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    @staticmethod
    def _record(key: str, elapsed: float, error: bool):
        with MetricsAspect._lock:
            m = MetricsAspect._metrics[key]
            m["count"] += 1
            if error:
                m["errors"] += 1
            m["total_time"] += elapsed
            m["min_time"] = min(m["min_time"], elapsed)
            m["max_time"] = max(m["max_time"], elapsed)

    @staticmethod
    def get_all_metrics() -> Dict[str, dict]:
        """获取所有监控指标"""
        with MetricsAspect._lock:
            result = {}
            for key, m in MetricsAspect._metrics.items():
                avg = m["total_time"] / m["count"] if m["count"] > 0 else 0
                result[key] = {
                    "count": m["count"],
                    "errors": m["errors"],
                    "error_rate": m["errors"] / m["count"] if m["count"] > 0 else 0,
                    "avg_time_ms": round(avg * 1000, 2),
                    "min_time_ms": round(m["min_time"] * 1000, 2) if m["count"] > 0 else 0,
                    "max_time_ms": round(m["max_time"] * 1000, 2),
                }
            return result

    @staticmethod
    def reset():
        """重置所有指标"""
        with MetricsAspect._lock:
            MetricsAspect._metrics.clear()
