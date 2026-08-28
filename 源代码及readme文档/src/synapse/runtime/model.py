"""smolagents 模型层（基座 = HuggingFace smolagents）。

- MockChatModel：离线确定性 smolagents 模型，按角色产出 CodeAct（驱动 CodeAgent 调 final_answer）。
  零网络、零 GPU，供 smoke/CI。内容 topic 驱动 → 同主题表示一致（利于残差节省演示）。
- make_model：mock | paratera（OpenAIServerModel，OpenAI 兼容；key 仅来自 .env，严禁硬编码）。

smolagents 只承担"单 Agent 运行时 + 代码执行"这层 commodity，
Agent 间通信/状态传递/记忆是本系统的核心（protocol/stateplane/memory），不在此处。
"""

from __future__ import annotations

import ast
import re

from smolagents import Model

_FINAL_CALL = re.compile(r"final_answer\s*\(")


def _balanced_final_call(s: str) -> str | None:
    """Return the balanced ``final_answer(...)`` call in ``s``, or None."""
    m = _FINAL_CALL.search(s)
    if not m:
        return None
    depth = 0
    for j in range(m.end() - 1, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return s[m.start() : j + 1]
    return None


def normalize_codeact(content: str) -> str:
    """Repair flaky small-model CodeAct so smolagents 1.26 can parse it.

    smolagents wants code wrapped in a ``<code>..</code>`` pair. Qwen3-Instruct
    intermittently emits a bare ``final_answer(...)`` with only a trailing
    ``</code>`` / ``<end_code>`` and no opening tag. We cannot just strip the tag:
    smolagents re-appends its stop tag (``</code>``) to any output that does not
    already end with it, so bare code becomes ``code</code>`` (no opening tag) and
    ``parse_code_blobs`` — which needs the *pair* — fails, burning every step
    ("Reached max steps") on a trivial call. The fix is to wrap the recovered code
    in a full ``<code>..</code>`` pair. We touch only CodeAct-looking outputs; plain
    text (e.g. a QA answer) is returned untouched.

    Args:
        content: Raw model output text.

    Returns:
        Code wrapped in a ``<code>..</code>`` pair, or the original ``content`` when
        it is already fenced / plain text / unrecoverable.
    """
    if not content or "<code>" in content or "```" in content:
        return content  # empty or already fenced → leave for smolagents
    if "final_answer(" not in content and "</code>" not in content and "<end_code>" not in content:
        return content  # plain text (QA answer etc.) → never touch
    s = content
    for tag in ("</code>", "<end_code>", "<end_action>", "<code>"):
        s = s.replace(tag, "")
    s = s.strip()
    if not s:
        return content
    try:
        ast.parse(s)  # whole remainder is valid python
        code = s
    except SyntaxError:  # prose around the call → keep just the balanced final_answer(...)
        code = _balanced_final_call(s)
        if code is None:
            return content  # unrecoverable → let smolagents raise as before
    return f"<code>\n{code}\n</code>"  # full pair: passes endswith check AND parse_code_blobs


def require_token_usage(msg):
    """真实后端响应必须携带完整可用的 token_usage（V3-02：usage 缺失 fail 而非静默计 0）。

    计量是证据链的地基：缺 usage（对象缺失 / 缺 input/output 字段 / 字段 None / 非 int /
    负数）时计 0 会让 token 节省数字失真且不可察觉，因此全部显式失败（审查 P0-3：
    "有 usage 壳、无可用值"同样禁止）。后端若回 prompt_tokens/completion_tokens 命名，
    应在适配层显式转换，而不是在计量层默认 0。
    """
    tu = getattr(msg, "token_usage", None)
    if tu is None:
        raise RuntimeError(
            "LLM response missing token_usage: chat usage is mandatory for the V3-02 evidence "
            "ledger (check backend compatibility / response shape)."
        )
    for field in ("input_tokens", "output_tokens"):
        v = getattr(tu, field, None)
        if type(v) is not int or v < 0:  # 排除 None/float/str/bool/负数
            raise RuntimeError(
                f"token_usage.{field} invalid ({v!r}): expected non-negative int. "
                "Backend returned an unusable usage object; refusing to record 0."
            )
    return tu


try:  # ChatMessage 路径在不同版本可能不同
    from smolagents.models import ChatMessage
except Exception:  # pragma: no cover
    from smolagents import ChatMessage  # type: ignore


def _chat(content: str):
    return ChatMessage(role="assistant", content=content)


def _count_prompt_tokens(messages) -> int:
    """近似输入 token = prompt 全文词数（mock 用；真实路径用 API usage）。"""
    total = 0
    for m in messages or []:
        c = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(c, list):  # smolagents 多模态 content 块
            c = " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in c)
        total += len(str(c or "").split())
    return total


def _codeact(role: str, topic: str, n_facts: int) -> str:
    """按角色返回一段可被 CodeAgent 解析执行的 CodeAct（确定性）。"""
    t = topic or "x"
    if role == "planner":
        body = f'final_answer(["retrieve {t}", "compute {t}", "summarize {t}"])'
    elif role == "retriever":
        facts = " ".join(f"{t}-fact{i}" for i in range(n_facts))
        body = f'final_answer("evidence about {t} : {facts}")'
    elif role == "executor":  # 真·CodeAct（M11）：在 smolagents 本地执行器里对注入的 evidence 计算
        body = "result = len(evidence.split())\nfinal_answer(result)"
    elif role == "summarizer":
        body = f'final_answer("conclusion on {t} : " + str(metric) + " evidence points")'
    else:
        body = 'final_answer("ok")'
    return f"Thought: {role} acts.\nCode:\n```py\n{body}\n```<end_code>"


class MockChatModel(Model):
    """离线确定性模型：按 role 出 CodeAct；topic 由 Session 在每任务前注入。"""

    def __init__(self, role: str, n_facts: int = 40):
        super().__init__()
        self.role = role
        self.topic = ""
        self.n_facts = n_facts
        self.output_tokens = 0  # 近似 LLM 输出 token（= 生成词数），供 M8 统计
        self.input_tokens = 0  # 近似 LLM 输入 token（= 收到的 prompt 词数）

    def generate(self, messages, stop_sequences=None, **kwargs):  # noqa: ANN001
        self.input_tokens += _count_prompt_tokens(messages)
        code = _codeact(self.role, self.topic, self.n_facts)
        self.output_tokens += len(code.split())
        return _chat(code)


def make_model(cfg, role: str):
    """按配置构造 smolagents 模型；真实路径用 OpenAIServerModel（OpenAI 兼容平台）。

    支持任何 OpenAI 兼容后端（paratera / vectorengine / 其他）：只要 llm_backend != "mock"
    且配齐 api_base + api_key，即走 OpenAIServerModel 同一代码路径。
    """
    if cfg.llm_backend != "mock":  # paratera / vectorengine / 任何 OpenAI 兼容平台
        from smolagents import OpenAIServerModel  # 需 [api] extra（openai 包）

        key = cfg.api_key()
        if not key:
            raise RuntimeError(f"{cfg.api_key_env} 未设置（API key 只放 .env，严禁硬编码）")

        class CountingOpenAIServerModel(OpenAIServerModel):
            """在模型层累计 output_tokens（M8）。

            必须在模型对象上计数：agent.run(reset=True) 每轮会清零 agent.monitor，
            跨任务读 monitor 会得到负 delta（已实测 bug）；模型对象跨 reset 持久，计数才正确。
            """

            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.output_tokens = 0
                self.input_tokens = 0

            def generate(self, *a, **kw):  # noqa: ANN001
                msg = super().generate(*a, **kw)
                tu = require_token_usage(msg)
                self.output_tokens += int(getattr(tu, "output_tokens", 0) or 0)
                self.input_tokens += int(getattr(tu, "input_tokens", 0) or 0)
                try:  # repair flaky CodeAct so the CodeAgent path doesn't burn all steps
                    fixed = normalize_codeact(msg.content or "")
                    if fixed != msg.content:
                        msg.content = fixed
                except (AttributeError, TypeError):  # content immutable/odd shape → leave as-is
                    pass
                return msg

        # temperature 进 self.kwargs → 合入 completion_kwargs（最高优先级）；固定 0 保复现性
        return CountingOpenAIServerModel(
            model_id=cfg.model,
            api_base=cfg.api_base,
            api_key=key,
            temperature=getattr(cfg, "temperature", 0.0),
        )
    return MockChatModel(role, n_facts=getattr(cfg, "n_facts", 40))
