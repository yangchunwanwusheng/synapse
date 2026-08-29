"""V3-02 双层计量 manifest：run 元信息采集与统一落档。

一切实验 Issue（V3-03/04/05/07）的证据链地基：code SHA / 配置快照 / 模型与数据集版本 /
seed / 温度 / UTC 时间 / 环境摘要随每次 run 落档，数字从此可溯源（R-P0-11）。

设计约束：
- 零新依赖（stdlib only）；不可用项（无 git / 无 uv.lock）显式标 unavailable，不猜测。
- 落档结构向后兼容：顶层保留 config/result 键（plot_* 脚本不改），新增 schema_version/manifest。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"


def _git(args: list[str]) -> str | None:
    """在 cwd 找 git 信息；git 不可用 / 非 git 目录返回 None（不猜测）。"""
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
        )
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def _file_sha256(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("synapse-mas")
    except Exception:
        return "unknown"


def collect_manifest(
    cfg,
    command: str,
    dataset: dict | None = None,
    seed: int | None = None,
    started_utc: str | None = None,
) -> dict:
    """采集 run 元信息；dataset 形如 {"path","sha256","n_items"}。

    started_utc 由调用方在 **run 开始时**采集传入（审查 P1-2：落档时刻 != 开始时刻）；
    缺省回退当前时刻（兼容旧调用方）。
    """
    code_sha = _git(["rev-parse", "HEAD"])
    dirty = _git(["status", "--porcelain"]) is not None  # 非空输出=工作区有未提交改动
    return {
        "command": command,
        "started_utc": started_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "code_sha": code_sha,
        "git_status": "ok" if code_sha else "unavailable",  # 审计可区分（审查 P2-2）
        "code_dirty": dirty,
        "config": cfg.to_dict(),  # 仅含配置字段与密钥环境变量名，无密钥值
        "model": cfg.model,
        "embed_model": cfg.embed_model,
        "llm_backend": cfg.llm_backend,
        "embedder": cfg.embedder,
        "temperature": cfg.temperature,
        "seed": seed,
        "dataset": dataset,  # {"path","sha256","n_items"} 或 None（合成任务）
        "env": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "package_version": _package_version(),
            "uv_lock_sha256": _file_sha256("uv.lock"),
            "collected_unix": int(time.time()),
        },
    }


def dataset_info(path: str, n_items: int | None = None) -> dict:
    """数据集版本锚定：路径 + SHA256 + 条数（R-P0-9/P1-9 数据可溯源）。"""
    info = {"path": path, "sha256": _file_sha256(path), "n_items": n_items}
    sidecar = f"{path}.meta.json"
    try:
        with open(sidecar, encoding="utf-8") as f:
            provenance = json.load(f)
        for key in ("dataset", "revision", "version", "split", "source_url", "source_sha256", "filters"):
            if key in provenance:
                info[key] = provenance[key]
        info["provenance_path"] = sidecar
    except (OSError, json.JSONDecodeError):
        pass
    if info["sha256"] is None:
        info["note"] = "file unreadable at manifest time"
    return info


def write_run(
    tag: str,
    cfg,
    payload: dict,
    command: str,
    dataset: dict | None = None,
    seed: int | None = None,
    per_item: list | None = None,
    root: str = "runs",
    started_utc: str | None = None,
) -> str:
    """统一落档：runs/<tag>_<本地时间戳>/result.json（manifest + 聚合 + 可选逐题）。

    先在内存完成 schema 校验与序列化，再创建目录写入（审查 P1-7：校验失败不留空目录；
    目录创建用 exist_ok=False 循环，避免并发同秒互相覆盖）。
    started_utc 由调用方在 run 开始时采集传入（审查 P1-2）。
    """
    doc = {
        "schema_version": SCHEMA_VERSION,
        "config": cfg.to_dict(),  # 向后兼容旧读取方（plot_* 脚本）
        "manifest": collect_manifest(cfg, command, dataset=dataset, seed=seed, started_utc=started_utc),
        "result": payload,
    }
    if per_item is not None:
        doc["per_item"] = per_item
    # 内存内校验 + 序列化，全部成功后才碰文件系统
    from .schema import validate_run_result

    errors = validate_run_result(doc)
    if errors:
        raise ValueError("run result failed schema validation:\n  " + "\n  ".join(errors))
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"

    os.makedirs(root, exist_ok=True)
    out_dir = os.path.join(root, f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    n = 2
    while True:
        try:
            os.mkdir(out_dir)  # 排他创建：并发同秒不会互相覆盖
            break
        except FileExistsError:
            out_dir = os.path.join(root, f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}-{n}")
            n += 1
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return out_dir
