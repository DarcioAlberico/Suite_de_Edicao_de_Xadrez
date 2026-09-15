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
revisor a partir do diagrama impresso acima de cada coluna de lances — **é o denominador dos
passos 7 e 11**. Não são "todas as colunas de lances": das 26 colunas com ≥ 6 lances, só 6 vêm
logo depois de um diagrama na mesma página; as outras 20 são continuações da partida (o diagrama
está páginas antes, ou os lances intermediários estão na prosa) e não têm posição a copiar. As
duas restantes são partidas do lance 1 (posição inicial). 21 regiões marcadas `movetext`.

| pág. | região | partição | FEN | lances que a repetição de legalidade reproduz da FEN |
|---|---:|---|---|---:|
| 10 | «22... ♖g6» | dev | `…/1B3R1K w - - 4 24` — o diagrama está em 24, a região começa em 22… | 1 |
| 10 | «39 ♔f1» | calib | `8/6k1/3b4/1R1p4/1PpPr1p1/2P3n1/3B2K1/6N1 w - - 0 39` | 0 |
| 12 | «19... g5!» | dev | `4k2r/p2n1ppp/Npr1p3/3pP3/3p1P2/8/P2N2PP/R3K2R b - - 0 19` | 6 |
| 13 | «17... ♗b4!» | calib | `r2q2k1/2p1b1pp/p3b3/1p1pP3/3P4/1PN1B3/1P4PP/R2Q1K2 b - - 0 17` | 2 |
| 15 | «14 ♘xe5 ♖xe5» | calib | `r2qr1k1/p2n1pbp/bp1p1np1/2pP4/8/P1N2NP1/1PQ1PPBP/R1B1R1K1 w - - 0 14` | 5 |
| 17 | «English Opening / 1 d4 ♘f6» | dev | posição inicial | 28 |
| 18 | «19 ♖c2 ♖g8!» | dev | `1qr1r1k1/1bbn1ppp/pp1ppn2/8/2P1P3/1NN1BP2/PP4PP/2RR1BQK w - - 0 19` | 1 |
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
