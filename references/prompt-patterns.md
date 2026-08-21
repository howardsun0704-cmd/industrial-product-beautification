# Editing prompt patterns

## Structure-lock block

Use this block in every editing request and replace the bracketed checklist:

> Retouch this source image into a clean professional industrial catalog photograph. Treat the
> source as immutable geometry; make localized appearance improvements instead of replacing or
> re-rendering the product. Remove dust, lint, fingerprints, tiny stains, distracting superficial
> scratches, and uneven color cast. Improve controlled studio lighting, material consistency,
> local contrast, and edge clarity. Preserve exactly: [part count, holes, fasteners, joints,
> markings, viewing angle, proportions, silhouette, extremities, and open internal structures].
> Preserve every visible product pixel and all negative spaces between components. Do not crop,
> add, remove, relocate, merge, reconstruct, or redesign any component.

## Chroma-background block

Append one of these blocks:

**Magenta key**

> Place only the product on a perfectly uniform #FF00FF background. Use no floor, horizon,
> cast shadow, reflection, prop, text, logo, watermark, border, or decorative element. Preserve
> the source framing exactly and apply the framing rule below.

**Green key**

> Place only the product on a perfectly uniform #00FF00 background. Use no floor, horizon,
> cast shadow, reflection, prop, text, logo, watermark, border, or decorative element. Preserve
> the source framing exactly and apply the framing rule below.

## Framing rule

Inspect the source before selecting a framing instruction:

- If every product extremity is visible with background margin, keep the entire product visible
  and preserve the same viewing angle and silhouette.
- If any product pixel meets a source frame edge, treat the crop as immutable. Keep the same
  extremity clipped at the same edge; do not outpaint, reconstruct, round off, recenter, or reveal
  geometry outside the source.
- State the expected number of top-level product subjects and enclosed openings in the prompt.
  When either count is uncertain, route the item to visual review instead of guessing.

## Product-family checks

- Plastic or nylon: preserve molded edges, color identity, bore liners, seams, and surface
  texture. Avoid waxy smoothing or translucent hallucinations.
- Metal: preserve machining marks, threads, stamped text, holes, bends, and assembly seams.
  Reduce uncontrolled glare without flattening metallic response.
- Reflective products: ask for broad controlled highlights. Do not replace reflections with
  invented grooves, facets, or extra edges.
- Assemblies: enumerate every top-level subject, component, and fastener before editing. Record
  their left-to-right order and relative spacing; verify the same counts and arrangement after
  editing.
- Marked products: require exact retention of embossed or printed markings. If the model
  distorts a mark, preserve it from the source with a conventional image-editing step.

## Rejection conditions

Reject and regenerate only the affected image when any of these occurs:

- Hole, screw, washer, clamp, insert, extremity, or component count changes.
- Any source-visible product area disappears, becomes transparent, or is cropped.
- The viewing angle, handedness, proportions, bounding aspect ratio, or silhouette changes.
- Text or embossing becomes invented or illegible.
- Product pixels are removed with the chroma background.
- An enclosed opening is filled, fragmented, reduced, or contains opaque residue in the alpha.
- A colored fringe, opaque corner, fake shadow, floor, prop, or watermark remains.
