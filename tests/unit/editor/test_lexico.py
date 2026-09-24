"""O léxico do editor de código (passo H2): cada caso escrito à mão, com as fichas esperadas.

A tabela é a especificação do realce: uma linha (ou várias, quando o caso é a fronteira entre
linhas) e as fichas que ela dá, como pares `(trecho, classe)`. O resto do texto — o livro — não é
ficha. Os casos de fronteira de linha são os que o realce incremental depende: o estado com que
uma linha termina decide a cor da seguinte.
"""

from __future__ import annotations

import random

import pytest

from caissa.editor.lexico import (
    EM_BLOCO,
    EM_STYLE,
    ESTADO_CSS,
    ESTADO_HTML,
    Classe,
    Modo,
    estado_inicial,
    modo,
    tokens,
    tokens_do_texto,
)

D, T, A, V = Classe.DELIMITADOR, Classe.TAG, Classe.ATRIBUTO, Classe.VALOR
E, C, CD, DC = Classe.ENTIDADE, Classe.COMENTARIO, Classe.CDATA, Classe.DECLARACAO
SEL, PROP, VAL = Classe.CSS_SELETOR, Classe.CSS_PROPRIEDADE, Classe.CSS_VALOR
AR, CH = Classe.CSS_ARROBA, Classe.CSS_CHAVE


def _pares(texto: str, tipo: str = "xhtml") -> list[list[tuple[str, Classe]]]:
    linhas = texto.split("\n")
    return [[(linha[f.inicio:f.fim], f.classe) for f in fichas]
            for linha, fichas in zip(linhas, tokens_do_texto(texto, tipo), strict=True)]


CASOS: list[tuple[str, str, str, list[list[tuple[str, Classe]]]]] = [
    # --- HTML, uma linha ------------------------------------------------------------------
    ("texto puro", "xhtml", "O rei vai a f7.", [[]]),
    ("figurina no texto", "xhtml", "1.♘f3 d5 2.♗b5+", [[]]),
    ("tag de abertura", "xhtml", "<p>", [[("<", D), ("p", T), (">", D)]]),
    ("tag de fecho", "xhtml", "</p>", [[("</", D), ("p", T), (">", D)]]),
    ("tag com texto", "xhtml", "<p>O rei.</p>",
     [[("<", D), ("p", T), (">", D), ("</", D), ("p", T), (">", D)]]),
    ("atributo com aspas duplas", "xhtml", '<p class="cb-movetext">',
     [[("<", D), ("p", T), ("class", A), ("=", D), ('"cb-movetext"', V), (">", D)]]),
    ("atributo com aspas simples", "xhtml", "<p id='p55-3'>",
     [[("<", D), ("p", T), ("id", A), ("=", D), ("'p55-3'", V), (">", D)]]),
    ("dois atributos", "xhtml", '<a href="#p55-3" id="r1">',
     [[("<", D), ("a", T), ("href", A), ("=", D), ('"#p55-3"', V), ("id", A), ("=", D),
       ('"r1"', V), (">", D)]]),
    ("atributo com espaço em volta do =", "xhtml", '<p class = "x">',
     [[("<", D), ("p", T), ("class", A), ("=", D), ('"x"', V), (">", D)]]),
    ("atributo sem valor", "xhtml", "<input disabled>",
     [[("<", D), ("input", T), ("disabled", A), (">", D)]]),
    ("tag vazia com barra", "xhtml", "<br/>", [[("<", D), ("br", T), ("/>", D)]]),
    ("imagem vazia com atributos", "xhtml", '<img src="../Images/dg_1.svg" alt="Diagrama 1"/>',
     [[("<", D), ("img", T), ("src", A), ("=", D), ('"../Images/dg_1.svg"', V), ("alt", A),
       ("=", D), ('"Diagrama 1"', V), ("/>", D)]]),
    ("maiúsculas", "xhtml", '<P CLASS="x">', [[("<", D), ("P", T), ("CLASS", A), ("=", D),
                                              ('"x"', V), (">", D)]]),
    ("tag com prefixo", "xhtml", '<epub:switch id="s">',
     [[("<", D), ("epub:switch", T), ("id", A), ("=", D), ('"s"', V), (">", D)]]),
    ("atributo com prefixo", "xhtml", '<span epub:type="pagebreak"/>',
     [[("<", D), ("span", T), ("epub:type", A), ("=", D), ('"pagebreak"', V), ("/>", D)]]),
    ("atributos data do contrato", "xhtml",
     '<figure class="cb-diagram" data-fen="8/8/8/8/8/8/8/K6k w - - 0 1" data-stm="w">',
     [[("<", D), ("figure", T), ("class", A), ("=", D), ('"cb-diagram"', V), ("data-fen", A),
       ("=", D), ('"8/8/8/8/8/8/8/K6k w - - 0 1"', V), ("data-stm", A), ("=", D), ('"w"', V),
       (">", D)]]),
    ("span de peça", "xhtml", '<span class="cb-piece" data-piece="N">♘</span>',
     [[("<", D), ("span", T), ("class", A), ("=", D), ('"cb-piece"', V), ("data-piece", A),
       ("=", D), ('"N"', V), (">", D), ("</", D), ("span", T), (">", D)]]),
    ("entidade nomeada", "xhtml", "a &amp; b", [[("&amp;", E)]]),
    ("entidade decimal", "xhtml", "fim&#8212;", [[("&#8212;", E)]]),
    ("entidade hexadecimal", "xhtml", "&#x2658;f3", [[("&#x2658;", E)]]),
    ("& solto não é entidade", "xhtml", "Tom & Jerry", [[]]),
    ("& sem ponto e vírgula", "xhtml", "a &amp b", [[]]),
    ("< solto antes de número", "xhtml", "1 < 2", [[]]),
    ("< no fim da linha", "xhtml", "texto <", [[]]),
    ("comentário numa linha", "xhtml", "<!-- nota -->", [[("<!--", C), (" nota -->", C)]]),
    ("comentário vazio", "xhtml", "<!---->", [[("<!--", C), ("-->", C)]]),
    ("comentário entre tags", "xhtml", "<p><!-- x --></p>",
     [[("<", D), ("p", T), (">", D), ("<!--", C), (" x -->", C), ("</", D), ("p", T),
       (">", D)]]),
    ("doctype", "xhtml", "<!DOCTYPE html>", [[("<!", DC), ("DOCTYPE html>", DC)]]),
    ("declaração xml", "xhtml", '<?xml version="1.0" encoding="utf-8"?>',
     [[("<?", DC), ('xml version="1.0" encoding="utf-8"?>', DC)]]),
    ("cdata numa linha", "xhtml", "<![CDATA[ a < b ]]>", [[("<![CDATA[", CD), (" a < b ]]>", CD)]]),
    ("link de volta da nota", "xhtml", '<a href="#n1">↩</a>',
     [[("<", D), ("a", T), ("href", A), ("=", D), ('"#n1"', V), (">", D), ("</", D), ("a", T),
       (">", D)]]),
    ("tag que nunca fecha antes de outra", "xhtml", '<p class="x" <b>',
     [[("<", D), ("p", T), ("class", A), ("=", D), ('"x"', V), ("<", D), ("b", T), (">", D)]]),
    # --- HTML, fronteira de linha ---------------------------------------------------------
    ("comentário em três linhas", "xhtml", "<!-- começa\ncontinua\ntermina --> <p>",
     [[("<!--", C), (" começa", C)], [("continua", C)],
      [("termina -->", C), ("<", D), ("p", T), (">", D)]]),
    ("cdata em duas linhas", "xhtml", "<![CDATA[ a\nb ]]>x",
     [[("<![CDATA[", CD), (" a", CD)], [("b ]]>", CD)]]),
    ("tag aberta de uma linha para a outra", "xhtml",
     '<figure class="cb-diagram"\n  data-fen="8/8/8/8/8/8/8/K6k w - - 0 1">',
     [[("<", D), ("figure", T), ("class", A), ("=", D), ('"cb-diagram"', V)],
      [("data-fen", A), ("=", D), ('"8/8/8/8/8/8/8/K6k w - - 0 1"', V), (">", D)]]),
    ("valor aberto de uma linha para a outra", "xhtml", '<a title="primeira\nsegunda">x',
     [[("<", D), ("a", T), ("title", A), ("=", D), ('"primeira', V)],
      [('segunda"', V), (">", D)]]),
    ("valor com aspas simples aberto", "xhtml", "<a title='um\ndois'>",
     [[("<", D), ("a", T), ("title", A), ("=", D), ("'um", V)], [("dois'", V), (">", D)]]),
    ("nome no fim da linha, atributos na seguinte", "xhtml", '<p\nclass="x">',
     [[("<", D), ("p", T)], [("class", A), ("=", D), ('"x"', V), (">", D)]]),
    ("doctype em duas linhas", "xhtml", "<!DOCTYPE html\n>", [[("<!", DC), ("DOCTYPE html", DC)],
                                                          [(">", DC)]]),
    # --- <style> --------------------------------------------------------------------------
    ("style numa linha", "xhtml", "<style>p { color: red; }</style>",
     [[("<", D), ("style", T), (">", D), ("p", SEL), ("{", CH), ("color", PROP), (":", CH),
       ("red", VAL), (";", CH), ("}", CH), ("</", D), ("style", T), (">", D)]]),
    ("style em várias linhas", "xhtml",
     "<style>\np.cb-caption {\n  font-style: italic;\n}\n</style>",
     [[("<", D), ("style", T), (">", D)], [("p.cb-caption", SEL), ("{", CH)],
      [("font-style", PROP), (":", CH), ("italic", VAL), (";", CH)], [("}", CH)],
      [("</", D), ("style", T), (">", D)]]),
    ("style com atributo", "xhtml", '<style type="text/css">p{}</style>',
     [[("<", D), ("style", T), ("type", A), ("=", D), ('"text/css"', V), (">", D), ("p", SEL),
       ("{", CH), ("}", CH), ("</", D), ("style", T), (">", D)]]),
    ("</style> dentro do comentário CSS fecha o elemento", "xhtml",
     "<style>/* a </style>",
     [[("<", D), ("style", T), (">", D), ("/* a ", C), ("</", D), ("style", T), (">", D)]]),
    ("style vazio com barra não abre CSS", "xhtml", "<style/>p { }",
     [[("<", D), ("style", T), ("/>", D)]]),
    ("elemento styles não é style", "xhtml", "<styles>p { }",
     [[("<", D), ("styles", T), (">", D)]]),
    # --- <script> -------------------------------------------------------------------------
    ("script numa linha", "xhtml", "<script>if (a < b) {}</script>",
     [[("<", D), ("script", T), (">", D), ("</", D), ("script", T), (">", D)]]),
    ("script em duas linhas", "xhtml", "<script>\nvar x = '<p>';\n</script>",
     [[("<", D), ("script", T), (">", D)], [], [("</", D), ("script", T), (">", D)]]),
    # --- CSS ------------------------------------------------------------------------------
    ("regra simples", "css", "p { margin: 0 }",
     [[("p", SEL), ("{", CH), ("margin", PROP), (":", CH), ("0", VAL), ("}", CH)]]),
    ("seletor com classe e pseudo", "css", "a.cb-move:focus {",
     [[("a.cb-move:focus", SEL), ("{", CH)]]),
    ("seletor com vírgula", "css", "h1, h2 {", [[("h1, h2", SEL), ("{", CH)]]),
    ("variável em :root", "css", ":root { --cor-texto: #222; }",
     [[(":root", SEL), ("{", CH), ("--cor-texto", PROP), (":", CH), ("#222", VAL), (";", CH),
       ("}", CH)]]),
    ("valor com var()", "css", "p { color: var(--cor-texto); }",
     [[("p", SEL), ("{", CH), ("color", PROP), (":", CH), ("var(--cor-texto)", VAL), (";", CH),
       ("}", CH)]]),
    ("valor com ponto e vírgula entre aspas", "css", 'p::after { content: "a;b"; }',
     [[("p::after", SEL), ("{", CH), ("content", PROP), (":", CH), ('"a;b"', VAL), (";", CH),
       ("}", CH)]]),
    ("font-face", "css", '@font-face { font-family: "Merida"; }',
     [[("@font-face", AR), ("{", CH), ("font-family", PROP), (":", CH), ('"Merida"', VAL),
       (";", CH), ("}", CH)]]),
    ("url", "css", 'src: url("../Fonts/merida.ttf");',
     [[("src: url(\"../Fonts/merida.ttf\")", SEL), (";", CH)]]),
    ("import", "css", '@import url("tema.css");',
     [[("@import", AR), ('url("tema.css")', SEL), (";", CH)]]),
    ("media com regra dentro", "css", "@media print {\n  p { color: black; }\n}",
     [[("@media", AR), ("print", AR), ("{", CH)],
      [("p", SEL), ("{", CH), ("color", PROP), (":", CH), ("black", VAL), (";", CH), ("}", CH)],
      [("}", CH)]]),
    ("media com condição", "css", "@media (min-width: 30em) { h1 { margin: 0 } }",
     [[("@media", AR), ("(min-width: 30em)", AR), ("{", CH), ("h1", SEL), ("{", CH),
       ("margin", PROP), (":", CH), ("0", VAL), ("}", CH), ("}", CH)]]),
    ("page", "css", "@page { margin: 2cm; }",
     [[("@page", AR), ("{", CH), ("margin", PROP), (":", CH), ("2cm", VAL), (";", CH),
       ("}", CH)]]),
    ("comentário CSS numa linha", "css", "/* tema */ p {",
     [[("/* tema */", C), ("p", SEL), ("{", CH)]]),
    ("comentário CSS em duas linhas", "css", "/* a\nb */ p {",
     [[("/* a", C)], [("b */", C), ("p", SEL), ("{", CH)]]),
    ("barra estrela barra não fecha", "css", "/*/ ainda comentário */ p",
     [[("/*/ ainda comentário */", C), ("p", SEL)]]),
    ("propriedade numa linha, valor na outra", "css", "p {\n  color\n  : red;\n}",
     [[("p", SEL), ("{", CH)], [("color", PROP)], [(":", CH), ("red", VAL), (";", CH)],
      [("}", CH)]]),
    ("important", "css", "p { color: red !important; }",
     [[("p", SEL), ("{", CH), ("color", PROP), (":", CH), ("red !important", VAL), (";", CH),
       ("}", CH)]]),
    ("declaração vazia", "css", "p { }", [[("p", SEL), ("{", CH), ("}", CH)]]),
]


@pytest.mark.parametrize(("tipo", "texto", "esperado"),
                         [(c[1], c[2], c[3]) for c in CASOS], ids=[c[0] for c in CASOS])
def test_as_fichas_de_cada_caso(tipo: str, texto: str,
                                esperado: list[list[tuple[str, Classe]]]) -> None:
    assert _pares(texto, tipo) == esperado


def test_a_tabela_tem_ao_menos_sessenta_casos() -> None:
    assert len(CASOS) >= 60


def test_estados_de_fim_de_linha() -> None:
    assert tokens("<p>O rei.</p>", ESTADO_HTML)[1] == ESTADO_HTML
    assert modo(tokens("<!-- aberto", ESTADO_HTML)[1]) is Modo.COMENTARIO
    assert modo(tokens('<a title="aberto', ESTADO_HTML)[1]) is Modo.ASPAS_DUPLAS
    assert modo(tokens("<p", ESTADO_HTML)[1]) is Modo.TAG
    fim = tokens("<style>p {", ESTADO_HTML)[1]
    assert modo(fim) is Modo.CSS
    assert fim & EM_STYLE
    assert fim & EM_BLOCO
    assert tokens("</style>", fim)[1] == ESTADO_HTML
    assert modo(tokens("/* a", ESTADO_CSS)[1]) is Modo.CSS_COMENTARIO


def test_o_estado_inicial_pelo_tipo() -> None:
    assert estado_inicial("css") == ESTADO_CSS
    assert estado_inicial(".CSS") == ESTADO_CSS
    assert estado_inicial("xhtml") == ESTADO_HTML
    assert estado_inicial("html") == ESTADO_HTML


def test_o_estado_cabe_num_inteiro_de_bloco() -> None:
    """O `QTextBlock.setUserState` guarda um int; -1 é «sem estado» para o Qt."""
    estados = set()
    for texto, tipo in (("<style>@media print {", "xhtml"), ("<script>", "xhtml"),
                        ('<a title="x', "xhtml"), ("/* a", "css")):
        estados.add(tokens(texto, estado_inicial(tipo))[1])
    assert all(0 <= e < 2**16 for e in estados)


def test_qualquer_linha_da_fichas_validas_e_em_ordem() -> None:
    """Nunca levanta; as fichas não se sobrepõem, vêm em ordem e cabem na linha."""
    sorteio = random.Random(42)
    alfabeto = '<>/="\'!-?[]&;#{}:*@ abcdefgpxyz0123♘♗\t'
    estados = [ESTADO_HTML, ESTADO_CSS]
    for _ in range(2000):
        linha = "".join(sorteio.choice(alfabeto) for _ in range(sorteio.randrange(60)))
        estado = sorteio.choice(estados)
        fichas, novo = tokens(linha, estado)
        estados.append(novo)
        fim_anterior = 0
        for ficha in fichas:
            assert 0 <= ficha.inicio < ficha.fim <= len(linha), (linha, ficha)
            assert ficha.inicio >= fim_anterior, (linha, fichas)
            fim_anterior = ficha.fim
        estados = estados[-50:]


def test_o_realce_de_um_capitulo_grande_e_linear() -> None:
    """Um capítulo de ~260 KB (o do portão de latência) em um passe, sem estado explodindo."""
    paragrafo = ('<p class="cb-movetext" id="p55-3">1.♘f3 d5 2.g3 &amp; '
                 '<span class="cb-piece" data-piece="N">♘</span> <!-- nota --></p>')
    texto = "\n".join([paragrafo] * 2200)
    assert len(texto.encode("utf-8")) > 250_000
    linhas = tokens_do_texto(texto)
    assert len(linhas) == 2200
    assert all(len(f) == len(linhas[0]) for f in linhas)
