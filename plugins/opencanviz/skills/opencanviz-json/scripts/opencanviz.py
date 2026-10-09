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
A follow camera keeps each step's visible content centered in the safe area (follow=False or any
.camera() turns it off); a labeled edge draws as an unlabeled "<id>_line" copy and its label fades
in once the line is drawn; gaps leave chip + 120 px of visible line; route="around" closes a cycle.

Recipes (scene.* builds, step.* animates): bar_chart/grow, line_chart/extend, scatter/scatter_to,
array/swap/color/bracket, pointer/point, tree, linked_list/append, graph, grid/set_cell,
variable/assign, code/highlight, sequence/message/activate, timeline/event, panels, bullets, counter,
progress, pie/sweep, path/follow, packet. Each writes only fields openCanviz plays and exports.
Recipes keep text at the readable floor (font_floor: body 34, code 30, ticks 28, variables 34 px at
1080p landscape, x1.4 in portrait) and lay out at their final size from step 0; scene.reserve(node)
makes the follow camera frame a node of your own before it appears.

check also reports: a delta step that adds edges but no nodes; an edge without animationStyle; an
edgeTween that trims 0 to 1 without trim 1 in the snapshot; glow 0 (use noGlow); a mono iconify icon
without iconStyle "solid" and fill; a structure node without its font field; sketchMode, kind "icon"
and lottie; typeProgress changed without a 0 to 1 tween; pathFollow on a path without length/cum.
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
    "cellColors", "noGlow", "padding", "syntaxColors", "highlightLineColor", "pointerPosition", "topWidth",
    "bottomWidth", "glyph", "drawStartMs", "drawProgress", "svgPaths", "svgViewBox",
    # charts
    "chartBars", "chartMaxValue", "chartShowValues", "chartBarColor", "barColors", "chartSeries", "chartXRange",
    "chartYRange", "chartXLabel", "chartYLabel", "chartGridLines", "chartPoints", "chartShowAxes", "chartBarSpacing", "cellShowIndices", "nodeSpacing", "levelHeight",
    # algorithm structures and pointers
    "cellFontSize", "cellIndexFontSize", "rangeStart", "rangeEnd", "rangeColor", "rangeLabel", "pointerTargetId",
    "pointerTargetIndex", "pointerLabel", "pointerColor", "pointerSidePosition", "pointerArrowSize",
    "pointerChartBarId", "pointerTreeNodeId", "pointerLinkedListNodeId", "pointerGraphNodeId", "pointerTargetRow",
    "pointerTargetCol", "treeNodes", "nodeRadius", "nodeFontSize", "nodeColors", "edgeColors", "linkedListNodes",
    "linkedListNodeWidth", "linkedListNodeHeight", "graphNodes", "graphEdges", "graphNodeRadius", "graphDirected",
    "gridValues", "gridColors", "gridCellFontSize", "gridIndexFontSize", "varName", "varValue", "varOrientation",
    # UML
    "lifelineLength", "activations", "attributes", "methods", "stereotype",
    # count-up text
    "countFrom", "countTo", "countStartMs", "countDurationMs", "countPrefix", "countSuffix", "countIsInt"}

# Kinds that get no theme fill/stroke from Scene.node(): the recipe methods pass exactly the fields the
# renderer was seen to use.
NO_THEME_KINDS = {"text", "svg", "icon", "progress", "group", "glyph", "algo-pointer", "algo-tree",
                  "algo-linked-list", "algo-graph", "algo-grid", "algo-variable", "algo-chart-line",
                  "algo-chart-scatter", "uml-actor"}
BROKEN_KINDS = {"icon": "kind 'icon' renders as a white box; use kind 'svg' with asset {type: icon, source: "
                        "iconify, ref} (the helper's scene.icon())",
                "lottie": "kind 'lottie' renders nothing in the exported video; use shapes, glyphs or icons"}
# Iconify sets whose icons carry their own colors; every other set is one color (currentColor), which renders
# black unless the node has iconStyle 'solid' and a fill.
MULTICOLOR_ICON_SETS = {"logos", "skill-icons", "devicon", "vscode-icons", "flat-color-icons", "twemoji", "noto",
                        "noto-v1", "fluent-emoji", "fluent-emoji-flat", "fluent-emoji-high-contrast", "emojione",
                        "openmoji", "fxemoji", "streamline-emojis", "circle-flags", "flag", "flagpack", "cif",
                        "token-branded", "material-icon-theme", "catppuccin", "unjs", "devicon-plain"}
# Font fields each kind needs; without them its text renders at 11-14 px.
FONT_FIELDS = {"algo-array": "cellFontSize", "algo-tree": "nodeFontSize", "algo-linked-list": "nodeFontSize",
               "algo-graph": "nodeFontSize", "algo-grid": "gridCellFontSize", "algo-variable": "labelFontSize",
               "algo-pointer": "labelFontSize"}
PALETTE = ["#38bdf8", "#f59e0b", "#22c55e", "#a78bfa", "#f472b6", "#f87171", "#2dd4bf", "#94a3b8"]

EDGE_FIELDS = {
    "id", "from", "to", "fromXY", "toXY", "fromPort", "toPort", "stroke", "width", "opacity", "trim",
    "trimStart", "arrow", "endArrowType", "startArrowType", "arrowSize", "strokeStyle", "lineType", "router",
    "cornerRadius", "label", "labelColor", "labelFontSize", "labelPosition", "labelPositionT",
    "labelBgColor", "animationStyle", "flowSpeed", "waypoints", "zIndex", "labelOffset", "labelOffsetX",
    "labelOffsetY", "labelBgPadding", "labelFontWeight"}

LABEL_KEYS = {"label", "labelColor", "labelFontSize", "labelPosition", "labelPositionT", "labelBgColor",
              "opacity", "labelOffset", "labelOffsetX", "labelOffsetY", "labelBgPadding", "labelFontWeight"}
LABEL_POP = 60         # a labeled arrow's label appears this fast once its line is drawn (an opaque chip)
TWIN_FADE = 300        # ... while the unlabeled line under it fades out over this

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
             "muted": "#94a3b8", "edge": "#94a3b8", "line": "#334155", "panel": "#111827", "accent": "#38bdf8",
             "hi": "#f59e0b", "ok": "#22c55e", "bad": "#ef4444", "code": "#e6edf3"},
    "light": {"background": "#f8fafc", "fill": "#ffffff", "stroke": "#334155", "text": "#0f172a",
              "muted": "#475569", "edge": "#64748b", "line": "#cbd5e1", "panel": "#f1f5f9", "accent": "#2563eb",
              "hi": "#d97706", "ok": "#16a34a", "bad": "#dc2626", "code": "#1f2937"},
}

COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|rgba?\([^)]*\)|transparent|none)$")
CHAR_W = 0.55          # average glyph width as a share of the font size (0.6 for bold and edge labels)
LINE_H = 1.2           # line height used to size text boxes
TEXT_PAD = 8           # breathing room inside a text node, top and bottom
LABEL_PAD = 10         # openCanviz default label padding
EDGE_GAP = 8           # an edge starts this far from its node
MIN_LINK_GAP = 100     # an unlabeled arrow: 84 px of visible line plus the end gaps
LABEL_LINE = 120       # visible line a labeled arrow keeps beside its label chip (60 px each side)
SIDE_MARGIN = 120      # left/right margin of project.area() in landscape (80 in portrait and square)
FOLLOW_MS = 800        # follow-camera pan length
PAN_FIRST_MS = 700     # a step that brings something in pans this long before it arrives


def caption_band(width, height):
    """Share of the frame height, at the bottom, that captions cover (20% landscape, 30% portrait)."""
    return 0.3 if height > width else 0.2


def edge_label_min(width, height):
    """Smallest readable edge-label font: 22 px landscape, 28 px portrait."""
    return 28 if height > width else 22


FONT_FLOORS = {"body": 34, "code": 30, "tick": 28, "var": 34}


def font_floor(kind, width, height):
    """Smallest readable font size for kind (body, code, tick, var) on a width x height artboard: at 1080p
    landscape body / event / bullet text 34 px, code 30, chart ticks and small labels 28, variable boxes 34;
    portrait (9:16) is scaled up by 1.4 because the phone shows the frame smaller."""
    return int(round(FONT_FLOORS[kind] * (1.4 if height > width else 1.0)))


def label_width(label, font_size):
    """Estimated width of an edge label chip."""
    return len(str(label)) * 0.6 * font_size + 24


def label_height(font_size):
    """Estimated height of an edge label chip."""
    return font_size * 1.2 + 10


def link_gap(label=None, font_size=24, vertical=False):
    """Gap two connected nodes need so the viewer sees a real arrow: 100 px unlabeled, else the label
    chip plus 120 px of visible line (along the arrow, so a vertical arrow counts the chip's height)."""
    if not label:
        return MIN_LINK_GAP
    chip = label_height(font_size) if vertical else label_width(label, font_size)
    return max(MIN_LINK_GAP, chip + 2 * EDGE_GAP + LABEL_LINE)


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

    def split(self, frac=0.5, gap=60):
        """Split side by side into (left frac of the width, the rest on the right), gap px apart. A code
        panel and its variables: left, right = body.split(0.68)."""
        lw = (self.w - gap) * frac
        return self._r(self.x, self.y, lw, self.h), self._r(self.x + lw + gap, self.y, self.w - lw - gap, self.h)

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


def font_floor_issue(node, width, height):
    """None if the node's text is at or above the readable floor (see font_floor), else a short reason.
    Code (monospace or syntaxStyle) needs the code floor, a variable box the variable floor, text of 4 or
    more words the body floor, and any other text or label the tick floor."""
    kind = node.get("kind")
    if kind == "algo-variable":
        fs, what = node.get("labelFontSize", 14), "var"
    elif kind == "text" and str(node.get("text", "")).strip():
        fs = node.get("fontSize", 24)
        if node.get("syntaxStyle") or "mono" in str(node.get("fontFamily", "")):
            what = "code"
        else:
            what = "body" if len(str(node["text"]).split()) >= 4 else "tick"
    elif kind == "algo-pointer" and node.get("pointerLabel"):
        fs, what = node.get("labelFontSize", 14), "tick"
    elif node.get("label") and kind not in ("svg", "icon", "lottie", "group"):
        fs = node.get("labelFontSize", 14)
        what = "body" if len(str(node["label"]).split()) >= 4 else "tick"
    else:
        return None
    if not _num(fs):
        return None
    floor = font_floor(what, width, height)
    if fs + 0.5 < floor:
        name = {"var": "variable", "code": "code", "body": "text of 4+ words", "tick": "short text"}[what]
        return "%s at %g px is under the %d px readable floor" % (name, fs, floor)
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
        self.parts = []       # nodes and lines that appear, hide and go with this one (a chart's axes, a bullet's glyph)
        self.meta = {}        # recipe state (current values, colors, ...)

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
        self.parts = []       # nodes revealed once the line is drawn (a sequence message's text)
        self.twin_steps = set()   # steps that draw a labeled edge through its unlabeled twin line
        self._twin = None

    def __repr__(self):
        return "Edge(%s)" % self.id

    @property
    def labeled(self):
        return bool(self.fields.get("label"))

    def _tween(self, drawing):
        """edgeTween for a draw-in (True) or draw-out. It always carries opacity: an edge waits for its
        draw at trim 0 AND opacity 0, because at trim 0 openCanviz still paints the arrowhead (a stub at
        the start port) and a label (floating at the start port)."""
        shown = self.fields.get("opacity", 1)
        fr, to = ({"trim": 0, "opacity": shown}, {"trim": 1, "opacity": shown}) if drawing else \
            ({"trim": 1, "opacity": shown}, {"trim": 0, "opacity": 0})
        return {"type": "edgeTween", "target": {"kind": "edge", "id": self.id}, "from": fr, "to": to}

    @property
    def twin_id(self):
        """Id of the unlabeled line that draws a labeled edge in (the label then fades in on the drawn line)."""
        if self._twin is None:
            self._twin = self.scene._id(self.id + "_line")
        return self._twin

    def twin_fields(self):
        f = {k: v for k, v in self.fields.items() if k not in LABEL_KEYS}
        f["id"] = self.twin_id
        return f


def _tline(fs, lh=LINE_H):
    """Height of a one-line text box at font size fs (what text_overflow wants, plus 2 px)."""
    return int(math.ceil(fs * lh + 2 * TEXT_PAD + 2))


def _hold_first_edge_tweens(sd):
    """Step 0 has no earlier state, so before a delayed edgeTween starts openCanviz shows the edge as
    the snapshot has it (drawn). Hold each edge at its first tween's start values until that tween runs."""
    first = {}
    for a in sd.get("actions") or []:
        if a.get("type") == "edgeTween" and a.get("from"):
            eid = a["target"]["id"]
            if eid not in first or a.get("offsetMs", 0) < first[eid].get("offsetMs", 0):
                first[eid] = a
    holds = [{"type": "edgeTween", "target": {"kind": "edge", "id": eid}, "from": dict(a["from"]),
              "to": dict(a["from"]), "durationMs": a["offsetMs"], "ease": "linear"}
             for eid, a in first.items() if a.get("offsetMs", 0) > 0]
    if holds:
        sd["actions"] = holds + sd["actions"]


def _fmt_num(v, decimals=0, prefix="", suffix=""):
    return "%s%s%s" % (prefix, ("{:,.%df}" % decimals).format(v), suffix)


def _affix(prefix, suffix):
    out = {}
    if prefix:
        out["countPrefix"] = prefix
    if suffix:
        out["countSuffix"] = suffix
    return out


def _nice_ceil(v):
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for k in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if k * e >= v - 1e-9:
            return _clean(k * e)
    return _clean(10 * e)


def _ticks(lo, hi, count=5):
    """About count round tick values from lo to hi."""
    span = float(hi - lo)
    if span <= 0:
        return [lo]
    raw = span / count
    e = 10 ** math.floor(math.log10(raw))
    step = next(k * e for k in (1, 2, 2.5, 5, 10) if k * e >= raw)
    start = math.ceil(lo / step) * step
    out, v = [], start
    while v <= hi + 1e-9:
        out.append(_clean(v) if abs(v) >= 1 or v == 0 else round(v, 6))
        v += step
    return out


def _tick_fmt(v):
    if float(v) == int(v):
        return str(int(v)) if abs(v) < 10000 else "{:,}".format(int(v))   # 1800 reads as a year
    return ("%g" % v)


def _series(m, upto):
    """The line-chart series drawn to point upto, plus copies nudged a couple of px each way: openCanviz
    draws a chart line 2 px wide, the copies make it read as a ~5 px line."""
    pts = m["points"]
    shown = [pts[min(i, upto)] for i in range(len(pts))]
    out = []
    for k, (dx, dy) in enumerate(m.get("offsets") or [(0, 0)]):
        out.append({"id": "s" if k == 0 else "s_w%d" % k, "color": m["color"],
                    "points": [{"x": _r4(x + dx), "y": _r4(y + dy)} for x, y in shown]})
    return out


def _r4(v):
    v = round(float(v), 4)
    return int(v) if v == int(v) else v


def _dots(m):
    return [{"id": "p%d" % i, "x": _clean(x), "y": _clean(y), "color": c, "size": m["size"]}
            for i, ((x, y), c) in enumerate(zip(m["points"], m["colors"]))]


def _list_nodes(vals):
    out = []
    for i, v in enumerate(vals):
        e = {"id": "l%d" % i, "value": v}
        if i + 1 < len(vals):
            e["next"] = "l%d" % (i + 1)
        out.append(e)
    return out


def _pointer_target(target, at):
    kind = target.fields.get("kind")
    m = target.meta.get("struct") or {}
    if kind == "algo-array":
        return {"pointerTargetIndex": int(at)}
    if kind == "algo-grid":
        return {"pointerTargetRow": int(at[0]), "pointerTargetCol": int(at[1])}
    if kind == "algo-chart":
        return {"pointerChartBarId": "b%d" % int(at)}
    field = {"algo-tree": "pointerTreeNodeId", "algo-linked-list": "pointerLinkedListNodeId",
             "algo-graph": "pointerGraphNodeId"}.get(kind)
    if field is None:
        raise OpenCanvizError("pointer(): %s is a %s; point at an array, tree, linked list, graph, grid or bar chart."
                              % (target.id, kind))
    nid = m.get("ids", {}).get(str(at))
    if nid is None:
        raise OpenCanvizError("pointer(): %s has no node %r." % (target.id, at))
    return {field: nid}


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
        self._cursor, self._last_start, self._tail = 0, 0, 0
        self._shift = None          # (from_ms, by_ms) when the follow camera delayed this step's arrivals
        self.timed = []             # (node, field, offset_ms): scene-time markers filled at compile time
        self.hooks = []             # fn(snapshot_by_id, step_start_ms, step_dict, adjust_offset) run at compile time

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
        """Show a hidden node (or a list of nodes, together): fadeIn, show, slideInLeft/Right/Up/Down. Sets
        opacity 1 for you. The node's parts (a chart's axes and labels, a bullet's glyph) come with it; a
        glyph draws itself in and a counter starts counting when it is revealed."""
        if isinstance(node, (list, tuple)):
            for i, n in enumerate(node):
                self.reveal(n, style, duration, offset if i == 0 else "with", ease, distance)
            return self
        self._own(node, Node)
        if style not in VIS_IN:
            raise OpenCanvizError("reveal(%s): style must be one of %s" % (node.id, sorted(VIS_IN)))
        node.events.append((self.index, "in"))
        act = {"type": "visibility", "target": {"kind": "node", "id": node.id}, "mode": style}
        if ease:
            act["ease"] = ease
        if distance is not None:
            act["slideDistance"] = distance
        start = self._action(act, duration, offset).get("offsetMs", 0)
        kind = node.fields.get("kind")
        if kind == "glyph":
            self.timed.append((node, "drawStartMs", start))
        if "countTo" in node.fields and not node.meta.get("count_managed"):
            self.timed.append((node, "countStartMs", start))
        for part in node.parts:
            if isinstance(part, Edge):
                self.draw(part, duration=duration, offset=start)
            else:
                self.reveal(part, style, duration, start, ease, distance)
        self._last_start = start
        return self

    def hide(self, item, style="fadeOut", duration=400, offset=None, ease=None):
        """Hide a node (fadeOut, hide, slideOut*), a list of nodes, or undraw an arrow. Arrows and parts of a
        hidden node go with it."""
        if isinstance(item, (list, tuple)):
            for i, n in enumerate(item):
                self.hide(n, style, duration, offset if i == 0 else "with", ease)
            return self
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
        start = self._action(act, duration, offset).get("offsetMs", 0)
        for part in item.parts:
            if isinstance(part, Node):
                self.hide(part, style, duration, start, ease)
        self._last_start = start
        return self

    def draw(self, edge, duration=700, offset=None, ease="ease-out"):
        """Draw an arrow in (trim 0 -> 1). Both end nodes must be visible by the end of this step.

        A labeled arrow is drawn by an unlabeled twin line (id <edge>_line); once the line is fully
        drawn the labeled edge appears on top of it at once (60 ms, so its opaque chip masks the line
        straight away) and the twin fades out under it (300 ms). openCanviz puts a label at the middle
        of the drawn part, so a label drawn with its line slides along with the tip and shows before the
        arrow does."""
        self._own(edge, Edge)
        edge.events.append((self.index, "draw"))
        if not edge.labeled:
            act = edge._tween(True)
            if ease:
                act["ease"] = ease
            start = self._action(act, duration, offset).get("offsetMs", 0)
            for part in edge.parts:
                self.reveal(part, "fadeIn", 300, start + duration)
            self._last_start = start
            return self
        edge.twin_steps.add(self.index)
        shown = edge.fields.get("opacity", 1)
        line = {"type": "edgeTween", "target": {"kind": "edge", "id": edge.twin_id},
                "from": {"trim": 0, "opacity": shown}, "to": {"trim": 1, "opacity": shown}}
        if ease:
            line["ease"] = ease
        start = self._action(line, duration, offset).get("offsetMs", 0)
        done = start + duration
        self.actions.append({"type": "edgeTween", "target": {"kind": "edge", "id": edge.id},
                             "from": {"trim": 1, "opacity": 0}, "to": {"trim": 1, "opacity": shown},
                             "durationMs": LABEL_POP, "offsetMs": done, "ease": "linear"})
        self.actions.append({"type": "edgeTween", "target": {"kind": "edge", "id": edge.twin_id},
                             "from": {"trim": 1, "opacity": shown}, "to": {"trim": 1, "opacity": 0},
                             "durationMs": TWIN_FADE, "offsetMs": done})
        self._tail = max(self._tail, done + TWIN_FADE)
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
            for part in item.parts:
                if isinstance(part, Node):
                    self.remove(part)
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

    # recipe steps -------------------------------------------------------------------------------
    def _recipe(self, node, key, what):
        self._own(node, Node)
        m = node.meta.get(key)
        if m is None:
            raise OpenCanvizError("%s(%s): this node was not made by scene.%s()." % (what, node.id, key))
        return m

    def _after_first(self, what, node):
        if self.index == 0:
            raise OpenCanvizError("%s(%s) animates from the previous step, and a scene's first step has none. Show %s "
                                  "in step 0 and call %s() in the next step." % (what, node.id, node.id, what))

    def _patch(self, node, **fields):
        self.node_patch.setdefault(node.id, {}).update(fields)

    def _count_over_step(self, text):
        """Fill countStartMs / countDurationMs at compile time so the number counts over the whole step."""
        def hook(snap, t0, sd, adj, n=text):
            snap[n.id]["countStartMs"] = int(t0)
            snap[n.id]["countDurationMs"] = int(sd["durationMs"])
        self.hooks.append(hook)

    def _late_reveal(self, node, lead=650):
        """Reveal node so its fade ends just before the step does (the offset is fixed at compile time)."""
        self.reveal(node, duration=400, offset=0)
        act = self.actions[-1]

        def hook(snap, t0, sd, adj, a=act):
            a["offsetMs"] = max(a.get("offsetMs", 0), int(sd["durationMs"]) - lead)
        self.hooks.append(hook)

    def grow(self, chart, which=None):
        """Bar chart: grow bars (an index, a list, or None = every bar not grown yet) from 0 to their value
        over this whole step. Each bar's value counts up while riding on top of the bar."""
        self._after_first("grow", chart)
        m = self._recipe(chart, "bars", "grow")
        n = len(m["values"])
        idx = [i for i in range(n) if i not in m["grown"]] if which is None else \
            ([which] if isinstance(which, int) else list(which))
        for i in idx:
            if not 0 <= i < n:
                raise OpenCanvizError("grow(%s): bar %r does not exist (0..%d)." % (chart.id, i, n - 1))
            if i in m["grown"]:
                raise OpenCanvizError("grow(%s): bar %d is already grown; grow each bar once." % (chart.id, i))
            m["grown"].add(i)
        self._patch(chart, chartBars=[{"id": "b%d" % i, "value": m["values"][i] if i in m["grown"] else 0, "label": ""}
                                      for i in range(n)])
        for i in idx:
            t = m["texts"][i]
            if t is not None:
                self.reveal(t, duration=300, offset=0)
                self._patch(t, y=m["top"][i])
                self._count_over_step(t)
        return self

    def extend(self, chart, upto=None):
        """Line chart: draw the line on to point index upto (default: the last point) over this step.
        Notes attached to points up to there fade in as the line reaches them."""
        self._after_first("extend", chart)
        m = self._recipe(chart, "line", "extend")
        pts = m["points"]
        upto = len(pts) - 1 if upto is None else upto
        if not m["shown"] < upto < len(pts):
            raise OpenCanvizError("extend(%s): upto must be past the last shown point (%d) and at most %d."
                                  % (chart.id, m["shown"], len(pts) - 1))
        m["shown"] = upto
        self._patch(chart, chartSeries=_series(m, upto))
        for i, t in sorted(m["notes"].items()):
            if i <= upto and not t.meta.get("shown"):
                t.meta["shown"] = True
                self._late_reveal(t)
        return self

    def scatter_to(self, chart, points, colors=None):
        """Scatter chart: move the dots to new (x, y) positions (and colors) over this step."""
        self._after_first("scatter_to", chart)
        m = self._recipe(chart, "scatter", "scatter_to")
        if len(points) != len(m["points"]):
            raise OpenCanvizError("scatter_to(%s): give %d points, one per dot." % (chart.id, len(m["points"])))
        m["points"] = list(points)
        if colors is not None:
            m["colors"] = list(colors)
        self._patch(chart, chartPoints=_dots(m))
        return self

    def swap(self, array, i, j):
        """Array: swap cells i and j; the two values arc past each other over the whole step (with the
        step's easing). Swap disjoint pairs only within one step. (An algoSwap action is not used: the
        exported video snaps it.)"""
        self._after_first("swap", array)
        m = self._recipe(array, "array", "swap")
        v = m["values"]
        if i == j or not (0 <= i < len(v) and 0 <= j < len(v)):
            raise OpenCanvizError("swap(%s): cells %r and %r must be two different indices in 0..%d."
                                  % (array.id, i, j, len(v) - 1))
        used = self.__dict__.setdefault("_swapped", {}).setdefault(array.id, set())
        if {i, j} & used:
            raise OpenCanvizError("swap(%s): cell %d or %d already swaps in this step; one swap per cell per step."
                                  % (array.id, i, j))
        if v[i] == v[j]:
            raise OpenCanvizError("swap(%s): cells %d and %d hold the same value, so nothing would move." % (array.id, i, j))
        used |= {i, j}
        v[i], v[j] = v[j], v[i]
        self._patch(array, cellValues=list(v))
        return self

    def color(self, struct, colors=None, edges=None, reset=False):
        """Color parts of a structure from this step on (cleared with None, or all with reset=True):
        array {index: color}, tree / linked list / graph {value: color} (graph edges={(a, b): color}),
        grid {(row, col): color}. The colors switch at the start of the step."""
        self._own(struct, Node)
        kind = struct.fields.get("kind")
        m = struct.meta.get("struct")
        if m is None:
            raise OpenCanvizError("color(%s): use it on a node from scene.array/tree/linked_list/graph/grid()."
                                  % struct.id)
        colors = colors or {}
        if kind == "algo-array":
            old = list(m["colors"])
            if reset:
                m["colors"] = [None] * len(m["colors"])
            for i, c in colors.items():
                m["colors"][i] = c
            # openCanviz keeps a cleared (null) cell in its old color for the whole step, so a cell cleared
            # here gets the plain fill color instead, which fades back over the step
            fill = struct.fields.get("fill")
            self._patch(struct, cellColors=[fill if (c is None and o is not None) else c
                                            for c, o in zip(m["colors"], old)])
        elif kind == "algo-grid":
            old = [list(r) for r in m["colors"]]
            if reset:
                m["colors"] = [[None] * len(r) for r in m["colors"]]
            for (r, c), col in colors.items():
                m["colors"][r][c] = col
            fill = struct.fields.get("fill")
            self._patch(struct, gridColors=[[fill if (c is None and o is not None) else c for c, o in zip(r, ro)]
                                            for r, ro in zip(m["colors"], old)])
        else:
            cleared = {}
            if reset:
                cleared = {nid: struct.fields.get("fill") or struct.scene.project.colors["fill"] for nid in m["colors"]}
                m["colors"], m["edge_colors"] = {}, {}
            for k, c in colors.items():
                nid = m["ids"].get(str(k))
                if nid is None:
                    raise OpenCanvizError("color(%s): no node %r." % (struct.id, k))
                if c is None:
                    if nid in m["colors"]:
                        cleared[nid] = struct.fields.get("fill") or struct.scene.project.colors["fill"]
                    m["colors"].pop(nid, None)
                else:
                    m["colors"][nid] = c
                    cleared.pop(nid, None)
            self._patch(struct, nodeColors=dict(m["colors"], **cleared))
            if edges:
                for (a, b), c in edges.items():
                    eid = m["edge_ids"].get((str(a), str(b))) or m["edge_ids"].get((str(b), str(a)))
                    if eid is None:
                        raise OpenCanvizError("color(%s): no edge %r-%r." % (struct.id, a, b))
                    m["edge_colors"][eid] = c
                self._patch(struct, edgeColors=dict(m["edge_colors"]))
        return self

    def point(self, pointer, at):
        """Move a pointer: an array index, a tree / list / graph value, or a grid (row, col). It glides."""
        self._own(pointer, Node)
        m = pointer.meta.get("pointer")
        if m is None:
            raise OpenCanvizError("point(%s): use it on a node from scene.pointer()." % pointer.id)
        self._patch(pointer, **_pointer_target(m["target"], at))
        return self

    def bracket(self, array, start, end, label=None, color=None):
        """Array: draw a bracket under cells start..end (inclusive) with a readable label under it."""
        m = self._recipe(array, "array", "bracket")
        th = self.scene.project.colors
        col = color or th["muted"]
        self._patch(array, rangeStart=start, rangeEnd=end, rangeColor=col, rangeLabel="")
        t = m.get("range_text")
        if label:
            f = array.fields
            cw = f["w"] / float(len(m["values"]))
            x0, x1 = f["x"] + start * cw, f["x"] + (end + 1) * cw
            fs = m["label_font"]
            if t is None:
                t = self.scene.text(label, x=x0, y=m["label_y"], w=x1 - x0, h=_tline(fs), fontSize=fs,
                                    color=col, id=array.id + "_range")
                m["range_text"] = t
                self.reveal(t, duration=400, offset=0)
            else:
                if t.meta.get("hidden"):
                    t.meta["hidden"] = False
                    self.reveal(t, duration=400, offset=0)
                self._patch(t, text=label, x=_clean(x0), w=_clean(x1 - x0), color=col)
        elif t is not None and not t.meta.get("hidden"):
            t.meta["hidden"] = True
            self.hide(t, offset=0)
        return self

    def assign(self, var, value):
        """Variable box: show a new value (it switches at the start of the step)."""
        m = self._recipe(var, "var", "assign")
        m["values"].append(str(value))
        self._patch(var, varValue=str(value))
        return self

    def set_cell(self, grid, row, col, value):
        """Grid: change one cell's value (switches at the start of the step)."""
        m = self._recipe(grid, "grid", "set_cell")
        m["values"][row][col] = str(value)
        self._patch(grid, gridValues=[list(r) for r in m["values"]])
        return self

    def append(self, lst, value):
        """Linked list: add a node at the tail (it appears at the start of the step)."""
        m = self._recipe(lst, "list", "append")
        if len(m["values"]) >= m["capacity"]:
            raise OpenCanvizError("append(%s): the list was sized for %d nodes; pass capacity= to linked_list()."
                                  % (lst.id, m["capacity"]))
        m["values"].append(str(value))
        m["ids"][str(value)] = "l%d" % (len(m["values"]) - 1)
        self._patch(lst, linkedListNodes=_list_nodes(m["values"]))
        return self

    def highlight(self, code, *lines):
        """Code panel: highlight these lines (1-based, as an editor numbers them); none clears it."""
        m = self._recipe(code, "code", "highlight")
        flat = []
        for ln in lines:
            flat.extend(ln if isinstance(ln, (list, tuple, range)) else [ln])
        for ln in flat:
            if not 1 <= ln <= m["lines"]:
                raise OpenCanvizError("highlight(%s): line %r is outside 1..%d." % (code.id, ln, m["lines"]))
        self._patch(code, highlightedLines=[ln - 1 for ln in flat])
        return self

    def activate(self, lifeline, start, end):
        """Sequence diagram: show an activation bar on a lifeline from message start to message end
        (the messages returned by scene.message(), or world y values)."""
        m = self._recipe(lifeline, "lifeline", "activate")
        ys = [s.meta_y if isinstance(s, Edge) else s for s in (start, end)]
        top = lifeline.fields["y"] + 50
        m["acts"].append({"startY": _clean(ys[0] - top - 12), "endY": _clean(ys[1] - top + 12)})
        self._patch(lifeline, activations=list(m["acts"]))
        return self

    def event(self, timeline, i=None):
        """Timeline: bring in the next event (or event i): its dot, year and text appear and the line grows
        to it over the step."""
        m = self._recipe(timeline, "timeline", "event")
        i = m["shown"] + 1 if i is None else i
        if not m["shown"] < i < len(m["events"]):
            raise OpenCanvizError("event(%s): event %r is not after the last shown one (%d)." % (timeline.id, i, m["shown"]))
        if m["shown"] < 0:
            self.reveal(timeline, duration=400, offset=0)
        if self.index == 0 and i > 0:
            self._after_first("event", timeline)
        m["shown"] = i
        ev = m["events"][i]
        self.reveal(ev, duration=500, offset=0)
        f = timeline.fields
        if m["vertical"]:
            self.move(timeline, h=max(12, m["pos"][i] - f["y"] + 6))
        else:
            self.move(timeline, w=max(12, m["pos"][i] - f["x"] + 6))
        return self

    def sweep(self, pie):
        """Pie / donut: reveal it and sweep every slice open from 12 o'clock over this step."""
        self._after_first("sweep", pie)
        m = self._recipe(pie, "pie", "sweep")
        self.reveal(pie, duration=400, offset=0)
        for w, (a0, a1) in zip(m["wedges"], m["angles"]):
            self._patch(w, startAngle=a0, endAngle=a1)
        return self

    def follow(self, node, path, duration=2000, offset=None, ease=None):
        """Move node along a path from scene.path(); it ends at the path's last point."""
        self._after_first("follow", node)
        self._own(node, Node)
        pts = self.scene.paths.get(path, {}).get("points")
        if not pts:
            raise OpenCanvizError("follow(%s): unknown path %r; make it with scene.path()." % (node.id, path))
        act = {"type": "pathFollow", "target": {"kind": "node", "id": node.id}, "pathId": path, "from": 0, "to": 1}
        if ease:
            act["ease"] = ease
        self._action(act, duration, offset)
        end = pts[-1]
        f = node.fields
        self._patch(node, x=_clean(end["x"] - f["w"] / 2.0), y=_clean(end["y"] - f["h"] / 2.0))
        return self

    def packet(self, edge, color=None, size=36, duration=1500, offset=None):
        """Send a dot along a drawn arrow (a request, a message, a packet)."""
        self._own(edge, Edge)
        col = color or self.scene.project.colors["hi"]
        self._action({"type": "pathAnimate", "target": {"kind": "edge", "id": edge.id}, "scale": 1, "opacity": 1,
                      "nodeSnapshot": {"id": self.scene._id(edge.id + "_pkt"), "kind": "circle", "w": size, "h": size,
                                       "fill": col, "stroke": "none"}}, duration, offset)
        return self


class Scene:
    """A scene: add nodes and arrows, then steps. Node ids are prefixed with s<N>_."""

    def __init__(self, project, index, name, transition, background):
        self.project, self.index, self.name = project, index, name
        self.prefix = "s%d_" % (index + 1)
        self.transition, self.background = transition, background
        self.nodes, self.edges, self.steps, self._ids = [], [], [], set()
        self.paths = {}

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
        if kind in BROKEN_KINDS:
            raise OpenCanvizError(BROKEN_KINDS[kind])
        what = "%s %r" % (kind, label or id or "")
        _check_fields(fields, NODE_FIELDS - {"id", "kind", "x", "y", "w", "h"}, what)
        if fields.get("glow") == 0:
            raise OpenCanvizError("%s: glow=0 is ignored by openCanviz; pass noGlow=True." % what)
        nid = self._id(id or label or fields.get("text") or kind)
        f = {"id": nid, "kind": kind}
        if kind == "algo-pointer":
            f.update({"x": 0, "y": 0, "w": 0, "h": 0})   # a pointer places itself on its target
        else:
            f.update(self._geom(at, x, y, w, h, what))
        th = self.project.colors
        if label is not None:
            f["label"] = label
            f.setdefault("labelColor", th["text"])
        if kind not in NO_THEME_KINDS:
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
        route="around" closes a cycle (last node back to the first): the arrow leaves and enters on the
        same side and runs outside the whole diagram, on whichever side (below, above, right, left) has
        room in the safe area. Labels get a readable font (24 px landscape, 30 px portrait).
        """
        for end in (a, b):
            if not isinstance(end, Node) or end.scene is not self:
                raise OpenCanvizError("arrow(): both ends must be nodes of this scene, got %r" % (end,))
        what = "edge %s->%s" % (a.id, b.id)
        _check_fields(fields, EDGE_FIELDS - {"id", "from", "to"}, what)
        if route not in (None, "below", "above", "left", "right", "around"):
            raise OpenCanvizError("%s: route must be None, 'below', 'above', 'left', 'right' or 'around'." % what)
        eid = self._id(id or "%s_to_%s" % (a.id[len(self.prefix):], b.id[len(self.prefix):]))
        f = {"id": eid, "from": a.id, "to": b.id}
        if route == "around":
            f.update({"fromPort": "S", "toPort": "S", "lineType": "elbowed"})   # side picked at save time
        elif route:
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
        f.update({"stroke": self.project.colors["edge"], "width": 4, "arrow": "end", "animationStyle": "none"})
        if label is not None:
            f.update(self.label_fields(label))
        f.update(fields)
        e = Edge(self, eid, a, b, f)
        e.user_fields = dict(fields)
        e.around = route == "around" and not ({"fromPort", "toPort", "waypoints"} & set(fields))
        self.edges.append(e)
        return e

    def label_fields(self, label, font_size=None):
        """Edge-label fields that center the label chip ON the line, whatever its direction: a chip in the
        background color masks the line behind it. (openCanviz's own placement puts it labelOffset px,
        default 12, off the line along the normal, which floats it beside vertical and leftward lines.)"""
        fs = font_size or self.project.edge_label_font
        return {"label": label, "labelColor": self.project.colors["muted"], "labelFontSize": fs,
                "labelPosition": "center", "labelOffset": 0.01, "labelOffsetY": _clean(fs * 0.6),
                "labelBgPadding": 8, "labelBgColor": self.scene_background()}

    def _route_around(self, e):
        """Pick the side for a route="around" arrow: the first of below, above, right, left whose lane
        clears every other node and stays in the safe area (label chip included); the lane runs 48 px
        outside the diagram, or far enough that a label chip centered on it clears the diagram by 16 px."""
        A = self.project.area()
        others = [n.fields for n in self.nodes if n is not e.a and n is not e.b and n.fields.get("kind") != "group"]
        fa, fb = e.a.fields, e.b.fields
        allf = [n.fields for n in self.nodes if n.fields.get("kind") != "group"]
        gx0 = min(n["x"] for n in allf)
        gy0 = min(n["y"] for n in allf)
        gx1 = max(n["x"] + n["w"] for n in allf)
        gy1 = max(n["y"] + n["h"] for n in allf)
        best = None
        lab = e.fields.get("label")
        lfs = e.fields.get("labelFontSize", 12)
        for side in ("S", "N", "E", "W"):
            f = dict(e.fields, fromPort=side, toPort=side, lineType="elbowed")
            f.pop("waypoints", None)
            pts = edge_path(f, fa, fb)
            if any(path_hits(pts, n) for n in others):
                pa, pb = _side_point(fa, side), _side_point(fb, side)
                half = 0
                if lab:
                    half = (label_height(lfs) if side in "NS" else label_width(lab, lfs)) / 2 + 16
                d = max(48, half)
                lane = {"S": gy1 + d, "N": gy0 - d, "E": gx1 + d, "W": gx0 - d}[side]
                wp = ([(pa[0], lane), (pb[0], lane)] if side in "NS" else [(lane, pa[1]), (lane, pb[1])])
                f["waypoints"] = [{"x": _clean(x), "y": _clean(y)} for x, y in wp]
                pts = edge_path(f, fa, fb)
                if any(path_hits(pts, n) for n in others):
                    continue
            inside = all(A.x - 1 <= x <= A.x + A.w + 1 and A.y - 1 <= y <= A.y + A.h + 1 for x, y in pts)
            if inside and lab:
                cx, cy = _path_mid(pts)
                lw, lh = label_width(lab, lfs), label_height(lfs)
                inside = A.x - 1 <= cx - lw / 2 and cx + lw / 2 <= A.x + A.w + 1 and \
                    A.y - 1 <= cy - lh / 2 and cy + lh / 2 <= A.y + A.h + 1
            if inside:
                best = f
                break
            if best is None:
                best = f
        if best is None:
            raise OpenCanvizError("edge %s (route='around'): no side has a clear lane around the diagram; leave "
                                  "room below or above the nodes." % e.id)
        e.fields = best

    # recipes ------------------------------------------------------------------------------------
    @property
    def _portrait(self):
        return self.project.height > self.project.width

    def _small_font(self):
        return 44 if self._portrait else 32

    def _floor(self, kind):
        return font_floor(kind, self.project.width, self.project.height)

    def line(self, p0, p1, a, b=None, arrow="none", color=None, width=3, dashed=False, id=None):
        """A straight line from world point p0 to p1 (an axis, a baseline, a sequence message). It is an
        edge pinned to node a (and b): it shows while they do and is drawn in with them."""
        for end in (a, b or a):
            if not isinstance(end, Node) or end.scene is not self:
                raise OpenCanvizError("line(): a and b must be nodes of this scene.")
        b = b or a
        eid = self._id(id or "%s_line" % a.id[len(self.prefix):])
        f = {"id": eid, "from": a.id, "to": b.id, "fromXY": {"x": _clean(p0[0]), "y": _clean(p0[1])},
             "toXY": {"x": _clean(p1[0]), "y": _clean(p1[1])}, "lineType": "straight", "arrow": arrow,
             "stroke": color or self.project.colors["muted"], "width": width, "animationStyle": "none"}
        if dashed:
            f["strokeStyle"] = "dashed"
        e = Edge(self, eid, a, b, f)
        e.user_fields, e.around = {}, False
        self.edges.append(e)
        return e

    def bar_chart(self, data, at, max_value=None, color=None, prefix="", suffix="", decimals=0, font=None,
                  values=True, id="bars"):
        """Bars that grow from zero. data = [(label, value), ...]. Category labels sit under the bars in a
        readable size and each value counts up on top of its bar while it grows. Reveal the chart (its
        labels and baseline come with it), then step.grow(chart) or step.grow(chart, i) per bar."""
        if not data:
            raise OpenCanvizError("bar_chart(): give at least one (label, value).")
        if decimals not in (0, 1):
            raise OpenCanvizError("bar_chart(): decimals must be 0 or 1 (openCanviz counts in whole numbers or "
                                  "one decimal).")
        th = self.project.colors
        n = len(data)
        lf = font or self._small_font()
        labels_h = (_tline(lf))
        x, y, w = at.x, at.y, at.w
        h = at.h - labels_h + 10
        bar_w = w / (n + 0.4 * (n - 1))
        gap = 0.4 * bar_w
        texts_fmt = [_fmt_num(v, decimals, prefix, suffix) for _, v in data]
        vf = min([fit_font(t, self.project.base_font, bar_w + 0.8 * gap, self.project.base_font * 1.4, bold=True)
                  or 14 for t in texts_fmt])
        vh = (_tline(vf))
        area_h = h - 18
        top_v = max_value if max_value is not None else max(v for _, v in data)
        if top_v <= 0:
            raise OpenCanvizError("bar_chart(): values must be > 0.")
        scale = top_v * area_h / float(area_h - (vh + 8 if values else 0))
        chart = self.node("algo-chart", None, x=x, y=y, w=w, h=h, id=id, noGlow=True, fill="transparent",
                          stroke="none", chartBars=[{"id": "b%d" % i, "value": 0, "label": ""} for i in range(n)],
                          chartMaxValue=_clean(scale), chartShowValues=False, chartBarSpacing=_clean(gap),
                          chartBarColor=color or th["accent"], labelColor=th["text"])
        base = y + area_h
        m = {"values": [v for _, v in data], "grown": set(), "texts": [], "top": []}
        for i, (lab, v) in enumerate(data):
            bx = x + i * (bar_w + gap)
            t = self.text(str(lab), x=bx - gap / 2, y=base + 6, w=bar_w + gap, h=labels_h, fontSize=lf,
                          color=th["muted"], id="%s_lbl%d" % (id, i))
            chart.parts.append(t)
            if values:
                vt = self.text(texts_fmt[i], x=bx - gap * 0.4, y=base - vh, w=bar_w + gap * 0.8, h=vh, fontSize=vf,
                               fontWeight=700, color=th["text"], id="%s_val%d" % (id, i), countFrom=0,
                               countTo=v, countIsInt=decimals == 0, **_affix(prefix, suffix))
                vt.meta["count_managed"] = True
                m["texts"].append(vt)
                m["top"].append(_clean(base - v / scale * area_h - vh - 4))
            else:
                m["texts"].append(None)
                m["top"].append(None)
        chart.parts.append(self.line((x - 10, base), (x + w + 10, base), chart, color=th["muted"], width=3))
        chart.meta["bars"] = m
        return chart

    def _plot(self, kind, at, x_range, y_range, x_ticks, y_ticks, x_title, y_title, font, fmt, id, extra):
        th = self.project.colors
        tf = font or self._small_font()
        fmt = fmt or _tick_fmt
        yt = _ticks(*y_range) if y_ticks is None else list(y_ticks)
        xt = _ticks(*x_range) if x_ticks is None else list(x_ticks)
        ylab = [fmt(v) for v in yt]
        gl = max(len(s) for s in ylab) * 0.58 * tf + 22
        top = int(tf * 1.7) if y_title else 10
        bottom = (_tline(tf)) + 8 + ((_tline(tf)) if x_title else 0)
        cx, cy, cw, ch = at.x + gl, at.y + top, at.w - gl, at.h - top - bottom
        if cw < 200 or ch < 160:
            raise OpenCanvizError("%s: the area is too small for a chart; give it at least 420 x 300 px." % kind)
        chart = self.node(kind, None, x=cx, y=cy, w=cw, h=ch, id=id, chartShowAxes=False, chartGridLines=False,
                          chartXRange=list(x_range), chartYRange=list(y_range), labelColor=th["text"],
                          fill="transparent", stroke="none", noGlow=True, **extra)
        X0, X1, Y0, Y1 = cx + 10, cx + cw - 12, cy + 14, cy + ch - 10
        span = float(y_range[1] - y_range[0]) or 1.0
        ylo, yhi = y_range[0] - 0.05 * span, y_range[1] + 0.05 * span
        xs = float(x_range[1] - x_range[0]) or 1.0

        def px(xv, yv):
            return X0 + (xv - x_range[0]) / xs * (X1 - X0), Y1 - (yv - ylo) / (yhi - ylo) * (Y1 - Y0)
        ax_y = px(0, y_range[0])[1]
        chart.parts.append(self.line((X0, ax_y), (X1, ax_y), chart, color=th["muted"], width=3))
        chart.parts.append(self.line((X0, px(0, y_range[1])[1]), (X0, ax_y), chart, color=th["muted"], width=3))
        th_ = _tline(tf)
        for v, s in zip(yt, ylab):
            chart.parts.append(self.text(s, x=at.x, y=px(0, v)[1] - th_ / 2, w=gl - 14, h=th_, fontSize=tf,
                                         textAlign="right", color=th["muted"], id="%s_y%s" % (id, _slug(s))))
        tw = min(220.0, (X1 - X0) / max(1, len(xt) - 1) if len(xt) > 1 else 220.0)
        for v in xt:
            s = fmt(v)
            chart.parts.append(self.text(s, x=px(v, 0)[0] - tw / 2, y=cy + ch + 4, w=tw, h=th_, fontSize=tf,
                                         color=th["muted"], id="%s_x%s" % (id, _slug(s))))
        if x_title:
            chart.parts.append(self.text(x_title, x=cx, y=cy + ch + 8 + th_, w=cw, h=_tline(tf), fontSize=tf,
                                         color=th["muted"], id="%s_xtitle" % id))
        if y_title:
            chart.parts.append(self.text(y_title, x=at.x, y=at.y, w=at.w * 0.6, h=_tline(tf), fontSize=tf,
                                         textAlign="left", color=th["muted"], id="%s_ytitle" % id))
        return chart, px

    def line_chart(self, points, at, x_range=None, y_range=None, color=None, x_ticks=None, y_ticks=None,
                   x_title=None, y_title=None, notes=None, font=None, fmt=None, id="line"):
        """A line that draws itself left to right. points = [(x, y), ...] in data units, sorted by x.
        Axes, tick labels and titles are readable text nodes. notes = {point index: "text"} labels a point
        when the line reaches it. Reveal the chart, then step.extend(chart, upto) one or more times."""
        if len(points) < 2:
            raise OpenCanvizError("line_chart(): give at least two points.")
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x_range = list(x_range or (min(xs), max(xs)))
        y_range = list(y_range or (min(0, min(ys)), _nice_ceil(max(ys))))
        th = self.project.colors
        col = color or th["hi"]
        m = {"points": [tuple(p) for p in points], "shown": 0, "color": col, "notes": {}}
        chart, px = self._plot("algo-chart-line", at, x_range, y_range, x_ticks, y_ticks, x_title, y_title, font,
                               fmt, id, {"chartSeries": _series(m, 0)})
        # the renderer maps data to px like px() does; 1.6 px in data units, each way
        (ax0, ay0), (ax1, ay1) = px(x_range[0], y_range[0]), px(x_range[1], y_range[1])
        ux = (x_range[1] - x_range[0]) / float(ax1 - ax0 or 1) * 1.6
        uy = (y_range[1] - y_range[0]) / float(ay0 - ay1 or 1) * 1.6
        m["offsets"] = [(0, 0), (0, uy), (0, -uy), (ux, 0), (-ux, 0)]
        chart.fields["chartSeries"] = _series(m, 0)
        tf = font or self._small_font()
        nf = max(self._floor("body"), tf + 6)
        for i, txt in sorted((notes or {}).items()):
            X, Y = px(*points[i])
            w = len(str(txt)) * 0.6 * nf + 24
            nx = min(max(X - w / 2, chart.fields["x"]), chart.fields["x"] + chart.fields["w"] - w)
            nh = _tline(nf)
            ny = Y - nh - 18 if Y - nh - 18 > chart.fields["y"] else Y + 18
            t = self.text(str(txt), x=nx, y=ny, w=w, h=nh, fontSize=nf, fontWeight=700, color=col,
                          id="%s_note%d" % (id, i))
            m["notes"][i] = t
        chart.meta["line"] = m
        return chart

    def scatter(self, points, at, x_range=None, y_range=None, colors=None, size=14, x_ticks=None, y_ticks=None,
                x_title=None, y_title=None, font=None, fmt=None, id="scatter"):
        """Dots at (x, y) in data units; step.scatter_to(chart, new_points, colors) moves them over a step."""
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x_range = list(x_range or (min(0, min(xs)), _nice_ceil(max(xs))))
        y_range = list(y_range or (min(0, min(ys)), _nice_ceil(max(ys))))
        th = self.project.colors
        m = {"points": list(points), "colors": list(colors or [th["accent"]] * len(points)), "size": size}
        chart, _ = self._plot("algo-chart-scatter", at, x_range, y_range, x_ticks, y_ticks, x_title, y_title, font,
                              fmt, id, {"chartPoints": _dots(m)})
        chart.meta["scatter"] = m
        return chart

    def array(self, values, at, font=None, indices=True, id="array"):
        """A row of cells (sorting, searching, two pointers). The rect also keeps 70 px on top for pointers
        and about 130 px below (170 in portrait) for the index row and a bracket label. Use step.swap / color / bracket and
        scene.pointer(). The index numbers are text nodes that come and go with the array."""
        n = len(values)
        th = self.project.colors
        sf, isf = self._small_font(), self._floor("tick")
        below = 16 + (_tline(isf) if indices else 0) + 4 + _tline(sf)
        y, h = at.y + 70, at.h - 70 - below
        if h < 80 or n == 0:
            raise OpenCanvizError("array(): give a rect at least %d px tall and one or more values." % (150 + below))
        cell_w = at.w / float(n)
        fs = font or int(min(64, cell_w * 0.45, (h - 30) * 0.5))
        # openCanviz's own index row resets the canvas alpha, so with it on the array ignores opacity and
        # cannot fade in or out; draw the indices as text nodes instead
        node = self.node("algo-array", None, x=at.x, y=y, w=at.w, h=h, id=id, cellValues=[str(v) for v in values],
                         cellColors=[None] * n, cellFontSize=fs, cellShowIndices=False, fill=th["fill"],
                         stroke=th["muted"], labelColor=th["text"], noGlow=True)
        if indices:
            for i in range(n):
                node.parts.append(self.text(str(i), x=at.x + i * cell_w, y=y + h + 16, w=cell_w, h=_tline(isf),
                                            fontSize=isf, color=th["muted"], id="%s_i%d" % (id, i)))
        m = {"values": [str(v) for v in values], "colors": [None] * n, "label_font": sf,
             "label_y": y + h + 16 + (_tline(isf) if indices else 0) + 4, "indices": indices}
        node.meta["array"] = node.meta["struct"] = m
        return node

    def pointer(self, target, at, label="", color=None, side="top", font=None, id=None):
        """A labeled arrow on a cell of a structure: an array index, a tree / linked list / graph value, a
        grid (row, col) or a bar index of a bar chart. It shows with its target; move it with step.point."""
        self._own_node(target)
        f = {"pointerTargetId": target.id, "pointerLabel": str(label), "pointerColor": color or self.project.colors["hi"],
             "labelFontSize": font or self._small_font() + 4, "pointerArrowSize": 20}
        if target.fields.get("kind") == "algo-array":
            if side == "bottom" and target.meta["array"]["indices"]:
                raise OpenCanvizError("pointer(%s): a bottom pointer sits right under the cells, over the index row "
                                      "and the bracket; use side=\"top\" or array(..., indices=False)." % label)
            f["pointerSidePosition"] = side
        f.update(_pointer_target(target, at))
        n = self.node("algo-pointer", None, id=id or "ptr_%s" % (label or "p"), **f)
        n.meta["pointer"] = {"target": target}
        target.parts.append(n)
        return n

    def _own_node(self, n):
        if not isinstance(n, Node) or n.scene is not self:
            raise OpenCanvizError("expected a node of this scene, got %r" % (n,))

    def tree(self, spec, at, font=None, radius=None, id="tree"):
        """A tree inside at. spec = {value: [left, right], ...}, root first; use "" for an empty child slot,
        e.g. {"5": ["3", "8"], "3": ["1", "4"], "8": ["", "9"]}. openCanviz scales a tree to fill its box,
        so the node is sized to the tree (centered in at) to keep circles from overlapping or ballooning."""
        spec = {str(k): [("" if c is None else str(c)) for c in v] for k, v in spec.items()}
        root = next(iter(spec))
        ids = {}
        order = [root] + [c for v in spec.values() for c in v if c]
        for v in order:
            ids.setdefault(v, "n_" + _slug(v))

        def slots(v, seen=()):
            kids = spec.get(v) or []
            if not kids or v in seen:
                return 1
            return max(1, sum(1 if not c else slots(c, seen + (v,)) for c in kids))

        def depth(v, seen=()):
            kids = [c for c in spec.get(v, []) if c and c not in seen]
            return 1 + max([depth(c, seen + (v,)) for c in kids] or [0])
        cols, rows = slots(root), depth(root)
        sp_k, lv_k = 2.6, 2.8           # spacing and level height in radii

        def natural(r):                  # openCanviz: leaves sit spacing apart, levels levelHeight apart
            return ((cols - 1) * sp_k * r + 2 * (r + 8), (rows - 1) * lv_k * r + 2 * (r + 8))
        r = float(radius or 64)
        while r > 14 and (natural(r)[0] > at.w or natural(r)[1] > at.h):
            r -= 1
        nw, nh = natural(r)
        nodes = []
        for v in dict.fromkeys(order):
            e = {"id": ids[v], "value": v}
            if spec.get(v):
                e["children"] = [ids[c] if c else "" for c in spec[v]]
            nodes.append(e)
        box = Rect(at.cx - nw / 2, at.cy - nh / 2, nw, nh)
        node = self.node("algo-tree", None, at=box, id=id, treeNodes=nodes, nodeRadius=_clean(r),
                         nodeSpacing=_clean(sp_k * r), levelHeight=_clean(lv_k * r), nodeFontSize=font or int(r * 0.9),
                         fill=self.project.colors["fill"], labelColor=self.project.colors["text"])
        node.meta["struct"] = {"ids": ids, "colors": {}, "edge_colors": {}, "edge_ids": {}}
        return node

    def linked_list(self, values, at, capacity=None, font=None, id="list"):
        """A linked list (boxes joined by next arrows, ending in null). capacity = most nodes it will hold
        after step.append(); the boxes are sized for that many."""
        cap = max(capacity or 0, len(values))
        nw = min(150.0, (at.w - 120) / (cap * 1.4))
        nh = min(100.0, at.h, nw * 0.7)
        fs = font or int(max(20, min(nw, nh) * 0.45))
        vals = [str(v) for v in values]
        node = self.node("algo-linked-list", None, at=at, id=id, linkedListNodes=_list_nodes(vals),
                         linkedListNodeWidth=_clean(nw), linkedListNodeHeight=_clean(nh), nodeFontSize=fs,
                         fill=self.project.colors["fill"], labelColor=self.project.colors["text"])
        m = {"values": vals, "capacity": cap, "ids": {v: "l%d" % i for i, v in enumerate(vals)}, "colors": {},
             "edge_colors": {}, "edge_ids": {}}
        node.meta["list"] = node.meta["struct"] = m
        return node

    def graph(self, nodes, edges, at, directed=False, font=None, radius=None, id="graph"):
        """A graph. nodes = {name: (fx, fy)} with fx, fy in 0..1 across the rect; edges = [(a, b) or
        (a, b, weight)]. Color nodes and edges with step.color(g, {name: c}, edges={(a, b): c})."""
        r = radius or int(max(24, min(44, at.h / 8.0, at.w / 12.0)))
        sw, sh = at.w - 2 * r - 20, at.h - 2 * r - 20
        gn = [{"id": "g_" + _slug(k), "value": str(k), "x": _clean(fx * sw), "y": _clean(fy * sh)}
              for k, (fx, fy) in nodes.items()]
        ids = {str(k): "g_" + _slug(k) for k in nodes}
        ge, eids = [], {}
        for e in edges:
            a, b = str(e[0]), str(e[1])
            if a not in ids or b not in ids:
                raise OpenCanvizError("graph(): edge %r-%r joins an unknown node." % (a, b))
            eid = "e_%s_%s" % (_slug(a), _slug(b))
            g = {"id": eid, "source": ids[a], "target": ids[b]}
            if len(e) > 2:
                g["weight"] = e[2]
            ge.append(g)
            eids[(a, b)] = eid
        node = self.node("algo-graph", None, at=at, id=id, graphNodes=gn, graphEdges=ge, graphNodeRadius=r,
                         graphDirected=bool(directed), nodeFontSize=font or int(r * 0.8), labelFontSize=24,
                         labelColor=self.project.colors["text"])
        node.meta["struct"] = {"ids": ids, "colors": {}, "edge_colors": {}, "edge_ids": eids}
        return node

    def grid(self, rows, at, font=None, id="grid"):
        """A table of cells (dynamic programming, a matrix, a board). rows = [[v, ...], ...]."""
        vals = [[str(v) for v in r] for r in rows]
        nr, nc = len(vals), max(len(r) for r in vals)
        fs = font or int(max(20, min(44, at.h / nr * 0.45, at.w / nc * 0.35)))
        node = self.node("algo-grid", None, at=at, id=id, gridValues=[list(r) for r in vals],
                         gridColors=[[None] * nc for _ in vals], gridCellFontSize=fs,
                         gridIndexFontSize=max(18, int(fs * 0.5)), fill=self.project.colors["fill"],
                         labelColor=self.project.colors["text"])
        m = {"values": vals, "colors": [[None] * nc for _ in vals]}
        node.meta["grid"] = node.meta["struct"] = m
        return node

    def variable(self, name, value, at, font=None, id=None):
        """A named value box ("min = 3"); step.assign(var, v) changes it. The box is only as wide as the
        name plus its longest value (openCanviz draws the name at the left edge and the value at the right
        edge, so a wide box splits them apart); it sits at the left of at, centered vertically. Every
        variable of the scene gets the same width so a column of them lines up."""
        fl = self._floor("var")
        fs = font or int(max(fl, min(fl * 1.4, at.h * 0.4)))
        h = min(at.h, int(math.ceil(fs * 2.0)))
        node = self.node("algo-variable", None, x=at.x, y=at.y + (at.h - h) / 2.0, w=at.w, h=h,
                         id=id or "var_" + _slug(name), varName=str(name), varValue=str(value), labelFontSize=fs,
                         labelColor=self.project.colors["text"])
        node.meta["var"] = {"values": [str(value)], "max_w": at.w}
        node.meta["reserve"] = True
        return node

    def _size_variables(self):
        """Narrow every variable box to its name plus its longest value (called once, at compile)."""
        vs = [n for n in self.nodes if "var" in n.meta]
        want = {}
        for n in vs:
            fs = n.fields["labelFontSize"]
            name_w = len(n.fields["varName"] + " =") * CHAR_W * fs
            val_w = max(len(v) for v in n.meta["var"]["values"]) * (CHAR_W + 0.07) * fs
            want[n.id] = 16 + name_w + 0.9 * fs + val_w + 8
        if not vs:
            return
        w = max(want.values())
        for n in vs:
            n.fields["w"] = _clean(min(n.meta["var"]["max_w"], max(w, n.fields["h"] * 1.6)))

    def code(self, source, at, language="python", font=None, id="code"):
        """A code panel with syntax colors (python, javascript or pseudo). step.highlight(code, 3) marks
        line 3 (1-based); the mark jumps from line to line."""
        if language not in ("python", "javascript", "pseudo"):
            raise OpenCanvizError("code(): language must be python, javascript or pseudo.")
        th = self.project.colors
        lines = source.rstrip("\n").split("\n")
        longest = max(len(l) for l in lines)
        fl = self._floor("code")
        fs = font or int(min(fl * 1.8, (at.h - 48) / (len(lines) * 1.4), (at.w - 48) / (longest * 0.62)))
        if fs < fl:
            raise OpenCanvizError("code(): %d lines of up to %d characters need a bigger rect (font would be %d px, "
                                  "the readable floor is %d); give the panel more width, shorten the longest line "
                                  "or show fewer lines." % (len(lines), longest, fs, fl))
        ch = min(at.h, int(math.ceil(len(lines) * fs * 1.4 + 2 * 20 + 12)))
        at = Rect(at.x, at.y + (at.h - ch) / 2.0, at.w, ch)
        node = self.node("text", None, at=at, id=id, text="\n".join(lines), fontFamily="monospace", fontSize=fs,
                         lineHeight=1.4, textAlign="left", verticalAlign="top", wrap="clip", syntaxStyle=language,
                         highlightedLines=[], color=th["code"], fill=th["panel"], stroke=th["line"],
                         strokeWidth=2, padding=20, noGlow=True)
        # openCanviz shows the old and new highlighted lines together until the step ends; this flag makes
        # the mark jump at the start of the step instead (seen working in the export renderer)
        node.fields["_animatedProps"] = {"highlightedLines": False}
        node.meta["code"] = {"lines": len(lines)}
        node.meta["reserve"] = True
        return node

    def sequence(self, names, at, font=None):
        """Lifelines for a sequence diagram, one per name, spread across at. Then scene.message(a, b, text)
        for each call and step.draw(msg) to send it (its text appears once the arrow lands)."""
        n = len(names)
        col = at.w / float(n)
        w = min(260.0, col - 40)
        th = self.project.colors
        out = []
        for i, name in enumerate(names):
            x = at.x + col * i + (col - w) / 2
            lf = font or (40 if self._portrait else 34)   # the header box is a fixed 50 px
            ln = self.node("uml-lifeline", str(name), x=x, y=at.y, w=w, h=at.h, id="life_" + _slug(name),
                           lifelineLength=_clean(at.h - 50), fill=th["fill"], stroke=th["muted"], labelColor=th["text"],
                           labelFontSize=lf, noGlow=True)
            ln.meta["lifeline"] = {"acts": []}
            out.append(ln)
        self._seq_y = at.y + 50 + 80
        return out

    def message(self, a, b, text, y=None, reply=False, font=None):
        """An arrow from lifeline a to lifeline b at height y (default: below the previous message), with
        its text above it. reply=True draws it dashed with an open head. Send it with step.draw(msg)."""
        if a is b:
            raise OpenCanvizError("message(): a and b must be different lifelines.")
        th = self.project.colors
        y = getattr(self, "_seq_y", a.fields["y"] + 130) if y is None else y
        self._seq_y = y + max(100, _tline(font or self._floor("body")) + 50)
        ax, bx = a.rect.cx, b.rect.cx
        e = self.line((ax, y), (bx, y), a, b, arrow="end", color=th["muted"] if reply else th["text"], width=3,
                      dashed=reply, id="msg_" + _slug(text))
        e.fields["endArrowType"] = "open-triangle" if reply else "triangle"
        e.fields["strokeStyle"] = "dashed" if reply else "solid"
        fs = font or self._floor("body")
        t = self.text(str(text), x=min(ax, bx) + 16, y=y - _tline(fs) - 8, w=abs(bx - ax) - 32, h=_tline(fs), fontSize=fs,
                      color=th["text"], id="msg_" + _slug(text) + "_text")
        e.parts.append(t)
        e.meta_y = y
        return e

    def timeline(self, events, at, font=None, color=None, id="timeline"):
        """Events [(year, text), ...] on a line that grows from one to the next: across in landscape, down in
        portrait. step.event(tl) brings in the next one (call it once per event). The whole track is laid
        out (and framed by the camera) from the first event, so the first dot sits where it will stay and
        the line grows along a faint track. In landscape, 4 or more events alternate above and below the
        line so each text gets twice the width. Keep each event text to a few words (about 30 characters)."""
        th = self.project.colors
        acc = color or th["accent"]
        n = len(events)
        if n < 2:
            raise OpenCanvizError("timeline(): give at least two events.")
        vertical = at.h > at.w
        floor = self._floor("body")
        handles, pos = [], []
        if not vertical and not font:
            # the biggest event font (up to 56 px) at which every text fits in 3 lines and the block fits at.h
            slot = at.w / float(n)
            tw = min(560.0, (2 * at.w - 24 * (n - 1)) / (n + 1.0)) if n >= 4 else slot - 16
            font = floor
            for f in range(56, floor - 1, -2):
                ls = [text_lines(str(t), f, tw) for _, t in events]
                if None in ls or max(ls) > 3:
                    continue
                bh = math.ceil(max(ls) * f * LINE_H + 2 * TEXT_PAD + 2)
                one = _tline(int(f * 1.35)) + 8 + bh
                blk = 2 * (one + f * 0.65 + 12) if n >= 4 else one + 34 + f * 1.3
                if blk <= at.h:
                    font = f
                    break
        fs = font or max(floor, 48 if self._portrait else 38)
        yf = int(fs * 1.35)
        D = int(fs * 1.3)

        def body_font(txt, w, h):
            tf = fit_font(str(txt), fs, w, h, minimum=min(fs, floor))
            if tf is None:
                raise OpenCanvizError("timeline(): event text %r does not fit at %d px (the readable floor); shorten "
                                      "it to a few words and say the rest in the narration." % (txt, floor))
            return tf

        if not vertical:
            slot = at.w / float(n)
            alt = n >= 4
            # alternating: texts on one side are two dots apart, and the end texts stay inside at
            tw = min(560.0, (2 * at.w - 24 * (n - 1)) / (n + 1.0)) if alt else slot - 16
            yh = _tline(yf)
            nl = max([text_lines(str(t), fs, tw) or 3 for _, t in events] + [1])
            body_h = int(math.ceil(min(3, nl) * fs * LINE_H + 2 * TEXT_PAD + 2))
            if alt:
                half = yh + 8 + body_h
                block = 2 * (half + D / 2.0 + 12)
                if block > at.h:
                    body_h = max(int(math.ceil(2 * fs * LINE_H + 2 * TEXT_PAD + 2)), int(body_h - (block - at.h) / 2))
                    half = yh + 8 + body_h
                    block = 2 * (half + D / 2.0 + 12)
                cy = at.y + max(0, (at.h - block) / 2.0) + half + D / 2.0 + 12
            else:
                block = yh + 14 + D + 20 + body_h
                cy = at.y + max(0, (at.h - block) / 2.0) + yh + 14 + D / 2.0
            for i in range(n):
                if alt:
                    pos.append(at.x + tw / 2.0 + (at.w - tw) * i / float(n - 1))
                else:
                    pos.append(at.x + slot * (i + 0.5))
            track = self.node("rect", None, x=pos[0], y=cy - 5, w=max(10, pos[-1] - pos[0]), h=10, id=id + "_track",
                              fill=th["line"], stroke="none", cornerRadius=5, noGlow=True)
            line = self.node("rect", None, x=pos[0] - 6, y=cy - 6, w=12, h=12, id=id, fill=th["muted"],
                             stroke="none", cornerRadius=6, noGlow=True)
            line.parts.append(track)
            for i, (yr, txt) in enumerate(events):
                xi = pos[i]
                dot = self.node("circle", None, x=xi - D / 2.0, y=cy - D / 2.0, w=D, h=D, id="%s_dot%d" % (id, i),
                                fill=acc, stroke=self.scene_background(), strokeWidth=5, noGlow=True)
                up = alt and i % 2 == 1
                tf = body_font(txt, tw, body_h)
                if up:
                    yy = cy - D / 2.0 - 12 - yh
                    by = yy - 8 - body_h
                    va = "bottom"
                else:
                    yy = cy + D / 2.0 + 12 if alt else cy - D / 2.0 - 14 - yh
                    by = (yy + yh + 8) if alt else cy + D / 2.0 + 20
                    va = "top"
                year = self.text(str(yr), x=xi - tw / 2.0, y=yy, w=tw, h=yh, fontSize=yf, fontWeight=700, color=acc,
                                 id="%s_year%d" % (id, i))
                body = self.text(str(txt), x=xi - tw / 2.0, y=by, w=tw, h=body_h, fontSize=tf, color=th["text"],
                                 verticalAlign=va, id="%s_text%d" % (id, i))
                dot.parts += [year, body]
                handles.append(dot)
        else:
            slot = at.h / float(n)
            lx = at.x + yf * 2.6 + 30
            for i in range(n):
                pos.append(at.y + slot * (i + 0.5))
            track = self.node("rect", None, x=lx - 5, y=pos[0], w=10, h=max(10, pos[-1] - pos[0]), id=id + "_track",
                              fill=th["line"], stroke="none", cornerRadius=5, noGlow=True)
            line = self.node("rect", None, x=lx - 6, y=pos[0] - 6, w=12, h=12, id=id, fill=th["muted"],
                             stroke="none", cornerRadius=6, noGlow=True)
            line.parts.append(track)
            for i, (yr, txt) in enumerate(events):
                yi = pos[i]
                dot = self.node("circle", None, x=lx - D / 2.0, y=yi - D / 2.0, w=D, h=D, id="%s_dot%d" % (id, i),
                                fill=acc, stroke=self.scene_background(), strokeWidth=5, noGlow=True)
                year = self.text(str(yr), x=at.x, y=yi - _tline(yf) / 2.0, w=lx - D / 2.0 - 16 - at.x, h=_tline(yf),
                                 fontSize=yf, fontWeight=700, color=acc, textAlign="right", id="%s_year%d" % (id, i))
                bx = lx + D / 2.0 + 20
                bw = at.x + at.w - bx
                tf = body_font(txt, bw, slot - 12)
                body = self.text(str(txt), x=bx, y=yi - (slot - 12) / 2, w=bw, h=slot - 12, fontSize=tf,
                                 color=th["text"], textAlign="left", id="%s_text%d" % (id, i))
                dot.parts += [year, body]
                handles.append(dot)
        line.meta["timeline"] = {"events": handles, "pos": pos, "shown": -1, "vertical": vertical}
        self.reserve(line, *handles)
        return line

    def panels(self, titles, at, colors=None, font=None):
        """Side-by-side panels (stacked in portrait) for before / after or A vs B. Returns the panel nodes;
        each has .content, the Rect to lay its own nodes out in. Reveal a panel to show it with its title."""
        th = self.project.colors
        cols = list(colors or [th["bad"], th["ok"], th["accent"], th["hi"]])
        rects = at.column(len(titles), gap=40) if self._portrait else at.row(len(titles), gap=60)
        fs = font or int(max(self._floor("body") * 1.1, self.project.base_font * 0.9))
        out = []
        for i, (title, r) in enumerate(zip(titles, rects)):
            c = cols[i % len(cols)]
            p = self.node("rect", None, at=r, id="panel_" + _slug(title), fill=th["panel"], stroke=c, strokeWidth=3,
                          cornerRadius=20, noGlow=True)
            head = self.text(str(title), x=r.x + 20, y=r.y + 16, w=r.w - 40, h=_tline(fs), fontSize=fs, fontWeight=700,
                             color=c, id="panel_" + _slug(title) + "_title")
            p.parts.append(head)
            top = 16 + _tline(fs) + 16
            p.content = Rect(r.x + 28, r.y + top, r.w - 56, r.h - top - 28, at.label_size)
            p.meta["reserve"] = True
            out.append(p)
        return out

    def bullets(self, items, at, glyph="check", color=None, font=None, id="point"):
        """A list of points, each with a check (or x, dot, arrow) that draws itself in when the point is
        revealed. The list is big (body text and up), centered as a block in at, and the camera frames the
        whole list from the first point. Returns the text nodes; reveal them one per step, or together."""
        th = self.project.colors
        n = len(items)
        floor = self._floor("body")
        start = font
        if not start:
            # the biggest font (up to 1.6 x base) at which every point fits in 2 lines and the list fits at.h
            start = floor
            for f in range(int(self.project.base_font * 1.6), floor - 1, -2):
                ls = [text_lines(str(t), f, at.w - f * 1.2 - 28) for t in items]
                if None in ls or max(ls) > 2:
                    continue
                r = math.ceil(max(ls) * f * LINE_H + 2 * TEXT_PAD + 6)
                if n * r + int(f * 0.6) * (n - 1) <= at.h:
                    start = f
                    break
        gap = int(start * 0.6)
        rh = min((at.h - gap * (n - 1)) / float(n), math.ceil(2 * start * LINE_H + 2 * TEXT_PAD + 6))
        g = int(min(rh, start * 1.2))
        tw = at.w - g - 28
        if font:
            fs = font
        else:
            got = [fit_font(str(t), start, tw, rh, minimum=floor) for t in items]
            if None in got:
                raise OpenCanvizError("bullets(): %r does not fit at %d px (the readable floor) in a %dx%d row; use "
                                      "fewer or shorter points, or a taller rect." % (items[got.index(None)], floor,
                                                                                       tw, rh))
            fs = min(got)
        widths = []
        for t in items:
            lines = text_lines(str(t), fs, tw) or 1
            widths.append(tw if lines > 1 else len(str(t)) * CHAR_W * fs + 12)
        text_w = min(tw, max(widths))
        block_w = g + 28 + text_w
        x0 = at.cx - block_w / 2.0
        y0 = at.cy - (n * rh + gap * (n - 1)) / 2.0
        out = []
        for i, txt in enumerate(items):
            ry = y0 + i * (rh + gap)
            gl = self.node("glyph", None, x=x0, y=ry + rh / 2.0 - g / 2.0, w=g, h=g, id="%s%d_glyph" % (id, i + 1),
                           glyph=glyph, color=color or th["ok"])
            t = self.text(str(txt), x=x0 + g + 28, y=ry, w=text_w, h=rh, fontSize=fs, textAlign="left",
                          id="%s%d" % (id, i + 1))
            t.parts.append(gl)
            out.append(t)
        self.reserve(*out)
        return out

    def counter(self, value, at, start=0, prefix="", suffix="", decimals=0, font=None, color=None, duration=1500,
                id=None):
        """A big number that counts up from start to value when it is revealed (over duration ms)."""
        if decimals not in (0, 1):
            raise OpenCanvizError("counter(): decimals must be 0 or 1.")
        txt = _fmt_num(value, decimals, prefix, suffix)
        fs = font or fit_font(txt, self.project.base_font * 2.4, at.w, at.h, bold=True) or 14
        return self.text(txt, at=at, fontSize=fs, fontWeight=800, color=color or self.project.colors["accent"],
                         id=id or "count_" + _slug(txt), countFrom=start, countTo=value, countDurationMs=duration,
                         countIsInt=decimals == 0, **_affix(prefix, suffix))

    def pie(self, data, at, donut=0.0, colors=None, font=None, decimals=0, id="pie"):
        """A pie (donut=0.55 for a ring) with a legend. data = [(label, value), ...]. step.sweep(pie)
        reveals it and sweeps the slices open; do not reveal it yourself."""
        th = self.project.colors
        cols = list(colors or PALETTE)
        total = float(sum(v for _, v in data))
        if total <= 0:
            raise OpenCanvizError("pie(): values must add up to more than 0.")
        if self._portrait:
            side = min(at.w * 0.8, at.h * 0.55)
            pr = Rect(at.cx - side / 2, at.y, side, side)
            legend = Rect(at.x, at.y + side + 40, at.w, at.h - side - 40)
        else:
            side = min(at.h, at.w * 0.48)
            pr = Rect(at.x + (at.w * 0.5 - side) / 2, at.cy - side / 2, side, side)
            legend = Rect(at.x + at.w * 0.55, at.y, at.w * 0.45, at.h)
        wedges, angles, acc = [], [], 0.0
        for i, (lab, v) in enumerate(data):
            a0 = -90 + 360 * acc / total
            acc += v
            a1 = -90 + 360 * acc / total
            f = dict(startAngle=-90, endAngle=-90, fill=cols[i % len(cols)], stroke=self.scene_background(),
                     strokeWidth=4, noGlow=True)
            if donut:
                f["innerRadius"] = donut
            wedges.append(self.node("wedge", None, at=pr, id="%s_%s" % (id, _slug(lab)), **f))
            angles.append((_clean(a0), _clean(a1)))
        n = len(data)
        rh = min(self.project.base_font * 1.8, (legend.h - 16 * (n - 1)) / float(n))
        rows = legend.column(n, gap=16, h=rh)
        fs = font or int(max(self._floor("body"), min(self.project.base_font, (rh - 2 * TEXT_PAD - 2) / LINE_H)))
        parts = wedges[1:]
        for i, ((lab, v), r) in enumerate(zip(data, rows)):
            sw = min(rh * 0.8, 40)
            parts.append(self.node("rect", None, x=r.x, y=r.cy - sw / 2, w=sw, h=sw, id="%s_key%d" % (id, i),
                                   fill=cols[i % len(cols)], stroke="none", cornerRadius=6, noGlow=True))
            pct = ("%." + str(decimals) + "f%%") % (100.0 * v / total)
            parts.append(self.text("%s  %s" % (lab, pct), x=r.x + sw + 20, y=r.y, w=r.w - sw - 20, h=r.h,
                                   fontSize=fs, textAlign="left", id="%s_keytext%d" % (id, i)))
        wedges[0].parts += parts
        wedges[0].meta["pie"] = {"wedges": wedges, "angles": angles}
        return wedges[0]

    def path(self, points, closed=False, id="path"):
        """A motion path through world points [(x, y), ...] for step.follow(node, path). Returns its id."""
        if len(points) < 2:
            raise OpenCanvizError("path(): give at least two points.")
        pts = [{"x": _clean(x), "y": _clean(y)} for x, y in points]
        if closed and pts[0] != pts[-1]:
            pts.append(dict(pts[0]))
        pid = self._id(id)
        # the export renderer reads length and cum (cumulative length at each point) straight from the file and
        # leaves the node where it is when they are missing, so fill them in here
        cum = [0]
        for p, q in zip(pts, pts[1:]):
            cum.append(_clean(cum[-1] + math.hypot(q["x"] - p["x"], q["y"] - p["y"])))
        self.paths[pid] = {"id": pid, "points": pts, "closed": bool(closed), "length": cum[-1], "cum": cum}
        return pid

    def scene_background(self):
        return self.background or self.project.colors["background"]

    def reserve(self, *nodes):
        """Make the follow camera frame these nodes (and their parts) from the first step, as if they were
        already on screen, so the layout does not pan when they arrive. The timeline, code, variable,
        bullets and panels recipes reserve their nodes for you: a code panel whose variables come in later
        is centered with them from the start."""
        for n in nodes:
            self._own_node(n)
            n.meta["reserve"] = True
        return nodes[0] if len(nodes) == 1 else nodes

    def _reserved_ids(self):
        out, todo = set(), [n for n in self.nodes if n.meta.get("reserve")]
        while todo:
            n = todo.pop()
            if isinstance(n, Node) and n.id not in out and n.fields.get("kind") != "algo-pointer":
                out.add(n.id)
                todo += n.parts
        return out

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
        self._size_variables()
        for e in self.edges:
            if e.around:
                self._route_around(e)
        vis, evis = self._timelines()
        snap_nodes = []
        for n in self.nodes:
            f = {k: v for k, v in n.fields.items() if not k.startswith("_") or k == "_animatedProps"}
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
            f["opacity"] = 0 if later else f.get("opacity", 1)
            if e.twin_steps:
                t = e.twin_fields()
                # end of step 0: drawn and faded if step 0 draws it, else waiting at trim 0 opacity 0
                t["trim"], t["opacity"] = (1, 0) if 0 in e.twin_steps else (0, 0)
                snap_edges.append(t)
            snap_edges.append(f)
        twins = {e.id: e.twin_id for e in self.edges if e.twin_steps}
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
                        epatch[e.id]["opacity"] = e.fields.get("opacity", 1) if evis[e.id][k] else 0
                    if k in e.twin_steps:
                        epatch[e.twin_id] = {"trim": 1, "opacity": 0}
            for eid in list(st.remove_edges):
                if eid in twins:
                    st.remove_edges.append(twins[eid])
            dur = st.duration
            words = len(str(st.narration or st.caption).split())
            need = max(st._cursor, st._tail)
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
                if sd["edges"] and not sd["nodes"]:
                    # openCanviz blanks every node in a delta step that lists edges but no nodes, so
                    # restate one node's current opacity
                    gone = {n.id for n in self.nodes if any(j <= k and kind == "remove" for j, kind in n.events)}
                    live = [n for n in self.nodes if n.id not in gone]
                    pick = next((n for n in live if vis[n.id][k]), live[0] if live else None)
                    if pick is not None:
                        sd["nodes"] = [{"id": pick.id, "opacity": shown_opacity[pick.id] if vis[pick.id][k] else 0}]
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
        self._follow(steps)
        _hold_first_edge_tweens(steps[0])
        snap = {n["id"]: n for n in steps[0]["nodes"]}
        t0 = 0
        for st, sd in zip(self.steps, steps):
            def adj(off, sh=st._shift):
                return off + sh[1] if sh and off >= sh[0] else off
            for node, field, off in st.timed:
                snap[node.id][field] = int(t0 + adj(off))
            for fn in st.hooks:
                fn(snap, t0, sd, adj)
            t0 += sd["durationMs"]
        scene = {"nodes": [dict(x) for x in steps[0]["nodes"]], "edges": [dict(x) for x in steps[0]["edges"]],
                 "steps": steps}
        if narration:
            scene["narration"] = narration
        if self.paths:
            scene["paths"] = dict(self.paths)
        if self.background:
            scene["background"] = self.background
        return scene


    def _follow(self, steps):
        """Follow camera: at the end of every step, center what is on screen in the safe area, so a
        lone first node or a half-built diagram sits in the middle instead of where the finished layout
        puts it. Off when the project has follow=False or any step of the scene sets its own camera."""
        P = self.project
        if not P.follow or any(st.camera_spec for st in self.steps):
            return
        A = P.area()
        nodes, edges = {}, {}
        cur = (0.0, 0.0)
        keep = self._reserved_ids()
        for k, sd in enumerate(steps):
            if k == 0:
                nodes = {n["id"]: dict(n) for n in sd["nodes"]}
                edges = {e["id"]: dict(e) for e in sd["edges"]}
            else:
                for nid in sd.get("removeNodeIds") or []:
                    nodes.pop(nid, None)
                for eid in sd.get("removeEdgeIds") or []:
                    edges.pop(eid, None)
                for p in sd["nodes"]:
                    nodes.setdefault(p["id"], {}).update(p)
                for p in sd["edges"]:
                    edges.setdefault(p["id"], {}).update(p)
            box = _visible_bbox(nodes, edges)
            if box is None:
                continue
            held = [n for i, n in nodes.items() if i in keep and all(_num(n.get(k)) for k in ("x", "y", "w", "h"))]
            if held:
                xs = [x for n in held for x in _ink_x(n)]
                box = (min([box[0]] + xs), min([box[1]] + [n["y"] for n in held]),
                       max([box[2]] + xs), max([box[3]] + [n["y"] + n["h"] for n in held]))
            target = _center_camera(box, (A.x, A.y, A.x + A.w, A.y + A.h))
            if math.hypot(target[0] - cur[0], target[1] - cur[1]) < 40:
                continue
            cam = {"camera": {"x": _clean(target[0]), "y": _clean(target[1]), "zoom": 1}}
            if k == 0:
                cam["cameraDurationMs"] = 0
            else:
                # pan first, then let the new things arrive: everything that starts at or after the first
                # arrival waits for the pan, so nothing appears while the frame is still moving (where it
                # would sit under the caption or off center for a moment)
                acts = sd.get("actions") or []
                ins = [a.get("offsetMs", 0) for a in acts if _arrives(a)]
                if ins:
                    off, pan = min(ins), PAN_FIRST_MS
                    for a in acts:
                        if a.get("offsetMs", 0) >= off:
                            a["offsetMs"] = a.get("offsetMs", 0) + pan
                    self.steps[k]._shift = (off, pan)
                    end = max([a.get("offsetMs", 0) + a.get("durationMs", 0) for a in acts] + [off + pan])
                    sd["durationMs"] = max(sd["durationMs"], int(math.ceil((end + 600) / 100.0) * 100))
                    cam.update({"cameraDurationMs": pan, "cameraEasing": "ease"})
                else:
                    off = 0
                    cam.update({"cameraDurationMs": int(min(FOLLOW_MS, sd["durationMs"])), "cameraEasing": "ease"})
                if off:
                    cam["cameraOffsetMs"] = off
            sd.update(cam)
            cur = target


def _arrives(a):
    """True for an action that brings something onto the screen (a reveal or an edge draw-in)."""
    if a.get("type") == "visibility":
        return a.get("mode") in VIS_IN
    if a.get("type") == "edgeTween":
        fr, to = a.get("from") or {}, a.get("to") or {}
        return _num(fr.get("trim")) and _num(to.get("trim")) and to["trim"] > fr["trim"]
    return False


class Project:
    """An openCanviz project. aspect: "16:9" (1920x1080), "9:16" (1080x1920) or "1:1" (1080x1080)."""

    def __init__(self, title, aspect="16:9", background=None, theme="dark", voice="alloy", captions=True,
                 caption_style=None, margin=60, side_margin=None, follow=True):
        if aspect not in ASPECTS:
            raise OpenCanvizError("aspect must be one of %s" % sorted(ASPECTS))
        if theme not in THEMES:
            raise OpenCanvizError("theme must be one of %s" % sorted(THEMES))
        if voice not in VOICES:
            raise OpenCanvizError("voice must be one of %s" % sorted(VOICES))
        self.title, self.aspect, self.voice, self.captions = title, aspect, voice, captions
        self.caption_style, self.margin = caption_style, margin
        self.width, self.height = ASPECTS[aspect]
        if side_margin is None:
            side_margin = SIDE_MARGIN if self.width > self.height else 80
        self.side_margin = max(side_margin, margin)
        self.follow = follow
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

    def area(self, margin=None, caption_space=None, side_margin=None):
        """The safe layout area: the artboard minus the margins (60 px top, 120 px left/right in landscape,
        80 in portrait and square), and minus the caption band at the bottom (20% of the height in
        landscape, 30% in portrait, where captions wrap to 3-4 lines)."""
        m = self.margin if margin is None else margin
        if m < 60:
            raise OpenCanvizError("area(): keep a margin of at least 60 px.")
        side = max(m, self.side_margin if side_margin is None else side_margin)
        if caption_space is None:
            cap = caption_band(self.width, self.height) * self.height if self.captions else m
        else:
            cap = max(caption_space, m)
        return Rect(-self.width / 2 + side, -self.height / 2 + m, self.width - 2 * side, self.height - m - cap,
                    self.edge_label_font)

    def safe_center(self):
        """Center of the default area() in world px; the follow camera centers each step's content here."""
        a = self.area()
        return a.cx, a.cy

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
            if k == "_animatedProps" and v == {"highlightedLines": False}:
                pass   # the one internal flag that is safe to set: code highlights jump instead of blending
            elif k in INTERNAL_FIELDS:
                errors.append("%s: remove '%s'; openCanviz sets it." % (where, k))
            if k == "sketchMode":
                errors.append("%s: remove sketchMode; it renders badly in the exported video." % where)
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
    if isinstance(e.get("fromXY"), dict) and isinstance(e.get("toXY"), dict):
        return [(e["fromXY"]["x"], e["fromXY"]["y"]), (e["toXY"]["x"], e["toXY"]["y"])]
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


def _path_mid(pts):
    """Point halfway along a polyline (where openCanviz centers an edge label)."""
    segs = [(p, q, math.hypot(q[0] - p[0], q[1] - p[1])) for p, q in zip(pts, pts[1:])]
    half, acc = sum(s[2] for s in segs) / 2.0, 0.0
    for p, q, l in segs:
        if acc + l >= half and l > 0:
            t = (half - acc) / l
            return p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        acc += l
    return pts[0]


def _ink_x(n):
    """Left and right x of what a node draws. A text node's box is often the full width of the frame,
    so its ink (the longest line, placed by textAlign) is used instead."""
    x0, x1 = n["x"], n["x"] + n["w"]
    if n.get("kind") != "text" or not _num(n.get("fontSize")) or n.get("fill") not in (None, "", "transparent", "none"):
        return x0, x1
    bold = str(n.get("fontWeight", 400)) in ("600", "700", "800", "900", "bold")
    longest = max([len(s) for s in str(n.get("text", "")).split("\n")] or [0])
    ink = min(n["w"], longest * (0.6 if bold else CHAR_W) * n["fontSize"])
    align = n.get("textAlign", "center")
    if align == "left":
        return x0, x0 + ink
    if align == "right":
        return x1 - ink, x1
    mid = (x0 + x1) / 2.0
    return mid - ink / 2.0, mid + ink / 2.0


def _visible_bbox(nodes, edges):
    """(x0, y0, x1, y1) of the visible nodes and drawn arrows, or None when nothing shows."""
    vis = {i: n for i, n in nodes.items() if (n.get("opacity", 1) or 0) > 0.01
           and all(_num(n.get(k)) for k in ("x", "y", "w", "h")) and n.get("kind") not in ("group", "algo-pointer")}
    if not vis:
        return None
    xs, ys = [], []
    for n in vis.values():
        xs += list(_ink_x(n))
        ys += [n["y"], n["y"] + n["h"]]
    for e in edges.values():
        a, b = vis.get(e.get("from")), vis.get(e.get("to"))
        if not a or not b or (e.get("trim", 1) or 0) <= 0.01 or (e.get("opacity", 1) or 0) <= 0.01:
            continue
        for x, y in edge_path(e, a, b):
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _center_camera(box, area):
    """Camera (x, y) at zoom 1 that puts box's center on area's center, kept so the box stays inside
    the area on each axis where it fits (else that axis keeps the authored position)."""
    out = []
    for lo_b, hi_b, lo_a, hi_a in ((box[0], box[2], area[0], area[2]), (box[1], box[3], area[1], area[3])):
        if hi_b - lo_b > hi_a - lo_a:
            out.append(0.0)
            continue
        ideal = (lo_b + hi_b) / 2 - (lo_a + hi_a) / 2
        out.append(round(min(max(ideal, hi_b - hi_a), lo_b - lo_a), 1))
    return out[0], out[1]


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


def _node_field_checks(n, where, E, W):
    """Fields seen to break the render: glow 0, sketchMode, one-color icons with no fill, missing font sizes."""
    nid, kind = n.get("id"), n.get("kind")
    if n.get("glow") == 0:
        E("%s: %s has glow 0, which openCanviz ignores; use \"noGlow\": true." % (where, nid))
    asset = n.get("asset")
    if isinstance(asset, dict) and asset.get("source") == "iconify":
        prefix = str(asset.get("ref", "")).split(":")[0]
        if prefix not in MULTICOLOR_ICON_SETS and not (n.get("iconStyle") == "solid" and n.get("fill")):
            W("%s: icon %s (%s) is one color and renders black; add \"iconStyle\": \"solid\" and a \"fill\" hex."
              % (where, nid, asset.get("ref")))
    ff = FONT_FIELDS.get(kind)
    if ff and ff not in n:
        W("%s: %s (%s) has no %s, so its text renders at 11-14 px; set it (the helper's recipes do)."
          % (where, nid, kind, ff))


def _overlap_ok(a, b):
    """Pairs that are meant to overlap: text over a chart, a lifeline or a progress bar, a glyph on a progress
    bar, pie wedges sharing a center, and any pair where one node is a thin line (12 px or less)."""
    ka, kb = a.get("kind"), b.get("kind")
    kinds = {ka, kb}
    if min(a["w"], a["h"], b["w"], b["h"]) <= 12:
        return True
    if ka == kb == "wedge":
        return True
    under = {"algo-chart", "algo-chart-line", "algo-chart-scatter", "progress", "uml-lifeline"}
    if "text" in kinds and (ka in under or kb in under):
        return True
    if kinds == {"glyph", "progress"}:
        return True
    return False


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
    # every node that shows at some point of the scene (the finished layout the steps build toward)
    ever = set()
    for k, st in enumerate(steps):
        if not isinstance(st, dict):
            continue
        for n in st.get("nodes") or []:
            if isinstance(n, dict) and (k == 0 and (n.get("opacity", 1) or 0) > 0.01 or k > 0 and (n.get("opacity") or 0) > 0.01):
                ever.add(n.get("id"))
        for a in st.get("actions") or []:
            if isinstance(a, dict) and _arrives(a) and isinstance(a.get("target"), dict):
                ever.add(a["target"].get("id"))
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
        if n["kind"] in BROKEN_KINDS:
            E("%s: node %s: %s." % (where, n["id"], BROKEN_KINDS[n["kind"]]))
        _node_field_checks(n, where, E, W)
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
        if "animationStyle" not in e:
            W("%s: edge %s has no animationStyle; openCanviz then runs marching dashes along it forever. Set "
              "\"animationStyle\": \"none\" (or \"flow\" on purpose)." % (where, e["id"]))
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
    view = (ab["x"] + ab["width"] / 2.0, ab["y"] + ab["height"] / 2.0, 1.0) if ab else None
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
            elif (st.get("edges") or st.get("addEdges")) and not (st.get("nodes") or st.get("addNodes")):
                E("%s: this delta step changes edges but lists no nodes, and openCanviz then blanks every node for "
                  "the step. List at least one node with an unchanged field (for example {\"id\": <any visible "
                  "node>, \"opacity\": 1}); the Python helper does this." % P)
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
                if "glow" in p and p["glow"] == 0:
                    E("%s: %s sets glow 0, which openCanviz ignores; use \"noGlow\": true." % (P, p["id"]))
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
        tp_tweened = {(a.get("target") or {}).get("id") for a in acts if isinstance(a, dict)
                      and a.get("type") == "transformTween" and "typeProgress" in (a.get("to") or {})}
        for p in (st.get("nodes") or []) if k > 0 else []:
            if isinstance(p, dict) and "typeProgress" in p and p.get("id") not in tp_tweened:
                W("%s: %s changes typeProgress with no transformTween, so the text jumps instead of typing. Tween "
                  "it: {\"type\":\"transformTween\",\"from\":{\"typeProgress\":0},\"to\":{\"typeProgress\":1}}."
                  % (P, p.get("id")))
        last_et = {}
        for a in acts:
            if isinstance(a, dict) and a.get("type") == "edgeTween":
                eid_ = (a.get("target") or {}).get("id")
                end_ = (a.get("offsetMs") or 0) + (a.get("durationMs") or 0)
                if eid_ not in last_et or end_ >= (last_et[eid_].get("offsetMs") or 0) + (last_et[eid_].get("durationMs") or 0):
                    last_et[eid_] = a
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
                to, fr = a.get("to") or {}, a.get("from") or {}
                if edges[tid].get("label") and _num(fr.get("trim")) and _num(to.get("trim")) and \
                        to["trim"] > fr["trim"] + 0.3 and (to.get("opacity", 1) or 0) > 0.01 and once(("slide", tid)):
                    W("%s: edge %s draws in with its label showing; openCanviz puts the label at the middle of the "
                      "drawn part, so it slides along with the tip and shows before the arrow. Draw an unlabeled "
                      "copy of the line (trim 0 -> 1), then fade the labeled edge in on it (edgeTween from "
                      "{\"trim\":1,\"opacity\":0} to {\"trim\":1,\"opacity\":1}, offsetMs = the end of the draw); "
                      "the Python helper's draw() does this." % (P, tid))
                cur = edges[tid].get("trim", 1)
                if "trim" in to and abs(to["trim"] - cur) > 0.01 and last_et.get(tid) is a:
                    E("%s: edgeTween on %s ends at trim %g but the step leaves it at %g; set \"trim\": %g for it in "
                      "this step's edges." % (P, tid, to["trim"], cur, to["trim"]))
            elif t == "pathFollow":
                pth = (sc.get("paths") or {}).get(a.get("pathId"))
                if not isinstance(pth, dict):
                    E("%s: pathFollow uses unknown path %s." % (P, a.get("pathId")))
                elif not (_num(pth.get("length")) and isinstance(pth.get("cum"), list)
                          and len(pth["cum"]) == len(pth.get("points") or [])):
                    E("%s: path %s needs \"length\" (total px) and \"cum\" (length so far at each point, starting "
                      "at 0); without them the exported video leaves the node where it is. scene.path() fills them."
                      % (P, a.get("pathId")))
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
            low = font_floor_issue(n, ab["width"], ab["height"]) if ab else None
            if low and once(("floor", nid)):
                W("%s: %s: %s (1080p landscape: body 34, code 30, ticks 28, variables 34; x1.4 in portrait). "
                  "Raise the font size and give it the room, or say less on screen." % (P, nid, low))
            for key in ("fill", "stroke", "color", "labelColor", "progressColor"):
                if key in n and (not isinstance(n[key], str) or not COLOR_RE.match(n[key].strip())):
                    W("%s: %s.%s=%r is not a hex color." % (P, nid, key, n[key]))
        vis = [nodes[i] for i in sorted(vis_nodes) if nodes[i].get("kind") not in ("group", "algo-pointer")
               and not nodes[i].get("parentId")
               and all(_num(nodes[i].get(x)) for x in ("x", "y", "w", "h"))]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                if _overlap_ok(a, b):
                    continue
                inside = _contains(a, b) or _contains(b, a)
                if inside and _overlap(a, b) and min(a["w"] * a["h"], b["w"] * b["h"]) > 0.8 * max(
                        a["w"] * a["h"], b["w"] * b["h"]) and once(("same", a["id"], b["id"])):
                    E("%s: %s and %s sit on the same spot (x=%g y=%g), so one hides the other; give them "
                      "different rects (note cut_bottom returns (rest, band): the band is [1])."
                      % (P, a["id"], b["id"], b["x"], b["y"]))
                elif _overlap(a, b) and not inside and once(("ov", a["id"], b["id"])):
                    W("%s: %s and %s overlap; move them apart or put one fully inside the other."
                      % (P, a["id"], b["id"]))
        c = st.get("camera")
        if ab and isinstance(c, dict) and all(_num(c.get(x)) for x in ("x", "y", "zoom")):
            view = (c["x"], c["y"], c["zoom"])
        if ab and view:
            later = [n for i, n in nodes.items() if i in ever and n.get("kind") not in ("group", "algo-pointer")
                     and not n.get("parentId") and all(_num(n.get(x)) for x in ("x", "y", "w", "h"))]
            _screen_checks(P, ab, captions, nodes, edges, vis, view, W, once, later)
        _layout_checks(P, ab, captions, nodes, edges, vis, any_caption, W, once)
        _arrow_length_checks(P, nodes, edges, vis, W, once)
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
        head = e.get("arrow", "end") not in ("none", None)
        if (e.get("label") or head) and trim <= 0.01 and op > 0.01 and once(("lbl0", eid)):
            W("%s: edge %s has %s and trim 0 but opacity %g; it shows at the start port before the line draws. "
              "Give it \"opacity\": 0 until its draw step, then opacity 1 with trim 1."
              % (P, eid, "a label" if e.get("label") else "an arrowhead", op))
        if e.get("label") and e.get("labelFontSize", 12) < lmin and once(("lfs", eid)):
            W("%s: edge %s label font is %g px; set labelFontSize to at least %d so it reads at 1080p."
              % (P, eid, e.get("labelFontSize", 12), lmin))
        if trim <= 0.01 or op <= 0.01 or not a or not b or e.get("from") not in vis_ids or e.get("to") not in vis_ids:
            continue
        if not all(_num(x.get(k)) for x in (a, b) for k in ("x", "y", "w", "h")):
            continue
        if "fromXY" in e and "toXY" in e:
            continue   # a pinned straight line (axis, baseline, message): no gap or crossing rules
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


def _arrow_length_checks(P, nodes, edges, vis, W, once):
    """A drawn arrow must show a real line: at least 80 px beside its label chip."""
    vids = {n["id"] for n in vis}
    for eid, e in edges.items():
        if (e.get("trim", 1) or 0) <= 0.01 or (e.get("opacity", 1) or 0) <= 0.01:
            continue
        if e.get("from") not in vids or e.get("to") not in vids or eid.endswith("_line") and eid[:-5] in edges:
            continue
        if "fromXY" in e and "toXY" in e:
            continue
        pts = edge_path(e, nodes[e["from"]], nodes[e["to"]])
        segs = [(p, q, math.hypot(q[0] - p[0], q[1] - p[1])) for p, q in zip(pts, pts[1:])]
        length = sum(s[2] for s in segs)
        chip = 0
        if e.get("label"):
            fs = e.get("labelFontSize") or 12
            acc, horiz = 0.0, True
            for p, q, s in segs:
                if acc + s >= length / 2 and s > 0:
                    horiz = abs(q[0] - p[0]) >= abs(q[1] - p[1])
                    break
                acc += s
            chip = label_width(e["label"], fs) if horiz else label_height(fs)
        if length - chip < 80 and once(("short", eid)):
            W("%s: arrow %s shows only %d px of line%s; leave a gap of the label chip plus 120 px between "
              "%s and %s (link_gap() gives it; the layout helpers use it when you pass labels=)."
              % (P, eid, max(0, length - chip), " beside its label" if chip else "", e["from"], e["to"]))


def _screen_checks(P, ab, captions, nodes, edges, vis, cam, W, once, later=None):
    """Where the step's content lands on screen (after the camera pan): centered in the safe area,
    and clear of the side edges. Skipped while the camera zooms. A step that shows part of a layout
    passes when the finished layout (later: every node the scene shows at some point) is centered and
    what shows already spans at least half of it on one axis (a timeline's first event, a code panel
    whose variables come next) or only text (a title over a list still to come), so the frame holds
    still while it fills in."""
    if abs(cam[2] - 1) > 0.05:
        return
    W_, H_ = ab["width"], ab["height"]
    sx, sy = cam[0] - (ab["x"] + W_ / 2.0), cam[1] - (ab["y"] + H_ / 2.0)
    box = _visible_bbox({n["id"]: n for n in vis}, edges)
    if box is None:
        return
    band = caption_band(W_, H_) * H_ if captions else 60
    acx, acy = ab["x"] + W_ / 2.0, ab["y"] + 60 + (H_ - 60 - band) / 2.0
    bcx, bcy = (box[0] + box[2]) / 2.0 - sx, (box[1] + box[3]) / 2.0 - sy
    off = math.hypot(bcx - acx, bcy - acy)
    if off > 0.15 * H_ and later:
        fb = _visible_bbox({n["id"]: dict(n, opacity=1) for n in later}, {})
        if fb is not None:
            fx, fy = (fb[0] + fb[2]) / 2.0 - sx, (fb[1] + fb[3]) / 2.0 - sy
            span = max((box[2] - box[0]) / max(1.0, fb[2] - fb[0]), (box[3] - box[1]) / max(1.0, fb[3] - fb[1]))
            if math.hypot(fx - acx, fy - acy) <= 0.15 * H_ and (span >= 0.5 or all(n.get("kind") == "text" for n in vis)):
                off = 0
    if off > 0.15 * H_ and once(("center", P)):
        W("%s: what shows sits %d px off the center of the safe area (%s); center it, or pan the camera to it "
          "(the Python helper's follow camera does this per step)." % (P, off, "%s%s" % (
              "high" if bcy < acy - 0.1 * H_ else "low" if bcy > acy + 0.1 * H_ else "",
              " left" if bcx < acx - 0.1 * H_ else " right" if bcx > acx + 0.1 * H_ else "")))
    side = 100 if W_ > H_ else 60
    for n in vis:
        if n.get("kind") == "text":
            continue
        x0, x1 = n["x"] - sx, n["x"] + n["w"] - sx
        if (x0 < ab["x"] + side - 1 or x1 > ab["x"] + W_ - side + 1) and once(("side", n["id"])):
            W("%s: %s comes within %d px of the side of the frame; keep %d px side margins (project.area() does)."
              % (P, n["id"], min(x0 - ab["x"], ab["x"] + W_ - x1), side))


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
