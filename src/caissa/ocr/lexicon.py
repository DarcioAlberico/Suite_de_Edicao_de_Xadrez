"""A multilingual lexicon plus a character n-gram model.

Two questions recur across this package and both need the same data:

* *Is this string real language, or is it garbage that merely has the shape of
  language?*  Asked by :mod:`caissa.ocr.engines.pdf_text_layer` about a PDF's
  own text layer with a broken ``ToUnicode``, and by :mod:`caissa.ocr.quality`
  about OCR output when no ground truth exists.
* *Which of two engine outputs is more plausible?*  Asked by
  :mod:`caissa.ocr.arbiter`.

There are two sources, and the difference between them is worth stating plainly
because it changes every threshold downstream.

**The embedded core** is the ~150 most frequent words of each supported
language, written out below as literals.  It is thin as a spell checker, but
this code never needs to *validate* a word — it needs to tell 50 % coverage
from 2 %, which is the gap between real text and a substitution cipher of real
text.  A broken CMap is exactly a substitution cipher: the letter frequencies
still look plausible, and only the words give it away.  The core ships with the
source, needs no data file, and makes a clean checkout work.

**The trunk's lists**, when this machine has them, add 164,723 words:
``acervo.txt.gz`` (the editorial text layer of the corpus's own non-OCR books),
``idioma.txt.gz`` and ``nomes.txt.gz`` (players, cities, tournaments).  With
them the hit rate on clean prose roughly doubles, which widens the gap this
module exists to measure.

Origem: ChessVisionOFF_Puro/assets/lexico/ (built by ``cvoff-texto-lexico``,
read by ``src/chess_diagram_ocr/text/lexico.py``).  Absorvido em 2026-09-07.
Alterações: the files are **read where they are**, never copied into this
repository.  Two reasons, both in the trunk's own
``assets/lexico/PROCEDENCIA.md``: ``idioma.txt.gz`` has no declared origin, and
``nomes.txt.gz`` is in part an extract of a commercial player index — the trunk
records that its licence has not been cleared, and copying it here would be
this project asserting a clearance nobody has made.  The corpus rule applies
unchanged: local material stays local.  Point ``CAISSA_LEXICON_DIR`` at the
folder to move it; leave it unset and the embedded core is used alone.

Chess prose is not ordinary prose, so notation is recognised separately and
excluded from the denominator.  Without that, a page of pure move text scores
as garbage and a perfectly good text layer gets thrown away.
"""

from __future__ import annotations

import gzip
import logging
import math
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

__all__ = [
    "SUPPORTED_LANGUAGES",
    "LANGUAGE_ALIASES",
    "EXTERNAL_LEXICON_FILES",
    "external_lexicon_dir",
    "external_lexicon",
    "lexicon_source",
    "reset_lexicon_cache",
    "normalise_lang",
    "lexicon_for",
    "tokenize",
    "is_chess_notation",
    "dictionary_hit_rate",
    "ngram_log_probability",
    "ngram_plausibility",
    "modelled_script_share",
    "MODELLED_SCRIPT",
    "script_profile",
    "implausible_char_ratio",
    "nonword_ratio",
    "NOTATION_ALPHABET",
    "is_move_token",
    "is_mangled_move",
    "mangled_move_ratio",
]


# --------------------------------------------------------------------------- #
# Word lists
# --------------------------------------------------------------------------- #

_PT = """
a o e de do da das dos em um uma para com não uma os as se por mais como mas
foi ao ele das tem à seu sua ou ser quando muito há nos já está eu também só
pelo pela até isso ela entre era depois sem mesmo aos seus quem nas me esse
eles você essa num nem suas meu às minha numa pelos elas qual nós lhe deles
essas esses pelas este dele tu te vocês vos lhes meus minhas teu tua teus tuas
nosso nossa nossos nossas dela delas esta estes estas aquele aquela aqueles
brancas pretas branco preto peça peças rei dama torre bispo cavalo peão peões
lance lances jogo jogos partida partidas posição posições tabuleiro casa casas
abertura defesa ataque ataques variante variantes final finais meio campeonato
xadrez jogador jogadores torneio vitória empate derrota vantagem melhor
diagrama capítulo página exemplo exercício solução resposta análise
"""

_EN = """
the of and to in a is that it for on with as was he are be by this from at or
an will his not have has had but they which one you were all their there been
if more when who would its into so what about them can no time only some could
than other these two may then do first any my now such like our over man me
even most made after also did many before must through back years where much
your way well down should because each just those people mr how too little
state good very make world still own see men work long get here between both
white black piece pieces king queen rook bishop knight pawn pawns move moves
game games position positions board square squares opening defence defense
attack variation variations endgame middlegame chess player players tournament
win wins draw loss advantage better best diagram chapter page example exercise
solution answer analysis line lines threat threats check mate castling
"""

_DE = """
der die das und in zu den von mit sich des auf für ist im dem nicht ein eine
als auch es an werden aus er hat dass sie nach wird bei einer um am sind noch
wie einem über einen so zum war haben nur oder aber vor bis mehr durch man
sein wurde sei kann gegen vom kann schon wenn habe seine ihre wieder mir uns
weiss schwarz figur figuren könig dame turm läufer springer bauer bauern zug
züge partie partien stellung stellungen brett feld felder eröffnung verteidigung
angriff variante endspiel mittelspiel schach spieler turnier sieg remis
vorteil besser diagramm kapitel seite beispiel übung lösung antwort analyse
"""

_ES = """
de la que el en y a los se del las un por con no una su para es al lo como más
o pero sus le ha me si sin sobre este ya entre cuando todo esta ser son dos
también fue había era muy años hasta desde está mi porque qué sólo han yo hay
vez puede todos así nos ni parte tiene él uno donde bien tiempo
blancas negras pieza piezas rey dama torre alfil caballo peón peones jugada
jugadas partida partidas posición posiciones tablero casilla casillas apertura
defensa ataque variante variantes final medio ajedrez jugador jugadores torneo
victoria tablas derrota ventaja mejor diagrama capítulo página ejemplo análisis
"""

_FR = """
de la le et les des en un une du dans il que pour qui sur ne pas plus par au
se ce est sont avec mais ou été son aux nous comme leur sans elle si tout même
deux fait bien où peut être encore aussi quand très après cette faire dont
blancs noirs pièce pièces roi dame tour fou cavalier pion pions coup coups
partie parties position positions échiquier case cases ouverture défense
attaque variante variantes finale milieu échecs joueur joueurs tournoi
victoire nulle défaite avantage meilleur diagramme chapitre page exemple
"""

_IT = """
di che e la il un in per non una sono mi si ma con le ha come da lo se ci ho
ti al ne dei della sul nel questo tutto anche quando più molto essere fare
bianco nero pezzo pezzi re donna torre alfiere cavallo pedone pedoni mossa
mosse partita partite posizione posizioni scacchiera casa case apertura difesa
attacco variante varianti finale mediogioco scacchi giocatore torneo vittoria
patta sconfitta vantaggio migliore diagramma capitolo pagina esempio analisi
"""

_NL = """
de het een en van in is dat op te zijn met voor niet aan er maar die ook als
om dan bij nog uit door over naar wat wel heeft was werd deze veel meer kan
wit zwart stuk stukken koning dame toren loper paard pion pionnen zet zetten
partij partijen stelling stellingen bord veld velden opening verdediging
aanval variant varianten eindspel middenspel schaak speler spelers toernooi
overwinning remise verlies voordeel beter diagram hoofdstuk pagina voorbeeld
"""

_RU = """
и в не на я быть он с что а по это она этот к но они мы как из у который то
за свой весь год от так о для ты же все тот мочь вы человек такой его сказать
только или ещё бы себя один как уже до когда вот кто да говорить
белые чёрные черные фигура фигуры король ферзь ладья слон конь пешка пешки ход
ходы партия партии позиция позиции доска поле поля дебют защита атака вариант
варианты эндшпиль миттельшпиль шахматы игрок турнир победа ничья поражение
преимущество лучше диаграмма глава страница пример упражнение решение анализ
"""

_RAW_LEXICONS: dict[str, str] = {
    "por": _PT,
    "eng": _EN,
    "deu": _DE,
    "spa": _ES,
    "fra": _FR,
    "ita": _IT,
    "nld": _NL,
    "rus": _RU,
}

SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(sorted(_RAW_LEXICONS))

#: Accept ISO-639-1, common Tesseract codes and a few informal spellings.
LANGUAGE_ALIASES: dict[str, str] = {
    "pt": "por", "pt_br": "por", "pt-br": "por", "ptbr": "por", "por": "por",
    "en": "eng", "en_us": "eng", "en-gb": "eng", "eng": "eng",
    "de": "deu", "ger": "deu", "deu": "deu",
    "es": "spa", "esp": "spa", "spa": "spa",
    "fr": "fra", "fre": "fra", "fra": "fra",
    "it": "ita", "ita": "ita",
    "nl": "nld", "dut": "nld", "nld": "nld",
    "ru": "rus", "rus": "rus",
}


def normalise_lang(lang: str) -> tuple[str, ...]:
    """Turn ``"por+eng"`` or ``"pt-BR"`` into a tuple of internal codes.

    Unknown codes are dropped rather than guessed at; an empty result means
    "use every language", which is the right default for a page whose language
    has not been detected yet.
    """
    out: list[str] = []
    for part in re.split(r"[+,;/\s]+", (lang or "").strip().lower()):
        if not part:
            continue
        code = LANGUAGE_ALIASES.get(part)
        if code and code not in out:
            out.append(code)
    return tuple(out)


# --------------------------------------------------------------------------- #
# The trunk's word lists, read in place
# --------------------------------------------------------------------------- #

LOGGER = logging.getLogger("caissa.ocr.lexicon")

#: Default location of the trunk's ``assets/lexico``.  Overridden by
#: ``CAISSA_LEXICON_DIR``; absent is normal and not an error.
_DEFAULT_LEXICON_DIR = Path(
    r"C:\Python-Chess2\ChessVisionOFF_Puro\assets\lexico")

#: file -> whether it is loaded by default.  ``nomes`` carries 150k proper
#: nouns; it is on because chess prose is dense with player and place names and
#: judging those "not a word" is what made a good page look like garbage.
EXTERNAL_LEXICON_FILES: dict[str, bool] = {
    "acervo.txt.gz": True,
    "idioma.txt.gz": True,
    "nomes.txt.gz": True,
}


def external_lexicon_dir() -> Path | None:
    """Where the trunk's lists are, or ``None``."""
    raw = os.environ.get("CAISSA_LEXICON_DIR")
    candidate = Path(raw) if raw else _DEFAULT_LEXICON_DIR
    return candidate if candidate.is_dir() else None


@lru_cache(maxsize=1)
def external_lexicon() -> frozenset[str]:
    """The trunk's word lists, case-folded; empty when they are not present.

    A missing or unreadable file is a fact to report at DEBUG and carry on
    with, never an exception: the embedded core is a working fallback and a
    batch of 500 books must not stop because a sibling checkout moved.
    """
    directory = external_lexicon_dir()
    if directory is None:
        return frozenset()
    words: set[str] = set()
    for name, wanted in EXTERNAL_LEXICON_FILES.items():
        if not wanted:
            continue
        path = directory / name
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    token = line.strip()
                    if token:
                        words.add(token.casefold())
        except (OSError, EOFError, gzip.BadGzipFile) as exc:
            LOGGER.debug("lista de palavras '%s' não pôde ser lida: %s",
                         path, exc)
    return frozenset(words)


def lexicon_source() -> dict[str, object]:
    """What the lexicon is actually made of, for the report and the UI."""
    external = external_lexicon()
    embedded = frozenset(
        word for raw in _RAW_LEXICONS.values() for word in raw.split())
    directory = external_lexicon_dir()
    return {
        "embedded_words": len(embedded),
        "external_words": len(external),
        "external_dir": str(directory) if directory else None,
        "external_files": tuple(
            name for name, wanted in EXTERNAL_LEXICON_FILES.items() if wanted),
        "total_words": len(embedded | external),
    }


def reset_lexicon_cache() -> None:
    """Forget every cached word set — for tests, and after a path change.

    The character n-gram model is deliberately *not* reset: it is built from
    the embedded literals alone and must stay that way.  Training it on the
    trunk's 350,000 proper nouns would teach it the letter statistics of Slavic
    and Hungarian surnames, and the whole point of the n-gram term is to be a
    signal that does not move when the word list does.
    """
    external_lexicon.cache_clear()
    lexicon_for.cache_clear()
    _folded_lexicon.cache_clear()


@lru_cache(maxsize=64)
def lexicon_for(langs: tuple[str, ...]) -> frozenset[str]:
    """Union of the word lists for ``langs``; all languages when empty.

    The trunk's lists are not tagged by language and are added whole.  That is
    correct for the question this module answers — "is this real text?" — and
    would be wrong for language *identification*, which is why nothing here
    claims to do that.
    """
    codes = langs or SUPPORTED_LANGUAGES
    words: set[str] = set()
    for code in codes:
        raw = _RAW_LEXICONS.get(code)
        if raw:
            words.update(raw.split())
    return frozenset(words) | external_lexicon()


# --------------------------------------------------------------------------- #
# Tokenisation and chess notation
# --------------------------------------------------------------------------- #

#: A token is a maximal run of letters, digits and the few marks that belong
#: inside chess notation.  Splitting on whitespace alone leaves punctuation
#: glued to words and depresses the dictionary hit rate on clean text.
_TOKEN = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*|[^\s\w]+", re.UNICODE)

#: Piece letters in the eight supported languages, plus the Unicode figurines
#: a born-digital book may use directly (U+2654..U+265F).  Named rather than
#: inlined because :func:`is_mangled_move` has to know *exactly* the same set:
#: two tables that agree by coincidence rather than by construction is the
#: twelfth blind gate this project found (docs/ROADMAP.md).
_PIECE_LETTERS = ("KQRBNPCDTSAFLGVWМКФЛСКПРrdtcafgpb"
                  + "".join(chr(c) for c in range(0x2654, 0x2660)))
#: Piece letters a pawn may promote to — no king, no pawn.
_PROMOTION_LETTERS = "KQRBNCDTSAFLGVW"
_FILES = "a-h"
_RANKS = "1-8"
#: Capture and move-link marks.  ``:`` is German/Russian capture.  The ``-``
#: is last so the string stays safe to interpolate into a character class.
_LINK_MARKS = "x:×-"
#: Promotion is written ``=Q``; the ``=`` is part of notation's alphabet.
_PROMOTION_MARK = "="
#: Annotation marks.  They only ever *trail* a move, which is what makes a
#: leading ``!`` in ``!txg7`` evidence of damage rather than of annotation.
_ANNOTATION_MARKS = "+#!?"

#: SAN / LAN / figurine notation in the eight supported languages, plus move
#: numbers, castling, results and evaluation symbols.  Anything matching this
#: is real chess text and must not count against the dictionary hit rate.
_NOTATION = re.compile(
    rf"""^(?:
        [{_PIECE_LETTERS}]?[{_FILES}]?[{_RANKS}]?[{_LINK_MARKS}]?[{_FILES}][{_RANKS}]
            (?:{_PROMOTION_MARK}[{_PROMOTION_LETTERS}])?[{_ANNOTATION_MARKS}]{{0,2}}
      | [OO0]-[OO0](?:-[OO0])?[{_ANNOTATION_MARKS}]{{0,2}}
      | \d{{1,3}}\.{{1,3}}
      | 1-0 | 0-1 | 1/2-1/2 | ½-½
      | [+=−±∓+-]{{1,2}}
      | [KQRBNP]\d?
    )$""",
    re.VERBOSE | re.UNICODE,
)


def tokenize(text: str) -> list[str]:
    """Split into word-ish tokens, keeping the original case."""
    return _TOKEN.findall(text or "")


def is_chess_notation(token: str) -> bool:
    """True for a token that is chess notation rather than a word."""
    if not token:
        return False
    if token.isdigit():
        return True
    return bool(_NOTATION.match(token))


def _fold(token: str) -> str:
    """Lower-case and strip accents, for lexicon lookup only."""
    lowered = token.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped


@lru_cache(maxsize=64)
def _folded_lexicon(langs: tuple[str, ...]) -> frozenset[str]:
    return frozenset(_fold(w) for w in lexicon_for(langs))


def dictionary_hit_rate(text: str, langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Fraction of word tokens found in the lexicon, and how many were judged.

    Digits, punctuation, chess notation and single letters are excluded from
    the denominator.  The second element matters: a hit rate over four tokens
    means nothing, and callers must refuse to act on a tiny sample.
    """
    words = _folded_lexicon(langs)
    considered = 0
    hits = 0
    for token in tokenize(text):
        if len(token) < 2 or not any(c.isalpha() for c in token):
            continue
        if is_chess_notation(token):
            continue
        considered += 1
        if _fold(token) in words:
            hits += 1
    return (hits / considered if considered else 0.0), considered


_VOWELS = frozenset("aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿаеёиоуыэюя")


def is_implausible_token(token: str) -> bool:
    """True when ``token`` cannot be a word in any supported language.

    Three one-sided tests, each chosen because clean text of *any* language
    scores zero on it while OCR output does not:

    * a digit inside a word — ``th1s``, ``be1ieve``, ``rn0ve``.  This is the
      single most characteristic OCR error there is, because the confusable
      pairs are exactly ``l/1/I``, ``O/0``, ``S/5``, ``B/8``, ``G/6``.  Chess
      notation is full of legitimate letter-digit tokens, which is why it is
      excluded before this test runs rather than after;
    * no vowel at all in four or more characters;
    * two different scripts in one token — Latin ``c`` inside a Cyrillic word
      is a scanned-page artefact, not a word.

    The length test counts *characters*, not letters.  Counting letters was a
    bug: substituting the ``i`` of ``th1s`` leaves three letters, the token is
    skipped as too short, and the estimator misses the very error it exists to
    find.
    """
    if len(token) < 4 or is_chess_notation(token):
        return False
    if not any(c.isalpha() for c in token):
        return False
    letters = sum(1 for c in token if c.isalpha())
    digits = sum(1 for c in token if c.isdigit())
    if letters >= 2 and digits >= 1:
        return True
    if len(script_profile(token)) > 1:
        return True
    if letters >= 4 and not any(c in _VOWELS for c in _fold(token)):
        return True
    return False


def nonword_ratio(text: str, langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Fraction of word-shaped tokens that cannot be words.

    See :func:`is_implausible_token` for the tests.  Real words that trip them
    (acronyms, Czech "smrt", model numbers) are rare enough not to move the
    ratio on a page of prose, while OCR output trips them constantly.
    """
    considered = 0
    bad = 0
    for token in tokenize(text):
        if len(token) < 4 or is_chess_notation(token):
            continue
        if not any(c.isalpha() for c in token):
            continue
        considered += 1
        if is_implausible_token(token):
            bad += 1
    return (bad / considered if considered else 0.0), considered


# --------------------------------------------------------------------------- #
# Notation integrity
# --------------------------------------------------------------------------- #

#: Every character real chess notation is built from, derived from the same
#: constants that build :data:`_NOTATION` so the two cannot drift apart.
#: Annotation marks are *not* here: they are stripped from the tail first,
#: precisely so that a mark found anywhere else counts as damage.
NOTATION_ALPHABET: frozenset[str] = frozenset(
    _PIECE_LETTERS + "abcdefgh" + "12345678"
    + _LINK_MARKS + _PROMOTION_MARK + "Oo0"
)

#: A square name.  The one thing a mangled move almost always keeps, because
#: the file and rank are ordinary Latin characters that no figurine font
#: touches — it is the *piece* glyph that comes back as garbage.
_SQUARE = re.compile(r"[a-h][1-8]")

#: Annotation glyphs (``!``, ``?``, ``+``, ``#``, ``⩲``, ``⨀``, …) trail a move
#: and never open one.  Anything non-alphanumeric at the tail is stripped
#: before judging, which keeps Dvoretsky's zugzwang mark ``Kd3ʘ`` — measured,
#: 60 pages, see docs/quality/F5_REPORT_C2.md — from counting as damage.
_TRAILING_MARKS = re.compile(r"[^0-9A-Za-zЀ-ӿ]+$")

#: Characters that may split a compound the lexicon should get a look at, so
#: that English ``f2-pawn`` and ``e4-square`` are words, not broken moves.
_COMPOUND_SPLIT = re.compile(r"[-'’]")

#: The one move that names no square.  ``0-0`` has to be spelt out rather than
#: caught by "contains a hyphen", because ``1-0`` and ``0-1`` are results and
#: a result is not a move.
_CASTLING = frozenset({"O-O", "O-O-O", "0-0", "0-0-0"})


def is_move_token(token: str) -> bool:
    """True for notation that actually names a move — a square or a castle.

    Narrower than :func:`is_chess_notation`, which also accepts move numbers,
    results and evaluation symbols.  Those are not moves and must not pad the
    denominator of :func:`mangled_move_ratio`: a page of bare move numbers and
    results would otherwise look like a page of healthy notation.
    """
    if not token or not is_chess_notation(token):
        return False
    if _SQUARE.search(token):
        return True
    return _TRAILING_MARKS.sub("", token).upper() in _CASTLING


def is_mangled_move(token: str, langs: tuple[str, ...] = ()) -> bool:
    """True when ``token`` is a move whose piece glyph did not survive.

    This is the one failure a page-level lexical verdict cannot see, and it is
    the failure that matters most in a chess book.  A figurine font maps the
    knight to a private code point; when a PDF is re-OCR'd, or subset without
    a usable ToUnicode, that code point comes back as whatever Latin letters
    happen to sit at the same place — ``♘xe5`` becomes ``ll'lxe5``, ``♕d6+``
    becomes ``'i'd6+``, ``♖h7`` becomes ``l:th7``.

    The prose around it is untouched, so every existing signal stays green:
    measured on Aagaard p222, ``implausible_char_ratio`` 0.001,
    ``broken_font_char_ratio`` 0.000, ``dictionary_hit_rate`` 0.71 — accepted
    at 0.98 with its move text destroyed.

    The test is one-sided by construction.  A mangled move keeps its square —
    file and rank are ordinary Latin that no figurine font touches — but its
    prefix contains a character that notation has no way to produce.  Clean
    notation in any of the eight supported languages scores zero on it:

    * ``Nf3``, ``Cf3``, ``Sf3``, ``Кf3``, ``♘f3`` — the piece letter is in
      :data:`NOTATION_ALPHABET`, and in any case the whole token is already
      valid notation and returns early;
    * ``Lf2-d4``, ``exd5``, ``e8=Q``, ``O-O`` — same;
    * ``f2-pawn``, ``the e4-square`` — a hyphenated compound whose other half
      is a word is a word, not a move;
    * ``Kd3ʘ``, ``Rd1!?`` — annotation glyphs are stripped from the tail.

    Measured over 257 corpus pages (F5_REPORT_C2 §2): the two clean controls
    peak at 0.062, while the damaged books never fall below 0.187.
    """
    if not token or is_chess_notation(token):
        return False
    if not _SQUARE.search(token):
        return False
    words = _folded_lexicon(langs)
    if _fold(token) in words:
        return False
    parts = _COMPOUND_SPLIT.split(token)
    if len(parts) > 1 and any(len(p) > 2 and _fold(p) in words for p in parts):
        return False
    core = _TRAILING_MARKS.sub("", token)
    return any(c not in NOTATION_ALPHABET for c in core)


def mangled_move_ratio(text: str,
                       langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Share of move-shaped tokens whose piece glyph is damaged, and how many
    moves were judged.

    The second element is the guard the caller must honour: a ratio over four
    moves says nothing, and a page of prose with no notation at all must not
    be condemned by the two moves it happens to quote.
    """
    good = 0
    bad = 0
    for token in tokenize(text):
        if is_move_token(token):
            good += 1
        elif is_mangled_move(token, langs):
            bad += 1
    total = good + bad
    return (bad / total if total else 0.0), total


# --------------------------------------------------------------------------- #
# Character n-gram model
# --------------------------------------------------------------------------- #

_BOUNDARY = "\x02"
#: Stands in for any character that is not a letter but is *inside* a word.
#: It never appears in the model, so every bigram containing it takes the
#: add-one floor — which is the point: an OCR substitution that puts a digit in
#: the middle of a word should be scored as the anomaly it is.
_UNKNOWN = "\x01"


def _build_bigrams() -> tuple[dict[str, int], dict[str, int], int]:
    """Bigram and unigram counts over every lexicon word, with boundaries."""
    bigrams: dict[str, int] = {}
    unigrams: dict[str, int] = {}
    total = 0
    for raw in _RAW_LEXICONS.values():
        for word in raw.split():
            padded = _BOUNDARY + _fold(word) + _BOUNDARY
            for i in range(len(padded) - 1):
                pair = padded[i:i + 2]
                bigrams[pair] = bigrams.get(pair, 0) + 1
                unigrams[padded[i]] = unigrams.get(padded[i], 0) + 1
                total += 1
    return bigrams, unigrams, total


_BIGRAMS, _UNIGRAMS, _BIGRAM_TOTAL = _build_bigrams()
_ALPHABET_SIZE = max(64, len(_UNIGRAMS) * 2)

#: Log-probability per bigram for text that is entirely unseen.  Used to
#: normalise the raw score into 0..1 so thresholds read as fractions.
_WORST_LOGP = math.log(1.0 / (_BIGRAM_TOTAL + _ALPHABET_SIZE))
#: Empirically the mean log-probability of clean lexicon text; recomputed here
#: rather than hard-coded so that editing the word lists cannot silently
#: invalidate every threshold in the package.


def _model_form(token: str) -> str:
    """A token as the bigram model sees it: folded, with non-letters marked.

    Working token by token rather than over the raw string is what makes the
    model sensitive to the errors that matter.  Scanning the whole string and
    treating every non-letter as a word boundary makes ``th1s`` look like the
    two short words ``th`` and ``s``, both perfectly plausible — so the model
    scored corrupted Portuguese at 1.000, a full mark, which is how the bug was
    found.  Marking the digit as an interior unknown instead makes the same
    token score at the smoothing floor.
    """
    return "".join(c if c.isalpha() else _UNKNOWN for c in _fold(token))


def ngram_log_probability(text: str) -> tuple[float, int]:
    """Mean add-one-smoothed log P(bigram) over the word-shaped tokens.

    Returns ``(mean_log_p, n_bigrams)``.  Chess notation and bare numbers are
    skipped: they are legitimate and they are not words, so scoring them as
    words would make every page of move text look corrupt.
    """
    total = 0.0
    n = 0
    for token in tokenize(text or ""):
        if not any(c.isalpha() for c in token):
            continue
        if is_chess_notation(token):
            continue
        padded = _BOUNDARY + _model_form(token) + _BOUNDARY
        for i in range(len(padded) - 1):
            pair = padded[i:i + 2]
            count = _BIGRAMS.get(pair, 0)
            context = _UNIGRAMS.get(pair[0], 0)
            total += math.log((count + 1.0) / (context + _ALPHABET_SIZE))
            n += 1
    return (total / n if n else 0.0), n


def _reference_scores() -> tuple[float, float]:
    """Calibration anchors: clean lexicon prose, and uniform random letters."""
    sample = " ".join(
        word for raw in _RAW_LEXICONS.values() for word in raw.split()[:80]
    )
    good, _ = ngram_log_probability(sample)
    # A deterministic pseudo-random string standing in for garbage.  Seeded by
    # a fixed constant so the calibration cannot drift between runs.
    state = 12345
    letters = []
    for _ in range(4000):
        state = (1103515245 * state + 12345) % (1 << 31)
        letters.append(chr(ord("a") + state % 26))
        if state % 7 == 0:
            letters.append(" ")
    bad, _ = ngram_log_probability("".join(letters))
    return good, bad


_GOOD_LOGP, _BAD_LOGP = _reference_scores()


def ngram_plausibility(text: str) -> tuple[float, int]:
    """Map the bigram log-probability onto 0..1, where 1 is clean prose.

    The two anchors are computed at import time from the lexicon itself and
    from a fixed pseudo-random string, so the scale survives edits to the word
    lists.  Values are clamped; a score above 1 would only mean the text is
    even more lexicon-like than the lexicon.
    """
    score, n = ngram_log_probability(text)
    if n == 0:
        return 0.0, 0
    span = _GOOD_LOGP - _BAD_LOGP
    if span <= 0:  # pragma: no cover - only if the word lists are emptied
        return 0.0, n
    return max(0.0, min(1.0, (score - _BAD_LOGP) / span)), n


#: The alphabet the bigram model was trained on.  Everything outside it hits
#: the smoothing floor, which reads as "implausible" and is not what it means.
MODELLED_SCRIPT = "latin"


def modelled_script_share(text: str) -> float:
    """Fraction of the letters in ``text`` the n-gram model can actually judge.

    The bigram model is built from the embedded Latin word lists.  Cyrillic and
    Greek are perfectly good letters that it has simply never seen, so every
    bigram made of them lands on the smoothing floor and
    :func:`ngram_plausibility` returns ~0.0 — *indistinguishable from garbage*.

    Measured on the corpus (E6, Boleslavsky, PDF text layer, five pages): the
    pages are 88–93 % Cyrillic and score 0.000, 0.026, 0.000, 0.115, 0.091.
    Page 60 of that book is a table of Russian figurine moves with almost no
    prose, and the combination of a 97-word Russian lexicon and a zero n-gram
    score rejected a text layer that is entirely correct.

    Callers must use this to let the n-gram term **abstain** rather than vote.
    An abstention is a smaller mistake than a confident wrong answer, and this
    is exactly the sort of page — non-Latin, mostly notation — where a wrong
    rejection costs the user an hour of needless OCR.
    """
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    modelled = sum(1 for c in letters if _script_of(c) == MODELLED_SCRIPT)
    return modelled / len(letters)


# --------------------------------------------------------------------------- #
# Script sanity
# --------------------------------------------------------------------------- #

_SCRIPT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0041, 0x024F, "latin"),
    (0x0370, 0x03FF, "greek"),
    (0x0400, 0x04FF, "cyrillic"),
    (0x0590, 0x05FF, "hebrew"),
    (0x0600, 0x06FF, "arabic"),
    (0x2100, 0x214F, "letterlike"),
    (0x2190, 0x21FF, "arrows"),
    (0x2200, 0x22FF, "math"),
    (0x2600, 0x26FF, "symbols"),      # chess pieces live at U+2654..U+265F
    (0x3000, 0x303F, "cjk_punct"),
    (0x3040, 0x30FF, "kana"),
    (0x4E00, 0x9FFF, "cjk"),
    (0xE000, 0xF8FF, "private_use"),
    (0xFB00, 0xFB4F, "alphabetic_presentation"),
    (0xFFF0, 0xFFFF, "specials"),
)

#: Scripts that a Latin- or Cyrillic-script chess book can legitimately contain.
PLAUSIBLE_SCRIPTS = frozenset({
    "latin", "greek", "cyrillic", "letterlike", "arrows", "math", "symbols",
    "alphabetic_presentation", "digit", "punctuation", "space",
})


def _script_of(ch: str) -> str:
    cp = ord(ch)
    if ch.isspace():
        return "space"
    if ch.isdigit():
        return "digit"
    for lo, hi, name in _SCRIPT_RANGES:
        if lo <= cp <= hi:
            return name
    if cp < 0x0041:
        return "punctuation"
    if unicodedata.category(ch).startswith("P"):
        return "punctuation"
    return "other"


def script_profile(text: str) -> dict[str, int]:
    """Count characters by coarse script.  Whitespace and digits are excluded
    from the *word*-level use in :func:`nonword_ratio` but kept here."""
    profile: dict[str, int] = {}
    for ch in text or "":
        if ch.isspace():
            continue
        name = _script_of(ch)
        if name in ("digit", "punctuation"):
            continue
        profile[name] = profile.get(name, 0) + 1
    return profile


def implausible_char_ratio(text: str) -> tuple[float, int]:
    """Fraction of characters that no correct text layer would contain.

    A missing or dead ``ToUnicode`` makes MuPDF hand back raw glyph indices, and
    glyph indices land wherever they land: the private use area, unassigned
    code points, CJK, or U+0000.  A Latin chess book with 30 % of its
    characters in the CJK block is not a multilingual edition.
    """
    considered = 0
    bad = 0
    for ch in text or "":
        if ch.isspace():
            continue
        considered += 1
        cp = ord(ch)
        if cp == 0 or cp == 0xFFFD:
            bad += 1
            continue
        category = unicodedata.category(ch)
        if category in ("Cc", "Cf", "Co", "Cs", "Cn"):
            bad += 1
            continue
        if _script_of(ch) not in PLAUSIBLE_SCRIPTS:
            bad += 1
    return (bad / considered if considered else 0.0), considered
