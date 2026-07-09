"""画 单跳 vs 两跳检索的前沿对比（验证"改进检索是否把前沿推高"）。

读 runs/hotpot_ksweep_* 按 config.qa_retrieval 分 single/twohop，取各自最新一次：
左：Pareto ΔF1 vs token 节省（两跳点更靠上=同样省幅下质量更好=前沿被推高）。
右：金标召回 vs k（两跳在低 k 召回更高=补回了桥接段）。

  uv run --extra viz python scripts/plot_retrieval_compare.py
输出 docs/figs/hotpot_retrieval_compare.png
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


def _by_mode() -> dict:
    """返回 {mode: rows}，每模式取最新一次 ksweep。"""
    out: dict[str, list] = {}
    latest_dir: dict[str, str] = {}
    for d in sorted(glob.glob(os.path.join("runs", "hotpot_ksweep_*"))):
        if not os.path.isdir(d):
            continue
        data = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))
        mode = data.get("config", {}).get("qa_retrieval", "single")
        out[mode] = data["rows"]
        latest_dir[mode] = d
    return out, latest_dir


def _err(rows):
    lo = [r["delta_mean"] - r["ci95"][0] for r in rows]
    hi = [r["ci95"][1] - r["delta_mean"] for r in rows]
    return [lo, hi]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("docs", "figs", "hotpot_retrieval_compare.png"))
    args = ap.parse_args()
    by_mode, dirs = _by_mode()
    if not by_mode:
        raise SystemExit("未找到 runs/hotpot_ksweep_*")

    style = {
        "single": {"c": "#d0521f", "m": "o", "lbl": "single-hop"},
        "twohop": {"c": "#9aa7b8", "m": "^", "lbl": "two-hop (embed expand)"},
        "bridge": {"c": "#1f5fd0", "m": "s", "lbl": "bridge (lexical entity)"},
    }
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 10})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    axL.axhspan(-0.03, 0.12, color="#2e8b57", alpha=0.08)
    axL.axhline(0, color="#444", lw=1.2)
    axL.axhline(-0.03, color="#888", ls="--", lw=1.2, label="non-inferiority margin")
    for mode, rows in by_mode.items():
        st = style.get(mode, {"c": "#666", "m": "x", "lbl": mode})
        tok = [r["token_saved"] for r in rows]
        dlt = [r["delta_mean"] for r in rows]
        axL.errorbar(
            tok,
            dlt,
            yerr=_err(rows),
            fmt=st["m"],
            color=st["c"],
            ms=8,
            capsize=5,
            lw=1.6,
            label=st["lbl"],
            zorder=3,
        )
        for r in rows:
            axL.annotate(
                f"k={r['k']}",
                (r["token_saved"], r["delta_mean"]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color=st["c"],
            )
    axL.set_xlabel("Real LLM token saved (%)")
    axL.set_ylabel("paired ΔF1 (synapse − text)  [95% CI]")
    axL.set_title("Frontier lift: two-hop points sit higher\n(same saving, smaller quality gap)")
    axL.grid(alpha=0.2)
    axL.legend(loc="lower left")

    for mode, rows in by_mode.items():
        st = style.get(mode, {"c": "#666", "m": "x", "lbl": mode})
        ks = [r["k"] for r in rows]
        rec = [r["gold_recall"] * 100 for r in rows]
        axR.plot(ks, rec, "-" + st["m"], color=st["c"], lw=2, ms=8, label=st["lbl"])
        for r in rows:
            axR.annotate(
                f"{r['gold_recall']:.2f}",
                (r["k"], r["gold_recall"] * 100),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=8,
                color=st["c"],
            )
    axR.set_xlabel("retrieval depth k (paras kept of 10)")
    axR.set_ylabel("gold paragraph recall (%)")
    axR.set_ylim(60, 100)
    axR.set_title("Two-hop recovers the bridge paragraph\n(higher recall at low k)")
    axR.grid(alpha=0.2)
    axR.legend(loc="lower right")

    modes = "+".join(sorted(by_mode))
    fig.suptitle(f"SYNAPSE on HotpotQA — retrieval improvement ({modes}, N=50)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (modes: {dict((m, dirs[m]) for m in by_mode)})")


if __name__ == "__main__":
    main()
