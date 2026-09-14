# Análise — onde o OCR de diagramas, o OCR de texto, os glifos de xadrez e a interface ainda perdem

> **Data:** 2026-09-14 · **Papel:** análise de lacunas, sem código alterado.
> **Fontes:** `docs/ROADMAP.md`, `docs/HANDOFF.md`, `docs/SPEC.md`, `docs/ASSETS.md`, e em
> `docs/quality/`: `SOL_REPORT.md`, `ROTULAGEM.md`, `CORPUS.md`, `F2_REPORT.md`,
> `F4_FIELD_REPORT.md`, `F5_REPORT_C2.md`, `F9_REPORT.md`, `F9_REPORT_C16.md`, `F11_REPORT_C3.md`
> (os nomes curtos abaixo referem-se a esses caminhos; `Sol.md` está na raiz); o código em
> `src/caissa/{ocr,vision,ingest,notation,ui}` e no tronco
> `..\ChessVisionOFF_Puro\src\chess_diagram_ocr\{qt,ui,semantics.py,decode.py,config.py}`; as duas
> capturas do bundle (`docs/quality/F12_janela_do_bundle.png`, `ROTULAGEM_aba_no_bundle.png`) e as
> duas imagens de `..\ChessVisionOFF_Puro\Proposta de interface\`.
> **Regra deste documento:** todo número citado vem de um relatório existente, com a origem ao
> lado. Nenhum número novo foi medido aqui. Onde a análise propõe um ganho, ele é uma **hipótese
> a medir**, nunca um resultado.
> **Revisão adversarial:** a versão 1.0 passou por um crítico independente em 2026-09-14 (32
> achados, 6 críticos); esta é a versão corrigida. Os achados estão resumidos no §8.
>
> Os dois documentos derivados: `OCR_UI_SPEC.md` (o contrato) e `OCR_UI_ROADMAP.md` (a execução).

---

## 0. Em uma tela — as alavancas que restam, por valor

O projeto está numa situação rara: **quase todo portão de reconhecimento está verde ou a um
diagrama da meta**, e os quatro portões vermelhos de OCR de texto são *do corpus e do motor
único*, não do código (`SOL_REPORT.md` §3). Então a pergunta certa não é "o que está quebrado",
é "**onde um esforço limitado ainda move um número que o usuário sente**". A tabela abaixo é a
resposta, ordenada por valor esperado sobre custo, e cada linha tem a evidência que a justifica.

| # | alavanca | área | evidência de que é lacuna | ganho esperado (hipótese) | custo | risco |
|---|---|---|---|---|---|---|
| 1 | **Segundo motor de OCR ao vivo** (Surya ou PaddleOCR/RapidOCR pelo worker da ADR-0003) | texto | os estratos degradados estão "no teto do Tesseract sozinho" — 150 DPI 0,037 vs meta 0,020, fax 0,063, foto 0,116; cirílico com 13–26 % de dicionário (`SOL_REPORT.md` §3, §4) | CER 150 DPI e foto abaixo da meta; russo | médio | licença dos pesos; VRAM |
| 2 | **OCR concorre com a camada de texto danificada** | texto | 16 de 33 livros com camada têm a notação destruída; o Dvoretsky é mantido a 0,55 com 43 % de lances *mangled* e o importador **não chama o OCR** enquanto a camada é mantida (`ROTULAGEM.md` §7c, `HANDOFF.md` §4.1) | lances corretos em 16 livros; hoje o modelo por livro só entra onde a camada é rejeitada | baixo–médio | regressão nos controles limpos |
| 3 | **`Movetext` → `GameScore`** com FEN do diagrama e lado a jogar | texto+diagrama | pendência 3 da F2; 12 lances legais de 18 em 6 páginas do Nunn; `side_to_move` de `default` em 6 de 9 (`F5_REPORT_C2.md` §7.5) | PGN de livro digitalizado ponta a ponta — o valor que o usuário compra | médio | árvore de variantes |
| 4 | **Cifra por livro aprendida da legalidade** | glifos | Tesseract erra figurina como cifra de substituição consistente (93–98 % dos erros de um caractere; `W`=dama, `H`=torre); o corretor resolve só a dama pela promoção e "se recusa a adivinhar o resto" (`HANDOFF.md` §4.1) | ilegível 34 % → perto do 4,9 % que o alfabeto estreito já dava, **sem** alargar o alfabeto | baixo | falsos positivos em livro bilíngue (os 4 casos reais do corretor) |
| 5 | **Amostras negativas e classes raras no ajuste fino** | glifos | `caissa_eng` "aprendeu a ver figurinas no ruído" (controle `photo` → `♖ … ♘♔R♗!`), ♔ 0/13 com 29 linhas (`ROTULAGEM.md` §4c) | modelo por livro deixa de ser só segunda opinião | baixo | nenhum: portão SOL-2 já existe |
| 6 | ~~Rendimento dos diagramas barrados na exportação~~ **corrigido em 2026-09-14 (passo 8)**: dos 96 diagramas casados **com FEN anotada**, 94 são exportados e 94 são exatos; os "20 barrados" eram **19 diagramas anotados sem FEN** (9 hachurados, 10 scan-puro — `exported_comparable` do F4 exclui-os) mais 2 barrados de verdade (Levenfis p150: um certo, um errado). A aritmética do `decode.py` (reparo ⇒ ≤ 0,5 ⇒ nunca exporta) é real e custa **1** diagrama em 96 | diagrama | `benchmarks/diagram_confidence_gate.py` | anotar os 19 (trabalho humano) é o que move o número | baixo | — |
| 7 | **Lado a jogar pela numeração do lance seguinte** | diagrama | o importador só marca o lado quando a legenda o declara (`ingest/pdf/importer.py` `_diagram_node`); 109 de 911 diagramas do acervo com lado no texto (`F2_REPORT.md` §4); `default` em 6 de 9 na cadeia da F5 (`F5_REPORT_C2.md` §7.5) | metade das posições de um livro de finais é das pretas — hoje quase todas saem `w` | baixo | nenhum |
| 8 | **Confiança por diagrama calibrada e discriminante** (não por casa) — **bloqueada pela população (passo 8, 2026-09-14)**: o conjunto de campo tem **2 negativos em 96**; nenhum modelo se ajusta nem se julga, e a sabotagem (ruído) é indistinguível da rodada real. Módulo, sinais e portão existem (`vision/classify/confidence.py`, `benchmarks/diagram_confidence_gate.py`); pesos **não** empacotados | diagrama | `OCR_UI_REPORT_C1.md` §4 | fila de revisão útil; o âmbar passa a significar algo | médio + humano | precisa de ≥ 30 diagramas **errados** anotados — o corpus decide, não o modelo |
| 9 | **Cor da peça fora da distribuição** (`q→Q`) | diagrama | única falha real de campo; **48 ocorrências** de `q→Q` em 2.064 glifos de 86 conjuntos (cor errada em 45 conjuntos); o fine-tune consertou a casa **e** regrediu o laboratório (`F4_FIELD_REPORT.md` §4.2, §6) | fecha o último diagrama do estrato `fonte` | alto | regressão — só com `lab_gate.py` |
| 10 | **Fila de rotulagem por incerteza** (aprendizado ativo) | corpus | 13 páginas de 200 rotuladas (12 do *Dvoretsky & Yusupov SFC4*, 1 do *Modern Endgame Manual*); 94 diagramas comparáveis (1 = 1,06 pp); a única página cronometrada levou 07:58 com 86 de 87 linhas aceitas em bloco (`ROTULAGEM_aba_no_bundle.png` — amostra de um) | cada hora de rotulagem vale mais; portões passam a ter significado | baixo (ferramenta) + humano | nenhum |
| 11 | **Janela de revisão de texto no produto** (SOL-11) | UI | modelo `ReviewQueue` pronto, "sem janela"; a aba Rotulagem é bancada de rótulo, não revisão (`SOL_REPORT.md` §5.3, `ROTULAGEM.md` §7d) | o revisor corrige só spans duvidosos antes de exportar | médio | nenhum |
| 12 | **Editor de posição lado a lado com o recorte** + sobreposição na página | UI | SPEC §10.4 e F9 "tabuleiro lado a lado com o recorte original": a aba Resultado mostra o tabuleiro e a **página inteira**, não o recorte ampliado (`F12_janela_do_bundle.png`); a proposta do usuário (`Imagem_1.png`) pede exatamente isso | correção de casa em 1 clique sem procurar na página | médio | nenhum |
| 13 | **Fita com rótulos e ícones legíveis** | UI | abertos desde o ciclo 15 e nunca remedidos: 6 de 24 botões de fita sem rótulo, cabeçalhos da compacta 0 de 5 desenhados, tinta dos ícones 17,6–41,4 % (`F9_REPORT_C16.md` §12; números de scripts avulsos `benchmarks/reports/ui/c12/c12_fita.py` e `c12_icones_da_janela.py`, **não** de um portão `caissa.ui.audit`) | a pele Fita (que já é a `imagem_2.png`, sete grupos em `ui/comandos.py`) fica inteira | baixo | nenhum |
| 14 | **Visor por ladrilhos** | UI | `VisorDePagina` é um `QScrollArea` com um `QPixmap` inteiro reescalado (`qt/visor.py`); zoom a 59 fps mediana, uma de quatro invocações a 54 (`F9_REPORT.md` D19, **2026-09-07**, não remedido no C16), 7 operações bloqueiam > 16 ms, abrir PDF 214,5 ms (`F9_REPORT_C16.md` §12) | zoom com folga; 4K sem engasgo; fecha o `bloqueio` que está reprovado | médio | regressão do portão de quadros |
| 15 | **Pele Foco como padrão + polimento** | UI | a pele escura da `Imagem_1.png` **já existe** — `Foco` (`ui/pele.py`, S-224) — e a `Fita` é a `imagem_2.png` (S-227); o padrão de fábrica é a `Clássica`, e é ela que as capturas do bundle mostram | percepção de produto (SPEC §10.1) sem pele nova | baixo | portão de contraste; decisão Q3 |

O que **não** está nesta tabela, e por quê, está no §6: TTA, temperatura, LLM em verificação,
meia escala, estipulação por LLM e `repair_ocr_region` foram medidos e rejeitados; repeti-los é
gastar o que já foi gasto.

---

## 1. Método

Li o estado registrado por frente (relatórios e críticas), o código dos módulos citados nas
pendências, e as duas imagens de proposta de interface. Não rodei benchmark nenhum: cada número
abaixo é de um relatório que nomeia o comando que o produziu. Onde uma afirmação depende de
código que só existe no tronco (`ChessVisionOFF_Puro`), o caminho está ao lado.

Duas regras do projeto valem para tudo que se propõe aqui, e o roadmap as impõe por passo:

1. **Todo portão novo precisa de sabotagem** que o faça reprovar (`HANDOFF.md` §7 — 21 portões
   cegos com a suíte verde).
2. **Nenhum número entra em relatório sem o comando ao lado** e sem os estratos
   (`CORPUS.md` §5; `field_exact` sempre com `export_rate` e `conditional_exact`).

---

## 2. OCR de diagramas (visão)

### 2.1 Onde está

| métrica | meta | medido | fonte |
|---|---|---|---|
| recall de detecção (campo) | ≥ 99,0 % | 99,13 % | `ROADMAP.md` |
| precisão de detecção (campo) | ≥ 98,5 % | 100,00 % | idem |
| diagramas perfeitos em campo, régua corrigida | ≥ 98,0 % | 98,94 % (93/94) | `F4_FIELD_REPORT.md` §0 |
| acurácia por casa (split 534) | ≥ 99,95 % | 99,9386 % | idem §8.3 |
| diagramas perfeitos, laboratório (split 534) | ≥ 99,0 % | 97,75 % | idem |
| s/diagrama (GPU, 6 processos) | ≤ 0,10 | 0,0903 | `ROADMAP.md` |
| ECE da confiança | ≤ 0,03 | 0,000265 **por casa** (`ASSETS.md` §2.14); por **diagrama**, nunca publicado — o portão do `ROADMAP.md` não diz qual dos dois | portão F4 |

A detecção fechou. A classificação está a **um diagrama** da meta de campo e a 1,25 pp da meta
de laboratório no split maior. O F4 mediu quatro alavancas e rejeitou as quatro (§0 daquele
relatório). O que ele deixou nomeado — e ninguém pegou — é o que segue.

### 2.2 D1 — Vinte diagramas certos são barrados antes de exportar, e a causa está escrita no código

`F4_FIELD_REPORT.md` §2.1: `scan-hachurado` tem 21 anotados, 21 casados, **10 exportados**,
10 exatos; `scan-puro` tem 44 casados e **35 exportados**. Vinte diagramas casados não chegam
ao `exported_comparable`, e a exatidão dos que chegam é 100 % nos dois estratos. O relatório diz
"não tem problema de exatidão, tem problema de rendimento — e é outra métrica, fora do escopo
desta frente". Ficou fora de escopo e ficou aberto.

O portão é `ACCEPT_MIN_CONFIDENCE = 0,80` (`chess_diagram_ocr/config.py:47`), aplicado em
`batch.py` e em `field_eval.py`. E `decode.py` (§"Uma posição reparada aqui nunca é exportada")
documenta uma **propriedade aritmética**: uma casa reparada pelo decodificador com restrições
recebe a confiança da classe escolhida, que não era o argmax, logo ≤ 0,5; `min_confidence` é o
mínimo das 64 casas; **nenhum diagrama reparado passa de 0,80, hoje nem com outro modelo**. O
próprio código diz "a mudança é no gate". Ou seja: uma das entregas centrais da F4 — o reparo
por legalidade, medido 25 → 33 legais no Kemeri — **não contribui com um único diagrama
exportado**.

Para o usuário isso é: num livro antigo (Chernev, Kmoch, Mieses, os livros de 1930–60 do
acervo), **um diagrama em dois não vira FEN**, e o que o barra não é uma leitura errada.

O caminho **não** é baixar o piso (isso compra `export_rate` com `field_exact`). É:

1. saber, para cada um dos 20 barrados, se a leitura está certa (a anotação diz) e por que foi
   barrado — reparo do decodificador (teto de 0,5), casa de baixa confiança sem reparo, ou
   erro real. `tools/f4_field_failures.py` grava só as predições **erradas** (docstring); precisa
   de uma opção nova para os barrados;
2. se são reparos certos e casas certas de confiança baixa: o portão passa a decidir por uma
   **confiança de diagrama** que veja o reparo como sinal, não como veto (D3), por estrato, sem
   perder `conditional_exact`;
3. se há erros reais de textura: o gerador (`caissa/vision/train/synthgen.py`, `SynthConfig`)
   **não tem nenhuma degradação de digitalização** — só warp, matiz, texto, inversão,
   deslocamento e temas —, embora os temas do TSOJ incluam um tabuleiro hachurado
   (`newspaper`). Aí é aumento de dados, com o `lab_gate.py` como portão.

### 2.3 D2 — Lado a jogar sai `w` quando o livro diz o contrário

Há **duas** cascatas de lado a jogar e é preciso nomear as duas. No tronco,
`chess_diagram_ocr/semantics.py::infer_side_to_move(placement, context)` decide por
texto → legalidade → padrão, com dez origens possíveis (`SideSource`: `text`, `ocr`, `glifo`,
as três `*-page-scope`, `legality`, `database`, `manual`, `default`) — e corre só na via raster
(`caissa/vision/classify/page.py`). No importador da suíte (`caissa/ingest/pdf/importer.py`),
`_diagram_node` aplica o lado **apenas quando a legenda o declarou** no `DiagramContext` de
`captions.py`; o contador `side_to_move` do relatório (**109 de 911** no acervo, `F2_REPORT.md`
§4) conta exatamente isso. Na cadeia da F5 o resultado vem de `default` em 6 de 9
(`F5_REPORT_C2.md` §7.5). Num livro de finais metade das posições é das pretas.

Há um sinal barato que nenhuma das duas usa: **a numeração do primeiro lance depois do
diagrama**. `22...♗f8` é pretas a jogar; `23.♖e1` é brancas. O parágrafo de estilo `Movetext`
(`RegionKind.MOVETEXT`) que a F2 já produz sob o diagrama carrega esse número. Um segundo
sinal: legendas do tipo "após 22.♖e1" / "after 22.Re1" / "nach 22.Te1" (posição *depois* do
lance das brancas ⇒ pretas jogam). Nenhum dos dois exige modelo; os dois entram como origens
novas do `SideSource` (estender, não substituir) e como campo do `DiagramContext` da suíte.

**Ressalva que muda o portão:** a única verdade de lado que existe fora da legenda são as
regiões rotuladas com FEN inicial — e o campo `start_fen` (`ocr/labeling/model.py`) está
**vazio em todas as 256 regiões** dos projetos de rotulagem e `null` nos 474 itens do manifesto
privado. A F5 também mediu que trocar o lado "não mudou nada" na cadeia de então (§7.5, item
2) — o lado é errado com frequência, mas não é o gargalo enquanto os tokens não fecham. O
número que prova esta alavanca só existe depois de alguém preencher `start_fen` (menu do botão
direito, «FEN inicial dos lances»). Consequência para T3 (abaixo): com o lado errado "todo
lance é ilegal a partir do primeiro".

### 2.4 D3 — Nenhuma confiança por diagrama, e a fila de revisão sente

O que existe por diagrama é `min_confidence` (a casa menos confiante) e o estado de legalidade
em três valores (`fen_utils.py`). A temperatura calibrada foi rejeitada com razão (`ASSETS.md`
§2.14: dobrou a fila sem consertar uma casa) — mas o que ela tentava calibrar era a **casa**; o
que a fila e o portão de exportação precisam é um estimador de **"este tabuleiro está exato"**.

Os sinais já existem e são gratuitos: margem mínima entre top-1 e top-2 por casa, número de
casas que o decodificador com restrições (`decode.py`) trocou — hoje um veto, D1 —, estado de
legalidade, regra de orientação que decidiu (`OrientationPolicy.explain()`), estrato da página,
via de detecção (vetorial/neural). Um modelo pequeno (regressão logística ou árvore rasa) dá
uma probabilidade.

**O portão não pode ser só ECE.** A população de campo é 93 exatos de 94 exportados: um
preditor **constante** p = 0,989 tem ECE ≈ 0,01 e passaria; embaralhar os rótulos com um
negativo em 94 devolve o mesmo vetor e **não reprova** — seria o 22.º portão cego. A população
certa são os **114 casados** (inclui os 20 barrados, cuja exatidão a anotação conhece), a
métrica é discriminação (AUROC, ou a curva risco × cobertura contra o preditor constante) mais
ECE, e a sabotagem é substituir os sinais por ruído. Validação por livro no conjunto de campo;
no split de laboratório de 534 não está verificado se há identidade de livro para fazer o mesmo.

É o que faz o âmbar da SPEC §10.4 significar algo, o que ordena a fila do painel Revisão, e o
que destrava D1 sem baixar piso nenhum.

### 2.5 D4 — A cor da peça fora da distribuição

`F4_FIELD_REPORT.md` §4.2: a única falha real de campo é `q→Q` na fonte `extra/condal`, e a
mesma confusão aparece **48 vezes** nos 2.064 glifos de 86 conjuntos de peças fora do acervo
(a decisão de cor erra em 45 dos 86 conjuntos). O fine-tune sintético
consertou a casa e **regrediu o laboratório e exportou 5 diagramas a menos** (§6). O relatório
deixa duas hipóteses não testadas: congelar o tronco convolucional e ajustar só a cabeça, ou
destilar a produção nas casas reais deixando o sintético agir só onde ela é incerta. As duas
são mensuráveis com `lab_gate.py` (nenhum candidato passa se custar acurácia por casa ou
legalidade). Custo alto, ganho de **um** diagrama — por isso está em 9.º, não em 1.º.

### 2.6 D5 — O corpus decide a meta por um tabuleiro

94 diagramas comparáveis: **1 = 1,06 pp**, e o IC de 93/94 não separa 97,9 % de 98,9 %
(`F4_FIELD_REPORT.md` §8.2 item 3). `CORPUS.md` §3 pede 400. A aba Dataset do tronco anota
página a página (`Anotar página`, `Sem diagrama`, `Tirar o selecionado` na captura do bundle);
o que falta é **escolher o que anotar**: os diagramas de menor confiança por diagrama (D3), os
estratos que faltam (SPEC §11.2: setas e destaques, moldura decorativa — nenhum dos dois está
entre os estratos do conjunto de campo: vetorial, scan-puro, scan-hachurado, fonte), e os
livros sem nenhum diagrama anotado. Uma fila ordenada por incerteza faz cada anotação valer
mais (alavanca 10).

### 2.7 D6 — Via vetorial: uma fonte inferida num catálogo de 37

A leitura exata por fonte (Via A) é o diferencial que a concorrência raster não tem
(`SPEC.md` §6.1). Estado: `font_catalog.FAMILIES` tem **37** famílias (29 verificadas, 7 não
verificadas, 1 inferida — as "18" do `ROADMAP.md` são o número da F3-A na época); `SkakNew` teve
a codificação **inferida** de um livro e sai a 0,85, não a 1,0 (`F2_REPORT.md` §4 e §6, item 6). Um segundo livro em SkakNew ou o
arquivo da fonte fecham o "verified". E para uma fonte desconhecida a via vetorial hoje não
tem fallback: os glifos são desenhos vetoriais que o classificador de casas do raster
poderia ler depois de renderizados — com proveniência `inferred` e confiança abaixo de 1,0.
Ganho pequeno e localizado; entra no roadmap como passo curto.

### 2.8 O que já está fechado e não deve ser reaberto

Detecção (recall pack), aceleração fp16 (paridade exata), decodificação com restrições
(`decode.py`, 25 → 33 legais no Kemeri), cascata de orientação com explicação. Nada aqui
pede toque.

---

## 3. OCR de texto

### 3.1 Onde está

`SOL_REPORT.md` §0–§3: 12 entregas com código, OCR ligado por padrão, decisão
aceitar/revisar/abster, portfólio de pré-processamento, calibração isotônica, fusão por token,
perfis prosa/lances, replay legal, proveniência no IR. CER cai em todo estrato degradado contra
o baseline congelado (sombra 0,076 → 0,031; foto 0,24 → 0,12; 150 DPI 0,052 → 0,037); 0/12
controles negativos; 0 importações silenciosas.

Quatro portões vermelhos, e o relatório é preciso sobre a causa de cada um:

| portão | medido | meta | causa nomeada |
|---|---|---|---|
| CER limpo | 0,0156 | 0,005 | `scan_clean_300` sintético lido pelo **motor único** (`ó/6`, `á/4`, `l/1`) |
| CER 150 DPI | 0,0371 | 0,020 | o mesmo motor a 150 DPI |
| acurácia de lances | 0,789 | 0,998 | 98 % dos lances do corpus **sem FEN de partida** — o replay não tem posição |
| lances inventados | 253 | 0 | idem; e um lance alterado conta como perdido **e** inventado |

Depois disso, o caminho de produto com o leitor de glifos e o `caissa_eng` secundário mediu
lances 75,7 → 82,1 %, inventados 412 → 317 (`ROTULAGEM.md` §4c, 2026-09-14).

### 3.2 T1 — Um motor só

O Tesseract está no teto nos estratos degradados; o roteador, o orçamento, os contratos por
versão, o worker isolado e o registro de pesos com licença **existem e foram exercitados com
módulos falsos** (`SOL_REPORT.md` §4, SOL-5). `pyproject.toml` já declara os extras
`ocr-surya`, `ocr-paddle`, `ocr-rapid`. O que falta é **instalar um, rodar
`tests/unit/ocr/test_optional_engines.py` como contrato e medir por estrato**.

Qual? Critérios que o projeto já fixou: pesos com licença auditável (`weights.py` marca Surya
"verificar"), isolamento em subprocesso pela ADR-0003 (ONNX Runtime não coexiste com o torch
cu128 no mesmo processo), e VRAM ≤ 7 GB com a visão ativa. RapidOCR é ONNX puro e leve
(candidato natural ao worker); Surya é o único com cirílico forte e layout, mas é torch — e
carregá-lo no mesmo processo do classificador de casas concorre pela VRAM. A decisão é de
medição: rodar os dois no `bench_sol.py` por estrato e idioma e ficar com o que fecha o
portão de 150 DPI **sem regressão nos limpos** (o IC bootstrap já existe).

### 3.3 T2 — O OCR não concorre com a camada danificada

O maior defeito **de produto** que a análise encontrou é este, porque afeta 16 dos 33 livros
com camada de texto e o usuário não vê nada: `HANDOFF.md` §4.1 mostrou que a notação está
destruída em Nunn, Burgess, Yusupov, Euwe, Polgar, Aagaard, Gaprindashvili (camada de OCR de
origem), e o veredito do nível 0 foi corrigido para aceitar essas páginas a **0,55** em vez
de 0,98. Mas `ROTULAGEM.md` §7c registra a consequência: a 0,55 a camada é **mantida** — "nessas
páginas o importador não chama o OCR, e o modelo do livro só entra quando a camada é
rejeitada ou não existe".

Ou seja: todo o caminho Sol (portfólio, fusão, glifos, modelo por livro) está pronto e **não
é acionado exatamente nos livros em que mais faria diferença**. O `Dvoretsky` que treinou o
`caissa_eng` a 94 % dos lances é importado com a camada danificada.

O conserto tem forma conhecida, com uma ressalva que a própria F5 mediu: numa página acusada
(`mangled_move_ratio` > 0,15 — controles ≤ 0,065, Gaprindashvili ≥ 0,195) o importador
**renderiza e submete ao `OcrService`** (`recognize_image`; não há `recognize_region` hoje), e
a camada de texto entra na fusão SOL-6 como **mais um candidato** — nunca como âncora quando
está acusada. A ressalva: em Gaprindashvili p202 "a prosa correta e os lances destruídos
dividem a mesma linha" (`HANDOFF.md` §4.1, `ocr/page.py`), e `RegionKind.MOVETEXT` só é
atribuído a blocos de análise (`paragraphs.py`). Então a disputa não pode ser "só nas regiões
`MOVETEXT`": onde a região não é separável, é **por token na página inteira** — a fusão já
decide por token, e a regra "âncora que é palavra ou lance nunca é substituída" é o que protege
a prosa (que no controle limpo a camada acerta a 98,8 %). Duas precisões mais: a faixa
"mantida" (0,55 ≤ v < 0,82) também contém páginas a 0,70 (`unjudged_script`) e 0,80
(`borderline`) **sem** notação danificada — a disputa é acionada pelo sinal `mangled`, não pela
faixa; e a régua de "lance legível" do portão é `piece_prefixes` de
`benchmarks/notation_integrity.py`, não `looks_like_move`, que é permissivo de propósito
(`ASSETS.md` §2.15). O "16 de 33" foi medido antes do conserto `ignore_diagram_fonts`
(`F2_REPORT.md` §5.4) e inclui o Polgar, hoje aceito — reobter a lista com `--what verdicts`
antes de fixar o portão. Portão: os livros acusados ganham lances e os controles limpos não
perdem um caractere (o mesmo `bench_ingest.py --dump`, diferenciado).

### 3.4 T3 — `Movetext` → `GameScore`: o produto final

Pendência 3 da F2. Hoje a cadeia diagrama → FEN → Tesseract → cifra → tronco da análise →
legalidade tira **12 lances legais de 18** em 6 páginas do Nunn (`F5_REPORT_C2.md` §7) e para
aí: o IR tem um `Paragraph` de estilo `Movetext` (`ParagraphStyle(name="Movetext")` em
`importer.py`, `RegionKind.MOVETEXT` em `paragraphs.py`) com `PieceGlyph` e texto — **não
existe classe `Movetext`** — e não uma árvore. Os três impedimentos nomeados em §7.5 — dano
residual de token (`@c2`, `2d2`), lado a jogar por `default`, e o tronco da análise que nem
sempre começa no diagrama — têm um dono cada: G1 (cifra por livro), D2 (lado pela numeração)
e a regra já descoberta de que "o tronco se emenda por cima da variante"
(`ocr/notation/movetext.py`).

O que falta construir: o passo que, tendo FEN + lado + tokens reparados, chama o analisador
tolerante — que **não** está no tronco `ChessVisionOFF`: veio do `PGN_Live_Editor` e já foi
absorvido em `src/caissa/notation/` (`parser.py`, `book_import.py`, `variation_builder.py`,
`pipeline.build_games_for_export`), sem que nada em `ingest/` o chame hoje — mais a reparação
por legalidade (`notation/legality_repair.py`), e grava um `GameScore` no IR (variantes são
`MoveNode.children[1:]`, `core/model/game.py`; não há classe `Variation`) com cada lance
carregando a proveniência do token (SOL-10 já põe motor/confiança no span). Métrica: **lances
legais encadeados por página** sobre as 6 páginas do Nunn e sobre as páginas rotuladas do
*Dvoretsky & Yusupov SFC4* — **depois** de alguém preencher o `start_fen` das regiões de
lances, que hoje está vazio em todas (§2.3). Há dois "Dvoretsky" no acervo (o *Endgame Manual*
2025, nativo, controle E1; e o *SFC4*, digitalizado, o rotulado) — nomear pelo arquivo. É a
única métrica desta análise que mede o que o usuário compra: PGN de um livro digitalizado.

### 3.5 T4 — O corpus continua sintético

13 páginas rotuladas de 200 (`HANDOFF.md` §4.5) — 12 do *SFC4* e 1 do *Modern Endgame
Manual*. A bancada está pronta, treina por livro e mede por partição. O que a torna cara é a
**ordem**: hoje o revisor abre uma página e lê 87 linhas (a única página cronometrada levou
07:58, com 86 aceitas em bloco — amostra de um). Com a decisão SOL-2 já existente por linha
(`REVIEW`/`ABSTAINED`, palavras fracas, candidatos discordantes) dá para construir uma **fila
de páginas por valor de rótulo**: páginas com mais linhas em `REVIEW`, de livros sem rótulo, de
estratos vazios no manifesto (cirílico, espanhol, fax), regiões de lances sem `start_fen`. O
"Aceitar confiáveis da página" já existe; o que falta é o "qual página abrir a seguir".
Ferramenta barata; o resto é trabalho humano, e é o único que faz os portões de CER e de
lances medirem o que a meta quer.

### 3.6 T5 — Léxico, layout e o que sobra

- **Russo**: sem Hunspell licenciado, 13–26 % de acerto de dicionário (`SOL_REPORT.md` §4,
  SOL-9). Um `ru_RU.dic` com licença auditável entra por `tools/build_lexicon.py`.
- **Soluções densas rejeitadas pelo nível 0** (Yusupov p. 701: "55 % impronunciáveis" numa
  página que é 90 % notação — `F2_REPORT.md` §4, pendência 5): o veredito por região já sabe
  distinguir `MOVETEXT`; falta o léxico contar lance válido como palavra **nessa região**.
- **Tabelas de lances em colunas** (3 páginas do Chernev): sem verdade de campo, não vira
  portão; fica registrado.
- **Super-resolução aprendida** para < 200 DPI: o `Upscale` é bicúbico + máscara de nitidez
  de propósito e o docstring diz onde o modelo entraria (atrás do worker ONNX). Só depois de
  T1, porque um segundo motor pode tornar isso desnecessário.

---

## 4. Glifos de xadrez (figurinas)

### 4.1 Onde está

Três leitores, nenhum treinado para figurina de origem:

| leitor | o que faz | medido |
|---|---|---|
| Tesseract `eng` | devolve o sósia latino, **sempre o mesmo dentro do livro** — no *SFC4*: ♖→H, ♕→W, ♘→S, ♗→2/8/& (`ROTULAGEM.md` §4b); no Gaprindashvili: `W`=dama, `H`=torre, `S`=**rei** (`HANDOFF.md` §4.1) — o mapa muda de fonte para fonte, que é a razão de G1 | 13–22 % das letras de peça |
| leitor de glifos do tronco (`engines/glyph.py`, 314 classes, 99,1 % no teste) | candidato secundário; troca sósia → figurina só em lance válido com conf ≥ 0,70 | p. 10 do *SFC4*: 27/27 linhas certas com ele, 0 sem |
| `caissa_<lang>` ajustado (`training/tesseract_finetune.py`) | emite ♔♕♖♗♘♙; por livro, registrado em `livros.json` | *SFC4*: 94 % dos lances; **♔ 0/13** (rodada `caissa_por`, 29 linhas de ♔; o `caissa_eng` teve 40 linhas de ♔ e não tem placar por peça publicado); **inventa no ruído** |

E o corretor de cifra (`notation/cipher.py`) sobre a saída do Tesseract: ilegível 78,5 % →
34,3 %; resolve a dama pela promoção e delega o resto à legalidade.

### 4.2 G1 — A cifra é do livro, e ninguém a guarda

O fato medido mais útil desta área está no `HANDOFF.md` §4.1: o Tesseract erra como **cifra
de substituição** — 93–98 % dos erros são de um caractere, e o mapa é estável dentro do
livro (`W`=dama, `H`=torre, `S`=rei). O corretor "se recusa a adivinhar" e cada lance é
resolvido sozinho pela legalidade.

Se em 20 posições diferentes só `♕` torna `Wd5` legal, então `W` = ♕ **neste livro**, com
evidência contável — e os lances ilegíveis restantes (os 34,3 %, medidos por
`notation_integrity.py --what decode`) podem ser reescritos com a tabela do livro, com a
contagem de evidência anexada à proveniência e um piso (por exemplo ≥ 5 confirmações
independentes e 0 contradições). Isso é o "treino de padrões" do FineReader feito sem treinar
nada. O `HANDOFF.md` avisa para **não alargar o alfabeto** para recuperar esse número — a
tabela por livro não alarga: restringe, porque só aceita o mapa que a legalidade daquele livro
provou.

**A ressalva que decide se isto vale:** a evidência vem de lances *provados pela legalidade*,
e o replay só tem posição para **2 % dos lances do corpus** (`SOL_REPORT.md` §3); a cadeia
inteira deu 12 lances legais em 6 páginas do Nunn. Ninguém mediu quantos lances provados
existem nas páginas fixas do Gaprindashvili. A primeira tarefa de G1 é **contar** — se forem
poucos, a tabela depende de D2 e T3 (mais posições) antes de render, e a ordem do roadmap muda.

Os quatro falsos positivos reais do corretor (russo correto, `K` latino em livro russo,
travessão, livro português com lances em inglês) são o conjunto de controle obrigatório —
com a precisão de que a regra "só token ilegível" já protege `Nf3` impresso; a sabotagem útil é
sobre um token **realmente ilegível** de um livro-controle, não sobre um lance válido.

### 4.3 G2 — Amostras negativas e classes raras no ajuste fino

`ROTULAGEM.md` §4c mede os dois defeitos e §7d os deixa como "próximo passo":

1. **Figurina no ruído**: o `caissa_eng` falha o controle `photo` e infla os inventados no
   `fax_dither` (+15). A verdade de treino só tem linhas de texto. Acrescentar ao `index.jsonl`
   linhas **negativas** — recortes de ruído, tabuleiro, mancha, com verdade vazia ou prosa
   sem figurina — é o que ensina o modelo a não emitir ♖ onde não há. O gerador de controles
   já existe (`ocr/controls.py`: 6 tipos, 12 itens no manifesto).
2. **Classes raras**: o ♔ 0/13 é da rodada `caissa_por` (29 linhas de ♔); o `caissa_eng` e o
   modelo por livro do *SFC4* (40 linhas de ♔) não têm placar por peça publicado — medir antes
   de fixar o portão. Sobreamostrar as linhas com classes raras na lista de treino
   (`lstmtraining` aceita listas com repetição) e, se não bastar, **sintetizar linhas** com os
   recortes reais de figurina do próprio livro colados em linhas de prosa do mesmo livro —
   verdade exata por construção, mesma tipografia.

Portão: o próprio SOL-2 (0 controles) mais o `Medir no livro…` por partição, que já existe —
medindo o modelo **do livro** (`models/tessdata/livros/<slug>/`), não o `caissa_eng` global de
`models/tessdata/` que o `bench_sol.py --model-prefix caissa` lê.

### 4.4 G3 — O leitor de glifos não aprende com a bancada

O leitor de glifos (314 classes) foi treinado no tronco com as formas do acervo de lá. A
bancada produz, a cada linha aceita, **pares alinhados** figurina-verdade × caixa de
caractere do Tesseract. Hoje isso alimenta só o `lstmtraining`. Colher esses recortes para o
conjunto do classificador de glifos é gratuito e fecha o círculo: o leitor que hoje dá 27/27
no Dvoretsky passa a ver as figurinas de cada livro rotulado. Prioridade baixa enquanto G1 e
G2 não forem medidos — pode ser que sobrem poucos casos.

### 4.5 G4 — Figurinas em PDF nativo: o catálogo é a única via

Em PDF nativo a figurina é um glifo de fonte de xadrez, e a F3-A lê pelo catálogo (18
famílias). Uma fonte fora do catálogo hoje vira letra crua (`2.♘xd4` → `2.l0xd4`, o modo de
falha real do acervo, `ROADMAP.md`). O mesmo fallback de D6 — renderizar o glifo e perguntar
ao leitor de glifos — vale aqui, com proveniência `inferred`. Um passo curto.

---

## 5. Interface

### 5.1 Onde está

A janela do produto (`F12_janela_do_bundle.png`, `ROTULAGEM_aba_no_bundle.png`) é o tronco
PyQt6: barra de menus, **sete abas** à esquerda (Resultado, Estudo, Revisão, Texto, Dataset,
Galeria, Rotulagem), visor de PDF à direita, rodapé. A F9 passou por 16 ciclos e foi
aprovada no 15 com portões de teclado, contraste (3 peles), bloqueio, quadros e texto
pintado — **tudo medido**. É um produto funcional e acessível.

O que ele **não** é, *como sai da caixa*: a "qualidade AAA, referência Affinity Publisher /
DaVinci Resolve" da SPEC §10.1. As capturas do bundle mostram a pele **Clássica** — o padrão
de fábrica — com controles Fusion cinza; a aba Rotulagem tem uma barra de ferramentas de três
linhas em 800 px; o tabuleiro ocupa a metade esquerda e a página inteira a direita, sem o
recorte do diagrama entre os dois.

**As duas imagens de `Proposta de interface/` já foram lidas pelo tronco** — e isto muda o
plano: `ui/pele.py` registra três peles, e o comentário do código diz de onde vêm. A **Foco**
(S-224) é *"escura […] e é a Imagem 1: cromo escuro com o documento claro"*; a **Fita** (S-227)
é *"a Imagem 2: grupos nomeados, ícone grande com rótulo"*, compacta por padrão desde a S-232;
os **sete grupos** da fita (`ui/comandos.py` `GRUPOS`: Arquivo, Edição, Visualização, OCR,
Acervo, Estudo, Ajuda) foram derivados da Imagem 2 com uma decisão registrada sobre o corte
OCR/Acervo. O que a proposta pede e ainda falta é, portanto, mais estreito do que "uma pele
nova":

| a proposta mostra | o que existe hoje | lacuna |
|---|---|---|
| **casca escura**, barra de menus simples, quatro ações grandes (OCR local · Próximo diagrama · Aplicar FEN · Exportar) | a pele **Foco** é isso; o padrão de fábrica é a Clássica | Foco (ou Fita) como padrão — decisão Q3 — e as ações primárias em evidência |
| tabuleiro grande com **casas duvidosas em destaque luminoso** | "Mapa de incerteza" (caixa de marcar), destaque discreto | o destaque como estado padrão, ligado a uma confiança que signifique algo (D3) |
| página ao lado com **caixa tracejada numerada** sobre o diagrama detectado | caixas existem ("clique num diagrama marcado da página") | numeração + estado (lido / duvidoso / corrigido) + sincronia com o tabuleiro |
| **fita agrupada com ícone e rótulo** | a pele Fita, com sete grupos; **inacabada**: 6 de 24 botões sem rótulo, cabeçalhos da compacta 0 de 5, tinta dos ícones 17,6–41,4 % — abertos desde o C15 e medidos por scripts avulsos (`benchmarks/reports/ui/c12/`), não por portão | terminar a Fita com portão próprio; **manter os sete grupos** |
| tabuleiro e página **lado a lado**, sem abas | sete abas | o fluxo principal (ler diagrama → corrigir → exportar) sem trocar de aba |

### 5.2 U1 — Editor de posição com o recorte original

SPEC §10.4 e o entregável da F9 "editor de posição: tabuleiro lado a lado com o recorte
original". Na aba Resultado o lado direito é a **página inteira** a 59 %; o diagrama
reconhecido está lá em algum lugar. Para conferir uma casa o usuário precisa achar o
diagrama na página, dar zoom, e voltar. O que a proposta pede — e o painel de Rotulagem já
faz para linhas de texto (recorte a 300 DPI acima da leitura) — é o **recorte do diagrama
ampliado ao lado do tabuleiro**, com a casa sob o ponteiro espelhada nos dois e a top-3 da
casa numa dica. Os dados existem (`tools/f4_field_failures.py` já grava recorte + top-3 por
casa); é montagem.

### 5.3 U2 — Janela de revisão de texto (SOL-11)

O modelo (`caissa.ocr.review.ReviewQueue`) está pronto, exporta correções e protege a
partição cega; a janela "depende do shell F9". A aba Rotulagem é uma **bancada de rótulo**:
lê toda linha, grava verdade, treina. A revisão de produto é outra coisa: só os spans
`REVIEW`/`ABSTAINED` do documento importado, recorte + texto, alternativas, aceitar / editar /
manter como imagem, e a decisão vai para o IR (`verified_by_human`) e para a exportação. Os
componentes visuais são os mesmos da aba (recorte, leitura com palavras fracas, alternativas,
verdade com paleta de figurinas) — reutilizar `PainelDeRotulagem`, trocar o modelo por baixo.

### 5.4 U3 — Fita: rótulos, grupos, ícones

Três itens abertos desde o ciclo 15, nunca remedidos (`F9_REPORT_C16.md` §12): botões de
fita sem rótulo (6/24), cabeçalhos da densidade compacta não desenhados (0/5), tinta dos
ícones 17,6–41,4 %. Os três números vieram de scripts avulsos do ciclo 12
(`benchmarks/reports/ui/c12/c12_fita.py`, `c12_icones_da_janela.py`), **não de um portão** —
o `texto_pintado` mede fonte pintada × recorte e passa hoje com os seis botões sem rótulo.
Então a primeira tarefa é promover os dois scripts a portões de `caissa.ui.audit`, com
sabotagem; a segunda é fechar os três números na pele Fita: título de grupo em toda
densidade, ícone de 24 px com tinta cheia e rótulo desenhado embaixo, hit area ≥ 40 px. Os
**sete grupos** ficam (`ui/comandos.py`); a proposta desenha quatro porque é um esboço.

### 5.5 U4 — Visor por ladrilhos e nada bloqueando

`qt/visor.py`: `VisorDePagina(QScrollArea)` guarda `_pagina: QPixmap` e `_escalada:
QPixmap` — a página inteira reescalada a cada zoom. A F9 mediu (ciclo 1, **2026-09-07**,
`F9_REPORT.md` D19; o portão `quadros` não foi rerodado no C16) pan com oito vezes de folga e
**zoom a 59 fps mediana, uma de quatro invocações a 54** (abaixo do piso de 55); no C16, 7
operações bloqueiam > 16 ms e abrir PDF leva 214,5 ms na thread de UI — o portão `bloqueio`
está **reprovado** hoje. A ADR-0001 já apontava a solução: `QGraphicsView` com cache de
ladrilhos, renderização na resolução alvo fora da thread, LRU por página. Em 4K com página a
300 DPI o `QPixmap` inteiro é o que engasga. Remedir `quadros` antes de mexer.

### 5.6 U5 — Foco como padrão e polimento

Três peles existem e passam no contraste, e a Foco **é** a pele escura da proposta (§5.1). O
que falta não é uma quarta pele: é (a) decidir o padrão de fábrica (Q3), (b) dar à Foco
tokens que a SPEC §10.2 pede (projetada, não a clara invertida — conferir no `qt/tema.py` se
o cromo escuro é derivado ou desenhado), e (c) o polimento de detalhe que a captura mostra
faltando, em todas as peles:

| princípio (`make-interfaces-feel-better`) | hoje | depois |
|---|---|---|
| raio concêntrico | grupos e botões com o mesmo raio | raio externo = interno + espaçamento |
| números tabulares | "p. 1 de 308", "59 %", contadores do rodapé mudam de largura | `tabular-nums` nos contadores e no rodapé |
| hit area | botões de peça na paleta ~28 px | ≥ 40 px, ideal 44 |
| estados | hover/press/focus do Fusion | foco visível projetado, press sutil, transições só nas propriedades que mudam |
| contorno de imagem | recorte e página sem contorno sobre fundo claro | contorno neutro 1 px em alfa |
| vazio | "Nenhum diagrama aberto. Clique…" em texto solto; vazio de painel a 4K 5 de 6 acima de 200 kpx (aberto no C16) | estado vazio desenhado, com a ação primária no lugar |

Tudo isso passa pelos portões que já existem (contraste em 100 % dos pares, teclado, texto
pintado) — a mudança de padrão não entra sem eles verdes nas três peles.

### 5.7 U6 — O livro como unidade de trabalho

O fluxo hoje é "abrir PDF → OCR melhor diagrama / OCR todos os diagramas → abas". A F2
importa o livro inteiro (911 diagramas em 552 páginas, 0 falhas), a exportação sai da aba
Rotulagem e do menu Arquivo, e a revisão de diagramas fica na aba Revisão. Não há uma tela
que diga **"este livro: 308 páginas, 212 diagramas lidos, 9 duvidosos, 41 regiões de texto em
revisão, exportar"**. Um trilho de páginas (miniaturas com estado: diagramas / texto /
revisado) à esquerda do visor, com progresso real e cancelável da importação (a F2 é
streaming e o `ExportadorDeLivro` já roda em thread com tranca), é o que transforma sete abas
num fluxo. Não é a Biblioteca de acervo (`ASSETS.md` §3, lacuna F9) — é um livro por vez,
bem feito.

### 5.8 O que a interface já tem e não precisa refazer

Paleta de comandos (`qt/paleta.py`), teclado completo com nomes acessíveis (117 rótulos ×
3 peles medidos), três peles com contraste medido, tabuleiro editável com paleta de peças,
cascata de orientação explicada, exportação em thread com tranca, retradução de botões de
diálogo. A migração de toolkit (PyQt6 → PySide6) está registrada como reversível e é decisão
de licença, não de qualidade — fora desta análise.

---

## 6. O que não refazer

Medido e rejeitado (`ASSETS.md` §2.14, `HANDOFF.md` §5, `F4_FIELD_REPORT.md` §5): TTA/jitter,
temperatura por casa, `verify_diagram` por LLM (especificidade 0,000), busca só em meia
escala, estipulação por LLM, `repair_ocr_region` por LLM (103 lances que não estão na
página), refino de recorte antes de classificar, decodificação com restrições para a falha
`q→Q` (as duas leituras são legais), fine-tune sintético **como está** (regride o laboratório).

Duas duplicações deliberadas que não se unificam: `looks_like_move` permissivo e o probe de
CMap do tronco (`ASSETS.md` §2.15).

---

## 7. Decisões que são do usuário, não da análise

1. **Segundo motor**: Surya (cirílico, torch, VRAM compartilhada) ou RapidOCR/Paddle (ONNX,
   worker isolado, latino)? A recomendação é medir os dois; a instalação de um deles baixa
   pesos com licença a auditar (`weights.py`).
2. **Rotulagem humana**: quem, quantas horas. Nenhum portão vermelho de Sol fecha sem isso.
   A ferramenta de ordenação (T4) reduz o custo, não o elimina.
3. **Foco (escura) ou Fita como padrão de fábrica** em vez da Clássica? A proposta sugere a
   escura. As três continuam disponíveis em *Ver ▸ Aparência*.
4. **Fluxo sem abas** (U6) muda a forma da janela que a F9 mediu em 16 ciclos. Cada portão
   precisa ser rerodado; é o passo mais caro da parte de interface e o que mais muda a
   percepção. Vale confirmar antes de começar.
5. **Preencher o `start_fen`** das regiões de lances já rotuladas (§2.3): é trabalho humano
   curto (13 páginas) e é o que dá número aos portões de lado a jogar e de partida.
6. O contraste SPEC §13 × Stockfish na F9-C16 continua pendente (`HANDOFF.md` §6.3) e não é
   desta análise.

---

## 8. O que a crítica adversarial corrigiu nesta versão

Um crítico independente leu a versão 1.0 dos três documentos contra o repositório (2026-09-14)
e devolveu 32 achados. Os que mudaram o plano, para que ninguém os reaprenda:

| achado | o que estava escrito | o que o repositório mostra |
|---|---|---|
| `start_fen` vazio | "as 13 páginas do Dvoretsky têm FEN inicial por região" | o campo existe e está vazio em 256/256 regiões e `null` em 474/474 itens do manifesto |
| duas cascatas de lado a jogar | "cascata do tronco, cinco origens" | o importador da suíte só usa a legenda (`captions.py`, `_diagram_node`); o tronco tem dez `SideSource` e corre só na via raster |
| ECE cego | "ECE ≤ 0,03, sabotagem: embaralhar rótulos" | com 93/94 um preditor constante passa e a sabotagem não reprova; o portão precisa de discriminação sobre os 114 casados |
| reparo nunca exporta | "os 11 barrados pelo piso de confiança" | `decode.py`: casa reparada ⇒ `min_confidence ≤ 0,5` ⇒ nunca passa 0,80; 20 barrados (hachurado + scan-puro) |
| peles | "nenhuma pele é a da proposta" | Foco = Imagem 1 (S-224), Fita = Imagem 2 (S-227), sete grupos derivados dela |
| portão da fita | "`texto_pintado` acusa o rótulo em `toolTip()`" | ele mede fonte × recorte e passa hoje; os 6/24 vieram de `c12_fita.py` |
| nomes do IR e do analisador | `Movetext`, `Variation`, "analisador do tronco" | `Paragraph` de estilo `Movetext`; `MoveNode.children[1:]`; `caissa.notation` (do `PGN_Live_Editor`) |
| sabotagem do passo 6 | "contar lance como palavra na página faz o p202 voltar a 0,98" | o 0,55 vem de `mangled_move_ratio`, ramo independente do `nonword` — a sabotagem não reprovaria |
| comandos dos portões da F9 | `PYQ -m caissa.ui.audit.*` | o venv do tronco não importa `caissa`; a receita é `PYTHONPATH=<suite>\src;<tronco>\src` + `QT_QPA_PLATFORM=offscreen` (`F9_REPORT_C16.md` §17) |
| contrato do motor opcional | "rodar `test_optional_engines.py` com o motor real" | o teste injeta módulos falsos e nunca pula — com o motor real o resultado é idêntico |
| `q→Q` | "em 48 de 86 conjuntos" | 48 ocorrências em 2.064 glifos; cor errada em 45 conjuntos |
| catálogo | "18 famílias" | 37 (29 verificadas, 7 não, 1 inferida) |
| gerador sintético | "não lista hachura" | não tem degradação de digitalização nenhuma; os temas do TSOJ incluem um hachurado |
| ♔ 0/13 | atribuído ao `caissa_eng` | é do `caissa_por`; o `eng` não tem placar por peça |
