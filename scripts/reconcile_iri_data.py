"""Reconcile original Amino assay metadata and test frozen models retrospectively.

No source CSV, descriptor file, previous benchmark or model is modified.
"""
import csv
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from rdkit.Chem.MolStandardize import rdMolStandardize

try:
    from scripts import advanced_iri as advanced
except ModuleNotFoundError:
    import advanced_iri as advanced

ROOT = advanced.ROOT
OUT = ROOT / "data/phase9"
EXCEPTIONS = {
    "ethyl 2-amino-5-methyl-1,3-oxazole-4-carboxylate": 7,
    "(2s)-2-amino-3-(3,5-dichloro-4-hydroxyphenyl)propanoic acid": 8,
    "5-nitropyridine-2-carboxylic acid": 9,
}


def normalized_parent(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid source SMILES")
    parent = rdMolStandardize.ChargeParent(mol)
    parent = rdMolStandardize.CanonicalTautomer(parent)
    return Chem.MolToSmiles(parent, isomericSmiles=False)


def resolve_condition(name, set_name, raw_concentration):
    if name in EXCEPTIONS:
        if set_name != "predict" or raw_concentration != "20":
            raise ValueError("Exception no longer matches audited source record")
        return {"resolved_compound_mM": 10., "figure4_compound_number": EXCEPTIONS[name],
                "status": "specific_main_text_exception_over_generic_csv_and_supplement_caption",
                "source_conflict": True,
                "evidence": "Main Figure 4 caption and results explicitly specify 10 mM for 7-9; Supplement Figure S10, PDF page 16, establishes structure-number mapping but its generic 20 mM caption conflicts."}
    return {"resolved_compound_mM": float(raw_concentration), "figure4_compound_number": None,
            "status": "source_nominal_condition", "source_conflict": False,
            "evidence": "DOLMEN amino.csv and main assay methods; no compound-specific exception identified."}


def build_records(rows, descriptor_rows):
    if len(rows) != len(descriptor_rows):
        raise ValueError("Unequal input tables")
    result = []
    for line, (row, descriptor) in enumerate(zip(rows, descriptor_rows), 2):
        if advanced.normalized_name(row["Name"]) != advanced.normalized_name(descriptor["Name"]):
            raise ValueError("Descriptor row-name mismatch")
        mol = Chem.MolFromSmiles(row["SMILES"])
        if mol is None:
            raise ValueError("Invalid source SMILES")
        supplied, calculated = float(descriptor["4"]), Descriptors.ExactMolWt(mol)
        salt_named = "chloride" in row["Name"].casefold()
        result.append({"id": f"amino:line{line}", "name": row["Name"],
            "canonical_smiles": Chem.MolToSmiles(mol),
            "connectivity": Chem.MolToSmiles(mol, isomericSmiles=False),
            "charge_tautomer_parent_for_overlap_only": normalized_parent(row["SMILES"]),
            "set": row["Set"], "raw_compound_mM": row["Concentration (mM)"],
            "condition": resolve_condition(row["Name"], row["Set"], row["Concentration (mM)"]),
            "assay": {"endpoint": "% MGS", "buffer": "10 mM NaCl", "anneal_C": -8, "anneal_minutes": 30,
                      "condition_source": "Main methods and Supplement section 1.1; lower MGS indicates stronger cell-free IRI"},
            "observed_mgs": float(row["Exp. % MGS"]), "reported_sd_mgs": float(row["Exp. error"]),
            "molecular_state": {"formal_charge_from_supplied_smiles": Chem.GetFormalCharge(mol),
                "supplied_descriptor_exact_mass": supplied, "smiles_exact_mass": calculated,
                "delta_smiles_minus_descriptor_Da": calculated - supplied,
                "mass_disagreement": abs(calculated - supplied) > .001,
                "chloride_named_but_no_chloride_fragment": salt_named and not any(a.GetAtomicNum() == 17 for a in mol.GetAtoms())},
            "normalization_note": "Charge/tautomer parent is only an overlap key, not an asserted assay protonation state. Source structures, descriptors and labels are preserved."})
    for name in EXCEPTIONS:
        if sum(r["name"] == name for r in result) != 1:
            raise ValueError("Missing or duplicate exception identity")
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    advanced.base.verify_manifest(json.loads((ROOT / "data/phase7/source-manifest.json").read_text()))
    advanced.base.verify_manifest(json.loads((OUT / "source-manifest.json").read_text()))
    with (ROOT / "data/raw/phase7/dolmen/data/datasets/amino.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    with (ROOT / "data/raw/phase7/dolmen/data/descriptors/std_amino.csv").open() as handle:
        descriptors = list(csv.DictReader(handle))
    records = build_records(rows, descriptors)
    training = [r for r in records if r["set"] == "train/test"]
    prediction = [r for r in records if r["set"] == "predict"]
    train_keys = {key: {r[key] for r in training} for key in ("canonical_smiles", "connectivity", "charge_tautomer_parent_for_overlap_only")}
    for r in prediction:
        r["overlap_with_training"] = {key: r[key] in keys for key, keys in train_keys.items()}
    prior = json.loads((ROOT / "data/phase8/advanced-results.json").read_text())
    metadata = prior["final_models"]["amino"]
    model_path = ROOT / metadata["local_path"]
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Frozen model artifact changed")
    bundle = joblib.load(model_path)
    if bundle["training_ids"] != [r["id"] for r in training]:
        raise ValueError("Unexpected frozen model training cohort")
    eligible = [r for r in prediction if r["condition"]["resolved_compound_mM"] == 20]
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
    fingerprints = np.array([generator.GetFingerprintAsNumPy(Chem.MolFromSmiles(r["canonical_smiles"])) for r in eligible], float)
    by_id = {f"amino:line{i}": d for i, d in enumerate(descriptors, 2)}
    standard = np.array([[float(by_id[r["id"]][str(i)]) for i in range(45)] for r in eligible])
    baseline = float(np.median([r["observed_mgs"] for r in training]))
    predictions = {"frozen_fingerprint_krr": bundle["models"]["fingerprint_krr"].predict(fingerprints),
                   "frozen_standard_svr": bundle["models"]["standard_svr"].predict(standard),
                   "training_median": np.full(len(eligible), baseline)}
    scored = [{"id": r["id"], "observed_mgs": r["observed_mgs"],
               "predicted_mgs": {m: float(v[i]) for m, v in predictions.items()},
               "overlap_with_training": r["overlap_with_training"]} for i, r in enumerate(eligible)]
    metrics = {}
    for group_name, mask in {"all_20mM": np.ones(len(eligible), bool),
                             "20mM_without_normalized_parent_overlap": np.array([not r["overlap_with_training"]["charge_tautomer_parent_for_overlap_only"] for r in eligible])}.items():
        y = np.array([r["observed_mgs"] for r in eligible])[mask]
        groups = np.array([r["connectivity"] for r in eligible])[mask]
        metrics[group_name] = {m: advanced.base.metrics(y, p[mask], groups) for m, p in predictions.items()} if len(y) >= 2 else {"status": "Insufficient rows for summary metrics"}
    audit = {"raw_rows": len(records), "training_rows": len(training), "prediction_rows": len(prediction),
             "prediction_20mM": len(eligible), "prediction_10mM": sum(r["condition"]["resolved_compound_mM"] == 10 for r in prediction),
             "mass_disagreements_all": sum(r["molecular_state"]["mass_disagreement"] for r in records),
             "mass_disagreements_training": sum(r["molecular_state"]["mass_disagreement"] for r in training)}
    advanced.base.write_json(OUT / "assay-reconciliation.json", {"source_doi": "10.1038/s41467-024-52266-w", "summary": audit, "records": records})
    advanced.base.write_json(OUT / "retrospective-diagnostic.json", {
        "status": "Retrospective source-selected diagnostic; labels were previously visible to the research team. Not new independent external validation.",
        "primary_model": "Frozen Phase 8 fingerprint component; standard SVR is secondary, not the full ensemble",
        "model_sha256": metadata["sha256"], "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scoring_rule": "Only resolved 20 mM prediction records; 10 mM exceptions are not scored against the 20 mM model. No retraining or parameter selection.",
        "metrics": metrics, "predictions": scored,
        "excluded_condition_shift_ids": [r["id"] for r in prediction if r["condition"]["resolved_compound_mM"] != 20],
        "limits": "Small source-selected sample; familiar chemical series; molecular-state uncertainties persist; no biological or mixture inference."})
    print(json.dumps(audit))
    print(json.dumps({g: {m: round(v["mae_mgs_points"], 2) for m, v in models.items()} for g, models in metrics.items()}))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.reconcile_iri_data import main as run
    run()
