# Origem: ChessVisionOFF_Puro/tests/test_packaging.py
# Absorvido em 2026-09-09 (F12). Alteracoes: os testes de raiz congelada viraram testes do
# manifesto (a suite nao tem `config.py` proprio); a guarda de spec ganhou a checagem da
# regra de `excludes` contra a medicao; entraram o teto de tamanho, a ausencia de `models/`
# no bundle, os caminhos citados pelo `.iss`, e a busca por modulo `.pyc`-only.
"""O que muda quando o programa e um `.exe` em vez de um checkout (F12).

Um defeito de empacotamento e caro de um jeito diferente dos outros: ele so aparece na
maquina de outra pessoa, e o sintoma e uma janela que some. Estes testes cobrem o que **pode**
ser afirmado aqui, e sao de dois tipos:

* **Sempre rodam** -- a spec, o manifesto, o `.iss` e o codigo de verificacao SHA-256 sao
  arquivos e funcoes, e nao dependem de nenhum build existir.
* **Pulam com o motivo se `dist/Caissa` nao existir** -- os que inspecionam o bundle. Pular
  com motivo, e nao passar contra um duplo: um teste verde que nunca viu um bundle diria
  exatamente nada sobre o bundle.

O teto de tamanho e afirmado, e nao suposto: ha um teste que le o numero medido pelo build e
o compara com o da SPEC secao 12. Ele documenta a distancia em vez de a esconder.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "packaging"
TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

if str(PACOTE) not in sys.path:
    sys.path.insert(0, str(PACOTE))

import caissa_modelos as mod  # noqa: E402 - depende do sys.path acima
import caissa_torch as ct  # noqa: E402 - idem

SPEC = PACOTE / "caissa.spec"
ISS = PACOTE / "installer.iss"
MANIFESTO = PACOTE / "manifesto.json"
MEDICAO = PACOTE / "modulos_vivos.json"
METRICAS = PACOTE / "bundle.json"
STDLIB = PACOTE / "stdlib_do_torch.json"
"""A biblioteca padrao que so o torch usa, medida. Ciclo 2."""
MANIFESTO_DE_TORCH = PACOTE / "torch_manifesto.json"
"""As rodas que NAO viajam no instalador, com URL https e SHA-256. Ciclo 2."""
LICENCAS = PACOTE / "licenses"
INDICE = LICENCAS / "INDICE.json"

TETO_DO_INSTALADOR_MB = 150.0
"""SPEC secao 12. Constante repetida aqui de proposito: um teste que importa o numero do
codigo que ele testa nao testa o numero."""


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def bundle() -> Path:
    """A pasta do build completo, ou pula com o motivo."""
    pasta = RAIZ / "dist" / "Caissa"
    if not (pasta / "Caissa.exe").exists():
        pytest.skip(
            f"nao ha build em {pasta}. Rode "
            "`.venv-pack\\Scripts\\python.exe packaging/build_windows.py`."
        )
    return pasta


# =========================================================================== #
# A spec
# =========================================================================== #
class TestSpec:
    """A `caissa.spec` e o unico lugar onde as decisoes de empacotamento moram."""

    def test_o_modo_e_onedir(self) -> None:
        """`--onefile` extrairia o bundle para %TEMP% a cada execucao; SPEC R4 proibe."""
        texto = _texto(SPEC)
        assert "COLLECT(" in texto
        assert "exclude_binaries=True" in texto

    def test_os_dois_executaveis_estao_declarados(self) -> None:
        """A janela (sem console) e o assistente (com console) saem do mesmo COLLECT."""
        texto = _texto(SPEC)
        assert 'name="Caissa"' in texto
        assert 'name="CaissaPrimeiraExecucao"' in texto
        assert "console=False" in texto, "a janela nao pode abrir com console"
        assert "console=True" in texto, "o assistente imprime; sem console nao imprime nada"

    def test_o_ponto_de_entrada_e_a_casca_e_nao_o_app_do_tronco(self) -> None:
        """Empacotar `app_pyqt.py` direto pularia a checagem de pesos que abre a caixa."""
        texto = _texto(SPEC)
        assert 'str(PACOTE / "caissa_app.py")' in texto
        assert 'str(PACOTE / "caissa_setup.py")' in texto
        assert "janela = Analysis(" in texto
        assert "assistente = Analysis(" in texto

    def test_upx_desligado(self) -> None:
        """UPX comprime DLL nativa e uma parte dos antivirus a poe em quarentena."""
        assert "upx=True" not in _texto(SPEC)
        assert _texto(SPEC).count("upx=False") >= 3

    def test_os_dados_do_usuario_nao_viajam_dentro_do_pacote(self) -> None:
        """`models/`, `data/`, `PDF/`, `PGN/` sao do usuario e ficam AO LADO do executavel."""
        texto = _texto(SPEC)
        bloco = texto[texto.index("datas = [") : texto.index("# excludes")]
        for proibido in ('"models"', '"data"', '"PDF"', '"PGN"', '"logs"'):
            assert proibido not in bloco, f"{proibido} nao pode estar em `datas`"

    def test_o_llm_nao_entra_e_a_spec_diz_por_que(self) -> None:
        """F11 mediu especificidade 0,000; o motivo tem de sobreviver no arquivo."""
        texto = _texto(SPEC)
        assert "0,000" in texto or "0.000" in texto
        assert "F11_REPORT" in texto

    def test_a_variante_distribuida_e_a_que_nao_leva_torch(self) -> None:
        """Ciclo 2 inverteu o padrao: quem se distribui e a que exclui o torch.

        No ciclo 1 o torch viajava congelado dentro e a variante sem ele era a excecao
        (`CAISSA_LIGHT`). Isso entregava a roda de **CPU** a quem tem uma RTX -- 0,5234
        s/diagrama em vez de 0,0903 (F4GPU secao 7) -- e ainda estourava o teto da SPEC
        secao 12 em 19,3 MB. Agora o padrao nao leva torch, e `CAISSA_COM_TORCH=1` monta a
        variante de **medicao**.

        O teste afirma o sentido do `if`, porque e nele que a inversao mora: um dia alguem
        pode voltar a congelar a roda "so para facilitar", e o efeito seria silencioso.
        """
        texto = _texto(SPEC)
        assert "SEM_TORCH = not COM_TORCH" in texto
        assert 'COM_TORCH = os.environ.get("CAISSA_COM_TORCH"' in texto
        assert "if SEM_TORCH:\n" in texto
        bloco = texto[texto.index("if SEM_TORCH:") : texto.index("_MEDICAO =")]
        for nome in ("torch", "torchvision", "sympy", "networkx", "fsspec", "filelock"):
            assert f'"{nome}",' in bloco, f"{nome} deveria sair do bundle e chegar em runtime/"

    def test_o_gancho_de_runtime_esta_nas_duas_analises(self) -> None:
        """Sem o gancho, o torch instalado ao lado do `.exe` existe em disco e nao para o programa.

        Ele entra por `comum`, que as duas `Analysis` recebem -- a janela e o assistente. Um
        `runtime_hooks` so na janela daria o modo de falha mais confuso possivel: o assistente
        instala 2,6 GB e o proprio assistente nao os enxerga na hora de sondar.
        """
        texto = _texto(SPEC)
        assert '"runtime_hooks": [str(PACOTE / "runtime_hook_torch.py")]' in texto
        assert (PACOTE / "runtime_hook_torch.py").is_file()
        gancho = _texto(PACOTE / "runtime_hook_torch.py")
        assert "sys.path.append(runtime)" in gancho, "append: o bundle continua vencendo"
        assert "add_dll_directory" in gancho, "o motivo de NAO chamar tem de ficar escrito"


class TestRegraDeExcludes:
    """A regra do tronco: so entra em `excludes` o que NAO aparece em `sys.modules`."""

    def test_a_medicao_existe_e_e_datada(self) -> None:
        assert MEDICAO.exists(), "rode `build_windows.py --medir-modulos`"
        dados = json.loads(_texto(MEDICAO))
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", dados["medido_em"])
        assert len(dados["vivos"]) > 50, "uma medicao com poucos modulos nao importou a arvore"

    def test_nenhum_exclude_e_um_modulo_vivo(self) -> None:
        """O ponto inteiro do arquivo. Excluir um modulo vivo quebra na maquina do usuario."""
        vivos = set(json.loads(_texto(MEDICAO))["vivos"])
        texto = _texto(SPEC)
        bloco = texto[texto.index("excludes = [") : texto.index("_MEDICAO =")]
        nomes = set(re.findall(r'^\s{4}"([A-Za-z_][\w.]*)",', bloco, flags=re.MULTILINE))
        assert nomes, "nao consegui ler a lista de excludes"
        assert not (nomes & vivos), f"excludes contem modulo vivo: {sorted(nomes & vivos)}"

    def test_o_tkinter_esta_vivo_e_por_isso_e_pedido_em_vez_de_excluido(self) -> None:
        """A regra vale nos dois sentidos, e este e o caso que mostra o segundo.

        `tkinter` esta vivo (`cli/texto_transcrever.py` do tronco ainda e Tk). Nao basta
        **nao** exclui-lo: o primeiro bundle levava os `.py` dele sem `_tkinter.pyd`, e um
        modulo pela metade e tao defeituoso quanto um modulo ausente -- neste caso derrubou
        `from PIL import ... ImageTk` e com ele todos os icones da fita.
        """
        vivos = set(json.loads(_texto(MEDICAO))["vivos"])
        assert "tkinter" in vivos
        texto = _texto(SPEC)
        excludes = texto[texto.index("excludes = [") : texto.index("_MEDICAO =")]
        assert '"tkinter"' not in excludes, "modulo vivo nao pode entrar em excludes"
        hidden = texto[texto.index("hiddenimports = [") : texto.index("pathex = [")]
        assert '"tkinter",' in hidden, "estando vivo, tem de ser pedido com a extensao nativa"
        assert '"PIL.ImageTk",' in hidden

    def test_o_onnxruntime_esta_excluido_e_a_spec_cita_a_adr(self) -> None:
        """ADR-0003: onnxruntime-gpu e torch cu128 no mesmo processo e conflito de DLL."""
        texto = _texto(SPEC)
        assert '"onnxruntime",' in texto
        assert "ADR-0003" in texto

    def test_a_coleta_do_torchvision_falha_alto_em_vez_de_sair_vazia(self) -> None:
        """O defeito original foi uma coleta vazia e SILENCIOSA; repeti-la seria o mesmo bug."""
        texto = _texto(SPEC)
        assert "def binarios_do_torchvision" in texto
        corpo = texto[texto.index("def binarios_do_torchvision") :]
        corpo = corpo[: corpo.index("\nbinaries =")]
        assert "raise SystemExit" in corpo, "coleta vazia tem de derrubar o build"
        assert 'glob("*.pyd")' in corpo


class TestJanelaNaoTrava:
    """Um `.exe` sem console que levanta abre uma caixa modal e espera um clique."""

    def test_a_casca_captura_excecao_em_vez_de_deixar_a_caixa_modal_aparecer(self) -> None:
        """Medido: 7 min 10 s parado numa caixa que ninguem ia clicar, ate o tempo limite."""
        texto = (PACOTE / "caissa_app.py").read_text(encoding="utf-8")
        assert "CODIGO_DE_ERRO_NAO_TRATADO = 7" in texto
        assert "except BaseException" in texto
        assert "traceback.format_exc()" in texto

    def test_o_codigo_7_tem_significado_escrito_no_assistente(self) -> None:
        """Um codigo de saida que o relatorio nao sabe traduzir e um numero solto."""
        texto = (PACOTE / "caissa_primeira_execucao.py").read_text(encoding="utf-8")
        assert "7: " in texto
        assert "excecao escapou" in texto


# =========================================================================== #
# O manifesto e a verificacao SHA-256
# =========================================================================== #
class TestManifesto:
    """O que nao viaja no instalador e chega depois, verificado."""

    def test_o_manifesto_carrega_e_valida(self) -> None:
        manifesto = mod.carregar_manifesto(MANIFESTO)
        assert manifesto.componentes
        assert manifesto.obrigatorios, "sem componente obrigatorio o assistente nao tem o que dizer"

    def test_todo_sha256_tem_64_hexadecimais(self) -> None:
        for componente in mod.carregar_manifesto(MANIFESTO).componentes:
            assert re.fullmatch(r"[0-9a-f]{64}", componente.sha256), componente.id

    def test_nenhum_destino_escapa_da_pasta_da_instalacao(self) -> None:
        """`..` num destino gravaria fora de `{app}`. A validacao recusa no carregamento."""
        for componente in mod.carregar_manifesto(MANIFESTO).componentes:
            destino = Path(componente.destino)
            assert not destino.is_absolute()
            assert ".." not in destino.parts

    def test_os_dois_lexicos_nao_apurados_exigem_consentimento(self) -> None:
        """LICENSING.md: eles nao entram sem o usuario dizer que sim."""
        manifesto = mod.carregar_manifesto(MANIFESTO)
        for ident in ("lexico-idioma", "lexico-nomes"):
            componente = manifesto.por_id(ident)
            assert componente.consentimento is True
            assert componente.obrigatorio is False
            assert "NAO APURADA" in componente.licenca.upper()

    def test_o_lexico_do_acervo_nao_exige_consentimento(self) -> None:
        """Ele e do proprio projeto e por isso viaja dentro do bundle -- nao esta aqui."""
        ids = {c.id for c in mod.carregar_manifesto(MANIFESTO).componentes}
        assert "lexico-acervo" not in ids

    def test_todo_componente_diz_o_que_se_perde_sem_ele(self) -> None:
        """ "Faltou o modelo" transfere ao usuario um diagnostico que o programa ja tinha."""
        for componente in mod.carregar_manifesto(MANIFESTO).componentes:
            assert len(componente.sem_ele) > 20, componente.id

    def test_sem_servidor_o_manifesto_diz_null_em_vez_de_uma_url_inventada(self) -> None:
        assert mod.carregar_manifesto(MANIFESTO).base_url is None

    @pytest.mark.skipif(not TRONCO.exists(), reason="o tronco nao esta nesta maquina")
    def test_os_hashes_batem_com_os_arquivos_do_tronco(self) -> None:
        """Um hash que ninguem reconfere envelhece na primeira vez que o peso e retreinado."""
        for componente in mod.carregar_manifesto(MANIFESTO).componentes:
            if not componente.origem_no_tronco:
                continue
            fonte = TRONCO / componente.origem_no_tronco
            if not fonte.exists():
                pytest.skip(f"{fonte} nao esta nesta maquina")
            assert fonte.stat().st_size == componente.bytes, componente.id
            assert mod.sha256_do_arquivo(fonte) == componente.sha256, componente.id


class TestVerificacao:
    """As funcoes que decidem se um arquivo baixado presta."""

    def test_arquivo_ausente_devolve_ausente_e_nao_levanta(self, tmp_path: Path) -> None:
        componente = mod.carregar_manifesto(MANIFESTO).obrigatorios[0]
        resultado = mod.verificar(componente, tmp_path)
        assert not resultado
        assert resultado.estado == "ausente"

    def test_tamanho_errado_e_detectado_antes_do_hash(self, tmp_path: Path) -> None:
        """Truncado por download interrompido e o caso comum; 4 bytes de metadado bastam."""
        componente = mod.carregar_manifesto(MANIFESTO).obrigatorios[0]
        alvo = tmp_path / componente.destino
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(b"x" * (componente.bytes - 1))
        assert mod.verificar(componente, tmp_path).estado == "tamanho-errado"

    def test_conteudo_trocado_com_o_tamanho_certo_e_pego_pelo_hash(self, tmp_path: Path) -> None:
        componente = mod.carregar_manifesto(MANIFESTO).obrigatorios[0]
        alvo = tmp_path / componente.destino
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(b"x" * componente.bytes)
        assert mod.verificar(componente, tmp_path).estado == "hash-errado"

    def test_instalacao_offline_recusa_arquivo_com_hash_errado(self, tmp_path: Path) -> None:
        componente = mod.carregar_manifesto(MANIFESTO).obrigatorios[0]
        origem = tmp_path / "origem"
        origem.mkdir()
        (origem / Path(componente.destino).name).write_bytes(b"nao sou o modelo")
        destino = tmp_path / "destino"
        resultado = mod.instalar_de_pasta(componente, origem, destino)
        assert not resultado
        assert resultado.estado == "hash-errado"
        assert not (destino / componente.destino).exists(), "nao pode ter copiado"

    def test_componente_sob_consentimento_nao_entra_sem_consentimento(self, tmp_path: Path) -> None:
        componente = mod.carregar_manifesto(MANIFESTO).por_id("lexico-nomes")
        resultado = mod.instalar_de_pasta(componente, tmp_path, tmp_path)
        assert resultado.estado == "sem-consentimento"

    def test_download_por_http_e_recusado_antes_de_qualquer_rede(self, tmp_path: Path) -> None:
        """Os `.pt` sao pickles do torch: canal nao autenticado seria execucao remota."""
        componente = mod.carregar_manifesto(MANIFESTO).obrigatorios[0]
        resultado = mod.baixar(componente, "http://exemplo.invalido", tmp_path)
        assert resultado.estado == "url-recusada"

    def test_a_raiz_de_instalacao_e_a_pasta_do_executavel_quando_congelado(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """E o contrato que faz reinstalar nao apagar o que o usuario baixou."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "Caissa.exe"))
        assert mod.raiz_de_instalacao() == tmp_path


# =========================================================================== #
# O instalador
# =========================================================================== #
class TestInstalador:
    """O `.iss` nao foi compilado nesta maquina; o que da para afirmar, afirma-se."""

    def test_o_iss_declara_que_nao_foi_compilado_aqui(self) -> None:
        """Uma promessa nao verificada tem de estar escrita no arquivo que a faz."""
        assert "NAO COMPILADO NESTA MAQUINA" in _texto(ISS)

    def test_os_nomes_de_variante_batem_com_os_da_spec(self) -> None:
        """Se um dos dois mudar sem o outro, o instalador empacota uma pasta que nao existe."""
        iss = _texto(ISS)
        spec = _texto(SPEC)
        assert '#define DistName "Caissa-com-torch"' in iss
        assert '#define DistName "Caissa"' in iss
        assert 'NOME = "Caissa-com-torch" if COM_TORCH else "Caissa"' in spec

    def test_os_executaveis_citados_sao_os_que_a_spec_produz(self) -> None:
        iss = _texto(ISS)
        assert '#define AppExeName "Caissa.exe"' in iss
        assert '#define SetupExeName "CaissaPrimeiraExecucao.exe"' in iss

    def test_a_compressao_e_a_mesma_que_o_build_mede_no_proxy(self) -> None:
        """Se este par divergir, o numero publicado no relatorio deixa de valer."""
        assert "Compression=lzma2/max" in _texto(ISS)
        assert "SolidCompression=yes" in _texto(ISS)
        assert "-m0=lzma2" in _texto(PACOTE / "build_windows.py")

    def test_o_installdelete_apaga_so_o_internal(self) -> None:
        """Varrer `{app}` destruiria os pesos que o usuario acabou de baixar."""
        iss = _texto(ISS)
        assert r'Name: "{app}\_internal"' in iss
        assert r'Name: "{app}"' not in iss.split("[InstallDelete]")[1].split("[Dirs]")[0]

    def test_as_pastas_do_usuario_sobrevivem_a_desinstalacao(self) -> None:
        """Seis pastas, e `runtime` e a mais cara: ate 4,2 GB baixados pelo usuario.

        Desinstalar e reinstalar apagando `runtime/` faria o usuario baixar 2,6 GB de novo
        sem pedir nada -- e numa maquina com franquia de dados isso e um dano, nao um
        inconveniente.
        """
        iss = _texto(ISS)
        bloco = iss.split("[Dirs]")[1].split("[Files]")[0]
        for nome in ("runtime", "models", "data", "PDF", "PGN", "logs"):
            assert f"{{app}}\\{nome}" in bloco, nome
        linhas = [ln for ln in bloco.splitlines() if ln.startswith("Name:")]
        assert len(linhas) == 6
        assert all("uninsneveruninstall" in ln for ln in linhas)

    def test_o_installdelete_nao_toca_no_runtime(self) -> None:
        """Reinstalar por cima nao pode apagar o torch que o usuario baixou."""
        bloco = _texto(ISS).split("[InstallDelete]")[1].split("[Dirs]")[0]
        assert "runtime" not in bloco, (
            "o [InstallDelete] varreria a pasta em que o assistente instalou ate 4,2 GB"
        )

    def test_o_assistente_roda_antes_de_a_janela_abrir(self) -> None:
        """Janela sem pesos e primeira impressao de coisa quebrada."""
        bloco = _texto(ISS).split("[Run]")[1]
        assert bloco.index("{#SetupExeName}") < bloco.index("{#AppExeName}")

    def test_a_licenca_mostrada_e_um_arquivo_que_o_bundle_carrega(self) -> None:
        """`LicenseFile` apontando para o que nao existe faz o ISCC falhar na compilacao."""
        assert r"LicenseFile={#SourceDir}\_internal\LICENSING.md" in _texto(ISS)
        assert (RAIZ / "LICENSING.md").exists()
        assert '(str(PROJETO / "LICENSING.md"), ".")' in _texto(SPEC)

    def test_todo_arquivo_de_origem_citado_pelo_iss_existe(self) -> None:
        """Os `#define` que apontam para o disco, conferidos um a um."""
        assert (RAIZ / "LICENSING.md").is_file()
        assert (TRONCO / "assets" / "cvoff.ico").is_file() or not TRONCO.exists()
        assert MANIFESTO.is_file()


# =========================================================================== #
# O bundle produzido
# =========================================================================== #
class TestBundle:
    """Pulam com motivo se nao houver build. Um verde sem bundle nao diria nada."""

    def test_os_dois_executaveis_sairam(self, bundle: Path) -> None:
        assert (bundle / "Caissa.exe").is_file()
        assert (bundle / "CaissaPrimeiraExecucao.exe").is_file()

    def test_a_pasta_de_modelos_nasce_ao_lado_do_exe_e_nao_dentro(self, bundle: Path) -> None:
        """As duas metades do contrato da SPEC secao 12, num teste so.

        `models/` fica **ao lado** do executavel e nasce com a instalacao; ela nao pode
        existir dentro de `_internal/`, que e o que uma reinstalacao sobrescreve. O que ela
        contem depois da primeira execucao e do usuario -- por isso o teste olha para onde
        ela esta, e nao para o que tem dentro.
        """
        modelos = bundle / "models"
        assert modelos.is_dir(), "a pasta tem de nascer com a instalacao"
        assert (modelos / "LEIA-ME.txt").is_file(), "uma pasta vazia sem explicacao e um bug"
        assert not (bundle / "_internal" / "models").exists(), (
            "`models/` dentro de `_internal` sumiria a cada reinstalacao"
        )

    def test_nenhum_peso_entrou_dentro_do_pacote(self, bundle: Path) -> None:
        """`_internal/` e o que o instalador sobrescreve; peso ali seria peso reinstalado.

        Olha so para `_internal/` de proposito. Depois da primeira execucao ha `.pt` em
        `models/`, e isso e o assistente funcionando -- confundir os dois faria o teste
        reprovar exatamente a instalacao correta.
        """
        interno = bundle / "_internal"
        for padrao in ("*.pt", "*.onnx", "*.safetensors", "*.gguf"):
            achados = list(interno.rglob(padrao))
            assert not achados, f"{padrao} dentro do pacote: {[str(p) for p in achados[:3]]}"

    def test_os_lexicos_de_licenca_nao_apurada_nao_estao_no_bundle(self, bundle: Path) -> None:
        """A decisao de LICENSING.md, conferida no artefato e nao so na spec."""
        assert not list(bundle.rglob("idioma.txt.gz"))
        assert not list(bundle.rglob("nomes.txt.gz"))
        assert list(bundle.rglob("acervo.txt.gz")), "o do proprio projeto deveria estar"

    def test_o_licensing_e_o_manifesto_viajam_com_o_programa(self, bundle: Path) -> None:
        assert (bundle / "_internal" / "LICENSING.md").is_file()
        assert (bundle / "_internal" / "manifesto.json").is_file()
        assert (bundle / "_internal" / "assets" / "lexico" / "PROCEDENCIA.md").is_file()

    def test_as_doze_pecas_estao_la(self, bundle: Path) -> None:
        """Sem elas o tabuleiro degrada para simbolo Unicode, peca a peca."""
        pecas = list((bundle / "_internal" / "assets" / "piece_images").glob("*.png"))
        assert len(pecas) == 12, [p.name for p in pecas]

    def test_nenhum_modulo_ficou_so_como_pyc_solto(self, bundle: Path) -> None:
        """`.pyc` solto em `_internal` e modulo que o PyInstaller nao pos no arquivo compilado.

        O sintoma na maquina do usuario e um `ModuleNotFoundError` numa funcao que so roda no
        caminho raro -- meses depois. O bundle so deve ter `.pyc` dentro de `base_library.zip`
        e do `PYZ`, e nao soltos na arvore.
        """
        soltos = [p for p in (bundle / "_internal").rglob("*.pyc") if "__pycache__" not in p.parts]
        assert not soltos, f"{len(soltos)} .pyc soltos: {[str(p) for p in soltos[:5]]}"

    def test_nao_sobrou_ferramenta_de_desenvolvimento(self, bundle: Path) -> None:
        """Cada uma seria MB que o usuario baixa e nunca executa."""
        interno = bundle / "_internal"
        for proibido in ("pytest", "mypy", "ruff", "scipy", "skimage", "streamlit", "pandas"):
            assert not (interno / proibido).exists(), f"{proibido} entrou no bundle"

    def test_o_tkinter_levou_a_extensao_nativa(self, bundle: Path) -> None:
        """`tkinter` esta vivo; leva-lo so como `.py` e um modulo pela metade.

        E o defeito foi visivel na janela: `ui/icones.py` do tronco faz
        `from PIL import Image, ImageDraw, ImageTk` numa linha so, e sem `_tkinter.pyd` a
        linha inteira levanta -- o `except` zera `Image`, e o programa perde TODOS os icones
        da fita por causa de um nome que nao usa desde o corte do Tk.
        """
        interno = bundle / "_internal"
        assert list(interno.glob("_tkinter*.pyd")), (
            "tkinter esta em modulos_vivos.json mas o bundle nao levou `_tkinter.pyd`. "
            "Sem ele, `from PIL import ... ImageTk` levanta e a Pillow inteira some."
        )
        assert (interno / "tcl").is_dir() or list(interno.glob("tcl*.dll")), (
            "sem o runtime do Tcl, `import tkinter` levanta mesmo com o `.pyd`"
        )

    def test_o_torchvision_levou_a_extensao_nativa(self, bundle: Path) -> None:
        """O defeito que so aparece rodando o `.exe`, virado em teste.

        O `hook-torchvision.py` do PyInstaller 6.22.2 procura `_C.pyd`/`image.pyd`; o
        torchvision 0.29 renomeou para `_C_stable.pyd`/`image_stable.pyd`. O hook nao acha,
        **nao reclama**, e o bundle sai com os `.py` e sem a extensao que registra os
        operadores -- e a janela morre com `operator torchvision::nms does not exist` no
        primeiro import, ja na maquina do usuario.

        No ciclo 2 o torchvision saiu do bundle e passa a chegar em `runtime/`, desempacotado
        de uma roda -- e uma roda sempre traz a extensao. A afirmacao continua valendo e muda
        de endereco: o teste procura onde o torchvision estiver.
        """
        pasta = bundle / "_internal" / "torchvision"
        de_onde = "_internal (variante de medicao)"
        if not pasta.is_dir():
            pasta = bundle / "runtime" / "torchvision"
            de_onde = "runtime (instalado pelo assistente)"
        if not pasta.is_dir():
            pytest.skip("torchvision nao esta no bundle nem instalado em runtime/")
        nativos = list(pasta.glob("*.pyd")) + list(pasta.glob("*.dll"))
        assert nativos, (
            f"torchvision em {de_onde} sem nenhum .pyd/.dll. Sem a extensao nativa o import "
            "levanta `operator torchvision::nms does not exist`. Ver `binarios_do_torchvision` "
            "na spec."
        )
        assert any(p.suffix == ".pyd" for p in nativos), [p.name for p in nativos]

    def test_o_tamanho_medido_esta_gravado_e_e_recente(self, bundle: Path) -> None:
        """Um numero declarado que ninguem recalcula envelhece; este sai do disco."""
        assert METRICAS.exists(), "o build grava packaging/bundle.json"
        dados = json.loads(_texto(METRICAS))
        # So o que o BUILD produziu. `runtime/`, `models/`, `PDF/`, `data/`, `PGN/` e
        # `logs/` sao do usuario e crescem com o uso -- somar o que ele baixou ao que o build
        # gerou faria o teste reprovar toda instalacao que alguem chegou a usar. `runtime/`
        # entrou nesta lista no ciclo 2 e e a maior de todas: com o torch cu128 instalado ela
        # sozinha passa de 4 GB, contra 295 MB do bundle inteiro. A lista e a do build
        # (`PASTAS_GUARDADAS`, que inclui `rotulagem/`): e o que ele exclui ao medir, e uma
        # segunda lista aqui divergiria no primeiro nome que alguem acrescentasse la.
        import build_windows

        do_usuario = set(build_windows.PASTAS_GUARDADAS)
        real = sum(
            f.stat().st_size
            for f in bundle.rglob("*")
            if f.is_file() and not (set(f.relative_to(bundle).parts) & do_usuario)
        ) / (1024 * 1024)
        assert abs(dados["mb"] - real) < 5.0, f"gravado {dados['mb']} MB, disco {real:.1f} MB"


class TestTeto:
    """O teto da SPEC secao 12, afirmado e nao suposto."""

    def test_o_teto_esta_escrito_no_build_e_e_o_da_spec(self) -> None:
        assert f"TETO_DO_INSTALADOR_MB = {TETO_DO_INSTALADOR_MB}" in _texto(
            PACOTE / "build_windows.py"
        )
        spec_md = (RAIZ / "docs" / "SPEC.md").read_text(encoding="utf-8")
        assert "150 MB" in spec_md

    def test_a_variante_que_se_distribui_cabe_no_teto(self) -> None:
        """O teste que o ciclo 1 nao podia ter, e que agora e o portao.

        No ciclo 1 quem cabia no teto era a variante `leve`, que **nao abria**
        (`ModuleNotFoundError: No module named 'torch'`) -- um teste verde sobre um produto
        inexistente. O que se distribuia dava 169,3 MB, 19,3 acima da SPEC secao 12.

        Agora e o inverso: `packaging/bundle.json` mede a variante padrao, que e a que se
        entrega, e e ela que tem de caber. Se um dia alguem voltar a congelar o torch, este
        teste reprova -- que e exatamente o que o ciclo 1 nao tinha.
        """
        if not METRICAS.exists():
            pytest.skip("rode `build_windows.py --instalador`")
        dados = json.loads(_texto(METRICAS))
        assert dados["variante"] == "padrao", (
            f"bundle.json mede a variante {dados['variante']!r}; o teto vale para a que se "
            "distribui"
        )
        instalador = dados["instalador"]
        if not instalador.get("ok"):
            pytest.skip(f"instalador nao medido: {instalador.get('erro')}")
        assert instalador["mb"] <= TETO_DO_INSTALADOR_MB, (
            f"o instalador que se distribui deu {instalador['mb']} MB, acima do teto de "
            f"{TETO_DO_INSTALADOR_MB} MB da SPEC secao 12"
        )

    def test_o_proxy_diz_que_e_proxy(self) -> None:
        """O Inno Setup nao esta nesta maquina; o numero publicado tem de dizer isso."""
        if not METRICAS.exists():
            pytest.skip("nao ha build medido")
        instalador = json.loads(_texto(METRICAS))["instalador"]
        if instalador.get("tipo") == "nao-pedido":
            pytest.skip("build rodado sem --instalador")
        if instalador["tipo"] != "proxy-lzma2":
            return  # compilado de verdade: nada a ressalvar
        assert "PROXY MEDIDO" in instalador.get("nota", ""), (
            "um numero de proxy sem a ressalva vira, na leitura de terceiros, um numero de "
            "instalador compilado"
        )

    def test_o_custo_do_torch_congelado_continua_medido(self) -> None:
        """Tirar o torch e uma decisao; o numero que a justifica nao pode sumir junto.

        A variante `com-torch` existe so para isso. Ela nao precisa caber no teto -- precisa
        **existir como numero**, porque e a diferenca entre ela e a padrao que diz quanto o
        torch custa no instalador.
        """
        com_torch = PACOTE / "bundle-com-torch.json"
        if not com_torch.exists():
            pytest.skip(
                "a medicao do custo do torch congelado vem do ciclo 1 (F12_REPORT.md secao 3: "
                "169,3 MB contra 79,1). Para refaze-la: "
                "`build_windows.py --com-torch --instalador`"
            )
        dados = json.loads(_texto(com_torch))
        assert dados["variante"] == "com-torch"
        assert dados["instalador"]["mb"] > 0


# =========================================================================== #
# A biblioteca padrao que so o torch usa (ciclo 2)
# =========================================================================== #
class TestBibliotecaPadraoDoTorch:
    r"""Tirar o torch do bundle tirou junto o Python que ele usa. Isto afirma que voltou.

    O defeito e desta forma: o PyInstaller coleta o que **ve**. Sem nenhum `import torch` na
    arvore congelada, ele nao ve `uuid`, nao ve `unittest.mock`, nao ve
    `asyncio.windows_events`. O torch que o assistente instala depois em `runtime/` acha o
    proprio pacote e nao acha o Python embaixo dele -- e o sintoma nao e legivel:

        -> filelock       FALHOU ModuleNotFoundError: No module named 'uuid'
        -> torch.version  FALHOU ImportError: cannot import name 'mock' from 'unittest'
        -> torch._C       EXIT = -1073740791   (0xC0000409, o processo morre sem traceback)

    A medicao esta em `packaging/stdlib_do_torch.json` e tem dois lados. `modulos` entra em
    `hiddenimports`; `extensoes_nativas` e conferida **no bundle pronto**, porque um nome em
    `hiddenimports` faz o PyInstaller tentar e nao garante que o `.pyd` chegou.
    """

    def test_a_medicao_existe_e_e_datada(self) -> None:
        assert STDLIB.exists(), "rode `build_windows.py --medir-stdlib-do-torch`"
        dados = json.loads(_texto(STDLIB))
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", dados["medido_em"])
        assert len(dados["modulos"]) > 100, "medicao rasa: o torch importa ~178 modulos"
        assert len(dados["fontes"]) >= 2, (
            "medir uma roda so nao distingue o que o torch usa do que aquela versao usa"
        )

    def test_os_tres_modulos_que_derrubaram_o_exe_estao_na_lista(self) -> None:
        """Os nomes exatos dos tres sintomas medidos, para a lista nao encolher em silencio."""
        modulos = set(json.loads(_texto(STDLIB))["modulos"])
        for nome in ("uuid", "unittest.mock", "asyncio.windows_events"):
            assert nome in modulos, f"{nome} saiu da medicao; era um dos tres sintomas"

    def test_todo_nome_medido_e_importavel_neste_interpretador(self) -> None:
        """Um nome errado em `hiddenimports` nao derruba o PyInstaller -- ele e ignorado.

        Que e o mesmo modo de falha do resto desta frente: a coleta que sai vazia sem
        reclamar. Como a lista e gerada por medicao e nao digitada, isto deve passar sempre;
        o teste existe para o dia em que alguem a editar a mao.
        """
        import importlib.util

        modulos = json.loads(_texto(STDLIB))["modulos"]
        ruins = [n for n in modulos if importlib.util.find_spec(n) is None]
        assert not ruins, f"nomes que nao existem nesta biblioteca padrao: {ruins}"

    def test_a_spec_pede_a_lista_nos_dois_executaveis(self) -> None:
        """O assistente instala 2,6 GB e sonda o que instalou no MESMO processo.

        Se a biblioteca padrao faltar so nele, ele baixa tudo e depois morre ao conferir.
        """
        texto = _texto(SPEC)
        assert "hiddenimports += _stdlib_do_torch" in texto
        assistente = texto[texto.index("hiddenimports_do_assistente = [") :]
        assistente = assistente[: assistente.index("\n]")]
        assert "*_stdlib_do_torch," in assistente

    def test_a_spec_recusa_montar_sem_a_medicao(self) -> None:
        """Sem a lista o bundle sai verde e o `.exe` morre com 0xC0000409 e sem traceback.

        Um build que sai pela metade e pior do que um build que nao sai: ele viaja.
        """
        texto = _texto(SPEC)
        bloco = texto[texto.index("_STDLIB = PACOTE") : texto.index("pathex = [")]
        assert "raise SystemExit" in bloco
        assert "0xC0000409" in bloco or "medir-stdlib-do-torch" in bloco

    def test_as_extensoes_nativas_foram_medidas_e_incluem_o_tkinter(self) -> None:
        """`_tkinter.pyd` e o caso que custou todos os icones da fita no ciclo 1."""
        dados = json.loads(_texto(STDLIB))
        extensoes = dados.get("extensoes_nativas") or {}
        assert extensoes, "rode `build_windows.py --medir-stdlib-do-torch` (versao do ciclo 2)"
        assert extensoes.get("_tkinter") == "_tkinter.pyd"
        for nome in ("_ssl", "_socket", "_hashlib", "_ctypes", "_bz2", "_lzma"):
            assert nome in extensoes, f"{nome} nao foi medido"
        assert all(p.endswith(".pyd") for p in extensoes.values()), extensoes

    def test_o_build_reprova_um_bundle_sem_extensao_nativa(self, tmp_path: Path) -> None:
        """O portao do ciclo 2, exercido contra um bundle deliberadamente furado.

        Nao basta a funcao existir: um `conferir` que devolve 0 para tudo e um comentario com
        sintaxe de codigo. Aqui ela recebe um `_internal/` a que falta exatamente um `.pyd` --
        `_tkinter.pyd`, o do defeito original -- e tem de devolver 1.
        """
        import build_windows as bw

        exigidas = json.loads(_texto(STDLIB))["extensoes_nativas"]
        interno = tmp_path / "_internal"
        interno.mkdir()
        for pyd in exigidas.values():
            (interno / pyd).write_bytes(b"")
        assert bw.conferir_extensoes_nativas(tmp_path) == 0, "com todas, tem de aprovar"

        (interno / "_tkinter.pyd").unlink()
        assert bw.conferir_extensoes_nativas(tmp_path) == 1, (
            "faltando `_tkinter.pyd` o build tem de FALHAR. Sem isso ele sai verde e o "
            "usuario recebe uma fita sem icones."
        )

    def test_o_build_chama_a_conferencia_depois_do_pyinstaller(self) -> None:
        """Uma funcao que ninguem chama nao e um portao."""
        texto = _texto(PACOTE / "build_windows.py")
        corpo = texto[texto.index("def build(") : texto.index("def achar_iscc")]
        assert "conferir_extensoes_nativas(saida)" in corpo
        assert corpo.index("conferir_extensoes_nativas(saida)") > corpo.index(
            "PyInstaller falhou"
        ), "conferir antes de o PyInstaller rodar nao confere nada"

    def test_o_bundle_tem_todas_as_extensoes_medidas(self, bundle: Path) -> None:
        """A mesma afirmacao, agora contra o bundle que existe no disco."""
        exigidas = json.loads(_texto(STDLIB)).get("extensoes_nativas") or {}
        if not exigidas:
            pytest.skip("medicao sem `extensoes_nativas`")
        presentes = {p.name for p in (bundle / "_internal").glob("*.pyd")}
        faltando = sorted(p for p in exigidas.values() if p not in presentes)
        assert not faltando, f"o bundle no disco saiu sem: {faltando}"


# =========================================================================== #
# O torch como componente de primeira execucao (ciclo 2)
# =========================================================================== #
class TestTorchDePrimeiraExecucao:
    """A roda certa para a GPU do outro lado, com hash, e um caminho offline obrigatorio."""

    def test_o_manifesto_das_rodas_carrega_e_valida(self) -> None:
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        assert {v.id for v in manifesto.variantes} == {"cu128", "cpu"}
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", manifesto.gerado_em)

    def test_toda_roda_e_https_e_tem_sha256_de_64_hexadecimais(self) -> None:
        """Uma roda e um zip de codigo executavel: baixa-la sem canal autenticado e sem hash
        conferido seria execucao remota com passos extras."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        for variante in manifesto.variantes:
            for roda in variante.rodas:
                assert roda.url.startswith("https://"), roda.nome
                assert re.fullmatch(r"[0-9a-f]{64}", roda.sha256), roda.nome
                assert roda.bytes > 0, roda.nome

    def test_o_manifesto_recusa_url_http(self, tmp_path: Path) -> None:
        """O portao, exercido: nao basta que hoje todas sejam https."""
        bruto = json.loads(_texto(MANIFESTO_DE_TORCH))
        bruto["variantes"][0]["rodas"][0]["url"] = "http://example.invalid/torch.whl"
        falso = tmp_path / "torch_manifesto.json"
        falso.write_text(json.dumps(bruto), encoding="utf-8")
        with pytest.raises(ValueError, match="url"):
            ct.carregar_manifesto_de_torch(falso)

    def test_uma_rtx_5060_recebe_cu128_e_a_frase_diz_por_que(self) -> None:
        """A maquina de referencia da SPEC secao 2. sm_120 so tem kernel em cu128."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        gpu = ct.Gpu(
            nome="NVIDIA GeForce RTX 5060",
            capacidade=(12, 0),
            driver="591.86",
            memoria_mib=8151,
        )
        variante, motivo = ct.escolher_variante(gpu, manifesto)
        assert variante.id == "cu128"
        assert "sm_120" in motivo
        assert "cu128" in motivo

    def test_sem_gpu_recebe_cpu_e_a_frase_diz_por_que(self) -> None:
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        variante, motivo = ct.escolher_variante(None, manifesto)
        assert variante.id == "cpu"
        assert "nvidia-smi" in motivo

    def test_uma_gpu_antiga_demais_recebe_cpu_em_vez_de_2_6_gb_inuteis(self) -> None:
        """Abaixo de sm_70 a roda cu128 nao traz kernel: seriam 2,6 GB para cair em CPU."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        gpu = ct.Gpu(
            nome="NVIDIA GeForce GTX 1060",
            capacidade=(6, 1),
            driver="474.11",
            memoria_mib=6144,
        )
        variante, motivo = ct.escolher_variante(gpu, manifesto)
        assert variante.id == "cpu"
        assert "sm_61" in motivo

    def test_driver_que_nao_declara_a_arquitetura_recebe_cpu(self) -> None:
        """Nao saber e diferente de saber que nao da. Apostar 2,6 GB no escuro e o erro."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        gpu = ct.Gpu(
            nome="NVIDIA Quadro K2000",
            capacidade=None,
            driver="391.35",
            memoria_mib=None,
        )
        variante, _ = ct.escolher_variante(gpu, manifesto)
        assert variante.id == "cpu"

    def test_a_diferenca_de_velocidade_e_medida_e_nao_adjetivo(self) -> None:
        """0,0903 contra 0,5234 s/diagrama, do F4GPU secao 7. Sem esses numeros o assistente
        estaria dizendo "mais rapido" para quem acabou de pagar 2,6 GB."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        assert manifesto.por_id("cu128").segundos_por_diagrama == 0.0903
        assert manifesto.por_id("cpu").segundos_por_diagrama == 0.5234
        assert ct.SEGUNDOS_POR_DIAGRAMA == {"cu128": 0.0903, "cpu": 0.5234}
        relatorio = (RAIZ / "docs" / "quality" / "F4GPU_REPORT.md").read_text(encoding="utf-8")
        assert "0,0903" in relatorio or "0.0903" in relatorio

    def test_o_assistente_diz_ao_usuario_de_cpu_o_que_ele_esta_recebendo(self) -> None:
        """Quem fica em CPU tem de ser avisado, e nao descobrir sozinho depois de um livro.

        As duas frases citam os dois numeros e a razao entre eles; nenhuma delas diz apenas
        "instalado com sucesso".
        """
        texto = _texto(PACOTE / "caissa_primeira_execucao.py")
        corpo = texto[texto.index("def _registrar_torch") :]
        corpo = corpo[: corpo.index("def _por_no_caminho")]
        assert "s por diagrama" in corpo
        assert "mais lento" in corpo
        assert "mais rapido" in corpo
        assert "300 paginas com 400" in corpo, "minutos de livro, e nao so segundos por peca"

    def test_o_caminho_offline_e_obrigatorio_e_esta_documentado_na_falha(self) -> None:
        """Sem rede o usuario nao pode ficar sem saida; e a mensagem de erro e onde ele olha."""
        texto = _texto(PACOTE / "caissa_primeira_execucao.py")
        assert "--rodas-de" in texto
        assert "Sem internet" in texto
        assert "torch_manifesto.json" in texto

    def test_a_copia_local_com_hash_errado_e_recusada_antes_de_desempacotar(
        self, tmp_path: Path
    ) -> None:
        """O caminho offline tem o mesmo portao do de rede -- e ele importa mais aqui.

        Um `.whl` e um zip de codigo que vai ser desempacotado e importado. Aceitar um que
        veio de um pendrive porque "veio de um pendrive" seria confiar na origem em vez de no
        conteudo.
        """
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        roda = min(manifesto.por_id("cpu").rodas, key=lambda r: r.bytes)
        origem = tmp_path / "espelho"
        origem.mkdir()
        (origem / roda.nome).write_bytes(b"\x00" * roda.bytes)  # tamanho certo, conteudo nao
        resultado = ct.obter_roda(roda, tmp_path / "cache", origem=origem)
        assert resultado.ok is False
        assert resultado.estado == "hash-errado"
        assert not (tmp_path / "cache" / roda.nome).exists(), "nao pode sobrar nada verificavel"
        assert not list((tmp_path / "cache").glob("*.parcial")), "nem o parcial pode ficar"

    def test_a_roda_ausente_no_espelho_e_reportada_e_nao_baixada_escondido(
        self, tmp_path: Path
    ) -> None:
        """`--rodas-de` significa offline. Cair para a rede em silencio quebraria a promessa."""
        manifesto = ct.carregar_manifesto_de_torch(MANIFESTO_DE_TORCH)
        roda = min(manifesto.por_id("cpu").rodas, key=lambda r: r.bytes)
        vazia = tmp_path / "vazia"
        vazia.mkdir()
        resultado = ct.obter_roda(roda, tmp_path / "cache", origem=vazia)
        assert resultado.ok is False
        assert resultado.estado == "nao-encontrado"

    def test_a_marca_registra_qual_roda_esta_instalada(self, bundle: Path) -> None:
        """Uma pasta com um `torch/` dentro nao diz se e cu128 ou cpu.

        Sem a marca, reinstalar rebaixaria um cu128 para cpu sem ninguem perceber -- e o
        usuario veria o programa ficar 5,8x mais lento sem nenhum evento a que ligar isso.
        """
        marca = bundle / "runtime" / ct.MARCA
        if not marca.exists():
            pytest.skip("torch ainda nao instalado neste bundle")
        dados = json.loads(_texto(marca))
        assert dados["variante"] in {"cu128", "cpu"}
        assert dados["segundos_por_diagrama"] == ct.SEGUNDOS_POR_DIAGRAMA[dados["variante"]]
        assert len(dados["rodas"]) == 10
        assert all(re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) for r in dados["rodas"])

    def test_o_torch_nao_viaja_dentro_do_bundle(self, bundle: Path) -> None:
        """O ponto inteiro do ciclo 2, medido no disco e nao na spec."""
        interno = bundle / "_internal"
        for proibido in ("torch", "torchvision", "sympy", "networkx", "functorch"):
            assert not (interno / proibido).exists(), (
                f"_internal/{proibido} existe: o torch voltou para dentro do instalador e o "
                "teto da SPEC secao 12 voltou a ser estourado"
            )

    def test_o_torch_instalado_fica_fora_do_que_o_instalador_sobrescreve(
        self, bundle: Path
    ) -> None:
        """`runtime/` e irma de `models/`: ao lado do `.exe`, nao dentro de `_internal/`."""
        if not (bundle / "runtime").exists():
            pytest.skip("torch ainda nao instalado neste bundle")
        assert (bundle / "runtime").is_dir()
        assert not (bundle / "_internal" / "runtime").exists()


# =========================================================================== #
# Os textos de licenca -- o portao que tira o build do "uso proprio"
# =========================================================================== #
class TestLicencas:
    """A AGPL exige que os textos acompanhem a distribuicao. Isto afirma que acompanham.

    O ciclo 1 fechou com a frase *"faltam os textos das licencas dentro do pacote; ate isso
    ser feito, o build e para uso proprio"*. Reunir os arquivos foi metade do trabalho; a
    outra metade e este portao, sem o qual a proxima dependencia entra sem texto e ninguem
    fica sabendo.
    """

    def test_o_indice_existe_e_e_datado(self) -> None:
        assert INDICE.exists(), "rode `packaging/coletar_licencas.py` no .venv-pack"
        dados = json.loads(_texto(INDICE))
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", dados["gerado_em"])
        assert len(dados["distribuicoes"]) >= 20, "poucas dependencias: a coleta nao rodou"

    def test_toda_dependencia_distribuida_tem_texto_de_licenca(self) -> None:
        """O portao. Uma dependencia sem texto reprova o build, e nao vira nota de rodape."""
        dados = json.loads(_texto(INDICE))
        assert dados["sem_texto"] == [], (
            "estas dependencias viajam no pacote e nao trazem o texto da propria licenca: "
            f"{dados['sem_texto']}. Sob AGPL isso nao e um detalhe -- e a condicao para "
            "poder distribuir."
        )
        assert dados["nao_encontradas_no_ambiente"] == [], dados["nao_encontradas_no_ambiente"]

    def test_cada_arquivo_declarado_no_indice_existe_no_disco(self) -> None:
        """Um indice que aponta para o que nao existe e pior do que nao ter indice."""
        dados = json.loads(_texto(INDICE))
        faltando = [
            arq
            for dist in dados["distribuicoes"]
            for arq in dist["arquivos"]
            if not (LICENCAS / arq).is_file()
        ]
        assert not faltando, faltando

    def test_as_dependencias_do_runtime_tambem_estao_cobertas(self) -> None:
        """O torch chega depois do instalador -- e chega distribuido pelo mesmo programa.

        Uma coleta que olhasse so para `_internal/` deixaria as dez rodas de fora e diria
        "tudo certo": o pacote entrega torch, torchvision, sympy, networkx, jinja2 e
        companhia, e a obrigacao de licenca acompanha a entrega, nao o instalador.
        """
        dados = json.loads(_texto(INDICE))
        do_runtime = {
            d["distribuicao"]
            for d in dados["distribuicoes"]
            if str(d.get("origem", "")).startswith("runtime")
        }
        for nome in ("torch", "torchvision", "sympy", "networkx", "filelock", "fsspec"):
            assert nome in do_runtime, f"{nome} chega em runtime/ e nao foi coberto"

    def test_as_duas_familias_de_copyleft_viajam_por_inteiro(self) -> None:
        """Referenciar a AGPL sem entregar o texto e o mesmo que nao a entregar."""
        for nome, marca in (
            ("AGPL-3.0.txt", "GNU AFFERO GENERAL PUBLIC LICENSE"),
            ("GPL-3.0.txt", "GNU GENERAL PUBLIC LICENSE"),
            ("LGPL-3.0.txt", "GNU LESSER GENERAL PUBLIC LICENSE"),
        ):
            caminho = LICENCAS / nome
            assert caminho.is_file(), nome
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            assert marca in texto.upper(), f"{nome} nao parece o texto da licenca"
            assert len(texto) > 7_000, f"{nome} tem {len(texto)} bytes; o texto e maior"

    def test_o_conjunto_de_pecas_distribuido_tem_licenca_declarada(self) -> None:
        """As 12 pecas sao arte de terceiro, e arte tambem tem licenca."""
        dados = json.loads(_texto(INDICE))
        pecas = dados["artefatos_nao_python"]["assets-piece_images"]
        assert "cburnett" in pecas["titulo"].lower()
        assert "GPL" in pecas["licenca"]
        assert (LICENCAS / pecas["arquivo"]).is_file()

    def test_o_licensing_concorda_com_o_pyproject(self) -> None:
        """Dois arquivos que declaram a licenca do mesmo binario nao podem discordar.

        Ate 2026-09-09 discordavam: `pyproject.toml` dizia `LGPL-3.0-or-later` e o
        `LICENSING.md` explicava, na secao 1, por que aquilo era falso. A declaracao foi
        corrigida; este teste existe para que a proxima divergencia apareca aqui e nao na
        leitura de quem for redistribuir.
        """
        pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
        assert 'license = { text = "AGPL-3.0-or-later" }' in pyproject
        licensing = (RAIZ / "LICENSING.md").read_text(encoding="utf-8")
        assert "AGPL-3.0-or-later" in licensing
        assert 'declara `license = { text = "LGPL-3.0-or-later" }`' not in licensing, (
            "o LICENSING.md ainda descreve o pyproject como LGPL; ele ja foi corrigido"
        )

    def test_o_licensing_diz_o_que_a_agpl_exige_de_quem_distribui(self) -> None:
        """Nao basta dizer "e AGPL": quem receber o binario precisa saber o que fazer."""
        licensing = (RAIZ / "LICENSING.md").read_text(encoding="utf-8")
        for exigencia in (
            "código-fonte correspondente",
            "§13",
            "AGPL-3.0-or-later",
            "Quem redistribuir este build assume estas cinco obrigações",
        ):
            assert exigencia in licensing, exigencia

    def test_os_textos_viajam_dentro_do_bundle(self, bundle: Path) -> None:
        """O disco e a unica prova. Um `datas` na spec e uma intencao."""
        pasta = bundle / "_internal" / "licenses"
        assert pasta.is_dir(), "o bundle saiu sem `_internal/licenses/`"
        for nome in ("AGPL-3.0.txt", "GPL-3.0.txt", "INDICE.json", "TERCEIROS.md"):
            assert (pasta / nome).is_file(), nome
        no_bundle = json.loads((pasta / "INDICE.json").read_text(encoding="utf-8"))
        assert no_bundle["sem_texto"] == []

    def test_o_assistente_mostra_as_licencas_na_primeira_execucao(self) -> None:
        """Um texto que viaja no pacote e nunca e apontado e um texto que ninguem le."""
        texto = _texto(PACOTE / "caissa_primeira_execucao.py")
        assert "Textos de licenca" in texto
        assert "AGPL-3.0-or-later" in texto


class TestOAssistenteNaoEspera:
    """Um passo que nao pode passar nao pode custar o tempo limite inteiro."""

    def test_o_auto_teste_nao_roda_quando_falta_componente_obrigatorio(self) -> None:
        """Medido em 2026-09-09, no bundle recem-construido e sem os pesos:

            [FALHA] Classificador de casas (pecas)   ausente
            [FALHA] Auto-teste                       nao terminou
                    TimeoutExpired: ... timed out after 300.0 seconds

        Cinco minutos de espera para repetir o que a linha de cima ja dizia -- e o relatorio
        terminando num tempo limite, que e o sintoma de "o programa travou" e nao o de "falta
        um arquivo". A guarda troca a espera por uma frase.
        """
        texto = _texto(PACOTE / "caissa_primeira_execucao.py")
        corpo = texto[texto.index("def auto_teste") :]
        corpo = corpo[: corpo.index("def _comando_do_auto_teste")]
        assert "p.estado == FALHA" in corpo, (
            "sem esta guarda o assistente chama o `--selftest` sem os pesos e espera "
            "`--tempo-limite` segundos por uma resposta que nao vem"
        )
        assert "bloqueado_por" in corpo
        assert corpo.index("faltando") < corpo.index("subprocess.run"), (
            "conferir depois de chamar nao evita a espera"
        )


# =========================================================================== #
# As pendencias: consertos escritos aqui, em arquivos que esta frente nao possui
# =========================================================================== #
_BLOQUEIO_DE_TORCH = r'''
import sys, json

class _SemTorch:
    """Faz `import torch` levantar, como num ambiente que nunca o instalou."""

    def find_spec(self, nome, caminho=None, alvo=None):
        if nome == "torch" or nome.startswith("torch."):
            raise ModuleNotFoundError(f"No module named {nome!r}")
        return None

for _nome in [n for n in sys.modules if n == "torch" or n.startswith("torch.")]:
    del sys.modules[_nome]
sys.meta_path.insert(0, _SemTorch())
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Controle negativo: sem ele, um bloqueio que nao bloqueia daria "ok" e o teste seria um
# duplo. `dataset` define `class BoardFenDataset(Dataset)` no escopo de modulo -- ele NAO
# pode importar aqui, e o patch nao pretende que importe.
controle = []
for _alvo in ("chess_diagram_ocr.dataset", "chess_diagram_ocr.training"):
    try:
        __import__(_alvo)
    except ModuleNotFoundError:
        controle.append(_alvo)
    except BaseException:
        pass
for _nome in [n for n in sys.modules if n.startswith("chess_diagram_ocr")]:
    del sys.modules[_nome]

try:
    import chess_diagram_ocr.qt.janela  # noqa: F401
except BaseException as exc:
    import traceback
    quadros = [
        f"{f.filename}:{f.lineno}  {(f.line or '').strip()}"
        for f in traceback.extract_tb(exc.__traceback__)
        if "chess_diagram_ocr" in f.filename
    ]
    print(json.dumps({
        "ok": False,
        "erro": f"{type(exc).__name__}: {exc}",
        "quadros": quadros,
        "controle": controle,
    }))
else:
    print(json.dumps({"ok": True, "controle": controle}))
'''


class TestPendencias:
    r"""`packaging/pendencias/` guarda consertos prontos em arquivos do tronco.

    A regra da pasta: **cada pendencia tem um teste que fica vermelho ate o conserto
    entrar**. Um conserto que existe so na cabeca de quem o descobriu e um conserto perdido
    no ciclo seguinte; um teste vermelho e o unico jeito de a lembranca sobreviver a um
    agente.
    """

    def test_a_janela_do_tronco_importa_sem_torch(self) -> None:
        r"""`pendencias/0001`: abrir a janela nao pode exigir o torch que ainda nao chegou.

        O instalador do ciclo 2 nao leva torch. Entre instalar e rodar o assistente existe
        uma janela de tempo em que `Caissa.exe` e chamado sem ele -- e ate 2026-09-09 o
        programa **nao abria**:

            ModuleNotFoundError: No module named 'torch'
              qt/janela.py:92  -> qt/campo.py:37 -> field_eval.py:48 -> checkpoint.py:27

        O diagnostico do ciclo 1 (*"`qt/janela.py` importa torch no topo"*) estava
        incompleto: ela nao importa torch, importa quatro modulos que transitivamente chegam
        nele -- 49 modulos falham num ambiente sem torch, 9 deles em `qt/`. O conserto nao e
        em `qt/`: e cortar quatro arestas em `checkpoint.py`, `inference.py`, `service.py` e
        `ui/pedido_de_treino.py`. O patch e a medicao estao em
        `packaging/pendencias/0001-torch-fora-do-escopo-de-modulo.patch`.

        Este teste importa a janela com o torch bloqueado por um `MetaPathFinder`, que e
        exatamente o ambiente do usuario logo depois de instalar. Ele roda no `.venv-pack`,
        que e o unico que tem PyQt6 -- por isso um subprocesso e nao um import daqui.
        """
        import subprocess

        python = RAIZ / ".venv-pack" / "Scripts" / "python.exe"
        if not python.is_file():
            pytest.skip(f"o ambiente de empacotamento nao existe em {python}")
        if not (TRONCO / "src" / "chess_diagram_ocr" / "qt" / "janela.py").is_file():
            pytest.skip(f"o tronco nao esta em {TRONCO}")

        processo = subprocess.run(  # noqa: S603 - argv fixo
            [str(python), "-c", _BLOQUEIO_DE_TORCH, str(TRONCO / "src"), str(TRONCO)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        saida = (processo.stdout or "").strip().splitlines()
        if not saida:
            pytest.fail(f"a sonda nao imprimiu nada.\nstderr:\n{processo.stderr[-2000:]}")
        dados = json.loads(saida[-1])
        assert set(dados["controle"]) == {
            "chess_diagram_ocr.dataset",
            "chess_diagram_ocr.training",
        }, (
            "o controle negativo falhou: com o torch bloqueado, `dataset` e `training` TEM de "
            "levantar (eles herdam de `nn.Module`/`Dataset` no import). Vieram "
            f"{dados['controle']}. "
            "Sem esse controle, um bloqueio que nao bloqueia faria este teste passar sozinho."
        )
        assert dados["ok"], (
            "a janela do tronco ainda nao importa sem torch. Aplique "
            "`packaging/pendencias/0001-torch-fora-do-escopo-de-modulo.patch` no tronco.\n"
            f"{dados['erro']}\n" + "\n".join("  " + q for q in dados.get("quadros", []))
        )

    def test_a_pendencia_esta_registrada_com_dono_e_teste(self) -> None:
        """Um patch numa pasta, sem dono e sem teste, e um arquivo esquecido com extensao."""
        readme = _texto(PACOTE / "pendencias" / "README.md")
        assert "0001-torch-fora-do-escopo-de-modulo.patch" in readme
        assert "TestPendencias::test_a_janela_do_tronco_importa_sem_torch" in readme.replace(
            "::\n", "::"
        ).replace("\n", "")
        assert (PACOTE / "pendencias" / "0001-torch-fora-do-escopo-de-modulo.patch").is_file()


class TestCoerenciaDoInventario:
    r"""O inventario que viaja dentro do pacote tem de descrever **aquele** pacote.

    Defeito de ordem, medido em 2026-09-09 alternando as duas variantes:
    `preparar_licencas_e_pecas()` roda antes do PyInstaller (tem de rodar -- os textos entram
    como `datas`), e `coletar_licencas._topos_do_toc()` le os `.toc` de `build/`, que naquele
    instante ainda sao os do build anterior. Depois de montar `com-torch` e em seguida a
    padrao, o inventario da padrao saiu afirmando:

        torch | bundle | ['functorch', 'torch', 'torchgen']

    O bundle padrao nao leva torch. O texto da licenca estava la -- o portao de `sem_texto`
    segurou --, mas o documento dizia algo falso sobre o conteudo do pacote.
    """

    def test_o_build_reconfere_o_inventario_depois_do_pyinstaller(self) -> None:
        texto = _texto(PACOTE / "build_windows.py")
        assert "def conferir_licencas_do_bundle" in texto
        corpo = texto[texto.index("def build(") : texto.index("def achar_iscc")]
        assert "conferir_licencas_do_bundle(saida)" in corpo
        assert corpo.index("conferir_licencas_do_bundle(saida)") > corpo.index(
            "PyInstaller falhou"
        ), "reconferir antes do build seria reler o mesmo `.toc` velho"

    def test_o_inventario_dentro_do_bundle_e_o_de_fora_dizem_a_mesma_coisa(
        self, bundle: Path
    ) -> None:
        """A afirmacao final, contra os dois arquivos no disco."""
        dentro = bundle / "_internal" / "licenses" / "INDICE.json"
        assert dentro.is_file(), "o bundle saiu sem inventario de licencas"
        de_dentro = {
            d["distribuicao"]: d["origem"]
            for d in json.loads(dentro.read_text(encoding="utf-8"))["distribuicoes"]
        }
        de_fora = {
            d["distribuicao"]: d["origem"] for d in json.loads(_texto(INDICE))["distribuicoes"]
        }
        assert de_dentro == de_fora, (
            "o inventario que viajou no pacote nao e o que `packaging/licenses/` mede. "
            "Rode o build de novo: a segunda passagem converge."
        )

    def test_o_que_o_inventario_diz_estar_no_bundle_esta_mesmo_la(self, bundle: Path) -> None:
        """A conferencia que fecha o circulo: o documento contra o disco, e nao contra si mesmo.

        A conferencia so vale para distribuicao **com extensao nativa**, e a razao e a mesma
        que fez `_topos_do_toc()` existir: o que e puro Python o PyInstaller congela dentro do
        arquivo compilado e nao aparece como pasta em `_internal/`. `chess`, `platformdirs` e
        `typing_extensions` estao no bundle e nao tem pasta -- procura-las no disco daria um
        falso negativo.

        Quem tem `.pyd`/`.dll`, porem, **tem** de virar pasta. `torch` marcado como `bundle`
        era exatamente isto: uma linha que 365 MB ausentes de `_internal/` desmentiam.
        """
        import importlib.metadata as md

        interno = bundle / "_internal"
        presentes = {p.name for p in interno.iterdir()}
        indice = json.loads(_texto(INDICE))
        erradas: list[str] = []
        for dist in indice["distribuicoes"]:
            if dist["origem"] != "bundle":
                continue
            topos = dist.get("onde_no_bundle") or []
            if not topos:
                continue
            try:
                arquivos = md.distribution(dist["distribuicao"]).files or []
            except md.PackageNotFoundError:
                continue
            if not any(str(f).endswith((".pyd", ".dll", ".so")) for f in arquivos):
                continue  # puro Python: vive dentro do arquivo compilado
            if not (set(topos) & presentes):
                erradas.append(f"{dist['distribuicao']} -> {topos}")
        assert not erradas, (
            "o inventario afirma que estas distribuicoes NATIVAS estao no bundle, e nenhuma "
            f"delas tem pasta em `_internal/`: {erradas}"
        )

    def test_o_que_chega_em_runtime_nao_esta_no_internal(self, bundle: Path) -> None:
        """O outro lado do mesmo erro: nove rodas marcadas como `runtime` que estivessem
        dentro do instalador significariam que o torch voltou a viajar congelado."""
        interno = bundle / "_internal"
        indice = json.loads(_texto(INDICE))
        do_runtime = [
            d["distribuicao"]
            for d in indice["distribuicoes"]
            if str(d.get("origem", "")).startswith("runtime")
        ]
        assert len(do_runtime) == 9, do_runtime
        for pasta in ("torch", "torchvision", "sympy", "networkx", "functorch", "torchgen"):
            assert not (interno / pasta).exists(), f"_internal/{pasta} nao deveria existir"
