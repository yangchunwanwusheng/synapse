"""CoQA 数据集加载（真实对话式 QA；每段对话 = 一组关联连续任务，赛题 M7）。

数据由 scripts/fetch_coqa.py 经 HuggingFace datasets-server 抓取到 data/coqa_sample.json。
不内置语料生成——证据来自真实 CoQA 故事文本，问答为真实标注。
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass


@dataclass
class Turn:
    idx: int
    q: str
    gold: str


@dataclass
class Conversation:
    conv_id: str
    source: str
    story: str
    turns: list[Turn]


def split_sentences(text: str) -> list[str]:
    """故事切句（共享语料的检索单元）。简单标点切分，足够稳健。"""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [s.strip() for s in parts if s.strip()]


def load_conversations(
    path: str = os.path.join("data", "coqa_sample.json"), n: int | None = None
) -> list[Conversation]:
    if not os.path.exists(path):
        raise SystemExit(f"未找到 {path}，请先 `uv run python scripts/fetch_coqa.py`")
    raw = json.load(open(path, encoding="utf-8"))
    convs = [
        Conversation(
            conv_id=c["id"],
            source=c.get("source", ""),
            story=c["story"],
            turns=[Turn(i, t["q"], t["a"]) for i, t in enumerate(c["turns"])],
        )
        for c in raw
    ]
    return convs[:n] if n else convs


# ---- HotpotQA distractor（大且稀疏上下文：每题 10 段，2 金标 + 8 干扰）----


@dataclass
class Paragraph:
    title: str
    text: str


@dataclass
class HotpotItem:
    qid: str
    q: str
    answer: str
    paragraphs: list[Paragraph]
    gold_titles: tuple[str, ...]
    level: str = ""
    qtype: str = ""


def load_hotpot(
    path: str = os.path.join("data", "hotpot_sample.json"), n: int | None = None, seed: int | None = None
) -> list[HotpotItem]:
    """加载 HotpotQA/MuSiQue distractor 数据。seed 非 None 时按 seed shuffle 题序（P0-4 可复现性）。"""
    if not os.path.exists(path):
        raise SystemExit(f"未找到 {path}，请先 `uv run python scripts/fetch_hotpot.py`")
    raw = json.load(open(path, encoding="utf-8"))
    items = [
        HotpotItem(
            qid=it["id"],
            q=it["question"],
            answer=it["answer"],
            paragraphs=[Paragraph(p["title"], p["text"]) for p in it["paragraphs"]],
            gold_titles=tuple(it.get("gold_titles", ())),
            level=it.get("level", ""),
            qtype=it.get("type", ""),
        )
        for it in raw
    ]
    if seed is not None:
        random.Random(seed).shuffle(items)
    return items[:n] if n else items
