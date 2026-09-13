# Sol · benchmark `sol` — sol_blind

> 2026-09-13T10:21:11+00:00 · corpus `25699ced8cc69327` (2026.09.13) · commit `aa8d81f` · Tesseract tesseract v5.5.0.20241111 · cego incluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 84 | 81 | 3 | 58 | 0.0685 | 0.0583–0.0808 | 0.2742 | 0.4220 | 645 | 95 | 0/0 | 2.86 |
| native | 46 | 46 | 0 | 5 | 0.0023 | 0.0008–0.0042 | 0.0131 | 0.9959 | 1 | 0 | 0/12 | 0.52 |
| photo | 84 | 83 | 1 | 27 | 0.1266 | 0.0995–0.1584 | 0.1915 | 0.7026 | 336 | 40 | 0/0 | 5.05 |
| scan_clean_300 | 178 | 177 | 1 | 41 | 0.0261 | 0.0120–0.0420 | 0.0594 | 0.9032 | 229 | 28 | 0/0 | 0.60 |
| scan_degraded_150 | 178 | 174 | 4 | 48 | 0.0346 | 0.0217–0.0505 | 0.0889 | 0.8035 | 458 | 89 | 0/0 | 3.75 |
| shadow_curl_bleed | 130 | 128 | 2 | 71 | 0.0305 | 0.0305–0.0305 | 0.1295 | 0.8456 | 210 | 52 | 0/0 | 4.60 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 44 | 44 | 0.0437 | 0.1004 | 0.7887 | 20 | 1.0000 |
| en | 253 | 253 | 0.0447 | 0.1293 | 0.7954 | 190 | 1.0000 |
| es | 36 | 36 | 0.0593 | 0.1180 | 0.7596 | 11 | 1.0000 |
| mixed | 4 | 4 | 0.1469 | 0.2087 | 0.8922 | 2 | 1.0000 |
| pt | 325 | 325 | 0.0389 | 0.0940 | 0.7897 | 69 | 1.0000 |
| ru | 38 | 27 | 0.0778 | 0.3155 | 0.4078 | 12 | 1.0000 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 32 | 22 | 0.0827 | 0.3251 | 0.4042 | 10 | — |
| latin | 668 | 667 | 0.0433 | 0.1111 | 0.7888 | 294 | 1.0000 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 16 | 14 | 0.0242 | 0.0957 | 0.8205 | 2 | 1.0000 |
| single | 604 | 596 | 0.0384 | 0.1139 | 0.7621 | 254 | — |
| table | 16 | 16 | 0.1158 | 0.1497 | 1.0000 | 0 | — |
| two-column | 64 | 63 | 0.0890 | 0.1529 | 0.8422 | 48 | 1.0000 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 271 | 270 | 0.0375 | 0.0891 | 0.8363 | 69 | 1.0000 |
| movetext | 397 | 389 | 0.0472 | 0.1375 | 0.7539 | 233 | — |
| problems | 16 | 14 | 0.0242 | 0.0957 | 0.8205 | 2 | 1.0000 |
| table | 16 | 16 | 0.1158 | 0.1497 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| blind | 161 | 155 | 0.0481 | 0.1294 | 0.7501 | 51 | 1.0000 |
| calib | 167 | 164 | 0.0341 | 0.0977 | 0.7865 | 62 | 1.0000 |
| dev | 372 | 370 | 0.0478 | 0.1222 | 0.7902 | 191 | 1.0000 |

## Calibração e abstenção

- ECE 0.2343, Brier 0.2437 em 689 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.5–0.6: 0.55→0.00 (18), 0.6–0.7: 0.66→0.06 (33), 0.7–0.8: 0.77→0.17 (138), 0.8–0.9: 0.85→0.72 (250), 0.9–1.0: 0.94→0.88 (250)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.045, 0.1: 1.00/0.045, 0.2: 1.00/0.045, 0.3: 1.00/0.045, 0.4: 1.00/0.045, 0.5: 1.00/0.045, 0.6: 0.97/0.043, 0.7: 0.93/0.041, 0.8: 0.73/0.036, 0.9: 0.36/0.035, 1.0: 0.00/0.000
- Enviado para revisão: 35.7%; abstenção 1.6%; importações silenciosas abaixo do limiar: 0.
- Tempo total 440.53 s, 1.974 s/MP.

## Portões

- ✗ **CER limpo** — 0.0142 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0346 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6668/8547 lances exatos (0.7802), mínimo 0.9980
- ✗ **lances inventados** — 304 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 12 controle(s) sem texto produziram conteúdo
- ✓ **ordem de leitura em duas colunas** — 1.0000 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados
- ✓ **regressão de CER [fax_dither]** — CER 0.0649 → 0.0685 (Δ +0.0036; IC da diferença começa em -0.0141)
- ✓ **inserções de texto [fax_dither]** — taxa de inserção 0.0041 → 0.0040
- ✓ **regressão de CER [native]** — CER 0.0023 → 0.0023 (Δ +0.0000; IC da diferença começa em -0.0033)
- ✓ **inserções de texto [native]** — taxa de inserção 0.0005 → 0.0005
- ✓ **regressão de CER [photo]** — CER 0.2399 → 0.1266 (Δ -0.1133; IC da diferença começa em -0.1557)
- ✓ **inserções de texto [photo]** — taxa de inserção 0.0000 → 0.0008
- ✓ **regressão de CER [scan_clean_300]** — CER 0.0271 → 0.0261 (Δ -0.0011; IC da diferença começa em -0.0315)
- ✓ **inserções de texto [scan_clean_300]** — taxa de inserção 0.0009 → 0.0009
- ✓ **ordem de leitura [scan_clean_300]** — 1.000 → 1.000
- ✓ **regressão de CER [scan_degraded_150]** — CER 0.0504 → 0.0346 (Δ -0.0158; IC da diferença começa em -0.0463)
- ✓ **inserções de texto [scan_degraded_150]** — taxa de inserção 0.0010 → 0.0010
- ✓ **ordem de leitura [scan_degraded_150]** — 0.963 → 1.000
- ✓ **regressão de CER [shadow_curl_bleed]** — CER 0.0748 → 0.0305 (Δ -0.0443; IC da diferença começa em -0.0511)
- ✓ **inserções de texto [shadow_curl_bleed]** — taxa de inserção 0.0361 → 0.0073

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
