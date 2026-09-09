---
name: creating-app-store-screenshot-packs
description: Use when users want promotional app screenshots, App Store or Google Play screenshot sets, device-specific marketing images, or a packaged multi-platform screenshot ZIP.
---

# Creating App Store Screenshot Packs

Create a reviewable marketing direction before rendering store-ready assets. Keep source UI truthful, use current store requirements, and make the final size and package operations deterministic.

## Workflow

Follow this order:

1. Inspect every supplied screenshot. Record its source filename, platform, device class, orientation, represented screen, sensitive or demo data, and marketing value. Map each source to the requested outputs.
2. Resolve only missing essentials: app name, output language, and whether screenshots may be adapted across platforms. Infer language from the screenshots when unambiguous. Never present an iPad capture as native iPhone or Android UI without explicit permission. Record every permitted adaptation; if permission or truthful source material is missing, pause that platform export.
3. Browse current accepted screenshot dimensions. For sizes, use only official Apple App Store Connect documentation on `developer.apple.com` and official Google Play Console documentation on `support.google.com`. Choose one accepted portrait size for each of `iphone`, `ipad`, `android-phone`, and `android-tablet`, and retain the source URLs and chosen pixel dimensions for verification.
4. Create a low-resolution copy of one representative screenshot and sanitize personal, payment, credential, notification, and obvious test/demo data with neutral replacements. Inspect the sanitized copy before saving it as `preview.png` beside a temporary copy of `assets/preview.html`. Patch the CSS custom properties, app name, headlines, relative image slot, platform labels, and `data-adapted` flags for the current inputs; do not add a server or external assets. Keep the template's choice names: layouts `L1 Hero`, `L2 Split`, `L3 Feature Focus`; styles `S1 Clean Cream`, `S2 Bold Brand`, `S3 Soft Gradient`. Open the local HTML file in a visible browser and verify the sanitized screenshot and all six choices display. Only then ask the user to choose in that gallery and paste its confirmed code into chat, then wait for a code matching `L1-S1` through `L3-S3`. A text-only list or promised preview does not complete this step; if the gallery cannot be shown, report that blocker before requesting a choice.
5. Only after confirmation, use built-in image generation or image editing to produce the marketing compositions in the chosen direction. Sanitize personal, payment, credential, notification, and obvious test/demo data with neutral replacements before export. Preserve the supplied app UI, logo, copy meaning, and platform truth; device frames are decoration, not evidence of native platform support. Check spelling, claims, safe margins, and visual fidelity.
6. Use an available deterministic raster tool for final resizing, padding, PNG conversion, and filename normalization. Scale proportionally and pad to the selected accepted dimensions; do not use generative expansion for this step. Name each platform's files `01.png`, `02.png`, and so on in presentation order. Programmatically verify every PNG's exact width and height.
7. Stage exactly four non-empty folders named `iphone`, `ipad`, `android-phone`, and `android-tablet`. From this skill directory, run `scripts/package_assets.py` with separate layout/style values, language, one or more official allowed sizes per platform, one `--source platform/numbered.png=ORIGINAL_PATH` for every output, and an `--adapted` flag for every adapted platform. Each original path must identify an existing supplied screenshot, not its sanitized or rendered derivative; relative paths resolve from the current directory. The manifest records this provenance as `source`, separately from `staged` and archive `output` paths:

   ```bash
   python3 scripts/package_assets.py STAGING_DIR app-store-assets.zip \
     --layout L2 --style S1 --language en \
     --size iphone=WIDTHxHEIGHT --size ipad=WIDTHxHEIGHT \
     --size android-phone=WIDTHxHEIGHT --size android-tablet=WIDTHxHEIGHT \
     --source 'iphone/01.png=/path/to/original-iphone.png' \
     --source 'ipad/01.png=/path/to/original-ipad.png' \
     --source 'android-phone/01.png=/path/to/original-iphone.png' \
     --source 'android-tablet/01.png=/path/to/original-ipad.png' \
     --adapted android-phone --adapted android-tablet
   ```

   Omit `--adapted` entries that do not apply. Inspect the exit status; on failure, fix the reported input rather than hand-building the archive. On success, inspect the ZIP listing and parse `app-store-assets/manifest.json`. Return the ZIP and summarize the confirmed code, language, dimensions, source mappings, and adaptations.
