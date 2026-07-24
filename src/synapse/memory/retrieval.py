"""混合检索（赛题 M6：关键词 + 标签 + 语义相似度，跨 Agent 跨任务复用）。"""
from __future__ import annotations

from ..stateplane.embedding import cosine


def _tokens(text: str) -> set[str]:
    return set((text or "").lower().split())


class HybridRetriever:
    def __init__(self, store, embedder, cfg):
        self._store = store
        self._embedder = embedder
        self._cfg = cfg

    def search(self, query: str, tags=None, k: int | None = None):
        """返回 [(unit, score)]，按融合分降序，命中单元 reuse_count += 1。

        §3.1 演化链：默认过滤已被取代（superseded_by 非空）的单元；命中单元的 links 指向的
        关联单元以小权重补进候选集（A-MEM 风格链接扩展），扩大有效召回而不引入过时记忆。
        """
        k = k or self._cfg.retrieval_k
        units = self._store.all()
        if not units:
            return []
        q_tokens = _tokens(query)
        q_tags = set(tags or ())
        q_emb = self._embedder.encode(query)
        c = self._cfg

        active = [u for u in units if u.superseded_by is None]  # 默认不返回已取代单元
        by_id = {u.mem_id: u for u in units}
        scored = []
        for u in active:
            kw = _jaccard(q_tokens, _tokens(u.content + " " + u.task_topic))
            tg = _jaccard(q_tags, set(u.tags)) if q_tags else 0.0
            sem = cosine(q_emb, u.embedding) if u.embedding else 0.0
            score = c.w_keyword * kw + c.w_tag * tg + c.w_semantic * sem
            scored.append((u, score))

        # 链接扩展：命中单元的 links（被取代的旧版本/相关单元）以 0.3× 原分补进，若仍活跃
        link_extra: dict[str, float] = {}
        for u, s in scored:
            if s <= 0 or not u.links:
                continue
            for lid in u.links:
                lu = by_id.get(lid)
                if lu and lu.superseded_by is None and lid not in {x.mem_id for x, _ in scored}:
                    link_extra[lid] = max(link_extra.get(lid, 0.0), s * 0.3)
        for lid, sc in link_extra.items():
            scored.append((by_id[lid], sc))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = [(u, s) for u, s in scored[:k] if s > 0]
        for u, _ in top:
            u.reuse_count += 1
        return top


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
