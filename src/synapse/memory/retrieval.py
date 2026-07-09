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
        """返回 [(unit, score)]，按融合分降序，命中单元 reuse_count += 1。"""
        k = k or self._cfg.retrieval_k
        units = self._store.all()
        if not units:
            return []
        q_tokens = _tokens(query)
        q_tags = set(tags or ())
        q_emb = self._embedder.encode(query)
        c = self._cfg

        scored = []
        for u in units:
            kw = _jaccard(q_tokens, _tokens(u.content + " " + u.task_topic))
            tg = _jaccard(q_tags, set(u.tags)) if q_tags else 0.0
            sem = cosine(q_emb, u.embedding) if u.embedding else 0.0
            score = c.w_keyword * kw + c.w_tag * tg + c.w_semantic * sem
            scored.append((u, score))

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
