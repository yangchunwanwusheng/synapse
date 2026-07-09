"""HotpotQA 规模化 k-前沿：找诚实操作点（token 节省 vs F1 非劣）。

单进程、共享 embedder（嵌入只付一次）、text 基线只跑一次并复用于所有 k 的同题配对 Δ。
回答：扩样本后，是否存在某个 k 使 synapse 既显著省 token 又 F1 非劣？省幅多少？
  uv run python scripts/sweep_hotpot_k.py --n 50 --ks 3 4 5 6 8
输出 runs/hotpot_ksweep_<ts>/result.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime

from synapse.cli import _load_dotenv
from synapse.config import load_config
from synapse.eval.metrics import improvement
from synapse.qa.dataset import load_hotpot
from synapse.qa.pipeline import run_synapse_hotpot, run_text_hotpot
from synapse.qa.stats import bootstrap_ci, mean_std, paired_winloss
from synapse.stateplane.embedding import make_embedder


def main() -> None:
    try:  # Windows 控制台/重定向默认 GBK，无法编码 − Δ 等；强制 UTF-8 防崩
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--ks", type=int, nargs="+", default=[3, 4, 5, 6, 8])
    ap.add_argument("--retrieval", default="single", choices=["single", "twohop", "bridge"])
    ap.add_argument(
        "--data", default="data/hotpot_sample.json", help="数据文件（hotpot 或 musique，同 schema）"
    )
    args = ap.parse_args()

    _load_dotenv()
    cfg = replace(load_config(None), llm_backend="paratera", embedder="api", qa_retrieval=args.retrieval)
    if not cfg.api_key():
        raise SystemExit(f"[ERR] {cfg.api_key_env} 未设置（.env）")

    dataset = os.path.splitext(os.path.basename(args.data))[0].replace("_sample", "")
    items = load_hotpot(args.data, args.n)
    embedder = make_embedder(cfg)  # 共享：段落嵌入只付一次
    print(
        f"== k-sweep: data={dataset} N={len(items)} ks={args.ks} retrieval={cfg.qa_retrieval} model={cfg.model} =="
    )

    out_dir = os.path.join("runs", f"{dataset}_ksweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "result.json")

    rt = run_text_hotpot(items, cfg)  # 基线只跑一次（与 k 无关）
    text_f1, tm = rt["f1_per_turn"], rt["metrics"]
    print(f"text baseline: F1={tm.quality} tokens={tm.llm_total_tokens}")

    rows = []
    for k in args.ks:
        rs = run_synapse_hotpot(items, replace(cfg, qa_para_k=k), embedder=embedder)
        sm = rs["metrics"]
        deltas = [s - t for t, s in zip(text_f1, rs["f1_per_turn"])]
        ci = bootstrap_ci(deltas)
        wl = paired_winloss(text_f1, rs["f1_per_turn"])
        rows.append(
            {
                "k": k,
                "token_saved": improvement(tm, sm)["llm_token_saved_pct"],
                "syn_f1": sm.quality,
                "gold_recall": rs["gold_recall"],
                "delta_mean": mean_std(deltas)["mean"],
                "ci95": ci,
                "noninferior": ci[0] >= -0.03,
                **wl,
            }
        )
        # 每个 k 后立即落盘（任何后续异常都不会丢已算结果）
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "config": cfg.to_dict(),
                    "dataset": dataset,
                    "n_items": len(items),
                    "text_f1": tm.quality,
                    "rows": rows,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        r = rows[-1]
        verdict = "NON-INFERIOR" if r["noninferior"] else "WORSE"
        print(
            f"  k={k}: token -{r['token_saved']:.1f}% | gold_recall {r['gold_recall']} | "
            f"synF1 {sm.quality} | dF1 {r['delta_mean']:+.3f} CI{ci} | {verdict} | "
            f"w/t/l {wl['syn_win']}/{wl['tie']}/{wl['syn_loss']}"
        )
    print(f"  artifacts -> {out_path}")


if __name__ == "__main__":
    main()
