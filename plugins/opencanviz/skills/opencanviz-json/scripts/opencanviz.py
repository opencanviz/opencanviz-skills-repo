#!/usr/bin/env python3
"""Build and check openCanviz project JSON (schema v1). One file, Python 3.9+, stdlib only.

Build:
    import sys; sys.path.insert(0, "<skill>/scripts")
    from opencanviz import Project

    p = Project("How DNS works", aspect="16:9")         # or "9:16", "1:1"
    s = p.scene("Lookup")                               # ids get an "s1_" prefix
    title, body = p.area().cut_top(120)                 # layout rects inside the margins
    cells = body.row(3)                                 # also column, grid, stack, centered
    t = s.text("How DNS works", at=title, fontSize=64)
    a, b, c = [s.box(name, at=r.centered(360, 200)) for name, r in zip(["Browser", "Resolver", "Server"], cells)]
    ab, bc = s.arrow(a, b), s.arrow(b, c)
    s.step("You type a name into the browser.").reveal(t).reveal(a)
    s.step("The browser asks a resolver.").draw(ab).reveal(b)
    s.step("The resolver asks the name server.").draw(bc).reveal(c)
    p.save("out.json")                                  # validates, raises OpenCanvizError on problems

Check any file (hand-written too):
    python3 opencanviz.py check out.json

Rules the builder enforces for you: step 0 is the full snapshot (later nodes at opacity 0, later
edges at trim 0) and equals the scene's nodes/edges; later steps are deltas; reveals set opacity 1
plus a visibility action; draws set trim 1 plus an edgeTween; an arrow may only be visible while
both of its end nodes are visible (otherwise save() raises and tells you which step to draw it in);
hiding or removing a node also hides or removes its arrows; ids are unique and prefixed per scene;
step durations are computed from the actions and narration unless you pass duration=.
"""

import json
import math
import os
import re
import sys

__all__ = ["Project", "Scene", "Step", "Node", "Edge", "Rect", "OpenCanvizError",
           "validate", "schema_errors", "check_file", "row", "column", "grid", "stack", "flow"]

SCHEMA_URL = "https://opencanviz.com/schema/v1.json"
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "schema.json")

ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}

NODE_KINDS = {
    "rect", "circle", "diamond", "triangle", "polygon", "star", "arrow", "cylinder", "text", "callout",
    "wedge", "chevron", "funnel", "progress", "svg", "icon", "group", "glyph", "lottie", "uml-actor",
    "uml-lifeline", "uml-class", "uml-note", "algo-array", "algo-pointer", "algo-grid", "algo-variable",
    "algo-tree", "algo-linked-list", "algo-graph", "algo-chart", "algo-chart-line", "algo-chart-scatter"}

NODE_FIELDS = {
    "id", "kind", "x", "y", "w", "h", "label", "labelColor", "labelFontSize", "labelFontWeight",
    "labelFontStyle", "labelFontFamily", "labelPadding", "labelTextAlign", "fill", "stroke", "strokeWidth",
    "strokeDashArray", "cornerRadius", "opacity", "zIndex", "text", "fontFamily", "fontSize", "fontWeight",
    "fontStyle", "lineHeight", "letterSpacing", "color", "textAlign", "verticalAlign", "wrap", "autoFit",
    "typeProgress", "highlightedLines", "syntaxStyle", "rotationZ", "rotationX", "rotationY", "scaleX",
    "scaleY", "pivotX", "pivotY", "parentId", "rough", "roughness", "glow", "pointerSide", "points",
    "innerRadius", "startAngle", "endAngle", "value", "progressColor", "asset", "iconStyle", "cellValues",
    "cellColors"}

EDGE_FIELDS = {
    "id", "from", "to", "fromXY", "toXY", "fromPort", "toPort", "stroke", "width", "opacity", "trim",
    "trimStart", "arrow", "endArrowType", "startArrowType", "arrowSize", "strokeStyle", "lineType", "router",
    "cornerRadius", "label", "labelColor", "labelFontSize", "labelPosition", "labelPositionT",
    "labelBgColor", "animationStyle", "flowSpeed", "waypoints", "zIndex"}

INTERNAL_FIELDS = {"_selected", "_animatedProps", "illuOf", "imageFailed", "_addedNodeIds", "_removedNodeIds",
                   "_addedEdgeIds", "_removedEdgeIds", "audioData", "audioUrl", "audioDurationMs", "words"}

VIS_IN = {"fadeIn", "show", "slideInLeft", "slideInRight", "slideInUp", "slideInDown"}
VIS_OUT = {"fadeOut", "hide", "slideOutLeft", "slideOutRight", "slideOutUp", "slideOutDown"}
EASINGS = {"linear", "ease", "ease-in", "ease-out", "spring", "bounce", "elastic", "back", "back-in", "step"}
TRANSITION_KINDS = {
    "crossfade", "slideDown", "slideUp", "slideLeft", "slideRight", "pushUp", "pushDown", "pushLeft",
    "pushRight", "travelOffUp", "travelOffDown", "travelOffLeft", "travelOffRight", "scribbleWipe",
    "scribbleWipeLeft", "scribbleWipeUp", "scribbleWipeDown", "colorWipe", "colorWipeLeft", "colorWipeUp",
    "colorWipeDown", "morph"}
VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}
TWEEN_PROPS = {"x", "y", "w", "h", "scaleX", "scaleY", "rotationX", "rotationY", "rotationZ", "opacity", "fill",
               "stroke", "strokeWidth", "strokeTrimStart", "strokeTrimEnd", "typeProgress", "drawProgress",
               "blur", "value"}

THEMES = {
    "dark": {"background": "#0f172a", "fill": "#1e293b", "stroke": "#38bdf8", "text": "#f8fafc",
             "muted": "#94a3b8", "edge": "#94a3b8"},
    "light": {"background": "#f8fafc", "fill": "#ffffff", "stroke": "#334155", "text": "#0f172a",
              "muted": "#475569", "edge": "#64748b"},
}

COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|rgba?\([^)]*\)|transparent|none)$")
CHAR_W = 0.55          # average glyph width as a share of the font size (0.6 for bold and edge labels)
LINE_H = 1.2           # line height used to size text boxes
TEXT_PAD = 8           # breathing room inside a text node, top and bottom
LABEL_PAD = 10         # openCanviz default label padding
EDGE_GAP = 8           # an edge starts this far from its node
MIN_LINK_GAP = 60      # room for an arrowhead between two connected nodes


def caption_band(width, height):
    """Share of the frame height, at the bottom, that captions cover (20% landscape, 30% portrait)."""
    return 0.3 if height > width else 0.2


def edge_label_min(width, height):
    """Smallest readable edge-label font: 22 px landscape, 28 px portrait."""
    return 28 if height > width else 22


def label_width(label, font_size):
    """Estimated width of an edge label pill."""
    return len(str(label)) * 0.6 * font_size + 24


def link_gap(label=None, font_size=24, vertical=False):
    """Gap two connected nodes need: arrowhead room, plus the label if there is one."""
    if not label:
        return MIN_LINK_GAP
    if vertical:
        return max(MIN_LINK_GAP, font_size * 1.2 + 8 + 48)
    return max(MIN_LINK_GAP, label_width(label, font_size) + 2 * EDGE_GAP + 24)


class OpenCanvizError(ValueError):
    """Raised when the project would not import or play correctly. The message says how to fix it."""


# --------------------------------------------------------------------------------------------- layout

class Rect:
    """A layout box in world px (x, y = top-left). Pass it as at= when you add a node."""

    def __init__(self, x, y, w, h, label_size=24):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)
        self.label_size = label_size  # edge label font the auto gaps are sized for (project.area() sets it)

    def _r(self, x, y, w, h):
        return Rect(x, y, w, h, self.label_size)

    def __repr__(self):
        return "Rect(x=%g, y=%g, w=%g, h=%g)" % (self.x, self.y, self.w, self.h)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def inset(self, dx, dy=None):
        """Shrink by dx on the left/right and dy (default dx) on the top/bottom."""
        dy = dx if dy is None else dy
        return self._r(self.x + dx, self.y + dy, self.w - 2 * dx, self.h - 2 * dy)

    def centered(self, w, h=None):
        """A w x h box centered in this one (clamped to fit)."""
        w = min(w, self.w)
        h = self.h if h is None else min(h, self.h)
        return self._r(self.cx - w / 2, self.cy - h / 2, w, h)

    def cut_top(self, h, gap=40):
        """Split into (top band of height h, the rest below it)."""
        return self._r(self.x, self.y, self.w, h), self._r(self.x, self.y + h + gap, self.w, self.h - h - gap)

    def cut_bottom(self, h, gap=40):
        """Split into (the rest above, bottom band of height h). Note the order: the band is [1]."""
        return self._r(self.x, self.y, self.w, self.h - h - gap), self._r(self.x, self.y + self.h - h, self.w, h)

    def row(self, n, gap=None, w=None, h=None, labels=None, label_size=None):
        """n cells side by side, for nodes joined left to right.

        gap=None sizes the gap for arrows: 60 px, or wide enough for the longest of labels (edge labels).
        w/h fix the cell size (the group is centered), else cells share the space.
        """
        label_size = self.label_size if label_size is None else label_size
        if gap is None:
            gap = max([link_gap(l, label_size) for l in (labels or [None])])
        cw = (self.w - gap * (n - 1)) / n if w is None else w
        total = cw * n + gap * (n - 1)
        if total > self.w + 0.5 or cw < 10:
            raise OpenCanvizError("row(%d) needs %d px (cells %d + gaps %d) but the area is %d px wide. Use flow(), "
                                  "which wraps to more rows, or shorter edge labels." % (n, total, cw, gap, self.w))
        ch = self.h if h is None else min(h, self.h)
        x0 = self.x + (self.w - total) / 2
        return [self._r(x0 + i * (cw + gap), self.cy - ch / 2, cw, ch) for i in range(n)]

    def column(self, n, gap=None, w=None, h=None, labels=None, label_size=None):
        """n cells stacked top to bottom (gap=None sizes it for arrows and their labels)."""
        label_size = self.label_size if label_size is None else label_size
        if gap is None:
            gap = max([link_gap(l, label_size, vertical=True) for l in (labels or [None])])
        ch = (self.h - gap * (n - 1)) / n if h is None else h
        total = ch * n + gap * (n - 1)
        if total > self.h + 0.5 or ch < 10:
            raise OpenCanvizError("column(%d) needs %d px but the area is %d px tall; use a smaller h or gap, or "
                                  "grid()/flow()" % (n, total, self.h))
        cw = self.w if w is None else min(w, self.w)
        y0 = self.y + (self.h - total) / 2
        return [self._r(self.cx - cw / 2, y0 + i * (ch + gap), cw, ch) for i in range(n)]

    def stack(self, n, h=None, gap=None, w=None, labels=None, label_size=None):
        """n cards stacked and centered vertically (portrait lists). h=None shares the height."""
        return self.column(n, gap=gap, w=w, h=h, labels=labels, label_size=label_size)

    def grid(self, rows, cols, gap=60):
        """rows x cols cells, row by row."""
        out = []
        for r in self.column(rows, gap=gap):
            out.extend(r.row(cols, gap=gap))
        return out

    def flow(self, n, labels=None, label_size=None, min_w=220, max_w=520, ratio=0.6):
        """n boxes for a chain a -> b -> c ..., in chain order, sized to fill the area.

        Picks 1 to 4 rows so boxes stay readable and the chain fills about 60-75% of the area. Rows run
        as a snake (left to right, then right to left) so every link joins neighbours, never skips
        over a box. labels are the edge labels (n - 1); gaps are sized so each label fits.
        """
        label_size = self.label_size if label_size is None else label_size
        hgap = max([link_gap(l, label_size) for l in (labels or [None])])
        vgap = max([link_gap(l, label_size, vertical=True) for l in (labels or [None])])
        best = None
        for r in range(1, min(n, 4) + 1):
            c = int(math.ceil(n / float(r)))
            if r > 1 and int(math.ceil(n / float(r - 1))) == c:
                continue
            cw = min(max_w, (self.w - hgap * (c - 1)) / c)
            if cw < min_w and r < min(n, 4):
                continue
            bh = min(cw * ratio, (self.h - vgap * (r - 1)) / r, 360)
            if bh < 80:
                continue
            gw, gh = c * cw + (c - 1) * hgap, r * bh + (r - 1) * vgap
            fill = gw * gh / (self.w * self.h)
            score = -abs(min(fill, 0.75) - 0.68) - (0.02 * r)
            if best is None or score > best[0]:
                best = (score, r, c, cw, bh)
        if best is None:
            raise OpenCanvizError("flow(%d): the boxes do not fit this area at a readable size; split the chain "
                                  "over two scenes or shorten the edge labels." % n)
        _, r, c, cw, bh = best
        spare = self.h - r * bh - (r - 1) * vgap
        vg = vgap + (min(spare / max(r + 1, 1), bh * 0.5) if r > 1 else 0)
        gh = r * bh + (r - 1) * vg
        y0 = self.y + (self.h - gh) / 2
        out = []
        for i in range(n):
            ri, ci = divmod(i, c)
            in_row = min(c, n - ri * c)
            gw = in_row * cw + (in_row - 1) * hgap
            full_w = c * cw + (c - 1) * hgap
            x_left = self.x + (self.w - full_w) / 2
            col = ci if ri % 2 == 0 else (c - 1 - ci)
            out.append(self._r(x_left + col * (cw + hgap), y0 + ri * (bh + vg), cw, bh))
        return out


def row(area, n, **kw):
    return area.row(n, **kw)


def column(area, n, **kw):
    return area.column(n, **kw)


def stack(area, n, **kw):
    return area.stack(n, **kw)


def grid(area, rows, cols, gap=60):
    return area.grid(rows, cols, gap)


def flow(area, n, **kw):
    return area.flow(n, **kw)


# ------------------------------------------------------------------------------------------ text fit

def _is_bold(weight):
    return weight == "bold" or (isinstance(weight, (int, float)) and weight >= 600)


def text_lines(text, font_size, width, bold=False):
    """Estimated wrapped line count, or None if a single word is wider than width."""
    cw = font_size * (CHAR_W + (0.05 if bold else 0))
    if width <= 0:
        return None
    lines = 0
    for para in str(text).split("\n"):
        cur = 0.0
        lines += 1
        for word in para.split(" "):
            ww = len(word) * cw
            if ww > width + 0.5:
                return None
            add = ww if cur == 0 else ww + cw
            if cur and cur + add > width:
                lines += 1
                cur = ww
            else:
                cur += add
    return lines


def _label_box(kind, w, h):
    inset = {"diamond": 0.5, "circle": 0.72, "triangle": 0.55, "star": 0.5, "cylinder": 0.8}.get(kind, 1.0)
    if kind == "cylinder":
        return w - 2 * LABEL_PAD, h * inset - 2 * LABEL_PAD
    return w * inset - 2 * LABEL_PAD, h * inset - 2 * LABEL_PAD


def text_overflow(node):
    """None if the node's text or label fits (estimate), else a short reason.

    Height needed = lines x fontSize x lineHeight (1.2 unless set) + padding.
    """
    kind = node.get("kind")
    w, h = node.get("w", 0) or 0, node.get("h", 0) or 0
    if kind == "text" and node.get("text"):
        fs = node.get("fontSize", 24)
        lh = max(node.get("lineHeight", LINE_H), LINE_H)
        bw, bh, txt, bold = w, h - 2 * TEXT_PAD, node["text"], _is_bold(node.get("fontWeight"))
    elif node.get("label") and kind not in ("svg", "icon", "lottie", "group"):
        fs = node.get("labelFontSize", 14)
        lh = LINE_H
        pad = node.get("labelPadding", LABEL_PAD)
        bw, bh = _label_box(kind, w, h)
        bw, bh = bw + 2 * LABEL_PAD - 2 * pad, bh + 2 * LABEL_PAD - 2 * pad
        txt, bold = node["label"], node.get("labelFontWeight") == "bold"
    else:
        return None
    n = text_lines(txt, fs, bw, bold)
    if n is None:
        return "a word is wider than the box at font size %g" % fs
    need = n * fs * lh
    if need > bh + 1:
        return "%d line(s) at font size %g need %d px of height plus padding, the box is %d px tall" % (n, fs, need, h)
    return None


def fit_font(text, start, w, h, kind="text", bold=False, minimum=14, line_height=LINE_H):
    """Largest font size <= start at which text fits a w x h node (estimate)."""
    fs = float(start)
    while fs >= minimum:
        probe = {"kind": kind, "w": w, "h": h, "fontWeight": 700 if bold else 400,
                 "labelFontWeight": "bold" if bold else "normal", "lineHeight": line_height}
        if kind == "text":
            probe.update(text=text, fontSize=fs)
        else:
            probe.update(label=text, labelFontSize=fs)
        if text_overflow(probe) is None:
            return int(fs)
        fs -= 2
    return None


# ------------------------------------------------------------------------------------------- builder

def _clean(v):
    v = round(float(v), 1)
    return int(v) if v == int(v) else v


def _slug(s):
    s = re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")
    return (s[:24].strip("_") or "item")


def _check_fields(fields, allowed, what):
    for k, v in fields.items():
        if k in INTERNAL_FIELDS:
            raise OpenCanvizError("%s: '%s' is set by openCanviz; leave it out." % (what, k))
        if k == "strokeWidth" and what.startswith("edge"):
            raise OpenCanvizError("%s: edges take width=, not strokeWidth=." % what)
        if k == "fillOpacity":
            raise OpenCanvizError("%s: fillOpacity does nothing in openCanviz; use a darker hex or opacity=." % what)
        if k not in allowed:
            close = [a for a in allowed if a.lower() == k.lower().replace("_", "")]
            hint = " Did you mean %s?" % close[0] if close else " Allowed: see schema.json."
            raise OpenCanvizError("%s: unknown field '%s'.%s" % (what, k, hint))
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise OpenCanvizError("%s: %s is %r; use a real number." % (what, k, v))


class Node:
    """A node handle returned by Scene.box/text/icon/node. Read its id, rect, or fields."""

    def __init__(self, scene, nid, fields):
        self.scene, self.id, self.fields = scene, nid, fields
        self.events = []      # (step_index, "in"|"out"|"remove")

    @property
    def rect(self):
        f = self.fields
        return Rect(f["x"], f["y"], f["w"], f["h"])

    def __repr__(self):
        return "Node(%s)" % self.id


class Edge:
    """An arrow handle returned by Scene.arrow."""

    def __init__(self, scene, eid, a, b, fields):
        self.scene, self.id, self.a, self.b, self.fields = scene, eid, a, b, fields
        self.events = []      # (step_index, "draw"|"undraw"|"remove")

    def __repr__(self):
        return "Edge(%s)" % self.id

    @property
    def labeled(self):
        return bool(self.fields.get("label"))

    def _tween(self, drawing):
        """edgeTween for a draw-in (True) or draw-out. A labeled edge also carries opacity, because a
        trim-0 edge's label otherwise floats at its start port."""
        fr, to = ({"trim": 0}, {"trim": 1}) if drawing else ({"trim": 1}, {"trim": 0})
        if self.labeled:
            shown = self.fields.get("opacity", 1)
            fr["opacity"], to["opacity"] = shown, (shown if drawing else 0)
        return {"type": "edgeTween", "target": {"kind": "edge", "id": self.id}, "from": fr, "to": to}


class Step:
    """One beat of a scene. Methods return the step, so calls chain.

    Actions run one after another inside the step unless you pass offset= (ms) or offset="with"
    (start together with the previous action).
    """

    def __init__(self, scene, index, caption, narration, duration, easing):
        self.scene, self.index = scene, index
        self.caption, self.narration, self.duration, self.easing = caption, narration, duration, easing
        self.node_patch, self.edge_patch = {}, {}
        self.actions, self.remove_nodes, self.remove_edges = [], [], []
        self.camera_spec = None
        self._cursor, self._last_start = 0, 0

    # timing
    def _place(self, duration, offset):
        if offset == "with":
            start = self._last_start
        elif offset is None:
            start = self._cursor
        else:
            if not isinstance(offset, (int, float)) or offset < 0:
                raise OpenCanvizError("step %d: offset must be ms >= 0 or \"with\", got %r" % (self.index, offset))
            start = offset
        self._last_start = start
        self._cursor = max(self._cursor, start + duration)
        return start

    def _action(self, act, duration, offset):
        start = self._place(duration, offset)
        act["durationMs"] = duration
        if start:
            act["offsetMs"] = start
        self.actions.append(act)
        return act

    def _own(self, item, cls):
        if not isinstance(item, cls) or item.scene is not self.scene:
            raise OpenCanvizError("step %d: expected a %s from this scene, got %r" % (self.index, cls.__name__, item))

    def reveal(self, node, style="fadeIn", duration=500, offset=None, ease=None, distance=None):
        """Show a hidden node: fadeIn, show, slideInLeft/Right/Up/Down. Sets opacity 1 for you."""
        self._own(node, Node)
        if style not in VIS_IN:
            raise OpenCanvizError("reveal(%s): style must be one of %s" % (node.id, sorted(VIS_IN)))
        node.events.append((self.index, "in"))
        act = {"type": "visibility", "target": {"kind": "node", "id": node.id}, "mode": style}
        if ease:
            act["ease"] = ease
        if distance is not None:
            act["slideDistance"] = distance
        self._action(act, duration, offset)
        return self

    def hide(self, item, style="fadeOut", duration=400, offset=None, ease=None):
        """Hide a node (fadeOut, hide, slideOut*) or undraw an arrow. Arrows of a hidden node are undrawn too."""
        if isinstance(item, Edge):
            self._own(item, Edge)
            item.events.append((self.index, "undraw"))
            self._action(item._tween(False), duration, offset)
            return self
        self._own(item, Node)
        if style not in VIS_OUT:
            raise OpenCanvizError("hide(%s): style must be one of %s" % (item.id, sorted(VIS_OUT)))
        item.events.append((self.index, "out"))
        act = {"type": "visibility", "target": {"kind": "node", "id": item.id}, "mode": style}
        if ease:
            act["ease"] = ease
        self._action(act, duration, offset)
        return self

    def draw(self, edge, duration=700, offset=None, ease="ease-out"):
        """Draw an arrow in (trim 0 -> 1). Both end nodes must be visible by the end of this step."""
        self._own(edge, Edge)
        edge.events.append((self.index, "draw"))
        act = edge._tween(True)
        if ease:
            act["ease"] = ease
        self._action(act, duration, offset)
        return self

    def remove(self, item):
        """Remove a node (and its arrows) or an arrow from this step on. A labeled arrow is drawn out and
        faded instead (hide), because a removed edge undraws to trim 0 with its label stuck at its start."""
        if isinstance(item, Edge) and item.labeled:
            return self.hide(item)
        if isinstance(item, Edge):
            self._own(item, Edge)
            item.events.append((self.index, "remove"))
            self.remove_edges.append(item.id)
        else:
            self._own(item, Node)
            item.events.append((self.index, "remove"))
            self.remove_nodes.append(item.id)
        return self

    def set(self, item, **fields):
        """Change fields from this step on; numbers and colors tween across the step. Not opacity/trim."""
        if isinstance(item, Edge):
            self._own(item, Edge)
            _check_fields(fields, EDGE_FIELDS - {"id", "from", "to"}, "edge %s" % item.id)
            if "trim" in fields or "opacity" in fields:
                raise OpenCanvizError("set(%s): use draw()/hide() for trim and opacity." % item.id)
            self.edge_patch.setdefault(item.id, {}).update(fields)
        else:
            self._own(item, Node)
            _check_fields(fields, NODE_FIELDS - {"id", "kind"}, "node %s" % item.id)
            if "opacity" in fields:
                raise OpenCanvizError("set(%s): use reveal()/hide() to change visibility, not opacity=." % item.id)
            self.node_patch.setdefault(item.id, {}).update(fields)
        return self

    def move(self, node, x=None, y=None, w=None, h=None, at=None, duration=None, offset=None, ease="ease-out"):
        """Move/resize a node. Without duration it tweens over the whole step; with duration a transformTween runs."""
        self._own(node, Node)
        if at is not None:
            x, y, w, h = at
        to = {k: v for k, v in (("x", x), ("y", y), ("w", w), ("h", h)) if v is not None}
        if not to:
            raise OpenCanvizError("move(%s): give x/y/w/h or at=Rect." % node.id)
        self.node_patch.setdefault(node.id, {}).update(to)
        if duration is not None:
            act = {"type": "transformTween", "target": {"kind": "node", "id": node.id}, "to": dict(to)}
            if ease:
                act["ease"] = ease
            self._action(act, duration, offset)
        return self

    def typewrite(self, node, duration=1200, offset=None):
        """Type a text node's text in (typeProgress 0 -> 1)."""
        self._own(node, Node)
        if node.fields.get("kind") != "text":
            raise OpenCanvizError("typewrite(%s): only text nodes can be typed." % node.id)
        node.fields["_type_step"] = self.index
        if self.index > 0:
            self.node_patch.setdefault(node.id, {})["typeProgress"] = 1
        self._action({"type": "transformTween", "target": {"kind": "node", "id": node.id},
                      "from": {"typeProgress": 0}, "to": {"typeProgress": 1}, "ease": "linear"}, duration, offset)
        return self

    def camera(self, x=0, y=0, zoom=1.0, duration=1000, offset=None, ease="ease-out"):
        """Pan/zoom so world point (x, y) is centered. zoom 1 = the whole artboard."""
        if zoom <= 0:
            raise OpenCanvizError("camera(): zoom must be > 0.")
        start = self._place(duration, offset)
        self.camera_spec = {"camera": {"x": x, "y": y, "zoom": zoom}, "cameraDurationMs": duration,
                            "cameraEasing": ease}
        if start:
            self.camera_spec["cameraOffsetMs"] = start
        return self

    def focus(self, node, zoom=1.5, duration=1000, offset=None, ease="ease-out"):
        """Camera zoom onto a node's center."""
        r = node.rect
        return self.camera(r.cx, r.cy, zoom, duration, offset, ease)

    def wait(self, ms):
        """Leave a pause before the next sequential action."""
        self._cursor += ms
        return self


class Scene:
    """A scene: add nodes and arrows, then steps. Node ids are prefixed with s<N>_."""

    def __init__(self, project, index, name, transition, background):
        self.project, self.index, self.name = project, index, name
        self.prefix = "s%d_" % (index + 1)
        self.transition, self.background = transition, background
        self.nodes, self.edges, self.steps, self._ids = [], [], [], set()

    def _id(self, want):
        base = want if want.startswith(self.prefix) else self.prefix + _slug(want)
        nid, n = base, 2
        while nid in self._ids:
            nid, n = "%s_%d" % (base, n), n + 1
        self._ids.add(nid)
        return nid

    def _geom(self, at, x, y, w, h, what):
        if at is not None:
            x, y, w, h = at
        if None in (x, y, w, h):
            raise OpenCanvizError("%s: give at=Rect (from project.area() and its row/column/grid/stack) or x, y, w, h."
                                  % what)
        if w < 10 or h < 10:
            raise OpenCanvizError("%s: %gx%g is too small; openCanviz skips nodes under 10x10 px. Draw lines as arrows."
                                  % (what, w, h))
        return {"x": _clean(x), "y": _clean(y), "w": _clean(w), "h": _clean(h)}

    def node(self, kind, label=None, at=None, x=None, y=None, w=None, h=None, id=None, **fields):
        """Any node kind from schema.json (rect, circle, diamond, cylinder, star, callout, ...)."""
        if kind not in NODE_KINDS:
            raise OpenCanvizError("node kind '%s' is not in the schema. Use one of: %s" % (kind, ", ".join(sorted(NODE_KINDS))))
        what = "%s %r" % (kind, label or id or "")
        _check_fields(fields, NODE_FIELDS - {"id", "kind", "x", "y", "w", "h"}, what)
        nid = self._id(id or label or fields.get("text") or kind)
        f = {"id": nid, "kind": kind}
        f.update(self._geom(at, x, y, w, h, what))
        th = self.project.colors
        if label is not None:
            f["label"] = label
            f.setdefault("labelColor", th["text"])
        if kind not in ("text", "svg", "icon", "progress", "group"):
            f.update({"fill": th["fill"], "stroke": th["stroke"], "strokeWidth": 3})
            if kind == "rect":
                f["cornerRadius"] = 16
        f.update(fields)
        if label is not None and "labelFontSize" not in fields:
            fs = fit_font(label, self.project.base_font, f["w"], f["h"], kind, f.get("labelFontWeight") == "bold")
            if fs is None:
                raise OpenCanvizError("%s: the label does not fit a %gx%g box even at 14 px. Make the box bigger or "
                                      "the label shorter." % (what, f["w"], f["h"]))
            f["labelFontSize"] = fs
        n = Node(self, nid, f)
        self.nodes.append(n)
        return n

    def box(self, label, at=None, **kw):
        """A rounded rect with a label."""
        return self.node("rect", label, at=at, **kw)

    def text(self, text, at=None, fontSize=None, **kw):
        """A text node. Without fontSize the largest size that fits (up to 1.5x the base) is used."""
        fields = {"text": text, "fontWeight": 400, "color": self.project.colors["text"], "textAlign": "center",
                  "verticalAlign": "middle", "fill": "transparent", "stroke": "none"}
        fields.update(kw)
        geom_kw = {k: fields.pop(k) for k in ("x", "y", "w", "h", "id") if k in fields}
        n = self.node("text", None, at=at, **dict(geom_kw, **fields))
        if fontSize is None:
            fs = fit_font(text, self.project.base_font * 1.5, n.fields["w"], n.fields["h"], "text",
                          _is_bold(n.fields.get("fontWeight")), line_height=n.fields.get("lineHeight", LINE_H))
            if fs is None:
                raise OpenCanvizError("text %r does not fit a %gx%g box even at 14 px. Make it bigger or shorter."
                                      % (text[:40], n.fields["w"], n.fields["h"]))
            fontSize = fs
        n.fields["fontSize"] = fontSize
        return n

    def icon(self, ref, at=None, **kw):
        """An Iconify icon, e.g. icon("mdi:database", at=rect). Loads when the project opens in the editor."""
        if ":" not in ref:
            raise OpenCanvizError("icon(%r): use an Iconify name like 'mdi:database'." % ref)
        kw.setdefault("id", ref.split(":")[-1])
        return self.node("svg", None, at=at, asset={"type": "icon", "source": "iconify", "ref": ref}, **kw)

    def progress(self, value=0.0, at=None, **kw):
        """A progress bar (value 0..1); animate it with step.set(bar, value=...)."""
        fields = {"value": value, "fill": self.project.colors["fill"], "stroke": "none", "progressColor": "#f59e0b"}
        fields.update(kw)
        return self.node("progress", None, at=at, **fields)

    def arrow(self, a, b, label=None, id=None, route=None, **fields):
        """An edge from node a to node b.

        Ports face each other unless you pass fromPort/toPort. route="below" or "above" sends a skip
        connection along its own lane under or over the row, so it does not cross the boxes between.
        Labels get a readable font (24 px landscape, 30 px portrait) and sit beside the line.
        """
        for end in (a, b):
            if not isinstance(end, Node) or end.scene is not self:
                raise OpenCanvizError("arrow(): both ends must be nodes of this scene, got %r" % (end,))
        what = "edge %s->%s" % (a.id, b.id)
        _check_fields(fields, EDGE_FIELDS - {"id", "from", "to"}, what)
        if route not in (None, "below", "above", "left", "right"):
            raise OpenCanvizError("%s: route must be None, 'below', 'above', 'left' or 'right'." % what)
        eid = self._id(id or "%s_to_%s" % (a.id[len(self.prefix):], b.id[len(self.prefix):]))
        f = {"id": eid, "from": a.id, "to": b.id}
        if route:
            side = {"below": "S", "above": "N", "left": "W", "right": "E"}[route]
            f.update({"fromPort": side, "toPort": side, "lineType": "elbowed"})
        elif "fromPort" not in fields and "toPort" not in fields:
            ra, rb = a.rect, b.rect
            dx, dy = rb.cx - ra.cx, rb.cy - ra.cy
            if abs(dx) >= abs(dy):
                f["fromPort"], f["toPort"] = ("E", "W") if dx >= 0 else ("W", "E")
            else:
                f["fromPort"], f["toPort"] = ("S", "N") if dy >= 0 else ("N", "S")
            if ra.cy == rb.cy or ra.cx == rb.cx:
                f["lineType"] = "straight"
        f.update({"stroke": self.project.colors["edge"], "width": 4, "arrow": "end"})
        if label is not None:
            pos = {"below": "below", "above": "above"}.get(route, "above")
            # At 22 px and up the renderer's label overlaps its own line whatever labelPosition says,
            # so the label gets a pill in the background color that masks the line behind it.
            f.update({"label": label, "labelColor": self.project.colors["muted"],
                      "labelFontSize": self.project.edge_label_font, "labelPosition": pos,
                      "labelBgColor": self.scene_background()})
            if not route and f.get("fromPort") in ("N", "S"):
                f["labelPosition"] = "center"
        f.update(fields)
        e = Edge(self, eid, a, b, f)
        self.edges.append(e)
        return e

    def scene_background(self):
        return self.background or self.project.colors["background"]

    def step(self, caption, narration=None, duration=None, easing=None):
        """Add a step. narration defaults to the caption; pass narration=False for no voice line."""
        if not caption or not str(caption).strip():
            raise OpenCanvizError("scene %d step %d: give a caption (one 8-20 word line)." % (self.index + 1, len(self.steps)))
        if easing is not None and easing not in EASINGS:
            raise OpenCanvizError("step easing must be one of %s" % sorted(EASINGS))
        st = Step(self, len(self.steps), caption, caption if narration is None else narration, duration, easing)
        self.steps.append(st)
        return st

    # compile ----------------------------------------------------------------------------------
    def _timelines(self):
        """Visible-at-end-of-step arrays for nodes and edges; raises on impossible orders."""
        n_steps = len(self.steps)
        vis = {}
        for n in self.nodes:
            ev = sorted(n.events, key=lambda e: e[0])
            state = not ev or ev[0][1] != "in"
            n.initial_visible = state if not (ev and ev[0] == (0, "in")) else True
            n.first_in = ev[0][0] if ev and ev[0][1] == "in" else None
            arr, i = [], 0
            for k in range(n_steps):
                while i < len(ev) and ev[i][0] == k:
                    kind = ev[i][1]
                    if kind == "in" and state and not (k == 0 and i == 0):
                        raise OpenCanvizError("%s is already visible when step %d reveals it. Reveal a node once, or "
                                              "hide it in an earlier step first." % (n.id, k))
                    if kind in ("out", "remove") and not state:
                        raise OpenCanvizError("%s is already hidden when step %d hides/removes it." % (n.id, k))
                    state = kind == "in"
                    i += 1
                arr.append(state)
            vis[n.id] = arr
        evis = {}
        for e in self.edges:
            ev = sorted(e.events, key=lambda x: x[0])
            # arrows of a hidden/removed node disappear with it
            for end in (e.a, e.b):
                for k, kind in end.events:
                    if kind in ("out", "remove"):
                        mine = [x for x in ev if x[0] <= k]
                        drawn_then = (not mine and (not ev or ev[0][1] != "draw")) or (mine and mine[-1][1] == "draw")
                        if drawn_then and not any(x[0] == k for x in ev):
                            if kind == "remove":
                                ev.append((k, "remove"))
                                self.steps[k].remove_edges.append(e.id)
                            else:
                                ev.append((k, "undraw"))
                                self.steps[k]._action(e._tween(False), 300, "with")
                            ev.sort(key=lambda x: x[0])
            e.events = ev
            state = not ev or ev[0][1] != "draw"
            e.first_draw = ev[0][0] if ev and ev[0][1] == "draw" else None
            arr, i = [], 0
            for k in range(n_steps):
                while i < len(ev) and ev[i][0] == k:
                    kind = ev[i][1]
                    if kind == "draw" and state and not (k == 0 and i == 0):
                        raise OpenCanvizError("%s is already drawn when step %d draws it." % (e.id, k))
                    state = kind == "draw"
                    i += 1
                arr.append(state)
            for k in range(n_steps):
                if not arr[k]:
                    continue
                for end in (e.a, e.b):
                    if not vis[end.id][k]:
                        later = [j for j in range(k, n_steps) if vis[end.id][j]]
                        if e.first_draw is None:
                            fix = ("call .draw(arrow) on the step where %s appears (step %d) or later"
                                   % (end.id, later[0]) if later else "reveal %s, then draw the arrow" % end.id)
                            raise OpenCanvizError("arrow %s is visible from step 0, but its end %s is hidden at step %d. "
                                                  "Arrows never drawn are shown from the start; %s." % (e.id, end.id, k, fix))
                        fix = ("draw it in step %d or later" % later[0]) if later else ("reveal %s first" % end.id)
                        raise OpenCanvizError("arrow %s is visible at step %d but its end %s is hidden then; %s."
                                              % (e.id, k, end.id, fix))
            evis[e.id] = arr
        return vis, evis

    def _compile(self):
        if not self.steps:
            raise OpenCanvizError("scene %d (%s) has no steps; add at least one with scene.step(caption)."
                                  % (self.index + 1, self.name))
        vis, evis = self._timelines()
        snap_nodes = []
        for n in self.nodes:
            f = {k: v for k, v in n.fields.items() if not k.startswith("_")}
            shown = f.pop("opacity", 1)
            f["opacity"] = shown if n.initial_visible else 0
            if n.fields.get("_type_step", -1) > 0:
                f["typeProgress"] = 0
            elif n.fields.get("_type_step") == 0:
                f["typeProgress"] = 1
            snap_nodes.append(f)
        shown_opacity = {n.id: n.fields.get("opacity", 1) for n in self.nodes}
        snap_edges = []
        for e in self.edges:
            f = dict(e.fields)
            later = e.first_draw is not None and e.first_draw > 0
            f["trim"] = 0 if later else 1
            if e.labeled:
                f["opacity"] = 0 if later else f.get("opacity", 1)
            snap_edges.append(f)
        steps, narration = [], []
        for st in self.steps:
            k = st.index
            npatch = {nid: dict(p) for nid, p in st.node_patch.items()}
            epatch = {eid: dict(p) for eid, p in st.edge_patch.items()}
            if k > 0:
                for n in self.nodes:
                    if vis[n.id][k] != vis[n.id][k - 1] and n.id not in st.remove_nodes:
                        npatch.setdefault(n.id, {})["opacity"] = shown_opacity[n.id] if vis[n.id][k] else 0
                for e in self.edges:
                    if evis[e.id][k] != evis[e.id][k - 1] and e.id not in st.remove_edges:
                        epatch.setdefault(e.id, {})["trim"] = 1 if evis[e.id][k] else 0
                        if e.labeled:
                            epatch[e.id]["opacity"] = e.fields.get("opacity", 1) if evis[e.id][k] else 0
            dur = st.duration
            words = len(str(st.narration or st.caption).split())
            need = st._cursor
            if dur is None:
                dur = int(math.ceil(max(2000, need + 600, words * 380 + 600) / 100.0) * 100)
            elif dur < need:
                raise OpenCanvizError("scene %d step %d: duration=%d but its actions run to %d ms. Raise duration or "
                                      "shorten the actions." % (self.index + 1, k, dur, need))
            if dur <= 0:
                raise OpenCanvizError("scene %d step %d: duration must be > 0." % (self.index + 1, k))
            sd = {"id": "%sstep%d" % (self.prefix, k)}
            if k > 0:
                sd["delta"] = True
            sd["durationMs"] = dur
            sd["caption"] = st.caption
            if st.easing:
                sd["easing"] = st.easing
            if k == 0:
                for nf in snap_nodes:
                    nf.update(npatch.get(nf["id"], {}))
                for ef in snap_edges:
                    ef.update(epatch.get(ef["id"], {}))
                sd["nodes"] = [dict(x) for x in snap_nodes]
                sd["edges"] = [dict(x) for x in snap_edges]
            else:
                sd["nodes"] = [dict({"id": nid}, **p) for nid, p in npatch.items()]
                sd["edges"] = [dict({"id": eid}, **p) for eid, p in epatch.items()]
            if st.remove_nodes:
                sd["removeNodeIds"] = list(dict.fromkeys(st.remove_nodes))
            if st.remove_edges:
                sd["removeEdgeIds"] = list(dict.fromkeys(st.remove_edges))
            if st.actions:
                sd["actions"] = st.actions
            if st.camera_spec:
                sd.update(st.camera_spec)
            steps.append(sd)
            if st.narration:
                v = self.project.voice
                narration.append({"id": "%sn%d" % (self.prefix, k), "text": str(st.narration), "stepIndex": k,
                                  "voice": {"provider": "openai", "voiceId": v, "voiceName": v.capitalize()}})
        scene = {"nodes": [dict(x) for x in steps[0]["nodes"]], "edges": [dict(x) for x in steps[0]["edges"]],
                 "steps": steps}
        if narration:
            scene["narration"] = narration
        if self.background:
            scene["background"] = self.background
        return scene


class Project:
    """An openCanviz project. aspect: "16:9" (1920x1080), "9:16" (1080x1920) or "1:1" (1080x1080)."""

    def __init__(self, title, aspect="16:9", background=None, theme="dark", voice="alloy", captions=True,
                 caption_style=None, margin=60):
        if aspect not in ASPECTS:
            raise OpenCanvizError("aspect must be one of %s" % sorted(ASPECTS))
        if theme not in THEMES:
            raise OpenCanvizError("theme must be one of %s" % sorted(THEMES))
        if voice not in VOICES:
            raise OpenCanvizError("voice must be one of %s" % sorted(VOICES))
        self.title, self.aspect, self.voice, self.captions = title, aspect, voice, captions
        self.caption_style, self.margin = caption_style, margin
        self.width, self.height = ASPECTS[aspect]
        self.colors = dict(THEMES[theme])
        if background:
            self.colors["background"] = background
        self.base_font = 40 if aspect == "16:9" else 48
        self.edge_label_font = 24 if aspect != "9:16" else 30
        self.scenes = []

    @property
    def artboard(self):
        return {"x": -self.width // 2, "y": -self.height // 2, "width": self.width, "height": self.height,
                "background": self.colors["background"]}

    def area(self, margin=None, caption_space=None):
        """The safe layout area: the artboard minus the margin, and minus the caption band at the bottom
        (20% of the height in landscape, 30% in portrait, where captions wrap to 3-4 lines)."""
        m = self.margin if margin is None else margin
        if m < 60:
            raise OpenCanvizError("area(): keep a margin of at least 60 px.")
        if caption_space is None:
            cap = caption_band(self.width, self.height) * self.height if self.captions else m
        else:
            cap = max(caption_space, m)
        return Rect(-self.width / 2 + m, -self.height / 2 + m, self.width - 2 * m, self.height - m - cap,
                    self.edge_label_font)

    def scene(self, name=None, transition="crossfade", transition_ms=600, background=None):
        """Add a scene. transition joins the previous scene to this one (None = hard cut)."""
        if transition is not None and transition not in TRANSITION_KINDS:
            raise OpenCanvizError("transition must be None or one of %s" % sorted(TRANSITION_KINDS))
        if transition is not None and not transition_ms > 0:
            raise OpenCanvizError("transition_ms must be > 0.")
        s = Scene(self, len(self.scenes), name or "Scene %d" % (len(self.scenes) + 1),
                  (transition, transition_ms), background)
        self.scenes.append(s)
        return s

    def to_dict(self, flat=False):
        """Build the JSON document (no validation). flat=True uses the single-scene form for one scene."""
        if not self.scenes:
            raise OpenCanvizError("add at least one scene with project.scene().")
        scenes = [s._compile() for s in self.scenes]
        doc = {"$schema": SCHEMA_URL, "title": self.title, "artboard": self.artboard}
        if flat:
            if len(scenes) != 1:
                raise OpenCanvizError("flat=True needs exactly one scene.")
            doc.update(scenes[0])
        else:
            doc["sceneNames"] = [s.name for s in self.scenes]
            if len(scenes) > 1:
                doc["transitions"] = [None if s.transition[0] is None else
                                      {"kind": s.transition[0], "durationMs": s.transition[1]}
                                      for s in self.scenes[1:]]
            doc["diagrams"] = scenes
        doc["showCaptions"] = bool(self.captions)
        if self.caption_style:
            doc["captionStyle"] = self.caption_style
        return doc

    def save(self, path, strict=True, flat=False):
        """Validate and write the file. strict=True also refuses layout warnings (overlap, overflow, empty step)."""
        doc = self.to_dict(flat=flat)
        errors, warnings = validate(doc)
        errors += schema_errors(doc) or []
        problems = errors + (warnings if strict else [])
        if problems:
            raise OpenCanvizError("%d problem(s), nothing written:\n  - %s" % (len(problems), "\n  - ".join(problems)))
        for w in warnings:
            sys.stderr.write("warning: %s\n" % w)
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2, allow_nan=False)
            fh.write("\n")
        return doc


# ----------------------------------------------------------------------------------------- validator

def schema_errors(doc):
    """Errors from jsonschema against the bundled schema.json, or None if jsonschema is not installed."""
    try:
        import jsonschema
    except ImportError:
        return None
    with open(SCHEMA_PATH) as fh:
        schema = json.load(fh)
    v = jsonschema.Draft202012Validator(schema)
    out = []
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "(root)"
        out.append("schema: %s: %s" % (loc, err.message[:300]))
    return out


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk_fields(obj, where, errors):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in INTERNAL_FIELDS:
                errors.append("%s: remove '%s'; openCanviz sets it." % (where, k))
            if k == "fillOpacity":
                errors.append("%s: fillOpacity does nothing; dim with opacity or a darker hex." % where)
            if _num(v) and (math.isnan(v) or math.isinf(v)):
                errors.append("%s.%s is %r; use a real number." % (where, k, v))
            _walk_fields(v, "%s.%s" % (where, k), errors)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_fields(v, "%s[%d]" % (where, i), errors)


def validate(doc):
    """Check a document against the SKILL.md rules. Returns (errors, warnings), each a list of strings."""
    errors, warnings = [], []
    E, W = errors.append, warnings.append
    if not isinstance(doc, dict):
        return ["the document must be a JSON object"], []
    _walk_fields(doc, "doc", errors)
    ab = doc.get("artboard")
    if not isinstance(ab, dict) or not all(k in ab for k in ("x", "y", "width", "height", "background")):
        E("artboard: include x, y, width, height and background, centered on the origin "
          "(16:9 = {\"x\":-960,\"y\":-540,\"width\":1920,\"height\":1080,\"background\":\"#0f172a\"}).")
        ab = None
    elif not (_num(ab["width"]) and _num(ab["height"]) and ab["width"] > 0 and ab["height"] > 0):
        E("artboard: width and height must be numbers > 0.")
        ab = None
    if "title" not in doc:
        W("title: add a project title.")
    if isinstance(doc.get("diagrams"), list):
        scenes = doc["diagrams"]
        if not scenes:
            E("diagrams: add at least one scene.")
        tr = doc.get("transitions")
        if tr is not None:
            if not isinstance(tr, list):
                E("transitions must be a list.")
            elif len(tr) > max(0, len(scenes) - 1):
                E("transitions has %d entries for %d scenes; it needs scenes - 1 (index i joins scene i to i+1)."
                  % (len(tr), len(scenes)))
            elif len(tr) < len(scenes) - 1:
                W("transitions has %d entries for %d scenes; missing ones are hard cuts." % (len(tr), len(scenes)))
            for i, t in enumerate(tr if isinstance(tr, list) else []):
                if t is None:
                    continue
                if not isinstance(t, dict) or t.get("kind") not in TRANSITION_KINDS:
                    E("transitions[%d]: kind must be one of %s, or null for a cut." % (i, sorted(TRANSITION_KINDS)))
                elif not (_num(t.get("durationMs")) and t["durationMs"] > 0):
                    E("transitions[%d]: durationMs must be > 0." % i)
        names = doc.get("sceneNames")
        if names is not None and (not isinstance(names, list) or len(names) != len(scenes)):
            W("sceneNames should have one name per scene.")
    elif isinstance(doc.get("nodes"), list):
        scenes = [doc]
    else:
        return errors + ["the document needs either a 'diagrams' list of scenes or top-level 'nodes', 'edges', 'steps'."], warnings
    all_ids = {}
    for si, sc in enumerate(scenes):
        _validate_scene(sc, si, ab, E, W, all_ids, captions=doc.get("showCaptions", True) is not False)
    dup = sorted(i for i, s in all_ids.items() if len(s) > 1)
    if dup:
        W("ids reused across scenes: %s. Prefix ids per scene (s1_, s2_)." % ", ".join(dup[:8]))
    return errors, warnings


def _side_point(n, side, gap=EDGE_GAP):
    x, y, w, h = n["x"], n["y"], n["w"], n["h"]
    return {"E": (x + w + gap, y + h / 2), "W": (x - gap, y + h / 2),
            "N": (x + w / 2, y - gap), "S": (x + w / 2, y + h + gap)}[side]


def _facing_sides(a, b):
    dx = (b["x"] + b["w"] / 2) - (a["x"] + a["w"] / 2)
    dy = (b["y"] + b["h"] / 2) - (a["y"] + a["h"] / 2)
    if abs(dx) >= abs(dy):
        return ("E", "W") if dx >= 0 else ("W", "E")
    return ("S", "N") if dy >= 0 else ("N", "S")


def edge_path(e, a, b):
    """Approximate polyline of an edge between nodes a and b, following openCanviz routing
    (default lineType is elbowed; curved bulges 25% of the length to the left of travel)."""
    auto = _facing_sides(a, b)
    fp, tp = e.get("fromPort") or auto[0], e.get("toPort") or auto[1]
    pa, pb = _side_point(a, fp), _side_point(b, tp)
    lt = e.get("lineType", "elbowed")
    if e.get("waypoints"):
        return [pa] + [(p["x"], p["y"]) for p in e["waypoints"] if isinstance(p, dict)] + [pb]
    if lt == "straight":
        return [pa, pb]
    if lt == "curved":
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        dist = math.hypot(dx, dy) or 1
        c = ((pa[0] + pb[0]) / 2 - dy / dist * dist * 0.25, (pa[1] + pb[1]) / 2 + dx / dist * dist * 0.25)
        pts = []
        for i in range(17):
            t = i / 16.0
            pts.append(((1 - t) ** 2 * pa[0] + 2 * (1 - t) * t * c[0] + t * t * pb[0],
                        (1 - t) ** 2 * pa[1] + 2 * (1 - t) * t * c[1] + t * t * pb[1]))
        return pts
    horiz = set("EW")
    if fp in horiz and tp in horiz:
        if fp == tp:
            lane = (max(pa[0], pb[0]) + 24) if fp == "E" else (min(pa[0], pb[0]) - 24)
            return [pa, (lane, pa[1]), (lane, pb[1]), pb]
        mx = (pa[0] + pb[0]) / 2
        return [pa, (mx, pa[1]), (mx, pb[1]), pb]
    if fp not in horiz and tp not in horiz:
        if fp == tp:
            lane = (max(pa[1], pb[1]) + 24) if fp == "S" else (min(pa[1], pb[1]) - 24)
            return [pa, (pa[0], lane), (pb[0], lane), pb]
        my = (pa[1] + pb[1]) / 2
        return [pa, (pa[0], my), (pb[0], my), pb]
    if fp in horiz:
        return [pa, (pb[0], pa[1]), pb]
    return [pa, (pa[0], pb[1]), pb]


def _seg_hits_box(p, q, n, inset=4):
    """Liang-Barsky: does segment p-q pass through node n's box (shrunk by inset)?"""
    x0, y0 = n["x"] + inset, n["y"] + inset
    x1, y1 = n["x"] + n["w"] - inset, n["y"] + n["h"] - inset
    if x1 <= x0 or y1 <= y0:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            r = qq / float(pp)
            if pp < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return False
    return True


def path_hits(points, n):
    return any(_seg_hits_box(points[i], points[i + 1], n) for i in range(len(points) - 1))


def link_gap_problem(e, a, b):
    """None if the space between connected nodes a and b fits the arrow and its label, else a reason."""
    fp, tp = e.get("fromPort"), e.get("toPort")
    sides = (fp, tp) if fp and tp else _facing_sides(a, b)
    label, fs = e.get("label"), e.get("labelFontSize", 12)
    if sides in (("E", "W"), ("W", "E")):
        left, right = (a, b) if sides[0] == "E" else (b, a)
        gap = right["x"] - (left["x"] + left["w"])
        need = link_gap(label, fs)
        if gap < need - 1:
            return "the horizontal gap is %d px but the arrow%s needs %d" % (gap, " and its label" if label else "", need)
    elif sides in (("S", "N"), ("N", "S")):
        top, bot = (a, b) if sides[0] == "S" else (b, a)
        gap = bot["y"] - (top["y"] + top["h"])
        need = link_gap(label, fs, vertical=True)
        if gap < need - 1:
            return "the vertical gap is %d px but the arrow%s needs %d" % (gap, " and its label" if label else "", need)
    return None


def _overlap(a, b):
    ix = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    iy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return ix > 2 and iy > 2


def _contains(a, b):
    return (a["x"] <= b["x"] + 1 and a["y"] <= b["y"] + 1 and a["x"] + a["w"] >= b["x"] + b["w"] - 1
            and a["y"] + a["h"] >= b["y"] + b["h"] - 1)


def _validate_scene(sc, si, ab, E, W, all_ids, captions=True):
    S = "scene %d" % (si + 1)
    if not isinstance(sc, dict):
        E("%s: must be an object." % S)
        return
    for key in ("nodes", "edges", "steps"):
        if not isinstance(sc.get(key), list):
            E("%s: '%s' must be a list%s." % (S, key, " with at least one step" if key == "steps" else ""))
    steps = sc.get("steps") if isinstance(sc.get("steps"), list) else []
    if not steps:
        E("%s: add at least one step; a scene with no steps renders nothing." % S)
        return
    s0 = steps[0]
    if not isinstance(s0, dict):
        E("%s step 0: must be an object." % S)
        return
    if s0.get("delta"):
        E("%s step 0: must be a full snapshot, not delta." % S)
    canon = lambda v: json.dumps(v, sort_keys=True)
    if isinstance(sc.get("nodes"), list) and isinstance(s0.get("nodes"), list) and \
            canon(sorted(sc["nodes"], key=lambda n: str(n.get("id")))) != canon(sorted(s0["nodes"], key=lambda n: str(n.get("id")))):
        E("%s: the scene's nodes must equal step 0's nodes (copy step 0's list)." % S)
    if isinstance(sc.get("edges"), list) and isinstance(s0.get("edges"), list) and \
            canon(sorted(sc["edges"], key=lambda n: str(n.get("id")))) != canon(sorted(s0["edges"], key=lambda n: str(n.get("id")))):
        E("%s: the scene's edges must equal step 0's edges (copy step 0's list)." % S)

    nodes, edges = {}, {}
    seen_ids = set()

    def add_node(n, where):
        if not isinstance(n, dict):
            E("%s: node entries must be objects." % where)
            return
        miss = [k for k in ("id", "kind", "x", "y", "w", "h") if k not in n]
        if miss:
            E("%s: node %s is missing %s." % (where, n.get("id", "?"), ", ".join(miss)))
            return
        if n["kind"] not in NODE_KINDS:
            E("%s: node %s kind '%s' is not in the schema." % (where, n["id"], n["kind"]))
        if n["id"] in seen_ids:
            E("%s: id %s is used twice; ids must be unique within a scene." % (where, n["id"]))
        seen_ids.add(n["id"])
        all_ids.setdefault(n["id"], set()).add(si)
        nodes[n["id"]] = dict(n)

    def add_edge(e, where):
        if not isinstance(e, dict) or "id" not in e:
            E("%s: every edge needs an id." % where)
            return
        if "strokeWidth" in e:
            E("%s: edge %s uses strokeWidth; edges take width." % (where, e["id"]))
        if e["id"] in seen_ids:
            E("%s: id %s is used twice; ids must be unique within a scene." % (where, e["id"]))
        seen_ids.add(e["id"])
        for end in ("from", "to"):
            if end in e and e[end] not in nodes:
                E("%s: edge %s %s=%s is not a node in the scene; it would be deleted on open. Add the node to step 0 "
                  "(opacity 0) or put the edge in addEdges of a later step." % (where, e["id"], end, e[end]))
        if not (("from" in e or "fromXY" in e) and ("to" in e or "toXY" in e)):
            E("%s: edge %s needs from and to." % (where, e["id"]))
        edges[e["id"]] = dict(e)

    for n in s0.get("nodes") or []:
        add_node(n, "%s step 0" % S)
    for e in s0.get("edges") or []:
        add_edge(e, "%s step 0" % S)

    narr = sc.get("narration")
    narr_steps = set()
    if isinstance(narr, list):
        for c in narr:
            if not isinstance(c, dict):
                continue
            k = c.get("stepIndex")
            if not isinstance(k, int) or k < 0 or k >= len(steps):
                E("%s narration %s: stepIndex %r is not a step (0..%d)." % (S, c.get("id"), k, len(steps) - 1))
            elif k in narr_steps:
                E("%s narration: two clips for step %d; use one clip per step." % (S, k))
            narr_steps.add(k)
            if not str(c.get("text", "")).strip():
                E("%s narration %s: text is empty." % (S, c.get("id")))
            v = c.get("voice")
            if not isinstance(v, dict) or not all(x in v for x in ("provider", "voiceId", "voiceName")):
                E("%s narration %s: voice needs provider, voiceId, voiceName (e.g. openai/alloy/Alloy)." % (S, c.get("id")))
    if not narr:
        W("%s: no narration; add one clip per step (text = caption) so it can be voiced." % S)
    else:
        missing = [k for k in range(len(steps)) if k not in narr_steps]
        if missing:
            E("%s: steps %s have no narration clip; add one clip per step." % (S, missing))

    prev_vis_nodes = None
    prev_edge_trim = {}
    any_caption = any(isinstance(st, dict) and str(st.get("caption", "")).strip() for st in steps)
    seen_msgs = set()

    def once(key):
        if key in seen_msgs:
            return False
        seen_msgs.add(key)
        return True
    for k, st in enumerate(steps):
        P = "%s step %d" % (S, k)
        if not isinstance(st, dict):
            E("%s: must be an object." % P)
            continue
        dur = st.get("durationMs")
        if not (_num(dur) and dur > 0):
            E("%s: durationMs must be a number > 0." % P)
            dur = 900
        if not isinstance(st.get("nodes"), list) or not isinstance(st.get("edges"), list):
            E("%s: include 'nodes' and 'edges' lists (empty lists are fine in delta steps)." % P)
        if not str(st.get("caption", "")).strip():
            W("%s: no caption." % P)
        before_n = {i: dict(n) for i, n in nodes.items()}
        before_e = {i: dict(e) for i, e in edges.items()}
        changed = False
        if k > 0:
            if not st.get("delta"):
                E("%s: add \"delta\": true and list only id plus changed fields (or it replaces the whole scene)." % P)
            for nid in st.get("removeNodeIds") or []:
                if nid not in nodes:
                    E("%s: removeNodeIds has unknown id %s." % (P, nid))
                nodes.pop(nid, None)
                changed = True
            for eid in st.get("removeEdgeIds") or []:
                if eid not in edges:
                    E("%s: removeEdgeIds has unknown id %s." % (P, eid))
                edges.pop(eid, None)
                changed = True
            for n in st.get("addNodes") or []:
                add_node(n, P)
                changed = True
            for e in st.get("addEdges") or []:
                add_edge(e, P)
                changed = True
            for p in st.get("nodes") or []:
                if not isinstance(p, dict) or "id" not in p:
                    E("%s: node changes need an id." % P)
                    continue
                if p["id"] not in nodes:
                    E("%s: node change for unknown id %s." % (P, p["id"]))
                    continue
                if st.get("delta") and len(p) > 8 and all(x in p for x in ("kind", "x", "y", "w", "h")):
                    W("%s: node %s is relisted in full; a delta lists only id plus changed fields." % (P, p["id"]))
                nodes[p["id"]].update(p)
                changed = changed or len(p) > 1
            for p in st.get("edges") or []:
                if not isinstance(p, dict) or "id" not in p:
                    E("%s: edge changes need an id." % P)
                    continue
                if "strokeWidth" in p:
                    E("%s: edge %s uses strokeWidth; edges take width." % (P, p["id"]))
                if p["id"] not in edges:
                    E("%s: edge change for unknown id %s." % (P, p["id"]))
                    continue
                edges[p["id"]].update(p)
                changed = changed or len(p) > 1
            if not changed and not st.get("actions") and not st.get("camera"):
                W("%s: nothing changes on screen; reveal, draw, move or highlight something, or merge the caption "
                  "into the previous step." % P)
        # actions
        acts = st.get("actions") or []
        for a in acts:
            if not isinstance(a, dict):
                E("%s: actions must be objects." % P)
                continue
            t = a.get("type")
            tgt = a.get("target") or {}
            tid = tgt.get("id")
            off, ad = a.get("offsetMs", 0) or 0, a.get("durationMs", 200 if t == "visibility" else 0) or 0
            if _num(off) and _num(ad) and off + ad > dur + 1:
                E("%s: %s on %s ends at %d ms but the step lasts %d ms; raise durationMs or shorten the action."
                  % (P, t, tid, off + ad, dur))
            if t == "visibility":
                if tid not in nodes:
                    E("%s: visibility action targets unknown node %s." % (P, tid))
                    continue
                op = nodes[tid].get("opacity", 1)
                if a.get("mode") in VIS_IN and op <= 0.01:
                    E("%s: %s fades in %s but its opacity stays 0 in this step, so it fades back out next step. Set "
                      "\"opacity\": 1 for it in this step's nodes." % (P, a.get("mode"), tid))
                if a.get("mode") in VIS_OUT and op > 0.01 and tid not in (st.get("removeNodeIds") or []):
                    E("%s: %s hides %s but its opacity is still %g; set \"opacity\": 0 in this step's nodes."
                      % (P, a.get("mode"), tid, op))
            elif t == "transformTween":
                if tid not in nodes:
                    E("%s: transformTween targets unknown node %s." % (P, tid))
                    continue
                fr, to = a.get("from") or {}, a.get("to") or {}
                if "x" in fr or "y" in fr:
                    E("%s: transformTween on %s has from.x/from.y, which are ignored; put the start position in the "
                      "previous step." % (P, tid))
                if a.get("isRelative") or "dx" in a or "dy" in a:
                    E("%s: transformTween on %s uses isRelative/dx/dy; use an absolute to.x/to.y." % (P, tid))
                if to.get("opacity") == 0:
                    E("%s: do not hide %s with an opacity transformTween; use a visibility fadeOut and opacity 0."
                      % (P, tid))
                for key, val in to.items():
                    if key not in TWEEN_PROPS:
                        E("%s: transformTween to.%s is not a tween property." % (P, key))
                    cur = nodes[tid].get(key, 1 if key in ("opacity", "typeProgress", "scaleX", "scaleY") else None)
                    if cur is not None and _num(val) and _num(cur) and abs(cur - val) > 0.01:
                        E("%s: transformTween on %s ends at %s=%g but the step sets %g; make the step's value match "
                          "to.%s." % (P, tid, key, val, cur, key))
            elif t == "edgeTween":
                if tid not in edges:
                    E("%s: edgeTween targets unknown edge %s." % (P, tid))
                    continue
                to = a.get("to") or {}
                cur = edges[tid].get("trim", 1)
                if "trim" in to and abs(to["trim"] - cur) > 0.01:
                    E("%s: edgeTween on %s ends at trim %g but the step leaves it at %g; set \"trim\": %g for it in "
                      "this step's edges." % (P, tid, to["trim"], cur, to["trim"]))
            elif t == "pathFollow":
                if a.get("pathId") not in (sc.get("paths") or {}):
                    E("%s: pathFollow uses unknown path %s." % (P, a.get("pathId")))
            elif t not in ("positionTween", "pathAnimate", "algoSwap", "containerTransform", "voiceOver"):
                E("%s: unknown action type %r." % (P, t))
            if t in ("visibility", "transformTween", "positionTween", "pathFollow") and tgt.get("kind") != "node":
                E("%s: %s target must be {\"kind\":\"node\",\"id\":...}." % (P, t))
            if t == "edgeTween" and tgt.get("kind") != "edge":
                E("%s: edgeTween target must be {\"kind\":\"edge\",\"id\":...}." % P)
            ease = a.get("ease")
            if ease is not None and ease not in EASINGS:
                E("%s: ease %r is not one of %s." % (P, ease, sorted(EASINGS)))
        tweened_edges = {(a.get("target") or {}).get("id") for a in acts if isinstance(a, dict) and a.get("type") == "edgeTween"}
        visual_in = {(a.get("target") or {}).get("id") for a in acts if isinstance(a, dict) and a.get("type") == "visibility"}
        cam = st.get("camera")
        if cam is not None and not (isinstance(cam, dict) and _num(cam.get("zoom")) and cam["zoom"] > 0
                                     and _num(cam.get("x")) and _num(cam.get("y"))):
            E("%s: camera needs x, y and zoom > 0." % P)
        if _num(st.get("cameraDurationMs")) and st["cameraDurationMs"] + (st.get("cameraOffsetMs") or 0) > dur + 1:
            E("%s: the camera move ends after the step; raise durationMs." % P)

        # state checks at the end of the step
        vis_nodes = {i for i, n in nodes.items() if (n.get("opacity", 1) or 0) > 0.01}
        for nid in vis_nodes:
            if k > 0 and before_n.get(nid, {}).get("opacity", 1) <= 0.01 and nid not in visual_in and \
                    nid not in {n.get("id") for n in st.get("addNodes") or []}:
                W("%s: %s goes from opacity 0 to visible without a fadeIn/slideIn action." % (P, nid))
        for eid, e in edges.items():
            trim = e.get("trim", 1)
            was = prev_edge_trim.get(eid, None)
            if k > 0 and was is not None and was <= 0.01 and trim > 0.01 and eid not in tweened_edges:
                E("%s: edge %s draws in without an edgeTween; add {\"type\":\"edgeTween\",\"target\":{\"kind\":\"edge\","
                  "\"id\":\"%s\"},\"from\":{\"trim\":0},\"to\":{\"trim\":1},\"durationMs\":700}." % (P, eid, eid))
            if trim > 0.01 and (e.get("opacity", 1) or 0) > 0.01:
                for end in ("from", "to"):
                    nid = e.get(end)
                    if nid and nid in nodes and nid not in vis_nodes:
                        E("%s: arrow %s is drawn but its end %s is hidden (opacity 0) at the end of the step, so it "
                          "points at empty space. Start it at trim 0 and draw it in the step that reveals %s, or later."
                          % (P, eid, nid, nid))
        # inside the step: an arrow must not start drawing before the node it joins has started to appear
        starts = {}
        for a in acts:
            if isinstance(a, dict) and a.get("type") == "visibility" and a.get("mode") in VIS_IN:
                nid = (a.get("target") or {}).get("id")
                starts[nid] = min(starts.get(nid, 1e18), a.get("offsetMs") or 0)
        for a in acts:
            if not (isinstance(a, dict) and a.get("type") == "edgeTween"):
                continue
            fr, to = a.get("from") or {}, a.get("to") or {}
            if not (_num(fr.get("trim")) and _num(to.get("trim")) and to["trim"] > fr["trim"]):
                continue
            e = edges.get((a.get("target") or {}).get("id")) or {}
            for end in (e.get("from"), e.get("to")):
                if end in starts and (a.get("offsetMs") or 0) < starts[end]:
                    E("%s: arrow %s starts drawing at %d ms but its end %s only starts to appear at %d ms, so it "
                      "draws toward empty space. Reveal %s first (or at the same offset), then draw the arrow."
                      % (P, e.get("id"), a.get("offsetMs") or 0, end, starts[end], end))
        for nid, n in nodes.items():
            if not all(_num(n.get(x)) for x in ("x", "y", "w", "h")):
                E("%s: node %s needs numeric x, y, w, h." % (P, nid))
                continue
            if n.get("kind") == "algo-pointer":
                continue
            if n["w"] < 2 or n["h"] < 2 or (n["w"] < 10 and n["h"] < 10) or n["w"] < 10 or n["h"] < 10:
                E("%s: node %s is %gx%g; nodes under 10x10 px are not drawn. Make it bigger or draw a line as an edge."
                  % (P, nid, n["w"], n["h"]))
            if nid not in vis_nodes:
                continue
            if ab and (n["x"] < ab["x"] - 1 or n["y"] < ab["y"] - 1 or n["x"] + n["w"] > ab["x"] + ab["width"] + 1
                       or n["y"] + n["h"] > ab["y"] + ab["height"] + 1):
                E("%s: node %s (x=%g y=%g w=%g h=%g) sticks out of the artboard (%g,%g %gx%g); move it inside."
                  % (P, nid, n["x"], n["y"], n["w"], n["h"], ab["x"], ab["y"], ab["width"], ab["height"]))
            why = text_overflow(n)
            if why:
                W("%s: text in %s will likely overflow: %s. Enlarge the box, lower the font size or shorten it."
                  % (P, nid, why))
            for key in ("fill", "stroke", "color", "labelColor", "progressColor"):
                if key in n and (not isinstance(n[key], str) or not COLOR_RE.match(n[key].strip())):
                    W("%s: %s.%s=%r is not a hex color." % (P, nid, key, n[key]))
        vis = [nodes[i] for i in sorted(vis_nodes) if nodes[i].get("kind") != "group" and not nodes[i].get("parentId")
               and all(_num(nodes[i].get(x)) for x in ("x", "y", "w", "h"))]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                inside = _contains(a, b) or _contains(b, a)
                if inside and _overlap(a, b) and min(a["w"] * a["h"], b["w"] * b["h"]) > 0.8 * max(
                        a["w"] * a["h"], b["w"] * b["h"]) and once(("same", a["id"], b["id"])):
                    E("%s: %s and %s sit on the same spot (x=%g y=%g), so one hides the other; give them "
                      "different rects (note cut_bottom returns (rest, band): the band is [1])."
                      % (P, a["id"], b["id"], b["x"], b["y"]))
                elif _overlap(a, b) and not inside and once(("ov", a["id"], b["id"])):
                    W("%s: %s and %s overlap; move them apart or put one fully inside the other."
                      % (P, a["id"], b["id"]))
        _layout_checks(P, ab, captions, nodes, edges, vis, any_caption, W, once)
        if k == len(steps) - 1 and ab:
            _fill_check(P, ab, captions, vis, W)
        prev_edge_trim = {i: e.get("trim", 1) for i, e in edges.items()}
        prev_vis_nodes = vis_nodes


def _layout_checks(P, ab, captions, nodes, edges, vis, any_caption, W, once):
    """Readability checks at the end of a step: caption band, edge labels, gaps, crossings."""
    vis_ids = {n["id"] for n in vis}
    if ab and captions and any_caption:
        band = caption_band(ab["width"], ab["height"])
        limit = ab["y"] + ab["height"] * (1 - band)
        for n in vis:
            if n["y"] + n["h"] > limit + 1 and once(("cap", n["id"])):
                W("%s: %s reaches y=%d, inside the caption band (bottom %d%% of the frame, below y=%d), where captions "
                  "will cover it. Move it up or shrink it." % (P, n["id"], n["y"] + n["h"], band * 100, limit))
    lmin = edge_label_min(ab["width"], ab["height"]) if ab else 22
    for eid, e in edges.items():
        a, b = nodes.get(e.get("from")), nodes.get(e.get("to"))
        trim, op = e.get("trim", 1), e.get("opacity", 1)
        if e.get("label") and trim <= 0.01 and op > 0.01 and once(("lbl0", eid)):
            W("%s: edge %s has a label and trim 0 but opacity %g; its label shows at the start port before the line "
              "draws. Give it \"opacity\": 0 until its draw step, then opacity 1 with trim 1." % (P, eid, op))
        if e.get("label") and e.get("labelFontSize", 12) < lmin and once(("lfs", eid)):
            W("%s: edge %s label font is %g px; set labelFontSize to at least %d so it reads at 1080p."
              % (P, eid, e.get("labelFontSize", 12), lmin))
        if trim <= 0.01 or op <= 0.01 or not a or not b or e.get("from") not in vis_ids or e.get("to") not in vis_ids:
            continue
        if not all(_num(x.get(k)) for x in (a, b) for k in ("x", "y", "w", "h")):
            continue
        why = link_gap_problem(e, a, b)
        if why and once(("gap", eid)):
            W("%s: edge %s: %s. Move %s and %s apart (row/column/stack/flow size the gaps when you "
              "pass labels=[...]), or shorten the label." % (P, eid, why, a["id"], b["id"]))
        pts = edge_path(e, a, b)
        for n in vis:
            if n["id"] in (a["id"], b["id"]) or _contains(n, a) or _contains(n, b):
                continue
            if path_hits(pts, n) and once(("x", eid, n["id"])):
                W("%s: edge %s from %s to %s passes over %s. Connect neighbours instead, or send the skip along its "
                  "own lane (fromPort and toPort both \"S\" with lineType \"elbowed\", and nothing in the lane below)."
                  % (P, eid, a["id"], b["id"], n["id"]))


def _fill_check(P, ab, captions, vis, W):
    shapes = [n for n in vis if n.get("kind") not in ("text",)]
    if len(shapes) < 3:
        return
    m = 60
    band = caption_band(ab["width"], ab["height"]) * ab["height"] if captions else m
    safe_w, safe_h = ab["width"] - 2 * m, ab["height"] - m - band
    x0 = min(n["x"] for n in vis)
    y0 = min(n["y"] for n in vis)
    x1 = max(n["x"] + n["w"] for n in vis)
    y1 = max(n["y"] + n["h"] for n in vis)
    fill = (x1 - x0) * (y1 - y0) / float(max(safe_w * safe_h, 1))
    if fill < 0.4:
        W("%s: the diagram fills only %d%% of the safe area (aim for 60-75%%); make the nodes bigger or spread them "
          "over more rows (Rect.flow does this)." % (P, fill * 100))


def _dedupe(msgs):
    out, seen = [], set()
    for m in msgs:
        key = re.sub(r"step \d+", "step N", m)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def check_file(path):
    """Validate a JSON file. Returns (errors, warnings)."""
    def bad_const(c):
        raise ValueError("%s is not valid JSON; use a number" % c)
    try:
        with open(path) as fh:
            doc = json.load(fh, parse_constant=bad_const)
    except (ValueError, OSError) as exc:
        return ["%s: does not parse as plain JSON: %s" % (path, exc)], []
    errors, warnings = validate(doc)
    se = schema_errors(doc)
    if se is None:
        warnings.append("jsonschema is not installed; schema.json was not checked (pip install jsonschema).")
    else:
        errors += se
    return _dedupe(errors), _dedupe(warnings)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] != "check":
        print("usage: python3 opencanviz.py check FILE.json [FILE.json ...]")
        return 2
    bad = 0
    for path in argv[1:]:
        errors, warnings = check_file(path)
        print("%s: %s" % (path, "OK" if not errors else "%d error(s)" % len(errors)))
        for e in errors:
            print("  error: " + e)
        for w in warnings:
            print("  warning: " + w)
        bad += bool(errors)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
