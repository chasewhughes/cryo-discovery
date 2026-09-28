#!/usr/bin/env python3
"""Recompute descriptive outcomes from the unmodified 2025 cardiomyocyte supplement."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from analyze_iri_data import read_sheet, NS

ROOT = Path(__file__).resolve().parents[1]


def describe(values):
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError('At least two finite observations required')
    return {'n_observations': len(values), 'mean': statistics.mean(values),
            'sample_sd': statistics.stdev(values), 'population_sd': statistics.pstdev(values),
            'sample_sem': statistics.stdev(values) / math.sqrt(len(values))}


def main():
    record = json.loads((ROOT/'data/phase3/dmso-free-cm-review.json').read_text())['retrieved_assets']['supplement_xlsx']
    source = ROOT / record['path']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256']
    with ZipFile(source) as z:
        sheets = [x.get('name') for x in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet', NS)]
    assert sheets[2:5] == ['DE Algorithm results','Cooling rate optimization','Nucleation temp optimization']
    assert sheets[7:9] == ['Post-thaw assessment (recovery)','Post-thaw assessment (calcium)']
    tables = {i: read_sheet(source, f'xl/worksheets/sheet{i}.xml') for i in (3,4,5,8,9)}
    value = lambda i, address: tables[i][address]['value']
    observations = []
    for sheet, rows, arm_col, endpoint_col, parameter in [(4,range(2,26),'A','C','cooling_rate_c_per_min'),
                                                       (5,range(2,26),'A','C','nucleation_c'),
                                                       (8,range(2,14),'A','D',None)]:
        for row in rows:
            recovery = value(sheet, f'{endpoint_col}{row}')
            assert 0 <= recovery <= 1
            obs = {'source_sheet': sheets[sheet-1], 'source_row': row,
                   'arm': value(sheet, f'{arm_col}{row}'), 'recovery_percent': recovery*100}
            if parameter: obs[parameter] = value(sheet, f'B{row}')
            else:
                obs.update(cooling_rate_c_per_min=value(sheet,f'B{row}'), nucleation_c=value(sheet,f'C{row}'))
                assert obs['cooling_rate_c_per_min']==5 and obs['nucleation_c']==-8
            observations.append(obs)
    final = {}
    for arm in ('Solution A','Solution B','DMSO'):
        values = [r['recovery_percent'] for r in observations if r['source_sheet']==sheets[7] and r['arm']==arm]
        assert len(values)==4
        final[arm] = describe(values)
    assert round(final['Solution A']['mean'],2)==92.06
    assert round(final['DMSO']['mean'],2)==80.19
    assert round(final['Solution A']['population_sd'],2)==2.50
    assert round(final['DMSO']['population_sd'],2)==4.22
    thermal = []
    for sheet,parameter in ((sheets[3],'cooling_rate_c_per_min'),(sheets[4],'nucleation_c')):
        groups=defaultdict(list)
        for obs in observations:
            if obs['source_sheet']==sheet:groups[(obs['arm'],obs[parameter])].append(obs['recovery_percent'])
        for (arm, setting), values in sorted(groups.items()):
            assert len(values)==4
            thermal.append({'source_sheet':sheet,'arm':arm,parameter:setting,**describe(values)})
    calcium=[]; signals=defaultdict(list)
    for row in range(2,20):
        arm = value(9,f'A{row}')
        peak,baseline,signal = [value(9,f'{c}{row}') for c in ('D','E','F')]
        up,down,ratio = [value(9,f'{c}{row}') for c in ('G','I','K')]
        assert math.isclose(signal,peak-baseline,abs_tol=1e-12)
        assert math.isclose(ratio,down/up,abs_tol=1e-12)
        calcium.append({'source_sheet':sheets[8], 'source_row':row,'arm':arm,
                        'reported_signal_amplitude':signal,'peak_average':peak,'minimum_average':baseline,
                        'difference_divided_by_minimum_for_definition_check':signal/baseline,
                        'reported_up_down_velocity_ratio':ratio})
        signals[arm].append(signal)
    assert {k:len(v) for k,v in signals.items()}=={'Solution A':5,'Solution B':3,'DMSO':3,'Passaged':7}
    generations=defaultdict(list)
    for row in range(2,74):
        generation=value(3,f'A{row}')
        generations[int(generation)].append(value(3,f'C{row}')*100)
    assert set(generations)==set(range(8)) and all(len(v)==9 for v in generations.values())
    out={'source_doi':'10.1186/s13287-025-04384-5','source_workbook':record,
         'analysis_type':'Descriptive recomputation; no new hypothesis tests or donor-independence assumptions',
         'recovery_observations':observations,'final_recovery_percent':final,'thermal_recovery_percent':thermal,
         'final_A_minus_DMSO_recovery_pp':final['Solution A']['mean']-final['DMSO']['mean'],
         'calcium_observations':calcium,'calcium_reported_signal_summaries':{k:describe(v) for k,v in signals.items()},
         'optimizer_generation_summaries':[{'generation':g,**describe(v)} for g,v in sorted(generations.items())],
         'checks':['Original supplementary file SHA-256 matches retrieval record',
                   '60 recovery rows: 24 cooling, 24 nucleation, 12 final-assessment; n=4 per arm/setting',
                   'Final means reproduce paper values; accompanying ± values reproduce population SD, not SEM',
                   'All 18 calcium amplitude entries equal peak-minus-minimum; all timing ratios agree',
                   'Eight optimizer populations have nine entries each; survivors may recur between generations'],
         'limitations':['One engineered CCND2 donor line; rows are observations, not independent donor samples.',
                        'No raw cell-count denominators, batch IDs or calcium image/trace identifiers in these tables; cross-panel observation independence is unresolved.',
                        'No absolute osmolyte concentrations or solution-composition map found in the workbook. Figure 2 reports dimensionless component levels.',
                        'The paper states figure error bars are standard error; its recovery prose ± values instead match population SD. Keep both definitions explicit.',
                        'Calcium amplitude entries equal peak-minus-minimum; paper labels amplitude F/F0. Upstream normalization is not documented here, so interpretation requires clarification.',
                        'Absence of a significant difference from fresh cells is not an equivalence test.',
                        'Optimized recovery uses DMSO comparator 80.19%, distinct from optimization-stage 69.4%; they must not be interchanged.',
                        'DMSO-free loading is 60 minutes versus 30 minutes for DMSO; formula and loading effects are confounded.']}
    (ROOT/'data/phase3/cm-2025-analysis.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'recovery_rows':len(observations),'calcium_rows':len(calcium),'A_minus_DMSO_pp':out['final_A_minus_DMSO_recovery_pp'],'final_recovery_percent':final},indent=2))


if __name__=='__main__':main()
