"""A sonda do WebEngine (Editor HTML/CSS, H1, tarefas 3b e 3d): o componente e a instalação.

Com rodas de mentira: o que o componente aparado leva e deixa, a instalação atômica (a pasta
parcial que só no fim vira `runtime/webengine`), a instalação que cai no meio (a parcial apagada,
nada instalado), a remoção, e a ligação do componente (num processo à parte: ela mexe no
`PyQt6.__path__` e no ambiente). A sonda de verdade, com o WebEngine e o PyInstaller, é o portão
do H1.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "packaging"))
import sonda_webengine as sonda  # noqa: E402

ARQUIVOS_DAS_RODAS = {
    "pyqt6_webengine-6.11.0": [
        "PyQt6/QtWebEngineCore.pyd", "PyQt6/QtWebEngineWidgets.pyd",
        "PyQt6/QtWebEngineCore.pyi", "PyQt6/bindings/QtWebEngineCore/x.sip",
        "PyQt6/QtWebEngineQuick.pyd"],
    "pyqt6_webengine_qt6-6.11.2": [
        "PyQt6/Qt6/bin/Qt6WebEngineCore.dll", "PyQt6/Qt6/bin/QtWebEngineProcess.exe",
        "PyQt6/Qt6/bin/Qt6WebEngineQuick.dll", "PyQt6/Qt6/resources/qtwebengine_resources.pak",
        "PyQt6/Qt6/resources/qtwebengine_resources.debug.pak",
        "PyQt6/Qt6/resources/qtwebengine_devtools_resources.pak",
        "PyQt6/Qt6/translations/qtwebengine_locales/pt-BR.pak",
        "PyQt6/Qt6/translations/qtwebengine_locales/en-US.pak",
        "PyQt6/Qt6/translations/qtwebengine_locales/de.pak",
        "PyQt6/Qt6/qml/QtWebEngine/qmldir"],
}


@pytest.fixture
def origem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `site-packages` de mentira com as duas rodas e os `RECORD` delas.

    O fecho das DLL pelo PE (o `pefile`, sobre binários de verdade) é do portão; aqui ele é o
    `Qt6Quick.dll` do Qt base, que o Qt6WebEngineCore importa.
    """
    monkeypatch.setattr(sonda, "_fecho_das_dll", lambda _binarios: {"Qt6Quick.dll"})
    pacotes = tmp_path / "site-packages"
    (pacotes / "PyQt6" / "Qt6" / "bin").mkdir(parents=True)
    (pacotes / "PyQt6" / "Qt6" / "bin" / "Qt6Quick.dll").write_bytes(b"x" * 10)
    for roda, arquivos in ARQUIVOS_DAS_RODAS.items():
        info = pacotes / f"{roda}.dist-info"
        info.mkdir(parents=True)
        with (info / "RECORD").open("w", encoding="utf-8", newline="") as registro:
            escritor = csv.writer(registro)
            for relativo in arquivos:
                arquivo = pacotes / relativo
                arquivo.parent.mkdir(parents=True, exist_ok=True)
                arquivo.write_bytes(b"x" * 10)
                escritor.writerow([relativo, "sha256=", "10"])
    return pacotes


def test_o_componente_aparado_deixa_a_depuracao_as_traducoes_e_o_quick(origem: Path) -> None:
    aparado = set(sonda.componente(origem, None))
    assert {"PyQt6/QtWebEngineCore.pyd", "PyQt6/QtWebEngineWidgets.pyd",
            "PyQt6/Qt6/bin/Qt6WebEngineCore.dll", "PyQt6/Qt6/bin/QtWebEngineProcess.exe",
            "PyQt6/Qt6/resources/qtwebengine_resources.pak",
            "PyQt6/Qt6/translations/qtwebengine_locales/pt-BR.pak",
            "PyQt6/Qt6/translations/qtwebengine_locales/en-US.pak"} <= aparado
    for fora in ("qtwebengine_resources.debug.pak", "qtwebengine_devtools_resources.pak",
                 "de.pak", "Qt6WebEngineQuick.dll", "QtWebEngineQuick.pyd", ".pyi", ".sip",
                 "qmldir"):
        assert not any(a.endswith(fora) for a in aparado), fora
    assert "PyQt6/Qt6/bin/Qt6Quick.dll" in aparado, "o Qt base do fecho vai, mesmo com Quick"
    pacote = origem.parent / "_internal"
    (pacote / "PyQt6" / "Qt6" / "bin").mkdir(parents=True)
    (pacote / "PyQt6" / "Qt6" / "bin" / "Qt6Quick.dll").write_bytes(b"x")
    assert "PyQt6/Qt6/bin/Qt6Quick.dll" not in sonda.componente(origem, pacote), (
        "o que o pacote já leva não vai no componente")
    inteiro = set(sonda.componente(origem, None, inteiro=True))
    assert aparado < inteiro
    assert "PyQt6/Qt6/translations/qtwebengine_locales/de.pak" in inteiro


def test_a_instalacao_e_atomica(origem: Path, tmp_path: Path) -> None:
    raiz = tmp_path / "Caissa"
    resultado = sonda.instalar(origem, raiz)
    assert resultado["arquivos"] == len(sonda.componente(origem, None))
    assert (raiz / "runtime" / "webengine" / "PyQt6" / "QtWebEngineWidgets.pyd").is_file()
    assert not (raiz / "runtime" / "webengine.parcial").exists()


def test_a_instalacao_que_cai_no_meio_nao_deixa_nada(origem: Path, tmp_path: Path) -> None:
    raiz = tmp_path / "Caissa"
    with pytest.raises(sonda._Abortada):
        sonda.instalar(origem, raiz, abortar_apos=2)
    assert sorted(p.name for p in (raiz / "runtime").glob("webengine*")) == []
    assert sonda.ligar_componente(raiz) is None, "sem o componente, a sonda cai no MuPDF"


def test_a_remocao_tira_o_componente(origem: Path, tmp_path: Path) -> None:
    raiz = tmp_path / "Caissa"
    sonda.instalar(origem, raiz)
    assert sonda.remover(raiz)
    assert not (raiz / "runtime" / "webengine").exists()
    assert not sonda.remover(raiz)


def test_ligar_o_componente_aponta_tudo_para_a_pasta_dele(origem: Path, tmp_path: Path) -> None:
    raiz = tmp_path / "Caissa"
    sonda.instalar(origem, raiz)
    codigo = (
        "import json, os, sys; sys.path.insert(0, sys.argv[1]); import sonda_webengine as s; "
        "from pathlib import Path; pasta = s.ligar_componente(Path(sys.argv[2])); import PyQt6; "
        "print(json.dumps({'pasta': str(pasta), 'caminho': list(PyQt6.__path__), "
        "'processo': os.environ['QTWEBENGINEPROCESS_PATH'], "
        "'recursos': os.environ['QTWEBENGINE_RESOURCES_PATH'], "
        "'traducoes': os.environ['QTWEBENGINE_LOCALES_PATH'], "
        "'path': os.environ['PATH'].split(os.pathsep)[0]}))")
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, check=False).stdout.strip()
    candidatos = [RAIZ / ".venv-pack" / "Scripts" / "python.exe"]
    if comum:
        candidatos.append(Path(comum).parent / ".venv-pack" / "Scripts" / "python.exe")
    python = next((c for c in candidatos if c.is_file()), Path(sys.executable))
    saida = subprocess.run(  # noqa: S603 - um Python com o PyQt6, com um código nosso
        [str(python), "-c", codigo, str(RAIZ / "packaging"), str(raiz)],
        capture_output=True, text=True, check=False)
    if saida.returncode != 0 and "No module named 'PyQt6'" in saida.stderr:
        pytest.skip("sem o PyQt6 neste Python")
    dados = json.loads(saida.stdout)
    pasta = raiz / "runtime" / "webengine"
    assert dados["pasta"] == str(pasta)
    assert str(pasta / "PyQt6") in dados["caminho"]
    assert dados["processo"] == str(pasta / "PyQt6" / "Qt6" / "bin" / "QtWebEngineProcess.exe")
    assert dados["recursos"] == str(pasta / "PyQt6" / "Qt6" / "resources")
    assert dados["traducoes"].endswith("qtwebengine_locales")
    assert dados["path"] == str(pasta / "PyQt6" / "Qt6" / "bin")


def test_os_filhos_do_processo_aparecem() -> None:
    """A foto dos processos acha o filho (a sonda lista assim o `QtWebEngineProcess`): a estrutura
    do `PROCESSENTRY32W` inteira, com o `dwSize` — sem ele a foto não anda."""
    if sys.platform != "win32":
        pytest.skip("a foto dos processos é do Windows")
    filho = subprocess.Popen(  # noqa: S603 - o Python dos testes, dormindo
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        import os

        achados = sonda.processos_filhos(os.getpid())
        assert filho.pid in {pid for pid, _ in achados}
        assert any(nome.lower().endswith(".exe") for _, nome in achados)
    finally:
        filho.kill()
        filho.wait()
