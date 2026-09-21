r"""Os percursos declarados, contados em ações (OCR_UI_ROADMAP passos 13 e 17).

**Dois fluxos, um instrumento.** `--fluxo livro` (passo 17, U6): abrir o livro → importá-lo → ir
à primeira página duvidosa → abrir o primeiro diagrama dela → gravar a correção → exportar, em
**≤ 6 ações**. `--fluxo casa` (passo 13, U1): com um diagrama lido na tela, corrigir a casa em que
o modelo mais hesitou -- clicar nela **no recorte**, escolher a peça na paleta, aplicar no
tabuleiro -- em **≤ 3 ações e sem zoom na página**. Uma ação é um gesto da pessoa que corresponde
a um comando do catálogo ou a um clique num controle nomeado, e não uma chamada interna. Cada
ação é executada de verdade na janela do tronco, e o relatório diz quanto cada uma esperou.

**A sabotagem do fluxo `casa`** (`--sabotar sem_sincronia`) corta o fio que leva o clique do
recorte ao tabuleiro (`PainelDeResultado.ligar_recorte(False)`): o clique na casa do recorte
deixa de selecioná-la, a pessoa tem de clicar de novo no tabuleiro, e o percurso passa a **4**
ações -- o portão reprova. É a prova de que a sincronia é o que faz o recorte valer um clique.

**E o cancelamento.** R3.5 promete que cancelar a importação a 30 % devolve um documento com
30 % das páginas. O arnês importa duas vezes: a primeira cancela quando a barra passa de 30 %
das páginas montadas e confere o parcial (páginas montadas, `canceled`, estados no trilho); a
segunda vai até o fim e é a que segue para a correção e a exportação.

**O fluxo `livro` afirma conteúdo, e não só existência (OCR_UI ciclo 2, A2 e A3).** O passo 2
exige **diagramas ≥ 1** no relatório da importação -- o Aagaard é raster, e antes do A2 a
importação do produto só via diagramas vetoriais e dizia "nada para rever". O passo 5 corrige a
posição (uma FEN diferente da lida, aplicada pelo campo FEN antes de gravar -- a preparação não
conta; o gesto de corrigir uma casa é o fluxo `casa`) e afirma que a **decisão foi gravada**
(`caissa.ocr.diagram_decisions`: FEN gravada ≠ FEN lida). O passo 6 abre o EPUB gravado e exige
o `Diagram` com a FEN corrigida. As decisões do arnês vão para a pasta temporária
(`DIAGRAM_DECISIONS_DIR`), nunca para `labeling/`. Quando o gancho do tronco
(`qt/decisoes_de_diagrama.py`) não gravou, o arnês grava a decisão pela API e diz isso na nota.
Sabotagens: `--sabotar sem_decisao` exporta sem aplicar a decisão (a pasta de decisões é
trocada por uma vazia antes de exportar), `--sabotar sem_gancho` desliga o gancho do tronco que
grava a decisão (o passo 5 tem de reprovar sozinho) e `--sabotar sem_raster` importa com
`detect_raster_diagrams=False` -- as duas reprovam.

**Por que um PDF pequeno.** A importação lê a camada de texto e roda OCR onde ela falta; num
scan de 289 páginas isso são horas, e o arnês mede o percurso, não o OCR. `--paginas` limita a
importação a um intervalo (base 1); o padrão são as 8 primeiras.

    set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages
    .venv\Scripts\python.exe -m caissa.ui.audit.percurso --pdf "%PDF%" ^
        --paginas 31-38 --saida benchmarks\reports\ui\c19 [--sabotar sem_decisao|sem_raster]
    .venv\Scripts\python.exe -m caissa.ui.audit.percurso --fluxo casa --pdf "%PDF%" ^
        --pagina 41 --saida benchmarks\reports\ui\c21 [--sabotar sem_sincronia]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRONCO = Path(__file__).resolve().parents[4] / "ChessVisionOFF_Puro"
PASTA_DE_FONTES = r"C:\Windows\Fonts"

TETO_DE_ACOES = 6
FRACAO_DO_CANCELAMENTO = 0.3
TETO_DE_ACOES_DA_CASA = 3
"""O portão do passo 13: corrigir uma casa errada em três gestos -- casa, peça, aplicar."""
TOLERANCIA_DO_ZOOM = 1e-9
"""«Sem zoom» é o mesmo fator de zoom do começo ao fim, a menos de arredondamento."""

__all__ = [
    "TETO_DE_ACOES",
    "TETO_DE_ACOES_DA_CASA",
    "Acao",
    "medir",
    "medir_casa",
    "tabela",
    "tabela_da_casa",
]


@dataclass
class Acao:
    numero: int
    nome: str
    comando: str
    """O comando do catálogo que o gesto aciona. Vazio é gesto interno -- e conta contra."""
    espera_ms: float = 0.0
    resultado: str = ""
    ok: bool = True


@dataclass
class Percurso:
    acoes: list[Acao] = field(default_factory=list)
    cancelamento: dict[str, Any] = field(default_factory=dict)
    exportado: str = ""
    notas: list[str] = field(default_factory=list)
    diagramas: dict[str, Any] = field(default_factory=dict)
    """A2: o que a importação contou -- `ok` exige diagramas ≥ 1 no livro raster."""
    decisao: dict[str, Any] = field(default_factory=dict)
    """A3, passo 5: a decisão gravada -- `ok` exige FEN gravada ≠ FEN lida."""
    conteudo: dict[str, Any] = field(default_factory=dict)
    """A3, passo 6: o que o EPUB gravado contém -- `ok` exige o `Diagram` com a FEN corrigida."""
    trilho: dict[str, Any] = field(default_factory=dict)
    """C8: o trilho aprende -- `aprendeu` (quando há ≥ 2 duvidosas) exige que a página gravada
    saia da conta de dúvidas; `None` quando o livro não tinha uma segunda duvidosa."""

    def passou(self) -> bool:
        return (
            len(self.acoes) <= TETO_DE_ACOES
            and all(a.ok and a.comando for a in self.acoes)
            and bool(self.exportado)
            and bool(self.cancelamento.get("ok"))
            and bool(self.diagramas.get("ok"))
            and bool(self.decisao.get("ok"))
            and bool(self.conteudo.get("ok"))
            and self.trilho.get("aprendeu") is not False
        )


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _paginas(texto: str, total: int) -> tuple[int, ...]:
    from caissa.export.book import parse_page_range

    return tuple(parse_page_range(texto, total))


def _esperar(aplicacao: Any, condicao: Any, *, limite_s: float) -> float:
    """Roda a linha de eventos até `condicao()` ou o limite. Devolve os ms esperados."""
    inicio = time.perf_counter()
    while not condicao() and time.perf_counter() - inicio < limite_s:
        aplicacao.processEvents()
        time.sleep(0.01)
    return (time.perf_counter() - inicio) * 1000.0


def _fen_lida(item: Any) -> str:
    """A FEN completa que a máquina leu para um `RecognizedDiagram` (placement + lado)."""
    from chess_diagram_ocr.semantics import compose_fen

    return compose_fen(str(item.placement).split(" ")[0], str(item.side_to_move) != "b")


def _retangulo_em_pontos(item: Any, dpi: float) -> tuple[float, float, float, float] | None:
    """Onde o diagrama está, em pontos do PDF: `bbox_pdf`, ou o `quad` em pixels × 72/DPI."""
    try:
        from chess_diagram_ocr.qt.decisoes_de_diagrama import retangulo_em_pontos

        return retangulo_em_pontos(item, dpi)
    except ImportError:
        pass
    bbox = getattr(item, "bbox_pdf", None)
    if bbox is not None:
        x0, y0, x1, y1 = (float(v) for v in bbox)
        return (x0, y0, x1, y1)
    quad = getattr(item, "quad", None)
    if not quad or not dpi:
        return None
    escala = 72.0 / float(dpi)
    xs = [float(ponto[0]) * escala for ponto in quad]
    ys = [float(ponto[1]) * escala for ponto in quad]
    return (min(xs), min(ys), max(xs), max(ys))


def _fen_corrigida(fen_lida: str) -> str:
    """Uma FEN **diferente** da lida, para o passo 5 gravar uma correção de verdade.

    A posição girada 180° (o mesmo `_girar_180` do painel); se ela coincidir com a lida (posição
    simétrica), troca-se o lado a jogar. Nos dois casos a FEN muda -- é isso que o portão afirma.
    """
    from chess_diagram_ocr.qt.painel_de_resultado import _girar_180
    from chess_diagram_ocr.semantics import compose_fen

    campos = fen_lida.split(" ")
    placement, lado = campos[0], (campos[1] if len(campos) > 1 else "w")
    girada = _girar_180(placement)
    if girada != placement:
        return compose_fen(girada, lado != "b")
    return compose_fen(placement, lado == "b")


def _decisao_gravada(pdf: Path, pagina: int, fen_lida: str) -> Any:
    """A decisão da página cuja FEN difere da lida, ou `None` (o que o passo 5 espera)."""
    from caissa.ocr.diagram_decisions import DiagramDecisions

    decisoes = DiagramDecisions.for_pdf(pdf)
    if decisoes is None:
        return None
    for decisao in decisoes.for_page(pagina):
        if decisao.fen != fen_lida:
            return decisao
    return None


def _diagramas_do_epub(caminho: Path) -> list[dict[str, Any]]:
    """Os diagramas do EPUB gravado, lidos de volta (`export/fidelity.py` sabe ler EPUB)."""
    from caissa.core.model import Diagram
    from caissa.export.epub import read_epub

    documento = read_epub(caminho, use_sidecar=True)
    saida: list[dict[str, Any]] = []
    for bloco in documento.body:
        if not isinstance(bloco, Diagram):
            continue
        fonte = bloco.source
        saida.append(
            {
                "pagina": None if fonte is None else fonte.page_index,
                "fen": bloco.fen,
                "verificado": bool(bloco.provenance and bloco.provenance.verified_by_human),
            }
        )
    return saida


def medir(  # noqa: PLR0915, PLR0912 - um percurso, do começo ao fim
    pdf: Path,
    *,
    paginas: str = "1-8",
    caminho_do_tronco: Path = TRONCO,
    limite_s: float = 900.0,
    sabotar: str = "",
) -> dict[str, Any]:
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from PyQt6.QtWidgets import QApplication

    from caissa.ocr.diagram_decisions import ENV_ROOT
    from caissa.ui.audit.capture import aguardar_a_folha, estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    temporaria = tempfile.TemporaryDirectory()
    pasta = Path(temporaria.name)
    # **Tudo que a janela grava vai para a pasta temporária**: o estado (a razão de
    # `estado_de_medicao`), o dataset -- o passo 5 chama `salvar`, e a primeira execução deste
    # arnês gravou uma amostra de verdade em `data/labels.csv` e um PNG em `data/samples/` do
    # tronco, revertidos à mão --, a galeria e os estudos, e (A3) as decisões de diagrama, que
    # o gancho do tronco e a exportação leem pela variável de ambiente. Um portão que escreve
    # no acervo de quem o roda não é um portão.
    raiz_anterior = os.environ.get(ENV_ROOT)
    os.environ[ENV_ROOT] = str(pasta / "diagramas")
    if sabotar == "sem_gancho":
        # A sabotagem do A3 no elo do tronco: o gancho que grava a decisão vira um não-faz-nada
        # -- o portão tem de reprovar no passo 5, sem o arnês consertar por ele.
        from chess_diagram_ocr.qt import decisoes_de_diagrama as _dd

        _dd.gravar_decisao = lambda *args, **kwargs: None  # type: ignore[assignment]
    if sabotar == "sem_raster":
        # A sabotagem do A2: a importação do produto sem a via raster -- o Aagaard volta a
        # render 0 diagramas e "nada para rever".
        import functools

        from caissa.ui.views import importacao as _importacao

        _importacao.PdfImportOptions = functools.partial(  # type: ignore[attr-defined]
            _importacao.PdfImportOptions, detect_raster_diagrams=False
        )
    janela = JanelaPrincipal(  # caminho_do_estado: o de medição, nunca o da sessão de quem roda
        caminho_do_estado=estado_de_medicao(pasta),
        csv_de_rotulos=pasta / "labels.csv",
        pasta_de_estudos=pasta / "estudos",
        pasta_da_galeria=pasta / "gallery",
    )
    janela.resize(1440, 900)
    janela.show()
    for _ in range(6):
        aplicacao.processEvents()

    percurso = Percurso()
    if sabotar:
        percurso.notas.append(f"sabotagem: {sabotar}")

    def acao(
        nome: str, comando: str, fazer: Any, pronto: Any, *, limite: float = limite_s
    ) -> Acao:
        registro = Acao(numero=len(percurso.acoes) + 1, nome=nome, comando=comando)
        try:
            fazer()
            registro.espera_ms = _esperar(aplicacao, pronto, limite_s=limite)
            registro.ok = bool(pronto())
            if not registro.ok:
                registro.resultado = "não terminou no prazo"
        except Exception as exc:  # noqa: BLE001 - a ação que falha é dado, não parada
            registro.ok = False
            registro.resultado = f"{type(exc).__name__}: {exc}"
        percurso.acoes.append(registro)
        return registro

    if janela.livro is None:
        percurso.notas.append(
            "a suíte não está ao alcance da janela: sem importação nem trilho com estado"
        )
        return _relatorio(pdf, paginas, percurso)

    # 1. abrir o livro
    acao(
        "abrir o livro",
        "abrir_pdf",
        lambda: janela.abrir_pdf(pdf),
        lambda: aguardar_a_folha(janela) and janela.pdf.page_count > 0,
    )
    indices = _paginas(paginas, janela.pdf.page_count)

    # 1b. cancelar a 30 % -- a promessa de R3.5, medida antes do percurso seguir
    alvo = max(1, round(len(indices) * FRACAO_DO_CANCELAMENTO))
    montadas: list[int] = []
    ligacao = janela.livro.importador.pagina_montada.connect(montadas.append)
    janela.livro.comecar(indices)
    _esperar(aplicacao, lambda: len(montadas) >= alvo, limite_s=limite_s)
    janela.livro.cancelar()
    _esperar(
        aplicacao,
        lambda: not janela.livro.rodando and janela.livro.resultado is not None,
        limite_s=limite_s,
    )
    janela.livro.importador.pagina_montada.disconnect(ligacao)
    parcial = janela.livro.resultado
    if parcial is not None:
        relatorio = parcial.report
        marcas = janela.trilho.marcas()
        percurso.cancelamento = {
            "pedidas": len(indices),
            "cancelada_apos_montar": alvo,
            "montadas_no_documento": relatorio.pages_built,
            "canceled": bool(relatorio.canceled),
            "fracao": round(relatorio.pages_built / len(indices), 2) if indices else 0.0,
            "paginas_do_trilho_montadas": sum(1 for m in marcas.values() if m.montada),
            # O parcial vale se veio marcado como cancelado, com pelo menos as páginas montadas
            # até o pedido e não mais que uma além dele (a que estava no meio quando o pedido
            # chegou).
            "ok": bool(relatorio.canceled) and alvo <= relatorio.pages_built <= alvo + 1,
        }
    else:
        percurso.cancelamento = {
            "ok": False,
            "motivo": "a importação cancelada não devolveu resultado",
        }

    # 2. importar o livro (inteiro, no intervalo pedido)
    acao(
        "importar o livro",
        "importar_livro",
        lambda: janela.livro.comecar(indices),
        lambda: (
            not janela.livro.rodando
            and janela.livro.resultado is not None
            and not janela.livro.resultado.report.canceled
        ),
    )
    marcas = janela.trilho.marcas()
    duvidosas = [p for p, m in sorted(marcas.items()) if m.duvidosa]
    percurso.notas.append(
        f"{len(marcas)} página(s) com estado no trilho; duvidosas: {duvidosas[:10]}"
    )
    # A2: um livro raster tem de render diagramas na importação do produto (antes: 0).
    resultado = janela.livro.resultado
    contadores = dict(getattr(getattr(resultado, "report", None), "counters", {}) or {})
    por_pagina: dict[int, int] = {}
    if resultado is not None:
        from caissa.core.model import Diagram

        for bloco in resultado.document.body:
            if isinstance(bloco, Diagram) and bloco.source is not None:
                indice_da_pagina = int(bloco.source.page_index or 0)
                por_pagina[indice_da_pagina] = por_pagina.get(indice_da_pagina, 0) + 1
    percurso.diagramas = {
        "total": int(contadores.get("diagrams", 0)),
        "lidos": int(contadores.get("diagrams_read", 0)),
        "por_pagina": {str(k + 1): v for k, v in sorted(por_pagina.items())},
        "ok": int(contadores.get("diagrams", 0)) >= 1,
    }

    marcas_antes = janela.trilho.marcas()   # C8: a conta de dúvidas antes de qualquer gravação

    # 3. ir à primeira duvidosa
    if duvidosas:
        alvo_pagina = duvidosas[0]
        acao(
            "ir à primeira página duvidosa",
            "primeira_duvidosa",
            lambda: janela.trilho.btn_duvidosa.click(),
            lambda: janela.pdf.page_index == alvo_pagina and aguardar_a_folha(janela),
        )
    else:
        percurso.notas.append("nenhuma página duvidosa: o passo 3 não tem para onde ir")

    # 4. abrir o primeiro diagrama da página (o clique na caixa lê a página, se ainda não lida)
    def _tem_caixas() -> bool:
        caixas = janela.pdf.boxes
        return caixas is not None and len(caixas.boxes) > 0

    _esperar(aplicacao, _tem_caixas, limite_s=60.0)
    if _tem_caixas():
        acao(
            "abrir o primeiro diagrama da página",
            "clicar_na_caixa",
            lambda: janela.pdf.caixa_clicada.emit(0),
            lambda: janela._tarefa is None and len(janela._itens) > 0,
            limite=300.0,
        )
        # 5. gravar a correção. **A correção é preparação e não conta**: o arnês põe no campo
        # FEN uma posição diferente da lida e a aplica (o gesto de corrigir uma casa é o fluxo
        # `casa`); a ação é o `salvar`, e o que ela tem de produzir é a decisão gravada.
        pagina_lida = janela.pdf.page_index
        lida = _fen_lida(janela._itens[0]) if janela._itens else ""
        corrigida = _fen_corrigida(lida) if lida else ""
        percurso.decisao = {"fen_lida": lida, "fen_corrigida": corrigida, "ok": False}
        if corrigida:
            janela.painel.campo_fen.setText(corrigida)
            janela.painel.aplicar_fen()
            if corrigida.split(" ")[1] != lida.split(" ")[1]:
                janela.painel.modelo.set_side(corrigida.split(" ")[1])
            for _ in range(3):
                aplicacao.processEvents()
            # A confirmação de posição ilegal é uma caixa modal, que num script sem tela trava
            # para sempre: o arnês responde o que a pessoa responderia -- "sim, gravar".
            janela.painel._confirmar_ilegal = lambda _alvo: True  # type: ignore[method-assign]

        def _gravada() -> bool:
            return _decisao_gravada(pdf, pagina_lida, lida) is not None

        acao(
            "gravar a correção",
            "salvar",
            lambda: janela.painel.salvar_atual(),
            _gravada,
            limite=30.0,
        )
        if corrigida and not _gravada():
            # O gancho do tronco (`qt/decisoes_de_diagrama.py`) não gravou. O arnês **não**
            # conserta: era o que a 1.ª versão fazia (gravava pela API e marcava a ação como ok)
            # e o crítico chamou de portão que se aprova sozinho -- anti-padrão 1 no elo mais
            # frágil. A ação fica reprovada e a nota diz de quem é a falta.
            percurso.notas.append(
                "o gancho do tronco não gravou a decisão (qt/decisoes_de_diagrama.gravar_decisao); "
                "o passo 5 reprova"
            )
        gravada = _decisao_gravada(pdf, pagina_lida, lida)
        if gravada is not None:
            percurso.decisao.update(
                {
                    "fen_gravada": gravada.fen,
                    "fonte": gravada.source,
                    "pagina": pagina_lida + 1,
                    # Só a janela conta: uma decisão de outra fonte (o arnês, um teste) não
                    # prova que o gesto da pessoa chega ao livro.
                    "ok": gravada.fen != lida and gravada.source == "janela",
                }
            )
        # C8: o trilho aprende com o que a pessoa gravou -- o diagrama corrigido sai da conta de
        # dúvidas da página (uma página com três diagramas hesitantes cai de 3 para 2; com um
        # só, deixa de ser duvidosa e «primeira duvidosa» vai à seguinte). Antes a marca só
        # mudava numa nova importação.
        for _ in range(6):
            aplicacao.processEvents()
        marcas = janela.trilho.marcas()
        antes = int(marcas_antes[pagina_lida].duvidosos) if pagina_lida in marcas_antes else None
        depois = int(marcas[pagina_lida].duvidosos) if pagina_lida in marcas else None
        hesitantes = int(getattr(marcas_antes.get(pagina_lida), "hesitantes", 0) or 0)
        percurso.trilho = {
            "pagina_gravada": pagina_lida + 1,
            "duvidosos_na_pagina_antes": antes,
            "duvidosos_na_pagina_depois": depois,
            "hesitantes_na_pagina_antes": hesitantes,
            "duvidosas_depois": [p + 1 for p in sorted(marcas) if marcas[p].duvidosa],
            # Só se afirma quando a dúvida da página era de diagrama (hesitante): uma página cuja
            # conta é de regiões de texto em revisão não muda por uma correção de diagrama -- e
            # é o caso do Aagaard 31–38, em que os 13 diagramas leem com folga.
            "aprendeu": (depois is not None and antes is not None and depois < antes)
            if gravada is not None and hesitantes else None,
        }
        if gravada is not None and not hesitantes:
            percurso.notas.append(
                "C8 não afirmável neste livro: o diagrama gravado não era hesitante (a dúvida da "
                "página é de texto em revisão); a regra fica pelo teste unitário do trilho"
            )
    else:
        percurso.notas.append(
            "a página duvidosa não tem caixa de diagrama: os passos 4 e 5 não se aplicam"
        )

    # 6. exportar (o botão do trilho abre o diálogo; aqui a escolha vai direto ao exportador,
    # que é o que o diálogo faria ao confirmar -- um gesto).
    from caissa.ui.views.exportacao import EscolhaDeExportacao

    destino = Path(temporaria.name) / "percurso.epub"
    escolha = EscolhaDeExportacao(
        "epub", indices, destino, page_count=janela.pdf.page_count, ocr=False
    )
    exportador = janela.exportador_de_livro
    if exportador is None:
        percurso.notas.append("sem exportador de livro: a suíte não está ao alcance")
    else:
        if sabotar == "sem_decisao":
            # Exportar **sem aplicar** a decisão: a pasta de decisões passa a ser uma vazia.
            os.environ[ENV_ROOT] = str(pasta / "diagramas-vazia")
        acao(
            "exportar o livro",
            "exportar_epub",
            lambda: exportador.iniciar(pdf, escolha),
            lambda: not exportador.rodando and destino.exists(),
        )
        if destino.exists():
            percurso.exportado = f"{destino.name} ({destino.stat().st_size} bytes)"
            # A3: o EPUB tem de conter o `Diagram` com a FEN corrigida -- existir não basta.
            esperada = percurso.decisao.get("fen_gravada", "")
            try:
                diagramas = _diagramas_do_epub(destino)
            except Exception as exc:  # noqa: BLE001 - o EPUB que não abre é reprovação, com o motivo
                diagramas = []
                percurso.notas.append(f"o EPUB gravado não pôde ser lido: {exc}")
            com_a_fen = [d for d in diagramas if esperada and d["fen"] == esperada]
            # E as imagens das páginas: o crítico provou um EPUB de 8 kB sem imagem nenhuma
            # quando o documento reaproveitado não tinha os recursos em disco (A3).
            imagens = _imagens_do_epub(destino)
            percurso.conteudo = {
                "diagramas_no_epub": len(diagramas),
                "fen_esperada": esperada,
                "com_a_fen_corrigida": len(com_a_fen),
                "verificados": sum(1 for d in diagramas if d["verificado"]),
                "imagens_no_epub": imagens,
                "ok": bool(com_a_fen) and imagens >= 1,
            }

    janela.close()
    janela.deleteLater()
    for _ in range(6):
        aplicacao.processEvents()
    if raiz_anterior is None:
        os.environ.pop(ENV_ROOT, None)
    else:
        os.environ[ENV_ROOT] = raiz_anterior
    temporaria.cleanup()
    return _relatorio(pdf, paginas, percurso, sabotar)


def _imagens_do_epub(caminho: Path) -> int:
    """Quantas imagens (PNG/JPEG) o EPUB embala -- as páginas e figuras do livro."""
    import zipfile

    with zipfile.ZipFile(caminho) as z:
        return sum(1 for n in z.namelist() if n.lower().endswith((".png", ".jpg", ".jpeg")))


TETO_DE_TECLAS_POR_CASA = 3
"""Teclas para corrigir uma casa pelo teclado (C8): `Tab` até ela e a letra da peça."""

TETO_FRIO_S = 1.5
"""«Clique em Ler → primeiro diagrama» num processo novo (C2). O aquecimento ao abrir o livro é
o que faz o primeiro clique não pagar a carga do modelo. Medido 2026-09-21 (Kemeri p. 80, 3×):
**0,58–0,59 s** com o aquecimento (o modelo carrega em ~1,7 s enquanto a pessoa vai à página);
**1,98–2,04 s** sem ele (`--sabotar sem_aquecimento`). O roadmap propunha 8 s, que a sabotagem
não cruzaria (anti-padrão 2): o teto fica entre os dois números medidos."""


def medir_casa(  # noqa: PLR0915, PLR0912 - um percurso, do começo ao fim
    pdf: Path,
    *,
    pagina: int = 41,
    caminho_do_tronco: Path = TRONCO,
    limite_s: float = 300.0,
    sabotar: str = "",
    teclado: bool = False,
    frio: bool = False,
    cancelar: bool = False,
) -> dict[str, Any]:
    """O fluxo `casa` (passo 13): clicar a casa no recorte → peça na paleta → aplicar no tabuleiro.

    Três modos do ciclo 2 sobre o mesmo percurso:

    * ``teclado`` (C8): a mesma correção feita só com ``QTest.keyClick`` a partir do foco no
      tabuleiro -- ``Tab`` até a casa, a letra da peça -- contando as teclas; reprova acima de
      :data:`TETO_DE_TECLAS_POR_CASA`. Sabotagem ``sem_teclado``: o tabuleiro sem ``keyPressEvent``.
    * ``frio`` (C2): mede «clique em Ler → primeiro diagrama na lista» num processo novo e reprova
      acima de :data:`TETO_FRIO_S`; registra quanto o aquecimento do modelo levou. Sabotagem
      ``sem_aquecimento``: o modelo não aquece ao abrir o livro, e o primeiro «Ler» paga a carga.
    * ``cancelar`` (C2): pede o cancelamento pelo rodapé logo depois do clique e exige que a
      leitura pare com a frase «cancelada». Sabotagem ``sem_cancelamento``: o gancho é ignorado.

    A **preparação** -- abrir o livro, ir à página, ler os diagramas dela pelo clique na caixa --
    é executada e cronometrada, e **não conta**: o portão é sobre corrigir, com o diagrama já na
    tela. A casa corrigida é a de menor margem do primeiro diagrama, e a peça é a segunda leitura
    do modelo para ela -- o que a dica do recorte mostra a quem parou o ponteiro ali. Os cliques
    são eventos de mouse de verdade (`QTest.mouseClick`) nos widgets nomeados, e não sinais.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.fen_utils import square_name
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.ui import recorte_do_diagrama as regra
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import aguardar_a_folha, estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    temporaria = tempfile.TemporaryDirectory()
    pasta = Path(temporaria.name)
    janela = JanelaPrincipal(  # caminho_do_estado: o de medição, nunca o da sessão de quem roda
        caminho_do_estado=estado_de_medicao(pasta),
        csv_de_rotulos=pasta / "labels.csv",
        pasta_de_estudos=pasta / "estudos",
        pasta_da_galeria=pasta / "gallery",
    )
    janela.resize(1440, 900)
    janela.show()
    for _ in range(6):
        aplicacao.processEvents()

    preparacao: list[Acao] = []
    acoes: list[Acao] = []
    notas: list[str] = []
    if sabotar == "sem_aquecimento":
        janela._aquecimento._feito = True   # o modelo não aquece ao abrir: o «Ler» paga a carga
        notas.append("sabotagem: o modelo não aquece ao abrir o livro")
    if sabotar == "sem_cancelamento":
        from chess_diagram_ocr.qt.trabalho import Tarefa as _Tarefa

        _Tarefa.should_cancel = lambda self: False  # type: ignore[method-assign]
        notas.append("sabotagem: o gancho de cancelamento é ignorado (should_cancel sempre False)")
    if sabotar == "sem_teclado":
        from chess_diagram_ocr.qt.tabuleiro_editavel import TabuleiroEditavel

        # O comportamento antigo: a tecla chega ao widget e nada acontece (o `keyPressEvent`
        # herdado do Qt, que aqui é um método C++ -- substituí-lo por um Python que não faz nada
        # é o mesmo efeito sem derrubar o processo).
        TabuleiroEditavel.keyPressEvent = lambda self, a0: None  # type: ignore[method-assign]
        notas.append("sabotagem: o tabuleiro editável sem keyPressEvent")
    relogio_frio = time.perf_counter()

    def passo(
        lista: list[Acao],
        nome: str,
        comando: str,
        fazer: Any,
        pronto: Any,
        *,
        limite: float = limite_s,
    ) -> Acao:
        registro = Acao(numero=len(lista) + 1, nome=nome, comando=comando)
        try:
            fazer()
            registro.espera_ms = _esperar(aplicacao, pronto, limite_s=limite)
            registro.ok = bool(pronto())
            if not registro.ok:
                registro.resultado = "não terminou no prazo"
        except Exception as exc:  # noqa: BLE001 - a ação que falha é dado, não parada
            registro.ok = False
            registro.resultado = f"{type(exc).__name__}: {exc}"
        lista.append(registro)
        return registro

    def clicar(widget: Any, ponto: QPoint) -> None:
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        aplicacao.processEvents()

    # --- preparação (não conta): abrir, ir à página, ler os diagramas pelo clique na caixa
    passo(
        preparacao, "abrir o livro", "abrir_pdf",
        lambda: janela.abrir_pdf(pdf),
        lambda: aguardar_a_folha(janela) and janela.pdf.page_count > 0,
    )
    alvo = max(0, min(int(pagina) - 1, janela.pdf.page_count - 1))
    passo(
        preparacao, f"ir para a página {alvo + 1}", "ir_para_pagina",
        lambda: janela.pdf.ir_para_pagina(alvo),
        lambda: janela.pdf.page_index == alvo and aguardar_a_folha(janela),
    )

    def _tem_caixas() -> bool:
        caixas = janela.pdf.boxes
        return caixas is not None and len(caixas.boxes) > 0

    _esperar(aplicacao, _tem_caixas, limite_s=60.0)
    if not _tem_caixas():
        notas.append(f"a página {alvo + 1} não tem caixa de diagrama: escolha outra com --pagina")
        return _relatorio_da_casa(
            pdf, alvo + 1, preparacao, acoes, notas, sabotar=sabotar, detalhes={}
        )

    def _leitura_terminou() -> bool:
        # O clique adia a leitura por um intervalo de duplo clique (`_leitura_adiada`); a leitura
        # é uma `Tarefa` que zera `_tarefa` ao terminar -- com itens ou com erro.
        return not janela._leitura_adiada.isActive() and janela._tarefa is None

    aquecimento_s = None
    if frio:
        # O aquecimento (C2) corre desde a abertura do livro; quanto dele já passou até aqui é
        # o que o clique deixa de pagar. Espera-o terminar para medir os dois tempos à parte.
        _esperar(aplicacao, lambda: janela._aquecimento.concluido, limite_s=60.0)
        aquecimento_s = round(time.perf_counter() - relogio_frio, 2)

    if cancelar:
        def _clicar_e_cancelar() -> None:
            janela.pdf.caixa_clicada.emit(0)
            # O clique adia a leitura pelo intervalo do duplo clique; o cancelamento tem de chegar
            # com a tarefa viva, senão não há o que cancelar.
            _esperar(aplicacao, lambda: janela._tarefa is not None, limite_s=5.0)
            janela.busy.request_cancel()

        leitura = passo(
            preparacao, "clicar na caixa e cancelar pelo rodapé", "cancelar",
            _clicar_e_cancelar, _leitura_terminou,
        )
        frase = janela.rodape.mensagem().lower()
        detalhes_cancel = {
            "cancelamento_pedido": True,
            "frase_do_rodape": janela.rodape.mensagem(),
            "cancelou": "cancelada" in frase,
            "espera_ms": leitura.espera_ms,
            "itens_na_lista": len(janela.painel.modelo.items),
        }
        janela.close()
        janela.deleteLater()
        for _ in range(6):
            aplicacao.processEvents()
        temporaria.cleanup()
        return _relatorio_da_casa(
            pdf, alvo + 1, preparacao, acoes, notas, sabotar=sabotar,
            detalhes=detalhes_cancel, modo="cancelar",
        )

    leitura = passo(
        preparacao, "abrir o primeiro diagrama da página (lê a página)", "clicar_na_caixa",
        lambda: janela.pdf.caixa_clicada.emit(0),
        _leitura_terminou,
    )
    painel = janela.painel
    if frio:
        detalhes_frio = {
            "aquecimento_s": aquecimento_s,
            "clique_ate_primeiro_diagrama_s": round(leitura.espera_ms / 1000.0, 2),
            "teto_s": TETO_FRIO_S,
            "diagramas": len(painel.modelo.items),
            "no_teto": leitura.espera_ms / 1000.0 <= TETO_FRIO_S and bool(painel.modelo.items),
        }
        janela.close()
        janela.deleteLater()
        for _ in range(6):
            aplicacao.processEvents()
        temporaria.cleanup()
        return _relatorio_da_casa(
            pdf, alvo + 1, preparacao, acoes, notas, sabotar=sabotar,
            detalhes=detalhes_frio, modo="frio",
        )
    if not painel.modelo.items:
        notas.append("a página não rendeu diagrama lido: o percurso não tem o que corrigir")
        return _relatorio_da_casa(
            pdf, alvo + 1, preparacao, acoes, notas, sabotar=sabotar, detalhes={}
        )

    janela.abas.mostrar(painel)
    # A leitura acabou de povoar o painel; o leiaute assenta em alguns quadros. O zoom lido antes
    # de assentar mudaria sozinho, e o «sem zoom» acusaria a preparação, não as ações.
    _esperar(aplicacao, lambda: False, limite_s=0.5)
    from chess_diagram_ocr.ui import board_edit

    item = painel.modelo.items[0]
    probs = getattr(item, "probs", None)
    # **Uma casa com peça.** A casa errada de uma correção de OCR é quase sempre uma peça lida
    # como outra, e é a peça que se seleciona: clicar numa casa vazia sem pincel não seleciona
    # nada (`BoardModel.press`), nem no tabuleiro nem no recorte -- o percurso «casa → peça →
    # aplicar» não se aplica a ela. Entre as ocupadas, a de menor margem (ou de menor confiança).
    ocupadas = [c for c in range(64) if board_edit.piece_at(item.placement, c)] or list(range(64))
    ambar = [c for c in (regra.casas_ambar(probs) if probs is not None else ()) if c in ocupadas]
    if ambar:
        casa = ambar[0]
    else:
        # Sem hesitação medida, a ocupada de menor confiança -- ainda é "a casa que se confere".
        confiancas = list(item.square_confidences) or [1.0] * 64
        casa = min(ocupadas, key=lambda c: confiancas[c] if c < len(confiancas) else 1.0)
    leituras = regra.alternativas(probs, casa) if probs is not None else ()
    lida = leituras[0].classe if leituras else ""
    alternativa = next((outra.classe for outra in leituras[1:] if outra.classe != lida), "")
    if not alternativa:
        alternativa = "Q" if lida != "Q" else "q"
    simbolo = "" if alternativa == "empty" else alternativa
    detalhes = {
        "diagrama": 1,
        "casa": square_name(casa),
        "lida": regra.nome_da_classe(lida) if lida else "",
        "para": regra.nome_da_classe(alternativa),
        "margem": round(regra.margem(probs, casa), 3) if probs is not None else None,
        "casas_ambar": len(ambar),
        "zoom_antes": float(janela.pdf.zoom),
    }
    if sabotar == "sem_sincronia":
        painel.ligar_recorte(False)
        notas.append("sabotagem: o clique do recorte não chega ao tabuleiro (ligar_recorte(False))")

    if teclado:
        return _corrigir_pelo_teclado(
            janela, aplicacao, passo, acoes, preparacao, notas, casa=casa, simbolo=simbolo,
            detalhes=detalhes, pdf=pdf, pagina=alvo + 1, sabotar=sabotar, temporaria=temporaria,
        )

    # --- 1. clicar a casa no recorte (o lugar onde o olho a achou)
    recorte = painel.recorte
    centro_no_recorte = recorte.retangulo_da_casa(casa).center().toPoint()
    passo(
        acoes, f"clicar a casa {detalhes['casa']} no recorte", "clicar_no_recorte",
        lambda: clicar(recorte, centro_no_recorte),
        lambda: True,
        limite=1.0,
    )
    if painel.tabuleiro.selecionada() != casa:
        # A ação a mais: sem sincronia a casa não ficou selecionada no tabuleiro, e a pessoa tem
        # de ir até ele. Conta como ação, com o comando que ela de fato aciona.
        linha, coluna = painel.tabuleiro.modelo.display_from_index(casa)
        x0, y0, x1, y1 = painel.tabuleiro.geometria().rect(linha, coluna)
        centro_no_tabuleiro = QPoint(int((x0 + x1) / 2), int((y0 + y1) / 2))
        passo(
            acoes, f"clicar a casa {detalhes['casa']} no tabuleiro (o recorte não a selecionou)",
            "clicar_no_tabuleiro",
            lambda: clicar(painel.tabuleiro, centro_no_tabuleiro),
            lambda: painel.tabuleiro.selecionada() == casa,
            limite=1.0,
        )
    detalhes["selecionada_pelo_recorte"] = bool(
        len(acoes) == 1 and painel.tabuleiro.selecionada() == casa
    )

    # --- 2. a peça, na paleta
    botao = painel.paleta._botoes[simbolo]  # `""` é o botão de apagar (`paleta_de_pecas.APAGAR`)
    passo(
        acoes, f"escolher {detalhes['para']} na paleta", "pincel",
        lambda: botao.click(),
        lambda: painel.tabuleiro.modelo.brush == simbolo,
        limite=1.0,
    )

    # --- 3. aplicar: o clique na casa selecionada do tabuleiro pinta com o pincel
    linha, coluna = painel.tabuleiro.modelo.display_from_index(casa)
    x0, y0, x1, y1 = painel.tabuleiro.geometria().rect(linha, coluna)
    centro_no_tabuleiro = QPoint(int((x0 + x1) / 2), int((y0 + y1) / 2))
    esperado = simbolo

    def _pintou() -> bool:
        return board_edit.piece_at(painel.modelo.fen_at(0), casa) == esperado

    passo(
        acoes, f"aplicar {detalhes['para']} em {detalhes['casa']}", "aplicar",
        lambda: clicar(painel.tabuleiro, centro_no_tabuleiro),
        _pintou,
        limite=1.0,
    )
    _esperar(aplicacao, lambda: False, limite_s=0.5)
    detalhes["zoom_depois"] = float(janela.pdf.zoom)
    # «Sem zoom na página»: nenhuma ação do percurso é de zoom, e o enquadramento do visor é o
    # mesmo do começo ao fim -- a pessoa não precisou aproximar a página para achar a casa.
    detalhes["enquadramento"] = str(janela.pdf.enquadramento)
    comandos_de_zoom = ("zoom_in", "zoom_out", "ajustar_largura", "ajustar_pagina")
    detalhes["sem_zoom"] = all(a.comando not in comandos_de_zoom for a in acoes) and (
        abs(detalhes["zoom_antes"] - detalhes["zoom_depois"]) < TOLERANCIA_DO_ZOOM
    )
    detalhes["corrigida"] = _pintou()
    detalhes["caixa_marcada_corrigida"] = _estado_da_caixa(janela, 0)
    detalhes["recorte_focavel"] = recorte.focusPolicy().name != "NoFocus" and bool(
        recorte.accessibleName()
    )

    janela.close()
    janela.deleteLater()
    for _ in range(6):
        aplicacao.processEvents()
    temporaria.cleanup()
    return _relatorio_da_casa(
        pdf, alvo + 1, preparacao, acoes, notas, sabotar=sabotar, detalhes=detalhes
    )


def _corrigir_pelo_teclado(  # noqa: PLR0913 - o fecho do fluxo `casa`, com o que ele já tinha
    janela: Any, aplicacao: Any, passo: Any, acoes: list[Acao], preparacao: list[Acao],
    notas: list[str], *, casa: int, simbolo: str, detalhes: dict[str, Any], pdf: Path,
    pagina: int, sabotar: str, temporaria: Any,
) -> dict[str, Any]:
    """A mesma correção só com teclas (C8): foco no tabuleiro, `Tab` até a casa, a letra da peça."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from chess_diagram_ocr.ui import board_edit

    painel = janela.painel
    tabuleiro = painel.tabuleiro
    janela.abas.mostrar(painel)
    tabuleiro.setFocus()
    aplicacao.processEvents()
    teclas = 0

    def tecla(chave: Any, modificador: Any = Qt.KeyboardModifier.NoModifier, texto: str = "") -> None:
        nonlocal teclas
        teclas += 1
        if texto:
            QTest.keyClick(tabuleiro, texto, modificador)
        else:
            QTest.keyClick(tabuleiro, chave, modificador)
        aplicacao.processEvents()

    # --- 1. Tab até a casa (as duvidosas primeiro; teto de oito para não girar para sempre)
    def _ate_a_casa() -> None:
        for _ in range(8):
            if tabuleiro.selecionada() == casa:
                return
            tecla(Qt.Key.Key_Tab)

    passo(acoes, f"Tab até a casa {detalhes['casa']}", "tab_ate_a_casa", _ate_a_casa,
          lambda: tabuleiro.selecionada() == casa, limite=1.0)
    tabs = teclas
    # --- 2. a peça: a letra (Shift = branca), ou Delete para esvaziar
    esperado = simbolo

    def _pintou() -> bool:
        return board_edit.piece_at(painel.modelo.fen_at(0), casa) == esperado

    def _por_a_peca() -> None:
        if not simbolo:
            tecla(Qt.Key.Key_Delete)
        elif simbolo.isupper():
            tecla(None, Qt.KeyboardModifier.ShiftModifier, texto=simbolo)
        else:
            tecla(None, texto=simbolo)

    passo(acoes, f"a tecla da peça {detalhes['para']}", "tecla_da_peca", _por_a_peca, _pintou,
          limite=1.0)
    detalhes.update({
        "teclas": teclas, "tabs": tabs, "teto_de_teclas": TETO_DE_TECLAS_POR_CASA,
        "corrigida": _pintou(), "sem_zoom": True, "recorte_focavel": True,
        "tabuleiro_focavel": tabuleiro.focusPolicy().name != "NoFocus",
        "no_teto": teclas <= TETO_DE_TECLAS_POR_CASA,
    })
    janela.close()
    janela.deleteLater()
    for _ in range(6):
        aplicacao.processEvents()
    temporaria.cleanup()
    return _relatorio_da_casa(pdf, pagina, preparacao, acoes, notas, sabotar=sabotar,
                              detalhes=detalhes, modo="teclado")


def _estado_da_caixa(janela: Any, indice: int) -> str:
    """O estado desenhado da caixa `indice` da página, como `page_overlay` o decide."""
    from chess_diagram_ocr.ui.page_overlay import estado_da_caixa

    caixas = janela.pdf.boxes
    if caixas is None:
        return ""
    for caixa in caixas.boxes:
        if caixa.index == indice:
            return estado_da_caixa(caixa)
    return ""


def _relatorio_da_casa(
    pdf: Path,
    pagina: int,
    preparacao: list[Acao],
    acoes: list[Acao],
    notas: list[str],
    *,
    sabotar: str,
    detalhes: dict[str, Any],
    modo: str = "casa",
) -> dict[str, Any]:
    if modo == "teclado":
        passou = bool(acoes) and all(a.ok and a.comando for a in acoes) and bool(
            detalhes.get("corrigida")) and bool(detalhes.get("no_teto"))
        portao = (f"OCR_UI ciclo 2, C8 -- corrigir a casa só pelo teclado (Tab até a casa, a letra da "
                  f"peça) em <= {TETO_DE_TECLAS_POR_CASA} teclas")
    elif modo == "frio":
        passou = bool(detalhes.get("no_teto"))
        portao = (f"OCR_UI ciclo 2, C2 -- clique em Ler → primeiro diagrama na lista em <= "
                  f"{TETO_FRIO_S:.0f} s num processo novo")
    elif modo == "cancelar":
        passou = bool(detalhes.get("cancelou"))
        portao = "OCR_UI ciclo 2, C2 -- cancelar pelo rodapé para a leitura entre diagramas"
    else:
        passou = (
            bool(acoes)
            and len(acoes) <= TETO_DE_ACOES_DA_CASA
            and all(a.ok and a.comando for a in acoes)
            and bool(detalhes.get("corrigida"))
            and bool(detalhes.get("sem_zoom"))
            and bool(detalhes.get("recorte_focavel"))
        )
        portao = (
            "OCR_UI passo 13 -- corrigir uma casa errada (casa no recorte → peça → aplicar) em <= "
            f"{TETO_DE_ACOES_DA_CASA} acoes, sem zoom na pagina"
        )
    return {
        "portao": portao,
        "modo": modo,
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "amostra": {"pdf": str(pdf), "pagina": pagina},
        "sabotagem": sabotar,
        "preparacao": [asdict(a) for a in preparacao],
        "acoes": [asdict(a) for a in acoes],
        "detalhes": detalhes,
        "notas": notas,
        "veredito": "PASSOU" if passou else "REPROVOU",
    }


def tabela_da_casa(relatorio: dict[str, Any]) -> str:
    amostra = relatorio["amostra"]
    linhas = [
        relatorio["portao"],
        f"Livro: {Path(amostra['pdf']).name}, pagina {amostra['pagina']}"
        + (f"  [sabotagem: {relatorio['sabotagem']}]" if relatorio["sabotagem"] else ""),
        "",
        "  preparacao (nao conta):",
    ]
    for a in relatorio["preparacao"]:
        marca = "ok" if a["ok"] else "!!"
        linhas.append(
            f"    {marca} {a['nome']:<52} [{a['comando']:<18}] "
            f"{a['espera_ms']:8.0f} ms  {a['resultado']}"
        )
    linhas.append("  acoes:")
    for a in relatorio["acoes"]:
        marca = "ok" if a["ok"] and a["comando"] else "!!"
        linhas.append(
            f"    {marca} {a['numero']}. {a['nome']:<49} [{a['comando']:<18}] "
            f"{a['espera_ms']:8.0f} ms  {a['resultado']}"
        )
    d = relatorio["detalhes"]
    if d:
        linhas.append("")
        linhas.append("  " + ", ".join(f"{k}={v}" for k, v in d.items()))
    linhas.extend(f"  nota: {nota}" for nota in relatorio["notas"])
    linhas.append(
        f"\n  Veredito: {relatorio['veredito']} "
        f"({len(relatorio['acoes'])} acoes, teto {TETO_DE_ACOES_DA_CASA})"
    )
    return "\n".join(linhas)


def _relatorio(pdf: Path, paginas: str, percurso: Percurso, sabotar: str = "") -> dict[str, Any]:
    return {
        "portao": (
            "OCR_UI passo 17 -- abrir → primeira duvidosa → corrigir → exportar em <= "
            f"{TETO_DE_ACOES} acoes; cancelar a 30 % devolve 30 % das paginas; "
            "C2 A2: diagramas >= 1 na importacao; C2 A3: decisao gravada (FEN != lida) e o "
            "EPUB traz o Diagram corrigido"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "amostra": {"pdf": str(pdf), "paginas": paginas},
        "sabotagem": sabotar,
        "acoes": [asdict(a) for a in percurso.acoes],
        "cancelamento": percurso.cancelamento,
        "diagramas": percurso.diagramas,
        "decisao": percurso.decisao,
        "trilho": percurso.trilho,
        "conteudo": percurso.conteudo,
        "exportado": percurso.exportado,
        "notas": percurso.notas,
        "veredito": "PASSOU" if percurso.passou() else "REPROVOU",
    }


def tabela(relatorio: dict[str, Any]) -> str:
    amostra = relatorio["amostra"]
    linhas = [
        relatorio["portao"],
        f"Livro: {Path(amostra['pdf']).name}, paginas {amostra['paginas']}",
        "",
    ]
    for a in relatorio["acoes"]:
        marca = "ok" if a["ok"] and a["comando"] else "!!"
        linhas.append(
            f"  {marca} {a['numero']}. {a['nome']:<40} [{a['comando']:<18}] "
            f"{a['espera_ms']:8.0f} ms  {a['resultado']}"
        )
    c = relatorio["cancelamento"]
    if c:
        linhas.append("")
        linhas.append("  cancelamento a 30 %: " + ", ".join(f"{k}={v}" for k, v in c.items()))
    for chave, titulo in (
        ("diagramas", "diagramas na importacao (A2)"),
        ("decisao", "decisao gravada (A3)"),
        ("conteudo", "conteudo do EPUB (A3)"),
        ("trilho", "o trilho aprende (C8)"),
    ):
        valores = relatorio.get(chave) or {}
        if valores:
            linhas.append(f"  {titulo}: " + ", ".join(f"{k}={v}" for k, v in valores.items()))
    if relatorio.get("sabotagem"):
        linhas.append(f"  sabotagem: {relatorio['sabotagem']}")
    if relatorio["exportado"]:
        linhas.append(f"  exportado: {relatorio['exportado']}")
    linhas.extend(f"  nota: {nota}" for nota in relatorio["notas"])
    linhas.append(
        f"\n  Veredito: {relatorio['veredito']} "
        f"({len(relatorio['acoes'])} acoes, teto {TETO_DE_ACOES})"
    )
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Os percursos declarados, em acoes (OCR_UI passos 13 e 17)."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--fluxo", choices=("livro", "casa"), default="livro")
    parser.add_argument(
        "--paginas", default="1-8", help="[livro] intervalo base 1 a importar (padrao: 1-8)"
    )
    parser.add_argument(
        "--pagina", type=int, default=41, help="[casa] a pagina com diagrama (base 1)"
    )
    parser.add_argument(
        "--sabotar",
        choices=("", "sem_sincronia", "sem_decisao", "sem_raster", "sem_gancho",
                 "sem_teclado", "sem_aquecimento", "sem_cancelamento"),
        default="",
        help="[casa] sem_sincronia, sem_teclado (--teclado), sem_aquecimento (--frio), "
             "sem_cancelamento (--cancelar); [livro] sem_decisao (exporta sem aplicar), sem_raster",
    )
    parser.add_argument("--teclado", action="store_true", help="[casa] a correção só pelo teclado (C8)")
    parser.add_argument("--frio", action="store_true", help="[casa] clique em Ler → primeiro diagrama (C2)")
    parser.add_argument("--cancelar", action="store_true", help="[casa] cancelar a leitura pelo rodapé (C2)")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--limite-s", type=float, default=900.0)
    args = parser.parse_args(argv)

    if args.fluxo == "casa":
        relatorio = medir_casa(
            args.pdf, pagina=args.pagina, caminho_do_tronco=args.tronco,
            limite_s=min(args.limite_s, 300.0), sabotar=args.sabotar,
            teclado=args.teclado, frio=args.frio, cancelar=args.cancelar,
        )
        nome = "percurso_casa" + ("_" + relatorio["modo"] if relatorio["modo"] != "casa" else "") + (
            f"_sabotado_{args.sabotar}" if args.sabotar else "")
        args.saida.mkdir(parents=True, exist_ok=True)
        alvo = args.saida / f"{nome}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        print(tabela_da_casa(relatorio))
        print(f"\nRelatorio: {alvo}")
        return 0 if relatorio["veredito"] == "PASSOU" else 1

    if args.sabotar == "sem_sincronia":
        parser.error("--sabotar sem_sincronia é do fluxo casa")
    relatorio = medir(
        args.pdf, paginas=args.paginas, caminho_do_tronco=args.tronco, limite_s=args.limite_s,
        sabotar=args.sabotar,
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    nome = "percurso" + (f"_sabotado_{args.sabotar}" if args.sabotar else "")
    alvo = args.saida / f"{nome}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    sys.exit(main())
