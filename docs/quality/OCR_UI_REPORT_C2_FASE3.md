# OCR/UI · ciclo 2 — relatório do construtor (fase 3: modelo e ciclo fechado)

> **Data:** 2026-09-21 · **Plano:** `docs/OCR_UI_ROADMAP_C2.md` §3b (fase 3: C4, B10, C11, C5,
> C6, A11) · **Análise:** `docs/OCR_UI_ANALISE_C2.md` · **Fases anteriores:**
> `OCR_UI_REPORT_C2.md`, `OCR_UI_REPORT_C2_FASE2.md` · **Papel:** construtor. Todo número traz o
> comando ao lado. Ambiente: suíte `.venv` (Python 3.11.9, `torch 2.11.0+cu128`, RTX 5060),
> tronco `..\ChessVisionOFF_Puro` (3.10, `torch 2.10.0+cpu`). O treino da ablação do C4 correu na
> GPU pela venv da suíte sobre o código do tronco, em segundo plano durante toda a fase; os
> tempos (`s/MP`, `s/diagrama`, `wall_s`) carregam essa contenção e são ditos com ela.
> Commits: tronco **5fb2711**, suíte: o commit que grava este relatório (hash na mensagem do commit
> seguinte da suíte, que traz as sementes 43/44 e a sabotagem `i50` do §C4); um em cada, o hash do
> outro na mensagem.

## §0 — Em uma tela (o que o usuário passa a ter)

| antes | depois | portão | passo |
|---|---|---|---|
| o aumento dirigido (`mhsp`) nunca virou produção; nenhum aumento tocava a espessura do traço; a janela retreinava sempre no genérico; uma época custava 10 min mesmo na GPU | `RandomStroke` (letra `e`, **1 px** — 2 px fecha o contorno das brancas, medido); a ablação `aug0` × `mhsp` × `mhspe` × `e` do zero com a mesma semente e partição; a janela retreina no regime do checkpoint de produção; o cache do dataset com piso na janela do amostrador: **10,1 → 3,2 min/época** | `lab_gate` (teste 566): produção 555, `aug0` **556**, `mhsp` 555, `mhspe` 553, `e` 554 — ±3 tabuleiros; campo: `mhsp` ≈ `aug0` (3 exportados-e-errados), `mhspe`/`e` **4**; **nenhuma variante domina, nada a trocar**; a sabotagem `i` (3 %) foi **inerte** — vermelho, `i50` e sementes 43/44 na fila | C4 |
| a cifra do livro fixava a peça pela **primeira** observação, não tinha estilo nem janela; o `♕` do texto saía `♛` no DOCX/EPUB; a revisão não distinguia figurina lida de figurina inferida | maioria, estilo (classe de tamanho da linha) e janela de páginas, exemplos com confiança; `PieceGlyph` com `figurine_set` e proveniência própria; um span por figurina no `PageText` com a origem (`figurine_origin`: `glyph`/`tesseract_figurine`/`cifra`) | `notation_integrity --what contest`: Gaprindashvili **914 → 917** (de 986), Aagaard 157, Nunn 363, controles intactos; `cifra_plana` → 914 | B10 |
| o decodificador não sabia de bispos da mesma cor nem de reis adjacentes; o lance impresso sob o diagrama nunca voltava à posição | `DecodeRules` (bispos por cor de casa contam como promovidos; reis que se tocam); `lance_seguinte`: o primeiro lance impresso é jogado, e a troca única de segunda opção ou de cor que faz a linha fechar é adotada com o gate julgando as outras casas | `lab_gate` produção: `classic` 0,9770 → **0,9806** (`helped` 0 → 2, `hurt` 0); no campo `next_move_checked` **2** de 114 (população de 2, dito) | C11 |
| 10 das 27 casas erradas do campo eram de cor, 4 delas `q→Q` no Koblenz a 0,71–1,00, e nenhum sinal do softmax as movia | a tinta do centro da casa contra as damas/torres/... **corrigidas do mesmo livro**, por peça e cor de casa, só onde as cores se separam; o perfil do livro (`perfil.json`) como recipiente, ao lado da cifra | `field_exact`: exatos **103 → 105** (Koblenz: as damas de casa escura `p30 d0 d6` e `p50 d0 h4`; `colour_repaired_wrong` 0); `sem_cor` → 103; `cor_trocada` → 103 (o calibrador cala); fechamento do Koblenz um-de-fora: k=22 → **6 trocas, 6 certas** | C5 |
| corrigir → treinar era manual e ninguém pesava a correção; nada registrava que perfil/modelo/rótulos leram um livro | `caissa-fechar-ciclo <pdf>`: manifesto de calibração (texto), calibrador de cor (diagramas), páginas cegas **e de campo** retidas, antes/depois um-de-fora, identidade gravada, `perfil.proposto.json` → `perfil.json` só com `--aprovar` | Koblenz: 22 diagramas, 2 retidos (p. 50 é campo), 22 → 16 casas de cor erradas; decisão em página cega retida (teste) | C6 |
| o PGN perdia retângulo, hash do recorte, confiança por casa, reparos, modelo, perfil e decisão humana | `<nome>.proveniencia.jsonl` ao lado do PGN (tronco) e do EPUB/DOCX (suíte), chave `p<pág>:d<n>`, `[ProvenanceFile]`/`[ProvenanceKey]` no PGN; a colisão de chaves é acusada | item sintético exportado e relido inteiro; dois diagramas com a mesma FEN → dois registros; chave por FEN → `ColisaoDeProveniencia` (testes) | A11 |

### 0.1 O que a medição mudou no desenho (as armadilhas, cada uma medida)

- **`RandomStroke` a 2 px troca o rótulo.** A proposta dizia «erosão/dilatação 1–2 px». Olhando 36
  casas reais (Koblenz, Burgess, Euwe; `stroke_view.py`): com 2 px a fração clara dentro da
  caixa do glifo de uma peça branca cai de 0,84 (mediana) para 0,34, mínimo 0,04 — a torre
  branca em casa hachurada vira um bloco preto — e a erosão de 2 px apaga as pretas
  (preenchimento mínimo 0,03). Com 1 px: 0,84 → 0,57 (mínimo 0,20) e 0,34 → 0,32. Um pixel.
- **O treino estava preso no disco, não na GPU.** 9,7 min/época na RTX 5060 (a mesma marca do
  `EXPERIMENTS_FASE7.md` em CPU): o cache do dataset por processo era `128 ÷ (workers+1) = 25`
  tabuleiros para uma janela de 64 do `BoardGroupedSampler` — cada casa reabria o PNG de
  800×800. Com o piso na janela: 3,2 min (`loader_probe`, 400 lotes 111 → 35 s). A ablação de
  4 variantes × 16 épocas passou de 11 h para 2 h; o treino da janela herda o piso.
- **O calibrador de cor custou cinco versões, cada uma medida um-de-fora nos 22 Koblenz corrigidos**
  (`caissa.ocr.closing --max-diagramas`): (1) todas as peças juntas, quantis p5/p95 → 7 de 15
  trocas erradas — um rei branco que mede o p5 dos reis brancos é trocado por definição;
  (2) por tipo de peça → um cavalo branco (a crina escura, 159) e uma torre preta (as ameias
  claras) trocados; (3) extremos com margem de 10 → um cavalo branco com **4** amostras (o
  extremo de quatro não é o extremo da impressão: mínimo 5); (4) por tipo **e cor da casa**
  → uma torre branca a 151 em casa clara, abaixo da branca mais escura e *dentro* das pretas
  (136–224: as p. 46–48 do livro imprimem as pretas hachuradas, tão claras quanto as brancas)
  → a régua só fala onde as cores se separam. (5) *Como* se separam foi medido três vezes —
  extremos, mediana ± 2 MAD, e **aparada uma amostra de cada lado** — e as duas primeiras
  rodadas dessa medição ainda tinham os dois tabuleiros da página de campo no conjunto (o
  erro de base da página, abaixo): nelas o MAD calava as damas de casa clara e a aparada as
  salvava. **Com a retenção certa as três regras dão o mesmo um-de-fora: 6 trocas, 6 certas**
  (`scratchpad/loo_variants.py`). Fica a aparada — pelo teste sintético (uma dama preta
  hachurada a 218 não cala quatro a 117–142; duas fora, e a cor não separa), **por argumento
  e não por número**, e é o que o relatório diz. 0 trocas com k = 6 ou 12 (as damas não chegam
  a 5 por cor de casa).
- **O próprio tabuleiro não é amostra de si.** A primeira versão somava as casas seguras (≥ 0,98)
  do diagrama às do livro; no Stefaniu p100 pediu `b2 P→p` (peões brancos de casas escuras
  contra os de casas claras) e só a guarda de legalidade a segurou. Com a chave por cor de casa
  e o mínimo de 5, uma peça por lado nunca chega — tirado.
- **A primeira aprovação do perfil do Koblenz levou as duas amostras da p. 50** — página do conjunto
  de campo — e o `field_exact` teria medido o próprio perfil. `closing.field_pages_of` retém as
  páginas de campo como as cegas (o campo mede, nunca alimenta). **E a segunda também as levou:**
  o `labels.csv` do tronco grava `source_page` como a janela mostra, em **base 1** (o próprio
  tronco subtrai um em `labels.pages_with_training_samples`), e o conjunto de campo, o manifesto
  cego e as decisões da janela são base 0 — a retenção comparava `51` com `50`, retinha dois
  tabuleiros da p. 49 (índice) e deixava entrar os dois da página de campo. Apareceu ao listar as
  seis trocas do um-de-fora casa a casa (`p51 h4 Q→q` era o `p50 d0` do campo). Corrigido
  (`closing._page_index_of_label`, teste com o rótulo `13` contra a página de campo `13`), perfil
  apagado e aprovado de novo, campo remedido: os números de §C5 são com as duas regras.
- **A segunda opção de uma casa segura é ruído.** Na primeira versão do lance seguinte a busca
  tentava a segunda opção de qualquer casa: no teste sintético uma casa **vazia a 0,99** virava
  dama porque `♛xe5` fecharia — e dois candidatos empatavam. Hoje: segunda opção só onde o
  modelo hesitou (margem < 0,9), a **cor** da mesma peça em qualquer casa (é o erro que o campo
  mede), uma linha de um lance só confirma e nunca troca, e a linha tem de fechar até o 3.º
  lance impresso.
- **A maioria na cifra não moveu número.** O ganho de 914 → 917 precisa de estilo **ou** janela
  (cada sabotagem sozinha devolve 917, as duas juntas 914); a maioria (`cipher_majority`) sozinha
  não muda nada nestas páginas. Fica, porque as tabelas do corpus têm 13 símbolos cuja primeira
  observação era a errada (`'it` Q×3 contra K×26) e o formato 1 nunca os provaria — e o
  relatório diz que é por argumento, não por número.
- **O sidecar é um só para os dois PGNs.** Dois arquivos com a mesma chave seriam a colisão que
  `verificar` existe para acusar; o `.review.pgn` aponta para o mesmo sidecar, com o veredito
  por linha. O teste de retomada da exportação passou a normalizar o nome do sidecar (único
  header que difere entre `inteiro.pgn` e `retomado.pgn`).
- **Os dois Koblenz que ficaram exatos continuam barrados.** O gate julga `gate_confidence` (sem as
  casas trocadas por evidência externa), mas o decodificador de legalidade também reparou outras
  casas nesses diagramas — corretamente — e um reparo do decodificador nunca exporta (S-132,
  «custa 1 em 96», análise §9.2). `exported` 103 → 103 é isso, não o calibrador.

### 0.2 Invariantes e portões rodados na integração

| invariante / portão | resultado | comando |
|---|---|---|
| testes do tronco | **4.744 passaram, 4 pulados, 8 xfail, 1 desselecionado, 2 reprovaram** em 703 s (`trunk_tests.out`, com a máquina cheia): `test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote` (os três módulos novos — `cor_por_livro.py`, `lance_seguinte.py`, `proveniencia.py` — fora da árvore do README; **corrigido**, 39/39) e `test_strings::AccentTests` (de antes da fase, o mesmo da fase 2: `cabecas`/`configuracoes`/`pagina`/`SELECAO` em módulos que a fase não tocou); o desselecionado, `ImpressaoDaMedicaoTests::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje`, compara a impressão de código dos relatórios correntes de `docs/metrics/` do tronco com a de hoje e reprova sempre que o código muda sem aqueles relatórios serem remedidos — como na fase 2 | `..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --deselect tests/test_field_eval.py::ImpressaoDaMedicaoTests::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje` (o de antes da fase) |
| suíte de testes (com PyQt6) | **3.907 passaram, 10 pulados, 0 reprovaram** em 1.084 s (`suite_tests2.out`, com o treino do C4 ao lado); a primeira corrida inteira reprovou **1** — `test_corpus::test_a_scan_without_a_text_layer_is_read_by_default` (Sol §SOL-1), a origem da figurina no `engine` do span (§B10, §4 do roadmap): corrigido com `TextSpan.figurine_origin`; `test_arquitetura.py` à parte **19/19** | `PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py --ignore=tests\unit\ui\test_arquitetura.py`; `test_arquitetura.py` à parte |
| `bench_sol` + `sol_gate --report-only` no código da fase (5 estratos, 684 itens) | **CER e lances idênticos ao `f3_on` da fase 2 ao décimo de milésimo** (native 0,0237/0,9391, abst. 38; scan_clean 0,0058/0,9586; degraded 0,0256/0,8839; fax 0,0312/0,8283; bleed 0,0387/0,9345); silenciosas 0, **controles 0/9**, ordem 0,9917 (o `twocol:a:10` de sempre); nenhuma regressão de CER fora do IC contra o `baseline`; os portões absolutos (CER limpo ≤ 0,005, lances ≥ 0,998, inventados 0, ordem 1,0) continuam **bloqueados** como no ciclo 1. 800 s de parede com o treino do C4 e o `field_exact` correndo ao lado (o tempo não é comparável ao da fase 2; o CER é) — o texto da página não passa por nada desta fase além do B10, e o B10 não moveu um caractere fora das páginas do `contest` | `CAISSA_FIGURINE_TESSDATA=models\tessdata .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither --label fase3_on` (`benchmarks\reports\sol\fase3_on_20260921_062711.json`); `benchmarks\sol_gate.py --report-only benchmarks\reports\sol\fase3_on_20260921_062711.json` |
| `lab_gate` produção, regras do decodificador | `classic` 0,9770 (553/566, `helped` 0, `hurt` 0, ilegais 0) → C11 **0,9806** (555/566, `helped` 2, `hurt` 0, ilegais 0); acurácia por casa 0,999117 → 0,999172 | `.venv\Scripts\python.exe benchmarks\lab_gate.py --runs 3 --rules classic --tag c11_classic` (`lab_gate_20260921_053550_c11_classic.json`); `… --tag c11_rules` (`…_053625_c11_rules.json`) |
| `field_exact` antes da fase (`sem_evidencia`) | exatos 103, exportados 103, exportados-e-errados 3, `field_exact` 0,9709, reparadas 14; `next_move_checked` 0, `colour_repaired` 0 | `.venv\Scripts\python.exe benchmarks\field_exact.py --variant recall-pack --runs 3 --sabotar sem_evidencia --tag f3_sem_evidencia` (`field_exact_20260921_052319_f3_sem_evidencia.json`) |
| `git status --short` | só os caminhos da fase nas duas árvores (o `perfil.json` e o `perfil.proposto.json` do Koblenz vivem em `models/`, ignorado; o manifesto em `labeling/`, ignorado) | `git status --short` |

### 0.3 O que ficou vermelho ou aberto (honesto)

- **C11 (b) não tem população no campo.** Dos 114 diagramas do conjunto de campo, **2** têm uma
  linha de lances impressa sob eles (`next_move_checked` 2; `replayed` 0, `repaired` 0): são
  livros de problemas e de exercícios, cuja solução não está sob o diagrama. A sabotagem
  `lance_vizinho` é inerte pelo mesmo motivo. O mecanismo fica pelos 11 testes
  (`test_lance_seguinte.py`) e o `games_gate` continua com a cobertura 0,04 que a análise
  previu. A página de livro de partidas (Burgess `...♛xe5`) é o caso — e o Burgess e5 no
  campo não tem linha sob o diagrama (é uma "fonte" com a solução noutro lugar).
- **C5 só fala com perfil, e só o Koblenz tem perfil.** O calibrador precisa de ≥ 5 diagramas
  corrigidos com a mesma peça na mesma cor de casa **em cada cor**; k = 6 e 12 não chegam para
  as damas. Burgess (e5), Niemeijer (3 de cor) e Stefaniu (f1) não têm diagramas corrigidos
  fora das páginas de campo: o calibrador cala neles até alguém rotular e fechar o ciclo. É o
  ciclo C6 funcionando como desenhado, não um número que faltou medir.
- **C5 não exporta o que consertou.** Os dois Koblenz que ficaram exatos carregam reparos do
  decodificador de legalidade noutras casas (S-132). Mudar isso é mudar o gate, não o
  calibrador (o próprio `decode.py` diz onde).
- **C5 cala nas damas de casa clara do Koblenz.** As duas que sobram no campo (`p30 d1 e6` a 0,87,
  `p50 d1 d7` a 0,71) estão em casa clara, e a chave `Qc` do livro não separa: as damas pretas
  corrigidas em casa clara medem 133–218 (as das p. 46–48, hachuradas, 153–182) contra brancas
  176–211. O instrumento sem resolução se abstém; é o desenho, e está medido (§C5).
- **B10: +3 lances em 986, e nenhum nos outros dois livros.** O Aagaard e o Nunn não têm
  símbolos que o estilo ou a janela resgatem. A maioria fica por argumento (§0.1).
- **C4: nenhuma variante domina, e a sabotagem foi inerte.** A uma semente e 16 épocas as cinco
  variantes ficam a ±3 tabuleiros de 566 no laboratório e o `RandomStroke` exporta **mais** um
  errado no campo (4 contra 3); `i` a 3 % é indistinguível do `aug0` — o instrumento não tem
  resolução para a pergunta, e a decisão de trocar o `.pt` (§10.2) não tem número que a
  sustente: `models/piece_classifier.pt` não foi tocado. `i50` e as sementes 43/44 estão na
  fila e entram num commit seguinte da suíte (§C4).
- **O conjunto de campo já estava contaminado antes da fase** (Anand 62, Euwe 25/62, Yusupov 14,
  Kemeri 144 têm amostras de treino, `labels.pages_with_training_samples`); e sete rótulos novos
  da janela (Koblenz p. 50 ×2, 51 ×2, 10, 13; Aagaard 7) ainda **não têm split** — a ablação do
  C4 treinou com `assign_splits=False` para não os atribuir por baixo da outra sessão; dois deles
  (rotulados `51`: a página de campo de índice 50, §0.1) são da página de campo, e o próximo
  `cvoff-train` os poria em `train`.

## §C4 — `mhsp` + `RandomStroke`, com ablação

**Antes.** `AugmentConfig` tinha blur, jitter, afim, `hflip`, hachura, granulação, papel e
inversão; nada mudava a **espessura do traço** — e é nela que o campo erra cor (as pretas em
traço grosso, as brancas em contorno fino; análise §3.4). O `mhsp` da S-40 nunca virou
produção. A janela retreinava sempre em `AugmentConfig()`. Uma época custava 10 min na GPU.

**Depois.** Tronco: `augment.RandomStroke` (letra `e`; morfologia em `max_pool2d`, sem `cv2`
no `DataLoader`; **1 px** — com 2 px a fração clara dentro do glifo de uma branca cai de 0,84
para 0,34, mínimo 0,04, e a erosão apaga as pretas, preenchimento mínimo 0,03; medido em 36
casas do Koblenz, Burgess e Euwe antes de treinar), só no interior da casa (`stroke_margin_px`
3: grade e hachura vizinha não são glifo), na ordem `hflip → invert → stroke → paper → hatch →
speckle`; `from_letters`/`version_of_checkpoint` (a janela retreina no regime do checkpoint,
`TrainingRequest.augment`); `Trainer.prepare` com o cache do dataset por processo ≥ a janela do
amostrador (`BOARDS_PER_CHUNK`): **10,1 → 3,2 min/época** (`loader_probe`, 400 lotes 111 → 35 s).
Suíte: `benchmarks/c4_ablation.py` (do zero, mesma semente e partição, `assign_splits=False`,
16 épocas; `--variants aug0,mhsp,mhspe,e,i,i50`), `lab_gate --candidate … --unconstrained
--rules`, `field_exact --model`, `f4_field_failures --model`.

**Medição — treino (semente 42, 16 épocas, GPU; `c4_ablation.py --seeds 42 --epochs 16`,
`benchmarks/reports/c4_ablation/c4_<variante>_s42.json`).** 4.344 tabuleiros de treino, 535 de
validação (`splits.csv` de hoje: 14 Koblenz de 2026-09-20 estão em `train`, 3 em `val`, 1 em
`test`; os 7 rótulos sem split ficaram fora):

| variante | regime | melhor época | `val_board_exact` | `T` (S-28) | parede |
|---|---|---|---|---|---|
| `aug0` | blur/jitter/afim | 15 | 0,9664 (517/535) | 1,004 | 1.715 s |
| `mhsp` | + espelho, hachura, granulação, papel | 16 | 0,9664 (517) | 1,218 | 1.767 s |
| `mhspe` | + `RandomStroke` 1 px | 12 | 0,9682 (518) | 0,996 | 1.801 s |
| `e` | só `RandomStroke` | 8 | 0,9682 (518) | 1,174 | 1.588 s |
| `i` (sabotagem, inversão sem troca de rótulo a 3 %) | | 9 | 0,9626 (515) | 0,853 | 1.647 s |

Um tabuleiro de 535 separa as quatro variantes na validação. O laboratório e o campo:

| modelo | `lab_gate` teste 566, restrito (`c11`): exatos · casa · ilegais · `helped`/`hurt` | sem decodificador: exatos · ilegais | campo: exatos · exportados · exp.-exatos · **exp.-errados** · `field_exact` | casas de cor entre as erradas (`f4`) |
|---|---|---|---|---|
| produção (+ C5/C11) | **555** · 0,999172 · 0 · 2/0 | 553 · 3 | 105 · 103 · 100 · **3** · 0,9709 | 8 (3 Koblenz, 3 Niemeijer, Stefaniu, Burgess) |
| `c4_aug0_s42` | **556** · 0,999420 · 0 · 2/0 | 554 · 1 | 103 · 104 · 101 · **3** · 0,9712 | 5 |
| `c4_mhsp_s42` | 555 · 0,999144 · 0 · 2/0 | 553 · 2 | 104 · 105 · 102 · **3** · 0,9714 | 4 |
| `c4_mhspe_s42` | 553 · 0,999089 · 0 · 3/0 | 550 · 4 | 101 · 102 · 98 · **4** · 0,9608 | 8 |
| `c4_e_s42` | 554 · 0,999227 · 0 · 2/0 | 552 · 2 | 106 · 100 · 96 · **4** · 0,9600 | 4 |
| `c4_i_s42` (sabotagem) | **556** · 0,999365 · 0 · 2/0 | 554 · 2 | 104 · 101 · 98 · **3** · 0,9703 | 4 |

```
.venv\Scripts\python.exe benchmarks\lab_gate.py --runs 3 --unconstrained --tag c4_s42 --candidate ..\ChessVisionOFF_Puro\models\experiments\c4_aug0_s42.pt … --candidate …\c4_i_s42.pt   (lab_gate_20260921_064813_c4_s42.json)
.venv\Scripts\python.exe benchmarks\field_exact.py --variant recall-pack --runs 3 --model ..\ChessVisionOFF_Puro\models\experiments\c4_<v>_s42.pt --tag c4_<v>_s42   (field_exact_20260921_06{5137,5500,5821,…}_c4_<v>_s42.json)
.venv\Scripts\python.exe tools\f4_field_failures.py --barrados --model … --out scratchpad\f4_c4_<v>
```

**O que os números dizem (e o que não dizem).**

- **Nenhuma variante domina.** No laboratório as cinco ficam a ±3 tabuleiros de 566 da produção
  (`aug0` e a sabotagem `i` em 556, `mhspe` em 553), todas com 0 ilegais e `hurt` 0; no campo,
  `mhsp` ≈ `aug0` (+1 exato, +1 exportado, os mesmos 3 exportados-e-errados) e as duas
  variantes com o `RandomStroke` (`mhspe`, `e`) exportam **4** errados em vez de 3 e caem a
  0,960 — o `e` tem o maior número de exatos (106) e o menor de exportados (100): calibrado
  mais frio (`T` 1,17), barra mais. O ganho de 1 tabuleiro de validação do `mhspe`/`e` não
  sobrevive ao teste nem ao campo. **O portão do C4 não passou: nada a trocar** (§10.2 — a
  decisão é da pessoa, e estes números não a sustentam; `models/piece_classifier.pt` intacto).
- **A sabotagem foi inerte, e isso é vermelho.** `i` a 3 % (o que a letra `i` sempre foi) é
  indistinguível do `aug0` no laboratório (556 = 556) e no campo (4 casas de cor contra 5). Uma
  sabotagem que não piora não prova o instrumento: a ablação a uma semente e 16 épocas não tem
  resolução para separar «aumento que ajuda a cor» de «aumento que a estraga» — e o mesmo vale
  para o ganho que ela mediria. Fica na fila `i50` (inversão em metade dos lotes,
  `SABOTAGE_VARIANTS` no `c4_ablation.py`) e as sementes 43/44 de `aug0`/`mhspe` (a correr ao
  fechar este relatório; entram num commit seguinte da suíte, com os JSON).
- **Os candidatos leem as damas do Koblenz certas sem calibrador — mas não é o aumento.** Os 14
  Koblenz corrigidos em 2026-09-20 (p. 7–12, 46–47) entraram em `train`; o modelo de produção
  não os viu. Koblenz no campo: produção 0/4 exatos (2/4 com o C5), candidatos 1–4/4, todos
  incluindo o `aug0`. É o livro no treino, não o traço — o mesmo que
  `labels.pages_with_training_samples` conta por página, aqui por livro (páginas diferentes).
  O calibrador do C5 chega a 2/4 **sem** retreinar, e a comparação justa do aumento é
  candidato contra candidato (mesma partição), não contra a produção.
- **Todos os retreinados perdem um Niemeijer p. 20 inteiro** (27–28 casas: orientação; produção
  8 casas) e ele fica barrado nos seis. Não é do aumento (o `aug0` também) — é o orçamento de
  16 épocas contra o checkpoint de produção; fora do escopo, dito.
- **O achado que valeu a fase é o cache.** 25 tabuleiros por worker para uma janela de 64 do
  `BoardGroupedSampler` reabriam o PNG a cada casa; com o piso, a época caiu de 10,1 para 3,2 min
  e os cinco treinos couberam em 2,4 h. O treino da janela herda o piso.

**Sabotagem.** `i` (acima) — inerte a 3 %, registrada como vermelha. Testes: `test_augment.py`
+8 (o raio só entra com o traço ligado; engrossar escurece e afinar clareia; 1 px preserva o
vão do contorno sintético e **2 px o fecha**; a borda da casa fica como está; raio zero e
probabilidade zero são identidade; o sorteio usa o RNG do torch; e a ordem dos estágios
ajustada), `test_training.py` +1 (o cache por processo nunca fica abaixo da janela do
amostrador), `test_configuracoes.py` +1 (`RegimeDeAumentoTests`: o pedido de treino lê o
regime do checkpoint — `from_letters` é a inversa de `version`, e sem metadado cai em `aug0`).


## §B10 — Cifra com escopo, `figurine_set`, proveniência do `PieceGlyph`

**Antes.** `book_cipher.py` fixava `entry.piece` na primeira observação e contava as seguintes como
contradição para sempre; a chave era o símbolo puro; `_observe_glyph_swaps` descartava a
confiança do leitor; `_span_inlines` construía `PieceGlyph` sem `figurine_set` (→ `BLACK`, `♕` saía
`♛` no DOCX/EPUB) e sem proveniência; `to_page_text` colapsava a linha num `TextSpan` com a
confiança mínima e a origem da figurina só no `trace()`.

**Depois.** Formato 2 da tabela (`evidence: peça → fonte → n`, `by_style`, `recent`, `first_piece`,
exemplos com confiança; o formato 1 é lido e convertido); `proven(style=, window=, majority=)`
com três regras — a linha do estilo (classe de tamanho da linha contra o corpo da página:
`r`/`s`/`l`), a linha inteira, a linha sobre as últimas 6 páginas com observações; o serviço mede
o corpo da página (`body_size_of`) e o estilo de cada token trocado (`size_class`); a região é
validada com `book.proven(style=região)`. `PageText` sai com um span por palavra com figurina,
com a confiança da palavra e `figurine_origin` = `glyph` (leitor), `tesseract_figurine` (modelo
do livro) ou `cifra` (inferida) — o `engine` do span continua o OCR que leu as palavras, porque
a proveniência do bloco é do OCR (Sol §SOL-1/§SOL-10: `test_a_scan_without_a_text_layer_is_
read_by_default` acusou a primeira versão, que punha a origem no `engine` e fazia o parágrafo
sair `glyph+tesseract`); o importador dá ao `PieceGlyph` o conjunto que a página imprime e uma
`Provenance` própria (`note` diz quem leu ou inferiu).

**Medição** (as tabelas dos livros restauradas de um instantâneo antes de **cada** corrida, para
todas partirem do mesmo estado; `benchmarks/reports/b10_contest_*.json`):

| configuração | Gaprindashvili E8 (8 pág.) | Aagaard E1 (6) | Nunn E2 (6) | controles |
|---|---|---|---|---|
| antes (formato 1) | **914** / 986 | 157 / 204 | 363 / 472 | 0 alterados |
| depois (estilo + janela + maioria) | **917** / 986 | 157 | 363 | 0 alterados |
| `--sabotar cifra_estilo` | 917 | 157 | 363 | 0 |
| `--sabotar cifra_janela` | 917 | 157 | 363 | 0 |
| `--sabotar cifra_primeira` (sem maioria) | 917 | 157 | 363 | 0 |
| `--sabotar cifra_plana` (os três desligados) | **914** | 157 | 363 | 0 |

```
# antes: restaurar o instantâneo das tabelas e rodar
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what contest --json benchmarks\reports\b10_contest_antes.json
# depois e sabotagens (cada uma com as tabelas restauradas antes)
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what contest [--sabotar cifra_estilo|cifra_janela|cifra_primeira|cifra_plana] --json benchmarks\reports\b10_contest_<x>.json
```

O `antes` desta fase é 914, e não os 891 do ciclo 1: as tabelas cresceram com as importações das
fases 1 e 2 (a de Gaprindashvili tem 416 símbolos). Testes: `test_book_cipher.py` 15 (6 novos:
formato 1 lido com a evidência, maioria, janela por páginas, estilo, `size_class`/`body_size_of`,
exemplos com confiança), `test_glyph_engine.py` +1 (o estilo de cada token e a sabotagem
`cipher_style=False`), `test_figurine_provenance.py` 3 (conjunto, proveniência, spans).

## §C11 — Restrições do decodificador e o lance seguinte

**Antes.** `decode._find_violations` sabia de reis (= 1), peões fora da 1.ª/8.ª, ≤ 8 peões, ≤ 16
peças e o excesso de promoção. Não sabia de bispos do mesmo lado em casas da mesma cor nem de
reis adjacentes. O primeiro lance impresso sob o diagrama era lido (`pdf_text.first_move_number`,
passo 7) só para o lado a jogar.

**Depois.** (a) `DecodeRules(bishop_colors=True, adjacent_kings=True)`: o lado começa com um bispo
claro e um escuro, logo `max(0, claros−1) + max(0, escuros−1)` bispos vieram de peões — a conta
entra em «promovidas demais para o número de peões» **sem** contar duas vezes o que a contagem
por tipo já contava; reis que se tocam são violação, com as duas casas como candidatas. (b)
`pdf_text.DiagramContext.first_moves_text` guarda a linha inteira; `lance_seguinte.conferir` a
joga sobre a leitura com `text.notacao.validar` (número de lance conferido, figurinas
traduzidas); se não fecha, tenta a segunda opção das casas hesitantes (margem < 0,9, até 6) e a
outra cor de cada peça lida, uma troca e depois duas, e adota a troca **única** que faz a linha
fechar até o 3.º lance impresso (uma linha de um lance só confirma). `RecognizedDiagram` e
`DiagramPosition` carregam `next_move`, `next_move_replays`, `next_move_repairs`; a casa trocada
fica com a confiança da matriz e o gate julga as outras (`gate_confidence`, em `field_eval` e em
`pdf_to_pgn.classify_position`); o PGN ganha `[OCRNextMove]`.

**Medição.**

| portão | antes | depois | comando |
|---|---|---|---|
| `lab_gate` produção, split `test` (566 tabuleiros), restrito | `classic`: exatos **0,9770** (553), casa 0,999117, ilegais 0, `helped` 0, `hurt` 0 | C11: exatos **0,9806** (555), casa 0,999172, ilegais 0, `helped` **2**, `hurt` **0** | `benchmarks\lab_gate.py --runs 3 [--rules classic]` (`lab_gate_20260921_053550_c11_classic.json`, `…_053625_c11_rules.json`) |
| `field_exact` (b) | — | `next_move_checked` **2** de 114, `replayed` 0, `repaired` 0, `ambiguous` 0 (`f3_on`); `--sabotar lance_vizinho`: idêntico — inerte (§0.3) | `benchmarks\field_exact.py --variant recall-pack --runs 3 [--sabotar sem_lance|lance_vizinho]` |
| `games_gate` | cobertura 0,04 | inalterado (nenhum diagrama do campo com linha sob ele que o mecanismo tocasse) | `benchmarks\games_gate.py` |

Os dois tabuleiros que o C11 (a) ganha no laboratório são os dois em que a leitura tinha um
par de bispos brancos na mesma cor com os oito peões (`decoder_helped` 0 → 2) — nenhum
tabuleiro que o argmax acertava foi estragado (`hurt` 0). Testes: `test_decode.py` +8 (bispos
com todos os peões → reparo; com um peão a menos → nada; três bispos não contam duas vezes;
reis que se tocam → o par de trocas mais barato; `CLASSIC_RULES` deixa passar), `test_lance_
seguinte.py` 11 (replica; sem lance; a dama de d6 provada por `...♛xe5`; a linha que para no 3.º
lance não troca; o lance do vizinho não troca; a casa vazia a 0,99 nunca vira dama; a cor de
uma peça segura pode trocar; um lance só confirma; empate não troca; `prediction_with_squares`
mantém a matriz; `apply_next_move` pelo contexto), `test_field_eval.py` +2 (o gate julga
`gate_confidence`; os contadores).


## §C5 — Calibrador de cor por livro, dentro do perfil do livro

**Antes.** Das 27 casas erradas nos 114 diagramas do campo, 10 eram a mesma peça na outra cor —
4 delas `q→Q` no Koblenz a 0,71–1,00 (análise §3.1) — e nenhum sinal do softmax as movia: uma
casa a 1,00 não tem temperatura, TTA nem protótipo que a mova (§9.1). O perfil por livro não
existia; a cifra vivia sozinha em `models/tessdata/livros/<livro>/`.

**Depois.** Tronco, `cor_por_livro.py`: a **tinta** do centro da casa (média de cinza dos 40 %
centrais, `medir`; `VERSAO_DA_MEDIDA = "centro40-v3"`) contra as amostras das peças
**corrigidas do mesmo livro**, guardadas **por tipo de peça e cor da casa** (`chave_da_amostra`:
`"Qe"` é uma dama em casa escura — a casa escura de um livro hachurado escurece o centro de
qualquer peça). `CalibradorDeCor.decidir` fala só com ≥ 5 amostras de cada cor na chave
(`MINIMO_POR_COR`), só quando as duas cores se separam aparada uma amostra de cada lado
(`_aparadas`), e só além dos extremos da outra cor com 10 níveis de folga (`MARGEM`) e não
além do que a própria cor mostra; fora disso, `Veredito(None)`. `trocas_de_cor` só olha a casa
em que o par `(X, x)` domina (`PAR_DOMINA` 0,90: a dúvida é *só* de cor); `apply_colour` aplica
as trocas por `inference.prediction_with_squares` (a matriz fica; `decode.changed_squares`
acumula), desfaz tudo se a posição trocada ficasse fatalmente ilegal, e devolve o motivo em
pt-BR (`cor pela tinta (perfil do livro, 22 diagramas): d6 Q→q (138 fora de 159–171, 8+8
amostras)`, o `p30 d0` do campo). As células são as que o modelo viu (`cells_as_read`: giradas
a 180° e invertidas no ponto de vista das pretas). A troca é reparo com **evidência externa**:
`RecognizedDiagram.colour_repairs`/`colour_reason`, `external_repairs`, e o gate julga
`gate_confidence` (as outras casas), como no lance seguinte; `[OCRColour]` no PGN,
`colour_repairs` no sidecar (A11). Sem
perfil, o calibrador **cala** (`calibrador_do_livro` → `caissa.ocr.book_profile.colour_for_pdf`,
importação guardada: o tronco sem a suíte lê como antes). Suíte, `ocr/book_profile.py`:
`BookProfile` (`perfil.json` ao lado da cifra: `fingerprint` do PDF, `model_identity`,
`dataset_version`, `ocr_config`, `colour`, `history` de `ClosureRecord`), gravado só pelo
fechamento com `--aprovar` (C6); `field_exact --sabotar sem_cor|cor_trocada` e `--perfil`;
`f4_field_failures --sem-cor|--perfil` com `colour_repairs`/`colour_reason` por diagrama.

**Medição.** Um-de-fora nos 22 Koblenz corrigidos (§C6): **6 trocas, 6 certas** — seis damas
brancas lidas a 0,94–1,00 em casa escura que a tinta (119–142) diz pretas contra a zona
159–171 da chave `Qe`; com k = 6 ou 12 as damas não chegam a 5 por cor de casa e o calibrador
cala. No campo (`benchmarks\field_exact.py --variant recall-pack --runs 3 [--sabotar …]`,
perfil aprovado de `caissa.ocr.closing … --aprovar`, páginas cegas e de campo retidas — §0.1):

| configuração | exatos (114) | acima do gate / exportados | exportados-e-errados | `colour_repaired` (casas · certas · erradas) | relatório |
|---|---|---|---|---|---|
| `sem_evidencia` (antes da fase) | 103 | 103 / 103 | 3 | 0 · 0 · 0 | `field_exact_20260921_052319_f3_sem_evidencia.json` |
| `sem_cor` | 103 | 103 / 103 | 3 | 0 · 0 · 0 | `…_053038_f3_sem_cor.json` |
| **`f3_on`** | **105** | 103 / 103 | 3 | **2 · 2 · 0** | `…_062424_f3_on.json` |
| `cor_trocada` (brancas ↔ pretas no perfil) | 103 | 103 / 103 | 3 | 0 · 0 · 0 | `…_062832_f3_cor_trocada.json` |

As duas trocas são as damas de casa escura do Koblenz — `p30 d0 d6 Q→q` (lida `Q` a **0,996**,
tinta 138) e `p50 d0 h4 Q→q` (**0,994**, tinta 118) — as duas casas mais seguras entre as
erradas do campo, que nenhum sinal do softmax moveria, e os dois diagramas ficam **exatos**
(Koblenz 0 → 2 de 4). Continuam barrados: os dois carregam reparos do decodificador de
legalidade noutras casas (`g8 q→k`, `c2 K→Q`; `g8 K→k`), e reparo do decodificador não exporta
(S-132, §0.3) — por isso `exported` e `exported_wrong` não se movem, e `field_exact` fica
0,9709. As outras duas damas do livro no
campo, `p30 d1 e6` (0,87) e `p50 d1 d7` (0,71), estão em **casa clara**, e a chave `Qc` do
perfil não separa: as damas pretas corrigidas em casa clara medem 133–218 (as das p. 46–48
da janela, hachuradas, 153–182) contra brancas 176–211 — a régua cala (§0.3). O `p30 d1` tem
ainda um `f3 Q→K` a 0,999 (tipo, não cor) que arrasta `g6` e `g1` pelo decodificador: não é
deste passo. `colour_repaired_wrong` **0** em todas as configurações; Burgess (`e5`),
Niemeijer (3 de cor) e Stefaniu (`f1`) não têm perfil e ficam como estavam. Os `s/diagrama`
(0,59 → 0,83 no `f3_on`) são o treino do C4 na GPU e o `bench_sol` correndo ao lado — a
medida da tinta custa uma média por casa.

**Sabotagem.** `--sabotar cor_trocada` troca as amostras brancas pelas pretas no perfil: as duas
cores deixam de se separar em toda chave (a preta mais clara aparada passa a ser a branca mais
escura) e o calibrador **cala** — exatos 105 → 103, 0 trocas, nenhuma casa certa virada; a
guarda de separação é o que impede protótipos invertidos de estragar leituras certas.
`--sabotar sem_cor` → 103: os dois exatos são do calibrador. Testes: `test_cor_por_livro.py` 15
(a chave é a peça na cor da casa; a medida é o centro e não o fundo; a branca mais escura é o
piso e não um quantil; além dos extremos com margem, abstenção no vão; distribuições
sobrepostas não são régua; outra peça não é régua desta; sem amostras de uma cor abstém;
serializa e recusa outra medida; uma amostra de outra impressão não cala as outras, duas
calam; a amostra do livro decide, e só a da mesma chave; `apply_colour` troca, registra e
desfaz a posição ilegal; o livro troca a cor que a tinta contradiz; sem perfil nada troca; só o
par dominando a casa é julgado; as casas medidas são as que o modelo viu), `test_field_eval.py`
(contadores `colour_*`), suíte `test_closing.py` (o perfil só muda com `--aprovar`; página
cega e de campo retidas; a base da página do `labels.csv`).


## §C6 — Fechar o ciclo

**Antes.** `ocr/review.py` persistia decisões e `corrections()` devolvia pares; recalibrar e
retreinar eram manuais; nada registrava que modelo, rótulos ou perfil leram um livro.

**Depois.** `caissa.ocr.closing.close_cycle(pdf)` / `caissa-fechar-ciclo <pdf> [--aprovar]
[--max-diagramas K] [--sem-medir]`:

1. **texto** — as linhas decididas do projeto de rotulagem (`calibration_pairs`, confiança por
   palavra) e as regiões da fila de revisão (`ReviewQueue.corrections`, score da região — o item
   não guarda confiança por palavra, e a linha do manifesto diz `granularity`) viram
   `labeling/fechamento/<livro>_<data>.jsonl`, com um cabeçalho de identidade; páginas cegas
   retidas e contadas;
2. **diagramas** — as linhas de `labels.csv` do tronco deste livro com procedimento humano
   (`ocr-aceito`, `ocr-corrigido`, `transcricao-manual`, `segunda-opiniao`; a linha sem
   procedimento é legado e não entra; `source_page` é base 1 e vira índice, §0.1) e as decisões
   da janela (`DiagramDecisions`, com um `render` que recorta a página) →
   `cor_por_livro.amostras_do_tabuleiro` por peça e cor de casa → `CalibradorDeCor`; páginas
   cegas **e as do conjunto de campo** retidas;
3. **antes/depois**, um de fora de cada vez: cada tabuleiro lido pelo classificador de produção
   sem calibrador e com o calibrador dos outros; exatos, casas de cor erradas, trocas e acertos;
4. **identidade** — `checkpoint_fingerprint` do `.pt`, SHA-256 dos pares `(arquivo, FEN)` de
   `labels.csv` (a regra do `labels_hash` do tronco), hash do PDF, commit da suíte;
5. `perfil.proposto.json` sempre; `perfil.json` só com `--aprovar`, com um `ClosureRecord` no
   histórico.

**Medição** (Koblenz; `benchmarks/reports/c6_fechamento_koblenz*.json`):

| k (diagramas corrigidos, fora do campo) | amostras (brancas/pretas) | antes: exatos / casas de cor erradas | depois | trocas (certas) |
|---|---|---|---|---|
| 6 | 36 / 38 | 0/6 · 8 | 0/6 · 8 | 0 |
| 12 | 60 / 51 | 1/12 · 11 | 1/12 · 11 | 0 |
| 22 (todos; 2 retidos: a página de campo 50) | 152 / 150 | 1/22 · 22 | **1/22 · 16** | **6 (6)** |

```
.venv\Scripts\python.exe -m caissa.ocr.closing "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\Koblenz - El dominio del arte de la combinacion (1978).pdf" --max-diagramas 12 --json benchmarks\reports\c6_fechamento_koblenz_k12.json
.venv\Scripts\python.exe -m caissa.ocr.closing "…Koblenz….pdf" --aprovar --json benchmarks\reports\c6_fechamento_koblenz.json
```

Os 22 Koblenz corrigidos são as páginas 7–13 e 46–50 da janela (índices 6–12 e 45–49), lidas
hoje pelo modelo de produção com **1 exato em 22 e 22 casas de cor erradas** — é o livro em que
o campo erra cor, e por isso a régua foi afinada nele (§0.1: cinco versões, todas medidas
assim). Com k ≤ 12 as damas não chegam a 5 amostras por cor de casa e o calibrador cala; com
22 troca 6 e acerta 6 — as seis são damas brancas lidas a 0,94–1,00 em casa escura que a
tinta diz pretas (índices p6 `c1` 136, p6 `f6` 139, p7 `f8` 142, p8 `d8` 128, p46 `d4` 133,
p49 `e7` 119, contra a zona 159–171 da chave `Qe`; `scratchpad/loo_detail.py`). As casas de
cor que sobram: reis (`k→K` lidos a 0,00–0,57, que o decodificador de legalidade recoloriu —
o par `(K, k)` não domina essas casas ou a tinta cai na zona), a dama de p45 `e7` (0,74, tinta
161 dentro de 159–171), dois peões de p45 `b5` (207–209 dentro de 199–240: a impressão
hachurada) e as torres de p47 (dentro de 147–169). Nenhum exato a mais no um-de-fora: os
tabuleiros que ganham a dama continuam com um rei recolorido.

**Sabotagem.** `test_a_blind_page_and_a_field_page_contribute_nothing` (uma linha de `labels.csv`
numa página cega e outra numa página de campo: retidas e contadas; sem a guarda entram) e
`test_text_corrections_become_calibration_pairs_minus_the_blind_page` (a decisão gravada por
um arnês numa página cega é retida pelo fechamento mesmo que a fila a tenha aceito).
`test_closing.py` 5; o perfil não muda sem `--aprovar`
(`test_close_cycle_writes_a_proposal_and_only_approval_writes_the_profile`).


## §A11 — Sidecar de proveniência

**Antes.** O PGN do tronco gravava `SourcePDF`, `Page`, `Diagram`, `OCRMinConfidence`,
`SideToMoveSource`, `DetectionSource`, `OCRProblems`, `OCRRotation`; o retângulo, o hash do recorte,
a confiança das 64 casas, os reparos, o modelo, o perfil e a decisão humana morriam na exportação.
No IR da suíte tudo isso existia (`DiagramSource`, `RecognitionResult`, `verified_by_human`) e os
exportadores imprimiam o tabuleiro.

**Depois.** Tronco: `DiagramPosition` ganha `bbox_pdf`, `image_hash` (`provenance.hash_board_rgb`),
`square_confidences`, `repairs` (o parcial da exportação os serializa); `write_gated_pgn(provenance=
Cabecalho(...))` grava `<nome>.proveniencia.jsonl` — cabeçalho (PDF e seu SHA-256, modelo, perfil do
livro quando a suíte está importável, gate, DPI, data) e uma linha por diagrama (aceitos, revisão,
rejeitados e repetidos, com o veredito e o motivo) — e os dois PGNs apontam com `[ProvenanceFile]`
e `[ProvenanceKey "p<página>:d<índice>"]`, a chave do `[Diagram]`. `proveniencia.read_sidecar`
relê e `verificar` acusa chave repetida (`ColisaoDeProveniencia`). Suíte: `export/provenance.write_
sidecar(document, saída)` faz o mesmo ao lado do EPUB/DOCX a partir do IR — uma linha por
`Diagram` (recorte, hash, `content_hash`, DPI, FEN, orientação, `verified_by_human`, a leitura da
máquina com 64 confianças, reparos, alternativas, avisos, a `Provenance` do nó) e por `GameScore`
(posição inicial, lances, proveniência), com o ULID do nó ao lado da chave; `export_book` o grava
sempre (`BookExportResult.provenance_path`; uma falha é aviso, nunca perde o livro).

**Medição.** Exportação real do Koblenz p. 30 (`save_pdf_positions_to_pgn(pdf, saída,
start_page=30, end_page=31)`): 2 diagramas em revisão, sidecar com cabeçalho
`{"source_hash": "0b7ab7…", "model_identity": "8786520-…", "profile": {"closures": 1,
"colour_diagrams": 22, …}, "accept_threshold": 0.8, "dpi": 220}` e as linhas `p30:d1`
(retângulo `[61, 226, 215, 380]`, hash `599d5994…`, `colour_repairs ["d6"]`, reparos
`[g8 q→k, c2 K→Q, d6 Q→q]`, `gate_confidence 0,004`) e `p30:d2`; o `.review.pgn` traz
`[OCRColour "tinta trocou d6"]`, `[ProvenanceFile "…proveniencia.jsonl"]` e `[ProvenanceKey "p30:d1"]`.
Testes: `test_proveniencia.py` 5 (o PGN aponta e o sidecar carrega o que o header não cabe; sem
cabeçalho não há sidecar; item sintético exportado e relido inteiro; **a mesma FEN em duas páginas
são dois registros e a chave por FEN colide, com as duas páginas na mensagem**; sidecar com chave
repetida é recusado na leitura), `test_provenance_sidecar.py` 3 (o mesmo pelo IR).

