"""Every example spec builds, passes the claim checks against its own sources, and only uses
bundled icons; the CLI refuses an unsourced claim.

    python3 -m unittest discover -s plugins/opencanviz/skills/launch-reel/tests
"""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import build  # noqa: E402
from launch_reel._icons import bundled  # noqa: E402

EXAMPLES = sorted(p for p in (SKILL / "examples").iterdir() if (p / "spec.json").exists())


def run(*argv):
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = build.main([str(a) for a in argv])
    return code, err.getvalue()


class ExampleTests(unittest.TestCase):
    def test_there_are_examples(self):
        self.assertGreaterEqual(len(EXAMPLES), 3)

    def test_each_example_builds_against_its_sources(self):
        for ex in EXAMPLES:
            with self.subTest(ex.name), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "reel.json"
                code, err = run(ex / "spec.json", "--sources", ex / "sources.md", "--out", out)
                self.assertEqual(code, 0, err)
                project = json.loads(out.read_text())
                self.assertEqual(project["meta"]["template"], "launch_reel")
                self.assertTrue(30_000 < project["meta"]["durationMs"] < 90_000)

    def test_each_example_uses_only_bundled_icons(self):
        icons = bundled()
        for ex in EXAMPLES:
            refs = re.findall(r'"((?:ph|logos|simple-icons):[a-z0-9-]+)"', (ex / "spec.json").read_text())
            self.assertEqual([r for r in refs if r not in icons], [], ex.name)

    def test_examples_have_no_em_dashes(self):
        for ex in EXAMPLES:
            self.assertNotIn("—", (ex / "spec.json").read_text(), ex.name)

    def test_unsourced_claim_stops_the_build(self):
        ex = SKILL / "examples" / "stridely"
        spec = json.loads((ex / "spec.json").read_text())
        spec["scenes"].insert(-1, {"type": "stat", "value": "3x", "label": "faster race times"})
        with tempfile.TemporaryDirectory() as d:
            p, out = Path(d) / "spec.json", Path(d) / "reel.json"
            p.write_text(json.dumps(spec))
            code, err = run(p, "--sources", ex / "sources.md", "--out", out)
            self.assertEqual(code, 2)
            self.assertIn("3x", err)
            self.assertFalse(out.exists())
            code, _ = run(p, "--sources", ex / "sources.md", "--out", out, "--allow-unsourced")
            self.assertEqual(code, 0)
            types = [s["type"] for s in json.loads(out.read_text())["meta"]["spec"]["scenes"]]
            self.assertNotIn("stat", types)

    def test_unknown_scene_type_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "spec.json"
            p.write_text(json.dumps({"scenes": [{"type": "hologram"}, {"type": "end"}]}))
            code, err = run(p, "--out", Path(d) / "reel.json")
            self.assertEqual(code, 2)
            self.assertIn("hologram", err)


if __name__ == "__main__":
    unittest.main()
