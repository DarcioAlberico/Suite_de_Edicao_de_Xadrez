# Caïssa Studio

Suíte profissional de **edição, reconhecimento e publicação** de material de xadrez, para
Windows, 100 % offline.

Ela transforma acervos heterogêneos — PDFs de qualidade variável, bases PGN de vários
gigabytes, digitalizações antigas, EPUBs — em documentos editáveis, pesquisáveis e
republicáveis em **PDF, DOCX, EPUB, HTML e LaTeX**.

O diferencial está em como o material é representado: um diagrama não é tratado como uma
*imagem*, mas como uma **posição** (FEN + proveniência + estilo); e o documento não é uma
sequência de páginas, mas uma **árvore semântica** da qual todos os formatos de saída são
renderizados. É isso que permite reflow em EPUB, diagramas vetoriais nítidos em qualquer
zoom, busca por posição dentro do livro, troca global da fonte de xadrez e tradução de
notação (`Nf3` ↔ `Cf3` ↔ figurino) sem redigitar nada.

A especificação completa está em [`docs/SPEC.md`](docs/SPEC.md); as decisões
arquiteturais vinculantes, em [`docs/adr/README.md`](docs/adr/README.md); o plano de
execução, em [`docs/ROADMAP.md`](docs/ROADMAP.md).

> **Estado atual (2026-09-11):** as quinze frentes do `ROADMAP.md` têm pelo menos um ciclo
> fechado. A última a começar, a ingestão de PDF (F2), fechou o seu em 2026-09-11 —
> `docs/quality/F2_REPORT.md`. Os relatórios por frente estão em `docs/quality/`.

---

## Requisitos de hardware

O projeto é dimensionado para a máquina de referência abaixo. Números menores funcionam,
mas o `doctor` vai avisar.

| Item | Mínimo | Referência (máquina de desenvolvimento) |
|---|---|---|
| Sistema | Windows 10 21H2 / Windows 11 | Windows 11 Pro build 26200 |
| Python | 3.11 (exatamente) | 3.11.9 |
| CPU | 4 núcleos | AMD Ryzen 5 8400F — 6C/12T |
| RAM | 16 GB | 31,6 GB |
| GPU | NVIDIA com CUDA; opcional, mas recomendada | GeForce RTX 5060 — 8 GB, sm_120 |
| Driver NVIDIA | 566+ (CUDA 12.8) | 591.86 |
| Disco livre | 20 GB | 76 GB |

### Por que **exatamente** Python 3.11

É a versão com cobertura completa de rodas binárias para PySide6, PyMuPDF, `onnxruntime` e
`torch` cu128. O 3.12+ ainda tem lacunas em partes da pilha, e o 3.10 fica para trás em
recursos de tipagem que o código usa.

### Por que a GPU precisa de CUDA 12.8

A RTX 5060 é Blackwell, *compute capability* **sm_120**. Rodas do PyTorch anteriores a
`cu128` **não contêm kernels** para essa arquitetura. O sintoma não é um erro claro: a
função `torch.cuda.is_available()` continua retornando `True` e a falha só aparece no
primeiro lançamento de kernel, como `no kernel image is available for execution on the
device` — ou, pior, como uma queda silenciosa para CPU. Por isso o `doctor` **executa uma
multiplicação de matrizes de verdade** em vez de confiar na consulta de disponibilidade.

---

## Instalação

```powershell
git clone <url-do-repositorio> Suite_de_Edicao_de_Xadrez
cd Suite_de_Edicao_de_Xadrez
.\scripts\setup_env.ps1
```

O script é **idempotente** — pode ser executado quantas vezes quiser. Ele:

1. localiza o Python 3.11;
2. cria o `.venv` (recriando-o se a versão estiver errada);
3. atualiza `pip`, `setuptools` e `wheel`;
4. instala o projeto em modo editável (`pip install -e ".[dev]"`);
5. instala o PyTorch a partir de `https://download.pytorch.org/whl/cu128` (cerca de 3 GB
   no primeiro uso — é normal demorar);
6. confere que o `onnxruntime-gpu` **não** está neste ambiente (ADR-0003);
7. executa o `scripts/doctor.py`.

### Grupos de dependências

O `pyproject.toml` declara seis grupos. O grupo *core* é instalado sempre; os demais são
extras opcionais:

```powershell
.\scripts\setup_env.ps1 -Extras "dev,vision"        # visão computacional
.\scripts\setup_env.ps1 -Extras "all"               # tudo, inclusive PySide6
.\scripts\setup_env.ps1 -Recreate                   # do zero
.\scripts\setup_env.ps1 -SkipTorch                  # sem GPU
```

| Grupo | Conteúdo |
|---|---|
| `core` | configuração, modelo de domínio, `python-chess` |
| `vision` | numpy, OpenCV (headless), Pillow, PyMuPDF, SciPy |
| `ocr` | Tesseract (binding), regex, rapidfuzz |
| `ui` | PySide6 |
| `export` | ReportLab, python-docx, EbookLib, lxml, Jinja2 |
| `dev` | ruff, mypy, pytest |

O **PyTorch não está em nenhum grupo**: as rodas `cu128` só existem num índice próprio,
que não pode ser declarado de forma portável no `pyproject.toml`. Quem o instala é o
`setup_env.ps1`.

O **onnxruntime também não**, e por outro motivo: a partir da versão 1.27 o pacote
`onnxruntime-gpu` do PyPI é compilado contra CUDA 13.0, enquanto as rodas Blackwell do
PyTorch usam CUDA 12.8. Carregar os dois no mesmo processo causa conflito de DLL ou queda
silenciosa para CPU. A solução adotada (ADR-0003) é rodá-lo num **processo trabalhador
separado**, com ambiente virtual próprio.

---

## Verificando o ambiente

```powershell
.venv\Scripts\python.exe scripts\doctor.py
```

O relatório cobre sistema, disco, Python, PyTorch, GPU, interoperabilidade e configuração.
Cada linha reprovada traz a **causa real** e a correção — não apenas "falhou".

A verificação central é a de GPU: o `doctor` aloca duas matrizes 4096 × 4096 em `float16`,
multiplica, sincroniza, cronometra e **confere o resultado numericamente** contra uma
referência calculada na CPU. Se houver queda silenciosa para CPU, ela é detectada e
apontada.

Opções úteis:

```powershell
# saída para consumo por outro programa
.venv\Scripts\python.exe scripts\doctor.py --json > report.json

# avisos passam a reprovar (útil em CI)
.venv\Scripts\python.exe scripts\doctor.py --strict

# máquina sem GPU: não reprova por causa dela
.venv\Scripts\python.exe scripts\doctor.py --allow-cpu

# ignora arquivos de configuração de usuário e de projeto
.venv\Scripts\python.exe scripts\doctor.py --isolated
```

Códigos de saída: `0` saudável · `1` requisito obrigatório reprovado · `2` o próprio
`doctor` falhou.

---

## Importando um PDF

```python
from caissa.ingest import import_pdf, PdfImportOptions
from caissa.ingest.pdf import combined_finder

# Camada de texto + diagramas vetoriais (fontes de xadrez), sem modelo nenhum:
resultado = import_pdf(r"C:\livros\Dvoretsky.pdf", PdfImportOptions(lang="eng"))
documento = resultado.document          # Document IR, com proveniência em cada nó
print(resultado.report.describe_pt())   # páginas, origem do texto, diagramas, tempo

# Com o detector raster do tronco e o classificador F4 na GPU (livros digitalizados):
resultado = import_pdf(
    r"C:\livros\Karpov.pdf",
    PdfImportOptions(pages=range(60, 70), diagram_finder=combined_finder()),
)
```

Uma página cuja camada de texto o nível 0 da F5 rejeita entra como imagem, com o motivo
na proveniência; `PdfImportOptions.ocr` recebe um `OcrProvider` para essas páginas.
`benchmarksench_ingest.py --dump` grava o IR de cada livro do acervo em texto, para a
leitura lado a lado.

## Desenvolvimento

```powershell
.\scripts\check.ps1              # ruff + mypy + pytest
.\scripts\check.ps1 -Fix         # aplica as correções automáticas do ruff antes
.\scripts\check.ps1 -Coverage    # com relatório de cobertura
```

As três portas de qualidade rodam sempre, mesmo que uma anterior falhe, para que um ciclo
mostre todos os problemas. O `mypy` roda em modo estrito completo sobre `caissa.core`.

### Configuração

A configuração é montada em camadas; a mais específica vence:

```
padrões  ->  arquivo do usuário  ->  variáveis de ambiente  ->  arquivo do projeto  ->  overrides
```

- **Arquivo do usuário:** `%LOCALAPPDATA%\CaissaStudio\caissa.toml` (ou `$CAISSA_CONFIG`).
- **Variáveis de ambiente:** `CAISSA_<SEÇÃO>__<CAMPO>`, por exemplo
  `CAISSA_RUNTIME__VRAM_BUDGET_GB=6.0`.
- **Arquivo do projeto:** `caissa.toml`, `.caissa.toml` ou a seção `[tool.caissa]` do
  `pyproject.toml`, procurados a partir do diretório de trabalho para cima.

Exemplo de `caissa.toml`:

```toml
[runtime]
vram_budget_gb = 6.0      # teto rígido de VRAM (ADR-0004)
device = "auto"           # auto | cuda | cpu

[cache]
page_cache_mb = 1024
model_weights_budget_gb = 6.0

[ui]
theme = "dark"
language = "pt_BR"
```

O `doctor` mostra de qual camada cada valor efetivo veio.

### Orçamento de VRAM

São 8 GB de VRAM disputados por detector, classificador, OCR e LLM — a soma dos picos não
cabe. Por isso nenhum subsistema chama `.to("cuda")` diretamente: os modelos são
declarados num registro com custo de VRAM e emprestados através do
`ModelResidencyManager`, que faz carga sob demanda, despejo LRU, teto rígido de 7,0 GB e
queda para CPU com aviso quando o despejo não basta.

```python
from caissa.vision.runtime import ModelResidencyManager, ModelSpec, gigabytes

manager = ModelResidencyManager()
manager.register(
    ModelSpec(
        name="square-classifier",
        vram_bytes=gigabytes(0.4),
        loader=lambda device: load_classifier(device),
        description="Classificador de casas",
    )
)

with manager.acquire("square-classifier") as lease:
    logits = lease.model(batch)

print(manager.budget_report().to_text())
```

### Estrutura

```
src/caissa/
  core/config/            configuração em camadas, validada e imutável
  vision/runtime/         seleção de dispositivo e orçamento de VRAM
  vision/ ocr/ export/    subsistemas (frentes F2–F8)
  ui/                     interface PySide6 (frente F9)
scripts/
  setup_env.ps1           preparação do ambiente
  doctor.py               relatório de saúde
  check.ps1               lint + tipos + testes
tests/unit/               testes rápidos, sem I/O
docs/                     SPEC, ROADMAP e ADRs
```

---

## Licença

LGPL-3.0-or-later, acompanhando a licença do PySide6 (ADR-0001).
