"""Builds the confirmation gallery from real compositions.

The gallery no longer mocks devices with CSS: it renders the actual planned
compositions through the same engine that produces the exports, so what the
user approves is what ships. Layout is chosen per screenshot by the engine and
shown for review; the user confirms a style direction.

    python3 scripts/build_preview.py spec.json --out preview/gallery.html
"""

import argparse
import json
import shutil
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import style as style_module
from generate_pack import PackGenerator
from render import AssetCache, CompositionRenderer

STYLE_CODES = style_module.STYLE_CODES
CARD_WIDTH = 250


def build(spec: dict, out: Path) -> dict:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache = AssetCache()
    renderer = CompositionRenderer(cache)
    summary = {}
    sections = []

    for code in STYLE_CODES:
        tokens = style_module.resolve(code, **spec.get("brand", {}))
        generator = PackGenerator({**spec, "style": code}, out.parent / f".plan-{code}", html_only=True)
        report = generator.run()
        summary[code] = {
            target: [item["layout"] for item in config["outputs"]]
            for target, config in report["platforms"].items()
        }
        cards = []
        for target in sorted(report["platforms"]):
            config = report["platforms"][target]
            width, height = config["size"]
            scale = CARD_WIDTH / width
            plans = json.loads((out.parent / f".plan-{code}" / f"{target}-plan.json").read_text())
            for item, plan in zip(config["outputs"], plans):
                frame = renderer.html(plan, tokens)
                cards.append(f"""
      <figure class="card">
        <div class="stage" style="width:{CARD_WIDTH}px;height:{height * scale:.0f}px">
          <iframe loading="lazy" scrolling="no" title="{escape(target)} {escape(item['filename'])}"
                  style="width:{width}px;height:{height}px;transform:scale({scale:.5f})"
                  srcdoc="{escape(frame, quote=True)}"></iframe>
        </div>
        <figcaption>
          <strong>{escape(target)} · {escape(item['filename'])}</strong>
          <span>{escape(item['layout_label'])}</span>
          <span class="mode mode-{escape(item['presentation'])}">{escape(item['presentation'])}</span>
        </figcaption>
      </figure>""")
        sections.append(f"""
    <section class="direction" data-style="{code}" hidden>
      <h2>{code} · {escape(style_module.resolve(code, **spec.get('brand', {}))['label'])}</h2>
      <div class="cards">{''.join(cards)}</div>
    </section>""")

    out.write_text(_page(spec, sections), encoding="utf-8")
    for code in STYLE_CODES:
        shutil.rmtree(out.parent / f".plan-{code}", ignore_errors=True)
    return {"gallery": str(out), "layouts": summary}


def _page(spec: dict, sections: list[str]) -> str:
    app = escape(spec.get("app_name", "Your app"))
    choices = "".join(
        f'<div class="choice"><input id="style-{code.lower()}" name="style" value="{code}" type="radio"'
        f'{" checked" if code == STYLE_CODES[0] else ""}>'
        f'<label class="pill" for="style-{code.lower()}">{code}</label></div>'
        for code in STYLE_CODES
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choose a direction</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#f4f2f8; color:#19172b;
         font:16px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ width:min(1240px, calc(100% - 32px)); margin:40px auto 64px; }}
  h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,3rem); line-height:1; }}
  h2 {{ margin:28px 0 12px; font-size:1.1rem; }}
  .intro {{ max-width:680px; color:#6f6a7d; }}
  .styles {{ display:flex; gap:8px; margin:24px 0; }}
  .choice input {{ position:absolute; opacity:0; pointer-events:none; }}
  .pill {{ display:inline-block; padding:10px 18px; border:1px solid #dedbe8; border-radius:999px;
          background:#fff; font-weight:700; cursor:pointer; }}
  .choice input:checked + .pill {{ color:#fff; border-color:#5b4bdb; background:#5b4bdb; }}
  .choice input:focus-visible + .pill {{ outline:3px solid #ffb35c; outline-offset:3px; }}
  .cards {{ display:flex; flex-wrap:wrap; gap:18px; }}
  .card {{ margin:0; }}
  .stage {{ overflow:hidden; border:1px solid #dedbe8; border-radius:14px; background:#fff; }}
  .stage iframe {{ border:0; transform-origin:0 0; }}
  figcaption {{ display:flex; flex-direction:column; gap:2px; padding:8px 2px; font-size:.8rem; color:#6f6a7d; }}
  figcaption strong {{ color:#19172b; }}
  .mode {{ align-self:flex-start; padding:2px 8px; border-radius:999px; font-weight:800; font-size:.72rem; }}
  .mode-native, .mode-native-offspec {{ color:#0d4429; background:#d6f2e3; }}
  .mode-promotional {{ color:#5b2b00; background:#ffe0ad; }}
  .confirm {{ display:flex; align-items:center; gap:12px; margin-top:32px; padding:18px;
             border-radius:20px; background:#fff; }}
  button {{ border:1px solid #dedbe8; border-radius:999px; padding:10px 16px; background:#fff;
           font:inherit; font-weight:700; cursor:pointer; }}
  .primary {{ color:#fff; border-color:#5b4bdb; background:#5b4bdb; }}
  output {{ min-width:78px; font:800 1.2rem ui-monospace, SFMono-Regular, Menlo, monospace; }}
  #status {{ color:#6f6a7d; }}
  [hidden] {{ display:none !important; }}
</style></head>
<body><main>
  <h1>Choose a direction</h1>
  <p class="intro">{app} · Layouts are chosen per screenshot by the layout engine and shown below.
  Pick a style direction, confirm, and paste the code into chat. A card marked
  <em>promotional</em> presents a phone capture as marketing artwork on a tablet canvas and never
  claims to be native tablet UI.</p>

  <form id="selector">
    <div class="styles">{choices}</div>
    {''.join(sections)}
    <div class="confirm" aria-live="polite">
      <button class="primary" id="confirm" type="button">Confirm and copy</button>
      <output id="code">Not confirmed</output>
      <button id="copy" type="button" hidden disabled>Copy code</button>
      <span id="status">Final rendering waits for this code.</span>
    </div>
  </form>
</main>
<script>
    let copyOperationToken = 0;

    function selectionCode() {{
      return document.querySelector('[name=style]:checked').value;
    }}

    function showDirection() {{
      const code = selectionCode();
      document.querySelectorAll('.direction').forEach((section) => {{
        section.hidden = section.dataset.style !== code;
      }});
    }}

    function invalidateSelection() {{
      const copy = document.querySelector('#copy');
      copyOperationToken += 1;
      document.querySelector('#code').value = 'Not confirmed';
      copy.hidden = true;
      copy.disabled = true;
      document.querySelector('#status').textContent = 'Selection changed. Confirm again before rendering.';
      showDirection();
    }}

    async function copyCode(code) {{
      if (navigator.clipboard?.writeText) {{
        try {{
          await navigator.clipboard.writeText(code);
          return true;
        }} catch (_) {{
          // Local file access may block the Clipboard API; use the fallback.
        }}
      }}
      const field = document.createElement('textarea');
      field.value = code;
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.append(field);
      field.select();
      let copied = false;
      try {{
        copied = document.execCommand('copy');
      }} catch (_) {{
        // The visible output below remains available for manual copying.
      }}
      field.remove();
      return copied;
    }}

    async function confirmSelection() {{
      const code = selectionCode();
      const operationToken = ++copyOperationToken;
      document.querySelector('#code').value = code;
      document.querySelector('#copy').hidden = false;
      document.querySelector('#copy').disabled = false;
      const copied = await copyCode(code);
      if (operationToken !== copyOperationToken || document.querySelector('#code').value !== code) return;
      document.querySelector('#status').textContent = copied
        ? `${{code}} copied. Paste it into chat to approve rendering.`
        : `${{code}} confirmed. Copy it manually from this page and paste it into chat.`;
    }}

    document.querySelector('#confirm').addEventListener('click', confirmSelection);
    document.querySelector('#copy').addEventListener('click', async () => {{
      const code = document.querySelector('#code').value;
      const operationToken = ++copyOperationToken;
      const copied = await copyCode(code);
      if (operationToken !== copyOperationToken || document.querySelector('#code').value !== code) return;
      document.querySelector('#status').textContent = copied
        ? `${{code}} copied again.`
        : `Copy it manually: ${{code}}. Then paste it into chat.`;
    }});
    document.querySelectorAll('[name=style]').forEach((input) => {{
      input.addEventListener('change', invalidateSelection);
    }});
    showDirection();
</script>
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build(json.loads(args.spec.read_text()), args.out)
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
