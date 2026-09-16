# OCR/UI · ciclo 1 — relatório do construtor

> **Data:** 2026-09-14 · **Plano:** `docs/OCR_UI_ROADMAP.md` · **Contrato:** `docs/OCR_UI_SPEC.md`
> · **Papel:** construtor. Todo número desta página traz ao lado o comando que o produziu.
> Ambiente: `.venv` (Python 3.11.9, torch 2.11.0+cu128, Tesseract 5.5.0), corpus dourado
> privado `43ac7c57017324d8` (446 itens, 747 medições nas partições `dev`+`calib`; a cega fora).
> Relatórios completos em `benchmarks/reports/sol/c1*_*.json`; os dois finais publicados sem
> texto do acervo em `docs/quality/sol/c1_sem.{json,md}` e `c1_rapidocr.{json,md}`.

---

## §0 — Passo 0 (humano, 2026-09-15): FEN inicial nas regiões de lances rotuladas

### 0.0 O número

**8 regiões com `start_fen`** nas 13 páginas rotuladas (todas no SFC4), preenchidas pelo
revisor (duas delas corrigidas depois, no passo 7 — ver §11.1) a partir do diagrama impresso acima de cada coluna de lances — **é o denominador dos
passos 7 e 11**. Não são "todas as colunas de lances": das 26 colunas com ≥ 6 lances, só 6 vêm
logo depois de um diagrama na mesma página; as outras 20 são continuações da partida (o diagrama
está páginas antes, ou os lances intermediários estão na prosa) e não têm posição a copiar. As
duas restantes são partidas do lance 1 (posição inicial). 21 regiões marcadas `movetext`.

| pág. | região | partição | FEN | lances que a repetição de legalidade reproduz da FEN |
|---|---:|---|---|---:|
| 10 | «22... ♖g6» | dev | `…/1B3R1K w - - 4 24` — o diagrama está em 24, a região começa em 22… | 1 |
| 10 | ~~«39 ♔f1» `w 39`~~ → «36 ... ♖e8!» (cega) | cega | `8/6k1/3b4/1R1p4/1PpPr1p1/2P3n1/3B2K1/6N1 b - - 0 36` — corrigida no passo 7 (§11.1): a FEN era do diagrama, e a região do diagrama é a que começa em 36… | 2 |
| 12 | «19... g5!» | dev | `4k2r/p2n1ppp/Npr1p3/3pP3/3p1P2/8/P2N2PP/R3K2R b - - 0 19` | 6 |
| 13 | «17... ♗b4!» | calib | `r2q2k1/2p1b1pp/p3b3/1p1pP3/3P4/1PN1B3/1P4PP/R2Q1K2 b - - 0 17` | 2 |
| 15 | «14 ♘xe5 ♖xe5» | calib | `r2qr1k1/p2n1pbp/bp1p1np1/2pP4/8/P1N2NP1/1PQ1PPBP/R1B1R1K1 w - - 0 14` | 5 |
| 17 | «English Opening / 1 d4 ♘f6» | dev | posição inicial | 28 |
| 18 | ~~«19 ♖c2 ♖g8!» `w 19`~~ → «18... ♔h8!!» | dev | `1qr1r1k1/1bbn1ppp/pp1ppn2/8/2P1P3/1NN1BP2/PP4PP/2RR1BQK b - - 0 18` — corrigida no passo 7 (§11.1) | 1 |
| 19 | «Fischer — Andersson» | **cega** | posição inicial | 19 |

A última coluna é o `repair_movetext(truth, start_fen=…)` de hoje sobre a verdade humana — a
linha de base dos passos 7 e 11, e ela já diz duas coisas: (1) 7 das 8 estão fora da cega
(uma cai na cega e não serve a portão de treino); (2) a repetição para cedo em 4 regiões
(0–2 lances) — em p10 «39 ♔f1» o replay não anda um lance de uma posição em que ♔g2–f1 é legal
(idioma não detectado), em p10 «22...» a FEN é do diagrama a 24, dois lances depois do início
da região. É trabalho do passo 11, não deste; aqui fica o número.

### 0.1 O que mudou nos artefatos

- `labeling/pages/*.json` (fora do git): 8 `start_fen`, 21 `kind=movetext`.
- Manifesto privado regravado (`Exportar → Fundir no manifesto`): 256 itens substituídos,
  446 itens, hash **`ab9e366c8e1c6a61` → `86426402f56220aa`**; 8 itens com `start_fen`.
  Após as duas correções do passo 7 (§11.1): **`eb9b31eff07efe2c`**, 8 itens com `start_fen`,
  2 na cega (p19 e a nova p10 «36…»), 6 utilizáveis.
- Baseline de Sol **recongelado** no hash novo (`docs/quality/sol/baseline.{json,md}`,
  747 medições): os relatórios `c1_*` deste ciclo foram medidos em `43ac7c57017324d8` e o
  `sol_gate` vai acusar a diferença de hash contra eles — correto, o corpus mudou.
- Contagem: `python -c` sobre `caissa.ocr.labeling.LabelProject` (8 regiões com FEN, todas
  válidas pelo `fen_problem`); fusão: `caissa.ocr.labeling.export.merge_into_manifest`.

```
.venv\Scripts\python.exe benchmarks\bench_sol.py --system baseline --label baseline --publish   # hash 86426402f56220aa
```

---

## §1 — Passo 1: segundo motor de OCR ao vivo

### 1.0 Em uma tela

| | sem (caminho de produto de ontem) | com RapidOCR 3.x, roteado | fonte |
|---|---:|---:|---|
| acurácia de lances | 0,819 | **0,893** | `c1_sem` → `c1_rapidocr`, `summary.overall.move_accuracy` |
| lances inventados | 291 | **169** | idem, `moves_invented` |
| regiões em revisão | 240 | **141** | idem, `review` |
| abstenções | 69 | 62 | idem, `abstained` |
| CER médio (abstenção = 0) | 0,0376 | **0,0357** | idem, `cer_mean` |
| CER ponderado nas 669 regiões que ambos respondem | 0,0417 | **0,0387** | §1.6 |
| controles negativos | 0/9 | **0/9** | `sol_gate` |
| importação silenciosa abaixo do limiar | 0 | **0** | `sol_gate` |
| regressão de CER fora do IC, por estrato | — | **nenhuma** | `sol_gate --baseline c1_sem` |
| s/Mpx | 2,34 | 3,01 | `seconds_per_megapixel` |

**Portão do passo** (`OCR_UI_ROADMAP.md` passo 1): *"CER `scan_degraded_150` ≤ 0,020 **ou** queda
fora do IC em ≥ 2 estratos degradados, sem regressão fora do IC em `native`/`scan_clean_300`;
controles 0/12; VRAM ≤ 7,0 GB."* Resultado: `fax_dither` cai fora do IC (0,058 → 0,032; IC da
diferença começa em −0,045); `photo` e `scan_degraded_150` caem **dentro** do IC (−0,004 e
−0,002); `native` e `scan_clean_300` não regridem (−0,0004 e +0,0006, dentro do IC); controles
0/9; VRAM: o motor roda em CPU (§1.2). **Pela letra, o portão de CER não fecha** — só um
estrato cai fora do IC. **Pelo que o usuário compra, o passo entrega**: +7,4 pp de lances
certos e −42 % de lances inventados sobre o corpus inteiro, com o único ✗ do `sol_gate` sendo a
taxa de inserção no estrato de sombra (0,7 % → 1,4 %, §1.7). Fica como está e fica dito.

Por estrato (`benchmarks/reports/sol/c1e_sem_20260914_070857.json` →
`c1g_rapid_20260914_074635.json`):

| estrato | n | CER sem → com | lances sem → com | inventados | revisão | s/Mpx |
|---|--:|---|---|---|---|---|
| `fax_dither` | 63 | 0,0582 → **0,0318** | 0,480 → **0,824** | 80 → **27** | 48 → 9 | 3,4 → 5,1 |
| `photo` | 63 | 0,1157 → 0,1115 | 0,718 → **0,822** | 40 → **24** | 14 → 5 | 5,7 → 7,7 |
| `scan_degraded_150` | 137 | 0,0361 → 0,0342 | 0,843 → **0,873** | 77 → **63** | 35 → 22 | 4,3 → 5,8 |
| `shadow_curl_bleed` | 101 | 0,0303 → 0,0386 | 0,861 → **0,935** | 42 → **8** | 42 → 9 | 5,1 → 5,7 |
| `scan_clean_300` | 137 | 0,0275 → 0,0281 | 0,942 → 0,949 | 23 → 21 | 34 → 28 | 0,9 → 1,1 |
| `native` (inclui os scans reais rotulados) | 237 | 0,0156 → 0,0151 | 0,905 → 0,907 | 29 → 26 | 67 → 68 | 1,6 → 2,1 |

Por idioma: `en` lances 0,834 → **0,930** (inventados 198 → 91); `pt` 0,825 → 0,876; `es` 0,787 →
0,854; `de` 0,793 → 0,825; `ru` 0,405 → 0,493 (CER 0,068 → 0,089 — o cirílico continua o pior
estrato, §1.8). Por fonte: `synth` lances 0,797 → 0,887; `pdf-scan` (SFC4, real) 0,866 → 0,869
com inventados 28 → 25; `pdf-native` 0,951 → 0,944 (inventados 13 → 12).

```
.venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --label c1e_sem
SOL_CONFIG='{"secondary_engines":["rapidocr"]}' .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --label c1g_rapid
.venv\Scripts\python.exe benchmarks\sol_gate.py --report-only benchmarks\reports\sol\c1g_rapid_20260914_074635.json --baseline benchmarks\reports\sol\c1e_sem_20260914_070857.json --label c1g_gate
```

O `sol_config` de cada rodada agora fica gravado no `environment` do relatório (`bench_sol.py`),
para que um número nunca mais precise de contexto de conversa para dizer qual serviço mediu.

### 1.1 O que foi instalado, e com que licença

`rapidocr 3.9.2` (PyPI, RapidAI, **Apache-2.0**; ONNX Runtime 1.30.0 CPU) e, como reserva,
`rapidocr-onnxruntime 1.4.4`. Os dois pedem `opencv-python`; o `.venv` tem
`opencv-python-headless 4.14`, que satisfaz `cv2` — instalação com `--no-deps` mais
`onnxruntime omegaconf colorlog requests PyYAML pyclipper shapely` (a dica do adaptador e o
`pyproject.toml` dizem isso). Os 11 modelos ONNX que o pacote baixou/embute estão em
`src/caissa/ocr/data/weights.json` com SHA-256, tamanho, origem (ModelScope `RapidAI/RapidOCR`
v3.9.2; modelos PP-OCR da PaddleOCR reexportados) e licença Apache-2.0 — registrados **antes** de
qualquer medição (R1.6). O Surya não foi instalado: pesos CC-BY-NC-SA com exceção comercial
("verificar"), torch no mesmo processo que o classificador de casas; fica para depois de a
questão de licença Q1 ser decidida.

### 1.2 ADR-0003, conferida

`onnxruntime` 1.30 CPU carregado **depois** do torch cu128 no mesmo processo: provedores
`['AzureExecutionProvider', 'CPUExecutionProvider']`, nenhum CUDA; `torch.cuda` continua a
executar (`scratchpad/smoke_rapid.py`, `torch.ones(2, device="cuda").sum() == 2.0`). Sem
provedor CUDA não há colisão a isolar, e o adaptador roda no processo. VRAM de pico: a do
classificador de casas, inalterada.

### 1.3 O contrato falso não prova nada — o teste de fumaça real prova

`tests/unit/ocr/test_optional_engines.py` injeta módulos falsos em `sys.modules` e nunca pula:
com o motor real instalado o resultado é idêntico (anti-padrão 6 do roadmap). O novo
`tests/integration/test_engine_live.py` (`slow`, `importorskip`) renderiza uma linha de prosa
enxadrística com o Times e exige texto com confiança do adaptador real: latino (3 testes) e
cirílico pelo `eslav`; e prova que **instalado ≠ usado** — `OcrServiceConfig(secondary_engines=())`
não vê o motor, `("rapidocr",)` vê.

```
.venv\Scripts\python.exe -m pytest tests\integration\test_engine_live.py -q      # 4 passed
```

### 1.4 Medido antes de mudar: o 1.x dobrava o CER

Primeira medição, RapidOCR 1.4 (modelo chinês) como membro pleno da cascata, sem calibração
(`c1_sem_20260914_054154.json` → `c1_rapid_20260914_055957.json`): CER 0,0401 → **0,0847**,
lances 0,821 → 0,766, inventados 317 → 423, s/Mpx 2,4 → 5,1. Ele venceu 224 regiões e leu
**187** delas pior. Duas causas, vistas nos piores itens: o dicionário do modelo chinês **não
tem espaço** (`techniqucsofcutting thekingoff`) e as linhas saem na ordem da detecção,
**intercalando as colunas** de uma região de duas colunas (`twocol:d:10`: CER 0,016 → 0,697).
Calibrar não bastava (§1.5): a leitura era pior, não só a confiança.

O 3.x baixa reconhecedores por alfabeto. Medido nos mesmos dois itens: o PP-OCRv6 multilíngue
padrão lê latino com acentos e espaços (`authored:es:9` em foto: leu as 6 linhas onde o
Tesseract deu `5.83 0-0 64`); o `eslav` PP-OCRv5 lê russo mantendo as casas latinas (`h7`),
onde o `cyrillic` genérico escreve `һ7` (shha). O adaptador (`caissa/ocr/engines/rapidocr.py`)
passou a preferir o 3.x, com uma instância por alfabeto (`latin` → padrão; `eslav` para
rus/ukr/bel; `cyrillic` para bul/srp/mkd), e ganhou **ordem de leitura por geometria**
(`_reading_order`): colunas de prosa uma após a outra; colunas de células curtas (mediana ≤ 12
caracteres — uma tabela de lances, brancas ao lado das pretas) linha a linha, como o
Tesseract e a verdade. Testes de geometria em `tests/unit/ocr/test_rapidocr_order.py` (6).

### 1.5 Calibração (SOL-4), refeita com o motor novo

```
.venv\Scripts\python.exe benchmarks\calibrate_sol.py     # partição calib, 112 itens, 68 tabelas
```

| chave | n palavras | ECE antes | ECE depois | Brier antes | Brier depois |
|---|--:|--:|--:|--:|--:|
| `rapidocr` (1.4, chinês) | 6.927 | 0,2405 | 0,0202 | 0,2491 | 0,1804 |
| `rapidocr` (3.x, PP-OCRv6) | 10.032 | 0,0417 | **0,0098** | 0,0494 | **0,0420** |
| `tesseract` | 10.040 | 0,0420 | 0,0090 | 0,0620 | 0,0599 |

Por palavra, o 3.x é um leitor **melhor que o Tesseract** neste corpus (Brier 0,042 contra
0,060). As 34 tabelas do Tesseract saíram **idênticas** às da calibração anterior (conferido
tabela a tabela), então o "sem" medido antes da recalibração continua válido. O
`calibration.json` empacotado é o novo (corpus `43ac7c57017324d8`).

### 1.6 Quatro defeitos que só a segunda opinião expôs — e o que cada um custou

Cada rodada intermediária está em `benchmarks/reports/sol/` com o mesmo `sem` ao lado:

| rodada | o que mudou | lances | inventados | CER `native` | o que mostrou |
|---|---|---:|---:|---:|---|
| `c1c_rapid` | 3.x calibrado, sem guarda | 0,874 | 321 | 0,0953 | ganha nos degradados, **destrói os scans reais** (`pdf-scan` lances 0,866 → 0,627, inventados 29 → 176) |
| `c1d_rapid` | + guarda de figurinas, ordem por linha em tabelas, número de lance protegido na fusão | 0,891 | 194 | 0,0696 | 54 regiões antes abstidas passam a responder, **41 aceitas** a CER 0,24 |
| `c1f_rapid` | + perdedor da arbitragem com a própria decisão; âncora abstida nunca sai aceita | 0,892 | 177 | 0,0392 | ainda 23 novas respostas no `native` (CER 0,15) e 14 regiões piores onde o RapidOCR venceu |
| `c1g_rapid` | + rota: só nas páginas em que o portfólio entra | **0,893** | **169** | **0,0151** | `native` intocado; nenhuma regressão fora do IC |

1. **RapidOCR ancorava linhas com figurinas** e descarta ♖/♕ (`12 fd1` para `12 ♖fd1`,
   `11d2` para `11 ♕d2`); a troca sósia→figurina do leitor de glifos não tem o que trocar.
   Regra em `OcrService._settle`: onde o leitor de glifos vê figurinas (confiança ≥ 0,70), um
   motor secundário **não ancora**; a leitura do Tesseract fica com a âncora e o RapidOCR entra
   por token. Para isso as leituras dos motores que **perderam** a arbitragem passaram a ser
   candidatas da fusão (`_engine_candidates`) — cada uma com a **própria** decisão, julgada
   pela mesma política sobre o próprio escore (um rótulo "REVIEW" fixo, a primeira versão,
   deixou 41 regiões abstidas saírem aceitas — a linha `c1d`).
2. **Tabela de lances lida coluna a coluna** (§1.4): a SFC4 imprime brancas ao lado de pretas;
   a ordem por coluna deu CER 0,7 em linhas que o motor tinha lido certo.
3. **A fusão trocava número de lance por lance.** `38` não contava como "apoiado" (não é
   palavra nem lance), e um candidato desalinhado por um slot oferecia `g5` com apoio lexical:
   invenção. `fusion._supported` passou a reconhecer o número de lance solto (`38`, `36...`,
   `12.`). Só isto, sem motor novo, tirou 17 inventados do "sem" (`c1b_sem` 308 → `c1e_sem` 291).
4. **A fusão certificava uma âncora abstida.** Com mais candidatos concordando, `decide()`
   levava uma região que o árbitro tinha abstido a ACCEPTED (`♘e4` para `37... ♘e4`: lance
   certo, número perdido — CER 0,24, aceito). SOL-2 diz que abstenção é real; agora **uma
   âncora abstida sai da fusão no máximo como REVIEW** (`test_an_abstained_anchor_comes_out_
   of_the_fusion_as_review_at_most`).

A **régua tem um artefato** que vale registrar: abstenção conta CER 0 na média por estrato.
Um motor que responde onde o outro se abstinha é penalizado pela própria coragem. Por isso a
tabela abaixo, sobre as **669 regiões que os dois respondem** (CER ponderado por caractere), e
as respostas novas à parte:

| estrato | n ambos | CERw sem | CERw com | novas respostas (decisão) |
|---|--:|--:|--:|---|
| `fax_dither` | 61 | 0,0591 | **0,0289** | 2 (revisão) |
| `native` | 173 | 0,0076 | 0,0076 | 2 (1 revisão, 1 aceita, CER 0) |
| `photo` | 62 | 0,1183 | 0,1122 | 1 (revisão) |
| `scan_clean_300` | 137 | 0,0409 | 0,0415 | 0 |
| `scan_degraded_150` | 135 | 0,0387 | 0,0366 | 2 (revisão) |
| `shadow_curl_bleed` | 101 | 0,0301 | 0,0346 | 0 |
| **todas** | 669 | 0,0417 | **0,0387** | 7 (6 revisão, 1 aceita) |

(`scratchpad/compare_sol.py c1e_sem c1g_rapid`; o script é do ciclo e será promovido a
`benchmarks/` se um segundo ciclo o pedir.)

### 1.7 A rota: o motor secundário entra onde o portfólio entra

O serviço não sabe o estrato de uma página; sabe os **sinais** que o portfólio de
pré-processamento (SOL-3) já mede — ruído, sombra, inclinação, resolução, curvatura — e os
limiares com que decide construir uma variante. `caissa.ocr.portfolio.degradation_reasons()`
é essa decisão como função pura; `OcrService._wants_secondary` a consulta por página e
`recognizer_for(lang, secondary=…)` monta a cascata com ou sem os motores de
`secondary_engines` (padrão agora `("rapidocr",)`; `secondary_only_when_degraded=True`). Um
teste segura a rota e o portfólio juntos (`test_degradation_reasons_are_the_variants_the_
portfolio_builds`): a rota nunca promete uma variante que o portfólio não construiria.

**O ✗ que resta**: `shadow_curl_bleed`, taxa de inserção 0,7 % → 1,4 % (CER dentro do IC;
lances 0,861 → 0,935; inventados 42 → 8). Causa vista: o RapidOCR **lê o verso transparente
espelhado** como uma linha (`bsbluoitib sb zism` para "mais de dificuldade" refletido) com
confiança 0,88 e 1/3 de "palavras" no léxico — nem confiança nem dicionário o separam. Fica
registrado como pendência: um detector de texto espelhado, ou preferir a variante
`bleed_sauvola` como entrada do motor secundário nessas páginas.

### 1.8 O que este passo não fechou

- **Russo**: lances 0,405 → 0,493, mas o CER piora (0,068 → 0,089): o `eslav` lê a prosa e
  deixa em branco as linhas densas de notação (`24.Кg5+ Крg8 25.Фh5`). Um dicionário russo
  licenciado (passo 6) e o perfil de lances para o RapidOCR são o caminho.
- **Os quatro portões absolutos de Sol** continuam vermelhos (CER limpo 0,028 vs 0,005;
  150 DPI 0,034 vs 0,020; lances 0,893 vs 0,998; inventados 169 vs 0) — a direção mudou muito,
  o teto do corpus sintético não.
- **Surya**: não medido (Q1).
- **Sabotagem do portão** executada e registrada: `c1c_rapid` **é** a rodada sem a guarda de
  figurinas — o `sol_gate` acusa `native` fora do IC (+0,080, IC a partir de +0,044) e
  `pdf-scan` com 176 inventados. Um portão que não reprovasse essa rodada estaria cego.

### 1.9 Suíte

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr tests\unit\ingest tests\unit\notation tests\integration\test_engine_live.py -q
1040 passed, 2 skipped
```

Testes novos: `test_engine_live.py` (4), `test_rapidocr_order.py` (6), guarda de figurinas e
âncora de prosa em `test_glyph_engine.py` (2), rota em `test_ocr_service.py` (1), portfólio (1),
fusão (2). **Um defeito pré-existente da suíte, não deste passo**: `tests/unit/export` e
`tests/unit/model/test_roundtrip_corpus.py` colidem no nome de módulo `conftest` quando
coletados juntos (`from conftest import CORPUS_NODES` resolve para
`tests/unit/ingest/conftest.py`); reproduz com os arquivos deste passo guardados no `stash`.
O arquivo passa sozinho (210 testes). A suíte inteira, com `--ignore` desse arquivo:

```
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py
3587 passed, 6 skipped, 3 warnings in 707.03s (0:11:47)
.venv\Scripts\python.exe -m pytest tests\unit\model\test_roundtrip_corpus.py -q -p no:cacheprovider
210 passed
```

### 1.10 Arquivos

**Novos**: `tests/integration/test_engine_live.py`, `tests/unit/ocr/test_rapidocr_order.py`,
`docs/quality/sol/c1_sem.{json,md}`, `docs/quality/sol/c1_rapidocr.{json,md}`, este relatório.
**Modificados**: `src/caissa/ocr/engines/rapidocr.py` (3.x por alfabeto, ordem de leitura,
dica de instalação), `src/caissa/ingest/pdf/ocr_service.py` (`secondary_engines`,
`secondary_only_when_degraded`, `_engine_candidates`, guarda de figurinas, rota),
`src/caissa/ocr/fusion.py` (número de lance apoiado; âncora abstida ≤ REVIEW),
`src/caissa/ocr/portfolio.py` (`degradation_reasons`), `src/caissa/ocr/data/weights.json`,
`src/caissa/ocr/data/calibration.json`, `docs/quality/sol/calibration.md`,
`benchmarks/bench_sol.py` (`sol_config` no relatório), `pyproject.toml` (extra `ocr-rapid`),
testes citados.

---

## §2 — Passo 2: o OCR contesta a camada de texto danificada

### 2.0 Em uma tela

O importador chamava o OCR só quando o nível 0 **rejeitava** a camada. Uma página mantida a
0,55 por notação destruída (`mangled_move_ratio > 0,15`, F5-C2) era copiada como estava — e
eram 16 dos 33 livros com camada. Agora `TextLayerVerdict.notation_damaged` nomeia esse caso,
`PdfImportOptions.ocr_contests_text_layer=True` manda a página ao `OcrService` mesmo assim, e
lá a camada é o nível 0 **por região**: abaixo da barra do árbitro, os motores correm; na
fusão a camada **ancora** (`OcrServiceConfig.damaged_layer_anchors=True`: a prosa é a do livro)
e os lances vêm dos motores token a token, porque um lance danificado é uma não-palavra que a
fusão troca por uma leitura apoiada. Uma região **sem lance algum** conserva o próprio veredito
(nada que a fonte quebrada pudesse ter tocado); uma com um lance que seja continua limitada ao
da página (portão cego 15).

Medido de ponta a ponta pelo importador, nas páginas fixas de `notation_integrity.py`
(`--what contest`, novo): sem → com, mesmo código.

| livro | pág. contestadas | lances com peça | **peça certa** | lances perdidos | CER da prosa (palavras) nas contestadas |
|---|---|---|---|---|---|
| Gaprindashvili E8 | 6/8 | 882 → 956 | **265 → 791** | 0 | 0,088 |
| Aagaard E1 | 5/6 | 158 → 195 | **0 → 133** | 0 | 0,012 |
| Nunn E2 (Pawnless) | 5/6 | 414 → 463 | **0 → 320** | 0 | 0,016 |
| Dvoretsky E1 (controle) | 0/4 | 172 → 172 | 170 → 170 | 0 | 0 caracteres alterados ✓ |
| Boleslávski E6 (controle) | 0/4 | 81 → 81 | 10 → 10 | 0 | 0 caracteres alterados ✓ |

"Peça certa" = lance bem formado cujo prefixo é uma letra de peça inglesa **ou uma figurina**
(a fusão emite ♘, a camada de notação canoniza). "Lances perdidos" = lances bem formados que
existiam antes e sumiram: **zero** em toda página. As duas páginas de cada livro que **não**
foram contestadas (Gaprindashvili p158/p190 já eram `ocr` — camada rejeitada; Aagaard p200 e
Nunn p220 estão abaixo do limiar de dano) não mudaram um caractere.

```
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what contest --json benchmarks\reports\ni_c2_contest_layer_anchor.json
```

### 2.1 A âncora: medido dos dois jeitos

A SPEC 1.1 previa a camada acusada "nunca âncora". Medi as duas regras na mesma bancada:

| âncora na região danificada | peça certa (Gap./Aag./Nunn) | CER da prosa (palavras) |
|---|---|---|
| o vencedor da arbitragem (Tesseract, em regra) | 720 / 109 / 258 | 0,094 / 0,022 / 0,068 |
| **a camada, com os motores por token** | **791 / 133 / 320** | **0,088 / 0,012 / 0,016** |

A camada a ancorar ganha nos dois eixos: mais lances recuperados **e** a prosa mais intacta.
É o contrário do que a SPEC supunha e é o que fica (`damaged_layer_anchors=True`); a SPEC
S1 foi corrigida. O motivo é o que a F5 mediu: a camada erra como **ruído só nos tokens de
lance** e acerta a prosa a 98,8 %; com ela na âncora a fusão só toca o que é não-palavra.
(`benchmarks/reports/ni_c2_contest.json` é a rodada com o vencedor na âncora.)

A "CER da prosa" é aproximada: compara só as palavras alfabéticas de ≥ 3 letras com a própria
camada como referência, porque a notação danificada dos dois lados não é prosa; o que resta
de diferença em p202/p230 do Gaprindashvili (0,14) é em parte ordem de leitura entre regiões.
Lido lado a lado em p170 e p202, a prosa é a mesma.

### 2.2 O que ainda não fecha nas páginas contestadas

- **Cifra residual**: em páginas de análise densa que o leiaute trata como uma região só
  (Gaprindashvili p230: 1 região, 154 lances), o Tesseract entrega o sósia (`Hd2`, `Sf2`,
  `2xf6`) e o leitor de glifos abstém sobre a página inteira, então a fusão não tem figurina
  para trocar — é a cifra por livro do **passo 3** (`H`=torre, `S`=rei, `2`=bispo neste
  livro), exatamente o caso para que ela existe.
- **Parágrafos da análise fragmentados** onde o Tesseract ancora (região cuja camada foi
  *rejeitada* por > 60 % de dano e portanto não é candidata): as linhas do OCR viram
  parágrafos curtos (Nunn Minor Piece p150, coluna direita). Comportamento pré-existente das
  páginas `ocr`; agora visível em mais páginas. Fica registrado.
- Custo: ~3 s por página contestada (Tesseract + RapidOCR onde a página é degradada + glifos).

### 2.3 Testes

`tests/unit/ingest/test_importer.py`: página mantida com notação danificada → OCR chamado e vê
`notation_damaged`, fonte `text-layer+ocr`, contador `contested_pages`; opção desligada → não
chamado; camada sã → não chamado. `tests/unit/ocr/test_page.py`: região sem lance conserva o
veredito, região com poucos lances continua limitada. `tests/unit/ingest/test_corpus.py`
(Nunn Minor Piece p150, agora contestada): os cinco parágrafos de prosa continuam inteiros e
a análise volta legível.

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr tests\unit\ingest tests\unit\notation tests\unit\export -q
1508 passed, 3 skipped                                      # suíte inteira: 3590 passed, 6 skipped (11:53), + 210 do test_roundtrip_corpus à parte
```

**Sabotagem do portão**: a rodada "sem" (`ocr_contests_text_layer=False`) **é** a sabotagem
— 0 % de peça certa em toda página contestada — e os dois controles têm de sair com 0
caracteres alterados, o que o instrumento verifica e imprime (`✓ controle intacto`).

### 2.4 O acervo inteiro

```
.venv\Scripts\python.exe benchmarks\bench_ingest.py --sample 12      # benchmarks/reports/ingest_20260914_114656.json
```

46 livros, 552 páginas, **0 falhas**. Fontes de página: `text-layer` 326, `text-layer+ocr` **64**
(12 livros: Aagaard ×2, Euwe Band 1-2 e Band 7, Gaprindashvili, Yusupov ×2, Mieses, Secrets of
Chess Training, Burgess, Nunn ×2), `ocr` 127, `image-only` 27, `rejected` 8. Blocos de lances
(`movetext`) **715 → 1.269** contra a rodada de 2026-09-11 — a notação que a camada trazia
destruída passa a ser reconhecida como lances. Tempo 64 s → 1.569 s: a rodada de 2026-09-11 era
sem OCR algum (o serviço ainda não estava costurado); os 127 `ocr` de páginas só de imagem
pesam mais que os 64 contestados (~3 s cada). Diagramas 74/74, como antes.

---

## §3 — Passo 3: a cifra por livro

### 3.0 Em uma tela

`caissa.ocr.notation.book_cipher.BookCipher`: a tabela **símbolo → peça** de um livro, com a
evidência de cada linha (apoio, contradições, exemplos, fonte da prova), guardada ao lado dos
outros artefatos do livro (`models/tessdata/livros/<slug>/cipher.json`, chaveada pelo hash do
PDF). O importador a carrega, o serviço a alimenta a cada prova e a aplica a cada região com
notação; `PdfImportOptions.book_cipher=False` não lê nem grava.

Medido pela mesma bancada do passo 2 (`notation_integrity.py --what contest`), com as tabelas
aprendidas em **24 páginas disjuntas** de cada livro (metade final do livro, sem as páginas de
teste) e depois aplicadas às páginas de teste:

| livro | peça certa, passo 2 → passo 3 | de | tabela (linhas provadas) | lances perdidos | CER prosa |
|---|---|---|---|---|---|
| Gaprindashvili E8 | 791 → **891** | 973 | 23 (1.884 observações) | 0 | 0,088 (=) |
| Aagaard E1 | 133 → **140** | 198 | 7 (412) | 0 | 0,012 (=) |
| Nunn E2 (Pawnless) | 320 → **346** | 472 | 12 (973) | 0 | 0,014 (=) |
| Dvoretsky, Boleslávski (controles) | inalterado | — | — | 0 | 0 caracteres alterados ✓ |

Somando os três passos no Gaprindashvili: **265 → 891** lances com a peça certa nas mesmas oito
páginas — de 30 % a 92 % dos lances com peça.

```
# aprender (24 páginas por livro, disjuntas das de teste) e depois medir
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what contest --json benchmarks\reports\ni_c3_contest_cipher.json
```

### 3.1 O que a medição mudou no desenho — duas vezes

**A tarefa 0 do passo ("contar primeiro") deu zero.** A evidência prevista era a reprodução
legal: um bloco com posição de partida reproduzido até o fim prova cada símbolo que usou. A
máquina existe e funciona (`test_a_complete_replay_proves_the_assignment_and_rewrites_the_block`:
a partida da Ópera com ♗→`&`, ♕→`W`, ♖→`H` reproduz 33 lances, prova os três símbolos e é
reescrita) — mas no acervo rendeu **0 observações** em 40 páginas do Gaprindashvili com 119
diagramas lidos, e 0 no Burgess, Euwe e Yusupov. O motivo é estrutural: os livros de notação
danificada são **livros de exercícios**, e as páginas danificadas são as de **soluções** — a
posição de cada solução é um diagrama numerado noutra página (`473 L.Seres-P.Kiss, Eger 1990`
refere-se ao diagrama 473, dezenas de páginas antes), e os diagramas dessas páginas saem sem
número (`Diagram.number` vazio: a camada em volta está danificada também). Sem a associação
número → diagrama não há posição, e sem posição não há prova legal. Essa associação é o
"o tronco começa no diagrama" do **passo 11**; fica registrada como pré-requisito dele.

Antes disso a reprodução tinha um defeito próprio: `?xf3` (o *slot* que o decodificador
escreve para "uma peça, não sei qual") **não era um lance** para o reparador — era pulado como
prosa e a reprodução seguia desincronizada em silêncio. Agora `?` é um coringa sobre as cinco
peças, resolvido **só quando uma** o torna legal; com duas legais o token fica sem leitura e
as duas aparecem para o revisor (`test_the_repairer_resolves_a_piece_slot_only_when_one_piece_
is_legal`). E `validate_region` passou a tratar as atribuições de símbolos como hipóteses de
reprodução — como já faz com os idiomas — escolhendo a única que reproduz mais longe
(`_best_assignment`, ≤ 3 símbolos livres, empate = nada).

**A segunda fonte de prova é visual.** O leitor de glifos já faz, na fusão, a troca sósia →
figurina com confiança ≥ 0,70 (SOL-6). Cada troca é uma observação `símbolo → peça` marcada
`glyph`; a tabela exige **10** delas (contra 5 provas legais) e tolera contradições até **2 %**
do apoio — metade da taxa de erro medida do classificador (99,1 %) — porque um desacordo em
cinquenta é o erro dele, não um segundo sentido do símbolo (`test_a_visual_row_tolerates_the_
classifier_error_rate_and_no_more`). Uma letra de peça do idioma do livro **nunca** vira
símbolo (SPEC R2.3): no Nunn a camada usa `R` onde havia ♗, e a tabela recusou a linha
`R → B` — o custo é declarado, o risco de reescrever uma torre impressa não.

### 3.2 O símbolo é do tamanho que o dano deixou

O corretor de cifra tratava só símbolos de **um** caractere (o sósia do Tesseract: `H`, `W`).
A camada de texto danificada, que desde o passo 2 é a âncora, deixa **aglomerados**:
`'it>d1` para ♔d1, `ll:'ixe5` para ♕xe5, `l:tb1` para ♖b1 — consistentes por figurina, e
15 % dos lances com peça do Gaprindashvili depois de todo símbolo de um caractere resolvido.
Três lugares aprenderam o aglomerado, com a mesma regra — curto (≤ 5), com ao menos um
caractere não alfanumérico (uma palavra nunca tem), deixando o mesmo corpo de lance:
`fusion._figurine_cut` (a troca sósia → figurina), `cipher.infer_cipher`/`decode` (o
alfabeto e a reescrita) e a evidência do serviço. Um dígito solto antes de uma casa (`2g5`)
também passou a ser símbolo: um desambiguador de fileira exige letra de peça antes, e o
Tesseract lê ♗ como `2` neste livro.

### 3.3 O que resta

- **Provas legais no acervo**: dependem do índice número → diagrama (passo 11).
- **Símbolos abaixo do piso**: linhas com 5–9 observações ficam "em evidência" e a tabela
  cresce a cada importação do mesmo livro (é o ciclo do FineReader: a segunda leitura sabe
  mais que a primeira).
- **Sósias do Tesseract em páginas sem camada** (scan puro): a tabela aprende com as trocas
  do leitor de glifos da mesma forma; não medido neste passo (as páginas de teste têm camada).

### 3.4 Testes

`tests/unit/ocr/test_book_cipher.py` (9): pisos e contradições, tolerância visual, ida e
volta com impressão digital, reescrita sem posição, notação correta intacta, prosa com um
símbolo intacta, aglomerados, prova por reprodução, empate prova nada, coringa do reparador.
`test_glyph_engine.py`: as trocas alimentam a tabela e `N` impresso não é símbolo.
`test_importer.py`: a tabela é lida e gravada junto dos modelos do livro, `book_cipher=False`
não toca no disco.

**Sabotagem**: a tabela com uma contradição não se aplica (`test_a_row_is_proven_by_five_
legal_proofs_...`); a página correta não muda com tabela nenhuma (`test_the_table_leaves_
correct_notation_and_prose_alone`); os dois controles saem do instrumento com 0 caracteres
alterados.

```
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py
3601 passed, 6 skipped, 3 warnings in 867.53s (0:14:27)
```

---

## §4 — Passo 8: a confiança por diagrama — instrumento construído, portão bloqueado pela população

### 4.0 Em uma tela

Existe agora `caissa.vision.classify.confidence` (os sinais de um tabuleiro reconhecido —
`min_confidence`, média, casas abaixo de 0,90 e de 0,70, menor margem top-1/top-2, casas
reparadas pelo decodificador, fatal, troca de lado, orientação ambígua, via vetorial — e uma
regressão logística L2 sobre eles, só numpy, com AUROC, ECE, Brier e risco × cobertura) e
`benchmarks/diagram_confidence_gate.py`, que corre o conjunto de campo pelo reconhecedor de
produção (3 execuções idênticas, ou reprova), rotula cada diagrama casado contra a anotação com
as duas réguas, ajusta por *leave-one-book-out* e compara com o preditor constante; `--sabotar
ruido` troca os sinais por ruído.

**O que a medição disse: não há o que ajustar.** Dos 114 diagramas casados, **96 têm FEN
anotada**, e desses **94 são exatos** (régua corrigida) — **2 negativos**. Nenhum modelo se
ajusta com dois negativos, nenhum portão de discriminação se julga (AUROC fora da dobra 0,02
com os sinais reais, 0,12 com ruído — indistinguíveis; `min_confidence` sozinho dá 0,88 sobre
os mesmos dois), e o gate reprova nas duas rodadas **por falta de população, não por falta de
sinal**. Nenhum peso foi empacotado; `default_confidence()` devolve `None` e quem chama
continua com `min_confidence`, dizendo-o.

```
.venv\Scripts\python.exe benchmarks\diagram_confidence_gate.py --runs 3                   # REPROVOU: negativos 2
.venv\Scripts\python.exe benchmarks\diagram_confidence_gate.py --runs 3 --sabotar ruido   # REPROVOU: indistinguível
```

### 4.1 O que a extração corrigiu na análise (D1)

`OCR_UI_ANALISE.md` §2.2 lia a tabela do `F4_FIELD_REPORT.md` §2.1 (`scan-hachurado`: 21
casados, 10 `exported_comparable`; `scan-puro`: 44 casados, 35) como "20 diagramas certos
barrados pelo portão". Errado: `exported_comparable` exige FEN anotada, e **19 dos diagramas
anotados não a têm** (9 hachurados, 10 scan-puro — contados com
`chess_diagram_ocr.field_eval.load_field_set`). Os barrados de verdade são **2**, os dois do
Levenfis p150 (hachurado): um **exato** com `min_confidence` 0,30 depois de 1 reparo — o caso
aritmético do `decode.py`, 1 em 96 —, e um errado com 0,07 e 2 reparos, que o portão barra
bem. O portão de exportação, no conjunto de campo, perde **um** diagrama certo. A linha 6 da
tabela da análise e o passo 9 do roadmap ficam corrigidos: a alavanca ali é **anotar** (os 19
sem FEN e mais livros), não mexer no piso.

### 4.2 O que fica

- Sinais e instrumento prontos; testes em `tests/unit/classify/test_diagram_confidence.py`
  (o ajuste separa o separável, as métricas respondem 0,5/0 a uma constante, ida e volta dos
  pesos, sinais lidos de um diagrama).
- **Pré-requisito humano, registrado como passo 0b no roadmap**: anotar a FEN dos 19
  diagramas sem ela e acrescentar diagramas **errados** ao conjunto (a fila da aba Dataset por
  menor `min_confidence` os encontra) — ≥ 30 negativos é o mínimo para um modelo de dez sinais
  dizer algo. Enquanto isso, o âmbar da UI e a fila de revisão seguem em `min_confidence`.
- Os passos 9, 13 (âmbar por p(exato)) e 18 dependem disto e ficam suspensos até lá.

---

## §5 — Passo 6: o dicionário russo e os lances que não são palavras

### 5.0 Em uma tela

- **`rus.dic.gz` / `rus.aff.gz`** no léxico empacotado: o `ru_RU` do repositório de dicionários
  do LibreOffice (146.269 radicais, 1.606 regras), **BSD-3-Clause**, Alexander I. Lebedev
  1997–2008 — licença lida **antes** de baixar; o aviso viaja no pacote como
  `LICENSE_ru_RU.txt`, como a BSD exige. A máquina não tinha `dict-ru`; o arquivo foi buscado
  uma vez para `models/hunspell/ru_RU/` (fora do git) e `tools/build_lexicon.py` o empacota
  como os outros três. Os `eng/por/spa` reconstruídos saíram byte a byte idênticos ao HEAD
  (conferido pelo SHA do conteúdo descomprimido) e foram mantidos.
- **Acerto de dicionário nas cinco páginas fixas do Boleslávski (E6)**: 25 / 20 / 13 / 22 / 25 %
  → **62 / 55 / 48 / 53 / 73 %** (`notation_integrity.py --what verdicts`, com e sem o
  `rus.dic.gz`). Nenhum veredito mudou; o Sol nos 9 itens sintéticos russos das partições
  `dev`+`calib` sai idêntico (o dicionário pesa na plausibilidade, não na leitura).
- **Um lance danificado não é uma "palavra impronunciável".** `lexicon.nonword_ratio` passou
  a pular os tokens que `is_mangled_move` reconhece — `Wh2t`, `t2'ic4`, `Elxg7t` são notação
  cujo glifo não sobreviveu, com sinal próprio. Efeito, medido:

| página | antes | depois |
|---|---|---|
| Yusupov *Build Up* p. 700–701 (soluções, 87–136 lances) | **rejeitada** — "55 % impronunciáveis" (29 dos 40 eram lances) | mantida a 0,55, notação danificada → **contestada** pelo passo 2 |
| Gaprindashvili p158 | rejeitada — 48 % — página inteira ao OCR | mantida a 0,55 (37 % de 149 lances) → contestada: 137 lances com peça, **95 %** certos, prosa do livro (CER 0,054) |
| Nunn *Minor Piece* p150, coluna direita | camada rejeitada, parágrafos da análise fragmentados pelo Tesseract | camada mantida: a análise fica **um parágrafo** com os lances legíveis dentro |
| os 16 livros acusados, os 2 controles | — | vereditos inalterados (`--what verdicts`) |

```
.venv\Scripts\python.exe tools\build_lexicon.py
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what verdicts
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what contest --json benchmarks\reports\ni_c6_contest.json
```

O `sol_gate.py` compara o hash do manifesto do léxico com o do baseline congelado e vai
acusar a diferença até o baseline ser recongelado — correto: o léxico mudou.

### 5.1 O que a medição mudou

A sabotagem prevista no roadmap ("contar o token danificado como lance válido no
`mangled_move_ratio`") não foi necessária como sabotagem: a mudança de fato foi a inversa — tirar
o token danificado do `nonword`, deixando o `mangled` como está — e os dois testes de corpus que
fixavam o comportamento antigo (`test_gaprindashvili_third_party_ocr_layer`: "p158 rejeitada";
`test_nunn_ocr_layer_keeps_the_paragraphs_whole`) reprovaram na hora e foram reescritos com o
motivo. O p158 é o caso a vigiar: da rejeição (OCR da página inteira, 98 % das peças) passou à
disputa (camada na âncora, 95 %) — três lances a menos e a prosa do livro no lugar da do
Tesseract.

### 5.2 Testes

`test_lexicon_package.py::test_the_russian_hunspell_dictionary_answers_prose_and_refuses_garbage`
(o pacote tem o dicionário e o aviso; prosa russa ≥ 0,9; espelhado 0/3); os dois testes de corpus
acima. Suíte `tests/unit/ocr` + `tests/unit/ingest` verde.

---

## §6 — Passo 5: a fila de rotulagem por valor de rótulo

### 6.0 Em uma tela

- **«Próxima que vale»** na aba Rotulagem (Qt) e na bancada Tk, e `caissa-rotular --sugerir`
  sem janela (`caissa.ocr.labeling.queue`; `ROTULAGEM.md` §8 tem a tabela de pesos). Pontua
  uma amostra espaçada das páginas não rotuladas pelo que um rótulo mudaria: linhas em regiões
  `REVIEW`/`ABSTAINED` (1), linhas duvidosas em regiões aceitas (0,5), blocos `movetext` sem
  `start_fen` (3), item do livro sem idioma/estrato no manifesto privado (+2), livro sem rótulo
  (×1,5); **linhas na partição cega valem 0** — a partição é função do id, a fila sabe antes.
  Em thread, cancelável entre páginas pelo segundo clique (R3.5), progresso na barra de estado,
  lista com o porquê e «Abrir página»; a lista fica em cache até «Recalcular».
- **Medido em três scans sem camada de texto** (Koblenz 1978 `spa`, Levenfis 1962 `ron`, Estrin
  1980 `deu`; 12 páginas cada a 300 DPI, projeto vazio): a ordem da fila **é** a ordem do
  oráculo (páginas ordenadas pelas linhas em revisão de fato) nos três livros — captura do
  oráculo no top-5 = **1,00 / 1,00 / 1,00**; com a sabotagem (pontuação constante → ordem
  sequencial) cai para **0,47 / 0,60 / 0,58** e o portão reprova.
- **O portão do roadmap ("top-5 ≥ 2× a mediana") era inatingível e foi reescrito.** Nestes
  scans o serviço manda **todas** as linhas fora da cega para revisão (top-5: 280/280,
  310/310, 287/287 linhas), então a distribuição de linhas `REVIEW` por página é a distribuição
  de linhas por página, comprimida: a razão do próprio oráculo é **1,27 / 1,22 / 1,08**. Nenhuma
  ordem clareia 2×. A bancada imprime a razão do roadmap **e o seu teto** (a do oráculo), e o
  portão passou a ser o que a fila controla — captura do oráculo ≥ 0,90 em cada livro.

```
.venv\Scripts\python.exe benchmarks\labeling_queue.py --pdfs 3
#   Koblenz  razão 1.27 (teto 1.27) captura 1.00 ✓ | Levenfis 1.22 (1.22) 1.00 ✓ | Estrin 1.08 (1.08) 1.00 ✓ → PASSOU
#   relatório: benchmarks\reports\labeling_queue_20260914_182959.json
.venv\Scripts\python.exe benchmarks\labeling_queue.py --pdfs 3 --sabotar constante
#   razão 0.60 / 0.72 / 0.63 · captura 0.47 / 0.60 / 0.58 → REPROVOU  (sabotagem: constante)
#   relatório: benchmarks\reports\labeling_queue_20260914_183438_constante.json
```

Antes da reescrita, o portão original foi executado tal como o roadmap o escreveu: rodada real
razão 1,27 / 1,22 / 1,08 → REPROVOU; sabotagem 0,60 / 0,72 / 0,63 → REPROVOU
(`labeling_queue_20260914_152236.json`, `labeling_queue_20260914_152725_constante.json`). O
portão via a sabotagem (a razão cai à metade) — a barra é que estava fora do alcance de qualquer
fila.

### 6.1 O que a medição disse além do portão

- **Em livro digitalizado antigo, a decisão por linha não discrimina: é tudo `REVIEW`.** As 36
  páginas têm 0 linhas "duvidosas em região aceita" porque não há região aceita. O valor da fila
  nesses livros é, na prática, *quantas linhas a página tem fora da cega* — útil (a página de
  índice com 0 linhas vai para o fim; a de 77 vai para o começo), mas não é "onde o serviço
  erra". Onde a fila deve separar de verdade é em livros de impressão limpa, em que a página
  aceita em bloco (SFC4: 86 de 87 linhas aceitas) fica atrás da página com dúvida. Isso não foi
  medido aqui — os três livros da bancada são os scans em que rotular custa mais — e fica
  registrado como limite do resultado.
- **Zero blocos `movetext` nos 432 blocos amostrados**: `label_page` divide a região de página
  inteira pelos parágrafos do motor (`kind="paragraph"`), e o analisador de leiaute não emitiu
  `MOVETEXT` nesses scans. O peso 3 do `start_fen` existe e está testado, mas não pesou nesta
  medição.
- **A partição cega leva 13–24 % das linhas** (41/321, 100/410, 95/382 no top-5): a fila as
  desconta, e a lista diz quantas ficaram de fora em cada página.
- Custo: 2,5 s/página (Koblenz, Estrin) a 6,7 s/página (Levenfis, 306 páginas de scan cinzento)
  a 300 DPI — 12 páginas em 30–80 s. O revisor vê "pontuando página N (k/12)" e pode cancelar.
- Os dois relatórios da sabotagem repetem, página a página, as contagens da rodada real (a
  sabotagem pontua de novo as mesmas páginas para saber o que a ordem constante entregou): o
  reconhecimento é determinístico entre execuções.

### 6.2 Testes

`tests/unit/ocr/test_labeling.py` (+4: os pesos e a partição cega; livro novo e faceta vazia;
`BookContext` lendo projeto e manifesto; `rank_pages` amostra, pula rotuladas, ordena, cancela e
aceita a pontuação constante da sabotagem) e `tests/unit/ui/test_rotulagem_view.py` (+1: o botão
pontua em thread, vira «Cancelar fila» enquanto roda, abre a lista com a melhor página primeiro,
«Abrir página» navega, o segundo clique reabre sem pontuar de novo).

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr\test_labeling.py -q                                  # 13 passed
set PYTHONPATH=.venv-pack\Lib\site-packages && .venv\Scripts\python.exe -m pytest tests\unit\ui\test_rotulagem_view.py -q   # 6 passed
.venv\Scripts\python.exe -m pytest tests\unit\ocr tests\unit\ingest -q                                # 731 passed, 2 skipped
```

---

## §7 — Passo 4: negativos e peças raras no ajuste fino

### 7.0 Em uma tela

- `caissa/ocr/training/negatives.py`: **negativos** = linhas de prosa do livro sem figurina,
  re-renderizadas sob vinheta de foto, ruído, manchas e fax **com margens só de textura** dos
  dois lados (a verdade fica; o `lstmtraining` pula verdade vazia, então "textura → nada" só
  se ensina pelas margens); **peças raras** = linhas da peça abaixo da mediana repetidas na
  `list.train`. `FineTuneConfig.negatives` / `.oversample_rare`, `caissa-treinar --negatives
  --oversample-rare`, duas caixas no *Treinar…* (Qt e Tk); o relatório do treino diz quantos
  negativos entraram e as cópias por peça. `Medir no livro…` publica figurinas inventadas e o
  placar por peça (`MeasureGroup.by_piece`, `figurines_invented`).
- **Modelo sozinho** (Tesseract ajustado como âncora, sem leitor de glifos nem segundo motor):
  controle `photo` com A (o modelo de 2026-09-14): responde 57 caracteres; com D (120
  negativos com margens): **0 figurinas**; `synth/fax_dither` inventados 206 → **126** (base
  `eng` 76). Sabotagem C (negativos = 0, raras 1,0): `♖.♖♘♘` no `photo`, 184 no fax. D2 (360
  negativos): pior — `♔.♔4u♔♔` no `photo`, 146 no fax: mais negativos não é monotônico, e um treino por configuração (uma semente) não separa 126 de 146.
- **No livro** (avaliação `calib`, 261 linhas, caminho do produto): D ≥ A em tudo — lances
  273 vs 271, figurinas 193 vs 191, ♘ 62 vs 61, inventados 9 vs 10, exatas 241 vs 238; peça
  mais rara ♔ 15/17 (88 %). Modelo sozinho: **204/204** figurinas, ♔ 17/17 — desde A.
- **Portão**: `photo` sem figurina ✓ (mas responde — o `eng` base abstém: FP de SOL-2 para o
  modelo sozinho, não para o produto, que só o usa como candidato); fax inventados ≤ base
  **✗** (126 > 76; −39 % sobre A); cada peça ≥ antes e a rara ≥ 75 % ✓; lances no livro ≥ antes
  ✓. Sabotagem executada e vista ✓.
- **Achado**: a fusão perde 11 figurinas e 10 lances que o modelo do livro já lê (204/204,
  282/288 sozinho vs 193/204, 273/288 no produto) porque ele nunca ancora. Passo 4b inserido.

```
# antes (A = models\tessdata\livros\dvoretsky_mark_yusupov_artur_sfc4_secret)
.venv\Scripts\python.exe -m caissa.ocr.training.cli --project labeling --document "<SFC4>" --base-lang eng ^
  --base-model models\tessdata_best\eng.traineddata --iterations 12000 --negatives 120 --oversample-rare 1.0 --out <D>
.venv\Scripts\python.exe -m caissa.ocr.training.cli ... --negatives 0 --oversample-rare 1.0 --out <C>     # sabotagem
.venv\Scripts\python.exe -m caissa.ocr.training.cli ... --negatives 360 --oversample-rare 1.0 --out <D2>
set SOL_CONFIG={"glyph_candidates": false, "figurine_candidates": false, "secondary_engines": []}
.venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --filter control --tessdata-dir <modelo> --model-prefix caissa
.venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata fax_dither --tessdata-dir <modelo> --model-prefix caissa
#   base: photo abstém, fax inventados 76 · A: 206 · B (120 sem margens): `De ♕a1`, 133 · C: `♖.♖♘♘`, 184 · D: 0 fig., 126
#   (scratchpad: bench_model.sh, summ_bench.py; medidas no livro: measure_sfc4.py, measure_alone.py)
```

### 7.1 O que a medição mudou no desenho

- **Margens de textura.** A primeira versão dos negativos (linha degradada, sem margens) não
  tirou a figurina do controle (`De ♕a1`). A supervisão que faltava é "textura → nada", que o
  Tesseract só aceita como margem de uma linha com verdade. Com as margens, 0 figurinas.
- **O portão do fax fica vermelho**, e fica registrado assim: o modelo do livro sozinho
  inventa mais que o `eng` em tipografia degradada (126 vs 76) mesmo com negativos. É a razão
  de ele seguir candidato secundário fora do seu livro; o produto não muda nos controles
  (0 → 0, como no §4c). Não vale gastar mais treinos aqui: o número que importa ao produto é
  o do livro, e esse está fechado.
- **Peça rara**: já resolvida pelo retreino sobre `eng` de A (♔ 17/17 sozinho). A caixa de
  sobreamostragem fica (custo zero; +19 cópias de ♔) mas não foi ela que mudou o placar.

### 7.2 O que fica

- Modelo do livro registrado para o SFC4 = **D (120 negativos com margens, raras 1,0; sha256 `57df721f0bf25e21…`, `lstmeval` 1,43 %)** (`models/tessdata/livros/…`,
  `livros.json`); o de 2026-09-14 (A) guardado fora do git.
- Padrões do diálogo: `RECOMMENDED_NEGATIVES = 120`, `RECOMMENDED_OVERSAMPLE = 1.0`.
- Testes: `test_training.py` (+4: degradações com margens, determinismo, só prosa como fonte,
  sobreamostragem até a fração da mediana, o treinador põe negativos e cópias na lista e a
  sabotagem os tira), `test_measure.py` (placar por peça e figurinas inventadas),
  `test_rotulagem_view.py` (as duas caixas chegam ao `FineTuneConfig`).

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr\test_training.py tests\unit\ocr\test_measure.py -q      # 18 passed
set PYTHONPATH=.venv-pack\Lib\site-packages && .venv\Scripts\python.exe -m pytest tests\unit\ui\test_rotulagem_view.py -q   # 6 passed
```

---

## §8 — Passo 4b: o modelo do livro na âncora, dentro do livro

### 8.0 Em uma tela

- `OcrServiceConfig.book_model_anchors` (ligado) + `TunedTesseractEngine`
  (`ocr/engines/tesseract.py`): com `figurine_tessdata` apontando para o livro **registrado
  para o PDF**, o modelo do livro é o motor âncora do seu idioma (`eng` lido com `caissa_eng`,
  resultado devolvido como `eng`, `meta["model"]` diz quem leu); o candidato de figurinas
  fica de fora nesse caso. Sem registro, ou idioma do livro sem modelo: nada muda.
- **SFC4, `calib`, caminho do produto**: figurinas 193 → **204/204**, lances 273 → **281**/288,
  inventados 9 → **5**, exatas 241 → 243, todas as peças 100 %. Portão (≥ 200 e ≥ 280) ✓.
- **Sabotagem (registro cruzado)**: o modelo do SFC4 ancorando um livro inglês de notação em
  letras emite **519 figurinas** em 6 páginas (base 0, candidato 9) — o isolamento por
  impressão digital é o que segura o risco, e o portão o vê.
- **`bench_sol` idêntica** à anterior (Δ 0,0000 em todos os estratos; controles 0/9;
  `c1_anchor.json`): sem livro registrado o âncora não entra. Os quatro portões absolutos
  continuam vermelhos como estavam.

```
.venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --label c1_anchor --publish --compare docs\quality\sol\c1_rapidocr.json
#   ✓ regressão de CER em 6/6 estratos (Δ ≤ 0,0001) · controles 0/9 · lances 6295/7047 (0,8933; antes 0,893)
.venv\Scripts\python.exe -m pytest tests\unit\ingest\test_ocr_service.py tests\unit\ocr\test_measure.py -q   # 19 passed
# medida no livro e sabotagem: scratchpad measure_sfc4.py / sabotage_cross.py (ROTULAGEM.md §7h tem as tabelas)
```

### 8.1 Testes

`test_ocr_service.py` (+2: o modelo toma o assento do Tesseract só com `figurine_tessdata` de
livro e só no idioma que tem modelo — a pasta global e `book_model_anchors=False` mantêm o
candidato; `TunedTesseractEngine` mapeia `por+eng → por+caissa_eng` e devolve o idioma pedido
com `meta["model"]`), o teste do importador atualizado (`book_model_anchors` ligado).

---

## §9 — Passo 10: fallback para glifo vetorial fora do catálogo — e o buraco que ele achou

### 9.0 Em uma tela

- **População zero.** `vector_survey.py --sample 24` (46 livros): **nenhum** livro do acervo
  tem fonte de xadrez fora do catálogo (`unknown_chess_fonts` vazio em 46/46); os dois
  livros "fonte" são o DEM (Chess Merida, verificada) e o Polgar 5334 (SkakNew, `inferred`).
  As fontes de figurina inline (SemFig, SkakNew-Figurine) também estão catalogadas. A tarefa 2
  (figurina inline em fonte desconhecida) fica **sem população** e não foi construída; a
  tarefa 3 (segundo livro SkakNew) idem — o survey diz que não há.
- **Construído (tarefa 1)**: `detect_unknown_font_lattices` (`vision/detect/vector_detect.py`,
  sem torch): o reticulado 8×8 de glifos de uma fonte de xadrez que o catálogo não conhece —
  a geometria é exata mesmo quando o mapa glifo → peça não é; devolve o retângulo das casas
  (união das caixas dos 64 glifos). `inferred_font_finder` (`ingest/pdf/finders.py`): renderiza
  esse retângulo a 300 DPI e o classificador de casas lê; `RecognitionPath.VECTOR_INFERRED`,
  confiança **≤ 0,85**, `method` com o nome da fonte; entra no `combined_finder` entre a via
  vetorial e a raster. Sem catálogo escondido, não faz nada (0 inferidos nos dois livros).
- **Medido pela sabotagem do roadmap** (Merida e SkakNew escondidas do catálogo, 24 páginas
  por livro): DEM 35/35 reticulados lidos, **35/35** iguais à leitura exata; Polgar 114/114
  lidos, **114/114** iguais à leitura do produto; confiança máx. 0,85. Sabotagem da bancada
  (`--sabotar cobertura`, leitura espelhada) reprova.
- **O achado**: na primeira medição o Polgar concordava em **46 %** — e o erro era da via
  **exata**. O extrator omite todo glifo de **torre em casa escura** da SkakNew (sem mapa
  Unicode); a via exata tomava a casa ausente por vazia ("provavelmente vazia no xadrezado")
  e publicava a posição errada a 0,79–0,82: **61 de 114 diagramas** do Polgar. Correção:
  uma casa ausente deixa de ser exata (`HOLE_CONFIDENCE_CAP` 0,60, detalhe no laudo,
  `DiagramHit.holes`, não confiável para o serviço de OCR); o `combined_finder` completa as
  casas ausentes com o classificador **só onde a fonte se calou** (`fill_holes`: toda casa que a
  fonte deu tem de coincidir) e marca `VECTOR_INFERRED`. Polgar: 61/61 completados.

```
.venv\Scripts\python.exe benchmarks\vector_survey.py --sample 24            # 46 livros, unknown_chess_fonts = 0
.venv\Scripts\python.exe benchmarks\vector_inferred_gate.py --sample 24    # PASSOU (vector_inferred_20260914_211441.json)
.venv\Scripts\python.exe benchmarks\vector_inferred_gate.py --sample 24 --sabotar cobertura   # REPROVOU
#   DEM: exatos 35, com casas ausentes 0 | família oculta: 35 lidos, 35 concordam, conf. máx 0,85
#   Polgar: exatos 114, com casas ausentes 61 → 61 completados | família oculta: 114 lidos, 114 concordam
```

### 9.1 O que a medição disse, com as ressalvas

- A concordância de 100 % nas 88 tábuas **sem** casas ausentes (35 DEM + 53 Polgar) é
  classificador contra fonte, independentes: é a medida do fallback. Nas 61 com casas
  ausentes, as casas presentes são verificadas pela fonte e as ausentes são classificador
  contra classificador (mesmo modelo, mesmo recorte) — ali a concordância não é prova; a prova
  é a inspeção (Polgar p. 91: a torre em a5 está impressa e a via exata a omitia) e o fato de
  as 61 diferenças serem **todas** torres em casa escura.
- Onde o produto usa só a via vetorial (a exportação da aba, sem torch), o Polgar sai agora
  com as 61 posições a 0,60 e o aviso — incompleto e dito; com o classificador
  (`combined_finder`, `bench_ingest --raster`) sai completo a ≤ 0,85. A leitura exata dos
  livros sem casas ausentes (DEM 23/24 páginas exatas) não muda: mesma FEN, mesma via
  (`inferidos com catálogo = 0`).
- O que este passo não fez: figurina inline em fonte desconhecida (sem população) e subir a
  SkakNew a `verified` (sem segundo livro; e o que faltava nela não era o mapa, era o extrator).

### 9.2 Testes

`tests/unit/detect/test_inferred_font.py` (6): o reticulado com a família escondida é o
retângulo das casas (Merida sintética); o `inferred_font_finder` lê pelo classificador com a
confiança limitada, não toca livro catalogado e sem pesos localiza sem ler; a ordem do
`combined_finder`; `fill_holes` só onde a fonte se calou, com o tabuleiro virado; uma casa
ausente derruba a confiança e sai em `holes`. `test_importer.py` intacto (`trusted` exige
via `VECTOR` **sem** buracos).

```
.venv\Scripts\python.exe -m pytest tests\unit\detect tests\unit\ingest -q     # 235 passed
```

---

## §10 — Passo 12: a fita com portões próprios — rótulos, cabeçalhos, ícones

### 10.0 Em uma tela

- **Dois portões novos** em `caissa.ui.audit`: `fita` (todo botão com rótulo **desenhado** — a
  dica não conta, R3.4; cabeçalho de cada grupo em toda densidade e largura; hit ≥ 40 px nos
  dois eixos; altura dentro do orçamento) e `icones` (traço ≥ 2 px no tamanho desenhado, caixa
  menor ≥ 60 % do lado, tinta ≥ 10 % do lado²). Um processo por pele × densidade, larguras
  1280/1366/1920, JSON + tabela, `--sabotar`. Promovidos dos scripts avulsos de
  `benchmarks/reports/ui/c12/`, que imprimiam e não julgavam.
- **A fita mudou no tronco** (quatro arquivos, registrados como pares reaplicáveis em
  `docs/quality/ui/c17/tronco_passo12.py` — ver §10.2 sobre por que não há commit lá):
  `Comando.rotulo_na_fita`/`na_fita` (os seis botões de glifo ganham palavra: "Menos zoom",
  "Mais zoom", "Lance anterior"…; "Apagar a peça" na fita devolve o pleno a 1.920 px); o
  cabeçalho do grupo desenhado **também no compacto** (orçamento 64 → 72 px, contado na função
  pura); `desfazer`/`refazer` redesenhados (caixa 20×9 → 20×18 px).
- **Antes → depois** (mesmos scripts do ciclo 12, mesma janela): botões com rótulo **18/24 →
  24/24**; cabeçalhos na compacta **0/5 → 5/5** (em 1280, 1366 e 1920, nas duas densidades);
  hit mínimo 43×49 px ✓; altura compacta 59–62 px (orçamento 72), plena 98 (120). Ícones:
  96 medidos em 4 arranjos, 0 com defeito, tinta 11,2–51,5 %.
- **Sabotagens executadas**: `--sabotar rotulo_na_dica` (o texto de um botão vai para a dica)
  → `fita` acusa 1 por medição, REPROVOU; `--sabotar tinta` (traço a 1 px) → `icones` acusa
  96/96, tinta 1,1–7,4 %, REPROVOU. `texto_pintado` continua PASSOU nos dois casos — é a régua
  que não via.
- **Os outros portões sobre a fita nova**: `texto_pintado` 540 medidos, 0 cobertos, 0
  cortados; `contraste` 300 pares claro e 300 escuro, 0 reprovados; `teclado` 0/0/0 nas 6 abas ×
  3 peles + 13 diálogos; `comandos` 385 medidos, 0 soltos, 0 prometem.

```
set AUDIT=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit
set PYTHONPATH=src
%AUDIT%.fita   --saida benchmarks\reports\ui\c17                              # 144 botões, 0 sem rótulo, 0 cabeçalhos ausentes → PASSOU
%AUDIT%.fita   --saida benchmarks\reports\ui\c17 --sabotar rotulo_na_dica    # 6 sem rótulo (1 por medição) → REPROVOU
%AUDIT%.icones --saida benchmarks\reports\ui\c17                              # 96 ícones, 0 com defeito, tinta 11,2–51,5 % → PASSOU
%AUDIT%.icones --saida benchmarks\reports\ui\c17 --sabotar tinta             # 96/96 com defeito → REPROVOU
%AUDIT%.texto_pintado --pdf "%PDF%" --saida benchmarks\reports\ui\c17         # PASSOU (540 medidos, 0/0)
%AUDIT%.contraste --saida benchmarks\reports\ui\c17                           # PASSOU (0 reprovados, claro e escuro)
%AUDIT%.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c17               # PASSOU (0/0/0)
%AUDIT%.comandos --pdf "%PDF%" --saida benchmarks\reports\ui\c17              # PASSOU (385, 0 soltos)
%AUDIT%.capture --pele fita --marca depois_<densidade> --pdf "%PDF%" --saida benchmarks\reports\ui\c17\capturas
#   retratos: docs\quality\ui\c17\fita_compacta_1366_depois.png, fita_plena_1920_depois.png
#   relatórios publicados: docs\quality\ui\c17\fita.json, icones.json
```

### 10.1 O que a medição mudou no desenho — e um portão reescrito

- **"Tinta ≥ 50 %" era o número errado para ícone de traço.** Um disco cheio tem 78 % de
  tinta, uma seta cheia 50 %; todo ícone de linha desta fita (traço declarado de 9 % do lado)
  fica entre 11 e 52 % por construção, e cobrar 50 % seria cobrar silhuetas. O portão de
  ícones cobra o que mede legibilidade em traço — traço ≥ 2 px no tamanho desenhado, caixa que
  enche o lado, tinta ≥ 10 % — e a sabotagem (traço a 1 px) prova que ele vê. Registrado no
  roadmap como portão reescrito.
- **Rotular os seis empurrou o modo pleno para fora do Full HD** (1.926 px pedidos a 1.920): o
  compacto assumia a tela mais comum. A resposta foi o texto de fita do botão mais largo
  ("Apagar a peça da / casa selecionada", 122 px → "Apagar a peça"): o pleno volta a 1.920 com
  1.874 px. Menu e botão continuam por extenso — o campo `rotulo_na_fita` é novo e é o único
  que muda.
- **O compacto com cabeçalho custa 59–62 px**, dentro dos 72 do orçamento novo (e dentro dos
  64 antigos na fonte do produto; o orçamento subiu para que uma fonte de sistema maior não o
  estoure por causa da linha auxiliar).

### 10.2 Onde as mudanças do tronco estão

O tronco (`ChessVisionOFF_Puro`) tem sessenta arquivos modificados e catorze novos **não
commitados** por outra sessão (os ciclos 9–16 da frente F9; `HEAD` é "Corta o tkinter"). Um
commit por caminho nos quatro arquivos deste passo levaria junto esse trabalho. As mudanças
ficam na árvore de trabalho do tronco e, aqui, como pares (antes, depois) reaplicáveis:
`docs/quality/ui/c17/tronco_passo12.py` (`--aplicar`, `--reverter`, sem argumento confere), mais
o `tests/test_qt_fita.py` resultante (`tronco_test_qt_fita_depois.py`). Quem commitar o tronco
leva estes quatro junto; até lá, o script diz se a árvore está com eles.

### 10.3 Testes

Tronco: `tests/test_qt_fita.py` (três testes que fixavam a decisão antiga — cabeçalho na dica,
glifo sem texto, seguidor de estado — reescritos com o motivo), `test_ui_comandos.py`,
`test_ui_icones.py`: 71 passed, 607 subtests. Suíte:
`tests/unit/ui/test_audit_fita.py` (4: o que é rótulo e o que é dica, o hit nos dois eixos,
os três defeitos e o orçamento, o ícone pelo traço/caixa/tinta).

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests\test_qt_fita.py tests\test_ui_comandos.py tests\test_ui_icones.py -q -p no:randomly   # 71 passed
.venv\Scripts\python.exe -m pytest tests\unit\ui\test_audit_fita.py -q                                                                # 4 passed
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly -p no:cacheprovider                                 # 4487 passed, 3 failed — os 3 são dos módulos novos de outra sessão (biblioteca, substituicao, desenho_de_diagrama, pdf_substituicao: acento, README, lista sem Tk), não deste passo
```

---

## §11 — Passo 7: o lado a jogar pela numeração do lance seguinte

### 11.0 Em uma tela

- **A regra, nas duas cascatas.** Suíte (`ingest/pdf/captions.py`): quando nenhuma palavra
  declara o lado, o **primeiro lance impresso sob o diagrama** decide (`22... ♖g8` → pretas,
  `23 ♘c4` / `23.Nc4` → brancas; origem `move-number`, confiança 0,9), e depois dele a legenda
  «após/after/nach/después/после N.x» (a posição *depois* daquele lance, origem
  `caption-after`, 0,85). Ordem: texto declarado → numeração → legenda «após» → escopo de
  página → (legalidade, no tronco) → `default`. O alcance da numeração é de 200 pt abaixo do
  tabuleiro, na mesma coluna — mais que o raio de legenda (60), porque no SFC4 um parágrafo de
  comentário separa o diagrama da coluna de lances (p. 12: 96 pt). Tronco
  (`pdf_text.py`, `semantics.py`, `procedencias.py`; commit `8d0f18c` **no tronco**, três
  arquivos que estavam limpos lá): mesma regra, mesmos dois valores em `SideOrigin`/`SideSource`.
- **A origem vai ao IR**: `RecognitionResult.side_to_move_source` (R2.5) — no registro do
  reconhecimento, não em `Diagram`, porque é proveniência de máquina e não sai para EPUB/DOCX;
  o relatório de importação conta `side_to_move_origin:<origem>`, com `default` dito.
- **Portão (verdade humana, `benchmarks/side_to_move_gate.py`)**: as regiões com `start_fen`
  do passo 0 fora da cega — **n = 6** —, o texto do revisor como texto da página e os
  tabuleiros do detector do tronco: **acerto 6/6, origem ≠ default 5/6** (a que fica é a
  partida do lance 1 sem diagrama, onde `default` = brancas é o certo). Sabotagem (paridade
  invertida): acerto 1/6 = 0,17 → REPROVOU. **PASSOU.**
- **Produto (OCR + via raster, informativo)**: 4/6 — p17 sem diagrama (default), p18 o OCR
  leu a linha «18... ♔h8!!» sem os três pontos e a numeração deu brancas.
- **Acervo** (`bench_ingest --sample 12 --raster`, 46 livros, 911 diagramas): origem ≠
  `default` **109 → 267** (`move-number` 142, `caption-after` 11, texto 92, OCR 13, escopo de
  página 9). **Abaixo dos ≥ 500 do roadmap**: 644 seguem `default`, em boa parte livros de
  problemas (mate em N sem lance impresso) — ali não há numeração a ler; o que sobra são
  legenda simbólica e escopo de página, que já estavam.

```
.venv\Scripts\python.exe benchmarks\side_to_move_gate.py                      # n=6: acerto 1.00, origem≠default 0.83 → PASSOU
.venv\Scripts\python.exe benchmarks\side_to_move_gate.py --sabotar paridade   # acerto 0.17 → REPROVOU
.venv\Scripts\python.exe benchmarks\bench_ingest.py --sample 12 --raster      # ingest_20260915_053902.json: 267/911
#   somatório: counters side_to_move_origin:* dos 46 livros (default 644, move-number 142, text 92, ocr 13, caption-after 11, text-page-scope 8, ocr-page-scope 1)
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests\test_pdf_text.py tests\test_semantics.py tests\test_side_survey.py -q   # 74 passed
.venv\Scripts\python.exe -m pytest tests\unit\ingest tests\unit\model -q --ignore=tests\unit\model\test_roundtrip_corpus.py           # 1105 passed
```

### 11.1 O que o portão achou na verdade humana — e o que foi corrigido antes de medir

A primeira rodada do portão deu 4/7 e as três falhas eram do **dado**, não da regra:
em p10 «39 ♔f1» a FEN era a do diagrama (posição antes de `36 ... ♖e8!`, a linha impressa sob
ele) com lado e número da região três lances depois — o primeiro lance era **ilegal** a partir
dela (o cavalo em g3 cobre f1); em p18 «19 ♖c2» a FEN tinha o rei preto em g8 com a linha
sob o diagrama dizendo `18... ♔h8!!`; p17 é a partida do lance 1 sem diagrama. O portão passou
a acusar `[verdade: 1.º lance ilegal da FEN]` por região, e o revisor corrigiu as duas (a FEN
do diagrama vai na região cuja primeira linha é a impressa logo abaixo dele, com o lado e o
número dessa linha). Manifesto `86426402f56220aa` → `eb9b31eff07efe2c`; baseline recongelado.
Lição para o passo 0, registrada no roadmap: a FEN é do **diagrama**, e a região que a recebe
é a que **começa** na linha sob ele.

### 11.2 O que não fechou

- A meta de acervo (≥ 500/911) não é alcançável por numeração: onde não há lance impresso
  não há o que ler. O número honesto é 267/911 (29 %), e o resto pede outra fonte (símbolo de
  legenda, escopo de página, legalidade no tronco) que já existe e não cobre.
- n = 6 é pouco para um portão; o que o sustenta é a sabotagem (0,17) e o acervo.

### 11.3 Testes

Suíte: `test_captions.py` (+4: o primeiro lance sob o diagrama, a legenda «após», a palavra
vence a numeração e a numeração vence o escopo de página, número de exercício não é lance),
`test_importer.py` (+1: origem `move-number` no IR e no contador; +2 asserções). Tronco:
`test_pdf_text.py` (+5).

---

## §12 — Passo 11: parágrafo `Movetext` → `GameScore` (portão vermelho)

### 12.0 Em uma tela

- **O passe** (`caissa/ingest/pdf/games.py`, ligado por `PdfImportOptions.games=True`, no fim
  de `_to_ir`): uma coluna de parágrafos `Movetext` consecutivos é um só texto; o **tronco**
  da análise (`ocr/notation/movetext.move_runs(main_line_only=True)`) é reproduzido a partir
  da posição do diagrama com o reparador de legalidade (`notation/legality_repair`); se ≥ 2
  lances encadeiam **e o primeiro é o primeiro impresso**, a coluna vira `GameScore` com um
  `MoveNode` por lance (`san`, `ply`, `position_before/after`, proveniência do parágrafo com
  a nota «impresso → SAN; reparo»); a prosa antes do tronco vai para `comment_before` do
  primeiro lance, a prosa depois e o que não encadeou para `comment_after` do último
  (`[não reproduzidos: …]`) — nada some (R2.4). Sem posição: o parágrafo fica.
- **A posição vem da geometria**, não da ordem de leitura: o importador lista os diagramas da
  página antes do texto, e a regra «último diagrama antes» dava à coluna esquerda o tabuleiro
  da direita (p10, p12). Agora é o diagrama mais próximo **acima** da coluna, na mesma página e
  com x sobreposto; uma partida que encadeou entrega a posição em que parou à coluna abaixo.
  Sem caixas (blocos sem `rect`), vale a ordem de leitura.
- **Sem inventar — três regras**, todas com sabotagem no unitário: (1) um reparo que muda a
  peça, a casa, a captura ou a promoção do token impresso (`Nb4`→`Nb8`, `♖g6`→`Bg6`,
  `Nxe5`→`Ne5` para e5 vazia) **encerra a cadeia** (`is_invention`); um que só muda a
  grafia (`1d4`→`d4`, `♖g8`→`Rg8`) não; (2) a captura impressa que o tabuleiro não vê é o
  sinal mais seguro de que a posição não é a da linha (p15: «14 ♘xe5» do diagrama que está
  dois meios-lances antes — legal por acaso, agora recusado); (3) uma coluna que começa em
  «1 d4» sem diagrama parte da posição inicial. Número colado pelo OCR («20g3») é separado
  antes do tronco, que o descartaria.
- **Portão (`benchmarks/games_gate.py`): REPROVOU.** Nunn 0 lances encadeados em 99 tokens
  (≥ 16); SFC4 cobertura da verdade 0,06 (≥ 0,9), inventados 0 (= 0). Sabotagem (`--sabotar
  fen`, toda posição trocada por outra do livro): cobertura 0,00 → reprova, como deve.
- **Onde funciona** (informativo, páginas de camada de texto com diagrama vetorial):
  Dvoretsky *Endgame Manual* p202: 2 partidas / 6 lances (`1.Kd7!! Kf4 2.Ke8! Kg5`,
  `1.b6 axb6`); p206–207: 3 / 22 (`Rh8 d2 g8=Q d1=Q+ Ka2 Qb3+ Qxb3 axb3+` completo). SFC4
  (OCR, via raster): p10 `21 ♖a3! ♔h8 22 ♖g3` (conferido na página), p13 `17... ♗b4! 18 ♔g1`.

```
.venv\Scripts\python.exe benchmarks\games_gate.py                 # games_20260915_073236.json: Nunn 0/99, SFC4 0.06, inventados 0 → REPROVOU
.venv\Scripts\python.exe benchmarks\games_gate.py --sabotar fen   # games_20260915_073350_fen.json: cobertura 0.00 → REPROVOU
.venv\Scripts\python.exe benchmarks\side_to_move_gate.py          # PASSOU; acusa p10 e p15 [verdade: 1.º lance ilegal da FEN]
.venv\Scripts\python.exe -m pytest tests\unit\ingest tests\unit\export tests\unit\notation -q   # 991 passed, 1 skipped (test_games.py: 9)
```

### 12.1 Por que o portão está vermelho — e o que cada número mede

- **Nunn (0/99).** As seis páginas saem `text-layer` (p120–p200, glifos danificados `\x15`,
  `i!D`, sem parágrafo `Movetext`: os lances vivem na prosa) ou `text-layer+ocr` (p220,
  p240) com `Movetext` ilegível («Bl) 1) 1.1...Nc5 lLic5 2 Kc4») e diagramas OCR com peças a
  menos (`5k2/8/2P1P3/2P5/8/6K1/8/8` para uma posição com bispo). Os 12/18 da F5 foram
  medidos noutro ponto da cadeia (tokens das legendas, não parágrafos do importador). Aqui o
  passe não tem em que trabalhar; o gargalo é o passo 8/9 (OCR do scan), não este.
- **SFC4 (0,06).** A verdade do passo 0 é *a região* reproduzida da sua `start_fen`; o
  produto encadeia *colunas `Movetext`*. As duas coisas divergem por construção em 4 das 6
  regiões: p12 «19... g5!» e p10 (cabeça) são **prosa com lances** (classe `Body` no layout,
  não `Movetext`) — o passe não as toca; p17 «English Opening» é a partida do lance 1, cuja
  coluna sai do layout **fora de ordem** (15, 16, 4, 17, 8, 9, 10, …: as duas colunas da
  página intercaladas) e com OCR «1 5 eh1»; p18 o OCR leu «18 ♔h8» sem os três pontos, o lado
  ficou brancas (§11) e nada encadeia. As duas que casam, casam inteiras (p13 2/2) ou casariam
  se a verdade estivesse certa (p10, abaixo).
- **Verdade com erro (2 de 6), acusada pelo `side_to_move_gate` endurecido** (a legalidade do
  1.º lance agora exige *sem reparo que mude o lance*): p10 «22... ♖g6» tem FEN com brancas a
  jogar e torre já em g8 (posição *depois* de 22...♖g8) e o texto diz «g6» onde a página
  imprime **♖g8**; p15 «14 ♘xe5 ♖xe5» tem a FEN do diagrama, que está **dois meios-lances
  antes** (13 h3! ♘e5 fica na prosa) — e5 vazia, «♘xe5» não é captura. Correções para o
  revisor (na bancada, não no disco):
  - p10, região «22... ♖g6»: texto `22... ♖g8`; FEN
    `3qr2k/rb2bpp1/1p1pp2p/p3P3/Pn1P1PN1/6R1/1P1NQ1PP/1B3R1K b - - 3 22`;
  - p15, região «14 ♘xe5 ♖xe5»: FEN
    `r2qr1k1/p4pbp/bp1p1np1/2pPn3/8/P1N2NPP/1PQ1PPB1/R1B1R1K1 w - - 1 14`.
- **O contador «inventados»** conta lances da partida que não estão impressos na página; um
  jogo do lado errado feito de lances impressos noutro lugar (p18 antes da regra 2: `Qf2
  Bxe4`) passa por ele — o que o pegou foi a captura impressa. A cobertura é a medida que
  vale; «inventados» é o piso.

### 12.2 O que muda no produto

`PdfImportOptions.games` (padrão `True`); contadores `games`, `game_moves`,
`movetext_kept_no_position`, `movetext_kept_no_chain`, `movetext_kept_short`. Os testes de
forma de página (`test_corpus.py` p202/p206, `test_importer.py` figurinas) passam
`games=False` para continuar a ler parágrafos. Exportadores já conheciam `GameScore`
(`export/{docx,html,latex,pdf,text}.py`); a fidelidade do corpus com partidas dentro não foi
medida (tarefa 5 do passo, aberta).

### 12.3 O que não fechou

- O portão como escrito (cobertura da região de verdade) não mede o passe; mede a soma
  «layout classifica a linha como `Movetext` + ordem de leitura + OCR + lado». Para ficar
  verde precisa de (a) verdade corrigida (2 regiões), (b) prosa com lances (`Body`) também
  reproduzida — regra nova, não deste passo, (c) ordem de leitura por coluna nas páginas OCR
  (p17), (d) passo 8/9 no Nunn. A meta ≥ 16/18 do Nunn é de outra medição e fica registrada
  como não comparável.
- Colunas partidas por prosa (p15: «16 ♗e3 ♘d7 / prosa / 17 f4! c4») encadeiam só até a
  prosa: a partida acaba onde o comentário começa, e o comentário seguinte recomeça do
  `position_after` — correto, mas sai em duas `GameScore` em vez de uma com comentário.

### 12.4 Testes

`tests/unit/ingest/test_games.py` (9): tronco encadeia e prosa fica; reparo que muda o lance
encerra a cadeia; linha que não começa no 1.º lance impresso fica; coluna de uma linha por
parágrafo é uma partida e a posição segue; sem diagrama nada muda; reparo de grafia não é
invenção; captura impressa em casa vazia recusa a posição; coluna «1 d4» parte da inicial;
a coluna toma o tabuleiro acima dela e não o último em ordem de leitura.

### 12.5 Depois da correção do revisor (mesmo dia)

As duas regiões foram corrigidas na bancada (p10: texto «22... ♖g8» e FEN antes desse lance;
p15: FEN depois de 13 h3! ♘e5); manifesto privado regravado (`merge_into_manifest`: 256
substituídos, 8 com `start_fen`), hash `eb9b31eff07efe2c` → **`f019591babf2941e`**; baseline
de Sol recongelado no hash novo. Resultado:

- `games_gate`: as duas verdades agora reproduzem (p10 3 lances, p15 7); a cobertura cai para
  **0,04** (2/46) — o produto continua a encadear só p13 e o p10 da *coluna sob o diagrama*
  (`21 ♖a3! ♔h8 22 ♖g3`, que não é a região de verdade). O portão fica vermelho pelas razões
  de §12.1, menos a verdade.
- `side_to_move_gate`: a correção de p10 pôs a FEN da região (pretas, 22…) sob um diagrama
  cuja linha seguinte é «21 ♖a3!» (brancas) — as duas coisas não são comparáveis, e o portão
  passou a dizê-lo: uma região cuja primeira linha **não é a linha de lance sob o diagrama**
  fica fora do acerto (`[região não começa sob o diagrama: FEN é da região, fora do acerto]`,
  p10 e p15), e o piso de origem conta só as regiões com diagrama (p17 é a partida do lance
  1, sem tabuleiro). **n = 4: acerto 4/4, origem ≠ default 3/3 → PASSOU**; sabotagem
  paridade 0,25 → REPROVOU.

```
.venv\Scripts\python.exe benchmarks\games_gate.py                   # games_20260915_075039.json: SFC4 0.04, inventados 0 → REPROVOU
.venv\Scripts\python.exe benchmarks\side_to_move_gate.py            # side_to_move_20260915_075243.json: n=4 1.00, origem 1.00 (n=3) → PASSOU
.venv\Scripts\python.exe benchmarks\side_to_move_gate.py --sabotar paridade   # 0.25 → REPROVOU
.venv\Scripts\python.exe benchmarksench_sol.py --system baseline --label baseline --publish   # corpus f019591babf2941e, commit 4047bb5
```

---

## §13 — Passo 14: a janela de revisão de texto (SOL-11)

(O roadmap previa este relatório em `OCR_UI_REPORT_C2.md` §4; os passos executados
continuam num só arquivo, como os anteriores.)

### 13.0 Em uma tela

- **A aba «Revisão de texto»** (`caissa/ui/views/revisao_de_texto.py`, montada no tronco
  por `qt/painel_de_revisao_de_texto.py` com a mesma guarda da Rotulagem; `abas.py`
  ganha `REVISAO_DE_TEXTO` no acervo, entre Rotulagem e Configuração). Abre um PDF, importa as
  páginas pedidas com OCR numa thread (campo «Páginas» — um capítulo de cada vez, porque um
  livro inteiro com OCR leva minutos), e mostra **só** os spans `REVIEW`/`ABSTAINED`
  (`ReviewQueue.from_import`, ordem por risco): tabela à esquerda (página, tipo, decisão,
  escore, motivo, texto), cartão à direita com recorte a 300 DPI, leitura com as palavras
  fracas em destaque, alternativas, motivo (razões, tokens em disputa, lances sem leitura
  legal, sugestão nunca aplicada) e o campo da verdade. Três ações e um atalho cada: Enter
  aceita (ou grava, se o texto mudou), Ctrl+Enter grava a edição, Ctrl+R mantém como imagem;
  «Pular» não decide. Cada decisão vai para a trilha (quem, quando, segundos) e a fila anda
  para a próxima pendente.
- **As decisões sobrevivem à janela e chegam à exportação.** `ReviewDecisions`
  (`caissa/ocr/review.py`) é o diário reduzido a uma decisão por região, gravado a cada
  decisão em `labeling/revisao/<livro>.json` (e a fila com a trilha em `<livro>.fila.json`,
  retomada ao reabrir o PDF). O importador as **aplica** (`PdfImportOptions.review_decisions`,
  `_apply_review_decisions` antes de tirar o texto da página): região aceita deixa de estar
  «para revisão» e sai com `verified_by_human` e confiança 1,0; editada leva o texto do
  revisor (linha a linha quando o número de linhas bate, senão uma linha sobre a caixa);
  mantida como imagem é abstida e vira a figura de sempre. `export_book` carrega as decisões
  do livro sozinho e o resumo diz «N decisão(ões) do revisor aplicada(s); OCR: restam M
  região(ões) para revisão» — a tarefa 4 do passo.
- **O cartão é um só** (`caissa/ui/widgets/cartao_da_linha.py`): a metade direita da
  Rotulagem foi extraída para um widget com sinais (aceitar/gravar/rejeitar/andar/alternativa)
  e as duas abas o montam; a Rotulagem mantém os nomes de sempre (`crop_label`, `truth`…)
  como apelidos, e os seus 6 testes de janela passam sem mudança.
- **Portão: PASSOU.** Num livro com N = 3 dúvidas a janela visita **3 e só 3** (cada chave
  uma vez, a tabela lista as pendentes e só elas); a correção numa página da partição cega é
  recusada com a frase «página N está na partição cega: a leitura não pode ser aceita nem
  corrigida aqui (ela mede o OCR)» e nada entra no diário — manter como imagem continua
  permitido; o tempo por página fica em `seconds_per_page` e na linha de estado
  («s/página»). *Sabotagem executada:* com `blind_guard` desligado a mesma correção passa e
  a página cega aparece no arquivo que o importador lê — o teste acusa a gravação.
- **Auditorias da F9**, pela primeira vez com as abas da suíte dentro da janela (o venv do
  tronco é 3.10 e não importa a suíte; a receita passa a ser o Python 3.11 da suíte com o
  `site-packages` do `.venv-pack` — a mesma composição do bundle): **teclado PASSOU** nos
  seis arranjos (Revisão de texto 43–48 focáveis, todos pelo Tab, 0 sem nome); **contraste
  PASSOU** (300 pares, 0 reprovados, claro e escuro); **bloqueio REPROVOU nas 7 operações de
  sempre** (item aberto do C16; abrir PDF mediana 117 ms contra 214,5 no C16 — não piorou;
  nenhuma das sete é da aba nova).

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr\test_review.py -q                                # 8 passed
.venv\Scripts\python.exe -m pytest tests\unit\ingest tests\unit\export -q                          # 667 passed, 1 skipped
set PYTHONPATH=.venv-pack\Lib\site-packages& .venv\Scripts\python.exe -m pytest tests\unit\ui\test_revisao_de_texto_view.py tests\unit\ui\test_rotulagem_view.py -q   # 11 passed
set PYTHONPATH=.venv-pack\Lib\site-packages& .venv\Scripts\python.exe -m pytest tests\unit\ui tests\unit\ocr -q   # 838 passed, 12 failed: test_arquitetura «importa sem Qt» — falha só com o PyQt6 no caminho (16/16 no venv puro)
cd ..\ChessVisionOFF_Puro & set PYTHONPATH=..\Suite_de_Edicao_de_Xadrez\src;src;..\Suite_de_Edicao_de_Xadrez\.venv-pack\Lib\site-packages& ..\Suite_de_Edicao_de_Xadrez\.venv\Scripts\python.exe -m pytest tests\test_qt_janela.py -q   # 83 passed (oito abas)
cd ..\ChessVisionOFF_Puro & .venv\Scripts\python.exe -m pytest tests\test_packaging.py -q -k janela   # 5 passed (catraca 1902 → 1905)
set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages& .venv\Scripts\python.exe -m caissa.ui.audit.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c17     # teclado_20260915_083037.json: TODOS PASSOU
... -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\c17                                    # contraste_20260915_082654.json: PASSOU
... -m caissa.ui.audit.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17                       # bloqueio_20260915_083111.json: REPROVOU, 7 operações (as do C16)
```

### 13.1 O que a auditoria achou de graça: a Rotulagem nunca tinha sido medida

Com a suíte dentro da janela, o `teclado` viu a aba Rotulagem pela primeira vez — e a
reprovou: **20 de 60 controles inalcançáveis pelo Tab** e **11 nomes que não nomeiam**
(◀ ▶ − + e as seis figurinas «sem letras», o campo do idioma «eco do papel», o visor sem
nome). A causa dos 20 era um roubo de foco: `page_spin.editingFinished` dispara quando o
Tab sai do campo, `go_page` reabria a página e `_show_line` punha o foco na verdade — a
volta do teclado pulava a barra inteira. Corrigido (só um número **diferente** vira a página;
o visor é `ClickFocus`, a tela só o mouse usa; nomes acessíveis nos botões de símbolo e nas
figurinas do cartão, que servem às duas abas): **58–62 focáveis, todos pelo Tab, 0 nomes
vazios**. Fica registrado que os portões da F9 rodados com o venv do tronco medem a janela
**sem** as abas da suíte; a receita acima é a que mede o produto que o bundle entrega.

### 13.2 Decisões de construção (tarefa 3)

- **Aba, não modo da Revisão.** A Revisão do tronco é a fila de diagramas (S-22); a
  revisão de texto é outra fila e outra unidade (o livro importado). Um interruptor de modo
  esconderia trabalho — o que a S-162 mediu como o pior lugar. Cabeçalho de
  `qt/painel_de_revisao_de_texto.py`.
- **Aplicar no importador, não no IR.** As decisões entram antes de o texto da página ser
  tirado dos regiões do OCR, onde já existe o caminho para «abstida → imagem» e a marca de
  revisão por span; o IR nasce certo em vez de ser remendado. Custo: a região é reencontrada
  por sobreposição de caixas (IoU ≥ 0,5) na próxima importação — o layout é determinístico
  para a mesma página e DPI.
- **Onde as decisões moram:** `labeling/revisao/` (git-ignored, ao lado do projeto de
  rotulagem), nunca ao lado do PDF — a pasta do acervo não é nossa para escrever.

### 13.3 O que não fechou

- A edição substitui o texto da região inteira; uma região de várias linhas em que o revisor
  muda só uma palavra continua a sair certa (linha a linha quando a contagem bate), mas a
  proveniência por span vira uma só (1,0, «decidida pelo revisor»).
- Depois do passo 8, diagramas com `confidence` baixa entrariam na mesma fila; hoje a fila é
  só de texto.
- `bloqueio` segue vermelho nas 7 operações do tronco (item aberto de sempre).

### 13.4 Testes

`tests/unit/ocr/test_review.py` (+4: diário → decisões e aplicação às regiões; manter como
imagem abstém e aceitar verifica; página cega recusa aceitar/editar com a frase, sabotagem
sem guarda grava; fila gravada volta com trilha e relógio). `tests/unit/ingest/test_importer.py`
(+1: decisões aplicadas na importação — `verified_by_human`, confiança 1,0, lista de revisão
vazia, contador). `tests/unit/ui/test_revisao_de_texto_view.py` (novo, 5: HTML da leitura;
monta e lista N e só N; decide, anda, grava sozinha e retoma; página cega com a frase e a
sabotagem; importação em thread). Tronco: `test_qt_janela.py` (oitava aba), `test_packaging.py`
(catraca 1905 com o motivo).

---

## §14 — Passo 15, tarefa 0: o «antes» do visor por ladrilhos (2026-09-15)

Medido com as abas da suíte na janela (receita de §13.0), livro `1937 Kemeri.pdf`:

- **`quadros` (3×): PASSOU.** zoom **75,3 / 81,8 / 78,3 fps @ p95** (piso 70), pan 790 / 745 /
  770, juntos 101,9 / 100,8 / 103,7. O D19 do ciclo 1 (59 fps mediana, 2026-09-07) está
  ultrapassado: o reescalonamento só quando o zoom muda (`pagina_escalada`) já dá a folga.
- **`bloqueio`: REPROVOU, 7 operações** (as mesmas do C16; `bloqueio_20260915_083111.json`):
  abrir PDF **170 ms** (PyMuPDF 41 %, disco 30 % — `games_cache.open_store` da Galeria,
  builtins 24 %), virar página **~70 ms** (rasterizar a 300 DPI = 45 ms + `mostrar_pagina`),
  aba Dataset 70 ms, aba Galeria 23 ms, rasterizar 46 ms. Nenhuma é do zoom ou do pan.

```
set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages& .venv\Scripts\python.exe -m caissa.ui.audit.quadros --pdf "%PDF%" --saida benchmarks\reports\ui\c17   # fps_20260915_085705/085707/085709.json
... -m caissa.ui.audit.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17   # bloqueio_20260915_083111.json
```

**O que o «antes» diz sobre o passo.** O portão do passo 15 («0 operações > 16 ms; abrir PDF
≤ 16 ms») não é um portão do visor: das 7 operações, 5 são rasterização e E/S **fora** dele
(`painel_do_pdf.desenhar_pagina` rasteriza na thread de UI e devolve `True` só com a imagem
pronta — é o contrato de quem chama o OCR; `painel_da_galeria.load_pdf` abre o SQLite; a aba
Dataset carrega as amostras ao aparecer). Ladrilhos em worker resolvem o zoom, que já passa.
O que falta é render e E/S fora da thread em `qt/painel_do_pdf.py`, `qt/painel_da_galeria.py`,
`qt/painel_do_dataset.py` — e os três, mais `qt/visor.py` e `ui/viewport.py`, carregam
**1.267 linhas não commitadas de outra sessão** (desde 2026-09-14 02:26). Pela regra deste
trabalho (commit só por caminho, em arquivo limpo) o passo fica **suspenso** até essa sessão
commitar ou guardar o que tem; o precedente do passo 12 (pares reaplicáveis em
`docs/quality/ui/c17/tronco_passo12.py`) vale para mudanças pequenas, não para esta.

---

## §15 — Passo 15: render e E/S fora da thread da janela (2026-09-16)

(O roadmap previa este relatório em `OCR_UI_REPORT_C2.md` §5; os passos executados continuam
num só arquivo, como os anteriores. O «antes» é o §14.)

### 15.0 Em uma tela

- **O `bloqueio` passa pela primeira vez** — 3 invocações, 3 × PASSOU; nenhuma operação acima
  de **6,6 ms** (piso 16). Era 7 operações reprovadas com 170 ms na pior (§14).
- **O que faltava não era ladrilho: era o GIL.** Rasterizar numa `QThread` tirou a conta da
  thread da janela só no nome — o `get_pixmap` do PyMuPDF 1.28 segura o interpretador os 43–49 ms
  inteiros, e a janela ficou parada **51 ms** por página numa thread. A leitura do `labels.csv`
  (5.431 FENs conferidas em Python) e a detecção de fundo têm a mesma doença. A solução é um
  **processo filho** (`chess_diagram_ocr/processo_de_trabalho.py`): o pai só espera, e esperar
  um `Pipe` solta o GIL.
- `quadros` sobe de 75–82 para **346–415 fps @ p95** no zoom: a redução ao zoom novo roda ao
  fundo (`cv2.resize`, que solta o GIL) e a folha anterior é esticada pelo pintor até a nítida
  chegar (quadro provisório).
- **Bandeira** `qt/painel_do_pdf.RASTERIZAR_AO_FUNDO` (padrão `True`; desfazer = `False`). A
  suíte do tronco a desliga uma vez no `conftest`; o caminho ao fundo tem testes próprios.
- Tronco: `8b61a3e` guarda o WIP da outra sessão (86 arquivos, a pedido do usuário); o passo vem
  por cima em commit próprio. Suíte do tronco: 4.507 passaram; 3 falhas pré-existentes de
  módulos da outra sessão (`biblioteca.py`, `cortina.py`, `selecao_de_area.py`,
  `substituicao.py` fora de `SEM_TKINTER`/acentos; `test_field_eval` pede remedição de campo
  desde o passo 7) e nenhuma nova.

### 15.1 O que foi medido antes de escrever código

A tarefa 0 (§14) dizia que 5 das 7 operações eram render e E/S fora do visor. Dividindo cada
operação em partes (`scratchpad/perfil15*.py`, Kemeri, janela 1280×800, offscreen):

| parte | ms | onde |
|---|---:|---|
| `get_pdf_page_count` (disco frio) | 19,5 | thread da janela |
| `galeria.load_pdf` → `open_store` (SQLite, frio) | 67,6 | thread da janela |
| `render_pdf_page` 220 DPI | 68 (frio) / 45 | thread da janela |
| `visor.mostrar_pagina` (array → `QPixmap` + reescala) | 5,7 | thread da janela |
| aba Dataset, 1.ª vez | **57,7** no 1.º `processEvents`; 4,4 com `_stale=False` | `_reler_agora` |
| aba Dataset, quente | 14 ms de Qt (69 widgets + `QTreeWidget` de 200 linhas), 1,3 ms de Python | — |

O 57,7 da aba Dataset **não era a aba**: era o CSV lendo numa thread e revezando o GIL com os
442 `eventFilter` que uma troca de aba dispara. Com `sys.setswitchinterval` em 0,5 ms cai para
7,8; em 0,1 ms para 6,0 (`perfil15g.py`); a leitura fica 20 % mais lenta (678 → 816 ms).

**Faixas não resolvem o PyMuPDF.** Rasterizar em cinco `get_pixmap(clip=)` de 512 px custa
110 ms no total e a pior faixa 30 ms — o scan embutido é decodificado inteiro a cada faixa — e
a pior espera da thread principal fica em 33 ms. O `displaylist` não muda nada. Medido em
`perfil15b/c`; é a razão de o passo não ter ficado em «ladrilhos em worker».

**`QImage.scaled` também segura o GIL** (11,4 ms de espera numa thread, 24 ms no total);
`cv2.resize` INTER_AREA custa 15 ms e a espera é 2,9 ms. Por isso `qt/imagens.reduzir_rgb`.

### 15.2 O que foi construído (tronco)

| onde | o quê |
|---|---|
| `processo_de_trabalho.py` (novo) | `ProcessoDeTrabalho`: um `ProcessPoolExecutor(spawn, 1)` preguiçoso; `executar(funcao, *args)`, `rasterizar`, `aquecer`, `encerrar`; recria o filho uma vez se ele morrer e cai para a linha com aviso se nem isso der; `em_processo=False` roda em linha |
| `qt/trabalho.py` | `ceder_a_interface()` na primeira `Tarefa`: `sys.setswitchinterval` → 0,1 ms (tabela medida no docstring) |
| `qt/painel_do_pdf.py` | `load_pdf` conta as páginas ao fundo e só aponta para o livro em `_livro_abriu` (S-123 mantida); `desenhar_pagina` pede a folha ao fundo (`_rasterizar` → filho → `preparar_folha`), a anterior fica na tela; `FolhaRasterizada` com a chave `(livro, página, dpi)` recusa folha atrasada; `aguardar_pagina()` para testes e arnês; bandeira `RASTERIZAR_AO_FUNDO` |
| `qt/visor.py` | `_pagina` vira o tamanho; a página inteira mora só no array; `FolhaPreparada`/`preparar_folha` (prevê o zoom do enquadramento); reescala ao fundo com quadro provisório esticado; geração para descartar reescala de página que saiu |
| `qt/imagens.py` | `reduzir_rgb` (OpenCV) |
| `qt/painel_da_galeria.py` | `_abrir_cache_de_posicoes(ao_fundo=True)` na abertura do livro; a busca por posição espera a abertura em vez de abrir outra |
| `games_cache.py` | `open_store(de_outra_thread=True)` → `check_same_thread=False` |
| `qt/marcas.py` | `ler_marcas_e_treino` (uma passada pelo CSV, no filho, para marcas **e** amostras de treino); `amostras_de_treino_guardadas` só devolve o que já está guardado |
| `qt/janela.py` | bandeira repassada; `_aviso_de_treino` não lê mais na thread da janela; detecção de fundo no filho (`detect_diagrams_rendering_page`, que rasteriza de novo em vez de receber 26 MB) |
| `qt/painel_do_dataset.py` | `load_rows` no filho, atravessando como tuplas (7,8 → 3,0 ms de `pickle.loads`) |
| `qt/campo.py` | conjunto de campo guardado por `(tamanho, mtime)` |
| `qt/tabela.py` | alinhamento resolvido uma vez por coluna |
| `ui/busy.py` | as três threads novas declaradas em `FORA_DO_REGISTRO` com o motivo |
| `detection/hybrid.py` | `detect_diagrams_rendering_page` |

Suíte (`caissa`): `ui/audit/capture.aguardar_a_folha` e o uso dela em `bloqueio`, `quadros`,
`capture`, `comandos`, `execucao`, `fita`, `teclado`, `texto_pintado`; `bloqueio --sabotar`;
a operação `rasterizar pagina a 300 DPI (render_pdf_page)` vira **referência** (medida e
publicada, fora de `viola` — ver 15.4).

### 15.3 Portão

```
set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages
.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17   # 3x
.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "%PDF%" --saida benchmarks\reports\ui\c17 --sabotar
.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "%PDF%" --saida benchmarks\reports\ui\c17   # 3x
```

`bloqueio` — `bloqueio_20260916_060952/061002/061012.json`, **PASSOU × 3**. Pior travamento por
operação nas três invocações (ms; o «frio» é a 1.ª execução):

| operação | pior | frio | §14 |
|---|---|---|---:|
| abrir PDF (load_pdf, 1.ª página) | 3,6 / 5,9 / 4,8 | 2,9 / 5,9 / 4,8 | 170 |
| virar para a página 41 | 1,9 / 1,7 / 2,3 | 1,9 / 1,7 / 1,1 | ~70 |
| virar para a página 42 | 2,8 / 2,5 / 4,0 | 0,7 / 1,9 / 1,4 | ~70 |
| virar para a página 121 | 4,1 / 2,0 / 2,3 | 1,6 / 2,0 / 2,3 | ~70 |
| aba Dataset: mostrar e carregar | 6,3 / 6,6 / 5,6 | 2,0 / 2,3 / 4,4 | 70 |
| aba Galeria: mostrar | 3,6 / 2,6 / 4,0 | 0,2 / 2,6 / 4,0 | 23 |
| carregar índice da Galeria | 0,0 | 0,0 | 1 |
| ajustar a página | 0,0 | 0,0 | 0 |
| contar páginas | 0,0 | 0,0 | 0 |
| *referência:* rasterizar 300 DPI direto | 57,9 / 55,2 / 61,2 | — | 46 |

**Sabotagem** (`--sabotar` = `rasterizar_ao_fundo=False`, tudo na thread da janela):
`bloqueio_sabotagem_20260916_054722.json`, **REPROVOU, 7 operações** — abrir 143 ms, virar
99–112 ms, Galeria 47,6/35,5, Dataset 31,2. O portão acusa.

`quadros` — `fps_20260916_054955/054957/055000.json` (mais `061026`, a última): zoom
**414,9 / 346,1 / 365,6 fps @ p95** (piso 70), pan 629,6 / 550,4 / 563,4, juntos 441,7 / 388,4 /
399,7. Era 75–82 (§14). O quadro medido é o provisório quando o zoom acaba de mudar; a nítida
chega por sinal ~15 ms depois (uma redução por passo, só o último zoom espera).

Também rerodados sem regressão: `teclado` (PASSOU em todos os arranjos,
`teclado_20260916_061059.json`), `comandos` (PASSOU, `comandos_20260916_061108.json`).

Cópias dos relatórios do portão (os três `bloqueio`, a sabotagem e o `fps` final) em
`docs/quality/ui/c17/*passo15*.json`; `benchmarks/reports/` não é versionado.

### 15.4 O que mudou no portão, e por quê

A operação *«rasterizar pagina a 300 DPI (render_pdf_page)»* chamava `render_pdf_page` **direto
na thread da janela**: era o custo bruto, posto na lista no ciclo 1 para atribuir a virada de
página. O produto não a chama mais nessa thread — e um portão da thread da interface que
reprovasse por uma função que a interface não chama estaria medindo outra coisa. Ela continua
medida e publicada (`referencia: true`, coluna «ref» na tabela) porque é o que o filho paga; sai
de `viola` e de `violam_o_portao`. Teste em `tests/unit/ui/test_medicao.py`.

`bloqueio` e as demais auditorias esperam a folha (`aguardar_a_folha`) **sob o vigia**: sem isso
«virar página» mediria só o pedido (2 ms) e a chegada da folha cairia na operação seguinte.

### 15.5 Achados que ficam

1. **Uma `QThread` não é «fora da thread da interface» em Python.** Só é quando o que roda nela
   solta o GIL — numpy e OpenCV soltam, PyMuPDF e o `csv`+python-chess não. Toda medição de
   bloqueio deste projeto que atribuiu custo a «Qt (toolkit)» ou «builtins (C)» dentro de
   `processEvents` precisa ser lida com isso em mente: parte daquele tempo era espera pelo GIL.
2. **O intervalo de troca do interpretador é um parâmetro de interface.** 5 ms (padrão) é bom
   para lote; 0,1 ms custa nada de vazão medível aqui e tira 50 ms de travamento.
3. **A folha de estilo não é o custo da aba Dataset** (13,8 → 13,2 ms sem as regras de
   `::item`; 9,5 sem folha nenhuma). Os ~14 ms de Qt para mostrar a aba com a tabela cheia são o
   `QTreeWidget` (2,6 ms sem ele) — cabeçalho pintado 6× por troca (3 pares hide/show) e a pintura
   das células. Fica abaixo do piso com 0 Python concorrente; é o item que sobra para quem quiser
   margem (item aberto, não bloqueante).
4. **`spawn` reimporta o `__main__`**: todo script que construa `JanelaPrincipal` com a bandeira
   ligada precisa do `if __name__ == "__main__"` — sem ele o filho abre outra janela e outro filho
   (aconteceu no primeiro roteiro de perfil). Os arnês e o `app_pyqt` já o têm; o bundle tem
   `mp.freeze_support()`. **O bundle não foi reconstruído neste passo** — conferir na próxima
   construção que o filho nasce dentro do `.exe`.
5. O item C16 «`bloqueio` reprovado» fecha; Q6 da SPEC (o que vale para 13 e 14 até o 15 fechar)
   deixa de ter objeto.

### 15.6 Testes

Tronco (Python 3.10, `.venv` do tronco): `tests/test_processo_de_trabalho.py` (novo, 6: em linha;
no filho de verdade — resultado volta, PID difere, a página do filho é igual à de
`render_pdf_page`, **150 ms de Python no filho não param a thread principal por mais de 40 ms**;
sem `spawn` possível cai para a linha), `tests/test_qt_painel_do_pdf.py::RasterizacaoAoFundoTests`
(5: volta antes da folha e a folha chega por sinal; a anterior fica na tela; virar duas vezes
mostra só a última; PDF quebrado não troca o livro; em linha a folha está ao voltar),
`tests/test_app_pyqt.py::VisorTests` (+4: em linha nítida na hora; quadro provisório até a nítida;
zoom que passou é descartado; `preparar_folha` prevê o enquadramento),
`tests/test_qt_trabalho.py::CederAInterfaceTests`. `conftest.trabalho_em_linha` (sessão).
Catraca de `qt/janela.py` 1.905 → 1.944 com o motivo em `test_packaging`. Suíte inteira:
**4.507 passed**, 3 falhas pré-existentes (15.0). Suíte da `caissa`: `tests/unit/ui/test_medicao.py`
+1 (a referência não decide o veredito).

### 15.7 Saída

Tronco: `8d9b02f` sobre `8b61a3e` (os 25 caminhos de 15.2). Suíte: este §15, a linha do
roadmap, `caissa/ui/audit/*` e `test_medicao.py`; relatórios em `benchmarks/reports/ui/c17/`.
**Desfazer:** `qt/painel_do_pdf.RASTERIZAR_AO_FUNDO = False` (o visor volta ao que era: tudo em
linha) — o `bloqueio` volta a reprovar nas 7, que é a sabotagem.

---

## §16 — Passo 16: Foco como padrão e polimento (Q3) (2026-09-16)

(O roadmap previa este relatório em `OCR_UI_REPORT_C3.md` §1; segue no arquivo único.)

### 16.0 Em uma tela

- **Foco é a pele de fábrica** (`ui/pele.PADRAO = FOCO`, decisão Q3 do usuário em 2026-09-16).
  As três continuam em *Ver ▸ Aparência* (R3.6); Clássica passa a segunda. A escura é
  **projetada**, como a SPEC §10.2 pede: `ui/tokens.NO_CROMO_ESCURO` tem valor próprio por papel
  de cromo, matiz preservada ao grau, elevação invertida — conferido, não refeito.
- **A janela voltou a caber em 1366×768, nas três peles.** Achado do passo: o piso da janela
  estava em **827 px na Foco** (793 na Clássica, 743 na Fita) — acima dos 768 que a F9-C2 tinha
  devolvido ao produto — por duas colunas: os dez cabeçalhos do PGN empilhados na Galeria
  (531 px) e o cartão da Rotulagem (496 px). Ambas rolam agora; piso **674 / 640 / 640**. Com
  a Foco como padrão, era o defeito que mais gente veria.
- `contraste` PASSOU nas duas polaridades (0 reprovados em 220 pares sob portão × 2), sabotagem
  acusa; `teclado` PASSOU em todos os arranjos; `texto_pintado` PASSOU.
- **`vazio` a 4K REPROVOU: 6 de 8 painéis acima de 200 kpx, antes e depois, nas três peles.**
  O instrumento é novo (`caissa.ui.audit.vazio`, régua do crítico do ciclo 5/9 promovida ao
  arnês) e o número reproduz o do ciclo 15 (Revisão 3 104,2 kpx). O que ele mede é a ausência
  de dados, não o leiaute — ver 16.4. Fica vermelho e declarado.
- Polimento: contadores tabulares (`tnum`, propriedade `tipografia.PROPRIEDADE_TABULAR` em
  página / total / zoom / rodapé), contorno neutro na página do visor e no recorte da Galeria,
  legenda da Galeria com 3–8 linhas em vez de 8 cravadas. Raio concêntrico e foco visível já
  estavam na folha (F9-C2: `raio - 1` no indicador, `:focus` 2 px) — conferidos.
- **O crítico visual às cegas (SPEC §11.4) não foi feito**: é papel do crítico, e o material
  está pronto — 96 retratos `depois16_*` (3 peles × 4 tamanhos × 8 abas) e as pranchas de
  controles (`amostrario_*.png`, `estados_*.png`) em `benchmarks/reports/ui/c18/`.

### 16.1 Padrão de fábrica

`ui/pele.py`: `PADRAO = FOCO`; `valida` e `escolhida` caem nele; `PELES` reordenada (Foco,
Clássica, Fita) porque a regra 1 da tabela é "a primeira é o padrão". `AppState.skin` continua
vazio para "nunca escolhida" — o padrão mora num lugar só. Testes: `test_ui_pele.py` (padrão =
Foco, primeira = padrão, inválida cai no padrão, Clássica continua registrada),
`test_qt_janela.py` (o menu abre com o padrão marcado; os dois testes da Clássica pedem-na por
nome). `test_qt_menu.py` e `test_strings.py` sem mudança.

### 16.2 O piso de 768, medido

`scratchpad/minalt*.py` (janela Foco a 1366×768, `minimumSizeHint` por aba):

| aba | antes | depois | o que mudou |
|---|---:|---:|---|
| Galeria | 674 | **516** | a lateral «Cabeçalhos do PGN» (10 campos + 5 botões = 531 px) entra numa `QScrollArea` de largura fixa; a legenda passa de 8 linhas cravadas a mínimo 3 / máximo 8 (`LINHAS_MINIMAS_DA_LEGENDA`) |
| Rotulagem (suíte) | 702 | **266** | cartão + botões + tabela numa `QScrollArea` dentro do divisor vertical |
| Resultado | 549 | 549 | passa a ser a mais alta |
| Revisão de texto | 501 | 501 | — |
| janela Foco / Clássica / Fita | 827 / 793 / 743 | **674 / 640 / 640** | `capture` deixou de avisar «pediu 1366x768, ficou …» nas 96 capturas |

As duas áreas de rolagem têm `NoFocus`: sem isso o `teclado` contou um focável sem nome nem papel
em cada aba (medido e corrigido antes do PASSOU).

### 16.3 Portões

```
set PYTHONPATH=src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages
.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\c18            # contraste_20260916_064651.json
.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\c18 --sabotar  # contraste_sabotagem_20260916_063027.json
.venv\Scripts\python.exe -m caissa.ui.audit.teclado --pdf "%PDF%" --saida benchmarks\reports\ui\c18        # teclado_20260916_065028.json
.venv\Scripts\python.exe -m caissa.ui.audit.texto_pintado --pdf "%PDF%" --saida benchmarks\reports\ui\c18  # texto_pintado_20260916_064740.json
.venv\Scripts\python.exe -m caissa.ui.audit.capture --saida benchmarks\reports\ui\c18 --marca depois16 --pdf "%PDF%"   # 96 PNG
.venv\Scripts\python.exe -m caissa.ui.audit.vazio --capturas benchmarks\reports\ui\c18 --marca depois16 --saida benchmarks\reports\ui\c18
.venv\Scripts\python.exe -m caissa.ui.audit.amostrario --saida benchmarks\reports\ui\c18 [--estados]
```

| portão | resultado |
|---|---|
| `contraste` | claro 300 pares / 220 sob portão / **0 reprovados**; escuro idem; menor folga 3,03:1 (polegar da barra, piso 3,0). **PASSOU** |
| `contraste --sabotar` | `TEXTO_SECUNDARIO` do cromo escuro a **3,90:1** (`#787d85`): escuro **12 reprovados**, todos do token plantado (a dica de campo em 12 lugares); claro 0. Acusa. O roadmap dizia «acusar 1»: um token são doze pares, e o portão acusa os doze |
| `teclado` | **PASSOU** em todos os arranjos (3 peles × 2 densidades, 8 abas + 13 diálogos) |
| `texto_pintado` | **PASSOU** |
| `vazio` (novo) | **REPROVOU** — 6 de 8 acima de 200 kpx em cada pele, antes (3 104,2 Revisão) e depois (3 036,0). Dataset e Resultado passam |
| `quadros` / `bloqueio` | do passo 15, sem mudança de visor além do contorno |

Cópias em `docs/quality/ui/c18/` (`*_passo16*.json`, um retrato por pele a 1366×768).

### 16.4 O que o `vazio` mede — e por que fica vermelho

Os seis painéis acima do teto são **áreas de conteúdo sem dados**: a tabela da Revisão com 27
linhas num viewport de 2 071 px, a coluna de lances do Estudo vazia, a Galeria sem varredura, o
Texto sem OCR, a Rotulagem e a Revisão de texto sem livro importado. A 3840×2160 **a 100 %** (a
captura não escala; um monitor 4K real corre a 150–200 %) qualquer área de dados vazia com mais
de ~100 px de altura passa de 200 kpx. Os dois que passam (Dataset 146,8; Resultado 43,3) passam
porque têm dados: 5.431 linhas e um tabuleiro.

Fechar o número exigiria pautar as áreas vazias (traços a cada linha, como uma folha de
planilha) — decisão de produto que este passo não toma. O que o passo entrega é a régua
(instrumento no arnês, testado em `test_medicao.py::TestVazio`), o número antes/depois e esta
leitura; a proposta para o crítico do C3 é medir a 200 % ou excluir do teto a área de dados
declaradamente vazia (com `EstadoVazio` desenhado). Fica **aberto e declarado**, como desde o C16.

### 16.5 Polimento entregue (tronco)

| onde | o quê |
|---|---|
| `ui/tipografia.py` | `PROPRIEDADE_TABULAR` (decisão: quem conta); `qt/tema.tabular` (o `tnum`); `qt/escala.aplicar_escala` aplica-o na varredura |
| `qt/painel_do_pdf.py`, `qt/rodape.py` | página, total, zoom e documento do rodapé declarados tabulares. **Medido: a Segoe UI já tem algarismos tabulares** (`1111` = `0000` = 28,0 px a 10 pt); o recurso vale para a família de reserva |
| `qt/visor.py` | `_desenhar_contorno`: fio de 1 px `CONTORNO_DE_CROMO` sobre o pixel externo da folha (não fora dela: crescer a folha deslocaria caixas e cliques) |
| `qt/tema.pintar_varios`, `qt/painel_da_galeria.py` | recorte da Galeria com fundo **e** contorno (dois `pintar` no mesmo widget deixavam só o segundo) |
| `qt/painel_da_galeria.py`, `ui/galeria_declarada.py` | lateral em rolagem; `LINHAS_MINIMAS_DA_LEGENDA = 3` |
| suíte `caissa/ui/views/rotulagem.py` | cartão em rolagem |

Testes: `test_qt_tema.py::PolimentoDoPasso16Tests` (3: o contador ganha `tnum` e a prosa não; os
contadores do produto estão declarados; `pintar_varios` declara as duas propriedades),
`test_medicao.py::TestVazio` (3). Suíte do tronco: **4.511 passed**, as mesmas 3 falhas
pré-existentes de §15.0. Suíte `caissa` `tests/unit/ui`: 282 passed no venv puro
(`test_revisao_de_texto_view` continua exigindo o `.venv-pack`, como desde o passo 14).

### 16.6 Saída

Tronco: `a3bf4c5` sobre `8d9b02f`. Suíte: `caissa/ui/audit/vazio.py` (novo), `contraste
--sabotar`, `views/rotulagem.py`, este §16, a linha do roadmap. **Desfazer:** `ui/pele.PADRAO =
CLASSICA` e a ordem de `PELES` (o polimento e a rolagem ficam: são independentes da pele).
