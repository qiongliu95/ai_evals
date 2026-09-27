from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from ai_evals.core.run_manager import RunManager, digest, read_jsonl, write_json, write_jsonl

FAILURE_SOURCES = ["model", "instruction_following", "format", "scorer", "task_or_sample",
                   "prompt_ambiguity", "runtime", "randomness", "unknown"]
FAILURE_FIELDS = ["run_id", "sample_id", "model", "scorer_result", "is_real_failure", "failure_source",
                  "failure_type", "notes", "needs_repeat_trial", "needs_targeted_case"]
TARGET_FIELDS = ["case_id", "source_failure_case", "hypothesis", "target_slice", "prompt", "expected_rule", "why_added"]


def csv_write(path, fields, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ratio(passed, total):
    return {"total": total, "pass": passed, "fail": total - passed, "pass_rate": passed / total if total else None}


def analyzed_run(path):
    manager = RunManager(path)
    if not (manager.path / "scored.jsonl").exists():
        raise ValueError(f"Score this run first: {path}")
    rows = read_jsonl(manager.path / "scored.jsonl")
    grading = json.loads((manager.path / "grading.json").read_text(encoding="utf-8"))
    raw_hash = digest(manager.path / "raw.jsonl")
    # 评分只对生成这些结果时使用的原始记录有效。
    if grading["raw_sha256"] != raw_hash or any(r["raw_sha256"] != raw_hash for r in rows):
        raise ValueError("Raw results changed after grading; score this run again")
    # 准确率排除运行和评分失败，避免把系统可靠性问题计为指令遵循失败。
    valid = [r for r in rows if r["grade_status"] == "scored"]
    summary = {"run_id": manager.config["run_id"], "model": manager.config["model_id"],
               "expected_samples": manager.config["sample_count"], "attempted_samples": len(rows),
               "scored_samples": len(valid), "missing_samples": manager.config["sample_count"] - len(rows),
               "runtime_errors": sum(r["status"] != "success" for r in rows),
               "grader_errors": sum(r["grade_status"] == "grader_error" for r in rows),
               "denominator_policy": "Only successfully generated and scored samples; coverage reported separately.",
               "overall": {}, "raw_sha256": raw_hash}
    slices = []
    # prompt 指标要求全部约束通过；instruction 指标则把每条约束独立计数。
    for mode in ("strict", "loose"):
        prompt_flags = [r["scorer_result"][f"prompt_{mode}"] for r in valid]
        instruction_flags = [flag for r in valid for flag in r["scorer_result"][f"instruction_{mode}"]]
        summary["overall"][f"prompt_{mode}"] = ratio(sum(prompt_flags), len(prompt_flags))
        summary["overall"][f"instruction_{mode}"] = ratio(sum(instruction_flags), len(instruction_flags))
        grouped = defaultdict(list)
        for row in valid:
            for item in row["scorer_result"]["instructions"]:
                grouped[item["instruction_id"]].append(item[mode])
        for instruction_id, flags in sorted(grouped.items()):
            slices.append({"run_id": summary["run_id"], "model": summary["model"], "mode": mode,
                           "instruction_type": instruction_id, **ratio(sum(flags), len(flags))})
    # 效率统计包含失败和重试在内的全部付费 attempts；准确率只使用上面的已评分样本。
    history = manager.raw()
    summary["efficiency"] = {"attempts": len(history),
                             "total_latency_ms": sum(r["latency_ms"] for r in history),
                             "input_tokens_known": sum(r["input_tokens"] or 0 for r in history),
                             "output_tokens_known": sum(r["output_tokens"] or 0 for r in history),
                             "attempts_missing_usage": sum(r["input_tokens"] is None or r["output_tokens"] is None for r in history),
                             "truncated_samples": sum(r.get("finish_reason") == "length" for r in rows),
                             "cost": None}
    write_json(manager.path / "summary.json", summary)
    return manager, rows, summary, slices


def analyze(paths, output_dir):
    if not 1 <= len(paths) <= 2:
        raise ValueError("Pass one run, or exactly two runs for comparison")
    runs = [analyzed_run(path) for path in paths]
    if len(runs) == 2:
        # 配对模型比较要求两个不同 model_id 使用同一个不可变 benchmark snapshot。
        a, b = (r[0].config for r in runs)
        if a["model_id"] == b["model_id"]:
            raise ValueError("Model comparison requires two different model IDs")
        if a["dataset_sha256"] != b["dataset_sha256"]:
            raise ValueError("Cannot compare different benchmark snapshots")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "overall.json", [r[2] for r in runs])
    overall = [{"run_id": summary["run_id"], "model": summary["model"], "metric": metric, **values}
               for _, _, summary, _ in runs for metric, values in summary["overall"].items()]
    csv_write(out / "overall.csv", ["run_id", "model", "metric", "total", "pass", "fail", "pass_rate"], overall)
    csv_write(out / "slices.csv", ["run_id", "model", "mode", "instruction_type", "total", "pass", "fail", "pass_rate"],
              [item for run in runs for item in run[3]])
    failure_path = out / "failure_analysis.csv"
    if not failure_path.exists():
        # This is an editable human annotation file; later analysis never overwrites it.
        failures = []
        for _, rows, _, _ in runs:
            for row in rows:
                if row["grade_status"] != "scored" or not row["scorer_result"]["prompt_strict"]:
                    failures.append({"run_id": row["run_id"], "sample_id": row["sample_id"], "model": row["model_id"],
                                     "scorer_result": json.dumps({"result": row["scorer_result"], "error": row["error"],
                                                                  "grader_error": row["grader_error"]}, ensure_ascii=False),
                                     "failure_source": "unknown"})
        csv_write(failure_path, FAILURE_FIELDS, failures)
    if not (out / "targeted_cases.csv").exists():
        csv_write(out / "targeted_cases.csv", TARGET_FIELDS, [])
    comparison = None
    if len(runs) == 2:
        arows, brows = ({r["sample_id"]: r for r in run[1]} for run in runs)
        # 只配对两次运行中同 sample_id 且都已评分的样本；其他 ID 明确作为覆盖率排除项保留。
        comparable = sorted(k for k in arows.keys() & brows.keys()
                            if arows[k]["grade_status"] == brows[k]["grade_status"] == "scored")
        comparison = {"model_a": runs[0][2]["model"], "model_b": runs[1][2]["model"],
                      "comparable_samples": len(comparable),
                      "unpaired_or_unscored_ids": sorted((arows.keys() | brows.keys()) - set(comparable)),
                      "parameter_match": runs[0][0].config["parameters"] == runs[1][0].config["parameters"],
                      "note": "parameter_match compares vendor parameter dictionaries; inspect saved configs for comparability.", "groups": {}}
        for mode in ("strict", "loose"):
            counts = Counter({key: 0 for key in ("A_pass_B_pass", "A_pass_B_fail", "A_fail_B_pass", "A_fail_B_fail")})
            cases, disagreements = [], []
            for key in comparable:
                a, b = arows[key], brows[key]
                # 即使 ID 相同，benchmark metadata 描述的约束不同也代表任务不同，不能比较。
                if a["benchmark_metadata"] != b["benchmark_metadata"]:
                    raise ValueError(f"Mismatched benchmark constraints for sample {key}")
                ap, bp = (r["scorer_result"][f"prompt_{mode}"] for r in (a, b))
                group = f"A_{'pass' if ap else 'fail'}_B_{'pass' if bp else 'fail'}"
                counts[group] += 1
                case = {"sample_id": key, "prompt": a["prompt"], "mode": mode, "group": group,
                        "instruction_types": a["benchmark_metadata"]["instruction_id_list"],
                        "constraints": a["benchmark_metadata"]["kwargs"],
                        "model_a": a["model_id"], "model_b": b["model_id"],
                        "run_a": a["run_id"], "run_b": b["run_id"],
                        "model_a_raw_output": a["raw_output"], "model_b_raw_output": b["raw_output"],
                        "model_a_scorer_result": a["scorer_result"], "model_b_scorer_result": b["scorer_result"]}
                cases.append(case)
                if ap != bp:
                    # disagreement cases 用于隔离模型结果分歧的样本，供后续定性分析。
                    disagreements.append(case)
            comparison["groups"][mode] = dict(counts)
            write_jsonl(out / f"comparison_cases_{mode}.jsonl", cases)
            write_jsonl(out / f"disagreement_cases_{mode}.jsonl", disagreements)
        write_json(out / "comparison_summary.json", comparison)
    text = ["# Baseline Statistics", "", "Rates use scored samples only; runtime/grader errors and missing samples are reported separately.",
            "", "| Model | Scored / planned | Prompt strict | Prompt loose | Instruction strict | Instruction loose |", "|---|---:|---:|---:|---:|---:|"]
    for _, _, s, _ in runs:
        rates = [s["overall"][k]["pass_rate"] for k in ("prompt_strict", "prompt_loose", "instruction_strict", "instruction_loose")]
        text.append(f"| {s['model']} | {s['scored_samples']} / {s['expected_samples']} | " + " | ".join("N/A" if r is None else f"{r:.2%}" for r in rates) + " |")
    text += ["", "These are descriptive statistics; no model capability conclusion is generated.",
             "Human annotations: failure_analysis.csv (preserved on reruns). New exports should use a new output directory."]
    (out / "baseline.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    return {"runs": [run[2] for run in runs], "comparison": comparison}
