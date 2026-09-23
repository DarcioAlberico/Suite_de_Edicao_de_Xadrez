# OCR/UI · ciclo 2 — relatório do construtor (fase 5: o texto que some sem aviso, a tabela lida por coluna, a janela que não cabe, e a régua do `.pt`)

> **Data:** 2026-09-23 · **Plano:** `docs/OCR_UI_ROADMAP_C2.md` §3d (fase 5: B13, B14, B15, A14,
> C17, C18, A15 — definida nesta sessão a partir do `sol.json` da fase 4 e das dívidas medidas) ·
> **Fases anteriores:** `OCR_UI_REPORT_C2.md`, `…_FASE2.md`, `…_FASE3.md`, `…_FASE4.md` ·
> **Papel:** construtor. Todo número traz o comando ao lado. Ambiente: suíte `.venv` (Python
> 3.11.9), tronco `..\ChessVisionOFF_Puro` (3.10), RTX 5060. O tronco estava no ramo do PR #35
> (`claude/campo-lance-no-resultado`, outra sessão) e voltou a `religa-as-decisoes-orfas`, o ramo
> das fases do ciclo 2, antes de qualquer mudança (o commit do PR continua no ramo dele).
> **Contenção:** as primeiras filas do `bench_sol`, a régua do C17, a suíte do tronco e a checagem
> de população do B14 correram em paralelo nesta máquina; a fila final de A/B (§0.2) correu quase
> sozinha (no meio dela, o arnês do C18 e testes unitários curtos). Os tempos (`s/MP`,
> `s/execução`) desses JSON carregam a contenção e são ditos com ela. O `sol.json` publicado foi
> medido no commit da fase (§A15) — com outra sessão rodando a suíte do tronco ao mesmo tempo: os
> CER e as decisões não dependem de carga (o `f5_before` reproduziu a fase 4, medida sozinha, item
> a item), o `s/MP` depende. Commits: tronco `36d6f65` (código) e `8243e90` (os quatro relatórios de campo
> remedidos); suíte `bb41c55` (código e documentos) e o seguinte (o `sol.json` medido no `bb41c55`, e este relatório fechado). **Outra sessão** trabalhava no tronco durante a integração
> (`qt/janela.py`, `qt/painel_de_texto.py`, `text/rico.py`, `ui/texto_declarado.py` modificados a
> partir das 05:27): não entram nos commits desta fase, e as medições do tronco feitas depois disso
> rodaram numa árvore limpa do commit.
>
> **Ciclo 2 do crítico** (§0.4). O ciclo 1 reprovou com três bloqueantes (o B13 embaralhando uma
> página real de colunas estreitas, a janela que cabia escondendo conteúdo, a coluna «≤ 0 errados»
> do C17); os consertos, a remedição e este relatório revisto estão no tronco `53dd066` e, na
> suíte, no `4fc0f4d` (código, documentos e evidência) e no seguinte (o `sol.json` medido no
> `4fc0f4d`, e este relatório fechado). As medições do ciclo 2 correram com a fila de A/B, a população do B14 e os testes do
> tronco em paralelo: os tempos carregam a contenção, os CER e as decisões não (a fila refeita dá
> os 747 itens da primeira, item a item).
>
> **Ciclo 3 do crítico** (§0.5). O ciclo 2 reprovou com dois bloqueantes (o B13 intercalando as
> duas colunas de um índice real sem prosa, e a reserva da mensagem do rodapé esvaziando as zonas
> de dispositivos e de ocupação); os consertos estão no tronco `885149d` e na suíte `3ff1830` (código e
> testes) e no seguinte (a fila de A/B e o `sol.json` medidos no `3ff1830`, a evidência e este
> relatório fechado).
>
> **Ciclo 4 do crítico** (§0.6). O ciclo 3 reprovou com um bloqueante (o B13 juntando, linha a
> linha, uma coluna de notas comuns e a lista de lances da outra coluna, e o importador aceitando a
> página embaralhada); os consertos estão no tronco `7cd400a` (só docstrings) e na suíte `7736617`
> (código, testes, a transcrição do ciclo 3) e no seguinte (a fila de A/B e o `sol.json` medidos
> nele, e este relatório fechado).
>
> **Ciclo 5 do crítico** (§0.7). O ciclo 4 reprovou com dois bloqueantes (o B13 intercalando as
> colunas de um índice quando a página tinha duas calhas ou mais e nenhuma prosa — páginas reais
> do acervo, e três colunas compostas **aceitas** trocadas —, e a ordem do Tab da Revisão de texto
> existindo só na cadeia do foco: com a tecla, o Tab parava no campo da verdade escrevendo
> tabulações); os consertos estão no tronco `37f662b`, `4f3e218` e `7a78367` e na suíte `b6978ec`
> (código, testes, a transcrição do ciclo 4) e no seguinte (a fila de A/B e o `sol.json` medidos
> nele, os portões no commit, e este relatório fechado).

## §0 — Em uma tela (o que o usuário passa a ter)

| antes | depois | portão | passo |
|---|---|---|---|
| uma tabela a 150 DPI e a lista de lances de duas colunas saíam **por coluna** — todos os nomes, depois todos os lugares; todos os lances das brancas, depois os das pretas —, com 100 % dos caracteres certos e CER 0,47–0,68 | os blocos do Tesseract lado a lado cujas linhas casam são lidos **por linha**, dentro da coluna da página — através da calha da página (achada com prosa de um lado, em faixas de largura comparável ou, de duas calhas, a vizinha da prosa; e, desde o ciclo 4 do crítico, antes de toda coluna de índice e entre uma partida e o texto) só uma lista de lances passa —, e nunca juntando texto corrido (prosa por comprimento, por palavras, notas de variantes ou, desde o ciclo 3 do crítico, linhas que continuam a frase, poucas palavras que tenham), duas numerações de lance, nem dois blocos com uma palavra de fora entre eles | `bench_sol`: `scan_degraded_150` CER **0,0224 → 0,0094** — o portão absoluto de 150 DPI do Sol, vermelho desde a fase 1, **verde**; `table:2/4/7` 0,465/0,640/0,676 → 0,0035/0,0036/0; nativos do Dvoretsky 0,590/0,381/0,347 → 0,051/0/0; `two-column` idêntico; 7 itens mudam, nenhum para pior (a regra final dá os 747 itens da primeira); páginas reais: a Gallagher de colunas estreitas, que a primeira regra levava de 0,2732 a **0,7042** pelo importador, vai a **0,2028**, e as pp. 51–53 ficam idênticas; o índice da Karpov 2 p. 268, que a regra do ciclo 2 intercalava (0,76), sai idêntico ao desligado; as notas comuns ao lado da partida, que a regra do ciclo 3 juntava e o importador **aceitava** (0,0052 → 0,6440), saem idênticas ao desligado; os índices reais que o crítico achou intercalados (ciclo 4) — a Flores pp. 460–464 pelo importador 0,6708/0,7224/0,0230/0,7117/0,4949 → **0,0438/0,0853/0,0230/0,0202/0,0364**, a Nunn p. 288 digitalizada 0,3212 → **0,0193**, três colunas compostas idênticas ao desligado — e a franja do texto corrido, **0 de 41** páginas em risco embaralhadas (o ciclo 4, 24); 280 páginas reais varridas (a Gallagher inteira e as páginas finais de nove livros): a leitura desligada igual à do ciclo 4 em 279, a ligada mudando em 6, as seis para melhor; a Estrin inteira (88, em alemão), 25 da Gunderam e 22 da Kmoch com as duas leituras iguais às do ciclo 4, e os índices reais do crítico (29 páginas) com 3 mudanças para melhor e 1 igual; sabotagem `table_rows=false` → os números da fase 4 | B13 |
| a leitura que perdia o fim de toda linha, ou linhas inteiras, saía **aceita** (a foto `synth:Dvoretsky…:201:21` aceita a 0,872 com CER 0,786), e as variantes que a leriam não rodavam | a fração das letras da região sob as palavras lidas (`ocr/coverage.py`): abaixo de 0,90 as variantes rodam mesmo com o original aceito, a leitura incompleta não ancora, e nunca sai `ACCEPTED`; a moldura escura do scanner não cega a medida, e a região que ela não julga é dita no rastro | aceitos com CER > 0,10 **30 → 7** (nenhum estrato sobe, nenhum entra): 18 lidos inteiros pela variante, 5 para a revisão; `photo` CER **0,0983 → 0,0207**; 27 itens mudam, nenhum para pior; população real pelo importador — 429 regiões de três livros do construtor e 95 de oito livros do crítico — sem sinalizar leitura boa; a Kmoch com moldura, de 0 letras a 1.058; piso ajustado só na `calib`, o desempate dito; sabotagem `ink_coverage=false` → os 30 | B14 |
| o fax a 0,0382 pelo instrumento honesto da fase 4 | absorvido pelo B14, sem rota própria | `fax_dither` **0,0382 → 0,0249** (≤ 0,0312) | B15 |
| o nível 0, o leiaute por página e o índice de busca liam a camada de texto com as ligaduras (`ﬁ`: 19 nas pp. 6–10 do Polgar) | as bandeiras do PyMuPDF sem `TEXT_PRESERVE_LIGATURES` nos três leitores — a caixa por caractere dividida junto | 19 → **0** nos três; `½ ² №` ficam; sabotagem (bandeiras antigas) → a ligadura volta | A14 |
| a decisão do `.pt` (§10.2) comparava modelos num gate fixo — duas escalas de confiança | a curva risco × cobertura do campo para 15 checkpoints, e o máximo de exatos exportados com ≤ 0/1/2 errados | a produção reproduz o `field_exact` publicado (103 exportados, 102 exatos) e, com zero errados, exporta **74** (portão 0,998) — o «≤ k errados» calculado em todo valor distinto de confiança; sabotagem (rótulos embaralhados sobre as mesmas linhas) → AURC pior em todo modelo e a ordem dos modelos a tau +0,31 | C17 |
| com as áreas visitadas e um livro, a janela pedia **1538×659** lógicos — a barra de anotação somava 810 px e uma frase do rodapé pedia 1.246 | rodapé elidido (a frase inteira na dica) com até 320 px garantidos à mensagem (~57 caracteres) e os dispositivos e a ocupação inteiros até 240 px, barra do campo fluida, os modos da aba Livro e o cartão da Revisão de texto em rolagem **com barra quando precisa**, e as fileiras de botões que descem de linha (Revisão de texto, cartão, Rotulagem, navegação da Galeria) | `caissa.ui.audit.minimo`: Clássica 1248×606, Foco **1248×640**, Fita 1246×629 ≤ 1250×640, com e sem livro, **e à vista** no mínimo e a 1366×728 — nenhum controle fora da vista sem barra, nenhum espremido, as **quatro zonas** do rodapé à vista com a linha cheia, para o nome mais longo e um comum (mensagem 320, documento 272–288, dispositivos 135, ocupação 171 px, para os dois nomes, medidas na linha do arnês, no mínimo): PASSOU; as cinco sabotagens (rodapé em `QLabel` → 3318 px; rolagens sem barra; mensagem sem piso → 0 px; o botão das mensagens com o piso de 1 px → 1/82 px; a reserva do ciclo 2 → dispositivos e ocupação com 0 px) REPROVARAM, e a sexta, `linha` (o produto reescrevendo o rodapé sem parar), também — ela achou que a medida se dizia «na linha do arnês» sem a linha ter assentado; o teclado com a **tecla** (ciclo 5 do crítico: a cadeia do foco não bastava): na Revisão de texto e na Rotulagem o Tab anda da tabela à última ação e de volta, cada controle à vista, e o portão aperta a tecla nos dois sentidos em toda área — PASSOU em sete das oito áreas e nos catorze diálogos, nas três peles e a 1280×800, 1248×640 e 1280×641, com o foco à vista nos dois sentidos, e REPROVOU na «Folha transcrita» do Texto, arquivo de outra sessão (§0.3); as ações da Revisão de texto à vista a 1280×641 | C18 |
| três invariantes com exceção em todo relatório: `AccentTests` vermelho, `ImpressaoDaMedicaoTests` com `--deselect`, `test_arquitetura` à parte | acentos por posição (nenhuma palavra permitida a mais, e sem as seis brechas que o crítico construiu nos ciclos 1 e 2; as oito do ciclo 3 escapam: a varredura julga cada literal pela posição dele, não segue o dado — §A15), a afirmação do arnês num processo novo (e o import quebrado dito como quebrado), os quatro relatórios de campo remedidos no commit | suíte: **4.032 passaram, 0 reprovaram** com o `test_arquitetura` na mesma corrida; tronco numa árvore limpa: 4.789 passaram e o único reprovado é o do ambiente, por construção da árvore efêmera; `ImpressaoDaMedicaoTests` **sem `--deselect`**; `AccentTests` verde | A15 |

### 0.1 O que a medição mudou no desenho (as armadilhas, cada uma medida)

- **Uma fila de A/B com um interruptor novo no meio.** A primeira fila do B13 (`on` e `off`)
  começou com o B14 ainda não escrito; o segundo processo, que nasceria depois de o B14 existir,
  teria o B14 **ligado** do lado `off` — a comparação mediria duas coisas. Parado e refeito: toda
  corrida da fase carrega o `SOL_CONFIG` explícito de **todos** os interruptores da fase
  (`{"table_rows": …, "ink_coverage": …}`), e a fila inteira roda no código final.
- **A semente pequena parte a tabela.** A primeira versão do B13 semeava os grupos na ordem de
  leitura; no `table:4` a 150 DPI as duas células de uma linha só da última fila (`Haia 1937`,
  `Eslava`) formaram um grupo próprio e a linha saiu partida (CER 0,033). Semeando pela coluna de
  células mais alta, 0,0036.
- **O corpus não mostra a página inteira.** Os itens de tabela do corpus são recortes: a regra do
  B13 que passava neles puxou uma coluna para o meio da outra nas páginas inteiras de duas colunas
  do Levenfis (p. 41 com similaridade 0,290 com o desligado). A primeira calha que resolveu isso
  contava **toda** linha da página — e desfez o `table:4` (0,0036 → 0,64), porque nada cruza o vão
  entre as colunas de uma tabela. A regra final conta só prosa; as duas medições vieram antes da
  fila final de A/B (§B13).
- **A altura da Foco não era de quem o comentário dizia.** A rolagem do cartão da Revisão de texto
  veio com um comentário que lhe atribuía os 640 px da Foco; descendo pelo filho mais alto de cada
  nível, quem os segura é a Galeria do tronco (516 px) — a Foco mede 640 antes e depois da rolagem.
  Comentário corrigido, Galeria nomeada (§C18).
- **A cobertura da tinta foi sequestrada duas vezes antes do benchmark** (revisão do próprio
  construtor, com imagens sintéticas — o corpus não tem estes casos, os livros têm): (1) uma foto
  em **meio-tom** (milhares de pontos de 5 px) fez a mediana de altura cair aos pontos e as letras
  virarem «grandes demais» — cobertura 0,009 numa página lida inteira; (2) uma foto de **tom
  contínuo** com manchas do tamanho de letra — 0,64–0,72. Depois: letra medida em polegadas
  (o teto físico do B11, 0,25 pol), tinta só em **linhas** de texto (letras esfregadas duas
  alturas-x na horizontal formando corridas largas, não mais altas que uma linha, e densas) e cada
  letra pesando um — 1,00 nos dois casos, e a leitura que perdeu 3 de 5 linhas continua em 0,40.
  O primeiro A/B do B14 (com a medida ingênua) foi descartado; o piso foi reajustado na `calib`
  com a medida final.
- **A premissa do A14 estava errada pela metade.** A fase 4 escreveu «o texto da camada de texto
  continua com ligaduras»; o extrator do importador (`textlayer._text_flags`) sempre leu com
  `TEXT_PRESERVE_LIGATURES` desligada, e o IR do Polgar já saía limpo. Os que ainda liam com as
  bandeiras padrão eram outros três: o motor de nível 0 (cujo `recognize_page` nem passa pela
  dobra do B12 — 6 ligaduras na p. 6 do Polgar, 5 na p. 9), as linhas de leiaute da página e o
  índice de busca.
- **O mínimo da janela depende de quais áreas já foram visitadas.** A recusa do `capture --escala`
  (fase 4, 1248×695) é medida antes de as áreas serem mostradas; com as áreas visitadas e um
  livro aberto a janela pedia **1538×659**. O motor da largura não era o visor: era a barra de
  anotação sob ele (`PainelDeCampo`, combo + três botões numa `QHBoxLayout`, 810 px na pele Foco);
  e a frase do rodapé num `QLabel` comum pedia 1.246 px sozinha.
- **Um arnês que sai por `os._exit` deixa órfão o processo de trabalho do tronco.** As sondas e o
  arnês do C18 saem sem desmontar a janela (fechar com a leitura do Dataset viva derruba o
  interpretador: `access violation` no `close`, medido); o filho `spawn` do
  `processo_de_trabalho` não morre com o pai no Windows — seis órfãos vivos, e um deles segurou a
  medição seguinte do portão por minutos. O arnês encerra o processo de trabalho (`encerrar(esperar=True)`)
  antes de sair.
- **O arnês da janela morria no retorno da medida** (ciclo 2). Com a máquina ocupada (a fila de
  A/B e a população do B14 ao lado), quatro de dez corridas do portão perderam uma pele em `access
  violation` antes de gravar o JSON; o `PYTHONFAULTHANDLER` pôs as quatro no retorno de
  `medir_uma_pele`, com a tarefa do Dataset esperando o processo de trabalho. A `QApplication`
  criada ali era uma variável local: o Python a soltava na volta e o PyQt a desmontava com a tarefa
  viva. Prender só a janela não bastou (a quarta morte veio depois disso); presas a aplicação e a
  janela até o `os._exit` (`minimo._VIVOS`), duas corridas completas das seis medidas (sem livro,
  com livro e as quatro sabotagens) saíram sem nenhuma morte e iguais entre si. E o filho órfão de
  uma pele morta segura o `stdout` que herdou: uma fila que lia o portão por `| grep` ficou minutos
  parada esperando um fim de arquivo que não vinha — as corridas passaram a gravar direto em
  arquivo.
- **A linha cheia do rodapé não pode depender do instante** (ciclo 2). O portão estendido achou o
  botão «Mensagens» com 27 de 82 px com o livro aberto porque, naquele instante, a importação do
  Kemeri ainda corria e punha a ocupação e a barra na linha. Uma medida que depende de a importação
  estar correndo não é medida: o arnês põe a linha cheia ele mesmo (`minimo._linha_cheia`: o nome
  de 149 caracteres, a frase de 300 e uma operação com a barra) antes de ler o mínimo e a vista,
  com e sem livro.

### 0.2 Invariantes e portões rodados na integração

| invariante / portão | resultado | comando |
|---|---|---|
| fila final de A/B do `bench_sol` no código final (6 estratos, 747 itens, quatro corridas em sequência, cada uma com o `SOL_CONFIG` dos **dois** interruptores; commit de base `f9ca678` + a árvore da fase) | `f5_on` (os dois ligados), `f5_b13_off`, `f5_b14_off`, `f5_before` (os dois desligados): o `f5_before` reproduz o `sol.json` da fase 4 **item a item** (diferença pareada 0 em todos os estratos e leiautes, os mesmos 30 aceitos errados, os mesmos portões) — os dois interruptores explicam toda a diferença, e o A14 não toca o corpus; 11–13 min por corrida. **Ciclo 2:** a fila refeita no código final (`scratchpad/bench_f5c2.sh`: `f5c2_on`, `f5c2_b13_off`, `f5c2_b14_off`, mesmo comando e os mesmos interruptores) dá os 747 itens **idênticos** aos da primeira, corrida a corrida (`f5c2_on` = `f5_on`, `f5c2_b13_off` = `f5_b13_off`, `f5c2_b14_off` = `f5_b14_off`, em CER e decisão): a regra nova do B13 e a moldura do B14 não mudam nenhum item do corpus — o que mudam está nas páginas reais. Evidência versionada: `docs/quality/sol/f5_ab.json` (por item, o CER, a decisão e o `answered` de cada corrida -- a média de cada estrato se refaz dos itens --; o resumo, os portões, o commit e o código não commitado de cada uma). **Ciclo 3:** a fila refeita no commit do código do ciclo 3 (`3ff1830`, `dirty_code` vazio; `scratchpad/bench_f5c3.sh`, as três corridas em paralelo) dá os 747 itens idênticos aos dos ciclos 1 e 2, em CER, decisão e todo campo numérico por item (o texto, os JSON só o guardam dos itens com CER acima de 0,05). **Ciclo 4:** a fila refeita no commit do código do ciclo 4 (`7736617`, `dirty_code` vazio; `scratchpad/c4/bench_f5c4.sh`, as três corridas em paralelo, com a máquina quieta) dá os 747 itens idênticos aos dos ciclos 1, 2 e 3 em todo campo por item que não é tempo — e, nos 70 itens de que o JSON guarda o texto, no texto (`c4/cmp_ab_c4.py`); o B13 muda os mesmos 7 itens e o B14 os mesmos 27, nenhum para pior; aceitos errados 7; `f5_ab.json` com as onze corridas. **Ciclo 5:** a fila refeita no commit do código do ciclo 5 (`b6978ec`, `dirty_code` vazio; `scratchpad/c5/bench_f5c5.sh`, as três corridas em paralelo, com os portões da janela ao lado) dá os 747 itens idênticos aos do ciclo 4 em todo campo por item que não é tempo, salvo um: o `real:Dvoretsky…:17:401:52` do `native`, cuja confiança relatada vai de 0,56 a 0,4884 — a do B13 desligado: o B13 movia as linhas dessa lista antes de ela ser pontuada, e a concordância agora é medida na ordem do motor; o CER (0,05128) e a decisão (revisão) não mudam. O B13 muda os mesmos 7 itens e o B14 os mesmos 27, nenhum para pior; aceitos errados 7; o 150 DPI em 0,0094; `f5_ab.json` com as catorze corridas (`c5/cmp_ab_c5.py`) | `scratchpad/bench_f5c.sh` (`CAISSA_FIGURINE_TESSDATA=models\tessdata`, `SOL_CONFIG='{"table_rows": …, "ink_coverage": …}' .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo --label <corrida>`); comparação `scratchpad/cmp_f5.py` |
| portões do Sol em `f5_on` | silenciosas **0**, controles **0/9**, ordem **1,0000**, ambiente reproduz; CER 150 DPI **0,0094 ≤ 0,020 ✓** (vermelho desde a fase 1); CER limpo 0,0113, lances 0,9164, inventados 157 — vermelhos (§0.3) | o próprio `bench_sol` |
| B13 em página real (ciclo 3: a regra final, com as varreduras do crítico) | **280 páginas** (a Gallagher inteira, 176, e as páginas finais de nove livros raster, 104): 43 mudam (ciclo 2: 46), e a leitura ligada é a do ciclo 2 em 275 -- as pp. 267, 268, 270 e 271 da Karpov 2 (índice) passam a idênticas ao desligado, e a Levenfis p. 302 (sumário) melhora — CER 0,1221 → 0,0738 contra a transcrição do crítico —, com 3 dos 6 títulos junto da sua página e as páginas dos outros três depois da última entrada; a Karpov 2 p. 268 pelo importador, idêntica ao desligado | `scratchpad/c3/varre.sh` (`…\_critico_f5\c2\b13_varredura.py`, quatro filas), `cmp_varre.py` |
| B13 em página real (ciclo 5: o código final, as sondas e as varreduras do crítico) | as sondas do crítico com o código final (`c5/sondas3.sh`; importador sem `CAISSA_FIGURINE_TESSDATA`): a Flores pp. 460–464 0,6708/0,7224/0,0230/0,7117/0,4949 → 0,0438/0,0853/0,0230/0,0202/0,0364, a Yusupov 4 p. 206 0,0465 = desligado, a Nunn p. 288 0,3212 → 0,0193, a p. 289 0,0174, a Aagaard *Matter* pp. 892/893 0,0958/0,0769, o `tres.pdf` idêntico ao desligado nas quatro páginas; o que o crítico mandou manter igual ao ciclo 4 — o `construido.pdf`, a Karpov 2 p. 268 (JSON igual), a Gallagher p. 50 em 0,2028, as tabelas do ciclo 2 (aberturas 0,0113), as páginas estreitas, a lista tabulada e a de avaliações separadas; a franja do texto corrido 0 de 41 páginas embaralhadas (o ciclo 4, 24); as três notas inglesas pelo importador idênticas ao desligado. As varreduras: as 280 páginas do crítico (a Gallagher inteira e as páginas finais de nove livros) com a leitura **desligada** igual à do ciclo 4 em 279 — a 280ª, a Stean p. 165, é a que a máquina sem memória degradou no ciclo 4, e voltou (item 3(d)) —; a ligada muda em **6**, as seis para melhor contra a ordem do livro: a Flores pp. 460–464 (o índice: linhas que juntam dois verbetes 7/17/31/2/7 no ciclo 4, 0/0/0/0/1 agora, e os nomes subindo em ordem — 3 descidas em 69 verbetes, 2 em 78, 2 em 78, 2 em 78 e 2 em 48) e a Gallagher p. 128 (o ciclo 4 juntava o ruído de um diagrama à prosa, «ae Hil aa now has a decisive blow. 25 Hed 1-0»; ela sai agora como com a regra desligada, o ruído em linhas dele e a prosa inteira); o B13 muda 41 das 280 do desligado (o ciclo 4, 43: a p. 462 da Flores e a Gallagher p. 128 deixam de mudar); a Estrin inteira em `deu+eng` (88 páginas), 25 da Gunderam (pp. 10–58) e 22 da Kmoch (pp. 10–52), rasterizadas a 300 DPI, com as duas leituras iguais às do ciclo 4 em todas as 135 (e mais 7 da Gunderam e 4 da Kmoch sem par no ciclo 4, que a varredura deste ciclo cobriu até o fim: o B13 não muda nenhuma); e os índices reais do ciclo 4 do crítico (Karpov 1 pp. 392–400, Aagaard *Matter* pp. 890–895, Yusupov 4 pp. 200–207, Nunn pp. 284–289; 29 páginas, pelo serviço, sem o B14): a leitura desligada igual à do crítico em todas; a ligada muda em 4 — três para melhor (Karpov 1 p. 398, 1 linha de dois verbetes no ciclo 4 e nenhuma agora; Yusupov 4 p. 206, 37 → 0; Nunn p. 288, 42 → 0, as três agora iguais ao desligado) e uma igual (Aagaard p. 893: o número da página, «893», sai numa linha dele no fim, e não colado ao título). A concordância nos dois sentidos, medida antes e descartada: nas 268 páginas da primeira etapa, 7 leituras desligadas mudaram — 5 para pior (Karpov 2 pp. 267/272 e Vladimirov pp. 380/384/385, o RapidOCR intercalando colunas), 1 para melhor (Stean p. 154) e 1 igual (Aagaard p. 190) | `scratchpad/c5/sondas3.sh`, `c5/varre.sh`, `c5/cmp_varre_c5.py` (o diff de cada página que muda em `c5/varre_diffs/`), `c5/cer_flores.py`, `c5/descidas.py`; a concordância nos dois sentidos, descartada: `c5/varre_simetrica/`, `c5/cmp_varre_simetrica.out` |
| B13 em página real (ciclo 4: a regra final, as sondas e as varreduras do crítico) | as sondas do crítico: `construido.pdf` pp. 0–3 pelo importador idênticas ao desligado (0,0052 `accepted`, 0,2284, 0,0367, 0,0754; duas execuções), `b13_estreita3.py --justificar` 0,0140/0,0087 em inglês e 0,2132/0,0152 em alemão (300/200 DPI), `b13_tabulada.py` 0,0140/0,0157/0,0140, notas reais de cinco livros 0 de 6; a Karpov 2 p. 268, a Gallagher pp. 50–53 (p. 50 em 0,2028), a Reinfeld 1977 p. 319 e a Levenfis p. 134 pelo importador com o texto de cada região igual ao do ciclo 3; as tabelas do ciclo 2 como no ciclo 3 (as aberturas 0,0113). As varreduras do crítico: **280 páginas**, a leitura ligada igual à do ciclo 3 nas 280 (43 mudam do desligado; a Stean p. 165 aparece como 44ª só porque a leitura **desligada** desta corrida saiu pior — outra variante escolhida, com a máquina sem memória; a desligada não passa pelo `rows.py`; o mecanismo, medido no ciclo 5: o RapidOCR falhando na alocação, §0.7 item 3(d)); a Estrin inteira em `deu+eng` (88 páginas), 25 da Gunderam (pp. 10–58) e 22 da Kmoch (pp. 10–52), raster 300 DPI: a leitura ligada igual à do ciclo 3 nas 135 (a Gunderam e a Kmoch interrompidas por memória) | `scratchpad/c4/sondas.sh`, `c4/varre.sh` (`…\_critico_f5\c2\b13_varredura.py` e `c3\b13_varredura3.py`), `c4/cmp_varre_c4.py`, `c4/cmp_importador.py`, `c4/cer_construido.py` |
| B13 em página real (ciclo 2) | Levenfis pp. 36–52 **15 de 17** idênticas, Estrin pp. 20–27 7 de 8, Stefaniu pp. 40–47 8 de 8, Kmoch pp. 28, 40, 44, 48 e 68 5 de 5, Gallagher pp. 48–55 7 de 8 (a p. 50 com a lista de lances por linha); pelo importador, a Gallagher pp. 50–53: p. 50 CER 0,2732 → **0,2028** contra a transcrição do crítico, pp. 51–53 idênticas; as três páginas construídas pelo crítico idênticas ao desligado; nenhum grupo atravessa a calha | `scratchpad/b13_c2_all.sh` → `b13_c2_all2.log` (`probe_b13_pages.py <pdf> <páginas> <lang>` e o `b13_importador.py` do crítico, com `CAISSA_FIGURINE_TESSDATA` fora do ambiente) |
| B14 na população real, pelo importador (código final) | construtor: Estrin pp. 20–27 (79 regiões medidas, a menor 0,919), Levenfis pp. 40–51 (240, a menor 0,931) e Stefaniu pp. 40–51 (110, a menor **0,900**) — nenhuma das 429 sinalizada. As contagens diferem das 504 do ciclo 1 em dois lugares: a Estrin do ciclo 1 foi medida com o classificador de diagramas indisponível (a `CAISSA_FIGURINE_TESSDATA` no ambiente, que o importador recusa — o log daquela corrida diz isso); e a p. 49 do Stefaniu saiu então em 83 regiões do tamanho de uma linha e sai hoje em 9 de parágrafo — a corrida de 04:15 mediu um `rows.py` intermediário, anterior ao commit do ciclo 1 (o log dela registra 96 regiões fundidas no Stefaniu), e o código commitado, o do ciclo 1 (`99546e9`) e o final, dá 9: as 83 eram daquela regra, e o número do ciclo 1 não se refaz com código commitado (crítico, ciclo 2); crítico (a sonda `b14_populacao.py` dele, os mesmos oito livros e páginas do ciclo 1): 95 regiões medidas, 6 sinalizadas — todas já em revisão ou abstenção, 5 delas ruído lido dentro de diagrama (Reinfeld ×3, Karpov, Vladimirov) e a Gallagher p. 50 (0,896, a página de colunas estreitas, CER 0,20); nenhuma leitura boa sinalizada. Kmoch com a moldura do scanner, rasterizada a 300 DPI: 0 → 1.058/1.162/995 letras, 55 regiões medidas, nenhuma sinalizada (a menor 0,953) | `scratchpad/b14_final.sh` (`b14_moldura_final.py` e `…\_critico_f5\b14_populacao.py`) |
| C17 régua do campo | 15 checkpoints × 3 execuções, linhas idênticas nas três; produção 103/1 no gate = `field_exact`; com zero errados, 74; sabotagem tau +0,31. Evidência versionada: `docs/quality/campo/f5_c17_regua.json` (as linhas por diagrama, o resumo e a sabotagem) | `benchmarks\model_ruler.py --runs 3 --tag f5_c17`; ciclo 2: `--linhas-de …_f5_c17.json --tag f5_c17_c2` e `--sabotar embaralhar --linhas-de …` |
| `sol.json` publicado no commit da fase | ciclo 5: republicado sobre o **`b6978ec`**, sem `SOL_CONFIG` e com `dirty_code` vazio: os 747 itens idênticos aos da `f5c5_on` em todo campo por item que não é tempo (o publicado não grava o texto; `c5/cmp_ab_c5.py`); aceitos errados 7; `sol_gate --report-only` sem regressão fora do IC, os mesmos três absolutos bloqueados e o de 150 DPI verde (`c5/sol_gate_c5.out`); 787 s. Ciclo 4: republicado sobre o **`7736617`**, sem `SOL_CONFIG` e com `dirty_code` vazio: os 747 itens idênticos aos da `f5c4_on` em todo campo por item que não é tempo (o publicado não grava o texto); aceitos errados 7; `sol_gate --report-only` sem regressão fora do IC, os mesmos três absolutos bloqueados e o de 150 DPI verde; 836 s. Ciclo 3: republicado sobre o **`3ff1830`**, sem `SOL_CONFIG` e com `dirty_code` vazio: os 747 itens idênticos aos do `sol.json` do ciclo 2 e aos da `f5c3_on`, em CER e decisão; aceitos errados 7; `sol_gate --report-only` sem regressão fora do IC, os mesmos três absolutos bloqueados e o de 150 DPI verde; 741 s. Ciclo 2: republicado sobre o **`4fc0f4d`**, sem `SOL_CONFIG`: os 747 itens idênticos aos do `sol.json` do ciclo 1 e aos da `f5c2_on`, em CER e decisão; aceitos errados 7; `sol_gate --report-only` sem regressão fora do IC, os mesmos três absolutos bloqueados e o de 150 DPI verde; 698 s. Ciclo 1: `bb41c55`, sem `SOL_CONFIG`: 747 itens idênticos aos da `f5_on`; `sol_gate --report-only` sem regressão fora do IC; os três absolutos do §0.3 bloqueados, o de 150 DPI verde (§A15) | `bench_sol … --label sol --publish`; `sol_gate.py --report-only docs\quality\sol\sol.json` |
| C18, ciclo 5: a linha assentada nas duas passadas, e o teclado com a tecla | no `b6978ec` contra o tronco `7a78367`, os dois sem nada fora do commit (o JSON grava os dois): o portão da janela PASSOU sem livro e com o Kemeri (1248×606 / 1248×640 / 1246×629; no mínimo, mensagem 320, documento 272–288, dispositivos 135, ocupação 171 px), com a linha reposta pelo arnês quando o produto a reescreveu, na passada da vista e na do rodapé (uma vez cada na corrida sem livro); as seis sabotagens REPROVARAM (`rodape` 3318 px; `corte` 3 controles fora da vista sem barra; `mensagem` 0–6 px; `aperto` 8 espremidos; `reserva` dispositivos e ocupação com 0–2 px; `linha` as oito áreas medidas fora da linha do arnês nas duas larguras, e o rodapé também). A pergunta antiga sobre a linha, reposta no arnês, deixa a sabotagem `linha` passar (`c5/linha_antiga.py` → `c5/linha_antiga.out`: «fora da linha em 0 áreas, reposta 1600×», «na linha True (reposta 200×)»). O teclado com a tecla nas três peles, a 1280×800, 1248×640 e 1280×641: as oito áreas e os catorze diálogos andam nos dois sentidos com o foco à vista (na Foco a tecla alcança 31 controles no Resultado, 59 no Estudo, 38 na Revisão, 27 no Dataset, 53 na Galeria, 63 na Rotulagem e 49 na Revisão de texto), e a «Folha transcrita» do Texto empaca — REPROVOU, arquivo de outra sessão. Antes dos consertos deste ciclo o portão achava também a lista de lances e a caixa de colar do Estudo e a «Leitura do motor» da Rotulagem (`c5/teclado_pre/`, `c5/janela_4f3e218/`) | `scratchpad/c5/janela_c5.sh` → `docs/quality/ui/c2_fase5/minimo*_20260923_2334*–2336*.json` e `teclado_*_20260923_2336*.json` |
| C18, ciclo 4: o arnês que mede com a linha assentada e grava de onde veio o código | no `7736617` (a suíte limpa) contra o tronco `7cd400a` limpo — o JSON grava os dois: PASSOU sem livro e com o Kemeri (1248×606 / 1248×640 / 1246×629; no mínimo, mensagem 320, documento 272–288, dispositivos 135, ocupação 171 px, para os dois nomes); as cinco sabotagens REPROVARAM (`reserva`: dispositivos 0 px e ocupação 0–10; `rodape`: 3318 px; `mensagem`: 0–22 px; `aperto`: espremidos; `corte`: fora da vista sem barra). Nas sete corridas no commit, com a máquina quieta, o produto não reescreveu a linha (`linha_reposta` 0); nas sete de antes do commit, com oito processos de OCR ao lado, reescreveu em seis delas (uma ou duas vezes), e o arnês a repôs (`c4/janela/`). Teclado PASSOU a 1280×800 e 1248×640 (Revisão de texto 50/50), com a ordem gravada no JSON: a tabela, o cartão, as ações | `scratchpad/c4/janela_c4.sh` → `docs/quality/ui/c2_fase5/minimo*_20260923_1835*–1837*.json` e `teclado_foco_20260923_1837*.json` |
| C18, ciclo 3: as quatro zonas do rodapé | PASSOU com e sem livro (1248×606 / 1248×640 / 1246×629); no mínimo, mensagem 320, documento 272–288, dispositivos 135, ocupação 171 px, para o nome de 149 caracteres e o da Karpov 2 (58); a 1366×728 documento 390–408; as sabotagens `aperto`, `rodape` (3318 px), `corte`, `mensagem` e **`reserva`** (dispositivos e ocupação com 0 px) REPROVARAM; sete corridas, nenhuma pele morta; teclado PASSOU (Revisão de texto 50/50); a sonda do crítico sobre o acervo: dispositivos cortados em 0 dos 46 livros a 1248–1600 px (ciclo 2: 46/46/45/22); a 1280×641 as seis ações da Revisão de texto à vista nas três peles | `scratchpad/minimo_c3.sh` → `docs/quality/ui/c2_fase5/minimo*_20260923_1353*–1356*.json`; `teclado_c2.sh`; `…\_critico_f5\c2\c18_rodape_acervo.py`, `…\_critico_f5\c18_visiveis.py` |
| C18 mínimo da janela e o que fica à vista (ciclo 2) | PASSOU com e sem livro (1248×606 / 1248×640 / 1246×629; 0 fora da vista sem barra e 0 espremidos no mínimo e a 1366×728; a mensagem com 480 px e o nome com 418–554 px, com a linha cheia); as sabotagens `aperto`, `rodape`, `corte` e `mensagem` REPROVARAM; duas corridas completas iguais, nenhuma morte (§0.1); teclado da Foco a 1280×800 e 1248×640 PASSOU em toda área (Revisão de texto 50/50, Rotulagem 65/65, Galeria 57/57) | `scratchpad/minimo_c2d.sh` (`caissa.ui.audit.minimo --tronco <árvore> [--pdf …1937 Kemeri.pdf] [--sabotar S]`, uma saída por corrida); `teclado_c2.sh` (`caissa.ui.audit.teclado --pele foco --pdf … --largura L --altura A`) |
| testes da suíte (com PyQt6, **com** `test_arquitetura.py` na mesma corrida) | ciclo 5: **4.051 passaram, 9 pulados, 1 reprovou** em 914 s, com o `test_arquitetura` na mesma corrida (`c5/suite_tests_c5.out`): o reprovado é a sabotagem do teste de ponta a ponta do ciclo 4 (`test_table_rows_page.py`) — desligar só o texto corrido já não embaralha a página, porque a calha da partida também a segura (cada regra sozinha) —; a sabotagem passou a desligar as duas, e o arquivo, de novo, passa; nenhum `src` mudou depois da corrida; ciclo 4: **4.032 passaram, 9 pulados, 0 reprovaram** em 1.089 s, com a publicação do `sol.json` ao lado (`c4/suite_tests_c4.out`); ciclo 3: **4.025 passaram, 9 pulados, 0 reprovaram** em 955 s (`suite_tests_c3.out`); ciclo 2: **4.020 passaram, 9 pulados, 0 reprovaram** em 789 s (`suite_tests_c2.out`; ciclo 1: 4.004 + 9) — nenhuma exceção | `PYTHONPATH=.venv-pack\Lib\site-packages QT_QPA_PLATFORM=offscreen .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py` |
| testes do tronco (sem `--deselect`; ciclo 4 numa árvore limpa do `7cd400a`, os ciclos 2 e 3 numa do `8243e90` com os arquivos deles) | ciclo 5, numa árvore limpa do `7a78367`: **4.792 passaram, 16 pulados, 8 xfail, 1 reprovou** em 464 s, a árvore limpa antes e depois (`c5/trunk_tests_c5b.out`; no `4f3e218`, 4.791 passaram, `c5/trunk_tests_c5.out`) — o reprovado é o do ambiente, por construção da árvore efêmera; ciclo 4: **4.789 passaram, 16 pulados, 8 xfail, 1 reprovou** em 3.590 s, com as varreduras ao lado (`c4/trunk_tests_c4.out`); ciclo 3: **4.790 passaram, 15 pulados, 8 xfail, 1 reprovou** em 547 s (`trunk_tests_c3.out`); ciclo 2: **4.787 passaram, 15 pulados, 8 xfail, 1 reprovou** em 746 s (`trunk_tests_c2.out`; ciclo 1: 4.781 passaram em 523 s): o reprovado é `test_environment::test_o_pacote_instalado_resolve_para_esta_arvore`, **por construção** na árvore efêmera (ela usa o `.venv` do checkout principal, cuja instalação editável aponta para lá — a mensagem diz isso); os 11 pulados a mais que no checkout principal pedem artefatos fora do git (PDFs, modelos). No checkout principal, `test_environment.py` e `ImpressaoDaMedicaoTests` **17/17** — o `ImpressaoDaMedicaoTests` sem `--deselect` pela primeira vez desde a fase 2. A suíte inteira do tronco não foi rodada no checkout principal para o portão: ele tinha o trabalho em andamento de outra sessão | `cd <árvore> && PYTHONPATH=<árvore>\src QT_QPA_PLATFORM=offscreen ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`; no checkout principal `…pytest tests/test_environment.py tests/test_field_eval.py::ImpressaoDaMedicaoTests` |
| `git status --short` | só os caminhos da fase nas duas árvores; fora deles, o trabalho de outras sessões (`packaging/*` e `uv.lock` na suíte, e no ciclo 2 `docs/EDITOR_HTML_CSS_ROADMAP.md`, `docs/EDITOR_HTML_CSS_SPEC.md` e `docs/quality/EDITOR_HTML_CSS_CRITICAS.md`; no tronco, `tests/test_qt_resultado_vista_do_impresso.py` e — surgidos durante a integração — `qt/janela.py`, `qt/painel_de_texto.py`, `text/rico.py`, `ui/texto_declarado.py`, e no ciclo 2 `tests/test_qt_texto_digitacao.py` e `tests/test_texto_digitacao.py`), não tocado; os commits do ciclo 2 foram feitos por caminho | `git status --short` |

### 0.3 O que ficou vermelho ou aberto (honesto)

- **Três portões absolutos do Sol continuam vermelhos**, os mesmos de toda fase: CER limpo
  0,0113 em 2 estratos (≤ 0,005 — o nativo, 0,0171, é quem puxa), acurácia de lances 0,9164
  (≥ 0,998), 157 lances inventados. O de 150 DPI saiu da lista.
- **Sete aceitos com CER > 0,10 ficaram** (eram 30; nenhum entrou): um nativo do Dvoretsky
  (`20:96:252`, 0,417), quatro de sombra (`Xadrez Vitorioso 156:266` 0,426, `120:398`, `60:324`,
  e o sintético `Dvoretsky 75:4` 0,221), um de fax (`authored:de:1`, 0,139) e um de foto
  (`Dvoretsky 54:1`, 0,105). A cobertura dos seis de raster fica entre 0,93 e 1,00
  (`f5_b14_fit2.json`, medida com o B14 desligado): a leitura cobre a tinta e erra dentro dela — o
  B14 mede o texto que falta, não o texto errado. O nativo tem 12 caracteres, abaixo das 12 letras
  que a medida pede para dizer alguma coisa.
- **A pele Foco fica no teto do portão da janela** (1248×640 ≤ 1250×640), segurada pela Galeria do
  tronco (516 px); a rolagem da Galeria é a próxima alavanca, não tomada (§C18). E a 125 % sobre
  1366×768 a janela continua sem caber — os pisos declarados das duas colunas somam mais que os
  1093 px lógicos (fase 4, inalterado).
- **A folga do piso do B14 é fina em região pequena**: na população real a menor cobertura do
  Stefaniu é 0,900 (cartões de ~20 letras), no piso e não abaixo (§B14). E o piso é **dito, não
  resolvido** (não bloqueante 10 do ciclo 2): a regra declarada não escolhe entre 0,8757 e 0,99, e
  o desempate que dá 0,90 foi escrito depois de a `dev` ter sido vista.
- **A régua do C17 não decide o `.pt`**: com uma semente por variante, a variância entre sementes é
  maior que a diferença entre variantes (§C17); a troca continua da pessoa (§10.2).
- **O B13 reordena o ruído que o Tesseract lê dentro dos diagramas** das páginas reais (Estrin
  p. 20, e parte da Levenfis p. 40): ruído antes e depois, só em outra ordem. As pp. 36 e 39 da
  Levenfis, que só isso mudavam na primeira regra, ficam idênticas com a final.
- **O B13 muda a leitura de linhas vizinhas ao grupo numa página rasterizada** (o não bloqueante 7
  do ciclo 1 e o 3 do ciclo 2 do crítico, que ficam): a região que agrupa escolhe outra variante,
  e o texto corrido dela muda para melhor e para pior — Levenfis p. 134 na sonda do crítico,
  `tipicd` → `tipică` mas `1...De7` → `1...De?`; na Gallagher p. 41 «33 ♔d3 ♘xb5» (certo
  desligado) → «33 ♔dd ♘8b5», e na p. 175 um lance sai da linha dele. Pelo importador, na
  Levenfis p. 134, só o ruído de um diagrama muda.
- **O ganho do B13 nas tabelas não generaliza para outra fonte** (não bloqueante 2 do ciclo 2): as
  linhas do `table:2` compostas em Times, com outra semente de degradação, saem 0,6224 → 0,5280
  (o `table:2` do corpus, em Georgia, 0,0035); o portão de 150 DPI verde se apoia em três itens de
  tabela.
- **A 1280×641 (o portátil-alvo maximizado) o cartão da Revisão de texto rola**: as seis ações
  ficam à vista, mas a fileira de figurinas (8 controles) desce abaixo da dobra, e na Fita também
  o rótulo da verdade; chega-se a elas pela barra do cartão.
- **A 1280×641 as ações do Resultado ficam abaixo da dobra** (não bloqueante 6 do ciclo 3, igual
  aos ciclos 1 e 2): na Foco, «Salvar a posição», «Salvar todas as posições da página»,
  «Desfazer», «Refazer», «Limpar» e «Esconder incerteza» com 0 px à vista — 13 controles na Fita,
  1 na Clássica —, alcançáveis pela barra do modo (`…\_critico_f5\c18_visiveis.py`).
- **O rodapé no aperto tem custo, e ele é dito** (não bloqueantes 4 e 5 do ciclo 3): a mensagem
  tem até 320 px garantidos, ~57 caracteres — a frase de erro do próprio produto sem o `.pt`
  (`leitura.FRASE_SEM_MODELO`, 84 caracteres, 474 px) sai elidida no meio, com a inteira na dica,
  nos 46 livros do acervo de 1246 a 1440 px, e o estado vazio do Resultado (73 caracteres, 409 px)
  também; e a ocupação não tem forma fixa: com «aquecendo o modelo (<caminho do .pt>)» ela vai ao
  teto (elidida em 46 de 46 livros; a exportação EPUB, 36 a 45) e o nome do livro do Kemeri fica
  com **95–96 px** a 1246–1248 — abaixo dos 120 que o portão cobra na importação, a operação que
  ele mede. Voltar a reserva a 480 px esvaziaria as zonas vizinhas (o bloqueante 2 do ciclo 2).
- **As regras do B13 recusam o que o ciclo 2 lia por linha** (não bloqueante 1 do ciclo 3): uma
  tabela de duas colunas que não é lista de lances e deixa uma calha de faixas comparáveis — os
  campeões mundiais, «nome | período», a 150 DPI — sai por colunas, **como com a regra desligada**
  (0,5696; o ciclo 2 dava 0,0000). A evidência de uma tabela de chave e valor abriria a calha para
  as notas que nenhuma regra chama de prosa (o bloqueante do ciclo 3). E o texto corrido do ciclo 4
  toma por prosa uma coluna de células em palavras minúsculas: «Rodada 1 | vitória das brancas /
  empate por repetição / …» sai por colunas (0,5000; o ciclo 3 dava 0,0000). As duas recusas
  devolvem a leitura do desligado, nunca uma pior (§0.6).
- **O B13 muda a leitura fora do grupo também em alemão** (não bloqueante 10 do ciclo 3): a Estrin
  p. 29 pelo importador troca a variante («13....Ld4: 14.Lg6! d5 15.Df3+» → «15....Ld4: 14.Lg6! ds
  15.Di3+»), e na p. 77, sem a máscara de diagramas, o bloco do alto da coluna direita sai antes
  da prosa da esquerda (igual no ciclo 2; pelo importador só o ruído do diagrama muda) — a classe
  do não bloqueante 3 do ciclo 2. E a Estrin das minhas sondas dos ciclos 2 e 3 (§0.2, §B13: «pp.
  20–27, 7 de 8») foi lida em `ron+eng`, a língua errada; a Estrin inteira em `deu+eng` está no
  ciclo 4 (88 páginas, a leitura ligada igual à do ciclo 3 em todas; 16 mudam do desligado, como no ciclo 3).
- **A15: a varredura de acentos não segue o dado** (não bloqueante 8 do ciclo 3): o crítico
  construiu oito formas de um texto de tela chegar à tela sem ser visto (§A15); nenhuma frase de
  tela real está escondida hoje.
- **O portão da janela não mede altura, nem editores, listas e tabelas** (não bloqueante 5 do
  ciclo 2): mede os controles de texto e de clique, na largura, e as quatro zonas do rodapé.
- **O B14 sinaliza leitura ruim que já ia para a revisão** nos livros do crítico: 5 regiões de
  ruído lido em diagrama e a Gallagher p. 50 (0,896, com CER 0,20). Nenhuma leitura boa, mas o
  piso continua com folga fina (a menor da população do construtor, 0,900 no Stefaniu; §B14).
- **O portão da janela não roda na plataforma real**: tudo `offscreen` com a fonte do produto
  imposta (o crítico disse o mesmo); e o `pdf` que os JSON do portão gravam é o caminho absoluto
  desta máquina, como no ciclo 1.
- **A «Folha transcrita» do Texto empaca a tecla** (o portão do teclado com a tecla, ciclo 5): o editor da folha guarda o Tab e escreve a tabulação no texto (e o Ctrl+Tab, que num editor do Qt sai do campo, troca de área nesta janela). O arquivo (`qt/painel_de_texto.py`, tronco) é de outra sessão, que trabalha nele agora: o portão fica **REPROVADO** ali, e o conserto — o `setTabChangesFocus(True)` do Estudo e do cartão, ou uma saída anunciada — fica para quem o edita.
- **A franja do texto corrido** (não bloqueante 1 do ciclo 4), com os números: 0–9 % das páginas, conforme o livro, têm notas que nenhuma regra de prosa segura (a triagem do crítico, `…\_critico_f5\c4\risco_paginas.out`); com uma partida ao lado, o ciclo 4 embaralhava 12 das 29 dessas páginas (e pelo importador a Nunn p. 29 0,0824 → 0,6571, a p. 143 0,1778 → 0,7276, a Burgess p. 133 0,1016 → 0,6213), e o ciclo 5, pela calha da partida, **nenhuma** (0 de 41 com as 11 do índice da Dvoretsky e a da Aagaard; as três inglesas idênticas ao desligado). Fica sem regra, e sem medida, a nota que nenhuma regra chama de prosa ao lado de algo que não é partida — uma tabela longa de células —: ali a calha só vale pelas regras de antes.
- **Pelo importador, a Stean p. 165 sai com a leitura do Tesseract** — a mesma que a máquina sem memória deu à varredura do ciclo 4 («7-45 IN USA», a linha de lixo no fim), em revisão —, e não com a do RapidOCR (0,9022), que é a boa: o leitor de glifos vê figurinas nesta contracapa (por engano), e a guarda de figurinas não deixa um motor secundário ancorar onde elas aparecem (`OcrService._settle`); sem a guarda o RapidOCR ancora e sai «$9-95 IN USA», e sem o B14 nada muda (`scratchpad/c5/stean165_ancora.py`). Não é do B13, e esta fase não mexe na guarda.
- **Um `MemoryError` dentro de um motor derruba a página**: o `OcrEngineBase.recognize` pega as falhas de operação (`OSError`, `ValueError`, `RuntimeError`) — e agora a página as diz —, mas não o `MemoryError` (simulado no RapidOCR, `scratchpad/c5/stean165_varredura.py`: a página não sai). Dito, não mudado.
- **O árbitro mede a concordância com o `difflib` num sentido só**: num texto longo a heurística de lixo dele dá números diferentes aos dois sentidos (0,2466 × 0,2936 na Nunn p. 288), e a concordância de duas leituras depende de qual é a primeira. Medida nos dois sentidos, ela mudou o vencedor em 7 de 268 páginas reais que o B13 nem toca, 5 para pior — o RapidOCR intercalando as colunas de uma página, que o detector dele junta através da calha (§0.7). O conserto que falta é o do RapidOCR, não o da medida; fica.
- **Não tomados, como o §3d disse**: o `18 . . .` do Dvoretsky, os homóglifos `Kp`/`Кр`, o `vazio`
  a 200 %, o alto contraste como pele, a crítica das fases 3 e 4.

### 0.4 O ciclo 1 do crítico: REPROVADO com três bloqueantes, e o que mudou

O crítico adversarial (Claude, num subagente, `CRITIC_CHARTER.md`; veredito transcrito em
`OCR_UI_ANALISE_C2_CRITICAS.md` «Fase 5») reproduziu os números do §0 e das seções contra os JSON e
os portões, e reprovou por três defeitos que as medições do construtor não viam. O construtor não
contestou nenhum; cada um foi medido de novo, consertado e travado por teste com sabotagem.

- **1. O B13 embaralhava as duas colunas de uma página real** (bloqueante 1). No importador de
  produção, a Gallagher (*Winning With the King's Gambit*, digitalizado, colunas de 22–27
  caracteres) p. 50 ia de CER **0,2732 → 0,7042** contra a transcrição do crítico, e a p. 53 punha o
  cabeçalho de «Game 17» nas notas da partida anterior; e três páginas construídas (duas partidas
  lado a lado 0,0190 → 0,5625; uma partida nas duas colunas 0,2241 → 0,4152). A causa: nenhuma
  linha de uma coluna estreita é prosa por **comprimento** (≥ 30 caracteres), então a calha nunca era
  julgada e o B1 não protegia (a faixa da direita tem mediana de lance). Cinco regras, cada uma do
  caso que a pediu e com teste e sabotagem (`test_table_rows.py`, 16 → 24):
  1. **prosa por palavras** — um bloco de 2 linhas ou mais cuja linha mediana tem 4 palavras nunca
     entra num grupo; as palavras contadas **por célula** quando o bloco tem calha interna (o
     `table:2` a 150 DPI lê três células de cada linha como uma: «Bona 2008 | Gambito da Dama
     Recusado | 88» tem 6 palavras na linha e 4 na célula maior);
  2. **uma numeração por grupo** — números de lance consecutivos, soltos (`26`, `27`…) ou seguidos
     de lance (`22 g4`, `21... ♖g8`); um número solto (o `21` que o Tesseract cortou da coluna) conta;
     e um bloco de lances cuja numeração própria fica entre ele e a do grupo não entra (a partida nas
     duas colunas: os lances da direita pareciam as respostas das pretas da esquerda);
  3. **a calha da página** achada pelo `find_gutters` sobre todas as linhas, valendo quando há um
     bloco de prosa de um dos lados (a p. 53: a calha existe, e a coluna esquerda tem notas);
  4. **a calha interna de um bloco só faz células quando é 1,5× mais larga que o espaço mediano entre
     palavras** — medido: um «rio» por três linhas justificadas da Gallagher p. 53 tem 20 px contra
     33 de espaço; as calhas entre as células do `table:2` têm 15 contra 7 (300 DPI: 32–68 contra
     14) — e o parágrafo da Kmoch p. 44 com uma calha espúria deixa de semear;
  5. **adjacência** — um bloco entra quando a maioria das suas linhas encontra o parceiro do grupo
     com espaço vazio entre eles, sem palavra de um bloco de fora na mesma altura (a Gallagher p. 52:
     «The | so-called | “Long» em três blocos, com o do meio num parágrafo).

  **Remedido** (as sondas do próprio crítico e as do construtor, com a regra final): a Gallagher
  p. 50 pelo importador passa a **melhorar** — CER **0,2732 → 0,2028** (a lista de lances da coluna
  direita, que o desligado lê número por número, sai `26 ♖e3 Qxd4`), e as pp. 51, 52 e 53 ficam
  idênticas ao desligado; as três páginas construídas ficam idênticas ao desligado; a Kmoch pp. 28,
  40, 44, 48 e 68, idênticas; a Levenfis pp. 36–52 com **15 de 17** idênticas (as pp. 36 e 39, que
  só reordenavam ruído de diagrama, agora ficam iguais), a Estrin 7 de 8, a Stefaniu 8 de 8; a
  Levenfis p. 134 pelo importador só reordena o ruído lido num diagrama (13 → 11 regiões,
  similaridade 0,9906, `scratchpad/b13_lev134.out`); e os sete itens
  do corpus com os números da primeira versão. O A/B do `bench_sol` foi refeito no código final e
  dá os 747 itens **idênticos** aos da primeira regra, corrida a corrida — o corpus não tem coluna
  estreita, e o que a regra nova muda está nas páginas reais (§B13).
- **2. A janela cabia escondendo** (bloqueante 2). As rolagens novas desligavam a barra horizontal
  e o portão lia só o `minimumSizeHint`: a 1248×640 a barra de ações do Resultado e «Pular»,
  «Anterior», «Próxima» da Revisão de texto ficavam com **0 px** à vista; e a mensagem do rodapé com
  **0 px** ao lado de um nome de livro de 149 caracteres — no leiaute de caixa o Qt encolhe **primeiro**
  o item esticável (`QLayoutStruct.smartSizeHint` devolve o mínimo quando há `stretch`), e o mínimo
  dela era zero. O que mudou (§C18): barra horizontal quando precisa; o conteúdo reflui — as
  fileiras de botões da Revisão de texto, do cartão e da Rotulagem viram fileiras fluidas
  (`ui/widgets/fileira_fluida.py`, novo), o recorte do cartão quebra linha e escala a imagem à
  largura que houver, a navegação da Galeria vira uma `BarraFluida`; a mensagem tem **480 px**
  garantidos enquanto está na tela (`rodape.LARGURA_DA_MENSAGEM`); e o **portão mede o que fica à
  vista**: nenhum controle fora da vista sem uma barra que leve a ele, nenhum espremido abaixo de
  90 % do próprio mínimo, a mensagem com ≥ 320 px ao lado do nome longo e com a linha do rodapé
  cheia — no mínimo da janela e a 1366×728 —, e uma sabotagem por regra. O portão estendido achou
  **mais** que o crítico, consertado no mesmo passo: quinze controles da Rotulagem espremidos até a
  metade do texto («Adicionar PDF…» com 57 de 107 px, a lista de projetos com 56 de 218) e quatro
  da Galeria; e, com o livro aberto e a importação em curso, o botão «Mensagens» do rodapé com 27
  de 82 px — ele tinha um piso de um pixel, que saiu (§C18).
- **3. A coluna «≤ 0 errados» do C17 saía errada** (bloqueante 3). A grade de limiares parava em
  0,99, e o único errado da produção está a 0,9979 com 74 exatos acima: a tabela dizia 0 e o texto
  dizia que «nenhum limiar exporta com zero erros»; seis modelos zerados pelo mesmo artefato. Os
  orçamentos passam a ser calculados em todo valor distinto de confiança (`model_ruler.cuts`), e a
  AURC trata empates pela média sobre as ordens do empate (a primeira versão dependia da ordem do
  `sorted`: `c4_mhspe_s44` entre 0,0111 e 0,0134). A tabela e as conclusões do §C17 foram refeitas
  sobre as mesmas linhas: com zero errados a produção exporta **74**.
- **Os não bloqueantes, no mesmo ciclo** (seis fechados, um dito). (a) O B14 cego numa digitalização com moldura
  escura (a borda do scanner era uma «coisa grande» do tamanho da página, e tudo dentro dela ficava
  de fora: Kmoch pp. 40/44/48 com 0 letras): um componente com a caixa de metade da imagem ou mais é
  a moldura, não uma figura (1.058/1.162/995 letras), e a região que o B14 não julga é dita no
  rastro. (b) O piso do B14: a regra de desempate foi escrita (§B14). (c) As brechas do
  `test_strings` (o `.split()` de qualquer receptor; a chave de um dicionário que vai para a tela):
  fechadas por posição e por uso, com os três casos do crítico no teste anti-brecha. (d) O
  `test_arquitetura` lia um import quebrado como «veio Qt»: código 3 para o binding, e qualquer
  outra saída não zero é falha do import dita com o erro. (e) As imprecisões do §C17 («96–97 e 99»)
  saíram com a tabela refeita. (f) A evidência não versionada: o A/B por item
  (`docs/quality/sol/f5_ab.json`), o ajuste do piso (`docs/quality/sol/f5_b14_fit3.json`), a régua
  do C17 (`docs/quality/campo/f5_c17_regua.json`) e os JSON do portão da janela
  (`docs/quality/ui/c2_fase5/`) foram versionados (§0.2). (g) A Levenfis p. 134, que a primeira
  regra rearrumava na sonda rasterizada do crítico: com a regra final, 19 → 15 regiões (a primeira regra: 11); a lista
  `2. Ne3:c5! Re8—d7` passa a sair numa linha (antes `2 Ned’:c5t RekR—Aa7` e `Re8—d7`
  separados), o ruído do diagrama é reordenado, e o texto corrido muda além do grupo, porque a
  região que agrupa escolhe outra variante — `tipicd` → `tipică` e `De7—a5di` → `De7—a5`, mas
  `1...De7` → `1...De?` (`scratchpad/b13_lev_raster_c2.out`); fica dito em §0.3.

### 0.5 O ciclo 2 do crítico: REPROVADO com dois bloqueantes, e o que mudou

O crítico refez as próprias reproduções do ciclo 1 com o código do ciclo 2 e deu os três
bloqueantes por resolvidos nos casos dados (a Gallagher, a janela, a régua), mas reprovou por dois
defeitos que os consertos deixavam passar ou criavam (veredito em
`OCR_UI_ANALISE_C2_CRITICAS.md` «Fase 5», ciclo 2). O construtor não contestou nenhum.

- **1. O B13 intercalava as duas colunas de um índice real** (bloqueante 1 do ciclo 2). A Karpov 2
  (*Chess Combinations — World Champions 2*, raster) p. 268 é um índice de nomes em duas colunas
  estreitas, sem uma linha de prosa: a regra do ciclo 2 só aceitava a calha única de
  `find_gutters` com prosa de um dos lados, descartava a calha que ela mesma achava (672–1002 px)
  e juntava os verbetes dois a dois — «Ragozin 24 Bennett 218», CER **0,7606** da leitura ligada
  contra a desligada (a ordem do livro), sem aviso. A mesma classe em mais três formas: um índice
  construído a 150 DPI (0,1824 → 0,6554), notas de variantes ao lado da lista de lances numerada
  («Or 21 Bd6 Rg8 22 g4 Rg6 26 Re3 Bxd4», 0,0113 → 0,5845) e a fixture do próprio teste com as
  notas trocadas por variantes e nenhum bloco de prosa. O que mudou (`rows.py`), cada regra com
  teste e sabotagem (`test_table_rows.py`, 24 → 29):
  1. **a calha da página vale sem prosa**: uma calha única de `find_gutters` sobre todas as linhas
     que deixa duas faixas de **largura comparável** — a estreita com ao menos metade da larga
     (`page_band_share`; a p. 268: 552 e 511 px) — é fronteira do grupo, com ou sem prosa;
  2. **só uma lista de lances a cruza**, e por evidência **positiva**: os números (e os lances das
     brancas) à esquerda, um lance por linha à direita, sem número próprio (`_numbers_column`,
     `_move_column`) — as listas do Dvoretsky, cuja calha única deixa faixas de 0,65–0,85 uma da
     outra, continuam lidas por linha; duas colunas da mesma forma (nome e páginas) são duas listas;
  3. **notas de variantes são texto corrido**: um bloco em que metade das linhas tem um número de
     lance **dentro** da linha, seguido de um lance, nunca entra num grupo nem o semeia
     (`_notes`, `notes_share`) — segura as notas de **variantes** ao lado da partida, onde as
     faixas não são comparáveis (a lista de lances tem linhas curtas); as notas **comuns** (três
     palavras por linha, poucos lances dentro) escapavam — o bloqueante do ciclo 3 (§0.6);
  4. **prosa por palavras pede continuação**: um terço das linhas, depois da primeira, começando
     por minúscula (`prose_continued`) — a tabela com as aberturas por extenso (4 palavras por
     célula, o não bloqueante 1 do ciclo 2) volta a ser lida por linha: **0,4646 → 0,0113** (no
     ciclo 2, 0,3456).

  **Remedido**: a Karpov 2 p. 268 pelo importador sai **idêntica** ao desligado; as construções do
  crítico também (o índice a 150 DPI 0,1824, as notas ao lado da lista 0,0113, sob um título de
  largura inteira 0,0102), e as duas fixtures de notas deixam de atravessar a calha; a
  classificação de torneio segue melhorando (0,1388 → 0,0909). As varreduras do crítico refeitas
  com a regra final (`…\_critico_f5\c2\b13_varredura.py`, quatro filas): **280 páginas** — a
  Gallagher inteira (176) e as páginas finais (índices, sumários, soluções) de nove livros raster
  (104) —, **43 mudam** contra 46 no ciclo 2, e a leitura ligada é a do ciclo 2 em 275. As cinco
  diferenças: as pp. 267, 268, 270 e 271 da Karpov 2 (índice) passam a sair idênticas ao
  desligado, e a Levenfis p. 302 (o sumário) melhora — CER 0,1221 → 0,0738 contra a transcrição
  do crítico; três dos seis títulos saem com a sua página («Capitolul XXIII : SCOALA DE SAH RUSĂ
  SI SOVIETICĂ 283»), e as páginas dos outros três, depois da última entrada (desligado, todas vão
  para o fim) — as linhas em maiúsculas não continuam frase, e a regra 4 deixou de tomá-las por
  prosa.
  A fila de A/B, refeita no commit: `f5c3_on`, `f5c3_b13_off` e `f5c3_b14_off`, no `3ff1830` com o código que mede limpo
  (`dirty_code` vazio), dão os 747 itens idênticos aos do ciclo 2 — e aos do ciclo 1 — em CER,
  decisão e todo campo numérico por item (o texto, os JSON só o guardam dos itens com CER acima de
  0,05 — os primeiros 200 caracteres): o corpus não tem índice, sumário nem nota de variante em coluna estreita, e o
  que as regras novas mudam está nas páginas reais. E as páginas reais do ciclo 2 (Levenfis,
  Estrin, Stefaniu, Kmoch, Gallagher pp. 48–55, a Gallagher pelo importador, os itens de tabela do
  corpus) saem com o mesmo resumo, página a página (`scratchpad/b13_c3_all.sh`).
- **2. O conserto da mensagem do rodapé esvaziava as zonas vizinhas** (bloqueante 2 do ciclo 2).
  A reserva de 480 px da mensagem saía das zonas de **dispositivos** e de **ocupação**: no aperto o
  leiaute tira de cada item não fixo a mesma parte, e as zonas curtas chegavam a 0 px antes do nome
  do livro — dispositivos cortados em **46 dos 46** livros do acervo a 1248 e a 1366 px, a queda
  para a CPU de novo em silêncio; e o portão passava porque só olhava a mensagem e o documento. O
  que mudou: no tronco (`qt/rodape.py`, `qt/rotulo.py`) a reserva da mensagem é a largura da
  frase até **320 px** (`LARGURA_DA_MENSAGEM`; ~57 caracteres na fonte do produto — o ciclo 3 escreveu «~45» —, o limiar de legibilidade do portão; o custo, dito no §0.6),
  as zonas de dispositivos e de ocupação têm o texto inteiro garantido até **240 px**
  (`LARGURA_DA_ZONA`), e quem cede é o nome do livro, elidido no meio; os pisos são do próprio
  rótulo elidido (`RotuloElidido(piso=…)`, o `minimumSizeHint` medido com a fonte de agora) —
  um `setMinimumWidth` calculado quando o texto chegava media com a fonte de antes do estilo, e a
  zona saía «peças cpu … sem pesos». Na suíte, o portão mede **as quatro zonas** com a linha cheia
  (a frase longa, a importação com a barra, os dispositivos da queda para a CPU), para o nome mais
  longo do acervo e um comum (a Karpov 2, 58 caracteres), no mínimo e a 1366×728, com a sabotagem
  nova `reserva` (o rodapé do ciclo 2). **Remedido**: a sonda do crítico sobre o acervo, zona de
  dispositivos cortada em **0 dos 46** livros a 1248, 1366, 1440 e 1600 px (ciclo 2: 46, 46, 45 e
  22); o portão PASSOU — no mínimo da janela mensagem 320, documento 272–288, dispositivos 135,
  ocupação 171; a 1366, documento 390–408 —, e a `reserva` REPROVOU (dispositivos e ocupação com 0 px), como as
  quatro sabotagens antigas; sete corridas, nenhuma pele morta; o teclado passou.
- **Os itens do mesmo ciclo.** (a) As ações do cartão da Revisão de texto saíram da rolagem: a
  1280×641 as seis ficam à vista nas três peles (no ciclo 2, 0 px na Foco); o que desce abaixo da
  dobra, dentro do cartão que rola, é a fileira de figurinas (8 controles; na Fita também o rótulo
  da verdade). (b) A evidência do A/B guarda o `answered` de cada item — a média de cada estrato se
  refaz dos itens (conferido em todas as corridas) — e o `bench_sol` grava o código não commitado
  que mediu (`dirty_code`); a fila do ciclo 3 correu no commit. (c) A frase da sabotagem do C17 e a
  do Stefaniu p. 49 corrigidas (§C17, §B14). (d) As três brechas novas do `test_strings`: a lista
  minúscula passada direto a uma chamada que escreve na tela, `", ".join(D)` e `[*D]` são varridas.
- **O que fica, dito.** O B13 muda a leitura de linhas vizinhas ao grupo (o não bloqueante 3 do
  ciclo 2: na Gallagher p. 41, «33 ♔d3 ♘xb5» → «33 ♔dd ♘8b5»; p. 175, um lance sai da linha dele);
  o ganho nas tabelas não generaliza para outra fonte (as linhas do `table:2` em Times, 0,6224 →
  0,5280); o portão da janela não mede altura, editores, listas e tabelas; o piso do B14 é dito,
  não resolvido (§0.3).

### 0.6 O ciclo 3 do crítico: REPROVADO com um bloqueante, e o que mudou

O crítico conferiu os dois bloqueantes do ciclo 2 e os deu por resolvidos (a Karpov 2 p. 268 pelo
importador idêntica ao desligado nas três execuções; dispositivos cortados em 0 dos 46 livros),
mas reprovou por um defeito da mesma classe dos bloqueantes 1 dos ciclos 1 e 2, que o conserto do
ciclo 2 não alcançava (veredito em `OCR_UI_ANALISE_C2_CRITICAS.md` «Fase 5», ciclo 3). O
construtor não contestou nenhum item. (As edições de `rows.py` e `test_table_rows.py` às 13:53–13:54
que o veredito atribui a «outra sessão» eram deste construtor, começando o ciclo 4 depois de ler o
rascunho do veredito; as sondas do crítico já tinham terminado.)

- **1. O B13 juntava, linha a linha, uma coluna de notas comuns e a lista de lances da outra
  coluna — e o importador aceitava a página embaralhada** (bloqueante 1 do ciclo 3). Na página que
  o crítico construiu na medida da Gallagher p. 50 (Times 10 pt, colunas de 1,95 pol., 300 DPI,
  notas justificadas na coluna), as notas são anotação comum — «White could also try / 21 Bd6!?,
  when after / 21...Rg8 22 g4 Rg6 the / position is unclear.» —, com mediana de 20–28 caracteres
  e 3 palavras por linha e menos da metade das linhas com número de lance dentro: nem prosa por
  comprimento, nem por palavras, nem notas de variantes; e as faixas da calha têm razão 0,41 (587
  e 240 px: a lista de lances sem tabulação tem linhas curtas). Nada segurava a calha. Pelo
  importador de produção, a p. 0 (inglês) ia de CER **0,0052 a 0,6440 com a decisão `accepted`**
  nos dois lados; a p. 1 (alemão) 0,2284 → 0,5499; as pp. 2 e 3, com notas reais da Kmoch, 0,0367
  → 0,5598 e 0,0754 → 0,5748. E o relatório dizia o contrário: «nunca através da calha» (§0) e,
  das notas de variantes, que seguravam «a página de notas ao lado da partida» (§0.5) — seguravam
  só as densas. O que mudou (`rows.py`; `test_table_rows.py` 29 → 34, e um teste de ponta a ponta
  novo):
  1. **texto corrido sem contar palavras** (`_running`, `running_lines = 4`): um bloco de 4
     linhas ou mais, com a linha mediana mais longa que uma célula (> 12 caracteres) e um terço
     das linhas, depois da primeira, abrindo com uma palavra minúscula, é prosa — nunca entra num
     grupo e, de um lado da calha, a segura. É o caminho que o crítico mediu
     (`c3\sabota_rows.instalar_sugestao`), com uma diferença: a continuação passa a pedir uma
     **palavra** (só letras) — um lance (`b6 23 Be3`, `exd5`) ou um número de lance não abre
     frase —, e isso vale também para a prosa por palavras;
  2. **de duas calhas ou mais, a da página é a vizinha da prosa** — a primeira depois da borda
     direita de um bloco de prosa, a primeira antes da esquerda. O crítico achou que, na
     Gallagher p. 50 real, o `find_gutters` vê duas calhas (a da página, 754–817, e a tabulação
     das pretas, 1171–1193), e a regra não reconhecia nenhuma: numa leitura que o árbitro
     descartou, a lista de lances da coluna esquerda entrou no grupo da partida da direita.
     «Prosa dos dois lados» não bastaria: com a partida tabulada e a coluna direita sem prosa,
     dois blocos de notas que nenhuma regra chama de prosa entram na partida (a página do
     crítico com a partida a 45 %, na fixture). Um grupo que atravessa calhas passa por uma só,
     entre faixas vizinhas, e com a evidência de lista de lances;
  3. **a avaliação separada do lance é parte dele** (`_move_tokens`): «31 Nh1 !?», «Bxd4 +-» — a
     evidência positiva pedia no máximo dois tokens por linha e recusava a lista (0,0603 no ciclo
     2 → 0,6724 no ciclo 3, o desligado); volta a **0,0603**;
  4. **o filtro de prosa da semente ganhou teste** (`_seeds`; não bloqueante 2): o último bloco
     das notas do crítico («change the bishops. / Now 26 Re3 was best. / White's rooks are /
     active, but Black / holds the draw.») é coluna de células pelo rio que as duas linhas
     esparsas abrem, e é texto corrido; sem o filtro, ele semeia. Nesta página a calha segura
     antes, e uma semente de cinco linhas não levaria as dezoito da partida (a parcela de pares):
     nenhuma página medida depende do filtro, e o teste diz isso — ele é o contrato da regra onde
     os outros dois não seguram.

  Cada regra com teste e sabotagem: sem o texto corrido, as notas do crítico juntam-se à partida
  (inteiras num bloco, ou cortadas como o PSM 3 as cortou); sem a regra das duas calhas, a lista da
  coluna esquerda entra na partida da direita e as notas entram na partida tabulada, e com «prosa
  dos dois lados» no lugar dela as notas entram na partida tabulada; contando a avaliação como
  token, a lista do Dvoretsky com avaliações fica por colunas; sem o filtro da semente, o bloco das
  notas vira semente. E
  `test_table_rows_page.py` passa a página do crítico, desenhada como ele a desenhou, pelo
  importador com o Tesseract: a leitura ligada é a desligada, e sem o texto corrido ela sai
  «White could also try 26 Re3…» (~60 s).

  **Remedido** (as sondas do crítico, com a regra final; `scratchpad/c4/sondas.sh`): pelo
  importador, as quatro páginas do `construido.pdf` saem **idênticas ao desligado** — 0,0052
  `accepted` (a página certa, aceita), 0,2284, 0,0367 e 0,0754 —, duas execuções iguais
  (`c4/cer_construido.py`); `b13_estreita3.py --justificar`, inglês 0,0140 e 0,0087 (300 e
  200 DPI) = desligado, alemão 0,2132 = desligado a 300 DPI e **0,0152** a 200 (desligado 0,2335:
  a lista de lances lida por linha); sem justificar, iguais ao desligado ou melhores; `b13_tabulada.py`:
  sem tabulação 0,0140 = desligado, **a 45 % 0,0157** (desligado 0,2373; ciclo 3 0,6510), a 60 %
  0,0140; notas reais de cinco livros (`b13_notas_reais.py 6`): **0 de 6** páginas embaralhadas em
  todos (a Kmoch, 2 de 6 no ciclo 3); a fixture do crítico sem OCR: nenhum grupo. **O que o
  crítico mandou manter:** a Karpov 2 p. 268 idêntica ao desligado; a Gallagher p. 50 em
  **0,2028** (WER 0,3121), as pp. 51–53 idênticas — as quatro, a Reinfeld 1977 p. 319 e a Levenfis
  p. 134 com o texto de cada região igual ao do ciclo 3 (`c4/cmp_importador.py`); as aberturas por
  extenso em **0,0113**, a classificação 0,0909, o índice 0,1824, o controle 0,5280, as notas de
  variantes 0,0113/0,0129/0,0102 e as tabelas de duas colunas do crítico como no ciclo 3. As
  varreduras: as 280 páginas do crítico com a leitura ligada igual à do ciclo 3 em todas (43 mudam do desligado; a Stean p. 165 difere só na leitura desligada, que não passa pelo `rows.py` — outra variante escolhida, com a máquina sem memória: o RapidOCR falhando na alocação, §0.7 item 3(d)); e a Estrin inteira em `deu+eng` (88 páginas), 25 da Gunderam e 22 da Kmoch (raster 300 DPI), iguais ao ciclo 3 em todas (`c4/cmp_varre_c4.py`; as duas últimas interrompidas quando oito processos de OCR ao mesmo tempo esgotaram o arquivo de paginação). A fila de A/B no commit: os 747 itens idênticos aos dos ciclos 1, 2 e 3 em todo campo por item que não é tempo (`f5c4_*`, no `7736617`, `dirty_code` vazio) — o corpus não tem notas comuns em coluna estreita, e o que a regra nova muda está nas páginas construídas; aceitos errados 7, o 150 DPI em 0,0094.

  **O que as regras recusam, dito** (não bloqueante 1 do ciclo 3): a tabela de duas colunas
  «nome | período» (os campeões mundiais) a 150 DPI, que o ciclo 2 lia por linha (0,0000), sai
  **por colunas, como com a regra desligada** (0,5696) — uma calha única de faixas comparáveis é
  fronteira, e o que a cruza tem de ser lista de lances. Dar à tabela de chave e valor a evidência
  dela (uma coluna de nomes ao lado de uma de números) abriria a calha para as notas que nenhuma
  regra chama de prosa ao lado de uma lista de lances — o bloqueante deste ciclo. E o texto
  corrido tem o seu preço, medido pelo construtor (`c4/probe_legenda.py`): uma coluna de células
  em palavras minúsculas é, para a regra, texto corrido — «Rodada 1 | vitória das brancas / empate
  por repetição / …» (8 linhas, mediana de 18 caracteres, toda linha abrindo com palavra
  minúscula), em Times a 300 DPI, lida por linha no ciclo 3 (0,0000), sai **por colunas, como com
  a regra desligada** (0,5000). A legenda de símbolos de um livro («!! brilliant move», «± White is
  much better») não muda: o Tesseract não a corta em blocos que o B13 junte, em nenhuma das regras
  (0,2157 nas três). Nada disso piora em relação ao desligado; o bloqueante deste ciclo era uma
  página trocada **e aceita**. A lista de lances com as avaliações separadas volta a ser lida por
  linha (item 3).
- **2. Os itens do mesmo ciclo.** (a) **A ordem do Tab da Revisão de texto de volta à visual** (**corrigido no ciclo 5**: a ordem existia só na cadeia do foco; com a tecla o Tab parava no campo da verdade e o Shift+Tab das ações punha o foco fora da vista — §0.7, item 2) (não
  bloqueante 3): tirar as ações da rolagem pôs as seis logo depois da tabela e antes do cartão; a
  cadeia do foco é posta à mão (`QWidget.setTabOrder`: a tabela, o cartão de cima para baixo, as
  ações), e `test_the_tab_order_follows_the_eye_table_card_then_the_actions` compara a ordem com a
  posição, com a sabotagem ao lado (sem a cadeia, «Aceitar leitura» vem antes da leitura).
  (b) **O custo da reserva de 320 px** (não bloqueante 4): são ~57 caracteres na fonte do produto
  (o ciclo 3 escreveu «~45»); a frase de erro do próprio produto sem o `.pt`
  (`leitura.FRASE_SEM_MODELO`, 84 caracteres, 474 px) sai elidida no meio, com a inteira na dica,
  nos 46 livros do acervo de 1246 a 1440 px, e o estado vazio do Resultado (73 caracteres, 409 px)
  também — a reserva de 480 px que as deixava inteiras esvaziava as zonas vizinhas (o bloqueante 2
  do ciclo 2). Ficou em 320, dito aqui, no §0.3 e nas docstrings do tronco (`7cd400a`) e do portão.
  (c) **O nome do livro com 95 px sob «aquecendo o modelo»** (não bloqueante 5): com a operação
  real «aquecendo o modelo (<caminho do .pt>)» a ocupação vai ao teto de 240 px, elidida, e o
  documento do Kemeri fica com 95–96 px a 1246–1248 — abaixo dos 120 que o portão cobra, e o portão
  mede a importação; a docstring de `LARGURA_DA_ZONA` dizia «textos curtos e de forma conhecida» e
  agora diz que a ocupação não tem forma fixa. (d) **As ações do Resultado abaixo da dobra a
  1280×641** (não bloqueante 6), iguais aos ciclos 1 e 2, entram no §0.3. (e) **O arnês do portão**
  (não bloqueante 9): o «162/152» do primeiro nome não era a linha medida antes de encher — era a
  linha **reescrita pelo próprio produto**: a visita às áreas acende a leitura do `labels.csv` do
  Dataset e a detecção dos dispositivos, e elas escrevem nas zonas («leitura do dataset
  (labels.csv)», 152 px; «peças ainda não · texto desligado», 162) depois de o arnês enchê-las
  (`c4/probe_rodape_primeira.py`); esperar mais voltas não bastava (a primeira tentativa deste
  ciclo, medida: a mesma leitura, estável). O arnês repõe a linha quando o produto a reescreve,
  mede quando duas voltas seguidas dão as mesmas larguras, grava quantas vezes repôs e se mediu a
  linha dele (fora dela a medida não passa), e grava o commit e o que o `src` de cada repositório
  tem fora dele (`suite`, `tronco`). **Remedido**, no commit: o portão PASSOU com e sem livro e as cinco sabotagens reprovaram, e o «162/152» não voltou em nenhuma das catorze corridas (sete antes do commit, com a linha reposta pelo arnês em seis, e sete no commit) — na medida do rodapé; na passada da vista o crítico o viu voltar com a máquina ocupada (ciclo 4, não bloqueante 2; §0.7, item 3(b)).
  (f) **As frases** (não bloqueante 7): o §0 dizia «480 px garantidos à mensagem» (são 320); o
  §0.5, que a Levenfis p. 302 passava a ler «cada título com a sua página» (três de seis); e
  «idênticos em CER, decisão e texto» (os JSON guardam o texto só dos itens com CER acima de 0,05,
  os primeiros 200 caracteres — 70 itens; conferem todos os campos por item, e o texto nesses 70).
  Corrigidas no lugar.
- **O que fica, dito** (§0.3): as oito brechas novas do `test_strings` (a varredura não segue o
  dado); a Estrin pp. 29 e 77 (o B13 fora do grupo, em alemão) e a Estrin das minhas sondas lida
  em `ron+eng`; a tabela «nome | período» por colunas; o rodapé no aperto; as ações do Resultado
  abaixo da dobra; o portão só `offscreen`.

### 0.7 O ciclo 4 do crítico: REPROVADO com dois bloqueantes, e o que mudou

O crítico conferiu o bloqueante do ciclo 3 e o deu por resolvido nas páginas dadas (o
`construido.pdf` idêntico ao desligado nas três execuções, as notas reais de cinco livros 0 de 6,
18 páginas alemãs sorteadas na medida da Gallagher 0 de 18), mas reprovou por dois defeitos
(veredito em `OCR_UI_ANALISE_C2_CRITICAS.md` «Fase 5», ciclo 4). O construtor não contestou nenhum
item. (As edições de `rows.py` e dos testes no checkout principal a partir de ~17:20 eram deste
construtor, começando o ciclo 5 depois de ler o rascunho do veredito; o crítico mediu numa árvore
limpa dele do `7d41996`.)

- **1. O B13 intercalava as colunas de um índice quando a página tinha duas calhas ou mais**
  (bloqueante 1). A regra do ciclo 4 dizia que, de duas calhas ou mais, a da página é a vizinha de
  um bloco de prosa — e um índice não tem prosa: nenhuma calha valia, e tudo cruzava. Pelo
  importador de produção, contra a ordem do livro: a Flores (*Chess Structures*, raster, do acervo)
  pp. 460–464, «David 412 Galkin 198», a p. 462 **0,0230 → 0,7217** e as pp. 461 e 463 **aceitas**
  com CER ~0,7 (a desligada também troca a ordem: todos os nomes, depois todas as páginas); a
  Yusupov 4 p. 206 digitalizada 0,0465 → 0,7915; a Nunn p. 288 0,3212 → 0,7395; e as três colunas
  que o crítico compôs (`tres.pdf`) **aceitas** trocadas, 0,0007 → 0,7791 — «índice | índice |
  prosa» 0,0000 → 0,3575. E essas pp. 460–464 estavam nas 280 páginas das varreduras desde o ciclo 2,
  contadas entre «as que mudam» sem que ninguém dissesse se mudavam para melhor. O que mudou
  (`rows.py`, `arbiter.py`, `engines/base.py`, `ingest/pdf/ocr_service.py`; `test_table_rows.py`
  34 → 40, `test_arbiter.py` +2, `test_ocr_service.py` +1, e `test_indices_do_acervo.py`,
  novo):
  1. **a calha antes de toda coluna de índice é da página, menos a da primeira**
     (`index_column`, `_index_gutters`): uma coluna é de índice quando as palavras que abrem as
     linhas **na margem dela** sobem em ordem alfabética — ao menos 6 cabeças
     (`list_min_heads`), 80 % dos pares em ordem e metade subindo (sem acento, sem caixa: «Cámpora»
     entre os C); a margem é a da linha mais à esquerda a seis alturas de linha (a margem de uma
     página digitalizada deriva) com 1,5 caractere de folga, e o subverbete recuado sob o nome
     («Potkin / Carlsen 112», os adversários de cada jogador na Yusupov) fica de fora; uma linha que
     abre com número ou lance («279, 280», «P251») não tem palavra. Duas listas lado a lado são duas
     listas, o que quer que fique entre elas — as páginas da primeira, o vão entre o nome e as
     páginas dele. A mesma função serve a página e o teste;
  2. **a calha entre uma partida e uma coluna de texto é da página** (`_game_gutters`,
     `game_min_lines = 3`), qualquer que seja o número de calhas, haja ou não prosa: partida é um
     bloco de 3 linhas ou mais abertas por números de lance consecutivos com o lance na mesma linha
     («26 Re3 Bxd4»), ou a coluna dos números ao lado da dos lances (o alemão corta «26.» dos
     lances pelo ponto); texto é linha mais longa que uma célula que não é a partida nem os lances
     dela. É o conserto da franja do texto corrido (não bloqueante 1, abaixo): as notas que nenhuma
     regra chama de prosa, ao lado de uma partida, não a cruzam;
  3. **o texto do lado da partida é procurado na faixa ocupada mais perto**: o `find_gutters` acha
     também o rio de uma coluna de linhas curtas justificadas, os blocos dela ficam todos à esquerda
     do rio, e a faixa entre o rio e a calha da página ficava vazia — sem texto ao lado da partida
     (as páginas do índice da Dvoretsky na medida da Gallagher, 4 de 11 ainda juntadas na primeira
     versão deste ciclo);
  4. **a concordância entre os motores é medida na ordem em que cada um leu** (`arbiter._engine_order`,
     `engine_order_text`). Na Nunn p. 288 as três regras acima deixavam a leitura do Tesseract certa
     — CER **0,0193** —, e o importador saía **pior** que o desligado: 0,7516, a leitura do
     RapidOCR, intercalada. O RapidOCR não separa as duas listas porque o detector dele junta caixas
     através da calha («R352, 441, P29, 205, Ruge», `scratchpad/c5/probe_rapidocr.py`); e o árbitro
     o escolhia porque o B13 reordena a leitura do Tesseract **antes** de ela ser pontuada, e a
     concordância (`difflib`) comparava as linhas já movidas com as linhas por linha do RapidOCR: a
     do RapidOCR subiu de 0,1822 para 0,2936 e ele passou o Tesseract, 0,5854 × 0,5797
     (`scratchpad/c5/arbitro.py`). O B13 muda a ordem das linhas, não o que o motor leu: a
     concordância de cada leitura é medida na ordem do motor (a do Tesseract antes do B13, guardada
     quando ele reordena), e a confiança e a plausibilidade continuam julgando as linhas que o leitor
     recebe. Com isso o B13 não decide mais quem ganha: na Nunn p. 288 os escores ligado são os do
     desligado (0,5797 × 0,5631), ganha o Tesseract, e sai a leitura dele reordenada, 0,0193. **Medida
     e descartada:** a concordância nos dois sentidos do `difflib` (a heurística de lixo dele faz os
     dois sentidos darem números diferentes num texto longo: 0,2466 × 0,2936 na Nunn) também
     devolvia a Nunn, mas mudava o vencedor em páginas que o B13 nem toca — nas 268 páginas da
     primeira etapa da varredura (`scratchpad/c5/varre_simetrica/`, `cmp_varre_simetrica.out`), 7
     leituras desligadas mudaram: a Karpov 2 pp. 267 e 272 e a Vladimirov pp. 380, 384 e 385 **para
     pior**, com a leitura do RapidOCR intercalando as duas colunas linha a linha (a p. 267: de 5 para
     45 descidas da ordem alfabética em 108 verbetes), a Stean p. 154 para melhor («Kh1», «Rce1»,
     «fxg6», «Bxf6», «Bc6») e a Aagaard p. 190 igual (um caractere errado por outro). A
     varredura foi parada antes da segunda etapa.

  Cada regra com teste e sabotagem: o índice de três colunas, o de partidas com os subverbetes e a
  margem que deriva, e o de nomes com as páginas afastadas saem uma lista por coluna, e sem a
  regra (`list_min_heads` fora de alcance; `list_margin_chars` enorme, que conta os subverbetes)
  se intercalam; as notas da franja ao lado da partida inteira e da cortada à alemã não a cruzam, e
  sem a calha da partida cruzam; o rio não esconde a calha, e sem a faixa ocupada mais perto a
  calha some; uma lista de lances cruza duas calhas da página em ordem e nada pula uma faixa (o não
  bloqueante 3); a concordância é a da ordem de cada motor, e o B13 move as linhas do leitor sem
  mudar a concordância (a sabotagem, medida nas linhas movidas, a muda). E pelo importador, com o
  acervo (`test_indices_do_acervo.py`, lento, pula sem o acervo): a Flores pp. 460–464, a Nunn
  p. 288 e a Yusupov p. 206 digitalizadas sem linha que junte dois verbetes («205, Ruge») e com os
  nomes subindo em ordem alfabética — a verdade é a ordem do livro, conferida sem transcrevê-la —;
  sabotagens: sem as calhas de índice a Flores p. 462 junta as listas, e com a concordância nas
  linhas movidas a Nunn p. 288 sai intercalada.

  **Remedido** (as sondas do crítico com o código final; `scratchpad/c5/sondas3.sh`, importador
  sem `CAISSA_FIGURINE_TESSDATA`): a Flores pp. 460–464 0,6708 / 0,7224 / 0,0230 / 0,7117 / 0,4949
  (desligado) → **0,0438 / 0,0853 / 0,0230 / 0,0202 / 0,0364** (as pp. 461 e 463 continuam
  `accepted`, agora na ordem do livro); a Yusupov 4 p. 206 0,0465 = desligado; a Nunn p. 288 0,3212 →
  **0,0193**; a Nunn p. 289 **0,0174** e a Aagaard *Matter* p. 893 **0,0769** mantidas, e a p. 892
  0,6896 → **0,0958** (o ciclo 4 dava 0,6833); o `tres.pdf` nas quatro páginas **idêntico ao
  desligado** (0,0007, 0,0000, 0,0000 — «índice | índice | prosa» — e 0,0058 a 150 DPI,
  `accepted`, agora certas). **O que o crítico mandou manter:** o `construido.pdf` idêntico ao
  desligado (0,0052 `accepted`, 0,2284, 0,0367, 0,0754); a Karpov 2 p. 268 com o JSON igual ao do
  crítico no ciclo 4; as aberturas por extenso **0,0113**, a classificação 0,0909, o índice 0,1824,
  o controle 0,5280 (`tabelas_c2`), e o resto das tabelas do crítico, das páginas estreitas e da
  lista tabulada iguais às do ciclo 4; a Gallagher p. 50 em **0,2028** (WER 0,3121), a mesma do
  ciclo 4 — com a concordância nos dois sentidos, descartada, ela ia a 0,2000 com outra variante
  escolhida pelo árbitro, e voltou.
  O `table:2/4/7` a 150 DPI, na fila de A/B no commit: 0,0035/0,0036/0, iguais ao ciclo 4.

  **As varreduras, julgadas** (`scratchpad/c5/varre.sh` e `cmp_varre_c5.py`; cada página que muda
  com o diff em `scratchpad/c5/varre_diffs/`): as 280 páginas do crítico (a Gallagher inteira e as páginas finais de nove livros) com a leitura **desligada** igual à do ciclo 4 em 279 — a 280ª, a Stean p. 165, é a que a máquina sem memória degradou no ciclo 4, e voltou (item 3(d)) —; a ligada muda em **6**, as seis para melhor contra a ordem do livro: a Flores pp. 460–464 (o índice: linhas que juntam dois verbetes 7/17/31/2/7 no ciclo 4, 0/0/0/0/1 agora, e os nomes subindo em ordem — 3 descidas em 69 verbetes, 2 em 78, 2 em 78, 2 em 78 e 2 em 48) e a Gallagher p. 128 (o ciclo 4 juntava o ruído de um diagrama à prosa, «ae Hil aa now has a decisive blow. 25 Hed 1-0»; ela sai agora como com a regra desligada, o ruído em linhas dele e a prosa inteira); o B13 muda 41 das 280 do desligado (o ciclo 4, 43: a p. 462 da Flores e a Gallagher p. 128 deixam de mudar). a Estrin inteira em `deu+eng` (88 páginas), 25 da Gunderam (pp. 10–58) e 22 da Kmoch (pp. 10–52), rasterizadas a 300 DPI, com as duas leituras iguais às do ciclo 4 em todas as 135 (e mais 7 da Gunderam e 4 da Kmoch sem par no ciclo 4, que a varredura deste ciclo cobriu até o fim: o B13 não muda nenhuma); e os índices reais do ciclo 4 do crítico (Karpov 1 pp. 392–400, Aagaard *Matter* pp. 890–895, Yusupov 4 pp. 200–207, Nunn pp. 284–289; 29 páginas, pelo serviço, sem o B14): a leitura desligada igual à do crítico em todas; a ligada muda em 4 — três para melhor (Karpov 1 p. 398, 1 linha de dois verbetes no ciclo 4 e nenhuma agora; Yusupov 4 p. 206, 37 → 0; Nunn p. 288, 42 → 0, as três agora iguais ao desligado) e uma igual (Aagaard p. 893: o número da página, «893», sai numa linha dele no fim, e não colado ao título).
- **2. O teclado com a tecla, e não com a cadeia** (bloqueante 2). O conserto do ciclo 4 existia só
  na cadeia do foco: com a tecla (`QTest.keyClick`), o Tab parava no campo da verdade — um
  `QPlainTextEdit` que guarda o Tab — escrevendo tabulações, as figurinas e as seis ações fora de
  alcance; e o Shift+Tab das ações punha o foco em «Letras → figurinas», abaixo da dobra do cartão,
  com 0×0 px à vista nas três peles (a rolagem só segue o foco que anda dentro dela). O portão do
  teclado e o teste andavam pela cadeia e diziam «50/50» e «a tabela, o cartão, as ações». O que
  mudou: o campo da verdade deixa o Tab sair (`setTabChangesFocus(True)`, na Revisão de texto e na
  Rotulagem, que usam o mesmo cartão); o controle que recebe o foco dentro da rolagem rola para a
  vista também quando o foco entra vindo de fora dela (`widgets/foco_a_vista.RolagemSegueOFoco`,
  um filtro de `FocusIn` com `ensureWidgetVisible`, na Revisão de texto e na Rotulagem); a tabela
  das dúvidas deixa o Tab sair em vez de andar de célula em célula; o teste aperta a tecla da
  tabela até a última ação e de volta, conferindo a ordem e que cada controle focado tinha um
  pixel à vista **quando recebeu o foco**, com as duas sabotagens (a verdade guardando o Tab: as
  ações fora de alcance e a tabulação no texto; sem o filtro: o foco fora da vista); e o **portão
  do teclado anda com a tecla**, para a frente e de volta, e diz onde ela empaca, se escreveu no
  controle e quem recebeu o foco fora da vista (`VoltaDaTecla`; uma janela pequena com os dois
  defeitos montados à mão é a sabotagem dele, `test_teclado_tecla.py`). Ele achou os dois que o
  crítico nomeou fora da Revisão de texto — o «Comentário do lance» do Estudo, consertado no
  tronco (`37f662b`, com teste da tecla e a sabotagem), e a «Folha transcrita» do Texto, arquivo de
  outra sessão que trabalha nele agora: fica **REPROVADO** no portão, dito aqui e no §0.3 — e mais
  três que ninguém tinha nomeado: a **lista de lances do Estudo**, um `QTextBrowser` que anda de
  âncora em âncora pelo teclado — numa partida de 120 lances o Tab ficava nela 180 teclas, e de
  volta o Shift+Tab não saía mais (2.000 teclas, `scratchpad/c5/probe_lista_estudo.py`) —, agora
  uma parada do Tab (tronco `4f3e218`: sem a navegação de links pelo teclado; os lances pelas setas
  da sala, o clique continua; teste com a sabotagem); a **caixa de colar posição ou partida do
  Estudo**, cujo campo guardava o Tab (tronco `7a78367`, teste com a sabotagem); e a **«Leitura do
  motor» da Rotulagem**, que recebia o Tab com 0 px à vista a 1280×641 (o cartão numa rolagem,
  como na Revisão de texto; teste com o instrumento do portão e a sabotagem,
  `test_rotulagem_view.py`). No commit (`b6978ec`, tronco `7a78367`), o portão do teclado nas três peles e nos três tamanhos: as oito áreas e os catorze diálogos andam com a tecla nos dois sentidos, com o foco à vista, menos a «Folha transcrita» do Texto — REPROVADO, dito.
- **3. Os itens do mesmo ciclo.** (a) **A franja do texto corrido, com os números** (não
  bloqueante 1): 0–9 % das páginas, conforme o livro, têm notas que nenhuma regra de prosa segura
  (a triagem do crítico, `c4\risco_paginas.out`); com OCR o ciclo 4 embaralhava **12 das 29** (e
  pelo importador a Nunn p. 29 0,0824 → 0,6571, a p. 143 0,1778 → 0,7276, a Burgess p. 133 0,1016 →
  0,6213, em revisão). Com a calha da partida (item 1.2) e a faixa ocupada mais perto (1.3):
  **0 das 29** — e 0 das 41 com as 11 páginas do índice da Dvoretsky e a da Aagaard (o ciclo 4, 24
  das 41; `scratchpad/c5/sondas3/notas_risco_w24.out`, a cópia do `b13_notas_medida.py` do crítico
  com o ciclo 4 no lugar do 3) —, e as três inglesas pelo importador **idênticas ao desligado**
  (0,0824, 0,1778, 0,1016). (b) **A passada da vista do arnês espera a linha** (não bloqueante 2):
  as duas passadas, a da vista e a do rodapé, põem a linha do arnês e esperam ela assentar pela
  mesma função (`_assentar_a_linha`), e a vista grava `linha_reposta` e as áreas medidas fora da
  linha (não passa). A sabotagem nova, `--sabotar linha` (o produto reescrevendo a zona dos
  dispositivos a cada volta do laço), achou um furo do ciclo 4: a medida dizia «na linha do arnês»
  quando o texto das zonas batia na **saída** do laço — e com o produto reescrevendo sem parar a
  última volta repunha a linha e saía; o portão passava (medido com a pergunta antiga reposta no
  arnês, `scratchpad/c5/linha_antiga.py` → `linha_antiga.out`: PASSOU, «fora da linha em 0 áreas,
  reposta 1600×» na vista e «na linha True (reposta 200×)» no rodapé). Só uma linha que **assentou**
  conta; a sabotagem reprova nas duas passadas. (c) **Um teste
  para as três faixas de `crosses`** (não bloqueante 3):
  `test_a_move_list_crosses_two_page_gutters_in_order_and_nothing_jumps_a_band` — números, lances
  das brancas e das pretas em três faixas: uma lista de lances; os números e os lances das pretas,
  sem nada na faixa do meio, não se juntam; e as duas sabotagens reprovam — mais de duas faixas
  sempre cruzam (a primeira regra do ciclo 4), e um grupo que pode pular uma faixa. (d) **A Stean
  p. 165** (não bloqueante 4): a leitura que piorou com a máquina sem memória não era o B13 (nenhum grupo) —
  pelo caminho da varredura (o serviço com o B14 desligado, `stean165_varredura.py`) a leitura boa
  («$9.95 IN USA») é a do **RapidOCR** (0,866), que roda **no processo**, e não num trabalhador
  isolado; sem memória, o `onnxruntime` levanta na alocação (`RuntimeError: bad allocation`), o
  `OcrEngineBase.recognize` devolve uma leitura vazia com o aviso, e o árbitro fica com a do
  Tesseract (0,6891, revisão) — **0,9894** de semelhança com a degradada do ciclo 4 («£7-75 IN
  USA», a linha de lixo). A decisão é **revisão**; e nada na página dizia que um motor tinha
  falhado. Agora o `OcrEngineBase` marca a leitura vazia de uma falha (`failed`), e a página diz
  «região 0: o motor rapidocr falhou e a leitura seguiu sem ele — Falha inesperada no motor
  rapidocr: bad allocation» (teste com a sabotagem: a falha sem a marca, como antes, é calada). Um
  `MemoryError` o `OcrEngineBase` não pega: a página não sai (dito). E pelo importador de produção
  (o B14 ligado) a p. 165 é **sempre** a leitura do Tesseract, a degradada, em revisão
  (`stean165.py`): a guarda de figurinas não deixa o RapidOCR (0,9022) ancorar ali — o leitor de
  glifos vê figurinas nesta contracapa, por engano; sem a guarda o RapidOCR ancora e sai «$9-95 IN
  USA», e sem o B14 nada muda (`stean165_ancora.py`) —; fora do escopo desta fase, dito no §0.3.
- **O que fica, dito** (§0.3): a «Folha transcrita» do Texto empaca a tecla (arquivo de outra
  sessão); a «Folha transcrita» do Texto (arquivo de outra sessão); o RapidOCR que intercala as colunas de uma página cujo detector junta caixas através da calha (a razão por que a concordância nos dois sentidos foi descartada); a guarda de figurinas que tira o RapidOCR da Stean p. 165 pelo importador; o `MemoryError` que derruba a página; e, dos ciclos anteriores, as oito brechas do A15, a Estrin pp. 29/77 fora do grupo, o custo da reserva de 320 px e o nome a ~95 px, as ações do Resultado abaixo da dobra a 1280×641 (a tecla chega a elas e as mostra), o portão só `offscreen`.

## §B13 — A tabela e a lista de lances lidas por linha

- **Arquivos.** Suíte: `ocr/layout/rows.py` (novo: `rows_of_tables`, `table_groups`,
  `TableRowsConfig`), `ocr/arbiter.py` (`ArbiterConfig.table_rows`; aplicado ao resultado de todo
  motor em PSM 1/3 — o de segmentação própria —, antes do escore), `ingest/pdf/ocr_service.py`
  (`OcrServiceConfig.table_rows`, levado ao árbitro da página e das variantes),
  `tests/unit/ocr/test_table_rows.py` (novo, 16 → 24 no ciclo 2 → 29 no ciclo 3 → 34 no ciclo 4 → **40** no ciclo 5), `tests/unit/ingest/test_table_rows_page.py` (novo no ciclo 4: a página do crítico pelo importador, com o Tesseract) e `tests/unit/ingest/test_indices_do_acervo.py` (novo no ciclo 5: a Flores pp. 460–464, a Nunn p. 288 e a Yusupov p. 206 digitalizadas, pelo importador, com as sabotagens); ciclo 5: `ocr/arbiter.py` (`_engine_order`: a concordância na ordem de cada motor). O `bench_sol` já entrega o
  `SOL_CONFIG` inteiro ao `OcrServiceConfig`: nenhuma linha nova lá.
- **A regra** (a docstring de `rows.py` tem os números e a razão de cada um): blocos **lado a lado**
  (`x` disjuntos, `y` sobrepostos); o grupo nasce num bloco de **células** — linha mediana de até
  12 caracteres (a constante do RapidOCR) **e nenhuma linha acima de 24**, ou calha interna nas
  próprias linhas —, a coluna de células mais alta primeiro; cresce pelo vizinho cujas linhas
  acham par de altura no grupo em ≥ 80 % das vezes; bloco de prosa (≥ 3 linhas, mediana ≥ 30, sem
  calha) nunca entra; e **o grupo não cruza a calha da página**. O grupo sai linha a linha, cada
  linha da esquerda para a direita, no lugar do primeiro bloco. **Ciclo 2 do crítico** (§0.4, a
  docstring tem a razão de cada número): prosa também **por palavras** (2 linhas ou mais com a
  linha mediana de 4 palavras, contadas por célula quando o bloco tem calha interna); **uma
  numeração de lance por grupo** (números consecutivos, soltos ou seguidos de lance, e um número
  solto conta); a calha da página achada sobre **todas** as linhas e valendo quando há prosa de um
  dos lados; a calha interna de um bloco só faz células quando é 1,5× mais larga que o espaço
  mediano entre palavras; e **adjacência** — um bloco entra quando a maioria das suas linhas
  encontra o parceiro com espaço vazio entre eles. **Ciclo 3** (§0.5): a calha única com duas
  faixas de largura comparável vale sem prosa, e só uma lista de lances a cruza (números à
  esquerda, um lance por linha à direita); notas de variantes (metade das linhas com um número de
  lance dentro delas) são texto corrido; e a prosa por palavras pede linhas que continuam a frase.
  **Ciclo 4** (§0.6): texto corrido também sem contar palavras (4 linhas ou mais, a mediana acima
  de uma célula, um terço das linhas abrindo com palavra minúscula — um lance não é palavra); de
  duas calhas ou mais, a da página é a vizinha da prosa; e a avaliação separada do lance
  (`31 Nh1 !?`) é parte dele. **Ciclo 5** (§0.7): a calha antes de toda coluna de índice é da página (as cabeças na margem da coluna em ordem alfabética, ao menos 6), e a calha entre uma partida e o texto também, procurada na faixa ocupada mais perto; e o árbitro compara as leituras na ordem de cada motor — o B13 não decide quem ganha.
- **Duas regras que o corpus não pedia e a página real pediu.** Os itens de tabela do corpus são
  recortes. Na página inteira, a primeira versão puxou uma coluna para o meio da outra no Levenfis
  (1962, digitalizado, duas colunas): p. 40 com similaridade **0,857** com o desligado, p. 41
  **0,290** (`scratchpad/probe_b13_pages.py`, `difflib` sobre o texto final da página com
  `table_rows` ligado e desligado). Duas causas, cada uma rastreada bloco a bloco
  (`probe_b13_trace.py`): o bloco da coluna direita (lances curtos **e** uma linha de prosa,
  «Scopul a fost atins, tempoul a», com calha interna dos números de lance) valia como coluna de
  células e semeou; e o ruído que o Tesseract lê num diagrama da coluna esquerda semeou um grupo
  que atravessou a calha. Daí o teto de 24 caracteres por linha de célula, e a calha: **um
  corredor de ≥ 8 px dentro do vão que no máximo 10 % das linhas de prosa (≥ 30 caracteres) que
  alcançam os dois blocos tocam**, julgado com ≥ 8 dessas linhas. Um corredor, não o vão inteiro:
  o fragmento da lista da esquerda acaba antes da margem da coluna, e o vão até o bloco da direita
  começa dentro da prosa da esquerda (medido: 790–888, prosa até 800). **Só prosa conta:** a
  primeira versão contava toda linha e desfez o `table:4` a 150 DPI (18 linhas, e nada cruza o vão
  entre as colunas de uma tabela: **0,0036 → 0,64**, medido) — travado por
  `test_a_table_s_own_column_gaps_are_not_a_gutter`, cuja fixture é a leitura do produto; com a
  contagem antiga o grupo some (conferido).
- **Página real, regra final** (`probe_b13_pages.py`, `table_rows` ligado × desligado, sem o
  B14, `CAISSA_FIGURINE_TESSDATA` fora do ambiente; ciclo 2: `scratchpad/b13_c2_all.sh` →
  `b13_c2_all2.log`): **Levenfis pp. 36–52** — **15 de 17** idênticas, p. 41 idêntica (a primeira
  versão da regra a deixava em 0,290), p. 40 0,987 e p. 50 0,999 com a lista de lances lida por
  linha (`2. Re7—b7 De5—a5`, `3. Rb7—c8! Da5—a8-+`, `3. Nb3—c2-+- Rg6—g5`, antes um lance por
  linha, o branco longe do preto); **Estrin pp. 20–27** — 7 de 8 idênticas, a p. 20 só com ruído
  de diagrama; **Stefaniu pp. 40–47** — 8 de 8; **Kmoch pp. 28, 40, 44, 48 e 68** — 5 de 5 (a
  p. 44 era a do parágrafo com a calha espúria); **Gallagher pp. 48–55** (colunas de 22–27
  caracteres) — 7 de 8, a p. 50 com a lista de lances por linha (`26 ♖e3 Qxd4`, `27 Bxd4 ♖d6`,
  antes um número e um lance por linha). **Pelo importador de produção**, com a transcrição do
  crítico: a Gallagher p. 50 vai de CER **0,2732 → 0,2028** (a primeira regra: 0,7042), e as
  pp. 51–53 ficam idênticas ao desligado — a p. 53 já não põe o cabeçalho de «Game 17» nas notas
  da partida anterior; as três páginas que o crítico construiu (duas partidas lado a lado, uma
  partida nas duas colunas) ficam idênticas ao desligado. Nenhum grupo atravessa a calha.
- **Corpus, item a item** (`scratchpad/probe_table.py`, serviço de produção,
  `SOL_CONFIG={"table_rows": false|true, "ink_coverage": false}`): `table:2` 0,465 → **0,0035**,
  `table:4` 0,640 → **0,0036**, `table:7` 0,676 → **0**, a 150 DPI; os três nativos do
  Dvoretsky `17:401:52` 0,590 → **0,051**, `11:54:52` 0,381 → **0**, `13:278:52` 0,347 → **0**;
  as três tabelas a 300 DPI ficam em 0 dos dois lados.
- **Portão: PASSOU** (`bench_sol`, seis estratos, 747 itens; `f5_on_20260923_045448.json` ×
  `f5_b13_off_20260923_050724.json`, o B14 ligado nos dois; diferença pareada item a item com IC
  95 % bootstrap, `scratchpad/cmp_f5.py`):

  | | desligado | ligado | diferença pareada [IC 95 %] |
  |---|--:|--:|---|
  | `scan_degraded_150` CER | 0,0224 | **0,0094** (portão ≤ 0,020) | −0,0129 [−0,0308; 0,0000] |
  | `native` CER | 0,0235 | **0,0171** | −0,0054 [−0,0121; −0,0001] |
  | leiaute `table` (12 itens) | 0,1517 | **0,0038** | −0,1478 [−0,2718; −0,0385] |
  | leiaute `two-column` (52) | 0,0111 | 0,0111 | 0 (idênticos) |
  | leiaute `single` (666) | 0,0199 | 0,0179 | −0,0019 [−0,0046; −0,0000] |
  | `scan_clean_300`, `photo`, `fax_dither`, `shadow_curl_bleed` | — | — | 0 (idênticos) |

  (O IC do 150 DPI toca o zero porque só 3 dos 137 itens mudam — as três tabelas —, todos no
  mesmo sentido. **Ciclo 2:** `f5c2_on_20260923_083229.json` × `f5c2_b13_off_20260923_084509.json`,
  no código final, dão esta tabela item a item — a regra nova não muda nenhum dos 747.) Nos 747 itens o B13 muda **7**, e nenhum para pior: as três tabelas a 150 DPI e
  quatro listas nativas do Dvoretsky (`17:401:52`, `11:54:52`, `13:278:52` e `20:396:53`, 0,095 →
  0,081). O portão absoluto de 150 DPI do Sol, vermelho desde a fase 1, **fica verde**; `table:2/4/7`
  ≤ 0,05 (0,0035/0,0036/0); os três nativos do Dvoretsky < 0,15 (0,051/0/0); `two-column` e
  `single` sem regressão; ordem de leitura 1,0000; silenciosas 0; controles 0/9. A acurácia de
  lances não muda (0,8817 a 150 DPI, 0,9416 no nativo): ela conta os lances, não a ordem deles —
  o que o B13 conserta é o texto que a pessoa lê.
- **Sabotagem.** `SOL_CONFIG='{"table_rows": false, "ink_coverage": true}'` devolve os números da
  fase 4 nos estratos que o B14 não toca, ao décimo de milésimo (150 DPI 0,0224, nativo 0,0235,
  `scan_clean_300` 0,0054; os seis itens com o CER da fase 4). Nos testes: duas colunas de prosa de
  linhas alinhadas → nenhum grupo; sem o teto de 24 **e** sem a calha, o bloco da coluna direita da
  p. 40 semeia e puxa a esquerda (cada regra sozinha o segura); sem a calha, duas colunas de
  células atravessam a calha da página. Ciclo 2, cada regra com a sua: sem a prosa por palavras e
  sem a numeração (`prose_words=999`, `numbered_share=2.0`), a coluna estreita de notas entra na
  lista de lances da outra coluna; contando as palavras sobre a linha inteira e não por célula, o
  `table:2` vira prosa; com a calha interna de qualquer largura, o parágrafo da Kmoch p. 44 com a
  calha espúria volta a semear (`[[20, 12]]`); sem a adjacência, «The | so-called | “Long» vira
  uma linha de três células; e duas partidas numeradas lado a lado, ou uma partida que continua na
  outra coluna, não se juntam.

## §B14 — A leitura que não cobre a tinta não é aceita, e a variante roda

- **Arquivos.** Suíte: `ocr/coverage.py` (novo: `ink_map(gray, dpi)` → `InkMap`, `ink_coverage(result,
  ink)`), `ingest/pdf/ocr_service.py` (`OcrServiceConfig.ink_coverage`, `min_ink_coverage=0.90`;
  `RegionRecognition.ink_coverage`; em `_wants_variants` a leitura incompleta pede as variantes
  mesmo aceita; em `_settle` a incompleta não ancora quando há uma completa e nenhuma incompleta sai
  `ACCEPTED`), `ocr/fusion.py` (`fuse_candidates(incomplete=…)`: a âncora prefere a leitura
  completa), `benchmarks/fit_ink_coverage.py` (novo: o piso ajustado **só na `calib`**, a `dev`
  impressa ao lado), `ocr/gates.py` e `benchmarks/bench_sol.py` («aceitos errados» — aceitos com
  CER > 0,10 — no resumo de cada estrato e no `sol.md`), `tests/unit/ocr/test_ink_coverage.py`
  (novo, 17 → **19** no ciclo 2: a moldura e a região não medida), `tests/unit/ocr/test_sol_metrics.py`
  (+1).
- **A medida** (os números e a razão de cada um estão em `CoverageConfig`): o fundo estimado por
  fechamento morfológico (0,2 pol), tinta abaixo de 0,62 do fundo; **letra** é o componente de
  0,03–0,25 pol de altura (o teto físico do B11), razão de aspecto ≤ 25; as letras esfregadas duas
  alturas-x na horizontal formam corridas, e só a corrida que é **linha de texto** conta (razão de
  aspecto ≥ 3, altura ≤ 3,5× a mediana — as linhas reais da foto medem 2,2–2,9× —, ≥ 0,4 letra
  por altura de linha); coisas maiores que 4× a mediana (fotos, figuras) e as caixas de diagrama
  que o chamador passa (`page_context`) ficam fora — **menos a moldura do scanner** (ciclo 2): um
  componente cuja caixa ocupa metade da imagem ou mais é a borda escura da digitalização, e dentro
  dela está a página (`CoverageConfig.frame_area_share`; a Kmoch pp. 40/44/48 tinha **0 letras**
  com a borda e passa a 1.058/1.162/995); cada letra pesa um. A região que a medida não julga
  (menos de 12 letras, ou tinta que as regras deixaram de fora) é **dita** no rastro — «cobertura
  da tinta não medida (N letras) — o B14 não julga esta região» —, e não calada. A cobertura é a fração das
  letras sob as caixas de palavra (com 0,35 da altura de folga); com menos de 12 letras, nenhuma
  palavra (`None`). Uma passada por página: **142–229 ms** numa página de 300 DPI com a máquina
  ocupada (`scratchpad/probe_b14.py`).
- **O piso, ajustado na `calib`** (`benchmarks/fit_ink_coverage.py --out
  benchmarks/reports/sol/f5_b14_fit2.json`, serviço **sem** o B14, a cobertura mínima das regiões de
  cada leitura; «perdida» = CER > 0,10, «boa» = CER ≤ 0,02):

  | piso | `calib` sinaliza | perdidas | boas | aceitas-perdidas | `dev` sinaliza | perdidas | boas | aceitas-perdidas |
  |---|--:|--:|--:|--:|--:|--:|--:|--:|
  | 0,80 | 1 | 1/16 | 0/182 | 1/8 | 6 | 6/30 | 0/359 | 4/21 |
  | 0,85 | 3 | 3/16 | 0/182 | 3/8 | 15 | 15/30 | 0/359 | 11/21 |
  | 0,88 | 6 | 6/16 | 0/182 | 6/8 | 19 | 19/30 | 0/359 | 15/21 |
  | **0,90** | **6** | **6/16** | **0/182** | **6/8** | 21 | 21/30 | 0/359 | 17/21 |
  | 0,92 | 7 | 7/16 | 0/182 | 6/8 | 21 | 21/30 | 0/359 | 17/21 |
  | 0,96 | 10 | 8/16 | 0/182 | 6/8 | 24 | 23/30 | 0/359 | 19/21 |

  A regra, dita antes de olhar a `dev`: o piso que sinaliza o máximo de aceitas-perdidas da `calib`
  sem sinalizar uma boa. **Ela não escolhe** (o crítico mediu, ciclo 1, não bloqueante 2): toda
  leitura boa da `calib` tem cobertura 1,0, e todos os pisos de 0,8757 a 0,99 sinalizam as mesmas
  seis perdidas (a sétima está em 0,9000 exatos). O desempate — **o menor piso na grade de décimos
  que atinge o máximo: 0,9** — foi escrito **depois** de a `dev` ter sido vista, e fica dito
  assim; na grade de centésimos seria 0,88, e a `dev` diria 15 das 21 aceitas-perdidas em vez de
  17, com 0 das 359 boas nos dois. A resolução de décimos é a que 16 leituras perdidas na `calib`
  sustentam. Com a regra da moldura o ajuste foi refeito (`f5_b14_fit3.json`, versionado em
  `docs/quality/sol/`): idêntico ao `fit2` byte a byte — nenhum item do corpus tem moldura.
- **Na população real, pelo importador** (`scratchpad/b14_population.py`/`b14_population2.py`: o
  `import_pdf` de verdade, com o localizador de diagramas passando as caixas ao serviço, e um
  `OcrService` que grava a cobertura de toda região): Estrin pp. 20–27 (80 regiões medidas, a menor
  0,969), Levenfis pp. 40–51 (240, a menor 0,931), Stefaniu pp. 40–51 (184, a menor **0,900**) —
  **nenhuma** das 504 sinalizada; Kemeri, Neumann e Boleslavski têm camada de texto (o B14 não se
  aplica: 0 regiões de raster). **A folga é fina em região pequena:** as menores do Stefaniu são
  cartões de ~20 letras, onde duas letras fora já dão 0,90 — no piso, não abaixo. Se o campo
  mostrar revisão demais nessas, a alavanca é um mínimo de letras perdidas (uma palavra), não o piso.
  **Ciclo 2, com o código final** (`scratchpad/b14_final.sh`): nos mesmos três livros,
  Estrin pp. 20–27 (79 regiões medidas, a menor 0,919), Levenfis pp. 40–51 (240, a menor 0,931) e Stefaniu pp. 40–51 (110, a menor **0,900**) — nenhuma das 429 sinalizada. As contagens diferem das 504 do ciclo 1 em dois lugares: a Estrin do ciclo 1 foi medida com o classificador de diagramas indisponível (a `CAISSA_FIGURINE_TESSDATA` no ambiente, que o importador recusa — o log daquela corrida diz isso); e a p. 49 do Stefaniu saiu então em 83 regiões do tamanho de uma linha e sai hoje em 9 de parágrafo — a corrida de 04:15 mediu um `rows.py` intermediário, anterior ao commit do ciclo 1 (o log dela registra 96 regiões fundidas no Stefaniu), e o código commitado, o do ciclo 1 (`99546e9`) e o final, dá 9: as 83 eram daquela regra, e o número do ciclo 1 não se refaz com código commitado (crítico, ciclo 2). Nos oito livros e páginas que o crítico mediu no ciclo 1, pela sonda dele
  (`b14_populacao.py`): Stean, Aagaard (a menor 0,976), Flores Rios (0,999) e Silman sem nenhuma;
  **6 sinalizadas de 95 medidas**, todas já em revisão ou abstenção — Reinfeld 1977 pp. 100/102/103
  (0,571–0,775, abstenções: ruído lido em diagrama), Karpov p. 103 (0,709) e Vladimirov p. 201
  (0,565), também ruído de diagrama, e a Gallagher p. 50 (0,896, a página de colunas estreitas, CER
  0,20 — no ciclo 1 eram três na Gallagher, nas pp. 50 e 52 que a primeira regra do B13
  rearrumava; com a final a p. 52 sai como com o B13 desligado, e nenhuma região dela fica abaixo
  do piso). A Kmoch, rasterizada com a moldura: 55 regiões medidas nas pp. 40/44/48, nenhuma
  sinalizada, a menor 0,953 (`b14_moldura_final.py`).
- **Portão: PASSOU** (`f5_on_20260923_045448.json` × `f5_b14_off_20260923_051900.json`, o B13
  ligado nos dois; `scratchpad/cmp_f5.py`):

  | estrato | CER desligado | CER ligado | diferença pareada [IC 95 %] | aceitos errados | revisão | s/MP* |
  |---|--:|--:|---|--:|--:|--:|
  | `photo` | 0,0983 | **0,0207** | −0,0776 [−0,1113; −0,0488] | 20 → **1** | 16 → 17 | 6,93 → 8,51 |
  | `fax_dither` | 0,0382 | **0,0249** | −0,0133 [−0,0258; −0,0029] | 4 → 1 | 19 → 21 | 5,40 → 5,51 |
  | `shadow_curl_bleed` | 0,0377 | 0,0359 | −0,0017 [−0,0051; 0,0000] | 5 → 4 | 27 → 28 | 6,06 → 5,93 |
  | `native`, `scan_clean_300`, `scan_degraded_150` | — | — | 0 (idênticos) | 1 → 1, 0, 0 | = | ≈ |

  **Aceitos com CER > 0,10: 30 → 7**, nenhum estrato sobe e nenhum entrou. Dos 30: **18** saem
  aceitos e certos (a variante que o B14 pediu leu o texto inteiro: CER mediano 0,0039, máximo
  0,0296 — `authored:de:4` 0,230 → 0, `authored:es:8` 0,266 → 0, `synth:Xadrez Vitorioso…:131:52`
  0,243 → 0,013), **5** vão para a revisão também com o texto bem melhor
  (`synth:Dvoretsky…:201:21` 0,786 → 0,007, `authored:en:21` 0,204 → 0,028), **7** ficam (§0.3). Nos
  747 itens o B14 muda 27, **nenhum para pior**; uma leitura em revisão passa a aceita
  (`authored:pt:18@photo` 0,29 → 0). Silenciosas 0, controles 0/9. *O `s/MP` destes JSON carrega a
  contenção da máquina (§ cabeçalho): a foto paga as variantes (+23 % nesta comparação, entre
  corridas de contenção parecida).
- **Sabotagem.** `SOL_CONFIG='{"table_rows": true, "ink_coverage": false}'` devolve os 30 e os
  números da fase 4 nos três estratos que o B14 toca, ao décimo de milésimo (foto 0,0983, fax
  0,0382, sombra 0,0377) — na primeira fila e na do ciclo 2 (`f5c2_b14_off`, item a item igual).
  Nos testes (`test_the_sabotage_switch_accepts_the_partial_reading_again`): com o interruptor
  desligado a leitura que perdeu as últimas linhas volta a sair `ACCEPTED`. Ciclo 2: sem a regra
  da moldura (`frame_area_share=1.01`), a página com borda escura volta a 0 letras; e a região de
  poucas letras sai com a nota no rastro.

## §B15 — O fax, depois do B14

- **Absorvido pelo B14, sem código próprio.** O §3d mandava medir o fax depois do B14 e só entrar
  com a rota do pontilhado (upscale + segundo motor) se o número não viesse. Veio: `fax_dither`
  **0,0382 → 0,0249** com o B14 (diferença pareada −0,0133 [−0,0258; −0,0029], fora do IC), abaixo
  do alvo de 0,0312 que a fase 4 tinha nomeado — e o B13 não toca o fax (idêntico ligado ou
  desligado). O `authored:en:21`, que a fase 4 citou como a linha inteira perdida (cobertura 0,847),
  sai 0,204 → 0,028; dos 4 aceitos errados do fax fica 1 (`authored:de:1`, 0,139, cobertura 0,964:
  erra dentro da tinta que leu). Acurácia de lances do fax 0,8201 → 0,8505.
- **Portão: PASSOU** (`fax_dither` ≤ 0,0312). **Sabotagem:** a do passo que entrou — o B14
  desligado devolve 0,0382.

## §A14 — As ligaduras da camada de texto

- **Arquivos.** Suíte: `ocr/engines/normalize.py` (`text_layer_flags(mode)`: as bandeiras padrão
  do PyMuPDF para o modo **sem** `TEXT_PRESERVE_LIGATURES` — nada mais muda), `ocr/engines/
  pdf_text_layer.py` (as cinco leituras da camada: `text`, `dict` ×2, `rawdict`), `ocr/layout/
  analyze.lines_from_pdf_page`, `index/sources.PdfTextSource.units`,
  `tests/unit/ocr/test_text_layer_ligatures.py` (novo, 6).
- **Por que as bandeiras e não o `fold_result`.** O MuPDF, com a bandeira desligada, divide a
  ligadura nas letras **e a caixa entre elas** (`ﬁ` → `f` com a caixa, `i` com largura zero no fim):
  o nível 0 é a leitura que guarda caixa por caractere (`rawdict`), e trocar o texto da palavra sem
  trocar os caracteres deixaria `char_box(offset)` apontando para a letra errada. O teste confere
  `len(word.chars) == len(word.text)`.
- **Portão.** Polgar, páginas 6–10 (índices 5–9), as 19 ligaduras que `page.get_text("text")`
  devolve com as bandeiras padrão: **0** no nível 0 (`recognize_page(force=True)`), **0** nas
  linhas de leiaute, **0** no índice de busca (`PdfTextSource(max_pages=10)`); `½`, `²`, `№`
  ficam. **Sabotagem:** as bandeiras antigas no nível 0 (`monkeypatch` de `text_layer_flags`) →
  a ligadura volta (`test_the_sabotage_old_flags_bring_the_ligature_back`). O IR do importador já
  saía com 0 — a correção vale para o que lê a camada por fora do importador: o OCR de contestação
  (onde o nível 0 ancora regiões), o leiaute por página e a busca.

## §C17 — A régua do campo para a decisão do `.pt` (§10.2)

- **Arquivos.** Tronco: `field_eval.py` (`FieldReport.diagrams`: uma linha por diagrama casado —
  livro, página, índice, `legal`, `gate_confidence`, `min_confidence`, `exact` na régua anotada,
  `contaminated` —, somada por `_accumulate`, fora do `as_dict` para não inchar os relatórios
  publicados), `tests/test_field_eval.py` (+1: as linhas refazem o gate em qualquer limiar).
  Suíte: `benchmarks/field_exact.py` (leva as linhas adiante), `benchmarks/model_ruler.py` (novo),
  `tests/unit/classify/test_model_ruler.py` (novo, 10).
- **Medição** (`benchmarks/model_ruler.py --runs 3 --tag f5_c17`, régua corrigida do
  `field_exact`, recall do pacote de produção, sem motor UCI; cada modelo três vezes, as linhas por
  diagrama **idênticas** nas três — o harness recusa se não forem; 51–103 s por execução, com a
  máquina ocupada): `benchmarks/reports/model_ruler_20260923_043817_f5_c17.json`. 114 diagramas
  casados e julgáveis por modelo. «≤ k err» é o maior número de diagramas **exatos** exportados com
  no máximo k errados, e o portão que o consegue — **calculado em todo valor distinto de confiança**
  (`model_ruler.cuts`), e não na grade de 0,30 a 0,99 da primeira versão (§0.4). A tabela abaixo é
  o resumo refeito sobre as mesmas linhas (`--linhas-de …_f5_c17.json --tag f5_c17_c2`):

  | modelo | exatos | gate 0,80: exp / err | ≤ 0 err (portão) | ≤ 1 err | ≤ 2 err | AURC |
  |---|---:|---:|---:|---:|---:|---:|
  | **produção** | 107 | **103 / 1** | 74 (0,9980) | 103 (0,5731) | 103 (0,4950) | 0,0063 |
  | `c4_aug0_s42` | 105 | 104 / 2 | 76 (0,9899) | 99 (0,9255) | 104 (0,7195) | 0,0070 |
  | `c4_aug0_s43` | 104 | 102 / 2 | 97 (0,9012) | 98 (0,8548) | 102 (0,7687) | 0,0056 |
  | `c4_aug0_s44` | 110 | 101 / 0 | 104 (0,7067) | 105 (0,6470) | 110 (0,3459) | 0,0017 |
  | `c4_mhsp_s42` | 106 | 105 / 1 | 103 (0,8457) | 104 (0,8246) | 105 (0,5567) | 0,0036 |
  | `c4_mhsp_s43` | 102 | 104 / 3 | 43 (1,0000) | 99 (0,8958) | 99 (0,8702) | 0,0134 |
  | `c4_mhsp_s44` | 105 | 86 / 0 | 91 (0,7247) | 92 (0,6455) | 103 (0,5006) | 0,0063 |
  | `c4_mhspe_s42` | 102 | 102 / 3 | 99 (0,8768) | 99 (0,8620) | 99 (0,8081) | 0,0077 |
  | `c4_mhspe_s43` | 102 | 98 / 4 | 43 (0,9998) | 87 (0,9512) | 89 (0,9193) | 0,0183 |
  | `c4_mhspe_s44` | 104 | 102 / 2 | 38 (1,0000) | 100 (0,8823) | 104 (0,6635) | 0,0122 |
  | `c4_e_s42` | 108 | 100 / 2 | 96 (0,9287) | 96 (0,8977) | 102 (0,6376) | 0,0051 |
  | `c4_e_s43` | 107 | 98 / 2 | 31 (0,9997) | 95 (0,8449) | 103 (0,5738) | 0,0142 |
  | `c4_e_s44` | 109 | 100 / 1 | 27 (0,9996) | 101 (0,7735) | 108 (0,3699) | 0,0139 |
  | `c4_x10_s42` | 108 | 72 / 0 | 93 (0,6886) | 101 (0,5646) | 101 (0,5427) | 0,0042 |
  | `c4_w3_s42` | 109 | 104 / 2 | 78 (0,9900) | 99 (0,8905) | 106 (0,5927) | 0,0052 |

  **Empates na AURC:** o risco dentro de um empate de confiança é a sua média sobre todas as ordens
  do empate — depois de `j` dos `k` diagramas empatados, `j·g/k` dos `g` errados dele (linearidade
  da esperança); a primeira versão tomava a ordem que o `sorted` deixava, e quatro modelos se
  moviam por ela (`c4_mhspe_s44` 0,0112 → 0,0122 agora, sem depender da ordem).
- **Portão: PASSOU.** No gate 0,80 a produção exporta **103 com 1 errado — 102/103**, o número do
  `field_exact` publicado. **Sabotagem** (`--sabotar embaralhar --linhas-de …_f5_c17.json`: os
  rótulos de exatidão redistribuídos com semente fixa sobre as **mesmas** linhas;
  `model_ruler_20260923_074145_f5_c17_c2_sabotado.json`): o AURC de todo modelo piora (produção
  0,0063 → 0,0579), as três colunas «≤ k err» caem a 0 em 5 dos 15 e, nos outros 10, a «≤ 0» fica
  entre 0 e 27 (verdadeira: 27–104) — as de ≤ 1 e ≤ 2 guardam uma parte em três (`c4_aug0_s44`
  71/92, `c4_w3_s42` 66/88, `c4_e_s44` 11/66, contra 105/110, 99/106 e 101/108 de verdade) —, e a
  ordem dos modelos pelo AURC fica com **tau de Kendall +0,31** contra a verdadeira — a régua lê a
  verdade, não as confianças. Nos testes: a mesma sabotagem sobre dois modelos construídos; o caso
  do crítico (um erro a 0,9979 com 74 exatos acima: a grade antiga acha 0, os cortes acham 74); e a
  AURC de um empate igual nas duas ordens.
- **O que a régua diz para §10.2** (a troca continua da pessoa). (1) O único errado que a produção
  exporta (Burgess p. 60 d2) está a **0,9979**, abaixo de 74 exatos: com zero errados a produção
  exporta **74** (portão 0,998) — a primeira versão dizia «nenhum limiar exporta com zero erros»,
  artefato da grade (§0.4). (2) Com zero errados, as variantes vão de 27 a 104 **conforme a
  semente**: `aug0` 76/97/104, `mhsp` 103/43/91, `mhspe` 99/43/38, `e` 96/31/27 — a variância entre
  sementes é maior que a diferença entre variantes, o mesmo veredito da fase 3 (§C4) agora na régua
  do dano. (3) Com um errado, a produção entrega 103; `c4_aug0_s44` 105 e `c4_mhsp_s42` 104 são uma
  semente cada. (4) O `x10` (ruído de rótulo) exporta 72 no gate, mas **não** é pior na curva: 93
  exatos com zero errados — é outra escala, como a fase 4 suspeitou. Nada a trocar com uma semente;
  o que decidiria é a mesma curva com três sementes da variante escolhida contra a produção
  retreinada nas mesmas três.

## §C18 — A janela cabe no portátil, e o que cabe fica à vista

- **Arquivos.** Tronco: `qt/rodape.py` (a mensagem, os dispositivos e a ocupação em
  `RotuloElidido` — a frase inteira na dica e em `mensagem()`/`dispositivos()`; ciclo 2: **480 px
  garantidos à mensagem** enquanto ela está na tela, `LARGURA_DA_MENSAGEM`, e o botão «Mensagens»
  com o mínimo dele), `qt/campo.py` (a barra de anotação numa `BarraFluida`, a mesma da barra do
  visor: os botões descem de linha em vez de somar), `qt/painel_principal.py` (cada modo da aba
  Livro dentro de uma rolagem, a API devolvendo o painel de dentro; ciclo 2: **barra horizontal
  quando o modo não cabe**), `qt/painel_da_galeria.py` (ciclo 2: a navegação numa `BarraFluida`),
  `tests/test_qt_janela_cabe.py` (novo, 8 → **14**), `tests/test_qt_rodape.py` (ciclo 2: a faixa do
  teste de elisão). Suíte: `ui/widgets/rotulo_que_encolhe.py` (novo: pinta elidido, `text()`
  continua inteiro, mínimo zero), `ui/widgets/fileira_fluida.py` (novo no ciclo 2: a fileira que
  desce de linha em vez de somar — o mínimo é o maior controle, a altura acompanha a largura),
  `ui/views/rotulagem.py` (os rótulos de estado; ciclo 2: as duas barras fluidas),
  `ui/widgets/cartao_da_linha.py` (o contexto; ciclo 2: o recorte quebra linha e a imagem escala à
  largura que houver, as teclas de figurina numa fileira fluida), `ui/views/revisao_de_texto.py`
  (o cartão numa rolagem — ciclo 2: com barra horizontal quando precisa — e as duas fileiras de
  botões fluidas), `ui/audit/minimo.py` (novo: o portão; ciclo 2: a vista, a linha cheia do rodapé
  e as sabotagens `corte`, `mensagem` e `aperto`), `tests/unit/ui/test_rotulo_que_encolhe.py`
  (novo, 4), `tests/unit/ui/test_fileira_fluida.py` (novo, 3).
- **Onde estava o mínimo, medido** (pele Foco, áreas visitadas, livro aberto; `scratchpad/
  probe_chain.py`, `probe_minsize2.py`): o divisor somava as abas (piso declarado 540) + o lado do
  visor **992** — o visor (520) empilhado com a barra de anotação (**810**: combo 198 + botões 178
  + 166 + 250 + vãos) mais o trilho (176); o rodapé pedia **1.246** com a frase de importação no
  `QLabel` da mensagem; na altura, o modo mais alto da aba Livro (o Resultado, **520**). Fora do
  mínimo da janela, mas cortando o conteúdo das abas: a linha de estado da Rotulagem pedia
  **2.868** px e o contexto do cartão, **1.056**.
- **Portão, primeira versão** (`caissa.ui.audit.minimo`: um subprocesso por pele, áreas visitadas,
  frase de 300 caracteres no rodapé, teto 1250×640; `docs/quality/ui/c2_fase5/minimo_20260923_074522.json`
  sem livro e `…_074539.json` com o Kemeri): **PASSOU** — Clássica **1248×606**, Foco **1248×640**,
  Fita **1246×629**, idênticos com e sem livro; sabotagem `rodape` → 2206×606 / 2206×640 /
  2194×629. **O crítico reprovou (bloqueante 2): a janela cabia escondendo** — o portão lia só o
  `minimumSizeHint`, e as rolagens desligavam a barra horizontal (§0.4).
- **Portão, ciclo 2: caber e estar à vista.** No mínimo da janela e a 1366×728, em **toda área**:
  nenhum controle (botão, rótulo com texto, campo, lista de escolha) fora da vista **sem uma barra
  de rolagem que leve a ele**; nenhum espremido abaixo de 90 % do próprio mínimo (o acolchoamento de
  um botão é de 8–16 px: 40 de 42 px come a borda, 57 de 107 é meia palavra); e o rodapé **com a
  linha cheia**, que o arnês põe (§0.1) — o nome de 149 caracteres, a frase de 300 e uma importação
  com a ocupação e a barra —, a mensagem com ao menos 320 px e nenhum botão dele espremido. Um
  controle de 1 ou 2 px só fica fora da conta quando o próprio mínimo também é esse (um separador,
  um rótulo elidido sem espaço): o botão com 1 px escapava por aí. **PASSOU**, sem livro e com o
  Kemeri (`docs/quality/ui/c2_fase5/minimo_20260923_114931.json` e `…_114945.json`): Clássica
  1248×606, Foco 1248×640, Fita 1246×629; nas duas larguras 0 fora da vista sem barra e 0
  espremidos, com 17–72 controles guardados pela rolagem e alcançáveis pela barra; a mensagem com
  **480 px** e o nome do livro com 418–554 px. Uma segunda corrida completa deu os mesmos números.
- **Sabotagens, uma por regra — as quatro REPROVARAM** (`…/minimo_sabotado_{rodape,corte,mensagem,aperto}_20260923_11*.json`):
  `rodape` (os rótulos do rodapé em `QLabel` comum) → mínimo **2208×606 / 2208×640 / 2190×629**;
  `corte` (toda rolagem sem barra horizontal, como na primeira versão) → 3 controles do Resultado
  fora da vista sem barra a 1248 px na Clássica e na Foco («Copiar FEN», «Limpar» e a frase de
  estado; a Fita, que arruma o Resultado de outro jeito, não perde nenhum); `mensagem` (sem o piso)
  → a mensagem com **0 px** e o nome com 885–931 px; `aperto` (o botão «Mensagens» com o piso de um
  pixel de antes) → **1/82 px** (1/76 na Fita) em toda área, nas três peles e nas duas larguras.
- **O que o portão estendido achou além do crítico** (consertado no ciclo): quinze controles da
  Rotulagem espremidos até a metade do texto («Adicionar PDF…» com 57 de 107 px, a lista de
  projetos com 56 de 218) e quatro da Galeria — as fileiras fluidas; e, com o livro aberto e a
  importação em curso, o botão «Mensagens» com **27 de 82 px**. Ele tinha um piso de um pixel,
  escrito para não subir a largura mínima da janela; mas quem cede nesta linha são os rótulos
  elididos, e sem o piso o mínimo do rodapé com tudo à vista fica abaixo de 950 px — quem decide a
  largura continua sendo o modo (`test_o_botao_de_mensagens_fica_com_o_seu_minimo_com_a_linha_cheia`,
  com a sabotagem ao lado). O teste de elisão do rodapé (`test_sem_folga_ele_volta_a_elidir`)
  montava uma faixa inteira de 320 px, que a janela nunca tem, e passou a dar os 320 px **ao nome**,
  somados ao mínimo da faixa.
- **Ciclo 3: as quatro zonas do rodapé, e as ações da Revisão de texto fora da rolagem** (§0.5). A
  reserva da mensagem é a frase até 320 px, dispositivos e ocupação têm o texto inteiro até 240 px,
  e cede o nome do livro; os pisos são do `RotuloElidido` (`piso=…`, medidos com a fonte de agora).
  O portão mede as quatro zonas, com o nome mais longo e um comum, e a sabotagem `reserva` (o
  rodapé do ciclo 2) reprova com as duas zonas em 0 px. Nos testes do tronco
  (`test_qt_janela_cabe.py`, 14 → 17): a garantia de cada zona curta, a reserva de uma frase curta
  e a sabotagem -- a garantia é cobrada na fonte que o teste tiver (o Qt desta instalação não acha
  a Segoe UI fora da suíte), os números do produto são os do portão.
- **Teclado** (`caissa.ui.audit.teclado --pele foco --pdf …Kemeri`, o comando do crítico no ciclo 1,
  com as árvores dos ciclos 2 e 3): **PASSOU** a 1280×800 e a 1248×640 — toda área com o `Tab` alcançando
  todos os focáveis e fechando (Resultado 37/37, Revisão de texto 50/50, Rotulagem 65/65, Galeria
  57/57): as fileiras fluidas não mudaram a ordem de ninguém — mas tirar as ações da Revisão de
  texto da rolagem (ciclo 3) mudou: elas passaram a vir logo depois da tabela, antes do cartão que
  fica acima delas, e este relatório disse o contrário (o crítico, ciclo 3; o portão do teclado
  conta alcance, não ordem). **Ciclo 4:** a cadeia do foco é posta à mão — a tabela, o cartão de
  cima para baixo, as ações —, e um teste compara a ordem com a posição, com a sabotagem ao lado
  (§0.6). Ciclo 4, no commit: PASSOU a 1280×800 e 1248×640 (Revisão de texto 50/50, Rotulagem 65/65, Galeria 57/57, Resultado 37/37), e a ordem que o portão grava vai da tabela (10) à leitura, às alternativas e à verdade (11–13), às figurinas (14–20) e às seis ações (21–26) — no ciclo 3, as ações eram 11–16 e o cartão 17–26 (`docs/quality/ui/c2_fase5/teclado_foco_20260923_1837*.json`). **Mas essa ordem era a da cadeia, e não a da tecla** (crítico, ciclo 4): o portão andava por `focusNextPrevChild`, e o `QPlainTextEdit` da verdade guarda o Tab. **Ciclo 5:** o campo da verdade deixa o Tab sair, o cartão rola até o foco que entra de fora, e o portão aperta a tecla (`QTest.keyClick`) nos dois sentidos e mede o foco à vista (`visibleRegion`) — no commit, PASSOU nas oito áreas menos o Texto e nos catorze diálogos, nas três peles e a 1280×800, 1248×640 e 1280×641, nos dois sentidos e com o foco à vista; ele achou, antes dos consertos, o comentário, a lista de lances e a caixa de colar do Estudo (tronco `37f662b`, `4f3e218`, `7a78367`) e a «Leitura do motor» da Rotulagem, e acha a «Folha transcrita» do Texto (outra sessão; §0.3).
- **A Foco fica no teto, e quem a segura é a Galeria do tronco.** Descendo pelo filho mais alto de
  cada nível (`scratchpad/probe_altura.py`): a pilha de áreas pede 516 px, e a página que pede 516
  é o `PainelDaGaleria` (Dataset 317, Rotulagem 266, Revisão de texto 135, Livro 91); a Foco soma
  124 px de cromo a isso, a Clássica 90. O cartão da Revisão de texto, que esta fase pôs numa
  rolagem, pedia 501 — **abaixo** da Galeria: a rolagem não baixou o mínimo de hoje (o comentário
  que a primeira versão escreveu dizendo o contrário foi corrigido); ela impede que a Revisão de
  texto passe a decidir quando a Galeria deixar. A Galeria na rolagem é a próxima alavanca e não foi
  tomada: a página da aba é o painel, e a janela e o arnês da suíte o procuram por identidade
  (`indexOf`, `widget(i)`, `area_atual`) — mudar isso é passo, não remendo.
- **O que não muda e por quê.** A 125 % sobre 1366×768 (1093×582 lógicos) a janela continua sem
  caber: os pisos **declarados** das duas colunas (abas 540 = recorte 240 + lateral 260 + folga;
  visor 520) já somam mais que 1093, e mudá-los é desenho — o número fica dito para o crítico C3.

## §A15 — As invariantes num comando só

- **`test_strings::AccentTests` (tronco), vermelho desde a fase 2.** Os seis achados eram todos
  identificadores: o id de comando `Comando("configuracoes", "Configurações…", …)` e o
  `Item("configuracoes")` do menu, a chave do despacho `"configuracoes": lambda…`, a chave do JSON
  gravado em disco (`{"pagina": …}`, `item["pagina"]`), o token cujo valor é o próprio nome
  (`SELECAO = "SELECAO"`) e a lista de palavras **dobradas** do casamento de títulos
  (`"… quebra cabecas …".split()`). A régua ganhou regras **por posição** — chave de dicionário e
  de subscrito, primeiro argumento de `Comando`/`Item`, o literal igual ao nome em maiúsculas, o
  receptor de `.split()` —, só para literais com forma de identificador nas três primeiras; nenhuma
  palavra entrou em `PERMITIDOS`. **Sabotagem/anti-brecha:**
  `test_os_identificadores_escapam_e_o_texto_de_tela_nas_mesmas_posicoes_nao` — `{"Pagina
  seguinte": …}`, `Comando("abrir", "Configuracoes da pagina")`, `{"pagina": "Ir para a pagina"}` e
  `QLabel("pagina")` continuam varridos. **Ciclo 2** (o crítico construiu três brechas, não
  bloqueante 3): o `.split()` só isenta a lista de **palavras minúsculas separadas por espaço**
  (`"… quebra cabecas …".split()`), e não um receptor qualquer nem um `split("|")`; a chave de um
  dicionário que o módulo **enumera** — `list(D)`, `sorted(D)`, `D.keys()`/`items()`/`values()`,
  `for x in D`, `addItems(D)` — vai para a tela e é varrida. Os três casos do crítico
  (`"Pagina anterior|Proxima pagina|Configuracoes".split("|")`, `addItems("Posicao Pagina
  Revisao".split())` e `{"pagina": 1, "posicao": 2}` com `addItems(list(...))`) entraram no teste
  anti-brecha, e as regras continuam escondendo só os seis identificadores de cima (as sondas do
  crítico, `a15_brecha.py` e `a15_escondidos.py`, apontadas para a árvore do ciclo 2: os três
  literais varridos, e nenhum escondido além daqueles). **Ciclo 3** (não bloqueante 7 do ciclo 2):
  enumerar é também `", ".join(D)` e `[*D]`, e a lista de palavras minúsculas não escapa quando vai
  direto a uma chamada que escreve na tela (`CHAMADAS_DE_TELA`: `addItems`, `setText`, `QLabel`…) --
  num `frozenset(...)` de palavras dobradas ela continua identificador. A sonda nova do crítico
  (`a15_brecha2.py`): os seis casos varridos; e as regras seguem escondendo só os seis
  identificadores. **Ciclo 4** (não bloqueante 8 do ciclo 3): o crítico construiu mais oito formas
  de um texto de tela chegar à tela sem ser visto — a lista minúscula guardada num nome e depois
  mostrada, dentro de `sorted()`, juntada para um `QLabel`, capitalizada numa lista; as chaves por
  `map(str.title, D)`, `D.copy()`, `self.D` e `modulo.D` (`a15_brecha3.py`). Ficam, ditas: a
  varredura julga cada literal pela **posição** dele no módulo, e seguir o dado por nomes,
  chamadas, atributos e módulos é outra ferramenta (uma análise de fluxo), não mais uma regra — a
  cada ciclo o crítico constrói outra forma. A varredura dele sobre o código real
  (`a15_escondidos.py`) não acha frase de tela escondida hoje.
- **`test_arquitetura` (suíte), «à parte» em todo relatório.** A afirmação «importar o arnês não
  traz um binding de Qt» agora roda num **processo novo** por arnês; com um teste de janela antes
  na mesma corrida continua verde (23/23 com `test_importacao_view.py` primeiro).
  **Sabotagem:** um pacote temporário com `from PyQt6 import QtCore` no topo → o subprocesso
  devolve o código do binding e o nome dele (`test_a_sabotagem_um_qt_no_topo_do_arnes_reprova`).
  **Ciclo 2** (não bloqueante 4: um `SyntaxError` no arnês saía como «trouxe um binding de Qt
  junto:» com a lista vazia): «veio Qt» sai com o código **3**, e qualquer outra saída não zero é
  a falha do import, dita com o erro (`test_um_import_que_quebra_nao_e_lido_como_qt`).
- **`ImpressaoDaMedicaoTests` (tronco), `--deselect` em toda fase.** O teste compara o digest dos
  módulos do caminho de medição gravado em cada relatório corrente com o de hoje; os quatro
  (`field_20260822_s99`, `controle_20260822`, `mhsp_20260822`, `s108_20260822`) tinham sido
  medidos no `7bcb396` (F9-C12) e dezoito módulos se moveram desde então — o `field_eval` desta
  fase entre eles. Remedidos pelo mesmo procedimento da F9-C12: uma árvore **limpa e efêmera** do
  commit da fase no tronco (`git worktree add --detach`), os quatro `.pt` copiados para dentro dela
  (o caminho gravado sai relativo, e o `.gitignore` não os deixa sujar a árvore), os PDFs lidos do
  checkout principal (o caminho não é gravado) e a saída **fora** da árvore — gravar em
  `docs/metrics` dentro dela a sujaria para a medição seguinte (`scratchpad/remedir_campo.sh`).
  Os quatro gravam `commit 36d6f654`, `dirty=false`, o `.pt` em caminho relativo e nenhum caminho
  absoluto (tronco `8243e90`). **Não é reprodução, é medição nova** — os quatro mudaram, e na
  mesma direção, porque a detecção mudou desde o `7bcb396`:

  | relatório (modelo) | casados | falsos positivos | exportados | taxa de exportação | exportados errados | exatidão de campo | exatos |
  |---|--:|--:|--:|--:|--:|--:|--:|
  | `field_20260822_s99` (produção) | 109 → 114 | 3 → 0 | 100 → 103 | 0,8696 → **0,8957** | 2 → 3 | 0,9787 → 0,9709 | 93 → 103 |
  | `controle_20260822` | 109 → 114 | 3 → 0 | 91 → 93 | 0,7913 → **0,8087** | 0 → 0 | 1,0000 → 1,0000 | 89 → 94 |
  | `mhsp_20260822` | 109 → 114 | 3 → 0 | 84 → 86 | 0,7304 → **0,7478** | 1 → 1 | 0,9878 → 0,9884 | 85 → 90 |
  | `s108_20260822` | 109 → 114 | 3 → 0 | 86 → 88 | 0,7478 → **0,7652** | 1 → 1 | 0,9880 → 0,9886 | 91 → 100 |

  Os três exportados errados da produção, pela régua **anotada** do tronco: Euwe p. 40, Burgess
  p. 60 (o de 0,998 do §C17) e Niemeijer p. 20 — este último é a anotação errada que a fase 4 achou
  (`field_corrections.json`); pela régua corrigida da suíte são 102/103, o número do §C17. A
  oitava remedição entrou no registro das anteriores (`docs/SPEC_REVISAO.md` do tronco). Com eles,
  `ImpressaoDaMedicaoTests` passa **sem `--deselect`** (§0.2).
- **`sol.json` no commit.** (No ciclo 3 do crítico, republicado pelo mesmo comando sobre o
  **`3ff1830`**, o código que mede sem nada por commitar: os 747 itens idênticos aos do ciclo 2. No
  ciclo 2, sobre o **`4fc0f4d`**: os 747 itens idênticos aos de baixo, em CER e decisão; o `s/MP` de
  `scan_clean_300` 1,48 → 1,27 com a máquina mais livre. O parágrafo abaixo é o do ciclo 1.)
  `docs/quality/sol/sol.json`/`.md` republicados sobre o **`bb41c55`** — o
  `environment.commit` do JSON é o do commit da fase pela primeira vez (o da fase 4 gravava o
  `f3bd27e`, a árvore anterior ao commit), sem `SOL_CONFIG` (os padrões de produção: os dois
  interruptores ligados). Os 747 itens saem **idênticos** aos da `f5_on` em CER e decisão; aceitos
  errados 7; o `sol.md` ganha a coluna. `sol_gate --report-only`: silenciosas 0, controles 0/9,
  ordem 1,0000, nenhuma regressão de CER fora do IC contra o `baseline`; bloqueados os mesmos três
  absolutos do §0.3 (o de 150 DPI verde). O `s/MP` publicado carrega a suíte do tronco que outra
  sessão rodava ao mesmo tempo (`scan_clean_300`, que o B13 e o B14 não mudam, 1,33 → 1,48: ~11 %
  de contenção; a foto 7,19 → 9,55 soma a contenção e as variantes do B14). Comando:
  `CAISSA_FIGURINE_TESSDATA=models\tessdata .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol
  --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo --label sol
  --publish`, e `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json`.
