"""A camada do OCR (spec S10): as dúvidas pendentes, no bloco de cada uma.

A dúvida é o trecho que o OCR não leu com certeza — o `Span` só de proveniência do IR, que a
ida legível guardou no `proveniencia.json` (a N3: as `duvidas` do bloco, e o nó sem `id` com
`duvida`). Até o serviço único de decisões (H7), toda dúvida está pendente: cada uma é um aviso
no elemento do bloco, com o trecho.
"""

from __future__ import annotations

from caissa.editor.validacao.contexto import Contexto
from caissa.editor.validacao.problema import Local, Problema, Severidade, regra
from caissa.editor.validacao.xml import Documento

__all__ = ["verificar"]

PENDENTE = regra("ocr-duvida-pendente", "ocr", Severidade.AVISA, "Dúvida do OCR pendente",
                 "Confira o trecho contra a página: aceite, corrija ou mantenha como imagem.")


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    mapa = contexto.mapa
    if mapa is None or documento.raiz is None:
        return []
    por_id = {e.get("id"): e for e in documento.elementos() if e.get("id")}
    problemas = []
    for ident, registro in mapa.nos.items():
        elemento = por_id.get(ident)
        if elemento is None:
            continue
        texto = elemento.texto()
        for duvida in registro.duvidas:
            trecho = texto[duvida.ini:duvida.fim].strip()
            problemas.append(Problema(PENDENTE, documento.local(elemento),
                                      f"{ident}, {duvida.ini}–{duvida.fim}: «{trecho[:40]}»"))
    for dono, registros in mapa.sem_id.items():
        elemento = por_id.get(dono) if dono else None
        for registro in registros:
            if not registro.duvida:
                continue
            local = documento.local(elemento) if elemento is not None else \
                Local(documento.arquivo, documento.raiz.linha, documento.raiz.coluna)
            problemas.append(Problema(PENDENTE, local,
                                      f"{dono or 'o capítulo'}, {registro.tipo} em "
                                      f"{registro.caminho}"))
    return problemas
