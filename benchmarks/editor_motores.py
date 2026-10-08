r"""Os motores de pré-visualização, medidos — o passo H1 do Editor HTML/CSS (tarefas 1, 2, 3e e 4).

Mede os dois motores que a spec D3 põe lado a lado: o **MuPDF** (`pymupdf.Story`, que o produto já
leva) e o **Chromium** (o `QWebEngineView` do PyQt6-WebEngine 6.11), que roda no **ambiente de
medição** — o venv de rascunho fora do repositório (`C:\Python-Chess2\_h1_webengine\.venv`, ou a
variável `CAISSA_WEBENGINE_PY`), que o produto não leva —, num processo filho, pelo arnês
`editor_chromium_medicao.py`.

1. **A matriz de CSS** (`--matriz`). As declarações dos 9 temas do CB
   (`sigil_chess.layout.templates`: a folha base mais a de cada tema), do `BASE_CSS`
   (`caissa.export.html`) e do `CHESS_CSS` (`caissa.export.epub`), lidas pelo `tinycss2`. Cada par
   propriedade–valor distinto é um caso: uma página **com** a declaração e outra **sem** ela, no
   elemento-alvo `#alvo` (no pseudo-elemento dele, quando a regra de origem é de um); o resto da
   regra de onde o par veio vai nas duas páginas, e as variáveis `:root` da folha de origem
   também. Na `font-family`, a página «sem» tem a família genérica da própria lista (a pergunta é
   se o motor acha a fonte nomeada, e não se ela difere da do molde). **«Desenha» = pixels
   diferentes** (a maior diferença entre os canais ≥ 16) no retângulo do alvo e do vizinho dele —
   a caixa do molde, `#caixa`, a união da das duas páginas, com 4 px de folga: a margem de baixo e
   a quebra só se veem no vizinho. O MuPDF roda aqui, rasterizado a 96 dpi, com um teto de
   páginas (a paginação que não termina vira o veredito «laço»). **O Chromium é a referência:** o
   caso que ele não desenha não tem efeito visível nesta página («sem efeito aqui») e fica fora do
   veredito do MuPDF. Dois **controles** conferem o instrumento: `color: #c00` desenha nos dois
   motores; `color: #000` (o padrão) não desenha em nenhum. Saída: `matriz_css.json` — os casos,
   o veredito por propriedade e motor, e a lista do que o Chromium desenha e o MuPDF não (a
   entrada do validador, H10).
2. **O livro hostil** (`--hostil`): `tests/fixtures/editor/hostil/`, nos dois motores; ver
   `hostil()`.
3. **A latência e as posições** (`--latencia`, tarefa 2): os capítulos de 50 KB e 260 KB do
   `PEDIDO` p. 50–60 pelo exportador HTML de hoje (o `XhtmlBuilder`; do IR real do H5, `--ir-real`
   — sem ele, o corpus sintético, e a exigência reprova). **MuPDF:** tecla → o leiaute do
   capítulo na página A5 da prévia e o raster da página, p50/p95 em 20 edições. **Posições:** um
   `id` em cada bloco (a cópia da prévia) e a cobertura do `element_positions` (**100 %**, o
   portão; a sabotagem `sem_ids` a derruba), e o acerto clique → bloco em 400 cliques (semente 42),
   conferido pelo texto na ordem. **Chromium** (o processo filho do ambiente de medição): o frio
   (do lançamento à primeira pintura), a memória extra (o hospedeiro e os `QtWebEngineProcess`) e
   o remendo do DOM por `runJavaScript` até a pintura (dois `requestAnimationFrame`), p50/p95 em
   50 edições — os critérios 2, 3 e 5 da D3, publicados. Saída: `latencia.json`.
4. **Os tamanhos do componente** (`--tamanhos`, tarefa 3e): ver `tamanhos()`.

Uso::

    & $PY benchmarks\editor_motores.py --matriz --saida benchmarks\reports\editor\h1\matriz
    & $PY benchmarks\editor_motores.py --matriz --limite 8 --saida <pasta>   (a rodada curta)
    & $PY benchmarks\editor_motores.py --latencia --ir-real benchmarks\reports\editor\h5_ir_real `
        --saida benchmarks\reports\editor\h1\latencia
"""

from __future__ import annotations

import argparse
import bisect
import html
import io
import itertools
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

LIMIAR_DO_CANAL = 16
FOLGA_PX = 4
DPI_DO_MUPDF = 96
MAXIMO_DE_PAGINAS = 12
PAGINA_EM_PONTOS = (960.0, 600.0)
"""A página do MuPDF em pontos: 1280 × 800 px a 96 dpi, o viewport do arnês Chromium."""

TEXTO = ("A posição depois do 20.º lance (1.e4 e5 2.Cf3 Cc6 3.Bb5 a6) é um exemplo clássico: as "
         "brancas trocam as damas, levam o rei ao centro e ganham o final de peões com a oposição "
         "— 1-0 em 41 lances, uma técnica que todo jogador precisa conhecer.")
VIZINHO = "O parágrafo vizinho, que se move quando a margem ou a quebra do alvo mudam."
MOLDES: dict[str, str] = {
    "bloco": f'<div id="caixa"><p id="alvo">{TEXTO}</p><p class="vizinho">{VIZINHO}</p></div>',
    "inline": f'<div id="caixa"><p>Antes do alvo <span id="alvo">alvo</span> e depois dele. '
              f'{TEXTO}</p></div>',
    "lista": '<div id="caixa"><ul id="alvo"><li>primeiro item da lista</li>'
             f'<li>segundo item da lista</li></ul><p class="vizinho">{VIZINHO}</p></div>',
    "tabela": '<div id="caixa"><table id="alvo"><caption>A legenda da tabela</caption>'
              '<tr><td>a1</td><td>b1</td></tr><tr><td>a2</td><td>b2</td></tr></table>'
              f'<p class="vizinho">{VIZINHO}</p></div>',
}
GENERICAS = ("serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui")
MOLDE_DA_PROPRIEDADE = {"list-style": "lista", "list-style-type": "lista",
                        "list-style-position": "lista", "border-collapse": "tabela",
                        "border-spacing": "tabela", "caption-side": "tabela",
                        "vertical-align": "inline"}
FOLHA_DO_MOLDE = ("body { margin: 8px; font-family: serif; font-size: 16px; line-height: 1.4; "
                  "color: #000; background: #fff; }\n#caixa { width: 600px; }\n"
                  "#alvo { background-color: #e0e0e0; }\n"
                  "td { border: 2px solid #444; padding: 2px 6px; }\n")
PSEUDOS = ("::before", "::after", "::first-letter", "::first-line", "::marker")
PAGINACAO = frozenset({"page-break-before", "page-break-after", "page-break-inside",
                       "break-before", "break-after", "break-inside", "orphans", "widows"})
"""As propriedades da paginação: a tela não as desenha; o MuPDF, que pagina, pode."""
CONTROLES = (("color", "#c00", True), ("color", "#000", False))
"""O par e se ele tem de desenhar: o instrumento que erra num deles não mede nada."""
HOSTIL = RAIZ / "tests" / "fixtures" / "editor" / "hostil"
ESPERA_DO_HOSTIL_MS = 600
"""Quanto a página hostil tem depois de carregar para tentar o que for (o refresh, o onerror)."""
SABOTAGENS = ("sem_interceptador", "sem_guarda_de_rede", "sem_ids")
"""`sem_interceptador` (do roadmap): o interceptador só olha, e o arquivo de fora passa.
`sem_guarda_de_rede`: tira também o `LocalContentCanAccessRemoteUrls` desligado, a camada que
barra o endereço de rede antes do interceptador — e as requisições chegam ao servidor."""


# --------------------------------------------------------------------------- #
# Os casos
# --------------------------------------------------------------------------- #


@dataclass
class Caso:
    """Um par propriedade–valor, com o contexto da regra de onde ele veio."""

    propriedade: str
    valor: str
    contexto: list[tuple[str, str]]
    pseudo: str
    molde: str
    variaveis: str
    fontes: list[str] = field(default_factory=list)
    controle: bool | None = None
    """No controle, se ele tem de desenhar; `None` nos casos das folhas."""

    @property
    def chave(self) -> str:
        return f"{self.propriedade}: {self.valor}"

    def folha(self, *, com: bool) -> str:
        """A folha da página: o molde, as variáveis da origem e a regra do alvo.

        Sem a declaração, a `font-family` fica com a genérica da própria lista: o caso mede se
        o motor acha a fonte nomeada.
        """
        declaracoes = [f"{p}: {v}" for p, v in self.contexto]
        if com:
            declaracoes.append(f"{self.propriedade}: {self.valor}")
        elif self.propriedade == "font-family":
            declaracoes.append(f"font-family: {generica(self.valor, self.variaveis)}")
        regra = f"#alvo{self.pseudo} {{ {'; '.join(declaracoes)} }}" if declaracoes else ""
        return f"{FOLHA_DO_MOLDE}{self.variaveis}\n{regra}\n"


def generica(valor: str, variaveis: str) -> str:
    """A família genérica de uma lista de `font-family` (a da variável, se o valor for uma)."""
    casado = re.fullmatch(r"\s*var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)\s*", valor)
    if casado:
        definicao = re.search(re.escape(casado.group(1)) + r"\s*:\s*([^;}]+)", variaveis)
        valor = definicao.group(1) if definicao else ""
    familias = [f.strip().strip("\"'").lower() for f in valor.split(",")]
    return next((f for f in reversed(familias) if f in GENERICAS), "serif")


def fontes_de_css() -> dict[str, str]:
    """As folhas medidas: os 9 temas do CB (a base mais o tema) e as duas do Caissa."""
    cb = _principal().parent / "Sigil-master" / "src" / "Resource_Files" / "python3lib"
    if str(cb) not in sys.path:
        sys.path.insert(0, str(cb))
    from sigil_chess.layout.templates import TEMPLATES

    from caissa.export.epub import CHESS_CSS
    from caissa.export.html import BASE_CSS

    fontes = {f"cb:{nome}": tema.css for nome, tema in TEMPLATES.items()}
    fontes["caissa:BASE_CSS"] = BASE_CSS
    fontes["caissa:CHESS_CSS"] = CHESS_CSS
    return fontes


def extrair_casos(fontes: dict[str, str]) -> tuple[list[Caso], dict[str, Any]]:
    """Os pares distintos das folhas, pelo `tinycss2`, e o que ficou fora (as `@page`)."""
    import tinycss2

    casos: dict[tuple[str, str], Caso] = {}
    fora: dict[str, int] = {}

    def declaracoes(regra: Any) -> list[tuple[str, str]]:
        return [(d.lower_name, tinycss2.serialize(d.value).strip())
                for d in tinycss2.parse_declaration_list(regra.content, skip_whitespace=True,
                                                         skip_comments=True)
                if d.type == "declaration"]

    for nome, css in fontes.items():
        regras = list(tinycss2.parse_stylesheet(css, skip_whitespace=True, skip_comments=True))
        variaveis = "\n".join(
            f":root {{ {'; '.join(f'{p}: {v}' for p, v in declaracoes(r) if p.startswith('--'))} }}"
            for r in regras if r.type == "qualified-rule"
            and tinycss2.serialize(r.prelude).strip() == ":root")
        pilha = list(regras)
        while pilha:
            regra = pilha.pop(0)
            if regra.type == "at-rule":
                if regra.lower_at_keyword in ("media", "supports") and regra.content is not None:
                    pilha[:0] = list(tinycss2.parse_rule_list(regra.content, skip_whitespace=True,
                                                              skip_comments=True))
                else:
                    fora[f"@{regra.lower_at_keyword}"] = fora.get(
                        f"@{regra.lower_at_keyword}", 0) + 1
                continue
            if regra.type != "qualified-rule":
                continue
            seletor = tinycss2.serialize(regra.prelude).strip()
            pseudo = next((p for p in PSEUDOS if p in seletor or p[1:] in seletor), "")
            todas = [(p, v) for p, v in declaracoes(regra) if not p.startswith("--")]
            for propriedade, valor in todas:
                chave = (propriedade, valor)
                if chave not in casos:
                    casos[chave] = Caso(
                        propriedade=propriedade, valor=valor,
                        contexto=[(p, v) for p, v in todas if p != propriedade],
                        pseudo=pseudo, molde=MOLDE_DA_PROPRIEDADE.get(propriedade, "bloco"),
                        variaveis=variaveis)
                if nome not in casos[chave].fontes:
                    casos[chave].fontes.append(nome)
    controles = [Caso(propriedade=p, valor=v, contexto=[], pseudo="", molde="bloco",
                      variaveis="", fontes=["controle"], controle=desenha)
                 for p, v, desenha in CONTROLES]
    return [*controles, *casos.values()], {"nao_testado": fora}


def pagina_xhtml(corpo: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR" xml:lang="pt-BR">\n'
            '<head><meta charset="utf-8"/><title>caso</title>'
            '<link rel="stylesheet" type="text/css" href="../Styles/caso.css"/></head>\n'
            f"<body>{corpo}</body>\n</html>\n")


# --------------------------------------------------------------------------- #
# O MuPDF
# --------------------------------------------------------------------------- #


@dataclass
class Raster:
    largura: int
    altura: int
    paginas: list[bytes]
    regiao: tuple[float, float, float, float] | None
    """O retângulo da `#caixa` (o alvo e o vizinho) na primeira página, em pixels."""
    laco: bool = False


def render_mupdf(corpo: str, css: str, *, arquivo: Path | None = None) -> Raster:
    """O Story do MuPDF, página a página até o teto, e cada página rasterizada.

    `arquivo` é a pasta de onde o MuPDF lê as imagens e as folhas (o `pymupdf.Archive`).
    """
    import pymupdf

    saida = io.BytesIO()
    escritor = pymupdf.DocumentWriter(saida)
    story = pymupdf.Story(html=corpo, user_css=css, em=16,
                          archive=pymupdf.Archive(str(arquivo)) if arquivo is not None else None)
    caixa = pymupdf.Rect(0, 0, *PAGINA_EM_PONTOS)
    posicoes: list[tuple[int, Any]] = []
    pagina = [0]

    def anotar(posicao: Any) -> None:  # o MuPDF exige um só argumento
        if posicao.id == "caixa":
            posicoes.append((pagina[0], tuple(posicao.rect)))

    mais = 1
    while mais and pagina[0] < MAXIMO_DE_PAGINAS:
        dispositivo = escritor.begin_page(caixa)
        mais, _ = story.place(caixa)
        story.element_positions(anotar)
        story.draw(dispositivo)
        escritor.end_page()
        pagina[0] += 1
    escritor.close()
    escala = DPI_DO_MUPDF / 72
    documento = pymupdf.open("pdf", saida.getvalue())
    imagens = [p.get_pixmap(dpi=DPI_DO_MUPDF, alpha=False) for p in documento]
    regiao = None
    for _, (x0, y0, x1, y1) in (p for p in posicoes if p[0] == 0):
        regiao = _uniao(regiao, (x0 * escala, y0 * escala, x1 * escala, y1 * escala))
    return Raster(imagens[0].width, imagens[0].height, [i.samples for i in imagens], regiao,
                  laco=bool(mais))


def pixels_mudados(a: bytes, b: bytes, largura: int, altura: int,
                   regiao: tuple[float, float, float, float] | None) -> int:
    """Os pixels RGB da região em que a maior diferença entre os canais é ≥ 16."""
    import numpy as np

    ia = np.frombuffer(a, dtype=np.uint8).reshape(altura, largura, 3).astype(np.int16)
    ib = np.frombuffer(b, dtype=np.uint8).reshape(altura, largura, 3).astype(np.int16)
    if regiao is not None:
        x0, y0, x1, y1 = (int(max(0, regiao[0] - FOLGA_PX)), int(max(0, regiao[1] - FOLGA_PX)),
                          int(min(largura, regiao[2] + FOLGA_PX + 1)),
                          int(min(altura, regiao[3] + FOLGA_PX + 1)))
        ia, ib = ia[y0:y1, x0:x1], ib[y0:y1, x0:x1]
    return int((np.abs(ia - ib).max(axis=2) >= LIMIAR_DO_CANAL).sum())


def _uniao(a: tuple[float, float, float, float] | None,
           b: tuple[float, float, float, float] | None) -> tuple[float, float, float, float] | None:
    if a is None or b is None:
        return a or b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def medir_mupdf(caso: Caso) -> dict[str, Any]:
    """O caso no MuPDF: os pixels mudados na região do alvo, e as páginas."""
    corpo = MOLDES[caso.molde]
    com, sem = render_mupdf(corpo, caso.folha(com=True)), render_mupdf(corpo, caso.folha(com=False))
    if com.laco or sem.laco:
        return {"veredito": "laco", "paginas": [len(com.paginas), len(sem.paginas)],
                "pixels": None}
    if len(com.paginas) != len(sem.paginas):
        return {"veredito": "desenha", "paginas": [len(com.paginas), len(sem.paginas)],
                "pixels": None}
    regiao = _uniao(com.regiao, sem.regiao)
    pixels = sum(pixels_mudados(a, b, com.largura, com.altura, regiao if i == 0 else None)
                 for i, (a, b) in enumerate(zip(com.paginas, sem.paginas, strict=True)))
    return {"veredito": "desenha" if pixels else "nao_desenha", "pixels": pixels,
            "paginas": [len(com.paginas), len(sem.paginas)]}


# --------------------------------------------------------------------------- #
# O Chromium, no processo filho do ambiente de medição
# --------------------------------------------------------------------------- #


def python_do_webengine() -> Path:
    """O Python do ambiente de medição com o PyQt6-WebEngine (fora do repositório)."""
    variavel = os.environ.get("CAISSA_WEBENGINE_PY")
    if variavel:
        return Path(variavel)
    return _principal().parent / "_h1_webengine" / ".venv" / "Scripts" / "python.exe"


def medir_no_chromium(casos: Sequence[Caso], pasta: Path) -> list[dict[str, Any]]:
    """Os casos no Chromium, num processo filho do ambiente de medição."""
    pasta.mkdir(parents=True, exist_ok=True)
    entrada, saida = pasta / "casos_chromium.json", pasta / "resultado_chromium.json"
    entrada.write_text(json.dumps([{"propriedade": c.propriedade, "pseudo": c.pseudo,
                                    "corpo": MOLDES[c.molde], "com": c.folha(com=True),
                                    "sem": c.folha(com=False)} for c in casos],
                                  ensure_ascii=False), encoding="utf-8")
    python = python_do_webengine()
    if not python.is_file():
        raise FileNotFoundError(f"o ambiente de medição com o WebEngine não existe: {python}")
    processo = subprocess.run(  # noqa: S603 - o Python do ambiente de medição, com os nossos args
        [str(python), str(Path(__file__).resolve()), "--filho-chromium", str(entrada),
         str(saida)], capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=3600)
    (pasta / "chromium.log").write_text(processo.stdout + processo.stderr, encoding="utf-8")
    if processo.returncode != 0 or not saida.is_file():
        raise RuntimeError(f"o processo do Chromium falhou ({processo.returncode}): "
                           f"{(processo.stderr or processo.stdout)[-600:]}")
    return list(json.loads(saida.read_text(encoding="utf-8")))


def filho_chromium(entrada: Path, saida: Path) -> int:
    """No ambiente de medição: cada caso com e sem a declaração, pelo arnês Chromium."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import editor_chromium_medicao as cm

    medidor = cm.Medidor()
    resultados = []
    anterior = None
    for caso in json.loads(entrada.read_text(encoding="utf-8")):
        medidas = {}
        for estado in ("com", "sem"):
            medidor.carregar(pagina_xhtml(caso["corpo"]), [("caso.css", caso[estado])])
            estado_js = medidor.js(
                "(function(){ const el = document.getElementById('alvo');"
                " const r = window.__medicao.rects(document.getElementById('caixa'));"
                " const s = getComputedStyle(el, "
                + (json.dumps(caso["pseudo"]) if caso["pseudo"] else "null")
                + "); return {rects: r, calculado: s.getPropertyValue("
                + json.dumps(caso["propriedade"]) + ")}; })()")
            imagem = medidor.capturar(diferente_de=anterior)
            anterior = imagem
            medidas[estado] = (imagem, estado_js)
        (img_com, js_com), (img_sem, js_sem) = medidas["com"], medidas["sem"]
        retangulos = [*js_com["rects"], *js_sem["rects"]]
        regiao = None
        for r in retangulos:
            regiao = _uniao(regiao, (r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"]))
        dpr = medidor.dpr()
        mudados = cm.mudados(img_com, img_sem)
        if regiao is not None:
            x0, y0 = (regiao[0] - FOLGA_PX) * dpr, (regiao[1] - FOLGA_PX) * dpr
            x1, y1 = (regiao[2] + FOLGA_PX) * dpr, (regiao[3] + FOLGA_PX) * dpr
            mudados = {(x, y) for x, y in mudados if x0 <= x <= x1 and y0 <= y <= y1}
        sem_efeito = js_com["calculado"] == js_sem["calculado"]
        resultados.append({"pixels": len(mudados), "calculado_com": js_com["calculado"],
                           "calculado_sem": js_sem["calculado"], "sem_efeito": sem_efeito,
                           "recusadas": list(medidor.recusadas),
                           "veredito": "desenha" if mudados else "nao_desenha"})
    saida.write_text(json.dumps(resultados, ensure_ascii=False), encoding="utf-8")
    return 0


# --------------------------------------------------------------------------- #
# A matriz
# --------------------------------------------------------------------------- #


def veredito_da_propriedade(casos: Iterable[dict[str, Any]], motor: str) -> dict[str, Any]:
    """Desenha, não desenha ou parcial, nos valores que o Chromium desenha.

    O Chromium é a referência: o valor que ele não desenha não tem efeito visível nesta página
    («sem efeito aqui»). O laço (a paginação do MuPDF que não termina) vence os outros: é o defeito
    que trava a prévia.
    """
    casos = list(casos)
    if any(c[motor]["veredito"] == "laco" for c in casos):
        return {"veredito": "laco", "falham": [c["valor"] for c in casos
                                               if c[motor]["veredito"] == "laco"]}
    visiveis = [c for c in casos if c["chromium"]["veredito"] == "desenha"]
    if not visiveis:
        return {"veredito": "sem_efeito_aqui", "falham": []}
    falham = [c["valor"] for c in visiveis if c[motor]["veredito"] != "desenha"]
    veredito = ("nao_desenha" if len(falham) == len(visiveis)
                else "parcial" if falham else "desenha")
    return {"veredito": veredito, "falham": falham}


def matriz(saida: Path, *, limite: int | None = None) -> tuple[dict[str, bool], dict[str, Any]]:
    """A matriz de CSS nos dois motores, e as exigências do instrumento."""
    fontes = fontes_de_css()
    casos, extras = extrair_casos(fontes)
    if limite is not None:
        casos = casos[:limite]
    resultados_mupdf = [medir_mupdf(c) for c in casos]
    resultados_chromium = medir_no_chromium(casos, saida)
    linhas = [{**{k: v for k, v in asdict(c).items() if k != "variaveis"},
               "mupdf": m, "chromium": ch}
              for c, m, ch in zip(casos, resultados_mupdf, resultados_chromium, strict=True)]
    por_propriedade: dict[str, dict[str, Any]] = {}
    for propriedade in sorted({c.propriedade for c in casos if c.controle is None}):
        dela = [linha for linha in linhas
                if linha["propriedade"] == propriedade and linha["controle"] is None]
        por_propriedade[propriedade] = {motor: veredito_da_propriedade(dela, motor)
                                        for motor in ("mupdf", "chromium")}
        # A quebra de página não desenha na tela do Chromium, e nem deve: é da paginação.
        por_propriedade[propriedade]["paginacao"] = propriedade in PAGINACAO
    mupdf_nao = {p: v["mupdf"]["falham"] for p, v in por_propriedade.items()
                 if v["mupdf"]["veredito"] in ("nao_desenha", "parcial", "laco")}
    exigencias: dict[str, bool] = {}
    for linha in (li for li in linhas if li["controle"] is not None):
        esperado = "desenha" if linha["controle"] else "nao_desenha"
        obtido = (linha["mupdf"]["veredito"], linha["chromium"]["veredito"])
        exigencias[f"controle «{linha['propriedade']}: "
                   f"{linha['valor']}» {esperado} nos dois motores (MuPDF {obtido[0]}, "
                   f"Chromium {obtido[1]})"] = obtido == (esperado, esperado)
    completos = sum(1 for li in linhas if li["mupdf"]["veredito"] and li["chromium"]["veredito"])
    exigencias[f"matriz completa: {completos}/{len(linhas)} casos com veredito nos dois motores "
               f"({len(por_propriedade)} propriedades, {len(fontes)} folhas)"] = (
        completos == len(linhas))
    registro = {"fontes": {nome: len(css) for nome, css in fontes.items()}, **extras,
                "casos": linhas, "por_propriedade": por_propriedade,
                "mupdf_nao_desenha": mupdf_nao,
                "laco_no_mupdf": [li["propriedade"] + ": " + li["valor"] for li in linhas
                                  if li["mupdf"]["veredito"] == "laco"]}
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "matriz_css.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    return exigencias, registro


# --------------------------------------------------------------------------- #
# O livro hostil
# --------------------------------------------------------------------------- #


class Servidor:
    """Um servidor TCP em 127.0.0.1 que só conta o que chega nele: nada sai da máquina."""

    def __init__(self) -> None:
        import socketserver
        import threading

        self.chegadas: list[str] = []
        servidor = self

        class Contador(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                self.request.settimeout(1.0)
                try:
                    dados = self.request.recv(2048)
                except OSError:
                    dados = b""
                primeira = dados.split(b"\r\n", 1)[0].decode("latin-1", "replace")[:160]
                servidor.chegadas.append("(tls)" if dados[:1] == b"\x16" else primeira)

        self._tcp = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Contador)
        self._tcp.daemon_threads = True
        self.porta = int(self._tcp.server_address[1])
        threading.Thread(target=self._tcp.serve_forever, daemon=True).start()

    def fechar(self) -> None:
        self._tcp.shutdown()
        self._tcp.server_close()


def livro_hostil(destino: Path, porta: int) -> tuple[Path, Path]:
    """O livro hostil em `destino/livro`, com a porta do servidor e a sentinela (`destino`)."""
    livro, sentinela = destino / "livro", destino / "fora.png"
    sentinela.write_bytes((HOSTIL / "Images" / "dentro.png").read_bytes())
    for arquivo in sorted(p for p in HOSTIL.rglob("*") if p.is_file() and p.suffix != ".md"):
        alvo = livro / arquivo.relative_to(HOSTIL)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if arquivo.suffix in (".xhtml", ".css", ".svg"):
            alvo.write_text(arquivo.read_text(encoding="utf-8").replace("{PORTA}", str(porta))
                            .replace("{FORA}", sentinela.as_uri()), encoding="utf-8")
        else:
            alvo.write_bytes(arquivo.read_bytes())
    return livro, sentinela


def _css_do_livro(livro: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8")
                     for p in sorted((livro / "Styles").glob("*.css")))


def hostil_no_mupdf(livro: Path, sentinela: Path, servidor: Servidor) -> dict[str, Any]:
    """Cada página no MuPDF; a sentinela e a imagem de dentro, lidas ou não, pelos pixels.

    O MuPDF lê imagens e folhas do `Archive` do livro. A página 09 é desenhada com e sem a
    sentinela (fora do livro) e com e sem a imagem de dentro: a de dentro tem de mudar o desenho
    (o controle), e a sentinela não.
    """
    antes = len(servidor.chegadas)
    paginas = {}
    for pagina in sorted((livro / "Text").glob("*.xhtml")):
        try:
            raster = render_mupdf(pagina.read_text(encoding="utf-8"), _css_do_livro(livro),
                                  arquivo=livro)
            paginas[pagina.name] = {"paginas": len(raster.paginas), "laco": raster.laco}
        except Exception as falha:  # noqa: BLE001 - o motor que cai também é resultado
            paginas[pagina.name] = {"erro": f"{type(falha).__name__}: {falha}"}

    def desenho() -> list[bytes]:
        return render_mupdf((livro / "Text" / "09_arquivos_fora.xhtml").read_text(
            encoding="utf-8"), _css_do_livro(livro), arquivo=livro).paginas

    def muda_sem(arquivo: Path) -> bool:
        com = desenho()
        guardado = arquivo.with_suffix(".guardado")
        arquivo.rename(guardado)
        try:
            sem = desenho()
        finally:
            guardado.rename(arquivo)
        return com != sem

    return {"paginas": paginas, "requisicoes": servidor.chegadas[antes:],
            "sentinela_lida": muda_sem(sentinela),
            "dentro_desenha": muda_sem(livro / "Images" / "dentro.png")}


def hostil_no_chromium(livro: Path, pasta: Path, servidor: Servidor, *,
                       sabotagem: str | None, javascript: bool) -> dict[str, Any]:
    """O livro hostil no Chromium, no processo filho do ambiente de medição."""
    pasta.mkdir(parents=True, exist_ok=True)
    rotulo = "js" if javascript else (sabotagem or "normal")
    entrada, saida = pasta / f"hostil_{rotulo}.json", pasta / f"hostil_{rotulo}_resultado.json"
    entrada.write_text(json.dumps({"livro": str(livro), "sabotagem": sabotagem,
                                   "javascript": javascript}), encoding="utf-8")
    antes = len(servidor.chegadas)
    processo = subprocess.run(  # noqa: S603 - o Python do ambiente de medição, com os nossos args
        [str(python_do_webengine()), str(Path(__file__).resolve()), "--filho-hostil",
         str(entrada), str(saida)], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False, timeout=1800)
    (pasta / f"hostil_{rotulo}.log").write_text(processo.stdout + processo.stderr,
                                                encoding="utf-8")
    if processo.returncode != 0 or not saida.is_file():
        raise RuntimeError(f"o processo do Chromium falhou ({processo.returncode}): "
                           f"{(processo.stderr or processo.stdout)[-600:]}")
    return {"paginas": json.loads(saida.read_text(encoding="utf-8")),
            "requisicoes": servidor.chegadas[antes:]}


def filho_hostil(entrada: Path, saida: Path) -> int:
    """No ambiente de medição: cada página do livro hostil, o que ela tentou e o que rodou."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import editor_chromium_medicao as cm

    dados = json.loads(entrada.read_text(encoding="utf-8"))
    livro = Path(dados["livro"])
    medidor = cm.Medidor(sabotagem=dados["sabotagem"], javascript=dados["javascript"])
    folhas = [(p.name, p.read_text(encoding="utf-8")) for p in sorted((livro / "Styles")
                                                                     .glob("*.css"))]
    imagens = {p.name: p.read_bytes() for p in sorted((livro / "Images").iterdir())}
    resultados = {}
    for pagina in sorted((livro / "Text").glob("*.xhtml")):
        print(f"página {pagina.name}", file=sys.stderr, flush=True)
        registro: dict[str, Any] = {}
        try:
            medidor.carregar(pagina.read_text(encoding="utf-8"), folhas, imagens=imagens)
            if 'id="j"' in pagina.read_text(encoding="utf-8"):
                links = medidor.focaveis()
                if links:
                    medidor.focar_por_tab(links[0]["id"])
                    QTest.keyClick(medidor.view.focusProxy() or medidor.view, Qt.Key.Key_Return)
            medidor.esperar(ESPERA_DO_HOSTIL_MS)
            registro["marca"] = medidor.js(
                "document.documentElement.getAttribute('data-hostil')")
        except Exception as falha:  # noqa: BLE001 - a página que foi embora não responde
            registro["erro"] = f"{type(falha).__name__}: {falha}"
            medidor.esperar(ESPERA_DO_HOSTIL_MS)
        # A página que o refresh levou embora: o endereço final já não é o do livro.
        registro["url_final"] = medidor.view.url().toString()
        registro["navegou"] = not registro["url_final"].endswith("/Text/pagina.xhtml")
        registro["recusadas"] = list(medidor.recusadas)
        registro["permitidas"] = list(medidor.permitidas)
        resultados[pagina.name] = registro
    saida.write_text(json.dumps(resultados, ensure_ascii=False), encoding="utf-8")
    return 0


def hostil(saida: Path, *, sabotagem: str | None = None) -> tuple[dict[str, bool],
                                                                   dict[str, Any]]:
    """O livro hostil nos dois motores, e o controle com o JavaScript ligado."""
    servidor = Servidor()
    try:
        with tempfile.TemporaryDirectory(prefix="caissa_hostil_") as temporaria:
            livro, sentinela = livro_hostil(Path(temporaria), servidor.porta)
            mupdf = hostil_no_mupdf(livro, sentinela, servidor)
            chromium = hostil_no_chromium(livro, saida, servidor, sabotagem=sabotagem,
                                          javascript=False)
            controle = hostil_no_chromium(livro, saida, servidor, sabotagem=None,
                                          javascript=True)
    finally:
        servidor.fechar()
    paginas = chromium["paginas"].values()
    marcas = [p["marca"] for p in paginas if p.get("marca")]
    permitidas = [u for p in paginas for u in p["permitidas"]]
    recusadas = [u for p in paginas for u in p["recusadas"]]
    navegacoes = [nome for nome, p in chromium["paginas"].items() if p.get("navegou")]
    marcas_do_controle = [p["marca"] for p in controle["paginas"].values() if p.get("marca")]
    exigencias = {
        f"hostil no Chromium: {len(chromium['requisicoes'])} requisição(ões) ao servidor, "
        f"{len(marcas)} script(s) rodado(s), {len(permitidas)} pedido(s) de fora do livro "
        f"deixado(s) passar, {len(navegacoes)} navegação(ões) para fora "
        f"({len(recusadas)} recusado(s) pelo interceptador)"
        + (f" -- {'; '.join(chromium['requisicoes'][:3])}" if chromium["requisicoes"] else "")
        + (f" -- {'; '.join(permitidas[:3])}" if permitidas else "")
        + (f" -- {', '.join(navegacoes)}" if navegacoes else ""): (
            not chromium["requisicoes"] and not marcas and not permitidas and not navegacoes),
        f"hostil no MuPDF: {len(mupdf['requisicoes'])} requisição(ões) ao servidor, a sentinela "
        f"de fora do livro {'lida' if mupdf['sentinela_lida'] else 'não lida'}, sem motor de "
        "script; o controle: a imagem de dentro "
        f"{'desenha' if mupdf['dentro_desenha'] else 'NÃO desenha'}": (
            not mupdf["requisicoes"] and not mupdf["sentinela_lida"] and mupdf["dentro_desenha"]),
        f"controle: com o JavaScript ligado, o Chromium roda {len(marcas_do_controle)} script(s) "
        f"do livro hostil ({', '.join(marcas_do_controle)})": bool(marcas_do_controle),
    }
    registro = {"porta": servidor.porta, "sabotagem": sabotagem, "mupdf": mupdf,
                "chromium": chromium, "controle_javascript": controle}
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "hostil.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return exigencias, registro


# --------------------------------------------------------------------------- #
# Os tamanhos do componente
# --------------------------------------------------------------------------- #

RODAS_DO_COMPONENTE = ("pyqt6_webengine", "pyqt6_webengine_qt6")
ORCAMENTO_MB = {"download": 150.0, "instalado": 300.0}
"""O orçamento do componente Chromium (spec §5.5)."""
TRADUCOES_MANTIDAS = ("pt-BR.pak", "en-US.pak")


def _corte(nome: str) -> str | None:
    """Por que o arquivo sai do componente aparado, ou `None` se fica."""
    base = nome.rsplit("/", 1)[-1]
    if base.endswith(".debug.pak") or "devtools" in base:
        return "depuração e ferramentas do desenvolvedor"
    if "/qtwebengine_locales/" in nome and base not in TRADUCOES_MANTIDAS:
        return "traduções além de pt-BR e en-US"
    if "Quick" in base or "/qml/" in nome:
        return "Qt Quick e QML"
    if base.endswith(".pyi") or "/bindings/" in nome or "/qsci/" in nome or ".dist-info/" in nome:
        return "desenvolvimento"
    return None


def tamanhos(saida: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    """Download e instalado do componente, inteiro e aparado, contra o orçamento da spec §5.5.

    O instalado sai dos `RECORD` das duas rodas no ambiente de medição; o download, das rodas no
    cache HTTP do pip (reconhecidas pelo `METADATA` de dentro do zip).
    """
    import csv
    import zipfile

    pacotes = python_do_webengine().parents[1] / "Lib" / "site-packages"
    arquivos: list[tuple[str, int]] = []
    versoes: dict[str, str] = {}
    for info in sorted(pacotes.glob("*.dist-info")):
        nome, _, versao = info.name.removesuffix(".dist-info").rpartition("-")
        if nome.lower() in RODAS_DO_COMPONENTE:
            versoes[nome.lower()] = versao
            with (info / "RECORD").open(encoding="utf-8") as registro:
                arquivos += [(linha[0], int(linha[2])) for linha in csv.reader(registro)
                             if len(linha) > 2 and linha[2].isdigit()]
    cortes: dict[str, int] = {}
    for nome, tamanho in arquivos:
        motivo = _corte(nome)
        if motivo:
            cortes[motivo] = cortes.get(motivo, 0) + tamanho
    inteiro = sum(t for _, t in arquivos)
    download = 0
    achadas: list[str] = []
    cache = Path(os.environ.get("LOCALAPPDATA", "")) / "pip" / "cache" / "http-v2"
    for corpo in cache.rglob("*.body") if cache.is_dir() else ():
        if corpo.stat().st_size < 100_000:
            continue
        try:
            with zipfile.ZipFile(corpo) as roda:
                metadados = next((n for n in roda.namelist() if n.endswith(".dist-info/METADATA")),
                                 "")
        except (zipfile.BadZipFile, OSError):
            continue
        nome = metadados.split("/", 1)[0].removesuffix(".dist-info")
        rotulo, _, versao = nome.rpartition("-")
        if rotulo.lower() in RODAS_DO_COMPONENTE and versoes.get(rotulo.lower()) == versao:
            download += corpo.stat().st_size
            achadas.append(nome)
    mb = {"download": download / 1e6, "inteiro": inteiro / 1e6,
          "aparado": (inteiro - sum(cortes.values())) / 1e6}
    exigencias = {
        f"componente: download {mb['download']:.1f} MB ({len(achadas)} de "
        f"{len(RODAS_DO_COMPONENTE)} rodas no cache) ≤ {ORCAMENTO_MB['download']:.0f} MB": (
            len(achadas) == len(RODAS_DO_COMPONENTE)
            and mb["download"] <= ORCAMENTO_MB["download"]),
        f"componente aparado: {mb['aparado']:.1f} MB instalado ≤ "
        f"{ORCAMENTO_MB['instalado']:.0f} MB (inteiro: {mb['inteiro']:.1f} MB)": (
            0 < mb["aparado"] <= ORCAMENTO_MB["instalado"]),
    }
    registro = {"versoes": versoes, "rodas_no_cache": achadas, "mb": mb,
                "cortes_mb": {k: v / 1e6 for k, v in sorted(cortes.items())},
                "orcamento_mb": ORCAMENTO_MB}
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "tamanhos.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return exigencias, registro


# --------------------------------------------------------------------------- #
# A linha de comando
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# A latência e as posições (tarefa 2)
# --------------------------------------------------------------------------- #

ALVOS_DOS_CAPITULOS = {"50kb": 50 * 1024, "260kb": 260 * 1024}
EDICOES_NO_MUPDF = 20
EDICOES_NO_CHROMIUM = 50
PONTOS = 400
SEMENTE = 42
ORCAMENTOS_DA_D3 = {"frio_s": 1.5, "remendo_p95_ms": 150.0, "memoria_mb": 350.0}
"""Os critérios 2, 3 e 5 da D3 (spec §3, D3; §5.5): o frio, o remendo e a memória extra."""
PAGINAS_DA_PREVIA = 500
"""O teto da paginação A5 da prévia (`previa.MAXIMO_DE_PAGINAS`)."""
_TEXTO_DO_BLOCO = re.compile(r">([^<>]*[^\s<>][^<>]*)<")
_SEM_TEXTO_DESENHADO = re.compile(r"<(style|script|svg)\b.*?</\1>", re.S)
"""O que não sai como texto na página do MuPDF: o CSS, o script e o SVG do texto (uma imagem)."""
FOLGA_DO_CLIQUE = 6.0
"""A distância (em pontos) em que o clique perto de um retângulo ainda é dele (o ascendente da
primeira linha fica acima da caixa do bloco)."""
SALTO_CURTO = 200
"""Até onde (em caracteres do texto normalizado) o trecho curto pode pular à frente: o «1» de uma
nota casaria com o «1» das coordenadas de um diagrama adiante e tiraria o resto do lugar."""
_ETIQUETA_DE_ABERTURA = re.compile(r"^<([A-Za-z][\w:-]*)")


@dataclass
class Capitulo:
    """Um capítulo da página do exportador HTML de hoje.

    A cabeça, os blocos do `<main>` e a cauda; os blocos repetem, na ordem, até o tamanho.
    """

    nome: str
    cabeca: str
    blocos: list[str]
    cauda: str
    origem: str

    def texto(self, trocas: dict[int, str] | None = None) -> str:
        trocas = trocas or {}
        return self.cabeca + "".join(trocas.get(k, b) for k, b in enumerate(self.blocos)) + \
            self.cauda

    @property
    def kb(self) -> float:
        """O tamanho do corpo (os blocos), em KB: o que o capítulo do projeto teria."""
        return sum(len(b.encode("utf-8")) for b in self.blocos) / 1024


def capitulos(ir_real: Path | None) -> dict[str, Capitulo]:
    """Os capítulos de 50 KB e 260 KB pelo `XhtmlBuilder` de hoje (a exportação HTML).

    Do `PEDIDO` p. 50–60 (o IR real do H5), ou do corpus sintético sem ele — e isso fica dito
    na origem.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from editor_ida_e_volta import carregar_ir_real, corpus_sintetico

    from caissa.editor.validacao.xml import Elemento, ler
    from caissa.export import export

    documentos = carregar_ir_real(ir_real) if ir_real is not None else {}
    if "pedido" in documentos:
        documento, origem = documentos["pedido"], "PEDIDO p. 50–60 (o IR real do H5)"
    else:
        documento, origem = corpus_sintetico(400, SEMENTE), "o corpus sintético (sem o IR real)"
    with tempfile.TemporaryDirectory(prefix="caissa_h1_capitulo_") as pasta:
        destino = Path(pasta) / "livro.html"
        export(documento, destino, "html")
        texto = destino.read_text(encoding="utf-8")
    lido, _ = ler("livro.html", texto)
    principal = next((e for e in lido.elementos() if e.nome == "main"), None)
    if principal is None:
        raise RuntimeError("a página do exportador HTML não tem <main>")
    filhos = [f for f in principal.filhos if isinstance(f, Elemento)]
    inicios = [lido.deslocamento(f.linha, f.coluna) for f in filhos]
    fim = texto.index("</main>", inicios[-1])
    blocos = [texto[a:b] for a, b in zip(inicios, [*inicios[1:], fim], strict=True)]
    cabeca, cauda = texto[:inicios[0]], texto[fim:]
    feitos = {}
    for nome, alvo in ALVOS_DOS_CAPITULOS.items():
        # O tamanho é o do corpo (os blocos): a cabeça da página do exportador leva o CSS e as
        # fontes embutidas, que no projeto do editor são arquivos à parte.
        escolhidos: list[str] = []
        tamanho = 0
        for bloco in itertools.cycle(blocos):
            if tamanho >= alvo:
                break
            escolhidos.append(bloco)
            tamanho += len(bloco.encode("utf-8"))
        feitos[nome] = Capitulo(nome, cabeca, escolhidos, cauda, origem)
    return feitos


def editar(capitulo: Capitulo, sorte: random.Random) -> tuple[int, str]:
    """Uma tecla: um caractere a mais no texto de um bloco sorteado."""
    for _ in range(100):
        indice = sorte.randrange(len(capitulo.blocos))
        bloco = capitulo.blocos[indice]
        trechos = list(_TEXTO_DO_BLOCO.finditer(bloco))
        if trechos:
            trecho = sorte.choice(trechos)
            lugar = sorte.randrange(trecho.start(1), trecho.end(1) + 1)
            return indice, bloco[:lugar] + "x" + bloco[lugar:]
    raise RuntimeError("nenhum bloco com texto no capítulo")


def _percentil(valores: Sequence[float], p: float) -> float:
    ordenados = sorted(valores)
    if not ordenados:
        return float("nan")
    return ordenados[min(len(ordenados) - 1, max(0, round(p / 100 * (len(ordenados) - 1))))]


def latencia_no_mupdf(capitulo: Capitulo, edicoes: int) -> dict[str, Any]:
    """Tecla → a página refeita, a cada edição (a primeira aquece e não conta).

    O leiaute do capítulo na página A5 da prévia, e o raster da página.
    """
    import pymupdf

    from caissa.editor.previa import paginar

    sorte = random.Random(SEMENTE)
    tempos: list[float] = []
    paginas, laco = 0, False
    pymupdf.TOOLS.mupdf_display_errors(False)
    for vez in range(edicoes + 1):
        indice, novo = editar(capitulo, sorte)
        texto = capitulo.texto({indice: novo})
        inicio = time.perf_counter()
        medida = paginar(texto, "", maximo=PAGINAS_DA_PREVIA)
        with pymupdf.open("pdf", medida.pdf) as pdf:
            pdf[0].get_pixmap(dpi=DPI_DO_MUPDF, alpha=False)
        if vez:
            tempos.append(1000 * (time.perf_counter() - inicio))
        paginas, laco = medida.paginas, medida.laco
    return {"kb": round(capitulo.kb, 1), "edicoes": len(tempos), "p50_ms": _percentil(tempos, 50),
            "p95_ms": _percentil(tempos, 95), "paginas": paginas, "laco": laco,
            "tempos_ms": [round(t, 1) for t in tempos]}


def _com_ids(capitulo: Capitulo) -> tuple[Capitulo, list[str]]:
    """O capítulo com um `id` em cada bloco; o `id` que o bloco já tem fica.

    É a cópia da prévia: o `element_positions` do MuPDF só dá a posição do elemento com `id`.
    """
    ids, blocos = [], []
    for indice, bloco in enumerate(capitulo.blocos):
        abertura = bloco[:bloco.index(">") + 1] if ">" in bloco else ""
        existente = re.search(r'\sid="([^"]+)"', abertura)
        if existente:
            ids.append(existente.group(1))
            blocos.append(bloco)
            continue
        ident = f"pos{indice}"
        ids.append(ident)
        blocos.append(_ETIQUETA_DE_ABERTURA.sub(rf'<\1 id="{ident}"', bloco, count=1))
    return Capitulo(capitulo.nome, capitulo.cabeca, blocos, capitulo.cauda, capitulo.origem), ids


def _texto_dos_blocos(blocos: Sequence[str]) -> list[str]:
    from caissa.editor.validacao.css import _normal

    sem_codigo = (_SEM_TEXTO_DESENHADO.sub("", b) for b in blocos)
    return [_normal(html.unescape(re.sub(r"<[^>]*>", "", b))) for b in sem_codigo]


def _visivel(bloco: str) -> bool:
    """O bloco que o MuPDF desenha: sem o `hidden`, e com texto ou imagem."""
    abertura = bloco[:bloco.index(">") + 1] if ">" in bloco else bloco
    if re.search(r"\shidden(=|\s|>|/)", abertura):
        return False
    texto = re.sub(r"<[^>]*>", "", _SEM_TEXTO_DESENHADO.sub("", bloco)).strip()
    return bool(texto) or "<img" in bloco or "<svg" in bloco


def _pagina_com_posicoes(texto: str) -> tuple[bytes, list[tuple[int, str, tuple[float, ...]]]]:
    """O capítulo na página A5 da prévia, e cada posição que o `element_positions` dá."""
    import io as _io

    import pymupdf

    historia = pymupdf.Story(html=texto, em=16)
    posicoes: list[tuple[int, str, tuple[float, ...]]] = []
    pagina_atual = [0]

    def anotar(posicao: Any) -> None:  # o MuPDF exige um só argumento
        if posicao.id:  # a abertura, o fecho e a continuação na página seguinte
            posicoes.append((pagina_atual[0], posicao.id, tuple(posicao.rect)))

    saida = _io.BytesIO()
    escritor = pymupdf.DocumentWriter(saida)
    caixa = pymupdf.Rect(36, 36, 420 - 36, 595 - 36)
    mais = True
    pymupdf.TOOLS.mupdf_display_errors(False)
    while mais and pagina_atual[0] < PAGINAS_DA_PREVIA:
        dispositivo = escritor.begin_page(pymupdf.Rect(0, 0, 420, 595))
        mais, _ = historia.place(caixa)
        historia.element_positions(anotar)
        historia.draw(dispositivo)
        escritor.end_page()
        pagina_atual[0] += 1
    escritor.close()
    return saida.getvalue(), posicoes


def _trechos_com_bloco(pdf_bytes: bytes,
                       capitulo: Capitulo) -> list[tuple[int, tuple[float, ...], int | None]]:
    """Cada trecho de texto da página (a página, a caixa) e o bloco que tem aquele texto.

    O bloco verdadeiro sai do texto, na ordem (o trecho curto só casa perto do anterior), e não
    das posições: é contra ele que o clique é conferido. O texto de fora do `<main>` (a cabeça do
    livro, o sumário, antes; as notas, depois) entra no fluxo sem bloco: senão o «Bispo» do
    sumário casaria dentro do primeiro bloco e tiraria o resto do lugar.
    """
    import pymupdf

    from caissa.editor.validacao.css import _normal

    trechos: list[tuple[int, str, tuple[float, ...]]] = []
    with pymupdf.open("pdf", pdf_bytes) as pdf:
        for numero, folha in enumerate(pdf):
            for bloco in folha.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT
                                        & ~pymupdf.TEXT_PRESERVE_IMAGES)["blocks"]:
                for linha in bloco.get("lines", []):
                    trechos += [(numero, s["text"], tuple(s["bbox"])) for s in linha["spans"]
                                if _normal(s["text"])]
    corpo = capitulo.cabeca[capitulo.cabeca.find("<body"):] if "<body" in capitulo.cabeca \
        else capitulo.cabeca
    textos = _texto_dos_blocos([corpo, *capitulo.blocos, capitulo.cauda])
    donos: list[int | None] = [None, *range(len(capitulo.blocos)), None]
    fluxo = "".join(textos)
    inicios = list(itertools.accumulate((len(t) for t in textos), initial=0))
    resultado: list[tuple[int, tuple[float, ...], int | None]] = []
    cursor = 0
    for numero, conteudo, caixa in trechos:
        chave = _normal(conteudo)
        achado = -1
        for variante in dict.fromkeys((chave, chave.rstrip("-\u2010"))):  # o hífen da quebra
            if variante:
                achado = fluxo.find(variante, cursor,
                                    None if len(variante) >= 12 else cursor + SALTO_CURTO)
            if achado >= 0:
                cursor = achado + len(variante)
                break
        resultado.append((numero, caixa, donos[bisect.bisect_right(inicios, achado) - 1]
                          if achado >= 0 else None))
    return resultado


def bloco_no_clique(posicoes: Sequence[tuple[int, str, tuple[float, ...]]],
                    pagina: int, x: float, y: float) -> str | None:
    """O bloco que um clique acha pelas posições do MuPDF (a regra que a prévia do H13 usa).

    O `element_positions` dá o bloco que passa de uma página só na primeira (medido: o bloco de
    três páginas vem na primeira, com o retângulo até 705 pt numa página de 559; o que mal passa
    vem com o retângulo dentro dela): nas seguintes, o texto acima do primeiro bloco que começa
    na página é a continuação do último bloco das anteriores. O clique fora de todo retângulo
    fica com o mais perto, até `FOLGA_DO_CLIQUE`.
    """
    dentro = [i for n, i, r in posicoes if n == pagina and r[0] <= x <= r[2] and r[1] <= y <= r[3]]
    if dentro:
        return dentro[-1]
    anteriores = [i for n, i, _ in posicoes if n < pagina]
    topo = min((r[1] for n, _, r in posicoes if n == pagina), default=math.inf)
    if anteriores and y < topo:
        return anteriores[-1]
    perto = [(max(r[0] - x, 0, x - r[2]) + max(r[1] - y, 0, y - r[3]), i)
             for n, i, r in posicoes if n == pagina]
    distancia, ident = min(perto, default=(math.inf, None))
    return ident if distancia <= FOLGA_DO_CLIQUE else None


def posicoes_no_mupdf(capitulo: Capitulo, *, sem_ids: bool = False) -> dict[str, Any]:
    """A cobertura do `element_positions` (os blocos com posição) e o acerto clique → bloco.

    Os 400 cliques (semente 42) caem no miolo de trechos de texto sorteados da página; o bloco
    que as posições dão (o que tem o retângulo que contém o clique) é conferido contra o bloco
    que tem aquele texto, achado pelo texto na ordem (independente das posições).
    """
    medido, ids = (capitulo, []) if sem_ids else _com_ids(capitulo)
    pdf_bytes, posicoes = _pagina_com_posicoes(medido.texto())
    # A cobertura conta os blocos que o MuPDF desenha (o `note-slot` escondido não tem posição).
    visiveis = [k for k, bloco in enumerate(capitulo.blocos) if _visivel(bloco)]
    alvos = {ids[k] for k in visiveis} if ids else set()
    com_posicao = {i for _, i, _ in posicoes if i in alvos}
    trechos = _trechos_com_bloco(pdf_bytes, medido)
    sorte = random.Random(SEMENTE)
    candidatos = [k for k, (_, _, bloco) in enumerate(trechos) if bloco is not None]
    cliques = [sorte.choice(candidatos) for _ in range(PONTOS)] if candidatos else []
    indice_do_id = {ident: k for k, ident in enumerate(ids)}
    dos_blocos = [(n, i, r) for n, i, r in posicoes if i in indice_do_id]
    acertos = 0
    for k in cliques:
        numero, (x0, y0, x1, y1), verdadeiro = trechos[k]
        achado = bloco_no_clique(dos_blocos, numero, (x0 + x1) / 2, y0 + 0.6 * (y1 - y0))
        acertos += achado is not None and indice_do_id[achado] == verdadeiro
    return {"blocos": len(visiveis), "escondidos": len(capitulo.blocos) - len(visiveis),
            "com_posicao": len(com_posicao),
            "cobertura": len(com_posicao) / len(visiveis) if visiveis else 0.0,
            "cliques": len(cliques), "acertos": acertos,
            "acerto": acertos / len(cliques) if cliques else 0.0, "sem_ids": sem_ids,
            "trechos_sem_bloco": sum(1 for _, _, b in trechos if b is None)}


def _memoria_mb(pid: int) -> float:
    """A memória privada (commit) do processo, em MB (o `GetProcessMemoryInfo` do psapi)."""
    import ctypes
    from ctypes import wintypes

    class Contadores(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    alca = kernel.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
    if not alca:
        return 0.0
    try:
        contadores = Contadores()
        contadores.cb = ctypes.sizeof(Contadores)
        if not psapi.GetProcessMemoryInfo(alca, ctypes.byref(contadores), contadores.cb):
            return 0.0
        return contadores.PrivateUsage / 2**20
    finally:
        kernel.CloseHandle(alca)


def medir_latencia_no_chromium(capitulo: Capitulo, pasta: Path, *,
                               edicoes: int = EDICOES_NO_CHROMIUM) -> dict[str, Any]:
    """O frio, a memória extra e o remendo no Chromium, num processo filho do ambiente de medição.

    O frio conta do lançamento do processo à primeira pintura do capítulo (o relógio de parede,
    dos dois lados): a importação do Qt, o perfil, a página, o carregamento e dois quadros.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    entrada, saida = pasta / "latencia_chromium.json", pasta / "resultado_latencia.json"
    sorte = random.Random(SEMENTE)
    remendos = []
    for _ in range(edicoes + 1):
        indice, novo = editar(capitulo, sorte)
        remendos.append({"indice": indice, "html": novo})
    entrada.write_text(json.dumps({"pagina": capitulo.texto(), "remendos": remendos},
                                  ensure_ascii=False), encoding="utf-8")
    python = python_do_webengine()
    if not python.is_file():
        raise FileNotFoundError(f"o ambiente de medição com o WebEngine não existe: {python}")
    lancado = time.time()
    processo = subprocess.run(  # noqa: S603 - o Python do ambiente de medição, com os nossos args
        [str(python), str(Path(__file__).resolve()), "--filho-latencia", str(entrada),
         str(saida)], capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=1800)
    (pasta / "latencia_chromium.log").write_text(processo.stdout + processo.stderr,
                                                 encoding="utf-8")
    if processo.returncode != 0 or not saida.is_file():
        raise RuntimeError(f"o processo do Chromium falhou ({processo.returncode}): "
                           f"{(processo.stderr or processo.stdout)[-600:]}")
    resultado = dict(json.loads(saida.read_text(encoding="utf-8")))
    resultado["frio_s"] = resultado.pop("pintado_em") - lancado
    return resultado


def filho_latencia(entrada: Path, saida: Path) -> int:
    """No ambiente de medição: o capítulo carregado (o frio), a memória, e cada remendo."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
    import editor_chromium_medicao as cm
    from sonda_webengine import processos_filhos

    dados = json.loads(entrada.read_text(encoding="utf-8"))
    antes = _memoria_mb(os.getpid())
    medidor = cm.Medidor()
    medidor.carregar(dados["pagina"], nome_da_pagina="pagina.html")
    pintado = time.time()
    medidor.esperar(500)  # a página assenta (o processo de renderização termina de subir)
    filhos = processos_filhos(os.getpid())
    memoria = {"hospedeiro_mb": _memoria_mb(os.getpid()) - antes,
               "filhos_mb": sum(_memoria_mb(pid) for pid, _ in filhos), "filhos": len(filhos),
               "nomes_dos_filhos": sorted({nome for _, nome in filhos})}
    tempos, na_pagina = [], []
    for vez, remendo in enumerate(dados["remendos"]):
        codigo = ("(function(){ const m = document.querySelector('main') || document.body;"
                  " const el = m.children[Math.min(" + str(remendo["indice"])
                  + ", m.children.length - 1)]; window.__pintado = 0;"
                  " const t = performance.now(); el.outerHTML = " + json.dumps(remendo["html"])
                  + "; requestAnimationFrame(() => requestAnimationFrame(() => {"
                  " window.__pintado = performance.now(); })); return t; })()")
        inicio = time.perf_counter()
        comeco = float(medidor.js(codigo))
        while True:
            pintou = medidor.js("window.__pintado || 0")
            if pintou:
                break
            medidor.esperar(1)
        if vez:  # o primeiro aquece
            tempos.append(1000 * (time.perf_counter() - inicio))
            na_pagina.append(float(pintou) - comeco)
    saida.write_text(json.dumps({
        "pintado_em": pintado, "memoria": memoria,
        "memoria_extra_mb": memoria["hospedeiro_mb"] + memoria["filhos_mb"],
        "remendos": len(tempos), "p50_ms": _percentil(tempos, 50), "p95_ms": _percentil(tempos, 95),
        "na_pagina_p95_ms": _percentil(na_pagina, 95),
        "tempos_ms": [round(t, 1) for t in tempos]}, ensure_ascii=False), encoding="utf-8")
    return 0


def latencia(saida: Path, ir_real: Path | None, *, sabotagem: str | None = None,
             sem_chromium: bool = False,
             edicoes: int | None = None) -> tuple[dict[str, bool], dict[str, Any]]:
    """A tarefa 2: a latência nos dois motores, as posições do MuPDF, o frio e a memória.

    O portão exige a cobertura das posições do MuPDF em 100 % no capítulo do PEDIDO; o resto
    (as latências, o acerto do clique, o frio, a memória: os critérios 2, 3 e 5 da D3) é
    publicado, e o veredito da D3 vai ao relatório.
    """
    caps = capitulos(ir_real)
    registro: dict[str, Any] = {"origem": caps["260kb"].origem, "sabotagem": sabotagem}
    registro["mupdf"] = {nome: latencia_no_mupdf(cap, edicoes or EDICOES_NO_MUPDF)
                         for nome, cap in caps.items()}
    registro["posicoes"] = posicoes_no_mupdf(caps["260kb"], sem_ids=sabotagem == "sem_ids")
    if not sem_chromium:
        registro["chromium"] = medir_latencia_no_chromium(
            caps["260kb"], saida / "chromium", edicoes=edicoes or EDICOES_NO_CHROMIUM)
        chromium = registro["chromium"]
        registro["d3"] = {
            "2_frio": chromium["frio_s"] <= ORCAMENTOS_DA_D3["frio_s"],
            "3_remendo": chromium["p95_ms"] <= ORCAMENTOS_DA_D3["remendo_p95_ms"],
            "5_memoria": chromium["memoria_extra_mb"] <= ORCAMENTOS_DA_D3["memoria_mb"]}
    posicoes = registro["posicoes"]
    do_pedido = caps["260kb"].origem.startswith("PEDIDO")
    exigencias = {
        f"posições: {posicoes['com_posicao']}/{posicoes['blocos']} blocos com posição no MuPDF "
        f"(a cobertura, 100 %); o clique acha o bloco em {posicoes['acertos']}/"
        f"{posicoes['cliques']}": posicoes["cobertura"] >= 1.0,
        f"latência: o capítulo de {caps['260kb'].kb:.0f} KB — {caps['260kb'].origem}":
            do_pedido,
    }
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "latencia.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    for nome, medida in registro["mupdf"].items():
        print(f"MuPDF {nome}: p50 {medida['p50_ms']:.0f} ms, p95 {medida['p95_ms']:.0f} ms "
              f"({medida['kb']} KB, {medida['paginas']} páginas"
              f"{', laço' if medida['laco'] else ''})")
    if "chromium" in registro:
        c = registro["chromium"]
        print(f"Chromium: frio {c['frio_s']:.2f} s, remendo p50 {c['p50_ms']:.0f} ms p95 "
              f"{c['p95_ms']:.0f} ms, memória extra {c['memoria_extra_mb']:.0f} MB — D3 "
              f"{registro['d3']}")
    return exigencias, registro


def _principal() -> Path:
    """O checkout principal (a árvore de trabalho acha o Sigil e o venv ao lado dele)."""
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--matriz", action="store_true")
    parser.add_argument("--hostil", action="store_true")
    parser.add_argument("--tamanhos", action="store_true")
    parser.add_argument("--latencia", action="store_true")
    parser.add_argument("--ir-real", type=Path)
    parser.add_argument("--sem-chromium", action="store_true",
                        help="a latência só no MuPDF (sem o ambiente de medição)")
    parser.add_argument("--edicoes", type=int,
                        help="as edições da latência (a rodada curta, que não mede)")
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--limite", type=int)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--filho-chromium", nargs=2, type=Path, metavar=("ENTRADA", "SAIDA"))
    parser.add_argument("--filho-hostil", nargs=2, type=Path, metavar=("ENTRADA", "SAIDA"))
    parser.add_argument("--filho-latencia", nargs=2, type=Path, metavar=("ENTRADA", "SAIDA"))
    args = parser.parse_args(argv)
    if args.filho_chromium:
        return filho_chromium(*args.filho_chromium)
    if args.filho_hostil:
        return filho_hostil(*args.filho_hostil)
    if args.filho_latencia:
        return filho_latencia(*args.filho_latencia)
    if args.saida is None:
        parser.error("--saida é obrigatório")
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    exigencias: dict[str, bool] = {}
    if args.matriz:
        exigencias.update(matriz(saida, limite=args.limite)[0])
    if args.hostil:
        exigencias.update(hostil(saida, sabotagem=args.sabotar)[0])
    if args.tamanhos:
        exigencias.update(tamanhos(saida)[0])
    if args.latencia:
        ir_real = args.ir_real if args.ir_real is None or args.ir_real.is_absolute() \
            else RAIZ / args.ir_real
        exigencias.update(latencia(saida, ir_real, sabotagem=args.sabotar,
                                   sem_chromium=args.sem_chromium, edicoes=args.edicoes)[0])
    if not exigencias:
        parser.error("diga o que medir: --matriz, --hostil, --tamanhos, --latencia")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


_ = tempfile  # a pasta de cada página do Chromium é a do arnês (`Medidor.carregar`)

if __name__ == "__main__":
    raise SystemExit(main())
