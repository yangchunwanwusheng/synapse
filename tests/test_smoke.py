"""Smoke / 单元测试。

- 平面级测试（residual/memory）纯 stdlib 可跑。
- 模式级测试（dual mode / 字节下降 / 负例区分）经 smolagents 基座，需在 .venv 跑：
    uv run pytest    或    uv run python tests/test_smoke.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from synapse.config import Config  # noqa: E402
from synapse.stateplane.residual import ResidualCodec  # noqa: E402
from synapse.stateplane.embedding import HashEmbedder  # noqa: E402
from synapse.memory.store import MemoryStore  # noqa: E402
from synapse.modes.text_mode import run_text  # noqa: E402
from synapse.modes.synapse_mode import SynapseSession  # noqa: E402
from synapse.eval.harness import ABRunner  # noqa: E402
from synapse import tasks as T  # noqa: E402


def test_residual_roundtrip_pass():
    cfg = Config()
    codec = ResidualCodec(cfg)
    emb = HashEmbedder(cfg.embed_dim)
    Y = emb.encode("evidence about alpha facts details")
    pkt = codec.encode(Y, Y)  # 完美预测基 → 残差为 0（cos=1≥阈值，立即达标）
    assert pkt.nnz == 0
    yq_hat = codec.decode(pkt, Y)
    assert codec.verify(yq_hat, Y) is True


def test_residual_verify_fail_triggers_fallback():
    # 接收方预测基失配（desync）→ 重构与真值 cos 低于阈值 → 校验失败 → 回退取全量文本
    cfg = Config()
    codec = ResidualCodec(cfg)
    emb = HashEmbedder(cfg.embed_dim)
    Y = emb.encode("alpha beta gamma evidence facts details")
    bad = emb.encode("completely unrelated zzz qqq xyz nope")  # 失配的预测基
    pkt = codec.encode(Y, Y)  # 发送方用好基编码
    yq_hat = codec.decode(pkt, bad)  # 接收方用错基重构
    assert codec.verify(yq_hat, Y) is False


def test_residual_highdim_2byte_index_roundtrip():
    # 真实句向量为 2048 维 → 稀疏索引需 2 字节；验证高维 round-trip + 收缩仍成立（dim>256 回归）
    cfg = Config()
    codec = ResidualCodec(cfg)
    Y = [((i % 7) - 3) / 10.0 for i in range(2048)]  # 确定性、含 index>256 的非零分量
    warm = codec.encode(Y, Y)  # 完美预测基 → 0 残差
    cold = codec.encode(Y, None)  # 无基 → 发多分量（含 index>255 → 走 2 字节索引）
    assert warm.nnz == 0 and cold.nnz > 0 and cold.dim == 2048
    yq_hat = codec.decode(cold, None)  # 2 字节索引解码须精确还原编码器承诺的 Ŷ
    assert codec.verify(yq_hat, Y) is True
    assert warm.nnz < cold.nnz  # 收缩：预测基越准 → nnz 越小


def test_codeact_executor_runs_offline():
    # M11：执行器是 smolagents CodeAgent，真·执行注入数据上的代码（离线 mock）
    from synapse.runtime.team import build_team

    team = build_team(Config())
    team.bind_topic("alpha")
    out = team.executor.run("count words", reset=True, additional_args={"evidence": "a b c d e"})
    assert out == 5  # len("a b c d e".split())


def test_normalize_codeact_repairs_flaky_output():
    # 根因修复：Qwen3-Instruct 偶发 bare final_answer(...)</code>；smolagents 对未以 </code> 结尾的输出
    # 会回补停止标签 → 变 code</code>（缺开标签）→ parse_code_blobs 需配对 → 烧光步数。修法=补成 <code>..</code> 配对。
    from smolagents.utils import parse_code_blobs

    from synapse.runtime.model import normalize_codeact

    tags = ("<code>", "</code>")
    # 观测到的畸形输出 → 修复后经 smolagents 真解析得到可执行代码
    assert parse_code_blobs(
        normalize_codeact("final_answer(len(evidence.split()))</code>"), tags
    ).strip() == ("final_answer(len(evidence.split()))")
    # 含散文前缀时抽取出 balanced final_answer(...) 调用
    prose = "Thought: I will count.\nfinal_answer(len(evidence.split()))<end_code>"
    assert parse_code_blobs(normalize_codeact(prose), tags).strip() == "final_answer(len(evidence.split()))"

    # 成功路（已 fenced / 纯文本 QA 答案）一律不动
    fenced = "Thought: ok.\n```py\nfinal_answer(3)\n```<end_code>"
    assert normalize_codeact(fenced) == fenced
    assert normalize_codeact("Shirley Temple") == "Shirley Temple"
    assert normalize_codeact("yes") == "yes"


def test_codeact_recovers_from_malformed_output_end_to_end():
    # 端到端复现（修复前 Reached max steps 返回非 5）：CodeAgent 经 normalize 后真执行得 5
    from smolagents import CodeAgent
    from smolagents.models import ChatMessage, Model

    from synapse.runtime.model import normalize_codeact

    class FakeMalformed(Model):
        def generate(self, messages, stop_sequences=None, **kw):  # noqa: ANN001
            return ChatMessage(
                role="assistant", content=normalize_codeact("final_answer(len(evidence.split()))</code>")
            )

    ag = CodeAgent(tools=[], model=FakeMalformed(), max_steps=2, verbosity_level=0, add_base_tools=False)
    assert ag.run("count", additional_args={"evidence": "a b c d e"}) == 5


def test_memory_write_mutation_effect():
    # LESSONS L3：变更生效验证——write 后 store 真有 diff
    store = MemoryStore(HashEmbedder(Config().embed_dim))
    n0 = len(store)
    u = store.write(source_agent="r", task_topic="alpha", summary="s", content="c1", kind="evidence")
    assert len(store) == n0 + 1
    assert u.mem_id and u.created_at and u.source_agent == "r"  # M5 元数据齐全
    assert u.embedding is not None


def test_dual_mode_runs():
    cfg = Config()
    task = T.g1_family(1)[0]
    t = run_text(task, cfg)
    s = SynapseSession(cfg).run_task(task)
    assert t["conclusion"] and s["conclusion"]
    assert t["metrics"].messages > 0 and s["metrics"].messages > 0


def test_synapse_saves_wire_bytes():
    res = ABRunner(Config()).run(T.linked_continuous(3, 3))
    assert res["improvement"]["wire_bytes_saved_pct"] > 0


def test_contraction_and_memory_reuse():
    res = ABRunner(Config()).run(T.g1_family(4))
    traj = res["contraction_bytes"]
    assert traj[-1] <= traj[0]  # 非文本字节随经验下降
    assert res["improvement"]["synapse_hit_rate"] > 0  # 跨任务复用


def test_negative_control_low_reuse():
    # 区分度——负例（无共享结构）命中率应低于关联任务
    linked = ABRunner(Config()).run(T.linked_continuous(3, 3))
    negative = ABRunner(Config()).run(T.negative_family(6))
    assert negative["improvement"]["synapse_hit_rate"] < linked["improvement"]["synapse_hit_rate"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"ALL {len(fns)} TESTS PASSED")
