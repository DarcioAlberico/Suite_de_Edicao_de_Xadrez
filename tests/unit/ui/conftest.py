"""Fixtures para a frente da interface (F9).

**Estes testes leem o tronco, e o tronco não é uma dependência declarada.** A interface do
produto mora em `ChessVisionOFF_Puro/src/chess_diagram_ocr`, que a ADR-0009 mantém como o
frontend PyQt6 do projeto e que a suíte **não** instala. Então o caminho dele entra em
`sys.path` aqui, uma vez, e o teste que não o encontrar **pula com o motivo** -- em vez de
passar contra um duplo e não dizer nada.

**Nada aqui importa Qt, e é o ponto do arranjo.** O venv desta suíte não tem binding de Qt
nenhum: foi por isso que a folha de estilo e o mapa da paleta mudaram de `qt/` para `ui/` na
F9. O que estes testes afirmam -- contraste, cascata, aritmética de quadro, fronteira de
toolkit -- é afirmável sem abrir janela, e é isso que faz o portão do §11.3 rodar na CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
"""Onde o frontend mora. Absoluto porque o tronco é um repositório vizinho e não um pacote."""


def _preparar_o_caminho() -> bool:
    fonte = TRONCO / "src"
    if not (fonte / "chess_diagram_ocr" / "ui" / "folha_de_estilo.py").exists():
        return False
    if str(fonte) not in sys.path:
        sys.path.insert(0, str(fonte))
    return True


TRONCO_PRESENTE = _preparar_o_caminho()

pytestmark = pytest.mark.skipif(
    not TRONCO_PRESENTE,
    reason=f"o frontend do tronco não está em {TRONCO / 'src'}; ver docs/ASSETS.md §1",
)


@pytest.fixture(scope="session")
def raiz_do_tronco() -> Path:
    """A raiz do repositório do frontend, para os testes que varrem arquivos."""
    return TRONCO
