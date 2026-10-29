"""Iconify icons as inline svgPaths, so a reel renders with no icon fetch in the player.

A spec names icons as Iconify refs: `ph:` (Phosphor) for the interface glyphs and `logos:` for
the multicolour brand marks on the app wall. A few hundred of them ship with the skill in
`icons.json`, already flattened to path + fill, so a build makes no network calls. A brand
mark's gradient fill collapses to its last stop, which is what a 28px logo reads as anyway.

Refs outside the bundle are fetched from api.iconify.design only when the build is asked to
(`--fetch-icons`, or LAUNCH_REEL_FETCH_ICONS=1), and kept on disk (LAUNCH_REEL_ICON_CACHE,
default ~/.cache/launch-reel-icons). Otherwise, and whenever a ref will not resolve, the icon
falls back to a sparkle: a missing icon in a launch video is a blemish, a crashed build is a
missing video.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

_BUNDLE = Path(__file__).with_name("icons.json")
_DISK = Path(os.environ.get("LAUNCH_REEL_ICON_CACHE", Path.home() / ".cache" / "launch-reel-icons"))
FALLBACK = "ph:sparkle-fill"

# Built once per process. Keyed on the ref, colour applied per call.
_parsed: dict[str, tuple[list[dict], dict]] = {}
_bundle: dict | None = None


def bundled() -> dict:
    """The refs that ship with the skill: {ref: {"vb": [x, y, w, h], "p": [[d, fill], ...]}}."""
    global _bundle
    if _bundle is None:
        try:
            _bundle = json.loads(_BUNDLE.read_text())
        except (OSError, ValueError):
            _bundle = {}
    return _bundle


def fetching() -> bool:
    return os.environ.get("LAUNCH_REEL_FETCH_ICONS", "") not in ("", "0")


def fetch_icon_svg(ref: str) -> str | None:
    """The ref's SVG from the disk cache or, when fetching is on, from Iconify."""
    f = _DISK / (re.sub(r"[^a-z0-9_-]+", "_", ref.lower()) + ".svg")
    try:
        if f.exists():
            return f.read_text()
    except OSError:
        pass
    if not fetching() or ":" not in ref:
        return None
    prefix, name = ref.split(":", 1)
    svg = None
    for wait in (1, 2, 4, 8):
        try:
            req = urllib.request.Request(f"https://api.iconify.design/{prefix}/{name}.svg",
                                         headers={"User-Agent": "opencanviz-launch-reel"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                svg = resp.read().decode()
            break
        except urllib.error.HTTPError as e:
            if e.code != 429:          # Iconify answers a burst with 429; anything else is final
                break
            time.sleep(wait)
        except (urllib.error.URLError, OSError):
            break
    if svg and "<path" in svg:
        try:
            _DISK.mkdir(parents=True, exist_ok=True)
            f.write_text(svg)
        except OSError:
            pass
        return svg
    return None


def _parse(svg: str) -> tuple[list[dict], dict]:
    vb = re.search(r'viewBox="([^"]+)"', svg)
    x, y, w, h = (float(v) for v in vb.group(1).split()) if vb else (0, 0, 24, 24)
    stops = {}
    for gid, inner in re.findall(r'<(?:linear|radial)Gradient id="([^"]+)"[^>]*>(.*?)</(?:linear|radial)Gradient>',
                                 svg, re.S):
        c = re.findall(r'stop-color="([^"]+)"', inner)
        stops[gid] = c[-1] if c else "#888888"
    # A fill set on a wrapping <g> applies to the paths inside it.
    group_fill = re.search(r'<g[^>]*fill="([^"]+)"', svg)
    paths = []
    for tag in re.findall(r'<path[^>]*/?>', svg):
        d = re.search(r' d="([^"]+)"', tag)
        if not d:
            continue
        fill = re.search(r'fill="([^"]+)"', tag)
        fill = fill.group(1) if fill else (group_fill.group(1) if group_fill else "currentColor")
        m = re.match(r"url\(#([^)]+)\)", fill)
        if m:
            fill = stops.get(m.group(1), "#888888")
        if fill == "none":
            continue
        paths.append({"d": d.group(1), "fill": fill})
    return paths, {"x": x, "y": y, "w": w, "h": h}


def _load(ref: str) -> tuple[list[dict], dict]:
    b = bundled().get(ref)
    if b:
        x, y, w, h = b["vb"]
        return [{"d": d, "fill": f} for d, f in b["p"]], {"x": x, "y": y, "w": w, "h": h}
    svg = fetch_icon_svg(ref) if ref and ":" in ref else None
    return _parse(svg) if svg else ([], {})


def icon_paths(ref: str, color: str | None = None) -> tuple[list[dict], dict]:
    """(svgPaths, svgViewBox) for an Iconify ref. `color` recolours every path, which is what
    a monochrome UI glyph wants; leave it None for a brand mark so it keeps its own colours."""
    if ref not in _parsed:
        parsed = _load(ref)
        if not parsed[0]:
            if ref == FALLBACK:
                parsed = ([{"d": "M12 2l2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6z",
                            "fill": "currentColor"}], {"x": 0, "y": 0, "w": 24, "h": 24})
            else:
                return icon_paths(FALLBACK, color or "#787774")
        _parsed[ref] = parsed
    paths, vb = _parsed[ref]
    out = []
    for p in paths:
        fill = p["fill"]
        if color or fill == "currentColor":
            fill = color or "#191919"
        out.append({"d": p["d"], "fill": fill})
    return out, dict(vb)


def resolves(ref: str) -> bool:
    """True when the ref draws: bundled, cached, or fetched."""
    if not ref or ":" not in ref:
        return False
    if ref in _parsed or ref in bundled():
        return True
    return bool(_load(ref)[0])
