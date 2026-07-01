"""巩固器（睡眠/回放）：跨任务巩固记忆，使记忆朝任务分布收敛。

机制：按 topic 把 evidence 单元的 embedding 取均值并归一化，建/更新一个原型单元
(kind=experience)。原型逼近该 topic 的代表向量 → 作预测基比任一单条更接近新任务的 Y
→ 残差更稀疏 → 非文本字节随经验进一步减少。
归一化到单位范数以匹配句向量尺度（否则质心范数偏小 → 残差反增）。
"""

from __future__ import annotations

import math


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Consolidator:
    def __init__(self, cfg):
        self._cfg = cfg

    def consolidate(self, store) -> int:
        """按 topic 对 evidence 单元 embedding 取均值并归一化 → 建/更新原型。返回更新的原型数。"""
        groups: dict[str, list[list[float]]] = {}
        for u in store.all():
            if u.kind == "evidence" and u.embedding:
                groups.setdefault(u.task_topic, []).append(u.embedding)
        n = 0
        for topic, embs in groups.items():
            if len(embs) < 2:  # 单样本无可巩固
                continue
            dim = len(embs[0])
            centroid = [sum(e[i] for e in embs) / len(embs) for i in range(dim)]
            store.upsert_prototype(topic, _normalize(centroid))
            n += 1
        return n
