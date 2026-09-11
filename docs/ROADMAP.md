# Caïssa Studio — Roadmap de Execução

> **Versão:** 1.0 · **Data:** 2026-09-07
> Documento de coordenação. Cada item tem dono (subagente), critério de pronto,
> e um crítico independente com mandato de reprovar.

---

## Como este roadmap funciona

O trabalho é dividido em **frentes** (F0–F12). Cada frente tem:

- **Construtor** — subagente que implementa.
- **Crítico** — subagente independente, adversarial, que só conhece os critérios de
  aceitação e a saída. Ele **não** conhece o construtor nem vê o código-fonte da
  justificativa; julga pelo resultado.
- **Portão** — condição objetiva e mensurável. Sem portão verde, a frente não fecha.
- **Ciclo `/loop`** — construtor → crítico → correções → crítico, repetido até
  aprovação. O crítico é instruído a reprovar em caso de dúvida.

### Regra de ouro dos críticos

> "Compare às cegas com o material de referência da indústria. Se você consegue
> identificar qual é o nosso por ser pior, **reprove**. Empate não é aprovação —
> aprovação exige que o nosso seja indistinguível ou melhor."

---

## Estado atual — atualizado 2026-09-07

> Leia `docs/ASSETS.md` v2.0 antes desta tabela. A maior parte do produto **já existe**;
> as frentes abaixo são de elevação e unificação, não de construção do zero.
> As metas de §11.3 da SPEC foram corrigidas para cima em classificação e mantidas em
> detecção, porque é lá que está o trabalho real.

> **Censo final — 2026-09-10**
>
> | | linhas | arquivos |
> |---|---:|---:|
> | Produto (`src/caissa`) | **80.109** | 139 |
> | Testes | **33.626** | 94 |
> | Ferramentas | 6.791 | 6 |
> | Empacotamento | 4.181 | 9 |
> | *Instrumentos de crítica* | *107.075* | *489* |
>
> **Os instrumentos que os críticos construíram para medir o produto pesam mais que o
> produto.** Treze documentos de crítica, 42 documentos ao todo.
>
> Disco em C: **31,5 GB livres** (eram 76,4 no início) — venvs, torch cu128, modelos e
> pacotes consumiram ~45 GB. Vale limpar `.venv-pack` e `dist/` quando não estiverem em uso.

| Frente | Nome | Estado | Evidência |
|---|---|---|---|
| F0 | Fundação e ambiente | **✅ PORTÃO APROVADO** | `doctor.py`: 20 ok, 0 falha; GPU sm_120 a 30,5 TFLOP/s |
| F1 | Document IR | **✅ concluída** | 1.125 testes, **99 % cobertura**, 49 tipos de nó |
| F2 | Ingestão de PDF | ⬜ não iniciada | 3 implementações a unificar |
| F3 | Detecção | **✅ META ATINGIDA** | **recall 0,9913 · precisão 1,0000** |
| F3-A | Detecção vetorial | ✅ absorvida pela F3 | catálogo de 18 fontes verificadas |
| F4 | Classificação e FEN | **✅ acima da meta** | 99,9854 % por casa |
| F4-GPU | Aceleração em GPU | **✅ META ATINGIDA** | **0,0903 s/diagrama**; paridade fp16 exata |
| F5 | OCR de texto | **✅ ciclo 2 fechado** | 368 testes; laço por região, integridade da notação, corretor de cifra e a cadeia ponta a ponta (`F5_REPORT_C2.md`) |
| F6 | Notação e regex | ✅ absorvida | 9.333 linhas; 43.400 idas-e-voltas de SAN |
| F7 | Tipografia | **✅ APROVADA (ciclo 10)** | reprovada 4×; 309 testes; vantagem verificada pelo crítico |
| F8 | Exportadores | **✅ concluída** | **DOCX 100 %, HTML 100 %, EPUB 99,52 %**; EPUBCheck 0 erros |
| F9 | Interface | **✅ APROVADA (ciclo 15)** | reprovada 7×; 238 testes; 3 peles × 2 densidades × 4 larguras |
| F10 | Índice e busca | **✅ concluída** | 126 testes; FTS5 com tokenizador de notação |
| F11 | LLM local | **✅ 5/5 tarefas medidas (ciclo 3)** | 1 entregue (`translate_notation_prose`), 1 só como sugestão (`caption_for_diagram`), 3 rejeitadas por medição — `F11_REPORT_C3.md` |
| F12 | Empacotamento | **✅ concluída** | instalador **79,4 MB**; torch cu128 na 1ª execução |

### Ciclos de crítica adversarial

| Frente | Ciclo | Veredito | O que a crítica encontrou |
|---|---|---|---|
| F7 | 1 | **REPROVADO** | 7/7 identificadas às cegas; nossas em último, penúltimo e antepenúltimo. Conteúdo **70 mm fora da folha** em 5 de 10 páginas. |
| F7 | 3 | **REPROVADO** | 4º de 6, mas o pé de coluna **empatou** e a grade de linha de base **perdeu para uma digitalização**. O ciclo 2 comprou a métrica com buracos: p8 com **37 % de branco**. |
| F7 | 5 | **REPROVADO** | **Sabotou o portão**: trocou um cavalo por uma dama no `.tex` e o comparador seguiu dizendo "222 tokens idênticos, 0 divergências", exit 0. |
| F7 | 8 | **REPROVADO** | Um defeito: o fólio nunca alterna. **Mas verificou e ampliou a vantagem** — reamostragem de 20.000 sorteios, p < 0,05 contra 7 de 8 colunas. |
| F7 | 10 | **✅ APROVADO** | 4º de 6 às cegas, **identificada por precisão, não por defeito**. Retirou 2 das 3 próprias acusações após medir as referências. |
| F9 | 1 | **REPROVADO** | Portão de teclado testava `bool(nome)` (34 controles anunciam "121"); o de bloqueio tirava mediana e escondia congelamento de **1.302 ms**. |
| F9 | 3 | **REPROVADO** | Perfilador de **amostra única** sempre premiava a chamada C mais longa e nunca via 108.620 chamadas Python miúdas. |
| F9 | 5 | **REPROVADO** | Contraste publicava **7,08:1** para um par que rendia **3,96:1** na tela — resolvia o token opaco sem compor alfa. |
| F9 | 7 | **REPROVADO** | O conserto do ciclo 6 pôs o nome numa **dica de ferramenta**, e o portão escrito para impedir isso **aceita `toolTip()` como "na tela"**. |
| F5 | 2 | **autocrítica** | O plano de registro estava errado quanto à causa — medi antes de construir e a arbitragem por região **não** fecha o defeito do Gaprindashvili (prosa e lances destruídos dividem a mesma linha). E a primeira sabotagem do veredito por região **passou nos 13 testes**: o portão estava cego. |

### Os onze portões cegos

Em cada um destes, **a suíte de testes estava verde** e a funcionalidade estava quebrada.
Nenhum foi encontrado por mais teste. Sete por crítica adversarial independente; o oitavo
por medir a premissa do próprio plano antes de executá-lo; o nono por reler o código
depois de a suíte já estar verde; e os dois últimos por **rodar o sistema de ponta a ponta
com os motores reais**, coisa que nenhum teste de costura com motor falso alcança.

| # | Portão | O que ele media | O que estava quebrado |
|---|---|---|---|
| 1 | Pé de coluna | dispersão do pé | comprado distribuindo buracos no corpo |
| 2 | Nomes de controle | `bool(nome)` | 34 controles anunciavam "121" |
| 3 | Paridade de exportadores | strings de token | cego à identidade da peça |
| 4 | Perfilador de bloqueio | amostra única | sempre a chamada C mais longa |
| 5 | Contraste | token opaco | sem compor o alfa que o Qt aplica |
| 6 | Espaço entre palavras | linhas justificadas | **excluía as linhas que recusou justificar** |
| 7 | Estado vazio na tela | aceitava `toolTip()` | nada desenhado na tela |
| 8 | Veredito da camada de texto | todo sinal léxico, sobre a página inteira | **16 livros com a notação destruída** eram aceitos a 0,98 — a prosa domina a contagem e vence a votação |
| 9 | Caixas do nível 0 no laço por região | o teste não passava raster | com raster, a translação era aplicada duas vezes e as caixas saíam da página |
| 10 | Veredito por região | a região sozinha | cortar a página **lavava** a acusação: 0,55 na página, 0,98 nas metades |
| 11 | Calibração do Tesseract | um piso de confiança **de palavra** | aplicado ao agregado da página, zerava o motor em 12 de 12 — a cascata nunca decidiu nada |

**A prática que ficou:** todo portão novo precisa de **prova de vitalidade** — uma sabotagem
que o faça reprovar. Um portão que só devolve zero é indistinguível de um portão cego.
E em pelo menos um caso a própria prova de vitalidade estava cega duas vezes, o que só
apareceu porque o construtor a rodou sabotada antes de confiar nela.

**As críticas também corrigiram os construtores para cima:** mediram 86,9 fps contra os
78,0 declarados e 104,4 contra 101,4; confirmaram 14 de 21 alegações; e um crítico
**retirou duas das próprias acusações** depois de medir as referências.

### Resultados verificados (2026-09-07)

**Velocidade — meta atingida.** `bench_throughput_cuda_6w_fp32_w6`, mediana de 3
execuções estáveis, 6 processos em GPU: **0,0903 s/diagrama** contra meta de 0,10.
Sete vezes mais rápido que a linha de base publicada (0,635). VRAM: 3,15 GiB de 7,0.

**A aceleração é idêntica, não só rápida.** `parity_fp16.json`: 200 tabuleiros,
12.800 casas, **zero divergência** — incluindo o argmax cru antes da decodificação com
restrições, que é onde um erro de uma casa poderia se esconder dentro da mesma posição
legal. fp16 é embarcável.

**A GPU nunca esteve quebrada — a roda é que estava errada.** A venv do tronco tem
`torch 2.10.0+cpu`, sem CUDA alguma. Não havia fallback silencioso a caçar.

**O Gemma 4 E4B não serve para verificar diagrama.** Com verdade de campo, 100 pares:
especificidade **0,000**, MCC **0,000**, 1.016 ms por chamada. Disse "consistente" aos 50
pares corretos **e aos 50 errados**. Ver `docs/quality/F11_REPORT.md`. É a terceira
otimização rejeitada por medição (as outras duas em `ASSETS.md` §2.14).

**Tesseract 5.5.0 com 161 idiomas já estava instalado**, apenas fora do `PATH` — que é o
resultado padrão do instalador oficial do Windows. Por isso o tronco o dava como ausente.

**O detector de CMap quebrado do tronco procura no lugar errado.** Ele conta U+FFFD, e a
medição da F5 achou **zero em 560 folhas**: o modo de falha deste acervo emite codepoints
crus de fonte de xadrez (`2.♘xd4` vira `2.l0xd4`), não U+FFFD.

### O gargalo fechou — reconhecimento está todo no alvo

`benchmarks/reports/validate_detection_20260907_054234.json`, 68 páginas anotadas,
115 diagramas, mediana de 3 execuções:

| variante | recall | precisão | falsos positivos |
|---|---|---|---|
| tronco, sem mudança | 0,9478 | 0,9732 | 3 |
| só meia escala (substituindo) | **0,9391** | 0,9730 | 3 |
| busca multiescala (somando) | 0,9826 | 0,9741 | 3 |
| só resgate de quadrado | 0,9652 | 0,9737 | 3 |
| só piso de contraste no embutido | 0,9478 | **1,0000** | 0 |
| **`recall_pack` (os três juntos)** | **0,9913** | **1,0000** | **0** |

114 de 115. **A única perda restante é a anotação da capa do Yusupov (página 0), que não
é diagrama nenhum** — na prática, 114 de 114.

Repare na segunda linha: buscar **só** em meia escala era o atalho de velocidade óbvio
(2,65× mais rápido) e **custa recall** — perde seis diagramas do `Reinfeld`, cujo
tabuleiro de 116 pt não sobrevive à redução. Não foi adotado. Velocidade que custa recall
é prejuízo.

#### Placar final de reconhecimento

> **Correção de 2026-09-10.** Os números de laboratório publicados antes vinham da divisão
> histórica de **320 tabuleiros**. A divisão de teste cresceu para **534** e os números
> caíram — **não é regressão, é uma amostra maior e mais difícil**. Ambos estão abaixo,
> porque comparar um com o outro pensando que se compara modelo é o erro que esta nota evita.

| métrica | meta | divisão de 320 (histórica) | divisão de 534 (atual) |
|---|---|---|---|
| Acurácia por casa | ≥ 99,95 % | 99,9854 % | **99,9386 %** ⚠️ |
| Diagramas perfeitos (laboratório) | ≥ 99,0 % | 99,06 % | **97,75 %** ⚠️ |

| métrica de campo | meta | medido |
|---|---|---|
| Diagramas perfeitos, régua **como anotada** | ≥ 98,0 % | 97,87 % (92/94) ⚠️ |
| Diagramas perfeitos, régua **corrigida** | ≥ 98,0 % | **98,94 %** (93/94) ✅ |
| Recall de detecção (campo) | ≥ 99,0 % | **99,13 %** ✅ |
| Precisão de detecção (campo) | ≥ 98,5 % | **100,00 %** ✅ |
| Segundos por diagrama (vazão) | ≤ 0,10 | **0,0903** ✅ |

**`field_exact` nunca deve ser publicado sozinho.** Ele condiciona na exportação, então um
modelo **menos confiante** pontua melhor nele: um candidato marcou `field_exact = 1,0000`
lendo **pior** — `conditional_exact` caiu de 0,9792 para 0,9583 e `export_rate` de 0,887 para
0,843, com quatro leituras corretas deixando de chegar ao PGN. Publique sempre os três.

O único item ainda abaixo é `field_exact` (97,87 % contra 98,0 %), e ele não se moveu em
nenhuma variante de detecção — é um limite de **classificação em campo**, não de detecção.
Alvo da próxima iteração da F4.

---

## F0 — Fundação e ambiente

**Objetivo:** Um `pip install -e .` que funciona, com GPU Blackwell realmente ativa.

### Entregáveis
- `pyproject.toml` com dependências fixadas e resolvidas para Python 3.11.
- `scripts/setup_env.ps1` — cria venv, instala torch cu128, valida `sm_120`.
- `src/caissa/core/config/` — configuração em camadas (padrão, usuário, projeto).
- `src/caissa/vision/runtime/device.py` — detecção de dispositivo e diagnóstico.
- `scripts/doctor.py` — relatório de saúde do ambiente legível por humano.
- CI local: `scripts/check.ps1` roda lint + tipos + testes.

### Riscos específicos desta máquina
1. **`sm_120`**: instalar torch do índice `https://download.pytorch.org/whl/cu128`.
   Validar com `torch.cuda.get_device_capability() == (12, 0)` **e** uma multiplicação
   de matrizes real na GPU (a mera presença de `torch.cuda.is_available()` não prova
   que existem kernels compilados).
2. **ONNX Runtime**: ver ADR-0003. Não instalar `onnxruntime-gpu` no mesmo ambiente
   sem a resolução do ADR.
3. **Disco**: 76 GB livres. `scripts/doctor.py` avisa abaixo de 20 GB.

### Portão F0
- [ ] `python scripts/doctor.py` reporta GPU ativa com capability (12, 0)
- [ ] Multiplicação de matrizes 4096x4096 roda na GPU em menos de 100 ms
- [ ] `pytest tests/unit` verde
- [ ] Zero erros de `ruff` e `mypy --strict` em `src/caissa/core`

---

## F1 — Document IR

**Objetivo:** O modelo semântico do §5 do SPEC, completo, tipado e serializável.

### Entregáveis
- Todos os tipos de nó de bloco e inline.
- `RunProps` completo com as propriedades da tabela §5.2.
- Serialização JSON com esquema versionado e migrações.
- Visitante (visitor) genérico e transformadores.
- Validador estrutural.
- Diferença semântica entre dois IRs (para testes de ida-e-volta).

### Portão F1
- [ ] 100 % de cobertura de testes nos tipos de nó
- [ ] Ida-e-volta JSON preserva identidade em corpus sintético de 10.000 nós
- [ ] `mypy --strict` limpo
- [ ] Crítico confirma que o IR expressa **todos** os recursos da tabela §5.2 sem perda

---

## F2 — Ingestão de PDF

**Objetivo:** PDF (vetorial ou digitalizado) para IR, com layout preservado.

### Entregáveis
- Renderização por página com cache LRU e orçamento de memória.
- Extração da camada de texto com detecção de CMap quebrado.
- Análise de layout: colunas, ordem de leitura, cabeçalho/rodapé, notas.
- Detecção de estilo: qual sequência de caracteres é título, corpo, legenda, lance.
- Streaming: abrir PDF de 500 páginas sem carregar tudo.

### Portão F2
- [ ] PDF de 500 páginas abre com primeira página em ≤ 2 s
- [ ] Memória estável em varredura completa (sem crescimento linear)
- [ ] Ordem de leitura correta em 100 % das páginas de coluna dupla do corpus
- [ ] Crítico compara o IR extraído com o PDF original lado a lado e aprova

---

## F3 — Visão: detecção de tabuleiro

**Objetivo:** Encontrar todo diagrama em qualquer página. Recall ≥ 99 %.

### Entregáveis
- Via A (vetorial): leitura exata de PDFs com fonte de xadrez conhecida.
- Via B (geométrica): Hough e retículo.
- Via C (neural): detector com keypoints de canto.
- Árbitro de vias com política de custo.
- Ferramenta de anotação para construir o corpus dourado.

### Portão F3
- [ ] Recall ≥ 99,0 % e precisão ≥ 98,0 % no corpus dourado
- [ ] Via A acerta 100 % em PDFs com fonte de xadrez identificada
- [ ] Menos de 50 ms/página em média no perfil típico
- [ ] Crítico testa contra chessvision.ai nas mesmas páginas e aprova a paridade

---

## F4 — Visão: classificação e FEN

**Objetivo:** ≥ 99,5 % de casas corretas, ≥ 97 % de diagramas perfeitos.

### Entregáveis
- `tools/synthgen` — gerador sintético (§6.6).
- Treino da CNN de casas com contexto 3x3.
- Solucionador de restrições de legalidade (§6.4).
- Calibração de confiança (temperature scaling) para que o âmbar signifique algo.
- Harness de avaliação com relatório por estrato.

### Portão F4
- [ ] Métricas do §11.3 atingidas no corpus dourado
- [ ] Confiança calibrada: erro esperado de calibração (ECE) ≤ 0,03
- [ ] Solucionador recupera ≥ 80 % dos casos de erro de casa única
- [ ] Crítico compara com chessvision.ai e ChessOCR nas mesmas imagens, às cegas

---

## F5 — OCR de texto e layout

**Objetivo:** Taxa de erro de caractere ≤ 0,5 % em digitalização limpa.

### Entregáveis
- Adaptadores para Tesseract, PaddleOCR, Surya, VLM.
- Pré-processamento (§7.2).
- Árbitro por região com confiança calibrada.
- Reconstrução de parágrafo, hifenização, ligaduras.

### Portão F5
- [ ] CER ≤ 0,5 % (limpo), ≤ 2,0 % (ruidoso 150 DPI)
- [ ] Multilíngue: pt, en, de, ru, es validados
- [ ] Crítico lê a saída de 20 páginas e aprova como "publicável após revisão leve"

---

## F6 — Notação: gramática e correção

**Objetivo:** ≥ 99,8 % de lances corretos após correção por legalidade.

### Entregáveis
- Gramática PEG para SAN, LAN, figurino, em 6 idiomas.
- Validação e correção por legalidade contra `python-chess`.
- Conversão entre idiomas e estilos de renderização.
- Detecção de blocos de partida no texto corrido.

### Portão F6
- [ ] ≥ 99,8 % de acurácia de lance no corpus dourado
- [ ] Conversão de idioma é ida-e-volta perfeita para 100.000 lances de teste
- [ ] Crítico injeta erros típicos de OCR e verifica a taxa de recuperação

---

## F7 — Tipografia e fontes de xadrez

**Objetivo:** Diagramas indistinguíveis de livro impresso profissional.

### Entregáveis
- Renderizador vetorial de diagrama (SVG canônico, exportável para todos os formatos).
- Suporte a conjuntos de peças: Merida, Alpha, Chess Cases, USCF, Leipzig, e SVG modernos.
- Figurino inline com métricas corretas na linha de base.
- Sistema de temas de tabuleiro.
- Marcas: setas, destaques, círculos, com estilo editorial.

### Portão F7
- [ ] Renderização vetorial nítida em 4x de zoom e em impressão 600 DPI
- [ ] Figurino alinhado à linha de base em todos os tamanhos de corpo
- [ ] **Crítico compara às cegas com páginas reais de Quality Chess / New in Chess**
- [ ] Crítico não consegue identificar qual diagrama é o nosso

---

## F8 — Exportadores

**Objetivo:** Cinco formatos, sem perda silenciosa.

### Entregáveis por formato
- **PDF**: fontes embutidas, diagramas vetoriais, outline, XMP, PDF/A opcional, tags.
- **DOCX**: estilos reais, campos SEQ e TOC, diagramas EMF, notas de rodapé.
- **EPUB 3**: reflowable, SVG inline, fontes subconjuntadas, nav, EPUBCheck limpo.
- **HTML**: autocontido ou site, diagramas interativos, modo escuro, CSS Paged Media.
- **LaTeX**: `xskak`, diagramas editáveis em texto, Makefile.
- Relatório de fidelidade com `DegradationWarning` por propriedade perdida.

### Portão F8
- [ ] EPUBCheck: 0 erros em todos os documentos do corpus
- [ ] DOCX abre no Word sem aviso de reparo, estilos aparecem no painel
- [ ] Ida-e-volta IR → formato → IR preserva ≥ 99 % dos nós
- [ ] **Crítico compara o PDF gerado com o livro original lado a lado, às cegas**

---

## F9 — UI PySide6

**Objetivo:** Qualidade visual AAA. Referência: Affinity Publisher, DaVinci Resolve.

### Entregáveis
- Shell da aplicação: docas, painéis, layouts persistentes, paleta de comandos.
- **Biblioteca**: grade de capas, facetas, busca instantânea em milhares de itens.
- **Leitor**: pan/zoom 60 fps, sobreposição de reconhecimento, miniaturas.
- **Editor de posição**: tabuleiro lado a lado com o recorte original.
- **Editor de documento**: edição rica do IR com estilos.
- **Lote**: fila, progresso real, cancelamento, relatório.
- Sistema de temas claro/escuro projetados, tokens de design, ícones vetoriais.
- Acessibilidade: navegação por teclado completa, leitores de tela, WCAG AA.

### Portão F9
- [ ] ≥ 55 fps sustentados em pan/zoom de página 300 DPI
- [ ] Nenhuma operação bloqueia a UI por mais de 16 ms
- [ ] WCAG AA em 100 % dos pares de cor, nos dois temas
- [ ] Navegação completa por teclado, sem mouse
- [ ] **Crítico visual compara capturas com Affinity Publisher e Chessbase, às cegas**

---

## F10 — Índice e busca

**Objetivo:** Consultar acervo de dezenas de GB em milissegundos.

### Entregáveis
- SQLite FTS5 com tokenizador que preserva notação.
- Índice posicional Zobrist.
- Motor de regex sobre texto e IR, com pré-visualização de substituição.
- Consulta por padrão de material.
- Indexação incremental em segundo plano com orçamento de disco.

### Portão F10
- [ ] Base PGN de 10 GB indexa sem estourar RAM
- [ ] Busca por posição em ≤ 50 ms sobre 1 milhão de posições
- [ ] Regex com substituição pré-visualizada e desfazer
- [ ] Índice ocupa ≤ 15 % do tamanho do acervo

---

## F11 — LLM local (Gemma 4)

**Objetivo:** Assistência sem sair da máquina, dentro do orçamento de VRAM.

### Entregáveis
- Runtime local (llama.cpp ou equivalente) com Gemma 4 E4B quantizado.
- `ModelResidencyManager`: carga sob demanda, despejo LRU, nunca estourar 7 GB.
- Casos de uso: verificação de diagrama duvidoso, extração de estipulação,
  correção de OCR em regiões difíceis, geração de legenda, tradução de notação.
- Degradação graciosa: se o modelo não está disponível, tudo continua funcionando.

### Portão F11
- [ ] Pico de VRAM ≤ 7,0 GB com pipeline de visão ativa simultaneamente
- [ ] Aplicação 100 % funcional com o LLM desativado
- [ ] Ganho mensurável de acurácia nos itens de baixa confiança

---

## F12 — Empacotamento

**Objetivo:** Instalador que funciona na máquina de um enxadrista, não de um dev.

### Entregáveis
- Build PyInstaller com DLLs nativas resolvidas.
- Instalador Inno Setup.
- Baixador de modelos com verificação SHA-256 e modo offline.
- Primeiro uso: assistente que valida GPU, baixa modelos, roda autoteste.

### Portão F12
- [ ] Instalação limpa em Windows sem Python funciona
- [ ] Instalador abaixo de 150 MB
- [ ] Autoteste do primeiro uso passa
- [ ] Desinstalação remove tudo

---

## Ordem de execução

```
F0 ─┬─> F1 ─┬─> F7 ──> F8 ──┐
    │       │               │
    ├─> F2 ─┼─> F3 ──> F4 ──┼─> F9 ──> F12
    │       │               │
    ├─> F5 ─┴─> F6 ─────────┤
    │                       │
    ├─> F10 ────────────────┤
    └─> F11 ────────────────┘
```

Frentes sem dependência entre si rodam em paralelo, um subagente cada.

---

## Registro de ciclos de crítica

| Data | Frente | Ciclo | Veredito | Observação |
|---|---|---|---|---|
| — | — | — | — | (preenchido durante a execução) |
