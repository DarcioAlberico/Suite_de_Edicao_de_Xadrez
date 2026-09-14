"""Training an engine on what the reviewer labelled.

FineReader trains *patterns*: a glyph the engine doubted, the character the
user typed.  Tesseract 5's recogniser is a line LSTM and has no patterns
to train; its equivalent is a **fine-tune**: the base model continues
training on line images with their ground truth until its error on a
held-out set stops falling, and the result is a new ``.traineddata`` the
engine loads like any language.  :mod:`.tesseract_finetune` is that
pipeline over the ground truth :func:`caissa.ocr.labeling.export.write_ground_truth`
produces, with the rules the rest of Sol already enforces:

* lines from the **development** partition train, lines from the
  **calibration** partition evaluate, and blind lines never reach the
  ground-truth directory in the first place;
* the base model, the result, every tool's version and the error rate
  before and after are recorded (Sol §SOL-12, "guardar configuração,
  versões e hashes dos modelos");
* the trained model is registered as a weight artefact with its hash,
  so a benchmark that loads it can say which one it loaded;
* a model trained on one book is bound to that book (:mod:`.books`): the
  importer applies it to that PDF and to no other, which is what the
  measurement of ROTULAGEM.md §4c demands.
"""

from __future__ import annotations

from .books import (
    BookModel,
    BookRegistry,
    book_dir,
    book_slug,
    models_root,
    pdf_fingerprint,
    register_training,
)
from .tesseract_finetune import (
    FineTuneConfig,
    FineTuneReport,
    TesseractFineTuner,
    TrainingTools,
    TrainingToolsError,
    download_base_model,
    find_training_tools,
    preflight,
)

__all__ = [
    "BookModel",
    "BookRegistry",
    "FineTuneConfig",
    "FineTuneReport",
    "TesseractFineTuner",
    "TrainingTools",
    "TrainingToolsError",
    "book_dir",
    "book_slug",
    "download_base_model",
    "find_training_tools",
    "models_root",
    "pdf_fingerprint",
    "preflight",
    "register_training",
]
