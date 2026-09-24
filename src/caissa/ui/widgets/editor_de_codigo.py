"""O editor de código do Editor HTML/CSS (spec S5, D4): o protótipo do H2, que o H12 faz componente.

**Todas as funções ligadas ao mesmo tempo** é o ponto do protótipo (roadmap H2): o crítico reprovou
decidir o componente antes de medir, e uma medida com metade das funções desligadas mede outro
editor. `Contadores` diz, a cada medida, que cada função trabalhou.

**O realce não pode segurar a janela** (anti-padrão 2: nada de `rehighlight()` do documento
inteiro). O `QSyntaxHighlighter` realça o documento todo de uma vez ao receber um texto — 2 MB são
dezenas de milhares de linhas numa chamada só. Aqui o realce é próprio:

- o **estado** de cada linha (`QTextBlock.userState`, o inteiro de `caissa.editor.lexico`) é
  calculado em fatias de no máximo `FATIA_MS`, num `QTimer` de zero, da primeira linha para a
  última — o estado de uma linha depende do fim da anterior;
- as **cores** só são postas nas linhas **visíveis** (e de novo quando elas mudam, ou rolam para
  a vista): pintar 40 mil linhas que ninguém está vendo é trabalho jogado fora;
- uma **tecla** relê a linha dela, e as seguintes só enquanto o estado do fim mudar — uma letra
  num parágrafo relê uma linha; um `<!--` aberto relê até onde o tempo da tecla permite, e o resto
  vai para as fatias.

**A carga também é fatiada.** Um `setPlainText` de 2 MB é uma chamada C++ de centenas de
milissegundos na thread da janela; `carregar` acrescenta o texto em pedaços de `PEDACO_DA_CARGA`,
um por volta do laço de eventos, com o desfazer desligado durante a carga.

**A prévia vai a outro processo** (o PyMuPDF segura o GIL): `pedir_previa` sai `ATRASO_DA_PREVIA_MS`
depois da última tecla, e quem liga o sinal manda o texto ao processo de trabalho
(`PreviaNoProcesso`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from PyQt6.QtCore import QMimeData, QObject, QRect, QSize, QStringListModel, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextLayout,
    QTextOption,
)
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from caissa.editor import lexico
from caissa.editor.lexico import Classe, Ficha

FUNCOES: frozenset[str] = frozenset({
    "realce", "margem", "dobras", "indicadores", "completar", "par_de_tags", "fechar_tag",
    "desfazer", "escala", "previa", "trilha", "busca", "invisiveis", "colar_simples",
})

#: Quanto uma fatia do realce (ou da carga, ou das dobras) pode segurar a janela.
FATIA_MS = 8.0
#: Quanto a própria tecla pode gastar relendo as linhas seguintes antes de deixar para as fatias.
TECLA_MS = 4.0
PEDACO_DA_CARGA = 24 * 1024
ATRASO_DA_PREVIA_MS = 300
#: O par de tags e a trilha de pão esperam o cursor parar este tanto.
PAUSA_DO_CURSOR_MS = 80
#: Até onde procurar o par de uma tag, ou o elemento aberto, em linhas.
ALCANCE_DO_PAR = 2000

#: Cores do protótipo, por papel. O H12 as troca pelos papéis de token do tronco (`CODIGO_*`),
#: com o portão de contraste nos pixels; todas aqui passam de 7:1 sobre o branco.
CORES_DO_PROTOTIPO: dict[Classe, str] = {
    Classe.DELIMITADOR: "#444444",
    Classe.TAG: "#0b4f8a",
    Classe.ATRIBUTO: "#7a2e00",
    Classe.VALOR: "#0a5c2b",
    Classe.ENTIDADE: "#6b1d8f",
    Classe.COMENTARIO: "#595959",
    Classe.CDATA: "#595959",
    Classe.DECLARACAO: "#595959",
    Classe.CSS_SELETOR: "#0b4f8a",
    Classe.CSS_PROPRIEDADE: "#7a2e00",
    Classe.CSS_VALOR: "#0a5c2b",
    Classe.CSS_ARROBA: "#6b1d8f",
    Classe.CSS_CHAVE: "#444444",
}
COR_DO_PROBLEMA = "#b00020"
COR_DA_DUVIDA = "#8a5a00"
COR_DA_LINHA_ATUAL = "#eef3fb"
COR_DO_PAR = "#d7e6f7"

#: Elementos que não têm fecho: não abrem região, não entram na pilha.
VAZIOS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                    "source", "track", "wbr"})

TAGS_DO_CONTRATO = (
    "a", "abbr", "blockquote", "body", "br", "caption", "div", "em", "figcaption", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6", "head", "hr", "html", "img", "li", "link", "meta", "nav",
    "ol", "p", "section", "small", "span", "strong", "style", "sub", "sup", "table", "tbody",
    "td", "th", "thead", "title", "tr", "u", "ul",
)
ATRIBUTOS_DO_CONTRATO = (
    "alt", "aria-label", "class", "data-fen", "data-mode", "data-nag", "data-orientation",
    "data-piece", "data-stm", "data-uci", "epub:type", "href", "id", "lang", "role", "src",
    "style", "title", "xml:lang",
)
PROPRIEDADES_CSS = (
    "background-color", "break-before", "color", "font-family", "font-size", "font-style",
    "font-variant", "font-weight", "letter-spacing", "line-height", "margin", "margin-bottom",
    "margin-left", "margin-right", "margin-top", "orphans", "page-break-before", "text-align",
    "text-indent", "text-transform", "widows",
)


@dataclass
class Contadores:
    """A prova de atividade (roadmap H2): uma medida com um contador zerado é inválida."""

    blocos_lexados: int = 0
    blocos_formatados: int = 0
    fatias: int = 0
    maior_fatia_ms: float = 0.0
    selecoes_extras: int = 0
    dobras_recolhidas: int = 0
    completar_aberto: int = 0
    tags_fechadas: int = 0
    pares_realcados: int = 0
    pedidos_de_previa: int = 0
    previas_recebidas: int = 0
    escala_aplicada: float = 1.0
    buscas: int = 0
    colados_simples: int = 0
    trilhas: int = 0

    def como_dict(self) -> dict[str, float]:
        return dict(vars(self))


class _Formatado(QTextBlockUserData):
    """Com que estado de entrada, e em que revisão do bloco, as cores dele foram postas."""

    def __init__(self, estado_de_entrada: int, revisao: int) -> None:
        super().__init__()
        self.estado_de_entrada = estado_de_entrada
        self.revisao = revisao


def formatos_das_classes(cores: dict[Classe, str] | None = None) -> dict[Classe, QTextCharFormat]:
    saida = {}
    for classe, cor in (cores or CORES_DO_PROTOTIPO).items():
        formato = QTextCharFormat()
        formato.setForeground(QColor(cor))
        if classe in (Classe.COMENTARIO, Classe.CDATA):
            formato.setFontItalic(True)
        saida[classe] = formato
    return saida


# --------------------------------------------------------------------------- #
# O realce incremental
# --------------------------------------------------------------------------- #


class RealceIncremental(QObject):
    """O estado de cada linha em fatias, e as cores só nas linhas à vista (ver o cabeçalho)."""

    confirmado = pyqtSignal()           # o estado de todas as linhas está calculado

    def __init__(self, editor: EditorDeCodigo, tipo: str) -> None:
        super().__init__(editor)
        self.editor = editor
        self.documento = editor.document()
        self.estado_inicial = lexico.estado_inicial(tipo)
        self.formatos = formatos_das_classes()
        self.contadores = editor.contadores
        self.sincrono = False           # a sabotagem `realce_sincrono`: tudo de uma vez
        #: As linhas [0, confirmado_ate) têm o estado do fim calculado com a entrada certa.
        self.confirmado_ate = 0
        self._blocos = self.documento.blockCount()
        self._aplicando = False
        self._fatias = QTimer(self)
        self._fatias.setInterval(0)
        self._fatias.timeout.connect(self._fatia)
        self._visiveis = QTimer(self)
        self._visiveis.setSingleShot(True)
        self._visiveis.setInterval(0)
        self._visiveis.timeout.connect(self.formatar_visiveis)
        self.documento.contentsChange.connect(self._mudou)
        editor.updateRequest.connect(lambda *_: self._visiveis.start())

    # ---------------------------------------------------------------- o estado das linhas

    def _entrada(self, bloco: QTextBlock) -> int:
        anterior = bloco.previous()
        if not anterior.isValid():
            return self.estado_inicial
        estado = anterior.userState()
        return estado if estado >= 0 else self.estado_inicial

    def _lexar(self, bloco: QTextBlock) -> tuple[list[Ficha], int]:
        fichas, fim = lexico.tokens(bloco.text(), self._entrada(bloco))
        self.contadores.blocos_lexados += 1
        return fichas, fim

    def _mudou(self, posicao: int, _removidos: int, acrescentados: int) -> None:
        if self._aplicando:
            return
        blocos = self.documento.blockCount()
        delta, self._blocos = blocos - self._blocos, blocos
        primeiro = self.documento.findBlock(posicao)
        ultimo = self.documento.findBlock(posicao + acrescentados)
        numero = primeiro.blockNumber()
        if numero < self.confirmado_ate:
            self.confirmado_ate = max(numero, self.confirmado_ate + delta)
        if self.sincrono:
            self.confirmado_ate = min(self.confirmado_ate, numero)
            self._ate_o_fim()
            return
        # A entrada da primeira linha mudada só é certa se a anterior está confirmada; além da
        # fronteira a linha é lida com entrada provisória, e a fronteira não anda por ela.
        confiavel = numero <= self.confirmado_ate
        limite = time.perf_counter() + TECLA_MS / 1000.0
        bloco = primeiro
        fim_do_trecho = ultimo.blockNumber()
        while bloco.isValid():
            _, fim = self._lexar(bloco)
            antigo = bloco.userState()
            bloco.setUserState(fim)
            atual = bloco.blockNumber()
            if atual >= fim_do_trecho and fim == antigo and atual < self.confirmado_ate:
                break                                    # o resto já estava certo
            if time.perf_counter() > limite:
                if confiavel:
                    self.confirmado_ate = atual + 1      # daqui em diante, as fatias
                break
            bloco = bloco.next()
        else:
            if confiavel:
                self.confirmado_ate = self.documento.blockCount()
        if not self.completo:
            self._fatias.start()
        self._visiveis.start()

    def _fatia(self) -> None:
        inicio = time.perf_counter()
        limite = inicio + FATIA_MS / 1000.0
        bloco = self.documento.findBlockByNumber(self.confirmado_ate)
        while bloco.isValid() and time.perf_counter() < limite:
            _, fim = self._lexar(bloco)
            bloco.setUserState(fim)
            bloco = bloco.next()
            self.confirmado_ate += 1
        duracao = (time.perf_counter() - inicio) * 1000.0
        self.contadores.fatias += 1
        self.contadores.maior_fatia_ms = max(self.contadores.maior_fatia_ms, duracao)
        if not bloco.isValid():
            self.confirmado_ate = self.documento.blockCount()
            self._fatias.stop()
            self.confirmado.emit()
        self._visiveis.start()

    def _ate_o_fim(self) -> None:
        """A sabotagem: o documento inteiro de uma vez, como o `rehighlight()`."""
        bloco = self.documento.findBlockByNumber(self.confirmado_ate)
        while bloco.isValid():
            fichas, fim = self._lexar(bloco)
            bloco.setUserState(fim)
            self._pintar(bloco, fichas, self._entrada(bloco))
            bloco = bloco.next()
        self.confirmado_ate = self.documento.blockCount()
        self.confirmado.emit()

    @property
    def completo(self) -> bool:
        return self.confirmado_ate >= self.documento.blockCount()

    # ---------------------------------------------------------------- as cores à vista

    def blocos_visiveis(self) -> Iterator[QTextBlock]:
        editor = self.editor
        bloco = editor.firstVisibleBlock()
        topo = editor.blockBoundingGeometry(bloco).translated(editor.contentOffset()).top()
        altura = editor.viewport().height()
        while bloco.isValid() and topo <= altura:
            if bloco.isVisible():
                yield bloco
            topo += editor.blockBoundingRect(bloco).height()
            bloco = bloco.next()

    def formatar_visiveis(self) -> None:
        for bloco in list(self.blocos_visiveis()):
            entrada = self._entrada(bloco)
            dados = bloco.userData()
            if (isinstance(dados, _Formatado) and dados.revisao == bloco.revision()
                    and dados.estado_de_entrada == entrada):
                continue
            fichas, _ = lexico.tokens(bloco.text(), entrada)
            self._pintar(bloco, fichas, entrada)

    def _pintar(self, bloco: QTextBlock, fichas: list[Ficha], entrada: int) -> None:
        faixas = []
        for ficha in fichas:
            faixa = QTextLayout.FormatRange()
            faixa.start, faixa.length = ficha.inicio, ficha.tamanho
            faixa.format = self.formatos[ficha.classe]
            faixas.append(faixa)
        self._aplicando = True
        try:
            bloco.layout().setFormats(faixas)
            bloco.setUserData(_Formatado(entrada, bloco.revision()))
            self.documento.markContentsDirty(bloco.position(), bloco.length())
        finally:
            self._aplicando = False
        self.contadores.blocos_formatados += 1

    def visivel_realcado(self) -> bool:
        """Toda linha à vista tem cor, com a entrada confirmada (o portão «visível ≤ 50 ms»)."""
        ultimo = -1
        for bloco in self.blocos_visiveis():
            dados = bloco.userData()
            if not (isinstance(dados, _Formatado) and dados.revisao == bloco.revision()
                    and dados.estado_de_entrada == self._entrada(bloco)):
                return False
            ultimo = bloco.blockNumber()
        return ultimo < self.confirmado_ate


# --------------------------------------------------------------------------- #
# A margem
# --------------------------------------------------------------------------- #


class Margem(QWidget):
    """Os números das linhas, os marcadores (problema, dúvida, diagrama, página) e as dobras."""

    MARCADORES: ClassVar[dict[str, str]] = {
        "problema": COR_DO_PROBLEMA, "duvida": COR_DA_DUVIDA, "diagrama": "#0b4f8a",
        "pagina": "#444444"}

    def __init__(self, editor: EditorDeCodigo) -> None:
        super().__init__(editor)
        self.editor = editor
        self.marcadores: dict[int, set[str]] = {}
        self.linhas_pintadas: list[int] = []
        self.setAccessibleName("Margem: números das linhas e marcadores")

    def largura(self) -> int:
        digitos = len(str(max(1, self.editor.blockCount())))
        return 18 + self.editor.fontMetrics().horizontalAdvance("9") * digitos + 14

    def sizeHint(self) -> QSize:  # noqa: N802 - assinatura do Qt
        return QSize(self.largura(), 0)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802 - assinatura do Qt
        pintor = QPainter(self)
        pintor.fillRect(evento.rect(), QColor("#f4f4f4"))
        editor = self.editor
        bloco = editor.firstVisibleBlock()
        topo = round(editor.blockBoundingGeometry(bloco).translated(editor.contentOffset()).top())
        altura_da_linha = editor.fontMetrics().height()
        pintadas = []
        while bloco.isValid() and topo <= evento.rect().bottom():
            altura = round(editor.blockBoundingRect(bloco).height())
            if bloco.isVisible() and topo + altura >= evento.rect().top():
                numero = bloco.blockNumber()
                pintadas.append(numero + 1)
                pintor.setPen(QColor("#555555"))
                pintor.drawText(0, topo, self.width() - 16, altura_da_linha,
                                int(Qt.AlignmentFlag.AlignRight), str(numero + 1))
                for indice, tipo in enumerate(sorted(self.marcadores.get(numero, ()))):
                    pintor.fillRect(2 + 4 * indice, topo + 3, 3, altura_da_linha - 6,
                                    QColor(self.MARCADORES.get(tipo, "#444444")))
                if editor.dobras is not None and editor.dobras.dobravel(numero):
                    simbolo = "▸" if numero in editor.dobras.recolhidas else "▾"
                    pintor.drawText(self.width() - 14, topo, 12, altura_da_linha,
                                    int(Qt.AlignmentFlag.AlignCenter), simbolo)
            topo += altura
            bloco = bloco.next()
        self.linhas_pintadas = pintadas
        pintor.end()


# --------------------------------------------------------------------------- #
# A estrutura: tags abertas, pares, regiões de dobra
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tag:
    nome: str
    linha: int
    inicio: int          # posição do «<» no bloco
    fim: int             # posição depois do nome
    fecho: bool
    vazia: bool = False  # «/>» ou elemento vazio


def tags_da_linha(texto: str, entrada: int) -> tuple[list[Tag], int]:
    """As tags de uma linha (com o fecho `/>` resolvido), e o estado do fim."""
    fichas, fim = lexico.tokens(texto, entrada)
    tags: list[Tag] = []
    for indice, ficha in enumerate(fichas):
        if ficha.classe is not Classe.TAG or indice == 0:
            continue
        delimitador = fichas[indice - 1]
        if delimitador.classe is not Classe.DELIMITADOR:
            continue
        fecho = texto[delimitador.inicio:delimitador.fim] == "</"
        nome = texto[ficha.inicio:ficha.fim]
        vazia = nome.lower() in VAZIOS
        for seguinte in fichas[indice + 1:]:
            if seguinte.classe is Classe.DELIMITADOR and texto[seguinte.inicio:seguinte.fim] in (
                    ">", "/>"):
                vazia = vazia or texto[seguinte.inicio:seguinte.fim] == "/>"
                break
            if seguinte.classe is Classe.TAG:
                break
        tags.append(Tag(nome, -1, delimitador.inicio, ficha.fim, fecho, vazia))
    return tags, fim


#: Quanto a busca de um par, ou da trilha, pode gastar numa volta do laço de eventos.
BUSCA_MS = 6.0


class Estrutura:
    """As tags do documento, lidas sob demanda por bloco, com o estado do realce.

    Toda busca tem orçamento (`BUSCA_MS`) além do alcance em linhas: numa linha que abre um
    elemento cujo fecho está a mil linhas, o par não é achado nesta volta — e a janela não pára.
    """

    def __init__(self, editor: EditorDeCodigo) -> None:
        self.editor = editor
        self.esgotou = False            # a última busca parou pelo orçamento

    def tags(self, bloco: QTextBlock) -> list[Tag]:
        anterior = bloco.previous()
        entrada = (anterior.userState() if anterior.isValid() and anterior.userState() >= 0
                   else self.editor.realce.estado_inicial if self.editor.realce else 0)
        encontradas, _ = tags_da_linha(bloco.text(), entrada)
        return [Tag(t.nome, bloco.blockNumber(), t.inicio, t.fim, t.fecho, t.vazia)
                for t in encontradas]

    def abertas_ate(self, bloco: QTextBlock, coluna: int, *, so_a_mais_interna: bool = False,
                    orcamento_ms: float = BUSCA_MS) -> list[Tag]:
        """Os elementos abertos antes de (bloco, coluna), do mais externo ao mais interno."""
        pilha_invertida: list[Tag] = []
        pendentes: dict[str, int] = {}
        atual = bloco
        passos = 0
        primeiro = True
        limite = time.perf_counter() + orcamento_ms / 1000.0
        self.esgotou = False
        while atual.isValid() and passos < ALCANCE_DO_PAR:
            if time.perf_counter() > limite:
                self.esgotou = True
                break
            tags = self.tags(atual)
            if primeiro:
                tags = [t for t in tags if t.inicio < coluna]
                primeiro = False
            for tag in reversed(tags):
                nome = tag.nome.lower()
                if tag.vazia:
                    continue
                if tag.fecho:
                    pendentes[nome] = pendentes.get(nome, 0) + 1
                elif pendentes.get(nome):
                    pendentes[nome] -= 1
                else:
                    pilha_invertida.append(tag)
                    if so_a_mais_interna:
                        return pilha_invertida
            atual = atual.previous()
            passos += 1
        return list(reversed(pilha_invertida))

    def par_de(  # noqa: PLR0911, PLR0912 - a busca para cada lado, com orçamento, lê melhor inteira
            self, bloco: QTextBlock, coluna: int, *,
               orcamento_ms: float = BUSCA_MS) -> tuple[Tag, Tag] | None:
        """A tag sob o cursor e a que faz par com ela, ou `None`."""
        alvo = next((t for t in self.tags(bloco) if t.inicio <= coluna <= t.fim), None)
        if alvo is None or alvo.vazia:
            return None
        nome = alvo.nome.lower()
        profundidade = 0
        passos = 0
        limite = time.perf_counter() + orcamento_ms / 1000.0
        self.esgotou = False
        if alvo.fecho:
            atual = bloco
            while atual.isValid() and passos < ALCANCE_DO_PAR:
                if time.perf_counter() > limite:
                    self.esgotou = True
                    return None
                tags = self.tags(atual)
                if atual == bloco:
                    tags = [t for t in tags if t.inicio < alvo.inicio]
                for tag in reversed(tags):
                    if tag.nome.lower() != nome or tag.vazia:
                        continue
                    if tag.fecho:
                        profundidade += 1
                    elif profundidade == 0:
                        return tag, alvo
                    else:
                        profundidade -= 1
                atual = atual.previous()
                passos += 1
            return None
        atual = bloco
        while atual.isValid() and passos < ALCANCE_DO_PAR:
            if time.perf_counter() > limite:
                self.esgotou = True
                return None
            tags = self.tags(atual)
            if atual == bloco:
                tags = [t for t in tags if t.inicio > alvo.inicio]
            for tag in tags:
                if tag.nome.lower() != nome or tag.vazia:
                    continue
                if not tag.fecho:
                    profundidade += 1
                elif profundidade == 0:
                    return alvo, tag
                else:
                    profundidade -= 1
            atual = atual.next()
            passos += 1
        return None


class Dobras:
    """Regiões de dobra: um elemento aberto numa linha e fechado numa linha mais abaixo.

    **O mapa das regiões é feito em fatias** (`mapear`), depois da carga e `ATRASO_DO_MAPA_MS`
    depois da última edição — a margem pinta a seta de cada linha à vista a cada rolagem, e
    perguntar o par de cada uma ali seria varrer o arquivo a cada quadro. A margem só consulta o
    mapa.
    """

    ATRASO_DO_MAPA_MS = 500

    def __init__(self, editor: EditorDeCodigo) -> None:
        self.editor = editor
        self.recolhidas: dict[int, int] = {}
        #: linha de abertura → (linha de fecho, nível: 0 = raiz, o elemento pai).
        self.regioes: dict[int, tuple[int, int, str]] = {}
        self._novas: dict[int, tuple[int, int, str]] = {}
        self._pilha: list[Tag] = []
        self._linha = 0
        self._dobrar_depois = False
        self._fila: list[int] = []
        self._mapear = QTimer(editor)
        self._mapear.setInterval(0)
        self._mapear.timeout.connect(self._fatia_do_mapa)
        self._desdobrar = QTimer(editor)
        self._desdobrar.setInterval(0)
        self._desdobrar.timeout.connect(self._fatia_de_desdobrar)
        self._atraso = QTimer(editor)
        self._atraso.setSingleShot(True)
        self._atraso.setInterval(self.ATRASO_DO_MAPA_MS)
        self._atraso.timeout.connect(self.mapear)
        self._blocos = editor.document().blockCount()
        editor.document().contentsChange.connect(self._mudou)

    def _mudou(self, posicao: int, _removidos: int, _acrescentados: int) -> None:
        documento = self.editor.document()
        delta = documento.blockCount() - self._blocos
        self._blocos = documento.blockCount()
        if delta:
            linha = documento.findBlock(posicao).blockNumber()
            self.recolhidas = {(a + delta if a > linha else a): (b + delta if b > linha else b)
                               for a, b in self.recolhidas.items()}
        if not self.editor.carregando:
            self._atraso.start()

    def mapear(self) -> None:
        self._novas, self._pilha, self._linha = {}, [], 0
        self._mapear.start()

    @property
    def ocupado(self) -> bool:
        return self._mapear.isActive() or self._desdobrar.isActive()

    def _fatia_do_mapa(self) -> None:
        limite = time.perf_counter() + FATIA_MS / 1000.0
        bloco = self.editor.document().findBlockByNumber(self._linha)
        while bloco.isValid() and time.perf_counter() < limite:
            for tag in self.editor.estrutura.tags(bloco):
                if tag.vazia:
                    continue
                if not tag.fecho:
                    self._pilha.append(tag)
                    continue
                profundidade = next((i for i in range(len(self._pilha) - 1, -1, -1)
                                     if self._pilha[i].nome.lower() == tag.nome.lower()), None)
                if profundidade is None:
                    continue                   # fecho sem abertura: arquivo mal formado
                aberta = self._pilha[profundidade]
                pai = self._pilha[profundidade - 1].nome.lower() if profundidade else ""
                del self._pilha[profundidade:]
                if aberta.linha < tag.linha:
                    self._novas[aberta.linha] = (tag.linha, profundidade, pai)
            bloco = bloco.next()
            self._linha += 1
        if bloco.isValid():
            return
        self._mapear.stop()
        self.regioes = self._novas
        self.editor.margem.update()
        if self._dobrar_depois:
            self._dobrar_depois = False
            self._fila = sorted(a for a, (_, _, pai) in self.regioes.items() if pai == "body")
            self._desdobrar.start()

    def regiao(self, linha: int) -> int | None:
        dado = self.regioes.get(linha)
        return dado[0] if dado else None

    def dobravel(self, linha: int) -> bool:
        return linha in self.recolhidas or linha in self.regioes

    def dobrar(self, linha: int, fim: int | None = None) -> bool:
        fim = fim if fim is not None else self.regiao(linha)
        if fim is None or linha in self.recolhidas:
            return False
        self._visibilidade(linha + 1, fim, visivel=False)
        self.recolhidas[linha] = fim
        self.editor.contadores.dobras_recolhidas += 1
        return True

    def desdobrar(self, linha: int) -> bool:
        fim = self.recolhidas.pop(linha, None)
        if fim is None:
            return False
        self._visibilidade(linha + 1, fim, visivel=True)
        return True

    def _visibilidade(self, primeira: int, ultima: int, *, visivel: bool) -> None:
        if ultima < primeira:
            return
        documento = self.editor.document()
        bloco = documento.findBlockByNumber(primeira)
        inicio = fim = bloco.position()
        while bloco.isValid() and bloco.blockNumber() <= ultima:
            dentro_de_outra = visivel and any(
                a < bloco.blockNumber() <= b for a, b in self.recolhidas.items())
            if not dentro_de_outra:
                bloco.setVisible(visivel)
            fim = bloco.position() + bloco.length()
            bloco = bloco.next()
        documento.markContentsDirty(inicio, max(0, fim - inicio))
        self.editor.viewport().update()
        self.editor.margem.update()

    # -- dobrar e desdobrar tudo, em fatias -------------------------------------------

    def dobrar_tudo(self) -> None:
        """Recolhe as regiões filhas do `<body>` (o primeiro nível do livro), em fatias."""
        self._desdobrando = False
        self._dobrar_depois = True
        self.mapear()

    def desdobrar_tudo(self) -> None:
        self._desdobrando = True
        self._fila = sorted(self.recolhidas)
        self._desdobrar.start()

    def _fatia_de_desdobrar(self) -> None:
        limite = time.perf_counter() + FATIA_MS / 1000.0
        while self._fila and time.perf_counter() < limite:
            linha = self._fila.pop()
            if self._desdobrando:
                self.desdobrar(linha)
            else:
                self.dobrar(linha)
        if not self._fila:
            self._desdobrar.stop()


# --------------------------------------------------------------------------- #
# O editor
# --------------------------------------------------------------------------- #


class EditorDeCodigo(QPlainTextEdit):
    """O editor de XHTML e CSS do projeto; ver o cabeçalho do módulo."""

    pedir_previa = pyqtSignal(str)
    trilha_mudou = pyqtSignal(list)
    carregado = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, *, tipo: str = "xhtml",
                 funcoes: Iterable[str] = FUNCOES, classes_do_projeto: Iterable[str] = (),
                 tamanho_da_fonte: float = 10.0) -> None:
        super().__init__(parent)
        self.funcoes = frozenset(funcoes)
        self.tipo = tipo
        self.contadores = Contadores()
        self.setAccessibleName("Código do arquivo")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        fonte = QFont("Consolas")
        fonte.setStyleHint(QFont.StyleHint.Monospace)
        fonte.setPointSizeF(tamanho_da_fonte)
        self._tamanho_base = tamanho_da_fonte
        self.setFont(fonte)
        self.classes_do_projeto = sorted(set(classes_do_projeto))

        self.realce: RealceIncremental | None = (
            RealceIncremental(self, tipo) if "realce" in self.funcoes else None)
        self.estrutura = Estrutura(self)
        self.dobras: Dobras | None = Dobras(self) if "dobras" in self.funcoes else None
        self.margem = Margem(self)
        self.margem.setVisible("margem" in self.funcoes)
        self._indicadores: list[QTextEdit.ExtraSelection] = []
        self._selecoes_do_cursor: list[QTextEdit.ExtraSelection] = []

        self.blockCountChanged.connect(self._ajustar_margem)
        self.updateRequest.connect(self._rolar_margem)
        self._depois_do_cursor = QTimer(self)
        self._depois_do_cursor.setSingleShot(True)
        self._depois_do_cursor.setInterval(PAUSA_DO_CURSOR_MS)
        self._depois_do_cursor.timeout.connect(self._cursor_parou)
        self.cursorPositionChanged.connect(self._cursor_andou)
        self._ajustar_margem()

        self._completar: QCompleter | None = None
        if "completar" in self.funcoes:
            self._completar = QCompleter(QStringListModel([], self), self)
            self._completar.setWidget(self)
            self._completar.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self._completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completar.activated[str].connect(self._inserir_completacao)

        self._previa = QTimer(self)
        self._previa.setSingleShot(True)
        self._previa.setInterval(ATRASO_DA_PREVIA_MS)
        self._previa.timeout.connect(self._emitir_previa)
        self.textChanged.connect(self._mudou_o_texto)
        self._carga: list[str] = []
        self._carregando = QTimer(self)
        self._carregando.setInterval(0)
        self._carregando.timeout.connect(self._pedaco_da_carga)
        if "invisiveis" in self.funcoes:
            self.mostrar_invisiveis(True)

    # ---------------------------------------------------------------- carga

    def carregar(self, texto: str) -> None:
        """Troca o texto em pedaços, um por volta do laço, com o desfazer desligado na carga."""
        self._carregando.stop()
        self.document().setUndoRedoEnabled(False)
        self.clear()
        pedacos, inicio = [], 0
        while inicio < len(texto):
            fim = texto.find("\n", inicio + PEDACO_DA_CARGA)
            fim = len(texto) if fim < 0 else fim + 1
            pedacos.append(texto[inicio:fim])
            inicio = fim
        self._carga = list(reversed(pedacos))
        if self._carga:
            self._pedaco_da_carga()
            self._carregando.start()
        else:
            self._fim_da_carga()

    def _pedaco_da_carga(self) -> None:
        if not self._carga:
            self._fim_da_carga()
            return
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(self._carga.pop())
        if not self._carga:
            self._fim_da_carga()

    def _fim_da_carga(self) -> None:
        self._carregando.stop()
        self.document().setUndoRedoEnabled("desfazer" in self.funcoes)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        if self.dobras is not None:
            self.dobras.mapear()
        self.carregado.emit()

    @property
    def carregando(self) -> bool:
        return self._carregando.isActive()

    # ---------------------------------------------------------------- margem

    def _ajustar_margem(self, *_: Any) -> None:
        largura = self.margem.largura() if self.margem.isVisible() else 0
        self.setViewportMargins(largura, 0, 0, 0)

    def _rolar_margem(self, retangulo: QRect, dy: int) -> None:
        if not self.margem.isVisible():
            return
        if dy:
            self.margem.scroll(0, dy)
        else:
            self.margem.update(0, retangulo.y(), self.margem.width(), retangulo.height())

    def resizeEvent(self, evento: QResizeEvent) -> None:  # noqa: N802 - assinatura do Qt
        super().resizeEvent(evento)
        area = self.contentsRect()
        self.margem.setGeometry(QRect(area.left(), area.top(), self.margem.largura(),
                                      area.height()))

    def marcar(self, linha: int, tipo: str) -> None:
        self.margem.marcadores.setdefault(linha, set()).add(tipo)
        self.margem.update()

    # ---------------------------------------------------------------- indicadores

    def definir_indicadores(self, intervalos: Iterable[tuple[int, int, str]]) -> None:
        """Sublinhados: `problema` em onda, `duvida` pontilhado, com a cor do papel."""
        selecoes = []
        for inicio, fim, tipo in intervalos:
            selecao = QTextEdit.ExtraSelection()
            cursor = QTextCursor(self.document())
            cursor.setPosition(inicio)
            cursor.setPosition(fim, QTextCursor.MoveMode.KeepAnchor)
            selecao.cursor = cursor
            formato = QTextCharFormat()
            if tipo == "problema":
                formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                formato.setUnderlineColor(QColor(COR_DO_PROBLEMA))
            else:
                formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
                formato.setUnderlineColor(QColor(COR_DA_DUVIDA))
            selecao.format = formato
            selecoes.append(selecao)
        self._indicadores = selecoes if "indicadores" in self.funcoes else []
        self._aplicar_selecoes()

    def indicadores(self) -> list[QTextEdit.ExtraSelection]:
        return list(self._indicadores)

    def _aplicar_selecoes(self) -> None:
        selecoes = [*self._indicadores, *self._selecoes_do_cursor]
        self.setExtraSelections(selecoes)
        self.contadores.selecoes_extras = len(selecoes)

    # ---------------------------------------------------------------- cursor: linha, par, trilha

    def _cursor_andou(self) -> None:
        linha = QTextEdit.ExtraSelection()
        linha.format.setBackground(QColor(COR_DA_LINHA_ATUAL))
        linha.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        linha.cursor = self.textCursor()
        linha.cursor.clearSelection()
        self._selecoes_do_cursor = [linha]
        self._aplicar_selecoes()
        # O par e a trilha leem outras linhas: esperam a pausa do cursor, e têm orçamento.
        self._depois_do_cursor.start()

    def _cursor_parou(self) -> None:
        selecoes = self._selecoes_do_cursor[:1]
        if "par_de_tags" in self.funcoes:
            cursor = self.textCursor()
            par = self.estrutura.par_de(cursor.block(), cursor.positionInBlock())
            if par is not None:
                for tag in par:
                    bloco = self.document().findBlockByNumber(tag.linha)
                    marca = QTextEdit.ExtraSelection()
                    marca.format.setBackground(QColor(COR_DO_PAR))
                    marca.cursor = QTextCursor(self.document())
                    marca.cursor.setPosition(bloco.position() + tag.inicio)
                    marca.cursor.setPosition(bloco.position() + tag.fim,
                                             QTextCursor.MoveMode.KeepAnchor)
                    selecoes.append(marca)
                self.contadores.pares_realcados += 1
        self._selecoes_do_cursor = selecoes
        self._aplicar_selecoes()
        if "trilha" in self.funcoes:
            self.trilha_mudou.emit(self.trilha())

    def trilha(self) -> list[str]:
        """Os elementos abertos no cursor; «…» na frente quando o orçamento parou a busca."""
        cursor = self.textCursor()
        self.contadores.trilhas += 1
        nomes = [t.nome for t in self.estrutura.abertas_ate(cursor.block(),
                                                             cursor.positionInBlock())]
        return ["…", *nomes] if self.estrutura.esgotou else nomes

    def par_sob_o_cursor(self) -> tuple[Tag, Tag] | None:
        cursor = self.textCursor()
        return self.estrutura.par_de(cursor.block(), cursor.positionInBlock())

    # ---------------------------------------------------------------- teclas: completar e fechar

    def keyPressEvent(self, evento: QKeyEvent) -> None:  # noqa: N802 - assinatura do Qt
        popup = self._completar.popup() if self._completar else None
        if popup is not None and popup.isVisible() and evento.key() in (
                Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab):
            evento.ignore()                 # a lista de completar fica com a tecla
            return
        super().keyPressEvent(evento)
        texto = evento.text()
        if not texto:
            return
        if texto == "/" and "fechar_tag" in self.funcoes and self._antes_do_cursor(2) == "</":
            self._fechar_tag()
        elif self._completar is not None:
            self._talvez_completar(texto)

    def _antes_do_cursor(self, quantos: int) -> str:
        cursor = self.textCursor()
        bloco = cursor.block().text()
        coluna = cursor.positionInBlock()
        return bloco[max(0, coluna - quantos):coluna]

    def _fechar_tag(self) -> None:
        cursor = self.textCursor()
        abertas = self.estrutura.abertas_ate(cursor.block(), cursor.positionInBlock() - 2,
                                             so_a_mais_interna=True)
        if not abertas:
            return
        # Um passo de desfazer próprio: o Ctrl+Z logo depois tira o fecho automático, e não a
        # tecla que a pessoa digitou junto com ele.
        cursor.beginEditBlock()
        cursor.insertText(abertas[-1].nome + ">")
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.contadores.tags_fechadas += 1

    def _talvez_completar(  # noqa: PLR0912 - um ramo por contexto da sugestão
            self, texto: str) -> None:
        if self._completar is None:
            return
        cursor = self.textCursor()
        bloco = cursor.block()
        anterior = bloco.previous()
        entrada = (anterior.userState() if anterior.isValid() and anterior.userState() >= 0
                   else lexico.estado_inicial(self.tipo))
        _, estado = lexico.tokens(bloco.text()[:cursor.positionInBlock()], entrada)
        antes = self._antes_do_cursor(60)
        palavras: tuple[str, ...] | list[str] = ()
        prefixo = ""
        modo = lexico.modo(estado)
        if texto == "<" and modo is lexico.Modo.TEXTO:
            palavras, prefixo = TAGS_DO_CONTRATO, ""
        elif modo is lexico.Modo.TAG and texto.isspace():
            palavras, prefixo = ATRIBUTOS_DO_CONTRATO, ""
        elif modo is lexico.Modo.ASPAS_DUPLAS and antes.endswith('class="'):
            palavras, prefixo = self.classes_do_projeto, ""
        elif modo is lexico.Modo.CSS and estado & lexico.EM_BLOCO and (
                texto.isalpha() or texto == "-"):
            inicio = len(antes) - len(antes.lstrip())
            palavra = antes.split()[-1] if antes.split() else ""
            if palavra and not palavra.endswith(":") and inicio >= 0:
                palavras, prefixo = PROPRIEDADES_CSS, palavra
        elif self._completar.popup().isVisible():
            palavra = ""
            for caractere in reversed(antes):
                if not (caractere.isalnum() or caractere in "-:_"):
                    break
                palavra = caractere + palavra
            self._completar.setCompletionPrefix(palavra)
            if self._completar.completionCount() == 0:
                self._completar.popup().hide()
            else:
                self._escolher_o_primeiro()
            return
        if not palavras:
            return
        modelo = self._completar.model()
        if not isinstance(modelo, QStringListModel):
            return
        modelo.setStringList(list(palavras))
        self._completar.setCompletionPrefix(prefixo)
        retangulo = self.cursorRect()
        retangulo.setWidth(220)
        self._completar.complete(retangulo)
        self._escolher_o_primeiro()
        self.contadores.completar_aberto += 1

    def _escolher_o_primeiro(self) -> None:
        """A lista abre com a primeira sugestão escolhida: o Enter a aceita (o exemplo do Qt)."""
        if self._completar is None:
            return
        modelo = self._completar.completionModel()
        self._completar.popup().setCurrentIndex(modelo.index(0, 0))

    def _inserir_completacao(self, palavra: str) -> None:
        if self._completar is None:
            return
        cursor = self.textCursor()
        prefixo = self._completar.completionPrefix()
        cursor.insertText(palavra[len(prefixo):])
        self.setTextCursor(cursor)

    def completar_visivel(self) -> bool:
        return bool(self._completar and self._completar.popup().isVisible())

    def sugestoes(self) -> list[str]:
        if self._completar is None:
            return []
        modelo = self._completar.completionModel()
        return [modelo.index(i, 0).data() for i in range(modelo.rowCount())]

    # ---------------------------------------------------------------- busca, escala, invisíveis

    def buscar(self, texto: str, *, para_tras: bool = False) -> bool:
        from PyQt6.QtGui import QTextDocument

        self.contadores.buscas += 1
        if para_tras:
            return self.find(texto, QTextDocument.FindFlag.FindBackward)
        return self.find(texto)

    def ir_para_linha(self, linha: int) -> None:
        bloco = self.document().findBlockByNumber(max(0, linha - 1))
        cursor = QTextCursor(bloco)
        self.setTextCursor(cursor)
        self.centerCursor()

    def aplicar_escala(self, fator: float) -> None:
        fonte = self.font()
        fonte.setPointSizeF(self._tamanho_base * fator)
        self.setFont(fonte)
        self.margem.setFont(fonte)
        self._ajustar_margem()
        self.contadores.escala_aplicada = fator

    def mostrar_invisiveis(self, ligado: bool) -> None:
        opcao = self.document().defaultTextOption()
        bandeiras = opcao.flags()
        marca = QTextOption.Flag.ShowTabsAndSpaces
        opcao.setFlags(bandeiras | marca if ligado else bandeiras & ~marca)
        self.document().setDefaultTextOption(opcao)

    # ---------------------------------------------------------------- colar e prévia

    def insertFromMimeData(self, origem: QMimeData | None) -> None:  # noqa: N802 - do Qt
        if origem is not None and "colar_simples" in self.funcoes and origem.hasText():
            self.insertPlainText(origem.text())
            self.contadores.colados_simples += 1
            return
        super().insertFromMimeData(origem)

    def _mudou_o_texto(self) -> None:
        if "previa" in self.funcoes and not self.carregando:
            self._previa.start()

    def _emitir_previa(self) -> None:
        self.contadores.pedidos_de_previa += 1
        self.pedir_previa.emit(self.toPlainText())

    def previa_recebida(self, _resultado: object) -> None:
        self.contadores.previas_recebidas += 1


# --------------------------------------------------------------------------- #
# A prévia no processo de trabalho
# --------------------------------------------------------------------------- #


class PreviaNoProcesso(QObject):
    """Manda o texto a um processo à parte (o PyMuPDF segura o GIL); a última pedida vence."""

    pronta = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None,
                 funcao: Callable[[str], Any] | None = None) -> None:
        super().__init__(parent)
        import concurrent.futures
        import multiprocessing

        from caissa.editor.previa import renderizar

        self._funcao = funcao or renderizar
        self._executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context("spawn"))
        self._em_voo = None
        self._pendente: str | None = None
        self.pedidos = 0
        self.respostas = 0

    def pedir(self, texto: str) -> None:
        self.pedidos += 1
        if self._em_voo is not None and not self._em_voo.done():
            self._pendente = texto            # a última vence
            return
        self._enviar(texto)

    def _enviar(self, texto: str) -> None:
        self._em_voo = self._executor.submit(self._funcao, texto)
        self._em_voo.add_done_callback(self._voltou)

    def _voltou(self, futuro: Any) -> None:     # roda numa thread do executor
        try:
            resultado = futuro.result()
        except Exception as falha:  # noqa: BLE001 - a falha da prévia é dita, não engolida
            resultado = {"erro": f"{type(falha).__name__}: {falha}"}
        self.respostas += 1
        self.pronta.emit(resultado)           # conexão enfileirada: chega na thread da janela
        pendente, self._pendente = self._pendente, None
        if pendente is not None:
            self._enviar(pendente)

    def encerrar(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)


@dataclass
class Montagem:
    """O editor e a prévia ligados, como a janela do H11 vai ligar."""

    editor: EditorDeCodigo
    previa: PreviaNoProcesso | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def montar(texto: str = "", *, tipo: str = "xhtml", funcoes: Iterable[str] = FUNCOES,
           classes_do_projeto: Iterable[str] = (), com_previa: bool = True) -> Montagem:
    editor = EditorDeCodigo(tipo=tipo, funcoes=funcoes, classes_do_projeto=classes_do_projeto)
    previa = None
    if com_previa and "previa" in editor.funcoes:
        previa = PreviaNoProcesso(editor)
        editor.pedir_previa.connect(previa.pedir)
        previa.pronta.connect(editor.previa_recebida)
    if texto:
        editor.carregar(texto)
    return Montagem(editor, previa)
