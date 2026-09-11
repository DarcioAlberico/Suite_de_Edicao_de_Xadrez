# F5 — OCR de texto · Relatório de qualidade

> **Data:** 2026-09-07 · **Máquina:** Windows 11, RTX 5060 (Blackwell), venv `torch cu128`
> **Escopo:** `src/caissa/ocr/` (7.702 linhas, 16 arquivos) · `tests/unit/ocr/` (3.247 linhas, 208 testes)
> Todas as medições deste documento foram feitas localmente, no acervo descrito em
> `docs/quality/CORPUS.md`. Nada saiu desta máquina.

---

## 0. Duas correções de fato, antes de qualquer número

Este relatório existe em parte para corrigir duas afirmações erradas que orientaram
trabalho anterior. Ambas foram verificadas nesta máquina, não assumidas.

### 0.1 «Nenhum projeto irmão tem OCR de texto» — **errado**

`ChessVisionOFF_Puro/src/chess_diagram_ocr/text/` são **50 módulos, ~15.700 linhas**,
mais `ocr.py` e `ocr_caption.py` um nível acima, mais um classificador de caracteres
treinado (`models/char_classifier.pt` + `char_meta.json`, temperatura calibrada
obrigatória, modelo e lista de classes presos por SHA-256). A `docs/ASSETS.md` §2.6 já
registrava a correção; a seção 1 abaixo faz a reconciliação capacidade por capacidade.

**Ressalva sobre o inventário herdado.** Ao ler os arquivos, cinco descrições do
briefing apontavam para o módulo errado, e isso muda conclusões:

| descrição herdada | o que o arquivo é de fato |
|---|---|
| `text/camada.py` = detecção de CMap quebrado | é o leitor de **negrito/itálico** da camada |
| `text/conflitos.py` = árbitro entre reconhecedores | é o detector de **colisão de rótulos** no conjunto de treino |
| `text/procedencia.py` = proveniência em execução | é o contrato do **CSV de proveniência de treino** |
| `text/ocr.py`, `text/ocr_caption.py` | não existem em `text/`; estão um nível acima |
| `text/recognizer.py` = adaptadores de motor | é o reconhecedor de **glifos** próprio |

### 0.2 «Tesseract não está instalado» — **errado**

```
C:\Program Files\Tesseract-OCR\tesseract.exe   →  tesseract v5.5.0.20241111, 161 idiomas
shutil.which("tesseract")                      →  None
```

Tesseract 5.5.0 **está** instalado, com 161 idiomas incluindo `por`, `eng`, `deu`, `rus`,
`spa`, `fra`, `ita`, `nld`. Ele apenas não está no `PATH` — que é o resultado padrão do
instalador oficial para Windows.

Isso é exatamente a razão pela qual o adaptador desta frente faz descoberta própria e
**não** usa `pytesseract`. O adaptador do tronco (`ocr.py:343`) chama
`pytesseract.get_tesseract_version()`, que só consulta o `PATH`; nesta máquina ele
devolve `None` e `build_recognizer` engole a exceção. O sintoma é um teste pulado com a
mensagem «motor tesseract não instalado» (`tests/test_ocr.py:272`) sobre uma máquina onde
ele está instalado. **A medição de CER da seção 3 só foi possível por causa dessa
diferença.**

---

## 1. Reconciliação com o tronco

Legenda: **N** = nosso (`src/caissa/ocr/`), **T** = tronco (`ChessVisionOFF_Puro`).

| Capacidade | Tronco | Nosso | Melhor | Decisão tomada |
|---|---|---|---|---|
| **Adaptador Tesseract** | `ocr.py:271-310`, via `pytesseract`, só `PATH`; **não acha o Tesseract desta máquina** | `engines/tesseract.py` (850 l.): `subprocess`, 3 variáveis de ambiente, `PATH`, 5 diretórios conhecidos; `tsv`+`hocr` numa invocação (confiança de palavra **e** caixas de caractere) | **N** | Mantido. Ver §0.2. |
| **Adaptador RapidOCR** | `ocr.py:211-239`, funcional | **ausente** | **T** | **Absorvido** → `engines/rapidocr.py` (311 l.), registrado no nível 2. |
| **Adaptadores EasyOCR** | `ocr.py:242-268` | ausente | T | **Não absorvido.** EasyOCR carrega torch próprio no mesmo processo; ADR-0004 (orçamento de VRAM) e ADR-0003 tornam isso uma decisão de arquitetura, não de adaptador. Registrado como lacuna. |
| **Binarização Sauvola** | **ausente** (grep `sauvola\|niblack\|threshold_local` em todo `src/` = 0 ocorrências) | `preprocess.py`, tabelas de área somada em float64 | **N** | Mantido. Medido em §3.2. |
| **Binarização Otsu / adaptativa** | `binarizacao.py:57-88`, com seletor `auto` guiado pela **fração de tinta do resultado** (`TINTA_PLAUSIVEL = (0.0005, 0.35)`) | tinha os dois métodos, **sem** a guarda | **T** (a ideia) | **Absorvido**: `PLAUSIBLE_INK` + escada de fallback em `Binarize`. |
| **Deskew** | **ausente** em `text/`. Existe em `preprocess.py:182` para recortes de **tabuleiro**: ±3,0°, passo 0,25°, e **desligado por padrão** (medido como no-op) | projeção sem rotacionar, ±10°, passo fino 0,02° | **N** | Mantido. Medido em §3.1. |
| **Remoção de sombra** | **ausente** em `text/`; a decisão registrada é «tratar iluminação irregular *escolhendo* o limiar adaptativo» (`binarizacao.py:5-11`) | fechamento morfológico + divisão | **N** | Mantido. |
| **Despeckle** | peneira de área/proporção em `boxes.py:161-172` (`0,005·escala²`, razão ≤ 6,0) — mas como **aceitação de glifo**, dentro do pipeline de glifos, não como limpeza de página | área **e** extensão, sobre componentes conexos | **N** para nosso uso | Mantidos os dois: resolvem problemas diferentes. |
| **Dewarp** | **ausente** (`cv2.remap` não aparece em lugar nenhum do tronco) | ajuste polinomial por linha + campo mediano | **N** | Mantido, com uma correção — §2.3. |
| **Bleed-through** | **ausente** (grep `bleed\|verso\|show.?through` = 0) | dois modos: com verso registrado, e heurístico | **N** | Mantido, com uma correção — §2.4. |
| **Detecção de colunas** | `colunas.py` — projeção de **linhas** (não de caixas) sobre x, calhas por vãos livres, número de colunas ilimitado; mais `regioes.py`, que resolve recursivamente o caso do parágrafo de largura total | histograma de cobertura com exclusão de linhas transversais + XY-cut | empate | Mantido o nosso; ele acerta no corpus (§3.3). `regioes.py` fica registrado como referência para o caso recursivo. |
| **Ordem de leitura** | `pagina.py:84` — região → separadores transversais → coluna → banda → x | `reading_order` + `_xy_cut` | empate | Mantido o nosso. Verificado em página real (§3.3). |
| **Cabeçalho corrente** | `pdf_text.py:100` — faixa fixa de **7 %** do topo/rodapé, descartada por inteiro, mais escolha da linha mais extrema em `leitor.py:1429`. **Sem** teste de repetição entre páginas | `RunningFurnitureDetector` — repetição entre páginas (`repeat_frac=0,25`, `min_repeats=3`) **e** faixa de margem | **N** | Mantido. Uma faixa fixa apaga um título de seção que caia no topo; o teste de repetição não. |
| **Nota de rodapé** | **ausente** — `pagina._BLOCOS` tem quatro tipos e nenhum é nota | `_detect_footnotes`: zona inferior + corpo menor + bloco contíguo até o pé | **N** | Mantido. |
| **CMap quebrado** | única sonda: `pdf_pesquisavel.pares_sem_mapeamento`, que **conta U+FFFD**. Medição registrada no próprio arquivo: **zero**, em 40 folhas de cada um dos 14 primeiros livros | quatro eixos: estrutura de fonte (Type0/Identity-H sem ToUnicode), entradas mortas no ToUnicode, taxa de glifos impossíveis, léxico + n-gramas | **N, decisivamente** | Mantido. Ver §1.1. |
| **Arbitragem** | `leitor._arbitro_de_confianca` (confiança média do classificador, nível de **glifo**) e `leitura_de_linha.confianca_por_concordancia` (`max` se concordam, `min` se não) | árbitro por região entre **motores**, calibrado, com escalonamento e registro | níveis diferentes | Mantidos os dois. |
| **Calibração** | `calibracao.py` — temperatura por NLL, ECE **por faixa**, obrigatória na carga do modelo (`modelo.py:208-214`) | `DEFAULT_CALIBRATIONS` escrito à mão, declarado provisório no próprio código | **T (o método)** | Não absorvível hoje: falta o corpus rotulado da SPEC §11.2. Registrado em §5 como a forma correta de ajustar nossos números. |
| **Léxico** | `assets/lexico/`, três `.txt.gz`, **363.799** palavras | 784 palavras embutidas | **T** | **Delegado** — §1.2. |
| **Estimador de qualidade / CER** | **nenhum em execução.** Existe um `cer()` em `cli/texto_placar.py:227`, que é ferramenta de medição. Em execução há faixas de confiança (`documento.py`, cortes 0,30 e 0,75) | `quality.py`: CER, WER, estimador sem referência com confiança própria | **N** | Mantido. |
| **Prosa vs lance** | `notacao.e_linha_de_notacao`, F1 medido **0,8151** em 305 blocos rotulados | regex `is_chess_notation` | T em geral | **Não delegado, de propósito** — §1.3. |
| **Meio-tom, tarja invertida, tabela com moldura, glifos colados/empilhados, caixa alta, apóstrofo** | `trama.py`, `negativo.py`, `tabela.py`, `colados.py`, `empilhados.py`, `caixa_alta.py`, `marca_fina.py` — todos com medições próprias | ausentes | **T** | **Não duplicados.** Pertencem ao pipeline de glifos do tronco. Registrados em §5. |

### 1.1 Por que a detecção de CMap quebrado é nossa, e não delegável

O tronco tentou e desistiu, e o motivo está escrito no próprio arquivo. A sonda dele
procura o caractere de substituição U+FFFD e mediu **zero** em 560 folhas. A causa:

> o modo de falha deste acervo não emite U+FFFD, **emite o codepoint bruto da fonte de
> xadrez** — `2.♘xd4` sai como `2.l0xd4`.

Um contador de U+FFFD é cego para isso por construção. Nosso detector pega exatamente
esse caso pelo eixo 3 (taxa de acerto no dicionário) e pelo eixo 4 (n-gramas): `l0xd4`
não é palavra em idioma nenhum e não é notação sob nosso analisador. É a única
capacidade desta frente que o tronco tentou e não conseguiu.

### 1.2 Léxico — delegado, não copiado

O tronco tem **363.799** palavras em três arquivos gzipados; nós tínhamos **784**.

A decisão foi **ler os arquivos onde eles estão**, com o núcleo embutido como fallback, e
**não copiá-los para este repositório**. A razão está no `assets/lexico/PROCEDENCIA.md`
do próprio tronco: `idioma.txt.gz` não tem origem declarada e `nomes.txt.gz` é em parte
um extrato de índice de jogadores de base comercial, com a licença registrada como **não
conferida**. Copiar seria este projeto afirmar uma liberação que ninguém fez. Vale a
mesma regra do acervo: material local fica local. `CAISSA_LEXICON_DIR` aponta para outro
lugar; sem os arquivos, o núcleo embutido sozinho continua funcionando (há teste).

**Efeito medido** — taxa de acerto no dicionário, camada de texto de páginas reais:

| estrato / livro | 784 palavras | 363.799 palavras |
|---|---|---|
| E1 Dvoretsky (5 pág.) | 0,485 – 0,673 | **0,885 – 0,974** |
| E1 Aagaard (5 pág.) | 0,534 – 0,605 | **0,803 – 0,935** |
| E2 Nunn (5 pág.) | 0,393 – 0,575 | **0,579 – 0,808** |
| E7 Capablanca pt-br (5 pág.) | 0,386 – 0,530 | **0,873 – 0,945** |
| E8 Gaprindashvili, OCR de terceiro (5 pág.) | 0,251 – 0,447 | 0,426 – 0,697 |
| E8 Dobonov, OCR de terceiro (5 pág.) | 0,284 – 0,430 | 0,493 – 0,654 |
| **E6 Boleslávski (cirílico)** | 0,103 – 0,194 | **0,103 – 0,194 — sem ganho** |

Nenhum veredito mudou de lado; o que mudou foi a **margem**, que é o que o sinal mede. O
modelo de n-gramas **não** é retreinado com essas listas (há teste): treiná-lo em 350 mil
sobrenomes destruiria justamente a independência entre os dois sinais.

E1 e E7 sobem para 0,87–0,97 porque muito do que antes contava como «palavra
desconhecida» era nome de jogador, de cidade e de torneio — que é o que `nomes.txt.gz`
tem. A linha do E6 é a que interessa mais, e levou à correção da §2.1.

### 1.3 Uma delegação que seria um bug — e por isso não foi feita

`caissa.notation.looks_like_move` já existe (frente F6) e parece o candidato óbvio para
substituir nosso `is_chess_notation`. **Medido:**

| token | `notation.looks_like_move` | nosso `is_chess_notation` |
|---|---|---|
| `Nf3`, `O-O`, `Qxe4+`, `Cf3` | sim | sim |
| `lLib8` | **sim** | não |
| `l0xd4` | **sim** | não |
| `i.d4+` | **sim** | não |

`looks_like_move` é um filtro **de recall**, e está certo em ser permissivo: o analisador
da F6 valida cada candidato contra o tabuleiro logo em seguida. Mas `lLib8` e `l0xd4` são
precisamente o que um CMap quebrado produz de `♖b8` e `♘xd4`. Tokens de notação saem do
denominador do dicionário — então delegar aqui **cegaria o detector de nível 0 para a
falha que ele existe para pegar**. A duplicação é deliberada e está pinada por teste
(`test_is_chess_notation_is_stricter_than_the_notation_front`) para que ninguém a
«limpe» depois.

### 1.4 O que foi apagado

Honestamente: **pouco**, e o motivo é o resultado da reconciliação em si. A hipótese de
partida era que nossa `src/caissa/ocr/` duplicava o tronco. Lidos os dois lados, as
capacidades acusadas de duplicação — Sauvola, deskew, remoção de sombra, dewarp,
bleed-through, detecção de CMap quebrado, árbitro entre motores, estimador de CER,
remoção de cabeçalho por repetição, identificação de nota de rodapé — **não existem no
tronco**. Não eram duplicatas.

Apagado de fato:

1. **`types.strip_accents`** (11 linhas) — duplicata exata de `lexicon._fold`, sem nenhum
   uso, e no módulo errado (auxiliar de texto dentro do módulo de geometria e tipos).
   Removida junto o `import unicodedata` que ficou órfão.
2. **A lista de 784 palavras como fonte primária** — rebaixada a fallback documentado
   (§1.2). Não apagada porque é o que faz um checkout limpo funcionar.
3. **`Binarize`, o caminho sem guarda** — o método configurado deixou de ser a palavra
   final; ver §1 (linha «Otsu / adaptativa»).

Não apagado, com justificativa: `engines/paddle.py`, `engines/surya.py` e
`engines/rapidocr.py` são adaptadores de motores não instalados. Cobertura de 23–30 %.
Isso é o contrato do registro, não código morto: cada um relata sua ausência com o
comando de instalação, e passa a funcionar se o pacote aparecer.

---

## 2. Defeitos encontrados por medição, e corrigidos

Nenhum destes veio de leitura de código. Todos apareceram quando um teste ou uma medição
produziu um número que não fazia sentido.

### 2.1 Página cirílica correta era **rejeitada** — `lexicon.py`, `pdf_text_layer.py`

O modelo de n-gramas é treinado nas listas latinas embutidas. Letras cirílicas são letras
perfeitamente boas que ele nunca viu, então todo bigrama cai no piso de suavização e
`ngram_plausibility` devolve ~0,0 — **indistinguível de lixo**. Com a cobertura de russo
do léxico em 97 palavras, a conjunção `dicionário < 0,12 E n-gramas < 0,55` virava, na
prática, um teste de 97 palavras.

Medido (E6, Boleslávski, camada de texto, 5 páginas): as páginas têm 88–93 % de cirílico
e pontuam 0,000 / 0,026 / 0,000 / 0,115 / 0,091. A **página 60 — uma tabela correta de
lances em notação figurada russa — era rejeitada por inteiro**, mandando para OCR uma
página que não precisava.

Corrigido: `modelled_script_share()` mede a fração de letras que o modelo sabe julgar, e
abaixo de `min_modelled_script_share = 0,50` **os dois termos lexicais se abstêm**. A
página é então aceita pela estrutura das fontes, com confiança **0,70** — abaixo da
confiança de borda, porque nada ali leu as palavras — e o motivo diz isso ao usuário.
Resultado depois: 5/5 aceitas, todas marcadas como script não julgado.

### 2.2 Toda página já reta era reamostrada — `preprocess.Deskew`

`min_angle` valia 0,05°. O ruído próprio do estimador, medido em quatro páginas retas por
construção (corpos e comprimentos de linha diferentes), é **−0,06, −0,08, −0,12, −0,12°**
— um viés pequeno e sistemático, porque a irregularidade da margem direita torna o perfil
de projeção levemente assimétrico. O padrão estava **abaixo do próprio piso de ruído**:
toda página reta do acervo levava um `warpAffine` bicúbico, e o borrão que vem junto,
para corrigir ruído. Novo padrão: **0,15°**.

### 2.3 Dewarp inventava curvatura em página plana — `preprocess.Dewarp`

Uma página sintética **plana** de 21 linhas relatava **9,0 px** de curvatura, três vezes o
`min_amplitude_px` de 3,0 — e era remapeada. A causa é que o centro de tinta de uma linha
oscila com o conteúdo (ascendentes, descendentes, fim de linha irregular), e a oscilação é
correlacionada entre linhas, então a mediana não a cancela.

Amplitude sozinha não separa curvatura de ruído. O que separa é **concordância**: uma
curvatura real tem a mesma forma em toda linha, a oscilação não. Nova métrica = amplitude
do campo mediano ÷ dispersão interquartil entre linhas:

| página | amplitude | dispersão | concordância |
|---|---|---|---|
| plana | 9,0 px | 6,3 px | **1,43** |
| curvada 14 px | 40,7 px | 5,9 px | **6,92** |

Limite em 2,0, com folga dos dois lados.

### 2.4 Bleed-through só enxergava uma faixa de 60 níveis — `preprocess.BleedThroughReduction`

A banda «suspeita» era `limiar_de_tinta + 60`, fixo. Medido numa página com fantasma no
nível 214: Otsu pôs o limiar em 146, a banda terminou em 206, e o fantasma — visível,
claramente não-tinta — nunca era tocado (`removed_pixels: 0`). Transparência do verso se
define por **onde está entre a tinta e o papel**, não por um número constante de níveis.
Agora a banda é uma fração (0,80) do intervalo tinta–papel, com o papel medido no
percentil 98. Mesmo caso: banda até 233, 14.429 pixels tratados.

O limite que **permanece**, e está pinado por teste: um fantasma mais escuro que o limiar
de tinta é indistinguível de tinta por qualquer regra que só olhe a frente da folha. A
resposta honesta é registrar o verso, que é o outro modo.

### 2.5 `applied` mentia — `preprocess.StepReport`

`applied` significava «a etapa rodou sem levantar exceção», mas `applied_steps` a usava
como «a etapa mudou a página». Toda etapa aqui pode, corretamente, não fazer nada — e
`Upscale` numa página de 300 DPI relatava `applied=True` com a mensagem «resolução
suficiente; sem ampliação». Acrescentado `changed`, derivado por identidade do array
(todo caminho de no-op devolve o array que recebeu, então o teste é exato e grátis).

### 2.6 `Deskew(max_angle=3.0)` devolvia 3,5° — `preprocess.estimate_skew_angle`

A busca fina abria `±coarse_step` em torno do vencedor grosso, sem reclampar. Um vencedor
na borda do intervalo deixava o refinamento sair dele. Grade fina agora clampada.

### 2.7 `OcrEngine` não declarava `supports_language` — `engines/base.py`

`EngineRegistry.available(lang=…)` e o árbitro chamam `supports_language` em qualquer
motor registrado, mas o Protocol não o declarava. Um adaptador que o omitisse falharia na
primeira página, não no registro. Acrescentado ao Protocol.

---

## 3. Medições

Regras de `CORPUS.md` §5 seguidas: mediana de 3 execuções onde há tempo envolvido,
estrato sempre nomeado, referência sempre declarada.

### 3.0 Motores realmente exercitados nesta máquina

| Nível | Motor | Disponível | Idiomas | Exercitado nos testes? |
|---|---|---|---|---|
| 0 | `pdf_text_layer` | **sim** | 9 | **sim** — sintético e corpus |
| 1 | `tesseract` 5.5.0 | **sim** (fora do `PATH`) | **161** | **sim** — CER real, §3.1 e §3.2 |
| 2 | `paddleocr` | não | — | só o caminho de ausência |
| 2 | `rapidocr` | não | — | só o caminho de ausência |
| 3 | `surya` | não | — | só o caminho de ausência |
| 4 | VLM (Gemma 4) | — | — | deliberadamente não registrado: é da F11 |

**Não medido, e dito claramente:** PaddleOCR, RapidOCR, EasyOCR e Surya não têm nenhum
número neste documento. Nenhum está instalado, nenhum foi instalado para medir, e por
ADR-0003 instalar `onnxruntime-gpu` ou `paddlepaddle-gpu` neste ambiente é proibido. O
que foi testado desses quatro é que **degradam bem**: relatam ausência em português, com
o comando de instalação e o aviso da ADR-0003, e nunca levantam exceção para a cascata.

### 3.1 CER por região — nível 1 contra a camada de texto do próprio livro

Referência: a camada de texto do livro, que é o que `CORPUS.md` §4 designa para a F5.
Recorte: **uma região de parágrafo por página**, a mesma para os dois lados. O recorte é
o ponto — um CER de página inteira mistura erro de caractere com ordem de leitura e com
o ruído que o Tesseract lê dentro dos diagramas, e deixa de medir o que o nome diz.
Renderização a 300 DPI, `--psm 6`, mediana de 3 execuções.

| Estrato | Livro | n | CER | CER (só prosa) | WER | s/região |
|---|---|---|---|---|---|---|
| **E1** | Dvoretsky 2025 + Aagaard | 16 | **0,0358** | **0,0142** | 0,166 | 0,23 |
| **E2** | Nunn, *Pawnless Endings* | 8 | **0,1337** | 0,1861 | 0,383 | 0,41 |
| **E8** | Dobonov, já OCR de terceiro | 8 | **0,0664** | **0,0353** | 0,381 | 0,23 |
| — | **todos** | **32** | **0,0574** | **0,0387** | — | — |

Como ler estes números, sem exagerá-los:

- **A referência não é verdade absoluta.** É a camada de texto do livro, que tem erros
  próprios — sobretudo em notação figurada. A coluna «só prosa» remove os tokens de
  notação dos dois lados e é o sinal mais limpo: **0,0142 em E1**.
- **O E2 é pior que o E8, e isso é sobre a referência, não sobre o motor.** A camada do
  Nunn traz a notação figurada já destruída (`\x0cg8`, `lLJfS+`, `Wg4+`), então o CER ali
  mede desacordo entre duas leituras ruins do mesmo figurino. É por isso que a coluna «só
  prosa» do E2 (0,186) é *pior* que a coluna cheia: os tokens de notação, que ambos os
  lados erram do mesmo jeito, estavam disfarçando o desacordo.
- **A meta da SPEC (CER ≤ 0,5 % limpo) não está atingida e não é comparável ainda.**
  Ela pressupõe verdade de campo anotada, que a §11.2 prevê e que não existe. Contra
  verdade exata — página sintética, texto conhecido — o Tesseract dá **CER 0,0000** com
  confiança média 0,966 (§3.2).

### 3.2 O pré-processamento vale o custo? Medido contra degradação conhecida

Página renderizada aqui, danificada aqui, então a referência é exata. Tesseract `--psm 6`.

| Degradação aplicada | CER cru | CER pré-processado | ganho |
|---|---|---|---|
| nenhuma (controle) | 0,0000 | 0,0000 | 0,0000 |
| inclinação 2,3° | 0,0000 | 0,0000 | 0,0000 |
| **iluminação desigual** | 0,0188 | **0,0000** | **+0,0188** |
| sujeira (600 pontos) | 0,0031 | **0,0000** | +0,0031 |
| verso transparecendo | 0,0024 | **0,0000** | +0,0024 |
| **inclinação + sombra + sujeira** | 0,0157 | **0,0016** | **+0,0141** |
| curvatura de foto (14 px) | 0,0000 | 0,0000 | 0,0000 |
| 150 DPI (ampliação) | 0,0047 | **0,0008** | +0,0039 |

Duas conclusões honestas, incluindo a que não favorece o código:

1. Onde há dano fotométrico, o pipeline **zera** o CER, e nunca piora nenhum caso.
2. **O Tesseract já é robusto sozinho** a 2,3° de inclinação e a curvatura suave: CER
   0,0000 sem pré-processamento nenhum. Deskew e dewarp não se pagam nessas páginas — e
   nas páginas de corpus da §3.1, que são renderizações limpas de PDF nativo, o
   pré-processamento é **levemente negativo** (mediana 0,0574 → 0,0598). É por isso que
   as etapas são selecionáveis e que `dewarp` já vinha desligado por padrão. Ligar o
   pipeline inteiro em fonte nativa é desperdício.

### 3.3 Camada de texto — veredito por estrato

Amostragem de páginas fixas, não aleatória (um teste de corpus instável é pior que
nenhum). Todos estes vereditos estão pinados em `tests/unit/ocr/test_text_layer.py`.

| Estrato | Livro | Páginas | Veredito | Está certo? |
|---|---|---|---|---|
| E1 | Dvoretsky 2025 | 5 | 5 aceitas @ 0,98 | **sim** |
| E1 | Aagaard | 5 | 5 aceitas @ 0,98 | **sim** |
| E1 | **Flores Rios (Quality Chess)** | 3 | 3 «só imagem» | **sim, e corrige o CORPUS.md** — ver abaixo |
| E2 | Nunn | 4 | 4 aceitas | sim |
| E6 | Boleslávski (cirílico) | 5 | 5 aceitas @ **0,70**, script não julgado | sim, depois da §2.1 |
| E8 | Gaprindashvili `_OCR_Aprimorar_Aprimorar` | 6 | 3 «só imagem», 1 rejeitada, 2 aceitas @ 0,98 | **parcialmente — ver abaixo** |
| E8 | Dobonov `_OCR` | 6 | 1 «só imagem», 5 aceitas @ 0,98 | **sim** |

**Correção ao `CORPUS.md`.** *Chess Structures* de Flores Rios está no estrato E1
(«produção digital moderna») e é a referência visual da F7. Para efeito de nível 0 ele
**não é nativo**: não tem camada de texto nenhuma (`char_total = 0` nas três páginas
amostradas). É PDF de imagem. E1 não implica «tem camada de texto boa».

**A fraqueza honesta desta frente — Gaprindashvili p202 e p245.** As duas são aceitas com
confiança 0,98, e isso está *parcialmente errado*. A prosa está correta; o texto de lances
está destruído — os figurinos Batsford voltaram como `'i'd6+`, `l:th7`, `J:!.'.8c7`. A
prosa domina a contagem de tokens e vence todos os sinais lexicais. **A correção não é um
limiar melhor: é arbitragem por região**, que é exatamente o que a SPEC §7.1 pede e por
que `RegionTask` tem `clip`. O veredito de página inteira é a unidade errada para um
livro que mistura prosa e figurino. Está pinado como teste, com a tabela, para que a
próxima pessoa não descubra de novo.

Contraste que impede a regra fácil: o Dobonov também passou por OCR de terceiro e é
aceito **corretamente**. Ele está em notação descritiva espanhola (`2. CxT`), com letras
comuns — o OCR de terceiro não tinha figurino para destruir. «Passou por OCR de outro»
não pode, sozinho, ser a regra de rejeição.

### 3.4 Detecção de CMap quebrado — verdade de campo sintética

PDFs construídos e quebrados pelo próprio teste, então a verdade é exata.

| Caso | Esperado | Obtido |
|---|---|---|
| TrueType embutida, ToUnicode íntegro | aceita | **aceita**, 0,98 |
| Base-14 (`helv`), sem ToUnicode | aceita | **aceita** — não confundir com Type0 |
| Type0/Identity-H, ToUnicode **removido** | rejeitada | **rejeitada**, 0,00 |
| Type0/Identity-H, ToUnicode presente mapeando tudo para U+0000 | rejeitada | **rejeitada**, 0,00 |
| Página em branco | «só imagem» | **«só imagem»** |

O quarto caso é o difícil: `has_tounicode` é verdadeiro e uma verificação ingênua passa.
Pego por `dead_entry_ratio ≥ 0,90`.

### 3.5 Custo

| Operação | Mediana | Observação |
|---|---|---|
| Tesseract, região de parágrafo (300 DPI) | **0,23 s** | E1/E8, 3 execuções |
| Tesseract, página inteira 8,4 MP | **1,00 s** | com `tsv`+`hocr` na mesma invocação |
| Veredito de nível 0, por página | < 0,01 s | sem renderizar nada |
| Pipeline de pré-processamento, página 2 MP | ~0,35 s | |
| Carga do léxico do tronco (364 mil palavras) | 0,16 s | uma vez por processo |

---

## 4. Testes

`tests/unit/ocr/` — **208 testes, 3.247 linhas, todos passando**. Cobertura do pacote:
**78 %**. Suíte do projeto inteiro: **1.969 passando**, nenhuma regressão.

| Arquivo | Testes | O que prova |
|---|---|---|
| `test_preprocess.py` | 41 | Recuperação de inclinação dentro de **0,2°** em 9 ângulos aplicados aqui; Sauvola contra Otsu sob iluminação desigual, medido por F1 de tinta contra a máscara limpa; despeckle preservando traços de 1 px; sombra, verso, dewarp, ampliação; determinismo e não-mutação da entrada |
| `test_text_layer.py` | 27 | CMap quebrado nos dois modos, análise de ToUnicode, estrutura de fonte, e os vereditos de corpus da §3.3 pinados com a tabela |
| `test_layout.py` | 43 | Ordem de leitura em duas colunas (esquerda inteira antes da direita), calha estreita rejeitada, título transversal não destrói a calha, cabeçalho por repetição, rodapé, nota de rodapé, legenda, rótulos de eixo do tabuleiro; e páginas reais do Nunn |
| `test_arbiter.py` | 27 | Escalonamento com motores falsos; texto de alta confiança e implausível **perde**; nível 0 com barra mais alta; idioma, disponibilidade e orçamento; determinismo em 5 execuções; desempate; registro completo anexado ao resultado |
| `test_engines.py` | 29 | Registro preguiçoso, fábrica que falha registrada uma vez só, `invalidate`; ausência explicada em português com `pip install` e aviso da ADR-0003; descoberta do Tesseract fora do `PATH`; CER real |
| `test_quality.py` | 41 | Levenshtein contra implementação ingênua em 60 pares aleatórios; CER exato; estimador **ordenado** e dentro de banda declarada; léxico e a divergência deliberada da §1.3 |

Notas sobre método:

- **Toda degradação de imagem é gerada nos testes**, então a verdade é exata. Nenhum
  fixture binário, nada para envelhecer.
- Testes de corpus levam `@pytest.mark.golden` e **pulam** quando o acervo não está na
  máquina. Nenhum PDF foi copiado para o repositório.
- Os testes de corpus afirmam **propriedades** que sobrevivem a ruído (contagem de
  colunas, colunas não intercaladas, cabeçalho removido, fólio encontrado), não
  transcrições.
- O teste da §3.3 sobre Gaprindashvili p202/p245 pina uma **fraqueza conhecida**. Se um
  dia falhar porque as páginas passaram a ser rejeitadas, isso é melhora: atualizar a
  tabela e este relatório, não apagar o teste.

---

## 5. O que falta

Ordenado por quanto muda o resultado.

1. **Arbitragem por região aplicada de fato à camada de texto** (§3.3). O árbitro existe,
   é testado e aceita `clip`; o que falta é o laço que corta a página em regiões, chama o
   nível 0 por região, e deixa o nível 1 assumir só as regiões de figurino. É a correção
   direta do único erro conhecido do nível 0.
2. **Corpus rotulado da SPEC §11.2.** Sem ele: as calibrações do árbitro continuam
   confessadamente provisórias, `NONWORD_DETECTION_RATE = 0,55` continua sendo a maior
   fonte de erro do estimador, e não há CER contra verdade de campo — só contra a camada
   de texto, que tem erros próprios. O método correto para ajustar está pronto no tronco:
   `calibracao.ece_por_faixa`, temperatura por NLL, ECE **por faixa** e não ponderada.
3. **Cobertura de não-latino.** O E6 hoje é aceito por abstenção, não por leitura. Falta:
   lista de palavras cirílicas, ou um modelo de n-gramas por script, ou o Surya (nível 3,
   que é o motor certo para isso e está atrás da ADR-0003).
4. **Cabeçalho corrente de capítulo.** A regra por repetição remove o cabeçalho de verso
   («SECRETS OF PAWNLESS ENDINGS», 12/12 páginas) e deixa o de recto, que é o título do
   capítulo e muda por seção. Comportamento correto para uma regra de repetição, resposta
   errada para o livro. Precisa de modelo de seção — é da F1.
5. **Absorver o pipeline de glifos do tronco**: `trama.py` (meio-tom — 71 componentes de
   caractere onde havia zero), `negativo.py` (tarja invertida), `tabela.py` (tabela com
   moldura), `colados.py`, `empilhados.py`, `caixa_alta.py` (CER 0,1434 → 0,1114 medido),
   `marca_fina.py`. Cada um tem medição própria e nenhum tem equivalente aqui.
6. **Adaptador EasyOCR** e a decisão de arquitetura que ele exige (torch no mesmo
   processo, ADR-0004).
7. **`ruff`**: 252 achados no pacote de OCR — e 207 em `notation`, 147 em `typeset`, 135
   em `vision`. A configuração é aspiracional e nenhum pacote do projeto está limpo. Os
   erros reais (`F`, `E9`) estão zerados nos arquivos desta frente. Uma limpeza
   `PLR2004`/`TID252` em toda a árvore é trabalho de projeto, não de frente.
8. **`mypy`**: 31 erros restantes, a maioria `no-any-return` na fronteira com PyMuPDF, que
   não tem stubs.

---

## 6. Arquivos

**Modificados** — `preprocess.py` (§2.2–2.6 e a guarda de tinta), `lexicon.py`
(delegação e `modelled_script_share`), `engines/pdf_text_layer.py` (abstenção por
script), `engines/base.py` (`supports_language` no Protocol),
`engines/registry.py` (RapidOCR), `types.py` (remoção de `strip_accents`).

**Criados** — `engines/rapidocr.py`; `tests/unit/ocr/__init__.py`,
`test_preprocess.py`, `test_text_layer.py`, `test_layout.py`, `test_arbiter.py`,
`test_engines.py`, `test_quality.py`; ampliações em `tests/unit/ocr/conftest.py`.

**Não tocados** — `src/caissa/core/`, `typeset/`, `notation/`, `vision/`, `llm/`,
`pyproject.toml`, `scripts/`, `benchmarks/`, `tests/integration/`.
