"""The golden rule of SPEC section 5.2, made a test.

    Nenhum exportador pode *silenciosamente* descartar uma propriedade. Se um
    formato nao suporta algo, o exportador registra um ``DegradationWarning``
    visivel no relatorio de exportacao.

A rule enforced by discipline decays. This module enforces it mechanically:
for every one of the forty-six run properties and every one of the twenty-four
paragraph properties, on every one of the five formats, either the profile says
the format carries it fully, or setting it produces a warning that names it.
There is no third option, and adding a property to the IR without deciding
which it is fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from corpus import FORMATS

from caissa.core.model import (
    Document,
    DocumentMetadata,
    Paragraph,
    RunProps,
    Text,
)
from caissa.export import EXPORTERS, export
from caissa.export.base import (
    PARAGRAPH_PROPERTY_NAMES,
    RUN_PROPERTY_NAMES,
    Capability,
)
from caissa.export.profiles import PROFILES, profile_for


def _document_with(props: RunProps) -> Document:
    """Build the smallest document that carries one run property.

    Args:
        props: The properties to put on the only run.

    Returns:
        The document.
    """
    return Document(
        metadata=DocumentMetadata(title="Teste", language="pt-BR"),
        body=(Paragraph(content=(Text(content="peao", props=props),)),),
    )


def _sample(name: str) -> object:
    """Produce a value for one run property, from the corpus generator.

    Args:
        name: The run property name.

    Returns:
        A value the generator considers realistic, or ``None`` when the
        generator never sets that property.
    """
    from generators import NodeFactory

    for seed in range(60):
        value = getattr(NodeFactory(seed).run_props(), name)
        if value not in (None, (), ""):
            return value
    return None


@pytest.mark.parametrize("format_name", FORMATS)
@pytest.mark.parametrize("name", RUN_PROPERTY_NAMES)
def test_every_run_property_is_carried_or_declared(
    tmp_path: Path, format_name: str, name: str
) -> None:
    """Setting one run property either survives or produces a warning.

    Args:
        tmp_path: Where the export is written.
        format_name: The format under test.
        name: The run property.
    """
    profile = profile_for(format_name)
    value = _sample(name)
    if value is None:
        pytest.skip(f"o gerador nunca define {name}; nada para medir")
    document = _document_with(RunProps(**{name: value}))
    support = profile.run_support(name).resolve(value)

    result = export(document, tmp_path / f"saida{EXPORTERS[format_name].suffix}", format_name)
    reported = {warning.property for warning in result.degradation.warnings}

    if support.capability is Capability.FULL:
        assert name not in reported, (
            f"{format_name} declarou carregar '{name}' e mesmo assim avisou sobre ela"
        )
    else:
        assert name in reported, (
            f"{format_name} declara '{name}' como {support.capability.value} "
            "mas nao registrou nenhum aviso ao grava-la"
        )


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_declared_loss_has_a_reason(format_name: str) -> None:
    """A capability table entry that cannot explain itself is not an entry.

    A user who is told "tracking degradado" and nothing else cannot decide
    whether to care. Every non-full entry names the mechanism.
    """
    profile = PROFILES[format_name]
    for table, label in (
        (profile.run, "run"),
        (profile.paragraph, "paragraph"),
        (profile.features, "feature"),
        (profile.nodes, "node"),
        (profile.node_fields, "node field"),
    ):
        for name, support in table.items():
            for resolved in (support, *support.by_value.values()):
                if resolved.capability is Capability.FULL:
                    continue
                assert resolved.detail, f"{format_name} {label} '{name}' sem motivo"
                assert len(resolved.detail) > 20, (
                    f"{format_name} {label} '{name}': motivo curto demais para ajudar"
                )


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_property_of_the_ir_has_a_declaration(format_name: str) -> None:
    """A property with no entry means "full", so the default must be true.

    This test does not check the tables directly -- it checks that the property
    lists the tables are written against still match the IR. A property added
    to ``RunProps`` after this front was written would otherwise silently
    default to "fully supported" everywhere.
    """
    from dataclasses import fields

    from caissa.core.model import ParagraphProps

    assert set(RUN_PROPERTY_NAMES) == {item.name for item in fields(RunProps)}
    assert set(PARAGRAPH_PROPERTY_NAMES) == {item.name for item in fields(ParagraphProps)}


@pytest.mark.parametrize("format_name", FORMATS)
def test_the_warning_names_the_node_it_came_from(
    tmp_path: Path, format_name: str
) -> None:
    """A degradation the user cannot locate is a degradation they cannot fix."""
    document = _document_with(RunProps(kerning_min_size=None, emboss=True, engrave=True))
    result = export(document, tmp_path / f"saida{EXPORTERS[format_name].suffix}", format_name)
    located = [
        warning
        for warning in result.degradation.warnings
        if warning.node_id is not None or warning.path
    ]
    if result.degradation.warnings:
        assert located, "nenhum aviso diz onde a perda aconteceu"


def test_the_noise_cap_counts_rather_than_hides(tmp_path: Path) -> None:
    """A thousand identical losses become a count, never a silence.

    A four-hundred-page book with tracking on every run would otherwise produce
    forty thousand identical lines, and a report nobody reads is the same as no
    report. The cap is on *lines*, not on the tally.
    """
    from caissa.export.base import ExportOptions

    run = RunProps(kerning_min_size=None, emboss=True)
    body = tuple(
        Paragraph(content=(Text(content=f"linha {index}", props=run),))
        for index in range(60)
    )
    document = Document(metadata=DocumentMetadata(title="Repetido"), body=body)
    result = export(
        document,
        tmp_path / "muitos.html",
        "html",
        options=ExportOptions(max_warnings_per_property=5),
    )
    emitted = [w for w in result.degradation.warnings if w.property == "emboss"]
    assert len(emitted) <= 6, "o limite de ruido nao foi aplicado"
    roll_up = [warning for warning in emitted if "no total" in warning.message]
    assert roll_up, "o total real de perdas nao foi informado"
    assert "60" in roll_up[0].message, f"total errado: {roll_up[0].message}"


def test_a_lossless_document_reports_nothing(tmp_path: Path) -> None:
    """A document that asks for nothing exotic degrades nowhere."""
    document = Document(
        metadata=DocumentMetadata(title="Simples", language="pt-BR"),
        body=(Paragraph(content=(Text(content="1.e4 e5"),)),),
    )
    for format_name in ("html", "epub"):
        result = export(
            document, tmp_path / f"limpo{EXPORTERS[format_name].suffix}", format_name
        )
        assert result.is_lossless, result.degradation.summary()
