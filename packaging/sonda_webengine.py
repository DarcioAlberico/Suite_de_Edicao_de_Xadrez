r"""A sonda congelada do WebEngine — o passo H1 do Editor HTML/CSS (tarefas 3b, 3c e 3d).

O Chromium como **componente**: o pacote (o PyInstaller do `build_windows.py`) leva o PyQt6 no
`_internal\` e **não** leva o WebEngine; o WebEngine mora em `runtime\webengine\`, ao lado do
`.exe` — o componente sob demanda do H14 —, ligado por `PyQt6.__path__`, `os.add_dll_directory`,
o `PATH` do processo e as variáveis `QTWEBENGINEPROCESS_PATH`, `QTWEBENGINE_RESOURCES_PATH` e
`QTWEBENGINE_LOCALES_PATH`. A sonda desenha a fixture num PNG e grava num JSON os caminhos das DLL
carregadas — as dela e as do `QtWebEngineProcess` —, para o portão conferir que as do WebEngine
vieram de `runtime\webengine\`. **Sem o componente, ela desenha pelo MuPDF, e diz.**

**A instalação atômica** (3d): `--instalar <site-packages com o WebEngine>` copia o componente para
`runtime\webengine.parcial\` e só no fim o renomeia para `runtime\webengine\`; a instalação que cai
no meio (`--abortar-apos N`, a sabotagem) apaga a parcial; `--remover` tira o componente.

**O componente** é o das rodas `PyQt6-WebEngine` e `PyQt6-WebEngine-Qt6` (os `RECORD` delas),
**aparado** (sem os `.pak` de depuração e das ferramentas do desenvolvedor, sem as traduções além
de pt-BR e en-US, sem o Qt Quick do WebEngine, sem os arquivos de desenvolvimento) — `--inteiro`
leva tudo —, mais o Qt base que o WebEngine usa e o pacote não leva: as DLL (pelas importações do
PE, com o `pefile` do PyInstaller) e os módulos do PyQt6 que ele importa ao carregar.

Uso (o `.exe` congelado, ou este arquivo com um Python que tenha o PyQt6)::

    sonda_webengine.exe --saida <pasta>
    python packaging\sonda_webengine.py --raiz <pasta do .exe> --saida <pasta>
    python packaging\sonda_webengine.py --instalar <site-packages> --raiz <pasta do .exe> `
        --pacote <pasta do .exe>\_internal [--abortar-apos 40]
    python packaging\sonda_webengine.py --remover --raiz <pasta do .exe>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

RODAS = ("pyqt6_webengine", "pyqt6_webengine_qt6")
TRADUCOES = ("pt-BR.pak", "en-US.pak")
MODULOS_DO_WEBENGINE = ("QtWebEngineCore", "QtWebEngineWidgets", "QtNetwork", "QtPrintSupport",
                        "QtWebChannel")
"""Os módulos do PyQt6 que o `import PyQt6.QtWebEngineWidgets` carrega além do núcleo."""
RAIZES_DO_PE = ("Qt6WebEngineCore.dll", "Qt6WebEngineWidgets.dll", "QtWebEngineProcess.exe")
BANDEIRAS = "--disable-gpu --disable-gpu-compositing"
CLARO = 200
"""O canal abaixo disto é tinta: a página em branco não tem nenhum."""
PIXELS_DE_DESENHO = 20
"""Os pixels de tinta (na amostra de 1 em 16) que o desenho de verdade passa."""
FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR" xml:lang="pt-BR">
<head><title>A sonda</title>
<style>body { margin: 16px; font: 18px serif; } .caixa { background: #1f5f9f; color: #fff;
padding: 12px; width: 300px; }</style></head>
<body><h1>A sonda do WebEngine</h1>
<p class="caixa">Um parágrafo numa caixa azul, desenhado pelo Chromium do componente.</p>
</body></html>
"""


# --------------------------------------------------------------------------- #
# O componente: o que ele leva, e a instalação atômica
# --------------------------------------------------------------------------- #


def _corte(nome: str) -> str | None:
    base = nome.rsplit("/", 1)[-1]
    if base.endswith(".debug.pak") or "devtools" in base:
        return "depuração"
    if "/qtwebengine_locales/" in nome and base not in TRADUCOES:
        return "traduções"
    if "Quick" in base or "/qml/" in nome:
        return "Qt Quick"
    if base.endswith(".pyi") or "/bindings/" in nome or "/qsci/" in nome or ".dist-info/" in nome:
        return "desenvolvimento"
    return None


def _arquivos_das_rodas(origem: Path, *, inteiro: bool) -> list[str]:
    arquivos = []
    for info in sorted(origem.glob("*.dist-info")):
        nome = info.name.removesuffix(".dist-info").rpartition("-")[0].lower()
        if nome not in RODAS:
            continue
        with (info / "RECORD").open(encoding="utf-8") as registro:
            arquivos.extend(linha[0] for linha in csv.reader(registro)
                            if linha and linha[0].startswith("PyQt6/")
                            and (inteiro or _corte(linha[0]) is None))
    return arquivos


def _fecho_das_dll(binarios: Path) -> set[str]:
    """As DLL de `binarios` que o WebEngine importa, direta ou indiretamente (o PE de cada uma)."""
    vistas: set[str] = set()
    fila = [binarios / n for n in RAIZES_DO_PE]
    fila += [binarios.parents[1] / f"{m}.pyd" for m in MODULOS_DO_WEBENGINE]
    while fila:
        arquivo = fila.pop()
        if not arquivo.is_file():
            continue
        import pefile  # o do PyInstaller: só quando há binário a ler

        pe = pefile.PE(str(arquivo), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        for importada in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            nome = importada.dll.decode("ascii", "replace")
            if (binarios / nome).is_file() and nome not in vistas:
                vistas.add(nome)
                fila.append(binarios / nome)
    return vistas


def componente(origem: Path, pacote: Path | None, *, inteiro: bool = False) -> list[str]:
    r"""Os arquivos do componente, relativos a `origem` (o `site-packages` com o WebEngine).

    As rodas do WebEngine (aparadas, salvo `inteiro`), e o Qt base que o WebEngine usa e o
    `pacote` (o `_internal\` do `.exe`) não leva — as DLL pelo PE e os módulos do PyQt6.
    """
    arquivos = _arquivos_das_rodas(origem, inteiro=inteiro)
    binarios = origem / "PyQt6" / "Qt6" / "bin"
    no_pacote = set()
    if pacote is not None:
        no_pacote = {p.name for p in (pacote / "PyQt6" / "Qt6" / "bin").glob("*")} | {
            p.name for p in (pacote / "PyQt6").glob("*.pyd")}
    # O Qt base que o PE do WebEngine importa vai sempre (o Qt Quick também: o Qt6WebEngineCore
    # o importa); o corte vale só para o que as rodas do WebEngine trazem de opcional.
    for dll in sorted(_fecho_das_dll(binarios)):
        caminho = f"PyQt6/Qt6/bin/{dll}"
        if dll not in no_pacote and caminho not in arquivos:
            arquivos.append(caminho)
    for modulo in MODULOS_DO_WEBENGINE:
        pyd = f"PyQt6/{modulo}.pyd"
        if f"{modulo}.pyd" not in no_pacote and pyd not in arquivos and (origem / pyd).is_file():
            arquivos.append(pyd)
    return arquivos


class _Abortada(RuntimeError):  # noqa: N818 - a queda de propósito, não um erro
    """A instalação que caiu no meio (a sabotagem `--abortar-apos`)."""


def instalar(origem: Path, raiz: Path, *, pacote: Path | None = None, inteiro: bool = False,
             abortar_apos: int | None = None) -> dict[str, Any]:
    r"""Copia o componente para `runtime\webengine.parcial\` e só no fim o renomeia.

    Raises:
        _Abortada: A sabotagem mandou cair depois de `abortar_apos` arquivos (a parcial já
            foi apagada quando ela sobe).
    """
    runtime = raiz / "runtime"
    parcial, final = runtime / "webengine.parcial", runtime / "webengine"
    if parcial.exists():
        shutil.rmtree(parcial)
    arquivos = componente(origem, pacote, inteiro=inteiro)
    total = 0
    try:
        for indice, relativo in enumerate(arquivos):
            if abortar_apos is not None and indice >= abortar_apos:
                raise _Abortada(f"a instalação caiu depois de {indice} arquivos")
            alvo = parcial / relativo
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem / relativo, alvo)
            total += alvo.stat().st_size
    except BaseException:
        shutil.rmtree(parcial, ignore_errors=True)
        raise
    if final.exists():
        shutil.rmtree(final)
    parcial.rename(final)
    return {"arquivos": len(arquivos), "mb": round(total / 1e6, 1), "pasta": str(final)}


def remover(raiz: Path) -> bool:
    final = raiz / "runtime" / "webengine"
    if not final.exists():
        return False
    shutil.rmtree(final)
    return True


# --------------------------------------------------------------------------- #
# A sonda: ligar o componente, desenhar, e as DLL carregadas
# --------------------------------------------------------------------------- #


def raiz_padrao() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def ligar_componente(raiz: Path) -> Path | None:
    r"""Liga o WebEngine de `runtime\webengine\`, se ele está lá; devolve a pasta dele."""
    pasta = raiz / "runtime" / "webengine"
    if not (pasta / "PyQt6" / "QtWebEngineWidgets.pyd").is_file():
        return None
    import PyQt6

    PyQt6.__path__.append(str(pasta / "PyQt6"))
    qt = pasta / "PyQt6" / "Qt6"
    binarios = qt / "bin"
    os.add_dll_directory(str(binarios))
    os.environ["PATH"] = str(binarios) + os.pathsep + os.environ.get("PATH", "")
    os.environ["QTWEBENGINEPROCESS_PATH"] = str(binarios / "QtWebEngineProcess.exe")
    os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(qt / "resources")
    os.environ["QTWEBENGINE_LOCALES_PATH"] = str(qt / "translations" / "qtwebengine_locales")
    return pasta


def _kernel() -> tuple[Any, Any, Any]:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                           wintypes.DWORD]
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR,
                                           wintypes.DWORD]
    return ctypes, k32, psapi


def modulos_do_processo(pid: int) -> list[str]:
    """Os caminhos dos módulos (DLL e o executável) carregados num processo."""
    ctypes, k32, psapi = _kernel()
    from ctypes import wintypes

    alca = k32.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
    if not alca:
        return []
    try:
        lista = (wintypes.HMODULE * 4096)()
        precisa = wintypes.DWORD()
        if not psapi.EnumProcessModulesEx(alca, lista, ctypes.sizeof(lista), ctypes.byref(precisa),
                                          0x03):  # LIST_MODULES_ALL
            return []
        buffer = ctypes.create_unicode_buffer(32768)
        nomes = []
        for indice in range(min(precisa.value // ctypes.sizeof(wintypes.HMODULE), 4096)):
            if psapi.GetModuleFileNameExW(alca, lista[indice], buffer, 32768):
                nomes.append(buffer.value)  # noqa: PERF401 - o buffer é reusado a cada volta
        return nomes
    finally:
        k32.CloseHandle(alca)


def processos_filhos(pid: int) -> list[tuple[int, str]]:
    """Os filhos diretos de um processo: o `QtWebEngineProcess` da sonda."""
    ctypes, k32, _ = _kernel()
    from ctypes import wintypes

    class Entrada(ctypes.Structure):
        _fields_ = [  # noqa: RUF012 - a forma do ctypes
                    ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entrada)]
    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entrada)]
    foto = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    filhos = []
    try:
        entrada = Entrada()
        entrada.dwSize = ctypes.sizeof(Entrada)
        continua = k32.Process32FirstW(foto, ctypes.byref(entrada))
        while continua:
            if entrada.th32ParentProcessID == pid:
                filhos.append((int(entrada.th32ProcessID), entrada.szExeFile))
            continua = k32.Process32NextW(foto, ctypes.byref(entrada))
    finally:
        k32.CloseHandle(foto)
    return filhos


def _em_branco(png: Path) -> bool:
    from PyQt6.QtGui import QImage

    imagem = QImage(str(png))
    if imagem.isNull():
        return True
    pixels = 0
    for y in range(0, imagem.height(), 4):
        for x in range(0, imagem.width(), 4):
            cor = imagem.pixelColor(x, y)
            if min(cor.red(), cor.green(), cor.blue()) < CLARO:
                pixels += 1
    return pixels < PIXELS_DE_DESENHO


def desenhar_chromium(fixture: Path, png: Path) -> dict[str, Any]:
    """A fixture pelo `QWebEngineView` fora da tela, com as DLL da sonda e do processo web."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = BANDEIRAS
    from PyQt6.QtCore import QEventLoop, QTimer, QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    vista = QWebEngineView()
    vista.resize(640, 480)
    vista.show()
    laco = QEventLoop()
    carregou: dict[str, bool] = {}

    def fim(ok: bool) -> None:
        carregou["ok"] = ok
        laco.quit()

    vista.loadFinished.connect(fim)
    vista.load(QUrl.fromLocalFile(str(fixture)))
    QTimer.singleShot(30000, laco.quit)
    laco.exec()
    for _ in range(20):  # o quadro chega depois do loadFinished
        espera = QEventLoop()
        QTimer.singleShot(100, espera.quit)
        espera.exec()
    vista.grab().save(str(png))
    filhos = processos_filhos(os.getpid())
    registro = {"carregou": bool(carregou.get("ok")),
                "dlls_da_sonda": modulos_do_processo(os.getpid()),
                "processos_web": [{"pid": pid, "exe": exe, "dlls": modulos_do_processo(pid)}
                                  for pid, exe in filhos if "webengine" in exe.lower()]}
    vista.close()
    app.processEvents()
    return registro


def desenhar_mupdf(fixture: Path, png: Path) -> dict[str, Any]:
    """A reserva: a fixture pelo `Story` do MuPDF."""
    import io

    import pymupdf

    historia = pymupdf.Story(html=fixture.read_text(encoding="utf-8"))
    saida = io.BytesIO()
    escritor = pymupdf.DocumentWriter(saida)
    dispositivo = escritor.begin_page(pymupdf.Rect(0, 0, 480, 360))
    historia.place(pymupdf.Rect(12, 12, 468, 348))
    historia.draw(dispositivo)
    escritor.end_page()
    escritor.close()
    with pymupdf.open("pdf", saida.getvalue()) as documento:
        documento[0].get_pixmap(dpi=96).save(str(png))
    return {"carregou": True, "dlls_da_sonda": modulos_do_processo(os.getpid()),
            "processos_web": []}


def sondar(raiz: Path, saida: Path) -> dict[str, Any]:
    saida.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix="caissa_sonda_")) / "sonda.xhtml"
    fixture.write_text(FIXTURE, encoding="utf-8")
    png = saida / "sonda.png"
    componente_ligado = ligar_componente(raiz)
    inicio = time.perf_counter()
    try:
        if componente_ligado is not None:
            registro = {"motor": "chromium", **desenhar_chromium(fixture, png)}
        else:
            registro = {"motor": "mupdf", **desenhar_mupdf(fixture, png)}
    except Exception as falha:  # noqa: BLE001 - a sonda diz como caiu, no JSON
        registro = {"motor": "nenhum", "erro": f"{type(falha).__name__}: {falha}"}
    registro["segundos"] = round(time.perf_counter() - inicio, 2)
    registro["componente"] = str(componente_ligado) if componente_ligado else None
    registro["congelada"] = bool(getattr(sys, "frozen", False))
    registro["png"] = str(png)
    registro["png_em_branco"] = _em_branco(png) if png.is_file() else True
    if componente_ligado is not None:
        pasta = str(componente_ligado).lower()
        web = [d for d in registro.get("dlls_da_sonda", []) if "webengine" in d.lower()]
        web += [p["exe"] for p in registro.get("processos_web", [])]
        web += [d for p in registro.get("processos_web", []) for d in p["dlls"]
                if "webengine" in d.lower()]
        registro["dlls_do_webengine"] = sorted(set(web))
        registro["webengine_de_fora"] = sorted(
            d for d in set(web) if "\\" in d and not d.lower().startswith(pasta))
    (saida / "sonda.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return registro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=None)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--instalar", type=Path, metavar="SITE_PACKAGES")
    parser.add_argument("--pacote", type=Path)
    parser.add_argument("--inteiro", action="store_true")
    parser.add_argument("--abortar-apos", type=int)
    parser.add_argument("--remover", action="store_true")
    args = parser.parse_args(argv)
    raiz = args.raiz or raiz_padrao()
    if args.remover:
        print(json.dumps({"removido": remover(raiz)}))
        return 0
    if args.instalar is not None:
        try:
            print(json.dumps(instalar(args.instalar, raiz, pacote=args.pacote,
                                      inteiro=args.inteiro, abortar_apos=args.abortar_apos),
                             ensure_ascii=False))
        except _Abortada as falha:
            restos = sorted(p.name for p in (raiz / "runtime").glob("webengine*"))
            print(json.dumps({"abortada": str(falha), "restos": restos}, ensure_ascii=False))
            return 1
        return 0
    if args.saida is None:
        parser.error("--saida é obrigatório para sondar")
    registro = sondar(raiz, args.saida)
    resumo = {k: registro.get(k) for k in ("motor", "carregou", "png_em_branco", "componente",
                                            "webengine_de_fora", "erro", "segundos")}
    print(json.dumps(resumo, ensure_ascii=False))
    ok = registro.get("motor") in ("chromium", "mupdf") and not registro.get("png_em_branco") \
        and not registro.get("webengine_de_fora")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
