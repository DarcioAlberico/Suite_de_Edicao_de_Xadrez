# Inventário de Ativos Existentes e Plano de Absorção

> **Versão 2.0 — 2026-09-07.** A versão 1.0 deste documento estava errada em pontos
> importantes e foi substituída. Ver §8 para o registro das correções.
>
> Este documento é vinculante: nenhum agente deve reescrever do zero algo listado aqui
> como existente. Reescrever código maduro e testado é desperdício e regressão.

---

## 0. Descoberta central

A suíte **não é um projeto novo**. Existem cinco bases de código em `C:\Python-Chess2\`,
somando mais de **160.000 linhas** de código próprio, com sete modelos treinados,
**mais de 4.600 testes** e dois instaladores funcionando.

**Decisão: Caïssa Studio é a unificação e elevação desses projetos.**

| Projeto | Linhas (código / testes) | Toolkit | Papel |
|---|---|---|---|
| **`ChessVisionOFF_Puro`** | **85.798 / 4.412 testes** | PyQt6 | **TRONCO.** É a aplicação principal. |
| `Editor_Diagramas_de_Xadrez` | 12.400 / 17.342 | PySide6 | Absorvido: edição e substituição em PDF |
| `PGN_Live_Editor` | 13.300 / 5.466 | PyQt6 | Absorvido: análise tolerante de PGN |
| `PDFimport` | 3.332 / — | PySide6 | Absorvido: EPUB e fontes |
| `Chess_diagram_to_FEN` | 5.033 / — | — | Segunda opinião (fotos, capturas de tela) |

---

## 1. Por que ChessVisionOFF_Puro é o tronco

Este é, de longe, o ativo mais valioso, e a versão 1.0 deste documento o subestimou.

- **145.272 linhas no total**, 330 módulos, **4.412 testes** que passam.
- Sete modelos treinados, incluindo um classificador de peças e um **classificador de
  caracteres de ~314 classes** para OCR de texto.
- **Sete abas de produto**: PDF, Resultado, Estudo, Texto, Galeria, Dataset, Revisão.
- **Camada `ui/` livre de toolkit** — 53 módulos, ~13.000 linhas, onde vive toda a
  decisão (posição de caixa, semântica de clique, zoom ancorado, atalhos, comandos,
  paleta de cores segura para daltônicos). A camada `qt/` apenas pinta. Esta disciplina
  arquitetural é o que torna a escolha de toolkit reversível e é o motivo pelo qual este
  projeto pode crescer.
- **40 comandos de linha de comando** registrados.
- Ciclo de melhoria de modelo completo: rotulagem, auditoria de dataset, divisões
  estáveis por hash, proveniência por hash perceptual, fila de revisão ordenada por valor
  de informação, calibração de temperatura, censo de detecção com diferenças.
- CI no Windows com matriz Python 3.10/3.13, ruff + mypy + pytest, disparado em **todo**
  push.

### 1.1 A precisão já medida supera as metas iniciais da SPEC

`docs/BASELINE.md` do projeto, divisão de teste, 320 tabuleiros / 20.480 casas:

| Métrica | Valor medido |
|---|---|
| **Exata por tabuleiro** | **0,9906** (317 de 320) |
| Com até 1 casa errada | 1,0000 |
| **Por casa** | **0,999854** (3 erros em 20.480) |
| Posições ilegais previstas | **0** |
| ECE (calibração) | 0,0001 |

A SPEC §11.3 pedia ≥ 97,0 % de diagramas perfeitos e ≥ 99,5 % de casas. **Ambas já estão
superadas em laboratório.** As metas da SPEC foram corrigidas para cima (ver §7).

### 1.1.1 Baseline verificada nesta máquina (2026-09-07)

```
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q
4412 passed, 2 skipped, 28 warnings, 3750 subtests passed in 248.25s (0:04:08)
```

Código de saída 0. **Este é o estado que não pode regredir.** Qualquer agente que toque o
tronco roda esta suíte antes e depois, e reporta os dois números.

Os 2 skips são legítimos e informativos: `tests\test_ocr.py:267` pula os motores
`easyocr` e `tesseract` porque **não estão instalados**. Só o caminho `rapidocr` existe
hoje. Nada da pipeline de diagramas é pulado.

Os 28 avisos vêm todos de `test_onnx_export.py` (rastreamento de `BoardHeadClassifier`) e
são conhecidos e explicados no próprio código.

### 1.2 Onde está o problema real

`docs/metrics/field_20260822_s99.json`, medido em páginas reais anotadas
(68 páginas, 115 diagramas):

| Métrica de campo | Valor | Meta |
|---|---|---|
| `detection_recall` | **0,9478** | 0,99 |
| `detection_precision` | 0,9732 | 0,98 ✔ |
| `field_exact` | 0,9787 | — |
| `export_rate` | 0,8696 | — |
| `seconds_per_diagram` | 0,635 | ≤ 0,10 |

**A classificação está resolvida. A detecção e a velocidade não estão.**
Um em cada vinte diagramas não é encontrado, e cada diagrama custa 0,64 s em CPU.

---

## 2. Joias da coroa — código a preservar intacto

### 2.1 Detecção por contorno com reparo morfológico diagonal
`ChessVisionOFF_Puro\src\chess_diagram_ocr\board_detection.py` (727 linhas)

Três passagens de limiar: simples, fechamento quadrado, e **fechamento diagonal**. A
justificativa documentada é sutil e correta: as casas escuras de um diagrama são de uma
paridade só, e duas casas da mesma paridade **encostam apenas pela quina**. Se um
contato de quina não sobrevive à rasterização, a corrente parte e o contorno fecha só
parte do tabuleiro — sai um quad com uma fileira a menos, exatamente 7/8. Custo medido do
reparo: 61,6 → 95,0 ms/página.

Também aqui: `_checker_score` e `_grid_score` (pontuação de textura de tabuleiro feita à
mão, que é o núcleo anti-falso-positivo), e `order_quad_points` por **ângulo em torno do
centroide** — não pela regra soma/diferença, que duplica um canto em losangos a 45°.

### 2.2 Fusão de duas fontes de detecção
`ChessVisionOFF_Puro\src\chess_diagram_ocr\detection\hybrid.py` (860 linhas)

O levantamento de 27 PDFs do acervo real está documentado no código:

| O que a página tem | Livros | Imagem embutida serve? |
|---|---|---|
| Imagem quadrada por diagrama | 10 | sim |
| Página inteira é digitalização | 12 | não: uma imagem só, cobrindo tudo |
| **Diagrama vetorial / fonte** | **2** | **não: não há imagem** |
| Misto | 3 | às vezes |

Conclusão medida: *"o bbox embutido é melhor em localizar; o warp por contorno é melhor
em alinhar"*. A fusão usa um para cada coisa. **As duas linhas "diagrama vetorial/fonte"
são exatamente a lacuna que a frente F3-A preenche.**

### 2.3 Decodificação com restrições de xadrez
`ChessVisionOFF_Puro\src\chess_diagram_ocr\decode.py` (329 linhas)

Busca best-first (heapq) sobre a matriz (64, 13). Regras: exatamente um rei por cor,
≤ 8 peões, ≤ 16 peças, nada na 1ª/8ª fileira, e contabilidade de promoções. Xeque
deliberadamente **não** é restrição, porque o diagrama de livro não informa o lado a
jogar. Efeito medido em `1937 Kemeri.pdf`, 47 tabuleiros: leituras legais **25 → 33**.

Isto já é a §6.4 da SPEC, implementada e medida.

### 2.4 Cascata de regras de orientação
`ChessVisionOFF_Puro\src\chess_diagram_ocr\orientation.py` (362 linhas)

Cinco regras em ordem, cada uma um dataclass congelado: `CoordinateRule`,
`SingleLegalRule`, `ConfidenceMarginRule`, `PawnPriorRule`, `TightMarginFallback`.
A `OrientationPolicy` decide, resolve e **explica** — o `.explain()` é o que permite
mostrar ao usuário por que o programa girou o tabuleiro.

### 2.5 Classificação de legalidade em três estados
`ChessVisionOFF_Puro\src\chess_diagram_ocr\fen_utils.py`

O critério é *"a violação depende do lado a jogar?"*. `FATAL_STATUSES` são erros reais de
leitura (sem rei, peões demais, peão na primeira fileira). `TURN_DEPENDENT_STATUSES`
(xeque oposto, xeque impossível) apenas indicam que o lado assumido está errado —
e é esse sinal que `semantics.infer_side_to_move` consome. `IGNORED_STATUSES` são
artefatos do `" w - - 0 1"` anexado automaticamente.

Nota registrada no código: um `.get(piece, empty)` anterior transformava lixo em casa
vazia silenciosamente, e fazia a "segunda opinião" reportar concordância total em
tabuleiros que nenhum dos dois leitores tinha lido. Agora `labels_from_fen` **levanta
exceção**. É o tipo de lição que não se reaprende de graça.

### 2.6 Subsistema completo de OCR de texto
`ChessVisionOFF_Puro\src\chess_diagram_ocr\text\` — **79 módulos, ~19.000 linhas**

**A versão 1.0 deste documento afirmou que não existia OCR de texto. Estava errado.**

Contém, entre outros: `leitor.py` (1480, a fachada), `pagina.py` (959, ordem de leitura),
`rico.py` (1185, **modelo de documento com texto rico**), `pdf_pesquisavel.py` (702,
camada de texto invisível), `dataset.py` (723, divisão sem vazamento), `notacao.py` (530,
prosa vs lance), `modelo.py` (524, o classificador de caracteres), `dicionario.py` (477,
desempate por léxico), `exportacao.py` (691), `binarizacao.py`, `colunas.py`,
`italico.py`, `negrito.py`, `colados.py` (glifos encostados), `trama.py` (meio-tom),
`empilhados.py`, `marca_fina.py` (apóstrofo vs vírgula), `caixa_alta.py`, `vertical.py`,
`duas_linhas.py`, `grade.py`.

Os adaptadores de motor (`RapidOcrRecognizer`, `EasyOcrRecognizer`, `TesseractRecognizer`,
atrás de um `TextRecognizer(Protocol)`) estão em `chess_diagram_ocr/ocr.py` (349) — **um
nível acima de `text/`**, não dentro dele. E `ocr_caption.py` (411) lê apenas a faixa ao
redor do diagrama.

> **Correções de atribuição (verificadas na frente F5, 2026-09-07).** A v2.0 deste
> documento descreveu errado três módulos, e o erro chegou ao briefing de um agente:
> - `camada.py` é o leitor de **negrito e itálico**, não um detector de CMap quebrado.
> - `conflitos.py` acha **colisões de rótulo de treino**, não é um árbitro de motores.
> - `text/ocr.py` **não existe**; o arquivo é `chess_diagram_ocr/ocr.py`.
>
> Lição operacional: descrição de módulo em documento de coordenação precisa ser
> conferida contra o arquivo antes de virar instrução. O agente da F5 conferiu e corrigiu
> — é o comportamento esperado.

O classificador de caracteres é `models/char_classifier.pt` (2,8 MB) + `char_meta.json`,
com **~314 classes** (`digit_*`, `lower_*`, `upper_*`, `ligature_*` incluindo pares de
glifos de figurino, `sym_*`), preso ao modelo por `modelo_sha256` + `classes_sha256`,
com temperatura calibrada **obrigatória**.

### 2.7 Índice de partidas e busca por posição
`ChessVisionOFF_Puro\src\chess_diagram_ocr\games_db.py` (1157) + `games_index.py` (402)
+ `games_cache.py` (664) + `games_census.py` (171)

**A versão 1.0 deste documento afirmou que não existia índice. Estava errado.**

Já existe: `PositionIndex`, `scan_by_players`, `scan_by_positions` (multiprocesso, em
blocos), `match_positions`, `rank_candidates`, com `games_index.sqlite` de **489 MB** e
`games_positions.sqlite` de 10,9 MB construídos sobre uma base PGN de **18,9 GB**.

Ou seja: a capacidade de "em qual partida está esta posição?" já funciona na escala que o
usuário tem. O que falta é busca **textual** no acervo de PDFs e o motor de regex.

### 2.8 Os dois espaços de coordenadas do PDF
`Editor_Diagramas_de_Xadrez\src\chess_pdf_editor\pdf_service.py`

```
page.rect = (escrita − origem) * rotation_matrix
escrita   = page.rect * derotation_matrix + origem
```

Páginas giradas com CropBox deslocado quebram qualquer sobreposição ingênua.
Já testado em `test_page_rotation.py` (469 linhas).

### 2.9 Gravação de PDF cancelável e atômica
Mesmo arquivo: `_CancelableWriter` + `save_document_atomically`.

Fatos medidos no código: um livro de 900 páginas emite **121.495 chamadas de `write()`
de ~5 bytes**; a primeira escrita só ocorre aos **57 % do tempo** (o MuPDF reconstrói a
xref antes); um `doc.save(path)` abortado deixou **2 bytes** no destino. A classe
deliberadamente **não** tem atributo `.name`, senão o PyMuPDF a trataria como caminho.

### 2.10 Reconstrução de `cmap` de fontes subconjuntadas
`PDFimport\PDFImport_v1.2.0\PDFImport\fontembed.py` (566 linhas)

Reconstrói a tabela `cmap` a partir do `ToUnicode` e do `CIDToGIDMap` do próprio PDF, e
sintetiza `name`/`OS/2`/`post`, com leitor/escritor SFNT escrito à mão. É raro, e é o que
permite exportar EPUB e DOCX preservando a fonte original do livro.

### 2.11 Analisador tolerante de PGN
`PGN_Live_Editor\pgn_live_editor\core\` — 21 módulos, 5.475 linhas, **93 % de cobertura**

Reconhece notação em texto ruidoso sem nunca falhar, propõe correções por hipóteses
cumulativas, valida por legalidade, **detecta sozinho o idioma do livro** (achando `Cf3`
ou `Dc7` passa a ler `Rh1` como Rei), e mantém dicionário de correções de OCR em três
camadas com escopos `token` / `prefixo` / `livre`.

### 2.12 Validação de ida-e-volta obrigatória
`PGN_Live_Editor\...\services\export_service.py`

Nenhum PGN é gravado sem ser relido pelo `python-chess` e conferido nó a nó. É o
princípio que a SPEC §11.3 exige para todos os exportadores — o padrão já existe.

### 2.13 Localizador neural para fotos
`Chess_diagram_to_FEN` (Jost Triller, MIT) — 5 modelos, 891 MB

Pipeline de 5 estágios: existência → segmentação para quad → rotação → FEN → orientação.
O `BoardRec` é ConvNeXt-Tiny por casa **mais** ConvNeXt-Tiny na imagem inteira, unidos
por um bloco de atenção — as casas se enxergam. Acurácia declarada 0,977.

O `warp_to_board` faz **zoom iterativo**: detecta, recorta mais perto, redetecta, até o
quad ocupar 70 % da imagem. É a peça mais reaproveitável para fotos de página.

Já está integrado como segunda opinião via `tsoj_reader.py` (203 linhas), que usa só 2
dos 5 modelos (232,8 MiB em vez de 296,1) e corrige duas incompatibilidades por
monkey-patch em vez de editar o clone. Ganho medido em
`Niemeijer - Zwarte Magie (1945)`, onde o classificador local desaba: leituras coerentes
**12/20 → 18/20**; três tabuleiros conferidos casa a casa: **60/41/23 → 64/64/64**.

### 2.14 Medições que economizam trabalho
Estas otimizações óbvias já foram testadas e **rejeitadas por medição**:
- **TTA** (7 vistas): ganhou 1 tabuleiro em 320, a 6× o custo. Desligado.
- **Temperatura calibrada** (T=1,85): dobrou a fila de revisão (ECE 0,000265 → 0,000837)
  sem consertar uma única casa. Registrada, não aplicada.
- **LLM local (F11), três das cinco tarefas**: `verify_diagram` (especificidade 0,000),
  `extract_stipulation` com LLM (12 invenções por zero acerto a mais) e `repair_ocr_region`
  (103 lances inventados por 69 consertados nas regiões rejeitadas). Ver
  `docs/quality/F11_REPORT.md`, `_C2.md`, `_C3.md`. Só `translate_notation_prose` entrou.

Nenhum agente deve "descobrir" essas ideias de novo sem ler estas medições antes.

### 2.15 Duplicações DELIBERADAS — não unifique

Nem toda repetição é desperdício. Estas existem porque os dois lados têm objetivos
**opostos**, e unificá-los quebra um dos dois. Estão fixadas por teste.

#### `looks_like_move` vs detecção de CMap quebrado

`caissa.notation.looks_like_move` é **permissivo de propósito**:

```
looks_like_move('lLib8')   -> True
looks_like_move('l0xd4')   -> True
looks_like_move('2.l0xd4') -> True
```

Isso está **correto** para a notação: `l0xd4` provavelmente É um `Nxd4` estragado pelo
OCR, e o `CandidateResolver` existe justamente para reparar isso. O portão precisa deixar
o lixo passar para poder consertá-lo.

E é **exatamente errado** para o detector de camada de texto quebrada, porque uma página
inteira de `l0xd4` é a assinatura de um CMap quebrado — a fonte de xadrez emite os
codepoints crus (`2.♘xd4` vira `2.l0xd4`). Um detector que perguntasse
"isto parece lance?" responderia "sim, tudo" e aprovaria a página destruída.

A frente F5 **recusou** essa delegação e fixou a recusa em teste. Mantenha assim.

#### Por que o probe de CMap do tronco não serve

O tronco detecta camada ruim contando U+FFFD. Medição da F5: **zero ocorrências em 560
folhas** do acervo. O modo de falha deste acervo não produz U+FFFD — produz codepoints
de fonte de xadrez legíveis como texto latino. Contar U+FFFD é procurar a chave debaixo
do poste.

---

## 3. Lacunas reais — o que de fato precisa ser construído

Esta lista foi corrigida. É bem mais curta do que a versão 1.0 supunha.

| Lacuna | Frente | Evidência de que é lacuna |
|---|---|---|
| **GPU nunca é usada** | F0/F4 | `device = torch.device("cpu")` no `Chess_diagram_to_FEN`; 0,635 s/diagrama medido. A RTX 5060 está parada. |
| **Recall de detecção 0,9478** | F3 | Medido em campo. Um em vinte diagramas não é achado. |
| **Detecção vetorial (via A)** | **F3-A** | Confirmado pelo levantamento de 27 PDFs: 2 livros são "vetorial/fonte" e nenhuma via atual os lê. Maior diferencial competitivo. |
| **Gerador de dados sintéticos** | F4 | Existe no `Chess_diagram_to_FEN` (`generate_chessboards.py`, 650 linhas) mas **não** no tronco. Portar. |
| **Document IR unificado** | F1 | `text/rico.py` é um modelo de texto rico, mas não cobre diagrama, partida e exportação multi-formato. Estender, não recomeçar. |
| **Exportação DOCX** | F8 | Não existe em nenhum projeto. |
| **Exportação LaTeX** | F8 | Não existe. |
| **Exportação HTML** | F8 | Só como pré-visualização interna. |
| **Exportação EPUB no tronco** | F8 | Existe em `PDFimport`, não no tronco. Portar. |
| **Busca textual no acervo + regex** | F10 | Índice de *posições* existe; de *texto* não. |
| **LLM local** | F11 | Não existe. |
| **Biblioteca de acervo** | F9 | Abre um livro por vez. Não há gestão de coleção. |
| **Unificação dos quatro apps** | F9 | Quatro executáveis separados hoje. |

---

## 4. Conflito de toolkit

| Projeto | Toolkit | Linhas de UI |
|---|---|---|
| ChessVisionOFF_Puro | **PyQt6** | ~14.000 |
| PGN_Live_Editor | **PyQt6** | 5.619 |
| Editor_Diagramas_de_Xadrez | PySide6 | ~7.000 |
| PDFimport | PySide6 (do Sigil) | 332 |

PyQt6 e PySide6 não coexistem no mesmo processo.

**Decisão (substitui a ADR-0001 original): PyQt6.**

Justificativa: ~19.600 linhas de UI em PyQt6 contra ~7.300 em PySide6. Portar a minoria
é três vezes menos trabalho. E o custo é reversível, porque o tronco já mantém toda a
decisão na camada `ui/` livre de toolkit — a camada `qt/` só pinta.

**Consequência a registrar honestamente:** PyQt6 é GPL. Distribuir binário fechado exigiria
licença comercial da Riverbank ou a migração para PySide6 (LGPL). Para uso próprio e
distribuição sob GPL, não há problema. A disciplina `ui/` mantém a porta aberta, e a
migração é mecânica: `pyqtSignal` → `Signal`, `pyqtSlot` → `Slot`.

---

## 5. Mapa de origem por frente

| Frente | Origem principal | Ação |
|---|---|---|
| F0 Fundação | novo | Construir |
| F1 Document IR | `ChessVisionOFF\text\rico.py` | Estender para diagrama, partida e 5 saídas |
| F2 Ingestão PDF | `ChessVisionOFF\pdf_io.py`, `pdf_text.py` + `Editor\pdf_service.py` + `PDFimport\extract.py` | Unificar |
| F3 Detecção | `ChessVisionOFF\board_detection.py` + `detection\` | Manter, elevar recall, **acrescentar via A e via neural** |
| F3-A Vetorial | **novo** | Construir — maior diferencial |
| F4 Classificação | `ChessVisionOFF\model.py`, `inference.py`, `decode.py` | Portar para GPU; portar gerador sintético do `Chess_diagram_to_FEN` |
| F5 OCR de texto | `ChessVisionOFF\text\` (79 módulos) + `ocr.py` | **Absorver e estender.** Não recomeçar. |
| F6 Notação | `PGN_Live_Editor\core\` + `ChessVisionOFF\text\notacao.py` | Absorver quase intacto |
| F7 Tipografia | `Editor\renderer.py` + `PDFimport\chessfig.py` + `fontembed.py` | Unificar e ampliar |
| F8 Exportadores | `PDFimport\builder.py` (EPUB) + `PGN\export_service.py` (padrão de ida-e-volta) + `ChessVisionOFF\text\pdf_pesquisavel.py` | Ampliar para 5 formatos |
| F9 UI | `ChessVisionOFF\qt\` + `ui\` (tronco) | Unificar os quatro apps, reprojetar visualmente |
| F10 Índice | `ChessVisionOFF\games_db.py` (posições, existe) | Acrescentar busca textual e regex |
| F11 LLM | **novo** | Construir |
| F12 Empacotamento | `ChessVisionOFF\packaging\` | Adaptar |

---

## 6. Regra para todos os agentes

Antes de escrever qualquer módulo, **procure a implementação existente** nos cinco
projetos. Se existir, leia, entenda por que foi feita daquele jeito — os comentários em
português documentam decisões duramente aprendidas e medições reais — e **estenda**.

Só escreva do zero o que está na seção 3.

Ao reaproveitar, registre a origem no cabeçalho:

```python
# Origem: ChessVisionOFF_Puro/src/chess_diagram_ocr/board_detection.py
# Absorvido em 2026-09-07. Alterações: <o que mudou e por quê>
```

E ao propor uma otimização, **verifique antes se ela já foi medida e rejeitada** (§2.14).

---

## 7. Metas corrigidas da SPEC

As metas de §11.3 da SPEC foram escritas antes deste levantamento e eram baixas demais
para classificação e altas demais em silêncio sobre detecção. Correção:

| Métrica | Meta antiga | Meta corrigida | Justificativa |
|---|---|---|---|
| Acurácia de casa | ≥ 99,5 % | **≥ 99,95 %** | já medido 99,9854 % |
| Diagramas perfeitos (laboratório) | ≥ 97,0 % | **≥ 99,0 %** | já medido 99,06 % |
| Diagramas perfeitos (campo) | — | **≥ 98,0 %** | medido 97,87 % |
| **Recall de detecção (campo)** | ≥ 99,0 % | **≥ 99,0 %** | medido 94,78 % — **é aqui que está o trabalho** |
| Precisão de detecção (campo) | ≥ 98,0 % | ≥ 98,5 % | medido 97,32 % |
| Segundos por diagrama | — | **≤ 0,10** | medido 0,635 em CPU; a GPU está ociosa |

---

## 8. Registro de correções da versão 1.0

A versão 1.0 deste documento foi escrita com base no levantamento de apenas três dos
cinco projetos e continha estes erros materiais:

1. **"Nenhum OCR de texto"** — falso. `ChessVisionOFF_Puro\src\chess_diagram_ocr\text\`
   tem 79 módulos e ~19.000 linhas, mais um classificador de caracteres de ~314 classes.
2. **"Índice e busca não existem"** — falso. `games_db.py` e companhia indexam uma base
   PGN de 18,9 GB em SQLite, com busca por posição funcionando.
3. **"Editor_Diagramas_de_Xadrez é o tronco"** — errado. ChessVisionOFF_Puro é seis vezes
   maior e muito mais maduro.
4. **"PySide6 vence"** — invertido. PyQt6 tem quase o triplo de linhas de UI.
5. **Metas de precisão baixas demais** — as metas de classificação já estavam superadas
   antes de o projeto começar; o gargalo real é detecção e velocidade.

O agente que redigiu a versão 1.0 não tinha o levantamento de ChessVisionOFF_Puro em
mãos. A lição operacional: **não escrever plano de absorção antes de ter o inventário
completo.**
