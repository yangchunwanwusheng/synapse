"""JL 随机投影域残差（V3-04 创新增强，cfg.residual_project_dim > 0 时启用）。

问题：高维稠密句向量（如 text-embedding-3-small 1536 维）能量均匀分布，原域稀疏残差
达标（cos≥阈值）所需分量数与维数同阶，残差字节 O(dim)——短文本场景下残差大于全文。

机制：确定性 ±1/√dim 随机投影到 k 维（JL 引理近似保持余弦几何）后，达标分量数按
维数比缩至 O(k)，残差字节 ≈ k/dim 倍下降。投影矩阵由 seed 派生（blake2b 逐元素符号，
行级缓存），发送/接收双方零存储共享同一投影；残差编码、向量索引、L2 校验全部在同一
投影域，content_digest 身份校验仍在文本域不受影响。

诚实边界：投影引入余弦估计方差 ~O(1/√k)，投影域 cos 阈值与原域语义存在偏差——
错配候选由身份校验拒绝并走回退链兜底；率失真收益与恢复质量按 Pareto 报告
（docs/design/v3-04-true-path.md §7），不调阈值掩盖。
"""

from __future__ import annotations

import hashlib
import math


class Projection:
    def __init__(self, dim: int, proj_dim: int, seed: int = 0):
        if proj_dim <= 0:
            raise ValueError(f"proj_dim must be > 0, got {proj_dim}")
        if proj_dim >= dim:
            raise ValueError(f"proj_dim {proj_dim} >= dim {dim}（投影须降维）")
        self.dim = dim
        self.proj_dim = proj_dim
        self.seed = seed
        self._scale = 1.0 / math.sqrt(dim)
        self._rows: dict[int, list[int]] = {}

    def _row(self, i: int) -> list[int]:
        """第 i 行符号向量（±1），seed 派生确定性生成，行级缓存。"""
        row = self._rows.get(i)
        if row is None:
            row = [
                1 if hashlib.blake2b(f"{self.seed}:{i}:{j}".encode(), digest_size=4).digest()[0] & 1 else -1
                for j in range(self.dim)
            ]
            self._rows[i] = row
        return row

    def project(self, vec: list[float]) -> list[float]:
        """投影并归一化（量化/余弦口径与原域一致）。维度不符显式失败。"""
        if len(vec) != self.dim:
            raise ValueError(f"projection dim mismatch: {len(vec)} != {self.dim}")
        out = []
        for i in range(self.proj_dim):
            row = self._row(i)
            s = 0.0
            for j in range(self.dim):
                if row[j] > 0:
                    s += vec[j]
                else:
                    s -= vec[j]
            out.append(s * self._scale)
        n = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / n for x in out]
