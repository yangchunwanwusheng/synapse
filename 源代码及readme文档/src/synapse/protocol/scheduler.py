"""调度器：按角色寻址、驱动消息流、记录通信度量（赛题 M9 调度模块）。"""
from __future__ import annotations

from .handshake import CNR


class Scheduler:
    def __init__(self, agents, cnr: CNR | None = None, metrics=None, transport=None):
        self.by_role = {a.role: a for a in agents}
        self.by_id = {a.agent_id: a for a in agents}
        self.cnr = cnr
        self.metrics = metrics
        self.transport = transport
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
        """路由消息并埋点度量；配置 transport 时发送真实 wire frame。

        返回的 Agent 仅表示本地路由意图，不是远端已接收或处理消息的凭证。
        """
        if self.transport is not None:
            payload = msg.to_wire().encode("utf-8")
            frame_bytes = self.transport.send(payload)
            # Only a successfully transmitted message is counted as delivered.
            if self.metrics is not None:
                self.metrics.record_message(msg)  # 已按 len(to_wire()) 记入 transport 口径
                # transport 真实帧长若含 framing 开销（如 4B 长度前缀），只补差值，避免双计
                if frame_bytes != len(payload) and hasattr(self.metrics, "transport_bytes"):
                    self.metrics.transport_bytes += frame_bytes - len(payload)
        elif self.metrics is not None:
            self.metrics.record_message(msg)
        return self.by_id.get(msg.receiver)
