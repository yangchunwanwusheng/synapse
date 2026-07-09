"""ToM 预测器：估计接收方可复现的预测基 B̂（非文本状态传递的"可预测部分"）。

- L0（默认，确定性）：B̂ = 接收方共享记忆中与 query 相关单元 embedding 的加权聚合。
  记忆随任务累积 → 聚合越接近新任务的 Y → 残差越稀疏 → 非文本字节越少。
- L1（可选扩展）：小 MLP / 检索式，自监督信号 = 残差重构成功率。
"""

from __future__ import annotations

from ..stateplane.embedding import cosine


class ToMPredictor:
    def __init__(self, retriever, embedder, cfg):
        self._retriever = retriever
        self._embedder = embedder
        self._cfg = cfg

    def estimate(
        self, receiver_id: str, query: str, target: list[float] | None = None, k: int | None = None
    ) -> list[float] | None:
        """返回 B̂_j（预测的接收方可复现向量）；无相关记忆时返回 None（退化为发全量）。"""
        emb, _ = self.best_base(self._retriever.search(query, k=k), target)
        return emb

    def best_base(self, results, target: list[float] | None) -> tuple[list[float] | None, str | None]:
        """从接收方记忆候选中选与 target(Y) 最接近者作预测基（发送方残差优化）。

        base 经其 mem_id 句柄告知接收方——双方共享记忆，接收方取同一单元复现该基。
        返回 (embedding, mem_id)；无候选返回 (None, None)。命中越准 → 基越接近 Y
        → 残差越稀疏 → 非文本字节越少。
        """
        if not results or target is None:
            return None, None
        best, best_sim = None, -2.0
        for unit, _score in results:
            if not unit.embedding:
                continue
            sim = cosine(unit.embedding, target)
            if sim > best_sim:
                best_sim, best = sim, unit
        if best is None:
            return None, None
        return best.embedding, best.mem_id
