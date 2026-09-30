# Registros de Decisão Arquitetural (ADR)

Cada decisão abaixo é vinculante. Alterar uma delas exige um novo ADR que a substitua
explicitamente, com justificativa e plano de migração.

---

## ADR-0001 — PySide6 (Qt 6) como toolkit de interface

**Status:** ~~Aceita~~ **SUBSTITUÍDA pela ADR-0009** · **Data:** 2026-09-07

> Esta decisão foi tomada antes do inventário completo dos projetos existentes e
> partia da premissa errada de que a base era Tkinter. Ver ADR-0009.

### Contexto
O requisito é qualidade visual "AAA", comparável a Affinity Publisher e DaVinci Resolve.
Os projetos irmãos existentes usam Tkinter. As opções consideradas foram Tkinter,
PySide6/PyQt6, e uma pilha web (Electron/Tauri + Python de fundo).

### Decisão
**PySide6.**

### Justificativa
- Tkinter não tem renderização acelerada, composição de camadas, animação, gráficos
  vetoriais de qualidade nem sistema de temas sério. Não há caminho de Tkinter até AAA.
- Qt tem `QGraphicsView` com transformação e cache de tiles — exatamente o necessário
  para pan/zoom a 60 fps sobre páginas de 300 DPI —, além de `QtSvg` para diagramas
  vetoriais e um sistema de estilos (QSS) que permite temas reais.
- PySide6 é **LGPL**, o que permite distribuição de aplicação fechada ou aberta sem
  a obrigação viral do PyQt6 (GPL) nem custo de licença comercial.
- Empacota bem com PyInstaller no Windows.

### Consequências
- O código dos projetos irmãos em Tkinter precisa ser **portado**, não reaproveitado
  diretamente. A lógica de CV e PDF é reaproveitável; a camada de widgets não.
- A equipe assume a complexidade de Qt (sinais, modelos, threads). Compensa-se com
  uma camada fina de abstração em `src/caissa/ui/`.
- Toda operação pesada precisa sair da thread de UI (`QThreadPool` + workers).

---

## ADR-0002 — Document IR como centro do sistema

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
O requisito é "formatação rica de texto para todos os formatos de saída (docx, html,
epub)" mais PDF e LaTeX. A abordagem ingênua é escrever um conversor por par de formatos
(N x M conversores), o que não escala e degrada em cada salto.

### Decisão
Um **Document IR** (representação intermediária) semântico e único. Importadores
produzem IR; exportadores consomem IR. Nenhum conversor direto formato-a-formato.

### Justificativa
- N + M em vez de N x M.
- Um recurso novo de formatação é implementado uma vez no IR e mapeado por exportador.
- Permite operações que só existem no nível semântico: trocar a fonte de xadrez de todo
  o livro, converter notação de idioma, renumerar diagramas, buscar por posição.
- Permite testes de ida-e-volta objetivos (§11.3 do SPEC), que é como se prova que não
  há perda silenciosa.

### Consequências
- O IR precisa ser expressivo o suficiente desde o início; subestimá-lo é a maior
  ameaça ao projeto. Por isso F1 tem crítico dedicado à completude.
- Existe um `RawPassthrough` como escotilha de escape, mas seu uso é medido: um
  documento com muito passthrough indica lacuna no IR.

---

## ADR-0003 — Isolamento do ONNX Runtime em subprocesso

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
A GPU desta máquina é Blackwell (`sm_120`), que exige rodas PyTorch **cu128**.
A partir da versão 1.27, o pacote `onnxruntime-gpu` do PyPI é compilado contra
**CUDA 13.0**. Carregar os dois no mesmo processo produz conflito de DLL do CUDA
Runtime, ou — pior — fallback silencioso para CPU, que passa despercebido e destrói
o desempenho sem gerar erro.

### Opções consideradas
1. Só PyTorch (converter todo modelo ONNX para TorchScript).
2. Só ONNX Runtime (abandonar PyTorch em produção).
3. Fixar `onnxruntime-gpu` em uma versão cu12 antiga.
4. **Isolar o ONNX Runtime em um subprocesso separado.**

### Decisão
**Opção 4 como arquitetura, com opção 1 como padrão de execução.**

Concretamente:
- Os modelos próprios (detector, classificador de casas) são **PyTorch nativo**, e no
  processo principal só existe torch cu128. Este é o caminho quente e o padrão.
- Motores de terceiros que só existem em ONNX (certos modelos de OCR) rodam em um
  **processo trabalhador separado**, com seu próprio ambiente CUDA, comunicando-se por
  memória compartilhada. O conflito de DLL deixa de existir porque os dois runtimes
  nunca compartilham espaço de endereçamento.
- A camada `src/caissa/vision/runtime/` esconde essa distinção do resto do sistema.

### Consequências
- Custo de serialização entre processos, mitigado por memória compartilhada para tensores.
- `scripts/doctor.py` **precisa** validar a GPU com uma operação real, não apenas com
  `torch.cuda.is_available()`, justamente porque o modo de falha é silencioso.
- A opção 3 foi rejeitada porque fixar uma versão antiga significa perder correções e,
  eventualmente, quebrar quando outra dependência exigir versão nova.

---

## ADR-0004 — ModelResidencyManager para orçamento de VRAM

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
São 8 GB de VRAM no total, disputados por: detector de tabuleiro, classificador de
casas, um ou mais motores de OCR, e um LLM multimodal. A soma dos picos excede a
capacidade. Sem coordenação, o resultado é erro de falta de memória em meio a um lote
de 500 PDFs — a pior hora possível.

### Decisão
Um gerenciador central e único de residência de modelos, com:
- Registro declarativo do custo de VRAM de cada modelo.
- Carga sob demanda (nenhum modelo é carregado na inicialização).
- Despejo LRU quando o orçamento é excedido.
- Teto configurável, padrão **7,0 GB** (deixa margem para a composição do desktop).
- Fallback automático para CPU quando o despejo não é suficiente, com aviso ao usuário.
- Fila serializada para modelos que não cabem simultaneamente.

### Consequências
- Nenhum código de subsistema chama `.to("cuda")` diretamente. Isso é verificado por lint.
- O LLM (o maior consumidor) é o primeiro candidato a despejo.
- O portão F11 testa exatamente o cenário de pico simultâneo.

---

## ADR-0005 — Gemma 4 E4B como LLM primário

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
O pedido do usuário foi "Gemma 4 ou 8, o que meu PC suportar". A família Gemma 4
(Google DeepMind, abril de 2026) tem os tamanhos **E2B** (2,3 B efetivos), **E4B**
(4,5 B efetivos), **12B** (arquitetura unificada sem encoder, junho de 2026),
**26B A4B** (MoE, 25,2 B totais / 3,8 B ativos) e **31B** denso. Não existe um "Gemma 8".
Todos os tamanhos aceitam entrada multimodal de imagem; E2B e E4B aceitam áudio nativo.

### Decisão
**Gemma 4 E4B quantizado (Q4_K_M) é o padrão.** Gemma 4 12B é opção explícita de
"modo qualidade". Os tamanhos 26B e 31B ficam disponíveis apenas em modo lote com
descarregamento para RAM.

### Justificativa (orçamento medido)

| Modelo | VRAM aprox. (Q4) | Cabe com a pipeline de visão? | Papel |
|---|---|---|---|
| Gemma 4 E2B | ~1,8 GB | Sim, com folga larga | Máquinas fracas |
| **Gemma 4 E4B** | **~3,0–3,5 GB** | **Sim (restam ~3,5 GB)** | **Padrão** |
| Gemma 4 12B | ~7,5 GB | Não simultaneamente | Modo qualidade, serializado |
| Gemma 4 26B A4B | ~15 GB | Não | Lote, offload para os 31,6 GB de RAM |
| Gemma 4 31B | ~18 GB | Não | Fora do alvo |

E4B é a escolha porque é o maior modelo que **coexiste** com o detector e o
classificador sem forçar descarregamento a cada diagrama — e o LLM aqui é auxiliar, não
o motor principal de reconhecimento. Precisão de reconhecimento vem da pipeline de visão
dedicada (§6), que é mais precisa e ordens de magnitude mais rápida que um VLM genérico
para esta tarefa.

### Consequências
- O LLM é sempre **opcional**. A aplicação inteira funciona sem ele (portão F11).
- Pesos ficam fora do instalador (restrição de disco R4).

---

## ADR-0006 — Detecção híbrida de tabuleiro

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
O acervo do usuário mistura PDFs vetoriais nativos (onde o diagrama é desenho vetorial
ou glifos de fonte de xadrez) com digitalizações de qualidade muito variável. Usar uma
rede neural em tudo é desperdício em ~70 % dos casos e **menos preciso** onde a
informação exata já está no arquivo.

### Decisão
Três vias em cascata por custo — vetorial, geométrica, neural — com um árbitro
(detalhado no §6.1 do SPEC).

### Justificativa
- A via vetorial atinge **100 %** de acurácia quando a fonte de xadrez é identificada,
  porque lê a posição diretamente dos glifos, sem inferência. Nenhum concorrente baseado
  em raster consegue igualar isso, e é o nosso diferencial mais forte em PDFs de editora.
- A via geométrica cobre digitalizações limpas a custo baixo.
- A via neural existe para o que sobra: torto, ruidoso, fotografado, com sobreposição.

### Consequências
- Manter um catálogo de métricas de fontes de xadrez (mapeamento glifo para peça) por
  família. Isso é dado, não código, e cresce com o tempo.
- O árbitro registra discordâncias entre vias para alimentar o corpus de treino.

---

## ADR-0007 — SQLite com FTS5 para o índice

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
O usuário tem bases PGN de dezenas de GB e milhares de PDFs. Precisa de busca textual,
por regex e por posição, em uma aplicação desktop sem servidor.

### Decisão
SQLite com FTS5 (tokenizador customizado para notação) e um índice posicional por hash
Zobrist. Sem servidor, arquivo único por biblioteca, indexação incremental.

### Justificativa
- Zero configuração e zero processo extra — requisito do perfil "não é programador".
- FTS5 é maduro e rápido o bastante para a escala descrita.
- O hash Zobrist transforma busca por posição em busca por inteiro de 64 bits, indexável
  em B-tree comum. É o que as bases comerciais fazem.
- Alternativas (Postgres, Elasticsearch, Lucene) exigem serviço em execução — inaceitável.

### Consequências
- Escrita concorrente exige cuidado (modo WAL, um escritor).
- O tokenizador customizado precisa ser escrito e testado com cuidado: é ele que faz
  `O-O-O` e `Nf3` serem pesquisáveis como tokens únicos.

---

## ADR-0008 — Correção de notação guiada por gramática e legalidade

**Status:** Aceita · **Data:** 2026-09-07

### Contexto
OCR genérico erra sistematicamente em notação de xadrez: confunde `l`/`1`/`I`,
`0`/`O`, `5`/`S`, `8`/`B`, perde os símbolos `+` e `#`, e não conhece as convenções de
idioma (`Cf3` em português é `Nf3` em inglês).

### Decisão
Tratar notação como **linguagem formal**: analisador PEG multilíngue, seguido de
validação e correção contra as regras do xadrez usando `python-chess`, a partir da
posição corrente.

### Justificativa
É o maior ganho isolado de precisão disponível no projeto, e é essencialmente gratuito
em custo computacional. O espaço de lances legais em uma posição típica tem algumas
dezenas de elementos; um candidato ilegal com uma substituição de caractere de distância
de um único lance legal é, com altíssima probabilidade, aquele lance. A verificação de
consistência ao longo da partida inteira torna o resultado praticamente certo.

### Consequências
- Depende de conhecer a posição inicial do bloco de lances, o que nem sempre é dado.
  Mitigação: tentar a posição inicial padrão e, se falhar, as posições de diagramas
  próximos na página.
- Precisa de tabelas de idioma por peça, mantidas como dado.

---

## ADR-0009 — PyQt6 como toolkit (substitui a ADR-0001)

**Status:** Aceita · **Data:** 2026-09-07 · **Substitui:** ADR-0001

### Contexto
A ADR-0001 escolheu PySide6 supondo que a base existente era Tkinter e que qualquer
caminho exigiria reescrita da UI. O inventário completo (`docs/ASSETS.md` v2.0) mostrou
que a premissa era falsa. A distribuição real de código de interface é:

| Projeto | Toolkit | Linhas de UI |
|---|---|---|
| ChessVisionOFF_Puro | PyQt6 | ~14.000 |
| PGN_Live_Editor | PyQt6 | 5.619 |
| Editor_Diagramas_de_Xadrez | PySide6 | ~7.000 |
| PDFimport | PySide6 | 332 |

Total: **~19.600 linhas em PyQt6** contra **~7.300 em PySide6**.

### Decisão
**PyQt6**, com a disciplina de camada `ui/` livre de toolkit mantida e verificada.

### Justificativa
- Portar a minoria custa menos de um terço do que portar a maioria.
- O tronco (ChessVisionOFF_Puro) já separa decisão de pintura: 53 módulos em `ui/`
  (~13.000 linhas) não importam toolkit nenhum, e `qt/` apenas desenha o que `ui/`
  decidiu. Essa disciplina é o que torna a escolha reversível — e é também o que já
  permite 4.412 testes rodarem sem abrir janela.
- Qt6 atende os requisitos técnicos (pan/zoom acelerado, SVG, temas) de forma idêntica
  nos dois bindings. A escolha é econômica, não técnica.

### Consequências — dita com todas as letras
- **PyQt6 é GPL.** Para uso próprio e para distribuição sob GPL, não há impedimento.
  Distribuir um binário de código fechado exigiria licença comercial da Riverbank
  **ou** a migração para PySide6 (LGPL).
- A migração continua viável: `pyqtSignal` → `Signal`, `pyqtSlot` → `Slot`, e os enums
  já são escopados nos dois. A disciplina `ui/` mantém a porta aberta, e um teste de
  arquitetura deve verificá-la (nenhum import de toolkit dentro de `ui/`).
- Se o usuário decidir distribuir comercialmente, esta ADR é revisitada com um plano de
  migração — não é uma decisão irreversível.

---

## ADR-0010 — O Editor HTML/CSS é uma vista-fonte do IR para a estrutura; o CSS é recurso verbatim

**Status:** Aceita (Q0, 2026-09-24) · **Data:** 2026-09-24 · **Origem:** `EDITOR_HTML_CSS_SPEC.md` D1

### Contexto
A ADR-0002 exige que toda saída saia do IR. O EPUB já nasce de um motor HTML ida-e-volta, mas em
marcação de máquina (`data-ir` por corrida, classes geradas). O CSS de um livro — cascata,
seletores, `@media`, `@page`, variáveis, `@font-face` — não tem representação no IR: o
`StyleSheet` guarda estilos nomeados estruturados, não regras CSS.

### Decisão
- **Estrutura.** O projeto guarda os XHTML que o usuário edita, byte a byte. O motor HTML ganha o
  **perfil legível** e o leitor dele: gerar é IR → XHTML legível; exportar é XHTML → IR →
  exportadores. A marcação fora do contrato é preservada: elemento → `RawPassthrough`/`RawInline`;
  atributo → `IRNode.html_attributes` (esquema v2, migração v1→v2).
- **CSS.** As folhas do projeto são `Resource(kind=STYLESHEET)`, **não interpretadas** pelo IR. O
  EPUB e o HTML as levam byte a byte; o PDF é a impressão do HTML exportado pelo motor da prévia
  Página; o DOCX aplica um **mapa de estilo** fechado e avisa o resto regra a regra; o LaTeX recebe
  a estrutura e um aviso único.

### Alternativas rejeitadas
HTML como verdade independente (o Sigil: fura a ADR-0002, o DOCX ignoraria as edições); traduzir
todo o CSS para o IR (o IR viraria um motor de CSS); o perfil de máquina atual (ilegível).

### Consequências
A ida e volta da estrutura é portão (roadmap H5); o mapa de estilo tem portão positivo e negativo
(H5, H24); o PDF tem portão de igualdade com a prévia, e o LaTeX, do aviso único (H24). Arquivo mal
formado não vai ao IR: grava o texto e mostra o erro.

**Reverte se:** o H5 provar que a estrutura não fecha a ida e volta sem perda fora das
normalizações declaradas (N1–N4).

---

## ADR-0011 — Um vocabulário de marcação só: o contrato `cb-*`

**Status:** Aceita (Q0 e Q3, 2026-09-24) · **Data:** 2026-09-24 · **Origem:** spec D2

### Contexto
Há três vocabulários para a mesma coisa: o do `export/html.py`, o `MARKUP` do fork ChessBook do
Sigil e o do renderizador do CB. O CB tem nove temas de CSS, um validador com linha e um
renderizador, todos em `cb-*`, e o contrato é do próprio usuário, congelado por política escrita.

### Decisão
O **Contrato de Marcação do Caissa v1** (`docs/MARKUP_CAISSA.md`, roadmap H3) é o `MARKUP` inteiro
mais as extensões da spec S4, pela política dele. Todo o resto é HTML semântico padrão. O leitor lê
o contrato **e** o legado `data-ir`. O usuário respondeu «sim» ao Q3 em 2026-09-24.

### Alternativas rejeitadas
Manter o vocabulário do `html.py` (não tem classe semântica); inventar um quarto.

### Consequências
Os temas e as regras do CB são absorvidos para a suíte, com cabeçalho «Origem:» e GPLv3. Portão de
interoperabilidade: o validador do CB aceita o EPUB do projeto (H3, H5).

**Reverte se:** o contrato `cb-*` for abandonado pelo usuário (uma resposta nova ao Q3).

---

## ADR-0012 — Dois motores de pré-visualização; o Chromium só com prova de pacote

**Status:** Aceita (Q0, 2026-09-24) · **Data:** 2026-09-24 · **Origem:** spec D3

### Contexto
Não há QtWebEngine. Somá-lo ao instalador custa cerca de 207 MB descomprimidos (extrapolado) e
ameaça o teto de 150 MB; em `runtime/` ele escaparia da medida do pacote. O MuPDF `Story` já está
no pacote e mediu 89 ms para 17 páginas, mas desenha um subconjunto do CSS.

### Decisão
A interface `MotorDePrevia` (sem Qt) tem duas implementações:
1. **MuPDF**, embutido e sempre presente: o modo Página e a reserva do modo Leitor.
2. **Chromium**, componente opcional «Pré-visualização de alta fidelidade»: o modo Leitor, o
   inspetor de estilos calculados, o escuro do leitor e a impressão.

O Chromium só vira padrão se o roadmap H1 provar, com números: uma sonda PyInstaller real,
nesta máquina e numa máquina limpa; frio ≤ 1,5 s; remendo p95 ≤ 150 ms em 260 KB; livro hostil
com 0 requisições e 0 scripts; memória extra ≤ 350 MB; download ≤ 150 MB e instalado ≤ 300 MB,
publicados; instalação atômica, por pasta, sem rede, e remoção que volta ao MuPDF. O manifesto do
componente (nomes, versões, SHA-256) viaja dentro do instalador, que é a raiz de confiança: a roda
com hash diferente é recusada, revogar uma versão é um instalador novo com outro manifesto, e o
editor recusa carregar componente cuja versão não bata com a do PyQt6 do pacote.

### Alternativas rejeitadas
`QTextBrowser` (não desenha CSS de livro); WebView2 (as razões do S-69); QtWebEngine no instalador
(fura o teto, a menos que o usuário o mude — Q2); só Chromium (o editor ficaria inútil até o
download).

### Consequências
Sem o Chromium, a janela diz num rótulo desenhado que a pré-visualização é a simplificada. O
validador marca a propriedade CSS que o motor ativo não desenha (a matriz do H1).

**Reverte se:** o H1 reprovar a sonda — o Q2 volta ao usuário com os números: embutir e subir o
teto, ou ficar só com o MuPDF.

---

## ADR-0013 — Editor de código nativo, provisório até o H2

**Status:** Aceita, provisória (Q0, 2026-09-24) · **Data:** 2026-09-24 · **Origem:** spec D4

### Contexto
O QScintilla não está instalado. O CodeMirror dependeria do Chromium opcional e seria opaco aos
portões. O `QPlainTextEdit` expõe a interface de texto acessível do Qt (UIA no Windows), os portões
o leem, e o Qt Creator e o Spyder mostram que ele chega a editor profissional — mas isso não está
provado aqui.

### Decisão
`EditorDeCodigo(QPlainTextEdit)` com as funções da spec S5. O roadmap H2 constrói um protótipo com
**todas as funções ligadas ao mesmo tempo** (realce, margem, dobras, indicadores, completar, par de
tags, desfazer, escala e prévia no processo de trabalho), mede o orçamento completo, prova a
leitura por UIA e ≥ 5 casos dourados por função. O H2b mede o QScintilla no mesmo arnês, antes de a
dependência entrar, se o H2 reprovar ou o H12 reprovar por limite do componente. Cursores
múltiplos ficam fora da v1.

### Consequências
A regra do editor (léxico, estrutura, operações) mora em `caissa/editor/`, sem toolkit, e sobrevive
a uma troca de componente.

**Reverte se:** o H2 reprovar, ou o H12 reprovar por limite do componente.

---

## ADR-0014 — Janela de primeiro nível, casca injetada, rota de teclas por janela ativa

**Status:** Aceita (Q0, 2026-09-24) · **Data:** 2026-09-24 · **Origem:** spec D5

### Contexto
Um editor com docas e menus pede `QMainWindow`. O tronco só trata `QDialog`, `janela.py` não tem
linha livre, e a guarda de teclas é global.

### Decisão
- **A suíte.** `JanelaDoEditorHtml(QMainWindow)` recebe uma **casca** (protocolo sem Qt no tipo) com
  tema e pele, acessibilidade e escala, dono das teclas, estado, fábrica do visor de PDF, editor de
  posição, mostrar na principal e o serviço de decisões.
- **O tronco.** Implementa a casca e a aba lançadora; estende o filtro de acessibilidade às
  janelas secundárias; reescreve a rota da guarda de teclas pela **janela ativa** (pop-up, campo de
  texto com AltGr e tecla morta, a janela do editor executa a ação dela, a principal como hoje).
- Os portões ganham `--janela editor`. A aba, ao ser ativada, abre ou traz à frente a janela; uma
  preferência desliga isso. **Um livro por janela:** abrir o mesmo livro de novo traz a janela
  existente à frente.

### Alternativas rejeitadas
`QDialog` não modal (`Esc` fecha e não há docas); um modo dentro da aba Livro (1250×640 não cabe
três painéis); a janela no tronco (a regra de documento iria para o Python 3.10).

**Reverte se:** o H11 mostrar que estender os portões custa mais que um `QDialog` com
`QMainWindow` embutido.
