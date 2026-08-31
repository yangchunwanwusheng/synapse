"""集中配置（配置驱动，无硬编码超参/路径/密钥）。

API key 等机密只从环境变量 / .env 读取，严禁写入代码或提交 Git。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Config:
    # ---- 表示 / 残差 ----
    embed_dim: int = 64  # 句向量维度（骨架小维；真实路径用 384/1024）
    quant_grid: int = 64  # Y 量化网格（checksum 在此网格上；与 int8 残差范围匹配）
    sparsity_eps: int = 0  # 旧逐分量阈值（保留向后兼容；率失真编码改用 verify_threshold）
    verify_threshold: float = 0.97  # 语义失真目标 = cos(Ŷ,Y) 下界；编码到此即止，低于即回退
    n_facts: int = 40  # Retriever "长证据"事实条数（放大纯文本透传冗余；配置驱动）

    # ---- 检索 / 记忆 ----
    retrieval_semantics: str = "v3-04"  # 检索语义版本（v3-04 起：链接扩展召回历史版本 + 复用计数=被消费前 k 个）；历史 run（pre-v3-04）不可与本版本横向比较（manifest 落档）
    retrieval_k: int = 5
    hit_threshold: float = 0.15  # 检索 top 分 > 阈值 记为记忆命中
    w_keyword: float = 0.3  # 混合检索权重
    w_tag: float = 0.2
    w_semantic: float = 0.5

    # ---- 运行 ----
    rounds: int = 10  # 连续任务轮数（赛题 M9 ≥10）
    seeds: tuple[int, ...] = (0, 1, 2)

    # ---- 消融开关（对照实验用；默认全 False = 完整 SYNAPSE，对既有 run 零影响）----
    abl_no_tom: bool = False  # 关预测基(b_hat=None) → 残差不因经验变准
    abl_no_consolidation: bool = False  # 关跨任务巩固 → 记忆不固化
    abl_no_residual: bool = False  # 发全量量化向量（无预测/无稀疏）→ 字节应更大
    abl_no_checksum: bool = False  # 关语义校验/回退 → 失配时端到端正确性应降
    abl_no_memory: bool = (
        False  # B3-no-mem：每任务清空跨任务记忆 → 证残差率下降因果源于记忆（P0-1 假设3 归因 ablation）
    )

    # ---- 真通路（V3-04，Issue #148746）----
    residual_true_path: bool = False  # True=残差/VLC 真数据通路（L1+L2 两级校验、重建检索恢复消费、三档真实分叉、CNR 驱动）；False=旧旁路路径（回归防护，翻转默认值须独立提交+真实评测重跑）
    base_policy: str = "oracle"  # V3-04 ToM 选基三档：oracle=发送方以Y择优(乐观) | query_top1=检索top-1(接收方可复现) | learned=topic原型(聚合学习式)；字节按档分列报告
    residual_project_dim: int = 0  # >0 时残差/索引在 JL 随机投影域（确定性共享投影，残差分量数≈按维数比下降）；0=原域；效果需真实 API 验证

    # ---- 真实数据集 QA ----
    qa_story_mode: str = "full"  # [CoQA] full=整段故事入prompt(历史口径) | sentences=句级检索top-k(qa_sentences_k 真实生效，V3-04 附带修复)
    qa_sentences_k: int = (
        4  # [CoQA] synapse 每轮检索的故事句子数（非文本选择；qa_story_mode=sentences 时生效）
    )
    qa_history_k: int = 2  # [CoQA] synapse 每轮复用的相关历史 Q&A 数（紧凑记忆，非全量透传）
    qa_para_k: int = 3  # [HotpotQA] synapse 每题检索的相关段落数（10 段中只取 k，丢干扰段）
    qa_retrieval: str = "single"  # [HotpotQA] "single"=单跳问题检索 | "twohop"=两跳(用第一跳内容补检索桥接段)

    # ---- 后端（骨架默认全离线 mock；真实路径 = Paratera 算力平台，OpenAI 兼容）----
    llm_backend: str = "mock"  # "mock" | "paratera"
    embedder: str = "hash"  # "hash" | "sentence" | "api"
    model: str = "Qwen3-235B-A22B-Instruct-2507"  # MoE(22B激活)+Instruct(非thinking)；2026-07-08 从 30B-A3B 切换（账户权限失效）
    api_base: str = "https://llmapi.paratera.com/v1"
    api_key_env: str = "PARATERA_API_KEY"
    temperature: float = 0.0  # 复现性：真实 LLM 固定 0（实验协议 §LLM 条件块 / L5）
    embed_model: str = "GLM-Embedding-3"  # embedder=api 时 Paratera 句向量模型（无 GPU/torch）

    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: str | None = None) -> Config:
    """从 YAML 覆盖默认配置；未指定 path 时返回默认（smoke 零依赖）。

    V3-02 fail-fast（P1-6）：path 显式给出后，文件缺失 / YAML 语法错误 / 未知键 /
    字段类型不符一律抛 ConfigError——静默回退默认配置会让实验以为自己跑在
    configs/vectorengine.yaml 上而实际全是 mock，属于证据链事故。
    """
    if not path:
        return Config()
    if not os.path.isfile(path):
        raise ConfigError(f"配置文件不存在或不是普通文件（目录/不可读同样拒绝）: {path}")
    try:
        import yaml  # 可选依赖
    except ImportError as e:
        raise ConfigError(f"pyyaml 未安装（uv sync --extra config），无法加载 {path}") from e
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML 解析失败: {path}\n{e}") from e
    except OSError as e:  # 权限/编码等 IO 层错误同样受控（审查 P0-2）
        raise ConfigError(f"配置文件读取失败: {path}\n{e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件顶层必须是映射（键值对）: {path}")
    unknown = sorted(set(data) - set(Config.__dataclass_fields__))
    if unknown:
        raise ConfigError(f"配置含未知字段 {unknown}（疑似拼写错误，可用字段见 Config 定义）: {path}")
    _check_types(path, data)
    known = dict(data)
    if "seeds" in known:
        known["seeds"] = tuple(known["seeds"])
    return Config(**known)


class ConfigError(ValueError):
    """配置加载失败（fail-fast，不静默回退默认）。"""


def _is_int(v) -> bool:
    return type(v) is int  # 排除 bool（bool 是 int 子类；审查 P0-2：rounds: true 不得通过）


def _check_types(path: str, data: dict) -> None:
    import dataclasses as dc

    for f in dc.fields(Config):
        if f.name not in data:
            continue
        val = data[f.name]
        if val is None:  # Config 无 Optional 字段：null 一律拒绝
            raise ConfigError(f"配置字段 {f.name} 不接受 null: {path}")
        t = f.type
        if t == "int" and not _is_int(val):
            raise ConfigError(f"配置字段 {f.name} 期望 int，实得 {type(val).__name__}: {path}")
        if t == "float" and type(val) not in (int, float):
            raise ConfigError(f"配置字段 {f.name} 期望数值，实得 {type(val).__name__}: {path}")
        if t == "str" and not isinstance(val, str):
            raise ConfigError(f"配置字段 {f.name} 期望 str，实得 {type(val).__name__}: {path}")
        if t == "bool" and not isinstance(val, bool):
            raise ConfigError(f"配置字段 {f.name} 期望 bool，实得 {type(val).__name__}: {path}")
        if t == "tuple[int, ...]":
            if not isinstance(val, (list, tuple)):
                raise ConfigError(f"配置字段 {f.name} 期望列表，实得 {type(val).__name__}: {path}")
            for el in val:
                if not _is_int(el):
                    raise ConfigError(f"配置字段 {f.name} 元素须为 int，实得 {type(el).__name__}: {path}")
