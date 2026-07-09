"""画 HotpotQA 统计稳健化图（N 题 × R 次重复 + 配对置信区间）：

左：token 节省跨重复的稳定性（R 个点 + mean±std 带）+ text/synapse F1 mean±std（误差棒）。
右：同题配对 ΔF1(synapse−text) 的均值 + 自助 95% CI 森林图，标 0 线与 −0.03 非劣边界 + 胜/平/负。

  uv run --extra viz python scripts/plot_hotpot_stats.py
输出 docs/figs/hotpot_stats.png
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _latest() -> str:
    runs = sorted(d for d in glob.glob(os.path.join("runs", "hotpot_stats_*")) if os.path.isdir(d))
    if not runs:
        raise SystemExit("未找到 runs/hotpot_stats_*，请先 `uv run synapse hotpot-stats`")
    return runs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=os.path.join("docs", "figs", "hotpot_stats.png"))
    args = ap.parse_args()
    run_dir = args.run or _latest()
    d = json.load(open(os.path.join(run_dir, "result.json"), encoding="utf-8"))
    cfg, res = d["config"], d["result"]
    runs = res["runs"]
    ts, tf, sf = res["token_saved"], res["text_f1"], res["syn_f1"]
    pd = res["paired_delta_f1"]

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 9})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))

    # 左：token 节省稳定性 + F1 误差棒
    tok = [r["token_saved"] for r in runs]
    axL.axhspan(ts["mean"] - ts["std"], ts["mean"] + ts["std"], color="#1f5fd0", alpha=0.12)
    axL.axhline(ts["mean"], color="#1f5fd0", lw=2, label=f"token saved {ts['mean']:.1f}±{ts['std']:.1f}%")
    axL.scatter(range(1, len(tok) + 1), tok, color="#1f5fd0", s=60, zorder=3)
    axL.set_xlabel("repeat run")
    axL.set_ylabel("Real LLM token saved (%)", color="#1f5fd0")
    axL.tick_params(axis="y", labelcolor="#1f5fd0")
    axL.set_xticks(range(1, len(tok) + 1))
    axL.set_ylim(0, 100)
    axL.set_title(f"Token saving stable across {res['repeats']} runs\n(N={res['n_items']} questions)")
    axL.grid(alpha=0.2)

    ax2 = axL.twinx()
    ax2.errorbar(
        [0.6, len(tok) + 0.4],
        [tf["mean"], sf["mean"]],
        yerr=[tf["std"], sf["std"]],
        fmt="s",
        color="#d0521f",
        ms=9,
        capsize=6,
        lw=2,
    )
    for xi, m, lab in ((0.6, tf["mean"], "text"), (len(tok) + 0.4, sf["mean"], "SYNAPSE")):
        ax2.annotate(
            f"{lab}\nF1 {m:.3f}",
            (xi, m),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=9,
            color="#d0521f",
        )
    ax2.set_ylabel("Answer F1 (mean±std)", color="#d0521f")
    ax2.tick_params(axis="y", labelcolor="#d0521f")
    ax2.set_ylim(0, 1)

    # 右：配对 ΔF1 森林图（非劣）
    lo, hi = pd["ci95"]
    color = "#2e8b57" if lo >= -0.03 else "#d0521f"
    axR.errorbar(
        [pd["mean"]],
        [1],
        xerr=[[pd["mean"] - lo], [hi - pd["mean"]]],
        fmt="o",
        color=color,
        ms=12,
        capsize=10,
        lw=2.5,
        zorder=3,
    )
    axR.axvline(0, color="#444", lw=1.4, label="no effect (Δ=0)")
    axR.axvline(-0.03, color="#d0521f", ls="--", lw=1.4, label="non-inferiority margin (−0.03)")
    axR.set_yticks([1])
    axR.set_yticklabels(["paired ΔF1\n(synapse − text)"])
    axR.set_ylim(0.5, 1.6)
    span = max(0.08, hi - lo)
    axR.set_xlim(min(-0.05, lo - span), max(0.05, hi + span))
    axR.set_xlabel("ΔF1 per question (paired)")
    verdict = "NON-INFERIOR ✓" if lo >= -0.03 else "inconclusive"
    axR.set_title(f"Quality non-inferiority: {verdict}")
    axR.annotate(
        f"Δ={pd['mean']:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]\n"
        f"win/tie/loss = {pd['syn_win']}/{pd['tie']}/{pd['syn_loss']}  (n={pd['n_pairs']} pairs)",
        (0.5, 0.18),
        xycoords="axes fraction",
        ha="center",
        fontsize=10,
        bbox=dict(boxstyle="round", fc="#f3f6fb", ec="#ccd"),
    )
    axR.legend(loc="upper left", fontsize=9)
    axR.grid(alpha=0.2, axis="x")

    fig.suptitle(
        f"SYNAPSE on HotpotQA distractor — statistical robustness "
        f"({cfg['model']}, N={res['n_items']}×R={res['repeats']}, k={res['para_k']}): "
        f"token −{ts['mean']:.0f}%±{ts['std']:.1f}, F1 {tf['mean']:.3f}→{sf['mean']:.3f}",
        fontsize=11.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (from {run_dir})")


if __name__ == "__main__":
    main()
