# OCR/UI · ciclo 2 — relatório do construtor (fase 4: o que nenhum portão media, e a evidência que faltava)

> **Data:** 2026-09-21 · **Plano:** `docs/OCR_UI_ROADMAP_C2.md` §3c (fase 4: C16, C12, A12, B11,
> B12, A13, C14, C15) · **Análise:** `docs/OCR_UI_ANALISE_C2.md` (§3.10, §4.9, §6.9, §10.6) ·
> **Fases anteriores:** `OCR_UI_REPORT_C2.md`, `OCR_UI_REPORT_C2_FASE2.md`,
> `OCR_UI_REPORT_C2_FASE3.md` · **Papel:** construtor. Todo número traz o comando ao lado.
> Ambiente: suíte `.venv` (Python 3.11.9, `torch 2.11.0+cu128`, RTX 5060), tronco
> `..\ChessVisionOFF_Puro` (3.10); Java 1.8.0_503; Stockfish 18 (a cópia do Sigil em
> `C:\Python-Chess2\Sigil-master\stockfish-windows-x86-64-avx2\stockfish\`, passada por `--motor`
> nos benchmarks e achada por `CVOFF_ENGINE_PATH`/`settings.engine.path` no produto). O treino do
> C16 correu na GPU em segundo plano durante a primeira metade da fase (13:07–14:02): os tempos
> (`s/diagrama`, `wall_s`) dessa janela carregam a contenção e são ditos com ela. Commits: tronco
> **40e2966**, suíte: o commit que traz este relatório (um em cada repositório, o hash do
> outro na mensagem; o `sol.json` publicado registra a árvore de trabalho `f3bd27e`, ver §0.3).

## §0 — Em uma tela (o que o usuário passa a ter)

| antes | depois | portão | passo |
|---|---|---|---|
| a exigência do problema («mate em 2», `#2`, `3‡`) só virava «Brancas jogam»; `Diagram.solution` nunca existia; a S-33 deixou escrita a hipótese «uma avaliação bizarra sugere erro de OCR» como não feita | a exigência é lida da legenda (6 línguas, `#N`/`N‡`/`N±`) ou da faixa de margem («Combinations #2» do Polgar), **jogada** sobre a leitura — busca exaustiva para mate em 1–2, Stockfish `go mate N` para 3+ — e devolvida: `[Stipulation]`/`[StipulationCheck]` no PGN, «Exigência #2: fecha (1.♛d1+)» no painel, `Diagram.stipulation` + `Diagram.solution` no EPUB/DOCX; quando não fecha, as candidatas do C11 são tentadas e a troca única adotada; e a **verdade anotada** é conferida contra a exigência | campo: 10 conferidas (Polgar 6 `#2` por escopo de página, Niemeijer `#3 #3 #3 #4`), 8 fecham, 2 não, 0 reparadas (população: nenhuma leitura errada de mate em 2), **verdade fecha 9/10** — a que não fecha é uma **anotação errada do conjunto de campo** (Niemeijer p20 d0, fila 5 deslocada); e uma segunda anotação errada apareceu pelo mesmo caminho (p20 d2, `h1 R→r`: a leitura da máquina era a certa) — `field_corrections.json`; sabotagem `sem_estipulacao` → 0 conferidas | C12 |
| «EPUBCheck 0 erros» era um teste **pulado** (jar ausente) | o jar 4.2.6 fixado em `tools/epubcheck-4.2.6/` (do zip que o Sigil já tinha; `tools/instalar_epubcheck.py`), `caissa.export.epubcheck` como locator/runner do produto, o teste roda, e `percurso --fluxo livro` valida o EPUB que a pessoa exportou | `test_epubcheck` 6/6 + `test_epubcheck_reports_no_errors` **não pulado** (0 erros); sabotagem `mimetype` corrompido → ≥ 1 erro; **e o portão achou 4 erros no EPUB do produto** (`OPF-028`, prefixo `pdf:` não declarado — invisível ao corpus dos testes), corrigidos: `percurso --fluxo livro` PASSOU com `erros=0`; `--sabotar sem_epubcheck` → REPROVOU | A12 |
| o instrumento roteava todo item limpo do benchmark como «letra pequena» (altura-x lida 5 px no recorte de 382 px) e corria RapidOCR + upscale onde o produto, com folhas inteiras, não corre; a abstenção contava como CER 0 | teto físico de componente (0,25 pol) — o parágrafo solto e a folha inteira medem a mesma altura-x; `cer_all` (abstenção = 1,0) e `cer_withheld` (o texto retido) publicados ao lado do CER dos aceitos | `bench_sol` (6 estratos, 747 itens; `sol.json` **republicado** — estava em `69583fd`, 2026-09-13): com o teto físico o benchmark **deixa de fazer o que o produto não faz** e os números mudam nos dois sentidos — `scan_clean_300` CER 0,0058 → **0,0054** e ordem 0,9833 → **1,0000**, `fax_dither` 0,0312 → **0,0382** (a rota «letra pequena» ajudava o fax por acidente), lances limpos 0,9586 → 0,9504; `native` CER 0,0235 entre os que respondem mas **0,1801 com a abstenção** (38 de 237), texto retido CER 0,46 (19) — a abstenção é justificada e agora é dita; sabotagem `xheight_relative` devolve os números da fase 3 ao décimo de milésimo | B11 |
| o Tesseract era informado de 300 DPI sobre a variante de 450; a ligadura `ﬁ` (U+FB01) entrava no IR | `RegionTask.dpi` → `TesseractEngine.with_dpi` (thread-local); as sete ligaduras dobram na fronteira de **todo** motor (`engines/normalize.py`, não NFKC: `½` e `²` ficam) | testes 6/6; `bench_sol` `variant_dpi` on × off: `scan_degraded_150` CER 0,0256 → **0,0224**, `photo` 0,1108 → **0,0983**, `shadow_curl_bleed` 0,0380 → 0,0377; lances 150 DPI 0,8839 → 0,8817 (−0,002, inventados 56 → 60); os outros estratos idênticos | B12 |
| uma pasta por processo para todas as importações; «podem ser exportadas» seguido de «descartada» no rodapé ao trocar de livro | uma pasta **por importação** (`<livro>-<n>`); `cancelar(motivo="troca_de_livro")` cala a promessa — um rodapé só | testes 2/2; `paralelo --outro-livro Aagaard`: **PASSOU**, o rodapé sem «podem ser exportadas» antes de «descartada»; `--sabotar rodape_duplo` devolve o par contraditório e **REPROVOU** | A13 |
| «casa e2 selecionada» ia ao rodapé e nenhum leitor de tela ouvia; nenhum portão rodava com `QT_SCALE_FACTOR`; `grep HighContrast` não achava nada | o tabuleiro anuncia «Tabuleiro, casa e2 selecionada: peão branco; N casas em dúvida» pelo nome acessível; `capture --escala 1.25/1.5/2` e `vazio` a 200 %; com o alto contraste do Windows ligado a pele **não** é aplicada | `audit.teclado._medir_o_tabuleiro` (sabotagem `CAISSA_SABOTAR_ANUNCIO=1` → REPROVOU); **vermelho medido**: a janela exige **1248×695 lógicos** — a 125 % não cabe em 1366×768 nem 1280×800, a 150 % só em ≥ 1920×1080, a 200 % só em 4K; `vazio` a 200 % sobre 4K: **6 de 8 painéis acima de 200 kpx** (pior 1 576,8, Texto) | C14 |
| o campo publicava um número que incluía páginas com amostra de treino; 7 rótulos da janela sem partição (dois de página de campo iam para `train` no próximo `cvoff-train`) | `field_exact_clean` ao lado do cheio (S-96 × S-97); rótulo novo de página de campo vai para `test`, nunca `train` (`training.pin_field_pages`), e os 7 receberam partição: 2 de página de campo → `test` pela guarda, os outros 5 pelo sorteio | produção, régua corrigida: `field_exact` **0,9903** (102/103) × `field_exact_clean` **0,9888** (88/89) — 14 diagramas de 6 páginas com amostra de treino, todos exportados e exatos; o viés é **+0,0015** (anotado: 0,9709 × 0,9663, +0,0046), medido; teste da guarda (rótulo `51` = página de campo `50`) | C15 |
| as sabotagens `i`/`i50` do C4 foram inertes (inversão sem troca de rótulo); a pergunta de `labels.py` («as corrigidas à mão treinam melhor?») sem número | `ruido_de_cor` (`X↔x` em 10 % das casas ocupadas de treino, `OptimPlan.label_noise`) e `corrected_repeat` (rota humana ×3, `ROTAS_HUMANAS`), ambos no checkpoint; variantes `x10`/`w3` na ablação | `x10` s42: teste **557/569** contra `aug0` s42 **558/569** (produção 555) — o laboratório vê 1 tabuleiro e 8 casas de um ruído de 10 %; mas o **campo** vê: exportados **72** contra 104 (32 barrados no gate — o modelo treinado com rótulo sujo fica menos confiante), 72/72 exatos, e 108/114 exatos no total contra 103 (o ruído regularizou). `w3` s42 (rota humana ×3): teste **558/569** (= `aug0`), campo 104 exportados, 101/102 exatos (= `aug0`), 107/114 exatos no total (+4); uma semente — medição, não veredito | C16 |

### 0.1 O que a medição mudou no desenho (as armadilhas, cada uma medida)

- **«Mate em N» é mate em exatamente N.** A primeira versão aceitava um mate mais curto como
  «fecha». Na busca de trocas isso deixava uma peça a mais «fechar» por um mate em 1 que o
  problema nunca teve — e o teste do empate (duas casas hesitantes) passou a ter três
  vencedoras. Um mate mais curto é cozido ou leitura errada: `Verificacao(False, "a leitura tem
  mate em 1 …, mais curto que a exigência")`. Com a regra, o par do C11 (`test_a_tie_between_
  two_repairs_adopts_none`) volta a ser um empate de duas.
- **A busca de trocas não corre com o motor.** Cada verificação de mate em 3+ custa até 3 s de
  Stockfish; 38 candidatas × 3 s numa página de seis problemas seria a janela travada. Com o
  motor só a conferência; a troca única só com a busca exaustiva (mate ≤ 2) e nunca com mate em 1
  (a regra «um lance só confirma» do C11).
- **O motor pendurava o processo na saída.** O `SimpleEngine` do python-chess corre o laço numa
  thread que não é *daemon*; o desligamento do interpretador junta essas threads **antes** dos
  `atexit`, e um `atexit.register(motor.close)` chegava tarde: o `field_exact` imprimia o
  relatório e não terminava (duas corridas mortas à mão). `estipulacao.registrar_fecho` usa
  `threading._register_atexit` — o gancho que `concurrent.futures` usa — e o processo sai
  (medido: `exit code 0` sem `close` explícito).
- **O portão (a) do C12 achou duas anotações erradas no conjunto de campo.** A verdade do
  Niemeijer p20 d0 (`2B5/1KR3B1/4P3/pN1k2pN/…`) tem **mate em 1** (`Nf6#`) para uma exigência
  `3‡` com solução impressa `1. Pd3` — e `Nd3` nem é legal na anotação: na imagem (renderizada a
  3× com grade, `scratchpad/nm_board.png`) o peão preto e o cavalo branco da fila 5 estão em
  **f5/g5**, não em g5/h5. Corrigida a fila, a posição tem mate em 2 — a verdade completa ainda
  não é a do compositor e fica para olho humano (lista do 0b). E o p20 d2: a anotação diz torre
  **branca** em h1; a leitura da máquina («exportada e errada», torre preta a 0,805) fecha o
  `3+` com `1.Kb7` — **a chave que o livro imprime** —, enquanto a anotação só tem o mate em 3 grosseiro
  `1.Rxg1 Bxg1 2.Ba3+ Bc5 3.Bxc5#` (uma captura de dama como chave) e `1.Kb7` é mate em 5. Prova
  documental + o glifo (corpo escuro em casa clara, como o bispo f2 e a dama g1 ao lado):
  entrou em `benchmarks/field_corrections.json` com a evidência. Régua corrigida: exportados-e-
  exatos **102/103** (0,9903), exatos 107/114.
- **A sabotagem `estipulacao_vizinha` morde pouco.** Numa página de problemas a exigência é a
  da página (as seis do Polgar são `#2`), e a rotação só muda onde as legendas diferem (2 das 10):
  `checked 10 · closed 8 · failed 2 · truth 8/10` contra `9/10`. A sabotagem que reprova o
  portão é `sem_estipulacao` (`checked 0`); a vizinha fica dita como fraca nesta população.
- **O primeiro EPUB do produto que o validador viu tinha 4 erros.** «EPUBCheck 0 erros» valia
  para o corpus sintético; o livro importado carrega metadados do PDF com `scheme="pdf"` e o
  `<package>` não declarava o prefixo. É o caso que a análise §6.9 descreve — um portão que só
  rodava onde não havia o que achar — e a razão de o `percurso --fluxo livro` validar o EPUB
  **que a pessoa exportou**, não um de laboratório.
- **A anotação de campo é base 0 e o `labels.csv` base 1 — de novo** (fase 3 §0.1): a guarda
  `pin_field_pages` converte, e o teste usa o rótulo `51` contra a página de campo `50`.
- **A altura-x sintética não reproduz «5 px».** Com a fonte do arnês o teto relativo em 382 px
  dá **0,0** (menos de 20 componentes sobram) e não 5 px como nos itens reais do corpus — os
  dois são a mesma falha (o que sobra não é letra); o teste afirma «solto = folha» com o teto
  físico e «solto ≠ folha» com o relativo, e o número da mudança de rota vem do benchmark.
- **O PyQt6 não expõe `QAccessible`.** O roadmap pedia `QAccessible.updateAccessibility`; o
  binding não o tem. O próprio `QWidget.setAccessibleName` emite o `NameChanged` de
  acessibilidade no Qt; o anúncio é o nome, só quando muda (senão cada redesenho anunciaria).
- **A janela tem um mínimo de 1248×695 lógicos.** `capture --escala` não mede um vazio a mais:
  mede que a 125 % (a tela de um portátil 1366×768 a 125 %, 1093×614 lógicos) a janela **não
  cabe**. É um número do desenho, novo, e vermelho.
- **O ruído de rótulo a 10 % quase não aparece no laboratório — e aparece inteiro no campo.**
  `x10` perde 1 tabuleiro (557 × 558 em 569) e 8 casas (36.386 × 36.394) no teste; no campo
  exporta 72 em vez de 104: a rede treinada com rótulo sujo fica menos confiante e o gate a
  barra. O instrumento que responde ao C4 é a taxa de exportação do campo, não o `board_exact`
  (§C16).

### 0.2 Invariantes e portões rodados na integração

| invariante / portão | resultado | comando |
|---|---|---|
| testes do tronco | **4.779 passaram, 4 pulados, 8 xfail, 1 desselecionado, 1 reprovou** em 372 s (`trunk_tests2.out`): `test_strings::AccentTests` (de antes da fase, o mesmo das fases 2 e 3: `cabecas`/`configuracoes`/`pagina`/`SELECAO` em módulos que a fase não tocou — o `nao` que a primeira corrida acusou em `plataforma.py` era desta fase e foi tirado). A primeira corrida inteira (535 s) reprovou também `test_ocr_caption::test_onde_a_camada_de_texto_respondeu_o_ocr_nao_roda`: o escopo de página da exigência consultava a margem por **OCR** em toda página sem exigência e quebrava a economia da S-61 — hoje só a camada de texto (§0.1) | `..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --deselect tests/test_field_eval.py::ImpressaoDaMedicaoTests::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje` |
| suíte de testes (com PyQt6) | **3.931 passaram, 9 pulados, 0 reprovaram** em 776 s (`suite_tests.out`; fase 3: 3.907/10 — o pulado que sumiu é o EPUBCheck); `test_arquitetura.py` à parte **19/19** | `PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py --ignore=tests\unit\ui\test_arquitetura.py`; `test_arquitetura.py` à parte |
| `bench_sol` + `sol_gate --report-only` no código da fase (6 estratos, com `photo`, 747 itens) | `sol.json` republicado (§B11): silenciosas **0**, controles **0/9**, ordem **1,0000**, ambiente reproduz o baseline, nenhuma regressão de CER fora do IC contra o `baseline` (o sistema Tesseract-só); os portões absolutos continuam **bloqueados** (CER limpo 0,0145 em 2 estratos ≤ 0,005; 150 DPI 0,0224 ≤ 0,020; lances 0,9029 ≥ 0,998; inventados 158) como em todas as fases — agora sobre o número do produto e não do artefato. 747 itens em ~20 min por corrida, três corridas em sequência e sem outro trabalho de CPU (o treino do C16 tinha acabado) | `CAISSA_FIGURINE_TESSDATA=models\tessdata .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo --label sol --publish`; `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` |
| `field_exact` no código da fase (produção, régua corrigida) | exportados 103, exatos 102/103 (**0,9903**), limpo 88/89 (**0,9888**), exatos 107/114; 3 corridas idênticas; estipulação 10/8/2, verdade 9/10; `field_exact_*_f4_final.json` | `.venv\Scripts\python.exe benchmarks\field_exact.py --variant recall-pack --runs 3 --corrections --tag f4_final --motor <stockfish>` |
| `git status --short` | só os caminhos da fase nas duas árvores (`tools/epubcheck-4.2.6/` ignorado; `benchmarks/reports/` ignorado) | `git status --short` |

### 0.3 O que ficou vermelho ou aberto (honesto)

- **C12 não reparou nada no campo.** Das 10 exigências, as 6 do Polgar fecham na leitura e as
  4 do Niemeijer são mate em 3–4 (nível do motor, sem busca de trocas). O reparo pela exigência
  fica pelos 22 testes (`test_estipulacao.py`) até haver no campo um mate em 2 lido errado.
  O Vladimirov (4 diagramas, scan) não tem exigência lida: o OCR das legendas não devolve
  `#2` — população, não mecanismo.
- **Duas anotações erradas no conjunto de campo.** Uma corrigida na sobreposição (Niemeijer
  p20 d2, prova documental); a outra (p20 d0) fica apontada com a evidência da imagem e sem
  correção — a fila 5 corrigida ainda tem mate em 2 para uma exigência de 3, e a verdade
  completa é olho humano (0b).
- **A janela não cabe a 125 % em 1366×768** (mínimo 1248×695 lógicos) e a 200 % sobre 4K os
  vazios passam do teto em 6 de 8 painéis. Os dois são do desenho, não do arnês: vão para o
  crítico visual C3 com os JSON (`benchmarks/reports/ui/c2_fase4/`).
- **O alto contraste é «a pele sai do caminho», não uma pele.** Contornos no tabuleiro e nos
  papéis de confiança são desenho (C3).
- **A sabotagem `estipulacao_vizinha` é fraca nesta população** (2 de 10 exigências diferem
  do vizinho).
- **O laboratório quase não vê 10 % de ruído de rótulo** (1 tabuleiro em 569); o campo vê
  32 exportados a menos. A régua da fase 3 para o C4 (`board_exact` + exportados-e-errados)
  era cega ao dano; a régua que o vê (exportados + exatos totais no campo) fica nomeada. O
  `w3` tem uma semente: as outras duas são treino de 2 × 25 min que a pessoa decide.
- **O texto da camada de texto do PDF continua com ligaduras.** B12 dobra o que os **motores**
  emitem; a camada de texto é «o que o PDF diz» e ficou intacta — dito aqui para ninguém supor
  o contrário.
- **O fax perdeu 0,0070 de CER no benchmark — e não perdeu nada no produto.** A rota «letra
  pequena» ajudava o fax por acidente do instrumento; o produto com folhas inteiras já pagava
  0,0382. A alavanca que devolve 0,0312 pelo sinal certo (fax/pontilhado → upscale + segundo
  motor) fica nomeada com o número, não feita.
- **O `sol.json` publicado carrega o commit da árvore de trabalho** (`f3bd27e`): remedir no
  commit final custa 20 min e o CER é determinístico (B9: 274/274; fase 2: `f3` = `f2`); a
  segunda corrida publicada no commit desta fase fica para o commit seguinte da suíte, como na
  fase 2.

## §C16 — A sabotagem que faltava ao C4 (ruído de rótulo `X↔x`) e o peso da correção humana

- **Arquivos.** Tronco: `dataset.py` (`BoardFenDataset.label_overrides`, `ruido_de_cor`,
  `ROTAS_HUMANAS`, `tabuleiros_de_rota_humana`), `training.py` (`OptimPlan.label_noise`,
  `OptimPlan.corrected_repeat`, os grupos repetidos no `BoardGroupedSampler` e as unidades
  repetidas na cabeça por tabuleiro, metadados `label_noise`/`corrected_repeat` no checkpoint,
  `train_model(label_noise=, corrected_repeat=)`), `cli/train.py` (`--label-noise`,
  `--corrected-repeat`), `tests/test_training.py` (+4). Suíte: `benchmarks/c4_ablation.py`
  (`LABEL_NOISE_VARIANTS = {"x10": 0.10, "x25": 0.25}`, `CORRECTED_REPEAT_VARIANTS = {"w3": 3,
  "w5": 5}`, `training_knobs` no JSON).
- **O que foi treinado.** `x10` e `w3`, semente 42, 16 épocas, `assign_splits=False` sobre a
  mesma partição da fase 3 (4 344 tabuleiros de treino, 535 de validação; 7 rótulos ainda sem
  split — os mesmos que o C15 atribuiu **depois**). `x10`: 7 011 casas de treino com a cor
  trocada (10 % das ocupadas); `train_square_acc` estaciona em 0,973 (o teto do rótulo sujo) e
  `val_square_acc` em 0,998 — a validação, limpa, não vê o ruído. Tempo: 1,5 min/época (GPU
  livre; a fase 3 mediu 3,2 com o campo ao lado).
  `.venv\Scripts\python.exe benchmarks\c4_ablation.py --seeds 42 --variants x10,w3 --epochs 16 --workers 4`
  (`benchmarks\reports\c4_ablation\c4_x10_s42.json`, `c4_w3_s42.json`; checkpoints em
  `..\ChessVisionOFF_Puro\models\experiments\c4_{x10,w3}_s42.pt`).
- **Laboratório** (`benchmarks\lab_gate.py --runs 3 --candidate … --unconstrained --tag f4_c16_<v>`;
  o split `test` tem agora **569** tabuleiros — 566 + os 3 que o C15 pôs em `test` —, por isso
  o `aug0` s42 foi remedido no mesmo conjunto):

  | modelo | teste exato (c11) | casas | ilegais (cru) | helped/hurt |
  |---|---|---|---|---|
  | produção (`piece_classifier.pt`) | 555/569 = 0,9754 | 0,999066 | 6 | 2/0 |
  | `c4_aug0_s42` | **558/569 = 0,9807** | 0,999396 | 1 | 2/0 |
  | `c4_x10_s42` (ruído 10 %) | **557/569 = 0,9789** | 0,999176 | 2 | 2/0 |
  | `c4_w3_s42` (rota humana ×3) | **558/569 = 0,9807** | 0,999259 | 2 | 3/0 |

  (`benchmarks\reports\lab_gate_20260921_140857_f4_c16_aug0.json`, `…_f4_c16_x10.json`,
  `…_f4_c16_w3.json`.)
- **Campo** (`field_exact.py --variant recall-pack --runs 3 --corrections --model … --tag f4_c16_<v>`,
  3 corridas idênticas cada; `benchmarks\reports\field_exact_*_f4_c16_{aug0,x10,w3}.json`):

  | modelo | exportados | exp.-exatos (anotado / corrigido) | `field_exact` | exatos em 114 | legais | exportados-e-errados |
  |---|---|---|---|---|---|---|
  | `c4_aug0_s42` | 104 | 101 / 102 | 0,9712 / 0,9808 | 103 / 105 | 114 | Koblenz p30, Burgess p60 |
  | `c4_x10_s42` | **72** | 72 / 72 | 1,0000 | **108** / 108 | 113 | — |
  | `c4_w3_s42` | 104 | 101 / 102 | 0,9712 / 0,9808 | **107** / 109 | 114 | Euwe p40, Burgess p60 |

- **Veredito.** A sabotagem `x10` **é vista** — não onde o C4 olhava. No laboratório o ruído
  de 10 % custa 1 tabuleiro em 569 (a rede é robusta a rótulo trocado: `train_square_acc`
  estaciona em 0,973 e a validação limpa não se move); no campo custa **32 diagramas
  exportados** (104 → 72): treinada sobre rótulos que mentem, a rede fica menos confiante, e a
  temperatura calibrada na validação limpa não a devolve — o gate de 0,80 barra o que antes
  passava. E o que passa é todo exato (72/72), com 108 exatos no total contra 103: o ruído
  regularizou. Logo: o instrumento que resolve a pergunta do C4 é o **campo, pela taxa de
  exportação e pelos exatos totais**, não o `board_exact` do teste — a fase 3 comparou as
  variantes pelo laboratório e pelos exportados-e-errados, e as duas réguas são cegas a este
  dano. A próxima sabotagem escrita (`x25`) não é necessária para provar a régua; fica na
  tabela para quem quiser a curva. O peso da correção humana (`w3`): igual ao `aug0` no que
  exporta e nos exportados-e-errados (2, outros dois diagramas), +4 exatos no total em uma
  semente — dentro da dispersão que a fase 3 mediu entre sementes (1–4). A pergunta de
  `labels.py` ganhou um número, e o número diz «não pior, talvez melhor; três sementes para
  afirmar». O `.pt` de produção continua intacto; a decisão §10.2 continua da pessoa, agora
  com a régua certa nomeada.

## §C12 — A estipulação como evidência

- **Arquivos.** Tronco: `estipulacao.py` (novo, 470 linhas: `Estipulacao`, `parse_estipulacao`,
  `estipulacao_de_pagina`, `Verificacao`, `verificar`, `ReparoPelaEstipulacao`, `conferir`,
  `apply_stipulation`, `motor_padrao`, `registrar_fecho`, `esquecer_motor`), `engine.py`
  (`EngineAnalyzer.mate_in`), `pdf_text.py` (`DiagramContext.stipulation`, a leitura nas
  linhas de legenda, `page_stipulation_declaration` na faixa de margem), `service.py`
  (`RecognitionOptions.stipulation`/`stipulation_engine`; `RecognizedDiagram.stipulation`,
  `stipulation_closes`, `stipulation_keys`, `stipulation_repairs`, `stipulation_reason`;
  `external_repairs` inclui as trocas pela exigência; `_stipulation_engine` só abre o motor para
  mate em 3+), `pdf_to_pgn.py` (`DiagramPosition.stipulation*`, `[Stipulation]`,
  `[StipulationCheck]`, `[OCRStipulation]`, `_motor_para`), `proveniencia.py` (o sidecar leva a
  exigência e o veredito), `field_eval.py` (contadores `stipulation_*` e o portão (a):
  `_truth_closes` joga a **verdade** contra a exigência lida), `qt/painel_de_resultado.py` +
  `ui/strings.estipulacao_conferida` («Exigência #2: fecha — Mate em 2 fecha: 1.Qd1+»),
  `README.md`, `tests/test_estipulacao.py` (novo, 22 testes), `test_pdf_to_pgn.py` (+1),
  `test_field_eval.py` (+2). Suíte: `ingest/pdf/captions.py` (`Stipulation`, `parse_stipulation`,
  `page_stipulation`, `apply_page_stipulation`, `DiagramContext.stipulation`), `importer.py`
  (`PdfImportOptions.verify_stipulations`; `Diagram.stipulation` = «Mate em 2»,
  `Diagram.solution` com a chave, aviso «exigência #2: …»; contadores `stipulations_checked`/
  `stipulations_failed`), `benchmarks/field_exact.py` (`--sabotar sem_estipulacao|
  estipulacao_vizinha`, `--motor`, contadores no JSON e na tela), `benchmarks/
  field_corrections.json` (+1 entrada com evidência), `tests/unit/ingest/test_captions.py`
  (+4, com o teste de paridade contra a gramática do tronco em 28 frases),
  `tests/unit/ingest/test_stipulation.py` (novo, 4).
- **A gramática.** `#2`/`# 2`/`‡2` como token (não `h#2`/`s#2`/`r#2`, não `problem #2`, não
  `#2.5`); `3#`/`3‡`/`3±`/`3+` como **linha inteira** (a camada de texto do Niemeijer devolve `3±`
  para o `3‡` impresso); «mate in two», «mate em 2 lances», «mat en 2 coups», «Matt in 2 Zügen»,
  «mat in twee zetten», «мат в 3 хода»; só em linha com formato de legenda — em prosa «mate em 2»
  é uma afirmação sobre uma variante; e o escopo de página («2.2 Combinations #2 (451-3514)» no
  topo do Polgar) vale para os diagramas cuja legenda cala, com duas exigências diferentes na
  faixa anulando-se. A suíte tem a mesma tabela e o teste de paridade a segura.
- **A busca.** Xeques primeiro, depois capturas; para o último lance só xeques; as chaves param
  na segunda (uma é o problema, duas é «cozido»); mate em exatamente N (um mais curto é dito);
  `LIMITE_NOS = 400 000` → «orçamento» em vez de fingir «não fecha». Medido: a verdade do teste
  (mate em 2) fecha em 68 nós; a posição inicial e a Italiana recusam mate em 2 em 40 e 97 nós
  (o primeiro lance sem xeque corta cedo). Mate em 3+ é `EngineAnalyzer.mate_in` (`Limit(mate=N,
  time=3 s)`), com o ponto de vista virado para quem joga.
- **Portão (campo).** `field_exact.py --variant recall-pack --runs 3 --corrections --tag f4_c12_on2
  --motor <stockfish>` (`benchmarks\reports\field_exact_20260921_134632_f4_c12_on2.json`):

  | régua | exportados | comparáveis | exatos | `field_exact` | exatos (114) | conferidas | fecham | não fecham | não verif. | reparadas | ambíguas | verdade fecha |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | como anotado | 103 | 103 | 100 | 0,9709 | 105 | 10 | 8 | 2 | 0 | 0 | 0 | **9/10** |
  | corrigida (+ Niemeijer h1) | 103 | 103 | **102** | **0,9903** | 107 | 10 | 8 | 2 | 0 | 0 | 0 | 9/10 |

  Por livro: Polgar p300 6/6 fecham (escopo de página `#2`, verdades 6/6); Niemeijer p20 4
  conferidas, 2 fecham (`1.Qc1` = o «Del.» do livro lido como `Dc1`; e a p20 d2 com a leitura
  da máquina `1.Kb7`), 2 não (d0: nem a verdade fecha; d3: leitura barrada no gate a 0,495 —
  a verdade fecha com `1.Nf5` = o «Pf5» impresso). **Sabotagens:** `--sabotar sem_estipulacao`
  → `checked 0`, exatos idênticos (`…_135739_f4_c12_sem.json`); `--sabotar estipulacao_vizinha`
  → `checked 10 · closed 8 · failed 2 · truth 8/10` (`…_140504_f4_c12_vizinha.json`): morde só
  onde as legendas diferem (§0.1). O portão (b) `stipulation_repaired_wrong` = 0 por população 0.
- **Saída.** `[Stipulation "#3"]` `[StipulationCheck "fecha: 1.Kb7"]` no PGN do Niemeijer;
  «Exigência #3: não fecha nesta leitura — confira» no painel do d0; no EPUB o `Diagram` com
  `stipulation="Mate em 2"` e `solution` de um lance (`emphasis=True`) — `test_stipulation.py`.

## §A12 — EPUBCheck como invariante

- **Arquivos.** Suíte: `src/caissa/export/epubcheck.py` (novo: `find_epubcheck_jar` —
  `CAISSA_EPUBCHECK`, `tools/epubcheck-*/`, `%LOCALAPPDATA%\Caissa\`, `%TEMP%`/home —,
  `java_available`, `run_epubcheck` → `EpubCheckResult(errors, warnings, output, jar)` com a
  linha-resumo lida nas duas línguas, erros fatais somados e **`-1` quando o processo falha
  sem resumo** — «arquivo não encontrado» saía com «0 erros» e código 1), `tools/
  instalar_epubcheck.py` (novo: desempacota o zip da release ou a cópia do Sigil),
  `tests/unit/export/corpus.py` (delega ao módulo), `tests/unit/export/test_epubcheck.py`
  (novo, 5), `ui/audit/percurso.py` (`Percurso.epubcheck`, `_epubcheck_do_epub`, `--sabotar
  sem_epubcheck`; `passou()` exige `epubcheck.ok`), `.gitignore` (`tools/epubcheck-*/`).
- **Portão.** `PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe -m pytest
  tests\unit\export\test_epubcheck.py tests\unit\export\test_epub.py -k epubcheck`: **6 passed**
  (antes: 1 skipped — «EPUBCheck nao encontrado»); o corpus sintético dá 0 erros. **Sabotagem:**
  `test_the_sabotage_a_broken_mimetype_is_counted` — o mesmo pacote com `mimetype = text/plain`
  → `errors ≥ 1`; `test_a_crash_never_reads_as_zero_errors` — pacote inexistente → `-1`.
  `percurso --fluxo livro` (Aagaard 31–38): a **primeira** corrida REPROVOU — o EPUB que a
  janela exporta tinha **4 erros** `OPF-028: Prefixo não declarado: "pdf"` (`content.opf`
  linhas 15–18): as entradas `MetadataEntry(scheme="pdf")` do importador (Producer, CreationDate…)
  saíam como `<meta property="pdf:Producer">` sem `pdf:` no `prefix` do `<package>`. O corpus
  sintético dos testes não tem entrada assim, por isso «0 erros» passava. `export/epub.py`:
  todo esquema de metadado vira prefixo declarado (`_prefix_token`, `_BUILTIN_PREFIXES` para os
  reservados) e o nome vira termo válido (`_property_token`: «Creation Date» → `Creation-Date`);
  `test_a_custom_metadata_scheme_is_a_declared_prefix` roda o EPUBCheck sobre um livro com essas
  entradas. Segunda corrida: **PASSOU**, `epubcheck.ok=True, erros=0, avisos=0`
  (`benchmarks/reports/ui/c2_fase4/percurso/percurso_20260921_171816.json`); `--sabotar
  sem_epubcheck` → `ok=False, motivo="EPUBCheck não rodou: jar ausente"`, **REPROVOU**
  (`…/percurso_sabotado_sem_epubcheck_20260921_171951.json`). Comando:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src;../ChessVisionOFF_Puro/src;.venv-pack/Lib/site-packages
  .venv/Scripts/python.exe -m caissa.ui.audit.percurso --fluxo livro --pdf "…/AAGAARD - Practical
  Chess Defence.pdf" --paginas 31-38 --saida benchmarks/reports/ui/c2_fase4/percurso`.
- **Saída.** «0 erros» é um número que o validador produziu, em toda invariante desta máquina
  — e o primeiro número que ele produziu sobre o produto foi 4.

## §B11 — O instrumento mede o que o produto faz

- **Arquivos.** Suíte: `ocr/portfolio.py` (`LETTER_MAX_INCHES = 0.25`, `_xheight_px(gray, dpi,
  relative=)`, `PortfolioConfig.xheight_relative` — a sabotagem —, `detect_signals(config=)`),
  `ingest/pdf/ocr_service.py` (passa o `portfolio` a `detect_signals`), `benchmarks/bench_sol.py`
  (`SOL_CONFIG` aninhado `{"portfolio": {...}}`; `cer_all` e `cer_withheld` por item; as colunas
  «CER c/ abst.» e «CER retido» no Markdown), `ocr/gates.py` (`cer_all_mean`,
  `cer_withheld_mean`, `withheld_with_text` no resumo), `tests/unit/ocr/test_portfolio.py` (+1),
  `test_sol_metrics.py` (+1).
- **Portão.** Três corridas de 747 itens (6 estratos, o `photo` incluído; `CAISSA_FIGURINE_TESSDATA=
  models\tessdata`; `--strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo`):
  `--label sol --publish` (a fase, publicada em `docs/quality/sol/sol.json` + `sol.md`),
  `SOL_CONFIG='{"portfolio": {"xheight_relative": true}}' --label f4_b11_off` (a sabotagem: o
  teto relativo, `benchmarks/reports/sol/f4_b11_off_20260921_150124.json`) e `SOL_CONFIG=
  '{"variant_dpi": false}' --label f4_b12_off` (§B12). O `f4_b11_off` reproduz a fase 3
  (`fase3_on_20260921_062711.json`) ao décimo de milésimo onde o B12 não toca — é a prova de
  que a diferença abaixo é a rota.

  | estrato | n | fase 3 / `b11_off` (teto relativo) | **`sol` (teto físico)** | Δ CER | lances antes → depois | ordem | CER c/ abst. | CER retido (n) |
  |---|---|---|---|---|---|---|---|---|
  | scan_clean_300 | 137 | 0,0058 | **0,0054** | −0,0004 | 0,9586 → 0,9504 | 0,9833 → **1,0000** | 0,0054 | — |
  | scan_degraded_150 | 137 | 0,0224 (B12 já on) | 0,0224 | 0 | 0,8817 → 0,8817 | 1,0 | 0,0224 | — |
  | native | 237 | 0,0234 | 0,0235 | +0,0001 | 0,9391 → 0,9416 | — | **0,1801** | **0,4648 (19)** |
  | shadow_curl_bleed | 101 | 0,0370 | 0,0377 | +0,0007 | 0,9383 → 0,9364 | — | 0,0377 | — |
  | fax_dither | 63 | 0,0312 | **0,0382** | **+0,0070** | 0,8283 → 0,8201 | — | 0,0382 | — |
  | photo | 63 | 0,0983 | 0,0983 | 0 | 0,8516 → 0,8516 | — | 0,0983 | — |

  O que a tabela diz: (1) nos itens limpos o benchmark corria RapidOCR + upscale e o produto
  não — tirado o artefato, o CER limpo melhora (0,0054) e a ordem fecha (o `twocol:a:10` de
  sempre era a rota, não o leiaute), mas os lances caem 0,9586 → 0,9504 (inventados 18 → 22):
  o segundo motor ajudava os lances nos itens limpos, e o produto nunca o teve; (2) no **fax**
  a rota «letra pequena» ajudava por acidente (+0,0070 de CER sem ela): o produto, com folhas
  inteiras, já pagava esse número — o benchmark é que o escondia; a alavanca nomeada é rotear
  o fax pelo sinal certo (`is_binary`/pontilhado → upscale + secundário), medida à parte
  (0,0312 é o ganho conhecido); (3) a abstenção não é CER 0: o `native` custa 0,1801 ao
  leitor quando os 38 abstidos contam a página inteira, e o texto que o serviço tinha e
  reteve (19 deles) mede CER 0,46 — reter foi certo, e agora está no `sol.md` («CER c/
  abst.», «CER retido»). `sol_gate --report-only docs/quality/sol/sol.json`: 0 silenciosas,
  **0/9 controles**, ordem 1,0000; os portões absolutos (CER limpo 0,0145 em 2 estratos ≤
  0,005; 150 DPI 0,0224 ≤ 0,020; lances 0,9029 ≥ 0,998; inventados 158 = 0) continuam
  **bloqueados** como em todas as fases — e agora sobre o número do produto.

## §B12 — O DPI real chega ao Tesseract; as ligaduras dobram na fronteira

- **Arquivos.** Suíte: `ocr/arbiter.py` (`RegionTask.dpi`; o árbitro entra em `engine.with_dpi`
  quando o motor o tem), `ocr/engines/tesseract.py` (`with_dpi`, `_effective_dpi`: o `--dpi` da
  linha de comando e o DPI gravado no PNG), `ocr/page.py` (`PageConfig.variant_dpi`, o DPI da
  página nas três construções de `RegionTask`), `ingest/pdf/ocr_service.py`
  (`OcrServiceConfig.variant_dpi`, propagado à `PageConfig`; o DPI da variante em
  `_read_on_variant`), `ocr/engines/normalize.py` (novo: `LIGATURES`, `fold_ligatures`,
  `fold_result`), `ocr/engines/base.py` (todo resultado passa por `fold_result`),
  `tests/unit/ocr/test_engine_dpi_ligatures.py` (novo, 6).
- **Portão.** Testes 6/6 (a fronteira: `ﬁ` nunca sai de um motor; `½`/`²`/`№` ficam; o
  árbitro entrega 450 ao motor que aceita e nada ao que não; o comando do Tesseract leva `--dpi
  450` dentro do bloco e `300` fora e noutra thread). `bench_sol` `sol` (on) × `f4_b12_off`
  (`benchmarks/reports/sol/f4_b12_off_20260921_151229.json`), B11 ligado nos dois:

  | estrato | `variant_dpi=False` | **`True`** | Δ CER | lances | inventados |
  |---|---|---|---|---|---|
  | scan_degraded_150 (upscale 150 → 300) | 0,0256 | **0,0224** | −0,0032 | 0,8839 → 0,8817 | 56 → 60 |
  | photo | 0,1108 | **0,0983** | −0,0125 | 0,8365 → 0,8516 | 20 → 21 |
  | shadow_curl_bleed | 0,0380 | 0,0377 | −0,0003 | 0,9317 → 0,9364 | 9 → 9 |
  | scan_clean_300 / native / fax_dither | idênticos | idênticos | 0 | idênticos | idênticos |

  Dizer ao Tesseract a resolução que ele recebe vale −0,0032 no estrato a 150 DPI (o único com
  upscale) e −0,0125 na foto (que também passa pela variante), com −0,002 de lances no
  primeiro. Fica ligado por medição. Ligaduras: 0 pontos de código U+FB00–FB06 nas 90 hipóteses
  que o JSON grava (só os itens com CER > 0,05 as carregam) — o corpus sintético não as produz,
  e a régua é o teste de fronteira (`test_the_base_wrapper_folds_for_every_engine`).

## §A13 — Recursos por importação; um rodapé só

- **Arquivos.** Suíte: `ui/views/importacao.py` (`pasta_da_importacao`: `<livro>-<n>` por
  importação, contador de processo; `cancelar(motivo=)`; `_concluiu` cala a promessa quando o
  motivo é `troca_de_livro`), `ui/audit/paralelo.py` (o rodapé anotado frase a frase na troca de
  livro: `rodape_frases`, `rodape_sem_contradicao`; `--sabotar rodape_duplo`),
  `tests/unit/ui/test_importacao_view.py` (novo, 2). Tronco: `qt/importador_de_livro.py`
  (`cancelar(motivo=)` na ponte e no protocolo), `qt/janela.py` (a troca de livro cancela com
  motivo).
- **Portão.** Testes 2/2 (a pasta muda a cada importação do mesmo livro e fica sob a raiz do
  processo; o cancelamento por troca não diz «podem ser exportadas», o comum diz). `paralelo
  --pdf "1937 Kemeri.pdf" --pagina 80 --outro-livro "AAGAARD - Practical Chess Defence.pdf"`
  (`benchmarks/reports/ui/c2_fase4/paralelo/paralelo_troca_20260921_172210.json`): **PASSOU** —
  o rodapé da troca, frase a frase: «Abrindo AAGAARD…», «A importação de 1937 Kemeri.pdf foi
  cancelada ao abrir outro livro.», … «A importação de 1937 Kemeri.pdf terminou depois de o
  livro mudar; descartada.» — `rodape_sem_contradicao=True`, `resultado_descartado=True`.
  **Sabotagem** `--sabotar rodape_duplo` (o cancelamento chega ao importador sem motivo):
  «Cancelando a importação… o que já foi lido fica.» e «Importação cancelada: 0 de 8 página(s)
  ficaram lidas e podem ser exportadas.» reaparecem antes de «descartada» → `False`, **REPROVOU**
  (`…/paralelo_sabotado_troca_20260921_172221.json`). Os outros campos do C7 continuam verdes
  (`importacao_viva_na_edicao=True`, `edicao_ms_apos_inicio` 39,1/37,3 ms).

## §C14 — O tabuleiro fala ao leitor de tela; os portões a 125/150/200 %; alto contraste

- **Arquivos.** Tronco: `qt/tabuleiro_editavel.py` (`_anunciar`), `ui/strings.py`
  (`nome_acessivel_do_tabuleiro`), `qt/plataforma.py` (`alto_contraste_ativo`,
  `ENV_ALTO_CONTRASTE`), `qt/tema.py` (`aplicar_tema` → `"alto_contraste"`,
  `alto_contraste_em_vigor`), `tests/test_qt_tabuleiro_editavel.py` (+2), `test_qt_tema.py` (+2).
  Suíte: `ui/audit/teclado.py` (`_medir_o_tabuleiro`, `SABOTAGEM_DO_ANUNCIO`, o bloco `tabuleiro`
  no JSON e no veredito), `ui/audit/capture.py` (`--escala`, `tamanhos_logicos`, as recusas em
  `*_recusas.json`, o nome do arquivo com o tamanho físico).
- **Portão.** Tronco: o nome acessível diz «Tabuleiro, casa a8 selecionada: torre preta», «…
  casa e5 selecionada: vazia; 2 casas em dúvida», «Tabuleiro, nenhuma casa selecionada; …»; a
  sabotagem (`_anunciar` calado) não muda o nome — 30/30 no arquivo. Alto contraste:
  `CVOFF_ALTO_CONTRASTE=1` → `aplicar_tema` devolve `"alto_contraste"`, `styleSheet() == ""`,
  `alto_contraste_em_vigor()`; `=0` → `"qss"` — 34/34. Escala (pele `foco`, offscreen):

  | escala | tela física | lógica pedida | ficou (mínimo) | cabe |
  |---|---|---|---|---|
  | 1,25 | 1280×800 / 1366×768 | 1024×640 / 1093×614 | 1248×695 | **não** |
  | 1,5 | 1280×800 / 1366×768 | 853×533 / 911×512 | 1248×695 | **não** |
  | 1,5 | 1920×1080 | 1280×720 | 1280×720 | sim |
  | 2 | 1280×800 / 1366×768 / 1920×1080 | 640×400 / 683×384 / 960×540 | 1248×695 | **não** |
  | 2 | 3840×2160 | 1920×1080 | 1920×1080 | sim |

  `vazio` sobre as capturas 3840×2160 a 200 % (`--capturas … --marca e2`): **6 de 8 painéis acima
  de 200 kpx** — Galeria 808,7, Resultado 327,1, Revisão de texto 1 565,8, Revisão 1 320,4,
  Rotulagem 325,9, Texto 1 576,8 — **REPROVOU** (`benchmarks/reports/ui/c2_fase4/vazio_e2_*.json`,
  `e{125,15,2}_escuro_recusas.json`). Comandos: `PYTHONPATH=src;..\ChessVisionOFF_Puro\src;
  .venv-pack\Lib\site-packages QT_QPA_PLATFORM=offscreen .venv\Scripts\python.exe -m
  caissa.ui.audit.capture --saida <pasta> --marca e2 --escala 2 --pele foco` e `-m
  caissa.ui.audit.vazio --capturas <pasta> --marca e2 --saida <pasta>`. `audit.teclado` (pele
  `foco`, `--json benchmarks/reports/ui/c2_fase4/teclado/teclado_foco.json`): **PASSOU** —
  `tabuleiro: nome_antes="Tabuleiro do diagrama"` (o nome estático da varredura de
  `acessibilidade.nomear_tudo`), `nome_depois="Tabuleiro, casa e2 selecionada: peão branco"`,
  `anuncia_a_casa=True, diz_a_peca=True`; com `CAISSA_SABOTAR_ANUNCIO=1` o nome fica «Tabuleiro
  do diagrama» e o portão **REPROVOU** (`teclado_foco_sabotado.json`). As demais réguas do
  portão (focáveis, nome, papel, diálogos) continuam PASSOU na mesma passada.

## §C15 — O campo limpo

- **Arquivos.** Tronco: `field_eval.py` (`contaminated_exported_comparable`,
  `contaminated_exported_exact`, `clean_exported_comparable`, `field_exact_clean` — no JSON e
  no resumo), `training.py` (`field_pages_beside`, `pin_field_pages`, a guarda em
  `resolve_splits`), `data/splits.csv` (+7), `tests/test_training.py` (+1), `test_field_eval.py`
  (+1). Suíte: `benchmarks/field_exact.py` (as colunas `clean`/`n_clean` e as chaves no JSON).
- **Portão.** Os 7 rótulos sem split: `board_20260921_041915_946609.png` e
  `board_20260921_041951_348219.png` (Koblenz «51» = página de campo 50) → **`test` pela guarda**
  (com o aviso: «2 rótulo(s) novo(s) vêm de página do conjunto de campo e foram para `test`»);
  os outros 5 pelo sorteio (Aagaard 7 → val; Koblenz 50 → train, val; 10 → test; 13 → train);
  nenhum registrado mudou. O split `test` passa de 566 a **569** tabuleiros (dito no §C16).
  `field_exact.py --variant recall-pack --runs 3 --corrections --tag f4_final --motor <stockfish>`
  (`benchmarks\reports\field_exact_*_f4_final.json`), com `training_pages` cruzado como o
  `cvoff-field` faz (antes o JSON dizia `contaminated 0` porque o `field_exact.py` não passava as
  páginas de treino — corrigido nesta fase):

  | régua | exportados | exp.-exatos | `field_exact` | contaminados (exp./exatos) | `n_clean` | `field_exact_clean` | viés |
  |---|---|---|---|---|---|---|---|
  | como anotado | 103 | 100 | 0,9709 | 14 (14/14) | 89 | **0,9663** (86/89) | +0,0046 |
  | corrigida | 103 | 102 | 0,9903 | 14 (14/14) | 89 | **0,9888** (88/89) | +0,0015 |

  As 6 páginas: Kemeri 80 (1) e 187 (1), Karpov 80 (6), Anand 62 (1), Yusupov 11 (2) e 14 (3);
  o Koblenz 50 (2 amostras) **não** está na lista porque a guarda pôs os seus rótulos em `test`.
  Os 14 contaminados saem todos exatos — o modelo lê o que treinou —, e é isso que o número
  limpo tira: o viés medido é pequeno (0,0015 na régua corrigida) e passa a ser dito em vez de
  suposto.
