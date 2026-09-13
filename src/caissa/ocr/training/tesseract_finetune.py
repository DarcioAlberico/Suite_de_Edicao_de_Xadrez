"""Fine-tune a Tesseract 5 LSTM model on labelled lines.

The steps are the ones ``tesstrain`` runs, done here directly so that a
failure names the step and the file, not a Makefile rule:

1. copy the base ``.traineddata`` into the work directory and unpack it
   (``combine_tessdata -u``): the ``.lstm`` to continue from and the
   ``.lstm-unicharset`` that says which characters the model can emit;
2. check every ground-truth line against that unicharset — a character the
   base cannot encode (a figurine, ``♖``) **extends the alphabet**: the
   characters of the truth are extracted (``unicharset_extractor``), merged
   into the base's (``merge_unicharsets``) and sealed into a starter
   ``.traineddata`` (``combine_lang_model``) that training continues into
   with ``--old_traineddata``, the way tesstrain adds characters to a
   model.  With ``extend_charset=False`` such lines are reported and left out;
3. turn each line image into an ``.lstmf`` (``tesseract … lstm.train``);
4. split by the partition the ground-truth index carries: ``dev`` trains,
   ``calib`` evaluates (a hashed tenth of ``dev`` when there is no
   ``calib``);
5. ``lstmtraining --continue_from``, streaming progress;
6. ``lstmtraining --stop_training`` to seal the checkpoint into a
   ``.traineddata``;
7. ``lstmeval`` on the evaluation list, base model and new model alike;
8. copy the other installed languages next to the result, so the output
   directory works as ``--tessdata-dir`` on its own, and write the ledger,
   the report and the log.

**The base must be a float model** (``tessdata_best``).  The Windows
installer ships the integer ``tessdata_fast`` models, which recognise
faster and cannot continue training; :func:`preflight` says which one it
found, and the trainer stops with that sentence rather than a stack trace.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ocr.engines.tesseract import find_tesseract
from caissa.ocr.engines.weights import WeightArtifact, WeightsLedger, sha256_of

__all__ = [
    "FineTuneConfig",
    "FineTuneReport",
    "TesseractFineTuner",
    "TrainingTools",
    "TrainingToolsError",
    "download_base_model",
    "find_training_tools",
    "preflight",
    "read_unicharset",
    "unknown_characters",
]

LogFn = Callable[[str], None]
ProgressFn = Callable[[dict[str, Any]], None]
#: ``(command, on_line, timeout_s) -> return code``; replaceable so the
#: pipeline is testable without the tools.
Runner = Callable[[Sequence[str], LogFn, float | None], int]

#: Languages copied next to the trained model when installed, so the output
#: directory serves ``por+eng`` and friends as ``--tessdata-dir`` by itself.
COPY_LANGS = ("eng", "por", "deu", "spa", "rus", "fra", "ita", "nld", "osd")

TESSDATA_BEST_URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main/{lang}.traineddata"
#: Below this the ``.lstm`` of a Latin-script model is almost surely the
#: integer (``tessdata_fast``) network — a hint; the tool's refusal is the verdict.
INTEGER_LSTM_MAX_BYTES = 2_500_000

#: Tesseract's own ``configs/lstm.train``, for a tessdata directory that has
#: no ``configs`` folder (some Linux packages split it out).
LSTM_TRAIN_CONFIG = """file_type                   .bl
textord_fast_pitch_test	T
tessedit_zero_rejection T
tessedit_minimal_rejection F
tessedit_write_rep_codes F
edges_children_fix F
edges_childarea 0.65
edges_boxarea 0.9
tessedit_train_line_recognizer T
textord_no_rejects T
tessedit_init_config_only T
"""


class TrainingToolsError(RuntimeError):
    """Raised with a pt-BR sentence naming what is missing."""


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TrainingTools:
    tesseract: str
    lstmtraining: str
    combine_tessdata: str
    lstmeval: str
    tessdata_dir: str
    #: The three tools that extend an alphabet; empty when not installed,
    #: in which case a new character is a reported exclusion, not a failure.
    unicharset_extractor: str = ""
    merge_unicharsets: str = ""
    combine_lang_model: str = ""

    @property
    def can_extend_charset(self) -> bool:
        return bool(
            self.unicharset_extractor and self.merge_unicharsets and self.combine_lang_model
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "tesseract": self.tesseract,
            "unicharset_extractor": self.unicharset_extractor,
            "merge_unicharsets": self.merge_unicharsets,
            "combine_lang_model": self.combine_lang_model,
            "lstmtraining": self.lstmtraining,
            "combine_tessdata": self.combine_tessdata,
            "lstmeval": self.lstmeval,
            "tessdata_dir": self.tessdata_dir,
        }


def _sibling(binary: str, name: str) -> str | None:
    exe = f"{name}.exe" if os.name == "nt" else name
    candidate = Path(binary).parent / exe
    if candidate.is_file():
        return str(candidate)
    return shutil.which(name)


def find_training_tools(
    binary: str | None = None, tessdata_dir: str | None = None
) -> TrainingTools:
    """Locate Tesseract and its training tools next to it, or on PATH."""
    tesseract = find_tesseract(binary)
    if tesseract is None:
        raise TrainingToolsError(
            "Tesseract não foi encontrado. Instale-o "
            "(https://github.com/UB-Mannheim/tesseract/wiki) ou informe o caminho do executável."
        )
    found: dict[str, str] = {}
    missing: list[str] = []
    for name in ("lstmtraining", "combine_tessdata", "lstmeval"):
        path = _sibling(tesseract, name)
        if path is None:
            missing.append(name)
        else:
            found[name] = path
    if missing:
        raise TrainingToolsError(
            "Ferramentas de treino do Tesseract ausentes: "
            + ", ".join(missing)
            + '. No instalador do Windows, marque "Training tools"; em Linux, instale o pacote '
            "tesseract-ocr training tools (ex.: libtesseract-dev / tesseract-ocr-training)."
        )
    if tessdata_dir is None:
        env = os.environ.get("TESSDATA_PREFIX")
        candidates = [
            env,
            str(Path(tesseract).parent / "tessdata"),
            "/usr/share/tesseract-ocr/5/tessdata",
            "/usr/share/tessdata",
            "/usr/local/share/tessdata",
            "/opt/homebrew/share/tessdata",
        ]
        tessdata_dir = next((c for c in candidates if c and Path(c).is_dir()), "")
    optional = {
        name: _sibling(tesseract, name) or ""
        for name in ("unicharset_extractor", "merge_unicharsets", "combine_lang_model")
    }
    return TrainingTools(
        tesseract=tesseract,
        lstmtraining=found["lstmtraining"],
        combine_tessdata=found["combine_tessdata"],
        lstmeval=found["lstmeval"],
        tessdata_dir=tessdata_dir or "",
        **optional,
    )


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run_streaming_with_timeout(cmd: Sequence[str], on_line: LogFn, timeout_s: float | None) -> int:
    return run_streaming(cmd, on_line, timeout_s=timeout_s)


def run_streaming(
    cmd: Sequence[str],
    on_line: LogFn,
    *,
    timeout_s: float | None = None,
    on_start: Callable[[subprocess.Popen[str]], None] | None = None,
) -> int:
    """Run ``cmd`` and hand every output line to ``on_line`` as it appears.

    ``on_start`` receives the process, so a caller can kill it on cancel.
    """
    proc = subprocess.Popen(  # noqa: S603 - the command is built from known tool paths
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
    )
    if on_start is not None:
        on_start(proc)
    started = time.monotonic()
    if proc.stdout is None:  # cannot happen with PIPE; keeps the type checker honest
        return proc.wait()
    try:
        for line in proc.stdout:
            on_line(line.rstrip("\r\n"))
            if timeout_s is not None and time.monotonic() - started > timeout_s:
                proc.kill()
                on_line(f"[tempo esgotado após {timeout_s:.0f} s; processo encerrado]")
                break
    finally:
        proc.stdout.close()
    return proc.wait()


# --------------------------------------------------------------------------- #
# Unicharset
# --------------------------------------------------------------------------- #


def read_unicharset(path: Path | str) -> set[str]:
    """The characters a model can emit, from its ``.lstm-unicharset``.

    The file is one unichar per line after a count; the first token is the
    unichar itself, and a line that starts with a space *is* the space.
    ``NULL``, ``Joined`` and ``|Broken|0|1`` are bookkeeping, not text.
    """
    chars: set[str] = set()
    lines = Path(path).read_text("utf-8").splitlines()
    for raw in lines[1:]:
        if not raw:
            continue
        token = raw.split(" ", 1)[0]
        if token == "":
            chars.add(" ")
            continue
        if token in ("NULL", "Joined", "|Broken|0|1"):
            continue
        chars.add(token)
    return chars


def unknown_characters(text: str, charset: set[str]) -> set[str]:
    """Characters of ``text`` the model cannot encode.

    Tesseract encodes NFC text and treats a space as a separator, so both are normalised.
    """
    return {c for c in unicodedata.normalize("NFC", text) if c != " " and c not in charset}


# --------------------------------------------------------------------------- #
# Configuration and report
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class FineTuneConfig:
    base_lang: str = "por"
    #: A float (``tessdata_best``) model to start from.  ``None`` looks for
    #: ``<base_lang>.traineddata`` in the tools' tessdata directory — which,
    #: on a stock Windows install, is the integer model and will be refused.
    base_model: Path | None = None
    model_name: str = ""
    max_iterations: int = 2000
    #: Percent; ``lstmtraining`` stops early when the training error is below it.
    target_error_rate: float = 0.01
    learning_rate: float = 0.0001
    #: Held out of ``dev`` for evaluation when the index has no ``calib`` lines.
    eval_share: float = 0.1
    #: Characters the base cannot encode extend its alphabet (figurines);
    #: off, lines carrying them are excluded and listed.
    extend_charset: bool = True
    workers: int = max(1, min(4, (os.cpu_count() or 2) - 1))
    copy_langs: tuple[str, ...] = COPY_LANGS
    train_timeout_s: float = 6 * 3600.0
    step_timeout_s: float = 600.0

    @property
    def name(self) -> str:
        return self.model_name or f"caissa_{self.base_lang}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_lang": self.base_lang,
            "base_model": str(self.base_model) if self.base_model else None,
            "model_name": self.name,
            "max_iterations": self.max_iterations,
            "target_error_rate": self.target_error_rate,
            "learning_rate": self.learning_rate,
            "eval_share": self.eval_share,
            "workers": self.workers,
            "extend_charset": self.extend_charset,
        }


@dataclass(slots=True)
class FineTuneReport:
    model_name: str
    out_dir: Path
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    base_model: str = ""
    base_sha256: str = ""
    model_path: str = ""
    model_sha256: str = ""
    lines_total: int = 0
    lines_train: int = 0
    lines_eval: int = 0
    lines_unencodable: int = 0
    unknown_chars: dict[str, int] = field(default_factory=dict)
    #: True when the alphabet was extended with ``unknown_chars``.
    charset_extended: bool = False
    charset_size: int = 0
    lstmf_failed: int = 0
    iterations: int = 0
    best_train_error: float | None = None
    cer_before: float | None = None
    wer_before: float | None = None
    cer_after: float | None = None
    wer_after: float | None = None
    tools: dict[str, str] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    copied_langs: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | trained | failed
    failure: str = ""
    log_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        data["out_dir"] = str(self.out_dir)
        return data

    def markdown(self) -> str:
        def pct(value: float | None) -> str:
            return "—" if value is None else f"{value:.2f} %"

        rows = [
            f"# Ajuste fino — {self.model_name}",
            "",
            f"- Estado: **{self.status}**" + (f" — {self.failure}" if self.failure else ""),
            f"- Início: {self.started_at} · duração: {self.duration_s:.0f} s",
            f"- Base: `{self.base_model}` (sha256 {self.base_sha256[:16]}…)",
            f"- Resultado: `{self.model_path}` (sha256 {self.model_sha256[:16]}…)"
            if self.model_path
            else "- Resultado: nenhum",
            f"- Linhas: {self.lines_total} rotuladas · {self.lines_train} treino · "
            f"{self.lines_eval} avaliação · {self.lines_unencodable} fora do unicharset · "
            f"{self.lstmf_failed} falhas de lstmf",
            f"- Iterações: {self.iterations} · melhor erro de treino: {pct(self.best_train_error)}",
            "",
            "| | CER | WER |",
            "|---|---:|---:|",
            f"| base | {pct(self.cer_before)} | {pct(self.wer_before)} |",
            f"| ajustado | {pct(self.cer_after)} | {pct(self.wer_after)} |",
        ]
        if self.unknown_chars and self.charset_extended:
            rows += [
                "",
                f"Caracteres acrescentados ao alfabeto (agora {self.charset_size}): "
                + ", ".join(
                    f"`{c}`×{n}"
                    for c, n in sorted(self.unknown_chars.items(), key=lambda kv: -kv[1])
                ),
            ]
        elif self.unknown_chars:
            rows += [
                "",
                "Caracteres fora do unicharset da base (linhas excluídas): "
                + ", ".join(
                    f"`{c}`×{n}"
                    for c, n in sorted(self.unknown_chars.items(), key=lambda kv: -kv[1])
                ),
            ]
        if self.versions:
            rows += ["", "Versões: " + ", ".join(f"{k} {v}" for k, v in self.versions.items())]
        return "\n".join(rows) + "\n"


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #


def _index_rows(gt_dir: Path) -> list[dict[str, Any]]:
    index = gt_dir / "index.jsonl"
    rows: list[dict[str, Any]] = []
    if index.is_file():
        with index.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
    else:
        for gt in sorted(gt_dir.glob("*.gt.txt")):
            name = gt.name[: -len(".gt.txt")]
            rows.append({"name": name, "partition": "dev"})
    return [
        r
        for r in rows
        if (gt_dir / f"{r['name']}.gt.txt").is_file() and (gt_dir / f"{r['name']}.png").is_file()
    ]


def _looks_integer(lstm_path: Path) -> bool:
    """Whether the ``.lstm`` is small enough to be an integer model.

    Float LSTMs of the Latin models are several MB; the integer ones a
    quarter of that.  A hint only — the tool's own refusal is the verdict.
    """
    try:
        return lstm_path.stat().st_size < INTEGER_LSTM_MAX_BYTES
    except OSError:
        return False


def preflight(
    gt_dir: Path | str, config: FineTuneConfig, tools: TrainingTools | None = None
) -> dict[str, Any]:
    """What a run would do, without running anything but the unpacking.

    Returns counts per partition, the characters the base cannot encode,
    the base model path and whether it looks trainable.
    """
    gt_dir = Path(gt_dir)
    tools = tools or find_training_tools()
    rows = _index_rows(gt_dir)
    base = config.base_model or Path(tools.tessdata_dir) / f"{config.base_lang}.traineddata"
    out: dict[str, Any] = {
        "lines": len(rows),
        "by_partition": {},
        "base_model": str(base),
        "base_exists": base.is_file(),
        "unknown_chars": {},
        "tools": tools.as_dict(),
    }
    for row in rows:
        part = str(row.get("partition", "dev"))
        out["by_partition"][part] = out["by_partition"].get(part, 0) + 1
    if not base.is_file():
        out["problem"] = (
            f"modelo base não encontrado: {base}. Informe um modelo float "
            f"(tessdata_best) com --base-model ou baixe "
            f"{TESSDATA_BEST_URL.format(lang=config.base_lang)}."
        )
        return out
    import tempfile

    with tempfile.TemporaryDirectory(prefix="caissa_preflight_") as tmp:
        work = Path(tmp)
        shutil.copy2(base, work / base.name)
        code = run_streaming(
            [
                tools.combine_tessdata,
                "-u",
                str(work / base.name),
                str(work / f"{config.base_lang}."),
            ],
            lambda _: None,
            timeout_s=config.step_timeout_s,
        )
        unicharset = work / f"{config.base_lang}.lstm-unicharset"
        lstm = work / f"{config.base_lang}.lstm"
        if code != 0 or not unicharset.is_file():
            out["problem"] = (
                f"combine_tessdata não conseguiu desempacotar {base.name} (código {code})."
            )
            return out
        out["looks_integer"] = _looks_integer(lstm)
        charset = read_unicharset(unicharset)
        counts: dict[str, int] = {}
        for row in rows:
            text = (gt_dir / f"{row['name']}.gt.txt").read_text("utf-8").strip("\n")
            for ch in unknown_characters(text, charset):
                counts[ch] = counts.get(ch, 0) + 1
        out["unknown_chars"] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        out["charset_size"] = len(charset)
        out["can_extend_charset"] = tools.can_extend_charset
        if counts and config.extend_charset and tools.can_extend_charset:
            out["note"] = (
                f"{len(counts)} caractere(s) novo(s) entram no alfabeto do modelo "
                f"(unicharset estendido): {' '.join(counts)}"
            )
        elif counts:
            out["note"] = (
                f"{len(counts)} caractere(s) fora do unicharset da base; as linhas "
                f"com eles serão excluídas (instale as ferramentas de treino ou "
                f"use --extend-charset)."
            )
    if out.get("looks_integer"):
        out["warning"] = (
            f"{base.name} parece um modelo inteiro (tessdata_fast): o ajuste fino "
            f"exige o modelo float de tessdata_best. Baixe "
            f"{TESSDATA_BEST_URL.format(lang=config.base_lang)} e passe-o em --base-model."
        )
    return out


# --------------------------------------------------------------------------- #
# The trainer
# --------------------------------------------------------------------------- #

#: Tesseract 5.3 prints ``char train=``; 5.5 prints ``BCER train=``.
_PROGRESS = re.compile(
    r"At iteration (\d+)/(\d+)/(\d+), mean rms=([\d.]+)%, delta=([\d.]+)%, "
    r"(?:char|BCER) train=([\d.]+)%, (?:word|BWER) train=([\d.]+)%"
)
_BEST = re.compile(r"New best BCER = ([\d.]+)")
_FINISHED = re.compile(r"minimal training error rate \(BCER\) = ([\d.]+)")
_EVAL = re.compile(r"Char error rate=([\d.]+), Word error rate=([\d.]+)")
_EVAL_BCER = re.compile(r"BCER eval=([\d.]+), BWER eval=([\d.]+)")
_PUNCT_RUN = re.compile(r"[.,;:!?()\[\]\"'+#=/-]+")
_EVAL_ITER = re.compile(r"Eval Char error rate=([\d.]+), Word error rate=([\d.]+)")


class TesseractFineTuner:
    """Runs the pipeline of the module docstring over one ground-truth directory."""

    def __init__(
        self,
        gt_dir: Path | str,
        out_dir: Path | str,
        config: FineTuneConfig | None = None,
        *,
        tools: TrainingTools | None = None,
        log: LogFn | None = None,
        progress: ProgressFn | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.gt_dir = Path(gt_dir)
        self.out_dir = Path(out_dir)
        self.config = config or FineTuneConfig()
        self.tools = tools or find_training_tools()
        self._log_fn = log or (lambda _line: None)
        self._progress = progress or (lambda _info: None)
        self._runner: Runner = runner or self._stream
        self._current: subprocess.Popen[str] | None = None
        self.work = self.out_dir / "work"
        self.report = FineTuneReport(
            model_name=self.config.name,
            out_dir=self.out_dir,
            tools=self.tools.as_dict(),
            config=self.config.as_dict(),
        )
        self._log_file: Any = None
        self.cancelled = False

    # -- logging ----------------------------------------------------------- #

    def log(self, line: str) -> None:
        stamp = datetime.now(UTC).strftime("%H:%M:%S")
        text = f"[{stamp}] {line}"
        if self._log_file is not None:
            self._log_file.write(text + "\n")
            self._log_file.flush()
        self._log_fn(text)

    def cancel(self) -> None:
        """Stop: no further step starts, and the tool running now is killed."""
        self.cancelled = True
        proc = self._current
        if proc is not None and proc.poll() is None:
            proc.kill()

    def _stream(self, cmd: Sequence[str], on_line: LogFn, timeout_s: float | None) -> int:
        def remember(proc: subprocess.Popen[str]) -> None:
            self._current = proc

        try:
            return run_streaming(cmd, on_line, timeout_s=timeout_s, on_start=remember)
        finally:
            self._current = None

    # -- steps ------------------------------------------------------------- #

    def _base_path(self) -> Path:
        cfg = self.config
        return cfg.base_model or Path(self.tools.tessdata_dir) / f"{cfg.base_lang}.traineddata"

    def _run(
        self,
        cmd: Sequence[str],
        *,
        capture: list[str] | None = None,
        timeout_s: float | None = None,
    ) -> int:
        self.log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

        def on_line(line: str) -> None:
            if capture is not None:
                capture.append(line)
            self.log(line)
            self._watch(line)

        return self._runner(cmd, on_line, timeout_s or self.config.step_timeout_s)

    def _watch(self, line: str) -> None:
        match = _PROGRESS.search(line)
        if match:
            self.report.iterations = int(match.group(1))
            self._progress(
                {
                    "iteration": int(match.group(1)),
                    "max": self.config.max_iterations,
                    "char_train": float(match.group(6)),
                    "word_train": float(match.group(7)),
                }
            )
        best = _BEST.search(line) or _FINISHED.search(line)
        if best:
            self.report.best_train_error = float(best.group(1))

    def prepare(self) -> tuple[Path, Path, Path]:
        """Copy and unpack the base.  Returns (traineddata, lstm, unicharset)."""
        base = self._base_path()
        if not base.is_file():
            raise TrainingToolsError(
                f"Modelo base não encontrado: {base}. Informe um modelo float (tessdata_best) "
                f"em --base-model; o download é "
                f"{TESSDATA_BEST_URL.format(lang=self.config.base_lang)}."
            )
        self.work.mkdir(parents=True, exist_ok=True)
        copied = self.work / f"{self.config.base_lang}.traineddata"
        shutil.copy2(base, copied)
        # ``--tessdata-dir`` also decides where ``lstm.train`` (a config
        # file under ``configs/``) is looked up, so the work directory needs
        # a copy — otherwise every line fails with "Can't open lstm.train".
        configs = Path(self.tools.tessdata_dir) / "configs"
        if configs.is_dir():
            shutil.copytree(configs, self.work / "configs", dirs_exist_ok=True)
        else:
            (self.work / "configs").mkdir(exist_ok=True)
            (self.work / "configs" / "lstm.train").write_text(LSTM_TRAIN_CONFIG, encoding="utf-8")
        self.report.base_model = str(base)
        self.report.base_sha256 = sha256_of(base)
        code = self._run(
            [
                self.tools.combine_tessdata,
                "-u",
                str(copied),
                str(self.work / f"{self.config.base_lang}."),
            ]
        )
        lstm = self.work / f"{self.config.base_lang}.lstm"
        unicharset = self.work / f"{self.config.base_lang}.lstm-unicharset"
        if code != 0 or not lstm.is_file() or not unicharset.is_file():
            raise RuntimeError(f"combine_tessdata -u falhou (código {code}) em {copied}")
        if _looks_integer(lstm):
            self.log(
                f"aviso: {base.name} parece um modelo inteiro (tessdata_fast); "
                f"o lstmtraining vai recusá-lo se for."
            )
        return copied, lstm, unicharset

    def select_lines(self, unicharset: Path) -> tuple[list[str], list[str]]:
        """Names to train on and to evaluate on, after the unicharset check."""
        rows = _index_rows(self.gt_dir)
        self.report.lines_total = len(rows)
        charset = read_unicharset(unicharset)
        counts: dict[str, int] = {}
        keep: list[dict[str, Any]] = []
        extend = self.config.extend_charset and self.tools.can_extend_charset
        for row in rows:
            text = (self.gt_dir / f"{row['name']}.gt.txt").read_text("utf-8").strip("\n")
            unknown = unknown_characters(text, charset)
            if unknown:
                for ch in unknown:
                    counts[ch] = counts.get(ch, 0) + 1
                if not extend:
                    self.report.lines_unencodable += 1
                    continue
            keep.append(row)
        self.report.unknown_chars = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        if counts and self.config.extend_charset and not self.tools.can_extend_charset:
            self.log(
                "aviso: unicharset_extractor/merge_unicharsets/combine_lang_model não instalados; "
                "as linhas com caracteres novos foram excluídas."
            )
        train = [r["name"] for r in keep if str(r.get("partition", "dev")) == "dev"]
        evaluate = [r["name"] for r in keep if str(r.get("partition", "dev")) == "calib"]
        if not evaluate and train:
            share = max(0.0, min(0.5, self.config.eval_share))
            held = [
                n
                for n in train
                if int(hashlib.sha256(n.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < share
            ]
            evaluate = held or train[-1:]
            train = [n for n in train if n not in set(evaluate)]
        if not train:
            raise RuntimeError(
                "nenhuma linha de treino: rotule linhas da partição dev "
                "(ou verifique os caracteres fora do unicharset)."
            )
        return train, evaluate

    def make_lstmf(self, names: Sequence[str], traineddata: Path) -> list[str]:
        """``tesseract <png> <base> --psm 13 lstm.train`` per line, in parallel.

        ``lstm.train`` reads the truth from a ``.box`` file **next to the
        image** (``BoxFileName`` swaps the extension), in the one-line
        ``WordStr`` form tesstrain writes; so each line's image is copied
        into the work directory with its box and its ``.gt.txt`` beside it,
        and the ground-truth directory is never written to.
        """
        lstmf_dir = self.work / "lstmf"
        lstmf_dir.mkdir(exist_ok=True)
        tessdata = str(traineddata.parent)
        lang = self.config.base_lang

        def one(name: str) -> str | None:
            if self.cancelled:
                return None
            target = lstmf_dir / f"{name}.lstmf"
            if target.is_file():
                return str(target)
            image = lstmf_dir / f"{name}.png"
            shutil.copy2(self.gt_dir / f"{name}.png", image)
            text = (self.gt_dir / f"{name}.gt.txt").read_text("utf-8").strip("\r\n")
            (lstmf_dir / f"{name}.gt.txt").write_text(text + "\n", encoding="utf-8")
            (lstmf_dir / f"{name}.box").write_text(wordstr_box(text, image), encoding="utf-8")
            cmd = [
                self.tools.tesseract,
                str(image),
                str(lstmf_dir / name),
                "--psm",
                "13",
                "--tessdata-dir",
                tessdata,
                "-l",
                lang,
                "lstm.train",
            ]
            output: list[str] = []
            code = self._runner(cmd, output.append, self.config.step_timeout_s)
            if code != 0 or not target.is_file():
                self.log(f"lstmf falhou para {name} (código {code}): " + " | ".join(output[-3:]))
                return None
            return str(target)

        done: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, self.config.workers)) as pool:
            for n, result in enumerate(pool.map(one, names), start=1):
                if result:
                    done.append(result)
                if n % 25 == 0 or n == len(names):
                    self.log(f"lstmf: {n}/{len(names)}")
                    self._progress({"lstmf": n, "lstmf_total": len(names)})
        return done

    def extend_unicharset(self, base_unicharset: Path, names: Sequence[str]) -> Path:
        """A starter ``.traineddata`` with the base's alphabet plus the truth's.

        It is what ``lstmtraining --old_traineddata`` continues into.

        Returns the new traineddata.  ``combine_lang_model`` insists on a
        ``radical-stroke.txt`` in its script directory even for a Latin
        alphabet; an empty table satisfies it, and nothing is downloaded.
        The word list is the truth's own vocabulary (tesstrain does the same).
        """
        tools = self.tools
        work = self.work / "charset"
        work.mkdir(exist_ok=True)
        texts = [(self.gt_dir / f"{n}.gt.txt").read_text("utf-8").strip("\r\n") for n in names]
        all_gt = work / "all-gt.txt"
        all_gt.write_text("\n".join(texts) + "\n", encoding="utf-8")
        # The three lists combine_lang_model turns into DAWGs — the truth's
        # own words, numbers and punctuation runs, as tesstrain derives them.
        # It refuses a word list without a punctuation list.
        tokens = [w for t in texts for w in t.split()]
        words = sorted({w for w in tokens if any(c.isalpha() for c in w)})
        numbers = sorted({w for w in tokens if any(c.isdigit() for c in w)})
        puncs = sorted(set(_PUNCT_RUN.findall("\n".join(texts)))) or ["."]
        for name, rows in (("words", words), ("numbers", numbers), ("puncs", puncs)):
            (work / f"{name}.txt").write_bytes(("\n".join(rows) + "\n").encode("utf-8"))
        extracted = work / "gt.unicharset"
        code = self._run(
            [
                tools.unicharset_extractor,
                "--output_unicharset",
                str(extracted),
                "--norm_mode",
                "2",
                str(all_gt),
            ]
        )
        if code != 0 or not extracted.is_file():
            raise RuntimeError(f"unicharset_extractor falhou (código {code})")
        merged = work / "merged.unicharset"
        code = self._run(
            [tools.merge_unicharsets, str(base_unicharset), str(extracted), str(merged)]
        )
        if code != 0 or not merged.is_file():
            raise RuntimeError(f"merge_unicharsets falhou (código {code})")
        script_dir = work / "script"
        script_dir.mkdir(exist_ok=True)
        # Bytes, not text: a Windows ``\r\n`` here is "invalid format at line 0".
        (script_dir / "radical-stroke.txt").write_bytes(b"\n")
        starter_dir = work / "starter"
        starter_dir.mkdir(exist_ok=True)
        code = self._run(
            [
                tools.combine_lang_model,
                "--input_unicharset",
                str(merged),
                "--script_dir",
                str(script_dir),
                "--words",
                str(work / "words.txt"),
                "--numbers",
                str(work / "numbers.txt"),
                "--puncs",
                str(work / "puncs.txt"),
                "--output_dir",
                str(starter_dir),
                "--lang",
                self.config.name,
            ]
        )
        starter = starter_dir / self.config.name / f"{self.config.name}.traineddata"
        if code != 0 or not starter.is_file():
            raise RuntimeError(f"combine_lang_model falhou (código {code}); veja o log")
        self.report.charset_extended = True
        self.report.charset_size = len(read_unicharset(merged))
        self.log(
            f"alfabeto estendido: {self.report.charset_size} caracteres, "
            f"novos: {' '.join(self.report.unknown_chars)}"
        )
        return starter

    def train(
        self,
        lstm: Path,
        traineddata: Path,
        train_list: Path,
        eval_list: Path,
        *,
        old_traineddata: Path | None = None,
    ) -> Path:
        cfg = self.config
        prefix = self.work / cfg.name
        cmd = [
            self.tools.lstmtraining,
            "--continue_from",
            str(lstm),
            "--traineddata",
            str(traineddata),
            "--model_output",
            str(prefix),
            "--train_listfile",
            str(train_list),
            "--max_iterations",
            str(cfg.max_iterations),
            "--target_error_rate",
            str(cfg.target_error_rate),
            "--learning_rate",
            str(cfg.learning_rate),
            "--debug_interval",
            "0",
        ]
        if eval_list.is_file() and eval_list.read_text("utf-8").strip():
            cmd += ["--eval_listfile", str(eval_list)]
        if old_traineddata is not None:
            # The network's output layer is remapped from the old alphabet to
            # the new one; the rest of the weights continue as they were.
            cmd += ["--old_traineddata", str(old_traineddata)]
        output: list[str] = []
        code = self._run(cmd, capture=output, timeout_s=cfg.train_timeout_s)
        checkpoint = Path(f"{prefix}_checkpoint")
        if self.cancelled:
            raise RuntimeError("treino cancelado pelo revisor")
        joined = "\n".join(output)
        if "integer" in joined.lower() and "cannot continue" in joined.lower():
            raise RuntimeError(
                f"{self.report.base_model} é um modelo inteiro (tessdata_fast) e não aceita "
                f"ajuste fino. Baixe o modelo float: "
                f"{TESSDATA_BEST_URL.format(lang=cfg.base_lang)} e passe-o em --base-model."
            )
        if not checkpoint.is_file():
            raise RuntimeError(
                f"lstmtraining terminou (código {code}) sem gravar {checkpoint.name}"
            )
        if code != 0:
            self.log(f"lstmtraining devolveu código {code}, mas gravou o checkpoint; seguindo.")
        return checkpoint

    def finalize(self, checkpoint: Path, traineddata: Path) -> Path:
        model = self.out_dir / f"{self.config.name}.traineddata"
        code = self._run(
            [
                self.tools.lstmtraining,
                "--stop_training",
                "--continue_from",
                str(checkpoint),
                "--traineddata",
                str(traineddata),
                "--model_output",
                str(model),
            ]
        )
        if code != 0 or not model.is_file():
            raise RuntimeError(f"lstmtraining --stop_training falhou (código {code})")
        self.report.model_path = str(model)
        self.report.model_sha256 = sha256_of(model)
        return model

    def evaluate(self, eval_list: Path, *, base_lstm: Path, traineddata: Path, model: Path) -> None:
        if not eval_list.is_file() or not eval_list.read_text("utf-8").strip():
            self.log("sem lista de avaliação; CER antes/depois não medidos")
            return
        before: list[str] = []
        self._run(
            [
                self.tools.lstmeval,
                "--model",
                str(base_lstm),
                "--traineddata",
                str(traineddata),
                "--eval_listfile",
                str(eval_list),
            ],
            capture=before,
        )
        self.report.cer_before, self.report.wer_before = _parse_eval(before)
        after: list[str] = []
        self._run(
            [self.tools.lstmeval, "--model", str(model), "--eval_listfile", str(eval_list)],
            capture=after,
        )
        self.report.cer_after, self.report.wer_after = _parse_eval(after)

    def copy_languages(self) -> None:
        src = Path(self.tools.tessdata_dir)
        for lang in self.config.copy_langs:
            source = src / f"{lang}.traineddata"
            target = self.out_dir / source.name
            if source.is_file() and not target.is_file():
                shutil.copy2(source, target)
                self.report.copied_langs.append(lang)

    def register(self, model: Path) -> None:
        ledger_path = self.out_dir / "weights.json"
        ledger = (
            WeightsLedger.from_dict(json.loads(ledger_path.read_text("utf-8")))
            if ledger_path.is_file()
            else WeightsLedger()
        )
        artifact = WeightArtifact(
            engine="tesseract",
            name=model.name,
            source=f"ajuste fino local de {self.report.base_model}",
            license="Apache-2.0 (modelo base tessdata_best) + dados rotulados do projeto",
            commercial_use="verify",
            version=self.report.finished_at or datetime.now(UTC).isoformat(),
            sha256=self.report.model_sha256,
            size_bytes=model.stat().st_size,
            note=f"CER avaliação {self.report.cer_before} → {self.report.cer_after} %; "
            f"{self.report.lines_train} linhas de treino",
        )
        ledger.artifacts = [a for a in ledger.artifacts if a.name != artifact.name] + [artifact]
        ledger_path.write_text(
            json.dumps(ledger.as_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    def versions(self) -> None:
        for key in ("tesseract", "lstmtraining"):
            output: list[str] = []
            try:
                self._runner([getattr(self.tools, key), "--version"], output.append, 60.0)
            except Exception as exc:  # noqa: BLE001 - a version is informative, never blocking
                output = [str(exc)]
            self.report.versions[key] = (output[0] if output else "").strip()

    # -- the run ----------------------------------------------------------- #

    def run(self) -> FineTuneReport:
        started = time.monotonic()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work.mkdir(exist_ok=True)
        self.report.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.report.log_path = str(self.out_dir / "log.txt")
        self._log_file = (self.out_dir / "log.txt").open("a", encoding="utf-8")
        try:
            self.log(f"ajuste fino {self.config.name} a partir de {self.config.base_lang}")
            self.versions()
            traineddata, lstm, unicharset = self.prepare()
            train_names, eval_names = self.select_lines(unicharset)
            self.log(
                f"linhas: {len(train_names)} treino, {len(eval_names)} avaliação, "
                f"{self.report.lines_unencodable} fora do unicharset"
            )
            train_files = self.make_lstmf(train_names, traineddata)
            eval_files = self.make_lstmf(eval_names, traineddata)
            self.report.lstmf_failed = (
                len(train_names) + len(eval_names) - len(train_files) - len(eval_files)
            )
            self.report.lines_train, self.report.lines_eval = len(train_files), len(eval_files)
            if not train_files:
                raise RuntimeError("nenhum .lstmf gerado; veja o log")
            train_list = self.work / "list.train"
            eval_list = self.work / "list.eval"
            # Bytes: a Windows text write would end each path in "\r", and
            # lstmtraining then reports "Deserialize header failed" per file.
            train_list.write_bytes(("\n".join(train_files) + "\n").encode("utf-8"))
            eval_list.write_bytes(
                ("\n".join(eval_files) + ("\n" if eval_files else "")).encode("utf-8")
            )
            if self.cancelled:
                raise RuntimeError("cancelado antes do treino")
            starter: Path | None = None
            if (
                self.report.unknown_chars
                and self.config.extend_charset
                and self.tools.can_extend_charset
            ):
                starter = self.extend_unicharset(unicharset, [*train_names, *eval_names])
            checkpoint = self.train(
                lstm,
                starter or traineddata,
                train_list,
                eval_list,
                old_traineddata=traineddata if starter else None,
            )
            model = self.finalize(checkpoint, starter or traineddata)
            self.evaluate(eval_list, base_lstm=lstm, traineddata=traineddata, model=model)
            self.copy_languages()
            self.report.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
            self.register(model)
            self.report.status = "trained"
        except Exception as exc:  # noqa: BLE001 - the report carries the failure
            self.report.status = "failed"
            self.report.failure = str(exc)
            self.log(f"FALHA: {exc}")
        finally:
            self.report.duration_s = time.monotonic() - started
            self.report.finished_at = self.report.finished_at or datetime.now(UTC).isoformat(
                timespec="seconds"
            )
            (self.out_dir / "report.json").write_text(
                json.dumps(self.report.as_dict(), ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            (self.out_dir / "report.md").write_text(self.report.markdown(), encoding="utf-8")
            if self._log_file is not None:
                self._log_file.close()
                self._log_file = None
        return self.report


def download_base_model(lang: str, dest_dir: Path | str, *, log: LogFn | None = None) -> Path:
    """Fetch ``tessdata_best/<lang>.traineddata`` (Apache-2.0) into ``dest_dir``.

    Only ever called because a person asked for it — the CLI flag or the
    dialog button — and the result is hashed so the ledger can name it.
    """
    import urllib.request

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{lang}.traineddata"
    url = TESSDATA_BEST_URL.format(lang=lang)
    say = log or (lambda _line: None)
    say(f"baixando {url}")
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as handle:  # noqa: S310
        shutil.copyfileobj(response, handle)
    say(
        f"gravado {target} ({target.stat().st_size / 1e6:.1f} MB, sha256 {sha256_of(target)[:16]}…)"
    )
    return target


def wordstr_box(text: str, image: Path) -> str:
    """Tesstrain's line-level box file.

    The whole strip is one ``WordStr`` box carrying the text after ``#``,
    followed by the end-of-line tab box.
    """
    width, height = _image_size(image)
    return f"WordStr 0 0 {width} {height} 0 #{text}\n\t 0 0 {width} {height} 0\n"


def _image_size(image: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(image) as handle:
            return int(handle.width), int(handle.height)
    except Exception:  # noqa: BLE001 - a fake image in tests, or Pillow missing
        return 1000, 100


def _parse_eval(lines: Sequence[str]) -> tuple[float | None, float | None]:
    for line in reversed(lines):
        match = _EVAL_ITER.search(line) or _EVAL.search(line) or _EVAL_BCER.search(line)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None, None
