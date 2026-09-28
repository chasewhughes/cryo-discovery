"""Reproduce the read-only Phase 11 descriptor audit from saved Phase 10 runs."""
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.hydration_descriptor import measure, VERSION

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    prior = json.loads((ROOT/'data/phase10/hydration-results.json').read_text())['results']
    source = {}
    with (ROOT/'cryo-adata/raw/phase8/dolmen/data/descriptors/hydhist_amino.csv').open() as f:
        r = csv.DictReader(f); keys = r.fieldnames[1:]
        for row in r: source[row['Name'].casefold()] = np.array([float(row[k]) for k in keys])
    checks = {}; all_ok = True
    for code, name in [('gly','l-glycine'), ('phe','l-phenylalanine')]:
        rows = []; all_h = []; all_c = []; original_pdfs=[]; max_count_diff=0
        for p in sorted((ROOT/'cryo-adata/raw/phase10/runpod/runs').glob(code+'-*/trajectory.npz')):
            d = np.load(p); hs=[]; cs=[]
            for xyz, box in zip(d['positions_nm'], d['boxes_nm']):
                c, h = measure(xyz, box, d['solute_indices'], d['water_oxygen_indices']); cs.append(c); hs.append(h)
                # Exact Phase 10 arithmetic: subtraction/norm stay float32.
                delta=xyz[d['water_oxygen_indices'],None,:]-xyz[None,d['solute_indices'],:]
                lengths=np.diag(box); delta-=lengths*np.rint(delta/lengths)
                nearest=np.linalg.norm(delta,axis=2).min(axis=1)
                hist=np.histogram(nearest,bins=100,range=(0,.5))[0]
                original_pdfs.append(hist/(hist.sum()*.005))
            cs, hs = np.asarray(cs), np.asarray(hs); saved = d['hydration_counts']
            diff = int(np.max(np.abs(cs-saved))); all_ok &= diff == 0
            max_count_diff=max(max_count_diff,diff)
            mean_h = hs.mean(axis=0); all_h.extend(hs); all_c.extend(cs)
            rows.append({'run': p.parent.name, 'count_030_nm': float(cs.mean(axis=0)[2]), 'pdf_integral_mean': float(np.mean(hs.sum(axis=1)*.005)), 'source_tv': float(.5*np.abs(mean_h-source[name]).sum()*.005), 'trajectory_sha256': sha(p)})
        mean_h = np.mean(all_h, axis=0)
        old = np.array(prior[name]['posthoc_definition_comparisons']['nearest_pdf']['mean_density'])
        checks[name] = {'saved_count_max_absolute_difference': diff, 'mean_count_030_nm': float(np.mean(all_c,axis=0)[2]), 'all_frame_integral_min': float(np.min(np.asarray(all_h).sum(axis=1)*.005)), 'all_frame_integral_max': float(np.max(np.asarray(all_h).sum(axis=1)*.005)), 'stored_posthoc_max_abs_density_difference': float(np.max(np.abs(mean_h-old))), 'stored_posthoc_total_variation': float(.5*np.abs(mean_h-old).sum()*.005), 'per_seed': rows}
        checks[name]['saved_count_max_absolute_difference']=max_count_diff
        old_recomputed=np.mean(original_pdfs,axis=0)
        checks[name]['original_float32_recalculation_tv_to_stored']=float(.5*np.abs(old_recomputed-old).sum()*.005)
        checks[name]['original_float32_to_new_float64_tv']=float(.5*np.abs(old_recomputed-mean_h).sum()*.005)
        if len(rows)!=3: raise ValueError('Expected three seeds per compound')
    if not all_ok: raise ValueError('Recomputed hydration counts differ from saved values')
    out = {'status':'completed_read_only_reanalysis', 'descriptor_version':VERSION, 'analysis_script_sha256':sha(__file__), 'descriptor_script_sha256':sha(ROOT/'scripts/hydration_descriptor.py'), 'checks':checks, 'interpretation':'New water-occupancy representation only; original DOLMEN settings unresolved. Exact cutoff/bin boundaries follow NumPy floating-point behavior.'}
    (ROOT/'data/phase11/descriptor-audit.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({'descriptor_version':VERSION, 'saved_count_checks_pass':all_ok, 'output':'data/phase11/descriptor-audit.json'}))
if __name__ == '__main__': main()
