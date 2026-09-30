r"""Os motores de pré-visualização, medidos — o passo H1 do Editor HTML/CSS (tarefas 1 e 4).

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

Uso::

    & $PY benchmarks\editor_motores.py --matriz --saida benchmarks\reports\editor\h1\matriz
    & $PY benchmarks\editor_motores.py --matriz --limite 8 --saida <pasta>   (a rodada curta)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
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
SABOTAGENS = ("sem_interceptador", "sem_guarda_de_rede")
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
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--limite", type=int)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--filho-chromium", nargs=2, type=Path, metavar=("ENTRADA", "SAIDA"))
    parser.add_argument("--filho-hostil", nargs=2, type=Path, metavar=("ENTRADA", "SAIDA"))
    args = parser.parse_args(argv)
    if args.filho_chromium:
        return filho_chromium(*args.filho_chromium)
    if args.filho_hostil:
        return filho_hostil(*args.filho_hostil)
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
    if not exigencias:
        parser.error("diga o que medir: --matriz, --hostil, --tamanhos")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


_ = tempfile  # a pasta de cada página do Chromium é a do arnês (`Medidor.carregar`)

if __name__ == "__main__":
    raise SystemExit(main())
