# F1 — Document IR: relatório de qualidade

**Data:** 2026-09-07 · **Escopo:** `src/caissa/core/model/`, `src/caissa/core/chess/`,
`tests/unit/model/` · **Especificação:** SPEC §5, ADR-0002

---

## 0. Veredito

| Portão | Alvo | Medido | |
|---|---|---|---|
| `mypy --strict` | 0 erros | **0 erros**, 23 arquivos | ✔ |
| `ruff check` | 0 erros | **0 erros** (eram 66 no início) | ✔ |
| `ruff format --check` | 0 arquivos | **0** (eram 6) | ✔ |
| Testes unitários | — | **1 125 passando, 0 falhando** | ✔ |
| Corpus de ida-e-volta | 10 000 nós | **10 001 nós, identidade exata** | ✔ |
| Tipos de nó construídos e round-tripped | 100 % | **49/49 nós + 46/46 objetos de valor** | ✔ |
| Cobertura de linha (model + chess) | ≥ 90 % | **99 %** (3 394 stmts, 8 não cobertas) | ✔ |
| Cobertura de ramo | — | **99 %** (808 ramos, 11 parciais) | ✔ |
| SPEC §5.1–§5.5 expressa no IR | 100 % | **100 % — nenhum item ausente** | ✔ |

Dois defeitos reais foram encontrados e corrigidos (§5). Nenhum item da SPEC §5 ficou
sem expressão no IR; há três desvios de forma, todos deliberados e documentados em §4.

---

## 1. Saída real dos comandos

Tudo abaixo foi executado com `.venv\Scripts\python.exe` nesta máquina.

### 1.1 `mypy --strict`

```
$ .venv/Scripts/python.exe -m mypy --strict src/caissa/core/model src/caissa/core/chess
pyproject.toml: note: unused section(s): module = ['onnxruntime.*', 'torch.*']
Success: no issues found in 23 source files
```

A afirmação do agente anterior ("mypy --strict is clean") **confere**. Foi verificada
antes de qualquer alteração minha e voltou a ser verificada depois.

### 1.2 `ruff`

A afirmação de limpeza **não** cobria o ruff. Na primeira execução:

```
$ .venv/Scripts/python.exe -m ruff check --statistics src/caissa/core/model src/caissa/core/chess
24  RUF001   ambiguous-unicode-character-string
19  PLR2004  magic-value-comparison
 4  D301     escape-sequence-in-docstring
 3  E501     line-too-long
 2  F401     unused-import
 2  PLR0911  too-many-return-statements
 2  PLR0912  too-many-branches
 2  RUF003   ambiguous-unicode-character-comment
 1  I001     unsorted-imports
 1  PLE2515  invalid-character-zero-width-space
 1  PLR0124  comparison-with-itself
 1  RUF002   ambiguous-unicode-character-docstring
 1  RUF100   unused-noqa
 1  SIM102   collapsible-if
 1  UP007    non-pep604-annotation-union
 1  UP037    quoted-annotation
Found 66 errors.

$ .venv/Scripts/python.exe -m ruff format --check src/caissa/core/model src/caissa/core/chess
6 files would be reformatted, 17 files already formatted
```

Durante o trabalho outro agente recalibrou `[tool.ruff.lint]` no `pyproject.toml`
(desligando `RUF001/2/3`, `D100`–`D107` e `PLC0415`), o que baixou o total para 39.
Os 39 restantes foram corrigidos de fato, não silenciados: o único `# noqa` em
`src/caissa/core/{model,chess}` continua sendo o `PLW0603` que já existia para os
contadores de módulo em `ids.py`. Quatro `# noqa` foram acrescentados em
`tests/unit/model/generators.py` — todos em tabelas de despacho do gerador
(`PLR0911`/`PLR0912`: um ramo por tipo de nó), com o motivo escrito na linha.
Estado final:

```
$ .venv/Scripts/python.exe -m ruff check src/caissa/core/model src/caissa/core/chess tests/unit/model
All checks passed!

$ .venv/Scripts/python.exe -m ruff format --check src/caissa/core/model src/caissa/core/chess tests/unit/model
43 files already formatted
```

### 1.3 Testes e cobertura

Cobertura medida com escopo restrito ao front (o `[tool.coverage.run] source` do
projeto abrange `src/caissa` inteiro, o que traria módulos de outros agentes):

```
$ .venv/Scripts/python.exe -m pytest tests/unit/model -q --cov-config=<f1.ini> --cov --cov-report=term-missing

Name                                       Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------------
src\caissa\core\chess\__init__.py              4      0      0      0   100%
src\caissa\core\chess\fen.py                 167      0     78      0   100%
src\caissa\core\chess\notation_tables.py     215      0     70      0   100%
src\caissa\core\model\__init__.py             19      0      0      0   100%
src\caissa\core\model\base.py                 13      0      0      0   100%
src\caissa\core\model\blocks.py              304      0     14      0   100%
src\caissa\core\model\degradation.py          85      0      2      0   100%
src\caissa\core\model\diagram.py             140      0      0      0   100%
src\caissa\core\model\diff.py                169      2     56      2    98%   314, 493
src\caissa\core\model\document.py            118      0      0      0   100%
src\caissa\core\model\game.py                139      0     10      0   100%
src\caissa\core\model\ids.py                  99      0     24      0   100%
src\caissa\core\model\inline.py              198      0     18      0   100%
src\caissa\core\model\marks.py                61      0      2      0   100%
src\caissa\core\model\migrations.py           73      0     16      0   100%
src\caissa\core\model\props.py               428      0     28      0   100%
src\caissa\core\model\provenance.py           61      0      0      0   100%
src\caissa\core\model\reflect.py              67      0     34      0   100%
src\caissa\core\model\registry.py             40      0      4      0   100%
src\caissa\core\model\serialize.py           289      6    134      3    98%   164-165, 605-606, 696-697
src\caissa\core\model\styles.py              202      0     40      3    99%   458->456, 502->508, 505->503
src\caissa\core\model\validate.py            387      0    230      2    99%   627->637, 1413->1412
src\caissa\core\model\visitor.py             116      0     48      1    99%   262->258
--------------------------------------------------------------------------------------
TOTAL                                       3394      8    808     11    99%
1125 passed in 82.38s (0:01:22)
```

A suíte inteira do repositório continua verde depois das minhas mudanças em
`ids.py` e nos dois `__init__.py`:

```
$ .venv/Scripts/python.exe -m pytest tests -q --ignore=tests/integration
1980 passed in 50.25s
```

### 1.4 As 8 linhas e 11 ramos não cobertos

Nenhum é um caminho alcançável pelo IR atual. Foram inspecionados um a um:

| Local | O que é | Por que não é alcançável |
|---|---|---|
| `diff.py:314` | `if not left.by_id: return "position"` | `_index` sempre registra o id da raiz; `by_id` nunca fica vazio. |
| `diff.py:493` | ramo `Mapping` de `_render` | nenhum campo do IR guarda um `Mapping`. |
| `serialize.py:164-165` | `_encode_scalar` "escalar inesperado" | o único chamador já estreitou o tipo antes. |
| `serialize.py:605-606` | `isinstance(document, Document)` | `_decode_dataclass(body, Document)` já recusa uma tag incompatível. |
| `serialize.py:696-697` | idem em `node_from_payload` | mesma razão. |
| `styles.py:458->456, 502->508, 505->503` | `if style is not None` dentro do laço da cadeia | `style_chain` só devolve nomes que resolvem. |
| `validate.py:627->637` | `_check_fen(..., required=False)` | **configuração morta**: nenhum chamador passa `required=False`. |
| `validate.py:1413->1412` | saída de uma expressão geradora | o laço sempre termina normalmente. |
| `visitor.py:262->258` | saída do laço `for name, annotation in types.items()` | idem. |

Um caminho semelhante — `Transformer._single` recusando a remoção de um filho
obrigatório — **é** testado, mas só pode ser alcançado chamando o método
diretamente: o vocabulário tem exatamente um campo de nó de valor único
(`Diagram.solution`) e ele é opcional. Está anotado no teste.

---

## 2. A suíte de testes

`tests/unit/model/` — 18 módulos, 8 088 linhas, **1 125 testes**.

| Módulo | Testes | O que prova |
|---|---:|---|
| `test_roundtrip_corpus.py` | 210 | O portão do front: 10 001 nós sintéticos, JSON → IR, identidade exata. |
| `test_notation_tables.py` | 168 | 2 170 SAN × 18 idiomas + 2 figurinos = **43 400** idas-e-voltas byte a byte. |
| `test_validate.py` | 92 | Uma classe de erro por código do validador, com guarda de completude. |
| `test_blocks_inlines.py` | 82 | Projeções semânticas: `plain_text`, `block_children`, número do lance. |
| `test_fen.py` | 58 | Estrutura da FEN e legalidade (SPEC §6.4), em camadas separadas. |
| `test_diagram.py` | 58 | SPEC §5.3 campo a campo: confiança por casa, proveniência, marcas. |
| `test_spec5_vocabulary.py` | 53 | SPEC §5.1 transcrita em asserções + superfície pública dos pacotes. |
| `test_codec_internals.py` | 50 | A maquinaria genérica do codec e as recusas do registro de tags. |
| `test_edges.py` | 47 | Os cantos: regressões de identidade, ramos raros do validador. |
| `test_game.py` | 43 | SPEC §5.4: variantes a profundidade 6, NAGs, relógio, `[%cal]`/`[%csl]`. |
| `test_props.py` | 41 | SPEC §5.2: as 46 propriedades de `RunProps`, todas definidas e restauradas. |
| `test_serialize.py` | 40 | Bordas do codec: omissão de padrões, recusas, aninhamento profundo. |
| `test_visitor.py` | 38 | `walk`, `Visitor`, `Transformer` e o compartilhamento estrutural. |
| `test_styles.py` | 34 | A cascata de estilos, um limite entre camadas por teste. |
| `test_ids.py` | 33 | ULID: unicidade, ordenação, tolerâncias Crockford, recusas. |
| `test_migrations.py` | 28 | Escrever um documento v(N-1), migrar, conferir. |
| `test_diff.py` | 26 | Cada classe de mudança com o caminho que ela deve reportar. |
| `test_degradation.py` | 24 | Os quatro verbos e o relatório de perdas do exportador. |

### 2.1 Guardas de completude (o que impede a suíte de apodrecer)

Cinco testes falham automaticamente quando alguém acrescenta algo sem cobri-lo:

- `test_every_registered_type_constructs_and_round_trips` — parametrizado sobre o
  registro de tags: um tipo novo entra na suíte no dia em que é declarado.
- `test_every_registered_node_type_appears_in_the_corpus` — o gerador tem de
  emitir todo tipo de nó, não só os que alguém lembrou.
- `test_maximal_run_props_sets_every_declared_field` — um campo novo em
  `RunProps` sem entrada no fixture da SPEC §5.2 quebra o teste.
- `test_every_documented_code_has_a_test` — um código do validador sem caso de
  teste quebra a suíte (encontrou `imagem.sem-recurso` durante este trabalho).
- `test_the_model_package_re_exports_every_public_name_of_its_modules` — um nome
  público inalcançável a partir do pacote quebra o teste (encontrou três).

### 2.2 O gerador sintético

`tests/unit/model/generators.py` já existia; foi estendido, não reescrito.
Duas lacunas foram fechadas:

- `leaf_inline` nunca produzia `Anchor` nem `NoteRef` — dois dos 49 tipos de nó
  ficavam fora do corpus de 10 000 nós;
- `run_props` nunca definia `font_stretch` nem `emphasis_mark`.

Com isso o corpus visita **49/49** tipos de nó. O seed é fixo (`0xCA155A`) e
`test_corpus_is_deterministic_from_its_seed` prova que o mesmo seed produz o
mesmo documento, de modo que uma falha é reproduzível pelo seed apenas.

### 2.3 A colisão `R` = Rei / `R` = Rook

O caso de maior risco do produto tem seção própria em `test_notation_tables.py`,
com sete testes dedicados, e mais um teste que percorre **todo** o corpus:

```python
def test_reading_portuguese_as_english_is_exactly_the_bug_this_prevents():
    naive = from_language("Ra1", "en")    # 'Ra1' — lido como torre
    correct = from_language("Ra1", "pt")  # 'Ka1' — é o rei
    assert naive != correct
```

Os mesmos falsos amigos foram tabelados e testados em outros treze pares:
`es/fr/it/ca/ro` (`R` = Rei), `fi/is` (`R` = Cavalo), `nl` (`P` = Cavalo),
`hu` (`B` = Torre), `ro` (`N` = Bispo), `de` (`B` = Peão), `cs` (`S` = Bispo),
`pl` (`W` = Torre). O russo `Кр` (rei, dois caracteres) tem teste próprio porque
precisa casar antes de `К` (cavalo), e a dobra de homóglifos cirílicos
minúsculos (`а` → `a`) também.

---

## 3. Cobertura da SPEC §5, item a item

Legenda: **E** = expressa · **P** = parcialmente expressa · **A** = ausente.

### 3.1 Preâmbulo do §5

| Item da SPEC | | Onde |
|---|:--:|---|
| Árvore imutável por versão | E | todo nó é `frozen=True, slots=True, kw_only=True` (`base.py`); testado em `test_every_node_is_frozen` |
| Serializável em JSON | E | `serialize.py`; envelope com `schema_version`/`kind`/`generator` |
| Identidade estável por nó (ULID) | E | `ids.py`; `IRNode.id` com `default_factory=new_ulid` |
| Todo importador produz IR; todo exportador consome IR | E | contrato de pacote; sem dependência de Qt/PyMuPDF/`python-chess` em `caissa.core` |

### 3.2 §5.1 — Tipos de nó

**Document** (4 partes):

| Item | | Onde |
|---|:--:|---|
| `metadata: title, authors, language, isbn, publisher, ...` | E | `DocumentMetadata` (23 campos, incl. `issn`, `edition`, `series`, `rights`, `custom`) |
| `styles: StyleSheet` (definições nomeadas, herdáveis) | E | `StyleSheet` com 5 famílias e cadeias `based_on` |
| `resources: fontes embutidas, imagens, folhas de estilo` | E | `Resource` + `ResourceKind` = `font, image, stylesheet, audio, video, data, pgn` |
| `body: Block[]` | E | `Document.body: tuple[Block, ...]` |

**Block** — os 13 marcadores da SPEC:

| Marcador da SPEC | | Classe | Campos exigidos presentes |
|---|:--:|---|---|
| `Heading(level 1-6, inlines, numbering)` | E | `Heading` | `level`, `content`, `numbering` (validador força 1–6) |
| `Paragraph(inlines, style, alignment, indents, spacing)` | E | `Paragraph` | `content` + `ParagraphProps` (24 campos) |
| `List(ordered\|unordered\|definition, items, marker style)` | E | `ListBlock` | `kind` (exatamente os 3), `items`, `marker_style` (12 estilos) |
| `Table(rows, cols, spans, header repeat, borders, alignment)` | E | `Table` | `rows`, `columns`, `repeat_header`, `header_row_count`, `borders`, `alignment`; spans em `TableCell` |
| `Figure(content, caption, number, placement)` | E | `Figure` | todos + `caption_above`, `alt_text` |
| `Diagram` (§5.3) | E | `Diagram` | ver §3.3 |
| `GameScore` (§5.4) | E | `GameScore` | ver §3.4 |
| `CodeBlock(language, text)` | E | `CodeBlock` | + `show_line_numbers` |
| `Math(latex, display\|inline)` | E | `MathBlock` | `latex`, `display`, `mathml`, `numbered`, `label` |
| `Footnote / Endnote(ref, content)` | E | `Footnote`, `Endnote` | `ref`, `content`, `marker` |
| `PageBreak / SectionBreak(columns, page geometry)` | E | `PageBreak`, `SectionBreak` | `ColumnLayout` (5 campos), `PageGeometry` (9 campos) |
| `Quote / Callout(kind, content)` | E | `Quote`, `Callout` | `CalloutKind` cobre o vocabulário de livro de xadrez: `exercise`, `solution`, `theory`, … |
| `RawPassthrough(format, text)` | E | `RawPassthrough` | + `RawInline`, a metade inline da escotilha |

**Inline** — os 15 marcadores da SPEC:

| Marcador da SPEC | | Classe | Observação |
|---|:--:|---|---|
| `Text(string, run properties)` | E | `Text` | `RunProps` completo |
| `Emphasis / Strong / Underline / Strike / SmallCaps` | E | 5 classes | cada uma envolve `tuple[Inline, ...]` |
| `Super / Sub` | E | `Superscript`, `Subscript` | |
| `Move` (§5.5) | E | `Move` | ver §3.5 |
| `PieceGlyph(piece, style)` | E | `PieceGlyph` | `piece: PieceType`, `figurine_set`, `font_family` |
| `Link(target, tooltip)` | E | `Link` | + `kind: LinkKind`, `title` |
| `NoteRef(id)` | E | `NoteRef` | **desvio de forma:** o campo chama-se `ref` e é `str`, não `ULID` — ver §4.1 |
| `InlineDiagram(fen, size)` | E | `InlineDiagram` | + `orientation`, `marks`, `style`, `alt_text` |
| `MathInline(latex)` | E | `MathInline` | + `mathml` |
| `LineBreak / NonBreakingSpace / Tab` | E | 3 classes | + `Space` com 9 larguras tipográficas |

**Doze tipos além da SPEC**, cada um com razão declarada e testada em
`test_every_extra_node_type_is_accounted_for`: `Span`, `NagSymbol`, `Anchor`,
`IndexEntry`, `ImageInline`, `RawInline`, `Space`, `ImageBlock`, `Group`,
`ThematicBreak`, `TableOfContents`, `ListItem`.

### 3.3 §5.2 — Propriedades de execução

A tabela da SPEC tem oito linhas. Todas mapeiam para campos nomeados de
`RunProps` (46 campos no total). O teste
`test_every_spec_5_2_row_maps_onto_declared_fields` transcreve a tabela e falha
se um campo sumir.

| Linha da SPEC | | Campos que a carregam |
|---|:--:|---|
| família, tamanho, peso, itálico | E | `font_family`, `font_fallbacks`, `font_size`, `font_weight`, `italic`, `oblique_angle`, `font_stretch` |
| cor de texto e realce | E | `color`, `highlight`, `background` (RGB, CMYK, cinza, spot, nomeada, automática) |
| espaçamento entre letras (tracking) | E | `letter_spacing`, `word_spacing`, `horizontal_scale` |
| kerning e ligaduras | E | `kerning`, `kerning_min_size`, `ligatures` (6 modos), `font_features` (tags OpenType arbitrárias) |
| versalete real vs sintético | E | `small_caps: SmallCapsMode` = `none, real, synthetic, petite, unicase` |
| deslocamento de linha de base | E | `baseline_shift`, `rise_relative`, `vertical_align` |
| idioma (hifenização / leitor de tela) | E | `language`, `hyphenate`, `spell_check`, `direction` |
| variações OpenType | E | `variation_axes: tuple[VariationAxis, ...]` |

**Regra de ouro do exportador** (nenhuma propriedade descartada em silêncio):
o mecanismo existe e é completo — `DegradationWarning` (10 campos),
`DegradationRecorder` (4 verbos: `unsupported`, `approximated`, `substituted`,
`rasterised`) e `DegradationReport` (`is_lossless`, `by_property`, `by_kind`,
`of_property`, `summary`). 24 testes. **O IR não pode, sozinho, provar que
nenhum exportador descarta algo** — isso é um portão dos fronts de exportação,
que devem afirmar `recorder.report().by_property()` contra o que o documento
pedia. Fica registrado aqui como dependência, não como lacuna do F1.

### 3.4 §5.3 — Nó `Diagram`

Os treze campos do bloco de código da SPEC, todos presentes:

| Campo da SPEC | | Observação |
|---|:--:|---|
| `id: ULID` | E | herdado de `IRNode` |
| `fen: str` (validada) | E | `validate_fen` (estrutura) + `position_problems` (legalidade §6.4) |
| `orientation: Literal["white","black"]` | E | `Orientation` StrEnum — serializa exatamente para `"white"`/`"black"` |
| `source: DiagramSource` (arquivo, página, retângulo, DPI) | E | `path`, `page_index`, `rect: Rect`, `dpi` + hash de conteúdo, rotação, extrator e versão |
| `recognition: RecognitionResult` (confiança por casa, modelo, versão, timestamp) | E | `per_square_confidence` (64), `model_name`, `model_version`, `recognised_at` + hash, duração, cantos, alternativas, reparos |
| `verified_by_human: bool` | E | |
| `style: DiagramStyle` (fonte/tema, coordenadas, moldura, tamanho) | E | `piece_set`, `theme: BoardTheme` (11 cores), `coordinates: CoordinateStyle`, `border`, `size` |
| `caption: list[Inline] \| None` | E | `tuple[Inline, ...]` (vazio em vez de `None` — ver §4.2) |
| `number: int \| None` | E | duplicatas detectadas pelo validador |
| `marks: list[Mark]` (setas, casas destacadas, círculos) | E | `MarkKind` = `arrow, square, circle, cross, dot, label`; aridade validada |
| `side_to_move_indicator: bool` | E | |
| `stipulation: str \| None` | E | |
| `solution: GameScore \| None` | E | o único campo de nó de valor único do IR |

O vetor de 64 floats é o ponto central do §5.3 e tem tratamento explícito:
`RecognitionResult.doubtful_squares(threshold)` devolve os índices abaixo do
limiar, `DocumentSettings.confidence_threshold` guarda o limiar do documento
(padrão 0,9), e o validador recusa um vetor com tamanho ≠ 64 ou valores fora de
`[0, 1]`.

### 3.5 §5.4 — Nó `GameScore`

| Item da SPEC | | Onde |
|---|:--:|---|
| variantes aninhadas em profundidade arbitrária | E | `MoveNode.children`; testado a profundidade 6 e a 40 plies |
| comentários antes/depois do lance | E | `comment_before`, `comment_after` (campos distintos) |
| NAGs `$1`…`$255` | E | `MoveNode.nags`, `NagSymbol.nag`; faixa validada |
| símbolos de avaliação | E | `EvalAnnotation` (centipawns / mate, com profundidade e texto) |
| relógio | E | `ClockAnnotation` com `ClockKind` = `clk, emt, egt, mct` |
| setas/destaques `[%cal]` / `[%csl]` | E | `MoveNode.arrows`, `MoveNode.highlights` como `tuple[Mark, ...]` — objetos, não texto de comentário |
| cabeçalhos PGN completos | E | `GameHeaders` (Seven Tag Roster nomeado) + `extra: tuple[PgnTag, ...]` sem limite |
| "Envolve `python-chess`" | **desvio deliberado** | ver §4.3 |

### 3.6 §5.5 — Inline `Move`

| Campo da SPEC | | Observação |
|---|:--:|---|
| `san: str` (forma canônica inglesa) | E | canônica: `O-O`, `x`, `=` |
| `ply: int` | E | projeta para `move_number` e `is_black_move` |
| `position_before: str` (FEN) | E | validada estruturalmente |
| `nags: list[int]` | E | |
| `render: MoveRenderStyle` (figurino \| letras-idioma \| ambos) | E | os três valores existem e são renderizados |
| `language: str` | E | 18 idiomas com tabela; `pt-BR` resolve para `pt` |

O exemplo literal da SPEC é um teste:

```python
def test_the_spec_5_5_example_holds_exactly():
    assert to_language("Nf3", "pt") == "Cf3"
    assert to_figurine("Nf3") == "♞f3"
    assert to_language("Nf3", "de") == "Sf3"
```

---

## 4. Desvios de forma (nenhum é lacuna de expressividade)

### 4.1 `NoteRef(id)` é `NoteRef.ref: str`

A SPEC escreve `NoteRef(id)`. A implementação usa uma chave de texto, não um
`ULID`. É o comportamento certo: uma nota importada de PGN, DOCX ou EPUB traz um
rótulo (`"1"`, `"*"`, `"nota-3"`) que precisa sobreviver à ida-e-volta, e amarrar
isso ao ULID interno destruiria o rótulo do autor. O validador liga
`NoteRef.ref` a `Footnote.ref`/`Endnote.ref` e reporta órfãos
(`nota.referencia-orfa`) e notas nunca referenciadas
(`nota.nunca-referenciada`).

### 4.2 Sequências opcionais são tuplas vazias, não `None`

A SPEC escreve `caption: list[Inline] | None`. O IR usa `tuple[Inline, ...] = ()`.
"Ausente" e "vazia" significam a mesma coisa para todo formato de saída, e uma
tupla vazia elimina uma classe inteira de `if x is not None` nos exportadores.
A distinção é preservada onde ela *importa* (`number: int | None`,
`solution: GameScore | None`).

### 4.3 `GameScore` não envolve `python-chess`

A SPEC §5.4 diz "Envolve `python-chess`". O IR não o faz, e isso é deliberado e
documentado em `caissa/core/chess/__init__.py`: `caissa.core` é dependência-zero
para que valide, serialize e faça ida-e-volta em um ambiente onde
`python-chess` não está instalado, e para que importe em milissegundos. O
raciocínio de *legalidade* (este SAN descreve um lance legal desta posição?)
pertence ao subsistema de notação (F6), que usa `python-chess`. O que a SPEC
pede que seja **preservado** está todo preservado (§3.5). O que fica de fora do
F1 é a geração/validação de lances, que nunca foi papel do IR.

Consequência prática: o `Move.san` do IR é lexicalmente válido mas não
verificado contra a posição. `validate()` reporta `lance.san-vazio` e
`fen.invalida`, não "lance ilegal". Isso é do F6.

---

## 5. Defeitos encontrados e corrigidos

### 5.1 `ids.py` — a monotonicidade do ULID quebrava (corrigido)

**Gravidade: real.** O módulo promete, no docstring de `ULID.new`, "strictly
greater than every identifier minted earlier by this process", e o docstring do
módulo justifica a escolha de ULID sobre UUID justamente porque "they sort by
creation time, so a diff of two documents produces stable, human-readable
ordering". `semantic_diff` pareia nós por id, e `ULID` é `order=True`.

O código lia o relógio e comparava com o último timestamp emitido, mas nunca o
**limitava** por ele:

```python
timestamp_ms = min(int(time.time() * 1000.0), _MAX_TIMESTAMP_MS)
if timestamp_ms == _last_timestamp_ms:
    ...
else:
    randomness = int.from_bytes(os.urandom(10), "big")   # <- timestamp menor aceito
```

Dois gatilhos, um só defeito:

1. **Relógio andando para trás** — uma correção de NTP, uma VM retomando de um
   snapshot. Reproduzido:

   ```
   first   01M1XDJSE8J31XEYW7B6VXVG86  1788767462856
   second  01M1XDJSE3CV3371F9MRPJP9PG  1788767462851
   monotonic? False
   ```

2. **Estouro do contador de entropia dentro de um milissegundo** — o ramo de
   estouro avança `timestamp_ms += 1` para preservar a ordem, mas a chamada
   seguinte relê o relógio (ainda no milissegundo anterior) e emite um id que
   ordena **antes** do que acabou de ser emitido.

Correção — uma linha, com o comentário que explica por quê:

```python
timestamp_ms = min(int(time.time() * 1000.0), _MAX_TIMESTAMP_MS)
timestamp_ms = max(timestamp_ms, _last_timestamp_ms)   # monotonicidade > precisão
```

Regressões: `test_a_backwards_clock_step_does_not_reorder_ids` e
`test_the_entropy_counter_rolls_over_inside_one_millisecond_without_repeating`
em `test_edges.py`. Ambos falham contra o código anterior.

### 5.2 O gerador sintético não visitava dois tipos de nó (corrigido)

`NodeFactory.leaf_inline` nunca produzia `Anchor` nem `NoteRef`. O corpus de
10 000 nós — o portão do front — cobria 47 dos 49 tipos. `NodeFactory.run_props`
também nunca definia `font_stretch` nem `emphasis_mark`, duas das 46
propriedades da §5.2. Corrigido; hoje o corpus visita 49/49 e o teste
`test_every_registered_node_type_appears_in_the_corpus` impede a regressão.

### 5.3 Superfície pública inalcançável (corrigido)

Doze nomes declarados públicos em `__all__` de módulo não eram reexportados pelo
pacote, obrigando o consumidor a alcançar submódulos:

- `caissa.core.chess`: `PIECE_LETTERS`, `board_squares`, `FIGURINE_BLACK`,
  `FIGURINE_WHITE`, `figurine_for_piece`, `is_supported_language`,
  `language_table`, `piece_for_letter`;
- `caissa.core.model`: `INLINE_WRAPPERS`, `EMPTY_RUN_PROPS`,
  `EMPTY_PARAGRAPH_PROPS`, e `UnderlineStyle` (importado mas fora do `__all__`,
  o que o ruff sinalizava como `F401`).

Todos reexportados. Guardado por
`test_the_model_package_re_exports_every_public_name_of_its_modules` e o par
para o pacote `chess`.

### 5.4 Limpeza de lint (39 achados)

Sem mudança de comportamento, exceto onde indicado:

- **`serialize.py`** — `_decode_class` tinha 10 `return` e 21 ramos; foi
  dividido em `_decode_atom` (Enum/ULID/datetime) e `_decode_primitive`
  (bool/int/float/str/bytes), com o comentário explicando por que `Enum` tem de
  vir antes dos primitivos (`StrEnum` é subclasse de `str`). `encode_value`
  ganhou `_encode_atom`. A comparação `value != value` (idioma de NaN) virou
  `math.isnan`, que é o que ela queria dizer — **mudança de comportamento
  benigna**: passou a rejeitar também `nan` gerado por outras vias, e
  `float("inf")` continua rejeitado.
- **`validate.py`** — `_check_structure` tinha 15 ramos; os tipos cuja única
  regra é "não estar vazio" foram para `_check_leaf_structure`. Valores mágicos
  (`1000`, `2`, `8`) viraram constantes nomeadas.
- **`fen.py`, `props.py`, `marks.py`, `notation_tables.py`** — valores mágicos
  para constantes nomeadas (`_MIN_FIELDS`, `_RANKS`, `_CMYK_COMPONENTS`,
  `_BOLD_THRESHOLD`, `_LONG_CASTLE_DASHES`, …).
- **`migrations.py`** — `Union[...]` → `X | Y` (PEP 604), verificado em tempo de
  execução com a referência adiante recursiva.
- **Docstrings** — sequências `\\uXXXX` escapadas substituídas pelos caracteres
  reais (`♞`, `×`, `†`, `‡`, `±`), que é o que a docstring queria mostrar.

---

## 6. Observações para os fronts seguintes

Coisas verdadeiras sobre o IR que não são defeitos, mas que quem consome
precisa saber:

1. **`Table.column_count` é `len(self.columns)`, não uma dedução das linhas.**
   Uma tabela importada com linhas e sem colunas declaradas reporta 0. O
   validador sinaliza (`tabela.sem-colunas`), mas um exportador que confie em
   `column_count` sem validar antes vai escrever uma tabela vazia.

2. **`Move.ply == 0` significa "sem número", e `move_number` devolve 1**, não 0.
   Documentado e testado.

3. **`MoveRenderStyle`, `FigurineSet` e `PieceType` vêm de
   `caissa.core.chess`**, não de `caissa.core.model`, embora sejam os tipos de
   `Move.render`, `PieceGlyph.piece`, `DocumentSettings.move_render` e
   `GameRenderOptions.figurine_set`. A fronteira é deliberada (o modelo depende
   do vocabulário de xadrez, não o contrário); quem escreve um exportador
   importa dos dois pacotes.

4. **`_check_fen(required=False)` é configuração morta** — nenhum chamador a
   usa. Ou um chamador futuro precisa dela (um FEN opcional em algum nó novo),
   ou o parâmetro deve sair. Não removi: é do tipo de decisão que pertence a
   quem acrescentar o próximo nó com FEN.

5. **O IR não modela histórico.** `Document` não carrega revisão nem ponteiro
   para a versão anterior. "Imutável por versão" (§5) é satisfeito pelos nós
   congelados, mas uma pilha de desfazer tem de viver fora do IR. Se a UI (F10)
   quiser desfazer estrutural barato, o `Transformer` já compartilha subárvores
   intactas — `test_an_untouched_subtree_is_shared_not_copied` prova por
   identidade de objeto, não por igualdade.

6. **`CURRENT_SCHEMA_VERSION == 1` e `DEFAULT_REGISTRY` não tem passos.** A
   maquinaria de migração está provada contra registros privados
   (`test_migrations.py`, 28 testes, incluindo um payload v1 de forma antiga que
   *não* decodifica sem a migração). Quando a primeira mudança de forma chegar,
   o passo e o bump de versão vão no mesmo commit.
