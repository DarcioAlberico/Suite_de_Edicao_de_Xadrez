# Caïssa Studio — Especificação Técnica

> Suíte profissional de edição, reconhecimento e publicação de material de xadrez.
> **Versão do documento:** 1.0 · **Data:** 2026-09-07 · **Status:** Baseline aprovada para implementação

---

## 0. Sumário executivo

Caïssa Studio é uma aplicação desktop offline para Windows que transforma acervos
heterogêneos de material enxadrístico — PDFs de qualidade variável, bases PGN de
múltiplos gigabytes, digitalizações, EPUBs — em documentos editáveis, pesquisáveis e
republicáveis em PDF, DOCX, EPUB, HTML e LaTeX, com **diagramas de xadrez reconhecidos
por visão computacional e reeditáveis como objetos vetoriais de primeira classe**.

O produto compete diretamente, em precisão de reconhecimento, com
[chessvision.ai](https://chessvision.ai) e [ChessOCR](https://helpman.komtera.lt/chessocr/),
e ultrapassa ambos no que eles não fazem: **edição e republicação do documento inteiro**.

### O diferencial arquitetural

Ferramentas existentes tratam o diagrama como uma **imagem**. Caïssa Studio trata o
diagrama como uma **posição** (FEN + proveniência + estilo), e o documento como uma
**árvore semântica** (IR) da qual todos os formatos de saída são renderizados. Essa
única decisão é o que permite: reflow em EPUB, diagramas vetoriais nítidos em qualquer
zoom, busca por posição dentro do livro, troca global de fonte de xadrez, e tradução de
notação (SAN inglês ↔ figurino ↔ português) sem redigitar nada.

---

## 1. Perfil do usuário-alvo

O usuário de referência (persona primária) é um **enxadrista profissional / editor de
material de xadrez**, com:

| Característica | Implicação de engenharia |
|---|---|
| Bases PGN de dezenas de GB | Indexação incremental, streaming, nunca carregar tudo em RAM |
| Centenas/milhares de PDFs de qualidade muito variável | Pipeline tolerante a ruído, com graus de confiança explícitos |
| Digitalizações antigas, tortas, com bleed-through | Deskew, despeckle, remoção de sombra, dewarp |
| Produz material para publicação | Saída tipograficamente correta, não "melhor esforço" |
| Trabalha em português, lê em inglês/alemão/russo/espanhol | OCR multilíngue + tradução de notação |
| Não é programador | Zero configuração obrigatória; tudo funciona no primeiro clique |

### Personas secundárias (validadas por agentes críticos dedicados)

- **P2 — Estudante:** importa posição de PDF, quer FEN/PGN no clipboard em 2 cliques.
- **P3 — Autor/editor:** escreve livro novo, precisa de diagramas nítidos e numeração automática.
- **P4 — Converter de acervo:** lote de 500 PDFs para EPUB reflowable, sem supervisão.
- **P5 — Treinador:** monta apostila com posições extraídas de várias fontes.

---

## 2. Restrições de hardware (medidas nesta máquina)

```
CPU   : AMD Ryzen 5 8400F — 6 núcleos físicos / 12 lógicos
RAM   : 31,6 GB
GPU   : NVIDIA GeForce RTX 5060 — 8 GB VRAM — Blackwell, compute capability sm_120
Driver: 591.86
Disco : C: 930 GB total, 76 GB livres  <-- RESTRIÇÃO CRÍTICA
SO    : Windows 11 Pro build 26200
Python: 3.10 / 3.11 / 3.12 / 3.14 instalados (3.11 é o padrão do shell)
```

### 2.1 Consequências não-negociáveis

**R1 — Blackwell exige CUDA 12.8+.** Rodas PyTorch anteriores a `cu128` não têm kernels
para `sm_120` e falham silenciosamente para CPU ou quebram com
`no kernel image is available for execution on the device`.

**R2 — Conflito ONNX Runtime x PyTorch.** A partir da versão 1.27, `onnxruntime-gpu`
publicado no PyPI é compilado contra **CUDA 13.0**, enquanto as rodas PyTorch Blackwell
usam **CUDA 12.8**. Carregar os dois no mesmo processo causa fallback silencioso para
CPU ou conflito de DLL. **Decisão: ver ADR-0003.**

**R3 — 8 GB de VRAM é o orçamento total**, compartilhado entre detector, classificador,
OCR e LLM. Nenhum subsistema pode assumir posse exclusiva da GPU. **Decisão: ver ADR-0004
(gerenciador de residência de modelos).**

**R4 — 76 GB livres em disco.** O conjunto completo de pesos não pode exceder **6 GB**;
o cache de páginas renderizadas e índices precisa de teto configurável com despejo LRU.

**R5 — Python 3.11 é o alvo.** É a versão com melhor cobertura de rodas binárias para
PySide6, PyMuPDF, onnxruntime e torch cu128. 3.14 ainda tem lacunas de rodas.

---

## 3. Decisões arquiteturais (resumo — detalhes em `docs/adr/`)

| ADR | Decisão | Justificativa em uma linha |
|---|---|---|
| 0001 | **PySide6 (Qt 6)** como toolkit de UI | Único caminho realista para qualidade visual AAA; LGPL permite distribuição |
| 0002 | **Document IR** único como centro do sistema | Um modelo, cinco saídas; sem isso "formatação rica em todos os formatos" é impossível |
| 0003 | **ONNX Runtime isolado em subprocesso** ou torch-only | Resolve R2 sem sacrificar aceleração |
| 0004 | **ModelResidencyManager** com carga sob demanda e despejo LRU de VRAM | Resolve R3 |
| 0005 | **Gemma 4 E4B** como LLM primário (12B opcional) | Cabe em 8 GB com folga para a pipeline de visão |
| 0006 | **Detecção híbrida**: geométrica rápida + rede neural de fallback | PDFs vetoriais não precisam de rede; digitalizações precisam |
| 0007 | **SQLite + FTS5 + índice posicional** para bases grandes | Zero servidor, streaming, cabe no perfil do usuário |
| 0008 | **Correção de notação guiada por gramática + legalidade** | Maior ganho isolado de precisão em OCR de xadrez |

---

## 4. Arquitetura de subsistemas

```
                        +------------------------------+
                        |        UI (PySide6)          |
                        |  Biblioteca · Leitor · Editor|
                        |  Inspetor · Lote · Diferenças|
                        +--------------+---------------+
                                       | sinais Qt / comandos
                        +--------------v---------------+
                        |      Núcleo de Aplicação     |
                        |  Comandos · Desfazer · Sessão|
                        +--------------+---------------+
                                       |
        +--------------+---------------+---------------+--------------+
        |              |               |               |              |
+-------v------++------v------++-------v------++-------v------++------v------+
|   INGEST     ||   VISION    ||     OCR      ||    INDEX     ||   EXPORT    |
| PDF/EPUB/    || detect ->   || engines ->   || SQLite FTS5  || PDF · DOCX  |
| DOCX/IMG/PGN || rectify ->  || layout ->    || + posicional || EPUB · HTML |
|              || classify -> || notation     || + regex      || LaTeX · PGN |
|              || fen         ||              ||              ||             |
+-------+------++------+------++-------+------++-------+------++------+------+
        |              |               |               |              |
        +--------------+---------------+---------------+--------------+
                                       |
                        +--------------v---------------+
                        |       DOCUMENT IR (§5)       |
                        |  árvore semântica versionada |
                        +--------------+---------------+
                                       |
                   +-------------------+-------------------+
           +-------v------+    +-------v------+    +-------v------+
           |   TYPESET    |    |     LLM      |    |   RUNTIME    |
           | fontes xadrez|    |  Gemma 4 E4B |    | residência de|
           | render vetor |    |  local       |    | modelos/VRAM |
           +--------------+    +--------------+    +--------------+
```

---

## 5. Document IR — o coração do sistema

O IR é uma árvore imutável-por-versão, serializável em JSON, com identidade estável por
nó (`ULID`). Todo importador produz IR; todo exportador consome IR.

### 5.1 Tipos de nó

```
Document
├── metadata: title, authors, language, isbn, publisher, ...
├── styles: StyleSheet (definições nomeadas, herdáveis)
├── resources: fontes embutidas, imagens, folhas de estilo
└── body: Block[]

Block =
  | Heading(level 1-6, inlines, numbering)
  | Paragraph(inlines, style, alignment, indents, spacing)
  | List(ordered|unordered|definition, items, marker style)
  | Table(rows, cols, spans, header repeat, borders, alignment)
  | Figure(content, caption, number, placement)
  | Diagram(ver §5.3)
  | GameScore(ver §5.4)
  | CodeBlock(language, text)
  | Math(latex, display|inline)
  | Footnote / Endnote(ref, content)
  | PageBreak / SectionBreak(columns, page geometry)
  | Quote / Callout(kind, content)
  | RawPassthrough(format, text)   <- escotilha de escape por formato

Inline =
  | Text(string, run properties)
  | Emphasis / Strong / Underline / Strike / SmallCaps
  | Super / Sub
  | Move(ver §5.5)
  | PieceGlyph(piece, style)       <- figurino
  | Link(target, tooltip)
  | NoteRef(id)
  | InlineDiagram(fen, size)       <- diagrama miniatura no meio do texto
  | MathInline(latex)
  | LineBreak / NonBreakingSpace / Tab
```

### 5.2 Propriedades de execução (run properties) — formatação rica

Cada `Text` carrega um `RunProps` completo, mapeado para **todos** os formatos de saída:

| Propriedade | PDF | DOCX | EPUB/HTML | LaTeX |
|---|---|---|---|---|
| família, tamanho, peso, itálico | sim | sim | sim | sim |
| cor de texto e realce | sim | sim | sim | sim |
| espaçamento entre letras (tracking) | sim | sim | sim | sim |
| kerning e ligaduras | sim | sim (ligatures) | sim (`font-feature-settings`) | sim (microtype) |
| versalete real vs sintético | sim | sim | sim | sim |
| deslocamento de linha de base | sim | sim | sim | sim |
| idioma (hifenização / leitor de tela) | sim | sim | sim | sim |
| variações OpenType | sim | estático | sim | sim |

> **Regra de ouro do exportador:** nenhum exportador pode *silenciosamente* descartar uma
> propriedade. Se um formato não suporta algo, o exportador registra um
> `DegradationWarning` visível no relatório de exportação. Isso é testado (§11).

### 5.3 Nó `Diagram` — diagrama como posição, não como imagem

```python
@dataclass(frozen=True)
class Diagram:
    id: ULID
    fen: str                       # posição completa, validada
    orientation: Literal["white", "black"]
    # --- proveniência (auditável) ---
    source: DiagramSource          # arquivo, página, retângulo, DPI
    recognition: RecognitionResult # confiança por casa, modelo, versão, timestamp
    verified_by_human: bool
    # --- apresentação ---
    style: DiagramStyle            # fonte/tema, coordenadas, moldura, tamanho
    caption: list[Inline] | None
    number: int | None             # numeração automática
    marks: list[Mark]              # setas, casas destacadas, círculos
    side_to_move_indicator: bool
    # --- semântica opcional ---
    stipulation: str | None        # "Mate em 2", "Brancas jogam e ganham"
    solution: GameScore | None
```

`recognition.per_square_confidence` é um vetor de 64 floats. A UI pinta em âmbar
qualquer casa abaixo do limiar, então o usuário revisa **apenas** o que é duvidoso —
esse é o fluxo que torna 97 % de acurácia utilizável na prática.

### 5.4 Nó `GameScore` — partida como árvore

Envolve `python-chess`, preservando: variantes aninhadas em profundidade arbitrária,
comentários antes/depois do lance, NAGs (`$1`…`$255`), símbolos de avaliação, relógio,
setas/destaques no estilo `[%cal]` / `[%csl]`, e cabeçalhos PGN completos.

### 5.5 Inline `Move` — lance como objeto semântico

```python
@dataclass(frozen=True)
class Move:
    san: str                # forma canônica inglesa: "Nf3", "O-O", "exd5"
    ply: int
    position_before: str    # FEN
    nags: list[int]
    render: MoveRenderStyle # figurino | letras-idioma | ambos
    language: str           # "en", "pt", "de", "ru", "es", ...
```

Renderizar `Move` em português dá "Cf3"; em figurino dá o glifo do cavalo; em alemão
"Sf3" — **a partir do mesmo IR**. É por isso que o lance não é texto.

---

## 6. Pipeline de visão computacional

Meta de precisão: **≥ 99,5 % de casas corretas** e **≥ 97 % de diagramas perfeitos**
no corpus dourado (§11.2), igualando ou superando chessvision.ai.

### 6.1 Estágio 1 — Detecção de tabuleiro

Estratégia híbrida, escolhida por página (ADR-0006):

**Via A — Vetorial (PDFs nativos, ~70 % do acervo típico, custo ~2 ms/página)**
Consulta o *display list* do PyMuPDF por famílias de retângulos preenchidos em grade
8x8, ou por glifos de fontes de xadrez conhecidas (Merida, Figurine, Chess Cases...).
Quando a fonte de xadrez é identificada, a posição é lida **exatamente, sem inferência**
— acurácia 100 %, e o caminho que a concorrência baseada em raster não tem.

**Via B — Geométrica (digitalizações limpas, ~15 ms/página)**
`Canny` → `HoughLinesP` → agrupamento de linhas por ângulo → busca de retículo 9x9 →
pontuação de plausibilidade (quadratura, alternância de cor, contraste).

**Via C — Neural (casos difíceis: tortos, com ruído, sombreados, sobrepostos)**
Detector one-stage leve (classe YOLO-nano, ~6 MB, entrada 640x640) treinado em
diagramas sintéticos (§6.6) e reais. Prediz caixa + 4 cantos (keypoints), o que já
resolve perspectiva e rotação.

O **árbitro** roda as vias em ordem de custo e aceita a primeira com confiança acima do
limiar; em desacordo, a via neural vence e a discrepância é registrada para telemetria
local.

### 6.2 Estágio 2 — Retificação

Homografia a partir dos 4 cantos, normalização para 512x512 (8 x 64 px). Correções:
deskew subpixel por refinamento de cantos, remoção de moldura decorativa, compensação de
iluminação (CLAHE no canal L de LAB), e detecção de orientação (coordenadas `a`–`h` /
`1`–`8` via OCR local, ou heurística de peças).

### 6.3 Estágio 3 — Classificação de casas

CNN residual compacta (entrada 64x64 por casa, ~1,5 M parâmetros, 13 classes:
6 peças x 2 cores + vazio). Treinada com:
- **Contexto 3x3:** cada casa vê os vizinhos (peças altas invadem a casa acima — causa
  nº 1 de erro em pipelines ingênuos).
- **Cabeça auxiliar** prevendo a cor da casa (branca/preta), o que regulariza.
- **Aumento pesado:** ruído de digitalização, JPEG, desfoque, bleed-through, dithering
  de fax, sub-amostragem, rotação ±2°.

### 6.4 Estágio 4 — Montagem e reparo do FEN

Aqui está a inteligência que separa 97 % de 99,5 %. Um **solucionador de restrições**
recebe a distribuição de probabilidade por casa e busca a posição de máxima
verossimilhança **sujeita à legalidade**:

- no máximo 1 rei por cor, exatamente 1 é obrigatório (salvo diagrama de problema);
- reis não adjacentes; lado que não joga não pode estar em xeque;
- no máximo 8 peões por cor, nenhum peão na 1ª ou 8ª fileira;
- contagem de peças coerente com promoções (bispos de casas iguais implicam promoção);
- se houver legenda "Mate em 2" ou similar, a posição precisa ter solução — validável.

Quando a leitura ingênua viola uma restrição, o solucionador troca as casas de menor
confiança até restaurar a legalidade, recuperando a maior parte dos erros de casa única.
Divergências residuais são apresentadas ao usuário, não escondidas.

### 6.5 Estágio 5 — Verificação assistida por LLM (opcional)

Gemma 4 E4B (multimodal) recebe o recorte do diagrama, o FEN candidato e a legenda, e
responde se são consistentes, além de extrair a estipulação ("Mate em 2", "Brancas jogam
e empatam") e o número do diagrama. Usado apenas em itens de baixa confiança, para não
gastar o orçamento de VRAM.

### 6.6 Gerador de dados sintéticos

Ferramenta própria (`tools/synthgen`) produz milhões de diagramas rotulados combinando:
posições reais de bases PGN x conjuntos de peças (Merida, Alpha, Chess Cases, USCF,
Leipzig, unicode, SVG modernos) x temas de tabuleiro x degradações de digitalização x
molduras e legendas. Rótulos são exatos por construção — o mesmo truque de bootstrap que
a chessvision.ai usou, executado localmente e sem custo.

---

## 7. OCR de texto

### 7.1 Cascata de motores

| Nível | Motor | Quando |
|---|---|---|
| 0 | **Camada de texto do PDF** | Sempre que existir e for confiável (detecção de CMap quebrado) |
| 1 | **Tesseract 5** (LSTM) | Padrão para digitalizações limpas; leve, offline |
| 2 | **PaddleOCR PP-Structure** | Layouts complexos, tabelas, multi-coluna |
| 3 | **Surya** | Scripts não-latinos, russo/grego, layouts difíceis |
| 4 | **VLM (Gemma 4)** | Último recurso em regiões que os anteriores reprovaram |

Todos os motores são adaptadores por trás de uma interface única, com um **árbitro por
região** que escolhe pelo maior escore de confiança calibrada e pela concordância entre
motores.

### 7.2 Pré-processamento de imagem

Deskew (transformada de projeção), remoção de sombra (morfologia), binarização adaptativa
(Sauvola), despeckle, correção de bleed-through (subtração do verso quando disponível),
dewarp (para fotos de páginas curvas), e super-resolução opcional para DPI < 200.

### 7.3 Pós-correção consciente de notação (maior ganho de precisão)

Notação de xadrez é uma **linguagem formal**. Um analisador PEG reconhece SAN/LAN/figurino
em múltiplos idiomas; cada lance candidato é validado contra `python-chess` a partir da
posição corrente. Erros clássicos de OCR são então corrigidos com confiança:

| Erro de OCR | Correção guiada por legalidade |
|---|---|
| `0-0` / `O-O` / `o-o` | canonicaliza para `O-O` |
| `Kf3` (K = rei) onde só o cavalo alcança | vira `Nf3` |
| `l` / `1` / `I`, `5` / `S`, `8` / `B`, `0` / `O` | resolvido pela legalidade |
| `Qxe4+` com o `+` perdido | reinserido a partir da posição |
| Numeração `1.e4` colada, ou `1 . e4` | normalizado |
| Idioma: `Cf3` (pt), `Sf3` (de), `Кf3` (ru) | mapeado para SAN canônico |

Quando a sequência de lances é internamente consistente e legal do início ao fim, a
confiança do bloco sobe para praticamente 1,0 — e o texto vira `GameScore` no IR, não
uma linha de caracteres.

---

## 8. Exportadores

Todos consomem o mesmo IR. Cada um tem um **relatório de fidelidade** (§11.3).

### 8.1 PDF
Motor próprio sobre ReportLab/PyMuPDF com: fontes embutidas (subconjunto), diagramas
**vetoriais** (nunca raster), índice remissivo, sumário navegável (outline), marcadores,
metadados XMP, PDF/A-2b opcional, e marcação de acessibilidade (tags).

### 8.2 DOCX
`python-docx` estendido com XML direto para o que a biblioteca não cobre: estilos reais
(não formatação direta), numeração automática de figuras via campos `SEQ`, sumário via
campo `TOC`, diagramas como **EMF vetorial** (não PNG) com fallback PNG de alta
resolução, notas de rodapé, e propriedades de documento.

### 8.3 EPUB 3
Reflowable com: XHTML semântico, CSS modular, diagramas em **SVG inline** (nítidos em
qualquer tela e em modo escuro), fontes de xadrez embutidas e subconjuntadas,
`nav.xhtml` com landmarks, MathML/SVG para fórmulas, metadados Dublin Core, e validação
integrada com EPUBCheck. Também exporta EPUB de layout fixo quando o original exige.

### 8.4 HTML
Página única autocontida ou site estático, com diagramas SVG interativos opcionais
(navegar a partida com as setas), impressão via CSS Paged Media, e modo escuro nativo.

### 8.5 LaTeX
Preâmbulo com `xskak` / `chessboard` / `chessfss`, diagramas como
`\chessboard[setfen=...]` — **editáveis em texto**, não imagens — figurino via
`skaknew`, e um `Makefile` gerado.

### 8.6 PGN / FEN / EPD
Exporta todas as posições e partidas reconhecidas, com comentários e variantes.

---

## 9. Motor de busca para acervos grandes

- **Índice de texto:** SQLite FTS5 com tokenizador customizado que preserva notação
  (`Nf3`, `O-O-O`, `1.e4` são tokens únicos e pesquisáveis).
- **Índice posicional:** hash Zobrist de cada posição de cada partida e diagrama, para
  responder "em quais dos meus 1.200 PDFs esta posição aparece?" em milissegundos.
- **Regex:** motor completo (`regex`, compatível com PCRE) sobre texto **e** sobre o IR,
  com substituição pré-visualizada, grupos nomeados e escopo (só legendas, só lances...).
- **Consulta por padrão de material:** "posições com bispos de cores opostas e até 6 peões".
- Indexação incremental, em segundo plano, com orçamento de disco configurável.

---

## 10. Interface (qualidade AAA)

Detalhada em `docs/quality/UI_SPEC.md`. Princípios:

1. **Densidade profissional sem poluição** — a referência visual é DaVinci Resolve /
   Affinity Publisher, não um utilitário Tkinter.
2. **Tema claro e escuro reais**, ambos projetados (não um invertendo o outro), com
   contraste WCAG AA verificado em todos os pares de cor.
3. **60 fps em pan/zoom** de páginas de 300 DPI — renderização em tile, cache LRU,
   trabalho pesado fora da thread de UI, sempre.
4. **Sobreposição de reconhecimento** — caixas numeradas sobre a página, casas duvidosas
   em âmbar, um clique abre o editor de posição lado a lado com o recorte original.
5. **Nada bloqueia.** Toda operação longa é cancelável, com progresso real (não
   indeterminado) e resultado parcial aproveitável.
6. **Atalhos de teclado para tudo**, com paleta de comandos (Ctrl+Shift+P).
7. **Desfazer/refazer universal**, inclusive para operações em lote.

---

## 11. Qualidade, testes e critérios de aceitação

### 11.1 Pirâmide de testes
Unitários (rápidos, sem I/O) → integração (pipeline real em arquivos pequenos) →
dourados (corpus fixo, métricas versionadas) → visuais (capturas comparadas por SSIM e
revisão de agente crítico).

### 11.2 Corpus dourado
Mínimo de **200 páginas** rotuladas manualmente, estratificadas por: PDF vetorial nativo,
digitalização 300 DPI limpa, digitalização 150 DPI ruidosa, fax/dithering, foto de
página, coluna dupla, diagrama com setas e destaques, diagrama com moldura decorativa,
notação em 5 idiomas, e material de problemas (composição).

### 11.3 Portões de aceitação (um agente crítico reprova o build se qualquer um falhar)

> **Nota (revisão 2026-09-07):** as metas abaixo foram corrigidas após o levantamento
> em `docs/ASSETS.md`. As de classificação já estavam superadas pelo código existente
> antes do início do projeto; o gargalo real é **detecção e velocidade**.

| Métrica | Mínimo | Já medido hoje |
|---|---|---|
| Acurácia de casa (laboratório) | ≥ 99,95 % | 99,9854 % ✔ |
| Diagramas perfeitos (laboratório) | ≥ 99,0 % | 99,06 % ✔ |
| Diagramas perfeitos (campo) | ≥ 98,0 % | 97,87 % |
| **Recall de detecção (campo)** | **≥ 99,0 %** | **94,78 % ← o trabalho está aqui** |
| Precisão de detecção (campo) | ≥ 98,5 % | 97,32 % |
| **Segundos por diagrama** | **≤ 0,10** | **0,635 (CPU; a GPU está ociosa)** |
| Taxa de erro de caractere (OCR, digitalização limpa) | ≤ 0,5 % |
| Acurácia de lance após correção por legalidade | ≥ 99,8 % |
| Fidelidade de ida-e-volta do IR (export/import) | ≥ 99 % dos nós preservados |
| EPUBCheck | 0 erros |
| Abertura de PDF de 500 páginas | ≤ 2 s até a primeira página |
| Pan/zoom | ≥ 55 fps sustentados |
| Pico de VRAM | ≤ 7,0 GB |
| Contraste de UI | WCAG AA em 100 % dos pares |

### 11.4 Revisão crítica adversarial
Cada subsistema é auditado por um agente crítico independente, com mandato explícito de
**reprovar**. Para a UI e para a saída tipográfica, a comparação é **às cegas e lado a
lado** contra material de referência da indústria (Quality Chess, New in Chess, Chessbase,
Everyman). Um subsistema só é considerado pronto quando o crítico, sem saber qual amostra
é a nossa, não consegue apontar a nossa como inferior.

---

## 12. Empacotamento e distribuição

- Instalador Windows (Inno Setup) e build PyInstaller com dependências nativas.
- Modelos baixados sob demanda no primeiro uso (mantém o instalador abaixo de 150 MB),
  com verificação de integridade SHA-256 e opção de instalação offline por pacote.
- Totalmente funcional **sem internet** após a configuração inicial.
- Sem telemetria remota. Diagnóstico é local e exportável pelo usuário.

---

## 13. Fora de escopo (v1)

Análise com engine (Stockfish) além de validação de legalidade; sincronização em nuvem;
colaboração multiusuário; app móvel; OCR de partituras manuscritas.
