"""
任务 API 路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import MissionCreate, MissionResponse
from services.mission_service import mission_service

router = APIRouter(prefix="/missions", tags=["missions"])


@router.post("", response_model=MissionResponse, summary="创建飞行任务")
async def create_mission(data: MissionCreate, db: AsyncSession = Depends(get_db)):
    return await mission_service.create_mission(db, data)


@router.get("", response_model=List[MissionResponse], summary="获取任务列表")
async def list_missions(
    status: Optional[str] = Query(None),
    drone_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await mission_service.get_all_missions(db, status, drone_id)


@router.get("/{mission_id}", response_model=MissionResponse, summary="获取任务详情")
async def get_mission(mission_id: str, db: AsyncSession = Depends(get_db)):
    return await mission_service.get_mission(db, mission_id)


@router.get("/{mission_id}/waypoints", summary="获取任务航点列表")
async def get_waypoints(mission_id: str, db: AsyncSession = Depends(get_db)):
    waypoints = await mission_service.get_mission_waypoints(db, mission_id)
    return {"mission_id": mission_id, "waypoints": waypoints, "count": len(waypoints)}


@router.post("/{mission_id}/start", summary="开始执行任务")
async def start_mission(mission_id: str, db: AsyncSession = Depends(get_db)):
    return await mission_service.start_mission(db, mission_id)


@router.post("/{mission_id}/pause", summary="暂停任务")
async def pause_mission(mission_id: str, db: AsyncSession = Depends(get_db)):
    return await mission_service.pause_mission(db, mission_id)


@router.post("/{mission_id}/cancel", summary="取消任务")
async def cancel_mission(mission_id: str, db: AsyncSession = Depends(get_db)):
    return await mission_service.cancel_mission(db, mission_id)


@router.delete("/{mission_id}", summary="删除任务")
async def delete_mission(mission_id: str, db: AsyncSession = Depends(get_db)):
    return await mission_service.delete_mission(db, mission_id)
