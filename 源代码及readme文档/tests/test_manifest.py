"""V3-02 双层计量对账测试（Issue 148752 验收恒等式）。

覆盖：
- 字节双口径恒等式：transport == Σ len(to_wire())；logical == Σ(header+text+nontext)
- 聚合守恒：aggregate 全字段 == Σ trajectory（合成 AB 聚合漏加 llm_input/output_tokens 的回归）
- usage 缺失 fail（真实后端禁止静默计 0）
- config fail-fast（P1-6：YAML 异常/未知键/缺文件 → ConfigError，不回默认）
- embedding cold/warm 分列（cache hit 不产生 API 请求）
- CAS 写入计数
- 落档 schema 校验（manifest 三层结构合法）
- hotpot/musique 逐题层（qid/预测/金标/F1，R-P0-11）

平面级测试纯 stdlib；模式级经 smolagents 基座，在 .venv 跑：uv run pytest
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from synapse.config import Config, ConfigError  # noqa: E402
from synapse.protocol.messages import Message, ActionType  # noqa: E402
from synapse.eval.metrics import Metrics  # noqa: E402
from synapse.eval.harness import ABRunner  # noqa: E402
from synapse.eval.schema import validate_run_result  # noqa: E402
from synapse.eval.manifest import write_run, dataset_info  # noqa: E402
from synapse.stateplane.cas import CAS  # noqa: E402
from synapse.stateplane.embedding import HashEmbedder, ApiEmbedder  # noqa: E402
from synapse.runtime.model import require_token_usage  # noqa: E402
from synapse.qa.pipeline import run_text_hotpot, run_synapse_hotpot  # noqa: E402
from synapse.qa.dataset import HotpotItem, Paragraph  # noqa: E402
from synapse import tasks as T  # noqa: E402


def _msgs():
    """一组覆盖各载荷形态的消息（text / residual 句柄 / 带 meta / 带 result）。"""
    return [
        Message("m1", "a", "b", ActionType.TELL.value, payload_kind="text", text="hello synapse 协议字节"),
        Message(
            "m2",
            "b",
            "c",
            ActionType.TELL.value,
            handles=("h1", "h2"),
            payload_kind="residual",
            checksum="ab12",
            meta={"nontext_bytes": 88, "nnz": 5, "tier": "residual"},
        ),
        Message("m3", "c", "d", ActionType.EXECUTE.value, result={"metric": 42}, params={"k": 1}),
    ]


def test_transport_bytes_identity():
    # 恒等式一：transport_bytes == Σ len(to_wire()) —— 对真实序列化帧长计数，非手工相加代理值
    m = Metrics()
    msgs = _msgs()
    for msg in msgs:
        m.record_message(msg)
    assert m.transport_bytes == sum(len(msg.to_wire().encode("utf-8")) for msg in msgs)


def test_logical_bytes_identity():
    # 恒等式二：logical_bytes == Σ(header_bytes + text_bytes + nontext_bytes)
    m = Metrics()
    msgs = _msgs()
    for msg in msgs:
        m.record_message(msg)
    assert m.logical_bytes == sum(
        msg.header_bytes() + msg.text_bytes() + msg.meta.get("nontext_bytes", 0) for msg in msgs
    )
    assert m.wire_bytes == m.logical_bytes  # 向后兼容别名


def test_transport_ge_logical():
    # to_wire() 含 capability/meta/text 等全部字段 → 传输口径 ≥ 逻辑口径（分离才有意义）
    m = Metrics()
    for msg in _msgs():
        m.record_message(msg)
    assert m.transport_bytes >= m.logical_bytes


def test_agg_conservation_all_fields():
    # 聚合守恒：synapse_total == Σ trajectory 全字段（回归：旧 _agg 漏加 llm_input/output_tokens → 0.0）
    res = ABRunner(Config()).run(T.linked_continuous(3, 3))
    total = res["synapse_total"]
    for f in (
        "messages",
        "llm_input_tokens",
        "llm_output_tokens",
        "transport_bytes",
        "header_bytes",
        "text_bytes",
        "nontext_bytes",
        "embed_requests",
        "embed_cache_hits",
        "cas_writes",
        "cas_write_bytes",
    ):
        assert total[f] == sum(t[f] for t in res["synapse_trajectory"]), f"聚合守恒破坏: {f}"
    # mock 近似 token 也必须累加非零（旧 bug：合成 AB 实跑 0.0）
    assert total["llm_input_tokens"] > 0 and total["llm_output_tokens"] > 0
    assert res["text_total"]["llm_input_tokens"] > 0


def test_metrics_absorb_conservation():
    a, b = Metrics(mode="a"), Metrics(mode="b")
    a.messages, a.llm_input_tokens, a.transport_bytes, a.quality = 2, 100, 500, 0.5
    b.messages, b.llm_input_tokens, b.transport_bytes, b.quality = 3, 50, 700, 1.0
    a.absorb(b)
    assert (a.messages, a.llm_input_tokens, a.transport_bytes, a.quality) == (5, 150, 1200, 1.5)


def test_usage_missing_fails():
    # 真实后端响应缺 token_usage → 显式 fail（禁止静默计 0 污染计量）
    try:
        require_token_usage(SimpleNamespace(token_usage=None))
        raise AssertionError("usage 缺失应 raise")
    except RuntimeError as e:
        assert "token_usage" in str(e)


def test_config_fail_fast(tmp_path):
    # P1-6：YAML 语法错 / 未知键 / 文件不存在 / 类型错 → ConfigError，绝不静默回默认
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("llm_backend: [unclosed", encoding="utf-8")
    for path, content in [
        (bad_yaml, None),
        (tmp_path / "unknown.yaml", "not_a_field: 1\n"),
        (tmp_path / "missing.yaml", None),
        (tmp_path / "typeerr.yaml", "rounds: not_a_number\n"),
    ]:
        if content is not None:
            path.write_text(content, encoding="utf-8")
        try:
            from synapse.config import load_config

            load_config(str(path))
            raise AssertionError(f"应 ConfigError: {path}")
        except ConfigError:
            pass
    # 合法配置不受影响
    good = tmp_path / "good.yaml"
    good.write_text("llm_backend: paratera\nrounds: 7\n", encoding="utf-8")
    from synapse.config import load_config

    cfg = load_config(str(good))
    assert cfg.llm_backend == "paratera" and cfg.rounds == 7


def test_hash_embedder_request_counter():
    emb = HashEmbedder(64)
    assert emb.requests == 0
    emb.encode("alpha beta")
    emb.encode("gamma")
    assert emb.requests == 2  # 离线路径同样计数（口径可比）


def test_api_embedder_cold_warm_split():
    # cold（真实 API 请求）与 warm（缓存命中）分列：命中不产生请求、usage 只在请求时累计
    emb = ApiEmbedder.__new__(ApiEmbedder)  # 绕过 __init__（免 openai import）
    emb._cache = {}
    emb.requests = emb.cache_hits = emb.input_tokens = 0
    emb.dim = 0
    emb._model = "test-embed"

    class _Resp:
        data = [SimpleNamespace(embedding=[0.1, 0.2])]
        usage = SimpleNamespace(prompt_tokens=7)

    emb._client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda model, input: _Resp()))
    emb.encode("same text")
    emb.encode("same text")  # 第二次 = cache hit
    emb.encode("other text")
    assert emb.requests == 2 and emb.cache_hits == 1 and emb.input_tokens == 14


def test_cas_write_counters():
    cas = CAS()
    cas.put(b"abc")
    cas.put(b"defgh")
    assert cas.writes == 2 and cas.write_bytes == 8


def test_write_run_schema_valid(tmp_path):
    # 落档即过 schema：三层结构（manifest/聚合/可选逐题）完整
    cfg = Config()
    res = ABRunner(cfg).run(T.linked_continuous(2, 2))
    out_dir = write_run(
        "test_ab",
        cfg,
        res,
        command="ab --rounds 2",
        dataset=dataset_info("data/x.json", 2),
        root=str(tmp_path),
    )
    doc = __import__("json").load(open(os.path.join(out_dir, "result.json"), encoding="utf-8"))
    assert validate_run_result(doc) == []
    assert doc["manifest"]["code_sha"]  # git 仓库内执行时应锚定 code SHA
    assert (
        doc["result"]["synapse_total"]["transport_bytes"] >= doc["result"]["synapse_total"]["logical_bytes"]
    )
    # 兼容层：旧读取方（plot_* 脚本）依赖的顶层 config/result 键仍在
    assert "config" in doc and "result" in doc


def test_schema_rejects_broken_doc():
    assert validate_run_result({"result": {}})  # 缺顶层键 → 报错
    assert validate_run_result(
        {
            "schema_version": "1.0.0",
            "config": {},
            "manifest": {
                "command": "x",
                "started_utc": "t",
                "schema_version": "1.0.0",
                "config": {"model": "m", "temperature": 0},
                "env": {"os": "o", "python": "p"},
            },
            "result": {"text": {"messages": 1}},
        }
    )  # metrics 缺 V3-02 计量字段 → 报错
    assert (
        validate_run_result(
            {
                "schema_version": "1.0.0",
                "config": {},
                "manifest": {
                    "command": "probe",
                    "started_utc": "t",
                    "schema_version": "1.0.0",
                    "config": {"model": "m", "temperature": 0},
                    "env": {"os": "o", "python": "p"},
                },
                "result": {"status": "error", "raw_error": "..."},
            }
        )
        == []
    )  # 失败 run 豁免


def test_hotpot_per_item_layer():
    # R-P0-11：逐题层有 qid/问题/双模式预测/金标/F1/检索段（离线 mock，结构对账非数值）
    items = [
        HotpotItem(
            qid="q1",
            q="Who wrote X?",
            answer="Alice",
            paragraphs=[Paragraph(f"P{i}", f"fact {i} about Alice and Bob") for i in range(4)],
            gold_titles=("P0", "P1"),
            level="bridge",
        ),
        HotpotItem(
            qid="q2",
            q="What is Y?",
            answer="yes",
            paragraphs=[Paragraph(f"Q{i}", f"fact {i} about Carol") for i in range(4)],
            gold_titles=("Q0",),
            level="comparison",
        ),
    ]
    cfg = Config()
    rt = run_text_hotpot(items, cfg)
    rs = run_synapse_hotpot(items, cfg)
    for rec in rt["per_item"]:
        assert rec["qid"] and rec["gold"] is not None and "pred" in rec and "f1" in rec
    for rec in rs["per_item"]:
        assert {
            "qid",
            "question",
            "gold",
            "pred",
            "f1",
            "retrieved_titles",
            "gold_titles",
            "gold_hit",
        } <= set(rec)
    # synapse 模式：CAS 写入与嵌入计数 > 0（cold 成本已分列计量）
    assert rs["metrics"].cas_writes > 0 and rs["metrics"].embed_requests > 0
    assert rs["metrics"].transport_bytes > 0


def test_synapse_mode_embed_cas_deltas():
    # 合成会话：单任务内 embed/CAS 为增量计数（多任务累计但非全局快照）
    from synapse.modes.synapse_mode import SynapseSession

    s = SynapseSession(Config())
    r1 = s.run_task(T.g1_family(1)[0])
    r2 = s.run_task(T.g1_family(1)[0])
    assert r1["metrics"].embed_requests > 0 and r1["metrics"].cas_writes > 0
    assert r2["metrics"].cas_writes > 0


if __name__ == "__main__":
    import tempfile

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    with tempfile.TemporaryDirectory() as td:
        for fn in fns:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                from pathlib import Path

                fn(Path(td))
            else:
                fn()
            print(f"PASS {fn.__name__}")
    print(f"ALL {len(fns)} TESTS PASSED")
