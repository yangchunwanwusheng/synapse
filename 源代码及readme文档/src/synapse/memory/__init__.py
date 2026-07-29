"""④ 共享记忆与检索（赛题 M5/M6）。

- MemoryUnit / MemoryStore : 统一记忆单元（ID/来源/时间/主题/摘要 元数据齐全）+ 持久化
- HybridRetriever          : 关键词 + 标签 + 语义混合检索，跨 Agent 跨任务复用
- ToMPredictor             : 估计接收方可复现的预测基 B̂（残差重构成功率自监督）
- Consolidator             : 跨任务巩固（使记忆朝任务分布收敛）
"""
from .store import MemoryUnit, MemoryStore
from .retrieval import HybridRetriever
from .tom import ToMPredictor
from .consolidate import Consolidator

__all__ = ["MemoryUnit", "MemoryStore", "HybridRetriever", "ToMPredictor", "Consolidator"]
