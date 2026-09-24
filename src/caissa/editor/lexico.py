"""O léxico do editor de código: uma linha e um estado entram, fichas e o estado seguinte saem.

Spec S5, D4; roadmap H2 (e H12, que faz do protótipo o componente). **Sem Qt** (R1.11): o realce
do widget pede a este módulo, linha a linha, e só pinta.

**Por que linha a linha, com estado.** O realce de um arquivo de 2 MB não pode ler o arquivo
inteiro a cada tecla: o `QSyntaxHighlighter` guarda um inteiro por bloco (a linha), e o realce
incremental relê só a linha que mudou — e as seguintes enquanto o estado do fim de cada uma mudar
(um `<!--` aberto muda o resto do arquivo; uma letra dentro de um parágrafo não muda nada). O
estado é esse inteiro: o **modo** em que a linha termina, mais duas marcas que a linha seguinte
precisa saber (dentro de `<style>`, dentro de `{ }` do CSS).

**O que conta como ficha** (`Classe`): o que o tema pinta de um jeito próprio. O resto da linha —
o texto do livro — não é ficha, e fica com a cor do texto.

**Nunca levanta.** Um arquivo mal formado é justamente o que o editor mais mostra (a pessoa está
no meio de uma tag); o léxico só decide cores, e qualquer entrada devolve fichas que cobrem
trechos válidos da linha.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Classe(StrEnum):
    """O papel de cada ficha — o tema escolhe a cor pelo papel (H12: `CODIGO_*`)."""

    DELIMITADOR = "delimitador"      # < > </ /> e o = do atributo
    TAG = "tag"                      # o nome do elemento
    ATRIBUTO = "atributo"
    VALOR = "valor"                  # o valor do atributo, com as aspas
    ENTIDADE = "entidade"            # &amp; &#8212; &#x2658;
    COMENTARIO = "comentario"        # <!-- … --> e /* … */
    CDATA = "cdata"
    DECLARACAO = "declaracao"        # <!DOCTYPE …>, <?xml …?>
    CSS_SELETOR = "css_seletor"
    CSS_PROPRIEDADE = "css_propriedade"
    CSS_VALOR = "css_valor"
    CSS_ARROBA = "css_arroba"        # @media, @page, @font-face
    CSS_CHAVE = "css_chave"          # { } ; :


class Modo(IntEnum):
    """O modo em que a linha termina: os quatro bits de baixo do estado."""

    TEXTO = 0
    TAG = 1                          # dentro de uma tag, depois do nome
    ASPAS_DUPLAS = 2                 # dentro de um valor "…"
    ASPAS_SIMPLES = 3                # dentro de um valor '…'
    COMENTARIO = 4                   # dentro de <!-- … -->
    CDATA = 5
    DECLARACAO = 6                   # dentro de <! … > ou <? … ?>
    CSS = 7                          # conteúdo de <style>, ou um arquivo .css
    CSS_COMENTARIO = 8               # dentro de /* … */
    BRUTO = 9                        # conteúdo de <script>: não é realçado até </script>


#: Marcas do estado, acima dos quatro bits do modo.
EM_STYLE = 1 << 4                    # a tag aberta, ou o CSS, é de um <style>
EM_BLOCO = 1 << 5                    # o CSS está dentro de { … } de declarações
EM_SCRIPT = 1 << 6                   # a tag aberta é de um <script>
EM_GRUPO = 1 << 7                    # o CSS está dentro de { … } de um @media/@supports
GRUPO_PENDENTE = 1 << 8              # veio um @media: a próxima { abre um grupo, não declarações
_MASCARA_DO_MODO = 0b1111

#: As regras-@ cujo bloco contém regras (seletor { … }), e não declarações.
_REGRAS_DE_GRUPO = frozenset({"@media", "@supports", "@layer", "@container", "@document"})

ESTADO_HTML = int(Modo.TEXTO)
ESTADO_CSS = int(Modo.CSS)


def estado_inicial(tipo: str) -> int:
    """O estado da primeira linha de um arquivo: `"css"` para folhas, qualquer outro é XHTML."""
    return ESTADO_CSS if tipo.lower().lstrip(".") == "css" else ESTADO_HTML


def modo(estado: int) -> Modo:
    return Modo(estado & _MASCARA_DO_MODO)


@dataclass(frozen=True, slots=True)
class Ficha:
    inicio: int
    fim: int
    classe: Classe

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


_NOME = re.compile(r"[A-Za-z_:][-A-Za-z0-9_:.]*")
_ESPACO = re.compile(r"\s+")
_ENTIDADE = re.compile(r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")
_FECHA_STYLE = re.compile(r"</style\s*>", re.IGNORECASE)
_FECHA_SCRIPT = re.compile(r"</script\s*>", re.IGNORECASE)
_ARROBA = re.compile(r"@[-A-Za-z]+")
_PROPRIEDADE = re.compile(r"--?[A-Za-z][-A-Za-z0-9_]*|[A-Za-z][-A-Za-z0-9_]*")


def tokens(linha: str, estado: int) -> tuple[list[Ficha], int]:  # noqa: PLR0912 - um ramo por modo
    """As fichas de `linha`, começando em `estado`, e o estado em que ela termina."""
    fichas: list[Ficha] = []
    i, n = 0, len(linha)
    marcas = estado & ~_MASCARA_DO_MODO
    atual = modo(estado)
    while i < n:
        if atual is Modo.TEXTO:
            i, atual, marcas = _texto(linha, i, fichas, marcas)
        elif atual is Modo.TAG:
            i, atual, marcas = _tag(linha, i, fichas, marcas)
        elif atual in (Modo.ASPAS_DUPLAS, Modo.ASPAS_SIMPLES):
            aspa = '"' if atual is Modo.ASPAS_DUPLAS else "'"
            fim = linha.find(aspa, i)
            if fim < 0:
                fichas.append(Ficha(i, n, Classe.VALOR))
                i = n
            else:
                fichas.append(Ficha(i, fim + 1, Classe.VALOR))
                i, atual = fim + 1, Modo.TAG
        elif atual is Modo.COMENTARIO:
            i, atual = _ate(linha, i, "-->", Classe.COMENTARIO, fichas, Modo.TEXTO, atual)
        elif atual is Modo.CDATA:
            i, atual = _ate(linha, i, "]]>", Classe.CDATA, fichas, Modo.TEXTO, atual)
        elif atual is Modo.DECLARACAO:
            i, atual = _ate(linha, i, ">", Classe.DECLARACAO, fichas, Modo.TEXTO, atual)
        elif atual is Modo.CSS:
            i, atual, marcas = _css(linha, i, fichas, marcas)
        elif atual is Modo.CSS_COMENTARIO:
            i, atual, marcas = _comentario_css(linha, i, fichas, marcas)
        else:                                                      # BRUTO
            achado = _FECHA_SCRIPT.search(linha, i)
            if achado is None:
                i = n
            else:
                i, atual, marcas = achado.start(), Modo.TEXTO, marcas & ~EM_SCRIPT
    return fichas, int(atual) | marcas


def _ate(linha: str, i: int, fecho: str, classe: Classe, fichas: list[Ficha],
         depois: Modo, atual: Modo) -> tuple[int, Modo]:
    """Uma ficha até `fecho` (incluído) e o modo `depois`; sem fecho, a linha inteira."""
    fim = linha.find(fecho, i)
    if fim < 0:
        fichas.append(Ficha(i, len(linha), classe))
        return len(linha), atual
    fichas.append(Ficha(i, fim + len(fecho), classe))
    return fim + len(fecho), depois


def _comentario_css(linha: str, i: int, fichas: list[Ficha], marcas: int,
                    desde: int | None = None) -> tuple[int, Modo, int]:
    """O fim de `/* … */` — ou o `</style>`, que fecha o elemento até dentro do comentário.

    `desde` é onde procurar o `*/`: logo depois do `/*` quando o comentário começa nesta linha
    (o `*` de `/*/` não fecha nada).
    """
    fim = linha.find("*/", i if desde is None else desde)
    if marcas & EM_STYLE:
        fecho = _FECHA_STYLE.search(linha, i)
        if fecho and (fim < 0 or fecho.start() < fim):
            if fecho.start() > i:
                fichas.append(Ficha(i, fecho.start(), Classe.COMENTARIO))
            return fecho.start(), Modo.CSS, marcas
    if fim < 0:
        fichas.append(Ficha(i, len(linha), Classe.COMENTARIO))
        return len(linha), Modo.CSS_COMENTARIO, marcas
    fichas.append(Ficha(i, fim + 2, Classe.COMENTARIO))
    return fim + 2, Modo.CSS, marcas


def _texto(  # noqa: PLR0911 - uma saída por forma de marcação lê melhor que uma tabela
    linha: str, i: int, fichas: list[Ficha], marcas: int,
) -> tuple[int, Modo, int]:
    n = len(linha)
    menor = linha.find("<", i)
    ecomercial = linha.find("&", i)
    proximo = min(p for p in (menor, ecomercial, n) if p >= 0)
    if proximo == n:
        return n, Modo.TEXTO, marcas
    if proximo == ecomercial and (menor < 0 or ecomercial < menor):
        achada = _ENTIDADE.match(linha, ecomercial)
        if achada:
            fichas.append(Ficha(ecomercial, achada.end(), Classe.ENTIDADE))
            return achada.end(), Modo.TEXTO, marcas
        return ecomercial + 1, Modo.TEXTO, marcas
    j = menor
    if linha.startswith("<!--", j):
        fichas.append(Ficha(j, j + 4, Classe.COMENTARIO))
        return _continuar_comentario(linha, j + 4, fichas, marcas)
    if linha.startswith("<![CDATA[", j):
        fichas.append(Ficha(j, j + 9, Classe.CDATA))
        return j + 9, Modo.CDATA, marcas
    if linha.startswith("<!", j) or linha.startswith("<?", j):
        fichas.append(Ficha(j, j + 2, Classe.DECLARACAO))
        return j + 2, Modo.DECLARACAO, marcas
    fechando = linha.startswith("</", j)
    inicio_do_nome = j + (2 if fechando else 1)
    nome = _NOME.match(linha, inicio_do_nome)
    if nome is None:
        return j + 1, Modo.TEXTO, marcas             # um «<» solto é texto
    fichas.append(Ficha(j, inicio_do_nome, Classe.DELIMITADOR))
    fichas.append(Ficha(nome.start(), nome.end(), Classe.TAG))
    elemento = nome.group().lower()
    if not fechando and elemento == "style":
        marcas |= EM_STYLE
    elif not fechando and elemento == "script":
        marcas |= EM_SCRIPT
    return nome.end(), Modo.TAG, marcas


def _continuar_comentario(linha: str, i: int, fichas: list[Ficha],
                          marcas: int) -> tuple[int, Modo, int]:
    fim = linha.find("-->", i)
    if fim < 0:
        fichas.append(Ficha(i, len(linha), Classe.COMENTARIO))
        return len(linha), Modo.COMENTARIO, marcas
    fichas.append(Ficha(i, fim + 3, Classe.COMENTARIO))
    return fim + 3, Modo.TEXTO, marcas


def _tag(  # noqa: PLR0911 - uma saída por ficha possível dentro de uma tag
    linha: str, i: int, fichas: list[Ficha], marcas: int,
) -> tuple[int, Modo, int]:
    espaco = _ESPACO.match(linha, i)
    if espaco:
        return espaco.end(), Modo.TAG, marcas
    caractere = linha[i]
    if linha.startswith("/>", i):
        fichas.append(Ficha(i, i + 2, Classe.DELIMITADOR))
        return i + 2, Modo.TEXTO, marcas & ~(EM_STYLE | EM_SCRIPT)
    if caractere == ">":
        fichas.append(Ficha(i, i + 1, Classe.DELIMITADOR))
        if marcas & EM_STYLE:
            return i + 1, Modo.CSS, (marcas | EM_STYLE) & ~EM_BLOCO
        if marcas & EM_SCRIPT:
            return i + 1, Modo.BRUTO, marcas
        return i + 1, Modo.TEXTO, marcas
    if caractere == "=":
        fichas.append(Ficha(i, i + 1, Classe.DELIMITADOR))
        return i + 1, Modo.TAG, marcas
    if caractere in "\"'":
        fim = linha.find(caractere, i + 1)
        if fim < 0:
            fichas.append(Ficha(i, len(linha), Classe.VALOR))
            aberto = Modo.ASPAS_DUPLAS if caractere == '"' else Modo.ASPAS_SIMPLES
            return len(linha), aberto, marcas
        fichas.append(Ficha(i, fim + 1, Classe.VALOR))
        return fim + 1, Modo.TAG, marcas
    nome = _NOME.match(linha, i)
    if nome:
        fichas.append(Ficha(nome.start(), nome.end(), Classe.ATRIBUTO))
        return nome.end(), Modo.TAG, marcas
    if caractere == "<":                               # a tag nunca fechou: começa outra
        return i, Modo.TEXTO, marcas & ~(EM_STYLE | EM_SCRIPT)
    return i + 1, Modo.TAG, marcas                     # um caractere estranho dentro da tag


def _css(  # noqa: PLR0911 - uma saída por forma de CSS
    linha: str, i: int, fichas: list[Ficha], marcas: int,
) -> tuple[int, Modo, int]:
    """O CSS de um `<style>` (marca EM_STYLE) ou de uma folha; EM_BLOCO dentro de `{ }`."""
    if marcas & EM_STYLE:
        fecho = _FECHA_STYLE.match(linha, i)
        if fecho:
            fichas.append(Ficha(i, i + 2, Classe.DELIMITADOR))
            fichas.append(Ficha(i + 2, i + 7, Classe.TAG))
            fichas.append(Ficha(fecho.end() - 1, fecho.end(), Classe.DELIMITADOR))
            return fecho.end(), Modo.TEXTO, marcas & ~(EM_STYLE | EM_BLOCO | EM_GRUPO
                                                       | GRUPO_PENDENTE)
    espaco = _ESPACO.match(linha, i)
    if espaco:
        return espaco.end(), Modo.CSS, marcas
    if linha.startswith("/*", i):
        return _comentario_css(linha, i, fichas, marcas, desde=i + 2)
    caractere = linha[i]
    if caractere == "{":
        fichas.append(Ficha(i, i + 1, Classe.CSS_CHAVE))
        if marcas & GRUPO_PENDENTE:
            return i + 1, Modo.CSS, (marcas | EM_GRUPO) & ~GRUPO_PENDENTE
        return i + 1, Modo.CSS, marcas | EM_BLOCO
    if caractere == "}":
        fichas.append(Ficha(i, i + 1, Classe.CSS_CHAVE))
        if marcas & EM_BLOCO:
            return i + 1, Modo.CSS, marcas & ~EM_BLOCO
        return i + 1, Modo.CSS, marcas & ~EM_GRUPO
    if not marcas & EM_BLOCO:
        return _fora_do_bloco(linha, i, fichas, marcas)
    return _dentro_do_bloco(linha, i, fichas, marcas)


def _fim_css(linha: str, i: int, paradas: str, marcas: int) -> int:
    """Onde termina um trecho de CSS: numa das `paradas`, num comentário, ou no `</style>`."""
    n = len(linha)
    j = i
    while j < n:
        if linha[j] in paradas or linha.startswith("/*", j):
            return j
        if marcas & EM_STYLE and linha[j] == "<" and _FECHA_STYLE.match(linha, j):
            return j
        if linha[j] in "\"'":
            fecho = linha.find(linha[j], j + 1)
            j = n if fecho < 0 else fecho + 1
            continue
        j += 1
    return n


def _fora_do_bloco(linha: str, i: int, fichas: list[Ficha], marcas: int) -> tuple[int, Modo, int]:
    arroba = _ARROBA.match(linha, i)
    if arroba:
        fichas.append(Ficha(i, arroba.end(), Classe.CSS_ARROBA))
        if arroba.group().lower() in _REGRAS_DE_GRUPO:
            marcas |= GRUPO_PENDENTE
        return arroba.end(), Modo.CSS, marcas
    if linha[i] == ";":
        fichas.append(Ficha(i, i + 1, Classe.CSS_CHAVE))
        return i + 1, Modo.CSS, marcas & ~GRUPO_PENDENTE
    fim = _fim_css(linha, i, "{;}", marcas)
    trecho = linha[i:fim].rstrip()
    if trecho:
        # A condição de um @media (`print and (min-width: 30em)`) não é seletor, é da regra.
        classe = Classe.CSS_ARROBA if marcas & GRUPO_PENDENTE else Classe.CSS_SELETOR
        fichas.append(Ficha(i, i + len(trecho), classe))
    return max(fim, i + 1), Modo.CSS, marcas


def _dentro_do_bloco(linha: str, i: int, fichas: list[Ficha],
                     marcas: int) -> tuple[int, Modo, int]:
    caractere = linha[i]
    if caractere in ":;":
        fichas.append(Ficha(i, i + 1, Classe.CSS_CHAVE))
        if caractere == ":":
            fim = _fim_css(linha, i + 1, ";}", marcas)
            inicio = i + 1 + (len(linha[i + 1:fim]) - len(linha[i + 1:fim].lstrip()))
            trecho = linha[inicio:fim].rstrip()
            if trecho:
                fichas.append(Ficha(inicio, inicio + len(trecho), Classe.CSS_VALOR))
            return max(fim, i + 1), Modo.CSS, marcas
        return i + 1, Modo.CSS, marcas
    propriedade = _PROPRIEDADE.match(linha, i)
    if propriedade:
        fichas.append(Ficha(i, propriedade.end(), Classe.CSS_PROPRIEDADE))
        return propriedade.end(), Modo.CSS, marcas
    arroba = _ARROBA.match(linha, i)
    if arroba:                                        # @page dentro de @media, por exemplo
        fichas.append(Ficha(i, arroba.end(), Classe.CSS_ARROBA))
        return arroba.end(), Modo.CSS, marcas
    return i + 1, Modo.CSS, marcas


def tokens_do_texto(texto: str, tipo: str = "xhtml") -> list[list[Ficha]]:
    """As fichas de cada linha de um texto inteiro — o caminho dos testes e do realce frio."""
    estado = estado_inicial(tipo)
    saida = []
    for linha in texto.split("\n"):
        fichas, estado = tokens(linha, estado)
        saida.append(fichas)
    return saida
