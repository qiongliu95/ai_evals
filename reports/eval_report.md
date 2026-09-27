# AI Eval Workspace — IFEval Evaluation Report

状态：V1 工程已建立；尚未执行真实模型基线。离线验证是软件测试，不是模型表现证据。

## 1. Evaluation Objective

测量指定模型对 IFEval 可自动验证指令的遵循情况，保留逐约束证据，支持重评分、分歧抽样和人工复核。当前不评价事实正确性、开放式任务质量或总体模型能力。

## 2. System Under Test

| Provider | Requested model ID | Live validation |
|---|---|---|
| DeepSeek | deepseek-flash | TODO |
| Qwen | qwen3.8-max-0902 | TODO |

API 返回的实际 model/version、运行日期与 endpoint：TODO（从 run 中记录）。

## 3. Evaluation Set

Google IFEval 官方固定版本 `e6890f85757dd84e27ca6df2dd30651dafad28e0`。
541 条 prompt，834 条约束，25 种 instruction。单约束 305 条，多约束 236 条；每条分别为 1/2/3 条约束的样本数为 305/179/57。

原始字段：`key`、`prompt`、`instruction_id_list`、`kwargs`。不修改数据。
详细分布见 [数据统计](ifeval_dataset_summary.md)，逐 prompt 数量见 `ifeval_prompt_inventory.csv`。

## 4. Task Validity

工程校验：字段、唯一 sample id、instruction 与 kwargs 长度、官方文件 SHA256。
人工检查 prompt/constraint 一致性及歧义：TODO。
指令通过不代表回答内容在事实、相关性或实用性上合格；部分 prompt 包含外部链接，当前单轮文本设置不提供网页访问工具。

## 5. Grader

直接调用未修改的 Google 官方 strict / loose 函数；保存源码、Apache-2.0 许可与 SHA256 清单。
strict 使用原始输出。loose 采用官方 8 种文本候选，每条约束任一候选满足即通过。prompt 通过要求全部约束通过；instruction 指标采用约束级微平均。

每个 scored result 保存 instruction id、原始/解析参数、规则描述、逐项 strict/loose 结果、整条 prompt 的失败项。随机种子及 langdetect seed 固定为 0。检查器异常与模型失败分开。

## 6. Experiment Setup

默认单 user message；原 prompt 原样传入；无额外 system、工具、搜索、强制输出格式。
非思考模式，temperature=0，max_tokens=4096，timeout=120 秒；真实采用值以 run/config.json 为准。
串行、无自动重试；显式 resume 追加失败样本的新 attempt，跳过成功样本。
正式实验 run_id、样本选择、实际环境及参数核验：TODO。

## 7. Baseline Result

TODO：尚无 DeepSeek / Qwen 实际结果，禁止用 offline fixture 填入此表。

| Model | Prompt strict | Prompt loose | Instruction strict | Instruction loose | Scored / planned |
|---|---|---|---|---|---|
| deepseek-flash | TODO | TODO | TODO | TODO | TODO |
| qwen3.8-max-0902 | TODO | TODO | TODO | TODO | TODO |

统计分母仅包含生成成功且评分成功的样本；必须同时呈现调用错误、评分错误、未完成数。

## 8. Failure Analysis

入口：`failure_analysis.csv`，字段约定：`annotation_schema.json`。
需人工填写 is_real_failure、failure_source、failure_type、notes、needs_repeat_trial、needs_targeted_case。
真实失败案例与复核：TODO。

## 9. Slice Analysis

TODO：真实 run 的 `slices.csv`，按 instruction type 分别输出 strict/loose total、pass、fail、pass_rate。
两个模型仅在可比样本交集上做四组划分；分歧导出包含双边原始输出与完整评分。

## 10. Coverage Gap

TODO：根据人工确认的实际失败记录覆盖缺口；不自动推断或补齐。

## 11. Targeted Evaluation

仅预留 `targeted_cases.csv` 空结构。本轮未增加任何 targeted evaluation 样本。
人工确认补测需求、假设和规则：TODO。

## 12. Re-evaluation

原始输出可离线重评分，无模型请求；每次记录 grader 版本、依赖版本、种子和 raw SHA256。
新的 scored/summary 可更新，raw 永不覆盖。若要保留某次评分快照，在重评分前另存派生文件。
实际规则修订、重复试验或新模型对照：TODO。

## 13. Efficiency Observation

统计已落盘 attempts 的 latency、已知 input/output tokens、未知 usage 数和截断数。
真实模型 token、延迟、费用：TODO。费用不根据未知单价猜测。
本轮模型 API 请求数：0；模型 API 费用：0。

## 14. Findings

### Confirmed

TODO：待真实模型实验和人工验证后填写。

### Observed but Unconfirmed

TODO。

### Unknown

两个模型在本设置下的实际分数、分歧、失败原因、时延与费用均未知。

## 15. Evaluation Quality Review

工程验收证据见 `validation_report.md`、`local_validation.json` 与测试记录。
TODO：真实实验完成后核对样本覆盖、比较设置、truncation、runtime/grader errors、人工复核一致性和重试选择偏差。

## 16. Limitations

- 官方规则属于可验证代理指标，并不评价内容质量；loose 可能让不同约束分别在不同变体上通过。
- NLTK 和语言检测依赖影响判定；种子已固定，但不承诺未来依赖或平台变更后完全相同。
- temperature=0 不保证云端确定性，模型别名的实际后端可能变化。
- 未使用真实账户调用；模型权限、区域端点与实时限流尚待极少量 smoke test 验证。
- API 超时/进程中断可能发生服务端已完成但客户端未落盘的情况，续跑无法保证不重复计费。
- 原始文件损坏时停止并保留证据；V1 不提供自动修复、分布式运行或版本化人工标注合并。
