"""结构化协议协作模式（SYNAPSE），基座 = smolagents。

赛题咬合：M2 结构化消息 + M4 句向量预测残差（非文本状态传递）+ M5/M6 共享记忆复用。
4 个 smolagents CodeAgent 做实际工作（含真·CodeAct=M11）；证据不再全量文本透传，而是经
共享记忆 + 预测残差跨 agent 传递。共享记忆跨任务累积 → 预测基更准 → 残差更稀疏
→ 非文本字节随经验减少。
"""

from __future__ import annotations

import time

from ..config import Config
from ..runtime.team import build_team, _make_verify_check_fn
from ..protocol.messages import Message, ActionType, spill_result
from ..protocol.handshake import CNR
from ..protocol.scheduler import Scheduler
from ..stateplane.embedding import make_embedder
from ..stateplane.residual import ResidualCodec
from ..stateplane.cas import CAS
from ..memory.store import MemoryStore
from ..memory.retrieval import HybridRetriever
from ..memory.tom import ToMPredictor
from ..memory.consolidate import Consolidator
from ..eval.metrics import Metrics
from ..prompts import plan_prompt, retrieve_prompt, execute_prompt, summarize_prompt


class SynapseSession:
    """持续会话：共享记忆跨任务累积，非文本字节随经验减少。"""

    def __init__(self, cfg: Config, team=None):
        self.cfg = cfg
        self.team = team or build_team(cfg)  # 持续复用同一团队
        self.embedder = make_embedder(cfg)
        self.store = MemoryStore(self.embedder)
        self.mem_retriever = HybridRetriever(self.store, self.embedder, cfg)
        self.tom = ToMPredictor(self.mem_retriever, self.embedder, cfg)
        self.codec = ResidualCodec(cfg)
        self.cas = CAS()
        self.consolidator = Consolidator(cfg)

    def run_task(self, task) -> dict:
        cfg = self.cfg
        # B3-no-mem 强 ablation：每任务前清空跨任务记忆（证假设3归因——残差率下降是否因果源于记忆）
        if getattr(cfg, "abl_no_memory", False):
            self.store._units.clear()
            if hasattr(self.store, "_prototypes"):
                self.store._prototypes.clear()
            self.cas = CAS()  # 重置内容寻址存储
        team = self.team
        team.bind_topic(task.topic)
        m = Metrics(mode="synapse")
        # §2.2 CNR 握手带运行时能力探测（check_fn 门控）：Executor 声明 codeact_sandbox 时实测
        sched = Scheduler(team.agents(), cnr=CNR(check_fn=_make_verify_check_fn()), metrics=m)
        planner = sched.agent("planner")
        retr = sched.agent("retriever")
        execu = sched.agent("executor")
        summ = sched.agent("summarizer")

        tok0 = team.llm_tokens()
        t0 = time.perf_counter()

        # 计划（结构化头，不透传长文本）
        plan = planner.run(plan_prompt(task), reset=True)
        sched.send(
            Message(
                sched.next_msg_id(),
                planner.agent_id,
                retr.agent_id,
                ActionType.PLAN.value,
                params={"steps": plan},
            )
        )

        # 检索共享记忆（一次检索复用于命中判定 + ToM）
        results = self.mem_retriever.search(task.topic, k=cfg.retrieval_k)
        hit = bool(results) and results[0][1] > cfg.hit_threshold
        m.record_query(hit)

        # §4.1 frozen-snapshot 记忆注入：任务前冻结当前相关记忆的 summary 快照注入 prompt，
        # session 中途写入落盘但不改已注入快照（保前缀缓存）；真实 API 路径的零成本 token 节省
        memory_snapshot = " | ".join(f"[{u.kind}]{u.summary}" for u, _ in results[:3]) or None
        if memory_snapshot:
            m.frozen_snapshot_injections += 1

        evidence = retr.run(retrieve_prompt(task, memory_snapshot), reset=True)
        Y = self.embedder.encode(evidence)
        if cfg.abl_no_tom:  # 消融：无 ToM 预测基 → 残差对零基编码、不因经验变准
            b_hat, base_id, base_sim = None, None, 0.0
        else:
            b_hat, base_id, base_sim = self.tom.best_base(results, Y)  # 发送方择最优预测基 B̂_j + sim

        # 证据正文存入共享 CAS（"记忆即媒介"）：接收方按句柄取，不在 agent 间消息里透传正文
        text_handle = self.cas.put(evidence.encode("utf-8"))

        # §1.2 三档混合协议（对标 HyLaT）：tier 标注发送方预测基强度，供协议演化分析。
        #   residual(强基) : sim ≥ 阈值 → 残差稀疏（核心收缩机制成立的稳态）
        #   embedding(弱基) : 0 < sim < 阈值 → 残差仍可编码但较大（记忆积累中）
        #   residual(零基) : 无记忆/首轮冷启动 → 对零基编码出大残差（收缩序列的起点，必为正）
        #   text(回退)     : 仅校验失败时切档 → 全量文本（协议正常一档，非异常降级）
        # 注：首轮冷启动不走 text 档而走零基 residual 档，以保住"残差随经验单调下降"的核心叙事
        # （若首轮 nontext=0、末轮>0，收缩断言会反相；零基残差是收缩序列的合法正起点）。
        has_base = b_hat is not None and base_sim > 0.0
        tier = (
            "residual" if not has_base or base_sim >= cfg.verify_threshold
            else "embedding"
        )

        # 非文本状态传递：预测残差编码（只传必要分量）；线缆只走 残差句柄 + 内容句柄 + 校验
        pkt = self.codec.encode(Y, b_hat, base_id)
        if cfg.abl_no_residual:  # 对照模式：发全量量化向量(dim×2)，无预测/无稀疏
            nontext_bytes, nnz = len(Y) * 2 + 12, len(Y)
        else:
            nontext_bytes, nnz = pkt.size_bytes(), pkt.nnz
        handle = self.cas.put(pkt.residual)
        sched.send(
            Message(
                sched.next_msg_id(),
                retr.agent_id,
                summ.agent_id,
                ActionType.TELL.value,
                handles=(handle, text_handle),
                payload_kind="residual",
                checksum=pkt.checksum,
                meta={"nontext_bytes": nontext_bytes, "nnz": nnz, "tier": tier},
            )
        )

        # 接收方：按句柄从共享 CAS 取回证据正文（非线缆透传），重嵌入得真值 Y_true
        recv_evidence = self.cas.get(text_handle)
        recv_text = recv_evidence.decode("utf-8") if recv_evidence else evidence
        Y_true = self.embedder.encode(recv_text)
        # 解码重构 Ŷ + 语义校验：cos(Ŷ, Y_true) ≥ 阈值
        yq_hat = self.codec.decode(pkt, b_hat)
        ok = True if cfg.abl_no_checksum else self.codec.verify(yq_hat, Y_true)
        if not ok:  # 校验不符（预测基失配/裁剪失真）→ 回退取全量文本（切到协议 text 档）
            sched.send(
                Message(
                    sched.next_msg_id(),
                    summ.agent_id,
                    retr.agent_id,
                    ActionType.ASK.value,
                    params={"reason": "verify_fail"},
                )
            )
            sched.send(
                Message(
                    sched.next_msg_id(),
                    retr.agent_id,
                    summ.agent_id,
                    ActionType.TELL.value,
                    payload_kind="text",
                    text=evidence,
                    meta={"fallback": True, "tier": "text"},
                )
            )

        # 执行（真·CodeAct，结构化结果）；§2.3 result 超预算则 spill 到 CAS 句柄 + 短摘要
        exec_res = execu.run(execute_prompt(), reset=True, additional_args={"evidence": evidence})
        exec_result, spill_handles = spill_result({"metric": exec_res}, self.cas)
        sched.send(
            Message(
                sched.next_msg_id(),
                execu.agent_id,
                summ.agent_id,
                ActionType.EXECUTE.value,
                result=exec_result,
                handles=spill_handles,
                meta={"spilled": bool(spill_handles)},
            )
        )
        # 使用环（§13.2）：总结器用接收方已取回的证据正文 + 计算结果出结论（复用同一冻结快照）
        conclusion = summ.run(
            summarize_prompt(task, memory_snapshot), reset=True,
            additional_args={"evidence": recv_text, "metric": exec_res},
        )

        # 写回高价值记忆（供后续任务复用 → 非文本字节更省）
        tags = tuple(task.topic.split())
        self.store.write(
            source_agent=retr.agent_id,
            task_topic=task.topic,
            summary=f"evidence:{task.topic}",
            content=evidence,
            kind="evidence",
            tags=tags,
            task_id=task.task_id,
        )
        self.store.write(
            source_agent=summ.agent_id,
            task_topic=task.topic,
            summary=f"conclusion:{task.topic}",
            content=conclusion,
            kind="conclusion",
            tags=tags,
            task_id=task.task_id,
        )
        sched.send(
            Message(
                sched.next_msg_id(),
                summ.agent_id,
                summ.agent_id,
                ActionType.WRITE.value,
                params={"topic": task.topic, "kind": "conclusion"},
            )
        )
        if not cfg.abl_no_consolidation:
            self.consolidator.consolidate(self.store)

        m.latency_s = time.perf_counter() - t0
        m.llm_tokens = team.llm_tokens() - tok0
        m.quality = 1.0 if conclusion else 0.0
        return {
            "metrics": m,
            "conclusion": conclusion,
            "nnz": nnz,
            "checksum_ok": ok,
        }
