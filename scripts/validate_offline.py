"""Save a reproducible end-to-end local demonstration, without any API calls."""
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
# 支持直接执行此脚本，同时从父目录导入工作区包。
sys.path.insert(0, str(ROOT.parent))

from ai_evals.core.result_schema import ProviderResult
from ai_evals.core.run_manager import RunManager, digest, now, write_json
from ai_evals.core.runner import run
from ai_evals.evals.ifeval.dataset import DATA, SOURCE, load_dataset, summarize, tasks_from_rows
from ai_evals.evals.ifeval.grader import grade_run
from ai_evals.evals.ifeval.analysis import analyze


def deny_network(*args, **kwargs):
    raise RuntimeError("Network is disabled during offline validation")


class FixtureProvider:
    def __init__(self, model_id, outputs):
        self.model_id, self.outputs, self.calls = model_id, outputs, 0

    def generate(self, prompt, parameters):
        self.calls += 1
        return ProviderResult(self.outputs[prompt], {"offline_fixture": True}, 0, None, None, "stop", self.model_id)


def main():
    # 验证必须证明本地 pipeline 不依赖网络，并让任何意外联网立即失败。
    socket.socket.connect = deny_network
    # 在运行生命周期前先覆盖固定 dataset 校验和报告生成阶段。
    summary = summarize(ROOT / "reports")
    selected = [row for row in load_dataset() if row["instruction_id_list"] == ["punctuation:no_comma"]][:4]
    managers = []
    # 两组相反的 fixture 让四个配对通过/失败象限各包含一个样本。
    for label, outputs in (("offline-fixture-a", ["pass", "pass", "a,b", "a,b"]),
                           ("offline-fixture-b", ["pass", "a,b", "pass", "a,b"])):
        config = {"eval_name": "ifeval", "provider": "offline_fixture", "model_id": label,
                  "parameters": {}, "dataset_sha256": digest(DATA), "dataset_source": SOURCE,
                  "validation_only": True, "note": "Deterministic test outputs, NOT model responses"}
        manager = RunManager.create(ROOT / "runs" / "local-validation", config, tasks_from_rows(selected))
        provider = FixtureProvider(label, dict(zip((r["prompt"] for r in selected), outputs)))
        run(manager, provider)
        raw_hash = digest(manager.path / "raw.jsonl")
        # 恢复运行必须跳过已成功样本，避免重复请求或重复写入证据。
        run(manager, provider)
        assert provider.calls == 4
        # 重复评分必须结果一致，且不得修改只追加的原始证据。
        first = grade_run(manager)
        second = grade_run(manager)
        assert [r["scorer_result"] for r in first] == [r["scorer_result"] for r in second]
        assert digest(manager.path / "raw.jsonl") == raw_hash
        managers.append(manager)
    report_dir = ROOT / "reports" / "local-validation" / managers[0].config["run_id"]
    # 每个象限各一个样本，用于验证配对分组和两个方向的 disagreement cases。
    result = analyze([m.path for m in managers], report_dir)
    assert set(result["comparison"]["groups"]["strict"].values()) == {1}
    result = {"validated_at": now(), "purpose": "Local software verification only; not a baseline",
              "model_api_calls": 0, "model_api_cost": 0, "dataset_samples": summary["sample_count"],
              "runs": [str(m.path) for m in managers], "analysis": str(report_dir),
              "checks": ["dataset", "runner", "success_skip", "raw_append", "independent_rescore",
                         "overall", "slice", "all_four_comparison_groups", "disagreement_export", "annotation_templates"]}
    write_json(ROOT / "reports" / "local_validation.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
