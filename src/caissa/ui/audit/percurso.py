r"""O percurso principal, contado em ações (OCR_UI_ROADMAP passo 17, U6).

**O que se mede.** Abrir o livro → importá-lo → ir à primeira página duvidosa → abrir o primeiro
diagrama dela → gravar a correção → exportar. O portão é **≤ 6 ações**, onde uma ação é um
gesto da pessoa que corresponde a um comando do catálogo ou a um clique no trilho -- e não uma
chamada interna. Cada ação é executada de verdade na janela do tronco, com a suíte ao alcance,
e o relatório diz quanto cada uma esperou.

**E o cancelamento.** R3.5 promete que cancelar a importação a 30 % devolve um documento com
30 % das páginas. O arnês importa duas vezes: a primeira cancela quando a barra passa de 30 %
das páginas montadas e confere o parcial (páginas montadas, `canceled`, estados no trilho); a
segunda vai até o fim e é a que segue para a correção e a exportação.

**Por que um PDF pequeno.** A importação lê a camada de texto e roda OCR onde ela falta; num
scan de 289 páginas isso são horas, e o arnês mede o percurso, não o OCR. `--paginas` limita a
importação a um intervalo (base 1); o padrão são as 8 primeiras.

    set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages
    .venv\Scripts\python.exe -m caissa.ui.audit.percurso --pdf "%PDF%" ^
        --paginas 31-38 --saida benchmarks\reports\ui\c19
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

__all__ = ["TETO_DE_ACOES", "Acao", "medir", "tabela"]


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

    def passou(self) -> bool:
        return (
            len(self.acoes) <= TETO_DE_ACOES
            and all(a.ok and a.comando for a in self.acoes)
            and bool(self.exportado)
            and bool(self.cancelamento.get("ok"))
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


def medir(  # noqa: PLR0915 - um percurso, do começo ao fim
    pdf: Path,
    *,
    paginas: str = "1-8",
    caminho_do_tronco: Path = TRONCO,
    limite_s: float = 900.0,
) -> dict[str, Any]:
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import aguardar_a_folha, estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    temporaria = tempfile.TemporaryDirectory()
    pasta = Path(temporaria.name)
    # **Tudo que a janela grava vai para a pasta temporária**: o estado (a razão de
    # `estado_de_medicao`), o dataset -- o passo 5 chama `salvar`, e a primeira execução deste
    # arnês gravou uma amostra de verdade em `data/labels.csv` e um PNG em `data/samples/` do
    # tronco, revertidos à mão --, a galeria e os estudos. Um portão que escreve no acervo de
    # quem o roda não é um portão.
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
        # 5. gravar a correção (a leitura como está, ou o que a pessoa corrigiu no editor)
        acao(
            "gravar a correção",
            "salvar",
            lambda: janela.painel.salvar_atual(),
            lambda: True,
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
        acao(
            "exportar o livro",
            "exportar_epub",
            lambda: exportador.iniciar(pdf, escolha),
            lambda: not exportador.rodando and destino.exists(),
        )
        if destino.exists():
            percurso.exportado = f"{destino.name} ({destino.stat().st_size} bytes)"

    janela.close()
    janela.deleteLater()
    for _ in range(6):
        aplicacao.processEvents()
    temporaria.cleanup()
    return _relatorio(pdf, paginas, percurso)


def _relatorio(pdf: Path, paginas: str, percurso: Percurso) -> dict[str, Any]:
    return {
        "portao": (
            "OCR_UI passo 17 -- abrir → primeira duvidosa → corrigir → exportar em <= "
            f"{TETO_DE_ACOES} acoes; cancelar a 30 % devolve 30 % das paginas"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "amostra": {"pdf": str(pdf), "paginas": paginas},
        "acoes": [asdict(a) for a in percurso.acoes],
        "cancelamento": percurso.cancelamento,
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
        description="O percurso principal em acoes (OCR_UI passo 17)."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument(
        "--paginas", default="1-8", help="intervalo base 1 a importar (padrao: 1-8)"
    )
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--limite-s", type=float, default=900.0)
    args = parser.parse_args(argv)

    relatorio = medir(
        args.pdf, paginas=args.paginas, caminho_do_tronco=args.tronco, limite_s=args.limite_s
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    alvo = args.saida / f"percurso_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    sys.exit(main())
