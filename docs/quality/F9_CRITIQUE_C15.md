# F9 — Interface, crítica do ciclo 15

```
VEREDITO: APROVADO
CICLO: 15
FRENTE: F9 (Interface)
```

**O bloqueante do ciclo 13 está morto, e eu o matei de novo com os meus próprios instrumentos, sem
alterar uma linha deles.** `c13_titulo_de_grupo_coberto.py` nas **seis** combinações de pele ×
densidade, a 1920 px:

```
  === classica|foco|fita / compacta / 1920 px
      QGroupBox com titulo, visiveis: 6      titulos com a tinta COBERTA por um filho: 0
      [Estudo   ] Lances                margem=26px  titulo=21px  ok
      [Estudo   ] Comentário do lance   margem=26px  titulo=21px  ok
      [Dataset  ] Filtros               margem=26px  titulo=21px  ok
  === classica|foco|fita / confortavel / 1920 px
      titulos com a tinta COBERTA por um filho: 0     margem=28px  titulo=21px
```

A margem era **9 px**; é **26/28 px**. `c13_titulo_de_grupo_cortado.py` fecha a aritmética nos seis
grupos e nas quatro combinações que rodei: `faixa=21 pintado=21 invade=0`. E o portão novo,
rodado por mim do zero, devolve `24 passadas | 564 textos | 24 cegos | 0 cobertos | 0 cortados —
PASSOU`, **número por número igual ao publicado**. A prova de vida também: `--faixa-de-antes`
devolve **108 cobertos**, 6 de 6 na compacta e 3 de 6 na confortável, com os **meus** seis nomes e
os **meus** seis números — `Reconhecido…` 3, `Lances` 8, `Comentário do lance` 8, `Filtros` 8,
`Cabeçalhos do PGN` 5, `Este diagrama` 5.

E olhei. O par `c14_ANTES/DEPOIS_fita_compacta_Estudo_Comentário_do_lance.png` mostra a diferença;
melhor ainda, a captura **não encenada** do ciclo 12 — `c12_fita_1920x1080_estudo.png`, que ninguém
produziu para provar nada — mostra `Lances` com **os 60 % de baixo de cada letra apagados**, e a
captura de hoje mostra o rótulo inteiro. Rodei os onze itens não bloqueantes um a um; **oito estão
fechados com o número pedido, dois estão fechados com um efeito colateral que eu meço abaixo, e o
décimo segundo continua aberto e declarado.** Nenhum teste do tronco foi alterado: **zero** arquivos
em `ChessVisionOFF_Puro/tests/` têm `mtime` posterior a 2026‑09‑09 22:00, contra **doze** arquivos
de produto. A suíte do tronco devolve `3 failed, 4 486 passed, 2 skipped, 4 536 subtests` — os
mesmos três de sempre, nenhum desta frente.

**Aprovo.** E aprovo dizendo, com número, as sete coisas que achei e que ninguém tinha olhado —
inclusive o **décimo segundo instrumento cego**, que é de uma espécie nova e que eu meço no §4.
Nenhuma delas apaga tinta na tela, nenhuma perde trabalho, nenhuma trava a janela. Elas são a
ordem de serviço do §8, não uma reprovação.

---

## Nota de procedimento

Conferi o destino de todo script antes de rodá‑lo. **Nada que eu tenha escrito saiu de
`docs/quality/F9_CRITIQUE_C15.md` e de `benchmarks/reports/critique/ui/c15/`.** Nenhum arquivo de
produto, de teste ou de portão foi tocado — conferido por `mtime`: **zero** `.py` em
`ChessVisionOFF_Puro/src` ou `/tests` tem `mtime` posterior ao início desta sessão. As quatro
sabotagens do §4 trocam a folha **em memória** (`QApplication.setStyleSheet`), que é o mesmo caminho
que `--faixa-de-antes` usa, e não escrevem nem apagam arquivo nenhum em `qt/` ou `ui/`.

**Uma exceção, e ela não é minha: a suíte escreve fora da pasta de quem a roda.** Rodar
`pytest tests` — que a carta §6 me obriga a fazer — gravou
`benchmarks/reports/parity_fp16.json` às 00:31:17, no meio da minha execução.
`tests/integration/test_gpu_parity.py:309` monta o destino como
`REPO_ROOT / "benchmarks" / "reports" / "parity_fp16.json"`, sem pasta por execução e sem opção.
Não consigo provar qual era o conteúdo anterior; o que está lá agora é o resultado determinístico
(`200 boards, 12 800 squares, 0 mismatches` nos quatro contadores). É a mesma armadilha que o item
16 do ciclo 11 fechou nos portões (*"`--saida` é obrigatório: este portão não escolhe pasta por
você"*), viva dentro de um teste. Item 14 do §8.

* `PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider` em tudo; `--saida` explícito em todo portão;
  `QT_QPA_FONTDIR=C:\Windows\Fonts` com barra simples (a armadilha que pegou o crítico do ciclo 13).
* Os instrumentos que reusei — `c13_titulo_de_grupo_coberto.py`, `c13_titulo_de_grupo_cortado.py`,
  `c13_fonte_pintada.py`, `c11_dialogos_prova.py` — **não gravam nada**, conferido por busca de
  `write_text`/`json.dump`/`.save(`/`mkdir` antes de cada um.
* **Dois erros meus, registrados.** (1) Medi a tinta do título com uma janela de linhas que incluía
  o filete do quadro e obtive "340 px" — número sem sentido; corrigido, a medida é 34 px. (2) Acusei
  o portão de bloqueio de morrer por causa do `PYTHONPATH`; a causa é outra e está no §5.7 —
  ele morre em **5 de 8** invocações idênticas, com e sem o tronco no caminho.
* **Um número do relatório eu não reproduzi**, e ele não muda nada: na passada `--faixa-de-antes` o
  relatório publica `cegos 564` e eu meço `cegos 504`. `medidos`, `cobertos` (108), `cortados` (0) e
  o veredito batem. A diferença são 60 medições de cabeçalho de diálogo que ficam ou não "cegas"
  conforme o diálogo tenha sido mostrado antes ou depois de a folha ser reaplicada — ordem, não
  medida. Fica registrado porque é um número publicado que não reproduz.

Instrumentos meus, todos em `benchmarks/reports/critique/ui/c15/`:

| instrumento | o que responde |
|---|---|
| `c15_quem_pinta_o_titulo.py` | **o §4**: com que fonte o Qt pinta `QGroupBox::title`, em 4 combinações |
| `c15_quem_pinta_o_cabecalho.py` | a mesma pergunta para `QHeaderView::section` — e a resposta é a **oposta** |
| `c15_a_regua_contra_a_tela.py` | a régua nova e o pixel desenhado, lado a lado, na janela do produto |
| `c15_sabotar_o_texto_pintado.py` | 4 sabotagens na folha em memória: `font:` curto, vírgula, descendência, id |
| `c15_o_que_a_faixa_de_antes_muda.py` | o que `--faixa-de-antes` muda além da faixa |
| `c15_olhar_as_telas.py` | botões repetidos, a barra do treino, o menu do motor, os `QGroupBox` por aba |
| `c15_retratar.py` | os retratos que o ciclo 14 publicou duplicados ou não publicou |
| `c15_ampliar.py` / `c15_recortar.py` / `c15_medir_tinta.py` / `c15_medir_faixa.py` | as lupas |

---

## §1 — Comparação às cegas (substituição do §2.1)

Mantida a substituição das rodadas anteriores: os **nove critérios de desenho**, cada um com a
pergunta *"isto sobrevive ao lado do Affinity Publisher, do Chessbase 17 e do Scrivener?"*

### 1. Hierarquia visual — **SOBREVIVE. É a conquista do ciclo.**

O degrau mais alto da escala voltou a existir na tela. Na Compacta, que é a densidade que a pele
`fita` traz por padrão, os seis títulos de grupo são pintados **inteiros**, 12 pt negrito, acima do
quadro, com 26 px de faixa para 21 px de tinta. O par ampliado a 4× não deixa dúvida: no ANTES o
filete do quadro atravessa as letras e o `ç` de `Comentário` perde a haste; no DEPOIS é um rótulo
de painel. Medido: a tinta do título passou de **8 linhas** de altura para **12**, e de 200 px
escuros para 655.

### 2. Ritmo espacial — **SOBREVIVE**

`c12_fita.py` continua devolvendo `topos [0, 49] alturas [43]` na compacta e `[0] / [81]` no pleno.
O preço da faixa nova foi medido e é honesto: os três painéis que têm grupo encolheram o vazio
(Dataset 1 905,3 → 1 896,8 kpx). Nada foi empurrado para fora em nenhuma das quatro larguras —
conferi a Galeria e o Resultado a 1280×800 na fita/compacta, que é o caso mais apertado, e os dois
grupos fecham dentro da janela.

### 3. Alinhamento — **SOBREVIVE, e o cabeçalho fechou**

`GLIFOS DE TEXTO em TODOS os arranjos: 0`. E o `Resultad·` do ciclo 13 acabou: o **meu**
`c13_fonte_pintada.py`, sem uma linha alterada, devolve `ELIDIDOS pela fonte que a tela pinta: 0`
de 24 nas três peles a 1366 px — eram 2, 2 e 1. Os dois campos de `JanelaDeBusca` dividem uma borda
esquerda (74 px) e uma direita (394 px) no modo com substituição, e no modo simples a calha some e
o campo `Achar` vai até 506 px — que é o comportamento certo e que **nenhuma fotografia publicada
mostra** (§6.3).

### 4. Densidade × vazio — **NÃO SOBREVIVE, e continua exatamente onde estava**

5 de 6 painéis acima de 200 kpx a 3840 px, pior 3 104,2 (Revisão). Aberto e declarado desde o ciclo
5. Não mudou e não piorou.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

`300 pares / 220 sob portão / 0 reprovados`, menor folga **3,27:1** e **3,03:1**. Reproduzido por
mim, número a número, nas duas polaridades × duas densidades.

### 6. Tipografia da interface — **SOBREVIVE na tela; a explicação de por que ela sobrevive está errada**

O que se vê é certo: título de grupo 12 pt negrito, cabeçalho de coluna 12 pt negrito, corpo 9 pt,
apoio 8 pt, e os quatro degraus se leem. O que o produto **escreveu** sobre quem desenha o título é
que não se sustenta ao pixel, e é o §4 desta crítica: o Qt **não honra**
`QGroupBox::title { font-size }`. Quem pinta aquele título é `ui/tipografia.PAPEL_POR_CLASSE`, uma
tabela em outro módulo, e não `ui/folha_de_estilo.PAPEL_PINTADO`, que é a que reserva a faixa. Hoje
as duas dizem `TITULO` e por isso a tela está certa. Não bloqueia — **nada está cortado** —, mas a
frase "as duas pontas andam juntas **por construção**" é falsa, e o instrumento que deveria pegar a
deriva olha a ponta que o Qt ignora.

### 7. Controles — **SOBREVIVE**

`216 / 216 / 240 / 240 / 360 / 360` focáveis nas abas e **50 em 13 telas de diálogo** por arranjo,
com `0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab` nos seis. Rodado por mim. E os botões
padrão voltaram para o catálogo do Qt: **16 concordam, 1 divergência declarada (`Abort`), 0 não
declaradas**, medido contra o `qtbase_pt_BR.qm` que esta árvore traz.

### 8. Estados vazios — **SOBREVIVE, com um defeito de desenho novo**

`0 de 5 → 5 de 5`: as cinco telas de diálogo que abrem vazias usam `qt/vazio.EstadoVazio`, com
título, frase e botão. `_JanelaDeColecao` parou de se contradizer. Mas o remédio trouxe **dois
botões desenhados com a mesma legenda** em duas dessas cinco telas — `Fechar` e `Fechar` em
`_JanelaDePartidas`, `Procurar por nome` e `Procurar por nome` em `DialogoDePartidas` —, e num deles
o "botão que resolve" só fecha a janela, que é o que o rodapé já fazia. É o §5.1.

### 9. A pele escura — **SOBREVIVE**

O cromo escuro está coerente: superfície `#1a1d21`, campo com foco em azul, documento (a folha do
livro, o tabuleiro) fora da pele, botão morto legível. Os títulos de grupo estão certos nas três
peles e nas duas polaridades. Não é claro invertido.

---

## §2 — O bloqueante do ciclo 13, remedido pelas duas metades

### 2.1 O produto: a faixa e a tinta são o mesmo número

Rodei os **meus dois** instrumentos, sem alterar uma linha:

```
  c13_titulo_de_grupo_coberto.py <pele> <densidade> 1920      (6 arranjos)
      titulos com a tinta COBERTA por um filho: 0  de 6, nos SEIS
      margem: 26px (compacta)  28px (confortavel)     titulo: 21px      (era margem=9px)

  c13_titulo_de_grupo_cortado.py <pele> 1920   com CVOFF_DENSITY=compacta|confortavel
      titulos cuja tinta pintada INVADE a borda do proprio quadro: 0
      faixa=21  pintado=21  invade=0    nos seis grupos, nas quatro combinacoes rodadas
```

### 2.2 O instrumento: o portão novo, rodado por mim

```
  24 passadas (3 peles x 2 densidades x 4 larguras)
  medidos 564 | cegos (folha != widget) 24 | cobertos 0 | cortados 0
  seletores de fonte que a regua NAO analisou: 0 []
  Veredito: PASSOU
```

Idêntico ao publicado, campo por campo, inclusive as 24 linhas por arranjo.

### 2.3 A prova de vida: eu a rodei, e ela reproduz os **meus** números

```
  --faixa-de-antes:  medidos 564 | cobertos 108 | cortados 0   REPROVOU
    <pele>/compacta  <larg>  aba Resultado  Reconhecido (clique e arra  COBERTO 3px (TabuleiroEditavel)
    <pele>/compacta  <larg>  aba Estudo     Lances                      COBERTO 8px (QTextBrowser)
    <pele>/compacta  <larg>  aba Estudo     Comentário do lance         COBERTO 8px (QTextEdit)
    <pele>/compacta  <larg>  aba Dataset    Filtros                     COBERTO 8px (QLabel, QLineEdit)
    <pele>/compacta  <larg>  aba Galeria    Cabeçalhos do PGN           COBERTO 5px (QLabel, QLineEdit)
    <pele>/compacta  <larg>  aba Galeria    Este diagrama               COBERTO 5px (BarraFluida)
    <pele>/confortavel      3 de 6, 2 px
```

**Não é encenação.** Li o caminho: `--faixa-de-antes` chama
`folha_de_estilo.folha_de_estilo(..., altura_do_titulo=espaco.linha())` e reaplica a folha; nenhum
byte do produto muda, e o `margin-top` volta a 4/6 px. Os seis nomes e os seis números são os do §3
do ciclo 13, à unidade.

### 2.4 **Mas as 42 fotografias `ANTES` não mostram a tela que o produto tinha** — e o defeito real era pior

Aqui eu discordo do relatório, e a medida é minha. O relatório publica os 84 PNG como *"mesma pele,
mesma densidade, mesma largura, mesmo recorte, **só a faixa muda**"*. Reaplicar a folha faz o Qt
despolir e repolir toda a janela, e isso **desfaz a varredura de `qt/escala.aplicar_escala`**:

```
  DEPOIS (produto de hoje)      grupo.font() = Segoe UI 12.0pt  negrito=True   margin-top = 21 px
  ANTES  (--faixa-de-antes)     grupo.font() = Segoe UI  9.0pt  negrito=False  margin-top =  4 px
```

Duas coisas mudam, não uma. E a consequência é visível: no PNG `ANTES` o título
`Comentário do lance` mede **115 px** de tinta; no `DEPOIS`, **157 px**. Na captura **não encenada**
do ciclo 12 — `benchmarks/reports/ui/c12/capturas/c12_fita_1920x1080_estudo.png` — o mesmo título
mede **157 px**, cortado ao meio.

**A fotografia do ANTES é mais branda do que a tela que o produto entregava.** O número do portão
não é afetado (`coberto` sai da fonte da folha, 21 px nos dois casos), e por isso a prova de vida
continua valendo; a **evidência fotográfica**, não. Isto é a favor do construtor, não contra: o
defeito que ele fechou era **maior** do que o par que ele publicou.

---

## §3 — Defeitos bloqueantes

**Nenhum.**

Não é uma frase de cortesia; é o resultado de procurar. Percorri, a olho e ampliadas, as 84
capturas do par ANTES/DEPOIS, os 8 retratos de diálogo, as 72 capturas do arnês nas três peles e
nas quatro larguras, e fotografei por conta própria as três telas de diálogo que faltavam. Rodei
os cinco portões e os quatro instrumentos meus dos ciclos 11 e 13. Sabotei o portão novo por quatro
caminhos. Não achei **tinta apagada, texto cortado onde caberia, par de contraste abaixo do piso,
foco invisível, travamento, perda de trabalho nem estado vazio sem orientação** em nenhuma das seis
combinações, em nenhuma das quatro larguras, em nenhuma das duas polaridades.

O que achei está nos §4, §5 e §6, e nada disso apaga uma letra na tela.

---

## §4 — O décimo segundo instrumento cego: a régua pergunta à folha num subcontrole em que a folha não tem voto

Os onze anteriores erraram a **regra** (ciclos 1–8), a **pele** (9), a **janela** (11), o **arquivo**
(12) e a **fonte** (13). Este erra o **mecanismo**.

### 4.1 O Qt não honra `QGroupBox::title { font-size }`

`c15_quem_pinta_o_titulo.py`, num `QGroupBox` isolado, com `Comentário do lance` (referências:
9 pt = 109 px, 12 pt negrito = 159 px, 20 pt negrito = 267 px):

| fonte do **widget** | a **folha** diz | tinta desenhada | quem ganhou |
|---|---|---|---|
| 9 pt | `font-size: 12pt; bold` | **109 px** | o widget |
| 9 pt | `font-size: 20pt; bold` | **109 px** | o widget |
| 12 pt negrito | (nada) | **157 px** | o widget |
| 20 pt negrito | `font-size: 12pt; bold` | **265 px** | o widget |

**A folha nunca ganha.** Quem pinta o título do grupo é `QWidget.font()`, que é o que
`ui/tipografia.PAPEL_POR_CLASSE["QGroupBox"] = TITULO` põe lá por `qt/escala.aplicar_escala`.

E o mesmo experimento no outro seletor da tabela (`c15_quem_pinta_o_cabecalho.py`, `Resultado`:
9 pt = 52 px, 12 pt negrito = 76 px, 20 pt negrito = 128 px) dá a resposta **oposta**:

| fonte do widget | a folha diz | tinta desenhada | quem ganhou |
|---|---|---|---|
| 9 pt | `12pt bold` na `::section` | **74 px** | a folha |
| 9 pt | `20pt bold` na `::section` | **125 px** | a folha |
| 12 pt negrito | regra na `::section` **sem** fonte | **50 px** | nem um nem outro: a fonte da aplicação |
| 12 pt negrito | **nenhuma folha** | **74 px** | o widget |

Dois dos três seletores de `PAPEL_PINTADO` obedecem a regras **contrárias**, e a tabela declara uma
regra só para os dois: *"seletor da folha → o degrau da escala com que **ela** o pinta"*.

### 4.2 O que isso faz com o portão novo

`medir_titulos_de_grupo` calcula `pintada = fonte_da_folha(regras, ..., base=widget.font())` — a
folha por cima do widget. Na janela do produto (`c15_a_regua_contra_a_tela.py`, título `Lances`;
referências 9 pt = 36 px, 12 pt negrito = 51 px, 20 pt negrito = 85 px):

```
  fonte do widget 9pt   folha 12pt   a REGUA diz  51 px      a TELA desenhou  34 px
  fonte do widget 9pt   folha 20pt   a REGUA diz  85 px      a TELA desenhou  34 px
  fonte do widget 12pt  folha 20pt   a REGUA diz  85 px      a TELA desenhou  49 px
```

A régua chamada *"a régua lê a fonte da folha de estilo, e não `QWidget.font()`"* lê, neste
subcontrole, exatamente a fonte que o Qt joga fora. Hoje ela acerta porque as duas tabelas
concordam — `PAPEL_PINTADO["QGroupBox::title"]` e `PAPEL_POR_CLASSE["QGroupBox"]` dizem as duas
`TITULO` —, e por isso **o produto está certo e eu aprovo**. Mas o mecanismo que o ciclo 14
descreve como *"a deriva deixa de ser possível em vez de ser reconsertada no ciclo seguinte"* é
uma coincidência entre duas tabelas em dois módulos, não uma construção. Basta alguém acreditar no
que `_escala_tipografica` tem escrito — *"o QSS de subcontrole é o que o Qt honra ao **pintar** o
título"* — e tirar `QGroupBox` de `PAPEL_POR_CLASSE` para o título cair a 9 pt numa faixa de 21 px,
com o portão devolvendo `0 cobertos` e `PASSOU`.

### 4.3 As quatro sabotagens: uma delas passa calada, e a defesa escrita contra ela não existe

`c15_sabotar_o_texto_pintado.py`, trocando **em memória** a linha `QGroupBox::title` da folha:

| sabotagem | a régua vê a regra? | `seletores que a regua NAO analisou` | veredito |
|---|---|---|---|
| `font: bold 20pt "Segoe UI"` (forma curta) | **não** | **0** | **SILÊNCIO** |
| `QGroupBox::title, QHeaderView::section { font-size: 20pt }` | não | **1** | acusa |
| `QWidget QGroupBox::title { font-size: 20pt }` | não | **1** | acusa |
| `QGroupBox#painel::title { font-size: 20pt }` | não | **1** | acusa |

Três de quatro fazem o número publicado subir — a válvula de escape funciona, e isso é mérito. A
quarta não: `font` (a forma curta) está fora de `PROPRIEDADES_DE_FONTE`, e como `_declaracoes_de_fonte`
filtra pela **mesma** tupla, a regra escapa das duas peneiras ao mesmo tempo. O módulo diz por
escrito que isso está coberto:

> *"Se ela aparecer um dia, `regras_de_fonte` não a vê e o teste
> `test_a_regua_le_toda_regra_de_fonte_da_folha` falha."*

**Esse teste não existe.** O que existe é `test_acha_toda_regra_de_fonte_da_folha`, e ele afirma
`achadas >= {as quatro conhecidas}` — um **superconjunto**: uma regra que a régua perca não o
derruba. E `test_nenhum_seletor_de_fonte_escapa_da_analise` afirma `== ()`, que a forma curta
também satisfaz. A defesa declarada contra a estreiteza da régua é a única das quatro que não
funciona, e o nome que ela cita está errado.

### 4.4 A população: três classes de widget, e a folha tem quatro papéis

`medir_a_tela` é `medir_titulos_de_grupo + medir_cabecalhos + medir_abas`. Não há `medir_rotulos`.
O relatório afirma, na tabela do §1.5, que `QLabel[apoio="true"]` foi *"medido junto, 0 cortados"*
— **ele não é medido**: nenhum `QLabel` entra na conta em nenhuma das 24 passadas. (Não há defeito
atrás disso: 8 pt é menor que o corpo, e o que sobra é ar. Mas o número publicado cobre uma classe
que a régua não visita.)

E a passada é sempre a **janela recém‑aberta**: um PDF, nenhum PGN carregado, nenhum filtro digitado,
nenhum motor. `qt/painel_de_estudo.py:404` constrói um **sétimo** `QGroupBox` — `Motor (<binário>)`,
com o **nome de um arquivo** dentro do título, que é a única largura de título variável do produto —
e as 24 passadas dizem `6` em todas. Hoje ele não existe por outro motivo (§6.1), mas a frase
"6 de 6" é sobre a população que o arnês alcança e é afirmada como se fosse o produto. É o item 6 do
§7 do ciclo 13 — *"o portão para de afirmar mais largura do que tem"* —, que foi fechado para os
diálogos e nasceu de novo no portão novo.

---

## §5 — Defeitos não bloqueantes

### 5.1 Duas telas desenham **dois botões com a mesma legenda**, e a distinção foi dada só a quem não vê

Medido no widget vivo (`c15_olhar_as_telas.py`) e fotografado por mim
(`c15/retratos/c15__JanelaDePartidas__Estudo___Partidas_.png`):

```
  [_JanelaDePartidas (Estudo | Partidas)]  560x400   botoes desenhados = ['Fechar', 'Fechar']
  [DialogoDePartidas (Galeria | Partidas)] 900x420   botoes desenhados =
        ['Procurar por nome', 'Aplicar', 'Procurar por nome', 'Aplicar aos vizinhos...', 'Fechar']
```

No código, os dois são o mesmo par de linhas:

```python
qt/painel_de_estudo.py:1988   EstadoVazio(..., rotulo_do_botao="Fechar",
                                          nome_acessivel="Fechar e escolher outra posição",
                                          acao=self.reject)
qt/dialogos.py:466            EstadoVazio(..., rotulo_do_botao="Procurar por nome",
                                          nome_acessivel="Procurar partidas por nome na base",
                                          acao=self.procurar_por_nome)
qt/dialogos.py:479            self.btn_por_nome = QPushButton("Procurar por nome", self)   # mesma acao
```

Duas coisas erradas, e a segunda é a que dói:

1. **A distinção foi para o `accessibleName` e não para a legenda.** O portão de teclado imprime
   `Fechar e escolher outra posição` e `Fechar`, e por isso `nomes_repetidos` sai vazio e ele passa.
   Quem **ouve** recebe dois nomes; quem **vê** recebe `Fechar` duas vezes a 160 px de distância
   numa janela de 560×400. É literalmente a inversão que esta frente já nomeou e consertou uma vez
   — F9‑C7 §1.8, no par `outro` da Galeria: *"era o contrário: quem ouve recebia a distinção e quem
   vê, não"*.
2. **Em `_JanelaDePartidas` o "botão que resolve" não resolve nada**: ele chama `self.reject`, que é
   o que o `Fechar` do rodapé já faz. O contrato que o próprio relatório escreve para o estado vazio
   é *"o título diz o que falta, a frase diz por que está vazio e o **botão faz**"*. Este não faz;
   ele repete a saída.

*Alvo: 0 pares de botões com legenda desenhada igual e ação igual visíveis ao mesmo tempo — hoje 2
telas de 5.*

### 5.2 Três comandos do menu **Estudo** nunca funcionam, e a mensagem manda fazer o que não resolve

Ver §6.1. `Analisar a posição com o motor`, `Análise contínua enquanto se navega` e
`Pôr a linha do motor como variante` estão no menu, **habilitados e visíveis**, e os três devolvem
`"Sem motor UCI instalado: ponha o Stockfish em engines/ e reabra."` — em qualquer máquina, com ou
sem Stockfish, porque `qt/janela.py:381` constrói `PainelDeEstudo` **sem** `analyzer` e nada em
`src/` chama `engine.find_engine`. *É o mais sério dos itens não bloqueantes.*

### 5.3 `outro`, em minúscula, na janela principal — o item 10 fechou só nos diálogos

`c14_miudezas_dos_dialogos.py` percorre `teclado.RECEITAS`, isto é, **as treze telas de diálogo**.
A janela principal ficou fora, e ela tem um rótulo de campo em minúscula, numa coluna de oito
capitalizados, visível na captura do próprio construtor
(`c14_escuro_1920x1080_galeria.png`, aba Galeria, grupo `Cabeçalhos do PGN`):

```
  White · Black · Event · Site · Date · Round · Result · Annotator · outro
                                                                    ^^^^^  qt/painel_da_galeria.py:396
```

*Alvo: os rótulos de campo da janela entram na mesma conta dos diálogos — hoje a conta é de 4 pares
em 13 telas e a janela não é medida.*

### 5.4 `brancas`/`pretas` numa aba e `Brancas`/`Pretas` na outra, com o catálogo dizendo qual é a certa

```
  ui/strings.py:68          SIDE_LABELS = {"w": "Brancas", "b": "Pretas"}      <- o catalogo
  qt/painel_de_resultado.py:370   ("w", "Brancas"), ("b", "Pretas")            <- cravado, concorda
  qt/painel_da_galeria.py:511     ("brancas", "w"), ("pretas", "b")            <- cravado, diverge
```

Os mesmos dois rádios, sob o mesmo rótulo `Lado a jogar`, em duas abas: `Brancas`/`Pretas` no
Resultado e `brancas`/`pretas` na Galeria. E `ui/formato.py:12` escreve a regra que os dois violam:
*"`ui/strings.py` existe desde a S‑04 justamente para 'brancas' ter um nome só"*.
*Alvo: os dois pares saem de `SIDE_LABELS`.*

### 5.5 Crase de máquina de escrever: `` `.pgn` `` desenhado na tela, e `...` contra `…` em 13 lugares

`ui/strings.py:210`, escrita **neste ciclo**:

> `"O arquivo abriu, e não há partida legível dentro dele. Escolha outro `.pgn`, ou abra este num
> editor para ver o que ele traz."`

As duas crases são desenhadas: aparecem no retrato
`c14_dialogo__JanelaDeColecao__Estudo___Abrir_P.png`, ampliado. É marcação de Markdown vazando
para texto de interface — a mesma família das aspas retas que esta frente já caçou (`strings.py:256`:
*"`\"` reto — aspas de máquina de escrever — estava em 12 das 36 capturas"*).

E, na mesma varredura, **13 linhas de texto desenhado usam três pontos ASCII** enquanto o caractere
`…` aparece em 19 literais de `qt/` e `ui/strings.py`:
`Aplicar aos vizinhos...` (desenhado no retrato de `DialogoDePartidas`), `Preparando treino...`,
`Treinando modelo...`, `varrendo...`, `cancelando...`, `Varrendo o livro...`,
`Renderizando página N...`, `Lendo a folha N...`, `Exportando para X...`,
`Iniciando exportação do PDF para PGN...`, `pensando...`. O menu que abre a mesma janela escreve
`Colar posição ou partida…`, com o caractere certo.
*Alvo: 0 crases e 0 reticências de três pontos em texto desenhado.*

### 5.6 A coluna `Status` gasta, com 27 repetições da mesma palavra, os pixels que faltam a `Motivo`

Na Revisão a 1280 px, com `Só pendentes` marcado, a coluna `Status` desenha **`pendente` nas 27
linhas** e ocupa ~70 px, enquanto `Motivo` — a coluna que diz o que conferir — sai elidida em
**25 de 27**. O item de `Motivo` está aberto desde o ciclo 4 e continua aberto com os números de
sempre (17 / 24 / 25 de 27 a 1920 / 1366 / 1280); o que é novo é que há 70 px de redundância ao
lado dele, e que a redundância é consequência do filtro que a própria aba impõe.
*Alvo: a largura vai para onde há informação.*

### 5.7 O portão de bloqueio morre com violação de acesso em **5 de 8** invocações idênticas

```
  8 invocacoes de `-m caissa.ui.audit.bloqueio --pdf ... --execucoes 1 --sem-perfil --saida ...`
     5 morreram: Segmentation fault / 0xC0000005, sem imprimir um caractere
     3 completaram: abrir PDF = 222 / 221 / 232 ms   -> mediana 222 ms   Veredito REPROVOU, 7 ops
  com o `PYTHONPATH=<suite>\src;<tronco>\src` que o §8 do ciclo 13 e o §6 do ciclo 14 publicam
  como a receita: 4 de 4 morreram.
```

O veredito reproduz (REPROVOU, 7 operações, mesma ordem de grandeza do 221,6 publicado) e o item
segue aberto e declarado, como nos quatro ciclos anteriores — **isso não mudou**. O que é novo é
que o portão que publica esse número morre calado na maioria das vezes, e morre sempre pela receita
escrita. Um portão que aborta sem imprimir nada é indistinguível, num CI, de um portão que passou.
*Alvo: 3 de 3 invocações completam, pela receita publicada.*

### 5.8 O item 12 do ciclo 13, aberto e conferido

Nenhum precisa fechar, e eu confirmo os números: `Motivo` ilegível (25 de 27 a 1280); **0 de 5**
cabeçalhos de fita desenhados na compacta; **6 de 24** botões de fita sem rótulo desenhado; tinta
dos ícones 17,6 %–41,4 %; **5 de 6** painéis acima de 200 kpx a 3840 (pior 3 104,2); marca da FEN só
à direita; a etiqueta local que segura `7bcb396`. E `DialogoDeTreino` continua sem botão nenhum
desenhado — a frase *"quem cancela é o rodapé"* está lá e é honesta, mas `JanelaDeEstatisticas`
ganhou `Fechar` e esta não.

---

## §6 — O que o ciclo 14 não admitiu

Julguei cada item declarado aberto e procurei o que não está em lista nenhuma.

### 6.1 O que ninguém olhou: a seção do motor não existe, e três comandos mentem

`docs/ROADMAP.md:901` marca **✅** o item *"Engine (Stockfish) opcional na aba de análise: avaliação
e melhor lance (S‑33)"*. Na janela Qt de hoje:

```
  PainelDeEstudo._analyzer = None           -> a 7a QGroupBox 'Motor (...)' nunca e' construida
  menu 'Estudo':
     'Analisar a posição com o motor'          habilitado=True  visivel=True
     'Análise contínua enquanto se navega'     habilitado=True  visivel=True
     'Pôr a linha do motor como variante'      habilitado=True  visivel=True
  os tres, invocados:
     -> "Sem motor UCI instalado: ponha o Stockfish em engines/ e reabra. · vez: brancas"
```

E a corrente inteira está solta:

```
  qt/janela.py:381        PainelDeEstudo(...)  -- sem `analyzer=`
  engine.find_engine      chamadores em src/: NENHUM  (so' tests/test_engine.py)
  EngineAnalyzer          construido em src/: NUNCA
  settings.EngineSettings.path   lido em src/: NUNCA
```

Instalar o Stockfish em `engines/` e reabrir **não muda nada**, porque nada procura o binário. A
mensagem não é uma degradação sinalizada: é uma receita que não funciona, entregue por três
comandos que o menu mostra habilitados. Carta §3.3, *"Mensagem de erro que não diz o que fazer a
seguir"* — esta diz, e está errada.

**Não bloqueia**, e digo por quê: a falha é sinalizada e não silenciosa, nada se perde, a aba não
promete a seção na própria superfície (ela é desenhada para não existir sem motor), e é a única
frente que catorze ciclos de crítica de **acabamento** nunca escopou. É item 1 do §8 e não veredito.
Se a mensagem fosse silenciosa, seria veredito.

### 6.2 O que foi declarado fechado e eu meço como fechado — com o efeito colateral nomeado

| item do §7 do ciclo 13 | medido por mim | julgamento |
|---|---|---|
| 2 · `Resultado` elidido | `c13_fonte_pintada` (meu): **0 de 24** nas três peles; eram 2/2/1 | **honestamente fechado**, e na raiz: `qt/tabela._largura_da_secao` continua perguntando `cabecalho.font()`, e quem mudou foi o `QEvent.Show` |
| 3 · `Ok → Confirmar` | catálogo do Qt: 16 concordam, 1 declarada, **0 não declaradas** | **honestamente fechado**, e a exceção `PALAVRAS_CURTAS_LEGITIMAS={"ok"}` é nomeada e testada |
| 4 · estados vazios | 5 de 5 usam o componente | **fechado, com o §5.1 em cima** |
| 5 · `JanelaDeAtalhos` | a linha do `Ctrl+Shift+S` termina em `(.cvtxt)`, sem barra horizontal | fechado |
| 6 · buracos do achador | rodado por mim no ciclo 13; hoje a frase publicada diz **"COMO CLASSE, em 13 telas"** e nomeia o que fica fora | **honestamente fechado** — e o portão novo (§4.4) recria o vício um andar acima |
| 7 · barra do treino | `range 0..8  valor 3  formato 'época %v de %m'` e a tinta **desenhada**: fotografei a barra e lê‑se `época 3 de 8` | fechado |
| 8 · E/S de disco | a lista saiu do relatório e entrou no portão | fechado |
| 9 · campos de `JanelaDeBusca` | esquerda `[74]`, direita `[394]` com substituição; sem ela a calha some e o campo vai a `506` | fechado |
| 10 · `filtro` → `Filtro` | fechado **nos diálogos**; a janela principal tem `outro` (§5.3) | **convenientemente fechado**: a população foi escolhida |
| 11 · `JanelaDeEstatisticas` | título desenhado + `Fechar` | fechado |

### 6.3 Os oito retratos de diálogo: dois são o mesmo arquivo, e um mostra um estado que o produto não tem

O relatório escreve: *"as oito telas de diálogo que este ciclo mexeu foram fotografadas e olhadas…
**Olhei os pares um a um**, ampliados, antes de escrever esta linha."* Conferi os oito:

```
  sha256 c14_dialogo_JanelaDeBusca__Achar_no_texto_.png  = 8c3d2e05201ad903...f188e146
  sha256 c14_dialogo_JanelaDeBusca__substituindo_.png    = 8c3d2e05201ad903...f188e146   IDENTICOS
```

E as duas telas **não** são iguais no widget: a simples tem 1 campo (borda direita 506 px) e nenhum
`Substituir todos`; a de substituição tem 2 campos (borda direita 394 px). O arquivo publicado é o
da substituição, publicado duas vezes — de modo que a tela cujo alinhamento o item 9 conserta
**nunca foi fotografada**. Fotografei‑a (`c15/retratos/c15_JanelaDeBusca__Achar_no_texto_.png`) e
ela está certa.

O terceiro: `c14_dialogo_DialogoDeTreino__Dataset___Treinar.png` mostra a barra **indeterminada** —
o bloco deslizante do Fusion, sem texto —, que é o estado em que a receita do arnês abre a janela e
que o produto nunca mostra, porque `ControladorDeTreino.iniciar` emite `avancou(0, epochs)` na
mesma thread, logo depois do `mostrar()`. A barra determinada com `época 3 de 8` desenhada existe:
eu a fotografei. O retrato publicado do item 7 é a fotografia do defeito que o item 7 fechou.

*Isto não muda nenhum veredito. Muda o peso da frase "fotografei e olhei", que é a prática que esta
frente adotou no ciclo 12 e que é a melhor coisa que aconteceu com ela.*

---

## §7 — O que eu confirmei com número

| o que o relatório afirma | o que eu medi |
|---|---|
| 0 de 6 títulos cobertos nas 24 combinações | **0 de 6 nos seis arranjos**, `c13_titulo_de_grupo_coberto.py`, sem alterar uma linha |
| `faixa=21 pintado=21 invade=0` | **idêntico**, nos seis grupos, quatro combinações |
| faixa 4/6 px → 21 px; primeiro filho em y=30/33/35 | **margem 9 px → 26/28 px**, título 21 px |
| portão novo: 24 passadas, 564, 24 cegos, 0, 0, **PASSOU** | **idêntico, campo por campo** |
| `--faixa-de-antes`: 108 cobertos, 6/6 e 3/6, `3·8·8·8·5·5` | **idêntico** — exceto `cegos` (504 aqui, 564 publicado) |
| `seletores de fonte que a regua NAO analisou: 0` | **0** — e três de quatro sabotagens o fazem subir (§4.3) |
| `c13_fonte_pintada`: 0 elididos de 24 nas 3 peles | **0 de 24 nas três**; eram 2 / 2 / 1 |
| teclado: 216/216/240/240/360/360 + 50 em 13 diálogos, 0·0·0·0 | **idêntico, à unidade, nos seis** |
| contraste: 300 / 220 / 0; 3,27 e 3,03 | **idêntico** |
| catálogo do Qt: 16 concordam, 1 declarada, 0 não declaradas | **idêntico**, contra o `.qm` |
| `c11_dialogos_prova`: antes=0 depois=0 | **antes=0, depois=0** |
| vazio a 4K: Revisão 3 104,2 · Texto 2 050,6 · Dataset 1 896,8 · Estudo 1 540,8 · Galeria 1 535,0 · Resultado 43,3 | **os seis à decimal**, `c5_vazios.py` (meu, do ciclo 5) sobre as capturas deste ciclo |
| `tests/unit/ui` **238 passed** (eram 198) | **238 passed em 2,54 s** |
| tronco: 3 failed / 4 486 passed / 2 skipped / 4 536 subtests | **idêntico, em 273,9 s**; as três são as pré‑existentes |
| nossa, sem `test_packaging.py`: 3 126 passed, 1 skipped, 0 failed | **3 126 passed, 1 skipped, 0 failed em 695,0 s**; o pulo é o de sempre (`test_fonts.py:333`, WOFF2 sem Brotli) |
| **nenhuma linha de teste do tronco alterada** | **0 arquivos em `tests/` com `mtime` > 2026‑09‑09 22:00**, contra 12 de produto; e `_largura_da_secao` continua medindo `cabecalho.font()` |
| bloqueio: REPROVOU, 7 ops, pior 221,6 ms | **REPROVOU, 7 ops**, abrir PDF 222/221/232 → **mediana 222 ms** — e 5 de 8 invocações abortaram (§5.7) |

**Quinze afirmações conferidas, quatorze reproduzidas à unidade e uma (`cegos` na prova de vida)
divergindo em 60 de 564, num número que não decide nada.** Não achei uma medição inflada, nem uma
arredondada a favor, nem uma publicada fora de ordem.

E vale dizer o que este ciclo fez de estruturalmente certo:

1. **Achou a raiz em vez de remendar o consumidor** — e provou isso do jeito mais caro possível: a
   primeira forma do conserto passava isolada e derrubava `tests/test_qt_tabela.py` em três pontos na
   suíte inteira. Ele moveu o conserto e **não tocou o teste**. Conferi: nenhum arquivo de teste do
   tronco tem `mtime` deste ciclo.
2. **Reverteu a própria regressão contra a tradução que o Qt já traz**, e transformou a decisão em
   tabela medida (`TRADUZIDOS_PELO_QT`) com as divergências obrigadas a ter motivo escrito.
3. **Fez o tamanho do ponto cego virar número publicado** (`cegos`, `seletores ignorados`). É a
   primeira régua desta frente que declara o que ela **não** enxerga. Que uma das quatro válvulas
   não feche (§4.3) não apaga que três fechem, e que a ideia esteja certa.
4. **Tirou a lista escrita à mão de dentro do próprio teste** (`test_arquitetura.py` passou a ler a
   pasta) — o defeito que reprovou os ciclos 9, 11 e 13, achado por ele, dentro dele.

---

## §8 — Ordem de serviço (nada aqui bloqueia)

1. **Os três comandos de motor param de mentir.** *Ou* a janela passa a procurar o binário
   (`engine.find_engine`, e `PainelDeEstudo(analyzer=…)`), *ou* os três itens saem do menu / ficam
   desabilitados com a razão na dica. *Alvo: 0 comandos habilitados que não podem ter efeito — hoje
   3; e `settings.EngineSettings.path`, `find_engine` e `EngineAnalyzer` deixam de ser código sem
   chamador em `src/`.*
2. **A régua passa a perguntar a fonte a quem o Qt de fato consulta, por subcontrole.** *Alvo:
   `medir_titulos_de_grupo` mede `QWidget.font()` para `QGroupBox::title` e a folha para
   `QHeaderView::section`, com o teste que prova a diferença — hoje as duas medem a folha, e a
   tabela do §4.1 mostra que o Qt ignora a folha num deles. Prova de vida: pôr o título a 20 pt na
   folha e a régua não pode dizer 85 px onde a tela desenha 34.*
3. **`PAPEL_PINTADO` e `PAPEL_POR_CLASSE` param de ser duas tabelas.** *Alvo: um teste que falhe se
   `PAPEL_POR_CLASSE["QGroupBox"] != PAPEL_PINTADO["QGroupBox::title"]` — hoje nada liga as duas, e
   é só a coincidência entre elas que mantém a faixa e a tinta em 21 px.*
4. **A forma curta `font:` deixa de escapar das duas peneiras.** *Alvo: uma regra
   `QGroupBox::title { font: bold 20pt "Segoe UI" }` faz `seletores ignorados` ir a 1 — hoje vai a 0,
   e o teste que o módulo cita como defesa (`test_a_regua_le_toda_regra_de_fonte_da_folha`) **não
   existe**; o que existe afirma um superconjunto e não cai.*
5. **Duas legendas iguais não convivem numa tela.** *Alvo: 0 pares de botões com a mesma legenda
   desenhada e a mesma ação — hoje `Fechar`+`Fechar` em `_JanelaDePartidas` e `Procurar por nome`
   duas vezes em `DialogoDePartidas`. E o botão do estado vazio de `_JanelaDePartidas` faz alguma
   coisa, ou sai: hoje ele chama `reject`, que é o rodapé. A distinção vai para a **legenda**, não
   só para o `accessibleName`.*
6. **A conta de rótulo de campo passa a incluir a janela.** *Alvo: `outro` vira `Outro` (ou some, com
   o par ganhando dois rótulos) e o instrumento mede a janela junto dos diálogos — hoje ele só olha
   `teclado.RECEITAS`.*
7. **`brancas`/`pretas` e `Brancas`/`Pretas` saem de `ui/strings.SIDE_LABELS`.** *Alvo: um literal
   só, com teste — hoje são dois pares cravados em dois painéis, e `ui/formato.py:12` escreve a
   regra que os dois violam.*
8. **Nem crase nem três pontos em texto desenhado.** *Alvo: 0 e 0 — hoje `` `.pgn` `` em
   `COLECAO_VAZIA_FRASE` e **13** textos com `...` contra 25 com `…`, os dois desenhados nos
   retratos deste ciclo.*
9. **O portão de bloqueio deixa de morrer calado.** *Alvo: 3 de 3 invocações completam pela receita
   publicada — hoje 5 de 8 abortam com `0xC0000005` sem imprimir nada, e 4 de 4 com o
   `PYTHONPATH` que os §8/§6 dos dois últimos relatórios publicam.*
10. **A frase do portão novo diz a população que ele alcança.** *Alvo: "os N `QGroupBox` visíveis da
    janela recém‑aberta" e o nome do que fica fora — hoje "6 de 6", e há um sétimo
    (`painel_de_estudo.py:404`, `Motor (<binário>)`, o único título de largura variável do produto)
    que nenhuma passada visita. E `QLabel[apoio]` sai da tabela do §1.5 ou entra em `medir_a_tela`.*
11. **A fotografia do ANTES volta a ser a tela de antes.** *Alvo: o par ANTES/DEPOIS mantém a fonte
    do widget (`escala.aplicar_escala` reaplicada depois de trocar a folha) — hoje o ANTES pinta
    115 px onde o produto pintava 157, e a captura não encenada do ciclo 12 é a prova. E os oito
    retratos de diálogo: 8 arquivos distintos, cada um no estado em que o produto abre a tela.*
12. **A largura de `Motivo` vem de onde não há informação.** *Alvo: com `Só pendentes` marcado, a
    coluna `Status` não gasta 70 px com 27 repetições de `pendente` — e `Motivo` sai de 25 de 27
    elididos.*
13. **A suíte para de escrever numa pasta publicada.** *Alvo: `tests/integration/test_gpu_parity.py`
    grava em `tmp_path` (ou onde o invocador disser) — hoje ele grava sempre em
    `benchmarks/reports/parity_fp16.json`, de modo que qualquer agente que cumpra a carta §6
    sobrescreve um artefato da pasta de outro. É o item 16 do ciclo 11, um andar abaixo.*
14. **Continuam abertos com os números de sempre, e nenhum precisa fechar:** bloqueio > 16 ms
    (7 operações, mediana 222 ms); vazio de painel a 4K (5 de 6 acima de 200 kpx, pior 3 104,2);
    0 de 5 cabeçalhos de fita na compacta; 6 de 24 botões de fita sem rótulo; tinta dos ícones
    17,6 %–41,4 %; marca da FEN só à direita; `DialogoDeTreino` sem botão desenhado; a etiqueta local
    que segura `7bcb396`.

---

## §9 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<suite>\src;<tronco>\src
set C15=benchmarks\reports\critique\ui\c15
set PY=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe

:: O BLOQUEANTE, com os MEUS instrumentos do ciclo 13, sem uma linha alterada
%PY% benchmarks\reports\critique\ui\c13\c13_titulo_de_grupo_coberto.py <pele> <densidade> 1920
     :: 0 de 6 nos SEIS arranjos; margem 26/28 px, titulo 21 px  (era margem 9 px, 6 de 6 cobertos)
set CVOFF_DENSITY=compacta& %PY% benchmarks\reports\critique\ui\c13\c13_titulo_de_grupo_cortado.py classica 1920
     :: faixa=21 pintado=21 invade=0
%PY% benchmarks\reports\critique\ui\c13\c13_fonte_pintada.py <pele> 1366   :: 0 elididos de 24 (eram 2)
%PY% benchmarks\reports\critique\ui\c11\c11_dialogos_prova.py              :: antes=0 depois=0

:: O PORTAO NOVO e a prova de vida, rodados por mim
%PY% -m caissa.ui.audit.texto_pintado --pdf "<livro>.pdf" --saida %C15%\gate_texto_pintado
     :: 24 passadas | 564 | 24 cegos | 0 cobertos | 0 cortados | 0 fora da analise. PASSOU
%PY% -m caissa.ui.audit.texto_pintado --pdf "..." --faixa-de-antes --saida %C15%\prova_de_vida
     :: 108 cobertos; 3 8 8 8 5 5 na compacta; 3 de 6 na confortavel. REPROVOU

:: O DECIMO SEGUNDO INSTRUMENTO CEGO  (nada e' escrito no produto: a folha troca em memoria)
%PY% %C15%\c15_quem_pinta_o_titulo.py       :: a folha NUNCA ganha em QGroupBox::title
%PY% %C15%\c15_quem_pinta_o_cabecalho.py    :: a folha SEMPRE ganha em QHeaderView::section
%PY% %C15%\c15_a_regua_contra_a_tela.py     :: a regua diz 85 px; a tela desenha 34
%PY% %C15%\c15_sabotar_o_texto_pintado.py   :: `font:` curto passa calado; virgula/descendencia/id acusam
%PY% %C15%\c15_o_que_a_faixa_de_antes_muda.py :: --faixa-de-antes tambem devolve a fonte do widget a 9pt

:: AS TELAS
%PY% %C15%\c15_olhar_as_telas.py            :: ['Fechar','Fechar']; menu do motor; 6 QGroupBox; barra 0..8
%PY% %C15%\c15_retratar.py                  :: os retratos que faltavam
certutil -hashfile benchmarks\reports\ui\c14\capturas\c14_dialogo_JanelaDeBusca__Achar_no_texto_.png SHA256
certutil -hashfile benchmarks\reports\ui\c14\capturas\c14_dialogo_JanelaDeBusca__substituindo_.png  SHA256
     :: 8c3d2e05201ad903...f188e146  nos dois

:: OS PORTOES DE SEMPRE
%PY% -m caissa.ui.audit.teclado   --pdf "..." --saida %C15%\gate_teclado  :: 216/216/240/240/360/360 +50. PASSOU
%PY% -m caissa.ui.audit.contraste --saida %C15%\gates                     :: 300/220/0; 3,27 e 3,03. PASSOU
set PYTHONPATH=<suite>\src& %PY% -m caissa.ui.audit.bloqueio --pdf "..." --execucoes 1 --sem-perfil --saida %C15%\gates
     :: REPROVOU, 7 ops, abrir PDF 222/221/232 -> mediana 222 ms; 5 de 8 invocacoes abortam

:: AS SUITES
.venv\Scripts\python.exe -m pytest tests\unit\ui -q -p no:cacheprovider          :: 238 passed
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py
     :: 3126 passed, 1 skipped, 0 failed
<tronco>\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly -p no:cacheprovider
     :: 3 failed, 4486 passed, 2 skipped, 4536 subtests em 273,9 s

:: NENHUM TESTE DO TRONCO ALTERADO
find <tronco>\src\chess_diagram_ocr <tronco>\tests -name "*.py" -newermt "2026-09-09 22:00"
     :: 12 arquivos, todos em src/; ZERO em tests/
```

---

## §10 — Veredito

**APROVADO.**

Aprovo porque o defeito que reprovou o ciclo 13 não está mais na tela, e eu não aceitei a palavra de
ninguém sobre isso: rodei os **meus** dois instrumentos, sem alterar uma linha, nas **seis**
combinações de pele × densidade, e os dois devolvem zero — `0 de 6 títulos cobertos`,
`faixa = pintado = 21, invade = 0`. A margem que reservava 9 px para 21 px de tinta reserva 26 e 28.
Olhei os pares ampliados a 4× e a diferença é a que a crítica pediu: `Comentário do lance` passa de
8 linhas de tinta com o filete do quadro atravessando as letras para 12 linhas de rótulo inteiro. E
olhei a captura que **ninguém produziu para provar nada** — a do ciclo 12 —, e nela o mesmo título
mede 157 px cortado ao meio, o que confirma o defeito e mostra que ele era pior do que o par que o
construtor publicou.

Aprovo porque a prova de vida é real e eu a rodei: `--faixa-de-antes` devolve **108 títulos
cobertos** nas 24 passadas e reproduz os **meus** seis nomes com os **meus** seis números
(3 · 8 · 8 · 8 · 5 · 5), e o caminho é uma reaplicação de folha que não toca um byte do produto.
Uma régua que sabe reprovar é uma régua.

Aprovo porque os onze itens não bloqueantes foram atacados um a um e oito fecharam com o número
pedido, medidos pelos meus instrumentos e não pelos dele: `Resultado` elidido **2 → 0 de 24** nas
três peles, e fechado na **raiz** — `_largura_da_secao` continua perguntando a fonte do widget, e
quem mudou foi o momento em que a escala alcança o diálogo; `Ok` de volta ao que o `qtbase_pt_BR.qm`
escreve, com **16 de 18** concordando e a única divergência com o motivo escrito; estados vazios
**0 de 5 → 5 de 5**; `JanelaDeAtalhos` sem rolagem horizontal; barra do treino determinada e com
`época 3 de 8` **desenhado**, que eu fotografei; os quatro buracos do achador fechados e a frase do
portão encolhida para o tamanho da medição. As suítes batem: `238`, `3 126`, e `3 failed / 4 486
passed` no tronco — os mesmos três de sempre. E a divulgação se sustenta ao `mtime`: **zero**
arquivos de teste do tronco tocados neste ciclo, contra doze de produto. Ele moveu o conserto para a
raiz e deixou o teste em paz.

Não reprovo pelo que achei, e digo por quê, item a item. O **décimo segundo instrumento cego** é
real e é de uma espécie nova — a régua pergunta a fonte à folha num subcontrole em que o Qt joga a
folha fora, e eu meço a régua dizendo 85 px onde a tela desenha 34 —, mas hoje ela acerta, porque
`PAPEL_PINTADO` e `PAPEL_POR_CLASSE` dizem as duas `TITULO`. **Não há tinta apagada atrás dela.**
Reprovar por um instrumento que hoje dá a resposta certa seria reprovar uma arquitetura, e a carta
me manda julgar a tela. O que a carta me manda fazer é escrever a conta, e ela está no §4 e nos itens
2, 3, 4 e 10 do §8: se essa deriva voltar, ela volta calada.

Os outros seis são desenho e palavra: dois botões com a mesma legenda em duas telas de diálogo
(e a distinção dada a quem ouve em vez de a quem vê); `outro` em minúscula na janela que a conta do
item 10 não visitou; `brancas` numa aba e `Brancas` na outra com o catálogo dizendo qual é a certa;
duas crases de Markdown e treze reticências de três pontos desenhadas; um portão que morre calado em
5 de 8 invocações; e dois retratos que são o mesmo arquivo. Nenhum deles apaga uma letra, trava a
janela, perde trabalho ou esconde um erro.

O mais sério é o mais antigo, e nenhum dos catorze ciclos o olhou: **três comandos do menu Estudo
estão habilitados e nunca podem funcionar**, porque a janela nunca procura o motor, e a mensagem
manda instalar o Stockfish e reabrir — o que não resolve. É item 1 do §8. Não é veredito porque a
falha é sinalizada e não silenciosa, nada se perde, e é uma ligação que falta, não um defeito do
acabamento que catorze ciclos vinham medindo. Se ela fosse silenciosa, seria veredito.

Catorze ciclos, e todo bloqueante nomeado morreu com o número que foi pedido. Este morreu com o
número pedido **e** com a régua que faltava, publicada com o tamanho do próprio ponto cego ao lado.
É hora.
