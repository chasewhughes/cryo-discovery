"""Phase 13 metadata adapter over the validated hydration integration engine."""
import argparse
import json
import sys
from pathlib import Path
try:
    from . import run_hydration_extension as engine
except ImportError:
    import run_hydration_extension as engine

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--input','--inputPATH','--input-path',dest='source',required=True)
    parser.add_argument('--output','--outputPATH','--output-path',dest='output',required=True)
    args,_=parser.parse_known_args(argv)
    parent=json.loads((Path(args.source)/'result.json').read_text())
    if parent.get('preparation_only') is not True or parent.get('compound') not in {'leu','ile'}:
        raise ValueError('Expected a fresh matched-control preparation')
    if parent['configuration']['water_molecules']!=2070 or parent['configuration']['ensemble']!='NPT':
        raise ValueError('Expected matched 2070-water NPT preparation')
    engine.main(argv)
    out=Path(args.output);result=json.loads((out/'result.json').read_text())
    (out/'result.json').rename(out/'core-result.json')
    result['phase']=13
    result['status']='Fresh same-formula control simulation; no efficacy validation'
    result['branching']['mode']='independent preparation followed by new thermostat/barostat streams'
    result['preparation_seed']=parent['seed']
    result['preparation_only']=False
    result['identity']=parent.get('identity',{})
    result['hashes']['integration_engine']=result['hashes']['script']
    result['hashes']['script']=engine.sha(__file__)
    result['hashes']['core_result']=engine.sha(out/'core-result.json')
    result['limits']=['Same formula and solvent number control mass; shape and stereochemistry remain different.',
        'Equilibration excluded; exact durations and frame count recorded in configuration.',
        'NPT liquid water at 273 K with no salt, ice interface, cell, apoptosis or toxicity model.',
        'Known-label method-development controls; no independent efficacy validation or model fitting.']
    engine.write_json(out/'result.json',result)

if __name__=='__main__':main()
