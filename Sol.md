# Sol — Roadmap de implementação para OCR de páginas de xadrez

> Documento de execução derivado de cinco análises independentes do projeto:
> integração, imagem/layout, motores/arbitragem, inteligência enxadrística e
> validação. O objetivo é transformar a infraestrutura existente em um OCR de
> prosa editorialmente confiável, sem degradar o motor de glifos já preciso.

## 1. Objetivo

Construir um pipeline de OCR para livros e páginas de xadrez que:

- preserve a camada textual válida de PDFs nativos;
- substitua apenas regiões comprovadamente danificadas;
- reconheça prosa, movetext, cabeçalhos, notas e tabelas;
- use contexto enxadrístico sem inventar lances;
- mantenha confiança e proveniência até o IR e a interface de revisão;
- abstenha-se quando não houver evidência suficiente;
- atinja os portões de precisão definidos na especificação do projeto.

### Metas mínimas

| Métrica | Meta |
|---|---:|
| CER em digitalização limpa | <= 0,5% |
| CER em digitalização ruidosa a 150 DPI | <= 2,0% |
| Acurácia exata de tokens de lance | >= 99,8% |
| Lances inexistentes inseridos | 0 no corpus dourado |
| Ordem de leitura em páginas de duas colunas | 100% no corpus dourado |
| Resultado abaixo do limiar importado silenciosamente | 0 |
| Páginas da avaliação humana | >= 20 |
| Páginas rotuladas no corpus dourado | >= 200 |

## 2. Princípios inegociáveis

1. **Precisão antes de cobertura.** É melhor preservar uma imagem para revisão
   do que inserir prosa ou lances inexistentes.
2. **Abstenção é um resultado válido.** Nenhum motor atingir o limiar nunca
   deve ser convertido em `accepted`.
3. **Correção localizada.** A camada PDF, o OCR e os reparadores competem por
   linha ou token, não pela página inteira.
4. **Contexto de xadrez restringe; não cria.** Legalidade serve para escolher
   entre candidatos observados, nunca para completar livremente uma partida.
5. **Confiança precisa ser calibrada.** Confiança bruta de motores diferentes
   não é comparável.
6. **Toda transformação é rastreável.** O IR deve registrar fonte, motor,
   variante de imagem, alternativas, confiança e justificativa.
7. **Nenhuma otimização sem corpus.** Mudanças de OCR só entram quando medidas
   por estrato e comparadas com o baseline versionado.

## 3. Arquitetura-alvo

```text
Página PDF ou imagem
  -> análise da camada PDF por fonte, span e região
  -> renderização seletiva em 300/400 DPI
  -> detecção de layout, colunas e ordem de leitura
  -> imagem original + variantes condicionais de pré-processamento
  -> roteamento por idioma, script e tipo de região
  -> OCR com múltiplos candidatos
  -> alinhamento geométrico e fusão por linha/palavra
  -> classificação: prosa, movetext, tabela, legenda ou cabeçalho
  -> validação linguística ou legalidade enxadrística
  -> decisão: aceitar, revisar ou abster
  -> IR com proveniência completa
```

## 4. Estado atual resumido

### Capacidades já presentes

- `PageRecognizer` e árbitro em cascata;
- adaptadores para camada PDF, Tesseract, PaddleOCR, RapidOCR e Surya;
- pré-processamento com upscale, sombra, bleed-through, deskew, Sauvola e
  despeckle;
- análise de layout e tipos de região;
- avaliação heurística de qualidade;
- detecção de movetext;
- inferência de cifras de peças;
- reparação baseada em legalidade;
- testes unitários extensos.

### Lacunas críticas

- `PdfImportOptions.ocr` é `None` por padrão;
- o pré-processamento não alimenta o OCR de produção;
- a calibração provisória favorece camadas PDF danificadas;
- o árbitro aceita o melhor resultado mesmo abaixo do limiar;
- a escolha é feita por resultado inteiro, sem fusão por token;
- o limite de motores pode impedir Surya de executar;
- PaddleOCR não implementa realmente PP-StructureV3;
- adaptadores opcionais precisam de testes contra APIs atuais;
- correção enxadrística não está ligada à importação final;
- confiança detalhada é perdida na conversão para `PageText`;
- o léxico forte depende de caminho externo absoluto;
- não há modelo linguístico equivalente para cirílico;
- o corpus dourado de 200 páginas ainda não existe.

## 5. Plano de implementação

## SOL-0 — Congelar baseline e criar medição confiável

**Prioridade:** P0  
**Dependências:** nenhuma  
**Bloqueia:** todas as otimizações posteriores

### Entregáveis

- [ ] Criar manifesto versionado do corpus dourado.
- [ ] Selecionar no mínimo 200 páginas representativas.
- [ ] Armazenar verdade textual Unicode por região e ordem de leitura.
- [ ] Rotular caixas de prosa, movetext, títulos, notas, tabelas e legendas.
- [ ] Marcar idioma da prosa e idioma da notação separadamente.
- [ ] Registrar DPI, origem, qualidade, script, layout e tipo de dano.
- [ ] Anotar tokens de lance e sua associação com partida/diagrama quando
      aplicável.
- [ ] Criar partições fixas de desenvolvimento, calibração e teste cego.
- [ ] Implementar executor único de benchmark com saída JSON e Markdown.
- [ ] Versionar resultados do baseline atual.

### Estratos obrigatórios

- PDF vetorial nativo limpo;
- PDF com ToUnicode ou fonte de peças corrompida;
- digitalização limpa a 300 DPI;
- digitalização degradada a 150 DPI;
- sombra, curvatura, sujeira e bleed-through;
- fax/dithering;
- fotografia de página;
- uma e duas colunas;
- tabelas e índices;
- português, inglês, alemão, espanhol e russo;
- notação algébrica, figurines e convenções históricas;
- problemas e composições;
- páginas vazias ou sem texto como controles negativos.

### Métricas

- CER e WER por página, região, idioma e estrato;
- acurácia exata de linha;
- acurácia de ordem de leitura;
- precisão, recall e F1 de regiões;
- acurácia exata de tokens SAN/LAN;
- lances perdidos, alterados e inventados;
- Expected Calibration Error e Brier score;
- curva risco versus cobertura da abstenção;
- tempo e memória por megapixel;
- percentual enviado para revisão humana.

### Critério de aceite

- O mesmo comando reproduz o baseline em uma máquina limpa.
- Cada resultado pode ser rastreado até página, região, motor e configuração.
- O conjunto de teste cego não é usado para ajustar limiares.

## SOL-1 — Integrar OCR ao importador principal

**Prioridade:** P0  
**Dependências:** SOL-0

### Entregáveis

- [ ] Implementar um `OcrService` concreto como padrão do importador.
- [ ] Conectar `PdfImporter`, `PageRecognizer` e `page_text_from_ocr`.
- [ ] Renderizar somente páginas ou regiões que precisem de OCR.
- [ ] Usar 300 DPI como base e 400 DPI para texto pequeno ou baixa resolução.
- [ ] Preservar `keep_scanned_pages` quando houver abstenção.
- [ ] Permitir desligar OCR explicitamente para importação rápida.
- [ ] Emitir progresso, cancelamento e relatório por página.
- [ ] Garantir que falha de um motor não perca a página nem encerre o livro.

### Decisão de fonte

Substituir a decisão binária página inteira por uma máscara de confiança:

- fonte e `ToUnicode` confiáveis: manter texto PDF;
- span suspeito: renderizar e reconhecer apenas a região;
- página sem camada textual: OCR integral;
- página mista: combinar spans confiáveis com OCR localizado.

### Critério de aceite

- Um PDF escaneado importado sem callback manual produz texto OCR ou uma
  abstenção explícita.
- Um PDF nativo limpo não sofre OCR visual desnecessário.
- Uma camada parcialmente danificada preserva os spans bons.

## SOL-2 — Introduzir aceitação segura e abstenção real

**Prioridade:** P0  
**Dependências:** SOL-1

### Entregáveis

- [ ] Criar enum de decisão: `ACCEPTED`, `REVIEW`, `ABSTAINED`.
- [ ] Remover o `accepted` criado quando nenhum motor atinge o limiar.
- [ ] Exigir limiar absoluto e evidência mínima para importação automática.
- [ ] Rejeitar texto vazio, ruído curto e texto sem suporte geométrico.
- [ ] Criar controles negativos com páginas brancas, tabuleiros sem texto,
      manchas, bordas e imagens aleatórias.
- [ ] Impedir que tokens com aparência de lance sejam aceitos apenas por forma.
- [ ] Manter a imagem original associada à região recusada.

### Política inicial

- `ACCEPTED`: alta confiança calibrada e sinais coerentes;
- `REVIEW`: resultado plausível, mas com divergência ou baixa confiança local;
- `ABSTAINED`: nenhum resultado ultrapassa o limiar ou existe risco de
  alucinação/inserção.

### Critério de aceite

- Imagem branca não gera conteúdo no IR.
- Nenhuma decisão abaixo do limiar recebe o rótulo `accepted`.
- Todas as abstenções ficam visíveis e recuperáveis na revisão.

## SOL-3 — Integrar pré-processamento como portfólio condicionado

**Prioridade:** P0  
**Dependências:** SOL-0, SOL-1

### Entregáveis

- [ ] Ligar `default_pipeline` ao serviço de OCR.
- [ ] Sempre manter a imagem original como candidata.
- [ ] Detectar sombra, inclinação, bleed-through, ruído e baixa resolução.
- [ ] Gerar somente variantes justificadas pelos sinais detectados.
- [ ] Implementar dewarp para fotografia ou curvatura de lombada.
- [ ] Registrar transformações e parâmetros no resultado.
- [ ] Comparar resultados por região, não apenas por página.
- [ ] Adicionar testes para garantir que páginas limpas não sejam degradadas.

### Portfólio inicial

1. original em tons de cinza;
2. deskew + correção de sombra;
3. redução de bleed-through + Sauvola;
4. upscale para 150 DPI ou fontes pequenas;
5. dewarp somente quando a geometria indicar curvatura.

### Critério de aceite

- Cada estrato degradado melhora ou mantém CER em relação ao baseline.
- Nenhuma variante piora significativamente o estrato limpo.
- O custo adicional fica registrado no relatório.

## SOL-4 — Recalibrar o árbitro

**Prioridade:** P0  
**Dependências:** SOL-0, SOL-2, SOL-3

### Entregáveis

- [ ] Remover pisos e gammas provisórios não medidos.
- [ ] Coletar confiança bruta por palavra e por linha de cada motor.
- [ ] Calibrar por motor, idioma, script, DPI e tipo de região.
- [ ] Usar partição exclusiva de calibração.
- [ ] Medir ECE, Brier score e curvas de confiabilidade.
- [ ] Criar limiares separados para aceitação e revisão.
- [ ] Não contar camada PDF vazia/rejeitada no orçamento de motores.
- [ ] Substituir ordem fixa por roteamento baseado em evidência.
- [ ] Permitir que Surya/Paddle sejam executados quando o caso exigir.

### Roteamento inicial

| Condição | Rota preferencial |
|---|---|
| PDF nativo confiável | camada PDF |
| Prosa latina simples | Tesseract |
| Layout complexo/tabela | PP-StructureV3 |
| Cirílico ou script difícil | Surya e/ou Paddle multilíngue |
| Movetext | Tesseract normal + configuração enxadrística |
| Baixa concordância | segundo motor + revisão |

### Critério de aceite

- Uma camada PDF danificada deixa de vencer apenas por possuir confiança fixa.
- Faixas declaradas como 90% de confiança ficam próximas de 90% de acerto.
- O roteador alcança todos os motores elegíveis sem violar o orçamento.

## SOL-5 — Atualizar e isolar motores opcionais

**Prioridade:** P1  
**Dependências:** SOL-4

### Entregáveis

- [ ] Implementar PP-StructureV3 como backend de layout real.
- [ ] Manter PaddleOCR simples como backend distinto.
- [ ] Atualizar Surya para a API atual e seu novo formato de blocos.
- [ ] Criar testes contratuais por versão suportada.
- [ ] Fixar intervalos de versões compatíveis.
- [ ] Executar Paddle e Surya em workers isolados.
- [ ] Controlar download, hash e versão dos pesos.
- [ ] Medir CPU, GPU, RAM e VRAM por worker.
- [ ] Verificar termos de licença dos pesos antes de distribuição comercial.
- [ ] Corrigir extras de instalação e remover dependências não utilizadas.

### Critério de aceite

- Instalação opcional não quebra o ambiente principal.
- Mudança de schema do motor falha de forma explícita, não como página vazia.
- Backend de layout devolve regiões e ordem de leitura verificáveis.

## SOL-6 — Implementar fusão geométrica por token

**Prioridade:** P1  
**Dependências:** SOL-3, SOL-4, SOL-5

### Entregáveis

- [ ] Alinhar linhas por sobreposição geométrica e baseline.
- [ ] Alinhar palavras com distância textual e posição.
- [ ] Construir um lattice de candidatos por token.
- [ ] Preservar candidatos N-best e suas fontes.
- [ ] Combinar camada PDF, variantes Tesseract e motores neurais.
- [ ] Usar concordância entre motores como evidência, não como verdade.
- [ ] Penalizar inserções sem suporte visual em outro candidato.
- [ ] Fazer escolha específica para pontuação, diacríticos e hífens.
- [ ] Tratar hifenização de fim de linha depois da ordem de leitura.

### Regras conservadoras

- Nunca substituir um span PDF confiável por OCR de confiança inferior.
- Não unir palavras através de colunas diferentes.
- Não completar palavra ou lance sem candidato observado.
- Em empate relevante, manter alternativa para revisão.

### Critério de aceite

- A fusão supera ou iguala o melhor motor individual em todos os estratos.
- A taxa de inserção não aumenta.
- É possível explicar de onde veio cada token final.

## SOL-7 — Criar perfis separados para prosa e movetext

**Prioridade:** P1  
**Dependências:** SOL-4, SOL-6

### Entregáveis

- [ ] Detectar idioma da prosa por documento e por região.
- [ ] Detectar separadamente a convenção de letras das peças.
- [ ] Criar `TesseractProfile.PROSE`.
- [ ] Criar `TesseractProfile.MOVETEXT`.
- [ ] Adicionar `user_words` com vocabulário editorial e enxadrístico.
- [ ] Adicionar `user_patterns` para SAN, LAN, resultados e numeração.
- [ ] Avaliar desativação de DAWGs somente no perfil de movetext.
- [ ] Testar whitelist limitada somente em candidatos adicionais de movetext.
- [ ] Manter pontuação, comentários e NAGs fora da whitelist estreita.

### Critério de aceite

- O perfil de movetext aumenta a acurácia dos lances sem degradar a prosa.
- O perfil de prosa preserva diacríticos e pontuação por idioma.
- Livros cuja prosa e notação usam convenções diferentes são suportados.

## SOL-8 — Integrar validação enxadrística ao documento

**Prioridade:** P1  
**Dependências:** SOL-6, SOL-7

### Entregáveis

- [ ] Converter regiões `MOVETEXT` em tokens estruturados.
- [ ] Associar cada região à partida, posição ou diagrama mais provável.
- [ ] Usar FEN somente quando sua proveniência for confiável.
- [ ] Propagar `side_to_move` explicitamente; não assumir valor padrão em silêncio.
- [ ] Aplicar inferência de cifra antes do replay legal.
- [ ] Corrigir homoglifos latinos/cirílicos antes da análise.
- [ ] Gerar candidatos para separadores inseridos ou removidos pelo OCR.
- [ ] Fazer replay de variantes e comentários, não apenas linha principal.
- [ ] Autoaplicar somente correção única e integralmente legal.
- [ ] Encaminhar ambiguidades para revisão com alternativas explicadas.
- [ ] Registrar lances corrigidos, perdidos e inventados no benchmark.

### Política contra alucinação

- VLM nunca substitui automaticamente a região.
- VLM pode sugerir candidatos apenas dentro da interface de revisão.
- Sugestão sem suporte visual ou legal permanece rejeitada.
- Repetições artificiais de lances recebem penalidade e bloqueio.

### Critério de aceite

- Acurácia de tokens de lance >= 99,8% no teste cego.
- Zero lances inventados no corpus dourado.
- Toda correção automática possui replay legal e evidência OCR rastreável.

## SOL-9 — Tornar léxicos reproduzíveis e multilíngues

**Prioridade:** P1  
**Dependências:** SOL-0, SOL-7

### Entregáveis

- [ ] Remover dependência de caminho absoluto externo.
- [ ] Auditar licença e origem de cada lista de palavras.
- [ ] Criar pacote/versionamento dos léxicos aprovados.
- [ ] Adicionar hash e metadados da versão usada em cada execução.
- [ ] Separar léxicos por idioma e script.
- [ ] Construir léxico cirílico e modelo de plausibilidade correspondente.
- [ ] Adicionar nomes de jogadores, autores, aberturas, eventos e cidades.
- [ ] Tratar flexões e ortografias históricas sem aceitar lixo arbitrário.
- [ ] Permitir léxico específico por livro sem contaminar o global.

### Critério de aceite

- Instalação limpa reproduz os mesmos escores linguísticos.
- Russo não é aceito apenas por abstenção do modelo latino.
- O léxico não força correções contra forte evidência visual.

## SOL-10 — Preservar confiança e proveniência no IR

**Prioridade:** P1  
**Dependências:** SOL-1, SOL-6

### Entregáveis

- [ ] Estender o contrato do `OcrProvider` para retornar resultado completo.
- [ ] Preservar confiança por caractere, palavra, linha e região.
- [ ] Preservar caixas, motor, versão e configuração.
- [ ] Preservar variante de pré-processamento e DPI.
- [ ] Preservar alternativas e concordância entre motores.
- [ ] Preservar decisão do árbitro e motivos de escalada.
- [ ] Armazenar CER estimado com confiança da estimativa.
- [ ] Evitar limitar todos os blocos pela pior linha da página.
- [ ] Criar relatório de importação com regiões críticas clicáveis.

### Critério de aceite

- Um token final pode ser rastreado até a imagem e os candidatos de origem.
- Regiões boas não herdam a baixa confiança de outra região da página.
- Reprocessamento seletivo pode reutilizar os metadados existentes.

## SOL-11 — Interface de revisão focada em risco

**Prioridade:** P2  
**Dependências:** SOL-2, SOL-8, SOL-10

### Entregáveis

- [ ] Mostrar apenas regiões `REVIEW` e `ABSTAINED` por padrão.
- [ ] Exibir recorte da imagem e texto lado a lado.
- [ ] Destacar palavras de baixa confiança.
- [ ] Mostrar candidatos alternativos e motor de origem.
- [ ] Exibir motivo linguístico ou enxadrístico da dúvida.
- [ ] Permitir aceitar, editar ou manter como imagem.
- [ ] Registrar correções humanas para futura calibração.
- [ ] Impedir que feedback do conjunto de teste cego volte ao treinamento.

### Critério de aceite

- Um revisor corrige somente spans duvidosos, sem reler a página inteira.
- Toda decisão humana fica auditável.
- O tempo de revisão por página é medido.

## SOL-12 — Portões de release e observabilidade

**Prioridade:** P0 para release  
**Dependências:** SOL-0 a SOL-11

### Entregáveis

- [ ] Executar corpus dourado no CI ou em job de qualidade controlado.
- [ ] Bloquear release quando uma meta crítica regredir.
- [ ] Comparar por estrato, não apenas por média agregada.
- [ ] Definir tolerância estatística e intervalo de confiança.
- [ ] Guardar configuração, versões e hashes dos modelos.
- [ ] Produzir relatório de diferenças por página e região.
- [ ] Fazer revisão humana cega de pelo menos 20 páginas.
- [ ] Comparar, quando disponíveis, ABBYY/Acrobat/outros baselines na mesma
      amostra, sem misturar verdades de referência.
- [ ] Monitorar tempo, memória e percentual de abstenção.

### Portões bloqueantes

- CER limpo > 0,5%;
- CER 150 DPI > 2,0%;
- acurácia de lance < 99,8%;
- qualquer lance inventado no corpus dourado;
- aumento estatisticamente relevante de inserções de texto;
- página abaixo do limiar importada sem marca de revisão;
- regressão de ordem de leitura em duas colunas;
- falha na reprodução do ambiente e dos modelos.

## 6. Sequência recomendada de entregas

### Marco A — OCR realmente funcional e seguro

Inclui SOL-0, SOL-1, SOL-2 e SOL-3.

Resultado esperado: PDFs escaneados passam por OCR automaticamente, com
pré-processamento seletivo e abstenção explícita.

### Marco B — Escolha correta entre fontes

Inclui SOL-4, SOL-5 e SOL-6.

Resultado esperado: camada PDF, Tesseract e motores neurais são comparados de
forma calibrada e fundidos localmente.

### Marco C — Precisão específica para livros de xadrez

Inclui SOL-7, SOL-8 e SOL-9.

Resultado esperado: prosa e notação usam perfis diferentes; legalidade melhora
lances sem inventar conteúdo; idiomas latinos e cirílico são avaliados de forma
real.

### Marco D — Produto editorial auditável

Inclui SOL-10, SOL-11 e SOL-12.

Resultado esperado: revisão humana eficiente, proveniência completa e releases
bloqueados por métricas reproduzíveis.

## 7. Testes mínimos por componente

### Importação

- PDF sem texto aciona OCR por padrão.
- PDF nativo limpo não é rasterizado desnecessariamente.
- PDF misto preserva spans bons e reconhece apenas os ruins.
- Falha de motor mantém imagem e relatório.

### Pré-processamento

- página limpa, sombra, bleed-through, rotação, ruído, 150 DPI e fotografia;
- comparação entre imagem original e variante processada;
- caixas corretamente transformadas de volta para coordenadas da página.

### Árbitro

- nenhum motor disponível;
- todos abaixo do limiar;
- camada PDF ruim contra Tesseract melhor;
- motores discordando em poucas palavras;
- orçamento sem contar candidatos vazios;
- rotas para latim, cirílico, tabela e movetext.

### Prosa

- diacríticos portugueses, alemães e espanhóis;
- ligaduras, travessões, aspas, notas de rodapé e hifenização;
- nomes próprios raros sem correção agressiva;
- duas colunas e cabeçalhos repetidos.

### Xadrez

- SAN, LAN, figurines, resultados, NAGs e variantes;
- homoglifos latinos/cirílicos;
- separador inserido ou removido;
- posição inicial conhecida e desconhecida;
- `side_to_move` ambíguo;
- dois reparos legais possíveis;
- candidato visualmente forte, mas ilegal;
- sequência legal inventada sem suporte na imagem.

### Controles negativos

- página branca;
- tabuleiro sem prosa;
- manchas e bordas;
- fotografia sem texto;
- ruído puro;
- texto muito curto;
- região recortada incorretamente.

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| VLM inventar lances plausíveis | somente sugestão para revisão; nunca autoaplicar |
| Pré-processamento degradar página limpa | manter original e usar portfólio condicionado |
| Confianças incomparáveis | calibração por motor/estrato em conjunto separado |
| API opcional mudar silenciosamente | worker versionado e teste contratual |
| Paddle/Torch colidirem em runtime | processos isolados |
| Léxico corrigir nome raro incorretamente | léxico como evidência fraca, não regra absoluta |
| Legalidade escolher continuação errada | exigir posição confiável e solução única |
| Média esconder idioma ruim | portões por estrato e idioma |
| Abstenção excessiva | otimizar curva risco/cobertura sem relaxar inserções |
| Corpus contaminar ajuste | divisão fixa entre desenvolvimento, calibração e teste cego |

## 9. Evidências do baseline analisado

- Testes unitários de OCR: 369 aprovados.
- Testes de ingestão e notação: 491 aprovados.
- Testes dourados de OCR existentes: 23 aprovados.
- Testes dourados de ingestão existentes: 6 aprovados.
- Motores disponíveis localmente: camada PDF e Tesseract 5.5.0.
- PaddleOCR, RapidOCR e Surya não estavam instalados.
- Em Gaprindashvili, página 202, a cascata executou Tesseract nas duas regiões,
  mas preservou a camada PDF danificada nas duas.
- Em imagem branca, Tesseract produziu o falso positivo `rs`, confirmando a
  necessidade de abstenção.
- Nos livros danificados do benchmark, a estrutura dos tokens de peça ficou a
  um caractere do correto em aproximadamente 93% a 98% dos casos, indicando que
  candidatos visuais combinados com legalidade têm alto potencial.
- O experimento com VLM reduziu CER mediano, mas inseriu 103 lances ausentes da
  página; por isso não é aceitável como transcrição automática.

## 10. Definição de pronto do projeto Sol

O projeto Sol estará concluído quando:

- [ ] OCR for parte padrão e configurável da importação;
- [ ] camada PDF for julgada por span/região;
- [ ] pré-processamento condicionado estiver ativo;
- [ ] confiança estiver calibrada em corpus separado;
- [ ] houver fusão por token com proveniência;
- [ ] prosa e movetext tiverem perfis próprios;
- [ ] reparação enxadrística estiver conectada ao IR;
- [ ] não houver inserção silenciosa abaixo do limiar;
- [ ] léxicos forem reproduzíveis e multilíngues;
- [ ] revisão humana estiver orientada a regiões de risco;
- [ ] os portões quantitativos e humanos estiverem verdes;
- [ ] os resultados forem reproduzíveis em ambiente limpo.

Até que todos esses critérios sejam satisfeitos, a aplicação deve apresentar o
OCR como assistido e sujeito a revisão, não como transcrição editorialmente
confiável.
