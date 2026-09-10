# Creating App Store Screenshot Packs

A skill for turning raw app screenshots into a reviewed, multi-platform marketing pack for the Apple App Store and Google Play.

Screenshots are classified by shape, compositions are laid out by a deterministic layout engine with separate phone and tablet catalogues, device correctness is validated before export, and the result ships as one ZIP with a provenance manifest.

## What it does differently

- **Real device handling.** A frame's screen area always matches the source screenshot's aspect ratio, so nothing is ever stretched into the wrong shape. Phone captures cannot produce tablet-shaped frames.
- **No fake tablets.** When only phone screenshots exist and a tablet export is requested, the skill uses a tablet layout tagged `promotional` that presents the phone as marketing artwork with a visible disclosure — and says a real tablet capture would be stronger. A phone capture is never framed as native tablet UI.
- **An adaptive layout engine.** 29 declarative templates across phone, tablet, and shared families. Layout is scored per screenshot against source shape, target family, screenshot count, headline length, promotional vs informational intent, position in the sequence, and what the set already used.
- **Sequence awareness.** The whole set is ordered before anything is composed: value proposition, core feature, secondary feature, management, notifications, customization.
- **Validation before export.** Phone frames in tablet exports, tablet frames in phone exports, up-scaled phone mockups, distorted screen areas, devices outside safe areas, clipped headlines, wrong export dimensions, and single-template sets are all rejected; the pipeline retries with the next-best layout.
- **One design system per pack.** Layouts vary, tokens do not.

## Requirements

- Python 3.11 or newer. No third-party Python dependency.
- A browser to display the confirmation gallery.
- Headless Chrome, Chromium, or Edge for rasterizing — optional; `--html-only` emits composition HTML for capture by other tooling.
- Internet access to verify current store dimensions.

## Installation

```bash
git clone https://github.com/ahmed-khaled-z/creating-app-store-screenshot-packs.git \
  ~/.claude/skills/creating-app-store-screenshot-packs
```

For Codex, clone into `~/.codex/skills/` instead. Confirm `SKILL.md` sits directly inside that directory. Start a new task if the skill is not offered in the current conversation.

Update with `git -C <skill dir> pull --ff-only`; uninstall by deleting the directory.

## Usage

Attach your screenshots, then:

```text
Create App Store and Google Play marketing screenshot packs from the attached screenshots.
App name: Schoolz
Language: English
Use the colors from the attached logo.
```

## Pipeline

1. Load and analyse every screenshot — dimensions, orientation, aspect ratio, device class.
2. Resolve each screenshot against each target: `native`, `promotional`, or `incompatible`.
3. Sequence the set by marketing role.
4. Build the confirmation gallery from real compositions and wait for a style code (`S1`–`S3`).
5. Select a layout per slide, resolve absolute geometry, render, validate, retry on failure.
6. Verify exact PNG dimensions, write the provenance manifest, produce the ZIP.

## Command line

```bash
python3 scripts/classify.py shot.png --target iphone --target ipad
python3 scripts/build_preview.py spec.json --out preview/gallery.html
python3 scripts/generate_pack.py spec.json --staging staging --report pack-report.json
python3 scripts/package_assets.py staging app-store-assets.zip --style S1 --language en \
  --size iphone=1290x2796 --size ipad=2048x2732 \
  --size android-phone=1080x1920 --size android-tablet=1600x2560 \
  --source 'iphone/01.png=/path/original.png' --pack-report pack-report.json
```

`generate_pack.py --html-only` plans, validates, and emits composition HTML without needing a browser binary.

## Layout catalogue

| Family | Templates |
|---|---|
| `phone` | hero-centered, hero-offset-left, hero-offset-right, hero-oversized, hero-cropped-bottom, floating-device, dual-side-by-side, dual-overlap, staggered-pair, foreground-background, angled-pair, triple-showcase, feature-spotlight, feature-comparison, step-sequence |
| `tablet` | tablet-hero, tablet-hero-landscape, tablet-portrait-centered, tablet-with-side-content, tablet-with-cards, dual-tablet, tablet-split-showcase |
| `tablet` (promotional) | tablet-promo-phone-showcase, tablet-promo-phone-offset, tablet-promo-phone-cards, tablet-promo-phone-editorial, tablet-promo-phone-trio |
| `shared` | marketing-showcase, sequence-strip |

Styles: `S1 Clean Cream`, `S2 Bold Brand`, `S3 Soft Gradient`.

## ZIP structure

```text
app-store-assets.zip
└── app-store-assets/
    ├── manifest.json
    ├── iphone/01.png …
    ├── ipad/
    ├── android-phone/
    └── android-tablet/
```

`manifest.json` records the style, language, dimensions, adapted platforms, and, per output, the original source screenshot, layout template, presentation mode, and device family.

## Repository structure

```text
SKILL.md                      Skill workflow
agents/openai.yaml            Codex display metadata
scripts/devices.py            Device families, classification, frame geometry
scripts/analyzer.py           Screenshot and set analysis
scripts/layouts/              Declarative layout templates
scripts/layout_engine.py      Layout selection, geometry, typography
scripts/style.py              Design tokens per style direction
scripts/render.py             Composition HTML and rasterization
scripts/validate.py           Device and set validation
scripts/generate_pack.py      Pipeline orchestration
scripts/build_preview.py      Confirmation gallery
scripts/classify.py           Standalone classification report
scripts/package_assets.py     Dimension checks, manifest, ZIP
scripts/test_*.py             Regression checks
```

## Known limitations

- Marketing role detection uses filename and label keywords, not screenshot content. Pass a `label` per slide for reliable sequencing.
- Landscape tablet templates need landscape captures; a portrait capture will not be rotated into them.
- Headless Chrome is the only bundled rasterizer. Where it is unavailable or blocked, use `--html-only` and capture the emitted HTML at 1× device scale factor.
- Sanitization of personal or demo data happens before the pipeline; the renderer never edits screenshot pixels.

## Tests

```bash
python3 scripts/test_pipeline.py
python3 scripts/test_build_preview.py
python3 scripts/test_package_assets.py
```

## License

[MIT](LICENSE)
