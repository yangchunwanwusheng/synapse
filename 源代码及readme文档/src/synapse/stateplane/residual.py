"""预测残差编码（赛题 M4：非文本中间状态传递的"生成/接收"核心）。

非文本载体 = 发送方观测 Y 与接收方可预测部分 Ŷ 之差的**稀疏残差**——只传必要分量，降低非文本字节。
按 |残差分量| 从大到小贪心地加入分量，直到重构 cos(Ŷ,Y) 达到失真目标 verify_threshold 即止。
预测基越准 → 达标所需分量越少 → 非文本字节越省。

校验回退：接收方用共享记忆里的同一证据正文重嵌入得真值 Y_true，校验 cos(Ŷ,Y_true)≥阈值；
若预测基失配或 int8 裁剪致失真过大 → 校验不达标 → 回退取全量文本，保证端到端正确性。
"""

from __future__ import annotations

from dataclasses import dataclass

from .checksum import digest_ints
from .embedding import cosine


def quantize_vec(vec: list[float], grid: int) -> list[int]:
    """量化到整数网格（公开接口：发送/接收双方在网格上对话）。"""
    return [int(round(v * grid)) for v in vec]


_quantize = quantize_vec  # 向后兼容旧内部名


def serialize_base(bq: list[int]) -> bytes:
    """量化向量序列化（int16 大端，dim×2 字节）——embedding 档全量 packet 的线缆形态。"""
    return b"".join(int(x).to_bytes(2, "big", signed=True) for x in bq)


def deserialize_base(b: bytes) -> list[int]:
    if len(b) % 2 != 0:
        raise ValueError(f"base/vector bytes length {len(b)} not even (int16 pairs)")
    return [int.from_bytes(b[i : i + 2], "big", signed=True) for i in range(0, len(b), 2)]


def _idx_width(dim: int) -> int:
    """稀疏残差索引字节宽：dim≤256 用 1 字节，更高维（真实句向量 2048）自动用 2 字节。"""
    return 1 if dim <= 256 else 2


@dataclass
class ResidualPacket:
    base_handle: str | None  # 预测基引用（旧路径=CAS 句柄；真通路=mem_id，见 synapse_mode）
    residual: bytes  # 稀疏 (index:1或2B, int8 value:1B) 对；索引宽由 dim 决定（见 _idx_width）
    dim: int
    nnz: int  # 非零残差分量数（越小越省）
    checksum: str  # 旧口径 digest_ints(量化Y)——仅展示透传；真通路 L1 在帧层单独计算（可复算）
    orig_bytes: int  # 全量 int16 编码字节（节省统计的分母）
    generation: int = 0  # 任务代（V3-04 真通路回填；旧路径恒 0）

    def size_bytes(self) -> int:
        """非文本载荷字节 = 稀疏残差 + 校验和(8B) + 头(4B)。"""
        return len(self.residual) + 8 + 4


class ResidualCodec:
    """稀疏 int8 预测残差编解码 + 语义校验。索引字节宽由 dim 自适应（≤256→1B，2048→2B）。"""

    INT8_MAX = 127

    def __init__(self, cfg):
        self.grid = cfg.quant_grid
        self.threshold = getattr(cfg, "verify_threshold", 0.97)

    def encode(
        self,
        Y: list[float],
        B_hat: list[float] | None,
        base_handle: str | None = None,
        generation: int = 0,
    ) -> ResidualPacket:
        yq = quantize_vec(Y, self.grid)
        iw = _idx_width(len(yq))  # 索引字节宽：≤256→1B，否则 2B（支持真实 2048 维句向量）
        bq = quantize_vec(B_hat, self.grid) if B_hat is not None else [0] * len(yq)

        # 贪心编码：先发 |残差| 最大的分量，逐个加入直到 cos(Ŷ,Y) 达失真目标即止
        order = sorted(range(len(yq)), key=lambda i: abs(yq[i] - bq[i]), reverse=True)
        yhat = list(bq)
        buf = bytearray()
        nnz = 0
        for i in order:
            if yq[i] - bq[i] == 0:
                break  # 余下分量残差为 0（已按 |r| 降序），再加无增益
            if cosine(yhat, yq) >= self.threshold:
                break  # 已达失真目标，停止（预测基越准 → 越早达标 → nnz 越小 → 字节越省）
            r = yq[i] - bq[i]
            rc = max(-self.INT8_MAX, min(self.INT8_MAX, r))  # 残差过大→裁剪（校验会捕获）
            yhat[i] = bq[i] + rc
            buf.append(i & 0xFF)
            if iw == 2:
                buf.append((i >> 8) & 0xFF)
            buf.append(rc & 0xFF)
            nnz += 1
        # checksum 保持旧口径 digest_ints(量化Y)——旧路径对外字段零变化（审查 P1-1）；
        # 真通路的 L1（可复算）在帧层用 checksum.digest_packet 单独计算
        checksum = digest_ints(yq)
        return ResidualPacket(base_handle, bytes(buf), len(yq), nnz, checksum, len(yq) * 2, generation)

    def decode(self, pkt: ResidualPacket, B_hat: list[float] | None) -> list[int]:
        """重构量化后的 Ŷ（旧对象接口：接收方直接持有发送方 B̂——仅旧旁路路径使用）。"""
        bq = quantize_vec(B_hat, self.grid) if B_hat is not None else [0] * pkt.dim
        return self.decode_bytes(pkt.residual, bq, pkt.dim)

    def decode_bytes(self, residual: bytes, bq_recv: list[int], dim: int) -> list[int]:
        """字节接口重构（V3-04 真通路）：接收方仅凭线缆可见内容（residual 字节 + 基）。

        bq_recv 为接收方解析出的量化基（真通路=自身记忆 embedding 量化；dim 以帧 meta 为准）。
        畸形输入（长度非 stride 对齐 / 索引越界 / 维度不符）抛 ValueError，由接收方转回退链，
        绝不让损坏帧崩溃任务（审查 P2-2）。
        """
        if dim <= 0 or len(bq_recv) != dim:
            raise ValueError(f"invalid dim/base: dim={dim}, base len={len(bq_recv)}")
        yq_hat = list(bq_recv)
        iw = _idx_width(dim)
        stride = iw + 1
        if len(residual) % stride != 0:
            raise ValueError(f"residual length {len(residual)} not stride-aligned ({stride})")
        for k in range(0, len(residual), stride):
            idx = residual[k] if iw == 1 else (residual[k] | (residual[k + 1] << 8))
            if idx >= dim:
                raise ValueError(f"residual index {idx} out of range (dim={dim})")
            val = residual[k + iw]
            if val >= 128:
                val -= 256  # int8 解码
            yq_hat[idx] = bq_recv[idx] + val
        return yq_hat

    def verify(self, yq_hat: list[int], Y_true: list[float]) -> bool:
        """语义校验：重构 Ŷ 与接收方重嵌入真值 Y_true 的 cos ≥ 阈值。

        失配（预测基 desync / 裁剪失真过大）→ cos 低于阈值 → 调用方回退取全量文本。
        """
        yq_true = _quantize(Y_true, self.grid)
        return cosine(yq_hat, yq_true) >= self.threshold
