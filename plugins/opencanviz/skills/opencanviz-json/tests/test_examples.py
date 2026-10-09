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


UNTITLED = "does not open with a title"


def clean(doc, titled=False):
    """Every problem in doc; the small test scenes have no title, so that warning is left out unless titled."""
    errors, warnings = oc.validate(doc)
    return errors + [w for w in warnings if titled or UNTITLED not in w] + (oc.schema_errors(doc) or [])


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
        cells = p.area().row(3, w=440, h=420)
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
        self.assertEqual(clean(p2.to_dict()), [])

    def test_labeled_edge_hidden_until_drawn(self):
        p, s, ra, rb = small_project()
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b, "calls")
        s.step("A first.").reveal(a)
        s.step("Then B, then the call.").reveal(b).draw(link)
        doc = p.to_dict()
        edges = {e["id"]: e for e in doc["diagrams"][0]["steps"][0]["edges"]}
        self.assertEqual((edges[link.id]["trim"], edges[link.id]["opacity"]), (0, 0))
        self.assertNotIn("label", edges[link.twin_id])

    def test_label_fades_in_after_its_line_is_drawn(self):
        p = oc.Project("t")
        s = p.scene("t")
        ra, rb = p.area().row(2, w=420, h=300, labels=["calls"])
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b, "calls")
        s.step("A first.").reveal(a)
        s.step("Then B, then the call.").reveal(b).draw(link, duration=700)
        doc = p.to_dict()
        self.assertEqual(clean(doc), [])
        st = doc["diagrams"][0]["steps"][1]
        acts = [x for x in st["actions"] if x["type"] == "edgeTween"]
        line = [x for x in acts if x["target"]["id"] == link.twin_id and "trim" in x["to"]][0]
        label = [x for x in acts if x["target"]["id"] == link.id][0]
        line_end = line.get("offsetMs", 0) + line["durationMs"]
        self.assertGreaterEqual(label["offsetMs"], line_end)
        self.assertEqual(label["from"]["opacity"], 0)
        patch = {e["id"]: e for e in st["edges"]}
        self.assertEqual(patch[link.twin_id], {"id": link.twin_id, "trim": 1, "opacity": 0})
        self.assertEqual((patch[link.id]["trim"], patch[link.id]["opacity"]), (1, 1))


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
        for edges in (doc["diagrams"][0]["steps"][0]["edges"], doc["diagrams"][0]["edges"]):
            edges[0].update(trim=1, opacity=1)
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


class LayoutOnScreen(unittest.TestCase):
    def chain(self, follow=True):
        p = oc.Project("t", follow=follow)
        s = p.scene("t")
        cells = p.area().flow(4, labels=["sends", "stores", "returns"])
        ns = [s.box(t, at=r) for t, r in zip("ABCD", cells)]
        es = [s.arrow(ns[i], ns[i + 1], l) for i, l in enumerate(["sends", "stores", "returns"])]
        s.step("A alone.").reveal(ns[0])
        for i in range(3):
            s.step("Next one, step %d." % i).reveal(ns[i + 1]).draw(es[i])
        return p

    def test_follow_camera_centers_the_lone_first_node(self):
        p = self.chain()
        doc = p.to_dict()
        st0 = doc["diagrams"][0]["steps"][0]
        a = [n for n in st0["nodes"] if n["opacity"] == 1][0]
        cx, cy = p.safe_center()
        cam = st0["camera"]
        self.assertEqual(st0["cameraDurationMs"], 0)
        self.assertAlmostEqual(a["x"] + a["w"] / 2 - cam["x"], cx, delta=2)
        self.assertAlmostEqual(a["y"] + a["h"] / 2 - cam["y"], cy, delta=2)
        self.assertEqual(clean(doc), [])

    def test_stub_arrow_is_refused(self):
        p = oc.Project("t")
        s = p.scene("t")
        a = s.box("House vote", x=-300, y=-300, w=300, h=150)
        b = s.box("Senate vote", x=-300, y=-70, w=300, h=150)
        e = s.arrow(a, b, "sent over to the other chamber")
        s.step("Both.").reveal(a).reveal(b).draw(e)
        _, warnings = oc.validate(p.to_dict())
        self.assertTrue(any("shows only" in w for w in warnings), warnings)

    def test_full_width_title_does_not_hide_an_off_center_node(self):
        p = oc.Project("t")
        s = p.scene("t")
        top, body = p.area().cut_top(110)
        cells = body.row(3, labels=["asks", "reads"])
        t = s.text("A short title", at=top, fontWeight=700)
        a = s.box("Browser", at=cells[0])
        s.step("Browser alone, under a title.").reveal(t).reveal(a)
        st0 = p.to_dict()["diagrams"][0]["steps"][0]
        self.assertIn("camera", st0)            # the title box spans the frame, its ink does not
        self.assertLess(st0["camera"]["x"], -100)

    def test_off_center_steps_are_flagged_without_follow(self):
        _, warnings = oc.validate(self.chain(follow=False).to_dict())
        self.assertTrue(any("off the center" in w for w in warnings), warnings)

    def test_side_margin(self):
        p = oc.Project("t")
        a = p.area()
        self.assertEqual((a.x, a.x + a.w), (-840, 840))
        p.follow = False                        # the follow camera would pan this pair to the middle
        s = p.scene("t")
        b = s.box("Edge box", x=-940, y=-200, w=300, h=200)
        c = s.box("Other", x=-400, y=-200, w=300, h=200)
        s.step("Both.").reveal(b).reveal(c, offset="with")
        _, warnings = oc.validate(p.to_dict())
        self.assertTrue(any("side of the frame" in w for w in warnings), warnings)

    def test_gap_leaves_a_visible_arrow(self):
        self.assertGreaterEqual(oc.link_gap(None), 100)
        lab = "absorbed by"
        self.assertGreaterEqual(oc.link_gap(lab, 24) - oc.label_width(lab, 24) - 2 * oc.EDGE_GAP, 120)
        self.assertGreaterEqual(oc.link_gap(lab, 24, vertical=True) - oc.label_height(24) - 2 * oc.EDGE_GAP, 120)
        p, s, ra, rb = small_project()          # 100 px gap: too short for a labeled arrow
        a, b = s.box("A", at=ra), s.box("B", at=rb)
        link = s.arrow(a, b, "calls")
        s.step("A first.").reveal(a)
        s.step("Then B and the call.").reveal(b).draw(link)
        _, warnings = oc.validate(p.to_dict())
        self.assertTrue(any("gap" in w for w in warnings), warnings)

    def test_hand_written_label_draw_is_flagged(self):
        doc = base_doc()
        sc = doc["diagrams"][0]
        for e in sc["edges"] + sc["steps"][0]["edges"]:
            e["label"], e["labelFontSize"] = "x", 24
            e["opacity"] = 0
        st = sc["steps"][1]
        st["edges"][0]["opacity"] = 1
        st["actions"][-1]["from"], st["actions"][-1]["to"] = {"trim": 0, "opacity": 1}, {"trim": 1, "opacity": 1}
        _, warnings = oc.validate(doc)
        self.assertTrue(any("slides along with the tip" in w for w in warnings), warnings)

    def test_cycle_closes_around_the_outside(self):
        p = oc.Project("t")
        s = p.scene("t")
        labs = ["heats", "rises", "cools"]
        cells = p.area().row(4, labels=labs, h=360)
        ns = [s.box(t, at=r) for t, r in zip(["Ocean", "Vapor", "Cloud", "Rain"], cells)]
        es = [s.arrow(ns[i], ns[i + 1], labs[i]) for i in range(3)]
        back = s.arrow(ns[3], ns[0], "flows back", route="around")
        s.step("The ocean.").reveal(ns[0])
        for i in range(3):
            s.step("The next stage, %d." % i).reveal(ns[i + 1]).draw(es[i])
        s.step("And back to the ocean.").draw(back)
        doc = p.to_dict()
        self.assertEqual((back.fields["fromPort"], back.fields["toPort"]), ("S", "S"))
        self.assertEqual(back.fields["labelPosition"], "center")
        self.assertEqual(clean(doc), [])


def load_example(name):
    with open(os.path.join(ROOT, "examples", name + ".json")) as fh:
        return json.load(fh)


def all_text(errors, warnings):
    return "\n".join(errors + warnings)


class CheckCatchesRenderBreakers(unittest.TestCase):
    """Fields the render probe showed to break playback or export."""

    def first_node(self, doc):
        sc = doc["diagrams"][0]
        return sc["nodes"][0], sc["steps"][0]["nodes"][0]

    def test_glow_zero(self):
        doc = load_example("minimal")
        for n in self.first_node(doc):
            n["glow"] = 0
        errors, _ = oc.validate(doc)
        self.assertTrue(any("noGlow" in e for e in errors), errors)

    def test_sketch_mode(self):
        doc = load_example("minimal")
        for n in self.first_node(doc):
            n["sketchMode"] = True
        errors, _ = oc.validate(doc)
        self.assertTrue(any("sketchMode" in e for e in errors), errors)

    def test_icon_kind(self):
        doc = load_example("minimal")
        for n in self.first_node(doc):
            n["kind"] = "icon"
        errors, _ = oc.validate(doc)
        self.assertTrue(any("white box" in e for e in errors), errors)

    def test_edge_without_animation_style(self):
        doc = load_example("minimal")
        sc = doc["diagrams"][0]
        for e in sc["edges"] + sc["steps"][0]["edges"]:
            e.pop("animationStyle", None)
        _, warnings = oc.validate(doc)
        self.assertTrue(any("animationStyle" in w for w in warnings), warnings)

    def test_delta_with_edges_but_no_nodes(self):
        doc = load_example("minimal")
        sc = doc["diagrams"][0]
        st = next(st for st in sc["steps"][1:] if st["edges"])
        st["nodes"] = []
        errors, _ = oc.validate(doc)
        self.assertTrue(any("lists no nodes" in e for e in errors), errors)

    def test_missing_font_field(self):
        doc = load_example("bubble_sort")
        sc = doc["diagrams"][0]
        for n in sc["nodes"] + sc["steps"][0]["nodes"]:
            if n["kind"] == "algo-array":
                n.pop("cellFontSize")
        _, warnings = oc.validate(doc)
        self.assertTrue(any("cellFontSize" in w for w in warnings), warnings)

    def test_path_needs_length_and_cum(self):
        doc = load_example("path_follow")
        sc = doc["diagrams"][0]
        for pth in sc["paths"].values():
            pth.pop("cum")
        errors, _ = oc.validate(doc)
        self.assertTrue(any("\"cum\"" in e for e in errors), errors)

    def test_code_keeps_only_the_highlight_flag(self):
        doc = load_example("code_walkthrough")
        sc = doc["diagrams"][0]
        code = [n for n in sc["nodes"] if n.get("highlightedLines") is not None or n.get("_animatedProps")]
        self.assertTrue(code and code[0]["_animatedProps"] == {"highlightedLines": False})
        code[0]["_animatedProps"] = {"x": False}
        for n in sc["steps"][0]["nodes"]:
            if n["id"] == code[0]["id"]:
                n["_animatedProps"] = {"x": False}
        errors, _ = oc.validate(doc)
        self.assertTrue(any("_animatedProps" in e for e in errors), errors)


class RecipeShapes(unittest.TestCase):
    def test_path_carries_length_and_cum(self):
        p = oc.Project("t")
        s = p.scene("t")
        pid = s.path([(0, 0), (300, 0), (300, 400)])
        pth = s.paths[pid]
        self.assertEqual(pth["cum"], [0, 300, 700])
        self.assertEqual(pth["length"], 700)

    def test_grid_values_are_not_shared_with_later_steps(self):
        doc = load_example("scatter_grid")
        sc = doc["diagrams"][1]
        g0 = next(n for n in sc["steps"][0]["nodes"] if n["kind"] == "algo-grid")
        self.assertEqual(g0["gridValues"][2][2], "")

    def test_cleared_cell_fades_to_the_fill(self):
        doc = load_example("bubble_sort")
        sc = doc["diagrams"][0]
        arr = next(n for n in sc["nodes"] if n["kind"] == "algo-array")
        patch = next(n for n in sc["steps"][2]["nodes"] if n["id"] == arr["id"])
        self.assertEqual(patch["cellColors"][0], arr["fill"])

    def test_bar_chart_grows_after_step_zero_only(self):
        p = oc.Project("t")
        s = p.scene("t")
        chart = s.bar_chart([("a", 3), ("b", 5)], at=p.area())
        with self.assertRaises(oc.OpenCanvizError):
            s.step("Bars grow in the first step.").grow(chart)

    def test_every_recipe_example_is_clean(self):
        for name in ["bar_chart", "line_chart", "scatter_grid", "bubble_sort", "data_structures",
                     "code_walkthrough", "sequence", "timeline", "before_after", "bullets",
                     "counter_progress", "pie", "path_follow"]:
            with self.subTest(example=name):
                self.assertEqual(clean(load_example(name)), [])

    def test_text_below_the_readable_floor_warns(self):
        doc = load_example("bullets")
        sc = doc["diagrams"][0]
        for n in sc["nodes"] + [n for st in sc["steps"] for n in st["nodes"]]:
            if n["id"] == "s1_point1" and "fontSize" in n:
                n["fontSize"] = 16
        _, warnings = oc.validate(doc)
        self.assertTrue(any("readable" in w for w in warnings), warnings)

    def test_variable_box_is_narrow(self):
        p = oc.Project("t")
        s = p.scene("t")
        v = s.variable("i", 0, at=p.area())
        s.step("i starts at zero.").reveal(v)
        s.step("i becomes 12.").assign(v, 12)
        node = next(n for n in p.to_dict()["diagrams"][0]["nodes"] if n["kind"] == "algo-variable")
        self.assertLess(node["w"], 400)

    def test_code_below_the_floor_is_refused(self):
        p = oc.Project("t")
        s = p.scene("t")
        src = "\n".join("value_%d = compute_something_long(%d)" % (i, i) for i in range(30))
        with self.assertRaises(oc.OpenCanvizError):
            s.code(src, at=p.area().cut_top(300)[0])

    def test_line_chart_draws_a_thick_line(self):
        doc = load_example("line_chart")
        chart = next(n for n in doc["diagrams"][0]["nodes"] if n["kind"] == "algo-chart-line")
        self.assertEqual(len(chart["chartSeries"]), 5)

    def test_timeline_spans_the_frame_from_the_start(self):
        doc = load_example("timeline")
        dots = [n for n in doc["diagrams"][0]["nodes"] if "_dot" in n["id"]]
        xs = [n["x"] for n in dots]
        self.assertGreater(max(xs) - min(xs), doc["artboard"]["width"] * 0.5)

    def test_bullets_are_centred(self):
        doc = load_example("bullets")
        pts = [n for n in doc["diagrams"][0]["nodes"] if n["id"].split("_", 1)[-1].startswith("point")]
        ab = doc["artboard"]
        lo = min(n["x"] for n in pts)
        hi = max(n["x"] + n["w"] for n in pts)
        self.assertLess(abs((lo + hi) / 2 - (ab["x"] + ab["width"] / 2)), ab["width"] * 0.08)


def acts(sc, k):
    return sc["steps"][k].get("actions", [])


class ShortTimedChanges(unittest.TestCase):
    def test_swap_is_a_short_algo_swap(self):
        sc = load_example("bubble_sort")["diagrams"][0]
        sw = [a for st in sc["steps"] for a in st.get("actions", []) if a["type"] == "algoSwap"]
        self.assertTrue(sw)
        self.assertTrue(all(a["durationMs"] == oc.SWAP_MS for a in sw))

    def test_colour_change_is_a_short_tween(self):
        sc = load_example("bubble_sort")["diagrams"][0]
        tw = [a for st in sc["steps"] for a in st.get("actions", [])
              if a["type"] == "transformTween" and "cellColors" in a.get("to", {})]
        self.assertTrue(tw)
        self.assertTrue(all(a["durationMs"] == oc.COLOR_MS for a in tw))

    def test_timeline_bar_grows_before_the_new_dot(self):
        sc = load_example("timeline")["diagrams"][0]
        for k in range(2, len(sc["steps"])):
            a = acts(sc, k)
            grow = [x for x in a if x["type"] == "transformTween" and "from" in x]
            self.assertTrue(grow, k)
            self.assertEqual(grow[0]["durationMs"], oc.TIMELINE_MS)
            reveal_end = max(x.get("offsetMs", 0) + x.get("durationMs", 0) for x in a
                             if x["type"] in ("fadeIn", "visibility"))
            self.assertLessEqual(reveal_end, oc.TIMELINE_MS)

    def test_line_chart_has_a_moving_tip(self):
        sc = load_example("line_chart")["diagrams"][0]
        tip = [n for n in sc["nodes"] if n["id"].endswith("_tip")]
        self.assertEqual(len(tip), 1)
        xs = {n["x"] for st in sc["steps"] for n in st["nodes"] if n["id"] == tip[0]["id"]}
        self.assertGreater(len(xs), 1)

    def test_no_tweens_to_missing_edges(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.json"))):
            doc = json.load(open(path))
            for sc in doc.get("diagrams", []):
                ids = {e["id"] for e in sc["edges"]}
                for st in sc["steps"]:
                    for a in st.get("actions", []):
                        if a.get("target", {}).get("kind") == "edge":
                            self.assertIn(a["target"]["id"], ids, path)

    def test_action_on_a_missing_id_is_an_error(self):
        doc = load_example("bubble_sort")
        sc = doc["diagrams"][0]
        sc["steps"][1].setdefault("actions", []).append(
            {"type": "algoSwap", "target": {"kind": "node", "id": "nope"}, "indices": [0, 1], "durationMs": 600})
        errors, _ = oc.validate(doc)
        self.assertTrue(any("nope" in e for e in errors), errors)

    def test_timed_colour_must_match_the_snapshot(self):
        doc = load_example("bubble_sort")
        sc = doc["diagrams"][0]
        for st in sc["steps"]:
            for a in st.get("actions", []):
                if a["type"] == "transformTween" and "cellColors" in a.get("to", {}):
                    a["to"]["cellColors"] = ["#123456"] * len(a["to"]["cellColors"])
                    errors, _ = oc.validate(doc)
                    self.assertTrue(errors)
                    return
        self.fail("no colour tween")

    def test_labeled_arrow_pops_its_label(self):
        p = oc.Project("t")
        s = p.scene("t")
        ca, cb = p.area().row(2, w=440, h=300)
        x = s.box("A", at=ca)
        y = s.box("B", at=cb)
        e = s.arrow(x, y, label="go")
        s.step("A and B.").reveal(x).reveal(y)
        s.step("A goes to B.").draw(e)
        eases = {a.get("ease") for st in p.to_dict()["diagrams"][0]["steps"] for a in st.get("actions", [])
                 if a["type"] == "edgeTween"}
        self.assertIn("step", eases)


class Titles(unittest.TestCase):
    def test_untitled_video_warns(self):
        p = oc.Project("t")
        s = p.scene("t")
        b = s.box("A", at=p.area().centered(440, 300))
        s.step("A box.").reveal(b)
        _, warnings = oc.validate(p.to_dict())
        self.assertTrue(any(UNTITLED in w for w in warnings), warnings)

    def test_title_stays_put_on_screen(self):
        sc = load_example("code_walkthrough")["diagrams"][0]
        nodes = {n["id"]: dict(n) for n in sc["nodes"]}
        tid = next(i for i, n in nodes.items() if n.get("meta", {}).get("title")
                   or (n.get("kind") == "text" and str(n.get("fontWeight")) == "700"))
        cam, seen = (0, 0), set()
        for st in sc["steps"]:
            for n in st["nodes"]:
                nodes.setdefault(n["id"], {}).update(n)
            if st.get("camera"):
                cam = (st["camera"]["x"], st["camera"]["y"])
            t = nodes[tid]
            seen.add((round(t["x"] - cam[0]), round(t["y"] - cam[1])))
        self.assertEqual(len(seen), 1, seen)


if __name__ == "__main__":
    unittest.main()
