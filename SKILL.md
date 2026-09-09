---
name: creating-app-store-screenshot-packs
description: Use when users want promotional app screenshots, App Store or Google Play screenshot sets, device-specific marketing images, or a packaged multi-platform screenshot ZIP.
---

# Creating App Store Screenshot Packs

Turn supplied app screenshots into a store-ready marketing pack. Device family, screenshot shape, marketing copy, composition, and export size are decided together before anything is rendered. Compositions are laid out deterministically by `scripts/`, not improvised per image, and device correctness is validated before export.

## Non-negotiables

- A tablet export shows tablet UI. A phone capture is never framed as a tablet.
- A frame's screen area always matches the source screenshot's aspect ratio, so screenshots are never stretched, squashed, or letterboxed inside the wrong shape.
- Phone and tablet targets use different layout catalogues, not one catalogue scaled up.
- No composition is painted over the application UI; device chrome is drawn in the bezel.
- A set varies its layouts while keeping one typography scale, palette, background, device style, shadow, radius, and spacing system.

## Workflow

1. **Inspect the inputs.** Record each screenshot's filename, represented screen, sensitive or demo data, and marketing value.

2. **Resolve missing essentials only:** app name, output language, brand colours, and whether screenshots may be adapted across platforms. Infer language from the screenshots when unambiguous.

3. **Classify every screenshot.** Run the analyzer to get device class, orientation, aspect ratio, and target compatibility before choosing anything:

   ```bash
   python3 scripts/classify.py SCREENSHOT [SCREENSHOT ...] --target iphone --target ipad
   ```

   The `presentation` field per screenshot/target decides what happens next:
   - `native` / `native-offspec` — render normally.
   - `promotional` — the source is a phone capture and the target is a tablet. Only tablet layouts tagged `promotional` are eligible; they present the phone as marketing artwork and carry a visible disclosure. Tell the user a real tablet capture would be stronger, and capture one from the project if you have access.
   - `incompatible` — a tablet capture against a phone target. Stop that platform and ask for real phone screenshots. Never crop tablet UI into a phone frame.

4. **Browse current accepted dimensions.** Use only official Apple App Store Connect documentation on `developer.apple.com` and official Google Play Console documentation on `support.google.com`. Choose one accepted portrait size per platform and keep the source URLs. `scripts/devices.py` carries documented defaults for reference only; the runtime lookup wins.

5. **Sanitize.** Replace personal, payment, credential, notification, and obvious test or demo data with neutral values in the screenshots you pass to the pipeline. Do not otherwise alter the application UI.

6. **Write the spec.** One JSON file drives both the gallery and the export:

   ```json
   {
     "app_name": "Schoolz",
     "language": "en",
     "brand": { "brand": "#5b4bdb", "brand_strong": "#2f246f", "accent": "#ffb35c" },
     "targets": {
       "iphone": {
         "size": [1290, 2796],
         "slides": [
           { "sources": ["/path/01-home.png"], "label": "home",
             "title": "Plan every school day",
             "subtitle": "Timetables, homework and grades in one place" },
           { "sources": ["/path/02-grades.png", "/path/03-chat.png"], "label": "dashboard",
             "title": "Track progress live", "subtitle": "Results update instantly" }
         ]
       }
     }
   }
   ```

   A slide with two or three `sources` becomes one multi-device composition. `label` steers sequencing and headline tone; `captions` and `bullets` feed layouts that use them; `layout` pins a template when you need a specific one. Slides are re-ordered into a marketing sequence automatically — value proposition first, then core feature, secondary feature, management, notifications, customization.

7. **Build and show the gallery.** Layouts are chosen by the engine; the user confirms a style direction:

   ```bash
   python3 scripts/build_preview.py spec.json --out preview/gallery.html
   ```

   Open the file in a visible browser and check every card renders. Each card shows its chosen layout and a `native` or `promotional` badge. Ask the user to pick and paste a code matching `S1` through `S3`. A text-only list does not complete this step; if the gallery cannot be shown, report that blocker before requesting a choice.

8. **Render after confirmation.**

   ```bash
   python3 scripts/generate_pack.py spec.json --staging staging --report pack-report.json
   ```

   This analyses, sequences, selects a layout per slide, resolves geometry, renders, validates, and retries with the next-best layout when validation fails. It rasterises with headless Chrome when available. Without a browser, add `--html-only`: it writes `staging/PLATFORM/NN.html` at exact canvas size for you to screenshot with your own browser tooling at 1× device scale factor.

9. **Check the output.** Read `pack-report.json` for the chosen layout, presentation mode, and warnings per file. Look at the rendered PNGs for spelling, claims, and fidelity before packaging.

10. **Package.** Stage exactly four non-empty folders named `iphone`, `ipad`, `android-phone`, and `android-tablet` containing only `01.png`, `02.png`, … in presentation order, then:

    ```bash
    python3 scripts/package_assets.py staging app-store-assets.zip \
      --layout AUTO --style S1 --language en \
      --size iphone=WIDTHxHEIGHT --size ipad=WIDTHxHEIGHT \
      --size android-phone=WIDTHxHEIGHT --size android-tablet=WIDTHxHEIGHT \
      --source 'iphone/01.png=/path/to/original-iphone.png' \
      --source 'ipad/01.png=/path/to/original-ipad.png' \
      --pack-report pack-report.json \
      --adapted android-phone
    ```

    Every staged output needs one `--source` naming an existing supplied screenshot, not a sanitized or rendered derivative. `--pack-report` records the layout template, presentation mode, and device family per file. Add `--adapted` per adapted platform. Inspect the exit status; on failure fix the reported input rather than hand-building the archive. On success inspect the ZIP listing and `app-store-assets/manifest.json`, return the ZIP, and summarize the confirmed style, language, dimensions, layouts, source mappings, and adaptations.

## Architecture

| Module | Responsibility |
|---|---|
| `scripts/devices.py` | `DeviceFamily` config, `DeviceClassifier`, `TargetDeviceResolver`, `DeviceFrameResolver` |
| `scripts/analyzer.py` | `ScreenshotAnalyzer` (cached geometry, role, intent), `SetAnalyzer` (sequence, summary) |
| `scripts/layouts/` | Declarative templates under `phone/`, `tablet/`, `shared/` |
| `scripts/layout_engine.py` | `LayoutLibrary`, `LayoutSelector`, `LayoutEngine`, `TypographyEngine` |
| `scripts/style.py` | `BrandStyleResolver` — one token set per pack |
| `scripts/render.py` | `AssetCache`, `CompositionRenderer`, `ExportManager` |
| `scripts/validate.py` | `OutputValidator` — per-composition and per-set rules |
| `scripts/generate_pack.py` | Pipeline orchestration |
| `scripts/build_preview.py` | Confirmation gallery from real compositions |
| `scripts/package_assets.py` | Dimension verification, provenance manifest, ZIP |

### Adding a layout

Drop a JSON file into `scripts/layouts/<family>/`. It needs `id`, `label`, `family`, `requires` (screenshot count, source class, orientation, presentation modes), `intent`, `tags`, `weight`, a `text` block (`area`, `align`, `title_max_chars`, `subtitle_max_chars`, `scale`), a `devices` list (`source`, `width`, `cx`, `top`, `rotate`, `z`, `fit`, `shadow`, `opacity`, `dim`, `max_overflow`), and optional `decor`. Positions are fractions of the canvas; sizes are fractions of canvas width. Nothing else changes.

### Adding a device family

Add an entry to `DEVICE_FAMILIES` in `scripts/devices.py` with its aspect-ratio range, `FrameStyle`, hero widths, max device width, safe margin, layout families, and documented export sizes. Layout selection and validation pick it up automatically.

## Tests

```bash
python3 scripts/test_pipeline.py
python3 scripts/test_build_preview.py
python3 scripts/test_package_assets.py
```
