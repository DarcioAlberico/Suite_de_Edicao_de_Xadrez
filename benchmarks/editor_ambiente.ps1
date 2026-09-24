# Ambiente dos portoes do Editor HTML/CSS -- EDITOR_HTML_CSS_ROADMAP.md secao 0.2 (passo H0).
#
# Uso, na raiz da suite:
#     . .\benchmarks\editor_ambiente.ps1
#     & $PY benchmarks\editor_portoes.py --passo H0 --saida benchmarks\reports\editor\h0
#
# So ASCII neste arquivo: o PowerShell 5 le um .ps1 sem BOM na pagina de codigo do sistema, e o
# travessao do nome do livro do pedido viraria outro caractere. Os livros sao achados pelo nome
# com curinga, e o script para se algum faltar.

$RAIZ = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
# Numa arvore de `git worktree` (a do critico, uma arvore limpa) nao ha .venv, e o tronco nao e a
# pasta vizinha: os dois vem do checkout principal.
$PRINCIPAL = Split-Path -Parent (git -C $RAIZ rev-parse --path-format=absolute --git-common-dir)
$TRONCO = (Resolve-Path (Join-Path $PRINCIPAL "..\ChessVisionOFF_Puro")).Path

function Get-AmbienteVirtual([string]$Nome) {
    foreach ($base in @($RAIZ, $PRINCIPAL)) {
        $candidato = Join-Path $base "$Nome\Scripts\python.exe"
        if (Test-Path -LiteralPath $candidato) { return $candidato }
    }
    return (Join-Path $RAIZ "$Nome\Scripts\python.exe")
}

$PY = Get-AmbienteVirtual ".venv"                           # suite, pytest
$PACK = Get-AmbienteVirtual ".venv-pack"                    # PyQt6/PyMuPDF do pacote
$PYQ = Join-Path $TRONCO ".venv\Scripts\python.exe"         # tronco
# So para medir (o produto nao leva): o pywinauto da sonda UIA do H2.
$MED = Get-AmbienteVirtual ".venv-medicao"
$SITE_DO_PACOTE = Join-Path (Split-Path -Parent (Split-Path -Parent $PACK)) "Lib\site-packages"

$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QPA_FONTDIR = "C:\Windows\Fonts"
$env:PYTHONIOENCODING = "utf-8"

function Enter-AmbienteDosPortoes {
    $env:PYTHONPATH = "$RAIZ\src;$TRONCO\src;$SITE_DO_PACOTE"
}

function Enter-AmbienteDosTestesQt {
    $env:PYTHONPATH = "$SITE_DO_PACOTE"
}

function Get-LivroDoEditor([string]$Padrao) {
    $achado = Get-ChildItem -LiteralPath (Join-Path $TRONCO "PDF") -Filter $Padrao -File |
        Select-Object -First 1
    if (-not $achado) { throw "livro ausente em $TRONCO\PDF: $Padrao" }
    return $achado.FullName
}

$PEDIDO = Get-LivroDoEditor "A Matter of Endgame Technique*Jacob Aagaard.pdf"   # p. 55; 898 p.
$LIVRO = Get-LivroDoEditor "AAGAARD - Practical Chess Defence.pdf"               # p. 31-38
$KEMERI = Get-LivroDoEditor "1937 Kemeri.pdf"                                    # p. 80
$DEM = Get-LivroDoEditor "Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf"     # nativo

foreach ($interprete in @($PY, $PACK, $PYQ, $MED)) {
    if (-not (Test-Path -LiteralPath $interprete)) { Write-Warning "interprete ausente: $interprete" }
}
