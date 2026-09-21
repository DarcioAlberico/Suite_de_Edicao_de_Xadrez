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

---

# Fase 1 do ciclo 2 (código) — vereditos dos críticos

> Objeto: a árvore de trabalho dos dois repositórios com os passos A1–A10, B4, B7, C1, C7 e o
> relatório `OCR_UI_REPORT_C2.md`, antes do commit. Os dois reprovaram o ciclo 1 (Claude 7
> bloqueantes, Codex 6); o que mudou por cada item está em `OCR_UI_REPORT_C2.md` §0.1. **Ciclo 2
> (sobre os commits 8de189f/a921641): os dois APROVARAM.** As dívidas não bloqueantes do Claude
> (`test_arquitetura` por ordem, frase ao reimportar, pasta de recursos por livro, booleanos do
> `paralelo`) foram fechadas no commit seguinte; `bloqueio` com folga e A2 com portão de aceitação
> ficam para a fase 2.

## Crítico Claude — ciclo 1 (REPROVADO, 7 bloqueantes)

# Veredito do crítico — fase 1 do OCR/UI ciclo 2 (código + relatório)

VEREDITO: REPROVADO
CICLO: 1

Objeto: a árvore de trabalho dos dois repositórios **no instante 17:37 de 2026-09-20** (`git status` e
`git diff` guardados em `critico_f1/suite_status.txt`, `suite.diff`, `tronco_status.txt`, `tronco.diff`)
e `docs/quality/OCR_UI_REPORT_C2.md` (mtime 17:35). A outra sessão continuou a editar os dois checkouts
durante esta crítica (17:43 `tests/test_ui_retorno_modal.py`; 17:56–18:07 `qt/janela.py`, `config.py`,
`diagram_decisions.py`, `recall.py`, `rotulagem.py`, `revisao_de_texto.py`, `importacao.py`, `fusion.py`,
`book.py`, `ocr_service.py`, `docs/OCR_UI_ROADMAP_C2.md` com 5 mutações novas). Os cinco bloqueantes
abaixo (1–5) foram conferidos de novo na árvore das 18:07 e **continuam abertos**; os itens 6 e 7 do
"não bloqueante" já foram tratados pela outra sessão segundo a tabela de mutações (não verifiquei).

## Conferências feitas

| passo | comando / arquivo:linha | confere? | nota |
|---|---|---|---|
| A4/A5 bloco §5.2 | `critico_f1/bloco_52.py` (PYTHONPATH=src, .venv 3.11) → `bloco_52.out` | sim | `Nf6⩲` → 10 lances, `suffix='⩲'`; travessão → 6; via de produto `±/⩲/²/!?/∞` → 10 sem cauda perdida; `5.O-O` colado → 16; `OO/OOO` → 16; `O-O⩲` → 16 |
| A4 | `MOVE_SUFFIX_CHARS` | parcial | são **40** pontos de código, não "44" como o relatório diz; contém `- = / – — −` (o `_TRAILING_JUNK` e o `_MOVE_SHAPE` herdam isso — sem regressão encontrada, mas sem teste que o fixe) |
| A4 | `tests/unit/notation` | sim | 408 passed (o relatório diz "407+83"; é 325+83) |
| WP1/WP2/WP3/WP5 unitários | 20 arquivos de teste (`pytest_suite_passos.txt`) | sim | 425 + 408 passed, 0 falhas |
| WP3/WP4 tronco | 13 arquivos (`pytest_tronco_passos.txt`, offscreen, .venv 3.10) | sim | 463 passed, 2 skipped, 8 xfailed |
| A1 | `validate_detection.py --variant baseline --variant raw --variant recall-pack --runs 3` (`validate_detection.log`, 71 s/corrida) | sim | baseline 0,9913/1,0000 = recall-pack; raw 0,9478/0,9732 (112 det., 3 FP) — mediana de 3 |
| A1 | `tools/f4_field_failures.py --barrados` (`f4_barrados.log`) | sim | 114 casados, recall 0,9913, precisão 1,0000, `variant=recall-pack` |
| A1 | `src/caissa/vision/detect/recall.py:103-135` `_forced` | parcial | o produto não troca atributo; **o arnês dos benchmarks ainda trocava** `bd._extract_candidate_quads`/`hybrid.detect_diagrams` (o roadmap dizia "nada de troca de atributo de módulo"); a tabela de mutações das 18:05 diz que virou `ContextVar` |
| A2/A3 | `percurso --fluxo livro` Aagaard 31-38 (`percurso_livro.log`, `percurso_livro/percurso_20260920_204447.json`) | sim | PASSOU, 6 ações (1040/45322/61/1042/8/13622 ms); 13 localizados/13 lidos; `fonte=janela`; EPUB 13 diagramas, 1 corrigido, 1 verificado |
| A2 | `critico_f1/aagaard_conf.py` (import direto p31-38) | sim | 13 diagramas, todos `neural`, conf 1,000, 64 confianças por casa, `model_hash=a907f610…`, orientação 1,0 |
| A2 sabotagem | `--sabotar sem_raster` | não rodei | reproduzi o mecanismo pelo teste `test_corpus::…when_ocr_is_off` (`detect_raster_diagrams=False` → 0) |
| A3 sabotagem | `--sabotar sem_decisao` | não rodei (100 s) | o teste `test_book_decisions::…sabotage` cobre o mesmo caminho (6 passed) |
| A3 | `critico_f1/prova_subconjunto.py` → `prova_subconjunto.out` | **NÃO** | ver bloqueante 1 |
| A3 | `critico_f1/prova_imagens.py` → `prova_imagens.out` | **NÃO** | ver bloqueante 2 |
| C1 sabotagem | `scratchpad/wp3/sabotar_c1.py` (inverte os 64 índices) | sim | 3 failed, 2 passed |
| C1 | `finders.signal_from_prediction` × tronco `inference.BoardPrediction` (`probs` (64,13) ordem de leitura, `runner_up`, `decode.changed_squares`, `OrientedPrediction.alternative`) | sim | contratos batem; `a1_index_from_reading_index` correto; `square_confidences_from_holes` correto nas duas orientações |
| C7 | `paralelo` Kemeri 1-8 p80 + `--sabotar trancar_tudo` (`paralelo.log`, `paralelo_sabotado.log`) | sim | PASSOU (edição a 27 ms com importação viva, `importacoes_da_ponte=1`); sabotagem REPROVOU (aplicar não terminou em 2007 ms) |
| C7 | `qt/janela.py:533` + `qt/importador_de_livro.py:129-136` + `qt/painel_do_pdf.py:419` | **NÃO** | ver bloqueante 3 |
| C7 | `views/revisao_de_texto.py:383-420, 571-588` + `ocr/review.py:177-203, 289-302, 498-503` | **NÃO** | ver bloqueante 4 |
| A7 | log do `percurso --fluxo livro` após `salvar` bem-sucedido | **NÃO** | ver bloqueante 5 |
| A7/A10/C1-X5 | `-k Correcoes/Falha/titulo/Estados/Historico` dentro dos 463 do tronco | sim | xfail estritos reprovam de fato (8 xfailed, 0 xpassed) |
| A6 sabotagem | `pytest -p sabotagem_a6 tests/unit/export/test_pdf_glyphs.py` | sim | 3 failed, 3 passed |
| A9 sabotagem | `pytest -p sabotagem_a9 tests/unit/export/test_diagram_alt_text.py` | sim | 8 failed, 5 passed |
| B7 | `scratchpad/wp5/medir_glifos.py` e `--stacked 0` (`medir_glifos*.out`) | sim | calib `:` 10/10 → 0/10, `;` 1/1 → 0/1, CER 1,64 → 1,88 %; `=` 0/0 (verdade sem `=`) |
| B4 sabotagem | `scratchpad/wp1/bench_sabot_final.log` (lido, não rodado) | sim (é vermelha) | `langs=()` dá inv 18 (o "depois" é 19): a sabotagem não discrimina — o relatório diz isso com honestidade |
| B4/A4 medição final | `scratchpad/wp1/bench/wp1_final_20260920_173007.json` vs mtime de `src/caissa/ocr/page.py` (17:31:14) | **NÃO** | a "árvore final" do `bench_sol` (17:24–17:30) é **anterior** à costura de `page.py` que faz o `margin` chegar à fusão; nenhum `bench_sol`/`sol_gate` mediu o código como está (Carta §6) |
| A5 | `games_gate` normal e `--sabotar ancora` (logs do construtor, lidos) | sim | normal REPROVOU (Nunn 0/99, cobertura 0,04 — dito no §0.3); sabotagem 0 partidas ancoradas |
| A8 | `test_importer -k contested_layer_whose_ocr` (dentro dos 425) | sim | `text-layer/review`, item de revisão de página inteira |
| Relatório §0.2 | `OCR_UI_REPORT_C2.md:40-42` | **NÃO** | "(preenchido abaixo, §I)" — não existe §I; A6.4 remete a um "§Testes (fim do relatório)" que também não existe |
| Invariantes do tronco | `scratchpad/integ/pytest_tronco.log` (corrida da integração, 17:42) | **NÃO** | 3 failed / 4652 passed: `test_field_eval`, `test_strings::AccentTests` (os dois ditos no §0.3) **e `test_ui_retorno_modal` (46 → 47)** — este não está no §0.3; a catraca foi subida às 17:43 com motivo no docstring do teste, sem o relatório dizer |
| Invariantes da suíte | `scratchpad/integ/pytest_suite.log` | em curso | as duas suítes completas ainda corriam às 18:07 — o relatório foi escrito antes das invariantes |
| `git status` só com os caminhos do passo | `suite_status.txt` | parcial | `uv.lock` (`??`, mtime 04:38) não é da fase 1 — commit por caminho nomeado tem de o excluir |
| Anti-padrões §5 | `cipher._MOVE_BODY`, `field_set.jsonl`, `toolTip()` | sim | só a cauda alargou; `field_set.jsonl` intocado; rótulos não estão em `toolTip()` (a dica do botão de lado traz a legenda, o rótulo está no texto do botão) |

## Defeitos bloqueantes

1. **`export_book(document=)` escreve o livro inteiro importado quando as páginas pedidas são um subconjunto.**
   Onde: `src/caissa/export/book.py:363-383` (`_export_book`, ramo `document is not None`) +
   `ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/importador_de_livro.py:156-170` (`documento_para` devolve o
   `ImportResult` quando `pedidas <= importadas`). O documento não é recortado às `indices`; só o metadado é
   carimbado (`_stamp_selection`). Prova (`prova_subconjunto.out`): importação de 3 páginas, exportação com
   `pages=[0]` → EPUB com **as 3 páginas e 3 diagramas**, descrição "Páginas 1 de 3 do original", `summary()`
   "1 página(s)". Por que reprova: o usuário importa o livro no trilho, pede o EPUB dos capítulos 31–38 e
   recebe o livro todo dizendo que é 31–38 — resultado errado sem sinal (Carta §3.3, falha silenciosa).
2. **A exportação pelo trilho (o fluxo que A3 construiu) perde todas as imagens.** Onde:
   `src/caissa/ui/views/importacao.py:112-121` importa sem `asset_dir` → `Resource.path=None`
   (`importer.py:1616-1640`); `export/epub.py:193-196` pula recursos sem `path`; `book.py` aceita o
   `document=` sem conferir. Prova (`prova_imagens.out`, Kemeri p1-2, scan): via `document=` → EPUB de
   **8 280 bytes, 0 imagens**; reimportação → 8 199 886 bytes, 2 imagens; o `summary()` das duas diz
   "2 imagens". Antes desta fase o trilho reimportava com `asset_dir` e as tinha. Regressão silenciosa no
   produto para todo livro digitalizado, figura ou região abstida. (A tabela de mutações das 18:05 diz que
   a integração inseriu uma recusa + `asset_dir` em `importacao.py` — não verifiquei; o portão
   `percurso --fluxo livro` tem de passar a afirmar imagens no EPUB, senão volta.)
3. **C7 destrancou "Abrir PDF…" durante a importação e o resultado é atribuído ao livro atual.** Onde:
   `qt/janela.py:533` (`trancar=lambda _liberado: None`; antes `pdf.trancar` desligava `btn_abrir`,
   `qt/painel_do_pdf.py:419`), `qt/importador_de_livro.py:129-136` (`_chegou` usa `self._pdf_atual()` e
   não `self._pdf_importado`; `_abriu_livro` não cancela a importação). Cenário: importar A, abrir B enquanto
   corre, A termina → `_entregar_a_revisao(resultado_de_A, pdf=B)` → `ReviewQueue.from_import(...,
   document=B.stem)` e `estados_do_trilho(resultado_A, B)`. A fila de dúvidas de A fica sob o nome de B e a
   primeira decisão grava `labeling/revisao/B.json` com regiões de A. Só `documento_para` tem a guarda.
   Por que reprova: dado humano gravado no livro errado, sem sinal.
4. **A entrega automática à Revisão de texto apaga as decisões gravadas do livro.** Onde:
   `src/caissa/ui/views/revisao_de_texto.py:383-397` (`receber_importacao`) → `_importado` (403-420) faz
   `self.queue = ReviewQueue.from_import(...)` (log vazio) sobre a fila que `abrir()` tinha carregado de
   `labeling/revisao/<livro>.json` com as decisões do revisor; a próxima decisão chama `gravar` (571-588)
   → `self.queue.decisions().save(destino)` (`review.py:498-503`, sobrescreve). As regiões já decididas
   foram aplicadas na importação (viraram `verified`) e não estão na fila nova → saem do arquivo. Antes
   isso só acontecia com o clique explícito em "Importar (OCR)" da aba; agora acontece em **toda**
   importação do trilho — inclusive a parcial cancelada (`paralelo.log`: `revisao_de_texto_recebeu_a_fila=True`
   depois do cancelamento). Compatibilidade com sessões antigas (`labeling/revisao/*.json`) quebrada.
5. **A7 pergunta "Correções não gravadas" depois de a pessoa ter gravado.** Onde:
   `ui/page_results.py:221-234` (`paginas_editadas`) e `ui/editor_model.py:331-335` (`has_hand_edits` =
   "a FEN difere da leitura", nunca "não gravada"; nada zera `edited_by_hand` ao salvar, e o `salvos` que a
   janela já mantém para `mark_saved` não é consultado). Prova: `percurso_livro.log` — a ação 5 `salvar`
   gravou (decisão `fonte=janela`) e o `close()` seguinte registra "Correções não gravadas nas páginas [31]".
   Por que reprova: o aviso que existe para não perder trabalho mente a cada sessão normal (corrigir →
   gravar → fechar), e a pessoa aprende a clicar "Sim"; com tela, é uma modal a mais em todo fechamento.
6. **O portão de A3 conserta-se a si próprio.** Onde: `src/caissa/ui/audit/percurso.py:419-441`: se o
   gancho do tronco não gravar, o arnês grava pela API (`source="arnes"`), põe `acoes[-1].ok = True` e
   `Percurso.passou()` (103-112) não olha `notas`. O `--sabotar sem_decisao` só testa o lado da exportação.
   Se `qt/decisoes_de_diagrama.gravar_decisao` regredir (ela "nunca levanta" e devolve `None` em quatro
   caminhos), o portão continua PASSOU. Anti-padrão 1 (portão sem sabotagem que o derrube) no elo mais
   frágil do passo.
7. **O relatório não tem as invariantes e não diz tudo o que ficou vermelho.** §0.2 é "(preenchido
   abaixo, §I)" sem §I; A6.4 remete a um "§Testes" inexistente; a corrida completa do tronco feita pela
   integração (`integ/pytest_tronco.log`, 17:42) teve **3** vermelhos e o §0.3 lista 2 — o terceiro
   (`test_ui_retorno_modal`, 46 → 47 modais) foi resolvido subindo a catraca às 17:43, com motivo no
   docstring do teste mas sem uma linha no relatório; a suíte completa ainda corria às 18:07. E o número de
   B4/A4 "árvore final" (CER 0,0172, inventados 61) foi medido às 17:24–17:30, **antes** da costura de
   `ocr/page.py` (17:31) que faz `GlyphWord.margin` chegar à fusão — ou seja, nenhum `bench_sol`/`sol_gate`
   mediu o código em que `figurine_min_margin=0,25` (limiar sem medição, admitido no §0.3) está de fato
   ativo. O WP5 pediu explicitamente à integração que rodasse `sol_gate` antes do commit. Carta §6:
   métrica não reproduzível para o código de hoje.

## Defeitos não bloqueantes

- `qt/decisoes_de_diagrama.gravar_decisao` (71-111) devolve `None` em silêncio (suíte ausente, item sem
  retângulo, exceção no `record`) e `painel_de_resultado._registrar_decisao` (1170-1187) descarta o retorno:
  a pessoa vê "Amostra gravada" mesmo quando a correção não chegará ao EPUB. Precisa de frase no rodapé.
- `book.apply_diagram_decisions` (464-517) e `importer._diagram_node` só contam as decisões casadas; uma
  decisão que não casa nenhuma caixa (deriva de geometria, DPI mudado) some sem contador nem aviso.
- `painel_de_resultado.py:1187` lê `dpi=self._parametros().dpi` na hora de gravar; com Configurações…
  (commit 504f354) o DPI pode mudar entre a leitura e a gravação → `quad × 72/dpi` errado → decisão que
  nunca casa (silencioso).
- A2 sem portão de aceitação: o produto entrega como `Diagram` toda leitura raster, inclusive as que o
  `field_eval` do tronco barra (`field_eval.py:1041-1057`, ilegal ou `min_confidence` baixa —
  `f4_barrados.log`: 11 barrados, 11 casados-e-errados). No Aagaard os 13 saem a 1,000; no Chernev p121 o
  relatório admite 0,20 — e o EPUB troca a foto do diagrama por um tabuleiro errado (o alt text avisa, o
  desenho não).
- `is_move_token` com idioma aceita `KQRBN` + figurinas além da tabela do idioma (desvio do roadmap,
  explicado); `Hea!` **não** é apanhado nem por `is_unsupported_move` nem por `is_mangled_move`
  (`critico_f1` probe), ao contrário do que o §B4 "não fechou" afirma.
- `games._anchor_mismatch` (247-273) compara o lado da FEN com a numeração da coluna sem olhar
  `side_to_move_source`: uma FEN com lado por omissão pode reprovar uma coluna certa como `side_mismatch`
  (falha segura, mas é o mesmo "lado que ninguém leu" que A9 trata — os dois passos não se falam).
- `residency.shared_square_classifier` é um segundo classificador no processo da janela (o tronco tem o
  seu no `OcrService`); e a importação, que agora usa o classificador (A2), não tranca o treino (C7).
- `rotulagem.abrir` (na árvore das 17:37) renderizava a página na thread da janela a cada "Abrir PDF"
  (`render_rgb` 27–164 ms medidos com a máquina carregada; a mutação das 18:05 diz 209 ms com o SHA-256 e
  moveu para `showEvent`); os portões `quadros`/`bloqueio` não foram rerodados depois de C7 no relatório.
- `perguntar_descarte` decide por `platformName() == "offscreen"`: um `QT_QPA_PLATFORM=offscreen` por
  acidente numa sessão real descarta edições sem perguntar (só `warning` no log).
- `Ponte._entregar_a_revisao` engole a exceção da aba (log) — a fila fica desatualizada sem frase.
- `_forced` em `recall.py` (17:37) ainda trocava dois atributos de módulo no arnês de benchmark, com
  `try/finally` — o produto não passa por ali; a mutação das 18:05 diz que virou `ContextVar`.
- `MOVE_SUFFIX_CHARS` = 40 pontos (relatório: 44); `tests/unit/notation` = 325+83 (relatório: 407+83);
  `translate_san("O-O","de")` passou a `0-0` (intencional, sem teste que o fixe).
- `tests/test_field_eval::…mediu_o_codigo_de_hoje` e `test_strings::AccentTests` continuam vermelhos
  (pré-existentes, admitidos, não consertados).

## O que falta

1. Corrigir 1–6 acima e fazer os arneses provarem: `percurso --fluxo livro` tem de afirmar (a) o número de
   páginas do EPUB == páginas pedidas e (b) imagens/figuras presentes quando o `ImportResult` as declara;
   `paralelo` tem de abrir outro livro durante a importação e afirmar que a fila e o trilho não trocam de
   livro; um teste da aba afirma que a fila carregada com decisões **não** é substituída por
   `receber_importacao` (mesclar, não trocar); `perguntar_descarte` só para páginas com edição **não gravada**
   (consultar `salvos`/zerar `edited_by_hand` ao gravar) e o `percurso --fluxo livro` afirma que o `close()`
   depois de `salvar` não avisa; `Percurso.passou()` reprova quando a decisão veio do arnês.
2. Invariantes de verdade, no relatório: `pytest tests` da suíte (com `--ignore` do roadmap) e do tronco
   (com os 3 vermelhos nomeados e a catraca de modais justificada no §0.3), `sol_gate --report-only` sobre
   um `bench_sol` rodado **depois** de `page.py` (com `margin` chegando à fusão e o 0,25 ativo), e o
   `git status --short` final sem `uv.lock` nem arquivos alheios.
3. §I/§Testes escritos; corrigir os números que o código contradiz (40, 325+83, `Hea!`).
4. Commits por caminho nomeado, um em cada repositório com o hash do outro — depois de 1–3.

## O que especificamente precisa mudar para eu aprovar

- `export_book(document=)`: recortar o `Document` às `indices` (ou `documento_para` só devolver quando
  `pedidas == importadas`) e um teste `test_book_decisions` com 3 páginas importadas e `pages=[0]` que exige
  1 página no EPUB.
- O `ImportResult` da janela com `asset_dir` de processo **e** `export_book` recusando (com motivo) um
  `document=` cujos recursos de imagem não têm bytes em disco; `percurso --fluxo livro` afirmando as imagens.
- `Ponte._chegou` usa `self._pdf_importado` e ignora (com frase no rodapé) um resultado de outro livro;
  ou `_abriu_livro` cancela a importação em curso antes de trocar de livro.
- `receber_importacao`: mesclar o `from_import` com a fila carregada (manter `log`/decisões, substituir só
  os itens) e nunca entregar um resultado `canceled` como fila nova; teste com `labeling/revisao` de
  `tmp_path` que prova que uma decisão anterior sobrevive a uma importação do trilho + nova decisão.
- `paginas_editadas` só com edição não gravada; xfail estrito para o caso "gravou e fechou → sem pergunta".
- `percurso.py`: sem gravação pela API dentro do portão (ou `passou()` = REPROVOU quando `fonte != "janela"`),
  e uma sabotagem que desligue `gravar_decisao` e faça o portão reprovar.
- Relatório com §0.2 preenchido (os quatro comandos das invariantes e os seus números, o `sol_gate` sobre a
  árvore final real), §0.3 completo (catraca de modais, `test_ui_retorno_modal`), e os três números
  corrigidos.

Regra 5 da Carta: quando estes sete bloqueantes acabarem — e os portões executados provarem cada um —
aprovo; o que a fase 1 construiu (A1 medido e reproduzido, A4/A5/B7 com sabotagens que derrubam, C1 com a
paridade e a sabotagem dos 64 índices, A6/A9 com as duas sabotagens) está correto no que medi.

## Crítico Codex — ciclo 1 (REPROVADO, 6 bloqueantes)

VEREDITO: REPROVADO
CICLO: 1

## Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---:|---|
| Briefing/charter/roadmap | `brief_critico_fase1.md`, `CRITIC_CHARTER.md`, `OCR_UI_ROADMAP_C2.md` | Sim | Critérios de sabotagem, falha silenciosa e métrica não reproduzível aplicados. |
| Diff completo | `git diff` + todos os `??` nos dois repositórios | Sim | Revisados código, testes, documentação, concorrência e integrações. |
| A1 | `src/caissa/vision/detect/recall.py:103-136` | Não | Ainda troca atributos globais de módulos em `_forced`; não é thread-safe. |
| A3 | `src/caissa/ui/views/exportacao.py:381,411`; `src/chess_diagram_ocr/qt/janela.py` | Parcial | `document=` foi integrado, mas há fallback silencioso e recursos de imagem sem `asset_dir`. |
| B4 | `OCR_UI_REPORT_C2.md:846-855`; roadmap l.232 | Não | `langs=()` não altera o resultado; a sabotagem não reprova. |
| B7 | `OCR_UI_REPORT_C2.md:1109-1110`; roadmap l.240-242 | Não | Recall de `=` continua não mensurável; o portão exige recall positivo. |
| Testes da suíte | `pytest --capture=no -p no:cacheprovider ...` | Não reproduzível | `10 passed, 10 errors`; os erros são `FileNotFoundError` por falta de diretório temporário gravável. |
| Testes do trunk | `pytest --capture=no -p no:cacheprovider ...` | Sim | `22 passed, 1 xfailed, 3 subtests passed`. |
| Integridade operacional | `git status --short` nos dois repositórios | Sim | Nenhum arquivo foi alterado por mim; as suítes paralelas não foram interrompidas. |

## Defeitos bloqueantes

1. **Monkeypatch global restante no A1**

   Onde: `Suite_de_Edicao_de_Xadrez/src/caissa/vision/detect/recall.py:103-136`.

   `_forced()` substitui `bd._extract_candidate_quads` e `hybrid.detect_diagrams` globalmente. Duas execuções concorrentes de variantes podem salvar/restaurar referências incorretas.

   Isso contradiz diretamente o roadmap: “sem trocar globais” e “nada de troca de atributo de módulo”. Reprovação imediata do A1.

2. **Fallback silencioso na exportação A3**

   Onde: `src/caissa/ui/views/exportacao.py:379-381`.

   Qualquer exceção em `documento_para(...)` é capturada e convertida em `documento = None`. A exportação continua, reimportando o PDF, sem informar que perdeu o documento já importado.

   É exatamente uma falha silenciosa com resultado plausível.

3. **Documento reutilizado sem recursos de imagem materializados**

   Onde: `src/caissa/ui/views/importacao.py:114`; `src/caissa/ingest/pdf/importer.py:377,1624-1634`; `src/caissa/export/epub.py:194`.

   A importação da janela não define `asset_dir`; os `Resource` ficam com `path=None`. Quando esse `Document` é reutilizado pela exportação, o EPUB ignora esses recursos e o HTML cai em placeholder. A operação pode terminar como “sucesso” com páginas/imagens perdidas.

4. **Sabotagem B4 não funciona**

   O próprio relatório registra que `langs=()` produz o mesmo placar (`18` contra `19`), sem mudança de lances/CER. O requisito do portão é que a contagem volte ao comportamento atual. Portanto, B4 não está fechado.

5. **Portão B7 não foi satisfeito**

   O relatório admite que `=` tem `0/0`, logo o recall não é mensurável. O roadmap exige recall positivo de `=`/`:`/`;`. Teste sintético não substitui a medição no corpus rotulado.

6. **Métricas principais não foram reproduzidas**

   O charter determina reprovação quando a medição não pode ser reproduzida, com pelo menos três execuções e mediana. Neste sandbox, a escrita temporária foi negada; mesmo usando `--capture=no` e sem cache, a suíte apresentou erros internos de `tempfile`. Assim, os números reportados não podem ser independentemente aprovados neste ciclo.

## Defeitos não bloqueantes

- O relatório é contraditório: afirma em `OCR_UI_REPORT_C2.md:35` que `document=` já passa pelo trilho, mas em `:585` afirma que ainda falta implementar.
- `DiagramDecisions.record()` faz carregar–alterar–gravar sem lock de arquivo; dois processos podem perder decisões concorrentes.
- O relatório ainda registra pendências conhecidas de A5/Nunn e calibração de glifos, embora algumas estejam declaradas como fora do escopo imediato.

## O que falta

- Remover totalmente o monkeypatch global do recall e passar `RecallOptions` pela API comum do trunk e da suíte.
- Transformar falha de `documento_para` em erro visível, sem cair silenciosamente em reimportação.
- Materializar/revincular `asset_dir` antes de reutilizar um `ImportResult` na exportação.
- Corrigir a sabotagem B4.
- Obter amostra rotulada contendo `=` e medir o portão B7 real.
- Reexecutar os gates num ambiente com temporário gravável, mínimo de três vezes, reportando medianas.
- Corrigir a contradição do relatório.

## O que especificamente precisa mudar para eu aprovar

A1, A3, B4 e B7 precisam passar seus portões e sabotagens; os fallbacks silenciosos precisam desaparecer; e todas as métricas numéricas precisam ser reproduzidas com três execuções. Só depois disso o relatório deve ser atualizado para refletir exatamente o código vigente.

## Crítico Claude — ciclo 2 (APROVADO; tronco 8de189f, suíte a921641)

# Veredito do crítico — fase 1 do OCR/UI ciclo 2 — CICLO 2

VEREDITO: APROVADO
CICLO: 2

Objeto: tronco `8de189f` (19:24) e suíte `a921641` (19:25), árvores limpas (`c2/tronco_status.txt`
vazio; `c2/suite_status.txt` só `?? uv.lock`, fora do commit como pedido); diffs `git diff HEAD~1`
em `c2/suite.diff` (9.926 l.) e `c2/tronco.diff` (3.399 l.); `docs/quality/OCR_UI_REPORT_C2.md` §0.1–0.3.

## Conferências feitas

| bloqueante do c1 / item | comando ou arquivo:linha | confere? | nota |
|---|---|---|---|
| 1 subconjunto | `export/book.py:367-376, 449-462` `_covers_exactly`; `qt/importador_de_livro.py documento_para` (== exatas); `c2/prova_reuso.py` → `prova_reuso.out` | sim | 3 importadas + `pages=[0]` → **1 página no EPUB, reimportou** (aviso no log); páginas exatas → **não reimporta**, 3 diagramas; `test_a_result_of_more_pages_than_asked_is_not_written_as_it_is` passa |
| 2 imagens | `views/importacao.py:32-46, 141` (`asset_dir` de processo, `atexit`); `book.py:377-388` `_images_on_disk`; `prova_reuso.out`; `percurso --fluxo livro` | sim | documento sem imagens em disco → reimporta (aviso); `imagens_no_epub=13` no Aagaard, EPUB 1.312.420 bytes |
| 3 trocar de livro | `qt/janela.py:1021-1025` (cancela + frase), `importador_de_livro.py:129-151` (`_pdf_importado`, descarta com frase, parcial cancelado não vai à fila); `paralelo --outro-livro` → `c2/paralelo_outro.log` | sim | PASSOU: `resultado_descartado=True, trilho_sem_estados_do_anterior=True, fila_nao_e_do_anterior=True, revisao_no_livro_novo=True`; `--sabotar sem_descarte` → **REPROVOU** (`resultado_descartado=False`); `test_o_resultado_de_outro_livro_e_descartado`, `test_o_parcial_cancelado_nao_vai_a_fila_de_revisao` passam |
| 4 decisões apagadas | `ocr/review.py:280-322` `carry_over`; `views/revisao_de_texto.py:392-439` | sim | `test_decisions_taken_before_survive_a_fresh_import_result` (lê o arquivo de decisões em `tmp_path`: 1 → 2 entradas, `KEEP_IMAGE`+`ACCEPT`; parcial cancelado recusado) passa |
| 5 «não gravadas» após gravar | `ui/editor_model.py:92-97, 345-361` (`unsaved_hand_edit`, `mark_saved`, `has_unsaved_hand_edits`); `painel_de_resultado.py:832, 1159`; `page_results.py:116, 170, 194, 244` | sim | `c2/livro.log`: **0** ocorrências de "Correções não gravadas" depois do `salvar` (c1: 1); `test_gravar_a_correcao_e_fechar_nao_pergunta` passa; xfail estrito da sabotagem continua XFAIL |
| 6 portão que se aprovava | `ui/audit/percurso.py:248-252, 431-451` (sem `record`; `ok` exige `fonte == "janela"`) | sim | `--sabotar sem_gancho` → **REPROVOU** no passo 5 (`decisao.ok=False`, nota nomeia o gancho); sem sabotagem PASSOU, `fonte=janela` |
| 7 relatório | §0.2 (tabela de invariantes), §0.3, l.741 (40), l.791 (408), l.934 (`Hea!` corrigido), `uv.lock` fora | sim, com ressalvas | ver não bloqueantes 1–3 |
| A1 sem monkeypatch (Codex) | `config.py:153-167` `RECALL_EM_VIGOR`/`recall_em_vigor`; `board_detection.py:858`, `hybrid.py:645`; `recall.py:100-115` | sim | `validate_detection --variant raw --variant baseline --runs 1` (`c2/validate_detection.log`): raw **0,9478/0,9732**, baseline **0,9913/1,0000** — o arnês por `ContextVar` mede o mesmo; `test_recall_pack` 23 passed |
| B4 sabotagem `passo_b4` | `fusion.py:94, 141-146, 299-304, 231, 436, 450, 510, 521`; `ocr_service.py` (`config.fusion` → `FusionConfig`) | sim, remedido | `bench_sol --strata native --filter real:` na árvore commitada (`c2/bench_b4_on.log`/`off.log`): ligado **0,0140 / 0,9296 / 19**; desligado **0,0149 / 0,9083 / 25** — idêntico ao §0.2, e agora medido no código commitado (o `on` da integração terminou 18:06:20 e `fusion.py`/`ocr_service.py` mudaram 18:05:34/18:07:17 — só o interruptor; a remedição fecha a dúvida) |
| `record()` com lock | `diagram_decisions.py:284-327` (`O_CREAT|O_EXCL`, stale 60 s, timeout 10 s) | sim | — |
| `documento_para` que falha é dito | `views/exportacao.py:385-392` | sim | rodapé + log |
| `gravar_decisao` → `None` é dito | `painel_de_resultado.py:1195-1201`; DPI da leitura (`params_of`) | sim | — |
| testes tocados | suíte 16 arquivos (`c2/pytest_suite.txt`) **265 passed**; tronco 10 arquivos (`c2/pytest_tronco.txt`) **410 passed, 8 xfailed**; `test_packaging` 36 passed com `LIMITE=1998` = `wc -l` | sim | — |
| catraca de modais | `tests/test_ui_retorno_modal.py` (LIMITE 47, MODAIS_DE_DECISAO 15, motivo no docstring) | sim | passa |
| `bloqueio` | §0.2: 14,8 / 16,2 / 14,5 ms (c21: 6,6) | registrado, não remedi | ver não bloqueante 4 |

## Defeitos bloqueantes

Nenhum. Os sete do ciclo 1 estão fechados no código, com teste ou arnês que reprova quando o
comportamento antigo volta (sabotagens `sem_gancho`, `sem_descarte` executadas por mim), e os três
números que a Carta §6 manda remedir (recall raw/baseline, B4 on/off) reproduzem ao milésimo.

## Defeitos não bloqueantes

1. **`test_arquitetura::test_o_arnes_de_auditoria_importa_sem_qt[*]` reprova por ordem** quando
   qualquer teste que carrega PyQt6 roda antes no mesmo processo: `pytest tests/unit/ui` com
   `.venv-pack` → **15 failed, 294 passed** (`c2/pytest_ui.txt`); sozinho 19 passed. O arquivo não
   mudou nesta fase (é pré-existente e só aparece porque a integração rodou a suíte inteira **com**
   Qt no caminho — o comando do roadmap §0 não o põe). O §0.2 diz "15 failed" na 1.ª corrida e
   "3.824 passed" na 2.ª sem explicar o que mudou entre as duas; a invariante como o roadmap a define
   (sem `.venv-pack`) não está reportada. Registrar a regra ("esse teste corre em processo próprio")
   ou pôr o teste em subprocesso.
2. A corrida do tronco do §0.2 (19:22, `integ/pytest_tronco2.log`) teve **3** vermelhos, e o terceiro
   era `test_packaging::test_a_janela_nao_volta_a_crescer` (1.998 > 1.992) — a catraca foi subida
   depois e o commit passa (36 passed); o §0.2 diz "3 failed … pré-existentes + catraca de modais",
   que era a corrida das 17:42. A invariante do commit não foi rodada depois da última edição.
3. `export_book` que **recusa** o `document=` (subconjunto, imagens ausentes) só avisa no log
   (`book.py:371, 383`): a pessoa pediu "exportar" esperando segundos e recebe minutos de OCR sem
   frase no rodapé. `documento_para` que **falha** é dito; o que é **recusado** não.
4. `bloqueio` 6,6 → ~15 ms (2 de 3 PASSOU, 1 viola por 0,2 ms): custo real de C7 (`abas.abrir` na
   thread da janela), honestamente registrado "no limite" — fica como dívida nomeada para a fase 2.
5. `_pasta_de_recursos()` é **uma** pasta por processo para todas as importações: chaves
   `diagrama-p31-0001.png` colidem entre livros com as mesmas páginas; uma exportação em curso
   sobre o resultado antigo lê arquivos que a importação seguinte sobrescreve (caso raro: exportar
   enquanto se importa outro livro; a tranca não o impede).
6. `ImportadorDoLivro._concluiu` ainda diz "Importação cancelada: N página(s) … podem ser
   exportadas" quando o cancelamento foi por troca de livro — a ponte descarta logo a seguir com a
   frase certa; duas frases contraditórias no rodapé em 1 s.
7. `paralelo._relatorio`: `all(detalhes["troca_de_livro"].values())` inclui os nomes dos livros
   (strings, sempre verdadeiras) — funciona, mas um campo booleano novo esquecido não reprovaria.
8. Mantidos do c1 (não bloqueantes, admitidos no §0.3): A2 sem portão de aceitação (leituras
   raster barradas pelo `field_eval` viram `Diagram` desenhado); `_anchor_mismatch` sem
   `side_to_move_source`; `figurine_min_margin=0,25` sem medição; `test_field_eval`/`AccentTests`
   vermelhos pré-existentes.

## O que falta

Nada para a fase 1 valer como fechada. Para a fase 2 levar: o item 1 (regra ou subprocesso para
`test_arquitetura`), o 3 (frase no rodapé quando a exportação reimporta), o 4 (`bloqueio` com
folga, já no roadmap C2), e a lista do §0.3.

## O que especificamente precisa mudar para eu aprovar

Nada mais — aprovado. Por quê (Regra 5): cada bloqueante do ciclo 1 tem agora (a) o código corrigido
que li, (b) um teste ou arnês que reprova o comportamento antigo e que eu executei, e (c) os
portões numéricos remedidos por mim no commit (`validate_detection` raw/baseline, `bench_sol` B4
on/off, `percurso --fluxo livro` com decisão da janela e 13 imagens, `paralelo` com troca de livro).
O que resta são dívidas nomeadas, nenhuma das quais faz o produto dar resultado errado em silêncio.

## Crítico Codex — ciclo 2 (APROVADO)

VEREDITO: APROVADO
CICLO: 2

## Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| A1 | `recall.py:101-116`; `test_recall_pack.py:148-158` | Sim | `ContextVar` com `set/reset`; 23 testes passaram, incluindo isolamento entre threads. |
| A3 | `exportacao.py:382-393`; `importacao.py:33-46,128-142`; `book.py:367-473` | Sim | Falha é emitida no rodapé/log; `asset_dir`, cobertura exata e imagens em disco estão protegidos. |
| B4 | `fusion.py:108-146,287-304`; `ocr_service.py:100-105,1014-1018` | Sim | `FusionConfig.passo_b4=False` chega via `SOL_CONFIG`; teste de sabotagem passou. 19 testes de fusão passaram. |
| B7 | `OCR_UI_ROADMAP_C2.md:290`; `test_glyph_postchain.py` | Sim | O portão de `=` foi honestamente reescrito como não mensurável no corpus; permanece teste sintético real. |
| Invariantes | `OCR_UI_REPORT_C2.md:96-110` | Sim | §0.2 registra comandos, números, sabotagens e falhas abertas. |
| Segunda lista do §0.1 | `importador_de_livro.py:129-180`; `percurso.py:423-452`; `painel_de_resultado.py:1183-1200` | Sim | Descarte de livro errado, carry-over, gate não autoaprovável, DPI correto e falha de registro sinalizada. |
| Detecção do tronco | `test_board_detection_recall.py`, `test_detection.py` | Sim | 95 testes + 14 subtestes passaram. |

## Defeitos bloqueantes

Nenhum. Os seis bloqueantes do ciclo 1 foram corrigidos no código commitado e possuem cobertura correspondente. A aprovação segue a Regra 5 da Carta.

## Defeitos não bloqueantes

- Suítes dependentes de `tempfile` não puderam rodar neste sandbox sem diretório temporário gravável; as verificações em memória e os testes sem temporário passaram.
- Há `uv.lock` e `.claude/` não rastreados, fora dos commits revisados.
- `=` ainda não tem corpus rotulado; isso está explicitamente declarado como trabalho humano futuro, não mascarado como métrica.

## O que falta

Nada para fechar a fase 1.

## O que especificamente precisa mudar para eu aprovar

Nada. A fase 1 está aprovada porque os bloqueantes foram encerrados, as sabotagens agora derrubam os portões quando apropriado, e o relatório distingue claramente o que foi medido do que permanece aberto.

---

# Fase 2 do ciclo 2 (código) — vereditos do crítico Codex

> Objeto: os commits da fase 2 (tronco `2077410`…`167d52d`, suíte `b156222`…`dcc72d7`) e o
> relatório `OCR_UI_REPORT_C2_FASE2.md`. Um crítico só, por pedido: o Codex (`codex exec -s
> read-only --ephemeral`, GPT-5.6, esforço `high`; briefing
> `brief_critico_fase2.md`, o mesmo formato da fase 1). **Ciclo 1: REPROVADO, 5 bloqueantes**;
> o que mudou por item está em `OCR_UI_REPORT_C2_FASE2.md` §0.1 (segunda lista). Antes de
> chamar o crítico, a revisão do próprio construtor já tinha fechado quatro defeitos
> (recorte que não virava, armadilha do `Tab`, tarefas com pai, parecer preso ao índice —
> §0.1, primeira lista) — o crítico achou o quinto e o sexto (a calibração das faixas e a
> `Tarefa` de `_rodar`) e duas falhas silenciosas. **Ciclo 2 (sobre tronco `b20cd6f`, suíte
> `c13baca`; sandbox `workspace-write` com `TEMP` no workspace, para os portões correrem):
> APROVADO, 0 bloqueantes** — os três não bloqueantes (o cabeçalho do relatório com o hash do
> tronco antes das correções, espaços em branco, os portões absolutos de CER vermelhos como
> declarado) fechados no commit seguinte, salvo o terceiro, que é o estado honesto do §0.3.

## Crítico Codex — ciclo 1 (REPROVADO, 5 bloqueantes)

VEREDITO: REPROVADO
CICLO: 1

## Conferências feitas

| Passo | Comando/arquivo:linha | Confere? | Nota |
|---|---|---:|---|
| Diff suíte | `git diff beb8a71..dcc72d7` — 39 arquivos, +4098/-143 | Sim | Diff inteiro lido. |
| Diff tronco | `git diff 8de189f..167d52d` — 34 arquivos, +1694/-52 | Sim | Diff inteiro lido. |
| Pytest suíte | módulos tocados, `-s -p no:cacheprovider` | Parcial | 72 passaram, 8 erros por ausência de diretório temporário utilizável; nenhum erro de asserção observado. |
| Pytest tronco | módulos tocados, `-s -p no:cacheprovider` | Parcial | 270 passaram, 86 falharam por `tempfile`/`TemporaryDirectory`; 3 xfails. |
| Bench NAG | `notation_integrity.py --what nags` e sabotagem | Sim | Normal passou; sabotagem produziu 0 NAG e reprovou. |
| Bench coordenadas | `coordinate_survey.py` normal/sabotagem | Parcial | Números reproduzidos: 10639 `a-h`, 0 `h-a`; sabotagem inverteu para 10639 `h-a`. Escrita do JSON foi negada. |
| Bench segunda opinião | `second_opinion_gate.py` normal/sabotagem | Não | Normal não chegou ao gate por tempdir/cache; JSON existente registra 23/27. Sabotagem reproduziu 0/27. |
| JSONs SOL | `benchmarks/reports/sol/f2_*.json` | Parcial | Números principais conferem com o relatório, mas todos registram `commit: beb8a71`, não `dcc72d7`. |
| JSONs UI | `benchmarks/reports/ui` | Parcial | Há passes finais, mas também falhas anteriores de C2, C8 e C9; não é uma série inteiramente limpa. |
| Estado da árvore | suíte `git status` | Observação | Não alterei arquivos. Durante a auditoria apareceu um diff externo não commitado que já corrige a calibração dos strips; foi preservado. |

## Defeitos bloqueantes

1. **B6/B2 — calibração semântica quebrada para `tesseract_strips`.**
   Em `src/caissa/ingest/pdf/ocr_service.py:76`, os strips recebem o engine `tesseract_strips`; em `:1081-1089` são pontuados com esse nome; em `:1351-1371`, `_calibrators` procura a tabela usando exatamente esse engine. A configuração possui tabela para `tesseract`, mas não para `tesseract_strips`, portanto os strips ficam na escala bruta enquanto o Tesseract principal é calibrado. Isso torna a fusão incomparável e invalida a alegação de B6. O diff externo não commitado adiciona precisamente o mapeamento ausente.

2. **Os benchmarks não comprovam o commit avaliado.**
   Os JSONs `f2_*` registram `environment.commit = beb8a71`, embora o commit sob revisão seja `dcc72d7`. Logo, os números do relatório não demonstram o comportamento do diff final.

3. **Métrica obrigatória não reproduzível neste ambiente.**
   O gate normal de segunda opinião não executou por falta de diretório temporário utilizável e erro de artefato pré-compilado no cache. Pelo próprio critério do briefing/charter, uma métrica que não pode ser reproduzida não pode aprovar.

4. **C2 — fechamento pode aceitar a janela com `QThread` ainda vivo.**
   `src/chess_diagram_ocr/qt/janela.py:1363` cria a tarefa como filha da janela. Em `:2022-2025`, `closeEvent` espera apenas um prazo fixo, registra aviso se a thread ainda estiver ativa e aceita o fechamento mesmo assim. A destruição da janela pode então abortar o processo com `QThread: Destroyed while thread is still running`.

5. **Falha de B2 pode ser descartada silenciosamente.**
   `src/caissa/ingest/pdf/ocr_service.py:1055-1065` captura qualquer exceção da leitura dos strips, registra apenas em `debug` e retorna nenhum candidato. O pipeline continua como se B2 não existisse, sem nota na decisão ou no relatório.

## Defeitos não bloqueantes

- `src/chess_diagram_ocr/service.py:777` e `:791` usam `getattr(..., None/False)` para campos de orientação. Um contrato quebrado pode cair silenciosamente na orientação padrão.
- `src/caissa/ingest/pdf/ocr_service.py:667-669` transforma falha de layout em fallback de leitura integral; há log, mas não há sinal claro no resultado entregue à UI.
- B8, C8 e C10 permanecem com evidência limitada conforme o próprio relatório: B8 não teve efeito estatístico conclusivo, C8 não demonstrou aprendizagem no corpus escolhido e C10 não teve amostras de orientação preta.

## O que falta

- Corrigir e commitar o mapeamento de calibração `tesseract_strips → tesseract`.
- Reexecutar os benchmarks no commit final, com diretório temporário gravável, cache limpo e três repetições.
- Reproduzir o gate normal de segunda opinião.
- Corrigir o ciclo de vida da thread no fechamento da janela.
- Tornar falhas de strips/layout/orientação observáveis no resultado, não apenas em logs.

## O que especificamente precisa mudar para eu aprovar

1. Calibrar `tesseract_strips` com a tabela de `tesseract` tanto na pontuação inicial quanto na fusão.
2. Garantir que os JSONs tragam `commit: dcc72d7` e correspondam exatamente ao relatório.
3. Fazer `closeEvent` cancelar e aguardar corretamente, ou manter a tarefa viva sem destruir a janela enquanto ela roda.
4. Expor falhas de B2/layout/orientação como notas ou estados verificáveis.
5. Entregar novamente os pytest e os três gates reproduzíveis em ambiente com escrita temporária.

## Crítico Codex — ciclo 2 (APROVADO)

VEREDITO: APROVADO
CICLO: 2

## Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| B2/B6 | [`arbiter.py:182-188,241-257,456-494`](<C:/Python-Chess2/Suite_de_Edicao_de_Xadrez/src/caissa/ocr/arbiter.py:182>) e `test_movetext_strips.py:177,205` | Sim | `tesseract_strips` usa a tabela Tesseract na pontuação e em `_calibrators`; testes passaram. |
| B1/B2 | [`page.py:645-760`](<C:/Python-Chess2/Suite_de_Edicao_de_Xadrez/src/caissa/ocr/page.py:645>) e `ocr_service.py:1052-1099` | Sim | Falhas deixam notas; candidatos são fatiados por palavra. Testes passaram. |
| Benchmarks | `f3_on`, `f3_b1_off`, `f3_b2_off` | Sim | Todos registram `environment.commit=3bbcf23`; configurações e números batem com §B1/§B2/§0.2. Uma corrida por configuração, conforme justificativa documentada. |
| B9 | `f2_on` × `f2_b9_serial` | Sim | Comparação independente: 274/274 itens iguais nos campos medidos. |
| C3 | `second_opinion_gate.py --failures ...` | Sim | PASSOU: 23/27 casas, 85,2%; sabotagem não passou. |
| C2 | [`janela.py:1365-1373,2035-2042`](<C:/Python-Chess2/ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/janela.py:1365>) e [`leitura.py:167-177`](<C:/Python-Chess2/ChessVisionOFF_Puro/src/chess_diagram_ocr/qt/leitura.py:167>) | Sim | Tarefas sem pai, slots protegidos por `_se_viva`, aquecimento cancelado no fechamento. |
| C8/C10 | `tabuleiro_editavel.py:252-305`; `painel_de_resultado.py:1416-1426` | Sim | Tab sai do tabuleiro; recorte e tabuleiro viram juntos no ponto de vista das pretas. |
| C9 | `pele.py` e `test_pele_da_suite.py:70` | Sim | Reserva clara corrigida; testes de contraste passaram. |
| Testes | Suíte: `86 passed`; tronco: `359 passed, 3 xfailed`; janela: `111 passed, 2 skipped, 3 xfailed` | Sim | A primeira falha do tronco foi apenas mistura de binários NumPy/Pillow 3.11 com Python 3.10; repetição no ambiente correto passou. |
| Benchmarks pequenos | `notation_integrity`, `coordinate_survey` e gate C3 | Sim | NAGs: 6/9; sabotagem: 0. Coordenadas: 10.639 `a-h`, 0 `h-a`; sabotagem inverteu o resultado. |

## Defeitos bloqueantes

Nenhum. Os cinco bloqueantes do ciclo 1 foram corrigidos, testados e reproduzidos nos portões correspondentes. Não encontrei regressão nova funcional nas correções.

## Defeitos não bloqueantes

1. O cabeçalho do relatório ainda diz tronco `2077410` em [`OCR_UI_REPORT_C2_FASE2.md:7`](<C:/Python-Chess2/Suite_de_Edicao_de_Xadrez/docs/quality/OCR_UI_REPORT_C2_FASE2.md:7>), embora o commit auditado seja `b20cd6f`.
2. `git diff --check` aponta apenas whitespace/blanks em documentação e fim de alguns arquivos de teste.
3. Os portões absolutos de CER/acurácia continuam vermelhos, mas isso está declarado honestamente no §0.3 e não foi introduzido por estas correções.

## O que falta

Nada bloqueante para fechar a fase 2.

## O que especificamente precisa mudar para eu aprovar

Nada no código. A fase está aprovada porque os cinco bloqueantes foram fechados, os testes tocados passaram, o gate C3 passou, as sabotagens falharam como esperado e os relatórios finais são coerentes com os JSON commitados.
