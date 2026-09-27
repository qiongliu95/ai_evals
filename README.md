# AI Eval Workspace V1

一个按文件保存证据的 Python 评测工作区。当前 suite 为 Google IFEval，目标模型为 `deepseek-flash` 与 `qwen3.8-max-0902`。不含 UI、数据库或自动模型能力结论。

## 目录

```text
ai_evals/
  core/                   通用 Task / ProviderResult / RawResult、Runner、RunManager
  providers/              两家厂商适配及复用的 HTTP 请求格式
  evals/ifeval/
    data/input_data.jsonl 官方数据原始字节
    vendor/               固定版本官方 scorer、许可证、SHA256 清单
    config/               两个模型的请求参数
    dataset.py            数据读取、完整性核验、分布统计
    grader.py             官方 strict / loose 调用与逐约束追溯
    analysis.py           Overall、Slice、分歧和人工分析导出
  cli.py                  命令入口
  tests/                  离线验收测试
  scripts/                可保存产物的离线验证
  runs/                   每个 run 的配置、任务快照和结果
  reports/                数据统计、报告模板、人工分析入口
```

## 安装

Python 3.11+。以下 PowerShell 命令均在 `ai_evals` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
```

后续使用 `.\.venv\Scripts\ai-eval.exe`，也可使用 `.\.venv\Scripts\python.exe -m ai_evals.cli`。项目采用 editable 安装，结果默认写入此目录；可在子命令前加 `--workspace <目录>` 指定另一处结果及 `.env` 目录。

## 环境变量

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写 `DEEPSEEK_API_KEY` 和 `DASHSCOPE_API_KEY`。文件已忽略，代码和配置文件均不保存 key。也可由进程环境提供；进程环境优先于 `.env`。

Qwen 默认北京端点。若账户位于其他地区或使用业务空间专属域名，修改 `DASHSCOPE_BASE_URL`。端点会随 run 固定，续跑使用原值。DeepSeek 可用 `DEEPSEEK_BASE_URL` 配置。不要把密钥放入 URL。

## 准备 IFEval

```powershell
.\.venv\Scripts\ai-eval.exe prepare --download-nltk
```

官方数据和 scorer 已随项目保留；该命令校验 SHA256 并输出真实分布。首次安装额外下载 NLTK `punkt_tab` 至 `.nltk_data`，用于官方句子计数器，不调用模型。之后使用 `prepare` 即可，不需要网络。输出：

- `reports/ifeval_dataset_summary.md`、`.csv`、`.json`
- `reports/ifeval_prompt_inventory.csv`：每条 prompt 的 instruction 数量

数据 541 条、834 条约束、25 种 instruction；原始字段为 `key`、`prompt`、`instruction_id_list`、`kwargs`。单约束 305 条，多约束 236 条（双约束 179、三约束 57）。

## 单条和小批量运行（会调用模型并可能计费）

```powershell
.\.venv\Scripts\ai-eval.exe run --provider deepseek --limit 1
.\.venv\Scripts\ai-eval.exe run --provider qwen --limit 3
.\.venv\Scripts\ai-eval.exe run --provider deepseek --sample-id 1000
```

默认单条；V1 CLI 限制每次选择 1–10 条，没有自动全量入口。`--sample-id` 可以重复传入。比较两个模型时使用相同选择。默认原始 prompt 直接作为唯一 user message，不加 system prompt、不改 prompt、不强制 JSON、不启用搜索或工具。

两个模型均配置非思考模式、temperature=0、max_tokens=4096；可用 `--max-tokens` 调整新 run 的输出上限。参数和 endpoint 保存于 `config.json`。`finish_reason=length` 的输出仍按原文评分，同时报告截断数。模型返回的实际 model 字段另存为 `response_model`。

## 断点续跑

```powershell
.\.venv\Scripts\ai-eval.exe resume runs/<run_id>
```

使用原任务快照和参数；成功项不再请求，失败项重试一次并追加新 attempt。单条异常不终止 batch；没有自动重试。Ctrl+C 后已落盘记录保留。同一 run 有进程锁，进程退出自动释放。

网络超时或进程在服务端完成后、落盘前退出时，无法判断服务端是否已计费，续跑可能重复该次请求。突然断电导致 JSONL 损坏时会报错并保留原件，不静默丢弃证据；需先人工检查原文件。请勿手工改写 config、tasks 或 raw。

## 独立评分

```powershell
.\.venv\Scripts\ai-eval.exe score runs/<run_id>
```

不需要 API key，不创建 provider，不访问网络。评分读取 raw 中的完整 benchmark metadata。重新执行会更新 `scored.jsonl` / `grading.json`，不会覆盖 `raw.jsonl`。每个样本选第一次成功的 attempt；没有成功则保留最后一次错误。

直接调用固定版本 Google 官方 `test_instruction_following_strict` / `test_instruction_following_loose`。strict 检查原文；loose 按官方实现检查原文、移除星号、移除首/尾行及其组合，共 8 个候选，每个 instruction 任一候选通过即可。prompt 通过要求所有 instruction 通过；instruction-level 为所有约束的微平均，不是 prompt 内比例的平均。

`scorer_result` 保存每条 instruction 的 id、kwargs、官方规则描述、strict/loose 布尔值及失败下标。官方检查器没有详细的因果解释；此处记录判定证据，不推测模型为什么失败。语言检测及 Python 随机种子固定为 0。缺失依赖/资源或检查器异常记为 `grader_error`，不会记为模型 Fail。

## 统计与人工分析

```powershell
.\.venv\Scripts\ai-eval.exe analyze runs/<run_id> --output reports/<analysis_name>
.\.venv\Scripts\ai-eval.exe analyze runs/<deepseek_run> runs/<qwen_run> --output reports/<comparison_name>
```

输出 `overall.json/csv`、`slices.csv`、`baseline.md`，并更新各 run 的 `summary.json`。所有 rate 仅以成功生成且成功评分的样本为分母；同时列出 planned/attempted/scored/missing、runtime/grader errors。零分母为 null。tokens/latency 包括所有已记录 attempts；未知 usage 不假装为已知，费用不自动估算。

两个 run 按 sample_id 对齐，仅比较双方都完成评分且约束一致的交集，导出 strict/loose 的四组数量、全部对照 cases 与 `disagreement_cases_*.jsonl`。文件包括 prompt、constraints、双边输出、评分明细、模型和 run_id。不把未配对或调用失败当成 disagreement。续跑改变 raw 后必须重新评分。

`failure_analysis.csv` 是人工记录入口；`is_real_failure`、`needs_repeat_trial`、`needs_targeted_case` 使用空白 / true / false。`failure_source` 允许值见 `reports/annotation_schema.json`，`failure_type` 为自由文本。原始模板在 `reports/`；分析目录会导出对应失败样本。重跑不会覆盖人工 CSV；续跑产生新失败时请使用新的分析目录并人工合并标注。

`targeted_cases.csv` 仅有表头，没有生成补充评测样本。`source_failure_case` 建议记录 `run_id/sample_id/model`。统一人工报告为 `reports/eval_report.md`，模型基线和 Findings 在真实实验前保留 TODO。

## 本地验证（零模型调用）

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/validate_offline.py
```

测试禁止 socket 网络连接，两个厂商使用 HTTP mock 验证真实适配代码；离线脚本只使用原始 IFEval prompt 和固定测试输出，结果明确标注为 `offline-fixture-*`，不代表 DeepSeek/Qwen 的表现。摘要：`reports/local_validation.json`。产物：`runs/local-validation/` 与 `reports/local-validation/`。

新增 suite 时复用 `core.Task`、provider 和 Runner，在新 suite 内编写 dataset/grader/analysis，并增加命令接线；无需修改 IFEval 实现。
