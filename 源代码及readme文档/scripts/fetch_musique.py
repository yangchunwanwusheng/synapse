"""抓取 MuSiQue（第二真实多跳数据集，EH2）到 data/musique_sample.json。

MuSiQue（`dgslibisey/MuSiQue`）每题 20 段、仅 2 段金标（is_supporting）→ 干扰占 90%，
比 HotpotQA(10 段/2 金标) 更稀疏，更强测通信效率。输出与 HotpotQA 同 schema → 复用 load_hotpot。
取 answerable 题前 N。
  uv run python scripts/fetch_musique.py [N]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from urllib.parse import urlencode

from dataset_provenance import write_dataset

DATASET = "dgslibisey/MuSiQue"
REVISION = "c8f4f8c9465fb69d31a8eae894c3fd509c4ca321"
BASE = "https://datasets-server.huggingface.co/rows"


def main() -> None:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    items = []
    filtered = {"paragraph_count_not_20": 0, "fewer_than_2_unique_gold_titles": 0}
    for off in range(0, 1200, 100):
        query = urlencode(
            {
                "dataset": DATASET,
                "config": "default",
                "split": "validation",
                "revision": REVISION,
                "offset": off,
                "length": 100,
            }
        )
        with urllib.request.urlopen(f"{BASE}?{query}", timeout=60) as r:
            rows = json.load(r)["rows"]
        for x in rows:
            row = x["row"]
            if not row.get("answerable", True):
                continue
            ps = row["paragraphs"]
            gold = [p["title"] for p in ps if p.get("is_supporting")]
            if len(ps) != 20:
                filtered["paragraph_count_not_20"] += 1
                continue
            if len(set(gold)) < 2:
                filtered["fewer_than_2_unique_gold_titles"] += 1
                continue
            paragraphs = [{"title": p["title"], "text": p["paragraph_text"].strip()} for p in ps]
            items.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "answer_aliases": row.get("answer_aliases", []),
                    "question_decomposition": row.get("question_decomposition", []),
                    "type": "musique",
                    "level": "multihop",
                    "gold_titles": list(dict.fromkeys(gold)),
                    "paragraphs": paragraphs,
                }
            )
        if len(items) >= want:
            break
    items = items[:want]
    metadata = write_dataset(
        "data/musique_sample.json",
        items,
        {"dataset": DATASET, "revision": REVISION, "split": "validation", "filters": filtered},
    )
    avg_p = sum(len(it["paragraphs"]) for it in items) / max(1, len(items))
    avg_w = sum(len(p["text"].split()) for it in items for p in it["paragraphs"]) / max(1, len(items))
    print(
        f"saved {len(items)} items -> data/musique_sample.json (avg {avg_p:.0f} paras, {avg_w:.0f} ctx words/题)"
    )
    print(f"revision={REVISION} sha256={metadata['output_sha256']} filtered={filtered}")
    for it in items[:3]:
        print(f"  {it['id'][:16]}: gold={it['gold_titles']}")


if __name__ == "__main__":
    main()
