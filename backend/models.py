"""
SQLAlchemy 数据模型
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class DroneStatus(str, enum.Enum):
    OFFLINE = "offline"
    STANDBY = "standby"
    ARMED = "armed"
    TAKEOFF = "takeoff"
    FLYING = "flying"
    LANDING = "landing"
    RETURN_TO_HOME = "return_to_home"
    EMERGENCY = "emergency"
    ERROR = "error"


class MissionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Drone(Base):
    """无人机实体"""
    __tablename__ = "drones"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(64), unique=True, index=True, nullable=False)  # 逻辑ID，如 DRONE-001
    sys_id = Column(Integer, unique=True, index=True)  # MAVLink System ID
    name = Column(String(128), nullable=False)
    model = Column(String(64), default="Generic Quadcopter")
    firmware = Column(String(64), default="PX4 v1.14")

    # 通信地址（ARP解析结果）
    connection_type = Column(String(32), default="udp")  # udp / serial / tcp
    connection_address = Column(String(256), default="127.0.0.1:14550")

    # 实时状态
    status = Column(Enum(DroneStatus), default=DroneStatus.OFFLINE)
    latitude = Column(Float, default=0.0)
    longitude = Column(Float, default=0.0)
    altitude = Column(Float, default=0.0)
    relative_altitude = Column(Float, default=0.0)
    heading = Column(Float, default=0.0)
    ground_speed = Column(Float, default=0.0)
    air_speed = Column(Float, default=0.0)
    vertical_speed = Column(Float, default=0.0)

    # 电池
    battery_voltage = Column(Float, default=0.0)
    battery_current = Column(Float, default=0.0)
    battery_percent = Column(Float, default=100.0)

    # GPS
    gps_satellites = Column(Integer, default=0)
    gps_fix_type = Column(Integer, default=0)

    # 姿态
    roll = Column(Float, default=0.0)
    pitch = Column(Float, default=0.0)
    yaw = Column(Float, default=0.0)

    # 元数据
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    group_id = Column(String(64), nullable=True)  # 所属编队组
    is_leader = Column(Boolean, default=False)  # 是否为长机

    missions = relationship("Mission", back_populates="drone", cascade="all, delete-orphan")
    telemetry_logs = relationship("TelemetryLog", back_populates="drone", cascade="all, delete-orphan")


class Mission(Base):
    """飞行任务"""
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    drone_id = Column(Integer, ForeignKey("drones.id"), nullable=True)
    status = Column(Enum(MissionStatus), default=MissionStatus.PENDING)

    # 航点列表（JSON存储）
    waypoints = Column(Text, default="[]")  # [{lat, lon, alt, speed, action}]

    # 任务参数
    max_altitude = Column(Float, default=120.0)
    max_speed = Column(Float, default=15.0)
    return_to_home_on_complete = Column(Boolean, default=True)

    # 进度
    current_waypoint = Column(Integer, default=0)
    total_waypoints = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    drone = relationship("Drone", back_populates="missions")


class TelemetryLog(Base):
    """遥测日志（用于历史轨迹回放）"""
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(Integer, ForeignKey("drones.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    latitude = Column(Float, default=0.0)
    longitude = Column(Float, default=0.0)
    altitude = Column(Float, default=0.0)
    speed = Column(Float, default=0.0)
    battery_percent = Column(Float, default=100.0)
    status = Column(String(32), default="offline")

    drone = relationship("Drone", back_populates="telemetry_logs")


class SwarmGroup(Base):
    """编队组"""
    __tablename__ = "swarm_groups"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    leader_drone_id = Column(String(64), nullable=True)
    formation_type = Column(String(32), default="line")  # line / circle / grid / v_shape
    member_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)


class EventLog(Base):
    """系统事件日志"""
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(16), default="INFO")  # INFO / WARNING / ERROR / CRITICAL
    source = Column(String(64), default="system")
    drone_id = Column(String(64), nullable=True)
    message = Column(Text, nullable=False)
