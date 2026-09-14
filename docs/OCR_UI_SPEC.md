# Especificação — elevação do OCR (diagramas, texto, glifos) e da interface

> **Data:** 2026-09-14 · **Versão:** 1.1 (corrigida pela crítica adversarial — `OCR_UI_ANALISE.md`
> §8) · **Deriva de:** `OCR_UI_ANALISE.md`.
> **Formato:** contrato de capacidade (capacidade → restrições → contrato de implementação →
> não-objetivos → questões abertas → passagem). É o que precisa ser verdade **antes** de
> qualquer passo do `OCR_UI_ROADMAP.md` começar; cada passo de lá cita a cláusula daqui que o
> governa.
> Este documento **não** substitui `SPEC.md`: estende as §6, §7 e §10 dela com o que o
> produto medido em 2026-09-14 ainda não cumpre. Onde conflita com `SPEC.md`, diz.
> Nomes curtos de relatório (`SOL_REPORT.md`, `ROTULAGEM.md`, `CORPUS.md`, `F*_REPORT*.md`,
> `CRITIC_CHARTER.md`) referem-se a `docs/quality/`; `Sol.md` está na raiz; o tronco é
> `..\ChessVisionOFF_Puro\src\chess_diagram_ocr\`.

---

## CAPACIDADE

Quem usa é o enxadrista-editor da `SPEC.md` §1: abre um livro em PDF — nativo ou
digitalizado, de qualquer década, em qualquer dos seis idiomas — e sai com um documento
editável (IR → DOCX/EPUB/HTML/LaTeX/PDF) e um PGN em que **cada diagrama é uma posição com o
lado certo a jogar, cada trecho de lances é uma partida legal encadeada a partir do diagrama
que o precede, e cada figurina impressa é uma peça, não uma letra**. O que muda com esta
capacidade: (a) os livros com camada de texto danificada — 16 dos 33 do acervo — passam a
ser lidos pelo OCR onde a camada mente, em vez de importados com a notação destruída; (b) os
estratos degradados deixam de estar presos ao teto de um motor; (c) o que o produto não
tem certeza aparece numa **janela de revisão** que mostra só o duvidoso, com o recorte ao
lado, para diagramas e para texto; (d) a interface principal deixa de ser sete abas de
utilitário e passa a ser um fluxo — livro, página, diagrama com o seu recorte, texto em
revisão, exportar — numa pele projetada, com a fita legível sem dica de ferramenta.

---

## RESTRIÇÕES

### R1. Regras fixas do projeto (herdadas, não negociáveis)

- **R1.1 Portão com sabotagem.** Todo portão novo traz uma sabotagem que o faz reprovar,
  executada e registrada antes de o portão valer (`HANDOFF.md` §7).
- **R1.2 Número com comando.** Nenhum número entra em relatório sem o comando que o produziu,
  por estrato, mediana de ≥ 3 execuções onde há aleatoriedade (`CORPUS.md` §5).
- **R1.3 Três números de campo juntos.** `field_exact` nunca sozinho — sempre com
  `export_rate` e `conditional_exact` (`F4_FIELD_REPORT.md` §6.5).
- **R1.4 Partição cega intocável.** Nada rotulado na partição `blind` entra em treino,
  calibração ou correção (`ROTULAGEM.md` §2; `review.blind_guard`).
- **R1.5 Nada de LLM em substituição de texto ou verificação de diagrama** (rejeitados por
  medição: `F11_REPORT_C3.md`, `ASSETS.md` §2.14). O LLM só sugere legenda.
- **R1.6 Sem caminho absoluto** em dados empacotados; pesos e léxicos com licença e SHA-256
  no `MANIFEST`/`weights.json` (SOL-9, SOL-12).
- **R1.7 O acervo não sai desta máquina** (`CORPUS.md` §0). Manifestos privados ficam
  gitignored.
- **R1.8 Commits por caminho nomeado**, nunca `git add -A` — outra sessão trabalha no mesmo
  checkout (`concurrent-sessions-same-repo`).
- **R1.9 ADR-0003.** ONNX Runtime só em subprocesso; nada de `onnxruntime-gpu` no processo do
  torch cu128. VRAM de pico ≤ 7,0 GB com visão e OCR ativos.

### R2. Invariantes de reconhecimento

- **R2.1 Abstenção real.** Uma leitura abaixo do limiar vai para `REVIEW`/`ABSTAINED`; nunca
  entra `accepted` (SOL-2). Vale para o novo candidato "camada de texto acusada" e para a
  cifra por livro.
- **R2.2 Âncora nunca é substituída se é palavra ou lance** (SOL-6). A cifra por livro só
  reescreve tokens **ilegíveis** (não-palavra, não-lance) e só com a tabela provada.
- **R2.3 Letra de peça impressa não vira figurina.** Um livro que imprime `Nf3` continua
  `Nf3` (guarda da fusão, `ROTULAGEM.md` §4c). A canonização figurina → letra é da camada de
  notação, na exportação.
- **R2.4 Legalidade decide, não adivinha.** Correção de lance só quando única, integralmente
  legal e com apoio visual (SOL-8). A cifra por livro herda a regra: um mapa entra na tabela
  quando a legalidade o provou em ≥ N posições independentes e 0 o contradisse.
- **R2.5 Lado a jogar tem fonte declarada.** O `SideSource` do tronco (`semantics.py`: `text`,
  `ocr`, `glifo`, três `*-page-scope`, `legality`, `database`, `manual`, `default`) é
  **estendido** com `move_number` e `caption` — nunca substituído — e a origem vai ao IR
  (`Diagram.side_to_move_source`) e ao relatório de importação, nas duas cascatas (tronco e
  `importer._diagram_node`).
- **R2.6 Velocidade não compra recall.** Nenhuma otimização que custe recall ou
  `export_rate` entra (`ROADMAP.md`, meia escala).
- **R2.7 Confiança por diagrama é probabilidade calibrada e discriminante de exatidão.**
  Publicada com ECE **e** com discriminação contra o preditor constante (AUROC ou risco ×
  cobertura) sobre **todos os diagramas casados** do conjunto de campo (114), não só os
  exportados (94) — com 93/94 exatos, ECE sozinho é cego. A UI, a fila de revisão e o portão
  de exportação só consomem esse número, não `min_confidence` cru; um tabuleiro reparado pelo
  decodificador deixa de ser vetado por aritmética (`decode.py`, `ACCEPT_MIN_CONFIDENCE`).

### R3. Invariantes de interface

- **R3.1 Os portões da F9 continuam valendo a cada mudança de tela**: contraste WCAG AA em
  100 % dos pares nas peles ativas, teclado completo com nomes, texto pintado, bloqueio
  ≤ 16 ms, ≥ 55 fps @ p95 em pan/zoom (`caissa.ui.audit.*`). Uma tela nova não fecha sem
  os cinco.
- **R3.2 Nada é decidido no widget.** Regra em `ui/` (sem toolkit), pintura em `qt/`
  (`ASSETS.md` §4) — a pele escura e a fita nova respeitam a divisão.
- **R3.3 Todo comando habilitado tem efeito alcançável** (`ui/audit/comandos`, F9-C16 §1).
- **R3.4 Rótulo desenhado, não dica.** Um controle da fita tem rótulo visível em toda
  densidade (portão 7 dos cegos: `toolTip()` não conta).
- **R3.5 A operação longa é cancelável, com progresso real e resultado parcial** (SPEC §10.5).
- **R3.6 Uma pele nova só entra como padrão com as três anteriores ainda disponíveis** até o
  crítico visual aprovar (SPEC §11.4).

### R4. Fronteiras de confiança e propriedade dos dados

- Verdade humana: `labeling/` (projeto), `benchmarks/corpus/golden/manifest.private.json`,
  `ChessVisionOFF_Puro/data/field_set.jsonl` — **o conjunto de campo é a régua e não se
  edita**; correções vão por sobreposição auditável (`benchmarks/field_corrections.json`).
- Modelos por livro: `models/tessdata/livros/<slug>/` + `livros.json` (hash do PDF).
- Tabela de cifra por livro: **nova**, ao lado do modelo do livro, chaveada pelo mesmo hash,
  com evidência por entrada.
- Pesos de motor opcional: `caissa/ocr/data/weights.json` com licença auditada antes de
  qualquer download.

---

## CONTRATO DE IMPLEMENTAÇÃO

### Atores

| ator | o que faz | onde |
|---|---|---|
| Editor (usuário final) | abre livro, revisa duvidosos, exporta | janela do produto (`Caissa.exe`) |
| Revisor/rotulador | produz verdade por linha e por diagrama; treina modelo do livro | aba Rotulagem, aba Dataset, `caissa-rotular` |
| Construtor | implementa um passo do roadmap | `src/caissa`, tronco |
| Crítico | reprova por medição, com sabotagem | `docs/quality/*_CRITIQUE_*.md` |
| Importador (`PdfImporter`) | orquestra nível 0, OCR, diagramas, IR | `caissa.ingest.pdf` |
| `OcrService` | portfólio, candidatos, fusão, decisão | `caissa.ingest.pdf.ocr_service` |

### Superfícies

**S1 — Reconhecimento de texto**

| interface | hoje | depois |
|---|---|---|
| `PdfImportOptions` | `enable_ocr`, `book_models`, `ocr` | + `ocr_contests_text_layer: bool = True` (T2 — **feito**, passo 2; contador `contested_pages` no relatório, fonte de página `text-layer+ocr`), + `book_cipher: bool = True` (G1) |
| `OcrServiceConfig` | `glyph_candidates`, `figurine_tessdata` | + `secondary_engines: tuple[str, ...] = ()` (T1, **dono: passo 1** — feito em 2026-09-14): os motores de nível ≥ 2 que o serviço acrescenta quando monta a cascata pelo registro; instalar deixa de mudar o comportamento por si; + `secondary_only_when_degraded: bool = True` — entram só nas páginas cujos sinais justificam uma variante do portfólio (`portfolio.degradation_reasons`); padrão medido: `("rapidocr",)` |
| `OcrService` | `recognize`, `recognize_image` | a disputa com a camada usa `recognize_image` sobre a página (ou faixa) renderizada; **não** há `recognize_region` — se for criado, é novo |
| fusão SOL-6 | candidatos: variantes × motor + glifos + `caissa_<lang>` | **feito em 2026-09-14 (passo 2), e ao contrário do previsto:** a camada danificada (`TextLayerVerdict.notation_damaged`) **ancora** a região (`OcrServiceConfig.damaged_layer_anchors=True`) e os motores entram por token — medido nas duas regras, a camada na âncora recupera mais lances (791/133/320 contra 720/109/258) **e** preserva melhor a prosa (CER de palavras 0,088/0,012/0,016 contra 0,094/0,022/0,068; `OCR_UI_REPORT_C1.md` §2.1). A confiança da camada continua a da região limitada pela página (portão cego 15); uma região sem lance algum conserva o próprio veredito |
| `caissa.ocr.notation.cipher` | resolve dama pela promoção | + `BookCipher` (tabela por livro, evidência por entrada, piso N, controle de contradição) — **novo módulo** `notation/book_cipher.py` |
| `caissa.ocr.training.tesseract_finetune` | linhas de texto | + linhas negativas (controles + prosa sem figurina) e sobreamostragem de classes raras (`FineTuneConfig.negatives`, `.oversample_rare`) |
| `caissa.ocr.labeling` | página escolhida à mão | + `queue.py`: fila de páginas por valor de rótulo (linhas `REVIEW`, livro sem rótulo, estrato vazio); a aba mostra "próxima que vale" |

**S2 — Reconhecimento de diagramas**

| interface | hoje | depois |
|---|---|---|
| lado a jogar — **duas cascatas** | tronco `semantics.infer_side_to_move` (texto → legalidade → default, só na via raster); suíte `importer._diagram_node` aplica o lado só quando `captions.DiagramContext.side_to_move` foi declarado | `DiagramContext` da suíte ganha `first_move_number` e `caption_after_move`; a regra `move_number`/`caption` entra nas duas cascatas entre texto e legalidade; `SideSource` estendido (R2.5); o relatório conta por origem |
| confiança do diagrama | `min_confidence` da casa; ECE só por casa | + `DiagramConfidence` (**novo**, `caissa.vision.classify.confidence`): p(exato) sobre margem mínima, casas reparadas pelo decodificador, legalidade, regra de orientação, via, estrato; ECE **e** discriminação publicados (R2.7); usada pela fila e pelo âmbar |
| portão de exportação | `ACCEPT_MIN_CONFIDENCE = 0,80` (`config.py`) em `min_confidence`, aplicado em `batch.py` e `field_eval.py`; reparo ⇒ ≤ 0,5 ⇒ nunca exporta | piso em `DiagramConfidence`, por estrato, escolhido na curva risco × cobertura para manter `conditional_exact` e subir `export_rate` no hachurado e no scan-puro |
| `caissa.vision.detect.font_catalog` | 37 famílias (29 verificadas, 7 não, `skak_diagram` inferida) | + fallback: glifo vetorial desconhecido renderizado → leitor de glifos → `RecognitionPath.VECTOR_INFERRED` a ≤ 0,85 |
| gerador sintético (`vision/train/synthgen`, `SynthConfig`) | sem degradação de digitalização (warp, matiz, texto, inversão, deslocamento, temas — inclui um tema hachurado) | + degradações de digitalização (hachura, ruído, JPEG) **só se** o diagnóstico de D1 apontar erro de textura; fine-tune de cabeça / destilação como experimentos com `lab_gate.py` |

**S3 — IR**

| nó / campo | mudança |
|---|---|
| `Diagram.side_to_move` | ganha `side_to_move_source` (R2.5) e `confidence` (R2.7) |
| `Paragraph` de estilo `Movetext` → `GameScore` | não existe classe `Movetext`: é `ParagraphStyle(name="Movetext")` (`importer.py`) sobre `RegionKind.MOVETEXT` (`paragraphs.py`). Passo novo `caissa.ingest.pdf.games` (T3): FEN do diagrama + lado + tokens reparados → analisador tolerante de `caissa.notation` (`parser`, `book_import`, `variation_builder`, `pipeline.build_games_for_export` — absorvidos do `PGN_Live_Editor`, nunca chamados por `ingest/`) → `legality_repair` → `GameScore` (`core/model/game.py`; variantes são `MoveNode.children[1:]`) com proveniência por lance; o parágrafo permanece quando não há posição de partida |
| spans de OCR | já carregam motor/confiança/revisão (SOL-10); ganham `cipher_evidence` quando reescritos por G1 |
| `review_items` | passam a incluir diagramas com `DiagramConfidence` abaixo do limiar, não só texto |

**S4 — Interface**

| tela / componente | hoje | depois |
|---|---|---|
| Editor de posição (aba Resultado) | tabuleiro + página inteira | + **painel de recorte** do diagrama ampliado, casa sob o ponteiro espelhada, top-3 na dica; casas com margem baixa em âmbar por padrão (U1) |
| Sobreposição na página | caixas clicáveis | caixas **numeradas** com estado (lido / duvidoso / corrigido), sincronizadas com o tabuleiro |
| Revisão de texto | inexistente (só bancada) | **`PainelDeRevisaoDeTexto`** sobre `ReviewQueue`: só `REVIEW`/`ABSTAINED`, recorte + leitura + alternativas + motivo, aceitar / editar / manter imagem → IR (U2); reutiliza os widgets de `caissa.ui.views.rotulagem` |
| Fita (pele `Fita`, S-227 = Imagem 2) | **sete grupos** (`ui/comandos.py` `GRUPOS`, decisão registrada); inacabada: título ausente na compacta (0/5), 6/24 sem rótulo, tinta 17,6–41,4 % — números de scripts avulsos, sem portão | os três números fechados **com portão próprio** (`caissa.ui.audit.fita`, `caissa.ui.audit.icones` — novos, promovidos de `benchmarks/reports/ui/c12/`), ícone 24 px tinta ≥ 50 %, rótulo desenhado, hit ≥ 40 px; os sete grupos mantidos (U3) |
| Visor | `QPixmap` inteiro reescalado | `QGraphicsView` com ladrilhos, render fora da thread, LRU por página e nível (U4) |
| Pele | 3 peles: Clássica (padrão), **Foco** (escura, S-224 = Imagem 1), Fita | padrão de fábrica decidido em Q3; Foco com tokens projetados (SPEC §10.2); polimento (raio concêntrico, tabular-nums, foco, contorno de imagem, vazio desenhado) nas três (U5) — **nenhuma pele nova** |
| Trilho do livro | — | miniaturas com estado por página, progresso da importação cancelável, botão Exportar (U6) — atrás de decisão (Q4) |
| Contagem de ações do usuário | não há instrumento (`ui/audit/execucao` mede threads de fundo, não cliques) | `caissa.ui.audit.percurso` (**novo**): reproduz um percurso declarado e conta ações; sabotagem própria |

### Estados e transições

**Página na importação (T2):**

```
camada de texto ──veredito nível 0──► ACEITA (≥ 0,82) ──► IR pela camada
                                   ├─► MANTIDA (0,55 ≤ v < 0,82) ──► regiões MOVETEXT com mangled > 0,15
                                   │                                  └─► OCR da região; camada = candidato; fusão ──► IR
                                   └─► REJEITADA ──► OCR da página inteira (como hoje)
```

**Diagrama:**

```
detectado ──► classificado ──► decodificado (restrições) ──► orientado ──► lado a jogar (fonte)
   ──► DiagramConfidence ──► ≥ limiar: EXPORTÁVEL · < limiar: REVISÃO (fila) · ilegal fatal: ABSTIDO
```

**Span de texto:** `ACCEPTED | REVIEW | ABSTAINED` (SOL-2) → na janela de revisão:
`aceito | editado | mantido_como_imagem`, gravado em `verified_by_human` e em
`corrections.json`; nunca em `blind`.

**Tabela de cifra do livro:** `vazia → em_evidência (n < N ou contradição) → provada (n ≥ N, 0
contradições) → aplicada`; uma contradição posterior **rebaixa** a entrada e o relatório diz.

### Implicações de dados

- `models/tessdata/livros/<slug>/cipher.json` — `{ "W": {"piece": "Q", "support": 23,
  "contradictions": 0, "examples": [...]}, ... }`, hash do PDF, versão.
- `benchmarks/corpus/golden/` — novos itens `pdf-scan` com `start_fen` obrigatório em regiões
  `movetext` (é o que dá significado ao portão de lances).
- `benchmarks/reports/diagram_confidence_*.json` — ECE, Brier, curva risco × cobertura por
  estrato.
- `docs/quality/OCR_UI_REPORT*.md` — um relatório por ciclo, com o comando ao lado de cada
  número (R1.2).

### Segurança, licenças, política

- Pesos de Surya/Paddle/RapidOCR: licença conferida e registrada em `weights.json` **antes**
  do download; se a licença não for auditável, o motor não entra (R1.6).
- Nada sai da máquina (R1.7). A fila de rotulagem lê só o manifesto privado local.
- A pele escura usa o conjunto `cburnett` (licença explícita); a arte da Chess.com continua
  fora (`HANDOFF.md` §6.1).

### Observabilidade

- Relatório de importação ganha: fonte do lado a jogar por diagrama; `DiagramConfidence` e
  ECE do livro; regiões em que a camada foi contestada e quem venceu a fusão; entradas de
  cifra aplicadas com suporte; motor secundário chamado × vezes, tempo, VRAM de pico.
- `ocr_trace.json` inclui o candidato `text_layer` e a decisão da fusão por token.
- Portões: `benchmarks/sol_gate.py`, `benchmarks/field_exact.py`, `benchmarks/lab_gate.py`,
  `caissa.ui.audit.*` — todos rodados por ciclo; novos: `benchmarks/diagram_confidence_gate.py`,
  `benchmarks/games_gate.py` (lances legais encadeados por página).

---

## NÃO-OBJETIVOS

- Biblioteca de acervo (grade de capas, facetas) — lacuna F9 conhecida, fora daqui.
- Migração PyQt6 → PySide6 — decisão de licença (`ASSETS.md` §4), fora daqui.
- Análise com engine além da legalidade — pendência SPEC §13 × F9-C16, decisão humana.
- OCR de partituras manuscritas, fotos de página sem PDF (a Via C neural existe para fotos
  embutidas; importar JPEG solto não entra neste ciclo).
- Treinar um `eng` global melhor — medido como inviável com 700 linhas (`ROTULAGEM.md` §4c);
  o modelo é por livro.
- Qualquer alavanca do `OCR_UI_ANALISE.md` §6.

---

## QUESTÕES ABERTAS (bloqueiam o passo que as cita)

| # | questão | bloqueia | recomendação |
|---|---|---|---|
| Q1 | Qual segundo motor instalar primeiro — RapidOCR (ONNX, worker isolado, latino) ou Surya (torch, cirílico, VRAM partilhada)? | passo 1 | medir os dois no `bench_sol.py` por estrato e idioma; instalar o que fechar 150 DPI sem regressão nos limpos; Surya exige medir VRAM com a visão ativa (R1.9) |
| Q2 | Quantas horas de rotulagem humana por semana, e quem? Inclui o **passo 0** (preencher `start_fen` nas 13 páginas já rotuladas). | passo 0; passo 5; os portões vermelhos de Sol; os portões dos passos 7 e 11 | passo 0 já (curto); a fila por valor de rótulo (passo 5) antes de rotular mais; então ≥ 20 páginas para a revisão cega, 200 para a meta |
| Q3 | Foco (escura) ou Fita como padrão de fábrica em vez da Clássica? | passo 16 | Foco, com as três peles mantidas em *Ver ▸ Aparência* até o crítico visual aprovar (R3.6) |
| Q4 | Refazer o fluxo principal sem abas (trilho do livro)? Muda a janela medida em 16 ciclos. | passo 17 | confirmar antes; se sim, é o último passo e reroda os cinco portões da F9 |
| Q5 | Piso N de evidência da cifra por livro | passo 3 | começar em 5 confirmações independentes (posições distintas) e 0 contradições; o portão de controles decide — **depois** de contar quantos lances provados existem no Gaprindashvili (passo 3, tarefa 0) |
| Q6 | O portão `bloqueio` está **reprovado** hoje (7 operações > 16 ms). R3.1 diz "tela nova não fecha sem os cinco". Qual vale para os passos 13 e 14, antes de o 15 fechar o visor? | passos 13, 14 | regra: 13 e 14 não podem **aumentar** o número de operações > 16 ms nem a mediana de abrir PDF; quem fecha o `bloqueio` é o 15, e até lá o item continua declarado aberto |

---

## PASSAGEM

**Trabalho humano curto antes de tudo**: passo 0 (`start_fen`). **Pronto para implementação
direta**: passos 1–15 do `OCR_UI_ROADMAP.md` (Q1, Q5 e Q6 respondidos pela medição do próprio
passo ou pela regra acima). **Precisa de decisão de produto**: Q2 (trabalho humano
continuado), Q3 e Q4 (forma da janela; bloqueiam 16 e 17). Próxima lane: `OCR_UI_ROADMAP.md`
(execução por passos, com portões e sabotagem), crítica por `docs/quality/CRITIC_CHARTER.md`
a cada ciclo.
