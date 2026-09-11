# F9 — Interface, relatório do ciclo 16

```
FRENTE: F9 (Interface)
CICLO: 16
ENTRADA: APROVADO no ciclo 15, com 14 itens no §8 — três deles defeitos que não deviam
         ter sobrevivido a uma aprovação.
```

Este ciclo não teve bloqueante para matar. Teve uma **ordem de serviço de 14 itens** e três coisas
que o crítico do ciclo 15 nomeou como as que importam: um menu que promete o que o produto não faz,
uma régua que pergunta a fonte a quem o Qt não consulta, e uma defesa escrita que não existe.

**Os três estão fechados, cada um com a medição do crítico reproduzida e com uma prova de vida
própria.** Os outros onze estão fechados com número ou declarados abertos com número. Nenhum
número deste relatório vem de outro lugar que não um comando que eu rodei.

---

## §0 — Os 14 itens do §8, um por linha

| # | o item | o que eu fiz | o número medido | veredito |
|---|---|---|---|---|
| 1 | três comandos de motor mentem | a janela procura o binário (`ui/sala_declarada.motor_de_analise`) e o entrega ao painel; sem motor, os três saem cinza com a razão na dica. Portão novo `caissa.ui.audit.comandos` | **0** comandos habilitados que não podem ter efeito (eram 3); 379 comandos medidos em 3 peles; `find_engine` e `EngineAnalyzer` com **1** chamador em `src/` (eram 0) | **FECHADO** (§1) |
| 2 | a régua pergunta à folha onde a folha não vota | `folha_de_estilo.QUEM_PINTA` (medido no pixel) + `texto_pintado.fonte_que_pinta` | com widget 9 pt e folha 20 pt: a régua diz **9 pt** no título e **20 pt** no cabeçalho; a régua antiga dizia 20 nos dois | **FECHADO** (§2) |
| 3 | `PAPEL_PINTADO` e `PAPEL_POR_CLASSE` são duas tabelas | `PAPEL_PINTADO` **deriva** de `PAPEL_POR_CLASSE`; teste que troca a classe e cobra a faixa | 2 seletores derivados; o teste de deriva passa e cai se a derivação sumir | **FECHADO** (§2.1) |
| 4 | `font:` curto escapa das duas peneiras | `mexe_na_fonte` separada de `PROPRIEDADES_DE_FONTE`; o teste citado passou a existir | as 4 sabotagens acusam **1** cada (a curta era **0**); a partição não deixa nada no meio | **FECHADO** (§3) |
| 5 | duas legendas iguais numa tela | o botão do vazio de `_JanelaDePartidas` sai; o do rodapé de `DialogoDePartidas` some enquanto o vazio o oferece | pares com a mesma legenda visíveis ao mesmo tempo: **2 → 0** nos treze diálogos | **FECHADO** (§4) |
| 6 | a conta de rótulo não inclui a janela | instrumento novo sobre as seis abas; `outro → Outro` e mais cinco que ele achou | 117 rótulos medidos × 3 peles, **0** em minúscula (eram 6) | **FECHADO** (§5) |
| 7 | `brancas` numa aba, `Brancas` na outra | os dois pares saem de `ui/strings.SIDE_LABELS` | **1** literal (eram 2 cravados em 2 painéis) | **FECHADO** (§5) |
| 8 | crase e três pontos em texto desenhado | `COLECAO_VAZIA_FRASE` sem crase; 26 trocas `...` → `…` | **0** crases e **0** reticências ASCII nos 117 rótulos das 3 peles; 1 exceção declarada (notação PGN) | **FECHADO** (§6) |
| 9 | o portão de bloqueio morre calado | `_descartar` no lugar de `close()`, na janela medida e na fria do perfil | **11 de 11** invocações completam pela receita publicada (eram 6 de 8 aqui, 3 de 8 no crítico) | **FECHADO** (§7) |
| 10 | a frase do portão não diz a população | campo `populacao` no relatório, e `QLabel[apoio]` declarado fora | a frase nomeia a janela recém-aberta e as duas coisas que ficam fora | **FECHADO** (§8) |
| 11 | o ANTES não é a tela de antes; 2 retratos iguais | escala reaplicada depois da folha, no script **e** no portão; 13 retratos no estado do produto | tinta **159 px** no ANTES e no DEPOIS (era 115 × 157); **0** sha256 repetido em 13 arquivos | **FECHADO** (§9) |
| 12 | `Status` gasta os pixels de `Motivo` | `Status` escondida enquanto `Só pendentes` está marcado | `Motivo` **+80 px** em toda largura; elididos a 1280 px com filtro: **7 → 0** de 27 | **FECHADO** (§10) |
| 13 | a suíte escreve em pasta publicada | não é minha área: o conserto preciso está escrito e sinalizado | confirmado: `parity_fp16.json` foi regravado pela minha execução | **ESCRITO E SINALIZADO** (§13) |
| 14 | os abertos de sempre | três remedidos, cinco repetidos do ciclo 15 **e marcados como tal** | bloqueio 7 operações / 214,5 ms (remedido); `DialogoDeTreino` sem botão (remedido); `Motivo` sem filtro 7 de 27 (remedido); vazio 4K, fita, ícones, FEN, etiqueta: repetidos | **ABERTOS, DECLARADOS** (§12) |

---

## Nota de procedimento

* Conferi o destino de cada script antes de rodá-lo. **Nada que eu escrevi saiu de
  `docs/quality/F9_REPORT_C16.md`, de `benchmarks/reports/ui/c16/` e dos arquivos de produto e de
  teste listados no §16.** Nada foi escrito em `benchmarks/reports/critique/`, em `packaging/`, em
  `pyproject.toml` nem em `tests/integration/`.
* `PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider` em tudo; `--saida` explícito em todo portão;
  `QT_QPA_FONTDIR=C:\Windows\Fonts`.
* **Uma exceção que não é minha, e ela é o item 13.** `pytest tests` regravou
  `benchmarks/reports/parity_fp16.json` — o sha256 antes da minha execução era
  `e7dffbfb…4c24f224`. É `tests/integration/test_gpu_parity.py:309`, que não é meu; o conserto
  preciso está no §13.
* **Instrumentos que passei a quebrar, e digo por quê.** `medir_titulos_de_grupo` /
  `medir_cabecalhos` / `medir_abas` passaram a exigir `quem_pinta=` (§2), então
  `c15_a_regua_contra_a_tela.py`, `c15_sabotar_o_texto_pintado.py` (do crítico) e
  `c14_recorte_do_titulo.py` (meu, do ciclo passado) levantam `TypeError` ao chamá-los. É **alto e
  não calado**, e o motivo é exatamente o conserto que o item 2 pediu: um padrão silencioso ali
  mediria a fonte errada sem avisar. **Não toquei um byte dos do crítico**; o meu está superado por
  `c16_recorte_do_titulo.py`, que faz o mesmo par com o ANTES honesto (§9). A invocação equivalente
  do instrumento do crítico é `medir_titulos_de_grupo(..., quem_pinta=dict(folha_de_estilo.QUEM_PINTA))`.

Instrumentos meus, todos em `benchmarks/reports/ui/c16/`:

| instrumento | o que responde |
|---|---|
| `c16_quem_pinta.py` | qual das duas fontes o Qt usa, **por seletor**, medido no pixel |
| `c16_o_menu_do_motor.py` | os três comandos do motor, com e sem binário |
| `c16_retratar_os_dialogos.py` | os treze diálogos, o sha256 de cada retrato, as legendas repetidas |
| `c16_rotulos_de_campo.py` | os rótulos desenhados da **janela**, não só dos diálogos |
| `c16_recorte_do_titulo.py` | o par ANTES/DEPOIS, com o ANTES honesto |
| `c16_largura_do_motivo.py` | `Motivo` elidido contra a redundância de `Status` |
| `c16_heranca_contra_o_qt.py` | `contraste.HERANCA` contra o MRO real do PyQt6 |

---

## §1 — Item 1: os três comandos do motor param de mentir

**O achado do crítico, reproduzido.** `Analisar a posição com o motor`, `Análise contínua enquanto
se navega` e `Pôr a linha do motor como variante` saíam `habilitado=True` em qualquer máquina e os
três respondiam *"Sem motor UCI instalado: ponha o Stockfish em engines/ e reabra"* — receita que
não resolvia nada, porque `qt/janela.py` construía `PainelDeEstudo` **sem** `analyzer` e
`engine.find_engine`, `EngineAnalyzer` e `settings.EngineSettings.path` **não tinham um chamador em
`src/`**.

**Escolhi a primeira das duas saídas que o crítico ofereceu: a janela passa a procurar o binário.**
E a segunda metade veio junto, porque uma sem a outra continua mentindo: numa máquina que de fato
não tem motor, os três saem do alcance com a razão na dica.

`ui/sala_declarada.motor_de_analise()` lê `settings.load_settings().engine`, chama
`engine.find_engine(path or None)` e devolve um `EngineAnalyzer` ou `None`. `qt/janela.py` o
constrói **antes dos painéis** (o painel decide na construção se desenha a seção do motor) e o
entrega em `PainelDeEstudo(analyzer=…)`. `menu.BarraDeMenus.impedir` desabilita os três com
`strings.SEM_MOTOR_DICA` quando não há motor. `sala_declarada.encerrar_o_motor` fecha o processo
filho no `closeEvent`.

Medido, `c16_o_menu_do_motor.py`, a mesma janela do produto nas duas condições:

```
  === SEM motor
    janela._analisador = None          estudo.has_engine = False
    menu[analisar_posicao ]  habilitado=False  dica: 'Precisa de um motor UCI, e nenhum foi…'
    menu[analise_continua ]  habilitado=False  dica: 'Precisa de um motor UCI, e nenhum foi…'
    menu[variante_do_motor]  habilitado=False  dica: 'Precisa de um motor UCI, e nenhum foi…'
    menu[partidas_da_posicao] habilitado=True   (nao exige motor)
    QGroupBox visiveis na aba Estudo: 2  ['Lances', 'Comentário do lance']

  === COM motor
    janela._analisador = <chess_diagram_ocr.engine.EngineAnalyzer …>   has_engine = True
    os tres:  habilitado=True
    QGroupBox visiveis na aba Estudo: 3  [… , 'Motor (c16_stockfish_de_mentira.exe)']
```

**A sétima `QGroupBox` que nenhuma passada do ciclo 15 visitava agora existe e é desenhada** — é a
`Motor (<binário>)` de `painel_de_estudo.py:404`, o único título de largura variável do produto
(§10).

**A mensagem parou de mandar fazer o que não resolve.** `strings.SEM_MOTOR_STATUS` diz
*"Nenhum motor UCI foi encontrado nesta máquina, e os comandos de análise estão desligados."*, e
quem explica o **como** é a dica do item cinza (`strings.SEM_MOTOR_DICA`), que nomeia os dois
caminhos que `find_engine` de fato percorre: `engines/` e `engine.path` no `settings.json`.

*Alvo do crítico: 0 comandos habilitados que não podem ter efeito — hoje **0**, medido pelo portão
novo do §1.1; e `find_engine`/`EngineAnalyzer` deixam de ser código sem chamador — hoje têm um,
cobrado por `test_o_motor_deixou_de_ser_codigo_sem_chamador`.*

### 1.1 O portão novo: **todo comando habilitado tem implementação alcançável**

O crítico pediu o portão e a mutação. `caissa/ui/audit/comandos.py` mede **todo comando desenhado**
— linha de menu, botão de fita, pílula de fila — e faz três perguntas:

* **solto**: habilitado e com **zero** receptores vivos no sinal. Clicar não faz nada.
* **promete**: habilitado e exigindo um recurso que a sessão não tem
  (`sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR`, hoje o único).
* **cinza sem motivo**: desabilitado e sem dica. Desabilitar sem explicar é o mesmo defeito com o
  sinal trocado.

```
  arranjo             medidos  habilit  soltos  prometem  cinza s/motivo  veredito
  classica                117      114       0         0               0  PASSOU
  foco                    121      118       0         0               0  PASSOU
  fita                    141      138       0         0               0  PASSOU
  medidos 379 | habilitados 370 | soltos 0 | prometem 0 | cinzas sem motivo 0
  sinais que nao soube perguntar 0                            Veredito: PASSOU
```

**Duas provas de vida, uma por regra, as duas mutando a janela montada sem tocar um byte do
produto:**

```
  --desligar salvar
      classica/foco/fita  [menu] salvar  "Salvar a posição"  SOLTO (receptores=0)
      soltos 3 | Veredito: REPROVOU                      (era 0 | PASSOU)

  --religar analisar_posicao,analise_continua,variante_do_motor      (numa maquina sem Stockfish)
      9 linhas PROMETE (3 peles x 3 comandos), receptores=2, exige=motor
      prometem 9 | Veredito: REPROVOU                    (era 0 | PASSOU)
```

A segunda reconstrói **exatamente** o estado do ciclo 15 e o portão o reprova. E a passada
`--com-motor`, que aponta `CVOFF_ENGINE_PATH` para um arquivo criado na pasta temporária do próprio
portão, devolve `379 medidos | 379 habilitados | 0 | 0 | 0 — PASSOU`: sem ela, "desabilitados" seria
indistinguível de "sempre desabilitados".

`nao_perguntados` é a conta do que ele **não** mediu — `receptores` negativo, quando o binding não
sabe responder. Hoje **0**, publicada ao lado do placar.

---

## §2 — Item 2: a régua pergunta a fonte a quem o Qt de fato consulta

**O mecanismo, medido por mim antes de mexer em qualquer coisa.** `c16_quem_pinta.py`, um widget
isolado por seletor, três combinações cada, texto `Comentário do lance` (referências: 9 pt = 109 px,
12 pt negrito = 159 px, 20 pt negrito = 267 px):

| seletor | folha 20pt / widget 9pt | folha 12pt / widget 20pt | quem ganha |
|---|---|---|---|
| `QGroupBox::title` | **109 px** | **265 px** | **o WIDGET** |
| `QHeaderView::section` | **265 px** | **157 px** | **a FOLHA** |
| `QTabBar::tab:selected` | **265 px** | **157 px** | **a FOLHA** |
| `QLabel[apoio="true"]` | **265 px** | **157 px** | **a FOLHA** |

Número por número igual ao §4.1 do crítico, com o meu instrumento. **Um dos quatro seletores da
folha obedece à regra contrária dos outros três**, e `PAPEL_PINTADO` tratava todos igual.

**O modelo passa a registrar quem pinta.** `ui/folha_de_estilo.QUEM_PINTA` é a tabela nova:
`seletor -> O_WIDGET | A_FOLHA`, com a medição acima escrita no docstring. Ela **não pode ficar para
trás da folha**: `test_quem_pinta_cobre_toda_regra_de_fonte_da_folha` percorre o texto gerado da
folha, acha todo bloco com declaração `font-*` e exige resposta para cada um — um quinto seletor
sem entrada derruba.

**A régua pergunta a quem ganha.** `texto_pintado.fonte_que_pinta(regras, quem_pinta=…, base=…)`
devolve `base` (o `QWidget.font()`) quando o widget ganha e a fonte da folha quando a folha ganha; e
`quem_pinta` é lido **do produto** em `medir_uma_passada` (`dict(folha_de_estilo.QUEM_PINTA)`), não
copiado para dentro do portão. Um seletor sem resposta faz `_quem_pinta` **levantar** — um padrão
silencioso mediria a fonte errada calado, que é como este ponto cego viveu catorze ciclos.

**A prova pedida: um caso em que as duas discordam.**
`test_a_regua_mede_a_fonte_que_ganha_em_cada_um` põe o widget a 9 pt e a folha a 20 pt e cobra:

```
  titulo   -> a regua responde  9 pt   (a folha de 20 pt e' descartada)   == o que a tela desenha
  cabecalho-> a regua responde 20 pt   (a folha ganha)
  a regua ANTIGA (fonte_da_folha) responderia 20 pt nos dois — e a tela desenha 34 px, nao 85
```

**O que isso fez com o número publicado.** `cego` deixou de significar "a folha diz outra coisa" e
passou a significar "a fonte que **pinta** difere da do widget": num subcontrole pintado pelo
widget, uma régua comum acerta, e chamá-la de cega era o erro. O placar continua em **24 cegos** de
540 — e agora os 24 são a aba selecionada de cada passada, que é onde a folha de fato ganha e o
widget de fato diverge.

### 2.1 Item 3: `PAPEL_PINTADO` e `PAPEL_POR_CLASSE` param de ser duas tabelas

Não é mais um teste de igualdade entre dois literais: é **derivação**.

```python
PAPEL_PINTADO = {
    "QGroupBox::title":     tipografia.PAPEL_POR_CLASSE["QGroupBox"],
    "QHeaderView::section": tipografia.PAPEL_POR_CLASSE["QHeaderView"],
    …
}
```

`test_o_degrau_do_titulo_e_o_da_classe_do_grupo` afirma a igualdade, e
`test_a_faixa_acompanha_a_classe_e_nao_o_literal` prova que é derivação e não coincidência: ele
troca `PAPEL_POR_CLASSE["QGroupBox"]` para `AUXILIAR`, recarrega a folha e cobra que a **faixa** siga
o degrau novo. Com dois literais, a faixa ficaria onde estava e o título encolheria dentro dela —
que é exatamente a deriva que o §4.2 do crítico descreve.

---

## §3 — Item 4: a forma curta `font:` deixa de escapar das duas peneiras

**A defesa que o módulo citava não existia.** `PROPRIEDADES_DE_FONTE` escrevia *"se ela aparecer um
dia, `regras_de_fonte` não a vê e o teste `test_a_regua_le_toda_regra_de_fonte_da_folha` falha"*, e
esse teste não existia em suíte nenhuma. O que existia afirmava um superconjunto.

**A causa era uma peneira só fazendo dois trabalhos.** `_declaracoes_de_fonte` filtrava pela **mesma**
tupla que `regras_de_fonte`: o que a régua não sabia ler, ela também não via. Hoje quem decide *"isto
mexe na fonte"* é `mexe_na_fonte` (larga: `font` e `font-*`) e quem decide *"eu sei interpretar
isto"* é `PROPRIEDADES_DE_FONTE` (estreita). A diferença entre as duas vira `seletores_ignorados`.

As quatro sabotagens do crítico, rodadas por mim como teste parametrizado
(`test_a_forma_curta_de_font_nao_escapa`):

| sabotagem | `seletores ignorados` antes | agora |
|---|---|---|
| `QGroupBox::title { font: bold 20pt "Segoe UI" }` | **0 — SILÊNCIO** | **1** |
| `QGroupBox::title, QHeaderView::section { font-size: 20pt }` | 1 | 1 |
| `QWidget QGroupBox::title { font-size: 20pt }` | 1 | 1 |
| `QGroupBox#painel::title { font-size: 20pt }` | 1 | 1 |

**E o teste que o módulo cita passou a existir, com o nome certo e a forma certa.**
`test_a_regua_le_toda_regra_de_fonte_da_folha` é uma **partição**, não um superconjunto: todo bloco
da folha que mexe na fonte está ou entre os lidos, ou entre os publicados como fora da análise.
Nada cai no meio. Nas duas densidades: `4 regras lidas, 0 ignoradas, 0 no meio`.

**Um terceiro buraco da mesma espécie, achado ao consertar este.** `font-style` estava em
`PROPRIEDADES_DE_FONTE` — declarado como legível — e `_aplicar` **não tinha ramo para ele**: a regra
passava pela peneira e era descartada em seguida, e o itálico muda o avanço horizontal do texto.
`Fonte` ganhou `italico`, `_aplicar` ganhou o ramo e `_qfont`/`_fonte_de` o levam ao `QFont`.
Cobrado por `test_font_style_deixou_de_ser_lido_e_jogado_fora`.

### 3.1 A varredura que o crítico mandou fazer: **toda** citação de teste em `src/caissa/`

Foram **23 citações** de nome de teste em docstrings de `src/caissa/`. Conferidas uma a uma contra
as duas suítes:

| citação | onde | veredito |
|---|---|---|
| `test_a_regua_le_toda_regra_de_fonte_da_folha` | `texto_pintado.py` | **não existia — escrito neste ciclo** |
| `test_capture_cobre_todas_as_peles` | `capture.py:70` | **nome errado**: o teste se chama `test_a_captura_cobre_toda_pele_registrada`. Citação corrigida |
| `test_a_heranca_bate_com_a_do_qt` | `contraste.py:161` | **não existe em nenhuma das duas suítes** — ver abaixo |
| `tests/test_busy.py` | `progresso.py` ×2 | existe (no tronco) |
| `test_ui_semantica_cor` | `contraste.py:985` | existe (no tronco) |
| as outras 17 | `export/`, `typeset/`, `llm/`, `vision/`, `ui/` | existem |

**O `test_a_heranca_bate_com_a_do_qt` não podia virar teste desta suíte** — o venv daqui não tem
binding de Qt, e um teste que sempre pula não é defesa: seria o mesmo defeito com outra roupa.
Virou instrumento (`c16_heranca_contra_o_qt.py`), que roda no venv do tronco. Rodado, **ele achou o
que a defesa inexistente deixava passar**:

```
  QScrollBar   declarada ('QWidget',)   o Qt diz ('QAbstractSlider', 'QWidget')
  QSlider      declarada ('QWidget',)   o Qt diz ('QAbstractSlider', 'QWidget')
  QToolTip     declarada ('QWidget',)   o Qt diz ()
  38 classes conferidas | 2 divergencias reais | 1 declarada
```

As duas reais foram consertadas (`QAbstractSlider` entrou na cadeia); a de `QToolTip` é deliberada
— ele é um `QObject` de fachada e a folha `QToolTip { … }` é aplicada ao rótulo interno, que é um
widget — e agora está **escrita** no lugar, com o instrumento nomeado ao lado. Divergência declarada
é o contrário de divergência esquecida.

---

## §4 — Item 5: duas legendas iguais não convivem numa tela

Medido por `c16_retratar_os_dialogos.py`, nos treze diálogos:

```
  pares de botoes com a MESMA legenda visiveis ao mesmo tempo:  2 -> 0
```

**`_JanelaDePartidas`** desenhava `Fechar` (estado vazio, `acao=self.reject`) e `Fechar` (rodapé,
`QDialogButtonBox.Close`) a 160 px um do outro numa janela de 560×400, com a distinção dada ao
`accessibleName` — quem **ouve** recebia dois nomes e quem **vê**, a mesma palavra duas vezes.
Entre as duas saídas que o crítico ofereceu (*"faz alguma coisa, ou sai"*), **sai**: o gesto que
resolve ali é escolher outra posição no tabuleiro, e este diálogo não tem como oferecê-lo — quem
troca de base é a Galeria, e a sala só **lê** a lista de bases. Um botão que repete o rodapé não é
uma saída a mais; é a mesma saída desenhada duas vezes. O título e a frase continuam dizendo o que
falta e por quê (olhei o retrato: `Nenhuma partida chega aqui` + frase + um `Fechar` só).

**`DialogoDePartidas`** desenhava `Procurar por nome` no estado vazio **e** no rodapé, ligados à
mesma ação. Some o do rodapé enquanto o vazio o oferece — o mesmo gesto que
`_JanelaDePartidas` já usava para esconder a frase do topo. **A condição é a que decide o vazio
(`not self._visiveis and not filtrando`) e não `self.vazio.isVisible()`**: este método roda na
construção, antes do `show()`, e ali `isVisible()` é `False` para tudo. A primeira forma deste
conserto passou pela leitura e falhou na tela; ela está registrada porque o número mudou de 1 para
0 só depois da segunda.

**E o controle não se perde em estado nenhum**, que é o que separa "tirar a duplicata" de "tirar a
função". Medido nos três estados do diálogo:

```
  lista vazia          -> ['Procurar por nome', 'Aplicar', 'Aplicar aos vizinhos…', 'Fechar']
                          (o do estado vazio; o do rodape sumiu)
  com 3 partidas       -> ['Aplicar', 'Procurar por nome', 'Aplicar aos vizinhos…', 'Fechar']
                          (o do rodape voltou; o vazio nao esta na tela)
  filtro sem casar     -> o do rodape, e o do vazio some (o vazio de filtro nao oferece procurar)
```

Exatamente **um** `Procurar por nome` desenhado nos três.

Portão de teclado sobre os treze diálogos depois da mudança: **PASSOU**, com
`_JanelaDePartidas 2 focáveis, 2 pelo Tab, fecha, 0 sem nome, 0 sem papel, 0 nome vazio`.

---

## §5 — Itens 6 e 7: a conta de rótulo passa a incluir a janela

`c14_miudezas_dos_dialogos.py` percorre `teclado.RECEITAS` — as **treze telas de diálogo**. A janela
principal ficava fora, e o item 10 do ciclo 13 fechou `filtro → Filtro` só nos diálogos. Escrevi a
conta que faltava: `c16_rotulos_de_campo.py` percorre as **seis abas** da janela nas três peles.

Primeira passada, **antes** de consertar (a lista inteira, não só o que o crítico nomeou):

```
  medidos: 117    comecando em minuscula: 5
      [Galeria/QRadioButton] 'padrão'  'com link'  'sem link'
      [Galeria/QPushButton ] 'anterior'  'próximo'
```

`outro` já tinha virado `Outro`; alargar a população achou **mais cinco**, todos na mesma aba, todos
a mesma espécie. Consertados (`LINK_CHOICES` e os dois botões de navegação). Depois, nas três peles:

```
  classica  medidos 117  minusculas 0  crases 0  reticencias ASCII 0
  fita      medidos 117  minusculas 0  crases 0  reticencias ASCII 0
  foco      medidos 117  minusculas 0  crases 0  reticencias ASCII 0
```

**Item 7 — `brancas`/`Brancas`.** Os dois pares de rádios saíam de literais cravados em dois painéis
(`painel_da_galeria.py:511` em minúscula, `painel_de_resultado.py:370` capitalizado), sob o mesmo
rótulo `Lado a jogar`, em duas abas. Os dois passaram a iterar `ui/strings.SIDE_LABELS`, que é o
catálogo que `ui/formato.py:12` já mandava usar. Um literal só, e é por isso que `brancas` sumiu da
lista acima sem ninguém escrevê-lo de novo.

---

## §6 — Item 8: nem crase nem três pontos em texto desenhado

**Crases:** `ui/strings.COLECAO_VAZIA_FRASE` mandava *"Escolha outro `` `.pgn` ``"* e as duas crases
eram desenhadas. Hoje: *"Escolha outro arquivo .pgn"*. **A informação ficou** — cobrado por
`test_a_frase_da_colecao_vazia_perdeu_as_crases_e_continua_dizendo_o_mesmo`, que exige `.pgn` no
texto. Olhei o retrato ampliado de `_JanelaDeColecao`: sem crase.

**Reticências:** **26 trocas** de `...` para `…` em 8 arquivos de `qt/` — os treze textos que o
crítico nomeou mais os que a mesma varredura achou ao lado deles (`Aplicar aos vizinhos…`,
`Preparando treino…`, `Treinando modelo…`, `Cancelando treino…`, `Treinando… época`, `varrendo…`,
`cancelando…`, `Varrendo o livro…`, `Cancelando…`, `Renderizando página N…`, `Lendo a folha N…`,
`Exportando para X…`, `Iniciando exportação do PDF para PGN…`, `Cancelando exportação…`,
`Exportando PDF → PGN…`, `procurando N par(es)…`, `base: N M partidas lidas…`,
`base: N posição(ões) a procurar…`, `base: pedaço N de M…`, `Procurando duplicatas…`, `pensando…`).

**Sobrou um, e ele fica declarado.** `ui/estudo_lista.py:225` escreve `f"{fullmove}... "` —
`12... Nf6`, a numeração de um lance das pretas em PGN. São três pontos por **convenção de notação
de xadrez**, iguais aos do arquivo de onde a linha vem; trocá-los faria a lista de lances divergir
do texto que ela representa. `test_a_reticencia_do_lance_preto_e_notacao_e_nao_tipografia` o fixa
pelo nome, para que "0 reticências ASCII" seja uma afirmação com a exceção nomeada e não uma
afirmação com um buraco.

O teste do catálogo (`tests/unit/ui/test_texto_desenhado.py`) diz, no cabeçalho, **qual é a
população que ele alcança e qual não** — os dicionários (`DIVERGENCIAS_DECLARADAS` guarda prosa de
manutenção, não texto de tela) ficam de fora, e quem cobre o resto é a tela, com os números do §5.

---

## §7 — Item 9: o portão de bloqueio deixa de morrer calado

**Reproduzi o defeito com a receita publicada** (`PYTHONPATH=<suite>\src;<tronco>\src`,
`--execucoes 1 --sem-perfil`), 8 invocações idênticas:

```
  ANTES:  2 de 8 morreram calados, codigo 139 (0xC0000005), sem imprimir um caractere
          6 completaram: abrir PDF 208.1 / 209.8 / 209.8 / 212.5 / 218.8 / 218.9 ms
```

**E procurei a causa em vez de adivinhá-la.** O crítico suspeitou do amostrador de pilha
(`sys._current_frames` + `traceback.extract_stack` sobre a thread da interface). Testei: com a foto
da pilha desligada em memória, **3 de 8 continuaram morrendo**. Não era ela.

A causa é a que este arnês já tinha documentado em outro módulo desde o ciclo 9: `medir()` fazia
`janela.close()` e **nada mais**. A `JanelaPrincipal` morria por coleta de lixo do Python com
`DeferredDelete` ainda pendentes no Qt — o aborto sem traceback que `teclado._descartar` descreve
palavra por palavra, e que este era o único módulo do arnês a não usar. `processEvents` não esvazia
aquela fila; só `sendPostedEvents(None, DeferredDelete)` esvazia. `_perfilar` tinha o mesmo problema
na janela fria que ele fabrica.

```
  DEPOIS: 0 de 8 morreram calados, 8 completaram      (--execucoes 1 --sem-perfil)
          abrir PDF 213.1 213.5 213.6 214.3 214.7 215.1 217.8 219.3  -> mediana 214.5 ms
  DEPOIS: 0 de 3 morreram, com o perfil ligado e 3 execucoes  -> 7 violacoes, REPROVOU
```

*Alvo do crítico: 3 de 3 invocações completam pela receita publicada — hoje **11 de 11**.*

**O veredito não mudou e continua aberto:** `REPROVOU, 7 operações`, abrir PDF mediana **214,5 ms**
contra o orçamento de 16 ms. É o item de sempre (§14).

---

## §8 — Item 10: a frase do portão diz a população que ele alcança

A frase publicada era *"Texto PINTADO: a régua lê a fonte da folha de estilo, e não `QWidget.font()`.
0 tinta coberta e 0 tinta cortada, em todo arranjo e em todo tamanho"* — e as duas metades estavam
erradas: a régua não lê sempre a folha (§2), e "todo arranjo" era a janela recém-aberta. Hoje o
relatório publica dois campos:

```
  portao:    "Texto PINTADO: a regua le a fonte que DE FATO pinta cada subcontrole
              (folha_de_estilo.QUEM_PINTA) -- nem sempre a da folha, nem sempre a do widget.
              0 tinta coberta e 0 tinta cortada."
  populacao: "os QGroupBox com titulo VISIVEIS na janela recem-aberta (um PDF, nenhum PGN,
              nenhum filtro digitado, motor conforme a maquina), todo QHeaderView visivel e a
              aba corrente de cada QTabBar, nas seis abas mais os treze dialogos.
              FORA: a setima QGroupBox 'Motor (<binario>)', que so' existe com motor
              instalado; e QLabel[apoio=true], o quarto seletor que a folha pinta, para o qual
              nao ha regua."
```

**`QLabel[apoio="true"]` sai da tabela do §1.5 e passa a ser declarado como não medido**, que era a
segunda metade do item: o relatório do ciclo 14 afirmava que ele era "medido junto, 0 cortados", e
nenhum `QLabel` entrava na conta. `medir_a_tela` diz isso no próprio docstring.

---

## §9 — Item 11: a fotografia do ANTES volta a ser a tela de antes

**O crítico estava certo, e o defeito era pior do que o par que o documentava.** Reaplicar a folha
faz o Qt despolir e repolir a janela inteira e **desfaz a varredura de `qt/escala.aplicar_escala`**:
o ANTES do ciclo 14 pintava o título a 9 pt não-negrito (115 px de tinta) onde o produto pintava
12 pt negrito (157 px). `c16_recorte_do_titulo.py` reaplica a escala **depois** de trocar a folha, e
imprime as duas fontes em cada passada para que "só a faixa muda" seja conferível:

```
  fita/compacta 1920px  DEPOIS
    produto:  faixa 21 px   grupo.font() = Segoe UI 12.0pt negrito=True
      [Estudo] Comentário do lance   tinta 159 px   COBERTO 0 px

  fita/compacta 1920px  ANTES
    produto:        faixa 21 px  grupo.font() = Segoe UI 12.0pt negrito=True
    folha trocada:  faixa  4 px  grupo.font() = Segoe UI  9.0pt negrito=False   <- o defeito do c14
    escala reaplicada em 161 widgets: faixa 4 px  grupo.font() = Segoe UI 12.0pt negrito=True
      [Estudo] Comentário do lance   tinta 159 px   COBERTO 8 px
```

**159 px nos dois lados** — a mesma tinta que a captura **não encenada** do ciclo 12 mede (157 px, a
2 px de arredondamento de métrica). Os seis números do ANTES reproduzem os do ciclo 13 à unidade:
`3 · 8 · 8 · 8 · 5 · 5` na compacta, `2` na confortável. **84 PNG** (42 ANTES + 42 DEPOIS), seis
arranjos.

**Olhei os pares, e digo exatamente quais.** Abri **12 dos 84 PNG** — 8 ANTES e 4 DEPOIS —
cobrindo quatro dos seis arranjos e cinco dos seis grupos: `fita/compacta` (`Comentário do lance`,
`Lances`, `Filtros`, `Reconhecido (clique e arraste…)`, `Este diagrama`), `foco/compacta`
(`Lances`), `classica/compacta` (`Cabeçalhos do PGN`) e `classica/confortavel`
(`Cabeçalhos do PGN`). **Não abri as 84, e não digo que abri**; os arranjos que faltam são a mesma
tela na mesma densidade, e o que os separa é o número que o instrumento imprime linha a linha.

O que se vê: em `Comentário do lance` o filete do quadro atravessa as letras no ANTES e a haste do
`ç` some; no DEPOIS o rótulo está inteiro acima do quadro. Em `Lances`, na clara e na escura, a base
de cada letra está comida no ANTES. Em `Filtros` (8 px) o corte é o mesmo; em `Reconhecido…` (3 px) e
`Cabeçalhos do PGN` na compacta (5 px) e na confortável (2 px), o corte é proporcional ao número
medido — que é a prova de que a fotografia e a régua estão medindo a mesma coisa.

**E a mesma correção entrou no portão.** `--faixa-de-antes` tinha o mesmo defeito do script de
captura: sem reaplicar a escala, ele media 16 px de tinta onde a tela do ciclo 13 tinha 21, e
publicava **36** títulos cobertos. Com a escala reaplicada:

```
  --faixa-de-antes:  medidos 540 | cegos 24 | cobertos 108 | cortados 0     REPROVOU
     classica/compacta 1280   Reconhecido (clique e arrast  COBERTO 3px  (TabuleiroEditavel)
                              Lances                        COBERTO 8px  (QTextBrowser)
                              Comentário do lance           COBERTO 8px  (QTextEdit)
                              Filtros                       COBERTO 8px  (QLabel, QLineEdit)
                              Cabeçalhos do PGN             COBERTO 5px  (QLabel, QLineEdit)
                              Este diagrama                 COBERTO 5px  (BarraFluida)
```

**108**, com os seis nomes, os seis números e os seis culpados do §2.3 do crítico.

### 9.1 Os retratos de diálogo: **13 arquivos distintos**, e olhei todos

O ciclo 14 publicou oito e **dois eram o mesmo arquivo** (`JanelaDeBusca` simples e com
substituição, sendo os dois o da substituição), de modo que a tela que o item 9 conserta nunca foi
fotografada; e o de `DialogoDeTreino` mostrava a barra **indeterminada**, que é o estado da receita
do arnês e não o do produto.

`c16_retratar_os_dialogos.py` fotografa os **treze** no estado em que o produto os abre — inclusive
`DialogoDeTreino` com `progresso(3, 8)` aplicado, que é o que `ControladorDeTreino.iniciar` emite na
mesma thread logo depois do `mostrar()` — e imprime o sha256 de cada um:

```
  telas fotografadas: 13
  arquivos com sha256 repetido: 0 []
  pares de botoes com a MESMA legenda visiveis ao mesmo tempo: 0
```

Abri os treze. O que vi, um a um: `JanelaDeBusca (Achar no texto)` com **um** campo indo até a borda
direita e sem `Substituir todos` — a tela que nunca tinha sido fotografada; `JanelaDeBusca
(substituindo)` com dois campos e o botão, arquivo diferente; `DialogoDeTreino` com a barra
**determinada** e `época 3 de 8` desenhado; `DialogoDePartidas` com um único `Procurar por nome`;
`_JanelaDePartidas` com um único `Fechar`; `_JanelaDeColecao` sem as crases; `JanelaDeAtalhos` sem
rolagem horizontal; `JanelaDeEstatisticas` com título e `Fechar`; `DialogoDeBases`,
`DialogoDeEscopo`, `JanelaDaPaleta`, `_JanelaDeColar` corretos. `ControladorDeTreino` é um objeto de
100×30 que o produto nunca mostra — o retrato existe e a receita diz isso.

---

## §10 — Item 12: a largura de `Motivo` vem de onde não há informação

Com `Só pendentes` marcado — que é como a aba abre — **toda linha tem o mesmo status**: a coluna
`Status` desenha a mesma palavra 27 vezes, zero bits, por construção do próprio filtro. Ela passa a
ser **escondida** enquanto o filtro está ligado; `Motivo` é `elastica=True` e recebe o espaço sem
que ninguém precise somar nada. Esconder e não estreitar: uma coluna de 20 px com `pende·` é pior
que coluna nenhuma. Ela **volta** ao desmarcar o filtro, que é quando o status volta a variar.

Medido (`c16_largura_do_motivo.py`, 27 itens, motivos do tamanho dos que a varredura produz):

```
  1280 px  Só pendentes=sim   Status=ESCONDIDA   Motivo= 419 px   elididos 0 de 27
  1280 px  Só pendentes=não   Status=80 px       Motivo= 339 px   elididos 7 de 27
  1366 px  Só pendentes=sim   Status=ESCONDIDA   Motivo= 467 px   elididos 0 de 27
  1920 px  Só pendentes=sim   Status=ESCONDIDA   Motivo= 780 px   elididos 0 de 27
```

**+80 px para `Motivo` em toda largura, e a elisão a 1280 px com o filtro ligado vai a 0.** Digo o
que este número **não** é: o `25 de 27` do crítico foi medido sobre a fila real da máquina dele, com
motivos mais longos que os meus; o que eu meço é o efeito da mudança sobre a mesma fila, com e sem
o filtro (7 → 0). O item de `Motivo` a 1280 px **sem** o filtro continua aberto, com 7 de 27.

---

## §11 — O que o placar do portão do texto pintado diz agora

```
  24 passadas (3 peles x 2 densidades x 4 larguras)
  medidos 540 | cegos (a fonte que pinta != a do widget) 24 | cobertos 0 | cortados 0
  seletores de fonte que a regua NAO analisou: 0 []
  Veredito: PASSOU
```

**`medidos` caiu de 564 para 540, e eu digo por quê:** são exatamente 24 — uma por passada — e é a
seção `Status` da tabela de Revisão, que o §10 esconde enquanto o filtro está ligado. Um cabeçalho
que não é desenhado não é medido. Nenhuma outra medição saiu da conta.

**E os 24 cegos têm nome.** Medidos um a um numa passada (`classica`, 1920 px): das 20 medições das
seis abas mais a janela, **uma** é cega, e é sempre a mesma —
`QTabBar::tab 'Galeria'  widget=9.0pt/não-negrito  pinta=9.0pt/negrito`. A folha ganha ali
(`QUEM_PINTA["QTabBar::tab:selected"] = A_FOLHA`) e o widget de fato diverge. Os títulos de grupo,
que a régua do ciclo 14 contava como cegos, **nunca foram**: quem os pinta é a fonte do widget.

---

## §12 — Item 14: o que continua aberto, com os números de sempre

Nenhum destes precisa fechar neste ciclo. **A terceira coluna diz se eu o remedi ou se estou
repetindo o número do ciclo 15** — repetir sem remedir e não dizer é o que transforma um item
aberto em folclore.

| item | número | remedido neste ciclo? |
|---|---|---|
| bloqueio > 16 ms | **REPROVOU, 7 operações**; abrir PDF mediana **214,5 ms** | **sim**, 11 invocações (§7) |
| `DialogoDeTreino` sem botão desenhado | `botoes=[]`, e a frase *"quem cancela é o rodapé"* desenhada | **sim**, no retrato do §9.1 |
| `Motivo` a 1280 px **sem** o filtro | 7 de 27 elididos | **sim** (§10), sobre a minha fila |
| vazio de painel a 4K | 5 de 6 acima de 200 kpx, pior 3 104,2 (Revisão) | **não** — número do ciclo 15, repetido |
| cabeçalhos de fita na compacta | 0 de 5 desenhados | **não** — número do ciclo 15, repetido |
| botões de fita sem rótulo | 6 de 24 | **não** — número do ciclo 15, repetido |
| tinta dos ícones | 17,6 %–41,4 % | **não** — número do ciclo 15, repetido |
| marca da FEN só à direita | aberto | **não** — não remedido |
| a etiqueta local que segura `7bcb396` | aberto | **não** — não remedido |

O que **posso** afirmar sobre os cinco não remedidos é que nada neste ciclo os toca: as capturas do
§9 mostram as mesmas seis abas, os portões de teclado e de contraste passaram sobre as três peles,
e nenhum arquivo de ícone, de fita ou de marca de FEN entrou no §16.

---

## §13 — Item 13: o conserto preciso de `tests/integration/test_gpu_parity.py`

**Não é meu, e por isso está escrito aqui em vez de aplicado.** `tests/integration/` está fora da
minha área por carta.

O defeito: `test_gpu_fp16_parity` grava **sempre** em `REPO_ROOT/benchmarks/reports/parity_fp16.json`,
sem pasta por execução e sem opção — de modo que qualquer agente que cumpra o §6 da carta (rodar
`pytest tests`) sobrescreve um artefato publicado da pasta de outro. É o item 16 do ciclo 11
(*"`--saída` é obrigatório: este portão não escolhe pasta por você"*) vivo dentro de um teste.

```python
# tests/integration/test_gpu_parity.py:309, hoje
destination = REPO_ROOT / "benchmarks" / "reports" / "parity_fp16.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
```

**O conserto, em três linhas, e ele não perde o número:**

1. Acrescentar uma opção ao `conftest.py` de `tests/` (ou de `tests/integration/`):

```python
def pytest_addoption(parser):
    parser.addoption(
        "--parity-out",
        default=None,
        help="onde gravar parity_fp16.json. Sem ela, o relatorio vai para tmp_path e o "
             "numero continua no stdout do teste: nenhuma suite escreve numa pasta publicada.",
    )
```

2. Trocar a assinatura do teste para receber `tmp_path` e `request`:

```python
def test_gpu_fp16_parity(crops, cpu_reference, gpu_fp16, tmp_path, request) -> None:
    ...
    escolhido = request.config.getoption("--parity-out")
    destination = Path(escolhido) if escolhido else (tmp_path / "parity_fp16.json")
```

3. Trocar a frase da asserção, que hoje manda olhar um caminho que pode não existir mais:

```python
    assert report["fen_mismatches"] == 0, (
        f"fp16 mudou {report['fen_mismatches']} FEN(s) em {report['boards']} tabuleiros; "
        f"nao embarcar fp16 neste caminho. Detalhes em {destination}"
    )
```

O `print` que já existe na linha 308 mantém o número no stdout, então **nada se perde** quando
ninguém passa `--parity-out`. Quem quiser o artefato publicado passa a dizer onde — que é a mesma
disciplina dos cinco portões desta frente.

**Sinalizado para quem for dono de `tests/integration/`.** Registro também o estado observado: antes
da minha execução, `benchmarks/reports/parity_fp16.json` tinha sha256 `e7dffbfb…4c24f224` e `mtime`
de 00:31; rodar `pytest tests` o regravou às **01:34**, no meio da minha passada — exatamente o que
o crítico do ciclo 15 relatou, confirmado uma segunda vez.

---

## §14 — Suítes

```
  tests/unit/ui                        271 passed em 2,51 s   (eram 238, +33)
     test_texto_pintado.py  27 -> 40   (a particao, as 4 sabotagens, quem pinta, as duas tabelas,
                                        font-style, e o seletor sem resposta)
     test_comandos.py       novo, 14   (a aritmetica do portao novo e a declaracao do produto)
     test_texto_desenhado.py novo, 5   (crase, reticencia, e a excecao da notacao PGN)
     test_arquitetura.py    13 -> 14   (o parametrizado le a pasta de audit/ e achou comandos.py)

  nossa, sem test_packaging.py         3 159 passed, 1 skipped, 0 failed em 671,6 s
     eram 3 126 + 1; a diferenca sao os 33 testes novos. O pulo e' o de sempre
     (test_fonts.py:333, WOFF2 sem Brotli).

  tronco                               3 failed, 4 486 passed, 2 skipped, 4 536 subtests em 280,4 s
     Eram 3 failed / 4 486 passed: identico. As tres sao as pre-existentes, nomeadas no §14.1 --
     test_docs, test_editor_model e test_strings::AccentTests. `test_packaging` voltou a passar.
```

### 14.1 O que eu quebrei no tronco e como consertei

**Rodei a suíte do tronco no meio do ciclo e ela foi de `3 failed` para `7 failed`.** Os quatro são
meus e digo o que fiz com cada um:

1. **`test_packaging.py::TamanhoDaJanelaTests::test_a_janela_nao_volta_a_crescer`** —
   `qt/janela.py` passou de **1883 para 1967 linhas** com a ligação do motor. A catraca existe para
   empurrar código para `ui/`, e o recado dela oferece duas saídas: baixar o que der para `ui/`, ou
   registrar um placar novo. **Não registrei placar novo.** Baixei:
   `motor_de_analise` e `encerrar_o_motor` foram para `ui/sala_declarada.py`; o laço que desabilita
   virou `menu.BarraDeMenus.impedir`; e mais duas peças que já deviam estar lá —
   `estado_do_rodape.contagem_das_caixas` (quatro somas sobre as caixas da página) e
   `page_results.colocacoes_conferidas` (a leitura de `fen_edits`). Hoje: **1883 linhas**, a catraca
   passa, e `ui/` ganhou três funções puras afirmáveis sem abrir tela.
2. **`test_qt_dialogos.py::…test_cancelar_marca_o_evento…`** e
   **`test_qt_painel_de_revisao.py::…test_o_progresso_vem_da_thread…`** — os dois fixam o texto
   desenhado que o item 8 mandou trocar (`...` → `…`). **Troquei o caractere esperado e nada mais**:
   a asserção é a mesma, com o mesmo `assertEqual` sobre a mesma frase.
3. **`test_qt_painel_de_estudo.py::…test_sem_motor_a_secao_nao_existe_e_os_comandos_dizem_isso`** —
   ele contava três ocorrências de `"Sem motor UCI instalado"`, que é a frase que o item 1 tirou.
   Trocado para contar `strings.SEM_MOTOR_STATUS`: **é mais forte que a versão de antes**, porque
   passa a cair também no dia em que o catálogo mudar e o painel não.

**São três arquivos de teste do tronco tocados, e eu os declaro em vez de os esconder.** O ciclo 15
fez virtude de "zero testes do tronco alterados"; mudar texto de interface **obriga** a mexer em quem
o fixa, e a alternativa — desistir do item 8 — seria escolher a métrica em vez do produto. Nenhuma
asserção foi enfraquecida: duas trocaram um caractere, uma passou a ler o catálogo.

As três pré-existentes continuam pré-existentes e não são desta frente:
`test_docs.py::test_a_arvore_do_README_lista_todo_modulo_do_pacote` (dois módulos fora da árvore do
README), `test_editor_model.py::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter`
(quatro módulos de `ui/` fora de `SEM_TKINTER`) e
`test_strings.py::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word` (seis literais
em `biblioteca.py`, `substituicao.py` e `tokens.py` — três arquivos que eu não toquei).

---

## §15 — Portões, todos rodados por mim neste ciclo

| portão | número | veredito |
|---|---|---|
| `texto_pintado` | 24 passadas, 540 medidos, 24 cegos, 0 cobertos, 0 cortados, 0 ignorados | **PASSOU** |
| `texto_pintado --faixa-de-antes` | 108 cobertos, 6/6 na compacta com `3·8·8·8·5·5` | **REPROVOU** (é a prova de vida) |
| `comandos` | 379 medidos, 370 habilitados, 0 soltos, 0 prometem, 0 cinzas sem motivo | **PASSOU** |
| `comandos --com-motor` | 379 medidos, 379 habilitados, 0/0/0 | **PASSOU** |
| `comandos --desligar salvar` | soltos 3 | **REPROVOU** (prova de vida) |
| `comandos --religar` (os três) | prometem 9 | **REPROVOU** (prova de vida) |
| `teclado` | os seis arranjos + os treze diálogos, `0 sem nome, 0 sem papel, 0 nome vazio` | **PASSOU** |
| `contraste` | claro **300/220/0**, menor folga 3,27:1; escuro **300/220/0**, menor folga 3,03:1 — idênticos aos do ciclo 15, **depois** do conserto de `HERANCA` (§3.1), porque a folha não escreve regra nenhuma para `QAbstractSlider` | **PASSOU** |
| `bloqueio` | 11 de 11 invocações completam; 7 operações violam; abrir PDF mediana 214,5 ms | **REPROVOU** (item aberto de sempre) |

---

## §16 — O que este ciclo tocou

**Produto (tronco), `src/chess_diagram_ocr/`:**
`ui/folha_de_estilo.py` (`QUEM_PINTA`, `PAPEL_PINTADO` derivada),
`ui/strings.py` (`SEM_MOTOR_STATUS`, `SEM_MOTOR_DICA`, crases), `ui/sala_declarada.py`
(`COMANDOS_QUE_EXIGEM_MOTOR`, `motor_de_analise`, `encerrar_o_motor`), `ui/galeria_declarada.py`
(`LINK_CHOICES`), `ui/estado_do_rodape.py` (`contagem_das_caixas`), `ui/page_results.py`
(`colocacoes_conferidas`), `qt/janela.py`, `qt/menu.py` (`impedir`), `qt/tema.py` (docstring),
`qt/dialogos.py`, `qt/painel_de_estudo.py`, `qt/painel_da_galeria.py`, `qt/painel_de_resultado.py`,
`qt/painel_de_revisao.py`, `qt/painel_de_texto.py`, `qt/painel_do_dataset.py`, `qt/painel_do_pdf.py`,
`qt/exportador.py`. **`ui/tipografia.py` não foi tocado** — `PAPEL_POR_CLASSE` é lido por
`folha_de_estilo`, e é justamente por não ter mudado que a derivação do §2.1 vale.

**Arnês (suíte), `src/caissa/ui/audit/`:**
`texto_pintado.py`, `comandos.py` (novo), `bloqueio.py`, `contraste.py`, `capture.py`.

**Testes (suíte), `tests/unit/ui/`:**
`test_texto_pintado.py`, `test_comandos.py` (novo), `test_texto_desenhado.py` (novo).

**Testes (tronco), três arquivos, declarados no §14.1:**
`tests/test_qt_dialogos.py`, `tests/test_qt_painel_de_estudo.py`, `tests/test_qt_painel_de_revisao.py`.

**E a lista acima é conferível por `mtime`, que é como esta frente confere divulgação desde o ciclo
14.** `find <tronco>/src/chess_diagram_ocr <tronco>/tests -name "*.py" -newermt "2026-09-10 00:40"`
devolve **21 arquivos**: os **18** de produto e os **3** de teste nomeados acima, e nenhum outro.

**Evidência:** `benchmarks/reports/ui/c16/` — 7 instrumentos; `capturas/` com **98** PNG (84 do par
ANTES/DEPOIS, 12 recortes de quem-pinta, 2 do menu do motor); `retratos/` com **13**; `gates/` com
**75** JSON, dos quais **22** são as passadas do portão de bloqueio que **completaram** — as que
morreram não escrevem nada, que é precisamente o defeito do §7.

---

## §17 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<suite>\src;<tronco>\src
set C16=benchmarks\reports\ui\c16
set PY=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe
set PDF=..\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf

:: O MECANISMO (item 2): quem pinta cada seletor, no pixel
%PY% %C16%\c16_quem_pinta.py
     :: QGroupBox::title -> o WIDGET;  os outros tres -> a FOLHA

:: O MENU DO MOTOR (item 1), nas duas condicoes
%PY% %C16%\c16_o_menu_do_motor.py
%PY% %C16%\c16_o_menu_do_motor.py --com-motor

:: O PORTAO NOVO e as duas provas de vida (item 1)
%PY% -m caissa.ui.audit.comandos --pdf "%PDF%" --saida %C16%\gates\comandos
     :: 379 | 370 | 0 | 0 | 0  PASSOU
%PY% -m caissa.ui.audit.comandos --pdf "%PDF%" --com-motor --saida %C16%\gates\comandos_com_motor
     :: 379 | 379 | 0 | 0 | 0  PASSOU
%PY% -m caissa.ui.audit.comandos --pdf "%PDF%" --desligar salvar --saida %C16%\gates\comandos_desligado
     :: soltos 3  REPROVOU
%PY% -m caissa.ui.audit.comandos --pdf "%PDF%" ^
     --religar analisar_posicao,analise_continua,variante_do_motor --saida %C16%\gates\comandos_religado
     :: prometem 9  REPROVOU

:: O PORTAO DO TEXTO PINTADO e a prova de vida (itens 2, 3, 4, 10, 11)
%PY% -m caissa.ui.audit.texto_pintado --pdf "%PDF%" --saida %C16%\gates\texto_pintado
     :: 540 | 24 cegos | 0 | 0 | 0 ignorados  PASSOU
%PY% -m caissa.ui.audit.texto_pintado --pdf "%PDF%" --faixa-de-antes --saida %C16%\gates\prova_de_vida
     :: 108 cobertos; 3 8 8 8 5 5 na compacta  REPROVOU

:: AS TELAS (itens 5, 6, 7, 8, 11, 12)
%PY% %C16%\c16_retratar_os_dialogos.py    :: 13 retratos, 0 sha256 repetido, 0 legendas repetidas
%PY% %C16%\c16_rotulos_de_campo.py <pele> :: 117 medidos, 0 minusculas, 0 crases, 0 reticencias
%PY% %C16%\c16_recorte_do_titulo.py <pele> <densidade> [--antes]   :: tinta 159 px nos DOIS
%PY% %C16%\c16_largura_do_motivo.py       :: com filtro: Status ESCONDIDA, Motivo +80 px, 0 elididos
%PY% %C16%\c16_heranca_contra_o_qt.py     :: 38 conferidas, 1 divergencia declarada

:: O PORTAO DE BLOQUEIO, 8 vezes, pela receita publicada (item 9)
for /L %i in (1,1,8) do %PY% -m caissa.ui.audit.bloqueio --pdf "%PDF%" --execucoes 1 ^
    --sem-perfil --saida %C16%\gates
     :: 8 de 8 completam; abrir PDF mediana 214,5 ms; REPROVOU, 7 operacoes

:: OS PORTOES DE SEMPRE
%PY% -m caissa.ui.audit.teclado   --pdf "%PDF%" --saida %C16%\gates\teclado     :: PASSOU
%PY% -m caissa.ui.audit.contraste --saida %C16%\gates\contraste                 :: 300/220/0 PASSOU

:: AS SUITES
.venv\Scripts\python.exe -m pytest tests\unit\ui -q -p no:cacheprovider          :: 271 passed
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py
<tronco>\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly -p no:cacheprovider
```
