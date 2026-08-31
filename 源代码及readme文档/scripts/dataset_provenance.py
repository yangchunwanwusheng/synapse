"""数据抓取脚本共用的确定性落档与来源哈希工具。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_dataset(path: str, rows: list[dict], provenance: dict) -> dict:
    """稳定序列化数据并写相邻 provenance sidecar，返回完整元数据。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(rows, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    target.write_bytes(payload)
    metadata = {
        **provenance,
        "output_path": target.as_posix(),
        "output_sha256": sha256_bytes(payload),
        "n_items": len(rows),
    }
    target.with_suffix(target.suffix + ".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata
