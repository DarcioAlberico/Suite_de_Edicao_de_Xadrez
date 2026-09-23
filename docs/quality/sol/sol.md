# Sol · benchmark `sol` — sol

> 2026-09-23T15:11:39+00:00 · corpus `f019591babf2941e` (2026.09.13) · commit `3ff1830` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | aceitos errados | CER médio | IC 95% | CER c/ abst. | CER retido | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 21 | 1 | 0.0249 | 0.0177–0.0327 | 0.0249 | — | 0.0999 | 0.8505 | 128 | 23 | 0/0 | 5.87 |
| native | 237 | 199 | 38 | 94 | 1 | 0.0171 | 0.0105–0.0245 | 0.1747 | 0.4648 (19) | 0.0400 | 0.9416 | 47 | 23 | 0/9 | 2.32 |
| photo | 63 | 63 | 0 | 17 | 1 | 0.0207 | 0.0097–0.0362 | 0.0207 | — | 0.0558 | 0.9357 | 55 | 20 | 0/0 | 9.09 |
| scan_clean_300 | 137 | 137 | 0 | 49 | 0 | 0.0054 | 0.0035–0.0076 | 0.0054 | — | 0.0267 | 0.9504 | 91 | 22 | 0/0 | 1.33 |
| scan_degraded_150 | 137 | 137 | 0 | 43 | 0 | 0.0094 | 0.0075–0.0115 | 0.0094 | — | 0.0477 | 0.8817 | 217 | 60 | 0/0 | 6.63 |
| shadow_curl_bleed | 101 | 101 | 0 | 28 | 4 | 0.0359 | 0.0236–0.0505 | 0.0359 | — | 0.0871 | 0.9364 | 67 | 9 | 0/0 | 6.32 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0164 | 0.0494 | 0.8893 | 6 | 1.0000 |
| en | 377 | 339 | 0.0165 | 0.0451 | 0.9456 | 85 | 1.0000 |
| es | 34 | 34 | 0.0108 | 0.0437 | 0.8904 | 5 | 1.0000 |
| mixed | 2 | 2 | 0.0042 | 0.0236 | 0.9464 | 0 | 1.0000 |
| pt | 279 | 279 | 0.0142 | 0.0460 | 0.9079 | 45 | 1.0000 |
| ru | 21 | 21 | 0.0753 | 0.2797 | 0.4883 | 16 | 1.0000 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.0851 | 0.2892 | 0.4952 | 14 | — |
| latin | 723 | 685 | 0.0156 | 0.0473 | 0.9226 | 143 | 1.0000 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| single | 666 | 628 | 0.0179 | 0.0529 | 0.9197 | 126 | — |
| table | 12 | 12 | 0.0038 | 0.0166 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.0111 | 0.0566 | 0.9016 | 31 | 1.0000 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 277 | 0.0204 | 0.0621 | 0.8905 | 61 | 1.0000 |
| movetext | 339 | 339 | 0.0178 | 0.0539 | 0.9278 | 96 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| prose | 71 | 64 | 0.0022 | 0.0106 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.0038 | 0.0166 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 232 | 0.0188 | 0.0537 | 0.9041 | 54 | 1.0000 |
| dev | 498 | 468 | 0.0162 | 0.0519 | 0.9214 | 103 | 1.0000 |

## Calibração e abstenção

- ECE 0.0762, Brier 0.1398 em 700 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.1–0.2: 0.10→0.00 (1), 0.2–0.3: 0.25→0.80 (5), 0.3–0.4: 0.35→0.29 (7), 0.4–0.5: 0.44→0.80 (10), 0.5–0.6: 0.55→0.58 (12), 0.6–0.7: 0.65→0.42 (26), 0.7–0.8: 0.76→0.56 (62), 0.8–0.9: 0.86→0.76 (211), 0.9–1.0: 0.95→0.93 (366)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.017, 0.1: 1.00/0.017, 0.2: 1.00/0.017, 0.3: 0.99/0.017, 0.4: 0.98/0.016, 0.5: 0.97/0.016, 0.6: 0.95/0.015, 0.7: 0.91/0.014, 0.8: 0.82/0.012, 0.9: 0.52/0.006, 1.0: 0.00/0.000
- Enviado para revisão: 34.2%; abstenção 5.1%; importações silenciosas abaixo do limiar: 0; aceitos com CER > 10 %: 7.
- Tempo total 680.87 s, 3.4388 s/MP.

## Portões

- ✗ **CER limpo** — 0.0113 em 2 estrato(s) limpo(s), limite 0.0050
- ✓ **CER 150 DPI** — 0.0094 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6636/7241 lances exatos (0.9164), mínimo 0.9980
- ✗ **lances inventados** — 157 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✓ **ordem de leitura em duas colunas** — 1.0000 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `real:Xadrez Vitorioso - Finai:156:266` | shadow_curl_bleed | 0.4255 | rapidocr | accepted |
| `real:Dvoretsky,_Mark_&_Yusupo:20:96:252` | native | 0.4167 | tesseract | accepted |
| `authored:ru:14` | shadow_curl_bleed | 0.3923 | rapidocr | review |
| `real:Dvoretsky,_Mark_&_Yusupo:11:280:251` | native | 0.3636 | tesseract | review |
| `synth:Dvoretsky - Dvoretsky's :103:8` | photo | 0.3213 | rapidocr | review |
| `real:Dvoretsky,_Mark_&_Yusupo:15:119:251` | native | 0.2692 | tesseract | review |
| `synth:Dvoretsky - Dvoretsky's :89:6` | photo | 0.2508 | rapidocr | review |
| `real:Xadrez Vitorioso - Finai:52:75` | shadow_curl_bleed | 0.2359 | rapidocr | review |
| `synth:Dvoretsky - Dvoretsky's :75:4` | shadow_curl_bleed | 0.2210 | rapidocr | accepted |
| `real:Xadrez Vitorioso - Finai:176:733` | shadow_curl_bleed | 0.2174 | rapidocr | review |
