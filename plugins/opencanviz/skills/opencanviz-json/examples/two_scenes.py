"""Two scenes: a typewriter title, then a slow path and a cache, with a crossfade, a move,
a removed edge and a camera zoom. Writes two_scenes.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project, Rect  # noqa: E402

p = Project("Caching in two minutes", aspect="16:9", background="#0f172a",
            caption_style={"variant": "band", "fontScale": 1.1, "textColor": "#f8fafc",
                           "bandColor": "#020617", "bandOpacity": 0.8})
area = p.area()

# Scene 1: title card.
s1 = p.scene("Title")
title_box, rest = area.inset(100, 0).cut_top(area.h * 0.55, gap=20)
title = s1.text("Caching in two minutes", at=title_box.cut_bottom(170)[1], fontWeight=800)
subtitle = s1.text("Why the second request is faster", at=rest.cut_top(90)[0], fontSize=44, color="#94a3b8")
(s1.step("Caching, in two minutes.")
 .typewrite(title, duration=1400)
 .reveal(subtitle, style="slideInDown", distance=60))

# Scene 2: slow path, then a cache in front of the database.
s2 = p.scene("Why caches help", transition="crossfade")
app_r, cache_r, db_r = area.row(3, w=500, h=400, labels=["2 ms"])
app = s2.box("App", at=app_r, stroke="#38bdf8")
cache = s2.box("Cache", at=cache_r, fill="#3b0764", stroke="#c084fc")
db = s2.node("cylinder", "Database", at=db_r.inset(40, 0), stroke="#f59e0b")
# The slow path skips over the cache, so it gets its own lane below the row.
slow = s2.arrow(app, db, "200 ms", route="below", stroke="#f59e0b", strokeStyle="dashed", arrow="both")
fast = s2.arrow(app, cache, "2 ms", stroke="#c084fc", arrow="both")

(s2.step("Without a cache, every request goes all the way to the database.")
 .reveal(app, style="slideInLeft")
 .reveal(db, style="slideInRight", offset=200)
 .draw(slow, offset=800))
(s2.step("A cache keeps recent answers close to the app.")
 .reveal(cache)
 .draw(fast))
(s2.step("The next request is answered in two milliseconds.")
 .remove(slow)
 .camera(x=(app.rect.cx + cache.rect.cx) / 2, y=cache.rect.cy, zoom=1.4))

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "two_scenes.json"))
