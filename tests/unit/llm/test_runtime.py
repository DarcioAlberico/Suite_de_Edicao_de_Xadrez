"""Runtime mechanics: seeding, timeout, cancellation, streaming, request shape.

Every test here drives a fake ``urlopen``. Nothing opens a socket, so the suite
runs identically on a machine with no Ollama and no GPU.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
from base64 import b64decode

import pytest

from caissa.llm.runtime import (
    DEFAULT_MODEL_TAG,
    CancellationToken,
    GenerationRequest,
    LlmCancelledError,
    LlmTimeoutError,
    LlmUnavailableError,
    NullRuntime,
    OllamaRuntime,
    get_runtime,
    reset_runtime,
)

from .conftest import PNG_BYTES


class FakeResponse:
    """Minimal stand-in for an ``http.client.HTTPResponse``."""

    def __init__(self, lines: list[str], *, on_close=None) -> None:
        self._lines = [line.encode("utf-8") for line in lines]
        self._on_close = on_close
        self.closed = False

    def read(self) -> bytes:
        return b"".join(self._lines)

    def __iter__(self):
        yield from self._lines

    def close(self) -> None:
        self.closed = True
        if self._on_close is not None:
            self._on_close()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def make_opener(routes: dict[str, object], *, record: list | None = None):
    """Build a fake ``urlopen`` that answers by URL suffix."""

    def opener(request, timeout=None):  # noqa: ANN001, ARG001
        if record is not None:
            body = json.loads(request.data) if request.data else None
            record.append((request.full_url, body, timeout))
        for suffix, response in routes.items():
            if request.full_url.endswith(suffix):
                if isinstance(response, Exception):
                    raise response
                if callable(response):
                    return response()
                return response
        raise urllib.error.URLError(f"rota nao roteada: {request.full_url}")

    return opener


def healthy_routes(reply: str = '{"verdict": "consistent"}', *, vision: bool = True):
    """Routes for a service that is up, with the model installed."""
    return {
        "/api/version": lambda: FakeResponse([json.dumps({"version": "0.33.2"})]),
        "/api/show": lambda: FakeResponse(
            [json.dumps({"capabilities": ["completion", "vision"] if vision else ["completion"]})]
        ),
        "/api/generate": lambda: FakeResponse(
            [
                json.dumps(
                    {
                        "model": DEFAULT_MODEL_TAG,
                        "response": reply,
                        "done": True,
                        "done_reason": "stop",
                        "prompt_eval_count": 100,
                        "eval_count": 20,
                    }
                )
            ]
        ),
    }


@pytest.fixture(autouse=True)
def _clean_runtime():
    reset_runtime()
    yield
    reset_runtime()


# --------------------------------------------------------------------------- #
# Request construction
# --------------------------------------------------------------------------- #


def test_request_rejects_impossible_parameters():
    with pytest.raises(ValueError, match="prompt"):
        GenerationRequest(prompt="   ")
    with pytest.raises(ValueError, match="max_tokens"):
        GenerationRequest(prompt="x", max_tokens=0)
    with pytest.raises(ValueError, match="timeout_s"):
        GenerationRequest(prompt="x", timeout_s=0)
    with pytest.raises(ValueError, match="temperature"):
        GenerationRequest(prompt="x", temperature=9.0)


def test_request_rejects_an_oversized_image():
    with pytest.raises(ValueError, match="excede o limite"):
        GenerationRequest(prompt="x", images=(b"\x00" * (9 * 1024 * 1024),))


def test_thinking_is_off_by_default():
    """Gemma 4 thinks by default and returns an empty `response`; measured, not assumed."""
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi"))
    body = next(body for url, body, _ in calls if url.endswith("/api/generate"))
    assert body["think"] is False


def test_seed_implies_greedy_decoding():
    """A seed with sampling on is not reproducible; the runtime pins top_k/top_p."""
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi", seed=1234, temperature=0.0))
    options = next(body for url, body, _ in calls if url.endswith("/api/generate"))["options"]
    assert options["seed"] == 1234
    assert options["top_k"] == 1
    assert options["top_p"] == 1.0
    assert options["temperature"] == 0.0


def test_no_seed_means_no_forced_greedy():
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi", seed=None))
    options = next(body for url, body, _ in calls if url.endswith("/api/generate"))["options"]
    assert "seed" not in options
    assert "top_k" not in options


def test_images_are_base64_encoded_once():
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi", images=(PNG_BYTES,)))
    body = next(body for url, body, _ in calls if url.endswith("/api/generate"))
    assert b64decode(body["images"][0]) == PNG_BYTES


def test_token_cap_reaches_the_wire():
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi", max_tokens=42))
    options = next(body for url, body, _ in calls if url.endswith("/api/generate"))["options"]
    assert options["num_predict"] == 42


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_same_seed_produces_the_same_request_bytes():
    """Reproducibility starts with an identical request; tests depend on it."""
    first: list = []
    second: list = []
    request = GenerationRequest(prompt="analise", seed=7, temperature=0.0, max_tokens=64)
    OllamaRuntime(opener=make_opener(healthy_routes(), record=first)).generate(request)
    OllamaRuntime(opener=make_opener(healthy_routes(), record=second)).generate(request)
    payload_a = next(body for url, body, _ in first if url.endswith("/api/generate"))
    payload_b = next(body for url, body, _ in second if url.endswith("/api/generate"))
    assert json.dumps(payload_a, sort_keys=True) == json.dumps(payload_b, sort_keys=True)


def test_deterministic_task_output_is_stable_across_calls():
    """Given a stable model, a task must return the same object every time."""
    from caissa.llm.tasks import verify_diagram  # noqa: PLC0415 - local by design

    from .conftest import GOOD_FEN, FakeRuntime, verdict_reply  # noqa: PLC0415

    reply = verdict_reply("inconsistent", 0.8, ["e4", "d5"], "nota")
    results = [
        verify_diagram(PNG_BYTES, GOOD_FEN, runtime=FakeRuntime([reply]), seed=0) for _ in range(5)
    ]
    for result in results[1:]:
        assert result.verdict == results[0].verdict
        assert result.confidence == results[0].confidence
        assert result.suspect_squares == results[0].suspect_squares


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


def test_dead_service_reports_unavailable_and_does_not_raise():
    runtime = OllamaRuntime(opener=make_opener({"/api/version": urllib.error.URLError("recusado")}))
    info = runtime.info()
    assert info.available is False
    assert "inacessivel" in info.detail
    assert runtime.is_available() is False


def test_missing_model_names_the_pull_command():
    """The error text must tell the user what to do, in one line."""
    routes = healthy_routes()
    routes["/api/show"] = urllib.error.HTTPError("u", 404, "not found", {}, None)  # type: ignore[arg-type]
    info = OllamaRuntime("gemma4:e4b-it-qat", opener=make_opener(routes)).info()
    assert info.available is False
    assert "ollama pull gemma4:e4b-it-qat" in info.detail


def test_text_only_model_refuses_images():
    """`gemma4:e4b` has no projector; sending it a diagram must fail loudly, not silently."""
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(vision=False)))
    assert runtime.info().vision is False
    with pytest.raises(LlmUnavailableError, match="projetor de visao"):
        runtime.generate(GenerationRequest(prompt="oi", images=(PNG_BYTES,)))


def test_probe_is_cached():
    """A missing service costs one probe per minute, not one per call."""
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    for _ in range(10):
        runtime.is_available()
    assert sum(1 for url, _, _ in calls if url.endswith("/api/version")) == 1


def test_probe_refresh_forces_a_new_check():
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.info()
    runtime.info(refresh=True)
    assert sum(1 for url, _, _ in calls if url.endswith("/api/version")) == 2


# --------------------------------------------------------------------------- #
# Timeout
# --------------------------------------------------------------------------- #


def test_socket_timeout_becomes_a_typed_timeout_error():
    routes = healthy_routes()
    routes["/api/generate"] = TimeoutError("read timed out")
    runtime = OllamaRuntime(opener=make_opener(routes))
    with pytest.raises(LlmTimeoutError):
        runtime.generate(GenerationRequest(prompt="oi", timeout_s=1.0))


def test_urlerror_wrapping_a_timeout_is_also_a_timeout():
    routes = healthy_routes()
    routes["/api/generate"] = urllib.error.URLError(TimeoutError("timed out"))
    runtime = OllamaRuntime(opener=make_opener(routes))
    with pytest.raises(LlmTimeoutError):
        runtime.generate(GenerationRequest(prompt="oi", timeout_s=1.0))


def test_timeout_budget_reaches_the_socket():
    calls: list = []
    runtime = OllamaRuntime(opener=make_opener(healthy_routes(), record=calls))
    runtime.generate(GenerationRequest(prompt="oi", timeout_s=9.5))
    timeout = next(t for url, _, t in calls if url.endswith("/api/generate"))
    assert timeout == 9.5


def test_streaming_stops_at_the_deadline():
    """A stream that never ends is abandoned when the wall clock runs out."""
    now = [0.0]

    def clock() -> float:
        now[0] += 5.0
        return now[0]

    endless = [json.dumps({"response": "tick ", "done": False}) for _ in range(100)]
    routes = healthy_routes()
    routes["/api/generate"] = lambda: FakeResponse(endless)
    runtime = OllamaRuntime(opener=make_opener(routes), clock=clock)
    with pytest.raises(LlmTimeoutError):
        list(runtime.stream(GenerationRequest(prompt="oi", timeout_s=10.0)))


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


def test_cancellation_before_the_call_is_immediate():
    token = CancellationToken()
    token.cancel()
    runtime = OllamaRuntime(opener=make_opener(healthy_routes()))
    with pytest.raises(LlmCancelledError):
        runtime.generate(GenerationRequest(prompt="oi"), token)


def test_cancellation_mid_stream_stops_and_closes_the_connection():
    """Closing the socket is what makes the server stop generating."""
    token = CancellationToken()
    closed: list[bool] = []
    lines = [json.dumps({"response": f"{index} ", "done": False}) for index in range(50)]
    routes = healthy_routes()
    routes["/api/generate"] = lambda: FakeResponse(lines, on_close=lambda: closed.append(True))
    runtime = OllamaRuntime(opener=make_opener(routes))

    received = []
    with pytest.raises(LlmCancelledError):
        for chunk in runtime.stream(GenerationRequest(prompt="oi"), token):
            received.append(chunk.text)
            if len(received) == 3:
                token.cancel()
    assert len(received) == 3
    assert closed == [True]


def test_cancellation_is_thread_safe():
    """The UI cancels from another thread while a worker is generating."""
    token = CancellationToken()
    lines = [json.dumps({"response": "x", "done": False}) for _ in range(2000)]
    routes = healthy_routes()
    routes["/api/generate"] = lambda: FakeResponse(lines)
    runtime = OllamaRuntime(opener=make_opener(routes))
    outcome: list[str] = []

    def worker() -> None:
        try:
            for _ in runtime.stream(GenerationRequest(prompt="oi"), token):
                time.sleep(0.0005)
        except LlmCancelledError:
            outcome.append("cancelled")

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.05)
    token.cancel()
    thread.join(timeout=10)
    assert outcome == ["cancelled"]


def test_token_is_idempotent():
    token = CancellationToken()
    assert token.cancelled is False
    token.cancel()
    token.cancel()
    assert token.cancelled is True
    with pytest.raises(LlmCancelledError):
        token.raise_if_cancelled()


# --------------------------------------------------------------------------- #
# Streaming
# --------------------------------------------------------------------------- #


def test_stream_yields_fragments_then_stops_at_done():
    lines = [
        json.dumps({"response": "Bran", "done": False}),
        json.dumps({"response": "cas", "done": False}),
        json.dumps({"response": " jogam", "done": True}),
        json.dumps({"response": "NAO DEVE APARECER", "done": False}),
    ]
    routes = healthy_routes()
    routes["/api/generate"] = lambda: FakeResponse(lines)
    runtime = OllamaRuntime(opener=make_opener(routes))
    chunks = list(runtime.stream(GenerationRequest(prompt="oi")))
    assert "".join(chunk.text for chunk in chunks) == "Brancas jogam"
    assert chunks[-1].done is True


def test_stream_skips_malformed_lines():
    lines = ["", "not json", json.dumps({"response": "ok", "done": True})]
    routes = healthy_routes()
    routes["/api/generate"] = lambda: FakeResponse(lines)
    runtime = OllamaRuntime(opener=make_opener(routes))
    assert "".join(c.text for c in runtime.stream(GenerationRequest(prompt="oi"))) == "ok"


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #


def test_factory_honours_the_environment_switch():
    assert isinstance(get_runtime(env={}), NullRuntime)
    assert isinstance(get_runtime(env={"CAISSA_LLM_ENABLED": "1"}), OllamaRuntime)
    assert isinstance(get_runtime(env={"CAISSA_LLM_ENABLED": "sim"}), OllamaRuntime)
    assert isinstance(get_runtime(env={"CAISSA_LLM_ENABLED": "0"}), NullRuntime)


def test_factory_reads_the_model_and_host():
    runtime = get_runtime(
        env={
            "CAISSA_LLM_ENABLED": "1",
            "CAISSA_LLM_MODEL": "gemma4:e2b-it-qat",
            "OLLAMA_HOST": "127.0.0.1:9999",
        }
    )
    assert isinstance(runtime, OllamaRuntime)
    assert runtime.model == "gemma4:e2b-it-qat"


def test_default_tag_is_the_multimodal_one():
    """`gemma4:e4b` is text-only. Defaulting to it would silently disable SPEC 6.5."""
    assert DEFAULT_MODEL_TAG == "gemma4:e4b-it-qat"
