"""Freeze and run a bounded, evidence-linked virtual experiment.

Usage: python scripts/discovery_pipeline.py status
       python scripts/discovery_pipeline.py freeze transport-001
       python scripts/discovery_pipeline.py run transport-001
       python scripts/discovery_pipeline.py verify transport-001

Only registered local adapters execute. Source/code checksums are verified before
run; an existing start receipt prevents accidental overwrite, even after failure.
Checksums detect changes, not adversarial tampering or external preregistration.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess

from hypothesis_registry import _digest, validate_conclusion, validate_hypothesis, validate_plan

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/phase14/hypotheses.json"
RUNS = ROOT / "data/phase14/runs"
CODE = ["scripts/discovery_pipeline.py", "scripts/cell_transport.py", "scripts/hypothesis_registry.py"]


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    # Serialize before creation, so a NaN does not leave a partial JSON artifact.
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x") as f:
        f.write(payload)


def require(errors):
    if errors:
        raise ValueError("; ".join(errors))


def run_path(run_id):
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", run_id):
        raise ValueError("Use a stable lowercase run ID (3-64 letters/digits/hyphens)")
    return RUNS / run_id


def check_refs(refs):
    for ref in refs:
        path = ROOT / ref["source_path"]
        if not path.is_file() or sha(path) != ref["sha256"]:
            raise ValueError(f"Missing or changed evidence: {ref['source_path']}")


def validate_design(h):
    from cell_transport import Parameters, validate_schedule
    design = h.get("design", {})
    Parameters(**design["parameters"])
    if set(design["schedules"]) != {"single", "staged"}:
        raise ValueError("Adapter requires single and staged schedules")
    for schedule in design["schedules"].values():
        validate_schedule(schedule)
    single, staged = (design["schedules"][name] for name in ("single", "staged"))
    if abs(sum(s["duration_min"] for s in single)-sum(s["duration_min"] for s in staged)) > 1e-10:
        raise ValueError("Comparison requires equal total duration")
    if any(single[-1][k] != staged[-1][k] for k in ("m1", "m2")) or single[-1]["m2"] <= 0:
        raise ValueError("Comparison requires equal, nonzero final CPA baths")
    for key in ("sensitivity_b_factors", "sensitivity_time_factors"):
        factors = design.get(key)
        if not isinstance(factors, list) or not factors or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in factors):
            raise ValueError(f"Invalid {key}")
    for key in ("minimum_volume_improvement", "minimum_final_loading_ratio", "reference_max_abs_state_error", "convergence_max_abs_metric_error"):
        value = h["acceptance_criteria"].get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid criterion: {key}")


def freeze(run_id, hypothesis_id=None):
    hypotheses = read(REGISTRY)["hypotheses"]
    if hypothesis_id is None and len(hypotheses) != 1:
        raise ValueError("Select --hypothesis when the registry has multiple hypotheses")
    matches = [h for h in hypotheses if hypothesis_id is None or h["id"] == hypothesis_id]
    if len(matches) != 1:
        raise ValueError("Hypothesis ID is missing or ambiguous")
    h = matches[0]
    require(validate_hypothesis(h))
    validate_design(h)
    check_refs(h["evidence_refs"])
    plan = {**h, "plan_id": run_id, "hypothesis_id": h["id"],
            "hypothesis_hash": _digest(h), "frozen_at": now(),
            "adapter": "cell_transport_v1",
            "code_refs": [{"source_path": p, "sha256": sha(ROOT/p)} for p in CODE],
            "git_head_before_freeze": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    require(validate_plan(plan, h))
    folder = run_path(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    write_new(folder / "hypothesis.json", h)
    write_new(folder / "plan.json", plan)
    print(f"Frozen {run_id}: {_digest(plan)}")


def decision(base, staged, criteria):
    improvement = staged["min_relative_volume"] - base["min_relative_volume"]
    retained = staged["final_intracellular_eg_osm_per_kg"] / base["final_intracellular_eg_osm_per_kg"]
    return {"min_volume_improvement": improvement, "final_loading_ratio": retained,
            "criteria_met": bool(improvement >= criteria["minimum_volume_improvement"] and
                                 retained >= criteria["minimum_final_loading_ratio"])}


def transport(plan):
    import numpy as np
    import scipy
    from cell_transport import Parameters, reference_error, simulate
    design = plan["design"]
    p = Parameters(**design["parameters"])
    trajectories = {name: simulate(steps, p) for name, steps in design["schedules"].items()}
    metrics = {name: value["metrics"] for name, value in trajectories.items()}
    reference = {name: reference_error(design["schedules"][name], value, p)
                 for name, value in trajectories.items()}
    convergence = {}
    for name, steps in design["schedules"].items():
        fine = simulate(steps, p, rtol=1e-11, atol=1e-13, sample_interval_min=.01)
        convergence[name] = max(abs(fine["metrics"][key]-val) for key, val in metrics[name].items())
    criteria = plan["acceptance_criteria"]
    checks_pass = max(reference.values()) <= criteria["reference_max_abs_state_error"] and max(convergence.values()) <= criteria["convergence_max_abs_metric_error"]
    primary = decision(metrics["single"], metrics["staged"], criteria)
    scenarios = []
    for b_factor in design["sensitivity_b_factors"]:
        for time_factor in design["sensitivity_time_factors"]:
            varied = Parameters(p.b*b_factor, p.minutes_per_tau*time_factor, p.gamma)
            pair = {name: simulate(steps, varied)["metrics"] for name, steps in design["schedules"].items()}
            scenarios.append({"b_factor": b_factor, "time_factor": time_factor,
                              "parameters": asdict(varied), "metrics": pair,
                              **decision(pair["single"], pair["staged"], criteria)})
    state = "supported_in_reference_model" if primary["criteria_met"] else "not_supported_in_reference_model"
    if not checks_pass:
        state = "inconclusive_numerical_checks_failed"
    result = {"hypothesis_id": plan["hypothesis_id"], "plan_id": plan["plan_id"],
              "plan_hash": _digest(plan), "result_type": "virtual", "claim_level": "model_prediction",
              "completed_at": now(), "decision": state,
              "claims": ["The frozen staged-loading hypothesis is " + state.replace("_", " ") + "."],
              "metrics": metrics, "primary_comparison": primary,
              "numerical_checks": {"passed": checks_pass, "appendix_reference_max_abs_state_error": reference,
                                   "tighter_solver_and_sampling_max_abs_metric_error": convergence},
              "sensitivity_scenarios": scenarios,
              "sensitivity_interpretation": "Deterministic assumed parameter scenarios, not biological replicates or confidence intervals.",
              "calibration_status": "Published equations and reference parameters; no independent measured volume-time curve fitted or validated.",
              "novelty_status": "known_reference",
              "limitations": plan["limitations"],
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}}
    return result, trajectories


def run(run_id):
    folder = run_path(run_id)
    h, plan = read(folder/"hypothesis.json"), read(folder/"plan.json")
    require(validate_plan(plan, h))
    if plan.get("design") != h.get("design") or plan.get("limitations") != h.get("limitations"):
        raise ValueError("Design or limitations changed after hypothesis freeze")
    validate_design(h)
    check_refs(plan["evidence_refs"] + plan["code_refs"])
    if plan["adapter"] != "cell_transport_v1":
        raise ValueError("Unknown adapter")
    write_new(folder/"started.json", {"started_at": now(), "plan_hash": _digest(plan)})
    result, trajectories = transport(plan)
    require(validate_conclusion(result, plan))
    write_new(folder/"result.json", result)
    write_new(folder/"trajectories.json", trajectories)
    files = ["hypothesis.json", "plan.json", "started.json", "result.json", "trajectories.json"]
    write_new(folder/"manifest.json", {"completed_at": now(), "files": {p: sha(folder/p) for p in files}})
    print(f"{run_id}: {result['decision']}; numerical checks passed={result['numerical_checks']['passed']}")


def verify(run_id):
    folder = run_path(run_id)
    manifest = read(folder/"manifest.json")
    expected = {"hypothesis.json", "plan.json", "started.json", "result.json", "trajectories.json"}
    if set(manifest["files"]) != expected:
        raise ValueError("Incomplete run manifest")
    for name, digest in manifest["files"].items():
        if sha(folder/name) != digest:
            raise ValueError(f"Run artifact changed: {name}")
    h, plan, result = (read(folder/name) for name in ("hypothesis.json", "plan.json", "result.json"))
    require(validate_plan(plan, h))
    require(validate_conclusion(result, plan))
    if plan.get("design") != h.get("design") or plan.get("limitations") != h.get("limitations"):
        raise ValueError("Design or limitations changed after hypothesis freeze")
    if read(folder/"started.json")["plan_hash"] != _digest(plan):
        raise ValueError("Start receipt does not match plan")
    check_refs(plan["evidence_refs"] + plan["code_refs"])
    print(f"{run_id}: artifact, evidence, current code hashes and conclusion schema verified")


def status():
    registry = read(REGISTRY)
    print(json.dumps({"hypotheses": [{"id": h["id"], "status": h["status"]} for h in registry["hypotheses"]],
                      "tracks": registry["tracks"],
                      "runs": [{"id": p.name, "state": "superseded_before_execution" if (p/"superseded.json").exists() else ("complete" if (p/"manifest.json").exists() else "frozen_or_incomplete")}
                               for p in sorted(RUNS.glob("*")) if p.is_dir()]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "freeze", "run", "verify"))
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--hypothesis", help="Registered hypothesis ID to freeze")
    args = parser.parse_args()
    if args.command == "status":
        status()
    elif not args.run_id:
        parser.error("run_id is required")
    else:
        try:
            if args.command == "freeze":
                freeze(args.run_id, args.hypothesis)
            else:
                {"run": run, "verify": verify}[args.command](args.run_id)
        except (ValueError, FileExistsError, FileNotFoundError) as exc:
            parser.exit(1, f"{exc}\n")
