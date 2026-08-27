"""A/B 评测台（赛题 M3 双模式对照 + M9 ≥10 轮连续任务）。

同一任务序列分别跑 text 模式（无状态、无记忆基线）与 synapse 模式（共享记忆持续累积），
输出每轮 Metrics 轨迹——synapse 的 nontext_bytes 随累计经验下降。
"""

from __future__ import annotations


class ABRunner:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, tasks) -> dict:
        from ..modes.text_mode import run_text
        from ..modes.synapse_mode import SynapseSession
        from .metrics import improvement

        text_traj, syn_traj = [], []

        # text 基线：每任务独立、无记忆
        for t in tasks:
            text_traj.append(run_text(t, self.cfg)["metrics"])

        # synapse：共享记忆跨任务累积
        session = SynapseSession(self.cfg)
        for t in tasks:
            syn_traj.append(session.run_task(t)["metrics"])

        text_total = _agg(text_traj)
        syn_total = _agg(syn_traj)
        return {
            "rounds": len(tasks),
            "text_trajectory": [m.summary() for m in text_traj],
            "synapse_trajectory": [m.summary() for m in syn_traj],
            "text_total": text_total.summary(),
            "synapse_total": syn_total.summary(),
            "improvement": improvement(text_total, syn_total),
            "contraction_bytes": [m.nontext_bytes for m in syn_traj],  # 非文本字节轨迹 y 轴
        }


def _agg(traj):
    from .metrics import Metrics

    agg = Metrics(mode=traj[0].mode if traj else "")
    for m in traj:
        agg.absorb(m)  # 全字段统一累加（V3-02：修复 llm_input/output_tokens 漏加导致的 0.0）
    if traj:
        agg.quality /= len(traj)  # quality 是每任务均值量：累加后取均值
    return agg
