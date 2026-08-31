"""向量可寻址索引（V3-04 真通路新增，赛题 M4+M5 交点）。

文本句柄 ↔ 量化向量的共享检索面：发送方 put(text_handle, quantize(Y))；
接收方凭重构向量 Ŷ（或全量向量）top-1 匹配恢复文本句柄——重建结果的消费出口，
取代"校验前直读全文"的旁路（R-P0-1）。进程内为线性扫描原型；跨进程/真实数据平面
（V3-05 之后的路线图项）替换为共享内存/faiss 后端时保持接口不变。
"""

from __future__ import annotations

from .embedding import cosine


class VectorIndex:
    def __init__(self):
        self._vecs: dict[str, list[int]] = {}

    def put(self, handle: str, vec) -> None:
        self._vecs[handle] = list(vec)

    def search(self, vec, k: int = 1) -> list[tuple[str, float]]:
        """按余弦降序返回前 k 个 (handle, sim)；空索引返回空表。"""
        hits = [(h, cosine(vec, v)) for h, v in self._vecs.items()]
        hits.sort(key=lambda x: x[1], reverse=True)
        return hits[:k]

    def __len__(self) -> int:
        return len(self._vecs)
