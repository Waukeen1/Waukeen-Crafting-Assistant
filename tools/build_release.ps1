param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:\.\d+)?$')]
    [string]$Version = "1.0.49",

    [Parameter(Mandatory = $false)]
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $Root "build"
$ReleaseRoot = Join-Path $Root "release"
$GeneratedRoot = Join-Path $BuildRoot "generated"
$UpdaterPayload = Join-Path $BuildRoot "updater-payload"
$DataPayload = Join-Path $BuildRoot "data-payload"
$MainDist = Join-Path $BuildRoot "main-dist"
$UpdaterDist = Join-Path $BuildRoot "updater-dist"
$WorkRoot = Join-Path $BuildRoot "work"
$SpecRoot = Join-Path $BuildRoot "spec"
$PackageName = "Waukeen-Crafting-Assistant-Windows.zip"
$PackagePath = Join-Path $ReleaseRoot $PackageName
$ChecksumPath = "$PackagePath.sha256"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not $BuildRoot.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Build path escaped the repository."
}

foreach ($path in @($BuildRoot, $ReleaseRoot)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
foreach ($path in @($GeneratedRoot, $UpdaterPayload, $DataPayload, $MainDist, $UpdaterDist, $WorkRoot, $SpecRoot)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

$SensitiveRuntimeFiles = @(
    "proxies.json",
    "settings.json",
    "trade_rate_limit_state.json",
    "cluster_template_audit_Allflame.json"
)
Copy-Item -Path (Join-Path $Root "data\*") -Destination $DataPayload -Recurse -Force
foreach ($fileName in $SensitiveRuntimeFiles) {
    $runtimePath = Join-Path $DataPayload $fileName
    if (Test-Path -LiteralPath $runtimePath) {
        Remove-Item -LiteralPath $runtimePath -Force
    }
}

$versionParts = @($Version.Split(".") | ForEach-Object { [int]$_ })
while ($versionParts.Count -lt 4) {
    $versionParts += 0
}
$versionTuple = $versionParts[0..3] -join ", "

$buildInfo = [ordered]@{
    version = $Version
    repository = "Waukeen1/Waukeen-Crafting-Assistant"
    channel = "stable"
} | ConvertTo-Json
[System.IO.File]::WriteAllText(
    (Join-Path $GeneratedRoot "build_info.json"),
    "$buildInfo`n",
    $Utf8NoBom
)

# Never ship the developer machine's Voyage coordinates. The application now
# calibrates from the active PoE client and keeps these values as manual fallback.
$ReleaseSettingsPath = Join-Path $GeneratedRoot "settings.ini"
$releaseSettings = Get-Content -LiteralPath (Join-Path $Root "settings.ini") -Raw
$releaseSettings = [regex]::Replace(
    $releaseSettings,
    '(?m)^(chart_grid_tl|chart_grid_br|board_grid_tl|board_grid_br)\s*=.*$',
    '$1 ='
)
$releaseSettings = [regex]::Replace(
    $releaseSettings,
    '(?m)^topic\s*=.*$',
    'topic ='
)
$releaseSettings = [regex]::Replace(
    $releaseSettings,
    '(?m)^(enabled|life_enabled|mana_enabled)\s*=.*$',
    '$1 = False'
)
[System.IO.File]::WriteAllText($ReleaseSettingsPath, $releaseSettings, $Utf8NoBom)

function Write-VersionInfo {
    param(
        [string]$Path,
        [string]$Description,
        [string]$InternalName,
        [string]$OriginalFilename
    )
    $content = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($versionTuple),
    prodvers=($versionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Waukeen'),
          StringStruct(u'FileDescription', u'$Description'),
          StringStruct(u'FileVersion', u'$Version'),
          StringStruct(u'InternalName', u'$InternalName'),
          StringStruct(u'OriginalFilename', u'$OriginalFilename'),
          StringStruct(u'ProductName', u'Waukeen Crafting Assistant'),
          StringStruct(u'ProductVersion', u'$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@
    [System.IO.File]::WriteAllText($Path, $content, $Utf8NoBom)
}

$MainVersionInfo = Join-Path $GeneratedRoot "main-version-info.txt"
$UpdaterVersionInfo = Join-Path $GeneratedRoot "updater-version-info.txt"
Write-VersionInfo $MainVersionInfo "Waukeen Crafting Assistant" "Waukeen Crafting Assistant" "Waukeen Crafting Assistant.exe"
Write-VersionInfo $UpdaterVersionInfo "WCA Safe Updater" "WCA Updater" "WCA Updater.exe"

Push-Location $Root
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "WCA Updater" `
        --icon (Join-Path $Root "assets\wca_icon.ico") `
        --version-file $UpdaterVersionInfo `
        --distpath $UpdaterDist `
        --workpath (Join-Path $WorkRoot "updater") `
        --specpath $SpecRoot `
        (Join-Path $Root "wca_updater.pyw")
    if ($LASTEXITCODE -ne 0) {
        throw "Updater build failed with exit code $LASTEXITCODE."
    }

    Copy-Item `
        -LiteralPath (Join-Path $UpdaterDist "WCA Updater.exe") `
        -Destination (Join-Path $UpdaterPayload "WCA Updater.exe") `
        -Force

    $mainArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", "Waukeen Crafting Assistant",
        "--icon", (Join-Path $Root "assets\wca_icon.ico"),
        "--version-file", $MainVersionInfo,
        "--distpath", $MainDist,
        "--workpath", (Join-Path $WorkRoot "main"),
        "--specpath", $SpecRoot,
        "--hidden-import", "win32clipboard",
        "--hidden-import", "winrt.system",
        "--hidden-import", "winrt.windows.graphics.capture",
        "--hidden-import", "winrt.windows.graphics.capture.interop",
        "--hidden-import", "winrt.windows.graphics.directx",
        "--hidden-import", "winrt.windows.graphics.directx.direct3d11.interop",
        "--hidden-import", "winrt.windows.graphics.imaging",
        "--hidden-import", "winrt.windows.media.ocr",
        "--hidden-import", "winrt.windows.storage.streams",
        "--collect-all", "dxcam",
        "--add-data", "$ReleaseSettingsPath;.",
        "--add-data", "$(Join-Path $GeneratedRoot 'build_info.json');.",
        "--add-data", "$(Join-Path $Root 'assets\wca_icon.png');assets",
        "--add-data", "$(Join-Path $Root 'assets\wca_icon.ico');assets",
        "--add-data", "$DataPayload;data",
        "--add-data", "$(Join-Path $Root 'itemcraft');itemcraft",
        "--add-data", "$(Join-Path $Root 'mapcraft');mapcraft",
        "--add-data", "$(Join-Path $Root 'basejewelcraft');basejewelcraft",
        "--add-data", "$(Join-Path $Root 'genericitemcraft');genericitemcraft",
        "--add-data", "$UpdaterPayload;updater",
        (Join-Path $Root "cluster_craft.pyw")
    )
    & $Python @mainArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Main application build failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

$AppDirectory = Join-Path $MainDist "Waukeen Crafting Assistant"
if (-not (Test-Path -LiteralPath (Join-Path $AppDirectory "Waukeen Crafting Assistant.exe"))) {
    throw "Built application executable was not found."
}

Compress-Archive -Path (Join-Path $AppDirectory "*") -DestinationPath $PackagePath -CompressionLevel Optimal
$Hash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    $ChecksumPath,
    "$Hash *$PackageName`n",
    $Utf8NoBom
)

Write-Host "Application: $AppDirectory"
Write-Host "Package:     $PackagePath"
Write-Host "SHA-256:    $Hash"
