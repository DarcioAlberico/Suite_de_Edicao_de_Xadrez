"""Sol §SOL-9: reproducible, multilingual lexicons.

A clean checkout must score text the same way this machine does: nothing
here depends on a sibling checkout, an environment variable, or a file
outside the package.
"""

from __future__ import annotations

import os

import pytest

from caissa.ocr import lexicon as lx
from caissa.ocr.hunspell import HunspellDictionary, load_packaged_dictionary


def test_no_absolute_external_path_and_the_env_var_is_the_only_door(monkeypatch):
    monkeypatch.delenv("CAISSA_LEXICON_DIR", raising=False)
    assert lx.external_lexicon_dir() is None
    monkeypatch.setenv("CAISSA_LEXICON_DIR", os.getcwd())
    assert lx.external_lexicon_dir() is not None
    monkeypatch.setenv("CAISSA_LEXICON_DIR", r"C:\nowhere\at\all")
    assert lx.external_lexicon_dir() is None


def test_the_manifest_names_origin_licence_and_hash_of_every_file():
    manifest = lx.packaged_manifest()
    files = manifest["files"]
    assert isinstance(files, dict)
    for name, info in files.items():
        assert info["source"], name
        assert info["license"], name
        assert len(info["sha256"]) == 64, name
    assert {"por.txt", "eng.txt", "rus.txt", "names.txt"} <= set(files)
    source = lx.lexicon_source()
    assert source["packaged_version"] == manifest["version"]
    assert source["packaged_files"]["por.txt"]["sha256"] == files["por.txt"]["sha256"][:16]


def test_licensed_dictionaries_answer_inflected_forms():
    por = load_packaged_dictionary("por")
    eng = load_packaged_dictionary("eng")
    if por is None or eng is None:
        pytest.skip("dicionários Hunspell não empacotados nesta build")
    assert por.is_word("posição")
    assert por.is_word("exige")          # exigir, by affix rule
    assert por.is_word("avancem")
    assert not por.is_word("xqzpl")
    assert eng.is_word("belongs")
    assert eng.is_word("outposts")
    assert eng.is_word("Rook")
    assert not eng.is_word("rooq")


def test_a_hand_built_hunspell_reader_applies_conditions_and_flags():
    d = HunspellDictionary()
    d.load_aff(["SFX S Y 2", "SFX S 0 s [^y]", "SFX S y ies y", "PFX U Y 1", "PFX U 0 un ."])
    d.load_dic(["3", "rook/S", "fly/S", "tie/U"])
    assert d.is_word("rooks")
    assert d.is_word("flies")
    assert not d.is_word("flys")        # the condition [^y] forbids it
    assert d.is_word("untie")
    assert not d.is_word("unrook")      # rook lacks the U flag
    assert len(d) == 3


def test_dictionary_hit_rate_uses_inflections_history_and_the_book_list():
    rate, judged = lx.dictionary_hit_rate(
        "As brancas jogaram a abertura espanhola e as pretas defenderam com precisão", ("por",))
    assert judged >= 9
    assert rate == pytest.approx(1.0)
    # Pre-reform spelling folds to the modern word when the modern word exists.
    assert lx._known("theoria", frozenset({"teoria"}), ()) is True
    assert lx._known("ryo", frozenset({"rio"}), ()) is True
    # A safe inflection of a listed word, never a chopped nonsense token.
    assert lx._known("cavalos", frozenset({"cavalo"}), ()) is True
    assert lx._known("qwzs", frozenset({"qwz"}), ()) is False     # stem too short
    # The per-book list counts only inside the block.
    assert not lx._known("Zvjaginsev", lx._folded_lexicon(("eng",)), ("eng",))
    with lx.book_lexicon(["Zvjaginsev", "Kramnik"]):
        assert lx._known("Zvjaginsev", lx._folded_lexicon(("eng",)), ("eng",))
        assert lx.lexicon_source()["book_words"] == 2
    assert lx.lexicon_source()["book_words"] == 0


def test_russian_is_scored_by_its_own_model_not_excused():
    good, n = lx.ngram_plausibility("Белые начинают и выигрывают после жертвы слона на поле")
    bad, m = lx.ngram_plausibility("щзъ фыв ъъж цчш ьььщ")
    assert n > 30 and m > 10
    assert good > 0.6
    assert bad < 0.2
    assert "cyrillic" in lx.MODELLED_SCRIPTS
    rate, judged = lx.dictionary_hit_rate("белые чёрные ладья ферзь король пешка", ("rus",))
    assert judged == 6 and rate == 1.0


def test_names_are_looked_up_but_never_modelled():
    assert lx._known("Capablanca", lx._folded_lexicon(("por",)), ("por",))
    assert lx._known("Zandvoort", lx._folded_lexicon(("eng",)), ("eng",))
    # The Latin model was built from the language lists alone: a bigram that
    # only occurs in a surname must stay unseen.
    assert "vj" not in lx._BIGRAMS or lx._BIGRAMS.get("vj", 0) == 0


def test_the_russian_hunspell_dictionary_answers_prose_and_refuses_garbage():
    """OCR_UI_ROADMAP passo 6: ``rus.dic.gz`` (BSD-3-Clause, A. I. Lebedev; the notice
    ships as ``LICENSE_ru_RU.txt``) replaces the 13–26 % dictionary hit rate the
    authored list gave Russian prose."""
    from importlib import resources

    from caissa.ocr.lexicon import dictionary_hit_rate, normalise_lang

    package = resources.files("caissa.ocr.data.lexicon")
    assert package.joinpath("rus.dic.gz").is_file()
    assert "Lebedev" in package.joinpath("LICENSE_ru_RU.txt").read_text("utf-8")
    prose = "Комбинация начинается жертвой слона и белые выигрывают решающий материал"
    hit, judged = dictionary_hit_rate(prose, normalise_lang("rus"))
    assert judged >= 8 and hit >= 0.9
    assert dictionary_hit_rate("bsbluoitib sb zism", normalise_lang("rus")) == (0.0, 3)
