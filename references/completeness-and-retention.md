# Completeness and pixel-retention checks

Read this reference when finalizing keyed images or validating a batch.

## Choose one authoritative source root

Select the directory whose immediate descendants should be reproduced under the output root.
Use that same path for source discovery, output-path construction, and
`validate_outputs.py --original-root`. A different root changes every expected relative path.

Do not infer completeness from the number of outputs and do not change `--expected` to match
what was produced. The source directory is authoritative. A valid delivery has exactly one
`<source-stem>_beautified.png` for every readable source image at the same relative path.

## Interpret key-extraction metrics

`finalize_keyed_product.py` writes a `key_extraction` object to each QA JSON:

- `border_connected_key_pixels`: key-like pixels connected to the canvas edge and removed as
  background.
- `interior_key_candidate_pixels`: key-like pixels enclosed inside the product silhouette.
- `removed_interior_key_pixels`: near-pure key pixels removed as enclosed holes in `auto`
  mode.
- `protected_interior_key_pixels`: ambiguous enclosed pixels retained to avoid deleting valid
  product color.

The default `--interior-key auto` is the safest general mode. If protected pixels are reported,
inspect the keyed intermediate and the final alpha at those locations. Regenerate with a
non-overlapping key color when the product materially overlaps the key.

Use `--interior-key preserve` when all enclosed key-like color belongs to the product and hole
transparency will be handled separately. Use `--interior-key remove` only after visual
confirmation that every enclosed candidate is background visible through a real opening; this
mode can delete legitimate product pixels.

## Completion gate

Run source-aware validation before delivery:

```bash
python scripts/validate_outputs.py \
  --original-root job/originals \
  --root job/outputs \
  --report job/qa/validation.json
```

The report must have:

- `automatic_checks_passed: true`
- `missing_output_count: 0`
- `unexpected_output_count: 0`
- no duplicate expected output paths
- no unapproved unreadable originals

Automatic checks prove file and alpha completeness only. Review before/after sheets for missing
parts, altered geometry, cropped extremities, changed markings, and incorrect holes before
delivery.
