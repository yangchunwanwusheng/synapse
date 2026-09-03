"""调度器：按角色寻址、驱动消息流、记录通信度量（赛题 M9 调度模块）。"""

from __future__ import annotations

from .handshake import CNR
from .messages import Capability


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

    def register(self, agent, view: CNR | None = None) -> dict[str, Capability]:
        """冷启动加入（#149015 M2 能力发现消息流）：定向 CAP_QUERY/CAP_REPLY 往返。

        流程（全部经 self.send 构造→校验→计量→消费，非注册表透传）：
        ① 冲突检查（同 id 同能力=幂等返回当前视图不重发；同 id 不同能力/同 role
        不同 id=显式拒绝）；② newcomer 进路由表 + hello（自身能力，warm 注册表口径
        不变）；③ 对每个在场 peer 定向发 CAP_QUERY（逐 peer 单发，无广播语义）；
        ④ 各 peer 依据自身 cap 经 CNR.handle_query 生成 CAP_REPLY（capability 字段
        携带声明）；⑤ CNR.accept_reply 校验（方向/关联/能力身份）通过才
        view.observe 进 newcomer 能力视图；⑥ 返回视图（不含 newcomer 自身）。

        view：newcomer 的独立能力视图（缺省=共享 self.cnr；传入独立 CNR 即得
        "仅由响应驱动"的冷启动视图——构造器 hello 的在场能力不会出现在其中）。
        cnr=None 且未传 view：路由表照常、消息流照发（协议层独立），返回已校验
        的响应能力 dict，但无视图可供后续 negotiate/resolve（调用方应显式感知）。

        幂等分支口径注意：同 id 同能力重调时返回"当前视图"（不重发消息流）——
        cnr=None 且未传 view 的场景下无可查视图，返回 {}（与首次调用的非空返回
        不对称，属预期）；混用 view 传参（首次传独立 view、重试不传）会读到
        不同来源的视图，调用方应保持同一 view 口径。

        边界如实声明：本编排是**进程内控制面定向分发**——peer 侧响应由本调度器
        代表各本地 agent 生成（agents 无 inbox/消息回调）；wire 序列化/反序列化
        与双端点往返在 tests/test_capability_discovery.py 的 transport 用例验证，
        不承诺分布式 receiver 多路复用或服务发现广播。部分 peer 传输失败时
        注册保持成功、视图如实缺该 peer（不伪造未收到的能力），异常上抛调用方。
        """
        existing = self.by_id.get(agent.agent_id)
        if existing is not None:
            if existing.cap == agent.cap:
                base = view.discover() if view is not None else (self.cnr.discover() if self.cnr else {})
                return {k: v for k, v in base.items() if k != agent.agent_id}
            raise ValueError(f"agent_id {agent.agent_id!r} already registered with a different capability")
        if agent.role in self.by_role:
            raise ValueError(
                f"role {agent.role!r} already held by {self.by_role[agent.role].agent_id!r}"
                "（by_role 单槽语义；覆盖须先显式移除）"
            )
        peers = list(self.by_id.values())  # 快照在场 agent（消息流对象）
        self.by_id[agent.agent_id] = agent
        self.by_role[agent.role] = agent
        if self.cnr is not None:
            self.cnr.hello(agent.cap)
        target_view = view if view is not None else self.cnr
        if target_view is not None:
            target_view.hello(agent.cap)  # 视图先含 newcomer 自身（negotiate 双端依据）
        accepted: dict[str, Capability] = {}
        for peer in peers:
            query = CNR.make_query(agent.agent_id, peer.agent_id, self.next_msg_id())
            self.send(query)
            reply = CNR.handle_query(query, peer.cap, self.next_msg_id())
            self.send(reply)
            cap = CNR.accept_reply(reply, query)
            if target_view is not None:
                target_view.observe(cap)
            accepted[cap.agent_id] = cap
        return accepted
