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

    def search(self, query: str, tags=None, k: int | None = None, consume_k: int = 1):
        """返回 [(unit, score)]，按融合分降序；仅被消费的 top-1 计 reuse_count。

        §3.1 演化链（V3-04 附带修复）：主结果默认过滤已被取代单元；命中单元的 links 指向的
        **历史版本（superseded）**以 0.3× 原分补进候选集——演化链上的旧版本正是链接扩展
        要召回的内容（彻查 P1-1：旧条件拒收 superseded 节点导致"沿链接扩大召回"从未发生）。
        复用计数语义（彻查 P1-3 + GPT 终审）：默认仅 top-1 计复用；调用方实际消费 k 个单元时
        显式传 consume_k=k（如 CoQA 句级/历史检索），链接扩展单元不计。
        """
        k = k or self._cfg.retrieval_k
        units = self._store.all()
        if not units:
            return []
        q_tokens = _tokens(query)
        q_tags = set(tags or ())
        q_emb = self._embedder.encode(query)
        c = self._cfg

        active = [u for u in units if u.superseded_by is None]  # 主结果不返回已取代单元
        by_id = {u.mem_id: u for u in units}
        scored_ids: set[str] = set()
        scored = []
        for u in active:
            kw = _jaccard(q_tokens, _tokens(u.content + " " + u.task_topic))
            tg = _jaccard(q_tags, set(u.tags)) if q_tags else 0.0
            sem = cosine(q_emb, u.embedding) if u.embedding else 0.0
            score = c.w_keyword * kw + c.w_tag * tg + c.w_semantic * sem
            scored.append((u, score))
            scored_ids.add(u.mem_id)

        # 链接扩展：命中单元的 links（被取代的历史版本/相关单元）以 0.3× 原分补进
        link_extra: dict[str, float] = {}
        for u, s in scored:
            if s <= 0 or not u.links:
                continue
            for lid in u.links:
                lu = by_id.get(lid)
                if lu and lid not in scored_ids:
                    link_extra[lid] = max(link_extra.get(lid, 0.0), s * 0.3)
        for lid, sc in link_extra.items():
            scored.append((by_id[lid], sc))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = [(u, s) for u, s in scored[:k] if s > 0]
        for u, _s in top[: max(0, consume_k)]:
            u.reuse_count += 1  # 仅被消费的前 consume_k 个计复用；扩展单元不计
        return top


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
