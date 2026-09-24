import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

sources = {
    "sqlite-vec/LICENSE-MIT": "https://raw.githubusercontent.com/asg017/sqlite-vec/v0.1.9/LICENSE-MIT",
    "sqlite-vec/LICENSE-APACHE": "https://raw.githubusercontent.com/asg017/sqlite-vec/v0.1.9/LICENSE-APACHE",
    "tokenizers/LICENSE": "https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.2/LICENSE",
    "tqdm/LICENCE": "https://raw.githubusercontent.com/tqdm/tqdm/v4.70.1/LICENCE",
    "cocoindex/LICENSE": "https://raw.githubusercontent.com/cocoindex-io/cocoindex/v1.0.24/LICENSE",
    "model/LICENSE": "https://www.apache.org/licenses/LICENSE-2.0.txt",
}
records = {}
for relative, url in sources.items():
    target = Path("build/third_party") / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response:
        data = response.read()
    target.write_bytes(data)
    records[relative] = {"source": url, "sha256": hashlib.sha256(data).hexdigest()}
(Path("build/third_party") / "supplemental-sources.json").write_text(json.dumps(records, indent=2) + "\n")
