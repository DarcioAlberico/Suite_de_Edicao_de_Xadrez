# Sol · benchmark `sol` — c1_sem

> 2026-09-14T10:08:56+00:00 · corpus `43ac7c57017324d8` (2026.09.13) · commit `010b10d` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 61 | 2 | 48 | 0.0582 | 0.0505–0.0660 | 0.2442 | 0.4803 | 435 | 80 | 0/0 | 3.43 |
| native | 237 | 173 | 64 | 67 | 0.0156 | 0.0093–0.0236 | 0.0393 | 0.9046 | 58 | 29 | 0/9 | 1.58 |
| photo | 63 | 62 | 1 | 14 | 0.1157 | 0.0822–0.1537 | 0.1744 | 0.7183 | 238 | 40 | 0/0 | 5.71 |
| scan_clean_300 | 137 | 137 | 0 | 34 | 0.0275 | 0.0113–0.0493 | 0.0519 | 0.9422 | 106 | 23 | 0/0 | 0.91 |
| scan_degraded_150 | 137 | 135 | 2 | 35 | 0.0361 | 0.0198–0.0558 | 0.0827 | 0.8427 | 284 | 77 | 0/0 | 4.34 |
| shadow_curl_bleed | 101 | 101 | 0 | 42 | 0.0303 | 0.0240–0.0372 | 0.1154 | 0.8615 | 146 | 42 | 0/0 | 5.05 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0496 | 0.0979 | 0.7929 | 11 | 1.0000 |
| en | 377 | 313 | 0.0322 | 0.0865 | 0.8342 | 198 | 1.0000 |
| es | 34 | 34 | 0.0590 | 0.1079 | 0.7865 | 11 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.9107 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0363 | 0.0848 | 0.8249 | 60 | 1.0000 |
| ru | 21 | 16 | 0.0683 | 0.3043 | 0.4052 | 10 | 1.0000 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 11 | 0.0739 | 0.3186 | 0.3906 | 8 | — |
| latin | 723 | 658 | 0.0369 | 0.0896 | 0.8225 | 283 | 1.0000 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0146 | 0.0649 | 0.8750 | 1 | 1.0000 |
| single | 666 | 598 | 0.0308 | 0.0869 | 0.8013 | 251 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |
| two-column | 52 | 51 | 0.0934 | 0.1505 | 0.8796 | 39 | 1.0000 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 262 | 0.0381 | 0.0872 | 0.8596 | 72 | 1.0000 |
| movetext | 339 | 323 | 0.0404 | 0.1119 | 0.7986 | 218 | — |
| problems | 8 | 8 | 0.0146 | 0.0649 | 0.8750 | 1 | 1.0000 |
| prose | 71 | 64 | 0.0022 | 0.0106 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 222 | 0.0296 | 0.0793 | 0.8174 | 81 | 1.0000 |
| dev | 498 | 447 | 0.0415 | 0.1003 | 0.8191 | 210 | 1.0000 |

## Calibração e abstenção

- ECE 0.1702, Brier 0.2079 em 669 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.5–0.6: 0.55→0.19 (26), 0.6–0.7: 0.66→0.22 (41), 0.7–0.8: 0.76→0.40 (127), 0.8–0.9: 0.85→0.73 (223), 0.9–1.0: 0.95→0.89 (252)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.038, 0.1: 1.00/0.038, 0.2: 1.00/0.038, 0.3: 1.00/0.038, 0.4: 1.00/0.038, 0.5: 1.00/0.038, 0.6: 0.96/0.035, 0.7: 0.90/0.034, 0.8: 0.71/0.031, 0.9: 0.38/0.029, 1.0: 0.00/0.000
- Enviado para revisão: 32.5%; abstenção 9.3%; importações silenciosas abaixo do limiar: 0.
- Tempo total 463.11 s, 2.339 s/MP.

## Portões

- ✗ **CER limpo** — 0.0215 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0361 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 5717/6984 lances exatos (0.8186), mínimo 0.9980
- ✗ **lances inventados** — 291 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✓ **ordem de leitura em duas colunas** — 1.0000 de ordem correta nos itens com mais de uma região
- ✓ **reprodução do ambiente** — ambiente, versões e hashes registrados

**Resultado:** bloqueado

## Dez piores itens

| item | estrato | CER | motor | decisão |
|---|---|--:|---|---|
| `synth:Dvoretsky - Dvoretsky's :201:21` | photo | 0.6964 | tesseract | accepted |
| `twocol:d:9` | scan_clean_300 | 0.6878 | tesseract | accepted |
| `table:7` | scan_degraded_150 | 0.6761 | tesseract | review |
| `table:4` | scan_degraded_150 | 0.6400 | tesseract | review |
| `twocol:d:4` | scan_clean_300 | 0.6222 | tesseract | accepted |
| `twocol:d:17` | scan_degraded_150 | 0.6110 | tesseract | accepted |
| `twocol:a:5` | scan_clean_300 | 0.6076 | tesseract | accepted |
| `twocol:a:4` | scan_clean_300 | 0.5615 | tesseract | accepted |
| `authored:de:4` | photo | 0.5312 | tesseract | accepted |
| `twocol:d:18` | scan_clean_300 | 0.4948 | tesseract | accepted |
