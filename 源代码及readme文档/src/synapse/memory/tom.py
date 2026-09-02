"""ToM 预测器：估计接收方可复现的预测基 B̂（非文本状态传递的"可预测部分"）。

V3-04 选基三档（cfg.base_policy，字节按档分列报告——彻查 R-P0-6 口径修复）：
- oracle（旧默认，乐观口径）：发送方以 cos(candidate, Y) 择优——目标感知 codebook 选择，
  发送方知道 Y 才能选出，残差字节是"encoder-oracle 估算载荷"；
- query_top1（接收方可复现）：基 = query 检索序下首个内容记忆单元（kind=evidence）——
  接收方凭同一 query 可独立复现，无 Y 泄漏，是诚实口径的残差上界；派生单元
  （conclusion/experience）不作基（#149012：弱相关派生基使残差比零基更贵且无复现语义）；
- learned（学习式）：基 = topic 巩固原型（Consolidator 从历史 evidence 聚合的质心，
  kind=experience）——记忆随任务累积逼近任务分布，非参数学习；无原型时退化为 query_top1。
"""

from __future__ import annotations

from ..stateplane.embedding import cosine


class ToMPredictor:
    def __init__(self, retriever, embedder, cfg):
        self._retriever = retriever
        self._embedder = embedder
        self._cfg = cfg
        self.policy = getattr(cfg, "base_policy", "oracle")

    def estimate(
        self, receiver_id: str, query: str, target: list[float] | None = None, k: int | None = None
    ) -> list[float] | None:
        """返回 B̂_j（预测的接收方可复现向量）；无相关记忆时返回 None（退化为发全量）。"""
        emb, _, _ = self.best_base(self._retriever.search(query, k=k), target)
        return emb

    def best_base(self, results, target: list[float] | None) -> tuple[list[float] | None, str | None, float]:
        """按 cfg.base_policy 三档选预测基；返回 (embedding, mem_id, sim)。

        mem_id 句柄上线缆，接收方从自身共享记忆取同一单元复现该基（真通路 _receive_frame）。
        sim 供 §1.2 三档协议发送方预判选档（各档的 sim 语义见类 docstring）。
        """
        if not results:
            return None, None, 0.0
        if self.policy == "learned":
            # 学习式：优先 topic 巩固原型（历史 evidence 聚合质心，接收方共享）；无原型退化 query_top1
            for unit, _score in results:
                if unit.kind == "experience" and unit.embedding:
                    sim = cosine(unit.embedding, target) if target is not None else 0.0
                    return unit.embedding, unit.mem_id, sim
        if self.policy in ("query_top1", "learned"):
            # query_top1（或 learned 无原型退化）：检索序下首个**内容记忆（kind=evidence）**单元，
            # 不偷看 Y（sim 仅报告不参与选择）。#149012：conclusion/experience 等派生单元不作为
            # 预测基——基须是接收方共享记忆中可复现的内容单元（与 learned 的 experience 资格
            # 过滤同构）；无内容单元时诚实退化为发全量（None），不拿弱相关派生基凑数
            for unit, score in results:
                if unit.kind == "evidence" and unit.embedding:
                    sim = cosine(unit.embedding, target) if target is not None else max(score, 0.0)
                    return unit.embedding, unit.mem_id, sim
            return None, None, 0.0
        # oracle（旧默认）：cos(candidate, Y) 择优——发送方目标感知（乐观口径，字节分列另报）
        if target is None:
            return None, None, 0.0
        best, best_sim = None, -2.0
        for unit, _score in results:
            if not unit.embedding:
                continue
            sim = cosine(unit.embedding, target)
            if sim > best_sim:
                best_sim, best = sim, unit
        if best is None:
            return None, None, 0.0
        return best.embedding, best.mem_id, best_sim
