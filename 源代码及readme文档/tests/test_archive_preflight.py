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
        {"kind": "missing-root", "path": str(missing), "severity": "warning"}
    ]


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
