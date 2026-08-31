"""轻量统计（纯 stdlib，无 scipy）：均值±标准差、配对自助法 95% CI、胜负计数。

用于实验验证稳健化：多次运行(捕捉 temp=0 MoE 非确定噪声) + 配对比较(同题 text vs synapse)，
给出"省 token 不伤质量"的可辩护非劣结论，而非单次点估计。
"""

from __future__ import annotations

import random
import statistics


def mean_std(xs: list[float]) -> dict:
    """样本均值与标准差（n<2 时 std=0）。"""
    if not xs:
        return {"mean": 0.0, "std": 0.0, "n": 0}
    mu = statistics.fmean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {"mean": round(mu, 4), "std": round(sd, 4), "n": len(xs)}


def bootstrap_ci(xs: list[float], iters: int = 5000, alpha: float = 0.05, seed: int = 0) -> list[float]:
    """均值的自助法 (1-alpha) 置信区间（可复现：固定种子）。"""
    if not xs:
        return [0.0, 0.0]
    if len(xs) == 1:
        return [round(xs[0], 4), round(xs[0], 4)]
    rnd = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += xs[rnd.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(alpha / 2 * iters)]
    hi = means[int((1 - alpha / 2) * iters)]
    return [round(lo, 4), round(hi, 4)]


def cluster_bootstrap_ci(
    clusters: list[list[float]], iters: int = 5000, alpha: float = 0.05, seed: int = 0
) -> list[float]:
    """题目级 cluster bootstrap：先题内均值，再在题目之间有放回抽样。

    每个 cluster 是同一题的重复运行观测。这样不会把同题重复调用误当成独立样本。
    """
    if any(not cluster for cluster in clusters):
        raise ValueError("clusters must not contain empty observations")
    return bootstrap_ci([statistics.fmean(cluster) for cluster in clusters], iters, alpha, seed)


def variance_components(clusters: list[list[float]]) -> dict[str, float]:
    """分列描述性总体方差（pvariance，分母 N），不是无偏方差分量估计。

    between_item 为题均值的总体方差；within_item 为有重复观测的题内总体
    方差的等权均值。仅诊断噪声来源，不用于显著性/非劣推断。
    """
    if not clusters or any(not cluster for cluster in clusters):
        return {"between_item": 0.0, "within_item": 0.0}
    item_means = [statistics.fmean(cluster) for cluster in clusters]
    within = [statistics.pvariance(cluster) for cluster in clusters if len(cluster) > 1]
    return {
        "between_item": round(statistics.pvariance(item_means), 6) if len(item_means) > 1 else 0.0,
        "within_item": round(statistics.fmean(within), 6) if within else 0.0,
    }


def alternating_order(item_ids: list[str], seed: int = 0) -> list[dict[str, str]]:
    """固定 seed 洗牌后按题交替 AB/BA，并返回可落档执行序列。"""
    ordered = list(item_ids)
    random.Random(seed).shuffle(ordered)
    return [{"qid": qid, "order": "AB" if i % 2 == 0 else "BA"} for i, qid in enumerate(ordered)]


def paired_winloss(text: list[float], syn: list[float], eps: float = 1e-9) -> dict:
    """同题配对胜负：synapse 优 / 平 / 劣 计数。"""
    win = sum(1 for t, s in zip(text, syn) if s > t + eps)
    loss = sum(1 for t, s in zip(text, syn) if t > s + eps)
    return {"syn_win": win, "tie": len(text) - win - loss, "syn_loss": loss}
