# Project visuals

Visuals in this repository explain the implementation. They do not contain
publication figures, measured-result charts or benchmark scorecards.

## Cover

[The cover](assets/epochcut-cover.png) has a
[vector export](assets/epochcut-cover.svg) and a reproducible source:
[`build_project_visuals.py`](../scripts/build_project_visuals.py).
It illustrates a queued request retaining epoch 0 while new admissions use
epoch 1. All labels describe code behaviour; no archived dataset is read.

```bash
python -m pip install -r requirements-visuals.txt
python scripts/build_project_visuals.py
python scripts/verify_project_showcase.py
```

The generated [`visual-manifest.json`](assets/visual-manifest.json) records only
source and export hashes. Keep labels concise and avoid inserting unpublished
numerical results into the cover.

## Editable protocol diagram

The main [Mermaid source](../diagrams/retained-authority.mmd) produces the grouped
[SVG](../diagrams/retained-authority.svg) and
[PNG](../diagrams/retained-authority.png). The
[Excalidraw scene](../diagrams/retained-authority.excalidraw) contains native,
editable shapes and connectors. Open it with **File → Open** at excalidraw.com.

The scene uses an ungrouped layout because the converter does not preserve the
main diagram's visual clusters. Its
[conversion source](../diagrams/retained-authority-editable.mmd) is generated from
the main source by `python scripts/prepare_editable_flow.py`. Labels and policy
branches remain the same; phase arrows expand to explicit entry/exit nodes.

After changing Mermaid, regenerate the grouped exports and converter scene
together. After editing the scene itself, preserve that scene and export from
it rather than overwriting it with another conversion.
