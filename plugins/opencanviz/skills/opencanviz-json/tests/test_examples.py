"""Run every example script, validate its output, and check that bad input is refused.

python3 -m unittest discover -s tests   (from the skill folder; stdlib only, jsonschema optional)
"""
import copy
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import opencanviz as oc  # noqa: E402

EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "*.py")))

try:
    import jsonschema  # noqa: F401
    HAVE_JSONSCHEMA = True
except ImportError:
    HAVE_JSONSCHEMA = False


def clean(doc):
    errors, warnings = oc.validate(doc)
    return errors + warnings + (oc.schema_errors(doc) or [])


class ExampleTests(unittest.TestCase):
    def test_there_are_examples(self):
        self.assertGreaterEqual(len(EXAMPLES), 6)

    def test_examples_run_and_validate(self):
        tmp = tempfile.mkdtemp()
        for script in EXAMPLES:
            name = os.path.splitext(os.path.basename(script))[0]
            with self.subTest(example=name):
                out = os.path.join(tmp, name + ".json")
                r = subprocess.run([sys.executable, script, out], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                with open(out) as fh:
                    doc = json.load(fh)
                self.assertEqual(clean(doc), [])
                errors, warnings = oc.check_file(out)
                self.assertEqual(errors + warnings, [])
                committed = os.path.join(ROOT, "examples", name + ".json")
                self.assertTrue(os.path.exists(committed), "commit %s.json next to the script" % name)
                with open(committed) as fh:
                    self.assertEqual(json.load(fh), doc, "%s.json is stale; rerun examples/%s.py" % (name, name))

    @unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed")
    def test_examples_match_schema(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.json"))):
            with self.subTest(file=os.path.basename(path)):
                with open(path) as fh:
                    self.assertEqual(oc.schema_errors(json.load(fh)), [])


def small_project():
    p = oc.Project("t")
    s = p.scene("t")
    a, b = p.area().row(2, w=420, h=300)
    return p, s, a, b


class BuilderRefuses(unittest.TestCase):
    def test_arrow_before_end_node_appears(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b)
        s.step("A shows up and the arrow points ahead.").reveal(a).draw(link)
        s.step("B shows up one step later.").reveal(b)
        with self.assertRaisesRegex(oc.OpenCanvizError, "draw it in step 1"):
            p.to_dict()

    def test_arrow_never_drawn_with_hidden_end(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        s.arrow(a, b)
        s.step("Only A at first.").reveal(a)
        s.step("Then B.").reveal(b)
        with self.assertRaisesRegex(oc.OpenCanvizError, "visible from step 0"):
            p.to_dict()

    def test_draw_starts_before_reveal_in_same_step(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b)
        s.step("A first.").reveal(a)
        s.step("The arrow draws, then B fades in.").draw(link).reveal(b)
        with self.assertRaisesRegex(oc.OpenCanvizError, "starts drawing"):
            p.save(os.path.join(tempfile.mkdtemp(), "x.json"))

    def test_tiny_node(self):
        p, s, ra, _ = small_project()
        with self.assertRaisesRegex(oc.OpenCanvizError, "too small"):
            s.box("x", x=0, y=0, w=200, h=4)

    def test_label_too_long_for_box(self):
        p, s, _, _ = small_project()
        with self.assertRaisesRegex(oc.OpenCanvizError, "does not fit"):
            s.box("a very long label " * 20, x=0, y=0, w=60, h=40)

    def test_unknown_and_wrong_fields(self):
        p, s, ra, rb = small_project()
        with self.assertRaisesRegex(oc.OpenCanvizError, "fillOpacity"):
            s.box("A", at=ra, fillOpacity=0.5)
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        with self.assertRaisesRegex(oc.OpenCanvizError, "width"):
            s.arrow(a, b, strokeWidth=3)

    def test_row_that_does_not_fit(self):
        p = oc.Project("t")
        with self.assertRaisesRegex(oc.OpenCanvizError, "flow"):
            p.area().row(6, w=400, h=200)

    def test_low_fill_refused_by_save(self):
        p = oc.Project("t")
        s = p.scene("t")
        cells = p.area().row(3, w=200, h=120)
        boxes = [s.box(t, at=c) for t, c in zip("ABC", cells)]
        s.step("Three small boxes in a thin row.").reveal(boxes[0]).reveal(boxes[1]).reveal(boxes[2])
        with self.assertRaisesRegex(oc.OpenCanvizError, "fills only"):
            p.save(os.path.join(tempfile.mkdtemp(), "x.json"))

    def test_skip_arrow_over_a_box(self):
        p = oc.Project("t")
        s = p.scene("t")
        cells = p.area().row(3, w=500, h=420)
        a, m, b = [s.box(t, at=c) for t, c in zip("AMB", cells)]
        skip = s.arrow(a, b, lineType="straight")
        s.step("Three boxes and an arrow straight across the middle one.").reveal(a).reveal(m).reveal(b).draw(skip)
        with self.assertRaisesRegex(oc.OpenCanvizError, "passes over s1_m"):
            p.save(os.path.join(tempfile.mkdtemp(), "x.json"))
        # the same link on its own lane is fine
        p2 = oc.Project("t")
        s2 = p2.scene("t")
        a, m, b = [s2.box(t, at=c) for t, c in zip("AMB", cells)]
        skip = s2.arrow(a, b, route="below")
        s2.step("Three boxes and an arrow that goes around the middle one.").reveal(a).reveal(m).reveal(b).draw(skip)
        p2.save(os.path.join(tempfile.mkdtemp(), "x.json"))

    def test_labeled_edge_hidden_until_drawn(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b, "calls")
        s.step("A first.").reveal(a)
        s.step("Then B, then the call.").reveal(b).draw(link)
        doc = p.to_dict()
        e = doc["diagrams"][0]["steps"][0]["edges"][0]
        self.assertEqual((e["trim"], e["opacity"]), (0, 0))


def base_doc():
    p, s, ra, rb = small_project()
    a, b = s.box("A", at=ra), s.box("B", at=rb)
    link = s.arrow(a, b)
    s.step("A first.").reveal(a)
    s.step("Then B and the arrow.").reveal(b).draw(link)
    return p.to_dict()


class ValidatorCatches(unittest.TestCase):
    def test_base_is_clean(self):
        self.assertEqual(clean(base_doc()), [])

    def test_drawn_edge_with_hidden_end(self):
        doc = base_doc()
        doc["diagrams"][0]["steps"][0]["edges"][0]["trim"] = 1
        doc["diagrams"][0]["edges"][0]["trim"] = 1
        errors, _ = oc.validate(doc)
        self.assertTrue(any("hidden" in e for e in errors), errors)

    def test_overlap_and_outside(self):
        doc = base_doc()
        sc = doc["diagrams"][0]
        for nodes in (sc["nodes"], sc["steps"][0]["nodes"]):
            nodes[1]["x"] = nodes[0]["x"] + 100
        errors, warnings = oc.validate(doc)
        self.assertTrue(any("overlap" in w for w in warnings), warnings)
        doc = base_doc()
        for nodes in (doc["diagrams"][0]["nodes"], doc["diagrams"][0]["steps"][0]["nodes"]):
            nodes[0]["x"] = 5000
        errors, _ = oc.validate(doc)
        self.assertTrue(any("artboard" in e for e in errors), errors)

    def test_two_boxes_on_the_same_spot(self):
        doc = base_doc()
        sc = doc["diagrams"][0]
        for nodes in (sc["nodes"], sc["steps"][0]["nodes"]):
            nodes[1]["x"], nodes[1]["y"] = nodes[0]["x"], nodes[0]["y"]
            nodes[1]["w"], nodes[1]["h"] = nodes[0]["w"], nodes[0]["h"]
        errors, _ = oc.validate(doc)
        self.assertTrue(any("same spot" in e for e in errors), errors)

    def test_text_overflow(self):
        doc = base_doc()
        for nodes in (doc["diagrams"][0]["nodes"], doc["diagrams"][0]["steps"][0]["nodes"]):
            nodes[0].update(label="Alpha beta gamma delta", labelFontSize=120)
        _, warnings = oc.validate(doc)
        self.assertTrue(any("overflow" in w or "fit" in w for w in warnings), warnings)

    def test_caption_band(self):
        doc = base_doc()
        for nodes in (doc["diagrams"][0]["nodes"], doc["diagrams"][0]["steps"][0]["nodes"]):
            for n in nodes:
                n["y"] = 300
        _, warnings = oc.validate(doc)
        self.assertTrue(any("caption" in w for w in warnings), warnings)

    def test_empty_step(self):
        doc = base_doc()
        sc = doc["diagrams"][0]
        sc["steps"].append({"id": "s1_extra", "delta": True, "durationMs": 2000, "caption": "Nothing happens here.",
                            "nodes": [], "edges": []})
        sc["narration"].append(dict(sc["narration"][-1], id="s1_n9", stepIndex=2, text="Nothing happens here."))
        _, warnings = oc.validate(doc)
        self.assertTrue(any("nothing" in w.lower() or "empty" in w.lower() for w in warnings), warnings)

    def test_nan_rejected(self):
        path = os.path.join(tempfile.mkdtemp(), "nan.json")
        with open(path, "w") as fh:
            fh.write(json.dumps(base_doc()).replace('"durationMs": 2000', '"durationMs": NaN', 1))
        errors, _ = oc.check_file(path)
        self.assertTrue(errors)

    def test_small_edge_label_font(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b, "x", labelFontSize=12)
        s.step("A first.").reveal(a)
        s.step("Then B and the arrow.").reveal(b).draw(link)
        _, warnings = oc.validate(p.to_dict())
        self.assertTrue(any("label" in w and "px" in w for w in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
