"""校验和（赛题 M4：非文本状态传递的正确性保障）。

L1 完整性校验（V3-04 重设计，R-P0-2）：哈希对象 = H(residual 字节 || base_handle ||
generation)，只含线缆双方可见内容，接收方可复算；拦截传输损坏 / 字节篡改 / 跨代重放。
旧 digest_ints(量化 Y) 依赖接收方不可能持有的精确 Y（其只有有损 Ŷ），数学上不可复算，
运行路径从未校验——保留仅作向后兼容，不再用于新路径。
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


def digest_packet(payload: bytes, base_handle: str | None, generation: int, size: int = 8) -> str:
    """L1 完整性哈希：H(payload || base_handle || generation)，长度前缀防拼接歧义。

    payload = residual 字节（residual 档）或全量量化向量字节（embedding 档）；
    base_handle = 预测基 CAS 句柄（embedding 档为空串）；generation = 任务代（防重放）。
    """
    h = hashlib.blake2b(digest_size=size)
    h.update(len(payload).to_bytes(8, "big"))
    h.update(payload)
    h.update((base_handle or "").encode("utf-8"))
    h.update(int(generation).to_bytes(8, "big", signed=True))
    return h.hexdigest()


def verify_packet(payload: bytes, base_handle: str | None, generation: int, checksum: str) -> bool:
    """接收方复算 L1：仅凭线缆可见内容（payload 字节 + base_handle + generation）比对。"""
    return digest_packet(payload, base_handle, generation) == checksum
