"""Bounded, reconstructed liquid-water hydration MD; not an ice or cell assay.

Run in the isolated MD environment. Original experimental labels and model
artifacts are never inputs to fitting or simulation. See simulation/README.md.
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
from rdkit import Chem, rdBase
from rdkit.Chem import AllChem, Descriptors

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {
    "phe": {"id": "amino:line8", "name": "l-phenylalanine", "residue": "PHE",
            "smiles": "[NH3+][C@@H](Cc1ccccc1)C(=O)[O-]", "patches": ["NTER", "CTER"]},
    "gly": {"id": "amino:line14", "name": "l-glycine", "residue": "GLY",
            "smiles": "[NH3+]CC(=O)[O-]", "patches": ["GLYP", "CTER"]},
}
CUTOFFS = np.arange(0.2, 0.50001, 0.05)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def solute(code, seed):
    spec = CONTROLS[code]
    mol = Chem.AddHs(Chem.MolFromSmiles(spec["smiles"]))
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ValueError("Conformer embedding failed")
    if AllChem.MMFFOptimizeMolecule(mol, maxIters=1000) != 0:
        raise ValueError("Initial conformer optimization failed")
    top = app.Topology()
    res = top.addResidue(spec["residue"], top.addChain())
    atoms = [top.addAtom(f"{a.GetSymbol()}{a.GetIdx()+1}", app.element.Element.getByAtomicNumber(a.GetAtomicNum()), res) for a in mol.GetAtoms()]
    for bond in mol.GetBonds():
        top.addBond(atoms[bond.GetBeginAtomIdx()], atoms[bond.GetEndAtomIdx()])
    xyz = np.asarray(mol.GetConformer().GetPositions()) * 0.1
    return mol, top, xyz * unit.nanometer


def hydration(positions_nm, box_nm, solute_indices, water_oxygen_indices):
    """Periodic distances; count each water once, but retain all pairs for PDF."""
    xyz = np.asarray(positions_nm)
    box = np.asarray(box_nm)
    if box.shape != (3, 3) or not np.allclose(box, np.diag(np.diag(box)), atol=1e-8):
        raise ValueError("This pilot analysis requires an orthorhombic box")
    lengths = np.diag(box)
    if np.any(lengths <= 2 * CUTOFFS[-1]):
        raise ValueError("Box is too small for requested hydration cutoffs")
    delta = xyz[water_oxygen_indices, None, :] - xyz[None, solute_indices, :]
    delta -= lengths * np.rint(delta / lengths)
    dist = np.linalg.norm(delta, axis=2)
    nearest = dist.min(axis=1)
    counts = np.array([np.count_nonzero(nearest <= c) for c in CUTOFFS])
    hist, _ = np.histogram(dist, bins=100, range=(0, 0.5))
    if not hist.sum():
        raise ValueError("No water-solute distances in histogram range")
    return counts, hist / (hist.sum() * 0.005)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compound", choices=CONTROLS, required=True)
    p.add_argument("--seed", type=int, default=20260906)
    p.add_argument("--platform", choices=["CPU", "OpenCL", "CUDA", "Reference"], default="CPU")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--equilibration-ps", type=float, default=100)
    p.add_argument("--production-ps", type=float, default=1000)
    p.add_argument("--frames", type=int, default=100)
    p.add_argument("--max-wall-seconds", type=float, default=1800)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.seed <= 0 or args.seed >= 2**31 or args.frames < 2 or args.equilibration_ps <= 0 or args.production_ps <= 0 or args.max_wall_seconds <= 0:
        p.error("Positive duration/seed and at least two frames are required")
    dt_ps = 0.002
    equil_steps = round(args.equilibration_ps / dt_ps)
    production_steps = round(args.production_ps / dt_ps)
    if production_steps < args.frames or production_steps % args.frames:
        p.error("Production steps must be divisible by frames")
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    water_xml = ROOT / "simulation/tip4p-ice.xml"
    charmm_xml = Path(app.__file__).parent / "data/charmm36.xml"
    mol, top, positions = solute(args.compound, args.seed)
    solute_n = mol.GetNumAtoms()
    ff = app.ForceField("charmm36.xml", str(water_xml))
    # Graph matching must find the charged free-amino-acid terminal templates.
    vacuum = ff.createSystem(top, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
    net_charge = sum(float(f.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge))
                     for f in vacuum.getForces() if isinstance(f, mm.NonbondedForce)
                     for i in range(vacuum.getNumParticles()))
    if abs(net_charge) > 1e-6:
        raise ValueError("Expected a neutral zwitterion")
    modeller = app.Modeller(top, positions)
    modeller.addSolvent(ff, model="tip4pew", boxSize=mm.Vec3(4, 4, 4)*unit.nanometer, neutralize=False)
    # tip4pew selects only starting packing/geometry; the force-field XML defines TIP4P/Ice.
    modeller.addExtraParticles(ff)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.PME,
                             nonbondedCutoff=1.0*unit.nanometer, switchDistance=0.8*unit.nanometer,
                             constraints=app.HBonds, rigidWater=True, ewaldErrorTolerance=5e-4)
    integrator = mm.LangevinMiddleIntegrator(273*unit.kelvin, 1/unit.picosecond, dt_ps*unit.picoseconds)
    integrator.setRandomNumberSeed(args.seed)
    integrator.setConstraintTolerance(1e-6)
    properties = {"Threads": str(args.threads)} if args.platform == "CPU" else {"Precision": "mixed" if args.platform == "CUDA" else "single"} if args.platform in {"CUDA", "OpenCL"} else {}
    plat = mm.Platform.getPlatformByName(args.platform)
    simulation = app.Simulation(modeller.topology, system, integrator, plat, properties)
    simulation.context.setPositions(modeller.positions)
    simulation.context.computeVirtualSites()
    simulation.minimizeEnergy(maxIterations=1000)
    simulation.context.setVelocitiesToTemperature(273*unit.kelvin, args.seed)
    def step_bounded(steps):
        while steps:
            if time.monotonic() - started > args.max_wall_seconds:
                raise TimeoutError("Pilot wall-time limit reached")
            n = min(steps, 500)
            simulation.step(n)
            steps -= n
    step_bounded(equil_steps)
    atoms = list(modeller.topology.atoms())
    solute_indices = [a.index for a in atoms if a.residue.index == 0]
    water_oxygens = [a.index for a in atoms if a.residue.index != 0 and a.element == app.element.oxygen]
    if len(solute_indices) != solute_n or len(water_oxygens) < 1000:
        raise ValueError("Unexpected solute/solvent topology")
    masses_da = sum(system.getParticleMass(i).value_in_unit(unit.dalton) for i in range(system.getNumParticles()))
    # NVT, 4 nm cube: deliberately fixed density; not a pressure-equilibrated reproduction.
    coords, boxes, counts, histograms, energies, temperatures = [], [], [], [], [], []
    dof = 3*sum(system.getParticleMass(i).value_in_unit(unit.dalton)>0 for i in range(system.getNumParticles())) - system.getNumConstraints() - 3
    timed = time.monotonic()
    for frame in range(args.frames):
        step_bounded(production_steps // args.frames)
        state = simulation.context.getState(positions=True, energy=True)
        xyz = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        box = state.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)
        energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        ke = state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
        if not np.isfinite(xyz).all() or not np.isfinite(energy+ke):
            raise ValueError("Nonfinite simulation state")
        count, hist = hydration(xyz, box, solute_indices, water_oxygens)
        coords.append(xyz.astype(np.float32)); boxes.append(box)
        counts.append(count); histograms.append(hist); energies.append(energy)
        temperatures.append(2*ke/(dof*0.00831446261815324))
    elapsed = time.monotonic()-timed
    np.savez_compressed(out/"trajectory.npz", positions_nm=coords, boxes_nm=boxes,
                        solute_indices=solute_indices, water_oxygen_indices=water_oxygens,
                        hydration_counts=counts, pair_histograms=histograms,
                        potential_kj_mol=energies, temperature_K=temperatures)
    (out/"system.xml").write_text(mm.XmlSerializer.serialize(system))
    (out/"integrator.xml").write_text(mm.XmlSerializer.serialize(integrator))
    with (out/"topology.pdb").open("w") as handle:
        app.PDBFile.writeFile(modeller.topology, state.getPositions(), handle)
    simulation.saveState(str(out/"final-state.xml"))
    counts = np.asarray(counts)
    block_means = [v.mean(axis=0).tolist() for v in np.array_split(counts, min(4, len(counts)))]
    result = {"status": "Reconstructed hydration feasibility pilot; no ice, cell, new experimental labels or efficacy validation",
              "control": CONTROLS[args.compound], "seed": args.seed,
              "state_assumption": "Explicit free amino-acid zwitterion; source CSV neutral SMILES preserved separately. Original per-compound topology unavailable.",
              "configuration": {"forcefield": "OpenMM charmm36.xml (2015 distribution)", "water": "TIP4P/Ice local XML",
                  "ensemble": "NVT", "temperature_K": 273, "box_nm": 4, "salt_added": False,
                  "solute_concentration_mM": 1000/(6.02214076e23*64e-24),
                  "density_g_ml": masses_da*1.66053906660e-24/(64e-21),
                  "time_step_ps": dt_ps, "equilibration_ps": equil_steps*dt_ps,
                  "production_ps": production_steps*dt_ps, "frames": args.frames,
                  "net_solute_charge_e": net_charge, "particles": system.getNumParticles(), "water_molecules": len(water_oxygens),
                  "platform": args.platform, "platform_properties": properties},
              "versions": {"python": platform.python_version(), "openmm": mm.__version__, "numpy": np.__version__, "rdkit": rdBase.rdkitVersion},
              "hashes": {"script": sha(__file__), "water_xml": sha(water_xml), "charmm_xml": sha(charmm_xml),
                         "trajectory": sha(out/"trajectory.npz"), "system": sha(out/"system.xml")},
              "timing": {"production_wall_seconds": elapsed, "total_wall_seconds": time.monotonic()-started,
                         "production_ns_per_day": args.production_ps/1000/elapsed*86400},
              "observables": {"cutoffs_nm": CUTOFFS.tolist(), "mean_hydration_counts": counts.mean(axis=0).tolist(),
                  "frame_sd_hydration_counts": counts.std(axis=0, ddof=1).tolist(),
                  "four_time_block_means": block_means,
                  "mean_hydration_per_molecular_weight": (counts.mean(axis=0)/Descriptors.MolWt(mol)).tolist(),
                  "pair_histogram_bin_width_nm": 0.005, "mean_pair_histogram_density": np.mean(histograms, axis=0).tolist(),
                  "mean_temperature_K": float(np.mean(temperatures)), "min_potential_kj_mol": min(energies), "max_potential_kj_mol": max(energies)},
              "limits": ["Frames are correlated; frame SD and block means are diagnostics, not independent replicate confidence intervals.",
                         "No barostat or ice interface; fixed-density liquid hydration is not a measure of ice inhibition.",
                         "Shorter than published 20 ns; original state/topology and several MD settings are unresolved.",
                         "PHE and GLY differ in molecular size; two controls cannot validate a hydration-activity relationship."]}
    write_json(out/"result.json", result)
    print(json.dumps({"compound": args.compound, "seed": args.seed, "output": str(out), "ns_per_day": result["timing"]["production_ns_per_day"], "temperature_K": result["observables"]["mean_temperature_K"]}), flush=True)


if __name__ == "__main__":
    main()
