"""Sol §SOL-7: Tesseract profiles for prose and movetext, and the two detectors."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from caissa.ocr.engines.profiles import (
    MOVE_PATTERNS,
    ProfileConfig,
    ProfileFiles,
    TesseractProfile,
    profile_for,
)
from caissa.ocr.engines.tesseract import TesseractConfig, TesseractEngine
from caissa.ocr.language import (
    detect_notation_convention,
    detect_prose_language,
    document_language,
)
from caissa.ocr.types import RegionKind

from .conftest import ENGLISH_BODY, PORTUGUESE_BODY, requires_font, requires_tesseract

# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


def test_profile_follows_the_region_kind():
    assert profile_for(RegionKind.MOVETEXT) is TesseractProfile.MOVETEXT
    for kind in (RegionKind.PARAGRAPH, RegionKind.HEADING, RegionKind.PAGE, RegionKind.TABLE):
        assert profile_for(kind) is TesseractProfile.PROSE


def test_profile_files_are_written_once_and_say_the_right_things(tmp_path: Path):
    files = ProfileFiles(ProfileConfig(), directory=tmp_path)
    prose = files.parameters(TesseractProfile.PROSE, "por")
    again = files.parameters(TesseractProfile.PROSE, "por")
    assert prose == again
    assert "load_system_dawg" not in prose          # prose keeps the DAWGs
    words = Path(prose["user_words_file"]).read_text("utf-8").split()
    assert "Capablanca" in words and "xeque" in words
    patterns = Path(prose["user_patterns_file"]).read_text("utf-8").splitlines()
    assert set(patterns) == set(MOVE_PATTERNS)

    movetext = files.parameters(TesseractProfile.MOVETEXT, "por")
    assert movetext["load_system_dawg"] == "0" and movetext["load_freq_dawg"] == "0"
    assert "tessedit_char_whitelist" not in movetext   # comments and NAGs stay readable
    strict = files.parameters(TesseractProfile.MOVETEXT_STRICT, "por")
    assert "tessedit_char_whitelist" in strict
    assert "x" in strict["tessedit_char_whitelist"] and "+" in strict["tessedit_char_whitelist"]

    kept = ProfileFiles(ProfileConfig(disable_dawgs_for_movetext=False), directory=tmp_path)
    assert "load_system_dawg" not in kept.parameters(TesseractProfile.MOVETEXT, "eng")


def test_the_command_carries_the_profile_and_can_be_switched_off(tmp_path: Path):
    engine = TesseractEngine(TesseractConfig(binary="tesseract"))
    engine._binary = "tesseract"
    engine._profile_files.directory = tmp_path
    cmd = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=6,
                                profile=TesseractProfile.MOVETEXT)
    joined = " ".join(cmd)
    assert "user_patterns_file=" in joined and "load_system_dawg=0" in joined
    plain = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=6)
    assert "user_patterns_file=" not in " ".join(plain)


@requires_tesseract
@requires_font
def test_the_movetext_profile_reads_a_move_list_at_least_as_well_as_the_plain_one():
    from PIL import Image, ImageDraw, ImageFont

    from caissa.ocr.metrics import move_accounting

    from .conftest import FONT_PATH

    text = ("1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Be3 e5 7.Nb3 Be6 "
            "8.f3 Be7 9.Qd2 O-O 10.O-O-O Nbd7 11.g4 b5 12.g5 b4 13.Ne2 Ne8")
    image = Image.new("L", (1500, 260), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, 36)
    draw.text((40, 40), text[:70], font=font, fill=0)
    draw.text((40, 120), text[70:], font=font, fill=0)
    gray = np.array(image)
    plain = TesseractEngine(TesseractConfig(use_profiles=False)).recognize(
        gray, lang="eng", psm_hint=RegionKind.MOVETEXT)
    profiled = TesseractEngine().recognize(gray, lang="eng", psm_hint=RegionKind.MOVETEXT)
    assert profiled.meta["profile"] == "movetext"
    before = move_accounting(text, plain.text)
    after = move_accounting(text, profiled.text)
    assert after.kept >= before.kept
    assert after.invented <= before.invented + 1


# --------------------------------------------------------------------------- #
# Detectors
# --------------------------------------------------------------------------- #


def test_prose_language_by_dictionary_and_script():
    assert detect_prose_language(PORTUGUESE_BODY).lang == "por"
    assert detect_prose_language(ENGLISH_BODY).lang == "eng"
    russian = detect_prose_language(
        "Белые начинают и выигрывают после жертвы слона на поле h7 и шаха конём; "
        "чёрный король не может уйти от вечного шаха на ферзевом фланге")
    assert russian.lang == "rus"
    short = detect_prose_language("Nf3 Nc6 Bb5")
    assert short.abstained and "poucas" in short.reason_pt


def test_a_tie_keeps_the_hint_and_otherwise_abstains():
    # Names and moves only: every language scores alike.
    text = "Kasparov Karpov Fischer Spassky Capablanca Alekhine Lasker Steinitz Morphy " \
           "Anderssen Tal Botvinnik Petrosian Smyslov Euwe Kramnik Anand Carlsen"
    guess = detect_prose_language(text, hint="deu")
    assert guess.lang == "deu" and "dica" in guess.reason_pt
    assert detect_prose_language(text).abstained


def test_document_language_samples_pages():
    guess = document_language([ENGLISH_BODY, ENGLISH_BODY, PORTUGUESE_BODY[:40]])
    assert guess.lang == "eng"


def test_notation_convention_is_detected_separately_from_the_prose():
    german = detect_notation_convention("1.e4 e5 2.Sf3 Sc6 3.Lb5 a6 4.La4 Sf6 5.0-0 Le7 6.Te1")
    assert german.locale == "de"
    portuguese = detect_notation_convention(
        "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Bg5 e6 7.f4 Be7 8.Df3 Dc7",
        prose_lang="por")
    assert portuguese.locale == "pt"
    # The detector also reads the vocabulary around the moves, so plain prose
    # about "torre" and "peão" still points at pt; nothing at all abstains and
    # the prose language is offered as the prior.
    assert detect_notation_convention("A torre pertence ao peão passado.").locale == "pt"
    nothing = detect_notation_convention("", prose_lang="por")
    assert nothing.abstained
    assert "pt" in nothing.reason_pt
