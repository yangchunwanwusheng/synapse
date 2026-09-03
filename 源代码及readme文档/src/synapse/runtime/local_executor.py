"""CodeAct 进程内受限执行器 + 调用方 deadline 超时（Issue #149013）。

smolagents 自带超时（local_python_executor.timeout 装饰器）用
``with ThreadPoolExecutor(...)`` 实现：future.result(timeout) 抛出
ExecutionTimeoutError 后，with 退出时的 shutdown(wait=True) 会 join 工作
线程到失控代码自然结束（T1 实测 wall 6s vs timeout 2s；sleep(10**9) 级
代码令 Agent 进程实质挂死）。本执行器把每步 CodeAct 放进一个裸 daemon
线程执行 inner 解释器（inner 传 timeout_seconds=None 走纯同步路径，无库
内线程池、无 with-join），调用方按 deadline 等待：

- **调用方 deadline 返回**：wall≈timeout，不再等待失控代码自然结束；
- **超时 state 隔离**：Python 线程不可强杀，超时后旧线程可能仍在旧 inner
  的 state 上继续执行——该 inner 立即作废（poisoned），绝不复用；后续调用
  在旧线程存活期间显式拒绝（ExecutorDrainingError，上层走显式降级），旧
  线程自然结束后按缓存 tools/variables 重建干净 inner 再恢复服务；
- **如实边界**：本档不提供强杀、无残留线程、超时后立即恢复——那些是
  subprocess 档（SubprocessExecutor）的语义。local 档只承诺"调用方在
  deadline 返回 + 超时 state 不被后续 step 复用 + 残留 daemon 线程不阻塞
  进程退出"；残留线程在存活期间仍占资源（如实记录，探针 T1 计数）。

与 subprocess 档同语义：同一 smolagents import 白名单静态检查、state 跨步
保持、final_answer 经 FinalAnswerException 识别。
"""

from __future__ import annotations

import threading

# fail-fast：依赖 smolagents 1.26 的模块级名字；未来版本若移除则导入即报错，
# 不做静默兜底（静默换异常类会让超时语义悄悄漂移）。
from smolagents.local_python_executor import (
    ExecutionTimeoutError,
    LocalPythonExecutor,
)

__all__ = ["ExecutionTimeoutError", "ExecutorDrainingError", "TimeoutLocalExecutor"]


class ExecutorDrainingError(RuntimeError):
    """超时后旧代码线程仍存活，本实例拒绝新的执行（上层应显式降级或等待重建）。"""


class TimeoutLocalExecutor:
    """进程内受限解释器 + 调用方 deadline 超时（duck-type 对齐 smolagents PythonExecutor）。

    状态机（复审 P0 修正：超时后共享 inner 复用会与残留线程并发读写 state）：
    IDLE/RUNNING 正常复用同一 inner（保留 step 间 state，与 smolagents 语义一致）；
    超时 → 该 inner poisoned（记 stale_inner + stale_thread），后续调用在旧线程
    存活期间拒绝、结束后丢弃旧 state 重建（replay 缓存的 tools/variables）。
    """

    def __init__(
        self,
        additional_authorized_imports: list[str] | None = None,
        timeout_seconds: int = 30,
        max_print_outputs_length: int | None = None,
    ):
        self.additional_authorized_imports = list(additional_authorized_imports or [])
        self.timeout_seconds = int(timeout_seconds)
        self.max_print_outputs_length = max_print_outputs_length
        self._lock = threading.Lock()
        self._tools: dict | None = None
        self._variables: dict = {}
        self._inner = self._make_inner()
        self._busy = False
        self._stale_inner = None
        self._stale_thread: threading.Thread | None = None
        self._closed = False

    def _make_inner(self) -> LocalPythonExecutor:
        return LocalPythonExecutor(
            additional_authorized_imports=self.additional_authorized_imports,
            max_print_outputs_length=self.max_print_outputs_length,
            timeout_seconds=None,  # 关键：禁用库内线程池超时（with-join 阻塞根因），纯同步
        )

    @property
    def state(self) -> dict:
        """诊断用 state 访问（CodeAgent 异常路径读 state["_print_outputs"]，agents.py:1735）。

        draining 期旧 state 仍可能被后台线程写——返回浅拷贝仅供日志诊断，
        不得用于控制流。
        """
        with self._lock:
            inner = self._inner if self._inner is not None else self._stale_inner
            return dict(inner.state) if inner is not None else {}

    def send_tools(self, tools: dict) -> None:
        with self._lock:
            self._ensure_serviceable_locked()
            self._tools = dict(tools)
            self._inner.send_tools(self._tools)

    def send_variables(self, variables: dict) -> None:
        with self._lock:
            self._ensure_serviceable_locked()
            self._variables.update(variables)  # 累积缓存：重建 inner 后 evidence 等注入不丢
            self._inner.send_variables(self._variables)

    def __call__(self, code_action: str):
        with self._lock:
            if self._closed:
                raise ExecutorDrainingError("TimeoutLocalExecutor: closed (cleanup called)")
            if self._busy:
                raise ExecutorDrainingError("TimeoutLocalExecutor: concurrent call rejected")
            self._reap_stale_locked()
            self._busy = True
            inner = self._inner  # 固定局部引用：工作线程只碰它，切换/重建不经过它
        result: dict = {}
        done = threading.Event()

        def _run() -> None:
            try:
                result["out"] = inner(code_action)
            except Exception as e:  # noqa: BLE001 — 正常异常转抛主线程；BaseException（SystemExit 等）不转抛
                result["err"] = e
            finally:
                done.set()

        worker = threading.Thread(target=_run, daemon=True, name="synapse-codeact-local")
        worker.start()
        timed_out = not done.wait(self.timeout_seconds)
        if timed_out and done.is_set():
            timed_out = False  # deadline 临界竞态：实际已完成，按正常路径取结果
        if timed_out:
            with self._lock:
                self._stale_inner = inner
                self._stale_thread = worker
                self._inner = None
                self._busy = False
            raise ExecutionTimeoutError(
                f"Code execution exceeded the maximum execution time of {self.timeout_seconds} seconds"
            )
        with self._lock:
            self._busy = False
        if "err" in result:
            raise result["err"]
        return result["out"]

    def _ensure_serviceable_locked(self) -> None:
        if self._closed:
            raise ExecutorDrainingError("TimeoutLocalExecutor: closed (cleanup called)")
        self._reap_stale_locked()

    def _reap_stale_locked(self) -> None:
        """旧线程自然结束后丢弃其 state 并重建（replay 缓存）；仍存活则拒绝新执行。"""
        if self._inner is not None:
            return
        if self._stale_thread is not None and self._stale_thread.is_alive():
            raise ExecutorDrainingError(
                "TimeoutLocalExecutor: previous timed-out code is still running in the "
                "background; local tier cannot kill it (subprocess tier provides kill + "
                "immediate recovery)"
            )
        self._inner = self._make_inner()
        if self._tools is not None:
            self._inner.send_tools(self._tools)
        if self._variables:
            self._inner.send_variables(self._variables)
        self._stale_inner = None
        self._stale_thread = None

    def cleanup(self) -> None:
        """CodeAgent.cleanup() 探测该方法（agents.py:1595）。

        如实语义：不强杀残留线程（Python 线程不可强杀），只阻断后续调用并
        释放引用；残留 daemon 线程由进程退出回收。
        """
        with self._lock:
            self._closed = True
            self._inner = None
            self._stale_inner = None
            self._stale_thread = None
            self._tools = None
            self._variables = {}
            self._busy = False
