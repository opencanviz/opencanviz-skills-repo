"""Builder tests: every scene in every style, the claim checks, audio, screenshots.

    python3 -m unittest discover -s plugins/opencanviz/skills/launch-reel/tests
"""
import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

needs_audio = unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                                  "numpy and scipy are optional")
needs_pil = unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow is optional")
from launch_reel import build_reel
from launch_reel._metrics import text_width
from launch_reel.scenes import fit, wrap
from launch_reel.spec import EXAMPLE, normalize


def _doc(project):
    return project["diagrams"][0]


def test_example_builds_deterministically():
    a, b = build_reel(EXAMPLE), build_reel(EXAMPLE)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert 40_000 < a["meta"]["durationMs"] < 90_000


def test_node_ids_unique():
    ids = [n["id"] for n in _doc(build_reel(EXAMPLE))["nodes"]]
    assert len(ids) == len(set(ids))


def test_mask_children_follow_their_mask():
    doc = _doc(build_reel(EXAMPLE))
    kids = {}
    for n in doc["nodes"]:
        if n.get("parentId"):
            assert n["opacity"] == 0, n["id"]          # a hidden group does not hide its children
            kids.setdefault(n["parentId"], []).append(n["id"])
    assert kids
    for s in doc["steps"][1:]:
        ops = {p["id"]: p["opacity"] for p in s.get("nodes", []) if "opacity" in p}
        for m, cs in kids.items():
            if m in ops:
                assert all(ops.get(c) == ops[m] for c in cs), (s.get("id"), m)


def test_visibility_cuts_are_one_frame():
    for s in _doc(build_reel(EXAMPLE))["steps"][1:]:
        if s.get("id", "").startswith("cut"):
            assert s["durationMs"] == 1


def test_normalize_drops_unknown_scenes_and_bad_colours():
    spec = normalize({"brand": {"name": "X", "ink": "red", "accents": ["#123456"]},
                      "scenes": [{"type": "logo"}, {"type": "nope"}, {"type": "end", "line": "Hi"}]})
    assert [s["type"] for s in spec["scenes"]] == ["logo", "end"]
    assert spec["brand"]["ink"].startswith("#") and len(spec["brand"]["accents"]) == 3


def test_fit_and_wrap():
    text, size = fit("A very long headline that will not fit at all in the box", 48, 300)
    assert 48 * 0.8 - 1 <= size < 48 and text.endswith("…")
    assert text_width(text, size) <= 300
    assert fit("Short", 48, 300) == ("Short", 48)
    lines = wrap("one two three four five six seven", 20, 120)
    assert len(lines) > 1 and all(text_width(l, 20, 500) <= 120 for l in lines)


# ---------------- style packs, stories, new scenes, sound ----------------
from launch_reel import STORIES, STYLES  # noqa: E402
try:
    from launch_reel.audio import SR, render_audio  # noqa: E402
except ImportError:                                  # numpy + scipy are optional
    render_audio = None
from launch_reel.scenes2 import SCENES2, world_dots  # noqa: E402

NEW_SCENES = [
    {"type": "problem", "pains": ["Too many tabs", "Lost docs"]},
    {"type": "dashboard", "kpis": [{"label": "Revenue", "value": "$12,480", "delta": "+18%"}], "chart_note": "Best week"},
    {"type": "terminal", "commands": [{"cmd": "npx tool init", "output": ["✓ Done"]}], "done": "Ready"},
    {"type": "browser", "title": "Hello", "subtitle": "A page", "features": [{"label": "Fast"}]},
    {"type": "split", "before": ["Slow"], "after": ["Fast"]},
    {"type": "stat", "value": "4.5x", "label": "faster"},
    {"type": "kanban", "cards": [{"title": "A", "col": 0}, {"title": "B", "col": 0}, {"title": "C", "col": 2}]},
    {"type": "notifications", "line": "Updates", "items": [{"title": "One", "body": "two"}]},
    {"type": "map", "line": "Everywhere", "pins": [{"city": "London"}, {"city": "Atlantis"}]},
    {"type": "pricing", "price": "$19", "features": ["All of it"]},
    {"type": "logo_grid", "line": "Works with", "apps": ["ph:gear-bold", "ph:bell-bold"]},
    {"type": "compare", "rows": ["Fast", "Cheap"], "them": [True, False]},
    {"type": "countdown", "line": "2 reasons", "items": [{"label": "One"}, {"label": "Two"}]},
    {"type": "feature_flash", "items": [{"label": "Search"}, {"label": "Write"}]},
    {"type": "end"},
]


def _all(style="classic", story="showcase"):
    return build_reel({"brand": EXAMPLE["brand"], "style": style, "story": story,
                       "scenes": [{"type": "logo"}] + NEW_SCENES})


def test_every_new_scene_is_registered_and_covered():
    assert set(SCENES2) == {s["type"] for s in NEW_SCENES if s["type"] != "end"}
    assert normalize({"scenes": NEW_SCENES})["scenes"] == NEW_SCENES


def test_every_style_builds_every_scene_with_unique_ids():
    for style in STYLES:
        doc = _doc(_all(style))
        ids = [n["id"] for n in doc["nodes"]]
        assert len(ids) == len(set(ids)), style
        for s in doc["steps"]:
            assert s["durationMs"] >= 1


def test_unknown_style_and_story_fall_back():
    sp = normalize({"style": "neon", "story": "saga"})
    assert (sp["style"], sp["story"]) == ("classic", "showcase")


def test_transitions_follow_the_style_and_land_on_the_beat():
    for name, style in STYLES.items():
        au = _all(name)["meta"]["audio"]
        half = 60000 / style.bpm / 2
        kinds = {t["kind"] for t in au["transitions"][1:]}
        assert kinds <= set(style.transitions) | {"cut"}, name
        for t in au["transitions"][1:]:
            assert min(t["t"] % half, half - t["t"] % half) < 1.01, (name, t)


def test_camera_fields_are_well_formed():
    doc = _doc(_all("glass"))
    for s in doc["steps"]:
        for k in ("camera", "cameraEnd"):
            if k in s:
                assert set(s[k]) == {"x", "y", "zoom"} and s[k]["zoom"] > 0
        if "cameraDurationMs" in s:
            assert 0 <= s["cameraDurationMs"] <= s["durationMs"]


def test_rapid_fire_story_plays_faster():
    slow, fast = _all(story="showcase"), _all(story="rapid_fire")
    assert fast["meta"]["durationMs"] < slow["meta"]["durationMs"]


def test_world_map_has_land_and_sea():
    d, h = world_dots()
    assert 300 < d.count("M") < 3000 and 350 < h < 500


@needs_audio
def test_audio_renders_every_cue_kind():
    proj = _all("dark")
    kinds = {e["kind"] for e in proj["meta"]["audio"]["events"]}
    assert {"whoosh", "pop", "type", "tick", "ding", "thud", "click"} <= kinds
    proj["meta"]["durationMs"] = 6000                     # keep the test fast
    sr, x = render_audio(proj)
    assert sr == SR and x.shape == (6 * SR, 2) and x.dtype.name == "int16"
    assert 2000 < abs(x).max() <= 32767 * 0.9


@needs_audio
def test_every_music_preset_renders():
    for style in STYLES.values():
        proj = {"meta": {"durationMs": 3000, "audio": {"music": style.music, "bpm": style.bpm, "events": []}}}
        assert abs(render_audio(proj)[1]).max() > 1000, style.music


# ---------------- suites, stacks, non-AI products, proof, screenshots ----------------
from launch_reel.media import attach_screenshots, embed_image  # noqa: E402
from launch_reel.checks import ground  # noqa: E402
from launch_reel.scenes3 import SCENES3  # noqa: E402

_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAACCAIAAADwyuo0AAAAEklEQVR4nGM0TpvJAANMDEgAAByYATYFOJkSAAAAAElFTkSuQmCC"
SCENES_3 = [
    {"type": "lineup", "line": "Five tools", "products": [{"name": "Kickrail", "color": "#f97316", "desc": "Referrals"},
                                                          {"name": "Mailrail", "color": "#2563eb", "desc": "Email"}]},
    {"type": "receipt", "items": [{"name": "Rewardful", "price": "$99/mo"}, {"name": "Brevo", "price": "$99/mo"}],
     "new_price": "$29/mo", "new_label": "Railhq Pass"},
    {"type": "snippet", "code": "<script src=\"https://x.io/p.js\"></script>", "status": "Live",
     "product": {"name": "Pathrail", "color": "#16a34a"}},
    {"type": "inbox", "items": [{"from": "Acme", "subject": "Receipt", "preview": "Thanks"},
                                {"from": "Acme", "subject": "Welcome", "preview": "Hi"}], "open": 1},
    {"type": "funnel", "stages": [{"label": "Visitors", "value": "1,000"}, {"label": "Paid", "value": "40"}]},
    {"type": "toggle", "items": [{"label": "Payouts", "sub": "Via Stripe"}, {"label": "Fraud checks"}]},
    {"type": "form_builder", "fields": [{"label": "Email", "type": "email"}, {"label": "Size", "type": "select"}]},
    {"type": "repo", "name": "railhq/kickrail", "desc": "Referral tracking", "license": "MIT", "stars": "1,200"},
    {"type": "timeline", "items": [{"date": "Oct 2", "label": "Kickrail"}, {"date": "Oct 9", "label": "Mailrail"}]},
    {"type": "quote", "quote": "One login for every tool.", "author": "Railhq"},
    {"type": "phone_app", "line": "Run more", "title": "Today", "value": "12.4 km", "value_label": "This week",
     "rows": [{"icon": "ph:heart-bold", "label": "Heart rate", "value": "142"}], "alert": {"title": "Run at 6pm"}},
    {"type": "screenshot", "image": _PNG, "image_w": 4, "image_h": 2, "frame": "phone",
     "focus": [{"x": 0.5, "y": 0.5, "label": "Here"}]},
    {"type": "end"},
]


def test_every_scene3_is_registered_and_builds_in_every_style():
    assert set(SCENES3) == {s["type"] for s in SCENES_3 if s["type"] != "end"}
    assert normalize({"scenes": SCENES_3})["scenes"] == SCENES_3
    for style in STYLES:
        doc = _doc(build_reel({"style": style, "scenes": SCENES_3}))
        ids = [n["id"] for n in doc["nodes"]]
        assert len(ids) == len(set(ids)), style
        assert any(n.get("imageData") == _PNG for n in doc["nodes"])


def test_product_scene_wears_its_chip_and_colour():
    doc = _doc(build_reel({"style": "classic", "scenes": SCENES_3}))
    by = {n["id"]: n for n in doc["nodes"]}
    assert by["s2_pct"]["text"] == "Pathrail" and by["s2_pcd"]["fill"] == "#16a34a"
    assert by["s2_bg"]["fill"] == "#16a34a"
    assert "s0_pct" not in by


_DESC = ("Railhq Pass bundles Kickrail and Mailrail for $29/mo. It replaces Rewardful ($99/mo) and Brevo ($99/mo). "
         "Kickrail is open source under the MIT license. "
         '"One login for every tool." Shipped Oct 2 and Oct 9.')


def test_ground_keeps_stated_claims():
    spec = normalize({"scenes": SCENES_3})
    notes = ground(spec, _DESC)
    kept = {s["type"] for s in spec["scenes"]}
    assert {"lineup", "receipt", "repo", "timeline", "quote", "screenshot"} <= kept
    repo = next(s for s in spec["scenes"] if s["type"] == "repo")
    assert repo["license"] == "MIT" and "stars" not in repo
    assert any("stars" in n for n in notes)


def test_ground_drops_invented_claims_and_ungated_ai():
    spec = normalize({"scenes": [
        {"type": "chat", "question": "hi"}, {"type": "doc_edit"},
        {"type": "receipt", "items": [{"name": "Rewardful", "price": "$99/mo"}, {"name": "Semrush", "price": "$129/mo"},
                                      {"name": "Brevo", "price": "$49/mo"}]},
        {"type": "stat", "value": "12,000", "label": "teams"},
        {"type": "compare", "columns": ["HubSpot", "Railhq"], "rows": ["Cheap"]},
        {"type": "quote", "quote": "Best tool we ever bought."},
        {"type": "timeline", "items": [{"date": "Jan 5", "label": "Beta"}, {"date": "Oct 2", "label": "Kickrail"}]},
        {"type": "screenshot"}, {"type": "end"}]})
    ground(spec, "Railhq replaces Rewardful ($99/mo) and Brevo. Shipped Oct 2.")
    types = [s["type"] for s in spec["scenes"]]
    assert types == ["compare", "end"]
    assert spec["scenes"][0]["columns"][0] == "Typical tools"


def test_ground_lets_ai_scenes_through_for_ai_products():
    spec = normalize({"scenes": [{"type": "chat"}, {"type": "doc_edit"}, {"type": "end"}]})
    ground(spec, "An AI assistant that drafts your release notes.")
    assert [s["type"] for s in spec["scenes"]] == ["chat", "doc_edit", "end"]


def test_ground_reads_spelled_out_numbers_in_the_description():
    spec = normalize({"scenes": [{"type": "stat", "value": "2 min", "label": "to list"}, {"type": "end"}]})
    assert ground(spec, "List a piece in two minutes.") == []
    assert spec["scenes"][0]["type"] == "stat"


@needs_pil
def test_screenshots_embed_and_attach():
    p = Path(tempfile.mkdtemp()) / "shot.png"
    p.write_bytes(base64.b64decode(_PNG.split(",")[1]))
    sh = embed_image(str(p))
    assert sh["image"].startswith("data:image/") and (sh["image_w"], sh["image_h"]) == (4, 2)
    spec = attach_screenshots({"scenes": [{"type": "screenshot", "caption": "a"}, {"type": "end"}]}, [sh, sh])
    assert [s["type"] for s in spec["scenes"]] == ["screenshot", "screenshot", "end"]
    assert all(s.get("image") for s in spec["scenes"][:2])


class BuilderTests(unittest.TestCase):
    """Runs every test_ function above under unittest, so the suite needs no pytest."""


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn):
        setattr(BuilderTests, _name, lambda self, f=_fn: f())
        getattr(BuilderTests, _name).__unittest_skip__ = getattr(_fn, "__unittest_skip__", False)
        getattr(BuilderTests, _name).__unittest_skip_why__ = getattr(_fn, "__unittest_skip_why__", "")

del _name, _fn
