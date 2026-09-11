"""The acceptance gate: what survives an export and what was declared.

SPEC section 11.3 sets the floor at 99 % of nodes preserved. SPEC section 5.2
says nothing may be dropped silently. This module tests both, per format, over
the same adversarial corpus the IR tests use -- a document that sets every run
property to a value nobody would choose on purpose, precisely so that an
exporter cannot pass by ignoring the hard cases.
"""

from __future__ import annotations

import pytest
from corpus import CORPUS_SEED, FORMATS, MARKUP_FORMATS, SIDECAR_FORMATS

from caissa.core.model import Document
from caissa.export.fidelity import (
    MINIMUM_FIDELITY,
    FidelityReport,
    export_then_reimport,
    measure,
)


@pytest.fixture(scope="module")
def reports(tmp_path_factory: pytest.TempPathFactory) -> dict[str, FidelityReport]:
    """Measure the corpus once per format and share the result.

    Args:
        tmp_path_factory: Where the exports are written.

    Returns:
        A report per format.
    """
    from generators import NodeFactory

    document = NodeFactory(CORPUS_SEED).document(min_nodes=200)
    root = tmp_path_factory.mktemp("fidelidade")
    return {
        name: export_then_reimport(document, name, directory=root / name)
        for name in FORMATS
    }


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_format_round_trips_without_crashing(
    reports: dict[str, FidelityReport], format_name: str
) -> None:
    """Every format writes a file and reads it back into a document."""
    report = reports[format_name]
    assert report.node_count > 100, "o corpus ficou pequeno demais para medir"
    assert report.result is not None
    assert report.result.path.exists()


@pytest.mark.parametrize("format_name", FORMATS)
def test_no_silent_loss_beyond_the_gate(
    reports: dict[str, FidelityReport], format_name: str
) -> None:
    """At least 99 % of nodes survive with nothing lost that was not declared.

    A node that lost only what the profile said the format cannot carry counts
    as preserved: the user was told. A node that lost anything else does not,
    however small the loss -- that is the cardinal sin this front exists to
    prevent, and it fails the build.
    """
    report = reports[format_name]
    assert report.declared_fidelity >= MINIMUM_FIDELITY, (
        f"semente {CORPUS_SEED:#x}: {report}"
    )


@pytest.mark.parametrize("format_name", FORMATS)
def test_the_report_names_what_it_lost(
    reports: dict[str, FidelityReport], format_name: str
) -> None:
    """Every declared loss carries a reason a user can read."""
    report = reports[format_name]
    for loss in report.losses:
        if loss.is_declared:
            assert loss.reason, f"perda declarada sem motivo: {loss}"


@pytest.mark.parametrize("format_name", MARKUP_FORMATS)
def test_markup_formats_are_measured_through_their_own_reader(
    reports: dict[str, FidelityReport], format_name: str
) -> None:
    """A number that measures the writer is labelled as such.

    PDF and LaTeX recover the IR from a sidecar, which measures serialisation
    and not the writer. The distinction has to survive into the report or it
    will be quoted as if it were evidence.
    """
    assert reports[format_name].method == "markup"


@pytest.mark.parametrize("format_name", SIDECAR_FORMATS)
def test_sidecar_formats_say_so(
    reports: dict[str, FidelityReport], format_name: str
) -> None:
    """PDF and LaTeX are honest about measuring their sidecar."""
    assert reports[format_name].method == "sidecar"


def test_identical_documents_measure_as_perfect(small: Document) -> None:
    """A document compared with itself has nothing to report."""
    report = measure(small, small, "html")
    assert report.fidelity == 1.0
    assert report.declared_fidelity == 1.0
    assert not report.losses
    assert not report.missing
    assert "Nenhuma perda silenciosa" in report.summary()


def test_a_dropped_node_is_reported_as_missing(small: Document) -> None:
    """Removing a block is seen, and is not called a property loss."""
    from dataclasses import replace

    trimmed = replace(small, body=small.body[:-1])
    report = measure(small, trimmed, "html")
    assert report.missing, "um bloco removido tem de aparecer como ausente"
    assert report.matched < report.node_count


def test_a_changed_field_is_attributed_to_the_right_node(small: Document) -> None:
    """A field that changed is reported with its node and its path."""
    from dataclasses import replace

    from caissa.core.model import DocumentMetadata

    other = replace(small, metadata=DocumentMetadata(title="Outro"))
    report = measure(small, other, "html")
    losses = [loss for loss in report.losses if loss.field == "metadata"]
    assert losses
    assert losses[0].node_type == "document"
    assert losses[0].path == "$"


def test_by_node_type_counts_nodes_and_not_losses(
    reports: dict[str, FidelityReport]
) -> None:
    """A node that lost three fields is one damaged node, not three."""
    report = reports["html"]
    for tag, (damaged, total) in report.by_node_type().items():
        assert damaged <= total, f"{tag}: {damaged} danificados de {total}"


def test_the_summary_is_in_portuguese(reports: dict[str, FidelityReport]) -> None:
    """The user-facing summary is written for the user."""
    text = reports["html"].summary()
    assert "fidelidade" in text
    assert "nos" in text


# --------------------------------------------------------------------------- #
# Attribution: naming the node that caused a loss, and not one that did not
# --------------------------------------------------------------------------- #
# OOXML is flat. There is no emphasis element, only a run with ``w:i``, so the
# wrapper genuinely disappears and its meaning lands on the runs it held. The
# fix for that is *attribution*, not pretending the wrapper survived -- and the
# line between the two is what these tests hold. Moving the wrapper's identity
# onto the run would report a node that changed type; leaving the run's gained
# property unexplained would report a silent loss that nobody could act on.
def test_a_flattened_wrapper_answers_for_what_it_pushed_onto_its_runs() -> None:
    """A property the run never set cannot have been lost by the run.

    The value arrived from an ancestor the format declared it flattens, so the
    loss is reported against that declaration -- with its reason -- instead of
    counting against the gate.
    """
    from dataclasses import replace

    from caissa.core.model import (
        Document,
        DocumentMetadata,
        Emphasis,
        Paragraph,
        RunProps,
        Text,
    )

    inner = Text(content="ponte")
    document = Document(
        metadata=DocumentMetadata(title="Enfase"),
        body=(Paragraph(content=(Emphasis(content=(inner,)),)),),
    )
    # What DOCX really gives back: the wrapper is gone and the run is italic.
    flattened = Document(
        id=document.id,
        metadata=document.metadata,
        body=(
            replace(
                document.body[0],
                content=(replace(inner, props=RunProps(italic=True)),),
            ),
        ),
    )
    report = measure(document, flattened, "docx")
    assert not report.silent_losses, report
    italics = [loss for loss in report.losses if loss.field == "props.italic"]
    assert italics, "a propriedade que apareceu nao foi reportada"
    assert italics[0].node_type == "text"
    assert "w:i" in italics[0].reason


def test_a_run_that_lost_what_it_did_set_is_still_a_silent_loss() -> None:
    """The attribution is for values that *arrived*, never for values that left.

    A run that asked for italic and came back without it lost something, and no
    ancestor explains that. This is the half of the rule that keeps it from
    being a way to pass the gate.
    """
    from dataclasses import replace

    from caissa.core.model import (
        Document,
        DocumentMetadata,
        Emphasis,
        Paragraph,
        RunProps,
        Text,
    )

    inner = Text(content="ponte", props=RunProps(italic=True, hidden=True))
    document = Document(
        metadata=DocumentMetadata(title="Enfase"),
        body=(Paragraph(content=(Emphasis(content=(inner,)),)),),
    )
    damaged = Document(
        id=document.id,
        metadata=document.metadata,
        body=(
            replace(
                document.body[0],
                content=(replace(inner, props=RunProps(italic=True)),),
            ),
        ),
    )
    report = measure(document, damaged, "docx")
    silent = {loss.field for loss in report.silent_losses}
    assert "props.hidden" in silent, report


def test_a_container_is_not_blamed_for_a_child_the_format_declared() -> None:
    """A paragraph whose anchor became a bookmark did not lose its content.

    The anchor's own profile entry already says the anchor stops being a node.
    Counting the parent as damaged as well reports the same declared
    substitution twice, under a node whose profile says "full".
    """
    from dataclasses import replace

    from caissa.core.model import Anchor, Document, DocumentMetadata, Paragraph, Text

    kept = Text(content="ponte")
    paragraph = Paragraph(content=(Anchor(name="lucena"), kept))
    document = Document(
        metadata=DocumentMetadata(title="Ancora"), body=(paragraph,)
    )
    flattened = Document(
        id=document.id,
        metadata=document.metadata,
        body=(replace(paragraph, content=(kept,)),),
    )
    report = measure(document, flattened, "docx")
    assert not report.silent_losses, report
    losses = [loss for loss in report.losses if loss.field == "content"]
    assert losses
    assert "bookmark" in losses[0].reason


def test_a_container_that_lost_an_undeclared_child_stays_silent() -> None:
    """A dropped child the format promised to keep is still a defect.

    The container rule asks what happened to the children. When the answer is
    "nothing was declared about them", the parent's changed content is not
    explained and counts against the gate.
    """
    from dataclasses import replace

    from caissa.core.model import Document, DocumentMetadata, Paragraph, Text

    kept = Text(content="ponte")
    paragraph = Paragraph(content=(Text(content="a "), kept))
    document = Document(metadata=DocumentMetadata(title="Texto"), body=(paragraph,))
    damaged = Document(
        id=document.id,
        metadata=document.metadata,
        body=(replace(paragraph, content=(kept,)),),
    )
    report = measure(document, damaged, "docx")
    assert report.silently_damaged, "a perda de um no pleno passou despercebida"


def test_a_container_whose_children_were_reordered_is_not_explained() -> None:
    """Order is content. A list that came back shuffled lost something.

    The rule only forgives children that *left*, and only when their own entry
    said they would; the ones that stayed have to be where they were.
    """
    from dataclasses import replace

    from caissa.core.model import Document, DocumentMetadata, Paragraph, Text

    first = Text(content="um")
    second = Text(content="dois")
    paragraph = Paragraph(content=(first, second))
    document = Document(metadata=DocumentMetadata(title="Ordem"), body=(paragraph,))
    shuffled = Document(
        id=document.id,
        metadata=document.metadata,
        body=(replace(paragraph, content=(second, first)),),
    )
    report = measure(document, shuffled, "docx")
    assert report.silently_damaged, "uma troca de ordem passou por declarada"


def test_every_docx_declaration_actually_reaches_the_export_report(
    reports: dict[str, FidelityReport]
) -> None:
    """A profile entry that never fires is a promise nobody keeps.

    The two numbers only work together if declaring a loss also *tells* the
    user: an entry that classifies a difference as declared while no warning
    names it would move the gate without moving the report.
    """
    report = reports["docx"]
    assert not report.unreported, "\n".join(str(loss) for loss in report.unreported[:10])
