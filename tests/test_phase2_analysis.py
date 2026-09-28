import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from analyze_iri_data import recovery
from collect_zenodo_tables import checked_block
from index_remote_rar import parse_header


class Phase2IntegrityTests(unittest.TestCase):
    def test_recovery_uses_initial_viable_yield(self):
        self.assertAlmostEqual(recovery(750000, 0.8, 1200000), 50)

    def test_bad_denominator_rejected(self):
        with self.assertRaises(ValueError):
            recovery(750000, 1, 0)

    def test_rar_header_integrity(self):
        block = checked_block(bytes([3, 5, 0, 0]))
        parsed = parse_header(block, 100)
        self.assertEqual((parsed['kind'], parsed['next_offset']), (5, 108))
        changed = bytearray(block)
        changed[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC mismatch'):
            parse_header(changed, 100)

    def test_truncated_rar_header_rejected(self):
        block = checked_block(bytes([3, 5, 0, 0]))
        with self.assertRaisesRegex(ValueError, 'exceeds range'):
            parse_header(block[:-1], 0)


if __name__ == '__main__':
    unittest.main()
