# Hydration sampling calibration

This analysis reuses the twelve Phase 11 trajectories. It is an engineering
calibration informed by the observed Phase 11 flags, not independent validation.
The primary 100-bin descriptor and TV > 0.05 threshold remain unchanged.

| Bins | Each endpoint window (ns) | TV range across runs | Above 0.05 |
| --- | --- | --- | --- |
| 20 | 0.5 | 0.0290–0.0552 | 3/12 |
| 20 | 1 | 0.0148–0.0386 | 0/12 |
| 20 | 1.5 | 0.0150–0.0285 | 0/12 |
| 50 | 0.5 | 0.0480–0.0977 | 11/12 |
| 50 | 1 | 0.0339–0.0686 | 5/12 |
| 50 | 1.5 | 0.0302–0.0490 | 0/12 |
| 100 | 0.5 | 0.0704–0.1154 | 12/12 |
| 100 | 1 | 0.0527–0.0846 | 12/12 |
| 100 | 1.5 | 0.0432–0.0680 | 11/12 |

The complete 20/50/100-bin, 100/250/500-ps block, and 0.5/1/1.5-ns endpoint
grid is preserved in `data/phase12/offline-calibration.json`, including every
trajectory and 1,000 block permutations per combination. Mixing compares
disjoint groups of equal duration, retaining within-block ordering and equal
frame weighting. Tail fractions are descriptive; exchangeability and the
dependence scale are unestablished. Fewer bins necessarily reduce or preserve
TV, so a lower coarse-bin value is not evidence of convergence.

The follow-up retains 100 bins and compares the first and second 5 ns of each
new 10-ns branch. Five 2-ns windows and all three block scales are secondary
diagnostics. Two NVT parents were selected because their Phase 11 chronological
TV exceeded the post hoc 100-ps mixing envelope; their matched NPT parents are
included. These selected branches share starting-state history with Phase 11.
They are not independent starting conformations, and old and new production
segments will not be pooled. This study measures sampling stability only.
