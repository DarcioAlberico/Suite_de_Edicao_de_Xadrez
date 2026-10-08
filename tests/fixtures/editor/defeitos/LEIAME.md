# Os defeitos do validador (Editor HTML/CSS, H10)

Um arquivo por regra (`Text/<código>.xhtml`, e o `Styles/css-mapa-docx.css`), cada um com o
defeito da regra e nenhum outro — e, para as regras que o crítico pediu mais (o contraste com
qualquer CSS, a imagem animada em toda fonte, a page-list), um arquivo por caso
(`Text/<código>-<caso>.xhtml`); `esperado.json` diz o código e a linha:coluna que o
validador tem de dar — tirados de um marcador no texto (o `<` do elemento, o nome da
declaração, o caractere), pela definição da regra, e não do validador. Os de apoio: as
imagens (`Images/`), as folhas ligadas (`Styles/cinza.css`, `Styles/fonte.css`, e a
cadeia de `@import` `Styles/importa-1.css` … `importa-6.css`, a cor só na última), os mapas
da proveniência (`Text/*.proveniencia.json`) e os marcadores de página que as page-list
apontam (`Text/apoio-paginas.xhtml`). O `seg-tamanho` (8 MB) o portão monta.
Regerar: `python tests/fixtures/editor/defeitos/gerar_defeitos.py` — o mesmo resultado, byte
a byte (os `ir_id` dos mapas são fixos); o teste `test_as_fixtures_sao_do_gerador` confere.
