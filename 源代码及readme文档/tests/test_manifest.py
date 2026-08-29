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

import json
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
    # 注意：transport 与 logical 无大小恒等式——to_wire() 帧只含 CAS 句柄而 logical 计入
    # 残差 payload 全量（真实 API 路径实测 transport < logical），两口径各自独立守恒即可。


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
    # 真实后端响应缺 token_usage / usage 壳但字段不可用 → 全部显式 fail（审查 P0-3）
    bad_msgs = [
        SimpleNamespace(token_usage=None),  # 整个 usage 缺失
        SimpleNamespace(token_usage=object()),  # 有壳无字段
        SimpleNamespace(token_usage=SimpleNamespace(input_tokens=3)),  # 缺 output_tokens
        SimpleNamespace(token_usage=SimpleNamespace(input_tokens=None, output_tokens=5)),  # 字段 None
        SimpleNamespace(token_usage=SimpleNamespace(input_tokens=True, output_tokens=5)),  # bool 冒充 int
        SimpleNamespace(token_usage=SimpleNamespace(input_tokens=-1, output_tokens=5)),  # 负数
        SimpleNamespace(token_usage=SimpleNamespace(input_tokens="15", output_tokens="5")),  # 字符串
    ]
    for msg in bad_msgs:
        try:
            require_token_usage(msg)
            raise AssertionError(f"不可用 usage 应 raise: {msg.token_usage!r}")
        except RuntimeError:
            pass
    # 完整合法 usage 正常通过
    ok = SimpleNamespace(token_usage=SimpleNamespace(input_tokens=15, output_tokens=3))
    assert require_token_usage(ok) is ok.token_usage


def test_config_fail_fast(tmp_path):
    # P1-6：YAML 语法错 / 未知键 / 文件不存在 / 类型错 / null / bool 冒充 / 坏 seed 元素 /
    # 目录当配置 → 全部 ConfigError，绝不静默回默认（审查 P0-2 扩充）
    from synapse.config import load_config

    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("llm_backend: [unclosed", encoding="utf-8")
    cases = [
        (bad_yaml, None),
        (tmp_path / "unknown.yaml", "not_a_field: 1\n"),
        (tmp_path / "missing.yaml", None),
        (tmp_path / "typeerr.yaml", "rounds: not_a_number\n"),
        (tmp_path / "null.yaml", "rounds: null\n"),
        (tmp_path / "boolint.yaml", "rounds: true\n"),
        (tmp_path / "seednull.yaml", "seeds: null\n"),
        (tmp_path / "seedbad.yaml", 'seeds: [1, "x"]\n'),
        (tmp_path / "dir.yaml", None),  # 目录而非文件
    ]
    for path, content in cases:
        if content is not None:
            path.write_text(content, encoding="utf-8")
        elif path.name == "dir.yaml":
            path.mkdir(exist_ok=True)
        try:
            load_config(str(path))
            raise AssertionError(f"应 ConfigError: {path}")
        except ConfigError:
            pass
    # 合法配置不受影响
    good = tmp_path / "good.yaml"
    good.write_text("llm_backend: paratera\nrounds: 7\nseeds: [0, 1]\n", encoding="utf-8")
    cfg = load_config(str(good))
    assert cfg.llm_backend == "paratera" and cfg.rounds == 7 and cfg.seeds == (0, 1)


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


def test_api_embedder_usage_missing_fails():
    # PR #5 审查 P1：embedding 侧 usage 缺失/不可用 → 显式 fail（与 chat 侧 require_token_usage 对称）
    def _emb_with(resp):
        emb = ApiEmbedder.__new__(ApiEmbedder)
        emb._cache = {}
        emb.requests = emb.cache_hits = emb.input_tokens = 0
        emb.dim = 0
        emb._model = "test-embed"
        emb._client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda model, input: resp))
        return emb

    bad_responses = [
        SimpleNamespace(data=[SimpleNamespace(embedding=[0.1])], usage=None),  # usage 缺失
        SimpleNamespace(data=[SimpleNamespace(embedding=[0.1])]),  # 无 usage 属性
        SimpleNamespace(  # prompt_tokens None
            data=[SimpleNamespace(embedding=[0.1])], usage=SimpleNamespace(prompt_tokens=None)
        ),
        SimpleNamespace(  # prompt_tokens 字符串
            data=[SimpleNamespace(embedding=[0.1])], usage=SimpleNamespace(prompt_tokens="7")
        ),
        SimpleNamespace(  # 负数
            data=[SimpleNamespace(embedding=[0.1])], usage=SimpleNamespace(prompt_tokens=-3)
        ),
    ]
    for resp in bad_responses:
        try:
            _emb_with(resp).encode("x")
            raise AssertionError(f"不可用 embed usage 应 raise: {resp.usage!r}")
        except RuntimeError:
            pass


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
    doc = json.load(open(os.path.join(out_dir, "result.json"), encoding="utf-8"))
    assert validate_run_result(doc) == []
    assert doc["manifest"]["code_sha"]  # git 仓库内执行时应锚定 code SHA
    assert (
        doc["result"]["synapse_total"]["transport_bytes"] >= doc["result"]["synapse_total"]["logical_bytes"]
    )
    # 兼容层：旧读取方（plot_* 脚本）依赖的顶层 config/result 键仍在
    assert "config" in doc and "result" in doc


def test_dataset_info_imports_provenance_sidecar(tmp_path):
    data = tmp_path / "sample.json"
    data.write_text("[]\n", encoding="utf-8")
    (tmp_path / "sample.json.meta.json").write_text(
        json.dumps(
            {
                "dataset": "example/qa",
                "revision": "a" * 40,
                "split": "validation",
                "output_sha256": "ignored-in-favor-of-recomputed-file-hash",
            }
        ),
        encoding="utf-8",
    )
    info = dataset_info(str(data), 0)
    assert info["dataset"] == "example/qa"
    assert info["revision"] == "a" * 40
    assert info["sha256"]


def _mini_manifest(command: str = "x") -> dict:
    """schema 合法的最小 manifest（新契约必填键齐全）。"""
    return {
        "command": command,
        "started_utc": "2026-08-27T12:00:00+00:00",
        "schema_version": "1.0.0",
        "code_sha": "a" * 40,
        "git_status": "ok",
        "code_dirty": False,
        "config": {"model": "m", "temperature": 0},
        "model": "m",
        "embed_model": "e",
        "llm_backend": "mock",
        "embedder": "hash",
        "temperature": 0,
        "seed": None,
        "dataset": None,
        "env": {"os": "o", "python": "p"},
    }


def test_schema_rejects_broken_doc():
    assert validate_run_result({"result": {}})  # 缺顶层键 → 报错
    assert validate_run_result(
        {
            "schema_version": "1.0.0",
            "config": {},
            "manifest": _mini_manifest(),
            "result": {"text": {"messages": 1}},
        }
    )  # metrics 缺 V3-02 计量字段 → 报错
    # 失败 run：显式 status=error + error 字符串 → 豁免 metrics 契约
    assert (
        validate_run_result(
            {
                "schema_version": "1.0.0",
                "config": {},
                "manifest": _mini_manifest("probe"),
                "result": {"status": "error", "error": "e2e: boom"},
            }
        )
        == []
    )  # 失败 run 豁免
    # 收紧：仅有 raw_error 键而无显式 status/error 字段 → 不豁免（审查 P1-1）
    assert validate_run_result(
        {
            "schema_version": "1.0.0",
            "config": {},
            "manifest": _mini_manifest("probe"),
            "result": {"raw_error": "..."},
        }
    )
    # 恒等式复算：logical != header+text+nontext → 报错
    m = _mini_manifest()
    bad = dict(_full_metrics(), logical_bytes=999)
    assert validate_run_result(
        {"schema_version": "1.0.0", "config": {}, "manifest": m, "result": {"text": bad}}
    )


def _full_metrics() -> dict:
    return {
        "llm_input_tokens": 10,
        "llm_output_tokens": 2,
        "transport_bytes": 50,
        "wire_bytes": 40,
        "logical_bytes": 40,
        "header_bytes": 10,
        "text_bytes": 20,
        "nontext_bytes": 10,
        "embed_requests": 1,
        "embed_cache_hits": 0,
        "embed_input_tokens": 3,
        "cas_writes": 1,
        "cas_write_bytes": 30,
    }


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


def test_abl_no_memory_counters_non_negative():
    # abl_no_memory 每任务重置 CAS/store（审查 P1-8）：delta 计数不得为负
    from dataclasses import replace as _replace

    from synapse.modes.synapse_mode import SynapseSession

    s = SynapseSession(_replace(Config(), abl_no_memory=True))
    for _ in range(2):
        m = s.run_task(T.g1_family(1)[0])["metrics"]
        assert m.cas_writes >= 0 and m.cas_write_bytes >= 0
        assert m.embed_requests >= 0 and m.embed_cache_hits >= 0


def _write_hotpot_fixture(path) -> str:
    items = [
        {
            "id": f"q{i}",
            "question": f"who did thing {i}?",
            "answer": f"person {i}",
            "paragraphs": [{"title": f"P{j}", "text": f"fact {j} about person {i}"} for j in range(3)],
            "gold_titles": ("P0",),
            "level": "bridge",
        }
        for i in range(2)
    ]
    import json as _json

    with open(path, "w", encoding="utf-8") as f:
        _json.dump(items, f)
    return str(path)


def test_hotpot_stats_schema_contract(tmp_path):
    # 审查 P0-1 回归：stats 命令的 result 必须能通过 schema 校验并成功落档
    from synapse.eval.manifest import collect_manifest
    from synapse.eval.schema import validate_run_result
    from synapse.qa.harness import run_hotpot_stats

    fx = _write_hotpot_fixture(tmp_path / "fixture.json")
    res = run_hotpot_stats(Config(), n_items=2, repeats=2, path=fx)
    doc = {
        "schema_version": "1.0.0",
        "config": Config().to_dict(),
        "manifest": collect_manifest(
            Config(), "hotpot-stats", dataset={"path": fx, "sha256": "x" * 64, "n_items": 2}
        ),
        "result": res,
    }
    errs = validate_run_result(doc)
    assert errs == [], f"hotpot-stats payload 应过 schema: {errs}"
    assert "text_total" in res and "synapse_total" in res  # 白名单命名（非 last_text/last_synapse）


def test_coqa_per_item_turn_layer():
    # 审查 P1-4：CoQA 逐 turn 展开层结构（qid 稳定、双模式预测与 F1 对齐）
    from synapse.qa.dataset import Conversation, Turn
    from synapse.qa.pipeline import run_synapse, run_text

    conv = Conversation(
        conv_id="c1",
        source="s",
        story="Alpha beta gamma delta story text here.",
        turns=[Turn(idx=0, q="who is alpha?", gold="a person"), Turn(idx=1, q="and beta?", gold="another")],
    )
    cfg = Config()
    rt, rs = run_text(conv, cfg), run_synapse(conv, cfg)
    assert len(rt["preds"]) == len(rs["preds"]) == len(rs["golds"]) == 2
    assert all(p is not None for p in rs["preds"])


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
