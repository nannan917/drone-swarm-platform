"""
无人机服务
处理无人机的注册、查询、状态更新、控制指令等业务逻辑
"""
import json
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Drone, DroneStatus, EventLog, TelemetryLog
from schemas import DroneCreate, DroneUpdate, DroneCommand, PlatformStats
from aop.exception_handler import DroneNotFoundError, DroneOfflineError
from arp.resolver import arp_resolver
from services.mavlink_service import mavlink_service
from services.ws_manager import ws_manager

logger = logging.getLogger("drone-swarm.drone-service")


class DroneService:
    """无人机业务服务"""

    async def register_drone(self, db: AsyncSession, data: DroneCreate) -> Drone:
        """注册新无人机（同时完成ARP注册和MAVLink连接）"""
        # ARP注册
        arp_entry = arp_resolver.register(
            drone_id=data.drone_id,
            connection_type=data.connection_type,
            connection_address=data.connection_address,
            sys_id=data.sys_id,
        )

        # 数据库存储
        drone = Drone(
            drone_id=data.drone_id,
            sys_id=arp_entry.sys_id,
            name=data.name,
            model=data.model,
            firmware=data.firmware,
            connection_type=data.connection_type,
            connection_address=data.connection_address,
            group_id=data.group_id,
            status=DroneStatus.STANDBY,
        )
        db.add(drone)
        await db.flush()

        # 建立MAVLink连接
        await mavlink_service.connect_drone(
            drone_id=data.drone_id,
            sys_id=arp_entry.sys_id,
            connection_type=data.connection_type,
            connection_address=data.connection_address,
        )

        # 记录事件
        await self._log_event(db, "INFO", "drone_service", data.drone_id,
                              f"Drone registered: {data.name} (sys_id={arp_entry.sys_id})")

        # 广播更新
        await ws_manager.broadcast({"type": "drone_registered", "drone_id": data.drone_id})

        return drone

    async def get_drone(self, db: AsyncSession, drone_id: str) -> Drone:
        """获取单架无人机"""
        result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
        drone = result.scalar_one_or_none()
        if not drone:
            raise DroneNotFoundError(drone_id)
        return drone

    async def get_all_drones(self, db: AsyncSession, status: str = None,
                             group_id: str = None) -> List[Drone]:
        """获取无人机列表"""
        query = select(Drone)
        if status:
            query = query.where(Drone.status == status)
        if group_id:
            query = query.where(Drone.group_id == group_id)
        query = query.order_by(Drone.id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_drone(self, db: AsyncSession, drone_id: str, data: DroneUpdate) -> Drone:
        """更新无人机信息"""
        drone = await self.get_drone(db, drone_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(drone, key, value)

        # 如果通信地址变了，更新ARP并重连
        if "connection_type" in update_data or "connection_address" in update_data:
            arp_resolver.register(
                drone_id=drone_id,
                connection_type=drone.connection_type,
                connection_address=drone.connection_address,
                sys_id=drone.sys_id,
            )
            await mavlink_service.disconnect_drone(drone_id)
            await mavlink_service.connect_drone(
                drone_id=drone_id,
                sys_id=drone.sys_id,
                connection_type=drone.connection_type,
                connection_address=drone.connection_address,
            )

        await self._log_event(db, "INFO", "drone_service", drone_id, "Drone info updated")
        return drone

    async def delete_drone(self, db: AsyncSession, drone_id: str):
        """删除无人机"""
        drone = await self.get_drone(db, drone_id)
        await db.delete(drone)
        await mavlink_service.disconnect_drone(drone_id)
        arp_resolver.unregister(drone_id)
        await self._log_event(db, "WARNING", "drone_service", drone_id, "Drone removed")
        await ws_manager.broadcast({"type": "drone_removed", "drone_id": drone_id})

    async def send_command(self, db: AsyncSession, drone_id: str, cmd: DroneCommand) -> dict:
        """向无人机发送控制指令"""
        drone = await self.get_drone(db, drone_id)
        conn = mavlink_service.get_connection(drone_id)
        if not conn or not conn.is_connected():
            raise DroneOfflineError(drone_id)

        result = await conn.send_command(cmd.command, cmd.params)

        # 更新数据库状态
        new_status = self._map_command_to_status(cmd.command)
        if new_status:
            drone.status = new_status

        await self._log_event(db, "INFO", "command", drone_id,
                              f"Command: {cmd.command} params={cmd.params} result={result}")
        return result

    async def update_telemetry(self, db: AsyncSession, drone_id: str, telemetry: dict):
        """更新无人机遥测数据（由MAVLink服务调用）"""
        result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
        drone = result.scalar_one_or_none()
        if not drone:
            return

        drone.latitude = telemetry.get("latitude", drone.latitude)
        drone.longitude = telemetry.get("longitude", drone.longitude)
        drone.altitude = telemetry.get("altitude", drone.altitude)
        drone.relative_altitude = telemetry.get("relative_altitude", drone.relative_altitude)
        drone.heading = telemetry.get("heading", drone.heading)
        drone.ground_speed = telemetry.get("ground_speed", drone.ground_speed)
        drone.vertical_speed = telemetry.get("vertical_speed", drone.vertical_speed)
        drone.battery_voltage = telemetry.get("battery_voltage", drone.battery_voltage)
        drone.battery_current = telemetry.get("battery_current", drone.battery_current)
        drone.battery_percent = telemetry.get("battery_percent", drone.battery_percent)
        drone.gps_satellites = telemetry.get("gps_satellites", drone.gps_satellites)
        drone.roll = telemetry.get("roll", drone.roll)
        drone.pitch = telemetry.get("pitch", drone.pitch)
        drone.yaw = telemetry.get("yaw", drone.yaw)
        status_str = telemetry.get("status")
        if status_str:
            try:
                drone.status = DroneStatus(status_str)
            except ValueError:
                pass
        drone.last_heartbeat = datetime.utcnow()

        # 刷新ARP条目
        arp_resolver.refresh_entry(drone_id)

    async def get_stats(self, db: AsyncSession) -> PlatformStats:
        """获取平台统计数据"""
        result = await db.execute(select(Drone))
        drones = list(result.scalars().all())

        total = len(drones)
        online = sum(1 for d in drones if d.status != DroneStatus.OFFLINE)
        flying = sum(1 for d in drones if d.status in (
            DroneStatus.FLYING, DroneStatus.TAKEOFF, DroneStatus.LANDING, DroneStatus.RETURN_TO_HOME
        ))
        offline = total - online
        avg_battery = sum(d.battery_percent for d in drones) / total if total > 0 else 0

        from models import Mission, MissionStatus, SwarmGroup
        missions_result = await db.execute(select(Mission))
        missions = list(missions_result.scalars().all())
        active_missions = sum(1 for m in missions if m.status == MissionStatus.RUNNING)

        groups_result = await db.execute(select(SwarmGroup))
        groups = list(groups_result.scalars().all())

        return PlatformStats(
            total_drones=total,
            online_drones=online,
            flying_drones=flying,
            offline_drones=offline,
            total_missions=len(missions),
            active_missions=active_missions,
            total_groups=len(groups),
            avg_battery=round(avg_battery, 1),
        )

    async def get_event_logs(self, db: AsyncSession, limit: int = 100,
                             drone_id: str = None) -> List[EventLog]:
        """获取事件日志"""
        query = select(EventLog).order_by(EventLog.timestamp.desc()).limit(limit)
        if drone_id:
            query = query.where(EventLog.drone_id == drone_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def _log_event(self, db: AsyncSession, level: str, source: str,
                         drone_id: Optional[str], message: str):
        """记录事件日志"""
        event = EventLog(level=level, source=source, drone_id=drone_id, message=message)
        db.add(event)
        await ws_manager.broadcast({
            "type": "event",
            "data": {"level": level, "source": source, "drone_id": drone_id,
                     "message": message, "timestamp": datetime.utcnow().isoformat()},
        })

    @staticmethod
    def _map_command_to_status(command: str) -> Optional[DroneStatus]:
        mapping = {
            "arm": DroneStatus.ARMED,
            "disarm": DroneStatus.STANDBY,
            "takeoff": DroneStatus.TAKEOFF,
            "land": DroneStatus.LANDING,
            "rtl": DroneStatus.RETURN_TO_HOME,
            "go_to": DroneStatus.FLYING,
        }
        return mapping.get(command)


# 全局单例
drone_service = DroneService()
