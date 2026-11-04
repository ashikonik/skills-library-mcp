# LaTeX Error Reference

Quick-lookup table for common errors. Organized by the error text you'll see in the log.

## Hard errors (lines starting with `!`)

### `! Undefined control sequence`
**Cause:** A command TeX doesn't recognize.
**Common triggers and fixes:**
- Misspelled command → check spelling (`\textbt` → `\textbf`)
- Missing package → identify which package provides the command and add `\usepackage{...}`
- Wrong engine → some commands only exist in xelatex/lualatex (e.g., `\setmainfont` needs `fontspec`, which requires xelatex or lualatex)
- Using a command outside its scope → e.g., `\cref` without `\usepackage{cleveref}`

**Frequent package lookups:**
| Command | Package |
|---------|---------|
| `\includegraphics` | graphicx |
| `\url`, `\href` | hyperref (or url) |
| `\toprule`, `\midrule`, `\bottomrule` | booktabs |
| `\SI`, `\si`, `\num` | siunitx |
| `\cref`, `\Cref` | cleveref |
| `\tikz`, `\begin{tikzpicture}` | tikz |
| `\lstlisting`, `\lstinline` | listings |
| `\mintinline`, `\begin{minted}` | minted (+ `-shell-escape`) |
| `\setmainfont` | fontspec (xelatex/lualatex only) |
| `\usecolortheme`, `\usetheme` | beamer class only |

### `! Missing $ inserted`
**Cause:** Math-mode content in text mode.
**Common triggers:**
- Bare `_` or `^` in text → escape as `\_` or `\^{}`, or use `\textsubscript{}`/`\textsuperscript{}`
- Greek letters outside math → wrap in `$...$`
- Copy-pasted code with underscores → use `\verb|...|` or the `listings`/`minted` package

### `! Missing } inserted` / `! Missing { inserted`
**Cause:** Unmatched braces. Often the real problem is one or more lines above the reported line.
**Debugging:** Count braces in the region around the error. Editors with brace-matching highlighting help.

### `! Extra alignment tab character &`
**Cause:** More `&` in a row than the table/align has columns.
**Fix:** Check your column spec. `{lll}` means 3 columns, so each row gets at most 2 `&`s.

### `! Misplaced alignment tab character &`
**Cause:** `&` used outside a tabular/align/matrix environment. Escape it as `\&` if it's literal text.

### `! LaTeX Error: File 'xxx.sty' not found`
**Cause:** Package not installed.
**Fixes:**
- Overleaf: The package genuinely doesn't exist or is misspelled. Check CTAN.
- TeX Live: `tlmgr install <package-name>` (may need `sudo`)
- MiKTeX: It should auto-install. If it doesn't, open the MiKTeX Console and install manually.

### `! LaTeX Error: Option clash for package xxx`
**Cause:** Package loaded twice with different options (often one explicit, one implicit via another package).
**Fix:** Use `\PassOptionsToPackage{options}{package}` before `\documentclass`, or remove the redundant `\usepackage` and consolidate options.

**Common culprit:** `xcolor` — loaded by many packages (tikz, tcolorbox, beamer). If you need `\usepackage[table]{xcolor}`, put `\PassOptionsToPackage{table}{xcolor}` before documentclass.

### `! LaTeX Error: Environment xxx undefined`
**Cause:** Using `\begin{xxx}` for an environment that doesn't exist.
**Common:** `\begin{lstlisting}` without `listings` package, `\begin{align}` without `amsmath`.

### `! Package inputenc Error: Unicode character ... not set up for use with LaTeX`
**Cause:** Non-ASCII character with pdflatex that `inputenc` can't handle.
**Fixes:**
- Add `\usepackage[utf8]{inputenc}` (default in modern TeX Live, but older templates may lack it)
- Switch to xelatex or lualatex, which handle Unicode natively
- Replace the offending character with a LaTeX command (e.g., `é` → `\'{e}`)

### `! Dimension too large`
**Cause:** A length calculation overflowed. Common with TikZ, very large tables, or extreme scaling.
**Fix:** Reduce the scale factor, break the content into smaller pieces, or use a different approach.

### `! TeX capacity exceeded`
**Cause:** Infinite loop or genuinely massive document hitting memory limits.
**Common triggers:** Recursive macro definitions, TikZ `\foreach` with too many iterations, extremely long tables.
**Fix:** Find the loop. If legitimate, increase memory: in `texmf.cnf` set `main_memory = 8000000` (or use lualatex, which has dynamic memory).

### `! Emergency stop`
**Cause:** TeX gave up after too many errors, or the file ended unexpectedly.
**Fix:** Fix the first error in the log — this one is always a downstream consequence.

## Warnings

### `LaTeX Warning: Reference 'xxx' on page N undefined`
**Cause:** A `\ref` or `\eqref` points to a label that doesn't exist.
**Fix:** Check the label name for typos. Compile twice (labels resolve on the second pass). If using `\label` inside a float, place it after `\caption`.

### `LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right`
**Cause:** Normal — just compile again. Labels update across passes.

### `LaTeX Warning: Citation 'xxx' on page N undefined`
**Cause:** Bibliography entry not found.
**Fixes:**
- Check the cite key matches exactly (case-sensitive) between `.tex` and `.bib`
- Make sure you ran BibTeX/Biber after the first compilation
- Check the .bib file has no syntax errors (mismatched braces are common)
- If using BibLaTeX, make sure you're running Biber, not BibTeX (and vice versa)

### `Overfull \hbox (Xpt too wide)`
**Cause:** Content extends into the margin.
**Fixes:**
- For text: add `\sloppy` (crude) or adjust `\tolerance` and `\emergencystretch`
- For URLs: `\usepackage[hyphens]{url}` or `\sloppy` in the relevant scope
- For tables: reduce column widths, use `tabularx`, or switch to `\resizebox`
- For images: check the width isn't exceeding `\textwidth`
- `\hfuzz=2pt` to suppress warnings under 2pt (cosmetic fix)

### `Underfull \hbox (badness XXXXX)`
**Cause:** TeX stretched whitespace too much trying to justify a line.
**Fix:** Usually cosmetic. Rephrase the paragraph, or use `\raggedright` for that section.

### `Package hyperref Warning: Token not allowed in a PDF string`
**Cause:** Math or formatting commands in a section title that hyperref tries to use as a PDF bookmark.
**Fix:** `\texorpdfstring{$E=mc^2$}{E=mc2}` — first arg for the document, second for the bookmark.

### `Float too large for page` / floats drifting away
**Cause:** LaTeX's float placement algorithm can't find a good spot.
**Fixes:**
- Relax placement: `\begin{figure}[htbp]` instead of `[h]`
- `\usepackage[section]{placeins}` to keep floats within their section
- `\clearpage` to force all pending floats out
- As a last resort: `[H]` from the `float` package (forces exact placement, may leave whitespace)
