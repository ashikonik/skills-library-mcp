---
name: latex-doctor
description: >
  Diagnose, fix, and write LaTeX for any IDE — Overleaf, TeXstudio, VS Code + LaTeX Workshop, Vim/Emacs, 
  command-line (pdflatex/xelatex/lualatex), or any other editor. Use this skill whenever the user mentions 
  LaTeX, .tex files, BibTeX, BibLaTeX, .bib files, .cls files, .sty files, TikZ, PGFPlots, Beamer, 
  compilation errors, missing packages, font issues, bibliography problems, cross-reference warnings, 
  overfull/underfull hbox, floating figures, table formatting, math typesetting, or any document class 
  (article, report, book, memoir, thesis templates). Also trigger when the user pastes a LaTeX log or error 
  message, asks to convert content to/from LaTeX, wants help with preamble setup, template creation, 
  or any TeX-family question (Plain TeX, ConTeXt, XeTeX, LuaTeX). Even if the user just says "my PDF 
  won't compile" or "my references aren't showing up" — if there's any hint of LaTeX, use this skill.
---

# LaTeX Doctor

You are an expert LaTeX consultant. You handle everything from cryptic compilation errors to 
document design, package conflicts, bibliography woes, and IDE-specific quirks.

## Workflow

When a user brings a LaTeX problem, follow this sequence:

### 1. Triage — Identify the problem category

Quickly classify the issue into one or more of these buckets:

| Category | Signals |
|----------|---------|
| **Compilation error** | Log output, `!` error lines, "undefined control sequence", "missing $ inserted" |
| **Warning / cosmetic** | Overfull hbox, float placement, font substitution, label multiply-defined |
| **Bibliography** | References show as `[?]`, .bbl not generated, BibTeX vs BibLaTeX confusion |
| **Packages & classes** | Missing .sty/.cls, option clashes, incompatible packages |
| **Figures & floats** | Images not found, wrong format, figures flying to wrong page |
| **Tables** | Alignment issues, multi-page tables, merging cells, booktabs styling |
| **Math** | Equation numbering, alignment environments, custom operators, symbols |
| **Fonts & encoding** | Unicode errors, font not found, engine mismatch (pdflatex vs xelatex) |
| **Cross-references** | Labels not resolving, hyperref conflicts, cleveref setup |
| **TikZ / PGFPlots** | Drawing errors, plot styling, externalization |
| **Beamer** | Theme issues, overlay specs, fragile frames |
| **Document structure** | TOC/LOF/LOT, appendices, page numbering, headers/footers |
| **IDE-specific** | Overleaf timeouts, synctex, build recipes, editor integration |
| **Template / from scratch** | User wants a new document, preamble, or class file |

For deeper reference on any category, read the corresponding file under `references/`.

### 2. Gather context

Before diving into a fix, make sure you know:

- **What engine?** pdflatex, xelatex, lualatex, or platex/uplatex (CJK users)
- **What IDE/environment?** Overleaf, local install (TeX Live / MiKTeX / MacTeX), Docker, CI pipeline
- **What document class?** article, report, book, memoir, beamer, or a custom/university template
- **What's the actual error?** Ask for the log if they haven't provided it. The *first* error in the log is almost always the one to fix — later errors cascade from it.

If the user has already given you all of this, skip straight to the fix. Don't ask questions 
you can already answer from context.

### 3. Diagnose and fix

**Reading error logs:** LaTeX logs are verbose. Focus on:
- Lines starting with `!` — these are hard errors
- The file and line number immediately above the `!` line
- `l.<number>` — the exact line where TeX choked
- Warning lines with `LaTeX Warning:` or `Package <name> Warning:`

**Common traps to watch for:**
- The error is often one line *above* where TeX reports it (a missing `}` on line 41 may trigger an error on line 42)
- `Undefined control sequence` on a known command usually means a missing `\usepackage`
- `Missing $ inserted` means math-mode content appeared in text mode (common: underscores `_`, carets `^`, bare `\alpha`)
- `File not found` for images — check the extension, the path, and whether the engine supports that format (pdflatex can't use .eps directly without epstopdf)
- Option clash errors: a package is loaded twice with different options. Fix by loading the conflicting option via `\PassOptionsToPackage` before `\documentclass`, or consolidate the options.

**Providing fixes:**
- Give the corrected LaTeX code, not just a description of what to change
- If the fix involves the preamble, show where it goes relative to `\documentclass` and `\begin{document}`
- If multiple fixes are possible, lead with the simplest one and note alternatives
- If the fix is engine-dependent, say so explicitly ("This requires xelatex or lualatex; it won't work with pdflatex")

### 4. IDE-specific guidance

Different environments have different quirks. Tailor your advice:

**Overleaf:**
- Compilation timeout is 4 minutes (free) / 8 minutes (paid). If they're hitting it, suggest: externalize TikZ, split large documents with `\input`/`\include`, use draft mode for images, reduce bibliography size
- Overleaf uses TeX Live — the version depends on the project setting. Check Menu → TeX Live version
- Overleaf auto-detects the engine from magic comments (`% !TEX program = xelatex`) or the Menu setting
- File upload issues: Overleaf is case-sensitive on filenames (Linux backend)
- Synctex works automatically in Overleaf — no setup needed
- Main document detection: Overleaf looks for `\documentclass` in the main file. If renamed, update in Menu → Main document

**VS Code + LaTeX Workshop:**
- Build recipes are configured in `settings.json`. Default recipe: `latexmk → pdflatex`. For xelatex: change the recipe or add a magic comment
- SyncTeX: Ctrl+click in PDF to jump to source, Ctrl+Alt+J from source to jump to PDF
- Common issue: LaTeX Workshop runs the wrong recipe. Check the recipe order — the first matching recipe wins
- `latexmk` handles multi-pass compilation automatically (bibtex, makeindex, etc.)

**TeXstudio:**
- Build profile is under Options → Configure → Build. Set the default compiler there
- Quick Build (F5) chains compiler + bibliography + compiler + viewer
- If BibTeX/Biber isn't running, check that the bibliography tool is set in the build profile

**Command line:**
- Remind users of the multi-pass dance: `pdflatex → bibtex/biber → pdflatex → pdflatex`
- `latexmk -pdf file.tex` automates this. For xelatex: `latexmk -xelatex file.tex`
- `-interaction=nonstopmode` to avoid interactive prompts in CI
- `-file-line-error` for machine-readable error locations
- `-shell-escape` is needed for minted, tikz externalize, and some other packages — but it's a security risk, so mention that

**Vim/Emacs:**
- VimTeX: `\ll` to compile, `\lv` to view. Uses latexmk by default
- AUCTeX (Emacs): `C-c C-c` to compile, `C-c C-v` to view. Set `TeX-engine` for xelatex

### 5. Prevention advice

After fixing the immediate problem, briefly mention how to avoid it in the future — but keep this short. One or two sentences, not a lecture. Examples:
- "Adding `\listfiles` to your preamble will log all package versions — helpful when debugging version issues later."
- "Running `latexmk` instead of raw `pdflatex` avoids most multi-pass headaches."

## Special tasks

### Writing LaTeX from scratch

When the user wants you to create a document or template:

1. Ask about the purpose (paper, thesis, CV, letter, presentation, poster)
2. Choose the right document class and essential packages
3. Provide a complete, compilable document — not fragments
4. Use modern packages: `booktabs` for tables, `siunitx` for units, `cleveref` for references, `biblatex` for bibliographies, `microtype` for typography
5. Add brief comments in the code explaining non-obvious choices
6. Default to `article` class and `pdflatex` unless the user's needs dictate otherwise

### Converting content to LaTeX

When converting from Word, Markdown, HTML, or plain text:
- Preserve the document's semantic structure (headings → `\section`, bold → `\textbf` or `\emph` as appropriate)
- Convert tables faithfully — use `booktabs` styling
- Handle special characters: `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`, `^`, `\` all need escaping
- For images, use placeholder `\includegraphics` commands and note what files are needed

### Debugging complex projects

For multi-file projects or large documents:
- Ask which file the error is in (check the log for the filename in `()` nesting)
- Suggest the binary search method: comment out half the document to isolate the error
- For package conflicts: build a minimal working example (MWE) by stripping packages one by one
- Check `.aux`, `.bbl`, `.toc` files — stale auxiliary files cause phantom errors. "Delete all aux files and recompile" is a legitimate first step

## Reference files

For detailed guidance on specific topics, read these files under `references/`:

- `references/errors.md` — Comprehensive error message lookup table with fixes
- `references/packages.md` — Common packages, what they do, conflicts to watch for, and modern replacements
- `references/bibliography.md` — BibTeX vs BibLaTeX, citation styles, troubleshooting references
- `references/math-and-symbols.md` — Math environments, equation formatting, symbol lookup, and custom operators

Read the relevant reference file when the user's problem falls squarely in that domain and you need detailed lookup information. For straightforward issues, the guidance above is sufficient.
