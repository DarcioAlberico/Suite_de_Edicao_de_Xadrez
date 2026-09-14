r"""O portão dos ícones da fita: traço, caixa e tinta de cada desenho no tamanho em que é desenhado.

**Promovido de `benchmarks/reports/ui/c12/c12_icones_da_janela.py`** (OCR_UI_ROADMAP passo 12),
que era um censo -- imprimia a tinta de cada ícone e não julgava. O roadmap escreveu o portão
como *"tinta ≥ 50 %"*, e esse número **não mede legibilidade de um ícone de traço**: um disco
cheio tem 78 % de tinta, uma seta cheia 50 %, e todo ícone de linha desta fita -- o traço declarado
de `ui/icones.py`, 9 % do lado -- fica entre 11 e 48 % por construção. Cobrar 50 % de tinta seria
cobrar silhuetas, que é outra família de arte. O que **mede** legibilidade em traço é o que se lê
aqui, direto do desenho e não de um número escolhido depois:

* **traço ≥ 2 px** em todo tamanho em que a fita desenha (20 e 32 px): abaixo disso o antialias
  dilui a linha num cinza -- `ui/icones._largura_do_traco(lado)` é a régua e o produto;
* **a caixa do desenho enche o lado**: o eixo maior é o lado inteiro (`na_grade` garante) e o menor
  não fica abaixo de 60 % dele -- é o "desfazer" de 20×9 px que o ciclo 15 fotografou;
* **tinta ≥ 10 % do lado²**: o piso abaixo do qual o desenho vira ruído no botão.

Tudo é medido no `QIcon` pedido ao botão **no tamanho em que ele o desenha**
(`iconSize()`), por pele × densidade × modo -- não no PNG de 100 unidades.

**A sabotagem** (`--sabotar tinta`) força o traço a 1 px na janela montada: o traço cai abaixo
de 2 e a tinta dos desenhos finos abaixo de 10 %, e o portão tem de acusar.

    ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.icones --saida <pasta>
    ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.icones --saida <pasta> ^
        --sabotar tinta
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: O venv do tronco é 3.10: sem `datetime.UTC`.
UTC = timezone.utc  # noqa: UP017 - o venv do tronco é 3.10
TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
TRACO_MINIMO_PX = 2
CAIXA_MENOR_MINIMA = 0.60
TINTA_MINIMA = 0.10
SABOTAGENS: tuple[str, ...] = ("tinta",)
#: Opacidade abaixo da qual um pixel é fundo (antialias residual).
OPACIDADE_MINIMA = 0.02


@dataclass(frozen=True)
class Icone:
    acao: str
    icone: str
    lado: int
    traco: int
    caixa_largura: int
    caixa_altura: int
    tinta: float
    """Massa de opacidade sobre lado², em 0..1."""

    @property
    def caixa_menor(self) -> float:
        return min(self.caixa_largura, self.caixa_altura) / self.lado if self.lado else 0.0

    @property
    def defeitos(self) -> tuple[str, ...]:
        saida = []
        if self.traco < TRACO_MINIMO_PX:
            saida.append(f"traco {self.traco} px < {TRACO_MINIMO_PX}")
        if self.caixa_menor < CAIXA_MENOR_MINIMA:
            saida.append(f"caixa {self.caixa_largura}x{self.caixa_altura} no lado {self.lado}")
        if self.tinta < TINTA_MINIMA:
            saida.append(f"tinta {100 * self.tinta:.1f} % < {100 * TINTA_MINIMA:.0f} %")
        return tuple(saida)

    def como_dicionario(self) -> dict[str, Any]:
        return {**asdict(self), "tinta": round(self.tinta, 4), "defeitos": list(self.defeitos)}


def caixa_de_tinta(imagem: Any) -> tuple[int, int, float]:
    """`(largura, altura, massa)` da opacidade de um `QImage` com alfa."""
    xs: list[int] = []
    ys: list[int] = []
    massa = 0.0
    for x in range(imagem.width()):
        for y in range(imagem.height()):
            valor = imagem.pixelColor(x, y).alpha() / 255.0
            if valor > OPACIDADE_MINIMA:
                xs.append(x)
                ys.append(y)
                massa += valor
    if not xs:
        return (0, 0, 0.0)
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, massa)


def veredito(icones: Iterable[Mapping[str, Any]]) -> str:
    icones = list(icones)
    if not icones:
        return "SEM ICONES"
    return "PASSOU" if all(not i["defeitos"] for i in icones) else "REPROVOU"


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pasta_de_fontes = Path(r"C:\Windows\Fonts")
    if pasta_de_fontes.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(pasta_de_fontes))
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def medir_uma_passada(
    *, caminho_do_tronco: Path = TRONCO, largura: int = 1920, sabotagem: str = ""
) -> dict[str, Any]:
    """Um arranjo (pele e densidade no ambiente): a fita numa largura, os ícones dos botões."""
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt import fita as qt_fita
    from chess_diagram_ocr.qt import icones as qt_icones
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.qt.plataforma import politica_de_escala
    from chess_diagram_ocr.ui import comandos
    from chess_diagram_ocr.ui import icones as ui_icones
    from PyQt6.QtWidgets import QApplication, QToolButton

    from caissa.ui.audit import teclado
    from caissa.ui.audit.capture import estado_de_medicao, impor_a_fonte_do_produto

    politica_de_escala()
    if sabotagem == "tinta":
        ui_icones._largura_do_traco = lambda _lado: 1  # type: ignore[assignment]
    aplicacao = QApplication.instance() or QApplication(sys.argv[:1])
    impor_a_fonte_do_produto(aplicacao)
    qt_icones.limpar_cache()
    tema.aplicar_tema(aplicacao)
    arranjo = f"{os.environ.get('CVOFF_SKIN', '?')}/{os.environ.get('CVOFF_DENSITY', '?')}"
    with tempfile.TemporaryDirectory() as temporaria:
        janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(Path(temporaria)))
    janela.show()
    janela.resize(int(largura), 768)
    for _ in range(8):
        aplicacao.processEvents()
    cromo = janela.findChild(qt_fita.Fita)
    lidos: list[dict[str, Any]] = []
    modo = ""
    if cromo is not None:
        modo = str(cromo.modo)
        por_id = {id(b): acao for acao, b in getattr(cromo, "_botoes", {}).items()}
        for botao in cromo.findChildren(QToolButton):
            if not botao.isVisible() or not botao.icon().availableSizes():
                continue
            acao = por_id.get(id(botao), "?")
            lado = botao.iconSize().width()
            imagem = botao.icon().pixmap(botao.iconSize()).toImage()
            larg, alt, massa = caixa_de_tinta(imagem)
            registro = comandos.comando(acao) if acao != "?" else None
            lidos.append(Icone(
                acao=acao, icone=(registro.icone if registro else "?"), lado=lado,
                traco=int(ui_icones._largura_do_traco(lado)),
                caixa_largura=larg, caixa_altura=alt, tinta=massa / max(1, lado * lado),
            ).como_dicionario())
    teclado._descartar(janela, aplicacao)
    return {"arranjo": arranjo, "largura": largura, "modo": modo, "sabotagem": sabotagem,
            "icones": lidos, "veredito": veredito(lidos)}


def auditar_as_peles(
    *, caminho_do_tronco: Path = TRONCO, saida: Path, sabotagem: str = "",
    larguras: tuple[int, ...] = (1280, 1920),
) -> dict[str, Any]:
    """Um processo por pele × densidade × largura (a largura decide o modo, e o modo o lado)."""
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    saida.mkdir(parents=True, exist_ok=True)
    passadas: list[dict[str, Any]] = []
    for registro in pele.PELES:
        for densidade in pele.DENSIDADES:
            for largura in larguras:
                carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
                alvo = saida / f"icones_{registro.nome}_{densidade}_{largura}_{carimbo}.json"
                ambiente = dict(os.environ)
                ambiente["CVOFF_SKIN"] = registro.nome
                ambiente["CVOFF_DENSITY"] = densidade
                argumentos = [
                    sys.executable, "-m", "caissa.ui.audit.icones", "--uma-passada",
                    "--tronco", str(caminho_do_tronco), "--json", str(alvo),
                    "--largura", str(largura),
                ]
                if sabotagem:
                    argumentos += ["--sabotar", sabotagem]
                subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
                if not alvo.exists():
                    raise RuntimeError(
                        f"o arranjo {registro.nome}/{densidade} nao produziu {alvo}."
                    )
                passada = json.loads(alvo.read_text(encoding="utf-8"))
                if passada["icones"]:
                    passadas.append(passada)
    icones = [i for p in passadas for i in p["icones"]]
    return {
        "portao": (
            f"Icones da fita: traco >= {TRACO_MINIMO_PX} px, caixa menor >= "
            f"{100 * CAIXA_MENOR_MINIMA:.0f} % do lado, tinta >= {100 * TINTA_MINIMA:.0f} % do "
            f"lado², no tamanho em que cada botao desenha."
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "sabotagem": sabotagem,
        "passadas": passadas,
        "icones": len(icones),
        "com_defeito": sum(1 for i in icones if i["defeitos"]),
        "tinta_min": min((i["tinta"] for i in icones), default=0.0),
        "tinta_max": max((i["tinta"] for i in icones), default=0.0),
        "veredito": veredito(icones),
    }


def tabela(relatorio: Mapping[str, Any]) -> str:
    linhas = [str(relatorio["portao"]), ""]
    for passada in relatorio["passadas"]:
        tintas = [i["tinta"] for i in passada["icones"]]
        lados = sorted({i["lado"] for i in passada["icones"]})
        linhas.append(
            f"  {passada['arranjo']:<20} larg {passada['largura']:>5} modo {passada['modo']:<9} "
            f"icones {len(passada['icones']):>3}  lado {lados}"
            f"  tinta {100 * min(tintas):.1f}-{100 * max(tintas):.1f} %  {passada['veredito']}"
        )
        for icone in passada["icones"]:
            if icone["defeitos"]:
                defeitos = "; ".join(icone["defeitos"])
                linhas.append(f"      {icone['acao']:<22} {icone['icone']:<20} {defeitos}")
    if relatorio.get("sabotagem"):
        linhas.append(f"  SABOTAGEM: {relatorio['sabotagem']} -- o portao tem de REPROVAR")
    linhas.append(
        f"  icones {relatorio['icones']} | com defeito {relatorio['com_defeito']} | tinta "
        f"{100 * relatorio['tinta_min']:.1f}-{100 * relatorio['tinta_max']:.1f} %"
    )
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portao dos icones da fita: traco, caixa, tinta.")
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--largura", type=int, default=1920, help="uso interno: a largura.")
    parser.add_argument("--sabotar", choices=SABOTAGENS, default="")
    parser.add_argument("--uma-passada", action="store_true", help="uso interno: um arranjo so.")
    parser.add_argument("--json", type=Path, default=None, help="uso interno: destino da passada.")
    args = parser.parse_args(argv)

    if args.uma_passada:
        if args.json is None:
            parser.error("--uma-passada exige --json.")
        passada = medir_uma_passada(
            caminho_do_tronco=args.tronco, largura=args.largura, sabotagem=args.sabotar
        )
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(passada, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.saida is None:
        parser.error("--saida e' obrigatorio: este portao nao escolhe pasta por voce.")
    relatorio = auditar_as_peles(
        caminho_do_tronco=args.tronco, saida=args.saida, sabotagem=args.sabotar
    )
    carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"icones_{carimbo}{'_' + args.sabotar if args.sabotar else ''}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
