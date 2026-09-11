"""The EMF writer, checked against the format rather than against itself.

Every assertion here walks the emitted record stream with `struct` and reads the
fields a consumer reads. That is deliberate: a test that only round-trips through
`caissa.export.emf` would pass just as happily on a file Word refuses to open.

The load-bearing test is `test_board_has_no_bitmap_records`. SPEC 8.2 asks for a
*vector* diagram; the way that requirement silently fails is a writer that wraps a
rasterised board in a metafile, and the only honest proof it did not is the absence of
EMR_BITBLT / EMR_STRETCHDIBITS / EMR_SETDIBITSTODEVICE from the stream.

On Windows there is a second, stronger proof: `test_windows_gdi_accepts_the_file`
hands the bytes to gdi32 and plays them into a memory DC. Nothing in this file mocks
that -- either the operating system parses and draws the metafile or the test fails.
"""

from __future__ import annotations

import functools
import struct
import sys
import warnings

import pytest

from caissa.export.emf import EMU_PER_MM, EmfError, EmfImage, svg_to_emf, svg_to_png

# --------------------------------------------------------------------------- #
# Record types, spelled out so a failure names the record
# --------------------------------------------------------------------------- #
EMR_HEADER = 1
EMR_EOF = 14
EMR_SELECTOBJECT = 37
EMR_CREATEBRUSHINDIRECT = 39
EMR_GDICOMMENT = 70
EMR_BITBLT = 76
EMR_STRETCHBLT = 77
EMR_SETDIBITSTODEVICE = 80
EMR_STRETCHDIBITS = 81
EMR_BEGINPATH = 59
EMR_ENDPATH = 60
EMR_EXTTEXTOUTW = 84
EMR_EXTCREATEPEN = 95

BITMAP_RECORDS = (EMR_BITBLT, EMR_STRETCHBLT, EMR_SETDIBITSTODEVICE, EMR_STRETCHDIBITS)
SIGNATURE = 0x464D4520
STOCK_OBJECT_BIT = 0x80000000

RED_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
    'viewBox="0 0 10 10"><rect x="0" y="0" width="10" height="10" fill="#FF0000"/></svg>'
)


# --------------------------------------------------------------------------- #
# A minimal EMF reader
# --------------------------------------------------------------------------- #
class Record:
    """One record from the stream: its type, its declared size and its raw bytes."""

    def __init__(self, itype: int, nsize: int, raw: bytes, offset: int) -> None:
        self.itype = itype
        self.nsize = nsize
        self.raw = raw
        self.offset = offset

    def u32(self, at: int) -> int:
        """Unsigned 32-bit field at `at` bytes from the start of the record."""
        return struct.unpack_from("<I", self.raw, at)[0]

    def i32(self, at: int) -> int:
        return struct.unpack_from("<i", self.raw, at)[0]


def walk(data: bytes) -> list[Record]:
    """Walk the record stream, asserting the structural invariants as it goes.

    Every record must declare a size that is at least 8, a multiple of 4, and within
    the file; the walk must land exactly on the end of the file.
    """
    records: list[Record] = []
    offset = 0
    while offset < len(data):
        assert len(data) - offset >= 8, f"registro truncado em {offset}"
        itype, nsize = struct.unpack_from("<II", data, offset)
        assert nsize >= 8, f"registro {itype} em {offset} declara nSize={nsize}"
        assert nsize % 4 == 0, f"registro {itype} em {offset} tem nSize={nsize}, nao multiplo de 4"
        assert offset + nsize <= len(data), f"registro {itype} em {offset} passa do fim do arquivo"
        records.append(Record(itype, nsize, data[offset : offset + nsize], offset))
        offset += nsize
    assert offset == len(data), "a caminhada nao consumiu o arquivo exatamente"
    return records


class Header:
    """The fields of EMR_HEADER a consumer actually reads."""

    def __init__(self, data: bytes) -> None:
        self.rcl_bounds = struct.unpack_from("<4i", data, 8)
        self.rcl_frame = struct.unpack_from("<4i", data, 24)
        (self.signature, self.version, self.n_bytes, self.n_records) = struct.unpack_from(
            "<4I", data, 40
        )
        self.n_handles = struct.unpack_from("<H", data, 56)[0]
        self.n_description = struct.unpack_from("<I", data, 60)[0]
        self.off_description = struct.unpack_from("<I", data, 64)[0]
        self.szl_device = struct.unpack_from("<2i", data, 72)
        self.szl_millimeters = struct.unpack_from("<2i", data, 80)

    @property
    def frame_width(self) -> int:
        """Frame width in 0.01 mm. rclFrame is inclusive-inclusive, hence the +1."""
        return self.rcl_frame[2] - self.rcl_frame[0] + 1

    @property
    def frame_height(self) -> int:
        return self.rcl_frame[3] - self.rcl_frame[1] + 1


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@functools.cache
def board_svg(width_mm: float = 90.0) -> str:
    """A real board SVG, marks and all, rendered by the canonical renderer."""
    from caissa.typeset.board_svg import (
        Arrow,
        CircleMark,
        DiagramStyle,
        FrameStyle,
        SideToMove,
        SquareHighlight,
        render_svg,
    )
    from caissa.typeset.fonts import FontNotFoundError

    with warnings.catch_warnings():
        # Several legacy chess fonts carry a head.created outside fontTools' range and
        # warn on every open. The project turns warnings into errors, which is right,
        # so the two known-benign ones are filtered by message -- exactly as
        # tests/unit/typeset/conftest.py does -- rather than blanket-ignored.
        warnings.filterwarnings("ignore", message=r".*timestamp.*out of range.*")
        warnings.filterwarnings("ignore", message=r".*timestamp seems very low.*")
        style = DiagramStyle(
            width_mm=width_mm,
            grid=True,
            frame=FrameStyle.SHADOWED,
            side_to_move=SideToMove.DOT,
        )
        marks = [
            SquareHighlight("e4", opacity=0.35),
            CircleMark("f7"),
            Arrow("g1", "f3"),
            Arrow("c4", "f7", opacity=0.6),
        ]
        try:
            return render_svg(
                "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                style,
                marks=marks,
            )
        except FontNotFoundError as exc:
            pytest.skip(f"Nenhuma fonte de xadrez instalada nesta maquina: {exc}")


@pytest.fixture(scope="module")
def board() -> EmfImage:
    return svg_to_emf(board_svg())


@pytest.fixture(scope="module")
def board_records(board: EmfImage) -> list[Record]:
    return walk(board.data)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_first_record_is_the_header_and_declares_the_file_size(board):
    records = walk(board.data)
    assert records[0].itype == EMR_HEADER
    header = Header(board.data)
    assert header.n_bytes == len(board.data)


def test_signature_and_version(board):
    header = Header(board.data)
    assert header.signature == SIGNATURE, "dSignature deve ser ' EMF'"
    assert header.version == 0x00010000


def test_record_count_matches_the_walk_and_the_last_record_is_eof(board, board_records):
    header = Header(board.data)
    assert header.n_records == len(board_records)
    assert board_records[-1].itype == EMR_EOF


def test_eof_record_self_reference(board_records):
    eof = board_records[-1]
    assert eof.itype == EMR_EOF
    assert eof.nsize == 20
    # nPalEntries, offPalEntries, nSizeLast
    assert eof.u32(8) == 0
    assert eof.u32(16) == eof.nsize, "nSizeLast deve repetir o nSize do proprio EMR_EOF"


def test_every_record_size_is_a_multiple_of_four_and_the_walk_is_exact(board_records, board):
    # `walk` asserts both invariants; this test states them so a failure is legible.
    assert sum(r.nsize for r in board_records) == len(board.data)
    assert all(r.nsize % 4 == 0 for r in board_records)


def test_header_declares_a_consistent_reference_device(board):
    header = Header(board.data)
    # The drawing grid is 0.01 mm, so the declared device resolution must be
    # 100 units per mm or a reader computing scale from the header disagrees with
    # a reader computing it from rclFrame.
    assert header.szl_device[0] == header.szl_millimeters[0] * 100
    assert header.szl_device[1] == header.szl_millimeters[1] * 100
    assert header.rcl_bounds == header.rcl_frame


def test_description_offset_lands_inside_the_header(board, board_records):
    header = Header(board.data)
    assert header.n_description > 0
    end = header.off_description + header.n_description * 2
    assert header.off_description >= 88
    assert end <= board_records[0].nsize


# --------------------------------------------------------------------------- #
# Handle table
# --------------------------------------------------------------------------- #
def test_handle_table_covers_every_selected_object(board, board_records):
    header = Header(board.data)
    used = [
        r.u32(8)
        for r in board_records
        if r.itype == EMR_SELECTOBJECT and not r.u32(8) & STOCK_OBJECT_BIT
    ]
    assert used, "o tabuleiro precisa selecionar ao menos um objeto"
    assert min(used) >= 1, "o indice 0 da tabela de handles e reservado"
    assert header.n_handles > max(used)


def test_objects_are_reused_not_recreated_per_square(board_records):
    # 64 squares in two colours. A writer that creates a brush per rect would emit
    # dozens of EMR_CREATEBRUSHINDIRECT records and a bloated handle table.
    brushes = [r for r in board_records if r.itype == EMR_CREATEBRUSHINDIRECT]
    assert len(brushes) < 20, f"{len(brushes)} pinceis criados; as cores nao estao sendo reusadas"


# --------------------------------------------------------------------------- #
# Vector, not raster -- the SPEC 8.2 requirement
# --------------------------------------------------------------------------- #
def test_board_pieces_are_real_paths(board_records):
    begins = sum(1 for r in board_records if r.itype == EMR_BEGINPATH)
    ends = sum(1 for r in board_records if r.itype == EMR_ENDPATH)
    assert begins >= 1, "nenhum EMR_BEGINPATH: as pecas nao sairam como caminhos"
    assert begins == ends, "cada EMR_BEGINPATH precisa de um EMR_ENDPATH"


def test_board_has_no_bitmap_records(board_records):
    found = sorted({r.itype for r in board_records if r.itype in BITMAP_RECORDS})
    assert not found, f"registros de bitmap encontrados: {found}; o EMF nao e vetorial"


def test_board_is_not_emf_plus(board_records):
    # EMF+ smuggles its records inside EMR_GDICOMMENT. Word reads plain EMF everywhere;
    # EMF+ needs GDI+ and is exactly the sort of thing that renders on one machine only.
    assert not [r for r in board_records if r.itype == EMR_GDICOMMENT]


def test_board_file_is_small(board):
    assert len(board.data) < 400 * 1024, f"{len(board.data)} bytes"


def test_board_carries_text_records(board_records):
    assert sum(1 for r in board_records if r.itype == EMR_EXTTEXTOUTW) == 16, (
        "8 letras de coluna e 8 numeros de linha"
    )


# --------------------------------------------------------------------------- #
# Colour
# --------------------------------------------------------------------------- #
def test_colorref_byte_order_is_bbggrr():
    image = svg_to_emf(RED_SVG)
    brushes = [r for r in walk(image.data) if r.itype == EMR_CREATEBRUSHINDIRECT]
    assert len(brushes) == 1
    # EMR_CREATEBRUSHINDIRECT: ihBrush(8) BrushStyle(12) ColorRef(16) BrushHatch(20)
    assert brushes[0].u32(16) == 0x000000FF, "vermelho puro deve ser 0x000000FF, nao 0x00FF0000"


def test_colorref_is_not_symmetric():
    blue = svg_to_emf(RED_SVG.replace("#FF0000", "#0000FF"))
    brushes = [r for r in walk(blue.data) if r.itype == EMR_CREATEBRUSHINDIRECT]
    assert brushes[0].u32(16) == 0x00FF0000


def test_pen_colour_uses_the_same_order():
    stroked = RED_SVG.replace('fill="#FF0000"', 'fill="none" stroke="#FF0000" stroke-width="1"')
    pens = [r for r in walk(svg_to_emf(stroked).data) if r.itype == EMR_EXTCREATEPEN]
    assert len(pens) == 1
    # EMR_EXTCREATEPEN: ...cbBits(24) PenStyle(28) Width(32) BrushStyle(36) ColorRef(40)
    assert pens[0].u32(40) == 0x000000FF


# --------------------------------------------------------------------------- #
# Size and scaling
# --------------------------------------------------------------------------- #
def test_frame_records_the_intrinsic_size(board):
    header = Header(board.data)
    assert abs(header.frame_width - round(board.width_mm * 100)) <= 1
    assert abs(header.frame_height - round(board.height_mm * 100)) <= 1


def test_width_override_scales_the_frame_and_keeps_the_aspect_ratio():
    svg = board_svg()
    natural = svg_to_emf(svg)
    wide = svg_to_emf(svg, width_mm=90.0)

    header = Header(wide.data)
    assert abs(header.frame_width - 9000) <= 1, "90 mm sao 9000 unidades de 0.01 mm"
    assert abs(wide.width_mm - 90.0) < 1e-9

    natural_aspect = natural.height_mm / natural.width_mm
    wide_aspect = wide.height_mm / wide.width_mm
    assert abs(wide_aspect - natural_aspect) < 1e-6
    assert abs(header.frame_height / header.frame_width - natural_aspect) < 1e-3


def test_width_override_scales_the_bounds_too():
    small = svg_to_emf(board_svg(), width_mm=30.0)
    header = Header(small.data)
    assert abs(header.frame_width - 3000) <= 1
    assert header.rcl_bounds == header.rcl_frame


def test_emu_conversion():
    image = svg_to_emf(RED_SVG, width_mm=25.4)
    assert image.width_emu == round(25.4 * EMU_PER_MM)
    assert image.height_emu == round(image.height_mm * EMU_PER_MM)
    assert EMU_PER_MM == 36000


def test_a_smaller_width_makes_a_smaller_frame_but_the_same_records():
    a = svg_to_emf(board_svg(), width_mm=40.0)
    b = svg_to_emf(board_svg(), width_mm=90.0)
    assert Header(a.data).n_records == Header(b.data).n_records
    assert Header(a.data).frame_width < Header(b.data).frame_width


# --------------------------------------------------------------------------- #
# Orientation -- a flipped board is the classic EMF mistake
# --------------------------------------------------------------------------- #
def test_window_and_viewport_extents_are_both_positive(board_records):
    ext = {9: None, 11: None}  # EMR_SETWINDOWEXTEX, EMR_SETVIEWPORTEXTEX
    for record in board_records:
        if record.itype in ext:
            ext[record.itype] = (record.i32(8), record.i32(12))
    assert ext[9] is not None, "faltou EMR_SETWINDOWEXTEX"
    assert ext[11] is not None, "faltou EMR_SETVIEWPORTEXTEX"
    assert ext[9] == ext[11], "janela e viewport iguais mantem 1 unidade logica = 1 de dispositivo"
    assert all(v > 0 for v in ext[9]), "extensao negativa inverteria o tabuleiro no eixo y"


def test_the_first_square_is_drawn_above_the_last():
    # a8 is drawn before a1 and must have the smaller y. If the writer flipped the
    # axis this ordering would invert and the board would come out upside down.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
        'viewBox="0 0 20 20">'
        '<rect x="0" y="0" width="5" height="5" fill="#111111"/>'
        '<rect x="0" y="15" width="5" height="5" fill="#222222"/></svg>'
    )
    rects = [r for r in walk(svg_to_emf(svg).data) if r.itype == 43]  # EMR_RECTANGLE
    assert len(rects) == 2
    assert rects[0].i32(12) < rects[1].i32(12), "o topo do SVG deve ficar no topo do EMF"


# --------------------------------------------------------------------------- #
# Opacity notes
# --------------------------------------------------------------------------- #
def test_transparency_is_reported_not_swallowed():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        'viewBox="0 0 10 10">'
        '<rect x="0" y="0" width="5" height="5" fill="#FF0000" opacity="0.5"/>'
        '<rect x="5" y="0" width="5" height="5" fill="#00FF00" opacity="0.25"/></svg>'
    )
    image = svg_to_emf(svg)
    assert len(image.notes) == 1
    note = image.notes[0]
    assert "2 elemento(s)" in note
    assert "canal alfa" in note


def test_transparency_is_blended_towards_white():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        'viewBox="0 0 10 10">'
        '<rect x="0" y="0" width="10" height="10" fill="#000000" opacity="0.5"/></svg>'
    )
    brushes = [r for r in walk(svg_to_emf(svg).data) if r.itype == EMR_CREATEBRUSHINDIRECT]
    # black at 50 % over white is mid grey in all three channels.
    assert brushes[0].u32(16) == 0x00808080


def test_an_opaque_diagram_has_no_notes():
    assert svg_to_emf(RED_SVG).notes == ()


def test_group_opacity_is_inherited():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        'viewBox="0 0 10 10"><g opacity="0.5">'
        '<rect x="0" y="0" width="10" height="10" fill="#000000"/></g></svg>'
    )
    image = svg_to_emf(svg)
    brushes = [r for r in walk(image.data) if r.itype == EMR_CREATEBRUSHINDIRECT]
    assert brushes[0].u32(16) == 0x00808080
    assert len(image.notes) == 1
    assert "1 elemento(s)" in image.notes[0]


def test_group_transform_is_applied():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
        'viewBox="0 0 20 20"><g transform="translate(5,5)">'
        '<rect x="0" y="0" width="5" height="5" fill="#000000"/></g></svg>'
    )
    rects = [r for r in walk(svg_to_emf(svg).data) if r.itype == 43]
    assert rects[0].i32(8) == 500, "5 mm sao 500 unidades de 0.01 mm"
    assert rects[0].i32(12) == 500


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #
def test_garbage_is_rejected_with_a_portuguese_message():
    with pytest.raises(EmfError, match="SVG invalido"):
        svg_to_emf("nao e svg <<<")


def test_a_zero_sized_viewbox_is_rejected():
    with pytest.raises(EmfError, match="dimensoes"):
        svg_to_emf(
            '<svg xmlns="http://www.w3.org/2000/svg" width="0mm" height="0mm" '
            'viewBox="0 0 0 0"/>'
        )


def test_an_empty_svg_still_produces_a_valid_metafile():
    image = svg_to_emf(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10"/>'
    )
    records = walk(image.data)
    assert records[0].itype == EMR_HEADER
    assert records[-1].itype == EMR_EOF
    assert Header(image.data).n_bytes == len(image.data)


# --------------------------------------------------------------------------- #
# PNG fallback
# --------------------------------------------------------------------------- #
def test_png_fallback_is_a_png():
    pytest.importorskip("pymupdf")
    data = svg_to_png(board_svg(), dpi=150)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# The real thing: hand the bytes to Windows
# --------------------------------------------------------------------------- #
def gdi_play(data: bytes, width: int, height: int):
    """Load an EMF into gdi32, read its header back and play it into a memory DC.

    Nothing here is mocked. `SetEnhMetaFileBits` validates the record stream,
    `GetEnhMetaFileHeader` reports what the OS understood, and `PlayEnhMetaFile`
    executes every record into a 32-bit top-down DIB.

    The surface is primed magenta before playing, so a pixel that is still magenta
    afterwards is a pixel GDI never drew.

    Returns:
        The native ENHMETAHEADER and the BGRA pixels, row 0 being the top.
    """
    import ctypes
    from ctypes import wintypes

    class RECTL(ctypes.Structure):
        _fields_ = [(n, wintypes.LONG) for n in ("left", "top", "right", "bottom")]

    class SIZEL(ctypes.Structure):
        _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

    class ENHMETAHEADER(ctypes.Structure):
        _fields_ = [
            ("iType", wintypes.DWORD), ("nSize", wintypes.DWORD),
            ("rclBounds", RECTL), ("rclFrame", RECTL),
            ("dSignature", wintypes.DWORD), ("nVersion", wintypes.DWORD),
            ("nBytes", wintypes.DWORD), ("nRecords", wintypes.DWORD),
            ("nHandles", wintypes.WORD), ("sReserved", wintypes.WORD),
            ("nDescription", wintypes.DWORD), ("offDescription", wintypes.DWORD),
            ("nPalEntries", wintypes.DWORD),
            ("szlDevice", SIZEL), ("szlMillimeters", SIZEL),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    void, dword, uint = ctypes.c_void_p, wintypes.DWORD, wintypes.UINT
    hdc_t, handle_t, obj_t = wintypes.HDC, wintypes.HANDLE, wintypes.HGDIOBJ
    for name, restype, argtypes in (
        ("SetEnhMetaFileBits", handle_t, [uint, ctypes.c_char_p]),
        ("GetEnhMetaFileHeader", uint, [handle_t, uint, void]),
        ("DeleteEnhMetaFile", wintypes.BOOL, [handle_t]),
        ("CreateCompatibleDC", hdc_t, [hdc_t]),
        ("DeleteDC", wintypes.BOOL, [hdc_t]),
        ("CreateDIBSection", wintypes.HBITMAP, [hdc_t, void, uint, void, handle_t, dword]),
        ("SelectObject", obj_t, [hdc_t, obj_t]),
        ("DeleteObject", wintypes.BOOL, [obj_t]),
        ("PlayEnhMetaFile", wintypes.BOOL, [hdc_t, handle_t, void]),
    ):
        getattr(gdi32, name).restype = restype
        getattr(gdi32, name).argtypes = argtypes

    emf = gdi32.SetEnhMetaFileBits(len(data), data)
    assert emf, f"gdi32 rejeitou o metafile (erro {ctypes.get_last_error()})"
    try:
        native = ENHMETAHEADER()
        assert gdi32.GetEnhMetaFileHeader(emf, ctypes.sizeof(native), ctypes.byref(native)), (
            "GetEnhMetaFileHeader falhou"
        )
        info = BITMAPINFOHEADER()
        info.biSize = ctypes.sizeof(info)
        info.biWidth = width
        info.biHeight = -height  # top-down, so row 0 is the top of the diagram
        info.biPlanes = 1
        info.biBitCount = 32
        hdc = gdi32.CreateCompatibleDC(None)
        assert hdc, "CreateCompatibleDC falhou"
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        assert bitmap, "CreateDIBSection falhou"
        try:
            gdi32.SelectObject(hdc, bitmap)
            surface = (ctypes.c_ubyte * (width * height * 4)).from_address(bits.value)
            for i in range(0, len(surface), 4):
                surface[i] = 0xFF      # blue
                surface[i + 1] = 0x00  # green
                surface[i + 2] = 0xFF  # red
            box = RECTL(0, 0, width, height)
            assert gdi32.PlayEnhMetaFile(hdc, emf, ctypes.byref(box)), (
                f"PlayEnhMetaFile falhou (erro {ctypes.get_last_error()})"
            )
            return native, bytes(surface)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(hdc)
    finally:
        gdi32.DeleteEnhMetaFile(emf)


def rgb_at(pixels: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    """Read one pixel out of the BGRA surface `gdi_play` returns."""
    off = (y * width + x) * 4
    return (pixels[off + 2], pixels[off + 1], pixels[off])


MAGENTA = (255, 0, 255)


@pytest.mark.skipif(sys.platform != "win32", reason="gdi32 so existe no Windows")
def test_windows_gdi_accepts_the_file(board):
    """The operating system parses the metafile and agrees with its header."""
    native, _ = gdi_play(board.data, 64, 64)
    assert native.iType == EMR_HEADER
    assert native.dSignature == SIGNATURE
    assert native.nBytes == len(board.data)
    assert native.nRecords == len(walk(board.data))
    assert native.nHandles > 1
    frame = native.rclFrame.right - native.rclFrame.left + 1
    assert abs(frame - round(board.width_mm * 100)) <= 1


@pytest.mark.skipif(sys.platform != "win32", reason="gdi32 so existe no Windows")
def test_windows_gdi_draws_the_whole_board(board):
    """Every record executes: GDI covers the frame and puts more than two inks on it.

    A malformed record size, a handle index outside the table or an unbalanced path
    bracket makes PlayEnhMetaFile bail out partway, leaving primed pixels behind.
    """
    width = height = 300
    _, pixels = gdi_play(board.data, width, height)
    untouched = sum(
        1
        for y in range(height)
        for x in range(width)
        if rgb_at(pixels, width, x, y) == MAGENTA
    )
    assert untouched == 0, f"{untouched} pixels nao foram desenhados"
    inks = {rgb_at(pixels, width, x, y) for y in range(0, height, 3) for x in range(0, width, 3)}
    assert len(inks) > 2, "o tabuleiro precisa de mais de duas cores no papel"


@pytest.mark.skipif(sys.platform != "win32", reason="gdi32 so existe no Windows")
def test_windows_gdi_draws_red_as_red():
    """The COLORREF byte order, proven through the OS rather than merely asserted.

    A writer that packs 0x00RRGGBB passes every structural test in this file and then
    hands Word a blue chess board.
    """
    _, red = gdi_play(svg_to_emf(RED_SVG).data, 64, 64)
    assert rgb_at(red, 64, 32, 32) == (255, 0, 0)
    _, blue = gdi_play(svg_to_emf(RED_SVG.replace("#FF0000", "#0000FF")).data, 64, 64)
    assert rgb_at(blue, 64, 32, 32) == (0, 0, 255)


@pytest.mark.skipif(sys.platform != "win32", reason="gdi32 so existe no Windows")
def test_windows_gdi_keeps_the_board_the_right_way_up():
    """The top of the SVG lands at the top. A sign error in the extents flips it."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
        'viewBox="0 0 20 20">'
        '<rect x="0" y="0" width="20" height="10" fill="#FF0000"/>'
        '<rect x="0" y="10" width="20" height="10" fill="#0000FF"/></svg>'
    )
    _, pixels = gdi_play(svg_to_emf(svg).data, 64, 64)
    assert rgb_at(pixels, 64, 32, 8) == (255, 0, 0), "a metade de cima do SVG deve ficar em cima"
    assert rgb_at(pixels, 64, 32, 56) == (0, 0, 255)
