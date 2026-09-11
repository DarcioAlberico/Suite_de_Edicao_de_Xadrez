#Requires -Version 5.1
<#
.SYNOPSIS
    CI local do Caissa Studio: ruff, mypy e pytest.

.DESCRIPTION
    Executa as tres portas de qualidade e sai com codigo diferente de zero se
    qualquer uma reprovar. Todas as etapas rodam mesmo que uma anterior falhe,
    para que um unico ciclo mostre todos os problemas.

      1. ruff check      -- lint
      2. ruff format     -- formatacao (apenas verifica; use -Fix para aplicar)
      3. mypy            -- tipos (strict em caissa.core, por pyproject.toml)
      4. pytest          -- testes

.PARAMETER Fix
    Aplica as correcoes automaticas do ruff (lint --fix e format) antes de
    verificar.

.PARAMETER NoTests
    Pula o pytest.

.PARAMETER Coverage
    Roda o pytest com relatorio de cobertura.

.PARAMETER PytestArgs
    Argumentos extras repassados ao pytest (ex.: -PytestArgs "-k residency").

.PARAMETER Paths
    Restringe ruff e mypy a caminhos especificos. Sem este parametro as portas
    valem para o repositorio inteiro, que e o comportamento correto do portao.
    Use-o durante o desenvolvimento de uma frente para ver apenas os problemas
    da sua propria area:

        .\scripts\check.ps1 -Paths "src\caissa\vision\runtime","tests\unit"

.EXAMPLE
    .\scripts\check.ps1

.EXAMPLE
    .\scripts\check.ps1 -Fix -Coverage
#>
[CmdletBinding()]
param(
    [switch] $Fix,
    [switch] $NoTests,
    [switch] $Coverage,
    [string] $PytestArgs = "",
    [string[]] $Paths = @()
)

$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Ambiente virtual nao encontrado em $VenvPython" -ForegroundColor Red
    Write-Host "Execute primeiro: .\scripts\setup_env.ps1" -ForegroundColor Red
    exit 1
}

$Results = [System.Collections.Generic.List[object]]::new()

function Invoke-Gate {
    param(
        [Parameter(Mandatory)] [string]   $Name,
        [Parameter(Mandatory)] [string[]] $Arguments
    )
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    Write-Host "> python $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $VenvPython @Arguments
    $code = $LASTEXITCODE
    $Results.Add([pscustomobject]@{ Name = $Name; ExitCode = $code }) | Out-Null
    if ($code -eq 0) {
        Write-Host "$Name : OK" -ForegroundColor Green
    }
    else {
        Write-Host "$Name : FALHOU (codigo $code)" -ForegroundColor Red
    }
    return $code
}

Push-Location $RepoRoot
try {
    # `powershell.exe -File check.ps1 -Paths "a","b"` collapses the array into a
    # single comma-joined string, so accept both shapes.
    $scope = @()
    foreach ($item in $Paths) {
        foreach ($part in ($item -split ',')) {
            $clean = $part.Trim().Trim('"').Trim("'")
            if ($clean) { $scope += $clean }
        }
    }

    $ruffTargets = if ($scope.Count -gt 0) { $scope } else { @(".") }
    $mypyTargets = if ($scope.Count -gt 0) { $scope } else { @() }
    if ($scope.Count -gt 0) {
        Write-Host ""
        Write-Host "Escopo restrito a: $($scope -join ', ')" -ForegroundColor Yellow
    }

    if ($Fix) {
        Write-Host ""
        Write-Host "=== ruff (correcao automatica) ===" -ForegroundColor Cyan
        & $VenvPython -m ruff check --fix @ruffTargets
        & $VenvPython -m ruff format @ruffTargets
    }

    Invoke-Gate -Name "ruff check" -Arguments (@("-m", "ruff", "check") + $ruffTargets) | Out-Null
    Invoke-Gate -Name "ruff format --check" -Arguments (@("-m", "ruff", "format", "--check") + $ruffTargets) | Out-Null
    Invoke-Gate -Name "mypy" -Arguments (@("-m", "mypy") + $mypyTargets) | Out-Null

    if (-not $NoTests) {
        $pytest = @("-m", "pytest")
        if ($Coverage) {
            $pytest += @("--cov=caissa", "--cov-report=term-missing:skip-covered")
        }
        if (-not [string]::IsNullOrWhiteSpace($PytestArgs)) {
            $pytest += ($PytestArgs -split '\s+')
        }
        Invoke-Gate -Name "pytest" -Arguments $pytest | Out-Null
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "===============================================================================" -ForegroundColor White
Write-Host " RESUMO" -ForegroundColor White
Write-Host "===============================================================================" -ForegroundColor White
$failed = 0
foreach ($result in $Results) {
    if ($result.ExitCode -eq 0) {
        Write-Host ("  [ OK ]    {0}" -f $result.Name) -ForegroundColor Green
    }
    else {
        Write-Host ("  [FALHA]   {0} (codigo {1})" -f $result.Name, $result.ExitCode) -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
if ($failed -eq 0) {
    Write-Host " Todas as portas de qualidade passaram." -ForegroundColor Green
    exit 0
}

Write-Host " $failed porta(s) reprovada(s)." -ForegroundColor Red
exit 1
