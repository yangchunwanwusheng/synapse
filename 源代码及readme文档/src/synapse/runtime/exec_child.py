"""CodeAct 子进程执行体（V3-08 / Issue #148750）。

由 SubprocessExecutor 以 `<python> exec_child.py` 直接拉起（不经 ``-m``，不 import synapse，
venv 变更零耦合）：

- stdin 收 JSON 载荷：``{code, state, additional_authorized_imports, max_print_outputs_length}``
- stdout 回单行 JSON 信封（全 ASCII）：``{ok, is_final_answer, logs, output_b64, state_b64, error}``
- 超时不由本进程负责：父进程持有 wall-clock，超时直接 kill 本进程（进程级强杀，
  smolagents 线程池超时"线程不可强杀"的问题由此消除）。

子进程内仍用 smolagents LocalPythonExecutor 求值 → 与进程内模式同一套
import 白名单静态检查 / state 语义 / final_answer(FinalAnswerException) 识别，
隔离的只是进程边界与资源，不改变语言语义。
"""

from __future__ import annotations

import base64
import json
import pickle
import sys


def _identity_final_answer(*args, **kwargs):  # noqa: ANN002, ANN003 — 与 smolagents Tool 同签名宽容度
    """final_answer 占位：LocalPythonExecutor 会把它包成 FinalAnswerException(value)。"""
    if len(args) == 1:
        return args[0]
    return args or kwargs.get("default")


def _pickle_b64(obj) -> str | None:
    try:
        return base64.b64encode(pickle.dumps(obj)).decode("ascii")
    except Exception:  # 不可 pickle 的输出降级为 repr 字符串（诚实保住结果文本）
        try:
            return base64.b64encode(pickle.dumps(repr(obj))).decode("ascii")
        except Exception:
            return None


def main() -> None:
    payload = json.loads(sys.stdin.read())
    from smolagents.local_python_executor import LocalPythonExecutor

    state_in = {}
    if payload.get("state_b64"):
        try:
            state_in = pickle.loads(base64.b64decode(payload["state_b64"]))
        except Exception:  # noqa: BLE001 — 传输层损坏按空状态起步（子进程求值自身仍受控）
            state_in = {}

    executor = LocalPythonExecutor(
        additional_authorized_imports=payload.get("additional_authorized_imports") or [],
        max_print_outputs_length=payload.get("max_print_outputs_length"),
        timeout_seconds=None,  # 父进程 wall-clock 强杀；进程内不再叠加线程超时
    )
    executor.send_variables(state_in)
    executor.send_tools({"final_answer": _identity_final_answer})

    ok, output, logs, is_final, error = True, None, "", False, None
    try:
        out = executor(payload["code"])
        output, logs, is_final = out.output, out.logs, out.is_final_answer
    except BaseException as e:  # noqa: BLE001 — 子进程内任何失败都封进信封交父进程定性
        ok, error = False, f"{type(e).__name__}: {e}"
        logs = str(executor.state.get("_print_outputs", ""))

    state = {}
    for k, v in executor.state.items():
        if k == "__name__":
            continue
        try:
            pickle.dumps(v)
            state[k] = v
        except Exception:
            pass  # 工具对象/异常实例等不可序列化状态：跨步保持降级为丢弃（诚实边界）

    sys.stdout.write(
        json.dumps(
            {
                "ok": ok,
                "is_final_answer": bool(is_final),
                "logs": logs,
                "output_b64": _pickle_b64(output) if ok else None,
                "state_b64": _pickle_b64(state) or "",
                "error": error,
            }
        )
        + "\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
