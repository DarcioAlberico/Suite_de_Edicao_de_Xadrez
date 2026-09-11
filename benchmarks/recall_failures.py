"""Why detection misses the 5 % it misses -- one row per lost diagram, with the guard that lost it.

``docs/ASSETS.md`` 1.2 puts field detection recall at 0,9478 against a target of
0,99.  ``benchmarks/validate_detection.py`` says *how much* is lost; this says
*where*.  A threshold moved against the wrong cause is a precision loss with no
recall to show for it, and ``ANALISE_DETECCAO.md`` 5 already records two of those.

The instrument the trunk provides
--------------------------------
``board_detection.detect_boards`` and ``detection.hybrid.detect_diagrams`` both
accept a ``rejected`` list and append a :class:`RejectedQuad` per barred
candidate, with the guard that barred it.  That list is the primary evidence
here.  It has two blind spots by design, and this script covers both:

* a contour under ``MIN_AREA_FRACTION`` is never recorded (2,6 million speckle
  rows in the first census run, against 499 accepted candidates), so a diagram
  lost to the area floor would look like "no candidate at all";
* a candidate dropped by the ``DEDUPE_IOU`` pass is not recorded either, since
  it is the same finding seen twice.

:func:`trace_page` re-runs the trunk's own gate order over the page and keeps
every contour that lands on an annotated box (IoU >= ``TRACE_IOU``), whatever
gate killed it.  It is a *measuring copy* in the sense of
``benchmarks/profile_detection.py``: nothing in production imports it, and it
mirrors ``_extract_candidate_quads`` gate for gate.  When the trace is empty for
a miss, "never proposed as a candidate" is a measurement and not an assumption.

Matching is the field set's own: IoU >= ``field_eval.MATCH_IOU`` on PDF points,
greedy over pairs sorted by IoU, which is what produced 0,9478.

Usage::

    .venv/Scripts/python.exe benchmarks/recall_failures.py --dump
    .venv/Scripts/python.exe benchmarks/recall_failures.py --pdf "1937 Kemeri.pdf"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from caissa.vision.classify.cvoff import ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

TRACE_IOU = 0.10
"""Quanto um contorno precisa cobrir da anotação para entrar no rastro.

Baixo de propósito: o rastro existe para responder "existiu contorno aqui?", e um
contorno que pega 7/8 do tabuleiro (o defeito de contato de quina da S-175) fecha IoU
0,875 -- mas um que pega só a moldura externa, ou só metade, fecha bem menos e ainda é
evidência. Abaixo disto é speckle, que é o que a S-131 mediu não valer a pena gravar.
"""

CAUSE_IOU = 0.20
"""IoU mínimo para uma recusa ser aceita como *a causa* daquela perda.

Acima do rastro: dizer "este candidato é o diagrama que se perdeu" é uma afirmação mais
forte que "havia contorno por aqui". Abaixo de 0,20 a sobreposição é acidental.
"""


@dataclass
class Trace:
    """Um contorno que caiu sobre uma caixa anotada, e o portão em que ele parou."""

    bbox: tuple[int, int, int, int]
    gate: str
    area_ratio: float
    elongation: float
    geom: float
    checker: float
    grid: float
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "gate": self.gate,
            "area_ratio": round(self.area_ratio, 5),
            "elongation": round(self.elongation, 4),
            "geom": round(self.geom, 4),
            "checker": round(self.checker, 4),
            "grid": round(self.grid, 4),
            "score": round(self.score, 4),
        }


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """IoU de duas caixas ``(x, y, w, h)``."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return float(inter / union) if union > 0 else 0.0


def trace_page(image_rgb: np.ndarray, targets: Sequence[tuple[int, int, int, int]]) -> list[Trace]:
    """Todo contorno que cai sobre uma das ``targets``, com o portão que o barrou.

    Espelha ``board_detection._extract_candidate_quads`` portão a portão -- inclusive a
    ordem, que é o que decide qual motivo é registrado quando dois se aplicam. O filtro por
    ``targets`` é o que mantém isto utilizável: sem ele são 2,6 milhões de linhas de speckle
    (S-131), e com ele são as dezenas de contornos que caem em cima do diagrama perdido.

    Args:
        image_rgb: A página renderizada, exatamente a que ``detect_boards`` recebe.
        targets: Caixas anotadas em **pixels** desta imagem.

    Returns:
        Um :class:`Trace` por contorno relevante. Vazio significa, medido, que nenhum
        contorno daquela região chegou sequer a ser um quadrilátero candidato.
    """
    import cv2

    from chess_diagram_ocr import board_detection as bd

    if not targets:
        return []

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh_base = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 8)
    image_area = float(image_rgb.shape[0] * image_rgb.shape[1])

    traces: list[Trace] = []

    for thresh in bd._threshold_passes(thresh_base):
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if len(contour) < 4:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
            else:
                quad = cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.float32)

            bbox = bd._bbox_from_quad(quad)
            if max((_iou(bbox, target) for target in targets), default=0.0) < TRACE_IOU:
                continue

            area = float(cv2.contourArea(quad.astype(np.float32)))
            area_ratio = area / image_area if image_area else 0.0
            elongation = bd._quad_elongation(quad)

            if area < image_area * bd.MIN_AREA_FRACTION:
                traces.append(Trace(bbox, "piso-de-area", area_ratio, elongation, 0.0, 0.0, 0.0, 0.0))
                continue
            if elongation > bd.ASPECT_MAX:
                traces.append(Trace(bbox, "aspecto", area_ratio, elongation, 0.0, 0.0, 0.0, 0.0))
                continue

            geom = bd._contour_geometry_score(quad, image_area)
            if (
                bd._bbox_visible_ratio(bbox, image_rgb.shape) < bd.MIN_VISIBLE_RATIO
                or bd._quad_point_inside_ratio(quad, image_rgb.shape) < bd.MIN_QUAD_INSIDE_RATIO
            ):
                traces.append(Trace(bbox, "fora-da-pagina", area_ratio, elongation, geom, 0.0, 0.0, 0.0))
                continue

            small = bd._small_gray(bd.warp_from_quad(image_rgb, quad, target_size=320))
            checker = bd._checker_score(small)
            grid = bd._grid_score(small)
            if bd.MIN_CHECKER_CONTRAST is not None and checker <= bd.MIN_CHECKER_CONTRAST:
                traces.append(Trace(bbox, "sem-contraste-de-casa", area_ratio, elongation, geom, checker, grid, 0.0))
                continue

            score = geom * (0.55 + 0.45 * bd._texture_from_parts(checker, grid))
            traces.append(Trace(bbox, "passou", area_ratio, elongation, geom, checker, grid, score))

    return traces


@dataclass
class Miss:
    """Um diagrama anotado que o detector não devolveu."""

    pdf: str
    page: int
    regime: str
    bbox_pdf: tuple[float, float, float, float]
    bbox_px: tuple[int, int, int, int]
    cause: str
    detail: str = ""
    best_iou: float = 0.0
    rejections: list[dict[str, Any]] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pdf": self.pdf,
            "page": self.page,
            "regime": self.regime,
            "bbox_pdf": [round(v, 2) for v in self.bbox_pdf],
            "bbox_px": list(self.bbox_px),
            "cause": self.cause,
            "detail": self.detail,
            "best_iou": round(self.best_iou, 4),
            "rejections": self.rejections,
            "traces": self.traces,
        }


def _match_greedy(annotated: Sequence[Any], read_boxes: Sequence[tuple[float, float, float, float]]) -> dict[int, int]:
    """A regra de ``field_eval._match``: guloso sobre os pares ordenados por IoU."""
    from chess_diagram_ocr.field_eval import MATCH_IOU, bbox_iou

    pairs = [
        (bbox_iou(a.bbox, box), ia, ib)
        for ia, a in enumerate(annotated)
        for ib, box in enumerate(read_boxes)
    ]
    pairs.sort(reverse=True)
    matched: dict[int, int] = {}
    used: set[int] = set()
    for iou, ia, ib in pairs:
        if iou < MATCH_IOU or ia in matched or ib in used:
            continue
        matched[ia] = ib
        used.add(ib)
    return matched


def _dump(
    image_rgb: np.ndarray,
    miss: Miss,
    accepted: Sequence[tuple[int, int, int, int]],
    destination: Path,
) -> None:
    """Grava o recorte da página com a anotação, os aceitos e as recusas desenhados."""
    import cv2

    x, y, w, h = miss.bbox_px
    pad = int(max(w, h) * 0.45) + 20
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(image_rgb.shape[1], x + w + pad)
    y1 = min(image_rgb.shape[0], y + h + pad)
    crop = np.ascontiguousarray(image_rgb[y0:y1, x0:x1]).copy()

    def draw(box: tuple[int, int, int, int], color: tuple[int, int, int], label: str, offset: int) -> None:
        bx, by, bw, bh = box
        cv2.rectangle(crop, (bx - x0, by - y0), (bx - x0 + bw, by - y0 + bh), color, 2)
        cv2.putText(
            crop, label, (max(2, bx - x0), max(12, by - y0 - 4 - offset)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA,
        )

    for index, item in enumerate(miss.rejections[:6]):
        draw(tuple(item["bbox"]), (220, 40, 40), f"{item['reason']} s={item['score']:.3f} c={item['checker']:.3f}", index * 13)
    for box in accepted:
        draw(box, (40, 80, 240), "aceito", 0)
    draw(miss.bbox_px, (30, 190, 60), "ANOTADO", 0)

    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))


def analyse(
    *,
    dpi: int = 220,
    max_boards: int = 12,
    pdf_filter: str = "",
    dump_dir: Path | None = None,
    trace: bool = True,
) -> dict[str, Any]:
    """Roda o detector híbrido sobre o conjunto de campo e classifica cada perda."""
    import fitz

    from chess_diagram_ocr.detection.hybrid import detect_diagrams
    from chess_diagram_ocr.field_eval import bbox_iou, load_field_set
    from chess_diagram_ocr.pdf_io import render_pdf_page

    from caissa.vision.classify.cvoff import cvoff_root

    root = cvoff_root()
    pages = [p for p in load_field_set(root / "data" / "field_set.jsonl") if p.reviewed]
    if pdf_filter:
        pages = [p for p in pages if pdf_filter.lower() in p.pdf.lower()]

    misses: list[Miss] = []
    annotated_total = 0
    detected_total = 0
    matched_total = 0

    for entry in pages:
        pdf_path = root / "PDF" / entry.pdf
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF do conjunto de campo ausente: {pdf_path}")
        image = render_pdf_page(pdf_path, entry.page, dpi=dpi)
        rejected: list[Any] = []
        with fitz.open(pdf_path) as doc:
            page = doc[entry.page]
            scale_x = image.shape[1] / page.rect.width if page.rect.width else 1.0
            scale_y = image.shape[0] / page.rect.height if page.rect.height else 1.0
            scale = (scale_x + scale_y) / 2.0
            candidates = detect_diagrams(page, image, max_boards=max_boards, rejected=rejected)

        boxes_pdf = [c.bbox_pdf for c in candidates]
        annotated_total += len(entry.diagrams)
        detected_total += len(candidates)
        matched = _match_greedy(entry.diagrams, boxes_pdf)
        matched_total += len(matched)

        lost = [i for i in range(len(entry.diagrams)) if i not in matched]
        if not lost:
            continue

        def to_px(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
            bx0, by0, bx1, by1 = box
            return (
                int(bx0 * scale),
                int(by0 * scale),
                max(1, int((bx1 - bx0) * scale)),
                max(1, int((by1 - by0) * scale)),
            )

        accepted_px = [to_px(box) for box in boxes_pdf]
        targets_px = [to_px(entry.diagrams[i].bbox) for i in lost]
        traces = trace_page(image, targets_px) if trace else []

        for position, index in enumerate(lost):
            annotation = entry.diagrams[index]
            target = targets_px[position]
            miss = Miss(
                pdf=entry.pdf,
                page=entry.page,
                regime=entry.regime,
                bbox_pdf=annotation.bbox,
                bbox_px=target,
                cause="nunca-proposto",
            )

            near_accepted = sorted(
                ((bbox_iou(annotation.bbox, box), i) for i, box in enumerate(boxes_pdf)),
                reverse=True,
            )
            near_rejected = sorted(
                (
                    (_iou(target, item.bbox), item)
                    for item in rejected
                    if _iou(target, item.bbox) >= TRACE_IOU
                ),
                key=lambda pair: -pair[0],
            )
            near_traces = sorted(
                ((_iou(target, item.bbox), item) for item in traces if _iou(target, item.bbox) >= TRACE_IOU),
                key=lambda pair: -pair[0],
            )
            miss.rejections = [
                {"iou": round(iou, 4), "reason": item.reason, "score": item.score, "checker": item.checker,
                 "bbox": list(item.bbox)}
                for iou, item in near_rejected[:12]
            ]
            miss.traces = [{"iou": round(iou, 4), **item.as_dict()} for iou, item in near_traces[:12]]

            best_acc_iou = near_accepted[0][0] if near_accepted else 0.0
            if best_acc_iou >= 0.5:
                miss.cause = "disputa-de-anotacoes"
                miss.detail = "um candidato aceito cobre duas anotacoes"
                miss.best_iou = best_acc_iou
            elif best_acc_iou >= CAUSE_IOU:
                miss.cause = "caixa-imprecisa"
                miss.detail = f"melhor candidato aceito com IoU {best_acc_iou:.3f} (<0,5)"
                miss.best_iou = best_acc_iou
            elif near_rejected and near_rejected[0][0] >= CAUSE_IOU:
                iou, item = near_rejected[0]
                miss.cause = item.reason
                miss.detail = f"score {item.score:.4f}, contraste {item.checker:.4f}"
                miss.best_iou = iou
            elif near_traces and near_traces[0][0] >= CAUSE_IOU:
                iou, item = near_traces[0]
                miss.cause = item.gate if item.gate != "passou" else "engolido-por-dedupe"
                miss.detail = (
                    f"rastro: alongamento {item.elongation:.3f}, area {item.area_ratio:.5f}, "
                    f"contraste {item.checker:.4f}, score {item.score:.4f}"
                )
                miss.best_iou = iou
            else:
                partial = near_traces[0] if near_traces else (near_rejected[0] if near_rejected else None)
                miss.detail = (
                    "nenhum contorno com IoU >= 0,20 sobre a caixa anotada"
                    if partial is None
                    else f"melhor contorno cobre so IoU {partial[0]:.3f}"
                )
                miss.best_iou = partial[0] if partial else 0.0

            misses.append(miss)
            if dump_dir is not None:
                stem = f"{Path(entry.pdf).stem[:48]}_p{entry.page}_{index}_{miss.cause}".replace(" ", "_")
                _dump(image, miss, accepted_px, dump_dir / f"{stem}.png")

    recall = matched_total / annotated_total if annotated_total else 0.0
    precision = matched_total / detected_total if detected_total else 0.0
    causes = Counter(m.cause for m in misses)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dpi": dpi,
        "max_boards": max_boards,
        "pages": len(pages),
        "annotated": annotated_total,
        "detected": detected_total,
        "matched": matched_total,
        "detection_recall": round(recall, 4),
        "detection_precision": round(precision, 4),
        "causes": dict(causes.most_common()),
        "causes_by_regime": {
            regime: dict(Counter(m.cause for m in misses if m.regime == regime).most_common())
            for regime in sorted({m.regime for m in misses})
        },
        "misses": [m.as_dict() for m in misses],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--pdf", default="", help="Só as páginas cujo nome de PDF contenha isto.")
    parser.add_argument("--dump", action="store_true", help="Grava um PNG por perda.")
    parser.add_argument("--no-trace", action="store_true", help="Pula o rastro completo (mais rápido).")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_dir = (args.out / f"recall_failures_{stamp}") if args.dump else None
    report = analyse(
        dpi=args.dpi,
        max_boards=args.max_boards,
        pdf_filter=args.pdf,
        dump_dir=dump_dir,
        trace=not args.no_trace,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"recall_failures_{stamp}.json"
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"\npaginas {report['pages']}  anotados {report['annotated']}  detectados {report['detected']}  "
        f"casados {report['matched']}"
    )
    print(f"recall {report['detection_recall']:.4f}   precisao {report['detection_precision']:.4f}\n")
    print(f"{'causa':<26}{'perdas':>7}")
    for cause, count in report["causes"].items():
        print(f"{cause:<26}{count:>7}")
    print()
    for miss in report["misses"]:
        print(f"  {miss['pdf'][:44]:<44} p{miss['page']:<4} {miss['regime']:<16} {miss['cause']:<22} {miss['detail']}")
    if dump_dir is not None:
        print(f"\npngs -> {dump_dir}")
    print(f"report -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
