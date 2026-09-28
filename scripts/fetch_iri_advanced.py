"""Fetch four small, pinned upstream hydration descriptor files."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "10ed726bed8158544222b5f16298a54013b6ad62"


def main():
    files = []
    for dataset in ("amino", "glyco2"):
        for representation in ("hydhist", "hydidx"):
            relative = f"data/descriptors/{representation}_{dataset}.csv"
            url = f"https://raw.githubusercontent.com/gcsosso/DOLMEN/{COMMIT}/{relative}"
            with urllib.request.urlopen(url, timeout=60) as response:
                content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise ValueError("Unexpected descriptor file size")
            path = ROOT / "data/raw/phase8/dolmen" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            files.append({"url": url, "local_path": str(path.relative_to(ROOT)),
                          "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    out = ROOT / "data/phase8"
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-manifest.json").write_text(json.dumps({"repository": "https://github.com/gcsosso/DOLMEN", "commit": COMMIT, "files": files}, indent=2) + "\n")
    print(f"Acquired {len(files)} descriptor files")


if __name__ == "__main__":
    main()
