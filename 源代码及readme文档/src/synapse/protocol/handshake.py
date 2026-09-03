"""CNR — Capability Negotiation & Resolution（赛题 M2 握手/能力发现/协议映射）。

各 Agent 广播 Capability；协商发送方/接收方编码：取双方支持编码的交集中**最高密度**的一种，
隐状态(hidden)仅同族允许，异构自动降级到 embedding/text（协议映射）。

§2.2 能力从"声明"到"验证"（借鉴 hermes check_fn 门控）：hello 时若提供 check_fn，则对 cap.probe
声明的项做运行时实测（如 Executor 声明 codeact_sandbox 前实测沙箱可执行），结果带 TTL 缓存，
可经 verified() 查询。注意（2026-09-03 如实收窄）：negotiate() 当前**不消费** probe 验证结果
（probe 项≠编码候选，两者不构成门控关系）；验证结果仅作握手期记录。

#149015 能力发现消息流：CAP_QUERY/CAP_REPLY 的构造、响应与校验原语（make_query /
handle_query / accept_reply），加上 observe()（登记"经消息流观察到的远端能力"，
不替远端执行本地探针）——冷启动 agent 据此建立独立能力视图并按响应路由
（resolve 按 role/action 选目标，negotiate 按双方 encodings 选编码，两者均只依据
视图内经 accept_reply 校验过的条目）。
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from .messages import ActionType, Capability, Message

ENCODING_RANK = {"hidden": 3, "residual": 2, "embedding": 1, "text": 0}


class CNRProtocolError(ValueError):
    """发现消息流协议违规（校验失败的 CAP_REPLY / 非法 CAP_QUERY 构造）。"""


class CNR:
    def __init__(self, check_fn: Optional[Callable[[Capability], set[str]]] = None, ttl: float = 300.0):
        self._caps: dict[str, Capability] = {}
        self._check_fn = check_fn
        self._ttl = ttl
        # 运行时验证缓存：agent_id -> (timestamp, verified_probe_subset)
        self._verified: dict[str, tuple[float, set[str]]] = {}

    def hello(self, cap: Capability) -> None:
        """本地 agent 上线登记：可选 check_fn 对其 probe 声明做运行时实测。"""
        self._caps[cap.agent_id] = cap
        # §2.2 握手即探测：对 cap.probe 声明的能力项运行 check_fn 实测，结果带 TTL 缓存
        if self._check_fn and cap.probe:
            verified = set(self._check_fn(cap))
            self._verified[cap.agent_id] = (time.monotonic(), verified)

    def observe(self, cap: Capability) -> None:
        """登记经消息流观察到的**远端**能力（#149015）。

        与 hello() 的区别：不执行 check_fn——probe 探测只能在能力声明者本地运行
        （接收方替远端执行探针既不可信也无意义）。TTL/verified 语义同hello：
        远端能力声明持续有效直至覆盖（TTL 只作用于本地 probe 验证缓存，不让
        能力条目过期）。
        """
        self._caps[cap.agent_id] = cap

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
            common.discard("hidden")  # 异构不可零拷贝隐状态
        if not common:
            return "text"
        return max(common, key=lambda e: ENCODING_RANK.get(e, 0))

    def resolve(self, *, role: str | None = None, action: str | None = None) -> tuple[str, ...]:
        """按能力视图选目标 agent（#149015"按响应路由"的动作面）。

        只返回视图中（经 hello/observe 登记）满足条件的 agent_id 元组（保持登记序）；
        role 与 action 都给时取交集语义。空结果=视图内无可路由目标（调用方应显式
        处理，不静默回退——回退会伪造路由依据）。
        """
        out: list[str] = []
        for cap in self._caps.values():
            if role is not None and cap.role != role:
                continue
            if action is not None and action not in cap.actions:
                continue
            out.append(cap.agent_id)
        return tuple(out)

    def verified(self, agent_id: str) -> set[str]:
        """供外部查询某 agent 已通过运行时探测的 probe 能力子集（§2.2 可验证承诺）。"""
        return self._verified_probe(agent_id)

    # ---------------- #149015 能力发现消息流原语（构造 / 响应 / 校验） ----------------

    @staticmethod
    def make_query(sender_id: str, receiver_id: str, msg_id: str) -> Message:
        """构造定向 CAP_QUERY（newcomer → 单个在场 peer；逐 peer 单发，无广播语义）。"""
        return Message(
            msg_id=msg_id,
            sender=sender_id,
            receiver=receiver_id,
            action=ActionType.CAP_QUERY.value,
            params={"scope": "capability"},
        )

    @staticmethod
    def handle_query(query: Message, local_cap: Capability, reply_msg_id: str) -> Message:
        """响应侧：依据收到的 CAP_QUERY 与**自己**的能力声明构造 CAP_REPLY。

        只读 query 的 sender/receiver/action——回复内容完全来自 responder 自身
        Capability，不查询任何共享注册表（响应语义：能力由声明者给出）。
        """
        if query.action != ActionType.CAP_QUERY.value:
            raise CNRProtocolError(f"not a CAP_QUERY (action={query.action!r})")
        return Message(
            msg_id=reply_msg_id,
            sender=query.receiver,
            receiver=query.sender,
            action=ActionType.CAP_REPLY.value,
            params={"query_id": query.msg_id},
            capability=local_cap,
        )

    @staticmethod
    def accept_reply(reply: Message, query: Message) -> Capability:
        """查询侧校验并消费 CAP_REPLY：通过才允许进入 newcomer 能力视图。

        校验：action=CAP_REPLY；方向（reply.sender==query.receiver 且
        reply.receiver==query.sender）；关联（params.query_id==query.msg_id）；
        能力身份（capability.agent_id==reply.sender）。任何一项不符抛
        CNRProtocolError——丢失/篡改/迟到的响应不得进入视图（路由依据的完整性）。
        """
        if reply.action != ActionType.CAP_REPLY.value:
            raise CNRProtocolError(f"not a CAP_REPLY (action={reply.action!r})")
        if reply.sender != query.receiver or reply.receiver != query.sender:
            raise CNRProtocolError(
                f"reply direction mismatch: {reply.sender}->{reply.receiver} "
                f"does not answer {query.sender}->{query.receiver}"
            )
        if reply.params.get("query_id") != query.msg_id:
            raise CNRProtocolError(
                f"reply correlation mismatch: query_id={reply.params.get('query_id')!r} != {query.msg_id!r}"
            )
        if reply.capability is None:
            raise CNRProtocolError("CAP_REPLY carries no capability")
        if reply.capability.agent_id != reply.sender:
            raise CNRProtocolError(
                f"capability identity mismatch: {reply.capability.agent_id!r} != sender {reply.sender!r}"
            )
        return reply.capability
