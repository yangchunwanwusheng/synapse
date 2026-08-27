# Run Result JSON Schema（V3-02 冻结版 v1.0.0）

> 本文件与 `src/synapse/eval/schema.py`（机器校验器）同步维护；改 schema 先改这里并升版本。
> 冻结日期：2026-08-28。升级规则：只增不改（新增可选字段=minor；破坏兼容=major，须迁移脚本）。

## 顶层结构

```jsonc
{
  "schema_version": "1.0.0",          // 必填。本 schema 版本
  "config": {...},                    // 必填。Config.to_dict() 全量配置快照（无密钥值，只有 env 变量名）
                                      //        [兼容层] 供 plot_* 旧脚本读取，内容与 manifest.config 相同
  "manifest": {...},                  // 必填。第 1 层：run 元信息
  "result": {...},                    // 必填。第 2 层：聚合计量（命令私有结构 + 通用 metrics 契约）
  "per_item": [...]                   // 可选。第 3 层：逐题记录
}
```

## 第 1 层 manifest（run 元信息）

| 字段 | 类型 | 说明 |
|---|---|---|
| command | string | CLI 子命令与关键参数（如 `hotpot --n 10 --seed 7`） |
| started_utc | string | ISO 8601 UTC（秒精度），run 开始时刻 |
| schema_version | string | 与顶层一致 |
| code_sha | string \| null | `git rev-parse HEAD`；非 git 环境为 null（不猜测） |
| code_dirty | bool | 工作区有未提交改动时 true（数字溯源须警惕） |
| config | object | 配置快照（同顶层 config） |
| model / embed_model | string | chat / embedding 模型名 |
| llm_backend / embedder | string | 后端类型（mock/paratera/...；hash/api/sentence） |
| temperature | number | 采样温度（复现性锚点） |
| seed | int \| null | 题序/随机化 seed |
| dataset | object \| null | `{path, sha256, n_items}`；合成任务为 null |
| env.os / env.python | string | 系统与 Python 版本摘要 |
| env.package_version | string | synapse-mas 包版本 |
| env.uv_lock_sha256 | string \| null | 依赖锁摘要（可复现环境） |

## 第 2 层 result（聚合计量）

命令私有字段不强校验，但任一模式聚合 metrics（`text` / `synapse` / `text_total` / `synapse_total`）
**必须**包含以下 V3-02 计量契约（缺一即校验失败）：

| 字段 | 口径 | 说明 |
|---|---|---|
| llm_input_tokens / llm_output_tokens | chat | 真实 LLM API usage 分列（缺失 fail，禁止静默计 0） |
| transport_bytes | 传输 | Σ `len(to_wire())`：每条消息真实序列化帧长（含全部字段） |
| wire_bytes = logical_bytes | 逻辑 | Σ header+text+nontext：header+payload 恒等式右侧 |
| embed_requests / embed_cache_hits | embed | 嵌入 API 请求（cold）/ 缓存命中（warm）分列 |
| cas_writes / cas_write_bytes | 状态面 | CAS put 次数/字节（共享状态建立成本） |

**恒等式（对账测试锁定）**：`transport_bytes == Σ逐消息 len(to_wire())`；
`logical_bytes == Σ(header_bytes + text_bytes + nontext_bytes)`；`aggregate == Σ trajectory`（全字段守恒）。

## 第 3 层 per_item（逐题记录，可选）

```jsonc
[{ "qid": "...", "question": "...", "gold": "...",
   "text_pred": "...", "text_f1": 0.0,
   "synapse_pred": "...", "synapse_f1": 0.0,
   "retrieved_titles": ["..."], "gold_titles": ["..."], "gold_hit": 1.0 }]
```

CoQA 对话式为 per_conversation（conv_id + questions/golds/preds 数组）。逐题层使 F1/EM 可离线复算。

## 校验器

`python -c "from synapse.eval.schema import validate_run_result; import json,sys; print(validate_run_result(json.load(open(sys.argv[1], encoding='utf-8'))))" runs/<dir>/result.json`

（校验器与 manifest 采集在 `src/synapse/eval/`，落档入口 `synapse.eval.manifest.write_run`。）
