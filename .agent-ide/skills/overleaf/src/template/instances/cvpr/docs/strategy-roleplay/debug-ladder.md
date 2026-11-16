# The discipline's debugging ladder (the prescription for vision / optimisation projects)

> This left the shared `03-executor.md` because **it names quantities of one discipline** (probe layers, spatial autocorrelation, low-frequency share, degrees-of-freedom audit); it does not hold in another venue, so it belongs to an instance, not to the layer. The layer's interface is in `03-executor.md`; read both.
> The thresholds and quantity names here hold only for vision / optimisation carriers; change discipline and the whole file is replaced — do not edit the layer documents.

### Experiment debugging: probe layers, cost, and "the ruler breaks first"

This section governs "how to kill a hypothesis with the least time". The difference from §10: §10 governs **writing** the debugging process, this section governs **doing** the investigation.

### 1. Layer the probes by cost, and exclude at the cheapest layer first

**The table is ordered by what a probe costs, not by what it is worth**: start at the cheapest layer that can still answer, because a cheap probe that kills the hypothesis saves the expensive one.

| Layer | Means | Order of magnitude | Answers |
|---|---|---|---|
| L0 | read the code, check implementation facts | zero | **is this even possible** (does the output carry this quantity) |
| L1 | one input + one forward pass | seconds | how the criterion reacts to **one** input |
| L2 | render-level comparison, no training | seconds to tens of seconds | the effect of geometry, sampling, background, initialisation |
| L3 | short training (10 steps) | tens of seconds to a minute | optimisation dynamics |
| L4 | full training (100 steps) + evaluation | minutes | end to end |

The rule: **what L0 can answer, do not take to L1; what L2 can answer, do not take to L4.**

Why: training mixes variables together — each one's effect is buried under optimisation drift and per-step sampling noise, and a reading inside the noise cannot be judged; and it costs one or two orders of magnitude more.

**L0 is skipped most and saves most.** Example: to add N·L shading to a render, first read whether the renderer outputs anything but RGB; then check whether a single-shell normals are already co-directional — the two together show the hypothesis should die at the design stage, and the machine never boots.

### 1.5. Explorations always run 100 steps first

For parameter changes and direction probes, a single run is **≤100 steps** and then a figure. No signal within 100 steps means change the hypothesis; do not raise the steps to 300 or 1000 and "wait for it to converge".

**Why:** more steps only enlarge a wrong direction while burning time and money linearly. The same pipeline has already run 300, 500 and 1000 and produced the same blob of noise — the step count was never the variable.

**How to apply:** 100 steps → open the figure → ask "did the figure's character change" (does a non-noise low-frequency block appear), not "what did the loss do". Unchanged, change the hypothesis; changed, go to 300; at 300 it is still growing without changing character, and only then 1000 is allowed. Before a long run, report 「steps × seconds per step」; over 3 minutes needs a written reason.

### 1.6. Magnitude measures cannot judge structure; record spatial quantities

A log holding only loss, std, cos and gradient norm holds "how much it changed" and nothing about "structure or noise". Three quantities must be recorded together:

1. **spatial autocorrelation**: `(x[...,:,:-1]*x[...,:,1:]).sum()/(x*x).sum()` (right neighbour), the same for the lower neighbour;
2. **low-frequency energy share**: the share of energy inside the central 25% radius of the spectrum, **watched against the step count**;
3. **adjacent-sign agreement of the cumulative update**: in the first-to-last snapshot difference `Δz`, the share of adjacent cells with the same sign.

**Criterion**: autocorrelation ≤ 0, or sign agreement ≈ 0.5 → judge "no structure learned" on the spot, change the hypothesis, look at no figure, add no steps. Conversely, autocorrelation > 0.5 while the product still looks bad → the amplitude or the frequency band is being cut, not a failure to build structure; the two have completely different fixes.

**Why:** amplitude-type signals all look normal when **no structure is learned at all** — the loss falls, std is stable, cos sits at 0.3–0.8. Several rounds judged on those alone will each conclude "it changed, just a bit short". Computing afterwards showed the cumulative update's spatial autocorrelation at 0.03 and sign agreement at 0.499 — the update is white noise; no loss curve ever yields that conclusion.

### 1.6.5. Read the shape of the distance curve, not its first point

**Single-point** metrics such as adjacent-pixel correlation and single-step difference magnitude give the same high score on real structure and on regular periodic artefacts — stripes are correlated everywhere. Separating the two requires the **whole distance curve** (lag = 2, 4, 8, 12, 16, 24, 32 …) and a look at its shape:

| Shape | Reading |
|---|---|
| falls to 0 within lag 2 and hugs 0 | no structure |
| periodic rebound midway (positive jump > 0.1 against the previous point) | regular artefact (grid, stripe, checkerboard) |
| monotone decay, still high at long lag | real structure |

Implementation costs a few more lags, which is negligible; skipping this step costs you an artefact reported as a result. An artefact's period usually equals a grid spacing exactly (render resolution / feature-map size), so converting the rebound's lag into pixels matches it to that grid — the hardest evidence for calling it an artefact.

### 1.7. When an upper-layer signal does not move, add probes downward, do not swap hyperparameters

With the symptom (loss not falling, product unchanged) stuck for two rounds, the correct action is **to keep measuring one layer down** and find which layer starts degrading: product → parameter update → single-step gradient → gradient spectrum → model input.

**The anti-pattern**: with the symptom unchanged, change lr, steps, weights, sampling range — all parameters at the same layer, while the degradation sits a layer below. Every changed parameter yields a "there was a change" reading, so you circle at the upper layer forever.

### 2. Cost written as a product, the first number being minutes

**Estimate before asking for the machine**: the product below turns a run into minutes, and a proposal without a minute count has not been estimated.

```
minimum cost = groups × steps × forwards per step × cost per forward + one-off overhead (boot, install, pull weights, upload)
```

Three rules:

- **"steps" and "compute" are not the same thing.** Turning 100 steps into 200 forwards with gradient accumulation or extra forwards pays double for a nominal 100 steps. "Keep it to 100 steps" refers to the bill.
- **One boot sweeps one variable.** Three hyperparameter settings run serially save two boots and two loads over three separate boots.
- **A proposal must carry a minute count**, and it must be the minimum; if you cannot compute it, compute it first.

### 3. When every arm of the comparison "fails to improve", check the ruler first

Six readings in one comparison table all static: suspect the measurement, not six hypotheses being refuted at once.

The order: does the sampling window cross a contour (a sharp edge is broadband and swamps the real signal) → does the frequency band cover the real period → is it diluted by a constant region (background, flat colour).

**The band must come from a reading, not from common sense.** The correct order is to measure the main-peak period with an FFT first, then set the band to it. Set the band by impression and what you measure is the window's own spurious peak.

### 4. Every probe must have its "how it dies" written first

Two lines before running:

```
reading A → the hypothesis holds
reading B → the hypothesis dies
```

A probe with no B should not run — it only produces a figure that can be explained any way you like.

### 5. Variance before difference

Comparing two groups at N=1 holds only when "the spread of repeats at one configuration" is far smaller than "the between-group difference".

Run one configuration N times first (5–10) and measure the median pairwise correlation:

| Median | Reading | Next step |
|---|---|---|
| > 0.9 | a single run can decide | one run per group is enough |
| 0.7–0.9 | the direction is discernible | 3 runs per group, take the median |
| < 0.7 | every single-run comparison is void | earlier A/B conclusions must be rerun |

### 6. Noise sources are measured separately

Repeat twice at the same seed and once at a different seed, separating "initialisation difference" from "per-step sampling noise". Mixed together, the effect of a configuration change cannot be attributed.

### 7. When you change the probe, side effects contaminate the criterion

Extra operations inside a probe (overlaid texture, added lighting, changed background) must be confined to the target region, with a hard mask, not a soft edge.

Criterion: **after the change, look first at "did anywhere that should not change change"** — if it did, that is contamination and this set of readings is void.

### 8. A refuted hypothesis keeps its readings

A negative result is a conclusion too; the standard form has four parts:

```
hypothesis  one sentence
reading     which quantity, how much, compared with what
criterion   how much would count as holding
conclusion  holds / refuted, and which candidate remains after the refutation
```

Leave no numbers and the next round repeats the same probe — the commonest repeated cost in debugging.

### 9. The remaining candidates must be countable

After each step, report "how many candidates remain" and give each one's means of discrimination. A candidate count that does not fall means the round advanced nothing and only consumed machine time.

### 10. Readings cannot replace the read

A spectral or statistical quantity answers "is there" and not "what does it look like".

An FFT reports only the strongest component. A broadband texture (maze, knit, fleece, fluff) is one broad patch in the frequency domain; compressed into one oblique line, the report says "regular oblique stripes" — while the actual frame is covered in loops. The two imply completely different next steps: the former can be notched out, the latter cannot.

The rule: **whenever the judgement is about form, the figure and one number must be given together.** A number alone conveys nothing, because the other side cannot decide from it.

The user's words (translated): "none of these formulas gives me the read of what it did".

### 11. Degrees-of-freedom audit: count which parameters are actually moving

Any judgement that "training is not working" starts with a grep-level audit, not with suspecting the algorithm.

| Degree of freedom | Check | Consequence of freezing it |
|---|---|---|
| position xyz | is there `requires_grad` | the surface stays the initial shape: no folds, no shading, no thickness |
| density (densify/prune) | is it implemented | too few points; once position is released, gaps appear and edges crumble into fringes |
| scaling | `requires_grad` | hard edges, no soft falloff |
| rotation | `requires_grad` | cannot lie on a curved surface |
| colour sh | `requires_grad` | no colour |
| opacity | `requires_grad` | surplus points cannot be culled |

Criterion: **if only colour is moving, every "structural" gradient has nowhere to go and is forced into colour — and the result is a surface covered in patterns.**

This is a characteristic failure mode. Seeing "flat fill + high-frequency texture everywhere + a static contour", the first reflex should be the degrees of freedom, not SD.

One hard ordering constraint: **densify must come before releasing position.** With a single-layer point cloud for support, position moves and gaps appear; add density first, and displacement becomes relief instead of fringes.

There is no sweet spot where "tuning lr grows the folds just right" — what is missing is density, not step size. Adjusting lr repeatedly yields only two outcomes: no reaction, or falling apart.

### 12. When a problem is found, "accept it" may not be a candidate

The user's words (translated): "if it is abnormal, try to fix it — why talk about accepting it?"

- The candidate list holds fixes only. Listing "accept the current state", "work around it" or "do something else first" as candidates hands the work back to the other side.
- The only moment concession may be discussed: the fixes have been tried and the readings recorded.
- 「Explaining the problem」 is not 「solving it」. An explanation must be followed by "how it gets fixed", or it merely enlarges the problem in place.

### 13. Iteration: it counts only with a reading

**One pass of the loop below, all four steps, or the round did not happen**: a change with no reading is not an iteration, it is an edit.

```
run → get a reading → say clearly why this did not work → change → (the next one starts from "run")
```

All four steps, or it does not count:

- **Changing the code is not iterating.** Changed and not run, the state is "unverified".
- **With no reading from the first run, rounds two and three may not be scheduled.** Designing three rounds up front to run together means round two was fixed before the first analysis.
- **Saying "this should work" means you hold no reading.**

One criterion: does this message carry a new reading.

### 14. Money-spending actions need their own permission

Booting, training, pushing, metered calls each need one explicit permission.

- **Report three numbers**: what you will do, how many minutes, which reading you will look at.
- **「Continue」 and 「carry on」 are not permission to boot**; they authorise only the free part (reading code, local computation, writing code, editing documents).
- **When challenged, stop the bleeding first**: kill the fire (shut down, withdraw the action), then answer "no", and only then discuss the cause. Reversed, you are building yourself a reason.

### 15. What to answer when asked for 「lessons learned」

**By default it means the experimental layer**: which road was walked, what each assumed, why it did not work. It does not include my behaviour problems, an environment-trap list, a problem tree, or "what I should do next time" — each of those four has its own question.

One line per attempt, four columns:

| Attempt | What it assumed | Why it failed (mechanism) | Source |
|---|---|---|---|

The mechanism must land on a mechanism, not stop at "the parameters were not tuned right".

Three outcomes, marked separately; never blurred into one "it failed":

| Type | Meaning |
|---|---|
| hypothesis refuted | the mechanism is clear, the road can be struck out |
| measurement invalid | it was not measured; the road is not disproved |
| untried | the one thing not yet touched |

**「Measurement invalid」 is most easily written as 「hypothesis refuted」.** Six geometry comparisons all static was in fact a band set where there is no signal; record it as "geometry is not the cause" and four more rounds proceed on a false premise.

Every line must point at a log line or a context line; a number written from memory is checked and rewritten, deleted if unverifiable, and never given as "about".

Close with one sentence: what these failures jointly point at, and the one thing not yet tried.

### 16. When a link goes wrong, check the previous link first

A wrong result at one link: the first action is not to tune parameters there, but to go back and verify whether the previous link's product passed **its own** criterion just now; if that is also in doubt, go one more link back. **Suspect upstream by default; do not default to believing your own last version produced something.**

**Why:** downstream input is upstream output. With a broken upstream, every downstream parameter change fits noise, and each change produces a reading that "looks like a change" — change the resolution and the figure gets finer, change the smoothing and it blurs, change the parametrisation and the texture softens. All of those changes are real and none points at success. The longer you tune, the more "upstream is broken" is misread as "the downstream parameters are not right".

**How to apply:**

1. **Every link has a delivery gate, written on the first line of that link's README.** No passing, no entering the next link; the pass standard must be "something that can be pointed at" (is the target object in the product), not a process measure like loss, std or cos.
2. **Before entering the next link, run the previous link's gate once and copy the reading into this round's record.** Write "just measured", not "it passed last time".
3. **Two rounds of downstream tuning without movement means stop and go back up.** Two rounds is the ceiling, not the starting point.
4. **Use the previous link's own criterion when checking back**; do not invent a new ruler to excuse yourself.
5. **With upstream unpassed, no product of the next link may enter the report or serve as evidence.** It is not "a poor result", it is "no result".

Counter-example: taking "a different downstream parameter will probably fix it" as the default assumption. With a broken upstream, every downstream change produces a reading that looks like a change, and every one of them is fake progress.
