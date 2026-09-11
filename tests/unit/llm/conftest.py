"""Shared fixtures for the F11 unit tests.

None of these tests touch a network, a GPU or a model. The whole point of this
suite is that the LLM front behaves correctly *without* any of those.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from caissa.llm import guardrails
from caissa.llm.guardrails import AuditLog, set_audit_log
from caissa.llm.runtime import (
    CancellationToken,
    GenerationChunk,
    GenerationRequest,
    GenerationResult,
    LlmCancelledError,
    LlmTimeoutError,
    RuntimeInfo,
)

# A legal, ordinary middlegame position used across the suite.
GOOD_FEN = "r3qr1k/pp3pbp/2pn4/7Q/3pP3/2NB3P/PPP3P1/R4RK1 w - - 0 1"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake image payload"


class FakeRuntime:
    """A scripted runtime. Returns canned text, records what it was asked.

    Deliberately not a ``Mock``: the tests need to assert on the *content* of
    requests (token caps, seeds, image attachment), and a hand-written double
    makes those assertions readable.
    """

    def __init__(
        self,
        replies: list[str] | None = None,
        *,
        available: bool = True,
        vision: bool = True,
        raises: Exception | None = None,
        truncated: bool = False,
        latency_ms: float = 12.0,
    ) -> None:
        """Build a double that answers with ``replies`` in order."""
        self.model = "fake:test"
        self._replies = list(replies or [])
        self._available = available
        self._vision = vision
        self._raises = raises
        self._truncated = truncated
        self._latency_ms = latency_ms
        self.requests: list[GenerationRequest] = []
        self.load_calls = 0
        self.unload_calls = 0

    def info(self) -> RuntimeInfo:
        return RuntimeInfo(
            backend="fake",
            model=self.model,
            available=self._available,
            vision=self._vision,
        )

    def is_available(self) -> bool:
        return self._available

    def generate(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> GenerationResult:
        self.requests.append(request)
        if cancel is not None and cancel.cancelled:
            raise LlmCancelledError("cancelado")
        if self._raises is not None:
            raise self._raises
        text = self._replies.pop(0) if self._replies else ""
        return GenerationResult(
            text=text,
            model=self.model,
            latency_ms=self._latency_ms,
            prompt_tokens=17,
            completion_tokens=len(text.split()),
            truncated=self._truncated,
        )

    def stream(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> Iterator[GenerationChunk]:
        result = self.generate(request, cancel)
        yield GenerationChunk(text=result.text, done=True)

    def load(self, *, timeout_s: float = 300.0) -> None:  # noqa: ARG002
        self.load_calls += 1

    def unload(self) -> None:
        self.unload_calls += 1


def verdict_reply(
    verdict: str = "consistent",
    confidence: float = 0.9,
    squares: list[str] | None = None,
    notes: str = "",
) -> str:
    """Serialise a well-formed ``verify_diagram`` reply."""
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": confidence,
            "suspect_squares": squares or [],
            "notes": notes,
        }
    )


@pytest.fixture
def audit() -> Iterator[AuditLog]:
    """An in-memory audit log installed for the duration of one test."""
    log = AuditLog(path=None)
    log._resolved = True  # noqa: SLF001 - keeps the test off the filesystem
    set_audit_log(log)
    yield log
    set_audit_log(None)


@pytest.fixture
def unavailable() -> FakeRuntime:
    """A runtime that is installed but cannot serve."""
    return FakeRuntime(available=False)


@pytest.fixture
def timing_out() -> FakeRuntime:
    """A runtime whose calls always time out."""
    return FakeRuntime(raises=LlmTimeoutError("estourou o prazo"))


__all__ = [
    "GOOD_FEN",
    "PNG_BYTES",
    "FakeRuntime",
    "guardrails",
    "verdict_reply",
]
