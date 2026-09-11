r"""Assistente de primeira execucao do Caissa Studio (F12).

A pergunta que este arquivo responde
------------------------------------
A SPEC secao 1 diz que o usuario-alvo **nao e programador** e que tudo tem de funcionar no
primeiro clique. O que o empacotamento cria e exatamente o contrario disso: uma pasta com
um `.exe`, sem pesos, numa maquina cuja GPU ninguem conferiu. Este assistente e a ponte, e
faz tres coisas, nessa ordem:

1. **Instala o PyTorch** (ciclo 2) -- a roda **certa para esta GPU**, e nao a que coube no
   instalador de quem o montou. `nvidia-smi` diz a arquitetura (nesta maquina: `sm_120`), o
   `caissa_torch.py` baixa cu128 ou CPU com SHA-256, e o relatorio diz **em segundos** o que
   a escolha significa: 0,0903 s/diagrama contra 0,5234 (F4GPU secao 7). O ciclo 1
   congelava a roda de CPU dentro do instalador e nao contava a ninguem.
2. **Confere a maquina** -- reusando `scripts/doctor.py`, que roda uma multiplicacao de
   matrizes 4096x4096 de verdade em vez de acreditar em `torch.cuda.is_available()`. A ADR
   0003 registra por que: em Blackwell (`sm_120`) com a roda errada, `is_available()`
   devolve `True` e o primeiro kernel morre. Um diagnostico que confia nessa funcao mente
   justamente na maquina de referencia deste projeto. **Depois** do passo 1, e nao antes:
   sem torch instalado nao ha o que sondar.
3. **Instala o que nao viaja dentro do binario** -- os pesos, por tamanho (SPEC secao 12),
   e tres artefatos por licenca nao apurada (LICENSING.md). Verificacao SHA-256 sempre.
4. **Roda o auto-teste** -- `Caissa.exe --selftest`, que e o auto-teste do tronco, sobre um
   PDF que este arquivo desenha na hora. Nao ha PDF de exemplo no bundle: um arquivo de
   teste embutido e peso morto para todo usuario depois do primeiro dia, e desenhar um
   tabuleiro com o PyMuPDF que ja esta ali prova mais -- que o PyMuPDF **do bundle** abre,
   desenha e rasteriza.

Degradar honestamente
---------------------
Sem GPU o programa **nao quebra**: ele roda na CPU. O que o assistente nao faz e deixar isso
implicito. Ele mede a mesma multiplicacao nos dois lados **nesta maquina** e imprime a razao
medida, em vez de repetir um numero de folheto que nao vale para o computador de quem esta
lendo. Sem torch nenhum, ele diz qual caminho some (o classificador neural) e qual continua
(a deteccao geometrica, o OCR, a notacao, a tipografia, os exportadores) -- porque
"funciona mais devagar" e "essa parte nao existe" sao respostas diferentes e o usuario
precisa saber qual das duas recebeu.

    Caissa.exe --primeira-execucao
    CaissaPrimeiraExecucao.exe --de-pasta "D:\\pendrive\\caissa-modelos"
    CaissaPrimeiraExecucao.exe --json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import caissa_modelos as mod
import caissa_torch as ct

__all__ = [
    "CODIGO_FALHA",
    "CODIGO_OK",
    "CODIGO_PARCIAL",
    "Assistente",
    "Passo",
    "main",
    "pdf_de_prova",
]

CODIGO_OK = 0
"""Tudo pronto: pesos verificados, auto-teste passou."""

CODIGO_PARCIAL = 3
"""Roda, com menos. Falta um componente opcional, ou a GPU nao esta disponivel e o caminho
e a CPU. **Nao e 1**: um usuario sem GPU tem um programa que funciona, e devolver o mesmo
codigo de uma instalacao quebrada apagaria a diferenca que o assistente existe para dizer."""

CODIGO_FALHA = 1
"""Falta algo obrigatorio, ou o auto-teste reprovou."""

_LARGURA = 74


@dataclass
class Passo:
    """Uma linha do relatorio. `estado` e uma das quatro palavras que o usuario le."""

    chave: str
    titulo: str
    estado: str
    valor: str = ""
    detalhe: str = ""
    dados: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        """Forma serializavel, para `--json`."""
        return {
            "chave": self.chave,
            "titulo": self.titulo,
            "estado": self.estado,
            "valor": self.valor,
            "detalhe": self.detalhe,
            "dados": self.dados,
        }


OK = "OK"
AVISO = "AVISO"
FALHA = "FALHA"
INFO = "INFO"


def _raiz_do_pacote() -> Path:
    """A pasta que contem o `.exe` (congelado) ou a raiz do repositorio (checkout)."""
    return mod.raiz_de_instalacao()


def _executavel_da_janela() -> Path | None:
    """`Caissa.exe`, quando existe ao lado deste processo.

    Num checkout nao existe, e o auto-teste roda o `app_pyqt.py` do tronco pelo interpretador
    atual. As duas formas exercitam o mesmo codigo; a diferenca e so quem carrega os modulos.
    """
    if not getattr(sys, "frozen", False):
        return None
    candidato = _raiz_do_pacote() / "Caissa.exe"
    return candidato if candidato.exists() else None


POSICAO_DE_PROVA: dict[str, str] = {
    # casa (coluna a-h, fileira 1-8) -> nome do PNG em assets/piece_images/
    "e1": "wk",
    "e8": "bk",
    "d4": "wp",
    "d5": "bp",
    "a1": "wr",
    "h8": "br",
}
r"""Uma posicao LEGAL, e nao um tabuleiro vazio -- e a diferenca custou um travamento.

O primeiro `pdf_de_prova` desenhava so as 64 casas, sem peca, no argumento de que "a grade e
o que o detector procura". A deteccao de fato achou a grade. O que veio depois nao terminou:
o `decode.py` do tronco faz busca best-first sobre a matriz (64, 13) **com as regras do
xadrez**, e a primeira delas e *exatamente um rei de cada cor*. Num tabuleiro vazio nenhuma
casa e rei, entao o reparo tem de ramificar sobre as **64 casas candidatas a virar rei**, de
duas cores -- e o auto-teste ficou 5 minutos sem responder e foi morto pelo tempo limite.

O defeito era do PDF de prova, e nao do decodificador: o decodificador estava fazendo
exatamente o que a ASSETS secao 2.3 documenta. Duas torres e dois peoes alem dos reis dao
uma posicao legal, que ele decide em um passo."""


def _pasta_de_pecas() -> Path:
    """Onde estao os 12 PNGs de peca. Congelado e uma resposta; num checkout sao duas.

    Congelado, `sys._MEIPASS` e a pasta interna do PyInstaller e a `caissa.spec` poe os PNGs
    la -- e o auto-teste, ao usa-los, prova de quebra que os `datas` do bundle sao
    encontraveis em execucao, que e uma classe de defeito que so aparece depois de empacotar.
    Num checkout eles moram no tronco, que nao e pacote instalado (mesmo arranjo de
    `tests/unit/ui/conftest.py`).
    """
    empacotada = Path(getattr(sys, "_MEIPASS", "")) / "assets" / "piece_images"
    if empacotada.is_dir():
        return empacotada
    do_pacote = Path(__file__).resolve().parent / "assets" / "piece_images"
    if do_pacote.is_dir():
        return do_pacote
    return Path(r"C:\Python-Chess2\ChessVisionOFF_Puro") / "assets" / "piece_images"


def pdf_de_prova(destino: Path, *, lado: float = 288.0) -> Path:
    """Desenha um PDF de uma pagina com um diagrama de xadrez e grava em `destino`.

    E o insumo do auto-teste, e a razao de ele ser **desenhado** em vez de embutido esta no
    docstring do modulo: um PDF de exemplo dentro do bundle e peso morto para todo usuario
    depois do primeiro dia, e desenhar um prova mais -- que o PyMuPDF **do bundle** abre,
    desenha e rasteriza, e que os PNGs de peca **do bundle** sao encontraveis e legiveis.

    288 pt = 4 polegadas. A 200 dpi isso da 800 px de tabuleiro, que e exatamente o
    `BOARD_SIZE` do tronco -- o auto-teste nao pede ao detector nenhuma reducao que a pagina
    de um livro real nao pediria.

    As pecas sao os PNGs de `assets/piece_images/`. Se a pasta nao estiver la (checkout sem
    os artefatos), o tabuleiro sai vazio e a funcao **avisa no proprio PDF**, em vez de
    entregar em silencio a posicao que trava o decodificador.
    """
    import fitz

    documento = fitz.open()
    pagina = documento.new_page(width=612, height=792)  # Carta, como quase todo livro
    margem_x = (612 - lado) / 2
    margem_y = 160.0
    casa = lado / 8

    claro = (0.93, 0.93, 0.88)
    escuro = (0.42, 0.49, 0.36)
    for linha in range(8):
        for coluna in range(8):
            retangulo = fitz.Rect(
                margem_x + coluna * casa,
                margem_y + linha * casa,
                margem_x + (coluna + 1) * casa,
                margem_y + (linha + 1) * casa,
            )
            cor = escuro if (linha + coluna) % 2 else claro
            pagina.draw_rect(retangulo, color=cor, fill=cor, width=0)

    pasta_de_pecas = _pasta_de_pecas()
    postas = 0
    for nome_da_casa, peca in POSICAO_DE_PROVA.items():
        arquivo = pasta_de_pecas / f"{peca}.png"
        if not arquivo.is_file():
            continue
        coluna = ord(nome_da_casa[0]) - ord("a")
        linha = 8 - int(nome_da_casa[1])  # fileira 8 e a de cima, e y cresce para baixo
        folga = casa * 0.06
        pagina.insert_image(
            fitz.Rect(
                margem_x + coluna * casa + folga,
                margem_y + linha * casa + folga,
                margem_x + (coluna + 1) * casa - folga,
                margem_y + (linha + 1) * casa - folga,
            ),
            filename=str(arquivo),
            keep_proportion=True,
        )
        postas += 1

    pagina.draw_rect(
        fitz.Rect(margem_x, margem_y, margem_x + lado, margem_y + lado),
        color=(0, 0, 0),
        width=1.2,
    )
    aviso = (
        ""
        if postas == len(POSICAO_DE_PROVA)
        else f"  [ATENCAO: so {postas} de {len(POSICAO_DE_PROVA)} pecas foram encontradas em "
        f"{pasta_de_pecas}]"
    )
    pagina.insert_text(
        (margem_x, margem_y - 24),
        "Caissa Studio - pagina de prova do auto-teste" + aviso,
        fontsize=11,
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(str(destino))
    documento.close()
    return destino


class Assistente:
    """Roda os passos e guarda o relatorio. Nenhum passo levanta excecao para o chamador."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Guarda os argumentos e prepara um relatorio vazio."""
        self.args = args
        self.passos: list[Passo] = []
        self.manifesto = mod.carregar_manifesto(args.manifesto)
        self.raiz = Path(args.raiz).resolve() if args.raiz else _raiz_do_pacote()

    # -- utilitarios ------------------------------------------------------- #

    def _add(self, passo: Passo) -> Passo:
        self.passos.append(passo)
        return passo

    def _tem(self, estado: str) -> bool:
        return any(p.estado == estado for p in self.passos)

    # -- 1. o torch, antes de tudo ----------------------------------------- #

    def instalar_torch(self) -> None:
        """Detecta a GPU, instala a roda certa e **diz em segundos** o que ela significa.

        Roda **antes** de `conferir_maquina`, e a ordem e o ponto: a sonda real do
        `doctor.py` e uma multiplicacao 4096x4096 *em torch*, e sem torch instalado ela nao
        pode acontecer. Antes daqui quem responde sobre a GPU e o `nvidia-smi` (hardware);
        depois daqui quem responde e o kernel de verdade (ADR-0003).
        """
        manifesto = ct.carregar_manifesto_de_torch(self.args.torch_manifesto)
        gpu = ct.detectar_gpu()
        variante, motivo = ct.escolher_variante(gpu, manifesto)
        if self.args.torch_variante:
            variante = manifesto.por_id(self.args.torch_variante)
            motivo = f"escolhida a mao por --torch-variante {self.args.torch_variante}."

        self._add(
            Passo(
                "gpu-detectada",
                "Placa de video",
                INFO,
                f"{gpu.nome} - {gpu.sm} - driver {gpu.driver}" if gpu else "nenhuma NVIDIA",
                motivo,
                dados={"gpu": gpu.como_dict() if gpu else None},
            )
        )

        ja = ct.estado_instalado(self.raiz)
        if ja and ja.get("variante") == variante.id and not self.args.reinstalar_torch:
            self._registrar_torch(variante, "ja instalado", OK, ja)
            self._por_no_caminho()
            return
        if ja and ja.get("variante") != variante.id:
            self._add(
                Passo(
                    "torch-troca",
                    "PyTorch instalado nao e o desta maquina",
                    AVISO,
                    f"instalado: {ja.get('variante')} - recomendado: {variante.id}",
                    "Rode de novo com --reinstalar-torch para trocar. Nada quebra enquanto "
                    "isso; o que muda e a velocidade.",
                )
            )
            self._por_no_caminho()
            return

        if self.args.sem_torch:
            self._add(
                Passo(
                    "torch",
                    "PyTorch",
                    AVISO,
                    "nao instalado (--sem-torch)",
                    "O caminho neural -- leitura de diagramas e OCR por glifo -- fica "
                    "INDISPONIVEL. A deteccao geometrica, a notacao, a tipografia e os "
                    "exportadores continuam. Para instalar depois:\n"
                    "    CaissaPrimeiraExecucao.exe",
                )
            )
            return

        origem = Path(self.args.rodas_de).resolve() if self.args.rodas_de else None
        de_onde = f"de {origem}" if origem else "de download.pytorch.org (HTTPS)"
        sys.stdout.write(
            f"\nInstalando {variante.titulo}\n"
            f"  {variante.mb:.0f} MB em {len(variante.rodas)} rodas, {de_onde}.\n"
            f"  Cada uma e conferida por SHA-256 antes de ser desempacotada.\n\n"
        )
        sys.stdout.flush()

        comeco = time.perf_counter()
        ok, resultados, marca = ct.instalar_variante(
            variante,
            raiz=self.raiz,
            origem=origem,
            manter_rodas=self.args.manter_rodas,
            progresso=self._progresso_de_roda,
        )
        decorrido = time.perf_counter() - comeco

        if not ok:
            ruim = next((r for r in resultados if not r.ok), None)
            self._add(
                Passo(
                    "torch",
                    "PyTorch",
                    AVISO,
                    f"nao instalado ({ruim.estado if ruim else 'erro'})",
                    (f"{ruim.detalhe}\n" if ruim else "")
                    + "O caminho neural fica INDISPONIVEL ate isto ser resolvido. O resto do "
                    "programa funciona.\n"
                    "Sem internet: baixe as rodas em outra maquina e use\n"
                    "    CaissaPrimeiraExecucao.exe --rodas-de <pasta com os .whl>\n"
                    "A lista, com o SHA-256 de cada uma, esta em "
                    "`_internal\\torch_manifesto.json`.",
                    dados={"resultados": [r.estado for r in resultados]},
                )
            )
            return

        marca["segundos_para_instalar"] = round(decorrido, 1)
        self._registrar_torch(variante, f"instalado em {decorrido:.0f} s", OK, marca)
        self._por_no_caminho()

    def _progresso_de_roda(self, roda: ct.Roda, lidos: int) -> None:
        """Uma linha a cada 128 MB. Um `.whl` de 2,6 GB sem nenhum sinal parece travado."""
        if roda.bytes < 50 * 1024 * 1024:
            return
        if lidos % (128 * 1024 * 1024) >= ct.TAMANHO_DO_BLOCO:
            return
        sys.stdout.write(
            f"  {roda.nome}: {lidos / 1024 / 1024:6.0f} de {roda.mb:.0f} MB "
            f"({100.0 * lidos / roda.bytes:4.0f}%)\n"
        )
        sys.stdout.flush()

    def _registrar_torch(
        self, variante: ct.Variante, valor: str, estado: str, marca: dict[str, Any]
    ) -> None:
        """A frase que o usuario le sobre velocidade. Em segundos, e nao em adjetivos."""
        outra = "cpu" if variante.id == "cu128" else "cu128"
        seu = variante.segundos_por_diagrama
        alternativo = ct.SEGUNDOS_POR_DIAGRAMA[outra]
        if variante.id == "cu128":
            frase = (
                f"O reconhecimento vai a **{seu:.4f} s por diagrama** (medido nesta maquina, "
                f"docs/quality/F4GPU_REPORT.md secao 7). Em CPU seriam {alternativo:.4f} s -- "
                f"{alternativo / seu:.1f}x mais lento. Um livro de 300 paginas com 400 "
                f"diagramas leva cerca de {400 * seu / 60:.0f} min em vez de "
                f"{400 * alternativo / 60:.0f} min."
            )
        else:
            frase = (
                f"O reconhecimento vai a **{seu:.4f} s por diagrama**. Nada quebra: a "
                f"deteccao, o OCR, a notacao, a tipografia e os exportadores nao usam GPU. "
                f"Com uma GPU NVIDIA seriam {alternativo:.4f} s -- {seu / alternativo:.1f}x "
                f"mais rapido. Na pratica: um livro de 300 paginas com 400 diagramas leva "
                f"cerca de {400 * seu / 60:.0f} min em vez de {400 * alternativo / 60:.0f} min."
            )
        self._add(
            Passo(
                "torch",
                f"PyTorch - {variante.titulo}",
                estado,
                f"{valor} ({variante.mb:.0f} MB em {ct.raiz_do_runtime(self.raiz)})",
                frase,
                dados={"marca": marca, "variante": variante.id},
            )
        )

    def _por_no_caminho(self) -> None:
        """Poe `runtime/` em `sys.path` AGORA, para o `doctor.py` deste mesmo processo.

        O `runtime_hook_torch.py` faz isto na inicializacao do `.exe` -- mas na primeira
        execucao o torch acabou de ser instalado, depois de o gancho ja ter rodado. Sem esta
        linha o assistente instalaria 2,6 GB e depois diria que nao ha torch, o que e a
        contradicao mais confusa que ele poderia produzir.
        """
        runtime = ct.raiz_do_runtime(self.raiz)
        if not runtime.is_dir():
            return
        if str(runtime) not in sys.path:
            sys.path.append(str(runtime))

    # -- 2. a maquina ------------------------------------------------------ #

    def conferir_maquina(self) -> None:
        """Reusa `scripts/doctor.py`. Ele e quem sabe fazer a pergunta certa sobre a GPU."""
        relatorio = self._relatorio_do_doctor()
        if relatorio is None:
            self._add(
                Passo(
                    "doctor",
                    "Diagnostico do ambiente",
                    AVISO,
                    "indisponivel",
                    "O doctor.py nao esta neste pacote. A conferencia de GPU foi pulada; "
                    "o resto do assistente continua.",
                )
            )
            return

        bruto = relatorio.get("raw", {})
        sonda = bruto.get("probe") or {}
        self._add(
            Passo(
                "sistema",
                "Maquina",
                INFO,
                self._resumo_do_sistema(relatorio),
                dados={"contagens": relatorio.get("counts", {})},
            )
        )

        if sonda.get("ok"):
            quente = float(sonda.get("warm_ms") or 0.0)
            gflops = float(sonda.get("gflops") or 0.0)
            razao = self._razao_contra_cpu(int(sonda.get("size") or 4096), quente)
            detalhe = (
                f"Kernel real de {sonda.get('size')}x{sonda.get('size')} em "
                f"{sonda.get('dtype')}, nao `is_available()` (ADR-0003)."
            )
            if razao is not None:
                detalhe += f" Medido agora: a GPU e {razao:.0f}x a CPU desta maquina."
            self._add(
                Passo(
                    "gpu",
                    "GPU",
                    OK,
                    f"{sonda.get('device')} - {quente:.1f} ms ({gflops / 1000:.1f} TFLOP/s)",
                    detalhe,
                    dados={"sonda": sonda, "razao_gpu_sobre_cpu": razao},
                )
            )
            return

        if ct.estado_instalado(self.raiz) is None:
            # "Nao ha GPU" e "nao ha com o que sondar a GPU" sao respostas diferentes, e
            # confundi-las diria a um dono de RTX 5060 que a placa dele nao serve. A sonda
            # real do doctor.py e uma multiplicacao EM TORCH; sem torch ela nao acontece, e
            # o unico dado honesto e o do `nvidia-smi`, que ja saiu no passo anterior.
            self._add(
                Passo(
                    "gpu",
                    "GPU",
                    AVISO,
                    "nao sondada - o PyTorch nao esta instalado",
                    "A verificacao de verdade e uma multiplicacao de 4096x4096 na placa "
                    "(ADR-0003), e ela precisa do PyTorch. O que a placa E esta no passo "
                    "acima, medido pelo `nvidia-smi`; o que ela FAZ so da para medir depois "
                    "de instalar a roda.",
                    dados={"sonda": sonda},
                )
            )
            return

        motivo = sonda.get("error_message") or sonda.get("diagnosis") or "sem GPU utilizavel"
        razao = self._razao_contra_cpu(2048, None)
        frase = (
            "O programa RODA NA CPU. Nada quebra: a deteccao geometrica, o OCR, a "
            "notacao, a tipografia e os exportadores nao usam GPU."
        )
        if razao is not None:
            frase += f" O que fica lento e o caminho neural, na ordem de {razao:.0f}x."
        self._add(
            Passo(
                "gpu",
                "GPU",
                AVISO,
                "nao utilizavel - caminho de CPU",
                f"{motivo}\n{frase}",
                dados={"sonda": sonda, "razao_gpu_sobre_cpu": razao},
            )
        )

    def _relatorio_do_doctor(self) -> dict[str, Any] | None:
        try:
            import doctor
        except ImportError:
            return None

        argumentos = ["--json", "--allow-cpu"]
        if self.args.pular_gpu:
            argumentos.append("--skip-gpu")
        try:
            analisador = doctor.build_parser().parse_args(argumentos)
            medico = doctor.Doctor(analisador)
            medico.run()
            return dict(json.loads(medico.render_json()))
        except Exception as exc:  # noqa: BLE001 - o doctor nunca pode derrubar o assistente
            self._add(
                Passo(
                    "doctor",
                    "Diagnostico do ambiente",
                    AVISO,
                    "falhou",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            return None

    @staticmethod
    def _resumo_do_sistema(relatorio: dict[str, Any]) -> str:
        for secao in relatorio.get("sections", []):
            if secao.get("title") == "SISTEMA":
                partes = [
                    c.get("value", "")
                    for c in secao.get("checks", [])
                    if c.get("key") in {"cpu", "ram"}
                ]
                return " - ".join(p for p in partes if p)
        return "nao medido"

    @staticmethod
    def _razao_contra_cpu(tamanho: int, gpu_ms: float | None) -> float | None:
        """Mede a MESMA multiplicacao na CPU e devolve a razao. `None` se nao der para medir.

        Sem torch nao ha o que comparar e a funcao devolve `None` -- e a mensagem que sai
        entao fala de caminho ausente, e nao de lentidao. Sao coisas diferentes.
        """
        try:
            import torch
        except Exception:  # noqa: BLE001 - DLL quebrada levanta OSError, nao ImportError
            return None

        lado = min(tamanho, 2048)  # 4096 em fp32 na CPU e dezenas de segundos; nao vale
        try:
            a = torch.randn(lado, lado, dtype=torch.float32)
            b = torch.randn(lado, lado, dtype=torch.float32)
            torch.matmul(a, b)  # aquece o BLAS; a primeira chamada aloca pools
            comeco = time.perf_counter()
            torch.matmul(a, b)
            cpu_ms = (time.perf_counter() - comeco) * 1000.0
        except Exception:  # noqa: BLE001
            return None

        if gpu_ms is None or gpu_ms <= 0:
            # Sem numero de GPU, extrapola pelo cubo do lado -- e o que a complexidade do
            # matmul manda -- para dizer a ordem de grandeza do que o usuario perde.
            escala = (4096 / lado) ** 3
            return max(1.0, (cpu_ms * escala) / 5.5)
        escala = (4096 / lado) ** 3
        return max(1.0, (cpu_ms * escala) / gpu_ms)

    # -- 2b. as licencas, que sao parte do produto ------------------------- #

    def conferir_licencas(self) -> None:
        """Os textos de licenca estao no pacote? A AGPL-3.0 secao 4 exige que estejam.

        Isto e uma verificacao de **produto**, e nao de desenvolvimento: quem recebe o
        binario recebe junto a obrigacao de poder ler sob que termos ele esta. O ciclo 1
        terminou sem esta pasta e com a frase *"o build e para uso proprio"*; o passo existe
        para que a ausencia dela volte a ser visivel se um dia alguem a tirar.
        """
        pasta = self._pasta_de_licencas()
        if pasta is None:
            self._add(
                Passo(
                    "licencas",
                    "Textos de licenca",
                    FALHA,
                    "ausentes deste pacote",
                    "A AGPL-3.0 secao 4 exige que o texto das licencas acompanhe a "
                    "distribuicao. Este pacote nao pode ser repassado a terceiros. "
                    "Rode `packaging/coletar_licencas.py` e refaca o build.",
                )
            )
            return
        try:
            indice = json.loads((pasta / "INDICE.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._add(Passo("licencas", "Textos de licenca", AVISO, "ilegiveis", f"{exc}"))
            return
        quantas = len(indice.get("distribuicoes", []))
        arte = indice.get("artefatos_nao_python", {}).get("assets-piece_images", {})
        self._add(
            Passo(
                "licencas",
                "Textos de licenca",
                OK,
                f"{quantas} dependencias, textos em {pasta}",
                "O binario e uma obra combinada sob AGPL-3.0-or-later (por causa do "
                "PyMuPDF). Quem redistribuir precisa entregar o fonte correspondente e "
                "estes textos junto -- `licenses/TERCEIROS.md` lista as cinco obrigacoes.\n"
                f"Arte das pecas: {arte.get('licenca', '?')}. Por que ela mudou em "
                "2026-09-09: `licenses/PECAS_PROCEDENCIA.md`.",
                dados={"distribuicoes": quantas},
            )
        )

    def _pasta_de_licencas(self) -> Path | None:
        """`licenses/` dentro do bundle, ou no `packaging/` de um checkout."""
        for candidata in (
            Path(getattr(sys, "_MEIPASS", "")) / "licenses",
            Path(__file__).resolve().parent / "licenses",
        ):
            if (candidata / "INDICE.json").is_file():
                return candidata
        return None

    # -- 3. os componentes ------------------------------------------------- #

    def instalar_componentes(self) -> None:
        """Verifica cada componente e, se pedido, instala de uma pasta local."""
        origem = Path(self.args.de_pasta).resolve() if self.args.de_pasta else None
        for componente in self.manifesto.componentes:
            resultado = mod.verificar(componente, self.raiz)
            if resultado.ok:
                self._add(
                    Passo(
                        f"componente:{componente.id}",
                        componente.titulo,
                        OK,
                        f"{componente.mb:.1f} MB - sha256 confere",
                        dados={"destino": str(resultado.caminho)},
                    )
                )
                continue

            if origem is not None:
                consentido = self._consentido(componente)
                resultado = mod.instalar_de_pasta(
                    componente, origem, self.raiz, consentido=consentido
                )
                if resultado.ok:
                    self._add(
                        Passo(
                            f"componente:{componente.id}",
                            componente.titulo,
                            OK,
                            f"instalado ({componente.mb:.1f} MB)",
                            resultado.detalhe,
                            dados={"destino": str(resultado.caminho)},
                        )
                    )
                    continue

            self._add(self._passo_de_ausencia(componente, resultado))

    def _consentido(self, componente: mod.Componente) -> bool:
        """Licenca nao apurada so entra com `--aceitar-licenca-nao-apurada`.

        A flag e feia de proposito. Um `--sim` generico faria o usuario aceitar sem ler; o
        nome escrito por extenso e a unica parte do consentimento que sobrevive a pressa.
        """
        if not componente.consentimento:
            return True
        return bool(self.args.aceitar_licenca_nao_apurada)

    def _passo_de_ausencia(self, componente: mod.Componente, resultado: mod.Resultado) -> Passo:
        estado = FALHA if componente.obrigatorio else AVISO
        if componente.consentimento:
            # A licenca aparece SEMPRE, e nao so quando o usuario passou `--de-pasta`.
            #
            # A primeira versao so imprimia isto no estado "sem-consentimento", que e o que
            # `instalar_de_pasta` devolve -- ou seja: quem nao pedisse a instalacao offline
            # via um "ausente" seco e nunca ficava sabendo que aquele arquivo esta de fora
            # por causa da licenca e nao por acaso. O motivo de um componente faltar e
            # exatamente a informacao que o assistente existe para dar.
            estado = INFO
            detalhe = (
                f"NAO ENTRA POR DECISAO DE LICENCA, e nao por falta de espaco.\n"
                f"Licenca: {componente.licenca}.\n"
                f"{componente.procedencia}\n"
                f"Sem ele: {componente.sem_ele}\n"
                "Para instalar assim mesmo: --de-pasta <origem> "
                "--aceitar-licenca-nao-apurada (ver LICENSING.md)"
            )
        else:
            como = (
                f"--de-pasta <pasta com {componente.destino}>"
                if self.manifesto.base_url is None
                else "o assistente baixa sozinho na proxima execucao"
            )
            detalhe = f"Sem ele: {componente.sem_ele}\nComo obter: {como}"
            if resultado.detalhe and resultado.estado != "ausente":
                detalhe = f"{resultado.detalhe}\n{detalhe}"
        return Passo(
            f"componente:{componente.id}",
            componente.titulo,
            estado,
            resultado.estado,
            detalhe,
            dados={"obrigatorio": componente.obrigatorio, "licenca": componente.licenca},
        )

    # -- 3. o auto-teste --------------------------------------------------- #

    def auto_teste(self) -> None:
        """Desenha um PDF, manda o `--selftest` do tronco le-lo, e reporta o codigo dele."""
        if self.args.pular_auto_teste:
            self._add(Passo("autoteste", "Auto-teste", INFO, "pulado por --pular-auto-teste"))
            return

        # Se algo OBRIGATORIO faltou, o auto-teste nao pode passar -- e o que ele faz nao e
        # falhar rapido: ele **pendura**. Medido em 2026-09-09, no bundle recem-construido e
        # sem os pesos:
        #
        #     [FALHA] Classificador de casas (pecas)   ausente
        #     [FALHA] Auto-teste                       nao terminou
        #             TimeoutExpired: ... timed out after 300.0 seconds
        #
        # Cinco minutos de espera para descobrir o que a linha de cima ja tinha dito. E pior
        # do que perda de tempo: a ultima linha do relatorio passa a ser um tempo limite, e o
        # usuario fica sem saber se o problema e o peso que falta ou o programa que travou.
        #
        # Entao ele nao roda, e diz por que nao rodou. Um auto-teste que nao pode passar nao
        # e um teste; e uma espera.
        faltando = [p.titulo for p in self.passos if p.estado == FALHA]
        if faltando:
            self._add(
                Passo(
                    "autoteste",
                    "Auto-teste",
                    INFO,
                    "nao rodado",
                    "Ele carrega um `.pt` e nao passaria sem ele -- ficaria pendurado ate o "
                    f"tempo limite de {self.args.tempo_limite:.0f} s. Resolva o que esta em "
                    f"FALHA acima ({', '.join(faltando)}) e rode o assistente de novo.",
                    dados={"bloqueado_por": faltando},
                )
            )
            return

        pasta = self.raiz / "PDF"
        try:
            pdf = pdf_de_prova(pasta / "caissa_pagina_de_prova.pdf")
        except Exception as exc:  # noqa: BLE001
            self._add(
                Passo(
                    "autoteste",
                    "Auto-teste",
                    FALHA,
                    "nao consegui desenhar o PDF de prova",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            return

        comando = self._comando_do_auto_teste(pdf)
        if comando is None:
            self._add(
                Passo(
                    "autoteste",
                    "Auto-teste",
                    AVISO,
                    "sem executavel para chamar",
                    "Nem `Caissa.exe` ao lado, nem `app_pyqt.py` do tronco. "
                    "O PDF de prova ficou em " + str(pdf),
                )
            )
            return

        ambiente = dict(os.environ)
        ambiente.setdefault("QT_QPA_PLATFORM", "offscreen")
        comeco = time.perf_counter()
        try:
            processo = subprocess.run(  # noqa: S603 - argv fixo, montado aqui
                comando,
                capture_output=True,
                text=True,
                timeout=self.args.tempo_limite,
                env=ambiente,
                check=False,
                cwd=str(self.raiz),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._add(
                Passo(
                    "autoteste",
                    "Auto-teste",
                    FALHA,
                    "nao terminou",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            return
        decorrido = time.perf_counter() - comeco

        codigo = processo.returncode
        significado = {
            0: "a instalacao le um diagrama",
            1: "a pagina nao foi reconhecida",
            2: "o PDF nao abriu",
            3: "o checkpoint nao esta la ou nao carrega",
            4: "le, mas o caminho de treino nao monta",
            5: "alguma pele nao monta o cromo",
            6: "o PyQt6 nao esta neste pacote",
            7: "uma excecao escapou -- o traceback esta em logs/",
        }.get(codigo, "codigo nao documentado")
        estado = OK if codigo == 0 else (AVISO if codigo in {3, 4, 5} else FALHA)
        cauda = (processo.stderr or processo.stdout or "").strip().splitlines()[-6:]
        self._add(
            Passo(
                "autoteste",
                "Auto-teste",
                estado,
                f"codigo {codigo} - {significado} ({decorrido:.1f} s)",
                "\n".join(cauda),
                dados={"comando": comando, "codigo": codigo, "segundos": decorrido},
            )
        )

    def _comando_do_auto_teste(self, pdf: Path) -> list[str] | None:
        janela = _executavel_da_janela()
        if janela is not None:
            return [str(janela), "--selftest", "--pdf", str(pdf)]
        tronco = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro") / "app_pyqt.py"
        if tronco.exists():
            return [sys.executable, str(tronco), "--selftest", "--pdf", str(pdf)]
        return None

    # -- relatorio --------------------------------------------------------- #

    def rodar(self) -> int:
        """Executa os blocos, **nesta ordem**, e devolve o codigo de saida.

        O torch vem primeiro porque tudo o que vem depois depende dele para dizer a verdade:
        a sonda real de GPU do `doctor.py` e uma multiplicacao em torch, e o auto-teste
        carrega um `.pt`. Perguntar sobre a GPU antes de instalar a roda daria a resposta de
        uma maquina que ainda nao existe.
        """
        self.instalar_torch()
        self.conferir_maquina()
        self.conferir_licencas()
        self.instalar_componentes()
        self.auto_teste()
        self._add(
            Passo(
                "disco",
                "Disco",
                INFO,
                self._resumo_de_disco(),
                dados={"raiz": str(self.raiz)},
            )
        )
        if self._tem(FALHA):
            return CODIGO_FALHA
        if self._tem(AVISO):
            return CODIGO_PARCIAL
        return CODIGO_OK

    def _resumo_de_disco(self) -> str:
        try:
            uso = shutil.disk_usage(self.raiz)
        except OSError as exc:
            return f"indisponivel ({exc})"
        instalado = sum(f.stat().st_size for f in self.raiz.rglob("*") if f.is_file()) / (
            1024 * 1024
        )
        return f"{uso.free / 1024**3:.1f} GB livres - instalacao ocupa {instalado:.0f} MB"

    def como_texto(self) -> str:
        """A tabela que o usuario le. Sem cor: um console de instalador nem sempre tem."""
        linhas = [
            "=" * _LARGURA,
            "  Caissa Studio - primeira execucao",
            f"  pasta: {self.raiz}",
            "=" * _LARGURA,
            "",
        ]
        for passo in self.passos:
            linhas.append(f"[{passo.estado:^5}] {passo.titulo}")
            if passo.valor:
                linhas.append(f"         {passo.valor}")
            linhas.extend(f"         {linha}" for linha in passo.detalhe.splitlines())
            linhas.append("")
        codigo = (
            CODIGO_FALHA
            if self._tem(FALHA)
            else (CODIGO_PARCIAL if self._tem(AVISO) else CODIGO_OK)
        )
        veredito = {
            CODIGO_OK: "Pronto. Feche esta janela e abra o Caissa Studio.",
            CODIGO_PARCIAL: (
                "Funciona, com menos. Cada AVISO acima diz o que falta e o que se perde."
            ),
            CODIGO_FALHA: "Falta algo obrigatorio. Cada FALHA acima diz o que.",
        }[codigo]
        linhas += ["-" * _LARGURA, veredito, "-" * _LARGURA]
        return "\n".join(linhas)

    def como_json(self) -> str:
        """Forma legivel por maquina, para o teste e para o suporte."""
        return json.dumps(
            {
                "esquema": 1,
                "raiz": str(self.raiz),
                "manifesto_gerado_em": self.manifesto.gerado_em,
                "passos": [p.como_dict() for p in self.passos],
            },
            indent=2,
            ensure_ascii=False,
        )


def construir_analisador() -> argparse.ArgumentParser:
    """Os argumentos do assistente."""
    analisador = argparse.ArgumentParser(
        prog="CaissaPrimeiraExecucao",
        description=(
            "Confere a maquina, instala os pesos que nao viajam no instalador e roda o "
            "auto-teste. Sem GPU o programa continua funcionando na CPU."
        ),
    )
    analisador.add_argument(
        "--de-pasta",
        default=None,
        help="instalacao offline: pasta local (pendrive, checkout do tronco) com os arquivos",
    )
    analisador.add_argument(
        "--aceitar-licenca-nao-apurada",
        action="store_true",
        help="instala tambem os dois lexicos de procedencia nao declarada (ver LICENSING.md)",
    )
    analisador.add_argument("--json", action="store_true", help="emite JSON em vez da tabela")
    analisador.add_argument("--pular-gpu", action="store_true", help="nao roda a carga na GPU")
    analisador.add_argument(
        "--pular-auto-teste", action="store_true", help="nao chama o --selftest"
    )
    analisador.add_argument(
        "--raiz", default=None, help="onde instalar (padrao: a pasta do executavel)"
    )
    analisador.add_argument(
        "--manifesto", default=None, type=Path, help="outro manifesto.json (para teste)"
    )
    analisador.add_argument(
        "--tempo-limite", type=float, default=300.0, help="segundos para o auto-teste"
    )
    analisador.add_argument(
        "--rodas-de",
        default=None,
        help="instalacao offline do PyTorch: pasta local com os .whl declarados em "
        "torch_manifesto.json",
    )
    analisador.add_argument(
        "--sem-torch",
        action="store_true",
        help="nao instala o PyTorch; o caminho neural fica indisponivel e o assistente diz isso",
    )
    analisador.add_argument(
        "--torch-variante",
        default=None,
        choices=["cu128", "cpu"],
        help="forca a roda em vez de deixar o nvidia-smi decidir",
    )
    analisador.add_argument(
        "--reinstalar-torch", action="store_true", help="troca a roda ja instalada"
    )
    analisador.add_argument(
        "--manter-rodas",
        action="store_true",
        help="nao apaga os .whl depois (para montar um espelho offline)",
    )
    analisador.add_argument(
        "--torch-manifesto", default=None, type=Path, help="outro torch_manifesto.json (teste)"
    )
    analisador.add_argument(
        "--sondar-torch",
        action="store_true",
        help="importa o torch em degraus e grava cada um em logs/sonda_torch.txt (diagnostico)",
    )
    analisador.add_argument(
        "--doctor",
        action="store_true",
        help="imprime o relatorio COMPLETO do scripts/doctor.py a partir deste pacote e sai",
    )
    analisador.add_argument(
        "--pausar",
        action="store_true",
        help="espera Enter no fim (o instalador usa, para a janela nao sumir)",
    )
    return analisador


PASSOS_DA_SONDA: tuple[tuple[str, str], ...] = (
    ("typing_extensions", "import typing_extensions"),
    ("filelock", "import filelock"),
    ("mpmath", "import mpmath"),
    ("sympy", "import sympy"),
    ("networkx", "import networkx"),
    ("fsspec", "import fsspec"),
    ("jinja2", "import jinja2"),
    ("torch.version", "import torch.version"),
    ("torch._C", "import torch._C"),
    ("torch", "import torch"),
    ("torch.cuda.is_available", "import torch; torch.cuda.is_available()"),
    ("torchvision", "import torchvision"),
)
"""A ordem em que o `import torch` acontece de verdade, quebrada em degraus.

Existe porque um `.exe` congelado que morre com `0xC0000409` nao deixa traceback: o processo
some **antes** de o Python conseguir escrever qualquer coisa. A unica forma de saber onde
ele parou e gravar cada degrau em disco, com `flush`, antes de tentar o proximo -- o arquivo
que sobra e o diagnostico."""


def sondar_torch(raiz: Path | None) -> int:
    r"""Importa o torch em degraus, gravando cada um em disco antes de tentar o proximo.

        dist\Caissa\CaissaPrimeiraExecucao.exe --sondar-torch

    O ultimo degrau escrito em `logs/sonda_torch.txt` e o degrau que matou o processo.
    """
    runtime = ct.raiz_do_runtime(raiz)
    if str(runtime) not in sys.path:
        sys.path.append(str(runtime))
    destino = (raiz or _raiz_do_pacote()) / "logs" / "sonda_torch.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as fh:

        def anotar(texto: str) -> None:
            fh.write(texto + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            sys.stdout.write(texto + "\n")
            sys.stdout.flush()

        anotar(f"runtime={runtime} existe={runtime.is_dir()}")
        anotar(f"frozen={getattr(sys, 'frozen', False)} meipass={getattr(sys, '_MEIPASS', None)}")
        for nome, codigo in PASSOS_DA_SONDA:
            anotar(f"-> {nome}")
            try:
                exec(codigo, {})  # noqa: S102 - literais fixos definidos acima
            except BaseException as exc:  # noqa: BLE001
                anotar(f"   FALHOU {type(exc).__name__}: {exc}")
            else:
                anotar(f"   ok {nome}")
        anotar("FIM")
    return 0


def rodar_doctor(raiz: Path | None) -> int:
    r"""Roda o `scripts/doctor.py` **de dentro deste pacote** e imprime o relatorio inteiro.

    Existe porque uma afirmacao como *"o bundle usa a GPU"* nao vale nada sem a saida do
    diagnostico que o projeto ja considera autoridade. O `doctor.py` viaja no `.exe`; esta
    flag e o unico jeito de chama-lo de la, ja que um pacote congelado nao tem `python` para
    rodar o script.

        dist\Caissa\CaissaPrimeiraExecucao.exe --doctor
    """
    runtime = ct.raiz_do_runtime(raiz)
    if runtime.is_dir() and str(runtime) not in sys.path:
        sys.path.append(str(runtime))
    try:
        import doctor
    except ImportError as exc:
        sys.stderr.write(f"doctor.py nao esta neste pacote: {exc}\n")
        return 2
    return int(doctor.main(["--allow-cpu"]))


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada. Devolve 0, 3 (parcial) ou 1 (falha)."""
    args = construir_analisador().parse_args(argv)
    if args.sondar_torch:
        return sondar_torch(Path(args.raiz).resolve() if args.raiz else None)
    if args.doctor:
        return rodar_doctor(Path(args.raiz).resolve() if args.raiz else None)
    try:
        assistente = Assistente(args)
        codigo = assistente.rodar()
    except Exception as exc:  # noqa: BLE001 - o assistente nunca some sem dizer por que
        import traceback

        sys.stderr.write("O assistente de primeira execucao falhou:\n")
        traceback.print_exc()
        sys.stderr.write(f"\n{type(exc).__name__}: {exc}\n")
        return 2

    sys.stdout.write((assistente.como_json() if args.json else assistente.como_texto()) + "\n")
    if args.pausar:
        # O instalador chama sem terminal proprio; sem a pausa a janela some com o relatorio.
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input("\nPressione Enter para fechar. ")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
