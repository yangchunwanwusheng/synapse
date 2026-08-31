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


def digest_packet(
    payload: bytes,
    base_handle: str | None,
    generation: int,
    session_id: str = "",
    domain: str = "",
    content_digest: str = "",
    size: int = 8,
    key: bytes | None = None,
) -> str:
    """L1 完整性/认证哈希：H(payload || base_handle || generation || session || domain || content)。

    域均为线缆双方可见内容（长度前缀防拼接歧义）：
    - payload：residual 字节（residual 档）或全量量化向量字节（embedding 档）
    - base_handle：预测基引用（mem_id；零基/embedding 档为空串）
    - generation：任务代（绑定任务代，检测跨代陈旧 packet——非完整重放防护）
    - session_id：会话标识（防跨会话重放；跨进程时经 CNR hello 交换，见设计文档）
    - domain：payload_kind（防 residual/embedding 跨域字节复用）
    - content_digest：发送方声明的恢复文本摘要（身份校验绑定，防帧与内容错配）
    - key：会话 MAC 密钥（blake2b keyed）——带 key 为认证完整性（MAC），能改 payload 的
      主动方无 key 不能重算校验和；无 key 仅为损坏/未同步篡改检测（integrity）。
      key 分发：同进程自动共享；跨进程经 CNR hello 协商（路线图，见设计文档 §6）。
    """
    h = hashlib.blake2b(digest_size=size, key=key) if key else hashlib.blake2b(digest_size=size)
    h.update(len(payload).to_bytes(8, "big"))
    h.update(payload)
    h.update((base_handle or "").encode("utf-8"))
    h.update(int(generation).to_bytes(8, "big", signed=True))
    h.update((session_id or "").encode("utf-8"))
    h.update((domain or "").encode("utf-8"))
    h.update((content_digest or "").encode("utf-8"))
    return h.hexdigest()


def verify_packet(
    payload: bytes,
    base_handle: str | None,
    generation: int,
    checksum: str,
    session_id: str = "",
    domain: str = "",
    content_digest: str = "",
    key: bytes | None = None,
) -> bool:
    """接收方复算 L1：仅凭线缆可见内容（+会话密钥）比对。"""
    return (
        digest_packet(payload, base_handle, generation, session_id, domain, content_digest, key=key)
        == checksum
    )
