# openCanviz skills

Agent skills for [openCanviz](https://opencanviz.com), which turns an outline into a narrated, animated explainer video.

The `opencanviz-json` skill teaches an AI agent to write openCanviz project JSON that you can paste into **Import** on [opencanviz.com/create](https://opencanviz.com/create). The agent plans scenes and steps, writes the JSON, checks it against the schema, and hands you a file that imports and plays.

## What is in this repository

```text
.claude-plugin/marketplace.json          Claude Code marketplace listing
plugins/opencanviz/
  .claude-plugin/plugin.json             plugin manifest
  skills/opencanviz-json/
    SKILL.md                             the skill: workflow, rules, checklist
    schema.json                          JSON Schema, same as https://opencanviz.com/schema/v1.json
    scripts/opencanviz.py                Python builder and validator (stdlib only, Python 3.9+)
    examples/*.json                      six complete projects that import and play
    examples/*.py                        the Python script that writes each example
    tests/test_examples.py               runs the examples and checks the validator refuses bad files
```

Agents that can run Python build the project with `scripts/opencanviz.py`, which lays out the nodes, fits the text, keeps captions and arrows readable, and refuses to save a file that breaks a rule. Agents that cannot run code write the JSON by hand from the rules in `SKILL.md`.

### Python example

```python
import sys; sys.path.insert(0, "plugins/opencanviz/skills/opencanviz-json/scripts")
from opencanviz import Project
p = Project("How caching works", aspect="16:9")
s = p.scene("Cache")
app_r, cache_r, db_r = p.area().row(3, labels=["2 ms"], h=400)
app, cache, db = s.box("App", at=app_r), s.box("Cache", at=cache_r), s.node("cylinder", "Database", at=db_r)
s.step("Every request goes to the app.").reveal(app)
s.step("A cache keeps recent answers close.").reveal(cache).draw(s.arrow(app, cache, "2 ms"))
s.step("The database holds everything else.").reveal(db).draw(s.arrow(cache, db))
p.save("caching.json")  # validated; raises with a fix hint if a rule is broken
```

Check any openCanviz JSON file, hand-written or not, with `python3 plugins/opencanviz/skills/opencanviz-json/scripts/opencanviz.py check file.json`. Run the tests with `python3 -m unittest discover -s plugins/opencanviz/skills/opencanviz-json/tests`.

## Install

### Claude Code

Add this repository as a plugin marketplace, then install the plugin:

```text
/plugin marketplace add opencanviz/opencanviz-skills-repo
/plugin install opencanviz@opencanviz-skills
```

Or from your shell:

```bash
claude plugin marketplace add opencanviz/opencanviz-skills-repo
claude plugin install opencanviz@opencanviz-skills
```

Then ask Claude for an openCanviz video as JSON, or run the skill directly with `/opencanviz:opencanviz-json`.

To use the skill without the plugin system, copy `plugins/opencanviz/skills/opencanviz-json/` to `~/.claude/skills/opencanviz-json/` (all your projects) or `.claude/skills/opencanviz-json/` (one project).

### Claude apps (claude.ai, desktop)

Download [opencanviz-json.zip](https://opencanviz.com/skills/opencanviz-json.zip), then in Claude open **Customize** > **Skills**, click **+**, choose **Create skill**, then **Upload a skill** and pick the zip.

### Other agents and chatbots

Paste the contents of [SKILL.md](plugins/opencanviz/skills/opencanviz-json/SKILL.md) into the chat or your agent's system prompt, and attach `schema.json` and one of the examples if the tool allows files. Agents that read a skills folder can use the `opencanviz-json` folder as is.

## Use the result

1. Copy the JSON the agent writes.
2. Open [opencanviz.com/create](https://opencanviz.com/create), choose **Import**, paste it and click **Import project**.
3. In the editor, open the **Narration** panel and click **Generate All Scenes** to voice the narration.

## Docs

- [The openCanviz JSON format](https://opencanviz.com/docs/json-overview)
- [JSON schema reference](https://opencanviz.com/docs/json-schema-reference)
- [JSON examples](https://opencanviz.com/docs/json-examples)
- [JSON rules for AI agents](https://opencanviz.com/docs/json-rules-for-ai-agents)

## License

MIT. See [LICENSE](LICENSE).
