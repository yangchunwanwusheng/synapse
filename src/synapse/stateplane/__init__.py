"""③ 状态交换·数据平面（赛题 M4 非文本状态传递核心）。

- CAS        : 内容寻址库，只传接收方缺的差集
- Embedder   : 句向量（HashEmbedder 离线兜底 / SentenceEmbedder 真实路径）
- ResidualCodec: 预测残差编码（只传必要分量）+ 语义校验回退
"""
from .cas import CAS
from .embedding import Embedder, HashEmbedder, cosine
from .residual import ResidualCodec, ResidualPacket
from .checksum import digest_ints, digest_bytes, verify

__all__ = [
    "CAS", "Embedder", "HashEmbedder", "cosine",
    "ResidualCodec", "ResidualPacket", "digest_ints", "digest_bytes", "verify",
]
