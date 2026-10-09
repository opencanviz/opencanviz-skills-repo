---
name: opencanviz-json
description: Write valid openCanviz video/diagram JSON that imports cleanly through Create > Import > Paste JSON or Mermaid on opencanviz.com, then plays and exports correctly. Use when asked to create or edit an openCanviz project as JSON, to turn a script or outline into an openCanviz video file, or to fix an openCanviz JSON file that imports but plays wrongly.
---

# openCanviz JSON

openCanviz turns a JSON file into an animated, narrated video. The user pastes your JSON into **Import** on https://opencanviz.com/create and clicks **Import project**. Import does not validate fields, so a file that parses can still play wrongly. Follow the rules below and validate before you answer.

## Files in this skill

- `schema.json`: the JSON Schema (draft 2020-12), the same as https://opencanviz.com/schema/v1.json. Validate every file against it.
- `examples/minimal.json`: two boxes, one arrow, two steps. The smallest correct project.
- `examples/flow.json`: a four-step 16:9 flow diagram with captions and narration.
- `examples/two_scenes.json`: two scenes, a crossfade, a typewriter title, `addNodes`, `addEdges`, `removeEdgeIds` and a camera zoom.
- `examples/short.json`: a 9:16 Short in the flat single-scene form.

Read the example closest to the request before you write. Copy its structure, not its content. Every example passes the schema and plays correctly in openCanviz.

Human docs: https://opencanviz.com/docs/json-overview, https://opencanviz.com/docs/json-schema-reference and https://opencanviz.com/docs/json-rules-for-ai-agents

## Workflow

1. **Plan.** Pick the aspect ratio (16:9 = 1920 x 1080, 9:16 = 1080 x 1920, 1:1 = 1080 x 1080). Split the topic into scenes, and each scene into 2 to 6 steps. Write one caption line per step, about 8 to 20 words.
2. **Lay out.** Center the artboard on the origin (`x = -width/2`, `y = -height/2`). Place every node inside it with a margin of at least 60 px. A node's `x`, `y` is its top-left corner.
3. **Write step 0** of each scene as a full snapshot: every node and edge the scene will ever show, with nodes that appear later at `"opacity": 0` and edges that draw in later at `"trim": 0`. Copy the same nodes and edges into the scene's `nodes` and `edges`.
4. **Write later steps** as deltas: `"delta": true`, then only `id` plus the changed fields. Add actions for timing.
5. **Add narration**: one clip per step, `text` equal to the caption, `stepIndex` matching the step.
6. **Validate** the file against `schema.json` with a real validator if you can run code (for example Python `jsonschema.Draft202012Validator`). Then walk the checklist at the end by hand.
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
11. Moving a node: set the new `x`/`y` in the delta step. It tweens across the whole step on its own. For tighter timing add `{"type":"transformTween","target":{"kind":"node","id":".."},"to":{"x":..,"y":..},"durationMs":..,"offsetMs":..}` with the same end values. `from.x` and `from.y` are ignored. Do not use `isRelative`, `dx` or `dy`.
12. An action controls only what it covers: `transformTween` and `edgeTween` cover the keys in `to`; `visibility` covers `opacity` (slides also cover `x`, `y`). Every other change in the step tweens automatically over the full step. Make the snapshot's end values match the action's `to`.
13. Drawing an edge in: start it at `"trim": 0`, set `"trim": 1` in the reveal step's `edges`, and add `{"type":"edgeTween","target":{"kind":"edge","id":".."},"from":{"trim":0},"to":{"trim":1},"durationMs":700}`.
   Draw an edge in only in the same step as its later end node, or after. An arrow that draws while one of its ends is still hidden points at empty space.
14. Edge line width is `width`. `strokeWidth` is for node outlines only.
15. Colors are hex strings. `fillOpacity` does nothing; to dim, lower `opacity` or pick a darker hex.
16. Leave out fields openCanviz fills in: `_addedNodeIds`, `_removedNodeIds`, `_addedEdgeIds`, `_removedEdgeIds`, `_animatedProps`, `_selected`, `illuOf`, `imageFailed`, and on narration `audioData`, `audioUrl`, `audioDurationMs`, `words`.
17. Plain JSON only: no comments, no trailing commas, no `NaN`, no functions.

## Timing model

- A step lasts `durationMs`; 0 or missing counts as 900. A scene lasts the sum of its steps; scenes play back to back. Once narration is recorded, each step stretches to fit its audio.
- Inside a step, an action starts at `offsetMs` (default 0) and runs for `durationMs` (visibility default 200). Keep `offsetMs + durationMs` within the step.
- Numbers and colors that differ from the previous step (`x`, `y`, `w`, `h`, `opacity`, `fontSize`, `value`, `fill`, `stroke`, `color`, `labelColor`) tween over the whole step with the step's `easing` (default `ease`).
- `transitions` inside a step, keyed by node id, can be `"instant"` to snap a change or `"fade"` to cross-fade it.
- Camera: `"camera": {"x": .., "y": .., "zoom": 1.4}` on a step, with `cameraDurationMs`. `x`, `y` is the world point at the center of the view; zoom 1 is 100 percent.

## Actions

| type | key fields | notes |
| --- | --- | --- |
| `visibility` | `mode`, `durationMs`, `offsetMs`, `ease`, `slideDistance` (150) | modes: `fadeIn`, `fadeOut`, `show`, `hide`, `slideInLeft/Right/Up/Down`, `slideOutLeft/Right/Up/Down` |
| `transformTween` | `from`, `to`, `durationMs`, `offsetMs`, `ease` | props: `x`, `y`, `w`, `h`, `scaleX`, `scaleY`, `rotationZ`, `opacity`, `fill`, `stroke`, `strokeWidth`, `typeProgress`, `value`, `blur` |
| `edgeTween` | `from`, `to`, `durationMs`, `offsetMs`, `ease` | props: `trim`, `trimStart`, `stroke`, `width`, `opacity` |
| `positionTween` | `from`, `to` (points), `durationMs` | prefer the snapshot plus `transformTween` |
| `pathFollow` | `pathId`, `from`, `to` (0..1), `rotateToTangent` | path lives in the scene's `paths` |

`target` is `{"kind":"node","id":".."}` or `{"kind":"edge","id":".."}`. Slide directions name the side: `slideInLeft` enters from the left, `slideInUp` enters from above, `slideInDown` from below, `slideOutLeft` exits to the left.

Easings: `linear`, `ease`, `ease-in`, `ease-out`, `spring`, `bounce`, `elastic`, `back`, `back-in`, `step`.

## Useful nodes

- Box: `{"id":"api","kind":"rect","x":-160,"y":-90,"w":320,"h":180,"cornerRadius":16,"fill":"#1e293b","stroke":"#38bdf8","strokeWidth":3,"label":"API","labelColor":"#f8fafc","labelFontSize":40}`
- Text: `{"id":"title","kind":"text","x":-700,"y":-460,"w":1400,"h":120,"text":"Title","fontSize":72,"fontWeight":700,"color":"#f8fafc","textAlign":"center"}`. Use `\n` for line breaks. Typewriter: tween `typeProgress` from 0 to 1.
- Database: `kind: "cylinder"`. Also `circle`, `diamond`, `triangle`, `star`, `callout`, `chevron`, `funnel`.
- Progress bar: `kind: "progress"` with `value` 0..1 and `progressColor`.
- Icon: `{"kind":"svg","asset":{"type":"icon","source":"iconify","ref":"mdi:database"}, ...}`. The icon loads when the project opens in the editor.
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

## Checklist before you answer

- [ ] Parses as JSON and validates against `schema.json`.
- [ ] `title` and a full `artboard` are present.
- [ ] Every scene has `nodes`, `edges` and at least one step; the scene lists equal step 0.
- [ ] Steps after 0 have `"delta": true` and only changed fields.
- [ ] All ids unique per scene and stable; every edge end exists.
- [ ] Every node is at least 10 x 10 px and inside the artboard.
- [ ] Every revealed node has `opacity` 1 in its reveal step; every drawn-in edge has `trim` 1.
- [ ] Every action ends within its step, and its `to` values match the snapshot.
- [ ] One narration clip per step; `transitions` has one entry fewer than there are scenes.
- [ ] No internal fields, comments or trailing commas.
