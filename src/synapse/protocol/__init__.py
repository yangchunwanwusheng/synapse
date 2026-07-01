"""② 协议解析与调度：结构化消息、CNR 握手/能力发现、调度器。"""
from .messages import ActionType, Capability, Message
from .handshake import CNR
from .scheduler import Scheduler

__all__ = ["ActionType", "Capability", "Message", "CNR", "Scheduler"]
