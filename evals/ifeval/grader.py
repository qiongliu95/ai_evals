"""Invoke the unmodified official strict/loose scorer, offline."""
from dataclasses import asdict
import importlib.metadata
import random
import sys

from ai_evals.core.run_manager import digest, effective_results, now, write_json, write_jsonl
from .dataset import COMMIT, SUITE, verify_sources


def official_modules():
    verify_sources()
    vendor = str(SUITE / "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    from instruction_following_eval import evaluation_lib, instructions_registry
    if not str(evaluation_lib.__file__).startswith(vendor):
        raise RuntimeError("Another instruction_following_eval package shadows the pinned scorer")
    import nltk
    local_data = str(SUITE.parents[1] / ".nltk_data")
    if local_data not in nltk.data.path:
        nltk.data.path.insert(0, local_data)
    from langdetect import DetectorFactory
    # langdetect otherwise changes results across independent rescoring processes.
    DetectorFactory.seed = 0
    return evaluation_lib, instructions_registry


def score_output(benchmark, output):
    evaluation_lib, registry = official_modules()
    inp = evaluation_lib.InputExample(**{k: benchmark[k] for k in ("key", "prompt", "instruction_id_list", "kwargs")})
    response = {inp.prompt: output}
    # 官方检查使用全局随机状态；各路径使用相同 seed 可重复评分且不泄漏状态。
    state = random.getstate()
    try:
        random.seed(0)
        strict = evaluation_lib.test_instruction_following_strict(inp, response)
        random.seed(0)
        loose = evaluation_lib.test_instruction_following_loose(inp, response)
        instructions = []
        random.seed(0)
        for index, instruction_id in enumerate(inp.instruction_id_list):
            checker = registry.INSTRUCTION_DICT[instruction_id](instruction_id)
            description = checker.build_description(**inp.kwargs[index])
            args = checker.get_instruction_args()
            if args and "prompt" in args:
                description = checker.build_description(prompt=inp.prompt)
            instructions.append({"index": index, "instruction_id": instruction_id,
                                 "kwargs": inp.kwargs[index], "description": description,
                                 "resolved_kwargs": checker.get_instruction_args(),
                                 "strict": strict.follow_instruction_list[index],
                                 "loose": loose.follow_instruction_list[index]})
    finally:
        random.setstate(state)
    return {"instructions": instructions,
            "prompt_strict": strict.follow_all_instructions, "prompt_loose": loose.follow_all_instructions,
            "instruction_strict": strict.follow_instruction_list, "instruction_loose": loose.follow_instruction_list,
            "prompt_reason": {mode: {"rule": "all instruction checks must pass",
                                      "failed_instruction_indices": [i for i, ok in enumerate(flags) if not ok]}
                              for mode, flags in (("strict", strict.follow_instruction_list), ("loose", loose.follow_instruction_list))},
            "official_strict": asdict(strict), "official_loose": asdict(loose)}


def grade_run(manager):
    official_modules()
    with manager.lock():
        # 每个评分结果都绑定到确切的原始证据，便于后续拒绝过期的派生结果。
        raw_hash = digest(manager.path / "raw.jsonl")
        score_id = now()
        provenance = {"source": "Google Research IFEval (unmodified)", "commit": COMMIT,
                      "random_seed": 0, "langdetect_seed": 0,
                      "dependencies": {p: importlib.metadata.version(p) for p in ("nltk", "langdetect", "absl-py", "immutabledict")}}
        scored = []
        for raw in effective_results(manager.raw()):
            row = dict(raw, scored_at=score_id, grader=provenance, raw_sha256=raw_hash,
                       grade_status="not_scored", scorer_result=None, grader_error=None)
            if raw["status"] == "success":
                try:
                    row["scorer_result"] = score_output(raw["benchmark_metadata"], raw["raw_output"])
                    row["grade_status"] = "scored"
                except Exception as exc:
                    row["grade_status"] = "grader_error"
                    row["grader_error"] = {"type": type(exc).__name__, "message": str(exc)}
            scored.append(row)
        # Derived artifacts may be replaced; the evidence journal is never changed.
        write_jsonl(manager.path / "scored.jsonl", scored)
        write_json(manager.path / "grading.json", {"scored_at": score_id, "raw_sha256": raw_hash,
                                                   "grader": provenance, "row_count": len(scored)})
        return scored
