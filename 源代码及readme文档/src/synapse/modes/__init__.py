"""协作模式（赛题 M3）：纯文本基线 vs 结构化协议（SYNAPSE）。"""
from .text_mode import run_text
from .synapse_mode import SynapseSession

__all__ = ["run_text", "SynapseSession"]
