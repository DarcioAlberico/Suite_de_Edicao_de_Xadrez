# Roadmap — elevação do OCR (diagramas, texto, glifos) e da interface

> **Data:** 2026-09-14 · **Versão:** 1.1 (corrigida pela crítica adversarial — `OCR_UI_ANALISE.md`
> §8) · **Contrato:** `OCR_UI_SPEC.md` · **Diagnóstico:** `OCR_UI_ANALISE.md`.
> **Formato:** plano de construção por passos (blueprint). Cada passo é autocontido — um
> construtor que chegue frio, sem esta conversa, executa o passo lendo só o **briefing** dele
> e os arquivos que ele nomeia. Cada passo tem portão **com sabotagem que reprova de verdade**,
> critério de saída, nível de modelo e como desfazer.
> **Modo de trabalho:** direto em `main`, commits por caminho nomeado (R1.8) — é como o
> projeto trabalha, com outra sessão no mesmo checkout. Ramos são opcionais para os passos
> 15–17 (mexem na forma da janela).
> Nomes curtos de relatório (`SOL_REPORT.md`, `ROTULAGEM.md`, `CORPUS.md`, `F*_REPORT*.md`)
> referem-se a `docs/quality/`; `Sol.md` está na raiz. "Tronco" é
> `..\ChessVisionOFF_Puro\src\chess_diagram_ocr\`. Os dois "Dvoretsky" do acervo são nomeados
> pelo arquivo: **SFC4** (*Dvoretsky & Yusupov — Secrets of Positional Play*, digitalizado, o
> rotulado) e **DEM** (*Dvoretsky's Endgame Manual*, nativo, Merida, controle E1).

---

## 0. Pré-voo (feito em 2026-09-14)

| verificação | resultado |
|---|---|
| repositório git, ramo padrão | sim, `main`; remoto `origin` GitHub; `gh` autenticado |
| plano anterior no mesmo tema | não há `plans/`; os roadmaps existentes são `ROADMAP.md` (frentes F0–F12) e `Sol.md` (OCR de prosa) — este documento **não os substitui**, só toma as pendências que eles deixaram nomeadas |
| memória do projeto | `f2-ingest-state`, `sol-ocr-state`, `labeling-training-state`, `bundle-rotulagem-tab`, `concurrent-sessions-same-repo` — lidas |
| ambiente | `.venv` (Python 3.11.9, torch cu128, pytest), `.venv-pack` (PyQt6, sem pytest), tronco `..\ChessVisionOFF_Puro\.venv` (Python 3.10, PyQt6 — **não importa `caissa`** sem `PYTHONPATH`) |

**Atalhos usados abaixo**

```
PY      = .venv\Scripts\python.exe                        (suíte, benchmarks, pytest)
PYQ     = ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe (testes do tronco)
PYQ-UI  = PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe   (testes PyQt6 da suíte)
GOLD    = benchmarks\corpus\golden\manifest.private.json  (gitignored; fica na máquina)
PDF     = ..\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf      (o PDF dos portões da F9)
```

**Portões da F9** (`caissa.ui.audit.*`) — a receita é a de `F9_REPORT_C16.md` §17, e falha sem ela:

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<suite>\src;<tronco>\src
set AUDIT=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit
%AUDIT%.contraste     --saida <pasta>
%AUDIT%.teclado       --pdf "%PDF%" --saida <pasta>
%AUDIT%.comandos      --pdf "%PDF%" --saida <pasta>
%AUDIT%.texto_pintado --pdf "%PDF%" --saida <pasta>
%AUDIT%.quadros       --pdf "%PDF%" --saida <pasta>        (3×; fps @ p95)
%AUDIT%.bloqueio      --pdf "%PDF%" --saida <pasta>
%AUDIT%.capture       --marca <cN> --pdf "%PDF%" --saida <pasta>   (--saida é obrigatório)
%AUDIT%.amostrario    --saida <pasta> --estados
```

Abaixo, `AUDIT.<x>` abrevia essa linha com a pasta `benchmarks\reports\ui\<ciclo>`.

**Invariantes verificadas depois de todo passo** (não passam sem estar verdes):

```
PY -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py   # ~13 min
PY benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json                        # 0 importações silenciosas, 0/12 controles
git status --short   # só os caminhos do passo
```

---

## 1. Mapa de dependências e faixas paralelas

```
 0 (humano) start_fen nas 13 páginas ──────────────┬────────────────┐
                                                   ▼                ▼
FAIXA A — texto e glifos          FAIXA B — diagramas               FAIXA C — interface
 1 motor secundário                7 lado a jogar ◄── 0             12 fita: portões + rótulos
 2 OCR contesta a camada           8 confiança por diagrama ──┐     15 visor por ladrilhos
 3 cifra por livro ──┐             9 rendimento dos barrados ◄─┘     13 editor com recorte ◄── 8
 4 negativos e raras │            10 fallback vetorial               14 revisão de texto  ◄── 8 (fila)
 4b modelo na âncora ◄── 4                                            
 5 fila de rotulagem │                                               16 Foco padrão + polimento ◄── 12
 6 léxico ru + lances│                                               17 trilho do livro ◄── 13,14,15,16 (Q4)
                     └──► 11 Paragraph Movetext → GameScore ◄── 0, 7        18 (opcional) cor da peça ◄── 8
```

- **Sem dependência entre si** (um construtor cada, em paralelo): 1, 2, 3, 4, 5, 6, 8, 10,
  12, 15. O 7 espera o 0 (só para o portão; o código pode começar).
- **Arquivos partilhados que exigem ordem** (quem entra depois rebaseia):

| arquivo | passos | ordem |
|---|---|---|
| `src/caissa/ingest/pdf/importer.py` | 2, 3, 7, 11 | 2 → 3 → 7 → 11 |
| `src/caissa/ingest/pdf/ocr_service.py` | 1 (`secondary_engine`), 2, 4b (`book_model_anchors`) | 1 → 2 → 4b |
| `src/caissa/ocr/fusion.py` | 2, 3 | 3 → 2 |
| `src/caissa/core/model/` (`Diagram`) | 7, 8 | 7 → 8 |
| `src/caissa/ui/views/rotulagem.py` | 4 (`DialogoDeTreino`), 5 (botão) | 4 → 5 |
| tronco `qt/fita.py`, `ui/medidas_da_fita.py` | 12, 16 | 12 → 16 |
| tronco `qt/painel_de_resultado.py` (13) e `qt/visor.py` (15) | não se tocam; o 13 só usa a API pública do visor | — |

- **Nível de modelo**: *forte* (raciocínio sobre regra de fusão/legalidade ou forma da
  janela) em 2, 3, 8, 11, 17; *padrão* nos demais.

---

## 2. Os passos

### Passo 0 — (humano) FEN inicial nas regiões de lances já rotuladas

**Objetivo.** Dar posição de partida às regiões `movetext` das 13 páginas rotuladas, para que
os portões dos passos 7 e 11 tenham verdade.

**Briefing.** `labeling/pages/*.json` tem 256 regiões; o campo `start_fen`
(`src/caissa/ocr/labeling/model.py`) está **vazio em todas**, e `null` nos 474 itens de `GOLD`.
Na aba Rotulagem (ou `caissa-rotular`), botão direito na região → «FEN inicial dos lances…»
(`ocr/labeling/app.py`); o diagrama que precede o trecho dá a posição (tabuleiro editável da
aba Resultado copia a FEN). Depois, *Exportar → Fundir no manifesto* regrava os itens
(`ROTULAGEM.md` §3) e o baseline de Sol precisa ser recongelado (hash do corpus muda).

**Portão.** Contagem: regiões `movetext` com `start_fen` ≠ "" nas 13 páginas (esperado: todas
as que seguem um diagrama). Registrar o número em `OCR_UI_REPORT_C1.md` §0 — é o denominador
dos passos 7 e 11. Sem sabotagem: é dado, não código.

**Saída.** `labeling/pages/*.json`, `GOLD` regravado, `docs/quality/sol/baseline.json` recongelado
(`PY benchmarks\bench_sol.py --system baseline --label baseline --publish`).

---

### Passo 1 — Segundo motor de OCR ao vivo

**Objetivo.** Um motor além do Tesseract instalado, medido por estrato e idioma, roteado
onde vence e ausente onde não.

**Briefing (autocontido).** O produto lê texto com `caissa.ingest.pdf.ocr_service.OcrService`
sobre o Tesseract 5.5.0. O roteamento por estrato (`caissa/ocr/routing.py`), o orçamento, os
contratos por versão (`ocr/engines/contracts.py`), os adaptadores (`engines/{surya,paddle,
paddle_structure,rapidocr}.py`), o worker em subprocesso (`engines/worker.py`, ADR-0003) e o
registro de pesos com licença (`engines/weights.py`, `ocr/data/weights.json`) existem.
**Atenção:** `tests/unit/ocr/test_optional_engines.py` injeta módulos **falsos** em
`sys.modules` e nunca pula — com o motor real instalado o resultado é idêntico; ele não é
evidência de que o real funciona (anti-padrão 5). Os extras estão em `pyproject.toml`
(`ocr-surya`, `ocr-paddle`, `ocr-rapid`). O `.venv` tem torch cu128 instalado por fora do
`pyproject` — **nunca** `uv sync`/`uv run` sem `--no-sync` (`ROTULAGEM.md` §1). Estratos e
metas: `SOL_REPORT.md` §1 e §3 (150 DPI 0,0371 vs 0,020; foto 0,116; fax 0,063; russo 13–26 %
de dicionário). Medição: `benchmarks/bench_sol.py`; portão: `benchmarks/sol_gate.py`; baseline
congelado `docs/quality/sol/baseline.json` (recongelado no passo 0 se ele já correu).

**Tarefas.**
1. Auditar licença dos pesos do candidato e gravar em `weights.json` **antes** de baixar
   (R1.6). RapidOCR (ONNX) vai pelo worker isolado; Surya (torch) mede VRAM de pico com o
   classificador de casas residente (`vision/runtime/residency.py`) — teto 7,0 GB (R1.9).
2. Instalar (`pip install -e .[ocr-rapid]` ou `[ocr-surya]` no `.venv`); se o ONNX Runtime
   CPU não coexistir com o torch, venv à parte e o worker; GPU do ONNX nunca no mesmo processo.
3. **Teste de fumaça real** (novo): `tests/integration/test_engine_live.py`, marcado `slow`,
   que só corre com o motor real instalado (`pytest.importorskip`) sobre um item do corpus e
   exige texto não vazio com confiança > 0 — é o que o contrato falso não prova.
4. `OcrServiceConfig.secondary_engine: str | None` (SPEC S1) — dono deste passo.
5. Medir: `bench_sol.py --system sol --label sol_<motor> --publish --compare
   docs\quality\sol\baseline.json`, por estrato e idioma.
6. Ajustar `routing.py`: o motor secundário entra só nos estratos/idiomas em que venceu
   fora do IC bootstrap; nos limpos, continua o Tesseract.
7. Se forem os dois candidatos (Q1), a tabela comparativa vai ao relatório e a decisão fica
   registrada.

**Verificação.**
```
PY -m pytest tests\unit\ocr -q
PY -m pytest tests\integration\test_engine_live.py -q -m slow
PY benchmarks\bench_sol.py --system sol --label sol_<motor> --publish --compare docs\quality\sol\baseline.json
PY benchmarks\sol_gate.py --report-only docs\quality\sol\sol_<motor>.json
```

**Portão e sabotagem.** CER `scan_degraded_150` ≤ 0,020 **ou** queda fora do IC em ≥ 2
estratos degradados sem regressão fora do IC em `native`/`scan_clean_300`; controles 0/12;
VRAM de pico ≤ 7,0 GB. *Sabotagem:* rotear o motor novo também no `native` com peso 1,0 —
o `sol_gate` tem de acusar regressão por estrato no nativo (o IC existe: `bootstrap_mean_ci`).

**Saída.** `docs/quality/OCR_UI_REPORT_C1.md` §1 com a tabela por estrato; `weights.json`;
`ocr_service.py` (a rota ficou no serviço, pela evidência da página — `degradation_reasons` —
e não em `routing.py`, que roteia por idioma/tipo de região); memória `sol-ocr-state` atualizada.
**Desfazer:** `OcrServiceConfig(secondary_engines=())`; os pesos ficam no disco sem uso.
**Estado (2026-09-14): executado** — ver a tabela de mutações do §4 e o relatório.

---

### Passo 2 — O OCR contesta a camada de texto danificada

**Objetivo.** Nas páginas em que a camada de texto é mantida a 0,55 por notação destruída, o
OCR corre e a camada entra na fusão como candidato — não como âncora.

**Briefing.** O nível 0 (`caissa/ocr/engines/pdf_text_layer.py`, `ingest/pdf/textlayer.py`)
julga a camada; `mangled_move_ratio > 0,15` rebaixa a página a 0,55 e *"outranks every
verdict below"* (controles ≤ 0,065; Gaprindashvili ≥ 0,195). A 0,55 a camada é **mantida** e o
importador (`ingest/pdf/importer.py`) não chama o OCR — `ROTULAGEM.md` §7c. A faixa "mantida"
(0,55 ≤ v < 0,82) também contém páginas a 0,70 (`unjudged_script`) e 0,80 (`borderline`) sem
dano — a disputa é acionada pelo **sinal `mangled`**, não pela faixa. Em Gaprindashvili p202
*"a prosa correta e os lances destruídos dividem a mesma linha"* (`HANDOFF.md` §4.1;
`ocr/page.py`), e `RegionKind.MOVETEXT` só é atribuído a blocos de análise
(`ingest/pdf/paragraphs.py`): onde a região não é separável, a disputa é **por token na
página inteira**. A fusão por token é `ocr/fusion.py` (SOL-6: âncora que é palavra/lance nunca
é substituída). O serviço tem `recognize` e `recognize_image` (**não** há `recognize_region`).
Régua de "lance legível": `piece_prefixes` em `benchmarks/notation_integrity.py` — nunca
`looks_like_move` (`caissa/notation/candidates.py`), permissivo de propósito (`ASSETS.md`
§2.15). A lista dos "16 de 33" livros acusados é anterior ao conserto `ignore_diagram_fonts`
(`F2_REPORT.md` §5.4) e inclui o Polgar — **reobter** com `--what verdicts`. Medição ponta a
ponta: `benchmarks/bench_ingest.py --sample 12 --dump`.

**Tarefas.**
0. `PY benchmarks\notation_integrity.py --what verdicts --json benchmarks\reports\ni_c2_antes.json`
   — a lista atual dos livros acusados e dos controles; é o "antes".
1. `PdfImportOptions.ocr_contests_text_layer: bool = True`.
2. No importador, página com `mangled_move_ratio > 0,15`: renderizar (a página, ou as faixas
   das regiões `MOVETEXT` quando o layout as separa) e chamar `OcrService.recognize_image`.
3. Na fusão, candidato `text_layer` **por token**, com a confiança calibrada do nível 0 da
   **região** (regra do portão cego 15: "região não vale mais que a página") e a marca
   `accused=True`, que o impede de ancorar. Prosa: a regra "âncora que é palavra ou lance não
   é substituída" a protege (no controle limpo a camada acerta 98,8 %).
4. `ocr_trace.json` e o relatório de importação registram "camada contestada em N regiões;
   venceu: OCR X, camada Y".
5. Testes em `tests/unit/ingest/test_importer.py`: página acusada → OCR chamado; página
   aceita ou a 0,70/0,80 sem `mangled` → não chamado; opção em `False` → não chamado.

**Verificação.**
```
PY -m pytest tests\unit\ingest tests\unit\ocr -q
PY benchmarks\notation_integrity.py --what verdicts --json benchmarks\reports\ni_c2_depois.json
PY benchmarks\bench_ingest.py --sample 12 --dump
```

**Portão e sabotagem.** Nos livros acusados (lista do "antes"): lances com `piece_prefixes`
por página **sobem** e o CER da prosa nas mesmas páginas não muda fora do IC; nos controles
limpos, **zero** caractere alterado (`bench_ingest --dump` diferenciado). *Sabotagem:* deixar a
camada ancorar (`accused=False`) — no Gaprindashvili p202 os tokens mangled (`!txg7`, `Wxg7`)
têm de voltar ao IR, e o teste de corpus que os nomeia tem de reprovar.

**Saída.** `OCR_UI_REPORT_C1.md` §2; `importer.py`, `ocr_service.py`, `page.py`, `pdf_text_layer.py`,
`notation_integrity.py --what contest`. **Desfazer:** `ocr_contests_text_layer=False`.
**Estado (2026-09-14): executado.** A disputa é por região com a camada na âncora (a regra
"acusada nunca ancora" foi medida e perdeu — §2.1 do relatório); o portão foi medido pelo
instrumento novo, não pelo `bench_ingest --dump` diferenciado.

---

### Passo 3 — Cifra por livro aprendida da legalidade

**Objetivo.** Uma tabela sósia → peça por livro, provada pela legalidade em posições
independentes, aplicada só a tokens ilegíveis, com evidência na proveniência.

**Briefing.** O Tesseract lê figurina como sósia latino estável **dentro do livro** — SFC4:
♖→H, ♕→W, ♘→S, ♗→2/8/& (`ROTULAGEM.md` §4b); Gaprindashvili: `W`=dama, `H`=torre, `S`=**rei**
(`HANDOFF.md` §4.1) — o mapa muda de fonte para fonte. `caissa/ocr/notation/cipher.py` resolve
a dama pela promoção e **se recusa a adivinhar o resto**; o ilegível cai 78,5 → 34,3 %, medido
por `benchmarks/notation_integrity.py --what decode` (`F5_REPORT_C2.md` §6.3). A reparação por
legalidade (`caissa/notation/legality_repair.py`; `ocr/notation/validate.py`, SOL-8) decide
lance a lance **quando tem posição** — e o replay só tem posição para 2 % dos lances do corpus
(`SOL_REPORT.md` §3). Quatro falsos positivos reais são o controle (`tests/unit/ocr/
test_cipher.py`: russo correto, `K` latino em livro russo, travessão, livro português com
lances em inglês). Modelo por livro: `models/tessdata/livros/<slug>/`, chaveado por
`PdfDocument.content_hash` (`ocr/training/books.py`). **Não alargar o alfabeto** do corretor.

**Tarefas.**
0. **Contar primeiro**: quantos lances *provados pela legalidade* existem hoje nas páginas do
   Gaprindashvili e nas do SFC4 com `start_fen` (passo 0). Se forem < 20 por livro, a tabela
   não tem de onde vir — registrar e reordenar este passo para depois do 11.
1. Novo `ocr/notation/book_cipher.py`: `BookCipher` com entradas `{sósia: {piece, support,
   contradictions, examples}}`; `observe(token_lido, lance_provado)`; `proven(N=5)`;
   `rewrite(token)` só para token que **não** é palavra nem lance válido (R2.2).
2. Persistir em `models/tessdata/livros/<slug>/cipher.json`; `PdfImportOptions.book_cipher=True`.
3. No importador: primeira passada coleta evidência (SOL-8 já marca os lances provados);
   segunda reescreve ilegíveis com a tabela provada; o span ganha `cipher_evidence` (SOL-10).
4. Contradição posterior rebaixa a entrada e o relatório diz.
5. Testes (`tests/unit/ocr/test_book_cipher.py`, novo): tabela provada reescreve `Wd5` →
   `♕d5`; entrada com contradição não reescreve; os quatro falsos positivos intactos; livro
   bilíngue não ganha tabela.

**Verificação.**
```
PY -m pytest tests\unit\ocr\test_cipher.py tests\unit\ocr\test_book_cipher.py tests\unit\notation -q
PY benchmarks\notation_integrity.py --what decode --json benchmarks\reports\ni_c3_decode.json
PY benchmarks\bench_sol.py --system sol --label sol_cipher --publish --compare docs\quality\sol\baseline.json
```

**Portão e sabotagem.** Gaprindashvili: ilegível (`--what decode`) 34,3 % → ≤ 15 % **sem**
lance inventado a mais (`caissa.ocr.metrics` `invented`); controles 0/12; livro português com
lances em inglês: 0 tokens reescritos. *Sabotagem:* injetar numa página-controle um token
**realmente ilegível** (`@c2`) e uma tabela com `N=1` provada por um único lance — o portão de
inventados tem de acusar a reescrita; com `N=5` o mesmo token fica intacto.

**Saída.** `OCR_UI_REPORT_C1.md` §3. **Desfazer:** `book_cipher=False`.
**Estado (2026-09-14): executado.** O portão foi medido pela bancada `--what contest` (peça
certa por página), não pelo `--what decode`, porque a âncora das páginas é a camada desde o
passo 2 e a cifra que importa é a dela (aglomerados), não a do Tesseract.

---

### Passo 4 — Amostras negativas e classes raras no ajuste fino

**Objetivo.** O modelo por livro deixa de emitir figurina no ruído e aprende as peças raras.

**Briefing.** `caissa/ocr/training/tesseract_finetune.py` ajusta a LSTM sobre `ground_truth/`
+ `index.jsonl` (partições dev/calib; cega nunca entra). Medido em `ROTULAGEM.md` §4c: o
`caissa_eng` produz `♖ … ♘♔R♗!` no controle `photo` e +15 inventados no fax; o ♔ 0/13 é da
rodada **`caissa_por`** (29 linhas de ♔) — o `caissa_eng` e o modelo por livro do SFC4 (40
linhas de ♔) **não têm placar por peça publicado**. Controles: `caissa/ocr/controls.py` (6
tipos; 12 itens no manifesto). `lstmtraining` aceita lista de treino com repetição. `Medir no
livro…` = `ocr/labeling/measure.py` (por partição). Receita por livro: `caissa-treinar --project
labeling --document "<stem do SFC4>" --book --base-lang eng --base-model
models/tessdata_best/eng.traineddata --iterations 12000` (~16 min), saída em
`models/tessdata/livros/<slug>/` — **não** em `models/tessdata/caissa_eng.traineddata`, que é
o global de 2026-09-13 e é o que `bench_sol.py --model-prefix caissa` lê.

**Tarefas.**
0. Medir o placar por peça do modelo por livro atual (`Medir no livro…` já separa figurinas
   certas; acrescentar a contagem por peça ao relatório) — é o "antes".
1. `FineTuneConfig.negatives: int` — linhas dos controles e recortes de prosa **sem** figurina
   do próprio livro, com verdade vazia/prosa; entram na lista de treino.
2. `FineTuneConfig.oversample_rare: float` — linhas com classe cuja contagem < mediana
   repetidas até a mediana.
3. Opcional se 2 não bastar: `synth_lines` — colar recortes reais de figurina (das linhas
   aceitas) em linhas de prosa do mesmo livro; verdade por construção.
4. `DialogoDeTreino` (`ui/views/rotulagem.py`) expõe as duas caixas.
5. Retreinar o SFC4 e remedir por partição.

**Verificação.**
```
PY -m pytest tests\unit\ocr\test_training.py -q
PY benchmarks\bench_sol.py --system sol --tessdata-dir models\tessdata\livros\<slug> --label sfc4_neg --publish --compare docs\quality\sol\baseline.json
```
(mais «Medir no livro…» da aba, ou `caissa.ocr.labeling.measure.measure_book` pela linha de comando.)

**Portão e sabotagem.** Controle `photo` sem figurina emitida; `synth/fax_dither` inventados
≤ baseline; cada peça na avaliação (`calib`) ≥ o "antes" e a mais rara ≥ 75 %; lances no
livro ≥ o "antes" (94 % no §7c). *Sabotagem:* `negatives=0` — o controle `photo` volta a
emitir figurina e o portão SOL-2 acusa.

**Saída.** `ROTULAGEM.md` §4d e `OCR_UI_REPORT_C1.md` §7. **Desfazer:** as duas opções em 0.

**Executado em 2026-09-14** (§4): negativos **com margens só de textura** (sem elas o `photo`
ainda emitia `De ♕a1`); `photo` sem figurina ✓, cada peça ≥ antes ✓ (modelo sozinho 204/204),
lances no livro ≥ antes ✓, sabotagem vista ✓; **fax inventados 126 > 76 da base ✗** (era 206) —
fica vermelho e registrado: o modelo do livro segue candidato secundário fora do seu livro.

---

### Passo 4b — O modelo do livro como âncora dentro do próprio livro

**Objetivo.** Dentro do livro registrado para ele, o modelo por livro ancora; fora, nada muda.

**Briefing (achado do passo 4, `ROTULAGEM.md` §4d).** O modelo do SFC4 sozinho lê **204/204**
figurinas e 282/288 lances da avaliação `calib`; o caminho do produto no mesmo livro —
Tesseract `eng` na âncora + leitor de glifos + o modelo como candidato secundário
(`figurine_candidates`, "never the anchor") — lê 193/204 e 273/288. A fusão perde 11
figurinas e 10 lances que o modelo já tinha, porque a regra SOL-6 só troca tokens que não são
palavra nem lance e nunca insere. A regra "nunca âncora" existe porque o modelo inventa em
ruído (fax 126 vs 76); dentro do livro para o qual foi treinado e registrado por impressão
digital (`livros.json`), esse risco é o do próprio livro — e é medido pelo `Medir no livro…`.

**Tarefas.**
1. `OcrServiceConfig.book_model_anchors: bool` (padrão ligado): quando `figurine_tessdata`
   é a pasta de um livro registrado para o PDF em importação, o `PageRecognizer` do idioma do
   livro usa `caissa_<lang>` como **modelo do motor âncora** (o `eng` base vira candidato).
   Fora do livro (sem registro), tudo como hoje.
2. Guardas que ficam: leitor de glifos e cifra como candidatos; controles nunca veem o modelo
   (não há registro para eles).
3. `Medir no livro…` ganha o terceiro lado "modelo na âncora".

**Verificação.**
```
PY -m pytest tests\unit\ingest\test_ocr_service.py tests\unit\ocr\test_measure.py -q
PY benchmarks\bench_sol.py --system sol --label c1_anchor --publish --compare docs\quality\sol\c1_rapidocr.json
```
(mais `Medir no livro…` no SFC4 com os três lados.)

**Portão e sabotagem.** No SFC4, `calib`, caminho do produto: figurinas ≥ 200/204 e lances
≥ 280/288 (hoje 193 e 273); `bench_sol` sem regressão fora do IC em estrato algum e controles
0 → 0 (o modelo não entra neles). *Sabotagem:* registrar o modelo do SFC4 para **outro** PDF
(Levenfis) e medir: o portão de controles/inventados tem de acusar — prova que o isolamento
por livro é o que segura o risco.

**Saída.** `ROTULAGEM.md` §7h; `OCR_UI_REPORT_C1.md` §8. **Desfazer:** `book_model_anchors=False`.

**Executado em 2026-09-14** (§4): figurinas 204/204, lances 281/288 na `calib` ✓; sabotagem de
registro cruzado: 519 figurinas inventadas em 6 páginas ✓ (vista); `bench_sol` idêntica ✓.

---

### Passo 5 — Fila de rotulagem por valor de rótulo

**Objetivo.** A aba Rotulagem diz qual página abrir a seguir para que cada rótulo humano
valha mais.

**Briefing.** 13 páginas rotuladas de 200 (12 SFC4 + 1 *Modern Endgame Manual*); a única
página cronometrada levou 07:58 com 86 de 87 linhas aceitas em bloco (amostra de um). A
decisão por linha (`REVIEW`/`ABSTAINED`, palavras fracas, candidatos discordantes) sai do
`OcrService.recognize_image` que a bancada usa (`ocr/labeling/recognise.py`). O manifesto
privado (`GOLD`) carrega estrato e idioma por item (`ocr/golden.py`); a partição é função do
id (`partition_for`), então a fila **pode** saber que uma região cairia na cega e não a
priorizar (ela não treina).

**Tarefas.**
1. `ocr/labeling/queue.py`: pontua páginas de um PDF (amostra espaçada, como `bench_ingest
   --sample`) por linhas `REVIEW` esperadas, livro sem rótulo, estrato/idioma vazio no
   manifesto, regiões `MOVETEXT` sem `start_fen`.
2. Botão «Próxima que vale» na aba (Qt e Tk) e `caissa-rotular --sugerir`.
3. O reconhecimento da pontuação roda em thread, cancelável (R3.5).
4. `benchmarks/labeling_queue.py` (novo): mede, em 3 PDFs, linhas `REVIEW` nas 5 primeiras
   páginas da fila contra a mediana das páginas amostradas; `--sabotar constante`.

**Verificação.**
```
PY -m pytest tests\unit\ocr\test_labeling.py -q
PYQ-UI -m pytest tests\unit\ui\test_rotulagem_view.py -q
PY benchmarks\labeling_queue.py --pdfs 3
PY benchmarks\labeling_queue.py --pdfs 3 --sabotar constante     # tem de reprovar
```

**Portão e sabotagem.** ~~As 5 primeiras da fila têm ≥ 2× as linhas `REVIEW` da mediana em
cada um dos 3 PDFs.~~ **Reescrito na execução** (§4, 2026-09-14): nos scans o serviço manda
todas as linhas para revisão e a razão do próprio oráculo é 1,1–1,3 — barra inatingível. O
portão é a **captura do oráculo**: as linhas `REVIEW` do top-5 da fila ≥ 0,90 das do top-5
ordenado pelas linhas de fato, em cada um dos 3 PDFs; a razão do roadmap continua impressa ao
lado do seu teto. *Sabotagem:* pontuação constante — a ordem vira a sequencial e a captura cai
(medido 0,47–0,60).

**Saída.** `ROTULAGEM.md` §8; `OCR_UI_REPORT_C1.md` §6. **Desfazer:** o botão some.

---

### Passo 6 — Léxico russo e lances como palavras em `MOVETEXT`

**Objetivo.** Um `ru_RU` licenciado no léxico; o veredito do nível 0 deixa de rejeitar páginas
de soluções por "impronunciáveis".

**Briefing.** `caissa/ocr/hunspell.py` aplica afixos em sentido inverso; `tools/build_lexicon.py`
empacota com `MANIFEST.json`. Russo hoje só com lista autoral e bigramas (`SOL_REPORT.md` §4,
SOL-9). Yusupov p. 701 rejeitada pelo nível 0 com "55 % impronunciáveis" numa página 90 %
notação (`F2_REPORT.md` §4, pendência 5). No veredito (`ocr/engines/pdf_text_layer.py`), o
`nonword_ratio` ("impronunciáveis") e o `mangled_move_ratio` são **ramos independentes**; o
0,55 do Gaprindashvili vem do `mangled` e não muda com o `nonword`. O veredito por região já
distingue `MOVETEXT`. Testes: `tests/unit/ocr/test_text_layer.py`,
`tests/unit/ocr/test_lexicon_package.py`.

**Tarefas.**
1. Localizar um `ru_RU.dic/.aff` com licença auditável (LibreOffice/AOT — conferir); se não
   houver, registrar e parar esta metade.
2. No `nonword_ratio`, em regiões `MOVETEXT`, token que é lance válido conta como palavra.
3. Teste de corpus: Yusupov p. 701 aceita; Polgar continua aceito; os livros acusados
   continuam a 0,55 (o `mangled` não muda).

**Verificação.**
```
PY -m pytest tests\unit\ocr\test_text_layer.py tests\unit\ocr\test_lexicon_package.py -q
PY benchmarks\notation_integrity.py --what verdicts
```

**Portão e sabotagem.** Yusupov p. 701 ≥ 0,82; nenhum livro acusado sobe. *Sabotagem:* contar
o token mangled (`'i'd6+`, `l:th`) como lance válido **no `mangled_move_ratio`** — o
Gaprindashvili p202 tem de voltar a 0,98 e o teste de corpus que fixa 0,55 tem de reprovar
(é o sinal certo; mexer no `nonword` não reprova nada, e por isso não serve de sabotagem).

**Saída.** `OCR_UI_REPORT_C1.md` §6. **Desfazer:** a regra do item 2 fora; o dicionário fica.

---

### Passo 7 — Lado a jogar pela numeração do lance seguinte

**Objetivo.** As duas cascatas de lado a jogar usam a numeração do primeiro lance sob o
diagrama e a legenda "após N.lance" antes de cair na legalidade e no padrão; a origem vai ao IR.

**Briefing.** Há **duas** cascatas. (a) Tronco: `semantics.py::infer_side_to_move(placement,
context)`, texto → legalidade → padrão, `SideSource` com dez valores; corre só na via raster
(`src/caissa/vision/classify/page.py`). (b) Suíte: `ingest/pdf/importer.py::_diagram_node`
aplica `_with_side` só quando `captions.DiagramContext.side_to_move` foi declarado pela
legenda; o contador `side_to_move` do relatório (109 de 911, `F2_REPORT.md` §4) conta isso. O
parágrafo de estilo `Movetext` sob o diagrama (`ingest/pdf/captions.py`,
`ocr/notation/movetext.py`) carrega a numeração (`22...` vs `23.`). Verdade: as regiões com
`start_fen` do passo 0 (o lado está na FEN). A F5 mediu que trocar o lado "não mudou nada" na
cadeia de então (§7.5) — o portão deste passo mede **a origem e o acerto do lado**, não os
lances.

**Tarefas.**
1. `captions.DiagramContext.first_move_number: tuple[int, bool] | None` (número, é_das_pretas)
   e `caption_after_move` ("após/after/nach/después/после N.x"), preenchidos pelo importador.
2. Regra `move_number` → `caption` entre texto e legalidade, nas duas cascatas; `SideSource`
   **estendido** com os dois valores (R2.5).
3. `Diagram.side_to_move_source` no IR (`caissa/core/model`); o relatório de importação conta
   por origem.
4. Portão: `benchmarks/side_to_move_gate.py` (novo) — sobre as regiões com `start_fen` do
   passo 0, compara o lado inferido com o da FEN; `--sabotar paridade`.

**Verificação.**
```
PYQ -m pytest tests -q -k semantics                (no tronco)
PY -m pytest tests\unit\ingest tests\unit\model -q
PY benchmarks\bench_ingest.py --sample 12 --raster
PY benchmarks\side_to_move_gate.py
PY benchmarks\side_to_move_gate.py --sabotar paridade     # tem de reprovar
```

**Portão e sabotagem.** Nas regiões com `start_fen` (n do passo 0): lado inferido = lado da
FEN em ≥ 90 %, com origem ≠ `default` em ≥ 80 %; no acervo (`--raster`), diagramas com origem
≠ `default` sobem de 109/911 para ≥ 500/911. *Sabotagem:* paridade invertida — o acerto cai
abaixo de 20 % e o portão reprova.

**Saída.** `OCR_UI_REPORT_C1.md` §7. **Desfazer:** as duas regras fora das cascatas.

---

### Passo 8 — Confiança por diagrama calibrada e discriminante

**Objetivo.** `DiagramConfidence` = p(tabuleiro exato), com ECE **e** discriminação
publicados, alimentando fila, âmbar e o portão de exportação.

**Briefing.** Por diagrama existem: `min_confidence` (casa menos confiante), top-k por casa
(`tools/f4_field_failures.py` mostra como obter), casas reparadas pelo decodificador com
restrições (`decode.py`), legalidade em três valores (`fen_utils.py`), regra de orientação
(`orientation.py` `.explain()`), via (`RecognitionPath`), estrato. **Propriedade documentada em
`decode.py`:** casa reparada ⇒ confiança ≤ 0,5 ⇒ `min_confidence ≤ 0,5` ⇒ nunca passa
`ACCEPT_MIN_CONFIDENCE = 0,80` (`config.py:47`, aplicado em `batch.py` e `field_eval.py`) —
"reparado" é hoje um veto, não um sinal. A temperatura por casa foi rejeitada (`ASSETS.md`
§2.14: ECE por casa 0,000265 → 0,000837 e fila dobrada) — **não** é isto. Conjunto de campo:
`ChessVisionOFF_Puro/data/field_set.jsonl` — **114 casados** (94 exportados, 93 exatos), régua
corrigida por `benchmarks/field_corrections.json`; laboratório: split de 534 (identidade de
livro no split: **não verificada** — se não houver, validar só por estrato). **Armadilha:** com
93/94 exatos um preditor constante p = 0,989 tem ECE ≈ 0,01 e embaralhar rótulos não reprova;
por isso o portão mede discriminação sobre os 114 (os 20 barrados têm exatidão conhecida).

**Tarefas.**
1. `caissa/vision/classify/confidence.py`: extrator de sinais + modelo raso (logística ou
   árvore de profundidade ≤ 3), validado por livro no campo (e por estrato no laboratório).
2. `benchmarks/diagram_confidence_gate.py` (novo): AUROC contra o preditor constante, ECE,
   Brier, curva risco × cobertura por estrato sobre os 114; `--sabotar ruido` substitui os
   sinais por ruído.
3. O nó `Diagram` ganha `confidence` (R2.7); a fila da aba Revisão ordena por ele; o painel
   Resultado pinta âmbar por margem de casa e mostra `confidence` do tabuleiro.
4. Publicar sempre com `field_exact`, `export_rate`, `conditional_exact` (R1.3).

**Verificação.**
```
PY benchmarks\diagram_confidence_gate.py --runs 3
PY benchmarks\diagram_confidence_gate.py --runs 3 --sabotar ruido      # tem de reprovar
PY benchmarks\field_exact.py --runs 3
```

**Portão e sabotagem.** AUROC ≥ 0,90 sobre os 114 casados (validação por livro); ECE ≤ 0,03;
a 95 % de cobertura, exatidão condicional ≥ a de hoje. *Sabotagem:* sinais substituídos por
ruído → AUROC ≈ 0,5 e o portão reprova (o ECE sozinho não reprovaria — é por isso que o
portão não é só ECE).

**Saída.** `OCR_UI_REPORT_C1.md` §8; `docs/quality/diagram_confidence.md`. **Desfazer:** a
fila volta a `min_confidence`.

---

### Passo 9 — Rendimento dos diagramas barrados na exportação

**Objetivo.** Os 20 diagramas casados e barrados (11 hachurados, 9 scan-puro) chegam ao PGN
quando estão certos — sem baixar o piso.

**Briefing.** `F4_FIELD_REPORT.md` §2.1: `scan-hachurado` 21/21/10 exportados, `scan-puro`
45/44/35. Portão: `ACCEPT_MIN_CONFIDENCE = 0,80` (`config.py:47`; `batch.py`, `field_eval.py`).
Causa estrutural conhecida: reparo ⇒ ≤ 0,5 (`decode.py`; "a mudança é no gate").
`tools/f4_field_failures.py` grava só predições **erradas** (docstring) — precisa de
`--barrados` (novo). Gerador: `caissa/vision/train/synthgen.py` (`SynthConfig`) **não tem
degradação de digitalização** (só warp, matiz, texto, inversão, deslocamento, temas; os temas
do TSOJ incluem um hachurado, `newspaper`). `lab_gate.py` reprova candidato que custe acurácia
por casa ou legalidade. Depende do passo 8.

**Tarefas.**
1. Diagnóstico: `f4_field_failures.py --barrados` — para cada um dos 20: certo/errado pela
   anotação e motivo do bloqueio (reparo, casa fraca sem reparo, erro real). Tabela no relatório.
2. Reparos certos e casas certas de confiança baixa: o portão passa a decidir por
   `DiagramConfidence`, por estrato, no ponto da curva risco × cobertura que mantém
   `conditional_exact`.
3. Erros reais de textura: degradações de digitalização no gerador; fine-tune **só da cabeça**
   (hipótese (a) do `F4_FIELD_REPORT.md` §8.2) sob `lab_gate.py`.
4. Relatório com os três números de campo lado a lado, por estrato e por livro.

**Verificação.**
```
PY tools\f4_field_failures.py --barrados --out benchmarks\reports\f4_barrados
PY benchmarks\field_exact.py --runs 3
PY benchmarks\lab_gate.py --runs 3
```

**Portão e sabotagem.** `export_rate` ≥ 0,85 no hachurado (era 0,476) e ≥ 0,90 no scan-puro
(era 0,795), com `conditional_exact` = 1,0 nos dois e `field_exact` ≥ 0,98 na régua
corrigida; laboratório sem regressão. *Sabotagem (independente do diagnóstico):* trocar a
anotação de 3 dos 20 barrados por uma FEN errada — o `conditional_exact` tem de cair e o
portão reprovar, prove-se o que se provar sobre os 20 reais.

**Saída.** `OCR_UI_REPORT_C1.md` §9. **Desfazer:** o portão volta a `min_confidence`.

---

### Passo 10 — Fallback para glifo vetorial fora do catálogo

**Objetivo.** Um diagrama ou figurina em fonte de xadrez desconhecida não vira letra crua:
o glifo é renderizado e lido pelo classificador, com proveniência `inferred`.

**Briefing.** Via A: `caissa/vision/detect/font_catalog.py` (`FAMILIES`: 37 — 29 verificadas,
7 não verificadas, `skak_diagram` inferida a 0,85) e `vector_detect.py`. Modo de falha real:
`2.♘xd4` → `2.l0xd4` (`ROADMAP.md`). Leitor de glifos: `caissa/ocr/engines/glyph.py` (314
classes, tronco `models/char_classifier.pt`); classificador de casas: `vision/classify`.
`RecognitionPath` em `caissa/core/model`. `benchmarks/vector_survey.py` lista as fontes do
acervo.

**Tarefas.**
1. Fonte desconhecida com glifos em grade 8×8 → renderizar cada casa e classificar;
   `RecognitionPath.VECTOR_INFERRED`, confiança ≤ 0,85, nota no relatório.
2. Figurina inline em fonte desconhecida → renderizar o glifo e pedir ao leitor de glifos;
   `PieceGlyph` com `inferred=True`.
3. Um segundo livro em `SkakNew` (o survey diz se há) para subir o catálogo a `verified`.

**Verificação.**
```
PY -m pytest tests\unit\detect tests\unit\ingest -q
PY benchmarks\vector_survey.py
```

**Portão e sabotagem.** Nas páginas do acervo com fonte fora do catálogo (o survey lista),
diagramas lidos > 0 com confiança ≤ 0,85; nos livros catalogados, **nada muda** (mesmo FEN,
mesma via). *Sabotagem:* remover `Merida` do catálogo — o DEM tem de cair para
`VECTOR_INFERRED` e o teste que fixa a via `VECTOR` a 1,0 tem de reprovar.

**Saída.** `OCR_UI_REPORT_C1.md` §9. **Desfazer:** o fallback atrás de opção desligada.

**Executado em 2026-09-14** (§4): população zero no acervo (survey: 0/46 com fonte fora do
catálogo); tarefa 1 construída e medida pela sabotagem (Merida/SkakNew escondidas: 35/35 e
114/114 iguais à leitura do produto, ≤ 0,85); tarefas 2 e 3 sem população. Achado: a via
exata publicava 61/114 posições erradas do Polgar (torres em casa escura omitidas pelo
extrator, tomadas por vazias) — corrigido: casa ausente ⇒ ≤ 0,60 e `holes`; o classificador
completa (`fill_holes`, `VECTOR_INFERRED`).

---

### Passo 11 — Parágrafo `Movetext` → `GameScore`

**Objetivo.** Um trecho de lances com posição de partida vira partida legal encadeada no IR,
com proveniência por lance; o produto exporta PGN de livro digitalizado.

**Briefing.** Pendência 3 da F2. A cadeia diagrama → FEN → OCR → cifra → tronco da análise →
legalidade tira 12 lances legais de 18 em 6 páginas do Nunn (`F5_REPORT_C2.md` §7). No IR
**não existe classe `Movetext`**: é `Paragraph` com `ParagraphStyle(name="Movetext")`
(`ingest/pdf/importer.py`) sobre `RegionKind.MOVETEXT` (`ingest/pdf/paragraphs.py`), com
`PieceGlyph` e texto. `ocr/notation/movetext.py` acha o tronco da análise ("o tronco se emenda
por cima da variante"); `ocr/notation/validate.py` faz o replay legal (SOL-8). O analisador
tolerante **não** é do tronco ChessVision: veio do `PGN_Live_Editor` e está em
`src/caissa/notation/` (`parser.py`, `book_import.py`, `variation_builder.py`,
`pipeline.build_games_for_export`) — nada em `ingest/` o chama; `games.py` **não** reescreve
`book_import`, compõe-no. `GameScore` em `caissa/core/model/game.py`; variantes são
`MoveNode.children[1:]` (não há `Variation`). Depende dos passos 0 (verdade), 3 (tokens) e 7
(lado). A F5 mediu que trocar o lado "não mudou nada" (§7.5) — por isso a sabotagem daqui
**não** é o lado.

**Tarefas.**
1. `caissa/ingest/pdf/games.py`: para cada parágrafo `Movetext` com posição de partida (FEN
   do diagrama anterior + lado, ou `start_fen` da região) → tokens → `caissa.notation.parser`/
   `book_import` → replay legal → `GameScore` com um `Move` por lance, cada um com
   proveniência do span (motor, confiança, revisão, `cipher_evidence`).
2. Sem posição de partida: o parágrafo fica como está (R2.4).
3. Variantes: só o tronco é obrigatório encadear; variantes entram como filhos quando legais
   a partir do lance pai, senão ficam como texto com motivo.
4. `benchmarks/games_gate.py` (novo): lances legais encadeados por página nas 6 páginas do
   Nunn e nas regiões com `start_fen` do SFC4; `--sabotar fen` troca a posição de partida por
   outra posição legal do mesmo livro.
5. Exportadores: `GameScore` já sai em DOCX/EPUB/HTML/LaTeX e PGN (F8) — conferir a
   fidelidade do corpus.

**Verificação.**
```
PY -m pytest tests\unit\ingest tests\unit\notation tests\unit\export -q
PY benchmarks\games_gate.py --runs 3
PY benchmarks\games_gate.py --runs 3 --sabotar fen        # tem de reprovar
```

**Portão e sabotagem.** Nunn (6 páginas): ≥ 16 de 18 lances legais encadeados (eram 12);
SFC4 (regiões com `start_fen`, partição `calib`): ≥ 90 % dos lances rotulados na partida; 0
lances que não estão na página. *Sabotagem:* FEN de partida trocada — o encadeamento tem de
cair abaixo de 30 % (um lance legal por acaso não sustenta uma sequência).

**Saída.** `OCR_UI_REPORT_C2.md` §1. **Desfazer:** `games.py` fora do importador; o
parágrafo permanece.

---

### Passo 12 — Fita: portões próprios, rótulos, títulos e ícones

**Objetivo.** Os três itens abertos desde o F9-C15 fecham **com portão**: rótulo desenhado em
todo botão, título de grupo em toda densidade, tinta dos ícones ≥ 50 %.

**Briefing.** A pele **Fita** (`ui/pele.py`, S-227) é a `imagem_2.png`; os **sete grupos**
(`ui/comandos.py` `GRUPOS`: Arquivo, Edição, Visualização, OCR, Acervo, Estudo, Ajuda) foram
derivados dela com decisão registrada (corte OCR/Acervo) — **mantêm-se**. Tronco: `qt/fita.py`,
`ui/medidas_da_fita.py` (regra da fita, não um portão), `qt/icones.py`, `ui/icones.py`. Os
números abertos (`F9_REPORT_C16.md` §12) — 6 de 24 sem rótulo, 0 de 5 cabeçalhos na compacta,
tinta 17,6–41,4 % — vieram de scripts avulsos `benchmarks/reports/ui/c12/c12_fita.py` e
`c12_icones_da_janela.py`; o `texto_pintado` mede fonte × recorte e **passa hoje** com os seis
sem rótulo, então não serve de portão para isto. Regras de detalhe: hit ≥ 40 px (44 ideal),
ícone opticamente centrado, animação só nas propriedades que mudam. **R3.4:** dica de
ferramenta não é rótulo.

**Tarefas.**
1. Promover os dois scripts a `caissa.ui.audit.fita` e `caissa.ui.audit.icones` (novos), com
   `--saida`, `--pdf`, e sabotagem embutida (`--sabotar rotulo_na_dica`, `--sabotar tinta`).
2. Regra em `ui/medidas_da_fita.py`: todo botão tem rótulo; título de grupo obrigatório em
   toda densidade; hit ≥ 40 px.
3. Ícones: redesenhar os de tinta < 50 % (24 px, traço 2 px).
4. Retratos antes/depois por pele × densidade (`AUDIT.capture --marca c17 --saida …`).

**Verificação.**
```
AUDIT.fita --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.fita --pdf "%PDF%" --saida benchmarks\reports\ui\c17 --sabotar rotulo_na_dica    # tem de reprovar
AUDIT.icones --saida benchmarks\reports\ui\c17
AUDIT.texto_pintado --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.contraste --saida benchmarks\reports\ui\c17
AUDIT.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.comandos --pdf "%PDF%" --saida benchmarks\reports\ui\c17
PYQ -m pytest tests -q -p no:randomly -p no:cacheprovider     (tronco)
```

**Portão e sabotagem.** 24/24 botões com rótulo desenhado; 5/5 cabeçalhos na compacta; tinta
≥ 50 % em todos os ícones; contraste 100 % dos pares nas 3 peles; teclado 0/0/0. *Sabotagem:*
`--sabotar rotulo_na_dica` move um rótulo para `toolTip()` — `AUDIT.fita` tem de acusar 1
(o `texto_pintado`, não).

**Saída.** `OCR_UI_REPORT_C2.md` §2. **Desfazer:** os ícones antigos ficam em `git`.

---

### Passo 13 — Editor de posição com o recorte e sobreposição numerada

**Objetivo.** Na aba Resultado, o recorte do diagrama ampliado ao lado do tabuleiro, casa sob
o ponteiro espelhada nos dois, top-3 na dica, âmbar por margem por padrão; na página, caixas
numeradas com estado.

**Briefing.** Tronco: `qt/painel_de_resultado.py` (1.145 linhas), `qt/tabuleiro_editavel.py`,
`qt/visor.py` (API pública: `pagina_escalada`, sinais de clique — o passo 15 a mantém),
`qt/marcas.py`. Hoje o lado direito é a página inteira (`F12_janela_do_bundle.png`); "Mapa de
incerteza" é uma caixa de marcar. Dados: recorte retificado e top-k por casa saem do
reconhecimento (`tools/f4_field_failures.py` mostra como). SPEC §10.4; proposta
`Imagem_1.png`. Depende do passo 8 para o âmbar significar p(exato). Regra em `ui/`, pintura
em `qt/` (R3.2). Detalhe: contorno neutro 1 px no recorte; números tabulares nos contadores.
**Não há instrumento que conte ações do usuário** (`ui/audit/execucao` mede threads de fundo)
— este passo cria um. O `bloqueio` está reprovado hoje (Q6): este passo não pode **aumentar**
o número de operações > 16 ms nem a mediana de abrir PDF.

**Tarefas.**
1. `ui/recorte_do_diagrama.py` (regra: casa ↔ pixel do recorte, top-3, margem) e
   `qt/painel_de_recorte.py` (pintura), ao lado do tabuleiro num `QSplitter`.
2. Sincronia: hover/seleção espelha; clique no recorte seleciona a casa no tabuleiro.
3. Âmbar por margem ligado por padrão; a caixa vira "esconder incerteza".
4. Caixas na página: número, cor por estado (lido / duvidoso / corrigido), clique abre.
5. Vazio desenhado quando não há diagrama.
6. `caissa.ui.audit.percurso` (novo): reproduz um percurso declarado (abrir página com
   diagrama de campo errado → selecionar casa → peça → aplicar) e conta ações;
   `--sabotar sem_sincronia`.

**Verificação.**
```
AUDIT.percurso --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.percurso --pdf "%PDF%" --saida benchmarks\reports\ui\c17 --sabotar sem_sincronia    # tem de reprovar
AUDIT.quadros --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.contraste --saida benchmarks\reports\ui\c17
```

**Portão e sabotagem.** Corrigir uma casa errada leva ≤ 3 ações sem zoom na página; fps
≥ 55 @ p95; `bloqueio` com **≤ 7** operações e abrir PDF ≤ 214,5 ms (não piora; quem fecha é o
15); teclado alcança o recorte. *Sabotagem:* sincronia desligada — o percurso precisa de uma
ação a mais e `AUDIT.percurso` reprova.

**Saída.** `OCR_UI_REPORT_C2.md` §3. **Desfazer:** o painel de recorte atrás de opção.

---

### Passo 14 — Janela de revisão de texto (SOL-11)

**Objetivo.** No produto, uma vista que mostra só os spans `REVIEW`/`ABSTAINED` do documento
importado, com recorte, leitura, alternativas e motivo; aceitar / editar / manter como
imagem grava no IR e nas correções.

**Briefing.** Modelo pronto: `caissa/ocr/review.py` (`ReviewQueue`, `corrections()`,
`blind_guard`). Widgets prontos: `caissa/ui/views/rotulagem.py` (`PainelDeRotulagem` —
recorte, leitura com palavras fracas, alternativas, verdade com paleta de figurinas; helpers
em `ocr/labeling/helpers.py`). A aba de rotulagem é bancada de verdade; esta é revisão de
produto (`ROTULAGEM.md` §7d). O IR carrega `verified_by_human` e o relatório `review_items`
(SOL-10). Depois do passo 8, diagramas com `confidence` baixo entram na mesma fila. Critérios
SOL-11: o revisor corrige só spans duvidosos; toda decisão auditável; tempo por página medido.
Q6 vale aqui também (não piorar o `bloqueio`).

**Tarefas.**
1. `caissa/ui/views/revisao_de_texto.py`: `PainelDeRevisaoDeTexto` compondo os widgets da
   rotulagem sobre `ReviewQueue`; três ações; navegação por duvidoso (Enter = aceitar e próximo).
2. Decisão → IR (`verified_by_human`, texto) → `corrections.json`; nunca em `blind`.
3. Montar como aba no tronco (`qt/painel_de_revisao_de_texto.py`, guarda como a Rotulagem)
   ou como modo da aba Revisão — decisão do construtor, registrada.
4. Exportação avisa quantos duvidosos restam.

**Verificação.**
```
PYQ-UI -m pytest tests\unit\ui\test_revisao_de_texto_view.py -q
PY -m pytest tests\unit\ocr\test_review.py -q
AUDIT.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c17
AUDIT.contraste --saida benchmarks\reports\ui\c17
AUDIT.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17
```

**Portão e sabotagem.** Num livro importado com N spans em revisão, o revisor visita **N e
só N** (auditoria conta); uma correção numa região `blind` é recusada com frase; tempo por
página gravado. *Sabotagem:* `blind_guard` desligado — o teste que corrige uma região cega
tem de acusar a gravação.

**Saída.** `OCR_UI_REPORT_C2.md` §4. **Desfazer:** a aba/modo some; `ReviewQueue` fica.

---

### Passo 15 — Visor por ladrilhos

**Objetivo.** Pan/zoom com folga a 300 DPI e 4K; nada > 16 ms na thread de UI ao abrir e ao
mudar de página; o `bloqueio` passa.

**Briefing.** `qt/visor.py`: `VisorDePagina(QScrollArea)` com `_pagina`/`_escalada: QPixmap`
(página inteira reescalada). Medido: zoom 59 fps mediana, uma invocação a 54
(`F9_REPORT.md` D19, **2026-09-07**, ciclo 1 — `quadros` não foi rerodado no C16: **remedir
antes**); 7 operações > 16 ms e abrir PDF 214,5 ms (`F9_REPORT_C16.md` §12, portão
`bloqueio` **reprovado**). Render: `caissa/ingest/pdf/render.py` (cache LRU com orçamento de
memória, F2). ADR-0001 aponta `QGraphicsView` com cache de ladrilhos. Sobreposições (caixas,
marcas) moram sobre o visor — manter a API pública para o passo 13.

**Tarefas.**
0. Remedir `quadros` (3×) e `bloqueio` no estado atual — o "antes" com data.
1. `qt/visor_ladrilhado.py`: `QGraphicsView`; ladrilhos de 512 px por nível de zoom,
   renderizados em worker (`QThreadPool`) na resolução alvo, LRU por página × nível.
2. Abrir PDF e mudar de página: I/O e primeira renderização fora da thread; a UI mostra a
   página anterior/placeholder em < 16 ms.
3. Mesma API pública do `VisorDePagina`; troca atrás de uma bandeira até os portões passarem.

**Verificação.**
```
AUDIT.quadros --pdf "%PDF%" --saida benchmarks\reports\ui\c17     # 3x
AUDIT.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17
```

**Portão e sabotagem.** Zoom ≥ 70 fps @ p95; pan mantém; **0** operações > 16 ms; abrir PDF
≤ 16 ms na thread de UI — o `bloqueio` passa pela primeira vez. *Sabotagem:* renderizar o
ladrilho na thread de UI — `bloqueio` tem de acusar.

**Saída.** `OCR_UI_REPORT_C2.md` §5. **Desfazer:** a bandeira volta ao visor antigo.

---

### Passo 16 — Foco como padrão e polimento (Q3)

**Objetivo.** A pele Foco (escura, S-224 = `Imagem_1.png`) vira o padrão de fábrica com
tokens projetados; polimento de detalhe nas três peles; contraste e teclado verdes.

**Briefing.** `ui/pele.py`: `PELES = (Clássica [padrão], Foco [escura, cromo_escuro=True],
Fita [compacta])`; folhas em `qt/tema.py`; `ui/folha_de_estilo.py` (`QUEM_PINTA`),
`ui/estilos.py`. Conferir em `qt/tema.py` se o cromo da Foco é **derivado** da clara ou
**desenhado** — a SPEC §10.2 exige projetado. Portões: `contraste` (compõe alfa — portão cego
5), `texto_pintado`, `teclado`; capturas `capture`. Regras: raio concêntrico, `tabular-nums`
em contadores e rodapé, hit ≥ 40 px, foco visível, contorno neutro em imagens, vazio desenhado
("vazio a 4K 5 de 6 > 200 kpx", aberto no C16). R3.6: as três peles ficam em *Ver ▸ Aparência*.
Depende do passo 12. **Sete abas** (`ui/abas.py`) e 13 diálogos nos retratos.

**Tarefas.**
1. Tokens da Foco em `ui/estilos.py`; folha em `qt/tema.py`; padrão de fábrica = Foco.
2. Polimento nas três peles: contadores tabulares (`p. 1 de 308`, `59 %`, rodapé), raio,
   foco, contorno de recorte/página, vazio desenhado.
3. Retratos das sete abas + 13 diálogos, três peles × duas densidades; crítico visual às
   cegas contra Affinity/Chessbase (SPEC §11.4).

**Verificação.**
```
AUDIT.contraste --saida benchmarks\reports\ui\c18
AUDIT.texto_pintado --pdf "%PDF%" --saida benchmarks\reports\ui\c18
AUDIT.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c18
AUDIT.amostrario --saida benchmarks\reports\ui\c18 --estados
```

**Portão e sabotagem.** Contraste 100 % dos pares nas três peles; vazio a 4K ≤ 200 kpx em
6/6 painéis; crítico visual não identifica a nossa como pior. *Sabotagem:* um par a 3,9:1 na
folha da Foco — `contraste` tem de acusar 1.

**Saída.** `OCR_UI_REPORT_C3.md` §1. **Desfazer:** padrão de fábrica volta à Clássica.

---

### Passo 17 — O livro como unidade (trilho de páginas) — atrás de Q4

**Objetivo.** Um trilho de miniaturas com estado por página (diagramas / texto / revisado),
progresso real e cancelável da importação, e Exportar — o fluxo principal sem trocar de aba.

**Briefing.** F2 importa em streaming (`caissa/ingest/pdf/importer.py`, `document.py`);
exportação em thread com tranca (`qt/exportador_de_livro.py`, `caissa/export/book.py`);
revisão de diagramas (`qt/painel_de_revisao.py`) e de texto (passo 14); confiança por
diagrama (passo 8). Sete abas hoje (`ui/abas.py`). Muda a forma da janela medida em 16 ciclos
— **só com Q4 respondida**; reroda os cinco portões da F9 e o `comandos`. R3.5: progresso
real, cancelável, resultado parcial aproveitável.

**Tarefas.**
1. `ui/trilho.py` (regra: estado por página a partir do IR e das filas) + `qt/trilho.py`.
2. Importação do livro como tarefa com progresso por página, cancelável, IR parcial usável.
3. Abas de acervo (Dataset, Galeria, Rotulagem) continuam; as de diagrama (Resultado,
   Estudo, Revisão, Texto) passam a modos do painel principal.
4. Ramo próprio; os portões todos; crítico.

**Verificação.** Todos os comandos dos passos 12–16, mais:
```
AUDIT.comandos --pdf "%PDF%" --saida benchmarks\reports\ui\c19
AUDIT.percurso --pdf "%PDF%" --saida benchmarks\reports\ui\c19
```

**Portão e sabotagem.** Abrir livro → ver primeiro diagrama duvidoso → corrigir → exportar
em ≤ 6 ações (`AUDIT.percurso`); cancelar a importação a 30 % devolve IR com 30 % das
páginas; nenhum comando promete o que não faz. *Sabotagem:* cancelamento que descarta o
parcial — o teste de importação tem de acusar IR vazio.

**Saída.** `OCR_UI_REPORT_C3.md` §2. **Desfazer:** o ramo não se funde.

---

### Passo 18 (opcional, experimento) — Cor da peça fora da distribuição

**Objetivo.** Testar as duas hipóteses do `F4_FIELD_REPORT.md` §8.2 item 4 (cabeça só;
destilação) sob `lab_gate.py`; adotar só se o laboratório não regredir.

**Briefing.** Falha: `q→Q` em `extra/condal` (Burgess p. 60, casa e5); 48 ocorrências de
`q→Q` em 2.064 glifos de 86 conjuntos (`benchmarks/style_coverage.py --sets holdout`);
`tools/f4_finetune.py` + `caissa/vision/train/` fazem o fine-tune; o sintético completo
regrediu o laboratório e exportou 5 a menos (§6). Depende do passo 8.

**Portão.** `lab_gate.py --runs 3` verde; `style_coverage` sobe; `field_exact`,
`export_rate` e `conditional_exact` publicados juntos, nenhum pior. Se um regredir, o
experimento fica registrado e **não entra**.

---

## 3. Ciclos e relatórios

| ciclo | passos | relatório | crítico |
|---|---|---|---|
| C1 | 0; 1–10 (faixas A e B, paralelas) | `docs/quality/OCR_UI_REPORT_C1.md` | `OCR_UI_CRITIQUE_C1.md` — remedir 1, 2, 3, 8 do zero |
| C2 | 11, 12, 13, 14, 15 | `OCR_UI_REPORT_C2.md` | remedir 11 e os portões da F9 |
| C3 | 16, 17 (se Q4), 18 (se houver) | `OCR_UI_REPORT_C3.md` | crítico visual às cegas |

Regra dos relatórios: todo número com o comando ao lado; três números de campo juntos; os
estratos sempre; a sabotagem de cada portão executada e citada; todo passo tem linha "Saída".

---

## 4. Protocolo de mutação do plano

- **Dividir** um passo: o novo passo herda o briefing e ganha portão próprio; anotar aqui.
- **Inserir**: só com evidência (um número de relatório) de que falta algo; nunca por
  intuição.
- **Pular**: com a razão medida (ex.: passo 1 fecha 150 DPI e torna a super-resolução
  desnecessária).
- **Abandonar**: registrar em `OCR_UI_ANALISE.md` §6 como "medido e rejeitado" com o número.
- **Reordenar**: respeitando os arquivos partilhados do §1 (ex.: passo 3 depois do 11 se a
  contagem da tarefa 0 der < 20 lances provados).
- Toda mutação entra na tabela abaixo.

| data | passo | mutação | por quê | quem |
|---|---|---|---|---|
| 2026-09-14 | 0 | inserido | crítica: `start_fen` vazio em 256/256 regiões — os portões de 7 e 11 não tinham verdade | análise |
| 2026-09-14 | 8 | portão reescrito | crítica: com 93/94 exatos o ECE é cego; discriminação sobre os 114 casados | análise |
| 2026-09-14 | 16 | reescrito | crítica: a Foco já é a Imagem 1; não há pele nova | análise |
| 2026-09-14 | 10 | **executado, tarefas 2–3 sem população** — `OCR_UI_REPORT_C1.md` §9 | `detect_unknown_font_lattices` + `inferred_font_finder` (`VECTOR_INFERRED`, ≤ 0,85); survey: 0/46 livros com fonte fora do catálogo, medido pela sabotagem (famílias escondidas): DEM 35/35, Polgar 114/114. **Achado**: a via exata tomava casa ausente por vazia — Polgar 61/114 posições erradas (torres em casa escura omitidas pelo extrator); agora ≤ 0,60 + `holes`, e o `combined_finder` completa com o classificador | construtor |
| 2026-09-14 | 4b | **executado** — `OCR_UI_REPORT_C1.md` §8 | `TunedTesseractEngine` na âncora dentro do livro registrado: SFC4 `calib` figurinas 193 → 204/204, lances 273 → 281/288, inventados 9 → 5; sabotagem (modelo do SFC4 ancorando um livro de letras): 519 figurinas inventadas; `bench_sol` idêntica (o âncora não entra sem registro) | construtor |
| 2026-09-14 | 4 | **executado, um portão vermelho** — `OCR_UI_REPORT_C1.md` §7 | negativos com margens de textura + sobreamostragem: `photo` 0 figurinas (antes 57 caracteres de ruído; sabotagem `♖.♖♘♘`), fax inventados 206 → 126 mas **> 76 da base** (✗ registrado); no livro D ≥ A em tudo; modelo sozinho já lia 204/204 desde A (o ♔ 0/13 era da rodada `por`). 360 negativos piorou (146; uma semente por configuração). Modelo D registrado para o SFC4 | construtor |
| 2026-09-14 | 4b | **inserido** | achado: a fusão perde 11 figurinas e 10 lances que o modelo do livro sozinho lê (204/204 vs 193/204 na `calib`) porque ele nunca ancora; ancorar com ele **dentro do livro registrado** é a alavanca seguinte, com sabotagem de registro cruzado | construtor |
| 2026-09-14 | 5 | **executado** — `OCR_UI_REPORT_C1.md` §6 | «Próxima que vale» (Qt, Tk, `--sugerir`), `ocr/labeling/queue.py`; fila = ordem do oráculo nos 3 scans (captura 1,00), sabotagem 0,47–0,60. Limite registrado: nos scans antigos toda linha é `REVIEW`, a fila separa por volume; sem `MOVETEXT` na amostra | construtor |
| 2026-09-14 | 5 | **portão reescrito** | "top-5 ≥ 2× a mediana" executado como escrito: REPROVOU na rodada real (1,27/1,22/1,08) **e** na sabotagem (0,60/0,72/0,63) — o teto da razão (a do oráculo) é 1,1–1,3 nestes livros. Portão novo: captura do oráculo ≥ 0,90; a razão e o teto ficam impressos | construtor |
| 2026-09-14 | 6 | **executado** — `OCR_UI_REPORT_C1.md` §5 | `ru_RU` (BSD-3-Clause, Lebedev) no léxico: acerto de dicionário no Boleslávski 13–25 % → 48–73 %; um lance danificado deixa de contar como "impronunciável" — Yusupov p. 700–701 e Gaprindashvili p158 passam de rejeitadas a contestadas; vereditos dos 16 acusados e dos controles inalterados | construtor |
| 2026-09-14 | 8 | **bloqueado pela população** — `OCR_UI_REPORT_C1.md` §4 | instrumento e módulo construídos; o conjunto de campo tem 2 negativos em 96 diagramas com FEN — nem ajuste nem portão de discriminação são possíveis; a sabotagem é indistinguível da rodada real. Pesos não empacotados | construtor |
| 2026-09-14 | 0b | **inserido** (humano) | anotar a FEN dos 19 diagramas do conjunto de campo sem ela e acrescentar ≥ 30 diagramas **errados** (fila da aba Dataset por menor `min_confidence`); os passos 8, 9, 13 (âmbar) e 18 esperam por isto | análise |
| 2026-09-14 | 9 | **premissa corrigida** | os "20 barrados" do F4 eram 19 anotados sem FEN + 2 barrados (1 certo, 1 errado); o portão de exportação perde 1 diagrama certo em 96. O passo fica reduzido a "anotar e remedir"; nada de mexer no piso | construtor |
| 2026-09-14 | 3 | **executado** — `docs/quality/OCR_UI_REPORT_C1.md` §3 | tarefa 0 deu **zero** provas legais no acervo (soluções de exercícios sem a posição na página); a tabela aprende também das trocas do leitor de glifos (10 provas visuais, ≤ 2 % contradições) e de aglomerados da camada danificada. Peça certa no Gaprindashvili 791 → 891 (de 973), Nunn 320 → 346, Aagaard 133 → 140; controles intactos. Pré-requisito do passo 11 registrado: índice número → diagrama | construtor |
| 2026-09-14 | 2 | **executado** — `docs/quality/OCR_UI_REPORT_C1.md` §2 | a página mantida com notação danificada vai ao OCR; a camada ancora e os motores entram por token (medido: melhor que o vencedor na âncora nos dois eixos). Peça certa: Gaprindashvili 265 → 791, Aagaard 0 → 133, Nunn 0 → 320; 0 lances perdidos; controles com 0 caracteres alterados. Novo instrumento `notation_integrity.py --what contest` | construtor |
| 2026-09-14 | 1 | **executado** — `docs/quality/OCR_UI_REPORT_C1.md` §1 | RapidOCR 3.x (Apache-2.0) roteado às páginas degradadas: lances 0,819 → 0,893, inventados 291 → 169, nenhuma regressão fora do IC; o portão de CER fecha só no fax (os outros dois degradados caem dentro do IC); ✗ residual: inserções no estrato de sombra (verso espelhado). Quatro defeitos de fusão/âncora expostos e corrigidos. Surya não medido (Q1) | construtor |

---

## 5. Anti-padrões que este plano proíbe (catálogo)

1. Portão sem sabotagem executada (21 portões cegos com a suíte verde — `HANDOFF.md` §7).
2. Sabotagem que não toca o sinal que o portão mede (a do passo 6 na versão 1.0).
3. `field_exact` publicado sozinho.
4. Comprar limiar por olho até o motor ganhar (`HANDOFF.md` §4.1 sobre a calibração).
5. Alargar o alfabeto do corretor de cifra para recuperar recall.
6. Motor de teste falso como única evidência de que o real funciona (portões cegos 15–16;
   `test_optional_engines.py`).
7. Número medido fora do corpus de `CORPUS.md`; número de amostra única sem dizer que é.
8. `git add -A` neste checkout.
9. Rótulo em `toolTip()`.
10. Repetir uma alavanca do `OCR_UI_ANALISE.md` §6 sem uma hipótese nova nomeada.
11. Editar `field_set.jsonl` em vez de sobrepor por `field_corrections.json`.
12. Criar o que já existe: peles (Foco, Fita), grupos da fita, analisador de PGN
    (`caissa.notation`), `DiagramContext` (há dois — nomear qual).
