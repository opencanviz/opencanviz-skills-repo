"""Bars that grow one by one while their values count up. Writes bar_chart.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Most spoken languages", aspect="16:9")
s = p.scene("Speakers")
title_area, body = p.area().cut_top(110)
title = s.text("Most spoken languages (total speakers, millions)", at=title_area, fontWeight=700)
chart = s.bar_chart([("English", 1500), ("Mandarin", 1100), ("Hindi", 610), ("Spanish", 560), ("Arabic", 420)],
                    at=body.inset(80, 20), suffix="M")

s.step("Which languages do the most people speak?").reveal(title).reveal(chart, offset=300)
s.step("English leads with about one and a half billion speakers.").grow(chart, 0)
s.step("Mandarin follows with about one point one billion.").grow(chart, 1)
s.step("Then Hindi, Spanish and Arabic.").grow(chart)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "bar_chart.json"))
