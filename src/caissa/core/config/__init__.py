"""Layered configuration for Caissa Studio.

Typical use::

    from caissa.core.config import get_config

    budget = get_config().runtime.vram_budget_bytes

See :mod:`caissa.core.config.schema` for the justification of the
dataclasses+``tomllib`` design and :mod:`caissa.core.config.loader` for the
layer precedence rules.
"""

from __future__ import annotations

from caissa.core.config.errors import ConfigError, ConfigFileError, UnknownSettingError
from caissa.core.config.loader import (
    CONTROL_ENV_VARS,
    ENV_PREFIX,
    ConfigLayer,
    environment_layer,
    get_config,
    load_config,
    project_file_layer,
    reset_config,
    set_config,
    user_config_path,
    user_file_layer,
)
from caissa.core.config.schema import (
    APP_NAME,
    CacheConfig,
    CaissaConfig,
    DevicePreference,
    LlmConfig,
    PathsConfig,
    RuntimeConfig,
    ThemePreference,
    UiConfig,
    VisionConfig,
    default_cache_dir,
    default_data_dir,
    default_log_dir,
    default_models_dir,
)

__all__ = [
    "APP_NAME",
    "CONTROL_ENV_VARS",
    "ENV_PREFIX",
    "CacheConfig",
    "CaissaConfig",
    "ConfigError",
    "ConfigFileError",
    "ConfigLayer",
    "DevicePreference",
    "LlmConfig",
    "PathsConfig",
    "RuntimeConfig",
    "ThemePreference",
    "UiConfig",
    "UnknownSettingError",
    "VisionConfig",
    "default_cache_dir",
    "default_data_dir",
    "default_log_dir",
    "default_models_dir",
    "environment_layer",
    "get_config",
    "load_config",
    "project_file_layer",
    "reset_config",
    "set_config",
    "user_config_path",
    "user_file_layer",
]
