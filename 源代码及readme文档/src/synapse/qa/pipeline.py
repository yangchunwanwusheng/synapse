"""CoQA 对话式多智能体 QA：纯文本基线 vs SYNAPSE（结构化协议+非文本检索+共享记忆）。

两模式同一应答模型、同一问题；差异只在**给应答 LLM 的上下文如何构造**：
- text 基线：每轮把【全量故事 + 全部历史 Q&A】当文本塞进 prompt → 输入 token 随轮次增长（赛题所述痛点）。
- synapse：故事切句**一次性**嵌入入共享记忆(M5)；每轮 planner 改写消解指代→retriever 按**句向量**检索
  top-k 句子(M4/M6，复用已存嵌入=记忆复用)→answerer 只读 top-k 句 + 紧凑相关历史 → 输入 token 近似恒定。

通信成本 = 真实 LLM (输入+输出) token（API usage 同口径两模式）；正确性 = 词级 F1(vs 标准答案)。
"""

from __future__ import annotations

import time

from ..eval.metrics import Metrics
from ..memory.retrieval import HybridRetriever
from ..memory.store import MemoryStore
from ..protocol.handshake import CNR
from ..protocol.messages import ActionType, Capability, Message
from ..protocol.scheduler import Scheduler
from ..runtime.model import make_model
from ..stateplane.cas import CAS
from ..stateplane.embedding import make_embedder
from .dataset import Conversation, HotpotItem
from .scoring import f1

ANSWER_SYS = (
    "You are a precise reading-comprehension assistant. Answer with the shortest exact phrase "
    "supported by the context (a few words; yes/no when applicable). Do not explain."
)


def _gen(model, sys_prompt: str, user: str) -> str:
    msg = model.generate([{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}])
    return (msg.content or "").strip()


def _io(*models) -> tuple[int, int]:
    ti = sum(int(getattr(m, "input_tokens", 0) or 0) for m in models)
    to = sum(int(getattr(m, "output_tokens", 0) or 0) for m in models)
    return ti, to


def _cap(agent_id: str, role: str, actions: tuple[str, ...]) -> Capability:
    return Capability(agent_id, role, actions, ("text", "embedding"), "paratera")


def run_text(conv: Conversation, cfg) -> dict:
    """纯文本基线：每轮全量故事+全部历史透传给应答模型（无记忆/无检索）。"""
    model = make_model(cfg, "answerer")
    m = Metrics(mode="text")
    cnr = CNR()
    cnr.hello(_cap("ctx-1", "retriever", ("TELL",)))
    cnr.hello(_cap("answerer-1", "summarizer", ("SUMMARIZE",)))
    sched = Scheduler([], cnr=cnr, metrics=m)
    history: list[tuple[str, str]] = []
    f1s: list[float] = []
    preds: list[str] = []  # V3-02 逐题落档：预测文本（与 golds 同序，供对账与复算）
    t0 = time.perf_counter()
    cum: list[int] = []
    for turn in conv.turns:
        hist_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in history)
        ctx = f"Story:\n{conv.story}\n\nConversation so far:\n{hist_text}\n\nQuestion: {turn.q}\nAnswer:"
        # 全量上下文作为一条文本消息透传给应答方（M8 消息/文本开销）
        sched.metrics.record_message(
            Message("m", "ctx-1", "answerer-1", ActionType.TELL.value, payload_kind="text", text=ctx)
        )
        ans = _gen(model, ANSWER_SYS, ctx)
        history.append((turn.q, ans))
        preds.append(ans)
        f1s.append(f1(ans, turn.gold))
        cum.append(sum(_io(model)))  # 累计 token 随轮次（基线应增长）
    m.latency_s = time.perf_counter() - t0
    m.llm_input_tokens, m.llm_output_tokens = _io(model)
    m.quality = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
    return {
        "metrics": m,
        "f1_per_turn": f1s,
        "cum_tokens": cum,
        "preds": preds,
        "golds": [t.gold for t in conv.turns],
    }


def run_synapse(conv: Conversation, cfg) -> dict:
    """SYNAPSE：故事入共享记忆(权威上下文，每轮可见→保质量)；对话历史存为记忆单元，每轮只注入
    【相关历史】= 近窗(消解局部指代) + 语义检索的更早相关轮(M4/M6)，而非像基线那样全量重述历史
    → 省"重复上下文"token(赛题所述痛点)，答案质量不降。无 planner 额外开销。
    """
    model_ans = make_model(cfg, "answerer")
    embedder = make_embedder(cfg)
    store = MemoryStore(embedder)
    retr = HybridRetriever(store, embedder, cfg)
    cas = CAS()
    m = Metrics(mode="synapse")
    # V3-02 cold/warm 分列：会话级 embedder/CAS 增量计数
    from ..eval.metrics import embedder_stats

    er0, eh0, et0 = embedder_stats(embedder)
    cnr = CNR()
    for aid, role, acts in (
        ("retriever-1", "retriever", ("RETRIEVE", "TELL")),
        ("answerer-1", "summarizer", ("SUMMARIZE",)),
    ):
        cnr.hello(_cap(aid, role, acts))
    sched = Scheduler([], cnr=cnr, metrics=m)

    # 故事一次性入共享记忆 + CAS（句柄寻址，跨轮复用同一份，不每轮新拷）。
    story_u = store.write(
        source_agent="story",
        task_topic=conv.conv_id,
        summary="story",
        content=conv.story,
        kind="evidence",
        tags=("story",),
    )
    cas.put(conv.story.encode("utf-8"))

    f1s: list[float] = []
    cum: list[int] = []
    preds: list[str] = []
    history: list[tuple[str, str]] = []
    win, sem = max(1, cfg.qa_history_k), cfg.qa_history_k
    t0 = time.perf_counter()
    n_msg = 1
    for turn in conv.turns:
        # retriever：从记忆取【相关历史】= 最近 win 轮 + 语义 top-sem 更早相关轮（embedding 选择）
        recent = history[-win:]
        recent_ids = {str(turn.idx - 1 - j) for j in range(win)}
        sem_hits = []
        if len(history) > win:
            for u, s in retr.search(turn.q, k=sem + win):
                if u.kind == "conclusion" and u.task_id not in recent_ids and s > cfg.hit_threshold:
                    sem_hits.append(u)
                if len(sem_hits) >= sem:
                    break
        m.record_query(bool(recent) or bool(sem_hits))  # 是否复用了历史记忆
        # 非文本/结构化消息：传句柄(故事 + 选中历史)，不在 agent 间消息里重述全文（M2/M4）
        handles = (story_u.mem_id,) + tuple(u.mem_id for u in sem_hits)
        sched.metrics.record_message(
            Message(
                f"m{n_msg}",
                "retriever-1",
                "answerer-1",
                ActionType.TELL.value,
                handles=handles,
                payload_kind="embedding",
                meta={"nontext_bytes": sum(len(h.encode()) for h in handles) + 8},
            )
        )
        n_msg += 1

        # answerer：完整故事(权威上下文) + 仅相关历史(近窗+语义) + 当前问题
        hist_lines = [f"Q: {q}\nA: {a}" for q, a in recent] + [u.content for u in sem_hits]
        ctx = (
            f"Story:\n{conv.story}\n\nRelevant prior Q&A:\n"
            + "\n".join(hist_lines)
            + f"\n\nQuestion: {turn.q}\nAnswer:"
        )
        ans = _gen(model_ans, ANSWER_SYS, ctx)
        f1s.append(f1(ans, turn.gold))
        preds.append(ans)
        history.append((turn.q, ans))
        store.write(
            source_agent="answerer-1",
            task_topic=conv.conv_id,
            summary=f"qa{turn.idx}",
            content=f"Q: {turn.q}\nA: {ans}",
            kind="conclusion",
            tags=("qa",),
            task_id=str(turn.idx),
        )
        cum.append(sum(_io(model_ans)))
    m.latency_s = time.perf_counter() - t0
    m.llm_input_tokens, m.llm_output_tokens = _io(model_ans)
    er, eh, et = embedder_stats(embedder)
    m.embed_requests, m.embed_cache_hits, m.embed_input_tokens = er - er0, eh - eh0, et - et0
    m.cas_writes, m.cas_write_bytes = cas.writes, cas.write_bytes
    m.quality = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
    return {
        "metrics": m,
        "f1_per_turn": f1s,
        "cum_tokens": cum,
        "preds": preds,
        "golds": [t.gold for t in conv.turns],
    }


def _retrieve_paras(retr, store, question: str, k: int, mode: str):
    """检索 k 段（k 固定 → token 成本与模式无关，差异只在"取到的是不是对的段"）。

    - single：单跳问题检索。
    - twohop：第一跳取 h1 段，用其正文做嵌入查询扩展再补检索（对桥接段较弱：长正文稀释查询）。
    - bridge：词法实体桥接——多跳问答(HotpotQA bridge)中第二跳金标段的标题(实体)通常被第一跳
      段正文提及（如「Kiss and Tell」正文提到「Shirley Temple」=第二段标题）；故取标题串现于
      第一跳正文的段为桥接段。直击多跳结构，零额外 LLM/嵌入开销。
    """
    if mode == "single":
        return [u for u, _ in retr.search(question, k=k)]
    h1 = max(1, k // 2)
    hop1 = [u for u, _ in retr.search(question, k=h1)]
    chosen, ids = list(hop1), {u.mem_id for u in hop1}
    if mode == "bridge":
        hop1_text = " ".join(u.content for u in hop1).lower()
        for u in store.all():  # 标题(实体)被第一跳正文提及 → 桥接段
            if u.mem_id not in ids and u.summary and u.summary.lower() in hop1_text:
                chosen.append(u)
                ids.add(u.mem_id)
                if len(chosen) >= k:
                    break
    else:  # twohop：嵌入查询扩展
        seed = question + " " + " ".join(u.content for u in hop1)
        for u, _ in retr.search(seed, k=k + h1):
            if u.mem_id not in ids:
                chosen.append(u)
                ids.add(u.mem_id)
            if len(chosen) >= k:
                break
    if len(chosen) < k:  # 不足 k 时按问题相似度补足
        for u, _ in retr.search(question, k=k + h1 + 2):
            if u.mem_id not in ids:
                chosen.append(u)
                ids.add(u.mem_id)
            if len(chosen) >= k:
                break
    return chosen[:k]


# ============ HotpotQA distractor：大且稀疏上下文（每题 10 段，2 金标 + 8 干扰）============
# CoQA 的故事每轮都得整篇喂给无状态 LLM（地板占 ~80% token，省幅天花板 ~19%）。
# HotpotQA 把"被重传却无关的上下文"放大到 ~80%：基线塞全 10 段、synapse 只检索相关段、丢干扰
# → 通信效率(赛题25分)/状态传递(20分)的对的 regime。这里每题语料独立（无跨题复用，记忆复用看 CoQA）。


def run_text_hotpot(items: list[HotpotItem], cfg) -> dict:
    """纯文本基线：每题把全部 10 段上下文（含 8 段干扰）整体透传给应答模型。"""
    model = make_model(cfg, "answerer")
    m = Metrics(mode="text")
    cnr = CNR()
    cnr.hello(_cap("ctx-1", "retriever", ("TELL",)))
    cnr.hello(_cap("answerer-1", "summarizer", ("SUMMARIZE",)))
    sched = Scheduler([], cnr=cnr, metrics=m)
    f1s: list[float] = []
    per_item: list[dict] = []  # V3-02 逐题落档（qid/预测/金标/F1）
    t0 = time.perf_counter()
    for it in items:
        paras = "\n\n".join(f"[{p.title}] {p.text}" for p in it.paragraphs)
        ctx = f"Context:\n{paras}\n\nQuestion: {it.q}\nAnswer:"
        sched.metrics.record_message(
            Message("m", "ctx-1", "answerer-1", ActionType.TELL.value, payload_kind="text", text=ctx)
        )
        ans = _gen(model, ANSWER_SYS, ctx)
        f1s.append(f1(ans, it.answer))
        per_item.append({"qid": it.qid, "question": it.q, "gold": it.answer, "pred": ans})
    m.latency_s = time.perf_counter() - t0
    m.llm_input_tokens, m.llm_output_tokens = _io(model)
    m.quality = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
    for rec, sc in zip(per_item, f1s):
        rec["f1"] = sc
    return {"metrics": m, "f1_per_turn": f1s, "per_item": per_item}


def run_synapse_hotpot(items: list[HotpotItem], cfg, embedder=None) -> dict:
    """SYNAPSE：每题 10 段一次性入共享记忆(状态面，句柄寻址)；retriever 按句向量检索 top-k 相关段
    （丢 8 段干扰，M4/M6）；应答方只读检索到的段（句柄传递，不在 agent 间重述全文）→ 大幅省 token。
    gold_recall = 检索到的金标段占比（证明"省 token 非靠丢答案段"）。
    embedder 可外部传入以跨多次运行复用嵌入缓存（多次重复实验时省嵌入调用）。
    """
    model = make_model(cfg, "answerer")
    embedder = embedder or make_embedder(cfg)
    m = Metrics(mode="synapse")
    cnr = CNR()
    for aid, role, acts in (
        ("retriever-1", "retriever", ("RETRIEVE", "TELL")),
        ("answerer-1", "summarizer", ("SUMMARIZE",)),
    ):
        cnr.hello(_cap(aid, role, acts))
    sched = Scheduler([], cnr=cnr, metrics=m)
    f1s: list[float] = []
    gold_recall: list[float] = []
    per_item: list[dict] = []  # V3-02 逐题落档（qid/预测/金标/F1/检索段）
    from ..eval.metrics import embedder_stats

    er0, eh0, et0 = embedder_stats(embedder)
    k = max(1, cfg.qa_para_k)
    t0 = time.perf_counter()
    n_msg = 1
    for it in items:
        store = MemoryStore(embedder)  # 每题独立 10 段语料（distractor 设定）
        cas = CAS()
        for p in it.paragraphs:
            store.write(
                source_agent="corpus",
                task_topic=it.qid,
                summary=p.title,
                content=p.text,
                kind="evidence",
                tags=("para",),
            )
            cas.put(p.text.encode("utf-8"))
        m.cas_writes += cas.writes  # 每题独立 CAS → 直接累入
        m.cas_write_bytes += cas.write_bytes
        retr = HybridRetriever(store, embedder, cfg)
        hits = _retrieve_paras(retr, store, it.q, k, cfg.qa_retrieval)
        got = {u.summary for u in hits}
        m.record_query(any(g in got for g in it.gold_titles))  # 是否检索到金标段
        if it.gold_titles:
            gold_recall.append(sum(1 for g in it.gold_titles if g in got) / len(it.gold_titles))
        # 非文本/结构化消息：只传选中段句柄，不在 agent 间重述全文（M2/M4）
        handles = tuple(u.mem_id for u in hits)
        sched.metrics.record_message(
            Message(
                f"m{n_msg}",
                "retriever-1",
                "answerer-1",
                ActionType.TELL.value,
                handles=handles,
                payload_kind="embedding",
                meta={"nontext_bytes": sum(len(h.encode()) for h in handles) + 8},
            )
        )
        n_msg += 1
        paras = "\n\n".join(f"[{u.summary}] {u.content}" for u in hits)
        ctx = f"Context:\n{paras}\n\nQuestion: {it.q}\nAnswer:"
        ans = _gen(model, ANSWER_SYS, ctx)
        f1s.append(f1(ans, it.answer))
        rec_hit = sum(1 for g in it.gold_titles if g in got) / len(it.gold_titles) if it.gold_titles else 0.0
        per_item.append(
            {
                "qid": it.qid,
                "question": it.q,
                "gold": it.answer,
                "pred": ans,
                "retrieved_titles": sorted(got),
                "gold_titles": list(it.gold_titles),
                "gold_hit": rec_hit,
            }
        )
    m.latency_s = time.perf_counter() - t0
    m.llm_input_tokens, m.llm_output_tokens = _io(model)
    er, eh, et = embedder_stats(embedder)
    m.embed_requests, m.embed_cache_hits, m.embed_input_tokens = er - er0, eh - eh0, et - et0
    m.quality = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
    for rec, sc in zip(per_item, f1s):
        rec["f1"] = sc
    return {
        "metrics": m,
        "f1_per_turn": f1s,
        "per_item": per_item,
        "gold_recall": round(sum(gold_recall) / len(gold_recall), 3) if gold_recall else 0.0,
    }
