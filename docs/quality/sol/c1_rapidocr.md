# Sol · benchmark `sol` — c1_rapidocr

> 2026-09-14T10:46:34+00:00 · corpus `43ac7c57017324d8` (2026.09.13) · commit `010b10d` · Tesseract tesseract v5.5.0.20241111 · cego excluído

## Resumo por estrato

| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances | perdidos | inventados | ctrl FP | s/MP |
|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| fax_dither | 63 | 63 | 0 | 9 | 0.0318 | 0.0211–0.0441 | 0.1064 | 0.8236 | 151 | 27 | 0/0 | 5.05 |
| native | 237 | 175 | 62 | 68 | 0.0151 | 0.0096–0.0226 | 0.0390 | 0.9067 | 57 | 26 | 0/9 | 2.10 |
| photo | 63 | 63 | 0 | 5 | 0.1115 | 0.0783–0.1460 | 0.1663 | 0.8224 | 152 | 24 | 0/0 | 7.72 |
| scan_clean_300 | 137 | 137 | 0 | 28 | 0.0281 | 0.0122–0.0497 | 0.0509 | 0.9488 | 94 | 21 | 0/0 | 1.12 |
| scan_degraded_150 | 137 | 137 | 0 | 22 | 0.0342 | 0.0185–0.0544 | 0.0766 | 0.8730 | 233 | 63 | 0/0 | 5.83 |
| shadow_curl_bleed | 101 | 101 | 0 | 9 | 0.0386 | 0.0255–0.0529 | 0.0930 | 0.9345 | 69 | 8 | 0/0 | 5.72 |

## Por prose_lang

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| — | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| de | 25 | 25 | 0.0499 | 0.0861 | 0.8250 | 7 | 1.0000 |
| en | 377 | 315 | 0.0246 | 0.0545 | 0.9300 | 91 | 1.0000 |
| es | 34 | 34 | 0.0560 | 0.0983 | 0.8539 | 8 | 1.0000 |
| mixed | 2 | 2 | 0.2850 | 0.3774 | 0.9107 | 1 | 1.0000 |
| pt | 279 | 279 | 0.0386 | 0.0768 | 0.8760 | 49 | 1.0000 |
| ru | 21 | 21 | 0.0888 | 0.2873 | 0.4930 | 13 | 0.9167 |

## Por script

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| cyrillic | 15 | 15 | 0.0972 | 0.2982 | 0.5048 | 12 | — |
| latin | 723 | 661 | 0.0343 | 0.0702 | 0.8986 | 157 | 0.9917 |

## Por layout

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| none | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| single | 666 | 604 | 0.0288 | 0.0673 | 0.8897 | 137 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |
| two-column | 52 | 52 | 0.0926 | 0.1441 | 0.9003 | 32 | 0.9904 |

## Por genre

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| control | 0 | 0 | 0.0000 | 0.0000 | 1.0000 | 0 | — |
| mixed | 308 | 265 | 0.0393 | 0.0838 | 0.8819 | 63 | 0.9904 |
| movetext | 339 | 327 | 0.0357 | 0.0774 | 0.8968 | 106 | — |
| problems | 8 | 8 | 0.0085 | 0.0536 | 1.0000 | 0 | 1.0000 |
| prose | 71 | 64 | 0.0022 | 0.0106 | 1.0000 | 0 | — |
| table | 12 | 12 | 0.1520 | 0.1890 | 1.0000 | 0 | — |

## Por partition

| valor | n | resp. | CER médio | WER | lances | inventados | ordem |
|---|--:|--:|--:|--:|--:|--:|--:|
| calib | 240 | 226 | 0.0289 | 0.0678 | 0.8807 | 56 | 1.0000 |
| dev | 498 | 450 | 0.0391 | 0.0790 | 0.8975 | 113 | 0.9904 |

## Calibração e abstenção

- ECE 0.1386, Brier 0.1860 em 676 respostas (acerto = CER ≤ 2 %).
- Confiabilidade por faixa (confiança → acerto, n): 0.5–0.6: 0.55→0.31 (16), 0.6–0.7: 0.65→0.30 (27), 0.7–0.8: 0.77→0.47 (60), 0.8–0.9: 0.86→0.71 (217), 0.9–1.0: 0.95→0.86 (356)
- Risco × cobertura (limiar: cobertura / CER): 0.0: 1.00/0.036, 0.1: 1.00/0.036, 0.2: 1.00/0.036, 0.3: 1.00/0.036, 0.4: 1.00/0.036, 0.5: 1.00/0.036, 0.6: 0.98/0.035, 0.7: 0.94/0.034, 0.8: 0.85/0.031, 0.9: 0.53/0.025, 1.0: 0.00/0.000
- Enviado para revisão: 19.1%; abstenção 8.4%; importações silenciosas abaixo do limiar: 0.
- Tempo total 595.5 s, 3.0076 s/MP.

## Portões

- ✗ **CER limpo** — 0.0216 em 2 estrato(s) limpo(s), limite 0.0050
- ✗ **CER 150 DPI** — 0.0342 em 1 estrato(s) a 150 DPI, limite 0.0200
- ✗ **acurácia de lances** — 6291/7047 lances exatos (0.8927), mínimo 0.9980
- ✗ **lances inventados** — 169 token(s) de lance sem correspondência na verdade
- ✓ **importação silenciosa abaixo do limiar** — 0 região(ões) aceitas abaixo do limiar sem revisão
- ✓ **controles negativos** — 0 de 9 controle(s) sem texto produziram conteúdo
- ✗ **ordem de leitura em duas colunas** — 0.9917 de ordem correta nos itens com mais de uma região
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
