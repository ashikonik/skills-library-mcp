# Bibliography Reference

## BibTeX vs BibLaTeX — which is the user using?

This is the single most common source of bibliography confusion. The two systems are **not interchangeable**.

| | BibTeX (+ natbib) | BibLaTeX (+ biber) |
|--|---|---|
| Backend | `bibtex` | `biber` |
| Style selection | `\bibliographystyle{plain}` | `\usepackage[style=authoryear]{biblatex}` |
| Citation commands | `\cite`, `\citep`, `\citet` (with natbib) | `\cite`, `\parencite`, `\textcite`, `\autocite` |
| Bibliography command | `\bibliography{refs}` | `\printbibliography` |
| .bib file declaration | `\bibliography{refs}` (at end) | `\addbibresource{refs.bib}` (in preamble, full filename with .bib) |
| Multiple bibliographies | Difficult | Built-in (`\printbibliography[keyword=...]`) |
| Unicode support | Poor | Native |
| Custom styles | .bst files (postfix language) | LaTeX macros (much easier to customize) |

**Detection:** Look at the preamble:
- `\usepackage{biblatex}` or `\usepackage[...]{biblatex}` → BibLaTeX system, must use **biber**
- `\bibliographystyle{...}` or `\usepackage{natbib}` → BibTeX system, must use **bibtex**

**The #1 mistake:** Using bibtex as the backend when biblatex is loaded (or vice versa). Overleaf usually auto-detects, but local setups often get this wrong.

## Compilation sequence

### BibTeX workflow
```
pdflatex main.tex    → generates .aux with \citation{} entries
bibtex main          → reads .aux + .bib, generates .bbl
pdflatex main.tex    → incorporates .bbl
pdflatex main.tex    → resolves cross-references to citations
```

### BibLaTeX + Biber workflow
```
pdflatex main.tex    → generates .bcf (XML request file)
biber main           → reads .bcf + .bib, generates .bbl
pdflatex main.tex    → incorporates .bbl
pdflatex main.tex    → resolves cross-references
```

`latexmk` automates both workflows. For biber: `latexmk -pdf -bibtex-cond` or just `latexmk -pdf` (it detects biber automatically in recent versions).

## Troubleshooting citations showing as [?]

Step-by-step checklist:

1. **Did you run bibtex/biber?** Check by looking for a .bbl file. If it doesn't exist, the backend hasn't run.
2. **Is the cite key correct?** Keys are case-sensitive. `\cite{Smith2020}` ≠ `\cite{smith2020}`.
3. **Is the .bib file found?** 
   - BibTeX: `\bibliography{refs}` (no .bib extension)
   - BibLaTeX: `\addbibresource{refs.bib}` (with .bib extension)
4. **Is the .bib entry syntactically valid?** Common errors:
   - Missing comma between fields
   - Unmatched braces in title or author
   - Using `=` instead of `= {` or `= "` 
5. **Is the entry type valid?** `@article`, `@book`, `@inproceedings` etc. Typos like `@artcle` silently fail.
6. **Backend mismatch?** If using biblatex, run biber not bibtex. Check IDE settings.
7. **Stale auxiliary files?** Delete `.aux`, `.bbl`, `.bcf`, `.blg`, and recompile from scratch.
8. **Overleaf-specific:** Check Menu → Bibliography tool is set to Biber (if using biblatex) or BibTeX.

## Common .bib file syntax errors

```bibtex
% WRONG — missing comma after year
@article{key,
  author = {Smith, John},
  title = {A Paper},
  year = {2020}
  journal = {Nature}
}

% RIGHT
@article{key,
  author = {Smith, John},
  title = {A Paper},
  year = {2020},
  journal = {Nature}
}
```

```bibtex
% WRONG — unbalanced braces in title
@article{key,
  title = {A {Study of {Complex} Systems},
}

% RIGHT
@article{key,
  title = {A {Study} of {Complex} Systems},
}
```

## Citation styles cheat sheet

### BibLaTeX styles (use with `style=` option)
- `authoryear` — (Smith, 2020) / Smith (2020)
- `authoryear-comp` — compressed: (Smith, 2020a,b)
- `numeric` — [1], [2], [3]
- `numeric-comp` — [1–3] compressed ranges
- `alphabetic` — [Smi20]
- `apa` — APA 7th edition (needs `biblatex-apa`)
- `ieee` — IEEE style (needs `biblatex-ieee`)
- `chicago-authordate` — Chicago (needs `biblatex-chicago`)
- `chem-acs` — ACS chemistry style (needs `biblatex-chem`)

### Natbib + BibTeX styles
- `plain` — [1], alphabetical order
- `unsrt` — [1], citation order
- `abbrv` — [1], abbreviated names
- `apalike` — (Smith, 2020) with APA-ish formatting
- `IEEEtran` — IEEE format

## Multiple bibliographies / per-chapter

BibLaTeX:
```latex
% In preamble
\usepackage[backend=biber, refsection=chapter]{biblatex}
\addbibresource{refs.bib}

% At end of each chapter
\printbibliography[heading=subbibliography]
```

## Encoding issues in .bib files

- BibTeX: Avoid Unicode. Use `{\"o}` for ö, `{\'{e}}` for é, etc.
- Biber: Unicode works natively. Save .bib as UTF-8.
- Mixed: If you have an old .bib with LaTeX-encoded characters, biber handles both fine. BibTeX chokes on raw Unicode.
