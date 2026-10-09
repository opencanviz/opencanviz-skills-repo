"""A donut chart whose slices sweep open, with a legend. Writes pie.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Where the time goes", aspect="16:9")
s = p.scene("Day")
title_area, body = p.area().cut_top(110)
title = s.text("How a developer spends a day", at=title_area, fontWeight=700)
pie = s.pie([("Coding", 35), ("Meetings", 25), ("Reviews", 20), ("Email", 20)], at=body, donut=0.55)

s.step("Where does a working day go?").reveal(title)
s.step("Only about a third of it is spent writing code.", duration=3500).sweep(pie)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "pie.json"))
