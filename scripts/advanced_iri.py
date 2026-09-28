"""Nested grouped IRI models; benchmark outcomes must not tune held-out fits."""
import csv
from collections import defaultdict
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import unicodedata

import joblib
import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold, ParameterGrid
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

try:
    from scripts import benchmark_iri as base
except ModuleNotFoundError:
    import benchmark_iri as base

ROOT = base.ROOT
OUT = ROOT / "data/phase8"
FAMILIES = ["standard_svr", "hydration_svr", "fingerprint_krr"]


def normalized_name(name):
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


def descriptor_rows(path):
    with path.open() as handle:
        rows = list(csv.reader(handle))
    width = len(rows[0]) - 1
    if any(len(row) != width + 1 for row in rows[1:]):
        raise ValueError(f"Unequal descriptor row widths: {path}")
    values = np.array([[float(v) if v.strip() else np.nan for v in row[1:]] for row in rows[1:]])
    if np.isinf(values).any():
        raise ValueError(f"Infinite descriptors: {path}")
    return [row[0] for row in rows[1:]], values


def join_by_name(records, names, values):
    lookup = defaultdict(list)
    for name, vector in zip(names, values):
        if normalized_name(name) not in ("", "nan"):
            lookup[normalized_name(name)].append(vector)
    joined, statuses = [], []
    for record in records:
        candidates = lookup.get(normalized_name(record["name"]), [])
        if not candidates:
            joined.append(np.full(values.shape[1], np.nan)); statuses.append("unmapped")
        elif not all(np.allclose(candidates[0], c, equal_nan=True, rtol=0, atol=0) for c in candidates[1:]):
            joined.append(np.full(values.shape[1], np.nan)); statuses.append("conflicting_duplicate_name")
        else:
            joined.append(candidates[0]); statuses.append("matched" if len(candidates) == 1 else "identical_duplicate_vectors")
    return np.array(joined), statuses


def load_features(dataset, records):
    names, standard_all = descriptor_rows(ROOT / f"data/raw/phase7/dolmen/data/descriptors/std_{dataset}.csv")
    standard = []
    for record in records:
        index = record["source_line"] - 2
        source_name, descriptor_name = normalized_name(record["name"]), normalized_name(names[index])
        if source_name != descriptor_name and {source_name, descriptor_name} != {"nan", ""}:
            raise ValueError(f"Standard row-name mismatch: {record['id']}")
        standard.append(standard_all[index])
    standard = np.array(standard)
    if standard.shape[1] != 45:
        raise ValueError("Unexpected standard descriptor schema")
    audit = {"standard_missing_cells": int(np.isnan(standard).sum()), "hydration": {}}
    hydration = [standard]
    for representation, width in (("hydhist", 100), ("hydidx", 10)):
        names, values = descriptor_rows(ROOT / f"data/raw/phase8/dolmen/data/descriptors/{representation}_{dataset}.csv")
        if values.shape[1] != width:
            raise ValueError(f"Unexpected {representation} schema")
        joined, statuses = join_by_name(records, names, values)
        hydration.append(joined)
        audit["hydration"][representation] = {
            "source_rows": len(names), "dimensions": width,
            "complete_rows": int(np.isfinite(joined).all(axis=1).sum()),
            "missing_cells": int(np.isnan(joined).sum()),
            "join_statuses": [{"id": r["id"], "status": status, "missing_features": int(np.isnan(row).sum())}
                              for r, status, row in zip(records, statuses, joined)]}
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
    fingerprints = np.array([generator.GetFingerprintAsNumPy(Chem.MolFromSmiles(r["canonical"])) for r in records], dtype=float)
    return {"standard_svr": standard, "hydration_svr": np.column_stack(hydration), "fingerprint_krr": fingerprints}, audit


def tanimoto(X, Y):
    product = np.asarray(X, dtype=float) @ np.asarray(Y, dtype=float).T
    denominator = X.sum(axis=1)[:, None] + Y.sum(axis=1)[None, :] - product
    return np.divide(product, denominator, out=np.zeros_like(product), where=denominator != 0)


class TanimotoRegressor(RegressorMixin, BaseEstimator):
    def __init__(self, alpha=1.):
        self.alpha = alpha

    def fit(self, X, y):
        self.X_ = np.asarray(X, dtype=float).copy()
        self.mean_ = float(np.mean(y))
        self.weights_ = np.linalg.solve(tanimoto(self.X_, self.X_) + self.alpha * np.eye(len(X)), y - self.mean_)
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X):
        return tanimoto(np.asarray(X, dtype=float), self.X_) @ self.weights_ + self.mean_


def configurations(family):
    if family == "fingerprint_krr":
        return [{"alpha": a} for a in (0.01, 0.1, 1., 10.)]
    return list(ParameterGrid({"C": [10., 100.], "gamma": ["scale", 0.01]}))


def estimator(family, parameters):
    if family == "fingerprint_krr":
        return TanimotoRegressor(**parameters)
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                         StandardScaler(), SVR(kernel="rbf", epsilon=5., **parameters))


def tune_fit(family, X, y, groups, grid=None):
    splits = list(GroupKFold(n_splits=3).split(X, y, groups))
    trials = []
    for parameters in grid or configurations(family):
        prediction = np.full(len(y), np.nan)
        for train, validation in splits:
            if set(groups[train]) & set(groups[validation]):
                raise ValueError("Inner-group leakage")
            fitted = estimator(family, parameters).fit(X[train], y[train])
            prediction[validation] = fitted.predict(X[validation])
        if not np.isfinite(prediction).all():
            raise ValueError("Missing inner predictions")
        trials.append({"parameters": parameters, "inner_oof_mae": float(np.mean(np.abs(y - prediction)))})
    best = min(trials, key=lambda trial: trial["inner_oof_mae"])
    return estimator(family, best["parameters"]).fit(X, y), {"selected": best, "trials": trials,
        "inner_splits": [{"train_indices": t.tolist(), "validation_indices": v.tolist()} for t, v in splits]}


def evaluate(dataset, records, features, grouping, previous):
    y = np.array([r["observed_mgs"] for r in records])
    groups = np.array([r[grouping] for r in records])
    predictions = {family: np.full(len(y), np.nan) for family in FAMILIES}
    traces = []
    for fold, (train, test) in enumerate(base.make_splits(records, grouping), start=1):
        old_fold = previous["folds"][fold - 1]
        if old_fold["test_ids"] != [records[i]["id"] for i in test] or old_fold["train_ids"] != [records[i]["id"] for i in train]:
            raise ValueError("Outer splits differ from Phase 7")
        trace = {"fold": fold, "outer_train_ids": old_fold["train_ids"], "outer_test_ids": old_fold["test_ids"], "families": {}}
        for family in FAMILIES:
            fitted, info = tune_fit(family, features[family][train], y[train], groups[train])
            predictions[family][test] = fitted.predict(features[family][test])
            trace["families"][family] = info
        traces.append(trace)
    predictions["ensemble"] = np.mean([predictions[f] for f in FAMILIES], axis=0)
    baseline = {name: np.array([p["predicted_mgs"][name] for p in previous["predictions"]]) for name in ("median", "forest")}
    if [p["id"] for p in previous["predictions"]] != [r["id"] for r in records]:
        raise ValueError("Baseline prediction alignment differs")
    results = {}
    for name, prediction in predictions.items():
        if not np.isfinite(prediction).all():
            raise ValueError("Nonfinite outer prediction")
        results[name] = base.metrics(y, prediction, groups)
        results[name]["paired_vs_phase7"] = {m: base.paired_group_interval(y, prediction, b, groups) for m, b in baseline.items()}
    return {"metrics": results, "tuning": traces,
            "predictions": [{"id": r["id"], "observed_mgs": r["observed_mgs"],
                             "predicted_mgs": {f: float(p[i]) for f, p in predictions.items()}}
                            for i, r in enumerate(records)]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for phase in ("phase7", "phase8"):
        base.verify_manifest(json.loads((ROOT / f"data/{phase}/source-manifest.json").read_text()))
    previous = json.loads((ROOT / "data/phase7/benchmark-results.json").read_text())
    cohorts = {"amino": [r for r in base.read_records("amino") if r["set"] == "train/test" and r["concentration_mM_raw"] == "20"],
               "glyco2": [r for r in base.read_records("glyco2") if r["concentration_mM_raw"] == "22"]}
    audits, evaluations, final_models = {}, {}, {}
    model_dir = ROOT / "data/raw/phase8/models"
    model_dir.mkdir(parents=True, exist_ok=True)
    for dataset, records in cohorts.items():
        features, audits[dataset] = load_features(dataset, records)
        evaluations[dataset] = {}
        for grouping in ("scaffold", "connectivity"):
            evaluations[dataset][grouping] = evaluate(dataset, records, features, grouping, previous["evaluations"][dataset][grouping])
            print(f"Finished {dataset} {grouping}", flush=True)
        y = np.array([r["observed_mgs"] for r in records])
        groups = np.array([r["scaffold"] for r in records])
        fitted_models, final_info = {}, {}
        for family in FAMILIES:
            fitted_models[family], final_info[family] = tune_fit(family, features[family], y, groups)
        path = model_dir / f"{dataset}-ensemble.joblib"
        joblib.dump({"models": fitted_models, "ensemble_weights": [1/3]*3,
                     "training_ids": [r["id"] for r in records], "status": "Research model; no independent external validation"}, path)
        final_models[dataset] = {"local_path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "parameters": final_info, "note": "Full-data fits are not used for reported performance. Only load locally generated, trusted model files."}
    artifact = {"plan_sha256": hashlib.sha256((OUT / "model-plan.json").read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "base_script_sha256": hashlib.sha256((ROOT / "scripts/benchmark_iri.py").read_bytes()).hexdigest(),
                "phase7_results_sha256": hashlib.sha256((ROOT / "data/phase7/benchmark-results.json").read_bytes()).hexdigest(),
                "source_manifest_sha256": hashlib.sha256((OUT / "source-manifest.json").read_bytes()).hexdigest(),
                "environment": {"python": platform.python_version(), "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn", "rdkit", "matplotlib", "joblib")}},
                "evaluations": evaluations, "final_models": final_models}
    base.write_json(OUT / "feature-audit.json", audits)
    base.write_json(OUT / "advanced-results.json", artifact)
    target = next(r for r in cohorts["glyco2"] if r["name"] == "n-2-fluorophenyl-d-gluconamide")
    base.write_json(OUT / "2fa-diagnostic.json", {"status": "Previously inspected known compound, not an independent confirmation", "source_record": target["id"],
        "withheld_predictions": {g: next(p for p in e["predictions"] if p["id"] == target["id"]) for g, e in evaluations["glyco2"].items()}})
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/tmp/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, dataset in zip(axes, cohorts):
        labels = ["Median", "Prior forest", "Standard SVR", "Hydration SVR", "Fingerprint KRR", "Ensemble"]
        values = [previous["evaluations"][dataset]["scaffold"]["metrics"][m]["mae_mgs_points"] for m in ("median", "forest")]
        values += [evaluations[dataset]["scaffold"]["metrics"][m]["mae_mgs_points"] for m in FAMILIES + ["ensemble"]]
        ax.barh(labels, values, color=["#9ca3af", "#9ca3af", "#5384a6", "#5384a6", "#5384a6", "#b65d38"])
        for i, value in enumerate(values):
            ax.text(value + .3, i, f"{value:.1f}", va="center", fontsize=9)
        ax.invert_yaxis(); ax.set_xlim(0, 45)
        ax.set_title(f"{dataset.capitalize()} | n={len(cohorts[dataset])}")
        ax.set_xlabel("MAE (% MGS points; lower is better)")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Advanced IRI models: nested tuning, withheld scaffolds", fontsize=14)
    fig.savefig(ROOT / "reports/advanced-iri.png", dpi=160)
    plt.close(fig)
    print(json.dumps({d: {g: {m: round(v["mae_mgs_points"], 2) for m, v in e["metrics"].items()} for g, e in gs.items()} for d, gs in evaluations.items()}))


if __name__ == "__main__":
    # Persist custom estimators under an importable module, not __main__.
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.advanced_iri import main as run
    run()
