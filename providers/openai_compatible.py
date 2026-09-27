"""Shared wire format used by both configured vendors; no SDK retry policy."""
import json
import os
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from ai_evals.core.result_schema import ProviderResult


class ProviderError(RuntimeError):
    def __init__(self, kind, message, *, http_status=None, raw_response=None):
        super().__init__(message)
        self.details = {"type": kind, "message": message, "http_status": http_status}
        self.raw_response = raw_response


class ChatProvider:
    def __init__(self, model_id, key_env, base_url, timeout=120, transport=None):
        self.model_id = model_id
        self.key_env = key_env
        self.base_url = base_url.rstrip("/")
        url = urlsplit(self.base_url)
        if url.scheme != "https" or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError("API base URL must be HTTPS without credentials, query, or fragment")
        self.timeout = timeout
        self.transport = transport

    def generate(self, prompt, parameters):
        key = os.environ.get(self.key_env)
        if not key:
            raise ProviderError("configuration", f"Missing environment variable: {self.key_env}")
        started = perf_counter()
        payload = {"model": self.model_id, "messages": [{"role": "user", "content": prompt}],
                   "stream": False, **parameters}
        # 禁止覆盖保留字段，确保实际请求与保存的运行配置一致。
        if any(k in parameters for k in ("model", "messages", "stream", "api_key")):
            raise ValueError("Parameters cannot override model, messages, stream, or credentials")
        try:
            # 禁止重定向，避免将 bearer credentials 转发到其他 endpoint。
            with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
                response = client.post(self.base_url + "/chat/completions",
                                       headers={"Authorization": f"Bearer {key}"}, json=payload)
        except httpx.RequestError as exc:
            # Exception text can contain request details; save a safe, typed description.
            raise ProviderError(type(exc).__name__, "API transport request failed") from exc
        latency = round((perf_counter() - started) * 1000, 3)
        try:
            # Defensive redaction if a gateway echoes credentials in an error response.
            data = json.loads(response.text.replace(key, "[REDACTED]"))
        except ValueError as exc:
            raise ProviderError("invalid_response", "API returned non-JSON", http_status=response.status_code) from exc
        if response.status_code != 200:
            raise ProviderError("http_error", "API request failed", http_status=response.status_code, raw_response=data)
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Missing text content")
            usage = data.get("usage") or {}
            return ProviderResult(content, data, latency, usage.get("prompt_tokens"),
                                  usage.get("completion_tokens"), choice.get("finish_reason"), data.get("model"))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("invalid_response", "API response has no usable text completion", raw_response=data) from exc
