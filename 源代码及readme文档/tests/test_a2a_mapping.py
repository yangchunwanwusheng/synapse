"""A2A Agent Card 映射测试（Issue #149015 可选项，M2 协议映射）。

pinned 快照：tests/fixtures/a2a_agent_card_schema_snapshot.json（a2aproject/A2A
specification/a2a.proto @ 98853be376c8，2026-09-03 核验；静态入库不动态抓取）。
快照只能检测"实现是否偏离已 pin 规范"，不能检测上游更新——升级须人工重核。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse.protocol.a2a import from_agent_card, to_agent_card
from synapse.protocol.messages import Capability

FIXTURE = Path(__file__).parent / "fixtures" / "a2a_agent_card_schema_snapshot.json"


def _cap():
    return Capability(
        agent_id="retriever-1",
        role="retriever",
        actions=("RETRIEVE", "TELL"),
        encodings=("text", "embedding", "residual"),
        model_family="mock-family",
        probe=("codeact_sandbox",),
    )


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_roundtrip_capability_lossless_including_probe():
    card = to_agent_card(_cap(), "https://example.com/a2a/v1")
    back = from_agent_card(card)
    assert back == _cap()  # 全字段（含 probe）roundtrip 无损


def test_card_conforms_to_pinned_schema():
    """产出的每个键都在 pinned 快照字段集内；required 字段全部存在；键名 camelCase。"""
    card = to_agent_card(_cap(), "https://example.com/a2a/v1", protocol_version="1.0")
    fx = _fixture()["messages"]

    card_fields = fx["AgentCard"]["json_fields"]
    assert set(card) <= set(card_fields), "未知顶层字段偏离 pinned 快照"
    for name, spec in card_fields.items():
        if spec["required"]:
            assert name in card, f"required 字段 {name} 缺失"

    iface = card["supportedInterfaces"][0]
    iface_fields = fx["AgentInterface"]["json_fields"]
    assert set(iface) <= set(iface_fields)
    for name, spec in iface_fields.items():
        if spec["required"]:
            assert name in iface

    skill = card["skills"][0]
    skill_fields = fx["AgentSkill"]["json_fields"]
    assert set(skill) <= set(skill_fields)
    for name, spec in skill_fields.items():
        if spec["required"]:
            assert name in skill

    assert set(card["capabilities"]) <= set(fx["AgentCapabilities"]["json_fields"])
    # lowerCamelCase 防回归（snake_case 是 proto 源名，不是 JSON 名）
    for key in card:
        assert "_" not in key, f"JSON 键 {key} 应为 lowerCamelCase"


def test_pins_are_recorded():
    fx = _fixture()["pinned_source"]
    assert fx["commit"] == "98853be376c88df25e1704771cd3ea9ef8823a96"
    assert fx["file"].endswith("a2a.proto")
    assert fx["verified_at"] >= "2026-09-03"


def test_to_agent_card_input_validation():
    with pytest.raises(ValueError, match="url is required"):
        to_agent_card(_cap(), "")
    with pytest.raises(ValueError, match="Major.Minor"):
        to_agent_card(_cap(), "https://x.example", protocol_version="1.0.0")
    card = to_agent_card(_cap(), "https://x.example", agent_version="9.9.9")
    assert card["version"] == "9.9.9"  # agent 版本可显式覆盖（≠协议版本）


def test_from_agent_card_strict_encodings_and_skills():
    no_enc = to_agent_card(_cap(), "https://x.example")
    for tag in [t for t in no_enc["skills"][0]["tags"] if t.startswith("synapse:encoding:")]:
        no_enc["skills"][0]["tags"].remove(tag)
    with pytest.raises(ValueError, match="refusing to invent"):
        from_agent_card(no_enc)  # 未声明编码不得静默当 text（伪造能力）
    back = from_agent_card(no_enc, default_encodings=("text",))  # 显式保守回退才允许
    assert back.encodings == ("text",)

    multi = to_agent_card(_cap(), "https://x.example")
    multi["skills"].append(dict(multi["skills"][0], id="second-skill"))
    with pytest.raises(ValueError, match="single-skill mapping refuses"):
        from_agent_card(multi)
    empty = {"skills": []}
    with pytest.raises(ValueError, match="no skills"):
        from_agent_card(empty)


def test_from_agent_card_ignores_foreign_tags_and_unknown_fields():
    card = to_agent_card(_cap(), "https://x.example")
    card["skills"][0]["tags"] += ["some-business-tag", "encoding:residual"]  # 非 synapse: 命名空间
    card["futureSpecField"] = {"unknown": True}  # pinned 快照之后的新字段
    back = from_agent_card(card)
    assert back == _cap()  # 外部标签/未知字段不影响解析
