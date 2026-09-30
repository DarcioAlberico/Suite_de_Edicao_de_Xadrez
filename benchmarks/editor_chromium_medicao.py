r"""O arnês de medição Chromium do Editor HTML/CSS — a entrega do passo H1 que o H19 e o H24 usam.

Roda no **ambiente de medição** (o venv de rascunho com o `PyQt6-WebEngine` 6.11, fora do
repositório), mesmo que o produto não leve o componente, e cumpre o contrato executável do
**Apêndice D** da spec:

- **A página.** Viewport de 1280 × 800 px CSS, `zoomFactor` 1,0, o JavaScript da página desligado;
  o script de medição roda no *ApplicationWorld*. Sem janela na tela (`offscreen`, desenho em
  software: `--disable-gpu --disable-gpu-compositing`, que também faz a captura determinística) e,
  por isso, sem ponteiro nem `:hover`. Uma folha de medição injetada só aqui zera `animation`,
  `transition` e `caret-color`. Toda requisição que não é um arquivo da pasta do livro é recusada e
  contada (R1.15).
- **A escala.** A `devicePixelRatio` (DPR) é lida e registrada; a captura tem o viewport × DPR; o
  retângulo CSS (x, y, l, a) cobre os pixels de `floor(x·DPR)` a `ceil((x+l)·DPR)`; área em px²
  CSS = pixels ÷ DPR².
- **O foco.** `focar_por_tab` manda `Tab` de verdade (`QTest.keyClick`) e espera o
  `document.activeElement` ser o alvo (a cada 16 ms, até 500 ms) e mais dois quadros. A captura não
  focada é feita com o foco num sentinela `tabindex=-1` fora do link, com a mesma rolagem.
- **A região e o limiar.** A união dos retângulos do link inflados por `outline-width` +
  max(`outline-offset`, 0) + 4 px CSS; um pixel muda quando a maior diferença entre os canais é
  ≥ 16; pixel mudado fora da região invalida a medida.
- **2.4.12:** (a) em todo centro de pixel CSS da união dos `getClientRects()` do link, recortada ao
  viewport, `elementsFromPoint(x, y)[0]` é o link ou um descendente; (b) o indicador por
  **máscara**: a renderização isolada (os outros elementos em `visibility: hidden`; nos
  ancestrais, `html` e `body` inclusive, os `::before`/`::after` escondidos e o `outline` e o
  `box-shadow` em `none`, por estilo em linha e por uma folha injetada por último, ambos com
  `!important`, conferidos pelo `getComputedStyle`) contra a normal — pixel da máscara isolada que
  não muda na normal está **encoberto**.
- **2.4.13:** na máscara real, a área ≥ P × 2 px² CSS (P = a soma dos perímetros dos retângulos
  não focados) e o contraste ≥ 3:1 numa área ≥ P × 2.
- **O autoteste** (o portão do H1): as sete fixtures do apêndice, com o resultado esperado; a
  sétima roda num processo com `QT_SCALE_FACTOR=1.5`. A sabotagem `pseudo_do_body` não esconde o
  pseudo-elemento dos ancestrais, e a fixture (6) tem de reprovar.

Uso (o Python é o do ambiente de medição)::

    $MEDICAO = "C:\Python-Chess2\_h1_webengine\.venv\Scripts\python.exe"
    & $MEDICAO benchmarks\editor_chromium_medicao.py --autoteste `
        --saida benchmarks\reports\editor\h1\chromium
    & ... benchmarks\editor_chromium_medicao.py --foco <arquivo.xhtml> [--folha <a.css> ...] `
        --saida <pasta>
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LARGURA, ALTURA = 1280, 800
LIMIAR_DO_CANAL = 16
ESPERA_DO_FOCO_MS, PASSO_MS = 500, 16
BANDEIRAS_DO_CHROMIUM = "--disable-gpu --disable-gpu-compositing"
FOLHA_DE_MEDICAO = ("*, *::before, *::after { animation: none !important; "
                    "transition: none !important; caret-color: transparent !important; }")
SABOTAGENS = ("pseudo_do_body",)
FAMILIAS_GENERICAS = {"StandardFont": "Times New Roman", "SerifFont": "Times New Roman",
                      "SansSerifFont": "Arial", "FixedFont": "Consolas",
                      "CursiveFont": "Comic Sans MS", "FantasyFont": "Impact"}
"""As famílias genéricas do Chrome no Windows (o `QWebEngineSettings.FontFamily` de cada uma)."""


def _preparar_ambiente() -> None:
    """Antes do Qt: sem janela na tela e desenho em software (a captura fica determinística)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    bandeiras = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu" not in bandeiras:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{bandeiras} {BANDEIRAS_DO_CHROMIUM}".strip()


# --------------------------------------------------------------------------- #
# Os pixels
# --------------------------------------------------------------------------- #


@dataclass
class Imagem:
    """A captura em RGB, linha a linha (bytes), na escala do dispositivo."""

    largura: int
    altura: int
    linhas: list[bytes]

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        linha = self.linhas[y]
        b, g, r = linha[4 * x], linha[4 * x + 1], linha[4 * x + 2]
        return r, g, b


def _imagem_do_qt(qimage: Any) -> Imagem:
    from PyQt6.QtGui import QImage

    rgb = qimage.convertToFormat(QImage.Format.Format_RGB32)
    largura, altura, passo = rgb.width(), rgb.height(), rgb.bytesPerLine()
    ponteiro = rgb.constBits()
    ponteiro.setsize(passo * altura)
    dados = bytes(ponteiro)
    return Imagem(largura, altura, [dados[y * passo:y * passo + 4 * largura]
                                    for y in range(altura)])


def mudados(a: Imagem, b: Imagem) -> set[tuple[int, int]]:
    """Os pixels em que a maior diferença entre os canais é ≥ 16 (de 255)."""
    fora: set[tuple[int, int]] = set()
    for y in range(min(a.altura, b.altura)):
        linha_a, linha_b = a.linhas[y], b.linhas[y]
        if linha_a == linha_b:
            continue
        for x in range(min(a.largura, b.largura)):
            i = 4 * x
            if linha_a[i:i + 3] == linha_b[i:i + 3]:
                continue
            if max(abs(linha_a[i + c] - linha_b[i + c]) for c in range(3)) >= LIMIAR_DO_CANAL:
                fora.add((x, y))
    return fora


def _luminancia(cor: tuple[int, int, int]) -> float:
    def canal(valor: int) -> float:
        c = valor / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(v) for v in cor)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """A razão de contraste do WCAG entre duas cores."""
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def pixels_do_retangulo(ret: dict[str, float], dpr: float, largura: int,
                        altura: int) -> Iterable[tuple[int, int]]:
    """Os pixels do dispositivo que o retângulo CSS cobre: floor(x·DPR) a ceil((x+l)·DPR)."""
    x0 = max(0, math.floor(ret["x"] * dpr))
    y0 = max(0, math.floor(ret["y"] * dpr))
    x1 = min(largura, math.ceil((ret["x"] + ret["width"]) * dpr))
    y1 = min(altura, math.ceil((ret["y"] + ret["height"]) * dpr))
    for y in range(y0, y1):
        for x in range(x0, x1):
            yield x, y


# --------------------------------------------------------------------------- #
# O navegador
# --------------------------------------------------------------------------- #

_BASE_JS = """
(function () {
  if (!window.__medicao) { window.__medicao = {ids: new Map(), els: [], quadros: 0}; }
  const M = window.__medicao;
  M.id = function (el) {
    if (!M.ids.has(el)) { M.ids.set(el, M.els.length); M.els.push(el); }
    return M.ids.get(el);
  };
  M.el = function (i) { return M.els[i]; };
  M.rects = function (el) {
    return [...el.getClientRects()].filter(r => r.width > 0 && r.height > 0)
      .map(r => ({x: r.x, y: r.y, width: r.width, height: r.height}));
  };
  return true;
})()
"""


@dataclass
class MedidaDoLink:
    """O resultado de um link: 2.4.12 (a) e (b), e 2.4.13 (área e contraste)."""

    link: int
    rotulo: str
    retangulos: list[dict[str, float]] = field(default_factory=list)
    perimetro: float = 0.0
    dpr: float = 1.0
    cobertos_na_caixa: int = 0
    pontos_na_caixa: int = 0
    area_real: float = 0.0
    area_isolada: float = 0.0
    encobertos: int = 0
    area_com_contraste: float = 0.0
    mudados_fora_da_regiao: int = 0
    invalida: str = ""

    @property
    def passa(self) -> bool:
        return (not self.invalida and self.cobertos_na_caixa == 0 and self.encobertos == 0
                and self.area_real >= 2 * self.perimetro
                and self.area_com_contraste >= 2 * self.perimetro)


class Medidor:
    """Um `QWebEngineView` de medição: carrega um livro e mede o foco dos links dele."""

    def __init__(self, *, sabotagem: str | None = None, javascript: bool = False) -> None:
        """`javascript=True` só no controle do livro hostil (o script tem de rodar ali).

        A sabotagem `sem_interceptador` (do H1) deixa o interceptador só olhar: o que sai da
        pasta do livro vai em `permitidas`, e não é recusado. A `sem_guarda_de_rede` tira também
        a outra camada, o `LocalContentCanAccessRemoteUrls` desligado, que barra o endereço de
        rede antes do interceptador.
        """
        _preparar_ambiente()
        from PyQt6.QtWebEngineCore import (
            QWebEnginePage,
            QWebEngineProfile,
            QWebEngineSettings,
            QWebEngineUrlRequestInterceptor,
        )
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication

        self.app = QApplication.instance() or QApplication(sys.argv[:1])
        self.sabotagem = sabotagem
        self.pasta: Path | None = None
        self.recusadas: list[str] = []
        self.permitidas: list[str] = []
        """O que saiu da pasta do livro sem ser recusado (só na sabotagem `sem_interceptador`)."""
        medidor = self

        class Interceptador(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info: Any) -> None:  # noqa: N802 - o nome do Qt
                url = info.requestUrl()
                caminho = Path(url.toLocalFile()) if url.isLocalFile() else None
                if caminho is None or medidor.pasta is None or not _dentro(caminho,
                                                                         medidor.pasta):
                    if medidor.sabotagem in ("sem_interceptador", "sem_guarda_de_rede"):
                        medidor.permitidas.append(url.toString())
                        return
                    medidor.recusadas.append(url.toString())
                    info.block(True)

        class Pagina(QWebEnginePage):
            """A guarda de navegação: a página não sai do livro (o meta refresh, o link).

            Sem ela, um `<meta http-equiv="refresh">` leva a prévia a um endereço de fora — a
            requisição é barrada, mas a página do livro vai embora (medido no H1, livro hostil).
            """

            def acceptNavigationRequest(self, url: Any, _tipo: Any,  # noqa: N802 - o nome do Qt
                                        _principal: bool) -> bool:
                caminho = Path(url.toLocalFile()) if url.isLocalFile() else None
                if (caminho is not None and medidor.pasta is not None
                        and _dentro(caminho, medidor.pasta)) or url.toString() == "about:blank":
                    return True
                if medidor.sabotagem == "sem_guarda_de_rede":
                    medidor.permitidas.append("navegação: " + url.toString())
                    return True
                medidor.recusadas.append("navegação: " + url.toString())
                return False

        self.perfil = QWebEngineProfile()  # sem nome: fora do disco, nada guardado
        self.interceptador = Interceptador()
        self.perfil.setUrlRequestInterceptor(self.interceptador)
        self.view = QWebEngineView()
        self.pagina = Pagina(self.perfil, self.view)
        self.view.setPage(self.pagina)
        ajustes = self.pagina.settings()
        # Fora da tela, o Qt não dá ao Chromium as famílias genéricas: `serif`, `sans-serif` e
        # `monospace` caem todas na mesma fonte. As do Chrome no Windows, ditas aqui.
        familia = QWebEngineSettings.FontFamily
        for qual, nome in FAMILIAS_GENERICAS.items():
            ajustes.setFontFamily(getattr(familia, qual), nome)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, javascript)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                             sabotagem == "sem_guarda_de_rede")
        self.view.setZoomFactor(1.0)
        self.view.resize(LARGURA, ALTURA)
        self.view.show()

    # -- o laço do Qt ----------------------------------------------------

    def esperar(self, ms: int) -> None:
        from PyQt6.QtCore import QEventLoop, QTimer

        laco = QEventLoop()
        QTimer.singleShot(ms, laco.quit)
        laco.exec()

    def js(self, codigo: str, *, prazo_ms: int = 5000) -> Any:
        """O código no ApplicationWorld; o resultado, ou `RuntimeError` sem resposta."""
        from PyQt6.QtCore import QEventLoop, QTimer
        from PyQt6.QtWebEngineCore import QWebEngineScript

        resposta: dict[str, Any] = {}
        laco = QEventLoop()

        def pronto(valor: Any) -> None:
            resposta["valor"] = valor
            laco.quit()

        self.pagina.runJavaScript(codigo, QWebEngineScript.ScriptWorldId.ApplicationWorld, pronto)
        QTimer.singleShot(prazo_ms, laco.quit)
        laco.exec()
        if "valor" not in resposta:
            raise RuntimeError(f"o script de medição não respondeu: {codigo[:80]}")
        return resposta["valor"]

    def quadros(self, n: int = 2) -> None:
        """Espera `n` quadros (`requestAnimationFrame` no ApplicationWorld)."""
        self.js("window.__medicao.quadros = 0; (function q(k){ requestAnimationFrame(() => {"
                " window.__medicao.quadros++; if (k > 1) q(k - 1); }); })(" + str(n) + "); 0")
        for _ in range(ESPERA_DO_FOCO_MS // PASSO_MS):
            # A página que foi embora (um refresh) já não tem o `__medicao`: sem quadros.
            if (self.js("window.__medicao ? window.__medicao.quadros : 0") or 0) >= n:
                return
            self.esperar(PASSO_MS)
        raise RuntimeError("os quadros não vieram")

    # -- a API do arnês --------------------------------------------------

    def carregar(self, xhtml: str, folhas: Sequence[tuple[str, str]] = (),
                 folha_do_usuario: str | None = None,
                 imagens: dict[str, bytes] | None = None, *,
                 nome_da_pagina: str = "pagina.xhtml") -> None:
        """O livro numa pasta temporária (`Text/`, `Styles/`, `Images/`), carregado do disco.

        `nome_da_pagina` escolhe o analisador do Chromium pela extensão: o `.xhtml` é XML (o
        livro), o `.html` é HTML5 (a página do exportador HTML de hoje, sem o `xmlns`, H1
        tarefa 2).
        """
        from PyQt6.QtCore import QEventLoop, QTimer, QUrl

        self.pasta = Path(tempfile.mkdtemp(prefix="caissa_medicao_"))
        (self.pasta / "Text").mkdir()
        (self.pasta / "Styles").mkdir()
        (self.pasta / "Images").mkdir()
        for nome, texto in folhas:
            (self.pasta / "Styles" / nome).write_text(texto, encoding="utf-8")
        for nome, dados in (imagens or {}).items():
            (self.pasta / "Images" / nome).write_bytes(dados)
        arquivo = self.pasta / "Text" / nome_da_pagina
        arquivo.write_text(xhtml, encoding="utf-8")
        self.recusadas.clear()
        self.permitidas.clear()
        carregou: dict[str, bool] = {}
        laco = QEventLoop()

        def fim(ok: bool) -> None:
            carregou["ok"] = ok
            laco.quit()

        self.pagina.loadFinished.connect(fim)
        self.view.load(QUrl.fromLocalFile(str(arquivo)))
        QTimer.singleShot(20000, laco.quit)
        laco.exec()
        self.pagina.loadFinished.disconnect(fim)
        if not carregou.get("ok"):
            raise RuntimeError(f"o livro não carregou: {arquivo}")
        self.js(_BASE_JS)
        folha = FOLHA_DE_MEDICAO + ("\n" + folha_do_usuario if folha_do_usuario else "")
        self.js("(function(){ const s = document.createElementNS('http://www.w3.org/1999/xhtml',"
                " 'style'); s.id = '__medicao_folha'; s.textContent = " + json.dumps(folha)
                + "; (document.head || document.documentElement).appendChild(s);"
                " const t = document.createElementNS('http://www.w3.org/1999/xhtml', 'span');"
                " t.id = '__medicao_sentinela'; t.tabIndex = -1; t.setAttribute('style',"
                " 'position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;"
                "pointer-events:none'); document.body.insertBefore(t, document.body.firstChild);"
                " return true; })()")
        self.quadros()

    def dpr(self) -> float:
        return float(self.js("window.devicePixelRatio"))

    def focaveis(self) -> list[dict[str, Any]]:
        """Os links (`a[href]`) na ordem do `Tab`: id do arnês, rótulo e retângulos."""
        return list(self.js(
            "[...document.querySelectorAll('a[href]')].map(a => ({id: window.__medicao.id(a),"
            " rotulo: (a.textContent || '').trim().slice(0, 60),"
            " rects: window.__medicao.rects(a)}))"))

    def focar_por_tab(self, link: int) -> None:
        """Foca o link com `Tab` de verdade, a partir do focável anterior (ou do sentinela)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest

        self.js("(function(){ const alvo = window.__medicao.el(" + str(link) + ");"
                " const todos = [...document.querySelectorAll('a[href]')];"
                " const i = todos.indexOf(alvo);"
                " const antes = i > 0 ? todos[i - 1] : document.getElementById("
                "'__medicao_sentinela');"
                " antes.focus({preventScroll: true}); return i; })()")
        destino = self.view.focusProxy() or self.view
        destino.setFocus()
        QTest.keyClick(destino, Qt.Key.Key_Tab)
        for _ in range(ESPERA_DO_FOCO_MS // PASSO_MS):
            if self.js("document.activeElement === window.__medicao.el(" + str(link) + ")"):
                self.quadros()
                return
            self.esperar(PASSO_MS)
        raise RuntimeError(f"o Tab não chegou ao link {link}")

    def retangulos(self, link: int) -> list[dict[str, float]]:
        return list(self.js("(function(){ const el = window.__medicao.el(" + str(link) + ");"
                            " el.scrollIntoView({block: 'center', inline: 'nearest'});"
                            " return window.__medicao.rects(el); })()"))

    def elementos_no_ponto(self, x: float, y: float) -> list[str]:
        return list(self.js(f"document.elementsFromPoint({x}, {y}).map(e => e.tagName)"))

    def estilo_calculado(self, link: int, pseudo: str | None = None) -> dict[str, str]:
        alvo = "null" if pseudo is None else json.dumps(pseudo)
        return dict(self.js(
            "(function(){ const s = getComputedStyle(window.__medicao.el(" + str(link) + "), "
            + alvo + "); const o = {}; for (const p of ['outline-width', 'outline-offset',"
            " 'outline-style', 'box-shadow', 'visibility', 'color', 'background-color'])"
            " o[p] = s.getPropertyValue(p); return o; })()"))

    def capturar(self, *, diferente_de: Imagem | None = None, prazo_ms: int = 400) -> Imagem:
        """A captura depois que o quadro novo chega e assenta.

        Os dois quadros do `requestAnimationFrame` são o mínimo do Apêndice D; o desenho em
        software ainda leva o quadro ao widget depois deles, e duas capturas iguais seguidas
        podem ser as do quadro velho. Por isso a captura espera o quadro mudar em relação ao
        estado de antes (`diferente_de`), até o prazo — a mudança que não vem é legítima (o link
        sem indicador) —, e depois espera duas capturas iguais.
        """
        atual = _imagem_do_qt(self.view.grab().toImage())
        if diferente_de is None:
            self.esperar(prazo_ms)
        else:
            for _ in range(prazo_ms // PASSO_MS):
                if atual.linhas != diferente_de.linhas:
                    break
                self.esperar(PASSO_MS)
                atual = _imagem_do_qt(self.view.grab().toImage())
        for _ in range(60):
            self.esperar(2 * PASSO_MS)
            seguinte = _imagem_do_qt(self.view.grab().toImage())
            if seguinte.linhas == atual.linhas:
                return seguinte
            atual = seguinte
        return atual

    # -- o foco de um link (Apêndice D) --------------------------------------

    def _desfocar(self) -> None:
        self.js("document.getElementById('__medicao_sentinela').focus({preventScroll: true});"
                " true")
        self.quadros()

    def _isolar(self, link: int) -> str:
        """A renderização isolada, e o motivo de invalidade.

        O motivo é '' quando a neutralização venceu o CSS do autor.
        """
        pseudos = "" if self.sabotagem == "pseudo_do_body" else (
            "[data-medicao-ancestral]::before, [data-medicao-ancestral]::after,"
            " html[data-medicao-ancestral]::before, html[data-medicao-ancestral]::after"
            " { visibility: hidden !important; }")
        return str(self.js(
            "(function(){ const link = window.__medicao.el(" + str(link) + ");"
            " const ancestrais = new Set(); for (let e = link.parentElement; e;"
            " e = e.parentElement) ancestrais.add(e);"
            " window.__medicao.guardados = [];"
            " for (const e of document.querySelectorAll('*')) {"
            "  if (e === link || link.contains(e)"
            "   || ['__medicao_folha', '__medicao_sentinela'].includes(e.id)) continue;"
            "  window.__medicao.guardados.push([e, e.getAttribute('style')]);"
            "  if (ancestrais.has(e)) { e.setAttribute('data-medicao-ancestral', '');"
            "   e.style.setProperty('outline', 'none', 'important');"
            "   e.style.setProperty('box-shadow', 'none', 'important'); }"
            "  else if (!['HEAD','TITLE','META','LINK','STYLE','SCRIPT'].includes(e.tagName))"
            "   e.style.setProperty('visibility', 'hidden', 'important'); }"
            " const s = document.createElementNS('http://www.w3.org/1999/xhtml', 'style');"
            " s.id = '__medicao_isolada'; s.textContent = " + json.dumps(pseudos) + ";"
            " document.documentElement.appendChild(s);"
            " for (const e of document.querySelectorAll('*')) {"
            "  if (e === link || link.contains(e) || e.id === '__medicao_sentinela') continue;"
            "  const c = getComputedStyle(e);"
            "  if (ancestrais.has(e)) {"
            "   if (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0)"
            "    return 'o outline de ' + e.tagName + ' venceu a neutralização';"
            "   if (c.boxShadow !== 'none') return 'o box-shadow de ' + e.tagName +"
            "    ' venceu a neutralização';"
            "   for (const p of ['::before', '::after']) {"
            "    const q = getComputedStyle(e, p);"
            "    if (q.content !== 'none' && q.visibility !== 'hidden' && " +
            ("false" if self.sabotagem == "pseudo_do_body" else "true") +
            ") return 'o ' + p + ' de ' + e.tagName + ' venceu a neutralização'; } }"
            "  else if (!['HEAD','TITLE','META','LINK','STYLE','SCRIPT'].includes(e.tagName)"
            "   && !['__medicao_isolada', '__medicao_sentinela'].includes(e.id)"
            "   && c.visibility !== 'hidden')"
            "   return 'a visibilidade de ' + e.tagName + ' venceu a neutralização'; }"
            " return ''; })()"))

    def _desisolar(self) -> None:
        self.js("(function(){ for (const [e, s] of window.__medicao.guardados || []) {"
                " if (s === null) e.removeAttribute('style'); else e.setAttribute('style', s);"
                " e.removeAttribute('data-medicao-ancestral'); }"
                " const s = document.getElementById('__medicao_isolada'); if (s) s.remove();"
                " window.__medicao.guardados = []; return true; })()")

    def medir_link(self, link: int, rotulo: str = "") -> MedidaDoLink:
        """2.4.12 e 2.4.13 de um link, pelo contrato do Apêndice D."""
        medida = MedidaDoLink(link=link, rotulo=rotulo, dpr=self.dpr())
        nao_focados = self.retangulos(link)
        rolagem = self.js("[scrollX, scrollY]")
        if any(r["height"] > ALTURA for r in nao_focados):
            medida.invalida = "link mais alto que o viewport: a medida por faixas não é deste arnês"
            return medida
        self._desfocar()
        base = self.capturar()
        self.focar_por_tab(link)
        self.js(f"scrollTo({rolagem[0]}, {rolagem[1]}); true")
        self.quadros()
        focada = self.capturar(diferente_de=base)
        estilo = self.estilo_calculado(link)
        motivo = self._isolar(link)
        self.quadros()
        focada_isolada = self.capturar(diferente_de=focada)
        self._desfocar()
        self.js(f"scrollTo({rolagem[0]}, {rolagem[1]}); true")
        self.quadros()
        nao_focada_isolada = self.capturar(diferente_de=focada_isolada)
        self._desisolar()
        self.quadros()
        nao_focada = self.capturar(diferente_de=nao_focada_isolada)
        if nao_focada.linhas != base.linhas and not motivo:
            motivo = "a renderização não focada não voltou igual depois da isolada"
        medida.retangulos = nao_focados
        medida.perimetro = sum(2 * (r["width"] + r["height"]) for r in nao_focados)
        if motivo:
            medida.invalida = motivo
        # (a) dentro das caixas do link, o topo é o link ou um descendente
        cobertos = self.js(
            "(function(){ const link = window.__medicao.el(" + str(link) + "); let n = 0,"
            " t = 0; for (const r of window.__medicao.rects(link)) {"
            " const x0 = Math.max(0, Math.floor(r.x)), y0 = Math.max(0, Math.floor(r.y));"
            " const x1 = Math.min(innerWidth, Math.ceil(r.x + r.width)),"
            " y1 = Math.min(innerHeight, Math.ceil(r.y + r.height));"
            " for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {"
            " if (x + 0.5 >= r.x + r.width || y + 0.5 >= r.y + r.height) continue; t++;"
            " const topo = document.elementsFromPoint(x + 0.5, y + 0.5)[0];"
            " if (!(topo && (topo === link || link.contains(topo)))) n++; } }"
            " return [n, t]; })()")
        medida.cobertos_na_caixa, medida.pontos_na_caixa = int(cobertos[0]), int(cobertos[1])
        # a região: os retângulos inflados pelo contorno e mais 4 px
        inflar = (_px(estilo.get("outline-width")) + max(_px(estilo.get("outline-offset")), 0)
                  + 4)
        regiao: set[tuple[int, int]] = set()
        for ret in nao_focados:
            inflado = {"x": ret["x"] - inflar, "y": ret["y"] - inflar,
                       "width": ret["width"] + 2 * inflar, "height": ret["height"] + 2 * inflar}
            regiao.update(pixels_do_retangulo(inflado, medida.dpr, focada.largura,
                                              focada.altura))
        real = mudados(nao_focada, focada)
        isolado = mudados(nao_focada_isolada, focada_isolada)
        medida.mudados_fora_da_regiao = len(real - regiao)
        if medida.mudados_fora_da_regiao and not medida.invalida:
            medida.invalida = (f"{medida.mudados_fora_da_regiao} pixels mudaram fora da região:"
                               " a mudança não é só do indicador")
        escala = medida.dpr ** 2
        medida.area_real = len(real & regiao) / escala
        medida.area_isolada = len(isolado & regiao) / escala
        medida.encobertos = len((isolado - real) & regiao)
        com_contraste = sum(1 for x, y in real & regiao
                            if contraste(nao_focada.pixel(x, y), focada.pixel(x, y)) >= 3)
        medida.area_com_contraste = com_contraste / escala
        return medida


def _px(valor: str | None) -> float:
    try:
        return float((valor or "0").removesuffix("px") or 0)
    except ValueError:
        return 0.0


def _dentro(caminho: Path, pasta: Path) -> bool:
    try:
        caminho.resolve().relative_to(pasta.resolve())
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------- #
# O autoteste (o portão do H1)
# --------------------------------------------------------------------------- #


def _pagina(corpo: str, estilo: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
            'lang="pt-BR" xml:lang="pt-BR"><head><title>autoteste</title><style>'
            "body { margin: 60px; font: 20px/1.6 serif; background: #ffffff; color: #111111; }"
            "a { color: #1c4f8b; text-decoration: none; }" + estilo + "</style></head><body>"
            + corpo + "</body></html>")


FIXTURES: dict[str, tuple[str, str]] = {
    "1_outline": ('<p><a href="#a">um link com contorno</a></p>',
                  "a:focus { outline: 2px solid #d00000; outline-offset: 0; }"),
    "2_box_shadow": ('<p><a href="#a">um link com sombra</a></p>',
                     "a:focus { outline: none; box-shadow: 0 0 0 3px #d00000; }"),
    # A caixa do link fica em y = 65..87 (a margem de 60 px e a entrelinha de 32 px); o contorno
    # de 2 px, em y = 63..64, e a sombra de 4 px, em y = 61..64.
    "3_faixa_irma": ('<p style="position: relative"><a href="#a">um link coberto</a>'
                     '<span style="position: absolute; left: 0; top: 3px; width: 400px;'
                     ' height: 1px; background: #ffffff"></span></p>',
                     "a:focus { outline: 2px solid #d00000; }"),
    "4_duas_linhas": ('<p style="width: 230px"><a href="#a">um link longo que quebra em duas'
                      " linhas</a></p>", "a:focus { outline: 2px solid #d00000; }"),
    "5_after_de_outro": ('<p style="position: relative"><a href="#a">um link</a>'
                         '<span class="cobre"></span></p>',
                         "a:focus { outline: 2px solid #d00000; }"
                         ".cobre::after { content: ''; position: absolute; left: 0; top: 3px;"
                         " width: 300px; height: 2px; background: #ffffff; }"),
    "6_after_do_body": ('<p><a href="#a">um link</a></p>',
                        "a:focus { outline: none; box-shadow: 0 0 0 4px #d00000; }"
                        "body::after { content: ''; position: absolute; left: 0;"
                        " top: 62px; width: 600px; height: 2px; background: #ffffff;"
                        " z-index: 5; }"),
}


def _esperado_do_contorno(rets: Sequence[dict[str, float]], largura: float) -> float:
    """A área, em px² CSS, de um contorno de `largura` em volta dos retângulos."""
    return sum((r["width"] + 2 * largura) * (r["height"] + 2 * largura) - r["width"] * r["height"]
               for r in rets)


def autoteste(saida: Path, *, sabotagem: str | None = None) -> tuple[dict[str, bool], dict]:
    """As fixtures do Apêndice D com o resultado esperado; a (7) num processo com escala 1,5."""
    medidor = Medidor(sabotagem=sabotagem)
    registro: dict[str, Any] = {"dpr": None, "fixtures": {}}
    exigencias: dict[str, bool] = {}
    for nome, (corpo, estilo) in FIXTURES.items():
        medidor.carregar(_pagina(corpo, estilo))
        registro["dpr"] = medidor.dpr()
        links = medidor.focaveis()
        medida = medidor.medir_link(links[0]["id"], links[0]["rotulo"])
        registro["fixtures"][nome] = asdict(medida)
        if nome == "1_outline":
            esperada = _esperado_do_contorno(medida.retangulos, 2)
            ok = abs(medida.area_real - esperada) <= 0.01 * esperada and medida.encobertos == 0
            exigencias[f"(1) outline 2px: área {medida.area_real:.0f} px² (esperada "
                       f"{esperada:.0f} ±1 %), {medida.encobertos} encobertos"] = ok
        elif nome == "2_box_shadow":
            esperada = _esperado_do_contorno(medida.retangulos, 3)
            ok = abs(medida.area_real - esperada) <= 0.01 * esperada and medida.encobertos == 0
            exigencias[f"(2) box-shadow 3px: área {medida.area_real:.0f} px² (esperada "
                       f"{esperada:.0f} ±1 %), {medida.encobertos} encobertos"] = ok
        elif nome == "4_duas_linhas":
            exigencias[f"(4) link em duas linhas: {len(medida.retangulos)} retângulos, área "
                       f"{medida.area_real:.0f} px²"] = (len(medida.retangulos) == 2
                                                         and medida.area_real > 0)
        else:
            numero = nome.split("_")[0]
            exigencias[f"({numero}) {nome}: {medida.encobertos} encobertos (esperado > 0)"] = (
                medida.encobertos > 0)
    exigencias.update(_autoteste_da_escala(registro, saida))
    return exigencias, registro


def _autoteste_da_escala(registro: dict[str, Any], saida: Path) -> dict[str, bool]:
    """(7) com `QT_SCALE_FACTOR=1.5`: as áreas em px² CSS iguais às de DPR 1 a ±2 %."""
    saida.mkdir(parents=True, exist_ok=True)
    arquivo = saida / "escala_1_5.json"
    ambiente = {**os.environ, "QT_SCALE_FACTOR": "1.5"}
    subprocess.run(  # noqa: S603 - o Python e os argumentos são deste arnês
        [sys.executable, __file__, "--so-fixture", "1_outline", "--json", str(arquivo)],
        env=ambiente, check=False, timeout=180)
    if not arquivo.is_file():
        return {"(7) escala 1,5: o processo não gravou a medida": False}
    medida = json.loads(arquivo.read_text(encoding="utf-8"))
    base = registro["fixtures"]["1_outline"]["area_real"]
    area = medida["area_real"]
    registro["escala_1_5"] = medida
    return {f"(7) escala 1,5 (DPR {medida['dpr']}): área {area:.0f} px² contra {base:.0f} "
            "com DPR 1 (±2 %)": base > 0 and abs(area - base) <= 0.02 * base
            and medida["dpr"] > 1}


def medir_livro(arquivo: Path, folhas: Sequence[Path], saida: Path) -> tuple[dict[str, bool],
                                                                              dict]:
    """Todo link de um arquivo XHTML: 2.4.12 e 2.4.13."""
    medidor = Medidor()
    medidor.carregar(arquivo.read_text(encoding="utf-8"),
                     [(f.name, f.read_text(encoding="utf-8")) for f in folhas])
    medidas = [medidor.medir_link(link["id"], link["rotulo"]) for link in medidor.focaveis()]
    reprovados = [m for m in medidas if not m.passa]
    registro = {"arquivo": str(arquivo), "dpr": medidor.dpr(), "recusadas": medidor.recusadas,
                "links": [asdict(m) for m in medidas]}
    saida.mkdir(parents=True, exist_ok=True)
    return ({f"foco: {len(medidas) - len(reprovados)}/{len(medidas)} links passam em 2.4.12 e "
             "2.4.13" + (" -- " + "; ".join(f"{m.rotulo}: {m.invalida or 'encoberto/área'}"
                                            for m in reprovados[:5]) if reprovados else ""):
             not reprovados}, registro)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--autoteste", action="store_true")
    parser.add_argument("--foco", type=Path)
    parser.add_argument("--folha", type=Path, action="append", default=[])
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--so-fixture", choices=sorted(FIXTURES))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.so_fixture:
        medidor = Medidor()
        corpo, estilo = FIXTURES[args.so_fixture]
        medidor.carregar(_pagina(corpo, estilo))
        link = medidor.focaveis()[0]
        medida = medidor.medir_link(link["id"], link["rotulo"])
        args.json.write_text(json.dumps(asdict(medida), ensure_ascii=False), encoding="utf-8")
        return 0
    if args.saida is None:
        parser.error("--saida é obrigatório")
    if args.autoteste:
        exigencias, registro = autoteste(args.saida, sabotagem=args.sabotar)
    elif args.foco is not None:
        exigencias, registro = medir_livro(args.foco, args.folha, args.saida)
    else:
        parser.error("diga --autoteste ou --foco <arquivo>")
    registro["sabotagem"] = args.sabotar
    registro["exigencias"] = exigencias
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "chromium_medicao.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


_ = (Callable,)

if __name__ == "__main__":
    raise SystemExit(main())
