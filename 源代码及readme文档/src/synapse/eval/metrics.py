"""度量（赛题 M8）：消息数 / 文本 token·字节 / 非文本字节·次数 / 耗时 / 记忆命中率 / 提升。"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Metrics:
    mode: str = ""
    messages: int = 0
    text_bytes: int = 0  # 文本载荷 utf-8 字节
    text_tokens: int = 0  # 文本载荷词数（token 近似）
    header_bytes: int = 0  # 结构化消息头字节
    nontext_transfers: int = 0  # 非文本状态传递次数
    nontext_bytes: int = 0  # 非文本载荷字节（残差/向量）
    fallbacks: int = 0  # 校验回退次数
    memory_queries: int = 0
    memory_hits: int = 0
    llm_tokens: int = 0  # 旧口径(=输出)；向后兼容合成管线
    llm_input_tokens: int = 0  # 真实 LLM 输入 token（通信成本主项：上下文/历史摄入）
    llm_output_tokens: int = 0  # 真实 LLM 输出 token
    latency_s: float = 0.0
    quality: float = 0.0  # CoQA: 词级 F1
    # §1.2 三档混合协议：发送方按预测基相似度预判选档，而非只靠接收方事后校验
    tier_residual: int = 0  # residual 档（预测基强，sim≥阈值）
    tier_embedding: int = 0  # embedding+text摘要档（预测基弱，0<sim<阈值）
    tier_text: int = 0  # text 档（无预测基/首轮冷启动/校验失败回退）
    frozen_snapshot_injections: int = 0  # §4.1 frozen-snapshot 记忆注入次数（保前缀缓存）
    result_spills: int = 0  # §2.3 result 序列化超阈值 → CAS 句柄 + 短摘要 的 spill 次数

    @property
    def llm_total_tokens(self) -> int:
        """真实通信成本 = 输入 + 输出 token（M8 通信效率主指标）。"""
        return self.llm_input_tokens + self.llm_output_tokens

    def record_message(self, msg) -> None:
        self.messages += 1
        self.header_bytes += msg.header_bytes()
        tb = msg.text_bytes()
        if tb:
            self.text_bytes += tb
            self.text_tokens += len((msg.text or "").split())
        nb = msg.meta.get("nontext_bytes", 0)
        if nb:
            self.nontext_transfers += 1
            self.nontext_bytes += nb
        if msg.meta.get("fallback"):
            self.fallbacks += 1
        # §1.2 三档混合协议档位统计（发送方预判标注，meta["tier"] ∈ residual|embedding|text）
        tier = msg.meta.get("tier")
        if tier == "residual":
            self.tier_residual += 1
        elif tier == "embedding":
            self.tier_embedding += 1
        elif tier == "text":
            self.tier_text += 1
        if msg.meta.get("spilled"):  # §2.3 result spill 降级
            self.result_spills += 1

    def record_query(self, hit: bool) -> None:
        self.memory_queries += 1
        if hit:
            self.memory_hits += 1

    @property
    def wire_bytes(self) -> int:
        """总线字节 = 结构化头 + 文本载荷 + 非文本载荷。"""
        return self.header_bytes + self.text_bytes + self.nontext_bytes

    @property
    def hit_rate(self) -> float:
        return self.memory_hits / self.memory_queries if self.memory_queries else 0.0

    def summary(self) -> dict:
        d = asdict(self)
        d["wire_bytes"] = self.wire_bytes
        d["hit_rate"] = round(self.hit_rate, 3)
        d["llm_total_tokens"] = self.llm_total_tokens
        return d


def _pct(base: float, new: float) -> float:
    return round((base - new) / base * 100, 2) if base else 0.0


def improvement(text_m: Metrics, syn_m: Metrics) -> dict:
    """synapse 相对 text 基线的提升（正=更省/更快）。

    通信效率主指标 = 真实 LLM (输入+输出) token 节省（同口径两模式）。
    """
    return {
        "llm_token_saved_pct": _pct(text_m.llm_total_tokens, syn_m.llm_total_tokens),
        "llm_input_saved_pct": _pct(text_m.llm_input_tokens, syn_m.llm_input_tokens),
        "wire_bytes_saved_pct": _pct(text_m.wire_bytes, syn_m.wire_bytes),
        "token_saved_pct": _pct(  # 旧口径(消息文本+输出)，向后兼容；通信效率请看 llm_token_saved_pct
            text_m.text_tokens + text_m.llm_tokens, syn_m.text_tokens + syn_m.llm_tokens
        ),
        "latency_saved_pct": _pct(text_m.latency_s, syn_m.latency_s),
        "synapse_hit_rate": round(syn_m.hit_rate, 3),
        "synapse_fallbacks": syn_m.fallbacks,
    }
