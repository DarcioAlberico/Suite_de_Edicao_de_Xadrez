"""Schema versioning and the upgrade path between versions.

Every serialised document carries a ``schema_version``. When the IR changes
shape, the new version registers a function that rewrites the *previous*
version's payload into the new one, and :meth:`MigrationRegistry.migrate` chains
those functions to bring a document of any past version up to the present.

The rules the registry enforces:

* a document from a **future** version is refused, not guessed at -- silently
  reading half of it would corrupt the user's work;
* a **gap** in the chain is refused with the exact missing step named;
* migrations run in order, one version at a time, so each function only ever
  has to know about the single shape change it introduced.

Migrations operate on raw JSON payloads, deliberately: by the time a document
has been decoded into dataclasses it is too late, because decoding is what would
have failed. The payload vocabulary (:data:`JsonValue`, :data:`JsonObject`) is
defined here for that reason and shared with
:mod:`caissa.core.model.serialize`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_REGISTRY",
    "JsonObject",
    "JsonValue",
    "Migration",
    "MigrationError",
    "MigrationFn",
    "MigrationRegistry",
]

#: Anything ``json.loads`` can produce.
JsonValue = bool | int | float | str | None | list["JsonValue"] | dict[str, "JsonValue"]

#: A JSON object -- the shape of both the envelope and every serialised node.
JsonObject = dict[str, JsonValue]

#: A migration takes the payload of version *n* and returns that of *n + 1*.
MigrationFn = Callable[[JsonObject], JsonObject]

#: Version written by this build. Bump it whenever the on-disk shape changes,
#: and register the matching migration in the same commit.
CURRENT_SCHEMA_VERSION: Final = 1


class MigrationError(ValueError):
    """Raised when a payload cannot be brought to the current schema version."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One registered upgrade step.

    Attributes:
        from_version: Version the step reads.
        to_version: Version it produces; always ``from_version + 1``.
        upgrade: The rewriting function.
        description: What changed, for the migration report.
    """

    from_version: int
    to_version: int
    upgrade: MigrationFn
    description: str = ""


class MigrationRegistry:
    """An ordered chain of schema upgrades.

    The default instance, :data:`DEFAULT_REGISTRY`, is what the serialiser uses.
    Constructing a private registry is how tests -- and any tool that needs to
    read a foreign dialect -- exercise the chain without touching global state.
    """

    __slots__ = ("_current_version", "_steps")

    def __init__(self, current_version: int = CURRENT_SCHEMA_VERSION) -> None:
        """Create an empty registry.

        Args:
            current_version: The version this registry migrates *to*.
        """
        self._current_version = current_version
        self._steps: dict[int, Migration] = {}

    @property
    def current_version(self) -> int:
        """The version every payload is brought up to."""
        return self._current_version

    @property
    def steps(self) -> tuple[Migration, ...]:
        """Every registered step, ordered by source version."""
        return tuple(self._steps[key] for key in sorted(self._steps))

    def add(self, migration: Migration) -> None:
        """Register an upgrade step.

        Args:
            migration: The step to register.

        Raises:
            MigrationError: If the step does not advance exactly one version,
                targets a version beyond :attr:`current_version`, or duplicates
                an existing step.
        """
        if migration.to_version != migration.from_version + 1:
            msg = (
                f"migracao deve avancar exatamente uma versao; recebido "
                f"{migration.from_version} -> {migration.to_version}"
            )
            raise MigrationError(msg)
        if migration.to_version > self._current_version:
            msg = (
                f"migracao para a versao {migration.to_version} ultrapassa a versao "
                f"corrente {self._current_version}"
            )
            raise MigrationError(msg)
        if migration.from_version in self._steps:
            msg = f"ja existe migracao a partir da versao {migration.from_version}"
            raise MigrationError(msg)
        self._steps[migration.from_version] = migration

    def register(
        self,
        from_version: int,
        *,
        description: str = "",
    ) -> Callable[[MigrationFn], MigrationFn]:
        """Decorator form of :meth:`add`.

        Args:
            from_version: Version the decorated function reads.
            description: What the step changes.

        Returns:
            A decorator that registers the function and returns it unchanged.
        """

        def decorate(function: MigrationFn) -> MigrationFn:
            self.add(
                Migration(
                    from_version=from_version,
                    to_version=from_version + 1,
                    upgrade=function,
                    description=description,
                )
            )
            return function

        return decorate

    def plan(self, from_version: int) -> tuple[Migration, ...]:
        """Return the steps needed to bring a payload up to date.

        Args:
            from_version: Version of the payload on hand.

        Returns:
            The steps to apply, in order. Empty when the payload is already
            current.

        Raises:
            MigrationError: If the version is from the future, is not a
                positive integer, or the chain has a gap.
        """
        if from_version < 1:
            msg = f"schema_version invalida: {from_version}"
            raise MigrationError(msg)
        if from_version > self._current_version:
            msg = (
                f"documento gravado com schema_version {from_version}, mais nova que a "
                f"suportada ({self._current_version}). Atualize o Caissa Studio para abri-lo."
            )
            raise MigrationError(msg)
        chain: list[Migration] = []
        version = from_version
        while version < self._current_version:
            step = self._steps.get(version)
            if step is None:
                msg = (
                    f"falta migracao da versao {version} para {version + 1}; "
                    f"nao e possivel atualizar um documento da versao {from_version}."
                )
                raise MigrationError(msg)
            chain.append(step)
            version = step.to_version
        return tuple(chain)

    def migrate(self, payload: JsonObject, from_version: int) -> tuple[JsonObject, tuple[str, ...]]:
        """Bring a payload up to :attr:`current_version`.

        Args:
            payload: The raw document payload, as loaded from JSON.
            from_version: Version it was written with.

        Returns:
            The upgraded payload and a description of each step applied, for
            the import report.

        Raises:
            MigrationError: If the chain cannot be built, or a step fails.
        """
        applied: list[str] = []
        current = payload
        for step in self.plan(from_version):
            try:
                current = step.upgrade(current)
            except Exception as exc:
                msg = f"falha ao migrar da versao {step.from_version} para {step.to_version}: {exc}"
                raise MigrationError(msg) from exc
            label = step.description or f"v{step.from_version} -> v{step.to_version}"
            applied.append(label)
        return current, tuple(applied)


#: The registry the serialiser uses. Version 1 is the first published shape, so
#: it has no steps yet; the machinery is exercised by the test suite against
#: private registries, which is also how any future dialect reader will use it.
DEFAULT_REGISTRY: Final = MigrationRegistry(CURRENT_SCHEMA_VERSION)
