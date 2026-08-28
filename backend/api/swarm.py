"""
编队 API 路由
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import SwarmGroupCreate, SwarmGroupResponse, SwarmCommand, DroneResponse
from services.swarm_service import swarm_service

router = APIRouter(prefix="/swarm", tags=["swarm"])


@router.post("/groups", response_model=SwarmGroupResponse, summary="创建编队组")
async def create_group(data: SwarmGroupCreate, db: AsyncSession = Depends(get_db)):
    return await swarm_service.create_group(db, data)


@router.get("/groups", response_model=List[SwarmGroupResponse], summary="获取所有编队组")
async def list_groups(db: AsyncSession = Depends(get_db)):
    return await swarm_service.get_all_groups(db)


@router.get("/groups/{group_id}", response_model=SwarmGroupResponse, summary="获取编队组详情")
async def get_group(group_id: str, db: AsyncSession = Depends(get_db)):
    return await swarm_service.get_group(db, group_id)


@router.get("/groups/{group_id}/members", response_model=List[DroneResponse], summary="获取编组成员")
async def get_members(group_id: str, db: AsyncSession = Depends(get_db)):
    return await swarm_service.get_group_members(db, group_id)


@router.post("/groups/{group_id}/members/{drone_id}", summary="添加无人机到编组")
async def add_member(group_id: str, drone_id: str, db: AsyncSession = Depends(get_db)):
    return await swarm_service.add_drone_to_group(db, group_id, drone_id)


@router.delete("/groups/{group_id}/members/{drone_id}", summary="从编组移除无人机")
async def remove_member(group_id: str, drone_id: str, db: AsyncSession = Depends(get_db)):
    return await swarm_service.remove_drone_from_group(db, group_id, drone_id)


@router.post("/groups/{group_id}/leader/{drone_id}", summary="设置长机")
async def set_leader(group_id: str, drone_id: str, db: AsyncSession = Depends(get_db)):
    return await swarm_service.set_leader(db, group_id, drone_id)


@router.post("/groups/{group_id}/command", summary="执行编队批量指令")
async def swarm_command(group_id: str, cmd: SwarmCommand, db: AsyncSession = Depends(get_db)):
    """
    批量指令: takeoff_all / land_all / rtl_all / formation_change
    """
    return await swarm_service.execute_swarm_command(db, group_id, cmd)


@router.delete("/groups/{group_id}", summary="删除编队组")
async def delete_group(group_id: str, db: AsyncSession = Depends(get_db)):
    await swarm_service.delete_group(db, group_id)
    return {"success": True}
