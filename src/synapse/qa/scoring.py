"""CoQA/SQuAD 风格词级 F1（答案正确性；保证"省 token 非靠少干活"）。

标准化：小写、去标点、去冠词、压空白；再做词级 P/R/F1。与 CoQA 官方评测一致口径。
"""

from __future__ import annotations

import re
import string


def normalize(s: str) -> str:
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
