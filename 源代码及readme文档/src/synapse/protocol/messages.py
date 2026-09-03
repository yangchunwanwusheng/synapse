"""结构化通信消息（赛题 M2）。

通信内容收敛为高密度语义单元 {action, params, result, capability}，
非文本载荷以 CAS 句柄 + payload_kind 引用，**不把全部协作信息塞进自然语言文本**。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum


class ActionType(str, Enum):
    # 握手 / 能力发现（CNR）
    HELLO = "HELLO"
    CAP_QUERY = "CAP_QUERY"
    CAP_REPLY = "CAP_REPLY"
    # 角色动作
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    EXECUTE = "EXECUTE"
    SUMMARIZE = "SUMMARIZE"
    # 言语行为（tell/ask/write/hold）
    TELL = "TELL"
    ASK = "ASK"
    WRITE = "WRITE"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Capability:
    """能力描述（M2 握手/能力发现/协议映射）。"""

    agent_id: str
    role: str  # planner|retriever|executor|summarizer
    actions: tuple[str, ...]
    encodings: tuple[str, ...]  # text|embedding|residual|hidden
    model_family: str  # 同族判定（隐状态零拷贝前提）
    probe: tuple[str, ...] = ()  # §2.2 声明可被运行时探测的能力项（如 codeact_sandbox），check_fn 实测后生效

    @classmethod
    def from_dict(cls, d: dict) -> "Capability":
        """wire dict（to_wire/asdict 产物，tuple 已序列化为 list）→ Capability。

        #149013 发现消息流接收侧需要：JSON 线缆回读时把 list 恢复为 tuple（frozen
        dataclass 的哈希/相等语义依赖 tuple）。字段缺失/类型不符显式失败，不静默
        造出空能力（能力声明是路由依据，半损数据比缺数据更危险）。
        """
        try:
            return cls(
                agent_id=str(d["agent_id"]),
                role=str(d["role"]),
                actions=tuple(str(a) for a in d["actions"]),
                encodings=tuple(str(e) for e in d["encodings"]),
                model_family=str(d["model_family"]),
                probe=tuple(str(p) for p in d.get("probe", ())),
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"invalid capability payload: missing/bad field {e}") from e


@dataclass
class Message:
    """Agent 间结构化消息。"""

    msg_id: str
    sender: str
    receiver: str
    action: str
    params: dict = field(default_factory=dict)
    result: dict | None = None
    capability: Capability | None = None
    handles: tuple[str, ...] = ()  # CAS 句柄（非文本载荷引用）
    payload_kind: str = "none"  # none|text|embedding|residual|hidden
    checksum: str | None = None  # hash(Y)，Verified Lossy
    text: str | None = None  # 文本载荷（text 模式或回退）
    meta: dict = field(default_factory=dict)

    def header_bytes(self) -> int:
        """结构化头字节数（不含 CAS 中的非文本 blob 与 text 正文）。

        用于 M8 通信开销统计：synapse 模式 wire = header_bytes + 非文本字节(CAS)。
        """
        head = {
            "msg_id": self.msg_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action,
            "params": self.params,
            "result": self.result,
            "handles": list(self.handles),
            "payload_kind": self.payload_kind,
            "checksum": self.checksum,
        }
        return len(json.dumps(head, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def text_bytes(self) -> int:
        return len(self.text.encode("utf-8")) if self.text else 0

    def to_wire(self) -> str:
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_wire(cls, wire: str | bytes) -> "Message":
        """to_wire() 的逆（#149015 发现消息流接收侧）：JSON → Message。

        tuple 字段（handles/capability 内的 actions/encodings/probe）从 JSON list
        恢复为 tuple；capability 经 Capability.from_dict 严格解析（坏数据显式失败）。
        缺 sender/receiver/action 的载荷不是本协议消息，显式拒绝。
        """
        if isinstance(wire, bytes):
            wire = wire.decode("utf-8")
        d = json.loads(wire)
        if not isinstance(d, dict):
            raise ValueError("wire payload is not a JSON object")
        for key in ("sender", "receiver", "action"):
            if not d.get(key):
                raise ValueError(f"wire payload missing required field {key!r}")
        cap = d.get("capability")
        return cls(
            msg_id=str(d.get("msg_id", "")),
            sender=str(d["sender"]),
            receiver=str(d["receiver"]),
            action=str(d["action"]),
            params=dict(d.get("params") or {}),
            result=d.get("result"),
            capability=Capability.from_dict(cap) if cap is not None else None,
            handles=tuple(str(h) for h in d.get("handles") or ()),
            payload_kind=str(d.get("payload_kind", "none")),
            checksum=d.get("checksum"),
            text=d.get("text"),
            meta=dict(d.get("meta") or {}),
        )


def spill_result(result: dict, cas, budget: int = 512) -> tuple[dict, tuple[str, ...]]:
    """§2.3 result 预算与 spill 降级（借鉴 hermes delegate 动态摘要预算 + spill-to-file）。

    若 result 序列化字节超 budget → 把完整 result 写入 CAS 返回句柄，result 字段替换为
    `{"spilled": True, "handle": h, "summary": <前 200 字符>}`；否则原样返回。
    返回 (新result, 新增handles)；让结构化协议具备大小自适应，与 §1.2 三档协议共用降级逻辑。
    """
    raw = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) <= budget:
        return result, ()
    handle = cas.put(raw)
    summary = json.dumps(result, ensure_ascii=False)[:200]
    return {"spilled": True, "handle": handle, "summary": summary}, (handle,)
