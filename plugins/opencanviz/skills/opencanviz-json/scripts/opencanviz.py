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

import base64
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
    "countFrom", "countTo", "countStartMs", "countDurationMs", "countPrefix", "countSuffix", "countIsInt",
    # text entrances and scene morphs
    "hideCaret", "writeHand", "blur", "morphKey", "wipeAxis", "wipeOrigin", "wipeSoft",
    # images, math and svg paths drawn in their own px
    "svgStretch", "imageData", "mathTex", "haloColor"}

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
LABEL_POP = 40         # a labeled arrow appears whole (ease "step": its chip opaque from the first frame) ...
TWIN_FADE = 40         # ... on the same frame as the unlabeled line under it goes (ease "step")

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
# Text entrances (render-checked in the export renderer): reveal(style=...) names -> what they do.
TEXT_ENTRANCES = {"type", "type_quiet", "write", "pop"}
BROKEN_ENTRANCES = {
    "blur": "a blur tween is not drawn in exported videos (only the editor shows it); use \"pop\" or a fade.",
    "blur-in": "a blur tween is not drawn in exported videos (only the editor shows it); use \"pop\" or \"zoom\".",
    "wipe": "drawProgress / wipeAxis wipes only image nodes; a text node appears whole. Use \"write\" or \"type\"."}
# Motion presets (render-checked in the export renderer; see SKILL.md "Motion presets").
MOTION_IN = {"fade", "slide", "drop", "rise", "zoom", "wipe", "draw"}
POP_FROM_MODES = {"below", "edges", "scatter", None}
EMPHASIS = {"pulse": 440, "shake": 300, "wiggle": 400, "flash": 800, "nudge": 500}     # default ms
BROKEN_EMPHASIS = {"glow": "a glow tween is not drawn and a glow change is barely visible; use \"pulse\" or \"flash\"."}
MOTION_OUT = {"fade", "slide", "shrink", "absorb", "scatter"}
CAPTION_DECIMAL = re.compile(r"\d\.\d")
SFX_PACKS = {"soft", "playful", "retro", "mech", "off"}
END_PAD_MS = 150       # hide(offset="end") finishes this long before the step ends
FLASH_HOLD_MS = 1500   # a flash stays lit at least this long, and to the end of its step
FLASH_OUT_MS = 350
IMPORT_SOFT_LIMIT = 150 * 1024
DOT_GAP = 6            # px a ring arc stops short of a dot at its end
PULSE_MIN_PX = 10      # a pulse grows a node's short side by at least this much
PULSE_MAX = 1.3
PULSE_THIN = 3.5       # one side over 3.5x the other: a pulse would not show, flash instead
DEAD_AIR_MS = 1000     # a captioned step may be blank this long at most (an exit finishing, a late reveal)
STEADY_MS = 300        # stage="steady": every scene crossfades this long (260-340 ms reads as one stage)
POP_MS, POP_FROM = 500, 0.6
STAGGER_MS = 180
TYPE_CPS = {"type": 28, "type_quiet": 28, "write": 16}     # characters per second
COLOR_WIPES = {"colorWipe", "colorWipeLeft", "colorWipeUp", "colorWipeDown"}
FLIP_TRANSITIONS = {"flip-x", "flip-y"}


def type_ms(text, style="type"):
    """Default typing time for a text: 28 characters a second (16 when a hand writes it), 600-3000 ms."""
    n = len(str(text).replace("\n", ""))
    return int(max(600, min(3000, round(1000.0 * n / TYPE_CPS.get(style, 28)))))


VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}
TWEEN_PROPS = {"x", "y", "w", "h", "scaleX", "scaleY", "rotationX", "rotationY", "rotationZ", "opacity", "fill",
               "stroke", "strokeWidth", "strokeTrimStart", "strokeTrimEnd", "typeProgress", "drawProgress",
               "blur", "value", "cellColors", "gridColors", "nodeColors", "cellValues", "gridValues",
               "highlightedLines", "color", "labelColor", "cylinderTopFill", "iconBg", "pointerColor", "rangeColor",
               "textStroke", "pointerTargetIndex", "pointerTargetRow", "pointerTargetCol", "rangeStart", "rangeEnd",
               "startAngle", "endAngle", "innerRadius", "cornerRadius"}
# Structure fields a transformTween can time: its `to` names the field (the step snapshot holds the value)
# and the change runs over the tween's offsetMs/durationMs instead of the whole step.
ALGO_TIMED = {"cellColors", "gridColors", "nodeColors", "cellValues", "gridValues", "highlightedLines"}
SWAP_MS = 600          # an array swap arcs this long from the step start
COLOR_MS = 350         # a structure's colors switch this fast from the step start
POINTER_MS = 350       # a pointer glides to its new cell this fast from the step start
FILL_MS = 350          # a node's fill / stroke / text colour changes this fast (set() without a duration)
MOVE_MS = 600          # move() without a duration
TIMELINE_MS = 600      # a timeline's line grows to the next event this fast
GROW_MS = 1400         # a line chart's extend() draws its new stretch of line this fast (whole extend)
NOTE_HOLD = 1500       # ... and holds the last point label this long before the step ends
# node fields whose change set()/move() time with a short transformTween; a change to one of these with no
# tween in the step plays across the whole step (the validator warns)
TIMED_COLORS = {"fill", "stroke", "color", "labelColor", "cylinderTopFill", "iconBg", "pointerColor",
                "rangeColor", "textStroke"}
TIMED_GEOM = {"x", "y", "w", "h"}

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
LABEL_EDGE = 120       # an edge label chip keeps this far from the left and right sides of the frame
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


FONT_FLOORS = {"body": 34, "code": 30, "tick": 28, "var": 34, "math": 56}


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


def _sc(v):
    """A scale factor: 2 decimals, so a gentle 1.04 pulse is not rounded away to 1."""
    v = round(float(v), 2)
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


def _fill(struct):
    """The plain cell / node colour openCanviz paints when a structure has no colour set for it."""
    return struct.fields.get("fill") or "#1e293b"


def _cells(struct, colors):
    fill = _fill(struct)
    return [c or fill for c in colors]


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
        self._end_acts = []    # (action, offset as placed) for hide(offset="end"), moved to the step's end
        self._hold_acts = []   # (action, offset as placed) a flash's way back, each moved to the step's end
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

    def reveal(self, node, style="fadeIn", duration=None, offset=None, ease=None, distance=None):
        """Show a hidden node (or a list of nodes, together). Sets opacity 1 for you. The node's parts (a
        chart's axes and labels, a bullet's glyph) come with it; a glyph draws itself in and a counter starts
        counting when it is revealed.

        Motion presets: "fade", "slide" (a 60 px rise), "drop" (falls in with a bounce: an arrival),
        "rise" (a soft 50 px rise), "zoom" (settles from 1.6x), "wipe" (left to right: a box or bar
        grows from its left edge, an image or equation is uncovered) and "draw" (an svg path or a ring arc
        draws itself on). step.pop() pops a group in with a stagger, step.stagger() any style.

        style: fadeIn, show, slideInLeft/Right/Up/Down (500 ms), or one of the text entrances:
        "type" (typewriter with a caret), "type_quiet" (no caret), "write" (a marker hand writes it on;
        text nodes only, duration from the text length unless given) and "pop" (fade in while scaling up
        from 0.6 with a "back" overshoot, 500 ms; any node). "blur" and "wipe" are refused: neither shows on
        text in an exported video. For lines one after another use reveal_lines()."""
        if style in TEXT_ENTRANCES:
            return self._entrance(node, style, duration, offset, ease)
        if style in MOTION_IN:
            if isinstance(node, (list, tuple)):
                start = self._place(0, offset)
                for n in node:
                    self._motion_in(n, style, duration, start, ease, distance)
                self._last_start = start
                return self
            return self._motion_in(node, style, duration, offset, ease, distance)
        if duration is None:
            duration = 500
        if isinstance(node, (list, tuple)):
            for i, n in enumerate(node):
                self.reveal(n, style, duration, offset if i == 0 else "with", ease, distance)
            return self
        self._own(node, Node)
        if style in BROKEN_ENTRANCES:
            raise OpenCanvizError("reveal(%s): %s" % (node.id, BROKEN_ENTRANCES[style]))
        if style not in VIS_IN:
            raise OpenCanvizError("reveal(%s): style must be one of %s or %s"
                                  % (node.id, sorted(VIS_IN), sorted(TEXT_ENTRANCES)))
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

    def _entrance(self, node, style, duration, offset, ease):
        if isinstance(node, (list, tuple)):
            for i, n in enumerate(node):
                self._entrance(n, style, duration, offset if i == 0 else "with", ease)
            return self
        self._own(node, Node)
        if style == "pop":
            ms = duration or POP_MS
            start = self._place(ms, offset)
            self.reveal(node, "fadeIn", min(250, ms), start)
            node.fields.setdefault("scaleX", 1)
            node.fields.setdefault("scaleY", 1)
            self._action({"type": "transformTween", "target": {"kind": "node", "id": node.id},
                          "from": {"scaleX": POP_FROM, "scaleY": POP_FROM}, "to": {"scaleX": 1, "scaleY": 1},
                          "ease": ease or "back"}, ms, start)
            self._last_start = start
            return self
        if node.fields.get("kind") != "text":
            raise OpenCanvizError("reveal(%s, %r): only text nodes can be typed or written; use \"pop\" or a "
                                  "fade for other nodes." % (node.id, style))
        if style == "write":
            node.fields["writeHand"] = True
            node.fields["hideCaret"] = True
        elif style == "type_quiet":
            node.fields["hideCaret"] = True
        return self.typewrite(node, duration or type_ms(node.fields.get("text", ""), style), offset)

    def reveal_lines(self, nodes, style="slideInUp", gap=STAGGER_MS, duration=None, offset=None, distance=40,
                     ease="ease-out"):
        """Bring separate nodes in one after another, gap ms apart (a bullet list, a stack of lines from
        scene.lines()). style is any reveal() style; slides default to a short 40 px rise."""
        nodes = list(nodes)
        if not nodes:
            raise OpenCanvizError("reveal_lines(): give at least one node.")
        if not isinstance(gap, (int, float)) or gap < 0:
            raise OpenCanvizError("reveal_lines(): gap must be ms >= 0.")
        start = self._place(0, offset)
        for i, n in enumerate(nodes):
            at = start + int(round(i * gap))
            if style in TEXT_ENTRANCES:
                self._entrance(n, style, duration, at, None)
            else:
                self.reveal(n, style, duration or 450, at, ease, distance if style.startswith("slideIn") else None)
        self._last_start = start
        return self

    def hide(self, item, style="fadeOut", duration=400, offset=None, ease=None, into=None, distance=None, gap=28):
        """Hide a node (fadeOut, hide, slideOut*), a list of nodes, or undraw an arrow. Arrows and parts of a
        hidden node go with it. Exit presets: "fade", "slide" (out to the right), "shrink" (scales to 0.6 as
        it fades), "absorb" (flies into the node into= and fades: a key reaching its server) and "scatter"
        (a list of letters or nodes blows apart from their center, gap ms apart).

        offset="end" plays the exit at the very end of the step, once its length is known, so the screen is
        not left blank while the caption plays (the checker refuses more than 1 s of dead air)."""
        if offset == "end":
            n0 = len(self.actions)
            self.hide(item, style, duration, self._cursor, ease, into, distance, gap)
            self._end_acts.extend((a, a.get("offsetMs", 0)) for a in self.actions[n0:])
            return self
        if style == "scatter":
            return self._scatter_out(item, None if duration == 400 else duration, offset, gap, distance or 160)
        if style == "fade":
            style = "fadeOut"
        if isinstance(item, (list, tuple)):
            start = self._place(0, offset)
            for n in item:
                self.hide(n, style, duration, start, ease, into, distance)
            self._last_start = start
            return self
        if style in ("shrink", "absorb", "slide") and isinstance(item, Node):
            self._own(item, Node)
            return self._motion_out(item, style, None if duration == 400 else duration, offset, into, distance)
        if isinstance(item, Edge):
            self._own(item, Edge)
            item.events.append((self.index, "undraw"))
            self._action(item._tween(False), duration, offset)
            return self
        self._own(item, Node)
        if style not in VIS_OUT:
            raise OpenCanvizError("hide(%s): style must be one of %s or %s" % (item.id, sorted(VIS_OUT),
                                                                            sorted(MOTION_OUT)))
        item.events.append((self.index, "out"))
        act = {"type": "visibility", "target": {"kind": "node", "id": item.id}, "mode": style}
        if ease:
            act["ease"] = ease
        if distance is not None and style.startswith("slideOut"):
            act["slideDistance"] = distance
        start = self._action(act, duration, offset).get("offsetMs", 0)
        for part in item.parts:
            if isinstance(part, Node):
                last = [e for e in part.events if e[0] <= self.index]
                if last and last[-1][1] in ("out", "remove"):
                    continue      # already gone (walk() fades a key's label before it arrives)
                self.hide(part, style, duration, start, ease, distance=distance)
        self._last_start = start
        return self

    def draw(self, edge, duration=700, offset=None, ease="ease-out"):
        """Draw an arrow in (trim 0 -> 1). Both end nodes must be visible by the end of this step.

        A labeled arrow is drawn by an unlabeled twin line (id <edge>_line); once the line is fully
        drawn, the labeled edge replaces it on one frame (a "step" ease, so the label chip is opaque from
        its first frame and the line never shows through it). openCanviz puts a label at the middle
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
                             "durationMs": LABEL_POP, "offsetMs": done, "ease": "step"})
        self.actions.append({"type": "edgeTween", "target": {"kind": "edge", "id": edge.twin_id},
                             "from": {"trim": 1, "opacity": shown}, "to": {"trim": 1, "opacity": 0},
                             "durationMs": TWIN_FADE, "offsetMs": done, "ease": "step"})
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

    def set(self, item, duration=None, offset=None, **fields):
        """Change fields from this step on. Not opacity/trim. On a node a colour (fill, stroke, color, ...)
        changes in the first 350 ms and x/y/w/h in 600 ms of the step (a transformTween; pass duration= /
        offset= to time it yourself); other numbers tween across the step."""
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
            self._timed_fields(item, fields, duration, offset)
        return self

    def _timed_fields(self, node, fields, duration=None, offset=None, ease="ease-out"):
        """A short transformTween for the colour and geometry fields in fields (merged into one already
        aimed at node in this step), so they do not crawl across the whole step."""
        to = {k: v for k, v in fields.items() if k in TIMED_COLORS | TIMED_GEOM}
        if not to:
            return
        ms = duration if duration is not None else (MOVE_MS if TIMED_GEOM & set(to) else FILL_MS)
        for a in self.actions:
            if a.get("type") == "transformTween" and a["target"]["id"] == node.id and not a.get("from") \
                    and offset is None and not a.get("offsetMs") and a.get("durationMs") == ms:
                a["to"].update(to)
                return
        act = {"type": "transformTween", "target": {"kind": "node", "id": node.id}, "to": to}
        if ease:
            act["ease"] = ease
        if duration is None and offset is None:
            act["durationMs"] = ms
            self.actions.append(act)
            self._tail = max(self._tail, ms)
        else:
            self._action(act, ms, offset)

    def move(self, node, x=None, y=None, w=None, h=None, at=None, duration=None, offset=None, ease="ease-out"):
        """Move/resize a node with a transformTween: 600 ms from the step start by default, or duration= /
        offset= (duration="step" glides across the whole step, e.g. a packet riding a slow arrow)."""
        self._own(node, Node)
        if at is not None:
            x, y, w, h = at
        to = {k: v for k, v in (("x", x), ("y", y), ("w", w), ("h", h)) if v is not None}
        if not to:
            raise OpenCanvizError("move(%s): give x/y/w/h or at=Rect." % node.id)
        self.node_patch.setdefault(node.id, {}).update(to)
        act = {"type": "transformTween", "target": {"kind": "node", "id": node.id}, "to": dict(to)}
        if ease:
            act["ease"] = ease
        if duration == "step":
            self._whole_step(act, offset or 0)
        else:
            self._action(act, MOVE_MS if duration is None else duration, offset)
        return self

    def _whole_step(self, act, start=0):
        """Add act running from start to the end of the step (its duration is filled at compile time)."""
        act["durationMs"] = 1
        if start:
            act["offsetMs"] = start
        self.actions.append(act)

        def hook(snap, t0, sd, adj, a=act, s0=start):
            a["durationMs"] = max(1, int(sd["durationMs"]) - s0)
        self.hooks.append(hook)

    def typewrite(self, node, duration=1200, offset=None, caret=True, hand=False):
        """Type a text node's text in (typeProgress 0 -> 1). caret=False hides the block caret; hand=True has
        a marker hand write it on (no caret). A text typed after the first step stays hidden until then:
        openCanviz draws a half-typed text whole in every step that is not typing it."""
        self._own(node, Node)
        if node.fields.get("kind") != "text":
            raise OpenCanvizError("typewrite(%s): only text nodes can be typed." % node.id)
        if hand:
            node.fields["writeHand"] = True
        if hand or not caret:
            node.fields["hideCaret"] = True
        node.fields["_type_step"] = self.index
        start = self._place(duration, offset)
        if self.index > 0:
            self.node_patch.setdefault(node.id, {})["typeProgress"] = 1
            if not node.events:
                self.reveal(node, "show", 1, start)
        self._action({"type": "transformTween", "target": {"kind": "node", "id": node.id},
                      "from": {"typeProgress": 0}, "to": {"typeProgress": 1}, "ease": "linear"}, duration, start)
        self._last_start = start
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
                # the bar grows over the whole step (openCanviz cannot time chartBars); its value rides it
                self._whole_step({"type": "transformTween", "target": {"kind": "node", "id": t.id},
                                  "to": {"y": m["top"][i]}, "ease": self.easing or "ease"})
                self._count_over_step(t)
        return self

    def extend(self, chart, upto=None):
        """Line chart: draw the line on to point index upto (default: the last point). The new stretch draws
        in about 1.4 s from the step start (an edge drawn along the points, so it is timed, unlike a chart
        series, which openCanviz always grows over the whole step); the dot rides its tip and each note
        fades in as the line reaches its point. The step then holds the last note for 1.5 s."""
        self._after_first("extend", chart)
        m = self._recipe(chart, "line", "extend")
        pts = m["points"]
        upto = len(pts) - 1 if upto is None else upto
        if not m["shown"] < upto < len(pts):
            raise OpenCanvizError("extend(%s): upto must be past the last shown point (%d) and at most %d."
                                  % (chart.id, m["shown"], len(pts) - 1))
        first, m["shown"] = m["shown"], upto
        P = [m["px"](*p) for p in pts[first:upto + 1]]
        cum = [0.0]
        for (x0, y0), (x1, y1) in zip(P, P[1:]):
            cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
        ms = int(min(GROW_MS, max(600, 350 * (len(P) - 1))))
        sc = self.scene
        run = sc.line(P[0], P[-1], chart, color=m["color"], width=m["width"],
                      id="%s_run%d" % (chart.id[len(sc.prefix):], upto))
        if len(P) > 2:
            run.fields.update(lineType="elbowed", cornerRadius=0,
                              waypoints=[{"x": _clean(x), "y": _clean(y)} for x, y in P])
        m.setdefault("runs", []).append(run)
        self.draw(run, duration=ms, offset=0, ease="linear")
        pid = sc.path(P, id="%s_tip%d" % (chart.id[len(sc.prefix):], upto))
        self.follow(m["tip"], pid, duration=ms, offset=0, ease="linear")
        end = ms
        for i, t in sorted(m["notes"].items()):
            if first < i <= upto and not t.meta.get("shown"):
                t.meta["shown"] = True
                at = int(ms * cum[i - first] / (cum[-1] or 1))
                self.reveal(t, duration=300, offset=max(0, at - 150))
                end = max(end, at + 150 + NOTE_HOLD)
            elif i <= first and not t.meta.get("shown"):
                t.meta["shown"] = True
                self.reveal(t, duration=300, offset=0)
        self._tail = max(self._tail, end)
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
        """Array: swap cells i and j; the two values arc past each other in the first 600 ms of the step
        (an algoSwap action). Swap disjoint pairs only within one step; they run together. The arc height
        is fixed by openCanviz (0.8 x cell height, at most 30 px)."""
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
        self.actions.append({"type": "algoSwap", "target": {"kind": "node", "id": array.id}, "indices": [i, j],
                             "durationMs": SWAP_MS, "ease": "ease"})
        self._tail = max(self._tail, SWAP_MS)
        return self

    def _timed(self, node, field, ms=COLOR_MS):
        """Run this step's change to a structure field over ms from the step start, not the whole step."""
        for a in self.actions:
            if a.get("type") == "transformTween" and a["target"]["id"] == node.id and field in a.get("to", {}):
                a["to"][field] = self.node_patch[node.id][field]
                return
        self.actions.append({"type": "transformTween", "target": {"kind": "node", "id": node.id},
                             "to": {field: self.node_patch[node.id][field]}, "durationMs": ms, "ease": "ease-out"})
        self._tail = max(self._tail, ms)

    def color(self, struct, colors=None, edges=None, reset=False):
        """Color parts of a structure from this step on (cleared with None, or all with reset=True):
        array {index: color}, tree / linked list / graph {value: color} (graph edges={(a, b): color}),
        grid {(row, col): color}. The colors change in the first 350 ms of the step (graph edge colors take
        the whole step: openCanviz cannot time them)."""
        self._own(struct, Node)
        kind = struct.fields.get("kind")
        m = struct.meta.get("struct")
        if m is None:
            raise OpenCanvizError("color(%s): use it on a node from scene.array/tree/linked_list/graph/grid()."
                                  % struct.id)
        colors = colors or {}
        if kind == "algo-array":
            if reset:
                m["colors"] = [None] * len(m["colors"])
            for i, c in colors.items():
                m["colors"][i] = c
            # never a null target: openCanviz keeps a cell tweened to null in its old colour for the whole
            # step, so a cleared cell gets the array's own fill and clears as the new colours land
            self._patch(struct, cellColors=_cells(struct, m["colors"]))
            self._timed(struct, "cellColors")
        elif kind == "algo-grid":
            if reset:
                m["colors"] = [[None] * len(r) for r in m["colors"]]
            for (r, c), col in colors.items():
                m["colors"][r][c] = col
            self._patch(struct, gridColors=[_cells(struct, r) for r in m["colors"]])
            self._timed(struct, "gridColors")
        else:
            if reset:
                m["colors"], m["edge_colors"] = {}, {}
            for k, c in colors.items():
                nid = m["ids"].get(str(k))
                if nid is None:
                    raise OpenCanvizError("color(%s): no node %r." % (struct.id, k))
                if c is None:
                    m["colors"].pop(nid, None)
                else:
                    m["colors"][nid] = c
            # every node gets an explicit colour (its plain fill when uncoloured), never a missing or null one
            fill = _fill(struct)
            self._patch(struct, nodeColors={nid: m["colors"].get(nid, fill) for nid in sorted(set(m["ids"].values()))})
            self._timed(struct, "nodeColors")
            if edges:
                for (a, b), c in edges.items():
                    eid = m["edge_ids"].get((str(a), str(b))) or m["edge_ids"].get((str(b), str(a)))
                    if eid is None:
                        raise OpenCanvizError("color(%s): no edge %r-%r." % (struct.id, a, b))
                    m["edge_colors"][eid] = c
                self._patch(struct, edgeColors=dict(m["edge_colors"]))
        return self

    def point(self, pointer, at):
        """Move a pointer: an array index, a tree / list / graph value, or a grid (row, col). On an array or
        grid it glides to the new cell in the first 350 ms of the step."""
        self._own(pointer, Node)
        m = pointer.meta.get("pointer")
        if m is None:
            raise OpenCanvizError("point(%s): use it on a node from scene.pointer()." % pointer.id)
        to = _pointer_target(m["target"], at)
        self._patch(pointer, **to)
        num = {k: v for k, v in to.items() if k in ("pointerTargetIndex", "pointerTargetRow", "pointerTargetCol")}
        if num:
            # without a tween the pointer (and its highlight frame) crawls across the whole step
            self.actions.append({"type": "transformTween", "target": {"kind": "node", "id": pointer.id},
                                 "to": num, "durationMs": POINTER_MS, "ease": "ease-out"})
            self._tail = max(self._tail, POINTER_MS)
        return self

    def bracket(self, array, start, end, label=None, color=None):
        """Array: draw a bracket under cells start..end (inclusive) with a readable label under it."""
        m = self._recipe(array, "array", "bracket")
        th = self.scene.project.colors
        col = color or th["muted"]
        self._patch(array, rangeStart=start, rangeEnd=end, rangeColor=col, rangeLabel="")
        self.actions.append({"type": "transformTween", "target": {"kind": "node", "id": array.id},
                             "to": {"rangeStart": start, "rangeEnd": end, "rangeColor": col}, "durationMs": COLOR_MS,
                             "ease": "ease-out"})
        self._tail = max(self._tail, COLOR_MS)
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
                self._timed_fields(t, {"x": _clean(x0), "w": _clean(x1 - x0), "color": col})
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
        self._timed(code, "highlightedLines")
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
        """Timeline: bring in the next event (or event i): the line grows to it in the first 600 ms of the
        step and its dot, year and text fade in as the line arrives."""
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
        f = timeline.fields
        key, base = ("h", "y") if m["vertical"] else ("w", "x")
        size = max(12, m["pos"][i] - f[base] + 6)
        old = m.get("size", 12)
        m["size"] = size
        if i == 0 or abs(size - old) < 1:
            self.reveal(ev, duration=500, offset=0)
            self._patch(timeline, **{key: size})
            return self
        # the line grows in 600 ms from the step start and the event fades in as the line reaches it
        self._patch(timeline, **{key: size})
        self.actions.append({"type": "transformTween", "target": {"kind": "node", "id": timeline.id},
                             "from": {key: old}, "to": {key: size}, "durationMs": TIMELINE_MS, "ease": "ease-out"})
        self.reveal(ev, duration=300, offset=TIMELINE_MS - 300)
        self._tail = max(self._tail, TIMELINE_MS)
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

    # motion presets -----------------------------------------------------------------------------
    def _cur(self, node, key, default=None):
        """A node's value of key as this step starts (the latest patch from an earlier step or this one)."""
        val = node.fields.get(key, default)
        for st in self.scene.steps[:self.index + 1]:
            p = st.node_patch.get(node.id)
            if p and key in p:
                val = p[key]
        return val

    def _tw(self, node, to, ms, start, ease=None, frm=None, **extra):
        act = {"type": "transformTween", "target": {"kind": "node", "id": node.id}, "to": dict(to)}
        if frm:
            act["from"] = dict(frm)
        if ease:
            act["ease"] = ease
        act.update(extra)
        act["durationMs"] = int(max(1, round(ms)))
        if start:
            act["offsetMs"] = int(round(start))
        self.actions.append(act)
        self._tail = max(self._tail, int(round(start + ms)))
        return act

    def _motion_in(self, node, style, duration, offset, ease, distance):
        """One node in with a motion preset (see MOTION_IN)."""
        self._own(node, Node)
        f = node.fields
        kind = f.get("kind")
        if style == "fade":
            return self.reveal(node, "fadeIn", duration, offset, ease)
        if style == "slide":
            return self.reveal(node, "slideInUp", duration or 500, offset, ease or "ease-out",
                               60 if distance is None else distance)
        if style == "draw":
            if kind == "wedge":
                ms = duration or 800
                start = self._place(ms, offset)
                self.reveal(node, "fadeIn", 60, start)   # not "show": it leaves the node visible before its offset
                a0 = f.get("startAngle", -90)
                self._tw(node, {"endAngle": f.get("endAngle", 270)}, ms, start, ease or "ease-out",
                         frm={"endAngle": a0 + 1})   # a zero sweep can draw a full disc
                self._last_start = start
                return self
            if kind != "svg" or not f.get("svgPaths"):
                raise OpenCanvizError("reveal(%s, \"draw\"): draw is for svg paths (scene.curve/poly/plot curves) "
                                      "and arcs (ring.arc / wedges); draw an arrow with step.draw(edge)." % node.id)
            ms = duration or 900
            start = self._place(ms, offset)
            self.reveal(node, "fadeIn", 60, start)   # not "show": it leaves the node visible before its offset
            f.setdefault("drawProgress", 1)
            self._tw(node, {"drawProgress": 1}, ms, start, ease or "linear", frm={"drawProgress": 0})
            self._last_start = start
            return self
        if style == "wipe":
            ms = duration or (900 if f.get("imageData") else 600)
            start = self._place(ms, offset)
            self.reveal(node, "fadeIn", 60, start)   # not "show": it leaves the node visible before its offset
            if f.get("imageData"):
                f.setdefault("wipeAxis", "x")
                f.setdefault("drawProgress", 1)
                self._tw(node, {"drawProgress": 1}, ms, start, ease or "linear", frm={"drawProgress": 0})
            elif kind == "text":
                raise OpenCanvizError("reveal(%s, \"wipe\"): %s" % (node.id, BROKEN_ENTRANCES["wipe"]))
            else:
                if f.get("rotationZ"):
                    raise OpenCanvizError("reveal(%s, \"wipe\"): the node is turned (rotationZ); a wipe moves its pivot "
                                          "to the left edge, so it would turn about the wrong point. Use \"fade\" or "
                                          "\"zoom\"." % node.id)
                f["pivotX"] = 0
                f.setdefault("scaleX", 1)
                self._tw(node, {"scaleX": 1}, ms, start, ease or "ease-out", frm={"scaleX": 0.01})
            self._last_start = start
            return self
        spec = {"drop": (700, "bounce", 0, -220, None, 150), "rise": (450, "ease-out", 0, 50, None, 400),
                "zoom": (500, "ease-out", 0, 0, 1.6, 300)}[style]
        ms, ez, dx, dy, sc, fade = spec
        ms = duration or ms
        if distance is not None and style in ("drop", "rise"):
            dy = -abs(distance) if style == "drop" else abs(distance)
        start = self._place(ms, offset)
        if sc:
            self.reveal(node, "fadeIn", min(fade, ms), start)
        else:
            # a node that travels while half transparent leaves x264 residue (faint dotted specks) along its
            # path in the exported mp4, so a moving entrance stays hidden for its first 44% and fades in late,
            # over at least 300 ms (a faster fade on a still-moving node left them too, in real renders)
            self.reveal(node, "fadeIn", int(round(max(300, 0.66 * ms))), int(round(start + 0.44 * ms)))
        if sc:
            f.setdefault("scaleX", 1)
            f.setdefault("scaleY", 1)
            self._tw(node, {"scaleX": 1, "scaleY": 1}, ms, start, ease or ez, frm={"scaleX": sc, "scaleY": sc})
        else:
            # isRelative: the tween runs from (home - (dx, dy)) to home, and home stays in the snapshot
            self._tw(node, {}, ms, start, ease or ez, isRelative=True, dx=dx, dy=-dy)
        self._last_start = start
        return self

    def pop(self, nodes, stagger=40, from_="below", duration=500, offset=None, distance=None, ease="back"):
        """Pop nodes in one after another, stagger ms apart: each fades in while it scales up from 0.35
        with a "back" overshoot and travels home from from_: "below" (120 px under), "edges" (out along the
        line from the group's center, so a word bursts outward-in), "scatter" (a fixed pseudo-random spot
        220 px away) or None (scale only). A node that travels fades in a quarter of the way home (a
        see-through mover leaves x264 specks); a plot or number-line point always pops in place. Home stays in the step-0 snapshot (an isRelative tween), so the
        follow camera frames the final layout and it works in a scene's first step."""
        nodes = [nodes] if isinstance(nodes, Node) else list(nodes)
        if not nodes:
            raise OpenCanvizError("pop(): give at least one node.")
        if from_ not in POP_FROM_MODES:
            raise OpenCanvizError("pop(): from_ must be one of %s." % sorted(POP_FROM_MODES, key=str))
        for n in nodes:
            self._own(n, Node)
        cx = sum(n.rect.cx for n in nodes) / len(nodes)
        cy = sum(n.rect.cy for n in nodes) / len(nodes)
        start = self._place(0, offset)
        for i, n in enumerate(nodes):
            at = start + i * stagger
            n.fields.setdefault("scaleX", 1)
            n.fields.setdefault("scaleY", 1)
            d = 120 if distance is None else distance
            if from_ == "below":
                ox, oy = 0, d
            elif from_ == "edges":
                vx, vy = n.rect.cx - cx, n.rect.cy - cy
                ln = math.hypot(vx, vy) or 1.0
                vx, vy = (vx / ln, vy / ln) if ln > 1 else (0, 1)
                ox, oy = vx * d * 1.4, vy * d * 1.4
            elif from_ == "scatter":
                a = (i * 137.508 + 23) * math.pi / 180      # golden-angle spread: varied, repeatable
                r = (220 if distance is None else distance) * (0.75 + 0.5 * ((i * 7919) % 11) / 10.0)
                ox, oy = math.cos(a) * r, math.sin(a) * r
            else:
                ox = oy = 0
            if n.meta.get("on_curve"):
                ox = oy = 0       # a plot point grows in place, on its curve
            extra = {"isRelative": True, "dx": _clean(-ox), "dy": _clean(-oy)} if (ox or oy) else {}
            if extra:
                # travelling while half transparent leaves x264 residue (dotted specks) along the path, so the
                # fade starts a quarter of the way in, when the node is mostly home
                self.reveal(n, "fadeIn", max(1, int(round(0.45 * duration))), int(round(at + 0.25 * duration)))
            else:
                self.reveal(n, "fadeIn", min(200, duration), at)
            self._tw(n, {"scaleX": 1, "scaleY": 1}, duration, at, ease, frm={"scaleX": 0.35, "scaleY": 0.35}, **extra)
        self._cursor = max(self._cursor, start + (len(nodes) - 1) * stagger + duration)
        self._last_start = start
        return self

    def stagger(self, nodes, style="pop", gap=STAGGER_MS, duration=None, offset=None, ease=None):
        """Bring nodes in one after another, gap ms apart, with any reveal() style (a table column, the terms
        of an equation, a row of cards)."""
        nodes = list(nodes)
        if not nodes:
            raise OpenCanvizError("stagger(): give at least one node.")
        start = self._place(0, offset)
        for i, n in enumerate(nodes):
            self.reveal(n, style, duration, start + int(round(i * gap)), ease)
        self._last_start = start
        return self

    def emphasize(self, node, style="pulse", duration=None, offset=None, color=None, scale=1.08, distance=40,
                  part=None):
        """Draw the eye to a node that is already on screen, then leave it as it was. One per beat.
        style: pulse (scale up and back, 440 ms), shake (side to side, 300 ms: an error, a rejection),
        wiggle (a small rotation, 400 ms: playful attention), flash (its fill, or a text's colour, flashes
        to color and back, 800 ms) or nudge (a 40 px push right and back, 500 ms: "this one moves next").
        "glow" is refused: a glow tween is not drawn.
        A pulse always grows the node by at least PULSE_MIN_PX on its short side (scale is raised for a
        small node); a wide, thin node (a table row, a cell, a bar: one side over PULSE_THIN times the
        other) gets a flash instead, since a few px of growth on its short side does not show; so does a
        table cell, a node packed in a row of look-alikes, or a ring arc, which would grow over its
        neighbours. A flash holds to the end of its step (at least FLASH_HOLD_MS), then fades back.
        part= (flash on an equation only) lights up one marked term: write it as \\part{name}{...} in the
        TeX, e.g. scene.math(r"\\frac{\\part{a}{x^2} + 2xh - \\part{b}{x^2}}{h}") and then
        emphasize(eq, "flash", part="a"); a list of names flashes several terms together."""
        if isinstance(node, (list, tuple)):
            start = self._place(0, offset)
            for n in node:
                self.emphasize(n, style, duration, start, color, scale, distance, part)
            self._last_start = start
            return self
        self._own(node, Node)
        if part is not None:
            if style != "flash" or not node.fields.get("imageData"):
                raise OpenCanvizError("emphasize(%s, part=%r): part= works with style=\"flash\" on an equation "
                                      "from scene.math() / math_row() / derivation()." % (node.id, part))
            return self._flash_parts(node, [part] if isinstance(part, str) else list(part), duration, offset, color)
        if style == "pulse":
            w, h = float(node.fields.get("w", 0) or 0), float(node.fields.get("h", 0) or 0)
            short, long_ = min(w, h), max(w, h)
            if short > 0 and long_ / short > PULSE_THIN and not node.fields.get("imageData"):
                style = "flash"
            elif short > 0:
                scale = max(scale, min(PULSE_MAX, 1 + PULSE_MIN_PX / short))
            if style == "pulse" and (node.meta.get("cell") or node.meta.get("ring_arc")
                                     or self._packed(node, max(w, h) * (scale - 1) / 2.0)):
                # a cell in a table or a row (or an arc on a ring) would grow into its neighbours: tint it
                style = "flash"
                if color is None:
                    was = self._cur(node, "fill")
                    if isinstance(was, str) and was.startswith("#") and len(was) == 7:
                        color = _mix(was, "#ffffff" if node.meta.get("ring_arc") else self.scene.project.colors["hi"],
                                     0.45 if node.meta.get("ring_arc") else 0.55)
        if style == "flash" and color is None and node.meta.get("ring_arc"):
            was = self._cur(node, "fill")
            if isinstance(was, str) and was.startswith("#") and len(was) == 7:
                color = _mix(was, "#ffffff", 0.45)     # an arc brightens in its own colour
        if style in BROKEN_EMPHASIS:
            raise OpenCanvizError("emphasize(%s, %r): %s" % (node.id, style, BROKEN_EMPHASIS[style]))
        if style not in EMPHASIS:
            raise OpenCanvizError("emphasize(%s): style must be one of %s." % (node.id, sorted(EMPHASIS)))
        f = node.fields
        total = duration or EMPHASIS[style]
        start = self._place(total, offset)
        if style == "pulse":
            sx, sy = self._cur(node, "scaleX", 1), self._cur(node, "scaleY", 1)
            f.setdefault("scaleX", 1)
            f.setdefault("scaleY", 1)
            half = total / 2.0
            self._tw(node, {"scaleX": _sc(sx * scale), "scaleY": _sc(sy * scale)}, half, start, "ease-out")
            self._tw(node, {"scaleX": sx, "scaleY": sy}, half, start + half, "ease-in")
        elif style == "shake":
            x0 = self._cur(node, "x")
            seq = [12, -12, 9, -9, 5, 0]
            ms = total / float(len(seq))
            for i, d in enumerate(seq):
                self._tw(node, {"x": _clean(x0 + d)}, ms, start + i * ms, "linear")
        elif style == "wiggle":
            r0 = self._cur(node, "rotationZ", 0) or 0
            seq = [6, -6, 4, -4, 0]
            ms = total / float(len(seq))
            for i, d in enumerate(seq):
                self._tw(node, {"rotationZ": _clean(r0 + d)}, ms, start + i * ms, "linear")
        elif style == "flash" and f.get("imageData"):
            # an image (an equation) draws no fill: light a highlighter box up behind it instead
            col = color or self.scene.project.colors["hi"]
            pad = 6
            hl = self.scene.node("rect", None, x=f["x"] - pad, y=f["y"] - pad, w=f["w"] + 2 * pad, h=f["h"] + 2 * pad,
                                 id=node.id + "_hl", fill=(col + "55") if len(col) == 7 else col, stroke="none",
                                 cornerRadius=10, noGlow=True, zIndex=0)
            self.reveal(hl, "fadeIn", int(total * 0.2), start)
            self._hold(lambda at: self.hide(hl, "fadeOut", FLASH_OUT_MS, at), start, total)
        elif style == "flash":
            key = "color" if f.get("kind") == "text" else "fill"
            was = self._cur(node, key)
            if was in (None, "transparent", "none"):
                was = (self.scene.scene_background() + "00") if key == "fill" else self.scene.project.colors["text"]
                if f.get(key) in (None, "transparent", "none"):
                    f[key] = was
            col = color or self.scene.project.colors["hi"]
            if key == "fill" and len(was) == 9 and len(col) == 7:
                col += "88"          # a see-through flash behind an equation or a label
            self._tw(node, {key: col}, total * 0.2, start, "ease-out")
            self._hold(lambda at: self._tw(node, {key: was}, FLASH_OUT_MS, at, "ease-in"), start, total)
        elif style == "nudge":
            x0 = self._cur(node, "x")
            self._tw(node, {"x": _clean(x0 + distance)}, total * 0.36, start, "ease-out")
            self._tw(node, {"x": x0}, total * 0.64, start + total * 0.36, "back")
        self._last_start = start
        return self

    def _flash_parts(self, node, names, duration, offset, color):
        parts = node.meta.get("parts") or {}
        f = node.fields
        total = duration or EMPHASIS["flash"]
        start = self._place(total, offset)
        col = color or self.scene.project.colors["hi"]
        for name in names:
            if name not in parts:
                raise OpenCanvizError("emphasize(%s, part=%r): no such part; its TeX marks %s. Mark a term with "
                                      "\\part{name}{...}." % (node.id, name, sorted(parts) or "none"))
            fx, fy, fw, fh = parts[name]
            pad = 6
            hl = self.scene.node("rect", None, x=f["x"] + fx * f["w"] - pad, y=f["y"] + fy * f["h"] - pad,
                                 w=max(10, fw * f["w"] + 2 * pad), h=max(10, fh * f["h"] + 2 * pad),
                                 id="%s_hl_%s" % (node.id, _slug(name)), fill=(col + "55") if len(col) == 7 else col,
                                 stroke="none", cornerRadius=8, noGlow=True, zIndex=0)
            self.reveal(hl, "fadeIn", int(total * 0.2), start)
            self._hold(lambda at, hl=hl: self.hide(hl, "fadeOut", FLASH_OUT_MS, at), start, total)
        self._last_start = start
        return self

    def _packed(self, node, grow):
        """True when node sits in a row or grid of look-alikes (same kind and size) closer than grow + 4 px,
        so a pulse would paint over the next one."""
        f = node.fields
        r = node.rect
        for n in self.scene.nodes:
            g = n.fields
            if n is node or g.get("kind") != f.get("kind") or abs(g.get("w", 0) - f.get("w", 0)) > 2 \
                    or abs(g.get("h", 0) - f.get("h", 0)) > 2:
                continue
            q = n.rect
            gx = max(q.x - (r.x + r.w), r.x - (q.x + q.w))
            gy = max(q.y - (r.y + r.h), r.y - (q.y + q.h))
            if max(gx, gy) < grow + 4 and min(gx, gy) < 0:
                return True
        return False

    def _hold(self, back, start, total):
        """A flash holds: it goes back (back(offset) adds the actions) at the step's end, and never sooner
        than FLASH_HOLD_MS after it lit up, so the eye has time to land on it. The cursor still moves on
        after the flash's own length, so what follows does not wait for the hold."""
        cur, n0 = self._cursor, len(self.actions)
        back(int(start + FLASH_HOLD_MS))
        self._hold_acts.extend((a, a.get("offsetMs", 0)) for a in self.actions[n0:])
        self._cursor = max(cur, start + total)
        self._tail = max(self._tail, int(start + FLASH_HOLD_MS + FLASH_OUT_MS))
        self._last_start = start

    def pulse(self, node, scale=1.08, offset=None, duration=440):
        """Scale a node up a little and back (two 220 ms tweens): "look here", "this one changed"."""
        return self.emphasize(node, "pulse", duration, offset, scale=scale)

    def tint(self, nodes, color, duration=FILL_MS, offset=None):
        """Recolour nodes from this step on: a text's colour, any other node's fill (a matrix row, the
        visited cells of a table, the winning bar)."""
        nodes = [nodes] if isinstance(nodes, Node) else list(nodes)
        start = self._place(duration, offset)
        for n in nodes:
            key = "color" if n.fields.get("kind") == "text" else "fill"
            self.set(n, duration=duration, offset=start, **{key: color})
        self._last_start = start
        return self

    def _exit_reset(self, node, start, to):
        """After a node has faded out, put the fields an exit moved back (1 ms, unseen) so the snapshot is
        unchanged and a later reveal shows it as it was."""
        self._tw(node, to, 1, start, "step")

    def _motion_out(self, node, style, duration, offset, into, distance):
        f = node.fields
        if style == "shrink":
            ms = duration or 400
            start = self._place(ms, offset)
            sx, sy = self._cur(node, "scaleX", 1), self._cur(node, "scaleY", 1)
            f.setdefault("scaleX", 1)
            f.setdefault("scaleY", 1)
            self.hide(node, "fadeOut", ms, start)
            self._tw(node, {"scaleX": _sc(sx * 0.6), "scaleY": _sc(sy * 0.6)}, ms, start, "ease-in")
            self._exit_reset(node, start + ms, {"scaleX": sx, "scaleY": sy})
        elif style == "absorb":
            if not isinstance(into, Node):
                raise OpenCanvizError("hide(%s, \"absorb\"): pass into=<node> it is absorbed into." % node.id)
            ms = duration or 500
            start = self._place(ms + 200, offset)
            x0, y0 = self._cur(node, "x"), self._cur(node, "y")
            sx, sy = self._cur(node, "scaleX", 1), self._cur(node, "scaleY", 1)
            f.setdefault("scaleX", 1)
            f.setdefault("scaleY", 1)
            tx = self._cur(into, "x") + into.fields["w"] / 2.0 - f["w"] / 2.0
            ty = self._cur(into, "y") + into.fields["h"] / 2.0 - f["h"] / 2.0
            self._tw(node, {"x": _clean(tx), "y": _clean(ty), "scaleX": _sc(sx * 0.4), "scaleY": _sc(sy * 0.4)},
                     ms, start, "ease-in")
            self.hide(node, "fadeOut", 200, start + ms - 80)
            self._exit_reset(node, start + ms + 130, {"x": x0, "y": y0, "scaleX": sx, "scaleY": sy})
        elif style == "slide":
            self.hide(node, "slideOutRight", duration or 400, offset, "ease-in", distance or 120)
        return self

    def _scatter_out(self, nodes, duration, offset, gap, distance):
        nodes = [nodes] if isinstance(nodes, Node) else list(nodes)
        ms = duration or 380
        cx = sum(n.rect.cx for n in nodes) / len(nodes)
        cy = sum(n.rect.cy for n in nodes) / len(nodes)
        start = self._place(0, offset)
        for i, n in enumerate(nodes):
            self._own(n, Node)
            at = start + i * gap
            x0, y0 = self._cur(n, "x"), self._cur(n, "y")
            vx, vy = n.rect.cx - cx, n.rect.cy - cy
            a = math.atan2(vy, vx) if math.hypot(vx, vy) > 1 else (i * 137.508) * math.pi / 180
            a += ((i * 7919) % 7 - 3) * 0.12
            r = distance * (0.8 + 0.4 * ((i * 31) % 5) / 4.0)
            n.fields.setdefault("scaleX", 1)
            n.fields.setdefault("scaleY", 1)
            self.hide(n, "fadeOut", ms, at)
            self._tw(n, {"x": _clean(x0 + math.cos(a) * r), "y": _clean(y0 + math.sin(a) * r), "scaleX": 0.3,
                         "scaleY": 0.3}, ms, at, "ease-in")
            self._exit_reset(n, at + ms, {"x": x0, "y": y0, "scaleX": 1, "scaleY": 1})
        self._cursor = max(self._cursor, start + (len(nodes) - 1) * gap + ms + 1)
        self._last_start = start
        return self

    def stream(self, edge, n=3, gap_ms=220, duration=900, offset=None, color=None, size=28):
        """Send n dots down a drawn arrow, gap_ms apart (a stream of requests, a flow of data). Each dot
        fades in and out at the ends of the line."""
        self._own(edge, Edge)
        col = color or self.scene.project.colors["hi"]
        start = self._place(duration + (n - 1) * gap_ms, offset)
        for i in range(n):
            sid = self.scene._id(edge.id + "_dot")
            act = {"type": "pathAnimate", "id": sid, "target": {"kind": "edge", "id": edge.id}, "scale": 1,
                   "opacity": 1, "fadeIn": True, "fadeOut": True, "rotateWithPath": False, "ease": "linear",
                   "nodeSnapshot": {"id": sid, "kind": "circle", "w": size, "h": size, "fill": col,
                                    "stroke": "none"},
                   "durationMs": duration}
            if start + i * gap_ms:
                act["offsetMs"] = int(start + i * gap_ms)
            self.actions.append(act)
        self._last_start = start
        return self

    def walk(self, node, ring, to_angle, duration=1200, offset=None, absorb_into=None, ease="linear"):
        """Move a node clockwise around ring (from scene.ring()) from where it sits to to_angle (degrees,
        0 = straight up, clockwise), hop by hop along the circle. absorb_into=<node> then shrinks it into
        that node and fades it out (a key reaching its server)."""
        self._own(node, Node)
        if not isinstance(ring, Ring):
            raise OpenCanvizError("walk(%s): ring must come from scene.ring()." % node.id)
        a0 = node.meta.get("ring_angle")
        if a0 is None:
            raise OpenCanvizError("walk(%s): place the node on the ring first (ring.place(node, angle))." % node.id)
        a1 = float(to_angle)
        while a1 < a0 - 1e-6:
            a1 += 360
        hops = max(2, int(math.ceil((a1 - a0) / 12.0)))
        start = self._place(duration, offset)
        ms = duration / float(hops)
        movers = [(node, ring.r)] + [(p, p.meta["ring_out"]) for p in node.parts if "ring_out" in p.meta]
        node.meta["ring_walker"] = True

        def at(a, rad):
            t = math.radians(a)
            return ring.cx + rad * math.sin(t), ring.cy - rad * math.cos(t)
        for m, rad in movers:
            f = m.fields
            for i in range(1, hops + 1):
                px, py = at(a0 + (a1 - a0) * i / float(hops), rad)
                self._tw(m, {"x": _clean(px - f["w"] / 2.0), "y": _clean(py - f["h"] / 2.0)}, ms,
                         start + (i - 1) * ms, ease)
            px, py = at(a1, rad)
            self._patch(m, x=_clean(px - f["w"] / 2.0), y=_clean(py - f["h"] / 2.0))
        node.meta["ring_angle"] = a1 % 360
        # its label would run into the label of the dot it walks to: fade it out before it gets there
        near = [d for ang, _, d in ring._dots if d is not node and d is not absorb_into
                and abs(((ang - a1 + 180) % 360) - 180) < 30 and any("ring_out" in q.meta for q in d.parts)]
        if absorb_into is not None or near:
            span = a1 - a0
            for p, _ in movers[1:]:
                clear = 30.0
                done = start + duration * max(0.0, (span - clear) / span) if span > 0 else start
                fade = min(300, max(120, done - start))
                self.hide(p, "fadeOut", int(fade), int(max(start, done - fade)))
        if absorb_into is not None:
            # it slides in under the server: a small dot fading out on top leaves an encoder smudge
            nodes = self.scene.nodes
            if nodes.index(node) > nodes.index(absorb_into):
                nodes.remove(node)
                nodes.insert(nodes.index(absorb_into), node)
            self._motion_out(node, "absorb", None, start + duration, absorb_into, None)
        self._last_start = start
        return self

    def ride(self, node, plot, fn, x0, x1, duration=2400, offset=None, tangent=None, hops=24):
        """Move a dot along a curve of plot from x0 to x1 (plot coordinates). tangent=<node from
        plot.tangent()> moves a tangent line with it, turned to the curve's slope at every hop."""
        self._own(node, Node)
        start = self._place(duration, offset)
        ms = duration / float(hops)
        f = node.fields
        for i in range(1, hops + 1):
            xv = x0 + (x1 - x0) * i / float(hops)
            px, py = plot.to_px(xv, fn(xv))
            to = {"x": _clean(px - f["w"] / 2.0), "y": _clean(py - f["h"] / 2.0)}
            self._tw(node, to, ms, start + (i - 1) * ms, "linear")
            if i == hops:
                self._patch(node, **to)
            if tangent is not None:
                tf = tangent.fields
                rot = plot.slope_deg(fn, xv)
                tt = {"x": _clean(px - tf["w"] / 2.0), "y": _clean(py - tf["h"] / 2.0), "rotationZ": rot}
                self._tw(tangent, tt, ms, start + (i - 1) * ms, "linear")
                if i == hops:
                    self._patch(tangent, **tt)
        self._last_start = start
        return self

    def crossfade(self, a, b, duration=500, offset=None):
        """Fade node a out while b fades in on the same spot (a curve morphing into the next one, a
        parameter sweep frame by frame, an equation turning into its simplified form)."""
        start = self._place(duration, offset)
        self.hide(a, "fadeOut", duration, start)
        self.reveal(b, "fadeIn", duration, start)
        self._last_start = start
        return self


class Scene:
    """A scene: add nodes and arrows, then steps. Node ids are prefixed with s<N>_."""

    def __init__(self, project, index, name, transition, background):
        self.project, self.index, self.name = project, index, name
        self.prefix = "s%d_" % (index + 1)
        self.transition, self.background = transition, background
        self.nodes, self.edges, self.steps, self._ids = [], [], [], set()
        self._rings = []
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

    def node(self, kind, label=None, at=None, x=None, y=None, w=None, h=None, id=None, morph_key=None, **fields):
        """Any node kind from schema.json (rect, circle, diamond, cylinder, star, callout, ...).
        morph_key pairs this node with the node of the same key in the next or previous scene for a
        "morph" scene transition (box() and text() pass it through too)."""
        if morph_key is not None:
            if not isinstance(morph_key, str) or not morph_key:
                raise OpenCanvizError("morph_key must be a non-empty string.")
            fields["morphKey"] = morph_key
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

    def lines(self, texts, at, fontSize=None, gap=None, **kw):
        """One text node per line, stacked in at (a Rect) with a shared font size, for reveal_lines():
        each line can then come in on its own. Returns the list of nodes."""
        texts = [str(t) for t in texts]
        if not texts:
            raise OpenCanvizError("lines(): give at least one line.")
        n = len(texts)
        gap = (at.h * 0.06 / max(1, n - 1)) if gap is None else gap
        rows = at.stack(n, gap=gap) if n > 1 else [at]
        if fontSize is None:
            sizes = [fit_font(t, self.project.base_font * 1.5, r.w, r.h, "text", _is_bold(kw.get("fontWeight")))
                     for t, r in zip(texts, rows)]
            if None in sizes:
                raise OpenCanvizError("lines(): a line does not fit its %gx%g row even at 14 px; give the lines "
                                      "more room or fewer words." % (rows[0].w, rows[0].h))
            fontSize = min(sizes)
        return [self.text(t, at=r, fontSize=fontSize, **kw) for t, r in zip(texts, rows)]

    def title(self, text, h=110, **kw):
        """The scene's title across the top of the safe area. Returns (title node, body Rect under it).
        Reveal the title in the first step. With the follow camera the title stays put on screen and the
        content is centered under it."""
        band, body = self.project.area().cut_top(h)
        n = self.text(text, at=band, fontWeight=700, **kw)
        n.meta["title"] = True
        return n, body

    def _is_title(self, n, A):
        """A title: made by scene.title(), or bold text across most of the top of the frame."""
        f = n.fields
        if n.meta.get("title"):
            return True
        return f.get("kind") == "text" and _is_bold(f.get("fontWeight")) and f.get("w", 0) >= 0.6 * A.w and \
            f.get("y", 1e9) <= A.y + 0.15 * A.h and f.get("h", 1e9) <= max(200, 0.25 * A.h) and not n.parts

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
                lx0 = max(A.x, -self.project.width / 2.0 + LABEL_EDGE)
                lx1 = min(A.x + A.w, self.project.width / 2.0 - LABEL_EDGE)
                inside = lx0 - 1 <= cx - lw / 2 and cx + lw / 2 <= lx1 + 1 and \
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
        when the line reaches it. A dot marks the line's current end. Reveal the chart, then
        step.extend(chart, upto) one or more times."""
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
        # a dot on the line's current end, so a chart showing one point is not empty axes; it rides the
        # tip of the line as extend() draws it on (both tween over the step with the step's easing)
        D = 26 if not self._portrait else 34
        X0, Y0 = px(*points[0])
        dot = self.node("circle", None, x=X0 - D / 2.0, y=Y0 - D / 2.0, w=D, h=D, id=id + "_tip", fill=col,
                        stroke=self.scene_background(), strokeWidth=4, noGlow=True)
        chart.parts.append(dot)
        m["tip"], m["px"], m["tip_d"] = dot, px, D
        m["width"] = 6 if not self._portrait else 7
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
                         cellColors=[th["fill"]] * n, cellFontSize=fs, cellShowIndices=False, fill=th["fill"],
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
        node.fields["nodeColors"] = {nid: _fill(node) for nid in sorted(set(ids.values()))}
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
        node.fields["nodeColors"] = {nid: _fill(node) for nid in sorted(set(m["ids"].values()))}
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
        node.fields["nodeColors"] = {nid: _fill(node) for nid in sorted(set(ids.values()))}
        return node

    def grid(self, rows, at, font=None, id="grid"):
        """A table of cells (dynamic programming, a matrix, a board). rows = [[v, ...], ...]."""
        vals = [[str(v) for v in r] for r in rows]
        nr, nc = len(vals), max(len(r) for r in vals)
        fs = font or int(max(20, min(44, at.h / nr * 0.45, at.w / nc * 0.35)))
        node = self.node("algo-grid", None, at=at, id=id, gridValues=[list(r) for r in vals],
                         gridColors=[[self.project.colors["fill"]] * nc for _ in vals], gridCellFontSize=fs,
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
                cy = at.y + min(40, max(0, (at.h - block) / 2.0)) + half + D / 2.0 + 12
            else:
                block = yh + 14 + D + 20 + body_h
                cy = at.y + min(40, max(0, (at.h - block) / 2.0)) + yh + 14 + D / 2.0
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

    # kinetic type, rings, tables, bars ----------------------------------------------------------
    def letters(self, word, at=None, cx=None, cy=None, size=120, color=None, fontWeight=800, id="ltr"):
        """One text node per letter of word (spaces leave a gap), spaced by measured letter widths and
        centered in at (or on cx, cy), for a kinetic title: step.pop(letters, stagger=45, from_="scatter")
        brings it in letter by letter and step.hide(letters, style="scatter") blows it apart."""
        if at is not None:
            cx, cy = at.cx, at.cy
        if cx is None or cy is None:
            raise OpenCanvizError("letters(): give at=Rect or cx, cy.")
        word = str(word)
        if not word.strip():
            raise OpenCanvizError("letters(): give a word.")
        adv = [_advance(ch) * size for ch in word]
        total = sum(adv)
        x = cx - total / 2.0
        out = []
        for ch, a in zip(word, adv):
            if ch != " ":
                bw = max(size * 0.9, a * 1.6)   # wider than the glyph: neighbours may overlap, letters do not clip
                out.append(self.text(ch, x=x + a / 2.0 - bw / 2.0, y=cy - size * 0.75, w=bw, h=size * 1.5,
                                     fontSize=size, fontWeight=fontWeight, color=color or self.project.colors["text"],
                                     id="%s_%s" % (id, _slug(ch) if ch.isalnum() else "c"), noGlow=True))
            x += a
        return out

    def ring(self, center=None, r=300, color=None, width=6, id="ring"):
        """A circle to place things on (a hash ring, a clock, a cycle). Angles are degrees, 0 = straight
        up, increasing clockwise. Returns a Ring: ring.node (the circle), ring.point(angle),
        ring.place(node, angle), ring.dot(angle, ...) and ring.arc(a0, a1, ...)."""
        if center is None:
            center = self.project.safe_center()
        ring = Ring(self, center, r, color, width, id)
        self._rings.append(ring)
        return ring

    def table(self, rows, at, header=True, colors=None, font=None, gap=6, id="tbl"):
        """A grid of labelled cells. rows = [[cell, ...], ...]; header=True makes row 0 bold on the accent
        colour. colors = {(r, c): "#hex"} or a list of lists (None keeps the plain fill). Returns a Table:
        table.cells[r][c], table.row(r), table.column(c). Reveal it column by column with
        step.stagger(table.column(c), "pop", gap=60), recolour cells with step.tint(...)."""
        return Table(self, rows, at, header, colors, font, gap, id)

    def compare_bars(self, items, at, unit="", font=None, id="cmp"):
        """A long and a short bar (or more), each with a big number at its end: "7 minutes" vs "40
        seconds". items = [(label, value, color), ...]. Returns a CompareBars: .labels, .bars, .numbers.
        Reveal each with step.reveal(label), step.reveal(bar, style="wipe"), step.reveal(num, style="pop")."""
        return CompareBars(self, items, at, unit, font, id)

    # math and graphs ---------------------------------------------------------------------------
    def math(self, tex, at=None, x=None, y=None, size=None, color=None, align="center", id="math"):
        """A LaTeX formula, compiled here to an SVG image (node + mathjax-full: scripts/tex2svg.js) and
        sized so its letters are about size px tall. at=Rect centers it there (align="left" puts it on the
        left edge); x, y put its top-left corner. Reveal it with style "wipe" (left to right), a fade, or
        build it term by term with math_row()."""
        size = size or max(64, self._floor("math"))
        res = _tex2svg([(tex, color or self.project.colors["text"])])[0]
        return self._math_node(tex, res, at, x, y, size, align, id)

    def _math_node(self, tex, res, at, x, y, size, align, id):
        floor = self._floor("math")
        if size < floor:
            raise OpenCanvizError("math(%r): size=%g is below the %d px floor for equations in this frame (56 "
                                  "landscape, 78 portrait); a smaller equation is unreadable on a phone. Raise size= "
                                  "and give it the room (split a long line into a derivation)." % (tex, size, floor))
        k = size * MATH_EX
        w, h = max(10.0, res["widthEx"] * k), max(10.0, res["heightEx"] * k)
        if at is not None:
            if w > at.w + 1 or h > at.h + 1:
                raise OpenCanvizError("math(%r): at size %g it is %dx%d px, larger than its %dx%d box; lower size= "
                                      "or give it more room." % (tex, size, w, h, at.w, at.h))
            x = at.x if align == "left" else (at.x + at.w - w if align == "right" else at.cx - w / 2.0)
            y = at.cy - h / 2.0
        if x is None or y is None:
            raise OpenCanvizError("math(%r): give at=Rect or x, y." % tex)
        url = "data:image/svg+xml;base64," + base64.b64encode(res["svg"].encode("utf-8")).decode("ascii")
        n = self.node("rect", None, x=x, y=y, w=w, h=h, id=id, imageData=url, mathTex=_tex_parts(tex), fill="transparent",
                      stroke="none", noGlow=True)
        n.meta["math"] = {"k": k, "heightEx": res["heightEx"], "depthEx": res["depthEx"]}
        n.meta["parts"] = dict(res.get("parts") or {})
        return n

    def math_row(self, terms, x=None, baseline=None, at=None, size=None, color=None, gap=None, colors=None, id="term"):
        """Several LaTeX terms side by side on one baseline (each its own node), for an equation that is
        built term by term: step.stagger(row, "fade", gap=300). at=Rect centers the row there. colors =
        one colour per term (None = the text colour). Returns the list of term nodes."""
        terms = list(terms)
        if not terms:
            raise OpenCanvizError("math_row(): give at least one term.")
        size = size or max(64, self._floor("math"))
        cols = list(colors or [None] * len(terms))
        res = _tex2svg([(t, c or color or self.project.colors["text"]) for t, c in zip(terms, cols)])
        k = size * MATH_EX
        g = size * 0.25 if gap is None else gap
        widths = [max(10.0, r["widthEx"] * k) for r in res]
        total = sum(widths) + g * (len(terms) - 1)
        asc = max((r["heightEx"] - r["depthEx"]) * k for r in res)
        desc = max(r["depthEx"] * k for r in res)
        if at is not None:
            if total > at.w + 1:
                raise OpenCanvizError("math_row(): the row is %d px wide, its box %d; lower size=." % (total, at.w))
            x = at.cx - total / 2.0
            baseline = at.cy - (asc + desc) / 2.0 + asc
        if x is None or baseline is None:
            raise OpenCanvizError("math_row(): give at=Rect or x and baseline.")
        out = []
        for t, r, w in zip(terms, res, widths):
            top = baseline - (r["heightEx"] - r["depthEx"]) * k
            out.append(self._math_node(t, r, None, x, top, size, "left", id))
            x += w + g
        return out

    def derivation(self, lines, at, size=None, gap=None, align="left", color=None, id="line"):
        """A derivation: one LaTeX line per step, stacked top to bottom in at. A line is a string, or a
        list of terms (math_row) so a changed term can be flashed with step.emphasize(term, "flash").
        Returns one entry per line: a node, or the list of term nodes. Reveal line i in its own step with
        style "wipe" (or stagger its terms). align="eq" lines the lines up on the end of their first term
        (write each line as [r"f'(x) =", r"..."] so the equals signs stack) and centers the block;
        "left" and "center" align whole lines."""
        if align not in ("left", "center", "eq"):
            raise OpenCanvizError("derivation(): align must be \"left\", \"center\" or \"eq\".")
        lines = list(lines)
        if not lines:
            raise OpenCanvizError("derivation(): give at least one line.")
        size = size or self._floor("math")
        k = size * MATH_EX
        g = size * 0.5 if gap is None else gap
        flat = [(i, t) for i, ln in enumerate(lines) for t in ([ln] if isinstance(ln, str) else ln)]
        res = _tex2svg([(t, color or self.project.colors["text"]) for _, t in flat])
        per = {}
        for (i, t), r in zip(flat, res):
            per.setdefault(i, []).append((t, r))
        heights = [max(r["heightEx"] for _, r in per[i]) * k for i in range(len(lines))]
        need = sum(heights) + g * (len(lines) - 1)
        if need > at.h + 1:
            raise OpenCanvizError("derivation(): %d lines need %d px, the box is %d px; lower size= or gap=."
                                  % (len(lines), need, at.h))
        y = at.y + (at.h - need) / 2.0
        gp = size * 0.25
        wid = lambda r: max(10.0, r["widthEx"] * k)   # noqa: E731
        lhs = [wid(per[i][0][1]) for i in range(len(lines))]
        rhs = [sum(wid(r) for _, r in per[i][1:]) + gp * (len(per[i]) - 1) for i in range(len(lines))]
        col, block = max(lhs), max(lhs) + max(rhs)
        out = []
        for i, ln in enumerate(lines):
            terms = per[i]
            widths = [wid(r) for _, r in terms]
            total = sum(widths) + gp * (len(terms) - 1)
            if total > at.w + 1 or (align == "eq" and block > at.w + 1):
                raise OpenCanvizError("derivation(): line %d is %d px wide, the box %d; lower size=."
                                      % (i, max(total, block if align == "eq" else 0), at.w))
            if align == "eq":
                x = at.cx - block / 2.0 + col - lhs[i]
            else:
                x = at.x if align == "left" else at.cx - total / 2.0
            asc = max((r["heightEx"] - r["depthEx"]) * k for _, r in terms)
            base = y + asc + (heights[i] - max(r["heightEx"] * k for _, r in terms)) / 2.0
            nodes = []
            for (t, r), w in zip(terms, widths):
                top = base - (r["heightEx"] - r["depthEx"]) * k
                nodes.append(self._math_node(t, r, None, x, top, size, "left", "%s%d" % (id, i)))
                x += w + gp
            out.append(nodes[0] if isinstance(ln, str) else nodes)
            y += heights[i] + g
        return out

    def plot(self, at, x_range, y_range, x_ticks=None, y_ticks=None, grid=False, font=None, color=None,
             x_label=None, y_label=None, id="plot"):
        """A coordinate plane in at: axes (through 0 when 0 is in range, else along the edge), ticks with
        labels and an optional grid, all one svg node plus its tick texts. Returns a Plot:
        plot.curve(fn), plot.area(fn, a, b), plot.point(x, y), plot.vector(x0, y0, x1, y1),
        plot.tangent(fn, x), plot.legend([...]), plot.to_px(x, y)."""
        return Plot(self, at, x_range, y_range, x_ticks, y_ticks, grid, font, color, x_label, y_label, id)

    def number_line(self, at, lo, hi, step=1, font=None, color=None, id="nline"):
        """A number line across at with a tick and a label every step. Returns a NumberLine:
        nl.to_px(v) and nl.point(v, ...) (a dot on the line)."""
        return NumberLine(self, at, lo, hi, step, font, color, id)

    def poly(self, points, closed=True, color=None, fill="none", width=4, id="poly"):
        """A polyline or polygon through world points (a triangle, a vector, a path) as one svg node.
        Reveal it with style "draw" to draw it on."""
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        pad = width + 2
        x0, y0 = min(xs) - pad, min(ys) - pad
        w, h = max(10.0, max(xs) - min(xs) + 2 * pad), max(10.0, max(ys) - min(ys) + 2 * pad)
        d = "M " + " L ".join("%s %s" % (_clean(px - x0), _clean(py - y0)) for px, py in points) + (" Z" if closed else "")
        return self.svg_path([{"d": d, "stroke": color or self.project.colors["accent"], "strokeWidth": width,
                               "fill": fill}], x0, y0, w, h, id)

    def svg_path(self, paths, x, y, w, h, id="path"):
        """An svg node drawing paths [{d, stroke, strokeWidth, fill}] in its own px (viewBox = its size)."""
        return self.node("svg", None, x=x, y=y, w=w, h=h, id=id, svgStretch=True,
                         svgViewBox={"x": 0, "y": 0, "w": _clean(w), "h": _clean(h)}, svgPaths=paths)

    def angle_mark(self, vertex, p1, p2, r=60, color=None, label=None, font=None, id="angle"):
        """Mark the angle at vertex between the rays to p1 and p2 (world points) with a filled wedge of
        radius r, and an optional label on its bisector. Returns the wedge (the label is its part)."""
        vx, vy = vertex
        a1 = math.degrees(math.atan2(p1[1] - vy, p1[0] - vx))
        a2 = math.degrees(math.atan2(p2[1] - vy, p2[0] - vx))
        sweep = (a2 - a1) % 360
        if sweep > 180:
            a1, a2, sweep = a2, a1, 360 - sweep
        col = color or self.project.colors["hi"]
        wdg = self.node("wedge", None, x=vx - r, y=vy - r, w=2 * r, h=2 * r, id=id, startAngle=_clean(a1),
                        endAngle=_clean(a1 + sweep), fill=col + "aa" if len(col) == 7 else col, stroke="none", noGlow=True)
        if label:
            mid = math.radians(a1 + sweep / 2.0)
            fs = font or self._floor("body")
            lx, ly = vx + math.cos(mid) * r * 1.6, vy + math.sin(mid) * r * 1.6
            bw = max(60, len(label) * fs * 0.6 + 16)
            wdg.parts.append(self.text(label, x=lx - bw / 2.0, y=ly - _tline(fs) / 2.0, w=bw, h=_tline(fs), fontSize=fs,
                                       color=col, id=id + "_lbl"))
        return wdg

    def side_label(self, p1, p2, text, offset=34, font=None, color=None, id="side"):
        """A label beside the segment p1-p2 (a triangle's side length), offset px along its normal
        (positive = to the left of the direction p1 -> p2)."""
        mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = dy / ln, -dx / ln
        fs = font or self._floor("body")
        bw = max(60, len(str(text)) * fs * 0.6 + 16)
        cx, cy = mx + nx * offset, my + ny * offset
        return self.text(str(text), x=cx - bw / 2.0, y=cy - _tline(fs) / 2.0, w=bw, h=_tline(fs), fontSize=fs,
                         color=color or self.project.colors["muted"], id=id)

    def matrix(self, rows, at, font=None, color=None, id="mat"):
        """A matrix: text cells between square brackets. Returns a Matrix: m.cells[r][c], m.row(r),
        m.column(c), m.node (the brackets; its parts are the cells). Highlight a row or column with
        step.tint(m.row(1), "#f59e0b") or step.emphasize(m.column(0), "pulse")."""
        return Matrix(self, rows, at, font, color, id)

    def venn(self, labels, at, colors=None, font=None, id="venn"):
        """Two or three see-through circles that overlap (an alpha fill, no glow), each with its label.
        Returns the list of circles; each circle's label is its part."""
        labels = list(labels)
        if len(labels) not in (2, 3):
            raise OpenCanvizError("venn(): give 2 or 3 labels.")
        cols = colors or PALETTE[:len(labels)]
        n = len(labels)
        d = min(at.w / (1.7 if n == 2 else 1.75), at.h / (1.0 if n == 2 else 1.7))
        r = d / 2.0
        if n == 2:
            centers = [(at.cx - r * 0.7, at.cy), (at.cx + r * 0.7, at.cy)]
        else:
            centers = [(at.cx - r * 0.75, at.cy - r * 0.35), (at.cx + r * 0.75, at.cy - r * 0.35),
                       (at.cx, at.cy + r * 0.85 - r * 0.35)]
        fs = font or self._floor("body")
        out = []
        for i, (lab, (cx, cy)) in enumerate(zip(labels, centers)):
            c = self.node("circle", None, x=cx - r, y=cy - r, w=d, h=d, id="%s_%s" % (id, _slug(lab)), fill=_alpha(cols[i], "77"),
                          stroke=cols[i], strokeWidth=4, noGlow=True)   # alpha fill: a fadeIn ends at opacity 1
            ox = {0: -0.45, 1: 0.45, 2: 0}[i] if n == 3 else (-0.45 if i == 0 else 0.45)
            oy = {0: -0.35, 1: -0.35, 2: 0.5}[i] if n == 3 else 0
            bw = r * 0.9
            c.parts.append(self.text(str(lab), x=cx + ox * r - bw / 2.0, y=cy + oy * r - _tline(fs) / 2.0, w=bw,
                                     h=_tline(fs), fontSize=fs, fontWeight=700, id="%s_lbl%d" % (id, i)))
            out.append(c)
        return out

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
        if CAPTION_DECIMAL.search(str(caption)):
            raise OpenCanvizError("scene %d step %d: the caption %r has a decimal number; the caption card splits "
                                  "\"7.1 minutes\" at the point. Round it or say it in words (\"about 7 minutes\")."
                                  % (self.index + 1, len(self.steps), caption))
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

    def _tangent_after_dot(self, st, k, vis):
        # a tangent line drawn before its dot reads as a stray bar: start it with the dot or later
        for n in self.nodes:
            dot = n.meta.get("tangent_dot")
            if dot is None:
                continue
            t0 = _in_start(st, n.id)
            if t0 is None:
                continue
            d0 = _in_start(st, dot.id)
            if d0 is None:
                if not (vis[dot.id][k - 1] if k > 0 else getattr(dot, "initial_visible", True)):
                    raise OpenCanvizError("scene %d step %d: tangent %s is revealed but its dot %s is hidden. Reveal "
                                          "the dot first (or in the same step)." % (self.index + 1, k, n.id, dot.id))
                continue
            if t0 >= d0:
                continue
            by = d0 - t0
            for a in st.actions:
                if a.get("target", {}).get("id") == n.id and a.get("offsetMs", 0) >= t0:
                    a["offsetMs"] = int(a.get("offsetMs", 0) + by)
                    st._cursor = max(st._cursor, a["offsetMs"] + (a.get("durationMs") or 0))

    def _compile(self):
        if not self.steps:
            raise OpenCanvizError("scene %d (%s) has no steps; add at least one with scene.step(caption)."
                                  % (self.index + 1, self.name))
        self._size_variables()
        for e in self.edges:
            if e.around:
                self._route_around(e)
        vis, evis = self._timelines()
        for ring in self._rings:
            ring._retrim(vis)
        snap_nodes = []
        for z, n in enumerate(self.nodes):
            f = {k: v for k, v in n.fields.items() if not k.startswith("_") or k == "_animatedProps"}
            f.setdefault("zIndex", z + 1)      # explicit: later nodes draw on top, in every renderer
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
            self._tangent_after_dot(st, k, vis)
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
            if st._end_acts:
                last = max(off + (a.get("durationMs") or 0) for a, off in st._end_acts)
                shift = max(0, dur - END_PAD_MS - last)
                for a, off in st._end_acts:
                    if off + shift:
                        a["offsetMs"] = int(off + shift)
            for a, off in st._hold_acts:
                a["offsetMs"] = int(off + max(0, dur - END_PAD_MS - off - (a.get("durationMs") or 0)))
            # openCanviz times algoSwap and algo-field tweens only when the step names its easing;
            # without it a swap snaps and a colour change takes the whole step
            sd["easing"] = st.easing or "ease"
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
            # The renderer reads a scene's own colour only when the scene also carries a
            # `bg` spec; {"kind": "solid"} paints that colour as the scene's ground.
            scene["background"] = self.background
            scene["bg"] = {"kind": "solid"}
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
        # titles stay fixed on screen: each pan moves them with the camera, and the content is centered
        # in the safe area under them
        titles = {n.id: (n.fields["x"], n.fields["y"], n.fields["y"] + n.fields["h"]) for n in self.nodes
                  if self._is_title(n, A)}
        tpos = {tid: (t[0], t[1]) for tid, t in titles.items()}
        # under a title the camera frames the scene's whole body layout from the first step when it fits,
        # so items appear in their final places and nothing shifts as the scene builds
        union = None
        if titles:
            un, ue = {}, {}
            for k, sd in enumerate(steps):
                if k == 0:
                    un = {n["id"]: dict(n) for n in sd["nodes"]}
                    ue = {e["id"]: dict(e) for e in sd["edges"]}
                else:
                    for p in sd["nodes"]:
                        un.setdefault(p["id"], {}).update(p)
                    for p in sd["edges"]:
                        ue.setdefault(p["id"], {}).update(p)
                bb = _visible_bbox({i: n for i, n in un.items() if i not in titles}, ue)
                if bb:
                    union = bb if union is None else (min(union[0], bb[0]), min(union[1], bb[1]),
                                                      max(union[2], bb[2]), max(union[3], bb[3]))
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
            shown_t = [t for t in titles if t in nodes and (nodes[t].get("opacity", 1) or 0) > 0.01]
            body_nodes = {i: n for i, n in nodes.items() if i not in titles}
            box = _visible_bbox(body_nodes, edges)
            held = [n for i, n in body_nodes.items() if i in keep and all(_num(n.get(k)) for k in ("x", "y", "w", "h"))]
            if box is None and held and not shown_t:   # a title alone is a title card, framed on its own
                box = (1e9, 1e9, -1e9, -1e9)
            area = (A.x, A.y, A.x + A.w, A.y + A.h)
            card = box is None
            if card:
                box = _visible_bbox(nodes, edges)    # a title card alone: center it
                if box is None:
                    continue
                shown_t = []
            elif shown_t:
                area = (A.x, max(titles[t][2] for t in shown_t) + 30, A.x + A.w, A.y + A.h)
            if shown_t and union and union[2] - union[0] <= area[2] - area[0] and \
                    union[3] - union[1] <= area[3] - area[1]:
                box = union
            elif held and not card:
                xs = [x for n in held for x in _ink_x(n)]
                box = (min([box[0]] + xs), min([box[1]] + [n["y"] for n in held]),
                       max([box[2]] + xs), max([box[3]] + [n["y"] + n["h"] for n in held]))
            target = _center_camera(box, area)
            if shown_t and box[3] - box[1] <= area[3] - area[1]:
                # sit the content close under the title, not in the middle of a tall empty band
                top = box[1] - target[1]
                target = (target[0], round(target[1] + max(0, top - area[1] - 120), 1))
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
            for tid in shown_t:
                ax, ay = titles[tid][0], titles[tid][1]
                new = (_clean(ax + target[0]), _clean(ay + target[1]))
                if new == tpos[tid]:
                    continue
                tpos[tid] = new
                nodes[tid].update(x=new[0], y=new[1])
                if k == 0:
                    for nf in sd["nodes"]:
                        if nf["id"] == tid:
                            nf.update(x=new[0], y=new[1])
                    continue
                pn = next((nf for nf in sd["nodes"] if nf["id"] == tid), None)
                if pn is None:
                    pn = {"id": tid}
                    sd["nodes"].append(pn)
                pn.update(x=new[0], y=new[1])
                act = {"type": "transformTween", "target": {"kind": "node", "id": tid},
                       "to": {"x": new[0], "y": new[1]}, "durationMs": cam["cameraDurationMs"], "ease": "ease"}
                if cam.get("cameraOffsetMs"):
                    act["offsetMs"] = cam["cameraOffsetMs"]
                sd.setdefault("actions", []).append(act)
            cur = target


# ------------------------------------------------------------------------------- math, graphs, motion helpers

MATH_EX = 0.431        # MathJax's ex is about 0.431 of the font size: size px letters = size * 0.431 px per ex
TEX2SVG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex2svg.js")
_TEX_CACHE = {}


_PART_RE = re.compile(r"\\part\s*\{([A-Za-z0-9_-]+)\}")


def _tex_parts(tex):
    """\\part{name}{...} -> \\cssId{oc-name}{...}: tex2svg.js measures each marked group."""
    return _PART_RE.sub(lambda m: r"\cssId{oc-%s}" % m.group(1), tex)


def _tex2svg(items):
    """Compile [(tex, color), ...] to [{svg, widthEx, heightEx, depthEx, parts}] with node + mathjax-full
    (scripts/tex2svg.js). Raises OpenCanvizError saying what to install when either is missing."""
    import subprocess
    todo = [it for it in dict.fromkeys(items) if it not in _TEX_CACHE]
    if todo:
        payload = json.dumps({"items": [{"tex": _tex_parts(t), "color": c, "display": True} for t, c in todo]})
        try:
            r = subprocess.run(["node", TEX2SVG], input=payload, capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            raise OpenCanvizError("math() needs Node.js (the `node` command) to compile LaTeX; install Node 16+ "
                                  "and run `npm i mathjax-full` (or set MATHJAX_PATH to a node_modules that has it).")
        if r.returncode == 3:
            raise OpenCanvizError("math() needs the mathjax-full package: run `npm i mathjax-full` in this folder, "
                                  "`npm i -g mathjax-full`, or set MATHJAX_PATH to the node_modules that has it.")
        if r.returncode != 0:
            raise OpenCanvizError("math(): tex2svg.js failed: %s" % (r.stderr.strip()[:300] or r.returncode))
        out = json.loads(r.stdout)["results"]
        for it, res in zip(todo, out):
            if not res.get("ok"):
                raise OpenCanvizError("math(%r): %s. Check the LaTeX (escape backslashes: use r\"...\")."
                                      % (it[0], res.get("error", "TeX error")))
            _TEX_CACHE[it] = res
    return [_TEX_CACHE[it] for it in items]


def _alpha(col, aa):
    """#rrggbb -> #rrggbbaa (a see-through fill); other colours unchanged."""
    return col + aa if isinstance(col, str) and len(col) == 7 and col.startswith("#") else col


def _advance(ch):
    """Width of a letter as a share of the font size (bold display type)."""
    if ch == " ":
        return 0.30
    if ch in "mwMW@%":
        return 0.98
    if ch in "iIl|.,:;'!j":
        return 0.36
    if ch in "ftrJLT()[]{}-/\\":
        return 0.52
    return 0.72


def _mix(a, b, t):
    """#rrggbb a moved t of the way to #rrggbb b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join("%02x" % int(round(x + (y - x) * t)) for x, y in zip(ca, cb))


class Ring:
    """A circle to place things on, from scene.ring(). Angles: degrees, 0 = straight up, clockwise."""

    def __init__(self, scene, center, r, color, width, id):
        self.scene, self.cx, self.cy, self.r = scene, float(center[0]), float(center[1]), float(r)
        th = scene.project.colors
        self.color = color or th["muted"]
        self.node = scene.node("circle", None, x=self.cx - r, y=self.cy - r, w=2 * r, h=2 * r, id=id,
                               fill="transparent", stroke=self.color, strokeWidth=width, noGlow=True)
        self._dots, self._arcs = [], []    # (angle, size, node), (a0, a1, node)

    def point(self, angle):
        a = math.radians(angle)
        return self.cx + self.r * math.sin(a), self.cy - self.r * math.cos(a)

    def place(self, node, angle):
        """Center node on the ring at angle (before the scene's steps move it). Returns the node."""
        px, py = self.point(angle)
        node.fields["x"], node.fields["y"] = _clean(px - node.fields["w"] / 2.0), _clean(py - node.fields["h"] / 2.0)
        node.meta["ring_angle"] = float(angle) % 360
        return node

    place_on_ring = place

    def dot(self, angle, size=40, color=None, label=None, font=None, out=None, id="dot", **kw):
        """A dot on the ring at angle, with an optional label outside the ring (its part)."""
        col = color or self.scene.project.colors["accent"]
        n = self.scene.node("circle", None, x=0, y=0, w=size, h=size, id=id, fill=col, stroke="none", noGlow=True, **kw)
        self.place(n, angle)
        self._dots.append((float(angle) % 360, float(size), n))
        self._layer()
        if label:
            fs = font or self.scene._floor("body")
            d = self.r + (out if out is not None else size / 2.0 + fs * 1.4)
            a = math.radians(angle)
            lx, ly = self.cx + d * math.sin(a), self.cy - d * math.cos(a)
            bw = max(60, len(str(label)) * fs * 0.62 + 16)
            lbl = self.scene.text(str(label), x=lx - bw / 2.0, y=ly - _tline(fs) / 2.0, w=bw, h=_tline(fs),
                                  fontSize=fs, fontWeight=700, color=col, id=id + "_lbl")
            lbl.meta["ring_out"] = d      # walk() carries the label round with its dot
            n.parts.append(lbl)
        return n

    def arc(self, a0, a1, color=None, thickness=14, id="arc"):
        """A band along the ring from a0 to a1 clockwise (a server's range of keys): a wedge with a large
        innerRadius. Reveal it with style "draw" to sweep it open from a0."""
        while a1 <= a0:
            a1 += 360
        ro = self.r + thickness / 2.0
        col = color or self.scene.project.colors["hi"]
        n = self.scene.node("wedge", None, x=self.cx - ro, y=self.cy - ro, w=2 * ro, h=2 * ro, id=id,
                            startAngle=_clean(a0 - 90), endAngle=_clean(a1 - 90),
                            innerRadius=round((self.r - thickness / 2.0) / ro, 4), fill=col, stroke="none", noGlow=True)
        n.meta["ring_arc"] = True
        self._arcs.append((float(a0), float(a1), n))
        self._layer()
        return n

    def _gap(self, size):
        return math.degrees((size / 2.0 + DOT_GAP) / self.r)

    def _retrim(self, vis):
        """A dot that appears inside an arc while the arc is on screen (server D added between B and C)
        cuts the arc back: its free end tweens to DOT_GAP px short of the new dot as the dot comes in.
        The arc keeps the side whose end has a dot on it (a server owns the arc just before it, so by
        default the end side). Walked dots (keys) are left alone: they pass over arcs by design."""
        scene = self.scene
        fixed = [(a, s, d) for a, s, d in self._dots if not d.meta.get("ring_walker")]
        for a0, a1, arc in self._arcs:
            f = arc.fields
            s0 = f.get("startAngle", -90) + 90.0
            s1 = f.get("endAngle", 270) + 90.0
            while s1 <= s0:
                s1 += 360
            at_end = any(abs(((ang - a1 + 180) % 360) - 180) < self._gap(sz) + 0.5 for ang, sz, _ in fixed)
            at_start = any(abs(((ang - a0 + 180) % 360) - 180) < self._gap(sz) + 0.5 for ang, sz, _ in fixed)
            keep_end = at_end or not at_start
            for st in scene.steps:
                k = st.index
                arc_on = vis[arc.id][k] or _in_start(st, arc.id) is not None
                if not arc_on:
                    continue
                arc_before = vis[arc.id][k - 1] if k > 0 else False
                a_in = _in_start(st, arc.id)
                for ang, sz, dot in fixed:
                    if not vis[dot.id][k]:
                        continue
                    g = self._gap(sz)
                    span = s1 - s0
                    rel = (ang - s0) % 360
                    if not (rel < span + g - 0.3 or rel > 360 - g + 0.3):
                        continue      # clear of the arc already
                    if rel > 360 - g or rel < g:
                        n0, n1 = ang + g, s1
                        if rel > 360 - g:
                            n0 = s0 + (rel - 360) + g
                    elif rel > span - g:
                        n0, n1 = s0, s0 + rel - g
                    elif keep_end:
                        n0, n1 = s0 + rel + g, s1
                    else:
                        n0, n1 = s0, s0 + rel - g
                    if n1 - n0 < 1:
                        continue
                    d_in = _in_start(st, dot.id)
                    dot_before = vis[dot.id][k - 1] if k > 0 else getattr(dot, "initial_visible", False) and \
                        d_in is None
                    to = {}
                    if abs(n0 - s0) > 0.01:
                        to["startAngle"] = _clean(n0 - 90)
                    if abs(n1 - s1) > 0.01:
                        to["endAngle"] = _clean(n1 - 90)
                    if not to:
                        continue
                    shown_first = arc_before or (a_in is not None and d_in is not None and a_in < d_in)
                    if shown_first and d_in is not None and not dot_before:
                        # the arc is up before the dot: cut it back as the dot comes in
                        st._tw(arc, to, 400, d_in, "ease-out")
                        st._patch(arc, **to)
                    elif not arc_before and k == min(i for i in range(len(scene.steps)) if vis[arc.id][i]
                                                    or _in_start(scene.steps[i], arc.id) is not None):
                        # the arc first appears with the dot already there: it starts out trimmed
                        f.update(to)
                        for act in st.actions:
                            if act.get("type") == "transformTween" and act["target"].get("id") == arc.id \
                                    and "endAngle" in act.get("from", {}):
                                act["from"]["endAngle"] = _clean(f["startAngle"] + 1)
                                act["to"]["endAngle"] = f["endAngle"]
                    else:
                        st._tw(arc, to, 400, d_in or 0, "ease-out")
                        st._patch(arc, **to)
                    s0, s1 = n0, n1

    def _layer(self):
        """Arcs draw under the ring's dots (they move below the first dot in the stacking order) and stop
        DOT_GAP px short of a dot that sits on either end, so a band never paints over a server."""
        nodes = self.scene.nodes
        dots = [d for _, _, d in self._dots]
        for a0, a1, arc in self._arcs:
            first = min((nodes.index(d) for d in dots), default=None)
            if first is not None and nodes.index(arc) > first:
                nodes.remove(arc)
                nodes.insert(first, arc)
            s0, s1 = a0, a1
            for ang, size, _ in self._dots:
                gap = math.degrees((size / 2.0 + DOT_GAP) / self.r)
                d0 = ((ang - a0 + 180) % 360) - 180
                d1 = ((ang - a1 + 180) % 360) - 180
                if abs(d0) < gap:
                    s0 = max(s0, a0 + d0 + gap)
                if abs(d1) < gap:
                    s1 = min(s1, a1 + d1 - gap)
            if s1 - s0 > 1:
                arc.fields["startAngle"], arc.fields["endAngle"] = _clean(s0 - 90), _clean(s1 - 90)


class Table:
    """Cells from scene.table(): .cells[r][c], .row(r), .column(c)."""

    def __init__(self, scene, rows, at, header, colors, font, gap, id):
        rows = [[str(c) for c in r] for r in rows]
        if not rows or not rows[0]:
            raise OpenCanvizError("table(): give at least one row with one cell.")
        m = max(len(r) for r in rows)
        rows = [r + [""] * (m - len(r)) for r in rows]
        n = len(rows)
        th = scene.project.colors
        cw = (at.w - gap * (m - 1)) / float(m)
        ch = min((at.h - gap * (n - 1)) / float(n), scene.project.base_font * 2.6)
        y0 = at.y + (at.h - (ch * n + gap * (n - 1))) / 2.0
        if font is None:
            sizes = [fit_font(c, scene.project.base_font, cw, ch, "rect", header and i == 0) for i, r in enumerate(rows)
                     for c in r if c]
            if None in sizes:
                raise OpenCanvizError("table(): a cell does not fit its %dx%d box; give the table more room or "
                                      "shorter cells." % (cw, ch))
            font = min(sizes) if sizes else scene.project.base_font
        self.cells = []
        for i, r in enumerate(rows):
            line = []
            for j, c in enumerate(r):
                col = None
                if isinstance(colors, dict):
                    col = colors.get((i, j))
                elif colors:
                    col = colors[i][j] if i < len(colors) and j < len(colors[i]) else None
                head = header and i == 0
                fill = col or ("#1e3a5f" if head and scene.project.colors is not THEMES["light"] else th["fill"])
                f = dict(fill=fill, stroke=th["line"], strokeWidth=2, cornerRadius=8, noGlow=True, labelFontSize=font)
                if head:
                    f["labelFontWeight"] = "bold"
                cell = scene.node("rect", c if c else None, x=at.x + j * (cw + gap), y=y0 + i * (ch + gap), w=cw, h=ch,
                                  id="%s_r%dc%d" % (id, i, j), **f)
                cell.meta["cell"] = True
                line.append(cell)
            self.cells.append(line)

    def row(self, r):
        return list(self.cells[r])

    def column(self, c):
        return [line[c] for line in self.cells]

    @property
    def all(self):
        return [n for line in self.cells for n in line]


class CompareBars:
    """From scene.compare_bars(): .labels, .bars, .numbers (lists, one per item)."""

    def __init__(self, scene, items, at, unit, font, id):
        items = list(items)
        if len(items) < 2:
            raise OpenCanvizError("compare_bars(): give at least two (label, value, color) items.")
        th = scene.project.colors
        lf = font or scene._floor("body")
        n = len(items)
        row_h = (at.h - 30 * (n - 1)) / float(n)
        nf = int(min(lf * 1.7, (row_h - _tline(lf) - 4) / 1.25))
        if nf < lf:
            raise OpenCanvizError("compare_bars(): %d rows do not fit in %d px; give a taller area." % (n, at.h))
        texts = [(it[3] if len(it) > 3 else _tick_fmt(it[1]) + unit) for it in items]
        num_w = max(len(t) for t in texts) * nf * 0.8 + 40
        nh = _tline(nf)
        bar_h = max(30, min(nh, nf * 1.1))
        top = max(v for _, v, *_ in items)
        if top <= 0:
            raise OpenCanvizError("compare_bars(): values must be > 0.")
        span = at.w - num_w
        self.labels, self.bars, self.numbers = [], [], []
        for i, it in enumerate(items):
            lab, v = it[0], it[1]
            col = it[2] if len(it) > 2 and it[2] else PALETTE[i % len(PALETTE)]
            y = at.y + i * (row_h + 30)
            self.labels.append(scene.text(str(lab), x=at.x, y=y, w=at.w, h=_tline(lf), fontSize=lf, textAlign="left",
                                          color=th["muted"], id="%s_lbl%d" % (id, i)))
            by = y + _tline(lf) + 4
            bw = max(12.0, span * v / float(top))
            self.bars.append(scene.node("rect", None, x=at.x, y=by + (nh - bar_h) / 2.0, w=bw, h=bar_h, id="%s_bar%d" % (id, i), fill=col,
                                        stroke="none", cornerRadius=10, noGlow=True, pivotX=0))
            self.numbers.append(scene.text(texts[i], x=at.x + bw + 16, y=by, w=num_w, h=nh,
                                           fontSize=nf, fontWeight=800, textAlign="left", color=col,
                                           id="%s_num%d" % (id, i)))


def _in_start(st, nid):
    offs = [a.get("offsetMs", 0) for a in st.actions if a.get("type") == "visibility"
            and a.get("target", {}).get("id") == nid and a.get("mode") in VIS_IN]
    return min(offs) if offs else None


class Plot:
    """A coordinate plane from scene.plot()."""

    def __init__(self, scene, at, x_range, y_range, x_ticks, y_ticks, grid, font, color, x_label, y_label, id):
        self.scene, self.id = scene, id
        self._points = []
        th = scene.project.colors
        self.xlo, self.xhi = float(x_range[0]), float(x_range[1])
        self.ylo, self.yhi = float(y_range[0]), float(y_range[1])
        if self.xhi <= self.xlo or self.yhi <= self.ylo:
            raise OpenCanvizError("plot(): x_range and y_range must be (low, high).")
        tf = font or scene._floor("tick")
        xt = list(x_ticks) if x_ticks is not None else _ticks(self.xlo, self.xhi, 5)
        yt = list(y_ticks) if y_ticks is not None else _ticks(self.ylo, self.yhi, 4)
        left = max(len(_tick_fmt(v)) for v in yt) * tf * 0.6 + 24 if yt else 20
        bottom = _tline(tf) + 8
        self.px0, self.py0 = at.x + left, at.y + 10
        self.pw, self.ph = at.w - left - 20, at.h - bottom - 10
        col = color or th["muted"]
        paths = []
        if grid:
            d = " ".join("M %s 0 V %s" % (_clean(self._lx(v)), _clean(self.ph)) for v in xt) + " " + \
                " ".join("M 0 %s H %s" % (_clean(self._ly(v)), _clean(self.pw)) for v in yt)
            paths.append({"d": d.strip(), "stroke": th["line"], "strokeWidth": 2, "fill": "none"})
        ax_y = self._ly(0) if self.ylo <= 0 <= self.yhi else self.ph
        ax_x = self._lx(0) if self.xlo <= 0 <= self.xhi else 0
        ticks = " ".join("M %s %s V %s" % (_clean(self._lx(v)), _clean(ax_y - 8), _clean(ax_y + 8)) for v in xt) + " " + \
            " ".join("M %s %s H %s" % (_clean(ax_x - 8), _clean(self._ly(v)), _clean(ax_x + 8)) for v in yt)
        paths.append({"d": "M 0 %s H %s M %s 0 V %s %s" % (_clean(ax_y), _clean(self.pw), _clean(ax_x), _clean(self.ph),
                                                             ticks.strip()), "stroke": col, "strokeWidth": 3, "fill": "none"})
        self.node = scene.svg_path(paths, self.px0, self.py0, self.pw, self.ph, id=id)
        for v in xt:
            if abs(v) < 1e-9 and self.ylo <= 0 <= self.yhi and self.xlo < 0:
                continue
            w = max(40, len(_tick_fmt(v)) * tf * 0.6 + 12)
            self.node.parts.append(scene.text(_tick_fmt(v), x=self.px0 + self._lx(v) - w / 2.0,
                                              y=self.py0 + ax_y + 10, w=w, h=_tline(tf), fontSize=tf, color=col,
                                              id="%s_x%s" % (id, _slug(_tick_fmt(v)))))
        for v in yt:
            if abs(v) < 1e-9 and self.xlo <= 0 <= self.xhi:
                continue
            w = left - 4
            self.node.parts.append(scene.text(_tick_fmt(v), x=self.px0 + ax_x - w - 12,
                                              y=self.py0 + self._ly(v) - _tline(tf) / 2.0, w=w, h=_tline(tf), fontSize=tf,
                                              color=col, textAlign="right", id="%s_y%s" % (id, _slug(_tick_fmt(v)))))
        for txt, xx, yy, al in ((x_label, self.px0 + self.pw - 160, self.py0 + ax_y - _tline(tf) - 6, "right"),
                                (y_label, self.px0 + ax_x + 14, self.py0, "left")):
            if txt:
                self.node.parts.append(scene.text(str(txt), x=xx, y=yy, w=150, h=_tline(tf), fontSize=tf, color=col,
                                                  textAlign=al, id="%s_%s" % (id, _slug(txt))))

    def _lx(self, x):
        return (x - self.xlo) / (self.xhi - self.xlo) * self.pw

    def _ly(self, y):
        return (self.yhi - y) / (self.yhi - self.ylo) * self.ph

    def to_px(self, x, y):
        """World px of plot point (x, y)."""
        return self.px0 + self._lx(x), self.py0 + self._ly(y)

    def slope_deg(self, fn, x):
        """rotationZ that lines a horizontal node up with the curve's tangent at x (screen degrees)."""
        h = (self.xhi - self.xlo) * 1e-4
        m = (fn(x + h) - fn(x - h)) / (2 * h)
        return _clean(round(math.degrees(math.atan2(-m * self.ph / (self.yhi - self.ylo), self.pw / (self.xhi - self.xlo))), 2))

    def _trace(self, fn, a, b, samples):
        segs, cur = [], []
        for i in range(samples + 1):
            x = a + (b - a) * i / float(samples)
            try:
                y = fn(x)
            except (ValueError, ZeroDivisionError):
                y = None
            if y is None or not (self.ylo - 1e-9 <= y <= self.yhi + 1e-9):
                if len(cur) > 1:
                    segs.append(cur)
                cur = []
                continue
            cur.append((self._lx(x), self._ly(y)))
        if len(cur) > 1:
            segs.append(cur)
        return segs

    def curve(self, fn, color=None, width=5, samples=160, x_range=None, id="curve"):
        """fn drawn across the plot (parts outside the y range are left out) as an svg node on the plot
        area. Reveal it with style "draw" to draw it on left to right."""
        a, b = x_range or (self.xlo, self.xhi)
        segs = self._trace(fn, a, b, samples)
        if not segs:
            raise OpenCanvizError("plot.curve(): the curve never enters the plot's y range.")
        d = " ".join("M " + " L ".join("%s %s" % (_clean(round(px, 1)), _clean(round(py, 1))) for px, py in s) for s in segs)
        return self.scene.svg_path([{"d": d, "stroke": color or self.scene.project.colors["accent"],
                                     "strokeWidth": width, "fill": "none"}], self.px0, self.py0, self.pw, self.ph,
                                   id="%s_%s" % (self.id, id))

    def area(self, fn, a, b, color=None, samples=80, id="area"):
        """The area between fn and the x axis from a to b, filled see-through."""
        col = color or self.scene.project.colors["accent"]
        base = self._ly(min(max(0, self.ylo), self.yhi))
        pts = [(self._lx(a), base)]
        for i in range(samples + 1):
            x = a + (b - a) * i / float(samples)
            pts.append((self._lx(x), self._ly(min(max(fn(x), self.ylo), self.yhi))))
        pts.append((self._lx(b), base))
        d = "M " + " L ".join("%s %s" % (_clean(round(px, 1)), _clean(round(py, 1))) for px, py in pts) + " Z"
        return self.scene.svg_path([{"d": d, "stroke": "none", "strokeWidth": 0,
                                     "fill": col + "55" if len(col) == 7 else col}], self.px0, self.py0, self.pw, self.ph,
                                   id="%s_%s" % (self.id, id))

    def point(self, x, y, size=28, color=None, label=None, font=None, id="pt"):
        """A dot at plot point (x, y), with an optional label above-right (its part)."""
        px, py = self.to_px(x, y)
        col = color or self.scene.project.colors["hi"]
        n = self.scene.node("circle", None, x=px - size / 2.0, y=py - size / 2.0, w=size, h=size,
                            id="%s_%s" % (self.id, id), fill=col, stroke="none", noGlow=True)
        n.meta["on_curve"] = True     # pop() grows it in place: a dot rising from below reads as off the curve
        if label:
            fs = font or self.scene._floor("tick")
            bw = len(str(label)) * fs * 0.62 + 16
            n.parts.append(self.scene.text(str(label), x=px + size * 0.6, y=py - size * 0.6 - _tline(fs), w=bw,
                                           h=_tline(fs), fontSize=fs, color=col, textAlign="left",
                                           id="%s_%s_lbl" % (self.id, id)))
        self._points.append((float(x), float(y), n))
        return n

    def vector(self, x0, y0, x1, y1, color=None, width=5, id="vec"):
        """An arrow from plot point (x0, y0) to (x1, y1), drawn as one svg node (style "draw" draws it on)."""
        (ax, ay), (bx, by) = self.to_px(x0, y0), self.to_px(x1, y1)
        ang = math.atan2(by - ay, bx - ax)
        hl = 22
        h1 = (bx - hl * math.cos(ang - 0.45), by - hl * math.sin(ang - 0.45))
        h2 = (bx - hl * math.cos(ang + 0.45), by - hl * math.sin(ang + 0.45))
        pad = hl + width
        x_0, y_0 = min(ax, bx) - pad, min(ay, by) - pad
        w, h = max(10, abs(bx - ax) + 2 * pad), max(10, abs(by - ay) + 2 * pad)
        q = lambda p: "%s %s" % (_clean(round(p[0] - x_0, 1)), _clean(round(p[1] - y_0, 1)))   # noqa: E731
        d = "M %s L %s M %s L %s L %s" % (q((ax, ay)), q((bx, by)), q(h1), q((bx, by)), q(h2))
        return self.scene.svg_path([{"d": d, "stroke": color or self.scene.project.colors["hi"], "strokeWidth": width,
                                     "fill": "none"}], x_0, y_0, w, h, id="%s_%s" % (self.id, id))

    def tangent(self, fn, x, length=360, color=None, thickness=10, id="tan", point=None):
        """A tangent line to fn at x (a thin bar turned to the slope). step.ride(dot, plot, fn, x0, x1,
        tangent=this) slides it along the curve. It belongs to the dot at (x, fn(x)) made by plot.point()
        (or the node you pass as point=): its reveal is moved so it starts with that dot or later, never
        before, and revealing it while the dot is hidden raises."""
        px, py = self.to_px(x, fn(x))
        if point is None:
            point = next((d for xx, yy, d in self._points
                          if abs(xx - x) < 1e-9 and abs(yy - fn(x)) < 1e-6), None)
        n = self.scene.node("rect", None, x=px - length / 2.0, y=py - 5, w=length, h=10, id="%s_%s" % (self.id, id),
                            fill=color or self.scene.project.colors["hi"], stroke="none", cornerRadius=3, noGlow=True,
                            rotationZ=self.slope_deg(fn, x))
        if thickness < 10:
            raise OpenCanvizError("plot.tangent(): thickness must be >= 10; the export renderer drops nodes under 10 px.")
        n.fields["h"] = thickness
        n.fields["y"] = _clean(py - thickness / 2.0)
        if point is not None:
            n.meta["tangent_dot"] = point
        return n

    def legend(self, items, at=None, font=None, id="key"):
        """A key in the plot's top-left corner (or in at): items = [(label, color), ...]. Returns the
        swatch nodes; each one's text is its part."""
        fs = font or self.scene._floor("body")
        x = at.x if at is not None else self.px0 + 30
        y = at.y if at is not None else self.py0 + 10
        out = []
        for i, (lab, col) in enumerate(items):
            rh = _tline(fs)
            sw = self.scene.node("rect", None, x=x, y=y + i * (rh + 6) + rh / 2.0 - 7, w=36, h=14,
                                 id="%s_%s%d" % (self.id, id, i), fill=col, stroke="none", cornerRadius=4, noGlow=True)
            sw.parts.append(self.scene.text(str(lab), x=x + 48, y=y + i * (rh + 6), w=len(str(lab)) * fs * 0.62 + 20,
                                            h=rh, fontSize=fs, textAlign="left", color=col,
                                            id="%s_%s%d_t" % (self.id, id, i)))
            out.append(sw)
        return out


class NumberLine:
    """From scene.number_line(): .node, .to_px(v), .point(v)."""

    def __init__(self, scene, at, lo, hi, step, font, color, id):
        self.scene, self.lo, self.hi, self.id = scene, float(lo), float(hi), id
        th = scene.project.colors
        tf = font or scene._floor("tick")
        self.x0, self.x1, self.cy = at.x + 30, at.x + at.w - 30, at.cy
        col = color or th["muted"]
        vals, v = [], self.lo
        while v <= self.hi + 1e-9:
            vals.append(_clean(round(v, 6)))
            v += step
        w = self.x1 - self.x0 + 60
        ticks = " ".join("M %s 22 V 50" % _clean(self.to_px(v) - self.x0 + 30) for v in vals)
        self.node = scene.svg_path([{"d": "M 0 36 H %s %s" % (_clean(w), ticks), "stroke": col, "strokeWidth": 4,
                                     "fill": "none"}], self.x0 - 30, self.cy - 36, w, 72, id=id)
        for v in vals:
            bw = max(40, len(_tick_fmt(v)) * tf * 0.6 + 12)
            self.node.parts.append(scene.text(_tick_fmt(v), x=self.to_px(v) - bw / 2.0, y=self.cy + 40, w=bw,
                                              h=_tline(tf), fontSize=tf, color=col, id="%s_%s" % (id, _slug(_tick_fmt(v)))))

    def to_px(self, v):
        return self.x0 + (v - self.lo) / (self.hi - self.lo) * (self.x1 - self.x0)

    def point(self, v, size=30, color=None, id="pt"):
        col = color or self.scene.project.colors["hi"]
        n = self.scene.node("circle", None, x=self.to_px(v) - size / 2.0, y=self.cy - size / 2.0, w=size, h=size,
                            id="%s_%s" % (self.id, id), fill=col, stroke="none", noGlow=True)
        n.meta["on_curve"] = True
        return n


class Matrix:
    """From scene.matrix(): .node (the brackets), .cells[r][c], .row(r), .column(c)."""

    def __init__(self, scene, rows, at, font, color, id):
        rows = [[str(c) for c in r] for r in rows]
        n, m = len(rows), max(len(r) for r in rows)
        th = scene.project.colors
        fs = font or scene.project.base_font
        cw = max(max(len(c) for r in rows for c in r) * fs * 0.62 + 36, fs * 1.6)
        ch = _tline(fs) + 8
        w, h = cw * m + 60, ch * n + 30
        if w > at.w + 1 or h > at.h + 1:
            raise OpenCanvizError("matrix(): %dx%d px does not fit its %dx%d box; lower font=." % (w, h, at.w, at.h))
        x0, y0 = at.cx - w / 2.0, at.cy - h / 2.0
        col = color or th["text"]
        d = "M 22 4 H 6 V %s H 22 M %s 4 H %s V %s H %s" % (_clean(h - 4), _clean(w - 22), _clean(w - 6), _clean(h - 4),
                                                           _clean(w - 22))
        self.node = scene.svg_path([{"d": d, "stroke": th["muted"], "strokeWidth": 4, "fill": "none"}], x0, y0, w, h, id=id)
        self.cells = []
        for i, r in enumerate(rows):
            line = []
            for j in range(m):
                t = scene.text(r[j] if j < len(r) else "", x=x0 + 30 + j * cw, y=y0 + 15 + i * ch, w=cw, h=ch, fontSize=fs,
                               color=col, id="%s_r%dc%d" % (id, i, j))
                self.node.parts.append(t)
                line.append(t)
            self.cells.append(line)

    def row(self, r):
        return list(self.cells[r])

    def column(self, c):
        return [line[c] for line in self.cells]


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
                 caption_style=None, margin=60, side_margin=None, follow=True, sfx=None, stage="follow"):
        if aspect not in ASPECTS:
            raise OpenCanvizError("aspect must be one of %s" % sorted(ASPECTS))
        if theme not in THEMES:
            raise OpenCanvizError("theme must be one of %s" % sorted(THEMES))
        if voice not in VOICES:
            raise OpenCanvizError("voice must be one of %s" % sorted(VOICES))
        if sfx is not None and sfx not in SFX_PACKS:
            raise OpenCanvizError("sfx must be one of %s (motion sound effects on appear / connect)." % sorted(SFX_PACKS))
        if stage not in ("follow", "steady"):
            raise OpenCanvizError("stage must be \"follow\" (the camera centers each step) or \"steady\" (a fixed "
                                  "camera and %d ms crossfades between scenes)." % STEADY_MS)
        self.sfx, self.stage = sfx, stage
        if stage == "steady":
            follow = False
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

    def scene(self, name=None, transition="crossfade", transition_ms=None, background=None, color=None):
        """Add a scene. transition joins the previous scene to this one: any of TRANSITION_KINDS, or None
        for a hard cut. color is the block colour of a colorWipe* (default the brand violet); "morph"
        needs at least one node in each of the two scenes with the same morph_key. transition_ms defaults
        to 600 (300 with stage="steady")."""
        if transition_ms is None:
            transition_ms = STEADY_MS if self.stage == "steady" else 600
        if transition is not None and transition not in TRANSITION_KINDS:
            raise OpenCanvizError("transition must be None or one of %s" % sorted(TRANSITION_KINDS))
        if transition is not None and not transition_ms > 0:
            raise OpenCanvizError("transition_ms must be > 0.")
        if color is not None:
            if transition not in COLOR_WIPES:
                raise OpenCanvizError("color= is only for the colorWipe transitions, not %r." % transition)
            if not (isinstance(color, str) and re.match(r"^#[0-9a-fA-F]{6}$", color)):
                raise OpenCanvizError("color must be a #rrggbb hex, got %r." % color)
        s = Scene(self, len(self.scenes), name or "Scene %d" % (len(self.scenes) + 1),
                  (transition, transition_ms, color), background)
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
                                      dict({"kind": s.transition[0], "durationMs": s.transition[1]},
                                           **({"color": s.transition[2]} if s.transition[2] else {}))
                                      for s in self.scenes[1:]]
            doc["diagrams"] = scenes
        doc["showCaptions"] = bool(self.captions)
        if self.sfx:
            doc["sfxPack"] = self.sfx
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
        # compact: no indent and no spaces after separators (an import over ~150 KB can time out)
        text = json.dumps(doc, separators=(",", ":"), allow_nan=False)
        if len(text) > IMPORT_SOFT_LIMIT:
            sys.stderr.write("note: %s is %d KB; an import much over %d KB can time out. Equations and images are "
                             "the heavy part: reuse one math node instead of repeating it, and split a long video "
                             "into two files.\n" % (path, len(text) // 1024, IMPORT_SOFT_LIMIT // 1024))
        with open(path, "w") as fh:
            fh.write(text + "\n")
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


def _opens_with_title(sc, ab):
    """True when a big or bold text node shows in the top third of the frame in the first two steps."""
    nodes = {n.get("id"): dict(n) for n in sc.get("nodes") or [] if isinstance(n, dict)}
    floor = font_floor("body", ab["width"], ab["height"])
    for st in (sc.get("steps") or [])[:2]:
        if not isinstance(st, dict):
            continue
        for n in st.get("nodes") or []:
            if isinstance(n, dict):
                nodes.setdefault(n.get("id"), {}).update(n)
        cam = st.get("camera") if isinstance(st.get("camera"), dict) else {}
        oy = (cam.get("y") or 0) if _num(cam.get("y")) else 0
        for n in nodes.values():
            if n.get("kind") != "text" or (n.get("opacity", 1) or 0) <= 0.01 or not _num(n.get("y")) \
                    or not _num(n.get("h")) or not str(n.get("text", "")).strip():
                continue
            big = _is_bold(n.get("fontWeight")) or (n.get("fontSize") or 0) >= 1.5 * floor
            if big and n["y"] + n["h"] / 2.0 - oy <= ab["y"] + ab["height"] / 3.0:
                return True
            if big and (n.get("fontSize") or 0) >= 1.5 * floor:
                return True        # a title card in the middle of the frame
    return False


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
                else:
                    if "color" in t and t["kind"] not in COLOR_WIPES:
                        W("transitions[%d]: color is used only by the colorWipe kinds; %s ignores it." % (i, t["kind"]))
                    if t["kind"] == "morph" and i + 1 < len(scenes):
                        keys = [{n.get("morphKey") for n in (sc.get("nodes") or []) if isinstance(n, dict)
                                 and n.get("morphKey")} if isinstance(sc, dict) else set()
                                for sc in (scenes[i], scenes[i + 1])]
                        if not keys[0] & keys[1]:
                            E("transitions[%d]: morph needs a node in scene %d and one in scene %d with the same "
                              "\"morphKey\" (the helper: morph_key=\"...\" on both); without one it is only a "
                              "crossfade. Node ids differ per scene, so they never pair." % (i, i + 1, i + 2))
        if scenes and isinstance(scenes[0], dict) and ab and not _opens_with_title(scenes[0], ab):
            W("scene 1: the video does not open with a title. Show a short bold title at the top in the first "
              "step (the Python helper: title, body = scene.title(\"...\")), or a title card.")
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
        pts = edge_path(e, a, b)
        for x, y in pts:
            xs.append(x)
            ys.append(y)
        if e.get("label") and "fromXY" not in e and len(pts) > 1:
            cx, cy = _path_mid(pts)
            lfs = e.get("labelFontSize", 12)
            lw, lh = label_width(e["label"], lfs), label_height(lfs)
            xs += [cx - lw / 2.0, cx + lw / 2.0]
            ys += [cy - lh / 2.0, cy + lh / 2.0]
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
    bar, pie wedges sharing a center, a small dot on a chart, and any pair where one node is a thin line (12 px or less)."""
    ka, kb = a.get("kind"), b.get("kind")
    kinds = {ka, kb}
    if min(a["w"], a["h"], b["w"], b["h"]) <= 12:
        return True
    if ka == kb == "wedge":
        return True
    if a.get("svgStretch") or b.get("svgStretch"):
        return True        # plot axes, curves, brackets and polygons are drawn over the things they mark
    for p, q in ((a, b), (b, a)):
        if p.get("kind") == "wedge" and (p.get("innerRadius") or 0) > 0:
            return True    # a thin arc: its box is the whole ring, so a box test means nothing
        if p.get("kind") == "circle" and (p.get("fill") in ("transparent", "none") or (p.get("opacity", 1) or 0) < 0.9
                                          or len(str(p.get("fill", ""))) == 9):
            return True    # a ring (hollow circle) with dots on it, see-through Venn circles
        if p.get("kind") == "wedge" and q.get("kind") == "circle":
            return True    # an arc on its ring
    if ka == kb == "text" and len(str(a.get("text", ""))) <= 1 and len(str(b.get("text", ""))) <= 1:
        return True        # the letters of a kinetic title
    under = {"algo-chart", "algo-chart-line", "algo-chart-scatter", "progress", "uml-lifeline"}
    if "text" in kinds and (ka in under or kb in under):
        return True
    if kinds == {"glyph", "progress"}:
        return True
    if "circle" in kinds and (ka in under or kb in under) and min(a["w"], b["w"]) <= 40:
        return True        # a marker dot on a chart (the line chart's tip)
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
    typing = [{(a.get("target") or {}).get("id") for a in (st.get("actions") or []) if isinstance(a, dict)
               and a.get("type") == "transformTween" and "typeProgress" in (a.get("to") or {})}
              if isinstance(st, dict) else set() for st in steps]
    typed_later = {k: set().union(*typing[k + 1:]) - typing[k] for k in range(len(steps) - 1)}
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
        elif CAPTION_DECIMAL.search(str(st.get("caption"))):
            W("%s: the caption has a decimal number (%r); the caption card splits \"7.1 minutes\" at the point. "
              "Round it or say it in words." % (P, st.get("caption")))
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
        for a in acts:
            if not isinstance(a, dict):
                continue
            tid = (a.get("target") or {}).get("id")
            if a.get("type") == "transformTween" and "blur" in (a.get("to") or {}):
                W("%s: %s tweens blur, which exported videos do not draw (only the editor shows it); the text "
                  "just fades. Use a pop (scale from 0.6, ease \"back\") or a fade." % (P, tid))
            if a.get("type") == "transformTween" and "drawProgress" in (a.get("to") or {}) and \
                    (nodes.get(tid) or {}).get("kind") == "text":
                W("%s: %s is a text node; drawProgress wipes only image nodes, so the text appears whole. Type "
                  "it (typeProgress) or write it on (writeHand)." % (P, tid))
        for nid, how in (st.get("transitions") or {}).items() if isinstance(st.get("transitions"), dict) else []:
            if how in FLIP_TRANSITIONS:
                W("%s: transitions[%s] is %s, which openCanviz does not draw; the change plays as a plain morph. "
                  "Use \"fade\" or \"instant\", or tween scaleX/scaleY yourself." % (P, nid, how))
        for nid in typed_later.get(k, ()):
            n = nodes.get(nid) or {}
            if (n.get("opacity", 1) or 0) > 0.01 and _num(n.get("typeProgress")) and n["typeProgress"] < 1:
                W("%s: %s is typed in a later step but is already visible here, and openCanviz draws a half-typed "
                  "text whole in any step that is not typing it. Keep it at opacity 0 until the step that types it "
                  "(the helper's typewrite does)." % (P, nid))
        # a visible node's colour / position change with no tween of its own plays across the whole step
        timed_keys = {}
        for a in acts:
            if isinstance(a, dict) and a.get("type") in ("transformTween", "pathFollow"):
                ks = set((a.get("to") or {}) if a.get("type") == "transformTween" else TIMED_GEOM)
                timed_keys.setdefault((a.get("target") or {}).get("id"), set()).update(ks)
        slow = TIMED_COLORS | TIMED_GEOM | ALGO_TIMED - {"cellValues", "gridValues"} | \
            {"pointerTargetIndex", "pointerTargetRow", "pointerTargetCol"}
        for p in (st.get("nodes") or []) if k > 0 else []:
            if not isinstance(p, dict) or p.get("id") not in before_n:
                continue
            was = before_n[p["id"]]
            if (was.get("opacity", 1) or 0) <= 0.01 or (p.get("opacity", was.get("opacity", 1)) or 0) <= 0.01:
                continue
            keys = sorted(x for x in p if x in slow and p[x] != was.get(x) and x not in timed_keys.get(p["id"], ()))
            if keys and once(("slow", p["id"], k)):
                W("%s: %s changes %s with no tween of its own, so the change plays across the whole %d ms step. Add "
                  "a transformTween with a short durationMs (350 ms for a colour, 600 ms for a move) whose to "
                  "repeats the new value; the Python helper's set()/move()/point() do this." % (P, p["id"],
                                                                                     ", ".join(keys), dur))
        for a in acts:
            if isinstance(a, dict) and a.get("type") == "transformTween":
                to = a.get("to") or {}
                cells = [to.get("cellColors")] if isinstance(to.get("cellColors"), list) else []
                cells += [r for r in (to.get("gridColors") or []) if isinstance(r, list)]
                if any(c is None for r in cells for c in r) or (isinstance(to.get("nodeColors"), dict) and
                                                                None in to["nodeColors"].values()):
                    W("%s: a colour tween on %s has a null cell; openCanviz keeps a cell tweened to null in its old "
                      "colour for the whole step. Write the plain fill (the array's \"fill\", default #1e293b) "
                      "instead." % (P, (a.get("target") or {}).get("id")))
        last_et, last_tw = {}, {}
        entering = {(a.get("target") or {}).get("id") for a in acts if isinstance(a, dict)
                    and a.get("type") == "visibility" and a.get("mode") in VIS_IN}
        last_vis = {}      # the renderer keeps the visibility action that starts last (a flash: in, then out)
        for a in acts:
            if isinstance(a, dict) and a.get("type") == "visibility":
                k_ = (a.get("target") or {}).get("id")
                if k_ not in last_vis or (a.get("offsetMs") or 0) >= (last_vis[k_].get("offsetMs") or 0):
                    last_vis[k_] = a
        for a in acts:
            if isinstance(a, dict) and a.get("type") == "transformTween":
                end_ = (a.get("offsetMs") or 0) + (a.get("durationMs") or 0)
                for key in (a.get("to") or {}):
                    kk = ((a.get("target") or {}).get("id"), key)
                    if kk not in last_tw or end_ >= (last_tw[kk].get("offsetMs") or 0) + (last_tw[kk].get("durationMs") or 0):
                        last_tw[kk] = a
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
                if last_vis.get(tid) is not a:
                    continue
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
                    if not (a.get("isRelative") and _num(a.get("dx")) and _num(a.get("dy")) and tid in entering
                            and "x" not in to and "y" not in to):
                        E("%s: transformTween on %s uses isRelative/dx/dy; that is only for an entrance (the node "
                          "has a fadeIn/show in this step, isRelative true with both dx and dy, no to.x/to.y: it "
                          "travels from home - (dx, dy) to home). Otherwise use an absolute to.x/to.y." % (P, tid))
                if to.get("opacity") == 0:
                    E("%s: do not hide %s with an opacity transformTween; use a visibility fadeOut and opacity 0."
                      % (P, tid))
                for key, val in to.items():
                    if key not in TWEEN_PROPS:
                        E("%s: transformTween to.%s is not a tween property." % (P, key))
                    if key in ALGO_TIMED:
                        if nodes[tid].get(key) != val:
                            E("%s: transformTween on %s times %s, but its to.%s differs from the step's %s; give the "
                              "same value in both (the tween only sets the timing)." % (P, tid, key, key, key))
                        continue
                    cur = nodes[tid].get(key, 1 if key in ("opacity", "typeProgress", "scaleX", "scaleY") else None)
                    if last_tw.get((tid, key)) is not a:
                        continue      # a later tween in this step takes the prop on (a pulse's way up, a shake)
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
            if t in ("positionTween", "pathFollow", "algoSwap", "containerTransform") and tid not in nodes:
                E("%s: %s targets unknown node %s." % (P, t, tid))
            if t == "pathAnimate" and tid not in edges:
                E("%s: pathAnimate targets unknown edge %s." % (P, tid))
            if t == "algoSwap" and tid in nodes:
                ix = a.get("indices")
                vals = nodes[tid].get("cellValues") or []
                if not (isinstance(ix, list) and len(ix) == 2 and all(isinstance(i, int) and 0 <= i < len(vals) for i in ix)
                        and ix[0] != ix[1]):
                    E("%s: algoSwap on %s needs \"indices\": [i, j], two different cells of its cellValues." % (P, tid))
                elif len(before_n.get(tid, {}).get("cellValues") or []) == len(vals) and \
                        before_n[tid]["cellValues"][ix[0]] != vals[ix[1]]:
                    E("%s: algoSwap on %s swaps cells %d and %d, but the step's cellValues do not hold them swapped; "
                      "put the swapped values in this step's snapshot." % (P, tid, ix[0], ix[1]))
            if (t == "algoSwap" or (t == "transformTween" and ALGO_TIMED & set(a.get("to") or {}))) \
                    and not st.get("easing"):
                E("%s: a %s on %s is timed only when the step has \"easing\" (e.g. \"ease\"); without it openCanviz "
                  "snaps a swap and spreads a colour change over the whole step." % (P, t, tid))
            if t in ("visibility", "transformTween", "positionTween", "pathFollow") and tgt.get("kind") != "node":
                E("%s: %s target must be {\"kind\":\"node\",\"id\":...}." % (P, t))
            if t == "edgeTween" and tgt.get("kind") != "edge":
                E("%s: edgeTween target must be {\"kind\":\"edge\",\"id\":...}." % P)
            ease = a.get("ease")
            if ease is not None and ease not in EASINGS:
                E("%s: ease %r is not one of %s%s." % (P, ease, sorted(EASINGS),
                  " (camelCase names play linear: write ease-out, not easeOut)" if re.search("[a-z][A-Z]", str(ease)) else ""))
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
        if str(st.get("caption", "")).strip():
            _dead_air_check(P, st, dur, nodes, vis_nodes, prev_vis_nodes, E)
        if ab and vis_nodes:
            _balance_check(P, ab, [nodes[i] for i in vis_nodes], W, once)
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
        c = st.get("camera")
        if ab and isinstance(c, dict) and all(_num(c.get(x)) for x in ("x", "y", "zoom")):
            view = (c["x"], c["y"], c["zoom"])
        # where the frame is: the artboard, moved by a zoom-1 camera pan (what the video shows)
        fx0, fy0 = ab["x"] if ab else 0, ab["y"] if ab else 0
        if ab and view and abs(view[2] - 1) <= 0.05:
            fx0 += view[0] - (ab["x"] + ab["width"] / 2.0)
            fy0 += view[1] - (ab["y"] + ab["height"] / 2.0)
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
            ix0, ix1 = _ink_x(n) if (fx0, fy0) != (ab["x"], ab["y"]) else (n["x"], n["x"] + n["w"])
            if ab and (ix0 < fx0 - 1 or n["y"] < fy0 - 1 or ix1 > fx0 + ab["width"] + 1
                       or n["y"] + n["h"] > fy0 + ab["height"] + 1):
                E("%s: node %s (x=%g y=%g w=%g h=%g) sticks out of the frame (%g,%g %gx%g: the artboard moved by "
                  "the camera); move it inside." % (P, nid, n["x"], n["y"], n["w"], n["h"], fx0, fy0, ab["width"],
                                                     ab["height"]))
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
        if ab and view:
            later = [n for i, n in nodes.items() if i in ever and n.get("kind") not in ("group", "algo-pointer")
                     and not n.get("parentId") and all(_num(n.get(x)) for x in ("x", "y", "w", "h"))]
            _screen_checks(P, ab, captions, nodes, edges, vis, view, W, once, later)
        _layout_checks(P, ab, captions, nodes, edges, vis, any_caption, W, once)
        _arrow_length_checks(P, nodes, edges, vis, W, once)
        _ring_arc_checks(P, vis, W, once)
        if k == len(steps) - 1 and ab:
            _fill_check(P, ab, captions, vis, W)
        prev_edge_trim = {i: e.get("trim", 1) for i, e in edges.items()}
        prev_vis_nodes = vis_nodes


def _ring_arc_checks(P, vis, W, once):
    """A ring band (a wedge with a large innerRadius) that runs under a visible dot on its ring, or stops
    closer than DOT_GAP px to it: a server added after the arcs were cut."""
    for a in vis:
        if a.get("kind") != "wedge" or not (a.get("innerRadius") or 0) > 0.5 or (a.get("opacity", 1) or 0) <= 0:
            continue
        ro = a["w"] / 2.0
        rm = ro * (1 + a["innerRadius"]) / 2.0
        cx, cy = a["x"] + ro, a["y"] + a["h"] / 2.0
        s0, s1 = a.get("startAngle", -90), a.get("endAngle", 270)
        while s1 <= s0:
            s1 += 360
        for d in vis:
            if d.get("kind") != "circle" or d is a or (d.get("opacity", 1) or 0) <= 0 or abs(d["w"] - d["h"]) > 1:
                continue
            if d.get("fill") in (None, "transparent", "none"):
                continue
            rd = d["w"] / 2.0
            dx, dy = d["x"] + rd - cx, d["y"] + rd - cy
            if abs(math.hypot(dx, dy) - rm) > rd:
                continue
            ang = math.degrees(math.atan2(dy, dx))         # the wedge's own convention: 0 = right, clockwise
            g = math.degrees((rd + DOT_GAP - 2) / rm)
            rel = (ang - s0) % 360
            if (rel < (s1 - s0) + g or rel > 360 - g) and once(("ringarc", a["id"], d["id"])):
                W("%s: arc %s runs under (or within %d px of) the dot %s on its ring; cut it back short of the "
                  "dot (ring.arc() and the compiler do this for dots made with ring.dot())."
                  % (P, a["id"], DOT_GAP, d["id"]))


def _balance_check(P, ab, vis, W, once):
    """A plot from scene.plot() that sits in one side of the frame and leaves the other third or more empty:
    a plot pushed left of a side column that has nothing in it yet."""
    top = ab["y"] + ab["height"] * 0.17
    body = [n for n in vis if isinstance(n.get("x"), (int, float)) and isinstance(n.get("w"), (int, float))
            and n.get("y", 0) + n.get("h", 0) > top and not (n.get("kind") == "text" and n.get("y", 0) < top)]
    ids = {n.get("id") for n in vis}

    def is_plot(n):   # scene.plot(): an svg node with tick labels <id>_x... and <id>_y...
        i = str(n.get("id"))
        return n.get("kind") == "svg" and any(str(j).startswith(i + "_x") for j in ids) and \
            any(str(j).startswith(i + "_y") for j in ids)
    if not any(is_plot(n) and n.get("w", 0) * n.get("h", 0) > ab["width"] * ab["height"] * 0.08 for n in body):
        return
    m = SIDE_MARGIN if ab["width"] > ab["height"] else 80
    sx0, sx1 = ab["x"] + m, ab["x"] + ab["width"] - m
    x0 = min(n["x"] for n in body)
    x1 = max(n["x"] + n["w"] for n in body)
    empty = max(x0 - sx0, sx1 - x1)
    if empty > 0.3 * (sx1 - sx0) and once(("balance", P.split(" step")[0])):
        W("%s: the content sits on the %s and the %s %d%% of the frame is empty. Center it and make it bigger, or "
          "fill the other side from the first step (a plot next to an equation: give each a half, both shown "
          "together)." % (P, "left" if x0 - sx0 < sx1 - x1 else "right", "right" if x0 - sx0 < sx1 - x1 else "left",
                          100 * empty / (sx1 - sx0)))


def _dead_air_check(P, st, dur, nodes, vis_nodes, prev_vis_nodes, E):
    """A captioned step must have something on screen: not blank at its end after an exit, and not blank at
    its start while the first reveal waits."""
    acts = [a for a in (st.get("actions") or []) if isinstance(a, dict) and a.get("type") == "visibility"]
    if not vis_nodes:
        outs = [(a.get("offsetMs") or 0) + (a.get("durationMs") or 200) for a in acts if a.get("mode") in VIS_OUT]
        blank = dur - max(outs) if outs else dur
        if blank > DEAD_AIR_MS:
            E("%s: nothing is on screen for the last %d ms while the caption %r plays (dead air). Keep something "
              "visible: reveal the next thing in this step, end the exit with the step (offset it later), or merge "
              "the caption into the next step." % (P, blank, st.get("caption")))
        return
    shown = prev_vis_nodes if prev_vis_nodes is not None else {
        i for i in vis_nodes if not any((a.get("target") or {}).get("id") == i and a.get("mode") in VIS_IN
                                        for a in acts)}
    if not shown:
        ins = [(a.get("offsetMs") or 0) for a in acts if a.get("mode") in VIS_IN]
        first = min(ins) if ins else 0
        if first > DEAD_AIR_MS:
            E("%s: the screen is blank for the first %d ms of the step while the caption %r plays (dead air); "
              "reveal something at the start." % (P, first, st.get("caption")))


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
    if off > 0.15 * H_:
        # under a title: the content is horizontally centered and starts close under it
        tl = [n for n in vis if n.get("kind") == "text" and _is_bold(n.get("fontWeight")) and n["w"] >= 0.5 * W_
              and n["y"] - sy <= ab["y"] + 0.2 * H_ and n["h"] <= max(200, 0.18 * H_)]
        rest = {n["id"]: n for n in vis if n not in tl}
        b2 = _visible_bbox(rest, edges) if tl and rest else None
        if b2 is not None:
            gap = (b2[1] - sy) - max(n["y"] + n["h"] - sy for n in tl)
            if abs((b2[0] + b2[2]) / 2.0 - sx - acx) <= 0.1 * H_ and -10 <= gap <= 200:
                off = 0
    if off > 0.15 * H_ and once(("center", P)):
        W("%s: what shows sits %d px off the center of the safe area (%s); center it, or pan the camera to it "
          "(the Python helper's follow camera does this per step)." % (P, off, "%s%s" % (
              "high" if bcy < acy - 0.1 * H_ else "low" if bcy > acy + 0.1 * H_ else "",
              " left" if bcx < acx - 0.1 * H_ else " right" if bcx > acx + 0.1 * H_ else "")))
    vis_ids = {n["id"] for n in vis}
    byid = {n["id"]: n for n in vis}
    for eid, e in edges.items():
        if not e.get("label") or "fromXY" in e or e.get("from") not in vis_ids or e.get("to") not in vis_ids:
            continue
        if (e.get("trim", 1) or 0) <= 0.01 or (e.get("opacity", 1) or 0) <= 0.01:
            continue
        pts = edge_path(e, byid[e["from"]], byid[e["to"]])
        if len(pts) < 2:
            continue
        cx = _path_mid(pts)[0] - sx
        lw = label_width(e["label"], e.get("labelFontSize", 12))
        d = min(cx - lw / 2.0 - ab["x"], ab["x"] + W_ - cx - lw / 2.0)
        if d < LABEL_EDGE - 1 and once(("lside", eid)):
            W("%s: edge %s's label comes within %d px of the side of the frame; keep %d px (move the nodes in, "
              "shorten the label, or route the arrow on another side)." % (P, eid, d, LABEL_EDGE))
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
