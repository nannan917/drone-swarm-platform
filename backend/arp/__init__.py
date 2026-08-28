"""
ARP - 无人机地址解析与注册协议 (Drone Address Resolution & Registration Protocol)

功能：
1. 维护 drone_id -> (sys_id, connection_type, connection_address) 的映射表
2. 支持动态注册、注销、地址更新
3. 缓存机制，带TTL过期
4. 持久化到JSON文件，重启后恢复
5. 模拟ARP请求/响应流程（类似网络ARP协议）
"""
from .resolver import ARPResolver, ARPEntryData

__all__ = ["ARPResolver", "ARPEntryData"]
