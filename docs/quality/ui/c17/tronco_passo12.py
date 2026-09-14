# ruff: noqa: E501 - pares verbatim do tronco
"""OCR_UI_ROADMAP passo 12 — as mudanças feitas no tronco (`ChessVisionOFF_Puro`), como dado.

O tronco tem, em 2026-09-14, sessenta arquivos modificados e não commitados por outra sessão
(os ciclos 9–16 da frente F9). Commitar lá os quatro arquivos que este passo toca levaria junto
o trabalho dessa sessão; então as mudanças ficam na árvore de trabalho do tronco e **aqui**, como
pares (antes, depois) reaplicáveis — `python tronco_passo12.py --aplicar` reaplica,
`--reverter` desfaz, sem argumento diz se a árvore do tronco está com elas.

O que muda, e por quê (relatório `OCR_UI_REPORT_C1.md` §10):

* `ui/comandos.py` — `Comando.rotulo_na_fita` e `na_fita`: a fita desenha uma palavra em todo
  botão; os seis de glifo ganham a sua ("Menos zoom", "Mais zoom", e os quatro de Estudo por
  extenso); "Apagar a peça" na fita devolve o modo pleno a 1.920 px.
* `qt/fita.py` — o cabeçalho do grupo é desenhado nos dois modos; `na_fita` no botão; a dica
  deixa de carregar o grupo (R3.4).
* `ui/medidas_da_fita.py` — o orçamento compacto conta o cabeçalho (64 → 72 px).
* `ui/icones.py` — `desfazer`/`refazer` enchem a caixa (20×9 → 20×18 px).
* `tests/test_qt_fita.py` — três testes que fixavam a decisão antiga, reescritos.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

PARES: dict[str, list[tuple[str, str]]] = {
    "src/chess_diagram_ocr/ui/comandos.py": [
        ('''    rotulo_curto: str = ""
    """O texto que o **botão** mostra, quando ele difere do rótulo do menu. Vazio = são o mesmo.
''', '''    rotulo_na_fita: str = ""
    """O texto que a **fita** desenha quando o curto é um glifo (`-`, `+`, `◀`…). Vazio = `no_botao`
    quando ele tem letra, `rotulo` quando não tem.

    **Toda tecla da fita tem rótulo desenhado** (OCR_UI_ROADMAP passo 12, R3.4: dica não é rótulo).
    Até o ciclo 16 os seis comandos de glifo saíam na fita só com o desenho — 6 de 24 sem palavra
    —, porque o glifo era o único texto curto que existia e ele não podia ficar ao lado do ícone.
    Aqui entra a palavra: os quatro de Estudo já a têm por extenso e curta ("Lance anterior"); os
    dois de zoom ganham duas ("Menos zoom", "Mais zoom") porque "Diminuir o zoom da página" não
    cabe em duas linhas de botão sem virar três."""

    rotulo_curto: str = ""
    """O texto que o **botão** mostra, quando ele difere do rótulo do menu. Vazio = são o mesmo.
'''),
        ('''    @property
    def no_botao(self) -> str:
        """O texto do botão: o curto quando ele existe, o do menu quando não."""
        return self.rotulo_curto or self.rotulo
''', '''    @property
    def no_botao(self) -> str:
        """O texto do botão: o curto quando ele existe, o do menu quando não."""
        return self.rotulo_curto or self.rotulo

    @property
    def na_fita(self) -> str:
        """O texto que a fita desenha: **sempre uma palavra**, nunca um glifo (passo 12)."""
        if self.rotulo_na_fita:
            return self.rotulo_na_fita
        return self.rotulo if self.so_glifo else self.no_botao
'''),
        ('''    Comando("apagar_casa", "Apagar a peça da casa selecionada", EDICAO, estilos.NEUTRO, icone="apagar_casa"),
''', '''    # `rotulo_na_fita`: com os seis botões de glifo rotulados (passo 12) a fita plena pedia
    # 1.926 px e deixava de caber a 1.920 (o compacto assumia a tela Full HD). O botão mais largo
    # era este, 122 px por "Apagar a peça da / casa selecionada"; "Apagar a peça" diz o mesmo ao
    # lado da casa com o X e devolve o pleno a 1.920. Menu e botão continuam por extenso.
    Comando(
        "apagar_casa",
        "Apagar a peça da casa selecionada",
        EDICAO,
        estilos.NEUTRO,
        icone="apagar_casa",
        rotulo_na_fita="Apagar a peça",
    ),
'''),
        ('''        icone="zoom_menos",
        rotulo_curto="-",
    ),
''', '''        icone="zoom_menos",
        rotulo_curto="-",
        rotulo_na_fita="Menos zoom",
    ),
'''),
        ('''        icone="zoom_mais",
        rotulo_curto="+",
    ),
''', '''        icone="zoom_mais",
        rotulo_curto="+",
        rotulo_na_fita="Mais zoom",
    ),
'''),
    ],
    "src/chess_diagram_ocr/qt/fita.py": [
        ('''        if self._modo == COMPACTO:
            # **O cabeçalho vira dica** (S-228): ele custa uma linha de texto por fita, e no modo
            # compacto essa linha é a diferença entre caber e competir com a página. O nome do
            # grupo não se perde -- ele passa a abrir a dica de cada botão dele.
            return moldura

        cabecalho = QLabel(grupo.rotulo, moldura)
''', '''        # **O cabeçalho é desenhado nos dois modos** (OCR_UI_ROADMAP passo 12; R3.4: dica não é
        # rótulo). A S-228 o mandava para a dica no compacto para caber em 64 px; medido, a linha
        # auxiliar custa 17–20 px e a fita compacta com cabeçalho fecha em 61–63 px na fonte do
        # produto -- cabe. O orçamento compacto passou a contá-lo (`medidas_da_fita.altura_da_fita`).
        cabecalho = QLabel(grupo.rotulo, moldura)
'''),
        ('''        acima = self._modo == PLENO
        botao = QToolButton(pai)
        botao.setText(quebrar_rotulo(registro.no_botao))
''', '''        acima = self._modo == PLENO
        botao = QToolButton(pai)
        # `na_fita`, e não `no_botao`: o glifo (`-`, `◀`) nunca chega à fita -- a palavra chega
        # (passo 12: 24 de 24 botões com rótulo desenhado; antes eram 18).
        botao.setText(quebrar_rotulo(registro.na_fita))
'''),
        ('''        lado = LADO_DO_ICONE[self._modo]
        vestiu = qt_icones.vestir(
            botao,
            registro.icone,
            comandos.papel(registro.acao),
            lado=lado,
            manter_texto=not registro.so_glifo,
        )
        if vestiu and registro.so_glifo:
            self._so_de_icone.add(registro.acao)
        dica_em(botao, self._dica(registro, grupo))
''', '''        lado = LADO_DO_ICONE[self._modo]
        # `manter_texto` sempre: o texto do botão da fita é uma palavra por construção
        # (`Comando.na_fita`), e `vestir` só apagaria um glifo que não está lá.
        qt_icones.vestir(
            botao,
            registro.icone,
            comandos.papel(registro.acao),
            lado=lado,
            manter_texto=True,
        )
        dica_em(botao, self._dica(registro, grupo))
'''),
        ('''        def escrever(texto: str) -> None:
            if acao in self._so_de_icone:
                return
            self._botoes[acao].setText(quebrar_rotulo(texto))
''', '''        def escrever(texto: str) -> None:
            # Um comando de glifo que alternasse escreveria o glifo pelo estado; a fita desenha
            # palavra, então o texto alternado só entra quando é palavra (passo 12).
            if comandos.comando(acao).so_glifo and not any(ch.isalpha() for ch in texto):
                return
            self._botoes[acao].setText(quebrar_rotulo(texto))
'''),
        ('''    def _dica(self, registro: comandos.Comando, grupo: GrupoDeFita) -> str:
        """O rótulo por extenso, a tecla, e -- no compacto -- o grupo que perdeu o cabeçalho."""
        titulo = (
            registro.rotulo
            if self._modo == PLENO
            else f"{grupo.rotulo} {strings.SETA} {registro.rotulo}"
        )
''', '''    def _dica(self, registro: comandos.Comando, grupo: GrupoDeFita) -> str:
        """O rótulo por extenso e a tecla. O grupo está no cabeçalho, nos dois modos (passo 12)."""
        del grupo  # desenhado, e não dito
        titulo = registro.rotulo
'''),
        ('        self._so_de_icone: set[str] = set()\n        """Os comandos que a fita desenha **sem texto**, porque o rótulo deles era um glifo e o\n        desenho o substituiu (F9-C9). Existe para o seguidor de `ao_alternar`: escrever um rótulo\n        num botão vestido de ícone reporia o glifo pela porta de trás, e o portão que o cobra não\n        olha por lá."""\n', ''),
        ('        self._so_de_icone.clear()\n', ''),
        ('        self._so_de_icone.clear()\n', ''),
        ('    pele,\n    strings,\n    tipografia,\n', '    pele,\n    tipografia,\n'),
    ],
    "src/chess_diagram_ocr/ui/medidas_da_fita.py": [
        ('''COMPACTO = "compacto"
"""Ícone pequeno, rótulo ao lado, cabeçalho na dica. É a mesma fita numa janela que não a comporta."""
''', '''COMPACTO = "compacto"
"""Ícone pequeno, rótulo ao lado, cabeçalho desenhado (passo 12). É a mesma fita numa janela que
não a comporta -- e, desde o passo 12 do OCR_UI_ROADMAP, com o nome do grupo à vista também aqui:
a dica não é rótulo (R3.4), e a linha auxiliar cabe no orçamento."""
'''),
        ('''ORCAMENTO: dict[str, int] = {PLENO: 120, COMPACTO: 64}
''', '''ORCAMENTO: dict[str, int] = {PLENO: 120, COMPACTO: 72}
'''),
        ('''a mais em troca de legibilidade. **64 px** é o que cabe sem a fita competir com a página num
1366×768, que é a tela em que a S-151 mediu o problema original."""
''', '''a mais em troca de legibilidade. **72 px** (era 64) é o compacto **com o cabeçalho desenhado**
(passo 12): a fila de botões de 43–45 px mais a linha auxiliar do nome do grupo; 9 % de 800 px,
ainda abaixo dos 20 % da S-151 e do que cabe sem a fita competir com a página num 1366×768."""
'''),
        ('''    lado = LADO_DO_ICONE[modo]
    rotulo = LINHAS_DO_ROTULO * linha_de_texto
    if modo == COMPACTO:
        # Ícone **ao lado** do rótulo: a altura é a do mais alto dos dois, e não a soma. E o
        # cabeçalho não entra porque ele virou dica -- é daí que vem quase toda a economia.
        return max(lado, rotulo) + MOLDURA_DO_BOTAO

    botao = lado + FOLGA_ACIMA_DO_ROTULO + rotulo + MOLDURA_DO_BOTAO
    return botao + espaco_ate_o_cabecalho(densidade, base=base) + linha_de_apoio + MOLDURA_DO_CABECALHO
''', '''    lado = LADO_DO_ICONE[modo]
    rotulo = LINHAS_DO_ROTULO * linha_de_texto
    cabecalho = espaco_ate_o_cabecalho(densidade, base=base) + linha_de_apoio + MOLDURA_DO_CABECALHO
    if modo == COMPACTO:
        # Ícone **ao lado** do rótulo: a altura é a do mais alto dos dois, e não a soma. O
        # cabeçalho entra (passo 12): a economia do compacto é a do ícone ao lado, não a do nome
        # do grupo escondido na dica.
        return max(lado, rotulo) + MOLDURA_DO_BOTAO + cabecalho

    botao = lado + FOLGA_ACIMA_DO_ROTULO + rotulo + MOLDURA_DO_BOTAO
    return botao + cabecalho
'''),
    ],
    "src/chess_diagram_ocr/ui/icones.py": [
        ('''    "desfazer": (
        Arco((50, 58), 28, 180, 360),
        Poli((10, 42), (22, 58), (34, 42)),
    ),
    "refazer": (
        Arco((50, 58), 28, 180, 360),
        Poli((66, 42), (78, 58), (90, 42)),
    ),
''', '''    # Três quartos de volta com a ponta da seta: a 20 px a meia-volta de antes ocupava 9 dos 20
    # px de altura e o botão parecia vazio (passo 12: caixa do desenho ≥ metade do lado nos dois
    # eixos).
    "desfazer": (
        Arco((50, 52), 30, 200, 470),
        Poli((10, 40), (22, 60), (36, 42)),
    ),
    "refazer": (
        Arco((50, 52), 30, 70, 340),
        Poli((64, 42), (78, 60), (90, 40)),
    ),
'''),
    ],
}


def _estado(caminho: Path, pares: list[tuple[str, str]]) -> str:
    texto = caminho.read_text(encoding="utf-8")
    if all(novo in texto for _, novo in pares):
        return "aplicado"
    if all(velho in texto for velho, _ in pares):
        return "por aplicar"
    return "misto"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--aplicar", action="store_true")
    grupo.add_argument("--reverter", action="store_true")
    args = parser.parse_args(argv)
    codigo = 0
    for relativo, pares in PARES.items():
        caminho = args.tronco / relativo
        estado = _estado(caminho, pares)
        if args.aplicar and estado == "por aplicar":
            texto = caminho.read_text(encoding="utf-8")
            for velho, novo in pares:
                texto = texto.replace(velho, novo, 1)
            caminho.write_text(texto, encoding="utf-8")
            estado = "aplicado agora"
        elif args.reverter and estado == "aplicado":
            texto = caminho.read_text(encoding="utf-8")
            for velho, novo in pares:
                texto = texto.replace(novo, velho, 1)
            caminho.write_text(texto, encoding="utf-8")
            estado = "revertido agora"
        if estado == "misto":
            codigo = 1
        print(f"{relativo}: {estado}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
