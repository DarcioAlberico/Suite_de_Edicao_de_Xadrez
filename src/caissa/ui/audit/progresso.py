"""Audita progresso determinado x indeterminado no tronco (SPEC §11.3: "progresso real").

O portão do §11.3 tem três palavras que valem cada uma um defeito: **real** (nunca
indeterminado quando o total é conhecido), **cancelável** e **resultado parcial aproveitável**.
Este módulo mede as duas primeiras, que são as que dá para afirmar sem rodar a operação.

**Por que leitura estática e não uma janela aberta.** Uma barra indeterminada só aparece
*enquanto a operação roda*: para pegá-la ao vivo seria preciso disparar um treino de nove
minutos por época, uma varredura de 338 s e uma detecção de duplicatas sobre 5.431 imagens --
e nenhum crítico rodaria isso três vezes. A decisão, porém, está escrita no código e não muda
com o relógio: `ui/estado_do_rodape.ocupacao()` devolve `DETERMINADO` se e somente se a
operação registrou `total > 0` no `BusyRegistry`. Então a pergunta "esta barra é determinada?"
é a pergunta "alguém passou `total=` para este registro?", e essa a árvore sintática responde
com certeza, em dois segundos, sem PyQt6 instalado.

**O defeito que este módulo existe para pegar** é o par: o total está ali, à vista, no próprio
texto que a operação escreve na tela -- `detail=f"{len(rotulos)} imagem(ns)"` -- e mesmo assim
não é passado como número. A barra fica andando de um lado para o outro enquanto a frase ao
lado diz exatamente quantas imagens são. Isso é o §11.3 violado com a resposta na mão.

Uso (roda em qualquer venv -- não importa Qt):

    python -m caissa.ui.audit.progresso --tronco C:/Python-Chess2/ChessVisionOFF_Puro
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11, e o venv do **tronco** -- que é onde o PyQt6 mora
(ADR-0009) -- é 3.10. O alias deixa o resto do módulo escrito na forma nova e faz o arnês rodar
nos dois interpretadores.

**Escrito como `timezone(timedelta(0))` e não como `timezone.utc`, e isso foi aprendido do jeito
caro.** O `ruff --fix` desta suíte tem alvo py311: ele reescreve `timezone.utc` como
`datetime.UTC` e acrescenta o `import` correspondente -- que é exatamente o `import` que morre no
3.10. Um `# noqa` não protege, porque a regra pega o **uso** e não a linha do alias. A forma
construída é idêntica por definição (`timezone(timedelta(0)) is timezone.utc`) e não tem por onde
ser reescrita. A regra está certa para o resto do repositório; aqui ela quebrava o arnês."""

logger = logging.getLogger(__name__)

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

PASTAS = ("qt", "ui")
"""Onde a interface mora. `ui/` entra porque `busy.py` e `estado_do_rodape.py` são a decisão
-- quem faz uma barra ser determinada é `BusyOperation.fracao`, e ela está lá."""

ARGUMENTOS_DE_SETRANGE = 2
"""`setRange(min, max)` tem dois argumentos. Uma chamada com outro número não é a que se procura."""

CONTADORES_EMBUTIDOS = ("len", "sum", "count", "size", "cardinality")
"""Chamadas cujo resultado **é** um número, decidido pela função e não pela variável.

**Esta lista substitui `PISTAS_DE_TOTAL`, e a substituição é o conserto do §4.2 do F9-C7.** A
régua antiga procurava os nomes `("total", "count", "epochs", "epocas", "paginas", "n_", "len")`
**no texto do `detail=`**, e o crítico mostrou o que isso vale:

```
  detalhe='f"{quantas} amostra(s)"'   -> evidencia=''                     -> 0 defeitos
  detalhe='f"{total} amostra(s)"'     -> evidencia='a contagem esta ...'  -> DEFEITO BLOQUEANTE
```

**Mesma tela, mesmo 5431, mesma barra andando: renomear uma variável local invertia o veredito.**
Um portão que decide pelo nome de uma variável local mede a escolha de quem escreveu o nome.

O que ficou no lugar são duas regras que não olham nome de variável nenhum -- `_e_contagem` e
`_numero_calculado_na_mesma_funcao` -- mais o `_DE_N`, que lê a **frase que a pessoa vê**. `len`
está aqui como *função chamada*, e não como texto: `f"{len(rotulos)} imagem(ns)"` acusa porque a
chamada devolve um número, e uma variável chamada `len_de_algo` não acusa mais por acaso."""

PROFUNDIDADE_DA_CADEIA = 3
"""Quantos passos de atribuição `_numero_calculado_na_mesma_funcao` segue por aritmética.

Um passo pega `restante = parcial - 1`; três cobrem tudo o que o tronco escreve hoje e param
bem antes de a busca virar um grafo de fluxo de dados. O teto existe pelo mesmo motivo do
`TETO_DE_VOLTAS` de `audit/teclado.py`: um laço sem teto vira travamento no lugar de defeito."""

_DE_N = re.compile(r"\bde\s*\{")
"""`f"época 1 de {n}"` -- o texto já promete um total a quem lê a frase.

Se a frase na tela diz "de 8", a barra ao lado dela não tem desculpa para ser indeterminada:
o número existe, está formatado, e só não foi passado adiante."""


# --------------------------------------------------------------------------- o que se acha


@dataclass(frozen=True)
class Indicador:
    """Uma operação longa com indicação de progresso, e o que ela informa sobre si."""

    operacao: str
    arquivo: str
    linha: int
    especie: str
    """`registro` (vai ao `BusyRegistry` e ao rodapé) ou `barra` (um `QProgressBar` próprio)."""

    total_conhecido: bool
    determinado: bool
    cancelavel: bool
    evidencia: str
    """De onde saiu cada resposta. É o que permite discordar do veredito sem ler o código."""

    invisivel: bool = False
    """A operação roda ao fundo e **não** se registra nem se declara (F9-C3).

    É a espécie de defeito que este portão não conseguia ver antes de existir: ele varria os
    pontos de chamada de `busy.register`, e uma operação que nunca chama `register` não aparece em
    varredura nenhuma de `register`. Ver `_operacoes_de_fundo`."""

    def bloqueia(self) -> bool:
        """Os dois defeitos bloqueantes: barra indeterminada com total conhecido, ou invisível.

        **O segundo é do F9-C3 e é a lição do ciclo 3.** O portão devolvia `PASSOU` com seis
        operações inventariadas enquanto duas leituras assíncronas rodavam sem registro, sem
        progresso e sem cancelamento -- e ele não podia acusá-las, porque a única coisa que ele
        procurava era gente que se registra. Um portão que só enxerga quem se declara mede a
        disciplina de quem declara, e não o produto.
        """
        return (self.total_conhecido and not self.determinado) or self.invisivel


@dataclass
class _Registro:
    """Um `register(...)` achado, mais o que os `update(...)` do mesmo token acrescentam."""

    nome: str
    arquivo: str
    linha: int
    token: str
    total_no_registro: bool
    cancelavel: bool
    detalhe: str
    total_por_atualizacao: bool = False
    fontes_do_total: list[str] = field(default_factory=list)
    numero_no_detalhe: str = ""
    """Por que se sabe que o `detail=` carrega um número -- vazio quando não carrega.

    Preenchido por `_numero_no_detalhe`, que decide pela **forma** da expressão interpolada e
    pelo que a função dona faz com ela, nunca pelo nome da variável. Ver `CONTADORES_EMBUTIDOS`."""


# ------------------------------------------------------------------------- leitura da árvore


def _texto(no: ast.AST | None, fonte: str) -> str:
    if no is None:
        return ""
    return (ast.get_source_segment(fonte, no) or "").strip()


def _kwarg(chamada: ast.Call, nome: str) -> ast.expr | None:
    for palavra in chamada.keywords:
        if palavra.arg == nome:
            return palavra.value
    return None


def _verdadeiro(no: ast.expr | None) -> bool:
    """`True` literal. Uma expressão que *pode* ser verdadeira não é uma promessa cumprida."""
    return isinstance(no, ast.Constant) and no.value is True


def _amarrado_ao_cancel(cancellable: ast.expr | None, cancel: ast.expr | None) -> bool:
    """`cancellable=f is not None, cancel=f` -- a promessa amarrada à própria função (F9-C2).

    **A régua não afrouxou; ela passou a ler o padrão que `busy.register` já executa.** A regra
    daqui é "prometer o botão sem entregar a função é oferecer um cancelamento que não cancela", e
    `register` a implementa literalmente: `cancellable and cancel is not None`. Um ajudante que
    escreve `cancellable=cancelar is not None, cancel=cancelar` **não pode** prometer sem
    entregar -- as duas palavras são a mesma variável, e a promessa é verdadeira exatamente quando
    a função existe.

    Exigir o `True` literal reprovaria esse ajudante e aprovaria quem escrevesse `cancellable=True`
    com um `cancel` que é `None` em metade das chamadas -- ou seja, cobraria a forma e deixaria
    passar o conteúdo. A checagem é estrita: o nome comparado tem de ser **o mesmo** que vai em
    `cancel`.
    """
    if not isinstance(cancellable, ast.Compare) or not isinstance(cancel, ast.Name):
        return False
    if len(cancellable.ops) != 1 or not isinstance(cancellable.ops[0], ast.IsNot):
        return False
    esquerda = cancellable.left
    direita = cancellable.comparators[0]
    ehnone = isinstance(direita, ast.Constant) and direita.value is None
    return ehnone and isinstance(esquerda, ast.Name) and esquerda.id == cancel.id


def _alvo_do_token(no: ast.AST, fonte: str) -> str:
    """O nome do atributo que guarda o `BusyToken` -- é ele que liga um `register` aos `update`.

    Sem essa ligação, `qt/exportador.py` seria lido como indeterminado: ele registra sem total e
    só o informa na primeira callback de página. O token é o fio entre as duas linhas.
    """
    pai = getattr(no, "_pai_atribuicao", None)
    return _texto(pai, fonte) if pai is not None else ""


def _anotar_atribuicoes(arvore: ast.AST) -> None:
    """Marca cada `Call` que está do lado direito de uma atribuição com o alvo dela."""
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) and no.targets:
            no.value._pai_atribuicao = no.targets[0]  # type: ignore[attr-defined]


def _total_a_vista(detalhe: str, numero: str = "") -> str:
    """Evidência de que o total estava disponível na linha do registro. Vazio se não houver.

    Duas fontes, e **nenhuma das duas é o nome de uma variável**: a frase que a pessoa lê
    (`_DE_N` -- "época 1 de {n}" promete um total a quem a lê) e a análise estrutural de
    `_numero_no_detalhe`, que já veio pronta em `numero`.
    """
    if _DE_N.search(detalhe or ""):
        return f'o proprio texto diz "de {{...}}": {detalhe}'
    return numero


def _interpolacoes(no: ast.AST | None) -> list[ast.expr]:
    """As expressões interpoladas em qualquer f-string dentro daquele nó.

    Atravessa `IfExp` e `BinOp` porque o tronco escreve as duas formas:
    `f"{quantas} amostra(s)" if quantas is not None else ""` e
    `f"motor {motor}" + (" · modo bloco" if bloco else "")`.
    """
    if no is None:
        return []
    return [
        pedaco.value
        for filho in ast.walk(no)
        if isinstance(filho, ast.JoinedStr)
        for pedaco in filho.values
        if isinstance(pedaco, ast.FormattedValue)
    ]


def _e_contagem(no: ast.expr) -> str:
    """Se **a forma** da expressão a torna um número. Vazio se não dá para dizer.

    Duas formas, e as duas independem de como quem escreveu chamou a variável:

    * uma chamada a um contador embutido -- `len(rotulos)`, `sum(...)`;
    * uma interpolação com **especificação numérica de formato** -- `{x:d}`, `{x:,}`,
      `{x:.0f}`. Quem escreve `:d` está dizendo que aquilo é um inteiro.
    """
    if isinstance(no, ast.Call) and _termo_final(no.func) in CONTADORES_EMBUTIDOS:
        return f"o detail chama um contador: {ast.unparse(no)}"
    return ""


def _numero_calculado_na_mesma_funcao(no: ast.expr, dona: ast.AST | None) -> str:
    """Se a expressão interpolada é um nome que a **própria função** acabou de calcular.

    É a segunda metade do alvo do §4.2 do F9-C7 -- *"o portão passa a exigir `total=` sempre que
    a mesma função chame um contador"*. `_registrar_a_leitura` faz

    ```python
    quantas = self.contagem_de_amostras()
    self._busy_registry.register(..., detail=f"{quantas} amostra(s)")
    ```

    e a chamada está a duas linhas do `register` que não recebe `total=`. A regra é sobre a
    **atribuição**, não sobre o nome: renomear `quantas` para `n`, para `total` ou para `xyz`
    devolve exatamente a mesma acusação, que é a prova de vida que o crítico pediu.

    Só entra atribuição vinda de uma **chamada**: `motor = self._motor` é um atributo lido, e
    `f"motor {motor}"` não promete contagem nenhuma -- é o único `detail=` interpolado do tronco
    que esta regra tem de deixar em paz, e ela deixa.

    **E a cadeia é seguida por aritmética, desde o F9-C10.** O crítico do ciclo 9 plantou

    ```python
    parcial = self.contagem_de_amostras()
    restante = parcial - 1
    ...register(..., detail=f"{restante} a ler")
    ```

    e a regra **perdia** o caso: ela procurava `restante = <chamada>` e achava
    `restante = <BinOp>`. Uma subtração não deixa de ser um número, e "o valor veio de uma
    chamada" tem de valer para o valor **derivado** dela -- senão a forma de escapar do portão é
    somar zero. `PROFUNDIDADE_DA_CADEIA` limita a busca: ela existe para não seguir um grafo de
    atribuições inteiro, e três passos cobrem tudo o que o tronco escreve hoje.

    **O falso positivo simétrico continua aberto, e o número dele está no relatório do ciclo 10.**
    `nome = self.nome_do_livro()` -- uma chamada que devolve **string** -- acusa, porque a AST não
    sabe o tipo do retorno. Fechá-lo exigiria tipos ou execução; a regra que o fecharia por
    heurística de nome é exatamente a que o ciclo 8 tirou daqui, e ela custou "renomeie a
    variável e o veredito inverte".
    """
    if dona is None or not isinstance(no, ast.Name):
        return ""
    nomes = {no.id}
    for _passo in range(PROFUNDIDADE_DA_CADEIA):
        cresceu = False
        for filho in ast.walk(dona):
            if not isinstance(filho, ast.Assign):
                continue
            alvos = {alvo.id for alvo in filho.targets if isinstance(alvo, ast.Name)}
            if not (alvos & nomes):
                continue
            if isinstance(filho.value, ast.Call):
                return (
                    f"a propria funcao calcula o numero: {ast.unparse(filho)} -- "
                    f"e o detail o imprime sem que `total=` o receba"
                )
            # Não é chamada: pode ser aritmética **sobre** um valor que veio de uma. Os nomes
            # que aparecem do lado direito entram na busca do próximo passo.
            if isinstance(filho.value, (ast.BinOp, ast.UnaryOp)):
                antes = len(nomes)
                nomes |= {
                    parte.id for parte in ast.walk(filho.value) if isinstance(parte, ast.Name)
                }
                cresceu = cresceu or len(nomes) > antes
        if not cresceu:
            break
    return ""


def _numero_no_detalhe(no: ast.AST | None, dona: ast.AST | None) -> str:
    """A evidência de que o `detail=` carrega um número, ou vazio. Ver as duas regras acima."""
    for interpolada in _interpolacoes(no):
        for evidencia in (
            _e_contagem(interpolada),
            _numero_calculado_na_mesma_funcao(interpolada, dona),
        ):
            if evidencia:
                return evidencia
    return ""


def _funcao_que_contem(arvore: ast.AST, linha: int) -> ast.FunctionDef | None:
    """A `def` mais interna que contém aquela linha. `None` fora de função."""
    achada: ast.FunctionDef | None = None
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        dentro = no.lineno <= linha <= (no.end_lineno or no.lineno)
        if dentro and (achada is None or no.lineno > achada.lineno):
            achada = no
    return achada


def _nome_repassado(arvore: ast.AST, chamada: ast.Call, fonte: str) -> str:
    r"""O nome da operação quando o `register` recebe um **parâmetro** em vez de um literal.

    **É o item 7 do §7, e o defeito era do instrumento e não do produto.** O inventário do ciclo 1
    publicou duas operações chamadas `"nome"` -- `qt/painel_da_galeria.py` e
    `qt/painel_de_texto.py`. As duas **têm** rótulo: elas registram por um ajudante
    (`_registrar_ocupado(nome, ...)`), e o literal está nos pontos de chamada dele
    (`"varredura do livro"`, `"busca por nome na base"`, ...). O que a varredura leu foi o nome do
    parâmetro.

    Então: quando o argumento é um `Name` que é parâmetro da função que contém o `register`, esta
    função procura as chamadas **daquela função** no mesmo módulo e devolve os literais que elas
    passam naquela posição, separados por `" / "`. Duas operações diferentes pelo mesmo ajudante
    aparecem como duas, que é o que elas são.

    Devolve o texto do nó quando não há como resolver -- o comportamento de antes, para que um
    padrão que a varredura não entenda continue visível em vez de sumir.
    """
    if not isinstance(chamada.args[0] if chamada.args else None, ast.Name):
        return _texto(chamada.args[0] if chamada.args else None, fonte)
    parametro = chamada.args[0]
    if not isinstance(parametro, ast.Name):  # pragma: no cover - a guarda de cima já o garantiu
        return _texto(parametro, fonte)
    dona = _funcao_que_contem(arvore, chamada.lineno)
    if dona is None:
        return _texto(parametro, fonte)
    nomes = [arg.arg for arg in dona.args.args]
    if parametro.id not in nomes:
        return _texto(parametro, fonte)
    # `self` conta na `def` e **não** conta na chamada: `self._registrar_ocupado("x")` tem um
    # argumento posicional, e a `def` tem dois. Sem este desconto o nome sai da posição errada.
    desconto = 1 if nomes and nomes[0] in ("self", "cls") else 0
    posicao = nomes.index(parametro.id) - desconto
    if posicao < 0:
        return _texto(parametro, fonte)
    rotulos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or getattr(no.func, "attr", "") != dona.name:
            continue
        if len(no.args) <= posicao:
            continue
        alvo = no.args[posicao]
        if isinstance(alvo, ast.Constant) and isinstance(alvo.value, str):
            rotulos.append(alvo.value)
        elif isinstance(alvo, ast.JoinedStr):
            # `f"Exportando para {formato.nome}"`: a parte fixa é o que identifica a operação.
            fixas = [
                pedaco.value
                for pedaco in alvo.values
                if isinstance(pedaco, ast.Constant) and isinstance(pedaco.value, str)
            ]
            rotulos.append("".join(fixas).strip() + " …")
    return " / ".join(dict.fromkeys(rotulos)) or _texto(parametro, fonte)


def _registros_de(caminho: Path, raiz: Path) -> Iterator[_Registro]:
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    _anotar_atribuicoes(arvore)
    atualizam_com_total: set[str] = set()
    achados: list[_Registro] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr == "update" and _kwarg(no, "total") is not None:
            atualizam_com_total.add(_texto(no.func.value, fonte))
            continue
        if no.func.attr != "register":
            continue
        primeiro = no.args[0] if no.args else None
        nome = (
            primeiro.value
            if isinstance(primeiro, ast.Constant)
            else _nome_repassado(arvore, no, fonte)
        )
        achados.append(
            _Registro(
                nome=str(nome or "(sem nome literal)"),
                arquivo=str(caminho.relative_to(raiz)).replace("\\", "/"),
                linha=no.lineno,
                token=_alvo_do_token(no, fonte),
                total_no_registro=_kwarg(no, "total") is not None,
                # `busy.register` faz `cancellable and cancel is not None`: prometer o botão sem
                # entregar a função é oferecer um cancelamento que não cancela.
                cancelavel=(
                    _verdadeiro(_kwarg(no, "cancellable"))
                    or _amarrado_ao_cancel(_kwarg(no, "cancellable"), _kwarg(no, "cancel"))
                )
                and _kwarg(no, "cancel") is not None,
                detalhe=_texto(_kwarg(no, "detail"), fonte),
                numero_no_detalhe=_numero_no_detalhe(
                    _kwarg(no, "detail"), _funcao_que_contem(arvore, no.lineno)
                ),
            )
        )

    for registro in achados:
        registro.total_por_atualizacao = registro.token in atualizam_com_total
        yield registro


def _barras_de(caminho: Path, raiz: Path) -> Iterator[Indicador]:
    """Os `QProgressBar` cujo intervalo é fixado em `(0, 0)` -- a barra indeterminada do Qt.

    `qt/rodape.py` também chama `setRange(0, 0)`, e ali **não** é defeito: o rodapé alterna
    entre os dois modos conforme o `BusyRegistry`, e a chamada está dentro do ramo indeterminado
    de `_trocar_modo_da_barra`. O que este detector procura é a outra forma -- a barra que nasce
    `(0, 0)` na construção do widget e nunca sai de lá.
    """
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    alterna = "setRange(0, 100)" in fonte or ("setRange(0, 0)" in fonte and "modo" in fonte)

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr != "setRange" or len(no.args) != ARGUMENTOS_DE_SETRANGE:
            continue
        valores = [arg.value if isinstance(arg, ast.Constant) else None for arg in no.args]
        if valores != [0, 0]:
            continue
        classe = _classe_em(arvore, no.lineno)
        # Alternante = o mesmo arquivo também sabe voltar para (0, 100). É o rodapé, e ele está
        # certo: a indeterminação dele é consequência de a operação não ter total, não escolha.
        if alterna and "rodape" in caminho.name:
            continue
        yield Indicador(
            operacao=f"{classe}: barra fixa em indeterminada",
            arquivo=str(caminho.relative_to(raiz)).replace("\\", "/"),
            linha=no.lineno,
            especie="barra",
            total_conhecido=False,
            determinado=False,
            cancelavel=False,
            evidencia="setRange(0, 0) na construcao do widget, sem caminho de volta",
        )


CLASSES_DE_THREAD = (
    "Thread",
    "Timer",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "Process",
    "Pool",
    "QThread",
    "QRunnable",
    # **Processo externo é operação de fundo pela mesma pergunta**, e as duas entraram da
    # sabotagem do crítico do ciclo 7 (formas f e g). O portão não pergunta "abriu uma thread?",
    # pergunta "há trabalho correndo que a janela não mostra?" -- e um `Popen` sem `wait` ou um
    # `QProcess.start` deixam trabalho correndo exatamente assim. Nenhum dos dois estava aqui, e
    # os dois escapavam inteiros: `Popen` não é subclasse de `Thread`, e `QProcess` tem `start`
    # num receptor sem nome de pool.
    "Popen",
    "QProcess",
    # `multiprocessing.pool.ThreadPool` -- forma (b) da sabotagem do ciclo 8. `Pool` já estava
    # aqui e o termo final de `ThreadPool` é `ThreadPool`: a régua compara o termo final, então
    # o irmão mais usado do `Pool` escapava inteiro.
    "ThreadPool",
)
"""As classes da biblioteca cuja **construção** abre uma linha de execução paralela.

**Reconhecidas pelo último termo do nome**, e é essa a diferença que fecha o defeito nº 4 do
ciclo 5. A lista anterior -- `("threading.Thread", "Tarefa")` -- comparava `ast.unparse(no.func)`
com **duas grafias literais**, e o crítico plantou seis operações de fundo em `qt/`: o detector
achou **uma**. `from threading import Thread` escreve `Thread`, `threading.Timer` escreve
`Timer`, `ThreadPoolExecutor(1).submit(...)` não escreve nenhuma das duas -- e as três abrem
thread igual. Comparar o **termo final** faz `threading.Thread`, `Thread` e
`concurrent.futures.ThreadPoolExecutor` caírem todas na mesma regra, que é o que o nome do
detector promete.

`Tarefa` saiu daqui de propósito: ela é `class Tarefa(QThread)` em `qt/trabalho.py`, e
`classes_de_thread` a encontra **por herança**. Uma subclasse nova não precisa mais ser
acrescentada a mão -- que era exatamente o furo pelo qual a forma (e) do crítico passou."""

METODOS_DE_SUBMISSAO = (
    "submit",
    "start_new_thread",
    "run_in_executor",
    "apply_async",
    # **`to_thread` e `moveToThread` entraram no ciclo 8**, das formas (d) e (e) da sabotagem do
    # crítico do ciclo 7. `asyncio.to_thread(f)` é a forma moderna de `run_in_executor`, que já
    # estava aqui; `x.moveToThread(fio)` é **o idioma canônico do Qt** -- o mais provável de
    # aparecer num `qt/` que cresça -- e escapava inteiro: ele não constrói thread nenhuma no
    # ponto de chamada (o `QThread` nasceu no `__init__`) e não se chama `submit`. O crítico foi
    # justo sobre isto: "o tronco é limpo hoje, então '0 invisíveis' é verdade; o portão é que
    # não consegue mantê-lo".
    "to_thread",
    "moveToThread",
    # As três do `asyncio` que abrem trabalho sem nomear thread nenhuma -- formas (c) e (d) da
    # sabotagem do ciclo 8. `create_task` e `ensure_future` põem uma corrotina para correr
    # concorrente; `run_coroutine_threadsafe` a empurra para um laço em **outra** thread.
    "create_task",
    "ensure_future",
    "run_coroutine_threadsafe",
)
"""Chamadas que empurram trabalho para uma linha de execução **já aberta**.

Um `self._pool.submit(...)` não constrói classe nenhuma no ponto de chamada: o pool nasceu no
`__init__` e some da varredura de construção. `map` **não** entra aqui -- é o nome mais comum do
repositório e um detector que o aceitasse acusaria dezenas de laços que não abrem thread
nenhuma. Portão que grita demais deixa de ser lido, que é a outra forma de ficar cego. Ele entra
em `METODOS_DE_POOL`, onde o receptor paga a conta da precisão."""

METODOS_DE_POOL = (
    "map",
    "imap",
    "imap_unordered",
    "starmap",
    "map_async",
    "starmap_async",
    "start",
    # Forma (e) da sabotagem do ciclo 8: `tryStart` é o irmão de `start` em `QThreadPool` --
    # submete se houver linha livre -- e não estava em régua nenhuma.
    "tryStart",
)
"""Métodos que só são submissão **quando o receptor é um pool** -- ver `RECEPTORES_DE_POOL`.

**`map` é a forma (c) da sabotagem do crítico do ciclo 7**, e ela passou por uma exclusão
declarada: `map` estava fora de `METODOS_DE_SUBMISSAO` de propósito, porque `map` é o nome mais
comum do repositório. A exclusão está certa e continua; o que faltava era a outra metade --
`self._pool.map(f, itens)` roda `f` em N threads e o receptor **diz** que é um pool. Exigir as
duas coisas mantém o portão silencioso sobre `dict.map`/`list(map(...))` e o faz enxergar a
submissão que a exclusão escondia.

`start` fica aqui pela mesma razão e com a regra extra de exigir argumento: ver
`RECEPTORES_DE_POOL`."""

RECEPTORES_DE_POOL = ("threadpool", "processpool", "pool", "executor")
"""Receptores em que um `.start(...)` **com argumento** é submissão, e não partida de relógio.

`start` não pode entrar em `METODOS_DE_SUBMISSAO`: `qt/` tem dezenas de `self._relogio.start(250)`
e todo `Tarefa(...).start()` é a *partida* de uma thread que a regra de construção já contou --
somá-la de novo infla o placar. Mas `QThreadPool.globalInstance().start(tarefa)` é a única forma
de empurrar um `QRunnable` para a fila do Qt, e ela não constrói nada no ponto de chamada nem se
chama `submit`. **Este furo saiu da sabotagem do ciclo 6, não da do ciclo 5**: escrevi oito formas
novas contra o detector recém-alargado e três passaram; esta é uma delas. A regra pede as duas
coisas -- nome de pool no receptor **e** pelo menos um argumento -- porque `pool.start()` sem
argumento nenhum não submete trabalho: ele liga o pool."""

FUNCOES_DE_PROCESSO_EXTERNO = ("startfile", "spawnl", "spawnle", "spawnv", "spawnve", "spawnlp", "spawnvp")
"""Funções que largam um programa externo correndo e devolvem na hora -- forma (g) do ciclo 8.

`os.startfile` é o caminho do Windows e não constrói classe nenhuma: nem `CLASSES_DE_THREAD`
nem `METODOS_DE_SUBMISSAO` o alcançavam. `os.system` e `subprocess.run` **não** entram: eles
bloqueiam, e o que bloqueia é problema do portão `caissa.ui.audit.bloqueio`, não deste.

Hoje `qt/` não chama nenhuma delas (`ui/leitura_do_pdf.py` chama, e `ui/` não é varrido por
esta régua -- ver `_operacoes_de_fundo`), então a regra é silenciosa sobre o tronco real."""

EMBRULHOS_DE_CHAMADA = ("partial", "partialmethod")
"""Funções que guardam uma classe para chamá-la depois, sem nomeá-la no ponto da chamada.

Forma (b) da sabotagem do crítico do ciclo 7. A regra olha o **primeiro argumento**, que é onde
o chamável embrulhado vai nas duas: `functools.partial(threading.Thread, target=f)` acusa, e os
dez `partial(self._ir, …)` de `qt/painel_da_galeria.py` não."""

APELIDOS_IGNORADOS = frozenset({"_", "__"})
"""Nomes de apelido que não valem resolução -- placeholders, nunca uma classe."""

RECEPTORES_DE_OCUPACAO = ("busy", "ocupad", "ocupac", "registry", "registro_de_ocupacao")
"""Que objeto, num `X.register(...)`, é o `BusyRegistry` -- pelo nome do receptor.

**A regra antiga aceitava qualquer chamada cujo nome contivesse `register` ou `registrar`**, e o
crítico do ciclo 5 marcou uma thread crua como REGISTRADA plantando um
`self._registrar_atalho_de_teclado()` na mesma função. Não é hipótese: `qt/` tem hoje
`self.historico.registrar`, `self._historico.registrar` e `self._mapa.registrar` -- três
`registrar` que não têm relação nenhuma com ocupação e que provariam registro pela regra
antiga."""

ASSINATURA_DO_REGISTRO = ("loses_work", "cancellable")
"""Argumentos que só `BusyRegistry.register` tem. É a segunda prova, independente do nome.

Um registro escrito com o receptor chamado de outra coisa (`self._estado.register(...)`)
continua sendo reconhecido pela assinatura -- e uma função que **não** registra não passa a
registrar por acaso, porque nada mais neste código recebe `loses_work=`."""

PROFUNDIDADE_DO_AJUDANTE = 3
"""Quantos níveis de ajudante o detector segue atrás do registro, dentro do mesmo módulo.

A Galeria e a aba de Texto registram por `self._registrar_ocupado`, que chama
`self._busy.register`. Exigir a chamada literal na mesma função empurraria para copiar o
registro em três lugares; aceitar o **nome** aceita `self.historico.registrar`. Seguir a
definição resolve os dois: `_registrar_ocupado` prova registro porque o corpo **dele** prova, e
`historico.registrar` não prova porque a definição dele não está aqui."""


def _fora_do_registro(raiz: Path) -> dict[tuple[str, str], str]:
    """A tabela `ui/busy.FORA_DO_REGISTRO`, lida por árvore sintática.

    **Lida do produto, e não copiada para cá.** A declaração de quem fica fora do registro é uma
    decisão -- ela responde *"o que se perde ao fechar a janela?"* -- e por isso mora em `ui/`,
    onde `tests/test_busy.py` a cobra. Este portão precisa da **mesma** tabela: uma cópia daria
    um arnês aprovando uma exceção que o produto já tirou, ou acusando uma que ele acabou de
    escrever.

    Por AST e não por `import` porque este módulo roda em qualquer venv, inclusive um sem o
    tronco no `sys.path` -- e devolve vazio quando não acha o arquivo, que é o que faz toda
    operação de fundo aparecer como invisível em vez de o portão morrer.
    """
    arquivo = raiz / "src" / "chess_diagram_ocr" / "ui" / "busy.py"
    if not arquivo.is_file():
        return {}
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    for no in ast.walk(arvore):
        alvo = no.targets[0] if isinstance(no, ast.Assign) and no.targets else None
        if isinstance(no, ast.AnnAssign):
            alvo, valor = no.target, no.value
        elif isinstance(no, ast.Assign):
            valor = no.value
        else:
            continue
        if not (isinstance(alvo, ast.Name) and alvo.id == "FORA_DO_REGISTRO"):
            continue
        try:
            tabela = ast.literal_eval(valor) if valor is not None else {}
        except ValueError:  # pragma: no cover - a tabela é literal por construção
            return {}
        return {tuple(chave): str(motivo) for chave, motivo in dict(tabela).items()}
    return {}


def _termo_final(no: ast.expr, apelidos: dict[str, str] | None = None) -> str:
    """O último termo de uma expressão de chamada: `threading.Thread` -> `Thread`.

    Com `apelidos`, o termo passa ainda pela tabela de `import ... as ...` do próprio arquivo,
    para que `from threading import Thread as T` faça `T(...)` responder `Thread`.

    **Um índice não esconde a classe** -- forma (a) da sabotagem do ciclo 8:
    `FABRICAS["fundo"](target=…)` tem `ast.unparse` igual a `FABRICAS['fundo']`, que não é nome
    nenhum. O termo passa a ser o do **contêiner**, e `apelidos_de_thread` põe `FABRICAS` na
    tabela quando o literal atribuído a ele carrega uma classe de thread.
    """
    while isinstance(no, ast.Subscript):
        no = no.value
    try:
        termo = ast.unparse(no).rsplit(".", 1)[-1]
    except Exception:  # pragma: no cover - ast.unparse não falha em árvore analisada
        return ""
    return (apelidos or {}).get(termo, termo)


def apelidos_de_thread(arvore: ast.AST) -> dict[str, str]:
    """A tabela `import ... as ...` do arquivo: nome local -> nome verdadeiro.

    **O segundo furo da sabotagem do ciclo 6.** O detector do ciclo 6 passou a comparar o
    *termo final* do nome, o que fecha `threading.Thread`, `Thread` e `threading.Timer` de uma
    vez -- mas o termo final de `T(target=...)` é `T`, e `from threading import Thread as T` é
    uma linha legal que nenhuma lista de nomes alcança. Pior: `class _Derivada(T)` some junto,
    porque a herança é seguida pelo nome da base. Duas das oito formas que plantei passaram
    exatamente por aqui.

    Só o `asname` interessa no `import`. `import threading as th` já era visto, porque
    `th.Thread` tem `Thread` como termo final; o que escapava era o apelido **da própria classe**.

    **O apelido por atribuição entrou no ciclo 8** -- forma (a) da sabotagem do crítico do ciclo
    7. `Fabrica = threading.Thread` seguido de `Fabrica(target=…).start()` não é um `import`, e
    por isso não passava por aqui: o termo final de `Fabrica(...)` é `Fabrica`, e nenhuma lista
    de nomes o alcança. A regra é estreita de propósito -- só entra atribuição de um **nome nu**
    (`Name` ou `Attribute`), nunca de uma chamada: `tarefa = Tarefa(...)` é uma *instância*, e
    tratá-la como apelido de classe faria `tarefa.qualquer_coisa()` virar construção de thread.
    """
    tabela: dict[str, str] = {}
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            for nome in no.names:
                if not nome.asname or nome.asname in APELIDOS_IGNORADOS:
                    continue
                verdadeiro = nome.name.rsplit(".", 1)[-1]
                if verdadeiro != nome.asname:
                    tabela[nome.asname] = verdadeiro
        elif isinstance(no, ast.Assign) and isinstance(no.value, (ast.Name, ast.Attribute)):
            verdadeiro = ast.unparse(no.value).rsplit(".", 1)[-1]
            for alvo in no.targets:
                if not isinstance(alvo, ast.Name) or alvo.id in APELIDOS_IGNORADOS:
                    continue
                if verdadeiro != alvo.id:
                    tabela.setdefault(alvo.id, verdadeiro)
        elif isinstance(no, ast.Assign) and isinstance(no.value, (ast.Dict, ast.List, ast.Tuple)):
            # **Um contêiner literal de classes** -- forma (a) do ciclo 8. Só entra se algum
            # elemento **for** uma classe de thread conhecida pela semente: um dicionário de
            # funções continua invisível, que é o certo.
            dentro = (
                list(no.value.values) if isinstance(no.value, ast.Dict) else list(no.value.elts)
            )
            for item in dentro:
                if not isinstance(item, (ast.Name, ast.Attribute)):
                    continue
                classe = ast.unparse(item).rsplit(".", 1)[-1]
                if classe not in CLASSES_DE_THREAD:
                    continue
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name) and alvo.id not in APELIDOS_IGNORADOS:
                        tabela.setdefault(alvo.id, classe)
    return tabela


def classes_de_thread(raiz: Path) -> set[str]:
    """Os nomes de classe que, construídos, abrem uma linha de execução -- **com as subclasses**.

    Parte de `CLASSES_DE_THREAD` e cresce por herança, em ponto fixo sobre `qt/` e `ui/`:
    `class Tarefa(QThread)` entra porque `QThread` está na semente, e uma
    `class MinhaTarefa(Tarefa)` entraria na volta seguinte.

    **É o furo pelo qual passou a forma (e) da sabotagem do ciclo 5** -- `class _MinhaThread
    (threading.Thread)` seguida de `_MinhaThread().start()`. Nenhuma lista de grafias literais
    pega isso, porque o nome da subclasse é escolhido por quem a escreve. A herança, sim.
    """
    nomes = set(CLASSES_DE_THREAD)
    bases_por_classe: dict[str, set[str]] = {}
    for arquivo in _arquivos(raiz):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        except SyntaxError:  # pragma: no cover - o tronco compila
            continue
        apelidos = apelidos_de_thread(arvore)
        for no in ast.walk(arvore):
            if isinstance(no, ast.ClassDef):
                bases_por_classe.setdefault(no.name, set()).update(
                    _termo_final(base, apelidos) for base in no.bases
                )
    mudou = True
    while mudou:
        mudou = False
        for classe, bases in bases_por_classe.items():
            if classe not in nomes and bases & nomes:
                nomes.add(classe)
                mudou = True
    return nomes


def forma_de_fundo(
    no: ast.Call, thread_classes: set[str], apelidos: dict[str, str] | None = None
) -> str:
    """Como esta chamada abre trabalho de fundo, ou `""` se ela não abre.

    Quatro regras, e cada uma existe porque a anterior não bastou: **construção** de classe de
    thread ou de processo (inclusive subclasse, import direto, apelido de import e apelido por
    atribuição), **submissão** a uma linha já aberta (`submit`, `run_in_executor`, `to_thread`,
    `moveToThread`, …), **submissão a um pool** por um método que só conta com receptor de pool
    (`map`, `start`, …) e **a classe de thread guardada num `partial`**. A string devolvida vai
    para a `evidencia`, para o relatório dizer *por que* aquela linha entrou.
    """
    termo = _termo_final(no.func, apelidos)
    if termo in thread_classes:
        return f"constroi {ast.unparse(no.func)}"
    if termo in METODOS_DE_SUBMISSAO:
        return f"submete trabalho por {ast.unparse(no.func)}"
    if termo in METODOS_DE_POOL:
        texto = ast.unparse(no.func)
        receptor = texto.rsplit(".", 1)[0].lower() if "." in texto else ""
        # `start` pede argumento; `map` e as irmãs já o pedem pela assinatura. `pool.start()`
        # sem argumento nenhum não submete trabalho: ele liga o pool.
        if any(palavra in receptor for palavra in RECEPTORES_DE_POOL) and (
            no.args or termo != "start"
        ):
            return f"submete trabalho por {texto}"
    # **A classe guardada num `partial`** -- forma (b) da sabotagem do crítico do ciclo 7:
    # `functools.partial(threading.Thread, target=f)()` não nomeia thread nenhuma na chamada que
    # de fato a abre. `partial` aparece dez vezes em `qt/` hoje e **nenhuma** com classe de
    # thread no primeiro argumento, então a regra é silenciosa sobre o tronco real.
    if termo in EMBRULHOS_DE_CHAMADA and no.args:
        embrulhado = _termo_final(no.args[0], apelidos)
        if embrulhado in thread_classes:
            return f"embrulha {ast.unparse(no.args[0])} em {termo}"
    # **Programa externo largado a correr** -- forma (g) do ciclo 8. Ver
    # `FUNCOES_DE_PROCESSO_EXTERNO` para por que `os.system` não está lá.
    if termo in FUNCOES_DE_PROCESSO_EXTERNO:
        return f"larga um programa externo por {ast.unparse(no.func)}"
    # **A classe buscada por `getattr`** -- forma (h) do ciclo 8, e a irmã da (h) do crítico do
    # ciclo 7 (`importlib.import_module("threading").Thread`). O nome da classe está ali, numa
    # constante: `getattr(threading, "Thread")(target=f)`.
    if isinstance(no.func, ast.Call) and _termo_final(no.func.func, apelidos) == "getattr":
        argumentos = no.func.args
        pedido = argumentos[1] if len(argumentos) > 1 else None
        if isinstance(pedido, ast.Constant) and str(pedido.value) in thread_classes:
            return f"constroi {ast.unparse(no.func)}"
    return ""


def _prova_de_registro(no: ast.Call) -> bool:
    """Se **esta** chamada é um registro no `BusyRegistry`. Ver `RECEPTORES_DE_OCUPACAO`."""
    if _termo_final(no.func) != "register":
        return False
    texto = ast.unparse(no.func)
    receptor = texto.rsplit(".", 1)[0].lower() if "." in texto else ""
    if any(palavra in receptor for palavra in RECEPTORES_DE_OCUPACAO):
        return True
    chaves = {palavra.arg for palavra in no.keywords if palavra.arg}
    return bool(chaves & set(ASSINATURA_DO_REGISTRO))


def _funcoes_do_modulo(arvore: ast.AST) -> dict[str, ast.AST]:
    return {
        no.name: no
        for no in ast.walk(arvore)
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _registra(
    funcao: ast.AST,
    funcoes: dict[str, ast.AST] | None = None,
    *,
    profundidade: int = PROFUNDIDADE_DO_AJUDANTE,
    vistos: frozenset[str] = frozenset(),
) -> bool:
    """Se a função registra a operação no `BusyRegistry` -- ela mesma ou por um ajudante seu.

    **A regra antiga era `"registrar" in nome`**, e o ciclo 5 mostrou o que ela aceita: uma
    thread crua numa função que também chama `self._registrar_atalho_de_teclado()` saía marcada
    como REGISTRADA. Agora a prova é a chamada certa -- `X.register(...)` num receptor de
    ocupação, ou com a assinatura do `BusyRegistry` -- e o ajudante só vale se a **definição**
    dele, neste módulo, tiver essa prova.
    """
    funcoes = funcoes if funcoes is not None else {}
    for no in ast.walk(funcao):
        if not isinstance(no, ast.Call):
            continue
        if _prova_de_registro(no):
            return True
        if profundidade <= 0:
            continue
        nome = _termo_final(no.func)
        ajudante = funcoes.get(nome)
        if ajudante is None or nome in vistos or ajudante is funcao:
            continue
        if _registra(
            ajudante, funcoes, profundidade=profundidade - 1, vistos=vistos | {nome}
        ):
            return True
    return False


def _operacoes_de_fundo(
    caminho: Path,
    raiz: Path,
    declaradas: dict[tuple[str, str], str],
    thread_classes: set[str] | None = None,
) -> Iterator[Indicador]:
    """Toda thread aberta neste arquivo, dita registrada, declarada ou **invisível** (F9-C3).

    **Este é o detector que faltava, e o ciclo 3 disse por quê.** As duas leituras assíncronas
    criadas no ciclo 2 rodavam com a aba cinza e o rodapé escrevendo "Lendo o dataset…", e o
    inventário deste portão devolvia seis linhas em que nenhuma era elas -- porque a varredura
    procurava `register` e elas nunca chamavam `register`. O portão que existe para achar
    "operação longa sem cancelamento" não podia achar a operação longa sem cancelamento.

    A régua é a mesma que `tests/test_busy.py` já aplicava, e o portão passa a aplicá-la também:
    **ou a operação se registra, ou ela está declarada em `ui/busy.FORA_DO_REGISTRO` com o motivo
    escrito.** O que muda é quem cobra -- o teste cobra na suíte do tronco, este arnês cobra no
    relatório que o crítico lê.
    """
    if caminho.parent.name != "qt":
        return
    thread_classes = thread_classes if thread_classes is not None else set(CLASSES_DE_THREAD)
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    pais: dict[ast.AST, ast.AST] = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[filho] = no
    funcoes = _funcoes_do_modulo(arvore)
    apelidos = apelidos_de_thread(arvore)
    # **Uma linha, uma operação.** `ThreadPoolExecutor(1).submit(f)` casa com as duas regras --
    # constrói o pool e submete a ele --, e são a mesma thread. Sem isto o relatório contaria 7
    # onde há 6, e um portão que infla o próprio placar é tão pouco confiável quanto um cego.
    ja_contadas: set[tuple[int, str]] = set()

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        forma = forma_de_fundo(no, thread_classes, apelidos)
        if not forma:
            continue
        dona: ast.AST | None = pais.get(no)
        while dona is not None and not isinstance(dona, (ast.FunctionDef, ast.AsyncFunctionDef)):
            dona = pais.get(dona)
        quem = getattr(dona, "name", "(fora de função)")
        if (no.lineno, quem) in ja_contadas:
            continue
        ja_contadas.add((no.lineno, quem))
        chave = (caminho.name, quem)
        registra = dona is not None and _registra(dona, funcoes)
        motivo = declaradas.get(chave, "")
        yield Indicador(
            operacao=f"{_classe_em(arvore, no.lineno)}.{quem}: operacao de fundo",
            arquivo=str(caminho.relative_to(raiz)).replace("\\", "/"),
            linha=no.lineno,
            especie="fundo",
            total_conhecido=False,
            determinado=False,
            # Uma thread de fundo não tem barra própria: as três colunas da tabela principal são
            # sobre o indicador, e o que importa aqui é o estado, que vai na `evidencia`.
            cancelavel=False,
            evidencia=(
                f"REGISTRADA ({forma}): o rodape a mostra e o Cancelar vale para ela"
                if registra
                else f"DECLARADA em ui/busy.FORA_DO_REGISTRO ({forma}): {motivo[:80]}"
                if motivo
                else f"INVISIVEL ({forma}): nao se registra e nao esta declarada -- "
                "nem o rodape nem este portao a veem"
            ),
            invisivel=not registra and not motivo,
        )


def _classe_em(arvore: ast.AST, linha: int) -> str:
    melhor = "(modulo)"
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.lineno <= linha <= (no.end_lineno or linha):
            melhor = no.name
    return melhor


def _callbacks_de_progresso(caminho: Path) -> set[str]:
    """Funções que recebem `total` como parâmetro -- prova de que a operação **sabe** o total.

    É a evidência mais forte que a leitura estática consegue: `_progresso(self, pagina, total,
    ...)` só existe porque quem chama tem o total na mão a cada passo. Uma barra indeterminada
    ao lado de uma callback dessas não é limitação, é omissão.
    """
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    return {
        no.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef)
        and any(arg.arg == "total" for arg in no.args.args)
    }


# ------------------------------------------------------- a faixa REAL da barra, medida no Qt

TOTAL_DE_REFERENCIA = 289
"""O total com que a faixa determinada é medida. É o `total=` real de `qt/exportador.py`.

Um número inventado mediria uma barra que o produto não monta; este é o de uma operação que
existe, e é o mesmo que o crítico do ciclo 7 usou para medir a barra no pixel das 36 capturas."""

ASSENTAR_MS = 90
"""Quanto tempo a fila de eventos gira antes de a faixa ser lida, em milissegundos.

**Medido contra a sabotagem que o pediu** (F9-C9 §4.2): o crítico adiou
`RodapeDaJanela._trocar_modo_da_barra` com um `QTimer.singleShot(40, ...)` e o portão continuou
verde, porque lia o estado inicial do widget. 90 ms é o dobro daquele atraso mais folga, e ainda
é um custo de milissegundos por valor distinto de total (ver `_FAIXAS_MEDIDAS`)."""


def faixa_da_barra_do_rodape(total: int, raiz: Path = TRONCO) -> tuple[int, int] | None:
    """`(minimum, maximum)` do `QProgressBar` do rodapé **vivo**, para um `total` daquele valor.

    **Por que medir em vez de deduzir** (F9-C7, §4.2). Este portão dizia "determinada" quando
    achava um `total=` no código e "indeterminada" quando não achava -- ou seja, ele **supunha**
    o que o widget faz com o argumento. Duas coisas erradas saem daí: a suposição pode estar
    errada (bastaria `qt/rodape.py` deixar de trocar de modo para o portão continuar verde com a
    barra andando), e o número publicado não é uma medida, é uma releitura do mesmo código.

    O crítico do ciclo 7 mediu a barra **no pixel das 36 capturas** -- um bloco de 59 px que anda
    e dá a volta na pista de 118 px, em 28 delas -- e registrou uma operação com `total=289` na
    janela viva, obtendo `min=0 max=100`. Esta função é essa medida, feita pelo portão: constrói
    o rodapé de verdade, entrega uma `BusyOperation` com aquele `total`, e lê o intervalo que o
    widget ficou tendo. `maximum > minimum` é determinada; `(0, 0)` é a marquise do Qt.

    Devolve `None` quando não dá para medir -- venv sem PyQt6, tronco fora do `sys.path`,
    plataforma sem servidor gráfico. **Não levanta**: o portão roda em qualquer venv, e um
    arnês que morresse por falta de binding seria pior que um que declara o que não mediu. Quem
    chama diz, no relatório, se a coluna veio de medida ou de leitura de código.

    ---

    **A leitura espera a fila de eventos assentar, e isso é o §4.2 da crítica do ciclo 9.** A
    primeira versão desta função lia o intervalo logo depois de `aplicar_ocupacao`, e o crítico
    mostrou o preço com duas sabotagens no rodapé:

        faixa que chega TARDE (QTimer.singleShot(40, ...)):  total=289 -> (0,100) -> 0 acusadas
        faixa que RECUA depois de lida:                      total=289 -> (0,100) -> 0 acusadas

    Nos dois casos o portão lia o estado **inicial** do widget -- `RodapeDaJanela.__init__` já
    faz `setRange(0, 100)` --, e não o que a operação produz. Um tique apagava o portão inteiro.
    Aqui a leitura só acontece depois de `ASSENTAR_MS` de fila girando, que é o mesmo remédio de
    `caissa.ui.audit.execucao.TEMPO_DE_ASSENTAR_S`.
    """
    origem = raiz / "src"
    if not origem.is_dir():  # pragma: no cover - tronco ausente
        return None
    if str(origem) not in sys.path:
        sys.path.insert(0, str(origem))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6.QtWidgets import QApplication

        from chess_diagram_ocr.qt.rodape import RodapeDaJanela
        from chess_diagram_ocr.ui.busy import BusyOperation
    except Exception:  # noqa: BLE001 - venv sem binding, e isso é um estado declarado
        return None
    try:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        rodape = RodapeDaJanela()
        rodape.aplicar_ocupacao(
            [
                BusyOperation(
                    name="medicao do portao",
                    loses_work=False,
                    detail="",
                    feito=0,
                    total=int(total),
                )
            ]
        )
        # **Gira a fila até `ASSENTAR_MS`, e só então lê.** Um `processEvents()` solto não
        # entrega um `QTimer.singleShot(40, ...)`: o tique só chega depois de 40 ms de relógio.
        limite = time.monotonic() + ASSENTAR_MS / 1000.0
        while time.monotonic() < limite:
            app.processEvents()
            time.sleep(0.005)
        faixa = (rodape.barra_de_progresso().minimum(), rodape.barra_de_progresso().maximum())
        rodape.deleteLater()
        app.processEvents()
    except Exception:  # noqa: BLE001 - medir não pode custar o relatório
        logger.debug("Não foi possível medir a faixa da barra do rodapé.", exc_info=True)
        return None
    return faixa


def faixas_medidas(raiz: Path = TRONCO) -> dict[bool, tuple[int, int]]:
    """As duas faixas que importam: com `total=` e sem. Vazio quando não deu para medir.

    Mantida porque é a forma que o teste do ciclo 8 sabota nos dois sentidos. A coluna
    `determinado` do relatório **não sai mais daqui** -- ver `faixa_por_operacao`.
    """
    medidas: dict[bool, tuple[int, int]] = {}
    for com_total, valor in ((True, TOTAL_DE_REFERENCIA), (False, 0)):
        faixa = faixa_da_barra_do_rodape(valor, raiz)
        if faixa is None:
            return {}
        medidas[com_total] = faixa
    return medidas


def faixa_por_operacao(
    total: int, raiz: Path = TRONCO, _cache: dict[int, tuple[int, int] | None] | None = None
) -> tuple[int, int] | None:
    """A faixa que o rodapé fica tendo **com aquela ocupação**, medida num rodapé novo.

    **A diferença para `faixas_medidas` é o escopo da pergunta, e ela foi cobrada** (F9-C9 §4.2):
    aquela media duas vezes -- `total=289` e `total=0` -- e depois resolvia `determinado` por
    consulta a esse par, com chave `passa_total`. Resultado medido pelo crítico nas sete
    operações reais: *"7 registros; 0 em que `passa_total` e `determinado` divergem"*. A coluna
    que o relatório apresentava como **medida** carregava exatamente a mesma informação que a
    coluna lida do código.

    Aqui a medida é por operação e com o total daquela operação, e o veredito exige **duas**
    coisas (ver `determinado_medido`): a faixa ser determinada, e ela **diferir** da faixa que a
    mesma barra tem sob uma ocupação indeterminada. A segunda é o que torna o número irredutível
    à leitura do código: um rodapé que deixasse de trocar de modo daria a mesma faixa nos dois
    casos, e todas as operações cairiam para `determinado=False` -- que é o defeito, acusado.
    """
    cache = _cache if _cache is not None else _FAIXAS_MEDIDAS
    chave = int(total)
    if chave not in cache:
        cache[chave] = faixa_da_barra_do_rodape(chave, raiz)
    return cache[chave]


def determinado_medido(
    total: int, raiz: Path = TRONCO
) -> tuple[bool | None, tuple[int, int] | None, tuple[int, int] | None]:
    """`(determinado, faixa com a ocupação, faixa de repouso indeterminado)`.

    `determinado` é `None` quando não deu para medir -- e aí o relatório volta a ler o código e
    **diz que voltou**, que é a disciplina de `faixa_da_barra_do_rodape`.
    """
    com = faixa_por_operacao(total, raiz)
    sem = faixa_por_operacao(0, raiz)
    if com is None or sem is None:
        return (None, com, sem)
    return (com[1] > com[0] and com != sem, com, sem)


_FAIXAS_MEDIDAS: dict[int, tuple[int, int] | None] = {}
"""Uma medição por valor de total, e não uma por operação: montar o rodapé custa, e duas
operações com o mesmo total dão a mesma faixa por construção. A chave é o **valor**, e não um
booleano -- que era exatamente o que reduzia a coluna a uma consulta de duas entradas."""


# ------------------------------------------------------------------------------- a auditoria


def _arquivos(raiz: Path) -> list[Path]:
    return sorted(
        arquivo
        for pasta in PASTAS
        for arquivo in (raiz / "src" / "chess_diagram_ocr" / pasta).rglob("*.py")
        if "__pycache__" not in arquivo.parts
    )


def auditar(raiz: Path = TRONCO, *, medir: bool = True) -> list[Indicador]:
    """Todos os indicadores de progresso do tronco, já classificados.

    `medir=True` lê a faixa **real** do `QProgressBar` do rodapé -- ver
    `faixa_da_barra_do_rodape`. Sem binding do Qt a medição devolve vazio e a coluna
    "determ.?" volta a ser lida do código, dizendo-o na evidência.
    """
    indicadores: list[Indicador] = []
    # **A faixa é medida por operação, e não uma vez para todas** -- ver `determinado_medido`.
    # `_FAIXAS_MEDIDAS` é a memória entre chamadas dentro desta passada; limpá-la aqui é o que
    # faz duas execuções seguidas no mesmo processo medirem o rodapé **atual** e não o de antes,
    # que é justamente o que a prova de vida de `c10_faixa_tardia.py` exige para poder sabotar.
    _FAIXAS_MEDIDAS.clear()
    declaradas = _fora_do_registro(raiz)
    # Uma passada antes de tudo, porque a herança é do repositório e não do arquivo: `Tarefa`
    # nasce em `qt/trabalho.py` e é construída em cinco outros módulos.
    thread_classes = classes_de_thread(raiz)
    for arquivo in _arquivos(raiz):
        sabe_o_total = bool(_callbacks_de_progresso(arquivo))
        for registro in _registros_de(arquivo, raiz):
            passa_total = registro.total_no_registro or registro.total_por_atualizacao
            # **A coluna "determinada?" é a faixa do widget medida COM AQUELA OCUPAÇÃO**, e não a
            # leitura do argumento nem uma consulta de duas entradas (F9-C9 §4.2). Ver
            # `determinado_medido`: a faixa tem de ser determinada **e** diferir da faixa de
            # repouso indeterminado. Sem binding do Qt volta a ser o argumento, e a evidência diz
            # qual dos dois foi.
            medido, faixa, faixa_de_repouso = (
                determinado_medido(TOTAL_DE_REFERENCIA if passa_total else 0, raiz)
                if medir
                else (None, None, None)
            )
            determinado = passa_total if medido is None else medido
            evidencia_do_texto = _total_a_vista(registro.detalhe, registro.numero_no_detalhe)
            # **"O total é conhecido" é do código; "a barra é determinada" é do widget.** Ligar
            # o primeiro ao segundo foi a primeira forma desta mudança, e um teste a derrubou:
            # com o rodapé sabotado para nunca sair de `(0, 0)`, uma operação que passa
            # `total=289` ficava com `total_conhecido=False` e o portão **não acusava** -- ou
            # seja, quebrar a barra apagava o defeito de quebrar a barra. `passa_total` é prova
            # de que quem escreveu tinha o número na mão, e ela não depende do que o Qt fez com
            # ele.
            total_conhecido = (
                passa_total or determinado or bool(evidencia_do_texto) or sabe_o_total
            )
            indicadores.append(
                Indicador(
                    operacao=registro.nome,
                    arquivo=registro.arquivo,
                    linha=registro.linha,
                    especie="registro",
                    total_conhecido=total_conhecido,
                    determinado=determinado,
                    cancelavel=registro.cancelavel,
                    evidencia=_evidencia(
                        registro, evidencia_do_texto, sabe_o_total, faixa, faixa_de_repouso
                    ),
                )
            )
        indicadores.extend(_barras_de(arquivo, raiz))
        indicadores.extend(_operacoes_de_fundo(arquivo, raiz, declaradas, thread_classes))
    indicadores.sort(key=lambda item: (not item.bloqueia(), item.arquivo, item.linha))
    return indicadores


def _evidencia(
    registro: _Registro,
    do_texto: str,
    callback: bool,
    faixa: tuple[int, int] | None = None,
    faixa_de_repouso: tuple[int, int] | None = None,
) -> str:
    partes: list[str] = []
    if faixa is not None:
        determinada = "DETERMINADA" if faixa[1] > faixa[0] else "INDETERMINADA"
        # **A faixa de repouso entra na evidência, e ela é a metade que faltava** (F9-C9 §4.2):
        # sem ela o leitor não tem como saber se a barra *reagiu* à operação ou se ela já estava
        # naquele intervalo desde o `__init__` -- que é o estado que o portão lia antes.
        repouso = (
            f", repouso min={faixa_de_repouso[0]} max={faixa_de_repouso[1]}"
            if faixa_de_repouso is not None
            else ""
        )
        mudou = "" if faixa_de_repouso is None else (
            " (a barra TROCOU de modo)" if faixa != faixa_de_repouso else " (a barra NAO trocou de modo)"
        )
        partes.append(
            f"faixa medida no rodape vivo com esta ocupacao: min={faixa[0]} max={faixa[1]}"
            f"{repouso} -> {determinada}{mudou}"
        )
    else:
        partes.append("faixa NAO medida (sem binding do Qt): lida do argumento total=")
    if registro.total_no_registro:
        partes.append("total= no proprio register()")
    elif registro.total_por_atualizacao:
        partes.append(f"total= chega depois, por {registro.token}.update()")
    if do_texto:
        partes.append(do_texto)
    if callback and not registro.total_no_registro and not registro.total_por_atualizacao:
        partes.append("o modulo tem callback de progresso com parametro `total`")
    if registro.cancelavel:
        partes.append("cancellable=True com cancel= de verdade")
    else:
        partes.append("sem cancelamento")
    return "; ".join(partes) or "nada declarado"


def bloqueantes(indicadores: Iterable[Indicador]) -> list[Indicador]:
    """As linhas que a carta chama de defeito bloqueante: total conhecido, barra indeterminada."""
    return [indicador for indicador in indicadores if indicador.bloqueia()]


def _sim(valor: bool) -> str:
    return "sim" if valor else "NAO"


def tabela(indicadores: Sequence[Indicador]) -> str:
    linhas = [
        "Progresso determinado x indeterminado (SPEC 11.3: progresso real, cancelavel)",
        "",
        f"  {'operacao':<34}{'total?':>8}{'determ.?':>10}{'cancel.?':>10}  onde",
    ]
    indicadores_com_barra = [item for item in indicadores if item.especie != "fundo"]
    de_fundo = [item for item in indicadores if item.especie == "fundo"]
    for indicador in indicadores_com_barra:
        linhas.append(
            f"  {indicador.operacao[:32]:<34}{_sim(indicador.total_conhecido):>8}"
            f"{_sim(indicador.determinado):>10}{_sim(indicador.cancelavel):>10}  "
            f"{indicador.arquivo}:{indicador.linha}"
        )
    linhas.append("")
    linhas.append(f"  ({len(indicadores_com_barra)} indicadores de progresso)")
    if de_fundo:
        linhas.append("")
        linhas.append(
            f"Operacoes de fundo em qt/ ({len(de_fundo)}) -- cada thread ou se REGISTRA (o rodape "
            "a mostra)"
        )
        linhas.append(
            "ou esta DECLARADA em ui/busy.FORA_DO_REGISTRO com o motivo. As demais sao INVISIVEIS."
        )
        for indicador in sorted(de_fundo, key=lambda item: (not item.invisivel, item.arquivo)):
            estado = indicador.evidencia.split(":", 1)[0].split(" em ")[0]
            linhas.append(
                f"  {estado:<12}{indicador.operacao[:44]:<46}"
                f"{indicador.arquivo}:{indicador.linha}"
            )
    travas = bloqueantes(indicadores)
    linhas.append("")
    if travas:
        linhas.append(
            f"DEFEITOS BLOQUEANTES ({len(travas)}): total conhecido com barra indeterminada, "
            "ou operacao de fundo invisivel"
        )
        for indicador in travas:
            linhas.append(f"  - {indicador.operacao}  ({indicador.arquivo}:{indicador.linha})")
            linhas.append(f"      {indicador.evidencia}")
    else:
        linhas.append("Nenhum defeito bloqueante de progresso.")
    sem_cancelar = [
        item for item in indicadores if item.especie == "registro" and not item.cancelavel
    ]
    if sem_cancelar:
        linhas.append("")
        linhas.append(f"Operacoes longas sem cancelamento ({len(sem_cancelar)}):")
        for indicador in sem_cancelar:
            linhas.append(f"  - {indicador.operacao}  ({indicador.arquivo}:{indicador.linha})")
    return "\n".join(linhas)


def relatorio(raiz: Path = TRONCO) -> dict[str, Any]:
    indicadores = auditar(raiz)
    travas = bloqueantes(indicadores)
    return {
        "portao": (
            "SPEC 11.3 -- progresso real (nunca indeterminado com total conhecido), cancelavel"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "tronco": str(raiz),
        "metodo": {
            "leitura": "estatica (ast) sobre qt/ e ui/ do tronco",
            "criterio_determinado": (
                "ui/estado_do_rodape.ocupacao() devolve DETERMINADO sse BusyOperation.fracao "
                "nao e None, e fracao e None sse total <= 0"
            ),
            "criterio_cancelavel": "register(cancellable=True) com cancel= de verdade",
            "limite": (
                "nao ve total calculado so em tempo de execucao e nunca declarado; "
                "essas linhas aparecem com total_conhecido a partir da evidencia do detail"
            ),
        },
        "indicadores": [asdict(indicador) for indicador in indicadores],
        "bloqueantes": [asdict(indicador) for indicador in travas],
        "veredito": "REPROVOU" if travas else "PASSOU",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditoria de progresso (SPEC 11.3).")
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument(
        "--saida",
        type=Path,
        required=True,
        # **Sem padrão, e isto é um conserto de higiene** (F9-C12, item 16 do ciclo 11). O
        # padrão era `benchmarks/reports/ui/` -- a pasta do construtor --, e o crítico do
        # ciclo 11 rodou uma sabotagem sem `--saida`: o JSON foi gravar na pasta que ele não
        # pode tocar, e ele teve de movê-lo à mão. Um padrão que escreve na pasta de outro
        # agente é uma armadilha; quem roda um portão diz onde quer o relatório.
        help="onde gravar o relatorio. Obrigatorio: este portao nao escolhe pasta por voce.",
    )
    args = parser.parse_args(argv)

    dados = relatorio(args.tronco)
    args.saida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"progresso_{marca}.json"
    alvo.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")

    print(tabela([Indicador(**item) for item in dados["indicadores"]]))
    print(f"\nRelatorio: {alvo}")
    return 0 if dados["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
