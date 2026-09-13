# Rotulagem humana e treino do Tesseract

> **Data:** 2026-09-13 · Sol §SOL-0 (corpus), §SOL-11 (revisão), §SOL-12 (hashes e versões).
> Ferramentas: `tools/rotular.py` (janela Tk), `tools/treinar_tesseract.py` (terminal),
> pacotes `caissa.ocr.labeling` e `caissa.ocr.training`.

`SOL_REPORT.md` §2 diz o que falta ao corpus dourado: **verdade escrita por gente sobre
scans reais**. Os portões de CER e de lances hoje medem tipografia sintética e regiões
nativas. Este documento descreve a bancada que fecha essa lacuna — o equivalente, no
projeto, ao modo *verificação* e ao *treino de padrões* do ABBYY FineReader — e o que
sai dela.

---

## 1. O que a bancada faz

```
python tools/rotular.py labeling --pdf "C:\...\PDF\Koblenz - El dominio del arte de la combinacion (1978).pdf" --reviewer ana
```

| Tela | O que é |
|---|---|
| esquerda | a página, com as regiões que o layout achou (tracejado roxo) e, dentro delas, uma caixa por **linha**, colorida pelo estado: âmbar pendente, verde aceita, azul editada, cinza rejeitada |
| direita, alto | o **recorte** da linha atual a 300 DPI |
| direita, meio | a **leitura do motor** com palavras fracas em destaque (amarelo abaixo do limiar, vermelho bem abaixo), as **leituras alternativas** dos outros candidatos (variante × motor), o **motivo** da dúvida e o campo **Verdade** |
| direita, baixo | a lista de linhas da página; «só duvidosas» filtra o que merece olhar |

O reconhecimento é o do produto (`OcrService.recognize_image`): mesmo layout, mesmos
candidatos, mesma fusão. Uma região `page` (layout não segmentou) é partida nos parágrafos
que o próprio motor devolve. Se o layout errou, **D** desenha uma região à mão e ela é
reconhecida sozinha.

**Teclas:** `Enter` aceita a leitura (ou grava o que você digitou, se mudou) e vai à
próxima pendente · `Ctrl+Enter` grava a edição · `Ctrl+R` rejeita (não é texto: mancha,
diagrama, coordenada) · `Alt+1`/`Alt+2` copiam uma alternativa · `Ctrl+↑/↓` navegam ·
`F5` reconhece a página · `PageUp/PageDown` mudam de página · `Ctrl+S` salva.
«Aceitar confiáveis da página» aceita de uma vez toda linha sem palavra fraca, sem candidato
discordante e com texto — o «pule o que o motor tem certeza» do FineReader; as duvidosas
continuam pendentes.

Botão direito numa região: tipo (`paragraph`, `movetext`, `heading`, …), **FEN inicial dos
lances** (o que o replay de legalidade precisa e 98 % do corpus não tem — `SOL_REPORT.md`
§3), rejeitar a região inteira, remover.

Cada decisão grava **quem, quando e quantos segundos** (`audit.jsonl`); o tempo por página
fica em `pages/*.json`. Projeto = pasta com `project.json`, `pages/`, `audit.jsonl`.

---

## 2. A regra da partição cega

Cada região completa vira um item do manifesto com id
`real:<livro[:24]>:<página>:<y0>:<x0>` (o esquema de `build_manifest.py`, mais `x0` para
duas colunas). A partição é a função fixa do id (`partition_for`): 50 % dev, 25 % calib,
25 % cega. A janela mostra a partição da região atual e a barra de estado conta as regiões
cegas da página.

**Uma região cega entra no manifesto (oculta por padrão) e em mais nada**: não vai para
a verdade de treino, nem para as correções, nem para os pares de calibração. A regra é por
região, e não por página, porque a partição do manifesto é por item e um item é uma região
— uma página com vinte regiões seria cega com probabilidade 1 − 0,75²⁰ ≈ 99,7 %.

`caissa.ocr.review.blind_guard`, que protege a fila de revisão do importador, é mais
conservador (marca a página inteira). Os dois concordam sobre quais ids são cegos.

---

## 3. O que sai (menu *Exportar*)

| Saída | Onde | Consumidor |
|---|---|---|
| **Verdade para treino** | `<projeto>/ground_truth/` — `<nome>.png` + `<nome>.gt.txt` por linha, `index.jsonl` com documento, página, região, partição, `report.json` | `lstmtraining` (via `caissa.ocr.training`) |
| **Fundir no manifesto dourado** | `benchmarks/corpus/golden/manifest.private.json` (ou outro) — um item `pdf-scan` por região completa, `strata=("native",)`, tags `human-labelled`, `scan`; itens com o mesmo id são substituídos | `bench_sol.py`, `calibrate_sol.py`, `sol_gate.py` |
| **Correções e pares** | `<projeto>/corrections.json` (o formato de `ReviewQueue.corrections()`), `<projeto>/calibration_pairs.json` (`(confiança, correta)` por linha, com motor/idioma/DPI/tipo) | auditoria; calibração direta |

«Região completa» = todas as linhas decididas e ao menos uma mantida como texto. O
gênero (`movetext` a partir de 6 lances) e o script (`cyrillic` para `ru`) seguem
`build_manifest.py`. Para o benchmark achar o PDF, ele precisa estar em `PDF_DIR`
(`sol_corpus.py`); o projeto guarda o caminho absoluto para as outras exportações.

Depois de fundir, o hash do corpus muda: o baseline precisa ser recongelado
(`bench_sol.py --system baseline --publish`) antes de o portão comparar alguma coisa.
A faceta `source` do relatório separa `pdf-scan` de `pdf-native` e `synth`.

---

## 4. Treino (ajuste fino do Tesseract)

O FineReader treina *padrões* por caractere. O reconhecedor do Tesseract 5 é uma LSTM
por linha e não tem padrões; o equivalente é o **ajuste fino**: o modelo base continua
treinando sobre linhas com verdade até o erro num conjunto reservado parar de cair, e o
resultado é um `.traineddata` novo que o motor carrega como qualquer idioma.

```
python tools/treinar_tesseract.py --project labeling --base-lang spa --preflight
python tools/treinar_tesseract.py --project labeling --base-lang spa --download-base
python tools/treinar_tesseract.py --gt labeling/ground_truth --base-lang spa --base-model models/tessdata_best/spa.traineddata --iterations 3000
```

Ou o botão **Treinar…** da janela (mesmo pipeline, log ao vivo, cancelável).

Passos (`caissa.ocr.training.tesseract_finetune`), cada um nomeado no log:

1. copia a base para `work/` e desempacota (`combine_tessdata -u`) — `.lstm` para continuar
   e `.lstm-unicharset` com os caracteres que o modelo sabe emitir; copia `configs/`
   também, porque `--tessdata-dir` decide onde `lstm.train` é procurado;
2. confere cada linha contra o unicharset; linha com caractere que a base não codifica
   (`♘`, por exemplo) é **excluída e listada** no relatório;
3. gera um `.lstmf` por linha (`tesseract <png> <base> --psm 13 lstm.train`), com o `.box`
   `WordStr` ao lado da imagem — é de lá que o Tesseract lê a verdade;
4. divide pela partição do `index.jsonl`: **dev treina, calib avalia** (sem calib, um
   décimo de dev por hash); cega nunca chegou aqui;
5. `lstmtraining --continue_from` com progresso (iteração, erro de treino);
6. `lstmtraining --stop_training` sela o checkpoint num `.traineddata`;
7. `lstmeval` na lista de avaliação, base e modelo novo — **CER e WER antes/depois**;
8. copia os idiomas instalados para a pasta de saída, que fica utilizável como
   `--tessdata-dir` sozinha; grava `weights.json` (hash, licença, base), `report.json`,
   `report.md`, `log.txt`.

### A base precisa ser float

O instalador do Windows traz os modelos **inteiros** (`tessdata_fast`): reconhecem mais
rápido e **não aceitam ajuste fino** — o `lstmtraining` responde
`is an integer (fast) model, cannot continue training` e o pipeline para com essa frase
traduzida. O preflight avisa antes (tamanho do `.lstm`). É preciso o modelo float de
`tessdata_best` (Apache-2.0): `--download-base` ou o botão «Baixar base» o buscam de
`github.com/tesseract-ocr/tessdata_best` para `models/tessdata_best/`, com hash gravado.

### Medir o modelo treinado

```
python benchmarks/bench_sol.py --tessdata-dir models/tessdata --model-prefix caissa --label caissa_spa
```

`por` vira `caissa_por` quando `models/tessdata/caissa_por.traineddata` existe; o resto
usa a base copiada. O relatório registra `tessdata_dir` e `model_prefix` no ambiente.
O portão (`sol_gate.py`) compara com o baseline como qualquer outra mudança.

---

## 4b. Figurinas: o leitor de glifos como segunda opinião

Nenhum motor de linha lê figurina: o `eng.traineddata` não tem ♖ no alfabeto, e o Tesseract
devolve a forma latina mais parecida — sempre a mesma (♖→H, ♕→W, ♘→S, ♗→2/8/&). O tronco
ChessVisionOFF tem um **classificador de glifos** treinado nessas formas
(`models/char_classifier.pt`, 314 classes com ♔♕♖♗♘♙ e ligaduras como `♕x`; 99,1 % no teste).
`caissa/ocr/engines/glyph.py` o expõe como motor, e o `OcrService` o consulta como
**candidato secundário** em regiões que carregam notação (`glyph_candidates=True`, padrão):

- roda **uma faixa por linha** que o Tesseract achou, para nunca fundir duas colunas;
- na fusão SOL-6 ele **nunca ancora** e nunca decide pontuação ou caixa (`36...` continua `36...`);
- a única troca que faz sozinho é a **figurina no lugar do sósia latino** — mesmo lance
  depois do primeiro caractere (um dígito/letra trocado tolerado), lance válido, confiança
  ≥ 0,70: `Hea!`→`♖e8!`, `2d5`→`♗d5`, `22...28,`→`22...♗f8,`, `De2`→`♘e2`; um lance de peão
  (`e4`) nunca é tratado como cifra;
- a prosa fica com o Tesseract (`If`, `40`, `Hubner:` — o leitor de glifos lê `lf`, `4o`).

Medido na página 10 de *Dvoretsky & Yusupov, Secrets of Positional Play* (figurinas, inglês):
das 27 linhas de lances, todas as figurinas saem certas depois da fusão; sem o candidato,
nenhuma. Custo: ~2 s a mais por página na GPU. Sem o tronco na máquina, o motor se declara
indisponível com uma frase e nada muda.

Isso **não treina** nada: o rótulo humano continua sendo a verdade, mas a hipótese que o
revisor vê já vem com ♖e8!, e é isso que entra no `.gt.txt` quando ele aceita — o que, por
sua vez, é o que permitiria a rota B (ensinar o próprio Tesseract as figurinas com unicharset
estendido), ainda não feita.

## 5. O que foi verificado em 2026-09-13

- Três páginas de *Koblenz — El dominio del arte de la combinación (1978)* (scan, espanhol):
  reconhecimento em 3,4 s/página, 19 regiões por página após a partição por parágrafo,
  linhas com confiança e alternativas; 47 linhas exportadas, **47 `.lstmf` gerados** com
  as ferramentas instaladas (Tesseract 5.5.0); `lstmtraining` recusou o `spa.traineddata`
  instalado com a mensagem de modelo inteiro, capturada como falha explícita.
- **O ajuste fino em si não foi executado**: exige o modelo float, que não está nesta
  máquina. O pipeline a partir do `lstmtraining` está coberto por `tests/unit/ocr/test_training.py`
  com um executor falso (ordem das ferramentas, listas por partição, unicharset, relatório,
  registro de pesos, recusa do modelo inteiro).
- 16 testes novos (`test_labeling.py`, `test_training.py`) mais 8 do leitor de glifos
  (`test_glyph_engine.py`); `tests/unit/ocr` + `tests/unit/ingest`: 686 passam.

## 6. O que continua faltando

1. Rotular de verdade: ≥ 20 páginas para a revisão cega de `SOL_REPORT.md` §5, 200 para a
   meta de Sol — trabalho humano, com a bancada pronta.
2. Baixar um `tessdata_best` e rodar o primeiro ajuste fino de ponta a ponta; medir com
   `--tessdata-dir` e publicar.
3. A janela de revisão do shell F9 continua pendente: esta é uma bancada Tk de rotulagem,
   não a interface do produto.
