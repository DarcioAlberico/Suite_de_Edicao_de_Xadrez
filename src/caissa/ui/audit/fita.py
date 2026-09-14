r"""O portão da fita: rótulo desenhado em todo botão, cabeçalho em toda densidade, hit ≥ 40 px.

**Por que um portão, e não o script do ciclo 12.** Os três números que ficaram abertos do ciclo
15 ao 16 -- 6 de 24 botões sem rótulo, 0 de 5 cabeçalhos na compacta, tinta dos ícones -- vinham
de `benchmarks/reports/ui/c12/c12_fita.py`, que imprimia e não julgava: nenhum critério, nenhum
veredito, nenhuma sabotagem. E o `texto_pintado`, que é portão, **passa** com os seis sem rótulo,
porque mede a tinta de um texto que existe -- um botão sem texto não tem tinta cortada nem coberta.
Este módulo é o portão que faltava (OCR_UI_ROADMAP passo 12).

**As três regras, e de onde vêm:**

* **todo botão da fita tem rótulo desenhado** -- `QToolButton.text()` com pelo menos uma letra.
  A dica de ferramenta **não** conta (R3.4 do `OCR_UI_SPEC.md`): ela só aparece a quem parou o
  ponteiro, e o leitor de tela e o toque não param ponteiro nenhum;
* **o cabeçalho de cada grupo está desenhado em toda densidade e em toda largura** -- um
  `QLabel` visível com o `rotulo` de cada `medidas_da_fita.grupos()`. Até o passo 12 o modo
  compacto o mandava para a dica;
* **hit ≥ 40 px** nos dois eixos de cada botão (44 é o ideal; 40 é o mínimo das regras de detalhe
  do `OCR_UI_ANALISE.md` §6).

**Um processo por arranjo** (pele × densidade), pela razão de `teclado.auditar_as_peles`; cada
processo mede as larguras pedidas, porque é a largura que decide o modo da fita (pleno ou
compacto), e a regra vale nos dois.

**A sabotagem** (`--sabotar rotulo_na_dica`) tira o texto de um botão da janela montada e o
escreve na dica: `texto_pintado` não vê (não há texto a pintar) e este portão tem de acusar
exatamente 1. É a prova de que a régua mede o rótulo, e não a dica.

    ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.fita --saida <pasta>
    ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.fita --saida <pasta> ^
        --sabotar rotulo_na_dica
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: O venv do tronco é 3.10: sem `datetime.UTC`.
UTC = timezone.utc  # noqa: UP017 - o venv do tronco é 3.10
TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
LARGURAS_PADRAO: tuple[int, ...] = (1280, 1366, 1920)
HIT_MINIMO = 40
HIT_IDEAL = 44
SABOTAGENS: tuple[str, ...] = ("rotulo_na_dica",)


# --------------------------------------------------------------------------- #
# A aritmética, sem Qt
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Botao:
    acao: str
    texto: str
    dica: str
    largura: int
    altura: int
    tem_icone: bool

    @property
    def tem_rotulo(self) -> bool:
        """Uma palavra desenhada: ao menos uma letra no texto do botão. A dica não conta."""
        return any(ch.isalpha() for ch in self.texto)

    @property
    def hit_ok(self) -> bool:
        return self.largura >= HIT_MINIMO and self.altura >= HIT_MINIMO


@dataclass
class Medida:
    """Uma largura de um arranjo: o que a fita desenhou."""

    arranjo: str
    largura_da_janela: int
    modo: str
    altura_da_fita: int
    orcamento: int
    botoes: list[Botao] = field(default_factory=list)
    cabecalhos_declarados: tuple[str, ...] = ()
    cabecalhos_visiveis: tuple[str, ...] = ()
    sabotagem: str = ""

    @property
    def sem_rotulo(self) -> list[Botao]:
        return [b for b in self.botoes if not b.tem_rotulo]

    @property
    def hit_pequeno(self) -> list[Botao]:
        return [b for b in self.botoes if not b.hit_ok]

    @property
    def cabecalhos_faltando(self) -> tuple[str, ...]:
        return tuple(c for c in self.cabecalhos_declarados if c not in self.cabecalhos_visiveis)

    @property
    def defeitos(self) -> int:
        return len(self.sem_rotulo) + len(self.hit_pequeno) + len(self.cabecalhos_faltando)

    @property
    def veredito(self) -> str:
        dentro = self.altura_da_fita <= self.orcamento
        return "PASSOU" if self.defeitos == 0 and dentro else "REPROVOU"

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "arranjo": self.arranjo,
            "largura_da_janela": self.largura_da_janela,
            "modo": self.modo,
            "altura_da_fita": self.altura_da_fita,
            "orcamento": self.orcamento,
            "botoes": [asdict(b) for b in self.botoes],
            "total": len(self.botoes),
            "com_rotulo": len(self.botoes) - len(self.sem_rotulo),
            "sem_rotulo": [b.acao for b in self.sem_rotulo],
            "hit_pequeno": [(b.acao, b.largura, b.altura) for b in self.hit_pequeno],
            "hit_abaixo_do_ideal": sum(
                1 for b in self.botoes if min(b.largura, b.altura) < HIT_IDEAL
            ),
            "cabecalhos_declarados": list(self.cabecalhos_declarados),
            "cabecalhos_visiveis": list(self.cabecalhos_visiveis),
            "cabecalhos_faltando": list(self.cabecalhos_faltando),
            "sabotagem": self.sabotagem,
            "defeitos": self.defeitos,
            "veredito": self.veredito,
        }


def veredito(medidas: Iterable[Mapping[str, Any]]) -> str:
    medidas = list(medidas)
    if not medidas:
        return "SEM FITA"
    return "PASSOU" if all(m["veredito"] == "PASSOU" for m in medidas) else "REPROVOU"


# --------------------------------------------------------------------------- #
# Qt: uma passada = um arranjo, todas as larguras
# --------------------------------------------------------------------------- #


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pasta_de_fontes = Path(r"C:\Windows\Fonts")
    if pasta_de_fontes.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(pasta_de_fontes))
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def medir_a_fita(cromo: Any, *, arranjo: str, largura: int, sabotagem: str = "") -> Medida:
    """A fita montada, lida: botões, cabeçalhos, hit. `sabotagem` mexe na janela montada."""
    from chess_diagram_ocr.ui import medidas_da_fita
    from PyQt6.QtWidgets import QLabel, QToolButton

    declarados = tuple(g.rotulo for g in medidas_da_fita.grupos())
    botoes = [b for b in cromo.findChildren(QToolButton) if b.isVisible()]
    if sabotagem == "rotulo_na_dica" and botoes:
        alvo = botoes[0]
        alvo.setToolTip(f"{alvo.text()}\n{alvo.toolTip()}")
        alvo.setText("")
    por_acao = {id(botao): acao for acao, botao in getattr(cromo, "_botoes", {}).items()}
    lidos = [
        Botao(
            acao=por_acao.get(id(b), b.accessibleName() or "?"),
            texto=(b.text() or "").replace("&", ""),
            dica=b.toolTip() or "",
            largura=int(b.width()),
            altura=int(b.height()),
            tem_icone=bool(b.icon().availableSizes()),
        )
        for b in botoes
    ]
    visiveis = tuple(
        r.text() for r in cromo.findChildren(QLabel) if r.isVisible() and r.text() in declarados
    )
    return Medida(
        arranjo=arranjo,
        largura_da_janela=largura,
        modo=str(cromo.modo),
        altura_da_fita=int(cromo.altura_medida()),
        orcamento=int(medidas_da_fita.ORCAMENTO[cromo.modo]),
        botoes=lidos,
        cabecalhos_declarados=declarados,
        cabecalhos_visiveis=visiveis,
        sabotagem=sabotagem,
    )


def medir_uma_passada(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    larguras: Sequence[int] = LARGURAS_PADRAO,
    sabotagem: str = "",
) -> list[dict[str, Any]]:
    """Um arranjo (a pele e a densidade já estão no ambiente), uma janela por largura."""
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt import fita as qt_fita
    from chess_diagram_ocr.qt import icones as qt_icones
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.qt.plataforma import politica_de_escala
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit import teclado
    from caissa.ui.audit.capture import estado_de_medicao, impor_a_fonte_do_produto

    politica_de_escala()
    aplicacao = QApplication.instance() or QApplication(sys.argv[:1])
    impor_a_fonte_do_produto(aplicacao)
    qt_icones.limpar_cache()
    tema.aplicar_tema(aplicacao)
    arranjo = f"{os.environ.get('CVOFF_SKIN', '?')}/{os.environ.get('CVOFF_DENSITY', '?')}"
    saida: list[dict[str, Any]] = []
    for largura in larguras:
        with tempfile.TemporaryDirectory() as temporaria:
            janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(Path(temporaria)))
        janela.show()
        janela.resize(int(largura), 768)
        if pdf is not None and Path(pdf).exists():
            janela.abrir_pdf(Path(pdf))
        for _ in range(8):
            aplicacao.processEvents()
        cromo = janela.findChild(qt_fita.Fita)
        if cromo is not None:
            medida = medir_a_fita(cromo, arranjo=arranjo, largura=int(largura), sabotagem=sabotagem)
            saida.append(medida.como_dicionario())
        teclado._descartar(janela, aplicacao)
    return saida


def auditar_as_peles(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    saida: Path,
    larguras: Sequence[int] = LARGURAS_PADRAO,
    sabotagem: str = "",
) -> dict[str, Any]:
    """O portão inteiro: um processo por pele × densidade."""
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    saida.mkdir(parents=True, exist_ok=True)
    medidas: list[dict[str, Any]] = []
    for registro in pele.PELES:
        for densidade in pele.DENSIDADES:
            carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            alvo = saida / f"fita_{registro.nome}_{densidade}_{carimbo}.json"
            ambiente = dict(os.environ)
            ambiente["CVOFF_SKIN"] = registro.nome
            ambiente["CVOFF_DENSITY"] = densidade
            argumentos = [
                sys.executable, "-m", "caissa.ui.audit.fita", "--uma-passada",
                "--tronco", str(caminho_do_tronco), "--json", str(alvo),
                "--larguras", ",".join(str(w) for w in larguras),
            ]
            if pdf is not None:
                argumentos += ["--pdf", str(pdf)]
            if sabotagem:
                argumentos += ["--sabotar", sabotagem]
            subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
            if not alvo.exists():
                raise RuntimeError(
                    f"o arranjo {registro.nome}/{densidade} nao produziu relatorio: o "
                    f"subprocesso morreu antes de escrever {alvo}."
                )
            medidas.extend(json.loads(alvo.read_text(encoding="utf-8")))
    return {
        "portao": (
            "Fita: todo botao com rotulo desenhado (a dica nao conta), cabecalho de grupo em toda "
            f"densidade e largura, hit >= {HIT_MINIMO} px, altura dentro do orcamento."
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "sabotagem": sabotagem,
        "larguras": list(larguras),
        "medidas": medidas,
        "botoes": sum(m["total"] for m in medidas),
        "sem_rotulo": sum(len(m["sem_rotulo"]) for m in medidas),
        "cabecalhos_faltando": sum(len(m["cabecalhos_faltando"]) for m in medidas),
        "hit_pequeno": sum(len(m["hit_pequeno"]) for m in medidas),
        "veredito": veredito(medidas),
    }


def tabela(relatorio: Mapping[str, Any]) -> str:
    linhas = [str(relatorio["portao"]), ""]
    linhas.append(
        f"  {'arranjo':<20} {'larg':>5} {'modo':<9} {'altura':>7} {'orc':>4} {'botoes':>6} "
        f"{'c/rot':>5} {'cabec':>7} {'hit<40':>6}  veredito"
    )
    for m in relatorio["medidas"]:
        linhas.append(
            f"  {m['arranjo']:<20} {m['largura_da_janela']:>5} {m['modo']:<9} "
            f"{m['altura_da_fita']:>7} {m['orcamento']:>4} {m['total']:>6} {m['com_rotulo']:>5} "
            f"{len(m['cabecalhos_visiveis'])}/{len(m['cabecalhos_declarados']):<5} "
            f"{len(m['hit_pequeno']):>6}  {m['veredito']}"
        )
        linhas.extend(f"      sem rotulo: {acao}" for acao in m["sem_rotulo"])
        linhas.extend(f"      hit pequeno: {acao} {w}x{h}" for acao, w, h in m["hit_pequeno"])
        linhas.extend(f"      cabecalho ausente: {cab}" for cab in m["cabecalhos_faltando"])
    if not relatorio["medidas"]:
        linhas.append("  (nenhuma pele com fita)")
    if relatorio.get("sabotagem"):
        linhas.append(f"  SABOTAGEM: {relatorio['sabotagem']} -- o portao tem de REPROVAR")
    linhas.append(
        f"  botoes {relatorio['botoes']} | sem rotulo {relatorio['sem_rotulo']} | "
        f"cabecalhos ausentes {relatorio['cabecalhos_faltando']} | hit < {HIT_MINIMO} px "
        f"{relatorio['hit_pequeno']}"
    )
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portao da fita: rotulo, cabecalho e hit.")
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--larguras", default=",".join(str(w) for w in LARGURAS_PADRAO))
    parser.add_argument("--sabotar", choices=SABOTAGENS, default="")
    parser.add_argument("--uma-passada", action="store_true", help="uso interno: um arranjo so.")
    parser.add_argument("--json", type=Path, default=None, help="uso interno: destino da passada.")
    args = parser.parse_args(argv)
    larguras = tuple(int(w) for w in args.larguras.split(",") if w)

    if args.uma_passada:
        if args.json is None:
            parser.error("--uma-passada exige --json.")
        medidas = medir_uma_passada(
            caminho_do_tronco=args.tronco, pdf=args.pdf, larguras=larguras, sabotagem=args.sabotar
        )
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(medidas, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.saida is None:
        parser.error("--saida e' obrigatorio: este portao nao escolhe pasta por voce.")
    relatorio = auditar_as_peles(
        caminho_do_tronco=args.tronco, pdf=args.pdf, saida=args.saida, larguras=larguras,
        sabotagem=args.sabotar,
    )
    carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"fita_{carimbo}{'_' + args.sabotar if args.sabotar else ''}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
