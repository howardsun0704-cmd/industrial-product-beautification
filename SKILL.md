---
name: industrial-product-beautification
description: Retouch industrial product photographs into clean, structure-faithful catalog assets with transparent PNG delivery, chroma-key extraction, edge cleanup, standard canvas sizing, batch QA reports, and before/after review sheets. Use for product photo beautification, industrial catalog imagery, transparent-background cutouts, dust/scratch/reflection cleanup, material enhancement, batch image normalization, or QA of edited machinery, fittings, clamps, handles, fasteners, metal, nylon, and plastic components.
---

# Industrial Product Beautification

Produce polished catalog images without changing engineering facts. Treat holes, fasteners,
threads, seams, markings, part count, viewing angle, proportions, and silhouette as immutable.

## Required workflow

1. Choose one authoritative source root, inventory every supported image beneath it, and keep
   every original read-only. Exclude prior output, QA, cache, and intermediate directories from
   discovery. Create a stable manifest before editing; record the source path, deterministic
   output path, processing status, QA path, and generated asset identifier for every item. Bind
   each generated asset to its source using explicit response metadata. Never infer this mapping
   from parallel completion order, timestamps, or directory sorting. If the editing service does
   not return stable identifiers, process edits sequentially.
2. Inspect representative images and record a structure checklist for each product family:
   part count, hole count and position, fasteners, joints, text/embossing, color, material,
   viewing angle, proportions, and open internal areas. Run the source preflight before editing.
   Record every frame edge touched by product pixels. Edge-contact sources enter crop-lock mode:
   the edit must retain the same clipped extremity and must never reveal geometry outside the
   source.
3. Create a small pilot across materially different products before starting a large batch.
   Include plastic, metal, dark, reflective, and structurally complex items when present.
4. Edit with an image-editing model. Clean dust, lint, fingerprints, minor stains, distracting
   scratches, uneven color cast, and uncontrolled reflections. Improve catalog lighting,
   material clarity, local contrast, and edge definition.
5. Require a pure chroma background and no cast shadow, floor, props, text, logo, watermark,
   or added object. Read [prompt-patterns.md](references/prompt-patterns.md) before composing
   the editing prompt. State the expected top-level subject count, enclosed-opening count, and
   either full-frame or crop-lock framing rule in every request. For large jobs, work in
   small reviewable batches and verify each response against the manifest before finalization. Regenerate any item with unsafe gradients, gray
   backgrounds, structural changes, or key colors that overlap the product; do not compensate
   with broad destructive thresholds.
6. Choose the key color with the lowest overlap with the product:
   - Use magenta for green products and most cool-colored plastics.
   - Use green for silver, gray, black, neutral metal, and warm-colored products.
   - If both colors occur materially in the product, choose another extraction method; do not
     erase legitimate product pixels to force chroma keying.
7. Work from the manifest in small batches. After each batch, compare every keyed asset with its
   source, confirm its asset identifier and target path, and redo only the failing item before
   continuing.
8. Convert each keyed edit with `scripts/finalize_keyed_product.py`. Preserve relative source
   folders, append `_beautified` to the filename, and write one QA JSON per image. Its default
   strict structure policy compares the original with the extracted alpha and rejects subject
   loss, missing openings, source-edge crops, fragmented hole edges, and large silhouette drift.
   Keep `--interior-key auto`; inspect protected interior key pixels before overriding it.
   Apply despill only to selected background pixels. A review-only crop may use
   `--structure-policy warn --approve-structure-review` only after direct human comparison;
   a hard structure failure can never be approved.
9. Validate with `scripts/validate_outputs.py` using `--original-root <source-root>
   --structure-policy strict`. The source tree, not a manually entered output count, defines
   the expected set. Read [completeness-and-retention.md](references/completeness-and-retention.md)
   when interpreting completeness, protected-key, structure, or review-approval results. Approve
   a review-only finding only by repeating `--approve-structure-review` with its exact relative
   output path.
10. Create review sheets with `scripts/make_qa_sheet.py`, then visually compare every output
    with its original. Automatic file and alpha checks do not prove structural fidelity. Reject
    invented, missing, relocated, cropped, or distorted features.
11. Deliver only after every readable source maps to exactly one valid output, no hard structure
    failure remains, and every review-only finding has a recorded per-file visual approval.
    Report damaged sources separately; never silently omit them.
    Unexpected legacy files in a mixed output root must be reported separately and must never be
    deleted, moved, or overwritten without explicit authorization.

## Output contract

- Keep originals untouched and preserve their relative directory structure.
- Keep source, original, keyed-copy, final-output, and QA paths pairwise distinct. Publish
  artifacts through same-directory temporary files and atomic replacement; a failed publish
  must restore prior files and leave no partial new delivery.
- Produce exactly one correctly named output for every readable source image.
- Deliver PNG in RGBA mode on a square canvas; default to 2048 x 2048.
- Keep all four corner alpha values at zero and preserve transparency through holes and open
  structures.
- Center the product without stretching it. Default maximum occupancy is 90% of the canvas.
- Use `<original-stem>_beautified.png` for final assets.
- Keep keyed intermediates, individual QA JSON files, and review sheets outside the final
  delivery directory.

Recommended job layout:

```text
job/
  originals/
  keyed/
  outputs/
  qa/reports/
  qa/sheets/
```

## Script commands

Finalize one keyed image:

```bash
python scripts/finalize_keyed_product.py \
  --source job/keyed/part-magenta.png \
  --original job/originals/part.jpg \
  --key magenta \
  --output job/outputs/part_beautified.png \
  --qa job/qa/reports/part.json \
  --batch-id B01 \
  --structure-policy strict
```

Validate a delivery set:

```bash
python scripts/validate_outputs.py \
  --original-root job/originals \
  --root job/outputs \
  --report job/qa/validation.json \
  --structure-policy strict
```

Build a visual review sheet:

```bash
python scripts/make_qa_sheet.py \
  --qa-root job/qa/reports \
  --batch-id B01 \
  --output job/qa/sheets/B01.png
```

## Human documentation

- Read [guide.zh-CN.md](references/guide.zh-CN.md) for Chinese deployment, usage, and
  operating instructions.
- Read [guide.en.md](references/guide.en.md) for the English version.
