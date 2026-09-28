"""Focused contract tests for the Phase 12 state extension runner."""
import unittest

try:
    import openmm as mm
    from openmm import unit
    from scripts.run_hydration_extension import validate_parent, _set_rngs, main
except ImportError:
    mm = None


@unittest.skipIf(mm is None, "Requires isolated MD environment")
class ExtensionContractTests(unittest.TestCase):
    def test_restoration_accepts_float32_rounding_but_rejects_displaced_state(self):
        import numpy as np
        from types import SimpleNamespace
        from scripts.run_hydration_extension import verify_restored_state
        xyz=np.array([[1.234567891,2.123456789,4.99999999]])
        vel=np.array([[.123456789,2.23456789,-.99999999]])
        def state(p,v):
            return SimpleNamespace(getPositions=lambda **kwargs:p*unit.nanometer,
                getPeriodicBoxVectors=lambda **kwargs:np.eye(3)*4*unit.nanometer,
                getVelocities=lambda **kwargs:v*unit.nanometer/unit.picosecond)
        source=state(xyz,vel)
        check=verify_restored_state(source,state(xyz.astype(np.float32).astype(float),vel.astype(np.float32).astype(float)))
        self.assertLess(check['max_position_error_nm'],1e-6)
        # Periodic wrapping can round at box-length scale even near zero coordinates.
        shifted=xyz.copy();shifted[0,0]+=6e-7
        verify_restored_state(source,state(shifted,vel))
        with self.assertRaisesRegex(ValueError,'positions'):verify_restored_state(source,state(xyz+.001,vel))
        with self.assertRaisesRegex(ValueError,'velocities'):verify_restored_state(source,state(xyz,vel+.001))

    def make_model(self, npt=True):
        system = mm.System()
        system.addParticle(1 * unit.dalton)
        if npt:
            force = mm.MonteCarloBarostat(1 * unit.bar, 273 * unit.kelvin, 25)
            system.addForce(force)
        integrator = mm.LangevinMiddleIntegrator(273 * unit.kelvin,
                                                   1 / unit.picosecond,
                                                   .002 * unit.picosecond)
        integrator.setConstraintTolerance(1e-6)
        return system, integrator

    def parent(self, ensemble):
        return {"descriptor_version": "cryo-nearest-water-v1", "configuration": {
            "ensemble": ensemble, "temperature_K": 273,
            "time_step_ps": .002, "pressure_bar": 1 if ensemble == "NPT" else None,
            "barostat_interval_steps": 25 if ensemble == "NPT" else None}}

    def test_rngs_are_reset_on_integrator_and_barostat_before_context(self):
        system, integrator = self.make_model()
        _set_rngs(system, integrator, 20261001)
        self.assertEqual(integrator.getRandomNumberSeed(), 20261001)
        self.assertEqual(system.getForce(0).getRandomNumberSeed(), 20361001)

    def test_parent_ensemble_and_physical_parameters_are_checked(self):
        system, integrator = self.make_model()
        self.assertEqual(validate_parent(self.parent("NPT"), system, integrator), "NPT")
        with self.assertRaisesRegex(ValueError, "barostat"):
            validate_parent(self.parent("NVT"), system, integrator)
        bad = self.parent("NPT")
        bad["configuration"]["temperature_K"] = 300
        with self.assertRaisesRegex(ValueError, "273"):
            validate_parent(bad, system, integrator)

    def test_nvt_requires_no_barostat(self):
        system, integrator = self.make_model(npt=False)
        self.assertEqual(validate_parent(self.parent("NVT"), system, integrator), "NVT")

    def test_nvt_rejects_multiple_barostats(self):
        system, integrator = self.make_model(npt=False)
        system.addForce(mm.MonteCarloBarostat(1 * unit.bar, 273 * unit.kelvin, 25))
        system.addForce(mm.MonteCarloBarostat(1 * unit.bar, 273 * unit.kelvin, 25))
        with self.assertRaisesRegex(ValueError, "barostat"):
            validate_parent(self.parent("NVT"), system, integrator)

    def test_wrong_integrator_is_rejected(self):
        system, _ = self.make_model(npt=False)
        with self.assertRaisesRegex(ValueError, "LangevinMiddle"):
            validate_parent(self.parent("NVT"), system, mm.VerletIntegrator(.002 * unit.picosecond))

    def test_cli_rejects_zero_frames_and_nonfinite_duration(self):
        common = ["--input", "/tmp/unused", "--seed", "20261001", "--output", "/tmp/unused-out"]
        with self.assertRaises(SystemExit):
            main(common + ["--frames", "0"])
        with self.assertRaises(SystemExit):
            main(common + ["--equilibration-ps", "nan"])


if __name__ == "__main__":
    unittest.main()
