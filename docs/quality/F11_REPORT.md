# F11 — LLM local (Gemma 4): resultado negativo

> **Data:** 2026-09-07 · **Veredito: o LLM NÃO deve ser usado para verificar diagramas.**
>
> Este relatório foi escrito pelo coordenador a partir dos artefatos de medição deixados
> em `benchmarks/reports/`, porque o agente construtor foi interrompido por limite de
> sessão antes de redigi-lo. Todo número aqui vem de um JSON gravado por aquela execução,
> citado pelo nome do arquivo. Nada foi estimado.

---

## 0. Conclusão em uma tela

**Gemma 4 E4B não tem poder discriminativo nenhum na tarefa de verificar se um FEN
corresponde a um diagrama.** Medido com verdade de campo, em 100 pares:

| | valor | leitura |
|---|---|---|
| Verdadeiros positivos | 50 | disse "consistente" nos 50 pares corretos |
| **Falsos positivos** | **50** | **disse "consistente" nos 50 pares deliberadamente errados** |
| Verdadeiros negativos | **0** | **não rejeitou nenhum par errado** |
| Falsos negativos | 0 | — |
| Precisão | 0,500 | = a taxa de acerto de uma moeda |
| Revocação | 1,000 | trivial: ele diz "sim" para tudo |
| **Especificidade** | **0,000** | **o número que condena** |
| **MCC** | **0,000** | **correlação zero com a verdade** |
| Acurácia balanceada | 0,500 | exatamente o acaso |
| Latência mediana | **1.016 ms** | um segundo por chamada, para não informar nada |

Fonte: `benchmarks/reports/llm_main.json`, experimento `A_fen_discrimination`,
50 pares, modelo `gemma4:e4b-it-qat`, servidor `ollama 0.33.2`.

Um classificador que responde "sim" a 100 % das entradas tem revocação perfeita e valor
nulo. É precisamente o modo de falha que a instrução do agente antecipou: **um LLM que
inventa confiança é pior que nenhum LLM, porque converte uma resposta errada em uma
resposta confiante.**

---

## 1. O segundo experimento confirma pelo lado oposto

`B_review_queue` rodou sobre a fila de revisão real
(`ChessVisionOFF_Puro/data/review_queue.json`), onde **não há verdade de campo**. O
próprio agente registrou a ressalva no JSON:

> "review_queue.json nao tem verdade de campo: estes numeros descrevem o que o modelo
> disse, nao se ele acertou."

O que ele disse:

| veredito | itens |
|---|---|
| `inconsistent` | 26 |
| `uncertain` | 1 |

E `llm_confidence: 0.95` em **todos os 26**.

Junte os dois experimentos: no A ele afirmou "consistente" em 100 % dos casos; no B
afirmou "inconsistente" em 96 % dos casos. Sempre com confiança alta. O veredito muda
conforme o formato do prompt, não conforme a imagem. Isso não é um detector ruidoso — é
um gerador de texto plausível sem acesso ao conteúdo.

### O único sinal com algum valor
`suspect_square_hit_rate = 0.34` (50 itens pontuados). Quando perguntado *qual* casa está
errada, ele acerta cerca de um terço das vezes. Está acima do acaso, mas muito abaixo do
que justifique 1 segundo de latência e 6,1 GB de pesos — e é inútil se o veredito de
"há erro" que o precede não vale nada.

---

## 2. O que foi realmente instalado

A ADR-0005 previu **~3,0–3,5 GB** para o E4B em Q4_K_M. **A previsão estava errada.**

| tag | tamanho em disco | observação |
|---|---|---|
| `gemma4:e4b-it-qat` | **6,1 GB** | a variante QAT é bem maior que a estimativa da ADR |
| `gemma4:12b-it-q4_K_M` | **7,6 GB** | segundo nível, puxado para testar o "modo qualidade" |

Total acrescentado: **13,7 GB**. Disco livre em C: caiu para **54,2 GB**.

O agente anunciou explicitamente que o segundo nível excedia o padrão de "um nível só"
antes de puxá-lo — comportamento correto —, mas foi interrompido antes de medir o 12B.
**Portanto não há evidência de que o 12B resolva o problema.** Não presuma que resolve.

---

## 3. O que isto significa para o produto

### 3.1 Desligar `verify_diagram`
A função existe no código e **não deve ser ligada por padrão**. Um veredito com
especificidade 0,0 alimentando o painel de revisão faria o usuário desconfiar de leituras
corretas e perder tempo conferindo o que já estava certo — o oposto do objetivo.

### 3.2 As barreiras funcionaram
A instrução de que o LLM só pode **baixar** confiança, nunca sobrescrever um resultado de
visão de alta confiança, é o que impediu esse experimento de corromper dados. Ela deve
permanecer, e vale para qualquer modelo futuro.

### 3.3 A pipeline de visão dedicada continua sendo a resposta certa
Isto era a hipótese da SPEC §6.5 e a medição a confirma pelo caminho difícil: o
classificador especializado acerta **99,9854 % das casas**; um VLM genérico acerta
**50 %** de uma pergunta binária muito mais fácil. Não há atalho por modelo grande.

### 3.4 Terceira otimização rejeitada por medição
`docs/ASSETS.md` §2.14 já registrava duas (TTA e temperatura calibrada). Esta é a
terceira. O padrão do projeto — medir antes de adotar — está pagando por si.

---

## 4. Onde o LLM ainda pode servir

O resultado negativo é específico da **verificação de posição por imagem**. Não foi
medido, e continua plausível, para tarefas de **texto**, onde o modelo trabalha no
domínio em que é bom:

- `extract_stipulation` — ler "Mate em 2" / "Weiß zieht und gewinnt" de uma legenda.
- `caption_for_diagram` — redigir legenda a partir de um FEN já confiável.
- `translate_notation_prose` — traduzir a prosa (**nunca** os lances, que passam pelo
  motor exato da F6).

Essas três não foram medidas. **Nenhuma delas deve ser ligada antes de medição própria,
com verdade de campo, no mesmo formato deste relatório.**

---

## 5. Recomendação sobre os 13,7 GB

Decisão do usuário, não minha. As opções:

1. **Remover os dois** (`ollama rm gemma4:e4b-it-qat gemma4:12b-it-q4_K_M`) — recupera
   13,7 GB. Indicado se as tarefas de texto da §4 não forem perseguidas.
2. **Manter só o E4B** — recupera 7,6 GB, preserva a possibilidade de medir a §4.
3. **Manter os dois** — só se houver intenção de medir o 12B, que segue não medido.

Nada foi removido. A remoção é destrutiva e é chamada do usuário.

---

## 6. Reprodutibilidade

```
benchmarks/reports/llm_main.json          experimentos A e B, 198,2 s de execução total
benchmarks/reports/llm_20260907_045918.json
benchmarks/bench_llm.py                   o arranjo de medição
```

Para refazer: `.venv\Scripts\python.exe benchmarks\bench_llm.py` com o Ollama em execução.

**Ressalva de honestidade:** o experimento A tem verdade de campo e é decisivo. O
experimento B não tem, e só descreve o comportamento do modelo. O 12B foi baixado mas
**não** foi medido. As tarefas de texto da §4 **não** foram medidas.
