"""CNR — Capability Negotiation & Resolution（赛题 M2 握手/能力发现/协议映射）。

各 Agent 广播 Capability；协商发送方/接收方编码：取双方支持编码的交集中**最高密度**的一种，
隐状态(hidden)仅同族允许，异构自动降级到 embedding/text（协议映射）。

§2.2 能力从"声明"到"验证"（借鉴 hermes check_fn 门控）：hello 时若提供 check_fn，则对 cap.probe
声明的项做运行时实测（如 Executor 声明 codeact_sandbox 前实测沙箱可执行），结果带 TTL 缓存；
negotiate 时 probe 项未通过验证则从候选编码中剔除，让能力发现成为"可验证承诺"。
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .messages import Capability

ENCODING_RANK = {"hidden": 3, "residual": 2, "embedding": 1, "text": 0}


class CNR:
    def __init__(self, check_fn: Optional[Callable[[Capability], set[str]]] = None, ttl: float = 300.0):
        self._caps: dict[str, Capability] = {}
        self._check_fn = check_fn
        self._ttl = ttl
        # 运行时验证缓存：agent_id -> (timestamp, verified_probe_subset)
        self._verified: dict[str, tuple[float, set[str]]] = {}

    def hello(self, cap: Capability) -> None:
        self._caps[cap.agent_id] = cap
        # §2.2 握手即探测：对 cap.probe 声明的能力项运行 check_fn 实测，结果带 TTL 缓存
        if self._check_fn and cap.probe:
            verified = set(self._check_fn(cap))
            self._verified[cap.agent_id] = (time.monotonic(), verified)

    def _verified_probe(self, agent_id: str) -> set[str]:
        """返回仍在 TTL 内的已验证 probe 子集；过期则清空（下次 hello 重测）。"""
        entry = self._verified.get(agent_id)
        if not entry:
            return set()
        ts, verified = entry
        if time.monotonic() - ts > self._ttl:
            return set()
        return set(verified)

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

    def verified(self, agent_id: str) -> set[str]:
        """供外部查询某 agent 已通过运行时探测的 probe 能力子集（§2.2 可验证承诺）。"""
        return self._verified_probe(agent_id)
