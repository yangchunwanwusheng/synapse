"""能力发现消息流集成测试（Issue #149015，M2）。

覆盖 CAP_QUERY/CAP_REPLY 的构造→校验→计量→消费全链：
1. 冷启动定向消息流（Scheduler.register 编排，消息经 send 计量）；
2. 独立能力视图仅由**已校验响应**驱动（丢响应/篡改响应的 peer 不可路由）；
3. wire 序列化双端点往返（to_wire → transport → from_wire → handle/accept）；
4. 注册幂等与冲突显式拒绝、无 peer/无 CNR 边界、from_wire 健壮性。
"""

from __future__ import annotations

import pytest

from synapse.eval.metrics import Metrics
from synapse.protocol.handshake import CNR, CNRProtocolError
from synapse.protocol.messages import ActionType, Capability, Message
from synapse.protocol.scheduler import Scheduler
from synapse.protocol.transport import InProcessTransport


def _cap(agent_id, role, actions=("TELL",), encodings=("text", "embedding"), family="mock-family"):
    return Capability(agent_id=agent_id, role=role, actions=actions, encodings=encodings, model_family=family)


class _Agent:
    """最小 agent 桩：Scheduler 只寻址 .role/.agent_id/.cap。"""

    def __init__(self, cap: Capability):
        self.cap = cap
        self.agent_id = cap.agent_id
        self.role = cap.role


class RecordingScheduler(Scheduler):
    """记录全部 send 的消息对象（wire 捕获替代 metrics 计数断言）。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.sent: list[Message] = []

    def send(self, msg):
        self.sent.append(msg)
        return super().send(msg)


def _three_peers():
    return [
        _Agent(_cap("planner-1", "planner", ("PLAN",), ("text",))),
        _Agent(_cap("retriever-1", "retriever", ("RETRIEVE", "TELL"), ("text", "embedding", "residual"))),
        _Agent(_cap("executor-1", "executor", ("EXECUTE",), ("text",))),
    ]


# ---------------- 1. 冷启动定向消息流（核心集成 #1） ----------------


def test_cold_start_discovery_directed_flow():
    peers = _three_peers()
    m = Metrics()
    sched = RecordingScheduler(peers, cnr=CNR(), metrics=m)
    newcomer = _Agent(_cap("summarizer-1", "summarizer", ("SUMMARIZE",), ("text", "embedding")))

    accepted = sched.register(newcomer)

    assert set(accepted) == {"planner-1", "retriever-1", "executor-1"}
    assert accepted["retriever-1"] == peers[1].cap
    # 消息流：3×CAP_QUERY（newcomer→peer 定向单发）+ 3×CAP_REPLY（peer→newcomer，capability 携带声明）
    assert len(sched.sent) == 6
    queries = [x for x in sched.sent if x.action == ActionType.CAP_QUERY.value]
    replies = [x for x in sched.sent if x.action == ActionType.CAP_REPLY.value]
    assert len(queries) == 3 and len(replies) == 3
    assert {q.receiver for q in queries} == {p.agent_id for p in peers}
    assert all(q.sender == "summarizer-1" for q in queries)
    ids = [x.msg_id for x in sched.sent]
    assert len(set(ids)) == 6  # msg_id 唯一
    reply_by_sender = {r.sender: r for r in replies}
    for q in queries:
        r = reply_by_sender[q.receiver]
        assert r.receiver == q.sender  # 方向：回给查询者
        assert r.params["query_id"] == q.msg_id  # 请求-响应关联
        assert r.capability is not None and r.capability.agent_id == r.sender  # 能力身份
    # 每条消息都计入 M8 度量（控制面开销如实计量）
    assert m.messages == 6
    # 注册后 newcomer 可被角色寻址（路由表口径）
    assert sched.agent("summarizer") is newcomer


# ---------------- 2. 独立视图仅由已校验响应驱动（核心集成 #2） ----------------


def test_fresh_view_populated_only_by_accepted_replies():
    cap_exec = _cap("executor-1", "executor", ("EXECUTE",), ("text", "embedding"))
    cap_summ = _cap("summarizer-9", "summarizer", ("SUMMARIZE",), ("text",))
    newcomer_cap = _cap("newcomer-1", "retriever", ("RETRIEVE",), ("text", "embedding"))
    shared = CNR()
    shared.hello(cap_exec)  # 共享注册表早已知道答案——视图不得从这里抄
    shared.hello(cap_summ)
    sched = Scheduler([_Agent(cap_exec), _Agent(cap_summ)], cnr=shared)
    fresh = CNR()  # newcomer 独立冷视图：初始只含自身

    accepted = sched.register(_Agent(newcomer_cap), view=fresh)

    # 正常路径：两个 peer 的响应都被接受
    assert set(accepted) == {"executor-1", "summarizer-9"}
    assert set(fresh.discover()) == {"newcomer-1", "executor-1", "summarizer-9"}

    # 按响应路由（动作面）：resolve 只看视图；丢弃响应的 peer 不可路由
    fresh2 = CNR()
    fresh2.hello(newcomer_cap)
    q_exec = CNR.make_query("newcomer-1", "executor-1", "q1")
    r_exec = CNR.handle_query(q_exec, cap_exec, "r1")
    fresh2.observe(CNR.accept_reply(r_exec, q_exec))  # 只消费 executor 的响应
    q_summ = CNR.make_query("newcomer-1", "summarizer-9", "q2")
    r_summ = CNR.handle_query(q_summ, cap_summ, "r2")  # summarizer 响应被丢弃（未 accept）
    assert fresh2.resolve(action="EXECUTE") == ("executor-1",)
    assert fresh2.resolve(action="SUMMARIZE") == ()  # 丢响应 → 不可路由（不静默回退）
    # 按响应路由（编码面）：未观察到的一端 negotiate 走 text 兜底
    assert fresh2.negotiate("newcomer-1", "executor-1") == "embedding"
    assert fresh2.negotiate("newcomer-1", "summarizer-9") == "text"


@pytest.mark.parametrize(
    "mutate",
    [
        # 方向不符（响应发给了别人）
        lambda r, q: r.__dict__.update(receiver="someone-else"),
        # 关联不符（迟到的旧响应/错配）
        lambda r, q: r.__dict__.update(params={"query_id": "stale-id"}),
        # 能力身份不符（替他人声明能力）
        lambda r, q: r.__dict__.update(
            capability=Capability("attacker", "executor", ("EXECUTE",), ("text",), "f")
        ),
        # 无能力载荷
        lambda r, q: r.__dict__.update(capability=None),
    ],
    ids=["wrong-direction", "stale-correlation", "identity-mismatch", "no-capability"],
)
def test_accept_reply_rejects_malformed_replies(mutate):
    q = CNR.make_query("newcomer-1", "executor-1", "q9")
    r = CNR.handle_query(q, _cap("executor-1", "executor"), "r9")
    mutate(r, q)
    with pytest.raises(CNRProtocolError):
        CNR.accept_reply(r, q)


def test_handle_query_rejects_non_query_action():
    msg = Message("m0", "a", "b", ActionType.TELL.value)
    with pytest.raises(CNRProtocolError, match="not a CAP_QUERY"):
        CNR.handle_query(msg, _cap("b", "executor"), "m1")


# ---------------- 3. wire 序列化双端点往返（核心集成 #3） ----------------


def test_discovery_wire_roundtrip():
    peer_cap = _cap(
        "retriever-1", "retriever", ("RETRIEVE", "TELL"), ("text", "embedding", "residual"), "fam-x"
    )
    newcomer_left, peer_right = InProcessTransport.pair()

    # newcomer 侧：序列化 CAP_QUERY 上线缆
    q = CNR.make_query("newcomer-1", "retriever-1", "q1")
    newcomer_left.send(q.to_wire().encode("utf-8"))
    # peer 侧：收线缆 → 反序列化 → 依据自身能力构造响应
    q_peer = Message.from_wire(peer_right.recv())
    assert q_peer == q  # wire 往返无损（等值比较）
    r = CNR.handle_query(q_peer, peer_cap, "r1")
    peer_right.send(r.to_wire().encode("utf-8"))
    # newcomer 侧：反序列化响应 → 校验 → 进视图 → 路由
    r_new = Message.from_wire(newcomer_left.recv())
    assert isinstance(r_new.capability.encodings, tuple)  # JSON list 已恢复 tuple
    assert r_new.capability == peer_cap
    view = CNR()
    view.hello(_cap("newcomer-1", "summarizer", ("SUMMARIZE",), ("text", "embedding")))
    view.observe(CNR.accept_reply(r_new, q))
    assert view.negotiate("newcomer-1", "retriever-1") == "embedding"
    assert view.resolve(role="retriever") == ("retriever-1",)
    # 各端字节计量 = 自己发出的帧长（query 与 reply 帧长不同是正常的）
    assert newcomer_left.transport_bytes == len(q.to_wire().encode("utf-8"))
    assert peer_right.transport_bytes == len(r.to_wire().encode("utf-8"))


# ---------------- 4. 注册幂等 / 冲突 / 边界 ----------------


def test_register_idempotent_and_conflicts():
    peers = _three_peers()
    m = Metrics()
    sched = Scheduler(peers, cnr=CNR(), metrics=m)
    newcomer = _Agent(_cap("summarizer-1", "summarizer", ("SUMMARIZE",)))
    sched.register(newcomer)
    n_after_first = m.messages

    same = _Agent(_cap("summarizer-1", "summarizer", ("SUMMARIZE",)))
    view = sched.register(same)  # 同 id 同能力：幂等，不重发消息流
    assert m.messages == n_after_first
    assert set(view) == {"planner-1", "retriever-1", "executor-1"}

    changed = _Agent(_cap("summarizer-1", "summarizer", ("SUMMARIZE", "WRITE")))
    with pytest.raises(ValueError, match="different capability"):
        sched.register(changed)

    dup_role = _Agent(_cap("summarizer-2", "summarizer", ("SUMMARIZE",)))
    with pytest.raises(ValueError, match="role.*already held"):
        sched.register(dup_role)


def test_register_without_peers_and_without_cnr():
    # 无在场 peer：0 消息、空视图，注册仍成功
    m = Metrics()
    sched = Scheduler([], cnr=CNR(), metrics=m)
    assert sched.register(_Agent(_cap("a-1", "planner"))) == {}
    assert m.messages == 0

    # 无 CNR：消息流照常发生（协议层独立），响应仍返回（已校验），但无视图可供协商
    m2 = Metrics()
    sched2 = Scheduler(_three_peers()[:1], cnr=None, metrics=m2)
    accepted = sched2.register(_Agent(_cap("b-1", "summarizer")))
    assert set(accepted) == {"planner-1"}  # 已校验响应如实返回
    assert m2.messages == 2  # 1 query + 1 reply 仍计量（控制面开销如实）


def test_from_wire_rejects_malformed_payloads():
    with pytest.raises(ValueError, match="missing required field"):
        Message.from_wire('{"sender":"a","receiver":"b"}')  # 缺 action
    with pytest.raises(ValueError, match="invalid capability"):
        Message.from_wire(
            '{"msg_id":"m","sender":"a","receiver":"b","action":"CAP_REPLY","capability":{"agent_id":"b"}}'
        )  # capability 缺字段
    with pytest.raises(ValueError, match="not a JSON object"):
        Message.from_wire("[1,2,3]")
