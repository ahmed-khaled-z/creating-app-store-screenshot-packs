"""CompositionRenderer and ExportManager.

The renderer only draws a plan it is handed; it makes no layout or device
decisions of its own. Device chrome is drawn in the bezel only, so nothing is
ever painted over the supplied application UI.
"""

import base64
import mimetypes
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path


CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge",
)


class AssetCache:
    """Reads each screenshot once per run and reuses the encoded copy.

    Batch renders reference the same few screenshots repeatedly; without this
    every composition would re-read and re-encode them.
    """

    def __init__(self) -> None:
        self._data_uris: dict[str, str] = {}

    def data_uri(self, path: str) -> str:
        cached = self._data_uris.get(path)
        if cached is None:
            raw = Path(path).read_bytes()
            mime = mimetypes.guess_type(path)[0] or "image/png"
            cached = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
            self._data_uris[path] = cached
        return cached


class CompositionRenderer:
    def __init__(self, cache: AssetCache | None = None) -> None:
        self.cache = cache or AssetCache()

    def html(self, plan: dict, tokens: dict) -> str:
        width, height = plan["canvas"]
        body = "".join([
            self._decor_html(plan, tokens),
            self._text_html(plan, tokens),
            "".join(self._device_html(device, tokens) for device in plan["devices"]),
        ])
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(plan['layout_label'])}</title>
<style>
  html,body {{ margin:0; padding:0; background:#000; }}
  #canvas {{
    position:relative; width:{width}px; height:{height}px; overflow:hidden;
    background:{tokens['background']};
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  .device {{ position:absolute; transform-origin:50% 50%; }}
  .device .body {{
    position:absolute; inset:0; border-radius:var(--body-radius);
    background:{tokens['device_body']};
    box-shadow: inset 0 0 0 1.5px {tokens['device_edge']}, var(--device-shadow);
  }}
  .device .screen {{ position:absolute; overflow:hidden; border-radius:var(--screen-radius); background:#0b0a14; }}
  .device .screen img {{ display:block; width:100%; height:100%; object-fit:cover; object-position:top center; }}
  .device .veil {{ position:absolute; inset:0; border-radius:var(--body-radius); background:#0b0a14; }}
  .cutout {{ position:absolute; background:#2b2940; border-radius:999px; }}
  .indicator {{ position:absolute; background:rgba(255,255,255,0.55); border-radius:999px; }}
  .textblock {{ position:absolute; display:flex; flex-direction:column; z-index:50; }}
  .textblock h1 {{ margin:0; font-weight:850; letter-spacing:-0.015em; color:{tokens['title_color']}; }}
  .textblock p {{ margin:0; font-weight:520; color:{tokens['subtitle_color']}; }}
  .blob {{ position:absolute; border-radius:50%; z-index:1; }}
  .card {{
    position:absolute; display:flex; align-items:center; justify-content:center;
    padding:0 2%; text-align:center; z-index:40;
    background:{tokens['card_surface']}; color:{tokens['card_ink']};
    box-shadow:{tokens['shadow_flat']};
  }}
  .caption {{ position:absolute; z-index:40; text-align:center; color:{tokens['muted']}; font-weight:700; transform:translate(-50%,-50%); }}
  .step {{
    position:absolute; z-index:45; display:flex; align-items:center; justify-content:center;
    border-radius:999px; color:#fff; background:{tokens['brand']}; font-weight:850;
    transform:translate(-50%,-50%);
  }}
  .bullets {{ position:absolute; z-index:40; display:flex; flex-direction:column; color:{tokens['subtitle_color']}; font-weight:600; }}
  .promo-note {{
    position:absolute; z-index:60; display:flex; align-items:center; justify-content:center;
    text-align:center; color:{tokens['muted']}; font-weight:700;
  }}
</style></head>
<body><div id="canvas">{body}</div></body></html>
"""

    def _device_html(self, device: dict, tokens: dict) -> str:
        frame = device["frame"]
        shadow = tokens[f"shadow_{device['shadow']}"]
        veil = (f'<div class="veil" style="opacity:{device["dim"]}"></div>'
                if device["dim"] > 0 else "")
        style = (
            f'left:{device["left"]}px; top:{device["top"]}px;'
            f'width:{device["width"]}px; height:{device["height"]}px;'
            f'transform:rotate({device["rotate"]}deg); opacity:{device["opacity"]};'
            f'z-index:{device["z"] * 10};'
            f'--body-radius:{frame["body_radius"]:.2f}px;'
            f'--screen-radius:{frame["screen_radius"]:.2f}px;'
            f'--device-shadow:{shadow};'
        )
        screen = (
            f'left:{frame["side_bezel"]:.2f}px; top:{frame["top_bezel"]:.2f}px;'
            f'width:{frame["screen_width"]:.2f}px; height:{frame["screen_height"]:.2f}px;'
        )
        return (
            f'<div class="device" style="{style}">'
            f'<div class="body"></div>'
            f'{self._chrome_html(frame)}'
            f'<div class="screen" style="{screen}">'
            f'<img src="{self.cache.data_uri(device["source"])}" alt="">'
            f'</div>{veil}</div>'
        )

    @staticmethod
    def _chrome_html(frame: dict) -> str:
        """Camera cutout and home indicator, drawn inside the bezel only."""
        width = frame["screen_width"]
        parts = []
        if frame["cutout"] == "island":
            pill_w, pill_h = width * 0.26, min(frame["top_bezel"] * 0.55, width * 0.020)
            parts.append(
                f'<div class="cutout" style="left:50%;transform:translateX(-50%);'
                f'top:{(frame["top_bezel"] - pill_h) / 2:.2f}px;width:{pill_w:.2f}px;height:{pill_h:.2f}px"></div>'
            )
        elif frame["cutout"] in ("punch-hole", "camera-dot"):
            dot = min(frame["top_bezel"] * 0.42, width * 0.012)
            parts.append(
                f'<div class="cutout" style="left:50%;transform:translateX(-50%);'
                f'top:{(frame["top_bezel"] - dot) / 2:.2f}px;width:{dot:.2f}px;height:{dot:.2f}px"></div>'
            )
        if frame["home_indicator"]:
            bar_w, bar_h = width * 0.24, max(frame["bottom_bezel"] * 0.18, 2.0)
            parts.append(
                f'<div class="indicator" style="left:50%;transform:translateX(-50%);'
                f'bottom:{(frame["bottom_bezel"] - bar_h) / 2:.2f}px;width:{bar_w:.2f}px;height:{bar_h:.2f}px"></div>'
            )
        return "".join(parts)

    @staticmethod
    def _text_html(plan: dict, tokens: dict) -> str:
        text = plan["text"]
        if not text["title_lines"] and not text["subtitle_lines"]:
            return ""
        x0, y0, x1, y1 = text["box"]
        justify = {"center": "center", "left": "flex-start", "right": "flex-end"}[text["align"]]
        title = "<br>".join(escape(line) for line in text["title_lines"])
        subtitle = "<br>".join(escape(line) for line in text["subtitle_lines"])
        block = (
            f'<h1 style="font-size:{text["title_size"]}px;line-height:1.08">{title}</h1>'
            if title else ""
        )
        if subtitle:
            block += (f'<p style="margin-top:{text["title_size"] * 0.42:.2f}px;'
                      f'font-size:{text["subtitle_size"]}px;line-height:1.35">{subtitle}</p>')
        return (
            f'<div class="textblock" style="left:{x0:.2f}px;top:{y0:.2f}px;'
            f'width:{x1 - x0:.2f}px;height:{y1 - y0:.2f}px;'
            f'align-items:{justify};justify-content:center;text-align:{text["align"]}">{block}</div>'
        )

    @staticmethod
    def _decor_html(plan: dict, tokens: dict) -> str:
        canvas_width = plan["canvas"][0]
        parts = []
        for item in plan["decor"]:
            kind = item["kind"]
            if kind == "blob":
                colour = tokens["accent"] if item.get("tone") == "accent" else tokens["brand"]
                size = item["px_r"] * 2
                parts.append(
                    f'<div class="blob" style="left:{item["px_cx"] - item["px_r"]:.2f}px;'
                    f'top:{item["px_cy"] - item["px_r"]:.2f}px;width:{size:.2f}px;height:{size:.2f}px;'
                    f'background:{colour};opacity:{tokens["blob_opacity"]}"></div>'
                )
            elif kind == "card" and item.get("text"):
                parts.append(
                    f'<div class="card" style="left:{item["px_cx"] - item["px_w"] / 2:.2f}px;'
                    f'top:{item["px_cy"] - item["px_h"] / 2:.2f}px;width:{item["px_w"]:.2f}px;'
                    f'height:{item["px_h"]:.2f}px;border-radius:{canvas_width * 0.022:.2f}px;'
                    f'font-size:{canvas_width * 0.022:.2f}px;font-weight:700">{escape(item["text"])}</div>'
                )
            elif kind == "caption" and item.get("text"):
                parts.append(
                    f'<div class="caption" style="left:{item["px_cx"]:.2f}px;top:{item["px_cy"]:.2f}px;'
                    f'font-size:{canvas_width * 0.024:.2f}px">{escape(item["text"])}</div>'
                )
            elif kind == "step":
                size = canvas_width * 0.062
                parts.append(
                    f'<div class="step" style="left:{item["px_cx"]:.2f}px;top:{item["px_cy"]:.2f}px;'
                    f'width:{size:.2f}px;height:{size:.2f}px;font-size:{size * 0.46:.2f}px">{item["index"]}</div>'
                )
            elif kind == "bullets" and item.get("items"):
                x0, y0, x1, y1 = item["px"]
                rows = "".join(
                    f'<span style="margin-bottom:{canvas_width * 0.016:.2f}px">• {escape(row)}</span>'
                    for row in item["items"][:4]
                )
                parts.append(
                    f'<div class="bullets" style="left:{x0:.2f}px;top:{y0:.2f}px;width:{x1 - x0:.2f}px;'
                    f'height:{y1 - y0:.2f}px;font-size:{canvas_width * 0.026:.2f}px">{rows}</div>'
                )
            elif kind == "promo-note":
                x0, y0, x1, y1 = item["px"]
                note = plan.get("promo_note") or "Application shown on a phone"
                parts.append(
                    f'<div class="promo-note" style="left:{x0:.2f}px;top:{y0:.2f}px;width:{x1 - x0:.2f}px;'
                    f'height:{y1 - y0:.2f}px;font-size:{canvas_width * 0.021:.2f}px">{escape(note)}</div>'
                )
        return "".join(parts)


class ExportManager:
    """Rasterises composition HTML at exact export dimensions.

    Headless Chrome is used because it is deterministic and already present on
    developer machines. When it is missing the caller is told to capture the
    HTML with its own browser tooling rather than falling back to anything
    generative.
    """

    def __init__(self, browser: str | None = None) -> None:
        self.browser = browser or self._discover()
        # One browser profile for the whole batch; a fresh profile per render
        # costs a full first-run initialisation each time.
        self._profile = tempfile.mkdtemp(prefix="screenshot-pack-profile-")
        self.timeout = 120

    def close(self) -> None:
        shutil.rmtree(self._profile, ignore_errors=True)

    @staticmethod
    def _discover() -> str | None:
        for candidate in CHROME_CANDIDATES:
            if Path(candidate).is_file():
                return candidate
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def rasterize(self, html: str, output: Path, size: tuple[int, int]) -> Path:
        if not self.browser:
            raise RuntimeError(
                "no headless Chrome/Chromium/Edge found; render the emitted HTML with "
                "a browser screenshot at the exact canvas size instead"
            )
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as work:
            page = Path(work) / "composition.html"
            page.write_text(html, encoding="utf-8")
            command = [
                self.browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                "--disable-sync", "--disable-background-networking",
                "--force-device-scale-factor=1", "--default-background-color=00000000",
                f"--user-data-dir={self._profile}",
                f"--window-size={size[0]},{size[1]}",
                f"--screenshot={output}", page.as_uri(),
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout)
            except subprocess.TimeoutExpired as expired:
                raise RuntimeError(
                    f"headless render timed out after {self.timeout}s; render the emitted "
                    "HTML with your own browser tooling at the exact canvas size"
                ) from expired
        if not output.is_file():
            raise RuntimeError(f"headless render failed: {result.stderr.strip()[:400]}")
        return output
