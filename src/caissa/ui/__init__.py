"""The suite's own interface pieces.

The product window is the trunk's (``ChessVisionOFF_Puro/app_pyqt.py``, ADR-0009);
what lives here are views the trunk mounts as tabs, written against the same
PyQt6 and the same rule the trunk keeps — the toolkit paints, the decisions
live in toolkit-free modules (:mod:`caissa.ocr.labeling`, :mod:`caissa.ocr.training`).
"""
