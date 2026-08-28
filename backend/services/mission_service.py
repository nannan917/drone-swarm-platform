"""
任务服务
处理飞行任务的创建、下发、执行、监控
"""
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Mission, MissionStatus, Drone
from schemas import MissionCreate
from aop.exception_handler import MissionNotFoundError, DroneNotFoundError
from services.mavlink_service import mavlink_service
from services.ws_manager import ws_manager

logger = logging.getLogger("drone-swarm.mission-service")


class MissionService:
    """飞行任务业务服务"""

    async def create_mission(self, db: AsyncSession, data: MissionCreate) -> Mission:
        """创建飞行任务"""
        mission_id = f"MISSION-{uuid.uuid4().hex[:8].upper()}"
        waypoints_json = json.dumps([wp.model_dump() for wp in data.waypoints], ensure_ascii=False)

        drone_db_id = None
        if data.drone_id:
            result = await db.execute(select(Drone).where(Drone.drone_id == data.drone_id))
            drone = result.scalar_one_or_none()
            if not drone:
                raise DroneNotFoundError(data.drone_id)
            drone_db_id = drone.id

        mission = Mission(
            mission_id=mission_id,
            name=data.name,
            description=data.description,
            drone_id=drone_db_id,
            waypoints=waypoints_json,
            total_waypoints=len(data.waypoints),
            max_altitude=data.max_altitude,
            max_speed=data.max_speed,
            return_to_home_on_complete=data.return_to_home_on_complete,
        )
        db.add(mission)
        await db.flush()

        await ws_manager.broadcast({"type": "mission_created", "mission_id": mission_id})
        logger.info("Mission created: %s (%d waypoints)", mission_id, len(data.waypoints))
        return mission

    async def get_mission(self, db: AsyncSession, mission_id: str) -> Mission:
        result = await db.execute(select(Mission).where(Mission.mission_id == mission_id))
        mission = result.scalar_one_or_none()
        if not mission:
            raise MissionNotFoundError(mission_id)
        return mission

    async def get_all_missions(self, db: AsyncSession, status: str = None,
                                drone_id: str = None) -> List[Mission]:
        query = select(Mission).order_by(Mission.created_at.desc())
        if status:
            query = query.where(Mission.status == status)
        result = await db.execute(query)
        missions = list(result.scalars().all())
        if drone_id:
            missions = [m for m in missions if m.drone and m.drone.drone_id == drone_id]
        return missions

    async def start_mission(self, db: AsyncSession, mission_id: str) -> dict:
        """开始执行任务"""
        mission = await self.get_mission(db, mission_id)
        if mission.status == MissionStatus.RUNNING:
            return {"success": False, "message": "Mission already running"}

        if not mission.drone_id:
            return {"success": False, "message": "No drone assigned to mission"}

        drone = await db.get(Drone, mission.drone_id)
        if not drone:
            return {"success": False, "message": "Assigned drone not found"}

        conn = mavlink_service.get_connection(drone.drone_id)
        if not conn or not conn.is_connected():
            return {"success": False, "message": f"Drone {drone.drone_id} is offline"}

        # 解析航点
        waypoints = json.loads(mission.waypoints) if mission.waypoints else []
        if not waypoints:
            return {"success": False, "message": "Mission has no waypoints"}

        # 更新任务状态
        mission.status = MissionStatus.RUNNING
        mission.started_at = datetime.utcnow()
        mission.current_waypoint = 0

        # 下发第一个航点（模拟）
        first_wp = waypoints[0]
        await conn.send_command("takeoff", {"altitude": first_wp.get("alt", 30)})

        await ws_manager.broadcast({
            "type": "mission_started",
            "mission_id": mission_id,
            "drone_id": drone.drone_id,
        })
        logger.info("Mission %s started on drone %s", mission_id, drone.drone_id)
        return {"success": True, "message": "Mission started", "mission_id": mission_id}

    async def pause_mission(self, db: AsyncSession, mission_id: str) -> dict:
        mission = await self.get_mission(db, mission_id)
        if mission.status != MissionStatus.RUNNING:
            return {"success": False, "message": "Mission is not running"}
        mission.status = MissionStatus.PAUSED
        await ws_manager.broadcast({"type": "mission_paused", "mission_id": mission_id})
        return {"success": True, "message": "Mission paused"}

    async def cancel_mission(self, db: AsyncSession, mission_id: str) -> dict:
        mission = await self.get_mission(db, mission_id)
        mission.status = MissionStatus.CANCELLED
        mission.completed_at = datetime.utcnow()

        # 让无人机返航
        if mission.drone_id:
            drone = await db.get(Drone, mission.drone_id)
            if drone:
                conn = mavlink_service.get_connection(drone.drone_id)
                if conn:
                    await conn.send_command("rtl", {})

        await ws_manager.broadcast({"type": "mission_cancelled", "mission_id": mission_id})
        return {"success": True, "message": "Mission cancelled, drone returning home"}

    async def delete_mission(self, db: AsyncSession, mission_id: str):
        mission = await self.get_mission(db, mission_id)
        if mission.status == MissionStatus.RUNNING:
            return {"success": False, "message": "Cannot delete a running mission"}
        await db.delete(mission)
        await ws_manager.broadcast({"type": "mission_deleted", "mission_id": mission_id})
        return {"success": True}

    async def get_mission_waypoints(self, db: AsyncSession, mission_id: str) -> list:
        mission = await self.get_mission(db, mission_id)
        return json.loads(mission.waypoints) if mission.waypoints else []


# 全局单例
mission_service = MissionService()
