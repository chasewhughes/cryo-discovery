import tempfile, unittest
from pathlib import Path
from scripts.extract_transport_screen import extract

class ExtractTransportScreenTests(unittest.TestCase):
    def test_published_tables_and_censored_statuses(self):
        p=Path('data/raw/phase15/transport/PMC11731021.xml')
        out=extract(p)
        self.assertEqual(len(out['table1_permeability']), 28) # 27 chemicals + sucrose
        self.assertEqual(len(out['table2_activation_energy']), 13)
        sucrose_e=next(r for r in out['table2_activation_energy'] if r['solute']=='Sucrose')
        self.assertIsNone(sucrose_e['E_PCPA_kJ_mol'])
        self.assertEqual(out['toxicity_summary']['status_counts']['4_C']['toxic'], 4)
        self.assertEqual(out['toxicity_summary']['status_counts']['25_C']['toxic'], 6)
        by={r['solute']:r for r in out['table1_permeability']}
        self.assertEqual(by['Sucrose']['4_C']['status'], 'measured')
        self.assertEqual(by['Triethylene Glycol Diacetate']['25_C']['status'], 'toxic')
        self.assertEqual(by['2-Methoxyethanol']['4_C']['status'], 'fast')
        self.assertIsNone(by['Pyridine']['4_C'].get('P_CPA_x10^-3_s^-1'))
        self.assertAlmostEqual(by['Ethylene Glycol']['25_C']['P_CPA_x10^-3_s^-1']['mean'],317.07)
        self.assertEqual(by['Ethylene Glycol']['25_C']['P_CPA_x10^-3_s^-1']['uncertainty_type'], 'not_explicitly_specified')
        self.assertNotIn('sd', by['Ethylene Glycol']['25_C']['P_CPA_x10^-3_s^-1'])

    def test_table_parser_expands_colspans(self):
        out=extract(Path('data/raw/phase15/transport/PMC11731021.xml'))
        tri=next(r for r in out['table1_permeability'] if r['solute']=='Triethanolamine')
        self.assertEqual(tri['25_C']['status'],'toxic')
        self.assertEqual(tri['4_C']['status'],'measured')

if __name__=='__main__': unittest.main()
