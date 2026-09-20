# Análise OCR/UI ciclo 2 — vereditos dos críticos adversariais

> Registro dos três ciclos de crítica de `docs/OCR_UI_ANALISE_C2.md` (2026-09-20). Dois críticos
> independentes, regidos por `CRITIC_CHARTER.md`: um agente Claude (Opus 5, com acesso só de leitura
> ao código, reproduzindo os números) e o Codex (`codex exec -s read-only`, GPT-5.6). Os vereditos
> do Codex estão transcritos na íntegra; os do Claude estão resumidos por ciclo (bloqueantes e o
> veredito), porque o texto completo vive no transcrito da sessão. Contagem: Claude 8 + 3 + 0
> bloqueantes; Codex 6 + 1 + 1 + 0 — os 'bloqueantes' de cada ciclo são os itens numerados abaixo.
> Veredito final: Claude APROVADO (ciclo 3), Codex APROVADO (ciclo 4).

## Crítico Claude

### Ciclo 1 — REPROVADO (8 bloqueantes)
1. §2.2/X5: `side_conflicting` "não mostrado" — falso (`painel_de_resultado.py:1195`, `strings.py:42`).
2. §3.3 sabotagem de D2 "0,9652" — `ROADMAP.md:164` é "só resgate", não o pacote menos o resgate.
3. §4.1 "CER limpo 0,0156 (`c1_rapidocr`)" — é 0,0216; 0,0156 é `sol.json`; inventados 167 × 169 sem nomear sistemas.
4. §4.2 "7 de 10 piores são twocol" — são 5 limpos + 1 a 150 DPI.
5. Alavanca 18 "64/64 nos 3 Niemeijer", "mediana 0,25" — a fonte diz 4/4, 23/23, 41/41 e média 0,25.
6. D3/D6 apoiados no Koblenz "8–11 casas de cor" — estado anterior a `d39b1f1`; não remedido.
7. §8 C3 (mhsp) → C4 (segundo modelo mhsp) — o segundo leitor seria irmão do primeiro.
8. Alavanca 1 antes de internalizar o `recall_pack` (monkeypatch global sem lock numa thread).
Não bloqueantes: linhas/arquivos imprecisos (7), `_supported` recebe `langs`, U7 erro não expira, 0/12 → 0/9, números sem origem (3), §8 sem X3/X4/X6, B1→B2 × T5, anti-padrão 5 e R2.2 a citar, D8 bispos condicionados, X2 exceção anotada, Aagaard `imagem-embutida`.
Achados novos: travessão em `_MOVE_SHAPE` (0 lances, silencioso); cancelamento por página.

### Ciclo 2 — REPROVADO (3 bloqueantes)
1. §3.1/§3.9 "as 4 casas que o decodificador reparou estão todas erradas" — `totals.repaired_squares = 14`, 10 certas, 4 erradas.
2. Koblenz "5 de cor a 0,71–1,00" — `g1 K→k` é reparo do decodificador sobre `K` a 0,48; "de cor" sem definição.
3. "289 páginas ≈ 17 min" — 289 × 31,9 / 8 = 1.152 s ≈ 19 min.
Não bloqueante: sabotagem do `--frio` não tocava o tempo.

### Ciclo 3 — APROVADO (0 bloqueantes)
Conferiu as três correções contra o próprio `failures.json`, executou o bloco do §5.2 literalmente e não achou erro novo. Não bloqueante: alinhar a formulação do §3.9 à do §3.1 (feito).

## Crítico Codex (transcrição integral)

### Ciclo 1

VEREDITO: REPROVADO  
CICLO: 1

## Conferências feitas

| item | arquivo:linha | confere? | nota |
|---|---|---|---|
| 1 | `OCR_UI_ANALISE_C2.md:37`; `src/caissa/ingest/pdf/importer.py:684-690` | Parcial | O fallback vetorial e a ausência de `combined_finder` na UI conferem; os números não foram reexecutados em 3 corridas. |
| 2 | `OCR_UI_ANALISE_C2.md:38`; `src/caissa/export/book.py:306-354` | Sim | A exportação reimporta o PDF e não consome o resultado OCR da janela. |
| 3 | `OCR_UI_ANALISE_C2.md:39`; `src/caissa/ocr/page.py:332-354` | Parcial | O caminho de página inteira e a ausência de chamada a `lines_from_result` conferem; a afirmação absoluta sobre todos os scans é excessiva. |
| 4 | `OCR_UI_ANALISE_C2.md:40`; `src/caissa/notation/legality_repair.py:145-148,331-340` | Sim | O erro Unicode e a perda de `Nf6⩲` são reproduzíveis. |
| 5 | `OCR_UI_ANALISE_C2.md:41`; `src/caissa/ingest/pdf/games.py:188-190,249-273` | Parcial | O fallback `anchors[-1].fen` confere, mas a medição publicada chama a função com assinatura inválida. |
| 6 | `OCR_UI_ANALISE_C2.md:42`; `src/caissa/ingest/pdf/finders.py:103-111`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/janela.py:1154-1227` | Sim | O `recall_pack` existe na suíte e não é usado pelo caminho da janela do tronco. |
| 7 | `OCR_UI_ANALISE_C2.md:43`; `src/caissa/ocr/fusion.py:318-338` | Sim | A decisão usa o escore da âncora mesmo após fusão. |
| 8 | `OCR_UI_ANALISE_C2.md:44`; `src/caissa/ocr/lexicon.py:376-405`; `src/caissa/ocr/fusion.py:353-372` | Sim | Os falsos tokens e a restrição de prefixo figurativo conferem. |
| 9 | `OCR_UI_ANALISE_C2.md:45`; `src/caissa/export/pdf.py:113-118,733-753,1223-1227` | Sim | O filtro por `has_char` pode remover símbolos sem falha explícita. |
| 10 | `OCR_UI_ANALISE_C2.md:46`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/janela.py:1304-1331,1903-1910` | Sim | Não há progresso/cancelamento adequado e o painel inteiro é desabilitado. |
| 11 | `OCR_UI_ANALISE_C2.md:47`; `src/caissa/ingest/pdf/importer.py:166-193,1280-1335` | Sim | O sinal por casa existe no modelo final, mas não atravessa `DiagramHit`/`_diagram_node`. |
| 12 | `OCR_UI_ANALISE_C2.md:48`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/ui/page_results.py:39,139-157` | Sim | O LRU de oito páginas e a perda de correções não salvas conferem. |
| 13 | `OCR_UI_ANALISE_C2.md:49`; `ChessVisionOFF_Puro/docs/EXPERIMENTS_FASE7.md:989-1005` | Parcial | `mhsp` foi medido e rejeitado; `RandomStroke` é hipótese nova, ainda sem ablação ou medição. |
| 14 | `OCR_UI_ANALISE_C2.md:50`; `src/caissa/ocr/engines/glyph.py:160-179,247-256` | Sim | A pós-cadeia do tronco não é chamada. |
| 15 | `OCR_UI_ANALISE_C2.md:51`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/janela.py:1304-1331`; `docs/quality/OCR_UI_REPORT_C1.md:1649-1688` | Parcial | O bloqueio e a duplicação de fluxo conferem; “289 páginas ≈20 min” é extrapolação sem marcação/proveniência adequada. |
| 16 | `OCR_UI_ANALISE_C2.md:52`; `src/caissa/ingest/pdf/games.py:158-178` | Sim | `MoveNode` não transporta NAGs. |
| 17 | `OCR_UI_ANALISE_C2.md:53`; `src/caissa/ingest/pdf/ocr_service.py:757-785,1163-1169` | Não | O perfil não depende apenas de `kind is MOVETEXT`; há o caminho alternativo `_looks_like_movetext(result)`. |
| 18 | `OCR_UI_ANALISE_C2.md:54`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/ui/configuracoes.py:116-127` | Parcial | A preferência permanece, mas a alegação numérica `64/64` não tem origem report§/marcador. |
| 19 | `OCR_UI_ANALISE_C2.md:55`; `ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/trilho.py:254-286`; `ui/tabuleiro_editavel.py:58-93` | Parcial | A deficiência atual confere; porém `--teclado` não existe no instrumento citado. |
| 20 | `OCR_UI_ANALISE_C2.md:56`; `src/caissa/ocr/arbiter.py:385-412`; `src/caissa/ocr/engines/rapidocr.py:442-477` | Sim | A calibração existe e o RapidOCR replica a confiança da linha por palavra. |

## Defeitos bloqueantes

1. **Comportamento incorreto atribuído ao perfil SOL-7.**  
   Em `OCR_UI_ANALISE_C2.md:53,292,355-358`, afirma-se que o perfil só roda quando `kind is MOVETEXT`. O código real em `src/caissa/ingest/pdf/ocr_service.py:775` usa:

   `region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)`

   e `_looks_like_movetext` está implementado em `:1163-1169`. A conclusão “nunca roda em página digitalizada” não é demonstrada e a descrição do comportamento é falsa.

2. **Medição de `game_from_paragraph` não é executável como publicada.**  
   `OCR_UI_ANALISE_C2.md:41` publica uma chamada com uma string e sem `start_fen`. A assinatura real em `src/caissa/ingest/pdf/games.py:188-190` exige `Paragraph` e `start_fen`. O defeito subjacente do fallback é real, mas a prova apresentada não é uma medição válida.

3. **Violação sistemática da regra de proveniência numérica.**  
   `OCR_UI_ANALISE_C2.md:13-16` promete origem `report§` para todos os números. Isso não ocorre, por exemplo, em `:44` (`167`, `204/204 vs 193`), `:45` (`27`, `37`), `:49` (`5.444`, `38`), `:50` (`314`, `2,3 F1`), `:51` (`289 ≈20 min`), `:54` (`64/64`) e `:55` (`25 teclas`). Sem fonte ou marcador `(medido nesta análise)`, o roadmap não é auditável.

4. **Instrumentos propostos não existem com os argumentos usados.**  
   `OCR_UI_ANALISE_C2.md:557,609` prescreve `percurso --frio` e `percurso --teclado`. O parser real em `src/caissa/ui/audit/percurso.py:656-672` não aceita nenhum deles. O documento não define o novo instrumento, contrato, saída ou gate correspondente.

5. **A seção de revisão adversarial está vazia.**  
   `OCR_UI_ANALISE_C2.md:17` afirma que §11 registra as alterações dos críticos, mas `:822-824` contém apenas um placeholder. Isso invalida a rastreabilidade exigida pelo brief.

6. **Afirmação de não repetição é falsa.**  
   `OCR_UI_ANALISE_C2.md:6-7` diz que nenhuma alavanca anterior é repetida. A alavanca 13 reabre o experimento `mhsp`, já medido e rejeitado em `ChessVisionOFF_Puro/docs/EXPERIMENTS_FASE7.md:989-1005`, relacionado também ao experimento anterior de cor de peças. A hipótese nova `RandomStroke` não basta: falta uma ablação que isole o ganho novo.

## Defeitos não bloqueantes

- Vários caminhos são ambíguos (`importer.py`, `janela.py`, `games.py`) sem indicar claramente suíte ou tronco.
- A quebra de linha do caminho do tronco em `OCR_UI_ANALISE_C2.md:8-9` prejudica a reprodutibilidade.
- Estimativas como “baixo”, “½ dia” e “20 min” não têm modelo de custo ou intervalo.
- A tabela mistura números medidos, extrapolados e provenientes de relatórios sem uma convenção visual uniforme.
- A ordem de implementação não explicita critérios de desempate entre impacto, risco e custo.

## O que falta

- **Gate EPUBCheck:** `docs/SPEC.md:397,475` exige integração com EPUBCheck e zero erros. `OCR_UI_ANALISE_C2.md` não menciona esse gate, inclusive na lista de lacunas de `:637-643`. Existe apenas o teste `tests/unit/export/test_epub.py:171-180`; não há evidência de execução no documento nem nos relatórios consultados.
- **Validação de soluções de problemas:** `docs/SPEC.md:226,312` exige solução validável quando há “Mate em 2” ou estipulação similar. O caminho de importação em `src/caissa/ingest/pdf/importer.py:1317-1329` apenas preenche `stipulation`; não valida nem popula `solution`. A análise menciona linhas de solução, mas não cria esse gate.
- Não há evidência de mediana de três execuções para os números apresentados como base de decisão; o próprio documento declara que nenhum portão foi rodado.

## O que especificamente precisa mudar para eu aprovar

1. Corrigir a descrição de SOL-7 para refletir o `OR _looks_like_movetext`, ou apresentar uma medição real demonstrando por que o caminho não é acionado em scans.
2. Substituir a medição de `game_from_paragraph` por um comando reproduzível com `Paragraph` e `start_fen`, incluindo saída completa.
3. Atribuir `report§` ou `(medido nesta análise)` a todos os números; remover os que não tiverem origem.
4. Definir formalmente `--frio` e `--teclado`, ou substituí-los por instrumentos existentes, com critérios de aprovação, saída e sabotagem.
5. Preencher §11 com o histórico adversarial real.
6. Reescrever a alegação de “nenhuma repetição” e separar claramente `mhsp` já rejeitado da nova hipótese `RandomStroke`.
7. Acrescentar os gates de EPUBCheck e validação de solução, ou justificar explicitamente sua exclusão do escopo.

Nenhum arquivo foi alterado.

### Ciclo 2

VEREDITO: REPROVADO  
CICLO: 2

## Conferências feitas

| Item | Arquivo:linha | Confere? | Nota |
|---|---|---:|---|
| S-66/Niemeijer | `..\ChessVisionOFF_Puro\docs\ROADMAP_FASE7.md:1493-1503`; `ui/editor_model.py:302-328` | Sim | Corrigido para 4/4, 23/23, 41/41; média 0,25 não mediana. |
| SOL-7 | `docs/OCR_UI_ANALISE_C2.md:418-427`; `src/caissa/ingest/pdf/ocr_service.py:759-777,1163-1169` | Sim | A condição é `MOVETEXT` ou ≥50% de tokens de lance, somente para Tesseract. |
| Assinatura de `game_from_paragraph` | `src/caissa/ingest/pdf/games.py:188-200`; §5.2/§5.3 | Parcial | A assinatura e os resultados foram corrigidos e reproduzidos com `Paragraph`/`Text`; o bloco publicado não define `FEN`. |
| Origem dos números | §3.1, §4.1, §5.2; `SOL_REPORT.md:174-176`; `c1_rapidocr.md:73-78`; `F4_FIELD_REPORT.md:572-578`; `F4GPU_REPORT.md:347-348` | Sim, nos números auditados | Mais de dez números conferidos com relatório, linha ou marcação de medição/extrapolação. |
| `--frio`, `--teclado`, `--paralelo` | `docs/OCR_UI_ANALISE_C2.md:649-652,665-668,703-707` | Sim | Reescritos como modos novos propostos, não como comandos existentes. |
| Não repetição do `mhsp` | `docs/OCR_UI_ANALISE_C2.md:195-222`; `..\ChessVisionOFF_Puro\docs\EXPERIMENTS_FASE7.md:993-1019`; `augment.py:53-68` | Sim | Há hipótese nova (`RandomStroke`), ablação explícita e justificativa distinta da rejeição anterior. |
| EPUBCheck/estipulação | `docs/OCR_UI_ANALISE_C2.md:315-319,747-752`; `tests/unit/export/corpus.py:31-49`; `importer.py:1317-1329`; `diagram.py:360-372` | Sim | O teste pulado e a ausência de `Diagram.solution` estão corretamente documentados. |
| Tabela nova §3.1 | §3.1; `tools/f4_field_failures.py:249-289`; corrida `--barrados` | Sim | 115 anotados, 114 casados, 103 exatos, 11 diagramas errados e 27 casas erradas; 7 barrados por reparo. |
| Ordem §8 | `docs/OCR_UI_ANALISE_C2.md:847-885` | Sim | As dependências principais estão coerentes: D2→D1→exportação, A4→A5, C3→C4 e X3→X6. |

## Defeitos bloqueantes

1. **Os comandos publicados em §5.2/§5.3 não são reproduzíveis como escritos.**  
   Em `docs/OCR_UI_ANALISE_C2.md:497-508`, o código usa `start_fen=FEN` e passa `FEN`, mas nunca define `FEN`. A execução literal com o interpretador exigido terminou em:

   `NameError: name 'FEN' is not defined`

   Isso viola diretamente a exigência de reprodução e a regra de métrica reproduzível. É também um erro novo introduzido pela reescrita.

   Com `from chess import STARTING_FEN as FEN` acrescentado manualmente, os comportamentos centrais conferem: travessão gera 0 lances silenciosamente; `Nf6⩲` perde o roque colado; `Nf6±` gera 10 plies no reparador; a via de produto gera as contagens descritas.

## Defeitos não bloqueantes

- A execução real de `--out` em pasta temporária foi impedida pelas permissões somente leitura; a corrida foi executada em memória, sem escrita, e produziu os mesmos contadores.
- Não encontrei outra divergência factual nova nas sete exigências, na alavanca 17, na tabela §3.1 ou na ordem §8.

## O que falta

Procurei lacunas novas nas quatro áreas e nas seções §3–§7. Além do erro de reprodutibilidade do bloco de comandos, não encontrei uma nova lacuna funcional verificável além das 20 alavancas já registradas.

## O que especificamente precisa mudar para eu aprovar

Definir `FEN` dentro do bloco de §5.2/§5.3, por exemplo:

```python
from chess import STARTING_FEN as FEN
```

Depois, executar novamente os blocos exatamente como publicados e registrar a saída confirmada.

### Ciclo 3

VEREDITO: REPROVADO  
CICLO: 3

## Conferências feitas

| item | arquivo:linha | confere? | nota |
|---|---|---|---|
| 1 | `importer.py:688-690`; `export/book.py:339-354` | sim | O produto usa o finder vetorial; raster fica fora. |
| 2 | `export/book.py:339-354`; `ui/views/exportacao.py:384-392` | sim | Correções da janela não chegam ao exportador. |
| 3 | `ocr/page.py:336-354` | sim | Scan cai em `_whole_page`/`PAGE`. |
| 4 | `notation/legality_repair.py:143,148,337-339` | sim | `⧱Ⲳ` e travessões continuam ausentes. |
| 5 | `ingest/pdf/games.py:60,273`; `ocr/notation/movetext.py:55,100-104` | sim | Âncora fallback e roque colado confirmados. |
| 6 | `vision/detect/recall.py:232-318`; `tronco:qt/janela.py:1154-1161,1227` | sim | `recall_pack` não é usado pela janela. |
| 7 | `ocr/fusion.py:318-338` | sim | Decisão final ainda parte da âncora. |
| 8 | `ocr/lexicon.py:376-405`; `ocr/fusion.py:353-431` | sim | Sósias e prefixos realmente atravessam como apoio. |
| 9 | `export/pdf.py:113-118,733-750`; `export/fidelity.py:396-408` | sim | Fonte/fidelidade não preservam as figurinas no PDF. |
| 10 | `tronco:qt/janela.py:1304-1331`; `ocr/tesseract.py:197` | sim | Cancelamento só ocorre entre páginas. |
| 11 | `importer.py:164-191,1301-1318`; `tronco:qt/painel_de_resultado.py:1184-1203` | sim | Sinal por casa ainda morre na fronteira. |
| 12 | `tronco:ui/page_results.py:39,139-157`; `tronco:qt/janela.py:1923-1927` | sim | Cache/edições descartadas sem proteção completa. |
| 13 | `tronco:docs/EXPERIMENTS_FASE7.md:989-1016`; `tools/f4_field_failures.py` | sim | `mhsp` segue fora da produção; cor é o erro dominante. |
| 14 | `ocr/engines/glyph.py:171-179,247-256`; `tronco:text/leitor.py:427-433` | sim | Pós-cadeia do tronco não foi absorvida. |
| 15 | `tronco:qt/janela.py:463-468,527,939-941`; `ui/views/revisao_de_texto.py:101-170` | sim | Reabertura/OCR duplicado confirmados. |
| 16 | `ingest/pdf/games.py:158-178`; `notation/book_import.py:670` | sim | NAGs não percorrem toda a via PDF→GameScore. |
| 17 | `ocr_service.py:759-777,1163-1169` | sim | Perfil SOL-7 só entra em região/página com ≥50% de tokens de lance. |
| 18 | `tronco:docs/ROADMAP_FASE7.md:1493-1503`; commit `653f88b` | sim | Segunda opinião local não está ligada à UI. |
| 19 | `tronco:qt/trilho.py:254-286`; `tronco:qt/tabuleiro_editavel.py` | sim | Navegação/teclado ainda não fecham o fluxo. |
| 20 | `ocr/arbiter.py:385-412`; `ocr/engines/rapidocr.py:442-477` | sim | Confianças continuam em escalas incompatíveis. |

Também conferi as seções §3.1–§3.9, §4.1–§4.9, §5.1–§5.8, §6.1–§6.10 e §7.1–§7.7 contra código e relatórios.

A corrida em memória de `tools/f4_field_failures.py --barrados` reproduziu:

- 115 anotados, 114 casados, recall `0,9913`, precisão `1,0000`;
- 103 exatos, 11 diagramas errados, 27 casas erradas;
- 100/103 exportados, `field_exact=0,9709`;
- `repaired_squares=14`, `repaired_diagrams=7`;
- 10 reparos corretos e 4 errados;
- 10 erros de cor na leitura final e 11 pelo `argmax`.

O bloco literal de §5.2 foi executado com o `.venv`: código de saída 0 e stdout vazio, pois as chamadas não têm `print`. Avaliação separada confirmou os comentários: 7 lances com `⩲`, 10 com `±`, 0 com travessão e 7 lances na via `game_from_paragraph`.

## Defeitos bloqueantes

1. **Número sem origem em §11.**  
   Em `OCR_UI_ANALISE_C2.md:968-969`, o texto afirma “8 + 6 bloqueantes” dos críticos anteriores, mas não fornece relatório, veredito anterior ou marca de medição. Isso viola a regra explícita do próprio documento: todo número deve ter origem. O `CRITIC_CHARTER.md` não contém esse número. É uma falha de proveniência factual e impede aprovação.

## Defeitos não bloqueantes

1. O bloco de §5.2 é silencioso: os resultados ficam apenas em comentários, sem `print` ou `assert`. A execução foi bem-sucedida, mas o bloco não registra suas próprias medições.

2. §11:978 cita `c1_rapidocr.md:84-96`, mas o quinto item `twocol` limpo está na linha 97. A afirmação é correta; a faixa citada é imprecisa.

3. `docs/quality/0b/barrados.md` é um snapshot diferente da corrida atual: registra 20 entradas, enquanto a corrida atual produziu 11 barrados. O documento não usa diretamente esses números, mas falta identificar claramente a versão/população do relatório.

## O que falta

Procurei novas lacunas em `src/caissa`, `tronco:qt`, `tests/`, `tools/` e nos relatórios citados. Não encontrei uma lacuna adicional claramente distinta das já registradas em §6.9 e §7; os problemas de EPUBCheck, escala, alto contraste, acessibilidade e cancelamento já estão explicitamente documentados.

## O que especificamente precisa mudar para eu aprovar

- Acrescentar em §11 a origem verificável do “8 + 6” ou remover esse número.
- Corrigir a referência `c1_rapidocr.md:84-96` para incluir a linha 97.
- Preferencialmente transformar o bloco de §5.2 em uma verificação auto-observável com `print`/`assert`.

Não alterei arquivos.

### Ciclo 4

VEREDITO: APROVADO  
CICLO: 4

## Conferências feitas

| item | arquivo:linha | confere? | nota |
|---|---|---:|---|
| Alavancas 1–20 | `OCR_UI_ANALISE_C2.md:37-56` + fontes citadas | Sim | Rechecagem do ciclo 3 sem divergência nova. |
| §3.1 | `OCR_UI_ANALISE_C2.md:139-170`; `benchmarks/reports/f4_grade/failures.json` | Sim | 103/114 exatos, 27 casas erradas, 14 reparos. |
| §3.9 | `OCR_UI_ANALISE_C2.md:291-310` | Sim | Os quatro reparos errados e a divisão 2+2 são coerentes com §3.1. |
| §5.2 | `OCR_UI_ANALISE_C2.md:514-533` | Sim | Executado literalmente com o `.venv`; código 0. |
| Saída §5.2 | idem | Sim | `ok: ⩲→7/O-O, travessão→0/(), via de produto ±/⩲→7` |
| §11 e “8 + 6” | `OCR_UI_ANALISE_C2.md:977-1016`; `docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md:1-30` | Sim | Origem agora explícita e verificável. |
| `c1_rapidocr` | `docs/quality/sol/c1_rapidocr.md:84-97` | Sim | A faixa contém os dez itens; são 5 `twocol` limpos e 1 a 150 DPI. |
| SOL-7 | `ocr_service.py:759-777,1163-1169` | Sim | A condição `MOVETEXT` ou ≥50% está corretamente descrita. |
| Assinatura de `game_from_paragraph` | `games.py:188-200`; §5.2 | Sim | O bloco usa `Paragraph`, `Text` e `FEN` definido. |
| Proveniência numérica | §3–§7; relatórios citados | Sim | Não encontrei número novo sem fonte ou marcador. |
| Ordem §8 | `OCR_UI_ANALISE_C2.md:847-911` | Sim | Dependências declaradas permanecem coerentes. |

## Defeitos bloqueantes

Nenhum encontrado.

## Defeitos não bloqueantes

- A referência abreviada `c1_rapidocr.md` em §11 poderia repetir `sol/c1_rapidocr.md` por clareza, mas a origem está identificável no documento.
- Existem snapshots distintos de relatórios F4; os números publicados correspondem ao snapshot `f4_grade`, não ao `f4_barrados`.

## O que falta

Procurei erro novo nas três correções do ciclo 3, nas linhas novas do §11, na faixa `c1_rapidocr.md:84-97` e na coerência §3.1/§3.9. Não encontrei nova lacuna bloqueante.

## O que especificamente precisa mudar para eu aprovar

Nada. Os bloqueantes anteriores foram eliminados: o “8 + 6” tem origem, a faixa do RapidOCR está correta e o bloco §5.2 é reproduzível, auto verificável e terminou com saída `ok`. Pela Regra 5 da Carta, aprovo.
