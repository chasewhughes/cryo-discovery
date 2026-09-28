"""Condition-specific IRI baselines with explicit structure-grouped validation.

Run with the storage wrapper and the requirements-iri.txt environment.
Original labels stay local; derived predictions and provenance are versioned.
"""
import csv
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/phase7/dolmen/data/datasets"
OUT = ROOT / "data/phase7"
FEATURES = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors",
            "NumRotatableBonds", "RingCount", "NumAromaticRings", "FractionCSP3",
            "HeavyAtomCount", "NHOHCount", "NOCount", "NumHeteroatoms",
            "BertzCT", "HallKierAlpha", "BalabanJ"]
MODEL_NAMES = ["median", "ridge", "forest"]


def structure(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    return {
        "canonical": Chem.MolToSmiles(mol, isomericSmiles=True),
        "connectivity": Chem.MolToSmiles(mol, isomericSmiles=False),
        "scaffold": MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "ACYCLIC",
        "features": [float(getattr(Descriptors, name)(mol)) for name in FEATURES],
    }


def read_records(dataset):
    records = []
    with (RAW / f"{dataset}.csv").open() as handle:
        for index, row in enumerate(csv.DictReader(handle), start=2):
            record = {"id": f"{dataset}:line{index}", "name": row["Name"],
                      "source_line": index, "concentration_mM_raw": row["Concentration (mM)"],
                      "set": row.get("Set", "train/test"),
                      "observed_mgs": float(row["Exp. % MGS"]), **structure(row["SMILES"])}
            if not np.isfinite(record["features"] + [record["observed_mgs"]]).all():
                raise ValueError(f"Nonfinite data: {record['id']}")
            records.append(record)
    return records


def model(name):
    if name == "median":
        return DummyRegressor(strategy="median")
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=10))
    if name == "forest":
        return RandomForestRegressor(n_estimators=300, min_samples_leaf=3,
                                     random_state=42, n_jobs=1)
    raise ValueError(name)


def make_splits(records, grouping):
    groups = np.array([r[grouping] for r in records])
    splitter = (GroupKFold(n_splits=5) if grouping == "scaffold" else
                GroupKFold(n_splits=5, shuffle=True, random_state=42))
    splits = list(splitter.split(np.zeros((len(records), 1)), groups=groups))
    for train, test in splits:
        for field in (grouping, "connectivity", "canonical"):
            assert not ({records[i][field] for i in train} & {records[i][field] for i in test}), field
    assert sorted(i for _, test in splits for i in test) == list(range(len(records)))
    return splits


def metrics(y, prediction, groups):
    errors = np.abs(y - prediction)
    unique = sorted(set(groups))
    return {"n": len(y), "mae_mgs_points": float(mean_absolute_error(y, prediction)),
            "rmse_mgs_points": float(np.sqrt(mean_squared_error(y, prediction))),
            "r2": float(r2_score(y, prediction)),
            "equal_group_mae_mgs_points": float(np.mean([np.mean(errors[groups == g]) for g in unique]))}


def paired_group_interval(y, prediction, baseline, groups):
    delta = np.abs(y - prediction) - np.abs(y - baseline)
    values = np.array([delta[groups == g].mean() for g in sorted(set(groups))])
    rng = np.random.default_rng(42)
    samples = rng.choice(values, size=(2000, len(values)), replace=True).mean(axis=1)
    return {"group_count": len(values), "equal_group_mean_delta": float(values.mean()),
            "percentile_95_interval": [float(x) for x in np.quantile(samples, [0.025, 0.975])],
            "interpretation": "Negative favors model; descriptive resampling of fixed out-of-fold group errors, not independent confirmation or molecular prediction intervals"}


def evaluate(records, grouping):
    X = np.array([r["features"] for r in records])
    y = np.array([r["observed_mgs"] for r in records])
    groups = np.array([r[grouping] for r in records])
    predictions = {name: np.full(len(records), np.nan) for name in MODEL_NAMES}
    assignments, folds = np.zeros(len(records), dtype=int), []
    for fold, (train, test) in enumerate(make_splits(records, grouping), start=1):
        assignments[test] = fold
        for name in MODEL_NAMES:
            fitted = model(name).fit(X[train], y[train])
            predictions[name][test] = fitted.predict(X[test])
        folds.append({"fold": fold, "train_ids": [records[i]["id"] for i in train],
                      "test_ids": [records[i]["id"] for i in test],
                      "train_groups": sorted(set(groups[train])), "test_groups": sorted(set(groups[test]))})
    assert all(np.isfinite(p).all() for p in predictions.values())
    results = {name: metrics(y, pred, groups) for name, pred in predictions.items()}
    for name in ("ridge", "forest"):
        results[name]["paired_group_error_vs_median"] = paired_group_interval(y, predictions[name], predictions["median"], groups)
    rows = [{"id": r["id"], "fold": int(assignments[i]), "group": r[grouping],
             "observed_mgs": r["observed_mgs"],
             "predicted_mgs": {name: float(pred[i]) for name, pred in predictions.items()}}
            for i, r in enumerate(records)]
    return {"grouping": grouping, "group_count": len(set(groups)),
            "largest_groups": Counter(groups).most_common(5), "metrics": results,
            "folds": folds, "predictions": rows}


def candidate_scope(cohorts, evaluations):
    glyco = cohorts["glyco2"]
    target = next(r for r in glyco if r["name"] == "n-2-fluorophenyl-d-gluconamide")
    result = {"2fa": {"status": "Already present in the published dataset; not a novel hit",
        "source_record": target["id"], "name": target["name"], "canonical_smiles": target["canonical"],
        "assay": "22 mM in PBS, reported % MGS; not the cellular dosing condition",
        "observed_mgs": target["observed_mgs"], "withheld_predictions": {}}}
    for group in ("scaffold", "connectivity"):
        evaluation = evaluations["glyco2"][group]
        result["2fa"]["withheld_predictions"][group] = next(p for p in evaluation["predictions"] if p["id"] == target["id"])
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
    target_fp = generator.GetFingerprint(Chem.MolFromSmiles(target["canonical"]))
    neighbors = []
    for r in glyco:
        if r["connectivity"] == target["connectivity"]:
            continue
        similarity = DataStructs.TanimotoSimilarity(target_fp, generator.GetFingerprint(Chem.MolFromSmiles(r["canonical"])))
        neighbors.append({"id": r["id"], "name": r["name"], "tanimoto": similarity,
                          "same_scaffold": r["scaffold"] == target["scaffold"]})
    result["2fa"]["nearest_other_connectivities"] = sorted(neighbors, key=lambda n: -n["tanimoto"])[:5]
    result["2fa"]["scope_note"] = "Aryl gluconamides are represented. Similarity is descriptive, not a calibrated applicability threshold; this assay cannot establish 2FA-plus-CEPT behavior."
    result["other_ranked_candidates"] = [
        {"candidate": "CEPT", "status": "No cocktail prediction: four-component recovery treatment; no mixture or biological-pathway labels in this benchmark"},
        {"candidate": "Polyampholyte", "status": "Macromolecular formulation outside this small-molecule representation"},
        {"candidate": "EG + trehalose", "status": "Mixture prediction unsupported; individual constituent IRI is not mixture CPA efficacy"},
        {"candidate": "CAMP", "status": "Multicomponent biomaterial outside representation"},
        {"candidate": "CspB", "status": "Protein outside representation"},
    ]
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify_manifest(manifest, root=ROOT):
    for item in manifest["files"]:
        content = (root / item["local_path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {item['local_path']}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / "source-manifest.json").read_text())
    verify_manifest(manifest)
    verify_manifest(json.loads((OUT / "primary-source-manifest.json").read_text()))
    raw = {name: read_records(name) for name in ("amino", "glyco", "glyco2")}
    cohorts = {"amino": [r for r in raw["amino"] if r["set"] == "train/test" and r["concentration_mM_raw"] == "20"],
               "glyco2": [r for r in raw["glyco2"] if r["concentration_mM_raw"] == "22"]}
    for records in cohorts.values():
        assert len({r["canonical"] for r in records}) == len(records), "Duplicate structures require an explicit policy"
    audit = {"source_commit": manifest["commit"], "raw_rows": {k: len(v) for k, v in raw.items()},
             "cohort_rows": {k: len(v) for k, v in cohorts.items()},
             "glyco_overlap_with_glyco2_by_canonical_structure": len({r["canonical"] for r in raw["glyco"]} & {r["canonical"] for r in raw["glyco2"]}),
             "glyco2_excluded_conditions": [{"id": r["id"], "concentration_mM_raw": r["concentration_mM_raw"]} for r in raw["glyco2"] if r["concentration_mM_raw"] != "22"],
             "feature_names": FEATURES,
             "features_note": "Recomputed 2D descriptors; archived 45-column upstream descriptors were acquired for inspection but not used",
             "structure_policy": "Canonicalize supplied SMILES; preserve salts, charges and tautomers as supplied. Connectivity grouping ignores stereochemistry, but no general salt/tautomer normalization or exhaustive analog clustering is claimed.",
             "amino_predict_records": [r["id"] for r in raw["amino"] if r["set"] == "predict"],
             "amino_predict_status": "Excluded from cross-validation; separate condition-audited diagnostic required because paper and CSV disagree on selected test concentrations"}
    write_json(OUT / "dataset-audit.json", audit)
    evaluations = {dataset: {group: evaluate(records, group) for group in ("scaffold", "connectivity")}
                   for dataset, records in cohorts.items()}
    artifact = {"plan_sha256": hashlib.sha256((OUT / "benchmark-plan.json").read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "source_manifest_sha256": hashlib.sha256((OUT / "source-manifest.json").read_bytes()).hexdigest(),
                "python": platform.python_version(),
                "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn", "rdkit", "matplotlib")},
                "evaluations": evaluations}
    write_json(OUT / "benchmark-results.json", artifact)
    write_json(OUT / "candidate-applicability.json", candidate_scope(cohorts, evaluations))
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/tmp/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    for ax, (dataset, result) in zip(axes, evaluations.items()):
        positions = np.arange(3)
        for offset, group, label, color in [(-0.18, "connectivity", "Withheld connectivity", "#6b8cae"), (0.18, "scaffold", "Withheld scaffold", "#b65d38")]:
            ax.bar(positions + offset, [result[group]["metrics"][n]["mae_mgs_points"] for n in MODEL_NAMES], 0.36, label=label, color=color)
        ax.set_xticks(positions, ["Median baseline", "Ridge", "Random forest"])
        ax.set_title(f"{dataset.capitalize()} | n={len(cohorts[dataset])}")
        ax.set_ylabel("Mean absolute error (% MGS points; lower is better)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, 45)
        ax.legend(fontsize=8)
    fig.suptitle("IRI prediction benchmark — existing assay data, not cell survival", fontsize=13)
    fig.savefig(ROOT / "reports/iri-benchmark.png", dpi=160)
    plt.close(fig)
    print(json.dumps({d: {g: {m: round(v["mae_mgs_points"], 2) for m, v in e["metrics"].items()} for g, e in gs.items()} for d, gs in evaluations.items()}))


if __name__ == "__main__":
    main()
