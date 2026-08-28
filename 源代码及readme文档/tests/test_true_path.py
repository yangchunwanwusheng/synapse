"""V3-04 残差/VLC 真数据通路测试（Issue #148746，红→绿过程见 commit 历史）。

对应设计：docs/design/v3-04-true-path.md（前置设计冻结 2026-08-28）

覆盖的 Issue 验收点：
- "篡改 residual 字节 checksum 必须拦截"（R-P0-2：L1 完整性校验，接收方可复算）
- "删重建逻辑答案必须变化"（R-P0-1：重建结果成为 summarizer 唯一输入，e2e 无旁路）
- no-residual 消融走独立 full-vector 真路径而非改账（R-P0-3）
- 三档真实分叉 + CNR negotiate() 驱动选档 + 冷启动诚实标档（R-P0-4）

注：新机制由 cfg.residual_true_path 门控（默认 False=旧旁路路径，回归防护）。
"""

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


def _pkt(emb, text, base_text=None, generation=3, handle="base-handle-x"):
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
    assert pkt.checksum == digest_packet(pkt.residual, "base-handle-x", 3)
    # 完好字节通过
    assert verify_packet(pkt.residual, "base-handle-x", 3, pkt.checksum) is True
    # 篡改任一字节 → 拦截
    bad = bytearray(pkt.residual)
    bad[0] ^= 0xFF
    assert verify_packet(bytes(bad), "base-handle-x", 3, pkt.checksum) is False


def test_generation_replay_rejected():
    # L1 绑定 generation：同 residual + 同 base_handle 在不同任务代必失败（防重放）
    from synapse.stateplane.checksum import verify_packet

    emb = HashEmbedder(Config().embed_dim)
    _, _, pkt = _pkt(emb, "evidence about beta : beta-fact0", None, generation=7)
    assert verify_packet(pkt.residual, "base-handle-x", 7, pkt.checksum) is True
    assert verify_packet(pkt.residual, "base-handle-x", 8, pkt.checksum) is False


def test_decode_bytes_from_serialized_base():
    # 接收方只凭句柄可见内容（residual 字节 + 序列化量化基）即可重构，不依赖发送方 B_hat 对象
    from synapse.stateplane.residual import quantize_vec, serialize_base, deserialize_base

    emb = HashEmbedder(Config().embed_dim)
    base_text = "evidence about alpha : alpha-fact0 alpha-fact1 alpha-fact2"
    text = base_text + " alpha-fact3"
    cfg, codec, pkt = _pkt(emb, text, base_text=base_text)
    bq_wire = serialize_base(quantize_vec(emb.encode(base_text)))  # 线缆侧基 = int16 字节
    assert pkt.base_handle == "base-handle-x"
    yq_wire = codec.decode_bytes(pkt.residual, deserialize_base(bq_wire), pkt.dim)
    yq_ref = codec.decode(pkt, emb.encode(base_text))  # 旧接口（内部量化）
    assert yq_wire == yq_ref, "字节接口重构须与对象接口一致"
    assert deserialize_base(serialize_base([0, -64, 127])) == [0, -64, 127]


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


def test_true_path_cold_start_recovers_via_zero_base():
    # 冷启动诚实标 residual_zero 档；零基残差经 L1+L2 恢复成功，无回退
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.tier_residual_zero == 1, "冷启动应诚实标 residual_zero 档"
    assert m.tier_residual == 0, "零基不得冒充强基 residual 档"
    assert m.recovery_residual == 1, "零基残差应真实恢复文本"
    assert m.fallbacks == 0, "无损坏时不应回退"
    assert m.tier_residual_bytes > 0, "残差档字节构成应有真值"
    assert captured.get("evidence"), "summarizer 应收到恢复的 evidence"


def test_reconstruction_is_consumed():
    # R-P0-1 核心断言：重建→检索→恢复的文本被真实消费。索引返回干扰项时
    # summarizer 输入随之变化——旁路路径（直读全文）下该输入恒为原文，必红。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    decoy = cas_decoy = session.cas.put("decoy text that never appeared on wire".encode("utf-8"))
    orig_search = session.vec_index.search
    session.vec_index.search = lambda v, k=1: [(decoy, 1.0)] or orig_search(v, k)
    session.run_task(T.g1_family(1)[0])
    assert captured.get("evidence") == "decoy text that never appeared on wire", (
        "summarizer 输入必须来自重建检索结果（真通路），而非 CAS 全文旁路"
    )


def test_broken_reconstruction_switches_to_fallback():
    # "删重建逻辑答案必须变化"的路径级断言：重建被破坏 → 检索失配 → 回退通道接管，
    # 而非静默沿用旁路全文（旁路路径下 fallbacks 恒 0，必红）。
    cfg = Config(residual_true_path=True)
    session = SynapseSession(cfg)
    captured = _spy_summarizer(session)
    orig = session.codec.decode_bytes

    def broken(residual, bq_recv, dim):  # noqa: ANN001
        return [999.0] * dim  # 垃圾重构：与任何 hash 向量都近乎正交

    session.codec.decode_bytes = broken
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.recovery_residual == 0, "重建被破坏时残差路径不得计为恢复成功"
    assert m.fallbacks >= 1, "重建失配必须触发回退（旧旁路静默）"
    assert captured.get("evidence"), "回退通道须仍能供出 evidence"
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
            r[0] ^= 0xFF  # 信道篡改；pkt.checksum 仍是发送方对原字节算的值
        return dataclasses.replace(pkt, residual=bytes(r))

    session.codec.encode = evil_encode
    res = session.run_task(T.g1_family(1)[0])
    m = res["metrics"]
    assert m.recovery_residual == 0, "被篡改的残差不得进入消费"
    assert m.fallbacks >= 1, "L1 完整性校验必须拦截并回退"


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
    assert m2.tier_residual_bytes <= m1.tier_residual_zero_bytes + m1.tier_residual_bytes, (
        "强基残差字节应不劣于零基（收缩方向不变）"
    )
