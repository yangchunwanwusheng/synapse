"""抓取 MuSiQue（第二真实多跳数据集，EH2）到 data/musique_sample.json。

MuSiQue（`dgslibisey/MuSiQue`）每题 20 段、仅 2 段金标（is_supporting）→ 干扰占 90%，
比 HotpotQA(10 段/2 金标) 更稀疏，更强测通信效率。输出与 HotpotQA 同 schema → 复用 load_hotpot。
取 answerable 题前 N。
  uv run python scripts/fetch_musique.py [N]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = (
    "https://datasets-server.huggingface.co/rows?dataset=dgslibisey%2FMuSiQue&config=default&split=validation"
)


def main() -> None:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    items = []
    for off in range(0, 1200, 100):
        with urllib.request.urlopen(f"{BASE}&offset={off}&length=100", timeout=60) as r:
            rows = json.load(r)["rows"]
        for x in rows:
            row = x["row"]
            if not row.get("answerable", True):
                continue
            ps = row["paragraphs"]
            gold = [p["title"] for p in ps if p.get("is_supporting")]
            if len(ps) < 2 or len(gold) < 2:
                continue
            paragraphs = [{"title": p["title"], "text": p["paragraph_text"].strip()} for p in ps]
            items.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "type": "musique",
                    "level": "multihop",
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
        open(os.path.join("data", "musique_sample.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    avg_p = sum(len(it["paragraphs"]) for it in items) / max(1, len(items))
    avg_w = sum(len(p["text"].split()) for it in items for p in it["paragraphs"]) / max(1, len(items))
    print(
        f"saved {len(items)} items -> data/musique_sample.json (avg {avg_p:.0f} paras, {avg_w:.0f} ctx words/题)"
    )
    for it in items[:3]:
        print(f"  {it['id'][:16]}: gold={it['gold_titles']}")


if __name__ == "__main__":
    main()
