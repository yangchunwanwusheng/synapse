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
POSIX 资源限制，指直接 worker；非安全沙箱——同用户文件系统/网络未隔离）"。
另两条通道边界（复审补）：子进程产物经 pickle 回传父进程反序列化——当前受限解释器内
构造恶意对象不可达，但放宽 ``additional_authorized_imports`` 时须重评此通道；超时强杀
的是**直接 worker 子进程**（白名单限制下无派生进程路径，进程树终止未单独验证）。
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
        """POSIX 资源限制；Windows 返回 None（subprocess 不接受可调用 preexec_fn）。

        注：preexec_fn 在多线程进程中 fork 属 CPython 文档警示场景——当前 synapse
        调用链单线程无碍；未来并发 run 需换 posix_spawn 方案。FSIZE 上限当前为模块
        常量（防日志/数据文件刷盘），memory/cpu 可经构造参数配置。
        """
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
        # 信封必须 ASCII（ensure_ascii=True）：子进程 stdin 编码随 locale（Windows GBK/POSIX C），
        # 中文 code/state 全部经 unicode 转义传输，任何 locale 解码均无损（实测 GBK 下中文往返精确相等）
        payload = json.dumps(
            {
                "code": code_action,
                # state 含 smolagents PrintContainer 等非 JSON 类型 → pickle b64 通道；
                # 逐 key 过滤：个别不可 pickle 的值只丢该键，不拖垮整个 state（复审 P1-2）
                "state_b64": _pickle_state({k: v for k, v in self.state.items() if k != "__name__"}),
                "additional_authorized_imports": self.additional_authorized_imports,
                "max_print_outputs_length": self.max_print_outputs_length,
            },
            ensure_ascii=True,
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
        # state 回传：解码失败=协议错误（显式失败，不静默丢 state）
        st = _unpickle(env.get("state_b64") or "")
        if st is _DECODE_FAILED:
            raise InterpreterError("executor protocol error: state decode failed")
        if isinstance(st, dict):
            # 整体重建（非合并，评审 P3）：子进程 state 是权威快照——代码内 del 的键随重建消失
            # （与 local 档 del 语义一致；原合并语义会残留父侧旧值并在下一步送回）；不可 pickle
            # 被丢弃的键同样不再保留旧值（旧值本就随一次性子进程消亡）。
            self.state = {"__name__": "__main__", **st}
        if not env.get("ok"):
            raise InterpreterError(env.get("error") or "executor failed without error message")
        if env.get("output_repr"):  # 非 final 中间结果不可 pickle → repr 降级（仅观察面，非业务承诺）
            output = env.get("output_repr_text", "")
        else:
            output = _unpickle(env.get("output_b64"))
            if env.get("output_b64") and output is _DECODE_FAILED:
                raise InterpreterError("executor protocol error: output decode failed")
        return CodeOutput(output=output, logs=env.get("logs", ""), is_final_answer=env["is_final_answer"])

    def cleanup(self) -> None:  # 一次性子进程无持久资源（CodeAgent.close 会探测性调用）
        pass


class _DecodeFailed:
    """哨兵：与合法 None 区分传输层解码失败。"""


_DECODE_FAILED = _DecodeFailed()


def _pickle_state(state: dict) -> str:
    """逐 key 过滤后 pickle（不可 pickle 的键丢弃），永不整体失败为 None。"""
    safe = {}
    for k, v in state.items():
        try:
            pickle.dumps(v)
            safe[k] = v
        except Exception:  # noqa: BLE001 — 单键不可序列化只丢该键（与子进程回传侧对称）
            continue
    return base64.b64encode(pickle.dumps(safe)).decode("ascii")


def _unpickle(b64: str | None):
    if not b64:
        return None
    try:
        return pickle.loads(base64.b64decode(b64))
    except Exception:  # noqa: BLE001 — 返回哨兵由调用方显式定性（协议错误不静默）
        return _DECODE_FAILED
