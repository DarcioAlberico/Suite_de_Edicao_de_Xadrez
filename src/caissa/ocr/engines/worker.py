"""An engine in its own process — Sol §SOL-5 and ADR-0003.

PaddleOCR brings its own runtime and Surya brings torch; measured in F5 and
in the residency work, either can collide with the project's own torch
cu128 build when loaded into the same process, and a crash in one of them
took the whole batch with it.  So the heavier engines run in a worker: a
child interpreter that hosts one adapter and speaks a line-oriented JSON
protocol over its pipes.  The parent side, :class:`IsolatedEngine`, is an
ordinary :class:`~caissa.ocr.engines.base.OcrEngine`, so the arbiter does
not know the difference.

Protocol (one JSON object per line, request → response):

``{"op": "probe"}``
    → ``{"ok": true, "schema": 1, "engine": name, "version": …, "languages": […]}``
    or ``{"ok": false, "reason": …}``.  The parent refuses a worker whose
    ``schema`` is not the one it speaks — the explicit failure §SOL-5 asks
    for instead of an empty page.

``{"op": "recognize", "image": <path to a PNG>, "lang": …, "psm_hint": …}``
    → ``{"ok": true, "result": <OcrResult as JSON>, "usage": {...}}`` or
    ``{"ok": false, "error": …, "detail": …}``.  ``usage`` carries wall
    time, CPU time, resident memory (with :mod:`psutil` when installed) and
    peak CUDA memory (when torch is present) for the call.

``{"op": "quit"}``
    → the worker exits.

The image travels as a file, not inline: a 300 DPI page is 22 MB and a
pipe is the wrong place for it.  The parent writes it to a temporary
directory it owns and removes it after the answer.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind
from .base import EngineCapabilities, OcrEngine, OcrEngineBase, OcrError

__all__ = [
    "WORKER_SCHEMA",
    "IsolatedEngine",
    "ResourceUsage",
    "result_from_json",
    "result_to_json",
    "serve",
]

WORKER_SCHEMA = 1

#: Cascade level of each hostable adapter, for the capabilities reported
#: before (or without) a successful probe.
HOSTED_LEVELS: dict[str, int] = {"paddleocr": 2, "paddle_structure": 2, "rapidocr": 2, "surya": 3}

#: Adapters a worker may host, by engine name.
HOSTABLE: dict[str, tuple[str, str]] = {
    "paddleocr": ("caissa.ocr.engines.paddle", "PaddleOcrEngine"),
    "paddle_structure": ("caissa.ocr.engines.paddle_structure", "PaddleStructureEngine"),
    "rapidocr": ("caissa.ocr.engines.rapidocr", "RapidOcrEngine"),
    "surya": ("caissa.ocr.engines.surya", "SuryaEngine"),
}


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _box(b: BBox) -> list[float]:
    return [b.x, b.y, b.w, b.h]


def result_to_json(result: OcrResult) -> dict[str, Any]:
    return {
        "engine": result.engine,
        "lang": result.lang,
        "region_kind": str(result.region_kind),
        "duration_s": result.duration_s,
        "warnings": list(result.warnings),
        "meta": _jsonable(dict(result.meta)),
        "lines": [
            {
                "box": _box(line.box), "baseline": list(line.baseline) if line.baseline else None,
                "block": line.block_index, "paragraph": line.paragraph_index,
                "line": line.line_index, "kind": str(line.kind), "font_size": line.font_size,
                "words": [
                    {
                        "text": w.text, "box": _box(w.box), "confidence": w.confidence,
                        "block": w.block_index, "paragraph": w.paragraph_index,
                        "line": w.line_index, "word": w.word_index,
                        "chars": [[c.text, _box(c.box), c.confidence, c.inherited_confidence]
                                  for c in w.chars],
                    }
                    for w in line.words
                ],
            }
            for line in result.lines
        ],
    }


def result_from_json(data: Mapping[str, Any]) -> OcrResult:
    lines = []
    for ln in data.get("lines", ()):
        words = tuple(
            OcrWord(
                text=w["text"], box=BBox(*w["box"]), confidence=float(w["confidence"]),
                chars=tuple(OcrChar(text=c[0], box=BBox(*c[1]), confidence=float(c[2]),
                                    inherited_confidence=bool(c[3])) for c in w.get("chars", ())),
                block_index=int(w.get("block", 0)), paragraph_index=int(w.get("paragraph", 0)),
                line_index=int(w.get("line", 0)), word_index=int(w.get("word", 0)))
            for w in ln.get("words", ())
        )
        baseline = ln.get("baseline")
        lines.append(OcrLine(
            words=words, box=BBox(*ln["box"]),
            baseline=(float(baseline[0]), float(baseline[1])) if baseline else None,
            block_index=int(ln.get("block", 0)), paragraph_index=int(ln.get("paragraph", 0)),
            line_index=int(ln.get("line", 0)), kind=RegionKind(ln.get("kind", "unknown")),
            font_size=float(ln.get("font_size", 0.0))))
    return OcrResult(
        engine=str(data.get("engine", "")), lang=str(data.get("lang", "")), lines=tuple(lines),
        region_kind=RegionKind(data.get("region_kind", "unknown")),
        duration_s=float(data.get("duration_s", 0.0)), warnings=tuple(data.get("warnings", ())),
        meta=dict(data.get("meta", {})))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# --------------------------------------------------------------------------- #
# Resource measurement
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    wall_s: float
    cpu_s: float
    rss_mb: float | None
    gpu_peak_mb: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"wall_s": round(self.wall_s, 4), "cpu_s": round(self.cpu_s, 4),
                "rss_mb": None if self.rss_mb is None else round(self.rss_mb, 1),
                "gpu_peak_mb": None if self.gpu_peak_mb is None else round(self.gpu_peak_mb, 1)}


def _rss_mb() -> float | None:
    try:
        import psutil

        return float(psutil.Process(os.getpid()).memory_info().rss) / (1024 * 1024)
    except Exception:  # noqa: BLE001 - psutil is optional
        return None


def _gpu_peak_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return float(torch.cuda.max_memory_allocated()) / (1024 * 1024)
    except Exception:  # noqa: BLE001 - torch is optional in the worker
        return None
    return None


# --------------------------------------------------------------------------- #
# The worker (child side)
# --------------------------------------------------------------------------- #


def _host(name: str) -> OcrEngine:
    module_name, class_name = HOSTABLE[name]
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)()  # type: ignore[no-any-return]


def serve(name: str, stdin: Any = None, stdout: Any = None) -> int:
    """Host ``name`` and answer requests until ``quit`` or EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if name not in HOSTABLE:
        stdout.write(json.dumps({"ok": False, "reason": f"motor desconhecido: {name}"}) + "\n")
        stdout.flush()
        return 2
    engine = _host(name)

    def reply(payload: dict[str, Any]) -> None:
        stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stdout.flush()

    for raw in stdin:
        try:
            request = json.loads(raw)
        except ValueError:
            reply({"ok": False, "error": "pedido inválido"})
            continue
        op = request.get("op")
        if op == "quit":
            reply({"ok": True})
            return 0
        if op == "probe":
            available = engine.available()
            version = getattr(engine, "version", None)
            reply({
                "ok": available, "schema": WORKER_SCHEMA, "engine": engine.name,
                "version": str(version() if callable(version) else version) if version else "",
                "languages": sorted(engine.languages()) if available else [],
                "reason": None if available else engine.unavailable_reason(),
                "capabilities": dataclasses.asdict(engine.capabilities()),
            })
            continue
        if op == "recognize":
            started_wall = time.perf_counter()
            started_cpu = time.process_time()
            try:
                from PIL import Image

                image = np.asarray(Image.open(request["image"]).convert("L"), dtype=np.uint8)
                result = engine.recognize(
                    image, lang=str(request.get("lang", "eng")),
                    psm_hint=RegionKind(request.get("psm_hint", "page")))
                usage = ResourceUsage(
                    wall_s=time.perf_counter() - started_wall,
                    cpu_s=time.process_time() - started_cpu,
                    rss_mb=_rss_mb(), gpu_peak_mb=_gpu_peak_mb())
                reply({"ok": True, "result": result_to_json(result), "usage": usage.as_dict()})
            except OcrError as exc:
                reply({"ok": False, "error": exc.message, "detail": exc.detail,
                       "kind": type(exc).__name__})
            except Exception as exc:  # noqa: BLE001 - the worker must answer, not die
                reply({"ok": False, "error": str(exc), "kind": type(exc).__name__})
            continue
        reply({"ok": False, "error": f"operação desconhecida: {op}"})
    return 0


# --------------------------------------------------------------------------- #
# The parent side
# --------------------------------------------------------------------------- #


@dataclass
class IsolatedEngine(OcrEngineBase):
    """An :class:`OcrEngine` whose adapter lives in a child process."""

    hosted: str = "paddleocr"
    python: str = sys.executable
    startup_timeout_s: float = 300.0
    call_timeout_s: float = 600.0
    env: dict[str, str] = field(default_factory=dict)
    _process: subprocess.Popen[str] | None = None
    _capabilities: EngineCapabilities | None = None
    _languages_seen: set[str] = field(default_factory=set)
    _version: str = ""
    last_usage: ResourceUsage | None = None

    def __post_init__(self) -> None:
        OcrEngineBase.__init__(self)
        self.name = self.hosted

    # -- process ----------------------------------------------------------- #

    def _start(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        env = {**os.environ, **self.env, "PYTHONIOENCODING": "utf-8"}
        self._process = subprocess.Popen(  # noqa: S603 - fixed argv, our own interpreter
            [self.python, "-m", "caissa.ocr.engines.worker", self.hosted],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return self._process

    def _call(self, request: dict[str, Any], timeout: float) -> dict[str, Any]:
        process = self._start()
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            line = process.stdout.readline()
            if line:
                return dict(json.loads(line))
            if process.poll() is not None:
                raise OcrError(self.name, "o worker isolado terminou sem responder",
                               detail=f"código {process.returncode}")
            if time.monotonic() > deadline:
                self.close()
                raise OcrError(self.name, f"o worker isolado não respondeu em {timeout:.0f} s")

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin is not None and process.poll() is None:
                process.stdin.write(json.dumps({"op": "quit"}) + "\n")
                process.stdin.flush()
            process.wait(timeout=5)
        except Exception:  # noqa: BLE001 - shutting down; nothing to report
            process.kill()
        finally:
            for pipe in (process.stdin, process.stdout):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter shutdown
            pass

    # -- OcrEngineBase ----------------------------------------------------- #

    def _probe(self) -> tuple[bool, str | None]:
        try:
            answer = self._call({"op": "probe"}, self.startup_timeout_s)
        except OcrError as exc:
            return False, f"{self.hosted}: {exc.message}"
        if answer.get("schema") != WORKER_SCHEMA:
            self.close()
            return False, (f"{self.hosted}: o worker fala o esquema {answer.get('schema')!r} e "
                           f"este adaptador o {WORKER_SCHEMA}; atualize os dois juntos.")
        if not answer.get("ok"):
            return False, str(answer.get("reason") or f"{self.hosted} indisponível no worker")
        self._languages_seen = set(answer.get("languages", ()))
        self._version = str(answer.get("version", ""))
        caps = answer.get("capabilities") or {}
        if caps:
            self._capabilities = EngineCapabilities(**caps)
        return True, None

    def _discover_languages(self) -> set[str]:
        self.available()
        return set(self._languages_seen)

    @property
    def version(self) -> str:
        self.available()
        return self._version

    def capabilities(self) -> EngineCapabilities:
        if self._capabilities is None:
            self.available()
        return self._capabilities or EngineCapabilities(
            level=HOSTED_LEVELS.get(self.hosted, 2), cost_per_megapixel_s=5.0,
            supports_char_boxes=False, supports_confidence=True, handles_layout=True,
            gpu_capable=self.hosted != "rapidocr")

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind) -> OcrResult:
        from PIL import Image

        with tempfile.TemporaryDirectory(prefix="caissa-worker-") as tmp:
            path = Path(tmp) / "region.png"
            Image.fromarray(np.ascontiguousarray(image)).save(path, format="PNG")
            answer = self._call({"op": "recognize", "image": str(path), "lang": lang,
                                 "psm_hint": str(psm_hint)}, self.call_timeout_s)
        if not answer.get("ok"):
            raise OcrError(self.name, str(answer.get("error", "falha no worker")),
                           detail=str(answer.get("detail", "")))
        usage = answer.get("usage") or {}
        self.last_usage = ResourceUsage(
            wall_s=float(usage.get("wall_s", 0.0)), cpu_s=float(usage.get("cpu_s", 0.0)),
            rss_mb=usage.get("rss_mb"), gpu_peak_mb=usage.get("gpu_peak_mb"))
        result = result_from_json(answer["result"])
        return result.with_meta(isolated=True, worker_usage=self.last_usage.as_dict())


if __name__ == "__main__":
    sys.exit(serve(sys.argv[1] if len(sys.argv) > 1 else ""))
