"""Launch reel: a fast-cut product launch video in the style of the big AI-tool launch reels.

One template, many products. A spec (see `spec.py`) carries the brand, a style pack, a story
structure and the copy for an ordered list of scenes (`scenes.py`, `scenes2.py`); `build_reel()`
turns it into a finished one-board DiagramData project, laid out and timed, with no model in the
loop. The agent's only job is writing the spec from what it knows about the product, which is
the part a template cannot know; `checks.py` holds the spec's claims to the agent's sources.

Style packs (`styles.py`) change the look and the motion: faces, panels, backdrops, transitions,
easing, and the music preset. Story structures (`STORIES` in `spec.py`) change the arc: which
scenes, in what order, at what pace. Sound (`audio.py`) is rendered from the cue events the
builder records, so every pop, type and tick lands on its frame; scene changes are padded onto
the beat of the music.

Not a storyboard chapter template and not a gallery video template: there is no narration and
no per-scene plan step. It is a motion piece, closer to an ad than to an explainer.
"""
from __future__ import annotations

from ._metrics import set_faces
from .builder import Reel
from .scenes import SCENES, Ctx
from .scenes3 import _hex, product_chip
from .spec import EXAMPLE, STORIES, normalize
from .styles import STYLES

__all__ = ["build_reel", "normalize", "EXAMPLE", "SCENES", "STYLES", "STORIES"]

# Bumped when a scene, style or check changes what a spec builds to.
VERSION = "1.0.0"


def build_reel(spec: dict) -> dict:
    """Spec in, DiagramData project out. Deterministic: the same spec builds the same reel."""
    spec = normalize(spec)
    b = spec["brand"]
    style = STYLES[spec["style"]]
    story = STORIES[spec["story"]]
    set_faces(style.display, style.body, style.display_scale)
    r = Reel(style.palette(b["ink"], b["paper"], b["accents"]), style, story["pace"])
    r.brand_name = b["name"]
    beat = 60000 / style.bpm / 2          # scene changes land on the half beat
    for i, sc in enumerate(spec["scenes"]):
        if i:
            at = 200 + r.t
            r.hold_raw(round((-at) % beat), "beat")
        tx, d = style.transition(i)
        r.begin_scene(i, tx, d)
        prod = sc.get("product") or {}
        col = _hex(prod.get("color"), "")
        base = r.pal
        if prod.get("name"):
            # one product of a suite: its scene takes the product's colour and wears its name
            if col:
                r.pal = base.with_accent(col)
                sc = dict(sc, bg=sc.get("bg") or col)
            r.backdrop += product_chip(r, f"s{i}_", prod["name"], col or base.accents[0])
        SCENES[sc["type"]](Ctx(r, b, i), sc)
        r.pal = base
    proj = r.project(f"{b['name']} launch reel")
    proj["meta"] = {"template": "launch_reel", "durationMs": r.duration_ms, "spec": spec,
                    "audio": {"music": style.music, "bpm": style.bpm, "events": r.events,
                              "transitions": r.transitions}}
    return proj
