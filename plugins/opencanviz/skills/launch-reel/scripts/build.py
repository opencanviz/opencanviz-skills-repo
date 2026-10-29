#!/usr/bin/env python3
"""Build an openCanviz launch reel from a spec.

    python3 build.py spec.json --sources facts.md --out reel.json
    python3 build.py spec.json --sources facts.md --screenshot dash.png --out reel.json
    python3 build.py spec.json --sources facts.md --out reel.json --audio reel.wav
    python3 build.py --scenes            # every scene type and its keys
    python3 build.py --icons ph:rocket   # which bundled icons match

Checks run before the build. Any claim in the spec (price, figure, competitor, date, stars,
quote) that the --sources files do not contain, an AI scene for a product with no AI, or a
scene the checks would drop, stops the build with one line per problem (exit 2). Fix the spec,
or add the missing fact to the sources if it is true and you can point to where it came from.
--allow-unsourced builds anyway, dropping or repairing those scenes.

Writes the project JSON (paste it into Import on opencanviz.com/create, or preview it with
preview.mjs). With --audio, also writes the music and sound effects as a WAV (needs numpy and
scipy); preview.mjs --audio mixes it into the preview MP4.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from launch_reel import SCENES, STORIES, STYLES, build_reel, normalize  # noqa: E402
from launch_reel._icons import bundled  # noqa: E402
from launch_reel.checks import check_icons, clean, ground  # noqa: E402
from launch_reel.media import attach_screenshots, embed_image  # noqa: E402

REFERENCE = Path(__file__).resolve().parents[1] / "reference" / "scenes.md"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="spec JSON")
    ap.add_argument("--sources", action="append", default=[],
                    help="text or markdown file of facts about the product (repeatable)")
    ap.add_argument("--out", help="project JSON to write")
    ap.add_argument("--story", choices=sorted(STORIES), help="override the spec's story")
    ap.add_argument("--style", choices=sorted(STYLES), help="override the spec's style")
    ap.add_argument("--screenshot", action="append", default=[], help="screenshot path or URL (repeatable)")
    ap.add_argument("--audio", help="also write the sound track to this WAV (needs numpy and scipy)")
    ap.add_argument("--allow-unsourced", action="store_true", help="build even when a claim is not in the sources")
    ap.add_argument("--fetch-icons", action="store_true", help="fetch icons that are not bundled from Iconify")
    ap.add_argument("--scenes", action="store_true", help="print the scene reference and exit")
    ap.add_argument("--icons", metavar="TEXT", help="list bundled icons whose ref contains TEXT and exit")
    a = ap.parse_args(argv)

    if a.scenes:
        print(REFERENCE.read_text())
        return 0
    if a.icons is not None:
        print("\n".join(r for r in sorted(bundled()) if a.icons.lower() in r))
        return 0
    if not (a.spec and a.out):
        ap.error("spec and --out are required")
    if a.fetch_icons:
        os.environ["LAUNCH_REEL_FETCH_ICONS"] = "1"

    spec = clean(json.loads(Path(a.spec).read_text()))
    spec.update({k: v for k, v in (("story", a.story), ("style", a.style)) if v})
    unknown = [s.get("type") for s in spec.get("scenes") or [] if s.get("type") not in SCENES]
    if unknown:
        print(f"unknown scene type(s): {', '.join(map(str, unknown))}; see build.py --scenes", file=sys.stderr)
        return 2
    attach_screenshots(spec, [embed_image(s) for s in a.screenshot])
    spec = normalize(spec)

    if not a.sources:
        print("warning: no --sources; every claim scene (stat, pricing, receipt, compare, repo, timeline, "
              "quote) will be treated as unsourced", file=sys.stderr)
    sources = "\n\n".join(Path(s).read_text() for s in a.sources)
    notes = ground(copy.deepcopy(spec), sources)
    if notes and not a.allow_unsourced:
        print("not built, the spec makes claims the sources do not support:", file=sys.stderr)
        for n in notes:
            print(f"  - {n}", file=sys.stderr)
        return 2
    notes = ground(spec, sources)
    for n in notes:
        print(f"  - {n}", file=sys.stderr)
    check_icons(spec)

    project = build_reel(spec)
    # meta.spec keeps the screenshots once already, in the scene nodes; don't carry them twice
    for sc in project["meta"]["spec"]["scenes"]:
        if str(sc.get("image") or "").startswith("data:"):
            sc["image"] = "(embedded)"
    Path(a.out).write_text(json.dumps(project, separators=(",", ":"), ensure_ascii=False))
    m = project["meta"]
    print(f"{a.out}: {m['spec']['style']} / {m['spec']['story']}, {len(spec['scenes'])} scenes, "
          f"{m['durationMs'] / 1000:.1f}s")
    if a.audio:
        try:
            from launch_reel.audio import wav_bytes
        except ImportError:
            print("--audio needs numpy and scipy: pip install numpy scipy", file=sys.stderr)
            return 1
        Path(a.audio).write_bytes(wav_bytes(project))
        print(a.audio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
