"""Optional local LLM (front F11, ADR-0005).

The whole subsystem is optional and every entry point degrades. If Ollama is not
running, if the model was never pulled, if the call times out, or if the reply
does not validate, each task returns ``None`` or a zero-confidence result and
the application carries on exactly as it would without an LLM. That is not a
courtesy; it is the acceptance criterion for this front.

What it is *for* (SPEC 6.5, 7.1 level 4):

* :func:`~caissa.llm.tasks.verify_diagram` -- second opinion on low-confidence
  diagrams. It can lower a confidence or raise a flag; it can never overwrite a
  FEN or raise a confidence.
* :func:`~caissa.llm.tasks.extract_stipulation` -- "Mate em 2", "Weiss zieht und
  gewinnt", diagram numbers, in the seven languages of the corpus.
* :func:`~caissa.llm.tasks.repair_ocr_region` -- last resort for regions the OCR
  cascade rejected. Measured in F11 cycle 3 and not wired: it invents more
  moves than it fixes on the scans where it would be called.
* :func:`~caissa.llm.tasks.caption_for_diagram` -- generated captions.
* :func:`~caissa.llm.tasks.translate_notation_prose` -- prose only; moves are
  masked and restored byte-for-byte.

What it is emphatically *not* for: producing positions. Recognition accuracy
comes from the vision pipeline in SPEC section 6, which is more accurate and
orders of magnitude faster at this task than a general VLM.
"""

from __future__ import annotations

from caissa.llm.guardrails import (
    AuditLog,
    AuditRecord,
    ConfidenceDecision,
    ConfidencePolicy,
    GuardedOutcome,
    apply_verdict,
    audit_log,
    validate_fen,
)
from caissa.llm.pipeline import (
    CaptionEnrichment,
    enrich_contexts,
    stipulation_for_context,
    stipulations_for_pdf_page,
)
from caissa.llm.prompts import PromptTemplate, list_prompts, load_prompt
from caissa.llm.residency import register_llm, unregister_llm
from caissa.llm.runtime import (
    CancellationToken,
    LlmRuntime,
    LlmUnavailableError,
    NullRuntime,
    OllamaRuntime,
    RuntimeInfo,
    get_runtime,
    reset_runtime,
)
from caissa.llm.tasks import (
    Stipulation,
    VerificationResult,
    caption_for_diagram,
    extract_stipulation,
    repair_ocr_region,
    translate_notation_prose,
    verify_diagram,
)

__all__ = [
    "AuditLog",
    "AuditRecord",
    "CancellationToken",
    "CaptionEnrichment",
    "ConfidenceDecision",
    "ConfidencePolicy",
    "GuardedOutcome",
    "LlmRuntime",
    "LlmUnavailableError",
    "NullRuntime",
    "OllamaRuntime",
    "PromptTemplate",
    "RuntimeInfo",
    "Stipulation",
    "VerificationResult",
    "apply_verdict",
    "audit_log",
    "caption_for_diagram",
    "enrich_contexts",
    "extract_stipulation",
    "get_runtime",
    "is_available",
    "list_prompts",
    "load_prompt",
    "register_llm",
    "repair_ocr_region",
    "reset_runtime",
    "stipulation_for_context",
    "stipulations_for_pdf_page",
    "translate_notation_prose",
    "unregister_llm",
    "validate_fen",
    "verify_diagram",
]


def is_available() -> bool:
    """Whether a local model can serve right now. Never raises."""
    try:
        return get_runtime().is_available()
    except Exception:  # noqa: BLE001 - the point of this function is to be safe
        return False
