# Contrato de Marcação do Caissa, v1

> **Data:** 2026-09-24 · **Versão:** 1 · **Normativo.** Passo H3 do `EDITOR_HTML_CSS_ROADMAP.md`;
> governa o perfil legível do motor HTML (H5), a validação (H10), os temas (H19) e a exportação
> (H24). Decisão: spec D2 (ADR-0011), com o Q3 respondido «sim» em 2026-09-24.
>
> **Origem:** o contrato `cb-*` do ChessBook Studio (o CB, `..\Sigil-master\chessbook\MARKUP.md`,
> GPLv3), absorvido **inteiro**, mais as extensões da spec S4. O texto abaixo o reescreve em
> português; as classes e os atributos são os mesmos, sem renomear nenhum.
>
> **Fixtures:** `tests/fixtures/editor/contrato/` (§11). **Instrumento:**
> `benchmarks/editor_contrato.py`.

---

## 1. O que é

É o XHTML que o Editor HTML/CSS gera, mostra, deixa editar e exporta — o **perfil legível** do
motor HTML. Um vocabulário só:
- as classes e os atributos `cb-*` deste documento para o que é de xadrez, e as poucas extensões
  que o livro precisa (§4, §5);
- **HTML semântico padrão** para todo o resto (título, parágrafo, lista, tabela, nota, citação).

**Por que congelado.** Um livro publicado não recebe CSS novo: uma classe renomeada quebra a cópia
que o leitor já tem. E os `data-*` são o que deixa ler um livro pronto de volta como partidas e
posições; um livro que os perdesse só se editaria como prosa. Mudar o contrato segue o §10.

**Quem lê.** O leitor do perfil legível (`ler_legivel`, H5) lê este contrato **e** o legado do
perfil de máquina (`data-ir`, `data-ir-id`, as classes `.pN/.rN/.dN`), que continua sendo lido.

**A regra de ida e volta** (spec R2.2a). Para todo XHTML `x` do projeto,
`canon(escrever(ler(x))) == canon(x)`, onde `canon` é a árvore XML com os atributos ordenados e o
espaço insignificante normalizado. O que o XHTML diz sobrevive; o que ele não diz sai do IR com o
padrão do campo. As únicas diferenças aceitas são N1–N4 (§8).

## 2. O arquivo

- Documento de conteúdo do EPUB 3 em XML bem formado, UTF-8:
  `<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
  lang="…" xml:lang="…">`, com `<head>` (`<title>`, e um `<link rel="stylesheet">` por folha do
  projeto, na ordem da espinha) e `<body>`.
- **O escritor legível não escreve** `data-ir`, `data-ir-id`, classe gerada `.pN/.rN/.dN` (N2),
  `<style>` gerado, nem dado da máquina: caminho local, nome de usuário, confiança, motor ou nota
  de OCR (R2.4). Esses dados vão para o `proveniencia.json` do projeto e para o sidecar.
- O que a pessoa escreve fica: um `<style>` dela, um `style=""`, um `data-*` dela (§7).

## 3. Identificadores, âncoras e páginas

A página segue a regra única da spec R2.7: **no `id`, a página do PDF em base 1** (a que a janela
mostra); no IR, nas decisões e no sidecar, base 0; o fólio impresso é uma terceira coisa.

| o quê | forma | exemplo |
|---|---|---|
| bloco com proveniência | `p<pág>-<n>` (n = ordem do bloco na página, de 1) | `<p id="p55-3">` |
| diagrama | `p<pág>-d<n>` | `<figure class="cb-diagram" id="p55-d1">` |
| partida | `p<pág>-g<n>` | `<section class="cb-game" id="p55-g1">` |
| marcador de página | `pg<pág>` | `<span epub:type="pagebreak" role="doc-pagebreak" id="pg55" aria-label="54"/>` |
| partida do livro (CB) | `game-NNN`, numerada de 1 no livro inteiro | `id="game-012"` |
| capítulo (CB) | `chapter-N` | `<section class="cb-chapter" id="chapter-3">` |
| arquivo de diagrama (CB) | `dg_<hash>` (pelo conteúdo: inserir um não renumera os outros) | `../Images/dg_8f2c1e.svg` |

- O `aria-label` do marcador de página é o **fólio impresso** (`running_page_number` do
  importador); na falta, o número do PDF, e a nota «fólio não lido» vai para o `proveniencia.json`,
  não para o livro. A `page-list` do EPUB reflete esses marcadores.
- O bloco sem proveniência (conteúdo que a pessoa escreveu) não ganha `id`, a menos que tenha
  âncora.
- O leitor devolve o `id` ao IR pelo `proveniencia.json` (o `ir_id` do bloco); sem ele, um ULID
  novo.

## 4. Blocos

| nó do IR | marcação legível | o leitor aceita também | origem |
|---|---|---|---|
| `Heading(level)` | `<hN id>`; o `numbering_text` num `span.cb-heading-number` no começo | `data-ir="heading"` | HTML + extensão |
| `Paragraph(style=None)` | `<p id>` | `data-ir="paragraph"` | HTML |
| `Paragraph(style="Movetext")` | `p.cb-movetext` | — | extensão |
| `Paragraph(style="Caption")` | `p.cb-caption` | — | extensão |
| `Paragraph(style="Footnote")` | `p.cb-footnote` | — | extensão |
| `Paragraph(style=X)`, outro | `p.cb-style-<slug(X)>` | a classe `.pN` do legado | extensão |
| `Paragraph(drop_cap=n)` | a classe `cb-dropcap` e `data-drop-cap="n"` | `class="dropcap"` | extensão |
| `ListBlock` / `ListItem` | `ul` ou `ol` (`start` quando ≠ 1) com `li`; a de definição, `dl` com `dt`/`dd` | `data-ir="list_block"` | HTML |
| `Quote` | `blockquote`, com a atribuição num `footer` | `span.attribution` | HTML |
| `Callout` | `aside.cb-callout[data-kind]`, título num `p.cb-callout-title` | — | extensão |
| `CodeBlock` | `pre` > `code` | — | HTML |
| `MathBlock` | `math[display="block"]` (MathML) | — | HTML |
| `Table` | `table` com `caption`, `thead`, `tbody`, `tr`, `th`, `td` (`colspan`/`rowspan`) | — | HTML |
| `ImageBlock` | `figure` > `img[src][alt]` + `figcaption` | `img` sozinho | HTML |
| `Figure` | `figure` + `figcaption` | — | HTML |
| `Footnote` | `aside[epub:type="footnote"][role="doc-footnote"][id]` | — | HTML + EPUB |
| `Endnote` | `aside[epub:type="endnote"][role="doc-endnote"][id]` | — | HTML + EPUB |
| `PageBreak` (quebra pedida) | `div.cb-page-break` (vazio) | — | extensão |
| `SectionBreak` | `hr.cb-section-break` | — | extensão |
| `ThematicBreak` | `hr` | — | HTML |
| `Group` | `div`, com a classe de estilo | — | HTML |
| `TableOfContents` (impresso) | `nav.cb-toc` > `ol` | — | extensão |
| `RawPassthrough` (`xhtml`) | o elemento como está | — | — |
| `RawPassthrough` (outro formato) | `pre.cb-raw[data-format]`, com o texto escapado | — | extensão |
| capítulo (CB) | `section.cb-chapter[id]` > `h1.cb-chapter-title` | — | MARKUP |

**`slug(X)`** é o do projeto (`caissa.editor.livros.slug`): NFKD sem acento, minúsculas ASCII,
`[^a-z0-9]+` → `-`, sem `-` nas pontas. «Citação longa» → `cb-style-citacao-longa`.

## 5. Dentro do parágrafo

| nó do IR | marcação legível | origem |
|---|---|---|
| `Text` | o texto | HTML |
| `Emphasis` / `Strong` / `Underline` / `Strike` | `em` / `strong` / `u` / `s` | HTML |
| `SmallCaps` | `span.cb-smallcaps` | extensão |
| `Superscript` / `Subscript` | `sup` / `sub` | HTML |
| `Span` (com estilo) | `span` com a classe de estilo | HTML |
| `RunProps.language` | `lang` e `xml:lang` no elemento, com o mesmo valor | HTML |
| `Link` | `a[href]` (`#id`, `arquivo.xhtml#id`, ou URL) | HTML |
| `Anchor` | `span[id]` | HTML |
| `NoteRef` | `a.cb-noteref[epub:type="noteref"][role="doc-noteref"][href="#id"]` | HTML + EPUB |
| `LineBreak` | `br` | HTML |
| `NonBreakingSpace` | U+00A0 | HTML |
| `ImageInline` | `img[src][alt]` | HTML |
| `MathInline` | `math` (MathML) | HTML |
| `InlineDiagram` | `span.cb-inline-diagram[data-fen]` > `img.cb-svg[src][alt]` | extensão |
| `IndexEntry` | `span.cb-index-mark[data-term]` | extensão |
| `RawInline` (`xhtml`) | o elemento como está | — |

## 6. O xadrez (MARKUP)

### 6.1 Diagrama

```html
<figure class="cb-diagram" id="p55-d1" data-fen="…" data-stm="b" data-mode="svg"
        data-orientation="white">
  <img class="cb-svg" src="../Images/dg_8f2c1e.svg" alt="Diagrama: …"/>
  <figcaption class="cb-diagram-caption">
    <span class="cb-diagram-label">Diagrama 12</span>
    <span class="cb-stipulation">Mate em 2</span>
    <span class="cb-stm-marker" aria-label="Pretas jogam"></span>
  </figcaption>
</figure>
```

| atributo ou classe | o quê | origem |
|---|---|---|
| `data-fen` | a posição (FEN inteira) — **obrigatório** | MARKUP |
| `data-stm` | `w` ou `b`: o lado da FEN; o tema desenha o marcador daqui | MARKUP |
| `data-mode` | `svg`, `font` ou `font-with-svg-fallback`; **ausente = `svg`** (o `InsertDiagram` do CB o omite) | MARKUP |
| `data-orientation` | `white` ou `black`; ausente = `white` | extensão |
| `cb-diagram` | a figura; `page-break-inside: avoid` | MARKUP |
| `cb-svg` | a imagem, no modo SVG — **derivada** (abaixo) | MARKUP |
| `cb-font-board`, `cb-rank` | o tabuleiro como texto, no modo fonte; uma `cb-rank` por fileira | MARKUP |
| `cb-svg-fallback` | a imagem do modo híbrido, mostrada onde a fonte não serve | MARKUP |
| `cb-diagram-caption` | a legenda | MARKUP |
| `cb-diagram-label` | o rótulo («Diagrama 12», o `label` do IR, ou o número automático) | extensão |
| `cb-stipulation` | a estipulação («Mate em 2»), o `stipulation` do IR | extensão |
| `cb-stm-marker` | o quadradinho de quem joga; cheio para as pretas; `aria-label` diz o lado | MARKUP |
| `cb-move-context` | onde a posição está na partida («após 24…Txf2»), o `move_context` do IR | extensão |

- **O que é derivado.** A `img.cb-svg` sai da FEN, da orientação e do estilo: o `src` é
  `../Images/dg_<hash>.svg`, com o hash desse conteúdo, e o arquivo é regenerável. O `alt` é o
  `alt_text` do IR quando a pessoa escreveu um; senão, a descrição da posição tirada da FEN,
  no idioma do livro (`descrever_posicao(fen, lado, idioma, conferida)`, H4), que diz quando a
  posição não foi conferida por uma pessoa. O leitor não lê a posição da imagem: lê o `data-fen`.
- O CB reprova diagrama sem `data-fen`, com FEN que não se lê, com `src` que o livro não leva, e
  diagrama cuja posição não é a do lance acima dele; avisa `img` sem `alt`.

### 6.2 Partida

```html
<section class="cb-game" id="p55-g1" data-eco="C67" data-result="1/2-1/2">
  <header class="cb-game-header">…</header>
  <div class="cb-moves">
    <p class="cb-line cb-mainline">
      <span class="cb-movenum">1.</span><span class="cb-move" data-uci="e2e4"
        data-fen="…">e4</span> <span class="cb-move" data-uci="e7e5" data-fen="…">e5</span>
      <span class="cb-movenum">2.</span><span class="cb-move" data-uci="g1f3"
        data-fen="…"><span class="cb-piece" data-piece="N">♘</span>f3</span>
      <span class="cb-nag" data-nag="5">⁉</span>
    </p>
    <p class="cb-comment">…</p>
  </div>
  <p class="cb-result">½-½</p>
</section>
```

| classe | elemento | o quê |
|---|---|---|
| `cb-game` | `section` | uma partida; `data-eco`, `data-result` |
| `cb-game-header` | `header` | o bloco acima dos lances |
| `cb-moves` | `div` | do primeiro ao último lance |
| `cb-result` | `p` | o resultado, na própria linha |
| `cb-line` | `p` | uma sequência de lances; sempre com `cb-mainline` ou `cb-variation` |
| `cb-mainline` | | a linha principal (profundidade 0) |
| `cb-variation` + `cb-depth-N` | | uma variante e a profundidade dela, de 1 para cima |
| `cb-movenum` | `span` | `12.` ou `12…`; `white-space: nowrap` |
| `cb-move` | `span` | um lance: `data-uci` e `data-fen` — **a posição depois dele** |
| `cb-piece` | `span` | a peça do lance; `data-piece` é **sempre a letra inglesa** |
| `cb-nag` | `span` | o símbolo de avaliação; `data-nag` é o código numérico |
| `cb-comment` | `p` (ou `span` num `cb-run-in`) | a prosa entre lances |
| `cb-run-in` | `p` | o parágrafo com a prosa corrida dentro (o comentário vira `span`) |

- **Dentro de `cb-piece`**, o que o livro imprime: a figurina Unicode (o padrão, `♘`), ou a letra
  do idioma do livro com uma fonte de xadrez que a desenha (`C` em português); nunca o caractere
  da fonte. O `data-piece` é o inglês nos dois casos.
- A linha quebra em parágrafo novo quando prosa, diagrama ou variante a interrompe, e o primeiro
  lance depois da quebra repete o número. **Um diagrama sempre quebra o parágrafo.** A segunda
  variante do mesmo lance abre o próprio parágrafo, também no `cb-run-in`.
- **O cabeçalho** (MARKUP): `p.cb-game-number`; `p.cb-player.cb-white` e `p.cb-player.cb-black`,
  cada um com `span.cb-elo` **antes** de `span.cb-name`; `p.cb-event` com `span.cb-event-name`,
  `span.cb-site`, `span.cb-round`, `time.cb-date[datetime]`; `p.cb-opening` com
  `span.cb-opening-name` e `span.cb-eco`; `p.cb-annotator`. **O elemento sem valor não sai: um
  campo que falta nunca se imprime como `?`** (o item 4 do H4).
- O `Move` do IR é o `cb-move`; o `MoveNode` é a posição dele na `cb-line`; o `GameScore`, a
  `section.cb-game`. O `PieceGlyph` é o `cb-piece`; o `NagSymbol`, o `cb-nag`.

### 6.3 Índices (MARKUP, gerados)

`nav.cb-index` (`epub:type="index"`) com uma das classes `cb-index-players`, `-openings`,
`-games`, `-endgames`, `-themes`, `-positions`; cada linha é um `p.cb-index-entry` com
`span.cb-index-name` e `span.cb-index-refs`, cujos links são `a.cb-ref.cb-ref-white` ou
`a.cb-ref.cb-ref-black` (a cor que o jogador teve naquela partida, e nada mais); o grupo é um
`cb-index-heading`, sem referência. Os atributos da entrada: `data-family` e `data-material`
(finais); `data-category` no grupo, `data-theme` e `data-origin` (`manual`, `nag`, `derived`,
unidos por vírgula) na entrada (temas); `data-fen`, `data-zobrist` (16 dígitos hexadecimais, o
hash polyglot do python-chess) e `data-stm` (posições — as dos diagramas do livro, pela chave
Zobrist).

## 7. O que o contrato não modela é preservado (R2.3)

- **Elemento desconhecido** → `RawPassthrough` (bloco) ou `RawInline` (dentro do parágrafo), no
  formato `xhtml`, com o elemento como está; o escritor o devolve igual.
- **Atributo desconhecido num elemento do contrato** — `style`, `title`, `aria-*`, `data-*` fora
  deste documento, classe além da de estilo — → `IRNode.html_attributes` do nó; o escritor os
  devolve na ordem do `canon`.
- **Nomes proibidos no livro publicado** (R2.4): o escritor nunca escreve atributo com nome de
  campo de proveniência (`data-confidence`, `data-engine`, `data-note`…). Se a pessoa escrever, a
  varredura da exportação (H24) acusa.

## 8. Normalizações declaradas — a lista fechada

- **N1.** As `RunProps` de família e de corpo que vêm do PDF digitalizado não viram marcação: o
  tema decide. Contadas por arquivo.
- **N2.** As classes geradas `.pN`/`.rN`/`.dN` não existem no perfil legível.
- **N3.** O `Span` que só carrega proveniência vira um intervalo no `proveniencia.json`
  (`duvidas`), e não marcação.
- **N4.** O espaço insignificante e a ordem dos atributos (`canon`).

Qualquer outra diferença na ida e volta reprova o portão do H5.

## 9. A política de CSS (spec S3b)

**A fonte.** As folhas em `OEBPS/Styles/` são a verdade. O IR as carrega como
`Resource(kind=STYLESHEET)`, sem interpretá-las.

| formato | o que recebe | o que avisa |
|---|---|---|
| EPUB e HTML | as folhas do projeto **byte a byte**, na ordem da espinha; nada de `BASE_CSS`/`CHESS_CSS`/`props.css` | — |
| PDF | a impressão do XHTML com as folhas, pelo motor da prévia Página | `css-nao-desenhado-pelo-motor` por propriedade que o motor ativo não desenha (a matriz do H1) |
| DOCX | o **mapa de estilo** (abaixo) | `css-fora-do-mapa` por regra ou propriedade fora do mapa |
| LaTeX | a estrutura pelo IR | **um** `css-nao-suportado-no-formato`, com a lista das folhas |

**O mapa de estilo** — um subconjunto fechado, com a cascata (especificidade e ordem) resolvida só
dentro dele:
- **Seletores:** `.classe`; `p.classe`; `span.classe`; `h1`…`h6`, com ou sem classe;
  `figcaption`; `blockquote`; as classes `cb-*` deste contrato; `:root`, só para variáveis.
- **Propriedades:** `font-family`, `font-size`, `font-weight`, `font-style`, `font-variant`
  (`small-caps` ou `normal`); `color`, `background-color` (o realce de trecho); `text-align`,
  `text-indent`, `margin-top`, `margin-right`, `margin-bottom`, `margin-left` (e o atalho
  `margin`), `line-height`, `letter-spacing`, `text-transform`; `break-before` e
  `page-break-before`; `widows` e `orphans`; e `var(--x)` resolvível pelas variáveis de `:root`.

**O resultado do mapa** (o contrato das fixtures `tests/fixtures/editor/css/`, que o H5
implementa em `editor/css/mapa_de_estilo.py`):

```json
{"estilos": {"<alvo>": {"<propriedade>": "<valor calculado>"}},
 "avisos": [{"codigo": "css-fora-do-mapa", "seletor": "…", "propriedade": "…",
             "arquivo": "…", "linha": 7}]}
```

- **O alvo** é o que o DOCX recebe como estilo: `p.<classe>` (estilo de parágrafo),
  `span.<classe>` (estilo de caractere), `hN` e `hN.<classe>` (títulos), `figcaption` e
  `blockquote`. Cada seletor do mapa cria os alvos que ele pode atingir: `.x` cria `p.x` e
  `span.x`; `p.x`, só `p.x`; `h2.x`, só `h2.x`; `h2`, só `h2`.
- **A cascata, por alvo.** O estilo de um alvo é o de um elemento daquele tipo com aquela classe e
  nenhuma outra: valem as regras cujo seletor casa com ele (`h2.titulo` recebe `h2`, `.titulo` e
  `h2.titulo`), pela especificidade e, no empate, pela ordem (as folhas na ordem da espinha, as
  regras na ordem do arquivo). Não há herança do `body` nem do pai.
- **O valor calculado**: `var(--x)` resolvido pelas variáveis de `:root` (a variável que não
  existe usa o valor de reserva do `var()`, e sem reserva a declaração avisa); `font-weight`
  `normal`→`400` e `bold`→`700`; cor em `#rrggbb` minúsculo (nome de cor e `#rgb` abertos); o
  atalho `margin` aberto em `margin-top`, `margin-right`, `margin-bottom` e `margin-left`;
  `page-break-before` escrito como `break-before` (`always`→`page`); o resto como escrito, sem
  espaço nas pontas.
- **Um aviso por construção fora do mapa**, com o código `css-fora-do-mapa`, o seletor, a
  propriedade (vazia quando a regra inteira fica fora) e `arquivo:linha` (a linha do seletor, da
  declaração ou da `@`-regra): combinadores (descendente, `>`, `+`, `~`), seletor de atributo, de
  `id`, universal, `p` ou `span` sem classe, pseudo-classe, pseudo-elemento, `@media`, `@page`,
  `@font-face` (as fontes vão pelo registro de fontes), `@import`, `display` (qualquer valor:
  grid, flex…), `float`, `position`, `transform`, `!important`, `font-weight` relativo
  (`bolder`, `lighter`) e toda propriedade fora da lista. A regra que fica fora não entra em
  alvo nenhum; a declaração que fica fora não entra, e as outras da mesma regra entram.

## 10. Mudar este contrato

- **Acrescentar** uma classe ou um `data-*` é seguro: exige uma linha nova aqui, a fixture e o
  aviso ao `CB validate` quando ele precisar saber.
- **Renomear ou remover** não: exige versão nova do contrato, migração dos projetos (o `formato` do
  `projeto.json`), um registro no `DECISIONS.md` do CB e uma mutação no roadmap §10.
- Quando um tema precisar de uma distinção que o contrato não diz, acrescenta-se um `data-*`, e
  não uma variante de classe.

## 11. As fixtures (o portão do H3)

`tests/fixtures/editor/contrato/` tem uma fixture por linha da S4, as combinações e a legada; a
tabela é a que o `benchmarks/editor_contrato.py` confere (100 % das linhas com fixture, o
`CB validate` com 0 erro).

| linha da S4 | fixture |
|---|---|
| `Heading(level)` | `titulo.xhtml` |
| `Paragraph(style=None)` | `paragrafo.xhtml` |
| `Paragraph(style="Movetext")` | `paragrafo_movetext.xhtml` |
| `Paragraph(style="Caption"\|"Footnote"\|X)` | `paragrafo_estilos.xhtml` |
| `Emphasis`…`Subscript` | `formatacao.xhtml` |
| `RunProps.language` | `lingua.xhtml` |
| `Link`/`Anchor`/`NoteRef` | `links_ancoras_notas.xhtml` |
| `Diagram` | `diagrama.xhtml` |
| `GameScore`/`MoveNode`/`Move` | `partida.xhtml` |
| `PieceGlyph` | `figurina.xhtml` |
| `NagSymbol` | `nag.xhtml` |
| página do PDF | `pagina.xhtml` |
| `RawPassthrough`/`RawInline` | `bruto.xhtml` |
| `html_attributes` | `atributos.xhtml` |
| combinações | `combinacao_capitulo.xhtml`, `combinacao_partida_com_diagrama.xhtml` |
| o legado do `XhtmlBuilder` de hoje | `legado_xhtml_builder.xhtml` |

- **As negativas** ficam fora do conjunto limpo, em `tests/fixtures/editor/contrato_negativas/`:
  `negativa_sem_fen.xhtml` (o diagrama sem `data-fen`), que a sabotagem do H3 põe no conjunto.
- **O CSS:** `tests/fixtures/editor/css/mapa_positivo/` (cada propriedade do mapa com dois
  valores, e o resultado esperado num `.json` ao lado) e `mapa_negativo/` (uma construção fora do
  mapa por arquivo, e o aviso esperado).
- **O sidecar** (spec Apêndice C): `tests/fixtures/editor/sidecar/`, escritas pelo crítico, com o
  SHA-256 no relatório do H3.
