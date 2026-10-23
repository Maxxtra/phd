# A0 poster

* `poster.pdf` — print-ready A0 portrait (841 × 1189 mm), fully vector: every figure, diagram and the QR
  code are vector; all fonts embedded (checked with `pdfimages -list` and `pdffonts`).
* `poster.tex` — editable source. Architecture and roadmap diagrams are TikZ; result figures are the
  vector PDFs in `../figures/`; **every number** comes from `generated/results.tex`, written by
  `seas report` from `results/`. Nothing is typed by hand.

## Design

Reproduces the SciFig **A0 Portrait — Classic** template specification in the **Navy** scheme
(scifig.ai/scientific-poster-templates/a0): three columns in a 1.2 : 1.6 : 1.2 ratio, title 85 pt,
author line 38 pt, section headings 44 pt, body 26 pt, captions 23 pt (references 20 pt), Navy
`#1B365D` title band and headings on white, body text `#1A1A1A`, Liberation Sans (Arial-metric).
The original `.pptx` could not be downloaded in the build environment, so the template's grid, type
scale and colours were rebuilt in LaTeX; this guarantees a vector PDF (PowerPoint export often
rasterises imported figures).

Classic was chosen over Spotlight: Spotlight is built around one dominant headline result, and the
honest Stage-1 headline (small energy effect, H2 not supported) does not warrant that framing. A
full-width key-findings strip gives the 60-second reading path; implemented work is tagged
**IMPLEMENTED** (solid, green) and future objectives **PLANNED** (dashed, grey).

## Build

```bash
seas report            # refresh generated/results.tex from results/
xelatex poster.tex && xelatex poster.tex   # two passes (header and column placement use overlays)
pdfinfo poster.pdf | grep "Page size"      # 2383.94 x 3370.39 pts (A0)
pdffonts poster.pdf                        # all 'emb' = yes
pdfimages -list poster.pdf                 # no entries: fully vector
```

Columns are stretched to a fixed height; an `Overfull \vbox` warning in `build.log` means a column
is too long. `poster_preview.png` is rendered with `pdftoppm -png -singlefile -scale-to-x 1200 -scale-to-y -1 poster.pdf poster_preview`.

## Before printing

* Add the UNSTPB and PRECIS logos (vector preferred) in the header band, left of the QR code.
* Print at 100 % on matte stock; order a small test print first.
