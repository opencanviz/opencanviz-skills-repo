"""Events on a line that grows from one to the next. Writes timeline.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("The Apollo program", aspect="16:9")
s = p.scene("Apollo")
title_area, body = p.area().cut_top(110)
title = s.text("The Apollo program", at=title_area, fontWeight=700)
tl = s.timeline([(1961, "Kennedy sets the Moon goal"), (1967, "Apollo 1 fire"), (1968, "Apollo 8 orbits the Moon"),
                 (1969, "Apollo 11 lands"), (1972, "Apollo 17, the last landing")], at=body.inset(20, 40))

s.step("In 1961 the United States set out to land people on the Moon.").reveal(title).event(tl)
s.step("In 1967 a fire killed the Apollo 1 crew during a test.").event(tl)
s.step("In 1968 Apollo 8 became the first crewed flight around the Moon.").event(tl)
s.step("In July 1969 Apollo 11 landed.").event(tl)
s.step("Apollo 17 made the last landing in 1972.").event(tl)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "timeline.json"))
