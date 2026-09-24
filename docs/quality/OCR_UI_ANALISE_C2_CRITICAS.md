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
> **Ciclo 2: REPROVADO, 2 bloqueantes** — os três do ciclo 1 resolvidos nos casos dados, mas o
> B13 ainda intercalava as duas colunas de um índice real sem prosa (Karpov 2 p. 268, CER 0,76
> contra a ordem do livro) através da calha que a própria regra achava, e a reserva de 480 px da
> mensagem do rodapé saía das zonas de dispositivos e de ocupação (a queda para a CPU de novo em
> silêncio); o que mudou está em `OCR_UI_REPORT_C2_FASE5.md` §0.5.
> **Ciclo 3: REPROVADO, 1 bloqueante** — os dois do ciclo 2 resolvidos (a Karpov 2 p. 268
> idêntica ao desligado; as quatro zonas do rodapé à vista), mas o B13 ainda juntava, linha a
> linha, uma coluna de **notas comuns** (três palavras por linha, poucos lances dentro) e a lista
> de lances da outra coluna, e o importador **aceitava** a página embaralhada (a página construída
> na medida da Gallagher p. 50: CER 0,0052 → 0,6440, `accepted`); o que mudou está em
> `OCR_UI_REPORT_C2_FASE5.md` §0.6. As edições de `rows.py` e `test_table_rows.py` que o
> veredito atribui a «outra sessão» (13:53–13:54) eram do construtor, começando o ciclo 4 depois
> de ler o rascunho; as sondas do crítico já tinham terminado.
> **Ciclo 4: REPROVADO, 2 bloqueantes** — o do ciclo 3 resolvido nas páginas dadas (as notas
> comuns idênticas ao desligado pelo importador), mas o B13 ainda intercalava as colunas de um
> **índice** quando a página tinha duas calhas ou mais e nenhuma prosa (a Flores pp. 460–464 do
> acervo, a Yusupov 4 p. 206 e a Nunn p. 288 digitalizadas, e três colunas construídas aceitas
> trocadas: 0,0007 → 0,7791), e a ordem do Tab da Revisão de texto só existia na cadeia do foco —
> com a tecla, o Tab parava no campo da verdade escrevendo tabulações, e o Shift+Tab das ações
> punha o foco numa figurina fora da vista; o que mudou está em `OCR_UI_REPORT_C2_FASE5.md`
> §0.7. As edições de `rows.py` e dos testes a partir de ~17:20 eram do construtor, começando o
> ciclo 5 depois de ler o rascunho; o crítico mediu numa árvore limpa do `7d41996`.
> **Ciclo 5: REPROVADO, 2 bloqueantes** — os dois do ciclo 4 resolvidos nas páginas dadas (a Flores
> pp. 460–464, a Nunn p. 288 e o `tres.pdf` certos pelo importador; o cartão da Revisão de texto com a
> tecla nos dois sentidos), mas não na classe: o B13 ainda intercalava duas listas lado a lado que a
> regra nova não via como índice — fora da ordem alfabética («jogador / adversários» pela
> classificação, 0,0000 → 0,6577 **aceito**) ou curtas (a última página de um índice, 5 verbetes) — e
> uma partida ao lado de uma tabela; e o teclado falhava onde o portão dizia PASSOU: a Rotulagem com
> uma página de linhas prendia o Tab, e o Shift+Tab que entra nas rolagens do tronco (os modos da aba
> Livro, a Galeria) punha o foco a 0×0 px com a rolagem no topo; o que mudou está em
> `OCR_UI_REPORT_C2_FASE5.md` §0.8.
> **Ciclo 6: REPROVADO, 3 bloqueantes** — os dois do ciclo 5 resolvidos nas páginas dadas (as listas
> do ataque, a partida × a classificação, tudo o que ele mandou manter igual byte a byte; a Rotulagem
> com linhas e as rolagens com o foco à vista), mas: o B13 intercalava listas cujas colunas têm
> **formas** diferentes (um índice com números de quatro algarismos, 0,0026 → 0,4916 **aceito**; a
> coluna do meio só de nomes; a classificação em duas metades) — a calha dependia de as duas colunas
> terem a mesma forma; o seguidor de foco rolava no **clique** do mouse, entre o pressionar e o soltar
> (um lance que ninguém jogou no Estudo, um rádio que não marca); e o item de página sem leitura,
> aceito com o Enter, virava a aceitação verificada da leitura seguinte da página inteira; o que
> mudou está em `OCR_UI_REPORT_C2_FASE5.md` §0.9.
> **Ciclo 7:** ⟨pendente⟩.

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

## Crítico Claude — ciclo 2 (REPROVADO, 2 bloqueantes)

VEREDITO: REPROVADO
CICLO: 2
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts novos estão em `C:\Python-Chess2\_critico_f5\c2\` e os do ciclo 1 em
`C:\Python-Chess2\_critico_f5\` (a saída de cada um ao lado, `*.out`/`*.json`); rodados da raiz da suíte com
`.venv\Scripts\python.exe`. A suíte principal estava no `158f420` com `git status --short src tests` vazio (o
`src` do `158f420` é o do `4fc0f4d`). «Tronco do ciclo 2» = minha árvore limpa
`git worktree add --detach C:\Python-Chess2\_critico_f5\tronco 53dd066`; «tronco do ciclo 1» = `tronco_c1`
(`8243e90`); «suíte do ciclo 1» = `suite_c1` (`99546e9`); `suite_sab` (`158f420`) para as sabotagens do
`test_arquitetura`. As quatro árvores ficaram limpas e foram removidas com `git worktree remove`. Sondas do
corpus e das páginas renderizadas com `CAISSA_FIGURINE_TESSDATA=models\tessdata`; importador e janela **sem**
ela. Nenhum arquivo dos dois checkouts principais foi editado; o `git status` deles terminou igual ao do
começo (só o trabalho das outras sessões). Nenhum processo meu ficou vivo (o único Python restante, PID 1996,
já existia às 07:51 e não é meu).

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| B13, Gallagher pp. 50–53 pelo importador | `b13_importador.py "<Gallagher>" 50,51,52,53 …\_critico_f5\b13_gallagher_c2.json` → `b13_gallagher_c2.out`; `gallagher_cer_c2.py` → `gallagher_cer_c2.out` | sim | p. 50 similaridade 0,7970 com a lista de lances por linha; pp. 51–53 idênticas; CER **0,2732 → 0,2028**, WER 0,4076 → 0,3121 — como o relatório |
| B13, páginas construídas do ciclo 1 | `b13_render.py` → `b13_render_c2.out`; `b13_caso_ruim.py` → `b13_caso_ruim_c2.out` | sim, com ressalva | renderizadas: CER igual ligado/desligado (0,2241; 0,0190; 0); leituras construídas: a partida em duas colunas não agrupa; as duas partidas só juntam os títulos de uma linha (`[[3, 4]]`); **o índice em duas colunas continua agrupado (`[[8, 9]]`)** → novo bloqueante 1 |
| B13, Kmoch p. 44 | `b13_trace_blocos.py "<Kmoch>" 44 nld+eng 300` → `c2\b13_trace_kmoch44_c2.out`; `b13_corredor.py` → `c2\b13_corredor_c2.out` | sim | GRUPOS `[]` (ciclo 1: `[[20, 12]]`); o corredor continua com 7 px — o conserto é o parágrafo com calha espúria não semear mais |
| B13, os 24 testes travam os casos do ciclo 1? | `test_table_rows.py` do `158f420` rodado contra o `rows.py` do `99546e9` (árvore `suite_c1`) | sim | 9 de 24 reprovam: 5 por asserção (Gallagher p. 50 `[[1, 6], [2, 3, 4, 7, 8, 9]]`, duas partidas `[[1, 2]]`, a partida nas duas colunas atravessa, Kmoch `[[20, 12]]`, o título partido `[[8, 6]]`) e 4 por parâmetro/função que não existia |
| B13, a Gallagher inteira | `c2\b13_varredura.py "<Gallagher>" 14-186/4,187-189 eng`, e `15-186/4`, `16-186/4`, `17-186/4` → `c2\b13v_gallagher.*`, `c2\b13v_gal_1[567].*`; diffs por `c2\ver_diff.py` | em parte | **176 páginas: 155 idênticas**; 21 mudam: 3 melhoram (pp. 33, 50, 124 — número e lances na mesma linha), 2 perdem lances (pp. 41, 175 — não bloqueante 3), o resto é ruído de diagrama reordenado ou fólio colado. Nenhum grupo cruzou a calha na Gallagher real |
| B13, páginas finais (índices, sumários, soluções) de nove livros raster | `c2\b13_varredura.py` em Karpov 2 262–272, Vladimirov 380–385 e 400–405, Silman 376–387, Stean 154–165, Flores Rios 452–465, Aagaard 180–192, Levenfis 296–305, Stefaniu 236–245, Reinfeld 1977 310–319 → `c2\b13v_*.out/json` | **não** | **Karpov 2 p. 268 (índice de jogadores): similaridade 0,4249, 2 grupos** → novo bloqueante 1. Melhoram: Reinfeld 1977 p. 319 (sumário; pelo importador CER 0,2508 → 0,1570 contra `c2\reinf77_p319_verdade.txt`, `c2\b13i_reinf319.*`, embora funda as entradas 1 e 2 numa linha) e Stefaniu p. 242 (sumário). O resto idêntico, cabeçalho+fólio ou ruído |
| B13, Karpov 2 p. 268 pelo importador, 3 execuções | `b13_importador.py "<Karpov 2>" 268 c2\b13i_karpov268{,_r2,_r3}.json` | **não** | similaridade 0,4255; **CER da leitura ligada contra a desligada (a ordem do livro) 0,7606** (WER 0,9502) nas 3; decisão `review` nos dois lados; nenhuma nota de reordenação |
| B13, rastro da p. 268 | `b13_trace_blocos.py "<Karpov 2>" 268 eng 300` → `c2\b13_trace_karpov268.out` | — | `find_gutters` sobre todas as linhas acha a calha **(672–1002 px)**; 0 linhas de prosa (≥ 30 car.); `_prose_gutters` = `[]`, `_page_gutters` = `[]`; grupos `[[7, 4, 6], [5, 8, 9]]` — b4 em x 133–685 com b7 em x 1002–1458 |
| B13, tabelas legítimas no formato e na degradação do corpus | `c2\b13_tabelas.py scan_degraded_150,scan_clean_300` (e com `SUITE_SRC=…\suite_c1\src` para a regra do ciclo 1), 3 execuções → `c2\b13_tabelas_c2.out`, `c2\b13_tabelas_c1.out` | em parte | classificação de torneio com a coluna 1, 2, 3… **não** é recusada (0,1388 → 0,0909 nos dois ciclos); rodadas de um match: nenhum grupo; **aberturas por extenso (4 palavras): 0,4646 → 0,3456 no ciclo 2, 0,0113 no ciclo 1** → não bloqueante 1; índice em duas colunas 0,1824 → 0,6554 nos dois ciclos; as linhas do `table:2` em Times 0,6224 → 0,5280 nos dois ciclos → não bloqueante 2 |
| B13, colunas estreitas com notas de variantes | `c2\b13_estreita.py` (3 execuções) → `c2\b13_estreita_c2.out`; `c2\b13_fixture_notas.py` → `.out` | **não** | página no leiaute da Gallagher p. 50 (Times 10 pt, 300 DPI, serviço de produção): notas de variantes \| lista numerada **0,0113 → 0,5845** («Or 21 Bd6 Rg8 22 g4 Rg6 26 Re3 Bxd4»); sob um título de largura inteira 0,0102 → 0,5292; lista \| notas: nenhum grupo. A fixture `gallagher_p50()` do próprio teste com as notas trocadas por variantes: não atravessa enquanto o alto da coluna direita é prosa por palavras (`[[7, 8, 9]]`); sem nenhum bloco de prosa, `[[7, 2, 4, 8, 9], [1, 6]]`, atravessa |
| C17 | `c2\conf_regua_c2.py` → `c2\conf_regua_c2.out` | sim | orçamentos ≤ 0/1/2 = força bruta sobre todo valor distinto, nos 15 modelos; AURC publicada = média de Monte Carlo sobre 4.000 ordens dos empates (±0,00001); a tabela do §C17 bate célula a célula 15/15; linhas do ciclo 2 = ciclo 1 = `docs/quality/campo/f5_c17_regua.json`; sabotagem: AURC pior 15/15, três colunas em 0 em 5/15, tau recalculado **+0,3143** |
| C18, portão estendido | `c2\minimo_c2.sh` (sem livro, Kemeri, `aperto`, `rodape`, `corte`, `mensagem`) → `c2\minimo\*.log`, `minimo*.json` | sim, no que mede | PASSOU sem livro e com o Kemeri (1248×606 / 1248×640 / 1246×629; 0 fora da vista sem barra; 0 espremidos; mensagem 480 px, documento 418–554), ao pixel do construtor; as quatro sabotagens REPROVARAM (1/82 px; 2208 px; 3 controles do Resultado sem barra na Clássica e na Foco; mensagem 0 px); nenhuma pele morta com sete processos de varredura ao lado |
| C18, o que fica à vista, mais largo que o portão | `c2\c18_vista.sh` (3 peles × com/sem livro × 400x300, 1280x640, 1366x728, 1248x800, 1440x900; também editores, listas, barras; corte por pai que não rola; altura) → `c2\c18_vista_*.out/json` | em parte | 0 controles dos tipos do portão cortados sem barra ou espremidos na largura fora do rodapé; **no rodapé, as zonas de ocupação e de dispositivos com 0 px** → novo bloqueante 2. Os «espremidos na altura» de editor/lista/cabeçalho são `setMaximumHeight` de desenho, iguais ao ciclo 1: descartados |
| C18, as sondas do ciclo 1 | `c18_visiveis.py` (foco, Kemeri) → `c2\c18_visiveis_c2.out` e, a 1280×641, `c2\c18_visiveis_1280_{foco,classica,fita}.out`; `c18_corte.py` → `c2\c18_corte_c2.out`; `c18_rodape_janela.py` → `c2\c18_rodape_janela_c2.out`; `c18_rodape2.py` → `c2\c18_rodape2_c2.out` | em parte | a barra horizontal do Resultado aparece (550 × 526 com barra); a 1248×640 e a **1280×641** (Foco) os botões do cartão da Revisão de texto têm 0 px à vista e só se chega a eles rolando (não bloqueante 4); rodapé: mensagem 480 px; com o Flores Rios a 1250 a zona de dispositivos desenha «…» |
| C18, rodapé com os nomes de todo o acervo | `c2\c18_rodape_zonas.py`, `c2\c18_rodape_acervo.py` contra `tronco` (`53dd066`) e `tronco_c1` (`8243e90`) → `*.out`, `*_c1.out` | **não** | zona de dispositivos cortada em **46/46 livros a 1248 e a 1366** (ciclo 1: 2 e 1), com 0 px em 14/46 a 1248 (ciclo 1: 0) → novo bloqueante 2 |
| C18, o teste de elisão mudado | `c2\c18_teste_elisao.py`; o teste antigo (`git show 8243e90:tests/test_qt_rodape.py`) rodado na árvore `53dd066` | sim | o antigo reprova porque, na faixa de 320 px, o nome desenha `''` (`'…' not found in ''`) — a razão do construtor confere; o novo dá 320 px ao nome e ele elide. Mudança legítima |
| C18, teclado e ordem do Tab | `c2\teclado_c2.sh` → `c2\teclado\*`; comparação com os JSON do ciclo 1 em `teclado\` | sim | PASSOU a 1280×800 e 1248×640 (Revisão de texto 50/50, Rotulagem 65/65, Galeria 57/57); **ordem do Tab idêntica à do ciclo 1** em Revisão de texto (49), Rotulagem (63), Galeria (53) e Resultado (31), nos dois tamanhos; o `QShortcut` tirado da Revisão de texto era import sem uso |
| B14, moldura | `b14_moldura_kmoch.py` → `c2\b14_moldura_kmoch_c2.out`; `c2\b14_moldura_c2.py` (5 itens da foto) → `c2\b14_moldura_c2.out` | sim | Kmoch 1.058/1.162/995 letras com a moldura; itens com moldura de 12 px: as mesmas letras que sem ela (209/195/234/187/422) e a cobertura medida (1,0); uma figura de meio-tom de 1,5× a largura do texto ao lado: nenhuma sinalização falsa |
| B14, piso | `cmp docs\quality\sol\f5_b14_fit3.json benchmarks\reports\sol\f5_b14_fit2.json` | sim, dito | idênticos; a tabela do §B14 confere; a grade do ajuste tem 0,88, que a regra «o menor piso que atinge o máximo» escolheria; o 0,90 vem da «grade de décimos», escrita depois da `dev` — o relatório diz |
| B14, população (os meus oito livros) | `b14_populacao.py c2\b14_pop "<Stean>:40..43" … "<Vladimirov>:200..203"` → `c2\b14_pop.out` | sim | **95 medidas, 6 sinalizadas**: Gallagher p. 50 (0,896, revisão), Reinfeld pp. 100/102/103 (abstenção), Karpov p. 103 e Vladimirov p. 201 (revisão), ruído de diagrama — como o relatório |
| B14, Stefaniu p. 49 (83 → 9 regiões) | `c2\stef49.py` (pp. 48–50 ×3, pp. 40–51 ×1, com a variável no ambiente ×1) | em parte | 9 regiões nas cinco; não reproduzi as 83 → não bloqueante 6 |
| A15, `test_strings` | `a15_brecha.py`, `a15_escondidos.py`, `c2\a15_brecha2.py` (Python do tronco, árvore `53dd066`) → `c2\a15_*.out` | em parte | os casos do ciclo 1 varridos (4/4); as regras escondem só os seis identificadores; três brechas construídas novas escapam → não bloqueante 7 |
| `test_arquitetura` | árvore `suite_sab` (`158f420`): `SyntaxError` e depois `from PyQt6 import QtCore` no topo de `ui/audit/minimo.py`; `pytest tests/unit/ui/test_arquitetura.py` | sim | «importar caissa.ui.audit.minimo falhou: Traceback…»; «trouxe um binding de Qt junto: PyQt6,PyQt6.QtCore,PyQt6.sip» (código 3); arquivo restaurado, `git status` vazio |
| A/B e evidência versionada | `c2\conf_sol_c2.py` → `c2\conf_sol_c2.out` | sim, com ressalva | `f5c2_on/b13_off/b14_off` = `f5_on/b13_off/b14_off` item a item (0 diferenças); `sol.json` do `158f420` = `f5c2_on` = `sol.json` do ciclo 1; `f5_ab.json` = JSON das corridas; aceitos com CER > 0,10: 30 → 7; B13 muda 7 itens, B14 27, nenhum pior; ressalvas → não bloqueante 8 |
| Portões do Sol no `sol.json` do `158f420` | `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` → `c2\sol_gate_c2.out` | sim | 150 DPI 0,0094 ≤ 0,020 ✓; CER limpo 0,0113, lances 0,9164, 157 inventados ✗; nenhuma regressão contra o `baseline`; `environment.commit` = `4fc0f4d` |
| Levenfis p. 134 | `b13_raster_paginas.py "<Levenfis>" 134 ron+eng` → `c2\b13_lev134_raster_c2.out`; `b13_importador.py … 134` → `c2\b13i_lev134.*` | sim | raster 19 → 15 regiões; importador 13 → 11, similaridade 0,9906 — como o relatório diz |
| Testes novos e tocados | suíte: `pytest tests/unit/ocr/test_table_rows.py tests/unit/ocr/test_ink_coverage.py tests/unit/classify/test_model_ruler.py tests/unit/ui/test_arquitetura.py tests/unit/ui/test_fileira_fluida.py tests/unit/ui/test_rotulo_que_encolhe.py tests/unit/ocr/test_sol_metrics.py`; tronco (árvore `53dd066`): `tests/test_qt_janela_cabe.py tests/test_qt_rodape.py tests/test_strings.py "tests/test_field_eval.py::ImpressaoDaMedicaoTests"` | sim | suíte **102 passaram**; tronco **86 passaram** (97 subtestes) |
| Tronco inteiro | `trunk_full_c2.sh` (árvore `53dd066`, `pytest tests -q -p no:cacheprovider -rfE`) → `trunk_full_c2.out` | sim | **4.786 passaram, 16 pulados, 8 xfail, 1 reprovado** em 540 s; o reprovado é `test_environment::…resolve_para_esta_arvore`, por construção da árvore efêmera; árvore limpa antes e depois. Um pulado a mais que o construtor (os `.pt` fora do git) |
| Suíte inteira, com o `test_arquitetura` na mesma corrida | `c2\suite_full_c2.sh` (`CAISSA_CVOFF_ROOT` e `PYTHONPATH` = árvore `53dd066`; `--ignore` de `test_packaging.py` e `test_roundtrip_corpus.py`) → `c2\suite_full_c2.out` | sim | **4.011 passaram, 17 pulados, 1 erro, 0 reprovados** em 728 s; 4.011 + 17 + 1 = 4.029 = 4.020 + 9 do construtor. O erro (`test_gpu_parity::test_cuda_actually_computes`) é o do meu ambiente no ciclo 1 (o carregador recusa `CAISSA_CVOFF_ROOT`); os 8 pulados a mais pedem artefatos fora do git |

### Os bloqueantes do ciclo 1

1. **B13 embaralhava as colunas estreitas da Gallagher — resolvido nos casos; não resolvido na classe.**
   Os casos que dei estão consertados e travados: Gallagher p. 50 pelo importador CER 0,2732 → 0,2028 (era
   0,7042), pp. 51–53 idênticas; as três páginas construídas idênticas ao desligado; Kmoch p. 44 sem grupo; os
   testes novos reprovam a regra do ciclo 1 por asserção em 5 casos. Na Gallagher inteira (176 páginas) nenhum
   grupo cruzou a calha. **Mas o que pedi no ciclo 1 — «o grupo nunca pode ter blocos dos dois lados de uma
   calha da página, com ou sem prosa para julgar» — não foi feito:** `_page_gutters` só aceita a calha que o
   próprio `find_gutters` acha quando há um bloco de prosa de um dos lados, e a primeira página real sem prosa
   que procurei embaralha (novo bloqueante 1).

2. **C18 — a janela cabia escondendo: resolvido nos controles; o conserto do rodapé esvaziou as zonas
   vizinhas.** Nenhum controle dos tipos do portão fica fora da vista sem barra ou espremido na largura, em 3
   peles × 5 tamanhos × com e sem livro (`c18_vista.sh`); o portão estendido passa e as quatro sabotagens
   reprovam; o teclado passa e a ordem do Tab é a do ciclo 1; a mudança do teste de elisão é legítima; a
   mensagem tem 480 px. Mas os 480 px saíram das zonas de dispositivos e de ocupação, que no ciclo 1 ficavam
   à vista (novo bloqueante 2).

3. **C17 — a coluna «≤ 0 errados» zerada pela grade: resolvido.** `model_ruler.cuts` = força bruta em todo
   valor distinto nos 15 modelos; a produção exporta 74 com zero errados (portão 0,998); a AURC é a esperança
   sobre as ordens dos empates (confere com Monte Carlo); a tabela e as conclusões (1)–(4) do §C17 batem com as
   linhas; o desempate está declarado; as linhas estão versionadas.

### Defeitos bloqueantes (novos)

1. **B13 intercala as duas colunas de um índice real do acervo, pelo importador de produção — através da calha
   que a própria regra acha.**
   - **Onde:** `src/caissa/ocr/layout/rows.py` — `_page_gutters` (a calha única de `find_gutters` só vale «when
     a side of it holds a block of prose»; «a move list alone (no prose in either band) return nothing»),
     `_is_column_gutter` (julga só com ≥ 8 linhas de ≥ 30 caracteres), `table_groups`.
   - **O quê:** Karpov, *Chess Combinations — World Champions 2* (acervo, raster), índice 268 (base 0; página
     impressa 268): o índice de jogadores em duas colunas estreitas, «Radulescu 8 / Ragozin 24 / … / R. FISCHER /
     Aaron 249 …» | «Benko 221, 246, 256, 261 / Bennett 218 / … / Saidy 262». Com o B13 desligado o texto sai na
     ordem do livro; **ligado, cada linha junta dois verbetes das duas colunas** — «Radulescu 8 Benko 991, 246,
     256, 261», «Ragozin 24 Bennett 218», «Sakharov 47 Byrne 8. 255, 271, 304» — e o cabeçalho «R. FISCHER»
     cai depois de verbetes da seção dele. **CER da leitura ligada contra a desligada 0,7606, WER 0,9502**, nas
     três execuções; decisão `review` nos dois lados, sem nenhum aviso de que a ordem foi reescrita. O rastro:
     `find_gutters` sobre todas as linhas acha a calha da página (672–1002 px de uma página de 1934), 0 linhas de
     prosa, `_page_gutters` descarta a calha, e os grupos `[[7, 4, 6], [5, 8, 9]]` juntam x 133–685 com
     x 1002–1458. A mesma classe aparece em mais três formas: o índice construído em duas colunas a 150 DPI
     (CER 0,1824 → 0,6554); uma página no leiaute da Gallagher p. 50 com notas de variantes (poucas palavras por
     linha) ao lado da lista numerada, construída e lida pelo serviço de produção (**0,0113 → 0,5845**, 3/3:
     «Or 21 Bd6 Rg8 22 g4 Rg6 26 Re3 Bxd4», «bishops: 26 Re3 Bxd4 27 32 Rd5 h6»); e a fixture `gallagher_p50()`
     do próprio teste do construtor, com as notas e o alto da coluna direita trocados por variantes — grupos
     `[[7, 2, 4, 8, 9], [1, 6]]`. A proteção nova depende de existir na página um bloco de ≥ 2 linhas com
     mediana de ≥ 4 palavras; índices, sumários, soluções e páginas de variantes não têm.
   - **Como reproduzir:** `unset CAISSA_FIGURINE_TESSDATA; .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\b13_importador.py "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\Karpov A - Chess Combinations -World Champions-2 (2011).pdf" 268 <saida.json>`
     (similaridade 0,4255; o CER pelo trecho em `c2\b13i_karpov268*.json`); rastro:
     `CAISSA_FIGURINE_TESSDATA=models\tessdata … b13_trace_blocos.py "<Karpov 2>" 268 eng 300`; varredura:
     `c2\b13_varredura.py "<Karpov 2>" 262-272 eng <saida.json>`; construídos: `c2\b13_tabelas.py`,
     `c2\b13_estreita.py`, `c2\b13_fixture_notas.py`; imagem da página: `c2\karpov2_p268.png`.
   - **Por que reprova:** é o bloqueante 1 do ciclo 1 numa página real que não é a Gallagher. O relatório afirma
     «dentro da coluna da página e nunca através da calha» (§0) e «Nenhum grupo atravessa a calha» (§0.2 e
     §B13); aqui atravessa, no caminho do produto, com os interruptores de produção, e o texto sai plausível e
     trocado sem sinal (Carta §3.3, falha silenciosa). Todo livro tem índice; o editor recebe, na revisão e na
     exportação, um índice com dois verbetes misturados por linha.

2. **C18: o conserto da mensagem do rodapé tirou a largura das zonas de dispositivos e de ocupação — a
   degradação para CPU volta a ser silenciosa.**
   - **Onde:** tronco `qt/rodape.py` (`LARGURA_DA_MENSAGEM = 480` como mínimo da mensagem enquanto há
     mensagem; o documento com mínimo 0 e o nome inteiro como largura desejada; no aperto o `QBoxLayout` tira a
     mesma quantidade de cada item não fixo, e as zonas curtas chegam a 0 primeiro); suíte
     `ui/audit/minimo.py` (`_rodape` mede mensagem, documento, barra e botões — não as zonas 3 e 4).
   - **O quê:** com o nome do livro na zona do documento, uma operação em curso e os dispositivos «peças cpu ·
     texto sem pesos», para os **46 PDFs do acervo**: a zona de dispositivos fica cortada (elidida ou 0 px) em
     **46/46 a 1248 e a 1366**, 45/46 a 1440, 22/46 a 1600, e com **0 px em 14/46 a 1248**; no ciclo 1
     (`8243e90`), cortada em 2 a 1248 e em 1 a 1366, 0 px em nenhum. Com o Flores Rios (87 caracteres):
     dispositivos 0 / 3 / 28 px de 135 a 1248 / 1366 / 1440 e ocupação («Importando o livro (p. 121 de 289)»)
     0 / 31 / 56 de 163, enquanto o nome recebe 418–526 px — no ciclo 1, 126/135 e 155/163 a 1248; com o nome de
     149 caracteres, as duas zonas em 0 px até 1600. Isolado a 1250 com o Flores Rios, a mensagem de 60
     caracteres usa 303 dos 480 px reservados (177 px vazios) e a zona de dispositivos desenha só «…»; a 1366,
     «peças …to cpu» (o «cuda» some).
   - **Como reproduzir:** `QT_QPA_PLATFORM=offscreen PYTHONPATH=src;<árvore 53dd066>\src;.venv-pack\Lib\site-packages .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c2\c18_rodape_acervo.py <árvore 53dd066>`
     (e com a árvore `8243e90` para o antes); `c2\c18_rodape_zonas.py`; `c18_rodape2.py` →
     `c2\c18_rodape2_c2.out`; na janela, `c2\c18_vista.sh` → `c2\c18_vista_*_*.out` (as duas zonas com 0 px no
     mínimo da janela — 1248×606, 1248×640, 1246×629 — nas três peles, com e sem livro).
   - **Por que reprova:** pela docstring do próprio tronco (`ui/dispositivos.py`), a zona de dispositivos existe
     porque «uma máquina com placa mas com o torch `+cpu` instalado roda na CPU em silêncio»; com ela em 0 px ou
     «…» a queda para CPU volta a ser silenciosa (Carta §3.3, «Degradação não sinalizada quando a GPU não está
     disponível») — e há reticências onde caberia (177 px vazios ao lado de uma zona em «…»). É o defeito do
     bloqueante 2 do ciclo 1 (uma zona do rodapé em 0 px) mudado de lugar pelo conserto, e o portão passa porque
     não mede essas zonas — ele diz medir «a linha do rodapé cheia».

### Defeitos não bloqueantes

1. **A regra de prosa por palavras recusa uma tabela legítima de células de quatro palavras.** A tabela do
   `table:2` com as aberturas por extenso («Defesa Siciliana, Variante Najdorf», «Gambito da Dama Recusado»), no
   formato e na degradação do corpus, a 150 DPI: desligado 0,4646, **regra do ciclo 1 0,0113, regra do ciclo 2
   0,3456** — duas células de abertura saem da linha delas e aparecem depois da tabela («12. Tal = Botvinnik
   Moscovo 1960 203», sem abertura). A docstring diz «A table's cells run 1–3 words»; o próprio corpus tem
   «Gambito da Dama Recusado» (`c2\b13_tabelas.py`, 3 execuções).
2. **O ganho do B13 nas tabelas do corpus não generaliza para outra fonte:** as mesmas cinco linhas do
   `table:2`, em Times e com a semente de degradação de outro id, saem 0,6224 → 0,5280 nas duas regras (o
   `table:2` do corpus, em Georgia: 0,0035). O portão de 150 DPI verde se apoia em três itens de tabela.
3. **O não bloqueante 7 do ciclo 1 (o B13 muda a leitura fora do grupo) aparece em lances na própria
   Gallagher:** p. 41, 1 → 12 regiões, «33 ♔d3 ♘xb5» (certo no desligado) → «33 ♔dd ♘8b5», «35 ♗xd6! ♔xd6» →
   «35 ‘Oxd6! @xd6»; p. 175, o 4º lance da partida 55 («♘c3 ♘f6») some da linha dele e «e4 ♘f6» entra na
   primeira linha com ruído de diagrama («An mWwWN e4 ♘f6 e4 eS») — `c2\ver_diff.py c2\b13v_gal_17.json 41`,
   `c2\b13v_gal_15.json 175`, imagens `c2\gal_p41_topo.png`, `c2\gal_p175.png`.
4. **No portátil-alvo maximizado (1280×641, pele Foco, a padrão) as ações principais do cartão da Revisão de
   texto — «Aceitar leitura», «Gravar edição», «Próxima» — ficam com 0 px à vista** e só se chega a elas
   rolando o cartão; na Fita, também a 1366×728 (6 botões). O portão as conta como «alcançáveis pela barra»
   (`c2\c18_visiveis_1280_*.out`).
5. **O portão da janela não mede altura, nem editores, listas e tabelas, nem as zonas 3 e 4 do rodapé** (é por
   isso que o bloqueante 2 passa).
6. **Stefaniu p. 49:** não reproduzi as 83 regiões (9 em cinco corridas, inclusive importando 40–51 juntas e
   com a variável no ambiente). A corrida que deu 83 (04:15) usou o `rows.py` anterior ao commit do ciclo 1 —
   o log dela registra «table-merged regions 96» no Stefaniu, e o `rows.py` commitado é o modificado às 05:50
   —, e comparar com o `99546e9` não testa aquela versão: «a diferença não é da regra» não se sustenta como
   escrito.
7. **A15: três brechas construídas ainda escapam** — `combo.addItems("pagina posicao revisao".split())` (lista
   minúscula que vai para a tela), `QLabel(", ".join(D))` e `combo.addItems([*D])` (`c2\a15_brecha2.py`);
   nenhuma frase de tela real escondida hoje.
8. **Evidência versionada incompleta para refazer os números:** `docs/quality/sol/f5_ab.json` não guarda o
   `answered`, e a média do `native` não se refaz dos itens (0,0143/0,0197 contra 0,0171/0,0235 do relatório; o
   resumo por estrato está lá, mas não é recalculável); e as corridas `f5c2_*` gravam `commit=99546e9`, sem
   marca de árvore suja, embora tenham medido o código antes do `4fc0f4d`.
9. **C17, frase da sabotagem:** «caem a 0 em 5 dos 15 e a quase nada nos outros» — `c4_aug0_s44` fica com
   71/92, `c4_w3_s42` com 66/88 e `c4_e_s44` com 11/66 nas colunas ≤ 1/≤ 2.
10. **Piso do B14:** dito, não resolvido — o 0,90 não sai da `calib` pela regra declarada (na grade do ajuste
    ela daria 0,88).

### O que falta

- A medida da janela na plataforma real (`windows`): tudo aqui foi `offscreen` com a fonte do produto imposta.
- O portão contra o checkout principal do tronco: não rodei (tem, sem commit, o trabalho de outra sessão).
- O `bench_sol` inteiro não foi rodado (o briefing proíbe); o A/B foi conferido item a item dos JSON.
- Varri a Gallagher inteira e as páginas finais de nove livros raster; não varri todas as páginas de todos os
  livros raster.
- A comparação às cegas da Carta não se aplica a esta frente e não foi feita.

### O que especificamente precisa mudar para eu aprovar (se REPROVADO)

1. **B13 — a calha da página vale sem prosa.** Uma calha única de `find_gutters` sobre todas as linhas, que
   divide a região em duas faixas de largura comparável (a da p. 268: 330 px no meio de 1934), é fronteira do
   grupo com ou sem prosa. Se isso desfizer as tabelas do corpus, a exceção precisa de evidência **positiva** de
   tabela (colunas de tipos diferentes, como nome × números; linha de cabeçalho), nunca da falta de prosa; duas
   colunas com o mesmo formato de linha (nome + números, em ordem alfabética) são duas listas; e uma linha de
   nota com dois ou mais números de lance embutidos é texto corrido para a regra, e não se junta a uma lista
   numerada. Travar por teste: a leitura da Karpov 2 p. 268 como fixture, a página de `c2\b13_estreita.py`, a
   fixture de `c2\b13_fixture_notas.py` sem bloco de prosa e a tabela de aberturas por extenso (aceita, ou dita
   fora do escopo com o número). Remedir a Gallagher inteira, as páginas finais dos livros raster (os comandos
   acima) e o A/B.
2. **C18 — as quatro zonas do rodapé à vista.** Dar às zonas de dispositivos e de ocupação a largura delas (ou
   um teto para o nome do livro, elidido no meio) e limitar a reserva da mensagem ao que a frase pede
   (`min(480, largura da frase)`); o portão medindo as quatro zonas com a linha cheia, no mínimo e a 1366×728,
   com o nome mais longo e um de ~60 caracteres do acervo, e uma sabotagem (a reserva atual) que reprove; um
   teste no tronco.
3. **No mesmo ciclo:** o `answered` (ou a média recalculável) na evidência versionada e o commit real das
   corridas do A/B; a frase da sabotagem do C17; a frase do Stefaniu p. 49; e, se o desenho for manter as ações
   do cartão da Revisão de texto abaixo da dobra a 1280×641, dizê-lo no relatório com o número.

## Crítico Claude — ciclo 3 (REPROVADO, 1 bloqueante)

VEREDITO: REPROVADO
CICLO: 3
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts novos estão em `C:\Python-Chess2\_critico_f5\c3\` (a saída de cada um ao lado,
`*.out`/`*.json`), os do ciclo 2 em `c2\` e os do ciclo 1 na raiz de `_critico_f5`; rodados da raiz da suíte com
`.venv\Scripts\python.exe`. A suíte principal estava no `e29a2b5` com `git status --short src tests benchmarks` vazio
e `git diff 3ff1830 -- src tests benchmarks` vazio (o código medido é o do `3ff1830`) do começo até as 13:53, quando
**outra sessão** passou a editar, sem commit, `src/caissa/ocr/layout/rows.py` (13:53:02) e
`tests/unit/ocr/test_table_rows.py` (13:54:08) no checkout principal — o texto novo cita este veredito ainda em
rascunho; não é objeto deste ciclo e não o toquei. Todas as minhas sondas terminaram antes (a última, `b13_sugestao`,
às 13:39), e a suíte inteira coletou os módulos às 13:40. «Tronco» =
minha árvore limpa `git worktree add --detach C:\Python-Chess2\_critico_f5\tronco 885149d`; «tronco_c2» = `53dd066`
(o antes do C18); `suite_c2` (`158f420`) para rodar os testes novos contra a regra do ciclo 2; `suite_c3`
(`e29a2b5`) para as sabotagens, feitas por monkeypatch num plugin do pytest (`c3\sabota_rows.py`) — nenhum arquivo
dos repositórios foi editado. A regra do ciclo 2 foi comparada na mesma corrida carregando o `rows.py` do `158f420`
ao lado e pondo-o no lugar de `rows_of_tables` (`c3\rows_c2.py`). Sondas do corpus e de páginas renderizadas com
`CAISSA_FIGURINE_TESSDATA=models\tessdata`; importador e janela sem ela. As quatro árvores ficaram limpas e foram
removidas com `git worktree remove`. O `git status` do tronco terminou igual ao do começo (só o trabalho de outra
sessão); o da suíte, com os dois arquivos que outra sessão editou às 13:53–13:54, além dos do começo. Nenhum
processo meu ficou vivo (as três varreduras que interrompi foram encerradas com os filhos; o único Python restante,
PID 1996, já existia às 07:51).

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| B13, Karpov 2 p. 268 pelo importador, 3 execuções | `b13_importador.py "<Karpov 2>" 268 c3\b13i_karpov268_r{1,2,3}.json` | sim | idêntica ao desligado nas três (similaridade 1,0000, 0 regiões agrupadas); os três JSON iguais byte a byte (`cmp`) |
| B13, Gallagher pp. 50–53, Reinfeld 1977 p. 319, Levenfis p. 134 pelo importador | `c3\importador_c3.sh` → `c3\b13i_{gallagher,reinf319,lev134}.*`; `gallagher_cer_c2.py c3\b13i_gallagher.json` | sim | p. 50 CER 0,2732 → **0,2028** (WER 0,4076 → 0,3121), pp. 51–53 idênticas; p. 319 (0,6807) e p. 134 (0,9906) com a mesma saída do ciclo 2 (`cmp` das saídas) |
| B13, as minhas varreduras do ciclo 2 com o código do ciclo 3 | `c3\varre_c3.sh` (`c2\b13_varredura.py`, 4 filas) → `c3\varre\*`; `c3\cmp_varre_c3.py` → `c3\cmp_varre_c3.out` | sim | **280 páginas**: mudam 46 no ciclo 2 e **43** no 3; a leitura ligada do ciclo 3 é a do ciclo 2 em **275**; a desligada é a mesma nas 280 (determinismo). As cinco diferenças: Karpov 2 pp. 267/268/270/271 passam a idênticas ao desligado, e a Levenfis p. 302 passa a mudar — os números do relatório conferem |
| B13, Levenfis p. 302 (sumário) | `c3\varre\lev_fim.json`; CER contra a minha transcrição da página (cada título com a sua página) | em parte | CER desligado **0,1221 → 0,0738** ligado: melhora; mas só **3 dos 6** títulos ficam com a página (XXII, XXIII, «Rezolvarea»); as páginas 260/271/272 dos outros três saem **depois** da última entrada, fora de ordem — o «passa a ler cada título com a sua página» do §0.5 não é literal |
| B13, as construções do ciclo 2 | `c2\b13_tabelas.py` → `c3\b13_tabelas_c3.out`; `c2\b13_estreita.py` ×3 → `c3\b13_estreita_c3_r{1,2,3}.out`; `c2\b13_fixture_notas.py`, `b13_caso_ruim.py`, `b13_render.py` → `c3\*_c3.out` | sim | aberturas por extenso **0,4646 → 0,0113** (ciclo 2: 0,3456); índice 0,1824 = desligado (ciclo 2: 0,6554); classificação 0,1388 → 0,0909; notas de variantes \| lista **0,0113 = desligado** (ciclo 2: 0,5845), sob título 0,0102 (ciclo 2: 0,5292), iguais nas 3 execuções; a fixture com variantes e sem prosa não atravessa (`[[7, 8, 9]]`); as construções do ciclo 1 inalteradas |
| B13, os 29 testes travam os casos? | `test_table_rows.py` do `e29a2b5` copiado para `suite_c2` e rodado contra o `rows.py` do `158f420` | sim | 29 passam no ciclo 3; contra a regra do ciclo 2 **9 reprovam** — 5 por asserção (índice, Dvoretsky com números próprios, notas de variantes, notas ao lado da partida, aberturas) e 4 por parâmetro que não existia |
| B13, cada regra nova com a sua sabotagem | `c3\sabota_rows.py` (plugin, `SABOTAGEM=…`) → `c3\sabota_rows.out` | em parte | largura desligada: 2 reprovam; nenhuma lista cruza: 1; toda coluna é lista: 2; sem `_notes`: 2; sem continuação: 1. **A semente sem o filtro de prosa** (`_is_cells(b) and not _is_prose(b)` → `_is_cells(b)`, reescrita no próprio módulo): **29 passam** — o «nunca o semeia» do §0.5 não tem teste |
| B13, tabelas legítimas de duas colunas | `c3\b13_tabelas3.py` (formato e degradação do corpus; desligado × ciclo 3 × ciclo 2), 3 execuções no caso que muda | **não** | «campeões mundiais (nome \| período)» a 150 DPI: desligado 0,5696, **ciclo 3 0,5696, ciclo 2 0,0000** — a calha única de faixas comparáveis agora a recusa; as outras (emparceiramento, jogador \| rating, abertura \| lances, rodada \| resultado) iguais nos três. Não bloqueante 1 |
| B13, listas de lances que a evidência positiva recusa | `c3\b13_lista_recusada.py` | **não** | limpa 0,6632 → 0,0632 (como no ciclo 2); com o resultado na última linha, idem; **com as avaliações separadas do lance** («31 Nh1 !?», «Bxd4 +-»): desligado 0,6724, **ciclo 3 0,6724, ciclo 2 0,0603**. Não bloqueante 1 |
| B13, notas que escapam de `_notes` | `c3\b13_estreita3.py [--justificar]` ×3 → `c3\b13_estreita3*.out`; `c3\b13_notas_reais.py 6`; `c3\b13_pdf_construido.py` + `b13_importador.py c3\construido.pdf 0,1,2,3` ×3; `c3\b13_tabulada.py` | **não** | → **bloqueante novo 1** |
| B13, prosa em alemão/holandês e a continuação | `c3\continua_idiomas.py`, `c3\prosa_por_palavras.py` (camada de texto de Gunderam, Euwe, Kemeri, Kmoch, Mieses, Nunn, Burgess, Fischer, rejustificada a 22–27 car.) | sim, com ressalva | a continuação tira a «prosa por palavras» de 5/244, 16/364, 14/295 parágrafos alemães de 3 linhas (e ≤ 8 dos de 4+); holandês 0. Mas só 3–39 % dos parágrafos estreitos reais são prosa por palavras, conforme a língua e o tamanho (inglês 9–34 %): a regra de palavras quase nunca segura uma coluna estreita real; quando algo segura, é o comprimento das linhas ou a largura das faixas |
| B13, livros alemães e holandeses inteiros, três leituras | `c3\b13_varredura3.py`: Estrin 0–87 (`deu+eng`, raster), Gunderam 10–142/2 e Kmoch 10–132 (raster 300 DPI da página) → `c3\v3_*.out/json` | sim | Estrin **88/88** páginas com a leitura ligada do ciclo 3 = a do ciclo 2; 16 mudam do desligado (ruído de diagrama, variante trocada). Gunderam 32 páginas (pp. 10–72, de 2 em 2) e Kmoch 48 (pp. 10–60 e 11–53) — varreduras interrompidas por mim: ciclo 3 = ciclo 2 em todas, 3 e 1 mudam do desligado (ruído, uma legenda, um fólio). Nenhum grupo com blocos dos dois lados da calha reconhecida |
| C18, portão com as cinco sabotagens | `c3\minimo_c3.sh` → `c3\minimo\*.log`, `minimo*.json` | sim | sem livro e com o Kemeri **PASSOU** (1248×606 / 1248×640 / 1246×629; mensagem 320, documento 272–288, dispositivos 135, ocupação 171; a 1366 documento 390–408), as cinco sabotagens **REPROVARAM** (`reserva`: dispositivos e ocupação 0 px), 0 tracebacks. 3 dos 7 JSON diferem dos do construtor só na primeira medida (dispositivos 162/ocupação 152 num nome, um «espremido» a mais na sabotagem `rodape`): o arnês às vezes mede antes de a linha estar cheia |
| C18, as zonas com o acervo | `c2\c18_rodape_acervo.py <tronco>` → `c3\c18_rodape_acervo_c3.out`; `c2\c18_rodape_zonas.py` → `c3\c18_rodape_zonas_c3.out` | sim | dispositivos cortados em **0 dos 46** a 1248/1366/1440/1600 (ciclo 2: 46/46/45/22); a frase de 60 car. com a largura dela (303 px), documento 285–297 a 1248 |
| C18, as zonas com frases e operações reais do produto | `c3\c18_rodape_c3.py <tronco>` (46 livros × 6 larguras × 2 frases × 3 operações) → `c3\c18_rodape_c3.out`; o mesmo contra `tronco_c2` → `c3\c18_rodape_c3_tronco_c2.out` | em parte | dispositivos cortados em 0 em todos os casos; **o nome do livro, no mínimo, 95–96 px** («1937 Ke… página», a página some) a 1246–1248 com a operação real «aquecendo o modelo (<caminho do .pt>)» (ciclo 2: 83 px); a ocupação elidida em 46/46 com ela e em 36–45/46 com «Exportando para EPUB (<nome>.epub)». Não bloqueantes 4 e 5 |
| C18, a mensagem de 320 px | `c3\c18_caracteres.py <tronco>` → `c3\c18_caracteres.out`; `c3\c18_rodape_c3*.out` | em parte | 320 px são **57 caracteres** (5,6 px/car.), não ~45; a frase de erro do próprio produto sem o `.pt` (`leitura.FRASE_SEM_MODELO`, 84 car., 474 px) sai elidida em **46/46 livros de 1246 a 1440 px**, e a 1600 em 22/46 (com a importação) a 46/46 (com o aquecimento do modelo) (ciclo 2, 480 px: inteira em 46/46 a 1248, 1366 e 1600) |
| C18, `RotuloElidido(piso=…)` nos outros usos | `grep RotuloElidido` no tronco; `test_qt_rodape.py`, `test_qt_janela_cabe.py` | sim | o único outro uso é `painel_do_pdf.lbl_pdf`, com `piso=0` (o `minimumSizeHint` e o `definir_texto` antigos) |
| C18, o que fica à vista a 1280×641 | `c18_visiveis.py` nas três peles → `c3\c18_visiveis_1280_*.out` | sim, com ressalva | as seis ações da Revisão de texto à vista; abaixo da dobra a fileira de figurinas (8; na Fita também o rótulo da verdade) — como o relatório diz. **O Resultado** tem 6 controles com 0 px na Foco («Salvar a posição», «Salvar todas as posições da página», «Desfazer», «Refazer», «Limpar», «Esconder incerteza»), 13 na Fita e 1 na Clássica — igual ao ciclo 2 e não dito. Não bloqueante 6 |
| C18, o que fica à vista, mais largo que o portão | `c2\c18_vista.py` (3 peles × com/sem livro × 5 tamanhos) → `c3\c18_vista_*.out` | sim | 0 controles dos tipos do portão cortados sem barra (ciclo 2: as duas zonas do rodapé com 0 px em todo tamanho); os 5 «espremidos na altura» restantes são o `QLineEdit` do combo de língua da Rotulagem (18 de 22 px), iguais ao ciclo 2. A Clássica com livro passou do tempo do meu `timeout` **na saída** (o `encerrar(esperar=True)` do meu arnês esperava a importação do filho), com a medida completa |
| C18, teclado e ordem do Tab | `c3\janela_c3.sh` → `c3\teclado\*`; comparação com os JSON do ciclo 2 | **não** | PASSOU a 1280×800 e 1248×640 (Revisão de texto 50/50, Rotulagem 65/65, Galeria 57/57); ordem do Tab idêntica em 7 áreas, mas **na Revisão de texto mudou**: as seis ações vêm logo depois da tabela (posições 11–16) e **antes** do cartão (leitura, alternativas, verdade, figurinas: 17–26). Não bloqueante 3 |
| A15, brechas | `c3\a15_brecha3.py` (Python do tronco, árvore `885149d`) → `c3\a15_brecha3.out`; `a15_escondidos.py` → `c3\a15_escondidos_c3.out` | em parte | as três do ciclo 2 varridas; **8 novas escapam** (a lista minúscula guardada num nome e depois mostrada, dentro de `sorted()`, juntada para um `QLabel`, capitalizada numa lista; chaves por `map(str.title, D)`, `D.copy()`, `self.D`, `modulo.D`); as regras seguem escondendo só os seis identificadores |
| Evidência e A/B | `c3\conf_sol_c3.py` → `c3\conf_sol_c3.out` | sim | `f5c3_*`: `commit=3ff1830`, `dirty_code=[]`, `SOL_CONFIG` explícito; **idênticas item a item** às `f5c2_*` e `f5_*` em todo campo numérico por item (CER, decisão, answered, WER, linhas, lances, caracteres, confiança…); o `sol.json` do `e29a2b5` = `f5c3_on` = o do ciclo 2; `f5_ab.json` = os JSON das corridas; médias por estrato refeitas **só** dos itens com `answered` = resumo (maior diferença 0,000004); aceitos com CER > 0,10: 30 → 7; B13 muda 7 itens, B14 27, nenhum para pior. O texto dos itens **não** é gravado nos JSON («idênticos… em texto» não é verificável) |
| Portões do Sol no `sol.json` do `e29a2b5` | `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` → `c3\sol_gate_c3.out` | sim | 150 DPI 0,0094 ≤ 0,020 ✓; CER limpo 0,0113, lances 0,9164, 157 inventados ✗; nenhuma regressão contra o baseline |
| C17, a frase da sabotagem | `model_ruler_20260923_074145_f5_c17_c2_sabotado.json` × `docs\quality\campo\f5_c17_regua.json` | sim | 5/15 com as três colunas em 0; nos outros 10 a «≤ 0» entre 0 e 27 (verdadeira 27–104); 71/92, 66/88, 11/66 contra 105/110, 99/106, 101/108 |
| Stefaniu p. 49 | relatório linhas 122 e 504 | sim | diz o que medi no ciclo 2 (a corrida de 04:15 mediu um `rows.py` anterior ao commit; as 83 não se refazem) |
| A transcrição do meu ciclo 2 | `git show 3ff1830 -- docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` × `veredito_ciclo2.md` | sim | idêntica salvo o nível dos títulos (`##` → `###`) |
| Testes tocados | suíte: `pytest tests/unit/ocr/test_table_rows.py tests/unit/ui/test_revisao_de_texto_view.py tests/unit/ui/test_arquitetura.py tests/unit/ui/test_fileira_fluida.py tests/unit/ui/test_rotulo_que_encolhe.py tests/unit/ocr/test_ink_coverage.py tests/unit/classify/test_model_ruler.py tests/unit/ocr/test_sol_metrics.py`; tronco (árvore `885149d`): `test_qt_janela_cabe.py test_qt_rodape.py test_strings.py "test_field_eval.py::ImpressaoDaMedicaoTests"` | sim | suíte **114 passaram**; tronco **89 passaram** (97 subtestes) |
| Tronco inteiro | `c3\testes_full_c3.sh` (árvore `885149d`) → `c3\trunk_full_c3.out` | sim | **4.789 passaram, 16 pulados, 8 xfail, 1 reprovado** em 1.420 s (com as varreduras ao lado); o reprovado é `test_environment::…resolve_para_esta_arvore`, por construção da árvore efêmera; 4.789 + 16 = 4.790 + 15 do construtor (um pulado a mais: artefato fora do git, como no ciclo 2); árvore limpa antes e depois |
| Suíte inteira, com o `test_arquitetura` na mesma corrida | `c3\testes_full_c3.sh` → `c3\suite_full_c3.out` | sim | **4.016 passaram, 17 pulados, 1 erro, 0 reprovados** em 857 s; 4.016 + 17 + 1 = 4.034 = 4.025 + 9 do construtor; o erro é o `test_gpu_parity::test_cuda_actually_computes` do meu ambiente (o mesmo dos ciclos 1 e 2) e os 8 pulados a mais pedem artefatos fora do git (`.pt`, acervo de PDFs, listas do tronco). Os módulos foram coletados às 13:40, com o código do `3ff1830` (ver as convenções) |

### Os bloqueantes do ciclo 2

1. **B13 intercalava as duas colunas de um índice real — resolvido.** A Karpov 2 p. 268 pelo importador de
   produção sai idêntica ao desligado nas três execuções (JSON iguais byte a byte); nas varreduras, as pp. 267, 268,
   270 e 271 passam a idênticas ao desligado; o índice construído a 150 DPI 0,1824 = desligado (era 0,6554); as notas
   de variantes ao lado da lista 0,0113 = desligado (era 0,5845), sob título 0,0102 (era 0,5292); a fixture de
   variantes sem prosa não atravessa; as aberturas por extenso 0,0113 (era 0,3456). Os testes novos reprovam a regra
   do ciclo 2 por asserção em 5 casos. Nas 280 páginas, a leitura ligada é a do ciclo 2 em 275, e as 5 que mudam
   melhoram. **Mas a classe — duas colunas estreitas juntadas linha a linha através da calha — continua aberta
   onde as faixas não são comparáveis e a coluna de notas não é «variantes» nem «prosa por palavras»**, e o
   importador aceita o resultado (bloqueante novo 1).

2. **C18: a reserva da mensagem esvaziava as zonas de dispositivos e de ocupação — resolvido.** Dispositivos
   cortados em 0/46 livros a 1248–1600 (eram 46/46/45/22); o portão mede as quatro zonas com o nome mais longo e o
   da Karpov 2, no mínimo e a 1366×728, PASSOU com e sem livro e as cinco sabotagens reprovaram (a `reserva` com as
   duas zonas em 0 px); há teste no tronco com a sabotagem ao lado. A reserva ficou em `min(320, frase)`, não em
   `min(480, frase)` como pedi — o custo não está dito (não bloqueante 4).

Os itens do mesmo ciclo: o `answered` na evidência e as médias recalculáveis — feito; o commit real e o
`dirty_code` das corridas — feito (`3ff1830`, `[]`); a frase da sabotagem do C17 — confere; a do Stefaniu p. 49 —
confere; as ações da Revisão de texto a 1280×641 — à vista nas três peles, e o que desceu está dito; mas a
mudança trocou a ordem do Tab (não bloqueante 3).

### Defeitos bloqueantes (novos)

1. **B13 junta, linha a linha, uma coluna de notas comuns e a lista de lances da outra coluna — e o importador de
   produção aceita a página embaralhada.**
   - **Onde:** `src/caissa/ocr/layout/rows.py` — `_page_gutters` (a calha única só vale com faixas de largura
     comparável, `page_band_share = 0.5`, ou com um bloco de «prosa» de um lado), `_is_prose` (prosa = ≥ 3 linhas
     com mediana ≥ 30 car., **ou** mediana de ≥ 4 palavras e continuação, **ou** `_notes`: metade das linhas com
     número de lance dentro), `table_groups`.
   - **O quê:** a página no leiaute da Gallagher p. 50 (Times 10 pt, colunas de 1,95 pol., 300 DPI, notas
     justificadas na coluna) com a lista de lances da partida **sem tabulação** na outra coluna. As notas são
     anotação comum — prosa com alguns lances («White could also try / 21 Bd6!?, when after / 21...Rg8 22 g4 Rg6
     the / position is unclear.») —, com mediana de 20–28 caracteres e de 3 palavras por linha e menos da metade
     das linhas com número de lance dentro: não são prosa por comprimento, nem por palavras, nem `_notes`; as
     faixas da calha única têm razão **0,41** (587 e 240 px). Nada segura a calha, e o grupo sai «White could also
     try 26 Re3 Bxd4 / 21 Bd6!?, when after 27 Rxd4 Rd6 / …». Números (o importador e o `b13_estreita3.py --justificar` em 3 execuções, iguais):
     - pelo **importador de produção**, a página gravada como PDF raster (`c3\construido.pdf`): p. 0 (inglês)
       CER **0,0052 → 0,6440, decisão `accepted` nos dois lados, cobertura da tinta 1,0** — a leitura
       embaralhada sai **aceita**; p. 1 (alemão) 0,2284 → 0,5499; pp. 2 e 3 com **notas reais** da Kmoch
       (pp. 45 e 77 da camada de texto, holandês, rejustificadas) 0,0367 → **0,5598** e 0,0754 → **0,5748**
       (`review`, sem aviso de reordenação);
     - pelo serviço (`b13_estreita3.py --justificar`): inglês 0,0140 → **0,6527** (300 DPI) e 0,0087 → 0,6475
       (200); alemão 0,2132 → 0,5364 e 0,2335 → 0,6616; a regra do ciclo 2 dá os mesmos números (o defeito vem
       do ciclo 2 e o conserto do ciclo 3 não o alcança);
     - com a lista **tabulada** a 45 % da coluna: 0,2373 → **0,6510**; a 60 % (a Gallagher põe as pretas a
       ~63 %) a página sai certa e melhora: 0,2356 → 0,0140 (`b13_tabulada.py`). A fronteira entre embaralhar e
       acertar cai no meio da tipografia real;
     - com notas reais de cinco livros do acervo na mesma medida (`b13_notas_reais.py 6`): a Kmoch embaralha 2 de
       6 páginas; Nunn, Burgess, Gunderam e Euwe 0 de 6 (nessa medida as linhas deles passam de 30 car. e são prosa
       por comprimento).
     Nas páginas reais não achei a configuração: a Gallagher inteira (176), as páginas finais de nove livros (104),
     a Estrin inteira (88), 32 da Gunderam e 48 da Kmoch. A Gallagher tabula as pretas, e mesmo assim a calha da
     página dela não é reconhecida pela regra nova: na p. 50 o `find_gutters` acha **duas** calhas (754–817 e
     1171–1193 — a sonda `scratchpad\probe_calha.out` do próprio construtor), o `_page_gutters` devolve nada, e numa
     das leituras que o árbitro descarta o grupo **cruza** (o bloco 3, x 266–628, a lista da coluna esquerda, com os
     blocos 7–9 da direita); a leitura que o importador entrega não cruza (conferido no `c3\b13i_gallagher.json`).
   - **Como reproduzir:** `CAISSA_FIGURINE_TESSDATA=models\tessdata .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c3\b13_pdf_construido.py C:\Python-Chess2\_critico_f5\c3\construido.pdf`;
     depois, **sem** a variável, `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\b13_importador.py C:\Python-Chess2\_critico_f5\c3\construido.pdf 0,1,2,3 <saida.json>`
     (as verdades em `c3\construido_p{0..3}_verdade.txt`); `c3\b13_estreita3.py --justificar`; `c3\b13_tabulada.py`;
     na regra, sem OCR: `c3\b13_fixture_notas_comuns.py` (grupos `[[2, 1]]`, atravessa).
   - **Por que reprova:** é a classe dos bloqueantes 1 dos ciclos 1 e 2 (colunas estreitas embaralhadas pelo B13),
     agora com a decisão **`accepted`**: a Carta §3.3 reprova sozinhos a falha silenciosa e a «confiança alta em
     resultado errado». Com o B13 desligado a mesma página sai certa e aceita; ligado sai trocada e aceita. E o
     relatório diz o contrário: «nunca através da calha» (§0) e, das notas, «é o que segura a página de notas ao
     lado da partida, onde as faixas não são comparáveis» (§0.5, linha 293) — segura só notas de variantes densas.
     O que pedi no ciclo 2 (a calha única de faixas **comparáveis** como fronteira, e a nota com números de lance
     embutidos como texto corrido) foi feito; o defeito está fora dessas duas condições, mas é a mesma classe, e o
     relatório a dá por fechada. O conserto não é caro: medi uma regra de «texto corrido» sem contar palavras (bloco de ≥ 4 linhas, mediana
     acima de uma célula, linhas que continuam a frase; `c3\sabota_rows.instalar_sugestao`) — as quatro páginas
     voltam ao desligado (0,0140 / 0,2132 / 0,0299 / 0,0713), as tabelas do ciclo 2 ficam como estão (aberturas
     0,0113, classificação 0,0909, índice 0,1824, controle 0,5280; `c3\b13_sugestao.out`) e dos 29 testes só
     reprovam 4 asserções de **sabotagem** (a regra nova segura o que a sabotagem soltava).

### Defeitos não bloqueantes

1. **As regras novas recusam o que o ciclo 2 lia por linha, e isso não está dito** (volta ao desligado):
   a tabela de duas colunas «nome \| período» a 150 DPI, **0,0000 no ciclo 2 → 0,5696** (`b13_tabelas3.py`, 3
   execuções); a lista de lances com as avaliações separadas do lance («31 Nh1 !?», «Bxd4 +-»), **0,0603 →
   0,6724** (`b13_lista_recusada.py`). A evidência positiva exige ≤ 2 tokens em toda linha da coluna das pretas.
2. **O filtro de prosa na semente** (`seeds = … if _is_cells(b) and not _is_prose(b)`, novo no ciclo 3) não tem
   teste: sem ele os 29 passam (`sabota_rows.py`, `SABOTAGEM=semente_de_prosa`).
3. **A ordem do Tab da Revisão de texto mudou e o relatório diz que não.** Tirar as ações da rolagem pôs as seis
   ações logo depois da tabela e antes do cartão (posições 11–16; o cartão 17–26) — a ordem do foco deixa de seguir
   a visual (as ações estão embaixo do cartão). O portão do teclado só conta alcance, e o §C18 (linha 707) diz
   «as fileiras fluidas não mudaram a ordem de ninguém», com as árvores dos ciclos 2 e 3.
4. **A reserva de 320 px elide a frase de erro do próprio produto.** `leitura.FRASE_SEM_MODELO` («Modelo de casas
   não encontrado. Aponte o arquivo .pt em Ferramentas ▸ Configurações…», 84 car., 474 px) e o estado vazio do
   Resultado (73 car., 409 px) — o primeiro erro de todo clone limpo — saem elididos («Modelo de casas não
   encont…rramentas ▸ Configurações…») em 46/46 livros de 1246 a 1440 px e, a 1600, em 22/46 a 46/46 conforme a operação; com 480 px (ciclo 2)
   cabiam inteiros. Pedi `min(480, largura da frase)`; o construtor pôs 320 e escreveu «~45 caracteres» (§0.5 linha
   323, docstring de `LARGURA_DA_MENSAGEM`): são 57. O custo não está no relatório.
5. **O nome do livro chega a 95 px com uma operação real, e a ocupação não é «curta e de forma conhecida».** Com
   «aquecendo o modelo (<caminho do .pt>)» (`qt/leitura.py:192`) a zona do documento do Kemeri — o livro do próprio
   portão — fica com **95–96 px** a 1246–1248 («1937 Ke… página»: a página some; ciclo 2: 83 px), abaixo dos 120
   do portão, que só mede a importação; e a ocupação sai elidida em 46/46 com essa operação e em 36–45/46 com a
   exportação EPUB, contra a docstring de `LARGURA_DA_ZONA` («textos curtos e de forma conhecida»).
6. **A 1280×641 (portátil-alvo maximizado, pele Foco) as ações do Resultado ficam com 0 px à vista** — «Salvar a
   posição», «Salvar todas as posições da página», «Desfazer», «Refazer», «Limpar», «Esconder incerteza» (13
   controles na Fita, 1 na Clássica); só pela barra. Igual ao ciclo 2 e não dito no §0.3, que fala só das figurinas.
7. **Frases do relatório que não batem:** §0 (linha 45), coluna «depois» do C18: «480 px garantidos à mensagem»
   (o código dá 320); §0.5: «a Levenfis p. 302 passa a ler cada título com a sua página» (3 de 6; as outras três
   páginas saem depois da última entrada, embora o CER melhore 0,1221 → 0,0738); «idênticos… em CER, decisão e
   texto» (os JSON não guardam o texto; todos os campos numéricos por item conferem); «~45 caracteres».
8. **A15: oito brechas construídas novas escapam** (`a15_brecha3.py`), entre elas a lista minúscula guardada num
   nome e passada ao `addItems` — que a regra nova isenta por desenho; nenhuma frase de tela real escondida hoje.
9. **O arnês do portão às vezes mede antes de a linha estar cheia:** 3 dos 7 JSON diferem dos do construtor só no
   primeiro nome medido (dispositivos 162/ocupação 152, e um «espremido» a mais na sabotagem `rodape`). E os JSON do
   portão não gravam o commit nem o estado da árvore do tronco medida: a do construtor (`C:\Python-Chess2\_f5c2_tronco`)
   é um `8243e90` com os arquivos do `885149d` copiados por cima — conferi que são iguais salvo o fim de linha
   (`diff --strip-trailing-cr`), mas o JSON não diz isso (o `bench_sol` passou a gravar o `dirty_code`; o portão não).
10. **No caminho sem máscara de diagramas** (o das varreduras de «página real», do construtor e minhas), a Estrin
    p. 77 (alemão, raster) sai com o bloco do alto da coluna direita («15.La4: Da4: 16.Df3 Sc6 17.b3! / Diese
    Möglichkeit…» e «Diagramm 105») **antes** da prosa da coluna esquerda — igual no ciclo 2; pelo importador só o
    ruído do diagrama muda. E a Estrin p. 29 pelo importador troca a variante: «13....Ld4: 14.Lg6! d5 15.Df3+» →
    «15....Ld4: 14.Lg6! ds 15.Di3+» (e «17.Le6%» → «17.Le6+») — o não bloqueante 3 do ciclo 2, em alemão. A sonda do
    construtor lê a Estrin com `ron+eng` (`b13_c3_all.sh`).
11. **Ficam, ditos:** a Gallagher pp. 41/175, o `table:2` em Times, o portão sem altura, o piso do B14.

### O que falta

- A medida da janela na plataforma real (`windows`): tudo `offscreen`, com a fonte do produto imposta.
- O `bench_sol` inteiro não foi rodado (o briefing proíbe); o A/B foi conferido item a item dos JSON.
- As varreduras da Gunderam (32 de 67 páginas) e da Kmoch (48 de 123) foram interrompidas por mim, pelo tempo; a Levenfis e
  a Stefaniu inteiras não foram varridas.
- Não achei página real com o defeito bloqueante: a prova é a página construída com a medida da Gallagher, notas
  comuns e notas reais da Kmoch, pelo importador de produção.
- A comparação às cegas da Carta não se aplica a esta frente.

### O que especificamente precisa mudar para eu aprovar (se REPROVADO)

1. **B13 — texto corrido nunca entra num grupo, conte ou não quatro palavras.** Uma coluna de notas comuns
   (poucas palavras por linha, poucos números de lance dentro) ao lado de uma lista de lances sem tabulação, ou
   tabulada a menos da metade da coluna, não pode ser juntada linha a linha. Um caminho medido: um bloco de ≥ 4
   linhas, com a linha mediana mais longa que uma célula e linhas que continuam a frase, é texto corrido (ou outro
   critério, desde que positivo e medido). Travar por teste com as minhas páginas — `c3\construido.pdf` pp. 0–3 pelo
   importador (a p. 0 não pode sair `accepted` embaralhada), `b13_estreita3.py --justificar`, `b13_tabulada.py`
   (45 %) — e as sabotagens atualizadas; manter a Karpov 2 p. 268 idêntica, a Gallagher p. 50 em 0,2028, os 7 itens
   do A/B e as aberturas em 0,0113; remedir as 280 páginas. Corrigir o §0 («nunca através da calha») e o §0.5
   (linha 293) para o que a regra de fato segura.
2. **No mesmo ciclo:** (a) a ordem do Tab da Revisão de texto de volta à visual (o cartão, depois as ações — um
   `setTabOrder`), travada por teste ou pelo portão do teclado comparando a ordem, e o §C18 (linha 707) corrigido;
   (b) dizer no relatório, com os números, o que as regras novas recusam (a tabela «nome \| período» 0,0000 →
   0,5696; a lista com avaliações separadas 0,0603 → 0,6724) e dar teste ao filtro de prosa da semente; (c) dizer o
   custo da reserva de 320 px (a frase sem o `.pt`, 474 px, elidida em 46/46 livros a 1246–1440) e corrigir «~45»
   para ~57 caracteres — ou voltar a `min(480, largura da frase)`; (d) dizer o documento com 95 px sob «aquecendo o
   modelo» e as ações do Resultado abaixo da dobra a 1280×641; (e) corrigir o §0 (320, não 480), a frase da Levenfis
   p. 302 e o «em texto».

## Crítico Claude — ciclo 4 (REPROVADO, 2 bloqueantes)

VEREDITO: REPROVADO
CICLO: 4
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts e as saídas deste ciclo estão em `C:\Python-Chess2\_critico_f5\c4\` (a saída de
cada um ao lado, `*.out`/`*.json`; as filas em `*.sh`, com `runs.log`), os dos ciclos anteriores em `c3\`, `c2\` e na
raiz; rodados da raiz da suíte com `.venv\Scripts\python.exe`. A suíte principal estava no `7d41996` com
`git status --short src tests benchmarks` vazio e `git diff 7736617 -- src tests benchmarks` vazio das 16:31
(`c4\estado_inicio.txt`) até pelo menos as 16:56:50 (`c4\varre\runs.log`, «inicio … src=[0]»); às 17:23:09 («fim …
src=[1]») o checkout tinha, sem commit, `src/caissa/ocr/layout/rows.py` (última escrita 17:23:21) e depois
`tests/unit/ocr/test_table_rows.py` — do **construtor**, começando o ciclo 5 a partir de ~17:20 depois de ler o
rascunho deste veredito (aviso dele; o texto novo cita números do rascunho que só existiam depois das 17:08). Não é
objeto deste ciclo e não o toquei. A minha última sonda de OCR no checkout principal começou às 17:08 (a Flores), e a
varredura carregou o módulo às 16:56:50; mesmo assim, o que carregou o `rows.py` do checkout depois das 16:56:50 foi
refeito numa árvore limpa minha do `7d41996`
(`git worktree add --detach C:\Python-Chess2\_critico_f5\suite_c4 7d41996`): a Flores pelo importador (JSON igual byte
a byte ao da primeira medida), as sabotagens (iguais), a Levenfis e a Stean da varredura (as 22 páginas iguais, ligada e desligada, à corrida no checkout e ao ciclo 3); a suíte inteira
rodou nessa árvore. O código medido é o do `7736617`. «Tronco» = a minha árvore limpa `git worktree add --detach C:\Python-Chess2\_critico_f5\tronco 7cd400a`
(sem o `.pt`, como todo clone); «suite_c3» = `git worktree add --detach C:\Python-Chess2\_critico_f5\suite_c3 e29a2b5`,
só para comparar a ordem do Tab com o ciclo 3. A regra do ciclo 3 foi comparada carregando ao lado o `rows.py` do
`3ff1830` (`c3\rows_3ff1830.py`, conferido igual ao do commit) e pondo-o no lugar de `rows_of_tables`; as sabotagens,
por monkeypatch num plugin do pytest (`c4\sabota_rows_c4.py`). Sondas do corpus e de páginas renderizadas com
`CAISSA_FIGURINE_TESSDATA=models\tessdata`; importador, janela e testes sem ela. No máximo três processos de OCR ao
mesmo tempo (quatro por alguns minutos). Nenhum arquivo dos dois repositórios foi editado. As três árvores minhas
foram removidas com `git worktree remove` (a da suíte depois de eu apagar as cópias de artefatos que pus nela).
No fim (17:54, `c4\estado_fim.txt`), a suíte continua no `7d41996` com o trabalho do ciclo 5 do construtor sem
commit (`rows.py`, `minimo.py`, `teclado.py`, `revisao_de_texto.py`, `cartao_da_linha.py`, dois testes e um novo),
e o tronco passou ao `37f662b` (commit do construtor durante esta crítica; eu medi a minha árvore do `7cd400a`).
Nenhum processo meu ficou vivo: o PID 1996 é de antes, e às 17:53 outra sessão rodava a minha
`c2\b13_varredura.py` (não mexi).

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| Bloqueante do ciclo 3: as minhas páginas pelo importador, 3 execuções | `c4\sondas_c4.sh` (`b13_importador.py c3\construido.pdf 0,1,2,3`) → `c4\b13i_construido_r{1,2,3}.json`; CER pelo `scratchpad\c4\cer_construido.py` do construtor → `c4\cer_construido.out` | sim | p. 0 **0,0052 `accepted` = desligado** (ciclo 3: 0,6440 `accepted`), p. 1 0,2284, p. 2 0,0367, p. 3 0,0754 — as quatro idênticas ao desligado, 0 grupos; os três JSON iguais byte a byte (`cmp`) |
| Bloqueante do ciclo 3: pelo serviço | `c3\b13_estreita3.py --justificar` → `c4\estreita3_just.out`; `c3\b13_estreita3.py` → `c4\estreita3.out`; `c3\b13_tabulada.py` → `c4\tabulada.out` | sim | inglês 0,0140 / 0,0087 (300/200 DPI) = desligado; alemão 0,2132 = desligado a 300 e **0,0152** a 200 (desligado 0,2335); tabulada a 45 % **0,0157** (desligado 0,2373; ciclo 3 0,6510), a 60 % 0,0140 |
| Bloqueante do ciclo 3: notas reais e fixture | `c3\b13_notas_reais.py 6` → `c4\notas_reais.out`; `c3\b13_fixture_notas_comuns.py` → `c4\fixture_notas_comuns.out` | sim | 0 de 6 páginas embaralhadas em cada um dos cinco livros (Kmoch: 2 de 6 no ciclo 3); a fixture: grupos `[]` (ciclo 3: `[[2, 1]]`, atravessava) |
| O que mandei manter | `b13_importador.py` Karpov 2 p. 268 → `c4\b13i_karpov268.json`; Gallagher pp. 50–53 → `c4\b13i_gallagher.json` + `gallagher_cer_c2.py`; `c2\b13_tabelas.py` → `c4\tabelas_c2.out`; `c3\b13_tabelas3.py` → `c4\tabelas3.out`; `c3\b13_lista_recusada.py` → `c4\lista_recusada.out` | sim | Karpov 2 p. 268: JSON **igual byte a byte** ao do ciclo 3; Gallagher p. 50 **0,2028** (WER 0,3121), as quatro páginas com o texto de cada região igual ao do ciclo 3; aberturas **0,0113**, classificação 0,0909, índice 0,1824, controle 0,5280; lista com avaliações separadas **0,0603** (ciclo 3: 0,6724); campeões «nome \| período» 0,5696 = desligado (dito no §0.3/§0.6) |
| A fila de A/B do ciclo 4 e o `sol.json` | `c4\conf_sol_c4.py` → `c4\conf_sol_c4.out` | sim | `f5c4_*`: `commit=7736617`, `dirty_code=[]`, `SOL_CONFIG` dos dois interruptores; **idênticas item a item** às `f5c3_*`, `f5c2_*` e `f5_*` em todo campo que não é tempo, e no texto (61/66/85 itens com texto nas três corridas, 0 diferem; o «70» do relatório é a `f5c4_on` com os 9 controles); `sol.json` do `7d41996` = `f5c4_on`, `commit=7736617`, sem `SOL_CONFIG`; `f5_ab.json` com as 11 corridas = os JSON, médias refeitas dos itens (maior diferença 0,000004); B13 muda os mesmos 7 itens, B14 os mesmos 27, nenhum para pior; aceitos errados 7 |
| Portões do Sol | `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` → `c4\sol_gate_c4.out` | sim | idêntico ao do construtor (`diff`): 150 DPI 0,0094 ✓; CER limpo 0,0113, lances 0,9164, 157 inventados ✗; nenhuma regressão |
| Os 34 testes do B13 e as sabotagens | `pytest tests\unit\ocr\test_table_rows.py` → `c4\test_table_rows.out`; `SABOTAGEM=… pytest -p sabota_rows_c4` → `c4\sabota_rows_c4.out` (e na árvore limpa → `c4\sabota_rows_c4_limpa.out`, igual) | em parte | 34 passam; sem o texto corrido 3 reprovam; continuação antiga 3; «de duas calhas, nenhuma» 1; avaliação como token 1; semente de prosa 1 (só o teste da própria `_seeds`, como o relatório diz). **A regra nova das três faixas em `crosses`** (faixas não vizinhas ou mais de duas → cruza) **não tem teste**: tirada, os 34 passam. Não bloqueante 3 |
| Testes tocados | suíte: `pytest tests\unit\ingest\test_table_rows_page.py …\test_table_rows.py tests\unit\ui\test_revisao_de_texto_view.py …\test_arquitetura.py …\test_fileira_fluida.py …\test_rotulo_que_encolhe.py tests\unit\ocr\test_ink_coverage.py tests\unit\classify\test_model_ruler.py tests\unit\ocr\test_sol_metrics.py` → `c4\suite_testes_tocados.out`; tronco (árvore `7cd400a`): `test_qt_janela_cabe.py test_qt_rodape.py test_strings.py "test_field_eval.py::ImpressaoDaMedicaoTests"` → `c4\tronco_testes_tocados.out` | sim | suíte **121 passaram** (o de ponta a ponta com o Tesseract em 20 s); tronco **89 passaram** (97 subtestes), árvore limpa depois |
| Texto corrido em parágrafos reais (sem OCR) | `c4\corrido_idiomas.py` → `c4\corrido_idiomas.out` (8 livros, 22/25/27 car. por linha, com e sem lances) | sim, com ressalva | a regra nova **ganha** prosa em toda língua e **perde** no máximo 5 blocos por faixa (a «palavra, não lance» quase não tira nada); mas fica fora de toda regra uma parte das notas com lances de 7+ linhas: alemão 20,9 %, holandês 11,3 %, inglês 10,4 % |
| Texto corrido em páginas reais na medida da Gallagher | `c4\b13_notas_medida.py 6 24 "de Gunderam" "de Euwe" "de Kemeri"` → `c4\notas_medida_de_w24.out` | sim | páginas sorteadas: **0 de 18** embaralhadas (ciclo 3: 7 de 18) |
| O caso ruim do texto corrido | triagem sem OCR `c4\risco_paginas.py {22,24,27}` → `c4\risco_paginas.out`, `c4\risco_dvoretsky.out`; as páginas em risco com OCR, `b13_notas_medida.py 30 24 --paginas-de=c4\risco_w24.json` → `c4\notas_risco_w24.out`; as inglesas pelo importador → `c4\cer_notas_en.out` | **não** | páginas cujas notas nenhuma regra segura: 0–9 % conforme o livro (Kemeri 7 % a 24 car.; Dvoretsky, notas limpas, só as do índice); dessas, o ciclo 4 embaralha **12 de 29**; pelo importador, Nunn p. 29 0,0824 → 0,6571, p. 143 0,1778 → 0,7276, Burgess p. 133 0,1016 → 0,6213, em **revisão**. Não bloqueante 1 |
| Ataques às regras novas nas fixtures dos testes | `c4\b13_fixtures_c4.py` → `c4\b13_fixtures_c4.out` | sim | notas cortadas em blocos de 2 ou 3 linhas: algum bloco sempre é prosa por palavras ou notas, a calha segura; a tabulação não vira calha da página (a prosa a cruza) |
| Páginas de três colunas e tabela ao lado da prosa | `c4\b13_tres_colunas.py` → `c4\tres_colunas.out`; `c4\b13_pdf_tres.py` + `b13_importador.py c4\tres.pdf 0,1,2,3` ×3 → `c4\cer_tres.out` | **não** | → **bloqueante novo 1** |
| Índices reais | `c4\indices_tres.py` → `c4\indices_tres.out` (camadas de texto: 46 PDFs); `c4\indices_reais.sh` → `c4\indices\*.out`; `c4\indices_raster.py` + importador ×3 → `c4\cer_indices.out`; Flores original ×3 → `c4\cer_flores.out` (verdade: `c4\verdade_colunas.py`), e uma vez na árvore limpa com `c4\b13_importador_arvore.py` → `c4\b13i_flores_limpa.json`, igual byte a byte | **não** | → **bloqueante novo 1** |
| Ordem do Tab da Revisão de texto, portão | `c4\teclado_c4.sh` (3 peles × 1280×800, 1248×640, 1280×641) → `c4\teclado\*.json` | sim | PASSOU nas 9; a ordem gravada é a tabela, leitura, alternativas, verdade, as 7 figurinas e as 6 ações, crescente nas três peles e nos três tamanhos |
| Ordem do Tab com a **tecla** | `c4\c18_tab_real.py` (código do ciclo 4 × `suite_c3`) → `c4\c18_tab_real_{c4,c3}.out`; `c4\c18_tab_areas.py` → `c4\c18_tab_areas_{c4,c3}.out` | **não** | → **bloqueante novo 2** |
| Foco à vista a 1280×641 | `c4\c18_foco_visivel.py` (Tab da tabela) e `c4\c18_foco_visivel_tras.py` (Shift+Tab de «Aceitar leitura») → `c4\c18_foco_visivel*_{foco,classica,fita}.out` | **não** | para a frente o Tab para na verdade (o cartão rola até ela: à vista); para trás, «Letras → figurinas» recebe o foco com **0×0 px** à vista nas três peles → **bloqueante novo 2** |
| O portão da janela, sete corridas, máquina ocupada | `c4\minimo_c4.sh` → `c4\minimo\*` | em parte | sem livro PASSOU; as cinco sabotagens REPROVARAM (`reserva`: dispositivos 0–22 e ocupação 0–58 px; `rodape` 3318 px; `mensagem` 0–142 px); **com o livro REPROVOU**: na Clássica a 1248×606, «[Dataset] RotuloElidido 'peças ainda …to desligado' 135/162 px» — o texto do próprio produto na zona de dispositivos, espremido, na passada da vista. Repetido três vezes com a máquina quieta (`c4\minimo_livro\livro_r{1,2,3}.log`): **PASSOU** as três, `linha_reposta` 0 em toda medida. Não bloqueante 2 |
| O «162/152» do arnês | `scratchpad\c4\probe_rodape_primeira2.out` do construtor | sim | depois da visita às áreas as zonas têm os textos do produto: «leitura do dataset (labels.csv)» (152 px) e «peças ainda não · texto desligado» (162 px); o arnês agora repõe a linha e grava `linha_reposta`/`linha_do_arnes` — mas só na medida do rodapé, não na da vista (acima) |
| O que o JSON do portão grava | os 7 JSON do commit (`docs\quality\ui\c2_fase5\minimo*_20260923_183*.json`) e os meus | sim | `suite`/`tronco` com o commit e o `fora_do_commit` do `src` (`[]` nos dois lados) |
| O custo da reserva e o nome com 95 px | `git show 7cd400a` (docstrings de `LARGURA_DA_MENSAGEM` e `LARGURA_DA_ZONA`); relatório §0.3 e §0.6 (b)(c) | sim | ~57 caracteres, a frase sem o `.pt` (84 car., 474 px) elidida em 46/46 de 1246 a 1440, o estado vazio do Resultado, a ocupação sem forma fixa, o nome a ~95 px — ditos nos três lugares |
| As ações do Resultado abaixo da dobra, as frases, o A15 | relatório §0 (linha 51), §0.3, §0.5 (linhas 329–351, 352–355, 365), §0.6, §A15 | sim | 320 e não 480; Levenfis p. 302 «três dos seis»; «em todo campo numérico… o texto só dos itens com CER > 0,05»; «~57»; as oito brechas ditas; as ações do Resultado a 1280×641 no §0.3 |
| A transcrição do meu ciclo 3 | `git show 7736617:docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` × `veredito_ciclo3.md` | sim | idêntica salvo o nível dos títulos; a nota das 13:53–13:54 está no cabeçalho da seção |
| As varreduras | `c4\varre_c4.sh` (Gallagher 14–186/4 e 187–189, Karpov 2 262–272, Levenfis 296–305, Stean 154–165, Estrin 0–87 em `deu+eng`) → `c4\varre\*`; `c4\cmp_varre_c4.py` → `c4\cmp_varre_c4.out`; a Levenfis e a Stean de novo na árvore limpa → `c4\varre_limpa\*` | sim, com ressalva | **168 páginas**: a leitura ligada do ciclo 4 é a do meu ciclo 3 em todas, e a desligada também (determinismo); B13 muda 25; iguais às do construtor, salvo a leitura **desligada** da Stean p. 165, que na corrida dele (máquina sem memória) saiu muito pior — não bloqueante 4. A Levenfis e a Stean refeitas na árvore limpa (`c4\b13_varredura_arvore.py` → `c4\varre_limpa\*`) dão as mesmas 22 páginas. A Gunderam e a Kmoch não refiz. E nas 280 do relatório estão as pp. 460–464 da Flores (bloqueante 1), mudadas igual nos ciclos 2, 3 e 4 |
| Tronco inteiro | `c4\testes_full_c4.sh so_tronco` (árvore `7cd400a`) → `c4\trunk_full_c4.out` | sim | **4.789 passaram, 16 pulados, 8 xfail, 1 reprovado** em 380 s — o `test_environment::…resolve_para_esta_arvore`, por construção da árvore efêmera (o mesmo do construtor e dos meus ciclos 2 e 3); árvore limpa antes e depois |
| Suíte inteira | `c4\suite_full_c4.sh` (na minha árvore limpa do `7d41996`, porque o checkout principal passou a ter o `rows.py` do ciclo 5 do construtor; o tronco da minha árvore) → `c4\suite_full_c4.out`; os que falharam, de novo com os artefatos de fora do git copiados para a árvore (`models\tessdata` sem a pasta `work`, `benchmarks\reports\blind3` e `proofsheet*`) → `c4\suite_refeitos.out`, `c4\suite_proofsheet2.out`, `c4\suite_gpu.out` | sim | **4.006 passaram, 29 pulados, 1 reprovado, 5 erros** em 794 s, com o `test_arquitetura`; os seis são da árvore e do meu ambiente: `test_corpus::test_nunn_ocr_layer…` (sem a `models\tessdata` as figurinas não se leem) e os quatro do `test_proofsheet` (PDFs e PNGs de `benchmarks\reports`) **passam** com os artefatos; o `test_gpu_parity::test_cuda_actually_computes` erra na montagem pela minha `CAISSA_CVOFF_ROOT` (o mesmo dos ciclos 1–3) e, sem ela, pula (sem CUDA). 4.006 + 29 + 1 + 5 = 4.041 = 4.032 + 9 do construtor; os 20 pulados a mais pedem o acervo de PDFs, o EPUBCheck e outros artefatos fora do git |

### O bloqueante do ciclo 3

**Resolvido nas páginas dadas.** O `construido.pdf` pp. 0–3 pelo importador de produção sai idêntico ao desligado nas
três execuções (p. 0: 0,0052 `accepted`, a página certa; os JSON iguais byte a byte); pelo serviço, o inglês e o
alemão justificados iguais ao desligado a 300 DPI e o alemão a 200 DPI melhor que ele (0,2335 → 0,0152); a lista
tabulada a 45 % 0,2373 → 0,0157; as notas reais de cinco livros 0 de 6; a fixture sem grupo. O que mandei manter está
mantido, byte a byte onde havia JSON. O texto corrido (`_running`) ganha prosa em toda língua sem perder quase nada
(`corrido_idiomas.out`), e 18 páginas alemãs sorteadas na medida da Gallagher saem certas (o ciclo 3 embaralhava 7).
**A classe fica aberta numa franja** (não bloqueante 1): notas que nenhuma regra chama de prosa — linhas que abrem
com lance ou com substantivo maiúsculo, menos de 1/3 de continuação, menos da metade com número de lance dentro —
ainda se juntam à lista ao lado; 12 de 29 páginas em risco embaralham, e pelo importador três páginas inglesas reais
(com as figurinas como o OCR as lê), em revisão, não aceitas.

### Defeitos bloqueantes (novos)

1. **O B13 intercala as colunas de um índice quando a página tem duas calhas ou mais — páginas reais do acervo, e o
   importador aceita a construída.** É a classe do bloqueante 1 do ciclo 2 (o índice da Karpov 2 intercalado),
   em três colunas ou em duas colunas de «nome … páginas».
   - **Onde:** `src/caissa/ocr/layout/rows.py`, `_page_gutters` (linhas 326–341: de duas calhas ou mais, a da página
     é só «a vizinha de um bloco de prosa»; sem prosa, `page` fica vazio e **nenhuma** calha vale), `table_groups`
     (`band` = 0 para todos; `crosses` nunca dispara) e `beside` (o corredor só vale com ≥ 8 linhas de prosa de ≥ 30
     caracteres, que um índice não tem). O §0 do relatório diz «através da calha da página (…, de duas calhas, a
     vizinha da prosa) só uma lista de lances passa» — numa página de duas calhas sem prosa não há calha da página, e
     tudo passa.
   - **O quê, com números** (importador de produção, três execuções com os JSON iguais byte a byte; CER contra a
     ordem do livro, coluna por coluna):
     - **Flores, *Chess Structures* (Quality Chess), pp. 460–464 — o índice de nomes, páginas raster do acervo**, que
       estão nas 280 páginas das varreduras desde o ciclo 2 (as mesmas similaridades 0,22–0,39 nas minhas dos ciclos
       2 e 3 e na do construtor; eu também não as julguei): duas colunas de página, cada uma «nome … páginas»; o B13
       as junta linha a linha — «David 412 Galkin 198 / Delchev 108, 198 Gao 365 / …». p. 462 **0,0230 → 0,7217**
       (revisão); p. 464 0,4949 → 0,6869; pp. 460, 461 e 463 com CER 0,61–0,72 nos dois lados e a **p. 461 e a
       p. 463 `accepted` nos dois** (a desligada também troca a ordem: todos os nomes, depois todos os números) —
       `c4\cer_flores.out`, verdade por coluna com `c4\verdade_colunas.py` conferida contra a imagem
       (`c4\indices\flores_p461.png`);
     - **Yusupov 4, *Fundamentos* (La Casa del Ajedrez), p. 206 («Índice de partidas», três colunas)**, a página do
       livro digitalizado copiada sem a camada de texto (a situação da Karpov 2): **0,0465 → 0,7915** (revisão) —
       «Potkin Vachier-Lagrave 169 Rublevsky 166 / Carlsen 112 Savchenko Smirnov / …» (`c4\cer_indices.out`,
       imagem `c4\indices\yusupov4_p206.png`);
     - **Nunn, *Minor Piece Endings*, p. 288**, igualmente como digitalizada: 0,3212 → **0,7395** («Polak P251
       Sackmann P60, 113»); na p. 289 o B13 acerta (0,3027 → 0,0174) — ele junta nome e páginas da mesma coluna e,
       conforme as alturas, a coluna vizinha também: a mesma página tipográfica sai certa ou trocada;
     - **páginas construídas** (`c4\tres.pdf`, Times 9 pt): índice de 108 verbetes em três colunas a 300 DPI
       **0,0007 → 0,7791, `accepted` nos dois lados**; 36 verbetes 0,0000 → 0,7429 `accepted`; a 150 DPI desfocado
       0,0058 → 0,7783 `accepted`; **«índice | índice | prosa» 0,0000 → 0,3575 `accepted`** — a prosa da terceira
       coluna escolhe só a calha vizinha dela, e as duas colunas de índice se juntam (`c4\cer_tres.out`).
     A regra do ciclo 3 dá os mesmos números (`c4\tres_colunas.out`: ciclo 3 = ciclo 4 em toda página): o defeito vem
     de antes, e a regra nova das duas calhas, feita para a Gallagher p. 50, não o alcança.
   - **Como reproduzir:** `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c4\b13_pdf_tres.py C:\Python-Chess2\_critico_f5\c4\tres.pdf`,
     depois, sem `CAISSA_FIGURINE_TESSDATA`, `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\b13_importador.py C:\Python-Chess2\_critico_f5\c4\tres.pdf 0,1,2,3 <saida.json>`
     e `c4\cer_pdf.py <saida.json> c4\tres.pdf`; para a Flores, `b13_importador.py "<PDF>\Mauricio Flores Rios - Chess Structures - A Grandmaster Guide[Quality Chess, 2015].pdf" 460,461,462,463,464 <saida.json>`
     (as verdades em `c4\flores\flores_p46{0..4}_verdade.txt`); para a Yusupov e a Nunn, `c4\indices_raster.py c4\indices_raster.pdf`
     e o importador nas pp. 0–4.
   - **Por que reprova:** é a classe que reprovou o ciclo 2, numa página **real do acervo que o importador lê por
     OCR** (a Flores, raster) e que já estava nas varreduras que o relatório cita como evidência («43 mudam, a leitura
     ligada igual à do ciclo 3») sem que alguém dissesse se as mudanças eram para melhor; a Carta §3.3 reprova sozinhas
     a falha silenciosa e a «confiança alta em resultado errado» — a página construída sai **aceita** trocada, e na
     Flores a p. 461 e a p. 463 saem **aceitas** com CER ~0,7. Um editor que importa um livro digitalizado recebe o
     índice de nomes trocado linha a linha, e parte dele aceito.

2. **A ordem do Tab «de volta à visual» só existe na cadeia do foco: com a tecla, o Tab para no campo da verdade
   antes das ações, e o caminho de volta das ações cai num botão invisível.** É o conserto deste ciclo (o meu não
   bloqueante 3 do ciclo 3), medido com a tecla.
   - **Onde:** `src/caissa/ui/views/revisao_de_texto.py` linhas 355–360 (a cadeia `[self.table, *_focaveis(self.cartao),
     *self.acoes.values(), *paginador]`) sobre o `CartaoDaLinha` (`ui/widgets/cartao_da_linha.py`), cujo campo
     «Verdade da linha» é um `QPlainTextEdit` com `tabChangesFocus() = False` e cujo `eventFilter` (linhas 221–247)
     trata Enter, Ctrl+Enter, Ctrl+R, Ctrl+↑/↓, Alt+1/2 e Alt+letra, não o Tab; o cartão rola dentro de um
     `QScrollArea`.
   - **O quê, com números** (a janela montada como o arnês, Kemeri aberto, Tab e Shift+Tab por `QTest.keyClick` no
     controle focado):
     - **para a frente, da tabela** (`c4\c18_tab_real_c4.out`, 1280×800, Foco): tabela → leitura → alternativas →
       verdade → **parado** — três Tabs deixam `'\t\t\t'` no texto da verdade; as 7 figurinas e as 6 ações não se
       alcançam. No ciclo 3 (`c4\c18_tab_real_c3.out`, a `suite_c3`): tabela → as **seis ações** → leitura →
       alternativas → verdade → parado. O Ctrl+Tab no campo troca de **área** (vai a «Negrito», na aba Texto); só o
       Shift+Tab ou os atalhos saem dele. Contando a área inteira (`c4\c18_tab_areas_{c4,c3}.out`), a Revisão de texto
       cai de **20 para 14** controles alcançados pela tecla;
     - **para trás, das ações, a 1280×641** (o portátil-alvo maximizado; `c4\c18_foco_visivel_tras_{foco,classica,fita}.out`):
       Shift+Tab em «Aceitar leitura» põe o foco em «Letras → figurinas», abaixo da dobra do cartão, com **0×0 px à
       vista** nas três peles — a rolagem não desce, porque o foco entra nela vindo de fora; só o Shift+Tab seguinte a
       faz rolar. No ciclo 3 o mesmo Shift+Tab voltava à tabela, à vista;
     - o portão do teclado anda por `focusNextPrevChild` e o teste novo por `nextInFocusChain`: nenhum dos dois passa
       pelo editor nem olha se o controle focado aparece, e os dois dizem «50/50» e «a tabela, o cartão, as ações»
       (`c4\teclado\*.json`: PASSOU nas três peles e nos três tamanhos). A tecla também empaca no Estudo («Comentário
       do lance»), no Texto («Folha transcrita») e na Rotulagem («Verdade da linha»), iguais no ciclo 3.
   - **Como reproduzir:** sem a variável, `QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=<suite>\src;<tronco>\src;.venv-pack\Lib\site-packages`:
     `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c4\c18_tab_real.py <suite>\src <tronco> foco "<PDF>\1937 Kemeri.pdf"`
     e `…\c4\c18_foco_visivel_tras.py <suite>\src <tronco> <pele> "<PDF>\1937 Kemeri.pdf" 1280x641`.
   - **Por que reprova:** a Carta §3.3 põe «estado de foco ausente ou invisível» entre os defeitos que reprovam
     sozinhos; e o conserto deste ciclo, que o relatório dá por feito («teclado PASSOU, e a ordem do Tab da Revisão de
     texto segue a visual», §0; §0.6 (a); §C18), tirou das seis ações o alcance pelo Tab que elas tinham no ciclo 3 —
     quem revisa pelo teclado aperta Tab para chegar a «Aceitar leitura» e escreve tabulações na verdade da linha. O
     `setTabOrder` foi pedido meu no ciclo 3, e o pedido estava incompleto (eu também medi só a cadeia); o que se julga
     é o teclado que o produto entrega.

### Defeitos não bloqueantes

1. **O texto corrido deixa uma franja de notas reais fora de toda regra.** 0–9 % das páginas, conforme o livro, têm
   notas que nenhuma regra chama de prosa (`c4\risco_paginas.out`); com OCR, o ciclo 4 embaralha 12 das 29
   (`c4\notas_risco_w24.out`; o ciclo 3, 16) — entre elas páginas alemãs cujo «texto» é tabela de resultados ou ruído
   da camada de texto (Kemeri pp. 62 e 75); as inglesas são notas de verdade. Pelo importador, Nunn p. 29
   0,0824 → 0,6571, p. 143 0,1778 → 0,7276, Burgess p. 133 0,1016 → 0,6213 (`c4\cer_notas_en.out`), em revisão. São
   notas de análise densa, com as figurinas como o OCR as lê: linhas que abrem com lance, número ou maiúscula (o bloco
   de 18 linhas da Nunn p. 29 tem continuação 0,29, abaixo do 1/3). O §0 diz «nunca juntando texto corrido (… linhas
   que continuam a frase, poucas palavras que tenham)» — a regra exige um terço de linhas que continuam, e estas não
   têm.
2. **O arnês espera a linha assentar no rodapé, mas não na passada da vista.** Com a máquina ocupada, uma das quatro
   corridas com o livro REPROVOU com a zona de dispositivos espremida no texto do próprio produto («peças ainda
   …to desligado», 135 de 162 px; `c4\minimo\livro.log`); com a máquina quieta, três PASSARAM. O veredito do portão
   depende da carga — o mesmo defeito do «162/152», noutro ponto do arnês.
3. **A regra de três faixas em `crosses` não tem teste** (`c4\sabota_rows_c4.out`, `SABOTAGEM=cruza_tres`: 34 passam).
4. **Degradação sem aviso sob falta de memória, vista pelo construtor e despachada.** A leitura **desligada** da Stean
   p. 165 da varredura dele (máquina sem memória) é muito pior que a minha e que a do ciclo 3 (`c4\cmp_varre_c4.out`:
   «$9.95 IN USA» → «£7-75 IN USA», «ISBN-10:0-486-42420-0» → «ISEN-10-486-42420-0», uma linha de lixo no fim); o §0.2
   e o §0.6 a registram como «outra variante escolhida, com a máquina sem memória» e seguem. Uma leitura que muda com a
   memória livre é «resultado não reproduzível» e «degradação não sinalizada» (Carta §3.3); não medi a decisão dela.
5. **As recusas estão ditas, e é o que pedi**: a tabela «nome \| período» 0,5696 e «vitória das brancas» 0,5000,
   iguais ao desligado. Fica a observação: as duas voltam ao desligado, e o desligado lê errado.
6. **Ficam, ditos pelo construtor:** as oito brechas do A15, a Estrin pp. 29/77 fora do grupo, o custo da reserva de
   320 px e o nome a ~95 px, as ações do Resultado abaixo da dobra a 1280×641, o portão só `offscreen`.

### O que falta

- A janela na plataforma real (`windows`): tudo `offscreen`, com a fonte do produto imposta.
- O `bench_sol` inteiro (o briefing proíbe): a fila foi conferida item a item dos JSON.
- As varreduras da Gunderam e da Kmoch (o construtor as refez; eu refiz 168 das páginas dele).
- A suíte inteira no checkout principal: rodou na minha árvore limpa, sem os artefatos de fora do git (os 20
  pulados a mais); os que dependiam deles rodei de novo com eles.
- O foco invisível ao entrar no cartão pelo Shift+Tab foi medido na Revisão de texto; a Rotulagem, que usa o mesmo
  cartão, não medi.
- A comparação às cegas da Carta não se aplica a esta frente.

### O que especificamente precisa mudar para eu aprovar (se REPROVADO)

1. **B13 — nenhum índice intercalado, com duas calhas ou mais.** Colunas da mesma forma lado a lado (nome e páginas,
   jogador e adversários) são listas separadas também quando o `find_gutters` acha duas ou mais calhas, com ou sem
   prosa: a calha da página tem de ser achada sem prosa (as faixas de largura comparável, como a regra de uma calha
   já faz) ou o cruzamento de **qualquer** calha tem de pedir a evidência positiva que hoje só a calha «da página»
   pede. Travar por teste, com a sabotagem, a Flores pp. 460–464 (raster, do acervo), a Yusupov 4 p. 206 e a Nunn
   p. 288 como digitalizadas, e o `c4\tres.pdf` (três colunas a 300 e a 150 DPI, e «índice | índice | prosa»),
   mantendo o `table:2/4/7` a 150 DPI, a Karpov 2 p. 268, a Gallagher p. 50 em 0,2028, as minhas páginas do ciclo 3, as
   aberturas em 0,0113 e o que o B13 acerta hoje (Nunn p. 289 0,0174, Aagaard *Matter* p. 893 0,0769). E julgar as
   páginas que mudam nas varreduras (melhor ou pior contra a ordem do livro), não só contar que mudam; corrigir o §0.
2. **O teclado da Revisão de texto com a tecla, não com a cadeia.** O campo da verdade do cartão (na Revisão de texto
   e na Rotulagem) deixando o Tab sair (`setTabChangesFocus(True)`, ou outra saída pelo Tab que não escreva na
   verdade); o controle do cartão que recebe o foco rolado para a vista também quando o foco entra vindo de fora da
   rolagem (o Shift+Tab das ações a 1280×641, nas três peles); um teste que aperte a **tecla** da tabela até a última
   ação e de volta, conferindo a ordem e que cada controle focado aparece, com a sabotagem ao lado; o portão do teclado
   dizendo onde a tecla empaca (as quatro áreas de hoje) e se o focado está à vista; corrigir o §0, o §0.6 (a) e o §C18.
3. **No mesmo ciclo:** (a) dizer no §0.3 a franja do texto corrido com os números (0–9 % das páginas em risco, 12 de
   29 embaralhadas, as três inglesas pelo importador); (b) a passada da vista do arnês esperando a linha como a do
   rodapé; (c) um teste para as três faixas de `crosses`; (d) a Stean p. 165 tratada como o que é — a leitura que
   piora sem aviso quando falta memória: medir a decisão dela e dizer o mecanismo.

## Crítico Claude — ciclo 5 (REPROVADO, 2 bloqueantes)

VEREDITO: REPROVADO
CICLO: 5
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts e as saídas deste ciclo estão em `C:\Python-Chess2\_critico_f5\c5\` (a saída de
cada um ao lado, `*.out`/`*.json`/`*.log`; as filas em `*.sh`, com `runs.log`); as cópias das minhas sondas dos
ciclos 2–4 apontadas para a árvore limpa estão em `c5\lib\` (`c5\lib\copia.py` diz o que troca). Todo o código
medido é o dos commits: a suíte numa árvore minha, `git worktree add --detach C:\Python-Chess2\_critico_f5\suite_c5 4e42158`
(o `src` do `4e42158` é o do `b6978ec`; `models\` copiada do checkout sem a pasta `work`, e para a suíte inteira os
artefatos de `benchmarks\reports` que o git não guarda), e o tronco noutra, `git worktree add --detach
C:\Python-Chess2\_critico_f5\tronco 7a78367` (sem o `.pt`, como todo clone; o classificador de diagramas do
importador vem do checkout do tronco, como nos ciclos anteriores). `git status` das duas árvores vazio do começo ao
fim (`c5\estado_inicio.txt`, os `runs.log`). O checkout principal da suíte estava no `4e42158` com o `src` igual ao
commit (`c5\estado_inicio.txt`); não o usei para medir. As varreduras do construtor (`scratchpad\c5\varre\`) eu não
refiz: conferi que o código delas é o do commit (`codigo_fim.diff` nos arquivos de OCR igual a
`git diff 7d41996 b6978ec -- src`) e julguei as páginas delas. Sondas do corpus e de páginas renderizadas com
`CAISSA_FIGURINE_TESSDATA=models\tessdata`; importador, janela e testes sem ela. No máximo quatro processos de OCR ao
mesmo tempo, com a memória virtual livre gravada a cada 3 s (`c5\memoria.log`, `c5\monitor_mem.ps1`); nenhuma
sonda registrou falha de motor (`grep "falhou\|bad alloc" c5\sondas\*.out` vazio). Nenhum arquivo dos dois
repositórios foi editado; as duas árvores foram removidas no fim (21:47, `git worktree remove`), e os checkouts
principais estão como no começo — suíte no `4e42158`, tronco no `7a78367`, os mesmos arquivos de outras sessões
modificados (`c5\estado_fim.txt`). Dois processos meus (a sonda `linha_antiga.py` do construtor, rodada como script:
o filho `spawn` do processo de trabalho não sobe e `encerrar(esperar=True)` fica parado a 0 % de CPU depois de gravar
o JSON) eu encerrei; nenhum processo meu ficou vivo (o PID 1996 é de antes).

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| Bloqueante 1: a Flores pp. 460–464 pelo importador, 3 execuções | `c5\sondas_c5.sh` (`c4\b13_importador_arvore.py`, `SUITE_REPO` = a árvore) → `c5\sondas\b13i_flores_r{1,2,3}.json`; `scratchpad\c5\cer_flores.py` e `descidas.py` → `c5\cer_flores.out` | sim | desligado 0,6708/0,7224/0,0230/0,7117/0,4949 → ligado **0,0438/0,0853/0,0230/0,0202/0,0364**, as três execuções iguais byte a byte (`cmp`); pp. 461 e 463 `accepted`. A p. 461 ainda tira do lugar as páginas de três verbetes (não bloqueante 1) |
| Bloqueante 1: `c4\tres.pdf` e `c4\indices_raster.pdf`, 3 execuções | idem → `c5\sondas\b13i_{tres,indices}_r{1,2,3}.json`; `c5\lib\cer_pdf.py` → `c5\cer_sondas.out` | sim | `tres.pdf` = desligado nas quatro (0,0007 / 0,0000 / 0,0000 «índice \| índice \| prosa» / 0,0058 a 150 DPI, `accepted`); Yusupov 4 p. 206 0,0465 = desligado; Nunn p. 288 0,3212 → **0,0193**; p. 289 0,3027 → 0,0174; Aagaard *Matter* p. 892 0,6896 → 0,0958, p. 893 0,3901 → **0,0769** (`accepted`); JSON iguais byte a byte |
| O que mandei manter | mesma fila → `c5\sondas\b13i_{construido,karpov268,gallagher,notas_en}.json`; `gallagher_cer_c2.py` → `c5\gallagher_cer.out`; `c5\lib\b13_{estreita3,tabulada,lista_recusada,tabelas3,tabelas}.py` → `c5\sondas\*.out` | sim | `construido.pdf` = desligado (0,0052 `accepted`, 0,2284, 0,0367, 0,0754); Karpov 2 p. 268 **igual byte a byte** ao meu ciclo 4; Gallagher p. 50 **0,2028** (WER 0,3121), pp. 50–53 com o texto de cada região igual ao ciclo 4; aberturas 0,0113, classificação 0,0909, índice 0,1824, controle 0,5280; estreitas, tabulada, lista recusada e tabelas do ciclo 3 com as linhas de CER iguais às do ciclo 4 (`md5` das linhas; na `tabelas3` só as calhas diagnósticas de uma variante mudam 2–5 px) |
| A fila de A/B e o `sol.json` | `c5\conf_sol_c5.py` → `c5\conf_sol_c5.out`; comparação de todo campo por item → `c5\conf_sol_c5b.out` | sim | `f5c5_*`: `commit=b6978ec`, `dirty_code=[]`; × `f5c4_*` nos 738 itens: só a `confidence` de `real:Dvoretsky…:17:401:52@native` difere (0,56 → 0,4884), em `f5c5_on` e `f5c5_b14_off`; o texto (61/66/85 itens com texto) igual; `sol.json` = `f5c5_on` em todo campo; `f5_ab.json` com as 14 corridas = os JSON; B13 muda os mesmos 7 itens, B14 os mesmos 27, nenhum para pior; aceitos com CER > 0,10: 7; `table:2/4/7` 0,0035/0,00364/0 |
| Portões do Sol | `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json` (na árvore) → `c5\sol_gate_c5.out` | sim | idêntico ao do construtor (`diff`): 150 DPI 0,0094 ✓; limpo 0,0113, lances 0,9164, 157 inventados ✗ |
| As sabotagens das regras novas contra os testes | `c5\sabota_c5.py` (plugin do pytest) → `c5\sabota_c5.out` | sim | sem sabotagem 93 passam; `sem_indice` 3 reprovam; `sem_partida` 2; `sem_contiguo` 1 e `tres_cruzam` 1 (o teste das três faixas); `ordem_nas_linhas` 2; `sem_marca_de_falha` 1; `sem_nota_de_falha` 1. E `indice_sem_ordem` (toda coluna de 6 cabeças é índice, em ordem ou não) só derruba 1 — o dos subverbetes: nenhum teste depende da ordem alfabética |
| Ataques ao `index_column` | `c5\b13_indices_ataque.py` → `c5\ataque\indices_ataque.out` (serviço) e o importador ×3 → `c5\ataque\b13i_ataque_r{1,2,3}.json`, `c5\ataque\cer_ataque.out` | **não** | → **bloqueante novo 1** |
| Uma lista real sem ordem alfabética | Neumann 1870 pp. 6–7 («Liste des Souscripteurs», nome \| exemplares, em duas metades), rasterizada (`c5\neumann_raster.pdf`), importador ×3 → `c5\b13i_neumann_r{1,2,3}.out` | sim | ligado = desligado, 0 grupos (os nomes longos não são células) |
| Uma partida ao lado de uma tabela | `c5\b13_partida_tabela.py` → `c5\partida_tabela.out` | **não** | → bloqueante novo 1 (c) |
| Uma tabela legítima com a primeira coluna em ordem alfabética | `c5\b13_tabela_em_ordem.py` → `c5\b13_tabela_em_ordem.out` (torneio «Nome \| País \| Rating \| Pontos», 12 jogadores, pelo serviço) | em parte | os nomes em ordem e os países fora dela: 0,7448 → **0,1207** (uma coluna de índice só, a tabela por linhas); os países **também** em ordem, por acaso: 0,7509 → **0,6367** — a calha entre as duas colunas vira da página e os nomes saem sozinhos (não bloqueante 11) |
| A franja do texto corrido, e com a partida em outras posições | `c5\lib\b13_notas_medida.py 100 24 --paginas-de=c4\risco_w24.json` → `c5\sondas\notas_risco_w24.out`; `c5\b13_franja_espelho.py 100` → `c5\franja_espelho.out` | sim | notas \| partida: **0 de 41** (ciclo 4: **23**, e não 24 — a saída do próprio construtor soma 23 e é igual à minha linha a linha); partida \| notas 0/41 (ciclo 4: 20); partida tabulada \| notas 0/41 (12); notas \| partida tabulada **1/41** (4): Dvoretsky p. 789, 0,5052 → 0,6522, igual ao ciclo 4. As três inglesas pelo importador = desligado (0,0824, 0,1778, 0,1016) |
| As varreduras julgadas | código das varreduras do construtor = commit (conferido); `c5\b13_muda.py` → `c5\b13_muda\*.txt` (65 páginas em que o B13 muda a leitura); `c5\b13_muda_triagem.py` → `c5\b13_muda_triagem.out`, e os diffs lidos | em parte | o construtor julgou as 6 que mudaram **entre ciclos** (Flores ×5 e Gallagher p. 128: confere) e as 4 dos índices reais; as 65 em que o B13 muda o desligado não foram julgadas. Julguei: 41 só reordenam ruído de diagrama; das 24 com texto, melhores as listas de lances por linha (Gallagher pp. 33, 124), sumários (Stefaniu p. 243, Levenfis p. 302, Reinfeld 1977 p. 319 — com dois títulos numa linha e «rayos la primera», «de Dama» vindos de outras linhas), Gunderam p. 20 e os índices; mistas ou piores a Gallagher pp. 41 e 175, a Aagaard (*Excelling*) p. 191, a Estrin p. 29 e a Gunderam p. 46 — as classes do §0.3. Não bloqueante 2 |
| A concordância na ordem do motor | `c5\conf_sol_c5b.out`; `scratchpad\c5\cmp_varre_simetrica.out`; os índices reais das varreduras contra as minhas verdades, `c5\indices_varredura_cer.py` → `c5\indices_varredura_cer.out`; a Nunn p. 288 pelo importador com o B14 ligado e desligado, `c5\nunn288_caminhos.py` → `c5\nunn288_caminhos.out` | em parte | só age onde o B13 reordena; no corpus muda só uma confiança. Nas varreduras, Yusupov p. 206 0,7908 → 0,0458 (melhor), Aagaard p. 893 0,0769 → 0,0761, Nunn p. 289 igual; mas a **Nunn p. 288 sai 0,7516 ligado e desligado** (ciclo 4: 0,7402), a leitura intercalada do RapidOCR, 30 descidas em 73 verbetes — o §0.7 a julga «para melhor». Pelo importador, digitalizada, 0,0193 com o B14 ligado ou desligado. A medida nos dois sentidos, do construtor, põe o RapidOCR intercalado em mais 5 páginas reais (não bloqueante 3) |
| A Stean p. 165 | `scratchpad\c5\stean165_varredura.py` (cópia na árvore: `c5\lib\`) → `c5\stean165_varredura.out`; `c5\falha_motor_importador.py` → `c5\falha_motor_importador.out` | sim, com ressalva | normal: RapidOCR, revisão 0,8472, «$9.95 IN USA»; RapidOCR levantando `RuntimeError("bad allocation")`: Tesseract, revisão 0,6891, 0,9894 de semelhança com a degradada do ciclo 4, e a nota «região 0: o motor rapidocr falhou…» na página; `MemoryError`: a página não sai. Pelo importador: a nota fica no traço (`ocr_trace.json`); o item de revisão diz só «Escore 0.749 abaixo do limite…»; com `MemoryError`, «OCR falhou na página 165: bad allocation» nas notas do relatório e **nenhum** item de revisão (não bloqueante 4) |
| O portão da janela e a sabotagem `linha` | `c5\minimo_c5.sh` → `c5\minimo\*` | sim | sem livro e com o Kemeri PASSOU (1248×606 / 1248×640 / 1246×629; mensagem 320, documento 272–288, dispositivos 135, ocupação 171); `linha` REPROVOU (fora da linha do arnês nas 8 áreas e no rodapé, nas três peles); `reserva` REPROVOU (dispositivos e ocupação 0–58 px); a pergunta antiga reposta (`scratchpad\c5\linha_antiga.py antes`) passa a sabotagem (`a_vista=True`), a de agora não (`False`) |
| O teclado com a tecla, na ordem do portão | `c5\c18_tecla_vista.py` (três peles × 1280×641 e o mínimo de cada) → `c5\tecla\*.out`; o próprio portão (Clássica, 1280×641) → `c5\teclado_portao\classica_1280x641.log` | sim | toda área anda nos dois sentidos, menos o Texto («Folha transcrita» empaca no Tab, escreve); nenhum foco com 0 px; o portão: 7 áreas PASSOU, o Texto REPROVOU |
| O teclado com a tecla, com as rolagens no topo | `c5\c18_tecla_vista2.py` → `c5\tecla2\*.out`; `c5\foco_fora_da_vista.py` → `c5\foco_fora_da_vista.out` e as capturas `c5\foco_fora\*.png`; `c5\portao_cego_rolagem.py` → `c5\portao_cego_rolagem.out` | **não** | → **bloqueante novo 2** |
| A Rotulagem com uma página reconhecida | `c5\rotulagem_real_tab.py` (Gallagher p. 51 reconhecida pelo próprio painel, 66 linhas, 1280×641) → `c5\rotulagem_real_tab.out`; `c5\rotulagem_tabela_tab.py` → `c5\rotulagem_tabela_tab.out` e `…_conserto.out` | **não** | → **bloqueante novo 2** |
| As setas na tabela da Revisão de texto | `c5\setas_revisao.py` → `c5\setas_revisao.out` | não | o comentário novo diz «As setas andam pelas linhas»: a primeira ↓ vai à linha 1 e põe o foco na «Verdade da linha»; as seguintes ficam no campo (não bloqueante 5) |
| Estudo (tronco `37f662b`, `4f3e218`, `7a78367`) | `tests\test_qt_painel_de_estudo.py` na árvore do tronco → `c5\tronco_testes_tocados.out`; as voltas acima | sim | 33 passaram (4 subtestes); comentário, lista de lances e caixa de colar soltam a tecla nos dois sentidos, nas três peles |
| A transcrição do meu ciclo 4 | `git show 4e42158:docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` × `veredito_ciclo4.md` | sim | 199 linhas iguais (salvo o nível dos títulos) |
| Testes novos e tocados | `c5\testes_tocados.sh` → `c5\suite_testes_tocados.out`, `c5\tronco_testes_tocados.out` | sim | suíte **119 passaram** em 104 s (`test_table_rows`, `test_arbiter`, `test_ocr_service`, `test_table_rows_page`, `test_indices_do_acervo` com o acervo, `test_revisao_de_texto_view`, `test_rotulagem_view`, `test_teclado_tecla`); tronco 33 passaram |
| Tronco inteiro | `c5\testes_full_c5.sh` (árvore `7a78367`) → `c5\trunk_full_c5.out` | sim | **4.792 passaram, 16 pulados, 8 xfail, 1 reprovou** em 373 s — o `test_environment::…resolve_para_esta_arvore`, por construção da árvore efêmera (o mesmo do construtor e dos meus ciclos 2–4); árvore limpa antes e depois |
| Suíte inteira | `c5\testes_full_c5.sh` (árvore `4e42158`, o tronco da minha árvore, `models\` e os artefatos de `benchmarks\reports` copiados) → `c5\suite_full_c5.out` | sim | **4.031 passaram, 29 pulados, 0 reprovaram, 1 erro** em 783 s, com o `test_arquitetura`; o erro é o `test_gpu_parity::test_cuda_actually_computes` na montagem, pela minha `CAISSA_CVOFF_ROOT` (o mesmo dos ciclos 1–4; sem ela, pula: sem CUDA). 4.031 + 29 + 1 = 4.061 = a conta do construtor; não listei os motivos dos 20 pulados a mais (no ciclo 4 eram o acervo, o EPUBCheck e artefatos fora do git); `test_indices_do_acervo` rodou na corrida dos tocados (0 pulados) |

### Os bloqueantes do ciclo 4

**1. Índices intercalados — resolvido nas páginas que dei; não resolvido na classe que o item 1 pedia.** As páginas:
a Flores pp. 460–464 pelo importador, três execuções iguais byte a byte, 0,6708/0,7224/0,0230/0,7117/0,4949 →
0,0438/0,0853/0,0230/0,0202/0,0364 (`c5\cer_flores.out`); o `tres.pdf` igual ao desligado nas quatro páginas; a Nunn
p. 288 0,3212 → 0,0193 e a Yusupov p. 206 igual ao desligado (`c5\cer_sondas.out`); tudo o que mandei manter está
mantido (a Karpov 2 p. 268 byte a byte, a Gallagher p. 50 em 0,2028, as aberturas em 0,0113). A regra, porém, não é a
que o item 1 pedia («colunas da mesma forma lado a lado (nome e páginas, jogador e adversários) são listas separadas
também quando o `find_gutters` acha duas ou mais calhas, com ou sem prosa»): é «uma coluna cujas cabeças sobem em ordem
alfabética, com ao menos 6 cabeças». Uma lista fora da ordem, ou a coluna curta da última página, continua intercalada
— e aceita (bloqueante novo 1).

**2. O teclado com a tecla — resolvido no cartão da Revisão de texto; não resolvido na Rotulagem nem nas rolagens do
tronco, e o portão continua dizendo PASSOU onde a tecla falha.** O cartão: o Tab anda da tabela à última ação e de
volta, a verdade não guarda o Tab, o Shift+Tab das ações entra no cartão com o foco à vista, nas três peles a 1280×641
(`c5\tecla\*.out`, `c5\tecla2\*.out`), com o teste da tecla e as duas sabotagens. Mas: a Rotulagem no estado de
trabalho (uma página reconhecida) prende o Tab num laço e o Shift+Tab não alcança 13 controles; e o Shift+Tab que entra
nas rolagens do tronco põe o foco em controles com 0×0 px à vista a 1280×641 — no Resultado e na Galeria nas três
peles, no Estudo e na Revisão na Fita — a mesma
classe do meu ciclo 4 («o controle que recebe o foco rolado para a vista também quando o foco entra vindo de fora da
rolagem»); o portão não vê nenhum dos dois (bloqueante novo 2).

### Defeitos bloqueantes (novos)

1. **O B13 ainda intercala listas lado a lado que a regra nova não reconhece como índice — e o importador aceita.**
   - **Onde:** `src/caissa/ocr/layout/rows.py`, `_index_gutters`/`_index_column`/`_entry_words` (linhas 407–451): a calha
     antes de uma coluna só é da página se as cabeças dela sobem em ordem alfabética (80 % dos pares, metade subindo) e
     são ao menos `list_min_heads = 6`; fora disso vale a regra de antes (de duas calhas ou mais, só a vizinha da prosa),
     e sem prosa `crosses` nunca dispara.
   - **O quê, com números** (páginas compostas como um livro digitalizado, Times 9 pt a 300 DPI, lidas pelo **importador
     de produção**, três execuções iguais byte a byte; CER contra a ordem do livro; `c5\ataque\cer_ataque.out`):
     - **(a) «jogador / adversários» em três colunas, os jogadores pela classificação** (o formato da Yusupov p. 206, sem a
       ordem alfabética; `indices_ataque.pdf` p. 8): **0,0000 `accepted` → 0,6577 `accepted`** — «Carlsen Caruana 82
       Nepomniachtchi 127 / Caruana 40 Ding 85 Radjabov / …». O desligado lê certo; o B13 estraga e o importador aceita;
     - **(b) «nome | páginas» afastadas (o formato da Nunn p. 288) com a segunda coluna de 5 verbetes** — a última página de
       um índice (p. 4): 0,6634 → **0,3196 `accepted`**, «Aaron 249 Ivkov 268 / Acevedo 228 Johannessen 265 / …»; a mesma
       página com a segunda coluna cheia (p. 5) sai 0,0028: a regra vê a coluna de 28 cabeças e não a de 5;
     - **(c) uma partida ao lado de uma tabela** (a classificação do torneio, «Aljechin 7½», como num livro de torneio de
       duas colunas; `c5\partida_tabela.out`, pelo serviço): 0,2218 → **0,7564**, «1 e4 e5 Aljechin 7½ / 2 Nf3 Nc6 Keres
       7 / …», e 0,3185 → 0,7357 com a colocação, 0,3185 → 0,7452 com três colunas, em revisão, iguais no ciclo 4: a
       calha da partida só vale ao lado de «texto» (linhas mais longas que uma célula), e a primeira coluna de uma tabela
       são células.
     A sabotagem `indice_sem_ordem` (`c5\sabota_c5.out`: toda coluna de 6 cabeças é índice, em ordem ou não) só derruba
     o teste dos subverbetes — a ordem alfabética não é exigida por nenhum dos casos que os testes guardam.
   - **Como reproduzir:** na árvore da suíte, com `CAISSA_FIGURINE_TESSDATA=models\tessdata`,
     `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c5\b13_indices_ataque.py C:\Python-Chess2\_critico_f5\c5\ataque\indices_ataque.pdf`
     (grava o PDF, as verdades e a leitura do serviço); depois, **sem** a variável,
     `SUITE_REPO=<árvore> .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c4\b13_importador_arvore.py C:\Python-Chess2\_critico_f5\c5\ataque\indices_ataque.pdf 0,1,2,3,4,5,6,7,8 <saida.json>`
     e `c5\lib\cer_pdf.py <saida.json> c5\ataque\indices_ataque.pdf`; a partida e a tabela: `c5\b13_partida_tabela.py`.
   - **Por que reprova:** é a classe do bloqueante 1 dos ciclos 2 e 4 e o texto exato do item 1 que pedi («jogador e
     adversários», «com ou sem prosa»); o conserto trocou «colunas da mesma forma» por «colunas em ordem alfabética».
     Numa página que o desligado lê certo o B13 produz um texto trocado linha a linha e o importador o **aceita** — a
     Carta §3.3 reprova sozinha a confiança alta em resultado errado. As páginas são compostas, como o `tres.pdf` que o
     construtor aceitou como prova e consertou; a lista real sem ordem que achei no acervo (Neumann 1870, nomes longos)
     não forma grupo.

2. **O teclado com a tecla continua falhando onde o portão diz PASSOU: a Rotulagem com uma página prende o Tab, e o
   Shift+Tab põe o foco a 0 px em quatro áreas do tronco (duas delas nas três peles).**
   - **Onde:** (a) `src/caissa/ui/views/rotulagem.py:638` — a tabela «Linhas da página» (`QTableWidget(0, 5)`) com a
     navegação do Tab ligada (o padrão do `QTableView`; a Revisão de texto a desligou, linha 285, a Rotulagem não), e
     `_on_table_select` → `CartaoDaLinha.mostrar_verdade` (`cartao_da_linha.py:204–207`) põe o foco na verdade a cada
     troca de linha; (b) as rolagens do tronco que o Tab alcança de fora sem seguir o foco — `qt/painel_principal.py:116`
     (os modos da aba Livro: Resultado, Estudo, Revisão) e `qt/painel_da_galeria.py:277` —; o `RolagemSegueOFoco` está só
     na Revisão de texto e na Rotulagem, e o `HANDOFF.md` o dá como regra («o conteúdo de uma rolagem que o Tab alcança
     de fora usa `RolagemSegueOFoco`»); (c) `ui/audit/teclado.py`, `_medir_uma_tela` (linhas 1117–1124): a volta do
     Shift+Tab corre logo depois da do Tab, com as rolagens já descidas por ela; e a Rotulagem entra no portão com a
     tabela sem linha (o Kemeri aberto, página não reconhecida) e no teste com o projeto vazio.
   - **O quê, com números:**
     - **Rotulagem, Gallagher p. 51 reconhecida pelo próprio painel (66 linhas), 1280×641** (`c5\rotulagem_real_tab.out`):
       o instrumento do portão (`teclado._volta_da_tecla`) diz **`passou=False fecha=False`** no Tab — a tecla anda pelas
       células, e a cada troca de linha o foco volta à «Verdade da linha»: «… Próxima > Linhas da página ×5 > Verdade da
       linha > Figurina rei > …», e «Adicionar PDF…», «Salvar», «Exportar», «Reconhecer (F5)», a navegação e o zoom não
       voltam; no **Shift+Tab, 23 de 37 focáveis** (com a tabela vazia, 36), e nunca alcançados as seis figurinas,
       «Letras → figurinas», «Aceitar leitura», «Gravar edição», «Rejeitar (imagem)», «Desfazer decisão», «Anterior» e
       «Próxima». Com 12 linhas sintéticas o mesmo
       (`c5\rotulagem_tabela_tab.out`); com `setTabKeyNavigation(False)` posto em memória, 36 controles nos dois sentidos,
       `passou=True` (`…_conserto.out`). O teste novo (`test_the_key_walks_the_tab_both_ways_with_every_control_in_sight`)
       e o portão medem a aba **sem linha nenhuma**;
     - **o foco a 0×0 px, com as rolagens como o usuário as encontra** (`c5\tecla2\*.out`: cada volta começa com toda
       rolagem no topo): a 1280×641, o Shift+Tab põe o foco em «Esconder incerteza» (Resultado) com **0×0 px** nas três
       peles; «Copiar cabeçalhos para todos» (Galeria) 0×0 nas três; «Comentário do lance» (Estudo) 0×0 na Fita (6 de 84
       px na Foco); «Próximo pendente» (Revisão) 0×0 na Fita; e no mínimo da Fita (1246×629) os mesmos. Na Clássica bastam
       **duas teclas**: «Abrir PDF» → «Modo Texto» → «Esconder incerteza», o retângulo do foco abaixo do rodapé
       (`c5\foco_fora_da_vista.out`, captura `c5\foco_fora\classica_Resultado_shift_tab.png`; a da Galeria,
       `classica_Galeria_shift_tab.png`). O §0.7 (linha 703) diz das ações do Resultado abaixo da dobra: «a tecla chega a
       elas e as mostra»;
     - **o portão não vê:** rodado na minha árvore, Clássica 1280×641 (`c5\teclado_portao\classica_1280x641.log`),
       Resultado e Galeria **PASSOU**, «Shift+Tab fecha», sem foco fora da vista; e com o conserto do meu ciclo 4 desfeito no
       produto (`_segue_o_foco.desligar()` na Revisão de texto, 1000×420), `_medir_uma_tela` passa os dois sentidos, e a
       mesma volta do Shift+Tab com a rolagem no topo acha «Letras → figurinas» fora da vista
       (`c5\portao_cego_rolagem.out`) — o portão não reprova o defeito que o bloqueante 2 do ciclo 4 descreveu.
   - **Como reproduzir:** sem a variável, `QT_QPA_PLATFORM=offscreen`,
     `PYTHONPATH=<suíte>\src;<tronco>\src;<checkout>\.venv-pack\Lib\site-packages`:
     `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c5\foco_fora_da_vista.py <suíte>\src <tronco> classica "<PDF>\1937 Kemeri.pdf" <pasta>`;
     `…\c5\rotulagem_real_tab.py <suíte>\src <tronco> "<PDF>\GALLAGHER - Winning With the King's Gambit.pdf" 51 eng 1280 641`;
     `…\c5\portao_cego_rolagem.py <suíte>\src <tronco>`.
   - **Por que reprova:** «estado de foco ausente ou invisível» reprova sozinho (Carta §3.3), e um teclado que prende
     quem trabalha na Rotulagem (a aba onde se rotula linha a linha pelo teclado: Enter, Ctrl+Enter, Alt+letra) é o
     defeito do bloqueante 2 do ciclo 4. O §0 (linha 59), o §0.7 item 2 e o §C18 dizem «na Revisão de texto e na
     Rotulagem o Tab anda da tabela à última ação e de volta, cada controle à vista» e «PASSOU … com o foco à vista nos
     dois sentidos»; o portão que sustenta a frase mede a Rotulagem vazia e o Shift+Tab com as rolagens já descidas.

### Defeitos não bloqueantes

1. **A Flores p. 461 sai `accepted` com páginas fora do lugar**: as linhas «255, 300, 304, 329, 334,» e «412, 428, 434,
   444, 454» (continuação de «Flores Rios») e as páginas de «Fressinet» («17, 361») e «Friedgood» («4») saem sete linhas
   abaixo, depois do cabeçalho «Name Index»; os dois nomes ficam sem páginas (CER 0,0853; diff contra a minha verdade;
   imagem `c5\flores_p461_110.png`). O relatório diz «as pp. 461 e 463 continuam `accepted`, agora na ordem do livro».
2. **As páginas que o B13 muda não foram julgadas**, como o item 1 do ciclo 4 pedia («não só contar que mudam»): o §0.7
   julga as 6 que mudaram entre ciclos e as 4 dos índices; das 65 em que o B13 muda o desligado (41 + 20 + 4), o
   relatório só conta. O meu julgamento está na linha da tabela acima: nenhuma classe nova, mas o §0 ainda diz «o B13 muda
   41 das 280» sem dizer para onde.
3. **A escolha entre a leitura certa e a do RapidOCR intercalada numa página de índice é frágil, e um julgamento do
   §0.7 está errado.** A medida nos dois sentidos, do construtor, passa 5 páginas reais ao RapidOCR intercalado (Karpov 2
   p. 267: 5 → 45 descidas em 108 verbetes). E na varredura do próprio construtor (o serviço na página do PDF original,
   sem o B14) a Nunn p. 288 sai com a leitura intercalada do RapidOCR («R352, 441, P29, 205, Ruge»): CER **0,7516**
   ligado e desligado, contra 0,7402 do ciclo 4 — 30 descidas da ordem alfabética em 73 verbetes (a verdade tem 3 em 74);
   o §0.7 a conta entre as «três para melhor» («Nunn p. 288, 42 → 0 … iguais ao desligado») olhando só as linhas com
   dois verbetes (`scratchpad\c5\varre_diffs\nunn_minor_p288.txt`; o CER contra a verdade: `c5\indices_varredura_cer.py`
   → `c5\indices_varredura_cer.out`, onde a Yusupov p. 206 vai de fato de 0,7908 a 0,0458). Pelo
   importador, a mesma página digitalizada sai 0,0193 com o B14 ligado ou desligado (`c5\nunn288_caminhos.out`): o que
   decide o vencedor ali não é o `_engine_order` só — é o caminho. Dito no §0.3 («o conserto que falta é o do
   RapidOCR»); fica, latente.
4. **O motor que falha é dito só no traço**: a nota vai a `PageRecognition.notes` → `ocr_trace.json` (só com
   `asset_dir`) e ao log; o item de revisão mostra «Escore 0.749 abaixo do limite…» (`c5\falha_motor_importador.out`), e
   uma região aceita depois de uma falha não teria aviso nenhum na interface. Com `MemoryError` a página some da fila de
   revisão (nenhum item), com «OCR falhou na página 165: bad allocation» nas notas do relatório. O roadmap diz «a página
   diz qual motor falhou e por quê».
5. **As setas na tabela da Revisão de texto** (`c5\setas_revisao.out`): o comentário do ciclo 5 diz «As setas andam
   pelas linhas»; a primeira ↓ vai à linha 1 e manda o foco à «Verdade da linha».
6. **A lista de lances do Estudo só por mouse** (tronco `4f3e218`): sem `LinksAccessibleByKeyboard`, quem usa o teclado
   ou um leitor de tela não salta a um lance da lista; dito no commit («os lances pelas setas da sala»).
7. **Foco parcial**: na Fita a 1280×641, «Leitura do motor» da Revisão de texto recebe o foco com 28 de 48 px à vista
   (58 %), com o filtro; a tabela da Rotulagem com 43–45 % (`c5\tecla\*.out`).
8. **Números do relatório**: «o ciclo 4, 24 das 41» — a saída do próprio construtor (`scratchpad\c5\sondas3\notas_risco_w24.out`)
   soma 23, igual à minha; e «Nunn p. 288, 42 → 0» linhas de dois verbetes dá 1 com a regex do próprio `cmp_varre_c5.py`.
9. **A franja, na posição da Gallagher p. 50** (notas | partida com as pretas numa parada): 1 de 41 embaralhada
   (Dvoretsky p. 789, 0,5052 → 0,6522), igual no ciclo 4 (`c5\franja_espelho.out`).
10. **Fora do B13, a última página de um índice de três colunas**: com 3 ou 5 verbetes na terceira coluna, o Tesseract
    junta cada um à linha da segunda («Ivkov 268 Robatsch 178»), ligado = desligado, `accepted` (0,0931 e 0,1544;
    `c5\ataque\cer_ataque.out` pp. 1–2).
11. **Uma tabela cujas duas primeiras colunas sobem em ordem por acaso é lida como dois índices**
    (`c5\b13_tabela_em_ordem.out`): a classificação de um torneio com os nomes em ordem alfabética sai por linhas
    (0,1207), mas se a coluna seguinte também sobe (os países, na mesma tabela), a calha entre elas vira da página e os
    nomes saem sozinhos, 0,6367 — melhor que o desligado (0,7509), longe da mesma tabela com a outra coluna (0,1207).
    Composta, e o caso é raro; é o outro lado do bloqueante novo 1: a ordem alfabética não diz o que é lista.
12. **Ficam, ditos pelo construtor:** a «Folha transcrita» do Texto prende o Tab (arquivo de outra sessão; o portão
    REPROVOU, dito no §0, §0.3, §0.7 e no roadmap); as oito brechas do A15; a Estrin pp. 29/77; o custo da reserva de 320
    px e o nome a ~95 px; o portão só `offscreen`.

### O que falta

- A janela na plataforma real (`windows`): tudo `offscreen`, com a fonte do produto imposta pelo arnês.
- O `bench_sol` inteiro (o briefing proíbe): a fila foi conferida item a item dos JSON.
- As varreduras do construtor não as refiz (conferi o código delas e julguei as páginas); as sondas do corpus e do
  importador, refiz todas na minha árvore.
- Os catorze diálogos com as rolagens no topo: a minha volta mediu as oito áreas; o diálogo «Base de partidas»
  (`qt/dialogos.py:229`) tem uma rolagem de caixas que o Tab alcança de fora (os botões ficam abaixo dela) e que não
  medi com bases bastantes para rolar.
- A comparação às cegas da Carta não se aplica a esta frente.

### O que especificamente precisa mudar para eu aprovar (se REPROVADO)

1. **B13 — uma lista ao lado de outra é lista, em ordem alfabética ou não, curta ou longa.** A calha antes da segunda
   de duas colunas da mesma forma (células de nome e páginas; jogador e adversários recuados) é da página sem pedir a
   ordem alfabética nem 6 cabeças à coluna — ou o cruzamento de qualquer calha pede a evidência positiva de tabela que
   hoje só a lista de lances dá. E uma partida ao lado de uma tabela não é uma tabela. Travar por teste, com a
   sabotagem, as páginas `c5\ataque\indices_ataque.pdf` p. 8 («jogador / adversários» pela classificação: tem de sair
   como o desligado, 0,0000) e p. 4 (a última página «nome | páginas» com 5 verbetes: sem linha que junte dois
   verbetes) pelo importador, e a `c5\partida_tabela\P_T.png` pelo serviço; mantendo tudo o que hoje confere (a Flores
   pp. 460–464, a Nunn pp. 288–289, a Yusupov p. 206, a Aagaard pp. 892–893, o `tres.pdf`, o `construido.pdf`, a Karpov
   2 p. 268, a Gallagher p. 50 em 0,2028, as aberturas em 0,0113, o `table:2/4/7`, a franja em 0 de 41).
2. **O teclado da Rotulagem com linhas, e o foco que entra nas rolagens do tronco.** (a) A tabela «Linhas da página»
   deixando o Tab sair (como a da Revisão de texto), com um teste da tecla na Rotulagem **com uma página de linhas**, nos
   dois sentidos, alcançando os mesmos 36 controles que a tecla alcança com a tabela vazia, e a sabotagem; (b) toda
   rolagem que o Tab alcança de fora mostrando o
   controle que recebe o foco — no tronco, os modos da aba Livro e a Galeria (e o diálogo «Base de partidas» com muitas
   bases) —, medido a 1280×641 nas três peles com a rolagem no topo; (c) o portão do teclado medindo cada sentido com
   as rolagens como o usuário as encontra (no topo, ou a área mostrada de novo) e a Rotulagem com uma página, com a
   sabotagem ao lado: o filtro desligado na Revisão de texto tem de reprovar o portão; (d) corrigir o §0, o §0.7 («a
   tecla chega a elas e as mostra», linha 703; e o item 2), o §C18, o roadmap e o `HANDOFF.md`.
3. **No mesmo ciclo:** julgar (ou dizer que não se julgou) as páginas em que o B13 muda o desligado; o «24» → 23; a Flores
   p. 461 dita como é; e a nota do motor que falhou chegando a quem revisa (ou dito que só o traço a guarda).

## Crítico Claude — ciclo 6 (REPROVADO, 3 bloqueantes)

VEREDITO: REPROVADO
CICLO: 6
FRENTE: OCR/UI ciclo 2, fase 5

Convenções dos comandos: os scripts e as saídas deste ciclo estão em `C:\Python-Chess2\_critico_f5\c6\` (a saída de cada
um ao lado ou na pasta dele; as filas em `*.sh`, com `runs.log`). Todo o código medido é o dos commits: a suíte numa árvore
minha, `git worktree add --detach C:\Python-Chess2\_critico_f5\suite_c6 9eb401c` (o `src` do `9eb401c` é o do `99ad8d7`:
`git diff --stat 99ad8d7 9eb401c -- src tests benchmarks` vazio; o OCR é o do `7f839f0`; `models\` copiada do checkout sem
`tessdata\work`, e para a suíte inteira os artefatos de `benchmarks\reports` que o git não guarda), e o tronco noutra,
`git worktree add --detach C:\Python-Chess2\_critico_f5\tronco 6e68315` (sem o `.pt`, como todo clone). Para comparar
regras, as três versões do `rows.py` tiradas do git (`c6\rows\rows_{4e42158,2c81e36,7f839f0}.py`). `git status` das duas
árvores vazio do começo ao fim (as linhas `status=[0]` dos `runs.log`). Sondas do corpus e de páginas renderizadas com
`CAISSA_FIGURINE_TESSDATA=models\tessdata`; importador, janela e testes sem ela. Memória virtual livre gravada a cada 3 s
(`c6\memoria.log`, `c6\monitor_mem.ps1`): caiu a **702 MB** às 01:11:49, no primeiro minuto da fila das sondas (abaixo de
2 GB de 01:11:36 a 01:12:16, com a suíte inteira do tronco de outra sessão ao lado); nenhuma sonda registrou falha de motor
(`grep "falhou\|bad alloc\|MemoryError"` nas saídas: 0) e as do primeiro minuto saíram iguais byte a byte às do ciclo 5.
A sessão foi interrompida por limite de uso da API e retomada (a fila das sondas tinha terminado); nada ficou rodando.
Nenhum arquivo dos dois repositórios foi editado. Processos meus que encerrei: uma sonda da Rotulagem parada a 0 % de CPU
depois de gravar tudo (a armadilha 7.2 da Carta, no `processo_de_trabalho().encerrar(esperar=True)`; troquei a saída das
minhas sondas por `c6\saida_limpa.py`), seis filhos `multiprocessing.spawn` órfãos que as minhas sondas de clique
deixaram (criados às 10:30:29–10:32:10, na saída delas) e as duas corridas da sonda do clique na linha, paradas a 0 % de
CPU; o PID 1996 é de antes e ficou. Nenhum processo meu ficou vivo. No fim (11:04) as minhas três árvores (a da suíte, a do
tronco e uma do `aa22702`) foram removidas com `git worktree remove`; o checkout da suíte está como no começo
(`9eb401c`, os mesmos arquivos de outras sessões modificados) e o do tronco avançou de `6e68315` para `aa22702`, commit de
outra sessão (`c6\estado_inicio.txt`, `c6\estado_fim.txt`); o `labeling/project.json` do usuário, o mesmo hash e a mesma
data de 2026-09-15.

### Conferências feitas

| passo | comando/arquivo:linha | confere? | nota |
|---|---|---|---|
| Bloqueante 1 do ciclo 5, as páginas que dei, pelo importador, 3 execuções | `c6\sondas_c6.sh` (`c4\b13_importador_arvore.py`) → `c6\sondas\b13i_ataque_r{1,2,3}.json`; `c6\cer_c6.py` → `c6\cer_sondas_parcial.out`, `…parcial2.out` | sim | `indices_ataque.pdf` p. 8 («jogador / adversários» pela classificação) **0,0000 `accepted` = desligado**; p. 4 (a última página, cinco verbetes) 0,6634 → **0,0048** `accepted`, 0 linhas com dois verbetes; p. 5 0,0028; as três execuções iguais byte a byte |
| O que mandei manter, pelo importador, 3 execuções | mesma fila → `c6\sondas\b13i_{flores,tres,indices}_r{1,2,3}.json`, `b13i_{construido,karpov268,gallagher,notas_en}.json`; `cer_c6.py --igual` | sim | **todos iguais byte a byte aos do meu ciclo 5**: a Flores pp. 460–464 0,0438/0,0853/0,0230/0,0202/0,0364; o `tres.pdf` 0,0007/0/0/0,0058; a Yusupov p. 206 0,0465, a Nunn pp. 288/289 0,0193/0,0174, a Aagaard pp. 892/893 0,0958/0,0769 `accepted`; o `construido.pdf`, a Karpov 2 p. 268, a Gallagher pp. 50–53 (p. 50 **0,2028**, `gallagher_cer_c2.py` → `c6\gallagher_cer.out`), as notas inglesas |
| Partida × tabela e tabela em ordem, pelo serviço (quatro regras: desligado, commit, 2c81e36, ciclo 5) | `c6\b13_servico_regras.py` → `c6\servico\partida_tabela.out`, `tabela_em_ordem.out` | sim | P\|T 0,2218 → **0,1418** (ciclo 5 0,7564); P\|Tn 0,3185 → 0,2611 (2c81e36 0,3376); T\|P 0,2182 → 0,2109; Pt\|T 0,5055 → 0,1527; P\|T3 0,3185 → 0,2611; a tabela com os nomes em ordem 0,7448 → 0,1207 e com os países em ordem 0,7509 → **0,1280** (ciclo 5 0,6367) — os números do construtor |
| As outras sondas do serviço | `c6\sondas\{estreita3_just,estreita3,tabulada,lista_recusada,tabelas3,tabelas_c2}.out` × as do ciclo 5 (`md5` das linhas de CER) | sim | iguais, menos uma linha da `tabelas3`: a classificação (1, 2, 3…) a 150 DPI 0,1818 → 0,1866 (o construtor a diz, §0.8); as aberturas 0,0113 |
| A franja | `c6\lib\b13_franja_espelho.py 100` → `c6\sondas\franja_espelho.out`; `b13_notas_medida.py 100 24` → `notas_risco_w24.out` | sim | **0 de 41** nos quatro leiautes (a Dvoretsky p. 789 N\|Pt 0,5052 → 0,3720); notas de risco 0 |
| As 1.622 leituras guardadas | `c6\todas_leituras_c6.py` (meu; só a leitura guardada é do construtor) → `c6\todas_leituras_c6.out` | sim | 4e42158 → 2c81e36: **8**; 2c81e36 → 7f839f0: **26**; o ciclo inteiro: 33; o corpus (1.048): 0 — os números dele, pelas mesmas listas de leituras |
| As seis páginas de leitura não escolhida, pelo serviço | `c6\varre_seis.sh` → `c6\varre_seis\`; `c6\cmp_seis.py` → `c6\cmp_seis.out` | sim | as seis iguais às do construtor no `7f839f0`, ligadas e desligadas; cinco iguais ao desligado; a Reinfeld 1977 p. 319 melhor (os dois títulos) |
| As 59/66 páginas julgadas | `scratchpad\c6\b13_muda_c7.out` e `b13_muda_c7\*.txt` | em parte | conferi as onze de ruído com menos fração de ruído (Estrin pp. 20, 29, 43, 48, 51, 58, 78; Gallagher pp. 137, 170; Aagaard pp. 183, 188): todas ruído de diagrama e coordenadas; as 7 que saem da lista no `7f839f0` são as que a minha reordenação acha. Não recontei as 66 |
| A fila de A/B e o `sol.json` | `c6\conf_sol_c6.py` → `c6\conf_sol_c6.out` | sim | `f5c6_*` (2c81e36) e `f5c7_*` (7f839f0), `dirty_code=[]`, iguais às `f5c5_*` em todo campo por item (o texto: 61/66/85 itens, 0 diferem); o `sol.json` do `9eb401c` com `commit=99ad8d7`, `dirty_code=[]`, igual à `f5c7_on` e ao do ciclo 5 item a item; `f5_ab.json` com as 20 corridas igual aos JSON; aceitos errados 7; `table:2/4/7` 0,0035/0,00364/0 |
| A transcrição do meu ciclo 5 | `c6\transcricao_c5.out` | sim | as 222 linhas não vazias do meu veredito estão em `OCR_UI_ANALISE_C2_CRITICAS.md` (linhas 1541–1779), salvo o nível dos títulos |
| Ataques à regra nova, pelo serviço (17 páginas compostas, quatro regras) | `c6\ataques_c6.py` → `c6\ataques\`; `c6\b13_servico_regras.py c6\ataques` → `c6\servico\ataques.out` | **não** | → **bloqueante novo 1**; as outras no não bloqueante 3 |
| Os ataques que quebram, pelo importador, 3 execuções | `c6\importador_c6.sh` → `c6\importador\`; `cer_c6.py` → `c6\importador_cer_parcial.out`, `…parcial2.out` | **não** | índice de quatro algarismos 0,0026 → **0,4916 `accepted`**; lista com a coluna do meio de outra forma 0,0032 → **0,7747 `accepted`**; 19 linhas com dois verbetes em cada; as três execuções iguais byte a byte |
| As páginas que o construtor deixou abertas, pelo importador | `c6\paginas_construtor.py` → `c6\paginas_construtor\`; importador + `cer_c6.py` → `c6\paginas_construtor.out` | **não** | a classificação em duas metades 0,3316 `accepted` → **0,7053 `accepted`** (bloqueante novo 1 (c)); o emparceiramento 0,6853 `accepted` ligado = desligado; a partida ao lado de um índice 0,6978 `accepted` ligado = desligado, 11 linhas juntas (não bloqueante 2) |
| Os índices reais degradados como o estrato de 150 DPI | `c6\indices_150.py` → `c6\i150\indices_150.pdf`; importador ×3 → `c6\i150_cer.out` | em parte | 7 de 9 saem intercalados com o B13 ligado **ou** desligado (0,70–0,78, `review`); o B13 melhora a Flores pp. 461 e 463 (0,3642 → 0,1269 `accepted`; 0,7088 → 0,1358); três execuções iguais (não bloqueante 6) |
| Bloqueante 2 do ciclo 5: a Rotulagem com a Gallagher p. 51 (66 linhas), na janela inteira, 1280×641, três peles | `c6\rotulagem_c6.py` → `c6\tecla\rotulagem_{classica,foco,fita}.out` | sim | o instrumento do portão passa nos dois sentidos (58/62/82 alcançados, nenhum escondido); as setas ↓ andam as linhas com o foco na tabela e o cartão acompanhando; nenhum controle com 0 px (a tabela recebe o foco com 69–76 % à vista na Clássica e na Foco, 42 % na Fita) |
| As voltas com as rolagens no topo | `c6\tecla_vista_c6.py` (três peles a 1280×641 e a Fita a 1246×629) → `c6\tecla\volta_*.out` | sim | toda área anda nos dois sentidos, **nenhum foco a 0 px**; só o Texto empaca («Folha transcrita», arquivo de outra sessão) |
| O Shift+Tab que entra nas rolagens do tronco | `c6\foco_fora_c6.py` → `c6\tecla\foco_fora_*.out` | sim | do primeiro controle, o Shift+Tab dá a volta inteira no Resultado, Estudo, Revisão e Galeria das três peles sem um controle sem pixel à vista (no ciclo 5: «Esconder incerteza» a 0×0 em duas teclas) |
| O portão, rodado por mim | `c6\portao_c6.sh` → `c6\portao\`; `c6\resumo_portao.py` → `c6\portao\resumo.out` | sim | Clássica e Fita a 1280×641 com o Kemeri: a Rotulagem medida com **47 linhas na medida**, só o Texto REPROVOU; `--sabotar foco` reprova Resultado, Galeria, Rotulagem, Revisão de texto e o diálogo com 40 bases; `--sabotar tabela` reprova a Rotulagem; `minimo` sem livro PASSOU, `--sabotar linha` REPROVOU |
| O portão escreve no `labeling/`? | `c6\estado_arvores.py` antes e depois (o `labeling/` do usuário copiado para a minha árvore, que é o que `default_project_dir()` abre nela) | sim | 1.512 arquivos, **0 mudaram**; `project.json` com o mesmo hash e a mesma data (2026-09-15 05:49:26), como o do checkout do usuário. A janela do tronco escreve o `data/games_positions.sqlite` (o cache de posições) da árvore do tronco que abre — não é do ciclo |
| O seguidor fora das rolagens: outra janela, rolagem morta | `c6\rolagem_morta.py` → `c6\rolagem_morta.out` | sim | o diálogo de bases destruído e depois trocas de foco: 0 exceções; o foco num campo de outra janela: 0 rolagens mexem; mas o diálogo aberto e fechado fica vivo como filho da janela com o seguidor ligado à aplicação (7 → 16 seguidores em 20 aberturas; não bloqueante 7) |
| O seguidor e o **mouse** | `c6\clique_parcial.py` (clique pelo `QWindow`: pressionar e soltar no mesmo ponto da janela) → `c6\tecla\clique2_*.out`; `c6\tabuleiro_salta.py` → `c6\tabuleiro_salta.out`; `c6\radio_salta.py` → `c6\radio_salta.out` | **não** | → **bloqueante novo 2** |
| As teclas de lista nas tabelas | `c6\teclas_de_lista.py` → `c6\tecla\teclas_de_lista_classica.out` | **não** | → não bloqueante 1 |
| A falha do motor na revisão | `c6\pagina_abstida_enter.py` → `c6\pagina_abstida_enter.out`; `c6\pagina_abstida_aceita.py` → `c6\pagina_abstida_aceita_gal53.out` | **não** | a região aceita com um motor a menos indo para revisão, com a falha entre os motivos, é certo (lido em `OcrService._with_failures` e no teste dele, que passou; não medido à parte); o item de página abstido → **bloqueante novo 3** (no produto o painel nasce sem `pasta`, `qt/painel_de_revisao_de_texto.py:50`, e grava em `decisions_path(pdf)`, o arquivo que o importador lê) |
| A «Folha transcrita» no `aa22702` (outra sessão; não é objeto) | árvore minha do `aa22702`, `c6\tecla_vista_c6.py` → `c6\tecla\volta_aa22702_foco.out` | sim | com ele o Texto anda nos dois sentidos (45 controles, fecha) na Foco a 1280×641: o item aberto do §0.3 se fecha fora deste ciclo |
| Testes novos e tocados | `c6\testes_c6.sh` → `c6\suite_testes_tocados.out`, `c6\tronco_testes_tocados.out` | sim | suíte **162 passaram** em 115 s (`test_table_rows`, `test_listas_compostas`, `test_indices_do_acervo`, `test_ocr_service`, `test_importer`, `test_table_rows_page`, `test_arbiter`, `test_foco_a_vista`, `test_revisao_de_texto_view`, `test_rotulagem_view`, `test_teclado_tecla`; nenhum pulado); tronco 61 passaram (+4 subtestes) |
| Suítes inteiras | `c6\testes_full_c6.sh` → `c6\trunk_full_c6.out`, `c6\suite_full_c6.out` | sim | tronco (árvore `6e68315`): **4.798 passaram, 16 pulados, 8 xfail, 1 reprovou** em 445 s — o `test_environment::…resolve_para_esta_arvore`, por construção da árvore efêmera (o mesmo do construtor); suíte (árvore `9eb401c`, com o `test_arquitetura`): **4.055 passaram, 25 pulados, 1 erro** em 806 s — o `test_gpu_parity::test_cuda_actually_computes` na montagem, pela minha `CAISSA_CVOFF_ROOT` (o mesmo dos ciclos 1–5); 4.055 + 25 + 1 = 4.081 = a conta do construtor (4.072 + 9); as duas árvores limpas antes e depois |
| O mouse na tabela da Rotulagem | `c6\clique_na_linha.py` → `c6\clique_na_linha.out` | não conclusivo | com a rolagem no topo, a 1280×641, na Clássica e na Foco, a sonda não achou uma linha inteira de «Linhas da página» à vista para clicar; e a segunda corrida parou a 0 % de CPU (encerrada por mim). Pelo código, o clique numa linha continua mandando o foco à verdade (`pelas_setas` é falso com o botão apertado): o mouse não perde nada com as setas; perde com o seguidor (bloqueante novo 2) |
| As frases que corrigi no ciclo 5 | `grep` no relatório, no roadmap e no `HANDOFF.md` do `9eb401c` | em parte | a Flores p. 461, o «42 → 0», «a tecla chega a elas e as mostra» e a Rotulagem vazia estão ditos como são; o «24» ficou em dois lugares (não bloqueante 8) |

### Os bloqueantes do ciclo 5

**1. Uma lista ao lado de outra é lista — resolvido nas páginas que dei; não resolvido na classe, e a regra nova tem um
buraco que a do ciclo 5 não tinha.** As páginas: a p. 8 do `indices_ataque.pdf` sai igual ao desligado (0,0000,
`accepted`), a p. 4 0,6634 → 0,0048 sem linha que junte dois verbetes, três execuções iguais; a partida ao lado da
classificação 0,2218 → 0,1418; a tabela em ordem por linhas; e tudo o que mandei manter saiu igual byte a byte ao meu
ciclo 5 (a Flores, a Nunn, a Yusupov, a Aagaard, o `tres.pdf`, o `construido.pdf`, a Karpov 2 p. 268, a Gallagher p. 50
em 0,2028, as aberturas em 0,0113, o `table:2/4/7`, a franja em 0 de 41). Mas a calha entre duas listas só é da página
quando as duas têm **a mesma forma** (`_list_gutters`, `rows.py:518–546`), e a forma de uma coluna de lista muda por
detalhes que colunas vizinhas da mesma lista não compartilham: uma linha com dois números, um número de quatro algarismos
(`_band_form`, `rows.py:508`: sem lista e com quatro algarismos é «nome com valor»), a coluna sem números. Onde a forma
difere, as colunas voltam a ser intercaladas e aceitas (bloqueante novo 1) — páginas que a regra alfabética do ciclo 5 lia
certo. O §0.8 (linha 803) diz «a forma das colunas faz o trabalho dela em toda página que ela fazia»: não faz.

**2. O teclado onde o usuário o usa — resolvido.** A Rotulagem com a Gallagher p. 51 reconhecida (66 linhas) anda nos
dois sentidos nas três peles a 1280×641, com as setas guardando o foco na tabela; com as rolagens no topo nenhum foco
fica a 0 px em área nenhuma (três peles e o mínimo da Fita), e o Shift+Tab de fora dá a volta inteira nas quatro áreas do
tronco; o portão mede cada sentido com as rolagens no topo e a Rotulagem com 47 linhas, e as duas sabotagens reprovam
onde devem (rodado por mim); o `labeling/` não é tocado. Mas o conserto — o seguidor que ouve **toda** troca de foco da
aplicação e rola até o controle inteiro — rola também no clique do mouse, entre o pressionar e o soltar (bloqueante
novo 2).

### Defeitos bloqueantes (novos)

1. **O B13 intercala listas cujas colunas têm formas diferentes — e o importador aceita.**
   - **Onde:** `src/caissa/ocr/layout/rows.py`, `_band_form` (linhas 489–515: uma faixa é «verbetes», `E`, se tem uma
     linha com dois números ou todos os números com até três algarismos, `_PAGE_DIGITS = 3`, linha 437; senão «nomes com
     valor», `V`; só nomes, `W`) e `_list_gutters` (linhas 518–546: a calha é da página só entre duas unidades **da mesma
     forma**, e `W` só numa página que é toda `W`).
   - **O quê, com números** (páginas compostas como um livro digitalizado, Times 9 pt a 300 DPI, como as do ciclo 5;
     pelo **importador de produção**, três execuções iguais byte a byte; CER contra a ordem do livro;
     `c6\importador_cer_parcial.out`):
     - **(a) um índice de jogadores com números de problema de quatro algarismos em três colunas** (o formato de uma
       coleção de milhares de problemas; `c6\ataques\indice_4dig.pdf`): duas colunas têm uma linha com dois números
       («Alekhine 1204, 3318», «Gelfand 2087, 4410») e a terceira não — formas `E`, `E`, `V` (`c6\servico\ataques.out`):
       **0,0026 `accepted` → 0,4916 `accepted`**, 19 linhas «Chiburdanidze 4377 Larsen 2131»; a regra do ciclo 5 lia
       0,0026;
     - **(b) uma lista cuja coluna do meio tem outra forma** (verbetes | só nomes | verbetes, `nomes_so_verb.pdf`, o
       ataque que o briefing pedia): formas `E`, `W`, `E`: **0,0032 `accepted` → 0,7747 `accepted`**, as três colunas
       juntas linha a linha («Aagaard 54 Chiburdanidze Larsen 314»); o ciclo 5 lia 0,0032.
     - **(c) a classificação de um torneio em duas metades que o próprio construtor compôs e deixou aberta** (§0.3,
       `scratchpad\c6\paginas\classificacao_2metades.png`, passada por mim pelo importador,
       `c6\paginas_construtor.py` → `c6\paginas_construtor.out`): **0,3316 `accepted` → 0,7053 `accepted`** — o OCR perde os
       pontos de uma metade, a forma dela vira «só nomes», e a calha entre as metades deixa de ser da página. O relatório a
       dá como «dito, não resolvido»; não é aceitável deixar: é o mesmo defeito, por outro detalhe.
     Nas (a) e (b) o desligado e a regra do ciclo 5 leem certo, e as duas regras do ciclo 6 (`2c81e36` e `7f839f0`) erram
     igual: é a regra das formas, não a da linha alta. No acervo não achei página com essa forma
     (`c6\acha_indices_4dig.py` → `acha_indices_4dig.out`: o índice da Karpov 1 tem quatro algarismos, mas em duas
     colunas com linhas de dois números nas duas); as páginas do ciclo 5 que estabeleceram o bloqueante também eram
     compostas.
   - **Como reproduzir:** na árvore da suíte, com `CAISSA_FIGURINE_TESSDATA=models\tessdata`,
     `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c6\ataques_c6.py` (grava as páginas e as verdades) e
     `…\c6\b13_servico_regras.py C:\Python-Chess2\_critico_f5\c6\ataques` (as quatro regras); sem a variável,
     `SUITE_REPO=<árvore> .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c4\b13_importador_arvore.py C:\Python-Chess2\_critico_f5\c6\ataques\indice_4dig.pdf 0 <saida.json>`
     e `…\c6\cer_c6.py <saida.json> --pdf …\c6\ataques\indice_4dig.pdf`; a página do construtor:
     `…\c6\paginas_construtor.py <pasta>` e o mesmo par de comandos em `<pasta>\classificacao_2metades.pdf`.
   - **Por que reprova:** é a classe do bloqueante 1 dos ciclos 2, 4 e 5 e o texto do item 1 que pedi («uma lista ao lado
     de outra é lista, em ordem alfabética ou não, curta ou longa»); numa página que o desligado e o ciclo 5 leem certo, o
     B13 do ciclo 6 produz um texto trocado linha a linha e o importador o **aceita** — confiança alta em resultado
     errado (Carta §3.3).

2. **O seguidor de foco rola a rolagem no clique do mouse, entre o pressionar e o soltar: o clique se perde, e no
   Estudo o tabuleiro joga um lance que ninguém jogou.**
   - **Onde:** `qt/foco_a_vista.py` do tronco (`6e68315`, linhas 65–70) e `ui/widgets/foco_a_vista.py` da suíte
     (`2c81e36`, linhas 76–81): `_foco_mudou` chama `mostrar` em **toda** troca de foco, também a que o clique dá — e o Qt
     dá o foco no pressionar, antes de entregar o evento; ligado aos modos da aba Livro (`qt/painel_principal.py:127`), à
     lateral da Galeria e ao diálogo de bases. O tabuleiro do Estudo completa o lance no soltar, na casa sob o ponteiro
     (`qt/tabuleiro_de_jogo.py:162–179`).
   - **O quê, com números** (a janela a 1280×641 com o Kemeri, as rolagens no topo como o usuário as encontra; o clique
     pelo `QWindow` — pressionar e soltar no mesmo ponto da janela, o que um mouse parado faz):
     - **em todo controle meio à vista numa rolagem que segue o foco, o soltar cai fora dele: 15 de 15** nas três peles
       (`c6\tecla\clique2_*.out`: a rolagem salta +13 a +129 px no pressionar); com o seguidor desligado, 0 de 15 e
       nada rola;
     - **o lance fantasma** (`c6\tabuleiro_salta.out`): na pele **Foco** (a padrão), o «Tabuleiro da partida» do Estudo
       fica com 13 px abaixo da dobra; depois de 1.e4 (as pretas jogam) e com o foco no campo da FEN, **um** clique na
       parte de baixo da casa e7 — para selecionar o peão — rola +19 px e **joga 1…e6** (a pilha vira `['e2e4','e7e6']`,
       as brancas passam a jogar); com o seguidor desligado o mesmo clique só seleciona e7. Na Fita o salto é de 129 px;
     - **o clique perdido** (`c6\radio_salta.out`): na Foco, os botões de rádio «Brancas» / «Pretas» do Resultado (o lado
       que joga na posição lida) ficam com 9 de 22 px à vista; o clique rola +19 px e **não marca** (continua desmarcado);
       com o seguidor desligado, marca. Quem acerta o lado a jogar e salva sem conferir grava a FEN errada. O «Gravar» da
       Galeria na Clássica perde o clique do mesmo jeito (`clique2_classica.out`).
     Pelo código do ciclo 5 da suíte (o filtro de `FocusIn` com `ensureWidgetVisible`), a classe já existia nas duas abas
     da suíte para botões — lido no código, não medido; o ciclo 6 a leva ao controle inteiro e às áreas do tronco.
   - **Como reproduzir:** sem a variável, `QT_QPA_PLATFORM=offscreen`,
     `PYTHONPATH=<suíte>\src;<tronco>\src;<checkout>\.venv-pack\Lib\site-packages`:
     `.venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c6\tabuleiro_salta.py <suíte>\src <tronco> foco 1280 641 "<PDF>\1937 Kemeri.pdf" 3`;
     `…\c6\radio_salta.py <suíte>\src <tronco> foco 1280 641 "<PDF>\1937 Kemeri.pdf"`;
     `…\c6\clique_parcial.py <suíte>\src <tronco> classica 1280 641 "<PDF>\1937 Kemeri.pdf" <saida.json>`.
   - **Por que reprova:** «qualquer coisa que trema, salte ou pisque durante interação» reprova sozinho (Carta §3.3); aqui
     o salto ainda muda o resultado: um lance que o usuário não fez entra no estudo dele, e um clique no lado a jogar se
     perde sem aviso — na pele padrão, no portátil-alvo, com a janela como ele a encontra.

3. **O item de página abstido, aceito com o Enter, vira a aceitação silenciosa — verificada — da leitura seguinte da
   página inteira.**
   - **Onde:** `ingest/pdf/importer.py:1000–1017` (`_failed_for_review`, `2c81e36`: o item `kind="page"`,
     `decision="abstained"`, o retângulo da página inteira, texto vazio); `ui/views/revisao_de_texto.py:611–616` (o Enter
     com a verdade vazia é «Aceitar leitura»); `ocr/review.py:333–346` (`decisions()` grava o aceite sem olhar o tipo) e
     `467–535` (`ReviewDecisions.apply` casa a decisão com toda região não aceita da página com IoU ≥ 0,5 contra o
     retângulo); o produto aplica o arquivo sozinho na importação e na exportação seguintes (`ui/views/importacao.py:162`,
     `export/book.py:534`; no tronco `qt/importador_de_livro.py:289`).
   - **O quê, com números** (a Gallagher p. 54, pelo importador de produção; `c6\pagina_abstida_enter.out`,
     `c6\pagina_abstida_aceita_gal53.out`): com o OCR levantando `MemoryError`, a página sai `image-only` e a Revisão de
     texto mostra, no topo da fila (risco 1,30), «O OCR falhou nesta página (o provedor falhou: bad allocation): ela não
     foi lida.», a verdade vazia e o foco nela; o **Enter** grava `accept`, retângulo (0, 0, 381, 597), texto `""`. Na
     importação seguinte, a região da página (IoU 1,00 com o retângulo), que o árbitro mandava para revisão com «5
     palavra(s) fora da geometria das linhas» e «sequência de lances repetida … suspeita de invenção», sai **`accepted`,
     «aceita pelo revisor», `verified=True`**, e a página some da fila de revisão (0 itens; o controle sem as decisões:
     1 item). O mesmo mecanismo já alcançava o item de página da camada contestada sem resposta
     (`_contested_without_answer`, desde a fase 1, `a921641`); o `2c81e36` põe nele a página cujo OCR levanta — o
     caminho que eu pedi no item 3 do ciclo 5.
   - **Como reproduzir:** sem a variável, `SUITE_REPO=<árvore> .venv\Scripts\python.exe C:\Python-Chess2\_critico_f5\c6\pagina_abstida_aceita.py "<PDF>\GALLAGHER - Winning With the King's Gambit.pdf" 53 eng`;
     a janela: `…\c6\pagina_abstida_enter.py <suíte>\src <tronco> "<PDF>\GALLAGHER - Winning With the King's Gambit.pdf" 53`.
   - **Por que reprova:** falha silenciosa e confiança alta em resultado que ninguém viu (Carta §3.3): o revisor aceitou
     «nada» numa página que não foi lida, e o produto transforma isso em «revisado» para a leitura que vier depois, e a
     tira da fila. É o menos frequente dos três (pede um `MemoryError` numa página), e o mais grave em consequência.

### Defeitos não bloqueantes

1. **As teclas de lista nas tabelas vão para os atalhos da janela** (`c6\tecla\teclas_de_lista_classica.out`, Clássica
   1280×641): com o foco em «Linhas da página» (a Rotulagem com a Gallagher p. 51), o **PgDn leva a aba à página
   seguinte do livro** (p. 52, a tabela vazia, o cartão vazio; o PgUp volta), o End manda a janela à última página (191),
   o Home à primeira; em «Dúvidas do livro», PgDn/End/Home viram a página do livro atrás da aba e a linha da lista não se
   mexe. A guarda de atalhos do tronco (`qt/atalhos.GuardaDeAtalhos`) só cede essas teclas a campos de texto, e o ciclo 6
   agora guarda o foco na tabela; o `pelas_setas` (`cartao_da_linha.py:56`) promete «as setas (ou o PgUp/PgDn)».
2. **Uma partida ao lado de uma coluna só de números** (`part_numeros`): pelo serviço 0,0170 → 0,6136 (revisão), igual
   no ciclo 5 — o `mixes` só protege a coluna de nomes. E **pelo importador a partida ao lado de outra coluna sai
   intercalada e aceita com o B13 ligado ou desligado**: a coluna de números 0,6080 `accepted`, e a partida ao lado de
   um índice que o construtor compôs 0,6978 `accepted` com 11 linhas juntas (`c6\paginas_construtor.out`; ele a mediu no
   nível do B13, 0,0149) — o intercalado vem do caminho do importador, fora do código deste ciclo, mas é a classe que o
   B13 existe para resolver e sai com confiança alta.
3. **Os outros ataques** (`c6\servico\ataques.out`, `c6\importador_cer_parcial2.out`): o emparceiramento com os ratings
   em coluna própria sai por linhas (importador 0,7577 → 0,0958); com o rating na célula do nome é lido por colunas
   (0,6563 aceito, igual ao desligado e ao ciclo 5 — o «tabela só de nomes lida como listas» do §0.3 vale também para
   nome com valor); a tabela de matches com meio ponto 0,7318 → 0,6642 aceito; a partida em notação alemã ao lado da
   classificação pelo serviço 0,3308 → 0,7519 (revisão; o Tesseract corta os números «1.»… numa linha alta e a coluna de
   lances não é vista como partida; pelo importador ligado = desligado, 0,7256); a partida com figurinas 0,3307 → 0,2480;
   o índice de partidas com travessão, com «1/2-1/2» e o de ECO: ligado = desligado (o de ECO abstido, CER 1,0, dos dois
   lados); a regra da linha alta: a célula de duas linhas 0,3755 → 0,3537, o corpo maior igual, a tabela apertada
   0,6036 → 0,6081, a grade igual.
4. **A Rotulagem na Fita a 1280×641**: a tabela recebe o foco com 42–45 % à vista (81–87 de 192 px; o seguidor mostra o
   começo dela, que não cabe; `volta_fita_*.out`), igual ao ciclo 5 (não bloqueante 7 de lá).
5. **A leitura desligada que o B13 às vezes piora pouco**: a classificação (1, 2, 3…) a 150 DPI 0,1818 → 0,1866 (dita);
   a Euwe p. 69 N\|P na franja 0,5016 → 0,5212 (abaixo do limiar de 0,05).
6. **Índices reais a 150 DPI**: 7 de 9 páginas saem intercaladas com o B13 ligado ou desligado (0,70–0,78, em
   revisão; `c6\i150_cer.out`) — o intercalado é do motor, fora do B13 (o §0.3 o diz só da Nunn p. 288).
7. **O diálogo «Base de partidas» nunca é destruído** (`perguntar_bases`, `qt/dialogos.py:363–365`): cada abertura deixa
   um diálogo filho da janela com um seguidor ligado à aplicação (7 → 16 em 20 aberturas; `c6\rolagem_morta.out`).
8. **Números e frases do relatório**: o «24» corrigido no §0 e no §0.8 ficou no §0.2 (linha 147, «o ciclo 4, 24») e no
   roadmap (linha 1133); o §0.3 (linha 278) e o §0.8 (linha 1001) dizem que a publicação foi «refeita no `7f839f0`», e o
   §0.2 (linha 152) e o `sol.json` dizem `99ad8d7`; o §0.8 (linha 803), «a forma das colunas faz o trabalho dela em toda
   página que ela fazia» (bloqueante novo 1).
9. **Ficam, ditos pelo construtor:** a coluna de um verbete só, a tabela só de nomes lida como listas (o emparceiramento
   dele, «Brancas | Pretas», pelo importador 0,6853 `accepted` ligado e desligado — `c6\paginas_construtor.out`; aceito
   por colunas, mas não pior que o desligado), o ponto inteiro sozinho tomado por número de lance, o RapidOCR intercalando a
   Nunn p. 288 pelo serviço, a última página de três colunas lida junta pelo Tesseract, o `bench_sol` que grava a
   procedência no fim, o portão do teclado sem o commit das árvores; das fases anteriores, as oito brechas do A15, a
   Estrin pp. 29/77, o custo da reserva de 320 px e o nome a ~95 px, o portão só `offscreen`. A «Folha transcrita» do
   Texto se fecha no `aa22702` (outra sessão; medido por mim, não é objeto).

### O que falta

- A janela na plataforma real (`windows`): tudo `offscreen`. O clique foi imitado pelo `QWindow` do Qt (o despacho que o
  mouse usa); num mouse de verdade o soltar cai no mesmo lugar da janela, que é o que medi.
- O `bench_sol` inteiro (o briefing proíbe): a fila foi conferida item a item dos JSON.
- As 1.622 leituras guardadas são do construtor (o `OcrResult` de antes do B13); o script que as reordena é meu. Não
  recontei as 66 páginas julgadas.
- A comparação às cegas da Carta não se aplica a esta frente.

### O que especificamente precisa mudar para eu aprovar (se REPROVADO)

1. **B13 — uma lista ao lado de outra é lista, qualquer que seja o detalhe de cada coluna.** A calha entre duas faixas
   que são listas (verbetes, nomes com números, só nomes) não pode depender de as duas terem a mesma forma: uma coluna sem
   a linha de dois números, com números de quatro algarismos ou sem números continua sendo coluna da mesma lista — ou o
   cruzamento pede evidência positiva de tabela. Travar por teste, com a sabotagem, pelo importador,
   `c6\ataques\indice_4dig.pdf` e `c6\ataques\nomes_so_verb.pdf` (têm de sair como o desligado, 0,0026 e 0,0032, sem linha
   com dois verbetes) e a classificação em duas metades do construtor (não pior que o desligado, 0,3316), mantendo tudo o
   que hoje confere (as páginas do ciclo 5, a Flores, a Nunn, a Yusupov, a Aagaard, o
   `tres.pdf`, o `construido.pdf`, a Karpov 2 p. 268, a Gallagher p. 50 em 0,2028, as aberturas em 0,0113, o
   `table:2/4/7`, a franja em 0 de 41, a partida × tabela e o emparceiramento com os ratings em coluna própria por linhas);
   e corrigir a frase do §0.8 (linha 803).
2. **O seguidor não rola no foco que o mouse dá** (na suíte e no tronco) — ou rola sem tirar o controle de baixo do
   ponteiro entre o pressionar e o soltar —, mantendo o que o teclado ganhou (o Tab e o Shift+Tab de fora com o controle
   inteiro à vista). Travar por teste com o clique pelo `QWindow` (pressionar e soltar no mesmo ponto da janela) e a
   sabotagem: na Foco a 1280×641 com a rolagem no topo, o clique na parte de baixo de e7 com as pretas a jogar só seleciona
   o peão (nenhum lance), e o clique em «Pretas» marca «Pretas»; e o portão do teclado (ou o da janela) com esse clique.
3. **O aceite de um item sem leitura não vira decisão sobre outra leitura.** O Enter/«Aceitar leitura» num item de página
   (ou sem texto) não grava um `accept` que o importador aplique às regiões da página — recusado, ou sem efeito na
   importação —, para o item do `MemoryError` e para o da camada contestada. Travar por teste: `MemoryError` na página,
   Enter no item, importação de novo → nenhuma região «aceita pelo revisor», e a página continua na fila; com a sabotagem,
   aceita.
4. **No mesmo ciclo** (não bloqueantes): as teclas de lista nas duas tabelas (ou a tabela as guarda, ou o comentário para
   de prometer o PgUp/PgDn); o «24» do §0.2 (linha 147) e do roadmap (linha 1133); o «refeita no `7f839f0`» do §0.3 e do
   §0.8 contra o `99ad8d7`.
