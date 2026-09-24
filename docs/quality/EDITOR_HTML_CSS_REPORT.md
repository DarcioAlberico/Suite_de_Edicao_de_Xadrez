# Relatório do construtor — Editor HTML/CSS

> O relatório que o roadmap (`docs/EDITOR_HTML_CSS_ROADMAP.md`) pede: uma seção por passo, todo
> número com o comando ao lado. Os portões rodam pelo executor único
> (`& $PY benchmarks\editor_portoes.py --passo <Hn> --saida benchmarks\reports\editor\<hn>`), que
> grava o `portao.json` com o HEAD dos dois repositórios; as saídas ficam em
> `benchmarks/reports/editor/` (fora do git). Construtor: Claude (sessão «Implementações
> pendentes»), 2026-09-24.

---

## H0 — O executor de portões e os leitores medidos

**Estado:** o executor, o ambiente e o instrumento estão prontos e testados; **a medição completa
(3 execuções de ~1 h e as 6 sabotagens) ainda não rodou**: outra sessão mediu na mesma máquina o
dia todo, e medir junto contaminaria os tempos das duas.

- **O executor** (`benchmarks/editor_portoes.py`): `tests/unit/editor/test_portoes.py`, 46 casos,
  inclusive os passos falsos «instrumento ausente», «sabotagem inócua» e «passo bom», e as
  publicações adulteradas da auditoria (ciclos 19–21 do crítico).
  `& $PY -m pytest tests/unit/editor/test_portoes.py -q -p no:cacheprovider`
- **O denominador da verdade** (o manifesto `dev` + `calib`, hash `f019591babf2941e`, 237 regiões
  de PDF): digitalizado 653 lances, 464 com figurina, 199 regiões; nativo **198 lances, 0 com
  figurina**, 38 regiões — a razão da mutação do §10 do roadmap.
  `& $PY -c "import sys; sys.path[:0]=['benchmarks','src']; import editor_portoes as P; from caissa.ocr.golden import load_manifest; print(P._contar_o_manifesto(load_manifest(P.manifesto_do_executor()))[1])"`
- **A medição:** pendente — `& $PY benchmarks\editor_portoes.py --passo H0 --saida benchmarks\reports\editor\h0`.

## H2 — O editor de código nativo aguenta, com tudo ligado?

**Estado:** o léxico, o protótipo e os dois instrumentos prontos; **a sonda UIA passou**; o arnês
de desempenho (`editor_codigo.py`, 3×) espera a máquina livre (ele mede bloqueios de 16 ms).

- **Casos dourados com tudo ligado:** `tests/unit/ui/test_editor_de_codigo.py`, 72 casos, e
  `tests/unit/editor/test_lexico.py`, 71: 143 passam.
  `. .\benchmarks\editor_ambiente.ps1; Enter-AmbienteDosTestesQt; & $PY -m pytest tests/unit/ui/test_editor_de_codigo.py tests/unit/editor/test_lexico.py -q -p no:cacheprovider`
- **UIA:** o `TextPattern` do editor lido pela UI Automation do Windows, numa janela real fora da
  tela, em 50 posições sorteadas (o caractere, a linha e, numa em cinco, a seleção): **50/50 nas
  3 execuções**. A sabotagem `uia_mudo` (um `QWidget` que só pinta o texto): **0/50**, «nenhum
  elemento com TextPattern».
  `& $MED benchmarks\editor_uia.py --saida <pasta>` e `& $MED benchmarks\editor_uia.py --sabotar uia_mudo --saida <pasta>`
  (`$MED` = `.venv-medicao`, Python 3.11 com `pywinauto` 0.6.9, `comtypes` 1.4.17 e `pywin32`
  312, os downloads consentidos em 2026-09-24; o produto não o leva).
- **O Narrador confirmado por uma pessoa:** pendente (é do usuário).
- **Desempenho:** pendente — `& $PY benchmarks\editor_portoes.py --passo H2 --saida benchmarks\reports\editor\h2`.

## H3 — O contrato de marcação e a política de CSS, no papel e em fixtures

**Estado:** o contrato escrito (`docs/MARKUP_CAISSA.md`), as fixtures e o instrumento prontos.

- **Cobertura:** as 14 linhas da S4 com fixture (100 %), mais 2 combinações e a legada; o §11 do
  contrato nomeia as mesmas.
- **`CB validate`** (`..\Sigil-master\src\Resource_Files\python3lib\sigil_chess\validate.py`, com o
  `python-chess` 1.11.2 do `.venv`): **0 erro, 0 aviso em 16 fixtures** (as 14 e as 2
  combinações). Ele acusa uma FEN de lance adulterada, um diagrama que não mostra a posição do
  lance acima dele e a negativa sem `data-fen` (a sabotagem `sem_fen`).
  `& $PY benchmarks\editor_contrato.py --saida <pasta>`
- **A legada:** `legado_xhtml_builder.xhtml`, saída do exportador HTML de hoje (perfil de máquina,
  `embed_ir=False`), lida pelo `read_html_text` com o título, o parágrafo, o diagrama e a partida.
  `& $PY benchmarks\editor_contrato.py --regerar-legada`
- **O mapa de estilo:** 24 fixtures positivas (as 19 propriedades do mapa, cada uma com dois
  valores, mais a cascata, as variáveis e as classes `cb-*`) e 24 negativas (uma construção fora
  do mapa por arquivo), cada uma com o resultado esperado declarado na forma do §9 do contrato.
- **As fixtures douradas do sidecar** (spec Apêndice C), escritas pelo **crítico** (Codex,
  2026-09-24, `-s workspace-write` restrito a `tests/fixtures/editor/sidecar/`) antes de qualquer
  escritor v2, assinadas no `LEIAME.md` dele, com as escolhas onde o apêndice deixa margem. O
  gerador dele (`gerar_esperado.py`) é independente: reflexão dos campos, sem os `as_dict()`; a
  `v1_de_hoje.jsonl` sai do `write_sidecar` de hoje. Duas execuções, bytes iguais. **Congeladas
  por SHA-256** (não mudam sem mutação no §10 do roadmap):
  - `v2_completo.jsonl` `76986fa5236626fe85af161ba48394aa14cd69ff8c45917ac933ffa6ea84dc32`
  - `v1_de_hoje.jsonl` `832646aa9e422d3116a830aac980add3b8e415fa948b748423c821089657e1e1`
  - `v1_migrado_esperado.jsonl` `a9d8c21bc4b07979def510d81459b22b69fa11ba806ad169a852ae83061ac24d`
  - (a entrada) `entrada.py` `61e1e7d662db4718ff5547808ae03203224a2b18b02f6fba717fbcbcde01ca4c`

  `$env:PYTHONPATH='src'; & $PY tests\fixtures\editor\sidecar\gerar_esperado.py` (regrava as três;
  o hash tem de sair igual).
