"""共享记忆单元与存储（赛题 M5：元数据齐全 + 统一 schema）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from ..stateplane.checksum import digest_bytes
from ..stateplane.embedding import cosine

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
    links: tuple[str, ...] = ()  # §3.1 演化链：相关/被取代记忆的 mem_id（A-MEM 风格动态链接）
    superseded_by: str | None = None  # §3.1 取代标记；非 None 表示已被更新版本取代，检索默认过滤

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
        supersede_threshold: float = 0.97,
    ) -> MemoryUnit:
        if kind not in VALID_KINDS:
            raise ValueError(f"未知记忆类型 kind={kind!r}，应属 {VALID_KINDS}")
        mem_id = digest_bytes(f"{source_agent}|{task_topic}|{content}".encode("utf-8"), size=12)
        new_emb = self._embedder.encode(content)
        # §3.1 A-MEM 风格取代检测：写入前扫描同 topic + kind 的活跃单元，
        # 若内容相似度 ≥ 阈值 → 标记旧单元被取代、新单元继承 links（演化链而非无限堆积）
        superseded_ids: list[str] = []
        for old in self._units.values():
            if (
                old.mem_id != mem_id
                and old.superseded_by is None
                and old.task_topic == task_topic
                and old.kind == kind
                and old.embedding
                and cosine(new_emb, old.embedding) >= supersede_threshold
            ):
                old.superseded_by = mem_id
                superseded_ids.append(old.mem_id)
        # 新单元 links = 被取代的旧单元（演化追溯链）
        prior_links = tuple(superseded_ids)
        unit = MemoryUnit(
            mem_id=mem_id,
            source_agent=source_agent,
            created_at=datetime.now(timezone.utc).isoformat(),
            task_topic=task_topic,
            summary=summary,
            kind=kind,
            content=content,
            tags=tuple(tags),
            embedding=new_emb,
            task_id=task_id,
            links=prior_links,
        )
        self._units[mem_id] = unit  # 内容寻址：同内容幂等去重
        return unit

    def upsert_prototype(
        self,
        topic: str,
        embedding: list[float],
        summary: str = "",
        n_evidence: int = 0,
        n_tasks: int = 0,
    ) -> MemoryUnit:
        """巩固原型：以给定(质心)embedding 建/更新一个 topic 级 experience 单元（不经内容再嵌入）。

        原型逼近 topic 的代表向量 → 作更优预测基 → 残差更稀疏 → 非文本字节更少。幂等：同 topic 覆盖。
        §3.4 增量摘要：summary 带上 evidence 条数 / 覆盖任务数 / 更新日期，记忆可读性直接影响评审观感。
        """
        mem_id = "proto:" + digest_bytes(topic.encode("utf-8"), size=10)
        prev = self._units.get(mem_id)
        if not summary:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            summary = f"prototype:{topic} | {n_evidence}evidence | 覆盖{n_tasks}任务 | 更新{date}"
        self._units[mem_id] = MemoryUnit(
            mem_id=mem_id,
            source_agent="consolidator",
            created_at=prev.created_at if prev else datetime.now(timezone.utc).isoformat(),
            task_topic=topic,
            summary=summary,
            kind="experience",
            content=f"consolidated prototype for {topic}",
            tags=tuple(topic.split()),
            embedding=embedding,
            reuse_count=prev.reuse_count if prev else 0,
            links=(prev.mem_id,) if prev else (),  # 沿演化链继承前版原型
        )
        if prev:
            prev.superseded_by = mem_id  # 旧原型被新原型取代
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
