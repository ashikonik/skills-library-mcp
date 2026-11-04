# Math & Symbols Reference

## Math environments — when to use what

| Environment | Package | Numbered? | Use for |
|-------------|---------|-----------|---------|
| `$ ... $` | base | No | Inline math |
| `\( ... \)` | base | No | Inline math (preferred by some style guides) |
| `\[ ... \]` | base | No | Display math (single, unnumbered) |
| `equation` | base | Yes | Single numbered equation |
| `equation*` | amsmath | No | Single unnumbered display equation |
| `align` | amsmath | Yes (each line) | Multiple aligned equations |
| `align*` | amsmath | No | Multiple aligned equations, unnumbered |
| `gather` | amsmath | Yes (each line) | Multiple centered equations (no alignment) |
| `gather*` | amsmath | No | Same, unnumbered |
| `multline` | amsmath | Yes | Single long equation split across lines |
| `split` | amsmath | Parent's | Sub-environment inside equation for alignment |
| `cases` | amsmath | Parent's | Piecewise functions |
| `aligned` | amsmath | Parent's | Like align, but as a sub-environment |
| `matrix`, `pmatrix`, etc. | amsmath | — | Matrices with various delimiters |

**Never use `$$ ... $$`** — it's Plain TeX, not LaTeX, and causes spacing bugs. Use `\[ ... \]` or `equation*`.

**Never use `eqnarray`** — it has known spacing bugs. Use `align` from amsmath instead.

## Alignment in multi-line equations

```latex
\begin{align}
  f(x) &= ax^2 + bx + c \\        % align on =
       &= a(x - r_1)(x - r_2)     % continuation aligned
\end{align}
```

For a single numbered equation that needs alignment:
```latex
\begin{equation}
\begin{split}
  f(x) &= ax^2 + bx + c \\
       &= a(x - r_1)(x - r_2)
\end{split}
\end{equation}
```

## Numbering control

- Number only some lines: use `align` with `\notag` or `\nonumber` on lines you don't want numbered
- Reference a specific equation: `\label{eq:quadratic}` right after the `\\` or before `\end`
- Sub-numbering (3a, 3b): `\usepackage{amsmath}` + `subequations` environment
- Custom tags: `\tag{$\star$}` replaces the number on that equation

```latex
\begin{subequations}\label{eq:maxwell}
\begin{align}
  \nabla \cdot \mathbf{E} &= \frac{\rho}{\epsilon_0} \label{eq:gauss} \\
  \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \epsilon_0 \frac{\partial \mathbf{E}}{\partial t} \label{eq:ampere}
\end{align}
\end{subequations}
```

## Spacing in math mode

| Command | Width | Use |
|---------|-------|-----|
| `\,` | thin space (3/18 em) | Before `dx` in integrals: `\int f(x)\,dx` |
| `\:` or `\>` | medium space (4/18 em) | Between related terms |
| `\;` | thick space (5/18 em) | Before conditions: `x > 0 \; \forall x` |
| `\!` | negative thin space | Tighten double integrals: `\iint\!\!\iint` |
| `\quad` | 1 em | Separator in display math |
| `\qquad` | 2 em | Larger separator |
| `~` | non-breaking space | In text near math |

## Custom operators

Don't write `sin`, `log`, `max` as italic variables — use `\sin`, `\log`, `\max`.

For operators not predefined:
```latex
% In preamble
\DeclareMathOperator{\argmax}{arg\,max}
\DeclareMathOperator{\tr}{tr}
\DeclareMathOperator*{\argmin}{arg\,min}  % * puts limits below in display

% Usage
\argmax_{x \in S} f(x)
```

## Common symbol lookup

### Greek letters
Lower: `\alpha \beta \gamma \delta \epsilon \zeta \eta \theta \iota \kappa \lambda \mu \nu \xi \pi \rho \sigma \tau \upsilon \phi \chi \psi \omega`

Upper: `\Gamma \Delta \Theta \Lambda \Xi \Pi \Sigma \Upsilon \Phi \Psi \Omega`

Variants: `\varepsilon \vartheta \varpi \varrho \varsigma \varphi`

### Relations
- `\leq \geq \neq \approx \equiv \sim \simeq \cong \propto`
- `\ll \gg \prec \succ \preceq \succeq`
- `\in \notin \subset \supset \subseteq \supseteq`

### Arrows
- `\rightarrow \leftarrow \leftrightarrow`
- `\Rightarrow \Leftarrow \Leftrightarrow`
- `\longrightarrow \longmapsto`
- `\xrightarrow{text}` (extensible, from amsmath)
- `\hookrightarrow \twoheadrightarrow` (injections, surjections)

### Miscellaneous
- `\partial \nabla \infty \emptyset \forall \exists`
- `\cdot \times \otimes \oplus \circ \bullet`
- `\ldots \cdots \vdots \ddots` (dots)
- `\hat{a} \bar{a} \tilde{a} \vec{a} \dot{a} \ddot{a}` (accents)

### Delimiters
Auto-sizing: `\left( ... \right)`, `\left[ ... \right]`, `\left\{ ... \right\}`
Manual sizing: `\big( \Big( \bigg( \Bigg(`
Unpaired: use `\left.` or `\right.` as invisible delimiter

**Tip:** `\left`/`\right` can produce ugly spacing. For fine control, use `\mleft`/`\mright` from the `mleftright` package, or manual `\bigl`/`\bigr`.

## Theorem-like environments

```latex
\usepackage{amsthm}

% In preamble
\newtheorem{theorem}{Theorem}[section]     % numbered within section
\newtheorem{lemma}[theorem]{Lemma}          % shares counter with theorem
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem*{remark}{Remark}                % unnumbered

\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}

\theoremstyle{remark}
\newtheorem*{example}{Example}
```

For styled theorem boxes, use `tcolorbox` with `\newtcbtheorem` or `mdframed`.

## Bold and italic in math

| Want | Command | Package |
|------|---------|---------|
| Bold italic (vectors) | `\bm{v}` | bm |
| Bold upright (matrices) | `\mathbf{A}` | base |
| Calligraphic | `\mathcal{F}` | base |
| Blackboard bold | `\mathbb{R}` | amssymb |
| Fraktur | `\mathfrak{g}` | amssymb |
| Script | `\mathscr{L}` | mathrsfs |
| Sans-serif | `\mathsf{T}` | base |
| Typewriter | `\mathtt{code}` | base |

## Fractions and binomials

- `\frac{a}{b}` — display-size fraction
- `\dfrac{a}{b}` — force display size even inline
- `\tfrac{a}{b}` — force text size even in display
- `\cfrac{a}{b}` — continued fraction (from amsmath)
- `\binom{n}{k}` — binomial coefficient
