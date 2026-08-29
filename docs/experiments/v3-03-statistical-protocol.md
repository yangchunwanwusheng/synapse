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
- 主质量指标为官方规范化后的多参考 max F1；次指标为多参考 max EM。逐题保存预测、全部参考、
  F1 与 EM，聚合值必须可由逐题记录重新计算。

## 配对与统计单位

- 同一题、同一模型、同一配置和 seed 下比较 Text(A) 与 SYNAPSE(B)。固定 seed 洗牌后按题交替
  AB/BA，执行序列随 run 落档。
- 独立抽样单位是“题”，不是同题的重复 API 调用。先在题内对重复运行求均值，再对题目做
  cluster bootstrap；报告题间方差和题内运行方差。
- 95% percentile bootstrap 使用 5,000 次重采样和固定 seed 0。
- 预注册非劣界：`δ = 0.03 F1`。仅当配对差值 `SYNAPSE - Text` 的 95% CI 下界不低于
  `-0.03` 时称为“在本协议与样本下非劣”；否则报告未证实或劣于基线，不改界值。

## 分阶段跑批

1. 两个数据集各 N=10 运行方向探针，只用于检查执行链、成本和效应方向，不升级为项目结论。
2. MuSiQue N≥100 正式跑批；逐题结果、执行序列、失败样本、数据 sidecar 与 manifest 全部入库。
3. API/数据失败不得丢弃题目；记录失败类别并在聚合分母中明确展示。不得只选择最佳 k、seed 或 run。

外部模型额度或凭据不可用时，只合并统计与数据基础设施，不生成或宣称正式实验结果。
