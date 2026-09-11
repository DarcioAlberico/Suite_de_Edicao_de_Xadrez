"""Configuration error types.

Kept in a leaf module so that :mod:`caissa.core.config.schema` and
:mod:`caissa.core.config.loader` can both import it without a cycle.
"""

from __future__ import annotations

__all__ = ["ConfigError", "ConfigFileError", "UnknownSettingError"]


class ConfigError(Exception):
    """Raised when a configuration value is missing, malformed or out of range.

    Messages are written for the end user (Brazilian Portuguese) and always name
    the offending dotted key, because the most common cause is a typo in a
    ``caissa.toml`` or an environment variable.
    """


class ConfigFileError(ConfigError):
    """Raised when a configuration file exists but cannot be read or parsed."""

    def __init__(self, path: str, reason: str) -> None:
        """Store the offending path and build a user-facing message."""
        self.path = path
        self.reason = reason
        super().__init__(f"Nao foi possivel ler o arquivo de configuracao {path}: {reason}")


class UnknownSettingError(ConfigError):
    """Raised when a layer supplies a key that does not exist in the schema."""

    def __init__(self, dotted_key: str, origin: str, suggestions: tuple[str, ...] = ()) -> None:
        """Store the offending key plus a list of near-miss valid keys."""
        self.dotted_key = dotted_key
        self.origin = origin
        self.suggestions = suggestions
        message = f"Opcao desconhecida '{dotted_key}' definida em {origin}"
        if suggestions:
            message += f". Voce quis dizer: {', '.join(suggestions)}?"
        super().__init__(message)
