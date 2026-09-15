# Sol · benchmark `baseline` — baseline

> 2026-09-15T05:19:45+00:00 · corpus `86426402f56220aa` (2026.09.13) · commit `48d762b` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 0 | 0.0449 | 0.0298–0.0600 | 0.1279 | 0.7921 | 178 | 25 | 0/0 | 3.13 |
| native | 237 | 230 | 7 | 0 | 0.0921 | 0.0745–0.1111 | 0.2564 | 0.4348 | 477 | 292 | 0/9 | 2.32 |
| photo | 63 | 63 | 0 | 0 | 0.2004 | 0.1732–0.2286 | 0.2739 | 0.6706 | 282 | 22 | 0/0 | 1.73 |
| scan_clean_300 | 137 | 137 | 0 | 0 | 0.0330 | 0.0169–0.0546 | 0.0574 | 0.9324 | 124 | 14 | 0/0 | 0.65 |
| scan_degraded_150 | 137 | 137 | 0 | 0 | 0.0454 | 0.0265–0.0695 | 0.0920 | 0.8371 | 299 | 65 | 0/0 | 2.27 |
| shadow_curl_bleed | 101 | 101 | 0 | 0 | 0.0397 | 0.0280–0.0530 | 0.1060 | 0.9288 | 75 | 12 | 0/0 | 3.44 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0551 | 0.0874 | 0.8179 | 7 | 1.0000 |
| en | 377 | 370 | 0.0789 | 0.1985 | 0.8038 | 360 | 1.0000 |
| es | 34 | 34 | 0.0684 | 0.1166 | 0.8118 | 8 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.8750 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0544 | 0.1020 | 0.8302 | 51 | 1.0000 |
| ru | 21 | 21 | 0.1311 | 0.3166 | 0.4648 | 3 | 0.8333 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.1143 | 0.3030 | 0.5048 | 3 | — |
| latin | 723 | 716 | 0.0694 | 0.1549 | 0.8073 | 427 | 0.9833 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 0.9792 | 1 | 1.0000 |
| single | 666 | 659 | 0.0657 | 0.1574 | 0.7837 | 397 | — |
| table | 12 | 12 | 0.1900 | 0.2231 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.1103 | 0.1656 | 0.8699 | 32 | 0.9808 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 301 | 0.0830 | 0.2019 | 0.8135 | 131 | 0.9808 |
| movetext | 339 | 339 | 0.0604 | 0.1388 | 0.7961 | 298 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 0.9792 | 1 | 1.0000 |
| prose | 71 | 71 | 0.0502 | 0.0636 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.1900 | 0.2231 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 238 | 0.0568 | 0.1428 | 0.7548 | 162 | 1.0000 |
| dev | 498 | 493 | 0.0768 | 0.1652 | 0.8221 | 268 | 0.9808 |

## Calibração e abstenção

- ECE 0.2711, Brier 0.2734 em 731 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.4–0.5: 0.46→0.00 (6), 0.5–0.6: 0.55→0.00 (13), 0.6–0.7: 0.65→0.00 (20), 0.7–0.8: 0.77→0.21 (91), 0.8–0.9: 0.86→0.53 (255), 0.9–1.0: 0.95→0.83 (346)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.070, 0.1: 1.00/0.070, 0.2: 1.00/0.070, 0.3: 1.00/0.070, 0.4: 1.00/0.070, 0.5: 0.99/0.069, 0.6: 0.97/0.066, 0.7: 0.95/0.062, 0.8: 0.82/0.052, 0.9: 0.47/0.039, 1.0: 0.00/0.000
- Enviado para revisão: 0.0%; abstenção 0.9%; importações silenciosas abaixo do limiar: 73.
- Tempo total 344.27 s, 1.7388 s/MP.

## Portões

- ✗ **CER limpo** — 0.0626 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0454 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 5845/7280 lances exatos (0.8029), mínimo 0.9980
- ✗ **lances inventados** — 430 token(s) de lance sem correspondência na verdade
- ✗ **importação silenciosa abaixo do limiar** — 73 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✗ **ordem de leitura em duas colunas** — 0.9833 de ordem correta nos itens com mais de uma região
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
| `real:Dvoretsky,_Mark_&_Yusupo:19:96:52` | native | 0.6154 | tesseract | accepted |
| `twocol:d:17` | scan_degraded_150 | 0.6128 | tesseract | accepted |
| `twocol:a:5` | scan_clean_300 | 0.6076 | tesseract | accepted |
| `real:Dvoretsky,_Mark_&_Yusupo:13:258:223` | native | 0.6000 | rapidocr | accepted |
| `table:3` | scan_degraded_150 | 0.5813 | tesseract | accepted |
