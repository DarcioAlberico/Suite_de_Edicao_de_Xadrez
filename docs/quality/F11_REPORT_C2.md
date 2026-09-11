# F11 ciclo 2 — as três tarefas de texto, medidas; e o LLM continua desligado

> **Data:** 2026-09-10 · **Máquina:** a de referência da SPEC §2 (Ryzen 5 8400F, 31,6 GiB,
> RTX 5060 8 GB `sm_120`, driver 591.86, Windows 11 Pro 26200). Disco livre em C: **27,1 GB**
> no início do ciclo, **40 GB** ao final — este ciclo não baixou nem removeu modelo nenhum;
> a folga veio de fora dele.
> **Modelo:** `gemma4:e4b-it-qat` · **Servidor:** Ollama 0.33.3 · `think=false`,
> esquema JSON forçado, `seed` fixo, `num_ctx=4096`.
>
> **Regra deste relatório:** todo número veio de um comando executado nesta máquina hoje.
> A §9 lista o que **não** foi medido e continua sendo a seção mais importante.

---

## 0. Conclusão em uma tela

| Tarefa | Veredito | O número que decide |
|---|---|---|
| `verify_diagram` (ciclo 1) | **NÃO ENTREGUE** (mantido) | especificidade 0,000 — o ciclo 1 continua valendo |
| `extract_stipulation` — **caminho determinístico** | **ENTREGUE, ligado** | abstenção **0,982** na metade retida (era 0,955); revocação 0,750 inalterada; MCC 0,783 |
| `extract_stipulation` — **com o LLM por cima** | **NÃO ENTREGUE** (desligado por padrão) | abstenção cai para **0,892** e a revocação **não sobe**: 12 invenções em vez de 2, por zero acerto a mais |
| `translate_notation_prose` | **ENTREGUE** | **0 lances alterados** em 1.130 tokens de lance, 92 parágrafos, 3 execuções |
| `caption_for_diagram` | **NÃO ENTREGUE como texto automático** — só como sugestão editável | **65 %** das legendas afirmam uma avaliação da posição que o modelo não pode verificar |

**O ciclo 2 acrescenta uma quarta otimização rejeitada por medição** (as três anteriores:
TTA, temperatura calibrada, `verify_diagram`). E acrescenta **uma correção que entrou**:
o casador determinístico inventava estipulação em 10 de 199 legendas sem estipulação; agora
inventa em 2, **sem perder um único positivo**, medido na metade retida do conjunto.

---

## 1. O que este ciclo mediu, e contra o quê

O ciclo 1 deixou explícito que `extract_stipulation`, `caption_for_diagram` e
`translate_notation_prose` **nunca foram medidas**. Este ciclo mede as três contra verdade
de campo construída a partir do acervo, não à mão livre.

### 1.1 O conjunto de legendas — 233 legendas reais, 29 livros, 7 idiomas

`benchmarks/corpus/derived/llm_captions.jsonl`. Cada legenda saiu do acervo pelo **mesmo
código que a pipeline usa**: `chess_diagram_ocr.detection.hybrid.detect_diagrams` acha as
caixas, `pdf_text.contexts_for_page` (`lines_near` → `assign_lines_to_diagrams` →
`context_from_lines`) recorta a faixa de legenda. Um segundo levantamento varreu a camada
de texto inteira de 33 livros atrás de legendas que **imprimem** uma estipulação, porque o
recorte por diagrama sozinho quase não as encontra — ver §1.3.

Três classes, e a distinção é a regra de rotulagem:

| Classe | O que a legenda diz | Rótulo esperado |
|---|---|---|
| **P** — 34 | Declara a tarefa: "Mate en 2", "White to play and win", "Weiß zieht und gewinnt" | `kind` correspondente |
| **S** — 67 | Declara **só o lado**: "Brancas jogam", "White to play", "Juegan las negras" | `kind = unknown` + lado |
| **N** — 132 | Não declara tarefa nenhuma: cabeçalho de partida, "Posição após 23…Txf3", "Stellung nach dem 20. Zuge", número solto, lixo de OCR | `kind = unknown` |

**S e N juntas (199) são o conjunto de abstenção.** É onde se mede a única coisa que decide
se isto é entregável: uma estipulação inventada é pior que nenhuma, porque o usuário não
consegue ver que foi inventada.

| idioma | P | S | N | total |
|---|---:|---:|---:|---:|
| en | 11 | 29 | 57 | 97 |
| pt | 0 | 33 | 24 | 57 |
| es | 9 | 4 | 10 | 23 |
| de | 3 | 0 | 18 | 21 |
| nl | 10 | 0 | 8 | 18 |
| ru | 0 | 0 | 11 | 11 |
| fr | 1 | 1 | 4 | 6 |
| **total** | **34** | **67** | **132** | **233** |

Armadilhas deliberadas, marcadas em `flags`: 10 legendas de lixo de OCR, 10 "posição após o
lance N", 8 diagramas de fonte (`Diagrama 120 !"""""""#…`), 7 armadilhas de ano
(`A.Chéron 1923` — 1923 é ano, **não** é número de diagrama; o rótulo é `número = null`),
10 legendas em notação de problemista neerlandesa (`2±` = mate em 2).

Metade **retida**: `split` estável por SHA-256 da legenda, `dev` (102) e `holdout` (131).
A metade `holdout` não foi olhada enquanto a correção da §4 era escrita.

### 1.2 O conjunto de prosa — 92 parágrafos, 9 livros, 6 idiomas

`benchmarks/corpus/derived/llm_prose.jsonl`. Blocos reais de texto com prosa **e** lances:
pt 24, de 24, en 13, nl 12, ru 12, es 7. **1.130 tokens de lance** pelo regex de mascaramento de produção
(pt 286, de 304, en 245, nl 137, ru 123, es 35), mediana de 22 palavras por parágrafo.

### 1.3 O que o acervo não tem, e é um achado por si só

**Legenda que imprime a estipulação em texto extraível é rara neste acervo.** Os livros de
problemas que a instrução citou não ajudam pela camada de texto:

| Livro | Camada de texto | Diagramas embutidos |
|---|---|---|
| `1000 Chess Problems - Vladimirov` | **0 caractere/página** | 0 |
| `Polgar 5334` | 625 car./pág. — mas as legendas são **só o ordinal** ("525", "1638") | 0 |
| `Niemeijer - Zwarte Magie` | 508 car./pág. — estipulação em notação de problemista (`2±`, `3±`) | 0 |

Uma varredura exaustiva (passo 1 página, 33 livros) atrás de "mate in N", "juegan y ganan",
"zieht und gewinnt", "to play and win" e congêneres devolveu **165 linhas**, das quais
sobraram 34 positivos inequívocos depois da rotulagem. Por isso os positivos são 34 e não
100: **é o que o acervo imprime.** Em `nl` e `ru` não há positivo explícito nenhum em texto
extraível, e o relatório diz isso em vez de fabricar um.

---

## 2. `extract_stipulation` — o veredito

### 2.1 O quadro completo, metade retida (131 legendas)

| braço | abstenção | precisão | revocação | F1 | MCC | `kind` nos positivos do núcleo | latência mediana |
|---|---:|---:|---:|---:|---:|---:|---:|
| **regras, como estavam** | 0,9550 | 0,7500 | 0,7500 | 0,7500 | 0,7050 | 1,000 | ~0 ms |
| **regras, corrigidas (§4)** | **0,9820** | **0,8824** | 0,7500 | **0,8108** | **0,7834** | 1,000 | ~0 ms |
| **regras corrigidas + LLM** | 0,8919 | 0,5556 | 0,7500 | 0,6383 | 0,5707 | 1,000 | 676 ms |

Leia a última linha com atenção. Ligando o LLM por cima do casador corrigido:

- **falsos positivos: 2 → 12.** Dez estipulações inventadas a mais, em 111 legendas que não
  declaram nenhuma.
- **revocação: 0,750 → 0,750.** Nenhum positivo a mais.
- **acurácia de `kind` nos positivos: 1,000 → 1,000.** Nada a ganhar ali.
- **custo: 676 ms por legenda** e 6,04 GiB de VRAM (§7).

O LLM cobra 676 ms e a VRAM inteira para piorar a abstenção em 9 pontos e não acertar nada
a mais. **Não é entregável ligado.** `caissa.llm.pipeline.LLM_ENRICHMENT_DEFAULT` é
`False`, e o valor está documentado com esta medição ao lado.

### 2.2 O braço "só LLM", conjunto completo (233)

Para atribuir o resultado ao modelo e não à combinação, o `bench_llm.py` também roda o
modelo **sozinho** (`allow_rules=False`). Mediana de 3 execuções,
`benchmarks/reports/llm_c2_text_tasks.json`:

| braço | abstenção (199) | precisão | revocação | MCC | nº de diagrama | lado |
|---|---:|---:|---:|---:|---:|---:|
| regras (antes da correção) | 0,9497 | 0,6970 | 0,6765 | 0,6340 | 0,5669 | 0,9630 |
| **só LLM, esquema forçado** | 0,9246 | 0,5946 | 0,6471 | 0,5522 | **0,8408** | **1,0000** |
| só LLM, **sem** esquema | 0,9246 | 0,5946 | 0,6471 | 0,5522 | 0,7643 | 0,6543 |
| regras + LLM (antes da correção) | 0,8844 | 0,5106 | 0,7059 | 0,5193 | 0,7070 | 0,9877 |

### 2.3 O que o modelo inventa, textualmente

As invenções do modelo não são aleatórias — são quase todas em legendas da classe **S**:

```
"78: Brancas jogam ***"   -> win
"87: Brancas jogam ***"   -> win
"As brancas jogam"        -> win
"55 White to play"        -> win
"54 White to play"        -> win
```

É uma leitura *defensável* de um livro de exercícios — "brancas jogam ***" num livro de
táticas quer dizer "ache o ganho". Mas a regra deste projeto é que a legenda vale pelo que
**diz**, e a consequência prática é ruim: o campo `[Stipulation]` do PGN exportado passaria
a afirmar "as brancas ganham" em posições onde o livro não afirmou nada.

### 2.4 Por idioma, conjunto completo

Abstenção (fração das legendas sem estipulação em que o braço se calou):

| idioma | n de abstenção | regras (antes) | só LLM | regras+LLM (antes) | **regras (depois da §4)** |
|---|---:|---:|---:|---:|---:|
| de | 18 | 0,722 | 1,000 | 0,722 | **0,889** |
| en | 86 | 0,988 | 0,895 | 0,895 | **1,000** |
| es | 14 | 1,000 | 1,000 | 1,000 | **1,000** |
| fr | 5 | 0,800 | 0,800 | 0,600 | **1,000** |
| nl | 8 | 0,875 | 1,000 | 0,875 | **1,000** |
| pt | 57 | 0,965 | 0,912 | 0,895 | **1,000** |
| ru | 11 | 1,000 | 1,000 | 1,000 | **1,000** |

Antes da correção o LLM era melhor que as regras em alemão e neerlandês (1,000 contra 0,722
e 0,875) e pior em inglês e português, que sozinhos são 143 das 199 legendas.

**Depois da correção da §4 as regras abstêm-se em 1,000 em seis dos sete idiomas**, e o
alemão sobe de 0,722 para 0,889 — restam ali as duas frases da §4. A vantagem que o LLM
tinha em `de` e `nl` desapareceu; o que resta dele é a desvantagem em `en` e `pt`.

(A coluna "depois" é medida em todo o conjunto, dev e holdout juntos, porque é uma
comparação por idioma e as fatias por idioma da metade retida são pequenas demais para
sustentar um número. Os números de veredito da §2.1 e da §4 são todos da metade retida.)

### 2.5 O número de diagrama: o LLM empata com o que já existe de graça

O braço "só LLM" acerta o ordinal impresso em **0,8471** das 157 legendas em que o ordinal é
inequívoco. Parece bom até a comparação certa ser feita — não contra o regex da F11, mas
contra o extrator que a pipeline **já usa**:

| extrator | acurácia (157) | custo |
|---|---:|---|
| `pdf_text.parse_context` (tronco, já em produção) | 0,8344 | microssegundos |
| `_rules_stipulation._NUMBER_RE` (F11) | 0,5669 | microssegundos |
| `gemma4:e4b-it-qat` | **0,8471** | **690 ms** |

Duas legendas de vantagem em 157, por 690 ms cada. **Não vale.** E o regex da F11 é pior que
o do tronco — motivo pelo qual `caissa.llm.pipeline` prefere o número do tronco ao extraído,
por construção, e não por configuração.

### 2.6 A notação de problemista neerlandesa: ninguém lê

Dos 34 positivos, 10 são legendas do `Niemeijer - Zwarte Magie` que declaram a estipulação
em notação de problemista (`2±` = mate em 2, `3±` = mate em 3):

| braço | acerto nos 10 |
|---|---:|
| regras | 0/10 |
| só LLM | 0/10 |
| regras + LLM | 0/10 |

Excluindo-os, nos **24 positivos do núcleo**:

| braço | revocação | `kind` | lances do mate (n=10) |
|---|---:|---:|---:|
| regras | 0,9583 | 0,9583 | 1,000 |
| só LLM | 0,9167 | 0,9167 | 1,000 |
| regras + LLM | **1,0000** | **1,0000** | 1,000 |

Aqui, e só aqui, o LLM acrescenta: uma legenda em 24. Contra dez invenções em 111. A troca
é ruim e é essa troca que decide.

---

## 3. O esquema JSON forçado: o que ele conserta, e o que não conserta

`GenerationRequest.json_schema` existia e **nunca era preenchido** — `guarded_json_call`
montava a requisição sem ele. O ciclo 2 deriva o esquema do mesmo mapa de `FieldSpec` que o
validador já usa (`guardrails.json_schema_for`) e o envia em `format`.

A/B nas mesmas 233 legendas, mesmo modelo, mesma semente:

| campo | sem esquema | com esquema |
|---|---:|---:|
| `kind` (abstenção / precisão / revocação) | 0,9246 / 0,5946 / 0,6471 | **igual** |
| **`diagram_number`** | 0,7643 | **0,8408** |
| **`side_to_move`** | 0,6543 | **1,0000** |

O esquema **não** muda o julgamento — o modelo classifica igual. Ele conserta os campos
**estruturados**: o lado a jogar sai de 65 % para 100 %, o número de 76 % para 84 %. Sem
gramática o modelo escreve "white" onde o esquema pede `"w"`, e o validador rejeita o campo.

**A gramática restringe a forma, não a verdade.** Continua havendo validação de esquema,
validação de domínio e a política de confiança depois dela — `test_json_schema.py` fixa
isso com uma resposta que satisfaz a forma e viola o intervalo, e que continua sendo
rejeitada.

---

## 4. A correção que entrou: prova forte contra prova fraca

Medir o casador determinístico contra 233 legendas reais mostrou que **ele também inventa**:
10 estipulações em 199 legendas que não declaram nenhuma. Os mecanismos, todos visíveis no
texto:

| # | idioma | disse | o que disparou |
|---|---|---|---|
| 1, 4, 5 | en, de, de | `mate/1` | `\b(?:#|M)\s?[1-9]\b` casando `m 1` em lixo de OCR |
| 2, 10 | nl, pt | `draw` | uma palavra de resultado solta em prosa corrida |
| 3 | de | `mate/7` | idem, dentro de uma variante |
| 6 | pt | `win` | "…23 h6 **vence**." no fim de uma linha de análise |
| 7, 8 | de | `draw`, `win` | "Stellung nach dem N. Zuge" + comentário com "Remis"/"gewinnt" |
| 9 | fr | `mate/2` | "…pour faire **mat**. … **2**) s'il ne reste…" — a janela de 24 caracteres do `_MATE_RE` atravessava o ponto final |

A correção separa **prova forte** de **prova fraca**:

- **Forte** — lida onde quer que apareça: a palavra de mate seguida *de perto* pelo número
  (janela reduzida de 24 para 12 caracteres, e agora barrando `.` `;` `:` `!` `?` `(` `)`),
  e a nova `_SIDE_RESULT_RE`, que exige **lado e resultado na mesma oração**
  ("las blancas ganan", "Weiß zieht und gewinnt", "White to play and win").
- **Fraca** — uma palavra que *pode* ser resultado, ou um `M` maiúsculo perto de um dígito:
  só é lida de algo com **forma de legenda** (≤ 90 caracteres e ≤ 3 tokens de lance).

O resultado, na metade **retida**, que não foi olhada enquanto a regra era escrita:

| | antes | depois |
|---|---:|---:|
| invenções (falsos positivos em 111) | 5 | **2** |
| abstenção | 0,9550 | **0,9820** |
| precisão | 0,7500 | **0,8824** |
| **revocação** | 0,7500 | **0,7500 — inalterada** |
| F1 | 0,7500 | **0,8108** |
| MCC | 0,7050 | **0,7834** |
| `kind` nos positivos do núcleo | 1,000 | 1,000 |

Na metade `dev`: invenções 5 → **0**, abstenção 0,9432 → **1,0000**, revocação inalterada.

**Nenhum positivo foi perdido em nenhuma das duas metades.** As duas invenções restantes são
comentário alemão que imprime lado e resultado dentro de uma oração subordinada
("würde Schwarz … das Remis erzwingen", "wegen L : h2f und Schwarz gewinnt"). Escrever uma regra contra
duas frases seria ajustar o casador ao próprio conjunto de teste; o ciclo parou aqui e
gravou o número. As duas estão fixadas por teste
(`tests/unit/llm/test_rules_guard.py::test_the_two_that_still_fire_are_recorded_rather_than_hidden`)
para que não cresçam sem que alguém veja.

---

## 5. `translate_notation_prose` — entregue

92 parágrafos reais, 6 idiomas, **3 execuções**, tradução para o inglês (ou para o português
quando a origem é inglês). `benchmarks/reports/llm_c2_text_tasks.json`:

| | valor |
|---|---:|
| Parágrafos | 92 |
| Tokens de lance no conjunto | 1.130 |
| **Lances alterados** | **0** |
| Traduzidos com os lances intactos | 91 |
| Devolvidos sem tradução (a sentinela quebrou) | 1 |
| Latência mediana | 1.304 ms |

**Zero é o número exigido e zero é o número medido.** A garantia é literal: cada token
mascarado volta byte a byte, na mesma ordem, verificado por varredura ordenada de substring
na saída.

O único parágrafo devolvido intacto foi rejeitado pela própria barreira, e o log mostra o
motivo, que é exatamente o modo de falha que ela existe para pegar:

```
traducao rejeitada: sentinelas esperadas [0, 1, 2, 3, 4, 5], encontradas [3, 4, 5, 0, 1, 2]
```

O modelo reordenou as sentinelas. A tradução inteira foi descartada e o usuário vê prosa não
traduzida — visível — em vez de notação embaralhada — invisível.

### 5.1 Uma armadilha de medição que vale registrar

A primeira versão desta medição acusou **corrupção** e estava errada. Ela comparava os
tokens de lance da entrada com os da saída por *re-varredura* com `_MASKABLE_RE`, e isso
falha por dois motivos que não são dano:

1. Prosa traduzida **nomeia casas**: "the square g7". `g7` tem forma de lance.
2. Este acervo escreve captura com `×` (U+00D7), que a máscara não cobre. O modelo
   normaliza para `x`, e o `b6` restaurado passa a ficar colado num `a4x` que nunca foi
   mascarado — intacto, mas já não é um token isolado.

A métrica certa é a garantia que a função de fato faz. A errada teria reprovado a tarefa por
fazer o trabalho dela. Fica registrado porque o crítico vai remedir.

---

## 6. `caption_for_diagram` — não entregue como texto automático

40 posições do `field_set.jsonl` (verdade humana), 3 execuções, legenda em pt-BR.

### 6.1 As barreiras que existem, funcionam

| medida | resultado |
|---|---:|
| Legendas com notação de lance | **0 / 40** |
| Legendas com ano ausente do contexto | **0 / 40** |
| Legendas com nome próprio ausente do contexto | 1 / 40 |
| Caiu para a legenda determinística | 2 / 40 |
| Comprimento mediano | 63 caracteres |
| Latência mediana | 308 ms |

### 6.2 E ainda assim as legendas não podem ser aplicadas sozinhas

Ler as legendas mostra um modo de falha que essas medidas não pegam. Contado sobre as
mesmas 40 posições, **idêntico nas 3 execuções**:

| medida | resultado |
|---|---:|
| **Legendas que afirmam uma avaliação da posição** | **26 / 40 = 0,650** |
| Legendas que afirmam um resultado ausente do contexto | 0 / 40 |

Amostras, com a nota humana ao lado:

```
nota "197, mate em 2"  ->  "O branco tem uma ameaça de mate em dois movimentos."      ok
nota "200, mate em 2"  ->  "O branco tem uma vantagem decisiva nesta posição final."  inventado
nota ""                ->  "O rei branco busca ativamente uma vantagem na posição."   inventado
nota ""                ->  "O cavalo branco ameaça um ataque decisivo contra a
                            estrutura de peões pretos."                               inventado
```

"Vantagem decisiva", "ameaça um ataque decisivo", "posição crítica" são **avaliações da
posição**, e o modelo as escreve a partir de um FEN em texto, sem motor e sem tabuleiro. É a
mesma classe de falha do `verify_diagram` do ciclo 1 — afirmação confiante sobre o conteúdo
de uma posição — só que aqui nada a intercepta.

**Portanto:** `caption_for_diagram` só pode aparecer como **sugestão que o usuário edita
antes de aceitar**, nunca como texto aplicado automaticamente a um livro exportado. A função
já devolve a legenda determinística ("Brancas jogam") quando o modelo não serve, e é essa
que deve ser o padrão.

Qualidade de legenda **não foi medida** e não há métrica objetiva para ela. O relatório diz
isso em vez de inventar um número — ver §9.

---

## 7. VRAM: os dois caminhos exercitados de verdade (ADR-0004)

Não é alocação simulada. O experimento carrega o LLM com `keep_alive="45m"`, dispara o
**mesmo** `bench_batch_throughput.py --workers 6 --device cuda` que a frente de visão usa, e
amostra a placa a cada 2 s enquanto ele roda. Depois despeja o LLM e roda de novo.
`benchmarks/reports/llm_c2_vram.json`.

| medida | MiB | acima do ocioso |
|---|---:|---:|
| Ocioso, nenhum modelo (área de trabalho) | 1.016 | — |
| **LLM residente sozinho** | 7.206 | **6.190** |
| **Visão sozinha, 6 workers CUDA (pico)** | 7.361 | **6.345** |
| LLM + visão (pico observado) | 7.672 | 6.656 |
| Placa | **8.151** | |
| Orçamento da ADR-0004 | 7.168 (7,0 GiB) | |

**6.190 + 6.345 = 12.535 MiB numa placa de 8.151 MiB.** Eles não cabem juntos, e não é
perto: falta 4,4 GB. O "pico observado" de 7.672 MiB não é os dois convivendo — é o que
sobrou depois de a placa resolver o conflito.

### 7.1 O que acontece quando se tenta mesmo assim

O reconhecimento **completou**, e é aí que está o perigo: não há erro, há degradação.

| | com o LLM residente | com o LLM despejado |
|---|---:|---:|
| Vazão | 0,1780 s/diagrama | **0,1522 s/diagrama** |
| Diagramas por segundo | 5,6 | **6,6** |
| FENs idênticos entre execuções | sim | sim |
| Pico VRAM por worker (alocador) | 537,5 MiB | 537,5 MiB |

**17 % mais lento**, sem mensagem nenhuma. E ao fim da execução o campo
`llm_still_resident_after_vision_run` saiu **`false`**: os pesos não estavam mais na placa,
apesar do `keep_alive` de 45 minutos. A causa mais provável é o próprio Ollama descarregando
sob pressão de memória — não foi confirmada instrumentando o servidor, e fica como hipótese.
O fato medido é o que importa: a "convivência" que o número 7.672 sugere **não existiu**, e
a aplicação não foi avisada nem de um lado nem do outro.

### 7.2 A declaração estava otimista, e foi corrigida

Três números já foram afirmados para o E4B. Só o último mede a coisa declarada:

| origem | valor | como |
|---|---:|---|
| ADR-0005 (estimativa) | 3,0–3,5 GiB | nunca medido |
| F11 ciclo 1 | 4.271 MiB | medido contra um ocioso mais cheio (2.488 MiB) |
| **F11 ciclo 2** | **6.190 MiB** | medido contra um ocioso de 1.016 MiB, os dois caminhos exercitados |

`caissa.llm.residency.MEASURED_VRAM_BYTES` passou de 4.271 para **6.190 MiB**, e ganhou
`MEASURED_VISION_VRAM_BYTES = 6.345 MiB` ao lado para que a aritmética "eles cabem?" seja
legível num lugar só.

Com a declaração honesta, o gerenciador da ADR-0004 chega sozinho à conclusão certa: 6.190
MiB contra um teto de 7.168 MiB não deixam espaço para um classificador fixado, e o LLM sai
primeiro porque `LLM_PRIORITY = 100` diz que ele é o primeiro candidato a despejo. Isso está
fixado por teste
(`test_residency.py::test_the_measured_pair_does_not_fit_and_the_budget_says_so`).

### 7.3 A fila, explícita

**Os dois caminhos têm de ser serializados.** Hoje a serialização acontece pela aritmética do
orçamento, que é suficiente e é a que está testada. Torná-la **explícita** — uma fila
nomeada, com espera em vez de despejo — custa uma linha numa frente que esta não é dona:

```python
# src/caissa/vision/classify/residency.py, na ModelSpec do SQUARE_CLASSIFIER
exclusive_group=QUALITY_EXCLUSIVE_GROUP,   # "gpu-exclusive"
```

O `_SerialQueue` do `caissa.vision.runtime.residency` já implementa a fila; o lado do LLM já
sabe declarar o grupo (`llm_model_spec(exclusive_group=...)`). Falta só o outro lado
declarar o mesmo grupo. Este ciclo **não** fez essa edição — o arquivo é de outra frente — e
registra o pedido aqui com a medição que o justifica.

### 7.4 Um achado que não é desta frente

O reconhecimento **sozinho**, a 6 workers CUDA, tem pico de **6.345 MiB acima do ocioso**.
Cabe nos 7,0 GiB da ADR-0004, com 823 MiB de folga — mas o pico de placa é 7.361 de 8.151
MiB, ou seja **790 MiB** de folga real numa máquina que também está desenhando a área de
trabalho. Não é problema desta frente e não foi investigado aqui; fica anotado porque a
medição estava na frente do nariz.

---

## 8. O que foi ligado, e o que ficou desligado

### 8.1 Ligado

**`caissa.llm.pipeline`** — a única costura entre o LLM e a pipeline de reconhecimento.

```python
from caissa.llm import stipulations_for_pdf_page

hints = stipulations_for_pdf_page(pdf, page_index, [c.bbox_pdf for c in candidates])
```

Lê a faixa de legenda pelo `pdf_text.contexts_for_pdf_page` — a **mesma** função que
`caissa.vision.classify.page` usa, então o texto é byte a byte o que o reconhecimento viu —
e devolve um `CaptionEnrichment` por diagrama. Verificado numa página real do
`400 Quebra-cabeças`:

```
p72 : 1 diagrama -> Stipulation(kind='unknown', side_to_move='w', diagram_number=63,
                                confidence=0.55, source='rules',
                                raw='Lichess\n63: Brancas jogam **')
p154: 1 diagrama -> Stipulation(kind='unknown', side_to_move='w', diagram_number=30,
                                source='rules', raw='Lichess\nAs brancas jogam\n30) Mosesov – Y. Vovk')
```

Nada inventado: a legenda declara lado e número, e é o que sai.

As barreiras do ciclo 1, aplicadas aqui e fixadas por teste:

| Regra | Como é cumprida |
|---|---|
| Saída estruturada validada por esquema | `json_schema_for` na ida, `validate_schema` na volta; o que não valida é **rejeitado**, não adivinhado |
| O LLM só pode **baixar** confiança ou **sinalizar** | Conflito com a página impressa corta a confiança pela metade e marca `side_conflict`/`number_conflict`; a página vence sempre |
| O LLM nunca sobrescreve resultado de alta confiança | `DiagramContext` é congelado e devolvido intacto; o enriquecimento fica **ao lado** |
| Toda chamada auditada | JSONL append-only com prompt, saída, latência, decisão e sha256 do prompt |
| A aplicação funciona sem o LLM | 3.346 testes passam com `llm.enabled = false`, que é o padrão |

**`extract_stipulation` determinístico**, com a correção da §4, ligado por padrão.

**`translate_notation_prose`**, com a máscara de lances, entregue como função. Ela é
biblioteca: quem a chama é a frente que edita texto, e essa frente ainda não existe em
`src/caissa/ui/`. O que este ciclo entrega é a garantia medida (§5) e a função pronta —
não uma tela.

**O esquema JSON forçado**, em todas as chamadas (`force_schema=True` por padrão).

### 8.2 Desligado

- `verify_diagram` — ciclo 1, especificidade 0,000.
- O braço LLM de `extract_stipulation` — `LLM_ENRICHMENT_DEFAULT = False`, §2.1.
- `caption_for_diagram` como texto automático — §6.2.

### 8.3 Um defeito encontrado por acidente, e corrigido

`CAISSA_LLM_ENABLED=1` — a variável que o próprio `caissa.llm.runtime` documenta para ligar
o LLM — **fazia `get_config()` levantar**, porque o carregador de configuração recusa nomes
`CAISSA_*` desconhecidos e espera `CAISSA_LLM__ENABLED`. O `AuditLog` tratava isso como
"sem diretório de log" e caía para memória. Resultado: a execução de medição inteira deste
ciclo, com mais de mil chamadas ao modelo, gravou **um** registro em disco.

Uma trilha de auditoria que some exatamente quando o subsistema está em uso é pior que
nenhuma, porque ninguém vai procurar um arquivo que acredita existir. Duas correções:

1. `AuditLog._resolve_path` cai para `caissa.core.config.schema.default_log_dir()` — função
   pura, não lê arquivo, não valida ambiente — antes de desistir.
2. `runtime._configured` aceita **as duas** grafias, `CAISSA_LLM_ENABLED` e
   `CAISSA_LLM__ENABLED`, para que ligar o subsistema não quebre a configuração em volta.

Fixado por `tests/unit/llm/test_audit_path.py`.

---

## 9. O que **não** foi medido

1. **`repair_ocr_region` continua sem medição.** É a quinta tarefa e nada neste ciclo a
   tocou. Não deve ser ligada.
2. **`gemma4:12b-it-q4_K_M` continua sem medição**, como no ciclo 1. A tabela de VRAM do
   coordenador diz 4,9 tok/s contra 15,3 — este ciclo não a refez.
3. **Qualidade de legenda não tem métrica objetiva** e não foi pontuada. A §6 mede apenas
   segurança e uma proxy de invenção; se uma legenda é *boa* para um livro, só um humano
   diz.
4. **Três idiomas não têm positivo explícito medível.** `ru` e `pt` têm **zero** positivos
   no conjunto — a camada de texto dos livros russos e portugueses deste acervo não imprime
   estipulação em palavras; `nl` tem 10, todos em notação de problemista que nenhum braço
   lê (§2.6). Para esses três idiomas, tudo o que a §2.4 mede é abstenção. Uma medição de
   `kind` em `pt`, que é o idioma primário do usuário, **não existe** e é o buraco mais
   incômodo deste relatório.
5. **Os rótulos foram atribuídos por este agente**, lendo cada legenda, não por um segundo
   humano independente. O arquivo está em
   `benchmarks/corpus/derived/llm_captions.jsonl` com a legenda e o rótulo lado a lado
   justamente para que o crítico discorde linha a linha.
6. **Os positivos foram selecionados por léxico.** A varredura da §1.3 só encontra legendas
   que casam com um léxico multilíngue — mais largo e de forma diferente do regex de
   produção, mas ainda um léxico. Uma legenda que declare estipulação em palavras que ele
   não conhece não está no conjunto.
7. **`caption_for_diagram` foi medida só em pt-BR.** Os outros seis idiomas não foram.
8. **A latência de `bench_llm.py` foi medida com a suíte de testes rodando em paralelo** por
   parte da execução. As medianas de §2 e §5 podem estar infladas; os números de acerto não
   dependem de carga. As medianas de §7 (VRAM e vazão) foram medidas com a máquina ociosa.
9. **As legendas do conjunto estão achatadas.** O levantamento juntou as linhas da faixa com
   espaço; em produção `DiagramContext.caption` as junta com `
`. O comprimento total é
   praticamente o mesmo, então o limiar de 90 caracteres da §4 se comporta igual — mas isso
   é raciocínio, não medição. Avaliar a estipulação **linha a linha**, e não sobre a faixa
   inteira, é a melhoria óbvia seguinte e não foi feita.
10. **Por que o LLM deixou de estar residente na §7.1 não foi confirmado.** A hipótese é
    despejo do Ollama sob pressão de memória; instrumentar o servidor confirmaria.

---

## 10. Disco: os 13,7 GB, contra o que é usado

| tag | disco | usado neste ciclo |
|---|---:|---|
| `gemma4:e4b-it-qat` | **6,15 GB** | sim — todas as medições |
| `gemma4:12b-it-q4_K_M` | **7,56 GB** | **não** — nunca foi medido, em nenhum ciclo |
| total da Caïssa | **13,71 GB** | |

O diretório `~/.ollama/models` inteiro tem 45,65 GB; os outros 31,94 GB são modelos do
usuário que não têm relação com este projeto (`qwen3-coder:30b`, `deepseek-r1:8b` e outros).

**Recomendação: remover o `gemma4:12b-it-q4_K_M`.** Recupera **7,56 GB** num disco que caiu
de 76,4 GB para 27,1 GB livres desde o início do projeto. Os argumentos:

- Ele nunca foi medido, em dois ciclos.
- A tabela do coordenador o mede em **4,9 tok/s contra 15,3** do E4B, por 600 MiB a mais de
  VRAM — três vezes mais lento numa placa de 8 GB.
- As três tarefas de texto deste ciclo **não são limitadas por capacidade do modelo**. A que
  falhou (§2) falhou por *inventar*, não por não saber; um modelo maior inventa com mais
  fluência. A que passou (§5) passou com 100 % de margem.
- A tarefa que poderia justificar um modelo maior — `verify_diagram` — é visual, e o ciclo 1
  mostrou que o problema ali não é tamanho.

O E4B **fica**: é o que roda `translate_notation_prose`, que é a tarefa entregue.

A remoção é destrutiva e é chamada do usuário. **Nada foi removido.** O comando é:

```
ollama rm gemma4:12b-it-q4_K_M
```

---

## 11. Reprodutibilidade

```
benchmarks/bench_llm.py --experiments e,f,g --repeats 3 --positions 40
benchmarks/bench_llm.py --experiments h --workers 6 --vision-pages 12

benchmarks/corpus/derived/rules_guard.py     4, as duas metades do casador
benchmarks/corpus/derived/rescore.py         2.5, 2.6
benchmarks/corpus/derived/caption_claims.py  6.2
benchmarks/corpus/derived/prod_after.py      2.1, o braço com LLM depois da correção

benchmarks/corpus/derived/llm_captions.jsonl   233 legendas rotuladas, com split dev/holdout
benchmarks/corpus/derived/llm_prose.jsonl       92 parágrafos anotados
benchmarks/corpus/derived/*.py                  os levantamentos que os construíram

benchmarks/reports/llm_c2_text_tasks.json           E, F, G — 1.581,8 s
benchmarks/reports/llm_c2_rescore.json              positivos com/sem a notação neerlandesa; nº de diagrama
benchmarks/reports/llm_c2_caption_claims.json       a taxa de avaliação inventada da §6.2
benchmarks/reports/llm_c2_rules_before.json         §4, antes
benchmarks/reports/llm_c2_rules_after.json          §4, depois
benchmarks/reports/llm_c2_production_after_fix.json §2.1, o braço com LLM depois da correção
benchmarks/reports/llm_c2_vram.json                 §7
```

Suíte: **3.346 passaram, 1 pulado, 0 falharam** em 720,5 s
(linha de base 3.289 + **57 testes novos** desta frente; os testes da F11 vão de 199 a 256).
Nada do tronco `ChessVisionOFF_Puro` foi editado — só lido.
