r"""O editor de código nativo aguenta, com tudo ligado? — o portão de desempenho do passo H2 (D4).

O protótipo (`caissa.ui.widgets.editor_de_codigo`) tem todas as funções da spec S5 ligadas ao mesmo
tempo; este arnês mede, com o pulso do `caissa.ui.audit.bloqueio` (um `QTimer` de 4 ms na thread
da janela: o vão entre dois disparos é o tempo em que ninguém atendeu o laço), as operações que o
roadmap H2 nomeia:

- **abrir** 50 KB, 500 KB e 2 MB — o pior bloqueio, o tempo até o **visível realçado** (toda linha
  à vista com cor, com o estado de entrada confirmado) e até o realce completo;
- **digitar** 60 s a 30 caracteres/s num arquivo de 500 KB com tudo ligado: 500 indicadores, três
  regiões dobradas, o completar abrindo, o fecho de tag, a prévia MuPDF pedida ao processo de
  trabalho;
- **dobrar e desdobrar tudo** em 500 KB;
- **desfazer** 100 passos;
- **colar** 100 KB;
- **trocar a escala** (150 %, 200 %, de volta);
- **primeira pintura** de um projeto de 300 capítulos pequenos (o livro do pedido, p. 1–300, pelo
  `XhtmlBuilder` de hoje): a lista dos 300 arquivos lida e o primeiro capítulo à vista, realçado.

**O portão:** pior bloqueio ≤ 16 ms em toda operação; visível realçado ≤ 50 ms; primeira pintura
≤ 800 ms. **A prova de atividade:** em cada medida os contadores do protótipo mostram as funções
ligadas (500 seleções extras, dobras recolhidas, o completar aberto, 100 passos de desfazer,
pedidos e respostas da prévia, a escala aplicada); uma medida com contador zerado é **inválida** e
reprova.

**Sabotagens** (`--sabotar`): `realce_sincrono` (o documento inteiro realçado de uma vez, como o
`rehighlight()`: o bloqueio estoura) e `funcoes_desligadas` (indicadores, dobras e prévia
desligados: a prova de atividade invalida a medida).

O capítulo de verdade vem do livro do pedido, importado sem OCR e sem detecção raster (só o texto e
a estrutura interessam aqui) e guardado em `benchmarks/reports/editor/fixtures/pedido_300/` — o git
ignora a pasta; o acervo não sai da máquina.

Uso (o PyQt6 vem do `.venv-pack`)::

    . .\benchmarks\editor_ambiente.ps1; Enter-AmbienteDosTestesQt
    & $PY benchmarks\editor_codigo.py --saida benchmarks\reports\editor\h2\1
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import random
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

ORCAMENTO_MS = 16.0
VISIVEL_MS = 50.0
PRIMEIRA_PINTURA_MS = 800.0
DIGITACAO_S = 60.0
CARACTERES_POR_S = 30
KB = 1024
SEMENTE = 42
SABOTAGENS = ("realce_sincrono", "funcoes_desligadas")

TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
    "<head>\n<title>{titulo}</title>\n"
    '<link rel="stylesheet" type="text/css" href="../Styles/livro.css"/>\n'
    "</head>\n<body>\n<section>\n{corpo}\n</section>\n</body>\n</html>\n"
)


# --------------------------------------------------------------------------- #
# O capítulo de verdade
# --------------------------------------------------------------------------- #


def _principal() -> Path:
    import subprocess

    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def livro_do_pedido() -> Path:
    pasta = _principal().parent / "ChessVisionOFF_Puro" / "PDF"
    achados = sorted(p for p in pasta.glob("*.pdf")
                     if fnmatch.fnmatch(p.name, "A Matter of Endgame Technique*Jacob Aagaard.pdf"))
    if not achados:
        raise FileNotFoundError(f"o livro do pedido não está em {pasta}")
    return achados[0]


def fixture_de_300(pasta: Path | None = None) -> Path:
    """Os 300 capítulos (uma página do pedido cada), gerados uma vez e guardados."""
    destino = pasta or RAIZ / "benchmarks" / "reports" / "editor" / "fixtures" / "pedido_300"
    if len(list(destino.glob("cap-*.xhtml"))) == 300:
        return destino
    from caissa.export.base import ExportContext, ExportOptions
    from caissa.export.html import HTML_PROFILE, XhtmlBuilder
    from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf

    livro = livro_do_pedido()
    resultado = import_pdf(livro, PdfImportOptions(pages=list(range(300)), enable_ocr=False,
                                                   detect_raster_diagrams=False))
    documento = resultado.document
    construtor = XhtmlBuilder(ExportContext(HTML_PROFILE, documento, ExportOptions()), epub=True)
    por_pagina: dict[int, list[Any]] = {}
    ultima = 0
    for bloco in documento.body:
        proveniencia = getattr(bloco, "provenance", None)
        if proveniencia is not None and proveniencia.page_index is not None:
            ultima = int(proveniencia.page_index)
        por_pagina.setdefault(ultima, []).append(bloco)
    (destino / "OEBPS" / "Text").mkdir(parents=True, exist_ok=True)
    destino.mkdir(parents=True, exist_ok=True)
    for numero in range(300):
        corpo = construtor.blocks(tuple(por_pagina.get(numero, ())))
        texto = TEMPLATE.format(titulo=f"Página {numero + 1}", corpo=corpo)
        (destino / f"cap-{numero + 1:03d}.xhtml").write_text(texto, encoding="utf-8")
    return destino


def texto_de(tamanho: int, capitulos: Path) -> str:
    """Um arquivo de ~`tamanho` bytes feito dos corpos dos capítulos de verdade, em ordem."""
    corpos = []
    total = 0
    arquivos = sorted(capitulos.glob("cap-*.xhtml"))
    indice = 0
    while total < tamanho:
        texto = arquivos[indice % len(arquivos)].read_text(encoding="utf-8")
        corpo = texto.split("<section>\n", 1)[1].rsplit("\n</section>", 1)[0]
        corpos.append(corpo)
        total += len(corpo.encode("utf-8"))
        indice += 1
    return TEMPLATE.format(titulo="Capítulo de medida", corpo="\n".join(corpos))


# --------------------------------------------------------------------------- #
# O laço de eventos sem espera ocupada
# --------------------------------------------------------------------------- #


def esperar(condicao: Callable[[], bool], limite_s: float) -> float | None:
    """Roda o laço até `condicao()` ou o limite; devolve os segundos, ou `None` sem chegar.

    Um `QEventLoop` com um temporizador de conferência, e não `processEvents` com `sleep`: o sono
    do Python seria contado como bloqueio pelo pulso.
    """
    from PyQt6.QtCore import QEventLoop, QTimer

    inicio = time.perf_counter()
    if condicao():
        return 0.0
    laco = QEventLoop()
    resultado: list[float] = []

    def conferir() -> None:
        if condicao():
            resultado.append(time.perf_counter() - inicio)
            laco.quit()
        elif time.perf_counter() - inicio > limite_s:
            laco.quit()

    relogio = QTimer()
    relogio.setInterval(2)
    relogio.timeout.connect(conferir)
    relogio.start()
    laco.exec()
    relogio.stop()
    return resultado[0] if resultado else None


def rodar_por(segundos: float) -> None:
    from PyQt6.QtCore import QEventLoop, QTimer

    laco = QEventLoop()
    QTimer.singleShot(int(segundos * 1000), laco.quit)
    laco.exec()


# --------------------------------------------------------------------------- #
# As operações
# --------------------------------------------------------------------------- #


class Medidor:
    """O pulso do `bloqueio`, zerado a cada operação; guarda o pior e o total de cada uma."""

    def __init__(self) -> None:
        from caissa.ui.audit.bloqueio import Vigia

        self.vigia = Vigia(amostrar=True).ligar()
        self.operacoes: dict[str, dict[str, Any]] = {}

    def medir(self, nome: str, corpo: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
        self.vigia.zerar(nome)
        extra = corpo() or {}
        resumo = self.vigia.resumo(nome)
        pior = [
            {"ms": round(t.duracao_ms, 1), "pilha": list(t.pilha[-4:])}
            for t in sorted(self.vigia.travamentos, key=lambda t: -t.duracao_ms)[:3]]
        dados = {"pior_ms": round(resumo.pior_ms, 2), "pulsos": resumo.pulsos,
                 "travamentos": resumo.travamentos,
                 "total_bloqueado_ms": round(resumo.total_bloqueado_ms, 1), "piores": pior, **extra}
        self.operacoes[nome] = dados
        print(f"  {nome}: pior {dados['pior_ms']} ms, {resumo.travamentos} acima de "
              f"{ORCAMENTO_MS:g} ms" + "".join(f", {k}={v}" for k, v in extra.items()
                                                 if not isinstance(v, (dict, list))), flush=True)
        return dados

    def desligar(self) -> None:
        self.vigia.desligar()


def _funcoes(sabotagem: str | None) -> frozenset[str]:
    from caissa.ui.widgets.editor_de_codigo import FUNCOES

    if sabotagem == "funcoes_desligadas":
        return FUNCOES - {"indicadores", "dobras", "previa"}
    return FUNCOES


def _editor(previa: Any, sabotagem: str | None) -> Any:
    from caissa.ui.widgets.editor_de_codigo import EditorDeCodigo

    editor = EditorDeCodigo(funcoes=_funcoes(sabotagem), classes_do_projeto=("cb-movetext",))
    if editor.realce is not None and sabotagem == "realce_sincrono":
        editor.realce.sincrono = True
    if previa is not None and "previa" in editor.funcoes:
        editor.pedir_previa.connect(previa.pedir)
        previa.pronta.connect(editor.previa_recebida)
    editor.resize(1100, 800)
    editor.show()
    esperar(lambda: False, 0.05)
    return editor


def _pronto(editor: Any) -> bool:
    dobras_ok = editor.dobras is None or not editor.dobras.ocupado
    realce_ok = editor.realce is None or editor.realce.completo
    return not editor.carregando and realce_ok and dobras_ok


def abrir(medidor: Medidor, previa: Any, texto: str, nome: str,
          sabotagem: str | None) -> Any:
    editor = _editor(previa, sabotagem)

    def corpo() -> dict[str, Any]:
        inicio = time.perf_counter()
        editor.carregar(texto)
        carga = time.perf_counter() - inicio          # o primeiro pedaço, na chamada
        visivel = esperar(lambda: editor.realce is not None and editor.realce.visivel_realcado(),
                          30.0)
        completo = esperar(lambda: _pronto(editor), 120.0)
        return {
            "visivel_ms": None if visivel is None else round((carga + visivel) * 1000, 1),
            "completo_ms": None if completo is None else round(
                (time.perf_counter() - inicio) * 1000, 1),
            "bytes": len(texto.encode("utf-8")), "linhas": editor.blockCount()}

    medidor.medir(nome, corpo)
    return editor


def digitar(medidor: Medidor, previa: Any, texto: str, sabotagem: str | None,
            *, segundos: float) -> Any:
    """60 s a 30 caracteres/s, no meio do arquivo, com tudo ligado."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtTest import QTest

    editor = _editor(previa, sabotagem)
    editor.carregar(texto)
    esperar(lambda: _pronto(editor), 120.0)
    tamanho = len(editor.toPlainText())
    editor.definir_indicadores([
        (int(n * tamanho / 520), int(n * tamanho / 520) + 6, "problema" if n % 2 else "duvida")
        for n in range(500)])
    if editor.dobras is not None:
        regioes = sorted(editor.dobras.regioes)
        for linha in regioes[len(regioes) // 4:len(regioes) // 4 + 3]:
            editor.dobras.dobrar(linha)
    meio = editor.document().findBlockByNumber(editor.blockCount() // 2)
    from PyQt6.QtGui import QTextCursor

    cursor = QTextCursor(meio)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    editor.setTextCursor(cursor)
    sorteio = random.Random(SEMENTE)
    roteiro = []
    while len(roteiro) < int(segundos * CARACTERES_POR_S):
        escolha = sorteio.random()
        if escolha < 0.05:
            roteiro.extend("<p>")
        elif escolha < 0.08:
            roteiro.extend("<em>xy</")
        elif escolha < 0.10:
            roteiro.append("\n")
        elif escolha < 0.25:
            roteiro.append(" ")
        else:
            roteiro.append(sorteio.choice("abcdefghijklmnoprstuvxz"))
    roteiro = roteiro[: int(segundos * CARACTERES_POR_S)]
    fila = list(reversed(roteiro))

    def tecla() -> None:
        if not fila:
            relogio.stop()
            return
        caractere = fila.pop()
        if caractere == "\n":
            QTest.keyClick(editor, 0x01000004)          # Qt.Key.Key_Return
        else:
            QTest.keyClicks(editor, caractere)

    relogio = QTimer()
    relogio.setInterval(int(1000 / CARACTERES_POR_S))
    relogio.timeout.connect(tecla)

    def corpo() -> dict[str, Any]:
        relogio.start()
        esperar(lambda: not fila and not relogio.isActive(), segundos + 30)
        rodar_por(0.5)
        return {"teclas": len(roteiro)}

    medidor.medir("digitar_500kb_tudo_ligado", corpo)
    if previa is not None:
        esperar(lambda: editor.contadores.previas_recebidas > 0, 120.0)
    return editor


def dobrar_tudo(medidor: Medidor, editor: Any) -> None:
    def corpo() -> dict[str, Any]:
        if editor.dobras is None:
            return {"recolhidas": 0}
        editor.dobras.dobrar_tudo()
        esperar(lambda: not editor.dobras.ocupado, 60.0)
        recolhidas = len(editor.dobras.recolhidas)
        editor.dobras.desdobrar_tudo()
        esperar(lambda: not editor.dobras.ocupado, 60.0)
        return {"recolhidas": recolhidas}

    medidor.medir("dobrar_e_desdobrar_tudo", corpo)


def desfazer_100(medidor: Medidor, editor: Any) -> None:
    from PyQt6.QtGui import QTextCursor

    sorteio = random.Random(SEMENTE)
    for numero in range(100):
        bloco = editor.document().findBlockByNumber(sorteio.randrange(editor.blockCount()))
        cursor = QTextCursor(bloco)
        cursor.insertText(f"[{numero}]")
    esperar(lambda: False, 0.2)
    passos = editor.document().availableUndoSteps()

    def corpo() -> dict[str, Any]:
        for _ in range(100):
            editor.undo()
            esperar(lambda: False, 0.005)
        return {"passos_de_desfazer": passos}

    medidor.medir("desfazer_100", corpo)


def colar_100kb(medidor: Medidor, editor: Any, texto: str) -> None:
    from PyQt6.QtCore import QMimeData

    dados = QMimeData()
    dados.setText(texto[: 100 * KB])

    def corpo() -> dict[str, Any]:
        editor.insertFromMimeData(dados)
        esperar(lambda: _pronto(editor), 60.0)
        return {"colados": len(dados.text())}

    medidor.medir("colar_100kb", corpo)


def trocar_escala(medidor: Medidor, editor: Any) -> None:
    def corpo() -> dict[str, Any]:
        for fator in (1.5, 2.0, 1.0):
            editor.aplicar_escala(fator)
            esperar(lambda: False, 0.1)
        return {"escalas": 3}

    medidor.medir("trocar_escala", corpo)


def primeira_pintura(medidor: Medidor, previa: Any, capitulos: Path,
                     sabotagem: str | None) -> float | None:
    """A lista dos 300 capítulos e o primeiro à vista, realçado — como a janela vai abrir."""
    resultado: list[float | None] = []

    def corpo() -> dict[str, Any]:
        inicio = time.perf_counter()
        arquivos = sorted(capitulos.glob("cap-*.xhtml"))
        tamanhos = {a.name: a.stat().st_size for a in arquivos}
        editor = _editor(previa, sabotagem)
        editor.carregar(arquivos[0].read_text(encoding="utf-8"))
        chegou = esperar(lambda: editor.realce is not None and editor.realce.visivel_realcado(),
                         10.0)
        editor.viewport().repaint()
        resultado.append(None if chegou is None else (time.perf_counter() - inicio) * 1000)
        return {"capitulos": len(tamanhos),
                "primeira_pintura_ms": None if chegou is None else round(resultado[0], 1)}

    medidor.medir("primeira_pintura_300", corpo)
    return resultado[0]


# --------------------------------------------------------------------------- #
# O portão
# --------------------------------------------------------------------------- #


def prova_de_atividade(contadores: dict[str, float], sabotagem: str | None) -> list[str]:
    """Os contadores que uma medida válida exige acesos (roadmap H2)."""
    exigidos = {
        "selecoes_extras": 500, "dobras_recolhidas": 1, "completar_aberto": 1,
        "tags_fechadas": 1, "pedidos_de_previa": 1, "previas_recebidas": 1, "blocos_formatados": 1,
        "passos_de_desfazer": 100,
    }
    faltas = [f"{nome} = {contadores.get(nome, 0):g} (mínimo {minimo})"
              for nome, minimo in exigidos.items() if contadores.get(nome, 0) < minimo]
    if contadores.get("escala_maxima", 1.0) < 2.0:
        faltas.append("a escala de 200 % não foi aplicada")
    del sabotagem
    return faltas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--sabotar", choices=SABOTAGENS, default=None)
    parser.add_argument("--segundos", type=float, default=DIGITACAO_S,
                        help="duração da digitação (o portão usa 60)")
    parser.add_argument("--fixture", type=Path, default=None,
                        help="a pasta dos 300 capítulos (gerada se faltar)")
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    pasta = args.saida.resolve()
    pasta.mkdir(parents=True, exist_ok=True)

    capitulos = fixture_de_300(args.fixture)
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.widgets.editor_de_codigo import PreviaNoProcesso

    _app = QApplication.instance() or QApplication([])
    previa = None if args.sabotar == "funcoes_desligadas" else PreviaNoProcesso()
    medidor = Medidor()
    textos = {nome: texto_de(tamanho, capitulos)
              for nome, tamanho in (("50kb", 50 * KB), ("500kb", 500 * KB), ("2mb", 2048 * KB))}
    try:
        for nome, texto in textos.items():
            editor = abrir(medidor, previa, texto, f"abrir_{nome}", args.sabotar)
            editor.close()
        editor = digitar(medidor, previa, textos["500kb"], args.sabotar,
                         segundos=args.segundos)
        dobrar_tudo(medidor, editor)
        desfazer_100(medidor, editor)
        colar_100kb(medidor, editor, textos["500kb"])
        trocar_escala(medidor, editor)
        contadores = editor.contadores.como_dict()
        contadores["passos_de_desfazer"] = medidor.operacoes["desfazer_100"]["passos_de_desfazer"]
        contadores["escala_maxima"] = 2.0 if contadores.get("escala_aplicada") else 1.0
        primeira = primeira_pintura(medidor, previa, capitulos, args.sabotar)
    finally:
        medidor.desligar()
        if previa is not None:
            previa.encerrar()

    exigencias: dict[str, bool] = {}
    for nome, dados in medidor.operacoes.items():
        exigencias[f"{nome}: pior bloqueio {dados['pior_ms']} ms ≤ {ORCAMENTO_MS:g} ms"] = (
            dados["pior_ms"] <= ORCAMENTO_MS)
    for nome in ("abrir_50kb", "abrir_500kb", "abrir_2mb"):
        visivel = medidor.operacoes[nome]["visivel_ms"]
        exigencias[f"{nome}: visível realçado em {visivel} ms ≤ {VISIVEL_MS:g} ms"] = (
            visivel is not None and visivel <= VISIVEL_MS)
    exigencias[f"primeira pintura de 300 capítulos em {primeira and round(primeira, 1)} ms ≤ "
               f"{PRIMEIRA_PINTURA_MS:g} ms"] = (primeira is not None
                                                 and primeira <= PRIMEIRA_PINTURA_MS)
    faltas = prova_de_atividade(contadores, args.sabotar)
    exigencias["prova de atividade: " + ("todas as funções trabalharam" if not faltas else
                                         "medida inválida: " + "; ".join(faltas))] = not faltas

    registro = {"sabotagem": args.sabotar, "operacoes": medidor.operacoes,
                "contadores": contadores, "exigencias": exigencias,
                "fixture": str(capitulos)}
    (pasta / "codigo.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    metricas = {f"pior_ms_{nome}": dados["pior_ms"] for nome, dados in medidor.operacoes.items()}
    metricas.update({f"visivel_ms_{nome}": medidor.operacoes[nome]["visivel_ms"]
                     for nome in ("abrir_50kb", "abrir_500kb", "abrir_2mb")
                     if medidor.operacoes[nome]["visivel_ms"] is not None})
    if primeira is not None:
        metricas["primeira_pintura_ms"] = round(primeira, 1)
    (pasta / "metricas.json").write_text(json.dumps(metricas, indent=1), encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
