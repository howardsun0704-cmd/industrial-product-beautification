# Editing prompt patterns

## Structure-lock block

Use this block in every editing request and replace the bracketed checklist:

> Retouch this image into a clean professional industrial catalog photograph. Remove dust,
> lint, fingerprints, tiny stains, distracting superficial scratches, and uneven color cast.
> Improve controlled studio lighting, material consistency, local contrast, and edge clarity.
> Preserve exactly: [part count, holes, fasteners, joints, markings, viewing angle, proportions,
> silhouette, and open internal structures]. Do not add, remove, relocate, merge, or redesign
> any component.

## Chroma-background block

Append one of these blocks:

**Magenta key**

> Place only the product on a perfectly uniform #FF00FF background. Use no floor, horizon,
> cast shadow, reflection, prop, text, logo, watermark, border, or decorative element. Keep the
> full product inside the frame with comfortable margins.

**Green key**

> Place only the product on a perfectly uniform #00FF00 background. Use no floor, horizon,
> cast shadow, reflection, prop, text, logo, watermark, border, or decorative element. Keep the
> full product inside the frame with comfortable margins.

## Product-family checks

- Plastic or nylon: preserve molded edges, color identity, bore liners, seams, and surface
  texture. Avoid waxy smoothing or translucent hallucinations.
- Metal: preserve machining marks, threads, stamped text, holes, bends, and assembly seams.
  Reduce uncontrolled glare without flattening metallic response.
- Reflective products: ask for broad controlled highlights. Do not replace reflections with
  invented grooves, facets, or extra edges.
- Assemblies: enumerate every visible component and fastener before editing. Verify the same
  count after editing.
- Marked products: require exact retention of embossed or printed markings. If the model
  distorts a mark, preserve it from the source with a conventional image-editing step.

## Rejection conditions

Reject and regenerate only the affected image when any of these occurs:

- Hole, screw, washer, clamp, insert, or component count changes.
- The viewing angle, handedness, proportions, or silhouette changes.
- Text or embossing becomes invented or illegible.
- Product pixels are removed with the chroma background.
- A colored fringe, opaque corner, fake shadow, floor, prop, or watermark remains.

