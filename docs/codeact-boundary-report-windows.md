# CodeAct 执行边界实测报告（探针自动生成）

- 生成时间：2026-08-31 21:04:06 +0800
- 主机：Windows 10 AMD64 / Python 3.11.14
- smolagents：1.26.0
- 探针脚本：`scripts/codeact_boundary_probe.py`（离线、确定性、有界时长）

## T1 超时强杀（timeout=2s，恶意 sleep=6s）

| 档位 | 结果 | 调用方 wall | 超时后仍被阻塞 | 线程泄漏 | 强杀后可恢复 |
|---|---|---|---|---|---|
| local | timeout | 6.0s | **是** | 否 | 是 |
| subprocess | timeout | 2.01s | 否 | 否 | 是 |

> local 档实测：`ExecutionTimeoutError` 在超时点抛出，但调用方被线程池 `shutdown(wait=True)` join 阻塞至代码自然结束（wall≈sleep 时长）——smolagents docstring 自述 *"the thread cannot be forcefully killed"* 的实测强化口径；`time.sleep(10**9)` 级代码将使 Agent 进程实质挂死。subprocess 档 wall≈timeout 即返回，父进程零残留线程且可继续服务。

## T2 import 可达性（两档同一 smolagents 白名单）

| 模块 | local | subprocess | 拦截证据（截断） |
|---|---|---|---|
| `subprocess` | 拒绝 | 拒绝 | Code execution failed at line 'import subprocess' due to: In |
| `socket` | 拒绝 | 拒绝 | Code execution failed at line 'import socket' due to: Interp |
| `os` | 拒绝 | 拒绝 | Code execution failed at line 'import os' due to: Interprete |
| `shutil` | 拒绝 | 拒绝 | Code execution failed at line 'import shutil' due to: Interp |
| `math` | 允许 | 允许 | 'imported math' |

## T3 文件系统可达性

| 档位 | open() builtin | __import__ builtin |
|---|---|---|
| local | blocked | blocked |
| subprocess | blocked | blocked |

> 解释器层静态防线（禁用 builtin + import 白名单）；非 OS 级文件系统隔离：两档均拦截 `open`/`__import__`（禁用 builtin）与白名单外 import；若经 `additional_authorized_imports` 放宽或解释器实现漏洞获得 `os` 等模块，子进程与宿主同 OS 用户，文件系统/网络权限**未隔离**——故材料口径为"受限解释器/进程级隔离执行器，非安全沙箱"。

## T4 资源限制（RLIMIT_AS=512MB，恶意分配=1024MB）

| 档位 | 平台 | 结果 | 是否受限 |
|---|---|---|---|
| local | Windows | N/A | False |
| subprocess | Windows | N/A | False |

## T5 崩溃遏制（子进程内除零 → 父进程存活）

| 档位 | 父进程存活 |
|---|---|
| local | 是 |
| subprocess | 是 |

---

**结论（实测口径）**：local 档超时不可强杀且调用方被阻塞；subprocess 档实现超时进程级强杀、零线程残留、崩溃遏制与 POSIX 资源限制（Windows 降级为仅超时+强杀）。两档均非安全沙箱（同用户文件系统/网络未隔离，import 白名单为解释器层静态检查）。
