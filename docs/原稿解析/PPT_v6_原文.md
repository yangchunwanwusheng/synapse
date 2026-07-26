
===== Slide 1 =====
SYNAPSE
SYNAPSE 队
2026 年 7 月
参赛团队：
完成日期：
面向多智能体协作的低开销通信、状态传递与共享记忆机制
第三届中国研究生操作系统开源创新大赛 · 社区赛题
运行环境：openEuler 24.03-LTS-SP3

===== Slide 2 =====
01
02
03
04
05
项目介绍项目介绍
项目亮点项目亮点
技术难点技术难点
项目测试项目测试
作品演示作品演示

===== Slide 3 =====
项目介绍
从「文本通信冗余」到「语义增量传输」的范式跃迁

===== Slide 4 =====
1.1  设计背景
① 时代趋势
大模型推动智能系统从「单Agent问答」向「多Agent协同执行」演进，RAG、任务规划、代码协作场景对Agent间通信提出更高要求。
② 三大瓶颈
• Token消耗极高：冗长上下文反复重传
• 状态编解码时延：内部↔文本反复转换，语义损耗
• 经验无法沉淀：缺乏跨任务记忆复用，频繁重复推理
③ 工程悖论
潜空间通信直接传Embedding，未压缩的高维向量体积甚至超过原始文本，且在有损信道下静默损坏。
三类现有方案对比
维度
自由文本
JSON工作流
潜空间通信
通信介质
自然语言
结构化文本
全量Embedding
Token开销
极高
高
更高(悖论)
状态传递
完整透传
部分结构化
向量未压缩
记忆复用
无
无
无
可靠性
依赖模型
依赖模型
静默损坏
三类方案均未同时解决「压缩+可靠+复用」

===== Slide 5 =====
1.2  设计目标
G1 通信极简
三档混合协议+残差编码双重压缩，多跳场景Token下降71%–81%
G2 状态无损
非文本状态经句向量预测残差编码，校验回退保障端到端正确
G3 记忆即通信
共享记忆作Wyner-Ziv解码端边信息，实现越用越省正反馈
G4 系统可复现
openEuler原生容器化部署，CLI一键实验，数据全程可溯源
① 共享记忆
积累 (M↗)
② 接收端
状态预测 Ŷ
③ 语义残差
编码 Z=Y−Ŷ
④ 通信开销
降低 (Residual↓)
Memory↗→Predict↑
→Residual↓→Comm↓

===== Slide 6 =====
1.3  较同类产品的优势
五维差异化优势对比
#
优势维度
SYNAPSE
同类方案
1
通信压缩机理
优化通信目标（减少需表达信息）
仅优化数据格式（压缩完整信息）
2
有损信道可靠性
VLC校验回退，保障端到端正确
静默损坏无防护
3
记忆角色
边信息源（参与通信编码）
静态知识库（仅查询）
4
理论根基
Wyner-Ziv（动态增长边信息）
Semantic R-D（静态能力假设）
5
工程实证
openEuler原型+三数据集因果消融
多为仿真/理论分析
SYNAPSE 实现了「压缩 + 可靠 + 复用」三合一
动态边信息建模 + 工程化实证 = 团队原创贡献

===== Slide 7 =====
1.4  作品原创性情况说明
1
原创一·理论建模
首次将多Agent协作通信形式化为「带增长边信息的Wyner-Ziv条件率失真编码」，揭示共享记忆作为解码端边信息的通信压缩机理，突破传统静态能力假设。
2
原创二·残差编码
提出句向量预测残差编码，仅传「惊讶残差」Z=Y−Ŷ；校验回退机制彻底解决潜空间通信「向量体积过大」与「有损传输静默出错」两大工程痛点。
3
原创三·统一架构
共享记忆同时作为通信媒介与边信息来源，实现「记忆即通信」统一架构，使历史经验从静态存储跃升为通信压缩的核心驱动力。
4
原创四·工程闭环
openEuler 24.03-LTS-SP3完整可运行原型，真实复杂数据集+因果消融实验，提供字节级可复现证据，验证系统级高效性与鲁棒性。
代码原创声明
本作品核心代码（结构化协议、ResidualCodec、HybridRetriever、ToMPredictor、CAS状态平面、ABRunner评测框架）均由参赛团队独立设计与实现，未使用任何第三方多Agent通信框架的成品代码。
理论基础Wyner-Ziv分布式源编码属公知信息，本作品在其上的动态边信息建模与工程化为团队原创贡献。
第三方依赖仅限：smolagents（Agent运行时底座）、GLM-Embedding-3（句向量）等基础库。
所有实验数据完整存档于 runs/ 目录，确保实验过程可溯源、可复验。

===== Slide 8 =====
项目亮点
三重机制 × 五模块架构 × 一条优化闭环

===== Slide 9 =====
2.1  功能亮点
机制一·结构化协议
Message Schema + 三档混合协议(residual/embedding/text)，按预测基相似度预判选档
机制二·非文本状态传递
CAS内容寻址+残差编码，高维(dim=1536)双字节索引，仅传预测外增量Z=Y−Ŷ
机制三·共享记忆复用
三路混合检索+ToM预测+记忆演化链(links/superseded)，CoQA命中率0.921
⑤ 评测与度量 eval/
A/B双模式·Metrics多维统计·可复现
④ 共享记忆与检索 memory/
HybridRetriever三路混合·ToMPredictor·演化链巩固器
③ 状态交换数据平面 stateplane/
CAS内容寻址·残差编解码·三档协议·VLC校验回退
② 协议解析与调度 protocol/
Message Schema·CNR能力运行时门控·Scheduler路由
① 多Agent运行时 runtime/
Planner·Retriever·Executor·Summarizer
数据流↓
记忆反哺↑
五模块覆盖赛题全要求：低开销通信 + 非文本状态 + 共享记忆复用

===== Slide 10 =====
2.2  其它亮点
✓
异构Agent兼容（CNR协商）
能力声明→能力发现→编码协商三阶段；按 hidden>residual>embedding>text 优先级自动选择通信方式，支持异构模型后端无缝协作与降级。
✓
离线/在线双运行模式
MockChatModel+HashEmbedder离线确定性自检（零成本零网络）；OpenAIServerModel真实API调用；两种模式共享同一Agent构建流程，仅在模型初始化阶段切换。
✓
openEuler原生容器部署
基于openeuler/openeuler:24.03-lts-sp3镜像约597MB，非root(uid 1001)运行提高安全性；内置HEALTHCHECK(synapse smoke)，docker run --rm 一键完成自检。
✓
CodeAct自主执行（赛题M11加分）
Executor Agent由LLM生成可执行Python代码，经LocalPythonExecutor在受限环境完成执行；实现从「文本推理」到「任务操作」的能力跃迁。

===== Slide 11 =====
技术难点
在有损语义信道上实现「低开销」与「高可靠」的平衡

===== Slide 12 =====
3.1  预测残差编码（难点一）

===== Slide 13 =====
3.2  Verified Lossy Coordination（难点二）

===== Slide 14 =====
项目测试
三层递进验证 · 三数据集 · 因果消融

===== Slide 15 =====
4.1  项目测试结果说明
结论：Token节省 10.65%–80.9%(多跳71%–81%)，MuSiQue/CoQA答案质量提升，HotpotQA压缩不牺牲召回(金标0.9)
① 通信效率与答案质量（Qwen3-235B-A22B 后端）
数据集
类型
最优配置
Token节省
synapse F1
text F1
ΔF1
HotpotQA
bridge多跳
N=10,single,k=3
71.09%
0.680
0.780
−0.100
MuSiQue
链式多跳
N=3,twohop,k=3
80.9%
0.857
0.524
+0.333
CoQA
对话式QA
3组对话
10.65%
0.684
0.656
+0.027
压缩不损质 · 残差97.6%可因果归因 · 越长越省

===== Slide 16 =====
作品演示
CLI一键实验 · openEuler容器一键自检

===== Slide 17 =====
5.1  作品演示播放
五条核心 CLI 命令覆盖完整演示链路：
$ uv run synapse smoke
离线自检（零网络零成本）
输出 SMOKE PASSED，5项验证全过
$ uv run synapse ab --rounds 10
text/synapse双模式A/B
直观对比Token与字节开销
$ uv run synapse hotpot --n 10
HotpotQA真实多跳
验证RAG场景压缩效果
$ uv run synapse signal --rounds 5
残差收缩验证
观测残差随记忆积累下降
$ uv run synapse m7 --g1 5 --g2 5
跨任务记忆复用
G2命中率≥G1，证明经验迁移
openEuler 容器一键演示：
$ docker run --rm synapse:latest
openeuler:24.03-lts-sp3 · ~597MB · 非root(uid 1001)
内置 HEALTHCHECK · 自动输出 SMOKE PASSED

===== Slide 18 =====
THANKS
SYNAPSE 队
2026 年 7 月
参赛团队：
完成日期：
期待评委提问与指导
SYNAPSE —— 让多智能体协作「越用越省、越用越聪明」