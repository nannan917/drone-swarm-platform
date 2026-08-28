"""
无人机 API 路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import (
    DroneCreate, DroneUpdate, DroneResponse, DroneCommand,
    DroneTelemetry, EventLogResponse,
)
from services.drone_service import drone_service

router = APIRouter(prefix="/drones", tags=["drones"])


@router.post("", response_model=DroneResponse, summary="注册新无人机")
async def register_drone(data: DroneCreate, db: AsyncSession = Depends(get_db)):
    """注册一架新无人机，自动完成ARP地址解析和MAVLink连接"""
    return await drone_service.register_drone(db, data)


@router.get("", response_model=List[DroneResponse], summary="获取无人机列表")
async def list_drones(
    status: Optional[str] = Query(None, description="按状态筛选"),
    group_id: Optional[str] = Query(None, description="按编队组筛选"),
    db: AsyncSession = Depends(get_db),
):
    return await drone_service.get_all_drones(db, status, group_id)


@router.get("/{drone_id}", response_model=DroneResponse, summary="获取无人机详情")
async def get_drone(drone_id: str, db: AsyncSession = Depends(get_db)):
    return await drone_service.get_drone(db, drone_id)


@router.put("/{drone_id}", response_model=DroneResponse, summary="更新无人机信息")
async def update_drone(drone_id: str, data: DroneUpdate, db: AsyncSession = Depends(get_db)):
    return await drone_service.update_drone(db, drone_id, data)


@router.delete("/{drone_id}", summary="删除无人机")
async def delete_drone(drone_id: str, db: AsyncSession = Depends(get_db)):
    await drone_service.delete_drone(db, drone_id)
    return {"success": True, "message": f"Drone {drone_id} deleted"}


@router.post("/{drone_id}/command", summary="发送控制指令")
async def send_command(drone_id: str, cmd: DroneCommand, db: AsyncSession = Depends(get_db)):
    """
    支持的指令:
    - arm: 解锁电机
    - disarm: 上锁电机
    - takeoff: 起飞 (params: altitude)
    - land: 降落
    - rtl: 返航
    - go_to: 飞往目标点 (params: latitude, longitude, altitude)
    - set_mode: 设置飞行模式 (params: mode)
    """
    return await drone_service.send_command(db, drone_id, cmd)


@router.get("/{drone_id}/events", response_model=List[EventLogResponse], summary="获取无人机事件日志")
async def get_drone_events(
    drone_id: str,
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await drone_service.get_event_logs(db, limit, drone_id)
