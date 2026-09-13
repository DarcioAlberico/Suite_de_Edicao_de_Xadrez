# Sol · benchmark `baseline` — baseline_blind

> 2026-09-13T10:13:01+00:00 · corpus `25699ced8cc69327` (2026.09.13) · commit `aa8d81f` · Tesseract tesseract v5.5.0.20241111 · cego incluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 84 | 84 | 0 | 0 | 0.0649 | 0.0576–0.0724 | 0.2813 | 0.4032 | 681 | 83 | 0/0 | 0.93 |
| native | 46 | 46 | 0 | 0 | 0.0023 | 0.0008–0.0042 | 0.0131 | 0.9959 | 1 | 0 | 0/12 | 0.48 |
| photo | 84 | 84 | 0 | 0 | 0.2399 | 0.2262–0.2552 | 0.3265 | 0.5522 | 511 | 36 | 0/0 | 1.00 |
| scan_clean_300 | 178 | 178 | 0 | 0 | 0.0271 | 0.0141–0.0435 | 0.0636 | 0.8810 | 282 | 23 | 0/0 | 0.46 |
| scan_degraded_150 | 178 | 178 | 0 | 0 | 0.0504 | 0.0340–0.0681 | 0.1133 | 0.7624 | 563 | 84 | 0/0 | 1.29 |
| shadow_curl_bleed | 130 | 130 | 0 | 0 | 0.0748 | 0.0684–0.0816 | 0.2545 | 0.7840 | 299 | 54 | 0/0 | 0.97 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 44 | 44 | 0.0613 | 0.1444 | 0.7706 | 25 | 1.0000 |
| en | 253 | 253 | 0.0668 | 0.1679 | 0.7564 | 175 | 1.0000 |
| es | 36 | 36 | 0.0805 | 0.1599 | 0.7377 | 10 | 1.0000 |
| mixed | 4 | 4 | 0.1469 | 0.2087 | 0.8922 | 2 | 1.0000 |
| pt | 325 | 325 | 0.0622 | 0.1372 | 0.7693 | 68 | 1.0000 |
| ru | 38 | 38 | 0.1561 | 0.4270 | 0.0365 | 0 | 0.8125 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 32 | 32 | 0.1475 | 0.4247 | 0.0362 | 0 | 1.0000 |
| latin | 668 | 668 | 0.0666 | 0.1537 | 0.7527 | 280 | 0.9808 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 16 | 16 | 0.0348 | 0.1361 | 0.7738 | 1 | 1.0000 |
| single | 604 | 604 | 0.0652 | 0.1650 | 0.7097 | 235 | — |
| table | 16 | 16 | 0.1516 | 0.1853 | 1.0000 | 0 | — |
| two-column | 64 | 64 | 0.1072 | 0.1791 | 0.7987 | 44 | 0.9766 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 271 | 271 | 0.0567 | 0.1231 | 0.8020 | 67 | 0.9766 |
| movetext | 397 | 397 | 0.0778 | 0.1958 | 0.6963 | 212 | — |
| problems | 16 | 16 | 0.0348 | 0.1361 | 0.7738 | 1 | 1.0000 |
| table | 16 | 16 | 0.1516 | 0.1853 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| blind | 161 | 161 | 0.0696 | 0.1728 | 0.6849 | 54 | 1.0000 |
| calib | 167 | 167 | 0.0636 | 0.1557 | 0.7263 | 52 | 1.0000 |
| dev | 372 | 372 | 0.0737 | 0.1678 | 0.7498 | 174 | 0.9712 |

## Calibração e abstenção

- ECE 0.3623, Brier 0.3116 em 700 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.2–0.3: 0.25→0.00 (2), 0.3–0.4: 0.38→0.00 (5), 0.4–0.5: 0.46→0.00 (20), 0.5–0.6: 0.56→0.00 (17), 0.6–0.7: 0.66→0.03 (71), 0.7–0.8: 0.75→0.07 (161), 0.8–0.9: 0.86→0.56 (196), 0.9–1.0: 0.95→0.86 (228)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.070, 0.1: 1.00/0.070, 0.2: 1.00/0.070, 0.3: 1.00/0.070, 0.4: 0.99/0.069, 0.5: 0.96/0.066, 0.6: 0.94/0.065, 0.7: 0.84/0.061, 0.8: 0.61/0.054, 0.9: 0.33/0.037, 1.0: 0.00/0.000
- Enviado para revisão: 0.0%; abstenção 0.0%; importações silenciosas abaixo do limiar: 232.
- Tempo total 156.89 s, 0.703 s/MP.

## Portões

- ✗ **CER limpo** — 0.0147 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0504 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6312/8649 lances exatos (0.7298), mínimo 0.9980
- ✗ **lances inventados** — 280 token(s) de lance sem correspondência na verdade
- ✗ **importação silenciosa abaixo do limiar** — 232 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 12 controle(s) sem texto produziram conteúdo
- ✗ **ordem de leitura em duas colunas** — 0.9812 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `synth:Dvoretsky - Dvoretsky's :201:21` | photo | 0.6964 | tesseract | accepted |
| `table:4` | scan_degraded_150 | 0.6946 | tesseract | accepted |
| `twocol:d:9` | scan_clean_300 | 0.6878 | tesseract | accepted |
| `twocol:a:9` | scan_degraded_150 | 0.6721 | tesseract | accepted |
| `twocol:d:4` | scan_clean_300 | 0.6199 | tesseract | accepted |
| `twocol:d:17` | scan_degraded_150 | 0.6128 | tesseract | accepted |
| `twocol:a:5` | scan_clean_300 | 0.6076 | tesseract | accepted |
| `table:3` | scan_degraded_150 | 0.5813 | tesseract | accepted |
| `twocol:a:4` | scan_clean_300 | 0.5615 | tesseract | accepted |
| `authored:de:4` | photo | 0.5312 | tesseract | accepted |
