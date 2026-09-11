"""Local LLM inference runtime -- the only place that talks to a model (ADR-0005).

Runtime choice: **Ollama over localhost HTTP**, not ``llama-cpp-python``.

The reasoning, in the order the arguments actually weigh:

1. **It sidesteps the ADR-0003 conflict by construction.** ``llama-cpp-python``
   links its own CUDA runtime *into this process*, next to the ``cu128`` torch
   build that the vision pipeline needs. That is precisely the DLL collision
   ADR-0003 was written about, and its failure mode is silent CPU fallback.
   Ollama runs in a separate process, so the two CUDA runtimes never share an
   address space. The conflict cannot happen.
2. **No new dependency.** This module imports nothing outside the standard
   library -- ``urllib.request`` and ``json`` are enough. ``llama-cpp-python``
   would need a wheel that does not exist for Blackwell/``sm_120`` on Windows
   and CPython 3.11, i.e. a source build against the CUDA 12.8 toolkit, which is
   a fragile thing to put in a user-facing installer.
3. **Multimodal input is a first-class field.** Ollama takes ``images`` as
   base64 on ``/api/generate``. The multimodal path in ``llama-cpp-python`` has
   moved repeatedly and needs a matching ``mmproj`` handle wired by hand.
4. **Eviction actually frees VRAM.** ``keep_alive: 0`` makes the server drop the
   model immediately, which is what lets :mod:`caissa.llm.residency` implement a
   real ADR-0004 unloader rather than a hopeful one.

The cost is honest and stated: a background service the application does not
own. Every entry point therefore treats absence as normal -- see
:class:`NullRuntime` and :func:`get_runtime`. Nothing in Caissa may assume a
model is there.

Measured on the reference machine (RTX 5060, 8 GiB, driver 591.86) with
``gemma4:e4b-it-qat`` and ``num_ctx=4096``: 4271 MiB of VRAM while resident,
13.5 s cold start, sub-second warm calls. See ``docs/quality/F11_REPORT.md``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from base64 import b64encode
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol, runtime_checkable

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_MODEL_TAG",
    "CancellationToken",
    "GenerationChunk",
    "GenerationRequest",
    "GenerationResult",
    "LlmCancelledError",
    "LlmError",
    "LlmRuntime",
    "LlmTimeoutError",
    "LlmUnavailableError",
    "NullRuntime",
    "OllamaRuntime",
    "RuntimeInfo",
    "available_backends",
    "get_runtime",
    "reset_runtime",
]

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #

#: Where the Ollama service listens by default.
DEFAULT_HOST: Final = "http://127.0.0.1:11434"

#: The tag installed and measured for F11.
#:
#: This is deliberately *not* ``gemma4:e4b``. That tag resolves to
#: ``e4b-it-q4_K_M``, whose manifest has a single model layer and **no
#: ``mmproj`` projector**: it is text-only and cannot look at a diagram at all.
#: Only the ``-qat`` build ships the 478 M-parameter CLIP projector, and it is
#: also the smaller download (6.15 GB against 9.61 GB).
DEFAULT_MODEL_TAG: Final = "gemma4:e4b-it-qat"

#: Availability probes are cached this long so a missing service costs one
#: connection attempt per minute, not one per call.
_PROBE_TTL_S: Final = 60.0

_CONNECT_TIMEOUT_S: Final = 2.0
_MAX_IMAGE_BYTES: Final = 8 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class LlmError(RuntimeError):
    """Base class for every failure raised by this package."""


class LlmUnavailableError(LlmError):
    """No usable runtime. Callers must degrade, never propagate this to the UI."""


class LlmTimeoutError(LlmError, TimeoutError):
    """A call exceeded its wall-clock budget and was abandoned."""


class LlmCancelledError(LlmError):
    """A call was cancelled through its :class:`CancellationToken`."""


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


class CancellationToken:
    """Thread-safe one-way flag used to abandon an in-flight generation.

    The UI holds one per running job. ``cancel`` is idempotent and may be called
    from any thread; the generating thread notices between streamed chunks.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        """Create an un-cancelled token."""
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation. Safe to call more than once, from any thread."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise :class:`LlmCancelledError` if cancellation was requested."""
        if self._event.is_set():
            raise LlmCancelledError("geracao cancelada pelo usuario")

    def wait(self, timeout: float | None = None) -> bool:
        """Block until cancelled or ``timeout`` elapses. Returns the flag."""
        return self._event.wait(timeout)


# --------------------------------------------------------------------------- #
# Request / response
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One call to the model, fully specified.

    Attributes:
        prompt: The user turn. Templates come from :mod:`caissa.llm.prompts`;
            no caller should be assembling these from string literals.
        system: Optional system turn.
        images: Raw encoded image bytes (PNG/JPEG). Base64 happens here so that
            no caller has to remember to do it.
        max_tokens: Hard cap on generated tokens. There is no unbounded call in
            this package -- an LLM that rambles is a latency incident.
        temperature: 0.0 for every structured task. Anything above 0 must be a
            deliberate choice by a caller that can tolerate variance.
        seed: Fixed seed for reproducible output. Tests rely on this.
        stop: Stop strings.
        json_schema: When given, the server is asked to constrain output to this
            JSON schema. It is a *help*, never a guarantee -- the output is
            validated again in :mod:`caissa.llm.guardrails` regardless.
        timeout_s: Wall-clock budget for the whole call, including model load.
        num_ctx: Context window. Smaller is cheaper in VRAM; 4096 is what the
            F11 measurements used.
        think: Whether to let the model emit reasoning tokens. Gemma 4 has
            thinking **on by default**, which silently spends the entire
            ``max_tokens`` budget and returns an empty ``response`` -- measured,
            not assumed. Everything here therefore defaults to ``False``.
    """

    prompt: str
    system: str | None = None
    images: tuple[bytes, ...] = ()
    max_tokens: int = 256
    temperature: float = 0.0
    seed: int | None = 0
    stop: tuple[str, ...] = ()
    json_schema: Mapping[str, Any] | None = None
    timeout_s: float = 120.0
    num_ctx: int = 4096
    think: bool = False

    def __post_init__(self) -> None:
        """Reject requests that cannot be honoured."""
        if not self.prompt.strip():
            raise ValueError("GenerationRequest.prompt nao pode ser vazio")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens deve ser positivo (recebido: {self.max_tokens})")
        if self.timeout_s <= 0:
            raise ValueError(f"timeout_s deve ser positivo (recebido: {self.timeout_s})")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature fora de [0, 2] (recebido: {self.temperature})")
        for image in self.images:
            if len(image) > _MAX_IMAGE_BYTES:
                raise ValueError(
                    f"imagem de {len(image)} bytes excede o limite de {_MAX_IMAGE_BYTES}"
                )


@dataclass(frozen=True, slots=True)
class GenerationChunk:
    """One streamed fragment."""

    text: str
    done: bool


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """A completed generation plus everything the audit log needs.

    Attributes:
        text: The generated text, with reasoning tokens excluded.
        model: The tag that actually answered.
        latency_ms: Wall-clock milliseconds, including any model load.
        prompt_tokens: Tokens consumed by prompt and images.
        completion_tokens: Tokens generated.
        truncated: Whether generation stopped at ``max_tokens`` rather than at a
            natural end. A truncated structured answer is almost always invalid
            JSON, so guardrails treat this as a rejection signal.
        thinking: Reasoning tokens, kept for the audit trail only.
    """

    text: str
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    truncated: bool = False
    thinking: str = ""


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
    """What a runtime is and whether it can serve. Shown in the UI diagnostics."""

    backend: str
    model: str
    available: bool
    detail: str = ""
    vision: bool = False
    server_version: str = ""


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #


@runtime_checkable
class LlmRuntime(Protocol):
    """What every task in :mod:`caissa.llm.tasks` is allowed to assume.

    Deliberately tiny. Anything richer would tempt callers to reach past the
    guardrails.
    """

    def info(self) -> RuntimeInfo:
        """Describe the backend and whether it can serve right now."""
        ...

    def is_available(self) -> bool:
        """Whether a call would have any chance of succeeding."""
        ...

    def stream(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> Iterator[GenerationChunk]:
        """Yield fragments as they are produced."""
        ...

    def generate(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> GenerationResult:
        """Run to completion and return the whole answer."""
        ...

    def load(self, *, timeout_s: float = 300.0) -> None:
        """Bring the weights into VRAM now (used by the residency loader)."""
        ...

    def unload(self) -> None:
        """Drop the weights from VRAM now (used by the residency unloader)."""
        ...


# --------------------------------------------------------------------------- #
# Null runtime -- the case that must always work
# --------------------------------------------------------------------------- #


class NullRuntime:
    """The runtime used when there is no model. Never raises on inspection.

    Every task in this package checks :meth:`is_available` and degrades. This
    class exists so that "no LLM" is an ordinary object rather than a ``None``
    that every call site has to remember to test.
    """

    __slots__ = ("_reason",)

    def __init__(self, reason: str = "nenhum runtime de LLM configurado") -> None:
        """Record why no model is available, for the diagnostics panel."""
        self._reason = reason

    def info(self) -> RuntimeInfo:
        """Describe the absent backend."""
        return RuntimeInfo(backend="none", model="", available=False, detail=self._reason)

    def is_available(self) -> bool:
        """Always ``False``."""
        return False

    def stream(
        self,
        request: GenerationRequest,  # noqa: ARG002 - protocol conformance
        cancel: CancellationToken | None = None,  # noqa: ARG002
    ) -> Iterator[GenerationChunk]:
        """Raise :class:`LlmUnavailableError`; callers must not get here."""
        raise LlmUnavailableError(self._reason)

    def generate(
        self,
        request: GenerationRequest,  # noqa: ARG002
        cancel: CancellationToken | None = None,  # noqa: ARG002
    ) -> GenerationResult:
        """Raise :class:`LlmUnavailableError`; callers must not get here."""
        raise LlmUnavailableError(self._reason)

    def load(self, *, timeout_s: float = 300.0) -> None:
        """Raise :class:`LlmUnavailableError`."""
        raise LlmUnavailableError(self._reason)

    def unload(self) -> None:
        """Do nothing -- there is nothing resident."""


# --------------------------------------------------------------------------- #
# Ollama runtime
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _ProbeCache:
    """Memo of the last availability probe."""

    checked_at: float = 0.0
    info: RuntimeInfo | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class OllamaRuntime:
    """Talks to a local Ollama service over HTTP.

    Args:
        model: Model tag to call.
        host: Base URL of the service.
        keep_alive: How long the server should hold the weights after a call.
            ``"0"`` unloads immediately; the residency manager overrides this
            when it owns the lifecycle.
        opener: Injected URL opener, so tests never touch a socket.
        clock: Injected monotonic clock, for deterministic timeout tests.
    """

    __slots__ = ("_clock", "_host", "_keep_alive", "_model", "_opener", "_probe")

    def __init__(
        self,
        model: str = DEFAULT_MODEL_TAG,
        *,
        host: str = DEFAULT_HOST,
        keep_alive: str = "5m",
        opener: Any | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        """Build a runtime bound to one model tag."""
        self._model = model
        self._host = host.rstrip("/")
        self._keep_alive = keep_alive
        self._opener = opener or urllib.request.urlopen
        self._clock = clock
        self._probe = _ProbeCache()

    # -- introspection ----------------------------------------------------- #

    @property
    def model(self) -> str:
        """The tag this runtime calls."""
        return self._model

    def info(self, *, refresh: bool = False) -> RuntimeInfo:
        """Probe the service, at most once per :data:`_PROBE_TTL_S`.

        Args:
            refresh: Ignore the cached answer and probe again.

        Returns:
            A :class:`RuntimeInfo`. Never raises: an unreachable service is a
            normal, expected state.
        """
        with self._probe.lock:
            cached = self._probe.info
            if (
                cached is not None
                and not refresh
                and self._clock() - self._probe.checked_at < _PROBE_TTL_S
            ):
                return cached
            info = self._probe_now()
            self._probe.info = info
            self._probe.checked_at = self._clock()
            return info

    def _probe_now(self) -> RuntimeInfo:
        """Ask the service for its version and whether the tag has vision."""
        try:
            version = self._get_json("/api/version", timeout=_CONNECT_TIMEOUT_S)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            return RuntimeInfo(
                backend="ollama",
                model=self._model,
                available=False,
                detail=(
                    f"servico Ollama inacessivel em {self._host} ({type(exc).__name__}). "
                    f"A aplicacao segue funcionando sem o LLM."
                ),
            )
        server_version = str(version.get("version", "?"))
        try:
            shown = self._post_json("/api/show", {"model": self._model}, timeout=15.0)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            return RuntimeInfo(
                backend="ollama",
                model=self._model,
                available=False,
                server_version=server_version,
                detail=(
                    f"modelo '{self._model}' nao instalado ({type(exc).__name__}). "
                    f"Instale com: ollama pull {self._model}"
                ),
            )
        capabilities = shown.get("capabilities") or []
        vision = "vision" in capabilities
        detail = "" if vision else f"'{self._model}' nao aceita imagens; tarefas visuais ficam off"
        return RuntimeInfo(
            backend="ollama",
            model=self._model,
            available=True,
            vision=vision,
            server_version=server_version,
            detail=detail,
        )

    def is_available(self) -> bool:
        """Whether the service is up and the tag is installed."""
        return self.info().available

    # -- HTTP plumbing ----------------------------------------------------- #

    def _request(self, path: str, payload: Mapping[str, Any] | None, timeout: float) -> Any:
        """Open one HTTP call and return the raw response object."""
        url = f"{self._host}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 - fixed localhost scheme, see _check_host
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="GET" if data is None else "POST",
        )
        return self._opener(req, timeout=timeout)

    def _get_json(self, path: str, *, timeout: float) -> dict[str, Any]:
        """GET a JSON document."""
        with self._request(path, None, timeout) as response:
            parsed: Any = json.loads(response.read())
        if not isinstance(parsed, dict):
            raise ValueError(f"resposta inesperada de {path}")
        return parsed

    def _post_json(
        self, path: str, payload: Mapping[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        """POST a JSON document and parse the JSON reply."""
        with self._request(path, payload, timeout) as response:
            parsed: Any = json.loads(response.read())
        if not isinstance(parsed, dict):
            raise ValueError(f"resposta inesperada de {path}")
        return parsed

    def _build_payload(self, request: GenerationRequest, *, stream: bool) -> dict[str, Any]:
        """Translate a :class:`GenerationRequest` into the Ollama wire format."""
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
            "num_ctx": request.num_ctx,
        }
        if request.seed is not None:
            options["seed"] = request.seed
            # Greedy decoding is what actually makes a seed reproducible; a seed
            # with top_p sampling still wanders between server versions.
            options["top_k"] = 1
            options["top_p"] = 1.0
        if request.stop:
            options["stop"] = list(request.stop)
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": request.prompt,
            "stream": stream,
            "think": request.think,
            "options": options,
            "keep_alive": self._keep_alive,
        }
        if request.system:
            payload["system"] = request.system
        if request.images:
            payload["images"] = [b64encode(image).decode("ascii") for image in request.images]
        if request.json_schema is not None:
            payload["format"] = dict(request.json_schema)
        return payload

    # -- generation -------------------------------------------------------- #

    def stream(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> Iterator[GenerationChunk]:
        """Yield fragments as the server produces them.

        Cancellation and the timeout are both checked between fragments, and the
        connection is closed on the way out, which is what makes the server stop
        generating rather than finishing into a socket nobody reads.

        Raises:
            LlmUnavailableError: If the service or the model is missing.
            LlmTimeoutError: If ``request.timeout_s`` elapses.
            LlmCancelledError: If ``cancel`` was fired.
        """
        info = self.info()
        if not info.available:
            raise LlmUnavailableError(info.detail or "runtime indisponivel")
        if request.images and not info.vision:
            raise LlmUnavailableError(
                f"'{self._model}' nao tem projetor de visao; nao aceita imagens"
            )
        yield from self._stream_raw(request, cancel)

    def _stream_raw(
        self, request: GenerationRequest, cancel: CancellationToken | None
    ) -> Iterator[GenerationChunk]:
        """Stream without the availability preamble (used by :meth:`generate`)."""
        payload = self._build_payload(request, stream=True)
        deadline = self._clock() + request.timeout_s
        if cancel is not None:
            cancel.raise_if_cancelled()
        try:
            response = self._request("/api/generate", payload, request.timeout_s)
        except (OSError, urllib.error.URLError) as exc:
            raise LlmUnavailableError(f"falha ao contatar {self._host}: {exc}") from exc
        try:
            for raw_line in response:
                if cancel is not None and cancel.cancelled:
                    raise LlmCancelledError("geracao cancelada pelo usuario")
                if self._clock() > deadline:
                    raise LlmTimeoutError(
                        f"geracao excedeu {request.timeout_s:.1f}s e foi abandonada"
                    )
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("linha nao-JSON do Ollama ignorada: %r", line[:120])
                    continue
                if error := event.get("error"):
                    raise LlmError(f"Ollama respondeu com erro: {error}")
                done = bool(event.get("done"))
                yield GenerationChunk(text=str(event.get("response", "")), done=done)
                if done:
                    return
        finally:
            response.close()

    def generate(
        self, request: GenerationRequest, cancel: CancellationToken | None = None
    ) -> GenerationResult:
        """Run to completion.

        Implemented on top of the non-streaming endpoint because the final event
        carries the token counts and the stop reason, both of which the audit log
        needs and neither of which can be reconstructed from fragments.
        """
        info = self.info()
        if not info.available:
            raise LlmUnavailableError(info.detail or "runtime indisponivel")
        if request.images and not info.vision:
            raise LlmUnavailableError(
                f"'{self._model}' nao tem projetor de visao; nao aceita imagens"
            )
        if cancel is not None:
            cancel.raise_if_cancelled()

        payload = self._build_payload(request, stream=False)
        started = self._clock()
        try:
            event = self._post_json("/api/generate", payload, timeout=request.timeout_s)
        except TimeoutError as exc:
            raise LlmTimeoutError(
                f"geracao excedeu {request.timeout_s:.1f}s e foi abandonada"
            ) from exc
        except (OSError, urllib.error.URLError) as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise LlmTimeoutError(
                    f"geracao excedeu {request.timeout_s:.1f}s e foi abandonada"
                ) from exc
            raise LlmUnavailableError(f"falha ao contatar {self._host}: {exc}") from exc
        elapsed_ms = (self._clock() - started) * 1000.0
        if cancel is not None and cancel.cancelled:
            raise LlmCancelledError("geracao cancelada pelo usuario")
        if error := event.get("error"):
            raise LlmError(f"Ollama respondeu com erro: {error}")
        return GenerationResult(
            text=str(event.get("response", "")),
            model=str(event.get("model", self._model)),
            latency_ms=elapsed_ms,
            prompt_tokens=int(event.get("prompt_eval_count", 0) or 0),
            completion_tokens=int(event.get("eval_count", 0) or 0),
            truncated=str(event.get("done_reason", "")) == "length",
            thinking=str(event.get("thinking", "") or ""),
        )

    # -- residency hooks --------------------------------------------------- #

    def load(self, *, timeout_s: float = 300.0) -> None:
        """Ask the server to bring the weights into VRAM and hold them.

        An empty prompt with a ``keep_alive`` is Ollama's documented way to load
        without generating. Cold load of ``gemma4:e4b-it-qat`` measured 13.5 s.
        """
        info = self.info(refresh=True)
        if not info.available:
            raise LlmUnavailableError(info.detail or "runtime indisponivel")
        self._post_json(
            "/api/generate",
            {"model": self._model, "prompt": "", "keep_alive": self._keep_alive, "stream": False},
            timeout=timeout_s,
        )

    def unload(self) -> None:
        """Ask the server to drop the weights immediately.

        This is what makes ADR-0004 eviction real for the LLM: without it the
        manager would decrement a number while 4.2 GiB stayed resident in
        another process. Failures are logged, not raised -- eviction runs on
        cleanup paths where an exception would be worse than a stale resident.
        """
        try:
            self._post_json(
                "/api/generate",
                {"model": self._model, "prompt": "", "keep_alive": 0, "stream": False},
                timeout=30.0,
            )
        except (OSError, urllib.error.URLError, ValueError) as exc:
            logger.warning("nao foi possivel descarregar '%s' do Ollama: %s", self._model, exc)


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #

_RUNTIME_LOCK = threading.Lock()
_RUNTIME: LlmRuntime | None = None


def _configured(env: Mapping[str, str] | None = None) -> tuple[bool, str, str]:
    """Resolve ``(enabled, model, host)`` from configuration and environment.

    ``caissa.core.config`` owns :class:`~caissa.core.config.schema.LlmConfig`
    but has no field for the backend host, so the host is read from the
    environment. Configuration is read defensively: a broken config file must
    not take the whole application down over an *optional* subsystem.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    enabled = False
    model = DEFAULT_MODEL_TAG
    try:
        from caissa.core.config import get_config  # noqa: PLC0415 - optional, deliberately lazy

        llm = get_config().llm
        enabled = bool(llm.enabled)
        # `model_id` defaults to the family name "gemma-4-e4b", which is not an
        # Ollama tag. Only honour it when it looks like one.
        if ":" in llm.model_id:
            model = llm.model_id
    except Exception as exc:  # noqa: BLE001 - optional subsystem, never fatal
        logger.debug("configuracao de LLM indisponivel (%s); usando padroes", exc)

    # Both spellings are honoured, and the double-underscore one is the one to
    # prefer: `caissa.core.config` maps `CAISSA_LLM__ENABLED` onto
    # `llm.enabled`, and *rejects* the single-underscore name as an unknown
    # option. Measured in F11 cycle 2: a run started with `CAISSA_LLM_ENABLED=1`
    # got a working LLM and a broken `get_config()`, which silently took the
    # audit log with it. Accepting the correct name here is what lets a caller
    # enable the subsystem without breaking the configuration around it.
    for name in ("CAISSA_LLM_ENABLED", "CAISSA_LLM__ENABLED"):
        if raw := environ.get(name):
            enabled = raw.strip().lower() in {"1", "true", "yes", "on", "sim"}
    for name in ("CAISSA_LLM_MODEL", "CAISSA_LLM__MODEL_ID"):
        if raw := environ.get(name):
            model = raw.strip()
    host = environ.get("OLLAMA_HOST") or environ.get("CAISSA_LLM_HOST") or DEFAULT_HOST
    if host and not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return enabled, model, host


def get_runtime(*, env: Mapping[str, str] | None = None, force: bool = False) -> LlmRuntime:
    """Return the process-wide runtime, building it on first use.

    Args:
        env: Environment override, for tests.
        force: Build an :class:`OllamaRuntime` even when ``llm.enabled`` is
            false. The benchmark uses this; ordinary code must not.

    Returns:
        An :class:`OllamaRuntime` when the LLM is enabled, otherwise a
        :class:`NullRuntime`. **This function never raises.** Callers get an
        object either way and ask it whether it can serve.
    """
    global _RUNTIME  # noqa: PLW0603 - deliberate process-wide singleton
    with _RUNTIME_LOCK:
        if _RUNTIME is not None and not force and env is None:
            return _RUNTIME
        enabled, model, host = _configured(env)
        runtime: LlmRuntime
        if enabled or force:
            runtime = OllamaRuntime(model, host=host)
        else:
            runtime = NullRuntime(
                "LLM desativado (llm.enabled = false). "
                "Todas as funcoes de reconhecimento seguem disponiveis."
            )
        if env is None:
            _RUNTIME = runtime
        return runtime


def reset_runtime() -> None:
    """Drop the cached runtime. For tests and for configuration changes."""
    global _RUNTIME  # noqa: PLW0603 - matches get_runtime
    with _RUNTIME_LOCK:
        _RUNTIME = None


def available_backends(env: Mapping[str, str] | None = None) -> Sequence[RuntimeInfo]:
    """Probe every backend Caissa knows about, for ``scripts/doctor.py``."""
    _, model, host = _configured(env)
    return [OllamaRuntime(model, host=host).info(refresh=True)]
