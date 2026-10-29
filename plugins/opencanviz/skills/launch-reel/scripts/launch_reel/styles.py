"""Style packs: the look and the motion of a reel, independent of what it says.

A pack changes everything a viewer reads as "style" and nothing a scene has to know about:

  palette     how the brand colours become paper, panels and fields (dark turns the paper to
              night and tints the fields deep; glass washes them pale)
  type        the display face for big lines and the body face for UI text, measured by the
              same tables the layout uses, so a Playfair headline is centred as truly as Inter
  surfaces    `dress()` restyles panels as they are made: glass panels go translucent over
              blurred colour blobs, editorial ones get hairlines and square corners, hand-drawn
              ones get a rough ink outline, flat ones lose their shadows
  motion      the transitions between scenes and the easing map: springy packs overshoot their
              pops, crisp ones ease out and stop
  score       which music preset `audio.py` plays under it

`classic` is the original look, so a spec without a style builds the reel it always built.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .builder import Palette, _mix

_SHADOW = "rgba(0,0,0"


@dataclass
class Style:
    name: str
    display: str = "Inter Brand"
    body: str = "Inter Brand"
    display_scale: float = 1.0
    display_weight: int | None = None
    display_tracking: float = -0.5
    transitions: tuple = ("cut",)
    push_dirs: tuple = ("right", "down", "right", "up")
    ease_map: dict = field(default_factory=dict)
    blur: bool = False
    push_ms: int = 560
    wipe_ms: int = 380
    music: str = "pop"
    bpm: int = 116
    mood: str = ""

    # ---- palette ----
    def palette(self, ink: str, paper: str, accents: list[str]) -> Palette:
        return Palette(ink, paper, accents)

    # ---- surfaces ----
    def dress(self, d: dict, pal: Palette):
        pass

    def backdrop(self, r, k: str) -> list[str]:
        return []

    def wipe_color(self, pal: Palette) -> str:
        return pal.accents[0]

    def transition(self, slot: int) -> tuple[str, str]:
        """(transition, push direction) into scene `slot`."""
        if slot == 0:
            return "cut", "right"
        tx = self.transitions[(slot - 1) % len(self.transitions)]
        return tx, self.push_dirs[(slot - 1) % len(self.push_dirs)]


def _is_panel(d: dict, pal: Palette) -> bool:
    return d["kind"] in ("rect", "circle") and str(d.get("fill", "")).lower() == pal.panel.lower()


def _is_shadow(d: dict) -> bool:
    return d["kind"] == "rect" and str(d.get("fill", "")).startswith(_SHADOW)


def _is_pill(d: dict) -> bool:
    return d.get("cornerRadius", 0) >= min(d.get("h", 0), d.get("w", 0)) / 2 - 1


class Classic(Style):
    pass


class Flat(Style):
    def dress(self, d, pal):
        d.pop("dropShadow", None)
        if _is_shadow(d):
            d["fill"] = "transparent"
        if d["kind"] == "rect" and not _is_pill(d) and d.get("cornerRadius", 0) > 10:
            d["cornerRadius"] = 10


class Glass(Style):
    def palette(self, ink, paper, accents):
        return Palette(ink, _mix(accents[0], "#ffffff", 0.86), accents, field_mix=0.5, field_toward="#ffffff")

    def dress(self, d, pal):
        if _is_shadow(d):
            d["fill"] = "transparent"
        elif _is_panel(d, pal) and d["kind"] == "rect":
            d["fill"] = "rgba(255,255,255,0.58)"
            d["stroke"], d["strokeWidth"] = "rgba(255,255,255,0.95)", 1.5
            if d.get("w", 0) > 300:
                d["dropShadow"] = dict(dx=0, dy=18, color="rgba(30,30,60,0.10)", radius=40)

    def backdrop(self, r, k):
        """Three big blurred blobs per stage in the brand colours, behind everything."""
        acc = r.pal.accents
        spots = [(-520, -300, 760, 0), (380, 120, 820, 1), (-80, 380, 640, 2)]
        ids = []
        for j, (x, y, dia, a) in enumerate(spots):
            r.node(f"{k}blob{j}", "circle", x - dia / 2, y - dia / 2, dia, dia, 1,
                   fill=_mix(acc[a % len(acc)], "#ffffff", 0.15), blur=120)
            ids.append(f"{k}blob{j}")
        return ids


class Editorial(Style):
    def palette(self, ink, paper, accents):
        return Palette("#161514", "#f1eee7", accents, panel="#fffdf9", field_mix=0.3, field_toward="#f1eee7")

    def dress(self, d, pal):
        d.pop("dropShadow", None)
        if _is_shadow(d):
            d["fill"] = "transparent"
        if d["kind"] == "rect" and d.get("cornerRadius", 0) > 4 and d.get("w", 0) > 60:
            d["cornerRadius"] = 3
        if _is_panel(d, pal) and d.get("stroke") in (None, "transparent") and d.get("w", 0) > 60:
            d["stroke"], d["strokeWidth"] = pal.ink, 1.2

    def wipe_color(self, pal):
        return pal.ink

    def backdrop(self, r, k):
        """A magazine folio: the brand name top left, a hairline under it."""
        name = r.brand_name if hasattr(r, "brand_name") else ""
        r.text(k + "folio", -600, -342, 600, 30, f"{name}  ·  Launch".strip(" ·"), 15, color=r.pal.grey,
               weight=500, z=3, letterSpacing=2)
        r.node(k + "rule", "rect", -600, -310, 1200, 1.2, 3, fill=r.pal.line)
        return [k + "folio", k + "rule"]


class Hand(Style):
    def palette(self, ink, paper, accents):
        return Palette(ink, "#fbf7ee", accents, panel="#fffefa", field_mix=0.3, field_toward="#ffffff")

    def dress(self, d, pal):
        d.pop("dropShadow", None)
        if _is_shadow(d):
            d["fill"] = "transparent"
            return
        if d["kind"] in ("rect", "circle") and d.get("w", 0) > 24 and not d["id"].endswith("bg"):
            d["rough"] = True
            if d.get("stroke") in (None, "transparent"):
                d["stroke"], d["strokeWidth"] = pal.ink, 2.4
            else:
                d["strokeWidth"] = max(2.0, d.get("strokeWidth", 0))
                if d["stroke"] == pal.line:
                    d["stroke"] = pal.grey


class Dark(Style):
    def palette(self, ink, paper, accents):
        p = Palette("#e8ecf2", "#0b0d12", accents, panel="#161a22", field_mix=0.88, field_toward="#0b0d12")
        return p

    def dress(self, d, pal):
        if _is_shadow(d):
            d["fill"] = "rgba(0,0,0,0.35)"
        if d.get("dropShadow"):
            d["dropShadow"] = dict(d["dropShadow"], color="rgba(0,0,0,0.45)")
        if _is_panel(d, pal) and d.get("stroke") in (None, "transparent") and d.get("w", 0) > 60:
            d["stroke"], d["strokeWidth"] = "#2a313d", 1.2

    def backdrop(self, r, k):
        """A faint dot grid across the stage, the developer-tool wallpaper."""
        dots = []
        for gy in range(-420, 421, 40):
            for gx in range(-760, 761, 40):
                dots.append(f"M{gx} {gy}h2.4v2.4h-2.4z")
        r.node(k + "grid", "svg", -760, -420, 1522.4, 842.4, 1, svgPaths=[{"d": "".join(dots), "fill": "rgba(255,255,255,0.08)"}],
               svgViewBox={"x": -760, "y": -420, "w": 1522.4, "h": 842.4}, svgStretch=True, fill="rgba(255,255,255,0.08)")
        return [k + "grid"]


CRISP = {"back": "ease-out"}

STYLES: dict[str, Style] = {
    "classic": Classic("classic", music="pop", bpm=116, mood="the original: Inter, white panels, hard cuts"),
    "flat": Flat("flat", display="Space Grotesk", display_weight=700, transitions=("push",), ease_map=CRISP,
                 music="pop", bpm=122, mood="bold colour blocks, no shadows, every scene pushes the last one off"),
    "glass": Glass("glass", transitions=("blur", "zoom", "blur", "cut"), blur=True, music="chill", bpm=96,
                   mood="frosted panels over soft colour, scenes blur away and focus in"),
    "editorial": Editorial("editorial", display="Playfair Display", display_weight=700, display_tracking=-1,
                           transitions=("wipe", "cut", "cut"), ease_map=CRISP, wipe_ms=460, music="piano",
                           bpm=88, mood="serif headlines, hairlines, ink wipes"),
    "hand": Hand("hand", display="Caveat", body="Comic Neue", display_scale=1.3, display_weight=700,
                 display_tracking=0, transitions=("wipe", "push", "cut"), music="uke", bpm=104,
                 mood="sketchbook: rough ink outlines and handwriting"),
    "dark": Dark("dark", display="Space Grotesk", display_weight=700, transitions=("zoom", "cut", "blur", "cut"),
                 ease_map=CRISP, blur=True, music="synth", bpm=124, mood="developer dark mode, zoom-throughs"),
}
