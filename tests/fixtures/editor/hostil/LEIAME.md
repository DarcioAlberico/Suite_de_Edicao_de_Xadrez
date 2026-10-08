# O livro hostil (Editor HTML/CSS, H1, tarefa 4)

Uma página por vetor: o script, o manipulador de evento, o link `javascript:`, as imagens de fora
(http e https), o CSS de fora (`@import`, `url()` e `@font-face`), o iframe, o meta refresh, o SVG
com script (no texto, por `<img>` e por `<object>`) e os arquivos fora do livro (o caminho do
Windows, `file:`, `../../` até a sentinela e o `file:` dela). Todo endereço de fora é `127.0.0.1:{PORTA}`, o
servidor que o `benchmarks/editor_motores.py --hostil` abre só para contar o que chega nele: nada
sai da máquina. `{FORA}` é o `file:` da sentinela, um PNG fora da pasta do livro. Os scripts marcam
`data-hostil` na raiz do documento; o portão exige 0 marcas, 0 requisições e 0 arquivos de fora
nos dois motores.
