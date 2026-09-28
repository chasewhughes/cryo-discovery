"""Matched NVT/NPT hydration stability study; no activity labels or fitting."""
import argparse
import platform
import time
from pathlib import Path

import numpy as np
import openmm as mm
from openmm import app, unit
from rdkit import rdBase

try:
    from .run_hydration_pilot import ROOT, CONTROLS, solute, sha, write_json, hydration
    from .hydration_descriptor import VERSION, CUTOFFS, EDGES, measure
except ImportError:
    from run_hydration_pilot import ROOT, CONTROLS, solute, sha, write_json, hydration
    from hydration_descriptor import VERSION, CUTOFFS, EDGES, measure


def add_barostat(system, ensemble, seed):
    if ensemble == 'NPT':
        barostat = mm.MonteCarloBarostat(1 * unit.bar, 273 * unit.kelvin, 25)
        barostat.setRandomNumberSeed(seed + 100000)
        system.addForce(barostat)
    elif ensemble != 'NVT':
        raise ValueError('Unknown ensemble')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compound', choices=CONTROLS, required=True)
    parser.add_argument('--ensemble', choices=['NVT', 'NPT'], required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--platform', choices=['CPU', 'OpenCL', 'CUDA', 'Reference'], default='CUDA')
    parser.add_argument('--equilibration-ps', type=float, default=500)
    parser.add_argument('--production-ps', type=float, default=3000)
    parser.add_argument('--frames', type=int, default=300)
    parser.add_argument('--max-wall-seconds', type=float, default=1400)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.seed < 2**31-100000 or args.frames < 6 or min(args.equilibration_ps, args.production_ps, args.max_wall_seconds) <= 0:
        parser.error('Invalid seed, duration or frame count')
    dt = .002
    eq, prod = round(args.equilibration_ps/dt), round(args.production_ps/dt)
    if prod < args.frames or prod % args.frames or eq < 10:
        parser.error('Production must divide into frames; equilibration needs >=10 steps')
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    water_xml = ROOT/'simulation/tip4p-ice.xml'
    mol, top, positions = solute(args.compound, args.seed)
    ff = app.ForceField('charmm36.xml', str(water_xml))
    modeller = app.Modeller(top, positions)
    modeller.addSolvent(ff, model='tip4pew', boxSize=mm.Vec3(4,4,4)*unit.nanometer, neutralize=False)
    modeller.addExtraParticles(ff)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.PME,
        nonbondedCutoff=1*unit.nanometer, switchDistance=.8*unit.nanometer,
        constraints=app.HBonds, rigidWater=True, ewaldErrorTolerance=5e-4)
    add_barostat(system, args.ensemble, args.seed)
    integrator = mm.LangevinMiddleIntegrator(273*unit.kelvin, 1/unit.picosecond, dt*unit.picosecond)
    integrator.setRandomNumberSeed(args.seed)
    integrator.setConstraintTolerance(1e-6)
    props = {'Threads':'2'} if args.platform == 'CPU' else {'Precision':'mixed' if args.platform == 'CUDA' else 'single'} if args.platform in {'CUDA','OpenCL'} else {}
    sim = app.Simulation(modeller.topology, system, integrator, mm.Platform.getPlatformByName(args.platform), props)
    sim.context.setPositions(modeller.positions)
    sim.context.computeVirtualSites()
    sim.minimizeEnergy(maxIterations=1000)
    sim.context.setVelocitiesToTemperature(273*unit.kelvin, args.seed)
    atoms = list(modeller.topology.atoms())
    sol = [a.index for a in atoms if a.residue.index == 0]
    wat = [a.index for a in atoms if a.residue.index != 0 and a.element == app.element.oxygen]
    if len(sol) != mol.GetNumAtoms() or len(wat) < 1000:
        raise ValueError('Unexpected topology')
    masses = sum(system.getParticleMass(i).value_in_unit(unit.dalton) for i in range(system.getNumParticles()))
    dof = 3*sum(system.getParticleMass(i).value_in_unit(unit.dalton)>0 for i in range(system.getNumParticles()))-system.getNumConstraints()-3

    def step(n):
        while n:
            if time.monotonic()-started > args.max_wall_seconds:
                raise TimeoutError('Stability job time limit reached')
            chunk = min(n, 500)
            sim.step(chunk)
            n -= chunk

    def snapshot():
        state = sim.context.getState(positions=True, energy=True)
        xyz = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        box = state.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)
        energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        temperature = 2*state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)/(dof*.00831446261815324)
        density = masses*1.66053906660e-3/np.linalg.det(box)
        if not np.isfinite(xyz).all() or not np.isfinite([energy,temperature,density]).all():
            raise ValueError('Nonfinite state')
        return state, xyz, box, energy, temperature, density

    equil = []
    for n in [eq//10 + (i < eq%10) for i in range(10)]:
        step(n)
        state, xyz, box, energy, temp, density = snapshot()
        equil.append({'time_ps':sim.currentStep*dt,'density_g_ml':density,'temperature_K':temp,'potential_kj_mol':energy})
    coords, boxes, counts, pdfs, energies, temps, densities, pairs = [], [], [], [], [], [], [], []
    timed = time.monotonic()
    for _ in range(args.frames):
        step(prod//args.frames)
        state, xyz, box, energy, temp, density = snapshot()
        count, pdf = measure(xyz, box, sol, wat)
        _, pair = hydration(xyz, box, sol, wat)
        coords.append(xyz.astype(np.float32)); boxes.append(box)
        counts.append(count); pdfs.append(pdf); energies.append(energy); temps.append(temp); densities.append(density)
        pairs.append(pair)
    elapsed = time.monotonic()-timed
    np.savez_compressed(out/'trajectory.npz', positions_nm=coords, boxes_nm=boxes,
        solute_indices=sol, water_oxygen_indices=wat, hydration_counts=counts,
        nearest_pdf=pdfs, pair_histograms=pairs, potential_kj_mol=energies, temperature_K=temps, density_g_ml=densities,
        production_time_ps=np.arange(1,args.frames+1)*prod*dt/args.frames)
    (out/'system.xml').write_text(mm.XmlSerializer.serialize(system))
    (out/'integrator.xml').write_text(mm.XmlSerializer.serialize(integrator))
    modeller.topology.setPeriodicBoxVectors(state.getPeriodicBoxVectors())
    with (out/'topology.pdb').open('w') as handle:
        app.PDBFile.writeFile(modeller.topology, state.getPositions(), handle)
    sim.saveState(str(out/'final-state.xml'))
    result = {'status':'Exploratory ensemble and duration sensitivity; no experimental efficacy validation',
        'control':CONTROLS[args.compound], 'compound':args.compound,'seed':args.seed,'descriptor_version':VERSION,
        'configuration':{'ensemble':args.ensemble,'pressure_bar':1 if args.ensemble=='NPT' else None,
            'barostat_interval_steps':25 if args.ensemble=='NPT' else None,'barostat_seed':args.seed+100000 if args.ensemble=='NPT' else None,
            'temperature_K':273,'equilibration_ps':eq*dt,'production_ps':prod*dt,'frames':args.frames,
            'time_step_ps':dt,'initial_box_nm':4,'salt_added':False,'mass_da':masses,
            'platform':args.platform,'platform_properties':props,'water_molecules':len(wat),
            'mean_solute_concentration_mM':float(np.mean(1000/(6.02214076e23*np.linalg.det(boxes)*1e-24)))},
        'equilibration_samples':equil,
        'observables':{'cutoffs_nm':CUTOFFS.tolist(),'histogram_edges_nm':EDGES.tolist(),
            'mean_hydration_counts':np.mean(counts,axis=0).tolist(),'mean_nearest_pdf':np.mean(pdfs,axis=0).tolist(),
            'mean_density_g_ml':float(np.mean(densities)),'mean_temperature_K':float(np.mean(temps))},
        'timing':{'production_wall_seconds':elapsed,'total_wall_seconds':time.monotonic()-started,
            'production_ns_per_day':prod*dt/1000/elapsed*86400},
        'versions':{'python':platform.python_version(),'openmm':mm.__version__,'numpy':np.__version__,'rdkit':rdBase.rdkitVersion},
        'hashes':{'script':sha(__file__),'descriptor':sha(Path(__file__).with_name('hydration_descriptor.py')),
            'pilot_dependency':sha(Path(__file__).with_name('run_hydration_pilot.py')),'water_xml':sha(water_xml),
            'charmm_xml':sha(Path(app.__file__).parent/'data/charmm36.xml'),'trajectory':sha(out/'trajectory.npz'),
            'system':sha(out/'system.xml')},
        'limits':['Short liquid-water simulation; no ice interface, cell, toxicity or apoptosis model.',
            'Nearest-water descriptor is a new representation; original DOLMEN settings remain unresolved.',
            'Frames are correlated; seeds are replicates. Apparent stability is not proof of convergence.',
            'NPT changes both density and effective solute concentration; no salt and no matched experimental concentration.']}
    write_json(out/'result.json', result)
    print(f'{args.compound} {args.ensemble} {args.seed}: completed {prod*dt/1000:g} ns', flush=True)


if __name__ == '__main__':
    main()
