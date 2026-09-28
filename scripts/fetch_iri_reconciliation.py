"""Acquire the two public supplements needed for the Phase 9 source audit."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def read(url, limit):
    with urllib.request.urlopen(url, timeout=60) as response:
        value = response.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Source exceeds acquisition cap")
    return value


def main():
    raw = ROOT / "data/raw/phase9"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {"files": []}
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11402961/supplementaryFiles"
    content = read(url, 25_000_000)
    archive = zipfile.ZipFile(io.BytesIO(content))
    member = "41467_2024_52266_MOESM1_ESM.pdf"
    if archive.getinfo(member).file_size > 12_000_000:
        raise ValueError("Supplement exceeds extraction cap")
    pdf = archive.read(member)
    if not pdf.startswith(b"%PDF"):
        raise ValueError("Not a PDF")
    path = raw / "warren-2024-supplement.pdf"
    path.write_bytes(pdf)
    manifest["files"].append({"url": url, "member": member,
        "local_path": str(path.relative_to(ROOT)), "bytes": len(pdf),
        "sha256": hashlib.sha256(pdf).hexdigest(), "archive_sha256": hashlib.sha256(content).hexdigest()})
    metadata_url = "https://api.figshare.com/v2/articles/29185191"
    metadata = read(metadata_url, 1_000_000)
    info = json.loads(metadata)
    if info["resource_doi"] != "10.1021/acs.cgd.5c00221":
        raise ValueError("Unexpected Figshare source DOI")
    item = next(f for f in info["files"] if f["id"] == 54935598)
    pdf = read(item["download_url"], 12_000_000)
    if not pdf.startswith(b"%PDF") or hashlib.md5(pdf).hexdigest() != item["computed_md5"]:
        raise ValueError("Source PDF/MD5 mismatch")
    path = raw / "acs-2025-si.pdf"
    path.write_bytes(pdf)
    manifest["files"].append({"url": item["download_url"], "local_path": str(path.relative_to(ROOT)),
        "bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(), "md5": item["computed_md5"]})
    path = raw / "acs-2025-si-metadata.json"
    path.write_bytes(metadata)
    manifest["files"].append({"url": metadata_url, "local_path": str(path.relative_to(ROOT)),
        "bytes": len(metadata), "sha256": hashlib.sha256(metadata).hexdigest()})
    out = ROOT / "data/phase9"
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified and saved {len(manifest['files'])} source files")


if __name__ == "__main__":
    main()
