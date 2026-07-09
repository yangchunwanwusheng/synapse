"""CoQA 真实数据集 QA 管线测试（离线 mock 验通信/记忆/token 管线；F1 与数据集逻辑纯离线）。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from dataclasses import replace  # noqa: E402

from synapse.config import Config  # noqa: E402
from synapse.qa.dataset import load_conversations, load_hotpot, split_sentences  # noqa: E402
from synapse.qa.pipeline import (  # noqa: E402
    run_synapse,
    run_synapse_hotpot,
    run_text,
    run_text_hotpot,
)
from synapse.qa.scoring import f1  # noqa: E402
from synapse.qa.stats import bootstrap_ci, mean_std, paired_winloss  # noqa: E402


def test_f1_normalization():
    assert f1("white", "white") == 1.0
    assert f1("the white cat", "a white cat") == 1.0  # 冠词归一
    assert f1("yes", "no") == 0.0
    assert 0 < f1("white cat", "white dog") < 1


def test_coqa_dataset_loads():
    convs = load_conversations(n=2)
    assert convs and convs[0].turns and convs[0].story
    assert len(split_sentences(convs[0].story)) >= 3


def test_qa_pipelines_offline_plumbing():
    # mock LLM：答案非真实，但通信/记忆/token 双向计数管线必须跑通
    cfg = Config()
    conv = load_conversations(n=1)[0]
    mt = run_text(conv, cfg)["metrics"]
    ms = run_synapse(conv, cfg)["metrics"]
    assert mt.messages > 0 and ms.messages > 0
    assert mt.llm_total_tokens > 0 and ms.llm_total_tokens > 0  # 输入+输出 token 计数生效
    assert ms.nontext_transfers > 0  # synapse 非文本状态传递（M4）
    assert ms.memory_queries > 0  # synapse 检索共享记忆（M6）


def test_hotpot_dataset_loads():
    items = load_hotpot(n=2)
    assert items and items[0].paragraphs and items[0].gold_titles
    assert len(items[0].paragraphs) == 10  # distractor 设定：10 段
    assert all(g in {p.title for p in items[0].paragraphs} for g in items[0].gold_titles)


def test_hotpot_pipelines_offline_plumbing():
    # synapse 只检索 k 段 → 应答输入 token 必 < 基线塞全 10 段（机制核心：丢干扰省 token）
    cfg = replace(Config(), qa_para_k=3)
    items = load_hotpot(n=3)
    mt = run_text_hotpot(items, cfg)["metrics"]
    rs = run_synapse_hotpot(items, cfg)
    ms = rs["metrics"]
    assert mt.llm_total_tokens > 0 and ms.llm_total_tokens > 0
    assert ms.llm_input_tokens < mt.llm_input_tokens  # 检索 k 段 < 全 10 段
    assert ms.nontext_transfers == len(items)  # 每题一次句柄传递（M4）
    assert ms.text_bytes == 0 and mt.text_bytes > 0  # synapse 不在 agent 间透传全文
    assert 0.0 <= rs["gold_recall"] <= 1.0


def test_hotpot_retrieval_modes():
    # 三种检索模式都应跑通、k 固定 → 输入 token 量级相当（差异只在取哪些段）
    items = load_hotpot(n=4)
    recalls = {}
    for mode in ("single", "twohop", "bridge"):
        cfg = replace(Config(), qa_para_k=3, qa_retrieval=mode)
        rs = run_synapse_hotpot(items, cfg)
        assert rs["metrics"].nontext_transfers == len(items)
        assert 0.0 <= rs["gold_recall"] <= 1.0
        recalls[mode] = rs["gold_recall"]
    assert set(recalls) == {"single", "twohop", "bridge"}


def test_bridge_pulls_title_mentioned_para():
    # 词法桥接：构造"段A正文提及段B标题"，bridge 模式应把 B 拉进来（单跳问题相似度选不到 B）
    from synapse.config import Config as _C
    from synapse.memory.store import MemoryStore
    from synapse.memory.retrieval import HybridRetriever
    from synapse.stateplane.embedding import HashEmbedder
    from synapse.qa.pipeline import _retrieve_paras

    emb = HashEmbedder(dim=64)
    store = MemoryStore(emb)
    store.write(
        source_agent="c",
        task_topic="q",
        summary="Alpha",
        content="Alpha mentions Bridgetown directly.",
        kind="evidence",
    )
    store.write(
        source_agent="c",
        task_topic="q",
        summary="Bridgetown",
        content="An unrelated capital city description.",
        kind="evidence",
    )
    store.write(
        source_agent="c",
        task_topic="q",
        summary="Noise",
        content="totally different distractor text.",
        kind="evidence",
    )
    retr = HybridRetriever(store, emb, _C())
    got = {u.summary for u in _retrieve_paras(retr, store, "Tell me about Alpha", 2, "bridge")}
    assert "Bridgetown" in got  # 标题被 Alpha 正文提及 → 桥接命中


def test_stats_helpers():
    ms = mean_std([1.0, 2.0, 3.0])
    assert ms["mean"] == 2.0 and ms["n"] == 3 and ms["std"] > 0
    assert mean_std([5.0])["std"] == 0.0  # 单点 std=0
    lo, hi = bootstrap_ci([0.0, 0.1, 0.2, 0.1, 0.0], seed=0)  # 可复现
    assert lo <= hi and lo == bootstrap_ci([0.0, 0.1, 0.2, 0.1, 0.0], seed=0)[0]
    wl = paired_winloss([0.0, 1.0, 0.5], [1.0, 1.0, 0.0])  # 胜/平/负
    assert wl == {"syn_win": 1, "tie": 1, "syn_loss": 1}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"ALL {len(fns)} QA TESTS PASSED")
