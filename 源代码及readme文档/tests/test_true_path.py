"""V3-04 残差/VLC 真数据通路测试（Issue #148746，红→绿过程见 commit 历史）。

对应设计：docs/design/v3-04-true-path.md（前置设计冻结 2026-08-28 + 审查修复版）

覆盖的 Issue 验收点与审查修复：
- "篡改 residual 字节 checksum 必须拦截"（R-P0-2：L1 完整性校验，接收方可复算）
- "删重建逻辑答案必须变化"（R-P0-1：重建结果成为 summarizer 唯一输入，e2e 无旁路）
- no-residual 消融走独立 full-vector 真路径而非改账（R-P0-3）
- 三档真实分叉 + CNR negotiate() 驱动选档 + 冷启动诚实标档（R-P0-4，含 text 真帧）
- 审查修复：接收方从线缆帧字段驱动（wire 反序列化）、基=mem_id 从自身记忆解析、
  content_digest 身份校验拒绝近邻错配、回退链每跳消费补发帧、no-memory 同步清索引、
  旧路径 checksum 口径零变化、畸形帧受控回退、率失真选档
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import dataclasses

from synapse.config import Config  # noqa: E402
from synapse.stateplane.residual import ResidualCodec  # noqa: E402
from synapse.stateplane.embedding import HashEmbedder  # noqa: E402
from synapse.modes.synapse_mode import SynapseSession  # noqa: E402
from synapse import tasks as T  # noqa: E402


# ---------- 平面级：L1 完整性校验（接收方可复算的哈希对象） ----------


def _pkt(emb, text, base_text=None, generation=3, handle="mem-base-x"):
    cfg = Config()
    codec = ResidualCodec(cfg)
    b_hat = emb.encode(base_text) if base_text else None
    return cfg, codec, codec.encode(emb.encode(text), b_hat, handle, generation)


def test_tampered_residual_intercepted():
    # R-P0-2：篡改 residual 字节 → L1 checksum 必须拦截（旧余弦校验实测仍 True）
    from synapse.stateplane.checksum import digest_packet, verify_packet

    emb = HashEmbedder(Config().embed_dim)
    cfg, codec, pkt = _pkt(emb, "evidence about alpha : alpha-fact0 alpha-fact1", None)
    assert pkt.nnz > 0, "零基编码应有非零残差分量"
    c = digest_packet(pkt.residual, "mem-base-x", 3, session_id="s1", domain="residual", content_digest="cd1")
    assert verify_packet(
        pkt.residual, "mem-base-x", 3, c, session_id="s1", domain="residual", content_digest="cd1"
    )
    # 篡改任一字节 → 拦截
    bad = bytearray(pkt.residual)
    bad[0] ^= 0xFF
    assert not verify_packet(
        bytes(bad), "mem-base-x", 3, c, session_id="s1", domain="residual", content_digest="cd1"
    )


def test_l1_domain_binding():
    # 审查修复：payload_kind 进哈希域——同字节同基同代，domain 不同 → 校验失败（防跨档字节复用）
    from synapse.stateplane.checksum import digest_packet

    emb = HashEmbedder(Config().embed_dim)
    _, _, pkt = _pkt(emb, "evidence about beta : beta-fact0", None, generation=7)
    c_res = digest_packet(pkt.residual, "b", 7, "sess", "residual", "cd")
    c_emb = digest_packet(pkt.residual, "b", 7, "sess", "embedding", "cd")
    assert c_res != c_emb


def test_generation_and_session_binding():
    # L1 绑定任务代与会话：跨代/跨会话的陈旧 packet 必失败
    from synapse.stateplane.checksum import digest_packet, verify_packet

    emb = HashEmbedder(Config().embed_dim)
    _, _, pkt = _pkt(emb, "evidence about beta : beta-fact0", None, generation=7)
    c = digest_packet(pkt.residual, "h", 7, session_id="sess-a", domain="residual", content_digest="cd")
    assert verify_packet(pkt.residual, "h", 7, c, session_id="sess-a", domain="residual", content_digest="cd")
    assert not verify_packet(
        pkt.residual, "h", 8, c, session_id="sess-a", domain="residual", content_digest="cd"
    )  # 跨代
    assert not verify_packet(
        pkt.residual, "h", 7, c, session_id="sess-b", domain="residual", content_digest="cd"
    )  # 跨会话


def test_decode_bytes_robustness():
    # 审查修复：畸形帧（非对齐长度 / 越界索引 / 奇数向量字节）→ ValueError 受控回退，不崩溃
    import pytest

    from synapse.stateplane.residual import deserialize_base, quantize_vec, serialize_base

    cfg = Config()
    codec = ResidualCodec(cfg)
    emb = HashEmbedder(cfg.embed_dim)
    base_text = "evidence about alpha : alpha-fact0 alpha-fact1 alpha-fact2"
    text = base_text + " alpha-fact3"
    _, codec2, pkt = _pkt(emb, text, base_text=base_text)
    bq = quantize_vec(emb.encode(base_text), codec.grid)
    # 正常往返（基可为浮点量化或序列化还原，两者等价）
    assert codec.decode_bytes(pkt.residual, bq, pkt.dim) == codec.decode(pkt, emb.encode(base_text))
    assert deserialize_base(serialize_base([0, -64, 127])) == [0, -64, 127]
    # 畸形输入
    with pytest.raises(ValueError):
        codec.decode_bytes(b"\xff\xff\xff", [0] * cfg.embed_dim, cfg.embed_dim)  # 非 stride 对齐
    with pytest.raises(ValueError):
        codec.decode_bytes(b"\x7f\x05", [0] * cfg.embed_dim, cfg.embed_dim)  # idx 0x7f=127 越界(dim=64)
    with pytest.raises(ValueError):  # 高维 2B 索引路径：idx 0xFFFF 越界 (dim=2048)
        codec.decode_bytes(b"\xff\xff\x05", [0] * 2048, 2048)
    with pytest.raises(ValueError):
        deserialize_base(b"\x01")  # 奇数字节
    with pytest.raises(ValueError):
        codec.decode_bytes(b"", [0] * 4, 8)  # 基维度不符


def test_receive_frame_rejects_malformed_frames():
    # GPT 闭环复核 B2/B3：content_digest 为强制不变量（缺失/畸形拒绝）；空 handles 不崩溃；
    # text 帧 L1 未过（错 checksum）拒绝——统一返回 (None, None) 走回退链。
    from synapse.eval.metrics import Metrics
    from synapse.protocol.messages import ActionType, Message
    from synapse.stateplane.checksum import digest_bytes

    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    m = Metrics()
    base_meta = {"generation": 1, "content_digest": "a" * 16, "dim": 4}
    # 缺 content_digest → strict 下身份绑定不变量拒绝
    bad1 = Message("m1", "r", "s", ActionType.TELL.value, handles=("h",),
                   payload_kind="residual", checksum="x", meta={"generation": 1, "dim": 4})
    assert session._receive_frame(bad1, m) == (None, None)
    # content_digest 畸形（长度错/非 str）
    bad2 = Message("m2", "r", "s", ActionType.TELL.value, handles=("h",),
                   payload_kind="residual", checksum="x", meta={"generation": 1, "content_digest": "abc", "dim": 4})
    assert session._receive_frame(bad2, m) == (None, None)
    # 空 handles → 受控 (None, None)，不抛异常
    bad3 = Message("m3", "r", "s", ActionType.TELL.value, handles=(),
                   payload_kind="residual", checksum="x", meta=dict(base_meta))
    assert session._receive_frame(bad3, m) == (None, None)
    # text 帧：正文与 digest 一致但 L1 checksum 错 → 拒绝（生成时未对正文算 L1 的帧不可信）
    text = "hello wire"
    cd = digest_bytes(text.encode("utf-8"))
    bad4 = Message("m4", "r", "s", ActionType.TELL.value, payload_kind="text", text=text,
                   checksum="deadbeefdeadbeef",
                   meta={"generation": 1, "content_digest": cd})
    assert session._receive_frame(bad4, m) == (None, None)
    assert m.recovery_text == 0


def test_legacy_checksum_unchanged():
    # 审查修复（P1-1）：旧路径零影响——encode() 的 pkt.checksum 保持旧口径 digest_ints(量化Y)
    from synapse.stateplane.checksum import digest_ints
    from synapse.stateplane.residual import quantize_vec

    cfg = Config()
    codec = ResidualCodec(cfg)
    emb = HashEmbedder(cfg.embed_dim)
    Y = emb.encode("evidence about alpha : alpha-fact0")
    pkt = codec.encode(Y, emb.encode("evidence about alpha : alpha-fact0 alpha-fact1"))
    assert pkt.checksum == digest_ints(quantize_vec(Y, codec.grid)), (
        "旧路径 Message.checksum 语义不得改变（跨 run 对账依赖）"
    )


def test_cosine_dim_mismatch_raises():
    # 附带修复：zip 静默截断会造出假高相似 → 维度不符必须显式失败
    import pytest

    from synapse.stateplane.embedding import cosine

    with pytest.raises(ValueError):
        cosine([1.0, 2.0], [1.0])


# ---------- 会话级：真通路消费语义（cfg.residual_true_path=True） ----------


def _spy_summarizer(session):
    """记录 summarizer 实际收到的 additional_args（evidence 即其唯一输入来源）。"""
    captured = {}
    orig = session.team.summarizer.run

    def spy(prompt, *a, **kw):  # noqa: ANN001
        captured.update(kw.get("additional_args") or {})
        return orig(prompt, *a, **kw)

    session.team.summarizer.run = spy
    return captured


def _wire_roundtrip(msg):
    """模拟线缆：Message → to_wire() JSON → 反序列化回 Message（接收方只见帧字段）。"""
    from synapse.protocol.messages import Message

    d = json.loads(msg.to_wire())
    d["handles"] = tuple(d.get("handles") or ())
    return Message(**d)


def test_true_path_cold_start_recovers_via_zero_base():
    # 冷启动诚实标 residual_zero 档；零基残差经 L1+L2+身份校验恢复成功，无回退
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.tier_residual_zero == 1, "冷启动应诚实标 residual_zero 档"
    assert m.tier_residual == 0, "零基不得冒充强基 residual 档"
    assert m.recovery_residual == 1, "零基残差应真实恢复文本"
    assert m.fallbacks == 0 and m.fallback_events == 0, "无损坏时不应回退"
    assert m.tier_residual_zero_bytes > 0, "零基残差档字节构成应有真值"
    assert res["final_recovery_ok"] and res["checksum_ok"]
    assert captured.get("evidence"), "summarizer 应收到恢复的 evidence"


def test_receive_frame_driven_by_wire_message():
    # 审查修复（P0-5）：接收方仅凭线缆帧字段驱动——to_wire 反序列化后的 Message 也能恢复
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    spy = {}
    orig = session._receive_frame

    def spy_receive(frame, m):
        wire = _wire_roundtrip(frame)  # 只经帧字段（handles/checksum/meta），无闭包变量
        spy["wire"] = True
        return orig(wire, m)

    session._receive_frame = spy_receive
    res = session.run_task(T.g1_family(1)[0])
    assert spy.get("wire") and res["metrics"].recovery_residual == 1


def test_reconstruction_is_consumed():
    # R-P0-1 核心断言：重建→检索→恢复的文本被真实消费。索引被破坏（返回空）时
    # 必须回退而非静默沿用旁路全文；旁路路径（直读全文）下 fallbacks 恒 0，必红。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    session.vec_index.search = lambda v, k=1: []  # 索引失效：无候选可恢复
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.recovery_residual == 0 and m.recovery_embedding == 0, "索引失效时非文本路径不得恢复"
    assert m.recovery_text == 1 and m.fallback_events == 1, "必须走 text 回退通道"
    assert captured.get("evidence"), "回退通道须仍能供出 evidence"
    assert res["final_recovery_ok"] and not res["checksum_ok"]


def test_near_miss_decoy_rejected_by_identity():
    # 审查修复（P1-1/GPT P0-3）：索引近邻错配（decoy 更相似）不得静默消费——
    # content_digest 身份校验拦截并回退；"恢复"必须是发送方声明的内容本身。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    decoy = session.cas.put("decoy text that never appeared on wire".encode("utf-8"))
    session.vec_index.search = lambda v, k=1: [(decoy, 1.0)]  # 注：decoy 恒胜出（无死分支）
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert captured.get("evidence") != "decoy text that never appeared on wire", (
        "身份校验必须拒绝与帧 content_digest 不符的候选"
    )
    assert m.recovery_text >= 1, "拒绝后应走 text 回退"
    assert not res["checksum_ok"]


def test_broken_reconstruction_switches_to_fallback():
    # "删重建逻辑答案必须变化"的路径级断言：重建被破坏 → 检索失配 → 回退通道接管。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    orig = session.codec.decode_bytes

    def broken(residual, bq_recv, dim):  # noqa: ANN001
        return [999] * dim  # 垃圾重构：与任何 hash 向量都近乎正交

    session.codec.decode_bytes = broken
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.recovery_residual == 0, "重建被破坏时残差路径不得计为恢复成功"
    assert m.fallback_events >= 1 and m.fallbacks >= 1, "重建失配必须触发回退（旧旁路静默）"
    assert captured.get("evidence") and res["final_recovery_ok"]
    session.codec.decode_bytes = orig


def test_tamper_in_session_intercepted():
    # 会话级"篡改 residual 字节 checksum 必须拦截"：信道翻转 residual 首字节，
    # checksum 保持发送方原值 → L1 拦截 → 回退（旧路径余弦校验实测放行，必红）。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    orig_encode = session.codec.encode

    def evil_encode(Y, b_hat, base_handle=None, generation=0):  # noqa: ANN001
        pkt = orig_encode(Y, b_hat, base_handle, generation)
        r = bytearray(pkt.residual)
        if r:
            r[0] ^= 0xFF  # 信道篡改；帧 checksum 仍是发送方对原字节算的值
        return dataclasses.replace(pkt, residual=bytes(r))

    session.codec.encode = evil_encode
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.recovery_residual == 0, "被篡改的残差不得进入消费"
    assert m.fallback_events >= 1, "L1 完整性校验必须拦截并回退"
    assert res["final_recovery_ok"], "回退链须保证端到端仍成功"


def test_tampered_fallback_embedding_frame_degrades_to_text():
    # 审查修复（P0-4/GPT P0-4）：回退跳 1 的补发 embedding 帧被篡改 → 该跳也须拦截 → 降到 text。
    # 补发帧同样经 _receive_frame 消费（不复用发送方本地 Y_q），篡改必须可见。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    real_store = session.cas._store
    seen = {"vec": None}
    orig_put = session.cas.put

    def evil_put(data: bytes) -> str:
        h = orig_put(data)
        if len(data) == cfg.embed_dim * 2 and seen["vec"] is None:
            seen["vec"] = h  # 首个进 CAS 的全量向量（即回退跳 1 的补发帧 payload）
        return h

    session.cas.put = evil_put
    # 先破坏首轮残差（触发回退），再让补发的 embedding 帧字节损坏
    orig_encode = session.codec.encode

    def evil_encode(Y, b_hat, base_handle=None, generation=0):  # noqa: ANN001
        pkt = orig_encode(Y, b_hat, base_handle, generation)
        r = bytearray(pkt.residual)
        if r:
            r[0] ^= 0xFF
        return dataclasses.replace(pkt, residual=bytes(r))

    session.codec.encode = evil_encode
    orig_get = session.cas.get

    def evil_get(handle):
        data = real_store.get(handle)
        if handle == seen.get("vec") and data:
            return bytes([data[0] ^ 0xFF]) + data[1:]  # 信道损坏补发帧
        return orig_get(handle)

    session.cas.get = evil_get
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.fallback_events == 1, "首帧残差被篡改 → 1 次回退事件"
    assert m.recovery_embedding == 0, "补发 embedding 帧损坏时该跳不得恢复"
    assert m.recovery_text >= 1, "必须降到 text 档（而非凭发送方本地 Y_q 恢复）"
    assert res["final_recovery_ok"]
    session.cas.get = orig_get


def test_no_residual_ablation_sends_full_vector():
    # R-P0-3：消融=真发全量量化向量 packet（embedding 帧），字节为真实线缆载荷，
    # 不得再出现 residual 帧改账。
    cfg = Config(residual_true_path=True, abl_no_residual=True)
    session = SynapseSession(cfg)
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.tier_embedding == 1
    assert m.recovery_embedding == 1, "全量向量应经索引真实恢复文本"
    assert m.tier_embedding_bytes == m.nontext_bytes, "消融字节=真实向量 packet（非改账）"
    assert m.nontext_bytes == cfg.embed_dim * 2 + 12, "int16 全量向量 + 头(4B) + 校验(8B)"


def test_rate_distortion_keeps_residual_cheaper_than_full_vector():
    # 审查修复（signal FAIL 根因）：弱基不再无条件发全量向量——率失真选档。
    # dim≤256 时 1B 索引使残差结构性不劣于全量（nnz×2B ≤ dim×2B），极端失配基也应选 residual；
    # 更高维（2B 索引）残差超全量时自动换 embedding 档（见 _true_path_transfer 率失真分支）。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    # 写入一条与 evidence 弱相关的真实记忆（mem_id 可被接收方同源解析，避免 desync 回退）
    weak_unit = session.store.write(
        source_agent="fake",
        task_topic="alpha",
        summary="weak base",
        content="zzz qqq xxx yyy wvv unrelated filler tokens",
        kind="strategy",
    )
    orig_best = session.tom.best_base
    session.tom.best_base = lambda results, target: (weak_unit.embedding, weak_unit.mem_id, 0.01)
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.tier_residual == 1, "弱基但残差仍更省时应走 residual 档（率失真，非无条件全量）"
    assert m.nontext_bytes <= cfg.embed_dim * 2 + 12, "真通路单帧字节不得劣于全量向量（signal 根因回归锁）"
    assert m.recovery_residual == 1, "弱基残差路径应可恢复"
    session.tom.best_base = orig_best


def test_cnr_text_negotiation_sends_real_text_frame():
    # 审查修复（P1-2）：negotiate 返回 "text" → 必须真发 text 帧（无向量载荷），
    # 且三套口径一致（tier_text=1、nontext=0、recovery_text=1）。
    from synapse.protocol.handshake import CNR

    calls = {"n": 0}
    orig = CNR.negotiate

    def fake(self, sender_id, receiver_id):  # noqa: ANN001
        calls["n"] += 1
        return "text"

    CNR.negotiate = fake
    try:
        cfg = Config(residual_true_path=True)
        session = SynapseSession(cfg)
        res = session.run_task(T.g1_family(1)[0])
        m = res["metrics"]
        assert calls["n"] >= 1
        assert m.tier_text == 1, "协商为 text 时应走真 text 档"
        assert m.nontext_bytes == 0, "text 档不得携带向量载荷（口径恒等式）"
        assert m.recovery_text == 1 and res["final_recovery_ok"]
    finally:
        CNR.negotiate = orig


def test_missing_base_in_receiver_memory_falls_back():
    # 审查修复（P0-4）：接收方按 mem_id 从自身记忆解析基——记忆缺失时受控回退，不崩溃。
    # 首轮零基（base_ref=""）不经记忆解析，故用第二轮强基帧验证。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    session.run_task(T.g1_family(2)[0])  # 第一轮建立记忆
    orig_get = session.store.get
    session.store.get = lambda mem_id: None  # 接收方记忆查无此基
    res = session.run_task(T.g1_family(2)[1])  # 第二轮强基 residual 帧 → 基解析失败
    m = res["metrics"]
    assert m.recovery_residual == 0, "基缺失时残差路径不得恢复"
    assert m.fallback_events >= 1 and res["final_recovery_ok"], "应回退且端到端成功"
    session.store.get = orig_get


def test_cnr_negotiate_drives_tier():
    # R-P0-4：negotiate() 必须真实调用并驱动选档——协商结果 embedding 时强基也被降档
    from synapse.protocol.handshake import CNR

    calls = {"n": 0}
    orig = CNR.negotiate

    def fake(self, sender_id, receiver_id):  # noqa: ANN001
        calls["n"] += 1
        return "embedding"

    CNR.negotiate = fake
    try:
        cfg = Config(residual_true_path=True)
        session = SynapseSession(cfg)
        m = None
        for task in T.g1_family(3):
            m = session.run_task(task)["metrics"]
        assert calls["n"] >= 3, "每轮发送前都应协商"
        assert m.tier_residual + m.tier_residual_zero == 0, "协商为 embedding 时不得走 residual 档"
    finally:
        CNR.negotiate = orig


def test_cold_start_then_warm_upgrades_tier():
    # 收缩叙事（诚实版）：首轮 residual_zero → 有记忆后强基升级 residual 档
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    m1 = session.run_task(T.g1_family(2)[0])["metrics"]
    m2 = session.run_task(T.g1_family(2)[1])["metrics"]
    assert m1.tier_residual_zero == 1
    assert m2.tier_residual == 1, "同族任务第二轮应以强基走 residual 档"
    assert m2.tier_residual_bytes <= m1.tier_residual_zero_bytes, "强基残差字节应不劣于零基（收缩方向不变）"


def test_no_memory_ablation_resets_recovery_surface():
    # 审查修复（P2-4）：no-memory 消融须同步重置 VectorIndex——每任务前清空，不残留悬空句柄
    cfg = Config(residual_true_path=True, abl_no_memory=True)
    session = SynapseSession(cfg)
    res1 = session.run_task(T.g1_family(1)[0])
    res2 = session.run_task(T.g1_family(1)[0])
    assert res1["final_recovery_ok"] and res2["final_recovery_ok"]
    # 每任务清空后仅含本轮 put 的条目（若未清空会跨任务累积）
    assert len(session.vec_index) == 1, "no-memory 消融下恢复面应每任务重置（防悬空句柄）"
    assert res2["metrics"].fallback_events == 0, "第二轮不应因首轮残留句柄污染口径"
