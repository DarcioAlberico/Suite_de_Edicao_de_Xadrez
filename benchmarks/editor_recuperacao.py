r"""Nada se perde, sob queda de verdade — o portão do passo H6 (EDITOR_HTML_CSS_ROADMAP).

Os testes de `tests/unit/editor/test_projeto.py` provam cada regra com um caso à mão. Este arnês
prova as mesmas regras **com o processo morrendo**: um filho edita e grava num projeto enquanto o
pai o mata com `TerminateProcess` (o `Popen.kill` do Windows) num instante sorteado, 50 vezes, e
depois reabre o projeto como a janela reabriria.

**O que se exige** (roadmap H6):

1. **queda** (50×): o filho edita por 2,5–4 s (sorteado), anotando cada edição no diário, e
   então grava o arquivo grande; o pai o mata num instante sorteado **dentro** dessa gravação
   (entre 0 e a duração que o filho mediu gravando o mesmo arquivo na preparação). A reabertura
   recupera do diário o texto com no máximo 2 s de perda (o registro das edições diz quando cada
   uma aconteceu); o arquivo grande é o antigo ou o novo, **nunca truncado**; a trava do filho
   morto é retomada. Sortear a morte ao acaso no laço inteiro quase nunca a punha dentro da
   gravação — a sabotagem `escrita_direta` passava em 6 de 6 quedas assim;
2. **versões**: depois de 300 gravações de 1 MB o teto de 200 MB está mantido e as 20 últimas
   estão lá; com versões de 12 MB, as 20 últimas ficam mesmo passando do teto (o piso vence); a
   versão restaurada é idêntica byte a byte;
3. **trava**: com o livro aberto aqui, um segundo processo que tenta abri-lo é recusado;
4. **mudança por fora**: 20 mudanças diferentes feitas por outro programa, todas detectadas; o
   mesmo texto regravado não conta.

**Sabotagens** (`--sabotar`), cada uma tem de reprovar:
- `sem_diario`: o filho não anota (a perda passa de 2 s);
- `escrita_direta`: a gravação escreve direto no destino, sem temporário (o arquivo sai truncado);
- `sem_trava`: a trava não recusa ninguém (o segundo processo abre);
- `lru_sem_piso`: a poda ignora o piso (as 20 últimas não ficam).

Grava `recuperacao.json` e `metricas.json` na `--saida`; o projeto de cada ensaio nasce e morre
numa pasta dela — nunca no `editor/` do usuário.

Uso::

    & $PY benchmarks\editor_recuperacao.py --saida benchmarks\reports\editor\h6\1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

SABOTAGENS = ("sem_diario", "escrita_direta", "sem_trava", "lru_sem_piso")
DIARIO = "OEBPS/Text/diario.xhtml"
GRANDE = "OEBPS/Text/grande.xhtml"
PERDA_MAXIMA_S = 2.0
QUEDAS = 50
SEMENTE = 42
MB = 1024 * 1024
RECUSADO = 3            # código do filho quando a trava o recusa


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _texto(k: int) -> str:
    return f"<p>edição {k}</p>\n"


def _grande(k: int) -> bytes:
    linha = f"<p>gravação {k:08d} — o conteúdo grande que a queda pode cortar</p>\n".encode()
    return linha * (8 * MB // len(linha))


def aplicar_sabotagem(nome: str | None) -> None:
    """Liga o defeito no processo que chama (o pai e o filho chamam os dois)."""
    if not nome:
        return
    from caissa.editor import diario, projeto, trava, versoes

    if nome == "sem_diario":
        diario.Diario.anotar = lambda *_a, **_k: None  # type: ignore[method-assign]
    elif nome == "escrita_direta":
        def direta(destino: Path | str, dados: bytes | str) -> None:
            conteudo = dados.encode("utf-8") if isinstance(dados, str) else dados
            with Path(destino).open("wb") as saida:
                for inicio in range(0, len(conteudo), 64 * 1024):
                    saida.write(conteudo[inicio:inicio + 64 * 1024])
                    saida.flush()
        projeto.gravar_atomico = direta  # type: ignore[assignment]
    elif nome == "sem_trava":
        original = trava.Trava.adquirir.__func__  # type: ignore[attr-defined]

        def sem_recusa(cls: type, pasta: Path, **_k: Any) -> trava.Trava:
            (pasta / trava.NOME).unlink(missing_ok=True)
            return original(cls, pasta)
        trava.Trava.adquirir = classmethod(sem_recusa)  # type: ignore[method-assign, assignment]
    elif nome == "lru_sem_piso":
        original_podar = versoes.Versoes.podar

        def sem_piso(self: versoes.Versoes) -> list[str]:
            piso, self.piso = self.piso, 0
            try:
                return original_podar(self)
            finally:
                self.piso = piso
        versoes.Versoes.podar = sem_piso  # type: ignore[method-assign]


# --------------------------------------------------------------------------- #
# O filho
# --------------------------------------------------------------------------- #


def filho(raiz: Path, pdf: Path, registros: Path, espera: float, sabotagem: str | None) -> int:
    """Edita por `espera` segundos, anotando cada edição, e então grava o arquivo grande."""
    from caissa.editor.projeto import ProjetoDoEditor

    aplicar_sabotagem(sabotagem)
    projeto = ProjetoDoEditor.criar(pdf, raiz=raiz)
    projeto.gravar(DIARIO, _texto(0))
    edicoes = (registros / "edicoes.log").open("a", encoding="utf-8")
    grandes = (registros / "grandes.log").open("a", encoding="utf-8")
    conteudo = _grande(0)
    grandes.write(_sha(conteudo) + "\n")
    grandes.flush()
    inicio = time.perf_counter()
    projeto.gravar(GRANDE, conteudo.decode("utf-8"))
    duracao = time.perf_counter() - inicio          # a gravação que o pai vai interromper
    print(f"pronto {duracao:.4f}", flush=True)
    fim = time.time() + espera
    k = 0
    while time.time() < fim:
        k += 1
        edicoes.write(f"{k} {time.time():.6f}\n")
        edicoes.flush()
        projeto.anotar(DIARIO, _texto(k))
        time.sleep(0.05)
    conteudo = _grande(k)
    grandes.write(_sha(conteudo) + "\n")
    grandes.flush()
    print("gravando", flush=True)
    projeto.gravar(GRANDE, conteudo.decode("utf-8"))
    print("gravou", flush=True)
    while True:                                    # o pai mata; se chegar aqui, espera morrer
        time.sleep(1)


def filho_que_abre(raiz: Path, pdf: Path, sabotagem: str | None) -> int:
    from caissa.editor.projeto import ProjetoDoEditor
    from caissa.editor.trava import LivroJaAberto

    aplicar_sabotagem(sabotagem)
    try:
        with ProjetoDoEditor.abrir(pdf, raiz=raiz):
            print("abriu", flush=True)
            return 0
    except LivroJaAberto as recusa:
        print(f"recusado: {recusa}", flush=True)
        return RECUSADO


# --------------------------------------------------------------------------- #
# O pai
# --------------------------------------------------------------------------- #


def _pdf(destino: Path) -> Path:
    import pymupdf

    documento = pymupdf.open()
    for numero in range(4):
        documento.new_page().insert_text((72, 72), f"Livro do arnês, p. {numero + 1}")
    documento.save(str(destino))
    documento.close()
    return destino


def _comando(*argumentos: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), *argumentos]


def _esperar(processo: subprocess.Popen[str], palavra: str, prazo_s: float = 60.0) -> str | None:
    """A linha do filho que começa com `palavra` (avisos de biblioteca podem vir antes)."""
    assert processo.stdout is not None
    limite = time.monotonic() + prazo_s
    while time.monotonic() < limite:
        linha = processo.stdout.readline()
        if not linha:
            return None                    # o filho saiu antes
        if linha.strip().startswith(palavra):
            return linha.strip()
    return None


def uma_queda(ensaio: Path, pdf: Path, espera: float, fracao: float,
              sabotagem: str | None) -> dict[str, Any]:
    from caissa.editor.projeto import ProjetoDoEditor

    raiz = ensaio / "editor"
    ensaio.mkdir(parents=True, exist_ok=True)
    argumentos = ["--filho", str(raiz), str(pdf), str(ensaio), f"{espera:.3f}"]
    if sabotagem:
        argumentos += ["--sabotar", sabotagem]
    processo = subprocess.Popen(_comando(*argumentos), stdout=subprocess.PIPE,  # noqa: S603
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    pronto = _esperar(processo, "pronto")
    gravando = _esperar(processo, "gravando", prazo_s=espera + 60.0) if pronto else None
    if gravando is None:
        processo.kill()
        processo.wait()
        return {"erro": "o filho não chegou à gravação", "trava_retomada": False}
    duracao = float(pronto.split()[1])
    time.sleep(fracao * duracao)        # sorteado dentro da gravação
    processo.kill()                     # TerminateProcess
    morte = time.time()
    processo.wait()

    edicoes = []
    for registro in (ensaio / "edicoes.log").read_text(encoding="utf-8").splitlines():
        partes = registro.split()
        if len(partes) == 2:               # a última linha pode ter sido cortada pela morte
            edicoes.append((int(partes[0]), float(partes[1])))
    shas = set((ensaio / "grandes.log").read_text(encoding="utf-8").split())

    with ProjetoDoEditor.abrir(pdf, raiz=raiz) as projeto:      # a trava do morto é retomada
        recuperado = projeto.recuperar_do_diario()
        texto = (recuperado[DIARIO].texto if DIARIO in recuperado
                 else (projeto.pasta / DIARIO).read_text(encoding="utf-8"))
        grande = (projeto.pasta / GRANDE).read_bytes()
    recuperada = int(texto.split("edição ")[1].split("<")[0])
    seguinte = next((quando for numero, quando in edicoes if numero == recuperada + 1), None)
    perda = max(0.0, morte - seguinte) if seguinte is not None else 0.0
    shutil.rmtree(ensaio, ignore_errors=True)
    return {
        "espera_s": round(espera, 3),
        "morte_na_gravacao_s": round(fracao * duracao, 4),
        "duracao_da_gravacao_s": round(duracao, 4),
        "edicoes": len(edicoes),
        "recuperada": recuperada,
        "perda_s": round(perda, 3),
        "perda_ok": perda <= PERDA_MAXIMA_S,
        "grande_inteiro": _sha(grande) in shas,
        "trava_retomada": True,
    }


def quedas(pasta: Path, pdf: Path, vezes: int, sabotagem: str | None) -> dict[str, Any]:
    sorteio = random.Random(SEMENTE)
    ensaios = []
    for indice in range(vezes):
        espera = sorteio.uniform(2.5, 4.0)
        fracao = sorteio.uniform(0.0, 1.0)
        try:
            resultado = uma_queda(pasta / "ensaios" / str(indice), pdf, espera, fracao, sabotagem)
        except Exception as falha:  # noqa: BLE001 - a falha do ensaio é um dado, e fica dita
            resultado = {"erro": f"{type(falha).__name__}: {falha}", "trava_retomada": False}
        ensaios.append(resultado)
        print(f"  queda {indice + 1}/{vezes}: {resultado}", flush=True)
    return {
        "ensaios": ensaios,
        "perda_ok": sum(1 for e in ensaios if e.get("perda_ok")),
        "grande_inteiro": sum(1 for e in ensaios if e.get("grande_inteiro")),
        "trava_retomada": sum(1 for e in ensaios if e.get("trava_retomada") and "erro" not in e),
        "perda_maxima_s": max((e.get("perda_s", 0.0) for e in ensaios), default=0.0),
    }


def versoes(pasta: Path) -> dict[str, Any]:
    from caissa.editor.versoes import PISO, TETO_BYTES, Versoes

    arquivo = "OEBPS/Text/cap.xhtml"
    comum = Versoes(pasta / "versoes_1mb")
    carimbos = [comum.guardar(arquivo, bytes([n % 251]) * MB + n.to_bytes(4, "big"))
                for n in range(300)]
    presentes = {v.carimbo for v in comum.listar()}
    total = comum.total_bytes()
    alvo = carimbos[-7]
    restaurado = comum.ler(alvo, arquivo) == bytes([(300 - 7) % 251]) * MB + (300 - 7).to_bytes(
        4, "big")
    shutil.rmtree(pasta / "versoes_1mb", ignore_errors=True)

    grandes = Versoes(pasta / "versoes_12mb")
    ultimos = [grandes.guardar(arquivo, bytes([n]) * 12 * MB) for n in range(25)]
    presentes_grandes = {v.carimbo for v in grandes.listar()}
    shutil.rmtree(pasta / "versoes_12mb", ignore_errors=True)
    return {
        "gravacoes": 300,
        "total_mb": round(total / MB, 1),
        "teto_mantido": total <= TETO_BYTES,
        "ultimas_20_presentes": set(carimbos[-PISO:]) <= presentes,
        "restaurada_identica": restaurado,
        "piso_vence_o_teto": set(ultimos[-PISO:]) <= presentes_grandes,
    }


def trava(pasta: Path, pdf: Path, sabotagem: str | None) -> dict[str, Any]:
    from caissa.editor.projeto import ProjetoDoEditor

    raiz = pasta / "trava" / "editor"
    with ProjetoDoEditor.criar(pdf, raiz=raiz):
        argumentos = ["--filho-que-abre", str(raiz), str(pdf)]
        if sabotagem:
            argumentos += ["--sabotar", sabotagem]
        segundo = subprocess.run(_comando(*argumentos), capture_output=True, text=True,  # noqa: S603
                                 encoding="utf-8", check=False, timeout=120)
    shutil.rmtree(pasta / "trava", ignore_errors=True)
    return {"segunda_abertura": segundo.stdout.strip()[:200],
            "segunda_recusada": segundo.returncode == RECUSADO}


def _mudancas() -> list[tuple[str, Any]]:
    """As 20 mudanças por fora: cada uma recebe o caminho e muda o arquivo."""
    def trocar(novo: bytes, *, manter_data: bool = False) -> Any:
        def aplicar(caminho: Path) -> None:
            antes = caminho.stat()
            caminho.write_bytes(novo)
            if manter_data:
                os.utime(caminho, ns=(antes.st_atime_ns, antes.st_mtime_ns))
        return aplicar

    def acrescentar(caminho: Path) -> None:
        with caminho.open("ab") as saida:
            saida.write(b"<p>mais</p>")

    def apagar(caminho: Path) -> None:
        caminho.unlink()

    def trocar_por_outro(caminho: Path) -> None:
        outro = caminho.with_name("outro.tmp")
        outro.write_bytes(b"<p>outro arquivo</p>")
        outro.replace(caminho)

    base = b"<p>O texto do livro, com 1.\xe2\x99\x98f3 e acentos: a\xc3\xa7\xc3\xa3o.</p>\n"
    sorteio = random.Random(SEMENTE)
    casos: list[tuple[str, Any]] = [
        ("acrescenta", acrescentar),
        ("esvazia", trocar(b"")),
        ("mesmo_tamanho", trocar(base.replace(b"livro", b"LIVRO"))),
        ("mesmo_tamanho_data_antiga", trocar(base.replace(b"livro", b"LIVRO"), manter_data=True)),
        ("apaga", apagar),
        ("troca_por_rename", trocar_por_outro),
        ("bom", trocar(b"\xef\xbb\xbf" + base)),
        ("crlf", trocar(base.replace(b"\n", b"\r\n"))),
        ("um_caractere_no_meio", trocar(base[:20] + b"X" + base[21:])),
        ("ultimo_byte", trocar(base[:-1] + b" ", manter_data=True)),
    ]
    for numero in range(10):
        posicao = sorteio.randrange(len(base))
        mudado = base[:posicao] + bytes([base[posicao] ^ 0x20]) + base[posicao + 1:]
        casos.append((f"sorteado_{numero}", trocar(mudado, manter_data=numero % 2 == 0)))
    return casos


def mudancas_por_fora(pasta: Path, pdf: Path) -> dict[str, Any]:
    from caissa.editor.projeto import ProjetoDoEditor

    raiz = pasta / "fora" / "editor"
    arquivo = "OEBPS/Text/cap.xhtml"
    detectadas, casos = [], _mudancas()
    base = b"<p>O texto do livro, com 1.\xe2\x99\x98f3 e acentos: a\xc3\xa7\xc3\xa3o.</p>\n"
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        for nome, mudar in casos:
            projeto.gravar(arquivo, base.decode("utf-8"))
            mudar(projeto.pasta / arquivo)
            detectadas.append((nome, projeto.mudou_por_fora(arquivo)))
        projeto.gravar(arquivo, base.decode("utf-8"))
        (projeto.pasta / arquivo).write_bytes(base)            # o mesmo texto, regravado
        falso_alarme = projeto.mudou_por_fora(arquivo)
    shutil.rmtree(pasta / "fora", ignore_errors=True)
    return {"casos": dict(detectadas), "detectadas": sum(1 for _, v in detectadas if v),
            "total": len(detectadas), "mesmo_texto_nao_conta": not falso_alarme}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS, default=None)
    parser.add_argument("--vezes", type=int, default=QUEDAS)
    parser.add_argument("--filho", nargs=4, metavar=("RAIZ", "PDF", "REGISTROS", "ESPERA"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--filho-que-abre", nargs=2, metavar=("RAIZ", "PDF"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.filho:
        return filho(Path(args.filho[0]), Path(args.filho[1]), Path(args.filho[2]),
                     float(args.filho[3]), args.sabotar)
    if args.filho_que_abre:
        return filho_que_abre(Path(args.filho_que_abre[0]), Path(args.filho_que_abre[1]),
                              args.sabotar)
    if args.saida is None:
        parser.error("--saida é obrigatória")
    pasta = args.saida.resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    aplicar_sabotagem(args.sabotar)
    pdf = _pdf(pasta / "livro.pdf")

    resultado = {
        "sabotagem": args.sabotar,
        "trava": trava(pasta, pdf, args.sabotar),
        "mudancas_por_fora": mudancas_por_fora(pasta, pdf),
        "versoes": versoes(pasta),
        "quedas": quedas(pasta, pdf, args.vezes, args.sabotar),
    }
    q, v = resultado["quedas"], resultado["versoes"]
    exigencias = {
        f"diário: {q['perda_ok']}/{args.vezes} reaberturas com perda ≤ {PERDA_MAXIMA_S:g} s":
            q["perda_ok"] == args.vezes,
        f"gravação: {q['grande_inteiro']}/{args.vezes} arquivos inteiros (o antigo ou o novo)":
            q["grande_inteiro"] == args.vezes,
        f"trava: {q['trava_retomada']}/{args.vezes} travas de processo morto retomadas":
            q["trava_retomada"] == args.vezes,
        f"versões: teto de 200 MB mantido ({v['total_mb']} MB) com as 20 últimas":
            v["teto_mantido"] and v["ultimas_20_presentes"],
        "versões: o piso de 20 vence o teto": v["piso_vence_o_teto"],
        "versões: a restaurada é idêntica byte a byte": v["restaurada_identica"],
        "trava: a segunda abertura do mesmo livro é recusada":
            resultado["trava"]["segunda_recusada"],
        (f"mudança por fora: {resultado['mudancas_por_fora']['detectadas']}/"
         f"{resultado['mudancas_por_fora']['total']} detectadas"):
            resultado["mudancas_por_fora"]["detectadas"] == resultado["mudancas_por_fora"]["total"],
        "mudança por fora: o mesmo texto regravado não conta":
            resultado["mudancas_por_fora"]["mesmo_texto_nao_conta"],
    }
    resultado["exigencias"] = exigencias
    (pasta / "recuperacao.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    (pasta / "metricas.json").write_text(json.dumps({
        "perda_ok": q["perda_ok"], "grande_inteiro": q["grande_inteiro"],
        "trava_retomada": q["trava_retomada"], "perda_maxima_s": q["perda_maxima_s"],
        "versoes_total_mb": v["total_mb"],
        "mudancas_detectadas": resultado["mudancas_por_fora"]["detectadas"]}, indent=1),
        encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
