"""O executor de portões do Editor HTML/CSS reprova o que tem de reprovar (roadmap §0.2, passo H0).

Três passos falsos são o portão do H0: **instrumento ausente** reprova sem rodar nada,
**sabotagem que passa** reprova como inócua, e o **passo bom** passa. O resto guarda as regras
que os passos seguintes herdam: toda repetição tem de passar, a sabotagem tem de reprovar pelo
motivo declarado, e a saída nunca cai nas pastas do usuário.

Os comandos falsos são o próprio Python com `-c`: rodam em milissegundos e não dependem de nada
da suíte. A sabotagem do executor (`EDITOR_PORTOES_SABOTAR=aceita_sem_instrumento`) faz o
primeiro teste reprovar, e é assim que o portão do H0 prova que a conferência morde.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[3]


def _carregar() -> ModuleType:
    caminho = RAIZ / "benchmarks" / "editor_portoes.py"
    especificacao = importlib.util.spec_from_file_location("editor_portoes", caminho)
    assert especificacao is not None
    assert especificacao.loader is not None
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules["editor_portoes"] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


portoes = _carregar()


def _python(codigo: str, nome: str = "cmd", **kwargs: object) -> object:
    return portoes.Comando(nome, (sys.executable, "-c", codigo), **kwargs)


PASSA = "import sys; sys.exit(0)"
REPROVA_COM_MOTIVO = "print('defeito da sabotagem: verdade insuficiente'); import sys; sys.exit(1)"
REPROVA_SEM_MOTIVO = "raise ImportError('um defeito qualquer')"
EXISTE = "benchmarks/editor_portoes.py"


def test_instrumento_ausente_reprova_sem_rodar_nada(tmp_path: Path) -> None:
    passo = portoes.Passo(
        nome="falso-instrumento", descricao="instrumento que não existe",
        instrumentos=(EXISTE, "benchmarks/nao_existe_este_instrumento.py"),
        portao=(_python(PASSA),),
        sabotagens=(portoes.Sabotagem("s", _python(REPROVA_COM_MOTIVO, "s"),
                                      motivo="verdade insuficiente"),),
    )
    veredito = portoes.julgar(passo, tmp_path)
    assert veredito.resultado == portoes.REPROVADO, (
        "o passo falso com instrumento ausente tem de REPROVAR «instrumento ausente»; "
        f"o executor deu {veredito.resultado}")
    assert veredito.motivos == ["instrumento ausente: benchmarks/nao_existe_este_instrumento.py"]
    assert veredito.execucoes == []
    assert veredito.sabotagens == []


def test_sabotagem_que_passa_reprova_como_inocua(tmp_path: Path) -> None:
    passo = portoes.Passo(
        nome="falso-sabotagem", descricao="sabotagem que não morde",
        instrumentos=(EXISTE,),
        portao=(_python(PASSA),),
        sabotagens=(portoes.Sabotagem("nao_morde", _python(PASSA, "nao_morde"),
                                      motivo="verdade insuficiente"),),
    )
    veredito = portoes.julgar(passo, tmp_path)
    assert veredito.resultado == portoes.REPROVADO
    assert veredito.motivos == ["sabotagem inócua: nao_morde (o portão passou com ela)"]


def test_passo_bom_passa_e_grava_o_registro(tmp_path: Path) -> None:
    grava = ("import json, sys, pathlib; p = pathlib.Path(sys.argv[1]); "
             "p.mkdir(parents=True, exist_ok=True); "
             "(p / 'metricas.json').write_text(json.dumps({'regioes': 150, 'cer': 0.25}))")
    comando = portoes.Comando("mede", (sys.executable, "-c", grava, "{saida}"), repeticoes=3)
    passo = portoes.Passo(
        nome="falso-bom", descricao="tudo certo",
        instrumentos=(EXISTE,),
        portao=(comando,),
        sabotagens=(portoes.Sabotagem("morde", _python(REPROVA_COM_MOTIVO, "morde"),
                                      motivo="verdade insuficiente"),),
    )
    veredito = portoes.julgar(passo, tmp_path)
    assert veredito.resultado == portoes.APROVADO, veredito.motivos
    assert [e.indice for e in veredito.execucoes] == [1, 2, 3]
    assert veredito.medianas == {"mede": {"regioes": 150.0, "cer": 0.25}}
    assert veredito.sabotagens[0].motivo_visto is True

    destino = portoes.gravar(veredito, tmp_path, inicio={}, comeco="agora", argv=["x"])
    registro = json.loads(destino.read_text(encoding="utf-8"))
    assert registro["veredito"]["passou"] is True
    assert set(registro["repositorios_no_fim"]) == {"suite", "tronco"}
    assert registro["repositorios_no_fim"]["suite"]["head"]


def test_sabotagem_que_reprova_por_outro_motivo_nao_prova_nada(tmp_path: Path) -> None:
    passo = portoes.Passo(
        nome="falso-outro-motivo", descricao="sabotagem que quebra por acaso",
        instrumentos=(EXISTE,),
        portao=(_python(PASSA),),
        sabotagens=(portoes.Sabotagem("quebra", _python(REPROVA_SEM_MOTIVO, "quebra"),
                                      motivo="verdade insuficiente"),),
    )
    veredito = portoes.julgar(passo, tmp_path)
    assert veredito.resultado == portoes.REPROVADO
    assert len(veredito.motivos) == 1
    assert veredito.motivos[0].startswith("sabotagem inócua: quebra (reprovou, mas a saída não diz")


def test_uma_repeticao_que_reprova_reprova_o_passo(tmp_path: Path) -> None:
    contador = tmp_path / "contador.txt"
    codigo = ("import pathlib, sys; c = pathlib.Path(sys.argv[1]); "
              "n = int(c.read_text()) + 1 if c.exists() else 1; c.write_text(str(n)); "
              "sys.exit(1 if n == 2 else 0)")
    comando = portoes.Comando("instavel", (sys.executable, "-c", codigo, str(contador)),
                              repeticoes=3)
    passo = portoes.Passo(
        nome="falso-instavel", descricao="uma execução de três reprova",
        instrumentos=(EXISTE,),
        portao=(comando,),
        sabotagens=(portoes.Sabotagem("morde", _python(REPROVA_COM_MOTIVO, "morde"),
                                      motivo="verdade insuficiente"),),
    )
    veredito = portoes.julgar(passo, tmp_path / "saida")
    assert veredito.resultado == portoes.REPROVADO
    assert veredito.motivos == ["portão reprovou: instavel, execução 2 de 3 (código 1)"]


def test_a_saida_nunca_cai_nas_pastas_do_usuario(tmp_path: Path) -> None:
    assert portoes.pasta_permitida(tmp_path)
    assert portoes.pasta_permitida(portoes.RELATORIOS / "h0")
    for nome in ("labeling", "data", "editor"):
        assert not portoes.pasta_permitida(portoes.RAIZ / nome / "h0")
    assert not portoes.pasta_permitida(portoes.RAIZ / "docs")


def test_main_recusa_saida_fora_e_passo_desconhecido(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        portoes.main(["--passo", "H0", "--saida", str(portoes.RAIZ / "labeling" / "x")])
    with pytest.raises(SystemExit):
        portoes.main(["--passo", "H999", "--saida", str(portoes.RELATORIOS / "x")])
    assert "--saida fora" in capsys.readouterr().err


def test_a_tabela_do_h0_tem_instrumento_repeticoes_e_sabotagens() -> None:
    passo = portoes.PASSOS["H0"]
    assert "benchmarks/editor_leitores.py" in passo.instrumentos
    leitores = next(c for c in passo.portao if c.nome == "leitores")
    assert leitores.repeticoes == 3
    assert "{saida}" in leitores.argv
    assert leitores.conferir == "metricas_do_h0"
    assert {s.nome for s in passo.sabotagens} == {
        "aceita_sem_instrumento", "so_uma_pagina", "sem_ordem", "na_falso_figurinas",
        "na_falso_lances", "na_falso_insercao"}
    for sabotagem in passo.sabotagens:
        assert sabotagem.motivo, sabotagem.nome


def test_a_tabela_do_h2_mede_o_prototipo_e_a_sonda_uia() -> None:
    passo = portoes.PASSOS["H2"]
    assert {"benchmarks/editor_codigo.py", "benchmarks/editor_uia.py", "{med}"} <= set(
        passo.instrumentos)
    codigo = next(c for c in passo.portao if c.nome == "codigo")
    assert codigo.repeticoes == 3
    assert codigo.ambiente == "testes_qt"
    uia = next(c for c in passo.portao if c.nome == "uia")
    assert uia.argv[0] == "{med}"
    assert {s.nome for s in passo.sabotagens} == {"realce_sincrono", "funcoes_desligadas",
                                                 "uia_mudo"}
    assert "med" in portoes.interpretes()


def _leitores_json(pasta: Path, *, sem: tuple[str, str, str] | None = None,
                   nao_se_aplica: dict[str, dict[str, object]] | None = None,
                   dado: dict[str, object] | None = None) -> Path:
    """Um `leitores.json` completo; `sem` apaga uma métrica; `nao_se_aplica` é por estrato, e a
    métrica declarada sai sem valor em todos os leitores, como no instrumento; `dado` troca todas
    as métricas publicadas."""
    por_estrato = {}
    for estrato in portoes.ESTRATOS_DO_H0:
        declaradas = dict((nao_se_aplica or {}).get(estrato, {}))
        leitores = {}
        for leitor in portoes.LEITORES_DO_H0:
            leitores[leitor] = {
                m: ({"valor": None, "ic95": None} if m in declaradas
                    else dict(dado) if dado is not None else {"valor": 0.5, "ic95": [0.4, 0.6]})
                for m in portoes.METRICAS_DO_H0}
        por_estrato[estrato] = {"leitores": leitores, "nao_se_aplica": declaradas}
    if sem is not None:
        estrato, leitor, metrica = sem
        por_estrato[estrato]["leitores"][leitor][metrica] = {"valor": None, "ic95": None}
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "leitores.json").write_text(json.dumps({"por_estrato": por_estrato}),
                                         encoding="utf-8")
    return pasta


#: Os denominadores de um manifesto como o de 2026-09-24: o nativo sem figurina.
CONTAS = {"digitalizado": {"lances": 653, "figurinas": 464, "regioes": 199},
          "nativo": {"lances": 198, "figurinas": 0, "regioes": 38}}


def _auditoria(problemas: list[str] | None = None) -> object:
    return portoes.Auditoria(CONTAS, list(problemas or []))


def _declaracao(metrica: str, zero: int = 0) -> dict[str, object]:
    return {"metrica": metrica, "denominador": "lances com figurina na verdade",
            "valor_do_denominador": zero, "motivo": "a verdade do estrato não tem o que contar"}


def test_a_conferencia_do_h0_acusa_a_metrica_ausente(tmp_path: Path) -> None:
    assert portoes.conferir_metricas_do_h0(_leitores_json(tmp_path / "ok"),
                                           auditoria=_auditoria()) == []
    faltas = portoes.conferir_metricas_do_h0(
        _leitores_json(tmp_path / "sem", sem=("nativo", "camada", "ordem")), auditoria=_auditoria())
    assert faltas == ["métrica ausente: ordem de camada no estrato nativo"]
    assert portoes.conferir_metricas_do_h0(tmp_path / "vazia") == [
        "métrica ausente: o leitores.json não foi gravado"]


def test_os_problemas_da_auditoria_reprovam(tmp_path: Path) -> None:
    problema = "publicação inconsistente: estrato adulterado em x"
    faltas = portoes.conferir_metricas_do_h0(_leitores_json(tmp_path / "ok"),
                                             auditoria=_auditoria([problema]))
    assert faltas == [problema]


def test_nao_se_aplica_so_com_o_denominador_zero_na_verdade(tmp_path: Path) -> None:
    aceita = _leitores_json(tmp_path / "fig", sem=("nativo", "glifo", "figurinas"),
                            nao_se_aplica={"nativo": {"figurinas": _declaracao("figurinas")}})
    assert portoes.conferir_metricas_do_h0(aceita, auditoria=_auditoria()) == []
    falsa = _leitores_json(tmp_path / "falsa", sem=("digitalizado", "glifo", "figurinas"),
                           nao_se_aplica={"digitalizado": {"figurinas": _declaracao("figurinas")}})
    faltas = portoes.conferir_metricas_do_h0(falsa, auditoria=_auditoria())
    assert faltas[0] == ("métrica ausente: figurinas no estrato digitalizado declarada «não se "
                         "aplica», mas a verdade tem 464 (figurinas)")
    assert "métrica ausente: figurinas de glifo no estrato digitalizado" in faltas


@pytest.mark.parametrize("estrago", ["sem_motivo", "motivo_vazio", "metrica_trocada",
                                     "denominador_nao_zero", "denominador_booleano", "sem_nome"])
def test_a_declaracao_incompleta_nao_dispensa(tmp_path: Path, estrago: str) -> None:
    declaracao = _declaracao("figurinas")
    if estrago == "sem_motivo":
        del declaracao["motivo"]
    elif estrago == "motivo_vazio":
        declaracao["motivo"] = "  "
    elif estrago == "metrica_trocada":
        declaracao["metrica"] = "lances"
    elif estrago == "denominador_nao_zero":
        declaracao["valor_do_denominador"] = 3
    elif estrago == "denominador_booleano":
        declaracao["valor_do_denominador"] = False
    else:
        del declaracao["denominador"]
    publicada = _leitores_json(tmp_path / estrago, sem=("nativo", "glifo", "figurinas"),
                               nao_se_aplica={"nativo": {"figurinas": declaracao}})
    faltas = portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria())
    assert faltas[0] == ("métrica ausente: figurinas no estrato nativo com a declaração de «não "
                         "se aplica» incompleta")


def test_a_ordem_e_o_cer_nunca_se_dispensam(tmp_path: Path) -> None:
    recusada = _leitores_json(tmp_path / "ordem", sem=("nativo", "glifo", "ordem"),
                              nao_se_aplica={"nativo": {"ordem": _declaracao("ordem")}})
    assert "métrica ausente: ordem de glifo no estrato nativo" in portoes.conferir_metricas_do_h0(
        recusada, auditoria=_auditoria())


# ------------------------------------------------------- a métrica publicada vale (ciclo 21)


def test_metricas_de_texto_reprovam_todas(tmp_path: Path) -> None:
    """O defeito do ciclo 21: `{"valor": "fraude", "ic95": "fraude"}` passava por publicada."""
    publicada = _leitores_json(tmp_path, dado={"valor": "fraude", "ic95": "fraude"})
    faltas = portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria())
    assert len(faltas) == 2 * 4 * 5
    assert all(f.startswith("métrica inválida: ") for f in faltas)
    assert ("métrica inválida: cer de fusao no estrato digitalizado (o valor 'fraude' não é um "
            "número finito)") in faltas


def test_nan_reprova(tmp_path: Path) -> None:
    publicada = _leitores_json(tmp_path, dado={"valor": float("nan"), "ic95": [0.1, 0.2]})
    assert '"valor": NaN' in (publicada / "leitores.json").read_text(encoding="utf-8")
    faltas = portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria())
    assert len(faltas) == 40
    assert all("(o valor nan não é um número finito)" in f for f in faltas)


@pytest.mark.parametrize(("dado", "defeito"), [
    ({"valor": float("inf"), "ic95": [0.1, 0.2]}, "o valor inf não é um número finito"),
    ({"valor": True, "ic95": [0.1, 0.2]}, "o valor True não é um número finito"),
    ({"valor": 0.5, "ic95": None}, "o intervalo None não é um par de números finitos"),
    ({"valor": 0.5, "ic95": [0.4]}, "o intervalo [0.4] não é um par de números finitos"),
    ({"valor": 0.5, "ic95": ["0.4", "0.6"]},
     "o intervalo ['0.4', '0.6'] não é um par de números finitos"),
    ({"valor": 0.5, "ic95": [0.4, float("nan")]},
     "o intervalo [0.4, nan] não é um par de números finitos"),
    ({"valor": 0.5, "ic95": [0.6, 0.4]}, "o intervalo [0.6, 0.4] invertido ou fora de [0.0, 1.0]"),
    ({"valor": None, "ic95": [0.4, 0.6]}, "o valor None não é um número finito"),
])
def test_valor_e_intervalo_malformados_reprovam(tmp_path: Path, dado: dict, defeito: str) -> None:
    publicada = _leitores_json(tmp_path, dado=dado)
    faltas = portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria())
    assert f"métrica inválida: ordem de camada no estrato nativo ({defeito})" in faltas
    assert len(faltas) == 40


def test_a_faixa_de_cada_metrica(tmp_path: Path) -> None:
    """O CER e os lances inventados passam de 1; lances certos, figurinas e ordem não."""
    publicada = _leitores_json(tmp_path, dado={"valor": 1.5, "ic95": [1.2, 1.9]})
    faltas = portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria())
    fora = {f.split(": ")[1].split(" de ")[0] for f in faltas}
    assert fora == {"lances", "figurinas", "ordem"}
    assert ("métrica inválida: lances de glifo no estrato nativo (o valor 1.5 fora de "
            "[0.0, 1.0])") in faltas
    abaixo = _leitores_json(tmp_path / "abaixo", dado={"valor": 0.1, "ic95": [-0.1, 0.3]})
    assert len(portoes.conferir_metricas_do_h0(abaixo, auditoria=_auditoria())) == 40


def test_declarada_e_publicada_com_valor_reprova(tmp_path: Path) -> None:
    publicada = _leitores_json(tmp_path, nao_se_aplica={"nativo": {"figurinas": _declaracao(
        "figurinas")}})
    dados = json.loads((publicada / "leitores.json").read_text(encoding="utf-8"))
    dados["por_estrato"]["nativo"]["leitores"]["glifo"]["figurinas"] = {"valor": 0.9,
                                                                        "ic95": [0.8, 1.0]}
    (publicada / "leitores.json").write_text(json.dumps(dados), encoding="utf-8")
    assert portoes.conferir_metricas_do_h0(publicada, auditoria=_auditoria()) == [
        "métrica inválida: figurinas de glifo no estrato nativo declarada «não se aplica» e "
        "publicada com valor"]


def test_forma_errada_do_json_nao_derruba_a_conferencia(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for conteudo in ([], {"por_estrato": []}, {"por_estrato": {"nativo": {"leitores": []}}},
                     {"por_estrato": {"nativo": {"leitores": {}, "nao_se_aplica": []}}}):
        (tmp_path / "leitores.json").write_text(json.dumps(conteudo), encoding="utf-8")
        faltas = portoes.conferir_metricas_do_h0(tmp_path, auditoria=_auditoria())
        assert faltas
        assert all(f.startswith(("métrica ausente", "publicação inconsistente")) for f in faltas)


# ------------------------------------------------------------ a auditoria contra o manifesto


def _manifesto(caminho: Path, figurina: str = "\u2658") -> list[str]:
    """Um manifesto mínimo: duas regiões digitalizadas (uma com figurina, de um livro) e duas
    nativas (sem figurina, de outro). Devolve os ids na ordem dos itens."""
    from caissa.ocr.golden import (
        GoldenItem,
        GoldenManifest,
        GoldenRegion,
        Partition,
        Source,
        partition_for,
        save_manifest,
    )

    usados: set[str] = set()

    def item(livro: str, fonte: Source, verdade: str) -> GoldenItem:
        ident = next(f"{livro}:{n}" for n in range(500)
                     if f"{livro}:{n}" not in usados
                     and partition_for(f"{livro}:{n}") is not Partition.BLIND)
        usados.add(ident)
        return GoldenItem(id=ident, source=fonte, book=livro, page_index=0, clip=(0, 0, 100, 100),
                          regions=(GoldenRegion(kind="paragraph", truth=verdade),))

    itens = [item("scan", Source.PDF_SCAN, f"1.{figurina}f3 d5 2.g3"),
             item("scan", Source.PDF_SCAN, "Um parágrafo sem lance."),
             item("nativo", Source.PDF_NATIVE, "1.Cf3 d5 2.g3 Bg4"),
             item("nativo", Source.PDF_NATIVE, "Outro parágrafo, 3.Bg2.")]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    save_manifest(GoldenManifest(items=itens), caminho)
    return [i.id for i in itens]


def _publicar(pasta: Path, manifesto: Path) -> list[dict[str, object]]:
    """A publicação honesta do manifesto: a lista, o hash dela e as regiões casadas pelo IoU."""
    from caissa.ocr.golden import load_manifest

    carregado = load_manifest(manifesto, include_blind=True)
    estratos = {"pdf-scan": "digitalizado", "pdf-native": "nativo"}
    lista = [{"id": i.id, "livro": i.book, "indice": 0, "caixa": [0, 0, 100, 100],
              "estrato": estratos[str(i.source)]} for i in carregado.items]
    pasta.mkdir(parents=True, exist_ok=True)
    identidade = carregado.content_hash()
    (pasta / "unidades.json").write_text(json.dumps({
        "manifesto": str(manifesto), "hash_do_manifesto": identidade,
        "hash_da_lista": portoes._hash_da_lista(lista), "unidades": lista}), encoding="utf-8")
    regioes = [{"id": u["id"], "estrato": u["estrato"], "casada": True,
                **{leitor: {"iou": 0.9 if leitor == "fusao" else 0.2}
                   for leitor in portoes.LEITORES_DO_H0}} for u in lista]
    (pasta / "leitores.json").write_text(json.dumps({
        "hash_do_manifesto": identidade, "hash_da_lista": portoes._hash_da_lista(lista),
        "regioes": regioes}), encoding="utf-8")
    return regioes


def _publicacao(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    manifesto = tmp_path / "verdade" / "manifesto.json"
    _manifesto(manifesto)
    pasta = tmp_path / "saida"
    return pasta, manifesto, _publicar(pasta, manifesto)


def _regravar(pasta: Path, nome: str, mudar) -> None:
    arquivo = pasta / nome
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    mudar(dados)
    arquivo.write_text(json.dumps(dados), encoding="utf-8")


def _problemas(pasta: Path, manifesto: Path) -> list[str]:
    return portoes.auditar_publicacao(pasta, manifesto=manifesto, minimo=1).problemas


def test_a_auditoria_honesta_nao_acha_nada_e_conta_o_manifesto(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    auditoria = portoes.auditar_publicacao(pasta, manifesto=manifesto, minimo=1)
    assert auditoria.problemas == []
    assert auditoria.denominadores["digitalizado"] == {"lances": 3, "figurinas": 1, "regioes": 2}
    assert auditoria.denominadores["nativo"] == {"lances": 5, "figurinas": 0, "regioes": 2}


def test_o_minimo_do_h0_vale_por_padrao(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    problemas = portoes.auditar_publicacao(pasta, manifesto=manifesto).problemas
    assert problemas == ["verdade insuficiente: 4 regiões casadas (mínimo 150), 2 livro(s), "
                         "estratos ['digitalizado', 'nativo']"]


def test_desmarcar_as_casadas_nao_zera_o_denominador(tmp_path: Path) -> None:
    """O defeito do ciclo 20: a publicação marcava a região como não casada e o N/A passava."""
    pasta, manifesto, _ = _publicacao(tmp_path)

    def desmarcar(dados: dict) -> None:
        for regiao in dados["regioes"]:
            regiao["casada"] = False
            regiao["fusao"]["iou"] = 0.1

    _regravar(pasta, "leitores.json", desmarcar)
    auditoria = portoes.auditar_publicacao(pasta, manifesto=manifesto, minimo=1)
    assert auditoria.denominadores["digitalizado"]["figurinas"] == 1
    assert any(p.startswith("verdade insuficiente: 0 regiões casadas") for p in auditoria.problemas)


def test_casada_que_o_iou_nao_sustenta_reprova(tmp_path: Path) -> None:
    pasta, manifesto, regioes = _publicacao(tmp_path)
    _regravar(pasta, "leitores.json", lambda d: d["regioes"][0].update(casada=False))
    assert (f"publicação inconsistente: «casada» que os IoUs não sustentam em 1 região(ões), "
            f"a primeira {regioes[0]['id']}") in _problemas(pasta, manifesto)
    _regravar(pasta, "leitores.json", lambda d: d["regioes"][0].pop("glifo"))
    assert any("«casada» que os IoUs não sustentam" in p for p in _problemas(pasta, manifesto))


def test_regioes_ausentes_reprovam(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    _regravar(pasta, "leitores.json", lambda d: d.pop("regioes"))
    problemas = _problemas(pasta, manifesto)
    assert "publicação inconsistente: o leitores.json não traz as regiões" in problemas
    assert any(p.startswith("verdade insuficiente: 0 regiões casadas") for p in problemas)


def test_regiao_a_menos_no_leitores_reprova(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    _regravar(pasta, "leitores.json", lambda d: d["regioes"].pop(0))
    assert ("publicação inconsistente: as regiões do leitores.json não são as da lista"
            in _problemas(pasta, manifesto))


def test_estrato_adulterado_reprova(tmp_path: Path) -> None:
    pasta, manifesto, regioes = _publicacao(tmp_path)
    _regravar(pasta, "leitores.json", lambda d: d["regioes"][0].update(estrato="nativo"))
    assert (f"publicação inconsistente: estrato adulterado em {regioes[0]['id']}"
            in _problemas(pasta, manifesto))


def test_lista_que_nao_confere_com_o_hash_reprova(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    _regravar(pasta, "unidades.json", lambda d: d["unidades"].pop())
    assert ("publicação inconsistente: a lista das unidades não confere com o hash_da_lista"
            in _problemas(pasta, manifesto))


def test_lista_recortada_com_o_hash_refeito_reprova(tmp_path: Path) -> None:
    """A lista sem a região da figurina e com o hash refeito: o manifesto ainda a tem."""
    pasta, manifesto, _ = _publicacao(tmp_path)

    def recortar(dados: dict) -> None:
        dados["unidades"].pop(0)
        dados["hash_da_lista"] = portoes._hash_da_lista(dados["unidades"])

    _regravar(pasta, "unidades.json", recortar)
    problemas = _problemas(pasta, manifesto)
    assert "publicação inconsistente: a lista tem 3 regiões e o manifesto, 4" in problemas
    assert ("publicação inconsistente: o leitores.json não é da lista gravada antes da leitura"
            in problemas)


def test_leitores_de_outra_lista_reprova(tmp_path: Path) -> None:
    pasta, manifesto, _ = _publicacao(tmp_path)
    _regravar(pasta, "leitores.json", lambda d: d.update(hash_da_lista="0" * 16))
    assert ("publicação inconsistente: o leitores.json não é da lista gravada antes da leitura"
            in _problemas(pasta, manifesto))


def test_manifesto_trocado_pela_publicacao_reprova(tmp_path: Path) -> None:
    """A publicação mede outro manifesto (sem a figurina) e grava o hash dele: o executor lê o seu,
    acusa o hash e conta a figurina que a verdade tem."""
    verdadeiro = tmp_path / "verdade" / "manifesto.json"
    _manifesto(verdadeiro)
    forjado = tmp_path / "forjado" / "manifesto.json"
    _manifesto(forjado, figurina="C")
    pasta = tmp_path / "saida"
    _publicar(pasta, forjado)
    auditoria = portoes.auditar_publicacao(pasta, manifesto=verdadeiro, minimo=1)
    assert "publicação inconsistente: o manifesto não é o da medição (hash)" in auditoria.problemas
    assert auditoria.denominadores["digitalizado"]["figurinas"] == 1


def test_o_executor_le_o_manifesto_do_checkout(tmp_path: Path) -> None:
    assert portoes.manifesto_do_executor().as_posix().endswith(portoes.MANIFESTO_DO_H0)


def test_a_conferencia_reprova_a_execucao_que_saiu_com_zero(tmp_path: Path) -> None:
    pasta = tmp_path / "saida"
    grava = ("import json, sys, pathlib; p = pathlib.Path(sys.argv[1]); "
             "p.mkdir(parents=True, exist_ok=True); "
             "(p / 'leitores.json').write_text(json.dumps({'por_estrato': {}}))")
    comando = portoes.Comando("mede", (sys.executable, "-c", grava, "{saida}"),
                              conferir="metricas_do_h0")
    execucao = portoes.rodar(comando, pasta, 1, motivo="métrica ausente")
    assert execucao.codigo == 2
    assert execucao.motivo_visto is True
