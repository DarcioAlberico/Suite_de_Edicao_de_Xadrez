# Relatório do construtor — Editor HTML/CSS

> O relatório que o roadmap (`docs/EDITOR_HTML_CSS_ROADMAP.md`) pede: uma seção por passo, todo
> número com o comando ao lado. Os portões rodam pelo executor único
> (`& $PY benchmarks\editor_portoes.py --passo <Hn> --saida benchmarks\reports\editor\<hn>`), que
> grava o `portao.json` com o HEAD dos dois repositórios; as saídas ficam em
> `benchmarks/reports/editor/` (fora do git). Construtor: Claude (sessão «Implementações
> pendentes»), 2026-09-24 a 2026-09-30.

---

## H0 — O executor de portões e os leitores medidos

**Estado:** o executor, o ambiente e o instrumento estão prontos e testados; **a medição completa
(3 execuções de ~1 h e as 6 sabotagens) ainda não rodou**: outra sessão mediu na mesma máquina o
dia todo, e medir junto contaminaria os tempos das duas.

- **O executor** (`benchmarks/editor_portoes.py`): `tests/unit/editor/test_portoes.py`, 46 casos,
  inclusive os passos falsos «instrumento ausente», «sabotagem inócua» e «passo bom», e as
  publicações adulteradas da auditoria (ciclos 19–21 do crítico).
  `& $PY -m pytest tests/unit/editor/test_portoes.py -q -p no:cacheprovider`
- **O denominador da verdade** (o manifesto `dev` + `calib`, hash `f019591babf2941e`, 237 regiões
  de PDF): digitalizado 653 lances, 464 com figurina, 199 regiões; nativo **198 lances, 0 com
  figurina**, 38 regiões — a razão da mutação do §10 do roadmap.
  `& $PY -c "import sys; sys.path[:0]=['benchmarks','src']; import editor_portoes as P; from caissa.ocr.golden import load_manifest; print(P._contar_o_manifesto(load_manifest(P.manifesto_do_executor()))[1])"`
- **A medição:** pendente — `& $PY benchmarks\editor_portoes.py --passo H0 --saida benchmarks\reports\editor\h0`.

## H1 — Motores de pré-visualização, medidos

**Estado:** em curso. Prontos e medidos: o arnês de medição Chromium (tarefa 5, `cc20e00`), a
matriz de CSS (tarefa 1) e o livro hostil (tarefa 4). Pendentes: a latência e as posições (tarefa
2: os capítulos do `PEDIDO` p. 50–60 saem do mesmo IR real do H5, que espera a máquina livre), a
sonda congelada (tarefa 3b: uma construção PyInstaller) e a máquina limpa (3c: o Windows Sandbox
ou uma VM, do usuário), a instalação atômica e os tamanhos (3d, 3e) e a entrada do executor.

- **O ambiente de medição:** o venv de rascunho `C:\Python-Chess2\_h1_webengine\.venv` (Python
  3.11, `PyQt6-WebEngine` 6.11.0 e `PyQt6-WebEngine-Qt6` 6.11.2, o download consentido em
  2026-09-24), fora do repositório; o produto não o leva.
- **O arnês** (`benchmarks/editor_chromium_medicao.py`): o autoteste das sete fixtures do Apêndice
  D passa (7/7), e a sabotagem `pseudo_do_body` reprova só a (6). **Achado:** fora da tela, o Qt
  não dá ao Chromium as famílias genéricas — `serif`, `sans-serif` e `monospace` caíam todas na
  mesma fonte; o arnês agora as diz (as do Chrome no Windows: Times New Roman, Arial, Consolas).
  `& $MEDICAO benchmarks\editor_chromium_medicao.py --autoteste --saida <pasta>`
- **A matriz de CSS** (`benchmarks/editor_motores.py --matriz`, ~2 min): as declarações dos 9 temas
  do CB, do `BASE_CSS` e do `CHESS_CSS` — **216 casos** (214 pares e os 2 controles), **58
  propriedades**; os controles passam (`color: #c00` desenha nos dois motores, `color: #000` em
  nenhum). Com o Chromium como referência: **21 propriedades desenham nos dois**, 9 só em parte no
  MuPDF, **10 o MuPDF não desenha**, 17 não têm efeito visível na página de prova (a paginação,
  sobretudo) e **1 trava o MuPDF**. O que o MuPDF não desenha — a lista para o validador (H10):
  - **`var()`**: nenhuma variável CSS resolve — toda cor, borda e medida do `BASE_CSS` por
    variável cai no padrão;
  - **as fontes do sistema** (Georgia, Palatino Linotype, DejaVu Sans…): o MuPDF só tem as dele, e
    a família nomeada cai em silêncio na genérica;
  - `border-radius`, `opacity`, `float`, `display: inline-block`, `font-variant: small-caps`,
    `letter-spacing`, `height`, `vertical-align: middle`, e o `::first-letter` (a capitular: o
    corpo, a entrelinha e o recuo dela).
  - **O laço:** `page-break-before: always` no primeiro elemento faz o `Story.place` do MuPDF
    paginar sem fim (o teste `test_o_mupdf_entra_em_laco_com_a_quebra_antes_do_primeiro_elemento`
    o prova); a prévia pelo MuPDF (H13) precisa de teto de páginas.

  `& $PY benchmarks\editor_motores.py --matriz --saida <pasta>` (`matriz_css.json`)
- **O livro hostil** (`tests/fixtures/editor/hostil/`, uma página por vetor; os endereços de fora
  são um servidor em `127.0.0.1` que só conta o que chega: nada sai da máquina):
  **Chromium: 0 requisições, 0 scripts, 0 pedidos de fora do livro, 0 navegações para fora**
  (5 recusados pelas guardas); **MuPDF: 0 requisições, a sentinela de fora do livro não lida, sem
  motor de script** (o controle: a imagem de dentro desenha); **o controle com o JavaScript
  ligado** roda 4 scripts (o `<script>`, o `onerror`, o link `javascript:` e o do SVG no texto).
  Sabotagens: `sem_interceptador` reprova (3 arquivos de fora passam); `sem_guarda_de_rede` (sem
  as três camadas) reprova com 8 requisições no servidor. **Achado para o H14:** o Chromium tem
  três camadas — o `LocalContentCanAccessRemoteUrls` desligado barra o endereço de rede antes do
  interceptador; o interceptador barra o arquivo de fora da pasta; e **faltava a guarda de
  navegação**: o `<meta http-equiv="refresh">` levava a prévia para fora do livro (a requisição
  barrada, mas a página ia embora). A R4.1 já pede a navegação recusada; o que faltava era no
  arnês, que agora a recusa no `acceptNavigationRequest`, e o componente do H14 tem de fazer o
  mesmo.
  `& $PY benchmarks\editor_motores.py --hostil [--sabotar sem_interceptador|sem_guarda_de_rede] --saida <pasta>`
- **Os testes:** `tests/unit/editor/test_motores.py` (11: a extração dos casos, a genérica da
  `font-family`, o veredito, os pixels, o laço e o `var()` do MuPDF, o livro hostil).
- **Os tamanhos do componente (tarefa 3e), medidos nas rodas 6.11 do ambiente de medição** — o
  orçamento da spec §5.5 é download ≤ 150 MB e instalado ≤ 300 MB:
  - **download: 132,6 MB** (as duas rodas, `PyQt6-WebEngine-Qt6` 6.11.2 e `PyQt6-WebEngine`
    6.11.0, achadas no cache HTTP do pip pelo `METADATA` de dentro do zip) — dentro;
  - **instalado inteiro: 358,6 MB** (o `Qt6WebEngineCore.dll` sozinho tem 203,4 MB) — **fora**; a
    spec extrapolava 207 MB de um PySide6;
  - **aparado: 222,5 MB** — sem os `.pak` de depuração e das ferramentas do desenvolvedor
    (90,1 MB), sem as traduções além de `pt-BR` e `en-US` (44,6 MB), sem o Qt Quick e o QML
    (1,1 MB) e sem os arquivos de desenvolvimento (0,3 MB) — dentro, **se** a sonda congelada
    provar que ele desenha (mais as DLL do Qt base que o WebEngine usa e o pacote não leva).
  `& $PY benchmarks\editor_motores.py --tamanhos --saida <pasta>` (`tamanhos.json`)
- **A sonda congelada e a instalação atômica (tarefas 3b e 3d):** `packaging/sonda_webengine.py` e
  `packaging/sonda_webengine.spec` — o pacote com o PyQt6 do `Caissa.exe` (QtCore, QtGui,
  QtWidgets) e sem nada do WebEngine; o componente em `runtime\webengine\`, ligado pelo
  `PyQt6.__path__`, o `os.add_dll_directory`, o `PATH` e as três variáveis do QtWebEngine; a sonda
  desenha a fixture num PNG e grava as DLL carregadas, as dela e as do `QtWebEngineProcess`, e sem
  o componente cai no MuPDF. **O componente que se instala** — as rodas aparadas, mais o Qt base
  que o WebEngine importa e o pacote não leva (10 DLL pelo PE, 16,4 MB: o Qt Quick, o QML, o
  WebChannel, o Positioning, o OpenGL, o PrintSupport; e os módulos QtNetwork, QtPrintSupport e
  QtWebChannel) — tem **42 arquivos, 240,0 MB**: dentro dos 300 MB. A instalação copia para
  `runtime\webengine.parcial\` e só no fim renomeia; a que cai no meio (`--abortar-apos N`) apaga
  a parcial. Testes: `tests/unit/test_sonda_webengine.py` (5, com rodas de mentira: o corte, a
  instalação atômica, a queda, a remoção, a ligação num processo à parte). **Pendentes:** a
  construção pelo PyInstaller e a rodada nesta máquina (a máquina livre) e a **máquina limpa**
  (o Windows Sandbox ou uma VM sem Python, do usuário).

## H2 — O editor de código nativo aguenta, com tudo ligado?

**Estado:** o léxico, o protótipo e os dois instrumentos prontos; **a sonda UIA passou**; o arnês
de desempenho (`editor_codigo.py`, 3×) espera a máquina livre (ele mede bloqueios de 16 ms).

- **Casos dourados com tudo ligado:** `tests/unit/ui/test_editor_de_codigo.py`, 72 casos, e
  `tests/unit/editor/test_lexico.py`, 71: 143 passam.
  `. .\benchmarks\editor_ambiente.ps1; Enter-AmbienteDosTestesQt; & $PY -m pytest tests/unit/ui/test_editor_de_codigo.py tests/unit/editor/test_lexico.py -q -p no:cacheprovider`
- **UIA:** o `TextPattern` do editor lido pela UI Automation do Windows, numa janela real fora da
  tela, em 50 posições sorteadas (o caractere, a linha e, numa em cinco, a seleção): **50/50 nas
  3 execuções**. A sabotagem `uia_mudo` (um `QWidget` que só pinta o texto): **0/50**, «nenhum
  elemento com TextPattern».
  `& $MED benchmarks\editor_uia.py --saida <pasta>` e `& $MED benchmarks\editor_uia.py --sabotar uia_mudo --saida <pasta>`
  (`$MED` = `.venv-medicao`, Python 3.11 com `pywinauto` 0.6.9, `comtypes` 1.4.17 e `pywin32`
  312, os downloads consentidos em 2026-09-24; o produto não o leva).
- **O Narrador confirmado por uma pessoa:** pendente (é do usuário).
- **Desempenho:** pendente — `& $PY benchmarks\editor_portoes.py --passo H2 --saida benchmarks\reports\editor\h2`.

## H3 — O contrato de marcação e a política de CSS, no papel e em fixtures

**Estado:** o contrato escrito (`docs/MARKUP_CAISSA.md`), as fixtures e o instrumento prontos.

- **Cobertura:** as 14 linhas da S4 com fixture (100 %), mais 2 combinações, as 3 fixtures das
  extensões do H5 (§12 do contrato, pelo escritor legível: `--regerar-extensoes`) e a legada; o
  §11 do contrato nomeia as mesmas.
- **`CB validate`** (`..\Sigil-master\src\Resource_Files\python3lib\sigil_chess\validate.py`, com o
  `python-chess` 1.11.2 do `.venv`): **0 erro, 0 aviso em 19 fixtures** (as 14, as 2 combinações
  e as 3 extensões; em 2026-09-30, no `d2f7531`). Ele acusa uma FEN de lance adulterada, um
  diagrama que não mostra a posição do lance acima dele e a negativa sem `data-fen` (a sabotagem
  `sem_fen`). Desde o H5 o instrumento conta também o que o CB confunde sem acusar (MARKUP
  §10): o elemento que uma expressão do `validate.py` casa sem ter a classe dela, e o `cb-move`
  sem `data-fen`, que ele pula. A conta achou o `cb-move-context` da v1 do contrato, que passou a
  `cb-diagram-context` na v2 (M-H5-2); agora, **0 e 0**. A sabotagem nova `confundida` (a
  negativa com a classe da v1 e um `cb-move` sem `data-fen`) dá **0 erro no CB** e reprova pela
  conta: 1 marcação confundida e 1 lance pulado.
  `& $PY benchmarks\editor_contrato.py --saida <pasta>` e `--sabotar confundida`
- **A legada:** `legado_xhtml_builder.xhtml`, saída do exportador HTML de hoje (perfil de máquina,
  `embed_ir=False`), lida pelo `read_html_text` com o título, o parágrafo, o diagrama e a partida.
  `& $PY benchmarks\editor_contrato.py --regerar-legada`
- **O mapa de estilo:** 24 fixtures positivas (as 19 propriedades do mapa, cada uma com dois
  valores, mais a cascata, as variáveis e as classes `cb-*`) e 24 negativas (uma construção fora
  do mapa por arquivo), cada uma com o resultado esperado declarado na forma do §9 do contrato.
- **As fixtures douradas do sidecar** (spec Apêndice C), escritas pelo **crítico** (Codex,
  2026-09-24, `-s workspace-write` restrito a `tests/fixtures/editor/sidecar/`) antes de qualquer
  escritor v2, assinadas no `LEIAME.md` dele, com as escolhas onde o apêndice deixa margem. O
  gerador dele (`gerar_esperado.py`) é independente: reflexão dos campos, sem os `as_dict()`; a
  `v1_de_hoje.jsonl` sai do `write_sidecar` de hoje. Duas execuções, bytes iguais. **Congeladas
  por SHA-256** (não mudam sem mutação no §10 do roadmap):
  - `v2_completo.jsonl` `76986fa5236626fe85af161ba48394aa14cd69ff8c45917ac933ffa6ea84dc32`
  - `v1_de_hoje.jsonl` `832646aa9e422d3116a830aac980add3b8e415fa948b748423c821089657e1e1`
  - `v1_migrado_esperado.jsonl` `a9d8c21bc4b07979def510d81459b22b69fa11ba806ad169a852ae83061ac24d`
  - (a entrada) `entrada.py` `61e1e7d662db4718ff5547808ae03203224a2b18b02f6fba717fbcbcde01ca4c`

  `$env:PYTHONPATH='src'; & $PY tests\fixtures\editor\sidecar\gerar_esperado.py` (regrava as três;
  o hash tem de sair igual).
- **Achado para o H24:** o escritor v1 do sidecar de hoje grava `\r\n` no Windows (o
  `v1_de_hoje.jsonl` tem CRLF, e o `.gitattributes` o guarda com `-text` para o hash não mudar);
  o escritor v2 tem de gravar `\n` explícito, como o Apêndice C manda.

## H4 — As dívidas da exportação que o editor poria na tela

**Estado:** os itens 3–9 da spec §2.7 corrigidos no produto e o contador pronto e testado
(`8a40016`); **o portão (os três EPUBs de antes e de depois, com o EPUBCheck) ainda não rodou**:
ele exporta três livros e espera a máquina livre.

- **Os testes:** `tests/unit/export/test_dividas_da_exportacao.py` (13) e
  `tests/unit/editor/test_dividas.py` (4).
  `& $PY -m pytest tests/unit/export/test_dividas_da_exportacao.py tests/unit/editor/test_dividas.py -q -p no:cacheprovider`
- **O instrumento** (`benchmarks/editor_dividas.py`) conta os dez sintomas no livro exportado,
  sem olhar o código; os EPUBs de antes saem de uma árvore destacada no commit anterior ao passo
  (`a6414f3`):
  `& $PY benchmarks\editor_dividas.py --gerar --codigo C:\Python-Chess2\_h4_antes\src --saida benchmarks\reports\editor\h4_antes`
- **O portão:** pendente — `& $PY benchmarks\editor_portoes.py --passo H4 --saida benchmarks\reports\editor\h4`.
- **Achado fora do passo:** `tests/unit/ingest/test_corpus.py::test_nunn_ocr_layer_keeps_the_paragraphs_whole`
  falha também no `9eb401c`, anterior ao programa; não é deste roadmap.

## H5 — O perfil legível, os atributos preservados, o CSS como recurso e o mapa de estilo

**Estado:** implementado em três commits (`02a372f`, `17b780b`, `d2f7531`) e na resposta ao
crítico (`adc9df2`, `1b24e25` e a desta rodada); o **H5, ciclo 1** do Codex reprovou com 3
bloqueantes, respondidos pelas mutações M-H5-1 (roadmap §10, spec 1.19) e M-H5-2 (o contrato v2);
o **ciclo 2 aprovou a M-H5-1** e reprovou só a governança da M-H5-2 — o registro no `DECISIONS.md`
do CB, feito como **D-004** (`bf56a19d3` do Sigil-master); **o ciclo 3 APROVOU** (a M-H5-2
aprovada, a M-H5-1 mantida, nenhum bloqueante); os testes e a
rodada leve do arnês passam; **o portão completo** (o IR real das páginas do portão, o corpus de 10
mil nós, 3 execuções, as 7 sabotagens e o EPUBCheck) **espera a máquina livre**.

- **A decisão da ida.** A primeira sondagem da ida (IR → XHTML legível → IR, `semantic_diff`, no
  corpus sintético que sorteia todo campo do IR) deu **3351 diferenças em 2 mil nós**: o perfil
  só escrevia o que as fixtures do H3 pediam. Todo campo passou a ir por um de quatro caminhos: o
  HTML; o contrato `cb-*` com as extensões `data-*` (o §12 do contrato); o mapa da proveniência
  (o `proveniencia.json`, formato 2); ou N1–N4, que `caissa.export.legivel.forma_normal` aplica ao
  IR, contadas por nó e campo. A leitura em IR de N1–N4 é a mutação M-H5-1 (a S4 da spec 1.19 e o
  §8 do contrato); a lista continua quatro.
- **O ciclo 1 do crítico** (2026-09-30, REPROVADO, 3 bloqueantes; transcrito em
  `EDITOR_HTML_CSS_CRITICAS.md`) e a resposta:
  1. a leitura de N2–N4 ampliava a lista fechada sem a mutação → a M-H5-1 no roadmap §10 e a spec
     1.19 (S2, S3, S4, §9). A N2 encolheu para exatamente o que o perfil de máquina só escreve
     pelas classes geradas: o estilo direto do diagrama (`data-style`) e as `RunProps` das opções
     da partida (`data-move-props`, `data-comment-props`, `data-variation-props`) passaram a ir no
     XHTML;
  2. a N3 perdia a proveniência dos nós sem `id` → o dado da máquina de todo nó sem `id` vai ao
     `proveniencia.json` com o lugar dele (o `id` do bloco dono, o caminho e, dentro do
     parágrafo, o intervalo e o SHA-256 do texto); o `conferir_mapa` prova que todo registro acha
     o lugar, e o portão exige registros = N3. O JSON ganhou o fólio, as dúvidas, a revisão e as
     decisões da S2 (vazias até o H7);
  3. o lance que não se joga ia num `cb-move` sem `data-fen` → vai num `span.cb-literal-move`, e o
     `cb-move` fica o do CB. O primeiro nome, `cb-move-literal`, ainda casava com a expressão
     `\bcb-move\b` com que o `validate.py` do CB acha o lance (o hífen é fronteira de palavra): o
     CB o pularia como um lance sem `data-fen`, e o «0 erro» não diria nada. O construtor achou
     isso antes do ciclo 2, trocou o nome e fez os dois portões contarem o que o CB confunde
     sem acusar (o elemento que uma expressão dele casa sem ter a classe dela, e o `cb-move` sem
     `data-fen`: têm de ser 0), no H5 em todos os arquivos da volta, o sintético também.
- **A ida no arnês** (a sonda do ciclo 1 virou a exigência da ida do próprio portão): 0 diferença
  em três sementes de 2 mil nós, com o mapa passando pelo JSON — semente 7: N1 14, N2 1349, N3
  117, N4 3; semente 11: 9, 1416, 132, 2; semente 13: 8, 1215, 122, 2 — e a N3 guardada no mapa é
  117, 132 e 122 registros, todos no lugar.
  `& $PY benchmarks\editor_ida_e_volta.py --semente 7 --nos 2000 --sem-epubcheck --saida <pasta>`
- **A conferência do leitor** (R2.3): cada elemento lido é reescrito e comparado pelo `canon`
  (sem os `id` de página, com o derivado do §6.1 recalculado); o que não volta igual fica bruto
  inteiro, e o `Capitulo.brutos` o registra. Sem o registro a volta escondia o defeito do
  escritor (as sabotagens `perde_fen` e `perde_classe` passavam por ela); com ele, o portão exige
  nenhum bruto nas fixtures e nos arquivos da ida, e só os do `esperado.json` nas 20 edições à
  mão (3: o itálico num comentário de partida, o `title` na imagem de um diagrama, o lance
  digitado sem o `cb-piece`).
- **O que a sondagem, a conferência e as edições acharam e ficou corrigido:** o MathML escrito
  pela pessoa virava o texto do `latex`; a fórmula de dentro do parágrafo lida como bloco numa
  célula; o link dentro de link conferido fora do contexto; o lance na prosa sem posição ganhava
  `data-ply="0"`; o `canon` colapsava o espaço sem quebra e os finos (agora só o espaço do XML);
  o bruto com `svg:`/`m:` saía sem o prefixo declarado; o `data-uci` era inventado para o lance
  do PDF (o importador deixa `uci=None`).
- **A rodada leve do arnês** (`--nos 2000`, sementes 7, 11 e 13, sem o IR real e sem EPUBCheck,
  na resposta ao ciclo 1): volta **40/40** arquivos (19 fixtures, 1 da ida, 20 edições) com 0
  bruto fora do esperado; CSS byte a byte **49/49** folhas; mapa de estilo **24/24** positivas e
  **24/24** negativas; CB **0 erro** em 39 arquivos. Cada sabotagem (semente 7) reprova na linha
  declarada: `perde_fen` (ida, 49 diferenças; volta, 6 brutos fora do esperado), `perde_classe`
  (ida, 647; volta, 7 brutos), `perde_atributo` (ida, 116; volta, 26/40), `nula` (ida, 2012, e os
  162 registros do mapa fora do lugar; volta, 1/40), `engole_desconhecido` (volta, 24/40),
  `css_silencioso` (mapa, 0/24 negativas) e a nova `lance_sem_fen` (a forma do ciclo 1 de volta:
  a ida sem diferença, a volta 40/40 e o validate do CB com 0 erro — e o portão reprova pelos
  **152 lances que o CB pularia**).
  `& $PY benchmarks\editor_ida_e_volta.py --nos 2000 --semente 7 --sem-epubcheck [--sabotar <nome>] --saida <pasta>`
- **Os testes:** `test_legivel.py` (27), `test_legivel_ida.py` (16), `test_legivel_conferencia.py`
  (28), `test_leitura.py` (5), `test_mapa_sem_id.py` (4), `test_mapa_de_estilo.py` (52),
  `test_paginas.py` (6), `test_esquema_v2.py` (7) e a tabela do executor.
- **Desvios declarados** (os dois primeiros, agora na M-H5-1): o perfil legível mora em
  `src/caissa/export/legivel.py`, e não num `XhtmlBuilder(perfil=)` (o escritor de máquina e o
  legível não partilham a forma; o H24 liga o exportador ao legível); o `cssselect2` passa ao H19,
  quando o inspetor de CSS o usar — nenhum código o importa; o `tinycss2` entrou no `pyproject`
  e no `.venv-pack`, e o inventário de licenças sai na próxima construção do pacote
  (`packaging/coletar_licencas.py` lê o pacote construído); o gerador do corpus sintético deixou de pôr o `lang` preservado ao lado da língua
  modelada num `Text` (o leitor nunca monta os dois); o arquivo com o nome derivado da imagem do
  diagrama desatualizado não fecha a volta por construção (o escritor refaz o derivado), e a
  edição #08 usa o nome novo, como o comando do diagrama (H22) fará.
- **O portão:** pendente —
  `& $PY benchmarks\editor_ida_e_volta.py --gerar-ir-real benchmarks\reports\editor\h5_ir_real` e
  `& $PY benchmarks\editor_portoes.py --passo H5 --saida benchmarks\reports\editor\h5`.

## H6 — O projeto em disco

**Estado:** implementado (`f9f0d4f`): o projeto, o diário, as versões, a trava, a gravação
atômica, o registro de livros e as migrações, sem Qt; **o portão** (3 execuções da recuperação e
as 4 sabotagens) **espera a máquina livre**.

- **Os testes:** `tests/unit/editor/test_projeto.py` (18), mais as pastas guardadas do pacote e a
  regra de arquitetura (o `editor/` sem toolkit).
- **O portão:** pendente — `& $PY benchmarks\editor_portoes.py --passo H6 --saida benchmarks\reports\editor\h6`.

## H10 — A validação em camadas, com linha e coluna

**Estado:** implementado — o pacote `src/caissa/editor/validacao/` (sem Qt, fora da thread da
janela), as fixtures de defeito, o arnês e a entrada `PASSOS["H10"]` do executor; os testes
passam; **o portão** espera o IR real do H5 (o conjunto limpo) e a máquina livre (o tempo).

- **As camadas e as regras** — 49 regras, cada uma com código, severidade, local
  (`arquivo:linha:coluna`, de 1, pela árvore do `expat`, que conta caracteres), o que fazer e,
  quando seguro, conserto (o `lang` da raiz, o `<abbr title>` da abreviatura):
  - **XML** (`xml.py`): bem formado; e a leitura patológica da R4.3 — o arquivo além de 8 MB, o
    aninhamento além de 256, o `DOCTYPE` com entidade (a leitura para na declaração: nada se
    expande, a externa nunca se resolve);
  - **segurança** (`seguranca.py`, R4.2 e R4.3): o `<script>`, o `on…`, o `javascript:`, o
    `<iframe>`/`<object>`/`<embed>`, o recurso remoto, o `@import` remoto, o caminho de recurso
    fora do projeto (acima da raiz, absoluto, `file:`, o link simbólico para fora);
  - **contrato** (`contrato.py`, absorvido do `validate.py` do CB com a «Origem:»): o diagrama sem
    `data-fen`, a FEN que não se lê, o `data-stm` incoerente, o `img.cb-svg` de outra posição, a
    imagem que falta, o `cb-move` sem `data-fen` (o CB o pula), a classe que o CB confunde e a
    `cb-*` fora do contrato;
  - **xadrez** (`xadrez.py`, do CB): o lance ilegal, a `data-fen` que não é a do lance, o
    diagrama que não mostra o lance de cima (avisa: o livro pode ter razão), a notação de duas
    línguas, a figurina fora da fonte ativa;
  - **CSS** (`css.py`): a sintaxe, a propriedade desconhecida, o que o MuPDF não desenha (a matriz
    do H1), o que o DOCX não leva (o mapa do H5) e o **contraste AAA 1.4.6 medido na página do
    MuPDF** (`previa.paginar`, com as variáveis da `:root` resolvidas e o teto de páginas do laço
    do H1): cada trecho, com a cor calculada, contra o fundo local (o retângulo preenchido embaixo
    dele), 7:1 no normal e 4,5:1 no grande (o MuPDF conta o px do CSS: grande é ≥ 24 px, ou
    ≥ 18,66 px em negrito);
  - **acessibilidade** (`acessibilidade.py`): o `lang`, os títulos, o `alt` (e o que afirma o não
    lido, pelo mapa), a `page-list` (duplicado, lacuna), a imagem de texto, a mídia, o
    interativo, o `meta refresh`, a animação (CSS e GIF/APNG), o `fixed`/`sticky`, o foco
    apagado, o link sem propósito, a seção sem papel, o símbolo fora do glossário, a abreviatura
    sem `<abbr>`, o dado da máquina no livro;
  - **OCR** (`ocr.py`): cada dúvida pendente do `proveniencia.json`, no bloco dela;
  - **EPUBCheck** (`epubcheck.py`, e o `--json` em `export/epubcheck.py`): cada mensagem com o
    local; a que o EPUBCheck dá sem local fica `0:0`, e não finge um `1:1`.
- **Os defeitos** (`tests/fixtures/editor/defeitos/`): **50/50** com o código e a linha:coluna
  certos — um arquivo por regra (49) e o de 8 MB que o portão monta —, cada um com o defeito dele e
  nenhum outro; o local esperado sai de um marcador no texto, pela definição da regra, e não do
  validador. Toda regra registrada tem o seu.
- **O limpo:** **0 problema que bloqueia ou avisa** nas 16 fixtures do contrato (as 14 linhas da S4
  e as 2 combinações); os capítulos legíveis do IR real esperam o `--gerar-ir-real` do H5.
- **O EPUBCheck** (4.2.6, Java 8): o EPUB mínimo limpo dá 0 erro; com a etiqueta errada e com a
  imagem que falta injetadas, **2/2 erros acusados na linha injetada** e **2/2 locais do
  EPUBCheck preservados** — e 1 mensagem que o próprio EPUBCheck dá sem local (o RSC-005 depois do
  erro fatal), contada à parte.
- **As sabotagens:** `sem_linha` reprova (6/50 defeitos certos) e `regra_muda` reprova (49/50: o
  diagrama sem `data-fen` some).
- **Os testes:** `tests/unit/editor/test_validacao.py` (70: cada defeito, toda regra com o seu, o
  vocabulário do validador igual ao do MARKUP, o de 8 MB, o limpo do contrato, os consertos, a
  coluna por caractere, o local do EPUBCheck, o pacote sem Qt, as variáveis e o teto da prévia) e a
  tabela do executor.
- **Decisões declaradas:** (1) o limpo conta os problemas que bloqueiam ou avisam; as notas
  (`informa`: o DOCX não leva, a prévia não desenha) e as dúvidas do OCR do IR real (dúvidas de
  verdade) são contadas à parte; (2) o símbolo fora do glossário só se confere com um glossário
  (o H24 o gera), e a abreviatura, pela lista do contrato (`Contexto.abreviaturas`); (3) além dos
  arquivos que o roadmap nomeia, `contexto.py`, `folha.py` e a camada `epubcheck.py`, e a
  `previa.paginar`/`resolver_variaveis` que a prévia do H13 usa; (4) o MARKUP ganhou a §12.4
  (`img.cb-imagem-de-texto`, `section.cb-resumo-simples`); (5) o diagrama que difere do lance de
  cima avisa (no CB é erro).
- **O portão:** pendente — `& $PY benchmarks\editor_portoes.py --passo H10 --saida benchmarks\reports\editor\h10`
  (a rodada sem o tempo: `& $PY benchmarks\editor_validacao.py --sem-desempenho --saida <pasta>`).
