"""Offline acceptance tests: no provider is permitted to access the network."""
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ai_evals.core.result_schema import ProviderResult, Task
from ai_evals.core.run_manager import RunManager, digest, read_jsonl, write_jsonl
from ai_evals.core.runner import run
from ai_evals.evals.ifeval.dataset import DATA, SUITE, load_dataset, summarize, tasks_from_rows
from ai_evals.evals.ifeval.grader import grade_run, official_modules, score_output
from ai_evals.evals.ifeval.analysis import analyze
from ai_evals.providers.deepseek import DeepSeekProvider
from ai_evals.providers.qwen import QwenProvider
from ai_evals.providers.openai_compatible import ProviderError


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr("socket.socket.connect", denied)


def config(model="offline-a"):
    return {"eval_name": "ifeval", "provider": "offline_fixture", "model_id": model,
            "parameters": {}, "dataset_sha256": digest(DATA), "validation_only": True}


class OfflineProvider:
    def __init__(self, model_id="offline-a", outputs=None, fail=None, interrupt=None):
        self.model_id = model_id
        self.outputs = outputs or {}
        self.fail = fail
        self.interrupt = interrupt
        self.calls = []

    def generate(self, prompt, parameters):
        self.calls.append(prompt)
        if prompt == self.interrupt:
            raise KeyboardInterrupt()
        if prompt == self.fail:
            raise RuntimeError("Offline failure")
        return ProviderResult(self.outputs.get(prompt, "local verification response"),
                              {"fixture": True}, 1.0, 2, 3, "stop", self.model_id)


def test_official_dataset_summary(tmp_path):
    rows = load_dataset()
    summary = summarize(tmp_path)
    assert summary["sample_count"] == 541
    assert summary["instruction_count"] == 834
    assert len(summary["instruction_types"]) == 25
    assert summary["instructions_per_prompt"] == {1: 305, 2: 179, 3: 57}
    assert summary["single_instruction"] == 305 and summary["multi_instruction"] == 236
    assert len(list((tmp_path / "ifeval_prompt_inventory.csv").open(encoding="utf-8-sig"))) == 542
    assert tasks_from_rows(rows)[0].metadata == rows[0]


@pytest.mark.parametrize("provider_class,key_env", [(DeepSeekProvider, "DEEPSEEK_API_KEY"), (QwenProvider, "DASHSCOPE_API_KEY")])
def test_provider_request_usage_and_raw(provider_class, key_env, monkeypatch):
    monkeypatch.setenv(key_env, "test-secret-no-real-key")
    seen = []
    body = {"model": "actual-model-version", "choices": [{"message": {"content": "  Raw text\n"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 9}}
    def handler(request):
        seen.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer test-secret-no-real-key"
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json=body)
    provider = provider_class(transport=httpx.MockTransport(handler))
    output = provider.generate("original prompt", {"max_tokens": 50})
    assert output.raw_output == "  Raw text\n" and output.raw_response == body
    assert output.input_tokens == 7 and output.output_tokens == 9 and output.latency_ms >= 0
    assert output.finish_reason == "length" and output.response_model == "actual-model-version"
    assert seen == [{"model": provider.model_id, "messages": [{"role": "user", "content": "original prompt"}],
                     "stream": False, "max_tokens": 50}]


@pytest.mark.parametrize("kind", ["http", "timeout", "non_json", "missing_content"])
def test_provider_errors_and_redaction(kind, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-no-real-key")
    calls = []
    def handler(request):
        calls.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("secret must not leak", request=request)
        if kind == "non_json":
            return httpx.Response(502, text="gateway error")
        if kind == "missing_content":
            return httpx.Response(200, json={"choices": []})
        return httpx.Response(429, json={"error": "test-secret-no-real-key"})
    with pytest.raises(ProviderError) as caught:
        DeepSeekProvider(transport=httpx.MockTransport(handler)).generate("p", {})
    assert len(calls) == 1
    assert "test-secret-no-real-key" not in json.dumps(caught.value.raw_response)
    assert "secret must not leak" not in str(caught.value)


def test_runner_resume_failure_continuation_and_raw_fields(tmp_path):
    tasks = [Task(str(i), f"prompt-{i}", {"extension": i}) for i in range(3)]
    manager = RunManager.create(tmp_path, config(), tasks)
    first = OfflineProvider(fail="prompt-1")
    run(manager, first)
    before = (manager.path / "raw.jsonl").read_bytes()
    assert [r["status"] for r in manager.raw()] == ["success", "error", "success"]
    second = OfflineProvider()
    run(RunManager(manager.path), second)
    assert second.calls == ["prompt-1"]
    assert (manager.path / "raw.jsonl").read_bytes().startswith(before)
    assert len(manager.raw()) == 4 and manager.raw()[-1]["attempt"] == 2
    run(manager, second)
    assert second.calls == ["prompt-1"]
    assert {"run_id", "eval_name", "sample_id", "system", "model_id", "input", "raw_output", "status", "error",
            "timestamp", "latency_ms", "input_tokens", "output_tokens", "run_config"} <= manager.raw()[0].keys()


def test_interrupted_run_and_lock_release(tmp_path):
    manager = RunManager.create(tmp_path, config(), [Task("a", "a"), Task("b", "b")])
    with pytest.raises(KeyboardInterrupt):
        run(manager, OfflineProvider(interrupt="b"))
    provider = OfflineProvider()
    run(manager, provider)
    assert provider.calls == ["b"] and len(manager.raw()) == 2
    with manager.lock():
        with pytest.raises(RuntimeError, match="already in use"):
            with RunManager(manager.path).lock():
                pass


def test_snapshot_mutation_rejected(tmp_path):
    manager = RunManager.create(tmp_path, config(), [Task("a", "a")])
    (manager.path / "tasks.jsonl").write_text('{}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot changed"):
        RunManager(manager.path)


def test_strict_loose_and_constraint_trace():
    # Unit fixture, not a new evaluation/targeted case.
    benchmark = {"key": 0, "prompt": "fixture", "instruction_id_list": ["detectable_format:json_format"], "kwargs": [{}]}
    result = score_output(benchmark, 'Preamble\n{"ok": true}\nPostamble')
    assert result["prompt_strict"] is False and result["prompt_loose"] is True
    assert result["prompt_reason"]["strict"]["failed_instruction_indices"] == [0]
    assert result["instructions"][0]["description"]
    empty = score_output(benchmark, "")
    assert not empty["prompt_strict"] and not empty["prompt_loose"]


def test_all_541_samples_agree_with_official_functions():
    lib, _ = official_modules()
    rows = load_dataset()
    for row in rows:
        output = "This is a local verification response.\n*Section*\nNo model was called."
        wrapped = score_output(row, output)
        inp = lib.InputExample(**row)
        random.seed(0)
        strict = lib.test_instruction_following_strict(inp, {row["prompt"]: output})
        random.seed(0)
        loose = lib.test_instruction_following_loose(inp, {row["prompt"]: output})
        assert wrapped["official_strict"] == asdict(strict)
        assert wrapped["official_loose"] == asdict(loose)


def test_score_analyze_disagreements_and_rescore(tmp_path):
    # Existing official no-comma-only prompts let fixtures cover all four groups.
    selected = [r for r in load_dataset() if r["instruction_id_list"] == ["punctuation:no_comma"]][:4]
    assert len(selected) == 4
    managers = []
    for model, outputs in (("offline-a", ["pass", "pass", "a,b", "a,b"]),
                           ("offline-b", ["pass", "a,b", "pass", "a,b"])):
        manager = RunManager.create(tmp_path, config(model), tasks_from_rows(selected))
        run(manager, OfflineProvider(model, dict(zip((r["prompt"] for r in selected), outputs))))
        original = digest(manager.path / "raw.jsonl")
        first = grade_run(manager)
        second = grade_run(manager)
        assert [r["scorer_result"] for r in first] == [r["scorer_result"] for r in second]
        assert digest(manager.path / "raw.jsonl") == original
        managers.append(manager)
    result = analyze([m.path for m in managers], tmp_path / "analysis")
    assert set(result["comparison"]["groups"]["strict"].values()) == {1}
    assert len(read_jsonl(tmp_path / "analysis/disagreement_cases_strict.jsonl")) == 2
    assert result["runs"][0]["overall"]["prompt_strict"]["pass_rate"] == 0.5
    notes = tmp_path / "analysis/failure_analysis.csv"
    before = notes.read_bytes()
    analyze([m.path for m in managers], tmp_path / "analysis")
    assert notes.read_bytes() == before
    assert len((tmp_path / "analysis/targeted_cases.csv").read_text(encoding="utf-8-sig").splitlines()) == 1


def test_missing_runtime_and_grader_errors_not_model_failures(tmp_path):
    selected = load_dataset()[:3]
    manager = RunManager.create(tmp_path, config(), tasks_from_rows(selected))
    run(manager, OfflineProvider(fail=selected[1]["prompt"]))
    rows = grade_run(manager)
    assert rows[1]["grade_status"] == "not_scored" and rows[1]["scorer_result"] is None
    result = analyze([manager.path], tmp_path / "stats")["runs"][0]
    assert result["runtime_errors"] == 1 and result["scored_samples"] == 2
    run(manager, OfflineProvider())
    with pytest.raises(ValueError, match="changed after grading"):
        analyze([manager.path], tmp_path / "stats")
    bad = {"key": 9, "prompt": "bad fixture", "instruction_id_list": ["unknown:checker"], "kwargs": [{}]}
    bad_manager = RunManager.create(tmp_path, config(), tasks_from_rows([bad]))
    run(bad_manager, OfflineProvider())
    rows = grade_run(bad_manager)
    assert rows[0]["grade_status"] == "grader_error" and rows[0]["scorer_result"] is None


def test_empty_run_rates_are_null(tmp_path):
    manager = RunManager.create(tmp_path, config(), tasks_from_rows(load_dataset()[:1]))
    grade_run(manager)
    result = analyze([manager.path], tmp_path / "empty")["runs"][0]
    assert result["missing_samples"] == 1
    assert result["overall"]["prompt_strict"]["pass_rate"] is None


@pytest.mark.parametrize("name", ["deepseek", "qwen"])
def test_cli_small_run_and_offline_rescore(name, tmp_path, monkeypatch):
    from ai_evals import cli
    cls, env = ((DeepSeekProvider, "DEEPSEEK_API_KEY") if name == "deepseek" else (QwenProvider, "DASHSCOPE_API_KEY"))
    monkeypatch.setenv(env, "local-cli-test-key")
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if name == "deepseek":
            assert payload["thinking"] == {"type": "disabled"}
        else:
            assert payload["enable_thinking"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": "offline fixture"}, "finish_reason": "stop"}]})
    monkeypatch.setattr(cli, "provider_for", lambda config: cls(transport=httpx.MockTransport(handler)))
    common = ["--workspace", str(tmp_path)]
    assert cli.main(common + ["run", "--provider", name, "--limit", "2"]) == 0
    path = next((tmp_path / "runs").iterdir())
    assert cli.main(common + ["resume", str(path)]) == 0
    assert len(requests) == 2
    monkeypatch.delenv(env)
    assert cli.main(common + ["score", str(path)]) == 0
    assert cli.main(common + ["analyze", str(path), "--output", str(tmp_path / "analysis")]) == 0
    assert len(requests) == 2


def test_cli_rejects_large_batch_before_provider(tmp_path, monkeypatch):
    from ai_evals import cli
    def forbidden(config):
        raise AssertionError("Provider should not be initialized for rejected batch")
    monkeypatch.setattr(cli, "provider_for", forbidden)
    assert cli.main(["--workspace", str(tmp_path), "run", "--provider", "deepseek", "--limit", "541"]) == 1
    assert not (tmp_path / "runs").exists()
