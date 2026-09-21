# Corpus Dourado e Material de Referência

> **Data:** 2026-09-07 · **revisto em 2026-09-11** (§0 e §2, ver `F5_REPORT_C2.md`)
> Este documento define **o que conta como medição válida** em Caïssa Studio.
> Números medidos fora deste corpus não valem para nenhum portão do roadmap.

---

## 0. Onde está

```
C:\Python-Chess2\ChessVisionOFF_Puro\PDF\          46 arquivos, ~800 MB
C:\Python-Chess2\ChessVisionOFF_Puro\pgn_database\ 6 arquivos (LumbrasGigaBase completa)
C:\Python-Chess2\ChessVisionOFF_Puro\data\         labels.csv, splits.csv, field_set.jsonl
```

Este acervo é material protegido por direito autoral. **Não sai desta máquina, não é
enviado a nenhum serviço, não entra em repositório.** Todas as medições são locais.

> **Contagem corrigida em 2026-09-11.** Este documento dizia «50 arquivos»; a varredura
> de `benchmarks/notation_integrity.py --what sweep` conta **46**. Ou quatro saíram desde
> 2026-09-07, ou o número sempre foi aproximado. Quem reportar «n de 50» está errando o
> denominador. Dos 46, **13 não têm camada de texto** com lances — são PDF de imagem.

---

## 1. Por que este acervo é bom

Não é uma coleção conveniente — é adversarialmente diversa, e isso é o que a torna útil:

- **155 anos de tipografia:** de Neumann (1870, tipografia móvel, francês) a Dvoretsky
  (2025, produção digital moderna).
- **Sete idiomas com notações diferentes:** inglês, português, espanhol, alemão,
  neerlandês, francês, romeno e russo (cirílico).
- **Escala de 1,8 MB a 143 MB** — inclui o caso patológico de 143 MB.
- **Variantes do mesmo livro em qualidades diferentes** (`_hq`, `_OCR`, `_Aprimorar`),
  o que permite medir sensibilidade à qualidade da fonte com o conteúdo controlado.
- **Editoras de referência presentes:** Quality Chess, Gambit, Batsford, Everyman.

---

## 2. Estratos de medição

Cada estrato tem um propósito de teste distinto. Um número reportado deve sempre dizer
**em qual estrato** foi medido.

### E1 — Produção digital moderna (o caso fácil, tolerância zero)
| Arquivo | Nota |
|---|---|
| `Mauricio Flores Rios - Chess Structures - A Grandmaster Guide[Quality Chess, 2015].pdf` | **Também é a REFERÊNCIA VISUAL** (§4) |
| `Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf` | |
| `AAGAARD - Practical Chess Defence.pdf` | **NÃO é nativo** — ver aviso abaixo |
| `A Matter of Endgame Technique – Jacob Aagaard.pdf` | **NÃO é nativo** — ver aviso abaixo |
| `📚Burgess G. The Gambit Book of Instructive.pdf` | Gambit. **NÃO é nativo** — ver aviso abaixo |

Aqui não há desculpa. Meta: **100 % de recall de detecção, 100 % de FEN exato.**

> ### ⚠ «E1» não implica «camada de texto boa»
>
> Este estrato classifica o livro pela **época e pela qualidade visual**, não pela camada
> de texto. **Quatro destes cinco falham no nível 0**, de dois jeitos diferentes:
>
> | arquivo | o que a camada de texto realmente é |
> |---|---|
> | `Flores Rios` | **não tem camada nenhuma** (`char_total = 0`): é PDF de imagem |
> | `AAGAARD - Practical Chess Defence` | digitalização re-OCR'd; toda fonte é um subconjunto sintetizado `Fd######-Identity-H` e **os figurinos não sobreviveram** — `♘xe5` volta como `ll'lxe5`. Mediana **0,295** de lances danificados, máximo 0,648 |
> | `📚Burgess G. The Gambit Book` | idem, mediana **0,336**, máximo 0,545 |
> | `A Matter of Endgame Technique` | idem, mediana 0,064 mas **máximo 0,489** — o livro alterna trechos intactos com trechos destruídos |
>
> **O único controle de camada de texto verdadeiramente limpo do acervo é o
> `Dvoretsky (2025)`**: 0,000 de lances danificados, em 59 páginas amostradas, com
> máximo **0,000** — nem uma exceção. Se você precisa de um E1 nativo para calibrar
> alguma coisa, é esse, e só esse.
>
> Números de `benchmarks/notation_integrity.py --what sweep`. A mediana muda um pouco
> com o tamanho da amostra (`--cap`); o que **não** muda é quais livros estão em qual
> lado. Ver `docs/quality/F5_REPORT_C2.md` §2.4 e §4.

### E2 — Digitalização limpa
`Karpov A - Chess Combinations 1 e 2 (2011)`, `Simple Chess - Stean`,
`📚Silman J. The Complete Book of Chess Strategy`, `📚Nunn J. Secrets of Pawnless Endings`,
`📚Nunn J. Secrets of Minor Piece Endings`, `Polgar 5334`.

> **«Digitalização limpa» também é sobre a imagem, não sobre a camada de texto.** Quatro
> destes seis carregam notação danificada na camada — `Nunn Minor Piece` 0,312,
> `Polgar 5334` 0,238, `Nunn Pawnless` 0,216, `Karpov 1` 0,110 — e `Simple Chess`,
> `Silman` e `Karpov 2` não têm camada de texto com lances.
> **Nenhum livro deste estrato serve de controle limpo para o nível 0.**
> Mesma fonte de números: `benchmarks/notation_integrity.py --what sweep`.

### E3 — Digitalização ruidosa / histórica
`1937 Kemeri.pdf` (143 MB — o caso patológico), `Kmoch - Zandvoort 1936 (1936)`,
`Mieses - Blind Schaken (1938)`, `Euwe, Kramer - Das Mittelspiel Band 1-2 (1956)` e
`Band 7 (1958)`, `Gunderam (1961)`, `Levenfis (1962)`, `Neumann (1870)`.

O `Euwe Band 1-2` já é conhecido como o pior caso do acervo — a medição registrada em
`detection/hybrid.py` dá acurácia de **0,010 a 0,025**. Ele é o teto de dificuldade.

### E4 — Fonte de xadrez / vetorial (o alvo da frente F3-A)
O levantamento registrado em `detection/__init__.py` diz que **2 dos 27 livros
amostrados** são "diagrama vetorial/fonte", sem imagem embutida — e nenhuma via atual os
lê. Identificar quais são é a primeira tarefa de F3-A. Suspeitos por época e origem:
`Mauricio Flores Rios (Quality Chess)`, `Dvoretsky (2025)`, `AAGAARD`.

Meta neste estrato: **100 % exato**, porque a posição está literalmente no arquivo.

### E5 — Composição / problemas
`1000 Chess Problems - Yakov Vladimirov 2015`,
`Niemeijer - Zwarte Magie (1945)`, `mate_em_dois.pgn`, `chess_problems_46_119.pgn`.

Estrato especial: posições de problema **violam** heurísticas normais (podem ter três
damas, podem não ter rei de um lado em certos gêneros). O solucionador de restrições da
SPEC §6.4 precisa saber distinguir. `Niemeijer` é onde o classificador local desaba
(confiança mínima média 0,25) e onde a segunda opinião neural ganha 12/20 → 18/20.

### E6 — Cirílico e não-latino
`📚Болеславский_И_Избранные_партии.pdf`,
`Журавлев_Н_The_Manual_of_Chess_Combinations_5_2021.pdf`.

Testa: OCR cirílico, notação russa (`Кf3` = cavalo), e o mapeamento de idioma da F6.

### E7 — Português (idioma primário do usuário)
`400 Quebra-cabeças de Estratégia de Xadrez` (+ variante `_hq`),
`Melhores Finais de Capablanca - Irving Chernev pt-br` (+ `_hq`),
`Minhas 60 partidas memoráveis Bobby Fischer pt-br algébrico`,
`1001_Sacrificios_e__Combinações_Vencedores_Fred_Reinfeld_hq`,
`Xadrez Vitorioso - Finais - Yasser Seirawan`.

Notação portuguesa: R=Rei, D=Dama, T=Torre, B=Bispo, C=Cavalo, P=Peão.
**Atenção à armadilha:** `B` é Bispo em português e *Bishop* em inglês — coincidem.
Mas `R` é Rei em português e *Rook* em inglês — **colidem com significados opostos**.
Esse é o caso de teste mais importante da frente F6.

### E8 — Pares de qualidade controlada
Mesmo conteúdo, qualidades diferentes. Mede sensibilidade sem confundir com conteúdo:

| Par | Uso |
|---|---|
| `1001_Winning_Chess_Sacrifices...` (72 MB) vs `..._hq` (36 MB) | compressão |
| `400 Quebra-cabeças...` (33,7 MB) vs `..._Kravtsiv_hq` (14,2 MB) | compressão |
| `Melhores Finais de Capablanca` (7,6 MB) vs `_hq` (9,5 MB) | idem |
| `Gaprindashvili ... _OCR_Aprimorar_Aprimorar.pdf` | já passou por OCR de terceiros |
| `La_Combinacion_En_El_Ajedrez ... _OCR.pdf` | idem |

Os arquivos já OCR'd são importantes: testam se conseguimos **detectar e rejeitar** uma
camada de texto ruim (SPEC §7.1 nível 0) em vez de confiar nela.

---

## 3. Conjunto anotado existente

Já existe verdade de campo em `ChessVisionOFF_Puro\data\`:

| Arquivo | Conteúdo |
|---|---|
| `field_set.jsonl` (25 KB) | **68 páginas anotadas à mão, 115 diagramas** — a medição de campo |
| `labels.csv` (691 KB) | 5.401 tabuleiros rotulados |
| `splits.csv` (205 KB) | divisões estáveis por hash, sem vazamento entre grupos |
| `gallery_human.jsonl` (218 KB) | anotações humanas por diagrama |
| `quarantine.csv` | rótulos rejeitados na auditoria |
| `samples\` | 5.847 PNGs de tabuleiro (~5 GB) |

**Regra:** medições de laboratório usam `splits.csv` (divisão de teste).
Medições de campo usam `field_set.jsonl`. Não misture, e sempre diga qual usou.

O `field_set.jsonl` precisa **crescer** — 115 diagramas é pouco para afirmar 99 % de
recall com intervalo de confiança útil. Meta: 400 diagramas anotados, cobrindo os
estratos E1–E8 proporcionalmente.

---

## 4. Referência para a comparação às cegas

O `CRITIC_CHARTER.md` exige comparação lado a lado sem saber qual amostra é a nossa.
O material de referência sai deste mesmo acervo:

| Frente | Referência | Arquivo |
|---|---|---|
| F7 Tipografia | **Quality Chess** | `Mauricio Flores Rios - Chess Structures...pdf` |
| F7 Tipografia | Gambit | `📚Burgess G. The Gambit Book of Instructive.pdf` |
| F7 Tipografia | Batsford | `Gaprindashvili ... (Bastford, 2005)...pdf` |
| F8 Exportação | O livro de origem | qualquer um, comparado com a nossa reexportação |
| F5 OCR | Camada de texto do próprio livro digital | E1 |

### Procedimento obrigatório para F7 e F8
1. Extraia uma página real do livro de referência como imagem de alta resolução.
2. Produza a nossa página equivalente (mesma posição, mesmo texto, mesmo tamanho).
3. Apresente as duas ao crítico **sem rótulo**, em ordem aleatória.
4. O crítico ordena e justifica **antes** de saber qual é qual.
5. Reprovação automática se ele identificar a nossa por ser pior.

---

## 5. Regras de medição

1. **Mediana de no mínimo 3 execuções.** Uma execução não é medição.
2. **Sempre nomeie o estrato.** "99 % de acurácia" sem estrato não significa nada.
3. **Nunca meça no conjunto de treino.** `splits.csv` existe para isso. E o inverso
   (OCR_UI ciclo 2, C6/C15): **o campo mede, nunca alimenta** — um rótulo tirado de uma
   página do `field_set.jsonl` vai para `test`, nunca para `train` (`training.pin_field_pages`,
   com o aviso no log), e o `field_exact` publica o número **limpo** (páginas sem amostra de
   treino, `field_exact_clean`) ao lado do cheio: a diferença é o viés, medido e não estimado.
4. **Reporte o pior estrato, não só a média.** A média esconde o `Euwe Band 1-2`.
5. **Verifique antes se já foi medido.** `docs/ASSETS.md` §2.14 lista otimizações já
   testadas e rejeitadas (TTA, temperatura calibrada). Não as redescubra.
6. **Números do construtor não valem para o crítico.** O crítico remede.
