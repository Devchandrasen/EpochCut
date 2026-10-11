param([string]$ArchiveName = "EpochCut_Code_Documentation.zip")

$ErrorActionPreference = "Stop"
if ([IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName -or $ArchiveName -notmatch '\.zip$') {
    throw "ArchiveName must be a ZIP filename, not a path"
}
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RunId = [Guid]::NewGuid().ToString("N")
$ReleaseRoot = Join-Path $ProjectRoot "output\release"
$StageRoot = Join-Path $ProjectRoot ("tmp\code-package-" + $RunId)
$ProjectStage = Join-Path $StageRoot "EpochCut"
$VerifyRoot = Join-Path $ProjectRoot ("tmp\code-verify-" + $RunId)
$ExtractedProject = Join-Path $VerifyRoot "EpochCut"
$Archive = Join-Path $ReleaseRoot $ArchiveName
if (Test-Path -LiteralPath $Archive) { throw "Archive exists; choose a new filename: $ArchiveName" }

& python (Join-Path $ProjectRoot "scripts\check_repository.py")
if ($LASTEXITCODE -ne 0) { throw "Repository scope check failed" }
$Files = @(git -C $ProjectRoot ls-files)
if ($LASTEXITCODE -ne 0) { throw "Could not enumerate tracked files" }
New-Item -ItemType Directory -Force -Path $ReleaseRoot, $ProjectStage, $VerifyRoot | Out-Null
foreach ($File in $Files) {
    $Destination = Join-Path $ProjectStage $File
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $Destination
}
Compress-Archive -Path $ProjectStage -DestinationPath $Archive
Expand-Archive -LiteralPath $Archive -DestinationPath $VerifyRoot

$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $ExtractedProject "src"
Push-Location $ExtractedProject
try {
    & python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw "Extracted tests failed" }
    & python examples/quickstart.py | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Extracted graph example failed" }
    & python examples/temporal_quickstart.py | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Extracted temporal example failed" }
    & python scripts/check_repository.py --archive
    if ($LASTEXITCODE -ne 0) { throw "Extracted repository scope or links failed" }
    & python scripts/verify_project_showcase.py
    if ($LASTEXITCODE -ne 0) { throw "Extracted visual checks failed" }
} finally {
    Pop-Location
    $env:PYTHONPATH = $PreviousPythonPath
}
[ordered]@{
    status = "PASS"
    archive = $Archive
    scope = "Code, documentation, tests and conceptual diagrams only"
    files = $Files.Count
    archive_sha256 = (Get-FileHash -LiteralPath $Archive).Hash.ToLowerInvariant()
} | ConvertTo-Json
