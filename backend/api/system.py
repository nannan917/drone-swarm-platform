"""
系统 API 路由 - 健康检查、统计、事件日志、AOP指标
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import PlatformStats, EventLogResponse
from services.drone_service import drone_service
from aop.metrics import MetricsAspect

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", summary="健康检查")
async def health_check():
    return {
        "status": "healthy",
        "service": "Drone Swarm Management Platform",
        "version": "1.0.0",
    }


@router.get("/stats", response_model=PlatformStats, summary="平台统计数据")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await drone_service.get_stats(db)


@router.get("/events", response_model=List[EventLogResponse], summary="系统事件日志")
async def get_events(limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await drone_service.get_event_logs(db, limit)


@router.get("/metrics", summary="AOP性能监控指标")
async def get_metrics():
    """获取AOP MetricsAspect收集的接口性能指标"""
    return MetricsAspect.get_all_metrics()


@router.post("/metrics/reset", summary="重置性能指标")
async def reset_metrics():
    MetricsAspect.reset()
    return {"success": True, "message": "Metrics reset"}
