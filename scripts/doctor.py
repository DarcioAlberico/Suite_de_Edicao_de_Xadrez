#!/usr/bin/env python
r"""Caissa Studio -- environment health report.

Run it with the project interpreter::

    .venv\\Scripts\\python.exe scripts/doctor.py
    .venv\\Scripts\\python.exe scripts/doctor.py --json > report.json

Design rules, because this file is the last line of defence:

* **Nothing is taken on faith.** In particular ``torch.cuda.is_available()`` is
  reported but never believed: on the Blackwell reference machine it returns
  ``True`` with the wrong wheel installed and the first kernel launch then dies
  with ``no kernel image is available for execution on the device`` (SPEC R1,
  ADR-0003). So the GPU check *runs a real 4096x4096 fp16 matrix multiply*,
  synchronises, times it, and cross-checks the numbers against a CPU reference.
* **Standard library only.** The one optional import is ``torch`` itself, plus
  the ``caissa`` package from ``src/`` (added to ``sys.path`` below so the report
  works even before ``pip install -e .``). A diagnostic tool that needs a healthy
  environment to report on a broken one is useless.
* **onnxruntime is inspected from a child process, never imported here.**
  Loading onnxruntime-gpu and torch cu128 in one process is exactly the DLL
  conflict ADR-0003 exists to avoid; the doctor must not commit the sin it is
  looking for.
* **Exit code is meaningful.** 0 = healthy, 1 = a hard requirement failed,
  2 = the doctor itself crashed. ``--strict`` promotes warnings to failures.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

TARGET_PYTHON = (3, 11)
GATE_MATMUL_SIZE = 4096
MIN_RAM_GB = 15.0
CRITICAL_FREE_DISK_GB = 2.0
BLACKWELL_MAJOR = 12
MIN_CUDA_BUILD = (12, 8)
_LABEL_WIDTH = 46
BYTES_PER_GB = 1024**3

OK = "OK"
WARN = "AVISO"
FAIL = "FALHA"
SKIP = "PULADO"
INFO = "INFO"

_STATUS_LABEL = {
    OK: "[  OK  ]",
    WARN: "[ AVISO]",
    FAIL: "[ FALHA]",
    SKIP: "[PULADO]",
    INFO: "[ INFO ]",
}
_STATUS_COLOR = {
    OK: "\x1b[32m",
    WARN: "\x1b[33m",
    FAIL: "\x1b[31;1m",
    SKIP: "\x1b[90m",
    INFO: "\x1b[36m",
}
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"


# --------------------------------------------------------------------------- #
# Output plumbing
# --------------------------------------------------------------------------- #


def _console_supports(text: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _degrade(text: str) -> str:
    """Strip accents when the console cannot encode them.

    Better plain than mojibake: a diagnostic report has to stay readable inside a
    legacy code-page console.
    """
    if _console_supports(text):
        return text
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _enable_ansi() -> bool:
    """Turn on virtual-terminal processing on Windows; report whether colour works."""
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001 - colour is cosmetic
        return False


class Printer:
    """Tiny writer that degrades accents and optionally colours output."""

    def __init__(self, *, color: bool) -> None:
        """Remember whether ANSI colour may be emitted."""
        self.color = color

    def line(self, text: str = "") -> None:
        """Write one line to stdout."""
        sys.stdout.write(_degrade(text) + "\n")

    def status(self, status: str) -> str:
        """Render a status badge, coloured when supported."""
        label = _STATUS_LABEL[status]
        if not self.color:
            return label
        return f"{_STATUS_COLOR[status]}{label}{_RESET}"

    def bold(self, text: str) -> str:
        """Render bold text when supported."""
        return f"{_BOLD}{text}{_RESET}" if self.color else text


# --------------------------------------------------------------------------- #
# Check model
# --------------------------------------------------------------------------- #


@dataclass
class Check:
    """One line of the report.

    Attributes:
        key: Stable machine-readable identifier, used by ``--json``.
        label: Human-readable name.
        status: One of ``OK`` / ``AVISO`` / ``FALHA`` / ``PULADO`` / ``INFO``.
        value: Short measured value.
        detail: Longer explanation, printed under the line when not ``OK``.
        hard: A failing hard check makes the process exit non-zero.
        data: Extra structured payload for ``--json``.
    """

    key: str
    label: str
    status: str
    value: str = ""
    detail: str = ""
    hard: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Plain-data view for ``--json`` output."""
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "value": self.value,
            "detail": self.detail,
            "hard": self.hard,
            "data": self.data,
        }


@dataclass
class Section:
    """A named group of checks."""

    title: str
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> Check:
        """Append and return ``check`` so callers can inspect it."""
        self.checks.append(check)
        return check


# --------------------------------------------------------------------------- #
# System facts (no third-party dependencies)
# --------------------------------------------------------------------------- #


def _windows_memory() -> tuple[int, int] | None:
    """Return ``(total, available)`` physical bytes via ``GlobalMemoryStatusEx``."""

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        )

    try:
        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(  # type: ignore[attr-defined]
            ctypes.byref(status)
        ):
            return None
    except Exception:  # noqa: BLE001
        return None
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def total_memory() -> tuple[int | None, int | None]:
    """Return ``(total_bytes, available_bytes)``; either may be ``None``."""
    if os.name == "nt":
        result = _windows_memory()
        return result if result else (None, None)
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return (None, None)
    return (pages * page_size, None)


def physical_core_count() -> int | None:
    """Count physical cores on Windows via ``GetLogicalProcessorInformationEx``."""
    if os.name != "nt":
        return None  # no portable POSIX answer; logical count is reported instead
    relation_processor_core = 0
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        length = ctypes.c_uint32(0)
        kernel32.GetLogicalProcessorInformationEx(
            relation_processor_core, None, ctypes.byref(length)
        )
        if length.value == 0:
            return None
        buffer = (ctypes.c_byte * length.value)()
        if not kernel32.GetLogicalProcessorInformationEx(
            relation_processor_core, buffer, ctypes.byref(length)
        ):
            return None
    except Exception:  # noqa: BLE001
        return None
    raw = bytes(buffer)
    offset = 0
    cores = 0
    while offset + 8 <= length.value:
        size = int.from_bytes(raw[offset + 4 : offset + 8], "little")
        if size == 0:
            break
        cores += 1
        offset += size
    return cores or None


def _cpu_name_from_registry() -> str | None:
    """Read the marketing CPU name from the Windows registry."""
    import winreg  # noqa: PLC0415 - Windows only

    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
    )
    with key:
        value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return str(value).strip() or None


def cpu_name() -> str:
    """Best-effort marketing name of the CPU."""
    if os.name == "nt":
        try:
            name = _cpu_name_from_registry()
        except Exception:  # noqa: BLE001 - registry layout varies by SKU
            name = None
        if name:
            return name
    return platform.processor() or platform.machine() or "desconhecido"


_WINDOWS_11_FIRST_BUILD = 22000


def os_description() -> str:
    """Human-readable operating-system description including the build number.

    ``platform.win32_ver()`` still reports Windows 11 as release "10" -- the
    build number is the only reliable discriminator, and 22000 is where 11
    starts.
    """
    if os.name != "nt":
        return f"{platform.system()} {platform.release()}"
    release, version, _service_pack, _kind = platform.win32_ver()
    try:
        edition = platform.win32_edition() or ""
    except Exception:  # noqa: BLE001 - absent on some Windows SKUs
        edition = ""
    tail = version.split(".")[-1]
    build = int(tail) if tail.isdigit() else 0
    name = "11" if build >= _WINDOWS_11_FIRST_BUILD else release
    parts = [f"Windows {name}", edition, f"(build {version})"]
    return " ".join(part for part in parts if part)


# --------------------------------------------------------------------------- #
# onnxruntime inspection -- from metadata and a child process, never in-process
# --------------------------------------------------------------------------- #

_ONNX_PROBE = (
    "import json,onnxruntime as ort\n"
    "info={'version':ort.__version__,'providers':list(ort.get_available_providers())}\n"
    "try:\n"
    "    info['build_info']=ort.get_build_info()\n"
    "except Exception as exc:\n"
    "    info['build_info']=None\n"
    "print(json.dumps(info))\n"
)


def onnx_distributions() -> dict[str, str]:
    """Return installed distributions relevant to the ADR-0003 conflict."""
    from importlib import metadata  # noqa: PLC0415 - only needed for this probe

    found: dict[str, str] = {}
    for dist in metadata.distributions():
        name = (dist.metadata["Name"] or "").lower()
        if name.startswith(("onnxruntime", "nvidia-cuda-runtime", "nvidia-cublas")):
            found[name] = dist.version or "?"
    return found


def onnx_package_dir() -> Path | None:
    """Locate the onnxruntime package without importing it."""
    from importlib import util  # noqa: PLC0415 - only needed for this probe

    try:
        spec = util.find_spec("onnxruntime")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


_CUDA_LIB_PATTERNS = (
    re.compile(r"^cudart64_(\d+)\.dll$", re.IGNORECASE),
    re.compile(r"^cublasLt64_(\d+)\.dll$", re.IGNORECASE),
    re.compile(r"^libcudart\.so\.(\d+)"),
    re.compile(r"^libcublasLt\.so\.(\d+)"),
)


def onnx_cuda_from_libraries(package_dir: Path) -> tuple[int, ...] | None:
    """Infer the CUDA major version from the CUDA libraries shipped alongside ORT.

    ``onnxruntime-gpu`` vendors (or links against) ``cudart64_<major>.dll``; the
    major number in that filename is the CUDA Runtime it will load into the
    process. Comparing it with ``torch.version.cuda`` is what detects the
    SPEC R2 conflict without importing either library here.
    """
    majors: set[int] = set()
    for sub in (package_dir, package_dir / "capi"):
        if not sub.is_dir():
            continue
        for path in sub.iterdir():
            for pattern in _CUDA_LIB_PATTERNS:
                match = pattern.match(path.name)
                if match:
                    majors.add(int(match.group(1)))
    if not majors:
        return None
    return tuple(sorted(majors))


def probe_onnxruntime(timeout: float = 60.0) -> dict[str, Any] | None:
    """Inspect onnxruntime from a *child* process, as ADR-0003 requires.

    Returns ``None`` when onnxruntime is not installed at all -- which is the
    healthy state for the main environment.
    """
    package_dir = onnx_package_dir()
    distributions = onnx_distributions()
    onnx_dists = {k: v for k, v in distributions.items() if k.startswith("onnxruntime")}
    if package_dir is None and not onnx_dists:
        return None

    report: dict[str, Any] = {
        "distributions": distributions,
        "package_dir": str(package_dir) if package_dir else None,
        "cuda_library_majors": (
            list(onnx_cuda_from_libraries(package_dir)) if package_dir else None
        ),
        "version": None,
        "providers": [],
        "build_info": None,
        "cuda_version": None,
        "probe_error": None,
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _ONNX_PROBE],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        report["probe_error"] = f"{type(exc).__name__}: {exc}"
        return report
    if completed.returncode != 0:
        report["probe_error"] = (completed.stderr or "").strip()[-500:]
        return report
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        report["probe_error"] = f"saida ilegivel do subprocesso: {exc}"
        return report

    report["version"] = payload.get("version")
    report["providers"] = payload.get("providers") or []
    report["build_info"] = payload.get("build_info")
    build_info = payload.get("build_info") or ""
    match = re.search(r"CUDA[ _]?[Vv]ersion[:= ]+(\d+)\.(\d+)", str(build_info))
    if match:
        report["cuda_version"] = [int(match.group(1)), int(match.group(2))]
    return report


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #


class Doctor:
    """Collects every check and renders the report."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Store CLI arguments and prepare an empty report."""
        self.args = args
        self.sections: list[Section] = []
        self.raw: dict[str, Any] = {}

    def section(self, title: str) -> Section:
        """Create and register a new section."""
        section = Section(title)
        self.sections.append(section)
        return section

    # -- individual sections ------------------------------------------------ #

    def check_system(self) -> None:
        """OS, CPU, RAM and free disk on the interpreter's drive."""
        section = self.section("SISTEMA")
        section.add(
            Check(
                "os",
                "Sistema operacional",
                INFO,
                os_description(),
                data={"machine": platform.machine()},
            )
        )

        logical = os.cpu_count() or 0
        physical = physical_core_count()
        cores = f"{physical}C/{logical}T" if physical else f"{logical} threads"
        section.add(
            Check(
                "cpu",
                "Processador",
                INFO,
                f"{cpu_name()} - {cores}",
                data={"logical": logical, "physical": physical, "name": cpu_name()},
            )
        )

        total, available = total_memory()
        if total is None:
            section.add(Check("ram", "Memoria RAM", SKIP, "nao foi possivel medir"))
        else:
            total_gb = total / BYTES_PER_GB
            avail_text = f", {available / BYTES_PER_GB:.1f} GiB livres" if available else ""
            status = OK if total_gb >= MIN_RAM_GB else WARN
            detail = (
                ""
                if status == OK
                else "O perfil-alvo pressupoe ~32 GiB para bases PGN grandes (SPEC secao 2)."
            )
            section.add(
                Check(
                    "ram",
                    "Memoria RAM",
                    status,
                    f"{total_gb:.1f} GiB{avail_text}",
                    detail,
                    data={"total_bytes": total, "available_bytes": available},
                )
            )

        self._check_disk(section)

    def _check_disk(self, section: Section) -> None:
        min_free_gb = self.config_min_free_disk()
        seen: set[str] = set()
        for label, target in (
            ("interpretador", Path(sys.prefix)),
            ("projeto", _REPO_ROOT),
        ):
            anchor = str(Path(target).anchor or target)
            if anchor in seen:
                continue
            seen.add(anchor)
            try:
                usage = shutil.disk_usage(target)
            except OSError as exc:
                section.add(
                    Check(f"disk_{label}", f"Disco ({label})", WARN, "indisponivel", str(exc))
                )
                continue
            free_gb = usage.free / BYTES_PER_GB
            total_gb = usage.total / BYTES_PER_GB
            if free_gb < CRITICAL_FREE_DISK_GB:
                status, hard = FAIL, True
                detail = "Espaco critico. As rodas do torch cu128 sozinhas ocupam cerca de 3 GiB."
            elif free_gb < min_free_gb:
                status, hard = WARN, False
                detail = (
                    f"Abaixo do minimo recomendado de {min_free_gb:.0f} GiB (SPEC R4). "
                    f"Cache de renderizacao, indices e pesos disputam este espaco."
                )
            else:
                status, hard, detail = OK, False, ""
            section.add(
                Check(
                    f"disk_{label}",
                    f"Disco {anchor} ({label})",
                    status,
                    f"{free_gb:.1f} GiB livres de {total_gb:.0f} GiB",
                    detail,
                    hard=hard,
                    data={
                        "free_bytes": usage.free,
                        "total_bytes": usage.total,
                        "path": str(target),
                    },
                )
            )

    def check_python(self) -> None:
        """Interpreter version, architecture and virtual-environment state."""
        section = self.section("PYTHON")
        current = sys.version_info[:2]
        is_target = current == TARGET_PYTHON
        section.add(
            Check(
                "python_version",
                "Versao do Python",
                OK if is_target else FAIL,
                platform.python_version(),
                ""
                if is_target
                else (
                    f"O alvo do projeto e Python {TARGET_PYTHON[0]}.{TARGET_PYTHON[1]} "
                    f"(SPEC R5): e a versao com cobertura completa de rodas binarias para "
                    f"PySide6, PyMuPDF e torch cu128. Recrie o ambiente com "
                    f"scripts/setup_env.ps1."
                ),
                hard=True,
                data={"version": platform.python_version(), "target": list(TARGET_PYTHON)},
            )
        )
        section.add(
            Check(
                "python_arch",
                "Arquitetura",
                OK if sys.maxsize > 2**32 else FAIL,
                f"{platform.architecture()[0]} ({platform.machine()})",
                "" if sys.maxsize > 2**32 else "E necessario um interpretador 64 bits.",
                hard=True,
            )
        )
        in_venv = sys.prefix != sys.base_prefix
        expected = _REPO_ROOT / ".venv"
        inside_project_venv = in_venv and Path(sys.prefix).resolve() == expected.resolve()
        section.add(
            Check(
                "python_venv",
                "Ambiente virtual",
                OK if inside_project_venv else WARN,
                sys.prefix,
                ""
                if inside_project_venv
                else (
                    f"O relatorio esta sendo gerado fora de {expected}. Os resultados descrevem "
                    f"este interpretador, nao necessariamente o do projeto."
                ),
                data={"in_venv": in_venv, "prefix": sys.prefix, "expected": str(expected)},
            )
        )
        section.add(
            Check(
                "package_import",
                "Pacote caissa importavel",
                OK if self._caissa_importable() else FAIL,
                self._caissa_location(),
                ""
                if self._caissa_importable()
                else 'Execute: pip install -e ".[dev]" (ou scripts/setup_env.ps1).',
                hard=True,
            )
        )

    @staticmethod
    def _caissa_importable() -> bool:
        try:
            import caissa  # noqa: F401,PLC0415
        except Exception:  # noqa: BLE001
            return False
        return True

    @staticmethod
    def _caissa_location() -> str:
        try:
            import caissa  # noqa: PLC0415

            return f"{caissa.__version__} em {Path(caissa.__file__ or '?').parent}"
        except Exception as exc:  # noqa: BLE001
            return f"indisponivel ({type(exc).__name__}: {exc})"

    def check_torch_and_gpu(self) -> None:
        """The section that matters: torch build, capability, and a REAL kernel."""
        section = self.section("GPU / PYTORCH")
        try:
            from caissa.vision.runtime import device as devmod  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            section.add(
                Check(
                    "runtime_import",
                    "caissa.vision.runtime.device",
                    FAIL,
                    "nao importavel",
                    f"{type(exc).__name__}: {exc}",
                    hard=True,
                )
            )
            return

        torch = devmod.import_torch()
        if torch is None:
            section.add(
                Check(
                    "torch",
                    "PyTorch",
                    FAIL,
                    "ausente",
                    (
                        f"{devmod.torch_import_error()}. Instale com: "
                        f"pip install torch --index-url https://download.pytorch.org/whl/cu128 "
                        f"(scripts/setup_env.ps1 faz isso)."
                    ),
                    hard=True,
                )
            )
            return

        build = devmod.torch_cuda_build_version(torch)
        build_text = ".".join(str(p) for p in build) if build else "CPU-only"
        section.add(
            Check(
                "torch_version",
                "Versao do PyTorch",
                OK,
                str(torch.__version__),
                data={"version": str(torch.__version__)},
            )
        )
        section.add(
            Check(
                "torch_cuda_build",
                "CUDA da roda do PyTorch",
                OK if build and build >= MIN_CUDA_BUILD else FAIL,
                build_text,
                ""
                if build and build >= MIN_CUDA_BUILD
                else (
                    "SPEC R1: GPUs Blackwell (sm_120) so tem kernels nas rodas cu128 ou "
                    "posteriores. Reinstale a partir de "
                    "https://download.pytorch.org/whl/cu128."
                ),
                hard=True,
                data={"cuda_build": list(build) if build else None},
            )
        )

        reported = bool(torch.cuda.is_available())
        section.add(
            Check(
                "torch_cuda_reported",
                "torch.cuda.is_available()",
                INFO,
                str(reported),
                "Valor apenas informativo -- ele retorna True mesmo quando nao existem "
                "kernels para a arquitetura da GPU. A verificacao real e a de baixo.",
                data={"reported": reported},
            )
        )

        driver = devmod.nvidia_smi_driver_version()
        section.add(
            Check(
                "driver",
                "Driver NVIDIA",
                INFO if driver else SKIP,
                driver or "nvidia-smi ausente",
            )
        )

        if not reported:
            section.add(
                Check(
                    "gpu_present",
                    "GPU CUDA",
                    FAIL if not self.args.allow_cpu else WARN,
                    "nenhuma",
                    "Nenhum dispositivo CUDA visivel para o PyTorch.",
                    hard=not self.args.allow_cpu,
                )
            )
            return

        index = 0
        props = torch.cuda.get_device_properties(index)
        capability = tuple(torch.cuda.get_device_capability(index))
        section.add(
            Check(
                "gpu_name",
                "GPU",
                INFO,
                f"{props.name} ({torch.cuda.device_count()} dispositivo(s))",
                data={"name": str(props.name), "count": int(torch.cuda.device_count())},
            )
        )
        cap_supported = not (
            capability[0] >= BLACKWELL_MAJOR and (build is None or build < MIN_CUDA_BUILD)
        )
        section.add(
            Check(
                "gpu_capability",
                "Compute capability",
                OK if cap_supported else FAIL,
                f"sm_{capability[0]}{capability[1]} ({capability[0]}, {capability[1]})",
                ""
                if cap_supported
                else (
                    f"A GPU e sm_{capability[0]}{capability[1]} mas a roda instalada foi "
                    f"compilada para CUDA {build_text}; nao ha kernels compativeis."
                ),
                hard=True,
                data={"capability": list(capability)},
            )
        )

        try:
            free_bytes, total_bytes = (int(v) for v in torch.cuda.mem_get_info(index))
        except Exception as exc:  # noqa: BLE001
            section.add(Check("vram", "VRAM", WARN, "indisponivel", f"{type(exc).__name__}: {exc}"))
            free_bytes = total_bytes = 0
        else:
            budget_gb = self.config_vram_budget()
            total_gb = total_bytes / BYTES_PER_GB
            over_budget = budget_gb > total_gb
            section.add(
                Check(
                    "vram",
                    "VRAM total / livre",
                    WARN if over_budget else OK,
                    f"{total_gb:.2f} GiB total, {free_bytes / BYTES_PER_GB:.2f} GiB livres",
                    (
                        f"runtime.vram_budget_gb = {budget_gb:.1f} GiB excede a VRAM fisica "
                        f"({total_gb:.2f} GiB). Reduza o orcamento (ADR-0004)."
                    )
                    if over_budget
                    else "",
                    data={"free_bytes": free_bytes, "total_bytes": total_bytes},
                )
            )

        self._run_real_workload(section, devmod, capability, index)

    def _run_real_workload(
        self,
        section: Section,
        devmod: Any,
        capability: tuple[int, ...],
        index: int = 0,
    ) -> None:
        """Allocate, multiply, synchronise, time and verify. The whole point."""
        if self.args.skip_gpu:
            section.add(Check("gpu_matmul", "Multiplicacao real na GPU", SKIP, "--skip-gpu"))
            return

        size = self.args.matmul_size
        started = time.perf_counter()
        probe = devmod.probe_real_compute(device=f"cuda:{index}", size=size, dtype="float16")
        wall_s = time.perf_counter() - started
        self.raw["probe"] = probe.as_dict()

        budget_ms = self.config_matmul_budget()
        if not probe.ok:
            raw_error = probe.error_message or (
                "(nenhuma excecao foi levantada; a verificacao numerica ou de dispositivo "
                "reprovou o resultado)"
            )
            section.add(
                Check(
                    "gpu_matmul",
                    f"Multiplicacao real {size}x{size} fp16",
                    FAIL if not self.args.allow_cpu else WARN,
                    probe.error_type or "resultado invalido",
                    f"{probe.diagnosis}\nErro bruto: {raw_error}",
                    hard=not self.args.allow_cpu,
                    data=probe.as_dict(),
                )
            )
            return

        within_budget = probe.warm_ms <= budget_ms
        section.add(
            Check(
                "gpu_matmul",
                f"Multiplicacao real {size}x{size} fp16",
                OK if within_budget else WARN,
                f"{probe.warm_ms:.2f} ms ({probe.gflops / 1000:.1f} TFLOP/s)",
                ""
                if within_budget
                else (
                    f"Acima do orcamento de {budget_ms:.0f} ms do portao F0. "
                    f"Verifique se outra aplicacao esta usando a GPU."
                ),
                data=probe.as_dict(),
            )
        )
        section.add(
            Check(
                "gpu_matmul_numeric",
                "Conferencia numerica (referencia de CPU)",
                OK,
                f"erro maximo {probe.max_abs_error:.5f} (tolerancia {probe.tolerance:.5f})",
                data={
                    "max_abs_error": probe.max_abs_error,
                    "tolerance": probe.tolerance,
                    "result_device": probe.result_device,
                },
            )
        )
        section.add(
            Check(
                "gpu_matmul_timing",
                "Tempos frio / quente / total",
                INFO,
                f"{probe.cold_ms:.2f} ms / {probe.warm_ms:.2f} ms / {wall_s * 1000:.0f} ms",
                data={"cold_ms": probe.cold_ms, "warm_ms": probe.warm_ms, "wall_ms": wall_s * 1000},
            )
        )
        self.raw["capability"] = list(capability)

    def check_interop(self) -> None:
        """ADR-0003: onnxruntime must not share this environment with torch cu128."""
        section = self.section("INTEROPERABILIDADE (ADR-0003)")
        if self.args.skip_onnx:
            section.add(Check("onnx", "onnxruntime", SKIP, "--skip-onnx"))
            return

        report = probe_onnxruntime()
        if report is None:
            section.add(
                Check(
                    "onnx",
                    "onnxruntime no ambiente principal",
                    OK,
                    "ausente (correto)",
                    data={"installed": False},
                )
            )
            section.add(
                Check(
                    "onnx_worker",
                    "Worker ONNX isolado",
                    INFO,
                    "sera criado por scripts/setup_onnx_worker.ps1 na frente F5",
                )
            )
            return

        distributions = report["distributions"]
        gpu_variant = any(name.startswith("onnxruntime-gpu") for name in distributions)
        version = report.get("version") or ", ".join(
            f"{k}=={v}" for k, v in distributions.items() if k.startswith("onnxruntime")
        )
        providers = report.get("providers") or []

        section.add(
            Check(
                "onnx",
                "onnxruntime no ambiente principal",
                WARN if gpu_variant else INFO,
                f"{version} (providers: {', '.join(providers) or 'n/d'})",
                (
                    "ADR-0003: onnxruntime-gpu NAO deve compartilhar ambiente com o torch "
                    "cu128. Remova-o daqui (pip uninstall onnxruntime-gpu) e use o ambiente "
                    "isolado do worker."
                )
                if gpu_variant
                else "",
                data=report,
            )
        )
        if report.get("probe_error"):
            section.add(
                Check(
                    "onnx_probe",
                    "Inspecao do onnxruntime (subprocesso)",
                    WARN,
                    "falhou",
                    str(report["probe_error"]),
                    data={"probe_error": report["probe_error"]},
                )
            )

        torch_cuda = self.raw.get("torch_cuda_build")
        onnx_cuda = report.get("cuda_version")
        library_majors = report.get("cuda_library_majors") or []
        if torch_cuda and (onnx_cuda or library_majors):
            onnx_major = onnx_cuda[0] if onnx_cuda else library_majors[0]
            mismatch = onnx_major != torch_cuda[0]
            onnx_text = (
                ".".join(str(p) for p in onnx_cuda)
                if onnx_cuda
                else f"~{onnx_major}.x (inferido das DLLs)"
            )
            section.add(
                Check(
                    "onnx_cuda_mismatch",
                    "CUDA Runtime: torch vs onnxruntime",
                    WARN if mismatch else OK,
                    f"torch {'.'.join(str(p) for p in torch_cuda)} vs onnxruntime {onnx_text}",
                    (
                        "CONFLITO (SPEC R2 / ADR-0003): os dois runtimes carregam CUDA "
                        "Runtimes de versoes maiores diferentes no mesmo processo. O sintoma "
                        "tipico nao e um erro: e queda silenciosa para CPU ou conflito de DLL. "
                        "Mantenha o onnxruntime em um ambiente separado."
                    )
                    if mismatch
                    else "",
                    data={"torch_cuda": torch_cuda, "onnx_cuda": onnx_cuda},
                )
            )

    def check_configuration(self) -> None:
        """Configuration layering, budgets and writable directories."""
        section = self.section("CONFIGURACAO")
        try:
            from caissa.core.config import get_config  # noqa: PLC0415

            config = get_config()
        except Exception as exc:  # noqa: BLE001
            section.add(
                Check(
                    "config",
                    "Configuracao em camadas",
                    FAIL,
                    "nao carregou",
                    f"{type(exc).__name__}: {exc}",
                    hard=True,
                )
            )
            return

        section.add(
            Check(
                "config",
                "Camadas de configuracao",
                OK,
                f"{len(config.sources)} camada(s)",
                "\n".join(config.sources),
                data={"sources": list(config.sources), "provenance": config.provenance},
            )
        )
        section.add(
            Check(
                "config_vram",
                "Orcamento de VRAM (ADR-0004)",
                OK,
                f"{config.runtime.vram_budget_gb:.1f} GiB "
                f"(origem: {config.origin_of('runtime.vram_budget_gb')})",
                data={"vram_budget_gb": config.runtime.vram_budget_gb},
            )
        )
        section.add(
            Check(
                "config_cache",
                "Tetos de cache (SPEC R4)",
                OK,
                f"paginas {config.cache.page_cache_mb} MiB · pesos "
                f"{config.cache.model_weights_budget_gb:.1f} GiB · indice "
                f"{config.cache.index_budget_gb:.0f} GiB · disco total "
                f"{config.cache.total_disk_budget_gb:.0f} GiB",
                data=config.to_dict()["cache"],
            )
        )

        for label, path in (
            ("dados", config.paths.data_dir),
            ("cache", config.paths.cache_dir),
            ("modelos", config.paths.models_dir),
        ):
            status, detail = OK, ""
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".caissa-doctor-write-test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                status, detail = WARN, f"{type(exc).__name__}: {exc}"
            section.add(Check(f"path_{label}", f"Diretorio de {label}", status, str(path), detail))

        try:
            from caissa.vision.runtime.residency import (  # noqa: PLC0415
                ModelResidencyManager,
            )

            manager = ModelResidencyManager(device="cpu" if self.args.skip_gpu else None)
            manager.resolve_device()
            report = manager.budget_report()
            section.add(
                Check(
                    "residency",
                    "ModelResidencyManager",
                    OK,
                    f"orcamento {report.budget_bytes / BYTES_PER_GB:.2f} GiB em {report.device}",
                    report.to_text(),
                    data=report.as_dict(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            section.add(
                Check(
                    "residency",
                    "ModelResidencyManager",
                    FAIL,
                    "falhou",
                    f"{type(exc).__name__}: {exc}",
                    hard=True,
                )
            )

    # -- configuration helpers --------------------------------------------- #

    def _config_value(self, getter: str, fallback: float) -> float:
        try:
            from caissa.core.config import get_config  # noqa: PLC0415

            runtime = get_config().runtime
            return float(getattr(runtime, getter))
        except Exception:  # noqa: BLE001
            return fallback

    def config_min_free_disk(self) -> float:
        """Free-disk warning threshold, in GiB."""
        return self._config_value("min_free_disk_gb", 20.0)

    def config_vram_budget(self) -> float:
        """VRAM budget, in GiB."""
        return self._config_value("vram_budget_gb", 7.0)

    def config_matmul_budget(self) -> float:
        """Warm-matmul time budget, in milliseconds."""
        return self._config_value("gpu_matmul_budget_ms", 100.0)

    # -- orchestration ------------------------------------------------------ #

    def run(self) -> int:
        """Execute every check and return the process exit code."""
        self.check_system()
        self.check_python()
        try:
            from caissa.vision.runtime.device import (  # noqa: PLC0415 - lazy by design
                torch_cuda_build_version,
            )

            build = torch_cuda_build_version()
            self.raw["torch_cuda_build"] = list(build) if build else None
        except Exception:  # noqa: BLE001
            self.raw["torch_cuda_build"] = None
        self.check_torch_and_gpu()
        self.check_interop()
        self.check_configuration()
        return self.exit_code()

    def all_checks(self) -> list[Check]:
        """Flatten every section into one list."""
        return [check for section in self.sections for check in section.checks]

    def counts(self) -> dict[str, int]:
        """Count checks by status."""
        tally = {OK: 0, WARN: 0, FAIL: 0, SKIP: 0, INFO: 0}
        for check in self.all_checks():
            tally[check.status] += 1
        return tally

    def hard_failures(self) -> list[Check]:
        """Every failing hard requirement."""
        return [c for c in self.all_checks() if c.status == FAIL and c.hard]

    def exit_code(self) -> int:
        """0 when healthy; 1 when a hard requirement (or, with --strict, a warning) fails."""
        if self.hard_failures():
            return 1
        if self.args.strict and self.counts()[WARN]:
            return 1
        if any(c.status == FAIL for c in self.all_checks()):
            return 1
        return 0

    def gate_f0(self) -> tuple[bool, list[str]]:
        """Evaluate the two GPU items of the F0 gate from ROADMAP.md."""
        by_key = {c.key: c for c in self.all_checks()}
        notes: list[str] = []
        capability = by_key.get("gpu_capability")
        matmul = by_key.get("gpu_matmul")
        cap_ok = capability is not None and capability.status == OK
        notes.append(
            f"GPU ativa com capability {capability.value if capability else 'n/d'}: "
            f"{'sim' if cap_ok else 'NAO'}"
        )
        budget = self.config_matmul_budget()
        matmul_ok = (
            matmul is not None
            and matmul.status == OK
            and float(matmul.data.get("warm_ms", 1e9)) < budget
        )
        measured = f"{matmul.data.get('warm_ms', 0):.2f} ms" if matmul and matmul.data else "n/d"
        notes.append(
            f"Matmul 4096x4096 abaixo de {budget:.0f} ms: "
            f"{'sim' if matmul_ok else 'NAO'} ({measured})"
        )
        return cap_ok and matmul_ok, notes

    # -- rendering ---------------------------------------------------------- #

    def render_text(self, printer: Printer) -> None:
        """Print the human-readable report."""
        width = 92
        stamp = datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        printer.line("=" * width)
        printer.line(printer.bold(" Caïssa Studio — Relatório de Saúde do Ambiente"))
        printer.line(f" {stamp}  ·  {platform.node()}  ·  {sys.executable}")
        printer.line("=" * width)

        for section in self.sections:
            printer.line()
            printer.line(printer.bold(section.title))
            printer.line("-" * width)
            for check in section.checks:
                printer.line(
                    f"  {printer.status(check.status)}  {check.label:<{_LABEL_WIDTH}} {check.value}"
                )
                if check.detail and check.status != OK:
                    for para in check.detail.splitlines():
                        for line in textwrap.wrap(para, width=width - 14) or [""]:
                            printer.line(f"{' ' * 12}{line}")
                elif check.detail and check.status == OK and self.args.verbose:
                    for para in check.detail.splitlines():
                        printer.line(f"{' ' * 12}{para}")

        tally = self.counts()
        printer.line()
        printer.line("=" * width)
        printer.line(
            printer.bold("RESUMO: ")
            + f"{tally[OK]} ok · {tally[WARN]} aviso(s) · {tally[FAIL]} falha(s) · "
            f"{tally[SKIP]} pulado(s) · {tally[INFO]} informativo(s)"
        )

        passed, notes = self.gate_f0()
        printer.line()
        printer.line(printer.bold("PORTÃO F0 (itens de GPU do ROADMAP):"))
        for note in notes:
            printer.line(f"  - {note}")
        printer.line(f"  => {'APROVADO' if passed else 'REPROVADO'}")

        failures = [c for c in self.all_checks() if c.status == FAIL]
        if failures:
            printer.line()
            printer.line(printer.bold("FALHAS QUE PRECISAM DE ACAO:"))
            for check in failures:
                marker = "obrigatória" if check.hard else "opcional"
                printer.line(f"  - [{marker}] {check.label}: {check.value}")
        printer.line("=" * width)

    def render_json(self) -> str:
        """Serialise the whole report."""
        passed, notes = self.gate_f0()
        payload = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "hostname": platform.node(),
            "executable": sys.executable,
            "exit_code": self.exit_code(),
            "summary": self.counts(),
            "gate_f0": {"passed": passed, "notes": notes},
            "hard_failures": [c.key for c in self.hard_failures()],
            "sections": [
                {"title": s.title, "checks": [c.as_dict() for c in s.checks]} for s in self.sections
            ],
            "raw": self.raw,
        }
        return json.dumps(payload, indent=2, ensure_ascii=True, default=str)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="doctor.py",
        description=(
            "Relatorio de saude do ambiente do Caissa Studio. Executa uma carga real na GPU "
            "em vez de confiar em torch.cuda.is_available()."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="emite JSON em vez da tabela")
    parser.add_argument(
        "--strict", action="store_true", help="trata avisos como falhas (codigo de saida 1)"
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="nao falha quando a GPU esta ausente ou inutilizavel",
    )
    parser.add_argument("--skip-gpu", action="store_true", help="pula a carga real na GPU")
    parser.add_argument("--skip-onnx", action="store_true", help="pula a inspecao do onnxruntime")
    parser.add_argument(
        "--matmul-size",
        type=int,
        default=GATE_MATMUL_SIZE,
        help=f"aresta das matrizes do teste de GPU (padrao: {GATE_MATMUL_SIZE})",
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="ignora os arquivos de configuracao de usuario e de projeto",
    )
    parser.add_argument("--no-color", action="store_true", help="desativa cores ANSI")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="mostra detalhes tambem nas linhas OK"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.isolated:
        os.environ["CAISSA_NO_USER_CONFIG"] = "1"
        os.environ["CAISSA_NO_PROJECT_CONFIG"] = "1"

    doctor = Doctor(args)
    try:
        code = doctor.run()
    except Exception as exc:  # noqa: BLE001 - the doctor must never crash silently
        import traceback  # noqa: PLC0415 - only needed on the crash path

        sys.stderr.write("O proprio doctor.py falhou:\n")
        traceback.print_exc()
        sys.stderr.write(f"\n{type(exc).__name__}: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(doctor.render_json() + "\n")
    else:
        doctor.render_text(Printer(color=not args.no_color and _enable_ansi()))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
