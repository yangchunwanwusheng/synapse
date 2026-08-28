"""内容寻址库（Content-Addressed Store）。

非文本载荷以内容哈希为句柄存取；diff 只传接收方缺的差集，避免重复传输。
"""

from __future__ import annotations

from .checksum import digest_bytes


class CAS:
    def __init__(self):
        self._store: dict[str, bytes] = {}
        self.writes = 0  # V3-02：put 次数（共享状态建立成本，cold 口径）
        self.write_bytes = 0  # put 累计字节

    def put(self, data: bytes) -> str:
        handle = digest_bytes(data, size=12)
        self._store[handle] = data
        self.writes += 1
        self.write_bytes += len(data)
        return handle

    def get(self, handle: str) -> bytes | None:
        return self._store.get(handle)

    def has(self, handle: str) -> bool:
        return handle in self._store

    def diff(self, local_handles, remote_handles) -> list[str]:
        """remote 有而 local 缺的句柄（需要传输的差集）。"""
        local = set(local_handles)
        return [h for h in remote_handles if h not in local]

    def __len__(self) -> int:
        return len(self._store)
