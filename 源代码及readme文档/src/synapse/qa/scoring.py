"""SQuAD/HotpotQA 风格 EM 与词级 F1。

标准化：小写、去标点、去冠词、压空白。多参考答案取最高分，避免只保留
第一个标注而低估模型质量。
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable


def normalize(s: str) -> str:
    """先去标点再去冠词；嵌套调用从内向外执行，不能按书写顺序理解。

    对照 CoQA evaluate-v1.0.py 与 HotpotQA hotpot_evaluate_v1.py：
    white_space_fix(remove_articles(remove_punc(lower(s))))。
    """
    s = (s or "").lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def f1(pred: str, gold: str) -> float:
    p, g = normalize(pred).split(), normalize(gold).split()
    if not p or not g:
        return float(p == g)  # 双空=1；一空一非空=0
    common: dict[str, int] = {}
    for w in p:
        if w in g:
            common[w] = common.get(w, 0) + 1
    overlap = sum(min(c, g.count(w)) for w, c in common.items())
    if overlap == 0:
        return 0.0
    prec, rec = overlap / len(p), overlap / len(g)
    return 2 * prec * rec / (prec + rec)


def exact_match(pred: str, gold: str) -> float:
    """标准化后的字符串完全一致。"""
    return float(normalize(pred) == normalize(gold))


def max_over_references(metric, pred: str, golds: Iterable[str]) -> float:
    """对全部参考答案评分并取最大值；空参考集合显式失败。"""
    refs = tuple(golds)
    if not refs:
        raise ValueError("at least one reference answer is required")
    return max(metric(pred, gold) for gold in refs)


def score(pred: str, golds: Iterable[str]) -> dict[str, float]:
    """返回可逐题落档的多参考 EM/F1。"""
    refs = tuple(golds)
    return {
        "em": max_over_references(exact_match, pred, refs),
        "f1": max_over_references(f1, pred, refs),
    }
