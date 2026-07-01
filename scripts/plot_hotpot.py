"""画 HotpotQA 实验图（真实数据集，真实 token）：

左：regime 对比——为何 CoQA 只省 8% 而 HotpotQA 省 75%（可压缩上下文比例不同 = 根因可视化）。
右：HotpotQA 省幅 vs 检索深度 k 的权衡曲线（token 省 / 金标召回 / F1），含 text 基线噪声带。

  uv run --extra viz python scripts/plot_hotpot.py
输出 docs/figs/hotpot_tradeoff.png
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _latest(prefix: str) -> str | None:
    runs = sorted(d for d in glob.glob(os.path.join("runs", f"{prefix}_*")) if os.path.isdir(d))
    return runs[-1] if runs else None


def _load_hotpot_runs() -> list[dict]:
    rows = []
    for d in sorted(glob.glob(os.path.join("runs", "hotpot_*"))):
        if not os.path.isdir(d):
            continue
        r = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))["result"]
        rows.append(
            {
                "k": r["para_k"],
                "token_saved": r["improvement"]["llm_token_saved_pct"],
                "gold_recall": r["gold_recall"] * 100,
                "text_f1": r["text"]["quality"],
                "syn_f1": r["synapse"]["quality"],
            }
        )
    # 同 k 取最后一次；按 k 排序
    by_k = {row["k"]: row for row in rows}
    return [by_k[k] for k in sorted(by_k)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("docs", "figs", "hotpot_tradeoff.png"))
    args = ap.parse_args()

    rows = _load_hotpot_runs()
    if not rows:
        raise SystemExit("未找到 runs/hotpot_*，请先 `uv run synapse hotpot`")
    ks = [r["k"] for r in rows]
    tok = [r["token_saved"] for r in rows]
    rec = [r["gold_recall"] for r in rows]
    tf = [r["text_f1"] for r in rows]
    sf = [r["syn_f1"] for r in rows]
    f1_lo, f1_hi = min(tf), max(tf)  # text 基线在多次同配置运行间的噪声带（temp=0 MoE 仍非确定）

    # CoQA 对照点（根因：可压缩上下文比例小 → 省幅天花板低）
    coqa_saved = None
    cd = _latest("coqa")
    if cd:
        coqa_saved = json.load(open(os.path.join(cd, "result.json"), encoding="utf-8"))["result"][
            "improvement"
        ]["llm_token_saved_pct"]

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12.5, "legend.fontsize": 10})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))

    # 左：regime 对比
    names, vals, cols = [], [], []
    if coqa_saved is not None:
        names.append("CoQA\n(short dense story\n~19% compressible)")
        vals.append(coqa_saved)
        cols.append("#9aa7b8")
    hp = next((r for r in rows if r["k"] == 3), rows[len(rows) // 2])
    names.append("HotpotQA\n(10 paras, ~80%\ndistractors)")
    vals.append(hp["token_saved"])
    cols.append("#1f5fd0")
    bars = axL.bar(names, vals, color=cols, width=0.55)
    for b, v in zip(bars, vals):
        axL.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}%", ha="center", fontweight="bold")
    axL.set_ylabel("Real LLM token saved (%)")
    axL.set_ylim(0, 100)
    axL.set_title("Saving ∝ compressible-context fraction\n(why regime decides the ceiling)")
    axL.grid(alpha=0.25, axis="y")

    # 右：k 权衡曲线
    axR.plot(ks, tok, "-o", color="#1f5fd0", lw=2, ms=7, label="token saved %")
    axR.plot(ks, rec, "-^", color="#2e8b57", lw=2, ms=7, label="gold recall %")
    axR.set_xlabel("retrieval depth k (paras kept of 10)")
    axR.set_ylabel("percent")
    axR.set_xticks(ks)
    axR.set_ylim(40, 100)
    axR.grid(alpha=0.25)

    ax2 = axR.twinx()
    ax2.axhspan(f1_lo, f1_hi, color="#d0521f", alpha=0.12)
    ax2.plot(ks, sf, "-s", color="#d0521f", lw=2, ms=7, label="SYNAPSE F1")
    ax2.axhline(sum(tf) / len(tf), ls="--", color="#888", lw=1.2, label="text F1 (mean±noise)")
    ax2.set_ylabel("Answer F1", color="#d0521f")
    ax2.set_ylim(0, 1)
    ax2.tick_params(axis="y", labelcolor="#d0521f")

    lines = axR.get_lines() + ax2.get_lines()
    axR.legend(lines, [ln.get_label() for ln in lines], loc="center left", fontsize=9)
    axR.set_title("Token saving vs retrieval depth\n(F1 held within text-baseline noise for k≥3)")

    fig.suptitle(
        f"SYNAPSE on HotpotQA distractor (real dataset, k={hp['k']}: "
        f"token −{hp['token_saved']:.0f}%, F1 {hp['text_f1']:.2f}→{hp['syn_f1']:.2f}, "
        f"gold recall {hp['gold_recall']:.0f}%)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"saved -> {args.out}  (hotpot runs: k={ks})")


if __name__ == "__main__":
    main()
