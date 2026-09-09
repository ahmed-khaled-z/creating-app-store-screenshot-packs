"""Pipeline entry point: spec JSON -> staged, validated PNGs per platform.

    python3 scripts/generate_pack.py spec.json --staging OUT [--html-only]

Ordering mirrors the documented workflow: analyse, classify, resolve target,
group, sequence, select layout, compose, render, validate, regenerate, export.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import style as style_module
from analyzer import ScreenshotAnalyzer, SetAnalyzer
from devices import PLATFORMS, TargetDeviceResolver
from layout_engine import LayoutEngine, LayoutLibrary, LayoutSelector
from render import AssetCache, CompositionRenderer, ExportManager
from validate import errors, validate_plan, validate_set

MAX_LAYOUT_ATTEMPTS = 4
DEFAULT_PROMO_NOTE = "Application shown on a phone"


class PackGenerator:
    def __init__(self, spec: dict, staging: Path, *, html_only: bool = False) -> None:
        self.spec = spec
        self.staging = Path(staging)
        self.html_only = html_only
        self.analyzer = ScreenshotAnalyzer()
        self.library = LayoutLibrary()
        self.selector = LayoutSelector(self.library)
        self.engine = LayoutEngine()
        self.renderer = CompositionRenderer(AssetCache())
        self.exporter = None if html_only else ExportManager(spec.get("browser"))
        self.tokens = style_module.resolve(spec["style"], **spec.get("brand", {}))

    def run(self) -> dict:
        report = {"style": self.tokens["code"], "language": self.spec["language"],
                  "app_name": self.spec.get("app_name", ""), "platforms": {}}
        for target in sorted(self.spec["targets"]):
            if target not in PLATFORMS:
                raise ValueError(f"unknown target platform: {target}")
            report["platforms"][target] = self._build_platform(target, self.spec["targets"][target])
        return report

    def _build_platform(self, target: str, config: dict) -> dict:
        canvas = tuple(config["size"])
        slides = self._sequence(config["slides"])
        folder = self.staging / target
        folder.mkdir(parents=True, exist_ok=True)

        plans, outputs, used = [], [], []
        for index, slide in enumerate(slides, start=1):
            plan, issues = self._compose(target, slide, canvas, used)
            used.append(plan["layout_id"])
            name = f"{index:02d}.png"
            html = self.renderer.html(plan, self.tokens)
            (folder / f"{index:02d}.html").write_text(html, encoding="utf-8")
            if not self.html_only:
                path = self.exporter.rasterize(html, folder / name, canvas)
                issues = issues + validate_plan(plan, rendered=path)
                blocking = errors(issues)
                if blocking:
                    raise ValueError(f"{target}/{name} failed validation: {blocking}")
            plans.append(plan)
            outputs.append({
                "filename": name,
                "html": f"{target}/{index:02d}.html",
                "layout": plan["layout_id"],
                "layout_label": plan["layout_label"],
                "presentation": plan["presentation"],
                "sources": plan["sources"],
                "reasons": plan["selection_reasons"],
                "issues": [issue for issue in issues if issue["severity"] == "warning"],
            })

        set_issues = validate_set(plans, self.tokens)
        if errors(set_issues):
            raise ValueError(f"{target} set validation failed: {errors(set_issues)}")
        (folder.parent / f"{target}-plan.json").write_text(json.dumps(plans, indent=2) + "\n")
        return {"size": list(canvas), "outputs": outputs, "set_warnings": set_issues}

    def _sequence(self, slides: list[dict]) -> list[dict]:
        """Order the whole set before composing any single image.

        Slides are sequenced, not files: the same screenshot may legitimately
        appear in more than one composition.
        """
        analysed = []
        for slide in slides:
            group = [self.analyzer.analyze(Path(path), slide.get("label"))
                     for path in slide["sources"]]
            analysed.append({**slide, "group": group})
        leads = SetAnalyzer.sequence([item["group"][0] for item in analysed])
        order = sorted(range(len(analysed)), key=lambda index: leads[index]["position"])
        sequenced = []
        for position, index in enumerate(sorted(order, key=lambda i: leads[i]["position"])):
            slide = analysed[index]
            lead = dict(slide["group"][0])
            lead["position"] = position
            lead["is_lead"] = position == 0
            slide["group"] = [lead, *slide["group"][1:]]
            sequenced.append(slide)
        return sequenced

    def _compose(self, target: str, slide: dict, canvas, used: list[str]) -> tuple[dict, list[dict]]:
        group = slide["group"]
        presentations = {TargetDeviceResolver.resolve(item, target)["presentation"] for item in group}
        if "incompatible" in presentations:
            raise ValueError(
                f"{target}: source screenshots are incompatible with this device family "
                f"({sorted(item['device_class'] for item in group)}). Capture real "
                f"{TargetDeviceResolver.family(target).label} screenshots for this platform."
            )
        presentation = "promotional" if "promotional" in presentations else sorted(presentations)[0]
        copy = {
            "title": slide.get("title", ""),
            "subtitle": slide.get("subtitle", ""),
            "captions": slide.get("captions", []),
            "bullets": slide.get("bullets", []),
        }

        excluded: set[str] = set()
        last_issues: list[dict] = []
        for _ in range(MAX_LAYOUT_ATTEMPTS):
            if slide.get("layout") and not excluded:
                choice = {"layout": self.library.get(slide["layout"]), "reasons": ["layout pinned in the spec"]}
            else:
                choice = self.selector.select(target=target, group=group, copy=copy, canvas=canvas,
                                              presentation=presentation, used=used, exclude=excluded)
            plan = self.engine.resolve(layout=choice["layout"], group=group, target=target,
                                       canvas=canvas, copy=copy, presentation=presentation)
            plan["selection_reasons"] = choice["reasons"]
            plan["promo_note"] = slide.get("promo_note", DEFAULT_PROMO_NOTE)
            last_issues = validate_plan(plan)
            if not errors(last_issues):
                return plan, last_issues
            excluded.add(choice["layout"]["id"])
        raise ValueError(
            f"{target}: no layout passed validation for {group[0]['filename']}: {errors(last_issues)}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--html-only", action="store_true",
                        help="emit composition HTML and validate the plan without rasterising; "
                             "screenshot each HTML at its exact canvas size with your own browser tooling")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        spec = json.loads(args.spec.read_text())
        report = PackGenerator(spec, args.staging, html_only=args.html_only).run()
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
