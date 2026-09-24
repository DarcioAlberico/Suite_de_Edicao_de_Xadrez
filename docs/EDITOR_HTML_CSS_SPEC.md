# Especificação — Editor HTML/CSS (janela dedicada: código, resultado e PDF original)

> **Data:** 2026-09-23 · **Versão:** 1.10 — **APROVADA pelo Codex no ciclo 11**, depois de dez ciclos
> reprovados (12, 8, 9, 4, 7, 4, 4, 3, 3 e 2 bloqueantes; §9 diz o que cada um mudou) · **Deriva de:** o pedido do usuário de
> 2026-09-23 (§0.1) e do mapeamento do
> código feito na mesma data (§2 — cada fato com arquivo:linha, os números com o comando no
> Apêndice A).
> **Formato:** contrato de capacidade (capacidade → o que existe → restrições → decisões → contrato
> de implementação → não-objetivos → questões abertas → passagem). É o que precisa ser verdade
> **antes** de qualquer passo do `EDITOR_HTML_CSS_ROADMAP.md` começar; cada passo de lá cita a
> cláusula daqui que o governa. Críticas: `quality/EDITOR_HTML_CSS_CRITICAS.md`.
> **Não substitui** `SPEC.md` nem `OCR_UI_SPEC.md`: estende a `SPEC.md` §8.3 (EPUB 3), §8.4 (HTML) e
> §10 (interface). Onde conflita com elas, o §3.6 diz onde e por quê.
> **Abreviações:** **T** = tronco `..\ChessVisionOFF_Puro\src\chess_diagram_ocr\`; **S** =
> `src\caissa\` desta suíte; **CB** = `..\Sigil-master\src\Resource_Files\python3lib\sigil_chess\`
> (o pacote Python do fork «ChessBook Studio» do Sigil); **MARKUP** =
> `..\Sigil-master\chessbook\MARKUP.md`; **A** = `S\ui\audit\`. Relatórios citados sem pasta estão
> em `docs/quality/`. Os passos `H0…H27` são os do roadmap.

---

## 0. Em uma tela

### 0.1 O pedido

> «Editor HTML/CSS com dois frames: um do HTML/CSS, outro para visualizar o PDF ou o resultado da
> formatação do HTML. Editar o HTML, ver o PDF e o resultado da formatação. Clico na aba Editor
> HTML/CSS e abre uma janela dedicada para edição e visualização, com menus e muitas ferramentas de
> formatação HTML/CSS. O HTML é alimentado com o OCR que alimenta a aba Texto, agora com os
> diagramas também. Nível de excelência AAA.» (usuário, 2026-09-23, condensado)

**Uma coisa que o pedido supõe e o código desmente:** a aba Texto **não** usa o OCR da exportação
(§2.1). «O OCR que alimenta a aba Texto» e «o OCR que vira o livro» são hoje dois leitores
diferentes. Escolher qual alimenta o editor — ou unificá-los — é decisão do usuário (Q1), com uma
medição antes (H0).

### 0.2 O que o usuário passa a ter

1. **A aba.** Uma aba **Editor HTML/CSS** na faixa da janela principal. Entrar nela abre (ou traz à
   frente) a **janela dedicada** do editor para o livro aberto. A aba mostra o estado do projeto e
   as ações principais.
2. **O projeto.** O livro inteiro, ou o intervalo que ele escolher, como **XHTML + CSS**, um
   arquivo por capítulo. Os **diagramas entram como posições** — FEN, lado a jogar, número,
   legenda e estipulação —, desenhados em SVG, nunca `[Diagrama N]`.
3. **Os painéis.**
   - À esquerda, o **código**.
   - À direita, o **Resultado** (fluxo de leitor ou página paginada), o **PDF original** ou os dois
     lado a lado (**Comparar**).
   - Os três ficam **sincronizados elemento a elemento**: um clique num deles leva os outros ao
     mesmo trecho, e o retângulo de origem acende na página do PDF.
4. **A revisão.** As **dúvidas do OCR** aparecem sublinhadas no código, contornadas no resultado e
   em caixa no PDF. `F8` vai à próxima e `Ctrl+Enter` aceita — o fluxo de verificação do
   FineReader, dentro do editor.
5. **As ferramentas.**
   - Menus de HTML, CSS, tipografia, livro (metadados, capa, sumário, arquivos) e xadrez.
   - Paleta de comandos.
   - Busca e substituição com regex no livro inteiro, com plano revisável.
   - **Temas de livro**.
6. **A validação contínua.** XHTML, contrato de marcação, xadrez, CSS, acessibilidade (com o Ace do
   DAISY como oráculo externo) e EPUBCheck, cada problema com «ir para linha:coluna».
7. **A exportação.**
   - EPUB e HTML: a estrutura é **exatamente** o XHTML editado, e o CSS vai **byte a byte**.
   - PDF: **impresso pelo mesmo motor da prévia Página**, com as mesmas quebras — MuPDF sempre,
     Chromium quando instalado.
   - DOCX: um mapa de estilo fechado, com um aviso para cada regra que fica de fora.
   - LaTeX: a estrutura pelo IR e um aviso único de que o CSS não chega lá.
   - A exportação da janela principal passa a usar o projeto quando ele existe.
8. **As garantias.**
   - **Nada se perde:** diário, versões, recuperação, pergunta ao fechar e arquivo mudado por fora
     detectado.
   - **Nada congela:** ≤ 16 ms na thread da janela.
   - **Tudo por teclado:** as teclas não vazam para a janela principal.
   - **Acessível:** contraste AAA no texto do código, leitor de tela e escala.

### 0.3 A janela

```
┌ Editor HTML/CSS — A Matter of Endgame Technique ───────────────────────────────── ▢ ✕ ┐
│ Arquivo Editar Localizar Inserir Formatar CSS Livro Xadrez Revisão Validar Ver Ajuda    │
│ [Gravar] [Desfazer][Refazer] │ [Parágrafo ▾][N][I] [Classe…] │ [Diagrama][Figurina ▾] │  │
│ [Próxima dúvida F8][Aceitar] │ Ver: (Código+Resultado)(Código+PDF)(Comparar)(Três)     │
├───────────────┬──────────────────────────────────┬─────────────────────────────────────┤
│ LIVRO         │ cap-02.xhtml ●  livro.css        │ Resultado ▾  Leitor 6" ▾  A5 ▾  ☾   │
│ ▾ Texto       │  31  <h2 id="p55-1">Chapter 1 …  │ ┌───────────────────────────────┐   │
│   cap-01 ✓    │  32  <figure class="cb-diagram"  │ │  Chapter 1 Endgame Elements   │   │
│   cap-02 ●    │        id="p55-d1" data-fen="…"  │ │   ┌────────┐                  │   │
│ ▾ Estilos     │  33    <img class="cb-svg" …/>   │ │   │ ♚   ♙  │  Diagrama 1      │   │
│   livro.css   │  34    <figcaption>…</figcaption>│ │   └────────┘                  │   │
│ ▾ Páginas     │  35  </figure>                   │ │ The pawn ending is the ulti-  │   │
│   55 ● 3 dúv. │  36  <p id="p55-3">The pawn …    │ │ mate realisation of White's…  │   │
│   56 ✓        │        ~~~~~~ (dúvida 0,62)      │ └───────────────────────────────┘   │
│ ESTRUTURA     │ body › section › p#p55-3         │ pág. 55 do PDF (impressa 54) ◂ ▸ ☑  │
├───────────────┴──────────────────────────────────┴─────────────────────────────────────┤
│ Problemas (3) │ Localizar │ Estilos │ Diagramas │ Histórico │ Recortes                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Ln 36, Col 14 · XHTML · pág. 55 · 2 dúvidas na página · EPUBCheck: 0 erros · gravado    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 0.4 As cinco decisões (§4)

| # | decisão | em uma linha |
|---|---|---|
| D1 | O editor é uma **vista-fonte do IR** para a **estrutura**. O **CSS** vai verbatim como recurso | XHTML legível ↔ IR pelo mesmo motor HTML da exportação. O CSS do projeto é `Resource(STYLESHEET)`. Sai byte a byte no EPUB/HTML. O PDF é a impressão desse HTML pelo motor da prévia. O DOCX usa um **mapa de estilo fechado**, com aviso por regra fora dele. O LaTeX recebe a estrutura e um aviso único |
| D2 | **Um vocabulário só** | o contrato `cb-*` do MARKUP, mais extensões registradas, vira o contrato público do Caissa. O leitor continua lendo o legado `data-ir` |
| D3 | **Dois motores de pré-visualização atrás de uma interface** | MuPDF `Story` embutido (sempre presente, paginado, sem rede). Chromium (QtWebEngine) como componente sob demanda. Só vira padrão se passar num **build PyInstaller real e numa máquina limpa** (H1) |
| D4 | **Editor de código nativo — provisório** | `QPlainTextEdit` especializado, condicionado a um protótipo **com todas as funções ligadas** passar no H2, em desempenho e em casos dourados. Se o H2 reprovar, ou o H12 reprovar por limite do componente, o H2b mede o QScintilla no mesmo arnês |
| D5 | **Janela de primeiro nível com casca injetada e rota de teclas por janela ativa** | `QMainWindow` da suíte montada pelo tronco. A guarda de teclas decide pela janela ativa, respeita pop-up, AltGr e tecla morta, e **executa** a ação do editor, não só a engole |

---

## 1. CAPACIDADE

**Quem usa:** o enxadrista-editor da `SPEC.md` §1 (persona primária e P3/P4). Ele importou um
livro — PDF nativo ou digitalizado, lido pelo OCR, com os diagramas reconhecidos — e precisa
transformá-lo num livro publicável.

**Hoje:**
- A aba Livro ▸ Texto mostra o texto **de uma página por vez**, num editor de texto rico. Os
  diagramas aparecem como `[Diagrama N]`, sem FEN, e a leitura é de um leitor próprio do tronco
  (§2.1).
- A exportação EPUB/DOCX nunca vê essa aba: ela reimporta o PDF pela suíte a cada vez.
- Não há onde formatar o livro e ver o resultado ao lado do original.

**Depois desta capacidade:**
- A janela Editor HTML/CSS abre o livro como um **projeto** — XHTML + CSS + diagramas.
- Ele edita o código com ferramentas de verdade e vê, ao lado, o resultado formatado e a página
  do PDF de onde cada trecho veio.
- Revisa as dúvidas do OCR no mesmo lugar em que formata.
- Exporta um EPUB que é o que está na tela (estrutura igual, CSS byte a byte) e que passa no
  EPUBCheck e no Ace.
- Exporta um PDF que é a prévia paginada impressa.
- Pelo IR, leva a estrutura ao DOCX (com o mapa de estilo) e ao LaTeX, com as perdas declaradas.

**O que muda para ele:**
- **(a)** O trabalho de formatação passa a existir: ele é persistente, versionado e exportável.
- **(b)** A verificação do OCR deixa de ser uma fila à parte e passa a acontecer em contexto.
- **(c)** O diagrama deixa de ser marcador e passa a ser objeto editável.
- **(d)** O critério de pronto do livro passa a ser medido: 0 dúvidas pendentes, 0 problemas
  bloqueantes, EPUBCheck 0 erros, Ace sem violação séria ou crítica.

---

## 2. O QUE EXISTE HOJE (lido e medido em 2026-09-23)

### 2.1 A aba Texto: outro leitor, uma página por vez — e uma mudança em andamento

- **O painel.** `PainelDeTexto` (T `qt/painel_de_texto.py`) é um `QTextEdit` sobre um
  `rico.DocumentoRico` imutável, com pilha de desfazer própria. O desfazer do Qt fica desligado de
  propósito.
- **A digitação.** Este arquivo está mudando durante esta sessão, por isso o método é citado pelo
  nome, não pela linha.
  - **No HEAD do tronco**, o único sinal ligado era `textChanged → _mostrar_vazio`, e o texto
    digitado não entrava no documento. Foi lido no início da sessão; o HEAD era `40e2966`, e
    depois `8243e90`, sem mudança nesse arquivo.
  - **Durante esta sessão**, uma mudança **ainda sem commit** na árvore do tronco:
    - passou a levar a digitação ao documento (`contentsChange` → `_digitado`, com funções puras
      novas em `text/rico.py`);
    - passou a perguntar ao fechar (`JanelaPrincipal.closeEvent` → `texto.confirmar_fechamento`);
    - trouxe testes (`tests/test_qt_texto_digitacao.py`, `tests/test_texto_digitacao.py`).
  - **Esta spec não depende dela.** A ponte do H26 espera ela estar commitada.
- **O leitor.** `ler()` → `text.leitor.ler_pagina(pdf, indice, dpi=220, motor, modo_bloco)`, com os
  motores «glifo» (classificador de caracteres do tronco), «camada» e o modo bloco (RapidOCR).
  - Nenhum import de `caissa`. **Não é** o `import_pdf` da suíte, que alimenta a exportação e a aba
    Revisão de texto.
  - Os dois caminhos não partilham identificador, motor nem geometria.
- **Os diagramas.** `BlocoDeDiagrama.texto = f"[Diagrama {indice+1}]"` (T `text/pagina.py:593-601`),
  com `placement=""`, porque `montar` é chamado sem `placements` (T `text/leitor.py:1326-1336`).
- **A cor de confiança** é por parágrafo, com o corte em 0,30/0,75 (T `text/documento.py:42`,
  `ocr.py:70`).
- **A página.** Uma folha por vez; um `.cvtxt` guarda uma folha.
  - O índice de página do painel só muda quando o livro abre (`janela.py:1060` →
    `definir_livro(alvo, pagina=…)`) e depois de uma leitura. `janela._pagina_apareceu` não o
    atualiza.
  - O comando «ler a folha que o visualizador mostra» (`sincronizar_com_a_pagina`, S-236) usa esse
    índice: lê a página da última abertura ou leitura, não a que está na tela.
- **A exportação HTML da aba** (`exportacao.Html`, T `text/exportacao.py`) escreve um `<style>` com
  as regras de `body` e `.diagrama` e, **só quando recebe os mapas**, as regras das classes de cor e
  de corpo (`exportacao.py:290-303`).
  - O painel a chama sem os mapas e sem recortes. Resultado: as classes de cor ficam sem regra, e
    o diagrama sai como o texto `[Diagrama N]` — o `<img>` só existe com um recorte
    (`exportacao.py:384-388`).

### 2.2 O caminho do produto: `import_pdf` → IR → exportadores

- **O IR** (S `core/model/`).
  - `Document.body` é uma tupla plana de blocos (`document.py:280`). `Group(role=CHAPTER)` existe
    (`blocks.py:136`), mas o importador não o cria.
  - Todo nó (`IRNode`, `base.py:53`) tem ULID e `provenance` opcional (`base.py:52-68`): página,
    `rect` em pontos PDF, motor, confiança, `band` (CERTAIN/CONFIDENT/DOUBTFUL/UNRELIABLE),
    `verified_by_human` e nota (`provenance.py:106-149`). **Não há campo REVIEW:** «para revisão»
    é `band=DOUBTFUL` mais a nota.
  - Os `Text` do bloco **não** têm proveniência — o bloco leva o agregado. As figurinas
    (`PieceGlyph`) têm a própria (`importer.py:1859-1900`).
  - O inline `Span` existe (`inline.py:391`). `RunProps` tem `language` (`props.py:948`), e
    `ResourceKind.STYLESHEET` existe (`document.py:63`).
- **Serialização.** JSON com migração: `CURRENT_SCHEMA_VERSION = 1`, `migrations.py:51`. Campo
  desconhecido é recusado: campo novo exige migração.
- **Fidelidade.** A ida e volta de 10.000 nós é portão (`tests/unit/model/test_roundtrip_corpus.py`).
  `core/model/diff.py` (`semantic_diff`) é o instrumento.
- **A importação.** `PdfImportOptions` (`importer.py:309-415`) aplica:
  - `review_decisions`: `labeling/revisao/<pdf>.json`, IoU ≥ 0,5 (`review.py:483-535`);
  - `diagram_decisions`: `labeling/diagramas/<pdf>.json`;
  - aceita `keep_partial` e `should_cancel`.

  Um diagrama leva FEN, lado a jogar com fonte, número, legenda, estipulação («Mate em N»
  conferida) e solução (`_diagram_node` 1512-1635). O fólio impresso é lido
  (`running_page_number`, `importer.py:1275`).
- **Os armazéns de decisão não gravam do mesmo jeito, e há mais de um escritor.**
  - `ReviewDecisions.save` grava com `write_text`, sem trava e sem temporário (`review.py:542-546`).
    A aba Revisão de texto a chama direto: `self.queue.decisions().save(destino)`
    (`ui/views/revisao_de_texto.py:623`).
  - `DiagramDecisions.save` grava com temporário e `replace` (`diagram_decisions.py:242-247`), e
    `record` carrega-acrescenta-grava sob um arquivo de trava `O_EXCL` com expiração de 60 s
    (`diagram_decisions.py:293-326`).
  - O gancho da aba Resultado importa `record` (T `qt/decisoes_de_diagrama.py:43`) e o chama pelo
    nome curto (`:106`).
  - Os leitores são `export/book.py:425-427,537-539`, o importador e T `qt/importador_de_livro.py:285-293`.

### 2.3 O motor HTML existe, é ida-e-volta — e é escrito para máquina

- **O construtor.** `XhtmlBuilder` (S `export/html.py:1951`) é o que o EPUB usa (`epub.py:282`).
  Ele escreve:
  - cada `Text` num `<span data-ir="text">`;
  - `data-ir-id` em todo bloco (`html.py:2142…`);
  - classes geradas `.pN/.rN/.dN` num `props.css` (`CssRegistry`, `:1748`), estáveis só para o
    mesmo documento;
  - o estilo nomeado só como `--caissa-pstyle: Movetext` dentro de uma regra `.pN` (`:1378`), sem
    classe semântica `.movetext` nem `.caption`.
- **O leitor.** `read_html_text` (`:4241`) lê **XML estrito** e reconstrói pelos `data-ir` mais o
  CSS gerado.
- **O EPUB.**
  - Divide os capítulos por título de nível ≤ `split_level=1` e por 260 KB (`epub.py:128-130, 419-448, 1345`).
  - Folhas: `base.css` = `BASE_CSS` (`html.py:171`), `chess.css` = `CHESS_CSS` (`epub.py:93`) e
    `props.css`.
  - O diagrama é um `<figure class="diagram" data-ir="diagram" data-fen …>` com **SVG em linha**:
    contornos traçados da Merida, em mm e determinístico (`diagrams.py:411-469`,
    `typeset/board_svg.py`).
- **O IR vai dentro do EPUB.** `embed_ir=True` por padrão (`base.py:392`) grava `OEBPS/caissa-ir.json`
  (`epub.py:353-361`), e com ele `DiagramSource.path` = o caminho absoluto do PDF
  (`importer.py:1551-1556`). Tarefa separada sugerida nesta sessão.
- **Não há sanitizador.** `escape()` (`html.py:1921`) trata `& < >` e NBSP, e
  `RawPassthrough`/`RawInline` html saem verbatim.
- **EPUBCheck.** `epubcheck.py` só lê a linha de resumo (−1 quando não entende), e `export_book`
  nunca o roda.

### 2.4 Três vocabulários de marcação para a mesma coisa

1. **MARKUP (`cb-*`, congelado).**
   - O que define: `figure.cb-diagram[data-fen][data-stm][data-mode=svg|font|font-with-svg-fallback]`,
     `img.cb-svg`, `figcaption.cb-diagram-caption`, `section.cb-game`,
     `p.cb-line.cb-mainline|cb-variation.cb-depth-N`, `span.cb-movenum`,
     `span.cb-move[data-uci][data-fen]` (FEN **depois** do lance), `span.cb-piece[data-piece]`,
     `span.cb-nag[data-nag]` e `cb-comment`.
   - A política: acrescentar classe é seguro; renomear exige versão, migração e `DECISIONS.md`
     (MARKUP:231-235).
   - O MARKUP **não** tem orientação do tabuleiro.
2. **O exemplo do `..\Plugins_Sigil_Edit\SPEC.md:77-97`** (`cb-score`, `cb-movetext`,
   `data-ply`…), nunca implementado.
3. **O `html.py` do Caissa** (§2.3): `.move`, `.game`, `.diagram`, `data-fen-before/after`,
   `data-ir-id`.

**O CB** (GPLv3, sem Qt, cerca de 20,6 mil linhas) traz, prontos:
- `render/svg.py`;
- `fontdiag`/`fontprofile`/`fontembed` com 17 perfis de fonte;
- `layout/templates.py`, com **9 modelos de CSS** em cadeias Python: `nic-classic`, `flowing`,
  `tiered`, `informator`, `everyman`, `puzzle-book`, `nic-yearbook`, `quality-chess` e
  `tournament-bulletin`;
- `validate.validate_book`, cujas mensagens trazem número de linha;
- `core/caret.resolve_caret`.

O `ROADMAP.md` do chessbook dá as fases 0–6 como feitas. O cache do pytest guarda 15 testes
reprovados em 2026-09-19, **não reexecutados**. O Sigil do usuário
(`build-native-vs\bin\Sigil.exe`) já faz pré-visualização em QtWebEngine e PDF por `printToPdf`.

### 2.5 A janela, as teclas e os portões

- **A catraca.** `janela.py` tem **2.077 linhas no HEAD `8243e90` = `LIMITE`**
  (T `tests/test_packaging.py:253`).
  - Contagem com `wc -l`, ou `.Count` no PowerShell (Apêndice A.3). **Não** com
    `Measure-Object -Line`, que pula as linhas vazias e dá 1.808 — o ciclo 2 do crítico caiu nessa
    armadilha por causa de um comando errado da versão 1.1.
  - A árvore de trabalho, com a mudança da aba Texto em andamento (§2.1), teve 2.080 linhas e voltou
    a 2.077 durante esta sessão (a outra sessão reconciliou).
  - O editor **não faz `janela.py` crescer** (R1.12).
  - As abas da suíte entram por `abas_da_suite.donos` (`janela.py:1878`) e `_na_aba_ou`
    (`:1881-1885`), com a guarda `disponivel()/montar()` de `painel_de_rotulagem.py:28-52`.
- **A guarda de teclas é da aplicação inteira** (T `qt/atalhos.py:269-293`) e vê as teclas de
  **toda janela**. Ela decide em três passos:
  1. o campo de texto em foco fica com as teclas próprias dele;
  2. um `DonoDeAcoes` (T `ui/atalhos.py:503`, `destino` `:577`) na cadeia de foco;
  3. senão, a janela principal.

  Sem dono, `Ctrl+S` numa janela nova grava o diagrama da janela principal. Só `atalhos.py` escreve
  teclas em T `qt/` (T `tests/test_qt_atalhos.py:119-129`).
- **Só `QDialog` recebe o tratamento automático.** Nome acessível, botões em pt-BR e escala vêm
  de um filtro de `QEvent.Show` que exige `isinstance(alvo, QDialog)` (T `qt/acessibilidade.py:224-225`).
- **O estado da janela** mora em `data/janela.json` (`AppState`, T `ui/state.py:38`,
  `STATE_VERSION = 6`). Campo novo exige subir a versão e escrever `_migrate`.
- **O visor de PDF.**
  - `PainelDoPdf` (T `qt/painel_do_pdf.py:204`) rasteriza no processo de trabalho (um filho
    `spawn`), porque o PyMuPDF segura o GIL por 43–49 ms por página.
  - `VisorDePagina` (T `qt/visor.py:323`) desenha caixas **de diagrama** (`definir_caixas`, `:542`).
    Não há chamada «acender este retângulo».
- **Portões que veriam a janela nova sem mudança:** quase nenhum (Apêndice B). Todo portão novo
  precisa de sabotagem, `--saida` obrigatório, `estado_de_medicao` (`A/capture.py:253-288`) e
  nenhum import de Qt no topo do módulo (`tests/unit/ui/test_arquitetura.py:188-208`).

### 2.6 Dependências e empacotamento

**O que há em cada ambiente:**

| | `.venv-pack` (3.11) | `.venv` suíte (3.11) | `.venv` tronco (3.10) |
|---|---|---|---|
| PyQt6 / Qt | 6.11.0 / 6.11.2 | — | 6.11.0 / 6.11.2 |
| QtWebEngine, QScintilla | **ausentes** | — | **ausentes** |
| QtPdf, QtPdfWidgets, QtSvg, QtWebChannel | presentes | — | presentes |
| PyMuPDF | 1.28.2 | 1.28.2 | 1.27.1 |
| tinycss2 / cssselect2 | ausentes | 1.5.1 / 0.10.1 (via CairoSVG) | 1.5.1 / 0.9.0 |
| lxml | ausente | ausente | ausente |

**Ferramentas da máquina:**
- Java 8 (`1.8.0_503`), que basta ao EPUBCheck 4.2.6.
- Node.js v25.9.0 com npm (para o Ace do DAISY, H24).
- **O Windows Sandbox não está habilitado** (`C:\Windows\System32\WindowsSandbox.exe` ausente).

**O MuPDF `Story` serve de motor de pré-visualização paginada** (medido nesta análise, mediana de
5 execuções, Apêndice A.1):

| capítulo | páginas A5 | posições de elementos | leiaute + escrita | rasterizar 1 página a 96 dpi |
|---|---|---|---|---|
| 12 parágrafos | 2 | 54 | 10,3 ms | 5,7 ms |
| 120 parágrafos + 20 diagramas SVG | 17 | 522 | 89,1 ms | 5,4 ms |

- `element_positions()` dá o retângulo de todo elemento com `id`.
- SVG via `Archive` é desenhado.
- Uma fonte **sem cmap Unicode** (a `ChessMerida.ttf`) é **ignorada em silêncio** (medido pelo
  explorador). `S typeset/fonts.py` já sabe sintetizar a cmap (`subset_font`).

**Teto do instalador.**
- `TETO_DO_INSTALADOR_MB = 150` (`packaging/build_windows.py:78`); `tests/integration/test_packaging.py:556-580`
  reprova acima disso.
- Última medida: **79,4 MB** (proxy LZMA2, `F12_REPORT_C2.md:16,41`).
- **Pegadinha:** `runtime/` é pasta do usuário e fica **fora** da medida do pacote
  (`build_windows.py:56-71, 811-815`). Um componente em `runtime/` precisa de orçamento e medida
  **próprios**.

**QtWebEngine.**
- Quanto custa: o mínimo de execução medido é **207 MB**, mais cerca de 14,8 MB de bibliotecas Qt
  que o pacote não leva. A medida é **extrapolada**: foi feita no PySide6 6.10.2 de outro projeto.
- O WebView2 já foi removido (tronco S-69, `ROADMAP_FASE7.md:1692-1703`):
  - a janela nativa pintava por cima de tudo;
  - o leitor do Edge não aceitava script injetado;
  - não dizia a página mostrada.

**Licenças e fontes.**
- O agregado é **AGPL-3.0-or-later** (`LICENSING.md:18`). GPL e LGPL são aceitas; é recusada a
  **origem desconhecida** (`LICENSING.md:139-144`). Pacotes Python entram no inventário
  automaticamente (`packaging/coletar_licencas.py:202-291`); fontes e dados, à mão
  (`ARTEFATOS_NAO_PYTHON`, `:88-107`).
- A suíte não traz fonte nenhuma. O EPUB usa as fontes instaladas do usuário (`fonts.py:438-484`).
  As fontes de xadrez instaladas não declaram licença, e `Chess Cases` tem `fsType=2`.

### 2.7 Defeitos achados que o editor poria na tela

O editor mostra a saída do motor HTML. Todo defeito dela passa a estar à vista.

| # | defeito | onde |
|---|---|---|
| 1 | sidecar de proveniência falha com `Rect` real (`list(rect)` → `TypeError`), engolido por `except` | `export/provenance.py:87,114`; `book.py:209-212` |
| 2 | decisão de diagrama sobrescreve «Mate em N» com «Brancas/Pretas jogam» | `book.py:586` |
| 3 | alt do diagrama importado é «Imagem da página N (W×H pt)» | `importer.py:1550,1622,1730-1731` |
| 4 | partida importada sai com «? – ? · *» e notação inglesa | `games.py:246-250`; `html.py:2606-2617` |
| 5 | todo EPUB com diagrama embute um subconjunto da Merida, embora as peças sejam contornos | `diagrams.py:467` → `epub.py:597-634` |
| 6 | SVG com cores fixas (nada de `currentColor`), contra o que `epub.py:24-30` afirma | `board_svg.py` |
| 7 | figurina importada recebe `.dN { font-family: <fonte do PDF> }` nunca embutida | `html.py` (`CssRegistry`) |
| 8 | perfil de capacidade diz `verified_by_human` não suportado, e a marcação o escreve | `profiles.py:114-116`; `html.py:2501,5079` |
| 9 | numeração automática de diagramas não implementada | `auto_number_diagrams` sem uso |
| 10 | EPUB leva o caminho absoluto do PDF no IR embutido | `epub.py:353-361`; `importer.py:1551-1556` |
| 11 | `ReviewDecisions.save` grava sem temporário e sem trava, e a aba Revisão de texto a chama direto | `review.py:542-546`; `ui/views/revisao_de_texto.py:623` |

- Os itens 1, 2 e 10 foram confirmados nesta sessão lendo o código e viraram a tarefa separada
  «Fix three silent EPUB export defects». Com ou sem ela, o **H4 os exige com fixture positiva**. O
  item 1 é pré-requisito do sidecar completo (R2.4).
- Os itens 3–9 são do explorador (execução em memória) e são o passo **H4**.
- O item 11 é o **H7**.

---

## 3. RESTRIÇÕES

### R1. Regras fixas (herdadas, não negociáveis)

- **R1.1–R1.9 da `OCR_UI_SPEC.md` valem inteiras:**
  - portão com sabotagem;
  - número com comando, mediana de ≥ 3 execuções quando há variação;
  - partição cega intocável;
  - nada de LLM em substituição de texto (R1.5);
  - sem caminho absoluto em dado empacotado;
  - o acervo não sai da máquina;
  - commits por caminho nomeado;
  - ADR-0003.
- **R1.10 ADR-0002.** Toda saída sai do IR. A estrutura do XHTML volta ao IR pelo leitor do mesmo
  motor. O CSS é conteúdo do IR como recurso (`ResourceKind.STYLESHEET`), e cada exportador o
  consome de um jeito (R2.2 c–e, a única definição):
  - EPUB e HTML: verbatim;
  - PDF: impressão do HTML exportado pelo motor da prévia Página;
  - DOCX: mapa de estilo;
  - LaTeX: aviso único.

  Não há conversor formato-a-formato.
- **R1.11 ADR-0009 e a divisão regra/pintura.**
  - Regra sem toolkit em S `editor/` (pacote novo; o `test_arquitetura` passa a afirmar isso).
  - Pintura em S `ui/views/editor_html/` e `ui/widgets/`.
  - A casca no tronco, em T `qt/` (com a regra em T `ui/`).
- **R1.12 O editor não faz `janela.py` crescer.**
  - O total de linhas depois do passo é ≤ o de antes, contado com `wc -l`/`.Count` (§2.5).
  - Medir pela diferença do passo, e não contra o `LIMITE`, porque outra sessão mexe no mesmo
    arquivo.
  - Uma linha trocada vale; uma a mais, não.
  - A aba e o comando entram pela tabela das abas da suíte e por módulos novos do tronco.
- **R1.13 O instalador continua ≤ 150 MB** (`test_packaging.py:556-580`).
  - Motor que não couber vai como **componente sob demanda**, com o **próprio orçamento medido**:
    download e instalado, publicados ao lado do pacote e nunca escondidos pela exclusão de
    `runtime/`.
  - Manifesto com SHA-256 dentro do instalador, instalação atômica, remoção que volta ao estado
    anterior, instalação por pasta, sem rede (`SPEC.md` §12).
- **R1.14 Licença conhecida ou nada.**
  - Fonte, CSS, JS ou modelo sem origem declarada não entra no pacote nem no EPUB.
  - Fonte de xadrez só é embutida no livro com licença declarada no registro de fontes (§5.7) e
    `fsType` que permite. O `pdfwrite.py:186-187,1348-1351` já recusa `fsType` restrito; o EPUB
    passa a recusar também.
- **R1.15 Sem rede.** Nada no editor fala com a internet — pré-visualização inclusive. O
  componente sob demanda só baixa pelo assistente e com consentimento.

### R2. Invariantes do documento

- **R2.1 Uma verdade por página.**
  - Toda página do projeto está em **um** estado: `NAO_GERADA`, `GERADA` (derivada do OCR e das
    decisões; pode ser regerada sem perguntar), `EDITADA` (o texto do editor é a verdade) ou
    `REVISADA`.
  - Página `EDITADA` ou `REVISADA` **nunca** é sobrescrita por regeneração: vira **proposta** por
    bloco (H25).
  - Até o H25 existir, regerar uma página editada exige confirmação explícita e deixa uma
    **versão**.
- **R2.2 O que se edita é o que se exporta.**
  - **(a) Estrutura, EPUB e HTML.** Para todo arquivo XHTML `x` do projeto,
    `canon(escrever(ler(x))) == canon(x)`, onde `canon` = árvore XML com atributos ordenados e
    espaço insignificante normalizado. O XHTML dentro do EPUB é `escrever(ler(x))`.
  - **(b) CSS, EPUB e HTML.** Cada folha do projeto vai **byte a byte**, ligada na mesma ordem.
  - **(c) PDF.** É a impressão do XHTML legível mais o CSS do projeto pelo **motor da prévia
    Página**: o MuPDF `Story`, sempre presente; o Chromium `printToPdf`, quando instalado (H27).
    - As páginas do PDF são as da prévia: mesmo número, mesmas quebras, mesmo texto por página.
    - A propriedade CSS que o motor não desenha (matriz do H1) gera `DegradationWarning` com
      seletor, propriedade e arquivo:linha.
    - É o exportador PDF «via HTML», que renderiza a saída do exportador HTML, que consome o IR
      (ADR-0002). O PDF pelo IR (`pdfwrite`) continua existindo fora do editor.
  - **(d) DOCX.** Fidelidade **declarada**:
    - o subconjunto do mapa de estilo (S3b) chega lá;
    - **toda** regra ou propriedade fora dele gera um `DegradationWarning` com seletor, propriedade
      e arquivo:linha;
    - nenhuma é descartada em silêncio.
  - **(e) LaTeX.** A estrutura pelo IR, como hoje. O CSS do projeto **não** chega, e um aviso
    único (`css-nao-suportado-no-formato`) lista as folhas. Sem mapa: é promessa a menos, dita.
  - As normalizações da estrutura são a lista **fechada** N1–N4 (S4). Qualquer outra diferença
    reprova o portão do H5.
- **R2.3 Nenhuma perda silenciosa** (`SPEC.md` §5.2, «regra de ouro»).
  - Marcação fora do contrato é **preservada**:
    - elemento desconhecido → `RawPassthrough`/`RawInline` `xhtml`;
    - atributo desconhecido em elemento do contrato → `html_attributes` do nó (S3).
  - Todo formato de saída que não a carrega avisa com código, arquivo e linha.
- **R2.4 O livro publicado não leva dado da máquina.**
  - Nenhum caminho local, nome de usuário, confiança, motor ou nota de OCR no EPUB. Isso vai ao
    sidecar de proveniência, ao lado.
  - Os `id` de bloco (`p55-3`) e os marcadores de página **ficam**: são âncoras estruturais.
  - A exportação do editor **não embute o IR**. O `ExportOptions.embed_ir` é `True` por padrão
    (`export/base.py:392`); `editor.exportacao.exportar` o **força** a `False`, e um teste espia as
    opções passadas ao exportador.
    - Motivo: a proveniência é opcional por nó (`IRNode.provenance`, `None` no conteúdo autoral,
      `base.py:58-63`), mas, onde existe, traz página, retângulo, motor, confiança e nota.
    - O contrato legível se relê sozinho.
  - **O sidecar é onde a proveniência sobrevive, completo.** Hoje ele registra só `Diagram` e
    `GameScore` (`export/provenance.py:98-153`). Na exportação do editor ele passa a levar
    também:
    - um registro por bloco do `proveniencia.json` do projeto (`id`, página base 0 e fólio, `rect`,
      motor e versão, confiança, faixa, estado de revisão e decisões aplicadas);
    - as dúvidas resolvidas, com por quem e quando.

    **O sidecar tem formato exato, fechado e completo por construção**
    (`<livro>.proveniencia.jsonl`, JSON Lines, UTF-8):
    - **Linha 1, o cabeçalho:** `{"formato": "caissa.proveniencia", "versao": 2, "livro":
      {"sha256", "nome"}, "gerado_em", "esquema": {<classe>: [<campo>, …]}}`. O `esquema` sai
      **por introspecção recursiva** das dataclasses e vai no próprio arquivo.
    - **As classes:** `Provenance`, `Rect`, `DiagramSource`, `RecognitionResult`, `FenCandidate`,
      `SquareRepair` (`core/model/`), `ReviewItem`, `AuditEntry`, `Decided` (`ocr/review.py`) e
      `DiagramDecision` (`ocr/diagram_decisions.py`).
    - **Um registro por linha, de três tipos:**
      - `{"tipo": "bloco", "id", "ir_id", "folio", "proveniencia", "duvidas", "revisao"}`;
      - `{"tipo": "diagrama", "id", "ir_id", "fonte", "reconhecimento", "decisoes"}`;
      - `{"tipo": "partida", …}` — o registro de hoje, `export/provenance.py:140-153`.
    - **Os nomes:** o envelope usa chaves em português. As dez classes saem com os nomes de campo
      em inglês.
    - **Como saem:** todas pelo **serializador canônico do sidecar** (reflexão dos campos da
      dataclass, Apêndice C). **Não** pelos `as_dict()` existentes, que arredondam:
      `ReviewItem.as_dict` arredonda `score`, e `AuditEntry.as_dict` arredonda `seconds`
      (`ocr/review.py:102-128`).
    - **Versões:** a versão 1 é a de hoje (A11: diagramas e partidas), e o leitor continua a lê-la.
      Migração 1→2 testada.
    - **Privacidade:** o sidecar é um artefato **local** de auditoria e leva `document_path`. A
      janela de exportação diz isso, e «sidecar sem caminhos» reduz os caminhos ao nome do arquivo,
      mantendo o campo.

    Um teste compara o `esquema` do cabeçalho com a introspecção, e um campo novo no IR que o
    sidecar não leve reprova. **O esquema canônico completo** — codificação, tipos, obrigatoriedade,
    etiquetas dos objetos aninhados, exemplo e o **mapeamento campo a campo da versão 1 de hoje** —
    é o **Apêndice C**, e o portão compara a saída byte a byte com fixtures douradas escritas por
    quem não constrói. O portão usa uma fixture com **todos** os
    campos preenchidos com valores fora do padrão e exige igualdade campo a campo em 100 % dos
    `id`. Os nós sem proveniência (o conteúdo autoral) não têm registro, e isso é o esperado. O
    sidecar relido reconstrói o mesmo mapa. O defeito do `Rect` (§2.7, item 1) é pré-requisito,
    corrigido e provado no H4.
  - **A varredura do EPUB é por lista de permissão, não por palavra proibida:**
    - (a) só entram tipos permitidos: `mimetype`, `container.xml`, OPF, `nav`, NCX, XHTML, CSS, SVG,
      fontes e imagens. **Nenhum JSON.**
    - (b) Os metadados do OPF só com as propriedades de uma lista fechada: `dc:*`,
      `dcterms:modified`, `schema:access*`, `caissa:document-id`.
    - (c) Os atributos de cada XHTML são os do arquivo do projeto, pela igualdade `canon` do R2.2.
      Nada que o exportador invente entra. **E mais:** atributo cujo nome, sem o prefixo `data-` ou
      `aria-` e normalizado, é um dos nomes de campo de proveniência (a lista da alínea d) é
      **problema bloqueante**, mesmo que o usuário o tenha escrito: `data-confidence`,
      `data-engine`, `data-note`, `data-band`, `data-ocr-*`. O validador oferece «remover». Dado
      de máquina não vai ao livro publicado por nenhum caminho.
    - (d) **A lista proibida sai por introspecção recursiva** de todas as classes do sidecar, com
      cada nome de campo em `snake_case` e em `kebab-case`. Exemplos: `document_path`,
      `document_hash`, `block_index`, `out_of_model`, `engine`, `engine_version`, `model_hash`,
      `model_version`, `confidence`, `band`, `orientation_confidence`, `rotation_degrees`,
      `extractor_version`, `verified_by_human`, `note`. **A lista escrita aqui é exemplo; vale a
      gerada.**
      - Ela é procurada nas **posições estruturadas** de **todo** recurso publicado: nome de
        atributo em XHTML, SVG, OPF e NCX (sem o prefixo `data-`/`aria-`); `property` e `name` de
        `<meta>`; nome de propriedade personalizada de CSS (`--confidence`); chave de objeto em
        qualquer texto com forma de JSON.
      - Não é procurada em palavra de prosa: «nota» no texto do livro é conteúdo.
      - Os nomes que são atributos legítimos do XHTML/SVG do contrato (`id`, `kind`…) saem de uma
        **lista de exceção fechada**, declarada no próprio teste.
    - (e) Nenhum caminho local, letra de unidade ou nome de usuário.
- **R2.5 O diagrama é posição.**
  - A FEN é a verdade, e a imagem é derivada (SVG gerado da FEN e do estilo, cache por hash).
  - Mudar a FEN no editor **é** gravar uma decisão de diagrama pelo serviço único (R5).
  - Uma decisão gravada na aba Resultado chega ao editor: numa página `GERADA`, pela regeneração
    do bloco; nas outras, como proposta.
- **R2.6 O que o livro imprime não é trocado por conveniência.**
  - Letra de peça impressa continua letra (`OCR_UI_SPEC` R2.3).
  - Converter notação é comando explícito, com plano revisável. A tipografia automática também.
- **R2.7 Base das páginas, uma regra só.**
  - Na interface e nos `id` (`p55-…`), a página é **a do PDF em base 1**, a que a janela mostra.
  - No IR, nas decisões e no sidecar (`p<pág>:d<n>`), é **base 0**.
  - O **fólio impresso** é uma terceira coisa. Na página do pedido, o seletor mostra 55 e o
    cabeçalho impresso diz «54». O fólio vai só no `aria-label` do marcador (`id="pg55"
    aria-label="54"`), que é o que a `page-list` do EPUB reflete. Ele vem de `running_page_number`
    (`importer.py:1275`); na falta, é o número do PDF, com a nota «fólio não lido».
  - A conversão mora num só módulo (S `editor/paginas.py`), e um teste a fixa. A armadilha da
    base 1 × 0 do `labels.csv` custou uma rodada no ciclo 2.
- **R2.8 Nenhum trabalho perdido.**
  - Diário ≤ 2 s depois da última mudança.
  - Gravação atômica (temporário + `os.replace`).
  - Recuperação visível depois de queda.
  - Pergunta ao fechar o editor **e** ao fechar a janela principal com o editor sujo.
  - Um livro aberto numa janela só (sem dois diários no mesmo projeto).
  - Erro de gravação que não perde o diário.
  - Arquivo mudado por fora detectado (recarregar / comparar / manter o meu).
  - Versões por gravação, com teto de espaço e as 20 últimas sempre guardadas.
  - Cada item tem percurso no H17.
- **R2.9 Desfazer universal** (`SPEC.md` §10.7).
  - Toda ferramenta é **um** passo de desfazer.
  - Operação em vários arquivos é **uma** transação do projeto.
  - O desfazer diz o que desfez quando a ação mudou estado de revisão além do texto.

### R3. Invariantes de interface

- **R3.1 Os portões da F9 valem para a janela nova:**
  - contraste;
  - teclado com nomes;
  - texto pintado;
  - bloqueio ≤ 16 ms;
  - ≥ 55 fps @ p95 no PDF;
  - comandos vivos;
  - mínimo ≤ 1250×640;
  - escala 150 %/200 %.

  Hoje nenhum vê uma `QMainWindow` secundária: **estendê-los é parte do trabalho** (H11).
- **R3.2 Texto do código em AAA, provado nos pixels.**
  - **Todo texto de tamanho normal ≥ 7:1** (WCAG 1.4.6): o texto comum **e cada cor de sintaxe**,
    também sobre seleção, linha atual e realce de busca.
  - «Texto grande» (≥ 18 pt, ou ≥ 14 pt em negrito, medidos no tamanho **calculado** do glifo)
    admite 4,5:1, e o portão só aplica a exceção onde mede esse tamanho.
  - Indicadores e bordas (não texto, WCAG 1.4.11) ≥ 3:1.
  - A medida vale em todos os estados que a tela pode mostrar ao mesmo tempo: seleção, linha
    atual, par de tag, ocorrência de busca, indicadores sobrepostos, dobra, as três peles e o alto
    contraste do Windows.
  - Medida **nos pixels** da renderização, não só nos pares declarados.
  - Toda cor que o editor usa em tempo de execução tem de ser um papel de token declarado: o
    portão descobre as cores usadas e reprova a que não for.
- **R3.3 Confiança na letra, nunca no fundo, e nunca só por cor** (WCAG 1.4.1).
  - A dúvida é sublinhado **pontilhado**; o problema é sublinhado em **onda**. As formas diferem,
    e não só a cor.
  - Com simulação de daltonismo (deuteranopia, protanopia, tritanopia), os dois continuam
    distinguíveis pela forma.
- **R3.4 Rótulo desenhado, não dica** (`OCR_UI_SPEC` R3.4). Alvo ≥ 24×24 px (WCAG 2.5.8) e ≥ 40 px
  na barra.
- **R3.5 Operação longa cancelável, com progresso real e resultado parcial:** gerar, validar o
  livro, EPUBCheck, Ace, exportar, substituir no livro e instalar o componente.
- **R3.6 A tecla vai para quem deve, e só para ele.** A rota decide pela **janela ativa**
  (`QApplication.activeWindow()`):
  - **(a)** Com um pop-up ativo (menu, lista de completar, `QCompleter`), a tecla é do pop-up e a
    guarda não intercepta.
  - **(b)** Com o foco num campo de texto do editor, as teclas próprias do campo ficam com ele.
    - Isso inclui **AltGr** (no Windows, `Ctrl+Alt` com texto, que é caractere e não atalho) e as
      **teclas mortas** do ABNT2 (´ ` ~ ^ ¨ compõem pelo método de entrada).
  - **(c)** O `DonoDeAcoes` da janela do editor **executa** a ação do editor ligada à tecla.
  - **(d)** Tecla que só existe na janela principal não é despachada para lá. A barra de estado diz
    «`Ctrl+R` lê a página na janela principal».
  - **(e)** Com a janela principal ativa, tudo como hoje.
  - **(f)** Duas janelas do editor (dois livros): a ativa decide.

  `Esc` só fecha o transitório, nunca a janela.
- **R3.7 Nenhum atalho `Ctrl+Alt+tecla` que o ABNT2 produz com AltGr** (`/ ? ° ª º § ¹ ² ³ £ ¢ ¬`…).
  Teste da tabela de atalhos.
- **R3.8 Strings em pt-BR com acento** (T `tests/test_strings.py`). Frases de erro que dizem o que
  fazer (`OCR_UI_ROADMAP_C2` A10). Estado vazio com orientação.

### R4. Segurança do conteúdo

- **R4.1 A pré-visualização não executa nada do livro e não sai da máquina.**
  - MuPDF: não há JS, e os recursos só vêm do `Archive` do projeto.
  - Chromium:
    - JavaScript desligado no mundo da página, com a ponte do editor no *ApplicationWorld*;
    - um interceptador recusa todo esquema que não seja `caissa-projeto:` ou `data:`;
    - perfil fora do registro;
    - navegação, download, plugins e `file://` recusados.
  - Portão com um livro hostil (§5.5).
- **R4.2 A exportação recusa com problema bloqueante** (arquivo:linha:coluna), e **não
  descarta**:
  - `<script>`, `on*`, `javascript:`;
  - `<iframe>`/`<object>`/`<embed>`;
  - recurso remoto em `src`/`href` de recurso;
  - `@import` remoto.

  Um `<a href="https://…">` de texto é permitido.
- **R4.3 Limites para entrada patológica:**
  - XHTML ≤ 8 MB;
  - aninhamento ≤ 256;
  - `DOCTYPE` com entidades internas recusado;
  - entidade externa nunca resolvida;
  - caminho de recurso contido no projeto: sem `..`, sem absoluto, sem link simbólico para fora.

### R5. Propriedade dos dados — e o serviço único de decisões

| dado | dono (quem escreve) | onde |
|---|---|---|
| projeto do editor (XHTML, CSS, SVG derivados, `projeto.json`, `proveniencia.json`, diário, versões) | o editor | `editor/<livro>/`: na raiz do repositório num checkout (gitignored); ao lado do `Caissa.exe` no pacote, em `PASTAS_GUARDADAS` (`build_windows.py:67`); `CAISSA_EDITOR_DIR` sobrepõe |
| índice hash do PDF → pasta | o editor | `editor/livros.json` |
| decisões de texto | aba Revisão de texto **e** o «Aceitar» do editor | `labeling/revisao/<pdf>.json`, **pelo serviço único** |
| decisões de diagrama | aba Resultado **e** «Editar posição» do editor | `labeling/diagramas/<pdf>.json`, **pelo serviço único** |
| registro de fontes (licença, origem, `fsType`) | o usuário, pela janela | `editor/fontes.json` |
| estado da janela do editor | o tronco | `data/janela.json`, `AppState` v7 |

**O serviço único de decisões** (S `ocr/decisoes.py`, H7) é o único caminho de escrita dos dois
armazéns. Os escritores de hoje migram para ele:
- a aba Revisão de texto (`ui/views/revisao_de_texto.py:623`);
- `diagram_decisions.record`;
- o gancho da aba Resultado (T `qt/decisoes_de_diagrama.py:43` importa, `:106` chama).

**A exclusividade é estrutural, não por padrão de texto.**
- Os métodos públicos de escrita dos armazéns **deixam de existir**: `ReviewDecisions.save`,
  `DiagramDecisions.save` e a função `record` viram `_gravar`/`_registrar`, privados do módulo.
- O serviço é o único chamador.
- Um **teste de arquitetura por AST**, sobre `src\caissa` e `..\ChessVisionOFF_Puro\src`:
  - (a) afirma por introspecção que as classes não têm `save` nem `record` públicos;
  - (b) reprova qualquer referência a `_gravar`/`_registrar` — por atributo, por nome importado,
    por alias ou por `getattr` com literal — fora de `ocr/decisoes.py` e dos dois módulos dos
    armazéns;
  - (c) reprova qualquer `import` de `record` de `caissa.ocr.diagram_decisions`.
- Um chamador esquecido quebra no import ou no teste, e não grava por fora.
- **A guarda de execução pega o que a análise estática não pega:** um escritor novo que monte o
  JSON e use `Path.write_text`, `open(..., "w")`, `os.replace`, `os.rename` ou nome dinâmico.
  - Durante a suíte inteira de testes e os percursos, um gancho de auditoria (`sys.addaudithook`)
    registra toda escrita sob `labeling/revisao/` e `labeling/diagramas/`. Os eventos foram medidos
    nesta sessão, em CPython 3.10.11 e 3.11.9:
    - `open` é escrita quando o modo tem `w`, `a`, `x` ou `+`, **ou** quando o modo é `None` (a
      chamada `os.open`, a da trava `O_EXCL`) e as flags têm `O_WRONLY`, `O_RDWR`, `O_CREAT`,
      `O_APPEND` ou `O_TRUNC`;
    - `os.rename`, que **o `os.replace` também dispara** — não existe evento `os.replace`;
    - `os.remove`.
  - O caminho é canonizado antes de comparar: `realpath` (resolve relativo, junção e link
    simbólico), `normcase`, e o nome longo da pasta-mãe por `GetLongPathNameW` (o nome 8.3).
  - Reprova a escrita que não vier de uma pilha que passa por `caissa/ocr/decisoes.py`.

O serviço garante:
- trava no processo (`RLock`) e **entre processos** (arquivo de trava `O_EXCL`, com expiração — o
  mecanismo que `diagram_decisions.py:293-326` já tem);
- releitura antes de gravar, com fusão por chave quando o arquivo mudou (concorrência otimista por
  `mtime` + hash);
- gravação atômica;
- **aviso de mudança** aos inscritos (observadores sem Qt; a ponte para sinais Qt mora em `ui/`);
- detecção de mudança feita por outro processo (a bancada Tk `caissa-rotular`) com releitura.

**Toda gravação devolve um recibo.** `gravar(...) -> Recibo`, e o recibo guarda a chave, a decisão
anterior e a nova. `Recibo.desfazer()` regrava a anterior pelo serviço, com releitura e trava.
Quem gravou decide onde pôr o recibo:
- **o editor:** na transação do projeto (R2.9) — o `Ctrl+Z` desfaz a decisão junto com o texto;
- **a aba Resultado:** na pilha de desfazer dela (a do A7 do ciclo 2);
- **a aba Revisão de texto**, que não tem pilha de desfazer: no aviso de conflito, como «restaurar
  a outra».

**Conflito na mesma chave** (duas decisões diferentes para a mesma região ou o mesmo diagrama em
menos de um ciclo de releitura) não é resolvido em silêncio:
- vence a última;
- a descartada vai para um **histórico de decisões** (`<armazém>.historico.jsonl`, só acréscimo);
- o aviso diz qual foi descartada e oferece «restaurar a outra», que a regrava pelo serviço;
- o recibo de quem gravou por último também a restaura.

Vale para os **dois** armazéns.

### 3.6 Onde esta especificação conflita com as anteriores

| cláusula anterior | o que muda | por quê |
|---|---|---|
| `SPEC.md` §8.3 «diagramas em SVG inline» | no **projeto**, `<img class="cb-svg" src="../Images/dg_<hash>.svg">`; no EPUB exportado, em linha ou arquivo é opção do exportador, em linha como padrão até o H24 medir | SVG em linha torna o código ilegível; o SVG é derivado da FEN (R2.5) |
| `SPEC.md` §8.4 «página única autocontida» | continua como saída; o projeto é um pacote de arquivos | a divisão por capítulo é a do EPUB (`epub.py:419-448`) |
| `SPEC.md` §5.2 «nenhum exportador descarta propriedade» | continua: o CSS que um formato não carrega **avisa** — no PDF, a propriedade que o motor não desenha; no DOCX, a regra fora do mapa; no LaTeX, o aviso único (R2.2 c–e) | D1: o CSS não é semântica do IR, é recurso |
| marcação do `html.py` (§2.3) | o perfil legível vira o contrato público do EPUB; o leitor continua aceitando o legado | D1, D2 |
| `pyproject.toml` grupo `ui` (`pyside6-essentials`) | desatualizado desde a ADR-0009; passa a declarar `PyQt6` | a regra de licença exige a lista verdadeira |

---

## 4. DECISÕES

Status **proposta**: entram em `docs/adr/README.md` como ADR-0010…0014 só depois da aprovação
do usuário (Q0). Cada uma diz o que a reverteria.

### D1 (ADR-0010) — O editor é uma vista-fonte do IR para a estrutura; o CSS é recurso verbatim

**Contexto.**
- A ADR-0002 exige que toda saída saia do IR.
- O EPUB já nasce de um motor HTML ida-e-volta (§2.3), mas em marcação de máquina.
- O CSS de um livro (cascata, seletores, `@media`, `@page`, variáveis, `@font-face`) **não tem**
  representação no IR: `StyleSheet` guarda estilos nomeados estruturados (`styles.py:256-283`), não
  regras CSS.

**Decisão.**
1. **Estrutura.**
   - O projeto guarda os XHTML que o usuário edita, byte a byte como ele os deixou.
   - O motor HTML ganha o **perfil legível** e o leitor dele: gerar é IR → XHTML legível, exportar
     é XHTML → IR → exportadores.
   - A marcação fora do contrato é preservada (R2.3): elemento → `RawPassthrough`/`RawInline`;
     atributo → `IRNode.html_attributes` (esquema v2, migração v1→v2 trivial,
     `migrations.py:51`).
2. **CSS.**
   - As folhas do projeto são `Resource(kind=STYLESHEET)` do documento, **não interpretadas** pelo
     IR.
   - O EPUB e o HTML as levam byte a byte.
   - O **PDF** é a impressão do HTML exportado pelo motor da prévia Página (R2.2c).
   - O **DOCX** aplica o **mapa de estilo** (S3b) — um subconjunto fechado, com a cascata resolvida
     só para ele — e avisa o resto regra a regra (R2.2d).
   - O **LaTeX** recebe a estrutura e um aviso único (R2.2e).

**Alternativas rejeitadas.**
- **(a) HTML como verdade independente** (o Sigil). Fura a ADR-0002: o DOCX ignoraria as edições.
- **(b) Traduzir todo o CSS para o IR.** O IR viraria um motor de CSS, e o DOCX continuaria sem
  flex, `@media` e seletor de irmão.
- **(c) O perfil de máquina atual.** Ilegível.

**Consequências.**
- A ida e volta da estrutura é **portão** (H5).
- O mapa de estilo tem portão próprio: positivo para cada propriedade mapeada, negativo para cada
  construção fora (H5, H24).
- O PDF tem portão de igualdade com a prévia Página, e o LaTeX tem portão do aviso único (H24).
- Arquivo mal formado não vai ao IR: grava o texto e mostra o erro.

**Reverte se:** o H5 provar que a estrutura não fecha a ida e volta sem perda fora de N1–N4.

### D2 (ADR-0011) — Um vocabulário só: o contrato `cb-*`

**Contexto.**
- Há três vocabulários (§2.4).
- O CB tem nove temas de CSS, um validador com linha e um renderizador, todos em `cb-*`.
- O contrato é do próprio usuário e é «congelado» por política escrita.

**Decisão.**
- O **Contrato de Marcação do Caissa v1** (`docs/MARKUP_CAISSA.md`, H3) = MARKUP inteiro + as
  extensões do S4, pela política dele.
- Todo o resto é HTML semântico padrão.
- O leitor lê o contrato **e** o legado `data-ir`.

**Alternativas rejeitadas.**
- **(a) Manter o vocabulário do `html.py`:** não tem classe semântica.
- **(b) Inventar um quarto.**

**Consequências.**
- Os temas e as regras do CB são **absorvidos** para a suíte, com cabeçalho «Origem:» e GPLv3.
- Portão de interoperabilidade: o validador do CB aceita o EPUB do projeto (H3, H5).

**Reverte se:** o usuário responder «não» ao Q3.

### D3 (ADR-0012) — Dois motores de pré-visualização; o Chromium só com prova de pacote

**Contexto.**
- Não há QtWebEngine.
- Somá-lo ao instalador custa cerca de 207 MB descomprimidos (extrapolado) e ameaça o teto de
  150 MB.
- Em `runtime/`, ele escaparia da medida do pacote (§2.6).
- O MuPDF `Story` já está no pacote e mediu 89 ms para 17 páginas, mas desenha um subconjunto do
  CSS.

**Decisão.**
- A interface `MotorDePrevia` (S `editor/previa.py`, sem Qt) tem duas implementações:
  1. **MuPDF (embutido, sempre presente).** Modo **Página** (paginado) e **reserva** do modo
     Leitor.
  2. **Chromium (componente opcional «Pré-visualização de alta fidelidade»).** Modo **Leitor**
     (fluxo, remendo incremental do DOM), inspetor de estilos calculados, escuro do leitor e
     impressão.
- **O Chromium só vira padrão se o H1 provar**, com números:
  1. uma **sonda PyInstaller real** — o PyQt6 no `_internal/` e o WebEngine em `runtime/` — que
     abre e desenha a fixture nesta máquina **e numa máquina limpa** (Windows Sandbox habilitado
     pelo usuário, ou uma VM sem Python);
  2. frio ≤ 1,5 s;
  3. remendo p95 ≤ 150 ms em 260 KB;
  4. livro hostil com 0 requisições e 0 scripts;
  5. memória extra ≤ 350 MB;
  6. **orçamento do componente**: download ≤ 150 MB e instalado ≤ 300 MB, publicados ao lado do
     pacote;
  7. instalação atômica (pasta parcial → renomear no fim; parcial abortada é apagada), instalação
     por pasta sem rede e remoção que devolve o editor ao MuPDF.
- **A confiança no componente.**
  - O manifesto (nomes, versões, SHA-256) viaja **dentro do instalador**, que é a raiz de
    confiança.
  - Roda com hash diferente é recusada.
  - Revogar uma versão = um instalador novo com outro manifesto.
  - O editor recusa carregar componente cuja versão não bata com a do PyQt6 do pacote.
- Sem o Chromium, a janela diz num rótulo desenhado: «Pré-visualização simplificada (MuPDF) —
  instalar a de alta fidelidade».
- O validador marca a propriedade CSS que o **motor ativo** não desenha (matriz do H1).

**Alternativas rejeitadas.**
- **(a) `QTextBrowser`:** o subconjunto do Qt não desenha o CSS de livro.
- **(b) WebView2:** as razões do S-69.
- **(c) QtWebEngine no instalador:** fura o R1.13, a menos que o usuário mude o teto (Q2).
- **(d) Só Chromium:** o editor ficaria inútil até o download.

**Reverte se:** o H1 reprovar a sonda. O Q2 volta ao usuário com os números: embutir e subir o
teto, ou ficar só com o MuPDF.

### D4 (ADR-0013) — Editor de código nativo, provisório até o H2

**Contexto.**
- QScintilla não está instalado. O CodeMirror dependeria do Chromium opcional e seria opaco aos
  portões.
- O `QPlainTextEdit` expõe a interface de texto acessível do Qt (UIA no Windows), os portões o
  leem, e o Qt Creator e o Spyder mostram que ele chega a editor profissional.
- **Mas isso não está provado aqui.**

**Decisão (provisória).**
- `EditorDeCodigo(QPlainTextEdit)` com as funções do S5.
- O H2 constrói um protótipo com **todas as funções ligadas ao mesmo tempo**: realce, margem,
  dobras, indicadores, completar, par de tags, desfazer, escala e prévia no processo de trabalho.
  Ele mede o orçamento completo e prova a leitura por UIA.
- O protótipo prova também **comportamento**, e não só atividade: ≥ 5 casos dourados por função,
  um subconjunto dos do H12, passam com tudo ligado.
- O **H2b** mede o QScintilla no **mesmo** arnês, com os mesmos portões, antes de a dependência
  entrar: `PyQt6-QScintilla`, GPL-3.0, inventário de licenças, cores pelos papéis de token e sonda
  UIA. Ele roda em dois casos:
  - o H2 reprova;
  - o H12 reprova por um **limite do componente** — bloqueio, leitura por UIA, ou uma função que o
    `QPlainTextEdit` não sustenta.
- Cursores múltiplos ficam fora da v1.

**Reverte se:** o H2 reprovar, ou o H12 reprovar por limite do componente.

### D5 (ADR-0014) — Janela de primeiro nível, casca injetada, rota de teclas por janela ativa

**Contexto.**
- Um editor com docas e menus pede `QMainWindow`.
- O tronco só trata `QDialog`, `janela.py` não tem linha livre, e a guarda de teclas é global.

**Decisão.**
- **A suíte.** `JanelaDoEditorHtml(QMainWindow)` (S `ui/views/editor_html/janela.py`) recebe uma
  **casca** (protocolo em S `editor/casca.py`) com:
  - tema e pele;
  - acessibilidade e escala;
  - dono das teclas;
  - estado;
  - fábrica do visor de PDF;
  - editor de posição;
  - mostrar na principal;
  - o serviço de decisões.
- **O tronco.** Implementa a casca e a aba lançadora (T `qt/painel_do_editor_html.py`, com a
  guarda `disponivel()/montar()`).
  - Estende o filtro de acessibilidade a `JANELAS_SECUNDARIAS`.
  - **Reescreve a rota da guarda** para a regra do R3.6: janela ativa, pop-up, AltGr, tecla morta,
    execução positiva.
- Os portões ganham `--janela editor` (H11).
- A aba, ao ser ativada, abre ou traz à frente a janela. Uma preferência desliga isso.
- **Um livro por janela.** Abrir o mesmo livro de novo traz a janela existente à frente.

**Alternativas rejeitadas.**
- **(a) `QDialog` não modal:** `Esc` fecha e não há docas.
- **(b) Modo dentro da aba Livro:** 1250×640 não cabe três painéis.
- **(c) A janela no tronco:** a regra de documento iria para o 3.10.

**Reverte se:** o H11 mostrar que estender os portões custa mais que um `QDialog` com
`QMainWindow` embutido.

---

## 5. CONTRATO DE IMPLEMENTAÇÃO

### 5.1 Atores

| ator | o que faz | onde |
|---|---|---|
| Editor (usuário final) | gera, edita, formata, revisa, valida e exporta o livro | janela Editor HTML/CSS (`Caissa.exe`) |
| Revisor | aceita, corrige ou mantém as dúvidas do OCR; corrige posições | a mesma janela; abas Revisão de texto e Resultado |
| Importador (`PdfImporter`) | IR com proveniência e decisões aplicadas | S `ingest/pdf/importer.py` |
| Motor HTML | IR ↔ XHTML (perfis máquina e legível) | S `export/html.py` |
| Serviço de decisões | único escritor dos armazéns de decisão | S `ocr/decisoes.py` |
| Projeto (`ProjetoDoEditor`) | arquivos, estados de página, diário, versões | S `editor/projeto.py` |
| Motores de pré-visualização | MuPDF (embutido); Chromium (componente) | S `editor/previa*.py` + S `ui/views/editor_html/previa_*.py` |
| Janela principal | aba lançadora, casca, rota de teclas | T `qt/` |
| Construtor | implementa um passo | `src/caissa`, tronco |
| Crítico | reprova por medição e às cegas | `quality/EDITOR_HTML_CSS_CRITICAS.md` |

### 5.2 Superfícies

**S1 — Aba lançadora, janela, casca e teclas**

| interface | hoje | depois |
|---|---|---|
| faixa de abas | `Livro \| Dataset \| Galeria \| Rotulagem \| Revisão de texto` | + `Editor HTML/CSS` (T `ui/abas.py`), pela tabela das abas da suíte, sem linha nova em `janela.py` |
| conteúdo da aba | — | **Estado do projeto:** páginas geradas, editadas e revisadas; dúvidas; problemas; última gravação; motor ativo. **Ações:** «Abrir o Editor HTML/CSS» (primária), «Gerar do OCR…», «Exportar EPUB…». **Estado vazio** com orientação. Ativar a aba abre ou traz à frente a janela (preferência ligada por padrão) |
| comando | — | `abrir_editor_html` no catálogo (T `ui/comandos.py`), em Ferramentas e na paleta; nome na lista de reserva de `abas_da_suite.py:36-37` |
| janela | — | `JanelaDoEditorHtml(QMainWindow)`: menus, barra com rótulos, docas (Livro, Estrutura, Estilos, Problemas, Localizar, Diagramas, Histórico, Recortes), dois ou três painéis, barra de estado. **Um livro por janela**; o mesmo livro não abre duas vezes |
| teclas | guarda global, destino pela cadeia de foco (§2.5) | a rota do R3.6. Tabela única de teclas do editor em S `editor/comandos.py`, com teste de duplicata e de AltGr (R3.7) |
| acessibilidade e escala | só `QDialog` | + `JANELAS_SECUNDARIAS` (T `qt/acessibilidade.py`) |
| estado | `AppState` v6 | v7: `editor_geometria`, `editor_docas` (bytes de `saveState` em base64), `editor_leiaute`, `editor_abrir_ao_entrar`, `editor_motor`; `_migrate` de v6 |

**S2 — Projeto do editor (S `editor/projeto.py`, sem Qt)**

```
editor/<slug>/                        (slug do nome do PDF; a chave real é o SHA-256 do PDF em editor/livros.json)
  projeto.json      {formato: 1, pdf_sha256, pdf_nome, paginas: {"55": {"estado": "EDITADA", "arquivo": "cap-02.xhtml",
                     "gerada_em", "editada_em", "geracao": "<hash das entradas>"}}, espinha: [...], metadados, tema, motor}
  OEBPS/Text/cap-01.xhtml …           (o que o usuário edita)
  OEBPS/Styles/livro.css              (+ outras folhas; vão byte a byte ao EPUB)
  OEBPS/Images/dg_<hash>.svg          (derivados da FEN + estilo; regeneráveis)
  OEBPS/Images/capa.<ext>             (capa, quando houver)
  OEBPS/Fonts/…                       (só com licença no registro)
  proveniencia.json {"formato": 2,
                     "blocos": {"p55-3": {"ir_id", "folio", "proveniencia": <Provenance inteiro, serializado pelo IR>,
                                "duvidas": [{"ini", "fim", "proveniencia": <Provenance do Span>, "alternativas"}],
                                "revisao": {"estado", "decisoes": [<Decided | AuditEntry | ReviewItem inteiros>]}}},
                     "diagramas": {"p55-d1": {"ir_id", "fonte": <DiagramSource inteiro>,
                                   "reconhecimento": <RecognitionResult inteiro, com FenCandidate[] e SquareRepair[]>,
                                   "decisoes": [<DiagramDecision inteiro>]}}}          (esquema completo: R2.4)
  gerado/<n>/…                        (a última geração de cada página: a base da fusão, H25)
  diario/                             (gravação automática)
  versoes/<carimbo>/                  (uma por gravação; LRU de 200 MB; as 20 últimas sempre guardadas)
  .trava                              (um livro, uma janela: O_EXCL + PID + expiração)
```

- **API.**
  - `ProjetoDoEditor.abrir(pdf) / criar(pdf, paginas)`;
  - `arquivos()`, `ler(arquivo)`, `gravar(arquivo, texto)` (atômica);
  - `estado(pagina)`, `marcar_editada(paginas)`;
  - `versao(…)`, `restaurar(…)`;
  - `recuperar_do_diario()`;
  - `mudou_por_fora(arquivo)`.
- **Migração** por `formato`, com teste.

**S3 — Gerar e ler (S `export/html.py` + S `editor/geracao.py`, `editor/leitura.py`)**

| interface | hoje | depois |
|---|---|---|
| `XhtmlBuilder` | perfil de máquina (§2.3) | `perfil: Literal["maquina","legivel"]`. O **legível** escreve o contrato (S4): sem `data-ir` por corrida e sem classes `.pN/.rN/.dN`; estilo nomeado vira classe; `RunProps` só como marcação semântica ou classe; `lang` de `RunProps.language`; `id` `p<pág>-<n>` nos blocos com proveniência; marcadores de página; `html_attributes` do nó escritos de volta |
| leitor | `read_html_text` (XML estrito; `data-ir`) | + `ler_legivel(texto, contexto)`: contrato → IR; elemento desconhecido → `RawPassthrough`/`RawInline` `xhtml`; atributo desconhecido (`style`, `title`, `aria-*`, `data-*` fora do contrato, classes além da de estilo) → `html_attributes`; `id` → ULID pelo `proveniencia.json` (sem ele, ULID novo); o legado `data-ir` continua lido |
| IR | sem lugar para atributo HTML | `IRNode.html_attributes: tuple[tuple[str, str], ...] = ()`; esquema v2 com migração v1→v2 trivial (padrão vazio é omitido na serialização) |
| geração | `export_book` reimporta ou reaproveita (`book.py:477-540`) | `editor.geracao.gerar(projeto, paginas, *, should_cancel, progress)`: a fonte do Q1 → IR por página → divisão em arquivos pela regra do EPUB → perfil legível → `proveniencia.json` → SVG em cache. Página `EDITADA`/`REVISADA` nunca é tocada |
| dúvidas por trecho | só o agregado do bloco | o importador embrulha os trechos `REVIEW`/`ABSTAINED` num `Span` com `provenance` (sem migração); o perfil legível não escreve esse `Span` e grava o intervalo (N3) |

**S3b — O CSS do projeto e o mapa de estilo**

- **A fonte.** As folhas em `OEBPS/Styles/` são a verdade. O IR as carrega como
  `Resource(kind=STYLESHEET)` sem interpretá-las.
- **EPUB e HTML (perfil legível).** Levam as folhas do projeto **byte a byte**, na ordem da
  espinha. Não escrevem `BASE_CSS`/`CHESS_CSS`/`props.css`: o tema do projeto os substitui, e os
  temas absorvidos cobrem o que eles cobriam.
- **PDF.** A impressão do XHTML legível com as folhas do projeto, pelo motor da prévia Página: o
  MuPDF `Story` (paginação idêntica à prévia) ou, com o componente, o Chromium `printToPdf` (H27).
  O que o motor não desenha avisa, pela matriz do H1.
- **LaTeX.** A estrutura pelo IR e o aviso único `css-nao-suportado-no-formato`.
- **Mapa de estilo** (DOCX) — um subconjunto **fechado**:
  - **Seletores simples:**
    - `.classe`, `p.classe`, `span.classe`;
    - `h1…h6` com ou sem classe;
    - `figcaption`, `blockquote`;
    - as classes `cb-*` do contrato;
    - `:root` (só para variáveis).
  - **Propriedades:**
    - `font-family`, `font-size`, `font-weight`, `font-style`, `font-variant: small-caps`;
    - `color`, `background-color` (realce de trecho);
    - `text-align`, `text-indent`, `margin-*`, `line-height`, `letter-spacing`, `text-transform`;
    - `break-before`/`page-break-before`, `widows`/`orphans`;
    - `var(--x)` resolvível pelas variáveis de `:root`.
  - **A cascata** (especificidade e ordem) é resolvida **só** dentro desse subconjunto, por
    classe.
  - **Todo o resto** gera `DegradationWarning(codigo="css-fora-do-mapa", seletor, propriedade,
    arquivo:linha)` por regra: combinadores, pseudo-classes e pseudo-elementos, `@media`, `@page`,
    `@font-face` (vai por outro caminho — o registro de fontes), grid, flex, `float`, `position`,
    transformações e propriedades desconhecidas.
- **A pré-visualização** mostra o EPUB/HTML (o CSS inteiro, no motor ativo). O relatório de
  exportação lista o que o PDF (motor), o DOCX (mapa) e o LaTeX (aviso único) não receberam.

**S4 — Contrato de marcação (resumo; texto normativo em `docs/MARKUP_CAISSA.md`, H3)**

| nó do IR | marcação legível | origem |
|---|---|---|
| `Heading(level)` | `<hN id="p55-1">` | HTML |
| `Paragraph(style=None)` | `<p id="p55-3">` | HTML |
| `Paragraph(style="Movetext")` | `<p class="cb-movetext">` | extensão |
| `Paragraph(style="Caption"\|"Footnote"\|X)` | `<p class="cb-caption">` / `cb-footnote` / `cb-style-<slug(X)>` | extensão |
| `Emphasis`/`Strong`/`Underline`/`Strike`/`SmallCaps`/`Superscript`/`Subscript` | `em`/`strong`/`u`/`s`/`span.cb-smallcaps`/`sup`/`sub` | HTML + extensão |
| `RunProps.language` | `lang` no elemento | HTML |
| `Link`/`Anchor`/`NoteRef` | `a[href]` / `span[id]` / `a.cb-noteref[epub:type=noteref]` | HTML + EPUB |
| `Diagram` | `figure.cb-diagram[id][data-fen][data-stm][data-mode="svg"][data-orientation]` > `img.cb-svg[src][alt]` + `figcaption.cb-diagram-caption` > `span.cb-diagram-label`, `span.cb-stipulation`, `span.cb-stm-marker` | MARKUP (`data-mode` padrão `svg`; ausente é aceito, como o `InsertDiagram` do CB o escreve) + extensões `data-orientation` (`white`\|`black`), `-label`, `-stipulation` |
| `GameScore` / `MoveNode` / `Move` | `section.cb-game` … `p.cb-line.cb-mainline` … `span.cb-movenum` + `span.cb-move[data-uci][data-fen]` | MARKUP |
| `PieceGlyph` | `span.cb-piece[data-piece]` | MARKUP |
| `NagSymbol` | `span.cb-nag[data-nag]` | MARKUP |
| página do PDF | `<span epub:type="pagebreak" role="doc-pagebreak" id="pg55" aria-label="54"/>` | EPUB 3 + DPUB-ARIA |
| `RawPassthrough`/`RawInline` | o elemento como está | — |
| qualquer nó com `html_attributes` | os atributos de volta, na ordem do `canon` | — |

**Normalizações declaradas** — a lista **fechada** do R2.2(a), medida no H5:
- **N1.** `RunProps` de família e corpo vindas do PDF digitalizado não viram marcação; o tema
  decide. Contadas por arquivo.
- **N2.** Classes geradas `.pN/.rN/.dN` não existem no perfil legível.
- **N3.** `Span` só de proveniência vira intervalo em `proveniencia.json`.
- **N4.** Espaço insignificante e ordem de atributos (`canon`).

**S5 — Editor de código (S `ui/widgets/editor_de_codigo.py`; regra em S `editor/`)**

- **v1 (H12).**
  - Realce incremental (HTML com CSS em `<style>`, e CSS).
  - Margem com números, dobras e marcadores de problema, dúvida, diagrama e página.
  - Sublinhado em **onda** (problema) e **pontilhado** (dúvida), com papel de token.
  - Linha atual; par de tags casado; fechar tag ao digitar `</`.
  - Completar tag, atributo, classe do projeto, propriedade e valor CSS e `data-*` do contrato.
  - Trilha de pão; busca simples; ir para linha.
  - Invisíveis e quebra de linha opcionais.
  - Zoom próprio; colar como texto simples.
- **Desempenho (H2 prova com tudo ligado, H12 cumpre):**
  - abrir 2 MB e digitar 60 s a 30 car/s em 500 KB com realce, indicadores (500 intervalos),
    completar, dobras e prévia MuPDF ligada, sem bloqueio > 16 ms;
  - visível realçado ≤ 50 ms;
  - primeira pintura de um projeto de 300 páginas ≤ 800 ms;
  - desfazer 100 passos e colar 100 KB sem bloqueio > 16 ms.

**S6 — Resultado (pré-visualização)**

| modo | motor | o que mostra |
|---|---|---|
| **Leitor** (fluxo) | Chromium; reserva MuPDF (página contínua) | o arquivo atual com o CSS do projeto na largura de um dispositivo: Leitor 6", Tablet, Celular, Livre |
| **Página** (paginado) | MuPDF (`Story`) — ou impressão do Chromium, se o H27 existir | páginas A5/A4/personalizada, quebras, viúvas e órfãs |
| **Escuro do leitor** | os dois | o livro com `prefers-color-scheme: dark` |

- **Atualização.** Pausa de 150 ms (arquivo ≤ 20 KB) ou 400 ms (> 20 KB).
  - Chromium: remendo do DOM que preserva a rolagem.
  - MuPDF: novo leiaute no processo de trabalho, repintando as páginas visíveis.
  - A última pedida vence.
- **Arquivo mal formado:** a última versão boa, com a faixa «XHTML mal formado na linha L:C».
- **Sincronia.** Clique no Resultado → cursor no código **no caractere**, com entidades e
  figurinas contadas (H9). Cursor → realce do elemento no Resultado.

**S7 — PDF original e Comparar**

- O painel de PDF é o `PainelDoPdf` do tronco, fabricado pela casca: mesmo processo de trabalho e
  portão `quadros`.
- API nova: `VisorDePagina.realcar(retangulos_pt, papel)` (papéis `ORIGEM`, `DUVIDA`, `SELECAO`) e
  o sinal `clicado_em(pagina0, x_pt, y_pt)`.
- Cursor num bloco → a página dele e o `rect` aceso. Clique no PDF → o bloco de menor `rect` que
  contém o ponto.
- **Comparar** = Resultado e PDF lado a lado, acoplados pela página (`pg<N>` ↔ página N).
- «Seguir a janela principal» opcional.

**S8 — Revisão do OCR no editor**

- **A fila.** As dúvidas de `proveniencia.json`, os blocos DOUBTFUL/UNRELIABLE e os diagramas com
  `DiagramConfidence` abaixo do limiar, em ordem de leitura.
- **As ações:**

  | ação | tecla | efeito |
  |---|---|---|
  | Próxima dúvida / anterior | `F8` / `Shift+F8` | leva o cursor à dúvida, acende no Resultado e no PDF, abre o recorte |
  | Aceitar | `Ctrl+Enter` | grava uma `ReviewDecision(accept)` **pelo serviço único**; a aba Revisão de texto aberta vê na hora (aviso de mudança) |
  | Editar | digitar dentro do intervalo | resolve localmente; a página vira `EDITADA` |
  | Alternativas | `Ctrl+.` | das que o IR ou o `ocr_trace` tiverem; se não há, «sem alternativa registrada» |
  | Manter como imagem | — | `ReviewDecision(keep_image)` pelo serviço |

- O `blind_guard` continua valendo (R1.4 herdada).

**S9 — Menus e ferramentas (catálogo; a fase de cada item está no roadmap)**

| menu | comandos (tecla) |
|---|---|
| **Arquivo** | Gerar do OCR… · Gravar (`Ctrl+S`) · Gravar tudo (`Ctrl+Shift+S`) · Versões… · Exportar EPUB… (`Ctrl+E`) · Exportar ▸ DOCX / PDF / HTML · Abrir a pasta do projeto · Fechar arquivo (`Ctrl+W`) |
| **Editar** | Desfazer (`Ctrl+Z`) · Refazer (`Ctrl+Y`) · Recortar/Copiar/Colar · Colar como texto simples (`Ctrl+Shift+V`) · Selecionar o elemento (`Ctrl+Shift+A`) · Duplicar linha (`Ctrl+Shift+D`) · Mover linha (`Alt+↑/↓`) · Excluir linha (`Ctrl+Shift+K`) · Comentar (`Ctrl+/`) · Maiúsculas ▸ · Preferências do editor… |
| **Localizar** | Localizar (`Ctrl+F`) · Substituir (`Ctrl+H`) · Localizar no livro (`Ctrl+Shift+F`) · Próxima/anterior (`F3`/`Shift+F3`) · Buscas salvas… · Ir para linha (`Ctrl+G`) · Ir para página do PDF… (`Ctrl+Shift+G`) · Ir para diagrama N… · Próximo problema (`Ctrl+F8`) |
| **Inserir** | Parágrafo · Título 1–6 (`Ctrl+1…6`) · Lista ▸ · Tabela… · Imagem… · Diagrama de uma FEN… (`Ctrl+Shift+Q`) · Figurina ▸ ♔♕♖♗♘♙ · Símbolo de avaliação ▸ (! ? !! ?? !? ?! ⩲ ⩱ ± ∓ +− −+ = ∞ □ △ ⇆ ↑ → ⊕ N) · Quebra de página · Nota de rodapé · Link/âncora (`Ctrl+K`) · Caractere especial… · Recorte ▸ |
| **Formatar** | Negrito `strong` (`Ctrl+B`) · Itálico `em` (`Ctrl+I`) · Sublinhado `u` (`Ctrl+U`) · Tachado `s` · Versalete · Sobrescrito/Subscrito · Estilo do parágrafo ▸ · Aplicar classe… (`Ctrl+Shift+C`) · Remover classe · Envolver em elemento… (`Ctrl+Shift+W`) · Trocar elemento… (`Ctrl+Shift+E`) · Desembrulhar · Dividir/Juntar parágrafos · Idioma do trecho… · Limpar formatação · **Tipografia ▸** Aspas tipográficas · Travessões e meias-riscas · Espaços inseparáveis do xadrez · Juntar hifenização do OCR · Reticências · Normalizar Unicode · **Consertar e embelezar** (`Ctrl+Shift+I`) |
| **CSS** | Painel Estilos · Ir para a regra (`F12`) · Nova regra para este elemento… · Extrair estilo em linha para classe · Renomear classe no livro… (`F2`) · Regras não usadas… · Reformatar CSS · Cores do livro… · Fontes do livro… · Tema do livro ▸ (os 9 do CB + «Caissa Clássico») · Variáveis do tema… · O que o DOCX não recebe… |
| **Livro** | Metadados… (título, autores, idioma, editora, ISBN, direitos) · Capa… · Sumário e marcos… · Arquivos ▸ Novo · Renomear (com os links) · Dividir no cursor · Juntar com o próximo · Ordem da espinha… · Páginas ▸ Gerar intervalo… · Regerar página… · Marcar revisada |
| **Xadrez** | Editar posição… (`Ctrl+Shift+B`) · Copiar FEN · Colar FEN como diagrama · Estilo do diagrama… · Numerar diagramas · Lado a jogar ▸ · Estipulação… · Marcar lances do parágrafo · Verificar lances · Converter notação ▸ · Fonte das figurinas… |
| **Revisão** | Próxima dúvida (`F8`) · Anterior (`Shift+F8`) · Aceitar (`Ctrl+Enter`) · Alternativas (`Ctrl+.`) · Manter como imagem · Mostrar dúvidas (alternar) |
| **Validar** | Verificar arquivo · Verificar livro · EPUBCheck · Acessibilidade do livro (Ace) · Ortografia (`F7`) · Relatórios ▸ (classes, estilos, caracteres, imagens, links, diagramas, lances, fontes) |
| **Ver** | Leiaute ▸ Código+Resultado (`Ctrl+Shift+1`) / Código+PDF (`Ctrl+Shift+2`) / Comparar (`Ctrl+Shift+3`) / Três painéis (`Ctrl+Shift+4`) · Resultado ▸ Leitor / Página / Escuro · Dispositivo ▸ · Painéis ▸ · Sincronizar · Invisíveis · Quebra de linha · Dobrar/Desdobrar · Zoom (`Ctrl+=`/`Ctrl+-`/`Ctrl+0`) · Paleta de comandos (`Ctrl+Shift+P`) · Tela cheia (`F11`) · Próximo painel (`F6`) |
| **Ajuda** | Guia do editor (`F1`) · Atalhos · Contrato de marcação · Sobre os motores |

- A tecla de cada comando mora numa tabela só (S `editor/comandos.py`). Menu, barra, paleta e
  legenda são gerados dela. Teste: nenhuma duplicata, nenhum AltGr ABNT2, todo comando alcançável
  por menu e paleta.
- Toda ferramenta que transforma texto é função pura `(texto, seleção, contexto) → [TextEdit]`,
  no padrão de S `notation/text_ops.py`, aplicada num bloco de desfazer.
- Ferramentas de livro inteiro produzem um **plano** revisável (padrão `SubstitutionPlan` de S
  `notation/regex_engine.py`), aplicado numa transação.

**S10 — Validação e Problemas (S `editor/validacao/`)**

| camada | regra | quando |
|---|---|---|
| XML | bem-formado, com linha:coluna do `expat` | pausa (arquivo) |
| contrato | classes e atributos do `MARKUP_CAISSA`, `data-fen` válida, `data-stm` coerente, `img.cb-svg` coerente com a FEN (absorvido de `CB validate.py`) | pausa |
| xadrez | lance legal a partir do diagrama ou do lance anterior; idioma de notação misturado; figurina fora da fonte ativa | pausa / livro |
| CSS | sintaxe (`tinycss2`); propriedade desconhecida; propriedade que o **motor ativo** não desenha; o que o mapa de estilo não leva; **contraste AAA 1.4.6** — todo trecho de texto normal < 7:1 (ou grande < 4,5:1), medido na página renderizada pelo MuPDF `Story` (cor calculada × fundo local), com qualquer CSS do projeto | pausa (arquivo); bloqueia exportar |
| acessibilidade | `lang`; hierarquia de títulos; `alt` presente e que não afirme o não lido; `page-list` sem lacuna; **imagem de texto** (a região «mantida como imagem», 1.4.5 AA / 1.4.9 AAA — a transcrição tem de **substituir** a imagem); `<audio>`/`<video>`/`<track>`; `animation`/`transition`/`@keyframes`; interativo além de `<a href>` (`<form>`, controles, `contenteditable`, `tabindex` > 0); `position: fixed/sticky`; `outline: none` em `:focus` sem substituto; link sem propósito próprio (2.4.9); papel das regiões (1.3.6); símbolo fora do glossário (3.1.3); abreviatura da lista sem `<abbr>` (3.1.4); atributo com nome de campo de proveniência (R2.4c) | comando e antes de exportar |
| acessibilidade (oráculo externo) | **Ace do DAISY** sobre o EPUB temporário (ferramenta de medição instalada com consentimento; não vai no pacote) | antes de exportar, em fundo |
| segurança | R4.2 e R4.3 | pausa; bloqueia exportar |
| OCR | dúvidas pendentes | contínuo |
| EPUBCheck | `--json`, cada mensagem com arquivo:linha:coluna | comando e antes de exportar |

- Todo problema tem código, severidade (bloqueia / avisa / informa), local, «o que fazer» e,
  quando seguro, conserto.
- Nada roda na thread da janela.

**S11 — Exportação a partir do projeto**

| interface | hoje | depois |
|---|---|---|
| exportar do editor | — | `editor.exportacao.exportar(projeto, formato, destino)`: ler (D1) → `Document` com o CSS como recurso e as fontes do registro → exportador. **EPUB e HTML:** a estrutura por `escrever(ler(x))`, o CSS byte a byte; no EPUB, EPUBCheck 0 erros e Ace sem violação séria ou crítica, senão recusa com a lista. **PDF:** impressão pelo motor da prévia Página, com as mesmas páginas. **DOCX:** mapa de estilo mais avisos. **LaTeX:** estrutura mais o aviso único |
| metadados, capa, sumário | do IR importado | editados no menu Livro; `nav` com `toc`, `landmarks` e `page-list` |
| diálogo da janela principal | reimporta | «Fonte: projeto do Editor HTML/CSS (editado em …)» como padrão, com «Reimportar do PDF» ao lado |
| metadados de acessibilidade do EPUB | parciais (`epub.py:737-849`) | `accessMode`, `accessibilityFeature` (com `pageNavigation`), `accessibilityHazard`, `accessibilitySummary`, e `dcterms:conformsTo` EPUB Accessibility 1.1 — WCAG 2.2 AA **só** quando a verificação e o Ace passam |

### 5.3 Estados e transições

**Página do projeto:**

```
NAO_GERADA ──gerar──► GERADA ──edição──► EDITADA ──«marcar revisada» (0 dúvidas)──► REVISADA
                        ▲  │                │  ▲                                     │
                        │  └─entradas mudaram: GERADA regera sozinha; EDITADA/REVISADA → proposta (H25)
                        │                        (antes do H25: confirmação + versão)   │
                        └───── «descartar edições da página» (com versão) ◄────────────┘ (edição depois de revisada → EDITADA)
```

**Dúvida:** `pendente → aceita | editada | mantida_como_imagem`. Aceitar e manter gravam pelo serviço
único.

**Arquivo aberto:**

```
limpo → sujo → (diário a cada 2 s) → gravando → limpo
                                              → erro_de_gravacao (motivo + o que fazer; diário mantido)
qualquer → mudado_por_fora → recarregar | comparar | manter o meu
```

**Motor Chromium:**

```
ausente → baixando (progresso, cancelável) → verificando (SHA-256) → instalando (pasta parcial) → pronto
                                                                                                → falhou(motivo) → parcial apagada → reserva MuPDF
pronto → «remover» → ausente
```

**Janela:** `fechada → aberta(livro) → em_primeiro_plano`.
- Abrir um livro já aberto traz a janela existente.
- Fechar com arquivo sujo pergunta «Gravar / Descartar / Cancelar».
- Fechar a janela principal com o editor sujo faz a mesma pergunta, e «Cancelar» aborta o
  fechamento da principal.
- Uma queda deixa o diário. A próxima abertura oferece «Recuperar» com a diferença à vista.

### 5.4 Implicações de dados

- `editor/livros.json` — `{sha256: {"pasta", "pdf_nome", "criado_em"}}`.
- `projeto.json` e `proveniencia.json` — esquemas versionados (`formato: 1`) com migração testada.
- IR esquema **v2** (`html_attributes`) com migração v1→v2 e o `test_roundtrip_corpus` estendido.
- `labeling/revisao/<pdf>.json` e `labeling/diagramas/<pdf>.json` — pelo serviço único; campo
  `origem` (`"editor"`, `"revisao_de_texto"`, `"resultado"`).
- `editor/fontes.json` — `{familia: {"arquivo", "licenca", "origem", "fsType", "declarado_por",
  "data"}}`.
- `data/janela.json` — `AppState` v7.
- `packaging/`:
  - `editor` em `PASTAS_DO_USUARIO` / `PASTAS_GUARDADAS`;
  - `webengine_manifesto.json` (componente, H14);
  - o relatório de tamanho do pacote ganha a linha do componente;
  - a Noto Sans Symbols2 (OFL) em `ARTEFATOS_NAO_PYTHON`.
- `docs/MARKUP_CAISSA.md` (H3), `docs/quality/EDITOR_HTML_CSS_REPORT.md` (criado pelo H0).

### 5.5 Desempenho e segurança medidos (orçamentos; cada um com portão no roadmap)

| medida | orçamento | portão |
|---|---|---|
| bloqueio da thread da janela (abrir projeto de 300 páginas; digitar 60 s a 30 car/s em 500 KB com tudo ligado; trocar de arquivo; gerar em fundo; busca no livro) | ≤ 16 ms, pior de 3 | `bloqueio --janela editor` (H11, H12) |
| primeira pintura do código | ≤ 800 ms | `editor_abertura` (H12) |
| Resultado MuPDF: tecla → página visível repintada, 260 KB | p95 ≤ 400 ms depois da pausa | `previa --motor mupdf` (H13) |
| Resultado Chromium: tecla → DOM remendado, 260 KB | p95 ≤ 150 ms depois da pausa; frio ≤ 1,5 s | `previa --motor chromium` (H14) |
| componente Chromium | download ≤ 150 MB, instalado ≤ 300 MB, publicados | H1, H14 |
| clique ↔ cursor ↔ retângulo no PDF | ≤ 100 ms; acerto de 100 % em 400 pontos estratificados, semente 42 | `editor_sincronia.py` (H9, H15) |
| pan/zoom do PDF no editor | ≥ 55 fps @ p95, mediana de 3 | `quadros --janela editor` (H15) |
| validação de um arquivo de 260 KB | ≤ 500 ms fora da thread | `editor_validacao.py` (H10) |
| PDF do projeto × prévia Página | mesmo número de páginas, mesmas quebras, mesmo texto por página (100 %) | `editor_publicacao.py` (H24) |
| livro hostil | 0 requisições, 0 scripts, 0 arquivos fora do projeto; a exportação recusa com linha | `previa --hostil` (H13, H14) |
| memória extra com o editor aberto num livro de 300 páginas | MuPDF ≤ 400 MB; Chromium ≤ +350 MB | H1, H14 |

### 5.6 Acessibilidade

**A janela** (WCAG 2.2, com AAA onde é mensurável):
- **Teclado:** tudo em menu e paleta, ordem de foco declarada, `F6` entre painéis, `Esc` só para o
  transitório.
- **Leitor de tela:**
  - nome acessível em todo painel;
  - leitura do código pela UIA provada por sonda automática (H2) e confirmada com o Narrador;
  - anúncios pelo nome acessível do rótulo de estado — o PyQt6 não expõe `QAccessible` (lição do
    C14).
- **Contraste:** R3.2 e R3.3; o alto contraste do Windows é respeitado.
- **Escala** 150 %/200 % sem corte.
- **Alvos** ≥ 24×24 px.
- **Movimento:** nenhuma animação.

**O livro exportado.** A meta é EPUB Accessibility 1.1 com o **WCAG 2.2 AA inteiro**, **mais todo
critério AAA que se aplica a um livro estático**, com portão. A tabela abaixo cobre **todos** os
critérios AAA do WCAG 2.2. O Q7 decide o tema padrão.

| critério AAA | aplica ao livro? | o que o editor faz | portão |
|---|---|---|---|
| 1.2.6–1.2.9 (mídia) | não: o livro não tem áudio nem vídeo | o validador reprova `<audio>`, `<video>` e `<track>` (fixture) | H10, H24 |
| 1.3.6 identificar o propósito | sim: regiões | `epub:type`/`role` em capítulo, nota, figura; `landmarks` no `nav` | H24: 100 % das seções e notas com papel |
| 1.4.6 contraste melhorado | sim | 7:1 para texto normal e 4,5:1 para grande, com **qualquer** CSS, medido nas páginas renderizadas | H10, H19, H24 |
| 1.4.7 áudio de fundo | não | — | — |
| 1.4.8 apresentação visual | sim, mas **conflita com o texto justificado**, a norma tipográfica do livro de xadrez | tema «Leitura AAA», com as cinco exigências do critério: (1) **cores selecionáveis pelo usuário** — o tema não fixa `color` nem `background-color` do conteúdo principal, só de elementos secundários (técnicas C23/C25 do W3C), e nunca com `!important`, então o tema do leitor de EPUB (claro, sépia, noturno) vale; (2) largura ≤ 80 caracteres; (3) não justificado; (4) entrelinha ≥ 1,5 e espaço entre parágrafos ≥ 1,5 × a entrelinha; (5) sem rolagem horizontal a 200 %. Se é o padrão, decide o **Q7** | H19: as cinco medidas; a (1) por análise do CSS **e** renderizando com uma folha do usuário que troca as cores — o texto principal tem de assumi-las |
| 1.4.9 imagem de texto (sem exceção) | sim: a região «mantida como imagem» **é** imagem de texto, e já fere o 1.4.5 AA — a exceção é só decorativa ou essencial, e **transcrição no alt não basta** | «Transcrever a região»: o texto revisado **substitui** a imagem, e a página vira `EDITADA`. Com qualquer imagem de texto restante, **nenhuma** declaração de conformidade (nem AA). O relatório as conta | H10, H24: 0 imagens de texto para declarar |
| 2.1.3 teclado (sem exceção) | sim: só links | o validador reprova todo interativo além de `<a href>`: `<form>`, `<input>`, `<button>`, `<select>`, `<textarea>`, `<details>`, `contenteditable`, `tabindex` > 0, `on*` | H10 (fixture de cada um), H24 |
| 2.2.3–2.2.6 (tempo) | não: sem limite de tempo | o validador reprova `<meta http-equiv="refresh">` e script (R4.2) | H10, H24 |
| 2.3.2 três lampejos; 2.3.3 animação por interação | sim | nenhuma animação: o validador reprova `animation`, `transition`, `@keyframes` e GIF/APNG animado | H10, H24 |
| 2.4.8 localização | sim | `nav` com `toc`, `landmarks` e `page-list`; título por capítulo | H24 |
| 2.4.9 propósito do link (só o link) | sim | todo link com texto ou `aria-label` que diga o destino («ir para o diagrama 12», «voltar à nota 3»), nunca «↩» sozinho | H24: 100 % |
| 2.4.10 cabeçalhos de seção | sim | títulos por seção | H24 |
| 2.4.12 foco não encoberto (melhorado); 2.4.13 aparência do foco | sim, nos links: o conteúdo pode esconder ou apagar o foco | o validador reprova `fixed`/`sticky` e `outline: none` sem substituto (o aviso cedo). **A prova é renderizada e geométrica**, pelo arnês de medição Chromium do H1 (`benchmarks/editor_chromium_medicao.py`, que roda no ambiente de medição, mesmo que o produto não leve o componente), com o **contrato executável do Apêndice D**: viewport, escala, coordenadas, espera do foco, limiar de pixel, pseudo-elementos. Para **todo** link do livro, focado por `Tab`: (a) **nenhuma parte encoberta** — em **todo** pixel CSS da união dos retângulos do link (`getClientRects()`, então link de várias linhas conta) e da área do indicador de foco, `elementsFromPoint` devolve no topo o próprio link ou um descendente; (b) **área do indicador** — os pixels que mudam entre a captura não focada e a focada, na mesma escala, somam ≥ a soma dos perímetros dos retângulos não focados × 2 px CSS; (c) **contraste** ≥ 3:1 entre os dois estados, pixel a pixel, na área mínima exigida | H19 (os temas), H24 (o livro) |
| 2.5.5 alvo melhorado | sim: link em linha está na exceção; link **fora** de linha (entradas do sumário, «voltar», links de bloco) precisa de 44×44 px CSS | os temas dão às entradas do `nav` e aos links de bloco altura de linha e área ≥ 44 px CSS. As exceções de alvo equivalente, de controle do agente e de apresentação essencial **não** são modeladas: o portão é conservador, pode reprovar a mais e nunca aprova a mais | H24: medido nas páginas renderizadas (retângulos do `element_positions`), 100 % dos alvos fora de linha |
| 2.5.6 mecanismos de entrada | sim | nenhum conteúdo restringe a modalidade de entrada (sem script, R4.2) | H10 (a regra de script) |
| 3.1.3 palavras incomuns | sim: símbolos de avaliação **e jargão** | **glossário** gerado e ligado no `nav`, a partir de um **inventário revisado de candidatos**. Os candidatos: (1) os NAG e as figurinas usados; (2) os termos do **léxico do contrato** (`editor/glossario/<idioma>.json`: zugzwang, oposição, fortaleza, casa de fuga…, pt/en/de/ru/es) presentes no livro; (3) toda palavra que o dicionário geral do idioma do livro não conhece e que não é notação; (4) os termos que o usuário marcar. **Uso restrito de palavra comum** (a «oposição» do xadrez) só se detecta pelo léxico ou pela pessoa — por isso a revisão é humana: cada candidato recebe «definir» (vai ao glossário com a definição) ou «uso comum» (fica registrado), e o inventário leva a **atestação** de quem revisou e quando (`editor/glossario/revisao.json`). Como a palavra comum usada como jargão **só uma pessoa acha**, a atestação é de **leitura integral**: o modo «Revisão de termos» percorre cada capítulo parágrafo a parágrafo, deixa marcar qualquer palavra como termo, e registra por capítulo quem o percorreu inteiro, quando e o **SHA-256 do texto do capítulo** revisado (os nós de texto do XHTML, normalizados). **Qualquer mudança no texto do capítulo vence a atestação**: o validador mostra «atestação vencida» e o capítulo volta a precisar da leitura | H24: 100 % dos candidatos com decisão, 100 % dos «definir» com definição e **100 % dos capítulos com a atestação de leitura integral cujo hash é o do texto atual** — só então o 3.1.3 conta como cumprido. O limite fica dito no relatório: a completude do jargão é atestada por uma pessoa, não medida por máquina |
| 3.1.4 abreviaturas | sim (GM, MI, ECO…) | `<abbr title>` para as abreviaturas de uma lista do contrato | H24: 100 % das da lista |
| 3.1.5 nível de leitura | sim | o critério aceita **conteúdo suplementar**: o editor oferece o bloco «Resumo em linguagem simples» (`section.cb-resumo-simples`) por capítulo, escrito pelo usuário. Exigir em **todo** capítulo é mais estrito que o WCAG, que pede o suplemento onde o texto exige leitura avançada; como o nível de um texto técnico de xadrez não se mede com confiança, fica a regra conservadora. Sem o resumo, o 3.1.5 fica **não cumprido** e dito | H24: com o Q7 (iv), 100 % dos capítulos com o resumo |
| 3.1.6 pronúncia | não | — | — |
| 3.2.5 mudança a pedido | sim | sem script (R4.2) e sem `meta refresh` | H10, H24 |
| 3.3.5, 3.3.6, 3.3.9 (formulários) | não: o livro não tem formulário | o validador reprova `<form>` e controles (a regra do 2.1.3) | H10, H24 |

- **A declaração de conformidade AAA** (`dcterms:conformsTo` … WCAG 2.2 Level AAA) é possível, e
  exige três coisas que mudam o livro:
  - o tema «Leitura AAA» (texto não justificado) como o do livro (1.4.8);
  - zero imagens de texto (1.4.9);
  - o resumo em linguagem simples em todo capítulo, escrito pelo usuário (3.1.5).
- Sem elas, o livro declara **AA** e o relatório lista, critério a critério, cada AAA cumprido.
- Qual das duas o produto entrega é do usuário (**Q7**). **H19 e H24 não começam sem a resposta.**

Em detalhe:
- `lang` no documento e nos trechos.
- Hierarquia de títulos sem salto.
- `nav` com `toc`, `landmarks` e **`page-list`** dos marcadores, com o fólio impresso.
- **Alt de diagrama descritivo, gerado da FEN**, por exemplo: «Diagrama 12. Brancas: Rg1, Tc1,
  peões a2, b2. Pretas: Rg8, Dd8. Brancas jogam». Diagrama não conferido diz «posição lida por
  reconhecimento, não conferida».
- Figurina lida pelo leitor de tela: Unicode, ou a letra do livro com fonte de xadrez (MARKUP).
- **Temas de livro:** **todo texto de tamanho normal ≥ 7:1** (WCAG 1.4.6) — texto corrido,
  legendas, notas, lances, figurinas e texto sobre realce.
  - Só o «texto grande» (≥ 18 pt, ou ≥ 14 pt em negrito, no tamanho **calculado**) admite 4,5:1.
  - O escuro do leitor segue as mesmas razões.
- **Oráculo externo:** o **Ace do DAISY** roda antes de exportar, e violação séria ou crítica
  bloqueia. Um **corpus negativo** (≥ 20 EPUBs com um defeito cada) prova que a verificação própria
  e o Ace acusam o que devem (H24).

### 5.7 Segurança, licenças, política

- R4 inteiro.
- **Componente Chromium:** rodas `PyQt6-WebEngine` e `PyQt6-WebEngine-Qt6` da versão do PyQt6 do
  pacote, SHA-256 no manifesto e licenças inventariadas (GPL-3.0 Riverbank; LGPL-3.0 Qt; avisos
  de terceiros do Chromium). Instalação também por pasta.
- **Absorvidos do CB** (temas, validador de contrato): cabeçalho «Origem:», GPLv3 no inventário.
- **JS de terceiros no Chromium** (remendo de DOM tipo `morphdom`, MIT): vendorizado, com licença
  e hash fixo; sem CDN.
- **Ferramentas de medição que não vão no pacote** (Ace/npm, `pywinauto`): versão fixa, instaladas
  com consentimento, fora do inventário do produto.
- **Fontes:** o registro do §5.4. Sem declaração, o livro usa figurinas Unicode com a Noto Sans
  Symbols2 (OFL 1.1). Nenhuma fonte do acervo do usuário vai ao pacote.

### 5.8 Observabilidade

- Relatório de geração por página: blocos, dúvidas, diagramas, normalizações N1–N4 e tempo.
- Relatório de exportação:
  - fidelidade (`export/fidelity.py`);
  - `DegradationWarning` por código, incluindo `css-fora-do-mapa`;
  - EPUBCheck e Ace, mensagem a mensagem;
  - acessibilidade.
- Log `logs/editor_html.log`: aberturas, gravações, recuperações, conflitos de decisão, falhas de
  motor com pilha.
- Portões com JSON em `benchmarks/reports/editor/<passo>/`, com o hash dos dois repositórios e a
  marca de árvore suja.

---

## 6. NÃO-OBJETIVOS

- **Edição direta no Resultado (WYSIWYG).** A pré-visualização é clicável e sincronizada, não
  editável. O Sigil abandonou o Book View pelo HTML ruim que ele gerava.
- **Scripts no livro, animações, formulários.** Nunca.
- **EPUB de leiaute fixo.**
- **Abrir qualquer EPUB do mundo como projeto.** Abrir EPUB do Caissa ou do CB é o H27 (opcional).
- **Cursores múltiplos, minimapa e Emmet** na v1.
- **Tradução do livro, LLM no texto** (R1.5), colaboração, nuvem, telemetria.
- **Migração PyQt6 → PySide6** (ADR-0009).
- **Trocar o renderizador de tabuleiro.** É o de S `typeset/board_svg.py`, o mesmo do EPUB.
- **Levar ao DOCX o CSS fora do mapa de estilo.** É declarado e avisado, não traduzido (D1).

---

## 7. QUESTÕES ABERTAS (bloqueiam o passo que as cita)

| # | questão | bloqueia | recomendação |
|---|---|---|---|
| Q0 | Aprovar D1–D5 como ADR-0010…0014 em `docs/adr/README.md`? | registro das ADRs | sim, depois da crítica |
| **Q1** | **Qual OCR alimenta o editor?** (A) o **do produto** (`import_pdf` → IR, o que a exportação usa, com as decisões de revisão e de diagrama, a cifra e o modelo do livro), com a ponte da aba Texto **obrigatória** (H26); (B) o **da aba Texto** (`ler_pagina`), o que exige FEN nos diagramas dele, um importador `PaginaLida → IR` novo e as decisões refeitas nesse caminho; (C) **unificar**: a aba Texto passa a mostrar o OCR do produto, e o leitor dela vira mais um candidato do produto, como o leitor de glifos já é | **H8** (geração) e H26 | decidir **com os números do H0** e pela **regra de decisão** dele. **Medida:** ≥ 150 regiões com verdade de ≥ 2 livros (um digitalizado, um nativo), partições `dev`+`calib`, a cega fora, com o hash do manifesto registrado. **Estatística:** por estrato *s*, Δ*s* = CER(aba Texto) − CER(produto), com intervalo de 95 % por reamostragem; o leitor da aba Texto **vence** em *s* ⇔ o limite **superior** do intervalo de Δ*s* < 0. **Regra, mutuamente exclusiva, nesta precedência:** **B** ⇔ vence em todos os estratos; senão **C** ⇔ vence em ao menos um (entra como candidato do produto onde vence); senão **A**. Recomendação provisória, até os números: **A agora, C como direção** |
| Q2 | O motor Chromium: (a) componente sob demanda; (b) dentro do instalador (fura o teto de 150 MB); (c) só MuPDF | H14 | **(a)**, se o H1 aprovar a sonda PyInstaller e a máquina limpa; senão a pergunta volta com os números |
| Q3 | Adotar o contrato `cb-*` como contrato público do Caissa (D2)? | H5 | **sim** |
| Q4 | Onde mora o projeto: `editor/` ao lado do executável ou pasta escolhida? | H6 | a padrão ao lado do executável, com «Mover o projeto…» |
| Q5 | Fontes de xadrez sem licença declarada: embutir quando o usuário declara, ou nunca? | H24 | **só com declaração** (R1.14) |
| Q6 | Tema padrão do livro | H19 | comparação às cegas de `quality-chess`, `nic-classic` e `informator` contra páginas reais |
| **Q7** | **O «AAA» do livro** (§5.6). **(i)** AA inteiro + todo AAA aplicável que não muda o livro; declara AA. **(ii)** o mesmo, com o tema «Leitura AAA» (não justificado) como padrão; declara AA. **(iii)** só AA. **(iv) AAA formal:** tema «Leitura AAA», zero imagens de texto e o resumo em linguagem simples em todo capítulo; declara **AAA** | **bloqueia H19 e H24** | **sem padrão: muda o produto.** A nota técnica: (iv) é viável, mas custa a tipografia justificada e a escrita dos resumos; (i) mantém a tipografia tradicional e cumpre todo AAA que não a muda. O pedido «nível AAA» pode ser qualidade de produto ou WCAG AAA — só o usuário diz |

---

## 8. PASSAGEM

- **Pronto para implementação direta:**
  - **H0** (a infraestrutura dos portões e a medição que informa o Q1);
  - depois dele, H1–H4 e H6–H7, independentes entre si.
- **Precisa de decisão do usuário:**
  - Q1, antes do H8, com os números do H0;
  - Q2, antes do H14, com os números do H1;
  - Q3, antes do H5;
  - Q5, antes do H24;
  - Q7 (o «AAA» do livro), antes do H19 e do H24.
- **Precisa de ação do usuário:**
  - habilitar o Windows Sandbox, ou dar uma VM, para a máquina limpa do H1 e do H14;
  - consentir os downloads de medição (rodas do QtWebEngine; `pywinauto`; Ace via npm).
- **Próxima trilha:** `EDITOR_HTML_CSS_ROADMAP.md`.
- **Crítica:** Codex nos documentos e em cada fase; crítico visual às cegas (Sigil com o fork
  ChessBook, Calibre Editar Livro, ABBYY FineReader na verificação, VS Code na ergonomia de edição)
  no fim das fases 2 e 5.

---

## 9. O que a crítica mudou (Codex, ciclo 1 → versão 1.1)

O ciclo 1 reprovou com 12 bloqueantes (vereditos em `quality/EDITOR_HTML_CSS_CRITICAS.md`).

| # | bloqueante | o que mudou |
|---|---|---|
| 1 | §2.1 afirmava a perda da digitação, e `janela.py` = 2.077 como fato atual | §2.1 separa o HEAD (perdia) da mudança em andamento sem commit (guarda); §2.5 dá HEAD 2.077 × árvore 2.080; R1.12 mede a diferença do passo |
| 2 | ida e volta «sem perda» impossível com CSS arbitrário | D1 dividida: estrutura pelo IR (com `html_attributes`, esquema v2); CSS como recurso verbatim no EPUB e **mapa de estilo fechado** com aviso por regra no DOCX/PDF/LaTeX (S3b, R2.2) |
| 3 | Chromium em `runtime/` sem prova, e a medida do pacote o excluiria | D3: sonda PyInstaller real, máquina limpa, orçamento próprio do componente, instalação atômica, remoção, manifesto como raiz de confiança |
| 4 | editor nativo decidido antes de provado | D4 provisória; o H2 mede com todas as funções ligadas e sonda UIA; o H2b (QScintilla) existe como passo |
| 5 | rota de teclas entre duas `QMainWindow` não especificada | R3.6 com pop-up, AltGr, tecla morta, execução positiva, janela principal ativa e duas janelas do editor; portão positivo e negativo (H11) |
| 6 | decisões partilhadas sem serviço, trava ou teste concorrente | R5 e o H7: serviço único com trava entre processos, releitura, fusão por chave, aviso de mudança e testes concorrentes |
| 7 | portões que aprovam implementação vazia | todo portão com casos dourados e contagens esperadas; sabotagem «operação nula» / «plano vazio» / «zero lances» |
| 8 | grafo incompleto | o roadmap §1 vira tabela única de dependências (H22/H23 → H24; H16/H22 → H25) |
| 9 | «não perder trabalho» sem percurso na janela | R2.8 detalhado e o passo novo **H17** (fechar, fechar a principal, queda e recuperação, um livro numa janela, erro de gravação, mudança por fora, versões) |
| 10 | Q1 decidido às escondidas | Q1 com as opções A/B/C e as consequências de cada uma; o **H0** mede os dois leitores; o H8 fica bloqueado até a decisão; a ponte da aba Texto deixa de ser opcional na opção A |
| 11 | AAA só nos pares declarados | R3.2/R3.3: descoberta de cores em tempo de execução, medida nos pixels em todos os estados, forma além da cor, simulação de daltonismo (H12) |
| 12 | acessibilidade e segurança só com validador próprio | Ace do DAISY como oráculo externo; corpus negativo de ≥ 20 EPUBs; temas com texto corrido ≥ 7:1 (S10, §5.6, H24) |

**O ciclo 2 (versão 1.1)** reprovou com 8 bloqueantes. Dos 12 do ciclo 1, 8 estavam resolvidos e 4
parciais. A versão 1.2:

| # | bloqueante c2 | o que mudou |
|---|---|---|
| 1 | `janela.py` «1.808 no HEAD» × 2.077 | a contagem da 1.1 estava certa (2.077, `wc -l`). O comando do Apêndice A.3 é que estava errado: `Measure-Object -Line` pula linhas vazias. A.3 corrigido; §2.5 e R1.12 dizem como contar; o HEAD da suíte atualizado (`bb41c55`, a fase 5 foi commitada durante a sessão) |
| 2 | o serviço de decisões não cobria a aba Revisão de texto (`revisao_de_texto.py:623`) | R5 lista os três escritores; um teste de arquitetura reprova gravação fora de `ocr/decisoes.py` |
| 3 | a tabela de dependências contradizia os passos (H8→H9, H8→H13/H15, H5→H19) | tabela refeita a partir do que cada passo **usa**; o grafo ASCII saiu (fonte única) |
| 4 | PDF e LaTeX prometidos sem portão | o PDF passa a ser a impressão da prévia Página (portão de igualdade de páginas); o LaTeX, estrutura + aviso único (portão do aviso); o DOCX fica com o mapa (R2.2c–e) |
| 5 | a Q1 decidida com evidência insuficiente | o H0 exige ≥ 150 regiões com verdade de ≥ 2 livros, `dev`+`calib`, intervalo de 95 % e a regra A/B/C (§7) |
| 6 | funções do editor sem caso dourado | o H2 prova que cada função **estava ligada** durante a medida; o H12 tem um caso dourado e uma sabotagem `funcao_nula:<nome>` por função |
| 7 | «AAA» aceitava 4,5:1 em texto normal | 7:1 para todo texto de tamanho normal (código, temas, legendas, realce); 4,5:1 só para texto grande medido pelo tamanho calculado (R3.2, §5.6) |
| 8 | o desfazer de conflito prometido e não testado | histórico de decisões só de acréscimo, «restaurar a outra», desfazer, nos **dois** armazéns; gravação atômica testada nos dois (R5, H7) |

Correção da contagem: o ciclo 2 deu **8 resolvidos e 4 parciais** (1, 6, 7, 8) dos 12 do ciclo 1, e
não «7 e 5» como a versão 1.2 escreveu.

**O ciclo 3 (versão 1.2)** reprovou com 9 bloqueantes, mais estreitos. A versão 1.3:

| # | bloqueante c3 | o que mudou |
|---|---|---|
| 1 | o teste de arquitetura do H7 era por padrão de texto e não pegava o alias `record(...)` de `qt/decisoes_de_diagrama.py:106` | exclusividade **estrutural**: a escrita pública deixa de existir (`_gravar`/`_registrar` privados), e o teste por AST pega atributo, nome importado, alias e `getattr` (R5) |
| 2 | a regra A/B/C sem sinal nem precedência | Δ = CER(aba Texto) − CER(produto); «vence» ⇔ limite superior < 0; precedência B → C → A, mutuamente exclusiva; hash do manifesto no relatório (§7 Q1, H0) |
| 3 | R1.10 contradizia R2.2/S3b sobre PDF/LaTeX | R1.10 e §3.6 remetem ao R2.2 c–e como definição única |
| 4 | o H24 usa a matriz do H1 sem depender dele | H1 na coluna do H24 |
| 5 | a D4 podia passar por contadores | o H2 exige ≥ 5 casos dourados por função; o H2b reabre também quando o H12 reprova por limite do componente |
| 6 | AAA prometido e livro declarado AA | o livro: AA inteiro + AAA 1.4.6 e 2.4.10 medidos com qualquer CSS; os outros AAA não prometidos, com a razão; `conformsTo` AA (§5.6, S10) |
| 7 | o portão não procurava confiança, motor ou nota no EPUB | a exportação do editor não embute o IR; varredura de proveniência em todos os arquivos do EPUB (R2.4, H24) |
| 8 | o H11 ainda media `janela.py` por `numstat` | contagem antes e depois do passo (H11, §0.3) |
| 9 | o desfazer «da janela» sem a transação | `Recibo` por gravação; o editor e a aba Resultado o põem na pilha; a aba Revisão de texto restaura pelo aviso (R5, H7) |

**O ciclo 4 (versão 1.3)** reprovou com 4 bloqueantes; dos 9 do ciclo 3, 5 resolvidos e 4 parciais. A versão 1.4:

| # | bloqueante c4 | o que mudou |
|---|---|---|
| 1 | o H7 exigia o desfazer do editor, que só nasce no H16/H22 | o H7 prova o serviço, o recibo, o `Ctrl+Z` da aba Resultado e o «restaurar» da aba Revisão de texto; o desfazer da decisão **no editor** é portão do H16 e do H22 |
| 2 | «todo nó tem proveniência» é falso, e a varredura era por lista de palavras | a proveniência é opcional por nó (`base.py:58-63`); o sidecar do editor passa a levar todo bloco do `proveniencia.json` (portão de completude); `embed_ir=False` forçado e testado; a varredura do EPUB é por **lista de permissão** (tipos de arquivo, metadados do OPF, atributos iguais aos do projeto) e os nomes proibidos saem por introspecção das dataclasses (R2.4) |
| 3 | «AAA» reduzido a dois critérios sem decisão do usuário | a tabela de **todos** os AAA do WCAG 2.2 com aplicabilidade, ação e portão; o tema «Leitura AAA» para o 1.4.8; a imagem de texto (1.4.5/1.4.9) como bloqueante da declaração; e o **Q7** ao usuário (§5.6, §7) |
| 4 | o teste estático não pegava escrita crua no armazém | guarda de execução por `sys.addaudithook` (`open` com escrita, `os.replace`, `os.rename`, `os.remove`) sob `labeling/revisao/` e `labeling/diagramas/`, durante a suíte e os percursos (R5, H7) |

**O ciclo 5 (versão 1.4)** reprovou com 7 bloqueantes; dos 4 do ciclo 4, 1 resolvido e 3 parciais. A versão 1.5:

| # | bloqueante c5 | o que mudou |
|---|---|---|
| 1 | o H24 ainda dizia «proveniência em todo nó» | corrigido; o sidecar é comparado **campo a campo** com o `proveniencia.json`; nó sem proveniência não tem registro (R2.4, H24) |
| 2 | a lista de permissão aceitaria `data-confidence` escrito no projeto | atributo com nome de campo de proveniência é bloqueante mesmo vindo do usuário, com «remover» (R2.4c, S10) |
| 3 | o `Rect` do sidecar podia continuar quebrado | o H4 exige os itens 1, 2 e 10 com fixture positiva (um `Rect` real do importador) |
| 4 | a guarda nomeava um evento `os.replace` que não existe | eventos medidos nesta sessão (3.10.11 e 3.11.9): `open` por modo **ou** flags, `os.rename` (que o `os.replace` dispara), `os.remove`; canonização por `realpath`, `normcase` e nome longo (R5, H7) |
| 5 | «transcrição basta» para o 1.4.9 | a transcrição **substitui** a imagem; com imagem de texto restante, nenhuma declaração de conformidade (§5.6) |
| 6 | as linhas «por construção» sem portão | cada uma virou regra do validador com fixture e portão: interativos, `meta refresh`, animação, `fixed`/`sticky`, foco apagado, `a:focus-visible` dos temas, alvo de 44 px fora de linha (§5.6, H10, H19, H24) |
| 7 | a Q7 sem decisão e com padrão rebaixado | a Q7 ganha a opção **(iv) AAA formal** (tema «Leitura AAA», zero imagens de texto, resumo em linguagem simples por capítulo), **sem padrão**, e **bloqueia** H19 e H24 (§5.6, §7) |

**O ciclo 6 (versão 1.5)** reprovou com 4 bloqueantes. Dos 7 do ciclo 5, 5 ficaram resolvidos; o 1 (sidecar) e o 6 (portões AAA) ficaram **parciais**. A versão 1.6:

| # | bloqueante c6 | o que mudou |
|---|---|---|
| 1 | sidecar «completo» sem esquema fechado | esquema por introspecção: todo campo de `Provenance`, `DiagramSource`, `RecognitionResult` e das decisões; teste de igualdade dos conjuntos de campos; fixture com todos os campos fora do padrão (R2.4) |
| 2 | o 1.4.8 sem a seleção de cores | o tema «Leitura AAA» não fixa cor do conteúdo principal (C23/C25), sem `!important`; provado renderizando com uma folha do usuário (§5.6, H19) |
| 3 | 2.4.12/2.4.13 por procuração | prova renderizada de **todo** link num Chromium do ambiente de medição: não encoberto (`elementFromPoint`), área do indicador ≥ perímetro de 2 px, contraste 3:1 (§5.6, H19, H24) |
| 4 | o 3.1.3 só com símbolos | glossário com símbolos **e** jargão, a partir de um léxico por idioma do contrato (revisado pelo usuário), mais os termos acrescentados; cobertura de 100 % (§5.6, H24) |

**O ciclo 7 (versão 1.6)** reprovou com 4 bloqueantes. Dos 4 do ciclo 6, 1 resolvido (o 1.4.8) e 3 parciais. A versão 1.7:

| # | bloqueante c7 | o que mudou |
|---|---|---|
| 1 | o sidecar sem formato exato nem as classes aninhadas | JSON Lines com cabeçalho e `esquema` por introspecção recursiva; as dez classes nomeadas (incluindo `FenCandidate`, `SquareRepair`, `ReviewItem`, `AuditEntry`, `Decided`, `DiagramDecision`); três tipos de registro; versão 2 com migração da 1; o exemplo do `proveniencia.json` completo (S2, R2.4) |
| 2 | a lista proibida escrita à mão e incompleta | gerada por introspecção recursiva (`snake_case` e `kebab-case`), procurada nas posições estruturadas de todo recurso publicado, com lista de exceção fechada no teste (R2.4d) |
| 3 | foco por cinco amostras | cobertura geométrica **completa**: todo pixel CSS da união dos retângulos e da área do indicador, link de várias linhas incluído; área e contraste pixel a pixel; o arnês é entrega do H1 (§5.6, H1, H19, H24) |
| 4 | o 3.1.3 só com o léxico | inventário de candidatos (símbolos, léxico, palavra fora do dicionário, marcadas pelo usuário) com decisão por candidato e **atestação** humana (§5.6, H24) |

**O ciclo 8 (versão 1.7)** reprovou com 3 bloqueantes; dos 4 do ciclo 7, 1 resolvido (a lista proibida) e 3 parciais. Ele achou também um caminho corrompido no H4: um `\r` e um `\a` que o shell da ferramenta interpretou dentro de um heredoc (a armadilha já registrada na memória). A versão 1.8:

| # | bloqueante c8 | o que mudou |
|---|---|---|
| 1 | o sidecar v2 sem esquema canônico nem mapeamento da v1 | **Apêndice C**: codificação canônica, todos os campos presentes, tipos e nulidade, as dez etiquetas, os quatro tipos de registro, o exemplo, o mapeamento campo a campo da v1 de hoje (`export/provenance.py:41-153`) e as fixtures douradas escritas pelo crítico |
| 2 | o arnês de foco sem contrato operacional | **Apêndice D**: viewport e rolagem, escala do dispositivo e conversão de coordenadas, serialização dos resultados, espera do foco, captura sem hover nem cursor, região e limiar da diferença, pseudo-elementos, e o autoteste com cinco fixtures |
| 3 | o 3.1.3 não atestava o texto inteiro | atestação de **leitura integral por capítulo** no modo «Revisão de termos», e o limite dito: a completude do jargão é humana (§5.6, H24) |

**O ciclo 9 (versão 1.8)** reprovou com 3 bloqueantes; o 3.1.3 e o caminho do H4 ficaram resolvidos. A versão 1.9:

| # | bloqueante c9 | o que mudou |
|---|---|---|
| 1 | o sidecar dependia dos `as_dict()` que arredondam, e as fixtures douradas não existiam antes da implementação | serializador canônico próprio (reflexão dos campos), etiquetas do registro para as seis classes registradas, tipos fechados (`Any` só nativo de JSON, senão erro), `extras_v1` sempre presente, `rect` da v1 em lista ou objeto; as fixtures douradas escritas pelo crítico **no H3** e congeladas por SHA-256 (Apêndice C). A afirmação «nenhuma tem etiqueta» estava errada — seis têm |
| 2 | o arnês tratava a pintura do contorno como elemento encobridor | o encobrimento se mede em duas partes: `elementsFromPoint` só dentro das caixas do link; o indicador, por **máscara** — o que muda na renderização isolada (os outros elementos em `visibility: hidden`) e não muda na normal está encoberto. Área e contraste na máscara real. Autoteste com `outline` e `box-shadow` sem falso encoberto (Apêndice D) |
| 3 | a atestação não se prendia ao texto revisado | a atestação guarda o SHA-256 do texto do capítulo; qualquer mudança a vence (§5.6, H24) |

**O ciclo 10 (versão 1.9)** reprovou com 2 bloqueantes; o 3.1.3 ficou resolvido. A versão 1.10:

| # | bloqueante c10 | o que mudou |
|---|---|---|
| 1 | o cabeçalho do sidecar leva `gerado_em` e o commit, que mudam a cada execução, e a fixture é comparada byte a byte | relógio e commit **injetáveis**; as fixtures com valores fixos; a igualdade byte a byte inteira; os valores reais por teste de invariantes (Apêndice C) |
| 2 | a máscara não pegava pseudo-elemento de ancestral (`body::after`) | na renderização isolada, os `::before`/`::after` dos ancestrais (com `html` e `body`) ficam ocultos, e a pintura de ancestral que pode passar por cima (`outline`, `box-shadow`) fica em `none`; fixture (6) nova no autoteste e sabotagem `pseudo_do_body` (Apêndice D, H1, H19, H24) |

O autoteste do arnês tem **sete** fixtures desde a 1.10 — a tabela do ciclo 8 falava em cinco, a
do ciclo 9 em seis. O exemplo do Apêndice C passou a mostrar `extras_v1`.

**O ciclo 11 (versão 1.10): APROVADO**, sem bloqueante. Os dois do ciclo 10 ficaram resolvidos. Dos
dois não bloqueantes que ele deixou, a versão final trata os dois:
- a neutralização da máscara prova que venceu o CSS do autor (Apêndice D);
- o histórico do roadmap §9 fica em ordem cronológica.

Veredito: «A 1.10 pode avançar para execução dos passos».

---

## Apêndice A — como reproduzir os números do §2

**A.1 MuPDF `Story` como motor paginado** (`.venv-pack\Scripts\python.exe`, ~10 s):

```python
import io, statistics, time, chess, chess.svg, pymupdf
svg = chess.svg.board(chess.Board("8/8/3k4/2p5/1pP5/1P1K4/8/8 w - - 0 1"), size=240)
arq = pymupdf.Archive(); arq.add(svg.encode(), "dg1.svg")
CSS = ("body{font-family:serif;font-size:10pt} p{text-indent:1.2em;margin:0;text-align:justify}"
       " p.movetext{font-weight:bold} figure.cb-diagram{text-align:center} figure.cb-diagram img{width:45mm}")
def cap(n):
    s = ["<h2 id='h1'>Chapter 1</h2>"]
    for i in range(n):
        s += [f"<p id='p{i}'>The pawn ending is the ultimate realisation of White's dream. "
              "The protected passed pawn is invincible, while Black will find it awkward to keep "
              "defending the b-pawn.</p>", f"<p id='m{i}' class='movetext'>54...♔c6 55.♔b4 ♔b6 56.e6 ♔d6</p>"]
        if i % 6 == 0: s.append(f"<figure id='d{i}' class='cb-diagram'><img src='dg1.svg'/></figure>")
    return "<body>" + "".join(s) + "</body>"
def medir(n):
    t0 = time.perf_counter(); st = pymupdf.Story(html=cap(n), user_css=CSS, archive=arq)
    out = io.BytesIO(); w = pymupdf.DocumentWriter(out); pos = []; mb = pymupdf.paper_rect("a5"); pg = 0
    mais = True
    while mais:
        dev = w.begin_page(mb); mais, _ = st.place(mb + (36, 36, -36, -36))
        st.element_positions(lambda p: pos.append(p)); st.draw(dev); w.end_page(); pg += 1
    w.close(); t1 = time.perf_counter(); d = pymupdf.open("pdf", out.getvalue())
    t2 = time.perf_counter(); d[0].get_pixmap(dpi=96); t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000, pg, len(pos)
for n in (12, 120):
    r = [medir(n) for _ in range(5)]
    print(n, r[0][2], r[0][3], round(statistics.median(x[0] for x in r), 1),
          round(statistics.median(x[1] for x in r), 1))
```

Saída em 2026-09-23: `12 2 54 10.3 5.7` e `120 17 522 89.1 5.4`.

**A.2 Os fatos do ambiente** (§2.6):
- `.venv-pack\Scripts\python.exe -c "import PyQt6.QtWebEngineWidgets"` → `ModuleNotFoundError`
  (idem `PyQt6.Qsci`).
- `import PyQt6.QtPdf, PyQt6.QtSvg, PyQt6.QtWebChannel` → sem erro.
- `Test-Path C:\Windows\System32\WindowsSandbox.exe` → `False`.
- `node --version` → `v25.9.0`.
- `java -version` → `1.8.0_503`.

**A.3 A catraca e a mudança em andamento** (§2.1, §2.5):
- `(git -C ..\ChessVisionOFF_Puro show HEAD:src/chess_diagram_ocr/qt/janela.py).Count` → **2.077**.
  Em Git Bash: `git show HEAD:… | wc -l` → 2.077. **Não** usar `Measure-Object -Line`, que conta
  só as linhas não vazias: 1.808.
- `(Get-Content ..\ChessVisionOFF_Puro\src\chess_diagram_ocr\qt\janela.py).Count` → 2.080 às 05h30 e
  2.077 às 06h15 de 2026-09-23 (a árvore mudou por outra sessão).
- `git -C ..\ChessVisionOFF_Puro status --short` mostra `painel_de_texto.py`, `text/rico.py`,
  `ui/texto_declarado.py` e `janela.py` modificados e os dois testes de digitação novos.
- **A página do pedido:** `pymupdf.open(PEDIDO)[54].get_text()` começa com `54\nChapter 1\n-
  Endgame Elements\n52.bxc7 &d7 53.&b5 &xc7 54.&xa5`. A camada de texto tem a notação cifrada
  (`&` = rei).

## Apêndice B — quem vê uma janela secundária hoje (A = `S\ui\audit\`)

| portão | mede | vê a janela do editor sem mudança? |
|---|---|---|
| `contraste` | pares declarados (QSS do app, paleta, `SIGNIFICADO`, suíte `PARES`) | só as cores da folha QSS |
| `teclado` | laço de Tab, nome e papel acessíveis | não (áreas da principal + `RECEITAS` de `QDialog`) |
| `texto_pintado` | títulos de grupo, cabeçalhos, aba selecionada | não |
| `bloqueio` | pulso de 4 ms durante operações listadas | não (lista fixa) |
| `quadros` | pan/zoom do `PainelDoPdf` | sim, se o painel for o `PainelDoPdf` |
| `comandos` | comando desenhado é vivo e cumpre | só o menu da principal |
| `minimo` | mínimo da janela principal | não |
| `vazio`, `capture`, `amostrario` | capturas das áreas | não |
| `percurso` | fluxos declarados | precisa de fluxos novos |
| `execucao`, `progresso` | threads e barras do tronco | só o código do tronco |


## Apêndice C — o sidecar de proveniência, versão 2 (esquema canônico)

**Arquivo e codificação.**
- O arquivo é `<livro>.proveniencia.jsonl`, ao lado do livro exportado, em UTF-8.
- Cada linha é um objeto JSON escrito por `json.dumps(obj, ensure_ascii=False, sort_keys=True,
  separators=(",", ":"))`, seguido de `\n`.
- **Todas as chaves listadas estão sempre presentes.** A nulidade vem do tipo, e nada é omitido
  por ser padrão.
- Os `float` saem na forma mais curta de ida e volta (`repr`), e nenhum é arredondado.
- `datetime` sai em ISO 8601 com o fuso. Enumeração, pelo `.value`. Tupla, como lista.

**Objetos das dez classes.** Cada um é `{"type": <etiqueta>, <campo>: <valor>, …}` com **todos**
os campos da dataclass, escrito pelo **serializador canônico do sidecar** (reflexão dos campos,
nunca os `as_dict()` que arredondam).
- **A etiqueta.** Seis das dez são nós registrados no IR (`@ir_node`; `registry.tag_for_class`) e
  usam a etiqueta do registro: `provenance`, `rect`, `diagram_source`, `fen_candidate`,
  `square_repair`, `recognition_result`. As quatro de decisão não são registradas e usam o nome
  da classe em `snake_case`.
- **Os tipos, fechados:** enumeração → `.value`; `datetime` → ISO 8601 com fuso; `Path` → texto;
  tupla → lista; `float` → `repr`, sem arredondar.
- **Campo tipado `Any` ou `dict`:** só valor nativo de JSON, recursivamente. Outro valor é **erro**
  (`ValorNaoSerializavel`, com classe, campo e tipo), nunca `str()` em silêncio.

| classe (módulo) | etiqueta | campos (introspecção de 2026-09-23; o cabeçalho leva a do momento) |
|---|---|---|
| `Provenance` (`core/model/provenance.py`) | `provenance` | kind, document_path, document_hash, page_index, block_index, rect, dpi, engine, engine_version, model_hash, confidence, band, extracted_at, verified_by_human, out_of_model, note |
| `Rect` (idem) | `rect` | x, y, width, height, unit |
| `DiagramSource` (`core/model/diagram.py`) | `diagram_source` | kind, path, content_hash, page_index, rect, dpi, rotation_degrees, image_hash, extracted_at, extractor, extractor_version |
| `FenCandidate` (idem) | `fen_candidate` | fen, score, legal |
| `SquareRepair` (idem) | `square_repair` | square, recognised, repaired, reason, confidence_before |
| `RecognitionResult` (idem) | `recognition_result` | fen, per_square_confidence, overall_confidence, orientation_confidence, side_to_move_confidence, side_to_move_source, path, model_name, model_version, model_hash, recognised_at, duration_ms, corners, alternatives (lista de `fen_candidate`), repairs (lista de `square_repair`), warnings |
| `ReviewItem` (`ocr/review.py`) | `review_item` | key, document, page_index, rect, kind, decision, reasons, text, engine, score, alternatives, low_confidence_words, disputed_tokens, legality, suggestion |
| `AuditEntry` (idem) | `audit_entry` | key, action, text, reviewer, at, seconds, note |
| `Decided` (idem) | `decided` | page_index, rect, action, text, reviewer, at |
| `DiagramDecision` (`ocr/diagram_decisions.py`) | `diagram_decision` | page_index, rect, fen, side, decided_at, reviewer, source, note |

**Os quatro tipos de linha** (a ordem: o cabeçalho; depois blocos, diagramas e partidas em ordem de
leitura):

| tipo | chaves obrigatórias (tipo) |
|---|---|
| `cabecalho` (1ª linha) | `tipo`="cabecalho"; `formato`="caissa.proveniencia"; `versao`=2; `livro` {`sha256` str, `nome` str}; `documento` {`caminho` str\|null, `hash` str\|null}; `alvo` str; `formato_do_livro` str; `paginas` [int base 0]; `perfil` objeto; `gerado_em` str; `gerador` {`programa`="caissa", `commit_da_suite` str}; `esquema` {etiqueta: [campo, …]} |
| `bloco` | `tipo`="bloco"; `id` str (`p<pág>-<n>`); `ir_id` str; `pagina0` int\|null; `folio` str\|null; `proveniencia` provenance; `duvidas` [{`ini` int, `fim` int, `texto` str, `proveniencia` provenance}]; `revisao` {`estado` "sem_duvida"\|"pendente"\|"aceita"\|"editada"\|"mantida_como_imagem", `decisoes` [review_item\|audit_entry\|decided]} |
| `diagrama` | `tipo`="diagrama"; `id` str (`p<pág>-d<n>`); `chave_v1` str (`p<pág0>:d<n>`); `ir_id` str; `fen` str; `orientacao` str; `estipulacao` str\|null; `verificado_por_pessoa` bool; `fonte` diagram_source\|null; `reconhecimento` recognition_result\|null; `proveniencia` provenance\|null; `decisoes` [diagram_decision] |
| `partida` | `tipo`="partida"; `id` str (`p<pág>-g<n>`); `chave_v1` str (`p<pág0>:g<n>`); `ir_id` str; `fen_inicial` str\|null; `lances` int; `proveniencia` provenance\|null |

Toda linha de `bloco`, `diagrama` e `partida` leva também `extras_v1`: um objeto vazio `{}` na
escrita nativa da v2, preenchido só na migração. Assim nenhuma chave é opcional.

Exemplo (uma linha de bloco, abreviada aqui só na largura):

```json
{"duvidas":[],"folio":"54","id":"p55-3","ir_id":"01J8…","pagina0":54,"proveniencia":{"band":"doubtful","block_index":3,"confidence":0.62,"document_hash":"9f2…","document_path":"C:/…/A Matter of Endgame Technique.pdf","dpi":300.0,"engine":"tesseract+glyph","engine_version":"5.5.0","extracted_at":"2026-09-23T06:40:00+00:00","kind":"ocr","model_hash":null,"note":"OCR para revisão","out_of_model":false,"page_index":54,"rect":{"height":88.0,"type":"rect","unit":"pt","width":301.5,"x":56.0,"y":212.0},"type":"provenance","verified_by_human":false},"extras_v1":{},"revisao":{"decisoes":[],"estado":"pendente"},"tipo":"bloco"}
```

**Mapeamento da versão 1 de hoje** (`export/provenance.py:41-153`, `VERSION = 1`). O leitor lê a
v1 e a converte assim:

| v1 | v2 |
|---|---|
| `{"kind":"header","version":1,…}` | `tipo`="cabecalho", `versao`=2 |
| `header.document_path`, `document_hash` | `documento.caminho`, `documento.hash`; `livro.sha256` = `document_hash`; `livro.nome` = nome do arquivo |
| `header.target`, `format`, `suite_commit`, `profile`, `pages`, `exported_at` | `alvo`, `formato_do_livro`, `gerador.commit_da_suite`, `perfil`, `paginas`, `gerado_em` |
| `diagram.key` = `p<k>:d<n>` | `chave_v1` igual; `id` = `p<k+1>-d<n>` (R2.7) |
| `diagram.id` | `ir_id` |
| `diagram.page_index`, `rect` (lista de 4, na ordem x, y, largura, altura — a das fixtures de hoje), `image_hash`, `content_hash`, `dpi` | `fonte` com esses campos (`rect` vira objeto `rect` com `unit`="pt"); os campos que a v1 não gravou saem `null` |
| `diagram.fen`, `orientation`, `verified_by_human`, `stipulation` | `fen`, `orientacao`, `verificado_por_pessoa`, `estipulacao` |
| `diagram.recognition.{fen, path, model_name, model_version, model_hash, overall_confidence, side_to_move_source, per_square_confidence, warnings}` | `reconhecimento` com os mesmos nomes; os que a v1 não gravou, `null`; o `per_square_confidence` da v1 vem arredondado a 4 casas e fica como veio |
| `diagram.recognition.repairs[]`, `alternatives[]` | `reconhecimento.repairs` (`square_repair`), `reconhecimento.alternatives` (`fen_candidate`) |
| `diagram.provenance` e `game.provenance` (10 campos) | `proveniencia` (os 16 campos; os seis que a v1 não gravou, `null`/padrão) |
| `game.key` = `p<k>:g<n>`, `id`, `page_index`, `initial_fen`, `moves` | `chave_v1`; `id` = `p<k+1>-g<n>`; `ir_id`; `proveniencia.page_index`; `fen_inicial`; `lances` |
| `rect` da v1 como **lista** de 4 (x, y, largura, altura) **ou** como objeto {x, y, width, height, unit} (a forma que o conserto do item 1 do H4 pode gravar) | `rect` (objeto `rect`); as duas formas são aceitas e testadas |
| chave da v1 que esta tabela não nomeia | `extras_v1` {chave: valor como lido} na mesma linha — nada se perde |

**Os dois campos que mudam a cada execução.** `gerado_em` e `gerador.commit_da_suite` vêm de um
**relógio** e de um **commit injetáveis**: o escritor recebe `agora()` e `commit()` (os padrões
leem o relógio e o `git rev-parse` do produto).
- As fixtures douradas são escritas com valores **fixos**: `gerado_em` =
  `"2026-01-01T00:00:00+00:00"`, `commit_da_suite` = `"fixture"`.
- O portão chama o escritor com os mesmos valores injetados. A igualdade byte a byte fica
  **inteira**, sem campo ignorado.
- Um teste separado de **invariantes** cobre os valores reais: `gerado_em` é ISO 8601 com fuso, a
  menos de 5 s do relógio do teste, e `commit_da_suite` é o que `git rev-parse --short=12 HEAD`
  devolve (ou vazio fora de um checkout).

**Fixtures douradas, escritas por quem não constrói** (o crítico), **no H3**, antes de qualquer
implementação, e congeladas por SHA-256 no relatório do H3:
- `tests/fixtures/editor/sidecar/v2_completo.jsonl`: a saída esperada de um `Document` de fixture
  que preenche as dez classes com valores fora do padrão, com listas não vazias. A saída do
  escritor é **igual byte a byte**.
- `v1_de_hoje.jsonl`, produzido pelo exportador atual, e `v1_migrado_esperado.jsonl`: a migração é
  igual byte a byte ao esperado.

## Apêndice D — o contrato do arnês de medição Chromium (foco, 2.4.12/2.4.13)

O arnês é `benchmarks/editor_chromium_medicao.py`, entregue pelo H1, e roda no ambiente de medição.

- **Página.** Viewport de 1280 × 800 px CSS, `zoomFactor` 1,0, o JavaScript da página desligado.
  O script de medição roda no *ApplicationWorld*. O ponteiro fica fora da janela (sem `:hover`).
  Uma folha de medição injetada só no arnês zera `animation`, `transition` e `caret-color`.
- **Escala.** A `window.devicePixelRatio` (DPR) é lida e registrada. A captura (`QWebEngineView.grab()`)
  tem o tamanho do viewport × DPR. Um retângulo CSS (x, y, l, a) cobre os pixels de
  `floor(x·DPR)` a `ceil((x+l)·DPR)`. Área em px² CSS = pixels ÷ DPR².
- **Serialização.** Cada consulta devolve JSON: retângulos como
  `[{"x","y","width","height"}]` em px CSS relativos ao viewport, depois de
  `scrollIntoView({block: "center", inline: "nearest"})`. Um link mais alto que o viewport é medido
  em faixas de 800 px CSS, rolando por faixa.
- **Foco.** `focar_por_tab(n)` manda `Tab` de verdade (`QTest.keyClick`). O arnês espera
  `document.activeElement` ser o alvo (consulta a cada 16 ms, até 500 ms) e mais dois
  `requestAnimationFrame` antes de capturar. A captura **não focada** do mesmo link, com a mesma
  rolagem, é feita com o foco num sentinela `tabindex=-1` fora dele.
- **A região e o limiar.** A diferença é medida na região = união dos retângulos do link inflados
  por `outline-width` + max(`outline-offset`, 0) + 4 px CSS.
  - Um pixel «muda» quando a maior diferença entre os canais RGB é ≥ 16 (de 255).
  - Pixel mudado **fora** da região invalida a medida (a mudança não é só do indicador), e o
    relatório diz.
- **O P.** P = soma de 2 × (largura + altura) dos retângulos **não focados**.
- **2.4.12 (nada encoberto).** Um indicador de foco é **pintura** (`outline`, `box-shadow`, borda,
  pseudo-elemento do próprio link), não elemento do DOM. Por isso o teste tem duas partes:
  - **(a) Dentro das caixas do link:** em todo centro de pixel CSS (x + 0,5, y + 0,5) da união dos
    `getClientRects()`, recortada ao viewport, `document.elementsFromPoint(x, y)[0]` é o link ou
    um descendente.
  - **(b) O indicador, por máscara.** A **renderização isolada** repete as duas capturas (não
    focada e focada) com tudo o que pode cobrir o indicador neutralizado, sem mudar o leiaute:
    - todo elemento que não é o link, um ancestral ou um descendente dele fica em
      `visibility: hidden`, e os pseudo-elementos dele somem junto;
    - nos **ancestrais** — `html` e `body` inclusive, marcados pelo arnês —, os `::before` e
      `::after` ficam em `visibility: hidden`, e a pintura que pode passar por cima (`outline`,
      `box-shadow`) fica em `none`;
    - o fundo dos ancestrais fica, porque é pintado por baixo e é igual nas duas capturas.
    - **A neutralização prova que venceu.** Ela vai por estilo em linha com `!important`
      (`style.setProperty(…, "important")`) nos elementos, e por uma folha injetada **por último**,
      com `!important` e seletor de especificidade alta, nos pseudo-elementos. Depois, o arnês lê o
      `getComputedStyle` de cada elemento e pseudo-elemento neutralizado: se uma regra do autor
      venceu, a medida é **inválida**, e o relatório diz qual propriedade e qual elemento.
    - M_iso = os pixels que mudam na renderização isolada: o indicador inteiro, desenhado.
    - M_real = os pixels que mudam na renderização normal.
    - Pixel **encoberto** = pixel de M_iso que não está em M_real: o indicador devia aparecer ali
      e algo o cobre.
    - A meta é **0** encobertos, e o relatório diz por link quantos e onde.
- **2.4.13 (área e contraste)**, medidos em **M_real** (o que a pessoa vê): a área ≥ P × 2 px²
  CSS, e o contraste entre focado e não focado ≥ 3:1 numa área ≥ P × 2.
- **Autoteste** (portão do H1), com resultado esperado conhecido:
  - (1) link com `outline: 2px solid` e nada por cima → área a ±1 % da esperada **e 0 encobertos**
    (a pintura do contorno fora da caixa não é acusada);
  - (2) link com `box-shadow: 0 0 0 3px` → idem;
  - (3) uma faixa irmã de 1 px, `position: absolute`, sobre o contorno → encobertos > 0;
  - (4) link em duas linhas → dois retângulos, os dois medidos;
  - (5) `::after` de **outro** elemento sobre o contorno → encobertos > 0;
  - (6) `body::after` (ou `html::before`) absoluto, com `z-index`, cobrindo uma faixa de um
    `box-shadow: 0 0 0 4px` → encobertos > 0: o pseudo-elemento de **ancestral** é acusado;
  - (7) com `QT_SCALE_FACTOR=1.5` → as áreas em px² CSS iguais às de DPR 1 a ±2 %.
