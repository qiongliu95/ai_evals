from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Task:
    sample_id: str
    input: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    raw_output: str
    raw_response: dict[str, Any]
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    response_model: str | None = None


class Provider(Protocol):
    model_id: str

    def generate(self, prompt: str, parameters: dict) -> ProviderResult: ...


@dataclass
class RawResult:
    run_id: str
    eval_name: str
    sample_id: str
    system: str
    model: str
    model_id: str
    input: str
    prompt: str
    benchmark_metadata: dict
    raw_output: str | None
    status: str
    error: dict | None
    timestamp: str
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    run_config: dict
    attempt: int
    raw_response: dict | None = None
    finish_reason: str | None = None
    response_model: str | None = None
