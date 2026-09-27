# AI Eval Workspace V1 验收记录

验证日期：2026-09-26。已完成工程、官方 IFEval 接入、离线评分及统计分析。没有调用 DeepSeek 或 Qwen API，没有推理费用，没有进行付费全量测试。

## 架构与职责

```text
ai_evals/
├── README.md / .env.example / pyproject.toml
├── cli.py
├── core/
│   ├── result_schema.py
│   ├── runner.py
│   └── run_manager.py
├── providers/
│   ├── openai_compatible.py
│   ├── deepseek.py
│   └── qwen.py
├── evals/ifeval/
│   ├── data/input_data.jsonl
│   ├── vendor/（官方 scorer、测试、LICENSE、manifest）
│   ├── config/deepseek.json / qwen.json
│   ├── dataset.py
│   ├── grader.py
│   └── analysis.py
├── tests/test_workspace.py
├── scripts/validate_offline.py
├── runs/
└── reports/
```

Core 定义通用任务、provider 返回值、raw 记录和运行流程。Runner 只执行任务并保存结果，单条错误不会中断 batch。RunManager 创建唯一 ID、保存配置与任务快照、追加 raw、识别成功样本并控制同一 run 的进程锁。它不引用 IFEval。

Providers 负责厂商模型 ID、API 参数、HTTP 错误、完整响应、token usage 和 latency；两个厂商复用同一种 HTTP 协议实现。API key 只从环境读取。

IFEval suite 独立负责官方字段读取与数据统计、官方评分调用、逐约束判定证据、Overall/Slice/分歧统计和人工分析导出。

额外文件的必要性：`tasks.jsonl` 固定所选任务，保证续跑不受数据选择变化影响；`grading.json` 记录评分输入的 raw SHA256，阻止续跑后误用旧评分。未引入平台、队列或数据库。

## IFEval 数据与评分

- 实际样本：541；约束：834；instruction type：25。
- 原始字段：key、prompt、instruction_id_list、kwargs；数据字节及字段未修改。
- 单 instruction：305；multi-instruction：236；1/2/3 条约束的 prompt 数分别为 305/179/57。
- 完整 25 类分布：[ifeval_dataset_summary.md](ifeval_dataset_summary.md)；可计算版本为同名 CSV/JSON。
- 每条 prompt 的约束数：[ifeval_prompt_inventory.csv](ifeval_prompt_inventory.csv)。
- [官方源码固定版本](https://github.com/google-research/google-research/tree/e6890f85757dd84e27ca6df2dd30651dafad28e0/instruction_following_eval)，Apache-2.0，原始文件与 SHA256 清单保留在 vendor。

strict 直接检查原始回复；loose 直接使用官方实现的 8 个文本候选（原文、去星号、去首行/尾行/首尾行及其组合）。每个 instruction 独立判定，prompt 为所有判定的逻辑 AND。instruction 总分按约束数微平均。

评分产物保留原 raw 字段，以及 instruction id、原始 kwargs、解析参数、规则描述、逐条 strict/loose 结果、prompt 失败项。该追溯说明的是规则判定依据，不伪造模型失败原因。运行错误、评分器错误均不自动等同于模型失败。

## 数据链路

`官方 Dataset → IFEval Task → 通用 Runner → Provider → raw.jsonl → IFEval Grader → scored.jsonl → Analysis`

每个 run 保存 `config.json`、`tasks.jsonl`、`raw.jsonl`；评分后增加 `scored.jsonl`、`grading.json`；分析后增加 `summary.json`。分析目录保存 Overall、Slice、strict/loose 四组对照、分歧 cases 和人工分析入口。

重新评分只读取已保存输出，不创建模型请求；raw SHA256 在验证前后保持不变。重复 attempt 不重复计入评分：采用第一次成功，或没有成功时的最后一次错误。分歧只比较双方都已评分的匹配 sample。

## 已实际完成的验证

工作区测试 **18 passed**；官方原始测试 **48 passed**。机器记录见 `test_results.xml` 和 `official_test_results.xml`。

| 验收项 | 证据 / 结果 |
|---|---|
| IFEval 加载与分布 | 541 条、834 约束、25 类；原始文件 SHA256 检查通过 |
| 官方 scorer 独立运行 | 官方 48 项测试通过；全部 541 条原始样本使用固定离线输出，适配层结果与官方 strict/loose 函数逐项一致 |
| DeepSeek provider | HTTP mock 检验 deepseek-flash、请求内容、非思考参数、响应、usage、finish_reason 和 latency |
| Qwen provider | HTTP mock 检验 qwen3.8-max-0902、请求内容、非思考参数、响应、usage、finish_reason 和 latency |
| 单条 / 小批量 | Runner 单样本与多样本路径、两个 provider 的 CLI 小批量流程通过 |
| 基础 API 错误 | 429、超时、非 JSON、缺失 content；无隐藏重试，错误响应密钥防御性脱敏 |
| Raw 完整性 | Schema 字段、扩展 metadata、完整 response、attempt；失败后继续，重试仅追加 |
| 独立重新评分 | 多次评分一致，raw 不变；CLI 评分时无 API key 仍可运行 |
| 断点续跑 | KeyboardInterrupt 后恢复；成功样本跳过，失败样本追加；同一 run 锁验证通过 |
| Overall / Slice | 四指标、约束级 strict/loose 分布、零分母 null、错误独立计数 |
| Disagreement | 四种组合各 1 条；严格/宽松各导出 2 条分歧，包含双边原文和完整评分 |
| Failure Analysis | 必需字段与允许 failure_source 已提供；重跑不会覆盖人工标注 |
| Coverage / Targeted | 仅空表头与字段说明，无新增 targeted case |
| 统一报告 | eval_report.md 包含全部 16 个章节；真实基线及能力发现仍为 TODO |
| 新 suite 可扩展 | Core 不引用 IFEval，接受普通 Task 及扩展 metadata；新 suite 独立接线即可 |
| 避免意外全量 | CLI 拒绝 --limit 541，拒绝时不初始化 provider |

工作区自动化测试与演示脚本禁止 socket 连接。离线产物摘要见 [local_validation.json](local_validation.json)，保存了两个 `offline-fixture-*` run 的位置。这些输出是软件测试 fixture，不能作为任何真实模型的评分结果。

## 实际问题、限制及决策

1. Windows 沙箱内公开源码下载遇到 TLS 凭据错误，依赖安装也出现卡住；获准后在工作区虚拟环境完成下载和安装。当前准备及离线测试均已成功。
2. 官方 requirements 中使用 `absl` 名称；实际安装正确发行包 `absl-py`。官方句子计数需要 NLTK `punkt_tab`，已下载至项目目录并验证。
3. 默认选择非思考模式、temperature=0、4096 tokens、单 user message；这是初始实验配置，尚未用真实 API 核验账号权限、区域端点或模型可用性。原始参数均会记录，不隐式切换模型。
4. 不新增真实 baseline、不推导模型能力结论、不创建 targeted evaluation 样本。本轮模型请求为 0、推理费用为 0；联网仅用于公开资料、源码和依赖准备。
5. API 超时或服务端完成到本地落盘之间中断，无法保证绝不重复计费；没有服务端幂等保证时不作此承诺。损坏 JSONL 会停止并保留原件，V1 不自动修复。
6. 评分率仅基于成功生成且评分成功的样本，必须连同覆盖率与错误数解释。失败重试及筛选可能引入选择偏差。
7. 官方规则不评价事实或内容质量；loose 可能让不同约束在不同候选文本上分别通过。固定随机种子用于重评分复现，仍需保留依赖版本。
8. 人工标注 CSV 不自动合并，新结果使用新分析目录；重评分会更新派生评分文件，需要保留历史评分时先另存。这些限制已写入 README。

当前没有待确认才能完成 V1 的决策。若后续开展真实 smoke test，需要配置相应密钥和账户地域端点，再执行 README 中的单条命令。
