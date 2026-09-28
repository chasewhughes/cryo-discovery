"""Acquire one bounded, shared alignment through Boltz's documented MSA service."""
import hashlib
import json
from pathlib import Path
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw/phase17/msa-assay'


def request(endpoint, data=None):
    req = urllib.request.Request('https://api.colabfold.com/'+endpoint,
        data=urllib.parse.urlencode(data).encode() if data is not None else None,
        headers={'User-Agent': 'boltz'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read(50_000_001)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    sequence = json.loads((ROOT/'data/phase17/target-sequence.json').read_text())['sequence']
    query = '>101\n'+sequence+'\n'
    (RAW/'query.fasta').write_text(query)
    ticket = RAW/'ticket.json'
    if not ticket.exists():
        response = request('ticket/msa', {'q': query, 'mode': 'env'})
        ticket.write_bytes(response)
    state = json.loads(ticket.read_text())
    deadline = time.time()+900
    while state['status'] in ('PENDING', 'RUNNING', 'UNKNOWN') and time.time() < deadline:
        print(json.dumps(state), flush=True)
        time.sleep(15)
        state = json.loads(request('ticket/'+state['id']))
        (RAW/'status.json').write_text(json.dumps(state, indent=2)+'\n')
    if state['status'] != 'COMPLETE':
        raise RuntimeError('MSA service did not complete: '+state['status'])
    archive = RAW/'result.tar.gz'
    if not archive.exists():
        body = request('result/download/'+state['id'])
        if len(body)>50_000_000: raise ValueError('MSA archive exceeds limit')
        archive.write_bytes(body)
    parts = []
    with tarfile.open(archive) as tar:
        for name in ('uniref.a3m', 'bfd.mgnify30.metaeuk30.smag30.a3m'):
            member = tar.getmember(name)
            if not member.isfile() or member.size > 40_000_000: raise ValueError('Invalid MSA member')
            content = tar.extractfile(member).read().decode().replace('\x00','')
            (RAW/name).write_text(content)
            parts.append(content)
    # Query first; deduplicate identical aligned strings preserving database order.
    entries=[]
    for part in parts:
        for block in part.split('>')[1:]:
            lines=block.splitlines(); entries.append((lines[0], ''.join(lines[1:])))
    if not entries or entries[0][1] != sequence: raise ValueError('MSA query sequence mismatch')
    seen=set(); selected=[]
    for name, seq in entries:
        aligned=''.join(c for c in seq if not c.islower() and c!='.')
        if len(aligned)!=len(sequence): raise ValueError('MSA aligned length mismatch')
        if seq not in seen:
            selected.append((name,seq)); seen.add(seq)
        if len(selected)==512: break
    if len(selected)<2: raise ValueError('No homologous alignment rows returned')
    output=RAW/'rock2-512.a3m'
    output.write_text(''.join('>'+name+'\n'+seq+'\n' for name,seq in selected))
    meta={'service':'https://api.colabfold.com','mode':'env','ticket_id':state['id'],
          'protein_source':'data/phase17/target-sequence.json','sequence_length':len(sequence),
          'returned_entries':len(entries),'selected_rows':len(selected),'policy':'Query first, deduplicate identical aligned strings, retain first 512 in service database order; no ligand labels used.',
          'database_versions':'Not explicitly supplied in service response; archive retained.',
          'sources':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [RAW/'query.fasta',ticket,archive,output,ROOT/'data/raw/phase17/source/mmseqs2.py']]}
    dest=ROOT/'data/phase17/msa-manifest.json'; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'selected_rows':len(selected),'path':str(output)}))


if __name__=='__main__': main()
