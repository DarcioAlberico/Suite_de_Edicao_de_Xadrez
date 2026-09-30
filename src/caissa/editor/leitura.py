"""A leitura do projeto do editor: o XHTML de volta ao IR (spec S3; passo H5).

`ler_legivel` lê um arquivo do projeto — o perfil legível (o contrato, `docs/MARKUP_CAISSA.md`)
ou o legado do perfil de máquina (`data-ir`), que continua lido — com o mapa da proveniência que o
`proveniencia.json` guarda. `mapa_para_json` e `mapa_de_json` levam o mapa ao arquivo e de volta
(o formato 2 da spec S2: os blocos e os diagramas pelo `id` do livro, com o fólio, as dúvidas, a
revisão e as decisões; os fólios das páginas; e o dado da máquina dos nós sem `id`, com o lugar
de cada um), `conferir_mapa` prova que todo registro acha o lugar dele no IR relido, e
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
from caissa.core.model.base import tag_of
from caissa.core.model.ids import ULID
from caissa.core.model.serialize import decode_value, encode_value
from caissa.core.model.visitor import walk
from caissa.export.legivel import (
    Capitulo,
    Duvida,
    MapaDaProveniencia,
    RegistroDoMapa,
    RegistroSemId,
    ler_capitulo,
    texto_plano,
)

__all__ = [
    "FORMATO_DO_MAPA",
    "conferir_mapa",
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


def _valor(valor: Any) -> Any:
    return None if valor is None else encode_value(valor)


def _sem_id_para_json(registro: RegistroSemId) -> dict[str, Any]:
    dados: dict[str, Any] = {"caminho": [list(passo) for passo in registro.caminho],
                             "tipo": registro.tipo,
                             "proveniencia": _valor(registro.proveniencia)}
    if registro.campo is not None:
        dados.update(campo=registro.campo, ini=registro.ini, fim=registro.fim,
                     texto_sha=registro.texto_sha, duvida=registro.duvida)
    if registro.fonte is not None or registro.reconhecimento is not None:
        dados.update(fonte=_valor(registro.fonte), reconhecimento=_valor(registro.reconhecimento),
                     conferido=registro.conferido)
    return dados


def _sem_id_de_json(dados: Mapping[str, Any]) -> RegistroSemId:
    proveniencia = dados.get("proveniencia")
    fonte, reconhecimento = dados.get("fonte"), dados.get("reconhecimento")
    return RegistroSemId(
        caminho=tuple((campo, int(indice)) for campo, indice in dados["caminho"]),
        tipo=dados["tipo"],
        proveniencia=decode_value(proveniencia, Provenance) if proveniencia is not None else None,
        campo=dados.get("campo"), ini=dados.get("ini"), fim=dados.get("fim"),
        texto_sha=dados.get("texto_sha"), duvida=bool(dados.get("duvida", False)),
        fonte=decode_value(fonte, DiagramSource) if fonte is not None else None,
        reconhecimento=decode_value(reconhecimento, RecognitionResult)
        if reconhecimento is not None else None,
        conferido=bool(dados.get("conferido", False)))


def _folio(registro: RegistroDoMapa, folios: Mapping[int, str]) -> str | None:
    pagina = getattr(registro.proveniencia, "page_index", None)
    return folios.get(int(pagina) + 1) if pagina is not None else None


def mapa_para_json(mapa: MapaDaProveniencia) -> dict[str, Any]:
    """O mapa no formato do `proveniencia.json` (spec S2, formato 2).

    Cada bloco com `id` leva o `ir_id`, a origem do `id`, o fólio da página dele, a proveniência
    inteira (serializada pelo IR), as dúvidas por trecho (a N3), a revisão e os nós de dentro dele
    que não têm `id` (`nos`, com o lugar de cada um); o diagrama leva também a origem da imagem, o
    reconhecimento, a conferência humana e as decisões. A revisão e as decisões ficam vazias até
    o serviço único de decisões (H7) as preencher. O dado da máquina dos nós sem dono com `id` vai
    em `capitulo`.
    """
    blocos: dict[str, Any] = {}
    diagramas: dict[str, Any] = {}
    for ident, registro in mapa.nos.items():
        dados: dict[str, Any] = {"ir_id": str(registro.ir_id), "origem": registro.origem,
                                 "folio": _folio(registro, mapa.folios),
                                 "proveniencia": _valor(registro.proveniencia),
                                 "duvidas": [{"ini": d.ini, "fim": d.fim,
                                              "proveniencia": encode_value(d.proveniencia),
                                              "alternativas": list(d.alternativas),
                                              "texto_sha": d.texto_sha}
                                             for d in registro.duvidas],
                                 "nos": [_sem_id_para_json(r) for r in mapa.sem_id.get(ident, [])]}
        if registro.fonte is not None or registro.reconhecimento is not None:
            dados.update(fonte=encode_value(registro.fonte or DiagramSource()),
                         reconhecimento=encode_value(registro.reconhecimento
                                                     or RecognitionResult()),
                         conferido=registro.conferido, decisoes=[])
            diagramas[ident] = dados
        else:
            dados["revisao"] = {"estado": "", "decisoes": []}
            blocos[ident] = dados
    return {"formato": FORMATO_DO_MAPA,
            "folios": {str(pagina): folio for pagina, folio in sorted(mapa.folios.items())},
            "blocos": blocos, "diagramas": diagramas,
            "capitulo": {"nos": [_sem_id_para_json(r) for r in mapa.sem_id.get("", [])]}}


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
                conferido=bool(registro.get("conferido", False)),
                duvidas=tuple(Duvida(ini=d["ini"], fim=d["fim"],
                                     proveniencia=decode_value(d["proveniencia"], Provenance),
                                     alternativas=tuple(str(a) for a in
                                                        d.get("alternativas") or ()),
                                     texto_sha=d.get("texto_sha"))
                              for d in registro.get("duvidas") or ()))
            if registro.get("nos"):
                mapa.sem_id[ident] = [_sem_id_de_json(r) for r in registro["nos"]]
    capitulo = (dados.get("capitulo") or {}).get("nos") or []
    if capitulo:
        mapa.sem_id[""] = [_sem_id_de_json(r) for r in capitulo]
    return mapa


def _indice_por_ulid(blocos: Iterable[Any]) -> dict[Any, Any]:
    indice: dict[Any, Any] = {}
    for bloco in blocos:
        for _, no in walk(bloco):
            indice.setdefault(no.id, no)
    return indice


def _seguir(no: Any, caminho: Iterable[tuple[str, int]]) -> Any:
    for campo, posicao in caminho:
        valor = getattr(no, campo, None) if not isinstance(no, list) else None
        if isinstance(no, list) and campo == "body":
            valor = no
        if posicao == -1:
            no = valor
        elif isinstance(valor, (tuple, list)) and 0 <= posicao < len(valor):
            no = valor[posicao]
        else:
            return None
        if no is None:
            return None
    return no


def _sha(texto: str) -> str:
    import hashlib

    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def conferir_mapa(
        capitulo: Capitulo, mapa: MapaDaProveniencia) -> list[str]:
    """O que no mapa não acha o lugar dele no IR relido (vazio: todo dado da máquina tem dono).

    Cada nó sem `id` é procurado pelo dono (o bloco com o `ir_id` do registro, ou o capítulo) e
    pelo caminho; o nó estrutural tem de ser do tipo registrado, e o trecho de dentro do parágrafo,
    cair no texto do campo com o mesmo SHA-256. As dúvidas de cada bloco, idem no conteúdo dele.
    """
    indice = _indice_por_ulid(capitulo.blocos)
    problemas: list[str] = []
    for dono, registros in mapa.sem_id.items():
        if dono:
            registro_do_dono = mapa.nos.get(dono)
            raiz = indice.get(registro_do_dono.ir_id) if registro_do_dono is not None else None
        else:
            raiz = list(capitulo.blocos)
        if raiz is None:
            problemas.append(f"o dono {dono!r} não está no IR relido")
            continue
        for registro in registros:
            no = _seguir(raiz, registro.caminho)
            onde = f"{dono or 'capítulo'}:{list(registro.caminho)}"
            if no is None:
                problemas.append(f"{onde}: o caminho não existe")
            elif registro.campo is None:
                if tag_of(no) != registro.tipo:
                    problemas.append(f"{onde}: {tag_of(no)} no lugar de {registro.tipo}")
            else:
                texto = "".join(texto_plano(x) for x in getattr(no, registro.campo, ()) or ())
                if _sha(texto) != registro.texto_sha or not (
                        0 <= (registro.ini or 0) <= (registro.fim or 0) <= len(texto)):
                    problemas.append(f"{onde}.{registro.campo}[{registro.ini}:{registro.fim}]: "
                                     "o trecho não é mais o mesmo")
    for ident, registro_do_bloco in mapa.nos.items():
        if not registro_do_bloco.duvidas:
            continue
        no = indice.get(registro_do_bloco.ir_id)
        texto = "".join(texto_plano(x) for x in getattr(no, "content", ()) or ()) if no else ""
        problemas.extend(
            f"{ident}: a dúvida [{duvida.ini}:{duvida.fim}] não acha o trecho"
            for duvida in registro_do_bloco.duvidas
            if no is None or _sha(texto) != duvida.texto_sha or duvida.fim > len(texto))
    return problemas


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
        nome = estilo if isinstance(estilo, str) else getattr(estilo, "name", None)
        if isinstance(nome, str):
            nomes.append(nome)
    return tuple(dict.fromkeys(n for n in nomes if n))
