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
