"""CodeAct 进程级隔离执行器（V3-08 / Issue #148750 二选一裁决 → 选 A 实现）。

smolagents LocalPythonExecutor 的超时由线程池 ``future.result(timeout)`` 实现，其官方
docstring 明确 *"the thread running the function cannot be forcefully killed"*——失控代码
（如死循环）超时后线程仍泄漏到进程结束，资源不受限。本执行器把每步 CodeAct 放进
一次性子进程：

- **超时可强杀**：父进程持有 wall-clock（``subprocess.run(timeout=...)``），超时即
  kill+wait，无残留线程；
- **POSIX 资源限制**：preexec 施加 RLIMIT_AS（地址空间）/RLIMIT_CPU/RLIMIT_FSIZE/
  RLIMIT_CORE；Windows 无 ``resource`` 模块，降级为仅超时+强杀（能力边界如实声明）；
- **cwd 隔离**：子进程工作目录为一次性临时目录，相对路径写不落仓库；
- 与进程内模式同语义：同一 smolagents import 白名单静态检查、state 跨步保持、
  final_answer 经 FinalAnswerException 识别（子进程内仍跑 LocalPythonExecutor）。

**非安全沙箱**（诚实边界）：子进程与宿主同 OS 用户，绝对路径文件系统与网络均可达；
import 白名单是静态检查而非强制隔离。材料表述口径："进程级隔离执行器（超时可强杀 +
POSIX 资源限制），非安全沙箱"。
"""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
import tempfile
import base64
from pathlib import Path

from smolagents.local_python_executor import CodeOutput, InterpreterError

_CHILD = Path(__file__).with_name("exec_child.py")

_DEFAULT_MEM_MB = 2048  # RLIMIT_AS 默认上限（Python+smolagents 导入的虚拟地址空间需留余量）
_DEFAULT_CPU_S = 120
_DEFAULT_FSIZE_MB = 8  # 代码产物写盘上限（防日志/数据文件刷盘）


class SubprocessExecutor:
    """每步 CodeAct 一次性子进程执行（接口 duck-type 对齐 smolagents PythonExecutor）。"""

    def __init__(
        self,
        additional_authorized_imports: list[str] | None = None,
        timeout_seconds: int = 30,
        memory_limit_mb: int = _DEFAULT_MEM_MB,
        cpu_seconds: int = _DEFAULT_CPU_S,
        max_print_outputs_length: int | None = None,
    ):
        self.additional_authorized_imports = list(additional_authorized_imports or [])
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_seconds = cpu_seconds
        self.max_print_outputs_length = max_print_outputs_length
        self.state: dict = {"__name__": "__main__"}

    def send_variables(self, variables: dict) -> None:
        self.state.update(variables)

    def send_tools(self, tools: dict) -> None:
        # 仅 final_answer 可带入子进程（其余 Tool 对象不可序列化；本项目 4 角色 agents 恒为
        # tools=[] + add_base_tools=False，send_tools 只会收到 final_answer）
        extra = {n for n in tools if n != "final_answer"}
        if extra:
            raise NotImplementedError(
                f"SubprocessExecutor 暂不支持除 final_answer 外的工具注入: {sorted(extra)}"
            )

    def _preexec(self):
        """POSIX 资源限制；Windows 返回 None（subprocess 不接受可调用 preexec_fn）。"""
        if os.name != "posix":
            return None
        import resource

        mem = self.memory_limit_mb * 1024 * 1024
        cpu = self.cpu_seconds
        fsize = _DEFAULT_FSIZE_MB * 1024 * 1024

        def _apply() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        return _apply

    def __call__(self, code_action: str) -> CodeOutput:
        payload = json.dumps(
            {
                "code": code_action,
                # state 含 smolagents PrintContainer 等非 JSON 类型 → pickle b64 通道
                "state_b64": _pickle_b64({k: v for k, v in self.state.items() if k != "__name__"}) or "",
                "additional_authorized_imports": self.additional_authorized_imports,
                "max_print_outputs_length": self.max_print_outputs_length,
            }
        )
        with tempfile.TemporaryDirectory(prefix="synapse-exec-") as cwd:
            try:
                proc = subprocess.run(
                    [sys.executable, str(_CHILD)],
                    input=payload,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    cwd=cwd,
                    preexec_fn=self._preexec(),
                )
            except subprocess.TimeoutExpired as e:
                # 进程级强杀：subprocess.run 超时路径内建 kill+wait，无泄漏线程
                raise InterpreterError(
                    f"Code execution exceeded the maximum execution time of "
                    f"{self.timeout_seconds} seconds (subprocess killed)"
                ) from e
        if proc.returncode != 0 or not proc.stdout.strip():
            tail = (proc.stderr or "").strip()[-500:]
            raise InterpreterError(f"executor process failed (exit={proc.returncode}): {tail}")
        env = json.loads(proc.stdout.strip().splitlines()[-1])
        self.state.update(_unpickle(env.get("state_b64") or ""))
        if not env.get("ok"):
            raise InterpreterError(env.get("error") or "executor failed without error message")
        output = _unpickle(env.get("output_b64"))
        return CodeOutput(output=output, logs=env.get("logs", ""), is_final_answer=env["is_final_answer"])

    def cleanup(self) -> None:  # 一次性子进程无持久资源（CodeAgent.close 会探测性调用）
        pass


def _pickle_b64(obj) -> str | None:
    try:
        return base64.b64encode(pickle.dumps(obj)).decode("ascii")
    except Exception:  # noqa: BLE001 — 父侧状态含不可 pickle 值时按 None 降级（子进程空状态起步）
        try:
            return base64.b64encode(pickle.dumps(None)).decode("ascii")
        except Exception:
            return None


def _unpickle(b64: str | None):
    if not b64:
        return None
    try:
        return pickle.loads(base64.b64decode(b64))
    except Exception:  # noqa: BLE001 — 传输层损坏按执行失败定性，不炸父进程
        return None
