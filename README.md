# Creating App Store Screenshot Packs

A Codex skill for turning raw app screenshots into a reviewed, multi-platform marketing pack for the Apple App Store and Google Play.

The skill displays an HTML gallery before rendering, lets you select a layout and style, sanitizes private or demo data, checks current official store dimensions, and returns one ZIP containing iPhone, iPad, Android phone, and Android tablet assets.

## Features

- HTML preview before final rendering.
- Three layouts: `L1 Hero`, `L2 Split`, and `L3 Feature Focus`.
- Three styles: `S1 Clean Cream`, `S2 Bold Brand`, and `S3 Soft Gradient`.
- Sanitization of email addresses, personal details, payment information, credentials, notifications, and obvious demo data.
- Runtime verification of current screenshot dimensions using official Apple and Google documentation.
- Explicit approval before adapting screenshots across platforms.
- Numbered PNG files and a provenance manifest inside one ZIP archive.

## Requirements

- Codex with skill support, image generation or editing tools, and the ability to open local HTML files.
- Python 3 for image validation and ZIP packaging. No third-party Python runtime dependency is required.
- Internet access to verify current store requirements.

Node.js is needed only to run the HTML concurrency regression test; it is not required for normal skill usage.

## Installation

### Recommended: Git

```bash
git clone https://github.com/ahmed-khaled-z/creating-app-store-screenshot-packs.git \
  ~/.codex/skills/creating-app-store-screenshot-packs
```

Verify the installation:

```bash
test -f ~/.codex/skills/creating-app-store-screenshot-packs/SKILL.md \
  && echo "Skill installed"
```

Start a new Codex task if the skill is not available in the current conversation.

### Manual installation

1. Open the repository and choose **Code → Download ZIP**.
2. Extract the archive.
3. Move the extracted directory to:

   ```text
   ~/.codex/skills/creating-app-store-screenshot-packs
   ```

4. Confirm that `SKILL.md` is directly inside that directory, not inside an additional nested folder.

### Update

```bash
git -C ~/.codex/skills/creating-app-store-screenshot-packs pull --ff-only
```

### Uninstall

Move the following directory to Trash, then start a new Codex task:

```text
~/.codex/skills/creating-app-store-screenshot-packs
```

## Usage

Attach your screenshots, then enter:

```text
Use $creating-app-store-screenshot-packs to create App Store and Google Play marketing screenshot packs from the attached screenshots.
```

You can provide optional details:

```text
Use $creating-app-store-screenshot-packs.
App name: Schoolz
Language: English
Use the colors from the attached logo.
Allow iPad screenshots to be adapted for Android tablets only.
```

## Workflow

1. The skill inspects every screenshot and identifies its platform, orientation, represented screen, marketing value, and sensitive data.
2. It asks only for missing essentials, including permission for any cross-platform adaptation.
3. It verifies current accepted dimensions using official Apple and Google documentation.
4. It creates a sanitized, low-resolution representative screenshot and opens the local `preview.html` gallery.
5. You choose a layout and style, then paste a confirmed code such as `L2-S1` into the conversation.
6. Final rendering starts only after the selection code is confirmed.
7. The skill validates dimensions, PNG structure, filenames, and provenance before creating the ZIP.

## Layouts and styles

| Code | Layout |
|---|---|
| `L1` | Hero |
| `L2` | Split |
| `L3` | Feature Focus |

| Code | Style |
|---|---|
| `S1` | Clean Cream |
| `S2` | Bold Brand |
| `S3` | Soft Gradient |

A valid confirmed selection ranges from `L1-S1` to `L3-S3`.

## ZIP structure

```text
app-store-assets.zip
└── app-store-assets/
    ├── manifest.json
    ├── iphone/
    │   ├── 01.png
    │   └── 02.png
    ├── ipad/
    ├── android-phone/
    └── android-tablet/
```

`manifest.json` records the selected layout, style, language, dimensions, original source screenshot for every output, and any adapted platforms.

## Important notes

- Native screenshots for each platform produce the most truthful results.
- iPad screenshots are not presented as native iPhone or Android interfaces without explicit approval.
- Review marketing text and product claims before uploading the images to a store.
- Store dimensions are verified at runtime instead of being stored as fixed constants, because platform requirements can change.

## Tests

```bash
python3 scripts/test_package_assets.py
python3 scripts/test_preview_html.py
node scripts/test_preview_race.js
```

## Repository structure

```text
SKILL.md                      Skill workflow
agents/openai.yaml            Codex display metadata
assets/preview.html           Self-contained layout and style selector
scripts/package_assets.py     PNG validation and ZIP packaging
scripts/test_*.py             Python regression checks
scripts/test_preview_race.js  HTML asynchronous-state regression check
```

## License

[MIT](LICENSE)
