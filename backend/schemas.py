"""
Pydantic 请求/响应 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============ 无人机 ============
class DroneCreate(BaseModel):
    drone_id: str = Field(..., description="无人机逻辑ID，如 DRONE-001")
    name: str
    model: Optional[str] = "Generic Quadcopter"
    firmware: Optional[str] = "PX4 v1.14"
    connection_type: Optional[str] = "udp"
    connection_address: Optional[str] = "127.0.0.1:14550"
    sys_id: Optional[int] = None
    group_id: Optional[str] = None


class DroneUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    connection_type: Optional[str] = None
    connection_address: Optional[str] = None
    group_id: Optional[str] = None
    is_leader: Optional[bool] = None


class DroneResponse(BaseModel):
    id: int
    drone_id: str
    sys_id: Optional[int] = None
    name: str
    model: str
    firmware: str
    connection_type: str
    connection_address: str
    status: str
    latitude: float
    longitude: float
    altitude: float
    relative_altitude: float
    heading: float
    ground_speed: float
    battery_percent: float
    battery_voltage: float
    gps_satellites: int
    roll: float
    pitch: float
    yaw: float
    last_heartbeat: Optional[datetime] = None
    registered_at: datetime
    group_id: Optional[str] = None
    is_leader: bool

    class Config:
        from_attributes = True


class DroneTelemetry(BaseModel):
    """实时遥测数据（WebSocket推送用）"""
    drone_id: str
    status: str
    latitude: float
    longitude: float
    altitude: float
    relative_altitude: float
    heading: float
    ground_speed: float
    vertical_speed: float
    battery_percent: float
    battery_voltage: float
    gps_satellites: int
    roll: float
    pitch: float
    yaw: float
    timestamp: str


class DroneCommand(BaseModel):
    """无人机控制指令"""
    command: str = Field(..., description="指令类型: arm/disarm/takeoff/land/rtl/go_to/set_mode")
    params: Dict[str, Any] = Field(default_factory=dict, description="指令参数")


# ============ 任务 ============
class Waypoint(BaseModel):
    lat: float
    lon: float
    alt: float = 50.0
    speed: float = 10.0
    action: Optional[str] = None  # waypoint / takeoff / land / loiter


class MissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    drone_id: Optional[str] = None
    waypoints: List[Waypoint] = Field(default_factory=list)
    max_altitude: float = 120.0
    max_speed: float = 15.0
    return_to_home_on_complete: bool = True


class MissionResponse(BaseModel):
    id: int
    mission_id: str
    name: str
    description: Optional[str] = None
    drone_id: Optional[int] = None
    status: str
    waypoints: str
    current_waypoint: int
    total_waypoints: int
    progress_percent: float
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 编队组 ============
class SwarmGroupCreate(BaseModel):
    group_id: str
    name: str
    formation_type: str = "line"
    description: Optional[str] = None


class SwarmGroupResponse(BaseModel):
    id: int
    group_id: str
    name: str
    leader_drone_id: Optional[str] = None
    formation_type: str
    member_count: int
    created_at: datetime
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SwarmCommand(BaseModel):
    """编队控制指令"""
    command: str = Field(..., description="takeoff_all/land_all/rtl_all/formation_change")
    params: Dict[str, Any] = Field(default_factory=dict)


# ============ ARP ============
class ARPEntry(BaseModel):
    drone_id: str
    sys_id: int
    connection_type: str
    connection_address: str
    resolved_at: str
    expires_at: str


class ARPResolveRequest(BaseModel):
    drone_id: str


# ============ 事件日志 ============
class EventLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    source: str
    drone_id: Optional[str] = None
    message: str

    class Config:
        from_attributes = True


# ============ 统计 ============
class PlatformStats(BaseModel):
    total_drones: int
    online_drones: int
    flying_drones: int
    offline_drones: int
    total_missions: int
    active_missions: int
    total_groups: int
    avg_battery: float
