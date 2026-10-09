"""Two panels compared side by side (stacked in portrait). Writes before_after.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Before and after caching", aspect="16:9")
s = p.scene("Compare")
title_area, body = p.area().cut_top(110)
title = s.text("Adding a cache", at=title_area, fontWeight=700)
before, after = s.panels(["Before", "After"], at=body)
b_text = s.text("Every request goes to the database: 120 ms", at=before.content)
a_text = s.text("Most requests hit the cache: 8 ms", at=after.content)

s.step("Here is the same page before and after a cache.").reveal(title)
s.step("Before, every request went all the way to the database.").reveal(before).reveal(b_text, offset=300)
s.step("After, most requests are answered from memory.").reveal(after).reveal(a_text, offset=300)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "before_after.json"))
