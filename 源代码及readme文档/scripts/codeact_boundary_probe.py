"""CodeAct 执行边界实测探针（V3-08 / Issue #148750）。

对 local（进程内受限解释器，默认档）与 subprocess（进程级隔离执行器，V3-08 新增）各跑
同一组边界探针，输出 JSON 结果与 Markdown 报告。探针全部离线、确定性、有界时长。

探针组（结果只记录实测事实，解释见 docs/工程化基线.md §CodeAct）：

  T1 timeout-kill   ：time.sleep(SLEEP) 配 timeout=T_LIMIT（SLEEP > T_LIMIT）
                      local 预期：ExecutionTimeoutError 抛出，但调用方被线程池 shutdown
                      (wait=True) 阻塞至 sleep 自然结束（wall ≈ SLEEP，实测口径）
                      subprocess 预期：T_LIMIT 即进程级强杀（wall ≈ T_LIMIT），父进程
                      零残留线程，且执行器下一步仍可服务
  T2 import 可达性  ：逐个 import subprocess/socket/os/shutil/math（两档同一 smolagents
                      白名单，预期 math 允许、其余静态拒绝）
  T3 文件系统可达性 ：open() 读系统临时目录 marker 文件（预期两档均被禁用 builtin 拦截——
                      解释器层防线，非 OS 级；同用户文件系统权限未隔离，如实记录）
  T4 资源限制       ：subprocess 档 POSIX RLIMIT_AS 上限下过量分配 → MemoryError/强杀；
                      local 档无资源限制（对照）；Windows 无 resource 模块记 N/A
  T5 崩溃遏制       ：subprocess 档子进程内失败（除零）后父进程存活且可继续服务

用法：
  uv run --no-sync python scripts/codeact_boundary_probe.py            # 打印 Markdown
  uv run --no-sync python scripts/codeact_boundary_probe.py --out docs/xx.md --json path.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

T_LIMIT = 2  # T1 超时上限（秒）
SLEEP = 6  # T1 恶意代码时长（秒）> T_LIMIT：local 档 wall≈SLEEP 即证明"超时后仍被阻塞"
MEM_LIMIT_MB = 512  # T4 subprocess 档 RLIMIT_AS
ALLOC_MB = 1024  # T4 恶意分配量（> MEM_LIMIT_MB）；经 "x"*N 字符串重复构造
# （bytearray(list) 大分配构造器属 smolagents 静态 Forbidden function，测不到 OS 级限制）


def _fa():
    return {"final_answer": lambda *a: a[0] if len(a) == 1 else (a or None)}


def _mk(mode: str, **kw):
    if mode == "local":
        from smolagents.local_python_executor import LocalPythonExecutor

        return LocalPythonExecutor(additional_authorized_imports=[], **kw)
    from synapse.runtime.subprocess_executor import SubprocessExecutor

    return SubprocessExecutor(**kw)


def _run(ex, code: str):
    """单次求值：返回 (outcome, detail)。outcome ∈ ok | blocked | timeout | error。"""
    try:
        out = ex(code)
        return "ok", repr(out.output)[:120]
    except Exception as e:  # noqa: BLE001 — 探针只记录事实
        msg = str(e)
        if "maximum execution time" in msg:
            return "timeout", msg[:160]
        if "not allowed" in msg or "Forbidden" in msg or "not defined" in msg or "failed at line" in msg:
            return "blocked", msg[:160]
        return "error", msg[:160]


def probe_timeout(mode: str) -> dict:
    threads_before = threading.active_count()
    ex = _mk(mode, timeout_seconds=T_LIMIT)
    ex.send_tools(_fa())
    code = "import time as _t\n_t.sleep(%d)\nfinal_answer('slept')" % SLEEP
    t0 = time.monotonic()
    outcome, detail = _run(ex, code)
    wall = round(time.monotonic() - t0, 2)
    # 强杀后执行器是否仍可服务（崩溃遏制 + 无状态损坏）
    recover_outcome, recover_detail = _run(ex, "final_answer('recovered')")
    return {
        "mode": mode,
        "timeout_s": T_LIMIT,
        "sleep_s": SLEEP,
        "outcome": outcome,
        "detail": detail,
        "caller_wall_s": wall,
        "caller_blocked_beyond_timeout": wall >= SLEEP - 0.5,
        "threads_after": threading.active_count(),
        "threads_leaked": threading.active_count() > threads_before,
        "recovered_after_timeout": recover_outcome == "ok" and recover_detail == "'recovered'",
    }


def probe_imports(mode: str) -> dict:
    results = {}
    for mod in ("subprocess", "socket", "os", "shutil", "math"):
        ex = _mk(mode, timeout_seconds=30)
        ex.send_tools(_fa())
        outcome, detail = _run(ex, f"import {mod}\nfinal_answer('imported {mod}')")
        results[mod] = {"outcome": outcome, "allowed": outcome == "ok", "detail": detail[:100]}
    return {"mode": mode, "results": results}


def probe_filesystem(mode: str, marker_path: str) -> dict:
    ex = _mk(mode, timeout_seconds=30)
    ex.send_tools(_fa())
    outcome, detail = _run(ex, f"f = open({marker_path!r})\nfinal_answer(f.read())")
    dunder = _mk(mode, timeout_seconds=30)
    dunder.send_tools(_fa())
    outcome2, detail2 = _run(dunder, 'final_answer(__import__("os").getcwd())')
    return {
        "mode": mode,
        "open_builtin": {"outcome": outcome, "detail": detail[:100]},
        "dunder_import": {"outcome": outcome2, "detail": detail2[:100]},
        "note": "解释器层静态防线（禁用 builtin + import 白名单）；非 OS 级文件系统隔离",
    }


def probe_resource_limit(mode: str) -> dict:
    alloc_code = 's = "x" * (%d * 1024 * 1024)\nfinal_answer(len(s))' % ALLOC_MB
    if os.name != "posix":
        return {
            "mode": mode,
            "platform": platform.system(),
            "outcome": "N/A",
            "detail": "Windows 无 resource 模块（RLIMIT 不可用，仅超时+强杀）",
        }
    kw = {"timeout_seconds": 30}
    if mode == "subprocess":  # local 档无任何资源限制（对照点），不接受该参数
        kw["memory_limit_mb"] = MEM_LIMIT_MB
    ex = _mk(mode, **kw)
    ex.send_tools(_fa())
    t0 = time.monotonic()
    outcome, detail = _run(ex, alloc_code)
    return {
        "mode": mode,
        "platform": platform.system(),
        "rlimit_as_mb": MEM_LIMIT_MB,
        "alloc_mb": ALLOC_MB,
        "outcome": outcome,
        "detail": detail[:120],
        "caller_wall_s": round(time.monotonic() - t0, 2),
        "enforced": outcome in ("blocked", "error"),
    }


def probe_crash_containment(mode: str) -> dict:
    ex = _mk(mode, timeout_seconds=30)
    ex.send_tools(_fa())
    _, fail_detail = _run(ex, "final_answer(1 / 0)")
    outcome, detail = _run(ex, "final_answer('parent alive')")
    return {
        "mode": mode,
        "child_failure": fail_detail[:100],
        "parent_survives": outcome == "ok" and detail == "'parent alive'",
    }


def build_report(results: dict) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M:%S %z")
    lines = [
        "# CodeAct 执行边界实测报告（探针自动生成）",
        "",
        f"- 生成时间：{ts}",
        f"- 主机：{platform.system()} {platform.release()} {platform.machine()} / Python {platform.python_version()}",
        f"- smolagents：{results['env']['smolagents_version']}",
        "- 探针脚本：`scripts/codeact_boundary_probe.py`（离线、确定性、有界时长）",
        "",
        "## T1 超时强杀（timeout=%ds，恶意 sleep=%ds）" % (T_LIMIT, SLEEP),
        "",
        "| 档位 | 结果 | 调用方 wall | 超时后仍被阻塞 | 线程泄漏 | 强杀后可恢复 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results["t1"]:
        lines.append(
            f"| {r['mode']} | {r['outcome']} | {r['caller_wall_s']}s | "
            f"{'**是**' if r['caller_blocked_beyond_timeout'] else '否'} | "
            f"{'是' if r['threads_leaked'] else '否'} | "
            f"{'是' if r['recovered_after_timeout'] else '否'} |"
        )
    lines += [
        "",
        "> local 档实测：`ExecutionTimeoutError` 在超时点抛出，但调用方被线程池 "
        "`shutdown(wait=True)` join 阻塞至代码自然结束（wall≈sleep 时长）——smolagents "
        'docstring 自述 *"the thread cannot be forcefully killed"* 的实测强化口径；'
        "`time.sleep(10**9)` 级代码将使 Agent 进程实质挂死。subprocess 档 wall≈timeout 即返回，"
        "父进程零残留线程且可继续服务。",
        "",
        "## T2 import 可达性（两档同一 smolagents 白名单）",
        "",
        "| 模块 | local | subprocess | 拦截证据（截断） |",
        "|---|---|---|---|",
    ]
    imp_local = results["t2_local"]["results"]
    imp_sub = results["t2_subprocess"]["results"]
    for mod in imp_local:
        a, b = imp_local[mod], imp_sub[mod]
        lines.append(
            f"| `{mod}` | {'允许' if a['allowed'] else '拒绝'} | {'允许' if b['allowed'] else '拒绝'} "
            f"| {(a['detail'] or b['detail'])[:60]} |"
        )
    lines += [
        "",
        "## T3 文件系统可达性",
        "",
        "| 档位 | open() builtin | __import__ builtin |",
        "|---|---|---|",
    ]
    for key in ("t3_local", "t3_subprocess"):
        r = results[key]
        lines.append(f"| {r['mode']} | {r['open_builtin']['outcome']} | {r['dunder_import']['outcome']} |")
    lines += [
        "",
        f"> {results['t3_local']['note']}：两档均拦截 `open`/`__import__`（禁用 builtin）与白名单外 "
        "import；若经 `additional_authorized_imports` 放宽或解释器实现漏洞获得 `os` 等模块，"
        "子进程与宿主同 OS 用户，文件系统/网络权限**未隔离**——故材料口径为"
        '"受限解释器/进程级隔离执行器，非安全沙箱"。',
        "",
        "## T4 资源限制（RLIMIT_AS=%dMB，恶意分配=%dMB）" % (MEM_LIMIT_MB, ALLOC_MB),
        "",
        "| 档位 | 平台 | 结果 | 是否受限 |",
        "|---|---|---|---|",
    ]
    for r in (results["t4_local"], results["t4_subprocess"]):
        lines.append(f"| {r['mode']} | {r['platform']} | {r['outcome']} | {r.get('enforced', False)} |")
    lines += [
        "",
        "## T5 崩溃遏制（子进程内除零 → 父进程存活）",
        "",
        "| 档位 | 父进程存活 |",
        "|---|---|",
    ]
    for r in (results["t5_local"], results["t5_subprocess"]):
        lines.append(f"| {r['mode']} | {'是' if r['parent_survives'] else '否'} |")
    lines += [
        "",
        "---",
        "",
        "**结论（实测口径）**：local 档超时不可强杀且调用方被阻塞；subprocess 档实现超时进程级强杀、"
        "零线程残留、崩溃遏制与 POSIX 资源限制（Windows 降级为仅超时+强杀）。两档均非安全沙箱"
        "（同用户文件系统/网络未隔离，import 白名单为解释器层静态检查）。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeAct 执行边界实测探针")
    parser.add_argument("--out", help="Markdown 报告输出路径（缺省打印 stdout）")
    parser.add_argument("--json", dest="json_out", help="JSON 原始结果输出路径")
    args = parser.parse_args()

    import smolagents

    fd, marker = tempfile.mkstemp(prefix="synapse-boundary-")
    os.write(fd, b"MARKER-12345")
    os.close(fd)
    try:
        results = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "env": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "machine": platform.machine(),
                "smolagents_version": smolagents.__version__,
            },
            "t1": [probe_timeout("local"), probe_timeout("subprocess")],
            "t2_local": probe_imports("local"),
            "t2_subprocess": probe_imports("subprocess"),
            "t3_local": probe_filesystem("local", marker),
            "t3_subprocess": probe_filesystem("subprocess", marker),
            "t4_local": probe_resource_limit("local"),
            "t4_subprocess": probe_resource_limit("subprocess"),
            "t5_local": probe_crash_containment("local"),
            "t5_subprocess": probe_crash_containment("subprocess"),
        }
    finally:
        os.unlink(marker)

    report = build_report(results)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8", newline="\n")
        print(f"markdown -> {args.out}")
    else:
        print(report)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        print(f"json -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
