"""Small, fail-closed validation helpers for frozen research hypotheses.

Example schema::

    hypothesis = {"id": "iri-2fa", "statement": "2FA lowers MGS",
      "model": "ridge", "domain": "22mM PBS splat assay",
      "endpoints": ["percent MGS"], "controls": ["vehicle"],
      "acceptance_criteria": {"mae_mgs_points": 20.0},
      "evidence_refs": [{"source_path": "data/raw/x.csv",
                         "sha256": "<64 hex>"}],
      "status": "known_reference"}
    plan = {**hypothesis, "plan_id": "plan-1",
      "hypothesis_id": "iri-2fa", "hypothesis_hash": "<sha256>",
      "frozen_at": "2026-09-06T12:00:00Z"}
    result = {"hypothesis_id": "iri-2fa", "plan_id": "plan-1",
      "plan_hash": "<sha256>", "result_type": "virtual",
      "claims": ["out-of-fold prediction"]}

Functions return a list of human-readable errors; callers may raise
``ValueError("; ".join(errors))`` when validation is a hard gate.
"""

import hashlib
import json
import math
import re

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,63}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
STATUSES = {"independently_unassessed", "known_reference", "prospective_hypothesis"}
VIRTUAL_CLAIM_LEVELS = {"model_prediction", "numerical_verification", "reference_reproduction"}
MEASUREMENT_CLAIM_LEVELS = {"experimental_observation"}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _finite(value):
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


def _base_errors(record, label):
    errors = []
    if not isinstance(record, dict):
        return [f"{label} must be an object"]
    if not _text(record.get("id")) or not ID_RE.fullmatch(record.get("id", "")):
        errors.append(f"{label}.id must be a stable 3-64 character identifier")
    if not _text(record.get("statement")):
        errors.append(f"{label}.statement is required")
    for field in ("model", "domain"):
        if not _text(record.get(field)):
            errors.append(f"{label}.{field} is required")
    for field in ("endpoints", "controls"):
        value = record.get(field)
        if not isinstance(value, list) or not value or not all(_text(x) for x in value):
            errors.append(f"{label}.{field} must be a non-empty list of text")
    criteria = record.get("acceptance_criteria")
    if not isinstance(criteria, (dict, list)) or not criteria:
        errors.append(f"{label}.acceptance_criteria is required")
    elif not _finite(criteria):
        errors.append(f"{label}.acceptance_criteria contains non-finite values")
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{label}.evidence_refs is required")
    else:
        for i, ref in enumerate(refs):
            if not isinstance(ref, dict) or not _text(ref.get("source_path")):
                errors.append(f"{label}.evidence_refs[{i}] needs source_path")
            if not isinstance(ref, dict) or not _sha(ref.get("sha256")):
                errors.append(f"{label}.evidence_refs[{i}] needs a 64-hex sha256")
    if record.get("status") not in STATUSES:
        errors.append(f"{label}.status must be one of {sorted(STATUSES)}")
    return errors


def validate_hypothesis(record):
    """Return schema errors for a hypothesis record."""
    return _base_errors(record, "hypothesis")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_plan(plan, hypothesis):
    """Return errors ensuring a plan freezes the supplied hypothesis verbatim."""
    errors = _base_errors(plan, "plan")
    errors.extend(validate_hypothesis(hypothesis))
    if not isinstance(plan, dict) or not isinstance(hypothesis, dict):
        return errors
    if not _text(plan.get("plan_id")) or not ID_RE.fullmatch(plan.get("plan_id", "")):
        errors.append("plan.plan_id must be a stable identifier")
    if plan.get("hypothesis_id") != hypothesis.get("id"):
        errors.append("plan.hypothesis_id does not match hypothesis.id")
    if not _text(plan.get("frozen_at")):
        errors.append("plan.frozen_at is required")
    try:
        expected = _digest(hypothesis)
    except (TypeError, ValueError):
        errors.append("hypothesis cannot be canonically hashed")
        expected = None
    if plan.get("hypothesis_hash") != expected:
        errors.append("plan.hypothesis_hash does not match canonical hypothesis")
    for field in ("statement", "model", "domain", "endpoints", "controls", "acceptance_criteria", "evidence_refs", "status"):
        if plan.get(field) != hypothesis.get(field):
            errors.append(f"plan.{field} differs from frozen hypothesis")
    return errors


def validate_conclusion(result, plan):
    """Return errors for a result and prohibit unsupported virtual claims."""
    errors = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if not isinstance(plan, dict):
        return ["plan must be an object"]
    if result.get("hypothesis_id") != plan.get("hypothesis_id"):
        errors.append("result.hypothesis_id does not match plan")
    if result.get("plan_id") != plan.get("plan_id"):
        errors.append("result.plan_id does not match plan")
    try:
        expected_plan_hash = _digest(plan)
    except (TypeError, ValueError):
        errors.append("plan cannot be canonically hashed")
        expected_plan_hash = None
    if result.get("plan_hash") != expected_plan_hash:
        errors.append("result.plan_hash does not match canonical frozen plan")
    if result.get("result_type") not in {"virtual", "measurement"}:
        errors.append("result.result_type must be virtual or measurement")
    claims = result.get("claims", [])
    if not isinstance(claims, list) or not claims or not all(_text(c) for c in claims):
        errors.append("result.claims must be a non-empty list of text")
    claim_level = result.get("claim_level")
    if result.get("result_type") == "virtual" and claim_level not in VIRTUAL_CLAIM_LEVELS:
        errors.append("virtual result claim_level must be model_prediction, numerical_verification, or reference_reproduction")
    if result.get("result_type") == "measurement" and claim_level not in MEASUREMENT_CLAIM_LEVELS:
        errors.append("measurement result claim_level must be experimental_observation")
    if claim_level == "established_novelty":
        errors.append("established_novelty requires a separate review and is never a direct conclusion")
    metrics = result.get("metrics")
    if metrics is not None and not _finite(metrics):
        errors.append("result.metrics contains non-finite values")
    refs = result.get("measurement_refs")
    if refs is not None:
        if not isinstance(refs, list) or not refs:
            errors.append("result.measurement_refs must be a non-empty list")
        else:
            for i, ref in enumerate(refs):
                if not isinstance(ref, dict) or not _text(ref.get("source_path")) or not _sha(ref.get("sha256")):
                    errors.append(f"result.measurement_refs[{i}] needs source_path and a 64-hex sha256")
    if result.get("result_type") == "virtual":
        forbidden = ("experimental efficacy", "experimental efficacy established", "synergy", "novelty established", "novel")
        for claim in claims if isinstance(claims, list) else []:
            if any(term in claim.lower() for term in forbidden):
                errors.append("virtual results cannot claim experimental efficacy, synergy, or established novelty")
    if result.get("result_type") == "measurement" and not result.get("measurement_refs"):
        errors.append("measurement results require measurement_refs")
    return errors
