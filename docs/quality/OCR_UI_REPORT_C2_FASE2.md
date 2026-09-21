# OCR/UI · ciclo 2 — relatório do construtor (fase 2)

> **Data:** 2026-09-21 · **Plano:** `docs/OCR_UI_ROADMAP_C2.md` §3 (fase 2: B1, B2, B3, B5, B6,
> B8, B9, C2, C3, C8, C9, C10) · **Análise:** `docs/OCR_UI_ANALISE_C2.md` · **Fase 1:**
> `OCR_UI_REPORT_C2.md` · **Papel:** construtor. Todo número traz o comando ao lado. Ambiente:
> suíte `.venv` (Python 3.11.9), PyQt6 do `.venv-pack`, tronco `..\ChessVisionOFF_Puro` (3.10),
> commit **2077410** (o da suíte é o que traz este relatório).
> Construída por **uma sessão, passo a passo**, com os benchmarks rodados em sequência (a
> primeira rodada, feita em paralelo com testes e portões, contaminou o `s/MP` e foi descartada).

## §0 — Em uma tela (o que o usuário passa a ter)

| antes | depois | portão | passo |
|---|---|---|---|
| página digitalizada em duas colunas lida como linhas de 2.300 px atravessando a calha (`twocol` CER 0,1251 no `f2_before`) | as colunas são achadas nas caixas de palavra da leitura inteira e lidas em ordem: `twocol` CER **0,0108 (`scan_clean_300`) e 0,0589 → 0,0173 (`scan_degraded_150`)**; `scan_clean_300` inteiro 0,0275 → **0,0058** | `bench_sol` A/B; sabotagem `scan.enabled=false` devolve 0,1249 | B1 |
| o perfil de lances do Tesseract só rodava em região ≥ 50 % lances (nunca numa página mista) | cada corrida de linhas com notação vira faixa lida com o perfil `MOVETEXT`, candidato secundário da fusão | `bench_sol` por gênero; sabotagem `movetext_strips=false` | B2 |
| nenhum NAG sobrevivia à via PDF → `GameScore` | `MoveNode.nags` sai da cauda do lance (`!?`, `±`, `²`→`⩲`, `⨀` pelo lado); apelidos `⇄ △ ⊕ ◻` | `notation_integrity --what nags`: 6 nós com NAG em 9 partidas; `--sabotar nags` → 0 | B3 |
| âncora abstida a 0,40 jogava fora um fundido que o leitor de glifos leu a 1,00 | âncora abstida + secundário independente concordando em ≥ 2 lances → o fundido é re-pontuado e vai à **revisão** (nunca aceito) | `bench_sol native`: abstidos 62 → 38 (24 regiões vão à revisão, 11 delas com CER ≤ 2 %); controles 0/9 | B5 |
| a fusão comparava confianças cruas de motores incomparáveis | as tabelas calibradas do SOL-4 põem Tesseract e RapidOCR na mesma escala antes de qualquer limiar | `bench_sol`; sabotagem `fusion.calibrated=false` | B6 |
| `register_verso` implementado, nunca chamado | páginas vizinhas do PDF (e o espelho) registradas; a melhor vira a variante `bleed_verso`, ao lado da heurística — **desligada por padrão, por medição** (`use_verso=False`) | `bench_sol shadow_curl_bleed` ligado × desligado: CER 0,0399 × **0,0387**, inventados 10 × 8 | B8 |
| variantes × motores × perfis em série; Tesseract de 180 s incancelável; cancelamento só entre páginas | candidatos independentes em 4 threads (ordem preservada); o gancho de cancelar chega ao `Popen` do Tesseract e o mata; `OcrCanceled` → `ImportCanceled` com o parcial | `s/MP` `workers=4` × `1`: `scan_clean_300` 1,41 → 1,26 s/MP, `scan_degraded_150` 9,21 → 7,34; 274 itens byte-iguais; testes de morte do filho e do importador | B9 |
| «Ler a página»: sem barra, sem Cancelar, painel inteiro cinza, primeiro clique paga o modelo | registrada no rodapé com total; Cancelar entre diagramas (o lido fica); só o gravar tranca; o modelo aquece ao abrir o livro; `.pt` ausente diz onde apontar | `audit.progresso` sem defeito; `percurso --cancelar` PASSOU (53 ms, «cancelada antes do primeiro diagrama»); `--sabotar sem_cancelamento` REPROVOU; `--frio` 0,58–0,64 s (3×) com o aquecimento; 1,98–2,17 s sem; `bloqueio` 3/3 PASSOU | C2 |
| segunda opinião morta desde o corte do Tk; a preferência prometia | botão «Segunda opinião» (leitor tsoj, outra família): casas em disputa marcadas, posição adotada desfazível, `corrected_by=segunda-opiniao` | `second_opinion_gate`: **23/27 casas erradas cobertas (85,2 %)**, mediana 2 em disputa; `--sabotar copia` 0/27 | C3 |
| trilho não aprendia; só «primeira duvidosa»; hesitação não contava; tabuleiro sem teclado | hesitantes na conta e corrigidos fora dela (`atualizar_trilho` ao gravar); próxima/anterior duvidosa (`Ctrl+PgDn/PgUp`); `Tab` + letra corrige uma casa em 2 teclas; as abas da suíte no catálogo (0 atalhos ambíguos) | `percurso --teclado` PASSOU — 2 teclas (1 `Tab` + a letra); `--sabotar sem_teclado` REPROVOU (9 teclas, casa não corrigida); `audit.comandos` PASSOU (424 medidos, 0 soltos, 0 que prometem) | C8 |
| abas da suíte com Tailwind cravado, `Consolas`, `◀`; pares não medidos | cada cor é um papel de `caissa.ui.theme.pele` → token do tronco no cromo em vigor; 8 pares no portão de contraste | `audit.contraste` 308 pares/228 sob portão PASSOU; `--sabotar` REPROVOU | C9 |
| `CoordinateRule` calava (ninguém produzia `BoardCoordinates`); vetorial não girava o `placement` | as coordenadas são lidas (tronco e suíte); ponto de vista das pretas gira a **FEN**, nunca a imagem; a tela desenha o tabuleiro virado para bater com o recorte | `coordinate_survey`: 46 livros, 10.639 linhas `a-h` e **0** `h-a`; espelhado → 0 e 10.639; testes com fixture do lado das pretas + espelho | C10 |

### 0.1 O que a integração e as medições mudaram (as armadilhas, cada uma medida)

- **B2 anexava e ancorava.** A primeira versão das faixas saía com `engine="tesseract"` e podia
  ganhar o assento de âncora: uma região virava só as linhas das faixas (`twocol:d:12` CER 0,0016
  → 0,68, REVIEW → ACCEPTED; `Euwe 82:352` 0,03 → 0,91). Hoje é `tesseract_strips`,
  `secondary=True` — só troca um token que a âncora duvidou.
- **B1 fatiava a leitura, não os candidatos.** No modo fatia a arbitragem é partilhada, e os
  candidatos dos outros motores eram de **página inteira**; um deles, acima da fatia no
  ranking, ancorava a região com a página toda (Dvoretsky `17:401:52` CER 0 → 0,76: cada região
  repetindo o texto inteiro). `PageRecognizer._slice` corta cada candidato à região.
- **Tabela e lista de lances têm calha limpa.** `table:2` (3 faixas, cada linha com entrada em
  cada faixa) CER 0,0036 → 0,47 e a lista brancas | pretas do Dvoretsky `18:179:252` 0 → 0,62.
  Duas guardas: `max_columns=2` e `min_band_chars=16` (coluna de prosa 40–70 caracteres por
  linha; coluna de lances 4–10).
- **Reler por região perde para fatiar.** `scan_reread=True` (PSM 6 no recorte de cada coluna):
  CER 0,0206 em 66,3 s; fatiar a leitura inteira: 0,0111 em 42,5 s (26 `twocol` de
  `scan_clean_300`, `probe_sol.py`). O recorte apertado da coluna perde para as palavras que o
  Tesseract já leu com o contexto da página. Fatiar é o padrão; reler fica como opção.
- **Uma página multi-região com uma região em revisão é uma página em revisão.**
  `PageRecognition.decision` devolvia a melhor região (ACCEPTED) e `below_threshold` True → o
  `sol_gate` contava "importação silenciosa" (4 no primeiro `f2_on`). Agora REVIEW propaga.
- **O verso real não domina.** Medido diagrama a diagrama no `shadow_curl_bleed` (`probe_verso.py`):
  o verso registrado ganha em `authored:ru:15` (0,178 → 0,099) e `ru:17` (0,148 → 0,092) e
  perde em `ru:14` e `Xadrez Vitorioso 156` — a curvatura derrota o registro global. Por isso
  `bleed_verso` é **mais uma** variante, e o árbitro escolhe por região.
- **A primeira rodada de benchmarks foi descartada** (rodada em paralelo com o portão B3 e
  com `test_busy`; `scan_degraded_150` saiu a 12,3 s/MP contra 6,7 no antes).
- **As setas do tabuleiro (C8) não chegavam ao widget na janela de verdade.** `←`/`→` e `Del`
  são atalhos globais (`ui/atalhos.py`: diagrama anterior/próximo, `apagar_casa`) e a guarda
  de atalhos é um filtro **na aplicação**, que vê a tecla antes do widget em foco. O teste do
  widget sozinho passava; a suíte inteira do tronco o reprovou (qualquer teste anterior que
  tivesse ligado a guarda a deixava viva). A saída é a da S-244: o tabuleiro em foco **toma
  para si** as três ações (`DonoDeAcoes`: `acoes_proprias`/`atender`) — a seta anda uma casa
  aqui e continua trocando de diagrama com o foco em qualquer outro lugar. Teste com a guarda
  ligada + sabotagem (sem `acoes_proprias` a janela fica com a seta e a seleção não sai do
  lugar). O portão `--teclado` (Tab + letra) não passava por aí, e é por isso que não pegou.
- **C10: o recorte não virava com o tabuleiro.** No ponto de vista das pretas a casa canônica
  `i` está impressa em `63 − i` — a mesma relação da leitura de cabeça para baixo —, mas o
  recorte virava só por `rotation == 180`: a tinta, o apontar e o clique no recorte caíam na
  casa espelhada. Achado na revisão do próprio construtor **antes** de chamar o crítico
  (2026-09-21, tronco 167d52d); `recorte.mostrar(virado=pretas)` e
  `PontoDeVistaDasPretasTests` (2: o tabuleiro e o recorte viram juntos e a posição fica
  canônica; de pé e das brancas nada vira).
- **A suíte inteira do tronco travava em `test_app_pyqt`** (não reprovava: **travava**). O
  serviço falso do arquivo não aceitava `progress=`/`should_cancel=` → `TypeError` → `_falhou`
  → `dialogos.mostrar_falha`, uma caixa **modal** que ninguém fecha num teste headless. Visto
  com `-o faulthandler_timeout`; o fake acompanha a assinatura de `recognize_page`.

### 0.2 Invariantes e portões rodados na integração

| invariante / portão | resultado | comando |
|---|---|---|
| suíte de testes (com PyQt6) | **3.882 passaram, 10 pulados, 1 reprovou** em 752 s (`suite_tests.log`) — o reprovado era o realce verde do C9 (`test_revisao_de_texto_view`, §C9): corrigido, 24/24 no arquivo e 12/12 com o tronco no caminho; `test_arquitetura.py` à parte **19/19** (a fronteira `ui/` sem toolkit vale para o `ui/teclado_do_tabuleiro.py` novo do tronco) | `PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py`; `test_arquitetura.py` à parte |
| testes do tronco | **4.687 passaram, 4 pulados, 8 xfail, 2 reprovaram** em 482 s (`trunk_tests2.log`) — os dois reprovados são os de antes da fase (`test_field_eval::ImpressaoDaMedicaoTests`: relatórios de campo mediram código anterior; `test_strings::AccentTests`: `cabecas`/`configuracoes`/`pagina`/`SELECAO` em módulos que a fase não tocou). A primeira corrida **travou** em `test_app_pyqt` (caixa modal do `_falhou`, §0.1) e a segunda reprovou `TecladoTests::test_setas_andam` (a guarda de atalhos, §0.1), `test_docs` (a contagem de threads: 18 → 20, `ARCHITECTURE.md`) e `test_editor_model::SemTkinterTests` (`teclado_do_tabuleiro.py` na lista) — os quatro corrigidos | `..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q` |
| `sol_gate --report-only` sobre o `f2_on` | 0 importações silenciosas, **0/9 controles**, nenhuma regressão de CER fora do IC em estrato algum (native 0,0921 → 0,0237, scan_clean 0,0330 → 0,0058, degraded 0,0454 → 0,0256, fax 0,0449 → 0,0312, bleed 0,0397 → 0,0399 contra o `baseline` do próprio portão); os portões absolutos (CER limpo ≤ 0,005, lances ≥ 0,998, inventados 0, ordem 1,0) continuam **bloqueados** como estavam no ciclo 1 — a ordem de leitura 0,9917 é o `twocol:a:10` (0,5 também no antes: o RapidOCR perde a primeira linha do russo) | `benchmarks\sol_gate.py --report-only benchmarks\reports\sol\f2_on_*.json` |
| `progresso` (F9) | **PASSOU** — `_rodar` REGISTRADA (total, cancel); `segunda_opiniao` DECLARADA | `python -m caissa.ui.audit.progresso --tronco ..\ChessVisionOFF_Puro --saida benchmarks\reports\ui\f2_c2` |
| `contraste` | **PASSOU** (308 pares, 228 sob portão, 8 da suíte); `--sabotar` **REPROVOU** | `python -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\f2_c9 [--sabotar]` |
| `comandos`, `teclado`, `bloqueio` | `comandos` **PASSOU** (424 medidos, 415 habilitados, 0 soltos, 0 que prometem, 0 cinzas sem motivo, 3 peles); `teclado` **PASSOU** (o tabuleiro no ciclo do `Tab`); `bloqueio` **PASSOU 3/3** («abrir PDF» pior 14,8 / 11,8 / 6,6 ms) depois de VIOLA com o aquecimento imediato (§C2) | ver §C2/§C8 |
| `percurso --fluxo livro` (Aagaard 31–38) | **PASSOU** — 6 ações, decisão `fonte=janela`, EPUB com os 13 diagramas e o corrigido; `trilho.aprendeu` em nota (0 hesitantes nas páginas: a dúvida é de texto — §0.3) | `python -m caissa.ui.audit.percurso --pdf "…AAGAARD….pdf" --paginas 31-38 --saida benchmarks\reports\ui\f2_c8` |
| catracas do tronco | `test_packaging.LIMITE` 1.998 → **2.058** (motivo no docstring: C2/C3/C8; a mecânica em `qt/leitura.py`, `qt/abas_da_suite.py`, `ui/teclado_do_tabuleiro.py`) | `pytest tests\test_packaging.py` |

### 0.3 O que ficou vermelho ou aberto (honesto)

- **B5 sobe o CER medido em `native` (0,0140 → 0,0237) e é isso que ele faz.** Uma região abstida
  conta CER 0 no `bench_sol` (C1 §1.6); as 24 regiões que o resgate manda à revisão passam a
  contar com o texto que têm. Pareado: nos 175 itens respondidos nos dois lados o CER é
  **idêntico (0,0134)**; nos 24 resgatados a mediana é 0,028 (11 com ≤ 2 %, 19 com ≤ 10 %),
  184 de 194 lances certos, 5 inventados. Os piores (`17:401:52` 0,59, `11:54:52` 0,38) são
  colunas de lances brancas | pretas lidas na ordem do PSM 3 — texto certo, ordem errada, e é
  o próximo passo de leiaute (uma tabela de lances por linhas), não da fusão.
- **B8 fica desligado por medição.** No `shadow_curl_bleed` a variante `bleed_verso` fez CER
  0,0387 → 0,0399 e inventados 8 → 10 (dentro do IC 0,0254–0,0530, mas na direção errada); o
  estrato é a própria página espelhada **e depois** curvada, e o registro global não segue a
  curvatura. O mecanismo está testado (`test_verso`, 7) e liga-se com `use_verso=True`; a
  decisão pede um livro real com verso real, que o corpus dourado não tem.
- **B2 não tem efeito mensurável em `native`** (as páginas nativas são lidas pela camada de
  texto; a faixa só corre sobre uma leitura do Tesseract) e **+0,4 pp de lances** nas regiões
  `movetext` de `scan_clean_300` (0,9572 → 0,9616; CER 0,0049 → 0,0047) — no limite do ruído.
- **B6 é pequeno e ambíguo:** `native` lances 0,9342 → 0,9391 e CER 0,0243 → 0,0237 a favor;
  `fax_dither` −0,1 pp e `scan_degraded_150` −0,1 pp contra. Fica ligado pelo `native`; os
  três limiares da `FusionConfig` não foram recalibrados (o §4.6 pedia `calibrate_sol.py` na
  partição `calib` — fica para quem mexer neles).
- **C8 «o trilho aprende» não é afirmável no Aagaard 31–38:** os 13 diagramas leem com folga
  (0 hesitantes) e a dúvida das páginas é de texto em revisão, que uma correção de diagrama
  não muda. O `percurso --fluxo livro` diz isso em nota e não reprova; a regra fica pelo teste
  unitário (`test_trilho`, hesitante → decidido) e pelo `PonteTests` (`atualizar_trilho`).
- **C10: população zero no acervo** — 46 livros, 10.639 linhas de coordenadas `a-h` e nenhuma
  `h-a`; as 175 colunas «1 no topo» vivem em livros sem coordenada nenhuma (enumerações) e
  não vêm acompanhadas de uma linha de letras invertida. Restava o bug vetorial, que está
  fechado; a via raster e o tronco leem as coordenadas mesmo assim, e a fixture do lado das
  pretas prova o caminho.
- **`f2_before` não é exatamente a fase 1:** o `_looks_like_movetext` sem números no
  denominador (B2), o `Popen` com sondagem e o `OMP_THREAD_LIMIT=1` (B9) não têm interruptor.
  O «antes» de referência da fase 1 para `native` continua sendo `critico_b4_on` (0,0140 / 0,9007
  no `real:`), e o `f2_before` coincide com ele ao milésimo em CER (0,0140).
- **O aquecimento do modelo custou 30–80 ms de bloqueio da janela na primeira versão** (a
  carga do `.pt` é C que segura o GIL): `bloqueio` VIOLA em «abrir PDF» e na primeira virada.
  Adiado para 3 s de ócio (reiniciado a cada virada de página), 3/3 PASSOU com folga.

---

## §B1 — Leiaute na página digitalizada

### Em uma tela

| medida | antes (`f2_before`) | depois (`f2_on`) | sabotagem (`f2_b1_off`) |
|---|--:|--:|--:|
| `scan_clean_300` CER, `two-column` (26) | 0,1251 | **0,0108** | 0,1249 |
| `scan_clean_300` CER, `single` (101) | 0,0047 | 0,0046 | 0,0046 |
| `scan_clean_300` CER, `table` (6) / `problems` (4) | 0,0023 / 0,0068 | 0,0023 / 0,0068 | idem |
| `scan_clean_300` CER inteiro (137) | 0,0275 | **0,0058** (IC 0,0034–0,0087) | 0,0274 |
| `scan_degraded_150` CER, `two-column` | 0,0589 | **0,0173** | 0,0589 |
| `scan_degraded_150` CER inteiro | 0,0336 | **0,0256** | 0,0335 |
| lances `scan_clean_300` / `scan_degraded_150` | 0,9542 / 0,8758 | 0,9586 / 0,8839 | 0,9580 / 0,8790 |
| ordem de leitura (60 itens com > 1 região) | 0,9917 | 0,9917 | 0,9917 |
| `s/MP` `scan_clean_300` | 1,23 | 1,26 | 1,21 |

### O que foi construído

`caissa/ocr/layout/scan.py`: a projeção do tronco (`text/colunas.py`) sobre as caixas de
**palavra** da leitura inteira — para cada x, quantas *linhas* o cobrem (a união das palavras da
linha, nunca a caixa da linha, que é o que o PSM 3 funde); uma linha tolerada na calha a partir
de 12; piso = max(0,8 × largura mediana de caractere, 1 % da largura do texto, 4 px); faixa
< 10 % fundida na vizinha pela calha mais estreita. As linhas partidas nas calhas vão ao
`analyze_page` de sempre (colunas, XY-cut, parágrafos); região com ≥ 50 % de lances (sem
contar números e pontos) vira `MOVETEXT`. `PageRecognizer._whole_page` → `_scan_layout` →
`_by_scan_layout`: por padrão **fatia** a leitura inteira (e os candidatos, `_slice`); com
`scan_reread` relê cada região (PSM 4/6). Duas guardas medidas: `max_columns=2` (tabela) e
`min_band_chars=16` (lista de lances).

### Portão

A tabela acima: `CAISSA_FIGURINE_TESSDATA=models\tessdata .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither --label f2_on` (`benchmarks\reports\sol\f2_on_20260921_001320.json`); o «antes» é o mesmo comando com todos os interruptores da fase 2 desligados (`SOL_CONFIG='{"page": {"scan": {"enabled": false}}, "movetext_strips": false, "fusion_rescue": false, "fusion": {"calibrated": false}, "use_verso": false, "workers": 1}'`, `f2_before_20260920_233910.json`); cada ablação desliga um só. `single`, `table` e `problems` inalterados ao décimo de milésimo (o controle de coluna única do tronco, Darcy Lima 0/39, refeito aqui como 101 itens `single`); a sabotagem `{"page": {"scan": {"enabled": false}}}` devolve `two-column` a 0,1249 — **REPROVA**. Os dois itens `two-column` que restam acima de 0,05: `twocol:a:10` (0,135 nos três — o RapidOCR perde a primeira linha do russo, antes da fase) e `twocol:a:11` (0,050).

### Testes

`tests/unit/ocr/test_scan_layout.py` (18): calha, controle de coluna única, tolerância só com
≥ 12 linhas, faixa estreita, piso, tabela de 3 faixas, lista de lances, fatia × reler, sabotagem.

---

## §B2 — O perfil de lances chega à página mista

### O que foi construído

`OcrService._strip_candidates`: numa região que não é movetext mas `_carries_notation`, as
linhas com ≥ 2 lances (`_line_carries_notation`) agrupadas em bandas de linhas consecutivas
(`_adjacent`), cada banda lida uma vez (`recognize_with_profile(MOVETEXT)`, PSM 7 numa linha /
PSM 6 numa banda; ≤ 8 bandas), traduzidas ao espaço da página e reunidas num candidato
`tesseract_strips` **secundário** (nunca âncora — §0.1). `_looks_like_movetext` deixa de contar
números e pontos no denominador (`10.d4` tokeniza em três; um bloco numerado além do lance 9 lia
como um terço de notação e nunca era movetext).

### Portão

| medida | `f2_on` | `f2_b2_off` |
|---|--:|--:|
| `native` CER / lances (`mixed` 87, `movetext` 48) | 0,0315 / 0,8755 · 0,0382 / 0,9676 | **idêntico** |
| `scan_clean_300` `mixed` (64) CER / lances | 0,0071 / 0,9544 | 0,0072 / 0,9533 |
| `scan_clean_300` `movetext` (63) CER / lances | 0,0047 / **0,9616** | 0,0049 / 0,9572 |
| `scan_clean_300` inteiro CER / lances | 0,0058 / 0,9586 | 0,0059 / 0,9559 |
| `s/MP` `scan_clean_300` | 1,26 | 1,10 |

O `f2_on` é o comando do §B1 (`benchmarks\reports\sol\f2_on_20260921_001320.json`); a ablação é o mesmo comando com `SOL_CONFIG='{"movetext_strips": false}' --label f2_b2_off` (`f2_b2_off_20260921_002336.json`). **No limite do ruído**: +0,4 pp de lances onde a faixa
corre, nada em `native` (a camada de texto lê as páginas nativas; a faixa só existe sobre uma
leitura do Tesseract). O custo é 0,16 s/MP em `scan_clean_300`. Fica ligado pelo sinal e pela
sabotagem, que reproduz o antes ao milésimo; o ganho que o SOL-7 mediu em movetext puro (CER
0,0168 → 0,0066) não se transfere às páginas mistas do corpus como o §4.5 esperava.

### Testes

`tests/unit/ingest/test_movetext_strips.py` (4): só a linha de notação vira faixa, com o perfil
`MOVETEXT`; a sabotagem deixa a região ao perfil de prosa; duas linhas de lance por faixa; o
denominador.

---

## §B3 — NAGs na via de importação

### O que foi construído

`nag_table.nags_from_suffix(suffix, white_to_move)`: fatia a cauda pelos glifos e apelidos do
mais longo para o mais curto (`!?±` → `$5 $16`; `³` → `$15`; `⨀` pelo lado); apelidos novos
`⇄` (a classe do leitor de glifos), `△`, `⊕`, `◻` (a fonte do Informator). `games._move_nodes`
preenche `MoveNode.nags` de `RepairedMove.suffix` (passo A4) com o lado de `fen_before`. O texto
do IR fica como impresso (`map_book_symbols` **não** reescreve os parágrafos): o NAG vai
estrutural, e o `²` visível é o que o livro imprime.

### Portão

`notation_integrity --what nags` (Dvoretsky 204/300/408/500/612; Aagaard 74/100/148/222/260),
diagramas ligados:

| livro | págs | lances c/ NAG no texto | partidas | nós | nós c/ NAG | códigos |
|---|--:|--:|--:|--:|--:|---|
| Dvoretsky E1 | 5 | 6 | 8 | 50 | **6** | `$1×2 $2×2 $3×1 $6×1` |
| Aagaard E1 | 5 | 21 | 1 | 2 | 0 | — (as análises do Aagaard não encadeiam em partida) |

**PASSOU** (6 nós com NAG em 9 partidas); `--sabotar nags` (apaga `!?` e os símbolos do texto
de onde as partidas nascem) → **REPROVOU** (0). Só `!`/`?` aparecem nas páginas pinadas — os
símbolos (`±`, `⩲`, `⨀`) ficam fixados por teste (`test_games` B3, 3 testes). Rodado **sem**
`CAISSA_FIGURINE_TESSDATA` no ambiente (com ele, o `config` do tronco recusa a variável e o
classificador não carrega — os diagramas ficam sem leitura e as partidas sem âncora).

---

## §B5 — O escore da fusão

### O que foi construído

`OcrService._rescue_abstained`: quando a âncora **e** o fundido abstêm, procura um candidato
independente (outro motor, ou secundário) aceito/revisão que concorde com o fundido em ≥ 2
lances; re-pontua o fundido pelo árbitro (`arbiter.score`, com os outros como `others`), decide
de novo e devolve **REVIEW** (nunca ACCEPTED — SOL-2; nunca por cima dos pisos de evidência: um
ABSTAINED do `decide` fica abstido). O motivo diz o escore antigo, o novo, os lances e a fonte.

### Portão

| medida (`native`, 237) | `f2_b5_off` | `f2_on` |
|---|--:|--:|
| abstidos / revisão | 62 / 70 | **38 / 94** |
| CER (o abstido conta 0) | 0,0134 | 0,0237 |
| CER **pareado** nos 175 respondidos nos dois | 0,0134 | 0,0134 |
| CER dos 24 resgatados (mediana; ≤ 2 %; ≤ 10 %) | — | 0,0989 (0,028; 11; 19) |
| lances dos 24 resgatados (certos / verdade / inventados) | 0 / 194 / 0 | 184 / 194 / 5 |
| lances `native` / inventados | 0,9362 / 18 | 0,9391 / 23 |
| controles / silenciosas | 0/9 · 0 | 0/9 · 0 |

O `f2_on` é o comando do §B1 (`benchmarks\reports\sol\f2_on_20260921_001320.json`); a ablação é o mesmo comando com `SOL_CONFIG='{"fusion_rescue": false}' --label f2_b5_off` (`f2_b5_off_20260921_002837.json`); o pareamento por item em
`scratchpad` (rows dos dois JSON). Nenhum resgate sai ACCEPTED (a razão em `reasons_pt` nomeia o
escore antigo, o novo, os lances e a fonte). O que sobe é o CER *medido*, porque o abstido
contava zero; o que o revisor passa a ver são 24 linhas de solução sob diagramas que antes
sumiam — 184 dos seus 194 lances certos.

---

## §B6 — Escala comum na fusão

### O que foi construído

`fuse_candidates(calibrators=)`: cada `Reading` entra com a confiança calibrada
(`ArbiterConfig.calibration_for(engine, facet).apply`, a faceta da região) — Tesseract e
RapidOCR têm tabela (68, SOL-4); o leitor de glifos e o modelo de figurinas ficam na escala
crua, que é a dos seus limiares (`figurine_min_confidence`, `figurine_min_margin`). Os três
limiares da `FusionConfig` **não** foram recalibrados; o A/B decide se a escala fica.

### Portão

| medida | `f2_b6_off` (escala crua) | `f2_on` (calibrada) |
|---|--:|--:|
| `native` CER / lances / inventados | 0,0243 / 0,9342 / 24 | **0,0237 / 0,9391** / 23 |
| `scan_degraded_150` CER / lances / inventados | 0,0256 / 0,8850 / 56 | 0,0256 / 0,8839 / 56 |
| `fax_dither` CER / lances / inventados | 0,0315 / 0,8294 / 23 | 0,0312 / 0,8283 / 23 |

O `f2_on` é o comando do §B1 (`benchmarks\reports\sol\f2_on_20260921_001320.json`); a ablação é o mesmo comando com `SOL_CONFIG='{"fusion": {"calibrated": false}}' --label f2_b6_off` (`f2_b6_off_20260921_003448.json`). Pequeno e ambíguo (§0.3): fica
ligado pelo `native`; os limiares da `FusionConfig` não foram recalibrados.

---

## §B8 — O verso real

### O que foi construído

`PageTask.verso_sources` (as páginas vizinhas renderizadas sob demanda —
`OcrService._neighbour_renders`), `_verso_for` (só quando `bleed_share` ≥ piso; candidatas =
vizinhas + espelho da própria; `register_verso` de cada uma; a melhor correlação ≥ 0,08),
`build_portfolio`: variante `bleed_verso` ao lado de `bleed_sauvola` (só ela recebe o verso;
+1 no teto). O piso foi medido numa página com **outra** página atravessando a 25 %
(`test_verso`): verso certo 0,13, espelho 0,10, página errada 0,03, ruído 0,001; o estrato
sintético (a própria página espelhada) registra a 0,22–0,28.

### Portão

| medida (`shadow_curl_bleed`, 101) | `f2_b8_off` | com `use_verso=True` (`f2_on`) |
|---|--:|--:|
| CER (IC) | **0,0387** (0,0254–0,0530) | 0,0399 (0,0265–0,0536) |
| lances / inventados / revisão | 0,9345 / 8 / 28 | 0,9336 / 10 / 30 |
| `s/MP` | 5,58 | 6,05 |

O `f2_on` é o comando do §B1 (`benchmarks\reports\sol\f2_on_20260921_001320.json`); a ablação é o mesmo comando com `SOL_CONFIG='{"use_verso": false}' --label f2_b8_off` (`f2_b8_off_20260921_003654.json`) — o `f2_on` correu com o padrão de então (`use_verso=True`); hoje o padrão é o lado `f2_b8_off` desta tabela, e reproduzir o `f2_on` pede `SOL_CONFIG='{"use_verso": true}'`. **Desligado por medição** (§0.3);
`OcrServiceConfig.use_verso=False` documenta os números. As correlações registradas no
estrato: 0,22–0,28 (o espelho da própria página).

### Testes

`tests/unit/ocr/test_verso.py` (7): a variante nasce ao lado da heurística e só ela vê o verso;
a melhor candidata vence; abaixo do piso nada; página sem transparência não pede as vizinhas;
sabotagem; `page±1` renderizadas.

---

## §B9 — Paralelo e cancelamento dentro da página

### O que foi construído

`caissa.ocr.cancel` (`OcrCanceled(BaseException)` — atravessa os `except Exception` que
protegem cada candidato; `cancellable(hook)` num `ContextVar`; `check_cancel`). O runner do
Tesseract passa a `Popen` + `communicate(timeout=0,1 s)` em laço, consultando o gancho e matando
o filho; `OMP_THREAD_LIMIT=1` no filho (`TesseractConfig.omp_thread_limit`); o perfil forçado
vira `threading.local` (duas threads não partilham um `_forced_profile`). `OcrService.
_run_readings`: as leituras extras de uma região (perfis, glifos, figurinas, cada variante) vão
a um `ThreadPoolExecutor(workers=4)` com `contextvars.copy_context()`, e a lista volta **na
ordem de submissão** (o traço é o mesmo do serial). O importador envolve a importação em
`cancellable(should_cancel)` e converte `OcrCanceled` em `ImportCanceled` com o parcial.

### Portão

| medida | `f2_b9_serial` (`workers=1`) | `f2_on` (`workers=4`) |
|---|--:|--:|
| `scan_clean_300` s/MP · segundos | 1,41 · 120,6 | **1,26 · 107,6** (−11 %) |
| `scan_degraded_150` s/MP · segundos | 9,21 · 196,8 | **7,34 · 156,9** (−20 %) |
| itens com `cer`/`decision`/`confidence`/`engine`/`hypothesis`/lances diferentes | — | **0 de 274** |
| `f2_before` (serial, sem faixas nem leiaute) | 1,23 · 105,5 / 6,67 · 142,5 | — |

O `f2_on` é o comando do §B1 (`benchmarks\reports\sol\f2_on_20260921_001320.json`); a ablação é o mesmo comando com `SOL_CONFIG='{"workers": 1}' --label f2_b9_serial` (`f2_b9_serial_20260921_004219.json`). O paralelo absorve o trabalho
que a fase acrescentou (as faixas do B2, a fatia do B1): o tempo total dos dois estratos volta
ao do «antes» com mais candidatos por região. Determinismo: 274 de 274 itens iguais nos campos
medidos. O cancelamento dentro da página: `test_cancel` (o filho `python -c "sleep 30"` morto em
< 5 s com o gancho ligado; o tempo limite continua a valer sem gancho) e o importador
(`OcrCanceled` na 2.ª página → `ImportCanceled`, 1 página no parcial com `keep_partial`).

### Testes

`tests/unit/ocr/test_cancel.py` (12): escopo do gancho, herança pela `copy_context`, o filho
morto em < 5 s, o tempo limite continua, ordem de submissão, o serial com `workers=1`,
cancelamento dentro do pool, o importador com `keep_partial`.

---

## §C2 — Ler a página com progresso, cancelamento e o gravar trancado

### O que foi construído

Tronco: `service.recognize_page(progress=, should_cancel=)` (avisa `(0, N)` … `(N, N)` e
levanta `RecognitionCanceled(partial)` antes de cada diagrama); `Tarefa.cancelar`/`should_cancel`
(um `Event`); `qt/leitura.py` (`Ocupacao`: a ficha do rodapé com `total` e o gancho de
progresso; `Aquecimento`: o modelo carregado numa `Tarefa` própria 3 s de ócio depois de abrir o livro
-- o relógio reinicia a cada virada de página e nunca dispara com tarefa em curso --, uma vez por
processo, com a frase do `.pt` ausente); `_rodar` registra no `BusyRegistry` (o `register` fica
na janela porque o portão `progresso` atribui a thread ao registro da mesma função) e devolve a
tarefa; `_falhou` trata `RecognitionCanceled` (o lido fica na lista, frase «cancelada») e o
`.pt` ausente (`Ferramentas ▸ Configurações…`, `painel.mostrar_vazio_sem_modelo`);
`_atualizar_controles` tranca só `btn_salvar*` (`painel.trancar_gravacao`); `("janela.py",
"_rodar")` sai de `FORA_DO_REGISTRO`.

### Portão

- `caissa.ui.audit.progresso`: **nenhum defeito bloqueante**; `_rodar` REGISTRADA (constrói
  Tarefa), `Aquecimento.iniciar` REGISTRADA, `segunda_opiniao` DECLARADA.
- `percurso --fluxo casa --cancelar` (Kemeri p. 80): **PASSOU** — o cancelamento pedido com a
  tarefa viva pára em 53 ms com «Leitura cancelada antes do primeiro diagrama.», 0 itens;
  `--sabotar sem_cancelamento` (`Tarefa.should_cancel` sempre falso) → **REPROVOU** (161 ms, «Lendo
  a página 80…», 1 item na lista). `--frio` (processo novo, 3×): clique em Ler → primeiro
  diagrama **0,58 / 0,59 / 0,58 s** com o aquecimento (que corre em 1,7 s enquanto a pessoa vai à
  página); `--sabotar sem_aquecimento` **1,98 / 2,04 / 2,01 s** → REPROVOU contra o teto de 1,5 s
  (o roadmap propunha 8 s, que a sabotagem não cruzaria — anti-padrão 2; o teto ficou entre
  os dois números medidos). Comandos: `python -m caissa.ui.audit.percurso --pdf "…1937
  Kemeri.pdf" --fluxo casa --pagina 80 --cancelar|--frio [--sabotar …] --saida benchmarks\reports\ui\f2_c2`.
- `bloqueio` (Kemeri, 3 corridas): com o aquecimento disparado ao abrir, **VIOLA** — «abrir PDF»
  27,8 / 36,5 / 44,5 ms e a primeira virada de página 84 / 57 ms (a carga do `.pt` é C que segura o
  GIL; a atribuição por família dava 97,7 % `builtins (C)`). Adiado para 3 s de ócio
  (`leitura.ESPERA_PARA_AQUECER_MS`, reiniciado a cada virada; nunca com tarefa ou operação
  registrada em curso): **PASSOU 3/3** — «abrir PDF» pior 14,8 / 11,8 / 6,6 ms (medianas 8,0 /
  8,6 / 5,1), contra 14,8 / 16,2 / 14,5 no fecho da fase 1. O primeiro «Ler» continua a 0,6 s
  (o aquecimento acabou aos 5,7 s da abertura no `--frio`).

### Testes

`tests/test_qt_leitura.py` (7): a ficha com total e cancelar; o aquecimento uma vez e a frase
do `.pt` ausente; a leitura registrada com o painel ligado e o gravar trancado; cancelar pelo
rodapé para entre diagramas e o lido fica; a sabotagem do serviço surdo lê até o fim.
`tests/test_service.py::ProgressoECancelamentoTests` (3).

---

## §C3 — Segunda opinião de outra família

### O que foi construído

`PainelDeResultado.segunda_opiniao` (comando `segunda_opiniao` no catálogo/menu; botão que
nasce escondido e aparece com diagrama + `local_reader` configurado): `build_local_provider`
(o clone tsoj, `Chess_diagram_to_FEN`), `predict(board_rgb)` numa `Tarefa`,
`modelo.mark_second_opinion` (adota a posição, guarda a disputa), histórico (Ctrl+Z devolve),
`tabuleiro.definir_casas_disputadas` (anel `DIVERGENTE` — o papel já existia para isto — e o
`Tab` percorre as disputadas), `label_route` → `segunda-opiniao`.

### Portão

`benchmarks/second_opinion_gate.py --failures benchmarks/reports/f4_grade/failures.json` (os
11 barrados de 2026-09-20 08:56, 27 casas erradas; leitor `C:\Python-Chess2\Chess_diagram_to_FEN`):

| n | livro | pág. | erradas | cobertas | disputa | s |
|--:|---|--:|--:|--:|--:|--:|
| 1 | Euwe, Kramer | 40 | 3 | 3 | 3 | 6,21 (1.ª carga) |
| 2 | Koblenz | 30 | 1 | 1 | 1 | 0,16 |
| 3 | Koblenz | 30 | 4 | 4 | 4 | 0,16 |
| 4 | Koblenz | 50 | 1 | 1 | 2 | 0,15 |
| 5 | Koblenz | 50 | 1 | 1 | 1 | 0,16 |
| 6 | Levenfis | 150 | 3 | 3 | 10 | 0,49 |
| 7 | Niemeijer | 20 | 8 | 6 | 6 | 0,36 |
| 8 | Niemeijer | 20 | 1 | 0 | 0 | 0,21 |
| 9 | Niemeijer | 20 | 1 | 1 | 1 | 0,17 |
| 10 | Stefaniu | 100 | 3 | 2 | 8 | 0,52 |
| 11 | Burgess | 60 | 1 | 1 | 1 | 0,36 |

**PASSOU — 23 de 27 casas erradas cobertas (85,2 %, piso 75 %); mediana 2 casas em disputa.**
`--sabotar copia` (o segundo leitor devolve a leitura do primeiro) → **REPROVOU, 0/27**. No
Euwe p40 a disputa é exatamente as três casas erradas, e o segundo leitor acerta `a6` (p) onde
o de produção leu `b`. Os 4 não cobertos: Niemeijer p20 (2 de 8 e 1 de 1) e Stefaniu p100 (1 de
3) — os dois leitores erraram igual.

### Testes

`tests/test_qt_painel_de_resultado.py::SegundaOpiniaoTests` (3): a disputa marcada e a posição
adotada, desfazível, com `label_route`; sem leitor o botão some e o comando diz por quê; a cópia
do primeiro não marca nada.

---

## §C8 — Trilho que aprende, dúvidas navegáveis, teclado no tabuleiro

### O que foi construído

- **Trilho.** `caissa.ui.trilho.hesitantes_por_pagina(document, diagram_decisions)`: um diagrama
  lido com casa < 0,90 conta como dúvida até alguém o corrigir (decisão gravada para a caixa,
  IoU ≥ 0,5, ou `verified_by_human`); `estados(document=, diagram_decisions=)`;
  `proxima_duvidosa`/`anterior_duvidosa` (suíte e tronco). `Ponte.atualizar_trilho()` relê as
  decisões do disco e reavalia as marcas — chamado por `_gravou_amostra` e `_fechar_item_da_fila`.
  Comandos `proxima_duvidosa`/`anterior_duvidosa` (`Ctrl+Page Down/Up`, menu Ver).
- **Teclado.** `ui/teclado_do_tabuleiro.py` (a regra, sem toolkit): `Tab`/`Shift+Tab` → a
  próxima/anterior duvidosa (as âmbar; sem elas as incertas; sem elas as ocupadas), setas, `k q r
  b n p` (Shift = branca), `Delete`, `Espaço`/`Enter` (o pincel). `TabuleiroEditavel` com
  `StrongFocus`, `keyPressEvent`, `definir_duvidosas` (o painel manda as âmbar). A letra é a peça
  e não a coluna (o `b` teria dois papéis). As setas e o `Delete` são atalhos **globais** da
  janela e a guarda os vê antes do widget: o tabuleiro em foco os toma para si pelo protocolo
  da S-244 (`acoes_proprias` = `ACOES_DAS_SETAS` + `apagar_casa`, `atender`), como o campo de
  texto toma o `←` (§0.1).
- **As abas da suíte no catálogo.** `caissa.ui.views.declarados` (as tabelas `comando → método`);
  `qt/abas_da_suite.py` (donos — a frase de ausência sem a suíte — e o roteamento por aba à
  frente); `salvar`/`ler_pagina`/`pagina_anterior`/`proxima_pagina` vão à aba da suíte que está
  à frente; os `QShortcut` locais ambíguos (`Ctrl+S`, `Ctrl+O`, `F5`, `PgUp`/`PgDn`) saíram das
  views. Cinco comandos novos no catálogo e no menu Arquivo.

### Portão

- `percurso --fluxo casa --teclado` (Kemeri p. 80): **PASSOU** — `Tab` até e2 (1 tecla: a
  ordem do `Tab` é a da dúvida, a casa de menor confiança primeiro) + `q` = **2 teclas**, teto 3;
  `--sabotar sem_teclado` (o `keyPressEvent` não faz nada) → **REPROVOU** (9 teclas, casa não
  corrigida). A primeira versão percorria as casas em ordem de tabuleiro e precisava de 8 `Tab`
  para chegar a e2 — foi o portão que mudou a regra (`teclado_do_tabuleiro.proxima_duvidosa`
  respeita a ordem da lista).
- `caissa.ui.audit.comandos`: **PASSOU** — 424 medidos (400 na fase 1), 415 habilitados, 0
  soltos, 0 que prometem, 0 cinzas sem motivo, nas três peles; `caissa.ui.audit.teclado`:
  **PASSOU**, o tabuleiro entra no ciclo do `Tab` de todas as áreas (Resultado 37 focáveis, 37
  pelo `Tab`, fecha).
- `percurso --fluxo livro` (Aagaard 31–38): **PASSOU** (6 ações, decisão `fonte=janela`, EPUB com
  13 diagramas e o corrigido); «o trilho aprende» fica em nota — 0 hesitantes na página (§0.3).
- Comandos: `python -m caissa.ui.audit.percurso --pdf "…1937 Kemeri.pdf" --fluxo casa --pagina 80
  --teclado [--sabotar sem_teclado] --saida benchmarks\reports\ui\f2_c8`; `…audit.comandos --pdf …
  --saida …`; `…audit.teclado --pdf … --saida …`.

### Testes

`tests/test_qt_tabuleiro_editavel.py::TecladoTests` (8: com a guarda de atalhos ligada as setas
andam e a janela não recebe a tecla; sabotagem sem `acoes_proprias`), `tests/unit/ui/test_trilho.py` (+2),
`tests/test_ui_comandos.py` (rótulos registrados), `tests/test_qt_janela.py` (110 passam).

---

## §C9 — As abas da suíte pela pele

### O que foi construído

`caissa/ui/theme/pele.py`: `PAPEIS` (papel da suíte → token do tronco + reservas clara/escura),
`cor(papel)` (o token no cromo em vigor — `tema.cromo_escuro_em_vigor()` — ou a reserva sem
tronco), `PARES` (o que as views pintam sobre o quê), `fonte_monoespacada`, `vestir_paginador`
(o ícone do tronco ao lado da palavra, `◀`/`▶` fora). As quatro views usam `pele.cor`.
`contraste.pares_pintados_da_suite` mede os 8 pares nas duas peles. Duas mutações medidas: a
caixa selecionada era `ALVO` (papel de tabuleiro, 1,65:1 sobre a folha) → `TRACEJADO` ("a área
que você está selecionando"), 6,18:1; e as palavras fracas da leitura do motor no cartão
(`leitura_em_html`) saíam com **fundo** `REALCE_NOTA`/`REALCE_DESTAQUE` — o teste da suíte
inteira mostrou o hexadecimal: `#b9ffc5`, verde, a cor de "nota do autor" atrás de uma palavra
duvidosa. A regra do editor de texto do tronco (`ui/texto_cores.py`) é a confiança na **letra**
(`conferir` em `ATENCAO`, `revisar` em `PROBLEMA_TEXTO`) e os realces de fundo são o canal de
quem escreve; o cartão passa a segui-la (`cartao_palavra_conferir`/`cartao_palavra_revisar`,
sem `background:`), e o teste pergunta os hexadecimais à pele em vigor em vez de fixá-los.

### Portão

`python -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\f2_c9`
(`contraste_20260921_043447.json`, depois da segunda mutação): claro 308 pares, 228 sob portão,
0 reprovados; escuro idem — **PASSOU**; os 8 da suíte nas duas peles (piores: `aviso` e
`cartao_palavra_revisar` sobre cromo 4,77:1 claro / `cartao_motivo` 5,04:1 escuro, piso 4,5;
`cartao_palavra_conferir` 5,20:1 claro / 5,09:1 escuro); `--sabotar` → **REPROVOU**
(`contraste_sabotagem_20260921_043448.json`). Antes do passo o portão tinha 300 pares e nenhum
das views da suíte.

### Testes

`tests/unit/ui/test_pele_da_suite.py` (5).

---

## §C10 — Coordenadas impressas e o ponto de vista das pretas

### O que foi construído

Suíte: `rotate_placement` (linhas invertidas, cada linha invertida — dígitos de vazio são um
caractere); a via vetorial gira o `placement` quando `white_at_bottom=False` e lê os rótulos em
volta das **células** em espaço de página (a caixa antiga, `write_rect`, ficava meia casa fora no
x e girava com a página — o leitor de rótulos nunca respondia e a orientação era sempre
`heuristic`); a via raster (`raster_diagram_finder(read_coordinates=True)`) lê os rótulos com
`point_of_view_from_labels` e, do lado das pretas com o classificador em 0°, gira a **FEN** e o
sinal por casa (`rotate_signal`), `orientation_white=False` — o renderizador vira de novo e a
exibição bate com o livro. Tronco: `pdf_text.board_coordinates_for` **produz** `BoardCoordinates`
(a coluna de dígitos e a linha de letras; `files_left_to_right` novo; ≥ 4 de cada);
`CoordinateRule` responde `black_point_of_view` em vez de `upright=False` (girar a imagem poria
as peças de cabeça para baixo); `OrientationPolicy.resolve(turn=)` gira o **mapeamento**
(`prediction_from_probs(probs[::-1])`, os mesmos parâmetros); `RecognizedDiagram.
black_point_of_view`; o painel desenha o tabuleiro **e o recorte** `virado` pelo mesmo critério
(§0.1: o recorte virava só pela rotação e a tinta caía na casa espelhada).

### Portão

`benchmarks\coordinate_survey.py` (os 46 PDFs do acervo, todas as páginas, camada de texto, 31 s):
**10.639 linhas de letras `a-h →` e 0 `h-a ←`**; colunas de dígitos 2.501 «8 no topo» e 175 «1 no
topo» — estas em livros sem linha de letras alguma (Secrets of Chess Training 81, Fischer 25,
Capablanca 20: enumerações), nunca ao lado de uma linha invertida. `--sabotar espelhar` troca as
colunas: 0 / 10.639 e 175 / 2.501. Conclusão: população zero no acervo, o bug vetorial era o
que restava (fechado), e o leitor de rótulos da via vetorial, que nunca respondia (a caixa de
escrita meia casa fora, em espaço girado), passa a responder `source="labels"`.

### Testes

`tests/unit/detect/test_point_of_view.py` (4: `rotate_placement`, o lado das pretas com
`coordinates="black"` → placement canônico, o espelho → como impresso, o sinal girado),
`tests/test_orientation.py` (a regra reescrita + letras + discordância),
`tests/test_pdf_text.py::BoardCoordinatesTests` (4).
