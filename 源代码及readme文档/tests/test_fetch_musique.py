"""离线验证 MuSiQue 过滤计数，避免下载依赖与网络请求。"""

import importlib.util
import io
import json
from pathlib import Path


def test_filter_counts_include_not_answerable(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("fetch_musique", scripts / "fetch_musique.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def row(qid, count=20, support=2):
        return {
            "id": qid,
            "question": "Who?",
            "answer": "Alice",
            "paragraphs": [
                {"title": str(i), "paragraph_text": " fact ", "is_supporting": i < support}
                for i in range(count)
            ],
        }

    rows = [{"answerable": False}, row("short", 19), row("one", support=1), row("ok")]
    response = json.dumps({"rows": [{"row": r} for r in rows]}).encode()
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(response))
    monkeypatch.setattr(module.sys, "argv", ["fetch_musique.py", "1"])
    captured = {}

    def save(path, items, metadata):
        captured.update(items=items, metadata=metadata)
        return {"output_sha256": "test-only"}

    monkeypatch.setattr(module, "write_dataset", save)
    module.main()
    assert [it["id"] for it in captured["items"]] == ["ok"]
    assert captured["metadata"]["filters"] == {
        "not_answerable": 1,
        "paragraph_count_not_20": 1,
        "fewer_than_2_unique_gold_titles": 1,
    }
