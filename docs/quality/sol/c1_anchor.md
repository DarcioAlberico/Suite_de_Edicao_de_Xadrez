# Sol · benchmark `sol` — c1_anchor

> 2026-09-14T20:52:17+00:00 · corpus `43ac7c57017324d8` (2026.09.13) · commit `f28f2fc` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 18 | 0.0318 | 0.0212–0.0442 | 0.1066 | 0.8236 | 151 | 26 | 0/0 | 5.70 |
| native | 237 | 175 | 62 | 69 | 0.0151 | 0.0096–0.0226 | 0.0389 | 0.9083 | 56 | 25 | 0/9 | 2.25 |
| photo | 63 | 63 | 0 | 17 | 0.1115 | 0.0783–0.1460 | 0.1663 | 0.8224 | 152 | 24 | 0/0 | 8.38 |
| scan_clean_300 | 137 | 137 | 0 | 44 | 0.0279 | 0.0119–0.0495 | 0.0505 | 0.9509 | 90 | 21 | 0/0 | 1.15 |
| scan_degraded_150 | 137 | 137 | 0 | 41 | 0.0341 | 0.0184–0.0544 | 0.0763 | 0.8725 | 234 | 63 | 0/0 | 6.33 |
| shadow_curl_bleed | 101 | 101 | 0 | 23 | 0.0386 | 0.0255–0.0529 | 0.0930 | 0.9345 | 69 | 8 | 0/0 | 6.27 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0499 | 0.0861 | 0.8250 | 7 | 1.0000 |
| en | 377 | 315 | 0.0245 | 0.0543 | 0.9307 | 90 | 1.0000 |
| es | 34 | 34 | 0.0560 | 0.0983 | 0.8539 | 8 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.9107 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0386 | 0.0767 | 0.8770 | 48 | 1.0000 |
| ru | 21 | 21 | 0.0884 | 0.2867 | 0.4883 | 13 | 0.9167 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.0975 | 0.3001 | 0.4952 | 12 | — |
| latin | 723 | 661 | 0.0342 | 0.0700 | 0.8993 | 155 | 0.9917 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| single | 666 | 604 | 0.0288 | 0.0673 | 0.8904 | 135 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.0924 | 0.1433 | 0.9003 | 32 | 0.9904 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 265 | 0.0393 | 0.0836 | 0.8819 | 63 | 0.9904 |
| movetext | 339 | 327 | 0.0356 | 0.0772 | 0.8976 | 104 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| prose | 71 | 64 | 0.0022 | 0.0106 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 226 | 0.0289 | 0.0678 | 0.8807 | 56 | 1.0000 |
| dev | 498 | 450 | 0.0390 | 0.0788 | 0.8983 | 111 | 0.9904 |

## Calibração e abstenção

- ECE 0.1437, Brier 0.1899 em 676 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.5–0.6: 0.54→0.62 (8), 0.6–0.7: 0.65→0.29 (28), 0.7–0.8: 0.77→0.45 (60), 0.8–0.9: 0.86→0.69 (224), 0.9–1.0: 0.95→0.86 (356)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.036, 0.1: 1.00/0.036, 0.2: 1.00/0.036, 0.3: 1.00/0.036, 0.4: 1.00/0.036, 0.5: 1.00/0.036, 0.6: 0.99/0.035, 0.7: 0.95/0.034, 0.8: 0.86/0.031, 0.9: 0.53/0.025, 1.0: 0.00/0.000
- Enviado para revisão: 28.7%; abstenção 8.4%; importações silenciosas abaixo do limiar: 0.
- Tempo total 644.0 s, 3.2526 s/MP.

## Portões

- ✗ **CER limpo** — 0.0215 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0341 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6295/7047 lances exatos (0.8933), mínimo 0.9980
- ✗ **lances inventados** — 167 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✗ **ordem de leitura em duas colunas** — 0.9917 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados
- ✓ **regressão de CER [fax_dither]** — CER 0.0318 → 0.0318 (Δ +0.0000; IC da diferença começa em -0.0230)
- ✓ **inserções de texto [fax_dither]** — taxa de inserção 0.0017 → 0.0017
- ✓ **regressão de CER [native]** — CER 0.0151 → 0.0151 (Δ -0.0000; IC da diferença começa em -0.0130)
- ✓ **inserções de texto [native]** — taxa de inserção 0.0017 → 0.0017
- ✓ **regressão de CER [photo]** — CER 0.1115 → 0.1115 (Δ +0.0000; IC da diferença começa em -0.0677)
- ✓ **inserções de texto [photo]** — taxa de inserção 0.0024 → 0.0024
- ✓ **regressão de CER [scan_clean_300]** — CER 0.0281 → 0.0279 (Δ -0.0001; IC da diferença começa em -0.0378)
- ✓ **inserções de texto [scan_clean_300]** — taxa de inserção 0.0006 → 0.0006
- ✓ **ordem de leitura [scan_clean_300]** — 0.983 → 0.983
- ✓ **regressão de CER [scan_degraded_150]** — CER 0.0342 → 0.0341 (Δ -0.0001; IC da diferença começa em -0.0360)
- ✓ **inserções de texto [scan_degraded_150]** — taxa de inserção 0.0004 → 0.0004
- ✓ **ordem de leitura [scan_degraded_150]** — 1.000 → 1.000
- ✓ **regressão de CER [shadow_curl_bleed]** — CER 0.0386 → 0.0386 (Δ +0.0000; IC da diferença começa em -0.0274)
- ✓ **inserções de texto [shadow_curl_bleed]** — taxa de inserção 0.0138 → 0.0138

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `synth:Dvoretsky - Dvoretsky's :201:21` | photo | 0.6964 | tesseract | accepted |
| `twocol:d:9` | scan_clean_300 | 0.6878 | tesseract | accepted |
| `table:7` | scan_degraded_150 | 0.6761 | tesseract | review |
| `table:4` | scan_degraded_150 | 0.6400 | tesseract | review |
| `twocol:d:4` | scan_clean_300 | 0.6222 | tesseract | review |
| `twocol:d:17` | scan_degraded_150 | 0.6110 | tesseract | accepted |
| `twocol:a:5` | scan_clean_300 | 0.6076 | tesseract | accepted |
| `twocol:a:4` | scan_clean_300 | 0.5615 | tesseract | review |
| `authored:de:4` | photo | 0.5312 | tesseract | accepted |
| `twocol:d:18` | scan_clean_300 | 0.4948 | tesseract | accepted |
