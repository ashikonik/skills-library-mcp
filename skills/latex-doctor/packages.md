# LaTeX Packages Reference

## Essential modern stack

These are the go-to packages for a well-set-up document in 2024+. Prefer these over older alternatives.

| Purpose | Modern package | Replaces / avoids |
|---------|---------------|-------------------|
| Graphics | `graphicx` | `graphics` (fewer options) |
| Colors | `xcolor` | `color` (fewer color models) |
| Tables | `booktabs` + `tabularx` or `tabularray` | `\hline`, `\cline`, vertical rules |
| Units & numbers | `siunitx` | Manual `\mathrm{kg}` |
| Cross-refs | `cleveref` | Manual `Figure~\ref{...}` |
| Hyperlinks | `hyperref` | (load last, with few exceptions) |
| Bibliography | `biblatex` + biber | `natbib` + bibtex (still common but older) |
| Typography | `microtype` | nothing — just use it |
| Code listings | `minted` or `listings` | verbatim hacks |
| Math | `amsmath` + `amssymb` + `mathtools` | bare LaTeX math |
| Fonts (xelatex/lua) | `fontspec` | `inputenc` + `fontenc` (pdflatex path) |
| Fonts (pdflatex) | `\usepackage[T1]{fontenc}` + font package | OT1 encoding (bad hyphenation) |
| PDF metadata | `hyperref` with `pdfauthor`, `pdftitle` | `\pdfinfo` |
| Geometry | `geometry` | Manual `\setlength` for margins |
| Headers/footers | `fancyhdr` or `scrlayer-scrpage` (KOMA) | `\markboth` hacks |
| Subfigures | `subcaption` | `subfigure` (deprecated), `subfig` (older) |
| Enumerations | `enumitem` | Manual `\renewcommand{\labelitemi}` |
| Algorithms | `algorithm2e` or `algpseudocode` | `algorithmic` (older) |

## Package load order

LaTeX is sensitive to package load order. General rules:

1. `\documentclass` first (obviously)
2. Encoding/font packages early (`fontenc`, `inputenc`, `fontspec`)
3. `babel` or `polyglossia` early (language support)
4. Math packages (`amsmath`, `mathtools`)
5. Most other packages in any order
6. `hyperref` near the end (it redefines many internals)
7. `cleveref` after `hyperref` (it patches hyperref's commands)
8. `glossaries` after `hyperref` if using `\glsxtrnewsymbol` etc.

Exceptions exist — some packages document their load order requirements. When in doubt, check the package documentation on CTAN.

## Known package conflicts

### hyperref + almost everything
`hyperref` is the most conflict-prone package because it redefines many LaTeX internals. Load it late. Known issues:
- `hyperref` + `cleveref`: load cleveref AFTER hyperref
- `hyperref` + `algorithm2e`: use `\usepackage[algo2e]{algorithm2e}` or load after hyperref
- `hyperref` + `autonum`: autonum must come after hyperref and amsmath
- `hyperref` in beamer: beamer loads hyperref automatically — don't load it again

### xcolor option clash
Many packages load `xcolor` internally (tikz, tcolorbox, beamer, mdframed). If you need specific xcolor options like `[table]` or `[dvipsnames]`, use:
```latex
\PassOptionsToPackage{table,dvipsnames}{xcolor}
\documentclass{...}
```

### amsmath + wasysym
Both define `\iint`. Load wasysym with `\usepackage[nointegrals]{wasysym}`.

### tikz + externalize + minted
Both need `-shell-escape`. That's fine. But `externalize` may try to externalize minted environments, which breaks. Add `\tikzset{external/optimize=false}` or exclude minted from externalization.

### babel + csquotes + biblatex
For proper localized quotes in bibliographies: load babel first, then csquotes, then biblatex with `\usepackage[autostyle]{csquotes}`.

## Deprecated packages — use these instead

| Don't use | Use instead | Why |
|-----------|-------------|-----|
| `subfigure` | `subcaption` | subfigure was deprecated in 2005 |
| `epsfig` | `graphicx` | epsfig is a compatibility wrapper |
| `times` | `mathptmx` or `newtxtext`+`newtxmath` | `times` doesn't set math fonts |
| `a4wide` | `geometry` | a4wide uses hardcoded margins |
| `t1enc` | `\usepackage[T1]{fontenc}` | t1enc is the old name |
| `fancyheadings` | `fancyhdr` | renamed decades ago |
| `doublespace` | `setspace` | doublespace is ancient |
| `cite` (with biblatex) | biblatex handles sorting | `cite` conflicts with biblatex |

## Useful niche packages

- `todonotes` — Margin notes for drafts (`\todo{Fix this}`)
- `showkeys` — Displays label names in the margin (draft mode)
- `lipsum` / `blindtext` — Placeholder text
- `standalone` — Compile TikZ figures as separate PDFs, then include
- `pdfpages` — Include entire PDF pages (`\includepdf`)
- `pgfplots` — Publication-quality plots from data
- `tcolorbox` — Colored and styled text boxes (theorems, examples, warnings)
- `mhchem` — Chemical formulas (`\ce{H2O}`)
- `circuitikz` — Circuit diagrams built on TikZ
- `forest` — Tree diagrams (linguistic, CS, org charts)
- `glossaries-extra` — Glossaries and acronym lists
- `acro` — Lightweight acronym management
- `xspace` — Smart spacing after custom commands
