# Sol · ciclo 1 — OCR de prosa editorialmente confiável: o que foi construído e o que foi medido

> **Data:** 2026-09-13 · **Frente:** Sol (`Sol.md`) · **Marcos:** A, B, C e D, código de todos;
> portões quantitativos ainda vermelhos onde o roadmap exige o que só um corpus humano dá.
> Ambiente: `.venv` na raiz, Python 3.11.9, Tesseract 5.5.0, PyMuPDF 1.28.2; PaddleOCR,
> PP-StructureV3, RapidOCR e Surya **não instalados**.
> Todo número desta página traz ao lado o comando que o produziu. Acervo: `CORPUS.md` §0.

---

## 0. Em uma tela

| Sol.md pedia | Estado | Onde |
|---|---|---|
| SOL-0 corpus dourado + executor único | **feito** (esqueleto medível; 190 itens, não 200 páginas humanas — §2) | `caissa.ocr.golden`, `metrics`, `gates`; `benchmarks/bench_sol.py` |
| SOL-1 OCR padrão do importador | **feito** | `caissa.ingest.pdf.ocr_service.OcrService`, `enable_ocr=True` |
| SOL-2 aceitar/revisar/abster | **feito** | `caissa.ocr.decision`, árbitro sem `accepted` abaixo do limite |
| SOL-3 portfólio condicionado | **feito** | `caissa.ocr.portfolio` |
| SOL-4 calibração + roteamento | **feito** (tabelas ajustadas na partição `calib`) | `caissa.ocr.calibration`, `routing`, `data/calibration.json` |
| SOL-5 motores opcionais | **feito** com testes contratuais em módulos falsos; não medido ao vivo (motores ausentes) | `engines/contracts`, `paddle_structure`, `worker`, `weights` |
| SOL-6 fusão por token | **feito** | `caissa.ocr.fusion` |
| SOL-7 perfis prosa/lances + idioma | **feito** | `engines/profiles`, `caissa.ocr.language` |
| SOL-8 validação enxadrística no documento | **feito** | `caissa.ocr.notation.validate`, contexto de diagramas no serviço |
| SOL-9 léxicos reproduzíveis | **feito** (dicionários Hunspell licenciados en/pt/es; russo só lista autoral) | `caissa.ocr.data.lexicon`, `hunspell`, `tools/build_lexicon.py` |
| SOL-10 proveniência no IR | **feito** | span com motor/confiança/revisão; `ocr_trace.json`; `review_items` |
| SOL-11 revisão por risco | **modelo feito, sem janela** (shell F9 não está neste repositório) | `caissa.ocr.review.ReviewQueue` |
| SOL-12 portões | **feito** | `benchmarks/sol_gate.py`; comparação por estrato com IC bootstrap |

**O que os portões dizem hoje** (`python benchmarks/sol_gate.py --report-only docs/quality/sol/sol.json`):
verde em *importação silenciosa abaixo do limiar* (0), *controles negativos* (0/9), *ordem de leitura*
(1,000) e em toda regressão por estrato; **vermelho** em CER limpo (0,0156 vs 0,005), CER 150 DPI
(0,0371 vs 0,020), acurácia de lances (0,789 vs 0,998) e lances inventados (253 vs 0). §3 diz por quê e
o que cada vermelho significa — nenhum deles é "o código não está pronto"; dois deles são o motor
único, e dois são a definição da métrica sobre um corpus sem verdade humana.

Testes: **654 aprovados** em `tests/unit/ocr` + `tests/unit/ingest` (eram 535), 963 com `notation`.

```
.venv\Scripts\python -m pytest tests\unit\ocr tests\unit\ingest tests\unit\notation -q
```

---

## 1. Baseline e depois, por estrato

Baseline = a cascata como estava antes de Sol (`PageRecognizer` sobre a renderização, sem
pré-processamento, árbitro aceitando o melhor de um lote ruim), congelada como sistema `baseline`
do executor e reproduzível. Sol = o caminho de produção (`OcrService`).

```
.venv\Scripts\python benchmarks\bench_sol.py --system baseline --label baseline --publish
.venv\Scripts\python benchmarks\bench_sol.py --system sol --label sol --publish --compare docs\quality\sol\baseline.json
```

Partições `dev` + `calib` (a cega fica de fora até um release); manifesto privado
`13dbac87bbae4c76` (190 itens: 46 regiões de PDFs nativos com verdade conferida contra a tinta,
132 itens tipografados — 60 parágrafos de livros nativos, 24 autorais em de/es/ru/pt/en, 32
páginas de duas colunas, 8 tabelas, 8 páginas de problemas — e 12 controles negativos).

| estrato | n | CER baseline | CER Sol | IC da diferença (início) | lances baseline | lances Sol | inserções |
|---|--:|--:|--:|--:|--:|--:|--:|
| native | 38 | 0,0025 | **0,0025** | — | 1,000 | 1,000 | = |
| scan_clean_300 | 137 | 0,0290 | **0,0287** | −0,038 | 0,893 | 0,910 | = |
| scan_degraded_150 | 137 | 0,0519 | **0,0371** | −0,055 | 0,776 | 0,815 | = |
| shadow_curl_bleed | 101 | 0,0758 | **0,0314** | −0,058 | 0,791 | 0,842 | 0,037 → 0,008 |
| fax_dither | 63 | 0,0635 | **0,0632** | −0,017 | 0,416 | 0,436 | = |
| photo | 63 | 0,2413 | **0,1161** | −0,179 | 0,563 | 0,707 | = |

Por idioma (CER): pt 0,060 → **0,037**; en 0,072 → **0,044**; de 0,067 → **0,051**; es 0,081 → **0,059**;
**ru 0,162 → 0,069** e lances em russo **0,019 → 0,399** (dois efeitos: `rus` passa a viajar com `eng`
para as casas latinas, e homoglifos К/K deixam de contar como lance diferente).

Custo: 0,70 → 1,91 s/MP (portfólio + candidatos de perfil + fusão), 120 s → 328 s no corpus inteiro.

Calibração da confiança que sai do sistema (acerto = CER ≤ 2 %): ECE **0,358 → 0,222**, Brier
**0,311 → 0,236**. Risco × cobertura no limiar 0,8: baseline cobre 62 % com CER 0,055; Sol cobre 74 %
com CER 0,036. 35 % dos itens vão para revisão, 5 abstêm (0,9 %), **0** entram aceitos abaixo do limiar.

Nenhum estrato regrediu fora do IC bootstrap; o limpo não foi degradado por variante alguma
(o original é sempre candidato — SOL-3).

---

## 2. O corpus: o que ele é e o que ele não é

Sol pede 200 páginas rotuladas por humanos. **Não existem.** O que o manifesto tem:

- **verdade exata sem humano**: 46 regiões de PDFs nativos cuja camada de texto foi conferida contra a
  tinta (`build_ocr_regions.py`, F11) e 60 parágrafos de livros nativos tipografados pelo próprio
  benchmark — exatos por construção, mas não são scans reais;
- **verdade autoral**: 24 parágrafos escritos para o corpus (alemão, espanhol, russo, português,
  inglês, cada um na convenção de peças do idioma) — a única fonte de espanhol e cirílico;
- **compostos**: duas colunas (ordem de leitura), tabelas (índice de partidas), páginas de problema
  (tabuleiro vazio + rótulo + solução);
- **12 controles negativos** determinísticos (branco, tabuleiro, manchas, borda, ruído, foto).

Partições fixas por hash do id (50/25/25); a cega não é carregada sem `--blind`; um manifesto
editado à mão é recusado. Dois arquivos: `manifest.json` (versionado: só texto que o repositório pode
carregar) e `manifest.private.json` (com passagens do acervo; fica na máquina, como `derived/`).

Consequência para os portões: **CER limpo ≤ 0,5 % e lances ≥ 99,8 %** estão sendo medidos contra
degradações sintéticas de páginas tipografadas em Times/Bookman/Georgia a 10,5 pt e contra regiões
nativas — não contra os scans que a meta tem em mente. O número que fecha esses portões só existe
depois de rotular scans reais; o esquema já recebe rótulo humano por item sem mudar (SOL-11 exporta
no formato). Quem for medir: `docs/quality/sol/*.md` nomeia o estrato em todo número.

---

## 3. Os quatro portões vermelhos, um a um

**CER limpo 0,0156 (meta 0,005).** `native` está em 0,0025 — passa. `scan_clean_300` está em 0,0287
e é o que puxa a média: são páginas tipografadas com blur, ruído e JPEG lidas pelo **único motor
instalado**. Nos 10 piores itens desse estrato o Tesseract troca `ó/6`, `á/4`, `l/1` em lances que
não têm posição conhecida para o replay corrigir (§4). O portão é do motor único, não do caminho.

**CER 150 DPI 0,0371 (meta 0,020).** Caiu 29 % com upscale + fusão; o resto é o mesmo motor a 150 DPI.

**Lances 0,789 (meta 0,998) e 253 inventados (meta 0).** Dois efeitos que a métrica junta e o
relatório separa: (a) um lance *alterado* conta como perdido **e** inventado (`caissa.ocr.metrics`,
por decisão: para o leitor, `Kfz` no lugar de `Kf3` é um lance que não existe); (b) **98 % dos
1.835 lances do corpus** estão em trechos sem diagrama associado e que não começam no lance 1 (trechos
de meio de partida, como um livro é) — o replay legal (SOL-8) não tem posição de partida e, por
princípio, **não assume** uma; só 2 % dos lances podem ser reproduzidos hoje. Onde ele tem posição,
ele fecha: ver `test_validate.py` (`dó→d6`, `cxdá→cxd4`, `Nf3Nc6` colado, variação entre parênteses).
O corpus humano precisa trazer a FEN de partida (ou o diagrama) de cada trecho de lances — o esquema
já tem o campo (`GoldenRegion.start_fen`).

Nenhum dos quatro está sendo "comprado" por limiar: as decisões abaixo da barra vão para revisão
(190 itens) ou abstenção (5), e o portão de importação silenciosa está em 0.

---

## 4. O que cada entrega faz, e o que a medição mostrou ao construí-la

**SOL-2 — a abstenção é real.** O árbitro tinha um verbo (aceitar); abaixo do limite o melhor de um
lote ruim era rotulado `accepted`. Agora: `exhausted` + decisão `REVIEW`/`ABSTAINED` com motivos, e a
página/corpo não emitem regiões abstidas. Pisos de evidência: caracteres, palavra ou lance em texto
curto, **tinta sob a caixa** (o `rs` na página branca), geometria das linhas, e — achado ao medir os
controles — **forma dos tokens**: o tabuleiro lido como `4 À be r Fr bi À be…` e a foto como `by s ata
ETA spa th` passavam em dicionário (todo fragmento é palavra em algum idioma). Medido nas verdades do
corpus com ≥ 12 palavras: a fração de tokens de ≤ 2 caracteres nunca passa de 0,47 e o comprimento
médio nunca cai de 3,05; os controles dão 1,00/1,4 e 0,71/2,1. Piso em 0,60/2,6: **0/9 controles**.

**SOL-4 — a calibração deixou de ser reputação.** `floor=0,55, gamma=1,4` foram removidos (o F5
ciclo 2 mediu que zeravam o Tesseract em 12 de 12 páginas). `benchmarks/calibrate_sol.py` alinha
8.496 palavras da partição `calib` à verdade e ajusta tabelas isotônicas por motor, idioma, script,
faixa de DPI e tipo de região: ECE por palavra **0,034 → 0,009** (`tesseract`), russo **0,15 → 0,06**
(`docs/quality/sol/calibration.md`). Consequência que o F5 tinha pedido para atualizar: em
Gaprindashvili p.202, Tesseract (0,727) **passa a vencer** a camada danificada (0,684) e a região vai
para revisão — o teste `test_a_damaged_text_layer_no_longer_beats_tesseract_on_fixed_confidence`
substitui o que registrava o defeito.

**SOL-6 — a fusão quase virou um jeito novo de piorar.** Primeira versão: âncora + votação ponderada.
No estrato fax, uma variante `upscale` ruidosa (CER 0,231) "corrigia" tokens da original (CER 0,031)
para 0,082. Regra final: **token-âncora que é palavra ou lance nunca é substituído**; só não-palavra
duvidosa aceita alternativa com apoio lexical e confiança igual ou maior. Depois disso o fax ficou
neutro em CER (0,0626 → 0,0632) e melhor em lances (356 → 365 de 837).

**SOL-7 — o perfil de lances vale, a whitelist só como extra.** Em 12 itens de movetext a 150 DPI:
CER 0,0168 (perfil prosa) → **0,0066** (perfil movetext, DAWGs desligados + padrões); a whitelist
estrita lê **137 vs 130** lances de 147 e destrói a prosa (CER 0,24) — exatamente o "candidato
adicional, nunca leitura única" do roadmap.

**SOL-8 — legalidade que não inventa.** Correção só quando única, integralmente legal **e com apoio
visual** (glifo duvidoso ou par de confusão conhecido): `Bxe4` confiante que só `Nxe4` tornaria legal
fica como sugestão. `side_to_move` da legenda ou da numeração; FEN de diagrama só com proveniência
confiável; quando FEN e numeração discordam, a numeração prevalece e fica registrado. VLM continua
sem substituir texto (`repair_ocr_region`, F11 ciclo 3).

**SOL-9 — sem caminho absoluto.** As listas do tronco só entram por `CAISSA_LEXICON_DIR` (com hash
registrado). Empacotados com `MANIFEST.json` (origem, licença, SHA-256): listas autorais por idioma e
nomes, mais os dicionários Hunspell com licença auditada desta máquina — SCOWL en_US, Vero pt_BR
(LGPLv3/MPL), RLA-ES es_ES (tri-licença) — com regras de afixo aplicadas em sentido inverso na
consulta (`caissa.ocr.hunspell`), 0,75 s de carga, 2 ms por página. Alemão, francês, italiano,
neerlandês e **russo** ficam com as listas autorais (nenhum Hunspell com licença auditável estava na
máquina): russo passa a ser *julgado* por um modelo de bigramas cirílico próprio — Boleslávski aceito
com os termos lexicais aplicados (`test_cyrillic_pages…`) — mas com 13–26 % de acerto de dicionário,
que é onde um `ru_RU.dic` entraria.

**SOL-5 — sem motor ao vivo.** Contratos por versão, `SchemaError` explícito, PP-StructureV3 como
backend próprio, worker isolado com protocolo versionado e medição de recursos, registro de pesos com
licença (Surya marcado "verificar"). Tudo exercitado com módulos falsos; o dia em que um Paddle/Surya
for instalado, `tests/unit/ocr/test_optional_engines.py` é o contrato e `IsolatedEngine` o caminho.

---

## 5. O que continua faltando

1. **Rótulo humano em scans reais** — sem isso os portões de CER e de lances medem tipografia
   sintética. A fila de revisão (SOL-11) já exporta no formato de calibração e do manifesto.
2. **Um segundo motor instalado** — os estratos degradados estão no teto do Tesseract sozinho; o
   roteador e o orçamento já chegam ao Surya/Paddle quando existirem.
3. **Janela de revisão** — o modelo existe; a janela é do shell F9, que não está neste repositório.
4. **Revisão humana cega de ≥ 20 páginas** e comparação com ABBYY/Acrobat — procedimento: a fila
   exporta `corrections()`, que entram no manifesto como regiões rotuladas.
5. **Dicionário russo licenciado** e mais vocabulário para de/fr/it/nl.

---

## 6. Arquivos

Novos: `caissa/ocr/{golden,metrics,gates,controls,decision,portfolio,calibration,routing,fusion,
language,review,hunspell}.py`, `caissa/ocr/notation/validate.py`, `caissa/ocr/engines/{profiles,
contracts,paddle_structure,worker,weights}.py`, `caissa/ocr/data/{calibration.json,weights.json,
lexicon/}`, `caissa/ingest/pdf/ocr_service.py`, `benchmarks/{bench_sol,sol_corpus,calibrate_sol,
sol_gate}.py`, `benchmarks/corpus/golden/`, `tools/build_lexicon.py`, `docs/quality/sol/`.
Alterados: `arbiter.py`, `page.py`, `lexicon.py`, `engines/{tesseract,paddle,surya,registry}.py`,
`ingest/pdf/{importer,textlayer}.py`, `pyproject.toml` (extras `ocr-paddle`, `ocr-surya`, `ocr-rapid`;
`pytesseract`/`rapidfuzz`/`regex` removidos por nunca terem sido importados).
