# Os defeitos do validador (Editor HTML/CSS, H10)

Um arquivo por regra (`Text/<código>.xhtml`, e o `Styles/css-mapa-docx.css`), cada um com o
defeito da regra e nenhum outro; `esperado.json` diz o código e a linha:coluna que o
validador tem de dar — tirados de um marcador no texto (o `<` do elemento, o nome da
declaração, o caractere), pela definição da regra, e não do validador. Os de apoio: as
imagens (`Images/`), as folhas ligadas (`Styles/cinza.css`, `Styles/fonte.css`) e os mapas
da proveniência (`Text/*.proveniencia.json`). O `seg-tamanho` (8 MB) o portão monta.
Regerar: `python tests/fixtures/editor/defeitos/gerar_defeitos.py` (o mesmo resultado; os
`ir_id` dos mapas saem novos a cada vez).
