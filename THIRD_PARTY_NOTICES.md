# Third-party notices and provenance

Delphi's original application code uses the repository's Apache-2.0 license. Its Python package declares dependencies but does not bundle their code, a Python interpreter, or model weights. Dependencies and models retain their own licenses and notices in their separately installed distributions.

## Dependencies

The tested direct dependencies are CocoIndex 1.0.24 (Apache-2.0), sqlite-vec 0.1.9 (MIT or Apache-2.0), SentenceTransformers 6.1.0 (Apache-2.0), NumPy 2.5.3 (BSD and bundled component notices), and pathspec 0.12.1 (MPL-2.0). They were installed from PyPI without modification. Exact transitive dependency versions are recorded in `requirements-lock.txt`; this version freeze does not authenticate wheel contents.

For a release that bundles dependencies, collect their licenses and notices from the actual release environment with `scripts/collect_notices.py`. During online preparation, `scripts/prepare_notices.py` retrieves supplemental upstream license texts omitted from the tested wheels. Both write to `build/third_party/`. Review the collection against the release contents, include required native-library and interpreter notices, and meet applicable source-availability obligations. The generated collection is excluded from the application package and source repository.

## Test model

- Repository: [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41)
- Revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- Declared model license: Apache-2.0, as recorded in its upstream model card.
- Asset hashes: `MODEL_PROVENANCE.json`.

The provisioned model directory under `.models/` retains its upstream model card, Apache license text, and provenance manifest alongside the weights. The pinned repository has no separate LICENSE file, so `scripts/prepare_model.py` supplies the canonical Apache text alongside the model card's declaration. Preserve these records when distributing the model. Replacement models require their own provenance and license review.
