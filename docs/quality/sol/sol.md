# Sol · benchmark `sol` — sol

> 2026-09-13T09:17:01+00:00 · corpus `1e35c70dc0e0d415` (2026.09.13) · commit `69583fd` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 61 | 2 | 43 | 0.0632 | 0.0544–0.0723 | 0.2657 | 0.4361 | 472 | 75 | 0/0 | 2.73 |
| native | 38 | 38 | 0 | 5 | 0.0025 | 0.0008–0.0046 | 0.0133 | 1.0000 | 0 | 0 | 0/9 | 0.51 |
| photo | 63 | 62 | 1 | 19 | 0.1161 | 0.0832–0.1542 | 0.1792 | 0.7065 | 248 | 35 | 0/0 | 5.03 |
| scan_clean_300 | 137 | 137 | 0 | 31 | 0.0287 | 0.0124–0.0505 | 0.0603 | 0.9101 | 165 | 24 | 0/0 | 0.58 |
| scan_degraded_150 | 137 | 135 | 2 | 36 | 0.0371 | 0.0204–0.0568 | 0.0897 | 0.8150 | 334 | 77 | 0/0 | 3.54 |
| shadow_curl_bleed | 101 | 101 | 0 | 56 | 0.0314 | 0.0249–0.0384 | 0.1290 | 0.8416 | 167 | 42 | 0/0 | 4.55 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0512 | 0.1057 | 0.7607 | 11 | 1.0000 |
| en | 178 | 178 | 0.0443 | 0.1317 | 0.8053 | 158 | 1.0000 |
| es | 34 | 34 | 0.0588 | 0.1136 | 0.7584 | 11 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.8750 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0374 | 0.0918 | 0.7964 | 62 | 1.0000 |
| ru | 21 | 16 | 0.0685 | 0.3061 | 0.3987 | 10 | 1.0000 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 11 | 0.0743 | 0.3212 | 0.3750 | 8 | — |
| latin | 524 | 523 | 0.0429 | 0.1103 | 0.7932 | 245 | 1.0000 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0230 | 0.1089 | 0.7708 | 2 | 1.0000 |
| single | 467 | 463 | 0.0355 | 0.1080 | 0.7702 | 212 | — |
| table | 12 | 12 | 0.1526 | 0.1908 | 1.0000 | 0 | — |
| two-column | 52 | 51 | 0.0944 | 0.1583 | 0.8535 | 39 | 1.0000 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 216 | 215 | 0.0390 | 0.0926 | 0.8440 | 57 | 1.0000 |
| movetext | 303 | 299 | 0.0430 | 0.1276 | 0.7631 | 194 | — |
| problems | 8 | 8 | 0.0230 | 0.1089 | 0.7708 | 2 | 1.0000 |
| table | 12 | 12 | 0.1526 | 0.1908 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 167 | 164 | 0.0341 | 0.0977 | 0.7865 | 62 | 1.0000 |
| dev | 372 | 370 | 0.0478 | 0.1222 | 0.7902 | 191 | 1.0000 |

## Calibração e abstenção

- ECE 0.2221, Brier 0.2360 em 534 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.5–0.6: 0.55→0.00 (12), 0.6–0.7: 0.66→0.00 (20), 0.7–0.8: 0.77→0.19 (107), 0.8–0.9: 0.85→0.73 (188), 0.9–1.0: 0.94→0.88 (207)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.044, 0.1: 1.00/0.044, 0.2: 1.00/0.044, 0.3: 1.00/0.044, 0.4: 1.00/0.044, 0.5: 1.00/0.044, 0.6: 0.98/0.042, 0.7: 0.94/0.041, 0.8: 0.74/0.036, 0.9: 0.39/0.036, 1.0: 0.00/0.000
- Enviado para revisão: 35.2%; abstenção 0.9%; importações silenciosas abaixo do limiar: 0.
- Tempo total 328.27 s, 1.9141 s/MP.

## Portões

- ✗ **CER limpo** — 0.0156 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0371 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 5188/6574 lances exatos (0.7892), mínimo 0.9980
- ✗ **lances inventados** — 253 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✓ **ordem de leitura em duas colunas** — 1.0000 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados
- ✓ **regressão de CER [fax_dither]** — CER 0.0635 → 0.0632 (Δ -0.0004; IC da diferença começa em -0.0169)
- ✓ **inserções de texto [fax_dither]** — taxa de inserção 0.0042 → 0.0040
- ✓ **regressão de CER [native]** — CER 0.0025 → 0.0025 (Δ +0.0000; IC da diferença começa em -0.0038)
- ✓ **inserções de texto [native]** — taxa de inserção 0.0006 → 0.0006
- ✓ **regressão de CER [photo]** — CER 0.2413 → 0.1161 (Δ -0.1253; IC da diferença começa em -0.1788)
- ✓ **inserções de texto [photo]** — taxa de inserção 0.0000 → 0.0010
- ✓ **regressão de CER [scan_clean_300]** — CER 0.0290 → 0.0287 (Δ -0.0003; IC da diferença começa em -0.0383)
- ✓ **inserções de texto [scan_clean_300]** — taxa de inserção 0.0009 → 0.0008
- ✓ **ordem de leitura [scan_clean_300]** — 1.000 → 1.000
- ✓ **regressão de CER [scan_degraded_150]** — CER 0.0519 → 0.0371 (Δ -0.0148; IC da diferença começa em -0.0551)
- ✓ **inserções de texto [scan_degraded_150]** — taxa de inserção 0.0006 → 0.0007
- ✓ **ordem de leitura [scan_degraded_150]** — 0.950 → 1.000
- ✓ **regressão de CER [shadow_curl_bleed]** — CER 0.0758 → 0.0314 (Δ -0.0444; IC da diferença começa em -0.0581)
- ✓ **inserções de texto [shadow_curl_bleed]** — taxa de inserção 0.0374 → 0.0081

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `synth:Dvoretsky - Dvoretsky's :201:21` | photo | 0.6964 | tesseract | accepted |
| `twocol:d:9` | scan_clean_300 | 0.6878 | tesseract | accepted |
| `table:7` | scan_degraded_150 | 0.6761 | tesseract | review |
| `table:4` | scan_degraded_150 | 0.6400 | tesseract | review |
| `twocol:d:4` | scan_clean_300 | 0.6199 | tesseract | accepted |
| `twocol:d:17` | scan_degraded_150 | 0.6128 | tesseract | accepted |
| `twocol:a:5` | scan_clean_300 | 0.6076 | tesseract | accepted |
| `twocol:a:4` | scan_clean_300 | 0.5615 | tesseract | accepted |
| `authored:de:4` | photo | 0.5312 | tesseract | accepted |
| `twocol:d:18` | scan_clean_300 | 0.5000 | tesseract | accepted |
