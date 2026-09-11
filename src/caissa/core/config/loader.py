"""Layered configuration loading.

Layer order, lowest precedence first::

    1. defaults        the dataclass defaults in :mod:`caissa.core.config.schema`
    2. user file       %LOCALAPPDATA%/CaissaStudio/caissa.toml  (or $CAISSA_CONFIG)
    3. environment     CAISSA_<SECTION>__<FIELD>=<value>
    4. project file    ./caissa.toml, ./.caissa.toml, or [tool.caissa] in
                       ./pyproject.toml, searched upward from the working tree
    5. overrides       values passed programmatically to :func:`load_config`

The ordering is deliberate: **the most specific scope wins**. A ``caissa.toml``
checked into one working tree describes that tree and should not be silently
defeated by a variable exported once in the shell profile; conversely a variable
exported for a single command should still beat the machine-wide user file.
Programmatic overrides sit on top because they come from an explicit call site
(tests, the batch runner, ``--flag`` handling).

Control variables consulted by the loader itself -- and therefore *not* settings:

``CAISSA_CONFIG``
    Absolute path to the user configuration file.
``CAISSA_PROJECT_DIR``
    Directory to start the upward search for a project file.
``CAISSA_NO_USER_CONFIG`` / ``CAISSA_NO_PROJECT_CONFIG``
    Truthy values disable that layer entirely (used by the test-suite and by
    ``scripts/doctor.py --isolated``).
"""

from __future__ import annotations

import difflib
import os
import threading
import tomllib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, get_args, get_origin, get_type_hints

from caissa.core.config.errors import ConfigError, ConfigFileError, UnknownSettingError
from caissa.core.config.schema import (
    SECTION_TYPES,
    CaissaConfig,
    default_data_dir,
)

__all__ = [
    "CONTROL_ENV_VARS",
    "ENV_PREFIX",
    "ConfigLayer",
    "environment_layer",
    "get_config",
    "load_config",
    "project_file_layer",
    "reset_config",
    "set_config",
    "user_config_path",
    "user_file_layer",
]

ENV_PREFIX: Final = "CAISSA_"
ENV_DELIMITER: Final = "__"
USER_CONFIG_FILENAME: Final = "caissa.toml"
PROJECT_CONFIG_FILENAMES: Final = ("caissa.toml", ".caissa.toml")

CONTROL_ENV_VARS: Final[frozenset[str]] = frozenset(
    {
        "CAISSA_CONFIG",
        "CAISSA_PROJECT_DIR",
        "CAISSA_NO_USER_CONFIG",
        "CAISSA_NO_PROJECT_CONFIG",
    }
)

_INT_PAIR_LENGTH: Final = 2
_TRUE_TOKENS: Final = frozenset({"1", "true", "yes", "on", "sim", "y", "t"})
_FALSE_TOKENS: Final = frozenset({"0", "false", "no", "off", "nao", "n", "f"})

RawSection = Mapping[str, object]
RawConfig = Mapping[str, RawSection]


# --------------------------------------------------------------------------- #
# Layers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ConfigLayer:
    """One contribution to the merged configuration.

    Attributes:
        name: Stable identifier used in provenance (``"user-file"``, ...).
        origin: Human-readable description of where the values came from.
        values: Section -> field -> raw value, before coercion.
        present: ``False`` when the layer exists conceptually but had nothing to
            contribute (e.g. no project file was found). Reported by ``doctor``.
    """

    name: str
    origin: str
    values: RawConfig
    present: bool = True

    def describe(self) -> str:
        """One-line description for diagnostics output."""
        if not self.present:
            return f"{self.name}: {self.origin} (ausente)"
        count = sum(len(section) for section in self.values.values())
        return f"{self.name}: {self.origin} ({count} valor(es))"


def _is_truthy(raw: str) -> bool:
    return raw.strip().lower() in _TRUE_TOKENS


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except OSError as exc:
        raise ConfigFileError(str(path), str(exc)) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFileError(str(path), f"TOML invalido -- {exc}") from exc


def _sectioned(data: Mapping[str, Any], origin: str) -> dict[str, dict[str, object]]:
    """Validate that a parsed TOML document is a mapping of known sections."""
    out: dict[str, dict[str, object]] = {}
    for key, value in data.items():
        if key not in SECTION_TYPES:
            raise UnknownSettingError(
                key, origin, tuple(difflib.get_close_matches(key, SECTION_TYPES, n=3))
            )
        if not isinstance(value, Mapping):
            raise ConfigError(
                f"A secao '[{key}]' em {origin} deve ser uma tabela, nao {type(value).__name__}"
            )
        out[key] = dict(value)
    return out


def user_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the path of the per-user configuration file."""
    environ = os.environ if env is None else env
    explicit = environ.get("CAISSA_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    return default_data_dir() / USER_CONFIG_FILENAME


def user_file_layer(path: Path | None = None, env: Mapping[str, str] | None = None) -> ConfigLayer:
    """Build the per-user file layer, or an empty layer if the file is absent."""
    environ = os.environ if env is None else env
    if _is_truthy(environ.get("CAISSA_NO_USER_CONFIG", "")):
        return ConfigLayer("user-file", "desabilitado por CAISSA_NO_USER_CONFIG", {}, present=False)
    target = path if path is not None else user_config_path(environ)
    if not target.is_file():
        return ConfigLayer("user-file", str(target), {}, present=False)
    return ConfigLayer("user-file", str(target), _sectioned(_read_toml(target), str(target)))


def _find_project_file(start: Path) -> tuple[Path, dict[str, Any]] | None:
    """Search ``start`` and its ancestors for a project configuration."""
    for directory in (start, *start.parents):
        for filename in PROJECT_CONFIG_FILENAMES:
            candidate = directory / filename
            if candidate.is_file():
                return candidate, _read_toml(candidate)
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            data = _read_toml(pyproject)
            tool = data.get("tool")
            if isinstance(tool, Mapping) and isinstance(tool.get("caissa"), Mapping):
                return pyproject, dict(tool["caissa"])
    return None


def project_file_layer(
    start_dir: Path | None = None, env: Mapping[str, str] | None = None
) -> ConfigLayer:
    """Build the project-local file layer by searching upward from ``start_dir``."""
    environ = os.environ if env is None else env
    if _is_truthy(environ.get("CAISSA_NO_PROJECT_CONFIG", "")):
        return ConfigLayer(
            "project-file", "desabilitado por CAISSA_NO_PROJECT_CONFIG", {}, present=False
        )
    if start_dir is not None:
        start = start_dir
    elif environ.get("CAISSA_PROJECT_DIR"):
        start = Path(environ["CAISSA_PROJECT_DIR"])
    else:
        start = Path.cwd()
    start = start.expanduser().resolve()
    found = _find_project_file(start)
    if found is None:
        return ConfigLayer(
            "project-file", f"nenhum caissa.toml a partir de {start}", {}, present=False
        )
    path, data = found
    return ConfigLayer("project-file", str(path), _sectioned(data, str(path)))


def _iter_env_settings(environ: Mapping[str, str]) -> Iterator[tuple[str, str, str, str]]:
    """Yield ``(section, field, value, variable_name)`` for every settings variable."""
    for name in sorted(environ):
        if not name.startswith(ENV_PREFIX) or name in CONTROL_ENV_VARS:
            continue
        remainder = name[len(ENV_PREFIX) :]
        if ENV_DELIMITER not in remainder:
            valid = ", ".join(f"{ENV_PREFIX}{s.upper()}{ENV_DELIMITER}..." for s in SECTION_TYPES)
            raise UnknownSettingError(
                name,
                "ambiente",
                (f"use {valid}",),
            )
        section_raw, _, field_raw = remainder.partition(ENV_DELIMITER)
        yield section_raw.lower(), field_raw.lower(), environ[name], name


def environment_layer(env: Mapping[str, str] | None = None) -> ConfigLayer:
    """Build the environment layer from ``CAISSA_<SECTION>__<FIELD>`` variables."""
    environ = os.environ if env is None else env
    values: dict[str, dict[str, object]] = {}
    seen: list[str] = []
    for section, fieldname, raw, varname in _iter_env_settings(environ):
        if section not in SECTION_TYPES:
            raise UnknownSettingError(
                varname, "ambiente", tuple(difflib.get_close_matches(section, SECTION_TYPES, n=3))
            )
        values.setdefault(section, {})[fieldname] = raw
        seen.append(varname)
    origin = ", ".join(seen) if seen else f"nenhuma variavel {ENV_PREFIX}*"
    return ConfigLayer("environment", origin, values, present=bool(seen))


# --------------------------------------------------------------------------- #
# Coercion
# --------------------------------------------------------------------------- #


def _coerce_bool(value: object, dotted: str, origin: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    raise ConfigError(
        f"{dotted} (definido em {origin}) deve ser booleano; "
        f"aceito: true/false/1/0/sim/nao (recebido: {value!r})"
    )


def _coerce_int(value: object, dotted: str, origin: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{dotted} (definido em {origin}) deve ser inteiro, nao booleano")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip(), 10)
        except ValueError as exc:
            raise ConfigError(
                f"{dotted} (definido em {origin}) deve ser inteiro (recebido: {value!r})"
            ) from exc
    raise ConfigError(f"{dotted} (definido em {origin}) deve ser inteiro (recebido: {value!r})")


def _coerce_float(value: object, dotted: str, origin: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{dotted} (definido em {origin}) deve ser numerico, nao booleano")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ConfigError(
                f"{dotted} (definido em {origin}) deve ser numerico (recebido: {value!r})"
            ) from exc
    raise ConfigError(f"{dotted} (definido em {origin}) deve ser numerico (recebido: {value!r})")


def _coerce_int_pair(value: object, dotted: str, origin: str) -> tuple[int, int]:
    if isinstance(value, str):
        parts: list[object] = [p for p in value.replace("[", "").replace("]", "").split(",") if p]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise ConfigError(
            f"{dotted} (definido em {origin}) deve ser uma lista de dois inteiros "
            f"(recebido: {value!r})"
        )
    if len(parts) != _INT_PAIR_LENGTH:
        raise ConfigError(
            f"{dotted} (definido em {origin}) deve ter exatamente dois inteiros "
            f"(recebido: {value!r})"
        )
    first = _coerce_int(parts[0], dotted, origin)
    second = _coerce_int(parts[1], dotted, origin)
    return (first, second)


def _coerce_literal(value: object, hint: object, dotted: str, origin: str) -> str:
    """Validate a value against a ``Literal[...]`` annotation."""
    allowed = get_args(hint)
    text = value if isinstance(value, str) else str(value)
    if text not in allowed:
        options = ", ".join(str(a) for a in allowed)
        raise ConfigError(
            f"{dotted} (definido em {origin}) deve ser um de [{options}] (recebido: {value!r})"
        )
    return text


def _coerce_path(value: object, dotted: str, origin: str) -> Path:
    """Convert a value to a :class:`~pathlib.Path`."""
    if isinstance(value, (str, Path)):
        return Path(value)
    raise ConfigError(f"{dotted} (definido em {origin}) deve ser um caminho (recebido: {value!r})")


def _coerce_str(value: object, dotted: str, origin: str) -> str:
    """Accept only genuine strings; a TOML table would happily hand over anything."""
    if isinstance(value, str):
        return value
    raise ConfigError(f"{dotted} (definido em {origin}) deve ser texto (recebido: {value!r})")


_SCALAR_COERCERS: Final[dict[object, Callable[[object, str, str], object]]] = {
    bool: _coerce_bool,
    int: _coerce_int,
    float: _coerce_float,
    str: _coerce_str,
    Path: _coerce_path,
}


def _coerce(value: object, hint: object, dotted: str, origin: str) -> object:
    """Convert a raw layer value to the type declared by the schema."""
    if get_origin(hint) is Literal:
        return _coerce_literal(value, hint, dotted, origin)
    if get_origin(hint) is tuple:
        return _coerce_int_pair(value, dotted, origin)
    scalar = _SCALAR_COERCERS.get(hint)
    if scalar is not None:
        return scalar(value, dotted, origin)
    raise ConfigError(  # pragma: no cover - guards against schema drift
        f"Tipo nao suportado para {dotted}: {hint!r}"
    )


_HINT_CACHE: dict[str, dict[str, object]] = {}


def _section_hints(section: str) -> dict[str, object]:
    """Return (and memoise) the resolved type hints of one schema section."""
    cached = _HINT_CACHE.get(section)
    if cached is None:
        cached = dict(get_type_hints(SECTION_TYPES[section]))
        _HINT_CACHE[section] = cached
    return cached


# --------------------------------------------------------------------------- #
# Merge + build
# --------------------------------------------------------------------------- #


def _merge(layers: list[ConfigLayer]) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Fold layers in order, recording which layer supplied each effective value."""
    merged: dict[str, dict[str, object]] = {}
    provenance: dict[str, str] = {}
    for layer in layers:
        for section, fields in layer.values.items():
            if section not in SECTION_TYPES:
                raise UnknownSettingError(
                    section,
                    layer.origin,
                    tuple(difflib.get_close_matches(section, SECTION_TYPES, n=3)),
                )
            hints = _section_hints(section)
            for name, raw in fields.items():
                dotted = f"{section}.{name}"
                if name not in hints:
                    raise UnknownSettingError(
                        dotted,
                        layer.origin,
                        tuple(f"{section}.{c}" for c in difflib.get_close_matches(name, hints, 3)),
                    )
                merged.setdefault(section, {})[name] = _coerce(
                    raw, hints[name], dotted, layer.origin
                )
                provenance[dotted] = layer.name
    return merged, provenance


def load_config(
    *,
    user_config_file: Path | None = None,
    project_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    overrides: RawConfig | None = None,
    include_user_file: bool = True,
    include_environment: bool = True,
    include_project_file: bool = True,
) -> CaissaConfig:
    """Build a :class:`CaissaConfig` from every enabled layer.

    Args:
        user_config_file: Explicit path to the user file. Defaults to
            ``$CAISSA_CONFIG`` or the platform data directory.
        project_dir: Where to start the upward search for a project file.
            Defaults to ``$CAISSA_PROJECT_DIR`` or the current directory.
        env: Environment mapping to read. Defaults to :data:`os.environ`.
            Passing an explicit mapping is how tests stay hermetic.
        overrides: Highest-precedence values, as ``{section: {field: value}}``.
        include_user_file: Disable the user-file layer.
        include_environment: Disable the environment layer.
        include_project_file: Disable the project-file layer.

    Returns:
        A fully validated, immutable configuration with provenance attached.

    Raises:
        ConfigError: If any layer supplies an unknown key, a value of the wrong
            type, or a value outside the allowed range.
    """
    environ = os.environ if env is None else env
    layers: list[ConfigLayer] = [ConfigLayer("defaults", "schema.py", {})]
    if include_user_file:
        layers.append(user_file_layer(user_config_file, environ))
    if include_environment:
        layers.append(environment_layer(environ))
    if include_project_file:
        layers.append(project_file_layer(project_dir, environ))
    if overrides:
        layers.append(ConfigLayer("overrides", "chamada de load_config()", overrides))

    merged, provenance = _merge(layers)

    sections: dict[str, object] = {}
    for section, cls in SECTION_TYPES.items():
        kwargs = merged.get(section, {})
        try:
            sections[section] = cls(**kwargs)
        except TypeError as exc:  # pragma: no cover - _merge already filters keys
            raise ConfigError(f"Nao foi possivel construir a secao '{section}': {exc}") from exc

    return CaissaConfig(
        runtime=sections["runtime"],  # type: ignore[arg-type]
        cache=sections["cache"],  # type: ignore[arg-type]
        paths=sections["paths"],  # type: ignore[arg-type]
        vision=sections["vision"],  # type: ignore[arg-type]
        llm=sections["llm"],  # type: ignore[arg-type]
        ui=sections["ui"],  # type: ignore[arg-type]
        provenance=provenance,
        sources=tuple(layer.describe() for layer in layers),
    )


# --------------------------------------------------------------------------- #
# Process-wide singleton
# --------------------------------------------------------------------------- #

_LOCK = threading.RLock()


@dataclass
class _ActiveConfig:
    """Holder for the process-wide configuration, so no function needs ``global``."""

    value: CaissaConfig | None = None


_ACTIVE = _ActiveConfig()


def get_config() -> CaissaConfig:
    """Return the process-wide configuration, loading it on first use.

    Thread-safe and idempotent. Subsystems should call this rather than reading
    the environment or files themselves.
    """
    with _LOCK:
        if _ACTIVE.value is None:
            _ACTIVE.value = load_config()
        return _ACTIVE.value


def set_config(config: CaissaConfig) -> None:
    """Install ``config`` as the process-wide configuration."""
    with _LOCK:
        _ACTIVE.value = config


def reset_config() -> None:
    """Drop the cached configuration so the next :func:`get_config` reloads it."""
    with _LOCK:
        _ACTIVE.value = None
