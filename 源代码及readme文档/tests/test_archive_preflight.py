import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "archive_preflight.py"


def test_preflight_reports_missing_roots_without_writing_files(tmp_path):
    report = tmp_path / "report.json"
    missing = tmp_path / "runs"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(missing), "--json", str(report)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"] == {"errors": 0, "warnings": 1, "files": 0}
    assert payload["findings"] == [
        {"kind": "missing-root", "path": missing.as_posix(), "severity": "warning"}
    ]
    assert all("\\" not in root for root in payload["roots"])


def test_preflight_detects_secret_absolute_path_and_large_file(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "config.txt").write_text(
        "token=sk-abcdefghijklmnopqrstuvwxyz123456\nsource=C:\\\\Users\\\\alice\\\\run.json\n",
        encoding="utf-8",
    )
    (candidate / "artifact.bin").write_bytes(b"x" * 101)
    report = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(candidate),
            "--json",
            str(report),
            "--max-bytes",
            "100",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"] == {"errors": 2, "warnings": 1, "files": 2}
    assert {(f["kind"], f["path"]) for f in payload["findings"]} == {
        ("secret-pattern", "config.txt"),
        ("absolute-path", "config.txt"),
        ("large-file", "artifact.bin"),
    }


def test_preflight_detects_linux_root_and_data_paths(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "paths.txt").write_text(
        "cache=/root/synapse\nartifact=/data/runs/result.json\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(candidate), "--json", str(report)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert {(f["kind"], f["path"]) for f in payload["findings"]} == {
        ("absolute-path", "paths.txt"),
    }


def test_gitignore_blocks_local_tool_directories():
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert ".zcode/" in gitignore.splitlines()
    assert ".claude/" in gitignore.splitlines()
