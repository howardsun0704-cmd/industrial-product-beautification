---
name: industrial-product-beautification
description: Retouch industrial product photographs into clean, structure-faithful catalog assets with transparent PNG delivery, chroma-key extraction, edge cleanup, standard canvas sizing, batch QA reports, and before/after review sheets. Use for product photo beautification, industrial catalog imagery, transparent-background cutouts, dust/scratch/reflection cleanup, material enhancement, batch image normalization, or QA of edited machinery, fittings, clamps, handles, fasteners, metal, nylon, and plastic components.
---

# Industrial Product Beautification

Produce polished catalog images without changing engineering facts. Treat holes, fasteners,
threads, seams, markings, part count, viewing angle, proportions, and silhouette as immutable.

## Required workflow

1. Discover the source set and keep every original read-only. Exclude prior output, QA, cache,
   and intermediate directories from discovery.
2. Inspect representative images and record a structure checklist for each product family:
   part count, hole count and position, fasteners, joints, text/embossing, color, material,
   viewing angle, proportions, and open internal areas.
3. Create a small pilot across materially different products before starting a large batch.
   Include plastic, metal, dark, reflective, and structurally complex items when present.
4. Edit with an image-editing model. Clean dust, lint, fingerprints, minor stains, distracting
   scratches, uneven color cast, and uncontrolled reflections. Improve catalog lighting,
   material clarity, local contrast, and edge definition.
5. Require a pure chroma background and no cast shadow, floor, props, text, logo, watermark,
   or added object. Read [prompt-patterns.md](references/prompt-patterns.md) before composing
   the editing prompt.
6. Choose the key color with the lowest overlap with the product:
   - Use magenta for green products and most cool-colored plastics.
   - Use green for silver, gray, black, neutral metal, and warm-colored products.
   - If both colors occur materially in the product, choose another extraction method; do not
     erase legitimate product pixels to force chroma keying.
7. Convert each keyed edit with `scripts/finalize_keyed_product.py`. Preserve relative source
   folders, append `_beautified` to the filename, and write one QA JSON per image.
8. Validate the whole set with `scripts/validate_outputs.py`, then create batch review sheets
   with `scripts/make_qa_sheet.py`.
9. Visually compare each output with its original. Automatic alpha checks do not prove
   structural fidelity. Reject invented, missing, relocated, or distorted features.
10. Deliver only after every automatic failure is resolved and every visual structure check
    passes. Report unreadable or damaged source files separately; never silently omit them.

## Output contract

- Keep originals untouched and preserve their relative directory structure.
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
  --batch-id B01
```

Validate a delivery set:

```bash
python scripts/validate_outputs.py \
  --root job/outputs \
  --report job/qa/validation.json \
  --expected 12
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

