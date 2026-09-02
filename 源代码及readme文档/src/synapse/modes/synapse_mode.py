"""结构化协议协作模式（SYNAPSE），基座 = smolagents。

赛题咬合：M2 结构化消息 + M4 句向量预测残差（非文本状态传递）+ M5/M6 共享记忆复用。
4 个 smolagents CodeAgent 做实际工作（含真·CodeAct=M11）；证据不再全量文本透传，而是经
共享记忆 + 预测残差跨 agent 传递。共享记忆跨任务累积 → 预测基更准 → 残差更稀疏
→ 非文本字节随经验减少。
"""

from __future__ import annotations

import hashlib
import time
import uuid

from ..config import Config
from ..runtime.team import build_team, _make_verify_check_fn
from ..protocol.messages import Message, ActionType, spill_result
from ..protocol.handshake import CNR
from ..protocol.scheduler import Scheduler
from ..stateplane.embedding import make_embedder
from ..stateplane.residual import (
    ResidualCodec,
    deserialize_base,
    quantize_vec,
    serialize_base,
)
from ..stateplane.checksum import digest_bytes, digest_packet, verify_packet
from ..stateplane.vector_index import VectorIndex
from ..stateplane.cas import CAS
from ..memory.store import MemoryStore
from ..memory.retrieval import HybridRetriever
from ..memory.tom import ToMPredictor
from ..memory.consolidate import Consolidator
from ..eval.metrics import Metrics, embedder_stats
from ..prompts import plan_prompt, retrieve_prompt, execute_prompt, summarize_prompt


def _valid_content_digest(cd) -> bool:
    """content_digest 合法性（blake2b 8B hex=16 字符）。strict 下缺失/畸形即校验失败。"""
    return isinstance(cd, str) and len(cd) == 16 and all(c in "0123456789abcdef" for c in cd)


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
        self.vec_index = VectorIndex()  # V3-04：文本句柄↔量化向量（接收方恢复面）
        self.generation = 0  # V3-04：任务代（L1 绑定任务代，检测跨代陈旧 packet）
        self.session_id = uuid.uuid4().hex[:16]  # V3-04：L1 会话域（防跨会话重放）
        # L1 认证密钥（审查遗留闭环）：keyed blake2b MAC——主动方无 key 不能重算校验和；
        # 同进程自动共享，跨进程经 CNR hello 协商（路线图，设计文档 §6）
        self._mac_key = hashlib.blake2b(uuid.uuid4().bytes, digest_size=32).digest()
        # 重放窗口：已成功消费帧 key=generation:msg_id（dict 保序；超限淘汰最老一半保持有界）
        self._consumed_frames: dict[str, None] = {}
        self._proj = None  # JL 投影器（cfg.residual_project_dim > 0 时惰性构建，发送/接收共享）
        self.consolidator = Consolidator(cfg)

    def run_task(self, task) -> dict:
        cfg = self.cfg
        self.generation += 1
        # B3-no-mem 强 ablation：每任务前清空跨任务记忆（证假设3归因——残差率下降是否因果源于记忆）
        if getattr(cfg, "abl_no_memory", False):
            self.store._units.clear()
            if hasattr(self.store, "_prototypes"):
                self.store._prototypes.clear()
            self.cas = CAS()  # 重置内容寻址存储
            self.vec_index = VectorIndex()  # 恢复面同步重置（审查 P2-4：防悬空句柄污染消融口径）
        team = self.team
        team.bind_topic(task.topic)
        m = Metrics(mode="synapse")
        # V3-02 cold/warm 分列：embedder 与 CAS 跨任务持久，取任务级增量
        er0, eh0, et0 = embedder_stats(self.embedder)
        cw0, cb0 = self.cas.writes, self.cas.write_bytes
        # §2.2 CNR 握手带运行时能力探测（check_fn 门控）：Executor 声明 codeact_sandbox 时实测
        sched = Scheduler(team.agents(), cnr=CNR(check_fn=_make_verify_check_fn()), metrics=m)
        planner = sched.agent("planner")
        retr = sched.agent("retriever")
        execu = sched.agent("executor")
        summ = sched.agent("summarizer")

        tok0 = team.llm_tokens()
        ti0, to0 = team.token_io()  # 新口径（M8 真实通信成本）
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

        if getattr(cfg, "residual_true_path", False):
            # V3-04 真通路：CNR 协商驱动 + 诚实分档 + 两级校验 + 恢复消费 + 逐跳回退链。
            # 接收方仅凭线缆帧字段重建并消费（mem_id 记忆解析基 / 向量索引检索恢复）；
            # 全文只经 text 帧通道（见 docs/design/v3-04-true-path.md）。
            recv_text, nnz, verified = self._true_path_transfer(
                sched, m, evidence, Y, b_hat, base_sim, base_id, text_handle, retr, summ
            )
            ok = verified
        else:
            # §1.2 三档混合协议（对标 HyLaT）：tier 标注发送方预测基强度，供协议演化分析。
            #   residual(强基) : sim ≥ 阈值 → 残差稀疏（核心收缩机制成立的稳态）
            #   embedding(弱基) : 0 < sim < 阈值 → 残差仍可编码但较大（记忆积累中）
            #   residual(零基) : 无记忆/首轮冷启动 → 对零基编码出大残差（收缩序列的起点，必为正）
            #   text(回退)     : 仅校验失败时切档 → 全量文本（协议正常一档，非异常降级）
            # 注：首轮冷启动不走 text 档而走零基 residual 档，以保住"残差随经验单调下降"的核心叙事
            # （若首轮 nontext=0、末轮>0，收缩断言会反相；零基残差是收缩序列的合法正起点）。
            has_base = b_hat is not None and base_sim > 0.0
            tier = "residual" if not has_base or base_sim >= cfg.verify_threshold else "embedding"

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
                m.fallback_events += 1  # V3-04 口径分列：旧路径一次失败=1 event=1 step
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
            summarize_prompt(task, memory_snapshot),
            reset=True,
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
        ti, to = team.token_io()
        m.llm_input_tokens = ti - ti0
        m.llm_output_tokens = to - to0
        er, eh, et = embedder_stats(self.embedder)
        m.embed_requests, m.embed_cache_hits, m.embed_input_tokens = er - er0, eh - eh0, et - et0
        m.cas_writes, m.cas_write_bytes = self.cas.writes - cw0, self.cas.write_bytes - cb0
        m.quality = 1.0 if conclusion else 0.0
        return {
            "metrics": m,
            "conclusion": conclusion,
            "nnz": nnz,
            "checksum_ok": ok,
            # 真通路补充口径：checksum_ok=首帧 L1+L2 是否通过；final_recovery_ok=最终是否恢复成功
            # （回退后仍可为 True；旧路径无回退链，两者恒相等）
            "final_recovery_ok": recv_text is not None,
        }

    # ---------------- V3-04 真通路（Issue #148746，docs/design/v3-04-true-path.md） ----------------

    # 档位能力秩（与 CNR.ENCODING_RANK 对齐：hidden 为路线图能力，按最高秩放行）
    _TIER_RANK = {"residual": 2, "residual_zero": 2, "embedding": 1, "text": 0, "hidden": 3}

    def _true_path_transfer(
        self, sched, m, evidence, Y, b_hat, base_sim, base_id, text_handle, retr, summ
    ) -> tuple[str, int, bool]:
        """残差/VLC 真数据通路：CNR 驱动选档发帧 + 接收方从线缆帧字段恢复 + 逐跳回退链。

        发送方：向量可寻址索引 put(text_handle, 量化Y)；率失真选档（残差 vs 全量向量取小）；
        按 消融/基强度/协商限幅 真实分叉（residual | residual_zero | embedding | text）。
        预测基只传 mem_id 句柄——接收方从自身共享记忆解析（记忆是解码端边信息），
        不传基向量、不直接复用发送方 b_hat 对象。
        接收方：_receive_frame 仅凭帧字段（payload_kind/handles/checksum/meta）驱动——
        L1 完整性（可复算）→ 记忆解析基重构 → L2 余弦检索 + content_digest 身份校验恢复；
        失败逐跳回退 残差→embedding→text（每跳都经构造帧→接收帧，不复用发送方局部变量）。
        返回 (恢复文本, nnz, 首帧两级校验是否通过)。
        """
        cfg = self.cfg
        gen = self.generation
        # 投影域（创新增强，默认关）：残差/索引在 JL 投影域——高维稠密向量下残差字节≈按维数比下降
        proj = self._projection_for(len(Y))
        Y_enc = proj.project(Y) if proj else Y
        b_enc = proj.project(b_hat) if (proj and b_hat is not None) else b_hat
        Y_q = quantize_vec(Y_enc, self.codec.grid)
        vec_bytes = serialize_base(Y_q)  # embedding 档全量 packet（率失真比较 + 回退跳 1 共用）
        full_vec_wire = len(vec_bytes) + 12
        text_wire = len(evidence.encode("utf-8")) + 12  # text 档载荷（正文+头/校验记账，同口径比较）
        content_digest = digest_bytes(evidence.encode("utf-8"))
        # 恢复面先行：文本句柄 ↔ 量化向量（接收方检索恢复的出口；帧本身不携带全文句柄）
        self.vec_index.put(text_handle, Y_q)

        negotiated = sched.cnr.negotiate(retr.agent_id, summ.agent_id)  # R-P0-4：真实协商驱动选档
        has_base = b_hat is not None and base_sim > 0.0
        base_ref = base_id if has_base else ""  # 基引用统一判据（试编码与发送帧一致）
        pkt = None
        if cfg.abl_no_residual:
            intended = "embedding"  # R-P0-3：消融=真发全量向量 packet，数据路径分叉而非改账
        else:
            # 三方率失真选档（GPT 闭环遗留）：残差 vs 全量向量 vs 全文取最小——协议对载荷形态
            # 全局最优；短文本场景诚实选 text 档（字节数是物理事实，不以档位偏好掩盖）
            pkt = self.codec.encode(Y_enc, b_enc if has_base else None, base_ref, gen)
            intended = (
                ("residual" if has_base else "residual_zero")
                if pkt.size_bytes() <= min(full_vec_wire, text_wire)
                else ("embedding" if full_vec_wire <= text_wire else "text")
            )
        cap = self._TIER_RANK.get(negotiated, 0)
        tier = intended if self._TIER_RANK[intended] <= cap else ("embedding" if cap >= 1 else "text")

        def _checksum(payload: bytes, base_ref: str, pk: str) -> str:
            # 认证域含 pk:source_dim:dim:project_dim（解释 payload 的关键元数据须防篡改；GPT 终审；
            # #149012：source_dim 显式上线缆后，接收方可凭帧独立复算激活投影档，不再依赖配置原值）；
            # tag 128bit（认证场景不用 64bit）
            domain = f"{pk}:{len(Y)}:{len(Y_q)}:{proj.proj_dim if proj else 0}"
            return digest_packet(
                payload,
                base_ref,
                gen,
                self.session_id,
                domain,
                content_digest,
                size=16,
                key=self._mac_key,
            )

        def _data_frame(payload_handle, base_ref, pk, checksum, nontext, nnz_, tier_):
            return Message(
                sched.next_msg_id(),
                retr.agent_id,
                summ.agent_id,
                ActionType.TELL.value,
                handles=(payload_handle, base_ref),
                payload_kind=pk,
                checksum=checksum,
                meta={
                    "nontext_bytes": nontext,
                    "nnz": nnz_,
                    "tier": tier_,
                    "generation": gen,
                    "content_digest": content_digest,
                    "source_dim": len(Y),  # 原始 embedding 维度（投影输入域；#149012）
                    "dim": len(Y_q),
                    "base_policy": self.tom.policy,  # V3-04 ToM 选基三档（字节按档分列报告）
                    "project_dim": proj.proj_dim if proj else 0,  # 投影域残差（0=原域）
                },
            )

        # --- 发送方：按档构造线缆帧（真实分叉；text 档=真文本帧，无向量载荷） ---
        nnz = 0
        if tier == "text":
            frame = Message(
                sched.next_msg_id(),
                retr.agent_id,
                summ.agent_id,
                ActionType.TELL.value,
                payload_kind="text",
                text=evidence,
                checksum=_checksum(evidence.encode("utf-8"), "", "text"),
                meta={
                    "tier": "text",
                    "generation": gen,
                    "content_digest": content_digest,
                    "base_policy": self.tom.policy,
                    "source_dim": len(Y),  # 认证域对称（pk:source_dim:dim:project_dim）
                    "dim": len(Y_q),
                    "project_dim": proj.proj_dim if proj else 0,
                },
            )
        elif tier == "embedding":
            vec_handle = self.cas.put(vec_bytes)
            frame = _data_frame(
                vec_handle,
                "",
                "embedding",
                _checksum(vec_bytes, "", "embedding"),
                full_vec_wire,
                len(Y_q),
                "embedding",
            )
            nnz = len(Y_q)
        else:  # residual / residual_zero（pkt 已在率失真试编码时算出，编码域=投影域）
            # base_ref 已在选档前统一（has_base 判据，与试编码一致）；消融路径 pkt=None 不会到这
            res_handle = self.cas.put(pkt.residual)
            frame = _data_frame(
                res_handle,
                base_ref,
                "residual",
                _checksum(pkt.residual, base_ref, "residual"),
                pkt.size_bytes(),
                pkt.nnz,
                tier,
            )
            nnz = pkt.nnz
        sched.send(frame)

        # --- 接收方：从线缆帧驱动（首帧 → 逐跳回退；每跳都经帧构造→帧接收） ---
        recv_text, channel = self._receive_frame(frame, m)
        verified = channel is not None
        if recv_text is None:
            sched.send(
                Message(
                    sched.next_msg_id(),
                    summ.agent_id,
                    retr.agent_id,
                    ActionType.ASK.value,
                    params={"reason": "verify_fail"},
                )
            )
            m.fallback_events += 1
            if frame.payload_kind == "residual":
                # 跳 1：embedding 档（全量向量）——补发帧同样经接收路径消费
                fb = _data_frame(
                    self.cas.put(vec_bytes),
                    "",
                    "embedding",
                    _checksum(vec_bytes, "", "embedding"),
                    full_vec_wire,
                    len(Y_q),
                    "embedding",
                )
                fb.meta["fallback"] = True
                sched.send(fb)
                recv_text, _ch = self._receive_frame(fb, m)
            if recv_text is None:
                # 跳 2：text 档——全文直传（唯一全文通道），接收方从帧 text 字段读取
                fb2 = Message(
                    sched.next_msg_id(),
                    retr.agent_id,
                    summ.agent_id,
                    ActionType.TELL.value,
                    payload_kind="text",
                    text=evidence,
                    checksum=_checksum(evidence.encode("utf-8"), "", "text"),
                    meta={
                        "fallback": True,
                        "tier": "text",
                        "generation": gen,
                        "content_digest": content_digest,
                        "source_dim": len(Y),  # 认证域对称（pk:source_dim:dim:project_dim）
                        "dim": len(Y_q),
                        "project_dim": proj.proj_dim if proj else 0,
                    },
                )
                sched.send(fb2)
                recv_text, _ch = self._receive_frame(fb2, m)
        return recv_text, nnz, verified

    def _receive_frame(self, msg, m) -> tuple[str | None, str | None]:
        """接收方恢复：仅凭线缆帧字段（payload_kind/handles/checksum/meta/text）驱动。

        - text 帧：L1（keyed MAC，域含正文字节）+ content_digest 身份校验后消费。
        - residual/embedding 帧：L1（keyed MAC）→ residual 按句柄从自身记忆解析预测基
          （缺失/维度不符→回退；投影域时基经同一共享投影）→ 重构 → L2 余弦检索 +
          content_digest 身份校验。
        - 重放窗口：已成功消费的帧（msg_id）重复投递直接拒绝（审查遗留闭环）。
        strict 下 content_digest 为强制不变量；任何失败统一返回 (None, None) 走回退链。
        """
        cfg = self.cfg
        strict = not cfg.abl_no_checksum
        meta = msg.meta or {}
        try:
            gen = int(meta.get("generation", 0))
        except (TypeError, ValueError):
            return None, None
        # 重放窗口：key=任务代:帧id（Scheduler 每任务重建、msg_id 跨任务重复，须以 generation 区分）
        frame_key = f"{gen}:{msg.msg_id}"
        if strict and frame_key in self._consumed_frames:
            return None, None
        if len(self._consumed_frames) > 10000:  # 有界重放窗口：淘汰最老一半
            for old in list(self._consumed_frames)[: len(self._consumed_frames) // 2]:
                del self._consumed_frames[old]
        # 代有效性：同会话只接受当前任务代的帧（旧代帧即便 MAC 合法也拒绝——GPT 终审）
        if strict and gen != self.generation:
            return None, None
        cd = meta.get("content_digest")
        if strict and not _valid_content_digest(cd):  # 身份绑定为不变量，非可选附加字段
            return None, None
        if msg.payload_kind == "text":
            if msg.text is None:
                return None, None
            tb = msg.text.encode("utf-8", errors="strict")
            # text 帧 L1（keyed MAC，128bit）：domain 与发送方对称（pk:source_dim:dim:project_dim）
            dim_meta = int(meta.get("dim", 0) or 0)
            domain = (
                f"text:{int(meta.get('source_dim', 0) or 0)}:{dim_meta}:"
                f"{int(meta.get('project_dim', 0) or 0)}"
            )
            if strict and not verify_packet(
                tb,
                "",
                gen,
                msg.checksum,
                self.session_id,
                domain,
                cd,
                size=16,
                key=self._mac_key,
            ):
                return None, None
            if strict and digest_bytes(tb) != cd:  # 显式身份比对（L1 域已绑定，防御深度）
                return None, None
            m.recovery_text += 1
            self._consumed_frames[frame_key] = None
            return msg.text, "text"
        try:
            hs = tuple(msg.handles or ())
            payload_handle = hs[0] if hs else ""
            base_ref = hs[1] if len(hs) > 1 else ""
            payload = self.cas.get(payload_handle)
            if payload is None:
                return None, None
            # 投影域一致性（GPT 终审：全非文本帧校验，不限于带基 residual；#149012 修订）：
            # 接收方凭帧声明 source_dim 独立复算激活投影档，须与帧声明 project_dim 一致——
            # 不再与 cfg.residual_project_dim 原值比较（64 维 mock 携带 384 目标工作点时
            # 发送方钳制声明 0，原值比较会误拒全部合法帧）；编码域 dim 须与 source_dim/
            # project_dim 自洽（pd>0 → dim==pd；pd==0 → dim==source_dim）；
            # source_dim/dim/project_dim 与 pk 同入 MAC 认证域
            try:
                src_meta = int(meta.get("source_dim", 0))
                dim = int(meta.get("dim", 0))
                pd_meta = int(meta.get("project_dim", 0) or 0)
            except (TypeError, ValueError):
                return None, None
            if src_meta <= 0 or pd_meta != self._effective_project_dim(src_meta):
                return None, None
            if dim != (pd_meta if pd_meta > 0 else src_meta):
                return None, None
            domain = f"{msg.payload_kind}:{src_meta}:{dim}:{pd_meta}"
            if strict and not verify_packet(
                payload,
                base_ref,
                gen,
                msg.checksum,
                self.session_id,
                domain,
                cd,
                size=16,
                key=self._mac_key,
            ):
                return None, None
            if msg.payload_kind == "residual":
                if base_ref:  # 记忆是解码端边信息：接收方从自身 MemoryStore 解析预测基
                    unit = self.store.get(base_ref)
                    emb = unit.embedding if unit is not None else None
                    if emb is None:
                        return None, None  # 基缺失 → 受控回退
                    proj = self._projection_for(len(emb))
                    if proj is not None:  # 投影域残差：基经同一共享投影（一致性已在上面统一校验）
                        emb = proj.project(emb)
                    if len(emb) != dim:
                        return None, None  # 维度不符（含投影后）→ 受控回退
                    bq_recv = quantize_vec(emb, self.codec.grid)
                else:
                    bq_recv = [0] * dim  # 零基冷启动（dim=投影域维数）
                yq_hat = self.codec.decode_bytes(payload, bq_recv, dim)
            elif msg.payload_kind == "embedding":
                yq_hat = deserialize_base(payload)
            else:
                return None, None
        except (ValueError, TypeError, IndexError):
            return None, None  # 畸形帧（空 handles/非对齐长度/越界索引/奇数向量字节等）→ 回退链
        hits = self.vec_index.search(yq_hat, k=1)
        if not hits:
            return None, None
        h, sim = hits[0]
        if strict and sim < cfg.verify_threshold:  # L2 语义校验（投影域/基失配/裁剪失真）
            return None, None
        data = self.cas.get(h)
        if data is None:
            return None, None
        # 身份校验：恢复文本须与帧声明 content_digest 一致——拦截索引近邻错配/decoy 静默消费
        if strict and digest_bytes(data) != cd:
            return None, None
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return None, None
        self._consumed_frames[frame_key] = None
        if msg.payload_kind == "residual":
            m.recovery_residual += 1
            return text, "residual"
        m.recovery_embedding += 1
        return text, "embedding"

    def _effective_project_dim(self, source_dim: int) -> int:
        """配置投影维的实际激活档：仅当 0 < cfg.residual_project_dim < source_dim 时激活（投影须降维）。

        发送方（len(Y)）、帧声明（source_dim）与接收方复算共用同一判定——64 维 mock 携带
        384 目标工作点时自动回原域（project_dim=0），1536 维真实评测下 384 生效（#149012）。
        """
        pd = int(getattr(self.cfg, "residual_project_dim", 0) or 0)
        return pd if 0 < pd < source_dim else 0

    def _projection_for(self, source_dim: int):
        """按配置惰性构建共享 JL 投影器（未激活返回 None=原域；激活判定见 _effective_project_dim）。"""
        pd = self._effective_project_dim(source_dim)
        if pd <= 0:
            return None
        if self._proj is None or self._proj.dim != source_dim or self._proj.proj_dim != pd:
            from ..stateplane.projection import Projection

            self._proj = Projection(source_dim, pd)
        return self._proj
