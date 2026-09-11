"""The node base class shared by every addressable element of the Document IR.

Three invariants hold for every type in this package and are relied upon by the
serialiser, the visitor, the validator and the differ:

1. **Everything is a frozen, slotted, keyword-only dataclass.** Immutability
   makes the tree safe to share across threads (the UI paints while a worker
   transforms), ``slots`` keeps a hundred-thousand-node book affordable in RAM,
   and ``kw_only`` means a forty-field ``RunProps`` never depends on argument
   order.
2. **Every dataclass carries a stable tag** (see
   :mod:`caissa.core.model.registry`).
3. **Every *node* owns an identity and may carry provenance.** Identity is what
   makes round-trip fidelity measurable (SPEC section 11.3): ``semantic_diff``
   pairs nodes across two documents by id, so an exporter/importer pair that
   preserves ids can be *proven* not to have lost anything.

Value objects -- ``RunProps``, ``Color``, ``Measure`` -- are registered
dataclasses too, but do not derive from :class:`IRNode`: they are properties
*of* a node rather than nodes in their own right, and giving them identity would
make the differ report noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from caissa.core.model.ids import ULID, new_ulid
from caissa.core.model.provenance import Provenance
from caissa.core.model.registry import (
    IRTypeError,
    class_for_tag,
    ir_node,
    is_ir_dataclass,
    iter_registered,
    tag_for_class,
    tag_of,
)

__all__ = [
    "IRNode",
    "IRTypeError",
    "class_for_tag",
    "ir_node",
    "is_ir_dataclass",
    "iter_registered",
    "tag_for_class",
    "tag_of",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class IRNode:
    """Base class of every addressable node in the Document IR.

    Attributes:
        id: Stable identity, minted on construction unless supplied.
        provenance: Where this node came from and how sure the reader was.
            ``None`` for authored content that was never read from anything.
    """

    id: ULID = field(default_factory=new_ulid)
    provenance: Provenance | None = None

    @property
    def node_type(self) -> str:
        """The stable serialisation tag of this node's class."""
        return tag_of(self)
