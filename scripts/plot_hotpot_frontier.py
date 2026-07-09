"""画 HotpotQA 规模化 k-前沿图（诚实 Pareto：token 节省 vs 质量）。

左：ΔF1(synapse−text) vs token 节省的 Pareto，每点标 k、配 95% CI 竖须，0 线 + −0.03 非劣边界 + 非劣带。
右：随 k 变化——token 节省% 与金标召回%（左轴）+ ΔF1 及 CI（右轴）；展示"召回↑→ΔF1→0 但省幅↓"机制。

  uv run --extra viz python scripts/plot_hotpot_frontier.py
输出 docs/figs/hotpot_frontier.png
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _latest() -> str:
    runs = sorted(d for d in glob.glob(os.path.join("runs", "hotpot_ksweep_*")) if os.path.isdir(d))
    if not runs:
        raise SystemExit("未找到 runs/hotpot_ksweep_*，请先 `uv run python scripts/sweep_hotpot_k.py`")
    return runs[-1]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=os.path.join("docs", "figs", "hotpot_frontier.png"))
    args = ap.parse_args()
    run_dir = args.run or _latest()
    d = json.load(open(os.path.join(run_dir, "result.json"), encoding="utf-8"))
    rows, text_f1 = d["rows"], d["text_f1"]
    ks = [r["k"] for r in rows]
    tok = [r["token_saved"] for r in rows]
    rec = [r["gold_recall"] * 100 for r in rows]
    dlt = [r["delta_mean"] for r in rows]
    lo = [r["delta_mean"] - r["ci95"][0] for r in rows]
    hi = [r["ci95"][1] - r["delta_mean"] for r in rows]
    MARGIN = -0.03

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 9})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    # 左：Pareto ΔF1 vs token saved
    axL.axhspan(MARGIN, 0.12, color="#2e8b57", alpha=0.08)
    axL.axhline(0, color="#444", lw=1.3)
    axL.axhline(MARGIN, color="#d0521f", ls="--", lw=1.3, label="non-inferiority margin (−0.03)")
    axL.errorbar(tok, dlt, yerr=[lo, hi], fmt="o", color="#1f5fd0", ms=9, capsize=6, lw=1.8, zorder=3)
    for r in rows:
        axL.annotate(
            f"k={r['k']}\nrecall {r['gold_recall']:.2f}",
            (r["token_saved"], r["delta_mean"]),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
        )
    axL.set_xlabel("Real LLM token saved (%)")
    axL.set_ylabel("paired ΔF1 (synapse − text)  [95% CI]")
    axL.set_title("Honest Pareto frontier at N=50\n(save more → quality gap grows)")
    axL.grid(alpha=0.2)
    axL.legend(loc="lower left")

    # 右：随 k——省幅/召回（左轴） + ΔF1 CI（右轴）
    axR.plot(ks, tok, "-o", color="#1f5fd0", lw=2, ms=7, label="token saved %")
    axR.plot(ks, rec, "-^", color="#2e8b57", lw=2, ms=7, label="gold recall %")
    axR.set_xlabel("retrieval depth k (paras kept of 10)")
    axR.set_ylabel("percent")
    axR.set_xticks(ks)
    axR.set_ylim(0, 100)
    axR.grid(alpha=0.2)

    ax2 = axR.twinx()
    ax2.axhspan(MARGIN, 0.1, color="#2e8b57", alpha=0.07)
    ax2.axhline(0, color="#444", lw=1.0)
    ax2.errorbar(
        ks, dlt, yerr=[lo, hi], fmt="s", color="#d0521f", ms=7, capsize=5, lw=1.6, label="ΔF1 (95% CI)"
    )
    ax2.set_ylabel("paired ΔF1", color="#d0521f")
    ax2.tick_params(axis="y", labelcolor="#d0521f")
    ax2.set_ylim(-0.28, 0.12)

    h1, l1 = axR.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    axR.legend(h1 + h2, l1 + l2, loc="center right", fontsize=9)
    axR.set_title("Recall↑ with k → ΔF1→0,\nbut token saving↓ (k=6 = best balance)")

    fig.suptitle(
        f"SYNAPSE on HotpotQA distractor — honest scaled frontier (N={d['n_items']}, text F1={text_f1:.3f}):\n"
        f"k=6 saves ~47% at ΔF1 −0.04 (CI incl. 0);  k=3's 75% costs −0.12 F1 (significant)",
        fontsize=11.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (from {run_dir})")


if __name__ == "__main__":
    main()
