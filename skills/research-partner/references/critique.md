# Constructive Critique

The goal is to make the work stronger, which requires being harder on it than a casual reader would be and fairer to it than a hostile reviewer would be. Both halves matter.

## Steelman before criticizing

Open by restating the paper's argument in a form its authors would endorse - the problem, why it is hard, what the contribution claims to be, and what evidence supports it. If you cannot do this convincingly, you have not understood the paper well enough to critique it, and should read it again rather than proceeding.

This is not politeness. Most bad reviews attack a version of the paper that was never written, and the restatement is what catches that.

## Separate the layers

Keep these distinct, since they call for completely different responses:

- **Claim** - is the thing being asserted true, and is it what the authors think they asserted?
- **Evidence** - does the experiment or argument actually support the claim, or a narrower one?
- **Framing** - is the contribution positioned correctly relative to prior work?
- **Presentation** - is it clear? This is real but lowest-stakes; do not let it dominate.

A paper with a good claim and weak evidence needs more experiments. A paper with good evidence and an overreaching claim needs one sentence changed. Conflating them wastes the authors' time.

## What to examine

Adapt to the field; not all apply everywhere.

- **Construct validity** - does the measurement measure the thing the paper says it does? Where a proxy stands in for the real quantity of interest, is the substitution defended?
- **Internal validity** - could something other than the proposed mechanism explain the result? Confounds, leakage, selection effects, experimenter degrees of freedom.
- **Baselines and fairness** - are comparisons tuned equally? An undertuned baseline is the most common way a real effect gets manufactured. Check whether the baseline is the actual state of the art or a convenient older version.
- **Statistical and inferential support** - variance across runs or subjects, sample size, multiple comparisons, whether the headline difference exceeds the noise, whether "no difference" is being read as evidence of equivalence.
- **Generalization** - what population, distribution, or regime does the evidence cover, and where does the paper's language quietly exceed it?
- **Ablations** - is the contribution isolated, or bundled with changes that could be doing the work?
- **Reproducibility** - is there enough detail to rebuild it? Code, data, hyperparameters, seeds, preprocessing.
- **Novelty and prior art** - is the closest prior work cited and honestly compared? Being second is fine; being second without acknowledging it is not.
- **Limitations and ethics** - are the stated limitations the real ones, or the safe ones?

## Grade severity

Untriaged criticism is unusable. Tag each point:

- **Fatal** - the central claim does not survive. Say plainly what would have to change.
- **Major** - the claim survives in weakened or narrowed form; needs new evidence or a scoped-back statement.
- **Minor** - fixable with available material.
- **Taste** - you would have done it differently. Label it as such and let the authors dismiss it without guilt.

Distinguish **"this is wrong"** from **"this has not convinced me"**. The second is a legitimate and common review outcome, and dressing it up as the first is what makes reviews feel unfair.

## Every criticism carries a remedy

For each point, state what would resolve it: the experiment to run, the claim to narrow, the citation to add, the analysis to include. If no remedy exists within the scope of this paper, say that too - it tells the authors to reframe rather than to keep patching.

## Multi-stance application

Run the standing lenses over the paper and note where they disagree, since that disagreement is usually the most useful thing you can tell an author. Work that is methodologically shaky but practically valuable, or theoretically elegant and practically dead on arrival, should be described that way rather than averaged into a single verdict.

Where the paper sits inside a field-level dispute, name the dispute. A methods objection is often a disciplinary commitment in disguise, and the authors deserve to know which they are facing.

## When the paper is the user's own

Adjust delivery, not standards. Say what a hostile reviewer would attack first and how to preempt it in the paper itself, distinguish problems that need new experiments from those that need better writing, and note where the writing undersells a real contribution - underclaiming is a real failure too. If the work has a fatal problem, say so early and directly; discovering it after submission costs far more.

## Output structure

```
# Critique of <paper>
## What the paper argues
   Steelman restatement
## Assessment
   Two or three sentences: what holds, what does not, overall
## Fatal
## Major
## Minor
## Taste
   Each point: what the problem is, why it matters, what would fix it
## Where the lenses disagree
## What is genuinely good here
```

Do not omit the last section. A critique that lists only problems gives no signal about what to preserve during revision.
