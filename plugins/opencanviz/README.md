# openCanviz

This plugin adds two skills. `opencanviz-json` teaches Claude to write an [openCanviz](https://opencanviz.com) video project as JSON. `launch-reel` makes a 40 to 70 second product launch video from a short spec. openCanviz is our product: it turns a project file into an animated video that you can narrate, edit and export. The skills are free and MIT licensed.

## What the skill does

Claude plans the scenes and steps, writes the JSON, checks it, and hands you a file to import. The skill includes:

- `SKILL.md`: the workflow, the rules and a checklist
- `schema.json`: the JSON Schema, the same as https://opencanviz.com/schema/v1.json
- `scripts/opencanviz.py`: a Python 3.9+ builder and validator that uses only the standard library. It lays out nodes, fits text, and refuses to save a file that breaks a rule. It covers text entrances, 22 scene transitions, motion presets, plots, tables and rings.
- `scripts/tex2svg.js`: turns LaTeX into SVG for math scenes
- `examples/`: 22 complete projects, each with the Python script that writes it
- `tests/test_examples.py`: runs the examples and checks that the validator refuses bad files

## launch-reel

Claude gathers facts about the product into a sources file, writes a spec (scenes, copy, story, style), and builds it with `scripts/build.py`, which refuses to build while any price, figure, competitor, date or quote in the spec is missing from the sources. Claude then renders a contact sheet with `scripts/preview.mjs` and `@opencanviz/player`, checks every scene, and revises. 37 scene types, 6 styles, 6 story shapes; see `skills/launch-reel/SKILL.md`.

It runs `python3` (standard library; `numpy` + `scipy` for the music WAV, `Pillow` for screenshots) and, for previews, `node` with Playwright's Chromium (`npm run setup` in `scripts/` downloads them). Icons are bundled, so builds make no network calls unless you pass `--fetch-icons`. The imported project has no music; `preview.mjs --mp4 --audio` renders a local MP4 with it.

## What opencanviz-json runs

- `python3` on your machine, to run the builder and validator, when Claude uses the helper. If the `jsonschema` package happens to be installed, the validator also checks the file against `schema.json`; it is not required.
- `node` with the `mathjax-full` package, only for LaTeX math scenes. The math calls run `node scripts/tex2svg.js` locally. If Node or the package is missing, they stop and print the install line (`npm i mathjax-full`). Installing it downloads a package from npm.
- The skill makes no network calls and sends no data anywhere. You copy the JSON into openCanviz yourself.

## Account

The skill itself needs no account. Importing the file needs a free openCanviz account at https://opencanviz.com/create. A free account can build and watch the video. Downloading the MP4 needs a plan, or a one-time purchase of that video's export.

## Use it

Ask Claude for an openCanviz video as JSON, or run `/opencanviz:opencanviz-json`. Then open https://opencanviz.com/create, choose **Import**, paste the JSON, click **Import project**, and use **Generate All Scenes** in the Narration panel to voice it.

Docs: https://opencanviz.com/docs/json-rules-for-ai-agents

## License

MIT
