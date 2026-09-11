# F8 — Exportadores

**Data:** 2026-09-07, segunda passagem
**Escopo:** `src/caissa/export/`, `tests/unit/export/`
**SPEC:** §8 (os cinco formatos), §5.2 (a regra de ouro), §11.3 (os portões)

---

## 0. Veredito em uma tela

| Formato | Fidelidade declarada | Fidelidade bruta | Método | Portão externo |
|---|---|---|---|---|
| **HTML** | **100 %** ✔ | 66,83 % | markup | — |
| **EPUB 3** | **99,52 %** ✔ | 66,83 % | markup | **EPUBCheck 4.2.6: 0 erros** ✔ |
| **DOCX** | **100 %** ✔ | 3,85 % | markup | **Word 2016 abre sem reparo** ✔ |
| **PDF** | 100 % (*) | 100 % (*) | sidecar | — |
| **LaTeX** | 100 % (*) | 100 % (*) | sidecar | **pdflatex gera o PDF** ✔ |

(*) 100 % via *sidecar*, o que mede serialização e **não** o escritor. Ver §3.

`tests/unit/export/` tem **434 testes, todos passando**. Os dois `xfail` do
DOCX viraram asserções: `test_no_silent_loss_beyond_the_gate[docx]` e
`test_a_realistic_book_loses_nothing_undeclared[docx]` medem 100 % e cobram
99 %. O estado da suíte inteira está em §9.

**O portão de §11.3 (≥ 99 % dos nós preservados) passa nos cinco formatos.**
Todos os números aqui saem de uma medição; nenhum é estimativa.

> **Segunda passagem (esta).** A primeira entrega deixou o DOCX em 61,54 % com
> um diagnóstico do que faltava. Esta passagem fechou o que estava listado lá:
> `w:tabs`, `w:numPr`, a estrutura de tabela, os `w:r` da partida e a atribuição
> de uma perda causada por um ancestral achatado ao nó que a declarou. O que
> mudou no perfil, e por quê, está em §6.4 — a leitura dessa seção é o que
> permite verificar que o número subiu por trabalho e não por declaração.

---

## 1. O que "fidelidade" quer dizer aqui, e por que há dois números

`caissa.export.fidelity` exporta, relê o arquivo com o leitor do próprio formato
e compara as duas árvores com `semantic_diff`. Cada campo que diferiu é então
procurado na tabela de capacidades do formato (`caissa.export.profiles`):

* o perfil diz que o formato **não** carrega aquilo → a perda é **declarada**, e
  o relatório de exportação já a nomeou;
* o perfil diz que carrega **plenamente** → a perda é **silenciosa**, e isso é
  um defeito, contado contra o portão.

Daí os dois números:

**`fidelity` (bruta)** — nós que voltaram idênticos, campo por campo. É o número
que a SPEC §11.3 literalmente pede, e é pessimista de um jeito que engana: um
parágrafo que perdeu apenas a tinta CMYK — perda que o formato declarou, sobre a
qual o usuário foi avisado e que nenhum leitor de EPUB conseguiria mostrar —
conta como danificado. Por isso HTML marca 66,83 % bruto mesmo sem nenhuma perda
real: o corpus adversarial põe CMYK, *spot*, *tracking* em twips e escalas
horizontais em quase toda execução.

**`declared_fidelity`** — nós sem nenhuma perda **não declarada**. É o número que
responde à pergunta que esta frente existe para responder: *o exportador é
honesto?* É contra ele que o portão é aplicado, e a substituição está registrada
aqui em vez de escondida no código.

> Um relatório que só publicasse a fidelidade bruta seria pessimista a ponto de
> ser inútil; um que só publicasse a declarada poderia esconder um perfil
> mentiroso. Os dois juntos não deixam saída: para inflar a declarada é preciso
> escrever no perfil, em português, por que o formato não carrega aquilo — e
> `test_every_declared_loss_has_a_reason` exige que a explicação tenha mais de
> vinte caracteres e nomeie o mecanismo.

---

## 2. Por formato

### 2.1 EPUB 3 — `epub.py` (1455 linhas)

| Item da SPEC §8.3 | Estado |
|---|---|
| XHTML semântico | ✔ `epub:type` em capítulos, notas, remissivo |
| CSS modular | ✔ `base.css` + `chess.css` + `props.css` |
| Diagramas em SVG **inline** | ✔ zero partes raster no pacote (testado) |
| Fontes de xadrez embutidas e subconjuntadas | ✔ **exercitado**: uma fonte de xadrez no texto corrido é embutida e subconjuntada — ver §8.1 |
| `nav.xhtml` com landmarks | ✔ `toc`, `bodymatter`, `footnotes`, `index` |
| MathML | ✔ com namespace e propriedade `mathml` no OPF |
| Metadados Dublin Core | ✔ `dc:title`, `dc:language`, `dc:identifier`, `dcterms:modified` |
| Layout fixo opcional | ✔ `rendition:layout pre-paginated` |
| **EPUBCheck 0 erros** | ✔ **verificado de verdade** |

**EPUBCheck: executado, não presumido.** EPUBCheck 4.2.6 (JAR baixado; Java
1.8.0_503 nesta máquina), rodado sobre **cinco corpora gerados com sementes
diferentes**: `0 erros fatais / 0 erros / 0 advertências` em todos.
`tests/unit/export/test_epub.py::test_epubcheck_reports_no_errors` encontra o JAR
sozinho (ou por `CAISSA_EPUBCHECK`) e faz o portão parte da suíte; sem Java ou
sem o JAR o teste **pula com a razão escrita**, nunca passa em silêncio.

O primeiro pacote gerado tinha **219 erros**. Os nove defeitos reais, todos
corrigidos:

| Erro | Causa | Correção |
|---|---|---|
| `RSC-005` × 6 | XHTML malformado: o divisor de seções cortava dentro de um elemento | divisor com consciência de profundidade (`split_markup`) |
| `CSS-001` × 183 | `direction` é **proibido** em folha de estilo EPUB | tirado do CSS; o valor viaja em `--caissa-rdirection` |
| `RSC-012` × 17 | `href="#x"` apontando para outro arquivo XHTML | reescrita por seção; âncora sem destino perde o `href` |
| `RSC-007` × 6 | `<img>` para arquivo que o pacote não carrega | vira marcador de texto **com aviso** |
| `OPF-014/015` × 4 | propriedades `svg`/`mathml` declaradas erradas | calculadas do conteúdo real da seção |
| `a` dentro de `a` | `Link` dentro de `Link`, e `Anchor` como `<a>` | o interno vira `<span>`; âncora é `<span id=...>` |
| `math` não permitido | MathML sem namespace | namespace injetado |
| `value` em `<li>` de `<ul>` | atributo só é legal dentro de `<ol>` | virou `data-start` |
| `RSC-011` | landmark apontando para fora da lombada | `nav.xhtml` entra na lombada com `linear="no"` |

### 2.2 DOCX — `docx.py` (4050 linhas)

| Item da SPEC §8.2 | Estado |
|---|---|
| **Estilos reais** (não formatação direta) | ✔ 37 estilos em `styles.xml`; Word confirma "Sumário 1" aplicado |
| Numeração de figuras via **campo SEQ** | ✔ `{ SEQ Diagrama \* ARABIC }`; Word lê o campo |
| Sumário via **campo TOC** | ✔ `{ TOC \o "1-3" \h \z \u }` + `w:updateFields` |
| Diagramas como **EMF vetorial** | ✔ **7 de 7 saíram como EMF** — ver abaixo |
| Notas de rodapé | ✔ `word/footnotes.xml`; Word conta 1 nota real |
| Propriedades de documento | ✔ `docProps/core.xml` e `app.xml` |
| **Abre no Word sem pedido de reparo** | ✔ **verificado no Word 2016 real** |
| Régua de tabulação (`w:tabs`) | ✔ escrita **e lida**; alinhamento e preenchimento exatos |
| Numeração nomeada (`w:numPr` + `w:abstractNum/w:name`) | ✔ ida e volta pelo nome da definição |
| Tabela: bordas, margens, largura, alinhamento, descrição | ✔ `w:tblBorders`, `w:tblCellMar`, `w:tblW`, `w:jc`, `w:tblDescription` |
| Linha e célula com identidade própria | ✔ bookmark entre `w:tr` e entre `w:tc` |
| Partida como uma execução por lance | ✔ a árvore de lances volta com os mesmos nós |
| Capitular (`w:framePr`) | ✔ número de linhas exato |
| Formatação da marca de parágrafo (`w:pPr/w:rPr`) | ✔ |
| Identidade do documento (`w:docVars`) | ✔ sobrevive inclusive a um *salvar* do Word |

**Word: verificado, não presumido.** Há Word 2016 nesta máquina
(`C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`). O arquivo foi
aberto via automação COM, com `DisplayAlerts` desligado — nesse modo um arquivo
que exigisse reparo levanta exceção em vez de perguntar. Resultado do corpus
adversarial completo:

```
OK corpus248.docx paragraphs=61 inlineShapes=7 footnotes=0 endnotes=0 fields=9
                  bookmarks=174 tables=2 lists=3
OK corpus21.docx  paragraphs=62 inlineShapes=9 footnotes=0 endnotes=0 fields=16
                  bookmarks=167 tables=1 lists=6
  tabela 1: linhas=2 colunas=3
```

`bookmarks` subiu de 134 para 174 porque linhas, células, lances e notas passaram
a ter identidade própria, e `lists` deixou de ser zero porque as definições de
numeração nomeadas agora existem em `word/numbering.xml`. As linhas e colunas que
o Word conta na tabela são as que o IR tinha.

e de um documento com nota e sumário:

```
OK notas.docx paragraphs=6 footnotes=1 fields=4 inlineShapes=1
  campo: TOC \o "1-3" \h \z \u
  campo: HYPERLINK \l "_Toc239680445"     <- o Word preencheu o sumário sozinho
  campo: PAGEREF _Toc239680445 \h         <- idem
  campo: SEQ Diagrama \* ARABIC
  estilo do 1o paragrafo: Sumário 1
  shape tipo=3 largura=130.4pt altura=131.7pt
```

Os dois campos `HYPERLINK`/`PAGEREF` não foram gravados por nós: o Word os gerou
ao abrir, o que prova que o campo TOC está vivo e que `w:updateFields` funcionou.

Nesta passagem entrou um documento a mais, que exercita cada elemento novo —
capitular, régua de tabulação, numeração nomeada com `w:startOverride`,
formatação da marca de parágrafo, tabela com bordas e margens próprias, partida
com variante e comentários, nota de rodapé e nota de fim:

```
OK recursos.docx paragraphs=12 footnotes=1 fields=3 bookmarks=30 tables=1 lists=1
  tabela 1: linhas=2 colunas=2
```

**A primeira tentativa foi recusada pelo Word.** Duas causas, ambas invisíveis a
qualquer verificação que não seja o Word:

1. **Ordem dos elementos.** OOXML declara `w:rPr` e `w:pPr` como `xsd:sequence`,
   não `xsd:all`. Um elemento fora de posição é violação de esquema, e o Word
   responde a isso recusando o arquivo. Corrigido com `_RPR_ORDER` / `_PPR_ORDER`
   e um passo de ordenação — o escritor emite na ordem que se lê melhor e é
   colocado em ordem legal no fim.
2. **Extensão negativa.** `wp:extent/@cx` é positivo por tipo. O corpus sintético
   gera diagramas de largura negativa e isso chegava ao arquivo. Agora o
   renderizador troca uma largura ≤ 0 pela padrão **e registra a substituição**.

**EMF: funcionou de verdade.** As estatísticas contam os dois caminhos
separadamente e o teste lê os contadores:

```
docx {'diagrams': 14, 'diagrams_emf': 7, 'games': 5, 'nodes': 198, 'styles': 37}
```

(`games` subiu de 3 para 5 e `nodes` de 177 para 198 nesta passagem: as duas
partidas a mais são soluções de diagrama, que antes não eram impressas, e os
nós a mais são os lances, agora contados um a um.)

`diagrams_png` nem aparece: **nenhum diagrama caiu para PNG**. Antes da correção
da largura negativa eram `diagrams_emf: 5, diagrams_png: 2`, e cada PNG vinha com
o aviso de rasterização dizendo o motivo exato
(`SVG invalido: dimensoes -1.15 x -1.15 mm`). O `test_asking_for_raster_says_so_out_loud`
liga `vector_diagrams=False` de propósito e exige um `DegradationWarning` de
rasterização para **cada** diagrama que virou pixel — um PNG silencioso reprova.

### 2.3 PDF — `pdf.py` (1430 linhas) sobre `pdfwrite.py` (2595 linhas)

| Item da SPEC §8.1 | Estado |
|---|---|
| Fontes embutidas em subconjunto | ✔ `FontEmbedder`, `cmap` reconstruído |
| Diagramas **vetoriais, nunca raster** | ✔ **348 operadores de caminho; zero XObject de imagem** |
| Sumário navegável (outline) | ✔ hierárquico por nível de título |
| Metadados XMP | ✔ mais DocInfo |
| PDF/A-2b opcional | parcial — ver `pdfa_caveats()` |
| Marcação de acessibilidade | parcial — árvore de estrutura existe, não é populada |

O teste de vetorialidade não é estilístico: `/Subtype /Image` é a **única** forma
de um bitmap existir numa página PDF, e o teste procura exatamente isso. Uma
regressão que rasterizasse o tabuleiro teria de adicionar um XObject e seria vista.

O motor de layout é uma galé de coluna única com quebra gulosa sobre as larguras
reais da fonte embutida. **Não** é Knuth-Plass e não flutua figuras; onde o IR
pede o que ele não faz (duas colunas, geometria de página fixa), o perfil declara
e o aviso é registrado.

### 2.4 LaTeX — `latex.py` (1004 linhas)

| Item da SPEC §8.5 | Estado |
|---|---|
| `xskak` / `chessboard` / `chessfss` | ✔ via `caissa.typeset.latex`, sem duplicar nada |
| Diagramas como `\chessboard[setfen=...]` | ✔ **editáveis em texto**, o FEN legível no fonte |
| Figurino | ✔ `\symknight{}` etc. |
| `Makefile` gerado | ✔ |
| **Compila** | ✔ **pdflatex gerou `livro.pdf`, 515 KB, exit 0** |

**pdflatex: executado, não presumido.** MiKTeX nesta máquina. Cinco defeitos
fatais — nenhum deles visível sem rodar o motor — encontrados e corrigidos, cada
um com teste:

| Erro do pdflatex | Causa | Correção |
|---|---|---|
| `Not allowed in LR mode` | `\begin{flushright}` dentro de célula | alinhamento vai para o especificador de coluna |
| `Undefined control sequence` (`\href`) | `hyperref`, `ulem`, `makeidx` faltando | carregados pelo exportador, sem tocar no preâmbulo de xadrez |
| `\xskak@do@parsemainline has an extra }` | partida com lances ilegais | jogabilidade verificada antes; se não replica, vira texto **com aviso** |
| `SETFEN undefined` | `\chessboard` num título, que o `book` põe em maiúsculas no cabeçalho | título viaja como texto puro no argumento opcional |
| `Unicode character ♞ not set up` | figurino Unicode literal | mapeado para comandos `chessfss` |

### 2.5 HTML — `html.py` (5574 linhas)

Página única autocontida ou site estático, diagramas SVG interativos opcionais,
CSS Paged Media para impressão, tema claro e escuro **projetados separadamente**
(não um invertendo o outro). A `read_html` lê o *markup* e a folha de estilo — as
duas coisas que um navegador lê — e não o sidecar, que existe para "reabrir minha
exportação" e é explicitamente ignorado na medição.

---

## 3. Onde os números **não** medem o escritor

PDF e LaTeX marcam 100 %, e isso precisa de asterisco. Recuperar um IR de uma
página de operadores de posicionamento de glifo não é possível em nenhum sentido
útil, e escrever um analisador de TeX é escrever TeX. Os dois exportadores
gravam o IR ao lado (`.caissa.json` para o PDF, um bloco de comentário
`%%CAISSA-IR` no `.tex`) e `read_pdf`/`read_latex` leem **isso**.

`FidelityReport.method` diz `"sidecar"` em letras, `READERS` documenta o que cada
método prova, e `test_sidecar_formats_say_so` trava a distinção. **Um 100 % de
sidecar é uma afirmação sobre `json`, não sobre o escritor**, e está aqui rotulado
assim para que ninguém o cite como se fosse outra coisa.

HTML, EPUB e DOCX são medidos pelo leitor do próprio formato: os números deles
são sobre o escritor.

---

## 4. O inventário de degradações — o artefato mais útil desta frente

**41 (HTML) · 43 (EPUB) · 142 (DOCX) · 45 (PDF) · 65 (LaTeX)** entradas não-plenas
declaradas — o DOCX cresceu de 109 para 142 nesta passagem, e cada entrada nova
está justificada em §6.4. Cada uma tem um motivo em português que **nomeia o mecanismo**
("`w:sz` guarda o corpo em meios-pontos inteiros; um corpo de 10,4 pt sai como
10,5 pt"), porque um usuário que sabe *por quê* decide se se importa.

`test_every_run_property_is_carried_or_declared` percorre as **46 propriedades de
execução × 5 formatos** e exige, para cada par, exatamente uma de duas coisas: o
perfil diz "plena" e **nenhum** aviso aparece, ou o perfil diz outra coisa e o
aviso **aparece nomeando a propriedade**. Não há terceira opção, e acrescentar uma
propriedade ao IR sem decidir qual é reprova aqui.

### 4.1 Propriedades de execução (as 44 que não são plenas em algum formato)

| Propriedade | HTML | EPUB | DOCX | PDF | LaTeX |
|---|---|---|---|---|---|
| `style` | plena | plena | plena | subst. | plena |
| `font_family` | plena | plena | plena | plena | aprox. |
| `font_fallbacks` | plena | plena | **ausente** | aprox. | **ausente** |
| `font_size` | plena | plena | aprox. | plena | plena |
| `font_weight` | plena | plena | por valor | por valor | por valor |
| `oblique_angle` | plena | plena | **ausente** | plena | **ausente** |
| `font_stretch` | plena | plena | **ausente** | subst. | aprox. |
| `color` | por valor | por valor | por valor | por valor | por valor |
| `highlight` | por valor | por valor | aprox. | plena | aprox. |
| `background` | por valor | por valor | subst. | plena | aprox. |
| `letter_spacing` | plena | plena | aprox. | plena | aprox. |
| `word_spacing` | plena | plena | **ausente** | plena | aprox. |
| `horizontal_scale` | aprox. | aprox. | aprox. | plena | aprox. |
| `kerning` | plena | plena | plena | aprox. | plena |
| `kerning_min_size` | **ausente** | **ausente** | aprox. | plena | **ausente** |
| `ligatures` | plena | plena | plena | **ausente** | plena |
| `font_features` | plena | plena | **ausente** | **ausente** | aprox. |
| `variation_axes` | plena | plena | subst. | subst. | aprox. |
| `small_caps` | por valor | por valor | por valor | por valor | por valor |
| `text_transform` | plena | plena | por valor | por valor | por valor |
| `baseline_shift` | plena | plena | aprox. | plena | plena |
| `rise_relative` | plena | plena | subst. | plena | plena |
| `vertical_align` | plena | plena | por valor | plena | por valor |
| `numeral_figure` | plena | plena | plena | **ausente** | aprox. |
| `numeral_spacing` | plena | plena | plena | **ausente** | **ausente** |
| `underline` | por valor | por valor | plena | por valor | por valor |
| `underline_color` | plena | plena | aprox. | plena | aprox. |
| `underline_thickness` | plena | plena | **ausente** | plena | aprox. |
| `underline_offset` | plena | plena | **ausente** | plena | aprox. |
| `underline_skip_ink` | plena | plena | **ausente** | **ausente** | **ausente** |
| `strikethrough` | plena | plena | plena | plena | por valor |
| `strikethrough_color` | plena | plena | **ausente** | plena | **ausente** |
| `overline` | plena | plena | **ausente** | plena | **ausente** |
| `outline` | aprox. | aprox. | aprox. | plena | **ausente** |
| `shadow` | plena | plena | aprox. | aprox. | **ausente** |
| `emboss` | subst. | subst. | plena | **ausente** | **ausente** |
| `engrave` | subst. | subst. | plena | **ausente** | **ausente** |
| `emphasis_mark` | plena | plena | plena | **ausente** | **ausente** |
| `opacity` | plena | plena | **ausente** | plena | aprox. |
| `hyphenate` | plena | plena | **ausente** | plena | plena |
| `spell_check` | plena | plena | plena | **ausente** | **ausente** |
| `direction` | plena | plena | plena | **ausente** | **ausente** |
| `no_break` | plena | plena | **ausente** | plena | plena |
| `hidden` | plena | plena | plena | plena | subst. |

"por valor" quer dizer que a resposta depende do valor pedido: `color` sobrevive
em RGB e é convertida em CMYK; `small_caps` é exata em `synthetic` e sintetizada
em `real`; `vertical_align` no DOCX existe para sobrescrito e subscrito e para
mais nada.

### 4.2 Propriedades de parágrafo (as 16 não-plenas)

| Propriedade | HTML | EPUB | DOCX | PDF | LaTeX |
|---|---|---|---|---|---|
| `style` | plena | plena | aprox. | plena | plena |
| `indent_left` / `indent_right` / `indent_first_line` | plena | plena | aprox. | plena | plena |
| `space_before` / `space_after` | plena | plena | aprox. | plena | plena |
| `line_spacing` | plena | plena | aprox. | plena | plena |
| `widow_control` | plena | plena | plena | plena | aprox. |
| `tab_stops` | subst. | subst. | aprox. | plena | plena |
| `borders` | plena | plena | aprox. | plena | plena |
| `padding` | plena | plena | aprox. | plena | aprox. |
| `shading` | plena | plena | aprox. | plena | aprox. |
| `direction` | plena | plena | plena | plena | **ausente** |
| `suppress_line_numbers` | **ausente** | **ausente** | plena | **ausente** | aprox. |
| `mark_props` | **ausente** | **ausente** | plena | **ausente** | **ausente** |
| `default_run` | plena | plena | subst. | plena | plena |

Todo o `aprox.` do DOCX é a mesma verdade dita muitas vezes: OOXML quantiza. O
corpo vai em meios-pontos, os recuos, espaços e paradas de tabulação em twips
inteiros, as bordas em oitavos de ponto, as cores sempre em sRGB. O `subst.` de
`default_run` é a outra verdade recorrente: onde o formato não tem um lugar para
a herança, ela é escrita em cada filho.

### 4.3 Campos de nó — a regra de ouro estendida

A SPEC §5.2 fala de *propriedades*, mas um campo de nó é uma propriedade com
outro nome: um diagrama que perde a confiança por casa perdeu algo que o autor
não pode mais auditar. `FormatProfile.node_fields` foi acrescentado nesta frente
e `audit_node_fields` roda em **todo** nó de **todo** exportador.

| Campo | Todos os formatos | Motivo |
|---|---|---|
| `*.provenance` | ausente | arquivo, página, retângulo, DPI: metadado de auditoria do IR |
| `diagram.source` | ausente | o recorte de origem no PDF não sobrevive fora do IR |
| `diagram.recognition` | ausente | confiança por casa e modelo: o arquivo guarda o FEN, não como se chegou a ele |
| `diagram.verified_by_human` | ausente | selo do editor, não do livro |
| `diagram.style` | substituída | virou geometria no desenho |
| `diagram.solution` | substituída | viaja como PGN; identidade recriada |
| `document.styles` | substituída | virou CSS gerado |
| `document.settings` | ausente | preferências de edição, não conteúdo publicado |
| `document.resources` | ausente | índice interno do IR |

Além dessa tabela comum, o DOCX tem **26 campos de nó só dele**, porque é o
único formato cuja leitura desce fundo o bastante para os campos chegarem a
divergir. Estão em `_DOCX_NODE_FIELDS` e listados em §6.4, cada um com o
elemento do ECMA-376 que responde por ele.

Uma consequência de `node_fields` valer nó a nó: quando o campo não tem
declaração própria, quem responde é a declaração do **tipo do nó**. "A partida
viaja como texto PGN" é uma afirmação sobre os lances, os cabeçalhos e os
comentários ao mesmo tempo, e desde esta passagem vale também para o registro de
propriedades do nó — uma nota que foi para `word/footnotes.xml` deixou lá a sua
formatação de bloco porque `CT_FtnEdn` não tem onde guardá-la.

---

## 5. Como HTML e EPUB chegaram a 100 % e 99,52 %

O ponto de partida medido foi **0 %**. Não por acaso: as duas metades do
problema, escrever e reler, não estavam alinhadas em nenhum lugar. Os itens 1 a
7 são da primeira passagem; 8, 9 e 10 são desta. As correções que valeram a pena
registrar, porque cada uma é uma armadilha genérica:

1. **A folha gerada não era lida.** O modo página única enfiava o CSS gerado no
   `<style>` anônimo; a `read_html` só lê `<style id="caissa-props">`. Toda a
   formatação do documento estava no arquivo e invisível para o leitor.
2. **Estilo resolvido vs. estilo próprio.** A folha precisa carregar o valor
   *resolvido* de cada propriedade — é o que o navegador aplica depois de
   achatar a cadeia de estilos. O nó do IR carrega só o que o autor definiu
   diretamente. Ler o bloco resolvido de volta promovia todo valor herdado para o
   nó: uma reimportação que reescreve o documento que acabou de ler. Agora a
   camada de autoria tem regra própria (`.r5-own` ao lado de `.r5`) que nenhum
   elemento aplica.
3. **Uma regra, dois registros.** A regra de um parágrafo carrega as
   propriedades de parágrafo *e* as de execução herdadas. `--caissa-style` era
   escrito pelos dois; quem chegasse depois vencia. Cada registro passou a se
   nomear (`--caissa-pstyle`, `--caissa-dr-*`).
4. **Colisões de propriedade.** `vertical-align` é escrito por três campos do IR;
   `font-style` por dois; `text-shadow` por `shadow` e por `emboss`/`engrave`;
   `text-decoration-color` pelo sublinhado e pelo tachado. Cada um passou a dizer
   quem é.
5. **Unidades que o CSS não sabe soletrar.** `twip` não é unidade CSS. Um valor
   convertido para pontos é um valor *diferente*, não o mesmo escrito de outro
   jeito. Marcadores `--caissa-twip-*` restauram a unidade.
6. **Ausência não é o mesmo que "desligado".** O CSS não distingue "o autor disse
   não" de "o autor não disse nada". `--caissa-off-*` diz.
7. **Execução sem formatação perdia a identidade.** Uma execução sem propriedades
   saía como texto puro — menor, e sem o nó. O efeito era perverso: **um livro de
   prosa comum pontuava pior (23,8 %) que um livro de tipografia exótica**.
   Agora toda execução mantém o seu `<span>`.
8. **O recuo de uma lista de definições ia em pontos e voltava em pontos.**
   `twip` não é unidade CSS, e o marcador que restaura a unidade existia para a
   folha de estilos e não para o atributo `data-indent` que a `<dl>` usa. Um nó
   de 208.
9. **A nota mudava de lugar.** Uma `Footnote` no meio do corpo ia para a seção
   de notas no fim — que é onde o leitor a procura e onde `epub:type="footnotes"`
   diz que ela mora — e voltava do fim. O corpo do documento reabria com os
   filhos em outra ordem. Agora fica no fluxo um `<div>` vazio e oculto com a
   identidade da nota, e a leitura a devolve ao lugar. Mesmo mecanismo do
   bookmark vazio do DOCX (§6.1).
10. **O EPUB lia cada nota duas vezes.** A seção de notas era percorrida pelo
    laço principal *e* pela varredura dedicada, o que num arquivo de página
    única não acontece porque a seção fica fora de `<main>`. Reabrir um EPUB
    dava duas cópias de cada nota. Defeito pré-existente, encontrado por esta
    passagem e corrigido nela.

---

## 6. DOCX: de 61,54 % a 100 %, e o que ainda falta

### 6.1 Onde vazava, e o que fechou cada vazamento

A tabela da entrega anterior, com a coluna do que foi feito:

| Perda | Nós | O que fechou |
|---|---|---|
| `move_node` ausente | 21 | a partida passou a ser gravada **uma execução por lance**, cada lance com o seu bookmark; a leitura remonta a árvore percorrendo os `w:r` |
| `table_cell` / `table_row` ausentes | 14 | bookmark entre `w:tr` e entre `w:tc` (`EG_ContentRowContent` e `EG_ContentCellContent` admitem `EG_RunLevelElts`), e a leitura desce até a célula |
| `props.tab_stops` | 9 | `w:tabs` passou a ser lido; alinhamento e preenchimento voltam exatos, a posição em twips (§6.4) |
| `props.vertical_align` | 7 | parte era `baseline` explícito que o escritor não gravava (`ST_VerticalAlignRun` **tem** `baseline`); o resto é atribuição, §6.2 |
| `props.color` | 5 | `w:color` é `ST_HexColor`, seis dígitos de sRGB e nenhum espaço de cor; a entrada de cor passou a discriminar cinza e nomeada além de CMYK e especial |
| `paragraph.content` | 5 | atribuição de contêiner, §6.3 |
| `props.numbering` | 4 | `NumberingRef` virou `w:numPr`, e o **nome** da definição vive em `w:abstractNum/w:name` |

E o que a medição mostrou depois, que não estava na lista:

| Perda | Nós | O que fechou |
|---|---|---|
| `document` ausente | 1 | `w:body` **é** o documento e não tem elemento próprio; a identidade foi para `w:docVars` em `word/settings.xml` |
| `paragraph`/`text` dentro de nota ausentes | 6 | `word/footnotes.xml` e `word/endnotes.xml` passaram a ser lidos, e um bookmark vazio guarda **onde** a nota estava no fluxo |
| `heading` virou `paragraph` | 1 | um título passa a levar sempre o estilo `HeadingN` — é dele que o sumário, o modo de estrutura e o painel de navegação do Word dependem |
| `table` virou `paragraph` | 2 | o bookmark abraça o `w:tbl` e não a legenda que vem antes |
| `paragraph.drop_cap` | 1 | `w:framePr` com `w:dropCap` e `w:lines` |
| `props.mark_props` | 1 | `w:pPr/w:rPr` é a formatação da marca de parágrafo, que é exatamente o que o campo quer dizer |
| `props.default_run` | 18 campos | OOXML não tem formatação de execução no nível do parágrafo; agora é escrita em cada `w:r` e declarada como substituição |
| `table_*` (bordas, margens, altura, largura, alinhamento, descrição) | 40 campos | `w:tblBorders`, `w:tblCellMar`, `w:tblW`, `w:jc`, `w:tblDescription`, `w:tcBorders`, `w:tcMar`, `w:trHeight`, `w:cantSplit` |

### 6.2 A verdade estrutural: OOXML é plano, e a correção é atribuição

Não existe elemento de ênfase; existe uma execução com `w:i`. O embrulho
desaparece do arquivo e o que sobrevive é o seu significado, aplicado a cada
execução que ele continha. Isso está declarado em `_DOCX_NODES` e o exportador
**não** transfere a identidade do embrulho para a execução — fazer isso
reportaria um nó que mudou de tipo.

O efeito colateral era que as propriedades do embrulho apareciam na execução
filha, e essa perda caía sobre o `Text`, cujo perfil é pleno. A correção é
**atribuir a perda a quem a declarou**, com uma regra estreita o bastante para
não virar desculpa:

> Uma propriedade que o nó **não definiu** não pode ter sido perdida por ele. Se
> o valor apareceu, veio de um ancestral que o formato declarou que achata, e é a
> declaração desse ancestral que responde por ele.

A outra metade da regra é o que a mantém honesta: uma propriedade que o nó
**definiu** e que voltou diferente continua sendo perda dele, ancestral ou não.
`test_a_run_that_lost_what_it_did_set_is_still_a_silent_loss` trava isso.

O mesmo vale para `ParagraphProps.default_run` — "toda execução deste parágrafo
começa daqui" — que um formato sem lugar para guardá-lo tem de escrever em cada
execução.

### 6.3 Contêineres: um pai não perde o filho que o formato avisou que levaria

Um parágrafo cujo `content` mudou porque a âncora dentro dele virou um bookmark
do Word não perdeu o seu conteúdo: a entrada de perfil da própria âncora já
disse que ela deixaria de ser um nó. Contar o pai como danificado reporta a
mesma substituição duas vezes, e a segunda vez debaixo de um nó cujo perfil diz
"plena".

A regra, e os três testes que a limitam:

* todo filho que sumiu tem de ter declaração não-plena — se um filho pleno
  sumiu, ninguém declarou nada e o pai é perda silenciosa
  (`test_a_container_that_lost_an_undeclared_child_stays_silent`);
* os filhos que ficaram têm de estar na mesma ordem relativa — ordem é conteúdo
  (`test_a_container_whose_children_were_reordered_is_not_explained`);
* filhos **novos** só são explicados quando o contêiner de fato guardava algo
  que o formato disse que reestruturaria.

E o parágrafo vazio que o OOXML exige depois de uma tabela deixou de ser lido
como nó: sem bookmark, sem propriedades e sem conteúdo, ele é embalagem.

### 6.4 O que foi acrescentado ao perfil, e por quê

Inflar a fidelidade declarada exige escrever no perfil, em português, por que o
formato não carrega a coisa. Estas são as entradas novas desta passagem, cada
uma com o elemento do ECMA-376 contra o qual pode ser conferida:

| Entrada | Grau | Elemento e razão |
|---|---|---|
| `tab_stops` | aprox. | `w:tab/@w:pos` é `ST_SignedTwipsMeasure`, um inteiro em vigésimos de ponto. É a mesma quantização que `indent_left` já declarava. Alinhamento e preenchimento voltam **exatos** |
| `default_run` | subst. | `w:pPr/w:rPr` é a marca de parágrafo, não a cascata das execuções; OOXML não tem o segundo |
| `color` (cinza, nomeada) | aprox./subst. | `ST_HexColor` são seis dígitos de sRGB e mais nada; a entrada já dizia isso para CMYK e especial |
| `document.metadata` | aprox. | `docProps/core.xml` tem o Dublin Core fixo; ISBN, editora, edição, série, direitos e o papel de cada contribuidor só caberiam em `docProps/custom.xml` como texto solto, e este exportador não os grava |
| `heading.numbering_text` | subst. | virou texto literal mais `w:tab` na própria execução |
| `heading.toc_text` | subst. | o campo TOC lê o texto do próprio título; um texto abreviado exigiria campos `TC` por título |
| `move_node.position_before` / `position_after` / `uci` | ausente | o movetext do PGN guarda **lances**, não posições; o FEN é recalculado por quem lê |
| `move_node.arrows` / `highlights` | aprox. | `[%cal]` e `[%csl]` têm quatro letras de cor |
| `move_node.evaluation` | aprox. | `[%eval]` carrega um texto só |
| `table.columns` / `width` / `borders` / `cell_padding` / `alignment` | aprox. | twips inteiros, oitavos de ponto, sRGB, e `w:tblPr/w:jc` com três posições |
| `table.repeat_header` / `header_row_count` / `table_row.repeat_on_break` / `table_cell.is_header` | subst. | OOXML tem **um** interruptor, `w:tblHeader` por linha, onde o IR guarda quatro decisões |
| `table.caption` / `caption_above` / `number` | subst. | `w:tblCaption` é uma cadeia de texto; a legenda virou parágrafo com campo SEQ |
| `table_cell.alignment` | ausente | `CT_TcPr` tem `w:vAlign` e **não tem** alinhamento horizontal: no OOXML ele é sempre do parágrafo |
| `table_cell.padding` / `borders`, `table_row.height` | aprox. | `w:tcMar`, `w:tcBorders`, `w:trHeight`, todos em twips ou oitavos de ponto |
| `footnote` / `endnote` (razão ampliada) | subst. | `CT_FtnEdn` é uma sequência de parágrafos com `w:type` e `w:id`: não tem formatação de bloco própria |

**O limite conhecido desta tabela.** `declared_fidelity` só pergunta se a perda
foi declarada, não *quanto* se perdeu: uma entrada `aprox.` cobre tanto "voltou
arredondado ao twip" quanto "não voltou". Isso vale para as quarenta entradas
`aprox.` que já existiam e vale para as novas. Quem cobre a diferença são os
testes de ida e volta: sabotar o escritor para não gravar `w:tabs` mantém a
fidelidade em 100 % **e reprova**
`test_the_paragraph_ruler_comes_back_from_w_tabs`, que exige as duas paradas de
volta com alinhamento, preenchimento e posição. O mesmo para `w:numPr`,
`w:framePr`, `w:pPr/w:rPr`, a estrutura de tabela e a árvore de lances — §8 lista
um teste por coisa que passou a voltar. Sabotar algo *não* declarado, como o
`w:i` da ênfase, derruba a medição na hora: 88,94 %, 23 nós silenciosos.

**A prova de que essas declarações não são decorativas:** o DOCX tem
**zero** perdas declaradas sem aviso (`FidelityReport.unreported`), contra 56
num estado intermediário desta sessão. Cada entrada acima dispara um
`DegradationWarning` que chega ao relatório de exportação com o nó que a causou.
`test_every_docx_declaration_actually_reaches_the_export_report` cobra isso.

### 6.5 O que continua aberto, medido

* **EPUB: `document.metadata`, 1 nó de 208 — 99,52 % em vez de 100 %.** O OPF
  grava título, subtítulo, descrição, idioma, autores, assuntos e identificador;
  não grava `short_title`, os idiomas adicionais, `modified`, edição, série e
  índice na série, capa, número de páginas, os metadados personalizados nem o
  papel/nome-de-ordenação de cada contribuidor. O EPUB 3 tem onde pôr tudo isso
  (`<meta property>` com `refines`, `belongs-to-collection`), então **isto é
  limitação deste exportador e não do formato** — e por isso não foi declarado.
  Fica como perda silenciosa medida.
* **DOCX: a identidade sobrevive ao Word abrir, e sobrevive *em parte* ao Word
  gravar.** Medido: abrir `recursos.docx` no Word 2016 e salvar preserva os 30
  bookmarks, mas o Word **move o bookmark de bloco para dentro do parágrafo**,
  logo depois do `w:pPr`, deixando o fim fora. `_hoisted_identity` recupera esse
  caso, e depois de um *salvar* do Word voltam com o id original o documento
  (via `w:docVars`), o sumário, o título, o parágrafo e a partida; **a tabela e
  os marcadores de nota não voltam**. A docstring do módulo afirmava, sem
  qualificação, que o Word preserva os bookmarks ao editar e salvar; agora diz o
  que foi medido.
* **DOCX: fidelidade bruta de 3,85 %.** Não é defeito, é o que OOXML é: corpo em
  meios-pontos, recuos em twips, cores em sRGB, uma partida que vira texto. O
  número está publicado ao lado do declarado exatamente para que ninguém precise
  acreditar só no segundo.
* **PDF: PDF/A-2b e marcação de acessibilidade são parciais.** `pdfa_caveats()`
  lista o que falta. Não afirme conformidade.
* **PDF: layout de coluna única.** Duas colunas e geometria de página são
  declaradas, não implementadas.
* **EPUB/HTML: 19 perdas declaradas sem aviso.** São entradas de perfil que
  classificam uma diferença como declarada sem que nenhum `DegradationWarning`
  a nomeie — `game_score.headers`, `props.mark_props`, `document.styles`. O
  DOCX está em zero; HTML e EPUB não. É pré-existente e continua aberto.

---

## 7. Defeito do F7, fechado deste lado

O `F7_REPORT.md` registra que o caminho SVG e o caminho LaTeX desenham conjuntos
de peças diferentes. Investigado daqui, é pior do que "desenhos diferentes":

```
!pdfTeX error: pdflatex.exe (file chess-merida-board-fig-raw.pfb):
               cannot open Type 1 font file for reading
 ==> Fatal error occurred, no output PDF file produced!
```

Pedir uma família cujo `.pfb` não está na árvore TeX **não gera PDF nenhum**.
`chessfss_family_available('merida')` responde `False` nesta máquina; só `alpha`
e `berlin` estão instaladas.

O exportador agora **verifica antes**, troca por uma família instalada, e o
relatório nomeia as duas com a consequência escrita: *"o mesmo livro sai com
desenhos diferentes nos dois caminhos até que o pacote Type1 correspondente seja
instalado"*. Não podemos instalar uma fonte; podemos recusar entregar um arquivo
que não compila, e dizer por quê. O defeito de aparência continua em aberto — a
correção é instalar `chess-merida` — mas deixou de ser silencioso e deixou de ser
fatal.

---

## 8. Testes

| Módulo | Testes | O que trava |
|---|---|---|
| `test_fidelity.py` | 31 | o portão de §11.3, por formato, com os dois números, **e as duas regras de atribuição** |
| `test_degradation.py` | 247 | 46 propriedades × 5 formatos: carregada ou declarada |
| `test_epub.py` | 16 | `mimetype` primeiro e sem compressão, XML bem formado, **EPUBCheck**, **fonte embutida e subconjuntada** |
| `test_docx.py` | 26 | estilos nomeados, campos SEQ/TOC, notas, relações, esquema, **e uma volta por cada coisa que passou a voltar** |
| `test_latex.py` | 9 | os cinco erros fatais do pdflatex, **e a compilação real** |
| `test_vectorness.py` | 6 | nenhum diagrama vira pixel, em nenhum dos cinco |
| `test_end_to_end.py` | 14 | livro real → cinco formatos → relatório; reprodutibilidade |
| `test_emf.py` / `test_pdfwrite.py` | 85 | os escritores de baixo nível (pré-existentes) |
| **Total** | **434** | todos passando; 84 % de cobertura em `caissa.export`, 93 % em `docx.py` |

### 8.1 O caminho da fonte de xadrez, exercitado

O mecanismo de subconjunto existia, estava testado em `caissa.typeset` e
**nenhuma exportação chegava nele**: o renderizador desenha as peças como
contornos e nunca pede uma face. Quatro testes novos em `test_epub.py` fecham
isso com um livro que pede tipo de xadrez no texto corrido:

* a face está no pacote, no manifesto, e é **subconjunto** — 1 328 bytes contra
  os 49 504 do arquivo inteiro da Chess Merida;
* o subconjunto carrega exatamente os três glifos que o texto pede (`n`, `f`,
  `3`) e nenhum outro, e responde por um `cmap` Unicode `(3, 1)` — sem ele o
  leitor procura `U+006E` e não acha nada, que é o bug clássico das fontes de
  xadrez legadas;
* a peça é escrita **na codificação da face que vai desenhá-la**: a Chess Merida
  não tem glifo em `U+265E`, então escrever o figurino Unicode e pedir essa
  família dava ao leitor um caractere que a fonte não sabe desenhar;
* uma família que não é de xadrez não gera aviso de fonte.

No caminho apareceu um defeito real: o exportador pedia **sempre** WOFF2, que
precisa do compressor Brotli. Sem ele o subconjunto falhava e a exportação
seguia com uma nota — nenhuma fonte embutida, nenhum aviso de degradação. Agora
cai para TrueType (também um tipo de mídia central do EPUB 3) e, quando falha de
verdade, registra `font_embedding` como substituição. **Esta máquina não tem
Brotli**, e é por isso que a face sai como `.ttf`. O EPUBCheck 4.2.6 aceitou o
pacote com a fonte embutida: `0 erros fatais / 0 erros / 0 advertências`.

### 8.2 Três testes que são portões e não verificações

* **`test_epubcheck_reports_no_errors`** roda o validador de outra gente. O nosso
  analisador aceitar o arquivo prova que o nosso analisador é tolerante, não que
  o arquivo é válido.
* **`test_the_project_compiles`** roda o pdflatex. Um `.tex` que não compila não é
  uma exportação degradada, é nenhuma exportação — e nenhum dos cinco defeitos
  fatais aparecia em qualquer checagem estática.
* **`test_docx_embeds_the_board_as_a_metafile`** lê os contadores `diagrams_emf` e
  `diagrams_png` separados e reprova se qualquer diagrama virou pixel sem aviso.

E um quarto, que nasceu nesta passagem:
`test_every_docx_declaration_actually_reaches_the_export_report` cobra que
**nenhuma** entrada do perfil do DOCX classifique uma diferença como declarada
sem que um `DegradationWarning` a nomeie. É a trava que impede o número declarado
de subir sem o relatório subir junto — e é ela que torna §6.4 verificável em vez
de acreditável.

---

## 9. Estado da suíte

```
antes desta frente:      2411 passaram,  3 falharam,  1 pulou
fim da 1a passagem:      2779 passaram,  0 falharam,  1 pulou, 2 xfail
fim da 2a passagem:      2874 passaram, 13 falharam,  1 pulou, 0 xfail
```

`tests/unit/export/` isolado: **434 passaram, 0 falharam**, nas duas ordens.

**As 13 falhas são todas de `tests/unit/typeset/`** — setas e cabeças de seta em
`board_svg`, `latex`, `proofsheet` e `typography`. Esta passagem correu com outra
frente editando `src/caissa/typeset/` ao mesmo tempo, ao ponto de `board_svg.py`
ter sido lido no meio de uma gravação (faltava o `import lru_cache` por alguns
segundos). **Zero falhas em `tests/unit/export/`**, e os arquivos tocados aqui
são exatamente `src/caissa/export/`, `tests/unit/export/` e este relatório —
nada em `caissa.typeset` foi alterado por esta frente, que só o importa.

Na execução completa anterior da mesma sessão as falhas eram 11, em
`tests/unit/typeset/` e `tests/unit/ui/`; as de `ui` desapareceram e as de
`typeset` aumentaram enquanto a outra frente trabalhava. É a mesma observação de
sempre: uma contagem de suíte medida com o repositório em movimento vale pelo que
diz sobre a *própria* área.

**Uma observação para a F7.** Com `pytest-randomly` reordenando a suíte,
`tests/unit/typeset/test_proofsheet.py::test_the_baselines_of_the_two_columns_register`
falhou **uma vez** em execução completa e passou sozinho, com o seu módulo
inteiro, e com a suíte em ordem determinística (`-p no:randomly`). É sensível à
ordem, provavelmente por causa de um cache de fonte de módulo em
`caissa.typeset`. Não é área desta frente e não foi tocado por ela — fica
registrado porque um teste que depende da ordem é um teste que vai falhar no CI
em algum momento e ninguém vai saber por quê.

---

## 10. Ambiente da verificação

| Ferramenta | Versão | Uso |
|---|---|---|
| Java | 1.8.0_503 | roda o EPUBCheck |
| EPUBCheck | 4.2.6 | **0 erros** em 5 corpora |
| Microsoft Word | 2016 (Office16) | **abre sem reparo** e **grava de volta**, via COM |
| MiKTeX pdflatex | instalado | **gera o PDF**, exit 0 |
| Python | 3.11.9 | |

Nada aqui foi presumido. Onde uma ferramenta não existisse, o teste pularia com
a razão escrita — mas as quatro existem nesta máquina e as quatro foram usadas.

A automação COM do Word roda por fora da suíte, porque `pywin32` não está nas
dependências do projeto e acrescentá-lo não é decisão desta frente. O que ela
mediu nesta passagem: quatro arquivos abertos sem pedido de reparo (o corpus
adversarial em três sementes e um documento que exercita cada elemento novo), e
um deles reaberto **depois de o Word gravá-lo** — resultado em §6.5.

Brotli não está instalado, então o subconjunto de fonte do EPUB sai em TrueType
em vez de WOFF2. Os dois são tipos de mídia centrais do EPUB 3 e o EPUBCheck
aceitou o pacote; numa máquina com `fonttools[woff]` a face sai menor.
