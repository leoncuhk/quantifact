"""OpenAI-compatible backends: codegen, semantic review and repair.

Any endpoint that speaks ``/chat/completions`` works — three environment
variables and nothing else:

    QF_LLM_API_KEY    required
    QF_LLM_BASE_URL   default https://api.openai.com/v1
    QF_LLM_MODEL      default gpt-4o-mini

Deliberately stdlib-only. The whole point of the architecture is that the model
is a replaceable code emitter behind one interface; it should not drag a vendor
SDK into the dependency set to prove it.

Two behaviours here were learned the hard way against a real reasoning model:
thinking is disabled for code generation (a reasoning model will happily spend
its entire budget thinking and return empty content) and re-enabled only for
repair, where the extra latency is worth it; and an empty completion first
retries with thinking off, then with a larger budget, capped, because some
gateways reject a budget they consider too large with a bare HTTP 400.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import pandas as pd

from ..contracts.semantic import DEBUG_PROMPT, SEMANTIC_PROMPT
from ..contracts.verdict import Verdict
from ..plan.model import Task
from .prompts import (
    CODEGEN_PROMPT,
    CONVENTIONS,
    column_lines,
    row_order_line,
    upstream_lines,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_OUTPUT_TOKENS = 6000


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    retries: int = 0
    per_call: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.calls} calls, {self.retries} retries, "
            f"{self.prompt_tokens + self.completion_tokens} tokens, "
            f"{self.seconds:.1f}s of API time"
        )


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 240,
        max_retries: int = 3,
        thinking: bool = False,
    ):
        self.api_key = api_key or os.environ.get("QF_LLM_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("QF_LLM_API_KEY is not set")
        self.base_url = (
            base_url or os.environ.get("QF_LLM_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get("QF_LLM_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.thinking = thinking
        self.usage = Usage()

    def complete(
        self,
        prompt: str,
        max_tokens: int = 3000,
        temperature: float = 0.0,
        thinking: bool | None = None,
    ) -> str:
        use_thinking = self.thinking if thinking is None else thinking
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if not use_thinking:
            body["thinking"] = {"type": "disabled"}
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "quantifact/0.1",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        last: Exception | None = None
        for attempt in range(self.max_retries):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read())
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode(errors="replace")
                last = RuntimeError(f"HTTP {e.code}: {detail}")
                if e.code == 400 and max_tokens > 1500:
                    max_tokens = max(1500, max_tokens // 2)
                    body["max_tokens"] = max_tokens
                    req.data = json.dumps(body).encode()
                    self.usage.retries += 1
                    continue
                if e.code in (400, 401, 403, 404):
                    break
                self.usage.retries += 1
                time.sleep(1.5 * (attempt + 1))
                continue
            except (
                urllib.error.URLError,
                OSError,
                TimeoutError,
                json.JSONDecodeError,
            ) as e:
                last = e
                self.usage.retries += 1
                time.sleep(1.5 * (attempt + 1))
                continue

            elapsed = time.perf_counter() - t0
            choice = payload["choices"][0]
            text = (choice["message"].get("content") or "").strip()
            u = payload.get("usage", {})
            self.usage.calls += 1
            self.usage.seconds += elapsed
            self.usage.per_call.append(elapsed)
            self.usage.prompt_tokens += u.get("prompt_tokens", 0)
            self.usage.completion_tokens += u.get("completion_tokens", 0)
            if text:
                return text
            last = RuntimeError(
                f"empty content (finish_reason={choice.get('finish_reason')})"
            )
            self.usage.retries += 1
            if use_thinking:
                use_thinking = False
                body["thinking"] = {"type": "disabled"}
            else:
                max_tokens = min(int(max_tokens * 1.8), MAX_OUTPUT_TOKENS)
                body["max_tokens"] = max_tokens
            req.data = json.dumps(body).encode()
        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts: {last}")


def strip_fence(text: str) -> str:
    """Models wrap code in fences however firmly you ask them not to."""
    text = text.strip()
    if text.startswith("```"):
        body = text.split("\n", 1)[1] if "\n" in text else ""
        text = body.rsplit("```", 1)[0]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(("def ", "import ", "from ", "@")):
            text = "\n".join(lines[i:])
            break
    return text.strip() + "\n"


class OpenAICompatCodegen:
    """Free-form pandas from the task contract. Determinism comes from the
    conventions and the validation layers, not from the model."""

    def __init__(
        self,
        client: LLMClient | None = None,
        max_tokens: int = 3000,
        runtime_hint: str | None = None,
    ):
        self.client = client or LLMClient()
        self.max_tokens = max_tokens
        # Naming the exact runtime is ordinary context engineering: without it
        # a model writes against whichever pandas it happens to remember.
        self.runtime_hint = runtime_hint
        self.name = f"llm:{self.client.model}"

    def generate(
        self, task: Task, upstream: dict[str, list[dict]], as_of: str = ""
    ) -> str:
        extras = ""
        if task.series_inputs:
            shown = task.series_inputs[:60]
            more = (
                f", {len(task.series_inputs)} total"
                if len(shown) < len(task.series_inputs)
                else ""
            )
            extras += (
                f"SERIES TO LOAD (exact ids{more}):\n"
                + "\n".join(f"  - {s}" for s in shown)
                + "\n\n"
            )
        if task.chart_spec:
            extras += f"CHART SPEC: {task.chart_spec}\n\n"
        if task.op:
            extras += f"OPERATION HINT: {task.op}\n\n"
        if task.invariants:
            extras += f"INVARIANTS CHECKED AFTER EXECUTION: {task.invariants}\n\n"
        if self.runtime_hint:
            extras += (
                f"TARGET RUNTIME: {self.runtime_hint} — use only APIs that "
                "exist in exactly these versions.\n\n"
            )
        prompt = CODEGEN_PROMPT.format(
            conventions=CONVENTIONS,
            name=task.name,
            type=task.type,
            description=task.description,
            as_of=as_of or "unspecified",
            row_expectation=task.row_expectation,
            index=task.index,
            row_order=row_order_line(task),
            columns=column_lines(task),
            upstream=upstream_lines(upstream),
            extras=extras,
        )
        return strip_fence(self.client.complete(prompt, self.max_tokens))


class OpenAICompatValidator:
    """L3 semantic validation."""

    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()

    def validate(
        self, task: Task, code: str, df: pd.DataFrame, as_of: str = ""
    ) -> Verdict:
        prompt = SEMANTIC_PROMPT.format(
            description=task.description,
            row_expectation=task.row_expectation,
            columns=task.column_names,
            code=code,
            as_of=as_of or "unspecified",
            sample=df.head(8).to_string(index=False),
        )
        text = self.client.complete(prompt, max_tokens=1200).strip()
        line = text.splitlines()[-1].strip() if text else "PROBLEM: empty verdict"
        ok = line.upper().startswith("OK")
        return Verdict(task.name, "L3-semantic", ok, [] if ok else [line])


class OpenAICompatDebugger:
    """Repairs code that failed a layer.

    Gets three things a bare verdict does not carry: the upstream schemas, a
    description of what the data actually looks like, and the runtime it is
    compiling for. Those are what a human looks at before rewriting.
    """

    def __init__(
        self,
        client: LLMClient | None = None,
        max_tokens: int = 4000,
        thinking: bool = True,
        runtime_hint: str | None = None,
    ):
        self.client = client or LLMClient()
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.runtime_hint = runtime_hint

    def edit(
        self,
        task: Task,
        code: str,
        verdict: Verdict,
        upstream: dict | None = None,
        evidence: str = "",
        as_of: str = "",
    ) -> str:
        ups = ""
        if upstream:
            ups = (
                "\nUPSTREAM DATAFRAMES (exact columns available to you):\n"
                + upstream_lines(upstream)
                + "\n"
            )
        conventions = CONVENTIONS + (
            f"\nTARGET RUNTIME: {self.runtime_hint} — the failure above may be an "
            "API that was removed in this version; use only what exists here.\n"
            if self.runtime_hint
            else ""
        )
        prompt = DEBUG_PROMPT.format(
            name=task.name,
            description=task.description,
            columns=task.column_names,
            row_expectation=task.row_expectation,
            as_of=as_of or "unspecified",
            code=code,
            upstream=ups,
            evidence=(
                f"\nWHAT THE DATA ACTUALLY LOOKS LIKE\n{evidence}\n" if evidence else ""
            ),
            problems="\n".join(f"- {p}" for p in verdict.problems),
            conventions=conventions,
        )
        return strip_fence(
            self.client.complete(prompt, self.max_tokens, thinking=self.thinking)
        )
