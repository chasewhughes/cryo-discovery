"""Scientific invariants for the reconstructed MD workflow (isolated MD env)."""
import math
import unittest
import xml.etree.ElementTree as ET

try:
    import openmm as mm
    from openmm import app, unit
    import numpy as np
    from scripts import run_hydration_pilot as pilot
except ImportError:
    pilot = None


@unittest.skipIf(pilot is None, "Requires isolated MD environment")
class HydrationTests(unittest.TestCase):
    def test_periodic_water_is_counted_once(self):
        # Both solute atoms see the boundary-crossing water; count one molecule.
        xyz = np.array([[0.05, 0, 0], [0.10, 0, 0], [3.95, 0, 0], [2, 2, 2]])
        counts, histogram = pilot.hydration(xyz, np.eye(3)*4, [0, 1], [2, 3])
        np.testing.assert_array_equal(counts, np.ones(7))
        self.assertAlmostEqual(float(histogram.sum()*0.005), 1)

    def test_nonorthogonal_box_rejected(self):
        box = np.eye(3)*4
        box[0, 1] = 0.2
        with self.assertRaises(ValueError):
            pilot.hydration(np.zeros((2, 3)), box, [0], [1])

    def test_water_physical_parameters(self):
        root = ET.parse(pilot.ROOT/'simulation/tip4p-ice.xml').getroot()
        atoms = root.findall('./Residues/Residue/Atom')
        self.assertAlmostEqual(sum(float(a.attrib['charge']) for a in atoms), 0)
        oxygen = root.find("./LennardJonesForce/Atom[@type='ice-O']")
        self.assertAlmostEqual(float(oxygen.attrib['epsilon'])/4.184, 0.21084)
        self.assertAlmostEqual(float(oxygen.attrib['sigma'])*10, 3.1668)
        # A real water system verifies the fourth site's physical displacement.
        ff = app.ForceField('charmm36.xml', str(pilot.ROOT/'simulation/tip4p-ice.xml'))
        top = app.Topology(); res = top.addResidue('HOH', top.addChain())
        o = top.addAtom('O', app.element.oxygen, res)
        h1 = top.addAtom('H1', app.element.hydrogen, res)
        h2 = top.addAtom('H2', app.element.hydrogen, res)
        top.addAtom('M', None, res); top.addBond(o,h1); top.addBond(o,h2)
        system = ff.createSystem(top, nonbondedMethod=app.NoCutoff, rigidWater=True)
        angle = math.radians(104.52/2)
        x, y = 0.09572*math.cos(angle), 0.09572*math.sin(angle)
        integ = mm.VerletIntegrator(0.001)
        context = mm.Context(system, integ, mm.Platform.getPlatformByName('Reference'))
        context.setPositions([[0,0,0],[x,y,0],[x,-y,0],[0,0,0]])
        context.computeVirtualSites()
        xyz = context.getState(positions=True).getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        self.assertAlmostEqual(float(np.linalg.norm(xyz[3]-xyz[0])), 0.01577)
        self.assertEqual(system.getNumConstraints(),3)

    def test_free_amino_acid_templates_are_zwitterionic(self):
        from rdkit import Chem
        from rdkit.Chem.MolStandardize import rdMolStandardize
        def normalized_parent(s):
            mol = rdMolStandardize.CanonicalTautomer(rdMolStandardize.ChargeParent(Chem.MolFromSmiles(s)))
            return Chem.MolToSmiles(mol, isomericSmiles=True)
        import json
        records = {x['id']:x for x in json.loads((pilot.ROOT/'data/phase9/assay-reconciliation.json').read_text())['records']}
        ff = app.ForceField('charmm36.xml', str(pilot.ROOT/'simulation/tip4p-ice.xml'))
        for code, spec in pilot.CONTROLS.items():
            mol, top, _ = pilot.solute(code,20260906)
            self.assertEqual(normalized_parent(spec['smiles']), normalized_parent(records[spec['id']]['canonical_smiles']))
            system = ff.createSystem(top, nonbondedMethod=app.NoCutoff)
            force = next(f for f in system.getForces() if isinstance(f,mm.NonbondedForce))
            charges = [force.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge) for i in range(system.getNumParticles())]
            self.assertAlmostEqual(sum(charges),0)
            self.assertEqual(Chem.GetFormalCharge(mol),0)
            self.assertTrue(any(a.GetFormalCharge()==1 for a in mol.GetAtoms()))
            self.assertTrue(any(a.GetFormalCharge()==-1 for a in mol.GetAtoms()))
            nitrogen = next(a for a in mol.GetAtoms() if a.GetAtomicNum()==7)
            ammonium = [nitrogen.GetIdx()] + [a.GetIdx() for a in nitrogen.GetNeighbors() if a.GetAtomicNum()==1]
            self.assertAlmostEqual(sum(charges[i] for i in ammonium), 0.69)
            self.assertEqual(sum(a.GetAtomicNum()==1 for a in mol.GetAtoms()),sum(a.element==app.element.hydrogen for a in top.atoms()))

    def test_water_dimer_energy_matches_coulomb_plus_lj(self):
        ff = app.ForceField('charmm36.xml',str(pilot.ROOT/'simulation/tip4p-ice.xml'))
        top = app.Topology(); chain=top.addChain()
        for _ in range(2):
            res=top.addResidue('HOH',chain)
            o=top.addAtom('O',app.element.oxygen,res)
            h1=top.addAtom('H1',app.element.hydrogen,res)
            h2=top.addAtom('H2',app.element.hydrogen,res)
            top.addAtom('M',None,res);top.addBond(o,h1);top.addBond(o,h2)
        system=ff.createSystem(top,nonbondedMethod=app.NoCutoff,rigidWater=True)
        angle=math.radians(104.52/2)
        x,y=.09572*math.cos(angle),.09572*math.sin(angle)
        first=np.array([[0,0,0],[x,y,0],[x,-y,0],[.01577,0,0]])
        second=first+np.array([0,0,.4])
        integ=mm.VerletIntegrator(.001)
        context=mm.Context(system,integ,mm.Platform.getPlatformByName('Reference'))
        context.setPositions(np.vstack([first,second]));context.computeVirtualSites()
        actual=context.getState(energy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        charges=np.array([0,.5897,.5897,-1.1794])
        coulomb=138.93545764438198*np.sum(charges[:,None]*charges[None,:]/np.linalg.norm(first[:,None,:]-second[None,:,:],axis=2))
        lj=4*(.21084*4.184)*((.31668/.4)**12-(.31668/.4)**6)
        self.assertAlmostEqual(actual,coulomb+lj,places=5)


if __name__ == '__main__':
    unittest.main()
