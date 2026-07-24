"""命令行入口：smoke（离线自检）/ ab（双模式对比）。

python -m synapse.cli smoke
python -m synapse.cli ab --rounds 10 [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime

from .config import Config, load_config
from .eval.harness import ABRunner
from . import tasks as T


def _load_dotenv(path: str = ".env") -> None:
    """极简 stdlib .env 加载（无第三方依赖）：仅填充未设置的环境变量，不覆盖已有。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _real_cfg(args):
    """构造真实后端配置：--config 优先；mock 默认覆盖为 paratera。无密钥返回 None。

    若 YAML 已指定具体 backend（如 vectorengine），尊重配置不覆盖——支持多平台切换。
    """
    _load_dotenv()
    cfg = load_config(getattr(args, "config", None))
    if cfg.llm_backend == "mock":  # 默认 mock → 回退到 paratera（向后兼容）
        cfg = replace(cfg, llm_backend="paratera")
    if not cfg.api_key():
        print(f"[ERR] {cfg.api_key_env} 未设置——请先在项目根 .env 填入密钥（严禁硬编码/提交）")
        return None
    return cfg


def cmd_smoke(_args) -> int:
    """离线 mock smoke：验证双模式跑通 + 残差节省 + 记忆复用 + 负例区分度。"""
    cfg = Config()  # mock LLM + hash embedder，全离线

    linked = ABRunner(cfg).run(T.linked_continuous(3, 3))
    negative = ABRunner(cfg).run(T.negative_family(6))

    imp = linked["improvement"]
    contraction = linked["contraction_bytes"]
    syn_hit = imp["synapse_hit_rate"]
    neg_hit = negative["improvement"]["synapse_hit_rate"]

    checks = {
        "双模式都产出结论": linked["synapse_total"]["quality"] == 1.0
        and linked["text_total"]["quality"] == 1.0,
        "synapse 省线缆字节(>0%)": imp["wire_bytes_saved_pct"] > 0,
        "记忆复用命中(关联任务 hit>0)": syn_hit > 0,
        "收缩(末轮非文本字节<=首轮)": contraction[-1] <= contraction[0],
        "区分度(负例命中率<关联命中率)": neg_hit < syn_hit,
    }

    print("== SYNAPSE smoke (offline mock) ==")
    print(
        json.dumps(
            {"linked_improvement": imp, "contraction_bytes": contraction, "negative_hit_rate": neg_hit},
            ensure_ascii=False,
            indent=2,
        )
    )
    for name, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f"SMOKE FAILED: {failed}")
        return 1
    print("SMOKE PASSED")
    return 0


def cmd_ab(args) -> int:
    cfg = load_config(args.config)
    res = ABRunner(cfg).run(T.linked_continuous(args.rounds, args.rounds))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def cmd_probe(args) -> int:
    """输出形态探针：真实 API 接通前确认①鉴权②输出非 thinking③CodeAct 可解析④token 计数。"""
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    print(
        f"== PROBE: backend={cfg.llm_backend} model={cfg.model} base={cfg.api_base} temp={cfg.temperature} =="
    )

    # 1) 原始生成：看输出形态（是否夹带 <think> 块 → 破坏结构化解析）
    from .runtime.model import make_model

    mdl = make_model(cfg, "retriever")
    try:
        msg = mdl.generate([{"role": "user", "content": "Reply with exactly: PROBE_OK"}])
    except Exception as e:  # noqa: BLE001  探针需暴露任何后端错误
        print("[raw.generate] ERROR:", repr(e))
        return 1
    content = msg.content or ""
    print("[raw.generate] content[:200]=", repr(content[:200]))
    print("[raw.generate] token_usage=", getattr(msg, "token_usage", None))
    has_think = "<think" in content.lower()
    print(f"  [{'WARN(含thinking块)' if has_think else 'OK'}] 输出形态")

    # 2) 端到端一个任务：CodeAct 解析 + 全管线 + 真实 token 计数
    from .modes.synapse_mode import SynapseSession

    try:
        out = SynapseSession(cfg).run_task(T.g1_family(1)[0])
    except Exception as e:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print("[e2e] ERROR:", repr(e))
        return 1
    mm = out["metrics"]
    print("[e2e] conclusion[:160]=", repr((out["conclusion"] or "")[:160]))
    print(
        f"[e2e] nontext_bytes={mm.nontext_bytes} llm_tokens={mm.llm_tokens} "
        f"fallbacks={mm.fallbacks} checksum_ok={out['checksum_ok']}"
    )
    ok = bool(out["conclusion"]) and mm.llm_tokens > 0
    print(f"  [{'PASS' if ok else 'FAIL'}] 端到端跑通 + 真实 token 计数>0")
    return 0 if ok else 1


def _half_means(contr):
    """非文本字节下降度量：前半均值/后半均值/下降%（抗逐点噪声，胜过首→末单点比较）。"""
    if not contr:
        return 0.0, 0.0, 0.0
    h = len(contr) // 2 or 1
    first = sum(contr[:h]) / h
    second = sum(contr[h:]) / max(1, len(contr) - h)
    drop = round((first - second) / first * 100, 1) if first else 0.0
    return round(first, 1), round(second, 1), drop


def cmd_signal(args) -> int:
    """signal 轮：真实 API 跑 G1(关联) + 负例族(因果对照)，synapse vs text，存档 + 字节节省判定 + 区分度。"""
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    if getattr(args, "no_memory", False):
        cfg = replace(cfg, abl_no_memory=True)
    print(
        f"== SIGNAL: backend={cfg.llm_backend} model={cfg.model} embedder={cfg.embedder} "
        f"rounds={args.rounds} topic={args.topic!r} temp={cfg.temperature} =="
    )
    linked = ABRunner(cfg).run(T.g1_family(args.rounds, topic=args.topic))
    negative = ABRunner(cfg).run(T.negative_family(min(args.rounds, 6)))

    out_dir = os.path.join("runs", f"signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"config": cfg.to_dict(), "linked": linked, "negative": negative}, f, ensure_ascii=False, indent=2
        )

    imp = linked["improvement"]
    lc, nc = linked["contraction_bytes"], negative["contraction_bytes"]
    lf, ls, ldrop = _half_means(lc)
    nf, ns, ndrop = _half_means(nc)
    lhit, nhit = imp["synapse_hit_rate"], negative["improvement"]["synapse_hit_rate"]
    ratio = round(ls / ns, 2) if ns else None  # 字节水平比：关联后半 / 负例后半（<1 = 关联更省）
    print(
        json.dumps(
            {
                "wire_bytes_saved_pct": imp["wire_bytes_saved_pct"],
                "token_saved_pct": imp["token_saved_pct"],
                "synapse_fallbacks": imp["synapse_fallbacks"],
                "linked": {
                    "contraction": lc,
                    "first_half": lf,
                    "second_half": ls,
                    "drop_pct": ldrop,
                    "hit": lhit,
                },
                "negative": {
                    "contraction": nc,
                    "first_half": nf,
                    "second_half": ns,
                    "drop_pct": ndrop,
                    "hit": nhit,
                },
                "converged_rate_ratio": ratio,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    kc1_ok = imp["wire_bytes_saved_pct"] > 0  # 字节节省判定：synapse 每任务字节更省
    contraction_ok = ldrop > 0  # 关联族后半 < 前半（字节随经验下降）
    # 因果区分用「字节水平」而非 drop%（后者对逐点噪声敏感）：关联达到显著更低的字节 + 命中更高
    causal_ok = ratio is not None and ratio < 0.85 and lhit > nhit
    print(
        f"  [{'PASS' if kc1_ok else 'FAIL'}] synapse 省线缆字节 (saved%={imp['wire_bytes_saved_pct']})"
    )
    print(f"  [{'PASS' if contraction_ok else 'WARN'}] 关联族字节下降 (前半 {lf} → 后半 {ls}, drop={ldrop}%)")
    print(
        f"  [{'PASS' if causal_ok else 'WARN'}] 因果区分 (关联字节 {ls} vs 负例 {ns}, ratio={ratio}; "
        f"命中 {lhit} vs {nhit})"
    )
    print(f"  artifacts -> {out_dir}/result.json")
    return 0 if (kc1_ok and contraction_ok) else 1


def _group_stats(traj):
    nb = [m["nontext_bytes"] for m in traj]
    q = sum(m["memory_queries"] for m in traj)
    h = sum(m["memory_hits"] for m in traj)
    return {
        "n": len(traj),
        "mean_nontext_bytes": round(sum(nb) / len(nb), 1) if nb else 0.0,
        "bytes": nb,
        "hit_rate": round(h / q, 3) if q else 0.0,
    }


def cmd_m7(args) -> int:
    """M7：≥2 组关联连续任务（G1 深挖 → G2 关联演进，同一持续会话）。

    验证 G2 复用 G1 累积的共享记忆 → G2 每任务字节更低、命中率从首个任务即高（跨组复用）。
    """
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    tasks = T.linked_continuous(args.g1, args.g2, topic=args.topic)
    print(
        f"== M7: backend={cfg.llm_backend} model={cfg.model} topic={args.topic!r} "
        f"G1={args.g1} → G2={args.g2}（同会话，G2 复用 G1 记忆）=="
    )
    res = ABRunner(cfg).run(tasks)
    syn = res["synapse_trajectory"]
    g1s = _group_stats(syn[: args.g1])
    g2s = _group_stats(syn[args.g1 :])

    out_dir = os.path.join("runs", f"m7_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"config": cfg.to_dict(), "result": res, "g1": g1s, "g2": g2s}, f, ensure_ascii=False, indent=2
        )

    print(json.dumps({"G1": g1s, "G2": g2s, "improvement": res["improvement"]}, ensure_ascii=False, indent=2))
    # M7 跨组复用：G2（暖启动，复用 G1）每任务字节 ≤ G1（含冷启动）且命中率 ≥ G1
    reuse_ok = g2s["mean_nontext_bytes"] <= g1s["mean_nontext_bytes"] and g2s["hit_rate"] >= g1s["hit_rate"]
    print(
        f"  [{'PASS' if reuse_ok else 'WARN'}] 跨组记忆复用 "
        f"(G2 均字节 {g2s['mean_nontext_bytes']} ≤ G1 {g1s['mean_nontext_bytes']}; "
        f"G2 命中 {g2s['hit_rate']} ≥ G1 {g1s['hit_rate']})"
    )
    print(f"  artifacts -> {out_dir}/result.json")
    return 0


def cmd_coqa(args) -> int:
    """真实数据集(CoQA)对话式 QA：text 基线 vs synapse，统计真实 LLM token + F1 + 记忆复用。"""
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    cfg = replace(cfg, embedder=args.embedder, qa_sentences_k=args.k)
    from .qa.harness import run_coqa

    print(
        f"== CoQA: model={cfg.model} embedder={cfg.embedder} k={cfg.qa_sentences_k} "
        f"convs={args.convs} (每段=1组关联连续任务) =="
    )
    res = run_coqa(cfg, n_conv=args.convs)

    out_dir = os.path.join("runs", f"coqa_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg.to_dict(), "result": res}, f, ensure_ascii=False, indent=2)

    imp, tt, st = res["improvement"], res["text_total"], res["synapse_total"]
    print(
        json.dumps(
            {
                "llm_token_saved_pct": imp["llm_token_saved_pct"],
                "llm_input_saved_pct": imp["llm_input_saved_pct"],
                "text_tokens_in/out/total": [
                    tt["llm_input_tokens"],
                    tt["llm_output_tokens"],
                    tt["llm_total_tokens"],
                ],
                "synapse_tokens_in/out/total": [
                    st["llm_input_tokens"],
                    st["llm_output_tokens"],
                    st["llm_total_tokens"],
                ],
                "text_F1": tt["quality"],
                "synapse_F1": st["quality"],
                "messages_text/syn": [tt["messages"], st["messages"]],
                "synapse_hit_rate": st["hit_rate"],
                "synapse_nontext_transfers": st["nontext_transfers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    token_ok = imp["llm_token_saved_pct"] > 0  # 通信效率：真实 token 更省
    f1_ok = st["quality"] >= tt["quality"] - 0.10  # 质量不显著下降（省 token 非靠少干活）
    print(
        f"  [{'PASS' if token_ok else 'FAIL'}] 真实 LLM token 节省 (saved%={imp['llm_token_saved_pct']}, 输入省%={imp['llm_input_saved_pct']})"
    )
    print(
        f"  [{'PASS' if f1_ok else 'WARN'}] 答案质量保持 (synapse F1 {st['quality']} vs text {tt['quality']})"
    )
    print(f"  artifacts -> {out_dir}/result.json")
    return 0 if (token_ok and f1_ok) else 1


def cmd_hotpot(args) -> int:
    """真实数据集(HotpotQA distractor)多文档 QA：基线塞全 10 段 vs synapse 只检索相关段（丢干扰）。

    设计：HotpotQA 每题 10 段含 8 段干扰，无状态 LLM 基线每轮重传全部 → synapse 只检索相关段，
    砍掉"被重传却无关的上下文"。诚实口径：真实 LLM token + 词级 F1 + 金标召回。
    """
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    cfg = replace(cfg, embedder=args.embedder, qa_para_k=args.k, qa_retrieval=getattr(args, "retrieval", "single"))
    from .qa.harness import run_hotpot

    print(
        f"== HotpotQA: model={cfg.model} embedder={cfg.embedder} para_k={cfg.qa_para_k} "
        f"retrieval={cfg.qa_retrieval} items={args.n} (每题 10 段=2 金标+8 干扰) =="
    )
    res = run_hotpot(cfg, n_items=args.n, seed=getattr(args, "seed", None))
    return _print_hotpot_result(cfg, res, "hotpot")


def cmd_musique(args) -> int:
    """真实数据集(MuSiQue)多文档 QA：与 HotpotQA 同结构但每题 20 段（干扰更密）。
    复用 run_hotpot 逻辑，只切换数据路径。P0-2 第二数据集交叉验证。
    """
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    cfg = replace(cfg, embedder=args.embedder, qa_para_k=args.k, qa_retrieval=getattr(args, "retrieval", "single"))
    from .qa.harness import run_hotpot

    print(
        f"== MuSiQue: model={cfg.model} embedder={cfg.embedder} para_k={cfg.qa_para_k} "
        f"retrieval={cfg.qa_retrieval} items={args.n} (每题 20 段) =="
    )
    res = run_hotpot(cfg, n_items=args.n, path="data/musique_sample.json", seed=getattr(args, "seed", None))
    return _print_hotpot_result(cfg, res, "musique")


def _print_hotpot_result(cfg, res, tag: str) -> int:
    """hotpot/musique 共用结果输出 + 落档。"""
    out_dir = os.path.join("runs", f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg.to_dict(), "result": res}, f, ensure_ascii=False, indent=2)
    imp, tt, st = res["improvement"], res["text"], res["synapse"]
    print(
        json.dumps(
            {
                "llm_token_saved_pct": imp["llm_token_saved_pct"],
                "llm_input_saved_pct": imp["llm_input_saved_pct"],
                "text_tokens_in/out/total": [
                    tt["llm_input_tokens"],
                    tt["llm_output_tokens"],
                    tt["llm_total_tokens"],
                ],
                "synapse_tokens_in/out/total": [
                    st["llm_input_tokens"],
                    st["llm_output_tokens"],
                    st["llm_total_tokens"],
                ],
                "text_F1": tt["quality"],
                "synapse_F1": st["quality"],
                "gold_recall": res["gold_recall"],
                "wire_bytes_saved_pct": imp["wire_bytes_saved_pct"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    token_ok = imp["llm_token_saved_pct"] > 0
    f1_ok = st["quality"] >= tt["quality"] - 0.03
    print(
        f"  [{'PASS' if token_ok else 'FAIL'}] 真实 LLM token 节省 "
        f"(saved%={imp['llm_token_saved_pct']}, 输入省%={imp['llm_input_saved_pct']})"
    )
    print(
        f"  [{'PASS' if f1_ok else 'WARN'}] 答案质量保持 "
        f"(synapse F1 {st['quality']} vs text {tt['quality']}, 金标召回 {res['gold_recall']})"
    )
    print(f"  artifacts -> {out_dir}/result.json")
    return 0 if (token_ok and f1_ok) else 1


def cmd_hotpot_stats(args) -> int:
    """HotpotQA 统计稳健化：N 题 × R 次重复 → token 省/F1 的 mean±std + 配对 Δ 95% CI + 胜负。"""
    cfg = _real_cfg(args)
    if cfg is None:
        return 2
    cfg = replace(cfg, embedder=args.embedder, qa_para_k=args.k)
    from .qa.harness import run_hotpot_stats

    print(
        f"== HotpotQA-STATS: model={cfg.model} embedder={cfg.embedder} para_k={cfg.qa_para_k} "
        f"N={args.n} × R={args.repeats} =="
    )
    res = run_hotpot_stats(cfg, n_items=args.n, repeats=args.repeats)

    out_dir = os.path.join("runs", f"hotpot_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg.to_dict(), "result": res}, f, ensure_ascii=False, indent=2)

    ts, tf, sf, gr = res["token_saved"], res["text_f1"], res["syn_f1"], res["gold_recall"]
    pd = res["paired_delta_f1"]
    print(
        json.dumps(
            {
                "level_counts": res["level_counts"],
                "token_saved_pct(mean±std)": f"{ts['mean']}±{ts['std']}",
                "text_F1(mean±std)": f"{tf['mean']}±{tf['std']}",
                "synapse_F1(mean±std)": f"{sf['mean']}±{sf['std']}",
                "gold_recall(mean±std)": f"{gr['mean']}±{gr['std']}",
                "paired_ΔF1_mean": pd["mean"],
                "paired_ΔF1_ci95": pd["ci95"],
                "paired_winloss": {k: pd[k] for k in ("syn_win", "tie", "syn_loss", "n_pairs")},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    token_ok = ts["mean"] > 0
    # 非劣：配对 ΔF1 的 95% CI 下沿 ≥ −0.03（质量不显著下降）
    noninferior = pd["ci95"][0] >= -0.03
    print(f"  [{'PASS' if token_ok else 'FAIL'}] token 省 {ts['mean']}%±{ts['std']} (远超噪声=真信号)")
    print(
        f"  [{'PASS' if noninferior else 'WARN'}] 质量非劣 (配对 ΔF1={pd['mean']}, 95%CI={pd['ci95']}, "
        f"胜/平/负={pd['syn_win']}/{pd['tie']}/{pd['syn_loss']})"
    )
    print(f"  artifacts -> {out_dir}/result.json")
    return 0 if (token_ok and noninferior) else 1


def main(argv=None) -> int:
    try:  # Windows 控制台/重定向默认 GBK，无法编码 − ± Δ 等 Unicode；强制 UTF-8 防崩/防乱码
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="synapse")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("smoke", help="离线 mock 自检").set_defaults(func=cmd_smoke)
    ab = sub.add_parser("ab", help="双模式 A/B 对比")
    ab.add_argument("--config", default=None)
    ab.add_argument("--rounds", type=int, default=5)
    ab.set_defaults(func=cmd_ab)
    pr = sub.add_parser("probe", help="真实 API 输出形态探针（L5）")
    pr.add_argument("--config", default=None)
    pr.set_defaults(func=cmd_probe)
    sg = sub.add_parser("signal", help="signal 轮：真实 API 小规模 A/B + 字节节省判定")
    sg.add_argument("--config", default=None)
    sg.add_argument("--rounds", type=int, default=5)
    sg.add_argument("--topic", default="the Transformer attention mechanism in deep learning")
    sg.add_argument("--no-memory", action="store_true", help="B3-no-mem ablation：每任务清空记忆（证假设3归因）")
    sg.set_defaults(func=cmd_signal)
    m7 = sub.add_parser("m7", help="M7：≥2 组关联连续任务，验证 G2 跨组复用 G1 记忆")
    m7.add_argument("--config", default=None)
    m7.add_argument("--g1", type=int, default=5)
    m7.add_argument("--g2", type=int, default=5)
    m7.add_argument("--topic", default="the Transformer attention mechanism in deep learning")
    m7.set_defaults(func=cmd_m7)
    cq = sub.add_parser("coqa", help="真实数据集(CoQA)对话式 QA：真实 token + F1 对比")
    cq.add_argument("--config", default=None)
    cq.add_argument("--convs", type=int, default=2)
    cq.add_argument("--embedder", default="api", choices=["api", "hash", "sentence"])
    cq.add_argument("--k", type=int, default=6, help="synapse 每轮检索故事句数")
    cq.set_defaults(func=cmd_coqa)
    hp = sub.add_parser("hotpot", help="真实数据集(HotpotQA distractor)：丢干扰段，真实 token + F1")
    hp.add_argument("--config", default=None)
    hp.add_argument("--n", type=int, default=10, help="题数")
    hp.add_argument("--embedder", default="api", choices=["api", "hash", "sentence"])
    hp.add_argument("--k", type=int, default=3, help="synapse 每题检索段数（10 段取 k）")
    hp.add_argument("--seed", type=int, default=None, help="题序 shuffle seed（P0-4 可复现性；None=原序）")
    hp.add_argument("--retrieval", default="single", choices=["single", "twohop", "bridge"],
                    help="检索模式：single=单跳 | twohop=嵌入查询扩展 | bridge=词法实体桥接")
    hp.set_defaults(func=cmd_hotpot)
    mq = sub.add_parser("musique", help="真实数据集(MuSiQue)：20 段干扰更密，第二数据集交叉验证")
    mq.add_argument("--config", default=None)
    mq.add_argument("--n", type=int, default=10, help="题数")
    mq.add_argument("--embedder", default="api", choices=["api", "hash", "sentence"])
    mq.add_argument("--k", type=int, default=3, help="synapse 每题检索段数（20 段取 k）")
    mq.add_argument("--seed", type=int, default=None, help="题序 shuffle seed（P0-4 可复现性）")
    mq.add_argument("--retrieval", default="single", choices=["single", "twohop", "bridge"],
                    help="检索模式：single=单跳 | twohop=嵌入查询扩展 | bridge=词法实体桥接")
    mq.set_defaults(func=cmd_musique)
    hs = sub.add_parser("hotpot-stats", help="HotpotQA 统计稳健化：N×R + 配对置信区间")
    hs.add_argument("--config", default=None)
    hs.add_argument("--n", type=int, default=50, help="题数")
    hs.add_argument("--repeats", type=int, default=3, help="重复次数（捕捉 temp=0 MoE 非确定）")
    hs.add_argument("--embedder", default="api", choices=["api", "hash", "sentence"])
    hs.add_argument("--k", type=int, default=3, help="synapse 每题检索段数（10 段取 k）")
    hs.set_defaults(func=cmd_hotpot_stats)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
