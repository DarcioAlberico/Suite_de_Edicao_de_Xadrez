r"""O portão dos **comandos**: um item habilitado tem de poder acontecer.

**Catorze ciclos de crítica de acabamento mediram a tinta de cada rótulo e nenhum perguntou se o
item fazia alguma coisa.** O crítico do ciclo 15 perguntou, e achou três: `Analisar a posição com
o motor`, `Análise contínua enquanto se navega` e `Pôr a linha do motor como variante` estavam
`habilitado=True, visivel=True` em **qualquer** máquina e os três respondiam
*"ponha o Stockfish em engines/ e reabra"* -- uma receita que não resolvia, porque
`qt/janela.py` construía `PainelDeEstudo` sem `analyzer` e `engine.find_engine` não tinha um único
chamador em `src/`. A corrente estava solta em quatro pontos e o menu prometia os três.

**Este portão mede a promessa, e não o texto dela.** Para cada comando desenhado na janela --
linha de menu, botão de fita, pílula da fila --, três perguntas:

* **solto**: o comando está habilitado e o sinal dele não tem **nenhum** receptor vivo. Clicar não
  faz nada, e nada avisa.
* **promete**: o comando está habilitado e declara precisar de um recurso que esta sessão **não
  tem** (`ui/sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR`, hoje o único). É o defeito do ciclo 15.
* **cinza sem motivo**: o comando está desabilitado e a dica dele não diz por quê. Desabilitar sem
  explicar é o mesmo defeito com o sinal trocado -- a pessoa vai procurar o erro na máquina dela.

**São duas provas de vida, uma por regra, e as duas mutam a janela montada sem tocar um byte do
produto** -- o mesmo caminho de `texto_pintado --faixa-de-antes`:

* `--desligar <acao>` desconecta o sinal daquele comando. Medido: `--desligar salvar` faz `soltos`
  ir de 0 a 1 e o veredito a `REPROVOU`.
* `--religar <acao>` **reabilita** um comando que a janela desabilitou, o que reconstrói
  exatamente o estado do ciclo 15. Medido: `--religar analisar_posicao,analise_continua,`
  `variante_do_motor` numa máquina sem Stockfish faz `prometem` ir de 0 a 3.

Um portão que só sabe dizer `PASSOU` não é um portão.

**E a outra metade, `--com-motor`**: o portão cria um arquivo na pasta temporária **dele**, aponta
`CVOFF_ENGINE_PATH` para ele e mede a janela de novo. Os três comandos do motor têm de sair
habilitados. Sem essa passada, "desabilitados" seria indistinguível de "sempre desabilitados", que
é a maneira preguiçosa de fechar o item 1 do §8.

A aritmética -- classificar um comando medido -- é pura e afirmada no venv da suíte, que **não tem
binding de Qt**. O Qt só entra dentro das funções que abrem a janela.

Uso (venv do tronco, que é onde o PyQt6 mora):

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=<suite>/src;<tronco>/src \
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.comandos --saida <pasta>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11 e o venv do tronco é 3.10. Ver `capture.UTC`."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

MOTOR = "motor"
"""O único recurso opcional que um comando desta janela declara precisar, hoje.

Um segundo recurso declarado no produto -- do jeito que `sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR`
declara este -- entra neste portão de graça, por `_exigencias`. O que **não** pode acontecer é ele
entrar só na janela, que foi como o motor viveu catorze ciclos."""


# --------------------------------------------------------------------- a aritmética, pura


@dataclass(frozen=True)
class Comando:
    """Um comando **desenhado**, e o que se sabe dele sem julgá-lo ainda."""

    acao: str
    superficie: str
    """`menu`, `fita` ou `fila` -- onde ele está desenhado."""
    rotulo: str
    habilitado: bool
    visivel: bool
    receptores: int
    """Quantos receptores vivos o sinal dele tem. `0` é um comando que não faz nada."""
    exige: str = ""
    """O recurso opcional que ele declara precisar, ou `""`."""
    dica: str = ""

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "acao": self.acao,
            "superficie": self.superficie,
            "rotulo": self.rotulo,
            "habilitado": self.habilitado,
            "visivel": self.visivel,
            "receptores": self.receptores,
            "exige": self.exige,
            "dica": self.dica,
        }


def defeito_de(comando: Comando, *, recursos: Mapping[str, bool]) -> str:
    """Como este comando está errado, ou `""`. **Pura, e é o coração do portão.**

    A ordem das três perguntas importa: um comando solto é pior que um comando que promete, e um
    que promete é pior que um cinza sem motivo. Devolver o primeiro é o que faz a linha do
    relatório dizer a coisa mais grave em vez da mais recente.
    """
    if not comando.visivel:
        return ""
    # **`receptores < 0` é "nao perguntei", e nao "ninguem escuta"**, e a diferença é a que
    # `_receptores` explica: confundir ponto cego com defeito faz o portão gritar sobre o que ele
    # não mediu, e é tão ruim quanto o silêncio. Ele sai numa conta própria, `nao_perguntados`.
    if comando.habilitado and comando.receptores == 0:
        return "solto"
    if comando.habilitado and comando.exige and not recursos.get(comando.exige, False):
        return "promete"
    if not comando.habilitado and not comando.dica.strip():
        return "cinza sem motivo"
    return ""


def veredito(medicoes: Sequence[Mapping[str, Any]]) -> str:
    """`PASSOU` só se houve medição e nenhuma delas achou defeito.

    Zero medições é `REPROVOU` pela mesma razão de `texto_pintado.veredito`: foi assim que o
    ciclo 9 publicou uma pele que ele não tinha medido.
    """
    if not medicoes:
        return "REPROVOU"
    return "PASSOU" if all(m["veredito"] == "PASSOU" for m in medicoes) else "REPROVOU"


@dataclass
class Medicao:
    """O que uma passada mediu, e o veredito dela."""

    arranjo: str
    recursos: dict[str, bool] = field(default_factory=dict)
    comandos: list[Comando] = field(default_factory=list)
    desligado: str = ""
    """A ação que a prova de vida desconectou nesta passada, se houve uma."""
    religados: tuple[str, ...] = ()
    """As ações que a prova de vida reabilitou nesta passada, se houve alguma."""

    def como_dicionario(self) -> dict[str, Any]:
        defeitos = [
            (comando, defeito_de(comando, recursos=self.recursos)) for comando in self.comandos
        ]
        achados = [(c, d) for c, d in defeitos if d]
        return {
            "arranjo": self.arranjo,
            "recursos": dict(self.recursos),
            "desligado": self.desligado,
            "religados": list(self.religados),
            "medidos": len(self.comandos),
            "por_superficie": {
                superficie: sum(1 for c in self.comandos if c.superficie == superficie)
                for superficie in sorted({c.superficie for c in self.comandos})
            },
            "habilitados": sum(1 for c in self.comandos if c.habilitado and c.visivel),
            "soltos": sum(1 for _, d in achados if d == "solto"),
            "prometem": sum(1 for _, d in achados if d == "promete"),
            "cinzas_sem_motivo": sum(1 for _, d in achados if d == "cinza sem motivo"),
            "nao_perguntados": sum(1 for c in self.comandos if c.receptores < 0),
            "defeitos": [dict(c.como_dicionario(), defeito=d) for c, d in achados],
            "veredito": "PASSOU" if not achados else "REPROVOU",
        }


# ------------------------------------------------------------------ daqui para baixo, o Qt


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pasta_de_fontes = Path(r"C:\Windows\Fonts")
    if pasta_de_fontes.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(pasta_de_fontes))
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _receptores(objeto: Any, sinal: Any) -> int:
    """Quantos receptores vivos aquele sinal tem. `-1` quando o Qt não sabe dizer.

    `-1` e não `0`: a diferença entre *"ninguém escuta"* e *"não consegui perguntar"* é a
    diferença entre um defeito e um ponto cego, e confundir os dois é como esta frente publicou
    zero por catorze ciclos.
    """
    try:
        return int(objeto.receivers(sinal))
    except Exception:  # noqa: BLE001 - binding sem `receivers` para este sinal
        return -1


def _exigencias(caminho_do_tronco: Path) -> dict[str, str]:
    """`ação -> recurso que ela exige`, lido do produto e não escrito aqui.

    Uma lista de "os comandos do motor" dentro deste portão seria a segunda declaração do mesmo
    fato, e a segunda é sempre a que fica para trás. A primeira é
    `ui/sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR`.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import sala_declarada

    return {acao: MOTOR for acao in sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR}


def medir_a_janela(janela: Any, *, exigencias: Mapping[str, str]) -> list[Comando]:
    """Todo comando desenhado desta janela: menu, fita e fila.

    **As três superfícies e não só o menu**, porque o defeito não é do menu: é da promessa. A
    mesma ação sai numa linha de menu, num botão da fita e numa pílula da fila conforme a pele, e
    medir só uma das três seria escolher a superfície em que o produto já estava certo -- que é o
    vício que o item 10 do §8 do ciclo 13 nomeou nos diálogos.
    """
    achados: list[Comando] = []
    for acao, item in getattr(janela.menu, "acoes", {}).items():
        achados.append(
            Comando(
                acao=acao,
                superficie="menu",
                rotulo=str(item.text() or "").replace("&", ""),
                habilitado=bool(item.isEnabled()),
                # `QAction.isVisible()` é a bandeira de `setVisible` e não "está na tela": num
                # menu fechado ela continua `True`, que é o que interessa -- a pergunta é se o
                # item é **oferecido**, não se o menu está aberto neste instante.
                visivel=bool(item.isVisible()),
                receptores=_receptores(item, item.triggered),
                exige=exigencias.get(acao, ""),
                dica=str(item.toolTip() or ""),
            )
        )
    for superficie, botoes in _botoes_do_cromo(janela):
        for acao, botao in botoes.items():
            achados.append(
                Comando(
                    acao=acao,
                    superficie=superficie,
                    rotulo=str(botao.text() or "").replace("&", ""),
                    habilitado=bool(botao.isEnabled()),
                    visivel=bool(botao.isVisible()),
                    receptores=_receptores(botao, botao.clicked),
                    exige=exigencias.get(acao, ""),
                    dica=str(botao.toolTip() or ""),
                )
            )
    return achados


def _botoes_do_cromo(janela: Any) -> list[tuple[str, Mapping[str, Any]]]:
    """`(superfície, {ação -> botão})` do cromo desta pele. Vazio na clássica, que não tem cromo.

    **Achado pela árvore e não por um atributo da janela**, porque a janela não guarda a barra: ela
    a entrega ao leiaute do cromo (`qt/janela._montar_o_cromo`). Procurar o dicionário `botoes` /
    `_botoes` é o que faz este portão alcançar a fita e a fila sem que nenhuma das duas precise
    saber que ele existe.
    """
    from PyQt6.QtWidgets import QWidget

    cromo = getattr(janela, "cromo", None)
    if cromo is None:
        return []
    achados: list[tuple[str, Mapping[str, Any]]] = []
    for widget in cromo.findChildren(QWidget):
        botoes = getattr(widget, "botoes", None) or getattr(widget, "_botoes", None)
        if isinstance(botoes, dict) and botoes:
            achados.append((type(widget).__name__.lower(), dict(botoes)))
    return achados


def medir_uma_passada(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    desligar: str = "",
    religar: Sequence[str] = (),
) -> dict[str, Any]:
    """Abre a janela uma vez, mede os comandos das três superfícies e devolve a medição.

    `desligar` e `religar` são as duas provas de vida: a primeira desconecta o sinal daquele
    comando, a segunda reabilita um comando que a janela tinha desabilitado. As duas mexem **na
    janela montada** e não no produto -- o mesmo caminho que `texto_pintado --faixa-de-antes` usa.
    """
    _preparar(caminho_do_tronco)
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit import teclado
    from caissa.ui.audit.capture import aguardar_a_folha, estado_de_medicao, impor_a_fonte_do_produto

    aplicacao = QApplication.instance() or QApplication(sys.argv[:1])
    impor_a_fonte_do_produto(aplicacao)
    from chess_diagram_ocr.qt.janela import JanelaPrincipal

    with tempfile.TemporaryDirectory() as temporaria:
        janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(Path(temporaria)))
    janela.show()
    if pdf is not None and Path(pdf).exists():
        janela.abrir_pdf(Path(pdf))
        aguardar_a_folha(janela)
    for _ in range(8):
        aplicacao.processEvents()

    if desligar:
        alvo = janela.menu.acoes.get(desligar)
        if alvo is None:
            raise KeyError(f"a janela nao desenha o comando {desligar!r} no menu.")
        alvo.triggered.disconnect()
        aplicacao.processEvents()
    for acao in religar:
        alvo = janela.menu.acoes.get(acao)
        if alvo is None:
            raise KeyError(f"a janela nao desenha o comando {acao!r} no menu.")
        alvo.setEnabled(True)
        alvo.setToolTip("")
    if religar:
        aplicacao.processEvents()

    medicao = Medicao(
        arranjo=f"{os.environ.get('CVOFF_SKIN', '?')}/{os.environ.get('CVOFF_DENSITY', '?')}",
        recursos={MOTOR: getattr(janela, "_analisador", None) is not None},
        comandos=medir_a_janela(janela, exigencias=_exigencias(caminho_do_tronco)),
        desligado=desligar,
        religados=tuple(religar),
    )
    saida = medicao.como_dicionario()
    teclado._descartar(janela, aplicacao)
    return saida


def auditar_as_peles(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    saida: Path,
    desligar: str = "",
    religar: Sequence[str] = (),
    com_motor: bool = False,
) -> dict[str, Any]:
    """O portão inteiro: um processo por pele, mais a passada `--com-motor`.

    Um processo por pele pela razão medida em `teclado.auditar_as_peles`: a pele resolve na
    importação, e duas janelas no mesmo processo abortavam o interpretador.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    saida.mkdir(parents=True, exist_ok=True)
    por_arranjo: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as temporaria:
        motor_de_mentira = ""
        if com_motor:
            # **Um arquivo qualquer serve, e é o ponto.** `find_engine` procura um *arquivo* e
            # `EngineAnalyzer.__init__` não abre processo nenhum: o que esta passada mede é a
            # **ligação** -- a janela achou, passou ao painel, o menu ficou vivo --, e não o UCI.
            # Ele nasce e morre na pasta temporária deste portão: nada é escrito em `engines/`.
            falso = Path(temporaria) / "stockfish_de_mentira.exe"
            falso.write_bytes(b"nao sou um motor")
            motor_de_mentira = str(falso)
        for registro in pele.PELES:
            arranjo = f"{registro.nome}{' +motor' if com_motor else ''}"
            carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            alvo = saida / f"comandos_{registro.nome}_{carimbo}.json"
            ambiente = dict(os.environ)
            ambiente["CVOFF_SKIN"] = registro.nome
            if com_motor:
                ambiente["CVOFF_ENGINE_PATH"] = motor_de_mentira
            argumentos = [
                sys.executable,
                "-m",
                "caissa.ui.audit.comandos",
                "--uma-passada",
                "--tronco",
                str(caminho_do_tronco),
                "--json",
                str(alvo),
            ]
            if pdf is not None:
                argumentos += ["--pdf", str(pdf)]
            if desligar:
                argumentos += ["--desligar", desligar]
            if religar:
                argumentos += ["--religar", ",".join(religar)]
            subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
            if not alvo.exists():
                raise RuntimeError(
                    f"a pele {arranjo!r} nao produziu relatorio: o subprocesso morreu antes de "
                    f"escrever {alvo}."
                )
            por_arranjo[arranjo] = json.loads(alvo.read_text(encoding="utf-8"))

    medidas = list(por_arranjo.values())
    return {
        "portao": (
            "Comandos: todo item habilitado e visivel tem implementacao alcancavel, e nenhum "
            "promete um recurso que esta sessao nao tem."
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "desligado": desligar,
        "religados": list(religar),
        "com_motor": com_motor,
        "arranjos": por_arranjo,
        "medidos": sum(m["medidos"] for m in medidas),
        "habilitados": sum(m["habilitados"] for m in medidas),
        "soltos": sum(m["soltos"] for m in medidas),
        "prometem": sum(m["prometem"] for m in medidas),
        "cinzas_sem_motivo": sum(m["cinzas_sem_motivo"] for m in medidas),
        "nao_perguntados": sum(m["nao_perguntados"] for m in medidas),
        "veredito": veredito(medidas),
    }


def tabela(relatorio: Mapping[str, Any]) -> str:
    """Uma linha por pele. O placar não fica sem dizer de quem é."""
    linhas = [str(relatorio["portao"]), ""]
    linhas.append(
        f"  {'arranjo':<18} {'medidos':>8} {'habilit':>8} {'soltos':>7} {'prometem':>9} "
        f"{'cinza s/motivo':>15}  veredito"
    )
    for arranjo, medida in relatorio["arranjos"].items():
        linhas.append(
            f"  {arranjo:<18} {medida['medidos']:>8} {medida['habilitados']:>8} "
            f"{medida['soltos']:>7} {medida['prometem']:>9} "
            f"{medida['cinzas_sem_motivo']:>15}  {medida['veredito']}"
        )
    defeitos = [
        (arranjo, defeito)
        for arranjo, medida in relatorio["arranjos"].items()
        for defeito in medida["defeitos"]
    ]
    if defeitos:
        linhas.append("")
        linhas.append("  DEFEITOS")
        for arranjo, defeito in defeitos:
            linhas.append(
                f"    {arranjo:<16} [{defeito['superficie']:<4}] {defeito['acao']:<22} "
                f"{defeito['rotulo'][:30]:<30} {defeito['defeito'].upper()}"
                f"  (receptores={defeito['receptores']}, exige={defeito['exige'] or '-'})"
            )
    recursos = {
        recurso: valor
        for medida in relatorio["arranjos"].values()
        for recurso, valor in medida["recursos"].items()
    }
    linhas.append("")
    linhas.append(f"  recursos desta sessao: {recursos}")
    if relatorio.get("desligado"):
        linhas.append(f"  PROVA DE VIDA: o sinal de {relatorio['desligado']!r} foi desconectado")
    if relatorio.get("religados"):
        linhas.append(
            f"  PROVA DE VIDA: {relatorio['religados']} foram reabilitados na janela montada"
        )
    linhas.append(
        f"  medidos {relatorio['medidos']} | habilitados {relatorio['habilitados']} | "
        f"soltos {relatorio['soltos']} | prometem {relatorio['prometem']} | "
        f"cinzas sem motivo {relatorio['cinzas_sem_motivo']} | "
        f"sinais que nao soube perguntar {relatorio['nao_perguntados']}"
    )
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Portao dos comandos: um item habilitado tem de poder acontecer."
    )
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        # Sem padrão, pelo mesmo motivo de `quadros.py` (item 16 do ciclo 11): um padrão que
        # escreve na pasta do construtor é uma armadilha para quem roda o portão de fora.
        help="onde gravar o relatorio. Obrigatorio, exceto com --uma-passada --json.",
    )
    parser.add_argument(
        "--desligar",
        default="",
        help=(
            "prova de vida: desconecta o sinal deste comando na janela montada, sem tocar o "
            "produto. --desligar salvar tem de fazer `soltos` ir a 1 e o veredito a REPROVOU."
        ),
    )
    parser.add_argument(
        "--religar",
        default="",
        help=(
            "prova de vida da outra regra: reabilita estes comandos (separados por virgula) na "
            "janela montada. Sem motor, --religar analisar_posicao,... poe `prometem` em 3."
        ),
    )
    parser.add_argument(
        "--com-motor",
        action="store_true",
        help=(
            "aponta CVOFF_ENGINE_PATH para um arquivo criado na pasta temporaria deste portao, "
            "para medir a outra metade: com motor, os tres comandos de analise ficam habilitados."
        ),
    )
    parser.add_argument("--uma-passada", action="store_true", help="uso interno: uma pele so.")
    parser.add_argument("--json", type=Path, default=None, help="uso interno: destino da passada.")
    args = parser.parse_args(argv)

    if args.uma_passada:
        if args.json is None:
            parser.error("--uma-passada exige --json.")
        medida = medir_uma_passada(
            caminho_do_tronco=args.tronco,
            pdf=args.pdf,
            desligar=args.desligar,
            religar=tuple(a for a in args.religar.split(",") if a),
        )
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(medida, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.saida is None:
        parser.error("--saida e' obrigatorio: este portao nao escolhe pasta por voce.")
    relatorio = auditar_as_peles(
        caminho_do_tronco=args.tronco,
        pdf=args.pdf,
        saida=args.saida,
        desligar=args.desligar,
        religar=tuple(a for a in args.religar.split(",") if a),
        com_motor=args.com_motor,
    )
    carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"comandos_{carimbo}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
