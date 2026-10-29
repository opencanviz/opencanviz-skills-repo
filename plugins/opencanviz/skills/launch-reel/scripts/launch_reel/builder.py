"""The reel builder: node and step plumbing every launch-reel scene is written against.

A launch reel is one DiagramData board with every node of every scene laid out up front
(invisible), and a timeline that moves between them. Two rules from building the first one by
hand are baked in here so no scene has to remember them:

  - A cut is a 1ms step. At 30fps a 34ms step still lands one frame half way through the
    opacity change, and that frame shows two scenes on top of each other.
  - Nothing appears or disappears inside a long step. Visibility flips in a 1ms step, then
    the motion runs in the next one. `appear()` does the flip.

Each scene gets its own stage: a patch of the board well away from the others, with its own
background. Scenes are written in stage coordinates around (0, 0) and the builder moves them
onto their stage, so a scene never knows where it sits. Stages are what make the transitions
possible: a push pans the camera from one stage to the next with both in view, a zoom flies
into the old stage and out of the new one, a wipe sweeps a band across, a blur lets the old
stage recede. `begin_scene()` picks the stage and the transition, and the scene's first `cut()`
plays it.

The camera is a track, not per-step fields. The engine's step camera eases from the previous
rest to `camera` and then drifts to `cameraEnd` inside that one step, so a move that outlives
its step snaps to its end at the next one. Scenes describe moves ("from c to e over d ms") and
`project()` writes each step's camera from the track, so a slow push-in really is slow.

The builder also keeps track of what is on screen, so a scene ends by calling `cut()` with the
next scene's opening nodes and everything the previous scene left up is switched off in the
same 1ms step, and it keeps a log of sound cues (pops, clicks, typing, whooshes) for the score.
"""
from __future__ import annotations

import copy

from ._icons import icon_paths
from ._metrics import DISPLAY_MIN, text_width

FONT = "Inter Brand"
MONO = "Menlo, 'DejaVu Sans Mono', monospace"
C0 = {"x": 0, "y": 0, "zoom": 1}
SPAN = 3600                     # stage pitch; a stage's background is this wide, so pushes meet
VIEW_W, VIEW_H = 1280, 720


def _mix(a: str, b: str, t: float) -> str:
    """Blend hex colour `a` toward `b` by t (0 = a, 1 = b)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _lum(c: str) -> float:
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class Palette:
    """The brand's colours plus the interface neutrals derived from them. Neutrals are mixed
    from the panel colour toward the ink, so the same derivation gives quiet greys on a white
    panel and quiet slates on a dark one."""

    def __init__(self, ink: str, paper: str, accents: list[str], panel: str = "#ffffff",
                 field_mix: float = 0.0, field_toward: str | None = None):
        self.ink, self.paper, self.panel = ink, paper, panel
        self.accents = accents
        self._field_mix, self._field_toward = field_mix, field_toward or paper
        self.grey = _mix(ink, panel, 0.55)
        self.faint = _mix(ink, panel, 0.68)
        self.line = _mix(ink, panel, 0.88)
        self.soft = _mix(panel, ink, 0.06)
        self.body = _mix(ink, panel, 0.12)
        self.link = accents[0]
        self.highlight = _mix(accents[0], panel, 0.80)
        self.disabled = _mix(panel, ink, 0.25)
        self.on_ink = panel                       # glyphs sitting on an ink-filled button
        self.bezel = "#111111" if _lum(panel) >= 0.4 else "#000000"
        self.keyboard = _mix(panel, ink, 0.16)
        self.good, self.bad = "#2f9e5b", "#d9534f"
        self.dark = _lum(panel) < 0.4

    def field(self, name: str | None) -> str:
        """A scene background by role: 'paper', 'accent1'..'accent3', or a hex colour (a suite
        product's own colour), mixed the same way the accents are."""
        if name and name.startswith("#") and len(name) == 7:
            return _mix(name, self._field_toward, self._field_mix) if self._field_mix else name
        if name and name.startswith("accent"):
            i = int(name[6:] or 1) - 1
            a = self.accents[i % len(self.accents)]
            return _mix(a, self._field_toward, self._field_mix) if self._field_mix else a
        return self.paper


    def with_accent(self, color: str) -> "Palette":
        """The same palette led by another accent: a suite product's scene in its own colour."""
        q = copy.copy(self)
        q.accents = [color] + [a for a in self.accents if a.lower() != color.lower()]
        q.link, q.highlight = color, _mix(color, self.panel, 0.80)
        return q


# ---------------- camera track ----------------
def _ease(t: float, ease: str) -> float:
    """The engine's easing curves (geometry-utils applyEasing), for sampling the track."""
    t = max(0.0, min(1.0, t))
    if ease == "ease":
        return t * t * (3 - 2 * t)
    if ease == "ease-in":
        return t * t
    if ease == "ease-out":
        return t * (2 - t)
    if ease == "back":
        c1 = 1.70158
        return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2
    return t


def _lerp(a: dict, b: dict, f: float) -> dict:
    return {k: a[k] + (b[k] - a[k]) * f for k in ("x", "y", "zoom")}


class Reel:
    def __init__(self, palette: Palette, style=None, pace: float = 1.0):
        from .styles import STYLES
        self.pal = palette
        self.style = style or STYLES["classic"]
        self.pace = pace
        self.nodes: list[dict] = []
        self.byid: dict[str, dict] = {}
        self.steps: list[dict] = []
        self.t = 0
        self.live: set[str] = set()     # ids switched on by a step and not yet switched off
        self.kids: dict[str, list[str]] = {}   # mask id -> the nodes it clips
        self.origin_of: dict[str, tuple[float, float]] = {}
        self.org = (0.0, 0.0)           # the stage being built
        self.shown_org = (0.0, 0.0)     # the stage on screen
        self.cells: set[tuple[int, int]] = set()
        self.cell = (0, 0)
        self.bg_id = "ground"
        self.backdrop: list[str] = []
        self.pending: str | None = None
        self.cam: list[dict] = [dict(t0=0, t1=0, a=C0, b=C0, ease="linear")]
        self.events: list[dict] = []
        self.transitions: list[dict] = []
        self._n = 0
        self.node("ground", "rect", -2400, -1600, 4800, 3200, -1, fill=palette.paper, opacity=1)

    # ---------------- stages ----------------
    def begin_scene(self, slot: int, transition: str = "cut", direction: str = "right"):
        """Open a stage for the next scene. Its first `cut()` plays `transition` from whatever
        is on screen. A push needs the new stage next to the old one in the push direction;
        everything else just takes the next free cell."""
        steps = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}
        cx, cy = self.cell
        cell = None
        if transition == "push":
            order = [direction] + [d for d in ("right", "down", "up", "left") if d != direction]
            for d in order:
                dx, dy = steps[d]
                if (cx + dx, cy + dy) not in self.cells:
                    cell, self._push_dir = (cx + dx, cy + dy), d
                    break
        if cell is None:
            if transition == "push":
                transition = "cut"
            x = max([c[0] for c in self.cells] + [-1]) + 1
            cell = (x, 0)
        self.cells.add(cell)
        self._next_cell = cell
        self.org = (cell[0] * SPAN, cell[1] * SPAN)
        self.pending = transition if self.steps else "cut"
        k = f"s{slot}_"
        self.bg_id = k + "bg"
        self.node(self.bg_id, "rect", -SPAN / 2, -SPAN / 2, SPAN, SPAN, 0, fill=self.pal.paper)
        self.backdrop = [self.bg_id] + self.style.backdrop(self, k)

    def _w(self, x, y, id=None):
        ox, oy = self.origin_of.get(id, self.org) if id else self.org
        return x + ox, y + oy

    def world(self, cam: dict, org=None) -> dict:
        ox, oy = org or self.org
        return {"x": cam.get("x", 0) + ox, "y": cam.get("y", 0) + oy, "zoom": cam.get("zoom", 1)}

    # ---------------- nodes ----------------
    def node(self, id, kind, x, y, w, h, z=10, **kw):
        assert id not in self.byid, f"duplicate node id {id}"
        d = dict(id=id, kind=kind, x=x, y=y, w=w, h=h, fill=kw.pop("fill", "transparent"),
                 stroke=kw.pop("stroke", "transparent"), strokeWidth=kw.pop("strokeWidth", 0),
                 opacity=kw.pop("opacity", 0), zIndex=z, blur=0)
        d.update(kw)
        if d.get("parentId"):
            # A hidden group does not hide what it clips, so a mask's children follow the mask's
            # visibility instead: `step()` copies every opacity change on a mask onto them.
            d["opacity"] = 0
            self.kids.setdefault(d["parentId"], []).append(id)
        else:
            d["x"], d["y"] = self._w(x, y)
            self.origin_of[id] = self.org
        if id != "ground":
            self.style.dress(d, self.pal)
        self.nodes.append(d)
        self.byid[id] = d
        return d

    def place(self, id, x, y):
        """Move a node to stage coordinates after it was made (e.g. once its height is known)."""
        d = self.byid[id]
        d["x"], d["y"] = self._w(x, y, id)

    def face(self, size: float, role: str | None = None) -> tuple[str, float]:
        if role == "mono":
            return MONO, size
        if role == "display" or (role is None and size >= DISPLAY_MIN):
            return self.style.display, size * self.style.display_scale
        return self.style.body, size

    def text(self, id, x, y, w, h, text, size, color=None, weight=600, align="left", z=20, role=None, **kw):
        fam, fs = self.face(size, role)
        if role != "mono" and fs != size:
            kw.setdefault("letterSpacing", self.style.display_tracking)
        if fam == self.style.display and role != "mono":
            weight = self.style.display_weight or weight
        return self.node(id, "text", x, y, w, h, z, text=text, color=color or self.pal.ink,
                         fontSize=round(fs, 1), fontWeight=weight, fontFamily=fam, labelFontFamily=fam,
                         textAlign=align, verticalAlign="middle", **kw)

    def icon(self, id, ref, x, y, size, z=20, color=None, **kw):
        paths, vb = icon_paths(ref, color)
        if color is None and _lum(self.pal.panel) < 0.3:
            # black brand marks (GitHub, X, Notion) vanish on a dark tile, so they take the ink
            # and their white counter-shapes (Notion's square) swap to the tile, so the mark inverts
            def flip(v):
                if isinstance(v, str) and len(v) == 4 and v[0] == "#":
                    v = "#" + "".join(ch * 2 for ch in v[1:])
                if isinstance(v, str) and len(v) == 7 and v[0] == "#":
                    return self.pal.ink if _lum(v) < 0.12 else self.pal.panel if _lum(v) > 0.92 else v
                return v
            paths = [dict(q, **{c: flip(q[c]) for c in ("fill", "stroke") if c in q}) for q in paths]
        h = size * vb["h"] / vb["w"] if vb.get("w") else size
        return self.node(id, "svg", x, y, size, h, z, svgPaths=paths, svgViewBox=vb,
                         fill=color or "#000000", **kw)

    def mask(self, id, x, y, w, h, z=15, **kw):
        """A clipping group. Children use local coordinates. It starts hidden like everything
        else and is switched on by `appear()`; its children stay at opacity 1 and are shown by
        moving them into the window rather than by fading."""
        return self.node(id, "group", x, y, w, h, z, clipContent=True, **kw)

    def rise_line(self, id, cx, cy, text, size, weight=600, color=None, z=20):
        """A headline line that rises into view through a mask. Returns the mask id."""
        w = text_width(text, size, weight) * 1.1 + 60
        h = size * 1.3 * max(1.0, self.style.display_scale ** 0.5)
        self.mask(id + "_m", cx - w / 2, cy - h / 2, w, h, z)
        self.text(id, 0, h, w, h, text, size, color=color, weight=weight, z=z + 1,
                  parentId=id + "_m", opacity=1, letterSpacing=-0.5, align="center")
        return id + "_m"

    # ---------------- camera ----------------
    def cam_at(self, t: float, strict: bool = False) -> dict:
        """Camera on the track at `t`. `strict` ignores moves that start exactly at `t`."""
        seg = None
        for s in self.cam:
            if s["t0"] < t or (s["t0"] == t and not strict):
                seg = s
        if seg is None:
            return dict(C0)
        if t >= seg["t1"] or seg["t1"] == seg["t0"]:
            return dict(seg["b"])
        return _lerp(seg["a"], seg["b"], _ease((t - seg["t0"]) / (seg["t1"] - seg["t0"]), seg["ease"]))

    def move_camera(self, camera: dict, dur: int, ease: str, org=None):
        """`camera` is {"c": start, "e": end, "d": ms, "ease": ..., "raw": world coords}. A start
        jumps there; an end moves there over d ms (linear when it outlives the step: a drift)."""
        raw = camera.get("raw")
        conv = (lambda c: dict(c)) if raw else (lambda c: self.world(c, org))
        t = self.t
        if camera.get("c") is not None:
            c = conv(camera["c"])
            self.cam.append(dict(t0=t, t1=t, a=c, b=c, ease="linear"))
        if camera.get("e") is not None:
            d = camera.get("d", dur)
            a = self.cam_at(t)
            e = camera.get("ease") or (ease if d <= dur else "linear")
            if e not in ("ease", "ease-in", "ease-out", "linear"):
                e = "ease-out"
            self.cam.append(dict(t0=t, t1=t + max(1, d), a=a, b=conv(camera["e"]), ease=e))

    # ---------------- steps ----------------
    def step(self, dur, ease="ease", ns=None, delays=None, actions=None, camera=None, note=""):
        ease = self.style.ease_map.get(ease, ease)
        ns = list(ns or [])
        for p in ns:
            if p["id"] == "bg":
                p["id"] = self.bg_id
        by = {p["id"]: p for p in ns}
        for p in list(ns):
            for prop in ("opacity", "blur"):
                if prop not in p:
                    continue
                for c in self.kids.get(p["id"], []):
                    if c in by:
                        by[c].setdefault(prop, p[prop])
                    else:
                        by[c] = dict(id=c, **{prop: p[prop]})
                        ns.append(by[c])
        for p in ns:
            if "x" in p or "y" in p:
                nd = self.byid.get(p["id"])
                if nd is not None and not nd.get("parentId"):
                    ox, oy = self.origin_of.get(p["id"], self.org)
                    if "x" in p:
                        p["x"] = p["x"] + ox
                    if "y" in p:
                        p["y"] = p["y"] + oy
        s = dict(note=note, durationMs=dur, easing=ease, nodes=ns, edges=[], actions=actions or [])
        if delays:
            s["delays"] = delays
        if camera:
            self.move_camera(camera, dur, ease, camera.get("org"))
        for p in ns:
            if "opacity" in p:
                (self.live.add if p["opacity"] > 0 else self.live.discard)(p["id"])
        self._cue(s)
        self.steps.append(s)
        self.t += dur
        return s

    def _cue(self, s: dict):
        """Sound cues read off the step itself, so scenes get them for free."""
        dur, ns, note = s["durationMs"], s["nodes"], s["note"]
        if dur > 1 and s["easing"] in ("back", "spring", "bounce", "ease-out") and \
                any("scaleX" in p and p.get("scaleX", 0) >= 1 for p in ns) and "press" not in note:
            self.cue("pop", n=sum(1 for p in ns if "scaleX" in p))
        for a in s["actions"]:
            if a.get("to", {}).get("typeProgress") == 1:
                self.cue("type", dur=a["durationMs"])
        if "press" in note:
            self.cue("click")

    def cue(self, kind: str, at: int | None = None, **kw):
        self.events.append(dict(t=200 + (self.t if at is None else at), kind=kind, **kw))

    def hold(self, ms, note="hold"):
        ms = round(ms * self.pace)
        if ms > 0:
            self.step(ms, "linear", note=note)

    @staticmethod
    def on(*ids):
        return [dict(id=i, opacity=1) for i in ids]

    @staticmethod
    def off(*ids):
        return [dict(id=i, opacity=0) for i in ids]

    def appear(self, *ids, note="on", extra=None):
        """Switch nodes on in a 1ms step, so the motion that follows never crossfades."""
        self.step(1, "linear", self.on(*ids) + (extra or []), note=note)

    def cut(self, show=(), bg=None, camera=None, note="cut", extra=None):
        """Cut to `show`: everything else on screen off, background swapped. The first cut of a
        scene plays the scene's transition; any later one is a plain 1ms hard cut."""
        camera = camera or {"c": C0}
        show = list(show)
        if self.pending:
            tx, self.pending = self.pending, None
            self.byid[self.bg_id]["fill"] = bg or self.pal.paper
            self.shown_org, self.cell = self.org, self._next_cell
            show = show + [b for b in self.backdrop if b not in show]
            self._transition(tx, show, camera, note, extra or [])
            return
        ns = self.off(*sorted(self.live - set(show) - set(self.backdrop))) + self.on(*show) + (extra or [])
        if bg:
            ns.append(dict(id=self.bg_id, fill=bg))
        self.step(1, "linear", ns, camera=camera, note=note)

    # ---------------- transitions ----------------
    def _scene_ids(self, ids) -> list[str]:
        """Ids plus the nodes their masks clip: what a blur has to reach."""
        out = []
        for i in ids:
            out.append(i)
            out += self.kids.get(i, [])
        return out

    def _transition(self, tx: str, show: list, camera: dict, note: str, extra: list):
        old = set(self.live)
        new_c = self.world(camera["c"]) if camera.get("c") is not None else self.world(C0)
        drift = {k: v for k, v in camera.items() if k != "c"}
        here = self.cam_at(self.t)
        self.transitions.append(dict(t=200 + self.t, kind=tx))
        if tx != "cut":
            self.cue("whoosh", tx=tx)
        n = len(self.transitions)
        off_old = lambda: self.off(*sorted(old - set(show)))

        if tx == "push":
            ms = self.style.push_ms
            self.step(1, "linear", self.on(*show) + extra, note=note + " (push in)")
            self.step(ms, "linear", camera={"e": new_c, "d": ms, "ease": "ease", "raw": True},
                      note="push")
            self.step(1, "linear", off_old(), note="push done")
        elif tx == "zoom":
            self.step(240, "ease-in", camera={"e": dict(here, zoom=here["zoom"] * 2.4), "d": 240,
                                               "ease": "ease-in", "raw": True}, note="zoom in",
                      ns=[dict(id=i, blur=10) for i in sorted(old) if i not in self.backdrop_ids()]
                      if self.style.blur else None)
            self.step(1, "linear", off_old() + self.on(*show) + extra,
                      camera={"c": dict(new_c, zoom=new_c["zoom"] * 0.55), "raw": True}, note=note)
            self.step(380, "ease-out", camera={"e": new_c, "d": 380, "ease": "ease-out", "raw": True},
                      note="zoom out")
        elif tx == "blur":
            fade = [i for i in sorted(old) if i not in self.backdrop_ids()]
            self.step(300, "ease-in", [dict(id=i, blur=18, opacity=0) for i in fade],
                      camera={"e": dict(here, zoom=here["zoom"] * 0.86), "d": 300, "ease": "ease-in",
                              "raw": True}, note="recede")
            fresh = [i for i in self._scene_ids(show) if i not in self.backdrop]
            self.step(1, "linear", off_old() + self.on(*show) + extra + [dict(id=i, blur=18) for i in fresh],
                      camera={"c": dict(new_c, zoom=new_c["zoom"] * 1.12), "raw": True}, note=note)
            self.step(340, "ease-out", [dict(id=i, blur=0) for i in fresh],
                      camera={"e": new_c, "d": 340, "ease": "ease-out", "raw": True}, note="focus")
        elif tx == "wipe":
            old_fill = self.byid[self.bg_id_prev]["fill"] if getattr(self, "bg_id_prev", None) else self.pal.paper
            new_fill = self.byid[self.bg_id]["fill"]
            band = new_fill if new_fill.lower() != old_fill.lower() else self.style.wipe_color(self.pal)
            vw, vh = VIEW_W / here["zoom"] + 40, VIEW_H / here["zoom"] + 40
            a = self.node(f"tx{n}_a", "rect", 0, 0, 0, vh, 900, fill=band)
            a["x"], a["y"] = here["x"] - vw / 2, here["y"] - vh / 2
            nw, nh = VIEW_W / new_c["zoom"] + 40, VIEW_H / new_c["zoom"] + 40
            b = self.node(f"tx{n}_b", "rect", 0, 0, nw, nh, 900, fill=band)
            b["x"], b["y"] = new_c["x"] - nw / 2, new_c["y"] - nh / 2
            self.origin_of[a["id"]] = self.origin_of[b["id"]] = (0, 0)
            ms = self.style.wipe_ms
            self.step(1, "linear", self.on(a["id"]), note="wipe on")
            self.step(ms, "ease-in", [dict(id=a["id"], w=vw)], note="wipe")
            self.step(1, "linear", off_old() + self.off(a["id"]) + self.on(*show, b["id"]) + extra,
                      camera={"c": new_c, "raw": True}, note=note)
            self.step(ms, "ease-out", [dict(id=b["id"], x=new_c["x"] + nw / 2, w=0)], note="unwipe")
            self.step(1, "linear", self.off(b["id"]), note="wipe off")
        else:
            self.step(1, "linear", off_old() + self.on(*show) + extra, camera={"c": new_c, "raw": True},
                      note=note)
        if drift.get("e") is not None:
            self.step(1, "linear", camera=dict(drift, c=None), note="drift")
        self.bg_id_prev = self.bg_id
        self.backdrop_prev = list(self.backdrop)

    def backdrop_ids(self) -> set[str]:
        return set(self.backdrop) | set(getattr(self, "backdrop_prev", []))

    # ---------------- helpers scenes share ----------------
    def tween(self, id, prop, a, b, dur):
        self._n += 1
        return {"id": f"tw_{id}_{self._n}", "type": "transformTween",
                "target": {"kind": "node", "id": id}, "from": {prop: a}, "to": {prop: b},
                "durationMs": dur, "offsetMs": 0, "ease": "linear"}

    def type_in(self, id, ms, note="type"):
        """Type a text node out. Switches it on first, in its own 1ms step."""
        self.appear(id, note=note + " on")
        self.step(ms, "linear", actions=[self.tween(id, "typeProgress", 0, 1, max(60, ms - 40))], note=note)

    def rise_in(self, *ids):
        return [dict(id=i, y=0) for i in ids]

    def rise_out(self, *ids):
        return [dict(id=i, y=-self.byid[i]["h"]) for i in ids]

    def count(self, ids: list[str], ms: int = 1000, note="count"):
        """Flip through pre-made frames of a number (made by `count_frames`), easing out so the
        digits race and then settle. Frames are lists, one entry per counter, shown together."""
        frames = list(zip(*ids)) if ids and isinstance(ids[0], list) else [(i,) for i in ids]
        n = len(frames)
        if n < 2:
            return
        ts = [round(ms * (1 - (1 - (j / (n - 1))) ** 2)) for j in range(n)]
        for j in range(1, n):
            self.step(1, "linear", self.off(*frames[j - 1]) + self.on(*frames[j]), note=f"{note} {j}")
            self.cue("tick", final=(j == n - 1))
            self.hold_raw(max(1, ts[j] - ts[j - 1] - 1), note)

    def hold_raw(self, ms, note="hold"):
        if ms > 0:
            self.step(ms, "linear", note=note)

    # ---------------- output ----------------
    def _camera_fields(self):
        """Write each step's camera from the track (see the module docstring)."""
        t, prev_end = 200, self.cam_at(0)
        for s in self.steps:
            ts, te = t, t + s["durationMs"]
            S, E = self.cam_at(ts - 200), self.cam_at(te - 200, strict=True)
            exact = [g for g in self.cam if g["t0"] == ts - 200 and g["t1"] == te - 200 and g["t1"] > g["t0"]]
            for k in ("camera", "cameraEnd", "cameraDurationMs", "cameraEasing"):
                s.pop(k, None)
            same = lambda a, b: all(abs(a[k] - b[k]) < 1e-3 for k in ("x", "y", "zoom"))
            if exact and same(S, prev_end) and exact[-1]["ease"] != "linear":
                s.update(camera=_r(E), cameraDurationMs=s["durationMs"], cameraEasing=exact[-1]["ease"])
            elif not (same(S, prev_end) and same(S, E)):
                s.update(camera=_r(S), cameraDurationMs=0, cameraEnd=_r(E))
            prev_end, t = E, te

    def project(self, name: str, hold_end: int = 1500) -> dict:
        self.hold(hold_end, "end hold")
        self._camera_fields()
        start = _r(self.cam_at(0))
        ground = dict(note="ground", durationMs=200, easing="linear", nodes=copy.deepcopy(self.nodes),
                      edges=[], actions=[], camera=start)
        steps = [ground] + self.steps
        artboard = dict(x=-640, y=-360, width=1280, height=720, background=self.pal.paper,
                        showBounds=False, shadeOutside=False, cropPreview=True, atmosphere=False)
        return {"artboard": artboard,
                "diagrams": [{"id": "launch-reel", "name": name, "camera": start,
                              "nodes": copy.deepcopy(self.nodes), "edges": [], "paths": {},
                              "steps": steps}],
                "showCaptions": False, "floatEnabled": False}

    @property
    def duration_ms(self) -> int:
        return 200 + self.t


def _r(c: dict) -> dict:
    return {"x": round(c["x"], 2), "y": round(c["y"], 2), "zoom": round(c["zoom"], 4)}
