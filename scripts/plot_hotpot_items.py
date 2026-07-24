"""画 HotpotQA 逐题图（新平台数据，token 节省 + 逐题 F1 散点 + 难度分层）。

左：逐题 F1 散点（text vs synapse），按难度着色，连线表示提升/下降。
右：总体对比柱（token 节省、wire_bytes 节省、金标召回、平均 F1）。

  uv run --extra viz python scripts/plot_hotpot_items.py [--run runs/hotpot_YYYYmmdd_HHMMSS]
输出 docs/figs/hotpot_items.png
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


def _latest() -> str:
    # 排除非实验目录（ksweep/stats）
    runs = sorted(
        d for d in glob.glob(os.path.join("runs", "hotpot_*"))
        if os.path.isdir(d) and not os.path.basename(d).startswith(("hotpot_ksweep", "hotpot_stats"))
        and os.path.exists(os.path.join(d, "result.json"))
    )
    if not runs:
        raise SystemExit("未找到 runs/hotpot_*，请先 `uv run synapse hotpot`")
    return runs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=os.path.join("docs", "figs", "hotpot_items.png"))
    args = ap.parse_args()
    run_dir = args.run or _latest()
    d = json.load(open(os.path.join(run_dir, "result.json"), encoding="utf-8"))
    cfg, res = d["config"], d["result"]
    tf1 = res["text_f1_per_item"]
    sf1 = res["synapse_f1_per_item"]
    levels = res.get("levels", ["?"] * len(tf1))
    imp = res["improvement"]
    gold = res["gold_recall"]
    # 长度对齐防护：取三者最小值，避免任一较短时 IndexError
    n = min(len(tf1), len(sf1))
    if len(tf1) != len(sf1):
        print(f"[WARN] text_f1({len(tf1)}) 与 synapse_f1({len(sf1)}) 长度不一致，截断到 {n}")
    if n == 0:
        raise SystemExit("text_f1_per_item / synapse_f1_per_item 均为空，无法画图")
    tf1, sf1 = tf1[:n], sf1[:n]
    # 预先算均值（F1 ×100 与百分比同量纲），供左图标题 + 右图柱状共用
    mean_tf1 = float(np.mean(tf1)) * 100 if tf1 else 0.0
    mean_sf1 = float(np.mean(sf1)) * 100 if sf1 else 0.0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 10})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.4, 1]})

    # 左：逐题 F1 散点（text vs synapse），连线 + 着色
    level_colors = {"easy": "#2e8b57", "medium": "#1f5fd0", "hard": "#d0521f"}
    x = np.arange(n)
    for i in range(n):
        lv = levels[i] if i < len(levels) else "?"
        c = level_colors.get(lv, "#888")
        axL.plot([i, i], [tf1[i], sf1[i]], "-", color=c, alpha=0.5, lw=1.5)
    axL.scatter(x, tf1, s=90, color="#d0521f", marker="o", zorder=3, label="text F1")
    axL.scatter(x, sf1, s=90, color="#1f5fd0", marker="s", zorder=3, label="SYNAPSE F1")
    axL.set_xticks(x)
    axL.set_xticklabels([f"Q{i+1}\n{levels[i] if i < len(levels) else '?'}" for i in range(n)], fontsize=9)
    axL.set_ylim(-0.05, 1.1)
    axL.set_ylabel("Answer F1 (vs gold)")
    axL.set_title(f"Per-item F1: text {mean_tf1/100:.3f} → SYNAPSE {mean_sf1/100:.3f}")
    axL.grid(alpha=0.25, axis="y")
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#d0521f", markersize=10, label="text F1"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#1f5fd0", markersize=10, label="SYNAPSE F1"),
    ] + [Line2D([0], [0], color=c, lw=3, label=f"{lv}") for lv, c in level_colors.items()]
    axL.legend(handles=legend_handles, loc="lower right", fontsize=9)

    # 右：总体对比柱（F1 乘 100 与百分比同量纲，避免 0-1 的柱子在 0-105 轴上看不见）
    metrics = ["LLM token\nsaved %", "wire bytes\nsaved %", "gold recall %", "text F1 %", "SYNAPSE F1 %"]
    vals = [
        imp["llm_token_saved_pct"],
        imp["wire_bytes_saved_pct"],
        gold * 100,
        mean_tf1,
        mean_sf1,
    ]
    colors = ["#1f5fd0", "#1f5fd0", "#2e8b57", "#d0521f", "#1f5fd0"]
    bars = axR.bar(metrics, vals, color=colors, width=0.6, edgecolor="white")
    for b, v in zip(bars, vals):
        axR.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}", ha="center", fontweight="bold", fontsize=10)
    axR.set_ylim(0, 105)
    axR.set_ylabel("percent / F1")
    axR.set_title("Overall metrics")
    axR.grid(alpha=0.25, axis="y")
    plt.setp(axR.get_xticklabels(), fontsize=9)

    fig.suptitle(
        f"SYNAPSE on HotpotQA (real API, {cfg['model']}, N={n}, single k={cfg['qa_para_k']}) — "
        f"from {os.path.basename(run_dir)}",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (N={n}, from {run_dir})")


if __name__ == "__main__":
    main()
