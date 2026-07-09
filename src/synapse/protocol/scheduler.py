"""调度器：按角色寻址、驱动消息流、记录通信度量（赛题 M9 调度模块）。"""
from __future__ import annotations

from .handshake import CNR


class Scheduler:
    def __init__(self, agents, cnr: CNR | None = None, metrics=None):
        self.by_role = {a.role: a for a in agents}
        self.by_id = {a.agent_id: a for a in agents}
        self.cnr = cnr
        self.metrics = metrics
        self._n = 0
        if cnr:
            for a in agents:
                cnr.hello(a.cap)

    def agent(self, role: str):
        return self.by_role[role]

    def next_msg_id(self) -> str:
        self._n += 1
        return f"m{self._n}"

    def send(self, msg):
        """路由消息并埋点度量；返回接收方 Agent（骨架不做真正异步投递）。"""
        if self.metrics is not None:
            self.metrics.record_message(msg)
        return self.by_id.get(msg.receiver)
