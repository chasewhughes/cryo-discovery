"""Run a clean Phase 12 extension from a saved Phase 11 OpenMM state.

The parent state is loaded without changing its physical model.  RNG seeds are
set on the deserialized integrator and barostat before the OpenMM Context is
created, then the saved positions and velocities are restored and the clock is
reset to zero.  The equilibration interval is excluded from reported frames.
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import openmm as mm
from openmm import app, unit

try:
    from .hydration_descriptor import VERSION, CUTOFFS, EDGES, measure
except ImportError:
    from hydration_descriptor import VERSION, CUTOFFS, EDGES, measure


DT_PS = 0.002
TEMP_K = 273.0
REQUIRED_INPUTS = (
    "system.xml", "integrator.xml", "final-state.xml",
    "topology-final-box.pdb", "result.json",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _parent_config(parent):
    try:
        return parent["configuration"]
    except (KeyError, TypeError):
        raise ValueError("Parent result lacks configuration")


def validate_parent(parent, system, integrator):
    config = _parent_config(parent)
    if parent.get("descriptor_version") != VERSION:
        raise ValueError("Parent descriptor does not match " + VERSION)
    if config.get("temperature_K") != TEMP_K:
        raise ValueError("Parent temperature must be 273 K")
    if not np.isclose(config.get("time_step_ps"), DT_PS):
        raise ValueError("Parent timestep must be 0.002 ps")
    ensemble = config.get("ensemble")
    if ensemble not in {"NVT", "NPT"}:
        raise ValueError("Parent ensemble must be NVT or NPT")
    if not isinstance(integrator, mm.LangevinMiddleIntegrator):
        raise ValueError("Parent integrator must be LangevinMiddleIntegrator")
    barostats = [system.getForce(i) for i in range(system.getNumForces())
                 if isinstance(system.getForce(i), mm.MonteCarloBarostat)]
    if (ensemble == "NPT") != (len(barostats) == 1):
        raise ValueError("Parent ensemble and barostat do not align")
    if ensemble == "NVT" and barostats:
        raise ValueError("NVT parent must not contain a barostat")
    if barostats:
        baro = barostats[0]
        if baro.getFrequency() != config.get("barostat_interval_steps"):
            raise ValueError("Parent barostat interval does not match result")
        if not np.isclose(baro.getDefaultPressure().value_in_unit(unit.bar),
                          config.get("pressure_bar")):
            raise ValueError("Parent barostat pressure does not match result")
        if not np.isclose(baro.getDefaultTemperature().value_in_unit(unit.kelvin), TEMP_K):
            raise ValueError("Parent barostat temperature must be 273 K")
    if hasattr(integrator, "getStepSize") and not np.isclose(
            integrator.getStepSize().value_in_unit(unit.picosecond), DT_PS):
        raise ValueError("Parent integrator timestep must be 0.002 ps")
    if hasattr(integrator, "getTemperature") and not np.isclose(
            integrator.getTemperature().value_in_unit(unit.kelvin), TEMP_K):
        raise ValueError("Parent integrator temperature must be 273 K")
    if not np.isclose(integrator.getFriction().value_in_unit(unit.picosecond ** -1), 1.0):
        raise ValueError("Parent Langevin friction must be 1/ps")
    if not np.isclose(integrator.getConstraintTolerance(), 1e-6):
        raise ValueError("Parent constraint tolerance must be 1e-6")
    return ensemble


def _set_rngs(system, integrator, seed):
    # These calls intentionally happen before Simulation creates its Context.
    if hasattr(integrator, "setRandomNumberSeed"):
        integrator.setRandomNumberSeed(seed)
    for i in range(system.getNumForces()):
        force = system.getForce(i)
        if isinstance(force, mm.MonteCarloBarostat):
            force.setRandomNumberSeed(seed + 100000)


def verify_restored_state(saved_state, restored_state):
    """Verify restoration within four float32 rounding units at coordinate/box scale."""
    source_positions = saved_state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    restored_positions = restored_state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    rounding = 4 * np.finfo(np.float32).eps
    box_scale = max(1., float(np.abs(saved_state.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)).max()))
    position_error = np.abs(source_positions-restored_positions)
    if not np.isfinite(restored_positions).all() or np.any(position_error > rounding*np.maximum(box_scale, np.abs(source_positions))):
        raise ValueError("Saved positions were not restored")
    try:
        source_velocities = saved_state.getVelocities(asNumpy=True).value_in_unit(unit.nanometer / unit.picosecond)
        restored_velocities = restored_state.getVelocities(asNumpy=True).value_in_unit(unit.nanometer / unit.picosecond)
    except Exception as exc:
        raise ValueError("Saved state lacks velocities") from exc
    velocity_error = np.abs(source_velocities-restored_velocities)
    if not np.isfinite(restored_velocities).all() or np.any(velocity_error > rounding*np.maximum(1, np.abs(source_velocities))):
        raise ValueError("Saved velocities were not restored")
    return {'max_position_error_nm':float(position_error.max()),
            'max_velocity_error_nm_ps':float(velocity_error.max()),
            'relative_rounding_bound':float(rounding),
            'position_box_scale_nm':box_scale,
            'bound':'Position: 4 * float32 epsilon * max(1, box scale, absolute source coordinate); velocity: 4 * epsilon * max(1, absolute source velocity). Not bitwise equality.'}


def _props(name):
    if name == "CPU":
        return {"Threads": "2"}
    if name in {"CUDA", "OpenCL"}:
        return {"Precision": "mixed" if name == "CUDA" else "single"}
    return {}


def run(args):
    input_path = Path(args.inputPATH)
    paths = {name: input_path / name for name in REQUIRED_INPUTS}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError("Missing input file(s): " + ", ".join(missing))
    out = Path(args.outputPATH)
    if out.exists():
        raise ValueError("Output path already exists: " + str(out))
    out.mkdir(parents=True)
    started = time.monotonic()
    parent = json.loads(paths["result.json"].read_text())
    system = mm.XmlSerializer.deserialize(paths["system.xml"].read_text())
    integrator = mm.XmlSerializer.deserialize(paths["integrator.xml"].read_text())
    saved_state = mm.XmlSerializer.deserialize(paths["final-state.xml"].read_text())
    ensemble = validate_parent(parent, system, integrator)
    parent_system_hash = parent.get("hashes", {}).get("system")
    if not parent_system_hash:
        raise ValueError("Parent result lacks required system hash")
    if parent_system_hash != sha(paths["system.xml"]):
        raise ValueError("Parent system hash does not match system.xml")
    seed = args.seedINT
    _set_rngs(system, integrator, seed)
    pdb = app.PDBFile(str(paths["topology-final-box.pdb"]))
    if system.getNumParticles() != sum(1 for _ in pdb.topology.atoms()):
        raise ValueError("System and topology particle counts do not match")
    props = _props(args.platform)
    simulation = app.Simulation(pdb.topology, system, integrator,
                                mm.Platform.getPlatformByName(args.platform), props)
    source_time_ps = saved_state.getTime().value_in_unit(unit.picosecond)
    simulation.loadState(str(paths["final-state.xml"]))
    restored = simulation.context.getState(positions=True, velocities=True)
    restoration_check = verify_restored_state(saved_state, restored)
    simulation.context.setTime(0 * unit.picosecond)
    simulation.currentStep = 0
    # The saved state is the starting point; loading it retains positions and velocities.
    atoms = list(pdb.topology.atoms())
    sol = [a.index for a in atoms if a.residue.index == 0]
    wat = [a.index for a in atoms if a.residue.index != 0 and a.element == app.element.oxygen]
    if not sol or len(wat) < 1000:
        raise ValueError("Unexpected Phase 11 topology selections")
    masses = sum(system.getParticleMass(i).value_in_unit(unit.dalton)
                  for i in range(system.getNumParticles()))
    dof = 3 * sum(system.getParticleMass(i).value_in_unit(unit.dalton) > 0
                  for i in range(system.getNumParticles())) - system.getNumConstraints() - 3
    eq_steps = round(args.equilibration_ps / DT_PS)
    prod_steps = round(args.production_ps / DT_PS)

    def step(n):
        while n:
            if time.monotonic() - started > args.max_wall_seconds:
                raise TimeoutError("Extension job time limit reached")
            chunk = min(n, 500)
            simulation.step(chunk)
            n -= chunk

    def snapshot():
        state = simulation.context.getState(positions=True, energy=True)
        xyz = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        box = state.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)
        energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        temperature = 2 * state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole) / (dof * .00831446261815324)
        density = masses * 1.66053906660e-3 / np.linalg.det(box)
        if not np.isfinite(xyz).all() or not np.isfinite([energy, temperature, density]).all():
            raise ValueError("Nonfinite state")
        return state, xyz, box, energy, temperature, density

    # Equilibration is deliberately omitted from all production arrays/statistics.
    step(eq_steps)
    coords, boxes, counts, pdfs, energies, temps, densities, pairs = [], [], [], [], [], [], [], []
    production_started = time.monotonic()
    for _ in range(args.frames):
        step(prod_steps // args.frames)
        state, xyz, box, energy, temp, density = snapshot()
        count, pdf = measure(xyz, box, sol, wat)
        coords.append(xyz.astype(np.float32)); boxes.append(box)
        counts.append(count); pdfs.append(pdf); energies.append(energy); temps.append(temp); densities.append(density)
        # Phase 11's pair histogram is retained for compatible downstream analysis.
        delta = xyz[wat, None, :] - xyz[None, sol, :]
        lengths = np.diag(box); delta -= lengths * np.rint(delta / lengths)
        distances = np.linalg.norm(delta, axis=2)
        pairs.append(np.histogram(distances, bins=100, range=(0, .5))[0] /
                     (np.count_nonzero(distances <= .5) * .005))
    elapsed = time.monotonic() - production_started
    np.savez_compressed(out / "trajectory.npz", positions_nm=coords, boxes_nm=boxes,
        solute_indices=sol, water_oxygen_indices=wat, hydration_counts=counts,
        nearest_pdf=pdfs, pair_histograms=pairs, potential_kj_mol=energies,
        temperature_K=temps, density_g_ml=densities,
        production_time_ps=np.arange(1, args.frames + 1) * prod_steps * DT_PS / args.frames)
    (out / "system.xml").write_text(mm.XmlSerializer.serialize(system))
    (out / "integrator.xml").write_text(mm.XmlSerializer.serialize(integrator))
    final_state, _, _, _, _, _ = snapshot()
    pdb.topology.setPeriodicBoxVectors(final_state.getPeriodicBoxVectors())
    with (out / "topology-final-box.pdb").open("w") as handle:
        app.PDBFile.writeFile(pdb.topology, final_state.getPositions(), handle)
    simulation.saveState(str(out / "final-state.xml"))
    input_hashes = {name: sha(path) for name, path in paths.items()}
    hashes = dict(input_hashes)
    hashes.update({"script": sha(__file__), "descriptor": sha(Path(__file__).with_name("hydration_descriptor.py"))})
    output_hashes = {name: sha(out / name) for name in ("system.xml", "integrator.xml", "final-state.xml", "topology-final-box.pdb", "trajectory.npz")}
    # Keep Phase 11's convenient top-level names and also expose explicit groups.
    hashes.update({"trajectory": output_hashes["trajectory.npz"], "system": output_hashes["system.xml"],
                   "integrator": output_hashes["integrator.xml"], "final_state": output_hashes["final-state.xml"],
                   "topology": output_hashes["topology-final-box.pdb"]})
    result = {
        "status": "Phase 12 stochastic branch extension; no experimental efficacy validation",
        "phase": 12, "compound": parent.get("compound"), "control": parent.get("control"),
        "seed": seed, "source_state_time_ps": source_time_ps, "descriptor_version": VERSION,
        "parent_seed": parent.get("seed"),
        "restoration_check": restoration_check,
        "branching": {"mode": "stochastic_branch", "retained_positions": True,
            "retained_velocities": True, "new_integrator_rng": seed,
            "new_barostat_rng": seed + 100000 if ensemble == "NPT" else None,
            "clock_reset": True},
        "configuration": {"ensemble": ensemble, "pressure_bar": 1 if ensemble == "NPT" else None,
            "barostat_interval_steps": 25 if ensemble == "NPT" else None,
            "barostat_seed": seed + 100000 if ensemble == "NPT" else None,
            "temperature_K": TEMP_K, "equilibration_ps": eq_steps * DT_PS,
            "production_ps": prod_steps * DT_PS, "frames": args.frames, "time_step_ps": DT_PS,
            "platform": args.platform, "platform_properties": props, "water_molecules": len(wat),
            "mass_da": masses},
        "observables": {"cutoffs_nm": CUTOFFS.tolist(), "histogram_edges_nm": EDGES.tolist(),
            "mean_hydration_counts": np.mean(counts, axis=0).tolist(),
            "mean_nearest_pdf": np.mean(pdfs, axis=0).tolist(),
            "mean_density_g_ml": float(np.mean(densities)), "mean_temperature_K": float(np.mean(temps))},
        "timing": {"production_wall_seconds": elapsed, "total_wall_seconds": time.monotonic() - started},
        "versions": {"python": platform.python_version(), "openmm": mm.__version__, "numpy": np.__version__},
        "hashes": hashes,
        "input_hashes": input_hashes, "output_hashes": output_hashes,
        "limits": ["Equilibration frames are excluded from production observables.",
            "This is a stochastic branch from the saved state, not an exact continuation.",
            "No experimental efficacy validation."],
    }
    write_json(out / "result.json", result)
    print(f"{parent.get('compound')} {ensemble} {seed}: completed {prod_steps * DT_PS / 1000:g} ns", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputPATH", "--input-path", "--input", dest="inputPATH", required=True)
    parser.add_argument("--seedINT", "--seed", dest="seedINT", type=int, required=True)
    parser.add_argument("--platform", choices=["CUDA", "OpenCL", "CPU"], default="CUDA")
    parser.add_argument("--equilibration-ps", type=float, default=100)
    parser.add_argument("--production-ps", type=float, default=10000)
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--max-wall-seconds", type=float, default=1800)
    parser.add_argument("--outputPATH", "--output-path", "--output", dest="outputPATH", required=True)
    args = parser.parse_args(argv)
    if not 0 < args.seedINT < 2**31 - 100000:
        parser.error("seedINT must be nonzero and below 2**31-100000")
    numeric = (args.equilibration_ps, args.production_ps, args.max_wall_seconds)
    if not all(np.isfinite(numeric)) or min(numeric) <= 0:
        parser.error("durations and max-wall-seconds must be positive")
    eq = round(args.equilibration_ps / DT_PS); prod = round(args.production_ps / DT_PS)
    if args.frames <= 0 or eq < 1 or prod < args.frames or prod % args.frames:
        parser.error("production steps must divide evenly into frames")
    run(args)


if __name__ == "__main__":
    main()
