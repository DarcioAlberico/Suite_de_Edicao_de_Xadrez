"""Tesseract 5 adapter — level 1 of the cascade (SPEC §7.1).

Driven by direct ``subprocess`` calls rather than ``pytesseract``.  Three
reasons, all of which cost real debugging time in the sibling projects:

* ``pytesseract`` adds a dependency whose only job is to build the same command
  line, and it hides the exit status behind its own exception type;
* it offers no way to ask for two output formats in one invocation, so getting
  word confidence *and* character boxes means running Tesseract twice — a 2x
  cost on the hottest path in the product;
* it looks the binary up on ``PATH`` only.  On this machine Tesseract is
  installed at ``C:\\Program Files\\Tesseract-OCR`` and is **not** on ``PATH``,
  which is the default outcome of the official Windows installer.  An adapter
  that only checks ``PATH`` reports "not installed" to a user who installed it.

One invocation therefore asks for ``tsv`` and ``hocr`` together: the TSV gives
the word/line/paragraph/block skeleton with confidence, and the hOCR — with
``hocr_char_boxes=1`` — gives baselines plus one ``ocrx_cinfo`` span per
character carrying both a box and a *measured* ``x_conf``.  Both are printed
from the same internal result, so the join is exact rather than approximate.

Note that ``hocr_char_boxes`` does **not** put ``x_bboxes`` in the word's own
``title``, which is where the hOCR specification suggests looking and where an
earlier draft of this adapter looked; it emits child spans instead.  Checking
only the word title makes the feature look broken when it is working.

Measured here (Tesseract 5.5.0, 2480x3300 page, ``--psm 6``, 3 runs, best of):

===============================================  ========
configuration                                    time
===============================================  ========
``tsv hocr``                                     1.80 s
``tsv hocr makebox``                             1.82 s
``tsv hocr`` + ``lstm_choice_mode=2``            2.08 s
===============================================  ========

So character boxes are free and are on by default.  ``makebox`` is kept as a
fallback for builds that ignore ``hocr_char_boxes``; it is requested only after
a region comes back with words but no character boxes, so the normal path never
pays for it.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind
from .profiles import ProfileConfig, ProfileFiles, TesseractProfile, profile_for
from .base import (
    EngineCapabilities,
    EngineLevel,
    OcrEngineBase,
    OcrError,
    normalise_gray,
)

__all__ = ["TesseractEngine", "TesseractConfig", "find_tesseract", "PSM_BY_REGION"]


# --------------------------------------------------------------------------- #
# Binary discovery
# --------------------------------------------------------------------------- #

#: Environment variables checked before anything else, in order.
ENV_OVERRIDES = ("CAISSA_TESSERACT", "TESSERACT_CMD", "TESSERACT_PATH")

#: Locations the official Windows installer, Chocolatey, Scoop and the common
#: Linux/macOS package managers use.  Checked in order; first hit wins.
_WINDOWS_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",
    r"C:\tools\tesseract\tesseract.exe",
    r"C:\ProgramData\chocolatey\bin\tesseract.exe",
)

_POSIX_CANDIDATES = (
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
    "/snap/bin/tesseract",
)

INSTALL_HINT_PT = (
    "Tesseract OCR não foi encontrado. Instale a versão 5 e reinicie o programa.\n"
    "  • Windows: baixe o instalador em "
    "https://github.com/UB-Mannheim/tesseract/wiki e, na tela de componentes, "
    "marque os idiomas desejados (Portuguese, English, German, Russian, "
    "Spanish, French, Italian, Dutch).\n"
    "  • Se já estiver instalado fora do PATH, aponte a variável de ambiente "
    "CAISSA_TESSERACT para o executável "
    "(ex.: C:\\Program Files\\Tesseract-OCR\\tesseract.exe)."
)

#: Languages the product promises (SPEC §7 / portão F5) plus the orientation
#: model.  Anything else Tesseract has installed is still usable.
TARGET_LANGUAGES = ("por", "eng", "deu", "rus", "spa", "fra", "ita", "nld")


def _expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def find_tesseract(explicit: str | os.PathLike[str] | None = None) -> str | None:
    """Locate the Tesseract executable, or ``None``.

    Order: explicit argument, environment override, ``PATH``, then the
    well-known install directories for the platform.
    """
    if explicit:
        candidate = _expand(str(explicit))
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found

    for var in ENV_OVERRIDES:
        value = os.environ.get(var)
        if not value:
            continue
        candidate = _expand(value)
        if os.path.isfile(candidate):
            return candidate
        # Tolerate the variable pointing at the install directory.
        exe = "tesseract.exe" if os.name == "nt" else "tesseract"
        joined = os.path.join(candidate, exe)
        if os.path.isfile(joined):
            return joined

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    candidates = _WINDOWS_CANDIDATES if os.name == "nt" else _POSIX_CANDIDATES
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Page segmentation modes
# --------------------------------------------------------------------------- #

#: RegionKind -> ``--psm``.  The layout analyser has already cut the page, so
#: the automatic modes (0-3) are only used when the caller explicitly asks for
#: a whole page.
PSM_BY_REGION: dict[RegionKind, int] = {
    RegionKind.PAGE: 3,            # fully automatic, no orientation detection
    RegionKind.COLUMN: 4,          # single column, variable sizes
    RegionKind.PARAGRAPH: 6,       # single uniform block
    RegionKind.HEADING: 6,         # a heading may wrap to two lines
    RegionKind.CAPTION: 6,
    RegionKind.FOOTNOTE: 6,
    RegionKind.MOVETEXT: 6,
    RegionKind.TABLE: 6,           # Tesseract has no table mode; that is level 2
    RegionKind.HEADER: 7,          # single line
    RegionKind.FOOTER: 7,
    RegionKind.PAGE_NUMBER: 7,
    RegionKind.SINGLE_LINE: 7,
    RegionKind.SINGLE_WORD: 8,
    RegionKind.DIAGRAM_LABEL: 8,   # "a".."h", "1".."8" — one token at a time
    RegionKind.SPARSE: 11,         # sparse text, no order assumed
    RegionKind.VERTICAL: 5,
    RegionKind.UNKNOWN: 3,
}


@dataclass(slots=True)
class TesseractConfig:
    """Everything about an invocation that a caller might reasonably change.

    Defaults are chosen for determinism: OEM 1 pins the LSTM engine instead of
    letting the build's default decide, and ``dpi`` is passed explicitly
    because Tesseract's own DPI guess changes its decisions and is frequently
    wrong on cropped regions.
    """

    binary: str | None = None
    #: 1 = LSTM only.  0/2/3 exist but 3 ("default") is build-dependent.
    oem: int = 1
    dpi: int | None = 300
    timeout_s: float = 180.0
    #: ``-c key=value`` pairs appended to every call.
    extra_config: dict[str, str] = field(default_factory=dict)
    #: When false, no character boxes are requested at all.
    want_char_boxes: bool = True
    #: Ask for the ``makebox`` renderer as well.  ``None`` means "decide at
    #: runtime": off until a region comes back with words but no character
    #: boxes, then on for the rest of the session.
    box_file_fallback: bool | None = None
    #: Directory holding ``*.traineddata``; ``None`` uses Tesseract's own.
    tessdata_dir: str | None = None
    #: Sol §SOL-7: choose the prose or movetext profile by region kind and
    #: hand Tesseract the matching word and pattern files.  Off, every
    #: region gets the plain configuration.
    use_profiles: bool = True
    profiles: ProfileConfig = field(default_factory=ProfileConfig)


# --------------------------------------------------------------------------- #
# hOCR scanning
# --------------------------------------------------------------------------- #

# hOCR from Tesseract is machine generated and structurally stable, so a
# targeted scanner beats an XML parse here: no DOCTYPE handling, no namespace
# juggling, and no chance of an external-entity fetch.
_HOCR_ELEMENT = re.compile(
    r"<span\s+class=['\"]"
    r"(ocr_line|ocr_header|ocr_caption|ocr_textfloat|ocrx_word|ocrx_cinfo)['\"]"
    r"[^>]*?title=['\"]([^'\"]*)['\"][^>]*>",
    re.IGNORECASE,
)
_HOCR_WORD_TEXT = re.compile(r">([^<]*)<", re.S)
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _title_field(title: str, key: str) -> str | None:
    """Read one ``key value; key value`` field out of an hOCR ``title``."""
    for chunk in title.split(";"):
        chunk = chunk.strip()
        if chunk.startswith(key) and (len(chunk) == len(key)
                                      or chunk[len(key)].isspace()):
            return chunk[len(key):].strip()
    return None


def _title_bbox(title: str) -> BBox | None:
    raw = _title_field(title, "bbox")
    if not raw:
        return None
    nums = _NUM.findall(raw)
    if len(nums) < 4:
        return None
    x0, y0, x1, y1 = (float(n) for n in nums[:4])
    return BBox.from_edges(x0, y0, x1, y1)


def _title_baseline(title: str) -> tuple[float, float] | None:
    raw = _title_field(title, "baseline")
    if not raw:
        return None
    nums = _NUM.findall(raw)
    if len(nums) < 2:
        return None
    return float(nums[0]), float(nums[1])


#: Integer ``(x0, y0, x1, y1)`` — the join key between TSV, hOCR and box file.
BoxKey = tuple[int, int, int, int]


def _key_of(box: BBox) -> BoxKey:
    return int(round(box.x0)), int(round(box.y0)), \
        int(round(box.x1)), int(round(box.y1))


@dataclass(slots=True)
class _HocrWord:
    box: BBox
    text: str
    chars: tuple[OcrChar, ...] = ()


@dataclass(slots=True)
class _HocrScan:
    baselines: dict[BoxKey, tuple[float, float]] = field(default_factory=dict)
    words: dict[BoxKey, _HocrWord] = field(default_factory=dict)


def _scan_hocr(hocr: str) -> _HocrScan:
    """Pull baselines, word text and (when present) character info out of hOCR.

    Keys are integer bounding boxes, which makes the join with the TSV exact:
    both files print the same integers from the same internal result.

    With ``lstm_choice_mode`` enabled Tesseract nests ``ocrx_cinfo`` spans
    inside each word, one per character, carrying ``x_bboxes`` in ordinary
    top-left page coordinates plus a real ``x_conf``.  The alternative-choice
    spans share the same class but have no ``x_bboxes``, which is the
    discriminator used below.
    """
    scan = _HocrScan()
    current: _HocrWord | None = None
    current_chars: list[OcrChar] = []

    def close_word() -> None:
        nonlocal current, current_chars
        if current is not None:
            current.chars = tuple(current_chars)
            scan.words[_key_of(current.box)] = current
        current = None
        current_chars = []

    for match in _HOCR_ELEMENT.finditer(hocr):
        cls = match.group(1).lower()
        title = match.group(2)

        if cls == "ocrx_cinfo":
            raw = _title_field(title, "x_bboxes")
            if raw is None or current is None:
                continue
            nums = [float(n) for n in _NUM.findall(raw)]
            if len(nums) < 4:
                continue
            tail = hocr[match.end():match.end() + 256]
            text_match = _HOCR_WORD_TEXT.match(">" + tail)
            ch = html.unescape(text_match.group(1)) if text_match else ""
            if len(ch) != 1:
                continue
            conf_raw = _title_field(title, "x_conf")
            conf = float(_NUM.findall(conf_raw)[0]) / 100.0 if conf_raw else 0.0
            current_chars.append(OcrChar(
                text=ch,
                box=BBox.from_edges(nums[0], nums[1], nums[2], nums[3]),
                confidence=max(0.0, min(1.0, conf)),
                inherited_confidence=False,
            ))
            continue

        close_word()
        box = _title_bbox(title)
        if box is None:
            continue

        if cls != "ocrx_word":
            baseline = _title_baseline(title)
            if baseline is not None:
                scan.baselines[_key_of(box)] = baseline
            continue

        tail = hocr[match.end():match.end() + 4096]
        text_match = _HOCR_WORD_TEXT.match(">" + tail)
        text = html.unescape(text_match.group(1)).strip() if text_match else ""
        current = _HocrWord(box=box, text=text)

    close_word()
    return scan


# --------------------------------------------------------------------------- #
# Box-file parsing
# --------------------------------------------------------------------------- #


def parse_box_file(data: str, image_height: int) -> list[tuple[str, BBox]]:
    """Parse Tesseract's ``makebox`` output into top-left pixel coordinates.

    The box format is ``char left bottom right top page`` with the origin at
    the **bottom** left of the image, which is why ``image_height`` is
    required: getting this flip wrong puts every character box on the mirror
    image of the line it came from, and the error is invisible in aggregate
    statistics.
    """
    out: list[tuple[str, BBox]] = []
    for raw in data.splitlines():
        if not raw:
            continue
        parts = raw.split(" ")
        if len(parts) < 5:
            continue
        ch = parts[0]
        if not ch or ch.isspace():
            continue
        try:
            left, bottom, right, top = (int(parts[i]) for i in range(1, 5))
        except ValueError:
            continue
        if right <= left or top <= bottom:
            continue
        out.append((ch, BBox.from_edges(
            float(left), float(image_height - top),
            float(right), float(image_height - bottom),
        )))
    return out


def _assign_boxes_to_words(
    char_boxes: list[tuple[str, BBox]],
    word_boxes: dict[BoxKey, BBox],
) -> dict[BoxKey, list[tuple[str, BBox]]]:
    """Group character boxes under the word box that contains their centre.

    Containment beats index matching here because the box file has no word
    delimiters at all: it is a flat stream of symbols, and a purely positional
    walk desynchronises for good the first time Tesseract emits a symbol the
    TSV dropped (it drops pure-punctuation words at some PSMs).
    """
    grouped: dict[BoxKey, list[tuple[str, BBox]]] = {}
    if not char_boxes or not word_boxes:
        return grouped
    # Sorting by y then x lets the search stay local without an index tree;
    # pages have a few thousand symbols, so this is not a hot spot.
    items = sorted(word_boxes.items(), key=lambda kv: (kv[1].y0, kv[1].x0))
    for ch, box in char_boxes:
        cx, cy = box.cx, box.cy
        best_key: BoxKey | None = None
        best_area = float("inf")
        for key, wbox in items:
            if wbox.x0 - 1.0 <= cx <= wbox.x1 + 1.0 and \
                    wbox.y0 - 1.0 <= cy <= wbox.y1 + 1.0:
                # Prefer the tightest containing box; words never nest, but a
                # 1 px tolerance can make two adjacent boxes both match.
                if wbox.area < best_area:
                    best_key, best_area = key, wbox.area
        if best_key is not None:
            grouped.setdefault(best_key, []).append((ch, box))
    for chars in grouped.values():
        chars.sort(key=lambda item: item[1].x0)
    return grouped


# --------------------------------------------------------------------------- #
# TSV parsing
# --------------------------------------------------------------------------- #

_TSV_HEADER = ("level", "page_num", "block_num", "par_num", "line_num",
               "word_num", "left", "top", "width", "height", "conf", "text")


@dataclass(slots=True)
class _TsvRow:
    level: int
    block: int
    par: int
    line: int
    word: int
    box: BBox
    conf: float
    text: str


def _parse_tsv(data: str) -> list[_TsvRow]:
    rows: list[_TsvRow] = []
    lines = data.splitlines()
    if not lines:
        return rows
    start = 1 if lines[0].lower().startswith("level") else 0
    for raw in lines[start:]:
        if not raw.strip():
            continue
        # The text column may itself contain nothing; split with a fixed count
        # so an empty trailing field survives.
        parts = raw.split("\t")
        if len(parts) < len(_TSV_HEADER) - 1:
            continue
        if len(parts) == len(_TSV_HEADER) - 1:
            parts.append("")
        try:
            level = int(parts[0])
            block = int(parts[2])
            par = int(parts[3])
            line = int(parts[4])
            word = int(parts[5])
            left, top, width, height = (float(parts[i]) for i in range(6, 10))
            conf = float(parts[10])
        except (TypeError, ValueError):
            continue
        rows.append(_TsvRow(
            level=level, block=block, par=par, line=line, word=word,
            box=BBox(left, top, width, height),
            conf=conf,
            text=parts[11],
        ))
    return rows


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #


class TesseractEngine(OcrEngineBase):
    """Level 1: Tesseract 5 (LSTM), CPU, offline."""

    name = "tesseract"

    def __init__(self, config: TesseractConfig | None = None) -> None:
        self._profile_files = ProfileFiles((config or TesseractConfig()).profiles)
        self._forced_profile: TesseractProfile | None = None
        super().__init__()
        self.config = config or TesseractConfig()
        self._binary: str | None = None
        self._version: str | None = None
        self._version_tuple: tuple[int, ...] = ()
        #: Set once a region proves this build ignores ``hocr_char_boxes``.
        self._box_fallback_armed = False

    # -- introspection ----------------------------------------------------- #

    @property
    def binary(self) -> str | None:
        return self._binary

    @property
    def version(self) -> str | None:
        self.available()
        return self._version

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT,
            cost_per_megapixel_s=0.55,
            supports_char_boxes=True,
            supports_confidence=True,
            handles_layout=True,
            requires_pdf_page=False,
            gpu_capable=False,
        )

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        binary = find_tesseract(self.config.binary)
        if binary is None:
            return False, INSTALL_HINT_PT
        self._binary = binary

        try:
            proc = self._run([binary, "--version"], timeout=20.0)
        except OcrError as exc:
            return False, (
                f"Tesseract foi encontrado em {binary}, mas não pôde ser "
                f"executado ({exc.message}). Verifique se a instalação está "
                f"íntegra ou reinstale-a."
            )
        banner = (proc.stdout or "") + (proc.stderr or "")
        first = banner.strip().splitlines()[0] if banner.strip() else ""
        self._version = first.strip()
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", first)
        if match:
            self._version_tuple = tuple(
                int(g) for g in match.groups() if g is not None
            )
        if self._version_tuple and self._version_tuple[0] < 4:
            return False, (
                f"Tesseract {self._version} é antigo demais: o reconhecimento "
                f"por LSTM exige a versão 4 ou superior (recomendada: 5). "
                f"Atualize a instalação em {binary}."
            )
        return True, None

    def _discover_languages(self) -> set[str]:
        assert self._binary is not None
        cmd = [self._binary, "--list-langs"]
        if self.config.tessdata_dir:
            cmd += ["--tessdata-dir", self.config.tessdata_dir]
        proc = self._run(cmd, timeout=30.0)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        langs: set[str] = set()
        for line in out.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of available"):
                continue
            # Script models are listed as "script\Cyrillic" / "script/Cyrillic".
            if line.startswith("script") and len(line) > 6 and line[6] in "\\/":
                langs.add("script/" + line[7:])
                continue
            if re.fullmatch(r"[A-Za-z_]{2,}", line):
                langs.add(line)
        return langs

    def missing_target_languages(self) -> tuple[str, ...]:
        """Which of the languages the product promises are not installed."""
        have = self.languages()
        return tuple(l for l in TARGET_LANGUAGES if l not in have)

    def language_hint_pt(self) -> str | None:
        """pt-BR advice when a promised language pack is missing."""
        missing = self.missing_target_languages()
        if not missing:
            return None
        return (
            "Pacotes de idioma ausentes no Tesseract: "
            + ", ".join(missing)
            + ". Reexecute o instalador do Tesseract e marque esses idiomas em "
            "\"Additional language data\", ou copie os arquivos "
            + ", ".join(f"{m}.traineddata" for m in missing)
            + " para a pasta tessdata."
        )

    # -- subprocess -------------------------------------------------------- #

    @staticmethod
    def _creation_flags() -> int:
        # Keep a console window from flashing over the Qt UI on every page.
        if sys.platform == "win32":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return 0

    def _run(self, cmd: list[str], *, timeout: float,
             cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=cwd,
                creationflags=self._creation_flags(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError(
                self.name,
                f"O Tesseract excedeu o tempo limite de {timeout:.0f}s.",
                detail=str(exc),
            ) from exc
        except OSError as exc:
            raise OcrError(
                self.name,
                f"Não foi possível executar o Tesseract: {exc}",
                detail=str(exc),
            ) from exc

    # -- recognition ------------------------------------------------------- #

    def _build_command(self, image_path: Path, out_base: Path, *,
                       lang: str, psm: int,
                       profile: TesseractProfile | None = None) -> list[str]:
        assert self._binary is not None
        cmd = [self._binary, str(image_path), str(out_base),
               "-l", lang, "--psm", str(psm), "--oem", str(self.config.oem)]
        if self.config.tessdata_dir:
            cmd += ["--tessdata-dir", self.config.tessdata_dir]
        if self.config.dpi:
            cmd += ["--dpi", str(int(self.config.dpi))]
        if self.config.want_char_boxes:
            cmd += ["-c", "hocr_char_boxes=1"]
        params = dict(self.config.extra_config)
        if profile is not None:
            params.update(self._profile_files.parameters(profile, lang))
        for key, value in sorted(params.items()):
            cmd += ["-c", f"{key}={value}"]
        cmd += ["tsv", "hocr"]
        if self._use_box_file():
            cmd += ["makebox"]
        return cmd

    def _use_box_file(self) -> bool:
        if not self.config.want_char_boxes:
            return False
        if self.config.box_file_fallback is not None:
            return self.config.box_file_fallback
        return self._box_fallback_armed

    def recognize_with_profile(self, image: NDArray[np.uint8], *, lang: str,
                               psm_hint: RegionKind,
                               profile: TesseractProfile) -> OcrResult:
        """Recognise with an explicit profile — the strict movetext candidate
        the service adds for token fusion (Sol §SOL-7)."""
        self._forced_profile = profile
        try:
            return self.recognize(image, lang=lang, psm_hint=psm_hint)
        finally:
            self._forced_profile = None

    def _recognize(
        self,
        image: NDArray[np.uint8],
        *,
        lang: str,
        psm_hint: RegionKind,
    ) -> OcrResult:
        from PIL import Image  # local import: keeps engine import cheap

        gray = normalise_gray(image)
        psm = PSM_BY_REGION.get(psm_hint, 3)
        warnings: list[str] = []
        profile: TesseractProfile | None = None
        if self.config.use_profiles:
            profile = self._forced_profile or profile_for(psm_hint)

        known = self.languages()
        requested = [p for p in lang.split("+") if p]
        usable = [p for p in requested if p in known] if known else requested
        if known and not usable:
            fallback = "eng" if "eng" in known else sorted(known)[0]
            warnings.append(
                f"Idioma '{lang}' não está instalado no Tesseract; "
                f"usando '{fallback}'."
            )
            usable = [fallback]
        effective_lang = "+".join(usable) if usable else lang

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="caissa-ocr-") as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "region.png"
            out_base = tmp_path / "out"
            pil = Image.fromarray(gray)
            save_kwargs: dict[str, object] = {}
            if self.config.dpi:
                save_kwargs["dpi"] = (int(self.config.dpi), int(self.config.dpi))
            pil.save(image_path, format="PNG", **save_kwargs)

            cmd = self._build_command(image_path, out_base,
                                      lang=effective_lang, psm=psm, profile=profile)
            proc = self._run(cmd, timeout=self.config.timeout_s, cwd=tmp)
            if proc.returncode != 0:
                raise OcrError(
                    self.name,
                    f"O Tesseract terminou com código {proc.returncode}.",
                    detail=(proc.stderr or "").strip()[:2000],
                )

            tsv_path = out_base.with_suffix(".tsv")
            hocr_path = out_base.with_suffix(".hocr")
            if not tsv_path.is_file():
                raise OcrError(
                    self.name,
                    "O Tesseract não gerou a saída TSV esperada.",
                    detail=(proc.stderr or "").strip()[:2000],
                )
            tsv_data = tsv_path.read_text(encoding="utf-8", errors="replace")
            hocr_data = ""
            if hocr_path.is_file():
                hocr_data = hocr_path.read_text(encoding="utf-8", errors="replace")
            else:
                warnings.append(
                    "Saída hOCR ausente: as linhas de base não estarão "
                    "disponíveis nesta região."
                )
            box_data = ""
            box_path = out_base.with_suffix(".box")
            if self._use_box_file() and box_path.is_file():
                box_data = box_path.read_text(encoding="utf-8", errors="replace")

        stderr = (proc.stderr or "").strip()
        if stderr and "Estimating resolution" not in stderr:
            for line in stderr.splitlines():
                line = line.strip()
                if line and not line.startswith("Warning: Invalid resolution"):
                    warnings.append(f"Tesseract: {line}")

        lines = self._assemble(tsv_data, hocr_data, box_data,
                               image_height=int(gray.shape[0]),
                               region_kind=psm_hint)
        if not lines and not warnings:
            warnings.append("Nenhum texto reconhecido nesta região.")

        with_chars = sum(1 for w in (word for line in lines
                                     for word in line.words) if w.chars)
        total_words = sum(len(line.words) for line in lines)
        coverage = with_chars / total_words if total_words else 0.0

        # This build ignores ``hocr_char_boxes``: arm the box-file renderer so
        # every later region gets character boxes.  Only one region pays.
        if (self.config.want_char_boxes and total_words >= 3
                and coverage == 0.0 and not self._use_box_file()):
            self._box_fallback_armed = True
            warnings.append(
                "Esta build do Tesseract não fornece caixas por caractere via "
                "hOCR; o modo alternativo foi ativado para as próximas regiões."
            )

        return OcrResult(
            engine=self.name,
            lang=effective_lang,
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=tuple(warnings[:12]),
            meta={
                "psm": psm,
                "profile": str(profile) if profile is not None else "",
                "oem": self.config.oem,
                "binary": self._binary,
                "version": self._version,
                "requested_lang": lang,
                "char_box_coverage": coverage,
                "char_box_source": "makebox" if box_data else "hocr",
                "image_shape": tuple(int(v) for v in gray.shape),
            },
        )

    # -- assembly ---------------------------------------------------------- #

    @staticmethod
    def _assemble(tsv_data: str, hocr_data: str, box_data: str, *,
                  image_height: int,
                  region_kind: RegionKind) -> list[OcrLine]:
        rows = _parse_tsv(tsv_data)
        scan = _scan_hocr(hocr_data) if hocr_data else _HocrScan()

        # Line-level rows give the line box; word-level rows give the content.
        line_boxes: dict[tuple[int, int, int], BBox] = {}
        word_boxes: dict[BoxKey, BBox] = {}
        for row in rows:
            if row.level == 4:
                line_boxes[(row.block, row.par, row.line)] = row.box
            elif row.level == 5 and row.text.strip():
                word_boxes[_key_of(row.box)] = row.box

        from_box_file: dict[BoxKey, list[tuple[str, BBox]]] = {}
        if box_data:
            from_box_file = _assign_boxes_to_words(
                parse_box_file(box_data, image_height), word_boxes)

        grouped: dict[tuple[int, int, int], list[OcrWord]] = {}
        order: list[tuple[int, int, int]] = []
        for row in rows:
            if row.level != 5:
                continue
            text = row.text
            if not text or not text.strip():
                continue
            key = (row.block, row.par, row.line)
            if key not in grouped:
                grouped[key] = []
                order.append(key)

            # Tesseract reports -1 for a word it declined to score; treating
            # that as 0 is right — an unscored word is not a confident one.
            conf = max(0.0, row.conf) / 100.0
            box_key = _key_of(row.box)

            # Measured per-character confidence (hOCR + lstm_choice_mode) wins
            # over the box file, which only has geometry.
            chars: tuple[OcrChar, ...] = ()
            hocr_word = scan.words.get(box_key)
            if (hocr_word is not None and hocr_word.chars
                    and "".join(c.text for c in hocr_word.chars) == text):
                chars = hocr_word.chars
            else:
                candidates = from_box_file.get(box_key, [])
                if candidates and "".join(c for c, _ in candidates) == text:
                    chars = tuple(
                        OcrChar(text=ch, box=cbox, confidence=conf,
                                inherited_confidence=True)
                        for ch, cbox in candidates
                    )

            grouped[key].append(OcrWord(
                text=text,
                box=row.box,
                confidence=conf,
                chars=chars,
                block_index=row.block,
                paragraph_index=row.par,
                line_index=row.line,
                word_index=row.word,
            ))

        out: list[OcrLine] = []
        for key in order:
            words = grouped[key]
            if not words:
                continue
            box = line_boxes.get(key) or BBox.union_of([w.box for w in words])
            block, par, line = key
            out.append(OcrLine(
                words=tuple(words),
                box=box,
                baseline=scan.baselines.get(_key_of(box)),
                block_index=block,
                paragraph_index=par,
                line_index=line,
                kind=region_kind,
                font_size=box.h,
            ))
        return out
