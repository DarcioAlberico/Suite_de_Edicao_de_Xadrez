# F2 · ciclo 1 — ingestão de PDF unificada, do arquivo ao Document IR

> **Data:** 2026-09-11 · **Frente:** F2 (a única nunca iniciada do `ROADMAP.md`) ·
> **Item:** HANDOFF §4.4
> Ambiente: `.venv` na raiz, Python 3.11.9, PyMuPDF 1.28.2, torch 2.11.0+cu128, RTX 5060.
> Todo número desta página traz ao lado o comando que o produziu.
> Acervo: `C:\Python-Chess2\ChessVisionOFF_Puro\PDF` (`CORPUS.md` §0, 46 arquivos).

---

## 0. O que este ciclo entrega

1. **O pacote `caissa.ingest.pdf` existe e produz Document IR** — 5.754 linhas em nove
   módulos, 166 testes em `tests/unit/ingest`, todos verdes, `ruff` e `mypy` limpos no
   pacote. As três implementações que o HANDOFF mandava unificar (`pdf_io.py` +
   `pdf_text.py` do tronco, `pdf_service.py` do Editor, `extract.py` do PDFimport) foram
   absorvidas com as medições que as justificavam, e cada módulo diz de onde veio e o que
   mudou (§1).
2. **Os três portões objetivos da F2 fecham, cada um com prova de vitalidade** (§2):
   primeira página de um livro de 500 páginas em **10–21 ms** (meta ≤ 2 s); memória
   estável em varredura completa (**+0,4 MB** entre a página 40 e a 240, contra
   **+1.198 MB** na versão sabotada que o mesmo medidor apanha); ordem de leitura
   correta em **40 de 40** páginas sintéticas de duas colunas, e o portão reprova a
   sabotagem que inverte as colunas.
3. **O quarto portão — o crítico compara o IR com o PDF lado a lado — foi feito por mim,
   em cinco páginas de quatro livros diferentes, e está fixado em `test_corpus.py`** (§3).
   Cada uma exigiu correções que a suíte sintética não pedia.
4. **Rodou no acervo inteiro, 552 páginas de 46 livros, sem uma falha** (§4): 8,6
   páginas/s pela camada de texto; com a via raster do tronco e o classificador F4 na GPU,
   1,6 páginas/s e **911 diagramas localizados e lidos**, 109 com lado a jogar vindo do
   texto.
5. **Cinco defeitos de outras frentes apareceram ao ligar a cadeia de ponta a ponta** (§5)
   — a lição do HANDOFF §7 repetida: um sistema testado só por partes não foi testado.
   Todos corrigidos, com teste que reprova sem a correção.

> **O que este ciclo NÃO faz.** Não há OCR ligado por padrão (a F5 é injetável pelo
> `OcrProvider`, e está testada com um motor falso); páginas cuja camada de texto o nível 0
> rejeita viram imagem com o motivo na proveniência. Não há `GameScore`: os lances entram
> como parágrafos de estilo `Movetext` com `PieceGlyph` — transformá-los em árvore é da F6.
> E a leitura lado a lado foi minha, não de um crítico independente (§6).

---

## 1. O que foi absorvido, e de onde

| módulo | origem | o que ficou | o que mudou |
|---|---|---|---|
| `geometry.py` | Editor §48 (dois espaços de coordenadas) | o modelo de dois espaços | **a fórmula**: a origem da CropBox que o Editor somava está errada — §5.1 |
| `document.py` | tronco `pdf_io.py` (S-61, S-331), PDFimport `open_pdf` | abrir uma vez e emprestar; recusar cifrado e não-PDF em pt-BR | um `RLock` por documento; `sample_indices` sem sorteio |
| `render.py` | tronco `render_pdf_page`, Editor `_BOARD_*_CACHE` | array próprio e gravável, `alpha=False` | cache LRU **em bytes**, honrando `cache.page_cache_mb` da F0 (que ninguém honrava) |
| `textlayer.py` | PDFimport `_span_style`, `_stroke_bold_fonts`, `chessfig.py` | negrito por flag + nome + **tinta**; figurinos por contexto; símbolos Informator | linhas mistas (dígito + glifos de tabuleiro) são partidas em duas — §5.4 |
| `captions.py` | tronco `pdf_text.py` (S-16, S-43, S-129, S-217) | lado a jogar em 6 idiomas, placement dominante, grupo como unidade, fólio por consecutividade | `№79.` aceito sem `n`; grupo vem inteiro; lances nunca reclamam legenda; `W?`/`B` |
| `paragraphs.py` | PDFimport `_starts_paragraph`, `_page_rows`, `_hyphen_wrap`, `_split_move`, `_continues` | medida justificada, hifenização, lance partido, continuação entre páginas | linha por **baseline** e sem ordem; regra de "a palavra caberia"; fronteira de bloco só com evidência — §3 |
| `importer.py` | novo | — | duas passadas, memória constante, IR com proveniência em cada nó |
| `finders.py` | tronco `detection` + F4 `BatchedClassifier` | os detectores e o classificador do produto | embrulhados no `DiagramFinder` do importador |
| `save.py` | Editor §43/§60 | gravação atômica com cancelamento (121.495 `write()`, 2 bytes no destino) | nada |

Layout já existia em `caissa.ocr.layout.analyze` (colunas, XY-cut, mobília, notas,
legendas) e **não foi duplicado**: a F2 chama e corrige (§5.5), como a SPEC pede.

---

## 2. Os três portões, com sabotagem

`tests/unit/ingest/test_gates.py` — 6 testes, 14,6 s.

```
.venv\Scripts\python.exe -m pytest tests\unit\ingest\test_gates.py -q
```

### 2.1 Primeira página de um livro de 500 páginas ≤ 2 s

Livro sintético de 500 páginas (1,27 MB, dois parágrafos por página). Abrir, renderizar a
página 0 a 150 DPI e extrair sua camada de texto, três execuções:

| execução | abertura | primeira página completa |
|---|---|---|
| 1 (fria) | 11,5 ms | **21,1 ms** |
| 2 | 0,9 ms | 9,8 ms |
| 3 | 0,9 ms | 9,5 ms |

Cem vezes abaixo da meta, porque `pymupdf.open` só lê o `xref` e o `PdfDocument` nunca
percorre as páginas ao abrir. **Sabotagem:** um `open_pdf` que toca todas as páginas
(`get_text` + `get_pixmap` a 200 DPI) leva **1,27 s** no mesmo livro, e o portão o vê.

### 2.2 Memória estável em varredura completa

Livro sintético de 240 páginas, cada uma com um raster de 640×560 e um parágrafo.
Working set do processo (`GetProcessMemoryInfo`), depois de `gc.collect()` e de esvaziar o
*store* do MuPDF (`TOOLS.store_shrink(100)`), para medir **o que o importador retém** e
não o que a biblioteca cacheia:

| ponto | working set |
|---|---|
| página 40 da segunda passada | 177,9 MB |
| página 240 | 178,3 MB |
| **crescimento em 200 páginas** | **+0,4 MB** (limite do portão: 25 MB) |

**Sabotagem:** um `diagram_finder` que guarda o pixmap de cada página (1,4 MB cada)
cresce **+1.198 MB** no mesmo intervalo e o portão reprova. O medidor vê vazamento.

### 2.3 Ordem de leitura em 100 % das páginas de duas colunas

Quarenta páginas sintéticas de duas colunas com títulos que atravessam as colunas,
notas de rodapé, cabeçalho corrente, fólio e hifenização, todas com a ordem esperada
conhecida: **40 de 40** páginas na ordem certa, parágrafo por parágrafo, texto idêntico.
**Sabotagem:** invertendo a ordem que o XY-cut devolve, 0 de 6 páginas — o portão
reprova.

Duas coisas o portão me ensinou enquanto o construía: a primeira versão do gerador de
páginas quebrava linhas por **contagem de caracteres**, o que deixava linhas com folga em
pontos e fazia as regras de parágrafo (certas) ver quebras escolhidas onde não havia;
e a nota de rodapé de duas linhas soltas era irreal pelo mesmo motivo. O gerador agora
compõe por largura medida (`get_text_length`), como um tipógrafo.

---

## 3. A leitura lado a lado (o quarto portão)

Renderizei a página e comparei bloco a bloco com o IR (`benchmarks/bench_ingest.py --dump`
grava o mesmo material para qualquer livro). Cada página abaixo está fixada em
`tests/unit/ingest/test_corpus.py` (marcador `golden`, 6 testes, 3 s).

| livro · página | o que a página tem | o que o IR tem depois deste ciclo | o que precisou mudar |
|---|---|---|---|
| **Dvoretsky 2025 p. 202** (E1, duas colunas, Chess-Merida + SemFig) | 2 diagramas com `4-12 / 4/2 / W?` embaixo; cabeçalho de estudo; prosa; análise em negrito; título de seção em negrito no pé | 2 `Diagram` (FEN exata, `label="4-12"`, `stipulation="Brancas jogam"`), **11 blocos na ordem impressa**, `Heading` no pé | rótulos de coordenada fora do fluxo; legenda consumida pelo diagrama; `4-10` é rótulo, não `number=4`; título negrito no tamanho do corpo promovido; **"4/2. G.van Breukelen 1969" separado de "Is it possible…"** exigiu a regra de abertura de frase — sem medida justificada, indentação e maiúscula decidem |
| **Dvoretsky p. 206→207** | análise que **continua na página seguinte** (`3.Ka2` / `Qb3+! 4.Qxb3 axb3+`) | um único parágrafo `Movetext` com `provenance.note = "continua até a página 206"` | a linha de lances no alto da coluna era chamada de legenda pela geometria; lances nunca são legenda |
| **Polgar 5334 pp. 300–302** (SkakNew-Diagram) | 6 problemas por página, número em cima de cada um, título corrente | **18 `Diagram` lidos exatos** (FEN conferida casa a casa no 1699), numerados 1699–1716 **na ordem impressa (por coluna)**, zero prosa | catálogo F3-A (§5.3); nível 0 (§5.4); linhas mistas; ordem de entradas por coluna |
| **Nunn, Minor Piece Endings p. 150** (E2, camada OCR de terceiros) | duas colunas, 4 parágrafos à esquerda, diagrama e 3 blocos à direita | **os 5 parágrafos inteiros**, na ordem | a camada abre bloco novo a cada poucas linhas sem motivo; a fronteira de bloco virou **evidência**, não prova — só conta com linha curta ou indentação |
| **Chernev, Melhores Finais de Capablanca p. 121** (pt-br, PDF do Word) | figurinos MS Gothic soltos, linhas tabulares `21 ♖f1-d1`, parágrafos sem indentação e sem entrelinha | **14 blocos idênticos ao impresso**, 4 `Movetext` | linha por baseline (o `♖` tem ascendente diferente); linha sem ordem esquerda→direita (o glifo vem depois no fluxo); "colunas" inventadas pelas células da tabela (§5.5); `22` do pé é lance, não fólio (§5.5); **"a palavra seguinte caberia"** para a quebra sem indentação |

O que a leitura ainda mostra errado, e está registrado em vez de escondido:

- No Chernev, 3 das 12 páginas amostradas mantêm uma tabela de lances como **três
  colunas** (as células de lance são largas o bastante para passar no teste de largura).
  Duas variantes mais agressivas do teste foram medidas e **descartadas** porque
  destruíam páginas reais de duas colunas (docstring de `_columns_are_real`).
- Uma nota "8-9 W?" que caia a mais de 60 pt do **tabuleiro e dos rótulos** não é
  associada — o raio é o do tronco, medido em livros sem rótulos, e o diagrama passou a
  incluir os rótulos justamente para alcançar as legendas do Dvoretsky a 72 pt.

---

## 4. O acervo inteiro

```
.venv\Scripts\python.exe benchmarks\bench_ingest.py --sample 12            # camada de texto + via vetorial
.venv\Scripts\python.exe benchmarks\bench_ingest.py --sample 12 --raster   # + detector do tronco + F4 na GPU
```

Doze páginas espaçadas por livro (cobertura de capa excluída), 46 livros, 552 páginas.
Relatórios: `benchmarks/reports/ingest_20260911_184126.json` (texto+vetor) e
`ingest_20260911_180648.json` (raster, rodado antes das correções de §3 — os números de
diagrama não mudam com elas; os de parágrafo estão no primeiro).

| | texto + via vetorial | + via raster (GPU) |
|---|---|---|
| páginas | 552 | 552 |
| tempo | 64,2 s (**8,6 páginas/s**) | 344 s (1,6 páginas/s) |
| mediana por página (2ª passada) | 59 ms | — |
| origem: camada de texto / imagem / rejeitada | **390 / 145 / 17** | idem |
| parágrafos · títulos · legendas · notas · blocos de lances | 5.491 · 833 · 367 · 68 · 715 | — |
| diagramas localizados / lidos | 74 / 74 (Dvoretsky 20, Polgar 54) | **911 / 911** |
| com lado a jogar declarado no texto | 25 | **109** |
| páginas com ≥ 3 colunas detectadas | 17 | — |
| falhas | **0** | **0** |

**A razão de descontinuidade** — fronteiras entre parágrafos consecutivos em que o
primeiro não termina em pontuação e o segundo abre em minúscula, que é como um parágrafo
partido ou fora de ordem se parece de fora — caiu de **0,217** na primeira rodada para
**0,147** com as correções de §3 (1.094 de 7.439 fronteiras). É uma régua aproximada,
não verdade de campo: livros quebram parágrafo no meio de frase para pôr um diagrama. Os
piores continuam sendo os livros antigos e irregulares — Mieses 1938 (0,354), Kmoch 1936
(0,284, tabelas de torneio), Gunderam 1961 (0,221).

**O que a via raster acrescenta e o que custa.** 911 diagramas em 552 páginas, 0 erros;
o tempo é dominado por renderizar a 220 DPI e pelo detector do tronco em CPU, não pelo
classificador. A vazão de 0,0903 s/diagrama da F4-GPU foi medida com seis processos; aqui
é um. A confiança dos diagramas raster é `min_confidence` do classificador e a via é
`RecognitionPath.NEURAL`; os vetoriais saem a 1,0 (`VECTOR`, Merida) ou 0,85 (`skak`,
codificação **inferida** e conferida, não verificada glifo a glifo).

**O que o nível 0 da F5 decide e o importador honra.** 17 páginas rejeitadas em 10
livros (AAGAARD 2, Gaprindashvili 1, Karpov 1 2, Polgar 2, Secrets 1, Anand 2, Журавлев
3, Nunn 1+2, Yusupov 1). A que vale registrar para a F5 é a **página de soluções do
Yusupov** (`p. 701`: "55 % das palavras impronunciáveis"), que é 90 % notação e cujos
lances o léxico não reconhece como palavras. O importador as grava como imagem com o
motivo; não confia numa camada que a F5 recusou.

---

## 5. Cinco defeitos de outras frentes, encontrados pela cadeia inteira

Nenhum aparecia nos testes das frentes donas. Todos têm teste que reprova sem a correção.

### 5.1 A fórmula dos dois espaços de coordenadas (F3-A, Editor §48)
`get_text` devolve caixas no espaço **não girado**; `page.rect` é o girado. O Editor somava
a origem da CropBox em espaço de escrita, e o `vector_detect.py` copiou. Medido em
`test_geometry.py` contra a **tinta renderizada**, em 4 rotações × CropBox deslocada ×
MediaBox com origem fora de (0, 0): a conversão certa é `texto × rotation_matrix`, **sem
termo de origem**; com ele, o tabuleiro cai **40 pt** longe da tinta numa página girada
com CropBox deslocada. `vector_detect` corrigido; `test_roundtrip.py` ganhou o teste
contra a tinta, que **reprova com a fórmula antiga** (3 de 3). Latente porque 18.766 das
18.767 páginas do acervo não têm rotação.

### 5.2 Dois tabuleiros lado a lado em alturas diferentes (F3-A)
Dvoretsky p. 203: o tabuleiro esquerdo começa 36 pt abaixo do direito. Agrupando as
linhas de glifos página inteira, as duas grades se intercalam e nenhuma janela de oito
linhas consecutivas é tabuleiro: **0 de 2 detectados**, e os 16 rótulos de coordenada
entravam na prosa como 16 parágrafos de um caractere. `detect_glyph_boards` agora parte
as células em agrupamentos horizontais antes das linhas. Teste sintético reprova sem.

### 5.3 `SkakNew-Diagram` era figurino no catálogo (F3-A)
O padrão `skaknew` do catálogo apanhava a fonte de **tabuleiro** do Polgar como fonte de
figurino inline, e a via vetorial ficava cega aos 5.334 diagramas do livro. Entrada
`skak_diagram` com a codificação do pacote LaTeX `skak` (`0`/`Z` vazias, `KQRBNP`/`kqrbnp`
nas claras, `JLTAMO`/`jltamo` nas escuras), lida da camada de texto e conferida casa a
casa contra a página. Confiança "inferred", que o detector reporta como 0,85 — honesta:
não foi verificada renderizando a fonte, que não está nesta máquina.

### 5.4 O nível 0 julgava glifos de tabuleiro como prosa (F5)
Numa página do Polgar a camada de texto é 48 glifos de tabuleiro, um número e um título
corrente. Julgada inteira, dava 8 % de palavras de dicionário e era **rejeitada — 11 de
11 amostradas**, para uma camada perfeitamente boa. `assess()` ganhou
`ignore_diagram_fonts=True`: os spans de fontes de **diagrama** do catálogo saem do texto
julgado; os de figurino **não**, porque suas letras são a notação cuja integridade
`mangled_move_ratio` mede. Os 369 testes de `tests/unit/ocr` continuam verdes; o Polgar
passa a 10 de 12 (as 2 restantes são páginas de texto corrido com outro problema).

### 5.5 Dois defeitos no layout compartilhado (F5, `ocr/layout/analyze.py`)
- **Colunas inventadas por células de tabela.** Uma página de partida do Chernev tem
  linhas `28 … ♔b8-b7` em três células; as linhas de prosa, largas, eram excluídas da
  votação de calhas como "linhas que atravessam", e os fragmentos curtos votavam quatro
  colunas. A F2 valida as colunas por **massa de caracteres** e por **largura do texto de
  cada coluna** e reanalisa com uma coluna quando falham (`_columns_are_real`).
- **Todo inteiro na faixa de margem era fólio.** O `22` da última linha tabular de uma
  página do Chernev caía nos 7,5 % de baixo e sumia como número de página. O detector de
  mobília agora registra **onde** os fólios do livro ficam (vigésimos da largura); um
  inteiro fora dessas posições é texto, e um livro que não mostrou fólio em posição
  nenhuma após `min_repeats` páginas não tem fólio na faixa. Teste em `test_layout.py`
  reprova sem.

E um sexto, na F1: `plain_text` **apagava** `PieceGlyph` — um livro em fonte de figurino
indexava cada `Nf3` como `f3`. Renderiza a letra canônica agora, como `Move` faz com a SAN.

---

## 6. O que fica registrado como pendência

1. **Crítica independente.** A leitura lado a lado de §3 foi feita pelo construtor. Pela
   `CRITIC_CHARTER.md` §2.2 a F2 (e a F8 que a consome) exigem comparação com o livro
   original por um crítico com mandato de reprovar; `bench_ingest.py --dump` produz o
   material.
2. **OCR ligado por padrão.** O `OcrProvider` está testado com motor falso e o
   `PageRecognizer` da F5 tem a forma certa; falta a costura (renderizar na resolução
   pedida, converter `OcrResult` com `page_text_from_ocr`) e medir no E8.
3. **`GameScore`.** Os blocos `Movetext` carregam `PieceGlyph` e texto; a F6 tem o
   analisador tolerante e a reparação por legalidade para transformá-los em árvore.
4. **Tabelas de lances como colunas** em 3 páginas do Chernev (§3) e a razão de
   descontinuidade dos livros antigos (§4): precisam de verdade de campo anotada para
   virar portão, e o `CORPUS.md` §5 continua pedindo as 200 páginas.
5. **Soluções densas rejeitadas pelo nível 0** (Yusupov p. 701, §4): decisão da F5; se o
   léxico passar a tratar notação como palavra, o importador herda.
6. **A fonte SkakNew não está nesta máquina**; a codificação foi inferida de um livro. Um
   segundo livro em SkakNew ou o arquivo da fonte fecham a confiança em "verified".
