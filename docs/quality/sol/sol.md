# Sol · benchmark `sol` — sol

> 2026-09-21T17:49:42+00:00 · corpus `f019591babf2941e` (2026.09.13) · commit `f3bd27e` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | CER c/ abst. | CER retido | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 19 | 0.0382 | 0.0251–0.0547 | 0.0382 | — | 0.1104 | 0.8201 | 154 | 23 | 0/0 | 5.60 |
| native | 237 | 199 | 38 | 94 | 0.0235 | 0.0141–0.0344 | 0.1801 | 0.4648 (19) | 0.0469 | 0.9416 | 47 | 23 | 0/9 | 2.85 |
| photo | 63 | 63 | 0 | 16 | 0.0983 | 0.0685–0.1320 | 0.0983 | — | 0.1460 | 0.8516 | 127 | 21 | 0/0 | 7.19 |
| scan_clean_300 | 137 | 137 | 0 | 49 | 0.0054 | 0.0035–0.0076 | 0.0054 | — | 0.0267 | 0.9504 | 91 | 22 | 0/0 | 1.33 |
| scan_degraded_150 | 137 | 137 | 0 | 43 | 0.0224 | 0.0094–0.0400 | 0.0224 | — | 0.0627 | 0.8817 | 217 | 60 | 0/0 | 6.65 |
| shadow_curl_bleed | 101 | 101 | 0 | 27 | 0.0377 | 0.0249–0.0522 | 0.0377 | — | 0.0874 | 0.9364 | 67 | 9 | 0/0 | 6.34 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0329 | 0.0685 | 0.8679 | 7 | 1.0000 |
| en | 377 | 339 | 0.0250 | 0.0537 | 0.9362 | 83 | 1.0000 |
| es | 34 | 34 | 0.0345 | 0.0716 | 0.8708 | 6 | 1.0000 |
| mixed | 2 | 2 | 0.0042 | 0.0236 | 0.9464 | 0 | 1.0000 |
| pt | 279 | 279 | 0.0302 | 0.0651 | 0.8862 | 46 | 1.0000 |
| ru | 21 | 21 | 0.0943 | 0.2861 | 0.4883 | 16 | 1.0000 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.1118 | 0.2982 | 0.4952 | 14 | — |
| latin | 723 | 685 | 0.0280 | 0.0614 | 0.9089 | 144 | 1.0000 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| single | 666 | 628 | 0.0293 | 0.0652 | 0.9024 | 127 | — |
| table | 12 | 12 | 0.1517 | 0.1872 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.0111 | 0.0566 | 0.9016 | 31 | 1.0000 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 277 | 0.0262 | 0.0674 | 0.8892 | 61 | 1.0000 |
| movetext | 339 | 339 | 0.0342 | 0.0723 | 0.9084 | 97 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| prose | 71 | 64 | 0.0022 | 0.0106 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.1517 | 0.1872 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 232 | 0.0262 | 0.0627 | 0.8935 | 55 | 1.0000 |
| dev | 498 | 468 | 0.0316 | 0.0684 | 0.9067 | 103 | 1.0000 |

## Calibração e abstenção

- ECE 0.1050, Brier 0.1631 em 700 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.1–0.2: 0.10→0.00 (1), 0.2–0.3: 0.25→0.60 (5), 0.3–0.4: 0.35→0.29 (7), 0.4–0.5: 0.45→0.64 (11), 0.5–0.6: 0.54→0.70 (10), 0.6–0.7: 0.65→0.41 (27), 0.7–0.8: 0.77→0.55 (64), 0.8–0.9: 0.86→0.72 (216), 0.9–1.0: 0.95→0.90 (359)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.030, 0.1: 1.00/0.030, 0.2: 1.00/0.029, 0.3: 0.99/0.029, 0.4: 0.98/0.029, 0.5: 0.97/0.027, 0.6: 0.95/0.027, 0.7: 0.91/0.025, 0.8: 0.82/0.023, 0.9: 0.51/0.015, 1.0: 0.00/0.000
- Enviado para revisão: 33.6%; abstenção 5.1%; importações silenciosas abaixo do limiar: 0.
- Tempo total 678.92 s, 3.429 s/MP.

## Portões

- ✗ **CER limpo** — 0.0145 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0224 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6538/7241 lances exatos (0.9029), mínimo 0.9980
- ✗ **lances inventados** — 158 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✓ **ordem de leitura em duas colunas** — 1.0000 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `synth:Dvoretsky - Dvoretsky's :201:21` | photo | 0.7857 | tesseract | accepted |
| `table:7` | scan_degraded_150 | 0.6761 | tesseract | review |
| `table:4` | scan_degraded_150 | 0.6400 | tesseract | review |
| `real:Dvoretsky,_Mark_&_Yusupo:17:401:52` | native | 0.5897 | tesseract | review |
| `table:2` | scan_degraded_150 | 0.4650 | tesseract | review |
| `real:Xadrez Vitorioso - Finai:156:266` | shadow_curl_bleed | 0.4255 | rapidocr | accepted |
| `real:Dvoretsky,_Mark_&_Yusupo:20:96:252` | native | 0.4167 | tesseract | accepted |
| `authored:ru:14` | shadow_curl_bleed | 0.3923 | rapidocr | review |
| `real:Dvoretsky,_Mark_&_Yusupo:11:54:52` | native | 0.3810 | tesseract | review |
| `real:Dvoretsky,_Mark_&_Yusupo:11:280:251` | native | 0.3636 | tesseract | review |
