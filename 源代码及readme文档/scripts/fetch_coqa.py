"""抓取 CoQA 1.0 dev 对话并保留全部人工参考答案。

每段对话 = 一组关联连续任务（赛题 M7）。筛选 8–20 轮、故事 ≤420 词。
  uv run python scripts/fetch_coqa.py [N]
"""

from __future__ import annotations

import json
import sys
import urllib.request

from dataset_provenance import sha256_bytes, write_dataset

SOURCE = "https://downloads.cs.stanford.edu/nlp/data/coqa/coqa-dev-v1.0.json"
SOURCE_SHA256 = "dfa367a9733ce53222918d0231d9b3bedc2b8ee831a2845f62dfc70701f2540a"


def main() -> None:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "synapse-dataset-fetch/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    actual_sha = sha256_bytes(raw)
    if actual_sha != SOURCE_SHA256:
        raise RuntimeError(f"CoQA source checksum mismatch: expected {SOURCE_SHA256}, got {actual_sha}")

    doc = json.loads(raw)
    convs = []
    for row in doc["data"]:
        questions = row["questions"]
        answers = row["answers"]
        if not (8 <= len(questions) <= 20 and len(row["story"].split()) <= 420):
            continue
        additional = row.get("additional_answers", {})
        turns = []
        for i, (question, answer) in enumerate(zip(questions, answers)):
            aliases = [refs[i]["input_text"] for refs in additional.values() if i < len(refs)]
            turns.append(
                {
                    "q": question["input_text"],
                    "a": answer["input_text"],
                    "answer_aliases": list(dict.fromkeys(aliases)),
                }
            )
        convs.append(
            {"id": row["id"], "source": row.get("source", ""), "story": row["story"], "turns": turns}
        )
        if len(convs) >= want:
            break

    metadata = write_dataset(
        "data/coqa_sample.json",
        convs,
        {
            "dataset": "CoQA",
            "version": doc.get("version", "1.0"),
            "split": "dev",
            "source_url": SOURCE,
            "source_sha256": actual_sha,
        },
    )
    print(f"saved {len(convs)} conversations -> data/coqa_sample.json")
    print(f"source_sha256={actual_sha} output_sha256={metadata['output_sha256']}")
    for conv in convs:
        print(
            f"  {conv['id']}: {len(conv['turns'])} turns, "
            f"story {len(conv['story'].split())} words, src={conv['source']}"
        )


if __name__ == "__main__":
    main()
