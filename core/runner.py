from collections import Counter
from dataclasses import asdict
from time import perf_counter

from .result_schema import RawResult
from .run_manager import effective_results, now


def run(manager, provider):
    config = manager.config
    if provider.model_id != config["model_id"]:
        raise ValueError("Provider model does not match saved run configuration")
    with manager.lock():
        history = manager.raw()
        # 恢复运行绝不重复成功请求；失败样本仍可再次尝试。
        completed = {r["sample_id"] for r in history if r["status"] == "success"}
        attempts = Counter(r["sample_id"] for r in history)
        for task in manager.tasks():
            if task.sample_id in completed:
                continue
            started = perf_counter()
            row = RawResult(
                run_id=config["run_id"], eval_name=config["eval_name"], sample_id=task.sample_id,
                system=config["provider"], model=config["model_id"], model_id=config["model_id"],
                input=task.input, prompt=task.input, benchmark_metadata=task.metadata,
                raw_output=None, status="error", error=None, timestamp=now(), latency_ms=0,
                input_tokens=None, output_tokens=None, run_config=config,
                attempt=attempts[task.sample_id] + 1)
            try:
                output = provider.generate(task.input, config["parameters"])
                for key, value in asdict(output).items():
                    setattr(row, key, value)
                row.status = "success"
            except Exception as exc:
                # Failures remain separate from benchmark pass/fail. No hidden retries.
                row.error = getattr(exc, "details", {"type": type(exc).__name__, "message": str(exc)})
                row.raw_response = getattr(exc, "raw_response", None)
                row.latency_ms = round((perf_counter() - started) * 1000, 3)
            manager.append(row)
        return effective_results(manager.raw())
