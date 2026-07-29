"""关联连续任务族（赛题 M7）。

- G1 主题深挖 + G2 关联演进：共享 topic 结构 → 跨任务记忆复用的前提。
- 漂移臂：中途切到弱相关主题 → 触发字节回弹（分布切换）。
- 负例族：刻意无共享结构 → 预期跨任务复用≈0（因果对照，区分度判定用）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    task_id: str
    topic: str
    query: str
    kind: str = "g1"  # g1 | g2 | drift | negative


def g1_family(n: int = 5, topic: str = "alpha") -> list[Task]:
    return [Task(f"g1-{i}", topic, f"deep dive {topic} hop {i}", "g1") for i in range(n)]


def g2_family(n: int = 5, topic: str = "alpha") -> list[Task]:
    # 复用 G1 的 topic 证据再分析（同 topic → 命中 G1 记忆）
    return [Task(f"g2-{i}", topic, f"reanalyze update compare {topic} iter {i}", "g2") for i in range(n)]


def linked_continuous(n_g1: int = 5, n_g2: int = 5, topic: str = "alpha") -> list[Task]:
    """≥2 组关联连续任务（M7）：G1 深挖 + G2 演进。"""
    return g1_family(n_g1, topic) + g2_family(n_g2, topic)


def drift_sequence(n: int = 5, topic: str = "alpha", drift_topic: str = "zeta") -> list[Task]:
    """G1 深挖后切到弱相关主题，触发字节回弹（分布切换 → 无共享记忆）。"""
    seq = g1_family(n, topic)
    seq += [Task(f"drift-{i}", drift_topic, f"new domain {drift_topic} hop {i}", "drift") for i in range(n)]
    return seq


# 真实但互不相关的主题（因果对照：证据实在，但无跨任务共享结构 → 预期复用≈0）
_NEG_TOPICS = (
    "the French Revolution of 1789",
    "photosynthesis in green plants",
    "blockchain consensus mechanisms",
    "the human adaptive immune system",
    "classical orbital mechanics",
    "supply and demand in economics",
    "plate tectonics and volcanism",
    "the history of jazz music",
)


def negative_family(n: int = 10) -> list[Task]:
    """无共享结构的对照族：每任务一个真实但互不相关的主题（证据实在，但无跨任务复用结构）。"""
    out = []
    for i in range(n):
        topic = _NEG_TOPICS[i % len(_NEG_TOPICS)]
        out.append(Task(f"neg-{i}", topic, f"explain the key facts about {topic}", "negative"))
    return out
