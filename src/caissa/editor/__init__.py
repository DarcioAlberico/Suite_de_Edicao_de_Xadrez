"""O Editor HTML/CSS: a regra, sem toolkit (`EDITOR_HTML_CSS_SPEC.md` R1.11).

Este pacote decide — o projeto em disco, o diário, as versões, a trava, e nos passos seguintes o
perfil legível, a validação e as operações de texto. Ele **não desenha**: a pintura mora em
`caissa.ui.views.editor_html` e `caissa.ui.widgets`, e o `test_arquitetura` afirma que nenhum
módulo daqui importa binding de Qt.
"""
