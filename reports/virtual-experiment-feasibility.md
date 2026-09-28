# Virtual experiments and laboratory feasibility

Follow-up: the [first IRI computational benchmark is now complete](iri-benchmark.md). The feasibility assessment below records the earlier planning state.

Assessment date: 2026-09-06. This extends the [Phase 5 matrix](../data/phase5/experiment-matrix.json). It is a feasibility assessment; no new simulation, laboratory experiment, purchase or external contact has occurred. The evidence corpus remains 40 papers and 75 experiment summaries. The additional sources below have not yet been extracted into that corpus.

## Recommended next step

Run a bounded computational benchmark before commissioning the cell pilot. First reproduce an existing ice-recrystallization-inhibition (IRI) prediction task with public molecular structures, assay labels and descriptors. In parallel, a literature-calibrated water-transport model can explore how uncertain cell properties change freezing predictions. Neither result should be represented as observed cell survival or proof that 2FA plus CEPT works.

There is a directly relevant precedent: Warren and colleagues combined molecular representations, including simulation-derived features, with experimental IRI data and subsequently tested predicted hits. They also report poor transfer between amino-acid and carbohydrate chemical domains and differences in assay solution conditions. This supports a narrowly defined benchmark with explicit domain limits. [Primary study](https://www.nature.com/articles/s41467-024-52266-w).

The authors provide structures, IRI labels and precomputed descriptors in [DOLMEN](https://github.com/gcsosso/DOLMEN); source data are deposited at [Warwick](https://wrap.warwick.ac.uk/id/eprint/187155/). Start by inspecting these files, licenses, assay metadata and dependencies. Public access has been checked; file-level integrity, complete model reproducibility and local runtime have not yet been checked. No new paid API is needed for that inspection or an initial local baseline.

## What each virtual experiment can answer

| Approach | Useful output | Required data and boundary |
| --- | --- | --- |
| IRI prediction / virtual compound screening | Rank structurally relevant candidates for an ice assay | Exact structures, comparable concentration/buffer/endpoint labels and external validation. IRI predictions are not viability or death-pathway predictions. |
| Cell water/CPA transport and freezing physics | Cell-volume trajectories, dehydration tradeoffs, sensitivity to thermal history; ice probability only with a calibrated nucleation model | Cell-specific permeability, activation energies, inactive volume, solution properties and thermal boundary conditions. Missing parameters remain ranges, not invented measurements. |
| Molecular dynamics | Test molecular hydration or ice-interface hypotheses for selected compounds | Verified stereochemistry, force fields, water model, concentration and convergence checks. Molecular behavior does not directly determine cell survival; large runs may require additional compute. |
| Cell/signaling models | Explore assumed injury, recovery, growth and pathway interactions | Calibrated rates and perturbation data. Encoding a protective rule and observing protection does not independently establish efficacy. |
| Simulated experimental design | Compare donor/batch allocation, precision and sensitivity to plausible effect sizes | Transparent variance/effect scenarios. Synthetic observations cannot augment biological replication or establish synergy. |

Published cryopreservation models estimate membrane transport parameters from cryomicroscopy and then model intracellular ice. That is a useful reference implementation, but parameters from HeLa cells cannot simply stand in for iPSCs. [Primary water-transport/ice study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4031135/). Nonideal-solution behavior can also matter in concentrated freezing media. [Primary modeling study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169418/).

[PhysiCell](https://physicell.org/) supports cell behavior and intracellular-model extensions. For this project, it would require custom cryoinjury and recovery calibration; the available framework is not evidence of a validated cryopreserved iPSC digital twin. Defer a large cell simulation until we have data that identify its parameters.

## Computational acceptance gates

1. Freeze source versions/hashes and retain assay conditions and structure identifiers. Do not pool incompatible IRI assays or count overlapping datasets twice.
2. Reproduce a simple baseline before adding molecular dynamics. Split by compound/scaffold, with related measurements kept together; fit preprocessing only within training folds. Compare to a trivial baseline and document error and applicability limits.
3. Test physical models for dimensional consistency, equilibrium/limiting behavior and numerical convergence; reproduce a published benchmark before exploring iPSC parameter ranges. Keep calibration and validation observations separate.
4. Report uncertainty and conditions under which candidate rankings change. If evidence does not constrain the model, identify the missing measurement rather than output a confident optimum.
5. Deliver a reproducible benchmark report, conditional candidate shortlist and measurement-priority list. These are the computational milestones; cell-function validation remains an experimental milestone.

## Laboratory handoff retained for later use

The proposed 48 frozen vials are three donor lines × two batches × two technical vials × four arms, plus matched fresh controls. This does not include dose qualification, destructive assay allocations, repeats or neuronal confirmation, and is not a power calculation. A laboratory must confirm whether its material supports all planned endpoints before quantities are fixed.

Use characterized iPSC lines and document identity, contamination testing, passage/genomic status and pluripotency. [ATCC characterization guidance](https://www.atcc.org/resources/culture-guides/stem-cell-culture-guide). Record absolute live-cell recovery immediately after wash and at 24 hours, with identity-qualified clonogenic output as a separate gate. For neuronal confirmation, hold culture age, density, medium and recording configuration explicit: these affect MEA readouts. [Manufacturer assay study](https://files.axionbiosystems.com/resources/application-note/best-practices-vitro-neural-assays-maestro-mea-system).

The [material check](../data/phase6/material-sources.json) identifies current CEPT-component catalog routes. Original CEPT methods use Sigma P8483; a later commercial kit should not redefine that literature reference. Exact 2FA catalog access is unresolved, so source-lab access or custom synthesis may be needed; a starting material is not an acceptable identity substitute. No material has been ordered.

For a quote, ask the eventual lab to price these work packages separately:

| Work package | Quantity basis to finalize | Current cost status |
| --- | --- | --- |
| Cell access, expansion and qualification | Three independent donors; existing banks versus acquisition; QC per line/batch | Quote required |
| 2FA and CEPT identity/material preparation | Confirmed formulation, fill and recovery volumes, assay usage, stock wastage and lot testing | Mostly unquoted; one displayed catalog price is not a project estimate |
| Tolerability and physical IRI qualification | Conditions, independent runs and assay capacity | Quote required |
| Frozen factorial and matched fresh controls | 48 core frozen vials plus separately allocated controls and assays | Quote required |
| Counting, identity and clonogenic assays | Sampling allocation and predeclared endpoints | Quote required |
| Neuronal differentiation and MEA confirmation | Conditional second stage, fixed schedule and independent batches | Quote required |
| Labor, storage, analysis and repeat allowance | Lab-specific hours, facilities and explicit repeat policy | Quote required |

No laboratory partner, experimental budget or cell inventory has been supplied. These prevent an executable laboratory schedule and firm cost estimate, but do not prevent public-data computational benchmarking. Wet-lab measurements will ultimately be needed to establish new compound activity, combination benefit, tolerability and retained function in the target cells.
