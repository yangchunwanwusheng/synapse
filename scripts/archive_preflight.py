#!/usr/bin/env python3
"""Read-only admission check for experiment archives before a scoped Git commit.

The scanner deliberately reports file metadata only. It never prints a matched line,
so a credential found during review is not copied into the report or terminal output.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\b"
        r"\s*[:=]\s*(?!<|\$\{|\{\{)[^\s#]{8,}"
    ),
)
ABSOLUTE_PATH = re.compile(
    r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+|(?<![A-Za-z0-9_.-])/(?:home|Users|tmp|var|opt|mnt)/)"
)


def _finding(kind: str, path: str, severity: str, line: int | None = None) -> dict[str, Any]:
    finding: dict[str, Any] = {"kind": kind, "path": path, "severity": severity}
    if line is not None:
        finding["line"] = line
    return finding


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan_text(path: Path, relative_path: str) -> list[dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError:
        return [_finding("unreadable-file", relative_path, "warning")]
    if b"\0" in raw[:8192]:
        return []
    text = raw.decode("utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    secret_reported = False
    path_reported = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if not secret_reported and any(pattern.search(line) for pattern in SECRET_PATTERNS):
            findings.append(_finding("secret-pattern", relative_path, "error", line_number))
            secret_reported = True
        if not path_reported and ABSOLUTE_PATH.search(line):
            findings.append(_finding("absolute-path", relative_path, "error", line_number))
            path_reported = True
    return findings


def scan_root(root: Path, max_bytes: int) -> tuple[list[dict[str, Any]], int]:
    """Return findings and inspected-file count without changing *root*."""
    if not root.exists():
        return [_finding("missing-root", str(root), "warning")], 0
    if not root.is_dir():
        return [_finding("invalid-root", str(root), "error")], 0

    findings: list[dict[str, Any]] = []
    files = 0
    for path in sorted((candidate for candidate in root.rglob("*") if candidate.is_file()), key=lambda p: str(p)):
        files += 1
        relative_path = _relative(path, root)
        try:
            size = path.stat().st_size
        except OSError:
            findings.append(_finding("unreadable-file", relative_path, "warning"))
            continue
        if size > max_bytes:
            findings.append(_finding("large-file", relative_path, "warning"))
        findings.extend(_scan_text(path, relative_path))
    return findings, files


def build_report(roots: list[Path], max_bytes: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files = 0
    for root in roots:
        root_findings, root_files = scan_root(root, max_bytes)
        findings.extend(root_findings)
        files += root_files
    findings.sort(key=lambda item: (item["severity"], item["kind"], item["path"], item.get("line", 0)))
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "format": "synapse-archive-preflight-v1",
        "roots": [str(root) for root in roots],
        "max_bytes": max_bytes,
        "summary": {"errors": errors, "warnings": warnings, "files": files},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="只读扫描待入库实验归档，不执行 Git 或文件迁移")
    parser.add_argument("--root", action="append", required=True, type=Path, help="待人工审核的归档根目录")
    parser.add_argument("--json", required=True, type=Path, help="JSON 审核记录输出路径")
    parser.add_argument("--max-bytes", type=int, default=1_048_576, help="人工审核的大文件阈值，默认 1 MiB")
    args = parser.parse_args()
    if args.max_bytes < 1:
        parser.error("--max-bytes must be a positive integer")

    report = build_report(args.root, args.max_bytes)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
