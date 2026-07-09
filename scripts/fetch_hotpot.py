"""抓取 HotpotQA distractor 验证集到 data/hotpot_sample.json（经 HuggingFace datasets-server）。

每题 = 10 段上下文（2 段金标 + 8 段干扰）= "大且稀疏上下文" regime：
基线塞全 10 段、SYNAPSE 只检索相关段 → 验证"丢干扰段大幅省 token 且 F1 不降"（赛题通信效率/状态传递）。
取验证集**前 N 题**（不挑样，保诚实），要求恰好 10 段且 2 个金标标题都在上下文内。
  uv run python scripts/fetch_hotpot.py [N]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = (
    "https://datasets-server.huggingface.co/rows?dataset=hotpotqa%2Fhotpot_qa"
    "&config=distractor&split=validation"
)


def main() -> None:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    items = []
    for off in range(0, 500, 100):
        with urllib.request.urlopen(f"{BASE}&offset={off}&length=100", timeout=60) as r:
            rows = json.load(r)["rows"]
        for x in rows:
            row = x["row"]
            ctx = row["context"]
            titles, sents = ctx["title"], ctx["sentences"]
            gold = tuple(row["supporting_facts"]["title"])
            if len(titles) != 10 or not all(g in titles for g in set(gold)):
                continue
            paragraphs = [{"title": t, "text": " ".join(s).strip()} for t, s in zip(titles, sents)]
            items.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "type": row.get("type", ""),
                    "level": row.get("level", ""),
                    "gold_titles": list(dict.fromkeys(gold)),
                    "paragraphs": paragraphs,
                }
            )
        if len(items) >= want:
            break
    items = items[:want]
    os.makedirs("data", exist_ok=True)
    json.dump(
        items,
        open(os.path.join("data", "hotpot_sample.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    n_words = sum(len(p["text"].split()) for it in items for p in it["paragraphs"]) / max(1, len(items))
    print(f"saved {len(items)} items -> data/hotpot_sample.json (avg {n_words:.0f} ctx words/题)")
    for it in items[:5]:
        print(f"  {it['id'][:12]}: {it['level']}/{it['type']} | gold={it['gold_titles']}")


if __name__ == "__main__":
    main()
