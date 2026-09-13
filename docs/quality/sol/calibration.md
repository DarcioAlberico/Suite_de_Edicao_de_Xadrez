# Sol · calibração por faceta (SOL-4)

> 2026-09-13T08:12:56+00:00 · corpus `6768f5a26d93783a` · partição `calib` · 8496 palavras alinhadas

| chave | n | ECE antes | ECE depois | Brier antes | Brier depois |
|---|--:|--:|--:|--:|--:|
| `tesseract` | 8496 | 0.0341 | 0.0093 | 0.0606 | 0.0596 |
| `tesseract|lang=eng` | 2869 | 0.0351 | 0.0066 | 0.0587 | 0.0575 |
| `tesseract|lang=eng|script=latin` | 2869 | 0.0351 | 0.0066 | 0.0587 | 0.0575 |
| `tesseract|lang=eng|script=latin|dpi=300` | 1766 | 0.0367 | 0.0134 | 0.0660 | 0.0648 |
| `tesseract|lang=eng|script=latin|dpi=300|kind=movetext` | 1195 | 0.0489 | 0.0192 | 0.0661 | 0.0642 |
| `tesseract|lang=eng|script=latin|dpi=300|kind=paragraph` | 571 | 0.0196 | 0.0099 | 0.0656 | 0.0609 |
| `tesseract|lang=eng|script=latin|dpi=low` | 1103 | 0.0412 | 0.0121 | 0.0472 | 0.0459 |
| `tesseract|lang=eng|script=latin|dpi=low|kind=movetext` | 704 | 0.0455 | 0.0218 | 0.0501 | 0.0501 |
| `tesseract|lang=eng|script=latin|dpi=low|kind=paragraph` | 399 | 0.0589 | 0.0259 | 0.0421 | 0.0392 |
| `tesseract|lang=por` | 5004 | 0.0377 | 0.0111 | 0.0559 | 0.0548 |
| `tesseract|lang=por|script=latin` | 5004 | 0.0377 | 0.0111 | 0.0559 | 0.0548 |
| `tesseract|lang=por|script=latin|dpi=300` | 3388 | 0.0441 | 0.0117 | 0.0595 | 0.0581 |
| `tesseract|lang=por|script=latin|dpi=300|kind=movetext` | 1959 | 0.0429 | 0.0158 | 0.0629 | 0.0613 |
| `tesseract|lang=por|script=latin|dpi=300|kind=paragraph` | 1429 | 0.0489 | 0.0222 | 0.0549 | 0.0548 |
| `tesseract|lang=por|script=latin|dpi=low` | 1616 | 0.0251 | 0.0078 | 0.0481 | 0.0472 |
| `tesseract|lang=por|script=latin|dpi=low|kind=movetext` | 956 | 0.0306 | 0.0146 | 0.0470 | 0.0459 |
| `tesseract|lang=por|script=latin|dpi=low|kind=paragraph` | 660 | 0.0228 | 0.0239 | 0.0498 | 0.0485 |
| `tesseract|lang=rus` | 337 | 0.1526 | 0.0586 | 0.1343 | 0.0732 |
| `tesseract|lang=rus|script=cyrillic` | 184 | 0.1505 | 0.0439 | 0.1199 | 0.0548 |
| `tesseract|lang=rus|script=cyrillic|dpi=300` | 113 | 0.1466 | 0.0346 | 0.0962 | 0.0558 |
| `tesseract|lang=rus|script=cyrillic|dpi=300|kind=movetext` | 113 | 0.1466 | 0.0346 | 0.0962 | 0.0558 |
| `tesseract|lang=rus|script=cyrillic|dpi=low` | 71 | 0.2185 | 0.0269 | 0.1576 | 0.0423 |
| `tesseract|lang=rus|script=cyrillic|dpi=low|kind=movetext` | 71 | 0.2185 | 0.0269 | 0.1576 | 0.0423 |
| `tesseract|lang=rus|script=latin` | 153 | 0.1551 | 0.0762 | 0.1517 | 0.0696 |
| `tesseract|lang=rus|script=latin|dpi=300` | 76 | 0.1335 | 0.0848 | 0.1351 | 0.0707 |
| `tesseract|lang=rus|script=latin|dpi=300|kind=paragraph` | 76 | 0.1335 | 0.0848 | 0.1351 | 0.0707 |
| `tesseract|lang=rus|script=latin|dpi=low` | 77 | 0.1764 | 0.1033 | 0.1680 | 0.0837 |
| `tesseract|lang=rus|script=latin|dpi=low|kind=paragraph` | 77 | 0.1764 | 0.1033 | 0.1680 | 0.0837 |
| `tesseract|lang=spa` | 286 | 0.0498 | 0.0322 | 0.0761 | 0.0752 |
| `tesseract|lang=spa|script=latin` | 286 | 0.0498 | 0.0322 | 0.0761 | 0.0752 |
| `tesseract|lang=spa|script=latin|dpi=300` | 179 | 0.0628 | 0.0451 | 0.0843 | 0.0839 |
| `tesseract|lang=spa|script=latin|dpi=300|kind=movetext` | 179 | 0.0628 | 0.0451 | 0.0843 | 0.0839 |
| `tesseract|lang=spa|script=latin|dpi=low` | 107 | 0.0637 | 0.0585 | 0.0625 | 0.0618 |
| `tesseract|lang=spa|script=latin|dpi=low|kind=movetext` | 107 | 0.0637 | 0.0585 | 0.0625 | 0.0618 |

Tabelas em `src\caissa\ocr\data\calibration.json`; recalibrar com `python benchmarks/calibrate_sol.py`.
