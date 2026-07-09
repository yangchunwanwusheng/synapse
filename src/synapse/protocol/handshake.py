"""CNR — Capability Negotiation & Resolution（赛题 M2 握手/能力发现/协议映射）。

各 Agent 广播 Capability；协商发送方/接收方编码：取双方支持编码的交集中**最高密度**的一种，
隐状态(hidden)仅同族允许，异构自动降级到 embedding/text（协议映射）。
"""
from __future__ import annotations

from .messages import Capability

ENCODING_RANK = {"hidden": 3, "residual": 2, "embedding": 1, "text": 0}


class CNR:
    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def hello(self, cap: Capability) -> None:
        self._caps[cap.agent_id] = cap

    def discover(self) -> dict[str, Capability]:
        return dict(self._caps)

    def negotiate(self, sender_id: str, receiver_id: str) -> str:
        s, r = self._caps.get(sender_id), self._caps.get(receiver_id)
        if not s or not r:
            return "text"
        common = set(s.encodings) & set(r.encodings)
        if "hidden" in common and s.model_family != r.model_family:
            common.discard("hidden")          # 异构不可零拷贝隐状态
        if not common:
            return "text"
        return max(common, key=lambda e: ENCODING_RANK.get(e, 0))
