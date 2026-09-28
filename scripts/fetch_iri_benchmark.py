"""Acquire a small, commit-pinned subset of DOLMEN; never execute upstream code."""
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "10ed726bed8158544222b5f16298a54013b6ad62"
PATHS = ["LICENSE", "README.md", "data/datasets/README.md",
         "data/descriptors/README.md"] + [
    f"data/{folder}/{prefix}{name}.csv"
    for name in ("amino", "glyco", "glyco2")
    for folder, prefix in (("datasets", ""), ("descriptors", "std_"))
]
PRIMARY = [
    ("paper-PMC11402961.xml", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11402961/fullTextXML"),
    ("figure4.png", "https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41467-024-52266-w/MediaObjects/41467_2024_52266_Fig4_HTML.png"),
]


def main():
    manifest = {"repository": "https://github.com/gcsosso/DOLMEN", "commit": COMMIT,
                "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "files": []}
    for relative in PATHS:
        url = f"https://raw.githubusercontent.com/gcsosso/DOLMEN/{COMMIT}/{relative}"
        req = urllib.request.Request(url, headers={"User-Agent": "cryo-research-benchmark"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Unexpected source size")
        path = ROOT / "data/raw/phase7/dolmen" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["files"].append({"upstream_path": relative,
            "local_path": str(path.relative_to(ROOT)), "url": url, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()})
    target = ROOT / "data/phase7/source-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    primary = {"doi": "10.1038/s41467-024-52266-w", "files": []}
    for filename, url in PRIMARY:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Unexpected primary-source size")
        path = ROOT / "data/raw/phase7" / filename
        path.write_bytes(content)
        primary["files"].append({"url": url, "local_path": str(path.relative_to(ROOT)),
                                  "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    (target.parent / "primary-source-manifest.json").write_text(json.dumps(primary, indent=2) + "\n")
    print(json.dumps({"files": len(PATHS), "bytes": sum(f["bytes"] for f in manifest["files"])}))


if __name__ == "__main__":
    main()
