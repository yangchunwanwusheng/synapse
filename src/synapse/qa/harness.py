"""CoQA A/B 评测台：同一批对话分别跑 text 基线与 synapse，聚合真实 token / F1 / 命中率。"""

from __future__ import annotations

from ..eval.metrics import Metrics, improvement
from ..stateplane.embedding import make_embedder
from .dataset import load_conversations, load_hotpot
from .pipeline import run_synapse, run_synapse_hotpot, run_text, run_text_hotpot
from .stats import bootstrap_ci, mean_std, paired_winloss


def _agg(traj: list[Metrics]) -> Metrics:
    agg = Metrics(mode=traj[0].mode if traj else "")
    for m in traj:
        agg.messages += m.messages
        agg.text_bytes += m.text_bytes
        agg.text_tokens += m.text_tokens
        agg.header_bytes += m.header_bytes
        agg.nontext_transfers += m.nontext_transfers
        agg.nontext_bytes += m.nontext_bytes
        agg.memory_queries += m.memory_queries
        agg.memory_hits += m.memory_hits
        agg.llm_input_tokens += m.llm_input_tokens
        agg.llm_output_tokens += m.llm_output_tokens
        agg.latency_s += m.latency_s
        agg.quality += m.quality
    if traj:
        agg.quality = round(agg.quality / len(traj), 4)
    return agg


def run_coqa(cfg, n_conv: int = 2, path: str = "data/coqa_sample.json") -> dict:
    convs = load_conversations(path, n_conv)
    text_traj, syn_traj, per = [], [], []
    for c in convs:
        rt = run_text(c, cfg)
        rs = run_synapse(c, cfg)
        text_traj.append(rt["metrics"])
        syn_traj.append(rs["metrics"])
        per.append(
            {
                "conv_id": c.conv_id,
                "source": c.source,
                "turns": len(c.turns),
                "text": rt["metrics"].summary(),
                "synapse": rs["metrics"].summary(),
                "text_f1_per_turn": rt["f1_per_turn"],
                "synapse_f1_per_turn": rs["f1_per_turn"],
                "text_cum_tokens": rt.get("cum_tokens", []),
                "synapse_cum_tokens": rs.get("cum_tokens", []),
            }
        )
    tt, st = _agg(text_traj), _agg(syn_traj)
    return {
        "n_conversations": len(convs),
        "per_conversation": per,
        "text_total": tt.summary(),
        "synapse_total": st.summary(),
        "improvement": improvement(tt, st),
    }


def run_hotpot(cfg, n_items: int = 10, path: str = "data/hotpot_sample.json") -> dict:
    """HotpotQA distractor A/B：基线塞全 10 段 vs synapse 只检索相关段（丢干扰）。"""
    items = load_hotpot(path, n_items)
    rt = run_text_hotpot(items, cfg)
    rs = run_synapse_hotpot(items, cfg)
    tm, sm = rt["metrics"], rs["metrics"]
    return {
        "n_items": len(items),
        "para_k": cfg.qa_para_k,
        "text": tm.summary(),
        "synapse": sm.summary(),
        "text_f1_per_item": rt["f1_per_turn"],
        "synapse_f1_per_item": rs["f1_per_turn"],
        "gold_recall": rs.get("gold_recall", 0.0),
        "levels": [it.level for it in items],
        "improvement": improvement(tm, sm),
    }


def run_hotpot_stats(cfg, n_items: int = 50, repeats: int = 3, path: str = "data/hotpot_sample.json") -> dict:
    """统计稳健化：N 题 × R 次重复（捕捉 temp=0 MoE 非确定）。

    输出 run 级 mean±std（token 省 / F1 / 召回）+ 同题配对 Δ(synapse−text) 的自助 95% CI 与胜负，
    给出"省 token 不伤质量"的可辩护非劣结论。embedder 跨重复共享缓存（仅首次付嵌入调用）。
    """
    items = load_hotpot(path, n_items)
    embedder = make_embedder(cfg)  # 共享缓存：repeats>1 时嵌入只调一次
    runs, pooled_t, pooled_s = [], [], []
    for _ in range(repeats):
        rt = run_text_hotpot(items, cfg)
        rs = run_synapse_hotpot(items, cfg, embedder=embedder)
        tm, sm = rt["metrics"], rs["metrics"]
        runs.append(
            {
                "token_saved": improvement(tm, sm)["llm_token_saved_pct"],
                "text_f1": tm.quality,
                "syn_f1": sm.quality,
                "gold_recall": rs.get("gold_recall", 0.0),
                "text_tokens": tm.llm_total_tokens,
                "syn_tokens": sm.llm_total_tokens,
            }
        )
        pooled_t += rt["f1_per_turn"]
        pooled_s += rs["f1_per_turn"]
    deltas = [s - t for t, s in zip(pooled_t, pooled_s)]
    levels = [it.level for it in items]
    return {
        "n_items": len(items),
        "repeats": repeats,
        "para_k": cfg.qa_para_k,
        "level_counts": {lv: levels.count(lv) for lv in sorted(set(levels))},
        "runs": runs,
        "token_saved": mean_std([r["token_saved"] for r in runs]),
        "text_f1": mean_std([r["text_f1"] for r in runs]),
        "syn_f1": mean_std([r["syn_f1"] for r in runs]),
        "gold_recall": mean_std([r["gold_recall"] for r in runs]),
        "paired_delta_f1": {
            "mean": mean_std(deltas)["mean"],
            "ci95": bootstrap_ci(deltas),
            **paired_winloss(pooled_t, pooled_s),
            "n_pairs": len(deltas),
        },
    }
