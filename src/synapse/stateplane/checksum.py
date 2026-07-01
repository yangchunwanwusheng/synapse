"""校验和（赛题 M4：非文本状态传递的正确性保障）。

对量化网格上的 Y 取哈希；接收方残差重构后比对，不符则回退取全量，
保证有损残差信道端到端绝不静默出错（代价 O(几十字节)）。
"""
from __future__ import annotations

import hashlib


def digest_ints(ints, size: int = 8) -> str:
    """对整数向量（量化网格上的 Y）取定长哈希（默认 8 字节）。"""
    h = hashlib.blake2b(digest_size=size)
    for x in ints:
        h.update(int(x).to_bytes(4, "big", signed=True))
    return h.hexdigest()


def digest_bytes(data: bytes, size: int = 8) -> str:
    return hashlib.blake2b(data, digest_size=size).hexdigest()


def verify(ints, checksum: str) -> bool:
    return digest_ints(ints) == checksum
