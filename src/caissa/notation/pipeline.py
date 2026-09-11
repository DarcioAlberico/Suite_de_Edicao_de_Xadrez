# Origem: PGN_Live_Editor/pgn_live_editor/services/parse_worker.py
# Absorvido em 2026-09-07. Alteracoes: removidas as classes `_ParseRunner` e `AsyncParser` (a metade
#   PyQt6 do modulo) e o import de PyQt6. A parte pura -- `ParseConfig`,
#   `SegmentAnalysis`, `SegmentDigest`, `DocumentAnalysis`, `ParsePipeline`,
#   `highlight_spans` e `build_games_for_export` -- vem intacta.
"""Pipeline de analise e execucao fora da thread de interface (SPEC 5.4).

Duas ideias sustentam a escala de livro:

1. **Incremental por segmento.** So a partida que contem o cursor e analisada a
   cada tecla; as demais ficam no cache enquanto o texto delas nao mudar. Sem
   isto, um capítulo de 64 partidas custaria 64 analises por caractere digitado.
2. **Fora da thread de UI.** A digitacao nunca espera pelo parser. A thread de
   trabalho tem a **sua propria** `ParsePipeline` -- nenhum objeto e
   compartilhado entre as duas threads, e por isso não há trava nenhuma aqui.

Pedidos pendentes colapsam: existe no maximo um em voo, e o mais recente vence.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import chess

from .candidates import as_dictionary
from .fen_tools import start_fen_of
from .game_splitter import (
    DEFAULT_SEPARATOR_PATTERN,
    GameSegment,
    index_at,
    split_games,
)
from .issues import Issue, count_by_severity
from .normalizer import LiveTextNormalizer
from .parser import GameAST, TolerantParser, iter_moves
from .pgn_headers import validate_headers
from .substitutions import Dictionary
from .tokenizer import PGNTokenizer


@dataclass(frozen=True)
class ParseConfig:
    """Tudo que muda o resultado da analise sem que o texto mude.

    Imutavel de proposito: e o unico dado que atravessa a fronteira de thread, e
    faz parte da chave do cache.
    """

    locale: str = "pt"
    # `(escopo, padrao, substituicao, idioma)` por entrada: e a forma imutavel
    # e ordenada do dicionario, que e o que pode atravessar a fronteira de
    # thread e entrar na chave do cache.
    dictionary: tuple[tuple[str, str, str, str], ...] = ()
    ignored_tokens: tuple[str, ...] = ()
    separator_pattern: str | None = DEFAULT_SEPARATOR_PATTERN

    @classmethod
    def build(
        cls,
        locale: str = "pt",
        dictionary: Dictionary | Mapping[str, str] | None = None,
        ignored_tokens: Iterable[str] = (),
        separator_pattern: str | None = DEFAULT_SEPARATOR_PATTERN,
    ) -> ParseConfig:
        return cls(
            locale=locale,
            dictionary=as_dictionary(dictionary).as_config(),
            ignored_tokens=tuple(sorted(ignored_tokens)),
            separator_pattern=separator_pattern,
        )

    @property
    def dictionary_map(self) -> Dictionary:
        return Dictionary.from_config(self.dictionary)


@dataclass
class SegmentAnalysis:
    """Uma partida do livro, ja analisada."""

    segment: GameSegment
    ast: GameAST
    start_fen: str

    @property
    def move_count(self) -> int:
        return sum(1 for _move in iter_moves(self.ast.moves))

    @property
    def issue_counts(self) -> dict[str, int]:
        return count_by_severity(self.ast.issues)


def highlight_spans(ast: GameAST) -> tuple[tuple[int, int, str, int], ...]:
    """`(inicio, fim, categoria, profundidade)` de cada lance, para o realce.

    A profundidade e um numero, e nao "e variante ou nao": e ela que da a cor
    de cada nivel. Numa partida de livro com quatro niveis de aninhamento,
    saber apenas que um lance **esta** numa variante nao ajuda a achar onde
    ele esta.
    """
    spans: list[tuple[int, int, str, int]] = []

    def walk(moves: list, depth: int):
        for move in moves:
            if move.start_index >= 0 and move.end_index > move.start_index:
                if not move.is_valid:
                    kind = "error"
                elif move.needs_review:
                    kind = "review"
                elif move.corrected_san:
                    kind = "fixed"
                else:
                    kind = "valid"
                spans.append((move.start_index, move.end_index, kind, depth))

            for variation in move.variations:
                walk(variation, depth + 1)

    walk(ast.moves, 0)
    return tuple(spans)


@dataclass(frozen=True)
class SegmentDigest:
    """O que basta para desenhar e contar uma partida que **nao** esta sob o cursor.

    Guardar isto, e nao a AST, e o que permite reaproveitar a analise de uma
    partida depois que ela mudou de lugar no documento: digitar na partida 3
    empurra as partidas 4 em diante, mas o texto delas continua o mesmo -- e as
    posicoes se corrigem com uma soma.
    """

    parsed_at: int
    spans: tuple[tuple[int, int, str, int], ...]
    move_count: int
    error_count: int
    warning_count: int

    def shifted_to(self, raw_offset: int) -> SegmentDigest:
        delta = raw_offset - self.parsed_at
        if delta == 0:
            return self
        return SegmentDigest(
            parsed_at=raw_offset,
            spans=tuple((start + delta, end + delta, kind, depth) for start, end, kind, depth in self.spans),
            move_count=self.move_count,
            error_count=self.error_count,
            warning_count=self.warning_count,
        )

    @classmethod
    def of(cls, analysis: SegmentAnalysis) -> SegmentDigest:
        counts = analysis.issue_counts
        return cls(
            parsed_at=analysis.segment.raw_offset,
            spans=highlight_spans(analysis.ast),
            move_count=analysis.move_count,
            error_count=counts["error"],
            warning_count=counts["warning"],
        )


@dataclass
class SegmentSummary:
    """O que o painel de partidas mostra por linha."""

    index: int
    title: str
    analyzed: bool = False
    move_count: int = 0
    error_count: int = 0
    warning_count: int = 0


@dataclass
class DocumentAnalysis:
    """O livro inteiro em segmentos, com a partida sob o cursor analisada."""

    raw_text: str = ""
    segments: list[GameSegment] = field(default_factory=list)
    active_index: int = 0
    active: SegmentAnalysis | None = None
    # Resumos ja ajustados a posicao atual de cada partida no documento.
    digests: dict[int, SegmentDigest] = field(default_factory=dict)

    @property
    def game_count(self) -> int:
        return len(self.segments)

    @property
    def highlight_spans(self) -> list[tuple[int, int, str, int]]:
        """Realce do documento inteiro, nao so da partida sob o cursor."""
        spans: list[tuple[int, int, str, int]] = []
        for index in sorted(self.digests):
            spans.extend(self.digests[index].spans)
        return spans

    @property
    def ast(self) -> GameAST:
        return self.active.ast if self.active else GameAST()

    @property
    def start_fen(self) -> str:
        return self.active.start_fen if self.active else chess.STARTING_FEN

    @property
    def issues(self) -> list[Issue]:
        return list(self.ast.issues)

    def segment_at(self, position: int) -> GameSegment | None:
        if not self.segments:
            return None
        return self.segments[index_at(self.segments, position)]

    def summaries(self) -> list[SegmentSummary]:
        summaries: list[SegmentSummary] = []
        for segment in self.segments:
            digest = self.digests.get(segment.index)
            if digest is None:
                summaries.append(SegmentSummary(index=segment.index, title=segment.title))
                continue

            summaries.append(
                SegmentSummary(
                    index=segment.index,
                    title=segment.title,
                    analyzed=True,
                    move_count=digest.move_count,
                    error_count=digest.error_count,
                    warning_count=digest.warning_count,
                )
            )
        return summaries


class ParsePipeline:
    """Texto bruto -> segmentos -> AST. **Nao** e seguro entre threads."""

    CACHE_LIMIT = 64

    def __init__(self, config: ParseConfig | None = None):
        self.config = config or ParseConfig()
        self.normalizer = LiveTextNormalizer(locale=self.config.locale)
        self.tokenizer = PGNTokenizer()
        self.parser = TolerantParser(locale=self.config.locale, dictionary=self.config.dictionary_map)
        self.parser.set_ignored_tokens(self.config.ignored_tokens)
        self._cache: OrderedDict[tuple, SegmentAnalysis] = OrderedDict()
        # Cache sem posicao: sobrevive a uma partida ser empurrada no documento.
        self._digests: OrderedDict[tuple, SegmentDigest] = OrderedDict()

    # ------------------------------------------------------------------

    def configure(self, config: ParseConfig) -> None:
        if config == self.config:
            return
        self.config = config
        self.normalizer.locale = config.locale
        self.parser.set_locale(config.locale)
        self.parser.set_dictionary(config.dictionary_map)
        self.parser.set_ignored_tokens(config.ignored_tokens)
        # A configuracao entra na chave do cache; trocar de dicionario invalida
        # tudo que foi analisado com o anterior.
        self._cache.clear()
        self._digests.clear()

    # ------------------------------------------------------------------

    def _cache_key(self, segment: GameSegment) -> tuple:
        return (segment.raw_offset, segment.content_offset, segment.end_offset) + self._digest_key(segment)

    def _digest_key(self, segment: GameSegment) -> tuple:
        return (self.config, segment.body, tuple(segment.headers.items()))

    def cached_for(self, segment: GameSegment) -> SegmentAnalysis | None:
        return self._cache.get(self._cache_key(segment))

    def digest_for(self, segment: GameSegment) -> SegmentDigest | None:
        """Resumo da partida, ja ajustado a posicao atual dela no documento."""
        digest = self._digests.get(self._digest_key(segment))
        return digest.shifted_to(segment.raw_offset) if digest is not None else None

    def _store(self, key: tuple, analysis: SegmentAnalysis) -> SegmentAnalysis:
        self._cache[key] = analysis
        self._cache.move_to_end(key)
        while len(self._cache) > self.CACHE_LIMIT:
            self._cache.popitem(last=False)

        digest_key = self._digest_key(analysis.segment)
        self._digests[digest_key] = SegmentDigest.of(analysis)
        self._digests.move_to_end(digest_key)
        while len(self._digests) > self.CACHE_LIMIT:
            self._digests.popitem(last=False)

        return analysis

    def analyze_segment(self, raw_text: str, segment: GameSegment) -> SegmentAnalysis:
        key = self._cache_key(segment)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        start_fen = start_fen_of(segment.headers)
        normalized = self.normalizer.normalize_with_mapping(segment.body, base_offset=segment.raw_offset)
        tokens = self.tokenizer.tokenize(normalized)

        ast = self.parser.parse(tokens, start_fen=start_fen)
        ast.headers = list(segment.headers.items())
        ast.issues.extend(validate_headers(segment.headers, raw_text, segment.content_offset, segment.end_offset))

        return self._store(key, SegmentAnalysis(segment=segment, ast=ast, start_fen=start_fen))

    def analyze(self, raw_text: str, cursor_position: int = 0) -> DocumentAnalysis:
        """Analisa **so** a partida sob o cursor; o resto vem do cache, se houver."""
        segments = split_games(raw_text, self.config.separator_pattern)
        active_index = index_at(segments, cursor_position)
        active = self.analyze_segment(raw_text, segments[active_index])

        digests = {active_index: SegmentDigest.of(active)}
        for segment in segments:
            if segment.index == active_index:
                continue
            digest = self.digest_for(segment)
            if digest is not None:
                digests[segment.index] = digest

        return DocumentAnalysis(
            raw_text=raw_text,
            segments=segments,
            active_index=active_index,
            active=active,
            digests=digests,
        )

    def analyze_all(self, raw_text: str) -> list[SegmentAnalysis]:
        """Todas as partidas -- exportacao em lote e contagem do painel."""
        segments = split_games(raw_text, self.config.separator_pattern)
        return [self.analyze_segment(raw_text, segment) for segment in segments]


def build_games_for_export(analyses: Sequence[SegmentAnalysis]) -> list[tuple[GameAST, str]]:
    """Formato que `pgn_export` espera, ignorando segmentos vazios."""
    return [
        (analysis.ast, analysis.start_fen)
        for analysis in analyses
        if analysis.ast.moves or analysis.ast.result or analysis.segment.headers
    ]
