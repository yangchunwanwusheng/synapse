# CodeAct 执行边界实测报告（探针自动生成）

- 生成时间：2026-09-03 03:14:39 +0000
- 主机：Linux 6.6.87.2-microsoft-standard-WSL2 x86_64 / Python 3.11.6
- smolagents：1.26.0
- 探针脚本：`scripts/codeact_boundary_probe.py`（离线、确定性、有界时长）

## T1 超时回收（timeout=2s，恶意 sleep=6s）

| 档位 | 结果 | 调用方 wall | 超时后仍被阻塞 | draining 期残留线程 | draining 拒绝 | 超时后可恢复 | 恢复语义 |
|---|---|---|---|---|---|---|---|
| local | timeout | 2.0s | 否 | 是（≈4.0s 后自然结束） | 是 | 是 | rebuild-after-drain |
| subprocess | timeout | 2.01s | 否 | 否（进程级强杀） | N/A | 是 | immediate |

> local 档实测（#149013 修复后）：调用方 wall≈timeout 即返回（`ExecutionTimeoutError`），不再被库内线程池 `shutdown(wait=True)` join 至代码自然结束（修复前 wall≈sleep 时长，`time.sleep(10**9)` 级代码会使 Agent 进程实质挂死）。如实边界：Python 线程不可强杀——超时 inner 立即作废，旧线程存活期间新执行被显式拒绝（draining），旧线程自然结束后丢弃其 state 重建 inner 恢复服务；残留 daemon 线程如实计数，不阻塞进程退出。
> subprocess 档实测：wall≈timeout 进程级强杀返回，父进程零残留线程且立即恢复（一次性子进程，无状态损坏）。

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
| local | Linux | ok | False |
| subprocess | Linux | blocked | True |

## T5 崩溃遏制（执行器内除零 → 执行器存活可继续服务）

| 档位 | 执行器存活 |
|---|---|
| local | 是 |
| subprocess | 是 |

---

**结论（实测口径，#149013 更新）**：local 档实现调用方 deadline 超时（wall≈timeout 返回），超时 state 作废重建、draining 期显式拒绝；不提供强杀/无残留/立即恢复（Python 线程模型决定，如实声明）。subprocess 档实现超时进程级强杀、零线程残留、立即恢复、崩溃遏制与 POSIX 资源限制（Windows 降级为仅超时+强杀）。两档均非安全沙箱（同用户文件系统/网络未隔离，import 白名单为解释器层静态检查）。
