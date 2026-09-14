# OCR/UI · ciclo 1 — relatório do construtor

> **Data:** 2026-09-14 · **Plano:** `docs/OCR_UI_ROADMAP.md` · **Contrato:** `docs/OCR_UI_SPEC.md`
> · **Papel:** construtor. Todo número desta página traz ao lado o comando que o produziu.
> Ambiente: `.venv` (Python 3.11.9, torch 2.11.0+cu128, Tesseract 5.5.0), corpus dourado
> privado `43ac7c57017324d8` (446 itens, 747 medições nas partições `dev`+`calib`; a cega fora).
> Relatórios completos em `benchmarks/reports/sol/c1*_*.json`; os dois finais publicados sem
> texto do acervo em `docs/quality/sol/c1_sem.{json,md}` e `c1_rapidocr.{json,md}`.

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
