"""共享记忆单元与存储（赛题 M5：元数据齐全 + 统一 schema）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from ..stateplane.checksum import digest_bytes

VALID_KINDS = ("evidence", "strategy", "conclusion", "plan", "experience")


@dataclass
class MemoryUnit:
    mem_id: str  # M5 记忆 ID（内容寻址）
    source_agent: str  # M5 来源 Agent
    created_at: str  # M5 创建时间（ISO8601）
    task_topic: str  # M5 任务主题
    summary: str  # M5 摘要描述
    kind: str  # evidence|strategy|conclusion|plan|experience
    content: str
    tags: tuple[str, ...] = ()  # M6 标签检索
    embedding: list[float] | None = None  # M6 语义检索 + 预测基载体
    task_id: str = ""
    reuse_count: int = 0  # 复用计数（M8 命中率）

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryStore:
    """共享记忆库；write 自动补 ID/时间/embedding，支持 JSON 持久化。"""

    def __init__(self, embedder, path: str | None = None):
        self._embedder = embedder
        self._path = path
        self._units: dict[str, MemoryUnit] = {}
        if path:
            self.load(path)

    def write(
        self,
        *,
        source_agent: str,
        task_topic: str,
        summary: str,
        content: str,
        kind: str = "evidence",
        tags=(),
        task_id: str = "",
    ) -> MemoryUnit:
        if kind not in VALID_KINDS:
            raise ValueError(f"未知记忆类型 kind={kind!r}，应属 {VALID_KINDS}")
        mem_id = digest_bytes(f"{source_agent}|{task_topic}|{content}".encode("utf-8"), size=12)
        unit = MemoryUnit(
            mem_id=mem_id,
            source_agent=source_agent,
            created_at=datetime.now(timezone.utc).isoformat(),
            task_topic=task_topic,
            summary=summary,
            kind=kind,
            content=content,
            tags=tuple(tags),
            embedding=self._embedder.encode(content),
            task_id=task_id,
        )
        self._units[mem_id] = unit  # 内容寻址：同内容幂等去重
        return unit

    def upsert_prototype(self, topic: str, embedding: list[float], summary: str = "") -> MemoryUnit:
        """巩固原型：以给定(质心)embedding 建/更新一个 topic 级 experience 单元（不经内容再嵌入）。

        原型逼近 topic 的代表向量 → 作更优预测基 → 残差更稀疏 → 非文本字节更少。幂等：同 topic 覆盖。
        """
        mem_id = "proto:" + digest_bytes(topic.encode("utf-8"), size=10)
        prev = self._units.get(mem_id)
        self._units[mem_id] = MemoryUnit(
            mem_id=mem_id,
            source_agent="consolidator",
            created_at=prev.created_at if prev else datetime.now(timezone.utc).isoformat(),
            task_topic=topic,
            summary=summary or f"prototype:{topic}",
            kind="experience",
            content=f"consolidated prototype for {topic}",
            tags=tuple(topic.split()),
            embedding=embedding,
            reuse_count=prev.reuse_count if prev else 0,
        )
        return self._units[mem_id]

    def get(self, mem_id: str) -> MemoryUnit | None:
        return self._units.get(mem_id)

    def all(self) -> list[MemoryUnit]:
        return list(self._units.values())

    def __len__(self) -> int:
        return len(self._units)

    # ---- 持久化 ----
    def save(self, path: str | None = None) -> None:
        path = path or self._path
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump([u.to_dict() for u in self._units.values()], f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        import os

        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for d in json.load(f):
                d["tags"] = tuple(d.get("tags", ()))
                u = MemoryUnit(**d)
                self._units[u.mem_id] = u
