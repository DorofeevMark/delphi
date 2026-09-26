import json
from pathlib import Path
import sys
from urllib.request import urlopen


def main():
    from huggingface_hub import snapshot_download

    manifest = json.loads(Path(__file__).with_name("model_provenance.json").read_text())
    destination = Path(sys.argv[1])
    snapshot_download(
        manifest["repository"], revision=manifest["revision"], local_dir=destination,
        allow_patterns=list(manifest["sha256"]),
    )
    if not (destination / "LICENSE").exists():
        with urlopen("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=60) as response:
            (destination / "LICENSE").write_bytes(response.read())


if __name__ == "__main__":
    main()
