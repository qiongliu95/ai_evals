from collections import Counter
import csv
import json
from pathlib import Path

from ai_evals.core.result_schema import Task
from ai_evals.core.run_manager import digest, read_jsonl, write_json

SUITE = Path(__file__).resolve().parent
DATA = SUITE / "data" / "input_data.jsonl"
# 固定上游版本可防止 benchmark 规则在不同运行之间静默变化。
COMMIT = "e6890f85757dd84e27ca6df2dd30651dafad28e0"
SOURCE = f"https://github.com/google-research/google-research/tree/{COMMIT}/instruction_following_eval"


def verify_sources():
    manifest = json.loads((SUITE / "vendor" / "manifest.json").read_text(encoding="utf-8"))
    # 在执行评测前用 vendor hash 确认官方 scorer 仍与固定的上游 snapshot 一致。
    for relative, expected in manifest["sha256"].items():
        if digest(SUITE / relative) != expected:
            raise ValueError(f"Official source changed: {relative}")
    return manifest


def load_dataset():
    verify_sources()
    rows = read_jsonl(DATA)
    # 稳定且唯一的 sample_id 是安全恢复运行和跨运行配对比较的前提。
    ids = set()
    for row in rows:
        if not {"key", "prompt", "instruction_id_list", "kwargs"}.issubset(row):
            raise ValueError("Missing official IFEval fields")
        if str(row["key"]) in ids:
            raise ValueError("Duplicate IFEval key")
        ids.add(str(row["key"]))
        # IFEval 按位置关联 instruction_id_list 与 kwargs；错位会使用错误规则评分。
        if not row["instruction_id_list"] or len(row["instruction_id_list"]) != len(row["kwargs"]):
            raise ValueError(f"Instruction/kwargs mismatch: {row['key']}")
    return rows


def tasks_from_rows(rows):
    return [Task(str(row["key"]), row["prompt"], row) for row in rows]


def summarize(output_dir):
    rows = load_dataset()
    counts = Counter(i for row in rows for i in row["instruction_id_list"])
    distribution = Counter(len(row["instruction_id_list"]) for row in rows)
    summary = {"source": SOURCE, "commit": COMMIT, "dataset_sha256": digest(DATA),
               "sample_count": len(rows), "instruction_count": sum(counts.values()),
               "fields": sorted(set().union(*(row.keys() for row in rows))),
               "instruction_types": dict(sorted(counts.items())),
               "instructions_per_prompt": dict(sorted(distribution.items())),
               "single_instruction": distribution[1],
               "multi_instruction": sum(n for k, n in distribution.items() if k > 1)}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "ifeval_dataset_summary.json", summary)
    with (out / "ifeval_dataset_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["category", "name", "count"])
        writer.writerow(["dataset", "samples", len(rows)])
        writer.writerow(["dataset", "instructions", sum(counts.values())])
        writer.writerows(("instruction_type", key, count) for key, count in sorted(counts.items()))
        writer.writerows(("instructions_per_prompt", key, count) for key, count in sorted(distribution.items()))
        writer.writerow(["sample_group", "single_instruction", summary["single_instruction"]])
        writer.writerow(["sample_group", "multi_instruction", summary["multi_instruction"]])
    with (out / "ifeval_prompt_inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample_id", "instruction_count", "instruction_types"])
        writer.writerows((r["key"], len(r["instruction_id_list"]), json.dumps(r["instruction_id_list"])) for r in rows)
    text = ["# IFEval Dataset Summary", "", f"Source: {SOURCE}", "",
            f"Samples: **{len(rows)}**; instructions: **{sum(counts.values())}**; types: **{len(counts)}**.",
            f"Fields: {', '.join(summary['fields'])}.",
            f"Single instruction: **{summary['single_instruction']}**; multi-instruction: **{summary['multi_instruction']}**.",
            "", "Counts below are instruction occurrences (not prompt counts).", "",
            "| Instruction type | Count |", "|---|---:|"]
    text += [f"| {key} | {value} |" for key, value in sorted(counts.items())]
    text += ["", "| Instructions per prompt | Prompts |", "|---:|---:|"]
    text += [f"| {key} | {value} |" for key, value in sorted(distribution.items())]
    text += ["", f"SHA256: `{summary['dataset_sha256']}`", "",
             "Original JSONL bytes and fields are retained. Per-prompt counts: `ifeval_prompt_inventory.csv`."]
    (out / "ifeval_dataset_summary.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    return summary
