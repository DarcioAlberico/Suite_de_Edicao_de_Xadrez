# Procedência dos 12 PNG de peça — o que foi apurado, e como

> **Data:** 2026-09-09 · **Frente:** F12 (empacotamento), ciclo 2.
> Todo número abaixo veio de um comando executado nesta máquina. Onde não houve medição,
> está escrito que não houve.

O ciclo 1 desta frente registrou `assets/piece_images/` como *"a única lacuna assumida"*:
12 PNG que entram no bundle **sem arquivo de procedência**, com a hipótese — escrita no
código do tronco, não em nenhum documento — de que são *"os PNGs do próprio tronco"*.

Este arquivo investiga essa hipótese. **Ela não se sustenta.**

---

## 1. O que os arquivos são, medido

`ChessVisionOFF_Puro/assets/piece_images/`, 12 arquivos, 12.072 bytes somados:

```
70x70, profundidade 8, tipo de cor 3 (paleta) + tRNS
chunks: IHDR PLTE tRNS gAMA sRGB IDAT IEND
```

**Nenhum chunk de texto.** Não há `tEXt`, `iTXt` nem `zTXt` — isto é, nenhum campo
`Author`, `Software`, `Copyright` ou `Comment`. Os arquivos não dizem nada sobre si mesmos.

## 2. O que o histórico do tronco diz

```
> git log --follow --diff-filter=A -- assets/piece_images/
297b37f Commit inicial: pipeline de OCR de diagramas de xadrez
> git log --oneline -- assets/piece_images/
297b37f   (um commit, e só)
```

`297b37f` é de **2026-07-25**, autor `DarcioAlberico`, e é o commit inicial do repositório.
A mensagem lista o que entrou e termina com *"Dados não versionados por tamanho ou direito
autoral"* — os PNG **não** estão nessa ressalva. A data de modificação dos arquivos em
disco é **2025-04-17**, quinze meses antes do commit: eles são anteriores ao repositório.

O histórico, portanto, não registra origem: registra apenas que chegaram prontos.

Nenhum README, `LICENSE`, `NOTICE` ou `PROCEDENCIA.md` acompanha a pasta. O repositório tem
`assets/lexico/PROCEDENCIA.md` e `src/chess_diagram_ocr/text/PROCEDENCIA.md` — a disciplina
existe no projeto; ela simplesmente não foi aplicada a esta pasta.

## 3. A comparação que decide

Ao lado do tronco, nesta máquina, está o clone de `tsoj/Chess_diagram_to_FEN` — o mesmo
repositório que a `caissa.spec` cita como origem de `scipy`/`skimage` no ambiente. Ele traz
**1.034 PNG de peça** organizados em 46 conjuntos completos, e um `resources/COPYING.md`
que documenta a licença de cada um.

Comparação das 12 peças do tronco contra os 46 conjuntos, todos reescalados para 70×70,
por IoU da silhueta (canal alfa binarizado em 0,5):

| conjunto | IoU médio das 12 peças |
|---|---:|
| **`extra/classic`** | **0,9808** |
| `extra/bases` | 0,8909 |
| `extra/icy_sea` | 0,8823 |
| `extra/wood` | 0,8818 |
| … | … |
| `extra/falcon` (pior) | 0,5495 |

O primeiro colocado está **0,09 acima** do segundo. Refazendo a comparação só contra
`extra/classic`, peça a peça, e medindo também a cor (RMSE em RGB sobre a área comum):

| peça | IoU | RMSE RGB |
|---|---:|---:|
| bb | 0,9721 | 9,32 |
| bk | 0,9797 | 13,97 |
| bn | 0,9900 | 10,19 |
| **bp** | 0,9840 | **0,00** |
| bq | 0,9693 | 9,54 |
| br | 0,9880 | 12,69 |
| wb | 0,9744 | 14,58 |
| wk | 0,9830 | 13,98 |
| wn | 0,9886 | 12,43 |
| wp | 0,9840 | 11,15 |
| wq | 0,9704 | 15,95 |
| wr | 0,9921 | 16,45 |
| **média** | **0,9813** | **11,69** |

O peão preto tem **RMSE 0,00**: as cores são idênticas, byte a byte, depois do reescalamento.
As demais diferenças de cor (média 11,7 em 255) são o que uma redução de 150×150 para 70×70
com reamostragem produz nas bordas antisserrilhadas.

**Nenhum arquivo é idêntico por SHA-256** — o que é esperado: os do tronco são 70×70 e os do
`classic` são 150×150. A igualdade é da *arte*, não do arquivo.

## 4. O que `resources/COPYING.md` diz sobre `extra/classic`

Citado literalmente do arquivo, linhas 16–23:

```
## Chess.com

**License:** All rights reserved. No open-source license provided.

**Piece sets** (`pieces/chess/extra/`):
8_bit, bases, book, bubblegum, cases, classic, club, condal, dash, game_room,
glass, gothic, graffiti, icy_sea, light, lolz, marble, maya, metal, modern, nature, neo,
neo_wood, neon, newspaper, ocean, sky, space, tigers, tournament, vintage, wood
```

`classic` está nessa lista.

## 5. O que fica estabelecido, e o que não fica

**Estabelecido:**

1. Os 12 PNG do tronco são a **mesma arte** do conjunto que um documento de atribuição de
   terceiro identifica como da **Chess.com**, cuja licença ele descreve como *"All rights
   reserved. No open-source license provided."*
2. Os arquivos não trazem metadado de autoria, e o histórico do tronco não registra origem.
3. A hipótese registrada no código do tronco — *"os PNGs do próprio tronco"* — **é falsa**:
   arte com IoU 0,98 e um canal de cor idêntico não é desenho independente.

**Não estabelecido, e é importante dizer:**

1. **Não se provou o caminho de cópia.** Não há evidência de que os arquivos vieram *deste*
   clone do `tsoj/Chess_diagram_to_FEN`. Podem ter vindo do site, de um tema de terceiro que
   redistribui a mesma arte, ou de qualquer outro lugar. O que a medição estabelece é a
   identidade da arte, não a rota.
2. **Não se conferiu a afirmação do `COPYING.md` na fonte.** Ele é o documento de atribuição
   de um repositório MIT de terceiro (Jost Triller, 2024); não é a licença publicada pela
   Chess.com. É o melhor registro disponível offline, e é registro, não decisão judicial.
3. **Não houve consulta jurídica.** Este arquivo não é parecer.

## 6. A decisão desta frente

A mesma que o projeto já tomou para os dois léxicos de procedência não apurada, e pelo mesmo
motivo — **distribuir é o ato que cria a responsabilidade**:

- **Os 12 PNG do tronco saem do bundle.** Não estão em `datas` da `packaging/caissa.spec`.
- Entram em `packaging/manifesto.json` como componente `pecas-do-tronco`, marcado
  `"consentimento": true`. O assistente de primeira execução só os instala com
  `--aceitar-licenca-nao-apurada`, e diz por escrito o que apurou antes de perguntar.
- **No lugar deles o bundle leva o conjunto `cburnett`**, que tem licença explícita e
  compatível (ver `licenses/PECAS_CBURNETT.md`). O tabuleiro continua sendo desenhado; o que
  muda é que agora existe uma linha de licença por trás dele.

Diferente dos léxicos, aqui **o custo da exclusão não é zero**: a arte muda de aparência.
O que não muda é a função — `assets/piece_images/` continua com 12 PNG de 70×70 com os
mesmos nomes, e `docs/quality/F12_REPORT_C2.md` publica a medição do auto-teste rodando com
o conjunto substituto.

**O que o dono do projeto precisa decidir**, e que esta frente não pode decidir por ele:
se a arte original é para ser recuperada (com licença), substituída de vez, ou mantida sob
consentimento explícito para uso próprio.
