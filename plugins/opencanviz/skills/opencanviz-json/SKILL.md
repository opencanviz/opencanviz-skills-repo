---
name: opencanviz-json
description: Write valid openCanviz video/diagram JSON that imports cleanly through Create > Import > Paste JSON or Mermaid on opencanviz.com, then plays and exports correctly. Use when asked to create or edit an openCanviz project as JSON, to turn a script or outline into an openCanviz video file, or to fix an openCanviz JSON file that imports but plays wrongly.
---

# openCanviz JSON

openCanviz turns a JSON file into an animated, narrated video. The user pastes your JSON into **Import** on https://opencanviz.com/create and clicks **Import project**. Import does not validate fields, so a file that parses can still play wrongly. Follow the rules below and validate before you answer.

**If you can run Python, use `scripts/opencanviz.py` (see `examples/*.py`); otherwise write JSON by hand following the rules below.** The helper applies every rule on this page for you and refuses to save a file that breaks one.

## Pick the visual that fits the topic

Boxes and arrows are for flows, systems and processes only. Everything else has a better shape; each row names the helper call and the example that shows it.

| The topic is | Show it as | Helper (scene / step) | Example |
| --- | --- | --- | --- |
| A flow, a system, a pipeline, a cycle | Boxes and labeled arrows | `box`, `arrow` / `reveal`, `draw` | `flow`, `two_scenes`, `portrait_stack` |
| Amounts compared across categories | Bar chart, values count up | `bar_chart` / `grow` | `bar_chart` |
| A trend over time | Line chart that draws itself | `line_chart` / `extend` | `line_chart` |
| Two measures per item, clusters | Scatter chart, dots move | `scatter` / `scatter_to` | `scatter_grid` |
| Parts of a whole | Pie or donut | `pie` / `sweep` | `pie` |
| Sorting, searching, two pointers | Array with pointers | `array`, `pointer` / `swap`, `color`, `point`, `bracket` | `bubble_sort` |
| A tree, a linked list, a graph | The structure itself | `tree`, `linked_list`, `graph` / `color`, `point`, `append` | `data_structures` |
| A table, a matrix, dynamic programming | Grid | `grid` / `set_cell`, `color` | `scatter_grid` |
| Code, line by line | Code panel plus variables | `code`, `variable` / `highlight`, `assign` | `code_walkthrough` |
| Who calls whom, in order | Sequence diagram | `sequence`, `message` / `draw`, `activate` | `sequence` |
| History, dates, milestones | Timeline | `timeline` / `event` | `timeline` |
| Before and after, A versus B | Two panels | `panels` | `before_after` |
| Tips, rules, steps of advice | Bullets with check marks | `bullets` / `reveal` | `bullets` |
| One big number, a percentage done | Counter, progress bar | `counter`, `progress` / `set` | `counter_progress` |
| Something travelling a route | A node on a path, a packet on an arrow | `path` / `follow`, `packet` | `path_follow` |

## Files in this skill

- `schema.json`: the JSON Schema (draft 2020-12), the same as https://opencanviz.com/schema/v1.json. Validate every file against it.
- `scripts/opencanviz.py`: a Python 3.9+ builder and validator (standard library only; also checks `schema.json` when `jsonschema` is installed).
- `examples/minimal.json`: two boxes, one arrow, two steps. The smallest correct project.
- `examples/flow.json`: a four-step 16:9 flow diagram with a title, captions and narration.
- `examples/two_scenes.json`: two scenes, a crossfade, a typewriter title, a skip arrow on its own lane, a removed edge and a camera zoom.
- `examples/short.json`: a 9:16 Short in the flat single-scene form, with stacked cards and a progress bar.
- `examples/science_explainer.json`: three narrated scenes with labeled arrows and a two-row comparison.
- `examples/portrait_stack.json`: a 9:16 Short with a vertical chain of cards and labeled arrows.
- Recipe examples, one per visual in the table above: `bar_chart`, `line_chart`, `scatter_grid`, `pie`, `bubble_sort`, `data_structures`, `code_walkthrough`, `sequence`, `timeline`, `before_after`, `bullets`, `counter_progress`, `path_follow`.
- Each example has a matching `.py` that writes it. `tests/test_examples.py` runs them all.

Read the example closest to the request before you write. Copy its structure, not its content. Every example passes the schema, the rules below, and plays correctly in openCanviz.

Human docs: https://opencanviz.com/docs/json-overview, https://opencanviz.com/docs/json-schema-reference and https://opencanviz.com/docs/json-rules-for-ai-agents

## Python helper

```python
import sys; sys.path.insert(0, "<skill folder>/scripts")
from opencanviz import Project
p = Project("Title", aspect="16:9")              # or "9:16", "1:1"; theme="light"; voice="nova"
s = p.scene("Scene name")                          # transition="crossfade" joins it to the previous scene
title, body = s.title("How a request is served")   # every video opens with a title; body = the rest of p.area()
cells = body.flow(3, labels=["asks", "reads"])     # also row/column/stack/grid/cut_top; gaps fit the labels
a, b = s.box("Client", at=cells[0]), s.node("cylinder", "DB", at=cells[1])
link = s.arrow(a, b, "asks")                       # route="below": skip arrow on its own lane; route="around": closes a cycle
s.step("Caption, also the narration.").reveal(title).reveal(a)  # .hide .move .set .typewrite .camera .focus .remove .wait
s.step("Next beat.").reveal(b).draw(link)          # reveal a node before drawing an arrow to it
p.save("out.json")                                 # validates; raises with a fix hint and writes nothing on error
```

`p.area()` is the artboard minus the margin and the caption band. `rect.cut_top(h)` returns `(band, rest)` but `rect.cut_bottom(h)` returns `(rest, band)`; two visible nodes on the same rect are refused. Fonts are fitted to their boxes. Ids get the `s1_` prefix. Step durations follow the narration length. The camera follows what is visible so each step's content sits centered in the safe area, a lone first node included (`Project(..., follow=False)` turns this off, as does any explicit `.camera`). A title (from `s.title`, or bold text across the top) stays fixed on screen; under it the camera frames the scene's finished layout from the first step when it fits, so things appear in their final places and nothing shifts. A title shown alone is centred as a title card. The checker warns when the first scene does not open with a title. `draw()` on a labeled edge draws an unlabeled copy (`<id>_line`); when the line is done the label appears with its opaque chip at once and the copy goes in the same frame. Rows keep 120 px side margins in landscape. To check a file written by hand, run `python3 scripts/opencanviz.py check out.json`.

## Recipes

Each recipe is a `scene.*` call that builds the visual inside a rect and `step.*` calls that animate it. They write only fields openCanviz plays and exports correctly, so use them rather than writing these node kinds by hand. Reveal the visual first (`step.reveal(node)`), then animate it in a later step: a recipe action in step 0 raises, because a change cannot tween before the scene has a previous state.

```python
title, body = s.title("Bubble sort")                          # reveal it in step 0
chart = s.bar_chart([("Python", 49), ("Java", 30)], at=body, suffix="M")  # labels, baseline, counting values
s.step("Two languages.").reveal(chart)
s.step("Python grows first.").grow(chart, 0)                 # one bar; grow(chart) grows the rest
line = s.line_chart(pts, at=body, x_ticks=[1800, 1900, 2000], y_ticks=[0, 4, 8], y_title="billions",
                    notes={3: "2 billion"})                  # .extend(line, upto) draws on to a point; a dot marks the tip
arr = s.array([5, 2, 8], at=body.inset(140, 40))             # .swap(arr, 0, 1) .color(arr, {0: c}) .bracket(arr, 2, 2, "sorted")
j = s.pointer(arr, 0, label="j")                             # .point(j, 1); also tree/list/graph values, grid (r, c)
tree = s.tree({"8": ["4", "12"], "4": ["2", "6"]}, at=body)  # sized for you; .color(tree, {"4": c})
lst = s.linked_list([3, 7], at=body, capacity=3)             # .append(lst, 9); capacity = the most it will hold
g = s.graph({"A": (0, .5), "B": (1, .5)}, [("A", "B")], at=body)  # .color(g, {...}, edges={("A", "B"): c})
grid = s.grid([[1, 1], [1, ""]], at=body)                    # .set_cell(grid, 1, 1, 2)
left, right = body.split(0.68)                               # code left, variables right
r_box, i_box = right.column(2, gap=40, h=120)
code = s.code(source, at=left)                               # .highlight(code, 3), 1-based lines
i = s.variable("i", 1, at=i_box)                             # .assign(i, 2); box only as wide as name + value
web, api = s.sequence(["Browser", "Server"], at=body)        # m = s.message(web, api, "GET /"); .draw(m)
tl = s.timeline([(1961, "Program starts"), (1969, "Moon landing")], at=body)  # .event(tl) once per event: the bar grows in 600 ms, the new dot lands as it ends; 4+ alternate
before, after = s.panels(["Before", "After"], at=body)       # lay out inside before.content
pts = s.bullets(["Use 12+ characters", "Never reuse"], at=body)  # reveal one per step
n = s.counter(2048, at=r, suffix=" MB"); bar = s.progress(0, at=r2)  # .set(bar, value=1) fills it over the step
# .set(box, fill="#0c4a6e") recolours in 350 ms; .move(box, x=.., y=..) moves in 600 ms
pie = s.pie([("Rent", 40), ("Food", 25)], at=body, donut=0.55)  # .sweep(pie) reveals it; do not reveal it yourself
road = s.path([(-600, 0), (0, -200), (600, 0)])              # .follow(parcel, road); .packet(edge) sends a dot
```

What the recipes take care of, and what to keep in mind if you write these kinds by hand:

- **Arrays:** always build them with `scene.array`. It turns openCanviz's index row off (`cellShowIndices: false`; that row resets the canvas alpha, so the array could not fade) and draws the indices as text nodes. `swap` writes the swapped `cellValues` plus an `algoSwap` action of 600 ms from the step start, so the values hop past each other while the narration says so. The hop height is fixed by openCanviz (no field for it). Use distinct values in an array you swap.
- **Pointers** sit above the cells (`side="top"`); a bottom pointer would cover the index row. `point` writes the new `pointerTargetIndex` (or row/col) plus a 350 ms `transformTween` on it; without the tween the pointer and its highlight frame crawl across the whole step. A grid pointer covers the cell above its target, so mark grid cells with `color` instead.
- **Colors** on cells, grid cells and tree/list/graph nodes change in 350 ms from the step start (a `transformTween` whose `to` holds the new `cellColors`, `gridColors` or `nodeColors`). Graph edge colours cannot be timed and take the whole step. Every cell and node gets an explicit hex, never `null`: an uncoloured one is written as the structure's `fill` (default `#1e293b`), because openCanviz keeps a cell tweened to `null` in its old color for the whole step. The validator warns on a `null` in a colour tween.
- **Code highlight:** the code node carries `"_animatedProps": {"highlightedLines": false}`, the one internal field you should write. Without it openCanviz shows the old and the new lines lit for the whole step. Keep it when you edit a code node.
- **Paths:** `pathFollow` needs `length` (total px) and `cum` (length so far at each point, from 0) on the path, or the exported video leaves the node where it is. `scene.path` fills them.
- **Fonts:** each structure kind has its own font field (`cellFontSize`, `nodeFontSize`, `gridCellFontSize`, `labelFontSize`, `fontSize`); without it the text renders at 11 to 14 px. The recipes size every one for the frame.
- Charts, trees, timelines and code panels size and center themselves in the rect you pass; give them the whole body rect.
- **Readable floor:** at 1080p landscape, text of 4+ words at least 34 px, code 30, chart ticks and short labels 28, variables 34; in portrait 1.4x that (48, 42, 39, 48). The recipes never go lower: `code()`, `bullets()` and `timeline()` raise when the text cannot fit at the floor, so shorten it (timeline events of 2 to 6 words) or give it a bigger rect. The checker warns on hand-written text under the floor.
- **Stable layout:** timelines, code panels, bullets, panels and variables are laid out at their final size from step 0, and the camera frames that final layout, so nothing shifts as items appear. `scene.reserve(node, ...)` does the same for your own nodes. `rect.split(0.68)` returns a left and a right rect side by side.
- **Line charts:** openCanviz grows a chart series over the whole step and cannot time it, so `extend` leaves the series at the first point and draws each new stretch as a straight edge through the points (`<id>_run<upto>`, `waypoints` = the points) with a linear 0.6 to 1.4 s `edgeTween` from the step start; the tip dot rides it with a `pathFollow` of the same length, each note fades in as the line reaches its point, and the step lasts at least 1.5 s past the last note so it stays on screen. The axes are the edges `<id>_line` and `<id>_line_2`.

## Workflow

1. **Plan.** Pick the aspect ratio (16:9 = 1920 x 1080, 9:16 = 1080 x 1920, 1:1 = 1080 x 1080). Split the topic into scenes, and each scene into 2 to 6 steps. Write one caption line per step, about 8 to 20 words.
2. **Lay out.** Center the artboard on the origin (`x = -width/2`, `y = -height/2`). Place every node inside it with a margin of at least 60 px (120 px at the sides in landscape), above the caption band, centered in that safe area, following the layout rules below. A node's `x`, `y` is its top-left corner.
3. **Write step 0** of each scene as a full snapshot: every node and edge the scene will ever show, with nodes that appear later at `"opacity": 0` and edges that draw in later at `"trim": 0`. Copy the same nodes and edges into the scene's `nodes` and `edges`.
4. **Write later steps** as deltas: `"delta": true`, then only `id` plus the changed fields. Add actions for timing.
5. **Add narration**: one clip per step, `text` equal to the caption, `stepIndex` matching the step.
6. **Validate** with `python3 scripts/opencanviz.py check out.json` if you can run Python (it also runs `schema.json` when `jsonschema` is installed), or against `schema.json` with any real validator. Then walk the checklist at the end by hand.
7. **Fix** every error and validate again.
8. **Output** the JSON alone in one ```json code block, with no comments and no trailing commas. Tell the user to paste it into Import, then open the Narration panel and click **Generate All Scenes** to voice it.

## Document shape

```json
{
  "$schema": "https://opencanviz.com/schema/v1.json",
  "title": "Project name",
  "artboard": { "x": -960, "y": -540, "width": 1920, "height": 1080, "background": "#0f172a" },
  "sceneNames": ["Intro", "Details"],
  "transitions": [{ "kind": "crossfade", "durationMs": 600 }],
  "showCaptions": true,
  "diagrams": [
    {
      "nodes": [],
      "edges": [],
      "steps": [
        { "id": "s1_step0", "durationMs": 2500, "caption": "...", "nodes": [], "edges": [], "actions": [] },
        { "id": "s1_step1", "delta": true, "durationMs": 2500, "caption": "...", "nodes": [], "edges": [], "actions": [] }
      ],
      "narration": [
        { "id": "s1_n0", "text": "...", "stepIndex": 0, "voice": { "provider": "openai", "voiceId": "alloy", "voiceName": "Alloy" } }
      ]
    }
  ]
}
```

`transitions[i]` joins scene `i` to scene `i+1`; use `null` for a hard cut. A one-scene file may instead put `nodes`, `edges`, `steps` and `narration` at the top level. `$schema` is optional and ignored by Import.

## Hard rules

1. Always include `artboard` with `x`, `y`, `width`, `height` and `background`. Without it the frame is guessed from the node bounds and is misplaced when coordinates are negative.
2. Every scene has at least one step. A scene with no steps renders nothing in playback and export.
3. Every step has `durationMs` (milliseconds, greater than 0) plus `nodes` and `edges` arrays (empty arrays are fine in delta steps).
4. Step 0 lists every node and every edge in full. The scene's `nodes` and `edges` equal step 0's.
5. Put `"delta": true` on every step after step 0. A delta entry is `id` plus only the changed fields. Changes carry forward to later steps.
6. Ids are unique within a scene and identical in every step. Prefix ids per scene (`s1_`, `s2_`) so they are unique across the project.
7. Edge `from` and `to` must be ids in the scene's `nodes`. Otherwise the edge is deleted when the project opens. A node that first appears through `addNodes` can only be joined by an edge in `addEdges` of the same or a later step.
8. Every node needs `id`, `kind`, `x`, `y`, `w`, `h`. Nothing smaller than 10 x 10 px, and nothing under 2 px in either direction: it is not drawn. Draw lines as edges, not thin rects.
9. Revealing a node: set `"opacity": 1` for it in the step's `nodes` AND add a `fadeIn` or `slideIn*` action. If the snapshot keeps opacity 0, the node fades back out in the next step.
10. Hiding a node: set `"opacity": 0` and use a `fadeOut` or `slideOut*` action, or list it in `removeNodeIds`. Do not hide with an opacity `transformTween`.
11. Moving or recolouring a node: set the new `x`/`y` (or `fill`, `stroke`, `color`) in the delta step **and** a short `transformTween` with the same end values; on its own the change plays across the whole step and lags the narration (the validator warns). The helper's `set()` times colours at 350 ms and `move()` / `set(x=..)` positions at 600 ms from the step start (`duration=` / `offset=` to change it, `move(..., duration="step")` for a deliberate slow glide). The tween: `{"type":"transformTween","target":{"kind":"node","id":".."},"to":{"x":..,"y":..},"durationMs":..,"offsetMs":..}` with the same end values. `from.x` and `from.y` are ignored. Do not use `isRelative`, `dx` or `dy`.
12. An action controls only what it covers: `transformTween` and `edgeTween` cover the keys in `to`; `visibility` covers `opacity` (slides also cover `x`, `y`). Every other change in the step tweens automatically over the full step. Make the snapshot's end values match the action's `to`. A `transformTween` on `cellColors`, `gridColors`, `nodeColors`, `cellValues`, `gridValues` or `highlightedLines`, and an `algoSwap`, are timed only when the step has `"easing"` (e.g. `"ease"`); without it the swap snaps and the colour takes the whole step.
13. Drawing an edge in: start it at `"trim": 0`, set `"trim": 1` in the reveal step's `edges`, and add `{"type":"edgeTween","target":{"kind":"edge","id":".."},"from":{"trim":0},"to":{"trim":1},"durationMs":700}`.
   Draw an edge in only in the same step as its later end node, or after. An arrow that draws while one of its ends is still hidden points at empty space.
14. Edge line width is `width`. `strokeWidth` is for node outlines only.
15. Colors are hex strings. `fillOpacity` does nothing; to dim, lower `opacity` or pick a darker hex.
16. Leave out fields openCanviz fills in: `_addedNodeIds`, `_removedNodeIds`, `_addedEdgeIds`, `_removedEdgeIds`, `_animatedProps` (except `{"highlightedLines": false}` on a code node, see Recipes), `_selected`, `illuOf`, `imageFailed`, and on narration `audioData`, `audioUrl`, `audioDurationMs`, `words`.
17. Plain JSON only: no comments, no trailing commas, no `NaN`, no functions.
18. A delta step that changes edges must also list at least one node (an unchanged one is fine). Otherwise openCanviz blanks every node for that step.
19. Every edge gets `"animationStyle": "none"` unless you want the motion; without it the line runs marching dashes forever.
20. An `edgeTween` that trims an edge from 0 to 1 needs `"trim": 1` for that edge in the same step's snapshot.
21. Turn glow off with `"noGlow": true`; `"glow": 0` is ignored.
22. One-color iconify icons (`mdi:`, `lucide:`, `tabler:` ...) render black unless the node has `"iconStyle": "solid"` and a `fill` hex. Multicolor sets (`logos:`, `skill-icons:`, `devicon:`, `twemoji:`, `noto:`, `flat-color-icons:`) need neither.
23. Never use `sketchMode`, `kind: "icon"` or `kind: "lottie"`; they render badly or not at all in the export. Icons are `kind: "svg"` with an iconify asset.
24. Change `typeProgress` only through a `transformTween` from 0 to 1 (the helper's `typewrite`); a bare change jumps.

## Layout rules

These keep the video readable once captions and arrows are on screen. The helper checks all of them.

25. **Caption band.** Keep every node out of the bottom 20% of the frame in landscape and the bottom 30% in portrait (captions wrap to 3 or 4 lines there). For 16:9 that is `y + h <= 324`; for 9:16, `y + h <= 384`.
26. **Fill the frame.** At the last step of a scene the diagram should cover about 60 to 75% of the safe area (artboard minus margin and caption band). No thin row with big empty bands: use bigger boxes or a second row.
27. **Text fits its box.** Width: characters x 0.55 x font size per line, within `w` minus padding. Height: lines x font size x 1.2 plus 16 px padding, within `h`. Shapes have less room inside (a circle about 72%, a diamond about 50%).
28. **Edge labels are readable.** `labelFontSize` at least 22 in landscape and 28 in portrait, with `"labelBgColor"` set to the background color so the label masks the line behind it.
29. **Gaps leave a real arrow.** Between two connected nodes leave at least 100 px. For a labeled edge leave the label chip (characters x 0.6 x `labelFontSize` + 24; vertical links: font size x 1.2 + 10) plus 120 px of visible line, so the chip never covers most of the arrow. When a chain does not fit in one row, wrap it to a second row running back the other way (a snake), so links still join neighbours.
30. **No edge crosses a node.** An edge may not pass over any node except its two ends. Join neighbours, and send a skip connection along its own lane: `"fromPort": "S", "toPort": "S", "lineType": "elbowed"` (or `N`/`N`) with nothing in the lane.
31. **Labels appear after their line.** The engine puts a label at the middle of the drawn part, so it slides with the tip and shows before the arrow. For a labeled edge, add an unlabeled copy (`<id>_line`, same ends, no label fields) listed before it: the copy starts at `"trim": 0, "opacity": 1` and draws in with `{"trim":0}` to `{"trim":1}`. The labeled edge sits at `"trim": 1, "opacity": 0` and switches on once the line is done: `{"type":"edgeTween","from":{"trim":1,"opacity":0},"to":{"trim":1,"opacity":1},"durationMs":40,"offsetMs":<end of the draw>,"ease":"step"}`, so the chip is opaque from its first frame (openCanviz draws the chip at the edge's opacity, and a slow fade shows the line through it). Switch the copy to opacity 0 with the same offset and `"ease":"step"`. The helper's `draw()` writes all of this. To take a labeled edge away, tween `trim` and `opacity` to 0 rather than using `removeEdgeIds`.
32. **Reveal before you draw.** Within a step, an arrow's `edgeTween` starts no earlier than the reveal of the node it points to (same or later `offsetMs`).
33. **Center what shows.** At every step the visible content's center sits within 15% of the frame height of the safe area's center. Lay the group out centered, or add a step `camera` (`x`, `y` = content center minus safe-area center, `zoom` 1) that pans as the content grows. A lone first node starts centered, not in a corner.
34. **Cycles close.** For a cycle topic (water cycle, feedback loop, Krebs cycle), join the last node back to the first with an elbowed arrow around the outside of the group (`S`/`S` or `N`/`N`, label below or above the lane), not through the middle. In Python: `s.arrow(last, first, "repeats", route="around")`.

## Timing model

- A step lasts `durationMs`; 0 or missing counts as 900. A scene lasts the sum of its steps; scenes play back to back. Once narration is recorded, each step stretches to fit its audio.
- Inside a step, an action starts at `offsetMs` (default 0) and runs for `durationMs` (visibility default 200). Keep `offsetMs + durationMs` within the step.
- Numbers and colors that differ from the previous step (`x`, `y`, `w`, `h`, `opacity`, `fontSize`, `value`, `fill`, `stroke`, `color`, `labelColor`) tween over the whole step with the step's `easing` (default `ease`) unless an action covers them. Give every visible colour or position change its own short `transformTween`.
- `transitions` inside a step, keyed by node id, can be `"instant"` to snap a change or `"fade"` to cross-fade it.
- Camera: `"camera": {"x": .., "y": .., "zoom": 1.4}` on a step, with `cameraDurationMs`. `x`, `y` is the world point at the center of the view; zoom 1 is 100 percent.

## Actions

| type | key fields | notes |
| --- | --- | --- |
| `visibility` | `mode`, `durationMs`, `offsetMs`, `ease`, `slideDistance` (150) | modes: `fadeIn`, `fadeOut`, `show`, `hide`, `slideInLeft/Right/Up/Down`, `slideOutLeft/Right/Up/Down` |
| `transformTween` | `from`, `to`, `durationMs`, `offsetMs`, `ease` | props: `x`, `y`, `w`, `h`, `scaleX`, `scaleY`, `rotationZ`, `opacity`, `fill`, `stroke`, `strokeWidth`, `typeProgress`, `value`, `blur`, `color`, `labelColor`, `pointerColor`, `rangeColor`, `pointerTargetIndex`/`Row`/`Col`, `rangeStart`/`End`; algo fields `cellColors`, `gridColors`, `nodeColors`, `cellValues`, `gridValues`, `highlightedLines` (step needs `easing`) |
| `edgeTween` | `from`, `to`, `durationMs`, `offsetMs`, `ease` | props: `trim`, `trimStart`, `stroke`, `width`, `opacity` |
| `algoSwap` | `indices` [i, j], `durationMs`, `offsetMs`, `ease` | on an `algo-array`; the step's `cellValues` hold the swapped values; step needs `easing` |
| `positionTween` | `from`, `to` (points), `durationMs` | prefer the snapshot plus `transformTween` |
| `pathFollow` | `pathId`, `from`, `to` (0..1), `rotateToTangent` | path lives in the scene's `paths` with `points`, `length` and `cum` |

`target` is `{"kind":"node","id":".."}` or `{"kind":"edge","id":".."}`. Slide directions name the side: `slideInLeft` enters from the left, `slideInUp` enters from above, `slideInDown` from below, `slideOutLeft` exits to the left.

Easings: `linear`, `ease`, `ease-in`, `ease-out`, `spring`, `bounce`, `elastic`, `back`, `back-in`, `step`.

## Useful nodes

- Box: `{"id":"api","kind":"rect","x":-160,"y":-90,"w":320,"h":180,"cornerRadius":16,"fill":"#1e293b","stroke":"#38bdf8","strokeWidth":3,"label":"API","labelColor":"#f8fafc","labelFontSize":40}`
- Text: `{"id":"title","kind":"text","x":-700,"y":-460,"w":1400,"h":120,"text":"Title","fontSize":72,"fontWeight":700,"color":"#f8fafc","textAlign":"center"}`. Use `\n` for line breaks. Typewriter: tween `typeProgress` from 0 to 1.
- Database: `kind: "cylinder"`. Also `circle`, `diamond`, `triangle`, `star`, `callout`, `chevron`, `funnel`.
- Progress bar: `kind: "progress"` with `value` 0..1 and `progressColor`.
- Icon: `{"kind":"svg","asset":{"type":"icon","source":"iconify","ref":"mdi:database"},"iconStyle":"solid","fill":"#38bdf8", ...}`. The icon loads when the project opens in the editor.
- Edge: `{"id":"a_to_b","from":"a","to":"b","fromPort":"E","toPort":"W","stroke":"#94a3b8","width":4,"arrow":"end"}`. Optional `strokeStyle` (`dashed`), `lineType` (`curved`, `elbowed`), `label`, `animationStyle` (`flow`, `ball`, `pulse`).

Full field lists and enums are in `schema.json`.

## Common mistakes

| Mistake | What happens | Fix |
| --- | --- | --- |
| No `artboard` | Frame lands in the wrong place | Always include it, centered on the origin |
| Scene with `"steps": []` | Blank scene in playback and export | At least one step |
| Revealed node left at opacity 0 in the snapshot | It fades in, then fades back out next step | Set `"opacity": 1` in that step's `nodes` |
| Edge to a node id that is not in `nodes` | Edge deleted when the project opens | Add the node to step 0 at opacity 0, or use `addEdges` |
| `strokeWidth` on an edge | Ignored | Use `width` |
| Later step relists every node in full without `delta` | Read as a new full snapshot; omitted fields are lost | `"delta": true`, changed fields only |
| `from.x` in a transformTween | Ignored | Put the start position in the previous step |
| Tiny dots or 1 px lines as nodes | Not drawn | 10 x 10 px minimum; draw lines as edges |
| Caption with no narration clip | Nothing to voice later | One clip per step, same text |
| Copying a backup's `audioData` or `_animatedProps` | Bloated or stale data | Leave internal fields out |
| Five boxes in one row with 12 px edge labels | Labels collide with boxes and are unreadable | Two rows, gaps sized for the labels, `labelFontSize` 22+ |
| Arrow from box 1 to box 3 in a row | It runs over box 2 | Same-side ports and `elbowed`, on a lane below or above |
| Nodes in the bottom fifth of the frame | Captions cover them | Keep the caption band clear |
| Arrow draws, then its end node fades in | It points at empty space | Reveal the node first, then draw |
| Label chip wider than the gap | A 30 px stub of arrow under a label | Chip width + 120 px of gap |
| Nodes filled from the top-left | Bottom half of the frame empty | Center the group, or pan the camera to it |
| Boxes and arrows for a chart, a sort, a timeline or code | A generic diagram that teaches nothing | Pick the visual from the table at the top |
| `cellShowIndices` left on, or an `algoSwap` in a step without `easing` | The array cannot fade; the swap snaps | `scene.array` and `step.swap` |
| Delta step with edges and no nodes | Every node blanks for that step | List one node too |
| Edge without `animationStyle` | Marching dashes forever | `"animationStyle": "none"` |
| `glow: 0`, `sketchMode`, `kind: "icon"`, lottie | Ignored or broken in the export | `noGlow: true`, plain style, `kind: "svg"` |
| Path without `length` and `cum` | The node never moves in the export | `scene.path` |

## Checklist before you answer

- [ ] Parses as JSON and validates against `schema.json`.
- [ ] `title` and a full `artboard` are present, and the first scene opens with an on-screen title.
- [ ] Every scene has `nodes`, `edges` and at least one step; the scene lists equal step 0.
- [ ] Steps after 0 have `"delta": true` and only changed fields.
- [ ] All ids unique per scene and stable; every edge end exists.
- [ ] Every node is at least 10 x 10 px and inside the artboard.
- [ ] Every revealed node has `opacity` 1 in its reveal step; every drawn-in edge has `trim` 1.
- [ ] Every action ends within its step, and its `to` values match the snapshot.
- [ ] One narration clip per step; `transitions` has one entry fewer than there are scenes.
- [ ] Caption band clear; diagram fills about 60 to 75% of the safe area; text fits its boxes.
- [ ] Text at or above the readable floor (34 body, 30 code, 28 ticks, 34 variables at 1080p landscape; 1.4x in portrait).
- [ ] Edge labels 22 px+ (28 px+ portrait) with `labelBgColor`; gaps fit them; no edge crosses a node.
- [ ] Labeled edges fade in after an unlabeled copy draws the line; arrows draw after their end nodes appear.
- [ ] Each step's content is centered in the safe area; 120 px side margins in landscape; every labeled arrow shows 120 px+ of line.
- [ ] The visual fits the topic (table at the top); boxes and arrows only for flows and systems.
- [ ] Every edge has `animationStyle`; no delta step lists edges without a node; no `glow: 0`, `sketchMode`, `kind: "icon"` or lottie.
- [ ] No internal fields (only the code node's `_animatedProps` flag), comments or trailing commas.
