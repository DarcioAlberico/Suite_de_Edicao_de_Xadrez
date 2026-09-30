"""A leitura do projeto do editor: o XHTML de volta ao IR (spec S3; passo H5).

`ler_legivel` lê um arquivo do projeto — o perfil legível (o contrato, `docs/MARKUP_CAISSA.md`)
ou o legado do perfil de máquina (`data-ir`), que continua lido — com o mapa da proveniência que o
`proveniencia.json` guarda. `mapa_para_json` e `mapa_de_json` levam o mapa ao arquivo e de volta
(o formato 2 da spec S2: os blocos e os diagramas pelo `id` do livro, e os fólios das páginas), e
`nomes_de_estilo` dá os nomes que as classes `cb-style-<slug>` voltam a ser.

Sem Qt (spec R1.11): a pintura mora em `caissa.ui`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from typing import Any

from caissa.core.model import (
    DiagramSource,
    Document,
    Provenance,
    RecognitionResult,
)
from caissa.core.model.ids import ULID
from caissa.core.model.serialize import decode_value, encode_value
from caissa.core.model.visitor import walk
from caissa.export.legivel import (
    Capitulo,
    MapaDaProveniencia,
    RegistroDoMapa,
    ler_capitulo,
)

__all__ = [
    "FORMATO_DO_MAPA",
    "e_legado",
    "ler_legivel",
    "mapa_de_json",
    "mapa_para_json",
    "nomes_de_estilo",
]

FORMATO_DO_MAPA = 2
"""O `formato` do `proveniencia.json` (spec S2)."""

_DATA_IR = re.compile(r"\sdata-ir(?:-id)?\s*=")


def e_legado(texto: str) -> bool:
    """Se o arquivo é do perfil de máquina (`data-ir`/`data-ir-id` nos elementos)."""
    return _DATA_IR.search(texto) is not None


def ler_legivel(texto: str, *, mapa: MapaDaProveniencia | None = None,
                estilos: Iterable[str] = ()) -> Capitulo:
    """O arquivo do projeto de volta ao IR.

    O perfil legível pelo contrato, com o mapa da proveniência; o legado do perfil de máquina
    pelo leitor dele (`read_html_text`), que o `data-ir` guia.

    Args:
        texto: O XHTML.
        mapa: O mapa do `proveniencia.json`; sem ele, os `id` e os marcadores ficam como vieram.
        estilos: Os nomes dos estilos do livro (`nomes_de_estilo`).
    """
    if not e_legado(texto):
        return ler_capitulo(texto, mapa=mapa, estilos=estilos)
    from caissa.export.html import read_html_text

    documento = read_html_text(texto)
    folhas: list[str] = []
    try:
        raiz = ET.fromstring(re.sub(r"^<!DOCTYPE[^>]*>\s*", "", texto.strip(),  # noqa: S314
                                    flags=re.IGNORECASE).encode("utf-8"))
        folhas = [e.get("href") or "" for e in raiz.iter("{http://www.w3.org/1999/xhtml}link")
                  if e.get("rel") == "stylesheet"]
    except ET.ParseError:
        pass
    return Capitulo(blocos=documento.body, titulo=documento.metadata.title or "",
                    folhas=tuple(folhas), idioma=documento.metadata.language or "pt-BR")


def mapa_para_json(mapa: MapaDaProveniencia) -> dict[str, Any]:
    """O mapa no formato do `proveniencia.json` (spec S2, formato 2).

    Cada registro leva o `ir_id`, a origem do `id` e a proveniência inteira, serializada pelo IR;
    o do diagrama, também a origem da imagem, o reconhecimento e a conferência humana.
    """
    blocos: dict[str, Any] = {}
    diagramas: dict[str, Any] = {}
    for ident, registro in mapa.nos.items():
        dados: dict[str, Any] = {"ir_id": str(registro.ir_id), "origem": registro.origem}
        if registro.proveniencia is not None:
            dados["proveniencia"] = encode_value(registro.proveniencia)
        if registro.fonte is not None or registro.reconhecimento is not None:
            dados["fonte"] = encode_value(registro.fonte or DiagramSource())
            dados["reconhecimento"] = encode_value(registro.reconhecimento or RecognitionResult())
            dados["conferido"] = registro.conferido
            diagramas[ident] = dados
        else:
            blocos[ident] = dados
    return {"formato": FORMATO_DO_MAPA,
            "folios": {str(pagina): folio for pagina, folio in sorted(mapa.folios.items())},
            "blocos": blocos, "diagramas": diagramas}


def mapa_de_json(dados: Mapping[str, Any]) -> MapaDaProveniencia:
    """O mapa de volta do `proveniencia.json`.

    Raises:
        ValueError: O formato não é o 2.
    """
    if dados.get("formato") != FORMATO_DO_MAPA:
        raise ValueError(f"proveniencia.json no formato {dados.get('formato')!r}; "
                         f"este leitor lê o {FORMATO_DO_MAPA}")
    mapa = MapaDaProveniencia(folios={int(p): str(f) for p, f in (dados.get("folios") or {})
                                      .items()})
    for secao, diagrama in (("blocos", False), ("diagramas", True)):
        for ident, registro in (dados.get(secao) or {}).items():
            proveniencia = registro.get("proveniencia")
            mapa.nos[ident] = RegistroDoMapa(
                ir_id=ULID.from_string(registro["ir_id"]), origem=registro["origem"],
                proveniencia=decode_value(proveniencia, Provenance)
                if proveniencia is not None else None,
                fonte=decode_value(registro["fonte"], DiagramSource) if diagrama else None,
                reconhecimento=decode_value(registro["reconhecimento"], RecognitionResult)
                if diagrama else None,
                conferido=bool(registro.get("conferido", False)))
    return mapa


def nomes_de_estilo(documento: Document) -> tuple[str, ...]:
    """Os nomes que as classes `cb-style-<slug>` voltam a ser.

    Os estilos da folha do documento e os que os nós usam (o parágrafo, a corrida, a tabela e o
    diagrama), na ordem em que aparecem.
    """
    folha = documento.styles
    nomes = [s.name for grupo in (folha.paragraph_styles, folha.character_styles,
                                  folha.table_styles, folha.list_styles, folha.diagram_styles)
             for s in grupo]
    for _, no in walk(documento):
        for campo in ("props", "run_props"):
            estilo = getattr(getattr(no, campo, None), "style", None)
            if isinstance(estilo, str):
                nomes.append(estilo)
        estilo = getattr(no, "style", None)
        if isinstance(estilo, str):
            nomes.append(estilo)
        elif isinstance(getattr(estilo, "name", None), str):
            nomes.append(estilo.name)
    return tuple(dict.fromkeys(n for n in nomes if n))
