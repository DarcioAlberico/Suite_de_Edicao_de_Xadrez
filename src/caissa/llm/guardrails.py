"""The part that decides whether the model's answer is allowed to matter.

An LLM that confidently invents a FEN is worse than no LLM at all, because it
launders a wrong answer into a confident one and the user stops checking. This
module exists so that a hallucination costs nothing but a log line.

Four defences, applied in order to every call:

1. **Bounded call.** Hard token cap and hard wall-clock timeout on every
   request. There is no unbounded generation in this package.
2. **Schema validation.** The reply is parsed as JSON and checked field by
   field against a declared shape. Anything unexpected -- a missing key, a
   string where a number belongs, an out-of-range confidence, a truncated
   answer -- is rejected. Rejection means "as if the LLM had not been called".
3. **Domain validation.** Chess claims are checked against the rules. A square
   name that is not a square is rejected; a FEN that does not parse or is not
   legal is rejected. `python-chess` is the arbiter, never the model.
4. **Bounded authority.** The result is fed through :class:`ConfidencePolicy`,
   which can only ever *lower* a confidence or *raise a flag*. There is no code
   path in Caissa where an LLM output raises a confidence or overwrites a
   high-confidence vision result. That is enforced here, in one place, and
   tested as an invariant rather than as a set of examples.

Everything is written to an append-only JSONL audit log -- prompt, output,
latency, decision -- so the user can answer "why did this change?" months later.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal

from caissa.llm.prompts import PromptTemplate
from caissa.llm.runtime import (
    CancellationToken,
    GenerationRequest,
    GenerationResult,
    LlmCancelledError,
    LlmError,
    LlmRuntime,
    LlmTimeoutError,
    LlmUnavailableError,
)

__all__ = [
    "MAX_TOKENS_CEILING",
    "TIMEOUT_CEILING_S",
    "AuditLog",
    "AuditRecord",
    "ConfidenceDecision",
    "ConfidencePolicy",
    "Decision",
    "FieldSpec",
    "GuardedOutcome",
    "SchemaViolation",
    "apply_verdict",
    "audit_log",
    "extract_json_object",
    "guarded_json_call",
    "is_legal_position",
    "json_schema_for",
    "normalise_square_names",
    "set_audit_log",
    "validate_fen",
    "validate_schema",
]

logger = logging.getLogger(__name__)

#: No prompt may ask for more than this, whatever its file says. A prompt file
#: is data; this is the code that does not trust it.
MAX_TOKENS_CEILING: Final = 1024

#: Nothing waits longer than this for the model, ever. The vision pipeline is
#: the product; the LLM is an assistant that must not be able to stall a batch.
TIMEOUT_CEILING_S: Final = 180.0

#: Above this vision confidence, the LLM may flag but may not change anything.
DEFAULT_HIGH_CONFIDENCE_FLOOR: Final = 0.90

#: The most a single LLM disagreement may cut a confidence by.
DEFAULT_MAX_PENALTY: Final = 0.60

_SQUARE_RE: Final = re.compile(r"^[a-h][1-8]$")
_FENCE_RE: Final = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

Decision = Literal[
    "accepted",
    "unavailable",
    "timeout",
    "cancelled",
    "runtime_error",
    "empty",
    "truncated",
    "not_json",
    "schema_violation",
    "domain_violation",
]


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class SchemaViolation(ValueError):
    """The model's JSON did not match the declared shape."""


# --------------------------------------------------------------------------- #
# JSON extraction and schema validation
# --------------------------------------------------------------------------- #


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply.

    Models wrap JSON in prose or in a fenced block however firmly the prompt asks
    them not to. This finds the object anyway, then the schema check decides
    whether it is usable. Being tolerant *here* and strict *there* is
    deliberate: tolerance in parsing costs nothing, tolerance in validation
    costs correctness.

    Raises:
        SchemaViolation: If no balanced JSON object can be found.
    """
    stripped = text.strip()
    if not stripped:
        raise SchemaViolation("resposta vazia")
    if fenced := _FENCE_RE.search(stripped):
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    if start < 0:
        raise SchemaViolation("resposta nao contem objeto JSON")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : index + 1]
                try:
                    parsed: Any = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise SchemaViolation(f"JSON malformado: {exc}") from exc
                if not isinstance(parsed, dict):
                    raise SchemaViolation("JSON de nivel superior nao e um objeto")
                return parsed
    raise SchemaViolation("objeto JSON nao fechado (resposta truncada?)")


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Declared shape of one field of a model reply.

    Attributes:
        kind: ``"str"``, ``"int"``, ``"float"``, ``"bool"`` or ``"list[str]"``.
        required: Whether absence is a violation. Optional fields fall back to
            ``default``.
        default: Value used when an optional field is absent or is ``None``.
        choices: Closed vocabulary. A value outside it is a violation -- this is
            what stops a model inventing a sixth verdict.
        minimum: Lower bound for numbers, inclusive.
        maximum: Upper bound for numbers, inclusive.
        max_length: Cap for strings and lists. Longer values are truncated
            rather than rejected: an over-long caption is a nuisance, not a lie.
        pattern: Regex every item must match (strings and list items).
    """

    kind: Literal["str", "int", "float", "bool", "list[str]"]
    required: bool = True
    default: Any = None
    choices: tuple[Any, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    pattern: re.Pattern[str] | None = None


def _coerce_scalar(name: str, value: Any, spec: FieldSpec) -> Any:  # noqa: PLR0912
    """Convert and range-check one scalar, raising on anything suspicious."""
    kind = spec.kind
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise SchemaViolation(f"campo '{name}' deveria ser booleano (recebido {value!r})")
    if kind in {"int", "float"}:
        if isinstance(value, bool):
            raise SchemaViolation(f"campo '{name}' deveria ser numero, veio booleano")
        try:
            number = int(value) if kind == "int" else float(value)
        except (TypeError, ValueError) as exc:
            raise SchemaViolation(f"campo '{name}' deveria ser {kind} (recebido {value!r})") from exc
        if spec.minimum is not None and number < spec.minimum:
            raise SchemaViolation(f"campo '{name}' = {number} abaixo do minimo {spec.minimum}")
        if spec.maximum is not None and number > spec.maximum:
            raise SchemaViolation(f"campo '{name}' = {number} acima do maximo {spec.maximum}")
        if spec.choices is not None and number not in spec.choices:
            raise SchemaViolation(f"campo '{name}' = {number!r} fora do vocabulario")
        return number
    # kind == "str"
    if not isinstance(value, str):
        raise SchemaViolation(f"campo '{name}' deveria ser texto (recebido {type(value).__name__})")
    text = value.strip()
    if spec.choices is not None and text not in spec.choices:
        raise SchemaViolation(f"campo '{name}' = {text!r} fora de {list(spec.choices)}")
    if spec.pattern is not None and not spec.pattern.match(text):
        raise SchemaViolation(f"campo '{name}' = {text!r} nao casa com o padrao exigido")
    if spec.max_length is not None and len(text) > spec.max_length:
        text = text[: spec.max_length].rstrip()
    return text


_JSON_TYPES: Final = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list[str]": "array",
}


def json_schema_for(schema: Mapping[str, FieldSpec]) -> dict[str, Any]:
    """Translate a :class:`FieldSpec` map into a JSON Schema for the server.

    Ollama takes a JSON Schema in ``format`` and compiles it into a decoding
    grammar, so the model *cannot* emit anything else. Before F11 cycle 2
    nothing in this package sent one, and ``GenerationRequest.json_schema``
    existed unused. The A/B on 233 real captions is in
    ``docs/quality/F11_REPORT_C2.md`` 3.2; the schema is derived from the same
    ``FieldSpec`` map that :func:`validate_schema` enforces afterwards -- one
    declaration, so the grammar and the validator cannot drift apart.

    It is a *help*, never a guarantee: the reply is still parsed and validated
    on the way back in. A grammar constrains shape, not truth.
    """
    properties: dict[str, Any] = {}
    for name, spec in schema.items():
        json_type = _JSON_TYPES[spec.kind]
        field: dict[str, Any] = {}
        if spec.choices is not None and spec.kind == "str":
            field["enum"] = [str(choice) for choice in spec.choices]
            field["type"] = json_type if spec.required else [json_type, "null"]
        else:
            field["type"] = json_type if spec.required else [json_type, "null"]
        if spec.kind == "list[str]":
            field["items"] = {"type": "string"}
        properties[name] = field
    return {
        "type": "object",
        "properties": properties,
        "required": [name for name, spec in schema.items() if spec.required],
    }


def validate_schema(payload: Mapping[str, Any], schema: Mapping[str, FieldSpec]) -> dict[str, Any]:
    """Check a parsed reply against a declared shape and return a clean dict.

    Unknown keys are dropped rather than rejected -- a model that adds a chatty
    ``"explanation"`` field has not lied about anything. Everything else is
    strict.

    Raises:
        SchemaViolation: On any missing, mistyped or out-of-range field.
    """
    cleaned: dict[str, Any] = {}
    for name, spec in schema.items():
        if name not in payload or payload[name] is None:
            if spec.required and spec.default is None:
                raise SchemaViolation(f"campo obrigatorio '{name}' ausente")
            cleaned[name] = spec.default
            continue
        raw = payload[name]
        if spec.kind == "list[str]":
            if isinstance(raw, str):
                raw = [raw]
            if not isinstance(raw, list):
                raise SchemaViolation(f"campo '{name}' deveria ser uma lista")
            items: list[str] = []
            item_spec = replace(spec, kind="str", max_length=None)
            for element in raw:
                items.append(_coerce_scalar(f"{name}[]", element, item_spec))
            if spec.max_length is not None:
                items = items[: spec.max_length]
            cleaned[name] = items
            continue
        cleaned[name] = _coerce_scalar(name, raw, spec)
    return cleaned


# --------------------------------------------------------------------------- #
# Domain validation -- chess is checked by chess, never by the model
# --------------------------------------------------------------------------- #


def validate_fen(fen: str, *, require_legal: bool = True) -> str | None:
    """Return a normalised FEN, or ``None`` if it is not usable.

    Args:
        fen: Candidate FEN or bare placement field.
        require_legal: Also demand a position that could occur in a real game
            (kings present, side not to move not in check, no pawns on the back
            ranks). Composition diagrams occasionally break the last of these,
            which is why it is a flag rather than a constant.

    Returns:
        The normalised FEN string, or ``None``. **Never raises** -- a rejected
        FEN is an ordinary outcome, and callers must treat ``None`` as "the LLM
        said nothing useful".
    """
    text = (fen or "").strip()
    if not text:
        return None
    try:
        import chess  # noqa: PLC0415 - core dependency, imported lazily to keep import cost off startup
    except ImportError:  # pragma: no cover - `chess` is a core dependency
        logger.error("python-chess indisponivel; nenhum FEN pode ser validado")
        return None
    if len(text.split()) == 1:
        text = f"{text} w - - 0 1"
    try:
        board = chess.Board(text)
    except ValueError:
        return None
    if require_legal and not is_legal_position(board):
        return None
    return board.fen()


def is_legal_position(board: Any) -> bool:
    """Whether a ``chess.Board`` is a position that could really occur.

    Uses ``python-chess``'s own status word rather than a hand-rolled rule list,
    so this stays correct as that library improves.
    """
    try:
        import chess  # noqa: PLC0415 - see validate_fen
    except ImportError:  # pragma: no cover
        return False
    status = board.status()
    fatal = (
        chess.STATUS_NO_WHITE_KING
        | chess.STATUS_NO_BLACK_KING
        | chess.STATUS_TOO_MANY_KINGS
        | chess.STATUS_TOO_MANY_WHITE_PAWNS
        | chess.STATUS_TOO_MANY_BLACK_PAWNS
        | chess.STATUS_PAWNS_ON_BACKRANK
        | chess.STATUS_TOO_MANY_WHITE_PIECES
        | chess.STATUS_TOO_MANY_BLACK_PIECES
        | chess.STATUS_OPPOSITE_CHECK
        | chess.STATUS_IMPOSSIBLE_CHECK
    )
    return not status & fatal


def normalise_square_names(values: Iterable[str], *, limit: int = 8) -> tuple[str, ...]:
    """Keep only strings that really are algebraic square names.

    A model asked for ``["e4", "d5"]`` will sometimes answer ``["e4", "the
    knight", "h9"]``. The junk is dropped silently: these are advisory hints for
    the review overlay, so a partial list is useful and a wrong list is not.
    """
    seen: list[str] = []
    for value in values:
        candidate = str(value).strip().lower()
        if _SQUARE_RE.match(candidate) and candidate not in seen:
            seen.append(candidate)
        if len(seen) >= limit:
            break
    return tuple(seen)


# --------------------------------------------------------------------------- #
# Bounded authority
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    """How much authority an LLM disagreement carries.

    Attributes:
        high_confidence_floor: At or above this vision confidence the LLM may
            only raise a flag. It cannot move the number, and it can never
            replace the FEN.
        max_penalty: Largest fraction a single disagreement may remove from a
            low-confidence item.
        min_llm_confidence: Below this the model's own stated confidence, its
            disagreement is ignored entirely.
    """

    high_confidence_floor: float = DEFAULT_HIGH_CONFIDENCE_FLOOR
    max_penalty: float = DEFAULT_MAX_PENALTY
    min_llm_confidence: float = 0.50

    @classmethod
    def from_config(cls) -> ConfidencePolicy:
        """Build from ``vision.square_confidence_threshold`` when available."""
        try:
            from caissa.core.config import get_config  # noqa: PLC0415 - optional at import time

            floor = float(get_config().vision.square_confidence_threshold)
        except Exception:  # noqa: BLE001 - configuration is optional here
            floor = DEFAULT_HIGH_CONFIDENCE_FLOOR
        return cls(high_confidence_floor=floor)


@dataclass(frozen=True, slots=True)
class ConfidenceDecision:
    """What the LLM was allowed to do to one vision result.

    Attributes:
        original: Confidence the vision pipeline reported.
        adjusted: Confidence after the LLM. Guaranteed ``<= original``.
        flagged: Whether to show the user a disagreement marker.
        reason: pt-BR explanation, shown in the review panel.
        verdict: What the model actually said.
    """

    original: float
    adjusted: float
    flagged: bool
    reason: str
    verdict: str

    @property
    def changed(self) -> bool:
        """Whether the confidence actually moved."""
        return abs(self.adjusted - self.original) > 1e-9


def apply_verdict(
    vision_confidence: float,
    verdict: str,
    llm_confidence: float,
    *,
    policy: ConfidencePolicy | None = None,
) -> ConfidenceDecision:
    """Fold an LLM verdict into a vision confidence, within strict limits.

    The invariants, which :mod:`tests.unit.llm.test_guardrails` checks against
    randomised inputs rather than examples:

    * ``adjusted <= original`` -- the LLM can never raise a confidence.
    * ``original >= high_confidence_floor`` implies ``adjusted == original`` --
      the LLM can never touch a high-confidence vision result.
    * ``verdict == "consistent"`` implies ``adjusted == original`` -- agreement
      is not evidence, because the model agrees with almost anything.

    Args:
        vision_confidence: What the pipeline reported, in ``[0, 1]``.
        verdict: ``"consistent"``, ``"inconsistent"`` or ``"uncertain"``.
        llm_confidence: The model's own stated confidence, in ``[0, 1]``.
        policy: Override the default limits.

    Returns:
        A :class:`ConfidenceDecision`.
    """
    rules = policy or ConfidencePolicy()
    original = min(1.0, max(0.0, float(vision_confidence)))

    if verdict != "inconsistent":
        reason = (
            "LLM concordou com a leitura da visao (concordancia nao aumenta a confianca)"
            if verdict == "consistent"
            else "LLM nao conseguiu decidir; leitura da visao mantida"
        )
        return ConfidenceDecision(original, original, flagged=False, reason=reason, verdict=verdict)

    if llm_confidence < rules.min_llm_confidence:
        return ConfidenceDecision(
            original,
            original,
            flagged=False,
            reason=(
                f"LLM discordou, mas com confianca propria baixa "
                f"({llm_confidence:.2f} < {rules.min_llm_confidence:.2f}); ignorado"
            ),
            verdict=verdict,
        )

    if original >= rules.high_confidence_floor:
        return ConfidenceDecision(
            original,
            original,
            flagged=True,
            reason=(
                f"LLM discordou, mas a visao esta em confianca alta "
                f"({original:.3f} >= {rules.high_confidence_floor:.2f}); "
                f"apenas sinalizado para revisao"
            ),
            verdict=verdict,
        )

    penalty = rules.max_penalty * min(1.0, max(0.0, float(llm_confidence)))
    adjusted = min(original, original * (1.0 - penalty))
    return ConfidenceDecision(
        original,
        adjusted,
        flagged=True,
        reason=(
            f"LLM discordou da leitura ({llm_confidence:.2f}); "
            f"confianca reduzida de {original:.3f} para {adjusted:.3f}"
        ),
        verdict=verdict,
    )


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """One line of the audit trail. Everything needed to explain a decision.

    Image bytes are recorded as digests, never inline: the corpus is
    copyrighted material that must not be duplicated into a log (CORPUS.md).
    """

    timestamp: str
    task: str
    prompt_id: str
    prompt_version: int
    prompt_sha256: str
    model: str
    decision: Decision
    detail: str
    latency_ms: float
    prompt_text: str
    system_text: str
    output_text: str
    image_digests: tuple[str, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Plain-data view for JSONL serialisation."""
        return {
            "timestamp": self.timestamp,
            "task": self.task,
            "prompt": f"{self.prompt_id}.v{self.prompt_version}",
            "prompt_sha256": self.prompt_sha256,
            "model": self.model,
            "decision": self.decision,
            "detail": self.detail,
            "latency_ms": round(self.latency_ms, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "truncated": self.truncated,
            "image_digests": list(self.image_digests),
            "prompt_text": self.prompt_text,
            "system_text": self.system_text,
            "output_text": self.output_text,
        }


class AuditLog:
    """Append-only JSONL trail of every LLM call.

    Failures to write are logged and swallowed. An audit log that can crash the
    application is a liability, not a safeguard.

    Args:
        path: Destination file. ``None`` resolves it from configuration, or from
            ``CAISSA_LLM_AUDIT``.
        max_text_chars: Prompts and outputs longer than this are truncated in
            the log. The full prompt is reconstructible from the prompt id,
            version and sha256 anyway.
    """

    __slots__ = ("_lock", "_max_text_chars", "_path", "_records", "_resolved")

    def __init__(self, path: Path | None = None, *, max_text_chars: int = 4000) -> None:
        """Create a log bound to ``path`` (resolved lazily on first write)."""
        self._path = path
        self._resolved = path is not None
        self._max_text_chars = max_text_chars
        self._lock = threading.Lock()
        self._records: list[AuditRecord] = []

    @property
    def path(self) -> Path | None:
        """Where records are written, once resolved."""
        if not self._resolved:
            self._path = self._resolve_path()
            self._resolved = True
        return self._path

    @staticmethod
    def _resolve_path() -> Path | None:
        """Find the log directory without letting configuration errors escape.

        There are two fallbacks and the second one matters. Measured in F11
        cycle 2: setting ``CAISSA_LLM_ENABLED`` -- the variable
        :mod:`caissa.llm.runtime` documents for turning the LLM on -- makes
        ``get_config()`` raise, because the configuration loader rejects
        unknown ``CAISSA_*`` names and expects ``CAISSA_LLM__ENABLED``. With
        only the first fallback, *the act of enabling the LLM silently turned
        its audit trail off*: an entire measurement run reached the model over
        a thousand times and left nothing on disk. An audit trail that
        disappears exactly when
        the subsystem is in use is worse than no audit trail, because nobody
        goes looking for a file they believe exists.

        So a broken configuration degrades to the platform's default log
        directory -- the same one :func:`caissa.core.config.schema.default_log_dir`
        computes, from a pure function that reads no file and validates no
        environment -- and only a filesystem with no home directory at all ends
        up memory-only.
        """
        if raw := os.environ.get("CAISSA_LLM_AUDIT"):
            return Path(raw)
        try:
            from caissa.core.config import get_config  # noqa: PLC0415 - optional

            return Path(get_config().paths.log_dir) / "llm_audit.jsonl"
        except Exception as exc:  # noqa: BLE001 - auditing must never be fatal
            logger.debug("configuracao indisponivel (%s); usando o log padrao", exc)
        try:
            from caissa.core.config.schema import default_log_dir  # noqa: PLC0415 - optional

            return default_log_dir() / "llm_audit.jsonl"
        except Exception as exc:  # noqa: BLE001 - auditing must never be fatal
            logger.warning("nenhum diretorio de log disponivel (%s); auditoria so em memoria", exc)
            return None

    def _clip(self, text: str) -> str:
        """Truncate long text for the log, marking that it was truncated."""
        if len(text) <= self._max_text_chars:
            return text
        return f"{text[: self._max_text_chars]}...[{len(text)} chars]"

    def write(self, record: AuditRecord) -> None:
        """Append one record. Never raises."""
        clipped = replace(
            record,
            prompt_text=self._clip(record.prompt_text),
            system_text=self._clip(record.system_text),
            output_text=self._clip(record.output_text),
        )
        with self._lock:
            self._records.append(clipped)
            destination = self.path
            if destination is None:
                return
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(clipped.as_dict(), ensure_ascii=False) + "\n")
            except OSError as exc:
                logger.warning("nao foi possivel gravar a auditoria do LLM em %s: %s", destination, exc)

    def records(self) -> tuple[AuditRecord, ...]:
        """Everything written in this process, for tests and the UI panel."""
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        """Forget in-memory records. Does not touch the file."""
        with self._lock:
            self._records.clear()


_AUDIT_LOCK = threading.Lock()
_AUDIT: AuditLog | None = None


def audit_log() -> AuditLog:
    """The process-wide audit log."""
    global _AUDIT  # noqa: PLW0603 - deliberate singleton
    with _AUDIT_LOCK:
        if _AUDIT is None:
            _AUDIT = AuditLog()
        return _AUDIT


def set_audit_log(log: AuditLog | None) -> None:
    """Replace the process-wide audit log. For tests and for a session-scoped log."""
    global _AUDIT  # noqa: PLW0603 - matches audit_log
    with _AUDIT_LOCK:
        _AUDIT = log


# --------------------------------------------------------------------------- #
# The guarded call
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class GuardedOutcome:
    """Result of one guarded call: either clean data or a recorded refusal.

    Attributes:
        payload: The validated fields, or ``None`` when nothing survived.
        decision: Why. ``"accepted"`` is the only value with a payload.
        detail: pt-BR explanation for the review panel.
        latency_ms: Wall clock, including a cold model load.
        raw_text: What the model actually said, for debugging.
    """

    payload: dict[str, Any] | None
    decision: Decision
    detail: str = ""
    latency_ms: float = 0.0
    raw_text: str = ""

    @property
    def ok(self) -> bool:
        """Whether there is usable data."""
        return self.payload is not None


def guarded_json_call(
    runtime: LlmRuntime,
    template: PromptTemplate,
    schema: Mapping[str, FieldSpec],
    values: Mapping[str, object],
    *,
    task: str,
    images: Sequence[bytes] = (),
    timeout_s: float = 60.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
    post_validate: Callable[[dict[str, Any]], str | None] | None = None,
    log: AuditLog | None = None,
    force_schema: bool = True,
) -> GuardedOutcome:
    """Render, call, validate, audit. The only sanctioned way to reach the model.

    Every failure mode ends in a :class:`GuardedOutcome` with ``payload=None``
    and a recorded reason. Nothing propagates: a task that cannot use the LLM
    must behave exactly as if the LLM were not installed.

    Args:
        runtime: The backend.
        template: A versioned prompt.
        schema: Declared shape of the reply.
        values: Placeholder values for the template.
        task: Task name for the audit trail.
        images: Image bytes to attach.
        timeout_s: Wall-clock budget, clamped to :data:`TIMEOUT_CEILING_S`.
        cancel: Cancellation token.
        seed: Fixed seed. ``None`` for deliberately varied output.
        post_validate: Domain check run after the schema check. Returns an error
            string to reject, or ``None`` to accept. This is where chess
            legality is enforced.
        log: Override the process-wide audit log.
        force_schema: Send the derived JSON Schema in Ollama's ``format`` field
            so the server constrains decoding to it. On by default; see
            :func:`json_schema_for`. ``False`` exists so the benchmark can
            measure what it buys rather than assert it.

    Returns:
        A :class:`GuardedOutcome`.
    """
    trail = log or audit_log()
    digests = tuple(sha256(image).hexdigest()[:16] for image in images)
    max_tokens = min(template.max_tokens, MAX_TOKENS_CEILING)
    budget = min(float(timeout_s), TIMEOUT_CEILING_S)

    def record(
        decision: Decision,
        detail: str,
        *,
        prompt_text: str = "",
        output: str = "",
        latency: float = 0.0,
        result: GenerationResult | None = None,
    ) -> GuardedOutcome:
        trail.write(
            AuditRecord(
                timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
                task=task,
                prompt_id=template.id,
                prompt_version=template.version,
                prompt_sha256=template.sha256,
                model=result.model if result else getattr(runtime, "model", ""),
                decision=decision,
                detail=detail,
                latency_ms=result.latency_ms if result else latency,
                prompt_text=prompt_text,
                system_text=template.system if prompt_text else "",
                output_text=output,
                image_digests=digests,
                prompt_tokens=result.prompt_tokens if result else 0,
                completion_tokens=result.completion_tokens if result else 0,
                truncated=bool(result.truncated) if result else False,
            )
        )
        return GuardedOutcome(
            payload=None,
            decision=decision,
            detail=detail,
            latency_ms=result.latency_ms if result else latency,
            raw_text=output,
        )

    if not runtime.is_available():
        return record("unavailable", "runtime de LLM indisponivel")

    try:
        prompt_text = template.render(**dict(values))
    except Exception as exc:  # noqa: BLE001 - a template bug must not crash a batch
        return record("runtime_error", f"falha ao montar o prompt: {exc}")

    request = GenerationRequest(
        prompt=prompt_text,
        system=template.system,
        images=tuple(images),
        max_tokens=max_tokens,
        temperature=template.temperature,
        seed=seed,
        stop=template.stop,
        timeout_s=budget,
        json_schema=json_schema_for(schema) if force_schema else None,
    )

    try:
        result = runtime.generate(request, cancel)
    except LlmUnavailableError as exc:
        return record("unavailable", str(exc), prompt_text=prompt_text)
    except LlmTimeoutError as exc:
        return record("timeout", str(exc), prompt_text=prompt_text, latency=budget * 1000.0)
    except LlmCancelledError as exc:
        return record("cancelled", str(exc), prompt_text=prompt_text)
    except (LlmError, OSError, ValueError) as exc:
        return record("runtime_error", f"{type(exc).__name__}: {exc}", prompt_text=prompt_text)

    if result.truncated:
        return record(
            "truncated",
            f"resposta cortada em {max_tokens} tokens; descartada",
            prompt_text=prompt_text,
            output=result.text,
            result=result,
        )
    if not result.text.strip():
        return record(
            "empty", "modelo respondeu vazio", prompt_text=prompt_text, result=result
        )

    try:
        parsed = extract_json_object(result.text)
    except SchemaViolation as exc:
        return record(
            "not_json", str(exc), prompt_text=prompt_text, output=result.text, result=result
        )

    try:
        payload = validate_schema(parsed, schema)
    except SchemaViolation as exc:
        return record(
            "schema_violation",
            str(exc),
            prompt_text=prompt_text,
            output=result.text,
            result=result,
        )

    if post_validate is not None:
        if error := post_validate(payload):
            return record(
                "domain_violation",
                error,
                prompt_text=prompt_text,
                output=result.text,
                result=result,
            )

    trail.write(
        AuditRecord(
            timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
            task=task,
            prompt_id=template.id,
            prompt_version=template.version,
            prompt_sha256=template.sha256,
            model=result.model,
            decision="accepted",
            detail="",
            latency_ms=result.latency_ms,
            prompt_text=prompt_text,
            system_text=template.system,
            output_text=result.text,
            image_digests=digests,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            truncated=False,
        )
    )
    return GuardedOutcome(
        payload=payload,
        decision="accepted",
        latency_ms=result.latency_ms,
        raw_text=result.text,
    )
