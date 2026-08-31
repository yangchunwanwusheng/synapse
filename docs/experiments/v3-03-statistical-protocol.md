# V3-03 统计实验预注册协议

状态：代码与正式跑批前冻结。任何参数变更必须以新提交记录原因，既有结果不得据此回选参数。

## 数据与评分

- HotpotQA：`hotpotqa/hotpot_qa` distractor validation，revision
  `1908d6afbbead072334abe2965f91bd2709910ab`。
- MuSiQue：`dgslibisey/MuSiQue` validation，revision
  `c8f4f8c9465fb69d31a8eae894c3fd509c4ca321`；仅保留 answerable、恰好 20 段且至少
  2 个唯一 supporting title 的题，过滤计数写入 sidecar。
- CoQA：官方 1.0 dev 文件，源 SHA-256
  `dfa367a9733ce53222918d0231d9b3bedc2b8ee831a2845f62dfc70701f2540a`，保留主答案和
  3 组额外人工答案。
- 主质量指标为规范化后的多参考 max F1；次指标为多参考 max EM。逐题保存预测、全部参考、
  F1 与 EM，聚合值必须可由逐题记录重新计算。
- 规范化顺序为小写 → 去标点 → 去冠词 → 压空白，与
  [CoQA 官方脚本](https://nlp.stanford.edu/data/coqa/evaluate-v1.0.py) 和
  [HotpotQA 官方脚本](https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py)
  的 `white_space_fix(remove_articles(remove_punc(lower(s))))` 一致（从内向外执行）。
  `a-team` → `ateam`、`the.best` → `thebest`、`th-e` → 空串已加入 golden 测试。
  此处是项目统一的 max-over-references 口径，不宣称完整复刻官方排行榜评测：
  CoQA 官方多参考聚合含 leave-one-out 平均；HotpotQA 另有特殊答案及空答案处理。
- sidecar 的 `output_sha256` 与数据文件重算哈希不一致时，manifest 标记
  `sidecar stale`、`provenance_verified=false`；保留的 revision 仅为原 sidecar 声明，
  不代表当前文件已验证。MuSiQue 过滤计数覆盖已扫描页面，包含 `not_answerable`，
  不包含满足条件后因 N 截断而未选入的题。

## 配对与统计单位

- 同一题、同一模型、同一配置和 seed 下比较 Text(A) 与 SYNAPSE(B)。正式跑批要求固定
  seed 洗牌后按题交替 AB/BA，并将实际执行序列随 run 落档。
  **待正式跑批接入**：当前 `alternating_order()` 仅提供序列生成与单测，harness/CLI
  仍整批先 Text 后 SYNAPSE，尚未执行逐题 AB/BA 或保存该执行序列。
  N=10 探针之前必须接入 runner 并验收实际调用顺序和落档，不能将生成器视作已经执行。
- 独立抽样单位是“题”，不是同题的重复 API 调用。先在题内对重复运行求均值，再对题目做
  cluster bootstrap；报告题间方差和题内运行方差。方差使用 `pvariance`（分母 N），
  是描述性总体方差，不是无偏方差分量估计，不用于统计推断。
- 95% percentile bootstrap 使用 5,000 次重采样和固定 seed 0。
- 预注册非劣界：`δ = 0.03 F1`。仅当配对差值 `SYNAPSE - Text` 的 95% CI 下界不低于
  `-0.03` 时称为“在本协议与样本下非劣”；否则报告未证实或劣于基线，不改界值。

## 分阶段跑批

1. 两个数据集各 N=10 运行方向探针，只用于检查执行链、成本和效应方向，不升级为项目结论。
2. MuSiQue N≥100 正式跑批；逐题结果、执行序列、失败样本、数据 sidecar 与 manifest 全部入库。
3. API/数据失败不得丢弃题目；记录失败类别并在聚合分母中明确展示。不得只选择最佳 k、seed 或 run。

外部模型额度或凭据不可用时，只合并统计与数据基础设施，不生成或宣称正式实验结果。
