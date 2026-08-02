param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:\.\d+)?$')]
    [string]$Version = "1.0.42",

    [Parameter(Mandatory = $false)]
    [string]$Python = "python",

    [Parameter(Mandatory = $false)]
    [string]$Iscc = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleaseRoot = Join-Path $Root "release"
$AppDirectory = Join-Path $Root "build\main-dist\Waukeen Crafting Assistant"
$InstallerScript = Join-Path $Root "installer\WaukeenCraftingAssistant.iss"

& (Join-Path $PSScriptRoot "build_release.ps1") -Version $Version -Python $Python
if ($LASTEXITCODE -ne 0) {
    throw "Application build failed with exit code $LASTEXITCODE."
}

if (-not $Iscc) {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    $Iscc = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if (-not $Iscc -or -not (Test-Path -LiteralPath $Iscc)) {
    throw "Inno Setup 6 bulunamadi. ISCC yolunu -Iscc ile belirtin."
}

& $Iscc `
    "/DAppVersion=$Version" `
    "/DSourceDir=$AppDirectory" `
    "/DOutputDir=$ReleaseRoot" `
    $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Setup build failed with exit code $LASTEXITCODE."
}

$SetupPath = Join-Path $ReleaseRoot "Waukeen-Crafting-Assistant-Setup-v$Version.exe"
if (-not (Test-Path -LiteralPath $SetupPath)) {
    throw "Setup executable was not produced."
}
$Hash = (Get-FileHash -LiteralPath $SetupPath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText("$SetupPath.sha256", "$Hash *$(Split-Path $SetupPath -Leaf)`n", (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Setup:   $SetupPath"
Write-Host "SHA-256: $Hash"
