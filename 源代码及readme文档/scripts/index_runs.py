"""V3-02 sidecar 索引：扫描 runs/*/result.json 生成 runs/index.json（不改任何原始文件）。

旧 106 个 run 无 manifest（R-P0-11：77 个 run 无 code_sha/dataset_version/预测文本）——
本脚本为它们建立可检索索引：tag、时间、配置摘要、关键聚合数字、manifest 有无。
只增不改：唯一产物是 runs/index.json（可重复生成，幂等覆盖自身）。

用法（在 源代码及readme文档/ 下）：
    uv run python scripts/index_runs.py [--runs-dir runs]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Windows GBK 控制台防崩（项目既定约定：涉及输出的脚本显式 utf-8）
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))


def _pick(d: dict, *keys):
    for k in keys:
        if k in d:
            return d[k]
    return None


def _summary_from_result(res: dict) -> dict:
    """从各命令的 result 结构里抽关键聚合（结构历史多样，全部容错）。"""
    out: dict = {}
    imp = (
        res.get("improvement") or (res.get("result") or {}).get("improvement")
        if isinstance(res, dict)
        else {}
    )
    if isinstance(imp, dict):
        for k in ("llm_token_saved_pct", "wire_bytes_saved_pct", "transport_saved_pct"):
            if k in imp:
                out[k] = imp[k]
    for side in ("text", "synapse", "text_total", "synapse_total"):
        m = res.get(side) if isinstance(res, dict) else None
        if isinstance(m, dict):
            if side in ("text", "text_total"):
                out.setdefault("text_f1", _pick(m, "quality"))
                out.setdefault("text_llm_total_tokens", _pick(m, "llm_total_tokens"))
            else:
                out.setdefault("synapse_f1", _pick(m, "quality"))
                out.setdefault("synapse_llm_total_tokens", _pick(m, "llm_total_tokens"))
    for k in ("n_items", "n_conversations", "rounds", "gold_recall"):
        if isinstance(res, dict) and k in res:
            out[k] = res[k]
    return out


def index_runs(runs_dir: str) -> dict:
    entries = []
    for name in sorted(os.listdir(runs_dir)):
        rj = os.path.join(runs_dir, name, "result.json")
        if not os.path.isfile(rj):
            continue
        try:
            with open(rj, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            entries.append({"dir": name, "error": f"unreadable: {e}"})
            continue
        mf = doc.get("manifest") if isinstance(doc, dict) else None
        cfg = doc.get("config") if isinstance(doc, dict) else None
        entries.append(
            {
                "dir": name,
                "schema_version": doc.get("schema_version") if isinstance(doc, dict) else None,
                "has_manifest": isinstance(mf, dict),
                "code_sha": mf.get("code_sha") if isinstance(mf, dict) else None,
                "command": mf.get("command") if isinstance(mf, dict) else None,
                "started_utc": mf.get("started_utc") if isinstance(mf, dict) else None,
                "model": (cfg or {}).get("model") if isinstance(cfg, dict) else None,
                "embedder": (cfg or {}).get("embedder") if isinstance(cfg, dict) else None,
                "llm_backend": (cfg or {}).get("llm_backend") if isinstance(cfg, dict) else None,
                "has_per_item": isinstance(doc.get("per_item"), list) if isinstance(doc, dict) else False,
                "summary": _summary_from_result(doc.get("result", {})) if isinstance(doc, dict) else {},
            }
        )
    return {
        "n_runs": len(entries),
        "indexed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 runs sidecar 索引（不修改任何 run 目录）")
    ap.add_argument("--runs-dir", default="runs")
    args = ap.parse_args()
    if not os.path.isdir(args.runs_dir):
        print(f"[ERR] 目录不存在: {args.runs_dir}")
        return 2
    idx = index_runs(args.runs_dir)
    out = os.path.join(args.runs_dir, "index.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
        f.write("\n")
    n_mf = sum(1 for r in idx["runs"] if r.get("has_manifest"))
    print(f"indexed {idx['n_runs']} runs ({n_mf} with manifest v1, {idx['n_runs'] - n_mf} legacy) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
