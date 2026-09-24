# Fixtures douradas do sidecar de proveniência v2

Estas fixtures são a entrega do H3, escritas pelo crítico independente antes
do escritor v2. Todos os artefatos ficam nesta pasta e usam UTF-8.

## Arquivos

- `entrada.py`: constrói o `Document` real e o dicionário de entrada do futuro
  escritor. `entrada_v1()` devolve a mesma árvore para o exportador atual, com
  o `DiagramSource.rect` como tupla.
- `gerar_esperado.py`: gerador independente. Usa `dataclasses.fields` e
  `registry.tag_for_class` para o serializador canônico; não importa escritor
  v2 e não chama `as_dict()` das classes de revisão.
- `v2_completo.jsonl`: saída v2 esperada para `entrada()`.
- `v1_de_hoje.jsonl`: bytes produzidos por
  `caissa.export.provenance.write_sidecar` sobre `entrada_v1()`.
- `v1_migrado_esperado.jsonl`: saída v2 esperada da migração independente da
  v1, conforme a tabela campo a campo do Apêndice C.

## Como gerar

Com o PowerShell no diretório do repositório:

```powershell
$env:PYTHONPATH='C:\Python-Chess2\_editor_h0\src'
$env:PYTHONDONTWRITEBYTECODE='1'
$py='C:\Python-Chess2\Suite_de_Edicao_de_Xadrez\.venv\Scripts\python.exe'
& $py 'C:\Python-Chess2\_editor_h0\tests\fixtures\editor\sidecar\gerar_esperado.py'
```

O gerador chama o exportador v1 real. Para tornar a fixture repetível, injeta
temporariamente no módulo do exportador `gerado_em =
2026-01-01T00:00:00+00:00` e `commit_da_suite = fixture`, exatamente como
permite o Apêndice C; nenhum código do produto é alterado. O alvo v1 é o nome
relativo `Livro.epub`, logo a linha v1 também não introduz um caminho absoluto.

## Escolhas onde a especificação deixa margem

1. A entrada foi congelada com as chaves `documento`, `cabecalho`, `blocos`,
   `diagramas`, `partidas`, `gerado_em` e `commit_da_suite`. Os três mapas usam
   `str(ir_id)` como chave; isso mantém as decisões fora do `Document`, como
   exige o contrato. O `documento.caminho` é uma `Path` relativa para exercer a
   regra “`Path` como texto” sem violar R2.4.
2. A ordem dos registros v2 é a pré-ordem de
   `caissa.core.model.visitor.walk`: bloco, diagrama, bloco, partida. Isso é a
   leitura mais estrita de “depois blocos, diagramas e partidas em ordem de
   leitura” quando os três tipos estão intercalados no `Document`. O parágrafo
   autoral sem `Provenance` não gera registro, conforme o Apêndice C: “Os nós
   sem proveniência ... não têm registro”.
3. Os IDs públicos usam página base 1 (`p5-1`, `p5-d1`, `p7-g1`), enquanto
   `pagina0` e `chave_v1` permanecem base 0. A escolha segue R2.7 (“na
   interface e nos `id` ... página ... base 1”) e a tabela de migração do
   Apêndice C (`p<k+1>-d<n>` e `p<k+1>-g<n>`).
4. O `kind` dos registros v1 foi colocado em `extras_v1`, porque a tabela de
   migração nomeia os campos de dados e não nomeia essa chave. É a leitura
   estrita de “toda chave da v1 que a tabela não nomeia vai para
   `extras_v1`”; assim nem o discriminador é perdido. No v2 nativo,
   `extras_v1` é sempre `{}`.
5. Na migração, uma lista v1 de quatro números vira `rect` com `unit: "pt"`,
   exatamente a regra do Apêndice C. Um objeto v1 conserva sua unidade; a
   fixture demonstra as duas formas: a fonte sai como lista porque veio da
   tupla do teste atual, enquanto a proveniência sai como objeto porque o
   exportador v1 corrigido reconhece o `Rect` real.
6. Campos que o exportador v1 não gravou viram `null`, salvo defaults
   estruturais: `RecognitionResult.corners` vira `[]` e
   `Provenance.out_of_model` vira `false`. O `per_square_confidence` permanece
   com o arredondamento de quatro casas que a v1 já gravou, sem reconstruir a
   precisão original.
7. O esquema segue o código atual, não a tabela histórica, e a ordem de cada
   lista é a de `dataclasses.fields`. Neste checkout não há divergência de
   campos entre o Apêndice C e as dez classes introspectadas em
   `2026-09-24`; o cabeçalho, portanto, materializa os campos atuais.

## Verificações e hashes

O gerador foi executado duas vezes; os quatro hashes correspondentes (e os
três JSONL) foram idênticos byte a byte. SHA-256:

```text
entrada.py                 61E1E7D662DB4718FF5547808AE03203224A2B18B02F6FBA717FBCBCDE01CA4C
v2_completo.jsonl          76986FA5236626FE85AF161BA48394AA14CD69FF8C45917AC933FFA6EA84DC32
v1_de_hoje.jsonl           832646AA9E422D3116A830AAC980ADD3B8E415FA948B748423C821089657E1E1
v1_migrado_esperado.jsonl  A9D8C21BC4B07979DEF510D81459B22B69FA11BA806AD169A852AE83061AC24D
```

Assinatura: **escrito pelo crítico (Codex), fixtures douradas do H3,
2026-09-24**.
