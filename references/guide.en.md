# Industrial Product Beautification Skill: Deployment, Usage, and Operations

## 1. Purpose

This Skill turns photos of industrial parts, clamps, fasteners, handles, metal, nylon, and
plastic components into clean transparent PNG catalog assets. It improves surfaces without
changing engineering facts. Hole locations and counts, bolts, washers, seams, markings, part
count, viewing angle, proportions, and silhouette must remain identical to the source.

The standard workflow covers source discovery, a structural checklist, pilot review, AI image
editing, structure-safe chroma-key extraction, 2048-square normalization, per-image QA,
source-derived full-set validation, and before/after visual review.

## 2. Environment deployment

### 2.1 Requirements

- Codex desktop or another Codex environment with Skills and image-editing capability
- Python 3.10 or newer
- Git, when installing from GitHub
- Python packages: NumPy and Pillow

### 2.2 Install the Skill

Clone the repository into the Codex Skills directory. Windows PowerShell:

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' }
git clone https://github.com/howardsun0704-cmd/industrial-product-beautification.git (Join-Path $skillsRoot 'industrial-product-beautification')
```

macOS / Linux:

```bash
git clone https://github.com/howardsun0704-cmd/industrial-product-beautification.git "${CODEX_HOME:-$HOME/.codex}/skills/industrial-product-beautification"
```

Start a new Codex task after installation and invoke `$industrial-product-beautification`.

### 2.3 Install script dependencies

Run these commands inside the Skill directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate`.

## 3. Usage

Attach images or provide a source directory and invoke the Skill explicitly. Example:

```text
Use $industrial-product-beautification on the industrial clamp photos in this directory.
Preserve all holes, bolts, markings, viewing angles, and proportions. Deliver 2048x2048
transparent PNGs. Create a five-image cross-material pilot first, then process the batch and
produce QA reports and before/after sheets.
```

Validation-only example:

```text
Use $industrial-product-beautification to validate the transparent PNG files in outputs and
compare them with the originals for structural changes.
```

## 4. Operating procedure

### 4.1 Recommended directories

```text
job/
  originals/       read-only source images
  keyed/           AI-edited pure chroma intermediates
  outputs/         final transparent PNG files
  qa/reports/      per-image QA JSON files
  qa/sheets/       batch comparison sheets
```

### 4.2 Select a key color

- Green or cyan plastic: use magenta `#FF00FF`.
- Silver, gray, black, neutral metal, or warm colors: use green `#00FF00`.
- If the product materially contains both green and magenta, use a different extraction method
  that cannot remove valid product pixels.

The AI intermediate must contain only the product and a perfectly uniform key background. It
must not contain a floor, horizon, shadow, reflection, prop, text, watermark, or border.

### 4.3 Produce a transparent asset

```powershell
python scripts/finalize_keyed_product.py `
  --source job/keyed/part-magenta.png `
  --original job/originals/part.jpg `
  --key magenta `
  --output job/outputs/part_beautified.png `
  --qa job/qa/reports/part.json `
  --batch-id B01
```

`--key auto` detects green or magenta from the image border. Specify the key explicitly for
production batches. The defaults are a 2048x2048 canvas and 90% maximum product occupancy;
override them with `--canvas` and `--occupancy`.

The default `--interior-key auto` removes key-like background connected to the canvas edge and
treats only near-pure enclosed key regions as holes. The QA JSON `key_extraction` object records
border-connected, removed-interior, and protected-interior pixel counts. Inspect unexpected
interior candidates in the keyed image and final alpha. Prefer a non-overlapping key color; do
not force `--interior-key remove` when it could erase product color.

### 4.4 Validate the full delivery

```powershell
python scripts/validate_outputs.py `
  --original-root job/originals `
  --root job/outputs `
  --report job/qa/validation.json
```

The validator treats `--original-root` as authoritative. It requires exactly one
`<source-stem>_beautified.png` at the matching relative path for every readable source and
reports missing outputs, unexpected outputs, wrong directory levels, name collisions, and
unreadable originals. It also checks PNG/RGBA format, size, transparent corners, fully
transparent and opaque pixels, and canvas-edge contact. Do not change `--expected` to the
current output count to hide a failure. A nonzero exit code means the delivery is incomplete or
an output check failed.

### 4.5 Create a batch review sheet

```powershell
python scripts/make_qa_sheet.py `
  --qa-root job/qa/reports `
  --batch-id B01 `
  --output job/qa/sheets/B01.png
```

Compare each result with its source for holes, bolts, washers, seams, text, orientation,
proportions, and silhouette. Passing alpha checks does not prove structural fidelity; reject
any image with an engineering-structure change.

## 5. Delivery standard

- Never overwrite, rename, or delete originals.
- Produce exactly one output per readable source, name it `<source-stem>_beautified.png`, and
  preserve relative directories.
- Default to 2048x2048 PNG, RGBA, with alpha zero at all four corners.
- Preserve transparency through holes and open structures.
- Add no text, brand, watermark, prop, floor, shadow, or decoration.
- Report unreadable or damaged sources separately; never omit them silently.
