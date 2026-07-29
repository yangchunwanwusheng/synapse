"""抓取 CoQA 验证集对话到 data/coqa_sample.json（经 HuggingFace datasets-server，无需重依赖）。

每段对话 = 一组关联连续任务（赛题 M7）。筛选 8–20 轮、故事 ≤420 词，便于小规模真实实验。
  uv run python scripts/fetch_coqa.py [N]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = (
    "https://datasets-server.huggingface.co/rows?dataset=stanfordnlp%2Fcoqa&config=default&split=validation"
)


def main() -> None:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    convs = []
    for off in range(0, 500, 100):
        with urllib.request.urlopen(f"{BASE}&offset={off}&length=100", timeout=60) as r:
            rows = json.load(r)["rows"]
        for x in rows:
            row = x["row"]
            q = row["questions"]
            a = row["answers"]
            ai = a["input_text"] if isinstance(a, dict) and "input_text" in a else a
            if 8 <= len(q) <= 20 and len(row["story"].split()) <= 420:
                convs.append(
                    {
                        "id": f"coqa-{x['row_idx']}",
                        "source": row.get("source", ""),
                        "story": row["story"],
                        "turns": [{"q": q[i], "a": ai[i]} for i in range(len(q))],
                    }
                )
        if len(convs) >= want:
            break
    convs = convs[:want]
    os.makedirs("data", exist_ok=True)
    json.dump(
        convs,
        open(os.path.join("data", "coqa_sample.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"saved {len(convs)} conversations -> data/coqa_sample.json")
    for c in convs:
        print(
            f"  {c['id']}: {len(c['turns'])} turns, story {len(c['story'].split())} words, src={c['source']}"
        )


if __name__ == "__main__":
    main()
