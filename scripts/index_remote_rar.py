#!/usr/bin/env python3
"""Index a public RAR5 archive using bounded HTTP ranges; no bulk extraction."""
import argparse, datetime, json, struct, time, zlib
from pathlib import Path
from urllib.request import Request, urlopen

URL='https://zenodo.org/api/records/14038512/files/Data%20manuscript.rar/content'
ROOT=Path(__file__).resolve().parents[1]

def vint(buf,pos):
    value=0
    for shift in range(0,70,7):
        b=buf[pos];pos+=1;value|=(b&127)<<shift
        if b<128:return value,pos
    raise ValueError('invalid RAR variable integer')

def parse_header(buf,offset):
    size,pos=vint(buf,4);end=pos+size
    if end>len(buf):raise ValueError('header exceeds range buffer')
    if zlib.crc32(buf[4:end])&0xffffffff != struct.unpack_from('<I',buf)[0]:
        raise ValueError('RAR header CRC mismatch')
    kind,pos=vint(buf,pos);flags,pos=vint(buf,pos)
    extra=0;data_size=0
    if flags&1:extra,pos=vint(buf,pos)
    if flags&2:data_size,pos=vint(buf,pos)
    out={'block_offset':offset,'header_bytes':end,'kind':kind,'flags':flags,
         'packed_bytes':data_size,'data_offset':offset+end,
         'next_offset':offset+end+data_size}
    if kind in (2,3):
        file_flags,pos=vint(buf,pos);unpacked,pos=vint(buf,pos);attributes,pos=vint(buf,pos)
        if file_flags&2:pos+=4
        if file_flags&4:out['data_crc32']=struct.unpack_from('<I',buf,pos)[0];pos+=4
        compression,pos=vint(buf,pos);host,pos=vint(buf,pos);length,pos=vint(buf,pos)
        name=buf[pos:pos+length].decode('utf-8')
        out.update(name=name,unpacked_bytes=unpacked,directory=bool(file_flags&1),
                   compression_method=(compression>>7)&7,solid=bool(compression&64))
    return out

class Reader:
    def __init__(self,url):self.url=url;self.bytes_read=0;self.requests=0
    def read(self,start,size=8192):
        for attempt in range(3):
            try:
                req=Request(self.url,headers={'Range':f'bytes={start}-{start+size-1}','User-Agent':'cryo-research/0.2'})
                with urlopen(req,timeout=30) as r:
                    if r.status!=206:raise ValueError('server did not honor HTTP range')
                    if not r.headers.get('Content-Range','').startswith(f'bytes {start}-'):
                        raise ValueError('server returned the wrong byte range')
                    value=r.read(size)
                self.bytes_read+=len(value);self.requests+=1;return value
            except Exception:
                if attempt==2:raise
                time.sleep(1+attempt)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--max-blocks',type=int,default=500)
    ap.add_argument('--output',default='data/phase2/archive-index.json');a=ap.parse_args()
    reader=Reader(URL);signature=reader.read(0,8)
    if signature!=b'Rar!\x1a\x07\x01\x00':raise ValueError('not RAR5')
    offset=8;blocks=[];status='block_limit';error=None
    try:
        for _ in range(a.max_blocks):
            b=parse_header(reader.read(offset),offset);blocks.append(b)
            if b['kind']==5:status='complete';break
            if b['kind']==4:raise ValueError('encrypted archive is unsupported')
            offset=b['next_offset']
    except Exception as e:status='partial';error=type(e).__name__+': '+str(e)
    out={'source_url':URL,'dataset_doi':'10.5281/zenodo.14038512',
         'retrieved_at':datetime.date.today().isoformat(),'status':status,'error':error,
         'http_requests':reader.requests,'bytes_downloaded':reader.bytes_read,'blocks':blocks}
    p=ROOT/a.output;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','error','http_requests','bytes_downloaded']}))
    print(json.dumps({'indexed_file_blocks':sum(b['kind']==2 for b in blocks)}))

if __name__=='__main__':main()
