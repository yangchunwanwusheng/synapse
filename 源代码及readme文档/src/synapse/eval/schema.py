"""run result JSON 的结构校验器（V3-02 schema 冻结件，stdlib only）。

三层 schema（与 docs/schema/run-result.schema.md 同步维护）：
1. manifest 层 —— run 元信息：谁（code_sha）、何时（started_utc）、何机（env）、何配置
2. aggregate 层（result）—— 聚合计量：双模式 metrics + improvement，V3-02 后必须含双口径与分列计数
3. per_item 层（可选）—— 逐题记录：qid / 预测 / 金标 / F1（R-P0-11 逐题可复算）

校验原则：必填项缺失/类型错报错；命令私有字段不强校验（schema 是地板不是天花板）。
"""

from __future__ import annotations

_METRIC_KEYS = (  # aggregate 层任一 metrics dict 必含（V3-02 双口径 + 分列计数）
    "llm_input_tokens",
    "llm_output_tokens",
    "transport_bytes",
    "wire_bytes",
    "logical_bytes",
    "embed_requests",
    "embed_cache_hits",
    "cas_writes",
)
_METRIC_DICT_NAMES = ("text", "synapse", "text_total", "synapse_total")


def _is_metrics_dict(name: str, d) -> bool:
    """识别一个 dict 是否为模式聚合 metrics（名字匹配或 *_metrics 后缀）。"""
    return isinstance(d, dict) and (name in _METRIC_DICT_NAMES or name.endswith("_metrics"))


def _check_metrics_dict(name: str, d, errors: list[str]) -> None:
    for k in _METRIC_KEYS:
        if k not in d:
            errors.append(f"{name} 缺计量字段 {k}（V3-02 后所有 metrics 均须双口径+分列计数）")
        elif not isinstance(d[k], (int, float)):
            errors.append(f"{name}.{k} 必须是数值，实得 {type(d[k]).__name__}")


def validate_run_result(doc) -> list[str]:
    """返回错误列表（空 = 通过）。doc 应为 json.load(result.json) 的结果。"""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return [f"顶层必须是 JSON 对象，实得 {type(doc).__name__}"]
    for key in ("schema_version", "manifest", "result", "config"):
        if key not in doc:
            errors.append(f"顶层缺必填键 {key}")

    mf = doc.get("manifest")
    if isinstance(mf, dict):
        for key in ("command", "started_utc", "schema_version", "config"):
            if key not in mf:
                errors.append(f"manifest 缺必填键 {key}")
        if mf.get("code_sha") is not None and not isinstance(mf.get("code_sha"), str):
            errors.append("manifest.code_sha 必须是 str 或 null")
        env = mf.get("env")
        if not isinstance(env, dict) or not ("os" in env and "python" in env):
            errors.append("manifest.env 必须含 os/python（环境摘要）")
        cfg = mf.get("config")
        if not isinstance(cfg, dict) or "model" not in cfg or "temperature" not in cfg:
            errors.append("manifest.config 必须含 model/temperature（配置快照）")
    elif "manifest" in doc:
        errors.append(f"manifest 必须是 dict，实得 {type(mf).__name__}")

    result = doc.get("result")
    if isinstance(result, dict):
        if result.get("status") == "error" or "raw_error" in result or "e2e_error" in result:
            pass  # 失败 run 也是证据：错误路径豁免 metrics 契约（但仍须可落档可索引）
        else:
            # 深度≤2 扫描 metrics dict（smoke 嵌在 result.linked.text_total；probe 在 result.e2e_metrics）
            found = []

            def _scan(node, prefix: str, depth: int) -> None:
                if depth > 2 or not isinstance(node, dict):
                    return
                for k, v in node.items():
                    if _is_metrics_dict(k, v):
                        found.append(f"{prefix}{k}")
                        _check_metrics_dict(f"{prefix}{k}", v, errors)
                    elif isinstance(v, dict):
                        _scan(v, f"{prefix}{k}.", depth + 1)

            _scan(result, "result.", 1)
            if not found:
                errors.append(
                    "result 缺模式聚合 metrics（text/synapse|text_total/synapse_total|*_metrics，"
                    "可嵌套一层，如 result.linked.text_total）"
                )
    elif "result" in doc:
        errors.append(f"result 必须是 dict，实得 {type(result).__name__}")

    if "per_item" in doc:
        pi = doc["per_item"]
        if not isinstance(pi, list):
            errors.append(f"per_item 必须是 list，实得 {type(pi).__name__}")
        else:
            for i, rec in enumerate(pi):
                if not isinstance(rec, dict) or "qid" not in rec:
                    errors.append(f"per_item[{i}] 必须是含 qid 的 dict")
                    break
    return errors
