"""SYNAPSE Capability ↔ A2A Agent Card 静态映射（Issue #149015 可选项，M2 协议映射）。

A2A（Agent2Agent，Linux Foundation 项目）Agent Card 规范正源 = a2aproject/A2A 仓库
`specification/a2a.proto`（a2a.json 是构建产物不入库）。本模块对 **pinned 快照**
（tests/fixtures/a2a_agent_card_schema_snapshot.json，冻结自 commit 98853be376c8，
2026-09-03 核验）做静态字段映射，不动态抓取任何规范网页。

映射约定（AgentSkill.tags 的 SYNAPSE 命名空间标签，lossless）：
  synapse:role:<role> / synapse:action:<A> / synapse:encoding:<E> /
  synapse:model-family:<F> / synapse:probe:<P>
外部卡片中的其他 tags 一律忽略（避免与业务标签碰撞）。

能力边界（如实声明）：仅做 SYNAPSE Capability 与 pinned Agent Card JSON 字段间的
**静态转换与字段校验**——未实现 A2A endpoint/Agent Card discovery URL 发布/
JSON-RPC 互操作/task lifecycle/security schemes 接入。
"""

from __future__ import annotations

import re

from .messages import Capability

#: pinned 快照核验过的协议版本示例（proto AgentInterface.protocol_version 注释）
_PROTOCOL_VERSION_RE = re.compile(r"^\d+\.\d+$")

_ROLE_TAG = "synapse:role:"
_ACTION_TAG = "synapse:action:"
_ENCODING_TAG = "synapse:encoding:"
_FAMILY_TAG = "synapse:model-family:"
_PROBE_TAG = "synapse:probe:"


def _tags(cap: Capability) -> list[str]:
    tags = [_ROLE_TAG + cap.role]
    tags += [_ACTION_TAG + a for a in cap.actions]
    tags += [_ENCODING_TAG + e for e in cap.encodings]
    tags.append(_FAMILY_TAG + cap.model_family)
    tags += [_PROBE_TAG + p for p in cap.probe]
    return tags


def to_agent_card(
    cap: Capability,
    url: str,
    *,
    agent_version: str | None = None,
    protocol_version: str = "1.0",
) -> dict:
    """Capability → pinned A2A Agent Card JSON（lowerCamelCase 键）。

    url：该 agent 的 A2A 接口地址——由部署方提供，映射不虚构（空值拒绝）。
    agent_version：Agent Card 的 version 是 agent 自身版本（非协议版本）；
    缺省读安装包 metadata（synapse 包 0.1.0），可显式覆盖。
    protocol_version：接口暴露的 A2A 协议版本，须 Major.Minor 形（"1.0"，
    "1.0.0" 这类三段式拒绝——pinned 快照示例为 "0.3"/"1.0"）。
    """
    if not url or not isinstance(url, str):
        raise ValueError(
            "Agent Card interface url is required (deployment-provided; mapping never invents it)"
        )
    if not _PROTOCOL_VERSION_RE.match(protocol_version):
        raise ValueError(
            f"protocol_version {protocol_version!r} must be Major.Minor (e.g. '1.0'; pinned spec examples: 0.3/1.0)"
        )
    if agent_version is None:
        try:
            from importlib.metadata import PackageNotFoundError, version

            agent_version = version("synapse-mas")
        except PackageNotFoundError:  # 源码树运行（未安装）——回退显式占位，不静默造版本
            agent_version = "0.0.0+source"
    return {
        "name": f"{cap.agent_id} ({cap.role})",
        "description": f"SYNAPSE {cap.role} agent (model family: {cap.model_family})",
        "version": agent_version,
        "supportedInterfaces": [
            {"url": url, "protocolBinding": "JSONRPC", "protocolVersion": protocol_version}
        ],
        "capabilities": {},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": cap.agent_id,
                "name": cap.role,
                "description": f"SYNAPSE {cap.role} agent",
                "tags": _tags(cap),
            }
        ],
    }


def from_agent_card(card: dict, *, default_encodings: tuple[str, ...] | None = None) -> Capability:
    """pinned A2A Agent Card JSON → Capability（单 skill 卡）。

    只消费 synapse: 命名空间 tags 与 skill.id/name；未知字段忽略（前向兼容：
    pinned 快照之后的新字段不炸解析）。能力字段缺失时的策略：
    - role/actions/model_family/probe 缺失 → 空值如实保留（无声明≠有能力）；
    - encodings 缺失 → 默认 ValueError（把'未声明'当 text 会伪造对方能力）；
      保守互操作回退须调用方显式传 default_encodings=("text",)。
    多 skill 卡显式拒绝（本映射定义为单能力卡；多 skill 归属语义须上层裁决）。
    """
    skills = card.get("skills") or []
    if len(skills) == 0:
        raise ValueError("Agent Card has no skills (single-skill mapping requires exactly one)")
    if len(skills) > 1:
        raise ValueError(f"Agent Card has {len(skills)} skills; single-skill mapping refuses ambiguous pick")
    skill = skills[0]
    if not isinstance(skill, dict) or not skill.get("id"):
        raise ValueError("Agent Card skill missing required field 'id'")
    tags = [str(t) for t in skill.get("tags") or []]
    role = next((t[len(_ROLE_TAG) :] for t in tags if t.startswith(_ROLE_TAG)), str(skill.get("name", "")))
    actions = tuple(t[len(_ACTION_TAG) :] for t in tags if t.startswith(_ACTION_TAG))
    encodings = tuple(t[len(_ENCODING_TAG) :] for t in tags if t.startswith(_ENCODING_TAG))
    model_family = next((t[len(_FAMILY_TAG) :] for t in tags if t.startswith(_FAMILY_TAG)), "")
    probe = tuple(t[len(_PROBE_TAG) :] for t in tags if t.startswith(_PROBE_TAG))
    if not encodings:
        if default_encodings is None:
            raise ValueError(
                "Agent Card declares no synapse:encoding tags; refusing to invent encodings "
                "(pass default_encodings=('text',) explicitly for conservative interop)"
            )
        encodings = tuple(default_encodings)
    return Capability(
        agent_id=str(skill["id"]),
        role=role,
        actions=actions,
        encodings=encodings,
        model_family=model_family,
        probe=probe,
    )
