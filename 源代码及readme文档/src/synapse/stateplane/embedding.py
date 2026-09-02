"""句向量编码器。

- HashEmbedder：纯 stdlib 特征哈希，确定性、离线、零依赖（供 smoke/CI）。
  共享 token 的文本得到相近向量 → 支持语义检索与 ToM 预测的骨架演示。
- ApiEmbedder：真实路径（OpenAI 兼容句向量 API，embedder="api"）。

历史注记：sentence-transformers 本地档（embedder="sentence"）因 import 指向不存在模块
构成虚假门面，已随 #149012 物理删除；真实句向量统一走 api 档。
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):  # zip 静默截断会造出假高相似（V3-04 附带修复）
        raise ValueError(f"cosine dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Embedder(Protocol):
    dim: int

    def encode(self, text: str) -> list[float]: ...


class HashEmbedder:
    """特征哈希句向量（确定性、无第三方依赖）。"""

    def __init__(self, dim: int = 64):
        self.dim = dim
        self.requests = 0  # V3-02：encode 调用计数（离线路径同样计数，保证口径可比）

    def encode(self, text: str) -> list[float]:
        self.requests += 1
        vec = [0.0] * self.dim
        for tok in (text or "").lower().split():
            h = int(hashlib.blake2b(tok.encode("utf-8"), digest_size=8).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class ApiEmbedder:
    """真实句向量（Paratera /embeddings，OpenAI 兼容，无 GPU）。

    内置缓存 = "嵌入一次、跨轮复用"（记忆复用的微观体现）：同一句子/查询只调一次嵌入 API。
    高维不受残差码 dim≤256 限制——CoQA 检索只用 cosine 相似度，不走残差编码。
    """

    def __init__(self, cfg):
        from openai import OpenAI

        self._client = OpenAI(base_url=cfg.api_base, api_key=cfg.api_key())
        self._model = cfg.embed_model
        self._cache: dict[str, list[float]] = {}
        self.dim = 0
        self.requests = 0  # V3-02 cold：真实嵌入 API 请求次数
        self.cache_hits = 0  # V3-02 warm：缓存命中（零 API 请求复用）
        self.input_tokens = 0  # API usage.prompt_tokens 累计

    def _require_usage(self, resp) -> int:
        """嵌入响应必须携带可用 usage.prompt_tokens（PR #5 审查 P1：与 chat 侧同型 fail）。

        usage 对象缺失或 prompt_tokens 非 non-negative int → RuntimeError，禁止静默计 0
        （embedding 成本与 chat 同为证据链地基；离线 HashEmbedder 无 API 调用不受此约束）。
        """
        usage = getattr(resp, "usage", None)
        if usage is None:
            raise RuntimeError(
                "embeddings response missing usage: embed usage is mandatory for the V3-02 "
                "evidence ledger (check backend compatibility)."
            )
        pt = getattr(usage, "prompt_tokens", None)
        if type(pt) is not int or pt < 0:
            raise RuntimeError(
                f"embeddings usage.prompt_tokens invalid ({pt!r}): expected non-negative int; "
                "refusing to record 0."
            )
        return pt

    def encode(self, text: str) -> list[float]:
        text = text or ""
        if text in self._cache:
            self.cache_hits += 1
            return self._cache[text]
        resp = self._client.embeddings.create(model=self._model, input=[text])
        v = resp.data[0].embedding
        self.input_tokens += self._require_usage(resp)
        self.requests += 1
        self.dim = len(v)
        self._cache[text] = v
        return v


def make_embedder(cfg) -> Embedder:
    """按配置构造编码器；真实编码器缺失/无密钥时回退 HashEmbedder（保证可运行）。"""
    if cfg.embedder == "api":
        try:  # 真实句向量（Paratera GLM-Embedding-3 等）
            if cfg.api_key():
                return ApiEmbedder(cfg)
        except Exception:
            pass
    return HashEmbedder(dim=cfg.embed_dim)
