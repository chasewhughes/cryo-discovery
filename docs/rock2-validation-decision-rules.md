# ROCK2 validation decision rules

This framework governs the next decision independently of any Phase20 prediction values. It keeps model ranking, assay transfer, and cryopreservation biology as separate questions.

## Evidence currently available

- **Phase17 internal benchmark: pass.** The 43-compound panel from the original ROCK2 study (DOI [10.1021/acs.jmedchem.8b01098](https://doi.org/10.1021/acs.jmedchem.8b01098)) passed its prespecified point gates: two fixed Boltz-2 seeds had 35.8% lower MAE than the mean baseline and Spearman rho 0.744. The scaffold bootstrap interval crossed the 20% improvement threshold, so this is evidence of retrospective ranking on that assay family, not external validation.
- **Phase18 external assay: fail for transfer qualification.** The separate Morwick bisbenzamide/ureidobenzamide study (DOI [10.1021/jm9014263](https://doi.org/10.1021/jm9014263)) had raw transfer MAE 0.834 versus 0.586 for its source-mean baseline and rho 0.448. An assay-specific calibration improved held-out MAE to 0.433, but rho remained 0.441 and the 12.4% gain missed the 20% gate. This shows limited transfer and an offset correction; it does not isolate the cause of the error. it does not justify retuning on the held-out compounds.
- **Phase20: pending.** The 2019 chromen study (DOI [10.1021/acs.jmedchem.9b01143](https://doi.org/10.1021/acs.jmedchem.9b01143)) is a separate, source-reconciled non-luciferase biochemical panel. Its 50 exact compounds are split by whole achiral Murcko scaffolds into 20 calibration and 30 test compounds. No result should be treated as available until the frozen run and validation record are complete.

The Phase17 and Phase18 results answer different questions because their assay conditions differ. Preserve raw ranking against the source labels separately from any additive assay calibration; calibration can correct a systematic offset while leaving ordering unchanged. Neither result establishes that a ligand protects cells, inhibits ice recrystallization, or improves post-thaw survival.

## Frozen decision tree

1. **Before interpreting Phase20**, verify the executed-plan hash, input manifest hashes, source-label provenance, complete two-seed archive, and deletion/cost receipts. A missing or changed artifact is a provenance failure and the result is inconclusive.
2. **If Phase20 passes all prespecified gates**, report a *provisional, domain-limited retrospective transfer* across the documented ROCK2 biochemical assay conditions. Report raw and calibrated MAE, bias, rho, seed differences, and scaffold-cluster uncertainty together. This does not validate prospective novelty, independence from Boltz pretraining, cellular efficacy, CPA activity, or cryoprotection. Any next screen requires a new frozen plan and a separate prospective evaluation.
3. **If Phase20 fails any primary gate**, suspend unchanged Boltz screening for scientific claims. Choose between a frozen baseline and a model revision only through a fresh plan with new data or a preregistered calibration/validation design. Do not search additional panels until one passes, change thresholds after seeing results, or reuse Phase20 test labels for fitting.
4. **If Phase20 cannot be adjudicated**, label the transfer inconclusive and preserve the run. Do not convert a partial result, failed validation, or assay calibration gain into a pass.

A pass or fail concerns the prespecified biochemical prediction gates only. It cannot be called “hypothesis validated” for cryoprotection. The 2FA study (DOI [10.1093/stmcls/sxad059](https://doi.org/10.1093/stmcls/sxad059)) reports cell viability and recovery outcomes in an iPSC system; those endpoints require their own matched controls and do not follow from ROCK2 biochemical binding.

## Minimum evidence before a biological claim

A later claim about a cryoprotective or recovery intervention needs, at minimum, an assay-matched biochemical result with a defined construct/readout and an independent source or prospective test, plus a separate cell or material evaluation that measures the relevant endpoint (for example, post-thaw absolute recovery, retained function, and appropriate vehicle/fresh/frozen controls). Ice activity, CPA toxicity, and cell survival are distinct evidence axes. A ROCK2 IC50 alone is therefore a mechanism or transfer result, not evidence of CPA ice control or post-thaw survival.

Reproduction should use the archived executed plan and local manifests; it should not rent new compute merely to resolve an unfavorable result. Any further experiment needs a new frozen plan and fresh cumulative billing reconciliation.
