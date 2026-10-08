"""Gravar sem deixar arquivo pela metade: temporário, `fsync` e `os.replace` (spec S2, R2.8).

O destino termina com um de dois conteúdos, nunca um terceiro: o anterior (ou nada) ou o novo,
inteiro. É a mesma técnica de `ingest.pdf.save.save_document_atomically`, para texto e bytes:
o parcial nasce **ao lado** do destino (o `os.replace` só é atômico no mesmo volume), com o PID no
nome, e é apagado em qualquer falha.

**Por que o parcial tem o PID.** Um processo morto no meio de uma gravação deixa o parcial dele;
o `limpar_parciais` da próxima abertura apaga só os de processos que não vivem mais — o de uma
janela viva, gravando agora, fica.

**O `PermissionError` do Windows.** Um antivírus ou um indexador abrindo o destino por um instante
faz o `os.replace` falhar; a gravação tenta de novo por até meio segundo antes de desistir. Quem
desiste diz o que houve (o erro sobe): a regra do anti-padrão 4 é não engolir.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

SUFIXO_PARCIAL = ".parcial"
TENTATIVAS_DE_TROCA = 10
PAUSA_ENTRE_TENTATIVAS_S = 0.05


def caminho_parcial(destino: Path, pid: int | None = None) -> Path:
    return destino.with_name(f".{destino.name}.{pid or os.getpid()}{SUFIXO_PARCIAL}")


def gravar_atomico(destino: Path | str, dados: bytes | str) -> None:
    """Grava `dados` em `destino` de uma vez: quem ler depois vê o antigo ou o novo, inteiro."""
    alvo = Path(destino)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    conteudo = dados.encode("utf-8") if isinstance(dados, str) else dados
    parcial = caminho_parcial(alvo)
    try:
        with parcial.open("wb") as saida:
            saida.write(conteudo)
            saida.flush()
            os.fsync(saida.fileno())
        _trocar(parcial, alvo)
    except BaseException:
        # BaseException: um KeyboardInterrupt no meio deixa o mesmo lixo que um OSError.
        parcial.unlink(missing_ok=True)
        raise


def _trocar(parcial: Path, alvo: Path) -> None:
    for tentativa in range(TENTATIVAS_DE_TROCA):
        try:
            parcial.replace(alvo)
            return
        except PermissionError:
            if tentativa == TENTATIVAS_DE_TROCA - 1:
                raise
            time.sleep(PAUSA_ENTRE_TENTATIVAS_S)


def limpar_parciais(pasta: Path, processo_vivo: Callable[[int], bool]) -> list[Path]:
    """Apaga os parciais de processos mortos sob `pasta`; devolve o que apagou.

    `processo_vivo` vem de `editor.trava` (injetado para o teste).
    """
    apagados: list[Path] = []
    if not pasta.is_dir():
        return apagados
    for parcial in pasta.rglob(f".*{SUFIXO_PARCIAL}"):
        _, _, pid = parcial.name[: -len(SUFIXO_PARCIAL)].rpartition(".")
        if not pid.isdigit() or processo_vivo(int(pid)):
            continue
        parcial.unlink(missing_ok=True)
        apagados.append(parcial)
    return apagados
