# Roadmap — Editor HTML/CSS

> **Data:** 2026-09-24 · **Versão:** 1.17 — **APROVADA pelo Codex no ciclo 18**. A 1.10 tinha sido
> aprovada no ciclo 11. A 1.11 registrou as respostas do usuário:
> - **Q1 = C**, a combinação guiada por medição: o H0 mede, o H0b combina, o H26 unifica a aba Texto;
> - **Q7 = (i)**, altíssimo padrão.
>
> Os ciclos 12 a 17 reprovaram o H0b e o H26 novos (spec §9).
> **Contrato:** `EDITOR_HTML_CSS_SPEC.md` — cada passo cita a cláusula que o governa.
> **Críticas:** `quality/EDITOR_HTML_CSS_CRITICAS.md`. **Relatório do construtor:**
> `quality/EDITOR_HTML_CSS_REPORT.md` — criado pelo H0; uma seção por passo, todo número com o
> comando ao lado.
>
> **Formato:** plano de construção por passos (blueprint). Cada passo é autocontido: um construtor
> que chegue frio executa o passo lendo só o **briefing** dele e os arquivos que ele nomeia. Cada
> passo traz:
> - objetivo e cláusula da spec;
> - arquivos e briefing;
> - tarefas;
> - portão **positivo** (casos esperados, não só ausência de erro) e **sabotagem que reprova de
>   verdade**;
> - saída, nível de modelo e como desfazer.
>
> As dependências estão **só** na tabela do §1.
>
> **Modo de trabalho:**
> - Direto em `main`, commits por caminho nomeado.
> - Tronco e suíte são repositórios distintos: um commit em cada, com o hash do outro na mensagem.
> - O H11 (rota de teclas da janela principal) vai em ramo próprio do tronco, fundido só com os
>   portões verdes, como o passo 17 do ciclo 1.
>
> Abreviações da spec: **T** (tronco), **S** (`src\caissa\`), **CB** (`sigil_chess`), **A**
> (`S\ui\audit\`).

---

## 0. Pré-voo e regras

### 0.1 Estado verificado em 2026-09-23

| verificação | resultado |
|---|---|
| repositórios | suíte em `main`, HEAD **no momento da escrita** `99546e9` (a fase 5 do ciclo 2 foi commitada **durante** esta sessão: `f9ca678` → `bb41c55` → `99546e9`), `origin` = `github.com/DarcioAlberico/Suite_de_Edicao_de_Xadrez`, `gh` autenticado; tronco no ramo `religa-as-decisoes-orfas`, HEAD `8243e90` |
| trabalho alheio no checkout | **suíte:** ainda sujos `docs/OCR_UI_ROADMAP_C2.md`, `docs/quality/OCR_UI_REPORT_C2_FASE5.md`, `packaging/*` e `uv.lock`. **Tronco:** a mudança da digitação da aba Texto sem commit (`qt/painel_de_texto.py`, `text/rico.py`, `ui/texto_declarado.py`, `qt/janela.py`, dois testes novos). Nenhum passo deste roadmap toca esses caminhos enquanto estiverem sujos (a barreira do §0.3) |
| `janela.py` | 2.077 linhas no HEAD = `LIMITE` (`wc -l`, ou `.Count` no PowerShell; **nunca** `Measure-Object -Line`, que pula as vazias e dá 1.808); a árvore oscilou entre 2.080 e 2.077 durante a sessão |
| planos anteriores no mesmo tema | `..\Plugins_Sigil_Edit\` (plano de plugins, não executado); `..\Sigil-master\chessbook\` (contrato `cb-*`; 15 testes no cache de reprovados, não reexecutados). Este roadmap **absorve** o que eles têm de reutilizável |
| ambiente | `.venv` (3.11, pytest, sem PyQt6), `.venv-pack` (3.11, PyQt6 6.11 / Qt 6.11.2, sem pytest), tronco `.venv` (3.10, PyQt6 6.11); **nenhum** tem QtWebEngine ou QScintilla; Java 8, Node v25.9.0; **Windows Sandbox não habilitado** |
| o livro do pedido | `A Matter of Endgame Technique – Jacob Aagaard.pdf`, página 55 do PDF (fólio impresso «54»), 898 páginas, camada de texto com a notação cifrada (`&` = rei) |

### 0.2 Comandos executáveis

Todos os comandos são **PowerShell**, a partir da raiz da suíte. O H0 cria dois arquivos
versionados:
- `benchmarks\editor_ambiente.ps1`: variáveis e o ambiente dos portões;
- `benchmarks\editor_portoes.py`: o executor único de portões.

**Antes do H0, nenhum portão deste roadmap roda** — é de propósito: o executor é o primeiro
instrumento.

```powershell
. .\benchmarks\editor_ambiente.ps1
#   $PY   = .venv\Scripts\python.exe                         (suíte, pytest)
#   $PACK = .venv-pack\Scripts\python.exe                    (PyQt6/PyMuPDF do pacote)
#   $PYQ  = ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe  (tronco)
#   $env:QT_QPA_PLATFORM = "offscreen"; $env:QT_QPA_FONTDIR = "C:\Windows\Fonts"
#   Enter-AmbienteDosPortoes  → $env:PYTHONPATH = "src;..\ChessVisionOFF_Puro\src;.venv-pack\Lib\site-packages"
#   Enter-AmbienteDosTestesQt → $env:PYTHONPATH = ".venv-pack\Lib\site-packages"
#   $PEDIDO = "..\ChessVisionOFF_Puro\PDF\A Matter of Endgame Technique – Jacob Aagaard.pdf"   (p. 55; 898 p.)
#   $LIVRO  = "..\ChessVisionOFF_Puro\PDF\AAGAARD - Practical Chess Defence.pdf"              (p. 31–38)
#   $KEMERI = "..\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf"                                    (p. 80)
#   $DEM    = "..\ChessVisionOFF_Puro\PDF\Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf"  (nativo)

& $PY benchmarks\editor_portoes.py --passo H5 --saida benchmarks\reports\editor\h5
```

**O executor de portões** (`editor_portoes.py`) tem uma tabela: para cada passo, os instrumentos,
os comandos do portão, as sabotagens e as repetições. Para o passo pedido, ele:
1. confere que todo instrumento e toda fixture existem, senão **REPROVA** «instrumento ausente»;
2. roda o portão (3× quando há tempo ou aleatoriedade) e exige PASSOU em todas as execuções;
3. roda **cada** sabotagem e exige que ela REPROVE, senão **REPROVA** «sabotagem inócua»;
4. grava `portao.json`, com o HEAD dos dois repositórios, a marca de árvore suja, as medianas e as
   saídas.

O comando de portão de cada passo abaixo é a entrada que o passo acrescenta nessa tabela.

### 0.3 Regras que valem para todos os passos

- **Barreira de árvore.** Antes de começar, o construtor roda
  `git status --porcelain -- <arquivos do passo>` nos dois repositórios.
  - Caminho sujo que não é deste passo → **o passo espera ou coordena**; não edita por cima (lição
    de `concurrent-sessions-same-repo`).
  - O commit leva só os caminhos do passo.
- **Portão novo só com sabotagem executada** e registrada.
  - O arnês tem `--saida` obrigatório e grava só em `benchmarks\reports\editor\` ou numa pasta
    temporária — nunca em `labeling\`, `data\` ou `editor\` do usuário (`capture.estado_de_medicao`).
  - Não importa Qt no topo do módulo (`tests/unit/ui/test_arquitetura.py:188-208`).
- **Número com comando**, com mediana de 3 onde há tempo ou aleatoriedade e semente fixa (42)
  onde há sorteio. Benchmark e testes **em sequência**, nunca em paralelo.
- **S `editor/` é sem Qt**; a pintura mora em S `ui/views/editor_html/` e `ui/widgets/`.
- **O editor não faz `janela.py` crescer** (R1.12): o total de linhas depois do passo é ≤ o de
  antes, com `(Get-Content <arquivo>).Count` antes e depois do passo. Uma linha trocada vale; uma a
  mais, não.
- **Toda cor nova é papel de token** do tronco, com par declarado. **Toda tecla nova mora numa
  tabela:** T `ui/atalhos.py` para a principal, S `editor/comandos.py` para o editor.
- **Toda fixture que imita dado do produto cita a função do produto que ela imita.** O sidecar
  passava no teste com tupla onde o produto usa `Rect` (spec §2.7).
- **Portão positivo.** Todo portão tem casos com **resultado esperado** — contagem, texto ou hash
  — e uma sabotagem do tipo «a implementação nula» (não faz nada) que reprova.

**Invariantes depois de todo passo:**

```powershell
. .\benchmarks\editor_ambiente.ps1; Enter-AmbienteDosTestesQt
& $PY -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py
& $PY -m pytest tests\unit\model\test_roundtrip_corpus.py -q -p no:cacheprovider
& $PYQ -m pytest ..\ChessVisionOFF_Puro\tests -q -o faulthandler_timeout=300      # quando o passo toca o tronco
& $PY benchmarks\editor_portoes.py --passo <Hn> --saida benchmarks\reports\editor\<hn>
git status --short; git -C ..\ChessVisionOFF_Puro status --short                   # só os caminhos do passo
```

---

## 1. Dependências — a tabela é a fonte única

| passo | depende de | decisão do usuário | libera |
|---|---|---|---|
A coluna «depende de» lista **tudo o que o passo usa**: código, artefato ou corpus. Um passo que
usa o projeto gerado de um livro real depende do H8. Um que usa a matriz de CSS depende do H1.

| passo | depende de | decisão ou ação do usuário | libera |
|---|---|---|---|
| **H0** executor de portões + medição dos leitores (Q1 = C) | — | — | todos; os números do leitor da aba contra a fusão e a margem do oráculo (entrada do H0b) |
| **H0b** a combinação: o candidato de glifo com o que a aba faz de diferente, e o RapidOCR fora da página degradada; uma configuração global, escolhida em `dev` + `calib` e confirmada uma vez na cega; e o veredito da aba por estrato | H0 | a troca precisão × tempo, **só** se a configuração que ganha passar de 2 × o tempo por página; rotular mais verdade nativa, **só** se o estrato nativo ficar sem evidência | H8, H26 |
| **H1** motores de pré-visualização (+ sonda PyInstaller, máquina limpa) | H0 | consentir o download das rodas; habilitar o Sandbox ou dar uma VM | H10 (matriz), H13, H14 |
| **H2** editor de código com tudo ligado (projeto sintético de 300 capítulos) | H0 | consentir `pywinauto` (medição) | H12 (ou H2b) |
| **H2b** QScintilla (só se o H2 reprovar, ou o H12 reprovar por limite do componente) | H2 reprovado, ou H12 reprovado por limite do componente | consentir a dependência | H12 |
| **H3** contrato de marcação + política de CSS + fixtures douradas do sidecar (escritas pelo crítico) | H0 | — | H5, H10, H19, H24 |
| **H4** dívidas da exportação (inclui o alt descritivo) | H0 | — | H5, H10 |
| **H5** perfil legível + `html_attributes` + CSS como recurso + mapa de estilo | H3, H4 | **Q3**; consentir `tinycss2`/`cssselect2` no `.venv-pack` | H8, H9, H10, H19, H23, H24 |
| **H6** projeto em disco | H0 | Q4 (tem padrão) | H8, H11, H17, H25 |
| **H7** serviço único de decisões | H0 | — | H8, H16, H22, H25 |
| **H8** geração a partir do OCR (projetos reais; a fusão do produto) | H0b, H5, H6, H7 | — (Q1 respondida: C) | H9, H13, H15, H16, H18, H19, H21, H22, H23, H24, H25, H26 |
| **H9** mapa de fontes e sincronia (usa o `proveniencia.json` do H8) | H5, H8 | — | H13, H15, H16 |
| **H10** validação em camadas (corpus limpo = saídas do H5) | H1, H3, H4, H5 | — | H12, H23, H24 |
| **H11** aba, janela, casca, rota de teclas, portões estendidos (projeto de fixture) | H6 | — | H12, H13, H15, H17 |
| **H12** editor de código (v1; projeto sintético do H2) | H2 (ou H2b), H10, H11 | — | H17, H18, H19, H20 |
| **H13** Resultado MuPDF (projetos do H8) | H1, H8, H9, H11 | — | H14, H22, H23, H24 |
| **H14** Resultado Chromium (componente) | H1, H13 | **Q2** | H27 |
| **H15** PDF original + Comparar (projetos do H8) | H8, H9, H11 | — | H16, H22 |
| **H16** revisão do OCR no editor | H7, H8, H15 | — | H25 |
| **H17** nada se perde, na janela | H6, H11, H12 | — | — |
| **H18** estrutura HTML + arquivos do livro (amostra nos projetos do H8) | H8, H12 | — | H21, H23 |
| **H19** CSS, temas, fontes (mapa do H5; `LIVRO` do H8; o Chromium de medição do H1 para o foco) | H1, H3, H5, H8, H12 | Q6 (Q7 respondida: i) | H24 |
| **H20** localizar e substituir, recortes, paleta (livro de fixture + projeto sintético do H2) | H12 | — | — |
| **H21** tipografia (`PEDIDO` p. 55 do H8) | H8, H18 | — | — |
| **H22** diagramas | H7, H8, H13, H15 | — | H24, H25 |
| **H23** lances e notação (figurina medida na página do MuPDF) | H5, H8, H10, H13, H18 | — | H24 |
| **H24** exportar do projeto + acessibilidade do EPUB (PDF pelo motor da prévia; avisos pela matriz do H1; fixtures douradas do sidecar do H3) | H1, H3, H5, H8, H10, H13, H19, H22, H23 | **Q5**; consentir o Ace (npm) (Q7 respondida: i) | H27 |
| **H25** regerar e fundir (3 vias) | H6, H8, H16, H22 | — | — |
| **H26** a aba Texto lê pelo produto e leva a formatação e os diagramas ao editor | H0b, H8; a mudança da digitação **commitada** | — (Q1 respondida: C) | — |
| **H27** (opcional) PDF pelo Chromium, abrir EPUB do Caissa/CB | H14, H24 | — | — |

- **Paralelos sem conflito de arquivo:**
  - H0b ∥ H1 ∥ H2 ∥ H3 ∥ H4 ∥ H6 ∥ H7, depois do H0 (o H0b só toca `ocr/engines/glyph.py`,
    `ingest/pdf/ocr_service.py` e os testes dele; nenhum outro passo toca esses arquivos);
  - H10 ∥ H8, depois do H5;
  - H9 depois do H8;
  - H13 ∥ H15, depois do H11 e do H9;
  - H17 ∥ H18 ∥ H19 ∥ H20, depois do H12;
  - H22 ∥ H23.
- **Ordem nos arquivos partilhados.** Derivada da tabela; quem entra depois rebaseia:
  - S `export/html.py`: H4 → H5 → H23 → H24;
  - S `ingest/pdf/importer.py`: H4 → H8;
  - S `export/epub.py`: H4 → H24;
  - S `ocr/review.py`, `ocr/diagram_decisions.py`, `ui/views/revisao_de_texto.py`, T
    `qt/decisoes_de_diagrama.py`: só o H7;
  - T `qt/atalhos.py`, `qt/acessibilidade.py`, `ui/state.py`, `ui/abas.py`, `ui/comandos.py`: só o
    H11;
  - T `qt/visor.py`: só o H15;
  - T `ui/tokens.py`: H12 → H15;
  - `A/teclado|texto_pintado|comandos|minimo|bloqueio|capture.py`: H11 → H12;
  - `A/percurso.py`: H16 → H17 → H22 → H24;
  - `packaging/*`: H6 → H14 → H19 → H24.
- **Nível de modelo:**
  - **forte**: H3, H5, H7, H8, H9, H11, H14, H24, H25;
  - **padrão** nos demais.

---

## 2. Fase 0 — medir e fixar antes de construir

### H0 — O executor de portões, o relatório, e os leitores medidos

- **Governa:** spec R1.1, R1.2, Q1 (respondida em 2026-09-24: C, a combinação guiada por medição).
- **Arquivos:**
  - `benchmarks/editor_ambiente.ps1`, `benchmarks/editor_portoes.py`, `tests/unit/editor/test_portoes.py`;
  - `benchmarks/editor_leitores.py` (novo);
  - `docs/quality/EDITOR_HTML_CSS_REPORT.md` (novo, §H0).
- **Briefing.**
  - O crítico reprovou os aliases de pseudocomando e os portões sem instrumento. Este passo cria o
    **único** caminho de execução de portões (§0.2) e faz ele reprovar quando o instrumento falta
    ou a sabotagem não morde.
  - A segunda metade **mede** o leitor da aba Texto contra a fusão que alimenta o editor. O
    usuário decidiu pelo mais preciso, ou pela combinação dos leitores (spec Q1 = C), e o H0b
    combina a partir destes números.
    - A aba Texto lê com `text.leitor.ler_pagina` (tronco, Python 3.10), com os motores `glifo` (o
      padrão) e `camada`, e o modo bloco.
    - O produto lê com a fusão do `import_pdf` (suíte, 3.11).
    - Os dois nunca foram comparados nas mesmas páginas.
    - `editor_leitores.py` roda cada um no seu ambiente (dois subprocessos, JSON), sobre as
      mesmas páginas.
    - **O conjunto com verdade** é o manifesto dourado (`benchmarks\corpus\golden\manifest.private.json`,
      gitignored, na máquina), partições `dev` e `calib` — a `blind` fica fora (R1.4 herdada).
      Contado em 2026-09-23:
      - SFC4 digitalizado: 13 páginas, 123 + 72 = 195 regiões;
      - Seirawan «Xadrez Vitorioso — Finais», nativo: 18 + 11 = 29 regiões;
      - as demais com 1–3 regiões.
    - O casamento leitor × região é por IoU ≥ 0,5 dos retângulos, **na mesma unidade**:
      - o leitor da aba dá a `PaginaLida` em pontos PDF. As linhas internas (`_Cru`) são pixels,
        e o `montar` converte cada uma por `_para_pontos` (T `text/leitor.py:660-668, 1060`);
      - o produto dá as regiões em pixels da página renderizada (`RegionRecognition.box_px`,
        `ocr_service.py:340`), e o instrumento as passa a pontos com o `dpi` da renderização;
      - a conversão acontece **uma vez**, e uma fixture de coordenadas conhecidas prova isso: dois
        retângulos de texto, em linhas diferentes, num PDF sintético, lidos pelos dois, cada um
        com IoU ≥ 0,9 contra a verdade.
    - **Sem verdade**, para o contexto: `PEDIDO` p. 50–60 e `LIVRO` p. 31–38. Ali se mede a taxa de
      discordância por caractere, figurinas, diagramas (com FEN ou não) e o tempo por página.
    - **O que a medição publica** (a entrada do H0b). Por estrato *s* — digitalizado e nativo, o
      `Source.PDF_SCAN` e o `Source.PDF_NATIVE` do manifesto (`ocr/golden.py:68-74`) — e por
      métrica, sobre as mesmas regiões, com intervalo de 95 % por reamostragem das regiões (1.000
      reamostras, semente 42).
      - **As métricas:**
        - **CER**;
        - **lances certos** e **lances inventados**, pelo `move_accounting` de S `ocr/metrics.py`
          (a régua do `bench_sol`);
        - **figurinas certas**: dos lances da verdade que levam figurina, a fração lida com a
          figurina certa, contada pelo mesmo `move_tokens`;
        - **ordem de leitura**: `reading_order_accuracy` de S `ocr/metrics.py:239-250`, sobre a
          ordem das regiões casadas de cada página, a mesma régua do `sol_gate`.

        São as métricas do veredito da aba no H0b, e o H0 as publica para todos os leitores e
        modos, por estrato, com intervalo.

        **São campos obrigatórios.** Cada uma das cinco métricas (CER, lances certos, lances
        inventados, figurinas certas e ordem de leitura) vem com valor e intervalo para cada
        leitor, modo e estrato.
        - Se qualquer uma faltar ou vier nula, o `editor_portoes.py` reprova «métrica ausente».
        - O `sol_gate` faz o contrário com a ordem: pula o portão quando ela falta
          (`gates.py:282-288`). Por isso a regra fica escrita aqui.
        - A **precisão de regiões** (casadas ÷ lidas) sai ao lado da ordem, porque a régua da ordem
          (LCS sobre a verdade) não vê região a mais. Ela é publicada e não entra no veredito.
      - **Os leitores:**
        - a fusão do produto;
        - o leitor da aba em três modos: `glifo`, `glifo` com o modo bloco, e `camada`.
      - **As diferenças** de cada modo contra a fusão, com intervalo.
      - **A margem do oráculo:** a métrica se cada região ficasse com a melhor leitura entre a fusão
        e o leitor da aba. É o teto do que a combinação pode ganhar.
      - O **hash do manifesto** (o que o `bench_sol` imprime) e a lista de regiões usadas.

      Nada aqui decide: o H0b mede a combinação e liga só o que provar ganho.
- **Tarefas.**
  - O executor com a tabela (vazia além do H0) e o teste dele.
  - O script de ambiente.
  - A medição dos leitores, 3×.
  - O relatório com as duas seções.
- **Portão** (`& $PY benchmarks\editor_portoes.py --passo H0 --saida benchmarks\reports\editor\h0`):
  - `test_portoes.py` com três passos falsos:
    - instrumento ausente → REPROVA «instrumento ausente»;
    - sabotagem que passa → REPROVA «sabotagem inócua»;
    - passo bom → PASSOU.
  - `editor_leitores.py` (3 execuções):
    - **denominador mínimo:** ≥ 150 regiões casadas com verdade, de ≥ 2 livros, com ao menos 1
      digitalizado e 1 nativo. Com menos (manifesto ausente, vazio ou casamento pobre), o
      instrumento **REPROVA** «verdade insuficiente», e não publica números;
    - publica, por estrato e métrica: as regiões; os números de cada leitor e modo; as diferenças
      com intervalo; a margem do oráculo; e o tempo por página;
    - publica o resultado **por região e por página** (JSON), que o H0b usa na reamostragem por
      página e no veredito da aba.
- **Sabotagem.** As três têm de reprovar:
  - `editor_portoes.py --sabotar aceita_sem_instrumento` (desliga a conferência): o teste do passo
    falso «instrumento ausente» passa a PASSOU, e o `test_portoes` reprova;
  - `editor_leitores.py --sabotar so_uma_pagina` (limita a verdade a uma página): o instrumento
    reprova «verdade insuficiente»;
  - `editor_leitores.py --sabotar sem_ordem` (o JSON sai sem a ordem de leitura de um modo do
    leitor da aba): o portão reprova «métrica ausente».
- **Saída:** o executor que todos os passos usam; os números do leitor da aba contra a fusão, que
  o H0b usa.
- **Nível:** padrão.
- **Desfazer:** apagar os três arquivos; nada no produto muda.

### H0b — A combinação: o que o leitor da aba Texto faz de diferente entra na fusão, se ganhar

- **Governa:** spec Q1 (C), R1.1, R1.2, R1.4, R1.5; a fusão geométrica por token do `Sol.md`
  §SOL-6, com o critério de aceite dela. **Depende de:** H0.
- **O que já está na fusão** (lido no código em 2026-09-24):
  - o classificador de glifos do tronco **já é candidato** (S `ocr/engines/glyph.py`, pela ponte
    `vision/classify/cvoff.py`), com a cadeia de página do tronco (`segmentar` →
    `linhas_do_glifo`), uma caixa por glifo e `secondary=True`. Mas há duas limitações:
    - ele só é consultado em região que é, parece ou carrega lance (`ocr_service.py:1408-1409`),
      e sempre com o tipo `MOVETEXT` (`ocr_service.py:1427-1443`);
    - ele roda sem o léxico e o juntador de lance do tronco (a docstring de `glyph.py` diz por quê);
  - o RapidOCR — o motor do modo bloco da aba — **já é motor secundário**
    (`secondary_engines=("rapidocr",)`), mas só em página degradada
    (`secondary_only_when_degraded=True`);
  - a camada de texto já é candidata (S `ocr/engines/pdf_text_layer.py`).
- **Por que o `ler_pagina` não entra na fusão** (a lição do ciclo 12):
  - a fusão é por token e precisa de caixa por palavra. A `PaginaLida` só tem caixa por linha, em
    pontos (`LinhaLida.bbox`, T `text/leitor.py:1058-1062`);
  - ele precisa do PDF e do índice, e o serviço recebe a página como imagem.

  Então as alavancas **estendem o adaptador que já existe**, que lê a imagem e dá a caixa por
  glifo.
- **As alavancas** são interruptores de `OcrServiceConfig`.
  - **`glyph_scope`** (novo): `"lance"`, o de hoje, ou `"toda_regiao"`, como a aba, que lê tudo com
    o classificador. Com `"toda_regiao"`, o pedido leva o tipo da própria região, e não `MOVETEXT`.
  - **`glyph_texto_do_tronco`** (novo, `bool`): aplica às palavras do candidato o pós-processamento
    de texto que a aba faz e o adaptador deixa de fora, o léxico e o juntador de lance. A palavra
    juntada fica com a união das caixas.
    - **A primeira tarefa** lista, lendo o `_ler_pagina_do_livro` (T `text/leitor.py:1216+`), o que
      mais a aba aplica e o adaptador não.
    - Cada item entra nesta alavanca ou fica registrado como fora, com o motivo.
  - **`secondary_only_when_degraded`** (existe): `False` roda o RapidOCR em toda página, como o
    modo bloco.
  - **Uma configuração só, global.** A fusão não tem roteamento por estrato, e o serviço não sabe o
    estrato. A medição é por estrato, e uma configuração que melhora um estrato e piora outro **não
    liga**.
  - **A família.** As alavancas mudam o alcance e o texto do candidato de glifo que já existe, e
    nunca criam um segundo candidato do mesmo classificador.
    - O `_independent_agreement` de `fusion.py` separa as fontes pelo nome do motor. Dois
      candidatos do mesmo classificador com nomes diferentes contariam o mesmo erro como dois
      apoios independentes (a regra do passo B4).
    - Por isso a identidade do classificador vai no `meta` do resultado: o `modelo_sha256`
      completo dos pesos. O teste da família conta por ela, e não pelo nome do motor.
- **O instrumento é o do H0** (`benchmarks/editor_leitores.py`): o `import_pdf` com
  `PdfImportOptions(ocr_config=…)` da configuração testada (`importer.py:351`), nas páginas do
  manifesto.
  - É o caminho do produto. A página nativa com camada confiável não passa pelo OCR, e nela as
    alavancas não mudam nada.
  - O `bench_sol` (`recognize_image`) lê a imagem até da página nativa, então ele fica só para as
    invariantes do `sol_gate`, no portão (c).
- **O comparador direcional.** Para cada estrato *s* e métrica *m*, Δ é orientada para que positivo
  seja melhor para a configuração testada.
  - **CER:** Δ = CER(referência) − CER(testada).
  - **Lances certos, figurinas certas e ordem de leitura:** Δ = valor(testada) − valor(referência).
  - **Inserção** (lances inventados): Δ = taxa(referência) − taxa(testada).

  O intervalo é o **bootstrap percentil**, com 1.000 reamostras e semente 42. A unidade reamostrada é
  a **página**: as regiões de uma página partilham a digitalização, e reamostrá-las soltas
  estreitaria o intervalo sem razão.
  - **«Ganha»** ⇔ o limite inferior do intervalo **unilateral de 97,5 %** de Δ > 0.
  - **«Não perde»** ⇔ esse limite ≥ −δ*m*. As margens:
    - 0,002 para CER e inserção, as tolerâncias do `sol_gate` (`gates.py:54-55`);
    - 0,01 para lances, figurinas e ordem de leitura.
  - **«Idênticas»**, a igualdade canônica: o mesmo SHA-256 do JSON canônico da página do IR.
    - **A forma canônica:**
      - UTF-8, com o texto em NFC;
      - `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`;
      - os números já arredondados antes (caixas a 0,01 pt, confiança a 4 casas);
      - as listas na ordem do IR: blocos, linhas e tokens na ordem de leitura, e os diagramas na
        ordem em que o IR os tem.
    - O JSON cobre tudo o que a aba mostra ou envia (H26):
      - o texto de cada bloco e linha, com as caixas e a confiança;
      - a procedência por token e as figurinas;
      - os diagramas, com FEN, lado, número, legenda, estipulação e caixa.
  - **«Inalterada»** ⇔ a configuração dá leituras idênticas às de hoje em todas as páginas da
    célula. Célula inalterada não perde e não precisa de evidência: é o caso da página nativa com
    camada confiável, que não passa pelo OCR.
  - **«Sem evidência»** ⇔ a célula mudou e tem menos de 20 regiões casadas ou menos de 5 páginas.
    É o piso: abaixo dele, poucas páginas decidem a reamostragem.

  O `sol_gate` compara CER, inserção e ordem de leitura, e não lances nem figurinas
  (`gates.py:269-288`); por isso este comparador.
- **As duas saídas do H0b**, com regras separadas:
  1. **A configuração da fusão**: uma só e global, a de hoje ou uma das 7 alternativas. Não há
     roteamento por estrato na fusão.
  2. **O veredito da aba, por estrato**: «produto» ou «leitor antigo». Ele é calculado com a
     configuração final, e o H26 o segue. Ele decide o que a aba Texto mostra por padrão, não o que
     a fusão faz.
- **A regra da configuração: escolha em `dev` + `calib`, um só teste final na cega.**
  - **Pré-registro.** As 7 alternativas (2³ − 1), as métricas, as margens, o piso e esta regra estão
    fixados neste documento, antes de qualquer medição.
  - **Escolha em `dev` + `calib`**, sobre todas as páginas dessas partições:
    - entram as alternativas que ganham da configuração de hoje em ≥ 1 par (*s*, *m*) e não perdem
      em nenhum;
    - a ordem é pelo limite inferior de Δ/δ*m* no par em que ganhou; no empate, fica a de menos
      alavancas ligadas;
    - sem nenhuma, fica a de hoje, e a cega não é aberta.
  - **O registro antes da cega.** A candidata e o par (*s*\*, *m*\*) são gravados num arquivo de
    pré-registro, com o SHA-256 dele no relatório, **antes** de a cega ser lida. A leitura da cega
    recusa rodar sem esse arquivo, e grava o hash que leu.
  - **A leitura cega**, uma vez: `editor_combinacao.py --cega` roda o instrumento do H0 nas páginas
    `blind`, com o pré-registro. Ela lê com três leitores:
    - o produto na configuração de hoje;
    - o produto na candidata;
    - os **três modos do leitor da aba** (`glifo`, `glifo` com o modo bloco, e `camada`).

    As mesmas leituras servem às duas saídas: o teste da configuração e o veredito da aba. O
    `sol_gate --blind` é outro comando, o portão de liberação do Sol, que continua valendo à
    parte.
  - **O teste final na cega.** A candidata liga só se as duas condições valem na partição
    `blind`:
    - ganha no par (*s*\*, *m*\*) — um só teste unilateral, pré-registrado;
    - não perde em nenhuma célula, inserção incluída. As células inalteradas passam; as que mudaram
      e ficaram sem evidência reprovam (falha fechada).

    Se reprovar, fica a de hoje neste ciclo, e **nenhuma outra alternativa vai à cega**.
  - **A R1.4** proíbe treino, calibração e correção com a cega (`OCR_UI_SPEC.md:44`), e não a
    avaliação: o `sol_gate --blind` já a avalia. Aqui a cega só avalia, uma vez, uma candidata já
    escolhida. O resultado entra no relatório do portão de liberação.
  - **A cota.** Se a candidata não melhora de verdade o par (*s*\*, *m*\*), a regra a liga com
    probabilidade de aproximadamente 2,5 % ou menos:
    - a decisão é um único teste unilateral, pré-registrado, sobre dados que nenhuma escolha viu;
    - o bootstrap percentil dá o nível aproximado, não exato, e o relatório diz isso.
  - **O tamanho.** A cega tem hoje 57 regiões digitalizadas em 14 páginas, e 8 nativas em 8 páginas
    (contagem de 2026-09-24).
    - Se a candidata muda leituras nativas, a célula nativa da cega fica sem evidência, e a regra
      não liga nada.
    - O §8 leva ao usuário a opção de rotular mais verdade nativa.
  - A configuração que liga vira o padrão de `OcrServiceConfig`, com o número no comentário, como as
    decisões por medição da fase 2 do ciclo 2. O H8 e o H26 só a consomem depois deste portão.
  - **As leituras são determinísticas.** As 3 execuções medem o tempo e conferem que as leituras se
    repetem: o mesmo hash das respostas nas 3. Não são 3 testes: o teste estatístico é um só,
    sobre as leituras.
- **O veredito da aba, por estrato** (a segunda saída). Com a configuração final, para cada estrato
  *s*, o veredito é «produto» se o produto não perde, em nenhuma métrica, para o leitor da aba
  sozinho em cada um dos três modos. Senão, ou sem evidência, o veredito é «leitor antigo». É o
  critério de aceite da SOL-6 com o leitor da aba entre os isolados.
  - **De onde vêm os números**, por estrato:
    - **(a)** se a configuração final dá leituras **idênticas** (a igualdade canônica) às de hoje em
      todas as páginas medidas do estrato (`dev`, `calib` e `blind`), valem os números do H0.
      Quando a configuração final é a de hoje, as leituras são idênticas por definição (e, sem
      candidata, a cega nem é aberta). **Com o piso:** a célula do estrato no H0 precisa ter ≥ 20
      regiões casadas e ≥ 5 páginas; abaixo, o veredito é «leitor antigo»;
    - **(b)** senão, valem os da leitura cega: o produto na configuração final contra os três modos
      do leitor da aba, nas páginas `blind` do estrato, em todas as métricas (CER, lances,
      figurinas, inserção e ordem de leitura), com o comparador e o piso de cima.
  - **Por que o caso (a) pode usar o H0**, que foi medido em `dev` + `calib`, as partições da
    escolha:
    - nessas páginas, o produto final **é** o produto de hoje, leitura por leitura;
    - a comparação do veredito é, então, a do H0, entre dois leitores fixados antes de qualquer
      medição: a configuração de hoje é a referência do pré-registro, e o leitor da aba não muda;
    - a escolha do H0b compara alternativas com a configuração de hoje, nunca com o leitor da aba.

    Então nenhuma escolha usou a comparação que o veredito usa, e os números do H0 não têm viés de
    seleção. O viés de seleção só aparece no leitor escolhido, e no caso (a) ele lê igual ao de
    hoje.
  - **O JSON do veredito** registra, por estrato: a fonte dos números (H0 ou cega), as páginas, os
    números de cada leitor, as diferenças com intervalo e o veredito.
- **Arquivos:**
  - S `ocr/engines/glyph.py`: o pós-processamento do tronco, pela ponte `cvoff`, atrás de
    `glyph_texto_do_tronco`; a identidade do classificador no `meta`, pelo `modelo_sha256`
    completo (hoje o `meta` leva só 12 caracteres, dentro do texto `model`, `glyph.py:279-282,
    468`);
  - S `ingest/pdf/ocr_service.py`: `glyph_scope` e `glyph_texto_do_tronco` em `OcrServiceConfig`; a
    condição de alcance (1408-1409) e o tipo da região (1427-1443) passam a ler o campo;
  - `benchmarks/editor_combinacao.py` (novo): as 8 configurações pelo `editor_leitores.py` × 3
    execuções em `dev` + `calib`, a escolha, o pré-registro, a leitura cega (`--cega`: o produto
    de hoje, a candidata e os três modos do leitor da aba), o teste final, o veredito da aba e o
    JSON com os números;
  - testes: a família, contada pela identidade do classificador; a união das caixas no juntador;
    `secondary=True`; a regra sobre números sintéticos; as fixtures das alavancas; a fixture
    dourada da fusão.
- **Briefing.**
  - O usuário quer o OCR mais preciso para texto e símbolos de xadrez, ou a combinação dos
    leitores (spec Q1).
  - A fusão do produto já combina camada, Tesseract, RapidOCR, o classificador de glifos, modelo e
    cifra do livro. Este passo traz o que a aba faz de diferente, e só se a medição prova e
    confirma.
  - As regras de sempre continuam valendo:
    - a âncora que é palavra ou lance nunca é trocada (SOL-6);
    - letra de peça impressa não vira figurina (OCR_UI R2.3);
    - a partição cega não entra em treino, calibração nem correção (R1.4); aqui ela só avalia,
      uma vez;
    - nada de LLM (R1.5).
  - **Armadilha medida no ciclo 2** (`OCR_UI_ROADMAP_C2.md`, passo B2): um candidato **sem**
    `secondary=True` ancora a região e estraga a fusão (`twocol:d:12`, CER 0,0016 → 0,68). O
    candidato de glifo continua secundário e nunca âncora.
- **Portão** (`& $PY benchmarks\editor_portoes.py --passo H0b`):
  - (a) **A regra.**
    - A configuração publicada é a que a regra dá sobre os números publicados, recalculada pelo
      `editor_portoes.py`.
    - Sobre números sintéticos, a regra acerta os casos de borda:
      - não liga com uma célula que mudou e ficou sem evidência;
      - liga com uma célula inalterada abaixo do piso, se o resto passa;
      - não liga com uma configuração que ganha num estrato e perde em outro;
      - não liga com uma configuração que ganha em `dev` + `calib` e não se confirma na cega;
      - o veredito da aba sai por estrato, e um estrato «leitor antigo» não muda a configuração da
        fusão;
      - o veredito de um estrato que a configuração final muda vem da leitura cega; o de um estrato
        com leituras idênticas às de hoje em todas as páginas medidas vem do H0;
      - **o caso (a) abaixo do piso**, pela fixture `tests/fixtures/editor/h0b/veredito_caso_a_abaixo_do_piso.json`:
        - ela é escrita **antes** da implementação e congelada por SHA-256: o valor literal do hash
          fica gravado no teste quando a fixture é escrita;
        - tem 150 regiões de 2 livros, um por estrato: o digitalizado com 140 regiões em 12 páginas,
          e o nativo com 10 regiões em 4 páginas. Passa no denominador do H0 e fica abaixo do piso no
          nativo;
        - a configuração final é igual à de hoje, e pelos números o produto fica à frente do leitor
          da aba no nativo. Sem o piso, o veredito nativo seria «produto»;
        - a saída esperada, em `veredito_caso_a_abaixo_do_piso.esperado.json`: digitalizado
          «produto»; nativo «leitor antigo», com o motivo «abaixo do piso: 10 regiões, 4 páginas».
    - **As métricas obrigatórias:** o JSON do H0b tem as cinco métricas, com valor e intervalo,
      para cada leitor, modo e estrato, na escolha e, quando houver, na leitura cega. Métrica
      ausente ou nula reprova.
    - **A igualdade canônica:** um caso por campo — texto, caixa, confiança, procedência, figurina e
      cada campo do diagrama (FEN, lado, número, legenda, estipulação e caixa). Cada um, mudado
      sozinho, torna as leituras diferentes; duas leituras iguais em tudo são idênticas.
    - **A disciplina da cega:** a escolha não lê nenhum item da `blind` (a `partition_for` de
      `ocr/golden.py` confere cada item lido), e o hash do pré-registro que a leitura da cega
      gravou é o do arquivo da escolha.
  - (b) **As alavancas estão vivas**, em fixtures determinísticas:
    - **alcance:** numa página sintética com uma região de prosa sem lance (a condição de 1408-1409
      falsa), `toda_regiao` pede o candidato de glifo, e `lance` não pede;
    - **tipo:** nesse pedido, o `psm_hint` e o `region_kind` do `RegionTask` são o tipo da região, e
      não `MOVETEXT`; um motor espião registra os dois;
    - **texto:** numa leitura sintética com `lf`, e com `1.` e `e4` separados,
      `glyph_texto_do_tronco=True` dá `If` e `1.e4`, e a palavra juntada tem a união das caixas;
    - o `secondary_only_when_degraded` é interruptor que já existe, com o teste dele.

    As contagens nas páginas `dev` (regiões com candidato, palavras mudadas) vão ao relatório, sem
    portão.
  - (c) **A configuração que liga**, se houver, passou no teste final da cega. E o `bench_sol` com ela
    passa no `sol_gate --report-only`, sem portão verde da linha de base virando vermelho.
  - (d) **A fixture dourada da fusão**, escrita **antes** da implementação e congelada por hash. Ela
    roda o `_settle` do serviço com candidatos sintéticos:
    - **primeiro caso:** numa região de prosa, a âncora (Tesseract) é a palavra certa. O candidato
      de glifo traz outra palavra do dicionário, errada, com decisão `ACCEPTED` e pontuação maior.
      - Com `secondary=True`, o motor dele entra em `never_anchor` (`ocr_service.py:1474`), e a
        âncora continua a do Tesseract.
      - A âncora suportada nunca é trocada (`fusion.py:696-704`), então a saída acerta;
    - **segundo caso:** a âncora está fraca (confiança < 0,35) e certa, e é um lance de peão, sem
      letra de peça no início — as condições da regra B4 (`fusion.py:639-643`), que roda antes da
      regra da âncora suportada. O classificador lê outro lance, confiante e com margem. Com um só
      candidato do classificador não há concordância independente, e a saída acerta.
  - (e) **O tempo.** A mediana, nas 3 execuções, do tempo por página em regime — sem a partida do
    processo e sem a primeira página — fica ≤ 2 × a de hoje, em cada estrato.
    - Acima disso, a configuração não liga por padrão. O relatório publica o ganho e o custo, e a
      troca precisão × tempo vai ao usuário (§8).
    - A resposta do usuário fica gravada no JSON da configuração (`decisao_humana`: quem, quando, a
      escolha e o texto) e no relatório.
- **Um estrato com veredito «leitor antigo»** fica vermelho no relatório, e o §10 registra. A
  configuração da fusão não muda por isso: ela tem a regra dela.
- **Sabotagem.** As onze têm de reprovar, cada uma contra a fixture que a torna determinística:
  - `--sabotar configuracao_trocada`: o JSON publica a configuração seguinte à da regra, na ordem
    circular fixa das 8 (depois da última vem a primeira). (a) reprova «configuração ≠ regra»;
  - `--sabotar cega_na_escolha`: a escolha lê as páginas da `blind` junto com as outras. (a)
    reprova pela disciplina da cega;
  - `--sabotar veredito_do_h0_alterado`: o veredito de um estrato que a configuração final muda usa
    os números do H0. (a) reprova no caso de borda do veredito;
  - `--sabotar piso_so_na_cega`: o piso vale só no caso (b). Na fixture
    `veredito_caso_a_abaixo_do_piso.json`, o nativo sai «produto», e não «leitor antigo»: (a)
    reprova;
  - `--sabotar sem_ordem`: a leitura cega sai sem a ordem de leitura de um modo do leitor da aba.
    (a) reprova «métrica ausente»;
  - `--sabotar igualdade_so_texto`: a igualdade compara só o texto. (a) reprova no teste da
    igualdade canônica, que acusa como idênticas duas leituras com uma caixa diferente;
  - `--sabotar escopo_inerte`: o serviço lê `glyph_scope`, mas continua pedindo só região de lance.
    (b), alcance, reprova;
  - `--sabotar tipo_fixo`: com `toda_regiao`, o pedido continua com `MOVETEXT`. (b), tipo, reprova;
  - `--sabotar texto_inerte`: o interruptor é lido e não aplicado. (b), texto, reprova;
  - `--sabotar ancora_o_candidato`: o candidato de glifo sai sem `secondary=True`. A fixture (d),
    primeiro caso, reprova:
    - o motor dele sai de `never_anchor`;
    - com decisão e pontuação maiores, ele ganha a âncora pela ordem de `fuse_candidates`
      (`fusion.py:351-356`);
    - a palavra errada, suportada, nunca é trocada;
  - `--sabotar dois_apoios`: com `toda_regiao`, entra um segundo candidato do mesmo classificador,
    com outro nome de motor e `secondary=True`. Duas coisas reprovam:
    - a fixture (d), segundo caso, porque o `_independent_agreement` vê dois motores concordando;
    - o teste da família, que conta pela identidade do classificador.
- **Saída:** a fusão mais precisa que alimenta o editor (H8) e, depois, a aba Texto (H26), com a
  configuração, o pré-registro, o teste da cega, o veredito da aba por estrato e os números
  publicados.
- **Nível:** forte.
- **Desfazer:** `glyph_scope="lance"`, `glyph_texto_do_tronco=False` e
  `secondary_only_when_degraded=True`, os valores de hoje.

### H1 — Motores de pré-visualização, medidos — e o Chromium provado num pacote real

- **Governa:** spec D3, R1.13, R1.15, R4.1, §5.5.
- **Arquivos:**
  - `benchmarks/editor_motores.py`;
  - `tests/fixtures/editor/css/`, `tests/fixtures/editor/hostil/`;
  - `packaging/sonda_webengine.py` e `packaging/sonda_webengine.spec` (a sonda congelada; saída em
    `build\sonda_webengine\`, ignorado);
  - relatório §H1.
- **Briefing.**
  - Não há QtWebEngine.
  - O MuPDF `Story` pagina, dá posições e mediu 89,1 ms para 17 páginas (spec A.1), mas desenha um
    subconjunto do CSS. Fonte sem cmap Unicode cai em silêncio.
  - O Chromium custaria cerca de 207 MB descomprimidos (extrapolado de um PySide6 — **meça o
    PyQt6**).
  - `runtime/` fica **fora** da medida do pacote (`build_windows.py:56-71, 811-815`): o componente
    precisa de orçamento próprio.
  - O crítico exigiu prova num **build PyInstaller real** e numa **máquina limpa**, não num venv.
  - O WebView2 foi removido (S-69); não o reintroduza.
- **Tarefas.**
  1. **Matriz de CSS.**
     - As propriedades dos 9 temas de CB `layout/templates.py`, de `BASE_CSS` (`html.py:171`) e de
       `CHESS_CSS` (`epub.py:93`), extraídas com `tinycss2`.
     - Para cada propriedade: uma página **com** e outra **sem** a declaração. «Desenha» = pixels
       diferentes no retângulo do elemento-alvo. Nos dois motores.
     - Saída: `matriz_css.json`.
  2. **Latência e posições.**
     - Capítulos de 50 KB e 260 KB do `PEDIDO` p. 50–60 (pelo `XhtmlBuilder` atual).
     - MuPDF: leiaute + raster da página visível, p50/p95.
     - Chromium: remendo por `runJavaScript`, com o carimbo de pintura por `requestAnimationFrame`
       → `QWebChannel`.
     - Cobertura de `element_positions` e acerto clique → elemento em 400 pontos (semente 42).
  3. **Chromium como componente.** Com consentimento: rodas `PyQt6-WebEngine` e
     `PyQt6-WebEngine-Qt6` 6.11 do PyPI, dizendo nome, origem e tamanho ao pedir.
     - **(a)** Venv de rascunho fora do repositório: frio, memória, `offscreen`.
     - **(b)** A **sonda congelada**: PyInstaller com a mesma versão do `build_windows.py`, o PyQt6
       no `_internal\` e o WebEngine numa pasta `runtime\webengine\`, ligados por `PyQt6.__path__`,
       `os.add_dll_directory`, `PATH` do processo, `QTWEBENGINEPROCESS_PATH`,
       `QTWEBENGINE_RESOURCES_PATH` e `QTWEBENGINE_LOCALES_PATH`. A sonda desenha a fixture num
       PNG e grava os caminhos das DLL carregadas (dela e do `QtWebEngineProcess`).
     - **(c)** A mesma sonda **numa máquina limpa** (Windows Sandbox, habilitado pelo usuário, ou uma
       VM sem Python), copiada como pasta.
     - **(d)** Instalação atômica: pasta parcial → renomear no fim. Instalação abortada a meio →
       parcial apagada. Remoção → a sonda cai no MuPDF.
     - **(e)** Tamanho do download e do instalado.
  4. **Livro hostil** (`tests/fixtures/editor/hostil/`): `<script>`, `onerror=`, `javascript:`,
     `<img src="https://…">`, `@import url(http…)`, `<iframe>`, `<meta http-equiv="refresh">`, SVG com
     `<script>`, `src="C:/Windows/win.ini"`, `src="../../../x"` — nos dois motores.
  5. **O arnês de medição Chromium**, uma **entrega** deste passo que o H19 e o H24 usam, rodando
     no ambiente de medição mesmo que o produto não leve o componente
     (`benchmarks/editor_chromium_medicao.py`). A API:
     - `carregar(xhtml, folhas, folha_do_usuario=None)`;
     - `focaveis()`;
     - `focar_por_tab(n)` (tecla real, `QTest.keyClick`);
     - `retangulos(el)` (os `getClientRects()`);
     - `elementos_no_ponto(x, y)` (`elementsFromPoint`);
     - `estilo_calculado(el)`;
     - `capturar()` (imagem na escala do dispositivo).

     O arnês cumpre o **contrato executável do Apêndice D da spec**:
     - viewport de 1280 × 800 e rolagem por `scrollIntoView`, com faixas para link mais alto;
     - a DPR registrada e a conversão de coordenadas;
     - serialização em JSON;
     - espera do foco (`activeElement` + dois quadros);
     - captura sem hover nem cursor;
     - região e limiar da diferença (canal ≥ 16);
     - pseudo-elemento contado pelo elemento que o gera.

     O encobrimento segue o algoritmo do apêndice: `elementsFromPoint` **só dentro das caixas do
     link**; o indicador (pintura: `outline`, `box-shadow`, pseudo-elemento do link) **por máscara**
     — a renderização isolada contra a normal. Na isolada ficam neutralizados os outros elementos
     (`visibility: hidden`) e, nos ancestrais (com `html` e `body`), os `::before`/`::after` e a
     pintura por cima (`outline`, `box-shadow`).
     **Autoteste** com as sete fixtures do apêndice: `outline` e `box-shadow` sem falso
     encoberto; `body::after` sobre o contorno acusado; e ainda — contorno de 2 px ±1 %; faixa de
     1 px na
     borda; link em duas linhas; `::after` de outro elemento; `QT_SCALE_FACTOR=1.5` ±2 %.
- **Portão** (registrado no executor). Publica a matriz, as latências, as posições, os tamanhos, o
  frio e o hostil, e exige:
  - hostil com **0** requisições, **0** scripts e **0** arquivos fora do projeto nos dois motores;
  - cobertura de posições do MuPDF 100 %;
  - a sonda congelada com PASSOU **nesta máquina e na limpa**, com as DLL do WebEngine vindas de
    `runtime\webengine\`;
  - o autoteste do arnês de medição Chromium com PASSOU.

  O veredito da D3 (critérios 1–7) vai ao relatório.
- **Sabotagem.** As três têm de reprovar:
  - `--sabotar sem_ids`: a cobertura cai;
  - `--sabotar sem_interceptador`: requisições > 0;
  - `--sabotar sonda_sem_runtime` (apaga `runtime\webengine\`): a sonda **tem** de falhar; se
    desenhar, ela carregou o WebEngine de outro lugar, e o portão reprova.
- **Saída:** a D3 confirmada ou mutada (§10); a lista «o MuPDF não desenha» para o validador (H10).
- **Nível:** padrão.
- **Desfazer:** apagar o arnês e a sonda; nada no produto muda.

### H2 — O editor de código nativo aguenta, com tudo ligado?

- **Governa:** spec D4, S5, R3.2, §5.5, §5.6.
- **Arquivos:**
  - `src/caissa/editor/__init__.py`, `editor/lexico.py`;
  - `src/caissa/ui/widgets/editor_de_codigo.py` (protótipo);
  - `benchmarks/editor_codigo.py`, `benchmarks/editor_uia.py` (sonda UIA; `pywinauto` só no ambiente
    de medição);
  - `tests/unit/editor/test_lexico.py`.
- **Briefing.**
  - O crítico reprovou decidir o componente antes de medir. O protótipo tem **todas** as funções
    da spec S5 ligadas ao mesmo tempo:
    - realce por linha com estado, com o visível primeiro e o resto em fatias ≤ 8 ms;
    - margem com números e marcadores;
    - dobras;
    - 500 intervalos de indicador (onda e pontilhado);
    - lista de completar;
    - par de tags;
    - desfazer;
    - escala 150 %/200 %;
    - prévia MuPDF no processo de trabalho.
  - O `QSyntaxHighlighter` realça o documento inteiro de uma vez por padrão; o portão `bloqueio`
    reprova acima de 16 ms (pulso de 4 ms, `A/bloqueio.py:74`).
  - O PGN_Live_Editor mediu pausas de 150/400 ms (`..\PGN_Live_Editor\pgn_live_editor\services\parse_worker.py:362-374`).
- **Tarefas.**
  - `lexico.py`: função pura `tokens(linha, estado)`, com ≥ 60 casos de teste, incluindo os de
    fronteira de linha.
  - O protótipo.
  - `editor_codigo.py`, com o pulso do `bloqueio`:
    - abrir 50 KB, 500 KB e 2 MB;
    - digitar 60 s a 30 car/s em 500 KB com tudo ligado;
    - dobrar e desdobrar tudo;
    - desfazer 100 passos;
    - colar 100 KB;
    - trocar a escala;
    - primeira pintura de um projeto de 300 capítulos pequenos (`PEDIDO` p. 1–300 pelo
      `XhtmlBuilder` atual).
  - `editor_uia.py`: pela UI Automation do Windows, lê o `TextPattern` do editor (linha e
    caractere sob o cursor, seleção) depois de mover o cursor para 50 posições sorteadas.
- **Portão.**
  - Pior bloqueio ≤ 16 ms em todas as operações (3×).
  - Visível realçado ≤ 50 ms; primeira pintura ≤ 800 ms.
  - **Prova de atividade:** em cada medida, os contadores do protótipo mostram as funções ligadas.
    - 500 `ExtraSelection` presentes;
    - dobras recolhidas > 0;
    - lista de completar aberta > 0 vezes;
    - pilha de desfazer com 100 passos;
    - pedidos de prévia ao processo de trabalho > 0;
    - escala aplicada.

    Medida com qualquer contador zerado é **inválida** e reprova.
  - **Comportamento, não só atividade:** ≥ 5 casos dourados por função, um subconjunto da tabela
    do H12 (realce, margem, indicadores, completar, par e fecho de tag, dobras, desfazer, colar,
    busca, escala), passam no protótipo **com tudo ligado**.
  - UIA devolve o texto certo em 50/50 posições.
  - O Narrador confirmado por uma pessoa (registrado).
- **Sabotagem.** As três têm de reprovar:
  - `--sabotar realce_sincrono` (`rehighlight()` do documento inteiro): o bloqueio passa de 16 ms;
  - `--sabotar funcoes_desligadas` (mede com indicadores, dobras e prévia desligados): a prova de
    atividade invalida a medida;
  - `editor_uia.py --sabotar uia_mudo` (a sonda contra um `QWidget` que só **pinta** o texto): 0/50
    — prova que a sonda lê pela interface de texto e não por acaso.
- **Saída:** a D4 confirmada, ou o H2b.
- **Nível:** padrão.
- **Desfazer:** apagar o protótipo.

### H2b — (só se o H2 reprovar) QScintilla no mesmo arnês

- **Governa:** spec D4.
- **Arquivos:** `pyproject.toml` e `.venv-pack` (`PyQt6-QScintilla`, GPL-3.0, Riverbank);
  `packaging/coletar_licencas.py` (inventário); o protótipo sobre `QsciScintilla`, com as cores
  pelos papéis de token.
- **Briefing.** Mesmo arnês, mesmos números. QScintilla estiliza sob demanda em C++, mas a
  acessibilidade no Windows não está provada aqui, e as cores dele não passam pela folha QSS: o
  `contraste` precisa de um adaptador.
- **Portão:** o do H2, inteiro, mais o inventário de licenças com a entrada nova.
- **Sabotagem:** as do H2.
- **Saída:** a D4 mutada (§10).
- **Nível:** padrão.
- **Desfazer:** remover a dependência.

### H3 — O contrato de marcação e a política de CSS, no papel e em fixtures

- **Governa:** spec D1, D2, S3b, S4, R2.2, R2.4.
- **Arquivos:**
  - `docs/MARKUP_CAISSA.md` (normativo);
  - `tests/fixtures/editor/contrato/*.xhtml` (uma por linha do S4, mais combinações, mais uma
    **legada** do `XhtmlBuilder` atual);
  - `tests/fixtures/editor/css/mapa_positivo/`, `mapa_negativo/`;
  - `benchmarks/editor_contrato.py`;
  - relatório §H3.
- **Briefing.**
  - Três vocabulários (spec §2.4). O MARKUP é congelado por política própria.
  - `CB validate.validate_book(documents, files, stylesheets, declared_licences)` (`validate.py:156-208`)
    dá problemas com linha.
  - O contrato diz, para cada nó do IR:
    - a marcação e os atributos obrigatórios;
    - o que é derivado (a `img.cb-svg`);
    - o que o leitor aceita como sinônimo (o legado `data-ir`, `data-mode` ausente = `svg`);
    - o que vai a `html_attributes`;
    - N1–N4.
  - **A política de CSS** (spec S3b) entra no mesmo documento: o que o mapa de estilo leva, o que
    avisa e com qual código.
  - A adoção de `cb-*` espera o Q3; o passo escreve o contrato e o marca «pendente Q3».
- **Tarefas.**
  - O documento.
  - As fixtures:
    - uma por linha do S4;
    - positivas do mapa: cada propriedade do mapa com 2 valores e o estilo esperado num `.json` ao
      lado;
    - negativas: uma por construção fora do mapa, com o aviso esperado.
  - **As fixtures douradas do sidecar** (spec Apêndice C), escritas pelo **crítico**, não pelo
    construtor, **antes de qualquer implementação**:
    - `tests/fixtures/editor/sidecar/v2_completo.jsonl`: a saída esperada de um `Document` de
      fixture que preenche as dez classes com valores fora do padrão;
    - `v1_de_hoje.jsonl`: produzido pelo exportador atual, com `rect` em tupla, como o teste de
      hoje;
    - `v1_migrado_esperado.jsonl`.

    O SHA-256 dos três vai ao relatório do H3 e não muda sem mutação no §10.
  - `editor_contrato.py`: roda o `CB validate` (o `sys.path` aponta o CB **só no arnês**) e
    confere as fixtures.
- **Portão.**
  - 100 % das linhas do S4 com fixture.
  - `CB validate` com 0 erros de contrato nas fixtures do contrato.
  - O leitor atual lê a fixture legada.
  - Cada fixture do mapa tem o resultado esperado declarado.
  - As três fixtures douradas do sidecar existem, assinadas pelo crítico, com o SHA-256 no
    relatório.
- **Sabotagem.** `negativa_sem_fen.xhtml` (sem `data-fen`) posta no conjunto limpo: o CB acusa, e
  o portão reprova.
- **Saída:** o contrato que o H5 implementa.
- **Nível:** forte.
- **Desfazer:** apagar o documento e as fixtures.

### H4 — As dívidas da exportação que o editor poria na tela

- **Governa:** spec §2.7 (os itens 1–10; 1, 2 e 10 **obrigatórios**, com ou sem a tarefa separada
  «Fix three silent EPUB export defects»), R2.3, R2.4, R1.14.
- **Arquivos:**
  - S `export/provenance.py` + `export/book.py` (item 1: `Rect` real; a falha deixa de ser engolida
    e vira aviso no relatório);
  - S `export/book.py` (item 2: «Mate em N» preservado);
  - S `export/epub.py` (item 10: sem caminho no IR embutido; item 5: Merida só quando usada como
    texto);
  - S `ingest/pdf/importer.py` (item 3: alt), S `ingest/pdf/games.py` (item 4: cabeçalho e língua);
  - S `export/html.py` (itens 4 e 7);
  - S `export/diagrams.py`, S `typeset/board_svg.py` ou a docstring de `epub.py:24-30` (item 6);
  - S `export/profiles.py` (item 8), a numeração automática (item 9);
  - `benchmarks/editor_dividas.py`, testes por item.
- **Briefing.**
  - O explorador reproduziu os itens 3–9 em memória em 2026-09-23. Os itens 1, 2 e 10 foram
    confirmados lendo o código (endereços na spec §2.7).
  - Se a tarefa separada já corrigiu 1, 2 e 10, o passo **confere com as fixtures positivas**
    abaixo e segue.
  - O alt descritivo é a primeira função partilhada por editor e EPUB:
    `descrever_posicao(fen, lado, idioma, conferida)` em S `export/diagrams.py`, pura (spec §5.6;
    A9 do ciclo 2).
  - Antes de mexer, exporte e guarde os EPUBs de antes (a sabotagem dos itens 3–9).
- **Tarefas.**
  - Um teste que reprova antes e passa depois, por item.
  - **Fixtures positivas dos itens 1, 2 e 10**, montadas **como o produto monta** — um documento
    do importador real, `LIVRO` p. 31–38, com `Rect` e não com tupla:
    - (1) o sidecar é gravado e cada registro de diagrama tem `rect` com x, y, largura, altura e
      unidade;
    - (2) um diagrama com «Mate em 2» e uma decisão de lado mantém «Mate em 2»;
    - (10) nenhum arquivo do EPUB tem letra de unidade, caminho absoluto ou o nome do usuário.
  - `editor_dividas.py --epub <arquivo> --saida <pasta>` grava, **por sintoma** (os dez),
    `{"sintoma", "severidade": "bloqueia", "contagem", "exemplos": ["arquivo:linha", …]}`.
- **Portão.**
  - EPUBs de `LIVRO` p. 31–38, `KEMERI` p. 80 e `PEDIDO` p. 55, por
    `& $PY -m caissa.export.cli --epub --paginas 31-38 --saida <pasta>\livro.epub $LIVRO` (e
    análogos).
  - Os **dez** sintomas **= 0**.
  - As três fixtures positivas PASSOU.
  - EPUBCheck 0 erros.
  - Os alts descritivos batem com a FEN em 100 % (o contador reconstrói a posição do alt).
- **Sabotagem.**
  - Itens 3–9: o contador sobre os EPUBs de **antes** (`benchmarks\reports\editor\h4\antes\`) dá
    > 0 em cada um.
  - Itens 1, 2 e 10, que podem já estar corrigidos antes: `--sabotar rect_como_lista`,
    `--sabotar estipulacao_sobrescrita` e `--sabotar caminho_no_ir` reintroduzem cada defeito
    por um remendo em memória, e a fixture correspondente reprova.
- **Saída:** o motor HTML sem as dívidas.
- **Nível:** padrão.
- **Desfazer:** reverter os commits do passo.

---

## 3. Fase 1 — o núcleo do documento (sem Qt)

### H5 — O perfil legível, os atributos preservados, o CSS como recurso e o mapa de estilo

- **Governa:** spec D1, D2, R2.2, R2.3, S3, S3b, S4. **Espera:** Q3.
- **Arquivos:**
  - S `export/html.py` (`XhtmlBuilder(perfil=)`, `ler_legivel`), S `export/profiles.py`;
  - S `core/model/base.py` (`IRNode.html_attributes`), `core/model/migrations.py` (v1→v2),
    `core/model/serialize.py`;
  - S `editor/leitura.py`, `editor/paginas.py` (R2.7);
  - S `editor/css/mapa_de_estilo.py` (sem Qt; `tinycss2`), `pyproject.toml`/`.venv-pack` (`tinycss2`,
    `cssselect2`, BSD);
  - testes;
  - `benchmarks/editor_ida_e_volta.py`;
  - `tests/unit/ui/test_arquitetura.py` (S `editor/` sem toolkit).
- **Briefing.**
  - O `XhtmlBuilder` (`html.py:1951`) é ida-e-volta, mas escreve para máquina (spec §2.3).
  - O perfil legível escreve o contrato de `docs/MARKUP_CAISSA.md`, e `ler_legivel` o lê **sem**
    `data-ir`.
  - O que o contrato não modela é **preservado**:
    - elemento → `RawPassthrough`/`RawInline` `xhtml`;
    - atributo → `IRNode.html_attributes`.
  - O campo novo exige o esquema v2: `CURRENT_SCHEMA_VERSION = 1` em `migrations.py:51`, e campo
    desconhecido é recusado. O padrão vazio é omitido na serialização, e a migração v1→v2 é
    trivial.
  - O CSS do projeto é `Resource(kind=STYLESHEET)` (`document.py:63`), **não** interpretado.
  - O **mapa de estilo** (spec S3b) calcula, por classe, as propriedades do subconjunto fechado,
    com a cascata só dentro dele e `var()` de `:root`. Cada regra ou propriedade fora do mapa gera
    um aviso com seletor, propriedade e arquivo:linha.
  - O EPUB **continua** no perfil de máquina até o H24. Este passo acrescenta e prova.
- **Tarefas.**
  1. O construtor e o leitor legíveis.
  2. O esquema v2 com migração, e o `test_roundtrip_corpus` estendido a `html_attributes`.
  3. `editor/paginas.py`, com teste de base 0/1 e fólio.
  4. O mapa de estilo.
  5. `editor_ida_e_volta.py`:
     - **ida** IR → XHTML → IR com `semantic_diff`, sobre o corpus sintético de 10.000 nós e o IR
       real de `LIVRO` p. 31–38, `KEMERI` p. 80, `PEDIDO` p. 50–60 e `DEM` p. 20–25;
     - **volta** XHTML → IR → XHTML com `canon`, sobre as fixtures do H3, os arquivos da ida e 20
       edições à mão (`tests/fixtures/editor/editados/`), com `style`, `title`, `aria-*`, classes
       extras e elemento fora do contrato;
     - CSS byte a byte (`Resource` → escrita);
     - o mapa de estilo nas fixtures positivas e negativas do H3.
- **Portão.**
  - Ida: 0 diferenças fora de N1–N4, com N1–N4 contadas.
  - Volta: `canon` idêntico em 100 %.
  - CSS idêntico em 100 %.
  - Mapa: positivas com o estilo esperado (100 %); negativas com o aviso esperado (100 %).
  - `CB validate` 0 erros de contrato.
  - EPUBCheck 0 erros num EPUB montado com o perfil legível no arnês.
- **Sabotagem.** Cada uma tem de reprovar:
  - `perde_fen`;
  - `perde_classe`;
  - `engole_desconhecido` (descarta em vez de preservar);
  - `perde_atributo` (ignora `html_attributes`);
  - `css_silencioso` (o mapa não avisa uma regra fora).
- **Saída:** o motor que o editor usa para gerar e para exportar.
- **Nível:** forte.
- **Desfazer:** o perfil é aditivo; a migração v2 tem o caminho de volta testado (v2 sem
  `html_attributes` → v1).

### H6 — O projeto em disco

- **Governa:** spec S2, R2.1, R2.8, R2.9, R5, §5.4, Q4.
- **Arquivos:**
  - S `editor/projeto.py`, `editor/diario.py`, `editor/versoes.py`, `editor/livros.py`,
    `editor/migracoes.py`, `editor/trava.py`;
  - `.gitignore` (`/editor/`);
  - `packaging/build_windows.py` (`editor` em `PASTAS_DO_USUARIO`/`PASTAS_GUARDADAS`) com o teste
    do pacote;
  - `benchmarks/editor_recuperacao.py`;
  - `tests/unit/editor/test_projeto.py`.
- **Briefing.**
  - O padrão de raiz é o do `labeling/`: repositório num checkout, ao lado do executável no pacote
    (`ocr/labeling/helpers.py:70-76` `default_project_dir`), com `CAISSA_EDITOR_DIR` sobrepondo.
  - O build **apaga** o que não está em `PASTAS_GUARDADAS` (`build_windows.py:67`).
  - Gravar é temporário + `os.replace`; o diário grava ≤ 2 s depois da mudança.
  - Versões: LRU de 200 MB, com as 20 últimas sempre guardadas.
  - A chave do livro é o SHA-256 do PDF.
  - **Um livro, uma janela:** `.trava` com `O_EXCL`, PID e expiração (o mecanismo de
    `diagram_decisions.py:293-326`).
  - `mudou_por_fora(arquivo)` compara `mtime` e hash com a última leitura.
- **Tarefas.**
  - A API da spec S2.
  - A migração por `formato`.
  - `editor_recuperacao.py`: um processo filho edita e grava enquanto o pai o mata com
    `TerminateProcess` em pontos sorteados (semente 42), 50×.
- **Portão.**
  - 50/50 reaberturas recuperam o diário com ≤ 2 s de perda.
  - 50/50 arquivos são o antigo ou o novo, nunca truncados.
  - Versão restaurada idêntica byte a byte.
  - Depois de 300 gravações, o teto de 200 MB é mantido e as 20 últimas estão lá.
  - Segunda abertura do mesmo livro recusada pela trava; trava vencida (processo morto) retomada.
  - Mudança por fora detectada em 100 % de 20 casos.
  - O teste do pacote afirma `editor` em `PASTAS_GUARDADAS`.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_diario`;
  - `escrita_direta` (sem temporário);
  - `sem_trava` (duas aberturas aceitas);
  - `lru_sem_piso` (apaga as 20 últimas).
- **Saída:** o projeto que a janela e a geração usam.
- **Nível:** padrão.
- **Desfazer:** apagar o pacote novo; a pasta de dados do usuário não é tocada.

### H7 — O serviço único de decisões

- **Governa:** spec R5, R2.5, S8.
- **Arquivos:**
  - S `ocr/decisoes.py` (novo);
  - S `ocr/review.py` (`ReviewDecisions.save` atômico, só chamado pelo serviço);
  - S `ocr/diagram_decisions.py` (o `record` passa pelo serviço);
  - **S `ui/views/revisao_de_texto.py`** (a gravação direta de `:623`, `self.queue.decisions().save(destino)`,
    passa pelo serviço);
  - T `qt/decisoes_de_diagrama.py` (o gancho da aba Resultado chama o serviço);
  - `tests/unit/ocr/test_escritores_de_decisao.py` (novo: o teste de arquitetura);
  - `benchmarks/editor_decisoes.py`, testes.
- **Briefing.**
  - Hoje `ReviewDecisions.save` grava com `write_text`, sem trava e sem temporário (`review.py:542-546`).
  - `diagram_decisions` já tem trava `O_EXCL` com expiração de 60 s (`diagram_decisions.py:293-326`).
  - Com o editor, as duas janelas escrevem nos dois armazéns. A bancada Tk (`caissa-rotular`) pode
    escrever de outro processo.
  - **O serviço** (spec R5):
    - `RLock` no processo e trava entre processos;
    - releitura antes de gravar, com fusão por chave quando o arquivo mudou (`mtime` + hash);
    - gravação atômica;
    - observadores sem Qt (a ponte para sinal Qt mora em `ui/`);
    - releitura quando outro processo gravou.
  - **Conflito na mesma chave:** vence a última. A descartada vai ao histórico só de acréscimo
    (`<armazém>.historico.jsonl`), com «restaurar a outra» e o desfazer (spec R5).
  - **Escritores de hoje** (`grep` em 2026-09-23):
    - a aba Revisão de texto (`revisao_de_texto.py:623`);
    - `diagram_decisions.record` (`:293-326`);
    - o gancho do tronco (`qt/decisoes_de_diagrama.py:43`).

  - **A exclusividade é estrutural** (spec R5):
    - `ReviewDecisions.save`, `DiagramDecisions.save` e `record` viram `_gravar`/`_registrar`,
      privados;
    - o gancho do tronco (`:43` importa `record`, `:106` o chama pelo nome curto) passa a chamar o
      serviço;
    - o teste de arquitetura por **AST**, sobre `src\caissa` e `..\ChessVisionOFF_Puro\src`,
      (a) afirma por introspecção que as classes não têm `save`/`record` públicos, (b) reprova
      referência a `_gravar`/`_registrar` — atributo, nome importado, alias, `getattr` com literal —
      fora do serviço e dos dois módulos dos armazéns, e (c) reprova `import` de `record` de
      `caissa.ocr.diagram_decisions`.
  - **O recibo:** `gravar(...) -> Recibo`, e `Recibo.desfazer()` regrava a anterior.
    - **Neste passo**, os dois escritores que já existem o usam: a aba Resultado (T
      `qt/decisoes_de_diagrama.py` devolve o recibo à pilha de desfazer do A7) e a aba Revisão de
      texto, que, sem pilha própria, mostra «restaurar a outra» no aviso.
    - O editor ainda não existe aqui. A transação dele usa o recibo no H16 (aceitar dúvida) e no
      H22 (editar posição), e os **portões desses passos** provam o `Ctrl+Z` do editor.
  - **A guarda de execução** (spec R5): um gancho `sys.addaudithook` instalado pelo `conftest` da
    suíte e do tronco e pelos arnês de percurso.
    - Registra toda escrita sob `labeling/revisao/` e `labeling/diagramas/`.
    - Os eventos são os medidos: `open` com modo `w`/`a`/`x`/`+` **ou** modo `None` com flags de
      escrita (o `os.open`); `os.rename`, que o `os.replace` dispara; `os.remove`.
    - O caminho é canonizado por `realpath`, `normcase` e nome longo.
    - Reprova a escrita que não passa por `caissa/ocr/decisoes.py` na pilha.
- **Tarefas.** O serviço com recibo; a migração dos três escritores; a escrita privada; o histórico;
  o teste de arquitetura; o arnês.
- **Portão.**
  - O teste de arquitetura com **0** escritores fora do serviço.
  - 2 threads × 1.000 decisões em chaves diferentes → 0 perdidas, **em cada um dos dois
    armazéns**.
  - 2 processos × 500 → 0 perdidas, nos dois.
  - Mesma chave, 100 conflitos em cada armazém:
    - 100 avisos;
    - o estado final é o da última;
    - as 100 descartadas estão no histórico;
    - «restaurar a outra» devolve cada uma (100/100);
    - **por escritor existente**, a restauração pelo caminho prometido: `Recibo.desfazer()` pela
      API (20/20); o `Ctrl+Z` da aba Resultado (20/20); o «restaurar a outra» da aba Revisão de
      texto (20/20).
  - **A guarda de execução**, ligada durante a suíte inteira dos dois repositórios e os percursos
    existentes: **0** escritas fora do serviço.
  - Gravação por outro processo → observadores avisados em ≤ 1 s em 20/20.
  - **Gravação atômica nos dois armazéns:** morte no meio da gravação (`TerminateProcess`, 50× cada)
    deixa o arquivo antigo ou o novo, nunca truncado.
  - As abas Revisão de texto e Resultado continuam gravando e lendo como antes (testes existentes
    verdes).
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_trava`: perdidas > 0;
  - `sem_releitura`: a gravação externa é sobrescrita;
  - `sem_aviso`: observadores não avisados;
  - `sem_historico`: a descartada some e «restaurar» falha;
  - `escritor_direto` (volta a chamada de `revisao_de_texto.py:623` para a escrita direta): o teste
    de arquitetura acusa;
  - `alias_escondido` (um módulo de teste importa `_registrar as gravar_rapido` e o chama): o teste
    por AST acusa;
  - `recibo_vazio` (o recibo não guarda a anterior): as restaurações por escritor caem;
  - `escrita_crua` (um teste monta o JSON e grava com `Path.write_text` em `labeling/revisao/`):
    a guarda de execução acusa;
  - `troca_atomica` (grava num temporário e faz `os.replace` para o armazém): o evento `os.rename`
    é acusado;
  - `por_juncao` (a mesma escrita por um caminho relativo e por uma junção `mklink /J` que aponta
    para `labeling\diagramas`): a canonização acusa as duas;
  - `trava_crua` (`os.open` com `O_CREAT|O_EXCL` no `.lock` de fora do serviço): a regra das flags
    acusa.
- **Saída:** um lugar só para gravar decisão.
- **Nível:** forte.
- **Desfazer:** reverter; os formatos de arquivo não mudam.

### H8 — Gerar o projeto a partir do OCR (com as dúvidas por trecho)

- **Governa:** spec S3, S8, R2.1, R2.5, R2.7, Q1 (respondida: C). **Depende de:** H0b, H5, H6,
  H7.
- **Arquivos:**
  - S `editor/geracao.py`, `editor/proveniencia.py`, `editor/diagramas.py` (cache de SVG);
  - S `ingest/pdf/importer.py` (`_span_inlines`: o `Span` de dúvida);
  - S `export/secoes.py` (a divisão em arquivos extraída de `epub.py:419-448,1345`, usada pelos
    dois);
  - `benchmarks/editor_geracao.py`, testes.
- **Briefing.**
  - A fonte é a **fusão do produto** (Q1 = C): o `import_pdf` com as decisões (`PdfImportOptions`,
    `importer.py:309-415`), com as alavancas que o H0b ligar, por intervalo, cancelável e parcial.
  - Divide pela regra do EPUB, escreve no perfil legível, grava `proveniencia.json` e os SVG pelo
    `DiagramRenderer` (`export/diagrams.py:411-469`).
  - Hoje a dúvida só existe no bloco (spec §2.2). O importador embrulha os trechos em revisão num
    `Span` com `provenance` (sem migração); o perfil legível grava o intervalo (N3).
  - **Página `EDITADA`/`REVISADA` nunca é regerada.**
  - O `PEDIDO` tem 898 páginas: o usuário escolhe o intervalo, e o resto fica `NAO_GERADA`.
- **Tarefas.**
  - A geração.
  - O `Span` de dúvida.
  - A regeneração de página `GERADA` quando as entradas mudam: o hash das decisões e do modelo do
    livro em `projeto.json.paginas[n].geracao`.
- **Portão** (`LIVRO` p. 31–38, `KEMERI` p. 80, `PEDIDO` p. 50–60, `DEM` p. 20–25):
  1. 100 % dos blocos com proveniência têm `id` e entrada.
  2. 100 % dos `Diagram` viram `figure.cb-diagram` com a FEN **depois** das decisões e SVG com
     hash que confere.
  3. 100 % dos `Span` de dúvida viram intervalo com o texto certo.
  4. Os números esperados, contados do IR pelo arnês, batem com os publicados: blocos, diagramas e
     dúvidas.
  5. Página `EDITADA` com hash idêntico depois de gerar de novo.
  6. Cancelar a 30 % deixa páginas completas e o resto `NAO_GERADA`.
  7. Tempo ≤ 1,05 × a importação sozinha.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_proveniencia`: (1) cai;
  - `sobrescreve_editada`: (5) cai;
  - `sem_diagramas` (a geração pula os `Diagram`): (2) e (4) caem.
- **Saída:** projetos reais para as fases seguintes.
- **Nível:** forte.
- **Desfazer:** reverter; o `Span` é aditivo.

### H9 — O mapa de fontes e a sincronia lógica

- **Governa:** spec S6, S7, §5.5.
- **Arquivos:** S `editor/mapa.py`, S `editor/sincronia.py`, `benchmarks/editor_sincronia.py`,
  testes.
- **Briefing.**
  - Três funções puras:
    - posição no código → (elemento, deslocamento no texto do elemento);
    - o inverso;
    - elemento → (página base 0, `rect`) pelo `proveniencia.json`.
  - O `expat` dá linha, coluna e byte de cada início de tag, em C.
  - Arquivo mal formado: o último mapa bom, mais o analisador tolerante do H2.
  - Entidades mudam o comprimento.
- **Tarefas.** As funções; a reserva; o arnês com amostragem **estratificada e semente 42**.
- **Portão.** 400 pontos por arquivo, nos arquivos do H8 e nas fixtures:
  - 25 % perto de entidade, 25 % em inline aninhado, 20 % em fronteira de tag ou atributo, 15 % em
    figurina ou NAG, 15 % em comentário ou CDATA;
  - ida e volta posição → elemento → posição: 100 %;
  - o `rect` do elemento contém o de proveniência: 100 %;
  - arquivo mal formado: regiões não editadas exatas em 100 %; a região editada devolve o elemento
    mais próximo **marcado** «aproximado» em 100 %;
  - ≤ 1 ms por consulta (mediana).
- **Sabotagem.** As duas têm de reprovar:
  - `sem_entidades`: acertos < 100 %;
  - `sem_marca_aproximado`: a região editada sai sem a marca.
- **Saída:** a base dos H13, H15 e H16.
- **Nível:** forte.
- **Desfazer:** apagar os módulos.

### H10 — A validação em camadas, com linha e coluna

- **Governa:** spec S10, R4.2, R4.3, R2.3, §5.6.
- **Arquivos:**
  - S `editor/validacao/`: `xml.py`, `contrato.py` (absorvido de CB `validate.py`, com «Origem:»),
    `xadrez.py`, `css.py`, `acessibilidade.py`, `seguranca.py`, `ocr.py`, `problema.py`;
  - S `export/epubcheck.py` (`--json`, mensagem com local);
  - `tests/fixtures/editor/defeitos/`, `benchmarks/editor_validacao.py`.
- **Briefing.**
  - Cada camada é `(arquivo, texto, contexto) → [Problema]`, com código, severidade, local, «o que
    fazer» e conserto opcional.
  - O EPUBCheck hoje só lê o resumo. O `--json` dá cada mensagem.
  - A camada CSS usa a matriz do H1 (o que o motor ativo ignora) e o mapa do H5 (o que o DOCX não
    recebe).
  - A camada CSS mede o **contraste AAA 1.4.6 na página renderizada** pelo MuPDF `Story`, a mesma
    função do H1: cor calculada de cada trecho × fundo local, 7:1 para texto normal e 4,5:1 para
    grande. Vale para **qualquer** CSS do projeto.
  - A camada de acessibilidade aplica o alt do H4 e o A9.
  - Nada na thread da janela.
- **Tarefas.**
  - As camadas.
  - ≥ 40 defeitos, um por regra, com a linha e a coluna esperadas num `.json` ao lado — incluindo
    os de acessibilidade por arquivo: `lang` ausente, salto de título, alt ausente, alt que afirma
    o não lido, marcador de página duplicado, **texto normal a 5,7:1 numa folha do projeto fora
    dos temas**, e os do AAA aplicável (spec §5.6):
    - região mantida como imagem (imagem de texto);
    - `<audio>`/`<video>`/`<track>`;
    - `animation`/`transition`/`@keyframes` e GIF animado;
    - `<form>`, `<input>`, `<button>`, `<select>`, `<textarea>`, `<details>`, `contenteditable`,
      `tabindex` > 0;
    - `<meta http-equiv="refresh">`;
    - `position: fixed/sticky`;
    - `:focus { outline: none }` sem substituto;
    - link só com «↩»;
    - seção sem papel;
    - símbolo fora do glossário;
    - abreviatura da lista sem `<abbr>`;
    - `data-confidence`/`data-engine`/`data-note` escritos no projeto.
  - O conjunto limpo: as saídas legíveis do H5 (o IR real de `LIVRO`, `KEMERI`, `PEDIDO` e `DEM`
    passado pelo perfil legível). Não depende do H8.
- **Portão.**
  - 100 % dos defeitos com código e linha:coluna certos.
  - 0 falsos positivos no limpo.
  - EPUBCheck com erro injetado → mensagem lida com local (100 %).
  - ≤ 500 ms por arquivo de 260 KB.
- **Sabotagem.** As duas têm de reprovar:
  - `sem_linha`;
  - `regra_muda` (desliga a regra de `data-fen`).
- **Saída:** a lista de problemas da janela.
- **Nível:** padrão.
- **Desfazer:** apagar o pacote de validação.

---

## 4. Fase 2 — a janela

### H11 — A aba, a janela, a casca, a rota de teclas e os portões que passam a vê-la

- **Governa:** spec D5, S1, R3.1, R3.6, R3.7, R1.12.
- **Arquivos.**
  - Tronco:
    - `ui/abas.py`;
    - `qt/painel_do_editor_html.py` (aba lançadora, guarda `disponivel()/montar()` de
      `painel_de_rotulagem.py:28-52`);
    - `qt/casca_do_editor_html.py`;
    - `qt/acessibilidade.py` (`JANELAS_SECUNDARIAS`);
    - **`qt/atalhos.py` e `ui/atalhos.py`** (a rota do R3.6);
    - `ui/state.py` (v7 + `_migrate`);
    - `ui/comandos.py` + `ui/menu.py`;
    - `qt/abas_da_suite.py` (`:36-37`);
    - testes, incluindo `test_qt_atalhos`.
  - Suíte:
    - `editor/casca.py`, `editor/comandos.py`, `ui/views/editor_html/janela.py`;
    - A `teclado.py`, `texto_pintado.py`, `comandos.py`, `minimo.py`, `bloqueio.py`, `capture.py`
      (`--janela editor`);
    - A `teclas_cruzadas.py` (novo);
    - testes.
- **Briefing.**
  - **A guarda de teclas** (T `qt/atalhos.py:269-293`) é da aplicação e decide pela cadeia de foco;
    a janela principal é o destino final.
  - A rota nova (spec R3.6) decide pela **janela ativa**:
    - pop-up ativo (`QApplication.activePopupWidget()`) → a tecla é dele;
    - campo de texto em foco → as teclas próprias dele, **incluindo** o texto que chega com
      `Ctrl+Alt` (AltGr) e as teclas mortas (`QInputMethodEvent`);
    - a janela do editor → o `DonoDeAcoes` dela **executa** a ação ligada;
    - tecla só da principal → não despachada, com aviso na barra;
    - janela principal ativa → como hoje.
  - **Acessibilidade.** Só `QDialog` é tratado (T `qt/acessibilidade.py:224-225`). Com
    `JANELAS_SECUNDARIAS`, a suíte não chama `nomear_tudo` (proibido fora de `acessibilidade.py`,
    `test_dialogos.py:232-243`).
  - **Os portões** hoje só veem a principal e os `QDialog` de `RECEITAS`. `--janela editor` abre a
    janela sobre um projeto de fixture e mede nela.
  - A casca é um protocolo sem Qt no tipo. Os testes da suíte usam uma casca falsa.
  - A aba ativada abre ou traz a janela à frente.
  - **O mesmo livro não abre duas vezes** (a trava do H6).
- **Tarefas.**
  - O esqueleto da janela: menus da S9 gerados da tabela, com comandos futuros desabilitados
    **com motivo**; docas; estados vazios; geometria e docas lembradas.
  - A rota; `teclas_cruzadas.py`.
- **Portão**, em projeto de fixture, nas três peles, 1366×768 e 1920×1080 a 150 %:
  - `teclado`, `texto_pintado`, `comandos`, `minimo` (≤ 1250×640) e `bloqueio` (abrir, trocar de
    doca, redimensionar) `--janela editor` **PASSOU**.
  - `teclas_cruzadas` **positivo e negativo:**
    - **(a)** Para cada tecla da tabela do editor, com o foco em cada painel, **a ação esperada do
      editor executou** (espião nos manipuladores) e **nenhuma** da principal.
    - **(b)** Com a principal ativa, as ações dela executam como antes.
    - **(c)** Com a lista de completar aberta, `↑`/`↓`/`Enter`/`Esc` vão à lista; com um menu
      aberto, ao menu.
    - **(d)** Os caracteres AltGr do ABNT2 (`/ ? ° ª º § ¹ ² ³ £ ¢ ¬`) digitados no editor
      aparecem no texto (12/12).
    - **(e)** `´`+`a` pelo método de entrada dá `á` (5 compostos).
    - **(f)** Duas janelas do editor (dois livros): as teclas agem só na ativa.
  - `janela.py` com total de linhas **depois ≤ antes do passo** — `(Get-Content …\qt\janela.py).Count`
    gravado no começo do passo, com a árvore como estava, de modo que a mudança pré-existente de
    outra sessão fica na base.
  - Os percursos antigos (`percurso --fluxo livro|casa`) continuam PASSOU.
- **Sabotagem.** Cada uma tem de reprovar:
  - `teclas_cruzadas --sabotar sem_dono` (a principal recebe);
  - `engole_tudo` (o dono engole sem executar: (a) cai);
  - `sem_popup` (a guarda intercepta o pop-up: (c) cai);
  - `altgr_como_atalho` ((d) cai);
  - `teclado --sabotar` (doca sem nome);
  - `minimo --sabotar doca_fixa`.
- **Saída:** a janela onde os passos seguintes pintam.
- **Nível:** forte.
- **Desfazer:** remover a aba; a rota nova tem o interruptor `CVOFF_ROTA_LEGADA=1` até a fusão do
  ramo; o `AppState` v7 lê v6.

### H12 — O editor de código (v1)

- **Governa:** spec S5, D4, R3.2, R3.3, §5.5.
- **Arquivos:**
  - S `ui/widgets/editor_de_codigo.py`, `ui/widgets/margem_do_codigo.py`;
  - S `editor/completar.py`, `editor/tags.py`, `editor/dobras.py`;
  - T `ui/tokens.py` (papéis `CODIGO_*`, `SUBLINHADO_PROBLEMA` onda, `SUBLINHADO_DUVIDA`
    pontilhado, `LINHA_ATUAL`, `PAR_DE_TAG`, `OCORRENCIA_DE_BUSCA`), com pares;
  - A `contraste.py`: **descoberta** das cores usadas, medida **nos pixels** e forma dos
    indicadores;
  - A `bloqueio.py`, A `editor_abertura.py`; testes.
- **Briefing.**
  - O protótipo do H2 (ou do H2b) vira componente.
  - **O contraste que o crítico exigiu não é o dos pares declarados:**
    - **(1) descoberta:** o portão enumera, em tempo de execução, todo `QTextCharFormat` do
      realce e toda `ExtraSelection`, e reprova a cor que não for papel declarado.
    - **(2) pixels:** uma fixture com todo tipo de token, seleção, linha atual, par de tag,
      ocorrência de busca, os dois indicadores sobrepostos e uma dobra, renderizada nas três peles,
      no escuro e no alto contraste. O contraste é medido no pixel do glifo contra o fundo local:
      **todo texto de tamanho normal — texto comum e cada token — ≥ 7:1**; texto grande (≥ 18 pt,
      ou ≥ 14 pt em negrito, pelo tamanho calculado) ≥ 4,5:1; indicadores ≥ 3:1.
    - **(3) forma:** dúvida e problema com estilos de sublinhado diferentes (onda × pontilhado),
      conferidos também sob simulação de deuteranopia, protanopia e tritanopia.
  - `Esc` fecha a lista de completar, não a janela.
- **Tarefas.** As funções da S5; um caso dourado **observável** e uma sabotagem por função; os três
  portões de contraste.
- **Portão.**
  - `bloqueio --janela editor --operacoes abrir_2mb,digitar_500kb_tudo_ligado,dobrar,desfazer_100,colar_100kb,trocar_arquivo`
    ≤ 16 ms (3×).
  - `contraste` (1)(2)(3) PASSOU.
  - `editor_abertura` ≤ 800 ms no projeto sintético de 300 capítulos do H2.
  - **Casos dourados por função**, cada um lido do widget e não da chamada:

    | função | casos | o que se observa |
    |---|---|---|
    | realce | 30 | a classe de token em cada posição = a do `lexico.py` |
    | margem | 10 | números de linha pintados, marcadores nas linhas esperadas |
    | indicadores | 20 | as `ExtraSelection` com os intervalos e os estilos esperados |
    | completar | 20 | a lista esperada |
    | fechar tag / par de tag | 15 cada | texto e realce esperados |
    | dobras | 10 | as linhas visíveis esperadas |
    | desfazer | 20 | texto **e** cursor byte a byte |
    | colar como texto simples | 10 | a área de transferência com HTML → só o texto |
    | invisíveis | 5 | as marcas de espaço e tabulação desenhadas |
    | busca simples | 15 | a seleção no intervalo esperado |
    | escala 150 %/200 % | 4 | métricas da fonte multiplicadas, nenhum corte (o `texto_pintado`) |
    | trilha de pão | 10 | o caminho esperado para o cursor |
- **Sabotagem.** Cada uma tem de reprovar:
  - `realce_sincrono`;
  - `cor_solta` (uma cor em hexadecimal no realce: (1) cai);
  - `so_cor` (dúvida com o mesmo estilo do problema: (3) cai);
  - `contraste --sabotar` (um token a 5:1: (2) cai);
  - `funcao_nula:<nome>` para **cada** linha da tabela (a função vira nada: os casos dela caem).
- **Saída:** o painel de código.
- **Se reprovar por limite do componente** — bloqueio, UIA, ou uma função que o `QPlainTextEdit`
  não sustenta —, a D4 reabre: roda o H2b, e o H12 é refeito sobre o componente escolhido
  (mutação no §10). Reprovação por defeito de implementação é consertada aqui mesmo.
- **Nível:** padrão.
- **Desfazer:** voltar ao protótipo.

### H13 — O Resultado pelo MuPDF (Leitor de reserva e Página)

- **Governa:** spec D3, S6, R4.1, §5.5.
- **Arquivos:**
  - S `editor/previa.py` (protocolo e a fila «a última vence»);
  - S `editor/previa_mupdf.py` (função de módulo no processo de trabalho: `Story` + `Archive` com
    CSS, SVG e fontes com cmap por `typeset/fonts.subset_font`);
  - S `ui/views/editor_html/previa.py`;
  - A `previa.py`; testes.
- **Briefing.**
  - O PyMuPDF segura o GIL (43–49 ms por página, T `processo_de_trabalho.py:1-15`): o leiaute roda
    no processo de trabalho, por função de módulo picklável.
  - `element_positions` dá os retângulos; o clique vira elemento e, pelo texto da página e pelo
    mapa do H9, caractere.
  - Arquivo mal formado: a última página boa, com a faixa.
  - Fonte sem cmap: o validador avisa.
- **Tarefas.** O motor, os modos Leitor (contínuo) e Página (A5/A4/6"), o escuro, o portão.
- **Portão** (`previa --motor mupdf`, projetos do H8):
  - tecla → página visível repintada, p95 ≤ 400 ms em 260 KB (3×);
  - clique → elemento certo em 100 % de 400 pontos (semente 42);
  - hostil: 0 recursos fora do projeto;
  - **fidelidade:** a sequência de palavras da página renderizada é igual à do XHTML exportado
    daquele arquivo;
  - `bloqueio --janela editor` com a prévia ligada ≤ 16 ms.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_descartar` (o p95 estoura);
  - `archive_aberto` (o hostil carrega `win.ini`);
  - `previa_congelada` (não atualiza: a fidelidade cai depois de uma edição).
- **Saída:** pré-visualização sem dependência nova.
- **Nível:** padrão.
- **Desfazer:** desligar o painel.

### H14 — O Resultado pelo Chromium (componente sob demanda)

- **Governa:** spec D3, R1.13, R1.15, R4.1, §5.7. **Espera:** Q2 = (a) e o H1 aprovado; senão muta.
- **Arquivos:**
  - `packaging/webengine_manifesto.json` (rodas, versões, SHA-256, tamanhos);
  - o componente no assistente de primeira execução (e `--de-pasta`);
  - `packaging/coletar_licencas.py`;
  - `packaging/build_windows.py` (o tamanho do componente em linha própria do `bundle.json`) e o
    teste do pacote;
  - S `editor/componente_chromium.py` (carregar de `runtime\webengine\`, conferir a versão);
  - S `ui/views/editor_html/previa_chromium.py` (perfil fora do registro, configurações do R4.1,
    interceptador, esquema `caissa-projeto:`, ponte no *ApplicationWorld*, remendo de DOM
    vendorizado MIT);
  - o inspetor, o escuro, os dispositivos;
  - A `previa.py` (`--motor chromium`, `--hostil`).
- **Briefing.**
  - O H1 provou a sonda; este passo torna produto o que ela provou, sem furar o teto do
    instalador.
  - A primeira coisa a medir: a ponte no *ApplicationWorld* roda com o JavaScript da página
    desligado.
  - O manifesto viaja no instalador.
  - Instalação em pasta parcial e renomeação no fim; abortada, a parcial é apagada; «Remover»
    volta ao MuPDF.
- **Tarefas.** O componente, o painel, o inspetor, os portões no Python **e no `.exe`**.
- **Portão.**
  - `previa --motor chromium`:
    - frio ≤ 1,5 s;
    - remendo p95 ≤ 150 ms em 260 KB (3×);
    - hostil 0 requisições e 0 scripts;
    - fidelidade como no H13;
    - memória ≤ +350 MB.
  - **No `.exe`, nesta máquina e na limpa:**
    - componente instalado **da pasta** (sem rede) → o editor desenha a fixture;
    - instalação abortada a 50 % → estado «falhou», parcial apagada, MuPDF ativo;
    - remover → MuPDF ativo;
    - roda adulterada (1 byte) → recusada pelo SHA-256.
  - Instalador ≤ 150 MB e componente dentro do orçamento (download ≤ 150 MB, instalado ≤ 300 MB),
    **os dois** no `bundle.json` e conferidos pelo teste do pacote.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_interceptador`;
  - `js_ligado`;
  - `sem_hash` (aceita roda adulterada);
  - `sem_parcial` (instala por cima: o abortado deixa lixo).
- **Saída:** o modo Leitor de alta fidelidade.
- **Nível:** forte.
- **Desfazer:** remover o componente pela própria janela.

### H15 — O PDF original e o Comparar

- **Governa:** spec S7, §5.5.
- **Arquivos:**
  - T `qt/visor.py` (`realcar(retangulos_pt, papel)`, `clicado_em`);
  - T `ui/tokens.py` (`ORIGEM`, `DUVIDA`, `SELECAO`, com pares);
  - T `qt/casca_do_editor_html.py` (`fabricar_visor`);
  - S `ui/views/editor_html/original.py`, S `editor/sincronia.py`;
  - `benchmarks/editor_sincronia.py` (a parte do PDF); testes.
- **Briefing.**
  - O painel é o `PainelDoPdf` (T `qt/painel_do_pdf.py:204`) fabricado pela casca: mesmo processo
    de trabalho, mesmo `quadros`.
  - O visor só desenha caixas de diagrama (T `qt/visor.py:542`); o realce de um retângulo
    qualquer é API nova.
  - Comparar acopla pela página (`pg<N>` ↔ N).
- **Tarefas.** API, painel, Comparar, «Seguir a janela principal».
- **Portão.**
  - `quadros --janela editor` ≥ 55 fps @ p95, mediana de 3.
  - Clique no PDF → bloco certo em 100 % de 400 pontos (semente 42), estratificados por tipo de
    bloco (título, parágrafo, legenda, lances, diagrama), sobre `LIVRO` p. 31–38 e `PEDIDO`
    p. 50–60.
  - Cursor → retângulo aceso ≤ 100 ms.
  - Virar página com bloqueio ≤ 16 ms.
- **Sabotagem.** `sem_sincronia`: acertos < 100 %.
- **Saída:** o painel de onde veio cada trecho.
- **Nível:** padrão.
- **Desfazer:** remover o painel; a API é aditiva.

### H16 — A revisão do OCR dentro do editor

- **Governa:** spec S8, R2.1, R5, R1.4.
- **Arquivos:**
  - S `editor/revisao.py` (a fila; aceitar e manter **pelo serviço do H7**);
  - S `ui/views/editor_html/revisao.py`;
  - A `percurso.py` (`--fluxo editor_duvida`); testes.
- **Briefing.**
  - A dúvida vem do `proveniencia.json` (H8).
  - Aceitar grava pelo serviço único, e a aba Revisão de texto **aberta ao mesmo tempo** vê a
    decisão pelo aviso de mudança.
  - Editar dentro do intervalo resolve localmente.
  - O `blind_guard` recusa decisão em página da partição cega, com a frase que diz por quê.
- **Tarefas.** A fila, as ações, o recorte, o percurso.
- **Portão.**
  - `percurso --fluxo editor_duvida --pdf $LIVRO --paginas 31-38`, **positivo:**
    - o arnês escolhe a primeira dúvida da página em ordem de leitura e troca o texto do intervalo
      por uma sentinela conhecida (`CORRIGIDO-PELO-ARNES`), numa segunda dúvida só aceita;
    - o `awkWard` da captura do usuário vem do leitor da aba Texto, não do OCR do produto, por isso
      não serve de fixture aqui.
    - Exige: ≤ 3 ações; o XHTML contém a correção; a dúvida está resolvida; a `ReviewDecision`
      tem página, retângulo e texto certos.
    - A aba Revisão de texto aberta mostra a decisão sem reabrir.
    - Depois de gerar de novo, a dúvida aceita continua aceita.
  - Dúvida em página cega recusada com a frase.
  - **O desfazer da decisão no editor** (o recibo do H7 na transação do projeto): `Ctrl+Z` depois de
    aceitar devolve a `ReviewDecision` ao estado anterior no armazém e a dúvida a pendente (20/20).
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_f8` (ações > 3);
  - `aceitar_local` (não grava: a dúvida volta ao regerar);
  - `sem_aviso` (a aba não atualiza).
- **Saída:** a verificação do OCR em contexto.
- **Nível:** padrão.
- **Desfazer:** desligar os comandos; as decisões são as mesmas da aba de revisão.

### H17 — Nada se perde, na janela

- **Governa:** spec R2.8, §5.3, `CRITIC_CHARTER` §3.3 («perda de trabalho ao fechar sem aviso»).
- **Arquivos:** S `ui/views/editor_html/seguranca.py` (diálogos de recuperação, conflito, erro de
  gravação); A `percurso.py` (`--fluxo editor_seguranca`); testes.
- **Briefing.** O crítico exigiu que «não perder trabalho» seja provado na janela, não só na
  biblioteca (H6). Cada cenário é um percurso com resultado esperado.
- **Tarefas e portão** (`percurso --fluxo editor_seguranca`, cada cenário com o esperado):
  1. Fechar o editor sujo → a pergunta; «Gravar» grava, «Descartar» descarta, «Cancelar» mantém a
     janela e o texto.
  2. Fechar a **janela principal** com o editor sujo → a mesma pergunta; «Cancelar» aborta o
     fechamento da principal.
  3. Queda (`TerminateProcess`) → reabrir → o diálogo de recuperação mostra a diferença →
     recuperar → o texto é o do diário.
  4. Abrir o mesmo livro pela segunda vez → a janela existente vem à frente; nenhuma segunda trava.
  5. Erro de gravação (arquivo somente leitura; pasta sem permissão; disco cheio simulado) → a
     frase diz o que fazer, o diário continua, nada se perde.
  6. Arquivo mudado por outro programa com a janela aberta → «recarregar / comparar / manter o
     meu»; cada opção faz o que diz.
  7. «Versões…» → restaurar uma versão de 10 gravações atrás → o texto é aquele, e a restauração é
     desfeita num passo.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_pergunta`;
  - `sem_diario`;
  - `grava_por_cima` (mudança por fora ignorada);
  - `duas_janelas_mesmo_livro`.
- **Saída:** a garantia que a carta do crítico pede.
- **Nível:** padrão.
- **Desfazer:** —

### 4.8 Crítica da fase 2

- **Codex** (a receita da memória: `-s workspace-write`, `TEMP` numa pasta própria, esforço `high`),
  com os portões reproduzidos por ele.
- **Crítico visual às cegas** (`CRITIC_CHARTER.md` §2): a janela contra o Sigil do usuário e o
  Calibre Editar Livro, na mesma página do `PEDIDO`, três peles, 1366×768 e 4K.
- Veredito em `EDITOR_HTML_CSS_CRITICAS.md` («Fase 2»).

---

## 5. Fase 3 — ferramentas de formatação

### H18 — A estrutura HTML e os arquivos do livro

- **Governa:** spec S9 (Inserir, Formatar, Editar, Livro ▸ Arquivos), R2.9.
- **Arquivos:**
  - S `editor/operacoes/estrutura.py`:
    - envolver, trocar elemento, desembrulhar, classe;
    - dividir e juntar parágrafo;
    - listas, tabela, nota, link, quebra, títulos;
    - limpar formatação;
    - consertar e embelezar.
  - S `editor/operacoes/arquivos.py`: novo, renomear com os links, dividir no cursor, juntar com o
    próximo, ordem da espinha.
  - `tests/fixtures/editor/operacoes/<op>/*.{antes,seleção,depois}.xhtml`;
  - `benchmarks/editor_operacoes.py`.
- **Briefing.**
  - Toda operação é função pura `(texto, seleção, contexto) → [TextEdit]`, no padrão de S
    `notation/text_ops.py`.
  - «Consertar e embelezar» não mexe no espaço de dentro de parágrafo.
  - Renomear, dividir e juntar arquivos atualizam todo link interno (`href="cap-02.xhtml#p55-3"`)
    numa transação.
- **Tarefas.** As operações; ≥ 10 **casos dourados** por operação (entrada, seleção, saída
  esperada); os comandos habilitados.
- **Portão.**
  - 100 % dos casos dourados.
  - 200 seleções sorteadas (semente 42) nos arquivos do H8 → bem-formado 100 %, desfazer byte a
    byte 100 %, um passo 100 %.
  - Integridade de links depois de 20 renomeações, divisões e junções: 0 links quebrados.
  - `comandos --janela editor`: todos vivos.
- **Sabotagem.** Cada uma tem de reprovar:
  - `operacao_nula` (devolve nada: os dourados caem);
  - `desfazer_em_dois`;
  - `link_quebrado` (renomeia sem os links).
- **Saída:** os menus de estrutura e de arquivos.
- **Nível:** padrão.
- **Desfazer:** desabilitar os comandos.

### H19 — O CSS: estilos, inspetor, temas, fontes

- **Governa:** spec S3b, S9 (CSS), S10, R1.14, R3.2, §5.6, §5.7. **Q6.**
- **Arquivos:**
  - S `editor/css/` (analisar, casar com `cssselect2`, especificidade, renomear classe no livro,
    regras não usadas, reformatar, «o que o DOCX não recebe»);
  - S `editor/temas/*.css` (os 9 do CB absorvidos como arquivos, com «Origem:» e GPLv3, mais
    «Caissa Clássico»);
  - S `ui/views/editor_html/estilos.py`;
  - `editor/fontes.json` e o diálogo «Fontes do livro»;
  - `packaging/coletar_licencas.py` (Noto Sans Symbols2, OFL);
  - `tests/fixtures/editor/css/renomear/` (livro de fixture com as ocorrências **contadas à mão**:
    38 de classe, 9 da mesma palavra em prosa); testes.
- **Briefing.**
  - O painel Estilos mostra as regras que casam com o elemento do cursor, em ordem de
    especificidade, com «ir para a regra» e «nova regra»; com o Chromium, também o estilo
    calculado (H14).
  - Renomear é um plano no livro inteiro.
  - Os temas cumprem o §5.6: **todo texto de tamanho normal ≥ 7:1** (texto corrido, legendas,
    notas, lances, figurinas, texto sobre realce); só o texto grande, pelo tamanho calculado
    (≥ 18 pt, ou ≥ 14 pt em negrito), ≥ 4,5:1. No claro e no escuro do leitor.
  - Fonte sem registro não embute.
- **Tarefas.** O painel, as operações, os temas, as fontes, a comparação às cegas do Q6, e o tema
  **«Leitura AAA»** (spec §5.6, 1.4.8), disponível e não padrão (Q7 = i).
  - O tema cumpre as **cinco** exigências do 1.4.8:
    - (1) **cores selecionáveis** — não fixa `color` nem `background-color` do conteúdo principal,
      só de elementos secundários (C23/C25), e nunca com `!important`;
    - (2) largura ≤ 80 caracteres;
    - (3) não justificado;
    - (4) entrelinha ≥ 1,5 e espaço entre parágrafos ≥ 1,5 × a entrelinha;
    - (5) sem rolagem horizontal a 200 %.
  - O portão mede as cinco no `LIVRO` p. 31–38 renderizado. A (1) é medida pela análise do CSS
    **e** renderizando com uma folha do usuário que troca as cores: o texto principal tem de
    assumi-las.
  - **O foco nos temas** (2.4.12/2.4.13) é provado **renderizando e com cobertura geométrica
    completa**, pelo arnês de medição Chromium do H1. Para cada link do `LIVRO` p. 31–38, focado
    por `Tab` em cada tema:
    - (a) **nada encoberto:** dentro das caixas do link (`retangulos(link)`, link de várias
      linhas incluído), `elementos_no_ponto` devolve no topo o link ou um descendente em todo
      pixel CSS; e o **indicador** — pintura, não elemento — tem 0 pixels na máscara isolada que
      faltem na máscara real (spec Apêndice D);
    - (b) **área**, na máscara real: ≥ a soma dos perímetros dos retângulos não focados × 2 px
      CSS, na escala do dispositivo;
    - (c) **contraste** ≥ 3:1 entre os dois estados, pixel a pixel, na área mínima exigida.
  - Sabotagens: `--sabotar leitura_justificada`, `cor_fixa_no_corpo` (`body { color: #222 !important }`:
    a folha do usuário não pega), `foco_apagado` e `foco_interno` (`outline: 1px; outline-offset: -1px`:
    a área não chega), `sobreposicao_na_borda` (uma faixa de 1 px sobre a borda de um link),
    `multilinha_encoberto` (a segunda linha de um link sob um bloco) e `pseudo_do_body` (um
    `body::after` absoluto sobre o contorno) reprovam.
  - **O Q7 foi respondido em 2026-09-24: (i).** O tema «Leitura AAA» é construído e fica
    disponível, sem ser o padrão. O padrão sai do Q6.
- **Portão.**
  - Renomear no livro de fixture: **38/38** de classe trocadas, **0/9** de prosa, um passo de
    desfazer.
  - O inspetor em 100 elementos lista o conjunto do `cssselect2` (100 %).
  - Os 10 temas desenham o `LIVRO` p. 31–38 com EPUBCheck 0 erros e as razões de contraste do
    §5.6 em 100 % (claro e escuro).
  - «O que o DOCX não recebe» lista exatamente os avisos esperados das fixtures negativas do H3.
- **Sabotagem.** Cada uma tem de reprovar:
  - `renomeia_texto` (prosa trocada > 0);
  - `tema_cinza` (legenda em `#595959` sobre branco = 7,0:1 passa; em `#666` = 5,7:1 tem de
    reprovar, porque é texto normal);
  - `embute_sem_registro`.
- **Saída:** o menu CSS e o tema padrão escolhido às cegas.
- **Nível:** padrão.
- **Desfazer:** desabilitar; os temas são dados.

### H20 — Localizar e substituir no livro, buscas salvas, recortes, paleta

- **Governa:** spec S9 (Localizar), R2.9, R3.5.
- **Arquivos:**
  - S `editor/busca.py` (sobre S `notation/regex_engine.py`, com os escopos arquivo, seleção,
    livro, só texto, atributos, CSS, lances e legendas);
  - S `ui/views/editor_html/localizar.py`;
  - `editor/buscas.json`, `editor/recortes.json`;
  - a paleta do editor;
  - `tests/fixtures/editor/busca/` (livro de 3 arquivos com **57** ocorrências conhecidas de 4
    padrões e **12** recusas marcadas);
  - testes.
- **Briefing.**
  - O `regex_engine` já produz `SubstitutionPlan` (cada ocorrência aceitável ou recusável, com
    ficha de desfazer).
  - Usa `regex` e cai para `re` **dizendo** (`PCRE`); a janela mostra qual está em vigor.
  - No livro inteiro, a busca é cancelável, com progresso, fora da thread.
- **Tarefas.** Painel, buscas salvas, recortes, paleta.
- **Portão.**
  - No livro de fixture: o plano lista **exatamente as 57** (0 a mais, 0 a menos), aplica as 45
    aceitas e deixa as 12 recusadas, e o desfazer devolve os três arquivos byte a byte.
  - No projeto sintético de 300 capítulos do H2 (o `PEDIDO` p. 1–300): plano ≤ 2 s fora da thread,
    com progresso e cancelamento; bloqueio ≤ 16 ms.
- **Sabotagem.** Cada uma tem de reprovar:
  - `plano_vazio`;
  - `aplica_tudo`;
  - `escopo_ignorado` (busca «só texto» casando em atributo).
- **Saída:** busca de livro com rede de segurança.
- **Nível:** padrão.
- **Desfazer:** desabilitar o painel.

### H21 — Tipografia sem estragar o xadrez

- **Governa:** spec S9 (Tipografia), R2.6, `CRITIC_CHARTER` §3.3.
- **Arquivos:** S `editor/operacoes/tipografia.py` (sobre S `typeset/typography.py`);
  `tests/fixtures/editor/tipografia/` (o corpus); testes.
- **Briefing.**
  - O risco é **o resultado e o roque**: `1-0`, `0-1`, `½-½`, `0-0`, `O-O-O` e `1.e4-e5` não viram
    meia-risca, e `Nf3` não ganha hífen.
  - Juntar `awk-`+`Ward` na quebra de linha só com o léxico.
  - Toda ferramenta produz plano.
  - **O corpus é escrito por quem não constrói:** o crítico (Codex), antes da implementação,
    ≥ 50 casos por idioma (pt, en, de, ru, es), congelado pelo SHA-256 registrado no relatório.
- **Tarefas.** As operações; o corpus congelado antes.
- **Portão.**
  - 100 % do corpus.
  - 0 tokens de notação alterados (tokenizador de S `notation/`).
  - A página do `PEDIDO` p. 55 (a da captura) sai com as aspas e os travessões certos.
  - A quebra hifenizada do OCR só se junta quando o léxico confirma a palavra junta. Uma palavra
    que o léxico não reconhece fica marcada para revisão, não «consertada» por palpite (fixture:
    10 quebras com a resposta esperada).
- **Sabotagem.** `sem_guarda_de_lance`: tokens alterados > 0.
- **Saída:** tipografia de revisor.
- **Nível:** padrão.
- **Desfazer:** desabilitar.

---

## 6. Fase 4 — xadrez

### H22 — Diagramas: posição, estilo, numeração, legenda

- **Governa:** spec R2.5, S9 (Xadrez), §5.6 (alt).
- **Arquivos:**
  - S `editor/diagramas.py` (mudar a FEN → decisão **pelo serviço do H7** → SVG → figura, numa
    transação);
  - T `qt/dialogo_de_posicao_do_editor.py` (`QDialog`: `tabuleiro_editavel` + `painel_de_recorte`
    com o recorte do PDF; entrada em `RECEITAS`);
  - `casca.editar_posicao`;
  - S `editor/estilo_do_diagrama.py`;
  - «Numerar diagramas» (plano);
  - A `percurso.py` (`--fluxo editor_diagrama`); testes.
- **Briefing.**
  - Mudar a FEN no editor **é** gravar decisão de diagrama, pelo mesmo serviço que a aba Resultado
    usa (T `qt/decisoes_de_diagrama.py`, migrado no H7). A aba Resultado aberta vê pelo aviso.
  - O SVG é derivado.
  - O `QDialog` do tronco herda acessibilidade e `Esc` e precisa de entrada em `RECEITAS`
    (`test_dialogos.py:40-68`).
- **Tarefas.** Diálogo, estilo, numeração, legenda, lado, estipulação.
- **Portão.**
  - `percurso --fluxo editor_diagrama --pdf $LIVRO --paginas 31-38`, positivo: o arnês corrige uma
    casa conhecida (FEN esperada) em ≤ 4 ações.
  - **Depois de fechar e reabrir** tudo, batem entre si: a FEN no XHTML, a da decisão gravada e a
    da aba Resultado; o hash do SVG é o de `render(fen, estilo)`; a legenda e o número estão
    inalterados; o recorte do PDF é o do diagrama.
  - «Numerar diagramas» no `LIVRO` dá a sequência esperada (1…n na ordem de leitura).
  - **O desfazer da posição no editor** (o recibo do H7): `Ctrl+Z` devolve a FEN, o SVG e a decisão
    anterior no armazém, e a aba Resultado aberta vê pelo aviso (20/20).
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_decisao` (a aba Resultado não vê);
  - `svg_velho` (não regenera: o hash cai).
- **Saída:** o diagrama como objeto editável.
- **Nível:** padrão.
- **Desfazer:** desabilitar o comando.

### H23 — Lances e notação

- **Governa:** spec R2.6, S9 (Xadrez), S10 (xadrez).
- **Arquivos:**
  - S `editor/lances.py`:
    - «Marcar lances do parágrafo»: `p.cb-movetext` → `p.cb-line` com
      `span.cb-move[data-uci][data-fen]`, pela cadeia de S `ingest/pdf/games.py` a partir do
      diagrama anterior, com a guarda `is_invention`;
    - «Verificar lances»;
    - «Converter notação» (plano);
    - «Fonte das figurinas» (CSS de `span.cb-piece` pela métrica de S `typeset/figurine.py`);
  - S `export/html.py` (leitura de `span.cb-move`);
  - `tests/fixtures/editor/lances/` (o corpus anotado);
  - testes.
- **Briefing.**
  - O `data-fen` do lance é a posição **depois** dele (MARKUP).
  - `games.attach_games` encadeia a coluna a partir do diagrama acima e encerra a cadeia quando o
    reparo inventa.
  - **O corpus anotado é de quem não constrói:** ≥ 10 parágrafos de `DEM` p. 20–25 (nativo,
    Merida) e do `PEDIDO` p. 55, com a FEN inicial, a lista de lances esperada e os UCI, anotados
    pelo crítico (ou pelo usuário) e congelados por hash.
- **Tarefas.** As quatro ferramentas; o corpus congelado antes.
- **Portão.**
  - **Corpus anotado:** 100 % dos lances esperados marcados com `data-uci`/`data-fen` certos;
    0 lances a mais.
  - **Corpus real** (`LIVRO` p. 31–38, `DEM` p. 20–25): a taxa publicada, com denominador (tokens
    de lance contados pelo tokenizador de S `notation/`). Piso: **≥ a taxa do `games.attach_games`
    nas mesmas páginas**, porque o editor não pode ler pior que o importador. 0 inventados.
  - Converter pt → en → pt é identidade em 100 % dos lances marcados.
  - A figurina assenta na linha de base: o desvio do pé do glifo, medido na página do MuPDF, é
    ≤ 2 % da altura de maiúscula.
- **Sabotagem.** Cada uma tem de reprovar:
  - `sem_legalidade` (ilegal marcado > 0);
  - `zero_lances` (não marca nada: o corpus anotado cai).
- **Saída:** o livro com lances de verdade.
- **Nível:** padrão.
- **Desfazer:** desabilitar; a marcação é aditiva.

---

## 7. Fase 5 — publicação e ciclo

### H24 — Exportar do projeto e a acessibilidade do EPUB

- **Governa:** spec D1, R2.2, R2.3, R2.4, R1.14, R4.2, S3b, S11, §5.6. **Q5.**
- **Arquivos:**
  - S `editor/exportacao.py`;
  - S `export/epub.py`: perfil legível; CSS byte a byte; fontes do registro; `page-list`;
    metadados `schema:`; recusa do R4.2; nada da máquina;
  - S `export/docx.py`: o mapa de estilo do H5 aplicado aos estilos do Word; avisos;
  - S `export/pdf.py`: o motor «via HTML» — o XHTML legível e as folhas do projeto impressos pelo
    MuPDF `Story` do H13 (mesmo leiaute da prévia Página), com os avisos da matriz do H1;
  - S `export/latex.py`: o aviso único `css-nao-suportado-no-formato` quando o documento traz folhas
    do projeto;
  - S `export/book.py` + S `ui/views/exportacao.py`: a fonte «projeto»;
  - S `ui/views/editor_html/livro.py`: metadados, capa, sumário e marcos;
  - S `editor/validacao/ace.py` (o Ace do DAISY, instalado com consentimento, versão fixa, fora do
    pacote);
  - `tests/fixtures/editor/a11y_negativo/` (≥ 20 EPUBs com um defeito cada);
  - A `percurso.py` (`--fluxo editor_exportar`);
  - `benchmarks/editor_publicacao.py`.
- **Briefing.**
  - A regra de ouro e o R2.2: estrutura por `escrever(ler(x))`, CSS byte a byte.
  - O EPUBCheck e o Ace rodam **antes** de declarar pronto.
  - A acessibilidade do livro (spec §5.6) bloqueia quando falha; `dcterms:conformsTo` só quando
    passa.
  - O corpus negativo tem: `lang` ausente, salto de título, alt ausente, alt que afirma o não lido,
    `page-list` com lacuna, `aria` mal usado, contraste de tema abaixo do §5.6, `nav` sem `toc`,
    ordem de leitura trocada, figura sem legenda acessível.
  - A pasta de fontes do usuário tem fontes de xadrez sem licença: sem registro, **não embute**.
  - **A exportação do editor não embute o IR** (`embed_ir=False`, spec R2.4).
    - A proveniência é **opcional** por nó (`IRNode.provenance`, `None` no conteúdo autoral) e, onde
      existe, traz página, retângulo, motor, confiança e nota.
    - Ela vai ao sidecar, fora do EPUB.
- **Tarefas.** A exportação, o DOCX por estilos, metadados, capa e sumário, o diálogo, o Ace, o
  corpus, o percurso.
- **Portão** (projetos `LIVRO`, `KEMERI`, `PEDIDO` p. 50–60, `DEM`):
  - EPUBCheck **0 erros**, com os avisos listados.
  - XHTML do EPUB = `escrever(ler(x))` em 100 %.
  - CSS byte a byte em 100 %.
  - Ace sem violação séria ou crítica.
  - **Corpus negativo:** a verificação própria acusa 100 % dos defeitos do escopo dela; o Ace acusa
    os do escopo dele, com o que cada um viu publicado.
  - DOCX: as fixtures positivas do mapa com o estilo do Word esperado (100 %); as negativas com o
    aviso (100 %).
  - **PDF:**
    - mesmo número de páginas que a prévia Página do MuPDF;
    - o texto de cada página igual ao da prévia (sequência de palavras);
    - as quebras nos mesmos elementos (100 %, nos 4 projetos);
    - cada propriedade CSS que o motor não desenha, segundo a matriz do H1, com o aviso esperado
      (100 %).
  - **LaTeX:** a estrutura igual à exportação LaTeX de hoje pelo IR (`semantic_diff` 0 fora de N1–N4)
    e **exatamente um** aviso `css-nao-suportado-no-formato` listando as folhas.
  - **`embed_ir` forçado:** o teste espia as opções que `editor.exportacao.exportar` passa ao
    exportador EPUB e exige `embed_ir=False` (100 % das chamadas).
  - **Sidecar no formato exato** (spec R2.4): JSON Lines, cabeçalho `caissa.proveniencia` versão 2
    com o `esquema`, registros `bloco`/`diagrama`/`partida`.
    - O `esquema` do cabeçalho é igual à introspecção recursiva das dez classes: `Provenance`,
      `Rect`, `DiagramSource`, `RecognitionResult`, `FenCandidate`, `SquareRepair`, `ReviewItem`,
      `AuditEntry`, `Decided`, `DiagramDecision`.
    - Com o relógio e o commit **injetados** nos valores fixos da fixture (spec Apêndice C), a saída
      do **serializador canônico** (não os `as_dict()`, que arredondam) é **igual byte a byte** à
      fixture dourada `tests/fixtures/editor/sidecar/v2_completo.jsonl`. Ela foi escrita
      pelo **crítico no H3** e congelada por SHA-256, e o portão confere o hash antes de usá-la. Cobre
      as dez classes com todos os campos fora do padrão e listas não vazias de `FenCandidate` e
      `SquareRepair`.
    - O sidecar relido é **igual em profundidade** ao escrito.
    - O teste de **invariantes** com o relógio e o commit reais: `gerado_em` ISO 8601 a menos de
      5 s do relógio do teste; `commit_da_suite` igual a `git rev-parse --short=12 HEAD`.
    - A migração de `v1_de_hoje.jsonl` (o exportador atual) é igual byte a byte a
      `v1_migrado_esperado.jsonl`, pelo mapeamento campo a campo do Apêndice C, com `extras_v1`
      para o que ele não nomeia.
    - os nós sem proveniência não têm registro;
    - o sidecar relido reconstrói o mesmo mapa;
    - exige o item 1 do H4.
  - **Varredura do EPUB por lista de permissão** (spec R2.4 a–e):
    - só os tipos de arquivo permitidos, 0 JSON;
    - metadados do OPF só da lista fechada;
    - atributos de cada XHTML iguais aos do arquivo do projeto, **e** nenhum com nome de campo de
      proveniência (`data-confidence`, `data-engine`, `data-note`…), mesmo se escrito pelo usuário;
    - **0 nomes da lista proibida**, gerada por introspecção recursiva das dez classes (`snake_case`
      e `kebab-case`), nas posições estruturadas de **todo** recurso publicado:
      - nome de atributo (XHTML, SVG, OPF, NCX);
      - `property`/`name` de `<meta>`;
      - propriedade personalizada de CSS;
      - chave de objeto em texto com forma de JSON.

      Menos a lista de exceção fechada do teste.
    - 0 caminhos absolutos, letras de unidade ou nomes de usuário.
  - **Os AAA da tabela** (spec §5.6), cada um com fixture negativa acusada e o livro limpo:
    - 1.2.x: 0 mídia;
    - 1.3.6: 100 % das seções e notas com papel;
    - 1.4.5/1.4.9: **0 imagens de texto** — a transcrição substitui a imagem — para declarar
      conformidade;
    - 2.1.3, 3.3.x: 0 interativos além de `<a href>`;
    - 2.2.x, 3.2.5: 0 `meta refresh`, 0 script;
    - 2.3.x: 0 animação;
    - 2.4.8: `toc`, `landmarks` e `page-list` presentes;
    - 2.4.9: 100 % dos links com propósito próprio;
    - 2.4.12/2.4.13: a prova do H19 aplicada a **todo** link do livro — `elementsFromPoint` dentro
      das caixas, a máscara isolada contra a real para o indicador, área ≥ perímetros × 2 px e
      contraste 3:1 na máscara real —, e 0 `fixed`/`sticky`;
    - 2.5.5: 100 % dos alvos **fora de linha** (entradas do `nav`, links de bloco) com ≥ 44×44 px
      CSS, medidos pelos retângulos do `element_positions` nas páginas renderizadas;
    - 3.1.3: o **inventário de candidatos** (spec §5.6) — símbolos usados, termos do léxico
      presentes, palavras que o dicionário geral do idioma não conhece e que não são notação, e as
      marcadas pelo usuário — com 100 % dos candidatos decididos («definir» / «uso comum»), 100 %
      dos «definir» com definição no glossário, e a **atestação de leitura integral por capítulo**
      no modo «Revisão de termos» (quem percorreu, quando e o **SHA-256 do texto do capítulo**), em
      100 % dos capítulos e **com o hash igual ao do texto atual** (`editor/glossario/revisao.json`). Sem ela, o 3.1.3 não conta como cumprido, e o relatório
      diz que a completude do jargão é atestada por pessoa, não medida;
    - 3.1.4: 100 % das abreviaturas da lista com `<abbr>`;
    - **Q7 = (i)** (respondida em 2026-09-24): a opção AAA formal não foi escolhida, e os portões
      dela (o tema «Leitura AAA» ativo, o resumo simples por capítulo) ficam fora do H24.

    `conformsTo`: **AA** quando o AA inteiro passa (Q7 = i); nenhum quando sobra imagem de texto.
    O relatório lista cada AAA cumprido.
  - **AAA 1.4.6:** 0 trechos de texto abaixo do limiar em todas as páginas renderizadas dos 4
    projetos, com o tema **e** com uma folha arbitrária de fixture
    (`tests/fixtures/editor/css/arbitraria.css`).
  - 0 fontes sem registro.
  - `percurso --fluxo editor_exportar`: EPUB válido em ≤ 2 ações.
- **Sabotagem.** Cada uma tem de reprovar:
  - `embute_sem_licenca`;
  - `caminho`;
  - `css_silencioso`;
  - `ace_desligado` (o corpus negativo deixa de ser acusado no escopo do Ace);
  - `exporta_perfil_maquina` (a igualdade estrutural cai);
  - `pdf_por_outro_leiaute` (o PDF impresso com outra largura de página: as páginas divergem da
    prévia);
  - `embute_ir` (`embed_ir=True`): a varredura acha proveniência;
  - `css_cinza` (a folha arbitrária com `p { color: #666 }`, 5,7:1): o AAA 1.4.6 reprova;
  - `metadado_de_maquina` (um `<meta property="caissa:engine">` no OPF): a lista de permissão acusa;
  - `sidecar_parcial` (o sidecar sem os blocos): a completude cai;
  - `link_seta` (a volta da nota só com «↩»): o 2.4.9 cai;
  - `alvo_pequeno` (entradas do `nav` com `line-height: 1` a 12 px): o 2.5.5 cai;
  - `foco_apagado` (`a:focus { outline: none }`): o 2.4.13 cai;
  - `data_confidence_no_projeto` (o usuário escreve `data-confidence` num `<p>`): a varredura acusa;
  - `imagem_com_alt` (a região mantida como imagem, só com a transcrição no alt): o 1.4.9 cai;
  - `sidecar_sem_campo` (o sidecar sem `note`): a igualdade de conjuntos cai;
  - `overlay_absoluto` (um bloco `position: absolute` sobre um link): o link sai encoberto;
  - `jargao_sem_definicao` («zugzwang» no texto e fora do glossário): o 3.1.3 cai;
  - `termo_fora_do_lexico` (uma palavra inventada, que nenhum dicionário conhece, no texto e sem
    decisão): o inventário a lista como candidato não decidido e o 3.1.3 cai;
  - `capitulo_sem_leitura` (um capítulo sem a atestação de leitura integral): o 3.1.3 cai;
  - `edita_depois_de_atestar` (muda uma palavra de um capítulo já atestado): a atestação vence e o
    3.1.3 cai;
  - `sem_square_repair` (o sidecar sem a lista de `SquareRepair`): a igualdade byte a byte cai;
  - `omite_padrao` (o escritor omite campos de valor padrão): a igualdade byte a byte cai;
  - `usa_as_dict` (o sidecar escreve `ReviewItem`/`AuditEntry` pelos `as_dict()` que arredondam):
    a igualdade byte a byte cai;
  - `relogio_real` (o escritor ignora o relógio injetado): o cabeçalho diverge da fixture e a
    igualdade cai; o teste de invariantes, com o relógio real, continua verde;
  - `pseudo_do_body` no livro: um `body::after` sobre um link do projeto é acusado;
  - `migra_sem_extras` (a migração descarta uma chave da v1 que a tabela não nomeia): a migração
    dourada cai;
  - `document_path_no_opf` (`<meta property="caissa:document_path">`): a lista proibida acusa;
  - `latex_mudo` (sem o aviso único).
- **Saída:** o livro publicado do que foi editado.
- **Nível:** forte.
- **Desfazer:** a exportação da principal volta a reimportar.

### H25 — Regerar e fundir (três vias por bloco)

- **Governa:** spec R2.1, §5.3.
- **Arquivos:** S `editor/fusao.py`, S `ui/views/editor_html/fusao.py`, `benchmarks/editor_fusao.py`,
  testes.
- **Briefing.**
  - Entradas novas chegam a páginas `EDITADA`/`REVISADA`: um modelo de livro melhor, decisões da
    aba Revisão de texto (H16), FENs da aba Resultado (H22).
  - **Base** = `gerado/<n>/`; **nossa** = o arquivo; **deles** = a geração nova.
  - Por bloco (`id`): um lado mudou → aplica e diz; os dois → proposta.
  - Bloco dividido, juntado ou apagado de um lado é caso de teste.
- **Tarefas.** A fusão; o painel; ≥ 30 cenários com o esperado, incluindo decisão de revisão
  aceita depois da edição local e FEN corrigida na aba Resultado com a legenda editada no editor.
- **Portão.**
  - 100 % dos cenários.
  - 0 sobrescritas silenciosas.
  - Desfazer a fusão volta byte a byte.
- **Sabotagem.** `deles_vence`: sobrescritas > 0.
- **Saída:** re-OCR sem medo.
- **Nível:** forte.
- **Desfazer:** voltar à regra «confirmação + versão».

### H26 — A aba Texto lê pelo produto, e a formatação e os diagramas vão ao editor

- **Governa:** spec Q1 (respondida: C), §0.2 (os diagramas como posições), §2.1, §5.2. **Depende
  de:** H0b, H8; a mudança da digitação da aba Texto **commitada** por quem a fez (a tarefa separada
  em andamento).
- **Arquivos:**
  - T `qt/painel_de_texto.py`:
    - o «Ler folha» pede ao produto a página do IR daquela folha: o `import_pdf` da página, com a
      decisão de fonte do importador e a fusão onde ela manda ao OCR, **fora da thread da janela**;
    - o combo de motor ganha «Produto» como **padrão**, e `glifo` e `camada` ficam como opções de
      diagnóstico;
    - o bloco de diagrama mostra o recorte, como hoje. O painel corta a folha pela `bbox` do bloco,
      em pontos × dpi/72 (`_recorte`, T `qt/painel_de_texto.py:620-642` na árvore de trabalho,
      `478-494` no HEAD). Embaixo vêm o número, o lado a jogar, a estipulação e a legenda;
    - o comando «Enviar a folha ao Editor HTML/CSS» e a faixa «esta página está no Editor HTML/CSS».
  - O tronco importa a suíte do jeito que já importa: tarde, com a pergunta «existe?» (T
    `qt/painel_de_rotulagem.py:31-40`). Sem a suíte, a aba fica no leitor antigo e diz isso na
    faixa.
  - T `text/pagina.py`: `BlocoDeDiagrama` ganha `fen`, `lado`, `numero`, `legenda` e `estipulacao`,
    todos com padrão vazio. O `.cvtxt` antigo abre como antes.
  - T `text/do_produto.py` (novo): a página do IR vira a `PaginaLida` que o painel já desenha, com
    as cores de confiança e as ferramentas de hoje.
    - O texto: blocos, linhas, retângulos em pontos, confiança e figurinas.
    - A procedência de cada bloco: `camada` quando todos os tokens vêm da camada; senão, a da
      fusão.
    - **Os diagramas:** cada diagrama do IR vira um `BlocoDeDiagrama` com a `bbox` do IR em pontos,
      o `indice` da lista do produto e os campos novos preenchidos do IR.
  - S `editor/ponte_texto.py`: as corridas do `DocumentoRico` viram o contrato (negrito, itálico,
    estilo e cor de autor como classe), e a página entra como `EDITADA`, com versão.
    - Cada marca `[Diagrama N]` volta ao diagrama do IR pelo `indice`.
    - Ela vira o `figure.cb-diagram[data-fen][data-stm]` do perfil legível (spec §5.2), com a
      legenda e a estipulação no `figcaption`.
    - O texto `[Diagrama N]` nunca chega ao XHTML.
  - Testes.
- **Briefing.**
  - Com o Q1 = C, nos estratos com veredito «produto», as duas abas mostram **a mesma leitura**, a
    mais precisa: a do produto, com a configuração do H0b.
  - Os diagramas vêm do OCR de diagramas do produto, como o usuário pediu. A marca `[Diagrama N]`
    continua sendo o que a pessoa move no texto (`text/pagina.py:593-601`), mas o diagrama que ela
    representa é o do IR, com a FEN.
  - **Fora da thread da janela.** O `bloqueio` decide entre a `Tarefa` e o processo filho do passo
    15 do OCR_UI (T `processo_de_trabalho.py`). Uma `QThread` não tira da janela o trabalho que
    segura o GIL, e o `get_pixmap` do PyMuPDF segura (medido no passo 15).
  - **As cores.** A confiança da fusão já está na escala calibrada do árbitro (passo B6), e os
    cortes da aba são 0,30 e 0,75 (T `text/documento.py:42`).
    - A aba pinta de «tranquilo» os blocos de procedência `camada` e `humano`, qualquer que seja a
      confiança (`text/documento.py:56-69`).
    - Por isso o portão (e) só conta os blocos lidos por OCR.
  - **A decisão de fonte de cada página** (`_decide_source`, `importer.py:953-1043`) diz o que a aba
    faz. São sete saídas:
    - `ocr` → estrato digitalizado. A aba mostra a página do IR;
    - `text-layer`, `text-layer+ocr` e `text-layer/review` → estrato nativo. A aba mostra a página do
      IR;
    - `blank` → a aba abre vazia e **editável**, e diz «página sem texto». O que a pessoa digitar
      é dela: «Enviar ao Editor» envia a folha como `EDITADA`, com a procedência «humano». A ponte
      só diz «nada a enviar» se a aba está vazia;
    - `image-only` (a página é imagem e o OCR do produto não deu texto, `importer.py:975-981`) e
      `rejected` (a camada foi recusada e o OCR não deu texto, `importer.py:982-987`) → o produto
      não tem texto para a página. A aba lê com o leitor antigo e diz na faixa o motivo que a
      decisão de fonte deu. A ponte envia a folha como `EDITADA`, com a procedência «leitor da
      aba».

    **O veredito da aba** (a segunda saída do H0b) vale por cima disso: nas páginas de um estrato
    com veredito «leitor antigo», a aba usa o leitor antigo e diz por quê. Não é roteamento da
    fusão, que tem uma configuração só.
  - O que a pessoa corrige ou formata na aba Texto chega ao projeto pela ponte, e não se perde nem
    se duplica.
- **Portão.**
  - (a) Nas páginas `LIVRO` p. 31–38 e `PEDIDO` p. 50–60, nos estratos em que a aba troca de
    leitor, o texto normalizado da aba Texto é o do IR do produto (100 % das páginas).
  - (b) Negrito, itálico, estilos e cores de autor de 20 folhas chegam ao XHTML (100 %).
  - (c) `bloqueio` ≤ 16 ms ao ler a folha.
  - (d) A faixa aparece em 100 % das páginas do projeto.
  - (e) Nas regiões com verdade do H0, só nos blocos lidos por OCR, a fração de palavras erradas cai
    de faixa em faixa de cor: vermelho > amarelo > verde.
  - (f) **Os diagramas, com denominador positivo.**
    - **A fixture de IR:** uma página do IR montada no teste, com 2 diagramas de campos conhecidos
      e **todos não vazios** (FEN, lado a jogar, número, legenda e a estipulação «Mate em 2»).
      - Os 2 aparecem na aba com os campos iguais aos do IR.
      - Depois de «Enviar ao Editor», os 2 viram `figure.cb-diagram` com a mesma `data-fen` e o
        mesmo `data-stm`, e a legenda e a estipulação no `figcaption`.
      - O XHTML tem 0 ocorrências de `[Diagrama`.
    - **As páginas reais** (`LIVRO` p. 31–38): o relatório conta os diagramas que o IR reconhece
      com FEN. Com zero, o portão reprova «sem diagramas para medir».
      - 100 % aparecem na aba com os campos do IR e com o recorte certo: IoU ≥ 0,9 entre a `bbox`
        do bloco e a caixa do diagrama do IR, em pontos.
      - 100 % viram `figure.cb-diagram` com a mesma `data-fen`.
      - O XHTML tem 0 ocorrências de `[Diagrama`.
  - (g) **As sete saídas da decisão de fonte:** um teste por saída, com uma página de IR sintética
    daquela saída.
    - Ele confere qual leitor a aba usa e o texto da faixa.
    - Ele faz **editar → enviar → reabrir**: digita uma frase na aba (na `blank`, na página vazia),
      envia ao Editor, reabre o projeto, e a frase está na página, com a procedência certa.
- **Sabotagem.** As sete têm de reprovar:
  - `leitor_antigo` (a aba lê pelo leitor do tronco): (a) cai;
  - `sem_estilo`: (b) cai;
  - `cores_trocadas` (os cortes invertidos): (e) cai;
  - `sem_diagramas` (o adaptador descarta os diagramas): (f) cai na fixture de IR, com 0 de 2;
  - `diagrama_como_texto` (a ponte escreve a marca como texto): (f) cai na fixture de IR, com 2
    ocorrências de `[Diagrama` no XHTML;
  - `sem_rota` (a saída `image-only` fica sem política e cai no padrão): (g) cai;
  - `branco_descarta` (a ponte não envia a página `blank`): (g) cai na `blank`, com a frase
    perdida.
- **Nível:** forte.
- **Desfazer:** o combo volta ao leitor do tronco como padrão; os campos novos do diagrama e a ponte
  são aditivos.

### H27 — (opcional) PDF e prévia Página pelo Chromium; abrir EPUB do Caissa ou do CB

- **Governa:** spec S6, R2.2c, §6.
- **Arquivos:**
  - S `ui/views/editor_html/previa_chromium.py` (`printToPdf` com `@page`, rasterizado pelo
    processo de trabalho): a prévia Página e o PDF pelo Chromium quando o componente existe;
  - S `editor/importar_epub.py`;
  - «Abrir no Sigil» (exporta um EPUB temporário e abre o `Sigil.exe` configurado);
  - testes.
- **Briefing.** O PDF pelo MuPDF já existe desde o H24. Este passo acrescenta o motor de CSS
  completo à prévia Página e ao PDF, com a mesma regra: PDF = prévia.
- **Portão.**
  - Com o Chromium, o PDF impresso e a prévia Página batem (mesmas páginas e quebras) em 3 livros.
  - Um EPUB do CB aberto, exportado e validado pelo `CB validate` dá 0 erros de contrato.
- **Sabotagem:** `sem_arroba_page`.
- **Nível:** padrão.
- **Desfazer:** remover as opções.

### 7.5 Crítica da fase 5 e do programa

- **Codex** sobre a fase.
- **Crítico visual às cegas:** um EPUB do projeto contra o livro original lado a lado
  (`CRITIC_CHARTER` §2.2, F8) e contra uma página da Quality Chess ou da New in Chess (F7).
- Veredito em `EDITOR_HTML_CSS_CRITICAS.md` («Fase 5»).

---

## 8. Humano

| item | quando | por quê |
|---|---|---|
| ~~Q1~~ | **respondida em 2026-09-24: C** (a combinação guiada por medição) | o H0 mede, o H0b combina, o H26 unifica a aba Texto |
| a troca precisão × tempo | **só** se a configuração que ganha no H0b passar de 2 × o tempo por página | o ganho e o custo publicados pelo H0b; a resposta fica gravada no JSON da configuração e no relatório; sem ela, a configuração fica desligada |
| rotular mais verdade nativa (`caissa-rotular`) | **só** se a candidata do H0b mudar leituras nativas e a célula nativa ficar sem evidência (a cega tem hoje 8 regiões nativas) | sem ela, a combinação não liga (falha fechada); o relatório do H0b diz quantas regiões e páginas faltam |
| Q2 com os números do H1 | antes do H14 | o componente Chromium |
| Q3 | antes do H5 | o contrato `cb-*` |
| Q5 | antes do H24 | fontes sem licença declarada |
| ~~Q7~~ | **respondida em 2026-09-24: (i)** (altíssimo padrão) | H19 e H24 desbloqueados; o tema «Leitura AAA» disponível, não padrão |
| Q0, Q4, Q6 | quando citadas | ADRs; pasta do projeto; tema padrão (juiz às cegas) |
| habilitar o **Windows Sandbox** (recurso opcional do Windows 11 Pro; admin + reinício) ou fornecer uma VM limpa | H1, H14 | a máquina limpa que o crítico exigiu |
| consentir os downloads: rodas do QtWebEngine (H1, H14); `pywinauto` (H2); `tinycss2`/`cssselect2` no `.venv-pack` (H5); Ace do DAISY via npm (H24); `PyQt6-QScintilla` (H2b, só se preciso) | nos passos | download da internet: nome, origem e tamanho ditos ao pedir |
| confirmar a leitura do Narrador (H2) | H2 | a sonda UIA prova a interface; a pessoa confirma o uso |
| declarar a licença das fontes de xadrez que quer embutir | H19/H24 | R1.14 |
| revisar o léxico de jargão por idioma (`editor/glossario/<idioma>.json`); decidir o inventário de termos; **percorrer cada capítulo** no modo «Revisão de termos» e atestar a leitura integral | H24, só para declarar o 3.1.3 | a palavra comum usada como jargão só uma pessoa acha (spec §5.6) |
| commitar (ou pedir que se commite) a mudança da digitação da aba Texto e reconciliar `janela.py` com o `LIMITE` | antes do H26 | trabalho de outra sessão |

## 9. Crítica dos documentos

- Esta spec e este roadmap passam pelo Codex **antes** de qualquer passo.
- **Ciclo 1:** REPROVADO, 12 bloqueantes (spec §9). A versão 1.1 trata os 12.
- **Ciclo 2:** REPROVADO, 8 bloqueantes. Dos 12 do ciclo 1, 8 estavam resolvidos e 4 parciais. A
  versão 1.2 trata os 8:
  - a contagem de linhas (o comando da 1.1 estava errado);
  - os escritores de decisão e o teste de arquitetura;
  - a tabela de dependências refeita;
  - PDF pela prévia e LaTeX com aviso único;
  - o H0 com denominador e regra;
  - casos dourados por função;
  - 7:1 para todo texto normal;
  - desfazer de conflito nos dois armazéns.
- **Ciclo 3:** REPROVADO, 9 bloqueantes, mais estreitos. A versão 1.3 trata os 9 (spec §9):
  - escrita de decisão privada e teste por AST;
  - a regra A/B/C formal;
  - R1.10 harmonizado;
  - H1 → H24;
  - comportamento dourado no H2 e reabertura pelo H12;
  - AAA 1.4.6 com qualquer CSS;
  - EPUB sem IR e varredura de proveniência;
  - `janela.py` antes/depois;
  - `Recibo` por gravação.
- **Ciclo 4:** REPROVADO, 4 bloqueantes; dos 9 do ciclo 3, 5 resolvidos e 4 parciais. A versão 1.4
  trata os 4 (spec §9):
  - o desfazer do editor passa ao H16/H22;
  - a proveniência opcional, o sidecar completo e a varredura por lista de permissão;
  - a tabela de todos os AAA e o Q7;
  - a guarda de execução contra escrita crua.
- **Ciclo 5:** REPROVADO, 7 bloqueantes; dos 4 do ciclo 4, 1 resolvido e 3 parciais. A versão 1.5
  trata os 7 (spec §9):
  - «todo nó» corrigido e o sidecar comparado campo a campo;
  - atributo de máquina bloqueado mesmo vindo do usuário;
  - o `Rect` obrigatório no H4;
  - os eventos de auditoria medidos (`os.replace` dispara `os.rename`) e a canonização;
  - o 1.4.9 sem «transcrição basta»;
  - portões para cada linha «por construção» da tabela AAA;
  - o Q7 com AAA formal, sem padrão, bloqueando H19/H24.
- **Ciclo 6:** REPROVADO, 4 bloqueantes; dos 7 do ciclo 5, 5 resolvidos e 2 parciais (o sidecar e
  os portões AAA). A versão 1.6 trata os 4:
  - o esquema do sidecar fechado por introspecção;
  - as cores selecionáveis do 1.4.8;
  - o foco provado renderizando todo link;
  - o glossário com jargão.
- **Ciclo 7:** REPROVADO, 4 bloqueantes; dos 4 do ciclo 6, 1 resolvido e 3 parciais. A versão 1.7
  trata os 4:
  - o sidecar em formato exato com as dez classes;
  - a lista proibida por introspecção recursiva em posições estruturadas;
  - o foco com cobertura geométrica completa e o arnês do H1;
  - o inventário de termos com atestação.
- **Ciclo 8:** REPROVADO, 3 bloqueantes; dos 4 do ciclo 7, 1 resolvido e 3 parciais, mais um caminho
  corrompido no H4 (`\r`/`\a` interpretados pelo shell). A versão 1.8 trata os 3 e o caminho:
  - o Apêndice C com o sidecar v2 canônico, o mapeamento da v1 e as fixtures douradas do crítico;
  - o Apêndice D com o contrato executável do arnês de foco;
  - a atestação de leitura integral por capítulo no 3.1.3.
- **Ciclo 9:** REPROVADO, 3 bloqueantes; o 3.1.3 e o caminho do H4 resolvidos. A versão 1.9 trata os 3:
  - o serializador canônico próprio, sem os `as_dict()` que arredondam, e as fixtures douradas
    escritas pelo crítico no H3;
  - o encobrimento do indicador por máscara isolada, não por `elementsFromPoint` na pintura;
  - a atestação presa ao hash do capítulo.
- **Ciclo 10:** REPROVADO, 2 bloqueantes; o 3.1.3 resolvido. A versão 1.10 trata os 2:
  - relógio e commit injetáveis no cabeçalho do sidecar;
  - pseudo-elementos e pintura de ancestral neutralizados na renderização isolada, com a
    fixture `body::after`.
- **Ciclo 11: APROVADO**, sem bloqueante. Veredito: «A 1.10 pode avançar para execução dos
  passos». Os dois não bloqueantes foram tratados na versão final (a neutralização prova que
  venceu; este histórico em ordem cronológica).
- **Decisões do usuário em 2026-09-24 (versão 1.11):** Q1 = C e Q7 = (i). O H0 passou a só medir,
  nasceu o H0b (a combinação) e o H26 foi reescrito (spec §9).
- **Ciclo 12:** REPROVADO, 5 bloqueantes, todos no H0b e no H26 novos (spec §9). A versão 1.12
  trata os 5:
  - o `ler_pagina` sai da fusão (caixa por linha, e ele precisa do PDF);
  - as alavancas passam a estender o adaptador de glifos que já existe;
  - as alavancas são globais;
  - a seleção fica numa metade das páginas e a confirmação na outra;
  - o H26 carrega os diagramas.
- **Ciclo 13:** REPROVADO, 5 bloqueantes (spec §9). Dos 5 do ciclo 12, 3 ficaram resolvidos e 2
  parciais. A versão 1.13 trata os 5:
  - a configuração única e global, dita em toda parte;
  - o piso por célula e a falha fechada;
  - a medição pelo caminho do produto;
  - sabotagens determinísticas, contra fixtures;
  - os diagramas com denominador positivo;
  - as sete saídas da decisão de fonte.
- **Ciclo 14:** REPROVADO, 3 bloqueantes (spec §9). Dos 5 do ciclo 13, 3 ficaram resolvidos e 2
  parciais. A versão 1.14 trata os 3:
  - as duas saídas do H0b: a configuração global e o veredito da aba por estrato;
  - a escolha em `dev` + `calib` e um só teste final, unilateral, na cega;
  - a página em branco editável, e editar → enviar → reabrir nas sete saídas.
- **Ciclo 15:** REPROVADO, 1 bloqueante (spec §9). Os 3 do ciclo 14 ficaram resolvidos. A versão
  1.15 trata o bloqueante:
  - a leitura cega do H0b passa a ler também os três modos do leitor da aba;
  - o veredito de cada estrato vem do H0 só quando o produto final lê igual ao de hoje em todas as
    páginas medidas, com a prova escrita;
  - nos outros estratos, o veredito vem da cega.
- **Ciclo 16:** REPROVADO, 2 bloqueantes (spec §9). A versão 1.16 trata os 2:
  - o H0 publica a ordem de leitura;
  - o piso vale também no caso (a);
  - a igualdade canônica fica definida e testada.
- **Ciclo 17:** REPROVADO, 2 bloqueantes (spec §9). A versão 1.17 trata os 2:
  - as cinco métricas passam a ser campos obrigatórios, e métrica ausente reprova (sabotagem
    `sem_ordem`);
  - o caso (a) abaixo do piso ganha a fixture `tests/fixtures/editor/h0b/veredito_caso_a_abaixo_do_piso.json`, com a saída esperada, e a
    `piso_so_na_cega` roda contra ela.
- **Ciclo 18:** APROVADO, sem bloqueante. A versão final trata os dois não bloqueantes (spec §9).
- Os vereditos e o que cada ciclo mudou ficam em `quality/EDITOR_HTML_CSS_CRITICAS.md`
  («Documentos»).

## 10. Mutações

| data | passo | mutação | por quê | quem |
|---|---|---|---|---|
| — | — | — | — | — |

**Protocolo:**
- Um passo que o portão prova impossível **não** baixa a régua em silêncio: ele muta, com linha
  aqui.
- Formas de mutar: dividir, inserir, pular, reordenar, abandonar.
- Toda mutação traz: o número que a motivou, com o comando; a cláusula da spec afetada; a
  aprovação (construtor + crítico).
- Mutação que muda D1–D5, ou uma resposta Q1/Q2 que escolha a outra opção, reabre a spec (nova
  versão).

## 11. Anti-padrões proibidos neste programa

1. Regerar o capítulo inteiro a cada tecla (REVIEW_1 do `Plugins_Sigil_Edit`).
2. `rehighlight()` do documento inteiro, ou PyMuPDF, na thread da janela.
3. Cor em hexadecimal no widget; rótulo só em `toolTip()`; `nomear_tudo` fora de
   `acessibilidade.py`; string de tecla fora das tabelas.
4. Gravar arquivo do projeto ou de decisão sem temporário + `os.replace`; gravar decisão fora do
   serviço do H7; `except Exception` que engole e segue.
5. Substituir no livro, converter notação ou aplicar tipografia sem plano revisável.
6. Renomear ou remover classe do contrato sem versão e migração.
7. Misturar base 0 e base 1 de página fora de `editor/paginas.py`.
8. Chromium com JavaScript da página ligado; recurso remoto «porque é só uma fonte».
9. Fixture que monta o dado de um jeito que o produto nunca monta; corpus de verificação escrito
   por quem constrói (H21, H23).
10. Portão sem instrumento, sem `--saida`, sem sabotagem, com uma execução só, ou que aprova a
    implementação nula.
11. Fonte de xadrez embutida sem licença no registro.
12. Tocar em `labeling/`, `data/` ou `editor/` do usuário a partir de um arnês.
13. Editar por cima de caminho que outra sessão deixou sujo (a barreira do §0.3).
14. Medir o pacote excluindo o componente que o editor exige.
