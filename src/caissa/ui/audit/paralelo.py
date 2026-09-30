r"""O fluxo `paralelo`: corrigir um diagrama **enquanto** o livro é importado (OCR_UI C2, passo C7).

**O que o portão mede.** A importação do livro trancava a janela inteira -- `controles.emit(False)`
chegava a `janela._trancar`, que fazia `abas.setEnabled(False)` (análise §6.4) -- e a pessoa
esperava minutos de OCR sem poder tocar no diagrama que já estava lido na tela. Desde C7 a
importação não tranca as abas nem o editor: só lê o PDF, e ler o PDF não é recurso que a correção
de uma casa dispute. O arnês prova isso do jeito mais direto: começa a importação de oito páginas
e, **um segundo depois**, com a importação ainda correndo, clica na caixa de uma página já lida
(`clicar_na_caixa`) e aplica uma peça numa casa do tabuleiro (`aplicar`). PASSOU se a casa mudou
com a importação viva; a importação é cancelada em seguida, porque o portão é sobre a edição e não
sobre o OCR.

**A sabotagem** (`--sabotar trancar_tudo`) religa o comportamento antigo -- `controles` →
`abas.setEnabled` -- e a mesma edição não acontece: o botão da paleta e o tabuleiro ficam
desabilitados, o clique não chega, a FEN não muda, e o portão REPROVA. É a prova de que a tranca
seletiva é o que faz a edição valer durante a importação.

**Também fica registrado, como dado:** quantas importações a ponte começou (`Ponte.importacoes`,
que deve ser 1), se a aba *Revisão de texto* recebeu o resultado sem rodar OCR nenhum (o parcial
cancelado também chega a ela), e se ela abriu o mesmo PDF que a janela.

    set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages
    .venv\Scripts\python.exe -m caissa.ui.audit.paralelo --pdf "%PDF%" ^
        --paginas 1-8 --pagina 41 --saida benchmarks\reports\ui\c2_c7 [--sabotar trancar_tudo]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ui.audit.percurso import TRONCO, Acao, _esperar, _paginas, _preparar

ESPERA_ANTES_DE_EDITAR_S = 1.0
"""Quanto a importação corre antes da edição: o «1 s depois» do roadmap."""

__all__ = ["ESPERA_ANTES_DE_EDITAR_S", "medir_paralelo", "tabela_do_paralelo"]


def medir_paralelo(  # noqa: PLR0915 - um percurso, do começo ao fim
    pdf: Path,
    *,
    paginas: str = "1-8",
    pagina: int = 41,
    caminho_do_tronco: Path = TRONCO,
    limite_s: float = 300.0,
    sabotar: str = "",
    outro_livro: Path | None = None,
) -> dict[str, Any]:
    """Importa `paginas` e, 1 s depois, corrige uma casa da página `pagina` (base 1), já lida.

    Com `outro_livro`, o segundo cenário (crítico da fase 1): abrir **outro PDF** durante a
    importação -- a importação é cancelada, o resultado que ainda chega dela é descartado, e
    nem o trilho nem a fila de dúvidas do livro novo recebem o que era do anterior.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.fen_utils import square_name
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.ui import board_edit
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
    detalhes: dict[str, Any] = {}

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

    def encerrar() -> dict[str, Any]:
        if janela.livro is not None and janela.livro.rodando:
            janela.livro.cancelar()
            _esperar(aplicacao, lambda: not janela.livro.rodando, limite_s=limite_s)
        janela.close()
        janela.deleteLater()
        for _ in range(6):
            aplicacao.processEvents()
        temporaria.cleanup()
        return _relatorio(
            pdf, paginas, pagina, preparacao, acoes, notas, sabotar=sabotar, detalhes=detalhes
        )

    if janela.livro is None:
        notas.append("a suíte não está ao alcance da janela: sem importação")
        return encerrar()

    # --- preparação (não conta): abrir, ir à página, ler os diagramas dela pelo clique na caixa
    passo(
        preparacao,
        "abrir o livro",
        "abrir_pdf",
        lambda: janela.abrir_pdf(pdf),
        lambda: aguardar_a_folha(janela) and janela.pdf.page_count > 0,
    )
    alvo = max(0, min(int(pagina) - 1, janela.pdf.page_count - 1))
    passo(
        preparacao,
        f"ir para a página {alvo + 1}",
        "ir_para_pagina",
        lambda: janela.pdf.ir_para_pagina(alvo),
        lambda: janela.pdf.page_index == alvo and aguardar_a_folha(janela),
    )

    def _tem_caixas() -> bool:
        caixas = janela.pdf.boxes
        return caixas is not None and len(caixas.boxes) > 0

    _esperar(aplicacao, _tem_caixas, limite_s=60.0)
    if not _tem_caixas():
        notas.append(f"a página {alvo + 1} não tem caixa de diagrama: escolha outra com --pagina")
        return encerrar()

    def _leitura_terminou() -> bool:
        return not janela._leitura_adiada.isActive() and janela._tarefa is None

    passo(
        preparacao,
        "ler a página pelo clique na caixa",
        "clicar_na_caixa",
        lambda: janela.pdf.caixa_clicada.emit(0),
        _leitura_terminou,
    )
    painel = janela.painel
    if not painel.modelo.items:
        notas.append(
            "a página não rendeu diagrama lido: não há o que corrigir durante a importação"
        )
        return encerrar()
    janela.abas.mostrar(painel)
    _esperar(aplicacao, lambda: False, limite_s=0.5)

    if sabotar == "trancar_tudo":
        # O comportamento antigo: a importação tranca a janela inteira (análise §6.4).
        janela.livro.importador.controles.connect(
            lambda liberado: janela.abas.setEnabled(bool(liberado))
        )
        notas.append(
            "sabotagem: `controles` volta a fazer `abas.setEnabled(False)` durante a importação"
        )

    # --- a importação começa, e corre 1 s antes da edição
    indices = _paginas(paginas, janela.pdf.page_count)
    passo(
        preparacao,
        f"começar a importação de {len(indices)} página(s)",
        "importar_livro",
        lambda: janela.livro.comecar(indices),
        lambda: janela.livro.rodando,
        limite=5.0,
    )
    _esperar(aplicacao, lambda: False, limite_s=ESPERA_ANTES_DE_EDITAR_S)
    detalhes["importacao_viva_antes_da_edicao"] = bool(janela.livro.rodando)
    detalhes["abas_habilitadas_durante"] = bool(janela.abas.isEnabled())
    detalhes["editor_habilitado_durante"] = bool(painel.isEnabled())
    if not janela.livro.rodando:
        notas.append(
            "a importação terminou antes de 1 s: o livro é pequeno demais para medir o paralelo"
        )

    # --- 1. clicar na caixa da página já lida (seleciona, não lê de novo)
    fen_antes = painel.modelo.fen_at(0)
    passo(
        acoes,
        "clicar na caixa do diagrama já lido",
        "clicar_na_caixa",
        lambda: janela.pdf.caixa_clicada.emit(0),
        lambda: painel.lista.currentRow() == 0,
        limite=2.0,
    )

    # --- 2. aplicar: peça na paleta, clique na casa
    casa = 27  # d4: uma casa do meio; a peça aplicada é a que ela não tem
    simbolo = "Q" if board_edit.piece_at(fen_antes, casa) != "Q" else "q"
    botao = painel.paleta._botoes[simbolo]
    linha, coluna = painel.tabuleiro.modelo.display_from_index(casa)
    x0, y0, x1, y1 = painel.tabuleiro.geometria().rect(linha, coluna)
    centro = QPoint(int((x0 + x1) / 2), int((y0 + y1) / 2))

    def _aplicar() -> None:
        botao.click()
        aplicacao.processEvents()
        QTest.mouseClick(
            painel.tabuleiro, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centro
        )
        aplicacao.processEvents()

    def _pintou() -> bool:
        return board_edit.piece_at(painel.modelo.fen_at(0), casa) == simbolo

    inicio = time.perf_counter()
    passo(
        acoes, f"aplicar {simbolo} em {square_name(casa)}", "aplicar", _aplicar, _pintou, limite=2.0
    )
    detalhes["importacao_viva_na_edicao"] = bool(janela.livro.rodando)
    detalhes["edicao_ms_apos_inicio"] = round((time.perf_counter() - inicio) * 1000.0, 1)
    detalhes["casa"] = square_name(casa)
    detalhes["corrigida"] = _pintou()
    detalhes["fen_mudou"] = painel.modelo.fen_at(0) != fen_antes

    # --- o que mais C7 promete, como dado
    detalhes["importacoes_da_ponte"] = int(getattr(janela.livro, "importacoes", 0))
    if outro_livro is not None and janela.livro.rodando:
        # Trocar de livro a meio da importação: a janela cancela, a ponte descarta (C7).
        anterior = janela._pdf
        marcas_antes = len(getattr(janela.trilho, "_marcas", {}) or {})
        # A13: o rodapé, frase a frase, do momento da troca até o relatório chegar -- para
        # acusar a promessa («podem ser exportadas») seguida do descarte («descartada»).
        frases: list[str] = []
        mostrar_original = janela.rodape.mostrar

        def mostrar_e_anotar(texto: str, **kwargs: Any) -> None:
            frases.append(str(texto))
            mostrar_original(texto, **kwargs)

        janela.rodape.mostrar = mostrar_e_anotar  # type: ignore[method-assign]
        if sabotar == "rodape_duplo":
            # O antes do A13: o importador promete exportar o que o descarte vai jogar fora.
            importador = getattr(janela.livro, "importador", None)
            if importador is not None:
                cancelar_original = importador.cancelar
                importador.cancelar = lambda *, motivo="": cancelar_original()  # type: ignore[method-assign]
                notas.append("sabotagem: o cancelamento por troca de livro chega sem motivo ao importador")
        passo(
            acoes,
            f"abrir outro livro ({outro_livro.name}) durante a importação",
            "abrir_pdf",
            lambda: janela.pdf.load_pdf(outro_livro),
            lambda: janela._pdf == outro_livro,
            limite=30.0,
        )
        if sabotar == "sem_descarte":
            # O comportamento antigo: a ponte atribuía o resultado ao livro **atual** -- o
            # relatório de A vira trilho e fila de B.  Fingir que a importação era de B.
            janela.livro._pdf_importado = outro_livro
            notas.append("sabotagem: a ponte toma o resultado da importação como sendo do livro novo")
        _esperar(aplicacao, lambda: not janela.livro.rodando, limite_s=limite_s)
        _esperar(aplicacao, lambda: False, limite_s=1.0)
        revisao = getattr(janela, "revisao_de_texto", None)
        fila = getattr(revisao, "queue", None) if revisao is not None else None
        fila_do_anterior = bool(fila and fila.items and fila.items[0].document == anterior.stem)
        janela.rodape.mostrar = mostrar_original  # type: ignore[method-assign]
        promessa = [f for f in frases if "podem ser exportadas" in f]
        descarte = [f for f in frases if "descartada" in f]
        detalhes["troca_de_livro"] = {
            "anterior": anterior.name,
            "novo": outro_livro.name,
            "rodape_frases": frases,
            # A13: sem a promessa de exportar o que foi descartado -- um rodapé só.
            "rodape_sem_contradicao": not (promessa and descarte),
            "resultado_descartado": janela.livro.resultado is None,
            "trilho_sem_estados_do_anterior": len(getattr(janela.trilho, "_marcas", {}) or {}) <= marcas_antes,
            "fila_nao_e_do_anterior": not fila_do_anterior,
            "revisao_no_livro_novo": (getattr(revisao, "pdf", None) == outro_livro) if revisao is not None else True,
        }
        return encerrar()
    janela.livro.cancelar()
    _esperar(
        aplicacao,
        lambda: not janela.livro.rodando and janela.livro.resultado is not None,
        limite_s=limite_s,
    )
    revisao = getattr(janela, "revisao_de_texto", None)
    detalhes["revisao_de_texto_montada"] = revisao is not None
    if revisao is not None:
        detalhes["revisao_de_texto_mesmo_pdf"] = getattr(revisao, "pdf", None) == janela._pdf
        detalhes["revisao_de_texto_recebeu_a_fila"] = getattr(revisao, "queue", None) is not None
        detalhes["revisao_de_texto_importou_sozinha"] = bool(
            getattr(revisao.importador, "rodando", False)
        )
    return encerrar()


def _relatorio(
    pdf: Path,
    paginas: str,
    pagina: int,
    preparacao: list[Acao],
    acoes: list[Acao],
    notas: list[str],
    *,
    sabotar: str,
    detalhes: dict[str, Any],
) -> dict[str, Any]:
    passou = (
        bool(acoes)
        and all(a.ok and a.comando for a in acoes)
        and bool(detalhes.get("importacao_viva_antes_da_edicao"))
        and bool(detalhes.get("importacao_viva_na_edicao"))
        and bool(detalhes.get("corrigida"))
        and bool(detalhes.get("abas_habilitadas_durante"))
        and bool(detalhes.get("editor_habilitado_durante"))
        and all(v for v in detalhes.get("troca_de_livro", {"ok": True}).values() if isinstance(v, bool))
    )
    return {
        "portao": (
            "OCR_UI C2 passo C7 -- corrigir uma casa (clicar_na_caixa → aplicar) com a importacao "
            "do livro em curso, 1 s depois de ela comecar; as abas e o editor continuam habilitados"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "amostra": {"pdf": str(pdf), "paginas": paginas, "pagina_lida": pagina},
        "sabotagem": sabotar,
        "preparacao": [asdict(a) for a in preparacao],
        "acoes": [asdict(a) for a in acoes],
        "detalhes": detalhes,
        "notas": notas,
        "veredito": "PASSOU" if passou else "REPROVOU",
    }


def tabela_do_paralelo(relatorio: dict[str, Any]) -> str:
    amostra = relatorio["amostra"]
    linhas = [
        relatorio["portao"],
        f"Livro: {Path(amostra['pdf']).name}, importando {amostra['paginas']}, editando a pagina "
        f"{amostra['pagina_lida']}"
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
    linhas.append("  acoes (com a importacao em curso):")
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
    linhas.append(f"\n  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Corrigir um diagrama com a importacao do livro em curso (OCR_UI C2, passo C7)."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument(
        "--paginas", default="1-8", help="intervalo base 1 a importar (padrao: 1-8)"
    )
    parser.add_argument(
        "--pagina", type=int, default=41, help="a pagina com diagrama a corrigir (base 1)"
    )
    parser.add_argument("--sabotar", choices=("", "trancar_tudo", "sem_descarte", "rodape_duplo"), default="")
    parser.add_argument(
        "--outro-livro", type=Path, default=None,
        help="abrir este PDF durante a importação: o resultado dela não pode virar trilho nem fila do livro novo",
    )
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--limite-s", type=float, default=300.0)
    args = parser.parse_args(argv)

    relatorio = medir_paralelo(
        args.pdf,
        paginas=args.paginas,
        pagina=args.pagina,
        caminho_do_tronco=args.tronco,
        limite_s=args.limite_s,
        sabotar=args.sabotar,
        outro_livro=args.outro_livro,
    )
    nome = "paralelo" + ("_sabotado" if args.sabotar else "") + ("_troca" if args.outro_livro else "")
    args.saida.mkdir(parents=True, exist_ok=True)
    alvo = args.saida / f"{nome}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela_do_paralelo(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    sys.exit(main())
