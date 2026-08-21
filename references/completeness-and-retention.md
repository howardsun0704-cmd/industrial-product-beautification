# Completeness and pixel-retention checks

Read this reference when finalizing keyed images or validating a batch.

## Choose one authoritative source root

Select the directory whose immediate descendants should be reproduced under the output root.
Use that same path for source discovery, output-path construction, and
`validate_outputs.py --original-root`. A different root changes every expected relative path.

Do not infer completeness from the number of outputs and do not change `--expected` to match
what was produced. The source directory is authoritative. A valid delivery has exactly one
`<source-stem>_beautified.png` for every readable source image at the same relative path.

## Bind generated assets deterministically

Before editing, create a manifest that fixes each source path, target path, processing status,
QA path, and generated asset identifier. Bind responses by an explicit identifier returned by
the editing service. Parallel completion order, file modification time, and directory sorting
are not valid identity signals. If stable response identifiers are unavailable, process one
source at a time.

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
Despill only pixels that the removal mask selected as background or antialiased fringe. Protected
interior product pixels must retain both their original alpha and RGB values.


Use `--interior-key preserve` when all enclosed key-like color belongs to the product and hole
transparency will be handled separately. Use `--interior-key remove` only after visual
confirmation that every enclosed candidate is background visible through a real opening; this
mode can delete legitimate product pixels.

## Source/output structure gate

The structure checker derives a conservative foreground mask from the original border color and
compares it with the final alpha at a reduced analysis resolution. It checks:

- major connected product-subject count;
- enclosed opening count and normalized transparent area;
- fragmented opening boundaries that indicate opaque residue;
- source product contact with a frame edge;
- large silhouette aspect-ratio changes.

Findings are intentionally two-level:

- severity: fail covers high-confidence loss, such as fewer major subjects, fewer enclosed
  openings, or a collapsed transparent opening. These findings cannot be approved.
- severity: review covers ambiguous changes, including a source crop, moderately reduced
  opening area, fragmented opening edges, and silhouette-ratio drift. These block delivery until
  the exact source/output pair is visually compared.

Use strict structure validation for delivery. A reviewed warning may be approved only by its
exact relative output path:

~~~bash
python scripts/validate_outputs.py \
  --original-root job/originals \
  --root job/outputs \
  --report job/qa/validation.json \
  --structure-policy strict \
  --approve-structure-review family/cropped-part_beautified.png
~~~

Approval is path-specific and does not suppress a hard failure on that file. Never change a
threshold or approve a whole directory merely to make a batch pass.

## Completion gate

Run source-aware validation before delivery:

```bash
python scripts/validate_outputs.py \
  --original-root job/originals \
  --root job/outputs \
  --report job/qa/validation.json
```

The source-coverage gate requires:

- `missing_output_count: 0`
- no duplicate expected output paths
- no unapproved unreadable originals
- every expected output to pass the per-file dimension, mode, alpha, and naming checks

In a dedicated delivery root, also require `unexpected_output_count: 0` and
`automatic_checks_passed: true`. In a mixed legacy output root, unexpected files may make the
top-level automatic flag false even when the complete expected set passes. Report those files
separately and get explicit authorization before deleting, moving, overwriting, or otherwise
changing them.

Automatic checks prove file and alpha completeness only. Review before/after sheets for missing
parts, altered geometry, cropped extremities, changed markings, and incorrect holes before
delivery.
