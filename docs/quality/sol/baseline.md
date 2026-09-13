# Sol · benchmark `baseline` — baseline

> 2026-09-13T08:53:17+00:00 · corpus `1e35c70dc0e0d415` (2026.09.13) · commit `62d7406` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 0 | 0.0635 | 0.0555–0.0714 | 0.2779 | 0.4159 | 500 | 62 | 0/0 | 0.92 |
| native | 38 | 38 | 0 | 0 | 0.0025 | 0.0008–0.0046 | 0.0133 | 1.0000 | 0 | 0 | 0/9 | 0.47 |
| photo | 63 | 63 | 0 | 0 | 0.2413 | 0.2243–0.2621 | 0.3286 | 0.5631 | 374 | 29 | 0/0 | 0.99 |
| scan_clean_300 | 137 | 137 | 0 | 0 | 0.0290 | 0.0126–0.0507 | 0.0618 | 0.8932 | 196 | 19 | 0/0 | 0.46 |
| scan_degraded_150 | 137 | 137 | 0 | 0 | 0.0519 | 0.0332–0.0756 | 0.1111 | 0.7755 | 412 | 72 | 0/0 | 1.30 |
| shadow_curl_bleed | 101 | 101 | 0 | 0 | 0.0758 | 0.0684–0.0830 | 0.2576 | 0.7913 | 220 | 44 | 0/0 | 0.96 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0670 | 0.1520 | 0.7571 | 12 | 1.0000 |
| en | 178 | 178 | 0.0721 | 0.1772 | 0.7656 | 144 | 1.0000 |
| es | 34 | 34 | 0.0812 | 0.1580 | 0.7360 | 10 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.8750 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0602 | 0.1347 | 0.7747 | 59 | 1.0000 |
| ru | 21 | 21 | 0.1617 | 0.4465 | 0.0188 | 0 | 0.7500 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.1455 | 0.4494 | 0.0000 | 0 | — |
| latin | 524 | 524 | 0.0684 | 0.1559 | 0.7554 | 226 | 0.9750 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0231 | 0.1095 | 0.7917 | 1 | 1.0000 |
| single | 467 | 467 | 0.0633 | 0.1608 | 0.7244 | 190 | — |
| table | 12 | 12 | 0.1900 | 0.2231 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.1159 | 0.1878 | 0.8058 | 35 | 0.9712 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 216 | 216 | 0.0612 | 0.1311 | 0.8060 | 52 | 0.9712 |
| movetext | 303 | 303 | 0.0737 | 0.1866 | 0.7129 | 173 | — |
| problems | 8 | 8 | 0.0231 | 0.1095 | 0.7917 | 1 | 1.0000 |
| table | 12 | 12 | 0.1900 | 0.2231 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 167 | 167 | 0.0636 | 0.1557 | 0.7263 | 52 | 1.0000 |
| dev | 372 | 372 | 0.0737 | 0.1678 | 0.7498 | 174 | 0.9712 |

## Calibração e abstenção

- ECE 0.3578, Brier 0.3109 em 539 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.2–0.3: 0.28→0.00 (1), 0.3–0.4: 0.39→0.00 (4), 0.4–0.5: 0.46→0.00 (9), 0.5–0.6: 0.56→0.00 (12), 0.6–0.7: 0.66→0.00 (53), 0.7–0.8: 0.76→0.08 (126), 0.8–0.9: 0.86→0.54 (145), 0.9–1.0: 0.94→0.87 (189)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.071, 0.1: 1.00/0.071, 0.2: 1.00/0.071, 0.3: 1.00/0.070, 0.4: 0.99/0.069, 0.5: 0.97/0.067, 0.6: 0.95/0.066, 0.7: 0.85/0.063, 0.8: 0.62/0.055, 0.9: 0.35/0.038, 1.0: 0.00/0.000
- Enviado para revisão: 0.0%; abstenção 0.0%; importações silenciosas abaixo do limiar: 166.
- Tempo total 119.8 s, 0.6985 s/MP.

## Portões

- ✗ **CER limpo** — 0.0157 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0519 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 4932/6634 lances exatos (0.7434), mínimo 0.9980
- ✗ **lances inventados** — 226 token(s) de lance sem correspondência na verdade
- ✗ **importação silenciosa abaixo do limiar** — 166 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✗ **ordem de leitura em duas colunas** — 0.9750 de ordem correta nos itens com mais de uma região
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
