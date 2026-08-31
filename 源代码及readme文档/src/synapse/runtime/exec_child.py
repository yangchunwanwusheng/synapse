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


class SerializationError(Exception):
    """final answer 对象不可 pickle——子进程通道无法回传（显式失败，不静默 repr 降级）。"""

    def __init__(self, type_name: str):
        super().__init__(
            f"SerializationError: final answer object of type {type_name} is not picklable — "
            "subprocess executor channel supports picklable results only (str/int/list/dict/...)"
        )


def _identity_final_answer(*args, **kwargs):  # noqa: ANN002, ANN003 — 与 smolagents Tool 同签名宽容度
    """final_answer 占位：LocalPythonExecutor 会把它包成 FinalAnswerException(value)。"""
    if len(args) == 1:
        return args[0]
    return args or kwargs.get("default")


def _pickle_b64(obj) -> str | None:
    try:
        return base64.b64encode(pickle.dumps(obj)).decode("ascii")
    except Exception:
        return None


def main() -> None:
    payload = json.loads(sys.stdin.read())
    from smolagents.local_python_executor import LocalPythonExecutor

    state_in = {}
    if payload.get("state_b64"):
        try:
            loaded = pickle.loads(base64.b64decode(payload["state_b64"]))
            if isinstance(loaded, dict):  # 复审 P1-2：None/畸形载荷按空状态起步，不再炸 send_variables
                state_in = loaded
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
    output_repr = False
    output_repr_text = ""
    try:
        out = executor(payload["code"])
        output, logs, is_final = out.output, out.logs, out.is_final_answer
        if ok and _pickle_b64(output) is None:
            # 复审修正：不可 pickle 的结果不再静默 repr 降级——final answer 属业务承诺，
            # 显式 SerializationError（子进程通道仅支持可 pickle 结果：str/int/list/dict 等）；
            # 非 final 中间结果降级 repr 且打标（父进程区分观察文本与真实值）。
            if is_final:
                raise SerializationError(type(output).__name__)
            output_repr, output_repr_text = True, repr(output)[:2000]
    except SerializationError as e:
        ok, error = False, str(e)
    except BaseException as e:  # noqa: BLE001 — 子进程内任何失败都封进信封交父进程定性
        ok, error = False, f"{type(e).__name__}: {e}"
        logs = str(executor.state.get("_print_outputs", ""))
        output_repr = False

    state = {}
    state_dropped = 0
    for k, v in executor.state.items():
        if k == "__name__":
            continue
        try:
            pickle.dumps(v)
            state[k] = v
        except Exception:
            state_dropped += 1  # 不可序列化状态键计数入信封（跨步保持降级为丢弃，透明化）

    sys.stdout.write(
        json.dumps(
            {
                "ok": ok,
                "is_final_answer": bool(is_final),
                "logs": logs,
                "output_b64": _pickle_b64(output) if ok and not output_repr else None,
                "output_repr": output_repr,
                "output_repr_text": output_repr_text,
                "state_b64": _pickle_b64(state) or "",
                "state_dropped": state_dropped,
                "error": error,
            },
            # ASCII 信封（与父侧对称）：stdout 编码随 locale，ensure_ascii=True 保证任何 locale 无损
            ensure_ascii=True,
        )
        + "\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
