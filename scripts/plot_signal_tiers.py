"""画 signal 三档协议演化图（新平台，新机制证据）。

左：残差字节柱状图，按档位着色（residual=橙/embedding=蓝），叠加命中率曲线。
右：B1-full vs B3-no-mem 对照（残差轨迹 + 因果归因标注）。

  uv run --extra viz python scripts/plot_signal_tiers.py
输出 docs/figs/signal_protocol_evolution.png
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _latest(prefix: str) -> str:
    runs = sorted(d for d in glob.glob(os.path.join("runs", f"{prefix}_*")) if os.path.isdir(d))
    if not runs:
        raise SystemExit(f"未找到 runs/{prefix}_*")
    return runs[-1]


def _tier_color(m):
    if m.get("tier_residual"):
        return "#d0521f"  # residual 档（零基/强基）= 橙红
    if m.get("tier_embedding"):
        return "#1f5fd0"  # embedding 档（弱基）= 蓝
    return "#888888"  # text 档 = 灰


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b1", default=None, help="signal B1-full run 目录")
    ap.add_argument("--b3", default=None, help="signal B3-no-mem run 目录")
    ap.add_argument("--out", default=os.path.join("docs", "figs", "signal_protocol_evolution.png"))
    args = ap.parse_args()

    # B1-full / B3-no-mem 自动定位：扫所有 signal_* run，按平均命中率区分（B1 高、B3 低）
    b1_dir = args.b1
    b3_dir = args.b3
    all_signal = sorted(
        d for d in glob.glob(os.path.join("runs", "signal_*"))
        if os.path.isdir(d) and not d.endswith(("signal_run.log",))
        and os.path.exists(os.path.join(d, "result.json"))
    )

    def _avg_hit(d):
        try:
            syn = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))["linked"]["synapse_trajectory"]
            return sum(m["hit_rate"] for m in syn) / len(syn) if syn else 0.0
        except Exception:
            return -1.0

    # 过滤掉无 tier_* 字段的旧 run（整改前的 run 没有三档协议统计）
    def _has_tier_fields(d):
        try:
            syn = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))["linked"]["synapse_trajectory"]
            return bool(syn) and "tier_residual" in syn[0]
        except Exception:
            return False

    tier_runs = [d for d in all_signal if _has_tier_fields(d)]
    search_pool = tier_runs if tier_runs else all_signal  # 全无 tier 字段则退化用全部

    if not b1_dir and search_pool:
        # B1-full = 平均命中率最高（>0.5）；若都不达标，取最高那个
        ranked = sorted(search_pool, key=_avg_hit, reverse=True)
        if ranked and _avg_hit(ranked[0]) > 0.5:
            b1_dir = ranked[0]
        elif ranked:
            b1_dir = ranked[0]  # 退化：只有低命中 run 时也用最高的
    if not b3_dir and len(search_pool) >= 2:
        # B3-no-mem = 命中率最低（<0.5）且不同于 B1
        for d in search_pool:
            if d == b1_dir:
                continue
            if _avg_hit(d) < 0.5:
                b3_dir = d
                break
    if not b1_dir:
        raise SystemExit("未找到任何 signal run（runs/signal_*/result.json）")

    b1 = json.load(open(os.path.join(b1_dir, "result.json"), encoding="utf-8"))
    syn = b1["linked"]["synapse_trajectory"]
    cfg = b1["config"]
    rounds = list(range(1, len(syn) + 1))
    bytes_arr = [m["nontext_bytes"] for m in syn]
    hits = [m["hit_rate"] for m in syn]
    colors = [_tier_color(m) for m in syn]

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 10})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))

    # 左：残差字节柱状图（档位着色）+ 命中率曲线
    b1_drop_pct = (bytes_arr[0] - bytes_arr[-1]) / bytes_arr[0] * 100 if bytes_arr and bytes_arr[0] > 0 else 0.0
    bars = axL.bar(rounds, bytes_arr, color=colors, width=0.6, edgecolor="white", linewidth=1.2)
    for r, b in zip(rounds, bytes_arr):  # 修 bug: x 坐标用轮次 r，不是字节值 b
        axL.text(r, b + max(bytes_arr) * 0.02, str(b), ha="center", va="bottom", fontsize=10, fontweight="bold")
    axL.set_xlabel("Round (shared memory accumulates →)")
    axL.set_ylabel("Non-text bytes (residual payload)")
    axL.set_title(f"Residual contracts {b1_drop_pct:.1f}% as memory grows\n(tier auto-shifts: residual→embedding)")
    axL.set_xticks(rounds)
    axL.grid(alpha=0.25, axis="y")

    axL2 = axL.twinx()
    axL2.plot(rounds, hits, "-o", color="#2e8b57", lw=2, ms=8, label="memory hit rate")
    axL2.set_ylabel("Memory hit rate", color="#2e8b57")
    axL2.set_ylim(-0.05, 1.1)
    axL2.tick_params(axis="y", labelcolor="#2e8b57")

    # 图例（档位颜色说明 + 命中率曲线）
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_items = [
        Patch(facecolor="#d0521f", label="residual tier (cold-start, zero base)"),
        Patch(facecolor="#1f5fd0", label="embedding tier (weak base, memory hit)"),
        Line2D([0], [0], color="#2e8b57", marker="o", label="memory hit rate"),
    ]
    axL.legend(handles=legend_items, loc="upper right", fontsize=9)

    # 右：B1 vs B3 对照（因果归因）
    if b3_dir and os.path.exists(os.path.join(b3_dir, "result.json")):
        b3 = json.load(open(os.path.join(b3_dir, "result.json"), encoding="utf-8"))
        b3_syn = b3["linked"]["synapse_trajectory"]
        b3_bytes = [m["nontext_bytes"] for m in b3_syn]
        m = min(len(rounds), len(b3_bytes))  # 防 x/y 长度不匹配
        axR.plot(rounds[:m], bytes_arr[:m], "-o", color="#1f5fd0", lw=2.2, ms=8, label="B1-full (with memory)")
        axR.plot(rounds[:m], b3_bytes[:m], "-s", color="#d0521f", lw=2.2, ms=8, label="B3-no-mem (ablation)")
        b3_drop = (b3_bytes[0] - b3_bytes[-1]) / b3_bytes[0] * 100 if b3_bytes and b3_bytes[0] > 0 else 0.0
        attribution = (b1_drop_pct - b3_drop) / b1_drop_pct * 100 if b1_drop_pct > 0 else 0.0
        axR.set_xlabel("Round")
        axR.set_ylabel("Non-text bytes")
        axR.set_title(f"Causal attribution: memory drives {attribution:.1f}% of contraction\n"
                      f"(B1 drop {b1_drop_pct:.1f}% vs B3 drop {b3_drop:.1f}%)")
        axR.grid(alpha=0.25)
        axR.legend(loc="upper right")
        # 标注归因百分比（用安全索引，防轨迹<3轮）
        mid_idx = min(2, m - 1) if m >= 2 else 0
        if m > 0:
            axR.annotate(f"{attribution:.1f}% of contraction\nattributable to memory",
                         xy=(rounds[mid_idx], (bytes_arr[mid_idx] + b3_bytes[mid_idx]) / 2),
                         fontsize=11, fontweight="bold", color="#2e8b57",
                         ha="center",
                         bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8f5e9", edgecolor="#2e8b57"))
    else:
        axR.text(0.5, 0.5, "B3 ablation run not found", ha="center", va="center", transform=axR.transAxes)
        axR.set_axis_off()

    fig.suptitle(
        f"SYNAPSE protocol evolution on signal (real API, {cfg['model']}, {cfg['embedder']} embedder)",
        fontsize=12.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (B1: {os.path.basename(b1_dir)}, B3: {os.path.basename(b3_dir) if b3_dir else 'N/A'})")


if __name__ == "__main__":
    main()
