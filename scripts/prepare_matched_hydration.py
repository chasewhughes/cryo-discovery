"""Prepare reproducible leucine/isoleucine CHARMM36/TIP4P-Ice NPT parents.

This command only builds, minimizes, and serializes a solvated starting state;
it performs no equilibration or production sampling.  It is intentionally
separate from the Phase 12 extension runner because these are newly prepared
conformations rather than branches from an existing state.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import openmm as mm
from openmm import app, unit
from rdkit import Chem, rdBase
from rdkit.Chem import AllChem, rdMolDescriptors

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {
    "leu": {"name": "l-leucine", "residue": "LEU",
            "smiles": "CC(C)C[C@H]([NH3+])C(=O)[O-]", "id": "amino:line4"},
    "ile": {"name": "l-isoleucine", "residue": "ILE",
            "smiles": "CC[C@H](C)[C@H]([NH3+])C(=O)[O-]", "id": "amino:line5"},
}
DT_PS = 0.002
DESCRIPTOR_VERSION = "cryo-nearest-water-v1"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def build_solute(code, seed):
    spec = CONTROLS[code]
    mol = Chem.AddHs(Chem.MolFromSmiles(spec["smiles"]))
    Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True, includeCIP=True)
    expected = 1 if code == "leu" else 2
    if len(centers) != expected or any(label != "S" for _, label in centers):
        raise ValueError(f"Unexpected {code} stereochemistry/CIP: {centers}")
    if Chem.GetFormalCharge(mol) != 0:
        raise ValueError("Matched control must be net neutral")
    params = AllChem.ETKDGv3(); params.randomSeed = int(seed)
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ValueError("Conformer embedding failed")
    if AllChem.MMFFOptimizeMolecule(mol, maxIters=1000) != 0:
        raise ValueError("Initial conformer optimization failed")
    Chem.AssignAtomChiralTagsFromStructure(mol, confId=0, replaceExistingTags=True)
    centers3d = Chem.FindMolChiralCenters(mol, includeUnassigned=True, includeCIP=True)
    if any(label != "S" for _, label in centers3d): raise ValueError(f"3D stereochemistry changed: {centers3d}")
    top = app.Topology(); residue = top.addResidue(spec["residue"], top.addChain())
    atoms = [top.addAtom(f"{a.GetSymbol()}{a.GetIdx()+1}",
                         app.element.Element.getByAtomicNumber(a.GetAtomicNum()), residue)
             for a in mol.GetAtoms()]
    for bond in mol.GetBonds(): top.addBond(atoms[bond.GetBeginAtomIdx()], atoms[bond.GetEndAtomIdx()])
    xyz = np.asarray(mol.GetConformer().GetPositions()) * 0.1 * unit.nanometer
    return mol, top, xyz


def validate_system(system, topology, code, water_count):
    atoms = list(topology.atoms())
    if system.getNumParticles() != len(atoms): raise ValueError("System/topology particle mismatch")
    sol = [a for a in atoms if a.residue.index == 0]
    wat = [a for a in atoms if a.residue.index != 0 and a.element == app.element.oxygen]
    if len(wat) != water_count or len(wat) < 1000: raise ValueError("Unexpected fixed water count")
    if len(sol) != Chem.MolFromSmiles(CONTROLS[code]["smiles"]).GetNumAtoms() + sum(1 for a in Chem.AddHs(Chem.MolFromSmiles(CONTROLS[code]["smiles"])).GetAtoms() if a.GetSymbol() == "H"):
        raise ValueError("Unexpected solute atom count")
    bar = [system.getForce(i) for i in range(system.getNumForces()) if isinstance(system.getForce(i), mm.MonteCarloBarostat)]
    if len(bar) != 1 or bar[0].getFrequency() != 25: raise ValueError("NPT barostat mismatch")
    return sol, wat


def prepare(code, seed, water_count, output, platform_name="OpenCL"):
    if code not in CONTROLS or seed <= 0 or water_count < 1000: raise ValueError("Invalid preparation inputs")
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    mol, top, positions = build_solute(code, seed)
    water_xml = ROOT / "simulation/tip4p-ice.xml"
    ff = app.ForceField("charmm36.xml", str(water_xml))
    vacuum = ff.createSystem(top, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
    net_charge = sum(float(f.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge))
                     for f in vacuum.getForces() if isinstance(f, mm.NonbondedForce)
                     for i in range(vacuum.getNumParticles()))
    if abs(net_charge) > 1e-6: raise ValueError("Expected neutral zwitterion partial charge")
    modeller = app.Modeller(top, positions)
    # numAdded fixes solvent count and total mass; NPT volume sets concentration. With
    # no explicit boxSize, OpenMM chooses a cubic box that fits that count.
    modeller.addSolvent(ff, model="tip4pew", numAdded=water_count, neutralize=False)
    box0 = modeller.topology.getPeriodicBoxVectors()
    box_lengths = [box0[i][i].value_in_unit(unit.nanometer) for i in range(3)]
    if not np.allclose(box_lengths, box_lengths[0], atol=1e-6):
        raise ValueError("Fixed-count solvent box is not cubic")
    modeller.addExtraParticles(ff)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.PME,
        nonbondedCutoff=1 * unit.nanometer, switchDistance=.8 * unit.nanometer,
        constraints=app.HBonds, rigidWater=True, ewaldErrorTolerance=5e-4)
    barostat = mm.MonteCarloBarostat(1 * unit.bar, 273 * unit.kelvin, 25)
    barostat.setRandomNumberSeed(seed + 100000); system.addForce(barostat)
    integrator = mm.LangevinMiddleIntegrator(273 * unit.kelvin, 1 / unit.picosecond,
                                               DT_PS * unit.picosecond)
    integrator.setRandomNumberSeed(seed); integrator.setConstraintTolerance(1e-6)
    props = {"Precision": "single"} if platform_name == "OpenCL" else {"Precision": "mixed"} if platform_name == "CUDA" else {"Threads": "2"}
    sim = app.Simulation(modeller.topology, system, integrator,
                         mm.Platform.getPlatformByName(platform_name), props)
    sim.context.setPositions(modeller.positions); sim.context.computeVirtualSites()
    sim.minimizeEnergy(maxIterations=1000); sim.context.setVelocitiesToTemperature(273 * unit.kelvin, seed)
    state = sim.context.getState(positions=True, velocities=True, energy=True)
    sol, wat = validate_system(system, modeller.topology, code, water_count)
    xyz = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    box = state.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)
    lengths = np.diag(box)
    # TIP4P/Ice geometry is constrained; this catches malformed solvent setup.
    water_atoms = [a.index for a in modeller.topology.atoms() if a.residue.index != 0]
    if len(water_atoms) != water_count * 4: raise ValueError("Unexpected TIP4P atom count")
    w = np.asarray(water_atoms).reshape(water_count, 4)
    delta = xyz[w[:, 1:3]] - xyz[w[:, :1]]
    delta -= lengths * np.rint(delta / lengths)
    oh_error = float(np.max(np.abs(np.linalg.norm(delta, axis=2) - .09572)))
    delta_m = xyz[w[:, 3]] - xyz[w[:, 0]]
    delta_m -= lengths * np.rint(delta_m / lengths)
    om_error = float(np.max(np.abs(np.linalg.norm(delta_m, axis=1) - .01577)))
    energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    if not np.isfinite(xyz).all() or not np.isfinite([energy, oh_error, om_error]).all(): raise ValueError("Nonfinite minimized state")
    if oh_error > 5e-6 or om_error > 5e-6: raise ValueError("TIP4P/Ice water geometry out of bounds")
    (out / "system.xml").write_text(mm.XmlSerializer.serialize(system))
    (out / "integrator.xml").write_text(mm.XmlSerializer.serialize(integrator))
    sim.saveState(str(out / "final-state.xml"))
    modeller.topology.setPeriodicBoxVectors(state.getPeriodicBoxVectors())
    with (out / "topology-final-box.pdb").open("w") as f: app.PDBFile.writeFile(modeller.topology, state.getPositions(), f)
    controls = json.loads((ROOT / "data/phase11/deferred-controls.json").read_text())
    hashes = {"script": sha(__file__), "descriptor": sha(ROOT / "scripts/hydration_descriptor.py"),
              "water_xml": sha(water_xml), "charmm_xml": sha(Path(app.__file__).parent / "data/charmm36.xml"),
              "deferred_controls": sha(ROOT / "data/phase11/deferred-controls.json")}
    hashes.update({n: sha(out / n) for n in ("system.xml", "integrator.xml", "final-state.xml", "topology-final-box.pdb")})
    hashes.update({"system": hashes["system.xml"], "integrator": hashes["integrator.xml"], "final_state": hashes["final-state.xml"], "topology": hashes["topology-final-box.pdb"]})
    neighbors = [{"index": int(a.GetIdx()), "symbol": a.GetSymbol(), "neighbors": sorted(int(n.GetIdx()) for n in a.GetNeighbors())} for a in mol.GetAtoms()]
    masses_da = sum(system.getParticleMass(i).value_in_unit(unit.dalton) for i in range(system.getNumParticles()))
    result = {"status": "Preparation only; no equilibration, production, or efficacy validation",
        "preparation_only": True, "descriptor_version": DESCRIPTOR_VERSION, "compound": code, "control": CONTROLS[code], "seed": seed,
        "source_smiles": CONTROLS[code]["smiles"],
        "identity": {"formula": rdMolDescriptors.CalcMolFormula(mol), "formal_charge": Chem.GetFormalCharge(mol), "net_partial_charge_e": net_charge, "stereochemistry_cip": Chem.FindMolChiralCenters(mol, includeUnassigned=True, includeCIP=True), "atom_neighbors": neighbors},
        "stereochemistry": {"expected_cip": "S" if code == "leu" else "2S,3S", "rdkit_centers": Chem.FindMolChiralCenters(mol, includeUnassigned=True, includeCIP=True),
            "atom_map": [{"index": int(a.GetIdx()), "symbol": a.GetSymbol(), "map": int(a.GetAtomMapNum())} for a in mol.GetAtoms()]},
        "configuration": {"ensemble": "NPT", "pressure_bar": 1, "barostat_interval_steps": 25,
            "barostat_seed": seed + 100000, "temperature_K": 273, "time_step_ps": DT_PS,
            "friction_per_ps": 1, "constraint_tolerance": 1e-6,
            "water_molecules": len(wat), "solute_concentration_mM": 1000 / (6.02214076e23 * np.prod(box_lengths) * 1e-24), "mass_da": masses_da,
            "box_nm": box_lengths[0],
            "platform": platform_name, "platform_properties": props},
        "minimized_state": {"time_ps": state.getTime().value_in_unit(unit.picosecond),
            "potential_kj_mol": energy,
            "water_OH_max_error_nm": oh_error, "water_OM_max_error_nm": om_error},
        "versions": {"python": platform.python_version(), "openmm": mm.__version__, "numpy": np.__version__, "rdkit": rdBase.rdkitVersion},
        "hashes": hashes, "limits": ["Reconstructed free-amino-acid zwitterion state; source assay microstate is not verified.", "Preparation only; no efficacy labels or MD production."],
        "source_control": {"id": CONTROLS[code]["id"], "deferred_controls_status": controls["status"]}}
    write_json(out / "result.json", result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compound", choices=CONTROLS, required=True); p.add_argument("--seed", type=int, required=True)
    p.add_argument("--water-molecules", type=int, default=2070); p.add_argument("--platform", choices=["OpenCL", "CUDA", "CPU"], default="OpenCL")
    p.add_argument("--output", type=Path, required=True); args = p.parse_args(argv)
    prepare(args.compound, args.seed, args.water_molecules, args.output, args.platform)


if __name__ == "__main__": main()
