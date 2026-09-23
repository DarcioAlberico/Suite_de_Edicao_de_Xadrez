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


# Fase 5 do ciclo 2 (código) — vereditos do crítico Claude

> Objeto: os commits da fase 5 (tronco `36d6f65` e `8243e90`, suíte `bb41c55` e `99546e9`) e o
> relatório `OCR_UI_REPORT_C2_FASE5.md`. Um crítico adversarial: Claude, num subagente, com a Carta
> (`CRITIC_CHARTER.md`) e o briefing `brief_critico_fase5.md` — que mandou conferir o tronco numa
> árvore limpa do commit, porque outra sessão tinha trabalho sem commit no checkout principal. O
> crítico escreveu só em `C:\Python-Chess2\_critico_f5\` (os scripts e as saídas citados abaixo).
> **Ciclo 1: REPROVADO, 3 bloqueantes** — o B13 embaralhando as colunas estreitas da Gallagher, o
> C18 cabendo porque escondia conteúdo, e a coluna «≤ 0 errados» do C17 zerada por uma grade de
> limiares que parava em 0,99; o que mudou por item está em `OCR_UI_REPORT_C2_FASE5.md` §0.4.
> **Ciclo 2:** ⟨pendente⟩.

## Crítico Claude — ciclo 1 (REPROVADO, 3 bloqueantes)

VEREDITO: REPROVADO
CICLO: 1
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts citados estão em `C:\Python-Chess2\_critico_f5\` (a saída de
cada um ao lado, `*.out`); rodados da raiz da suíte com `.venv\Scripts\python.exe`. Sondas do
corpus com `CAISSA_FIGURINE_TESSDATA=models\tessdata`; sondas pelo importador e da janela **sem**
ela. «Tronco da fase» = minha árvore limpa `git worktree add --detach C:\Python-Chess2\_critico_f5\tronco 8243e90`
(`git status` vazio). «Antes da fase» = minhas árvores `suite_antes` (`f9ca678`) e `tronco_antes`
(`40e2966`). Nenhum arquivo dos dois checkouts principais foi editado.

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| Números do §0/§B13/§B14 contra os JSON | `conf_sol.py` → `conf_sol.out` | sim | `scan_degraded_150` 0,00942; `photo` 0,02068; aceitos com CER > 0,10: 7 (30 em `f5_before` e na fase 4); `f5_on` = `sol.json` publicado em 747/747 itens (CER e decisão); `f5_before` = `sol.json` da fase 4 (`git show f9ca678:…`) em 747/747; B13 muda 7 itens, nenhum pior; B14 muda 27, nenhum pior; 0 aceitos-e-bons (CER ≤ 0,02) viraram revisão; dos 30: 18 aceitos e certos, 5 revisão, 7 ficam, nenhum novo |
| Portões do Sol no `sol.json` publicado | `.venv\Scripts\python.exe benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` | sim | 150 DPI 0,0094 ≤ 0,020 ✓; CER limpo 0,0113, lances 0,9164, 157 inventados ✗ (os mesmos três); nenhuma regressão contra o `baseline`; `environment.commit` = `bb41c55` |
| B13, itens do corpus, 3 execuções | `probe_itens.py '{"table_rows": true\|false, "ink_coverage": true}' 3 table:7@scan_degraded_150 "real:Dvoretsky,_Mark_&_Yusupo:11:54:52@native"` → `b13_itens.out` | sim | `table:7` 0,67611 → 0; Dvoretsky `11:54:52` 0,38095 → 0; 3/3 idênticas nos dois lados |
| B14, item-vitrine, 3 execuções | `probe_itens.py '{"table_rows": true, "ink_coverage": true\|false}' 3 "synth:Dvoretsky - Dvoretsky's :201:21@photo"` → `b14_item.out` | sim | desligado: CER 0,78571 `accepted`; ligado: 0,00714 `review`, nota «a leitura cobre 22 % da tinta — variantes pedidas» |
| B13, páginas do Levenfis citadas no §B13, com o `rows.py` commitado (ele foi modificado às 05:50, depois das medições de 04:19–04:42) | `scratchpad\probe_b13_pages.py "<Levenfis>" 40,41,50 ron+eng` → `b13_levenfis_builderprobe.out` | sim | p. 40 0,9808, p. 41 idêntica, p. 50 0,9992 — como no relatório |
| B13, páginas que o construtor não mediu | `b13_importador.py "<Levenfis>" 41,142 …`; `b13_raster_paginas.py "<Kmoch 1936>" 24,36,40,48,56,64,68,76,80 nld+eng` (e 44,68,24 a 150/200 DPI); `b13_raster_paginas.py "<Levenfis>" 118,134,142,148,150,156,158,160 ron+eng` | em parte | Kmoch 9/10 idênticas e p. 68 **melhor** («20. Kd2,»/«22. Kd1,» voltam ao lugar); Levenfis 118/134 formam os pares brancas\|pretas; **mas** ver bloqueante 1 (Gallagher) e o grupo que cruza a calha na leitura do Tesseract da Kmoch p. 44 (`b13_trace_blocos.py "<Kmoch>" 44 nld+eng` → `b13_trace_kmoch44.out`: `Pd5: \| (Een duidelijke wenk tot`, corredor de 7 px < `gutter_min_px` 8) |
| B14, população real nova (importador, localizador de diagramas ligado) | `b14_populacao.py C:\Python-Chess2\_critico_f5\b14_pop "<Stean>:40..43" "<Aagaard>:60..63" "<Gallagher>:50..53" "<Flores Rios>:100..103" "<Silman>:100..103" "<Reinfeld 1977>:100..103" "<Karpov 2>:100..103" "<Vladimirov>:200..203"` → `b14_pop.out`, recortes em `b14_pop\` | sim (nenhum alarme falso danoso) | Aagaard 32 regiões medidas, mín. 0,976; Flores Rios 26, mín. 0,999; Stean e Silman 1,0; sinalizadas: Gallagher p. 52 r2 0,794 (perdeu «explanation.» — verdadeiro), p. 52 r1 0,529 (pedaço da mesma linha, regiões sobrepostas), p. 50 r0 0,894 (a página que o B13 embaralha); Reinfeld 3, Karpov 1, Vladimirov 1 em páginas de diagrama com lixo já em revisão/abstenção |
| B14, piso ajustado «só na `calib`» | `b14_piso.py` → `b14_piso.out` | em parte | não bloqueante 2 |
| B14, a perda que a medida não vê | `b14_moldura_kmoch.py`, `b14_moldura.py`, `b14_moldura2.py` → `*.out` | não | não bloqueante 1 |
| A14 | `a14_polgar.py` → `a14_polgar.out`; leitura do `pymupdf.utils.get_text` 1.28.2; `Grep get_text(` em `src` | sim | Polgar pp. 6–10: 19 com as bandeiras padrão → 0 no nível 0, 0 no leiaute, 0 no índice; 0 palavras com caixa por caractere desalinhada; `½ ² №` pelo teste; os `get_text` restantes sem bandeira leem só tamanho de fonte (`ocr_service.py:677`) ou geometria de diagrama (`vector_detect.py`, `survey.py`) |
| C17, produção remedida por mim | `.venv\Scripts\python.exe benchmarks\model_ruler.py --models production --runs 3 --tag critico_f5 --out C:\Python-Chess2\_critico_f5\campo` → `campo\ruler.log` | sim no gate | 107 exatos, gate 0,80: 103 exportados / 1 errado, AURC 0,0063; linhas idênticas nas 3 execuções (o arnês recusa se não forem) |
| C17, «melhor com ≤ k errados» e «o errado mais confiante» | `conf_regua.py` (JSON do construtor) e `conf_regua.py C:\Python-Chess2\_critico_f5\campo\model_ruler_20260923_064258_critico_f5.json` → `conf_regua.out` | **não** | bloqueante 3 |
| C17, sabotagem | `c17_sabotagem.py` → `c17_sabotagem.out` | sim | tau +0,20 recalculado; 11/15 com as três colunas em 0; AURC 3,4× a 25,4× pior; em 20 sementes o tau fica entre −0,10 e +0,52 (mediana 0,29) |
| Remedição do campo (A15), reproduzida | `remedir.sh` (código da árvore `8243e90`, `.pt` e PDFs do checkout principal por caminho, saída fora da árvore) → `campo\field_producao_critico.json` | sim | 114 casados, 0 falsos positivos, 103 exportados, 0,8957, 3 errados, exatidão 0,9709, 103 exatos — iguais ao `docs/metrics/field_20260822_s99.json`; digest de código `144290fc3ad091b7` e de modelo `a907f61086da609f` iguais; os quatro relatórios gravam `36d6f654…`, `dirty=false`, `.pt` relativo, nenhum `C:\`/`C:/` (`grep -c`) |
| C18, portão | `minimo.sh` (tronco = minha árvore `8243e90`) → `minimo\minimo_20260923_094706.json`, `…_094717.json`, `…_sabotado_rodape_…_094726.json` | sim | Clássica 1248×606, Foco 1248×640, Fita 1246×629, sem livro e com o Kemeri — PASSOU; sabotagem 2206×606 / 2206×640 / 2194×629 — REPROVOU. Ao pixel os do construtor |
| C18, teclado | `teclado.sh` (`caissa.ui.audit.teclado --pele foco --pdf <Kemeri>` a 1280×800 e 1248×640) → `teclado.out` | sim | PASSOU nos dois tamanhos: toda área com o `Tab` alcançando todos os focáveis e fechando (Resultado 37/37, Revisão de texto 50/50) |
| C18, API | `Grep "\.pilha\b"` no `src` da árvore `8243e90` e da suíte | sim | só `qt/painel_principal.py` usa a pilha; `ui/audit/capture.py:237` usa `widget_do_modo`; a suíte do tronco passa |
| C18, o que a janela mostra no tamanho do portão | `c18_visiveis.sh`, `c18_corte.py`, `c18_rodape_janela.py`, `c18_rodape2.py` → `*.out`, capturas em `img\c18\` | **não** | bloqueante 2 |
| A15, `test_strings` | `a15_brecha.py`, `a15_escondidos.py` (com o `.venv` do tronco e a árvore `8243e90`) | em parte | não bloqueante 3; hoje as regras novas escondem só os seis identificadores do §A15 |
| A15, `test_arquitetura` reprova um Qt no topo de um arnês real | árvore minha `suite_sab` (`99546e9`), `from PyQt6 import QtCore` depois do `from __future__` em `src/caissa/ui/audit/minimo.py`, `pytest tests/unit/ui/test_arquitetura.py` | sim | `test_o_arnes_de_auditoria_importa_sem_qt[minimo]` reprova, 20 passam (arquivo restaurado); ver não bloqueante 4 |
| Testes do tronco da fase | `cd C:\Python-Chess2\_critico_f5\tronco && PYTHONPATH=C:\Python-Chess2\_critico_f5\tronco\src QT_QPA_PLATFORM=offscreen C:\Python-Chess2\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider` → `trunk_full.out` | sim | **4.780 passaram, 16 pulados, 8 xfail, 1 reprovado** em 387 s; o reprovado é `test_environment::test_o_pacote_instalado_resolve_para_esta_arvore` (por construção da árvore efêmera); `ImpressaoDaMedicaoTests` passa **sem** `--deselect`. Um pulado a mais que o construtor (ele copiou os `.pt` para a árvore dele) |
| Testes da suíte com o tronco da fase | `suite_full.sh` (`CAISSA_CVOFF_ROOT` e `PYTHONPATH` = árvore `8243e90`; `pytest tests -q -p no:cacheprovider -rfEs --ignore=…test_packaging.py --ignore=…test_roundtrip_corpus.py`) → `suite_full.out` | sim | **3.995 passaram, 17 pulados, 1 erro, 0 reprovados** em 725 s, com o `test_arquitetura` na mesma corrida; mesmo total do construtor (4.013 = 4.004 + 9). O erro (`tests/integration/test_gpu_parity.py::test_cuda_actually_computes`) é do meu ambiente: o carregador de configuração da suíte recusa o `CAISSA_CVOFF_ROOT` que usei para apontar o tronco da fase (`UnknownSettingError`); sem a variável o arquivo dá 2 passaram, 5 pulados. Os 8 pulados a mais pedem artefatos fora do git (`.pt`, acervo `PDF/`, listas do tronco) que a árvore efêmera não tem |

### Defeitos bloqueantes

1. **B13 embaralha as duas colunas de uma página real, pelo importador do produto — através da calha que o relatório diz que ele nunca cruza.**
   - **Onde:** `src/caissa/ocr/layout/rows.py` — `_is_column_gutter` (`gutter_min_lines = 8` linhas de «prosa» de ≥ 30 caracteres para julgar) e `table_groups` (sem evidência, a regra **junta**); o gancho em `ocr/arbiter.py`.
   - **O quê:** Gallagher, *Winning With the King's Gambit* (acervo, digitalizado, duas colunas estreitas, figurino), índice 50 (base 0; página impressa 51): com o B13 **desligado** o texto sai coluna por coluna; **ligado**, a coluna esquerda inteira é intercalada linha a linha com a lista de lances da direita — «The best chance to get 27 Bxd4 Rd6», «his rook into the game, but 28 R£6+», «21... Rigs 36 Hei», «still has an edge, his own 45 Voo». **CER 0,2732 → 0,7042, WER 0,4076 → 0,8408** contra a página transcrita (`gallagher_p50_verdade.txt`). No índice 53 (impressa 54) o cabeçalho da partida seguinte («Game 17 / Teschner - Dahl / Berlin 1946 / 1 e4 e5 / 2 f4 ef / 3 ♘f3 g5», coluna direita) entra linha a linha nas notas da partida anterior («coming onslaught. Teschner - Dahl», «This is just a waste of 1 e4 es»). Causa, pelo rastro dos blocos: a página tem **0 linhas de ≥ 30 caracteres** (coluna de ~26), a regra da calha nunca é julgada, e a coluna de números da direita (`b7`) semeia um grupo `[7, 2, 3, 4, 8, 9]` que puxa a prosa e a lista da coluna esquerda (medianas 10–24, abaixo do corte de «prosa»); o B1 não protege porque a faixa da direita tem mediana < 16. Construído, pelo serviço de produção (Tesseract, 300 DPI): duas partidas lado a lado **0,0190 → 0,5625** («1.e4c¢5 1. gxf6 Bf8»); uma partida que continua da coluna esquerda para a direita 0,2241 → 0,4152 («1.e4 21. Rg7 Bh6»). Na Kmoch p. 44 o grupo `[20, 12]` junta um parágrafo da coluna direita a um fim de linha da esquerda («Pd5: | (Een duidelijke wenk tot») porque o maior corredor livre no vão de 23 px tem 7 px, com 16 linhas de prosa para julgar (`b13_corredor.py` → `b13_corredor.out`) — aqui o RapidOCR venceu e o texto final não mudou.
   - **Como reproduzir:** `unset CAISSA_FIGURINE_TESSDATA; .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\b13_importador.py "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\GALLAGHER - Winning With the King's Gambit.pdf" 50,51,52,53 C:\Python-Chess2\_critico_f5\b13_gallagher.json` (p. 50 similaridade 0,2652; p. 53 0,9148), depois `gallagher_cer.py`; rastro: `CAISSA_FIGURINE_TESSDATA=models\tessdata … b13_trace_blocos.py "<Gallagher>" 50 eng 300`; construídos: `… b13_render.py`, `b13_caso_ruim.py`.
   - **Por que reprova:** o §B13 afirma «dentro da coluna da página e nunca através da calha» e «a página de duas colunas de prosa não muda»; numa página real do acervo, no caminho do produto, o passo **mais que dobra** o erro e mistura lances de uma coluna (e de uma partida) na outra — o conteúdo de xadrez, que é o que o livro vende, sai trocado. O portão não viu porque o corpus só tem recortes e a amostra real (Levenfis, Estrin, Stefaniu) tem colunas largas; o leiaute de duas colunas estreitas com lances (Batsford/Everyman) é comum. A decisão da região continua `review` nos dois lados: o revisor recebe um texto pior sem aviso de que a ordem foi reescrita (Carta §3.3, «resultado plausível sem sinalizar»).

2. **C18: a janela «cabe» em 1250×640 escondendo conteúdo — controles inalcançáveis pelo mouse no tamanho do portão e a 1366×728, e a mensagem do rodapé com 0 px.**
   - **Onde:** tronco `qt/painel_principal.py::_rolagem_de` e suíte `ui/views/revisao_de_texto.py` (rolagens com `ScrollBarAlwaysOff` na horizontal: o mínimo de largura do painel deixa de subir, e o que não cabe é cortado sem barra); tronco `qt/rodape.py` (a mensagem com `stretch=1` e `largura_desejada=0`: no cálculo do Qt o item com stretch só recebe a sobra, e o documento com o nome do arquivo leva a largura inteira que pede); `ui/audit/minimo.py` só mede `minimumSizeHint`.
   - **O quê (mesma montagem do arnês: Kemeri, áreas visitadas, frase de 300 caracteres):** antes da fase (`f9ca678` + `40e2966`) o mínimo era 2200×695 — a janela não cabia na tela, que é o defeito que o C18 atacou — e dentro dela **nada** estava cortado (a mensagem, num `QLabel` comum, empurrava a janela mas nunca sumia); depois, a **1248×640** a Revisão de texto esconde «Pular», «Anterior», «Próxima» e «Letras → figurinas» (**0 px visíveis**) e corta «Manter como imagem» (88/141 px), «Verdade (Enter aceita · Ctrl+Enter grava a edição · Ctrl+F…» e a frase do cartão (289/462 px); o Resultado corta «Copiar FEN» (66/80) e a frase de estado (516/530) — o comentário do tronco «na largura nada muda» é falso (o painel pede 550, a rolagem mostra 526). A **1366×728** (portátil comum) continuam «Anterior» e «Próxima» com 0 px e «Pular» com 8/50. A 1600×860 nada corta. O teclado alcança tudo (`teclado.sh` PASSOU); o mouse, não, e não há barra que diga que há mais. Rodapé: com um livro do próprio acervo de nome longo (`Gaprindashvili…Aprimorar.pdf`, 149 caracteres) aberto na janela, a mensagem fica com **0 px a 1248×640 e a 1366×728** (o documento ocupa 919–957 px; a 1600×860 também 0 px enquanto a ocupação mostra a leitura do dataset) — toda mensagem, inclusive de erro, some; isolado, com o nome do Flores Rios (87 caracteres), «Não foi possível exportar: a pasta de destino é somente leitura. Escolha outra pasta…» sai «Não foi possível exportar: …asta em Arquivo › Exportar.» a 1250.
   - **Como reproduzir:** `C:\Python-Chess2\_critico_f5\c18_visiveis.sh` (antes × depois, lista cada botão/rótulo cuja região visível é menor que o retângulo); `c18_corte.py foco C:\Python-Chess2\_critico_f5\tronco "<Kemeri>"` (Revisão de texto: pede 466, mostra 293 — 173 px sem barra; Resultado: 550 × 526); capturas `img\c18\foco_Revisão_de_texto.png`, `img\c18\foco_1366_Revisão_de_texto.png`; rodapé: `c18_rodape_janela.py foco C:\Python-Chess2\_critico_f5\tronco "<Gaprindashvili…pdf>"` → `c18_rodape_janela.out`; isolado, `c18_rodape2.py` → `c18_rodape2.out` (Gaprindashvili: 0 px a 1250, 93 px a 1366) e `c18_rodape3.out` (Flores Rios, Dvoretsky). Tudo com `QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=src;C:\Python-Chess2\_critico_f5\tronco\src;.venv-pack\Lib\site-packages` e a fonte do produto imposta (`impor_a_fonte_do_produto` → `confere: sim`).
   - **Por que reprova:** a saída prometida é «a janela cabe no portátil»; no tamanho que o portão aprova, e num portátil de 1366×768, botões da revisão ficam fora da vista sem rolagem e a zona de mensagens pode desaparecer por inteiro — Carta §3.3 («texto cortado», «mensagem de erro que não diz o que fazer»: aqui nem aparece). O portão passa enquanto a coisa que ele deveria garantir está quebrada, porque mede o pedido de tamanho e não o que fica visível.

3. **C17: a coluna central da régua («melhor com ≤ 0 errados») está errada em 6 dos 15 modelos, e a conclusão (1) do §C17 é falsa.**
   - **Onde:** `benchmarks/model_ruler.py` — `THRESHOLDS = 0,30 … 0,99` e `best_at_budget` só olham essa grade; as confianças saturam no topo (produção: 74 dos 114 julgáveis em ≥ 0,998, valores distintos 0,998 … 1,0 acima de 0,99; 64 valores repetidos).
   - **O quê:** o errado da Burgess (p. 60 d2) tem `gate_confidence` **0,9979**, e **74** diagramas exatos da produção estão em ≥ 0,998 (os do topo em 1,0): com o limiar 0,998 a produção exporta **74 exatos e 0 errados**; a tabela diz 0, e o texto diz «o único errado que a produção exporta é o diagrama mais confiante dela … nenhum limiar exporta com zero erros — por isso a coluna «≤ 0» é 0». O mesmo artefato zera `c4_mhsp_s43` (verdadeiro 43), `c4_mhspe_s43` (43), `c4_mhspe_s44` (38), `c4_e_s43` (31), `c4_e_s44` (27). Nas minhas linhas (3 execuções, idênticas) o resultado é o mesmo.
   - **Como reproduzir:** `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\conf_regua.py` (JSON do construtor `model_ruler_20260923_043817_f5_c17.json`) e `… conf_regua.py C:\Python-Chess2\_critico_f5\campo\model_ruler_20260923_064258_critico_f5.json` (o meu), → «≤0 err na grade=0 (lim None) | em qualquer limiar: ≤0 74 (lim 0.998)»; «errados mais confiantes: Burgess 0,9979».
   - **Por que reprova:** o C17 existe para dar à pessoa a comparação «no mesmo risco» para a decisão §10.2; a tabela entregue erra essa comparação justamente no risco zero e o relatório tira dela um fato que as próprias linhas desmentem. Métrica que não reproduz o que afirma (Carta §6).

### Defeitos não bloqueantes

1. **B14 fica cego, em silêncio, numa digitalização com moldura escura.** A borda do scanner vira um componente do tamanho da página, e a regra (4) do `ink_map` («o que está dentro de uma coisa grande não é texto») exclui todas as letras: Kmoch pp. 40/44/48 dão **0 letras** com a moldura e 995–1.162 sem ela (`b14_moldura_kmoch.py`; componente de 1791×2690 px na p. 44); nos 15 itens da foto testados, uma moldura de 12 px cinza 40 zera o mapa (cobertura `None` nos 15), e nos dois em que rodei os dois lados o B14 ligado dá exatamente o desligado (`b14_moldura.py`, `b14_moldura2.py`). A cobertura vira `None` sem nota no rastro. Não bloqueia porque, no acervo, o único livro com moldura (Kmoch) usa a camada de texto, e nos itens testados a moldura também mudou a leitura para inteira; mas é degradação não sinalizada.
2. **O piso 0,90 não sai da `calib`.** Na `calib` toda leitura boa tem cobertura 1,0; pela regra declarada (máximo de aceitas-perdidas sem sinalizar boa) empatam todos os pisos de 0,8757 a 0,99 (6/8, 0/182) — `b14_piso.py`. O 0,90 é o do primeiro ajuste, feito com a medida descartada. E a folga no real é zero: Stefaniu 0,900 no relatório; Gallagher p. 50 0,894 aqui.
3. **`test_strings`: as regras por posição abrem brecha.** A do `.split()` não tem a restrição de forma das outras (qualquer literal que receba `.split()` escapa), e a da chave de dicionário deixa passar chave com forma de identificador que vai para a tela. Construídos: `"Pagina anterior|Proxima pagina|Configuracoes".split("|")`, `combo.addItems("Posicao Pagina Revisao".split())`, `{"pagina": 1, "posicao": 2}` com `addItems(list(...))` — os três escapam (`a15_brecha.py`). O teste anti-brecha do commit não cobre essas posições. Hoje nenhuma frase de tela real se esconde (`a15_escondidos.py`: só os seis identificadores do §A15).
4. **`test_arquitetura._bindings_ao_importar` lê um import que quebrou (código 1 da exceção) como «veio um binding de Qt»** — com um `SyntaxError` no arnês a mensagem sai «trouxe um binding de Qt junto: » com a lista vazia. Reprova, mas pelo motivo errado.
5. **AURC depende da ordem dentro dos empates** em 4 dos 15 modelos (embaralhando os empates: `c4_mhspe_s44` 0,0111–0,0134, `c4_mhsp_s43` 0,0126–0,0142, `c4_e_s43` 0,0138–0,0146, `c4_e_s44` 0,0136–0,0142 — `conf_regua.py`), sem regra de desempate declarada; e «as outras duas sementes … entregam 96–97 e 99» não bate com a própria tabela (aug0: 97 e 97; mhsp: 99 e 92).
6. **A evidência dos números do §0/§B13/§B14/§C17 não está versionada:** `benchmarks/reports/` é ignorado pelo git (`git check-ignore` → `.gitignore:43`) — `f5_*.json`, `f5_b14_fit2.json`, `model_ruler_*.json` só existem nesta máquina; só o `sol.json` e os JSON do `minimo` foram commitados.
7. **O B13 muda o leiaute da página e, com ele, a leitura de linhas que não são tabela:** Levenfis p. 134 (rasterizada) passa de 19 para 11 regiões e o texto corrido muda para melhor e para pior («tipicd» → «tipică», mas «De7» → «De?») — `b13_levenfis_raster.out`.

### O que falta

- Um portão do B13 em página inteira real de colunas estreitas e em página de duas colunas de lances (o corpus só tem recortes; as páginas reais medidas são de colunas largas).
- Um portão do C18 que meça o que fica visível (nenhum controle com região visível menor que o retângulo sem barra de rolagem visível) no mínimo e a 1366×728, e a mensagem do rodapé legível com o nome de arquivo mais longo do acervo.
- A medida da janela na plataforma real (`windows`): tudo aqui foi `offscreen` com a fonte do produto imposta; não abri janelas na área de trabalho do usuário.
- O arnês `minimo` contra o checkout principal do tronco (opcional no briefing): não rodei — ele tem, sem commit, o trabalho de outra sessão em `qt/janela.py` e `qt/painel_de_texto.py`, e o que se julga é o `8243e90`.
- A comparação às cegas da Carta não se aplica a esta frente e não foi feita.
- Fora da fase (não pesa no veredito): o carregador de configuração da suíte (`core/config/loader.py`) recusa com `UnknownSettingError` a variável `CAISSA_CVOFF_ROOT`, que o próprio `vision/classify/cvoff.py` documenta como a primeira forma de apontar o tronco.
- As minhas árvores (`tronco`, `tronco_antes`, `suite_antes`, `suite_sab`) foram removidas ao fim com `git worktree remove`; para reproduzir, recriá-las com `git worktree add --detach <pasta> <commit>` (`8243e90`, `40e2966`, `f9ca678`, `99546e9`).

### O que especificamente precisa mudar para eu aprovar

1. **B13:** o grupo nunca pode ter blocos dos dois lados de uma calha da página, **com ou sem prosa para julgar** — sem evidência, não juntar. Por exemplo: estimar a calha da página com `find_gutters` sobre todas as palavras (não só sobre faixas de prosa) e proibir grupo que a cruze; e/ou não juntar dois blocos que começam ambos por número de lance (são duas sequências, não brancas|pretas); e/ou exigir que a largura do grupo caiba numa coluna. Travar por teste os casos da Gallagher p. 50 e p. 53 (a leitura do produto como fixture, como o construtor fez com o `table:4`), as duas páginas construídas de `b13_render.py` e a Kmoch p. 44 (corredor de 7 px); refazer o A/B e as páginas reais, incluindo a Gallagher 50–53.
2. **C18:** barra horizontal `AsNeeded` nas rolagens novas (ou conteúdo que reflui — a fileira de botões do cartão numa `BarraFluida`, rótulos com quebra), até nenhum botão ficar fora da vista sem barra a 1248×640 e a 1366×728; o rodapé com prioridade real para a mensagem (teto ou elisão no meio para o documento, ou um mínimo de largura para a mensagem) e um caso de portão com o nome de 149 caracteres; o `caissa.ui.audit.minimo` reprovando quando um controle visível fica cortado sem barra no tamanho medido, com a sabotagem correspondente (rolagem com `AlwaysOff`) reprovando.
3. **C17:** `best_at_budget` sobre todos os valores distintos de confiança (ou uma grade até 1,0 com passo que separe 0,9979 de 1,0), a tabela e o texto do §C17 refeitos (itens 1 e 2), e um desempate declarado para a AURC (média sobre as ordens dos empates, ou ordenar por confiança e depois por exatidão pior-primeiro, dito).
4. **Não bloqueantes a fechar no mesmo ciclo:** nota no rastro quando a cobertura não é medida por exclusão total (moldura), e a regra (4) não excluir o que está dentro de um componente do tamanho da página; a regra de desempate do piso escrita antes de olhar a `dev`; a regra do `.split()` com a mesma restrição de forma e o teste anti-brecha cobrindo `.split()` e chave exibida; `_bindings_ao_importar` distinguindo exceção de binding encontrado.
