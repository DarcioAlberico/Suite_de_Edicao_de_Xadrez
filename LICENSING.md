# Licenciamento do binário distribuído do Caïssa Studio

**Escopo.** Este arquivo é sobre **distribuir um executável**. Rodar o projeto a partir do
checkout, para uso próprio, não levanta nenhuma das questões abaixo — a obrigação de
copyleft nasce no ato de entregar o binário a outra pessoa.

**O que este arquivo não é.** Não é parecer jurídico. Ele registra fatos verificáveis — que
licença cada dependência declara, medida no ambiente de empacotamento — e diz o que cada
fato implica. Onde o fato é "não se sabe", está escrito "não se sabe".

**Data da medição: 2026-09-09**, no venv de empacotamento
(`.venv-pack`, CPython 3.11.9). Os campos vieram de `importlib.metadata`, não de memória.

---

## 1. A resposta curta

O binário do Caïssa Studio, como empacotado hoje, **é uma obra derivada sob AGPL-3.0**.

A ADR-0009 registrou honestamente que **PyQt6 é GPL** e que isso tem consequências. A
medição confirma a ADR e acrescenta uma dependência mais forte que ela não citava:

| Componente | Versão | Licença declarada | Efeito na distribuição |
|---|---|---|---|
| **PyMuPDF** | 1.28.2 | `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License` | **AGPL-3.0** — a mais forte do conjunto |
| **PyQt6** | 6.11.0 | `License-Expression: GPL-3.0-only` | GPL-3.0 (ou licença comercial da Riverbank) |
| python-chess | 1.11.2 | `GPL-3.0+` | GPL-3.0 |
| PyQt6-Qt6 (as bibliotecas Qt) | 6.11.2 | `LGPL v3` | LGPL — *não* é o problema |
| PyInstaller | 6.22.2 | GPLv2+ **com exceção de bootloader** | não contamina o app congelado |
| torch / torchvision | `2.11.0+cu128` **ou** `2.14.0+cpu` — a roda depende da GPU do usuário (§4) | Apache-2.0, BSD-2/3, BSL-1.0, MIT | permissiva |
| numpy · Pillow · OpenCV · fontTools · platformdirs · python-ulid · tomli-w | — | BSD / MIT / Apache-2.0 / MIT-CMU | permissivas |

> **O achado que a ADR-0009 não previa: PyMuPDF é AGPL, não GPL.**
> A AGPL acrescenta à GPL a cláusula de uso em rede (§13): quem oferece o programa
> **modificado** como serviço acessível pela rede deve oferecer o fonte aos usuários desse
> serviço, mesmo sem distribuir binário nenhum. Para um aplicativo de desktop instalado na
> máquina do usuário isso não muda nada na prática; a hora em que passa a importar é a
> primeira vez que alguém puser o Caïssa atrás de um serviço web.

### A inconsistência do ciclo 1, corrigida no ciclo 2

O ciclo 1 registrou aqui que `pyproject.toml` declarava `license = { text =
"LGPL-3.0-or-later" }` e que aquilo era falso: com PyMuPDF (AGPL-3.0), PyQt6 (GPL-3.0-only)
e python-chess (GPL-3.0+) no conjunto, **um binário distribuído não pode ser LGPL** — a LGPL
é mais permissiva do que a GPL permite para uma obra combinada.

**Corrigido em 2026-09-09.** O `pyproject.toml` agora declara
`license = { text = "AGPL-3.0-or-later" }`, com a medição no comentário acima da linha. Os
dois arquivos passaram a dizer a mesma coisa, e
`tests/integration/test_packaging.py::TestLicencas::test_o_LICENSING_concorda_com_o_pyproject`
existe para que a próxima divergência apareça num teste vermelho, e não na leitura de quem
for redistribuir.

### O que a distribuição sob AGPL-3.0-or-later exige, na prática

São as cinco obrigações que `packaging/licenses/TERCEIROS.md` repete dentro do pacote
instalado:

1. **Entregar o código-fonte correspondente** — o do Caïssa e o das bibliotecas copyleft —
   ou uma oferta escrita e válida de obtê-lo, junto com o binário. "Correspondente" quer
   dizer: o fonte **daquele** build, não o do repositório em outra data.
2. **Manter os avisos de copyright e o texto das licenças** dentro do pacote instalado —
   `_internal/licenses/`, que o §4 detalha.
3. **Licenciar o conjunto sob AGPL-3.0-or-later**, e não sob termos mais restritivos.
4. **Não impedir a modificação e a reinstalação** pelo usuário.
5. **§13 (a cláusula que a GPL não tem):** se o programa **modificado** for oferecido por
   rede, o fonte vai para os usuários desse serviço — mesmo sem distribuir binário nenhum.

Nada disso impede a distribuição. Impede a distribuição **fechada**.

> **Quem redistribuir este build assume estas cinco obrigações.** Não são do dono do
> projeto: são de quem entrega o arquivo. Um `.zip` do `dist/Caissa/` enviado a um colega já
> é distribuição.

---

## 2. Os ativos de terceiros dentro do bundle

### 2.1 O que entra

| Ativo | Tamanho | Origem | Situação |
|---|---:|---|---|
| `assets/piece_images/` (12 PNG) | 40 KB | **cburnett**, rasterizado dos SVG em `packaging/assets/piece_images_fonte/` | **GPL-2.0-or-later**, redistribuído sob GPL-3.0 — ver abaixo |
| `assets/cvoff.ico` | 46 KB | gerado por `ui/plataforma.py::gravar_icone()`, versionado | do projeto |
| `assets/lexico/acervo.txt.gz` | 24,9 KB | camada de texto editorada dos livros do acervo do dono do projeto | do projeto, derivado e refazível |

**Os doze PNGs de peça — a lacuna do ciclo 1, fechada no ciclo 2.**

O ciclo 1 registrou aqui que `assets/piece_images/` entrava no bundle **sem arquivo de
procedência**, sob a hipótese — escrita no código do tronco, em nenhum documento — de que
eram *"os PNGs do próprio tronco"*. O ciclo 2 investigou a hipótese e ela **não se
sustenta**: `packaging/licenses/PECAS_PROCEDENCIA.md` mede que os 12 PNG do tronco são a
mesma arte que o único documento de atribuição disponível atribui à **Chess.com**, descrita
ali como *"All rights reserved. No open-source license provided."* (IoU 0,98 e canal de cor
idêntico). Aquele documento não é a fonte, e a investigação diz por extenso o que **não**
estabeleceu: a rota da cópia, a alegação na origem, e que nada disso é parecer jurídico.

**Decisão desta frente: os 12 PNG do tronco não são distribuídos.** No lugar deles o pacote
leva o conjunto **cburnett**, de Colin M. L. Burnett, GPL-2.0-or-later — rasterizado dos SVG
originais por `packaging/gerar_pecas_livres.py`, com o SHA-256 de cada SVG registrado em
`packaging/assets/piece_images_fonte/PROCEDENCIA.json`. A atribuição viaja no pacote
(`_internal/licenses/PECAS_CBURNETT.md`), e o texto da GPL-3.0 vai junto.

Isto **aumenta** a obrigação de copyleft em vez de diminuí-la, e é a troca certa: uma
licença forte e conhecida no lugar de uma licença desconhecida. Sob AGPL-3.0-or-later, que
já é a licença do conjunto, a GPL-3.0 das peças não acrescenta restrição nova.

### 2.2 O que **não** entra, e por quê

#### Os dois léxicos de procedência não declarada

`ChessVisionOFF_Puro/assets/lexico/PROCEDENCIA.md` registra, em detalhe e por conta própria:

- **`idioma.txt.gz`** (31 KB, 10.010 palavras) — sai de `Dic-1.txt` e
  `Novo Documento de Texto.txt`, que *"não trazem cabeçalho, licença nem README"*.
  **De fora, origem não declarada.**
- **`nomes.txt.gz`** (1,09 MB, 349.565 nomes) — 57,0% vem das bases PGN do próprio dono do
  projeto; **0,4% vem exclusivamente de `MegaDatabase(Jogadores).txt`**, que o próprio
  PROCEDENCIA.md identifica como *"um extrato de índice de jogadores"* da MegaDatabase da
  **ChessBase — base comercial**; e 42,6% mistura essas fontes com as duas listas soltas.

A F5 já sinalizou isso, e o PROCEDENCIA.md fecha dizendo **"Decisão: pendente do dono do
projeto"**. Uma decisão pendente não é uma autorização, e o empacotamento é exatamente o
ponto em que ela deixa de poder ficar pendente: **distribuir é o ato que cria a
responsabilidade.**

**Decisão desta frente: os dois ficam fora do binário.** Não estão em `datas` na
`packaging/caissa.spec`; estão em `packaging/manifesto.json` marcados
`"consentimento": true`, e o assistente de primeira execução só os instala com
`--aceitar-licenca-nao-apurada` — uma flag escrita por extenso de propósito, porque um
`--sim` genérico faria o usuário aceitar sem ler.

**O custo dessa exclusão está medido, e é pequeno.** O PROCEDENCIA.md mediu em 40 páginas de
11 livros: *"Tirar os nomes não muda uma letra do que o leitor entrega hoje."* Sem os dois,
o texto de saída é **idêntico caractere por caractere**; o que se perde são 39 + 22 palavras
de proteção contra reescrita do dicionário. Um seguro, e pequeno — contra uma pergunta de
licenciamento sem resposta.

#### As duas fontes tipográficas

`ChessVisionOFF_Puro/fonts (2)/` tem `NotoSansSymbols2-Regular.ttf` (Noto — SIL Open Font
License, clara) e **`SimbolosDeXadrez.ttf` (procedência não declarada)**. Nenhuma das duas
entra no bundle: não estão em `assets/` e não estão em `datas`. A segunda ficaria fora de
qualquer jeito, pela mesma regra dos léxicos.

#### O LLM

Não é uma questão de licença e sim de mérito, mas pertence ao mesmo inventário:
`docs/quality/F11_REPORT.md` mediu **Gemma 4 E4B com especificidade 0,000** na verificação de
diagramas — ele aprova tudo, e um verificador que nunca reprova não verifica. **Não é
empacotado, não é baixado, e não está no manifesto.** Os gigabytes ficam no disco do usuário
e o veredito que eles comprariam não discrimina.

---

## 3. O que teria de mudar para uma distribuição fechada

A ADR-0009 diz que a escolha de PyQt6 é **econômica e reversível**, e que a disciplina
`ui/` (decide, sem toolkit) contra `qt/` (pinta) mantém a porta aberta. Isso continua
verdadeiro e é metade do caminho. A outra metade é o PyMuPDF, que a ADR não citava.

| Bloqueio | Custo de sair | Observação |
|---|---|---|
| **PyQt6** (GPL-3.0-only) | migrar para **PySide6** (LGPL-3.0) — `pyqtSignal` → `Signal`, `pyqtSlot` → `Slot`; enums já são escopados nos dois | Mecânico, pela disciplina `ui/`. O `pyproject.toml` da suíte **já** declara `pyside6-essentials`; é o tronco que está em PyQt6. **Ou** licença comercial da Riverbank. |
| **PyMuPDF** (AGPL-3.0) | licença comercial da **Artifex**, ou trocar por `pypdfium2` (BSD-3) / `pdfminer.six` (MIT) | **É o mais caro.** O ASSETS §2.8 e §2.9 documentam que os dois espaços de coordenadas do PDF e a gravação atômica/cancelável são joias da coroa construídas em cima do PyMuPDF. Não é um `import` que se troca. |
| **python-chess** (GPL-3.0+) | reimplementar validação de legalidade e PGN, ou achar equivalente permissivo | Caro em correção: legalidade e promoções são exatamente onde a decodificação com restrições (ASSETS §2.3) ganha precisão. |
| PyInstaller | nada | A exceção de bootloader existe justamente para isto: o app congelado não herda a GPLv2. |
| torch, numpy, Pillow, OpenCV, fontTools | nada | Permissivas. Basta manter os avisos. |
| **PNGs de peça** (cburnett, GPL-2.0-or-later) | desenhar um conjunto próprio, ou licenciar um permissivo | Hoje eles **acrescentam** copyleft, e por isso a linha está aqui. Sob AGPL não custam nada; numa distribuição fechada, custam. O caminho já está pavimentado: `gerar_pecas_livres.py` rasteriza de SVG, então trocar o conjunto é trocar 12 arquivos de entrada. |
| Léxicos | reconstruir de fonte declarada | O PROCEDENCIA.md do tronco já descreve a saída 3: *"uma lista de nomes com licença explícita, ou os nomes que o próprio acervo já traz"*. Não é bloqueio de distribuição: eles já ficam de fora. |

**Ordem recomendada, se um dia a decisão vier:** PyMuPDF primeiro (é o que decide entre AGPL
e GPL, é o mais caro, e é o que ninguém está preparando), PyQt6 depois (é mecânico e a porta
está aberta), python-chess por último.

---

## 4. O que fica dentro do pacote instalado

O instalador grava, ao lado do executável:

- este arquivo (`LICENSING.md`), em `_internal/`;
- `assets/lexico/PROCEDENCIA.md`, o registro original do tronco sobre os léxicos, **inclusive
  a parte que descreve os dois arquivos que não foram empacotados** — o usuário que quiser
  entender por que a pasta tem um `.txt.gz` e não três encontra a resposta ali;
- `_internal/manifesto.json`, que declara para cada componente a licença, a procedência e o
  que se perde sem ele.

**O que faltava no ciclo 1 e existe no ciclo 2** — `_internal/licenses/`, gerado por
`packaging/coletar_licencas.py` e medido em 2026-09-09:

| dentro de `_internal/licenses/` | o que é |
|---|---|
| `AGPL-3.0.txt`, `GPL-3.0.txt`, `LGPL-3.0.txt` | os três textos integrais das licenças copyleft do conjunto |
| uma pasta por dependência (21 delas) | o arquivo de licença que **aquela** distribuição publica, copiado do próprio pacote instalado |
| `TERCEIROS.md` | o aviso consolidado, com as cinco obrigações do §1 |
| `PECAS_CBURNETT.md` | a atribuição da arte das peças |
| `PECAS_PROCEDENCIA.md` | por que a arte anterior não é distribuída |
| `INDICE.json` | o índice legível por máquina: cada distribuição, versão, licença declarada, arquivos, e se veio do bundle ou de `runtime/` |

**As 21 cobrem as duas metades da entrega**: as 12 que viajam em `_internal/` e as 9 que o
assistente de primeira execução instala em `runtime/` (torch, torchvision, sympy, networkx,
filelock, fsspec, Jinja2, MarkupSafe, mpmath). Uma coleta que olhasse só para o instalador
deixaria essas nove de fora e diria "tudo certo" — a obrigação acompanha o que o programa
**entrega**, não o que o `setup.exe` carrega.

E o portão que impede a lista de envelhecer:
`test_TODA_dependencia_distribuida_tem_texto_de_licenca` reprova se `INDICE.json` listar
qualquer distribuição sem texto. Enquanto ele estiver verde, o pacote **pode** ser entregue
a terceiros sob AGPL-3.0-or-later — o que no ciclo 1 não podia.

---

## 5. Resumo em cinco linhas

1. O binário é **AGPL-3.0-or-later**, por causa do PyMuPDF — não apenas GPL, como a ADR-0009
   supunha. O `pyproject.toml` foi corrigido e agora diz o mesmo.
2. Distribuir é permitido; distribuir **fechado** não é, sem licença comercial ou troca de
   dependências.
3. Os dois léxicos de licença não apurada **não estão no bundle**, e tirá-los não muda um
   caractere da saída.
4. Os doze PNGs de peça agora são **cburnett** (GPL-2.0-or-later, redistribuídos sob
   GPL-3.0), com atribuição no pacote. A arte anterior, medida como sendo de procedência não
   apurável, **não é distribuída**.
5. Os textos das licenças **estão** dentro do pacote, as 21 dependências distribuídas estão
   cobertas, e um teste reprova a que entrar sem texto. O build deixou de ser "para uso
   próprio".
