"""
编队服务
处理无人机编队组的管理和编队控制
"""
import logging
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SwarmGroup, Drone
from schemas import SwarmGroupCreate, SwarmCommand
from services.mavlink_service import mavlink_service
from services.ws_manager import ws_manager

logger = logging.getLogger("drone-swarm.swarm-service")


class SwarmService:
    """编队业务服务"""

    async def create_group(self, db: AsyncSession, data: SwarmGroupCreate) -> SwarmGroup:
        group = SwarmGroup(
            group_id=data.group_id,
            name=data.name,
            formation_type=data.formation_type,
            description=data.description,
        )
        db.add(group)
        await db.flush()
        await ws_manager.broadcast({"type": "swarm_group_created", "group_id": data.group_id})
        return group

    async def get_all_groups(self, db: AsyncSession) -> List[SwarmGroup]:
        result = await db.execute(select(SwarmGroup).order_by(SwarmGroup.created_at.desc()))
        return list(result.scalars().all())

    async def get_group(self, db: AsyncSession, group_id: str) -> SwarmGroup:
        result = await db.execute(select(SwarmGroup).where(SwarmGroup.group_id == group_id))
        group = result.scalar_one_or_none()
        if not group:
            from aop.exception_handler import DronePlatformError
            raise DronePlatformError("group_not_found", f"Group {group_id} not found", 404)
        return group

    async def get_group_members(self, db: AsyncSession, group_id: str) -> List[Drone]:
        result = await db.execute(select(Drone).where(Drone.group_id == group_id))
        return list(result.scalars().all())

    async def set_leader(self, db: AsyncSession, group_id: str, drone_id: str) -> dict:
        group = await self.get_group(db, group_id)
        result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
        drone = result.scalar_one_or_none()
        if not drone:
            from aop.exception_handler import DroneNotFoundError
            raise DroneNotFoundError(drone_id)

        # 取消原长机
        old_leader = await db.execute(select(Drone).where(Drone.group_id == group_id, Drone.is_leader == True))
        for d in old_leader.scalars().all():
            d.is_leader = False

        drone.is_leader = True
        drone.group_id = group_id
        group.leader_drone_id = drone_id
        group.member_count = len(await self.get_group_members(db, group_id))

        await ws_manager.broadcast({"type": "swarm_leader_changed", "group_id": group_id, "drone_id": drone_id})
        return {"success": True, "message": f"{drone_id} is now leader of {group_id}"}

    async def add_drone_to_group(self, db: AsyncSession, group_id: str, drone_id: str) -> dict:
        group = await self.get_group(db, group_id)
        result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
        drone = result.scalar_one_or_none()
        if not drone:
            from aop.exception_handler import DroneNotFoundError
            raise DroneNotFoundError(drone_id)
        drone.group_id = group_id
        group.member_count = len(await self.get_group_members(db, group_id))
        return {"success": True, "message": f"{drone_id} added to {group_id}"}

    async def remove_drone_from_group(self, db: AsyncSession, group_id: str, drone_id: str) -> dict:
        result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
        drone = result.scalar_one_or_none()
        if drone:
            drone.group_id = None
            drone.is_leader = False
        group = await self.get_group(db, group_id)
        group.member_count = len(await self.get_group_members(db, group_id))
        return {"success": True}

    async def execute_swarm_command(self, db: AsyncSession, group_id: str, cmd: SwarmCommand) -> dict:
        """执行编队指令（批量控制）"""
        members = await self.get_group_members(db, group_id)
        if not members:
            return {"success": False, "message": "Group has no members"}

        drone_ids = [d.drone_id for d in members]
        results = await mavlink_service.broadcast_command(cmd.command, cmd.params, drone_ids)
        await ws_manager.broadcast({
            "type": "swarm_command",
            "group_id": group_id,
            "command": cmd.command,
            "drone_ids": drone_ids,
        })
        return {"success": True, "results": results, "affected": len(drone_ids)}

    async def delete_group(self, db: AsyncSession, group_id: str):
        group = await self.get_group(db, group_id)
        # 解除所有成员
        members = await self.get_group_members(db, group_id)
        for d in members:
            d.group_id = None
            d.is_leader = False
        await db.delete(group)
        await ws_manager.broadcast({"type": "swarm_group_deleted", "group_id": group_id})


# 全局单例
swarm_service = SwarmService()
