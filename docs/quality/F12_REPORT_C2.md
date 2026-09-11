# F12 ciclo 2 — o torch sai do instalador, e o pacote passa a poder ser entregue

> **Data:** 2026-09-09 · **Máquina:** a de referência da SPEC §2 (Ryzen 5 8400F, 31,6 GiB,
> RTX 5060 8 GB `sm_120`, driver 591.86, Windows 11 Pro 26200, C: 931 GB).
>
> **Regra deste relatório, herdada do ciclo 1:** todo número veio de um comando executado
> nesta máquina hoje. Onde não houve medição, está escrito que não houve — a §8 lista o que
> **não** foi verificado, e continua sendo a seção mais importante para quem seguir.

---

## 0. Conclusão em uma tela

| Pergunta | Resposta medida |
|---|---|
| O instalador cabe nos 150 MB da SPEC §12? | **Sim. 79,4 MB** (proxy LZMA2 medido) — 70,6 MB de folga. O ciclo 1 dava 169,3. |
| O que mudou para caber? | **O torch saiu do bundle.** Ele custa 436,3 MB de bundle e 90,1 MB de instalador — medido nas duas variantes, hoje. |
| Quem tem GPU perde velocidade por isso? | **Não. Ganha.** O assistente instala **cu128** para `sm_120`, não a roda de CPU que o ciclo 1 congelava: 0,0903 s/diagrama em vez de 0,5234. |
| O caminho de download foi exercido? | **Sim.** 2.643 MB baixados de `download.pytorch.org`, SHA-256 conferido roda a roda, instalados em **80 s**. |
| Há caminho offline? | **Sim, e foi rodado**: `--rodas-de <pasta>` instalou a variante de CPU em **30 s sem tocar a rede**. |
| O `doctor.py` roda a partir do bundle? | **Sim.** `sm_120 (12, 0)`, matmul real 4096² fp16 em **5,46 ms**, portão F0 **APROVADO**. |
| O auto-teste passa com as peças substitutas? | **Sim.** Código 0, lê `4k2r/8/8/3p4/3P4/8/8/R3K3`, confiança mínima 0,804, legal. |
| Os textos de licença estão dentro do pacote? | **Sim: 21 dependências, 99 arquivos, `sem_texto: []`** — e agora há um teste que reprova a que entrar sem texto. |
| O instalador foi compilado? | **Não.** O Inno Setup continua ausente desta máquina. §8. |
| Disco antes / depois | **34,26 GiB → 33,98 GiB** (−0,28 GiB líquido; o vale foi 27,6 GB durante a instalação do cu128) |

---

## 1. O tamanho, medido nas duas variantes hoje

O ciclo 1 comparava a variante que se distribuía (169,3 MB, acima do teto) com uma variante
"leve" que **não abria**. Este ciclo inverteu os papéis: o padrão é o que não leva torch, e
`CAISSA_COM_TORCH=1` monta a variante de **medição** — que existe só para dar este número.

| | bundle | arquivos | instalador (proxy LZMA2) | teto de 150 MB |
|---|---:|---:|---:|---|
| **padrão** — o que se distribui | **295,3 MB** | 1.307 | **79,4 MB** | **70,6 MB de folga** |
| `com-torch` — só medição | 731,6 MB | 3.994 | 169,5 MB | 19,5 MB acima |
| **diferença** | **436,3 MB** | 2.687 | **90,1 MB** | |

O arquivo medido: `dist/caissa-0.1.0-padrao-proxy.7z`, **83.291.456 bytes**. As métricas
ficam em `packaging/bundle.json` e `packaging/bundle-com-torch.json`, gravadas pelo build.

### 1.1 Os dois executáveis encolheram 32 MB cada

O ciclo 1 mediu que os dois `.exe` carregavam a árvore `.pyc` do torch **cada um** — 40,5 MB
de duplicação. Sem torch no bundle, isso desaparece:

| | ciclo 1 (bytes) | ciclo 2 (bytes) | diferença |
|---|---:|---:|---:|
| `Caissa.exe` | 44.440.612 (42,38 MB) | **10.670.676 (10,18 MB)** | **−32,20 MB** |
| `CaissaPrimeiraExecucao.exe` | 42.446.865 (40,48 MB) | **8.619.329 (8,22 MB)** | **−32,26 MB** |

### 1.2 O que sobrou no bundle, e é o próximo alvo

```
100,4 MB  34,0%  cv2
 72,0 MB  24,4%  PyQt6           <- a janela
 37,7 MB  12,8%  pymupdf
 20,0 MB   6,8%  numpy.libs
 12,8 MB   4,3%  PIL
```

Com o torch fora, **`cv2` virou o maior item do pacote** — um terço dele. Não é desta frente
decidir o que fazer com isso, mas o número agora existe e a decisão passou a ser possível.

---

## 2. O torch como componente de primeira execução

### 2.1 Por que isto era o ponto do ciclo

`docs/quality/F4GPU_REPORT.md` §7 mediu **0,0903 s/diagrama em GPU contra 0,5234 em CPU**.
O ciclo 1 congelava a roda de **CPU** dentro do instalador — de modo que o produto instalado
entregava 5,8× menos velocidade do que o mesmo código rodando do checkout, **em silêncio**, a
quem tivesse a placa que a SPEC §2 chama de máquina de referência.

O torch agora segue o caminho que os pesos já seguiam: sai do instalador e chega na primeira
execução, com SHA-256, caminho offline obrigatório, e a roda **certa para a GPU do outro
lado**.

### 2.2 A transcrição da instalação, do bundle, nesta máquina

`dist/Caissa/CaissaPrimeiraExecucao.exe`, com `runtime/` vazio:

```
Instalando PyTorch cu128 (GPU NVIDIA Blackwell e posteriores)
  2643 MB em 10 rodas, de download.pytorch.org (HTTPS).
  Cada uma e conferida por SHA-256 antes de ser desempacotada.

  torch-2.11.0+cu128-cp311-cp311-win_amd64.whl:    128 de 2626 MB (   5%)
  ...                                             (uma linha a cada 128 MB)
  torch-2.11.0+cu128-cp311-cp311-win_amd64.whl:   2560 de 2626 MB (  98%)

[INFO ] Placa de video
         NVIDIA GeForce RTX 5060 - sm_120 - driver 591.86
         NVIDIA GeForce RTX 5060 (sm_120, driver 591.86). A SPEC R1 e a ADR-0003 dizem
         que sm_120 so tem kernels nas rodas cu128 ou posteriores -- e por isso e a cu128
         que vai ser instalada, e nao a de CPU.

[ OK  ] PyTorch - PyTorch cu128 (GPU NVIDIA Blackwell e posteriores)
         instalado em 80 s (2643 MB em ...\dist\Caissa\runtime)
         O reconhecimento vai a **0.0903 s por diagrama** (medido nesta maquina,
         docs/quality/F4GPU_REPORT.md secao 7). Em CPU seriam 0.5234 s -- 5.8x mais lento.
         Um livro de 300 paginas com 400 diagramas leva cerca de 1 min em vez de 3 min.
```

**80 segundos**, 10 rodas, cada uma verificada antes de ser desempacotada. Resultado em
disco: `runtime/` com **4.311 MB**. A marca `runtime/caissa_torch.json` registra **14.413
entradas desempacotadas**; o disco tem 16.009 arquivos, e a diferença são 1.594 `.pyc` que os
próprios imports criaram depois — o que também confirma que a pasta é usada, e não só
gravada.

A escolha não é `is_available()`: `caissa_torch.detectar_gpu()` pergunta ao `nvidia-smi` a
`compute_cap` **antes de existir torch na máquina**, e `escolher_variante()` decide a partir
dela. O motivo da escolha é impresso junto — porque um usuário que recebe CPU precisa saber
que recebeu CPU.

### 2.3 A frase que o usuário de CPU lê

Medido forçando a outra roda (`--torch-variante cpu`), que instalou **129 MB em 32 s**:

```
[ OK  ] PyTorch - PyTorch CPU (sem GPU NVIDIA utilizavel)
         O reconhecimento vai a **0.5234 s por diagrama**. Nada quebra: a deteccao, o OCR,
         a notacao, a tipografia e os exportadores nao usam GPU. Com uma GPU NVIDIA seriam
         0.0903 s -- 5.8x mais rapido. Na pratica: um livro de 300 paginas com 400
         diagramas leva cerca de 3 min em vez de 1 min.
```

Em segundos, e não em adjetivos. E dizendo **o que não muda** — porque "funciona mais
devagar" e "essa parte não existe" são respostas diferentes.

*(Um defeito corrigido no caminho: a frase da CPU terminava em `"em vez de 1."`, sem a
unidade. Uma letra, mas é a última coisa que o usuário lê sobre o assunto.)*

### 2.4 O caminho offline, rodado sem rede

```
> CaissaPrimeiraExecucao.exe --torch-variante cpu --rodas-de <pasta com os 10 .whl>
Instalando PyTorch CPU (sem GPU NVIDIA utilizavel)
  129 MB em 10 rodas, de ...\scratchpad\cpu_offline_rodas.
  Cada uma e conferida por SHA-256 antes de ser desempacotada.
[ OK  ] PyTorch - ... instalado em 30 s
```

**Nenhum byte de rede.** As rodas vieram de uma pasta local, e cada uma passou pelo mesmo
portão de hash — que aqui pesa mais do que na rede: um `.whl` é um zip de código que vai ser
desempacotado e importado, e aceitá-lo porque "veio de um pendrive" seria confiar na origem
em vez de no conteúdo. As duas recusas (`hash-errado`, `nao-encontrado`) têm teste próprio.

### 2.5 A prova: `doctor.py` reportando `sm_120` **a partir do bundle**

`dist\Caissa\CaissaPrimeiraExecucao.exe --doctor`, com o torch vindo de `runtime/`:

```
GPU / PYTORCH
  [  OK  ]  Versao do PyTorch                    2.11.0+cu128
  [  OK  ]  CUDA da roda do PyTorch              12.8
  [ INFO ]  torch.cuda.is_available()            True
            Valor apenas informativo -- ele retorna True mesmo quando nao existem kernels
            para a arquitetura da GPU. A verificacao real e a de baixo.
  [ INFO ]  Driver NVIDIA                        591.86
  [  OK  ]  Compute capability                   sm_120 (12, 0)
  [  OK  ]  VRAM total / livre                   7.96 GiB total, 6.85 GiB livres
  [  OK  ]  Multiplicacao real 4096x4096 fp16    5.46 ms (25.1 TFLOP/s)
  [  OK  ]  Conferencia numerica (ref. de CPU)   erro maximo 0.03098 (tolerancia 0.50000)

RESUMO: 19 ok · 1 aviso · 0 falhas · 0 pulados · 7 informativos

PORTAO F0 (itens de GPU do ROADMAP):
  - GPU ativa com capability sm_120 (12, 0): sim
  - Matmul 4096x4096 abaixo de 100 ms: sim (5.46 ms)
  => APROVADO
```

Cinco execuções ao longo da sessão deram **4,72 · 5,05 · 5,20 · 5,34 · 5,46 ms** — todas duas
ordens de grandeza abaixo do limite de 100 ms do portão. O único aviso é o de sempre: o
relatório está sendo gerado fora do `.venv` do projeto, o que é exatamente o que se espera de
um `.exe`.

**O que este relatório prova, e é o ponto:** o kernel real roda a partir do pacote instalado,
com a roda que o próprio pacote escolheu e baixou. Não é `is_available()` dizendo `True`.

### 2.6 A sonda de importação, degrau a degrau

`--sondar-torch` importa a cadeia em 12 degraus e grava cada um. Do bundle final:

```
runtime=...\dist\Caissa\runtime existe=True
frozen=True meipass=...\dist\Caissa\_internal
-> typing_extensions ok   -> filelock ok   -> mpmath ok    -> sympy ok
-> networkx ok            -> fsspec ok     -> jinja2 ok    -> torch.version ok
-> torch._C ok            -> torch ok      -> torch.cuda.is_available ok
-> torchvision ok
```

**12 de 12.** Esses degraus existem por causa do defeito da §3.

---

## 3. A biblioteca padrão que só o torch usa — a lista, e o portão que faltava

### 3.1 O defeito

Tirar o torch do bundle tira junto uma coisa que ninguém declara: os módulos da **biblioteca
padrão** que só ele importa. O PyInstaller coleta o que **vê**; sem nenhum `import torch` na
árvore congelada, ele não vê `uuid`, não vê `unittest.mock`, não vê
`asyncio.windows_events`. O torch instalado depois em `runtime/` acha o próprio pacote e não
acha o Python embaixo dele — e o sintoma não é legível:

```
-> filelock       FALHOU  ModuleNotFoundError: No module named 'uuid'
-> torch.version  FALHOU  ImportError: cannot import name 'mock' from 'unittest'
-> torch._C       EXIT = -1073740791     (0xC0000409, o processo morre sem traceback)
```

### 3.2 A medição

`build_windows.py --medir-stdlib-do-torch` importa torch e torchvision num processo limpo,
em **três** fontes, e grava a união:

| fonte | torch |
|---|---|
| `dist/Caissa/runtime` | 2.11.0+cu128 |
| `.venv/Lib/site-packages` | 2.11.0+cu128 |
| `.venv-pack/Lib/site-packages` | 2.14.0+cpu |

**178 módulos, idênticos nas três.** A `caissa.spec` os pede em `hiddenimports` nas **duas**
`Analysis` — a janela e o assistente —, e **recusa montar** se `stdlib_do_torch.json` não
existir. O assistente precisa da lista tanto quanto a janela: ele instala 2,6 GB e sonda o
que instalou no mesmo processo.

### 3.3 O que a lista de nomes **não** cobre, e é o que o ciclo 1 perdeu

Um nome em `hiddenimports` faz o PyInstaller *tentar* coletar. Não garante que a extensão
nativa chegou — e quando não chega, ninguém reclama. Foi assim que o ciclo 1 perdeu **todos
os ícones da fita**: `_tkinter.pyd` ficou de fora, os `.py` de `tkinter` entraram,
`PIL/ImageTk.py` levantou `ImportError`, e como `ui/icones.py` importa
`Image, ImageDraw, ImageTk` **na mesma linha**, o `except` do módulo zerou os três. Build
verde, instalador verde, janela sem ícones.

Então a medição ganhou um segundo lado: **quais extensões nativas a árvore realmente
carrega**, medidas do mesmo jeito. São **17**:

```
_asyncio  _bz2  _ctypes  _decimal  _elementtree  _hashlib  _lzma  _multiprocessing
_overlapped  _queue  _socket  _sqlite3  _ssl  _tkinter  _uuid  pyexpat  select
```

E `build_windows.conferir_extensoes_nativas()` roda **depois** do PyInstaller e reprova o
build que sair sem alguma. Exercido contra um `_internal/` deliberadamente furado:

```
ERROR O bundle saiu sem 1 extensao(oes) nativa(s) ... que a medicao de 2026-09-09 exige:
ERROR   _tkinter   -> _tkinter.pyd AUSENTE em ...\_internal
ERROR Isto NAO e cosmetico: um modulo pela metade nao levanta onde falta -- ele levanta em
ERROR quem o importa. Foi assim que `_tkinter.pyd` apagou todos os icones da fita no ciclo 1.
codigo = 1
```

Nos três builds desta sessão a checagem passou: *"As 17 extensoes nativas da biblioteca
padrao estao em _internal/."*

**A regra desta frente, dita de novo:** a coleta que sai vazia **sem reclamar** é o defeito.
Vale para `excludes` (`modulos_vivos.json`), para o torchvision (`binarios_do_torchvision`) e
agora para a biblioteca padrão.

---

## 4. As licenças — o portão que tira o build do "uso próprio"

O ciclo 1 fechou com: *"faltam os textos das licenças dentro do pacote; até isso ser feito, o
build é para uso próprio"*. Reunir os arquivos foi metade do trabalho; a outra metade é o
portão, sem o qual a próxima dependência entra sem texto e ninguém fica sabendo.

### 4.1 O que existe, medido

`packaging/licenses/` — **99 arquivos, 2 MB**, e viaja inteira em `_internal/licenses/`:

| | |
|---|---|
| `AGPL-3.0.txt`, `GPL-3.0.txt`, `LGPL-3.0.txt` | os três textos integrais |
| 21 pastas por distribuição | o arquivo de licença que **aquela** distribuição publica |
| `TERCEIROS.md` | o aviso consolidado, com as cinco obrigações |
| `PECAS_CBURNETT.md` / `PECAS_PROCEDENCIA.md` | a arte das peças: a atribuição, e por que mudou |
| `INDICE.json` | o índice legível por máquina |

**As 21 cobrem as duas metades da entrega:** 12 que viajam em `_internal/` e **9 que o
assistente instala em `runtime/`** — torch, torchvision, sympy, networkx, filelock, fsspec,
Jinja2, MarkupSafe, mpmath. Uma coleta que olhasse só para o instalador deixaria essas nove
de fora e diria "tudo certo". A obrigação acompanha o que o programa **entrega**, não o que o
`setup.exe` carrega.

Estado medido: `sem_texto: []`, `nao_encontradas_no_ambiente: []`.

### 4.2 O portão

`test_toda_dependencia_distribuida_tem_texto_de_licenca` reprova se `INDICE.json` listar
qualquer distribuição sem texto. Enquanto ele estiver verde, **o pacote pode ser entregue a
terceiros sob AGPL-3.0-or-later** — o que no ciclo 1 não podia.

### 4.3 Um defeito de ordem, encontrado alternando as duas variantes

`preparar_licencas_e_pecas()` roda **antes** do PyInstaller — e tem de rodar, porque os textos
entram no bundle como `datas`. Mas `coletar_licencas._topos_do_toc()` lê os `.toc` de
`build/`, que naquele instante ainda são os do build **anterior**. Depois de montar
`com-torch` e em seguida a padrão, o inventário da padrão saiu afirmando:

```
torch | bundle | ['functorch', 'torch', 'torchgen']
```

O bundle padrão não leva torch. O texto da licença estava lá — o portão de `sem_texto`
segurou — mas **o documento afirmava algo falso sobre o conteúdo do pacote**, e um inventário
de licença que erra o que está dentro é um inventário que ninguém pode usar.

Conserto: `conferir_licencas_do_bundle()` refaz a coleta **depois** do PyInstaller, com o
`.toc` fresco, e compara com a cópia que viajou dentro do bundle. Divergindo, o build falha e
pede outro; a segunda passagem converge. No build final: *"Inventario de licencas confere com
o bundle: 21 distribuicoes."*

### 4.4 A versão declarada para o que chega em `runtime/`

Um segundo erro de precisão, do mesmo tipo. A versão de cada distribuição vinha de
`importlib.metadata` do venv de **empacotamento** — e para as nove que chegam em `runtime/`
essa não é a versão que o usuário recebe: ele recebe a roda que a GPU dele pedir. O
`TERCEIROS.md` declarava `torch 2.14.0+cpu` para quem instala `2.11.0+cu128`.

Agora o índice guarda `versoes_por_variante` para essas nove, lido do `torch_manifesto.json`,
e a tabela mostra as duas quando elas diferem:

```
| torch       | 2.14.0+cpu (cpu) ou 2.11.0+cu128 (cu128) | Apache-2.0 AND ... |
| torchvision | 0.29.0+cpu (cpu) ou 0.26.0+cu128 (cu128) | BSD                |
| sympy       | 1.14.0                                   | BSD                |
```

`sympy` aparece com uma versão só porque as duas rodas trazem a mesma; repetir
`1.14.0 (cpu) ou 1.14.0 (cu128)` para o que não muda tornaria a coluna ilegível sem
acrescentar informação.

### 4.5 `LICENSING.md` e `pyproject.toml` agora dizem a mesma coisa

O ciclo 1 registrou a divergência (o `pyproject.toml` declarava `LGPL-3.0-or-later`, o que
era falso com PyMuPDF AGPL no conjunto) e a deixou aberta, por não ser arquivo daquela
frente. A coordenação corrigiu para **`AGPL-3.0-or-later`**; o `LICENSING.md` foi reescrito
para descrever o estado atual em vez do antigo, e
`test_o_licensing_concorda_com_o_pyproject` existe para que a próxima divergência apareça num
teste vermelho e não na leitura de quem for redistribuir.

**O que a AGPL-3.0-or-later exige de quem distribuir este build** — as cinco obrigações que
`TERCEIROS.md` repete dentro do pacote:

1. **Entregar o código-fonte correspondente** — o do Caïssa e o das bibliotecas copyleft — ou
   uma oferta escrita e válida de obtê-lo, junto com o binário. *Correspondente* quer dizer o
   fonte **daquele** build, não o do repositório em outra data.
2. **Manter os avisos de copyright e os textos das licenças** dentro do pacote instalado.
3. **Licenciar o conjunto sob AGPL-3.0-or-later**, e não sob termos mais restritivos.
4. **Não impedir a modificação e a reinstalação** pelo usuário.
5. **§13:** se o programa **modificado** for oferecido por rede, o fonte vai para os usuários
   desse serviço — mesmo sem distribuir binário nenhum.

Isso vale para **quem entrega o arquivo**, não para o dono do projeto: um `.zip` do
`dist/Caissa/` enviado a um colega já é distribuição.

### 4.6 As peças

O bundle leva o conjunto **cburnett** (Colin M. L. Burnett, GPL-2.0-or-later, redistribuído
sob GPL-3.0), rasterizado dos SVG originais por `packaging/gerar_pecas_livres.py`. Conferido
no disco:

```
wk.png  no bundle    0a17c2acfcbe5071...
wk.png  em packaging 0a17c2acfcbe5071...   <- o mesmo arquivo
wk.png  no tronco    5fdf265e56a4f5f5...   <- outra arte, NAO distribuida
```

A investigação que levou a essa troca é do meu antecessor e está em
`packaging/licenses/PECAS_PROCEDENCIA.md`. Não a refiz e não a resumo aqui além do
necessário: ela mediu que os 12 PNG do tronco são a mesma arte que o único documento de
atribuição disponível atribui à Chess.com, *"All rights reserved"* — e foi explícita sobre o
que **não** estabeleceu.

---

## 5. O auto-teste, do bundle final

```
[ OK  ] Auto-teste
         codigo 0 - a instalacao le um diagrama (5.2 s)
         19:13:05 INFO app_pyqt:   diagrama 1: 4k2r/8/8/3p4/3P4/8/8/R3K3
                                   | conf min 0.804 | legal
         19:13:05 INFO app_pyqt: Auto-teste concluido: 1 diagrama(s) reconhecido(s).
         19:13:06 INFO app_pyqt: Auto-teste: o caminho de treino tambem montou.
         19:13:06 INFO app_pyqt: Auto-teste: classificador de caracteres -- presente.
         19:13:06 INFO app_pyqt: Auto-teste: as 3 peles registradas montam o cromo.
```

O PDF de prova é desenhado na hora, com os PNGs **do bundle** — de modo que ele prova de
quebra que os `datas` são encontráveis em execução e que as peças `cburnett` são reconhecidas
pelo classificador treinado com as outras. O assistente inteiro terminou com **código 0**.

### 5.1 Um defeito medido e consertado nesta sessão: o auto-teste que pendurava

Rodando o assistente num bundle recém-construído, **sem os pesos**:

```
[FALHA] Classificador de casas (pecas)   ausente
[FALHA] Auto-teste                       nao terminou
        TimeoutExpired: ... timed out after 300.0 seconds
```

**Cinco minutos** para descobrir o que a linha de cima já tinha dito. E pior do que perda de
tempo: a última linha do relatório vira um tempo limite, que é o sintoma de "o programa
travou" e não o de "falta um arquivo".

Agora o assistente não roda um teste que não pode passar. Medido, no mesmo estado:

```
[INFO ] Auto-teste
         nao rodado
         Ele carrega um `.pt` e nao passaria sem ele -- ficaria pendurado ate o tempo
         limite de 300 s. Resolva o que esta em FALHA acima (Classificador de casas
         (pecas)) e rode o assistente de novo.
```

**300 s → 4 s**, e uma frase no lugar de uma espera.

---

## 6. A pendência 0001 entrou, e o teste que a vigia está verde

`packaging/pendencias/0001-torch-fora-do-escopo-de-modulo.patch` foi escrito pelo meu
antecessor e **aplicado no tronco durante esta sessão** por outra frente. A regra da pasta é
que cada pendência tenha um teste que fique vermelho até o conserto entrar; esse teste
faltava, e agora existe:

```
tests/integration/test_packaging.py::TestPendencias::test_a_janela_do_tronco_importa_sem_torch
```

Ele importa `chess_diagram_ocr.qt.janela` num subprocesso do `.venv-pack` com o torch
bloqueado por um `MetaPathFinder` — que é exatamente o ambiente do usuário entre instalar e
rodar o assistente. Medido hoje:

```
import chess_diagram_ocr.qt.janela                    ->  ok
controle: import chess_diagram_ocr.dataset           ->  ModuleNotFoundError: 'torch'
controle: import chess_diagram_ocr.training          ->  ModuleNotFoundError: 'torch'
```

O controle negativo é parte do teste e não um enfeite: sem ele, um bloqueio que não bloqueia
faria a asserção passar sozinha. `dataset` e `training` definem classes que herdam de
`Dataset`/`nn.Module` no escopo de módulo — eles **devem** continuar exigindo torch. O que
mudou é que **abrir a janela deixou de importá-los**.

---

## 7. Os testes

`tests/integration/test_packaging.py`: **96 testes, 96 passando, 0 pulados** (o ciclo 1
tinha 52). O que entrou neste ciclo, por classe:

| classe | o que afirma |
|---|---|
| `TestBibliotecaPadraoDoTorch` (9) | os 178 módulos, os três nomes que derrubaram o `.exe`, que todo nome medido importa, que a spec pede a lista nos dois executáveis e **recusa montar sem ela**, as 17 extensões nativas, e o portão exercido contra um bundle furado |
| `TestTorchDePrimeiraExecucao` (15) | manifesto válido, https e SHA-256 em toda roda, recusa de URL http, escolha de variante para `sm_120` / sem GPU / `sm_61` / capacidade desconhecida, os dois números de velocidade, o caminho offline, as duas recusas de `obter_roda`, a marca do que foi instalado, e que o torch **não** está em `_internal/` |
| `TestLicencas` (10) | o índice datado, **toda dependência distribuída com texto**, cada arquivo do índice no disco, as 9 do `runtime/` cobertas, os três textos integrais completos, a arte das peças, `LICENSING.md` ↔ `pyproject.toml`, as cinco obrigações escritas, e os textos **dentro** do bundle |
| `TestCoerenciaDoInventario` (4) | que o inventário descreve **aquele** pacote: o de dentro igual ao de fora, o que ele diz estar no bundle está, e as 9 de `runtime/` não estão |
| `TestPendencias` (2) | a janela do tronco importa sem torch, com controle negativo |
| `TestOAssistenteNaoEspera` (1) | o auto-teste não é chamado quando falta componente obrigatório |

**Seis testes do ciclo 1 descreviam um produto que não existe mais.** Quatro reprovavam ao
começo desta sessão e dois passavam pulando — que é a forma mais silenciosa de um teste
envelhecer. Todos foram reescritos, e nenhum removido:

| teste | o que ele afirmava | o que afirma agora |
|---|---|---|
| `..._a_unica_que_exclui_o_torch` | que só a variante `leve` excluía torch | que a **distribuída** é a que exclui, e nomeia as seis bibliotecas que saíram junto |
| `os_nomes_de_variante_batem...` | `Caissa-leve` no `.iss` | `Caissa-com-torch` |
| `as_pastas_do_usuario_sobrevivem...` | cinco pastas | **seis** — `runtime/` entrou, e é a mais cara: até 4,3 GB baixados pelo usuário |
| `o_tamanho_medido_esta_gravado...` | somava `runtime/` ao bundle (4.562 MB contra 295 gravados) | ignora o que o usuário baixou |
| `a_variante_leve_cabe_no_teto` | *pulava* se `bundle-leve.json` sumisse | exige que **a variante distribuída** caiba |
| `o_torchvision_levou_a_extensao_nativa` | *pulava* — "build leve: não leva torchvision" | procura o torchvision onde ele estiver: `_internal/` ou `runtime/` |

`TestTeto::test_a_variante_que_se_distribui_cabe_no_teto` é o que o ciclo 1 não podia ter:
lá quem cabia no teto era a variante que **não abria** — um teste verde sobre um produto
inexistente.

**Portão de não-regressão da suíte inteira**, rodado ao fim desta sessão:

```
> .venv\Scripts\python.exe -m pytest tests/ -q --timeout=900
3145 passed, 1 skipped in 826.87s (0:13:46)
```

O ciclo 1 fechou em `3022 passados / 1 pulado`; o único pulado continua sendo o mesmo, e não
é desta frente: WOFF2 sem o compressor Brotli, em `tests/unit/typeset/test_fonts.py`.

`ruff check` e `ruff format --check` limpos em `packaging/` e no arquivo de teste. As **28
pendências de lint** que o `packaging/` acumulava foram pagas — não com `# noqa` genérico:
duas constantes nomeadas onde havia número mágico, um `with` composto, um `Path.parts` no
lugar de `split(os.sep)`, quebras de linha, e **um** `noqa` de arquivo no
`runtime_hook_torch.py`, com a razão escrita (ele roda no bootloader, antes de existir
logger, e `pathlib` ali só põe mais um módulo na frente do primeiro `import torch`).

---

## 8. O que **não** foi verificado

Esta seção existe porque as coisas abaixo são as que quebram na máquina de outra pessoa.
As quatro primeiras vêm do ciclo 1 **e continuam valendo**.

1. **O instalador nunca foi compilado.** O Inno Setup continua ausente desta máquina
   (procurei em `C:\Program Files\Inno Setup 6`, `C:\Program Files (x86)\Inno Setup 6` e no
   `PATH`). Os **79,4 MB** são um **proxy medido**: um `.7z` LZMA2 sólido da `dist/`, que é
   literalmente a compressão que o `[Setup]` pede (`Compression=lzma2/max`,
   `SolidCompression=yes`). O `setup.exe` real acrescenta o stub do Inno (~1,2 MB) e os
   arquivos de idioma. O arquivo diz isso, o JSON diz isso, e um teste afirma que dizem.
   **Com 70,6 MB de folga, o stub não ameaça o teto — mas ninguém viu o `.iss` compilar.**

2. **Não há assinatura de código.** Os dois `.exe` são não assinados; o SmartScreen vai
   avisar em qualquer máquina que não seja esta. Exige um certificado, que é uma decisão e
   uma despesa do dono do projeto.

3. **Nunca rodou numa máquina Windows limpa, sem Python.** Tudo aqui foi executado na máquina
   que tem cinco Pythons, o CUDA, o tronco e os venvs. O `--onedir` é feito para isso e
   `_internal/` carrega `python311.dll` — mas a afirmação "roda numa máquina sem Python"
   continua sendo a promessa do PyInstaller, não uma medição desta frente.

4. **O download dos *pesos* nunca tocou a rede.** `manifesto.json` tem `base_url: null`
   porque não há servidor publicado; os pesos chegam por `--de-pasta`. **O que mudou neste
   ciclo é que o download do *torch* tocou a rede** — 2,6 GB de `download.pytorch.org`,
   verificados e desempacotados. Os dois caminhos usam a mesma máquina de verificação; só um
   dos dois foi exercido de ponta a ponta contra um servidor.

5. **O caminho offline do cu128 (2,6 GB) não foi rodado.** O `--rodas-de` foi exercido com as
   rodas de **CPU** (129 MB). O código é o mesmo — `obter_roda(origem=...)` não distingue
   variante — e as duas recusas têm teste; mas a cópia de 2,6 GB em si não foi executada.

6. **Só uma GPU foi testada.** `sm_120` real. Os outros três ramos de `escolher_variante()`
   (sem GPU, `sm_61`, driver que não declara `compute_cap`) são testes de unidade contra a
   função, e não máquinas.

7. **Ressalva sobre as instalações com `--raiz`.** Nas execuções que instalaram em pasta
   temporária, o `runtime_hook_torch.py` já havia posto o `runtime/` **do bundle** em
   `sys.path` na inicialização do `.exe` — de modo que a linha `[ OK ] GPU` daquelas
   execuções reflete o cu128 do bundle, e não a roda recém-instalada na pasta temporária. O
   que aquelas execuções mediram, e é o que está citado aqui, foi a **instalação**: bytes,
   hash, desempacotamento e tempo.

8. **O bundle `com-torch` foi apagado depois de medido** (731,6 MB + 169,5 MB de `.7z`), por
   disco. Os números sobrevivem em `packaging/bundle-com-torch.json`; refazê-los é
   `build_windows.py --com-torch --instalador`, ~6 min.

9. **`packaging/bundle-leve.json` foi removido.** Ele media uma variante que a spec não produz
   mais (a `leve` do ciclo 1). Os números dela continuam publicados no `F12_REPORT.md`; um
   arquivo de métricas de uma variante inexistente é o tipo de artefato que engana leitor.

10. **A janela não foi aberta nesta sessão.** O ciclo 1 capturou `F12_janela_do_bundle.png`
    com um livro carregado; aqui o que foi exercido é o `--selftest` (que dirige a mesma
    janela em modo `offscreen`) e o assistente. A captura do ciclo 1 continua sendo a única
    prova visual, e é de um bundle anterior.

---

## 9. Diário de disco (SPEC R4)

| momento | GiB livres em C: |
|---|---:|
| início da sessão | **34,26** |
| antes de baixar o cu128 | 34,35 |
| durante o download | 32,42 |
| desempacotando o cu128 (o vale) | **29,41** — o assistente reportou 27,6 GB no seu próprio passo de disco |
| depois de apagar o `runtime/` antigo | 31,79 |
| depois de apagar as 10 rodas guardadas (`runtime/.rodas`, 2.644 MB) | 34,29 |
| 1º build da variante padrão | 34,28 → 34,29 |
| build `com-torch` | 34,20 → **33,03** |
| depois de apagar o bundle `com-torch` e o `.7z` dele | 33,88 |
| 2º build padrão (após o portão de extensões nativas) | 33,88 → 33,84 |
| 3º build padrão (após o portão de coerência do inventário) | 33,89 → 33,90 |
| 4º build padrão (após a formatação) | 34,01 → 33,99 |
| 5º e último build padrão (com os documentos de licença corrigidos) | 33,94 → 33,92 |
| **fim da sessão** | **33,98** |

*(As linhas de build são as que o próprio `build_windows.py` grava em `bundle.json`; as
demais são `Get-PSDrive C`.)*

**Consumo líquido: −0,28 GiB**, tendo passado por 2,6 GB de download, 4,3 GB de
desempacotamento, **cinco** builds da variante padrão e um da `com-torch`. O
`build_windows.py` recusa começar com menos de 6 GB livres e grava antes/depois em cada
`bundle.json`.

Uma nota de método que vale registrar: o PyInstaller **apaga `dist/Caissa` inteira** antes de
montar (`INFO: Removing dir ...\dist\Caissa`). Em todos os builds desta sessão o
`runtime/` — 4,3 GB que o usuário baixou — foi movido para fora e devolvido depois. Numa
instalação real isso não acontece, porque o `[InstallDelete]` do `.iss` apaga só `_internal`
e `runtime/` está declarado `uninsneveruninstall`; mas quem reconstruir aqui precisa saber,
e há teste afirmando as duas coisas do lado do `.iss`.

---

## 10. O que fica aberto para o ciclo 3

1. **Compilar o instalador de verdade.** É a lacuna mais antiga desta frente e agora é a
   única entre "medido" e "entregável". Instalar o Inno Setup 6 e rodar
   `build_windows.py --instalador` fecha o item 1 da §8 — o `.iss` está escrito e cada
   caminho que ele cita tem teste afirmando que existe.
2. **Rodar numa VM Windows limpa.** Copiar `dist/Caissa/` e rodar
   `CaissaPrimeiraExecucao.exe`. É o único teste que responde "roda sem Python?".
3. **`cv2`, 100,4 MB, um terço do pacote.** Com o torch fora, virou o maior item. Não é desta
   frente decidir, mas a medição agora aponta para lá.
4. **Um servidor para os pesos.** `base_url: null` é honesto e é uma lacuna; o torch mostrou
   que a máquina de verificação funciona contra a rede.
5. **A degradação na janela.** Com a pendência 0001 aplicada, a janela **abre** sem torch. O
   passo seguinte — o botão de reconhecer dizer *"instale o PyTorch pelo assistente"* em vez
   de levantar `ModuleNotFoundError` — é em `qt/`, e o padrão a copiar é da própria suíte:
   `src/caissa/vision/runtime/device.py::import_torch()`.
