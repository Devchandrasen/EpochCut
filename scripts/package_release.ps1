$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputRoot = Join-Path $ProjectRoot "output"
$PdfRoot = Join-Path $OutputRoot "pdf"
$ReleaseRoot = Join-Path $OutputRoot "release"
$ScratchRoot = Join-Path $ProjectRoot "tmp"

New-Item -ItemType Directory -Force -Path $PdfRoot, $ReleaseRoot, $ScratchRoot | Out-Null

$FinalPdf = Join-Path $PdfRoot "EpochCut_TDSC_Paper.pdf"
Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\main.pdf") -Destination $FinalPdf -Force

$RunId = [Guid]::NewGuid().ToString("N")
$ArtifactStage = Join-Path $ScratchRoot ("release_stage_" + $RunId)
$ArtifactProject = Join-Path $ArtifactStage "EpochCut"
$OverleafStage = Join-Path $ScratchRoot ("overleaf_stage_" + $RunId)
$VerifyStage = Join-Path $ScratchRoot ("verify_stage_" + $RunId)
New-Item -ItemType Directory -Force -Path $ArtifactProject, $OverleafStage, $VerifyStage | Out-Null

$ProjectFiles = @(".gitattributes", ".gitignore", "CITATION.cff", "README.md", "SECURITY.md", "pyproject.toml")
foreach ($File in $ProjectFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $ArtifactProject
}

$ProjectDirs = @(".github", "configs", "docs", "evaluation", "examples", "results", "scripts", "src", "tests")
foreach ($Dir in $ProjectDirs) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Dir) -Destination $ArtifactProject -Recurse
}

$PaperTarget = Join-Path $ArtifactProject "paper"
New-Item -ItemType Directory -Force -Path (Join-Path $PaperTarget "figures") | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\main.tex") -Destination $PaperTarget
Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\references.bib") -Destination $PaperTarget
Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\main.pdf") -Destination $PaperTarget
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
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ("paper\figures\" + $FigureFile)) -Destination (Join-Path $PaperTarget "figures")
}

Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\main.tex") -Destination $OverleafStage
Copy-Item -LiteralPath (Join-Path $ProjectRoot "paper\references.bib") -Destination $OverleafStage
$OverleafFigures = Join-Path $OverleafStage "figures"
New-Item -ItemType Directory -Force -Path $OverleafFigures | Out-Null
foreach ($FigureFile in $FigureFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ("paper\figures\" + $FigureFile)) -Destination $OverleafFigures
}

$ArtifactZip = Join-Path $ReleaseRoot "EpochCut_Reproducibility_Artifact.zip"
$OverleafZip = Join-Path $ReleaseRoot "EpochCut_Overleaf_Source.zip"
Compress-Archive -Path $ArtifactProject -DestinationPath $ArtifactZip -Force
Compress-Archive -Path (Join-Path $OverleafStage "*") -DestinationPath $OverleafZip -Force

Expand-Archive -LiteralPath $ArtifactZip -DestinationPath (Join-Path $VerifyStage "artifact")
Expand-Archive -LiteralPath $OverleafZip -DestinationPath (Join-Path $VerifyStage "overleaf")

$Expected = @(
    (Join-Path $VerifyStage "artifact\EpochCut\paper\main.pdf"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\raw\dynamic_topology_results.csv"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\analysis\confirmatory_analysis.json"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\mcp_confirmatory_v1\analysis\mcp_llm_analysis.json"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\mcp_confirmatory_v1\raw\mcp_llm_trials.csv"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\mcp_confirmatory_v1\raw\mcp_llm_transcripts.jsonl"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\hosted_confirmatory_v3\hosted_mcp_llm_trials.csv"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\hosted_confirmatory_v3\hosted_mcp_llm_transcripts.jsonl"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\hosted_confirmatory_v3\mcp_effect_ledger.jsonl"),
    (Join-Path $VerifyStage "artifact\EpochCut\results\hosted_confirmatory_v3\analysis\hosted_mcp_llm_analysis.json"),
    (Join-Path $VerifyStage "artifact\EpochCut\configs\hosted_mcp_protocol_v3.json"),
    (Join-Path $VerifyStage "artifact\EpochCut\docs\HOSTED_MCP_RESULT.md"),
    (Join-Path $VerifyStage "artifact\EpochCut\evaluation\mcp_dynamic_server.py"),
    (Join-Path $VerifyStage "overleaf\main.tex"),
    (Join-Path $VerifyStage "overleaf\references.bib"),
    (Join-Path $VerifyStage "overleaf\figures\architecture.pdf"),
    (Join-Path $VerifyStage "overleaf\figures\architecture.drawio"),
    (Join-Path $VerifyStage "overleaf\figures\mcp_llm_security.pdf")
)
$Missing = @($Expected | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($Missing.Count -gt 0) {
    throw "Fresh-extract verification failed: $($Missing -join ', ')"
}

$ExtractedOverleaf = Join-Path $VerifyStage "overleaf"
Push-Location $ExtractedOverleaf
try {
    & pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "First extracted-source LaTeX pass failed" }
    & bibtex main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Extracted-source BibTeX pass failed" }
    & pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Second extracted-source LaTeX pass failed" }
    & pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Final extracted-source LaTeX pass failed" }
} finally {
    Pop-Location
}

$ExtractedPdf = Join-Path $ExtractedOverleaf "main.pdf"
if (-not (Test-Path -LiteralPath $ExtractedPdf -PathType Leaf)) {
    throw "Extracted Overleaf source did not produce main.pdf"
}

$SourcePdfHash = (Get-FileHash -LiteralPath (Join-Path $ProjectRoot "paper\main.pdf") -Algorithm SHA256).Hash
$FinalPdfHash = (Get-FileHash -LiteralPath $FinalPdf -Algorithm SHA256).Hash
if ($SourcePdfHash -ne $FinalPdfHash) {
    throw "Final PDF copy does not match the verified manuscript"
}

[ordered]@{
    status = "PASS"
    final_pdf = $FinalPdf
    reproducibility_zip = $ArtifactZip
    overleaf_zip = $OverleafZip
    extracted_files_checked = $Expected.Count
    extracted_source_compiled = $true
    final_pdf_sha256 = $FinalPdfHash.ToLowerInvariant()
} | ConvertTo-Json
