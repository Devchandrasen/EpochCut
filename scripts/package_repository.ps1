$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleaseRoot = Join-Path $ProjectRoot "output\release"
$ScratchRoot = Join-Path $ProjectRoot "tmp"
$RunId = [Guid]::NewGuid().ToString("N")
$StageRoot = Join-Path $ScratchRoot ("repository_stage_" + $RunId)
$ProjectStage = Join-Path $StageRoot "EpochCut"
$VerifyRoot = Join-Path $ScratchRoot ("repository_verify_" + $RunId)
$ExtractedProject = Join-Path $VerifyRoot "EpochCut"
$Archive = Join-Path $ReleaseRoot "EpochCut_Project_Repository.zip"

New-Item -ItemType Directory -Force -Path $ReleaseRoot, $ProjectStage, $VerifyRoot | Out-Null

$Files = @(".gitattributes", ".gitignore", "CITATION.cff", "README.md", "SECURITY.md", "pyproject.toml")
foreach ($File in $Files) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $ProjectStage
}

$Directories = @(
    ".github",
    "configs",
    "docs",
    "evaluation",
    "examples",
    "results",
    "scripts",
    "src",
    "tests"
)
foreach ($Directory in $Directories) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Directory) -Destination $ProjectStage -Recurse
}

$PaperStage = Join-Path $ProjectStage "paper"
New-Item -ItemType Directory -Force -Path (Join-Path $PaperStage "figures") | Out-Null
foreach ($PaperFile in @("main.tex", "references.bib", "main.pdf")) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ("paper\" + $PaperFile)) -Destination $PaperStage
}
$FigureFiles = @(
    "architecture.drawio",
    "architecture.pdf",
    "architecture.png",
    "latency_scaling.pdf",
    "latency_scaling.png",
    "mcp_llm_security.pdf",
    "mcp_llm_security.png",
    "security_cost.pdf",
    "security_cost.png"
)
foreach ($FigureFile in $FigureFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ("paper\figures\" + $FigureFile)) -Destination (Join-Path $PaperStage "figures")
}

Compress-Archive -Path $ProjectStage -DestinationPath $Archive -Force
Expand-Archive -LiteralPath $Archive -DestinationPath $VerifyRoot

$Expected = @(
    "README.md",
    "CITATION.cff",
    "SECURITY.md",
    ".github\workflows\ci.yml",
    "docs\GETTING_STARTED.md",
    "examples\quickstart.py",
    "src\epochcut\engine.py",
    "results\analysis\confirmatory_analysis.json",
    "paper\main.pdf"
)
$Missing = @(
    $Expected | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $ExtractedProject $_) -PathType Leaf)
    }
)
if ($Missing.Count -gt 0) {
    throw "Fresh-extract repository verification failed: $($Missing -join ', ')"
}

$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $ExtractedProject "src"
Push-Location $ExtractedProject
try {
    & python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Extracted repository tests failed" }
    & python examples/quickstart.py | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Extracted repository quick start failed" }
    & python scripts/verify_artifacts.py
    if ($LASTEXITCODE -ne 0) { throw "Extracted repository artifact verification failed" }
} finally {
    Pop-Location
    $env:PYTHONPATH = $PreviousPythonPath
}

[ordered]@{
    status = "PASS"
    archive = $Archive
    extracted_files_checked = $Expected.Count
    tests_rerun = $true
    quickstart_rerun = $true
    artifacts_reverified = $true
    archive_sha256 = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json
