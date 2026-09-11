"""Text OCR for Caïssa Studio — SPEC §7.

The public surface of front F5.  Importing this module is cheap: no engine is
constructed, no external binary is probed, and PyMuPDF, PIL, PaddleOCR and
Surya are not imported until an engine that needs them is actually built.

Typical use::

    from caissa.ocr import (Arbiter, RegionTask, default_registry,
                            default_pipeline, PreprocessContext)

    pipeline = default_pipeline()
    page = pipeline.run(raster, PreprocessContext(dpi=300)).image
    arbiter = Arbiter(default_registry().available(lang="por"))
    outcome = arbiter.run(RegionTask(image=page, lang="por"))
    print(outcome.result.text)
    print(outcome.explain_pt())
"""

from .arbiter import (
    Arbiter,
    ArbiterConfig,
    ArbitrationOutcome,
    EngineScore,
    EscalationDecision,
    RegionTask,
    arbitrate,
)
from .engines.base import (
    EngineCapabilities,
    EngineLevel,
    OcrEngine,
    OcrEngineBase,
    OcrError,
)
from .notation import (
    CIPHER_SLOT,
    CipherReport,
    CipherSymbol,
    candidate_locales,
    decode_cipher,
    infer_cipher,
)
from .page import (
    PageConfig,
    PageOutcome,
    PageRecognizer,
    PageTask,
    RegionOutcome,
    recognize_page,
)
from .engines.registry import (
    EngineInfo,
    EngineRegistry,
    available_engines,
    build_default_registry,
    default_registry,
    describe_engines,
)
from .preprocess import (
    Binarize,
    BleedThroughReduction,
    Deskew,
    Despeckle,
    Dewarp,
    PreprocessContext,
    PreprocessOutcome,
    PreprocessPipeline,
    ShadowRemoval,
    StepReport,
    Upscale,
    default_pipeline,
)
from .lexicon import (
    is_chess_notation,
    is_mangled_move,
    is_move_token,
    mangled_move_ratio,
)
from .quality import (
    PageQuality,
    QualityThresholds,
    RegionQuality,
    Severity,
    assess_page,
    assess_result,
    character_error_rate,
    estimate_cer,
)
from .types import (
    BBox,
    OcrChar,
    OcrLine,
    OcrResult,
    OcrWord,
    RegionKind,
    TextRegion,
)

__all__ = [
    "Arbiter",
    "ArbiterConfig",
    "ArbitrationOutcome",
    "BBox",
    "Binarize",
    "BleedThroughReduction",
    "CIPHER_SLOT",
    "CipherReport",
    "CipherSymbol",
    "Deskew",
    "Despeckle",
    "Dewarp",
    "EngineCapabilities",
    "EngineInfo",
    "EngineLevel",
    "EngineRegistry",
    "EngineScore",
    "EscalationDecision",
    "OcrChar",
    "OcrEngine",
    "OcrEngineBase",
    "OcrError",
    "OcrLine",
    "OcrResult",
    "OcrWord",
    "PageConfig",
    "PageOutcome",
    "PageQuality",
    "PageRecognizer",
    "PageTask",
    "PreprocessContext",
    "PreprocessOutcome",
    "PreprocessPipeline",
    "QualityThresholds",
    "RegionKind",
    "RegionOutcome",
    "RegionQuality",
    "RegionTask",
    "Severity",
    "ShadowRemoval",
    "StepReport",
    "TextRegion",
    "Upscale",
    "arbitrate",
    "assess_page",
    "assess_result",
    "available_engines",
    "build_default_registry",
    "candidate_locales",
    "character_error_rate",
    "decode_cipher",
    "default_pipeline",
    "default_registry",
    "describe_engines",
    "estimate_cer",
    "infer_cipher",
    "is_chess_notation",
    "is_mangled_move",
    "is_move_token",
    "mangled_move_ratio",
    "recognize_page",
]
