"""O contador do H4 (`benchmarks/editor_dividas.py`) vê cada um dos dez sintomas, e só eles."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "benchmarks"))

import editor_dividas as dividas  # noqa: E402

KINGS = "4k3/8/8/8/8/8/8/4K3"

#: Um capítulo como o exportador de antes do H4 o escrevia, com um defeito de cada item.
CAPITULO_DE_ANTES = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>x</title></head>
<body>
<figure class="diagram" data-ir-id="D1" data-fen="{KINGS} w - - 0 1"
 data-stipulation="Pretas jogam">
<svg xmlns="http://www.w3.org/2000/svg" aria-label="Imagem da página 31 (180 × 180 pt)">
<title>Imagem da página 31 (180 × 180 pt)</title>
<rect x="0" y="0" width="40" height="40" fill="#FFFFFF"/></svg>
<figcaption><span class="caption-text">Mate em 2</span></figcaption>
</figure>
<div class="game"><p class="headers">? &#8211; ? &#183; *</p>
<p class="movetext"><span class="move" data-ir-id="M1">1.Nf3</span></p></div>
<p>1.<span class="piece r1 d1" data-ir-id="P1">&#9816;</span>f3</p>
<p>C:\\Users\\alguem\\Livro.pdf</p>
</body></html>
"""
CSS_DE_ANTES = """.r1 { font-family: FigurineCBTimes; }
.d1 { font-family: FigurineCBTimes; }
@font-face { font-family: "Chess Merida"; src: url(../Fonts/merida.woff2); }
"""


def _epub(pasta: Path, arquivos: dict[str, str]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "livro.epub"
    with zipfile.ZipFile(destino, "w") as pacote:
        for nome, texto in arquivos.items():
            pacote.writestr(nome, texto)
    return destino


def test_o_alt_reconstroi_a_posicao() -> None:
    assert dividas._placement_do_alt("Rei preto em e8; Rei branco em e1.") == KINGS
    assert dividas._placement_do_alt("Black king on e8; White king on e1.") == KINGS
    assert dividas._placement_do_alt("Peão branco em a2") == "8/8/8/8/8/8/P7/8"
    assert dividas._placement_do_alt("Imagem da página 31 (180 × 180 pt)") is None


def test_o_epub_de_antes_tem_os_dez_sintomas(tmp_path: Path) -> None:
    epub = _epub(tmp_path, {"OEBPS/Text/c1.xhtml": CAPITULO_DE_ANTES,
                            "OEBPS/Styles/props.css": CSS_DE_ANTES})
    (tmp_path / "livro.proveniencia.jsonl").write_text(
        json.dumps({"kind": "header", "version": 1}) + "\n"
        + json.dumps({"kind": "diagram", "key": "p30:d1", "id": "D1",
                      "rect": [1, 2, 3, 4]}) + "\n", encoding="utf-8")
    (tmp_path / "livro.degradacoes.json").write_text(json.dumps(
        [{"property": "diagram.verified_by_human", "node_id": "D1"}]), encoding="utf-8")
    contas, alts = dividas.contar(epub)
    assert {n: c.contagem > 0 for n, c in contas.items()} == dict.fromkeys(range(1, 11), True)
    assert alts == {"diagramas": 1, "batem": 0, "exemplos": alts["exemplos"]}


def test_o_epub_de_hoje_nao_tem_sintoma(tmp_path: Path) -> None:
    from caissa.core.chess.notation_tables import PieceType
    from caissa.core.model import Diagram, Document, Paragraph, PieceGlyph, Text
    from caissa.export import export
    from caissa.export.base import ExportOptions
    from caissa.export.provenance import sidecar_path, write_sidecar

    documento = Document(body=(
        Diagram(fen=f"{KINGS} w - - 0 1"),
        Paragraph(content=(Text(content="1."), PieceGlyph(piece=PieceType.KNIGHT,
                                                          font_family="FigurineCBTimes"),
                           Text(content="f3"))),
    ))
    destino = tmp_path / "livro.epub"
    resultado = export(documento, destino, "epub", options=ExportOptions(embed_ir=False))
    write_sidecar(documento, destino, format_name="epub")
    assert sidecar_path(destino).is_file()
    destino.with_suffix(".degradacoes.json").write_text(json.dumps(
        [{"property": w.property} for w in resultado.degradation.warnings]), encoding="utf-8")
    contas, alts = dividas.contar(destino)
    assert {n: c.contagem for n, c in contas.items() if c.contagem} == {}
    assert alts["diagramas"] == alts["batem"] == 1


def test_so_um_sintoma(tmp_path: Path) -> None:
    epub = _epub(tmp_path, {"OEBPS/Text/c1.xhtml": CAPITULO_DE_ANTES})
    contas, _ = dividas.contar(epub, so=3)
    assert list(contas) == [3]
    assert contas[3].contagem == 1
