# Editor HTML/CSS — vereditos dos críticos

> Críticas adversariais da `EDITOR_HTML_CSS_SPEC.md` e do `EDITOR_HTML_CSS_ROADMAP.md` (documentos) e,
> depois, de cada fase executada. Carta: `CRITIC_CHARTER.md`, adaptada a documento no ciclo dos
> documentos (número sem origem, linha fora de ±10, contradição com ADR ou `SPEC.md`, portão sem
> sabotagem que reprova, dependência errada, promessa sem plano).
> Crítico: Codex (`codex exec -s read-only --ephemeral`, esforço `high`), sem acesso a esta conversa;
> lê os documentos e o código dos dois repositórios.

## Documentos — ciclo 1 (2026-09-23): REPROVADO, 12 bloqueantes

O que a versão 1.1 mudou para cada bloqueante está na spec §9. O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 1  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | Spec §2.1 L129–130: painel é `QTextEdit` e desfazer nativo desligado | `painel_de_texto.py:325,339–343` | Confirmada |
| 2 | Spec §2.1 L131–136: somente `textChanged` é ligado e edição não entra no documento | `painel_de_texto.py:355,554–556,1509–1618` | Falsa |
| 3 | Spec §2.1 L139–142: Texto usa `ler_pagina` do tronco | `painel_de_texto.py:1443–1446` | Confirmada |
| 4 | Spec §2.1 L143–144: diagrama vira `[Diagrama N]` | `text/pagina.py:593–601` e `text/leitor.py:1326–1336` | Confirmada |
| 5 | Spec §2.1 L147–150: seletor não acompanha o PDF e HTML não tem CSS | `painel_de_texto.py:1411–1414,1481–1495`; `text/exportacao.py:297–303,384–388` | Parcialmente falsa |
| 6 | Spec §2.2 L155–156: `Document.body` é tupla e `GroupRole.CHAPTER` existe | `document.py:276–280`; `blocks.py:131–143` | Confirmada |
| 7 | Spec §2.2 L157–160: IR possui identidade, proveniência e bandas de confiança | `base.py:52–63`; `provenance.py:106–149` | Confirmada |
| 8 | Spec §2.2 L161–163: `Span` e proveniência própria de figurinas existem | `inline.py:389–403`; `importer.py:1859–1900` | Confirmada |
| 9 | Spec §2.2 L168–172: opções de revisão, decisões de diagrama e cancelamento existem | `importer.py:309–415,1512–1635` | Confirmada |
| 10 | Spec §2.3 L176–185: `XhtmlBuilder` e leitor XML estrito existem | `html.py:1951–1966,4241–4267` | Confirmada |
| 11 | Spec §2.3 L178–183: exportação atual usa `data-ir`, `data-ir-id` e CSS gerado | `html.py:2137–2147,2982–2989,1748–1774` | Confirmada |
| 12 | Spec §2.3 L182: estilo nomeado vira `--caissa-pstyle` | `html.py:1375–1378` | Confirmada |
| 13 | Spec §2.3 L187–193: EPUB divide por título/260 KB e usa `CHESS_CSS` | `epub.py:93–105,419–447` | Confirmada |
| 14 | Spec §2.3 L194–196: IR embutido e caminho absoluto do PDF | `base.py:372–392`; `epub.py:353–361`; `importer.py:1551–1555` | Confirmada |
| 15 | Spec §2.3 L197–200: parser escapa texto, preserva raw e exportador não executa EPUBCheck | `html.py:1921–1935`; `epubcheck.py:104–139`; ausência de chamada em `book.py:282–380` | Confirmada |
| 16 | Spec §2.4 L204–214: vocabulários `cb-*`, plugin e Caissa coexistem | `MARKUP.md:109–121`; `EDITOR_HTML_CSS_SPEC.md:739–750` | Confirmada |
| 17 | Spec §2.4 L205 e S4 L745: atributos do diagrama são `data-mode` e `data-orientation` | MARKUP `:109–121`; spec `:745` | Contraditória internamente |
| 18 | Spec §2.5 L230–232: `janela.py` tem 2.077 linhas | `(Get-Content ...\\qt\\janela.py).Count` | Falsa: resultado atual 2.080 |
| 19 | Spec §2.5 L233–241: guarda de teclas é global e acessibilidade trata `QDialog` | `qt/atalhos.py:275–292`; `qt/acessibilidade.py:220–227` | Confirmada |
| 20 | Spec §2.5 L242–248: estado é v6 e visor só possui caixas de diagrama | `ui/state.py:38`; `qt/visor.py:323,542–550` | Confirmada |
| 21 | Spec §2.6 L265–270: QtWebEngine/QScintilla ausentes e QtPdf presente | execução real no `.venv-pack` | Confirmada |
| 22 | Spec §2.6 L286–295: teto é 150 MB e custo Chromium foi extrapolado | `build_windows.py:78`; `tests/integration/test_packaging.py:546–580` | Confirmada |
| 23 | Roadmap pré-voo L39–46 define `PACK`, `AUDIT`, `PYQ-UI` como comandos | `Get-Command PACK,AUDIT,PYQ,PYQ-UI` | Não executáveis como escritos |
| 24 | Roadmap H1 L152–206 já dispõe de benchmark, fixtures e sabotagens | `Test-Path` nos arquivos citados | Falsa no estado atual: todos ausentes |
| 25 | Roadmap H5 L368–377 possui portão executável de ida e volta | `benchmarks/editor_ida_e_volta.py` | Instrumento ainda não existe |
| 26 | Roadmap H10 L596–608 já pode auditar a janela secundária | módulos/aliases atuais | Não executável como escrito |
| 27 | Roadmap H13 L713–725 testa componente Chromium empacotado | `packaging/webengine_manifesto.json` e `src/caissa/editor` | Arquivos ainda não existem |
| 28 | Roadmap H21 L981–987 mede cobertura de lances publicados | texto do portão | Não há denominador, recall mínimo ou corpus esperado |
| 29 | Roadmap H22 L1020–1032 mede acessibilidade bloqueante do EPUB | `editor_publicacao.py` e validator | Harness inexistente; “0 bloqueantes” pode ser tautológico |
| 30 | Roadmap §1 L109–115 contém todas as dependências | grafo versus H20/H21/H22/H23 | Incompleto |

## Defeitos bloqueantes

1. ONDE `EDITOR_HTML_CSS_SPEC.md:131–150` e `EDITOR_HTML_CSS_ROADMAP.md:64,1079–1090`. O documento afirma que a aba Texto perde edições e precisa de um conserto separado. COMO CONFERIR: `painel_de_texto.py:554–556` conecta `contentsChange`; `:1509–1540` processa digitação; `:1562–1618` grava o novo `DocumentoRico`; `(Get-Content ...\\qt\\janela.py).Count` retorna 2.080, não 2.077. POR QUE REPROVA: a base factual usada para Q1, H25 e o limite da catraca está errada. Um contrato com fatos falsos e números já vencidos não pode governar implementação.

2. ONDE spec D1 L527–546, R2.2 L381–392, S3/S4 L730–758 e H5 L346–377. O QUE: promete ida e volta XHTML↔IR “sem perda” e ainda permite editar CSS, mas o IR só possui estilos estruturados finitos; o CSS arbitrário não tem representação definida. COMO CONFERIR: `core/model/styles.py:256–283` mostra o `StyleSheet`; `html.py:1748–1774` gera classes CSS; o leitor atual reconstrói por `data-ir` em `html.py:4241–4267`. Não há contrato para cascata, seletores, pseudo-elementos, `@media`, `@page`, variáveis, `@font-face`, grid/flex ou CSS desconhecido. POR QUE REPROVA: `canon(escrever(ler(x))) == canon(x)` não é sustentável para a capacidade prometida. `RawPassthrough` preserva XHTML, não fecha a semântica CSS nem garante exportação equivalente.

3. ONDE spec D3 L574–607, R1.13 L361–363, roadmap H1/H13 L179–186 e L685–729. O QUE: propõe QtWebEngine dentro de `runtime\`, separado do PyQt6 em `_internal\`, sem demonstrar carregamento real no PyInstaller. COMO CONFERIR: `QtWebEngineWidgets` está ausente no `.venv-pack`; `build_windows.py:56–71` trata `runtime` como pasta do usuário e a medição em `:811–815` a exclui; `webengine_manifesto.json` e `src/caissa/editor` ainda não existem. POR QUE REPROVA: o portão de tamanho pode aprovar excluindo justamente o componente; não há prova de DLLs, `QtWebEngineProcess`, recursos, locais, versão binária, instalação offline, rollback ou execução em máquina limpa.

4. ONDE spec D4 L617–633, S5 L760–779 e roadmap H2/H11 L238–246,636–644. O QUE: a decisão por `QPlainTextEdit` é tratada como caminho profissional antes de provar desempenho e acessibilidade. COMO CONFERIR: o benchmark `benchmarks/editor_codigo.py` não existe; o portão mede até 2 MB, mas a spec exige também abertura de projeto de 300 páginas, primeira pintura ≤800 ms, digitação com prévia e operações completas. A verificação do Narrador é apenas “curta” e manual. POR QUE REPROVA: não há instrumento que prove o orçamento real sob edição, realce, completar, dobras, desfazer e escala; se o nativo falhar, o plano de migração para QScintilla não tem passo, pacote, licença nem novo portão.

5. ONDE spec D5/S1 L642–700 e roadmap H10 L568–608. O QUE: “DonoDeAcoes” e `JANELAS_SECUNDARIAS` são declarados como solução, mas o roteamento entre duas `QMainWindow` não está especificado. COMO CONFERIR: `qt/atalhos.py:275–292` instala filtro na aplicação inteira; `qt/acessibilidade.py:220–227` só trata `QDialog`. O portão H10 espiona comandos, mas não testa ações nativas, IME, AltGr durante entrada de texto, menus/popups, duas janelas de editor ou foco com a janela principal ativa/inativa. POR QUE REPROVA: pode “passar” engolindo a tecla e ainda não executar o comando correto; R3.6 e R3.7 não estão provados.

6. ONDE spec R5 L498–501 e roadmap H15 L771–789/H20 L939–953. O QUE: promete decisões compartilhadas com trava, releitura e sinais entre duas janelas, mas H15 só testa uma decisão e uma reabertura da aba. COMO CONFERIR: `ocr/review.py:542–547` grava diretamente com `write_text`; apenas `diagram_decisions.py:293–326` tem lock local. Não existe serviço único nem teste de duas janelas concorrentes, conflito, mtime ou atualização de vistas. POR QUE REPROVA: duas janelas podem perder decisões de revisão ou exibir estado obsoleto; isso viola diretamente “nada se perde”.

7. ONDE roadmap H16 L821–829, H18 L884–889 e H21 L981–987. O QUE: vários portões aceitam implementação vazia ou parcialmente vazia. COMO CONFERIR: H16 exige apenas XHTML válido e desfazer; uma operação que não altere nada passa. H18 não fixa padrão, número esperado de ocorrências ou recusas; um plano vazio passa. H21 exige “0 lances inventados”, mas não exige cobertura mínima; marcar zero lances também passa. POR QUE REPROVA: sabotagens não provam capacidade positiva. Os portões não distinguem “funciona” de “não faz nada”.

8. ONDE roadmap §1 L109–115, L127–137. O QUE: o grafo de dependências omite dependências semânticas importantes. COMO CONFERIR: H22 depende apenas de H5/H9/H17, mas exporta o resultado de decisões e marcações de H20/H21; H23 depende de H6/H7, mas precisa integrar decisões geradas por H20 e revisão de H15. A própria tabela de arquivos impõe `H21 → H22`, embora o grafo não mostre isso. POR QUE REPROVA: o roadmap pode executar uma fase com contrato funcional incompleto ou exigir rebase oculto. O grafo precisa ser a fonte única, não uma mistura de grafo, ordem de fases e tabela de arquivos.

9. ONDE spec R2.8 L419–424, S1 L695–700 e roadmap H6/H10. O QUE: a aceitação de “não perder trabalho” não cobre o fluxo completo. COMO CONFERIR: H6 testa recuperação/atomicidade, mas não testa a pergunta ao fechar, fechar a janela principal enquanto a secundária está suja, dois diários concorrentes, teto LRU após muitas versões nem recuperação visível na UI. H10 não inclui esses percursos. POR QUE REPROVA: o requisito do usuário é perda zero, e o portão não cobre os eventos que mais causam perda.

10. ONDE spec Q1 L1020–1021, capacidade L30–44 e não-objetivos L1007–1008. O QUE: a especificação decide recomendar o OCR de `import_pdf`, embora o usuário tenha pedido o OCR que alimenta a aba Texto; a ponte da aba Texto vira opcional. COMO CONFERIR: a própria spec registra que `PainelDeTexto` usa `text.leitor.ler_pagina`, enquanto a exportação usa `caissa.ingest.pdf.importer`; são leitores, identificadores e geometrias distintos. H25 é opcional e depende de um conserto que o código atual já contém parcialmente. POR QUE REPROVA: a decisão de produto foi escondida como recomendação. É preciso decidir explicitamente se o editor compartilha o mesmo OCR/IR da aba Texto ou se existem dois produtos de OCR com sincronização formal.

11. ONDE spec R3.2 L445–451 e roadmap H11 L636–644. O QUE: a meta AAA do código exige 7:1 para texto comum, mas o portão só testa pares declarados e uma cor sabotada. COMO CONFERIR: H11 não exige amostragem de todos os estados, seleção, foco, alto contraste Windows, tema escuro, realces sobrepostos e daltonismo; apenas `AUDIT.contraste`. POR QUE REPROVA: “100% dos pares declarados” pode passar com declaração incompleta. O teste deve descobrir papéis ausentes e avaliar pixels/estados reais.

12. ONDE spec S10 L860–876 e roadmap H9/H22. O QUE: acessibilidade e segurança dependem de validadores próprios, sem ferramenta externa ou corpus negativo completo. COMO CONFERIR: H9 prevê ≥40 defeitos, mas H22 aceita “0 bloqueantes” do próprio sistema; não há comando obrigatório para Ace/DAISY/EPUB Accessibility nem casos de falso negativo para `aria`, ordem de títulos, `page-list`, foco e alt enganoso. POR QUE REPROVA: o produto pode declarar acessibilidade passada porque o próprio validador não detectou a falha.

## Defeitos não bloqueantes

- `EDITOR_HTML_CSS_SPEC.md:204–214` e `:739–750` usam `data-mode` no MARKUP e `data-orientation` no contrato Caissa sem decidir compatibilidade ou migração.
- H1/H13 dependem de download sob consentimento, mas não definem quem assina o manifesto, como revogar uma versão vulnerável ou como desfazer instalação parcial.
- H4 promete “sete sintomas” sem schema do contador, severidade por sintoma ou corpus mínimo.
- H8 mede 200 pontos aleatórios, mas não fixa seed nem distribuição por entidades, comentários, elementos sobrepostos e XHTML inválido.
- H17 testa somente contraste AA dos temas, embora a promessa de excelência AAA seja mais ampla.
- H19 exige 100% dos casos, mas não define um corpus versionado independente do construtor.
- H20 permite “≤4 ações”, porém não mede que o recorte original, FEN, SVG e texto de legenda permaneçam consistentes após reabrir.
- H24 e H25 estão marcados como opcionais apesar de influenciarem interoperabilidade e continuidade entre a aba Texto e o editor.
- O pré-voo L30–35 afirma `git status` e estado de repositórios, mas não inclui uma barreira que impeça o roadmap de trabalhar sobre os 16+6 arquivos modificados já existentes.
- A spec cita `EDITOR_HTML_CSS_CRITICAS.md` e `EDITOR_HTML_CSS_REPORT.md`, mas nenhum dos dois documentos é criado antes desta crítica.

## O que especificamente precisa mudar para eu aprovar

- Corrigir toda a §2 contra o código atual, incluindo `contentsChange`, exportação HTML, sincronização de página e o valor real de `janela.py`.
- Resolver Q1 explicitamente com o usuário e definir uma única fronteira de dados entre OCR, aba Texto, IR e editor.
- Reescrever D1/R2.2: ou limitar CSS a um subconjunto formalmente fechado, ou preservar CSS como fonte com conversão explícita e `DegradationWarning`; testar cascata, `@media`, `@page`, fontes, SVG e CSS desconhecido.
- Provar o Chromium em build PyInstaller real, com runtime instalado em máquina limpa, DLLs/recursos verificados, tamanho medido incluindo o instalador do componente e rollback.
- Definir roteamento de teclado por janela e testar duas `QMainWindow`, AltGr, IME, popups, menus, ações globais e leitor de tela.
- Criar o serviço único de decisões com lock, releitura, sinal e testes concorrentes entre duas janelas.
- Tornar cada portão não-vazio: corpus fixo, seed, contagens esperadas, cobertura mínima, casos positivos e falha obrigatória quando o instrumento não existe.
- Corrigir o grafo: explicitar `H20/H21 → H22` e as dependências de H23 sobre revisão/decisões.
- Acrescentar percursos de fechamento, recuperação, diário, versões, conflito e erro de gravação à aceitação UI.
- Substituir aliases pseudocódigo (`PACK`, `AUDIT`, `PYQ-UI`) por comandos PowerShell executáveis ou scripts versionados.
- Só então repetir a crítica documental e a comparação às cegas contra Sigil, Calibre Editar Livro e ABBYY FineReader.
## Documentos — ciclo 2 (2026-09-23): REPROVADO, 8 bloqueantes

Dos 12 do ciclo 1: 8 resolvidos, 4 parciais (1, 6, 7, 8) — a versão 1.2 escreveu «7 e 5», erro corrigido na 1.3. O que a versão 1.2 mudou está na spec §9 (tabela do ciclo 2). Nota do autor: o bloqueante 1 veio de um comando errado do Apêndice A.3 da versão 1.1 (`Measure-Object -Line` conta só linhas não vazias: 1.808), não de uma contagem errada — `janela.py` tem 2.077 linhas no HEAD `8243e90`. O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 2  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 1 — situação

| # | bloqueante c1 | situação | evidência |
|---:|---|---|---|
| 1 | Fatos incorretos sobre digitação e tamanho de `janela.py` | **PARCIAL** | A árvore atual tem `contentsChange` e `_digitado` (`qt/painel_de_texto.py:568,1533`), mas os números declarados na spec estão errados: HEAD tem 1.808 linhas e a árvore 2.077, não 2.077/2.080. |
| 2 | Ida e volta impossível com CSS arbitrário | **RESOLVIDO** | D1 separa estrutura IR de CSS verbatim e cria mapa fechado com avisos (`spec D1`, `S3b`, roadmap H5). |
| 3 | QtWebEngine fora da medição do pacote | **RESOLVIDO** | H1/H14 exigem sonda PyInstaller, máquina limpa, manifesto, hash, instalação atômica e orçamento próprio. |
| 4 | QPlainTextEdit decidido sem prova | **RESOLVIDO** | D4 é provisória; H2 mede todas as funções e H2b existe como alternativa. |
| 5 | Roteamento de teclas entre janelas não especificado | **RESOLVIDO** | R3.6/H11 incluem janela ativa, pop-ups, AltGr, teclas mortas, execução positiva e duas janelas. |
| 6 | Decisões compartilhadas sem serviço único | **PARCIAL** | R5/H7 existem, mas `ui/views/revisao_de_texto.py:622-623` ainda grava `ReviewDecisions` diretamente; H7 não lista nem bloqueia esse caminho. |
| 7 | Portões aceitavam implementação vazia | **PARCIAL** | Há casos positivos e sabotagens, mas H2/H12, H0 e H24 ainda não verificam todas as capacidades prometidas. |
| 8 | Grafo de dependências incompleto | **PARCIAL** | H9 usa artefatos de H8 mas depende apenas de H5; H19 precisa do mapa de H5, mas a tabela não declara essa dependência. |
| 9 | “Nada se perde” sem percurso de janela | **RESOLVIDO** | H17 cobre fechamento, queda, recuperação, erro de gravação, conflito externo, versões e janela principal. |
| 10 | Q1 decidido implicitamente | **RESOLVIDO** | Q1 agora tem A/B/C, medição H0 e bloqueia H8/H26 até decisão. |
| 11 | AAA testado só em cores declaradas | **RESOLVIDO** | R3.2/H12 adicionam descoberta em runtime, pixels, estados sobrepostos e daltonismo. |
| 12 | Acessibilidade dependente só de validador próprio | **RESOLVIDO** | H24 inclui Ace do DAISY e corpus negativo externo. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | A aba Texto usa `contentsChange` e `_digitado` (§2.1) | `qt/painel_de_texto.py:568,1533-1646` | Confirmada na árvore; ausente no HEAD. |
| 2 | A mudança de digitação ainda não está commitada (§2.1) | `git status` do tronco | Confirmada. |
| 3 | A aba Texto e `import_pdf` são leitores distintos (§2.1) | `text/leitor.py`; `ingest/pdf/importer.py` | Confirmada. |
| 4 | Diagramas da aba Texto viram `[Diagrama N]` (§2.1) | `text/pagina.py:589-601`; `text/leitor.py:1326` | Confirmada. |
| 5 | `janela.py:1060` define o livro no painel Texto (§2.1) | `qt/janela.py:1060` | Confirmada. |
| 6 | A mudança de página visível não chama `texto.definir_livro` (§2.1) | `qt/janela.py:_pagina_apareceu` | Confirmada. |
| 7 | Exportação HTML sem mapas deixa estilos incompletos (§2.1) | `text/exportacao.py:290-303`; chamada sem mapas no painel | Confirmada. |
| 8 | Sem recorte, diagrama HTML vira marca textual (§2.1) | `text/exportacao.py:576-590` e `diagrama()` | Confirmada. |
| 9 | `Document.body` é plano e `GroupRole.CHAPTER` existe (§2.2) | `core/model/document.py`; `blocks.py` | Confirmada. |
| 10 | `IRNode` possui `id` e `provenance` (§2.2) | `core/model/base.py:52-63` | Confirmada. |
| 11 | `Span` e proveniência de figurinas existem (§2.2) | `core/model/inline.py`; `importer.py:1859-1900` | Confirmada. |
| 12 | `CURRENT_SCHEMA_VERSION = 1` (§2.2) | `core/model/migrations.py:51` | Confirmada. |
| 13 | `ResourceKind.STYLESHEET` existe (§2.2) | `core/model/document.py:58-63` | Confirmada. |
| 14 | `RunProps.language` existe (§2.2) | `core/model/props.py:948` | Confirmada. |
| 15 | Opções de revisão, diagramas e cancelamento existem (§2.2) | `ingest/pdf/importer.py:309-415` | Confirmada. |
| 16 | Diagrama conserva FEN, lado, estipulação e solução (§2.2) | `importer.py:1512-1635` | Confirmada, com ressalvas de semântica a validar no H8. |
| 17 | `ReviewDecisions.save` não é atômico (§2.2) | `ocr/review.py:542-546` | Confirmada. |
| 18 | `DiagramDecisions.record` usa `O_EXCL` (§2.2) | `ocr/diagram_decisions.py:293-326` | Confirmada. |
| 19 | `DiagramDecisions.save` já usa temporário e `replace` | `ocr/diagram_decisions.py:242-247` | Confirmada. |
| 20 | `XhtmlBuilder` escreve `data-ir`/`data-ir-id` (§2.3) | `export/html.py:1951,2141-2142` | Confirmada. |
| 21 | O leitor HTML atual depende de XML estrito (§2.3) | `export/html.py:4241-4267` | Confirmada. |
| 22 | EPUB usa `split_level=1` e limite de 260 KB (§2.3) | `export/epub.py:128-130,419-448` | Confirmada. |
| 23 | EPUB embute `caissa-ir.json` (§2.3) | `export/epub.py:353-361` | Confirmada. |
| 24 | O IR embutido pode carregar caminho absoluto do PDF (§2.3) | `importer.py:1551-1556` | Confirmada. |
| 25 | EPUBCheck não é executado por `export_book` (§2.3) | `export/epubcheck.py`; `export/book.py:282-380` | Confirmada. |
| 26 | `janela.py` tem 2.077 no HEAD e 2.080 na árvore (§2.5) | `git show HEAD:...`; árvore atual | **Falsa no estado observado**: 1.808 no HEAD e 2.077 na árvore. |
| 27 | Suite está em HEAD `f9ca678` (§0.1 do roadmap) | `git rev-parse HEAD` | **Falsa no estado observado**: HEAD atual `bb41c558`. |
| 28 | `runtime/` é excluído da medição (§2.6) | `build_windows.py:56-71,806-815` | Confirmada. |
| 29 | `html_attributes` já existe como campo do IR (D1/H5) | `core/model/base.py` | **Não existe ainda**; é tarefa futura do H5, portanto deve ser tratado apenas como contrato planejado. |
| 30 | Todos os escritores de decisões passarão pelo H7 | `ui/views/revisao_de_texto.py:622-623` | **Não sustentada pelo plano atual**: existe escritor direto fora dos arquivos listados no H7. |

## Defeitos bloqueantes (novos ou remanescentes)

1. **ONDE** spec §2.5 e roadmap §0.1. **O QUE** os números de HEAD/árvore estão incorretos, e o número errado é usado como `LIMITE` de `janela.py`. **COMO CONFERIR** `git show HEAD:src/chess_diagram_ocr/qt/janela.py | Measure-Object -Line` dá 1.808; a árvore dá 2.077. **POR QUE REPROVA** a catraca e R1.12 passam a operar contra uma base factual falsa. A spec deve registrar o comando, os hashes e medir somente o delta do passo.

2. **ONDE** spec R5 e roadmap H7. **O QUE** o serviço único não cobre todos os escritores: `ui/views/revisao_de_texto.py:622-623` chama `self.queue.decisions().save(destino)` diretamente. **COMO CONFERIR** localizar todos os usos de `ReviewDecisions.save` e exigir que apenas `ocr/decisoes.py` grave. **POR QUE REPROVA** duas janelas podem continuar perdendo decisões apesar de H7 passar nos testes concorrentes.

3. **ONDE** roadmap §1, H5, H9, H13, H15 e H19. **O QUE** a tabela de dependências contradiz os próprios passos: H9 usa “arquivos do H8”, mas depende somente de H5; H13/H15 usam projetos/proveniência do H8 sem dependência explícita; H19 usa o mapa de estilo do H5, mas H5 não libera H19. **COMO CONFERIR** comparar a coluna “depende de”, o grafo ASCII e os “Arquivos/Portão” de cada passo. **POR QUE REPROVA** permite executar portões sobre corpus inexistente ou incompleto e torna a tabela não sendo fonte única.

4. **ONDE** D1, S3b, S11 e H24. **O QUE** a promessa cobre DOCX, PDF e LaTeX, mas H24 só possui tarefas e portões positivos para DOCX; não há verificação do mapa, avisos ou fidelidade no LaTeX nem no PDF pelo IR. **COMO CONFERIR** H24 lista `export/docx.py`, mas não `export/latex.py`, e seu portão não menciona nenhum caso LaTeX/PDF. **POR QUE REPROVA** o programa pode aprovar uma exportação declarada como fiel sem testar dois dos formatos prometidos. Adicionar portões independentes ou retirar a promessa.

5. **ONDE** H0 e Q1. **O QUE** o portão aceita apenas uma página com verdade (`CER em ≥1 página`) para decidir qual OCR alimenta o editor. Não há cobertura mínima por livro, denominador, exigência de manifesto golden não vazio ou regra para comparar os leitores. **COMO CONFERIR** executar H0 com apenas uma página golden ou com manifesto privado vazio. **POR QUE REPROVA** Q1 pode escolher uma fonte de dados central com evidência insuficiente; a recomendação provisória A não pode substituir uma decisão baseada em medição adequada.

6. **ONDE** D4, H2 e H12. **O QUE** o portão mede latência e UIA, mas não exige resultado positivo para várias funções anunciadas: margem, indicadores, realce correto, desfazer semântico, colagem simples, invisíveis, busca e escala. Dobrar um documento vazio ou executar uma operação sem efeito pode continuar dentro do orçamento. **COMO CONFERIR** substituir o protótipo por um editor que não altere nem exponha essas funções; os critérios publicados ainda podem passar. **POR QUE REPROVA** a sabotagem de implementação nula não cobre o editor inteiro. Cada função deve ter caso dourado observável e sabotagem própria.

7. **ONDE** spec R3.2, §5.6 e roadmap H12/H19. **O QUE** o pedido é AAA, mas o contrato aceita sintaxe do código, títulos, legendas e realces com 4,5:1, que é limiar AA para texto normal. A spec não define quando esses textos seriam “texto grande”. **COMO CONFERIR** `R3.2` exige `tokens ≥ 4,5:1`; H19 repete `títulos e legendas ≥ 4,5:1`. **POR QUE REPROVA** um tema pode passar no portão e ainda não cumprir AAA. Exigir 7:1 para texto normal ou declarar e medir exceções por tamanho tipográfico.

8. **ONDE** R5/H7 e o portão de conflitos. **O QUE** a spec promete “volta pelo desfazer” quando duas decisões colidem, mas H7 mede apenas 100 avisos e estado final da última decisão; não testa o desfazer nem a recuperação da decisão descartada. O teste atômico cobre `ReviewDecisions`, não ambos os armazéns. **COMO CONFERIR** inserir dois conflitos reais, tentar desfazer e matar a gravação de `DiagramDecisions`. **POR QUE REPROVA** o usuário pode receber aviso e ainda perder uma decisão sem recuperação, contrariando R5 e “nada se perde”.

## Defeitos não bloqueantes

- A ausência atual dos arquivos `benchmarks/editor_portoes.py`, H5, H7, `src/caissa/editor` e fixtures é coerente com o fato de serem artefatos criados por passos futuros.
- A extensão `data-orientation` agora está explicitamente declarada no contrato Caissa; a antiga contradição com `data-mode` foi sanada.
- As referências de linha podem deslocar-se com a árvore suja; isso só vira bloqueante quando o número é usado como limite ou fato normativo.
- H17 está substancialmente completo como plano de aceitação; falta apenas executá-lo.
- H1/H14 tratam corretamente a exceção de `runtime/`, desde que o orçamento separado seja realmente incorporado ao `bundle.json`.
- H27 ser opcional não bloqueia o núcleo solicitado do editor.

## O que especificamente precisa mudar para eu aprovar

- Corrigir hashes, contagens e comandos de medição da §2.5 e do roadmap §0.1.
- Fazer o H7 abranger `ui/views/revisao_de_texto.py` e bloquear qualquer `ReviewDecisions.save` direto fora do serviço; testar desfazer de conflito nos dois armazéns.
- Corrigir a tabela/grafo: explicitar H8→H9, H8→H13/H15 quando necessário e H5→H19.
- Acrescentar portões para PDF e LaTeX, ou retirar esses formatos da promessa D1/S11.
- Fortalecer H0 com corpus mínimo, denominadores, manifesto golden obrigatório e critério de decisão para Q1.
- Transformar cada função do editor em caso positivo observável, inclusive margem, indicadores, realce, busca, escala, desfazer e colagem.
- Corrigir os limiares AAA ou declarar formalmente as exceções de texto grande e medi-las.
- Reexecutar a crítica após essas alterações e somente depois aprovar H0.
## Documentos — ciclo 3 (2026-09-23): REPROVADO, 9 bloqueantes

Do ciclo 2: 2 resolvidos, 6 parciais. Do ciclo 1: os parciais seguem parciais pelos mesmos motivos, e o «quinto parcial» era um erro de contagem nosso. O que a versão 1.3 mudou está na spec §9 (tabela do ciclo 3). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 3  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 2 (e parciais do ciclo 1) — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| C2-1 | Contagem de `janela.py` | RESOLVIDO | Spec §2.5 L277–283 e Apêndice A.3 L1302–1309 usam `.Count`/`wc -l`; HEAD e árvore atuais têm 2.077 linhas. O HEAD atual `99546e9` é descendente de `bb41c55`, portanto a referência histórica é explicável. |
| C2-2 | Serviço único para decisões | PARCIAL | H7 agora lista `revisao_de_texto.py:623`, o gancho do tronco e teste arquitetural. Porém o teste descrito não detecta necessariamente o escritor indireto do tronco nem garante o desfazer integrado à janela. |
| C2-3 | Dependências incompletas | PARCIAL | H8→H9/H13/H15 e H5→H19 foram corrigidos. Contudo H24 usa explicitamente a matriz CSS do H1 (L1268–1269, L1303), mas a tabela §1 não declara H1 como dependência direta. |
| C2-4 | PDF, DOCX e LaTeX sem portões | RESOLVIDO | H24 L1264–1306 define exportadores e portões independentes para DOCX, PDF e LaTeX. |
| C2-5 | H0 com evidência insuficiente | PARCIAL | O denominador mínimo de 150 regiões e dois livros foi acrescentado. Porém a regra A/B/C ainda tem sinal e precedência ambíguos: B é subconjunto de C se o leitor da aba Texto vencer em todos os estratos. |
| C2-6 | Implementação vazia nos portões | PARCIAL | H12 tem casos dourados por função e `funcao_nula`. Mas H2 ainda prova principalmente atividade por contadores, não comportamento semântico; se H2 passar e H12 reprovar, não existe transição definida para H2b. |
| C2-7 | AAA | PARCIAL | R3.2/H19 corrigem o contraste para 7:1 no texto normal. Porém §5.6 declara o livro exportado como WCAG 2.2 AA, S10 ainda fala em contraste AA, e H24 não exige numericamente AAA para CSS arbitrário do projeto. |
| C2-8 | Desfazer de conflitos nos dois armazéns | PARCIAL | H7 agora exige histórico, restauração e desfazer em ambos os armazéns. Mas o passo só lista serviço/benchmark; não define a transação nem o comando de desfazer da janela que deve restaurar a decisão descartada. |
| C1-1 | Fatos de digitação e tamanho | RESOLVIDO | A spec distingue HEAD, árvore suja e histórico da medição. |
| C1-6 | Decisões compartilhadas | PARCIAL | É o mesmo defeito de C2-2: o plano lista a migração, mas o teste arquitetural proposto não cobre todos os caminhos reais. |
| C1-7 | Portões não-vazios | PARCIAL | H12 melhorou substancialmente, mas H2 continua com prova de atividade, não de resultado. |
| C1-8 | Grafo de dependências | PARCIAL | A maior parte foi corrigida, mas H24→H1 ainda está ausente. |
| C1-5 | Quinto parcial do ciclo 1 | NÃO RESOLVIDO | `EDITOR_HTML_CSS_CRITICAS.md` L107 afirma “5 parciais”, mas a tabela L117–128 marca apenas 1, 6, 7 e 8 como parciais. O quinto não é identificável sem inventá-lo. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | `janela.py` tem 2.077 linhas no HEAD (§2.5) | `git show HEAD:...` e `.Count` | Confirmada |
| 2 | A mudança de digitação está na árvore, mas não no HEAD (§2.1) | `painel_de_texto.py:568,1533–1646`, `git status` | Confirmada |
| 3 | `ReviewDecisions.save` grava diretamente (§2.2) | `ocr/review.py:542–546` | Confirmada |
| 4 | `DiagramDecisions.save` usa temporário e `replace` (§2.2) | `ocr/diagram_decisions.py:242–247` | Confirmada |
| 5 | O gancho do tronco chama `record` em `:43` (§2.2/H7) | `qt/decisoes_de_diagrama.py:43,94–106` | Parcial: `:43` apenas importa `record`; a chamada real está em `:106` |
| 6 | Os leitores usados pelo produto são distintos (§2.1/§2.2) | `text/leitor.py`, `export/book.py:425–427,537–539` | Confirmada |
| 7 | `html_attributes` já existe no IR (§2.2/D1) | `core/model/base.py:53–63` | Falsa como estado atual; é artefato futuro do H5 |
| 8 | O conjunto dourado contém 195 regiões SFC4 | `manifest.private.json`, campos `source/book/partition/regions` | Confirmada em `dev+calib` |
| 9 | O conjunto dourado contém 29 regiões Seirawan | mesmo manifesto | Confirmada em `dev+calib` |
| 10 | H0 exige pelo menos 150 regiões de dois livros | roadmap H0 L228–233 | Confirmada |
| 11 | A regra A/B/C decide Q1 por CER e IC de 95% | spec Q1; roadmap H0 L210–217 | Parcial: falta definir sinal e precedência |
| 12 | CSS é `Resource` verbatim e DOCX usa mapa fechado | spec D1/S3b L651–658, L871–900 | Confirmada como proposta |
| 13 | R1.10 também diz que PDF/LaTeX usam o mapa | spec R1.10 L401–404 | Confirmada; contradiz D1/S3b |
| 14 | H1 exige sonda PyInstaller e máquina limpa | spec D3; roadmap H1 L275–303 | Confirmada como plano, ainda não executada |
| 15 | H2 mede todas as funções ligadas | roadmap H2 L318–360 | Confirmada, mas a prova é de atividade |
| 16 | H12 tem casos dourados por função | roadmap H12 L842–863 | Confirmada |
| 17 | R3.6 cobre popups, AltGr, IME e duas janelas | spec R3.6; roadmap H11 L763–805 | Confirmada como contrato/portão |
| 18 | H7 lista os escritores atuais | roadmap H7 L569–626 | Confirmada, mas com detecção incompleta |
| 19 | H17 cobre fechamento, queda, recuperação e conflito externo | roadmap H17 L1008–1033 | Confirmada |
| 20 | H19 exige 7:1 e sabota `#666` | roadmap H19 L1104–1119 | Confirmada |
| 21 | H24 tem portões de PDF e LaTeX | roadmap H24 L1290–1318 | Confirmada |
| 22 | O livro exportado é AA, com texto corrido AAA | spec §5.6 L1129–1143 | Confirmada; incompatível com uma promessa AAA global |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE spec R5 L597–599 e roadmap H7 L599–601. O QUE o teste arquitetural não cobre o escritor real do tronco: `qt/decisoes_de_diagrama.py` importa `record` em `:43` e chama o alias em `:106`, não `diagram_decisions.record(...)`. Além disso, `current.add(...).save(...)` em `diagram_decisions.py` não corresponde necessariamente aos padrões listados. COMO CONFERIR executando o teste contra os caminhos atuais. POR QUE REPROVA: o portão pode declarar “serviço único” enquanto ainda existe gravação fora dele.

2. ONDE H0 L210–217 e spec Q1. O QUE A/B/C não tem sinal formal nem precedência; B pode satisfazer C simultaneamente. COMO CONFERIR com CER do leitor da aba menor em ambos os estratos. POR QUE REPROVA: a mesma medição pode produzir duas recomendações incompatíveis para uma decisão de produto.

3. ONDE spec R1.10 L401–404 versus R2.2/S3b L439–459 e L871–900. O QUE um trecho normativo diz que PDF/LaTeX consomem CSS pelo mapa, enquanto D1 diz que PDF usa CSS completo e LaTeX apenas avisa. COMO CONFERIR comparando o contrato do exportador com a matriz H1. POR QUE REPROVA: implementadores podem produzir formatos diferentes e ambos alegarem conformidade.

4. ONDE roadmap §1 L138–152. O QUE H24 usa a matriz do H1, mas não depende de H1 na tabela. COMO CONFERIR removendo o artefato do H1 e executando H24. POR QUE REPROVA: a tabela declarada como fonte única permite executar um portão com instrumento ausente.

5. ONDE spec D4 L755–765 e roadmap H2/H12. O QUE H2 pode passar com contadores ativos, mas sem comportamento funcional; H12 só descobre isso depois e não define reabertura da decisão QScintilla. COMO CONFERIR usar funções que apenas incrementam contadores e executam UIA. POR QUE REPROVA: a escolha da arquitetura pode ser aprovada por uma prova tautológica.

6. ONDE spec §5.6/S10 e H19/H24. O QUE a promessa de nível AAA não corresponde ao contrato exportado AA, e o validador ainda usa “contraste AA”. COMO CONFERIR colocar texto normal 5,7:1 em CSS do projeto, fora dos dez temas. POR QUE REPROVA: o livro pode passar e ainda descumprir o nível AAA pedido.

7. ONDE spec R2.4 L465–469 e H24 L1307–1308. O QUE o portão verifica caminhos, letras de unidade e nomes de usuário, mas não verifica ausência de confiança, motor ou notas de OCR. COMO CONFERIR inserir esses campos em `caissa-ir.json`, atributos desconhecidos e `RawPassthrough`. POR QUE REPROVA: dados da máquina podem chegar ao livro publicado apesar de o portão passar.

8. ONDE spec R1.12 L409–414 e roadmap H11 L797. O QUE H11 exige `git diff --numstat` com zero inserções em `janela.py`, em vez de medir o delta do passo. COMO CONFERIR: a árvore atual tem uma alteração pré-existente `1 1` nesse arquivo, embora o total continue 2.077. POR QUE REPROVA: o portão falha por trabalho de outra sessão ou força uma coordenação destrutiva, contrariando o estado compartilhado.

9. ONDE spec R5 L608–615 e roadmap H7 L609–617. O QUE o portão promete desfazer “da janela”, mas H7 não cria nem lista a integração com a pilha de desfazer da janela. COMO CONFERIR procurar o objeto/transação que liga o serviço ao editor e aos dois armazéns. POR QUE REPROVA: o histórico pode existir, mas o usuário ainda pode não conseguir restaurar a decisão descartada pelo desfazer prometido.

## Defeitos não bloqueantes

- O HEAD atual da suíte é `99546e9`, filho de `bb41c55`; a referência histórica não é falsa, mas deveria dizer explicitamente “HEAD no momento da escrita”.
- `EDITOR_HTML_CSS_CRITICAS.md` afirma cinco parciais do ciclo 1, mas enumera quatro.
- H24 depende de H13 transitivamente, então a execução sequencial pode funcionar; o problema é a tabela declarar-se fonte única.
- H27 opcional não bloqueia o núcleo MuPDF.
- Referências de linha futuras podem deslocar-se, desde que cada portão registre o commit e o arquivo efetivamente usado.

## O que especificamente precisa mudar para eu aprovar

- Reescrever o teste de arquitetura do H7 como análise estrutural/allowlist real, cobrindo aliases e chamadas indiretas; incluir o caminho `qt/decisoes_de_diagrama.py:106`.
- Definir formalmente o sinal de CER e a regra mutuamente exclusiva: B primeiro; C somente em alguns estratos; A quando o produto não perde em nenhum.
- Fixar hash/versão do manifesto dourado no relatório H0.
- Harmonizar R1.10, R2.2 e S3b sobre PDF, DOCX e LaTeX.
- Acrescentar H1 como dependência explícita de H24.
- Exigir comportamento positivo no H2 ou definir H2b também quando H12 reprovar.
- Transformar AAA em critério verificável para o livro inteiro, incluindo CSS arbitrário e estados reais.
- Acrescentar testes de ausência de confiança, motor e notas de OCR no EPUB.
- Medir `janela.py` antes/depois do passo, isolando alterações pré-existentes.
- Definir a transação de desfazer da janela para conflitos nos dois armazéns.
- Corrigir a contagem histórica dos parciais e repetir a crítica documental.
## Documentos — ciclo 4 (2026-09-23): REPROVADO, 4 bloqueantes

Do ciclo 3: 5 resolvidos, 4 parciais. O que a versão 1.4 mudou está na spec §9 (tabela do ciclo 4). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 4  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 3 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Exclusividade do serviço de decisões | PARCIAL | R5 e H7 cobrem aliases, imports e métodos privados, mas o AST não reprova um novo escritor que serialize diretamente com `write_text`, `os.replace` ou acesso dinâmico. |
| 2 | Regra A/B/C de Q1 | RESOLVIDO | §7 Q1 e H0 definem Δ = CER(Texto) − CER(produto), vitória pelo limite superior `< 0` e precedência exclusiva B → C → A. |
| 3 | Contradição PDF/LaTeX | RESOLVIDO | R1.10 agora remete explicitamente a R2.2(c–e); S3b repete a mesma política. |
| 4 | Dependência H24 → H1 | RESOLVIDO | A tabela do roadmap §1 agora declara H1 como dependência direta de H24. |
| 5 | D4 aprovada por contadores | RESOLVIDO | H2 exige pelo menos cinco casos dourados por função; H12 reabre H2b quando houver limite do componente. |
| 6 | Promessa AAA inconsistente | PARCIAL | O livro agora é declarado AA + dois critérios AAA, mas isso não satisfaz o pedido de nível AAA nem justifica sistematicamente os demais critérios. |
| 7 | Proveniência no EPUB | PARCIAL | H24 remove `caissa-ir.json` e alguns nomes conhecidos, mas a varredura não cobre todos os campos de proveniência nem prova a completude do sidecar. |
| 8 | Contagem de `janela.py` | RESOLVIDO | H11 mede antes/depois com `.Count`; HEAD e árvore atual do tronco têm 2.077 linhas, embora o arquivo esteja sujo. |
| 9 | Desfazer por escritor | PARCIAL | `Recibo` está especificado, mas H7 exige a integração real do editor e da aba Resultado antes de H16/H22, que são passos posteriores e dependem de H7. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | O gancho importa `record` em `qt/decisoes_de_diagrama.py:43` (§2.2) | Tronco `qt/decisoes_de_diagrama.py:40–47` | Confirmada |
| 2 | O gancho chama `record` em `:106` | Mesmo arquivo, `:94–106` | Confirmada |
| 3 | `ReviewDecisions.save` grava diretamente | Suíte `ocr/review.py:542–546` | Confirmada |
| 4 | `DiagramDecisions.save` usa temporário e `replace` | Suíte `ocr/diagram_decisions.py:242–247` | Confirmada |
| 5 | `#595959` sobre branco é aproximadamente 7:1 | Cálculo sRGB | Confirmada: 7,0047:1 |
| 6 | `#666` sobre branco é aproximadamente 5,7:1 | Cálculo sRGB | Confirmada: 5,7418:1 |
| 7 | A regra de vitória de Q1 usa o limite superior do intervalo | Spec §7 Q1, roadmap H0:210–217 | Confirmada |
| 8 | B, C e A são mutuamente exclusivas | Spec §7 Q1, roadmap H0:214–217 | Confirmada |
| 9 | H0 exige pelo menos 150 regiões, dois livros, um nativo e um digitalizado | Roadmap H0:230–235 | Confirmada |
| 10 | Todo nó do IR carrega proveniência | `core/model/base.py:53–63` | Falsa como formulada: `provenance` é opcional e pode ser `None`; o próprio docstring diz isso. |
| 11 | O IR tem proveniência em todo nó para o sidecar | `export/provenance.py:98–153` | Falsa como cobertura: o sidecar registra principalmente `Diagram` e `GameScore`, não cada nó. |
| 12 | `embed_ir` é `True` por padrão | `export/base.py:389–395` | Confirmada |
| 13 | A exportação do editor usará `embed_ir=False` | Spec R2.4; roadmap H24:1319–1320 | Apenas proposta futura; não é estado atual nem há teste positivo explícito de que o caminho do editor sempre force `False`. |
| 14 | H2 tem comportamento observável por função | Roadmap H2:361–364 | Confirmada |
| 15 | H2b reabre quando H12 reprova por limite do componente | Spec D4; roadmap H12:893–895 | Confirmada |
| 16 | H24 varre todos os arquivos do EPUB | Roadmap H24:1340–1344 | Confirmada como plano, mas a lista de chaves é incompleta. |
| 17 | H24 tem portões independentes de PDF e LaTeX | Roadmap H24:1332–1339 | Confirmada |
| 18 | A tabela declara H24 dependente de H1 | Roadmap §1, linha 152 | Confirmada |
| 19 | `janela.py` tem 2.077 linhas no HEAD e na árvore atual | `git show HEAD:...` e `.Count` | Confirmada |
| 20 | O tronco está sujo por alterações da aba Texto | `git status --short` | Confirmada |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE roadmap §1, H7:614–633 e H16/H22. O QUE o portão de H7 exige o `Recibo.desfazer()` real do editor e o `Ctrl+Z` real da aba Resultado, mas H16 e H22 são passos posteriores que dependem de H7. COMO CONFERIR executar H7 em uma base contendo apenas os artefatos permitidos por sua linha de dependências. Os caminhos reais ainda não existem; usar dublês não prova a integração. POR QUE REPROVA: o passo não é autocontido e pode aprovar um desfazer que ainda não existe, ou tornar o próprio H7 inexequível.

2. ONDE spec R2.4:471–482 e roadmap H24:1319–1348. O QUE a spec afirma que todo nó carrega proveniência, mas `IRNode.provenance` é opcional (`core/model/base.py:58–63`) e o sidecar atual registra somente classes específicas (`export/provenance.py:98–153`). Além disso, a varredura cita apenas `confidence`, `band`, `engine`, `model_hash`, `note`, `ocr_`, `data-ir-id` e `proveniencia`; não cobre, por exemplo, `engine_version`, `page_index`, `rect`, `verified_by_human`, `source`, `content_hash`, `dpi`, `recognition` e `model_name`. COMO CONFERIR inserir esses campos em `RawPassthrough`, atributos desconhecidos ou metadados e rodar a varredura. POR QUE REPROVA: dados de máquina podem escapar, ou a proveniência pode simplesmente desaparecer quando o IR é removido do EPUB.

3. ONDE spec §5.6:1165–1177 e roadmap H19:1135–1145. O QUE o contrato do livro declara `conformsTo` AA e promete apenas AAA 1.4.6 e 2.4.10; as justificativas apresentadas cobrem somente 1.4.8, 3.1.3 e 3.1.5. COMO CONFERIR comparar isso com o pedido explícito de “nível AAA” e procurar critérios AAA restantes sem decisão de aplicabilidade ou portão. POR QUE REPROVA: o plano entrega uma conformidade AA ampliada, não nível AAA. Se essa redução for intencional, precisa ser uma decisão explícita do usuário, não uma alteração silenciosa do objetivo.

4. ONDE spec R5:610–620 e roadmap H7:604–613, 639–648. O QUE o teste AST prova apenas ausência de certos nomes públicos/privados e imports; não prova que nenhum módulo escreva diretamente o armazém por outra API. COMO CONFERIR adicionar um escritor que construa o JSON e use `Path.write_text`, `os.replace` ou `getattr` com nome montado dinamicamente; as sabotagens previstas não o cobrem. POR QUE REPROVA: a afirmação “serviço é o único caminho de escrita” pode passar enquanto existe um caminho concorrente sem trava, recibo ou histórico.

## Defeitos não bloqueantes

- Os cálculos de contraste do H19 estão corretos.
- A contagem de `janela.py` está corretamente distinguida entre HEAD e árvore de trabalho.
- A insuficiência estatística potencial do estrato nativo de apenas 29 regiões é uma fragilidade metodológica, mas a regra de decisão já é determinística.
- A omissão de invisíveis e trilha de pão no subconjunto comportamental do H2 é coberta posteriormente pelo H12.
- A inconsistência histórica sobre “cinco parciais” no relatório antigo continua apenas como erro editorial.

## O que especificamente precisa mudar para eu aprovar

- Separar o portão do serviço H7 dos portões de integração de H16/H22, ou criar uma fase posterior explícita para os três caminhos de desfazer.
- Fazer o teste arquitetural auditar efetivamente todas as APIs de escrita dos dois armazéns, não apenas nomes privados e aliases.
- Corrigir a afirmação de proveniência para refletir o modelo opcional e definir o contrato completo do sidecar.
- Tornar a varredura semântica e abrangente, incluindo todos os campos de proveniência e dados de origem.
- Forçar e testar positivamente `embed_ir=False` no caminho de exportação do editor.
- Decidir com o usuário se o livro deve cumprir AAA real; se sim, acrescentar os critérios e portões restantes. Se não, declarar formalmente o escopo como AA + critérios AAA selecionados.
## Documentos — ciclo 5 (2026-09-23): REPROVADO, 7 bloqueantes

Do ciclo 4: 1 resolvido, 3 parciais. O que a versão 1.5 mudou está na spec §9 (tabela do ciclo 5). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 5  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 4 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Desfazer por escritor | RESOLVIDO | H7 agora testa apenas `Recibo`, `Ctrl+Z` da aba Resultado e restauração da aba Revisão (`ROADMAP` H7:614–640). O desfazer do editor foi corretamente deslocado para H16/H22 (`H16:1047–1048`, `H22:1265–1266`), ambos dependentes de H7. |
| 2 | Proveniência no EPUB | PARCIAL | `IRNode.provenance` é opcional (`core/model/base.py:53–63`), mas o `ROADMAP` ainda afirma em H24 que há proveniência “em todo nó” (`H24:1344–1345`). O portão cobre IDs, mas não garante igualdade completa dos campos nem corrige explicitamente o defeito real de `Rect` (`export/provenance.py:87,114`; `export/book.py:209–212`). |
| 3 | Promessa AAA inconsistente | PARCIAL | A tabela agora lista todos os critérios AAA, mas Q7 continua sem decisão e o plano recomenda declarar apenas AA (`SPEC` §5.6:1191–1224; §7:1297). Além disso, há lacunas de portão para critérios classificados como “por construção”. |
| 4 | Escrita direta fora do serviço | PARCIAL | O AST foi ampliado e a guarda de execução foi adicionada (`SPEC` R5:630–646; `ROADMAP` H7:604–640), mas o plano cita `os.replace` como evento separado. Em Python 3.10 e 3.11, `os.replace()` emite o evento de auditoria `os.rename`, não `os.replace`. Uma implementação literal deixará escapar a substituição atômica. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | `IRNode.provenance` é opcional (SPEC R2.4) | `core/model/base.py:53–63` | Confirmada: pode ser `None`. |
| 2 | O sidecar atual registra apenas `Diagram` e `GameScore` (SPEC §2.3) | `export/provenance.py:98–153` | Confirmada. |
| 3 | `embed_ir=True` é o padrão | `export/base.py:389–395` | Confirmada. |
| 4 | O exportador do editor força `embed_ir=False` | SPEC R2.4; ROADMAP H24:1365–1366 | Apenas proposta futura; ainda não é comportamento existente. |
| 5 | `sys.addaudithook` existe nos dois ambientes | Python 3.10.11 do tronco e 3.11.9 da suíte | Confirmada. |
| 6 | A auditoria captura `open`, `os.remove` e renomeações | execução local nos dois ambientes | Confirmada. `os.replace` aparece como `os.rename`; a redação atual está tecnicamente errada. |
| 7 | O gancho consegue provar a pilha do escritor | SPEC R5:643–646 | Parcial: é viável, mas o plano não define canonicalização de caminhos, junctions/symlinks ou caminhos relativos. |
| 8 | H7 não depende mais do desfazer do editor | ROADMAP §1:135,144,150; H7/H16/H22 | Confirmada e coerente. |
| 9 | Os escritores atuais são distintos | `ocr/review.py:542–547`; `ocr/diagram_decisions.py:242–248`; tronco `qt/decisoes_de_diagrama.py:43,106` | Confirmada. |
| 10 | H2 exige comportamento positivo, não só contadores | ROADMAP H2:349–365 | Confirmada. |
| 11 | H2b reabre quando H12 reprova por limite do componente | ROADMAP H2b e H12 | Confirmada. |
| 12 | A regra A/B/C de Q1 é exclusiva | SPEC §7 Q1:1291 | Confirmada. |
| 13 | A tabela AAA omite algum critério WCAG 2.2 | SPEC §5.6:1195–1217 | Não: a lista inclui os critérios AAA, inclusive 2.4.12, 2.4.13 e 3.3.9. A conferência normativa do W3C confirma esses critérios e seus níveis. [WCAG 2.2](https://www.w3.org/TR/wcag/) |
| 14 | Transcrição torna uma imagem de texto aceitável para 1.4.9 | SPEC §5.6:1202; ROADMAP H24:1376–1378 | Falsa. WCAG 1.4.9 exige que imagens de texto sejam apenas decorativas ou essenciais; transcrição, sozinha, não é exceção. [W3C — 1.4.9](https://www.w3.org/WAI/WCAG21/Understanding/images-of-text-no-exception) |
| 15 | Links inline são a única questão de 2.5.5 | SPEC §5.6:1210 | Incompleta: alvos não inline ainda precisam de 44×44 CSS px, salvo outras exceções. O portão não mede isso. [W3C — 2.5.5](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced) |
| 16 | H4 cobre as dívidas necessárias ao sidecar | ROADMAP H4:434–463 | Falsa como garantia: o portão enumera sete sintomas, mas deixa o defeito de `Rect` fora da contagem obrigatória. |
| 17 | A varredura por lista de permissão impede dados de máquina em XHTML | SPEC R2.4:490–502; ROADMAP H24:1369–1375 | Não demonstrado: R2.4(c) permite todos os atributos já presentes no XHTML do projeto, inclusive atributos com nomes como `data-confidence` ou `data-engine`. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE `ROADMAP` H24:1344–1345 e SPEC R2.4:478–489. O QUE a spec corrigiu a opcionalidade da proveniência, mas H24 ainda afirma que o IR tem proveniência em todo nó. COMO CONFERIR criar um nó autoral com `provenance=None` e executar H24. POR QUE REPROVA: o documento contém contratos incompatíveis sobre o que deve entrar no sidecar.

2. ONDE `SPEC` R2.4:495 e `ROADMAP` H24:1372. O QUE a lista de permissão aceita atributos XHTML por igualdade com o projeto, enquanto R2.4 proíbe confiança, motor e notas de OCR no EPUB. COMO CONFERIR inserir `data-confidence`, `data-engine` ou `data-note` num XHTML do projeto e rodar a varredura. POR QUE REPROVA: a própria regra de permissão pode aprovar dados de máquina que a regra de privacidade proíbe.

3. ONDE `SPEC` §2.7:370 e `ROADMAP` H4:434–463. O QUE o defeito real `list(Rect)` continua sendo engolido por `book.py:209–212`, mas o portão H4 não exige que ele seja corrigido. COMO CONFERIR exportar um documento com `Rect` real e verificar se o sidecar é produzido e contém o retângulo. POR QUE REPROVA: H24 pode declarar sidecar completo enquanto o exportador silenciosamente não grava sidecar algum.

4. ONDE `SPEC` R5:643–646 e `ROADMAP` H7:620–640. O QUE a guarda de execução nomeia `os.replace` como evento separado. COMO CONFERIR instalar o gancho nos Python 3.10 e 3.11 e chamar `os.replace`; o evento observado é `os.rename`. POR QUE REPROVA: se implementado literalmente, o caminho atômico usado pelos escritores pode escapar da guarda arquitetural.

5. ONDE `SPEC` §5.6:1202 e `ROADMAP` H24:1376–1382. O QUE o plano trata “imagem de texto com transcrição” como suficiente para 1.4.9. COMO CONFERIR publicar uma imagem contendo texto não essencial, mas com transcrição. POR QUE REPROVA: o EPUB pode passar no portão e ainda violar o critério AAA.

6. ONDE `SPEC` §5.6:1195–1217 e `ROADMAP` H10:754–764/H24:1376–1384. O QUE a tabela enumera todos os AAA, mas os portões não verificam efetivamente 2.5.5, 2.1.3, formulários classificados como inexistentes, nem todas as condições de 2.4.12/2.4.13. COMO CONFERIR inserir link não-inline pequeno, `<form>` ou CSS que remova o foco. POR QUE REPROVA: “todos os AAA aplicáveis” vira uma afirmação não demonstrada.

7. ONDE SPEC §7 Q7:1297 e §5.6:1219–1224. O QUE a recomendação padrão aceita AA e admite não cumprir 3.1.5, embora o pedido do usuário tenha solicitado nível AAA. COMO CONFERIR executar o plano sem responder Q7. POR QUE REPROVA: H19/H24 ficam sem critério de produto definido e a interpretação do requisito do usuário é alterada sem decisão explícita.

## Defeitos não bloqueantes

- As contagens de `janela.py` continuam corretas: HEAD e árvore têm 2.077 linhas; a árvore permanece suja por trabalho externo.
- A tabela histórica do ciclo 4 está consistente com os quatro bloqueantes anteriores.
- H27 continua opcional e não bloqueia o núcleo MuPDF.
- Referências de linha futura podem mudar se cada portão registrar o arquivo e o commit efetivamente executados.

## O que especificamente precisa mudar para eu aprovar

- Corrigir H24 para dizer que a proveniência é opcional e definir igualdade campo a campo do sidecar.
- Tornar a correção de `Rect` um requisito explícito de H4 ou H24, com fixture positiva.
- Fazer a varredura rejeitar atributos XHTML de proveniência gerada, ou definir formalmente por que atributos arbitrários do usuário não são dados de máquina.
- Documentar e implementar a guarda usando o evento `os.rename` para cobrir `os.replace`, com canonicalização segura dos caminhos.
- Corrigir o tratamento de 1.4.9 e acrescentar portões reais para 2.5.5, foco, formulários e demais critérios classificados como “por construção”.
- Responder Q7 antes de liberar H19/H24, mantendo AAA formal se esse for o requisito do produto.
## Documentos — ciclo 6 (2026-09-23): REPROVADO, 4 bloqueantes

Do ciclo 5: 5 resolvidos, 2 parciais (1 e 6). O que a versão 1.6 mudou está na spec §9 (tabela do ciclo 6). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 6  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 5 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Proveniência no EPUB | PARCIAL | A opcionalidade foi corrigida e o H24 exige comparação campo a campo, mas “sidecar completo” não define todos os campos atuais (`note`, `model_hash`, `verified_by_human`, `model_name`, hashes da fonte etc.). Spec R2.4:472–493; `export/provenance.py:84–126`. |
| 2 | Atributos de proveniência no XHTML | RESOLVIDO | R2.4(c) agora reprova explicitamente `data-confidence`, `data-engine`, `data-note` etc., mesmo se escritos pelo usuário. Spec:499–509; roadmap H24:1411–1418. |
| 3 | `Rect` do sidecar | RESOLVIDO | H4 tornou os itens 1, 2 e 10 obrigatórios e exige fixture positiva com `Rect` real do importador. Roadmap H4:434–465. |
| 4 | Escrita direta fora do serviço | RESOLVIDO | A redação foi corrigida para auditar `os.rename`, que é o evento emitido por `os.replace`; a canonização também foi especificada. Spec:649–661; roadmap H7:639–645. |
| 5 | Tratamento de imagens de texto | RESOLVIDO | A transcrição agora substitui a imagem; `alt` sozinho não é aceito. Spec §5.6:1217; roadmap H24:1421–1423. Isso está coerente com o [WCAG 1.4.9](https://www.w3.org/WAI/WCAG21/Understanding/images-of-text-no-exception). |
| 6 | Portões para os critérios AAA | PARCIAL | Foram acrescentados vários portões, mas 1.4.8 não cobre seleção de cores e 2.4.12/2.4.13 ainda são inferidos por proxies insuficientes. Spec:1214–1225; roadmap H19:1193–1199 e H24:1429–1432. |
| 7 | Q7 sem decisão/padrão implícito | RESOLVIDO | Q7 agora tem a opção (iv), não tem padrão e bloqueia H19/H24. Spec:1302–1313; roadmap §1:147–152. Conforme solicitado, a ausência de resposta do usuário não é defeito. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | `IRNode.provenance` é opcional (R2.4) | `core/model/base.py:53–63` | Confirmada: pode ser `None`. |
| 2 | H4 exige os itens 1, 2 e 10 | Roadmap H4:434–465 | Confirmada. |
| 3 | H24 força `embed_ir=False` | Roadmap H24:1405–1406; spec R2.4:476–478 | Confirmada como requisito futuro e portão; não é comportamento atual. |
| 4 | `os.replace` emite `os.rename` | Execução nos Python 3.10.11 e 3.11.9 | Confirmada. Em ambos: `os.rename(path_a, path_b, -1, -1)`; nenhum evento `os.replace`. |
| 5 | `os.open(..., O_CREAT|O_EXCL|O_WRONLY)` emite `open` | Execução nos dois Python | Confirmada: evento `open(path, None, 1409)`. A operação foi tentada em caminho inexistente; o sandbox bloqueou a criação, mas o evento foi emitido antes da falha. |
| 6 | 1.4.6 usa 7:1 e 4,5:1 para texto grande | Spec §5.6:1214 | Confirmada pelo [WCAG 1.4.6](https://www.w3.org/WAI/WCAG21/Understanding/contrast-enhanced). |
| 7 | 1.4.9 não aceita transcrição somente no `alt` | Spec §5.6:1217 | Confirmada pelo [W3C](https://www.w3.org/WAI/WCAG21/Understanding/images-of-text-no-exception). |
| 8 | 2.5.5 exige 44×44 para alvos fora de linha | Spec §5.6:1225; roadmap H24:1431–1432 | Parcial: a regra é conservadora, mas não registra as exceções de alvo equivalente, controle do agente do usuário e apresentação essencial previstas pelo [WCAG 2.5.5](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced). |
| 9 | 2.4.13 é provado por contorno de 2 px e contraste 3:1 | Spec:1224; roadmap H19:1197–1199 | Não confirmada: o WCAG exige também área mínima equivalente ao perímetro de 2 px; um indicador interno/inset de 2 px pode falhar. Ver [W3C 2.4.13](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance). |
| 10 | 2.4.12 é provado proibindo `fixed/sticky` | Spec:1224; roadmap H24:1429–1430 | Não confirmada: `fixed/sticky` são causas comuns, não teste suficiente de que nenhum conteúdo autoral encobre o componente focado. Ver [W3C 2.4.12](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-enhanced). |
| 11 | 3.1.5 é atendido com resumo suplementar | Spec:1229; roadmap H24:1435–1436 | Conceitualmente confirmada, mas o plano é mais estrito que o WCAG: o critério exige conteúdo suplementar quando o texto requer nível avançado, não necessariamente um resumo em todos os capítulos. Ver [W3C 3.1.5](https://www.w3.org/WAI/WCAG21/Understanding/reading-level.html). |
| 12 | A árvore e o HEAD têm 2.077 linhas em `janela.py` | Tronco, `git show HEAD:...` e árvore atual | Confirmada: ambos retornam 2.077; a árvore está modificada pelos trabalhos da aba Texto. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE spec R2.4:482–493 e roadmap H24:1407–1410. O QUE o sidecar é chamado de “completo”, mas o contrato enumera apenas parte da proveniência; ficam sem obrigação explícita `note`, `model_hash`, `verified_by_human`, `model_name`, `content_hash`, `image_hash`, `dpi` e demais campos do modelo atual. COMO CONFERIR criar uma fixture com todos esses campos em `proveniencia.json` e comparar o conjunto e os valores dos campos do sidecar. POR QUE REPROVA: o portão pode passar enquanto dados necessários à auditoria são perdidos.

2. ONDE spec §5.6:1216 e roadmap H19:1193–1196. O QUE o “tema Leitura AAA” mede cinco condições, mas omite a primeira exigência do WCAG 1.4.8: mecanismo para selecionar cores de primeiro plano e fundo. COMO CONFERIR usar um EPUB com cores fixadas no CSS, sem mecanismo de seleção e sem garantia declarada do agente leitor; executar H19/H24. POR QUE REPROVA: a opção Q7(iv) pode declarar AAA formal sem satisfazer todos os requisitos de [1.4.8](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation).

3. ONDE spec §5.6:1224 e roadmap H19:1197–1199/H24:1429–1430. O QUE 2.4.12/2.4.13 são reduzidos à ausência de `fixed/sticky`, `outline:none` e existência de `a:focus-visible` com 2 px/3:1. COMO CONFERIR inserir overlay `position:absolute`, foco com indicador `outline-offset` negativo ou indicador interno de 2 px, e medir todos os links focáveis renderizados. POR QUE REPROVA: esses proxies podem aprovar foco encoberto ou indicador com área insuficiente; o WCAG 2.4.13 exige área mínima além do contraste.

4. ONDE spec §5.6:1227 e roadmap H24:1433. O QUE a ação implementada cobre apenas NAG e figurinas, embora a própria tabela inclua “jargão”. COMO CONFERIR publicar termos como “zugzwang”, “oposição” ou “fortaleza” sem definição e executar o portão. POR QUE REPROVA: [WCAG 3.1.3](https://www.w3.org/WAI/WCAG21/Understanding/unusual-words.html) exige mecanismo para identificar definições de palavras incomuns e jargão, não apenas símbolos.

## Defeitos não bloqueantes

- A regra de 2.5.5 é mais restritiva que o WCAG por não modelar todas as exceções; isso tende a gerar falso reprovar, não falso aprovar.
- O H24 ainda depende de implementação futura do exportador e do sidecar; isso está explicitamente tratado como trabalho de H4/H24.
- As referências de linha futura podem mudar se cada portão registrar o commit efetivamente executado.
- A ausência de resposta a Q7 não é defeito: o roadmap bloqueia corretamente H19/H24.

## O que especificamente precisa mudar para eu aprovar

- Definir o esquema completo e fechado do sidecar, incluindo todos os campos de `Provenance`, `DiagramSource` e decisões; exigir fixture positiva campo a campo.
- Acrescentar ao H19/H24 o mecanismo de seleção de cores de 1.4.8 ou declarar formalmente a dependência de um agente EPUB que o forneça.
- Substituir os proxies de foco por teste renderizado de todos os componentes: ausência de encobrimento, área mínima do indicador e contraste entre estados focado/não focado.
- Cobrir 3.1.3 com glossário ou definições de todas as palavras incomuns/jargões usados, não somente NAG e figurinas.
- Atualizar a tabela do ciclo 5 para refletir que os bloqueantes 1 e 6 continuam PARCIAIS.
## Documentos — ciclo 7 (2026-09-23): REPROVADO, 4 bloqueantes

Do ciclo 6: 1 resolvido (1.4.8), 3 parciais. O que a versão 1.7 mudou está na spec §9 (tabela do ciclo 7). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 7  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 6 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Sidecar completo e fechado | PARCIAL | Spec R2.4:490–502 e Roadmap H24:1419–1426 adicionam introspecção, mas §5.2:931 ainda mostra um `proveniencia.json` reduzido. O código possui `Provenance` completo (`core/model/provenance.py:108–149`), objetos aninhados em `RecognitionResult` (`core/model/diagram.py:200–215`) e decisões em `Decided`/`AuditEntry`/`DiagramDecision` (`ocr/review.py:115–123,439–465`; `ocr/diagram_decisions.py:77–102`), sem mapeamento fechado. |
| 2 | WCAG 1.4.8, seleção de cores | RESOLVIDO | Spec §5.6:1225 e H19:1193–1202 especificam as cinco exigências e teste com folha do usuário. C23/C25 são técnicas suficientes para deixar as cores do conteúdo principal sob controle do usuário; o mecanismo pode ser fornecido pelo agente leitor. [W3C 1.4.8](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation) |
| 3 | WCAG 2.4.12/2.4.13 | PARCIAL | A prova renderizada foi acrescentada (Spec §5.6:1233; H19:1203–1211; H24:1445–1447), mas cinco chamadas a `elementFromPoint` não provam que nenhuma parte do componente esteja encoberta. Também falta definir o arnês DOM/teclado/pixels no artefato produzido por H1. |
| 4 | WCAG 3.1.3, jargão | PARCIAL | O glossário agora cobre símbolos e termos do léxico revisado (Spec §5.6:1236; H24:1450–1452), mas o portão mede apenas termos previamente listados. Ele não demonstra que todo termo usado de modo incomum ou restrito foi identificado. [W3C 3.1.3](https://www.w3.org/WAI/WCAG21/Understanding/unusual-words.html) |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | `janela.py` tem 2.077 linhas no HEAD | Spec A.3:1473–1480 | Confirmada: `git show HEAD:...` = 2.077; árvore de trabalho também = 2.077. A árvore continua modificada nos arquivos informados pelo usuário. |
| 2 | H1 precede H19 | Roadmap §1:128,147; H19:1203–1204 | Confirmada formalmente, mas o H1 só especifica PNG e caminhos de DLL; não especifica a interface de medição que H19 precisa. |
| 3 | Proveniência é opcional por nó | Spec R2.4:480–482 | Confirmada em `core/model/base.py:53–63`: `IRNode.provenance` pode ser `None`. |
| 4 | O sidecar atual registra apenas diagramas e partidas | Spec §2.3; `export/provenance.py:84–153` | Confirmada. O comportamento atual ainda não é o sidecar novo proposto. |
| 5 | `Provenance` tem todos os campos prometidos pelo esquema | R2.4:490–499 | Não conferida: o modelo inclui `document_path`, `document_hash`, `block_index` e `out_of_model` (`provenance.py:134–149`), ausentes da lista textual de campos proibidos em R2.4(d):515–518. |
| 6 | `DiagramSource` e `RecognitionResult` entram inteiros | R2.4:493–499; H24:1419–1425 | Parcial: os campos de topo estão identificados, mas `FenCandidate` e `SquareRepair`, aninhados, não são nomeados nem exigidos explicitamente. |
| 7 | As cinco exigências do 1.4.8 estão cobertas | Spec §5.6:1225; H19:1193–1202 | Confirmada, inclusive a solução C23/C25 de não fixar as cores principais. |
| 8 | O teste de 2.4.13 mede a área mínima correta | Spec §5.6:1233; H19:1206–1208 | Parcial: o critério exige área equivalente ao perímetro de 2 px do componente não focado, além de contraste; o documento não define cálculo geométrico completo. [W3C 2.4.13](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance) |
| 9 | O teste de 2.4.12 é garantido por ausência de `fixed`/`sticky` | Spec §5.6:1233; H24:1445–1447 | Falsa como garantia suficiente: são proxies, não prova de ausência de sobreposição autoral. [W3C 2.4.12](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-enhanced) |
| 10 | 100% do léxico usado implica 100% do jargão coberto | Spec §5.6:1236; H24:1450–1452 | Não confirmada: termos fora do léxico podem aparecer e passar sem definição. |
| 11 | `embed_ir=False` já é comportamento existente | R2.4:477–479; H24:1417–1418 | Falsa no estado atual; é requisito futuro testado por espião. |
| 12 | A guarda de escrita cobre `os.replace` | Spec R5:658–669; H7:639–645 | Confirmada: a redação corrigiu corretamente para o evento `os.rename`. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE Spec §5.2:931, R2.4:490–499 e Roadmap H24:1419–1426. O QUE o “esquema fechado” não define o formato exato dos registros, nem quais classes de decisão e objetos aninhados entram; além disso, o exemplo do `proveniencia.json` continua reduzido. COMO CONFERIR montar uma fixture com `Provenance`, `DiagramSource`, `RecognitionResult`, `FenCandidate`, `SquareRepair`, `Decided`, `ReviewItem`, `AuditEntry` e `DiagramDecision`, com todos os campos preenchidos, e comparar o JSON relido campo a campo. POR QUE REPROVA: uma implementação literal ainda pode perder campos e passar no teste superficial de conjuntos.

2. ONDE Spec R2.4(c–d):508–518 e Roadmap H24:1430–1434. O QUE a lista de nomes proibidos não corresponde a todos os campos reais por introspecção; faltam, entre outros, `document_path`, `document_hash`, `block_index`, `out_of_model`, `rotation_degrees`, `extractor_version`, `orientation_confidence` e `model_version`. COMO CONFERIR inserir esses nomes como atributos XHTML e como texto em OPF/CSS/SVG. POR QUE REPROVA: dados de máquina ou de origem podem entrar no EPUB enquanto o portão declara privacidade garantida.

3. ONDE Spec §5.6:1233 e Roadmap H19:1203–1211/H24:1445–1447. O QUE cinco amostras de `elementFromPoint` não provam “nenhuma parte” encoberta; o H1 também não define o mecanismo para foco por teclado, captura dos dois estados e análise dos pixels. COMO CONFERIR colocar um overlay fino na borda do link, fora das cinco amostras, ou usar um link multilinha, e executar a prova no mesmo artefato Chromium do H1. POR QUE REPROVA: o portão pode aprovar uma violação de 2.4.12 e uma área de foco menor que o perímetro exigido.

4. ONDE Spec §5.6:1236 e Roadmap H24:1450–1452. O QUE o portão garante apenas que termos do léxico estão definidos, não que todo jargão ou expressão incomum do livro foi identificado. COMO CONFERIR inserir um termo especializado fora do léxico, sem adicioná-lo manualmente, e executar H24. POR QUE REPROVA: o livro pode declarar AAA apesar de não haver mecanismo para identificar a definição de um termo usado de forma restrita.

## Defeitos não bloqueantes

- A ausência atual de QtWebEngine e Windows Sandbox está explicitamente registrada como pré-condição de H1, não como defeito documental.
- Q7 sem padrão e bloqueando H19/H24 é coerente; exige decisão do usuário.
- A regra conservadora de 2.5.5 pode gerar falso reprovar, mas não falso aprovar.
- As referências de linha futura podem mudar quando os passos forem executados, desde que o relatório registre o commit medido.

## O que especificamente precisa mudar para eu aprovar

- Definir o JSON fechado do sidecar, incluindo namespaces, versão, migração e todas as classes/objetos aninhados; atualizar o exemplo de §5.2.
- Gerar e testar a lista proibida completa por introspecção, inclusive nos atributos XHTML e em todos os recursos publicados.
- Transformar a prova de foco em teste de cobertura geométrica completa, com área calculada contra o componente não focado e arnês explicitamente fornecido pelo H1.
- Fazer o portão de 3.1.3 exigir um inventário revisado de todos os termos incomuns/restritos presentes, não apenas os que já aparecem no léxico.
## Documentos — ciclo 8 (2026-09-23): REPROVADO, 3 bloqueantes

Do ciclo 7: 1 resolvido (a lista proibida), 3 parciais. O que a versão 1.8 mudou está na spec §9 (tabela do ciclo 8) e nos Apêndices C e D. O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 8  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 7 — situação

| # | bloqueante | situação | evidência |
|---|---|---|---|
| 1 | Sidecar completo e fechado | PARCIAL | As dez classes e três tipos de registro foram nomeados (`SPEC` R2.4:490–506; `S2`:953–959; `ROADMAP` H24:1438–1449), mas não há formato canônico completo nem migração 1→2 campo a campo. O código atual ainda usa `kind: header/diagram/game` (`src/caissa/export/provenance.py:41–70,98–153`). |
| 2 | Lista proibida por introspecção | RESOLVIDO | A lista agora é recursiva, cobre `snake_case`/`kebab-case`, posições estruturadas e exceções fechadas (`SPEC` R2.4:517–540; `ROADMAP` H24:1450–1463). |
| 3 | WCAG 2.4.12/2.4.13 | PARCIAL | A prova geométrica e o arnês foram acrescentados (`SPEC`:1261; `ROADMAP` H1:293–313, H19:1218–1230), mas faltam contratos operacionais de serialização DOM, viewport, escala, foco assíncrono e análise de pixels. |
| 4 | WCAG 3.1.3, jargão | PARCIAL | O inventário, decisões e atestação foram acrescentados (`SPEC`:1264; `ROADMAP` H24:1479–1483), mas não há garantia de identificar palavras comuns usadas como jargão fora do léxico e não marcadas pelo usuário. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---|---|---|---|
| 1 | As dez classes do sidecar existem | `core/model/diagram.py:96,129,145,170`; `core/model/provenance.py:72,108`; `ocr/review.py:61,116,440`; `ocr/diagram_decisions.py:78` | CONFIRMADA |
| 2 | O registro de partida atual está em `export/provenance.py:140–153` | `src/caissa/export/provenance.py:140–153` | CONFIRMADA, mas o formato atual é `kind: game`, não o novo `tipo: partida`; a migração não está especificada. |
| 3 | A API Chromium proposta é viável para `getClientRects`, `elementsFromPoint` e captura | `ROADMAP` H1:293–306; `.venv-pack` | PARCIAL: as primitivas do navegador são adequadas, mas `QtWebEngineWidgets` e `QtWebEngineCore` não existem no ambiente atual; a execução real depende do H1. |
| 4 | Spec e roadmap definem o mesmo sidecar exato | `SPEC` R2.4/S2; `ROADMAP` H24:1438–1449 | PARCIAL: a estrutura de alto nível coincide, mas faltam tipos, campos obrigatórios/opcionais, omissão de defaults e mapeamento v1→v2. |
| 5 | A lista proibida cobre os campos reais | `dataclasses.fields()` nas dez classes; `SPEC` R2.4:528–540 | CONFIRMADA no papel: inclui campos reais como `document_path`, `document_hash`, `rotation_degrees`, `model_version` e `out_of_model`. |
| 6 | A prova de foco cobre geometricamente links multilinha e overlays | `SPEC`:1261; `ROADMAP` H1:304–306, H19:1218–1230 | PARCIAL: há bons casos de sabotagem, mas o contrato não define conversão DOM→JSON, recorte/viewport, DPR, limiar de diferença de pixels ou pseudo-elementos. |
| 7 | O inventário humano fecha o 3.1.3 | `SPEC`:1264; `ROADMAP` H24:1479–1483,1514–1516 | PARCIAL: atesta decisões dos candidatos encontrados, não a completude do inventário do texto inteiro. |
| 8 | A contagem de `janela.py` é 2.077 no HEAD e na árvore | `SPEC` §2.5:279–285; `(git show HEAD:<caminho>).Count` | CONFIRMADA: HEAD e árvore atual têm 2.077 linhas; a árvore do tronco continua suja nos arquivos declarados. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE `SPEC` R2.4:490–506, S2:953–959 e `ROADMAP` H24:1438–1449. O QUE o “formato exato” do sidecar ainda não fecha a representação concreta dos registros, objetos aninhados, defaults, campos obrigatórios e migração do formato atual. COMO CONFERIR criar um golden fixture independente com todas as dez classes e comparar o JSONL esperado, incluindo uma fixture v1 migrada para v2. POR QUE REPROVA: um leitor e escritor podem passar no round-trip entre si e ainda perder ou renomear dados de auditoria; o portão pode aprovar um formato incompatível.

2. ONDE `SPEC` §5.6:1261 e `ROADMAP` H1:293–313/H19:1218–1230/H24:1474–1476. O QUE a “cobertura completa” ainda não define como DOMRects e elementos serão serializados, como pixels fora do viewport serão tratados, como CSS pixels serão convertidos para pixels capturados, nem como o indicador será isolado de outras mudanças visuais. COMO CONFERIR executar o arnês com link multilinha parcialmente fora da viewport, `devicePixelRatio` diferente, overlay absoluto e pseudo-elemento cobrindo a borda, além de foco interno de área insuficiente. POR QUE REPROVA: o portão pode declarar conformidade 2.4.12/2.4.13 enquanto aceita foco encoberto ou indicador menor que o mínimo exigido.

3. ONDE `SPEC` §5.6:1264 e `ROADMAP` H24:1479–1483. O QUE o inventário detecta símbolos, léxico, palavras desconhecidas pelo dicionário e marcações explícitas, mas não garante detectar uma palavra comum empregada como jargão restrito fora do léxico. COMO CONFERIR inserir uma palavra comum usada com sentido técnico de xadrez, fora do léxico e sem marcação do usuário, e verificar se o inventário e a atestação humana a registram. POR QUE REPROVA: o produto pode declarar AAA sem oferecer mecanismo para identificar e definir todo jargão usado de forma incomum.

## Defeitos não bloqueantes

- `ROADMAP` H4:492–493 contém corrupção textual (`benchmarks` + caractere de controle); o caminho pretendido parece ser `benchmarks\reports\editor\h4\antes\`. É corrigível antes da execução do passo.
- O `Rect` ainda causa `TypeError` no código atual (`export/provenance.py:87`), mas H4 exige fixture positiva com `Rect` real e sabotagem específica (`ROADMAP`:451–497); não é falha documental remanescente.
- A ausência atual de QtWebEngine e Windows Sandbox está explicitamente tratada como pré-condição do H1.
- Q7 continua sem resposta, mas isso está corretamente modelado como decisão do usuário que bloqueia H19/H24.

## O que especificamente precisa mudar para eu aprovar

- Fechar o esquema v2 do sidecar com exemplos canônicos, tipos, obrigatoriedade, defaults, tags dos objetos aninhados e mapeamento explícito do sidecar v1 atual.
- Transformar o arnês de foco em contrato executável: serialização dos resultados JS, viewport/scroll, DPR, conversão de coordenadas, captura, limiar de diferença e tratamento de overlays/pseudo-elementos.
- Fazer o 3.1.3 exigir atestação de cobertura do texto inteiro, incluindo revisão humana de termos comuns usados como jargão fora do léxico.
- Corrigir o caminho corrompido do H4.
## Documentos — ciclo 9 (2026-09-23): REPROVADO, 3 bloqueantes

Do ciclo 8: o 3.1.3 e o caminho do H4 resolvidos; o sidecar parcial; o arnês não resolvido. O que a versão 1.9 mudou está na spec §9 (tabela do ciclo 9). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 9  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 8 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Sidecar v2 canônico | **PARCIAL** | Os nomes das dez dataclasses conferem com `dataclasses.fields()`. Porém, a spec manda usar `as_dict()` para decisões (`SPEC:502–504`), enquanto `ReviewItem.as_dict()` arredonda `score` (`ocr/review.py:102–112`) e `AuditEntry.as_dict()` arredonda `seconds` (`ocr/review.py:125–128`), contradizendo `SPEC:1553–1558`, que exige preservação sem arredondamento. As fixtures douradas também ainda não existem no checkout. |
| 2 | Arnês WCAG 2.4.12/2.4.13 | **NÃO RESOLVIDO** | As primitivas existem: `runJavaScript(worldId)` retorna dados simples de forma assíncrona e `QTest.keyClick` é suportado pelo Qt ([QWebEnginePage](https://doc.qt.io/qt-6/qwebenginepage.html), [QTest](https://doc.qt.io/qt-6/qtest.html)). Mas `SPEC D:1646–1648` aplica `elementsFromPoint` também à região do indicador. Um `outline` válido é pintura CSS, não descendente DOM; a fixture positiva de `outline: 2px` (`D:1653–1655`, `H1:313–314`) tende a ser acusada como encoberta. |
| 3 | WCAG 3.1.3, jargão | **RESOLVIDO** | A leitura integral por capítulo está explicitamente exigida em `SPEC:1267` e `ROADMAP:1491–1497,1624`, e só é necessária para declarar o 3.1.3. O limite humano está corretamente declarado. |
| H4 | Caminho corrompido | **RESOLVIDO** | `ROADMAP:500` contém `benchmarks\reports\editor\h4\antes\`; a varredura dos documentos encontrou zero caracteres BEL (`0x07`). |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | As dez classes e seus campos (`SPEC C:1564–1575`) | `dataclasses.fields()` no `.venv-pack` | **CONFIRMADA quanto aos nomes**: todos os campos listados coincidem. |
| 2 | Nenhuma das dez classes tem etiqueta no IR (`SPEC C:1560–1562`) | `registry.py` e decorators | **FALSA**: seis têm etiquetas: `provenance`, `rect`, `diagram_source`, `fen_candidate`, `square_repair`, `recognition_result`; quatro não têm. |
| 3 | Mapeamento v1→v2 (`SPEC C:1593–1609`) | `export/provenance.py:41–153` | **PARCIALMENTE CONFIRMADO**: `VERSION=1`, cabeçalho, diagramas e partidas correspondem em grande parte; porém o v1 atual ainda faz `list(provenance.rect)` em `:87`, incompatível com `Rect` real, e a migração não define completamente `extras_v1`. |
| 4 | Todos os campos presentes e sem arredondamento (`SPEC C:1553–1558`) | `ocr/review.py:102–128` | **CONTRADITÓRIA**: `as_dict()` arredonda valores, enquanto o contrato canônico proíbe arredondamento. |
| 5 | Contrato do arnês Chromium (`SPEC D`, `ROADMAP H1`) | primitivas Qt e coerência dos testes | **PARCIAL**: as APIs citadas existem, mas o teste de encobrimento conflita com a fixture positiva de `outline`. |
| 6 | Atestação integral só para declarar 3.1.3 | `SPEC:1267`, `ROADMAP:1494–1497,1624` | **CONFIRMADA e coerente** entre spec e roadmap. |
| 7 | Contagem de `janela.py` | `git show HEAD:src/chess_diagram_ocr/qt/janela.py` e árvore | **CONFIRMADA**: HEAD 2.077; árvore 2.077. |
| 8 | Caminho H4 corrigido | bytes do roadmap e `ROADMAP:500` | **CONFIRMADA**. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE `SPEC C:1553–1562,1593–1617` e `ROADMAP:1450–1458`. O QUE o sidecar usa uma semântica canônica incompatível com os `as_dict()` existentes e ainda depende de fixtures douradas que não estão presentes. COMO CONFERIR instanciar `ReviewItem(score=0.123456)` e `AuditEntry(seconds=1.2345)`, serializar pelos `as_dict()` atuais e comparar com a regra de `repr` sem arredondamento; conferir que `tests/fixtures/editor/sidecar/*.jsonl` não existe. POR QUE REPROVA: uma implementação literal pode arredondar ou perder dados de auditoria, e o portão byte a byte não possui ainda um oráculo independente congelado.

2. ONDE `SPEC D:1637–1650` e `ROADMAP H1:293–314`. O QUE a regra de `elementsFromPoint` inclui a área pintada do indicador, embora `outline` não seja elemento DOM. COMO CONFERIR executar a fixture positiva `outline: 2px solid` e observar que pontos fora do retângulo do link não retornam o link/descendente. POR QUE REPROVA: o arnês pode reprovar um indicador de foco válido; se a área for excluída para fazê-lo passar, deixa de testar encobrimento nessa região.

3. ONDE `SPEC:1267` e `ROADMAP:1494–1497,1624`. O QUE a atestação de leitura não está vinculada ao conteúdo revisado: não há hash ou versão do capítulo nem regra de invalidação após edição. COMO CONFERIR atestar um capítulo, alterar seu texto e executar H24 sem refazer a leitura. POR QUE REPROVA: o portão pode declarar 3.1.3 para texto que não foi integralmente revisado.

## Defeitos não bloqueantes

- `SPEC C:1561–1562` contém a afirmação factual errada sobre etiquetas do IR; as etiquetas existentes coincidem com as desejadas, então a correção textual não muda a saída.
- O `TypeError` de `Rect` em `export/provenance.py:87` está corretamente coberto como pré-requisito pelo H4.
- As referências a linhas futuras podem ser registradas pelo relatório do passo, conforme a regra do ciclo 9.

## O que especificamente precisa mudar para eu aprovar

- Separar explicitamente o serializador canônico do sidecar dos `as_dict()` arredondadores, ou eliminar os arredondamentos; definir etiquetas via registry quando existirem; fechar tipos, enums, `Any` e `extras_v1`.
- Criar e congelar, antes da implementação, `v2_completo.jsonl`, `v1_de_hoje.jsonl`, `v1_migrado_esperado.jsonl` e seus SHA-256.
- Corrigir o algoritmo do arnês para não tratar a pintura do indicador como elemento DOM encobridor e definir medição para `outline`, `box-shadow` e pseudo-elementos.
- Vincular cada atestação de capítulo ao hash da versão revisada e invalidá-la quando o conteúdo mudar.
## Documentos — ciclo 10 (2026-09-23): REPROVADO, 2 bloqueantes

Do ciclo 9: o 3.1.3 resolvido; o sidecar e o arnês parciais. O que a versão 1.10 mudou está na spec §9 (tabela do ciclo 10). O veredito, transcrito sem edição:

VEREDITO: REPROVADO  
CICLO: 10  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 9 — situação

| # | bloqueante | situação | evidência |
|---:|---|---|---|
| 1 | Sidecar v2 canônico | PARCIAL | A spec agora define serializador próprio, etiquetas, tipos, `extras_v1` e fixtures independentes (`SPEC` C:1562–1640; `ROADMAP` H3:448–465, H24:1461–1474). Porém, o cabeçalho exige `gerado_em` e `gerador.commit_da_suite` (`SPEC` C:1601), ambos variáveis. O código atual usa `datetime.now()` (`src/caissa/export/provenance.py:65–70`) e o commit corrente (`:182–186, 201–207`). |
| 2 | Arnês WCAG 2.4.12/2.4.13 | PARCIAL | A máscara corrige o falso positivo de `outline` e `box-shadow` (`SPEC` D:1666–1687; `ROADMAP` H1:313–318). Contudo, a isolamento preserva ancestrais do link; pseudo-elementos de `body`/`html` não são ocultados. |
| 3 | WCAG 3.1.3, jargão | RESOLVIDO | A atestação agora contém SHA-256 do texto normalizado por capítulo e vence após edição (`SPEC` §5.6:1270; `ROADMAP` H24:1507–1513, 1547–1549). |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---:|---|---|---|
| 1 | Seis das dez classes têm `@ir_node` e etiquetas citadas (C:1574–1577) | `core/model/registry.py:40–69,93–109`; `provenance.py:70–108`; `diagram.py:94–169` | CONFIRMADA: `provenance`, `rect`, `diagram_source`, `fen_candidate`, `square_repair`, `recognition_result`. As quatro classes de decisão não estão registradas. |
| 2 | `ReviewItem.as_dict` arredonda `score` | `ocr/review.py:102–112` | CONFIRMADA: `round(self.score, 4)`. |
| 3 | `AuditEntry.as_dict` arredonda `seconds` | `ocr/review.py:125–128` | CONFIRMADA: `round(self.seconds, 2)`. |
| 4 | O serializador canônico não usa esses `as_dict()` | `SPEC` R2.4:502–507, C:1571–1581; `ROADMAP` H24:1466–1470 | COERENTE: a correção está explicitamente documentada; a implementação ainda não existe, como esperado. |
| 5 | As fixtures douradas são criadas no H3 e consumidas no H24 | `ROADMAP` H3:448–465; dependências: linha 131; H24:1461–1474 | CONFIRMADA. A ausência atual das fixtures não é defeito. |
| 6 | A máscara não acusa o indicador pintado e acusa sobreposição | `SPEC` D:1666–1678; `ROADMAP` H1:313–318 | PARCIAL: funciona para elementos externos ocultáveis, mas não para pseudo-elementos de ancestrais. |
| 7 | Atestação presa ao hash do capítulo | `SPEC` §5.6:1270; `ROADMAP` H24:1510–1513 | CONFIRMADA e coerente; a sabotagem `edita_depois_de_atestar` cobre a invalidação. |
| 8 | Contagem de `janela.py` distingue HEAD e árvore | `SPEC` §2.5:279–285, Apêndice A.3:1532–1539 | CONFIRMADA: `git show HEAD` = 2.077 linhas e árvore atual = 2.077; `Measure-Object` produz 1.808 por ignorar vazias. |

## Defeitos bloqueantes (novos ou remanescentes)

1. ONDE `SPEC` C:1601, 1634–1640 e `ROADMAP` H3:448–465/H24:1466–1474. O QUE a fixture dourada é congelada por SHA-256 e comparada byte a byte, mas inclui `gerado_em` e o commit da suíte, valores variáveis entre execuções e entre H3 e H24. COMO CONFERIR gerar a fixture no H3, fazer outro commit ou esperar alguns segundos e exportar o mesmo documento; a linha do cabeçalho muda. POR QUE REPROVA: o portão necessariamente falha ou precisa ignorar campos dinâmicos sem contrato; em ambos os casos a garantia byte a byte é falsa. Definir relógio/commit injetáveis e valores fixos da fixture, ou excluir esses campos da comparação byte a byte e testá-los por invariantes.

2. ONDE `SPEC` D:1671–1678 e `ROADMAP` H1:313–318. O QUE a renderização isolada esconde elementos que não são link, ancestral ou descendente; portanto, `body::after` ou `html::before` que cubra o contorno continua presente tanto em `M_iso` quanto em `M_real`. COMO CONFERIR usar `box-shadow: 0 0 0 4px` no foco e um `body::after` absoluto, com `z-index`, cobrindo uma faixa da borda. `position:absolute` não é proibido pelo portão atual. POR QUE REPROVA: a sobreposição fica invisível para `M_iso \ M_real`, e o livro pode ser aprovado como 2.4.12 conforme apesar de o indicador estar parcialmente encoberto. Ocultar/testar pseudo-elementos de ancestrais e adicionar essa sabotagem ao H1/H19/H24.

## Defeitos não bloqueantes

- `SPEC` §9:1475 diz “cinco fixtures”, mas o Apêndice D e o H1 especificam seis. Corrigir a redação.
- O exemplo abreviado do sidecar não mostra `extras_v1`, embora C:1606–1607 o exija; a regra normativa está clara.
- O `TypeError` atual de `Rect` permanece coberto pelo H4, que exige a correção e a fixture positiva.
- A ausência atual do arnês e das fixtures é esperada: são artefatos criados por H1/H3.

## O que especificamente precisa mudar para eu aprovar

- Tornar determinísticos `gerado_em` e `gerador.commit_da_suite` nas fixtures, ou retirar ambos da comparação byte a byte com validações independentes.
- Corrigir a máscara para tratar pseudo-elementos e pintura de ancestrais; adicionar um caso de sobreposição via `body::after`/`html::before`.
- Corrigir “cinco” para “seis” no histórico da spec.


## Documentos — ciclo 11 (2026-09-23): APROVADO

Os dois bloqueantes do ciclo 10 resolvidos. Os dois não bloqueantes foram tratados na versão final: a neutralização da máscara prova que venceu o CSS do autor (spec Apêndice D), e o histórico do roadmap §9 foi posto em ordem cronológica. O veredito, transcrito sem edição:

VEREDITO: APROVADO  
CICLO: 11  
FRENTE: Editor HTML/CSS — documentos (spec + roadmap)

## Bloqueantes do ciclo 10 — situação

| # | bloqueante | situação | evidência |
|---|---|---|---|
| 1 | Cabeçalho dinâmico impedindo fixture byte a byte | RESOLVIDO | Spec Apêndice C:1644–1653 define relógio/commit injetáveis, valores fixos e invariantes reais. Roadmap H24:1470–1481 repete o contrato. O HEAD ainda confirma o comportamento antigo em `src/caissa/export/provenance.py:65–70,182–207`, que será substituído pelo H24. |
| 2 | Máscara não detectava pseudo-elementos de ancestrais | RESOLVIDO | Spec Apêndice D:1692–1704 neutraliza pseudo-elementos de ancestrais, incluindo `html`/`body`, e pintura `outline`/`box-shadow`. Fixture (6):1714–1715 e Roadmap H1:313–321/H19:1253–1257/H24:1563 exigem que `body::after` seja acusado. |

## Afirmações conferidas

| # | afirmação (doc §) | conferida em | resultado |
|---|---|---|---|
| 1 | O cabeçalho atual usa `datetime.now()` e o commit corrente | `src/caissa/export/provenance.py:65–70,182–207` no HEAD `99546e9` | CONFIRMADA |
| 2 | Relógio e commit injetáveis permitem fixture determinística, mantendo teste dos valores reais | Spec C:1644–1653; Roadmap H24:1470–1478 | COERENTE |
| 3 | A máscara isolada neutraliza pseudo-elementos e pintura ancestral, sem tratar `outline` como elemento DOM | Spec D:1687–1704; Roadmap H1:313–321 | COERENTE |
| 4 | A sabotagem `pseudo_do_body` é exercitada em H1, H19 e H24 | Roadmap H1:318–321, H19:1253–1257, H24:1561–1563 | CONFIRMADA |

## Defeitos bloqueantes (novos ou remanescentes)

1. Não há bloqueante novo ou remanescente. Os dois defeitos do ciclo 10 têm contrato positivo, sabotagem específica e verificação coerente entre spec e roadmap.

## Defeitos não bloqueantes

- O mecanismo exato para garantir que a CSS de neutralização vença regras autorais com `!important` poderia ser explicitado; o portão existente já exige a sabotagem ancestral correspondente.
- O roadmap §9 lista historicamente o ciclo 10 antes do ciclo 9; é apenas redação histórica.

## O que especificamente precisa mudar para eu aprovar

- Nada bloqueante. A 1.10 pode avançar para execução dos passos H1/H3/H24.