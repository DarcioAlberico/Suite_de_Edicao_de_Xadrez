; Origem: Editor_Diagramas_de_Xadrez/packaging/installer.iss
; Absorvido em 2026-09-09 (F12). Alteracoes: dois executaveis em vez de um; as pastas
; gravaveis do usuario passaram a ser criadas e PRESERVADAS na desinstalacao; o assistente
; de primeira execucao roda no fim da instalacao em vez de o programa abrir sem pesos; e a
; pagina que explica por que o instalador e pequeno.
;
; Instalador Windows do Caissa Studio.
;
;     .venv-pack\Scripts\python.exe packaging/build_windows.py --instalador
;
; Ou diretamente, se o ISCC estiver no PATH:
;
;     ISCC.exe packaging/installer.iss /DAppVersion=0.1.0 /DVariant=padrao
;
; Os `#define` abaixo sao so os padroes de quem compila a mao. Quem manda e o
; `build_windows.py`, que os sobrescreve com `/D` -- a versao sai do `pyproject.toml`.
;
; --------------------------------------------------------------------------------------
; NAO COMPILADO NESTA MAQUINA. O Inno Setup nao esta instalado aqui, e por isso o
; `build_windows.py` mede um proxy LZMA2 solido (7-Zip) com a MESMA compressao que o bloco
; [Setup] pede, e o `F12_REPORT_C2.md` diz que e proxy. Este arquivo esta escrito para compilar
; -- `tests/integration/test_packaging.py` confere que cada caminho citado aqui existe --,
; mas ninguem o viu compilar. Ver a secao "o que nao foi verificado" do relatorio.
; --------------------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef Variant
  #define Variant "padrao"
#endif

#define AppName "CaissaStudio"
#define AppDisplayName "Caissa Studio"
#define AppExeName "Caissa.exe"
#define SetupExeName "CaissaPrimeiraExecucao.exe"

; Cada variante empacota a pasta que o `build_windows.py` gerou para ela. Os nomes
; espelham a `caissa.spec`; se um dos dois mudar sem o outro, o teste acusa.
;
; `padrao` e o que se distribui: SEM torch dentro. A variante `com-torch` existe so para o
; F12_REPORT_C2.md medir quanto o torch custaria congelado, e nao e para ser publicada --
; ela entrega a roda de CPU a quem tem uma RTX, que e a troca que o ciclo 2 desfez.
#if Variant == "com-torch"
  #define DistName "Caissa-com-torch"
  #define SetupSuffix "com-torch"
#else
  #define DistName "Caissa"
  #define SetupSuffix "setup"
#endif

; `AddBackslash(...)` e nao `"..\dist\" + DistName`: um literal terminado em contrabarra
; depende de como o pre-processador trata a barra antes das aspas, e isto nao pode ser
; compilado nesta maquina para tirar a duvida. A funcao embutida nao tem essa ambiguidade.
#ifndef SourceDir
  #define SourceDir AddBackslash("..\dist") + DistName
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
; O AppId e o mesmo nas duas variantes de proposito: e o mesmo aplicativo, e quem instalou a
; `com-torch` e depois a `padrao` deve TROCAR de instalacao, nao ficar com duas. Ver
; [InstallDelete], que e onde essa troca deixa de ser uma armadilha.
AppId={{3F9A6C21-7D48-4B0E-9C5A-1E2D8B4A6F30}
AppName={#AppDisplayName}
AppVersion={#AppVersion}
AppVerName={#AppDisplayName} {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=Caissa Studio
DefaultDirName={autopf}\{#AppDisplayName}
DefaultGroupName={#AppDisplayName}
UninstallDisplayName={#AppDisplayName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-{#AppVersion}-{#SetupSuffix}-setup
; O build e x64 e leva binarios nativos (PyMuPDF, Qt, torch).
; `x64` e nao `x64compatible`: o segundo so existe a partir do Inno Setup 6.3, e num
; 6.0-6.2 seria erro de compilacao. `x64` e aceito em todo o 6.x -- nas versoes novas com
; aviso de obsolescencia, que e o modo certo de errar quando nao se pode compilar aqui.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; Sem assinatura de codigo o SmartScreen ja avisa; exigir administrador por cima disso e um
; segundo obstaculo para quem so quer abrir um livro. O padrao e instalacao por usuario, e
; quem quiser para a maquina toda escolhe no dialogo.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; A MESMA compressao que `build_windows.py` usa no proxy de medicao. Se este par mudar, o
; numero publicado no F12_REPORT.md deixa de valer.
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
; O que a licenca obriga a mostrar. AGPL-3.0 por causa do PyMuPDF -- ver LICENSING.md.
LicenseFile={#SourceDir}\_internal\LICENSING.md
; A SPEC secao 2 mede 8 GB de VRAM e disco como restricao critica; o instalador nao pode
; fingir que cabe em qualquer lugar.
MinVersion=10.0.17763

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
brazilianportuguese.WelcomeLabel2=Isto vai instalar o [name/ver] no seu computador.%n%nO instalador e pequeno de proposito: nem os modelos de reconhecimento nem o PyTorch vem dentro dele. Terminada a instalacao, um assistente confere a sua placa de video e instala a versao do PyTorch CERTA PARA ELA -- com uma GPU NVIDIA o reconhecimento fica cerca de 6x mais rapido, e congelar uma escolha unica no instalador tiraria isso de quem tem a placa. Tudo com verificacao SHA-256. Sem internet, o assistente aceita uma pasta local.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; A armadilha que este bloco fecha: instalar a variante `padrao` por cima da `com-torch`
; deixaria o torch da anterior em `_internal`, porque o Inno nao remove o que nao esta na
; lista de arquivos novos. O bundle diria "sem torch" com o motor congelado importavel ao
; lado -- e a roda ERRADA venceria a que o assistente instalou em `runtime/`.
;
; Apaga so o `_internal` do proprio bundle, e nao `{app}` inteiro: `models/`, `runtime/`,
; `data/`, `PDF/`, `PGN/` e `logs/` sao do usuario, e varrer tudo destruiria o que nao e
; nosso -- inclusive os 2,6 GB de torch que ele acabou de baixar, que e o pior jeito
; possivel de atualizar um programa.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; Nascem vazias e SOBREVIVEM a desinstalacao (`uninsneveruninstall`). Um usuario que corrigiu
; 3.000 rotulos e depois desinstalou para reinstalar nao pode perde-los no caminho.
;
; `runtime` e onde o PyTorch e instalado na primeira execucao -- ate 4,2 GB da roda cu128.
; Ele esta nesta lista pelo mesmo motivo dos rotulos, e com mais forca: rebaixar 2,6 GB de
; download a cada atualizacao do programa seria um jeito caro de perder quem instalou.
Name: "{app}\runtime"; Flags: uninsneveruninstall
Name: "{app}\models"; Flags: uninsneveruninstall
Name: "{app}\data";   Flags: uninsneveruninstall
Name: "{app}\PDF";    Flags: uninsneveruninstall
Name: "{app}\PGN";    Flags: uninsneveruninstall
Name: "{app}\logs";   Flags: uninsneveruninstall

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Primeira execucao (conferir a placa, instalar PyTorch e modelos)"; Filename: "{app}\{#SetupExeName}"; Parameters: "--pausar"
Name: "{group}\{cm:UninstallProgram,{#AppDisplayName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; A ORDEM importa e e o ponto deste bloco. O assistente roda ANTES de o programa abrir: uma
; janela que sobe sem pesos e uma primeira impressao de coisa quebrada, e o diagnostico que
; explicaria o vazio so apareceria depois de o usuario ja ter concluido que nao funciona.
Filename: "{app}\{#SetupExeName}"; Parameters: "--pausar"; Description: "Conferir a placa de video, instalar o PyTorch certo e os modelos (recomendado)"; Flags: postinstall skipifsilent
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppDisplayName}}"; Flags: nowait postinstall skipifsilent unchecked
