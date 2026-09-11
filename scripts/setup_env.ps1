#Requires -Version 5.1
<#
.SYNOPSIS
    Cria e atualiza o ambiente de desenvolvimento do Caissa Studio.

.DESCRIPTION
    Idempotente: pode ser executado quantas vezes for necessario. Cada etapa
    verifica o estado atual antes de agir e informa se pulou ou executou.

    Etapas:
      1. Localiza o Python 3.11 (alvo do projeto, SPEC R5).
      2. Cria .venv se ainda nao existir.
      3. Atualiza o pip.
      4. Instala o projeto em modo editavel com os extras pedidos.
      5. Instala o PyTorch a partir do indice cu128 -- obrigatorio para a GPU
         Blackwell sm_120 desta maquina (SPEC R1).
      6. Verifica que onnxruntime-gpu NAO esta neste ambiente (ADR-0003) e roda
         pip check.
      7. Executa scripts/doctor.py.

    O PyTorch nao esta no pyproject.toml de proposito: as rodas cu128 so existem
    em https://download.pytorch.org/whl/cu128, um indice que nao pode ser
    declarado de forma portavel em dependencies.

.PARAMETER Extras
    Extras a instalar, separados por virgula. Padrao: "dev".
    Opcoes: core (implicito), vision, ocr, ui, export, dev, all.

.PARAMETER Recreate
    Apaga e recria o .venv do zero.

.PARAMETER SkipTorch
    Nao instala nem verifica o PyTorch.

.PARAMETER TorchIndex
    Indice alternativo de rodas do PyTorch.

.PARAMETER NoDoctor
    Nao executa scripts/doctor.py ao final.

.EXAMPLE
    .\scripts\setup_env.ps1

.EXAMPLE
    .\scripts\setup_env.ps1 -Extras "dev,vision,ui" -Recreate
#>
[CmdletBinding()]
param(
    [string] $Extras = "dev",
    [switch] $Recreate,
    [switch] $SkipTorch,
    [string] $TorchIndex = "https://download.pytorch.org/whl/cu128",
    [switch] $NoDoctor
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$StepNumber = 0
$TotalSteps = 7
$StartedAt = Get-Date

function Write-Step {
    param([string] $Message)
    $script:StepNumber++
    Write-Host ""
    Write-Host ("[{0}/{1}] {2}" -f $script:StepNumber, $TotalSteps, $Message) -ForegroundColor Cyan
    Write-Host ("       " + ("-" * 62)) -ForegroundColor DarkGray
}

function Write-Info { param([string] $Message) Write-Host "       $Message" }
function Write-Good { param([string] $Message) Write-Host "       $Message" -ForegroundColor Green }
function Write-Warn { param([string] $Message) Write-Host "       $Message" -ForegroundColor Yellow }
function Write-Bad  { param([string] $Message) Write-Host "       $Message" -ForegroundColor Red }

# Native tools legitimately write to stderr (pip warnings, "package not found").
# With $ErrorActionPreference = "Stop" PowerShell turns that into a terminating
# NativeCommandError, so every native call is made from a function that lowers the
# preference locally and judges success by $LASTEXITCODE instead.
function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]   $Exe,
        [Parameter(Mandatory)] [string[]] $Arguments,
        [Parameter(Mandatory)] [string]   $What
    )
    $ErrorActionPreference = "Continue"
    Write-Info "> $Exe $($Arguments -join ' ')"
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$What falhou (codigo $LASTEXITCODE)."
    }
}

function Invoke-Capture {
    param(
        [Parameter(Mandatory)] [string]   $Exe,
        [Parameter(Mandatory)] [string[]] $Arguments
    )
    $ErrorActionPreference = "Continue"
    $output = & $Exe @Arguments 2>&1
    return [pscustomobject]@{
        Text     = ($output | Out-String)
        ExitCode = $LASTEXITCODE
    }
}

function Get-InstalledVersion {
    param([string] $Package)
    $result = Invoke-Capture -Exe $VenvPython -Arguments @("-m", "pip", "list", "--format=json", "--disable-pip-version-check")
    if ($result.ExitCode -ne 0) { return $null }
    try { $packages = $result.Text | ConvertFrom-Json } catch { return $null }
    foreach ($entry in $packages) {
        if ($entry.name -and $entry.name.ToLower() -eq $Package.ToLower()) { return $entry.version }
    }
    return $null
}

Write-Host ""
Write-Host "===============================================================================" -ForegroundColor White
Write-Host " Caissa Studio - preparacao do ambiente de desenvolvimento" -ForegroundColor White
Write-Host " Projeto : $RepoRoot"
Write-Host " Extras  : $Extras"
Write-Host "===============================================================================" -ForegroundColor White

# --------------------------------------------------------------------------- #
# 1. Interpretador
# --------------------------------------------------------------------------- #
Write-Step "Localizando o Python 3.11 (alvo do projeto, SPEC R5)"

$BasePython = $null
$candidates = @()

$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    $probe = Invoke-Capture -Exe "py" -Arguments @("-3.11", "-c", "import sys; print(sys.executable)")
    if ($probe.ExitCode -eq 0 -and $probe.Text.Trim()) { $candidates += $probe.Text.Trim() }
}
$candidates += @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
    "C:\Python311\python.exe",
    "C:\Program Files\Python311\python.exe"
)

foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
        $probe = Invoke-Capture -Exe $candidate -Arguments @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        if ($probe.ExitCode -eq 0 -and $probe.Text.Trim() -eq "3.11") {
            $BasePython = $candidate
            break
        }
    }
}

if (-not $BasePython) {
    Write-Bad "Python 3.11 nao encontrado."
    Write-Bad "Instale-o (https://www.python.org/downloads/release/python-3119/) e repita."
    Write-Bad "Candidatos testados:"
    $candidates | ForEach-Object { Write-Bad "  - $_" }
    exit 1
}
$fullVersion = (Invoke-Capture -Exe $BasePython -Arguments @("-c", "import sys; print(sys.version.split()[0])")).Text.Trim()
Write-Good "Python $fullVersion em $BasePython"

# --------------------------------------------------------------------------- #
# 2. Ambiente virtual
# --------------------------------------------------------------------------- #
Write-Step "Preparando o ambiente virtual (.venv)"

if ($Recreate -and (Test-Path -LiteralPath $VenvDir)) {
    Write-Warn "Removendo o .venv existente (-Recreate)..."
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
}

if (Test-Path -LiteralPath $VenvPython) {
    $venvVersion = (Invoke-Capture -Exe $VenvPython -Arguments @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")).Text.Trim()
    if ($venvVersion -ne "3.11") {
        Write-Warn "O .venv existente usa Python $venvVersion; recriando com 3.11."
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
    else {
        Write-Good "Reutilizando o .venv existente (Python $venvVersion)."
    }
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Invoke-Checked -Exe $BasePython -Arguments @("-m", "venv", $VenvDir) -What "Criacao do venv"
    Write-Good "Ambiente virtual criado em $VenvDir"
}

# --------------------------------------------------------------------------- #
# 3. pip
# --------------------------------------------------------------------------- #
Write-Step "Atualizando o pip"
# Apenas o pip: builds PEP 517 trazem seu proprio setuptools em ambiente isolado,
# e atualizar o setuptools do venv a forca quebra a restricao setuptools<82 que as
# rodas do torch declaram.
Invoke-Checked -Exe $VenvPython `
    -Arguments @("-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "pip") `
    -What "Atualizacao do pip"
$pipVersion = (Invoke-Capture -Exe $VenvPython -Arguments @("-m", "pip", "--version")).Text.Trim()
Write-Good $pipVersion

# --------------------------------------------------------------------------- #
# 4. Projeto em modo editavel
# --------------------------------------------------------------------------- #
Write-Step "Instalando o projeto em modo editavel: pip install -e `".[$Extras]`""
Push-Location $RepoRoot
try {
    $target = if ([string]::IsNullOrWhiteSpace($Extras)) { "." } else { ".[$Extras]" }
    Invoke-Checked -Exe $VenvPython `
        -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-e", $target) `
        -What "Instalacao editavel"
}
finally {
    Pop-Location
}
Write-Good "Pacote caissa instalado em modo editavel."

# --------------------------------------------------------------------------- #
# 5. PyTorch cu128
# --------------------------------------------------------------------------- #
Write-Step "PyTorch com kernels para Blackwell sm_120 (SPEC R1)"

if ($SkipTorch) {
    Write-Warn "Pulado por -SkipTorch."
}
else {
    $needsInstall = $true
    $torchProbeCode = "try:`n    import torch, json`n    print(json.dumps({'version': torch.__version__, 'cuda': torch.version.cuda}))`nexcept Exception:`n    print('')"
    $torchProbe = Invoke-Capture -Exe $VenvPython -Arguments @("-c", $torchProbeCode)
    $torchInfo = ($torchProbe.Text -split "`n" | Where-Object { $_.Trim().StartsWith("{") } | Select-Object -First 1)

    if ($torchProbe.ExitCode -eq 0 -and $torchInfo) {
        try {
            $parsed = $torchInfo.Trim() | ConvertFrom-Json
            $cuda = $parsed.cuda
            if ($cuda) {
                $parts = $cuda.Split('.')
                $major = [int]$parts[0]
                $minor = if ($parts.Length -gt 1) { [int]$parts[1] } else { 0 }
                if (($major -gt 12) -or ($major -eq 12 -and $minor -ge 8)) {
                    Write-Good "torch $($parsed.version) (CUDA $cuda) ja atende ao requisito cu128; nada a fazer."
                    $needsInstall = $false
                }
                else {
                    Write-Warn "torch $($parsed.version) foi compilado com CUDA $cuda -- antigo demais para sm_120. Reinstalando."
                }
            }
            else {
                Write-Warn "A instalacao atual do torch e a versao somente-CPU. Reinstalando com cu128."
            }
        }
        catch {
            Write-Warn "Nao foi possivel interpretar a versao do torch instalado; reinstalando."
        }
    }
    else {
        Write-Info "PyTorch ainda nao esta instalado neste ambiente."
    }

    if ($needsInstall) {
        Write-Info "Baixando as rodas cu128 (~3 GB na primeira vez). Isso demora."
        Invoke-Checked -Exe $VenvPython `
            -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "--index-url", $TorchIndex, "torch", "torchvision") `
            -What "Instalacao do PyTorch cu128"
        Write-Good "PyTorch instalado a partir de $TorchIndex"
    }
}

# --------------------------------------------------------------------------- #
# 6. ADR-0003
# --------------------------------------------------------------------------- #
Write-Step "Verificando o isolamento do ONNX Runtime (ADR-0003)"

$ortGpu = Get-InstalledVersion "onnxruntime-gpu"
if ($ortGpu) {
    Write-Bad "onnxruntime-gpu $ortGpu esta instalado NESTE ambiente."
    Write-Bad "Isso viola o ADR-0003: a partir da 1.27 o pacote e compilado contra CUDA 13.0,"
    Write-Bad "enquanto as rodas Blackwell do torch usam CUDA 12.8. Carregar os dois no mesmo"
    Write-Bad "processo causa conflito de DLL ou -- pior -- queda silenciosa para CPU."
    Write-Bad "Remova com: .venv\Scripts\python.exe -m pip uninstall -y onnxruntime-gpu"
}
else {
    Write-Good "onnxruntime-gpu ausente deste ambiente -- correto."
}

$ortCpu = Get-InstalledVersion "onnxruntime"
if ($ortCpu) {
    Write-Warn "onnxruntime $ortCpu (CPU) esta instalado. Nao conflita com o CUDA do torch,"
    Write-Warn "mas o caminho acelerado exige o worker isolado mesmo assim."
}

$pipCheck = Invoke-Capture -Exe $VenvPython -Arguments @("-m", "pip", "check")
if ($pipCheck.ExitCode -ne 0) {
    Write-Warn "pip check apontou conflitos de dependencia:"
    $pipCheck.Text.Trim() -split "`n" | ForEach-Object { Write-Warn "  $_" }
}
else {
    Write-Good "pip check: nenhum conflito de dependencia."
}

Write-Host ""
Write-Info "NOTA (ADR-0003): o ONNX Runtime NAO e instalado aqui."
Write-Info "Os modelos proprios (detector e classificador de casas) sao PyTorch nativo e"
Write-Info "rodam neste processo. Os motores de terceiros que so existem em ONNX rodam em um"
Write-Info "PROCESSO TRABALHADOR SEPARADO, com ambiente virtual proprio (.venv-onnx) e seu"
Write-Info "proprio CUDA Runtime, comunicando-se por memoria compartilhada. Esse ambiente e"
Write-Info "criado por um script separado (scripts/setup_onnx_worker.ps1, entregue na frente"
Write-Info "F5, quando o primeiro motor ONNX for integrado). Enquanto ele nao existir, a"
Write-Info "configuracao vision.onnx_worker_enabled permanece false e nada muda."

# --------------------------------------------------------------------------- #
# 7. Diagnostico
# --------------------------------------------------------------------------- #
Write-Step "Relatorio de saude do ambiente"

$elapsed = (Get-Date) - $StartedAt
Write-Info ("Tempo decorrido ate aqui: {0:mm\:ss}" -f $elapsed)

if ($NoDoctor) {
    Write-Warn "Pulado por -NoDoctor. Execute manualmente:"
    Write-Warn "  .venv\Scripts\python.exe scripts\doctor.py"
    exit 0
}

Write-Host ""
$ErrorActionPreference = "Continue"
& $VenvPython (Join-Path $PSScriptRoot "doctor.py")
$doctorExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"

Write-Host ""
if ($doctorExit -eq 0) {
    Write-Host " Ambiente pronto. Proximos passos:" -ForegroundColor Green
    Write-Host "   .\scripts\check.ps1                       # lint + tipos + testes"
    Write-Host "   .venv\Scripts\python.exe scripts\doctor.py --json > report.json"
}
else {
    Write-Host " O doctor reprovou o ambiente (codigo $doctorExit)." -ForegroundColor Red
    Write-Host " Leia as linhas [ FALHA] acima: cada uma traz a causa e a correcao." -ForegroundColor Red
}

exit $doctorExit
