"""画 CoQA 实验图（真实数据集，真实 token）：累计 token vs 轮次（基线增长 vs SYNAPSE 平稳）+ F1 对比。

  uv run --extra viz python scripts/plot_coqa.py [--run runs/coqa_YYYYmmdd_HHMMSS]
输出 docs/figs/coqa_tokens.png
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
    runs = sorted(d for d in glob.glob(os.path.join("runs", "coqa_*")) if os.path.isdir(d))
    if not runs:
        raise SystemExit("未找到 runs/coqa_*，请先 `uv run synapse coqa`")
    return runs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default=os.path.join("docs", "figs", "coqa_tokens.png"))
    args = ap.parse_args()
    run_dir = args.run or _latest()
    d = json.load(open(os.path.join(run_dir, "result.json"), encoding="utf-8"))
    cfg, res = d["config"], d["result"]
    per = res["per_conversation"]
    tt, st, imp = res["text_total"], res["synapse_total"], res["improvement"]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 13, "legend.fontsize": 10})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))

    # 左：累计 token vs 轮次（每段对话两条线）
    for i, c in enumerate(per):
        tx, sy = c.get("text_cum_tokens", []), c.get("synapse_cum_tokens", [])
        lbl_t = "text baseline" if i == 0 else None
        lbl_s = "SYNAPSE" if i == 0 else None
        axL.plot(range(1, len(tx) + 1), tx, "-o", color="#d0521f", lw=1.8, ms=4, alpha=0.85, label=lbl_t)
        axL.plot(range(1, len(sy) + 1), sy, "-s", color="#1f5fd0", lw=1.8, ms=4, alpha=0.85, label=lbl_s)
    axL.set_xlabel("Conversation turn")
    axL.set_ylabel("Cumulative LLM tokens (input+output)")
    axL.set_title("Token cost grows with dialogue —\nbaseline re-pastes story+history, SYNAPSE doesn't")
    axL.grid(alpha=0.25)
    axL.legend(loc="upper left")

    # 右：F1 对比（每段 + 总体）+ token 节省标注
    labels = [c["conv_id"].replace("coqa-", "c") for c in per] + ["ALL"]
    tf = [c["text"]["quality"] for c in per] + [tt["quality"]]
    sf = [c["synapse"]["quality"] for c in per] + [st["quality"]]
    x = range(len(labels))
    axR.bar([i - 0.2 for i in x], tf, 0.4, color="#d0521f", label="text F1")
    axR.bar([i + 0.2 for i in x], sf, 0.4, color="#1f5fd0", label="SYNAPSE F1")
    axR.set_xticks(list(x))
    axR.set_xticklabels(labels)
    axR.set_ylim(0, 1)
    axR.set_ylabel("Answer F1 (vs gold)")
    axR.set_title("Answer quality maintained")
    axR.grid(alpha=0.25, axis="y")
    axR.legend(loc="lower right")

    fig.suptitle(
        f"SYNAPSE on CoQA (real dataset, {cfg['model']}, {cfg['embedder']} embedder) — "
        f"LLM tokens −{imp['llm_token_saved_pct']}% (input −{imp['llm_input_saved_pct']}%), "
        f"F1 {tt['quality']:.2f}→{st['quality']:.2f}",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (from {run_dir})")


if __name__ == "__main__":
    main()
