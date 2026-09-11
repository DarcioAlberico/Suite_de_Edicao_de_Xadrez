"""Ferramentas de auditoria visual da interface (F9).

Existem para que a medição seja **reproduzível pelo crítico**, e não uma afirmação do
construtor. A carta dos agentes críticos (§6) diz que todo portão numérico é remedido por quem
julga, e que métrica que não se reproduz é reprovação -- então cada portão da F9 é um programa
que um terceiro hostil roda sem perguntar nada a ninguém:

| módulo | o que ele mede | portão |
|---|---|---|
| `contraste` | todo par de cor das duas peles, derivado da folha e da paleta | WCAG 2.1 AA |
| `teclado` | a volta do `Tab`, o nome acessível e o papel de cada controle | SPEC §10.6 |
| `quadros` | o tempo de quadro do pan e do zoom numa página de 300 DPI | >= 55 fps (p95) |
| `bloqueio` | quanto tempo cada operação segura a thread da interface | <= 16 ms |
| `progresso` | barra indeterminada com total conhecido; operação sem cancelamento | SPEC §11.3 |
| `capture` | fotografa a janela em toda aba, pele e tamanho | prova visual |
| `amostrario` | a prancha de controles, com os estados que a tela feliz não tem | prova visual |

**Dois deles rodam em qualquer venv e três precisam do tronco.** `contraste` e `progresso` são
leitura pura -- da folha de estilo, que desde a F9 mora em `ui/folha_de_estilo.py` e não importa
toolkit, e da árvore sintática do frontend --, e por isso são afirmados por teste na suíte, que
**não tem binding de Qt nenhum**. `quadros`, `bloqueio`, `teclado`, `capture` e `amostrario`
dirigem uma janela de verdade e rodam com o venv do tronco, onde o PyQt6 mora (ADR-0009); mesmo
neles, a aritmética que decide o número é pura, mora antes do primeiro `import PyQt6` e é
afirmada em `tests/unit/ui/test_medicao.py`.
"""
